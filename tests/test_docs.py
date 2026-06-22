# 知识库混合召回测试 trigram字面路补向量盲区 多语言 删除同步 老库回填
# 直接插chunk绕开文件读取 向量按需造假 不碰网络

from __future__ import annotations

import math

import pytest

import desktop_pet.docs as docs_mod
from desktop_pet.docs import DocStore


def _unit(x, y, z):
    n = math.sqrt(x * x + y * y + z * z)
    return [x / n, y / n, z / n]


@pytest.fixture()
def kb(tmp_path, monkeypatch):
    monkeypatch.setattr(docs_mod, "_DB_PATH", tmp_path / "docs.db")
    monkeypatch.setattr(docs_mod, "embed_texts", lambda texts: None)  # 默认无向量 只测字面路
    return DocStore()


def _add(kb, source, chunks):
    with kb._lock:
        for i, c in enumerate(chunks):
            kb._conn.execute(
                "INSERT INTO chunks(source, idx, content, embedding) VALUES (?, ?, ?, NULL)",
                (source, i, c))
        kb._conn.commit()


def test_fts_recall_multilingual(kb):
    _add(kb, "manual.md", [
        "安装时如果报 ModuleNotFoundError 先检查虚拟环境",
        "数据库连接字符串配置在 settings.yaml 里",
        "The CLI flag --verbose enables debug logging",
        "ポート8080がすでに使用されています",
        "周末团建去哪里玩还没定",
    ])
    out = kb.recall("ModuleNotFoundError 怎么办")
    assert "ModuleNotFoundError" in out
    out = kb.recall("settings.yaml 在哪")
    assert "settings.yaml" in out
    out = kb.recall("--verbose flag")
    assert "verbose" in out
    out = kb.recall("8080 ポート")
    assert "8080" in out


def test_recall_empty_kb(kb):
    assert "empty" in kb.recall("anything")


def test_fts_sync_on_forget(kb):
    _add(kb, "a.md", ["唯一标识符 zzztoken 出现在这"])
    _add(kb, "b.md", ["无关内容一", "无关内容二"])
    assert "zzztoken" in kb.recall("zzztoken")
    kb.forget("a.md")
    assert "zzztoken" not in kb.recall("zzztoken"), "删文档后FTS该同步 不再召回"


def test_fts_backfill_existing(tmp_path, monkeypatch):
    monkeypatch.setattr(docs_mod, "_DB_PATH", tmp_path / "docs.db")
    monkeypatch.setattr(docs_mod, "embed_texts", lambda texts: None)
    kb1 = DocStore()
    _add(kb1, "old.md", ["历史文档提到 RuntimeError 复现步骤", "其它无关"])
    kb1._conn.close()
    kb2 = DocStore()  # 重开触发回填
    assert "RuntimeError" in kb2.recall("RuntimeError"), "重开后历史chunk该被FTS回填"


def test_hybrid_fuses_vector_and_fts(tmp_path, monkeypatch):
    # 向量路把目标排在很后 字面路精确命中 RRF融合后该冒头
    vmap = {
        "用户指南第一章 介绍": _unit(1.0, 0.0, 0.0),
        "用户指南第二章 配置": _unit(0.0, 1.0, 0.0),
        "故障排查 EADDRINUSE 端口占用": _unit(0.0, 0.0, 1.0),
        "用户指南第三章 进阶": _unit(1.0, 1.0, 0.0),
        "EADDRINUSE 怎么解决": _unit(0.9, 0.9, 0.2),  # query 偏向前面几条
    }
    monkeypatch.setattr(docs_mod, "_DB_PATH", tmp_path / "docs.db")
    monkeypatch.setattr(docs_mod, "embed_texts",
                        lambda texts: [vmap.get(t, _unit(1.0, 1.0, 1.0)) for t in texts])
    kb = DocStore()
    with kb._lock:
        for i, c in enumerate(list(vmap)[:4]):
            kb._conn.execute(
                "INSERT INTO chunks(source, idx, content, embedding) VALUES (?, ?, ?, ?)",
                ("g.md", i, c, docs_mod.pack(vmap[c])))
        kb._conn.commit()
    out = kb.recall("EADDRINUSE 怎么解决", k=2)
    assert "EADDRINUSE" in out, f"字面路该把端口错误那条融合上来 实际{out}"
