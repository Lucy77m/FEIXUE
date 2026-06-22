# 主循环集成场景 由test_mainloop以子进程方式运行 退出码0即通过
# 钉的是单元测试摸不到的东西 线程亲和 信号派发 完整回路 UI心跳
# 那次mixin槽卡死就是函数全对但派发线程错位 这里就是为再也不踩它

from __future__ import annotations

import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("FEIXUE_DATA_DIR", tempfile.mkdtemp(prefix="feixue_itest_"))

FAILS: list[str] = []


def check(ok: bool, what: str) -> None:
    if not ok:
        FAILS.append(what)


def main() -> int:
    from PySide6.QtCore import QTimer

    # 探针挂在被调对象上 不碰slot本身 slot被patch会改变派发行为
    import desktop_pet.pet.chat as chat
    ui_threads: dict[str, str] = {}

    def probe(name, orig):
        def f(self, *a, **k):
            ui_threads.setdefault(name, threading.current_thread().name)
            return orig(self, *a, **k)
        return f

    chat.ThoughtBubbles.start = probe("think.start", chat.ThoughtBubbles.start)
    chat.ThoughtBubbles.stop = probe("think.stop", chat.ThoughtBubbles.stop)
    chat.SpeechText.speak = probe("speech.speak", chat.SpeechText.speak)

    state = {"worker_thread": "", "reply": "", "busy_seq": []}

    # 关掉退避重试 这个场景测回路机制不测退避时序 退避归test_retry管
    # 不关的话连接错误要退避1+2+4秒 把回路拖过观测窗口
    import desktop_pet.agent.loop as loop_mod
    loop_mod._RETRY_MAX = 0

    # 在Agent.run上包探针记执行线程 千万不能动信号连接
    # 教训 拿普通函数顶掉queued slot会让派发退化成direct 把agent拉回主线程
    from desktop_pet.agent.loop import Agent
    orig_run = Agent.run

    def spy_run(self, *a, **k):
        state["worker_thread"] = threading.current_thread().name
        return orig_run(self, *a, **k)
    Agent.run = spy_run

    from desktop_pet.app.core import PetApp
    pa = PetApp()
    # 指到打不开的地址 逼出错误回复 链路本身必须完整走通
    pa._settings.api_key = "itest"
    pa._settings.base_url = "http://127.0.0.1:1"
    pa._shown = True  # 真实里能打字就说明桌宠已在屏上 回复上屏前会校验 _shown
    pa._thread.start()

    def on_reply(raw: str) -> None:
        state["reply"] = raw
        QTimer.singleShot(1500, finish)  # 留点时间让busy收尾和think.stop走完
    pa._worker.reply_ready.connect(on_reply)
    pa._worker.busy_changed.connect(lambda b: state["busy_seq"].append(b))

    beats = [0]
    hb = QTimer()
    hb.timeout.connect(lambda: beats.__setitem__(0, beats[0] + 1))
    hb.start(50)

    QTimer.singleShot(300, lambda: pa._input.submitted.emit("集成测试你好", None))

    done = {"ran": False}

    def finish() -> None:
        if done["ran"]:
            return
        done["ran"] = True
        # 回路 错误回复必须回来且是人话
        check(bool(state["reply"]), "发消息后没有任何回复返回")
        check("[" not in state["reply"][:1], f"回复像原始错误而非人话: {state['reply'][:60]}")
        # 线程亲和 worker干活在工人线程 UI演出在主线程
        check(state["worker_thread"] not in ("", "MainThread"),
              f"agent没有在工人线程跑: {state['worker_thread']!r}")
        for name, thr in ui_threads.items():
            check(thr == "MainThread", f"UI对象 {name} 在 {thr} 被操作 必须是MainThread")
        check("speech.speak" in ui_threads, "回复没有走到speech.speak上屏")
        check("think.start" in ui_threads and "think.stop" in ui_threads,
              f"思考气泡未按busy开合: {sorted(ui_threads)}")
        # busy必须先True后False地闭合
        check(state["busy_seq"][:1] == [True] and state["busy_seq"][-1:] == [False],
              f"busy序列不闭合: {state['busy_seq']}")
        # UI心跳 50ms一跳 全程没冻住
        check(beats[0] >= 60, f"UI心跳过少({beats[0]}) 事件循环疑似被卡")
        try:
            pa._worker.shutdown()  # 收掉shell和python子进程
            pa._thread.quit()
            pa._thread.wait(2000)
        except Exception:
            pass
        if FAILS:
            sys.stderr.write("\n".join("FAIL: " + f for f in FAILS) + "\n")
            sys.stderr.flush()
            os._exit(1)
        sys.stdout.write("mainloop integration OK\n")
        sys.stdout.flush()
        os._exit(0)

    QTimer.singleShot(9000, finish)

    def watchdog() -> None:
        # 整个场景15秒兜底 防卡死挂住CI
        import time
        last, still = -1, 0
        for _ in range(60):
            time.sleep(0.25)
            if beats[0] == last:
                still += 1
                if still >= 12:  # 3秒没心跳 判死
                    sys.stderr.write("FAIL: UI事件循环卡死 3秒无心跳\n")
                    sys.stderr.flush()
                    os._exit(2)
            else:
                still = 0
            last = beats[0]
        sys.stderr.write("FAIL: 场景超时未结束\n")
        sys.stderr.flush()
        os._exit(3)

    threading.Thread(target=watchdog, daemon=True).start()
    return pa._app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
