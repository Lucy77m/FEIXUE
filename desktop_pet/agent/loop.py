# author: bdth
# email: 2074055628@qq.com
# Agent 主循环：驱动 LLM 多步工具调用、子代理/后台任务、计划与反思

from __future__ import annotations

import copy
import json
import re
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from openai import OpenAI

from desktop_pet.agent import tools
from desktop_pet.agent.progress import PLAN_ICON, describe_step, render_plan
from desktop_pet.agent import prompts
from desktop_pet.agent.prompts import SUBAGENT_PROMPT, SYSTEM_PROMPT, language_hint
from desktop_pet.agent.streaming import StreamMessage, reassemble
from desktop_pet.audit import audit
from desktop_pet.docs import docs, read_file_text
from desktop_pet.emotion.state import emotion
from desktop_pet.executor import pycode, shell, web
from desktop_pet import i18n, journal, persona
from desktop_pet.mcp_hub import mcp_hub
from desktop_pet.memory.store import store
from desktop_pet.settings import Settings, build_http_client
from desktop_pet.skills import skills

_MAX_STEPS = 16
_MAX_STEPS_CEILING = 64
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
    if len(text) <= _MAX_TOOL_RESULT_CHARS:
        return text
    return text[:_MAX_TOOL_RESULT_CHARS] + f"\n…[truncated {len(text) - _MAX_TOOL_RESULT_CHARS} chars]"


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think_leak(text: str) -> str:
    if not text or "think>" not in text:
        return text
    text = _THINK_BLOCK_RE.sub("", text)
    return text.replace("<think>", "").replace("</think>", "").strip()


def _parse_json(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


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
        self._shell = shell.new_session()
        self._python = pycode.new_runner()
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

    def _build_tools(self) -> list[dict]:
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
        for wipe in (store.wipe, journal.clear, persona.clear, docs.forget):
            try:
                wipe()
            except Exception:
                pass
        self._messages = [self._system_message()]
        self._plan = []

    def cancel(self) -> None:
        self._cancel.set()
        self._shell.close()
        self._python.close()
        client = self._oa_client
        if client is not None:
            self._oa_client = None
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
        self._shell.close()
        self._python.close()

    def _system_message(self, query: str | None = None) -> dict:
        if self._depth > 0:
            return {"role": "system", "content": SUBAGENT_PROMPT}
        parts = [SYSTEM_PROMPT]
        parts += [emotion.tone_hint(), prompts.time_hint()]
        memory_context = store.as_context(query)
        if memory_context:
            parts.append(memory_context)
        journal_context = journal.as_context()
        if journal_context:
            parts.append(journal_context)
        persona_context = persona.as_context()
        if persona_context:
            parts.append(persona_context)
        skills_context = skills.as_context()
        if skills_context:
            parts.append(skills_context)
        lang = language_hint(self._settings.language)
        if lang:
            parts.append(lang)
        return {"role": "system", "content": "\n\n".join(parts)}

    def _prepare(self, query: str | None = None) -> None:
        self._trim_history()
        self._messages[0] = self._system_message(query)
        self._tools = self._build_tools()

    def _trim_history(self) -> None:
        n = len(self._messages)
        if n <= 2:
            return
        used = 0
        start = n
        for i in range(n - 1, 0, -1):
            used += _estimate_tokens(self._messages[i])
            if used > _HISTORY_TOKEN_BUDGET and i < n - 1:
                break
            start = i
        while start < n - 1 and self._messages[start].get("role") == "tool":
            start += 1
        if start > 1:
            del self._messages[1:start]

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
        self._on_perform = on_perform
        if self._owns_cancel:
            self._cancel.clear()
        self._prepare(user_message)
        history_mark = len(self._messages)
        n_att = len(attachments) if isinstance(attachments, list) else 0
        audit.user(user_message + (f"  [附件×{n_att}]" if n_att else ""))
        self._messages.append({"role": "user", "content": self._compose_user_content(user_message, attachments)})
        configured_steps = self._settings.max_steps if self._settings.max_steps > 0 else _MAX_STEPS
        max_steps = min(configured_steps, _MAX_STEPS_CEILING)
        for _ in range(max_steps):
            if self._cancel.is_set():
                del self._messages[history_mark:]
                return _RUN_CANCELLED
            step(i18n.thinking_label())
            message = self._complete(think)
            if message.content:
                message.content = _strip_think_leak(message.content)
            self._messages.append(self._as_dict(message))
            if not message.tool_calls:
                reply = message.content or ""
                self._turn_substantive = (
                    self._turn_used_tools or (len(user_message) + len(reply)) >= _REFLECT_MIN_CHARS
                )
                audit.reply(reply)
                return reply

            if message.content:
                step(message.content.strip())

            images: list[str] = []
            parsed = [(c, _parse_json(c.function.arguments or "{}") or {}) for c in message.tool_calls]
            if any(c.function.name not in _COSMETIC_TOOLS for c, _ in parsed):
                self._turn_used_tools = True
            results: dict[str, tools.ToolResult] = {}

            spawns = [(c, a) for c, a in parsed if c.function.name == _SPAWN_TOOL]
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
                    results[call.id] = tools.dispatch(
                        call.function.name, arguments,
                        shell_session=self._shell, py_session=self._python,
                    )

            for call, arguments in parsed:
                result = results[call.id]
                audit.tool(call.function.name, arguments, result.text)
                self._messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": _cap_tool_result(result.text)}
                )
                if result.image_data_url:
                    images.append(result.image_data_url)
            if images:
                self._append_images(images)
            if self._cancel.is_set():
                del self._messages[history_mark:]
                return _RUN_CANCELLED
        self._hit_step_limit = True
        self._turn_substantive = True
        if self._cancel.is_set():
            del self._messages[history_mark:]
            return _RUN_CANCELLED
        step(i18n.thinking_label())
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

    def _client(self) -> OpenAI:
        creds = (self._settings.api_key, self._settings.base_url, self._settings.proxy)
        if self._oa_client is None or self._oa_creds != creds:
            self._oa_client = OpenAI(
                api_key=self._settings.api_key or "missing",
                base_url=self._settings.base_url,
                timeout=_REQUEST_TIMEOUT,
                max_retries=_MAX_RETRIES,
                http_client=build_http_client(self._settings.proxy),
            )
            self._oa_creds = creds
        return self._oa_client

    def _complete(self, on_think: Callable[[str], None], offer_tools: bool = True) -> StreamMessage:
        params: dict = {
            "model": self._settings.model,
            "messages": self._messages,
            "stream": True,
            "temperature": self._settings.temperature,
        }
        if offer_tools:
            params["tools"] = self._tools
        if self._settings.max_tokens > 0:
            params["max_tokens"] = self._settings.max_tokens
        params["extra_body"] = {"enable_thinking": self._settings.enable_thinking}
        stream = self._client().chat.completions.create(**params)
        return reassemble(stream, on_think, should_cancel=self._cancel.is_set)

    def _update_plan(self, steps: list, emit_plan: Callable[[str], None]) -> str:
        cleaned: list[dict] = []
        for raw in steps or []:
            if isinstance(raw, dict) and str(raw.get("text", "")).strip():
                status = raw.get("status")
                cleaned.append(
                    {"text": str(raw["text"]).strip(), "status": status if status in PLAN_ICON else "todo"}
                )
        self._plan = cleaned
        if cleaned:
            emit_plan(render_plan(cleaned))
        done = sum(1 for step in cleaned if step["status"] == "done")
        return f"Plan updated: {done}/{len(cleaned)} done."

    def _show_media(self, tool_name: str, arguments: dict, emit_media: Callable[[str, str, str], None]) -> str:
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
        name = (name or "").strip()
        if not _is_performable(name):
            return f"(I don't have a \"{name}\" move. Options — {_perform_names()})"
        hook = self._on_perform
        if hook is None:
            return "(Can't do that move right now.)"
        hook(name)
        return f"OK, doing the \"{name}\" move now."

    def _confirm(self, action: str) -> str:
        action = (action or "").strip()
        if not action:
            return "(No action described — nothing to confirm.)"
        if self._on_confirm is None:
            return "(No confirm UI available here; treat as NOT approved — skip it, or have the user do it in the foreground.)"
        approved = self._on_confirm(action)
        return ("User tapped 执行 — approved, go ahead." if approved
                else "User tapped 不执行 — rejected; do NOT do it, just acknowledge briefly.")

    @staticmethod
    def _fetch_media(source: str) -> str | None:
        local = Path(source)
        if local.is_file():
            return str(local)
        if source.lower().startswith(("http://", "https://")):
            return web.download_to_temp(source)
        return None

    def _run_subagent(self, task: str, step: Callable[[str], None] | None, result_schema: str | None = None) -> str:
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
            return worker.run(task, on_step=step)
        except Exception as exc:
            return f"(Sub-agent couldn't finish: {exc})"
        finally:
            worker.close()

    def _run_workflow(self, mode: str, tasks: list, result_schema: str | None, step: Callable[[str], None] | None) -> str:
        """确定性编排：fanout=并行扇出 N 个子任务；pipeline=顺序把上阶段输出注入下阶段。"""
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
                prev = self._run_subagent(stage, step, result_schema if i == len(clean) else None)
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
        # 定时任务亲自做(完整工具执行)，跑完回滚历史
        snapshot = list(self._messages)
        try:
            return self.run(
                prompts.timed_task_nudge(task), on_step=on_step, on_think=on_think,
                on_plan=on_plan, on_media=on_media, on_perform=on_perform,
            )
        finally:
            self._messages = snapshot

    def _start_background_task(self, task: str) -> str:
        if self._depth >= _MAX_SUBAGENT_DEPTH:
            return "(Can't start a background task from here.)"
        task = (task or "").strip()
        if not task:
            return "(No task given — didn't start one.)"
        if self._notify is None:
            return "(Background tasks aren't available in this environment.)"
        notify, settings, depth = self._notify, self._settings, self._depth

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
        self._prepare()
        messages = copy.deepcopy(self._messages) + [
            {"role": "user", "content": prompts.reminder_nudge(what)}
        ]
        try:
            content = (
                self._client().chat.completions.create(
                    model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
                )
                .choices[0]
                .message.content
                or ""
            ).strip()
        except Exception:
            content = ""
        content = _strip_think_leak(content)
        if not content:
            content = f"[neutral]\n{what}"
        audit.reply(content, proactive=True)
        return content

    def speak_spontaneously(self, mode: str, context: str = "") -> str:
        self._prepare()
        nudge = prompts.spontaneous_nudge(mode)
        if context.strip():
            nudge = context.strip() + "\n" + nudge
        messages = copy.deepcopy(self._messages) + [
            {"role": "user", "content": nudge}
        ]
        try:
            content = (
                self._client().chat.completions.create(
                    model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
                )
                .choices[0]
                .message.content
                or ""
            ).strip()
        except Exception:
            return ""
        content = _strip_think_leak(content)
        if content:
            audit.reply(content, proactive=True)
        return content

    def rewrite_text(self, text: str) -> str:
        """把选中文字独立改写一遍。"""
        text = (text or "").strip()
        if not text:
            return ""
        messages = [
            {"role": "system", "content": prompts.REWRITE_PROMPT},
            {"role": "user", "content": text},
        ]
        try:
            content = (
                self._client().chat.completions.create(
                    model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
                )
                .choices[0]
                .message.content
                or ""
            ).strip()
        except Exception:
            return ""
        return _strip_think_leak(content)

    def transform_clipboard(self, kind: str, text: str) -> str:
        """对用户刚复制的报错/外文/代码顺手给一两句。"""
        text = (text or "").strip()
        if not text:
            return ""
        messages = [
            {"role": "system", "content": prompts.CLIP_ALCHEMY_SYSTEM},
            {"role": "user", "content": f"{prompts.clip_alchemy_instr(kind)}\n\n内容：\n{text[:4000]}"},
        ]
        try:
            content = (
                self._client().chat.completions.create(
                    model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
                )
                .choices[0]
                .message.content
                or ""
            ).strip()
        except Exception:
            return ""
        return _strip_think_leak(content)

    def explore_topic(self, topic: str) -> str:
        """空闲时用临时子代理查一件小事，用自己口吻总结一句。"""
        worker = Agent(self._settings, depth=self._depth + 1)
        try:
            return worker.run(prompts.explore_nudge(topic))
        except Exception:
            return ""
        finally:
            worker.close()

    def peek_screen(self, trigger: str = "") -> str:
        """看一眼当前活动窗口截图，判断用户是不是卡住了。"""
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
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": capture.to_data_url(cap.png_bytes)}},
        ]
        messages = [self._system_message(), {"role": "user", "content": content}]
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
            )
            text = _strip_think_leak((resp.choices[0].message.content or "").strip())
        except Exception:
            return ""
        if not text or text.strip().upper().lstrip("[").startswith("NONE"):
            return ""
        audit.reply(text, proactive=True)
        return text

    def _set_screen_watch(self, arguments: dict) -> str:
        """开/关定时看屏分析。"""
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
        """定时看屏：截当前活动窗口，按用户指定的关注点分析并用自己的口吻报一句。"""
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
            {"type": "text", "text": prompts.watch_focus_prompt(focus)},
            {"type": "image_url", "image_url": {"url": capture.to_data_url(cap.png_bytes)}},
        ]
        messages = [self._system_message(), {"role": "user", "content": content}]
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
            )
            text = _strip_think_leak((resp.choices[0].message.content or "").strip())
        except Exception:
            return WATCH_FAIL
        stripped = re.sub(r"^\s*\[\w+\]\s*", "", text).strip()
        if not stripped or stripped.upper() == "NONE":
            return ""
        audit.reply(text, proactive=True)
        return text

    def reflect(self) -> None:
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
        try:
            reflect_msg = prompts.REFLECT_PROMPT + "\n\n[Your current self-portrait — evolve THIS gently, don't toss it]:\n" + (persona.get() or "(none yet — this is the first one you're forming)")
            conversation = snapshot + [{"role": "user", "content": reflect_msg}]
            try:
                content = (
                    self._client().chat.completions.create(
                        model=self._settings.model, messages=conversation, timeout=_BACKGROUND_TIMEOUT
                    )
                    .choices[0]
                    .message.content
                    or ""
                )
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
        self._drop_old_images()
        content: list[dict] = [{"type": "text", "text": "(screenshot below)"}]
        for url in images:
            content.append({"type": "image_url", "image_url": {"url": url}})
        self._messages.append({"role": "user", "content": content})

    def _drop_old_images(self) -> None:
        for message in self._messages:
            if message.get("role") == "user" and isinstance(message.get("content"), list):
                texts = [
                    part.get("text", "")
                    for part in message["content"]
                    if isinstance(part, dict) and part.get("type") == "text"
                ]
                joined = " ".join(t for t in texts if t).strip()
                message["content"] = joined or "[older image omitted]"

    def _compose_user_content(self, text: str, attachments: object):
        """把用户附件并进这一轮消息：图片走多模态 image_url，文件读正文内联并后台入知识库。"""
        if not isinstance(attachments, list) or not attachments:
            return text
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
            return full_text or "(用户发来了附件)"
        content: list[dict] = [{"type": "text", "text": full_text or "看看这张图。"}]
        for img in images:
            content.append({"type": "image_url", "image_url": {"url": img["data_url"]}})
        return content

    def _ingest_and_read(self, files: list) -> str:
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
