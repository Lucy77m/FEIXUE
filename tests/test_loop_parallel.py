# author: bdth
# email: 2074055628@qq.com
# 验证 agent 强化：回合内并发只读工具、取证工具按需端出、卡死回灌提示
# 都用假 _complete / 假 dispatch 驱动真实主循环 不碰网络

from __future__ import annotations

import os
import tempfile
import threading
import time
import types

os.environ.setdefault("STAR_DATA_DIR", tempfile.mkdtemp(prefix="mochi_par_"))

from desktop_pet.agent import tools  # noqa: E402
from desktop_pet.agent.loop import Agent  # noqa: E402
from desktop_pet.settings import Settings  # noqa: E402


def _tool_call(cid: str, name: str, arguments: str):
    return types.SimpleNamespace(
        id=cid, type="function",
        function=types.SimpleNamespace(name=name, arguments=arguments),
    )


def _msg(content, tool_calls, finish_reason):
    return types.SimpleNamespace(
        content=content, tool_calls=tool_calls,
        finish_reason=finish_reason, usage=None,
    )


def _agent() -> Agent:
    ag = Agent(Settings(api_key="x", base_url="http://127.0.0.1:1"))
    ag.new_topic()  # 清掉可能从上次会话恢复的历史 各测试从干净对话起步
    return ag


def test_parallel_reads_run_concurrently_and_keep_order():
    """一回合三个 read_file 应并发跑（峰值≥2、总时长远小于串行），结果按原序回灌"""
    ag = _agent()
    try:
        calls = [
            _tool_call("c1", "read_file", '{"path": "a.txt"}'),
            _tool_call("c2", "read_file", '{"path": "b.txt"}'),
            _tool_call("c3", "read_file", '{"path": "c.txt"}'),
        ]
        steps = [
            _msg("", calls, "tool_calls"),          # 第一步：吐三个并发安全工具
            _msg("[happy]\n看完了", None, "stop"),   # 第二步：纯文本收尾
        ]
        seq = {"i": 0}

        def fake_complete(on_think, offer_tools=True):
            m = steps[seq["i"]]
            seq["i"] += 1
            return m
        ag._complete = fake_complete

        live = {"n": 0, "peak": 0}
        spans: list[tuple[float, float]] = []
        lock = threading.Lock()

        def fake_dispatch(name, arguments, *, shell_session=None, py_session=None):
            start = time.monotonic()
            with lock:
                live["n"] += 1
                live["peak"] = max(live["peak"], live["n"])
            time.sleep(0.4)
            with lock:
                live["n"] -= 1
            with lock:
                spans.append((start, time.monotonic()))
            return tools.ToolResult(f"content-of-{arguments['path']}")
        orig = tools.dispatch
        tools.dispatch = fake_dispatch
        try:
            reply = ag.run("读这三个文件")
        finally:
            tools.dispatch = orig

        assert reply.strip().endswith("看完了")
        # 并发证据：峰值≥2 是确定性证明(两个 dispatch 真同时在跑)
        # 只量 dispatch 阶段跨度 与 run() 里记忆召回等开销解耦——串行需 3×0.4=1.2s 并发≈0.4s
        assert live["peak"] >= 2, f"未并发 峰值仅 {live['peak']}"
        span = max(e for _, e in spans) - min(s for s, _ in spans)
        assert span < 0.8, f"dispatch 跨度 {span:.2f}s 像是串行"
        # 顺序：工具结果按 c1 c2 c3 原序回灌 不被完成顺序打乱
        tool_msgs = [m for m in ag._messages if m.get("role") == "tool"]
        got = [(m["tool_call_id"], m["content"]) for m in tool_msgs]
        assert got == [
            ("c1", "content-of-a.txt"),
            ("c2", "content-of-b.txt"),
            ("c3", "content-of-c.txt"),
        ], got
    finally:
        ag.close()


def test_repeated_failure_triggers_nudge():
    """同名同参连续失败到阈值 回灌一句换思路提示"""
    ag = _agent()
    try:
        bad = [_tool_call("c1", "read_file", '{"path": "ghost.txt"}')]
        # 连发 4 步同样的失败调用 第三次该触发 nudge 之后收尾
        steps = [
            _msg("", bad, "tool_calls"),
            _msg("", bad, "tool_calls"),
            _msg("", bad, "tool_calls"),
            _msg("[sad]\n算了", None, "stop"),
        ]
        seq = {"i": 0}

        def fake_complete(on_think, offer_tools=True):
            m = steps[min(seq["i"], len(steps) - 1)]
            seq["i"] += 1
            return m
        ag._complete = fake_complete

        def fake_dispatch(name, arguments, *, shell_session=None, py_session=None):
            return tools.ToolResult("[tool read_file failed: FileNotFoundError]")
        orig = tools.dispatch
        tools.dispatch = fake_dispatch
        try:
            ag.run("一直读这个不存在的文件")
        finally:
            tools.dispatch = orig

        nudges = [m for m in ag._messages
                  if m.get("role") == "user" and "dead end" in str(m.get("content", ""))]
        assert nudges, "连续失败未触发换思路提示"
    finally:
        ag.close()


def test_looks_failed_only_scans_first_line():
    """失败检测只看首行——分页读/后台轮询正文里的 failed/error 不算失败"""
    f = Agent._looks_failed
    # 真失败：标记在首行
    assert f("[tool read_file failed: FileNotFoundError]") is True
    assert f("[安全拦截：高危操作]") is True
    assert f("[tool click is missing required argument(s): x]") is True
    # 假失败：分页读成功 正文里恰好有 error:/failed 不该误判
    assert f("[chars 0–500 of 1200]\nlog line error: build failed here") is False
    # 假失败：后台轮询仍在跑 正文流出报错词
    assert f("[background shell #3: still running; 5s elapsed]\nERROR: 1 test failed") is False
    assert f("plain output mentioning failed") is False


def test_strip_order_puts_named_param_first():
    """非标参数 400：错误点名谁就先剥谁 不连坐剥掉其它有效参数"""
    base = lambda: [("extra_body", "_strip_extra_body"),
                    ("temperature", "_strip_temperature"),
                    ("stream_options", "_strip_stream_options"),
                    ("prompt_cache_key", "_strip_cache_key")]
    # 只嫌 prompt_cache_key → 它排第一个先剥 别的不动
    assert Agent._strip_order(base(), "unknown parameter: prompt_cache_key")[0][0] == "prompt_cache_key"
    # 点名 temperature → temperature 先剥
    assert Agent._strip_order(base(), "temperature not supported")[0][0] == "temperature"
    # 没点名任何参数 → 维持默认序(extra_body 先)
    assert Agent._strip_order(base(), "some opaque 400")[0][0] == "extra_body"


def test_stuck_sig_is_canonical_over_key_order():
    """键序/空白不同但语义相同的参数 应算同一签名"""
    c1 = _tool_call("a", "read_file", '{"path":"x","n":1}')
    c2 = _tool_call("b", "read_file", '{ "n": 1, "path": "x" }')
    assert Agent._stuck_sig(c1, {"path": "x", "n": 1}) == Agent._stuck_sig(c2, {"n": 1, "path": "x"})


def test_paginated_read_does_not_trigger_stuck_nudge():
    """重复读同一个大文件(分页成功、正文含 error:/failed)不该被误判成卡死"""
    ag = _agent()
    try:
        rd = [_tool_call("c1", "read_file", '{"path": "big.log"}')]
        steps = [_msg("", rd, "tool_calls")] * 3 + [_msg("[content]\n读完了", None, "stop")]
        seq = {"i": 0}

        def fake_complete(on_think, offer_tools=True):
            m = steps[min(seq["i"], len(steps) - 1)]
            seq["i"] += 1
            return m
        ag._complete = fake_complete

        def fake_dispatch(name, arguments, *, shell_session=None, py_session=None):
            return tools.ToolResult("[chars 0–500 of 99999]\nstack trace: error: it failed 无法打开")
        orig = tools.dispatch
        tools.dispatch = fake_dispatch
        try:
            ag.run("把这个大日志读几遍")
        finally:
            tools.dispatch = orig

        nudges = [m for m in ag._messages
                  if m.get("role") == "user" and "dead end" in str(m.get("content", ""))]
        assert not nudges, "成功的分页读被误判成卡死并发了提示"
    finally:
        ag.close()
