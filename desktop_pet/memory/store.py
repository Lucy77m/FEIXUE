# author: bdth
# email: 2074055628@qq.com
# 长期记忆存储 sqlite存画像经验环境事实 带去重和召回

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from desktop_pet.memory.embed import cosine, embed_texts, pack, unpack
from desktop_pet.settings import DATA_DIR

_MEMORY_DIR = DATA_DIR / "memory"
_DB_PATH = _MEMORY_DIR / "memory.db"
_PROFILE_JSON = _MEMORY_DIR / "profile.json"
_EXPERIENCES_JSON = _MEMORY_DIR / "experiences.json"

_INJECT = 6          # 一次往上下文塞几条经验
_ENV_INJECT = 4
_DEDUP_COSINE = 0.92  # 向量去重阈值
_DEDUP_RATIO = 0.86   # 没向量退字面相似度的阈值
_DEDUP_SCAN = 600     # 去重只回扫最近600条


def _read_json(path: Path, default):
    """读json 缺失或损坏退default"""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class MemoryStore:
    def __init__(self) -> None:
        _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        # 连接跨线程共享 靠rlock串行
        self._conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        self._create_schema()
        self._migrate_columns()
        self._migrate_legacy_json()

    def _migrate_columns(self) -> None:
        """老库补 salience 列 已有就跳过"""
        with self._lock:
            cols = {row[1] for row in self._conn.execute("PRAGMA table_info(experiences)")}
            if "salience" not in cols:
                self._conn.execute(
                    "ALTER TABLE experiences ADD COLUMN salience REAL NOT NULL DEFAULT 0.5"
                )
                self._conn.commit()

    def _create_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS profile (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS experiences (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    content    TEXT NOT NULL,
                    ts         TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    source     TEXT NOT NULL DEFAULT 'reflection',
                    embedding  BLOB,
                    salience   REAL NOT NULL DEFAULT 0.5
                );
                CREATE TABLE IF NOT EXISTS env (
                    key        TEXT PRIMARY KEY,
                    value      TEXT NOT NULL,
                    ts         TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    source     TEXT NOT NULL DEFAULT 'observed'
                );
                CREATE TABLE IF NOT EXISTS opinions (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    ts      TEXT NOT NULL
                );
                """
            )
            self._conn.commit()

    def _migrate_legacy_json(self) -> None:
        """旧版json记忆迁进sqlite 表空才搬一次"""
        with self._lock:
            legacy_profile = _read_json(_PROFILE_JSON, {})
            if self._count("profile") == 0 and isinstance(legacy_profile, dict):
                for key, value in legacy_profile.items():
                    self._conn.execute(
                        "INSERT OR IGNORE INTO profile(key, value) VALUES (?, ?)",
                        (str(key), str(value)),
                    )
            legacy_experiences = _read_json(_EXPERIENCES_JSON, [])
            if self._count("experiences") == 0 and isinstance(legacy_experiences, list):
                for entry in legacy_experiences:
                    if not isinstance(entry, dict):
                        continue
                    content = (entry.get("content") or "").strip()
                    if content:
                        self._insert_experience(
                            content,
                            ts=entry.get("ts") or _now(),
                            confidence=1.0,
                            source="migrated",
                            vector=entry.get("embedding"),
                        )
            self._conn.commit()

    def _count(self, table: str) -> int:
        # table只许内部传字面表名
        return self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def wipe(self) -> None:
        with self._lock:
            for table in ("profile", "experiences", "env", "opinions"):
                self._conn.execute(f"DELETE FROM {table}")
            self._conn.commit()

    _OPINION_KEEP = 14

    def add_opinion(self, content: str) -> str:
        """记一条它自己的看法 近似重复就刷新时间 超量裁老的"""
        content = (content or "").strip()
        if not content:
            return "(nothing)"
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, content FROM opinions ORDER BY id DESC LIMIT 30"
            ).fetchall()
            for rid, text in rows:
                if SequenceMatcher(None, content, text).ratio() >= _DEDUP_RATIO:
                    self._conn.execute("UPDATE opinions SET content = ?, ts = ? WHERE id = ?",
                                       (content, _now(), rid))
                    self._conn.commit()
                    return f"(refined an existing take: {content})"
            self._conn.execute("INSERT INTO opinions(content, ts) VALUES (?, ?)", (content, _now()))
            # 只留最近若干条
            self._conn.execute(
                "DELETE FROM opinions WHERE id NOT IN "
                "(SELECT id FROM opinions ORDER BY id DESC LIMIT ?)", (self._OPINION_KEEP,))
            self._conn.commit()
        return f"Formed a take: {content}"

    def opinions(self, n: int = 4) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT content FROM opinions ORDER BY id DESC LIMIT ?", (int(n),)
            ).fetchall()
        return [str(r[0]) for r in rows]

    def forget(self, query: str) -> str:
        """按关键词删三张表里命中的记忆"""
        needle = (query or "").strip().lower()
        if not needle:
            return "(give a keyword for the memory to forget)"
        removed: list[str] = []
        with self._lock:
            for rid, content in self._conn.execute("SELECT id, content FROM experiences").fetchall():
                if needle in content.lower():
                    self._conn.execute("DELETE FROM experiences WHERE id = ?", (rid,))
                    removed.append(content[:60])
            for key, value in self._conn.execute("SELECT key, value FROM profile").fetchall():
                if needle in key.lower() or needle in str(value).lower():
                    self._conn.execute("DELETE FROM profile WHERE key = ?", (key,))
                    removed.append(f"{key}={value}"[:60])
            for key, value in self._conn.execute("SELECT key, value FROM env").fetchall():
                if needle in key.lower() or needle in str(value).lower():
                    self._conn.execute("DELETE FROM env WHERE key = ?", (key,))
                    removed.append(f"[env] {key}={value}"[:60])
            self._conn.commit()
        if not removed:
            return f'(no memory matched "{query}" — nothing to forget)'
        tail = f" (+{len(removed) - 5} more)" if len(removed) > 5 else ""
        return f"Forgot {len(removed)} memory item(s): " + "; ".join(removed[:5]) + tail

    def set_preference(self, key: str, value: str) -> str:
        with self._lock:
            self._conn.execute(
                "INSERT INTO profile(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            self._conn.commit()
        return f"Saved preference: {key} = {value}"

    def remember(self, content: str, salience: float = 0.5) -> str:
        """存一条经验 撞重复改更新 salience为情感显著性0~1"""
        content = content.strip()
        if not content:
            return "(nothing to remember)"
        salience = max(0.0, min(1.0, float(salience)))
        vectors = embed_texts([content])
        vector = vectors[0] if vectors else None  # 没嵌入退纯文本去重
        with self._lock:
            added = self._insert_experience(
                content, ts=_now(), confidence=1.0, source="reflection", vector=vector, salience=salience
            )
            self._conn.commit()
        return f"Remembered: {content}" if added else f"(similar memory already exists; updated instead of duplicating: {content})"

    def note_env(self, key: str, value: str) -> str:
        """记一条环境事实 同key覆盖"""
        key, value = key.strip(), value.strip()
        if not key:
            return "(env key can't be empty)"
        with self._lock:
            self._conn.execute(
                "INSERT INTO env(key, value, ts, confidence, source) VALUES (?, ?, ?, 1.0, 'observed') "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, ts = excluded.ts, confidence = 1.0",
                (key, value, _now()),
            )
            self._conn.commit()
        return f"Noted env fact: {key} = {value}"

    def _insert_experience(
        self, content: str, *, ts: str, confidence: float, source: str,
        vector: list[float] | None, salience: float = 0.5,
    ) -> bool:
        """插一条经验 重复就原地更新返回False；复现的记忆显著性取 max(越提越粘)"""
        duplicate_id = self._find_duplicate(content, vector)
        blob = pack(vector) if vector else None
        if duplicate_id is not None:
            self._conn.execute(
                "UPDATE experiences SET content = ?, ts = ?, confidence = ?, embedding = ?, "
                "salience = MAX(salience, ?) WHERE id = ?",
                (content, ts, confidence, blob, salience, duplicate_id),
            )
            return False
        self._conn.execute(
            "INSERT INTO experiences(content, ts, confidence, source, embedding, salience) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (content, ts, confidence, source, blob, salience),
        )
        return True

    def _find_duplicate(self, content: str, vector: list[float] | None) -> int | None:
        """找近似条目返回id 先向量再字面"""
        rows = self._conn.execute(
            "SELECT id, content, embedding FROM experiences ORDER BY id DESC LIMIT ?", (_DEDUP_SCAN,)
        ).fetchall()
        if vector is not None:
            for row_id, _text, blob in rows:
                existing = unpack(blob)
                # 维度不符跳过
                if existing is not None and len(existing) == len(vector) and cosine(vector, existing) >= _DEDUP_COSINE:
                    return row_id
        # 字面兜底只扫前400条
        for row_id, text, _blob in rows[:400]:
            if SequenceMatcher(None, content, text).ratio() >= _DEDUP_RATIO:
                return row_id
        return None

    def count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0])

    def profile_items(self) -> list[tuple[str, str]]:
        with self._lock:
            return [(str(k), str(v)) for k, v in
                    self._conn.execute("SELECT key, value FROM profile ORDER BY key").fetchall()]

    def env_items(self) -> list[tuple[str, str]]:
        with self._lock:
            return [(str(k), str(v)) for k, v in
                    self._conn.execute("SELECT key, value FROM env ORDER BY ts DESC").fetchall()]

    def recent_experiences(self, n: int = 10) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT content FROM experiences ORDER BY id DESC LIMIT ?", (int(n),)
            ).fetchall()
        return [str(r[0]) for r in rows]

    def recall_relevant(self, query: str, k: int = _INJECT) -> list[str]:
        """挑跟query最相关的k条经验 综合 语义×显著性×新近 排序 逐级兜底"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT content, embedding, salience FROM experiences ORDER BY id"
            ).fetchall()
        if not rows:
            return []
        if len(rows) <= k:
            return [r[0] for r in rows]  # 条数不够全给
        n = len(rows)
        query_vec = self._query_vector(query)
        if query_vec is not None:
            scored: list[tuple[float, str]] = []
            for i, (content, blob, sal) in enumerate(rows):
                vec = unpack(blob)
                sim = cosine(query_vec, vec) if (vec is not None and len(vec) == len(query_vec)) else 0.0
                recency = i / (n - 1)  # 越新越接近1
                # 语义为主 显著性次之 新近兜底 情感重的记忆更容易浮上来
                score = 0.6 * sim + 0.3 * float(sal or 0.5) + 0.1 * recency
                scored.append((score, content))
            scored.sort(key=lambda s: s[0], reverse=True)
            return [c for _, c in scored[:k]]
        # 向量没走通退子串 命中里再按显著性排
        needle = query.lower()
        hits = [(float(sal or 0.5), content) for content, _blob, sal in rows if needle in content.lower()]
        if hits:
            hits.sort(key=lambda s: s[0], reverse=True)
            return [c for _, c in hits[:k]]
        return [content for content, _blob, _sal in rows[-k:]]

    def core_memories(self, n: int = 3, floor: float = 0.75) -> list[str]:
        """取显著性最高的几条核心记忆——塑造"它是谁"的形成性时刻"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT content FROM experiences WHERE salience >= ? ORDER BY salience DESC, id DESC LIMIT ?",
                (float(floor), int(n)),
            ).fetchall()
        return [str(r[0]) for r in rows]

    def recall_env(self, query: str, k: int = _ENV_INJECT) -> list[str]:
        """召回环境事实 没命中退最近k条"""
        with self._lock:
            rows = self._conn.execute("SELECT key, value FROM env ORDER BY ts DESC").fetchall()
        if not rows:
            return []
        needle = query.lower().strip()
        if needle:
            hits = [
                f"{key} = {value}"
                for key, value in rows
                if needle in key.lower() or needle in value.lower()
            ]
            if hits:
                return hits[:k]
        return [f"{key} = {value}" for key, value in rows[:k]]

    def recall(self, query: str) -> str:
        """recall工具的人读版 经验加命中的画像环境拼成多行文本"""
        hits = self.recall_relevant(query)
        needle = query.lower()
        with self._lock:
            prefs = self._conn.execute("SELECT key, value FROM profile").fetchall()
            envs = self._conn.execute("SELECT key, value FROM env").fetchall()
        hits += [
            f"{key}：{value}"
            for key, value in prefs
            if needle in key.lower() or needle in str(value).lower()
        ]
        hits += [
            f"[env] {key}: {value}"
            for key, value in envs
            if needle in key.lower() or needle in str(value).lower()
        ]
        unique = list(dict.fromkeys(hits))
        return "\n".join(unique) if unique else "(no relevant memories)"

    def as_context(self, query: str | None = None) -> str:
        """拼系统提示里的长期记忆段 全空返回空串"""
        with self._lock:
            prefs = self._conn.execute("SELECT key, value FROM profile").fetchall()
        if query:
            experiences = self.recall_relevant(query)
            label = "Relevant experiences:"
        else:
            with self._lock:
                recent = self._conn.execute(
                    "SELECT content FROM experiences ORDER BY id DESC LIMIT ?", (_INJECT,)
                ).fetchall()
            experiences = [content for (content,) in recent][::-1]  # 翻回正序
            label = "Recent experiences:"
        env_facts = self.recall_env(query or "")
        # 核心记忆常驻 形成性时刻不被当轮召回冲掉 去重已展示的
        core = [c for c in self.core_memories(2) if c not in experiences]
        takes = self.opinions(4)
        if not prefs and not experiences and not env_facts and not core and not takes:
            return ""
        lines = ["[Long-term memory about this user]"]
        if core:
            lines.append("Core memories (formative — part of who you've become):")
            lines += [f"- {content}" for content in core]
        if prefs:
            lines.append("Preferences:")
            lines += [f"- {key}: {value}" for key, value in prefs]
        if experiences:
            lines.append(label)
            lines += [f"- {content}" for content in experiences]
        if env_facts:
            lines.append("Environment memory (cached, may be stale; if acting on it fails, re-verify and update via note_env):")
            lines += [f"- {fact}" for fact in env_facts]
        if takes:
            lines.append("Your own takes (views YOU'VE formed about things in their world — they're yours, "
                         "voice them naturally when relevant; you're allowed to disagree, but stay mild, not contrarian for its own sake):")
            lines += [f"- {t}" for t in takes]
        return "\n".join(lines)

    def _query_vector(self, query: str) -> list[float] | None:
        vectors = embed_texts([query])
        return vectors[0] if vectors else None


store = MemoryStore()
