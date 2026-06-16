# author: bdth
# email: 2074055628@qq.com
# agent主循环 多步工具调用 周边职能拆在旁边几个mixin里

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import (
    APIConnectionError,
    APITimeoutError,
    BadRequestError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from desktop_pet import i18n, journal, persona
from desktop_pet.agent import prompts
from desktop_pet.agent import tools
from desktop_pet.agent.duties import DutiesMixin
from desktop_pet.agent.history import HistoryMixin
from desktop_pet.agent.loopdefs import (
    _BACKGROUND_TOOL,
    _CONFIRM_TOOL,
    _CONTROL_TOOLS,
    _COSMETIC_TOOLS,
    _FRESH_AFTER,
    _GIF_TOOL,
    _IMAGE_TOOL,
    _INPUT_TOOL_HINT,
    _MAX_EMPTY_RETRIES,
    _MAX_PARALLEL_SUBAGENTS,
    _MAX_PARALLEL_TOOLS,
    _MAX_RETRIES,
    _MAX_SUBAGENT_DEPTH,
    _PARALLEL_SAFE,
    _PERFORM_TOOL,
    _PLAN_TOOL,
    _REFLECT_MIN_CHARS,
    _REQUEST_TIMEOUT,
    _RETRY_BASE_S,
    _RETRY_CAP_S,
    _RETRY_MAX,
    _RUN_CANCELLED,
    _SHELL_TOOLS,
    _SPAWN_TOOL,
    _STUCK_LIMIT,
    _SUBAGENT_BUDGET,
    _WATCH_TOOL,
    _WEB_TOOLS,
    _WORKFLOW_TOOL,
)
from desktop_pet.agent.progress import describe_step
from desktop_pet.agent.prompts import SUBAGENT_PROMPT, SYSTEM_PROMPT, language_hint
from desktop_pet.agent.streaming import StreamMessage, reassemble
from desktop_pet.agent.subagents import SubagentsMixin
from desktop_pet.agent.textops import _cap_tool_result, _parse_json, _strip_think_leak, _strip_toolcall_leak
from desktop_pet.agent.toolhandlers import ToolHandlersMixin
from desktop_pet.audit import audit
from desktop_pet.docs import docs
from desktop_pet.emotion.state import emotion
from desktop_pet.executor import pycode, shell
from desktop_pet.mcp_hub import mcp_hub
from desktop_pet.memory.store import store
from desktop_pet.settings import AUTONOMY_BUDGETS, Settings, build_http_client
from desktop_pet.skills import skills
from desktop_pet.usage import meter as usage_meter

# 这些是值得等一等再试的瞬时错误 限流 5xx 网络抖动 超时
# 不含 400 参数错 401 鉴权 404 模型名错 那些重试多少次都一样 该快速失败
_TRANSIENT_ERRORS = (RateLimitError, InternalServerError, APITimeoutError, APIConnectionError)


def _retry_after_seconds(exc: Exception) -> float | None:
    """从限流响应头里抠 Retry-After 服务端让等多久就等多久 抠不到返回None"""
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None)
    if not headers:
        return None
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


class Agent(HistoryMixin, ToolHandlersMixin, SubagentsMixin, DutiesMixin):
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
        self._closing = False  # close()/cancel 置位:在途反思/压缩 daemon 据此别再造新 OpenAI client 漏掉 httpx 池
        self._retired_clients: list = []  # 配置变了换下来的旧 client——可能仍有线程在流式用着 不当场关 退出时统一收
        self._shell = shell.new_session()
        self._python = pycode.new_runner()
        self._compressed = ""
        self._compress_lock = threading.Lock()
        self._pending_compress: list[str] = []  # 待摘要的被裁段 后台串行消化
        self._compress_busy = False
        self._compress_gen = 0  # 换话题/遗忘会自增 在途摘要发现代差变了就丢弃不回写
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
        self._turn_emotion_peak = 0.5  # 本轮情绪强度峰值 喂给记忆显著性
        self._stuck: dict[str, int] = {}  # 本轮同名同参的连续失败计数 撞顶提醒换思路
        self._stuck_warned: set[str] = set()  # 已就某签名提醒过 一轮只提一次
        self._hit_step_limit = False
        self._last_active = 0.0
        self._turn_user_idx = -1
        self._strip_extra_body = False  # 网关不认非标参数 400后记下不再发
        self._strip_temperature = False  # 新claude等模型不收temperature 同样剥
        self._strip_stream_options = False
        self._strip_cache_key = False  # 网关不认prompt_cache_key就剥
        if depth == 0:
            self._try_restore_session()  # 只主代理恢复上次会话

    def _build_tools(self) -> list[dict]:
        """按深度和权限开关裁工具单"""
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
        """清空全部记忆和当前会话"""
        for wipe in (store.wipe, journal.clear, persona.clear, docs.forget):
            try:
                wipe()
            except Exception as exc:
                # 别再静默吞——某步清不掉(如库损坏)要留痕 否则像重置没生效
                audit.system("forget_all step failed", step=getattr(wipe, "__name__", str(wipe)), error=repr(exc))
        self._reset_compressed()
        self._known_files.clear()
        self._clear_session_file()
        self._messages = [self._system_message()]
        self._plan = []
        self._turn_user_idx = -1

    def new_topic(self) -> None:
        """只清当前对话 长期记忆保留"""
        store.bump_epoch()  # 让上一段对话在途的反思作废:它总结的是被丢弃的话题 不该再写进长期记忆/persona/journal
        self._reset_compressed()
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
        self._close_retired_clients()

    @staticmethod
    def was_cancelled(reply: str) -> bool:
        return reply == _RUN_CANCELLED

    @property
    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    def _seal_pending_tool_calls(self, note: str) -> None:
        """给没结果的tool_call补占位结果"""
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
        self._closing = True  # 终态:之后晚到的反思/压缩 daemon 调 _client() 会被拒 不再造没人关的 client
        if self._depth == 0:
            self._save_session()
        self._shell.close()
        self._python.close()
        self._close_retired_clients()
        with self._client_lock:
            client = self._oa_client
            self._oa_client = None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    def _close_retired_clients(self) -> None:
        """收掉历次配置变更留下的旧 client 的 httpx 连接池"""
        with self._client_lock:
            retired = self._retired_clients
            self._retired_clients = []
        for c in retired:
            try:
                c.close()
            except Exception:
                pass

    def _system_message(self) -> dict:
        """拼系统提示 只放基本不变的内容"""
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
        """每轮现算的状态注记"""
        parts = [emotion.tone_hint(), prompts.time_hint()]
        mood_reason = emotion.mood_note()  # 心情明显时附上"为什么" 让它说得出因
        if mood_reason:
            parts.append(mood_reason)
        from desktop_pet import somatic
        body = somatic.context()
        if body:
            parts.append(body)
        memory_context = store.as_context(query)
        if memory_context:
            parts.append(memory_context)
        return "[当前状态注记——以这条最新的为准，历史消息里的同类注记已过期]\n" + "\n\n".join(parts)

    def run(
        self,
        user_message: str,
        attachments: object = None,
        on_step: Callable[[str], None] | None = None,
        on_think: Callable[[str], None] | None = None,
        on_plan: Callable[[str], None] | None = None,
        on_media: Callable[[str, str, str], None] | None = None,
        on_perform: Callable[[str], bool] | None = None,
        on_control: Callable[[bool, str], None] | None = None,
    ) -> str:
        """对外入口 跑一轮对话回最终文本"""
        try:
            return self._run_impl(
                user_message, attachments, on_step=on_step, on_think=on_think,
                on_plan=on_plan, on_media=on_media, on_perform=on_perform, on_control=on_control,
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
        on_control: Callable[[bool, str], None] | None = None,
    ) -> str:
        """核心多步循环 执行工具调用直到纯文本回复或撞步数顶"""
        def step(message: str) -> None:
            if on_step is not None:
                on_step(message)

        def control(active: bool, label: str) -> None:
            # 借用和归还鼠标键盘时通知UI弹收浮层
            if on_control is not None:
                on_control(active, label)

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
        self._stuck = {}
        self._stuck_warned = set()
        self._on_perform = on_perform
        if self._owns_cancel:
            self._cancel.clear()
        now = time.monotonic()
        # 隔25分钟以上自动翻篇
        if (self._depth == 0 and self._last_active
                and now - self._last_active > _FRESH_AFTER and len(self._messages) > 1):
            self._reset_compressed()
            self._known_files.clear()
            self._messages = [self._system_message()]
        self._last_active = now
        # 抓这次交流的情绪强度 此刻夸还是骂已经鉴别结算完 记忆显著性用它放大
        _val, _aro, _rap = emotion.snapshot()
        self._turn_emotion_peak = max(_aro, abs(_val))
        self._prepare()
        history_mark = len(self._messages)  # 出错回滚点
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
                message.content = _strip_toolcall_leak(_strip_think_leak(message.content))
            self._messages.append(self._as_dict(message))
            if not message.tool_calls:
                reply = message.content or ""
                if not reply.strip():
                    # 空回复催一两次再放弃
                    empties += 1
                    if empties <= _MAX_EMPTY_RETRIES and steps < hard_cap:
                        self._messages.append({"role": "user", "content": prompts.EMPTY_REPLY_NUDGE})
                        steps += 1
                        continue
                    del self._messages[history_mark:]
                    self._turn_substantive = False
                    audit.reply("[empty reply]")
                    return prompts.EMPTY_REPLY_FALLBACK
                # 判断这轮是否实质 决定要不要reflect
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
            truncated = message.finish_reason == "length"  # 区分被截断还是坏json
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

            # 多个子代理并发跑 单个走下面普通分支
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

            # 一回合里多个只读工具并发跑 互不依赖 多工具回合提速明显
            # 只取 _PARALLEL_SAFE——run_shell/run_python 共享单会话不能并发 留给串行
            par = [(c, a) for c, a in parsed
                   if c.id not in results and a is not None and c.function.name in _PARALLEL_SAFE]
            if len(par) > 1:
                for c, a in par:
                    step(describe_step(c.function.name, a))
                with ThreadPoolExecutor(max_workers=min(_MAX_PARALLEL_TOOLS, len(par))) as pool:
                    futures = {
                        pool.submit(tools.dispatch, c.function.name, a,
                                    shell_session=self._shell, py_session=self._python): c.id
                        for c, a in par
                    }
                    for future in as_completed(futures):
                        results[futures[future]] = future.result()
                for c, a in par:
                    self._note_file(c.function.name, a)  # read_file 的 mtime 记账 串行做避免并发写 dict

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
                    # dispatch前过高危确认和edit护栏两道闸
                    denial = (self._guard_risky(call.function.name, arguments)
                              or self._guard_edit(call.function.name, arguments))
                    if denial is not None:
                        results[call.id] = tools.ToolResult(denial)
                    else:
                        hint = _INPUT_TOOL_HINT.get(call.function.name)
                        if hint is not None:
                            control(True, hint)  # 要动你的鼠标键盘了 弹浮层
                        try:
                            results[call.id] = tools.dispatch(
                                call.function.name, arguments,
                                shell_session=self._shell, py_session=self._python,
                            )
                        finally:
                            if hint is not None:
                                control(False, "")  # 这一下操作完了 收浮层 去抖留显交给UI
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
            # 同名同参连续失败 撞顶回灌一句"别原地打转换思路" 一轮每签名只提一次
            # 每步每签名只计一次——一条响应里重复同样调用不该一步就把计数顶上去
            failed_sigs: set[str] = set()
            ok_sigs: set[str] = set()
            for call, arguments in parsed:
                sig = self._stuck_sig(call, arguments)
                (failed_sigs if self._looks_failed(results[call.id].text) else ok_sigs).add(sig)
            for sig in ok_sigs - failed_sigs:
                self._stuck[sig] = 0  # 本步成功的 streak 清零
            stuck_hits: list[str] = []
            for sig in failed_sigs:
                self._stuck[sig] = self._stuck.get(sig, 0) + 1
                if self._stuck[sig] >= _STUCK_LIMIT and sig not in self._stuck_warned:
                    self._stuck_warned.add(sig)
                    stuck_hits.append(sig.split("\x00", 1)[0])
            if stuck_hits:
                self._messages.append({
                    "role": "user",
                    "content": prompts.repeat_stuck_nudge("、".join(dict.fromkeys(stuck_hits))),
                })
            if self._cancel.is_set():
                self._seal_cancelled()
                return _RUN_CANCELLED
            steps += 1
            # 每隔checkpoint步插一句自检
            if steps < hard_cap and steps % checkpoint == 0:
                self._messages.append({"role": "user", "content": prompts.step_checkpoint_nudge(steps)})
        self._hit_step_limit = True
        self._turn_substantive = True
        if self._cancel.is_set():
            self._seal_cancelled()
            return _RUN_CANCELLED
        step(i18n.thinking_label())
        # 撞步数顶 不给工具求一次纯文本收尾
        self._messages.append({"role": "user", "content": prompts.STEP_LIMIT_NUDGE})
        try:
            message = self._complete(think, offer_tools=False)
            self._messages.append(self._as_dict(message))
            reply = _strip_toolcall_leak(_strip_think_leak(message.content or ""))
        except Exception as exc:
            audit.reply(f"[step-limit 收尾调用失败: {type(exc).__name__}: {exc}]")
            reply = ""
        if not reply:
            reply = "[confused]\n这个任务我试了好多步还是没搞定，先停一下——可能太复杂、或者得用管理员权限再来。"
        audit.reply(reply)
        return reply

    def _budget(self) -> tuple[int, int]:
        """返回检查点间隔和步数上限"""
        if self._depth > 0:
            return _SUBAGENT_BUDGET
        return AUTONOMY_BUDGETS.get(self._settings.autonomy, AUTONOMY_BUDGETS["正常"])

    def _client(self) -> OpenAI:
        """懒建缓存openai客户端 配置变了重建"""
        creds = (self._settings.api_key, self._settings.base_url, self._settings.proxy)
        with self._client_lock:
            if self._closing and self._oa_client is None:
                # 已关停:别再为晚到的反思/压缩 daemon 造一个没人会去关的 client(httpx 池泄漏)
                raise RuntimeError("agent is closing")
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
                self._strip_temperature = False
                self._strip_cache_key = False
                if old is not None:
                    # 别在这关:可能正有 worker 线程在用 old 做流式补全 当场 close 会掐断它那一轮
                    # 先留着 等 close()/cancel 收尾时统一关(配置变更很少 顶多攒下寥寥几个)
                    self._retired_clients.append(old)
            return self._oa_client

    def _model_name(self) -> str:
        """子代理优先用小模型 没配退回主模型"""
        if self._depth > 0:
            sub = (getattr(self._settings, "subagent_model", "") or "").strip()
            if sub:
                return sub
        return self._settings.model

    def _complete(self, on_think: Callable[[str], None], offer_tools: bool = True) -> StreamMessage:
        """发一次流式补全 非标参数400就剥掉重试"""
        params: dict = {
            "model": self._model_name(),
            "messages": self._messages,
            "stream": True,
        }
        if not self._strip_temperature:
            params["temperature"] = self._settings.temperature
        if offer_tools:
            params["tools"] = self._tools
        if self._settings.max_tokens > 0:
            params["max_tokens"] = self._settings.max_tokens
        if self._wants_thinking_param():
            params["extra_body"] = {"enable_thinking": self._settings.enable_thinking}
        if not self._strip_stream_options:
            params["stream_options"] = {"include_usage": True}
        if not self._strip_cache_key:
            # 稳定key帮服务端把同前缀的多步请求路由到同一缓存 提命中率省钱
            # 系统前缀整轮稳定、历史只追加 本就缓存友好 这是再添一把routing提示
            params["prompt_cache_key"] = f"mochi-d{self._depth}"
        try:
            stream = self._create_stream(params)
        except BadRequestError as exc:
            candidates = [
                ("extra_body", "_strip_extra_body"),
                ("temperature", "_strip_temperature"),
                ("stream_options", "_strip_stream_options"),
                ("prompt_cache_key", "_strip_cache_key"),
            ]
            # 错误消息一个非标参数都没点名 -> 这个 400 跟它们无关(上下文超长/内容策略/模型名错等)
            # 别盲剥四个参数把整会话永久降级(降采样、丢用量统计、丢缓存路由) 直接抛出真错误让上层看见
            if not any(key in str(exc).lower() for key, _flag in candidates):
                raise
            # 非标参数400就逐个剥掉重试 错误消息点名的先剥 剥光还炸才抛
            order = self._strip_order(candidates, str(exc))
            last = exc
            stream = None
            for key, flag in order:
                if key not in params:
                    continue
                params.pop(key)
                setattr(self, flag, True)
                try:
                    stream = self._create_stream(params)
                    break
                except BadRequestError as retry_exc:
                    last = retry_exc
            if stream is None:
                raise last
        message = reassemble(stream, on_think, should_cancel=self._cancel.is_set)
        if message.usage:
            usage_meter.add(message.usage["input"], message.usage["output"], message.usage.get("cached", 0))
        return message

    def _create_stream(self, params: dict):
        """发起补全 瞬时错误指数退避重试 400原样抛给上层剥参数 退避期间可被取消打断"""
        delay = _RETRY_BASE_S
        attempt = 0
        while True:
            try:
                return self._client().chat.completions.create(**params)
            except BadRequestError:
                raise  # 参数问题 退避没用 交给上层剥
            except _TRANSIENT_ERRORS as exc:
                if attempt >= _RETRY_MAX or self._cancel.is_set():
                    raise
                wait = _retry_after_seconds(exc)
                wait = min(wait if wait is not None else delay, _RETRY_CAP_S)
                # 用cancel.wait睡 取消能立刻把它叫醒 不傻等
                if self._cancel.wait(wait):
                    raise
                delay = min(delay * 2, _RETRY_CAP_S)
                attempt += 1

    def _meter_response(self, resp) -> None:
        """记非流式调用用量"""
        try:
            u = resp.usage
            if u is None:
                return
            cached = 0
            details = getattr(u, "prompt_tokens_details", None)  # 缓存命中token在这
            if details is not None:
                cached = int(getattr(details, "cached_tokens", 0) or 0)
            usage_meter.add(int(u.prompt_tokens or 0), int(u.completion_tokens or 0), cached)
        except Exception:
            pass

    def _wants_thinking_param(self) -> bool:
        # 官方openai和剥过标记的不发enable_thinking
        if self._strip_extra_body:
            return False
        return "api.openai.com" not in (self._settings.base_url or "").lower()

    @staticmethod
    def _looks_failed(text: str) -> bool:
        """工具结果是不是一条失败回执 用于卡死检测。只看首行——失败回执的标记词都在
        首行方括号里；而分页读文件 '[chars..of..]'、后台轮询 '[..still running..]' 这些
        成功结果的标记词出现在正文里，扫全文会把成功的读/轮询误判成失败"""
        t = (text or "").lstrip()
        if not t.startswith("["):  # 失败回执统一裹方括号 普通输出极少以[开头
            return False
        head = t.split("\n", 1)[0].lower()
        markers = ("failed", "missing required", "不是合法 json", "没有执行",
                   "安全拦截", "被拒绝", "couldn't", "can't", "error:", "无法", "打不开", "截断")
        return any(m in head for m in markers)

    @staticmethod
    def _strip_order(order: list, exc_text: str) -> list:
        """非标参数 400 时的剥除顺序：错误消息点名了哪个就把它挪到最前先剥，
        否则按默认序。否则会连坐——网关只嫌 prompt_cache_key，却把 temperature/
        stream_options 一并永久剥掉（剥过的标记整会话不复原），白白降采样、丢用量统计"""
        low = (exc_text or "").lower()
        for i, (key, _flag) in enumerate(order):
            if key in low:
                order.insert(0, order.pop(i))
                break
        return order

    @staticmethod
    def _stuck_sig(call, arguments) -> str:
        """卡死签名：名字+规范化参数。用解析后的 dict 排序序列化 让键序/空白不同但
        语义相同的调用算同一个 否则模型每次微调序列化就绕过了检测"""
        canon = (json.dumps(arguments, sort_keys=True, ensure_ascii=False)
                 if arguments is not None else (call.function.arguments or ""))
        return call.function.name + "\x00" + canon

    @staticmethod
    def _as_dict(message) -> dict:
        """assistant消息转成历史dict"""
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
