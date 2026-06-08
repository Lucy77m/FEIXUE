# author: bdth
# email: 2074055628@qq.com
# 危险命令拦截:匹配灾难性操作并阻止执行

from __future__ import annotations

import re

_CATASTROPHIC: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bformat\s+[a-z]:", re.I), "formatting a disk"),
    (re.compile(r"\bdiskpart\b", re.I), "diskpart partitioning"),
    (re.compile(r"\b(?:clear-disk|remove-partition|initialize-disk)\b", re.I), "disk / partition wipe"),
    (re.compile(r"\bcipher\s+/w\b", re.I), "cipher /w wiping free disk space"),
    (re.compile(r"\breg\s+delete\s+hk(?:lm|ey_local_machine)\b[^\n]*?\s/f\b", re.I),
     "force-deleting the HKLM registry hive"),
    (re.compile(r"\b(?:shutil\.rmtree|os\.removedirs)\s*\(\s*[\"'](?:[a-z]:\\{0,2}|/|~)[\"']\s*\)", re.I),
     "recursively deleting a drive root"),
)

_DELETE_VERB = re.compile(r"\b(?:remove-item|ri|rd|rmdir|del|rm)\b", re.I)
_RECURSE_OR_FORCE = re.compile(
    r"(?:/s\b|/q\b|-recurse\b|-force\b|-r\b|"
    r"-[rfvdi]*r[rfvdi]*f[rfvdi]*\b|"
    r"-[rfvdi]*f[rfvdi]*r[rfvdi]*\b)",
    re.I,
)
_BARE_ROOT = re.compile(
    r"(?:[a-z]:\\{1,2}(?:windows\\?system32|windows|users)?|/|~)(?=[\s\"'*]|$)", re.I
)


def check_blocked(text: str) -> str | None:
    for pattern, reason in _CATASTROPHIC:
        if pattern.search(text):
            return reason
    if _DELETE_VERB.search(text) and _RECURSE_OR_FORCE.search(text) and _BARE_ROOT.search(text):
        return "recursively deleting a drive root / system directory"
    return None
