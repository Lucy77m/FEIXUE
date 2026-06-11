# author: bdth
# email: 2074055628@qq.com
# 应用配置 Settings 读写 数据目录定位 http 客户端构造

from __future__ import annotations

import json
import uuid as _uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import os as _os
import sys as _sys


def atomic_write_text(path: Path, text: str) -> None:
    """原子写文件"""
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
    """定位数据目录"""
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

# 自主度档位对应步数和工具上限
AUTONOMY_BUDGETS = {
    "省心": (12, 30),
    "正常": (24, 100),
    "放手干": (40, 500),
}

# 思考档位对应thinking开关和预算
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
    subagent_model: str = ""  # 留空跟主 model 走

    embed_model: str = "text-embedding-3-small"
    proxy: str = ""
    allow_web: bool = True
    allow_control: bool = True
    allow_shell: bool = True
    language: str = "中文"
    temperature: float = 0.7
    max_tokens: int = 0
    history_tokens: int = 24_000  # 历史超量往前截
    autonomy: str = "正常"
    enable_thinking: bool = True
    think_level: str = "medium"
    proactive_enabled: bool = True
    proactive_level: str = "正常"
    ui_language: str = "中文"
    tts_enabled: bool = False
    tts_rate: int = 0
    sfx_enabled: bool = False
    weather_enabled: bool = False  # 天气拟态默认关：IP定位常常离谱(代理/CGNAT)，宁可不显也不显错的
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
            # 只挑认识的键 旧字段直接丢
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
    # 不读环境代理 只认传进来的
    import httpx

    timeout = httpx.Timeout(connect=8.0, read=90.0, write=30.0, pool=8.0)
    proxy = (proxy or "").strip()
    if proxy:
        try:
            # 新版 httpx 用 proxy 老版退回 proxies
            return httpx.Client(proxy=proxy, trust_env=False, timeout=timeout)
        except TypeError:
            return httpx.Client(proxies=proxy, trust_env=False, timeout=timeout)
    return httpx.Client(trust_env=False, timeout=timeout)
