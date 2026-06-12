# author: bdth
# email: 2074055628@qq.com
# 混合检索纯函数测试 查询构造的多语言和安全边界 RRF融合的名次合成

from __future__ import annotations

import sqlite3

from desktop_pet.memory.hybrid import fts_query, rrf_fuse


def test_fts_query_extracts_tokens():
    # 英文 代码 数字 都该被拎成带引号的phrase
    q = fts_query("how to fix login_error code 404")
    assert '"login_error"' in q and '"404"' in q and '"how"' in q
    assert " OR " in q


def test_fts_query_escapes_quotes():
    # 裸引号必须转义 不然MATCH语法炸 这条直接喂sqlite验证不抛
    q = fts_query('search for abc"def term')
    con = sqlite3.connect(":memory:")
    con.execute('CREATE VIRTUAL TABLE t USING fts5(content, tokenize="trigram")')
    con.execute("INSERT INTO t VALUES ('abc def')")
    con.execute("SELECT content FROM t WHERE t MATCH ?", (q,)).fetchall()  # 不抛即过


def test_fts_query_skips_short_and_long():
    # 2字中日韩太短trigram索引不到 跳过 整句太长不当精确子串 也跳过
    assert fts_query("ab 我") is None  # 全是短词
    long_cjk = "这是一段很长的中文句子应该整体交给向量检索而不是当精确子串"
    assert fts_query(long_cjk) is None  # 超长中文串不进FTS
    # 但短中文术语该留下
    assert '"登录页面"' in fts_query("登录页面 打不开")


def test_fts_query_multilingual():
    assert fts_query("エラーコード") is not None  # 日文
    assert fts_query("config.yaml") is not None   # 文件名
    assert fts_query("12345") is not None          # 数字
    assert fts_query("") is None
    assert fts_query("a b") is None                # 全是1字符


def test_rrf_fuse_combines_ranks():
    # B两路都靠前 该融合到第一
    vec = ["A", "B", "C"]
    fts = ["B", "D", "A"]
    out = rrf_fuse([vec, fts])
    assert out[0] == "B"
    assert set(out) == {"A", "B", "C", "D"}  # 单路命中的也不丢


def test_rrf_fuse_single_list():
    assert rrf_fuse([["X", "Y"]]) == ["X", "Y"]
    assert rrf_fuse([[]]) == []


def test_rrf_fuse_rewards_agreement():
    # 两路都中的应胜过任一路单独靠前的
    a = ["solo1", "shared", "x"]
    b = ["solo2", "shared", "y"]
    out = rrf_fuse([a, b])
    assert out[0] == "shared", f"两路共识该冒头 实际{out}"
