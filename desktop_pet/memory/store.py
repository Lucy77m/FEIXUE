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

from desktop_pet.memory.embed import cosine, cosine_batch, embed_texts, pack, unpack
from desktop_pet.memory.hybrid import fts_query, rrf_fuse
from desktop_pet.settings import DATA_DIR, delete_db_files

_MEMORY_DIR = DATA_DIR / "memory"
_DB_PATH = _MEMORY_DIR / "memory.db"
_PROFILE_JSON = _MEMORY_DIR / "profile.json"
_EXPERIENCES_JSON = _MEMORY_DIR / "experiences.json"

_INJECT = 6          # 一次往上下文塞几条经验
_ENV_INJECT = 4
_DEDUP_COSINE = 0.92  # 向量去重阈值
_DEDUP_RATIO = 0.86   # 没向量退字面相似度的阈值
_DEDUP_SCAN = 600     # 去重只回扫最近600条

_RELATED_COSINE = 0.80   # 同主题但不到重复的带宽下沿 新信息进来旧条目降权
_SUPERSEDE_FACTOR = 0.6  # 被顶掉的旧条目显著性打的折
_SUPERSEDE_MAX = 2       # 一次最多降权几条 防误伤一大片
_MAX_EXPERIENCES = 1500  # 经验表容量上限 超了裁显著性最低的老条目
_RECALL_BONUS = 0.01     # 被真召回一次显著性回一点血
_RECALL_POOL = 30        # 两路各召回这么多候选 再RRF融合精排到k
_HYBRID_W_REL = 0.60     # 融合相关性的权重 语义和字面都进这一项
_HYBRID_W_SAL = 0.25     # 衰减后显著性的权重
_HYBRID_W_REC = 0.15     # 新近度的权重

_CLUSTER_COSINE = 0.80   # 成簇下沿 同主题的几个侧面才揉 不到这条不算一簇
_CLUSTER_MIN = 3         # 至少这么多条才值得合并成一条概括
_CLUSTER_MAX = 8         # 一簇最多收几条 给LLM的料有上限
_CLUSTER_RUNS = 2        # 一次consolidation最多揉几簇 控LLM调用数
_CLUSTER_SCAN = 400      # 只在最近这么多条未合并经验里找簇
_CONSOLIDATED_DEMOTE = 0.5  # 被揉进概括的原始条目显著性打的折


def _effective_salience(sal: float, last_seen: str, now: datetime) -> float:
    """显著性随冷落时间半衰 越重要的记忆半衰期越长
    形成性记忆几个月才掉一半 鸡毛蒜皮几周就沉底 被召回会刷新last_seen回血"""
    try:
        age_days = max(0.0, (now - datetime.fromisoformat(last_seen)).total_seconds() / 86400.0)
    except (ValueError, TypeError):
        return sal
    tau = 14.0 + 76.0 * sal  # 半衰期14~90天随显著性走
    return sal * 0.5 ** (age_days / tau)


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
    def __init__(self, db_path: Path | None = None) -> None:
        path = db_path or _DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._lock = threading.RLock()
        # 连接跨线程共享 靠rlock串行
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._fts = False
        try:
            self._create_schema()
            self._migrate_columns()
            self._migrate_legacy_json()
            self._setup_fts()
        except sqlite3.DatabaseError:
            self._rebuild()  # 库损坏(异常退出留下)就重建空库 别让 app 起不来(自愈只能在跑起来后调)

    def _setup_fts(self) -> None:
        """给经验内容建trigram全文索引 triggers自动跟主表同步增删改
        UPDATE只盯content列 显著性回血改其它列不会白白重建索引
        这个sqlite没编译FTS5就退化纯向量 仍能用 不报错"""
        try:
            with self._lock:
                self._conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS experiences_fts USING fts5("
                    "content, content='experiences', content_rowid='id', tokenize='trigram')"
                )
                self._conn.executescript(
                    """
                    CREATE TRIGGER IF NOT EXISTS experiences_ai AFTER INSERT ON experiences BEGIN
                        INSERT INTO experiences_fts(rowid, content) VALUES (new.id, new.content);
                    END;
                    CREATE TRIGGER IF NOT EXISTS experiences_ad AFTER DELETE ON experiences BEGIN
                        INSERT INTO experiences_fts(experiences_fts, rowid, content) VALUES('delete', old.id, old.content);
                    END;
                    CREATE TRIGGER IF NOT EXISTS experiences_au AFTER UPDATE OF content ON experiences BEGIN
                        INSERT INTO experiences_fts(experiences_fts, rowid, content) VALUES('delete', old.id, old.content);
                        INSERT INTO experiences_fts(rowid, content) VALUES (new.id, new.content);
                    END;
                    """
                )
                # 老库回填 FTS空但主表有货就整体重建一次索引
                fts_n = self._conn.execute("SELECT count(*) FROM experiences_fts").fetchone()[0]
                exp_n = self._conn.execute("SELECT count(*) FROM experiences").fetchone()[0]
                if fts_n == 0 and exp_n > 0:
                    self._conn.execute("INSERT INTO experiences_fts(experiences_fts) VALUES('rebuild')")
                self._conn.commit()
            self._fts = True
        except sqlite3.OperationalError:
            self._fts = False

    def _fts_search(self, query: str, pool: int) -> list[int]:
        """字面路 trigram召回一批id 按bm25排 没FTS或没有效查询词返回空"""
        if not self._fts:
            return []
        match = fts_query(query)
        if not match:
            return []
        try:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT rowid FROM experiences_fts WHERE experiences_fts MATCH ? "
                    "ORDER BY bm25(experiences_fts) LIMIT ?", (match, pool)
                ).fetchall()
            return [int(r[0]) for r in rows]
        except sqlite3.OperationalError:
            return []

    def _migrate_columns(self) -> None:
        """老库补列 已有就跳过"""
        with self._lock:
            cols = {row[1] for row in self._conn.execute("PRAGMA table_info(experiences)")}
            if "salience" not in cols:
                self._conn.execute(
                    "ALTER TABLE experiences ADD COLUMN salience REAL NOT NULL DEFAULT 0.5"
                )
            if "last_seen" not in cols:
                # 旧条目的last_seen用写入时间垫底
                self._conn.execute("ALTER TABLE experiences ADD COLUMN last_seen TEXT")
                self._conn.execute("UPDATE experiences SET last_seen = ts WHERE last_seen IS NULL")
            if "recall_count" not in cols:
                self._conn.execute(
                    "ALTER TABLE experiences ADD COLUMN recall_count INTEGER NOT NULL DEFAULT 0"
                )
            if "consolidated" not in cols:
                # 已被夜间合并揉进概括的原始条目标1 不再参与下次聚类
                self._conn.execute(
                    "ALTER TABLE experiences ADD COLUMN consolidated INTEGER NOT NULL DEFAULT 0"
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
            try:
                for table in ("profile", "experiences", "env", "opinions"):
                    self._conn.execute(f"DELETE FROM {table}")
                self._conn.commit()
            except sqlite3.DatabaseError:
                # 库损坏(异常退出常留下)时 DELETE 走不通——整个重建 保证重置一定清干净
                self._rebuild()

    def close(self) -> None:
        """退出前干净关闭——锁住等任何在途写(如后台反思的 commit)收尾再关。
        关完磁盘上的库就是一致的 之后进程被硬杀也不会把 SQLite 截断成 malformed(损坏根因)"""
        with self._lock:
            try:
                self._conn.commit()
            except Exception:
                pass
            try:
                self._conn.close()
            except Exception:
                pass

    def _rebuild(self) -> None:
        """删掉损坏的库文件 重连建空表 让重置在库坏掉时也一定生效"""
        try:
            self._conn.close()
        except Exception:
            pass
        path = self._path
        self._conn = None  # 丢掉死连接引用 否则 delete_db_files 里的 gc 收不掉它 文件句柄不放 unlink 必失败
        delete_db_files(path)  # 连 WAL/SHM 一起清 带退避重试绕开 Windows 句柄释放延迟
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._create_schema()
        self._migrate_columns()
        self._fts = False
        self._setup_fts()

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
        """插一条经验 重复就原地更新返回False 复现的记忆显著性取max越提越粘
        同主题的旧条目降权加速淡出 表满裁掉最不重要的"""
        duplicate_id = self._find_duplicate(content, vector)
        blob = pack(vector) if vector else None
        if duplicate_id is not None:
            self._conn.execute(
                "UPDATE experiences SET content = ?, ts = ?, confidence = ?, embedding = ?, "
                "salience = MAX(salience, ?), last_seen = ? WHERE id = ?",
                (content, ts, confidence, blob, salience, ts, duplicate_id),
            )
            return False
        self._supersede_related(vector)
        self._conn.execute(
            "INSERT INTO experiences(content, ts, confidence, source, embedding, salience, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (content, ts, confidence, source, blob, salience, ts),
        )
        self._prune_overflow()
        return True

    def _supersede_related(self, vector: list[float] | None) -> None:
        """新信息落地时给同主题旧条目打折 它们大概率被新的顶掉了
        注意这不是严格的矛盾判定 只是语义相近 所以只降权不删 错了还能靠召回回血"""
        if vector is None:
            return
        rows = self._conn.execute(
            "SELECT id, embedding FROM experiences ORDER BY id DESC LIMIT ?", (_DEDUP_SCAN,)
        ).fetchall()
        sims = cosine_batch(vector, [blob for _id, blob in rows])  # numpy批量 一次算完
        demoted = 0
        for (row_id, _blob), sim in zip(rows, sims):
            if _RELATED_COSINE <= sim < _DEDUP_COSINE:
                self._conn.execute(
                    "UPDATE experiences SET salience = MAX(0.05, salience * ?) WHERE id = ?",
                    (_SUPERSEDE_FACTOR, row_id),
                )
                demoted += 1
                if demoted >= _SUPERSEDE_MAX:
                    return

    def _prune_overflow(self) -> None:
        """超容量就裁 显著性最低且最老的先走 召回扫表的成本也被这个上限锁死"""
        total = self._conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0]
        excess = int(total) - _MAX_EXPERIENCES
        if excess > 0:
            self._conn.execute(
                "DELETE FROM experiences WHERE id IN "
                "(SELECT id FROM experiences ORDER BY salience ASC, id ASC LIMIT ?)",
                (excess,),
            )

    def _find_clusters(self) -> list[list[tuple[int, str]]]:
        """在未合并经验里贪心找紧致的语义簇 每簇是同一主题的几个侧面
        和去重不同 这里不是近义重复 是要把分散的touchpoint揉成一条更高阶的事实"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, content, embedding FROM experiences "
                "WHERE consolidated = 0 AND embedding IS NOT NULL "
                "ORDER BY id DESC LIMIT ?", (_CLUSTER_SCAN,)
            ).fetchall()
        items = [(rid, content, unpack(blob)) for rid, content, blob in rows]
        items = [(rid, c, v) for rid, c, v in items if v is not None]
        if len(items) < _CLUSTER_MIN:
            return []
        used: set[int] = set()
        clusters: list[list[tuple[int, str]]] = []
        for seed_id, seed_c, seed_v in items:
            if seed_id in used:
                continue
            sims = cosine_batch(seed_v, [pack(v) for _i, _c, v in items])
            members = []
            for (rid, content, _v), sim in zip(items, sims):
                if rid in used:
                    continue
                if sim >= _CLUSTER_COSINE:  # 含种子自身 sim=1
                    members.append((rid, content))
                    if len(members) >= _CLUSTER_MAX:
                        break
            if len(members) >= _CLUSTER_MIN:
                clusters.append(members)
                used.update(rid for rid, _c in members)
                if len(clusters) >= _CLUSTER_RUNS:
                    break
        return clusters

    def consolidate(self, summarize) -> int:
        """夜间合并 把成簇的零碎经验揉成更高阶概括 summarize是注入的LLM回调
        聚类和落库在锁内 LLM和嵌入在锁外做 返回揉成了几条"""
        clusters = self._find_clusters()
        if not clusters:
            return 0
        count = 0
        for members in clusters:
            texts = [c for _id, c in members]
            try:
                summary = (summarize(texts) or "").strip()
            except Exception:
                summary = ""
            if not summary:
                continue
            vecs = embed_texts([summary])
            vector = vecs[0] if vecs else None
            blob = pack(vector) if vector else None
            member_ids = [rid for rid, _c in members]
            with self._lock:
                # 概括以高显著性入库 来源标consolidation 自带last_seen
                self._conn.execute(
                    "INSERT INTO experiences(content, ts, confidence, source, embedding, salience, last_seen) "
                    "VALUES (?, ?, 1.0, 'consolidation', ?, 0.7, ?)",
                    (summary, _now(), blob, _now()),
                )
                # 原始条目标记已合并并降权 留着但沉底 具体细节偶尔还用得上
                qmarks = ",".join("?" * len(member_ids))
                self._conn.execute(
                    f"UPDATE experiences SET consolidated = 1, salience = salience * ? "
                    f"WHERE id IN ({qmarks})",
                    (_CONSOLIDATED_DEMOTE, *member_ids),
                )
                self._prune_overflow()  # 合并出的概括也服从容量上限 别让 consolidation 路径绕过裁剪
                self._conn.commit()
            count += 1
        return count

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
        """混合召回 向量语义和trigram字面两路各取候选 RRF融合 再叠衰减显著性和新近精排
        字面路语言无关零依赖 专补向量漏掉的精确词 文件名报错码英文术语数字
        断网拿不到向量时单靠字面路仍能召回 被真命中的当场回血刷新冷落计时"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, content, embedding, salience, last_seen FROM experiences ORDER BY id"
            ).fetchall()
        if not rows:
            return []
        if len(rows) <= k:
            return [r[1] for r in rows]  # 条数不够全给
        n = len(rows)
        now = datetime.now()
        meta = {  # id到内容 衰减显著性 新近度
            rid: (content, _effective_salience(float(sal or 0.5), last_seen or "", now), i / (n - 1))
            for i, (rid, content, _blob, sal, last_seen) in enumerate(rows)
        }
        ids = [rid for rid, *_ in rows]

        # 向量路 余弦排名取候选池
        vec_rank: list[int] = []
        query_vec = self._query_vector(query)
        if query_vec is not None:
            sims = cosine_batch(query_vec, [blob for _id, _c, blob, _s, _l in rows])
            order = sorted(range(len(ids)), key=lambda i: sims[i], reverse=True)
            vec_rank = [ids[i] for i in order[:_RECALL_POOL] if sims[i] > 0.0]

        # 字面路 trigram按bm25排名取候选池
        fts_rank = self._fts_search(query, _RECALL_POOL)

        if not vec_rank and not fts_rank:
            # 两路都空 退子串再退最近 这条多半是没配嵌入且无字面命中
            needle = query.lower()
            hits = [(meta[rid][1], meta[rid][0]) for rid in ids if needle in meta[rid][0].lower()]
            if hits:
                hits.sort(key=lambda s: s[0], reverse=True)
                return [c for _s, c in hits[:k]]
            return [meta[rid][0] for rid in ids[-k:]]

        # RRF融合两路 再用衰减显著性和新近度调制 取top-k
        fused = rrf_fuse([vec_rank, fts_rank])
        m = len(fused)
        scored = []
        for pos, rid in enumerate(fused):
            entry = meta.get(rid)  # 快照取完后才被并发写(反思/合并)插进来的 id 不在 meta 里 跳过别 KeyError
            if entry is None:
                continue
            content, eff, recency = entry
            rel = 1.0 - pos / m  # 融合名次转0~1相关性
            final = _HYBRID_W_REL * rel + _HYBRID_W_SAL * eff + _HYBRID_W_REC * recency
            scored.append((final, rid, content))
        scored.sort(key=lambda s: s[0], reverse=True)
        top = scored[:k]

        # 真召回到的强化 都是两路捞出来的 给回血刷新计时
        hit_ids = [rid for _f, rid, _c in top]
        if hit_ids:
            stamp = _now()
            with self._lock:
                self._conn.executemany(
                    "UPDATE experiences SET last_seen = ?, recall_count = recall_count + 1, "
                    "salience = MIN(1.0, salience + ?) WHERE id = ?",
                    [(stamp, _RECALL_BONUS, rid) for rid in hit_ids],
                )
                self._conn.commit()
        return [c for _f, _rid, c in top]

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
