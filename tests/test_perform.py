# 演出状态机回归 点名粘性 软硬打断 让位
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

if QApplication.instance() is None:
    QApplication([])

from desktop_pet.pet.activities import _ACTIVITIES
from desktop_pet.pet.character import BlobPet

NAME = list(_ACTIVITIES)[0]


def test_sticky_survives_talking():
    p = BlobPet()
    assert p.start_activity(NAME)
    p._talking = True
    p._advance_activity(0.1)
    assert p._activity == NAME


def test_hard_interrupt_ends_sticky():
    p = BlobPet()
    assert p.start_activity(NAME)
    p._dragging = True
    p._advance_activity(0.1)
    assert p._activity is None


def test_self_play_yields_to_talking():
    p = BlobPet()
    p._activity = NAME
    p._act_sticky = False
    p._costume = _ACTIVITIES[NAME][0]
    p._talking = True
    p._advance_activity(0.1)
    assert p._activity is None


def test_react_dropped_during_sticky():
    p = BlobPet()
    assert p.start_activity(NAME)
    p.react("celebrate")
    assert p._react is None
    p._advance_activity(0.1)
    assert p._activity == NAME


def test_user_message_yields_performance():
    """用户来新消息 粘性退掉 思考姿势接管"""
    p = BlobPet()
    assert p.start_activity(NAME)
    p.yield_performance()
    p._busy = True
    p._advance_activity(0.1)
    assert p._activity is None


def test_pending_perform_waits_for_idle():
    """点名先入队 忙完才播"""
    p = BlobPet()
    p._busy = True
    assert p.perform(NAME)
    p.advance(0.05)
    assert p._activity is None, "忙时不该开播"
    p._busy = False
    p.advance(0.05)
    assert p._activity == NAME, "闲下来该开播了"
    assert p._act_sticky


@pytest.mark.parametrize("name", list(_ACTIVITIES))
def test_every_activity_plays_to_finish(name):
    """68个小品每个完整走完所有阶段 不崩不卡"""
    p = BlobPet()
    assert p.start_activity(name)
    guard = 0
    while p._activity is not None and guard < 100000:
        p._advance_activity(0.05)
        p.advance(0.05)
        guard += 1
    assert p._activity is None, f"{name} 演不完"
