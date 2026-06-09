# author: bdth
# email: 2074055628@qq.com
# 版本更新检查：查 GitHub 最新 Release 与本机版本比对，无需服务器。

from __future__ import annotations

from desktop_pet import __version__
from desktop_pet.settings import build_http_client

REPO = "dulaiduwang003/MOCHI"
_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"


def _parse(v: str) -> tuple[int, ...]:
    nums: list[int] = []
    for part in (v or "").strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(digits) if digits else 0)
    return tuple(nums) or (0,)


def is_newer(latest: str, current: str) -> bool:
    a, b = list(_parse(latest)), list(_parse(current))
    n = max(len(a), len(b))
    a += [0] * (n - len(a))
    b += [0] * (n - len(b))
    return a > b


def check_latest(proxy: str = "") -> dict:
    """查 GitHub 最新 release，返回 {status, current, latest, notes, url, error}；
    status 为 'newer' / 'latest' / 'error'。含网络，调用方务必放后台线程。"""
    result = {
        "status": "error", "current": __version__, "latest": "",
        "notes": "", "url": RELEASES_PAGE, "error": "",
    }
    try:
        client = build_http_client(proxy)
        try:
            resp = client.get(
                _API,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "Mochi-Updater"},
            )
            resp.raise_for_status()
            data = resp.json()
        finally:
            client.close()
    except Exception as exc:
        result["error"] = str(exc)[:200]
        return result
    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        result["error"] = "no release found"
        return result
    result["latest"] = tag.lstrip("vV")
    result["notes"] = str(data.get("body") or "").strip()[:500]
    result["url"] = str(data.get("html_url") or RELEASES_PAGE)
    result["status"] = "newer" if is_newer(result["latest"], __version__) else "latest"
    return result
