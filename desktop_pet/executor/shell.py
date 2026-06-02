# author: bdth
# email: 2074055628@qq.com
# 执行 shell 命令的后端：维护常驻 PowerShell 会话并支持 cmd 单次执行

from __future__ import annotations

import base64
import locale as _locale
import queue
import subprocess
import threading
import time
import uuid

from desktop_pet.executor.safety import check_blocked

_TIMEOUT = 60
# 打包成无控制台 GUI 后，子进程(powershell/cmd)启动会被 Windows 分配一个可见黑窗——这个 flag 阻止它
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_ENCODING_SETUP = (
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
    "[Console]::InputEncoding=[Text.Encoding]::UTF8;"
    "$OutputEncoding=[Text.Encoding]::UTF8"
)


class _PowerShell:

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._out: queue.Queue | None = None
        self._lock = threading.Lock()

    def run(self, command: str, timeout: float = _TIMEOUT) -> str:
        with self._lock:
            self._ensure()
            output = self._out
            start, end = f"<<S{uuid.uuid4().hex}>>", f"<<E{uuid.uuid4().hex}>>"
            encoded = base64.b64encode(command.encode("utf-8")).decode("ascii")
            framed = (
                f"Write-Output '{start}'; "
                f"try {{ Invoke-Expression "
                f"([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded}'))) }} "
                f"catch {{ Write-Output $_.Exception.Message }}; "
                f"Write-Output \"{end}$LASTEXITCODE\"\n"
            )
            try:
                self._proc.stdin.write(framed)
                self._proc.stdin.flush()
            except (OSError, ValueError):
                self._restart()
                return "[PowerShell session error; reset — please retry]"
            return self._collect(output, start, end, timeout)

    def _ensure(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self._out = queue.Queue()
        self._proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NoLogo"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=_NO_WINDOW,
        )
        threading.Thread(target=self._pump, args=(self._proc, self._out), daemon=True).start()
        try:
            self._proc.stdin.write(_ENCODING_SETUP + "\n")
            self._proc.stdin.flush()
        except (OSError, ValueError):
            pass

    def _pump(self, proc: subprocess.Popen, output: queue.Queue) -> None:
        try:
            for line in proc.stdout:
                output.put(line)
        except (OSError, ValueError):
            pass
        finally:
            output.put(None)

    def _collect(self, output: queue.Queue, start: str, end: str, timeout: float) -> str:
        deadline = time.time() + timeout
        seen_start = False
        captured: list[str] = []
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                self._restart()
                return f"[ran past {timeout:.0f}s without finishing; gave up and reset the session]"
            try:
                line = output.get(timeout=remaining)
            except queue.Empty:
                self._restart()
                return f"[ran past {timeout:.0f}s without finishing; gave up and reset the session]"
            if line is None:
                self._restart()
                return "[PowerShell process exited unexpectedly; session reset]"
            if not seen_start:
                if line.strip() == start:
                    seen_start = True
                continue
            if line.strip().startswith(end):
                code = line.strip()[len(end):].strip() or "0"
                body = "".join(captured).strip()
                return f"[exit {code}]\n{body}".strip()
            captured.append(line)

    def _restart(self) -> None:
        if self._proc is not None:
            _kill_proc(self._proc)
        self._proc = None

    def close(self) -> None:
        proc = self._proc
        if proc is not None:
            _kill_proc(proc)


def _kill_proc(proc: subprocess.Popen) -> None:
    # 必须非阻塞：cancel() 会在 UI 主线程同步调用它，任何 proc.wait() 都会卡住界面。
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass
    try:
        if proc.stdout is not None:
            proc.stdout.close()
    except Exception:  # noqa: BLE001
        pass
    threading.Thread(target=_reap, args=(proc,), daemon=True).start()  # 后台回收，免僵尸又不阻塞


def _reap(proc: subprocess.Popen) -> None:
    try:
        proc.wait(timeout=10)
    except Exception:  # noqa: BLE001
        pass


_session = _PowerShell()


def new_session() -> _PowerShell:
    return _PowerShell()


def run_shell(command: str, shell: str = "powershell", session: _PowerShell | None = None) -> str:
    blocked = check_blocked(command)
    if blocked is not None:
        return f"[blocked: {blocked}. This is an irreversible high-risk operation and was prevented; if truly needed, have the user do it manually.]"
    if shell == "cmd":
        try:
            proc = subprocess.run(
                ["cmd", "/c", command],
                capture_output=True,
                text=True,
                encoding=_locale.getpreferredencoding(False),
                errors="replace",
                timeout=_TIMEOUT,
                creationflags=_NO_WINDOW,
            )
        except subprocess.TimeoutExpired:
            return f"[timeout after {_TIMEOUT}s]"
        output = (proc.stdout or "") + (proc.stderr or "")
        return f"[exit {proc.returncode}]\n{output}".strip()
    return (session or _session).run(command)
