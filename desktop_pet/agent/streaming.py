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
    def __init__(
        self, content: str | None, tool_calls: list[StreamToolCall] | None,
        finish_reason: str | None = None, usage: dict | None = None,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls
        self.finish_reason = finish_reason
        self.usage = usage


def _safe_close(stream) -> None:
    """取消时主动断流——底层 close 抛什么都吞掉，别让收尾把整个回合拖崩。"""
    try:
        stream.close()
    except Exception:
        pass


def _safe_think(on_think: Callable[[str], None], text: str) -> None:
    """回调进 UI 线程，吞掉它的异常——一次刷字失败不能中断后面的分片重组。"""
    try:
        on_think(text)
    except Exception:
        pass


def _read_usage(chunk) -> dict | None:
    """从分片里捞 usage——流式下通常只有最后一片带，前面全是 None，拿到就用。"""
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
        # 命中前缀缓存的 token 数——某些供应商不给 details，缺了就当 0，不影响主计数。
        try:
            cached = int(getattr(details, "cached_tokens", 0) or 0)
        except (TypeError, ValueError):
            cached = 0
    if inp == 0 and out == 0:
        return None  # 占位的空 usage 别覆盖掉真值
    return {"input": inp, "output": out, "cached": cached}


def reassemble(
    stream, on_think: Callable[[str], None], should_cancel: Callable[[], bool] | None = None
) -> StreamMessage:
    """把流式分片攒成一条完整消息：正文拼接 + 工具调用按 index 归并，思考内容边来边回调。"""
    content: list[str] = []
    calls: dict[int, dict] = {}
    finish: str | None = None
    usage: dict | None = None
    for chunk in stream:
        # 取消优先于一切——先断流再 break，别再处理这一片，省得多刷半句字出去。
        if should_cancel is not None and should_cancel():
            _safe_close(stream)
            break
        found = _read_usage(chunk)
        if found is not None:
            usage = found
        if not chunk.choices:
            continue  # usage-only 的尾片就没 choices，跳过别崩
        choice = chunk.choices[0]
        if getattr(choice, "finish_reason", None):
            finish = choice.finish_reason
        delta = choice.delta
        if delta is None:
            continue
        # reasoning_content 是非标字段——有的供应商直接给，有的塞在 model_extra 里，两条路都兜。
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning is None and getattr(delta, "model_extra", None):
            reasoning = delta.model_extra.get("reasoning_content")
        if reasoning:
            _safe_think(on_think, reasoning)
        if delta.content:
            content.append(delta.content)
            _safe_think(on_think, delta.content)
        # 工具调用按 index 攒：name/id 只在某一片里来一次，arguments 是逐片拼的 JSON 串。
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
            cid = f"{cid}_{i}"  # 同一回合 id 撞了就缀 index 强行拆开，下游靠 id 配 tool 结果，绝不能重
        seen.add(cid)
        tool_calls.append(StreamToolCall(cid, calls[i]["name"], "".join(calls[i]["args"])))
    return StreamMessage("".join(content) or None, tool_calls or None, finish, usage)
