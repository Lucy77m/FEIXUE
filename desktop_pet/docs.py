# 文档知识库 抽取文本pdf切块向量化入库 供语义召回

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from desktop_pet.memory.embed import cosine_batch, embed_texts, pack
from desktop_pet.memory.hybrid import fts_query, rrf_fuse
from desktop_pet.settings import DATA_DIR, delete_db_files

_DB_PATH = DATA_DIR / "docs.db"
_CHUNK = 800
_OVERLAP = 120
_MAX_FILE = 600_000
_MAX_CHUNKS = 4000
_EMBED_BATCH = 32
_RECALL_K = 5
_RECALL_POOL = 30      # 两路各召回这么多候选 再RRF融合
_TEXT_EXT = frozenset(
    {".txt", ".md", ".rst", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml",
     ".html", ".csv", ".tex", ".log", ".ini", ".cfg", ".java", ".go", ".rs", ".c",
     ".cpp", ".h", ".sql", ".sh", ".vue", ".xml"}
)
_DOC_EXT = _TEXT_EXT | {".pdf"}
_IGNORE_DIRS = frozenset({".venv", "venv", "__pycache__", ".git", "node_modules", "dist", "build"})
_PDF_TEXT_MIN = 16


def _read_text(file: Path) -> str | None:
    """读纯文本 多编码依次试 都不行强解兜底"""
    try:
        raw = file.read_bytes()
    except OSError:
        return None
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _read_pdf(file: Path) -> str | None:
    """提取pdf文字 扫描页走ocr"""
    try:
        import pymupdf
    except ImportError:
        return None
    try:
        doc = pymupdf.open(str(file))
    except Exception:
        return None
    parts: list[str] = []
    try:
        for page in doc:
            text = page.get_text().strip()
            if len(text) >= _PDF_TEXT_MIN:
                parts.append(text)
            else:
                ocr = _ocr_pdf_page(page)
                if ocr:
                    parts.append(ocr)
    finally:
        doc.close()
    joined = "\n\n".join(parts).strip()
    return joined or None


def _ocr_pdf_page(page) -> str:
    """扫描页渲成位图走ocr"""
    try:
        import numpy as np

        from desktop_pet.executor import vision

        pix = page.get_pixmap(dpi=200)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n >= 3:
            bgr = arr[:, :, 2::-1].copy()
        else:
            bgr = np.repeat(arr[:, :, :1], 3, axis=2).copy()
        boxes = vision.ocr_boxes(bgr, 0, 0)
    except Exception:
        return ""
    # 按行再按x排 还原阅读顺序
    boxes.sort(key=lambda b: (round(b["center_abs"][1] / 12), b["center_abs"][0]))
    return " ".join(b["text"] for b in boxes)


def _chunk_text(text: str) -> list[str]:
    """按段落攒块 超长段落硬切带重叠"""
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    buffer = ""
    for para in (p.strip() for p in text.split("\n\n") if p.strip()):
        if len(para) > _CHUNK:  # 超长段先收buffer再硬切
            if buffer:
                chunks.append(buffer)
                buffer = ""
            for i in range(0, len(para), _CHUNK - _OVERLAP):
                chunks.append(para[i : i + _CHUNK])
        elif len(buffer) + len(para) + 2 <= _CHUNK:
            buffer = f"{buffer}\n\n{para}" if buffer else para
        else:
            chunks.append(buffer)
            buffer = para
    if buffer:
        chunks.append(buffer)
    return chunks


class DocStore:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._closing = False  # close 置位 在途入库 daemon 别往已关连接写
        self._conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        self._fts = False
        try:
            self._create_schema()
            self._setup_fts()
        except sqlite3.DatabaseError:
            self._rebuild()  # 库损坏就重建空库 别让 app 起不来

    def _create_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS chunks ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, "
                "idx INTEGER NOT NULL, content TEXT NOT NULL, embedding BLOB)"
            )
            self._conn.commit()

    def _rebuild(self) -> None:
        """库损坏时删文件重建空库 损坏后照样能起能清 对齐 MemoryStore._rebuild"""
        try:
            self._conn.close()
        except Exception:
            pass
        self._conn = None  # 丢掉死连接引用 否则 delete_db_files 里的 gc 收不掉它 unlink 必失败
        delete_db_files(_DB_PATH)
        self._conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        self._fts = False
        self._create_schema()
        self._setup_fts()

    def _setup_fts(self) -> None:
        """给chunk内容建trigram全文索引 triggers跟chunks表同步 没FTS5就退化纯向量"""
        try:
            with self._lock:
                self._conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5("
                    "content, content='chunks', content_rowid='id', tokenize='trigram')"
                )
                self._conn.executescript(
                    """
                    CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                        INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
                    END;
                    CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                        INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES('delete', old.id, old.content);
                    END;
                    CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE OF content ON chunks BEGIN
                        INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES('delete', old.id, old.content);
                        INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
                    END;
                    """
                )
                fts_n = self._conn.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
                ch_n = self._conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
                if fts_n == 0 and ch_n > 0:
                    self._conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
                self._conn.commit()
            self._fts = True
        except sqlite3.OperationalError:
            self._fts = False

    def _fts_search(self, query: str, pool: int) -> list[int]:
        """字面路 trigram召回一批chunk id 按bm25排"""
        if not self._fts:
            return []
        match = fts_query(query)
        if not match:
            return []
        try:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? "
                    "ORDER BY bm25(chunks_fts) LIMIT ?", (match, pool)
                ).fetchall()
            return [int(r[0]) for r in rows]
        except sqlite3.OperationalError:
            return []

    def ingest(self, path: str) -> str:
        """文件或目录入库 目录递归收并跳过忽略目录"""
        target = Path(path).expanduser()
        if not target.exists():
            return f"[path doesn't exist: {path}]"
        files = [target] if target.is_file() else [
            f for f in sorted(target.rglob("*"))
            if f.is_file() and f.suffix.lower() in _DOC_EXT
            and not any(part in _IGNORE_DIRS for part in f.parts)
        ]
        if not files:
            return f"[no readable text files under {path}]"
        total_chunks, done_files, skipped = 0, 0, 0
        for file in files:
            if total_chunks >= _MAX_CHUNKS:  # 全局封顶
                skipped += 1
                continue
            added = self._ingest_file(file, _MAX_CHUNKS - total_chunks)
            if added < 0:  # 读不出时记skip
                skipped += 1
            else:
                total_chunks += added
                done_files += 1
        tail = f", {skipped} file(s) skipped (too big / unreadable / over cap)" if skipped else ""
        return f"Ingested {done_files} file(s), {total_chunks} chunks into the knowledge base{tail}."

    def _drop_source(self, source: str) -> None:
        """清掉某来源的旧块 文件读不出或超大了 别让 recall 继续供陈旧内容"""
        with self._lock:
            self._conn.execute("DELETE FROM chunks WHERE source = ?", (source,))
            self._conn.commit()

    def _source_has_embeddings(self, source: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM chunks WHERE source = ? AND embedding IS NOT NULL LIMIT 1", (source,)
            ).fetchone()
        return row is not None

    def _ingest_file(self, file: Path, budget: int) -> int:
        """单文件入库返回chunk数 读不出返回负数"""
        source = str(file)
        text = _read_pdf(file) if file.suffix.lower() == ".pdf" else _read_text(file)
        if text is None or len(text) > _MAX_FILE:
            self._drop_source(source)  # 同名文件曾入库 现在读不出或超大 清掉旧块 别留陈旧知识
            return -1
        chunks = _chunk_text(text)[:budget]  # 超出剩余配额截断
        if not chunks:
            self._drop_source(source)
            return -1
        # 先无锁把所有块算好 embedding 是几十秒的网络慢活
        # 绝不能持锁做 否则主线程的 docs.sources count 会卡在锁上 整个 ui 冻住
        prepared: list[tuple] = []
        any_ok = False   # 这次至少有一批拿到了真向量
        any_fail = False  # 这次至少有一批没拿到 嵌入进了冷却
        for start in range(0, len(chunks), _EMBED_BATCH):
            batch = chunks[start : start + _EMBED_BATCH]
            vectors = embed_texts(batch)
            if not vectors or len(vectors) != len(batch):  # 向量化挂了也照样存内容
                vectors = [None] * len(batch)
                any_fail = True
            else:
                any_ok = True
            for offset, (content, vector) in enumerate(zip(batch, vectors)):
                prepared.append((source, start + offset, content, pack(vector) if vector else None))
        # 部分嵌入时别拿半成品覆盖掉之前已全嵌入的旧块
        # 保留旧块 等嵌入恢复后重新入库补全 首次入库则照常存
        if any_ok and any_fail and self._source_has_embeddings(source):
            return -1
        # 短事务 锁内只做删旧块加批量插新块 不碰网络
        with self._lock:
            if self._closing:  # 退出已开始关库 别往即将关掉的连接写 投喂入库的 daemon 没被 join 可能晚到这
                return -1
            self._conn.execute("DELETE FROM chunks WHERE source = ?", (source,))
            self._conn.executemany(
                "INSERT INTO chunks(source, idx, content, embedding) VALUES (?, ?, ?, ?)", prepared
            )
            self._conn.commit()
        return len(chunks)

    def recall(self, query: str, k: int = _RECALL_K) -> str:
        """混合召回 向量语义和trigram字面两路RRF融合 断网或没命中逐级兜底"""
        query = (query or "").strip()
        if not query:
            return "(no search query given)"
        with self._lock:
            rows = self._conn.execute("SELECT id, source, content, embedding FROM chunks").fetchall()
        if not rows:
            return "(the knowledge base is empty — ingest some documents first with ingest_docs)"
        by_id = {cid: (source, content) for cid, source, content, _b in rows}
        ids = [cid for cid, *_ in rows]

        # 向量路 余弦排名取候选池
        vec_rank: list[int] = []
        vectors = embed_texts([query])
        query_vec = vectors[0] if vectors else None
        if query_vec is not None:
            sims = cosine_batch(query_vec, [blob for _i, _s, _c, blob in rows])
            order = sorted(range(len(ids)), key=lambda i: sims[i], reverse=True)
            vec_rank = [ids[i] for i in order[:_RECALL_POOL] if sims[i] > 0.0]

        # 字面路 trigram按bm25
        fts_rank = self._fts_search(query, _RECALL_POOL)

        if vec_rank or fts_rank:
            fused = rrf_fuse([vec_rank, fts_rank])[:k]
            # cid in by_id 兜底 快照取完才被并发 ingest 插进来的新块 不在 by_id 里 别 KeyError
            parts = [f"【{Path(by_id[cid][0]).name}】\n{by_id[cid][1]}" for cid in fused if cid in by_id]
            if parts:
                return "\n\n".join(parts)

        needle = query.lower()  # 两路都空退子串
        hits = [(s, c) for _i, s, c, _b in rows if needle in c.lower()]
        if not hits:
            return "(nothing relevant found in the knowledge base)"
        return "\n\n".join(f"【{Path(s).name}】\n{c}" for s, c in hits[:k])

    def forget(self, source: str | None = None) -> str:
        """删文档 给source模糊删 不给清空整库"""
        with self._lock:
            try:
                if source:
                    cur = self._conn.execute("DELETE FROM chunks WHERE source LIKE ?", (f"%{source}%",))
                    self._conn.commit()
                    return f"Removed {cur.rowcount} chunk(s) from the knowledge base (matching \"{source}\")."
                self._conn.execute("DELETE FROM chunks")
                self._conn.commit()
                return "Cleared the knowledge base."
            except sqlite3.DatabaseError:
                # 库损坏 DELETE 走不通 重建空库 保证清知识库重置一定生效 对齐 store.wipe
                self._rebuild()
                return "Cleared the knowledge base (rebuilt a corrupt index)."

    def count(self) -> int:
        """按source去重的文档篇数"""
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(DISTINCT source) FROM chunks").fetchone()[0])

    def summary(self) -> str:
        with self._lock:
            rows = self._conn.execute(
                "SELECT source, COUNT(*) FROM chunks GROUP BY source ORDER BY source"
            ).fetchall()
        if not rows:
            return "(the knowledge base is empty)"
        return "\n".join(f"- {Path(source).name} ({n} chunks)" for source, n in rows)

    def sources(self) -> list[tuple[str, str, int]]:
        """控制面板列文档用"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT source, COUNT(*) FROM chunks GROUP BY source ORDER BY source"
            ).fetchall()
        return [(str(s), Path(s).name, int(n)) for s, n in rows]

    def forget_exact(self, source: str) -> int:
        """整路径精确删"""
        with self._lock:
            cur = self._conn.execute("DELETE FROM chunks WHERE source = ?", (source,))
            self._conn.commit()
        return cur.rowcount

    def close(self) -> None:
        """退出前干净关闭 锁住等在途写收尾再关 防硬杀截断成损坏库"""
        with self._lock:
            self._closing = True  # 置位后在途入库的锁内段会早退 不再 INSERT 到即将关掉的连接
            try:
                self._conn.commit()
            except Exception:
                pass
            try:
                self._conn.close()
            except Exception:
                pass


def read_file_text(path: str) -> str | None:
    """取文件纯文本 pdf走抽取ocr 读不出给None"""
    p = Path(path).expanduser()
    if not p.is_file():
        return None
    if p.suffix.lower() == ".pdf":
        return _read_pdf(p)
    return _read_text(p)


docs = DocStore()
