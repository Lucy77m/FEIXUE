# author: bdth
# email: 2074055628@qq.com
# 网络执行器 发 http 请求返回截断后的响应文本

from __future__ import annotations

import httpx

_TIMEOUT = 30
_MAX_BODY = 20000  # 回给模型的字符上限
_MAX_DOWNLOAD = 200_000  # 边读边截的字节上限
# content type 命中任一子串就当文本读
_TEXTY = ("text/", "json", "xml", "javascript", "html", "csv", "yaml", "x-www-form-urlencoded")


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
            text = raw.decode(response.encoding or "utf-8", errors="replace")
    except Exception as exc:
        return f"[request failed: {exc}]"
    if len(text) > _MAX_BODY:
        text = text[:_MAX_BODY] + f"\n[truncated; received {len(text)} chars{' (download stopped early, body is even longer)' if truncated_dl else ''}]"
    elif truncated_dl:
        text += f"\n[download stopped at {_MAX_DOWNLOAD} bytes; body is longer]"
    return f"[{response.status_code} {response.reason_phrase}]\n{text}".strip()
