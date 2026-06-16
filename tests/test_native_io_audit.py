# author: bdth
# email: 2074055628@qq.com
# 板块⑦ 原生IO 重审隐患回归——_geom/_LAST 线程本地隔离、clipboard 恢复守卫、hotkeys 就绪事件

from __future__ import annotations

import threading

import pytest


# ---------- capture._geom 线程本地:并发 agent 的截图->点击坐标互不污染 ----------

def test_geom_is_thread_local():
    from desktop_pet.eyes import capture
    seen = {}
    barrier = threading.Barrier(2)

    def worker(name, geom):
        capture.set_geom(geom)
        barrier.wait()  # 两个线程都设完各自 geom 后再读 全局会被对方覆盖
        seen[name] = capture.current_geom()

    a = threading.Thread(target=worker, args=("A", (0, 0, 1920, 1080)))
    b = threading.Thread(target=worker, args=("B", (1920, 0, 2560, 1440)))
    a.start(); b.start(); a.join(); b.join()
    assert seen["A"] == (0, 0, 1920, 1080), "A 线程的 geom 被别的线程覆盖了"
    assert seen["B"] == (1920, 0, 2560, 1440), "B 线程的 geom 被别的线程覆盖了"


# ---------- elements._last 线程本地:act_element 不会解析到别的 agent 的元素表 ----------

def test_elements_last_is_thread_local():
    from desktop_pet.eyes import elements
    seen = {}
    barrier = threading.Barrier(2)

    def worker(name, items):
        elements._last()[:] = items
        barrier.wait()
        seen[name] = list(elements._last())

    a = threading.Thread(target=worker, args=("A", [{"idx": 1, "tag": "A"}]))
    b = threading.Thread(target=worker, args=("B", [{"idx": 9, "tag": "B"}]))
    a.start(); b.start(); a.join(); b.join()
    assert seen["A"] == [{"idx": 1, "tag": "A"}], "A 的元素表被别的线程覆盖了"
    assert seen["B"] == [{"idx": 9, "tag": "B"}], "B 的元素表被别的线程覆盖了"


# ---------- clipboard 恢复守卫:None / 空快照是 no-op(不碰真实剪贴板) ----------

def test_clipboard_restore_noop_on_empty():
    from desktop_pet.executor import clipboard
    # 不该抛 也不该清空真实剪贴板
    clipboard.restore_clipboard(None)
    clipboard.restore_clipboard({})
    assert hasattr(clipboard, "snapshot_clipboard")


# ---------- hotkeys 就绪事件存在:stop() 投 WM_QUIT 前能等 _tid 就位 ----------

def test_hotkeys_has_ready_event():
    from desktop_pet.hotkeys import GlobalHotkeys
    hk = GlobalHotkeys({})
    assert isinstance(hk._ready, threading.Event), "应有就绪事件供 stop() 等待 _tid 赋值"
    assert not hk._ready.is_set(), "未启动时不该是就绪态"
