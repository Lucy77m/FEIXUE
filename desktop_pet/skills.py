# author: bdth
# email: 2074055628@qq.com
# 技能仓库:把 AI 自创的 Python 代码片段存到磁盘并用 JSON 注册表管理,供后续直接调用

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from desktop_pet.settings import DATA_DIR, atomic_write_text

_DIR = DATA_DIR / "skills"
_REGISTRY = _DIR / "registry.json"
# 技能名得是合法 Python 标识符 —— 它直接当文件名(name.py)，顺手挡掉 ../ 之类的路径注入。
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _read_registry() -> dict:
    """读注册表 —— 文件不在/JSON 损坏/被手改成非 dict 一律退回空表，启动不能因为这个崩。"""
    if not _REGISTRY.exists():
        return {}
    try:
        data = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


class SkillStore:
    """AI 自创代码的落盘仓库 —— 每个技能一个 name.py，元信息(desc/params/时间)进 registry.json。"""

    def __init__(self) -> None:
        self._registry: dict = _read_registry()

    def create(self, name: str, code: str, desc: str, params: str = "") -> str:
        """新建或覆盖一个技能 —— 名字非法或语法不过都拒绝落盘，宁可不存也不留坏代码。"""
        if not _NAME_RE.match(name):
            return f"Invalid skill name (letters/digits/underscore only, not starting with a digit): {name}"
        # 存之前先 compile 过一遍语法 —— 坏代码进了仓库以后 run_skill 才炸，太晚。
        try:
            compile(code, f"<skill {name}>", "exec")
        except SyntaxError as exc:
            return (f"Skill NOT saved — the code has a syntax error: {exc}. "
                    "Fix it, and run it once via run_python to confirm it actually works, then save.")
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
        """只改已有技能的代码，不碰 desc/params —— 想连描述一起改走 create。"""
        if name not in self._registry:
            return f"No skill named \"{name}\"; create it first with create_skill."
        try:
            compile(code, f"<skill {name}>", "exec")
        except SyntaxError as exc:
            return f"Not saved — syntax error: {exc}. Fix it and try again."
        self._write_code(name, code)
        self._registry[name]["updated"] = datetime.now().isoformat(timespec="seconds")
        self._save_registry()
        return f"Updated the code of skill \"{name}\"."

    def code(self, name: str) -> str | None:
        """取技能源码 —— 注册表登记了但 .py 被手删的情况也回 None，让调用方当不存在处理。"""
        if name not in self._registry:
            return None
        path = self._path(name)
        return path.read_text(encoding="utf-8") if path.exists() else None

    def count(self) -> int:
        return len(self._registry)

    def listing(self) -> str:
        if not self._registry:
            return "(no skills yet)"
        return "\n".join(
            f"- {name}({meta.get('params', '')}): {meta.get('desc', '')}"
            for name, meta in self._registry.items()
        )

    def as_context(self) -> str:
        """拼进系统提示的那段技能清单 —— 让模型知道哪些能直接 run_skill，别每次重写一遍。"""
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
