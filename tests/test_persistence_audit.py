# author: bdth
# email: 2074055628@qq.com
# 板块①持久化重审隐患回归 坏embedding 坏reminders.json skills并发 forget坏库 重入库清陈旧 孤儿tmp
# 全程不碰网络 向量按需造假

from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest


# ---------- 坏 embedding blob 不再崩掉召回 去重 聚类 ----------

def test_unpack_rejects_truncated_blob():
    from desktop_pet.memory.embed import unpack
    assert unpack(b"abc") is None        # 3 字节 非 4 的倍数
    assert unpack(b"") is None
    assert unpack(None) is None
    assert unpack(b"\x00\x00\x80\x3f") == [1.0]  # 合法 4 字节仍正常


def test_cosine_batch_survives_corrupt_blob():
    from desktop_pet.memory.embed import cosine_batch
    good = b"\x00\x00\x80\x3f\x00\x00\x00\x00"  # 1.0 0.0
    # 混入一条 3 字节坏 blob 不该抛 ValueError
    sims = cosine_batch([1.0, 0.0], [good, b"bad", None])
    assert len(sims) == 3
    assert round(sims[0], 3) == 1.0
    assert sims[1] == 0.0 and sims[2] == 0.0


def test_recall_and_remember_survive_corrupt_embedding_row(tmp_path, monkeypatch):
    import desktop_pet.memory.store as store_mod
    from desktop_pet.memory.store import MemoryStore
    monkeypatch.setattr(store_mod, "embed_texts", lambda texts: [[1.0, 0.0, 0.0] for _ in texts])
    m = MemoryStore(tmp_path / "m.db")
    m.remember("正常的一条记忆 关键词苹果")
    # 直接塞一条 embedding 字节数不是 4 的倍数的坏行
    with m._lock:
        m._conn.execute(
            "INSERT INTO experiences(content, ts, confidence, source, embedding, salience, last_seen) "
            "VALUES ('坏行', ?, 1.0, 'x', ?, 0.5, ?)",
            (datetime.now().isoformat(), b"\x01\x02\x03", datetime.now().isoformat()),
        )
        m._conn.commit()
    # 召回再写入 _find_duplicate 会扫到坏行 都不该抛
    out = m.recall_relevant("苹果", k=5)
    assert any("苹果" in c for c in out)
    m.remember("又一条 关键词香蕉")  # 不抛即通过
    m.close()


# ---------- forget 在库损坏时给明确提示 不静默吞 ----------

def test_forget_on_corrupt_db_reports_clearly(tmp_path):
    from desktop_pet.memory.store import MemoryStore
    db = tmp_path / "m.db"
    m = MemoryStore(db)
    m.remember("随便记一条")
    m._conn.close()
    db.write_bytes(b"SQLite format 3\x00" + b"\xff" * 300)  # 头有效 内容损坏
    m._conn = sqlite3.connect(str(db), check_same_thread=False)
    msg = m.forget("随便")
    assert "corrupt" in msg.lower(), f"坏库 forget 该明确提示损坏 而不是静默 得到: {msg}"


# ---------- consolidate 在 close 后不再往关掉的连接写 ----------

def test_wipe_bumps_reset_epoch(tmp_path):
    """重置代数 wipe 自增 普通读写不变"""
    from desktop_pet.memory.store import MemoryStore
    m = MemoryStore(tmp_path / "m.db")
    e0 = m.reset_epoch()
    m.remember("写一条不该改代数")
    assert m.reset_epoch() == e0, "普通写入不该动重置代数"
    m.wipe()
    assert m.reset_epoch() == e0 + 1, "wipe 该让重置代数 +1"
    m.wipe()
    assert m.reset_epoch() == e0 + 2
    m.close()


def test_bump_epoch_invalidates_inflight_writes(tmp_path):
    """换话题 bump_epoch 或重置 wipe 后 带旧代数的反思写入锁内丢弃"""
    from desktop_pet.memory.store import MemoryStore
    m = MemoryStore(tmp_path / "m.db")
    e0 = m.reset_epoch()
    assert "Remembered" in m.remember("带对代数", epoch=e0), "代数一致该正常写"
    m.bump_epoch()  # 模拟换话题
    for call in (lambda: m.remember("x", epoch=e0), lambda: m.set_preference("k", "v", epoch=e0),
                 lambda: m.note_env("k", "v", epoch=e0), lambda: m.add_opinion("o", epoch=e0)):
        assert "reset/topic changed" in call(), "带旧代数的写入该被丢弃"
    # 无 epoch 参数的正常写入不受影响 工具直调路径
    assert "Remembered" in m.remember("普通写不传epoch")
    m.close()


def test_wipe_also_bumps_epoch_for_guard(tmp_path):
    """wipe 同样推进代数 让带旧代数的在途反思写入失效"""
    from desktop_pet.memory.store import MemoryStore
    m = MemoryStore(tmp_path / "m.db")
    e0 = m.reset_epoch()
    m.wipe()
    assert m.reset_epoch() == e0 + 1
    assert "reset/topic changed" in m.add_opinion("旧看法", epoch=e0)
    m.close()


def test_store_writes_skip_when_closing(tmp_path):
    """关库进行中 各写入方法静默跳过 不往已关连接写"""
    from desktop_pet.memory.store import MemoryStore
    m = MemoryStore(tmp_path / "m.db")
    m._closing = True
    for call in (lambda: m.remember("x"), lambda: m.set_preference("k", "v"),
                 lambda: m.note_env("k", "v"), lambda: m.add_opinion("o"),
                 lambda: m.forget("x")):
        assert "shutting down" in call(), "关库中写入该跳过"
    m._closing = False
    assert "Remembered" in m.remember("恢复后正常写")


def test_consolidate_skips_write_after_close(tmp_path, monkeypatch):
    import desktop_pet.memory.store as store_mod
    from desktop_pet.memory.store import MemoryStore
    monkeypatch.setattr(store_mod, "embed_texts", lambda texts: [[1.0, 0.0, 0.0] for _ in texts])
    m = MemoryStore(tmp_path / "m.db")
    m._closing = True  # 模拟 close 已置位
    # 即便伪造出一个簇 consolidate 的锁内段也该因 _closing 早退 不写不抛
    monkeypatch.setattr(m, "_find_clusters", lambda: [[(1, "a"), (2, "b"), (3, "c")]])
    n = m.consolidate(lambda texts: "概括")
    assert n == 0, "关库中不该写入合并结果"
    m.close()


# ---------- reminders.json 坏 id 不再让 app 起不来 ----------

def test_reminders_skips_bad_id_entries(tmp_path, monkeypatch):
    import desktop_pet.reminders as rmod
    monkeypatch.setattr(rmod, "_PATH", tmp_path / "reminders.json")
    fire = datetime.now().isoformat()
    rmod._PATH.write_text(json.dumps([
        {"id": "1.0", "fire_at": fire, "what": "坏id浮点串", "created_at": fire},
        {"id": "abc", "fire_at": fire, "what": "坏id字母", "created_at": fire},
        {"id": None, "fire_at": fire, "what": "坏id null", "created_at": fire},
        {"id": [1], "fire_at": fire, "what": "坏id列表", "created_at": fire},
        {"id": 7, "fire_at": fire, "what": "好的", "created_at": fire},
    ]), encoding="utf-8")
    items = rmod.ReminderStore()._load()  # 不该抛
    assert [i.what for i in items] == ["好的"], "坏 id 的条目该被跳过 只留好的"


# ---------- SkillStore 并发创建不再崩 dictionary changed size ----------

def test_skills_concurrent_create_no_crash(tmp_path, monkeypatch):
    import desktop_pet.skills as skmod
    monkeypatch.setattr(skmod, "_DIR", tmp_path / "skills")
    monkeypatch.setattr(skmod, "_REGISTRY", tmp_path / "skills" / "registry.json")
    store = skmod.SkillStore()
    errs: list[str] = []

    def worker(w: int) -> None:
        try:
            for j in range(25):
                store.create(f"skill_{w}_{j}", "x = 1", f"desc {w}")
                store.listing()
                store.as_context()
                store.count()
        except Exception as exc:  # noqa: BLE001
            errs.append(repr(exc))

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errs, f"并发 create/listing 不该抛: {errs[:3]}"
    assert store.count() == 100


# ---------- 重新入库一个变得不可读 超大的文件 该清掉旧块 ----------

def test_reingest_unreadable_drops_stale_chunks(tmp_path, monkeypatch):
    import desktop_pet.docs as docs_mod
    from desktop_pet.docs import DocStore
    monkeypatch.setattr(docs_mod, "_DB_PATH", tmp_path / "docs.db")
    monkeypatch.setattr(docs_mod, "embed_texts", lambda texts: None)
    kb = DocStore()
    folder = tmp_path / "kb"
    folder.mkdir()
    note = folder / "note.txt"
    note.write_text("原始可读内容 关键词西瓜", encoding="utf-8")
    kb.ingest(str(folder))
    assert "西瓜" in kb.recall("西瓜")
    # 文件变超大 重新入库被跳过 但旧块该被清掉 不再供陈旧
    note.write_text("x" * (docs_mod._MAX_FILE + 10), encoding="utf-8")
    kb.ingest(str(folder))
    assert "西瓜" not in kb.recall("西瓜"), "陈旧旧块该在跳过时被清掉"


# ---------- 孤儿 .tmp 启动清扫 ----------

def test_sweep_stale_tmp_removes_old_only(tmp_path):
    from desktop_pet.settings import sweep_stale_tmp
    old = tmp_path / ".settings.json.deadbeef.tmp"
    fresh = tmp_path / ".persona.json.cafe.tmp"
    old.write_text("x", encoding="utf-8")
    fresh.write_text("y", encoding="utf-8")
    # 把 old 的 mtime 拨到 10 分钟前
    past = time.time() - 600
    import os
    os.utime(old, (past, past))
    sweep_stale_tmp(tmp_path, max_age_s=300.0)
    assert not old.exists(), "够旧的孤儿 tmp 该被清"
    assert fresh.exists(), "刚写的 tmp 不该动"
