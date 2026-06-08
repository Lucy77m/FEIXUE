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
    if time.monotonic() < _disabled_until:
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
    except Exception:
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


def rank_by_cosine(query_vec: list[float], blobs: list[bytes | None], k: int) -> list[int]:
    """在打包向量里挑出与 query_vec 余弦最高的前 k 个，返回其下标(降序)。"""
    dim = len(query_vec)
    try:
        import numpy as np

        rows = [(i, np.frombuffer(b, dtype=np.float32)) for i, b in enumerate(blobs) if b]
        rows = [(i, v) for i, v in rows if v.shape[0] == dim]
        if not rows:
            return []
        idxs = [i for i, _ in rows]
        mat = np.vstack([v for _, v in rows])
        q = np.asarray(query_vec, dtype=np.float32)
        denom = np.linalg.norm(mat, axis=1) * float(np.linalg.norm(q))
        sims = np.divide(mat @ q, denom, out=np.zeros(len(idxs), dtype=np.float32), where=denom > 0)
        order = np.argsort(-sims)[:k]
        return [idxs[int(j)] for j in order]
    except Exception:
        scored = []
        for i, b in enumerate(blobs):
            try:
                v = unpack(b)
            except Exception:
                continue
            if v is not None and len(v) == dim:
                scored.append((cosine(query_vec, v), i))
        scored.sort(key=lambda p: p[0], reverse=True)
        return [i for _, i in scored[:k]]


def pack(vector: list[float]) -> bytes:
    return array("f", vector).tobytes()


def unpack(blob: bytes | None) -> list[float] | None:
    if not blob:
        return None
    vector = array("f")
    vector.frombytes(blob)
    return vector.tolist()
