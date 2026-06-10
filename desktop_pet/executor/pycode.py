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
_OUTPUT_CAP = 8_000
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _python_exe() -> str:
    """返回跑用户代码 / 装库用的 Python 解释器。打包后优先用随包带的 pyruntime，没有再退到 sys.executable。"""
    if getattr(sys, "frozen", False):
        runtime = Path(sys.executable).parent / "pyruntime" / "python.exe"
        if runtime.exists():
            return str(runtime)
    return sys.executable

# 打包/隔离环境下 pywin32 的原生 DLL 加载不到——手动把那几个目录塞进 add_dll_directory，否则 import win32api 直接炸。
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

# 子进程跑的常驻 REPL：从 stdin 一行行收 base64 代码 → exec 进同一个 _ns（命名空间跨次保留）→ 用 START/END 框住 base64 结果写回。
# 走 base64 是因为代码/输出里换行随便有，纯文本分帧会被用户的 print 撞乱。
_BOOTSTRAP = r'''
import base64, io, sys, traceback
from contextlib import redirect_stderr, redirect_stdout
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
        # stderr 也要进缓冲：库的 warning/logging 默认走 stderr，否则这些输出会整段消失
        with redirect_stdout(_buf), redirect_stderr(_buf):
            exec(_code, _ns)
    except BaseException:
        _buf.write(traceback.format_exc())
    _text = _buf.getvalue()
    if len(_text) > __CAP__:
        _omit = len(_text) - 7000
        _text = (_text[:4500] + "\n...[output too long; omitted " + str(_omit)
                 + " chars in the middle -- head and tail (where errors usually are) kept]...\n"
                 + _text[-2500:])
    _payload = base64.b64encode(_text.encode("utf-8")).decode("ascii")
    _out.write(_START + "\n" + _payload + "\n" + _END + "\n")
    _out.flush()
'''


class PythonRunner:
    """常驻一个子进程跑代码——一次开起来，后续 run 复用同一命名空间，变量/import 都留着。run 串行加锁。"""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._out: queue.Queue | None = None
        self._start = ""
        self._end = ""
        self._lock = threading.Lock()

    def run(self, code: str, timeout: float = _EXEC_TIMEOUT) -> str:
        """跑一段代码拿文本输出（含 traceback）。串行——同一时刻只有一段在跑。"""
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
        """子进程里重跑一遍 DLL 修复——刚装完 pywin32 这种带原生库的包后调一下，省得重启会话。"""
        try:
            self.run(_DLL_FIX)
        except Exception:
            pass

    def _ensure(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        # 分帧标记每次会话随机生成——固定串会被用户代码 print 出同样内容时撞到，随机 uuid 基本不可能重。
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
        """后台线程死读 stdout 灌进队列——这样 _collect 那边才能带 timeout 取，不会被阻塞读卡死。"""
        try:
            for line in proc.stdout:
                output.put(line)
        except (OSError, ValueError):
            pass
        finally:
            output.put(None)  # 哨兵：管道关了通知 _collect 子进程没了

    def _collect(self, output: queue.Queue, timeout: float) -> str:
        """从队列攒到 END 标记为止拼本次输出，超时就放弃。"""
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
                # START 之前的行全丢——子进程启动期的杂音（DLL fix 的 warning 之类）不该混进结果。
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
    """杀进程 + 关管道，然后扔后台线程去 wait 收尸——主线程不能在这等，否则调用方（含 UI 线程）会被卡住。"""
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
    """pip 装一个包，回头一段尾巴日志。装完带原生库的包记得 refresh_native_dlls 让常驻会话能 import。"""
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
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip()[-1500:]  # 只留尾巴——pip 的真正报错基本都在最后几行
    head = f"Installed {name}" if proc.returncode == 0 else f"[install failed, exit {proc.returncode}]"
    return f"{head}\n{tail}".strip()
