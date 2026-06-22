# API瞬时错误退避测试 限流5xx超时才重试 400和鉴权快速失败 取消能打断退避

from __future__ import annotations

import threading
import time

import httpx
import pytest
from openai import (
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

import desktop_pet.agent.loop as loop
from desktop_pet.agent.loop import Agent, _retry_after_seconds


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    # 退避基准压到几乎为0 不拖慢测试 逻辑不变
    monkeypatch.setattr(loop, "_RETRY_BASE_S", 0.001)
    monkeypatch.setattr(loop, "_RETRY_CAP_S", 0.01)
    monkeypatch.setattr(loop, "_RETRY_MAX", 3)


def _req():
    return httpx.Request("POST", "http://x/v1/chat/completions")


def _rate_limit(retry_after=None):
    headers = {"retry-after": str(retry_after)} if retry_after is not None else {}
    resp = httpx.Response(429, headers=headers, request=_req())
    return RateLimitError("rate limited", response=resp, body=None)


def _timeout():
    return APITimeoutError(request=_req())


def _auth():
    resp = httpx.Response(401, request=_req())
    return AuthenticationError("bad key", response=resp, body=None)


def _bad_request():
    resp = httpx.Response(400, request=_req())
    return BadRequestError("bad param", response=resp, body=None)


class _FakeAgent:
    """只装_create_stream要用到的两样 client和cancel 其余不碰"""

    def __init__(self, behaviors):
        # behaviors是一串 每次create按序消费 异常就raise 其它当成功结果返回
        self._behaviors = list(behaviors)
        self._cancel = threading.Event()
        self.calls = 0

    def _client(self):
        agent = self

        class _C:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kw):
                        agent.calls += 1
                        b = agent._behaviors.pop(0)
                        if isinstance(b, Exception):
                            raise b
                        return b
        return _C()


def _run(behaviors):
    fa = _FakeAgent(behaviors)
    return fa, Agent._create_stream(fa, {"model": "m"})


def test_retries_then_succeeds():
    fa, out = _run([_timeout(), _rate_limit(), "STREAM_OK"])
    assert out == "STREAM_OK"
    assert fa.calls == 3, "该重试两次第三次成功"


def test_gives_up_after_max():
    fa = _FakeAgent([_timeout()] * 10)
    with pytest.raises(APITimeoutError):
        Agent._create_stream(fa, {"model": "m"})
    assert fa.calls == 4, "首发+3次重试=4次后放弃"


def test_bad_request_not_retried():
    fa = _FakeAgent([_bad_request(), "never"])
    with pytest.raises(BadRequestError):
        Agent._create_stream(fa, {"model": "m"})
    assert fa.calls == 1, "400立刻抛 交给上层剥参数 不退避"


def test_auth_error_not_retried():
    fa = _FakeAgent([_auth(), "never"])
    with pytest.raises(AuthenticationError):
        Agent._create_stream(fa, {"model": "m"})
    assert fa.calls == 1, "鉴权错重试没用 快速失败"


def test_cancel_aborts_backoff(monkeypatch):
    # 退避睡久一点好观察取消打断
    monkeypatch.setattr(loop, "_RETRY_BASE_S", 5.0)
    monkeypatch.setattr(loop, "_RETRY_CAP_S", 5.0)
    fa = _FakeAgent([_timeout(), _timeout(), "STREAM_OK"])
    # 起个线程200ms后取消 主调用应被立刻叫醒而非睡满5秒
    threading.Timer(0.2, fa._cancel.set).start()
    t0 = time.monotonic()
    with pytest.raises(APITimeoutError):
        Agent._create_stream(fa, {"model": "m"})
    assert time.monotonic() - t0 < 2.0, "取消该立刻打断退避 不傻等"


def test_retry_after_header_parsed():
    assert _retry_after_seconds(_rate_limit(retry_after=3)) == 3.0
    assert _retry_after_seconds(_rate_limit()) is None
    assert _retry_after_seconds(_timeout()) is None  # 无response属性
