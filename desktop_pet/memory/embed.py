# author: bdth
# email: 2074055628@qq.com
# 文本嵌入 调openai生成向量 带余弦相似度和打包工具

from __future__ import annotations

import math
import threading
import time
from array import array

from openai import OpenAI

from desktop_pet.settings import Settings, build_http_client

_client: OpenAI | None = None
_client_key: tuple[str, str, str] | None = None
_client_lock = threading.Lock()  # 序列化 client 首建/重建——多线程(worker/反思/合并/入库daemon)并发首调时防重复造 client 漏掉 httpx 连接池
_disabled_until = 0.0
_DISABLE_COOLDOWN_S = 300.0  # 嵌入出错冷却5分钟

_EMBED_TIMEOUT = 20.0
_EMBED_RETRIES = 1


def _get_client(settings: Settings) -> OpenAI | None:
    """复用openai客户端 配置变了才重建"""
    global _client, _client_key
    if not settings.api_key:
        return None
    key = (settings.api_key, settings.base_url, settings.proxy)
    with _client_lock:  # 加锁:两个线程同时见 _client is None 各造一个 后者覆盖前者会漏掉前者的 httpx client
        if _client is None or _client_key != key:
            if _client is not None:  # 配置变了 先关掉旧 client 的 httpx 连接池 别漏 socket/句柄
                try:
                    _client.close()
                except Exception:
                    pass
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
    """一批文本转向量 失败返回None不抛"""
    global _disabled_until
    if not texts:
        return None
    if time.monotonic() < _disabled_until:  # 冷却期内直接放弃
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
    except Exception:  # 出错吞掉进冷却
        _disabled_until = time.monotonic() + _DISABLE_COOLDOWN_S
        return None
    return [item.embedding for item in response.data]


def cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度 维度不符或零向量返回0"""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def cosine_batch(query_vec: list[float], blobs: list[bytes | None]) -> list[float]:
    """一次算query对一批blob的余弦 维度不符或空blob给0 有numpy走矩阵没有退逐条
    返回长度与blobs一致 顺序对齐 调用方拿去和阈值比"""
    dim = len(query_vec)
    n = len(blobs)
    try:
        import numpy as np

        sims = [0.0] * n
        idxs, vecs = [], []
        for i, b in enumerate(blobs):
            if not b or len(b) % 4:  # 空或截断(长度非4倍数)的blob跳过 别让np.frombuffer抛
                continue
            v = np.frombuffer(b, dtype=np.float32)
            if v.shape[0] == dim:
                idxs.append(i)
                vecs.append(v)
        if not idxs:
            return sims
        mat = np.vstack(vecs)
        q = np.asarray(query_vec, dtype=np.float32)
        denom = np.linalg.norm(mat, axis=1) * float(np.linalg.norm(q))
        batch = np.divide(mat @ q, denom, out=np.zeros(len(idxs), dtype=np.float32), where=denom > 0)
        for j, i in enumerate(idxs):
            sims[i] = float(batch[j])
        return sims
    except Exception:
        out = []
        for b in blobs:
            v = unpack(b)
            out.append(cosine(query_vec, v) if (v is not None and len(v) == dim) else 0.0)
        return out


def rank_by_cosine(query_vec: list[float], blobs: list[bytes | None], k: int) -> list[int]:
    """按余弦挑最相近的k条下标"""
    dim = len(query_vec)
    try:
        import numpy as np  # 有numpy走矩阵 没装退逐条cosine

        rows = [(i, np.frombuffer(b, dtype=np.float32)) for i, b in enumerate(blobs) if b and not len(b) % 4]
        rows = [(i, v) for i, v in rows if v.shape[0] == dim]  # 维度不符的剔掉
        if not rows:
            return []
        idxs = [i for i, _ in rows]
        mat = np.vstack([v for _, v in rows])
        q = np.asarray(query_vec, dtype=np.float32)
        denom = np.linalg.norm(mat, axis=1) * float(np.linalg.norm(q))
        # 零向量留0防除零
        sims = np.divide(mat @ q, denom, out=np.zeros(len(idxs), dtype=np.float32), where=denom > 0)
        order = np.argsort(-sims)[:k]  # 取负变降序
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
    """向量按float32序列化成bytes"""
    return array("f", vector).tobytes()


def unpack(blob: bytes | None) -> list[float] | None:
    """bytes还原成向量 长度不是4的倍数(截断/字节级损坏)当None跳过
    别让一条坏blob抛 ValueError 崩掉召回/去重/聚类/反思整条链"""
    if not blob or len(blob) % 4:
        return None
    vector = array("f")
    vector.frombytes(blob)
    return vector.tolist()
