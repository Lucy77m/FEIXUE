# author: bdth
# email: 2074055628@qq.com
# 远程触发（文件收件箱）：轮询 DATA_DIR/inbox/ 下的 json 并执行，处理后移到 inbox/done/。

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path

from desktop_pet.settings import DATA_DIR

INBOX = DATA_DIR / "inbox"
_DONE = INBOX / "done"
_MAX_PER_POLL = 5
_SETTLE_S = 4.0


class RemoteInbox:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seen: set[tuple[str, int, int]] = set()

    def ensure_dir(self) -> None:
        try:
            INBOX.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    def poll(self) -> list[tuple[str, str]]:
        """读 inbox/*.json（除 done/ 外），每个文件一条触发并归档到 inbox/done/，返回 [(kind, content)]。"""
        out: list[tuple[str, str]] = []
        with self._lock:
            if not INBOX.exists():
                return out
            try:
                files = sorted(p for p in INBOX.glob("*.json") if p.is_file())
            except OSError:
                return out
            now_ts = time.time()
            for p in files[:_MAX_PER_POLL]:
                try:
                    st = p.stat()
                    if now_ts - st.st_mtime < _SETTLE_S:
                        continue
                except OSError:
                    continue
                fp = (p.name, int(st.st_mtime), st.st_size)
                if fp in self._seen:
                    continue
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError, ValueError):
                    if not self._archive(p, bad=True):
                        self._seen.add(fp)
                    continue
                if isinstance(data, dict):
                    task = str(data.get("task") or "").strip()
                    say = str(data.get("say") or "").strip()
                    if task:
                        out.append(("task", task))
                    elif say:
                        out.append(("say", say))
                if not self._archive(p):
                    self._seen.add(fp)
        return out

    def _archive(self, p: Path, bad: bool = False) -> bool:
        try:
            _DONE.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            p.rename(_DONE / f"{stamp}_{p.name}{'.bad' if bad else ''}")
            return True
        except OSError:
            try:
                p.unlink()
                return True
            except OSError:
                return False


remote_inbox = RemoteInbox()
