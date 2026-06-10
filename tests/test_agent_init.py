# Agent 构造冒烟测试：__init__ 中途就会调用 _system_message()/_build_tools()，
# 属性初始化顺序错了只有实例化才会暴露（曾因 _compressed 晚于 _messages 初始化导致启动崩溃）。
import pytest

from desktop_pet.agent import loop as loop_mod
from desktop_pet.agent.loop import Agent
from desktop_pet.settings import Settings


@pytest.fixture(autouse=True)
def _isolate_session(monkeypatch, tmp_path):
    monkeypatch.setattr(loop_mod, "_SESSION_PATH", tmp_path / "session.json")


def test_agent_constructs_and_closes():
    agent = Agent(Settings())
    try:
        assert agent._messages and agent._messages[0]["role"] == "system"
        assert isinstance(agent._messages[0]["content"], str) and agent._messages[0]["content"]
        assert agent._tools, "工具列表不应为空"
        assert agent._turn_context("test").strip()
    finally:
        agent.close()


def test_subagent_constructs_and_closes():
    agent = Agent(Settings(), depth=1)
    try:
        assert agent._messages[0]["role"] == "system"
    finally:
        agent.close()
