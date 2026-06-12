# author: bdth
# email: 2074055628@qq.com
# 混合检索的两件纯算法工具 把自然语言查询变成安全的FTS5查询 把多路排序RRF融合
# 字面检索走SQLite自带的trigram分词 语言无关 零依赖 中英日数字代码一视同仁
# 它和向量检索互补 trigram精确命中具体的词 文件名报错码英文术语数字 向量管语义

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
    """把用户的话拆成安全的trigram MATCH查询 取不出有效词返回None就跳过字面路
    长中日韩整句不进FTS 那是向量的活 这里只收能精确命中的具体词"""
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
    """倒数排名融合 每路给每个条目按名次贡献 1/(k+名次) 累加后重排
    名次靠前贡献大 多路都命中的自然冒头 只在一路命中的也不丢 这是hybrid的核心
    k默认60是RRF常用值 平滑掉头部名次的过度主导"""
    scores: dict = {}
    for lst in rank_lists:
        for rank, item in enumerate(lst):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda it: scores[it], reverse=True)
