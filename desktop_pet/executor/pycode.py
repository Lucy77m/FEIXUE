# author: bdth
# email: 2074055628@qq.com
# 在独立 Python 子进程里持久运行 / 安装第三方库的代码执行器

from __future__ import annotations

import base64
import queue
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from desktop_pet.executor.safety import check_blocked

_EXEC_TIMEOUT = 60
_INSTALL_TIMEOUT = 300
_OUTPUT_CAP = 200_000
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _python_exe() -> str:
    """返回跑用户代码 / 装库用的 Python 解释器。"""
    if getattr(sys, "frozen", False):
        runtime = Path(sys.executable).parent / "pyruntime" / "python.exe"
        if runtime.exists():
            return str(runtime)
    return sys.executable

_DLL_FIX = (
    "import os, sys\n"
    "if hasattr(os, 'add_dll_directory'):\n"
    "    for _sp in [p for p in sys.path if p and p.endswith('site-packages')]:\n"
    "        for _sub in ('pywin32_system32', 'win32', 'win32/lib', 'pywin32'):\n"
    "            _d = os.path.join(_sp, _sub)\n"
    "            if os.path.isdir(_d):\n"
    "                try: os.add_dll_directory(_d)\n"
    "                except OSError: pass\n"
)

_BOOTSTRAP = r'''
import base64, io, sys, traceback
from contextlib import redirect_stdout
__DLLFIX__
_in = sys.stdin
sys.stdin = io.StringIO("")
_out = sys.__stdout__
_ns = {}
_START = "__START__"
_END = "__END__"
while True:
    _line = _in.readline()
    if not _line:
        break
    try:
        _code = base64.b64decode(_line.strip()).decode("utf-8")
    except Exception:
        continue
    _buf = io.StringIO()
    try:
        with redirect_stdout(_buf):
            exec(_code, _ns)
    except BaseException:
        _buf.write(traceback.format_exc())
    _text = _buf.getvalue()
    if len(_text) > __CAP__:
        _text = _text[:__CAP__] + "\n...[output too long, truncated]"
    _payload = base64.b64encode(_text.encode("utf-8")).decode("ascii")
    _out.write(_START + "\n" + _payload + "\n" + _END + "\n")
    _out.flush()
'''


class PythonRunner:

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._out: queue.Queue | None = None
        self._start = ""
        self._end = ""
        self._lock = threading.Lock()

    def run(self, code: str, timeout: float = _EXEC_TIMEOUT) -> str:
        blocked = check_blocked(code)
        if blocked is not None:
            return f"[blocked: {blocked}. This is an irreversible high-risk operation and was prevented.]"
        with self._lock:
            self._ensure()
            output = self._out
            encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
            try:
                self._proc.stdin.write(encoded + "\n")
                self._proc.stdin.flush()
            except (OSError, ValueError):
                self._restart()
                return "[Python subprocess error; reset — please retry]"
            return self._collect(output, timeout)

    def refresh_native_dlls(self) -> None:

        try:
            self.run(_DLL_FIX)
        except Exception:
            pass

    def _ensure(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self._start = f"<<S{uuid.uuid4().hex}>>"
        self._end = f"<<E{uuid.uuid4().hex}>>"
        self._out = queue.Queue()
        bootstrap = (
            _BOOTSTRAP.replace("__DLLFIX__", _DLL_FIX)
            .replace("__START__", self._start)
            .replace("__END__", self._end)
            .replace("__CAP__", str(_OUTPUT_CAP))
        )
        self._proc = subprocess.Popen(
            [_python_exe(), "-c", bootstrap],
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

    def _pump(self, proc: subprocess.Popen, output: queue.Queue) -> None:
        try:
            for line in proc.stdout:
                output.put(line)
        except (OSError, ValueError):
            pass
        finally:
            output.put(None)

    def _collect(self, output: queue.Queue, timeout: float) -> str:
        deadline = time.time() + timeout
        seen_start = False
        captured: list[str] = []
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                self._restart()
                return f"[code ran past {timeout:.0f}s without finishing; gave up and reset the Python session (namespace cleared).]"
            try:
                line = output.get(timeout=remaining)
            except queue.Empty:
                self._restart()
                return f"[code ran past {timeout:.0f}s without finishing; gave up and reset the Python session (namespace cleared).]"
            if line is None:
                self._restart()
                return "[Python subprocess exited unexpectedly (the code may have crashed or force-exited it); session reset.]"
            stripped = line.strip()
            if not seen_start:
                if stripped == self._start:
                    seen_start = True
                continue
            if stripped == self._end:
                try:
                    text = base64.b64decode("".join(captured)).decode("utf-8", "replace")
                except Exception:
                    return "[failed to decode output; this result was dropped.]"
                return text.strip() or "[no output]"
            captured.append(stripped)

    def _restart(self) -> None:
        if self._proc is not None:
            _kill_proc(self._proc)
        self._proc = None

    def close(self) -> None:
        proc = self._proc
        if proc is not None:
            _kill_proc(proc)


def _kill_proc(proc: subprocess.Popen) -> None:
    try:
        proc.kill()
    except Exception:
        pass
    for pipe in (proc.stdout, proc.stdin):
        try:
            if pipe is not None:
                pipe.close()
        except Exception:
            pass
    threading.Thread(target=_reap, args=(proc,), daemon=True).start()


def _reap(proc: subprocess.Popen) -> None:
    try:
        proc.wait(timeout=10)
    except Exception:
        pass


def new_runner() -> PythonRunner:
    return PythonRunner()


def install_package(name: str) -> str:
    try:
        proc = subprocess.run(
            [_python_exe(), "-m", "pip", "install", name],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=_INSTALL_TIMEOUT,
            creationflags=_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return f"[install timed out (>{_INSTALL_TIMEOUT}s): {name}]"
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip()[-1500:]
    head = f"Installed {name}" if proc.returncode == 0 else f"[install failed, exit {proc.returncode}]"
    return f"{head}\n{tail}".strip()
