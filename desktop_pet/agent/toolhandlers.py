# 内置工具处理mixin 计划 弹图 演出 确认 高危命令和edit护栏

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from desktop_pet.agent.loopdefs import _GIF_TOOL, _is_performable, _perform_names
from desktop_pet.agent.progress import render_plan
from desktop_pet.agent.textops import _norm_plan_status
from desktop_pet.executor import safety, web


class ToolHandlersMixin:
    """特殊工具的就地处理和两道护栏"""

    def _update_plan(self, steps: list, emit_plan: Callable[[str], None]) -> str:
        """收计划清单全量覆盖 洗状态渲染到面板"""
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
        """桌宠旁弹图或gif"""
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
        """桌宠做动作 名字不在册列回可选项"""
        name = (name or "").strip()
        if not _is_performable(name):
            return f"(I don't have a \"{name}\" move. Options — {_perform_names()})"
        hook = self._on_perform
        if hook is None:
            return "(Can't do that move right now.)"
        hook(name)
        return f"OK, doing the \"{name}\" move now."

    def _confirm(self, action: str) -> str:
        """弹确认面板等用户点 批准置_risk_approval"""
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
        """危险命令扫描 返回拒绝文案或None放行"""
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
            self._risk_approval = False  # 放行只用一次 用完清掉
            return None
        if self._on_confirm is None:
            return (f"[安全拦截：这一步包含高危操作（{risk}），而当前环境（后台/子代理）没有确认按钮，"
                    "没有执行。需要的话改在前台对话里做，由用户确认后执行。]")
        if self._on_confirm(f"高危操作：{risk}\n{text[:200]}"):
            return None
        return f"[用户点了「不执行」——这个高危操作（{risk}）被拒绝了。不要再尝试，简短告知用户即可。]"

    @staticmethod
    def _file_key(path: str) -> str:
        """路径归一成_known_files的键"""
        try:
            return os.path.normcase(str(Path(path).expanduser().resolve()))
        except (OSError, ValueError):
            return os.path.normcase(str(Path(path).expanduser()))  # resolve失败退一步用没解析的

    def _guard_edit(self, name: str, arguments: dict) -> str | None:
        """edit前护栏 没读过或mtime变了打回重读"""
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
        """记下文件mtime给_guard_edit比对"""
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

    @staticmethod
    def _fetch_media(source: str) -> str | None:
        local = Path(source)
        if local.is_file():
            return str(local)
        if source.lower().startswith(("http://", "https://")):
            return web.download_to_temp(source)
        return None

    def _set_screen_watch(self, arguments: dict) -> str:
        """开关定时盯屏"""
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
