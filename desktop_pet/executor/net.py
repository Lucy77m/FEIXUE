# author: bdth
# email: 2074055628@qq.com
# 网络执行器：发起 HTTP 请求并返回截断后的响应文本

from __future__ import annotations

import httpx

_TIMEOUT = 30
_MAX_BODY = 20000


def http_request(url: str, method: str = "GET", body: str | None = None) -> str:
    try:
        response = httpx.request(
            method.upper(), url, content=body, timeout=_TIMEOUT, follow_redirects=True
        )
    except Exception as exc:
        return f"[request failed: {exc}]"
    text = response.text
    if len(text) > _MAX_BODY:
        text = text[:_MAX_BODY] + f"\n[truncated; full body is {len(text)} chars]"
    return f"[{response.status_code} {response.reason_phrase}]\n{text}".strip()
