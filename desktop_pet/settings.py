# author: bdth
# email: 2074055628@qq.com
# 应用配置：Settings 数据类的读写与默认值、数据目录定位、HTTP 客户端构造

from __future__ import annotations

import json
import uuid as _uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import os as _os
import sys as _sys


def atomic_write_text(path: Path, text: str) -> None:
    """原子写文本(临时文件 + os.replace 覆盖目标)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{_uuid.uuid4().hex}.tmp"
    try:
        tmp.write_text(text, encoding="utf-8")
        _os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _default_data_dir() -> Path:
    """定位数据目录：开发期用项目内 data/，打包后用 %APPDATA%/Mochi，STAR_DATA_DIR 可覆盖。"""
    override = _os.environ.get("STAR_DATA_DIR")
    if override:
        return Path(override)
    if getattr(_sys, "frozen", False):
        base = _os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "Mochi"
    return Path(__file__).resolve().parent.parent / "data"


DATA_DIR = _default_data_dir()
SETTINGS_PATH = DATA_DIR / "settings.json"

CAPTURE_WINDOW = "window"
CAPTURE_FULLSCREEN = "fullscreen"

LANGUAGES = ("跟随", "中文", "English", "日本語")

PROACTIVE_LEVELS = ("安静", "正常", "话痨")

# 放手程度 → (检查点间隔 soft, 安全顶 hard)：每干满 soft 步让模型自检"还要不要继续"，
# 真推进就续杯、卡住就收尾；到 hard 步强制收尾，防失控无限烧。
AUTONOMY_LEVELS = ("省心", "正常", "放手干")
AUTONOMY_BUDGETS = {
    "省心": (12, 30),
    "正常": (24, 100),
    "放手干": (40, 500),
}

THINK_LEVELS = ("off", "low", "medium", "high", "max")
THINK_PRESETS = {
    "off": (False, 2048),
    "low": (True, 2048),
    "medium": (True, 3072),
    "high": (True, 6144),
    "max": (True, 0),
}


@dataclass
class Settings:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    embed_model: str = "text-embedding-3-small"
    proxy: str = ""
    allow_web: bool = True
    allow_control: bool = True
    allow_shell: bool = True
    language: str = "中文"
    temperature: float = 0.7
    max_tokens: int = 0
    autonomy: str = "正常"
    enable_thinking: bool = True
    think_level: str = "medium"
    proactive_enabled: bool = True
    proactive_level: str = "正常"
    ui_language: str = "中文"
    tts_enabled: bool = False
    tts_voice: str = ""
    tts_rate: int = 0
    birthday: str = ""
    watch_screen: bool = False
    clip_sampler: bool = False
    clip_alchemy: bool = False
    clip_alchemy_kinds: str = "error,foreign,code"
    quick_paste_back: bool = True
    remote_inbox: bool = False
    hotkey_summon: str = "ctrl+alt+s"
    hotkey_ask: str = "ctrl+alt+a"
    hotkey_quick: str = "ctrl+shift+q"

    @classmethod
    def load(cls) -> Settings:
        if not SETTINGS_PATH.exists():
            return cls()
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError, OSError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        fields = cls.__dataclass_fields__
        try:
            return cls(**{k: v for k, v in data.items() if k in fields})
        except (TypeError, ValueError):
            return cls()

    def save(self) -> None:
        atomic_write_text(
            SETTINGS_PATH,
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


def build_http_client(proxy: str):
    """按代理设置造一个 httpx.Client。"""
    import httpx

    timeout = httpx.Timeout(connect=8.0, read=90.0, write=30.0, pool=8.0)
    proxy = (proxy or "").strip()
    if proxy:
        try:
            return httpx.Client(proxy=proxy, trust_env=False, timeout=timeout)
        except TypeError:
            return httpx.Client(proxies=proxy, trust_env=False, timeout=timeout)
    return httpx.Client(trust_env=False, timeout=timeout)
