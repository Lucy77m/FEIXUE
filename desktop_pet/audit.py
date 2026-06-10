# author: bdth
# email: 2074055628@qq.com
# 审计日志:把用户消息、回复、工具调用按天写入 JSONL 文件

from __future__ import annotations

import json
import threading
from datetime import datetime

from desktop_pet.settings import DATA_DIR

_LOG_DIR = DATA_DIR / "logs"
_MAX_RESULT = 4000


def _truncate(value: object) -> str:
    """工具结果可能几十 KB（截图 base64、长网页），落盘前砍到 4000 字符——日志只为复盘，不留全文。"""
    text = value if isinstance(value, str) else str(value)
    if len(text) <= _MAX_RESULT:
        return text
    return text[:_MAX_RESULT] + f"…(+{len(text) - _MAX_RESULT} chars)"


class _Audit:
    """单例审计器 → 每条事件一行 JSON，按天分文件落到 logs/。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _write(self, event: str, fields: dict) -> None:
        record = {"ts": datetime.now().isoformat(timespec="seconds"), "event": event}
        record.update(fields)
        line = json.dumps(record, ensure_ascii=False, default=str)  # default=str 兜底：args 里混进 Path/datetime 也不至于抛
        # 主动回复跑在定时线程、用户交互在 UI 线程——同时写同一文件，整个写动作上锁串起来
        with self._lock:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            path = _LOG_DIR / f"audit-{datetime.now():%Y%m%d}.jsonl"  # 跨午夜会自然滚到新文件
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
