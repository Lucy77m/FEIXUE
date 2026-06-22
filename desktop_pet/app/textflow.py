# 文本小工具 情绪标签解析 分句 异常转人话

from __future__ import annotations

import re


_EMOTION_RE = re.compile(r"^\s*\[(\w+)\]\s*")
_SPLIT_AFTER = frozenset("。！？!?，、；,;")
_BRACKETS = {"（": "）", "(": ")", "「": "」", "『": "』", "【": "】", "《": "》", "〈": "〉",
             "[": "]", "{": "}", "“": "”", "‘": "’"}


def _parse_emotion(text: str) -> tuple[str, str]:
    match = _EMOTION_RE.match(text)
    if match:
        return match.group(1).lower(), text[match.end():].strip()
    return "neutral", text.strip()


def _split_sentences(text: str) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    stack: list[str] = []
    for ch in text:
        if ch == "\n":
            if buf:
                out.append("".join(buf))
                buf = []
            stack.clear()
            continue
        buf.append(ch)
        if ch in _BRACKETS:
            stack.append(_BRACKETS[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
        elif ch in _SPLIT_AFTER and not stack:
            out.append("".join(buf))
            buf = []
    if buf:
        out.append("".join(buf))
    sentences = [s.strip() for s in out if s.strip()]
    return sentences or [text.strip()]


def _friendly_error(exc: Exception) -> str:
    """异常转成一句人话"""
    name = type(exc).__name__
    nlow = name.lower()
    msg = str(exc)
    low = msg.lower()
    if "authentication" in nlow or "401" in msg or "invalid api key" in low or "incorrect api key" in low or "unauthorized" in low:
        return "诶…我连不上大脑：API key 好像不对或没权限。打开控制面板检查下密钥吧。"
    if "permission" in nlow or "403" in msg:
        return "这个 key 没访问权限（403）——确认下密钥对应的服务开通了没。"
    if "notfound" in nlow or ("404" in msg and "model" in low):
        return "模型名字我这边没找到（404），去控制面板核对下模型名。"
    if "connection" in nlow or "timeout" in nlow or any(
        k in low for k in ("timed out", "connect", "getaddrinfo", "ssl", "proxy", "failed to establish")
    ):
        return "网络连不上或超时了——检查下网络 / 代理设置？"
    if "ratelimit" in nlow or "429" in msg or "quota" in low or "rate limit" in low:
        return "请求太频繁或额度用完了（429），缓一下再试～"
    short = msg if len(msg) <= 200 else msg[:200] + "…"
    return f"出了点状况：{name}: {short}"
