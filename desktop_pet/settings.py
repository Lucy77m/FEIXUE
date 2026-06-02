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
    """原子写文本：先写唯一临时文件再 os.replace 覆盖目标。
    避免进程在写到一半时被杀（反思是 fire-and-forget daemon、退出走 os._exit），
    留下半截 / 损坏的 JSON 让下次启动读不出来。临时名带 uuid，多线程同写同一文件也不会撞 tmp。"""
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
    """开发期用项目内 data/；PyInstaller 打包后改用用户可写的 %APPDATA%/Mochi
    （打包后 __file__ 落在临时/只读目录，不能拿来存配置与记忆）；STAR_DATA_DIR 始终可覆盖。"""
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

THINK_LEVELS = ("off", "low", "medium", "high", "max")
# 思考档位 → (enable_thinking, max_tokens)。无=关思考最快；低/中/高=开思考、回复渐长；MAX=开思考且不限长度。
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
    max_steps: int = 16
    enable_thinking: bool = True
    think_level: str = "medium"
    proactive_enabled: bool = True
    proactive_level: str = "正常"
    ui_language: str = "中文"
    tts_enabled: bool = False  # 朗读(TTS)：默认关，避免突然出声；控制面板「对话」页可开
    birthday: str = ""  # 你的生日 MM-DD，留空=不过；用于节日/生日特殊表现
    watch_screen: bool = False  # 看屏主动帮手：默认关(会偶尔截屏判断你是否卡住)
    clip_sampler: bool = False  # 剪贴板采样器：监听复制内容做本地分类（炼金术/recall 的底座），隐私默认关
    clip_alchemy: bool = False  # 剪贴板炼金术：复制到报错/外文/代码时主动冒泡帮你解释/翻译/改好
    clip_alchemy_kinds: str = "error,foreign,code"  # 炼金术处理哪些类别（逗号分隔：error/foreign/code/url）
    quick_paste_back: bool = True  # 顺手就改：改写后自动 Ctrl+V 粘贴替换（关掉则只放进剪贴板）
    hotkey_summon: str = "ctrl+alt+s"    # 全局热键：唤出 MOCHI + 输入框
    hotkey_ask: str = "ctrl+alt+a"       # 全局热键：选中文字问它
    hotkey_quick: str = "ctrl+shift+q"   # 全局热键：顺手就改（选中文字一键改写）

    @classmethod
    def load(cls) -> Settings:
        if not SETTINGS_PATH.exists():
            return cls()
        # 损坏/被占用/非 dict 一律退回出厂默认(api_key 空 → 启动会弹控制面板让用户重配)，
        # 绝不让坏掉的 settings.json 直接崩 PetApp 启动。
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
    """按代理设置造一个 httpx.Client 给 OpenAI 客户端用。
    留空＝直连且 trust_env=False（无视系统/环境里的 *_PROXY，免得国内接口被乱代理劫持）；
    填了＝只走这个代理。
    超时细分：连不上就 8s 快速失败，别让坏网/坏配置把请求线程卡到天荒地老。"""
    import httpx

    timeout = httpx.Timeout(connect=8.0, read=90.0, write=30.0, pool=8.0)
    proxy = (proxy or "").strip()
    if proxy:
        try:
            return httpx.Client(proxy=proxy, trust_env=False, timeout=timeout)
        except TypeError:  # 老版本 httpx 用 proxies=
            return httpx.Client(proxies=proxy, trust_env=False, timeout=timeout)
    return httpx.Client(trust_env=False, timeout=timeout)
