# 联网执行器 多引擎搜索 正文抓取 媒体下载到临时目录

from __future__ import annotations

import hashlib
import logging
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)

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
    """复用 primp client 用够次数就重建换指纹"""
    global _client, _client_uses
    with _client_lock:
        # 重建判断要在锁里
        if _client is None or _client_uses >= _CLIENT_MAX_USES:
            import primp
            _client = primp.Client(impersonate=_IMPERSONATE, timeout=_FETCH_TIMEOUT)
            _client_uses = 0
        _client_uses += 1
        return _client

# 正文命中这些词多半是反爬墙
_BLOCK_MARKERS = (
    "enable javascript", "automated bot check", "verify you are human",
    "checking your browser", "captcha", "cloudflare", "access denied",
    "请开启 javascript", "人机验证", "访问验证",
)


def _http_get(url: str) -> str:
    return _client_get().get(url).text or ""


def _search_bing_cn(query: str, n: int) -> list[dict]:
    """抓 bing 中文站的 html 抠结果"""
    from urllib.parse import quote
    from lxml import html as _H

    # ensearch 0 强制中文站
    html_text = _http_get(f"https://cn.bing.com/search?q={quote(query)}&ensearch=0&setlang=zh-CN")
    if len(html_text) < 1000:
        _logger.warning("bing response too short (%d chars), likely blocked", len(html_text))
        return []
    doc = _H.fromstring(html_text)
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
    if not out:
        _logger.warning("bing xpath returned 0 results — page structure may have changed")
    return out


def _search_baidu(query: str, n: int) -> list[dict]:
    """百度搜索兜底"""
    from urllib.parse import quote
    from lxml import html as _H

    html_text = _http_get(f"https://www.baidu.com/s?wd={quote(query)}&rn={n}")
    if len(html_text) < 1000:
        _logger.warning("baidu response too short (%d chars), likely blocked", len(html_text))
        return []
    doc = _H.fromstring(html_text)
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
    if not out:
        _logger.warning("baidu xpath returned 0 results — page structure may have changed")
    return out


def _search_ddgs(query: str, n: int) -> list[dict]:
    from ddgs import DDGS

    out: list[dict] = []
    for r in DDGS().text(query, max_results=n):
        url = (r.get("href") or r.get("url") or "").strip()
        if url.startswith("http"):
            out.append({"title": r.get("title", ""), "url": url, "body": r.get("body", "")})
    return out


# 顺序就是优先级
_SEARCH_BACKENDS = (("ddgs", _search_ddgs), ("bing", _search_bing_cn), ("baidu", _search_baidu))


def web_search(query: str, max_results: int = _MAX_RESULTS) -> str:
    """逐个引擎试 谁先出结果用谁"""
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
        # 0 条也接着试下一家
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
    """抓网页 trafilatura 抠正文"""
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
        if attempt < _RETRIES - 1:  # 最后一次失败不再睡
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
    # 短且命中反爬词才判墙
    if len(text) < 300 and any(marker in text.lower() for marker in _BLOCK_MARKERS):
        return "[blocked: this page needs JavaScript or has an anti-bot wall — no content available, try a different source]"
    if len(text) > _FETCH_CAP:
        text = text[:_FETCH_CAP] + f"\n…[truncated {len(text) - _FETCH_CAP} chars]"
    return text


_MEDIA_EXT = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"})
_MAX_MEDIA_BYTES = 32 * 1024 * 1024  # 媒体下载上限 防一个 url 把临时盘内存撑爆
_CTYPE_EXT = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
    "image/webp": ".webp", "image/bmp": ".bmp", "image/svg+xml": ".svg",
}


def download_to_temp(url: str, subdir: str = "star_media") -> str | None:
    """下载图片到临时目录"""
    try:
        import primp
    except ImportError:
        return None
    try:
        response = _client_get().get(url)
        clen = str(getattr(response, "headers", {}).get("content-length", "") or "")
        if clen.isdigit() and int(clen) > _MAX_MEDIA_BYTES:
            return None  # 声明就超过上限 直接不下
        data = response.content
    except Exception:
        return None
    if not data or len(data) > _MAX_MEDIA_BYTES:
        return None  # 谎报或无 content-length 的实际超大 也不落盘
    # 先信 url 后缀 再看 content type 都认不出就 bin
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in _MEDIA_EXT:
        ctype = str(getattr(response, "headers", {}).get("content-type", "")).split(";")[0].strip()
        suffix = _CTYPE_EXT.get(ctype, ".bin")
    folder = Path(tempfile.gettempdir()) / subdir
    try:
        folder.mkdir(exist_ok=True)
        # 文件名用 url md5 前 16 位 同图覆盖去重
        target = folder / (hashlib.md5(url.encode("utf-8")).hexdigest()[:16] + suffix)
        target.write_bytes(data)
    except OSError:
        return None
    return str(target)
