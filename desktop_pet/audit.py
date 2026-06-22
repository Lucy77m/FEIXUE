# 审计日志 用户消息 回复 工具调用按天写jsonl

from __future__ import annotations

import json
import threading
from datetime import datetime

from desktop_pet.settings import DATA_DIR

_LOG_DIR = DATA_DIR / "logs"
_MAX_RESULT = 4000


def _truncate(value: object) -> str:
    """截断过长的工具结果"""
    text = value if isinstance(value, str) else str(value)
    if len(text) <= _MAX_RESULT:
        return text
    return text[:_MAX_RESULT] + f"…(+{len(text) - _MAX_RESULT} chars)"


class _Audit:
    """单例审计器 每事件一行json 按天分文件"""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _write(self, event: str, fields: dict) -> None:
        record = {"ts": datetime.now().isoformat(timespec="seconds"), "event": event}
        record.update(fields)
        line = json.dumps(record, ensure_ascii=False, default=str)  # 兜底非json类型
        with self._lock:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            path = _LOG_DIR / f"audit-{datetime.now():%Y%m%d}.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def user(self, text: str) -> None:
        self._write("user", {"text": text})

    def reply(self, text: str, proactive: bool = False) -> None:
        self._write("reply", {"text": text, "proactive": proactive})

    def tool(self, name: str, args: dict, result: str) -> None:
        self._write("tool", {"name": name, "args": args, "result": _truncate(result)})

    def system(self, message: str, **fields: object) -> None:
        self._write("system", {"message": message, **fields})


audit = _Audit()
