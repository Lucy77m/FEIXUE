# author: bdth
# email: 2074055628@qq.com
# 网络执行器：发起 HTTP 请求并返回截断后的响应文本

from __future__ import annotations

import httpx

_TIMEOUT = 30
_MAX_BODY = 20000  # 回给模型的字符上限——再多也塞不进上下文，纯浪费 token
_MAX_DOWNLOAD = 200_000  # 边读边截的字节闸：哪怕没声明 content-length，也不会被大响应拖死
# content-type 命中任一子串就当文本读；二进制(图片/视频/zip)走不到这里，交给 run_python 落盘
_TEXTY = ("text/", "json", "xml", "javascript", "html", "csv", "yaml", "x-www-form-urlencoded")


def http_request(url: str, method: str = "GET", body: str | None = None, headers: dict | None = None) -> str:
    """发一次 HTTP 请求，只把文本响应截断后回给模型；二进制不读、流式读避免大响应吃满内存。"""
    # headers 可能是模型瞎传的(非 dict / 非字符串值)，统统 str 化兜底，传不进去就当没有
    hdrs = {str(k): str(v) for k, v in headers.items()} if isinstance(headers, dict) else None
    try:
        with httpx.stream(
            method.upper(), url, content=body, headers=hdrs, timeout=_TIMEOUT, follow_redirects=True
        ) as response:
            ctype = (response.headers.get("content-type") or "").lower()
            # 没声明 content-type 时(ctype 为空)放行当文本——总比把可能有用的正文直接拦掉强
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
                    truncated_dl = True  # 提前刹住，下面好提示模型「正文其实更长」
                    break
            # 服务器没给 encoding 就赌 utf-8；坏字节用 replace 顶住，宁可出几个 � 也别让整个请求抛异常
            text = raw.decode(response.encoding or "utf-8", errors="replace")
    except Exception as exc:
        return f"[request failed: {exc}]"
    if len(text) > _MAX_BODY:
        text = text[:_MAX_BODY] + f"\n[truncated; received {len(text)} chars{' (download stopped early, body is even longer)' if truncated_dl else ''}]"
    elif truncated_dl:
        text += f"\n[download stopped at {_MAX_DOWNLOAD} bytes; body is longer]"
    return f"[{response.status_code} {response.reason_phrase}]\n{text}".strip()
