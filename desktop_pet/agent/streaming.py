# author: bdth
# email: 2074055628@qq.com
# 将流式 LLM 响应的分片(delta)重组为完整消息(正文 + 工具调用),并实时回调思考内容

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
    def __init__(self, content: str | None, tool_calls: list[StreamToolCall] | None) -> None:
        self.content = content
        self.tool_calls = tool_calls


def _safe_close(stream) -> None:
    try:
        stream.close()
    except Exception:
        pass


def _safe_think(on_think: Callable[[str], None], text: str) -> None:
    try:
        on_think(text)
    except Exception:
        pass


def reassemble(
    stream, on_think: Callable[[str], None], should_cancel: Callable[[], bool] | None = None
) -> StreamMessage:
    content: list[str] = []
    calls: dict[int, dict] = {}
    for chunk in stream:
        if should_cancel is not None and should_cancel():
            _safe_close(stream)
            break
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning is None and getattr(delta, "model_extra", None):
            reasoning = delta.model_extra.get("reasoning_content")
        if reasoning:
            _safe_think(on_think, reasoning)
        if delta.content:
            content.append(delta.content)
            _safe_think(on_think, delta.content)
        for call in delta.tool_calls or []:
            slot = calls.setdefault(call.index, {"id": "", "name": "", "args": []})
            if call.id:
                slot["id"] = call.id
            if call.function and call.function.name:
                slot["name"] = call.function.name
            if call.function and call.function.arguments:
                slot["args"].append(call.function.arguments)
    tool_calls = [
        StreamToolCall(calls[i]["id"], calls[i]["name"], "".join(calls[i]["args"]))
        for i in sorted(calls)
    ] or None
    return StreamMessage("".join(content) or None, tool_calls)
