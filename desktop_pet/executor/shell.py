# author: bdth
# email: 2074055628@qq.com
# shell 命令后端 常驻 powershell 会话和 cmd 单次执行

from __future__ import annotations

import base64
import locale as _locale
import queue
import subprocess
import threading
import time
import uuid
from collections import deque

from desktop_pet.executor.safety import check_blocked

_TIMEOUT = 600
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_IDLE_LIMIT = 120
# 输出截断 两头保留中间丢
_CAP_HEAD = 4_500
_CAP_TAIL = 2_500

_ENCODING_SETUP = (
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
    "[Console]::InputEncoding=[Text.Encoding]::UTF8;"
    "$OutputEncoding=[Text.Encoding]::UTF8"
)

_NONINTERACTIVE_ENV = (
    "$env:CI='1';"
    "$env:npm_config_yes='true';"
    "$env:GIT_TERMINAL_PROMPT='0';"
    "$env:PIP_NO_INPUT='1'"
)


class _PowerShell:
    """常驻 powershell 会话 cwd 和环境变量跨命令保留"""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._out: queue.Queue | None = None
        self._lock = threading.Lock()

    def run(self, command: str, timeout: float = _TIMEOUT) -> str:
        """跑一条命令 随机哨兵夹出这条的输出"""
        with self._lock:
            self._ensure()
            output = self._out
            start, end = f"<<S{uuid.uuid4().hex}>>", f"<<E{uuid.uuid4().hex}>>"
            # base64 转一手防 powershell 二次解释
            encoded = base64.b64encode(command.encode("utf-8")).decode("ascii")
            framed = (
                f"Write-Output '{start}'; "
                # 先清零防上一条退出码粘住
                f"$global:LASTEXITCODE=0; "
                f"try {{ Invoke-Expression "
                f"([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded}'))) }} "
                # 抛异常手动置 1
                f"catch {{ Write-Output $_.Exception.Message; $global:LASTEXITCODE=1 }}; "
                f"Write-Output \"{end}$LASTEXITCODE`t$($PWD.Path)\"\n"
            )
            try:
                self._proc.stdin.write(framed)
                self._proc.stdin.flush()
            except (OSError, ValueError):
                # 进程死了就重置 让上层重试
                self._restart()
                return "[PowerShell session error; reset — please retry]"
            return self._collect(output, start, end, timeout)

    def _ensure(self) -> None:
        """没活进程就拉一个新的"""
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
            self._proc.stdin.write(_ENCODING_SETUP + ";" + _NONINTERACTIVE_ENV + "\n")
            self._proc.stdin.flush()
        except (OSError, ValueError):
            pass

    def _pump(self, proc: subprocess.Popen, output: queue.Queue) -> None:
        """后台线程读 stdout 进队列"""
        try:
            for line in proc.stdout:
                output.put(line)
        except (OSError, ValueError):
            pass
        finally:
            output.put(None)  # 哨兵 None 通知 _collect 进程没了

    def _collect(self, output: queue.Queue, start: str, end: str, timeout: float) -> str:
        """从队列攒输出到 end 哨兵 总超时加静默超时"""
        deadline = time.time() + timeout
        idle_deadline = time.time() + _IDLE_LIMIT
        seen_start = False
        head: list[str] = []
        head_len = 0
        tail: deque[str] = deque()
        tail_len = 0
        dropped = 0
        while True:
            now = time.time()
            remaining = min(deadline, idle_deadline) - now
            if remaining <= 0:
                # 区分静默超时和总超时
                stalled = now >= idle_deadline and now < deadline
                self._restart()
                if stalled:
                    return (
                        f"[no output for {_IDLE_LIMIT:.0f}s, so it was killed (with any child processes). "
                        f"Two common causes: (1) it's waiting for interactive input this shell can't "
                        f"provide — re-run non-interactively (add -y / --yes / --default, or pipe the "
                        f"answer in); (2) it's a long-running server like `npm run dev` / `vite` — don't "
                        f"run those blocking; start them in the BACKGROUND (Start-Process / Start-Job) "
                        f"and then probe the port.]"
                    )
                return f"[ran past {timeout:.0f}s without finishing; gave up and reset the session]"
            try:
                line = output.get(timeout=remaining)
            except queue.Empty:
                continue
            if line is None:
                self._restart()
                return "[PowerShell process exited unexpectedly; session reset]"
            idle_deadline = time.time() + _IDLE_LIMIT  # 有新行就续命静默计时
            if not seen_start:
                # start 之前的残留回显丢掉
                if line.strip() == start:
                    seen_start = True
                continue
            if line.strip().startswith(end):
                # end 行尾带退出码和当前路径
                rest = line.strip()[len(end):]
                code_part, _, cwd = rest.partition("\t")
                code = code_part.strip() or "0"
                head_text = "".join(head)
                tail_text = "".join(tail)
                # 按真实字符数再卡一刀
                if len(head_text) > _CAP_HEAD:
                    dropped += len(head_text) - _CAP_HEAD
                    head_text = head_text[:_CAP_HEAD]
                if len(tail_text) > _CAP_TAIL:
                    dropped += len(tail_text) - _CAP_TAIL
                    tail_text = tail_text[-_CAP_TAIL:]
                body = head_text
                if dropped:
                    body += f"\n…[输出过长，中间省略约 {dropped} 字符；开头和结尾都保留了]…\n"
                body += tail_text
                result = f"[exit {code}]\n{body.strip()}".strip()
                if cwd.strip():
                    result += f"\n[cwd: {cwd.strip()}]"
                return result
            # 先填满 head 之后全进 tail 滑窗
            if head_len < _CAP_HEAD:
                head.append(line)
                head_len += len(line)
            else:
                tail.append(line)
                tail_len += len(line)
                while len(tail) > 1 and tail_len > _CAP_TAIL:  # 至少留 1 行
                    evicted = tail.popleft()
                    tail_len -= len(evicted)
                    dropped += len(evicted)

    def _restart(self) -> None:
        if self._proc is not None:
            _kill_proc(self._proc)
        self._proc = None

    def close(self) -> None:
        proc = self._proc
        if proc is not None:
            _kill_proc(proc)


def _kill_proc(proc: subprocess.Popen) -> None:
    """连子进程树一起杀"""
    pid = proc.pid
    if pid is not None:
        try:
            # 先 taskkill 杀进程树再补一刀 kill 双保险
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, timeout=10, creationflags=_NO_WINDOW,
            )
        except Exception:
            pass
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
    # 后台线程异步收尸
    threading.Thread(target=_reap, args=(proc,), daemon=True).start()


def _reap(proc: subprocess.Popen) -> None:
    try:
        proc.wait(timeout=10)  # 收尸防僵尸
    except Exception:
        pass


_session = _PowerShell()


def new_session() -> _PowerShell:
    return _PowerShell()


def run_shell(command: str, shell: str = "powershell", session: _PowerShell | None = None) -> str:
    """对外入口 先过黑名单 cmd 单次进程 powershell 走常驻会话"""
    blocked = check_blocked(command)
    if blocked is not None:
        return f"[blocked: {blocked}. This is an irreversible high-risk operation and was prevented; if truly needed, have the user do it manually.]"
    if shell == "cmd":
        # cmd 一次一进程 编码用系统本地代码页
        proc = subprocess.Popen(
            ["cmd", "/c", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding=_locale.getpreferredencoding(False),
            errors="replace",
            creationflags=_NO_WINDOW,
        )
        try:
            output, _ = proc.communicate(timeout=_TIMEOUT)
        except subprocess.TimeoutExpired:
            _kill_proc(proc)
            return f"[ran past {_TIMEOUT:.0f}s without finishing; killed it]"
        return f"[exit {proc.returncode}]\n{output or ''}".strip()
    stripped = command.rstrip()
    # 拦 bash 习惯的尾随 & 放行 &&
    if stripped.endswith("&") and not stripped.endswith("&&"):
        return ("[a trailing `&` to background a command is bash syntax that this PowerShell "
                "rejects — drop the `&`, or background it with Start-Job { ... } / Start-Process.]")
    return (session or _session).run(command)
