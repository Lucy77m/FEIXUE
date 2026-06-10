# author: bdth
# email: 2074055628@qq.com
# 联网执行器：多引擎网页搜索、正文抓取提取、媒体文件下载到临时目录

from __future__ import annotations

import hashlib
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

_MAX_RESULTS = 6
_FETCH_CAP = 20_000
_FETCH_TIMEOUT = 8.0
_RETRIES = 2
_RETRY_SLEEP = 0.8
_IMPERSONATE = "random"

_client = None
_client_lock = threading.Lock()
_client_uses = 0
_CLIENT_MAX_USES = 40


def _client_get():
    """复用 primp.Client，用够 _CLIENT_MAX_USES 次就重建 → 换一批 impersonate 指纹，别老一个指纹撞风控。"""
    global _client, _client_uses
    with _client_lock:
        # 多线程共用，重建判断得在锁里，不然俩线程同时进来各建一个。
        if _client is None or _client_uses >= _CLIENT_MAX_USES:
            import primp
            _client = primp.Client(impersonate=_IMPERSONATE, timeout=_FETCH_TIMEOUT)
            _client_uses = 0
        _client_uses += 1
        return _client

# 正文里出现这些词＝多半被反爬墙拦了（人机验证/JS 挑战页），不是真内容。
_BLOCK_MARKERS = (
    "enable javascript", "automated bot check", "verify you are human",
    "checking your browser", "captcha", "cloudflare", "access denied",
    "请开启 javascript", "人机验证", "访问验证",
)


def _http_get(url: str) -> str:
    return _client_get().get(url).text or ""


def _search_bing_cn(query: str, n: int) -> list[dict]:
    """直接抓 cn.bing.com 的 HTML 抠结果 —— 没用官方 API（要 key、要钱）。靠 b_algo 这个结果块的 class。"""
    from urllib.parse import quote
    from lxml import html as _H

    # ensearch=0 强制中文站，否则按浏览器语言可能跳到国际版，结果质量两样。
    doc = _H.fromstring(_http_get(f"https://cn.bing.com/search?q={quote(query)}&ensearch=0&setlang=zh-CN"))
    out: list[dict] = []
    for li in doc.xpath('//li[contains(concat(" ", normalize-space(@class), " "), " b_algo ")]'):
        a = li.xpath('.//h2//a[@href]')
        if not a:
            continue
        url = (a[0].get("href") or "").strip()
        title = a[0].text_content().strip()
        p = li.xpath('.//p')
        body = p[0].text_content().strip() if p else ""
        if title and url.startswith("http"):
            out.append({"title": title, "url": url, "body": body})
        if len(out) >= n:
            break
    return out


def _search_baidu(query: str, n: int) -> list[dict]:
    """百度兜底 —— 它的结果 div class 变着花样（c-container / result），摘要 class 更乱，所以下面 xpath 多塞了几种。"""
    from urllib.parse import quote
    from lxml import html as _H

    doc = _H.fromstring(_http_get(f"https://www.baidu.com/s?wd={quote(query)}&rn={n}"))
    out: list[dict] = []
    for div in doc.xpath('//div[contains(@class, "c-container") or contains(@class, "result")]'):
        a = div.xpath('.//h3//a[@href]')
        if not a:
            continue
        url = (a[0].get("href") or "").strip()
        title = a[0].text_content().strip()
        body = " ".join("".join(
            div.xpath('.//*[contains(@class, "abstract") or contains(@class, "c-abstract") or contains(@class, "content-right")]//text()')
        ).split())
        if title and url.startswith("http"):
            out.append({"title": title, "url": url, "body": body[:200]})
        if len(out) >= n:
            break
    return out


def _search_ddgs(query: str, n: int) -> list[dict]:
    from ddgs import DDGS

    out: list[dict] = []
    for r in DDGS().text(query, max_results=n):
        url = (r.get("href") or r.get("url") or "").strip()
        if url.startswith("http"):
            out.append({"title": r.get("title", ""), "url": url, "body": r.get("body", "")})
    return out


# 顺序＝优先级：bing 国内能直连且结构稳，baidu 次之，ddgs 放最后（国内常连不上，但解析最规整）。
_SEARCH_BACKENDS = (("bing", _search_bing_cn), ("baidu", _search_baidu), ("ddgs", _search_ddgs))


def web_search(query: str, max_results: int = _MAX_RESULTS) -> str:
    """按 _SEARCH_BACKENDS 顺序逐个引擎试，谁先出结果用谁；全挂了把各家错误类型拼回去方便排查。"""
    query = (query or "").strip()
    if not query:
        return "(no search query given)"
    results: list[dict] = []
    used = ""
    errors: list[str] = []
    for name, backend in _SEARCH_BACKENDS:
        try:
            found = backend(query, max_results)
        except Exception as exc:
            errors.append(f"{name}:{type(exc).__name__}")
            continue
        # 解析成功但 0 条也算这家没戏，接着试下一个，别提前 return 空。
        if found:
            results, used = found, name
            break
    if not results:
        detail = "; ".join(errors)
        return f"[search failed on all engines: {detail}]" if detail else "(no results found)"
    blocks = [f"(via {used})"]
    for i, result in enumerate(results, 1):
        title = (result.get("title") or "").strip()
        url = (result.get("url") or "").strip()
        snippet = " ".join((result.get("body") or "").split())[:200]
        blocks.append(f"{i}. {title}\n   {url}\n   {snippet}")
    return "\n".join(blocks)


def web_fetch(url: str) -> str:
    """抓网页 → trafilatura 抠正文喂模型。失败一律返回 [方括号] 提示串，不抛——上层当普通文本读。"""
    url = (url or "").strip()
    if not url:
        return "(no URL given)"
    try:
        import primp
        import trafilatura
    except ImportError:
        return "[web fetch unavailable: missing primp / trafilatura]"
    html = ""
    error = ""
    for attempt in range(_RETRIES):
        try:
            html = _client_get().get(url).text or ""
            if html.strip():
                break
        except Exception as exc:
            error = str(exc)
        if attempt < _RETRIES - 1:  # 最后一次失败就别再睡了，直接落到下面报错
            time.sleep(_RETRY_SLEEP)
    if not html.strip():
        return f"[fetch failed (after {_RETRIES} retries): {error or 'empty response'}]"
    try:
        text = trafilatura.extract(html, include_comments=False, include_links=False) or ""
    except Exception as exc:
        return f"[text extraction failed: {exc}]"
    text = text.strip()
    if not text:
        return "(no main text extracted — likely a dynamic / paywalled / anti-scraping page)"
    # 短＋命中反爬关键词才判墙：长正文里偶尔提一句"captcha"是正常内容，别误杀。
    if len(text) < 300 and any(marker in text.lower() for marker in _BLOCK_MARKERS):
        return "[blocked: this page needs JavaScript or has an anti-bot wall — no content available, try a different source]"
    if len(text) > _FETCH_CAP:
        text = text[:_FETCH_CAP] + f"\n…[truncated {len(text) - _FETCH_CAP} chars]"
    return text


_MEDIA_EXT = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"})
_CTYPE_EXT = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
    "image/webp": ".webp", "image/bmp": ".bmp", "image/svg+xml": ".svg",
}


def download_to_temp(url: str, subdir: str = "star_media") -> str | None:
    """把图片下到临时目录，给桌宠"星星收藏"用。哪步挂了都吞掉返回 None。"""
    try:
        import primp
    except ImportError:
        return None
    try:
        response = _client_get().get(url)
        data = response.content
    except Exception:
        return None
    if not data:
        return None
    # 先信 URL 后缀；很多 CDN 链接没后缀（带 query 或纯 hash 路径），再退而看 content-type，都认不出就 .bin。
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in _MEDIA_EXT:
        ctype = str(getattr(response, "headers", {}).get("content-type", "")).split(";")[0].strip()
        suffix = _CTYPE_EXT.get(ctype, ".bin")
    folder = Path(tempfile.gettempdir()) / subdir
    try:
        folder.mkdir(exist_ok=True)
        # 文件名用 url 的 md5 前 16 位 → 同一张图重复下覆盖同名，天然去重、不堆垃圾。
        target = folder / (hashlib.md5(url.encode("utf-8")).hexdigest()[:16] + suffix)
        target.write_bytes(data)
    except OSError:
        return None
    return str(target)
