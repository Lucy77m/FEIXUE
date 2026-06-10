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
    """原子写：写一半崩了别留半个坏文件，先写 tmp 再 os.replace 整体换上。"""
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

# 自主度档位 → (单轮最大步数, 单轮最大工具调用数)，越放手给得越宽。
AUTONOMY_BUDGETS = {
    "省心": (12, 30),
    "正常": (24, 100),
    "放手干": (40, 500),
}

# 思考档位 → (是否开 thinking, thinking 预算 token)；max 给 0 表示不设上限。
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
    subagent_model: str = ""  # 留空就跟主 model 走，省得便宜活儿也烧贵模型

    embed_model: str = "text-embedding-3-small"
    proxy: str = ""
    allow_web: bool = True
    allow_control: bool = True
    allow_shell: bool = True
    language: str = "中文"
    temperature: float = 0.7
    max_tokens: int = 0
    history_tokens: int = 24_000  # 历史超这个量就往前截，给当轮上下文腾地方
    autonomy: str = "正常"
    enable_thinking: bool = True
    think_level: str = "medium"
    proactive_enabled: bool = True
    proactive_level: str = "正常"
    ui_language: str = "中文"
    tts_enabled: bool = False
    tts_voice: str = ""
    tts_rate: int = 0
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
            # 只挑认识的键：旧版本遗留字段(如已删的 birthday)直接丢，不然 cls() 会炸
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
    # trust_env=False：别让系统/环境里的代理变量偷偷生效，代理只认这里传进来的
    import httpx

    timeout = httpx.Timeout(connect=8.0, read=90.0, write=30.0, pool=8.0)
    proxy = (proxy or "").strip()
    if proxy:
        try:
            # 新版 httpx 用 proxy=，老版只认 proxies= —— 撞 TypeError 就退回老写法
            return httpx.Client(proxy=proxy, trust_env=False, timeout=timeout)
        except TypeError:
            return httpx.Client(proxies=proxy, trust_env=False, timeout=timeout)
    return httpx.Client(trust_env=False, timeout=timeout)
