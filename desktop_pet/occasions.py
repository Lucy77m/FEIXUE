# author: bdth
# email: 2074055628@qq.com
# 时刻/节日感知:公历节日 + 你的生日。命中时返回一句给模型的应景"由头"，让它自然道一句。

from __future__ import annotations

import re
from datetime import datetime

_FESTIVALS = {
    "01-01": "元旦",
    "02-14": "情人节",
    "04-01": "愚人节",
    "06-01": "儿童节",
    "10-31": "万圣节",
    "12-24": "平安夜",
    "12-25": "圣诞节",
    "12-31": "跨年夜",
}


def _norm_md(raw: str) -> str:
    """把用户随手填的生日规范成 'MM-DD'：'6-2'、'6/2'、'06-02'、'2026-06-02' 都认；认不出返回 ''。"""
    nums = re.findall(r"\d+", raw or "")
    if len(nums) < 2:
        return ""
    try:
        month, day = int(nums[-2]), int(nums[-1])
    except ValueError:
        return ""
    if 1 <= month <= 12 and 1 <= day <= 31:
        return f"{month:02d}-{day:02d}"
    return ""


def today_key(now: datetime, birthday: str = "") -> str | None:
    """今天是不是特别的日子；是则返回一个稳定 key(供去重)，否则 None。"""
    md = now.strftime("%m-%d")
    if _norm_md(birthday) == md:
        return "birthday"
    if md in _FESTIVALS:
        return "festival:" + md
    return None


def describe(key: str) -> str:
    """把 key 翻成给模型的中文"由头"(模型会用用户的语言回应)。"""
    if key == "birthday":
        return "今天是 ta 的生日"
    if key.startswith("festival:"):
        return "今天是" + _FESTIVALS.get(key.split(":", 1)[1], "一个特别的日子")
    return ""
