# author: bdth
# email: 2074055628@qq.com
# 板块⑤ 伴生行为重审隐患回归——somatic 跨线程迭代加锁;docs 关库中入库不写已关连接

from __future__ import annotations

import threading


# ---------- somatic:worker 读 context 时主线程狂写 不该 RuntimeError ----------

def test_somatic_concurrent_note_and_context():
    import desktop_pet.somatic as somatic
    somatic.clear()
    errors: list[str] = []
    stop = [False]

    def churn() -> None:
        i = 0
        while not stop[0]:
            try:
                somatic.note(f"事件{i}")
                somatic.set_state("k", f"状态{i}")
                somatic.set_state("k2", None)
                i += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))
                break

    t = threading.Thread(target=churn, daemon=True)
    t.start()
    try:
        for _ in range(4000):
            somatic.context()  # 加锁前这里会撞 deque/dict changed size during iteration
    finally:
        stop[0] = True
        t.join(timeout=1.0)
        somatic.clear()
    assert not errors, f"并发读写 somatic 不该抛: {errors[:3]}"


# ---------- docs:关库进行中 入库静默跳过 不写已关连接 ----------

def test_docs_ingest_skips_when_closing(tmp_path, monkeypatch):
    import desktop_pet.docs as docs_mod
    from desktop_pet.docs import DocStore
    monkeypatch.setattr(docs_mod, "_DB_PATH", tmp_path / "docs.db")
    monkeypatch.setattr(docs_mod, "embed_texts", lambda texts: None)
    ds = DocStore()
    folder = tmp_path / "kb"
    folder.mkdir()
    (folder / "a.txt").write_text("关键词菠萝", encoding="utf-8")

    ds._closing = True  # 模拟 close() 已置位
    ds._ingest_file(folder / "a.txt", 100)  # 锁内段该早退 不写
    assert ds.count() == 0, "关库中不该写入 chunks"

    ds._closing = False
    ds.ingest(str(folder))
    assert ds.count() >= 1, "恢复后正常入库"
    ds.close()
