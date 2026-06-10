# author: bdth
# email: 2074055628@qq.com
# 危险命令拦截

from __future__ import annotations

import re

# 灾难级操作直接 block 不给确认机会
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

# 删除动词 跟递归强制和裸根三者一起判
_DELETE_VERB = re.compile(r"\b(?:remove-item|ri|rd|rmdir|del|rm)\b", re.I)
# 递归强制 flag 黏连短 flag 也命中
_RECURSE_OR_FORCE = re.compile(
    r"(?:/s\b|/q\b|-recurse\b|-force\b|-r\b|"
    r"-[rfvdi]*r[rfvdi]*f[rfvdi]*\b|"
    r"-[rfvdi]*f[rfvdi]*r[rfvdi]*\b)",
    re.I,
)
# 裸根和系统目录 带子路径的不算
_BARE_ROOT = re.compile(
    r"(?:[a-z]:[\\/]{1,2}(?:windows[\\/]?system32|windows|users)?(?=[\s\"'*]|$)"
    r"|(?<![^\s\"'=])(?:/|~/?)(?=[\s\"'*]|$))",
    re.I,
)


def check_blocked(text: str) -> str | None:
    """硬拦截 命中返回原因 否则 None"""
    for pattern, reason in _CATASTROPHIC:
        if pattern.search(text):
            return reason
    # 删除动词加递归强制加裸根 三个凑齐才拦
    if _DELETE_VERB.search(text) and _RECURSE_OR_FORCE.search(text) and _BARE_ROOT.search(text):
        return "recursively deleting a drive root / system directory"
    return None


# 危险但不必然致命 只提醒确认不硬拦
_RISKY: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bgit\s+push\b[^\n|;&]*(?:--force(?:-with-lease)?\b|\s-f\b)", re.I),
     "git 强制推送（覆盖远端历史）"),
    (re.compile(r"\bgit\s+reset\s+--hard\b", re.I), "git reset --hard（丢弃未提交的修改）"),
    (re.compile(r"\bgit\s+clean\b[^\n|;&]*\s-[a-z]*[fx]", re.I), "git clean（删除未跟踪的文件）"),
    (re.compile(r"\bgit\s+checkout\s+--\s", re.I), "git checkout --（丢弃文件的未提交修改）"),
    (re.compile(r"\b(?:shutdown|restart-computer|stop-computer)\b", re.I), "关机 / 重启电脑"),
    (re.compile(r"\bformat-volume\b", re.I), "格式化卷"),
    (re.compile(r"\breg\s+delete\b", re.I), "删除注册表项"),
    (re.compile(r"\bremove-itemproperty\b", re.I), "删除注册表值"),
    (re.compile(r"\bshutil\.rmtree\s*\(", re.I), "递归删除目录（shutil.rmtree）"),
)

# git rm --cached 算白名单 兜底前先抠掉
_GIT_RM_CACHED = re.compile(r"\bgit\s+rm\b[^\n|;&]*--cached\b", re.I)


def check_risky(text: str) -> str | None:
    """软警告 命中返回中文原因 已 block 的不重复警告"""
    if check_blocked(text) is not None:
        return None
    for pattern, reason in _RISKY:
        if pattern.search(text):
            return reason
    # 兜底 删除动词加递归强制就提醒
    stripped = _GIT_RM_CACHED.sub(" ", text)
    if _DELETE_VERB.search(stripped) and _RECURSE_OR_FORCE.search(stripped):
        return "递归 / 强制删除文件或目录"
    return None
