# author: bdth
# email: 2074055628@qq.com
# 记忆系统行为测试 遗忘曲线 召回强化 同主题降权 容量上限
# 向量全部用手造的假embedding 不碰网络

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest

import desktop_pet.memory.store as store_mod
from desktop_pet.memory.store import (
    MemoryStore,
    _DEDUP_COSINE,
    _MAX_EXPERIENCES,
    _RELATED_COSINE,
    _effective_salience,
)


def _unit(x: float, y: float, z: float) -> list[float]:
    n = math.sqrt(x * x + y * y + z * z)
    return [x / n, y / n, z / n]


# 文本到假向量的字典 余弦关系都是算好的
_FAKE_VECS = {
    "我平时用npm管包": _unit(1.0, 0.0, 0.0),
    "我换pnpm了 以后别用npm": _unit(0.86, 0.51, 0.0),   # 与上一条cos约0.86 同主题非重复
    "今天天气很好": _unit(0.0, 0.0, 1.0),                  # 不相干
    "查询包管理器": _unit(0.98, 0.2, 0.0),                 # 接近npm那条的查询
    "查询天气": _unit(0.0, 0.1, 0.99),
}


@pytest.fixture()
def mem(tmp_path, monkeypatch):
    def fake_embed(texts):
        out = []
        for t in texts:
            v = _FAKE_VECS.get(t)
            if v is None:
                return None  # 不认识的文本当嵌入失败
            out.append(v)
        return out
    monkeypatch.setattr(store_mod, "embed_texts", fake_embed)
    return MemoryStore(tmp_path / "m.db")


def _set_meta(mem, content_like, *, days_ago=None, salience=None):
    """直接改库里某条的last_seen或salience 模拟时间流逝"""
    if days_ago is not None:
        stamp = (datetime.now() - timedelta(days=days_ago)).isoformat(timespec="seconds")
        mem._conn.execute("UPDATE experiences SET last_seen = ? WHERE content LIKE ?",
                          (stamp, f"%{content_like}%"))
    if salience is not None:
        mem._conn.execute("UPDATE experiences SET salience = ? WHERE content LIKE ?",
                          (salience, f"%{content_like}%"))
    mem._conn.commit()


def _row(mem, content_like):
    return mem._conn.execute(
        "SELECT salience, recall_count, last_seen FROM experiences WHERE content LIKE ?",
        (f"%{content_like}%",),
    ).fetchone()


def test_decay_math():
    now = datetime.now()
    fresh = now.isoformat(timespec="seconds")
    old = (now - timedelta(days=90)).isoformat(timespec="seconds")
    # 刚写的不掉血
    assert _effective_salience(0.8, fresh, now) == pytest.approx(0.8, abs=0.01)
    # 高显著性90天掉一半左右 半衰期到不了即大于四分之一
    assert 0.3 < _effective_salience(0.8, old, now) < 0.5
    # 低显著性同样90天几乎沉底
    assert _effective_salience(0.2, old, now) < 0.05
    # 坏时间戳不炸 原样返回
    assert _effective_salience(0.5, "garbage", now) == 0.5


def test_supersede_related_demotes_old(mem):
    mem.remember("我平时用npm管包", salience=0.6)
    # 确认假向量的关系落在降权带里
    a, b = _FAKE_VECS["我平时用npm管包"], _FAKE_VECS["我换pnpm了 以后别用npm"]
    sim = sum(x * y for x, y in zip(a, b))
    assert _RELATED_COSINE <= sim < _DEDUP_COSINE
    mem.remember("我换pnpm了 以后别用npm", salience=0.6)
    old_sal = _row(mem, "npm管包")[0]
    new_sal = _row(mem, "pnpm")[0]
    assert old_sal < 0.6 * 0.7, f"旧条目该被降权 实际{old_sal}"
    assert new_sal == pytest.approx(0.6)
    assert mem.count() == 2  # 降权不是删除


def test_recall_reinforces_hits(mem):
    mem.remember("我平时用npm管包", salience=0.5)
    mem.remember("今天天气很好", salience=0.5)
    out = mem.recall_relevant("查询包管理器", k=1)
    assert out == ["我平时用npm管包"]
    sal, cnt, _ls = _row(mem, "npm管包")
    assert cnt == 1 and sal > 0.5, "真命中该回血"
    # 不相干的那条不被强化
    sal2, cnt2, _ls2 = _row(mem, "天气很好")
    assert cnt2 == 0 and sal2 == pytest.approx(0.5)


def test_stale_memory_sinks(mem):
    mem.remember("我平时用npm管包", salience=0.5)
    mem.remember("今天天气很好", salience=0.5)
    # npm那条被冷落一年 天气是新鲜的 用一个对两边相似度都不高的查询
    _set_meta(mem, "npm管包", days_ago=365)
    out = mem.recall_relevant("查询天气", k=1)
    assert out == ["今天天气很好"]


def test_overflow_prunes_least_salient(mem, monkeypatch):
    monkeypatch.setattr(store_mod, "_MAX_EXPERIENCES", 5)
    # 绕开remember的嵌入路径 直接插无向量条目
    for i in range(5):
        with mem._lock:
            mem._insert_experience(f"条目{i}独特内容标记{i}xyzw", ts=store_mod._now(),
                                   confidence=1.0, source="t", vector=None, salience=0.1 * (i + 1))
            mem._conn.commit()
    assert mem.count() == 5
    with mem._lock:
        mem._insert_experience("第六条挤进来的重要内容qrst", ts=store_mod._now(),
                               confidence=1.0, source="t", vector=None, salience=0.9)
        mem._conn.commit()
    assert mem.count() == 5, "超限后该裁回上限"
    contents = mem.recent_experiences(10)
    assert not any("条目0" in c for c in contents), "显著性最低的该先被裁"
    assert any("第六条" in c for c in contents)


def test_cosine_batch_matches_scalar():
    from desktop_pet.memory.embed import cosine, cosine_batch, pack
    q = _unit(1.0, 0.2, 0.0)
    vecs = [_unit(1.0, 0.0, 0.0), _unit(0.0, 1.0, 0.0), _unit(0.5, 0.5, 0.5)]
    blobs = [pack(v) for v in vecs] + [None, b""]  # 混进空blob
    out = cosine_batch(q, blobs)
    assert len(out) == len(blobs)
    for v, got in zip(vecs, out[:3]):
        assert got == pytest.approx(cosine(q, v), abs=1e-5)
    assert out[3] == 0.0 and out[4] == 0.0  # 空blob给0
    # 维度不符也给0不炸
    assert cosine_batch(q, [pack([1.0, 2.0])]) == [0.0]


def test_dedup_still_works(mem):
    mem.remember("我平时用npm管包", salience=0.3)
    out = mem.remember("我平时用npm管包", salience=0.8)
    assert "updated" in out or "similar" in out
    assert mem.count() == 1
    assert _row(mem, "npm管包")[0] == pytest.approx(0.8), "重复写入显著性取max"


# 记忆合并 一簇同主题且互不重复的经验 两两余弦落在related带[0.80,0.92)里
# 不能太像 否则remember时被当重复合掉 三个偏移0.32在yz面120度分开 两两cos约0.86
_THEME_VECS = {
    "周一要交方案 时间紧": _unit(1.0, 0.32, 0.0),
    "又熬夜赶活到两点": _unit(1.0, -0.16, 0.277),
    "压力大 这周没睡好": _unit(1.0, -0.16, -0.277),
    "周末去爬山很开心": _unit(0.0, 0.0, 1.0),  # 不相干 不该进簇
}


@pytest.fixture()
def mem_theme(tmp_path, monkeypatch):
    def fake_embed(texts):
        out = []
        for t in texts:
            v = _THEME_VECS.get(t)
            out.append(v if v is not None else _unit(0.5, 0.5, 0.5))  # 概括也给个向量
        return out
    monkeypatch.setattr(store_mod, "embed_texts", fake_embed)
    return MemoryStore(tmp_path / "t.db")


def test_consolidation_merges_theme(mem_theme):
    for t in _THEME_VECS:
        mem_theme.remember(t, salience=0.4)
    # 确认三条赶工两两落在related带里 成簇但不会在remember时被当重复合掉
    vs = [_THEME_VECS[t] for t in list(_THEME_VECS)[:3]]
    for i in range(3):
        for j in range(i + 1, 3):
            sim = sum(x * y for x, y in zip(vs[i], vs[j]))
            assert store_mod._CLUSTER_COSINE <= sim < store_mod._DEDUP_COSINE, f"{i},{j} sim={sim}"
    assert mem_theme.count() == 4, "四条都该独立存下来 没被去重合并"

    calls = {"n": 0}
    def summarize(texts):
        calls["n"] += 1
        assert all("爬山" not in t for t in texts), "不相干的不该进簇"
        return "主人最近在高压赶工期 常熬夜没睡好"
    n = mem_theme.consolidate(summarize)
    assert n == 1, "三条赶工该揉成一簇"
    assert calls["n"] == 1
    # 概括以高显著性入库
    summ = _row(mem_theme, "高压赶工")
    assert summ is not None and summ[0] == pytest.approx(0.7)
    # 原始三条被标记consolidated并降权 具体显著性supersede也插过手 只断言降了和标记到位
    done = mem_theme._conn.execute(
        "SELECT COUNT(*) FROM experiences WHERE consolidated = 1").fetchone()[0]
    assert done == 3
    assert _row(mem_theme, "周一要交方案")[0] < 0.4, "原始条目该被降权沉底"
    # 不相干的那条没被动
    assert mem_theme._conn.execute(
        "SELECT consolidated FROM experiences WHERE content LIKE '%爬山%'").fetchone()[0] == 0


def test_consolidation_idempotent(mem_theme):
    for t in _THEME_VECS:
        mem_theme.remember(t, salience=0.4)
    mem_theme.consolidate(lambda texts: "概括一")
    # 再跑一次 原始条目已标consolidated 不该再成簇
    n2 = mem_theme.consolidate(lambda texts: "不该被调用")
    assert n2 == 0, "揉过的不该重复揉"


def test_consolidation_respects_none(mem_theme):
    for t in _THEME_VECS:
        mem_theme.remember(t, salience=0.4)
    # summarize回空串模拟模型判NONE 该簇放弃 原始条目不标记
    n = mem_theme.consolidate(lambda texts: "")
    assert n == 0
    done = mem_theme._conn.execute(
        "SELECT COUNT(*) FROM experiences WHERE consolidated = 1").fetchone()[0]
    assert done == 0, "没揉成就不该标记 留待下次"


def test_consolidation_needs_min_size(mem_theme):
    # 只放两条赶工 不够CLUSTER_MIN(3) 不成簇
    for t in list(_THEME_VECS)[:2]:
        mem_theme.remember(t, salience=0.4)
    n = mem_theme.consolidate(lambda texts: "不该被调用")
    assert n == 0
