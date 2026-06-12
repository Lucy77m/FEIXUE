# author: bdth
# email: 2074055628@qq.com
# 子代理mixin 派活 workflow编排 后台任务计数排队

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from desktop_pet.agent import prompts
from desktop_pet.agent.loopdefs import _MAX_PARALLEL_SUBAGENTS, _MAX_SUBAGENT_DEPTH, _MAX_WORKFLOW_TASKS
from desktop_pet.agent.textops import _parse_json_value


_MAX_BG_TASKS = 3
_BG_TASK_SEMAPHORE = threading.Semaphore(_MAX_BG_TASKS)
_BG_ACTIVE = 0
_BG_ACTIVE_LOCK = threading.Lock()


class SubagentsMixin:
    """把活分出去的那套"""

    def _run_subagent(self, task: str, step: Callable[[str], None] | None, result_schema: str | None = None) -> str:
        """派临时子代理干一件子事 跑完即弃"""
        from desktop_pet.agent.loop import Agent
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
        """校验子代理结果json 不合法重试一次"""
        from desktop_pet.agent.loop import Agent
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
        """跑一组子任务 pipeline串行fanout并发"""
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
                prev = self._run_subagent(stage, step, result_schema if i == len(clean) else None)  # schema只压在最后一段
            return prev
        out = [""] * len(clean)
        with ThreadPoolExecutor(max_workers=min(_MAX_PARALLEL_SUBAGENTS, len(clean))) as pool:
            futures = {pool.submit(self._run_subagent, t, None, result_schema): idx for idx, t in enumerate(clean)}
            for future in as_completed(futures):
                out[futures[future]] = future.result()
        return "\n\n".join(f"## 子任务 {i + 1}：{clean[i][:48]}\n{out[i]}" for i in range(len(clean)))

    def run_background(self, task: str) -> str:
        return self._start_background_task(task)

    def _start_background_task(self, task: str) -> str:
        """任务丢后台线程跑 干完notify回贴"""
        from desktop_pet.agent.loop import Agent
        if self._depth >= _MAX_SUBAGENT_DEPTH:
            return "(Can't start a background task from here.)"
        task = (task or "").strip()
        if not task:
            return "(No task given — didn't start one.)"
        if self._notify is None:
            return "(Background tasks aren't available in this environment.)"
        notify, settings, depth = self._notify, self._settings, self._depth

        # 计数加1判断要不要提示已排队 并发上限靠信号量
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
