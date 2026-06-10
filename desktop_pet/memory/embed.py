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
_DISABLE_COOLDOWN_S = 300.0  # 嵌入接口出岔子(没配 key／网络断／模型名错)就先停 5 分钟，别每条消息都去撞墙

_EMBED_TIMEOUT = 20.0
_EMBED_RETRIES = 1


def _get_client(settings: Settings) -> OpenAI | None:
    """复用同一个 OpenAI 客户端；key/base_url/proxy 任一变了才重建。"""
    global _client, _client_key
    if not settings.api_key:
        return None
    key = (settings.api_key, settings.base_url, settings.proxy)
    if _client is None or _client_key != key:  # 三元组当指纹，用户在设置里改了哪项都能命中重建
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
    """一批文本转向量，失败一律返回 None(交给上层退化成无嵌入模式)，不抛异常。"""
    global _disabled_until
    if not texts:
        return None
    if time.monotonic() < _disabled_until:  # 冷却期内直接放弃，省得反复发请求
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
    except Exception:  # 超时／鉴权／配额都吞掉，进冷却 —— 嵌入挂了不能拖垮主流程
        _disabled_until = time.monotonic() + _DISABLE_COOLDOWN_S
        return None
    return [item.embedding for item in response.data]


def cosine(a: list[float], b: list[float]) -> float:
    """两向量余弦相似度；维度对不上或有零向量都返回 0(当不相关处理)。"""
    if len(a) != len(b):  # 换过嵌入模型／维度不一致的旧向量，直接判 0 别硬算
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def rank_by_cosine(query_vec: list[float], blobs: list[bytes | None], k: int) -> list[int]:
    """检索热路径：和库里每条打包向量算余弦，挑最相近的 k 条(下标按相似度降序)。"""
    dim = len(query_vec)
    try:
        import numpy as np  # 有 numpy 走矩阵一把算完；没装就掉进 except 逐条 cosine

        rows = [(i, np.frombuffer(b, dtype=np.float32)) for i, b in enumerate(blobs) if b]
        rows = [(i, v) for i, v in rows if v.shape[0] == dim]  # 维度不符的(旧模型遗留)直接剔掉
        if not rows:
            return []
        idxs = [i for i, _ in rows]
        mat = np.vstack([v for _, v in rows])
        q = np.asarray(query_vec, dtype=np.float32)
        denom = np.linalg.norm(mat, axis=1) * float(np.linalg.norm(q))
        # where=denom>0：零向量那行的相似度留 0，不让除零冒 nan 把排序搅乱
        sims = np.divide(mat @ q, denom, out=np.zeros(len(idxs), dtype=np.float32), where=denom > 0)
        order = np.argsort(-sims)[:k]  # 取负号变降序，argsort 默认升序
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
    """向量按 float32 序列化成 bytes 存库 —— 比 float64 省一半体积，精度对检索够用。"""
    return array("f", vector).tobytes()


def unpack(blob: bytes | None) -> list[float] | None:
    """pack 的逆操作；必须和 pack 一样用 "f"(float32)，不然 frombytes 字节数对不上会炸。"""
    if not blob:
        return None
    vector = array("f")
    vector.frombytes(blob)
    return vector.tolist()
