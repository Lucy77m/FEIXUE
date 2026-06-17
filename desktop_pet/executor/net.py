# author: bdth
# email: 2074055628@qq.com
# 网络执行器 发 http 请求返回截断后的响应文本

from __future__ import annotations

import re

import httpx

_TIMEOUT = 30
_MAX_BODY = 20000  # 回给模型的字符上限
_MAX_DOWNLOAD = 200_000  # 边读边截的字节上限
# content type 命中任一子串就当文本读
_TEXTY = ("text/", "json", "xml", "javascript", "html", "csv", "yaml", "x-www-form-urlencoded")
_META_CHARSET = re.compile(rb'charset=["\']?\s*([a-z0-9_\-]+)', re.I)


def _looks_binary(raw: bytes) -> bool:
    """没声明 content-type 时嗅一下 含 NUL 或控制字节占比过高就当二进制 别解成乱码喂给模型"""
    sample = raw[:2048]
    if not sample:
        return False
    if b"\x00" in sample:
        return True
    texty = sum(1 for b in sample if b in (9, 10, 13) or 32 <= b < 127 or b >= 128)
    return (texty / len(sample)) < 0.7


def _decode_body(response: httpx.Response, raw: bytes) -> str:
    """按头部charset body里meta charset utf-8 gbk 的顺序解码 别一律当utf-8把gbk页面解成乱码"""
    header_cs = getattr(response, "charset_encoding", None)  # 仅当头真带 charset 才非 None
    if header_cs:
        try:
            return raw.decode(header_cs, errors="replace")
        except (LookupError, ValueError):
            pass
    m = _META_CHARSET.search(raw[:4096])
    if m:
        try:
            return raw.decode(m.group(1).decode("ascii", "ignore"), errors="replace")
        except (LookupError, ValueError):
            pass
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def http_request(url: str, method: str = "GET", body: str | None = None, headers: dict | None = None) -> str:
    """发一次 http 请求 文本响应截断返回"""
    # headers 全 str 化兜底
    hdrs = {str(k): str(v) for k, v in headers.items()} if isinstance(headers, dict) else None
    try:
        with httpx.stream(
            method.upper(), url, content=body, headers=hdrs, timeout=_TIMEOUT, follow_redirects=True
        ) as response:
            ctype = (response.headers.get("content-type") or "").lower()
            # 没声明 content type 就放行当文本
            if ctype and not any(t in ctype for t in _TEXTY):
                clen = response.headers.get("content-length") or "?"
                return (
                    f"[{response.status_code} {response.reason_phrase}]\n"
                    f"[二进制响应（{ctype}，{clen} bytes）——正文没有读取。"
                    f"要下载这个文件就用 run_python（如 httpx/urllib 存到本地路径），别用 http_request 收二进制。]"
                )
            raw = b""
            truncated_dl = False
            for chunk in response.iter_bytes():
                raw += chunk
                if len(raw) >= _MAX_DOWNLOAD:
                    truncated_dl = True
                    break
            if not ctype and _looks_binary(raw):
                # 没声明 content-type 又嗅出是二进制 别硬解成乱码
                return (f"[{response.status_code} {response.reason_phrase}]\n"
                        f"[二进制响应（无 content-type，{len(raw)} bytes）——正文没有读取。"
                        f"要下载就用 run_python 存到本地路径。]")
            text = _decode_body(response, raw)
    except Exception as exc:
        return f"[request failed: {exc}]"
    if len(text) > _MAX_BODY:
        text = text[:_MAX_BODY] + f"\n[truncated; received {len(text)} chars{' (download stopped early, body is even longer)' if truncated_dl else ''}]"
    elif truncated_dl:
        text += f"\n[download stopped at {_MAX_DOWNLOAD} bytes; body is longer]"
    return f"[{response.status_code} {response.reason_phrase}]\n{text}".strip()
