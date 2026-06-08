# author: bdth
# email: 2074055628@qq.com
# 工程纪律工具：看未提交的 git diff、跑项目测试。

from __future__ import annotations

import os
import subprocess
import sys

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_DIFF_CAP = 20_000
_TEST_CAP = 8_000
_DIFF_TIMEOUT = 30
_TEST_TIMEOUT = 300


def _repo_cwd(path: str) -> str:
    p = (path or ".").strip() or "."
    if os.path.isdir(p):
        return p
    parent = os.path.dirname(p)
    return parent or "."


def _run(cmd: list[str], cwd: str, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=cwd or None, capture_output=True, text=True, timeout=timeout,
        creationflags=_NO_WINDOW, encoding="utf-8", errors="replace",
    )


def _kill_tree(pid: int) -> None:
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, timeout=10, creationflags=_NO_WINDOW)
    except Exception:
        pass


def review_diff(path: str = ".", staged: bool = False) -> str:
    """看工作区未提交的 git diff（staged=True 看已暂存的）。"""
    cwd = _repo_cwd(path)
    p = (path or ".").strip() or "."
    try:
        chk = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd, 10)
    except FileNotFoundError:
        return "[git 没装或不在 PATH 里]"
    except Exception as exc:
        return f"[看 diff 失败: {type(exc).__name__}: {exc}]"
    if chk.returncode != 0:
        return f"[这不是 git 仓库: {p}]"
    args = ["git", "--no-pager", "diff"]
    if staged:
        args.append("--staged")
    args += ["--", "." if os.path.isdir(p) else os.path.basename(p)]
    try:
        r = _run(args, cwd, _DIFF_TIMEOUT)
    except subprocess.TimeoutExpired:
        return "[git diff 超时]"
    out = (r.stdout or "").strip()
    if not out:
        st = _run(["git", "--no-pager", "status", "--porcelain", "-b"], cwd, 10).stdout.strip()
        tail = f"\n{st}" if st else ""
        return ("(没有未暂存的改动)" if staged else "(工作区没有未提交的改动)") + tail
    if len(out) > _DIFF_CAP:
        out = out[:_DIFF_CAP] + f"\n…[diff 太长，截断 {len(out) - _DIFF_CAP} 字符；给 path 限定某文件再看]"
    return out


def run_tests(command: str = "", path: str = ".") -> str:
    """跑项目测试并返回结果摘要（不给 command 就自动探测）。"""
    cwd = _repo_cwd(path)
    cmd = (command or "").strip()
    if not cmd:
        if any(os.path.exists(os.path.join(cwd, f)) for f in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini")):
            cmd = "python -m pytest -q"
        elif os.path.exists(os.path.join(cwd, "package.json")):
            cmd = "npm test"
        else:
            return "[没探测到测试配置(pyproject/pytest.ini/package.json)——用 command 参数给我测试命令]"
    try:
        proc = subprocess.Popen(
            cmd, cwd=cwd or None, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            creationflags=_NO_WINDOW, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        return f"[测试命令跑不起来(命令不存在?): {cmd}]"
    except Exception as exc:
        return f"[跑测试失败: {type(exc).__name__}: {exc}]"
    try:
        out, _ = proc.communicate(timeout=_TEST_TIMEOUT)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        _kill_tree(proc.pid)
        try:
            proc.communicate(timeout=5)
        except Exception:
            pass
        return f"[测试超过 {_TEST_TIMEOUT}s 没跑完——已杀掉测试进程树。可能卡住，或套件太大，给 path 缩小范围只跑相关的]"
    out = (out or "").strip()
    verdict = "✓ 测试通过" if rc == 0 else f"✗ 测试失败(exit {rc})"
    if not out:
        return f"{verdict}（命令 {cmd!r} 无输出）"
    if len(out) > _TEST_CAP:
        out = f"…[前面截断 {len(out) - _TEST_CAP} 字符]\n" + out[-_TEST_CAP:]
    return f"{verdict}（命令 {cmd!r}）\n{out}"
