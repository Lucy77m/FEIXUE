# author: bdth
# email: 2074055628@qq.com
# 文本向量化(嵌入)模块:调用 OpenAI 接口生成文本向量,并提供余弦相似度与向量打包/解包工具

from __future__ import annotations

import math
import time
from array import array

from openai import OpenAI

from desktop_pet.settings import Settings, build_http_client

_client: OpenAI | None = None
_client_key: tuple[str, str, str] | None = None
# 之前是个永不复位的布尔：一次失败（缺 key / 限流 / 网络抖）后整个进程永久退化成子串检索，
# API 恢复也不会自愈。改成冷却时间戳：失败后只静默冷却一段时间，过后自动重试、自己复活。
_disabled_until = 0.0
_DISABLE_COOLDOWN_S = 300.0

_EMBED_TIMEOUT = 20.0
_EMBED_RETRIES = 1


def _get_client(settings: Settings) -> OpenAI | None:
    global _client, _client_key
    if not settings.api_key:
        return None
    key = (settings.api_key, settings.base_url, settings.proxy)
    if _client is None or _client_key != key:
        _client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=_EMBED_TIMEOUT,
            max_retries=_EMBED_RETRIES,
            http_client=build_http_client(settings.proxy),
        )
        _client_key = key
    return _client


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    global _disabled_until
    if not texts:
        return None
    if time.monotonic() < _disabled_until:  # 还在冷却期，先用降级检索，过后再试
        return None
    settings = Settings.load()
    if not settings.api_key or not settings.embed_model:
        _disabled_until = time.monotonic() + _DISABLE_COOLDOWN_S
        return None
    client = _get_client(settings)
    if client is None:
        _disabled_until = time.monotonic() + _DISABLE_COOLDOWN_S
        return None
    try:
        response = client.embeddings.create(model=settings.embed_model, input=texts)
    except Exception:  # noqa: BLE001
        _disabled_until = time.monotonic() + _DISABLE_COOLDOWN_S
        return None
    return [item.embedding for item in response.data]


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def pack(vector: list[float]) -> bytes:
    return array("f", vector).tobytes()


def unpack(blob: bytes | None) -> list[float] | None:
    if not blob:
        return None
    vector = array("f")
    vector.frombytes(blob)
    return vector.tolist()
