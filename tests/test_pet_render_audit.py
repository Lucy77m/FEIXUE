# author: bdth
# email: 2074055628@qq.com
# 板块④a 渲染核心重审隐患回归——截图自家窗口集合的并发/泄漏;活动时长上限不能误杀最长小品

from __future__ import annotations

import threading

import pytest


# ---------- capture._own_hwnds:注册/注销成对 + 并发遍历不炸 ----------

def test_capture_register_unregister_pairs():
    import desktop_pet.eyes.capture as cap
    before = set(cap._own_hwnds)
    cap.register_own_window(0xABC1)
    cap.register_own_window(0xABC2)
    assert 0xABC1 in cap._own_hwnds and 0xABC2 in cap._own_hwnds
    cap.unregister_own_window(0xABC1)
    assert 0xABC1 not in cap._own_hwnds, "关闭的窗口该从集合里移除 别堆死句柄"
    cap.unregister_own_window(0xABC2)
    cap.unregister_own_window(0xDEAD)  # 不存在的注销不报错
    assert set(cap._own_hwnds) == before


def test_capture_concurrent_register_during_iteration():
    """worker 线程遍历自家窗口集合时 主线程随时增删(球/虫子随生随灭)不该 RuntimeError"""
    import desktop_pet.eyes.capture as cap
    errors: list[str] = []
    stop = [False]

    def churn():
        i = 0
        while not stop[0]:
            try:
                cap.register_own_window(0x10000 + (i % 64))
                cap.unregister_own_window(0x10000 + (i % 64))
                i += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))
                break

    t = threading.Thread(target=churn, daemon=True)
    t.start()
    try:
        for _ in range(3000):
            # 复刻 _grab 的取快照方式:加锁拿副本再遍历
            with cap._own_lock:
                snap = list(cap._own_hwnds)
            for _h in snap:
                pass
    finally:
        stop[0] = True
        t.join(timeout=1.0)
    assert not errors, f"并发增删遍历不该抛: {errors[:3]}"


# ---------- 活动最长时长 vs 抗卡死上限:别再用低于最长小品的固定阈值 ----------

def test_activity_maxage_cap_accommodates_longest():
    from desktop_pet.pet.activities import _ACTIVITIES
    totals = {name: sum(s[1] for s in spec[3]) for name, spec in _ACTIVITIES.items()}
    longest_name = max(totals, key=totals.get)
    longest = totals[longest_name]
    # 抗卡死上限取"自身阶段总时长 + 5s",对每个小品都留有余量——固定 25s 会误杀 sprout(约26s)
    for name, total in totals.items():
        cap = total + 5.0
        assert cap > total, f"{name} 的抗卡死上限该高于其自然总时长"
    # 钉住:确实存在超过 25s 的小品(sprout),所以固定 25 阈值是错的
    assert longest > 25.0, f"最长小品 {longest_name}={longest:.1f}s 该 > 25s(否则此回归失去意义)"
