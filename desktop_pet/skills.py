# author: bdth
# email: 2074055628@qq.com
# 技能仓库 AI 自创代码落盘 json 注册表管理

from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path

from desktop_pet.settings import DATA_DIR, atomic_write_text

_DIR = DATA_DIR / "skills"
_REGISTRY = _DIR / "registry.json"
# 技能名必须是合法 python 标识符
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _read_registry() -> dict:
    """读注册表 坏了退回空表"""
    if not _REGISTRY.exists():
        return {}
    try:
        data = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


class SkillStore:
    """AI 自创代码仓库 每个技能一个 py 文件 元信息进注册表"""

    def __init__(self) -> None:
        # 并行子智能体共享这一个 skills 单例 没锁会迭代 registry 时被插键崩或两次写互覆盖
        self._lock = threading.RLock()
        self._registry: dict = _read_registry()

    def create(self, name: str, code: str, desc: str, params: str = "") -> str:
        """新建或覆盖技能"""
        if not _NAME_RE.match(name):
            return f"Invalid skill name (letters/digits/underscore only, not starting with a digit): {name}"
        # 落盘前先过一遍语法
        try:
            compile(code, f"<skill {name}>", "exec")
        except SyntaxError as exc:
            return (f"Skill NOT saved — the code has a syntax error: {exc}. "
                    "Fix it, and run it once via run_python to confirm it actually works, then save.")
        with self._lock:
            verb = "Updated" if name in self._registry else "Created"
            self._write_code(name, code)
            self._registry[name] = {
                "desc": desc,
                "params": params,
                "updated": datetime.now().isoformat(timespec="seconds"),
            }
            self._save_registry()
        return f"{verb} skill \"{name}\": {desc}"

    def edit(self, name: str, code: str) -> str:
        """只改已有技能的代码 不碰元信息"""
        try:
            compile(code, f"<skill {name}>", "exec")
        except SyntaxError as exc:
            return f"Not saved — syntax error: {exc}. Fix it and try again."
        with self._lock:
            if name not in self._registry:
                return f"No skill named \"{name}\"; create it first with create_skill."
            self._write_code(name, code)
            self._registry[name]["updated"] = datetime.now().isoformat(timespec="seconds")
            self._save_registry()
        return f"Updated the code of skill \"{name}\"."

    def code(self, name: str) -> str | None:
        """取技能源码 没有就回 None"""
        with self._lock:
            if name not in self._registry:
                return None
            path = self._path(name)
        return path.read_text(encoding="utf-8") if path.exists() else None

    def count(self) -> int:
        with self._lock:
            return len(self._registry)

    def listing(self) -> str:
        with self._lock:
            if not self._registry:
                return "(no skills yet)"
            return "\n".join(
                f"- {name}({meta.get('params', '')}): {meta.get('desc', '')}"
                for name, meta in self._registry.items()
            )

    def as_context(self) -> str:
        """拼给系统提示的技能清单"""
        with self._lock:
            if not self._registry:
                return ""
            lines = ["[Skills you already have (call directly with run_skill; don't rewrite them)]"]
            lines += [
                f"- {name}({meta.get('params', '')}): {meta.get('desc', '')}"
                for name, meta in self._registry.items()
            ]
        return "\n".join(lines)

    def _path(self, name: str) -> Path:
        return _DIR / f"{name}.py"

    def _write_code(self, name: str, code: str) -> None:
        atomic_write_text(self._path(name), code)

    def _save_registry(self) -> None:
        atomic_write_text(_REGISTRY, json.dumps(self._registry, ensure_ascii=False, indent=2))


skills = SkillStore()
