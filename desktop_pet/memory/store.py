# author: bdth
# email: 2074055628@qq.com
# 长期记忆存储:基于 SQLite 持久化用户画像、经验与环境事实,支持向量/文本去重与相关性召回

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from desktop_pet.memory.embed import cosine, embed_texts, pack, rank_by_cosine, unpack
from desktop_pet.settings import DATA_DIR

_MEMORY_DIR = DATA_DIR / "memory"
_DB_PATH = _MEMORY_DIR / "memory.db"
_PROFILE_JSON = _MEMORY_DIR / "profile.json"
_EXPERIENCES_JSON = _MEMORY_DIR / "experiences.json"

_INJECT = 6          # 一次往上下文塞几条经验，多了挤占预算、稀释当前话题
_ENV_INJECT = 4
_DEDUP_COSINE = 0.92  # 向量这条线收得紧——0.92 以上才算重复，怕把"相近但不同"的经验误删
_DEDUP_RATIO = 0.86   # 没向量时退回字面相似度，阈值放低一点，纯文本噪声多
_DEDUP_SCAN = 600     # 去重只回扫最近 600 条，老记忆不再参与比对，省得每次插入全表扫


def _read_json(path: Path, default):
    """读旧版 JSON，文件不在或半截损坏(写到一半崩过)都退 default，不抛。"""
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
        # check_same_thread=False：后台反思线程和主线程都要写，连接跨线程共享，靠下面的 RLock 串行化
        self._conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        self._create_schema()
        self._migrate_legacy_json()

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
                    embedding  BLOB
                );
                CREATE TABLE IF NOT EXISTS env (
                    key        TEXT PRIMARY KEY,
                    value      TEXT NOT NULL,
                    ts         TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    source     TEXT NOT NULL DEFAULT 'observed'
                );
                """
            )
            self._conn.commit()

    def _migrate_legacy_json(self) -> None:
        """老版本把记忆存在 profile.json/experiences.json，迁进 SQLite——只在对应表为空时搬一次，跑过就不会重复导入。"""
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
        # table 拼进 SQL 是裸字符串——只许内部传字面表名，绝不能接外部输入
        return self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def wipe(self) -> None:
        with self._lock:
            for table in ("profile", "experiences", "env"):
                self._conn.execute(f"DELETE FROM {table}")
            self._conn.commit()

    def forget(self, query: str) -> str:
        """关键词命中就删——经验/画像/环境三张表全扫，回一句人话总结删了啥。"""
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

    def remember(self, content: str) -> str:
        """存一条经验。先算 embedding 再插——撞到相似的不新增，改成更新原条目(见 _insert_experience)。"""
        content = content.strip()
        if not content:
            return "(nothing to remember)"
        vectors = embed_texts([content])
        vector = vectors[0] if vectors else None  # 嵌入模型没起来就退成纯文本去重
        with self._lock:
            added = self._insert_experience(
                content, ts=_now(), confidence=1.0, source="reflection", vector=vector
            )
            self._conn.commit()
        return f"Remembered: {content}" if added else f"(similar memory already exists; updated instead of duplicating: {content})"

    def note_env(self, key: str, value: str) -> str:
        """记一条环境事实(如某窗口标题、某路径)，同 key 覆盖并刷新时间戳，置信度拉回 1.0。"""
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
        self, content: str, *, ts: str, confidence: float, source: str, vector: list[float] | None
    ) -> bool:
        """插一条经验，返回 True=新增 / False=撞重复改为原地更新。调用方据此区分提示语。"""
        duplicate_id = self._find_duplicate(content, vector)
        blob = pack(vector) if vector else None
        if duplicate_id is not None:
            self._conn.execute(
                "UPDATE experiences SET content = ?, ts = ?, confidence = ?, embedding = ? WHERE id = ?",
                (content, ts, confidence, blob, duplicate_id),
            )
            return False
        self._conn.execute(
            "INSERT INTO experiences(content, ts, confidence, source, embedding) VALUES (?, ?, ?, ?, ?)",
            (content, ts, confidence, source, blob),
        )
        return True

    def _find_duplicate(self, content: str, vector: list[float] | None) -> int | None:
        """找已存在的近似条目，命中返回其 id。先走向量(语义)，再退字面相似度兜底。"""
        rows = self._conn.execute(
            "SELECT id, content, embedding FROM experiences ORDER BY id DESC LIMIT ?", (_DEDUP_SCAN,)
        ).fetchall()
        if vector is not None:
            for row_id, _text, blob in rows:
                existing = unpack(blob)
                # 维度对不上(换过嵌入模型、老数据没向量)直接跳过，否则 cosine 会算错
                if existing is not None and len(existing) == len(vector) and cosine(vector, existing) >= _DEDUP_COSINE:
                    return row_id
        # 字面兜底只扫前 400——SequenceMatcher 是 O(n·m)，全扫 600 条逐对比对太慢
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
        # ts 倒序，新观察到的覆盖在前
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
        """挑跟 query 最相关的 k 条经验。向量排序 → 关键词命中 → 都没有就退最近 k 条，逐级兜底。"""
        with self._lock:
            rows = self._conn.execute("SELECT content, embedding FROM experiences ORDER BY id").fetchall()
        if not rows:
            return []
        if len(rows) <= k:
            return [content for content, _ in rows]  # 总共没几条，排序没意义，全给
        query_vec = self._query_vector(query)
        if query_vec is not None:
            idxs = rank_by_cosine(query_vec, [blob for _, blob in rows], k)
            if idxs:
                return [rows[i][0] for i in idxs]
        # 向量这条路没走通(模型没起来/全是无向量旧数据)，退到子串匹配
        needle = query.lower()
        hits = [content for content, _ in rows if needle in content.lower()]
        return hits[:k] if hits else [content for content, _ in rows[-k:]]

    def recall_env(self, query: str, k: int = _ENV_INJECT) -> list[str]:
        """召回环境事实：query 命中就给命中的，没命中(或空 query)退最近 k 条。环境靠新鲜度，按 ts 倒序。"""
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
        """给 recall 工具的人读版：相关经验 + 命中的画像/环境，拼成多行文本，dict.fromkeys 去重保序。"""
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
        """拼成塞进系统提示的那段长期记忆。有 query 走相关召回，没 query 给最近几条；三块全空就返回空串、不占位。"""
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
            experiences = [content for (content,) in recent][::-1]  # 取最新几条后翻正序，读起来时间顺
            label = "Recent experiences:"
        env_facts = self.recall_env(query or "")
        if not prefs and not experiences and not env_facts:
            return ""
        lines = ["[Long-term memory about this user]"]
        if prefs:
            lines.append("Preferences:")
            lines += [f"- {key}: {value}" for key, value in prefs]
        if experiences:
            lines.append(label)
            lines += [f"- {content}" for content in experiences]
        if env_facts:
            lines.append("Environment memory (cached, may be stale; if acting on it fails, re-verify and update via note_env):")
            lines += [f"- {fact}" for fact in env_facts]
        return "\n".join(lines)

    def _query_vector(self, query: str) -> list[float] | None:
        vectors = embed_texts([query])
        return vectors[0] if vectors else None


store = MemoryStore()
