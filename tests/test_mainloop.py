# agent主循环集成测试 子进程跑完整场景 数据目录隔离不碰真库
# 单元测试全绿但真机卡死的事故发生过一次 这个测试就是那次的疫苗

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCENARIO = Path(__file__).parent / "_mainloop_scenario.py"


def test_mainloop_roundtrip():
    """发一条消息走完整链路 线程亲和 回复上屏 心跳不断"""
    proc = subprocess.run(
        [sys.executable, str(_SCENARIO)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60,
    )
    detail = f"\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert proc.returncode == 0, f"集成场景退出码 {proc.returncode}{detail}"
    assert "mainloop integration OK" in proc.stdout, detail
