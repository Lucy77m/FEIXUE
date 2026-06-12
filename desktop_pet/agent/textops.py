# author: bdth
# email: 2074055628@qq.com
# 纯文本处理 token毛估 think和工具调用泄漏清理 json抠取 转写渲染

from __future__ import annotations

import json
import re


_MAX_TOOL_RESULT_CHARS = 8_000
_TOKENS_PER_CJK_CHAR = 1.0
_TOKENS_PER_OTHER_CHAR = 0.25
_TOKENS_PER_MESSAGE = 4
_TOKENS_PER_IMAGE = 1_200
_SUMMARY_SRC_MAX_CHARS = 12_000


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x3400 <= o <= 0x9FFF or 0x3000 <= o <= 0x30FF or 0xF900 <= o <= 0xFAFF
            or 0xFF00 <= o <= 0xFFEF or 0x20000 <= o <= 0x3FFFF)


def _text_tokens(text: str) -> int:
    cjk = sum(1 for ch in text if _is_cjk(ch))
    return int(cjk * _TOKENS_PER_CJK_CHAR + (len(text) - cjk) * _TOKENS_PER_OTHER_CHAR)


def _estimate_tokens(message: dict) -> int:
    """毛估一条消息token数"""
    total = _TOKENS_PER_MESSAGE
    content = message.get("content")
    if isinstance(content, str):
        total += _text_tokens(content)
    elif isinstance(content, list):
        for part in content:
            if part.get("type") == "image_url":
                total += _TOKENS_PER_IMAGE
            else:
                total += _text_tokens(part.get("text", ""))
    for call in message.get("tool_calls") or []:
        fn = call.get("function", {})
        total += _text_tokens((fn.get("name") or "") + (fn.get("arguments") or ""))
    return total


def _cap_tool_result(text: str) -> str:
    """工具输出过长掐成头尾两段"""
    if len(text) <= _MAX_TOOL_RESULT_CHARS:
        return text
    head = _MAX_TOOL_RESULT_CHARS * 5 // 8
    tail = _MAX_TOOL_RESULT_CHARS - head
    omitted = len(text) - head - tail
    return (text[:head] + f"\n…[输出过长，中间省略 {omitted} 字符；头尾都保留了]…\n" + text[-tail:])


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think_leak(text: str) -> str:
    """清掉think标签泄漏"""
    if not text or "think>" not in text:
        return text
    text = _THINK_BLOCK_RE.sub("", text)
    return text.replace("<think>", "").replace("</think>", "").strip()


# 工具调用本该走tool_calls字段 有时模型当正文吐出来 这些标记打头就是泄漏
_TOOLCALL_MARK_RE = re.compile(
    r"(?:\bcall\b\s*)?<\s*/?\s*(?:antml:)?(?:invoke|function_calls|parameter|tool_call)\b",
    re.IGNORECASE,
)


def _strip_toolcall_leak(text: str) -> str:
    """工具调用语法漏进正文就从第一处标记起整段切掉 正常回复绝不含这些"""
    if not text:
        return text
    m = _TOOLCALL_MARK_RE.search(text)
    if m is None:
        return text
    return text[: m.start()].rstrip()


_PLAN_STATUS_ALIAS = {
    "done": "done", "completed": "done", "complete": "done", "finished": "done",
    "finish": "done", "ok": "done", "success": "done", "✓": "done", "x": "done",
    "doing": "doing", "in_progress": "doing", "in-progress": "doing", "inprogress": "doing",
    "active": "doing", "current": "doing", "running": "doing", "wip": "doing", "ongoing": "doing", "started": "doing",
    "todo": "todo", "pending": "todo", "not_started": "todo", "queued": "todo", "waiting": "todo",
}


def _norm_plan_status(status) -> str:
    """状态写法归一到todo doing done"""
    return _PLAN_STATUS_ALIAS.get(str(status or "").strip().lower(), "todo")


def _parse_json(text: str) -> dict | None:
    """从文本抠最外层json对象 失败给None"""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _parse_json_value(text: str) -> dict | list | None:
    """从文本抠json 对象和数组都收"""
    best: tuple[int, dict | list] | None = None
    for opener, closer in (("{", "}"), ("[", "]")):
        end = text.rfind(closer)
        start = text.find(opener)
        for _ in range(4):  # 最多往后挪4个开括号试探
            if start == -1 or end <= start:
                break
            try:
                data = json.loads(text[start : end + 1])
            except (json.JSONDecodeError, ValueError):
                start = text.find(opener, start + 1)
                continue
            if isinstance(data, (dict, list)) and (best is None or start < best[0]):
                best = (start, data)
            break
    return best[1] if best else None


def _render_transcript(messages: list[dict]) -> str:
    """被裁消息压成纯文本喂压缩模型"""
    lines: list[str] = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content")
        if isinstance(content, list):
            texts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
            text = " ".join(t for t in texts if t).strip() or "[图片]"
        else:
            text = str(content or "").strip()
        if role == "assistant":
            calls = m.get("tool_calls") or []
            if calls:
                names = ", ".join(
                    f"{c.get('function', {}).get('name', '?')}({(c.get('function', {}).get('arguments') or '')[:100]})"
                    for c in calls
                )
                text = (text + " " if text else "") + f"[调用工具: {names}]"
        elif role == "tool":
            text = "[工具结果] " + text
        if text:
            lines.append(f"{role}: {text[:500]}")
    out = "\n".join(lines)
    if len(out) > _SUMMARY_SRC_MAX_CHARS:
        half = _SUMMARY_SRC_MAX_CHARS // 2
        out = out[:half] + "\n…(中间略)…\n" + out[-half:]
    return out
