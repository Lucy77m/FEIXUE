# run() 主循环的脚本化测试：用假 _complete 喂预设回复，覆盖工具派发、
# 硬约束守卫（高危命令/先读后改）、空回复重试、取消、schema 校验、会话持久化。
# 不碰网络；会话文件指到 tmp_path，不污染真实 data/。
import json
import time

import pytest

from desktop_pet.agent import loop as loop_mod
from desktop_pet.agent.loop import Agent
from desktop_pet.agent.streaming import StreamMessage, StreamToolCall
from desktop_pet.settings import Settings


class _NullAudit:
    def user(self, *a, **k): pass
    def reply(self, *a, **k): pass
    def tool(self, *a, **k): pass


@pytest.fixture
def agent(monkeypatch, tmp_path):
    monkeypatch.setattr(loop_mod, "_SESSION_PATH", tmp_path / "session.json")
    monkeypatch.setattr(loop_mod, "audit", _NullAudit())
    a = Agent(Settings())
    yield a
    a.close()


def _script(monkeypatch, replies: list[StreamMessage]):
    queue = list(replies)

    def fake_complete(self, on_think, offer_tools=True):
        assert queue, "模型被调用的次数超过了脚本预设"
        return queue.pop(0)

    monkeypatch.setattr(Agent, "_complete", fake_complete)
    return queue


def _tool_call(cid: str, name: str, args: dict) -> StreamMessage:
    return StreamMessage(None, [StreamToolCall(cid, name, json.dumps(args))], "tool_calls")


class TestRunLoop:
    def test_simple_reply(self, agent, monkeypatch):
        _script(monkeypatch, [StreamMessage("[happy]\n你好", None, "stop")])
        assert agent.run("在吗") == "[happy]\n你好"

    def test_session_saved_after_turn(self, agent, monkeypatch):
        _script(monkeypatch, [StreamMessage("[happy]\n好", None, "stop")])
        agent.run("记一下")
        data = json.loads(loop_mod._SESSION_PATH.read_text(encoding="utf-8"))
        assert any(m["role"] == "user" for m in data["messages"])

    def test_tool_call_then_reply(self, agent, monkeypatch):
        plans: list[str] = []
        _script(monkeypatch, [
            _tool_call("c1", "plan", {"steps": [{"text": "第一步", "status": "doing"}]}),
            StreamMessage("[happy]\n计划好了", None, "stop"),
        ])
        reply = agent.run("做个计划", on_plan=plans.append)
        assert reply == "[happy]\n计划好了"
        assert plans and "第一步" in plans[0]
        tool_results = [m for m in agent._messages if m.get("role") == "tool"]
        assert any("Plan updated" in m["content"] for m in tool_results)

    def test_empty_reply_retried_with_nudge(self, agent, monkeypatch):
        _script(monkeypatch, [
            StreamMessage(None, None, "stop"),
            StreamMessage("[happy]\n这次有话了", None, "stop"),
        ])
        assert agent.run("说话") == "[happy]\n这次有话了"

    def test_cancel_mid_turn(self, agent, monkeypatch):
        def fake_complete(self, on_think, offer_tools=True):
            self.cancel()
            return _tool_call("c1", "plan", {"steps": [{"text": "x"}]})

        monkeypatch.setattr(Agent, "_complete", fake_complete)
        result = agent.run("跑个长任务")
        assert Agent.was_cancelled(result)


class TestGuards:
    def test_risky_shell_denied_without_confirm_ui(self, agent, monkeypatch):
        _script(monkeypatch, [
            _tool_call("c1", "run_shell", {"command": "git push --force origin main"}),
            StreamMessage("[sad]\n被拦了", None, "stop"),
        ])
        agent.run("强推一下")
        tool_results = [m["content"] for m in agent._messages if m.get("role") == "tool"]
        assert any("安全拦截" in t for t in tool_results)

    def test_edit_requires_read_first(self, agent, monkeypatch, tmp_path):
        target = tmp_path / "a.txt"
        target.write_text("original", encoding="utf-8")
        _script(monkeypatch, [
            _tool_call("c1", "edit_file", {"path": str(target), "old": "original", "new": "changed"}),
            StreamMessage("[confused]\n要先读", None, "stop"),
        ])
        agent.run("改文件")
        tool_results = [m["content"] for m in agent._messages if m.get("role") == "tool"]
        assert any("read_file" in t for t in tool_results)
        assert target.read_text(encoding="utf-8") == "original"

    def test_edit_allowed_after_read(self, agent, monkeypatch, tmp_path):
        target = tmp_path / "b.txt"
        target.write_text("original", encoding="utf-8")
        _script(monkeypatch, [
            _tool_call("c1", "read_file", {"path": str(target)}),
            _tool_call("c2", "edit_file", {"path": str(target), "old": "original", "new": "changed"}),
            StreamMessage("[happy]\n改好了", None, "stop"),
        ])
        agent.run("读了再改")
        assert target.read_text(encoding="utf-8") == "changed"

    def test_edit_blocked_when_file_changed_behind_back(self, agent, monkeypatch, tmp_path):
        target = tmp_path / "c.txt"
        target.write_text("v1", encoding="utf-8")
        agent._note_file("read_file", {"path": str(target)})
        time.sleep(0.01)
        target.write_text("v2", encoding="utf-8")
        import os
        os.utime(target, (time.time() + 10, time.time() + 10))
        denial = agent._guard_edit("edit_file", {"path": str(target)})
        assert denial is not None and "重新 read_file" in denial


class TestSchemaValidation:
    class _StubWorker:
        def __init__(self, replies):
            self._replies = list(replies)

        def run(self, _msg):
            return self._replies.pop(0)

    def test_good_json_normalized(self, agent):
        out = agent._validate_schema_result(self._StubWorker([]), '废话 {"a": 1} 收尾', '{"a":int}')
        assert json.loads(out) == {"a": 1}

    def test_bad_json_retried_once(self, agent):
        worker = self._StubWorker(['这次给你 {"a": 2}'])
        out = agent._validate_schema_result(worker, "完全不是 JSON", '{"a":int}')
        assert json.loads(out) == {"a": 2}

    def test_two_failures_reported_honestly(self, agent):
        worker = self._StubWorker(["还是不是 JSON"])
        out = agent._validate_schema_result(worker, "不是 JSON", '{"a":int}')
        assert "没能给出合法 JSON" in out


class TestSessionRestore:
    def test_fresh_session_restored_and_sealed(self, monkeypatch, tmp_path):
        path = tmp_path / "session.json"
        monkeypatch.setattr(loop_mod, "_SESSION_PATH", path)
        monkeypatch.setattr(loop_mod, "audit", _NullAudit())
        path.write_text(json.dumps({
            "saved_at": time.time(),
            "compressed": "之前在改 fs.py",
            "messages": [
                {"role": "user", "content": "帮我改个文件"},
                {"role": "assistant", "content": "", "tool_calls": [
                    {"id": "x1", "type": "function",
                     "function": {"name": "read_file", "arguments": "{}"}},
                ]},
            ],
        }, ensure_ascii=False), encoding="utf-8")
        a = Agent(Settings())
        try:
            assert any(m.get("role") == "user" for m in a._messages)
            sealed = [m for m in a._messages if m.get("role") == "tool" and m.get("tool_call_id") == "x1"]
            assert sealed
            assert "fs.py" in a._compressed
        finally:
            a.close()

    def test_stale_session_ignored(self, monkeypatch, tmp_path):
        path = tmp_path / "session.json"
        monkeypatch.setattr(loop_mod, "_SESSION_PATH", path)
        monkeypatch.setattr(loop_mod, "audit", _NullAudit())
        path.write_text(json.dumps({
            "saved_at": time.time() - 3600,
            "messages": [{"role": "user", "content": "旧话"}],
        }), encoding="utf-8")
        a = Agent(Settings())
        try:
            assert len(a._messages) == 1
        finally:
            a.close()
