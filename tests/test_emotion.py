# 夸骂识别 否定按小句扫 自指只看紧邻不误伤我觉得你棒

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("FEIXUE_DATA_DIR", tempfile.mkdtemp(prefix="feixue_emo_"))

import pytest  # noqa: E402

from desktop_pet.emotion.state import appraise_user_message as appraise  # noqa: E402


@pytest.mark.parametrize("text, want", [
    # 远距离否定 以前 4 字符窗口看不到否定词会乱判成 scolded
    ("完全没有任何理由说你笨", None),
    ("我不会觉得你这人很笨啊", None),
    ("我觉得你一点都不蠢", None),
    # 紧邻否定 一直能处理
    ("你不笨", None),
    ("我其实一点都不觉得你笨", None),
    # 自指 它在说自己不是夸骂用户
    ("我自己好笨", None),
    # 但我作主语夸或骂对方不该被自指误伤
    ("我觉得你好棒", "praised"),
    # 干净的夸骂
    ("你真笨", "scolded"),
    ("你真棒", "praised"),
    ("谢谢你帮大忙", "praised"),
    ("stupid", "scolded"),
    ("good job", "praised"),
    # 夸骂同时命中或都没命中 不猜
    ("你真棒，但有点笨", None),
    ("今天天气不错啊", None),
])
def test_appraise(text, want):
    assert appraise(text) == want


def test_empty():
    assert appraise("") is None
    assert appraise(None) is None
