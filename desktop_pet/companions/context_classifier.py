"""Unified foreground-window classification for all companion modules.

Consolidates the duplicated keyword lists from wellbeing, boredom, and playtime
into a single source of truth.  Returns a fine-grained category that each
consumer can collapse into its own coarser set.
"""

from __future__ import annotations

_TERMINAL = (
    "powershell", "windows terminal", "cmd.exe", "terminal", "wsl", "codex",
    "windowsterminal", "wt.exe",
)

_CODE = (
    "visual studio", "vs code", "vscode", " - code", "pycharm", "intellij",
    " idea", "sublime", "notepad++", "cursor", "windsurf", "rider", "goland",
    "clion", "webstorm", "neovim", "- vim", "code.exe", "devenv", "idea64",
    "overleaf", "jupyter",
)

_DOCUMENT = (
    "word", "- word", "- excel", "- powerpoint", "winword", "acrobat",
    "sumatrapdf", "obsidian", "notepad", ".pdf", ".docx",
)

_MEDIA = (
    "youtube", "bilibili", "哔哩哔哩", "netflix", "twitch", "tiktok", "抖音",
    "douyin", "- vlc", "vlc", "mpv", "potplayer", "spotify", "爱奇艺",
    "腾讯视频", "优酷",
)

_SOCIAL = (
    "reddit", "instagram", "facebook", "微博", "小红书",
)

_BROWSER = (
    "chrome", "msedge", "firefox", "brave", "opera",
)

# Check order matters: terminal before code (powershell overlaps),
# media before social (some overlap), browser last (very broad).
_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("terminal", _TERMINAL),
    ("code", _CODE),
    ("document", _DOCUMENT),
    ("media", _MEDIA),
    ("social", _SOCIAL),
    ("browser", _BROWSER),
)


def classify_window(title: str, process: str = "") -> str:
    """Classify a foreground window by its title and optional process name.

    Returns one of: ``"terminal"``, ``"code"``, ``"document"``, ``"media"``,
    ``"social"``, ``"browser"``, or ``"generic"``.
    """
    t = (title + " " + process).lower()
    if not t.strip():
        return "generic"
    for category, keywords in _CATEGORIES:
        if any(kw in t for kw in keywords):
            return category
    return "generic"
