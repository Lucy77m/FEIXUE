# author: bdth
# email: 2074055628@qq.com
# 文档知识库：抽取文本/PDF(含扫描页OCR)、切块向量化入库，供语义召回

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from desktop_pet.memory.embed import embed_texts, pack, rank_by_cosine
from desktop_pet.settings import DATA_DIR

_DB_PATH = DATA_DIR / "docs.db"
_CHUNK = 800
_OVERLAP = 120
_MAX_FILE = 600_000
_MAX_CHUNKS = 4000
_EMBED_BATCH = 32
_RECALL_K = 5
_TEXT_EXT = frozenset(
    {".txt", ".md", ".rst", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml",
     ".html", ".csv", ".tex", ".log", ".ini", ".cfg", ".java", ".go", ".rs", ".c",
     ".cpp", ".h", ".sql", ".sh", ".vue", ".xml"}
)
_DOC_EXT = _TEXT_EXT | {".pdf"}
_IGNORE_DIRS = frozenset({".venv", "venv", "__pycache__", ".git", "node_modules", "dist", "build"})
_PDF_TEXT_MIN = 16


def _read_text(file: Path) -> str | None:
    """读纯文本：utf-8(带 BOM)→gbk 依次试，都不行就强解 utf-8 忽略坏字节兜底。"""
    try:
        raw = file.read_bytes()
    except OSError:
        return None
    for encoding in ("utf-8-sig", "gbk"):  # 中文文档不少是 gbk，放第二顺位
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _read_pdf(file: Path) -> str | None:
    """提取 PDF 文字（有文本层的页直接读，扫描页走 OCR）。"""
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
    """扫描页没文本层，渲成 200dpi 位图走 OCR。"""
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
    # 按行(y 量化到 12px 一档)再按 x 排，把散落的框还原成正常阅读顺序
    boxes.sort(key=lambda b: (round(b["center_abs"][1] / 12), b["center_abs"][0]))
    return " ".join(b["text"] for b in boxes)


def _chunk_text(text: str) -> list[str]:
    """按段落攒块，尽量不切断语义；超长段落才硬切并带 _OVERLAP 重叠防边界丢上下文。"""
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    buffer = ""
    for para in (p.strip() for p in text.split("\n\n") if p.strip()):
        if len(para) > _CHUNK:  # 单段就超长 —— 先把攒着的 buffer 收掉，再按步长硬切
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
        self._conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS chunks ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, "
                "idx INTEGER NOT NULL, content TEXT NOT NULL, embedding BLOB)"
            )
            self._conn.commit()

    def ingest(self, path: str) -> str:
        """收一个文件或整个目录入库；目录递归收文本/PDF，跳过 _IGNORE_DIRS（.git/node_modules 等）。"""
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
            if total_chunks >= _MAX_CHUNKS:  # 全局封顶，别让一个大目录把库撑爆
                skipped += 1
                continue
            added = self._ingest_file(file, _MAX_CHUNKS - total_chunks)
            if added < 0:  # -1 = 读不出/太大/没切出块，记 skip 不算失败
                skipped += 1
            else:
                total_chunks += added
                done_files += 1
        tail = f", {skipped} file(s) skipped (too big / unreadable / over cap)" if skipped else ""
        return f"Ingested {done_files} file(s), {total_chunks} chunks into the knowledge base{tail}."

    def _ingest_file(self, file: Path, budget: int) -> int:
        """单文件入库，返回写入的 chunk 数；读不出/超 _MAX_FILE/无内容返回 -1。"""
        text = _read_pdf(file) if file.suffix.lower() == ".pdf" else _read_text(file)
        if text is None or len(text) > _MAX_FILE:
            return -1
        chunks = _chunk_text(text)[:budget]  # budget = 剩余全局配额，超了截断
        if not chunks:
            return -1
        source = str(file)
        with self._lock:
            self._conn.execute("DELETE FROM chunks WHERE source = ?", (source,))  # 先删旧的，重复 ingest 同一文件不留残块
            for start in range(0, len(chunks), _EMBED_BATCH):
                batch = chunks[start : start + _EMBED_BATCH]
                vectors = embed_texts(batch)
                if not vectors or len(vectors) != len(batch):  # 向量化挂了也照样存内容，留给 recall 的关键词兜底
                    vectors = [None] * len(batch)
                for offset, (content, vector) in enumerate(zip(batch, vectors)):
                    self._conn.execute(
                        "INSERT INTO chunks(source, idx, content, embedding) VALUES (?, ?, ?, ?)",
                        (source, start + offset, content, pack(vector) if vector else None),
                    )
            self._conn.commit()
        return len(chunks)

    def recall(self, query: str, k: int = _RECALL_K) -> str:
        """语义召回：query 向量化 → 全库余弦取 top-k；向量这路没结果再退回关键词子串匹配。"""
        query = (query or "").strip()
        if not query:
            return "(no search query given)"
        with self._lock:
            rows = self._conn.execute("SELECT source, content, embedding FROM chunks").fetchall()
        if not rows:
            return "(the knowledge base is empty — ingest some documents first with ingest_docs)"
        vectors = embed_texts([query])
        query_vec = vectors[0] if vectors else None
        if query_vec is not None:
            idxs = rank_by_cosine(query_vec, [blob for _, _, blob in rows], k)
            if idxs:
                return "\n\n".join(f"【{Path(rows[i][0]).name}】\n{rows[i][1]}" for i in idxs)
        needle = query.lower()  # 兜底：embedding 不可用或排不出名次时，纯子串匹配
        hits = [(s, c) for s, c, _ in rows if needle in c.lower()]
        if not hits:
            return "(nothing relevant found in the knowledge base)"
        return "\n\n".join(f"【{Path(s).name}】\n{c}" for s, c in hits[:k])

    def forget(self, source: str | None = None) -> str:
        """删文档：给了 source 按子串 LIKE 模糊删，不给则清空整个库。"""
        with self._lock:
            if source:
                cur = self._conn.execute("DELETE FROM chunks WHERE source LIKE ?", (f"%{source}%",))
                self._conn.commit()
                return f"Removed {cur.rowcount} chunk(s) from the knowledge base (matching \"{source}\")."
            self._conn.execute("DELETE FROM chunks")
            self._conn.commit()
            return "Cleared the knowledge base."

    def count(self) -> int:
        """文档篇数 —— 按 source 去重，不是 chunk 数。"""
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
        """给控制面板列文档用 —— 完整路径留着精确删，文件名只为展示。"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT source, COUNT(*) FROM chunks GROUP BY source ORDER BY source"
            ).fetchall()
        return [(str(s), Path(s).name, int(n)) for s, n in rows]

    def forget_exact(self, source: str) -> int:
        """配合 sources() 的整路径精确删 —— 不走 forget 的模糊 LIKE，免得误删同名。"""
        with self._lock:
            cur = self._conn.execute("DELETE FROM chunks WHERE source = ?", (source,))
            self._conn.commit()
        return cur.rowcount


def read_file_text(path: str) -> str | None:
    """取一个文件的纯文本，PDF 走抽取/OCR；非文件或读不出给 None。"""
    p = Path(path).expanduser()
    if not p.is_file():
        return None
    if p.suffix.lower() == ".pdf":
        return _read_pdf(p)
    return _read_text(p)


docs = DocStore()
