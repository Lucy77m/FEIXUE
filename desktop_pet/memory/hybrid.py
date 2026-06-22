# 混合检索两件纯算法工具 自然语言查询变安全 FTS5 查询 多路排序 RRF 融合
# 字面检索走 SQLite trigram 分词 语言无关 和向量检索互补

from __future__ import annotations

import re

# latin数字下划线连写 或 一段中日韩文字 各成一个token
_TOKEN_RE = re.compile(
    r"[A-Za-z0-9_]+"
    r"|[一-鿿㐀-䶿぀-ヿ가-힯]+"
)
_MIN_LEN = 3       # trigram按3字符滑窗 短于这个的词索引不到
_CJK_MAX = 12      # 太长的中日韩串多半是整句 交给向量 不硬塞FTS当精确子串
_MAX_TERMS = 12    # 一个查询最多取几个词 防超长query炸出巨型MATCH


def _is_cjk_run(tok: str) -> bool:
    return bool(tok) and "一" <= tok[0] <= "힯"


def fts_query(text: str) -> str | None:
    """把用户的话拆成安全的 trigram MATCH 查询 取不出有效词返回 None 跳过字面路"""
    if not text:
        return None
    phrases: list[str] = []
    seen: set[str] = set()
    for tok in _TOKEN_RE.findall(text):
        if len(tok) < _MIN_LEN:
            continue
        if _is_cjk_run(tok) and len(tok) > _CJK_MAX:
            continue  # 整句交给向量 别当精确子串硬匹配
        key = tok.lower()
        if key in seen:
            continue
        seen.add(key)
        esc = tok.replace('"', '""')  # 转义内部引号 防MATCH语法注入
        phrases.append(f'"{esc}"')
        if len(phrases) >= _MAX_TERMS:
            break
    if not phrases:
        return None
    return " OR ".join(phrases)


def rrf_fuse(rank_lists: list[list], k: int = 60) -> list:
    """倒数排名融合 每路按名次贡献 1/(k+名次) 累加后重排 多路命中的自然冒头"""
    scores: dict = {}
    for lst in rank_lists:
        for rank, item in enumerate(lst):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda it: scores[it], reverse=True)
