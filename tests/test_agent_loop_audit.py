# 板块③ Agent循环与工具 重审隐患回归 取消时丢半截tool_calls 过期定时提醒拒收 后台任务排队不算已跑

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

import pytest

from desktop_pet.agent.streaming import reassemble


# ---------- 取消中途断流 别把攒到一半的 tool_calls 拼进消息 ----------

class _Fn:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments


class _TC:
    def __init__(self, index, cid=None, name=None, args=None):
        self.index = index
        self.id = cid
        self.function = _Fn(name, args)


class _Delta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.reasoning_content = None
        self.model_extra = None


class _Choice:
    def __init__(self, delta, finish_reason=None):
        self.delta = delta
        self.finish_reason = finish_reason


class _Chunk:
    def __init__(self, choices):
        self.choices = choices
        self.usage = None


def test_reassemble_drops_partial_toolcalls_on_cancel():
    # 第一片给半截 arguments 随后取消 不该把半截当成 tool_call 拼出来
    chunks = [
        _Chunk([_Choice(_Delta(content="正在", tool_calls=[
            _TC(0, cid="call_1", name="run_shell", args='{"command": "git pu')]))]),
        _Chunk([_Choice(_Delta(tool_calls=[_TC(0, args='ll origin"}')]))]),
    ]
    state = {"hit": False}

    def should_cancel():
        # 第一片放行 第二片之前返回 True 触发取消断流
        if not state["hit"]:
            state["hit"] = True
            return False
        return True

    msg = reassemble(iter(chunks), lambda s: None, should_cancel=should_cancel)
    assert msg.tool_calls is None, "取消时该丢掉半截 tool_calls 只回文本"
    assert msg.content == "正在"


def test_reassemble_keeps_toolcalls_without_cancel():
    # 不取消时 完整 tool_calls 该正常拼出
    chunks = [
        _Chunk([_Choice(_Delta(tool_calls=[_TC(0, cid="c1", name="run_shell", args='{"command":')]))]),
        _Chunk([_Choice(_Delta(tool_calls=[_TC(0, args=' "ls"}')]), finish_reason="tool_calls")]),
    ]
    msg = reassemble(iter(chunks), lambda s: None, should_cancel=lambda: False)
    assert msg.tool_calls and len(msg.tool_calls) == 1
    assert msg.tool_calls[0].function.name == "run_shell"
    assert msg.tool_calls[0].function.arguments == '{"command": "ls"}'


# ---------- 过期的带日期定时提醒 别假装设好了 due 会静默丢弃 ----------

def test_schedule_reminder_rejects_stale_dated(monkeypatch):
    import desktop_pet.agent.tools as tools_mod
    added: list = []
    monkeypatch.setattr(tools_mod.reminders, "add",
                        lambda fire, msg, repeat="": added.append((fire, msg, repeat)))

    stale = (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
    out = tools_mod._schedule_reminder("买牛奶", stale, None)
    assert "past" in out.lower(), f"5h前的该被拒 得到: {out}"
    assert not added, "过期超宽限的不该真入库"

    future = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    tools_mod._schedule_reminder("买面包", future, None)
    assert any(m == "买面包" for _, m, _ in added), "未来时间该入库"

    # 宽限内仍入库 due 会带迟到提示送达 不该拦
    recent = (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M")
    tools_mod._schedule_reminder("喝水", recent, None)
    assert any(m == "喝水" for _, m, _ in added), "2h宽限内的过期时间仍该入库"


# ---------- 后台任务 排队未开跑时已跑记0 抢到槽才计时 ----------

def test_bgtask_queued_not_counted_as_running():
    from desktop_pet.agent.bgtasks import _BgRegistry
    reg = _BgRegistry()
    tid = reg.register("活儿", threading.Event())
    assert reg.snapshot()[0][2] == 0.0, "排队未开跑 已跑时长该是 0 不该虚高"
    reg.mark_started(tid)
    time.sleep(0.02)
    assert reg.snapshot()[0][2] > 0.0, "开跑后已跑时长该 > 0"
    reg.unregister(tid)
    assert reg.snapshot() == []
