# author: bdth
# email: 2074055628@qq.com
# 剪贴板文本的本地启发式分类器：判断复制的是 报错 / 外文 / 代码 / 链接 / 普通

from __future__ import annotations

import re

KINDS = ("error", "foreign", "code", "url", "plain")
INTERESTING = frozenset({"error", "foreign", "code", "url"})

_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)
_CJK_RE = re.compile(r"[一-鿿぀-ヿ가-힯]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_ERR_RE = re.compile(
    r"traceback \(most recent call last\)|\bexception\b|\b\w*error\b|\bpanic:|segmentation fault|"
    r"stack trace|unhandled|\berrno\b|File \"[^\"]+\", line \d+|cannot read propert|"
    r"is not defined|is not a function|command not found|permission denied|"
    r"报错|异常|错误|堆栈|崩溃|栈溢出",
    re.IGNORECASE,
)
_CODE_RE = re.compile(
    r"\b(def|class|function|import|from|const|let|var|public|private|return|elif|"
    r"include|SELECT|INSERT|UPDATE|print|echo)\b|=>|::|->|\};|</?\w+>|#include|\$\(|console\.log",
    re.MULTILINE,
)


def classify(text: str) -> tuple[str, float]:
    """返回 (类别, 置信度0~1)。"""
    s = (text or "").strip()
    if len(s) < 2:
        return ("plain", 0.0)
    if "\n" not in s and _URL_RE.match(s):
        return ("url", 0.95)
    if _ERR_RE.search(s):
        return ("error", 0.9)
    code_hits = len(_CODE_RE.findall(s))
    if code_hits >= 2 or (code_hits >= 1 and "\n" in s and _symbol_ratio(s) > 0.08):
        return ("code", min(0.6 + 0.1 * code_hits, 0.92))
    cjk = len(_CJK_RE.findall(s))
    latin = len(_LATIN_RE.findall(s))
    letters = cjk + latin
    if letters and len(s) >= 20 and cjk / letters < 0.15 and latin >= 12:
        return ("foreign", 0.85 if latin >= 40 else 0.7)
    return ("plain", 0.3)


def is_interesting(kind: str) -> bool:
    return kind in INTERESTING


def _symbol_ratio(s: str) -> float:
    syms = sum(1 for c in s if not c.isalnum() and not c.isspace())
    return syms / max(len(s), 1)
