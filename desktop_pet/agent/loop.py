# author: bdth
# email: 2074055628@qq.com
# Agent 主循环：驱动 LLM 多步工具调用、子代理/后台任务、计划与反思

from __future__ import annotations

import copy
import json
import os
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from openai import BadRequestError, OpenAI

from desktop_pet.agent import tools
from desktop_pet.agent.progress import PLAN_ICON, describe_step, render_plan
from desktop_pet.agent import prompts
from desktop_pet.agent.prompts import SUBAGENT_PROMPT, SYSTEM_PROMPT, language_hint
from desktop_pet.agent.streaming import StreamMessage, reassemble
from desktop_pet.audit import audit
from desktop_pet.docs import docs, read_file_text
from desktop_pet.emotion.state import emotion
from desktop_pet.executor import pycode, safety, shell, web
from desktop_pet import i18n, journal, persona
from desktop_pet.mcp_hub import mcp_hub
from desktop_pet.usage import meter as usage_meter
from desktop_pet.memory.store import store
from desktop_pet.settings import AUTONOMY_BUDGETS, DATA_DIR, Settings, atomic_write_text, build_http_client
from desktop_pet.skills import skills

_SUBAGENT_BUDGET = (12, 40)
_MAX_EMPTY_RETRIES = 2
_FRESH_AFTER = 25 * 60
_RUN_CANCELLED = "\x00cancelled"
_MAX_SUBAGENT_DEPTH = 1
_SPAWN_TOOL = "spawn_agent"
_BACKGROUND_TOOL = "start_background_task"
_PLAN_TOOL = "plan"
_IMAGE_TOOL = "show_image"
_GIF_TOOL = "play_gif"
_PERFORM_TOOL = "perform"
_CONFIRM_TOOL = "confirm"
_WATCH_TOOL = "set_screen_watch"
_WORKFLOW_TOOL = "spawn_workflow"
_MAX_WORKFLOW_TASKS = 8
_COSMETIC_TOOLS = frozenset({_PERFORM_TOOL, _PLAN_TOOL, _IMAGE_TOOL, _GIF_TOOL})
_REFLECT_MIN_CHARS = 50
_ATTACH_FILE_CHARS = 6000
_SUMMARY_MAX_CHARS = 4_000
_SUMMARY_SRC_MAX_CHARS = 12_000
_SUMMARY_TIMEOUT = 30.0
_SESSION_PATH = DATA_DIR / "session.json"
def _perform_names() -> str:
    from desktop_pet.pet.behaviors import registry
    from desktop_pet.pet.behaviors.registry import Category
    from desktop_pet.pet.character import _ACTIVITIES
    reactions = sorted(n for n in registry.names(Category.REACTION))
    return "skits: " + " ".join(_ACTIVITIES) + " ; actions: " + " ".join(reactions)


def _is_performable(name: str) -> bool:
    from desktop_pet.pet.behaviors import registry
    from desktop_pet.pet.behaviors.registry import Category
    from desktop_pet.pet.character import _ACTIVITIES
    if name in _ACTIVITIES:
        return True
    spec = registry.get(name)
    return spec is not None and spec.category == Category.REACTION
_WEB_TOOLS = frozenset({"web_search", "web_fetch", "http_request", "install_package"})
_CONTROL_TOOLS = frozenset({
    "screenshot", "screen_elements", "act_element", "list_windows", "focus_window", "manage_window",
    "click", "double_click", "right_click", "move_mouse", "scroll", "type_text", "press_keys",
    "read_clipboard", "write_clipboard", "read_process_memory", "recall_clipboard",
    _WATCH_TOOL,
})
_SHELL_TOOLS = frozenset({
    "run_shell", "run_python", "run_skill", "create_skill", "edit_skill", "write_file", "edit_file",
    "review_diff", "run_tests",
})
_MAX_PARALLEL_SUBAGENTS = 4
_MAX_BG_TASKS = 3
_BG_TASK_SEMAPHORE = threading.Semaphore(_MAX_BG_TASKS)
_BG_ACTIVE = 0
_BG_ACTIVE_LOCK = threading.Lock()
_REFLECT_SEMAPHORE = threading.Semaphore(1)
_HISTORY_TOKEN_BUDGET = 24_000
_MAX_TOOL_RESULT_CHARS = 8_000
_TOKENS_PER_CJK_CHAR = 1.0
_TOKENS_PER_OTHER_CHAR = 0.25
_TOKENS_PER_MESSAGE = 4
_TOKENS_PER_IMAGE = 1_200

_REQUEST_TIMEOUT = httpx.Timeout(connect=8.0, read=90.0, write=30.0, pool=8.0)
_BACKGROUND_TIMEOUT = 45.0
_MAX_RETRIES = 1

def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x3400 <= o <= 0x9FFF or 0x3000 <= o <= 0x30FF or 0xF900 <= o <= 0xFAFF
            or 0xFF00 <= o <= 0xFFEF or 0x20000 <= o <= 0x3FFFF)


def _text_tokens(text: str) -> int:
    cjk = sum(1 for ch in text if _is_cjk(ch))
    return int(cjk * _TOKENS_PER_CJK_CHAR + (len(text) - cjk) * _TOKENS_PER_OTHER_CHAR)


def _estimate_tokens(message: dict) -> int:
    """毛估一条消息的 token，只为裁历史算预算——不接真 tokenizer（多依赖、还得对上各家分词）。
    宁可估多点早裁，别撑爆上下文。"""
    total = _TOKENS_PER_MESSAGE
    content = message.get("content")
    if isinstance(content, str):
        total += _text_tokens(content)
    elif isinstance(content, list):
        for part in content:
            if part.get("type") == "image_url":
                total += _TOKENS_PER_IMAGE
            else:
                total += _text_tokens(part.get("text", ""))
    for call in message.get("tool_calls") or []:
        fn = call.get("function", {})
        total += _text_tokens((fn.get("name") or "") + (fn.get("arguments") or ""))
    return total


def _cap_tool_result(text: str) -> str:
    """工具输出太长就掐成头尾两段——头多尾少（5:3），开头一般是命令/状态、结尾常是报错或结论，中间最不重要。"""
    if len(text) <= _MAX_TOOL_RESULT_CHARS:
        return text
    head = _MAX_TOOL_RESULT_CHARS * 5 // 8
    tail = _MAX_TOOL_RESULT_CHARS - head
    omitted = len(text) - head - tail
    return (text[:head] + f"\n…[输出过长，中间省略 {omitted} 字符；头尾都保留了]…\n" + text[-tail:])


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think_leak(text: str) -> str:
    """清掉 <think>…</think> 思维链泄漏——有的模型/网关不吃 enable_thinking，会把思考直接吐进正文。"""
    if not text or "think>" not in text:
        return text
    text = _THINK_BLOCK_RE.sub("", text)
    return text.replace("<think>", "").replace("</think>", "").strip()


_PLAN_STATUS_ALIAS = {
    "done": "done", "completed": "done", "complete": "done", "finished": "done",
    "finish": "done", "ok": "done", "success": "done", "✓": "done", "x": "done",
    "doing": "doing", "in_progress": "doing", "in-progress": "doing", "inprogress": "doing",
    "active": "doing", "current": "doing", "running": "doing", "wip": "doing", "ongoing": "doing", "started": "doing",
    "todo": "todo", "pending": "todo", "not_started": "todo", "queued": "todo", "waiting": "todo",
}


def _norm_plan_status(status) -> str:
    """把模型给的各种状态写法归一到 todo/doing/done，避免 'completed' 这种同义词被当未开始而"重置"清单。"""
    return _PLAN_STATUS_ALIAS.get(str(status or "").strip().lower(), "todo")


def _parse_json(text: str) -> dict | None:
    """从一段可能裹着废话/代码围栏的文本里抠出最外层 {…} 当 dict——只认对象，失败给 None。"""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _parse_json_value(text: str) -> dict | list | None:
    """比 _parse_json 宽：对象和数组都收，子代理按 result_schema 返回时用——schema 可能要的是 [...] 而非 {...}。"""
    best: tuple[int, dict | list] | None = None
    for opener, closer in (("{", "}"), ("[", "]")):
        end = text.rfind(closer)
        start = text.find(opener)
        for _ in range(4):  # 最多往后挪 4 个开括号试探，防止开头一个孤立的 { 让整段解析失败
            if start == -1 or end <= start:
                break
            try:
                data = json.loads(text[start : end + 1])
            except (json.JSONDecodeError, ValueError):
                start = text.find(opener, start + 1)
                continue
            if isinstance(data, (dict, list)) and (best is None or start < best[0]):
                best = (start, data)
            break
    return best[1] if best else None


def _render_transcript(messages: list[dict]) -> str:
    """把被裁掉的消息压成纯文本喂给压缩模型——图片只留占位、每条截到 500 字，整体过长就掐头尾。"""
    lines: list[str] = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content")
        if isinstance(content, list):
            texts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
            text = " ".join(t for t in texts if t).strip() or "[图片]"
        else:
            text = str(content or "").strip()
        if role == "assistant":
            calls = m.get("tool_calls") or []
            if calls:
                names = ", ".join(
                    f"{c.get('function', {}).get('name', '?')}({(c.get('function', {}).get('arguments') or '')[:100]})"
                    for c in calls
                )
                text = (text + " " if text else "") + f"[调用工具: {names}]"
        elif role == "tool":
            text = "[工具结果] " + text
        if text:
            lines.append(f"{role}: {text[:500]}")
    out = "\n".join(lines)
    if len(out) > _SUMMARY_SRC_MAX_CHARS:
        half = _SUMMARY_SRC_MAX_CHARS // 2
        out = out[:half] + "\n…(中间略)…\n" + out[-half:]
    return out


class Agent:
    def __init__(
        self, settings: Settings, *, depth: int = 0,
        notify: Callable[[str, str], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self._settings = settings
        self._depth = depth
        self._notify = notify
        self._oa_client: OpenAI | None = None
        self._oa_creds: tuple[str, str, str] | None = None
        self._client_lock = threading.Lock()
        self._shell = shell.new_session()
        self._python = pycode.new_runner()
        self._compressed = ""
        self._risk_approval = False
        self._known_files: dict[str, float] = {}
        self._messages: list[dict] = [self._system_message()]
        self._plan: list[dict] = []
        self._on_confirm: Callable[[str], bool] | None = None
        self._tools = self._build_tools()
        self._cancel = cancel_event or threading.Event()
        self._owns_cancel = cancel_event is None
        self._on_perform: Callable[[str], bool] | None = None
        self._turn_used_tools = False
        self._turn_substantive = True
        self._hit_step_limit = False
        self._last_active = 0.0
        self._turn_user_idx = -1
        self._strip_extra_body = False  # 这两个 strip 标记：某些网关不认 extra_body/stream_options，首次 400 后记下来别再发
        self._strip_stream_options = False
        if depth == 0:
            self._try_restore_session()  # 只主代理恢复上次会话；子代理是一次性的，没历史可接

    def _build_tools(self) -> list[dict]:
        """按深度+面板开关裁工具单：子代理不能再开子代理/后台/看屏；web/control/shell 三类各自受权限位控制。"""
        excluded: set[str] = set()
        if self._depth >= _MAX_SUBAGENT_DEPTH:
            excluded |= {_SPAWN_TOOL, _BACKGROUND_TOOL, _WORKFLOW_TOOL, _WATCH_TOOL}
        if self._notify is None:
            excluded.add(_BACKGROUND_TOOL)
        if self._on_confirm is None:
            excluded.add(_CONFIRM_TOOL)
        if not self._settings.allow_web:
            excluded |= _WEB_TOOLS
        if not self._settings.allow_control:
            excluded |= _CONTROL_TOOLS
        if not self._settings.allow_shell:
            excluded |= _SHELL_TOOLS
        offered = [t for t in tools.TOOLS if t["function"]["name"] not in excluded]
        return offered + mcp_hub.tool_schemas()

    def forget_all(self) -> None:
        """彻底失忆：长期记忆/日记/人格/知识库连同当前会话一起清空——和 new_topic 不同，这个不可逆。"""
        for wipe in (store.wipe, journal.clear, persona.clear, docs.forget):
            try:
                wipe()
            except Exception:
                pass
        self._compressed = ""
        self._known_files.clear()
        self._clear_session_file()
        self._messages = [self._system_message()]
        self._plan = []
        self._turn_user_idx = -1

    def new_topic(self) -> None:
        """翻篇：只清当前对话窗口（含压缩摘要/落盘会话），长期记忆/情绪/人格全部保留。"""
        self._compressed = ""
        self._known_files.clear()
        self._clear_session_file()
        self._messages = [self._system_message()]
        self._plan = []
        self._turn_user_idx = -1
        self._last_active = 0.0

    def cancel(self) -> None:
        self._cancel.set()
        threading.Thread(target=self._teardown_io, daemon=True, name="mochi-cancel-io").start()

    def _teardown_io(self) -> None:
        try:
            self._shell.close()
        except Exception:
            pass
        try:
            self._python.close()
        except Exception:
            pass
        with self._client_lock:
            client = self._oa_client
            self._oa_client = None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    @staticmethod
    def was_cancelled(reply: str) -> bool:
        return reply == _RUN_CANCELLED

    @property
    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    def _seal_pending_tool_calls(self, note: str) -> None:
        """给每个还没拿到结果的 tool_call 补一条占位结果——悬空的 tool_call 会让下一次请求格式非法。
        中断/出错/重启时都用它把历史补回合法状态，又不丢掉"刚才在干嘛"。"""
        have = {m.get("tool_call_id") for m in self._messages if m.get("role") == "tool"}
        pending = []
        for m in self._messages:
            if m.get("role") == "assistant":
                for call in m.get("tool_calls") or []:
                    cid = call.get("id")
                    if cid and cid not in have:
                        pending.append(cid)
                        have.add(cid)
        for cid in pending:
            self._messages.append({"role": "tool", "tool_call_id": cid, "content": note})

    def _seal_cancelled(self) -> None:
        self._seal_pending_tool_calls("[用户中断了这次操作，这一步没有执行完。]")

    @property
    def hit_step_limit(self) -> bool:
        return self._hit_step_limit

    def set_notify(self, notify: Callable[[str, str], None]) -> None:
        self._notify = notify
        self._tools = self._build_tools()

    def set_confirm(self, on_confirm: Callable[[str], bool]) -> None:
        self._on_confirm = on_confirm
        self._tools = self._build_tools()

    def close(self) -> None:
        if self._depth == 0:
            self._save_session()
        self._shell.close()
        self._python.close()

    def _system_message(self) -> dict:
        """系统提示——刻意只放"基本不变"的东西（人格/技能/日记/压缩摘要），把会变的状态挪到 _turn_context。
        这样 system 段长期稳定，前缀缓存能逐字节命中，省 token。"""
        if self._depth > 0:
            return {"role": "system", "content": SUBAGENT_PROMPT}
        parts = [SYSTEM_PROMPT]
        lang = language_hint(self._settings.language)
        if lang:
            parts.append(lang)
        skills_context = skills.as_context()
        if skills_context:
            parts.append(skills_context)
        persona_context = persona.as_context()
        if persona_context:
            parts.append(persona_context)
        journal_context = journal.as_context()
        if journal_context:
            parts.append(journal_context)
        if self._compressed:
            parts.append(
                "[前情摘要] 本次对话更早的部分因超长被压缩成了下面这份备忘——"
                "这些事真实发生过，里面的约束和决定仍然有效：\n" + self._compressed
            )
        return {"role": "system", "content": "\n\n".join(parts)}

    def _turn_context(self, query: str | None = None) -> str:
        """每轮现算的状态注记（情绪/时间/相关记忆），塞进当轮 user 消息——所以历史里的旧注记都过期，以最新这条为准。"""
        parts = [emotion.tone_hint(), prompts.time_hint()]
        memory_context = store.as_context(query)
        if memory_context:
            parts.append(memory_context)
        return "[当前状态注记——以这条最新的为准，历史消息里的同类注记已过期]\n" + "\n\n".join(parts)

    def _prepare(self) -> None:
        """每次请求前刷新：裁历史、重建 system(可能并入了新摘要)、重算工具单(权限/深度可能变了)。"""
        self._trim_history()
        self._messages[0] = self._system_message()
        self._tools = self._build_tools()

    def _history_budget(self) -> int:
        """历史 token 预算取用户设置，没填/非法/非正就退回默认；再低也兜个 8000，太小连最近几轮都装不下。"""
        try:
            value = int(self._settings.history_tokens)
        except (TypeError, ValueError, AttributeError):
            return _HISTORY_TOKEN_BUDGET
        if value <= 0:
            return _HISTORY_TOKEN_BUDGET
        return max(8_000, value)

    def _trim_history(self) -> None:
        """从尾往头累计 token，超预算就把前面的裁掉——裁掉的不是直接扔，交给 _compress_history 压成摘要存进 system。"""
        n = len(self._messages)
        if n <= 2:
            return
        budget = self._history_budget()
        used = 0
        start = n
        for i in range(n - 1, 0, -1):
            used += _estimate_tokens(self._messages[i])
            if used > budget and i < n - 1:
                break
            start = i
        # 别让保留段以 tool 消息打头——开头悬着个没有对应 assistant tool_call 的 tool，请求会被判非法
        while start < n and self._messages[start].get("role") == "tool":
            start += 1
        if start > 1:
            dropped = self._messages[1:start]
            del self._messages[1:start]
            self._compress_history(dropped)

    def _compress_history(self, dropped: list[dict]) -> None:
        """把裁掉的对话叫模型缩成一份备忘，和已有摘要滚动合并——用便宜的 subagent_model，没配就退回主模型。
        摘要失败也不能丢得无声无息：补一句"细节已不可考"，至少让它知道前面发生过事。"""
        transcript = _render_transcript(dropped)
        if not transcript:
            return
        source = ""
        if self._compressed:
            source += "[更早的既有摘要——合并进新备忘]\n" + self._compressed + "\n\n"
        source += "[本次被裁剪的对话]\n" + transcript
        model = (getattr(self._settings, "subagent_model", "") or "").strip() or self._settings.model
        content = ""
        try:
            resp = self._client().chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompts.COMPRESS_PROMPT},
                    {"role": "user", "content": source},
                ],
                timeout=_SUMMARY_TIMEOUT,
            )
            self._meter_response(resp)
            content = (resp.choices[0].message.content or "").strip()
        except Exception:
            content = ""
        content = _strip_think_leak(content)
        if content:
            self._compressed = content[:_SUMMARY_MAX_CHARS]
        else:
            note = "(有一段更早的对话因超长被丢弃，且摘要生成失败，细节已不可考。)"
            if note not in self._compressed:
                self._compressed = (self._compressed + "\n" + note).strip()[:_SUMMARY_MAX_CHARS]

    def run(
        self,
        user_message: str,
        attachments: object = None,
        on_step: Callable[[str], None] | None = None,
        on_think: Callable[[str], None] | None = None,
        on_plan: Callable[[str], None] | None = None,
        on_media: Callable[[str, str, str], None] | None = None,
        on_perform: Callable[[str], bool] | None = None,
    ) -> str:
        """对外入口：跑一轮对话/任务，回最终文本。外面这层只负责无论怎么退出都把会话落盘（崩了也别丢上下文）。"""
        try:
            return self._run_impl(
                user_message, attachments, on_step=on_step, on_think=on_think,
                on_plan=on_plan, on_media=on_media, on_perform=on_perform,
            )
        finally:
            if self._depth == 0:
                self._save_session()

    def _run_impl(
        self,
        user_message: str,
        attachments: object = None,
        on_step: Callable[[str], None] | None = None,
        on_think: Callable[[str], None] | None = None,
        on_plan: Callable[[str], None] | None = None,
        on_media: Callable[[str, str, str], None] | None = None,
        on_perform: Callable[[str], bool] | None = None,
    ) -> str:
        """核心多步循环：补 system/记忆 → 喂用户消息 → 反复(模型出工具调用→执行→回灌结果)直到它给纯文本回复或撞步数顶。"""
        def step(message: str) -> None:
            if on_step is not None:
                on_step(message)

        def think(fragment: str) -> None:
            if on_think is not None:
                on_think(fragment)

        def emit_plan(markdown: str) -> None:
            if on_plan is not None:
                on_plan(markdown)

        def emit_media(kind: str, path: str, caption: str) -> None:
            if on_media is not None:
                on_media(kind, path, caption)

        self._plan = []
        self._turn_used_tools = False
        self._hit_step_limit = False
        self._risk_approval = False
        self._on_perform = on_perform
        if self._owns_cancel:
            self._cancel.clear()
        now = time.monotonic()
        # 隔了 25 分钟以上再开口，多半是新话题：自动翻篇，省得把半小时前的上下文硬塞进来带偏
        if (self._depth == 0 and self._last_active
                and now - self._last_active > _FRESH_AFTER and len(self._messages) > 1):
            self._compressed = ""
            self._known_files.clear()
            self._messages = [self._system_message()]
        self._last_active = now
        self._prepare()
        history_mark = len(self._messages)  # 记下落笔点：本轮中途出错就回滚到这，不留半截脏历史
        n_att = len(attachments) if isinstance(attachments, list) else 0
        audit.user(user_message + (f"  [附件×{n_att}]" if n_att else ""))
        self._messages.append({
            "role": "user",
            "content": self._compose_user_content(user_message, attachments, self._turn_context(user_message)),
        })
        self._turn_user_idx = len(self._messages) - 1
        checkpoint, hard_cap = self._budget()
        steps = 0
        empties = 0
        while steps < hard_cap:
            if self._cancel.is_set():
                self._seal_cancelled()
                return _RUN_CANCELLED
            step(i18n.thinking_label())
            try:
                message = self._complete(think)
            except Exception:
                self._seal_pending_tool_calls("[这一步请求出错中断了，没有拿到结果。]")
                raise
            if message.content:
                message.content = _strip_think_leak(message.content)
            self._messages.append(self._as_dict(message))
            if not message.tool_calls:
                reply = message.content or ""
                if not reply.strip():
                    # 既没工具又没正文——有的模型偶尔抽风返回空，催一两次再放弃，别让用户对着空白
                    empties += 1
                    if empties <= _MAX_EMPTY_RETRIES and steps < hard_cap:
                        self._messages.append({"role": "user", "content": prompts.EMPTY_REPLY_NUDGE})
                        steps += 1
                        continue
                    del self._messages[history_mark:]
                    self._turn_substantive = False
                    audit.reply("[empty reply]")
                    return prompts.EMPTY_REPLY_FALLBACK
                # 这轮够不够"实质"决定事后要不要 reflect：动过工具，或者一问一答总长过线，才值得反思沉淀
                self._turn_substantive = (
                    self._turn_used_tools or (len(user_message) + len(reply)) >= _REFLECT_MIN_CHARS
                )
                audit.reply(reply)
                return reply

            if message.content:
                step(message.content.strip())

            if self._cancel.is_set():
                self._seal_cancelled()
                return _RUN_CANCELLED

            images: list[str] = []
            parsed = [(c, _parse_json(c.function.arguments or "{}")) for c in message.tool_calls]
            truncated = message.finish_reason == "length"  # 参数 JSON 解析失败时用它区分：是被 max_tokens 截了，还是模型本来就吐了坏 JSON
            if any(c.function.name not in _COSMETIC_TOOLS for c, _ in parsed):
                self._turn_used_tools = True
            results: dict[str, tools.ToolResult] = {}

            for call, arguments in parsed:
                if arguments is not None:
                    continue
                results[call.id] = tools.ToolResult(
                    "[输出在工具参数中途被 max_tokens 截断，这一步没有执行——把这一步拆小一点，或请用户调大 max_tokens。]"
                    if truncated else
                    f"[tool {call.function.name} 的参数不是合法 JSON，这一步没有执行——用合法 JSON 重新调用一次。]"
                )

            # 一轮里要起好几个子代理就并发跑——彼此独立，串行等会很慢。单个的走下面普通分支即可
            spawns = [(c, a) for c, a in parsed if c.function.name == _SPAWN_TOOL and c.id not in results]
            if len(spawns) > 1:
                for c, a in spawns:
                    step(describe_step(c.function.name, a))
                with ThreadPoolExecutor(max_workers=min(_MAX_PARALLEL_SUBAGENTS, len(spawns))) as pool:
                    futures = {
                        pool.submit(self._run_subagent, a.get("task", ""), None, a.get("result_schema")): c.id
                        for c, a in spawns
                    }
                    for future in as_completed(futures):
                        results[futures[future]] = tools.ToolResult(future.result())

            for call, arguments in parsed:
                if call.id in results:
                    continue
                if call.function.name != _PERFORM_TOOL:
                    step(describe_step(call.function.name, arguments))
                if call.function.name == _SPAWN_TOOL:
                    results[call.id] = tools.ToolResult(self._run_subagent(arguments.get("task", ""), step, arguments.get("result_schema")))
                elif call.function.name == _WORKFLOW_TOOL:
                    results[call.id] = tools.ToolResult(self._run_workflow(
                        arguments.get("mode", "fanout"), arguments.get("tasks", []),
                        arguments.get("result_schema"), step))
                elif call.function.name == _BACKGROUND_TOOL:
                    results[call.id] = tools.ToolResult(self._start_background_task(arguments.get("task", "")))
                elif call.function.name == _PLAN_TOOL:
                    results[call.id] = tools.ToolResult(self._update_plan(arguments.get("steps", []), emit_plan))
                elif call.function.name in (_IMAGE_TOOL, _GIF_TOOL):
                    results[call.id] = tools.ToolResult(self._show_media(call.function.name, arguments, emit_media))
                elif call.function.name == _PERFORM_TOOL:
                    results[call.id] = tools.ToolResult(self._perform(arguments.get("name", "")))
                elif call.function.name == _CONFIRM_TOOL:
                    results[call.id] = tools.ToolResult(self._confirm(arguments.get("action", "")))
                elif call.function.name == _WATCH_TOOL:
                    results[call.id] = tools.ToolResult(self._set_screen_watch(arguments))
                else:
                    # 普通工具走 dispatch 前先过两道闸：高危命令要确认、edit 前必须先 read 过且文件没被人改动
                    denial = (self._guard_risky(call.function.name, arguments)
                              or self._guard_edit(call.function.name, arguments))
                    if denial is not None:
                        results[call.id] = tools.ToolResult(denial)
                    else:
                        results[call.id] = tools.dispatch(
                            call.function.name, arguments,
                            shell_session=self._shell, py_session=self._python,
                        )
                        self._note_file(call.function.name, arguments)

            for call, arguments in parsed:
                result = results[call.id]
                audit.tool(call.function.name, arguments or {}, result.text)
                self._messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": _cap_tool_result(result.text)}
                )
                if result.image_data_url:
                    images.append(result.image_data_url)
            if images:
                self._append_images(images)
            if self._cancel.is_set():
                self._seal_cancelled()
                return _RUN_CANCELLED
            steps += 1
            # 每隔 checkpoint 步插一句"停下来想想是不是跑偏了"，防止它埋头钻进死胡同一直耗步数
            if steps < hard_cap and steps % checkpoint == 0:
                self._messages.append({"role": "user", "content": prompts.step_checkpoint_nudge(steps)})
        self._hit_step_limit = True
        self._turn_substantive = True
        if self._cancel.is_set():
            self._seal_cancelled()
            return _RUN_CANCELLED
        step(i18n.thinking_label())
        # 撞到步数顶：最后再求一次纯文本收尾，不给工具（offer_tools=False）——再给它又会继续调，收不了场
        self._messages.append({"role": "user", "content": prompts.STEP_LIMIT_NUDGE})
        try:
            message = self._complete(think, offer_tools=False)
            self._messages.append(self._as_dict(message))
            reply = _strip_think_leak(message.content or "")
        except Exception as exc:
            audit.reply(f"[step-limit 收尾调用失败: {type(exc).__name__}: {exc}]")
            reply = ""
        if not reply:
            reply = "[confused]\n这个任务我试了好多步还是没搞定，先停一下——可能太复杂、或者得用管理员权限再来。"
        audit.reply(reply)
        return reply

    def _budget(self) -> tuple[int, int]:
        """(检查点间隔, 安全顶)。子代理/后台用固定小预算防递归放大；主代理按面板的"放手程度"。"""
        if self._depth > 0:
            return _SUBAGENT_BUDGET
        return AUTONOMY_BUDGETS.get(self._settings.autonomy, AUTONOMY_BUDGETS["正常"])

    def _client(self) -> OpenAI:
        """懒建并缓存 OpenAI 客户端；key/base_url/proxy 任一变了就重建，顺手关掉旧的别漏连接。"""
        creds = (self._settings.api_key, self._settings.base_url, self._settings.proxy)
        with self._client_lock:
            if self._oa_client is None or self._oa_creds != creds:
                old = self._oa_client
                self._oa_client = OpenAI(
                    api_key=self._settings.api_key or "missing",
                    base_url=self._settings.base_url,
                    timeout=_REQUEST_TIMEOUT,
                    max_retries=_MAX_RETRIES,
                    http_client=build_http_client(self._settings.proxy),
                )
                self._oa_creds = creds
                self._strip_extra_body = False
                self._strip_stream_options = False
                if old is not None:
                    try:
                        old.close()
                    except Exception:
                        pass
            return self._oa_client

    def _model_name(self) -> str:
        """子代理优先用单独配的小模型（省钱省时），没配才退回主模型；主代理永远用主模型。"""
        if self._depth > 0:
            sub = (getattr(self._settings, "subagent_model", "") or "").strip()
            if sub:
                return sub
        return self._settings.model

    def _complete(self, on_think: Callable[[str], None], offer_tools: bool = True) -> StreamMessage:
        """发一次流式补全并回灌用量。带 extra_body(enable_thinking)/stream_options 这些非标参数——
        碰到不认它们的网关会 400，于是逐个剥掉重试并记标记，下次直接不带。"""
        params: dict = {
            "model": self._model_name(),
            "messages": self._messages,
            "stream": True,
            "temperature": self._settings.temperature,
        }
        if offer_tools:
            params["tools"] = self._tools
        if self._settings.max_tokens > 0:
            params["max_tokens"] = self._settings.max_tokens
        if self._wants_thinking_param():
            params["extra_body"] = {"enable_thinking": self._settings.enable_thinking}
        if not self._strip_stream_options:
            params["stream_options"] = {"include_usage": True}
        try:
            stream = self._client().chat.completions.create(**params)
        except BadRequestError:
            # 先怀疑 extra_body（最容易被拒），剥了还 400 再剥 stream_options；都不是就如实抛出
            if "extra_body" in params:
                params.pop("extra_body")
                try:
                    stream = self._client().chat.completions.create(**params)
                    self._strip_extra_body = True
                except BadRequestError:
                    if "stream_options" not in params:
                        raise
                    params.pop("stream_options")
                    stream = self._client().chat.completions.create(**params)
                    self._strip_extra_body = True
                    self._strip_stream_options = True
            elif "stream_options" in params:
                params.pop("stream_options")
                stream = self._client().chat.completions.create(**params)
                self._strip_stream_options = True
            else:
                raise
        message = reassemble(stream, on_think, should_cancel=self._cancel.is_set)
        if message.usage:
            usage_meter.add(message.usage["input"], message.usage["output"], message.usage.get("cached", 0))
        return message

    def _meter_response(self, resp) -> None:
        """记一次非流式调用的用量（摘要/反思/旁路那些）。整段 try 兜底——计费失败绝不能拖垮正经请求。"""
        try:
            u = resp.usage
            if u is None:
                return
            cached = 0
            details = getattr(u, "prompt_tokens_details", None)  # 命中缓存的 token 藏在这，单独算便宜价
            if details is not None:
                cached = int(getattr(details, "cached_tokens", 0) or 0)
            usage_meter.add(int(u.prompt_tokens or 0), int(u.completion_tokens or 0), cached)
        except Exception:
            pass

    def _wants_thinking_param(self) -> bool:
        # 官方 openai.com 不认 enable_thinking，直接别发；之前被网关 400 剥过(strip 标记)的也别再发
        if self._strip_extra_body:
            return False
        return "api.openai.com" not in (self._settings.base_url or "").lower()

    def _update_plan(self, steps: list, emit_plan: Callable[[str], None]) -> str:
        """收下模型给的整张计划清单（每次都是全量覆盖，不是增量），洗一遍状态后渲染到面板。回一句进度给模型。"""
        cleaned: list[dict] = []
        for raw in steps or []:
            if isinstance(raw, dict) and str(raw.get("text", "")).strip():
                cleaned.append(
                    {"text": str(raw["text"]).strip(), "status": _norm_plan_status(raw.get("status"))}
                )
        self._plan = cleaned
        if cleaned:
            emit_plan(render_plan(cleaned))
        done = sum(1 for step in cleaned if step["status"] == "done")
        return f"Plan updated: {done}/{len(cleaned)} done."

    def _show_media(self, tool_name: str, arguments: dict, emit_media: Callable[[str, str, str], None]) -> str:
        """在桌宠旁弹图/GIF。source 可以是本地路径或 URL；显示前先用 PIL verify 一遍，免得把坏文件塞给 UI 崩掉。"""
        source = str(arguments.get("source", "")).strip()
        caption = str(arguments.get("caption", "")).strip()
        kind = "gif" if tool_name == _GIF_TOOL else "image"
        noun = "GIF" if kind == "gif" else "image"
        if not source:
            return f"(no {noun} source given)"
        path = self._fetch_media(source)
        if path is None:
            return f"(couldn't get that {noun}: {source})"
        try:
            from PIL import Image
            Image.open(path).verify()
        except Exception:
            return f"(那个{noun}打不开或格式损坏，没法显示: {source})"
        emit_media(kind, path, caption)
        return f"{'Looped that GIF' if kind == 'gif' else 'Showed that image'} beside the user."

    def _perform(self, name: str) -> str:
        """让桌宠当场做个动作/演段小剧场。名字不在册就把可选项列回去让它重挑，别默默吞掉。"""
        name = (name or "").strip()
        if not _is_performable(name):
            return f"(I don't have a \"{name}\" move. Options — {_perform_names()})"
        hook = self._on_perform
        if hook is None:
            return "(Can't do that move right now.)"
        hook(name)
        return f"OK, doing the \"{name}\" move now."

    def _confirm(self, action: str) -> str:
        """让模型主动求用户点确认。点了「执行」就置 _risk_approval，给紧随其后的高危调用放一次行。
        没有确认 UI（后台/子代理）一律按"未批准"处理——宁可不做，别擅自动手。"""
        action = (action or "").strip()
        if not action:
            return "(No action described — nothing to confirm.)"
        if self._on_confirm is None:
            return "(No confirm UI available here; treat as NOT approved — skip it, or have the user do it in the foreground.)"
        approved = self._on_confirm(action)
        if approved:
            self._risk_approval = True
            return "User tapped 执行 — approved, go ahead."
        return "User tapped 不执行 — rejected; do NOT do it, just acknowledge briefly."

    def _guard_risky(self, name: str, arguments: dict) -> str | None:
        """执行 shell/python/测试前扫一遍危险命令；命中就弹确认。返回拒绝文案=拦下，None=放行。"""
        if name == "run_shell":
            text = str(arguments.get("command") or "")
        elif name == "run_python":
            text = str(arguments.get("code") or "")
        elif name == "run_tests":
            text = str(arguments.get("command") or "")
        else:
            return None
        risk = safety.check_risky(text)
        if risk is None:
            return None
        if self._risk_approval:
            self._risk_approval = False  # 刚通过 confirm 拿到的放行只用一次，用完立刻清，别让后续命令蹭这张通行证
            return None
        if self._on_confirm is None:
            return (f"[安全拦截：这一步包含高危操作（{risk}），而当前环境（后台/子代理）没有确认按钮，"
                    "没有执行。需要的话改在前台对话里做，由用户确认后执行。]")
        if self._on_confirm(f"高危操作：{risk}\n{text[:200]}"):
            return None
        return f"[用户点了「不执行」——这个高危操作（{risk}）被拒绝了。不要再尝试，简短告知用户即可。]"

    @staticmethod
    def _file_key(path: str) -> str:
        """把路径归一成 _known_files 的键——normcase 抹掉 Windows 大小写差异，别让同一文件存成两条。"""
        try:
            return os.path.normcase(str(Path(path).expanduser().resolve()))
        except (OSError, ValueError):
            return os.path.normcase(str(Path(path).expanduser()))  # resolve 失败（盘符没了/路径非法）也别崩，退一步用没解析的

    def _guard_edit(self, name: str, arguments: dict) -> str | None:
        """edit_file 前的护栏：没 read 过就先 read；读过但 mtime 变了（run_python/外部程序动过）也打回去重读。
        不然 old 是凭记忆写的，对不上真实现状，edit 要么打偏要么悄悄改错地方。"""
        if name != "edit_file":
            return None
        path = str(arguments.get("path") or "")
        if not path:
            return None
        key = self._file_key(path)
        known = self._known_files.get(key)
        if known is None:
            return (f"[先用 read_file 看一遍 {path} 的当前内容，再来 edit——"
                    "old 必须照着文件的真实现状写，不能凭记忆。]")
        try:
            mtime = os.path.getmtime(key)
        except OSError:
            return None
        if mtime != known:
            self._known_files.pop(key, None)
            return (f"[{path} 在你上次读取之后被改动过（可能是 run_python、命令或外部程序干的）——"
                    "重新 read_file 拿到当前内容再改，别基于过期的内容编辑。]")
        return None

    def _note_file(self, name: str, arguments: dict) -> None:
        """读/写/改成功后记下该文件此刻的 mtime，作为 _guard_edit 下次比对的基准。"""
        if name not in ("read_file", "write_file", "edit_file"):
            return
        path = str(arguments.get("path") or "")
        if not path:
            return
        key = self._file_key(path)
        try:
            self._known_files[key] = os.path.getmtime(key)
        except OSError:
            self._known_files.pop(key, None)


    def _save_session(self) -> None:
        """把当前会话落盘，下次启动接上。原子写避免写一半崩了留个坏文件；system 消息不存(每次重建)。"""
        try:
            data = {
                "saved_at": time.time(),
                "compressed": self._compressed,
                "messages": self._strip_images_for_save(self._messages[1:]),
            }
            atomic_write_text(_SESSION_PATH, json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    @staticmethod
    def _strip_images_for_save(messages: list[dict]) -> list[dict]:
        """落盘前把图片消息压成纯文本占位——base64 截图又大又没法跨重启复用，存了纯属浪费磁盘。"""
        out: list[dict] = []
        for m in messages:
            m2 = dict(m)
            content = m2.get("content")
            if isinstance(content, list):
                texts = [p.get("text", "") for p in content
                         if isinstance(p, dict) and p.get("type") == "text"]
                m2["content"] = " ".join(t for t in texts if t).strip() or "[图片已在重启时省略]"
            out.append(m2)
        return out

    @staticmethod
    def _clear_session_file() -> None:
        try:
            _SESSION_PATH.unlink(missing_ok=True)
        except OSError:
            pass

    def _try_restore_session(self) -> None:
        """启动时尝试接上上次会话——超过 25 分钟的就当过期不接（同 _FRESH_AFTER 的"隔太久算新话题"口径）。
        全程对脏数据宽容：解析失败/格式不对/空了，直接放弃当无会话可恢复。"""
        try:
            data = json.loads(_SESSION_PATH.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(data, dict):
            return
        saved_at = data.get("saved_at")
        if not isinstance(saved_at, (int, float)) or time.time() - saved_at > _FRESH_AFTER:
            return
        messages = data.get("messages")
        if not isinstance(messages, list):
            return
        cleaned = [m for m in messages
                   if isinstance(m, dict) and m.get("role") in ("user", "assistant", "tool")]
        if not cleaned:
            return
        # 开头不能是 tool（前面对应的 assistant 没存进来就成孤儿，请求会非法）——削到第一条非 tool 为止
        while cleaned and cleaned[0].get("role") == "tool":
            cleaned.pop(0)
        if not cleaned:
            return
        compressed = data.get("compressed")
        if isinstance(compressed, str):
            self._compressed = compressed[:_SUMMARY_MAX_CHARS]
        self._messages = [self._system_message()] + cleaned
        self._seal_pending_tool_calls("[这一步执行到一半时程序重启了，没有拿到结果。]")
        self._last_active = time.monotonic()

    @staticmethod
    def _fetch_media(source: str) -> str | None:
        local = Path(source)
        if local.is_file():
            return str(local)
        if source.lower().startswith(("http://", "https://")):
            return web.download_to_temp(source)
        return None

    def _run_subagent(self, task: str, step: Callable[[str], None] | None, result_schema: str | None = None) -> str:
        """派一个深一层的临时代理干一件子事，跑完即弃（共用同一个 cancel，主代理一停它也停）。
        给了 result_schema 就要求只回 JSON，并在 _validate_schema_result 里校验+重试一次。"""
        if self._depth >= _MAX_SUBAGENT_DEPTH:
            return "(Sub-agents can't spawn their own sub-agents — do it yourself or report back.)"
        task = (task or "").strip()
        if not task:
            return "(No subtask given — nothing to delegate.)"
        lang = (self._settings.language or "").strip()
        if lang and lang != "跟随":
            task = f"{task}\n\n(Write your final answer in {lang}.)"
        schema = result_schema.strip() if isinstance(result_schema, str) else ""
        if schema:
            task = f"{task}\n\n(Return your final answer as ONLY a JSON object of this shape — no prose, no code fence: {schema})"
        worker = Agent(self._settings, depth=self._depth + 1, cancel_event=self._cancel)
        try:
            result = worker.run(task, on_step=step)
            if Agent.was_cancelled(result):
                return "(用户中断了操作，这个子任务没有完成。)"
            if schema:
                result = self._validate_schema_result(worker, result, schema)
        except Exception as exc:
            return f"(Sub-agent couldn't finish: {exc})"
        finally:
            worker.close()
        return result

    def _validate_schema_result(self, worker: "Agent", result: str, schema: str) -> str:
        """校验子代理结果是不是合法 JSON，不是就让它(带同一上下文)重试一次；还不行就把原话原样交回，别硬吞。"""
        parsed = _parse_json_value(result)
        if parsed is not None:
            return json.dumps(parsed, ensure_ascii=False)
        if self._cancel.is_set():
            return result
        retry = worker.run(prompts.schema_retry_nudge(schema))
        if Agent.was_cancelled(retry):
            return "(用户中断了操作，这个子任务没有完成。)"
        parsed = _parse_json_value(retry)
        if parsed is not None:
            return json.dumps(parsed, ensure_ascii=False)
        return f"[子代理重试后仍没能给出合法 JSON——以下是它的原话]\n{result}"

    def _run_workflow(self, mode: str, tasks: list, result_schema: str | None, step: Callable[[str], None] | None) -> str:
        """一组子任务两种跑法：pipeline 串着跑、把上一段输出喂下一段；fanout 并发各跑各的再汇总。
        tasks 容错——模型有时把数组塞成 JSON 字符串甚至单个字符串，这里都掰成 list。"""
        if self._depth >= _MAX_SUBAGENT_DEPTH:
            return "(Can't run a workflow from inside a sub-agent.)"
        if isinstance(tasks, str):
            s = tasks.strip()
            if s.startswith("["):
                try:
                    j = json.loads(s)
                    tasks = j if isinstance(j, list) else [s]
                except Exception:
                    tasks = [s]
            else:
                tasks = [s]
        elif not isinstance(tasks, (list, tuple)):
            tasks = [tasks] if tasks else []
        clean = [str(t).strip() for t in (tasks or []) if str(t).strip()]
        if not clean:
            return "(No tasks given for the workflow.)"
        if len(clean) > _MAX_WORKFLOW_TASKS:
            clean = clean[:_MAX_WORKFLOW_TASKS]
        if (mode or "fanout").strip().lower() == "pipeline":
            prev = ""
            for i, t in enumerate(clean, 1):
                if self._cancel.is_set():
                    return f"(Workflow stopped at stage {i}.)\n\n{prev}"
                stage = t if i == 1 else f"{t}\n\n[Previous stage's output to build on]:\n{prev}"
                prev = self._run_subagent(stage, step, result_schema if i == len(clean) else None)  # schema 只压在最后一段，中间环节不强求 JSON
            return prev
        out = [""] * len(clean)
        with ThreadPoolExecutor(max_workers=min(_MAX_PARALLEL_SUBAGENTS, len(clean))) as pool:
            futures = {pool.submit(self._run_subagent, t, None, result_schema): idx for idx, t in enumerate(clean)}
            for future in as_completed(futures):
                out[futures[future]] = future.result()
        return "\n\n".join(f"## 子任务 {i + 1}：{clean[i][:48]}\n{out[i]}" for i in range(len(clean)))

    def run_background(self, task: str) -> str:
        return self._start_background_task(task)

    def run_timed_task(
        self,
        task: str,
        on_step: Callable[[str], None] | None = None,
        on_think: Callable[[str], None] | None = None,
        on_plan: Callable[[str], None] | None = None,
        on_media: Callable[[str, str, str], None] | None = None,
        on_perform: Callable[[str], bool] | None = None,
    ) -> str:
        """定时任务到点了，用主代理身份跑一遍。跑完把对话历史还原成跑之前的样子——
        定时活儿是"插播"，不该把用户正聊的上下文搅乱、也不该污染后面的反思。"""
        snapshot = list(self._messages)
        try:
            return self.run(
                prompts.timed_task_nudge(task), on_step=on_step, on_think=on_think,
                on_plan=on_plan, on_media=on_media, on_perform=on_perform,
            )
        finally:
            self._messages = snapshot
            if self._depth == 0:
                self._save_session()

    def _start_background_task(self, task: str) -> str:
        """丢一个任务到后台线程跑，干完用 notify 回贴。最多同时 _MAX_BG_TASKS 个，超了就排队(信号量挡着)。
        立刻返回一句话给用户，不阻塞当前对话。"""
        if self._depth >= _MAX_SUBAGENT_DEPTH:
            return "(Can't start a background task from here.)"
        task = (task or "").strip()
        if not task:
            return "(No task given — didn't start one.)"
        if self._notify is None:
            return "(Background tasks aren't available in this environment.)"
        notify, settings, depth = self._notify, self._settings, self._depth

        # 先抢着把计数+1（决定这条要不要提示"已排队"），真正的并发上限靠线程里的信号量卡——
        # 计数只为给用户一句准话，别和信号量混为一谈
        global _BG_ACTIVE
        with _BG_ACTIVE_LOCK:
            queued = _BG_ACTIVE >= _MAX_BG_TASKS
            _BG_ACTIVE += 1

        def work() -> None:
            global _BG_ACTIVE
            from desktop_pet.agent.bgtasks import bg_tasks
            cancel = threading.Event()
            tid = bg_tasks.register(task, cancel)
            try:
                with _BG_TASK_SEMAPHORE:
                    worker = Agent(settings, depth=depth + 1, cancel_event=cancel)
                    try:
                        result = worker.run(task)
                    except Exception as exc:
                        result = f"(Couldn't finish it: {exc})"
                    finally:
                        worker.close()
                if not cancel.is_set():
                    notify(task, result)
            finally:
                bg_tasks.unregister(tid)
                with _BG_ACTIVE_LOCK:
                    _BG_ACTIVE -= 1

        try:
            threading.Thread(target=work, daemon=True, name="star-bg-task").start()
        except RuntimeError as exc:
            with _BG_ACTIVE_LOCK:
                _BG_ACTIVE -= 1
            return f"(Couldn't start the background task: {exc})"
        if queued:
            return (f"Already running {_MAX_BG_TASKS} background tasks, so \"{task[:30]}\" is queued — "
                    "it'll start once one frees up, and I'll tell you when it's done.")
        return f"OK, working on \"{task[:30]}\" in the background — I'll tell you when it's done."

    def deliver_reminder(self, what: str) -> str:
        """到点提醒，用它当下的口吻说出来而不是干巴巴念字条。模型搭不上话就直接退回原文，提醒不能漏。"""
        self._prepare()
        # 在历史副本上加一句就发，不写回 self._messages——主动说话是旁路，不该挤进正经对话流
        messages = copy.deepcopy(self._messages) + [
            {"role": "user", "content": self._turn_context() + "\n\n" + prompts.reminder_nudge(what)}
        ]
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
            )
            self._meter_response(resp)
            content = (resp.choices[0].message.content or "").strip()
        except Exception:
            content = ""
        content = _strip_think_leak(content)
        if not content:
            content = f"[neutral]\n{what}"
        audit.reply(content, proactive=True)
        return content

    def speak_spontaneously(self, mode: str, context: str = "") -> str:
        """没人开口时它自己冒一句（闲聊/关心/吐槽，看 mode）。同样走历史副本、不落库；憋不出就返回空串，宁可不说。"""
        self._prepare()
        nudge = prompts.spontaneous_nudge(mode)
        if context.strip():
            nudge = context.strip() + "\n" + nudge
        messages = copy.deepcopy(self._messages) + [
            {"role": "user", "content": self._turn_context() + "\n\n" + nudge}
        ]
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
            )
            self._meter_response(resp)
            content = (resp.choices[0].message.content or "").strip()
        except Exception:
            return ""
        content = _strip_think_leak(content)
        if content:
            audit.reply(content, proactive=True)
        return content

    def rewrite_text(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        messages = [
            {"role": "system", "content": prompts.REWRITE_PROMPT},
            {"role": "user", "content": text},
        ]
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
            )
            self._meter_response(resp)
            content = (resp.choices[0].message.content or "").strip()
        except Exception:
            return ""
        return _strip_think_leak(content)

    def transform_clipboard(self, kind: str, text: str) -> str:
        """剪贴板炼金：按 kind（翻译/润色/解释…）改写选中文本。无状态单发，超 4000 字截断够用了。"""
        text = (text or "").strip()
        if not text:
            return ""
        messages = [
            {"role": "system", "content": prompts.CLIP_ALCHEMY_SYSTEM},
            {"role": "user", "content": f"{prompts.clip_alchemy_instr(kind)}\n\n内容：\n{text[:4000]}"},
        ]
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
            )
            self._meter_response(resp)
            content = (resp.choices[0].message.content or "").strip()
        except Exception:
            return ""
        return _strip_think_leak(content)

    def explore_topic(self, topic: str) -> str:
        worker = Agent(self._settings, depth=self._depth + 1)
        try:
            return worker.run(prompts.explore_nudge(topic))
        except Exception:
            return ""
        finally:
            worker.close()

    def peek_screen(self, trigger: str = "") -> str:
        """偷瞄一眼屏幕主动搭话（卡住雷达触发时带上窗口名重点看报错）。没什么可说就回 NONE，过滤成空串别硬聊。"""
        from desktop_pet.eyes import capture
        from desktop_pet.settings import CAPTURE_WINDOW
        try:
            cap = capture.capture_screen(CAPTURE_WINDOW)
        except Exception:
            return ""
        if not cap.png_bytes:
            return ""
        prompt = prompts.PEEK_PROMPT
        if trigger.strip():
            prompt = f"（卡住雷达注意到前台窗口「{trigger.strip()[:80]}」可能有问题——重点看看是不是报错/卡住。）\n" + prompt
        content = [
            {"type": "text", "text": self._turn_context() + "\n\n" + prompt},
            {"type": "image_url", "image_url": {"url": capture.to_data_url(cap.png_bytes)}},
        ]
        messages = [self._system_message(), {"role": "user", "content": content}]
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
            )
            self._meter_response(resp)
            text = _strip_think_leak((resp.choices[0].message.content or "").strip())
        except Exception:
            return ""
        if not text or text.strip().upper().lstrip("[").startswith("NONE"):  # 容忍模型把 NONE 裹进 [neutral] 这类情绪标签里
            return ""
        audit.reply(text, proactive=True)
        return text

    def _set_screen_watch(self, arguments: dict) -> str:
        """开/关定时盯屏：给 focus 就开（默认 ~5 分钟一瞄），interval<=0 或不给 focus 就关。"""
        from desktop_pet.watcher import watcher
        focus = str(arguments.get("focus") or "").strip()
        interval = arguments.get("interval_minutes")
        try:
            mins = float(interval) if interval is not None else None
        except (TypeError, ValueError):
            mins = None
        stop = (mins is not None and mins <= 0)
        if not focus or stop:
            watcher.stop()
            return "(Stopped the periodic screen-watch. I'll only look again when you ask.)"
        if mins is None:
            mins = 5.0
        _en, foc, real_min = watcher.start(focus, mins)
        return (f"(Periodic screen-watch is ON: every ~{real_min:.0f} min I'll glance at your screen and report on "
                f"\"{foc}\". I'll start within a minute. Say 'stop watching' anytime to turn it off.)")

    def analyze_screen(self, focus: str) -> str:
        """定时盯屏的单次执行：截屏+按 focus 问模型。截不到图回 WATCH_FAIL，没情况回空串（别每次都打扰）。"""
        from desktop_pet.eyes import capture
        from desktop_pet.settings import CAPTURE_WINDOW
        from desktop_pet.watcher import WATCH_FAIL
        try:
            cap = capture.capture_screen(CAPTURE_WINDOW)
        except Exception:
            return WATCH_FAIL
        if not cap.png_bytes:
            return WATCH_FAIL
        content = [
            {"type": "text", "text": self._turn_context() + "\n\n" + prompts.watch_focus_prompt(focus)},
            {"type": "image_url", "image_url": {"url": capture.to_data_url(cap.png_bytes)}},
        ]
        messages = [self._system_message(), {"role": "user", "content": content}]
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
            )
            self._meter_response(resp)
            text = _strip_think_leak((resp.choices[0].message.content or "").strip())
        except Exception:
            return WATCH_FAIL
        stripped = re.sub(r"^\s*\[\w+\]\s*", "", text).strip()  # 剥掉开头的 [emotion] 标签再判 NONE，否则永远判不出"没情况"
        if not stripped or stripped.upper() == "NONE":
            return ""
        audit.reply(text, proactive=True)
        return text

    def reflect(self) -> None:
        """一轮聊完后台默默复盘一次，沉淀记忆/人格。非阻塞，且信号量限只跑一个——抢不到就这轮不反思，不排队。"""
        if len(self._messages) <= 2:
            return
        if not self._turn_substantive:
            return
        if not _REFLECT_SEMAPHORE.acquire(blocking=False):
            return
        try:
            snapshot = copy.deepcopy(self._messages)
            threading.Thread(
                target=self._reflect, args=(snapshot,), daemon=True, name="star-reflect"
            ).start()
        except Exception:
            _REFLECT_SEMAPHORE.release()

    def _reflect(self, snapshot: list[dict]) -> None:
        """后台线程体：让模型把这轮提炼成 JSON（经验/偏好/环境/日记/自我画像/该忘的），各取所需写进对应存储。
        每类都逐项做了类型校验——模型给的 JSON 字段可能缺、可能类型不对，挨个挡一下别让脏数据进库。"""
        try:
            reflect_msg = prompts.REFLECT_PROMPT + "\n\n[Your current self-portrait — evolve THIS gently, don't toss it]:\n" + (persona.get() or "(none yet — this is the first one you're forming)")
            conversation = snapshot + [{"role": "user", "content": reflect_msg}]
            try:
                resp = self._client().chat.completions.create(
                    model=self._settings.model, messages=conversation, timeout=_BACKGROUND_TIMEOUT
                )
                self._meter_response(resp)
                content = resp.choices[0].message.content or ""
            except Exception:
                return
            data = _parse_json(content)
            if not data:
                return
            for experience in (data.get("experiences") or [])[:5]:
                if isinstance(experience, str) and experience.strip():
                    store.remember(experience.strip())
            preferences = data.get("preferences")
            if isinstance(preferences, dict):
                for key, value in preferences.items():
                    if isinstance(key, str) and isinstance(value, (str, int, float)):
                        store.set_preference(key, str(value))
            env = data.get("env")
            if isinstance(env, dict):
                for key, value in env.items():
                    if isinstance(key, str) and isinstance(value, (str, int, float)):
                        store.note_env(key, str(value))
            episode = data.get("episode")
            if isinstance(episode, str) and episode.strip():
                journal.add(episode.strip())
            self_text = data.get("self")
            if isinstance(self_text, str) and self_text.strip():
                persona.update(self_text.strip())
            for stale in (data.get("forget") or [])[:5]:
                if isinstance(stale, str) and stale.strip():
                    store.forget(stale.strip())
        finally:
            _REFLECT_SEMAPHORE.release()

    def _append_images(self, images: list[str]) -> None:
        """把新截图作为一条 user 消息塞进历史——塞之前先清掉旧图：多张高清截图叠着既费 token 又容易拿过期画面误判。"""
        self._drop_old_images()
        content: list[dict] = [{"type": "text", "text": "(screenshot below)"}]
        for url in images:
            content.append({"type": "image_url", "image_url": {"url": url}})
        self._messages.append({"role": "user", "content": content})

    def _drop_old_images(self) -> None:
        """把历史里旧的图片消息退化成纯文本占位——但当轮用户自己发的那张图(turn_user_idx)留着，那是任务原料不能动。"""
        for idx, message in enumerate(self._messages):
            if idx == self._turn_user_idx:
                continue
            if message.get("role") == "user" and isinstance(message.get("content"), list):
                texts = [
                    part.get("text", "")
                    for part in message["content"]
                    if isinstance(part, dict) and part.get("type") == "text"
                ]
                joined = " ".join(t for t in texts if t).strip()
                message["content"] = joined or "[older image omitted]"

    def _compose_user_content(self, text: str, attachments: object, context: str = ""):
        """拼这条 user 消息：没附件就一段纯文本；有图就返回 OpenAI 的多模态 list；文件先读出文本拼进正文。"""
        prefix = (context + "\n\n") if context else ""
        if not isinstance(attachments, list) or not attachments:
            return (prefix + text) if text else prefix.rstrip()
        images = [
            a for a in attachments
            if isinstance(a, dict) and a.get("kind") == "image" and a.get("data_url")
        ]
        files = [
            a for a in attachments
            if isinstance(a, dict) and a.get("kind") == "file" and a.get("path")
        ]
        file_ctx = self._ingest_and_read(files)
        full_text = text
        if file_ctx:
            full_text = (text + "\n\n" if text else "") + file_ctx
        if not images:
            return prefix + (full_text or "(用户发来了附件)")
        content: list[dict] = [{"type": "text", "text": prefix + (full_text or "看看这张图。")}]
        for img in images:
            content.append({"type": "image_url", "image_url": {"url": img["data_url"]}})
        return content

    def _ingest_and_read(self, files: list) -> str:
        """附件文件双轨：一边后台异步全文入知识库（recall_docs 以后能召回），一边当场读前 6000 字直接喂进对话。
        读不出文本的（二进制/不支持的格式）只留个说明，靠知识库那条路兜着。"""
        if not files:
            return ""
        blocks: list[str] = []
        for f in files:
            path = f.get("path")
            name = f.get("name") or path
            if not path:
                continue
            try:
                threading.Thread(target=self._safe_ingest, args=(path,), daemon=True, name="mochi-ingest").start()
            except RuntimeError:
                pass
            text = read_file_text(path)
            if text and text.strip():
                body = text if len(text) <= _ATTACH_FILE_CHARS else text[:_ATTACH_FILE_CHARS] + "\n…（已截断，全文已存入知识库，可用 recall_docs 召回）"
                blocks.append(f"【附件文件：{name}】\n{body}")
            else:
                blocks.append(f"【附件文件：{name}】（无法直接读取文本，可能是二进制或不支持的格式；已尝试存入知识库）")
        return "\n\n".join(blocks)

    @staticmethod
    def _safe_ingest(path: str) -> None:
        try:
            docs.ingest(path)
        except Exception:
            pass

    @staticmethod
    def _as_dict(message) -> dict:
        """把流式拼回来的 assistant 消息转成能回灌历史的 dict——tool_calls 得照 OpenAI 的结构原样带上，下一轮才接得住工具结果。"""
        data: dict = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            data["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in message.tool_calls
            ]
        return data
