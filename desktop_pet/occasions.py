# 节日感知 公历节日命中返回应景由头

from __future__ import annotations

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


def today_key(now: datetime) -> str | None:
    """公历节日命中返回稳定key"""
    md = now.strftime("%m-%d")
    if md in _FESTIVALS:
        return "festival:" + md
    return None


def describe(key: str) -> str:
    """key转应景描述 认不出回空串"""
    if key.startswith("festival:"):
        return "今天是" + _FESTIVALS.get(key.split(":", 1)[1], "一个特别的日子")
    return ""
