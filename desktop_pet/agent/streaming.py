# author: bdth
# email: 2074055628@qq.com
# 流式响应分片重组成完整消息 实时回调思考内容

from __future__ import annotations

from collections.abc import Callable


class StreamFn:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class StreamToolCall:
    def __init__(self, call_id: str, name: str, arguments: str) -> None:
        self.id = call_id
        self.type = "function"
        self.function = StreamFn(name, arguments)


class StreamMessage:
    def __init__(
        self, content: str | None, tool_calls: list[StreamToolCall] | None,
        finish_reason: str | None = None, usage: dict | None = None,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls
        self.finish_reason = finish_reason
        self.usage = usage


def _safe_close(stream) -> None:
    """断流 close异常吞掉"""
    try:
        stream.close()
    except Exception:
        pass


def _safe_think(on_think: Callable[[str], None], text: str) -> None:
    """回调思考内容 异常吞掉"""
    try:
        on_think(text)
    except Exception:
        pass


def _read_usage(chunk) -> dict | None:
    """从分片取usage"""
    u = getattr(chunk, "usage", None)
    if u is None:
        return None
    try:
        inp = int(getattr(u, "prompt_tokens", 0) or 0)
        out = int(getattr(u, "completion_tokens", 0) or 0)
    except (TypeError, ValueError):
        return None
    cached = 0
    details = getattr(u, "prompt_tokens_details", None)
    if details is not None:
        # 缓存命中token数 没有就当0
        try:
            cached = int(getattr(details, "cached_tokens", 0) or 0)
        except (TypeError, ValueError):
            cached = 0
    if inp == 0 and out == 0:
        return None  # 空usage不覆盖真值
    return {"input": inp, "output": out, "cached": cached}


def reassemble(
    stream, on_think: Callable[[str], None], should_cancel: Callable[[], bool] | None = None
) -> StreamMessage:
    """流式分片攒成完整消息"""
    content: list[str] = []
    calls: dict[int, dict] = {}
    finish: str | None = None
    usage: dict | None = None
    for chunk in stream:
        # 取消就先断流再break
        if should_cancel is not None and should_cancel():
            _safe_close(stream)
            break
        found = _read_usage(chunk)
        if found is not None:
            usage = found
        if not chunk.choices:
            continue  # usage尾片没choices 跳过
        choice = chunk.choices[0]
        if getattr(choice, "finish_reason", None):
            finish = choice.finish_reason
        delta = choice.delta
        if delta is None:
            continue
        # reasoning_content从delta和model_extra两处取
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning is None and getattr(delta, "model_extra", None):
            reasoning = delta.model_extra.get("reasoning_content")
        if reasoning:
            _safe_think(on_think, reasoning)
        if delta.content:
            content.append(delta.content)
            _safe_think(on_think, delta.content)
        # 工具调用按index攒 arguments逐片拼
        for call in delta.tool_calls or []:
            slot = calls.setdefault(call.index, {"id": "", "name": "", "args": []})
            if call.id:
                slot["id"] = call.id
            if call.function and call.function.name:
                slot["name"] = call.function.name
            if call.function and call.function.arguments:
                slot["args"].append(call.function.arguments)
    seen: set[str] = set()
    tool_calls: list[StreamToolCall] = []
    for i in sorted(calls):
        cid = calls[i]["id"] or f"call_{i}"
        if cid in seen:
            cid = f"{cid}_{i}"  # id撞了缀index拆开
        seen.add(cid)
        tool_calls.append(StreamToolCall(cid, calls[i]["name"], "".join(calls[i]["args"])))
    return StreamMessage("".join(content) or None, tool_calls or None, finish, usage)
