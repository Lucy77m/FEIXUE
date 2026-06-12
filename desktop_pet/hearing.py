# author: bdth
# email: 2074055628@qq.com
# 听觉 sensevoice本地识别 全程离线
# 两种入口 按住热键说话(松开发送) 唤醒词"墨池"(说完静音自动发送)
# 模型按需下载 没下载就完全沉默

from __future__ import annotations

import queue
import threading
import time

from desktop_pet.settings import DATA_DIR

HEAR_DIR = DATA_DIR / "hearing"
_SR = 16000
_CHUNK = 1600  # 100ms

_DL_BASE = "https://github.com/dulaiduwang003/MOCHI/releases/download/models"
_FILES = {  # 键是短名 值是release文件名和进度权重
    "sv_model": ("hear-sv-model.int8.onnx", 0.90),
    "sv_tokens": ("hear-sv-tokens.txt", 0.01),
    "vad": ("hear-vad.onnx", 0.01),
    "kws_encoder": ("hear-kws-encoder.onnx", 0.05),
    "kws_decoder": ("hear-kws-decoder.onnx", 0.02),
    "kws_joiner": ("hear-kws-joiner.onnx", 0.005),
    "kws_tokens": ("hear-kws-tokens.txt", 0.005),
}
DOWNLOAD_SIZE_HINT = "250MB"

_WAKE_KEYWORD = "m ò ch í @墨池"
_TALK_CAP_S = 10.0     # 单次说话硬上限 浮条带倒计时
_WAKE_IDLE_S = 6.0     # 唤醒后一直没人说话就收回
_PARTIAL_EVERY = 0.6   # 部分识别刷新间隔
_PARTIAL_WIN_S = 10.0  # 实时识别只看最近这几秒 不然越说越卡

_enabled = False
_wake_on = False
_shutdown = threading.Event()
_loop_thread: "threading.Thread | None" = None
_lock = threading.Lock()

_talk_req = threading.Event()    # 热键按下
_talk_end = threading.Event()    # 热键松开
_audio_q: "queue.Queue" = queue.Queue()

_recognizer = None
_kws = None
_vad_cfg = None
_model_lock = threading.Lock()  # 预热线程和工作线程都会触发加载
_warming = False

# 回调由app注入 全在工作线程触发 注意转qt信号
cb_partial = None   # (text) 说话中的实时文本
cb_final = None     # (text) 一句定稿
cb_state = None     # 回调收状态名 idle listening wake_hit 三种
cb_tick = None      # 回调收采集中剩余秒数 给浮条画倒计时
cb_busy = None      # app注入 返回True表示正在思考执行任务 热键和唤醒词都无视
cb_wake_block = None  # app注入 返回True只屏蔽唤醒词 比如开会 热键仍可用

_capturing = False  # 正在采集一句 防热键重入
_STALL_S = 5.0      # 麦克风这么久没出声当它死了 多半是系统休眠回来 重开


def _app_busy() -> bool:
    try:
        return bool(cb_busy()) if cb_busy is not None else False
    except Exception:
        return False


def _wake_blocked() -> bool:
    try:
        return bool(cb_wake_block()) if cb_wake_block is not None else False
    except Exception:
        return False


def _path(key: str):
    return HEAR_DIR / _FILES[key][0]


def is_ready() -> bool:
    return all(_path(k).exists() for k in _FILES)


# ── 下载 ──────────────────────────────────────────────────────

_dl_lock = threading.Lock()
_dl_state = {"state": "idle", "pct": 0.0, "msg": ""}


def download_status() -> dict:
    with _dl_lock:
        st = dict(_dl_state)
    if st["state"] != "downloading" and is_ready():
        st["state"] = "ready"
    return st


def start_download(proxy: str = "") -> None:
    with _dl_lock:
        if _dl_state["state"] == "downloading":
            return
        _dl_state.update(state="downloading", pct=0.0, msg="")
    if is_ready():
        with _dl_lock:
            _dl_state.update(state="idle", pct=0.0)
        return
    threading.Thread(target=_download, args=(proxy,), daemon=True, name="mochi-hear-dl").start()


def _download(proxy: str) -> None:
    try:
        from desktop_pet.settings import build_http_client

        HEAR_DIR.mkdir(parents=True, exist_ok=True)
        done_w = 0.0
        with build_http_client(proxy) as client:
            for key, (name, weight) in _FILES.items():
                dest = _path(key)
                if dest.exists():
                    done_w += weight
                    continue
                tmp = dest.with_suffix(dest.suffix + ".part")
                with client.stream("GET", f"{_DL_BASE}/{name}", follow_redirects=True) as resp:
                    resp.raise_for_status()
                    total = int(resp.headers.get("content-length") or 0)
                    got = 0
                    with open(tmp, "wb") as fh:
                        for chunk in resp.iter_bytes(1024 * 256):
                            fh.write(chunk)
                            got += len(chunk)
                            frac = (got / total) if total else 0.0
                            with _dl_lock:
                                _dl_state["pct"] = min(0.999, done_w + weight * frac)
                tmp.replace(dest)
                done_w += weight
        with _dl_lock:
            _dl_state.update(state="idle", pct=1.0, msg="")
        _warmup_async()  # 刚下完就预热 用户第一句不用等冷加载
    except Exception as e:
        for key in _FILES:
            part = _path(key).with_suffix(_path(key).suffix + ".part")
            try:
                part.unlink(missing_ok=True)
            except OSError:
                pass
        with _dl_lock:
            _dl_state.update(state="error", msg=str(e)[:120])


# ── 开关 ──────────────────────────────────────────────────────

def set_enabled(on: bool) -> None:
    """听觉总开关 开了热键说话可用"""
    global _enabled
    _enabled = bool(on) and is_ready()
    if _enabled:
        _warmup_async()
    _kick()


def set_wake_enabled(on: bool) -> None:
    """唤醒词开关 开了麦克风常开跑关键词检测"""
    global _wake_on
    _wake_on = bool(on) and is_ready()
    if _wake_on:
        _warmup_async()
    _kick()


def _warmup_async() -> None:
    """后台预载模型并跑一遍空音频 把首句的冷启动消掉"""
    global _warming
    if _warming or _recognizer is not None:
        return
    _warming = True

    def _go():
        global _warming
        try:
            import numpy as np
            _decode(np.zeros(_SR // 2, dtype=np.float32))
            if _wake_on:
                _load_kws()
        except Exception:
            pass
        finally:
            _warming = False

    threading.Thread(target=_go, daemon=True, name="mochi-hear-warmup").start()


def start_talk() -> None:
    """热键按下 开始听 采集中重按和它正忙时直接忽略"""
    if not _enabled or _capturing or _app_busy():
        return
    _talk_end.clear()
    _talk_req.set()
    _kick()


def stop_talk() -> None:
    """热键松开 定稿发送"""
    _talk_end.set()


def _kick() -> None:
    global _loop_thread
    if not (_enabled or _wake_on):
        return
    with _lock:
        if _loop_thread is not None and _loop_thread.is_alive():
            return
        _loop_thread = threading.Thread(target=_loop, daemon=True, name="mochi-hearing")
        _loop_thread.start()


def shutdown() -> None:
    _shutdown.set()
    _talk_end.set()


# ── 模型加载 ───────────────────────────────────────────────────

def _import_sherpa():
    """sherpa不带ort dll 自己也不静态链 会按名找onnxruntime.dll
    python包的ort是静态嵌在pyd里的 进程里没这个名字 windows就摸到system32的1.17老版本炸掉
    所以按全路径把包里1.24的dll先载进来占住名字"""
    import ctypes
    import os

    import onnxruntime
    dll = os.path.join(os.path.dirname(onnxruntime.__file__), "capi", "onnxruntime.dll")
    if os.path.exists(dll):
        try:
            ctypes.WinDLL(dll)
        except OSError:
            pass
    import sherpa_onnx
    return sherpa_onnx


def _load_recognizer():
    global _recognizer
    with _model_lock:
        if _recognizer is None:
            sherpa_onnx = _import_sherpa()
            _recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=str(_path("sv_model")),
                tokens=str(_path("sv_tokens")),
                num_threads=1,  # 单线程 慢一点但不跟ui抢核 卡动画
                use_itn=True,
                language="auto",
            )
    return _recognizer


def _load_kws():
    global _kws
    with _model_lock:
        if _kws is not None:
            return _kws
        sherpa_onnx = _import_sherpa()
        kw_file = HEAR_DIR / "keywords.txt"
        kw_file.write_text(_WAKE_KEYWORD + "\n", encoding="utf-8")
        _kws = sherpa_onnx.KeywordSpotter(
            tokens=str(_path("kws_tokens")),
            encoder=str(_path("kws_encoder")),
            decoder=str(_path("kws_decoder")),
            joiner=str(_path("kws_joiner")),
            keywords_file=str(kw_file),
            max_active_paths=4,
            keywords_score=2.0,
            keywords_threshold=0.2,
            num_trailing_blanks=1,
            num_threads=1,
            provider="cpu",
        )
    return _kws


def _new_vad():
    sherpa_onnx = _import_sherpa()
    global _vad_cfg
    if _vad_cfg is None:
        cfg = sherpa_onnx.VadModelConfig()
        cfg.silero_vad.model = str(_path("vad"))
        cfg.silero_vad.min_silence_duration = 0.9   # 静音这么久算说完
        cfg.silero_vad.min_speech_duration = 0.2
        cfg.sample_rate = _SR
        _vad_cfg = cfg
    return sherpa_onnx.VoiceActivityDetector(_vad_cfg, buffer_size_in_seconds=_TALK_CAP_S + 5)


def _decode(samples) -> str:
    import numpy as np
    rec = _load_recognizer()
    s = rec.create_stream()
    s.accept_waveform(_SR, np.asarray(samples, dtype=np.float32))
    rec.decode_stream(s)
    return (s.result.text or "").strip()


# ── 主循环 ─────────────────────────────────────────────────────

def _emit(cb, *args) -> None:
    if cb is not None:
        try:
            cb(*args)
        except Exception:
            pass


def _loop() -> None:
    """采音线程外的消费线程 状态机 唤醒检测和说话采集"""
    import numpy as np
    import sounddevice as sd

    try:
        # 降优先级 识别突发不许跟ui抢核卡动画
        import ctypes
        ctypes.windll.kernel32.SetThreadPriority(ctypes.windll.kernel32.GetCurrentThread(), -1)
    except Exception:
        pass
    stream = None
    ks = None
    try:
        def _on_audio(indata, frames, t, status):
            try:
                _audio_q.put_nowait(indata[:, 0].copy())
            except Exception:
                pass

        last_audio = time.monotonic()
        while not _shutdown.is_set():
            if not (_enabled or _wake_on):
                break  # 全关了 线程退出 麦克风释放
            if stream is None:
                stream = sd.InputStream(samplerate=_SR, channels=1, dtype="float32",
                                        blocksize=_CHUNK, callback=_on_audio)
                stream.start()
                last_audio = time.monotonic()

            # 等事件 热键说话或唤醒词命中
            talking_src = None
            if _talk_req.is_set():
                _talk_req.clear()
                talking_src = "hotkey"
            elif _wake_on:
                try:
                    chunk = _audio_q.get(timeout=0.2)
                    last_audio = time.monotonic()
                except queue.Empty:
                    stream = _check_stall(stream, last_audio)
                    continue
                if _wake_blocked():
                    continue  # 开会等场景 唤醒词整个屏蔽 音频直接丢
                kws = _load_kws()
                if ks is None:
                    ks = kws.create_stream()
                ks.accept_waveform(_SR, chunk)
                while kws.is_ready(ks):
                    kws.decode_stream(ks)
                    r = kws.get_result(ks)
                    if r:
                        kws.reset_stream(ks)
                        if _app_busy():
                            continue  # 它正忙 喊名字也装没听见
                        talking_src = "wake"
                        _emit(cb_state, "wake_hit")
                        break
                if talking_src is None:
                    continue
            else:
                # 只开了热键 没在说 闲等
                try:
                    _audio_q.get(timeout=0.2)
                    last_audio = time.monotonic()
                except queue.Empty:
                    stream = _check_stall(stream, last_audio)
                continue

            # ── 采集一句 ──
            global _capturing
            _capturing = True
            _drain(_audio_q)
            _emit(cb_state, "listening")
            buf: list = []
            vad = _new_vad() if talking_src == "wake" else None
            spoke = False
            discard = False
            t0 = time.monotonic()
            last_partial = t0  # 不从0起 否则第一块音频就触发识别 冷加载时会堵住采集
            final_text = ""
            while not _shutdown.is_set():
                if talking_src == "hotkey" and _talk_end.is_set():
                    break
                if (talking_src == "hotkey" and not _enabled) or (talking_src == "wake" and not _wake_on):
                    discard = True  # 说一半被设置面板关掉 这句作废
                    break
                try:
                    chunk = _audio_q.get(timeout=0.3)
                except queue.Empty:
                    chunk = None
                now = time.monotonic()
                if chunk is not None:
                    buf.append(chunk)
                    if vad is not None:
                        vad.accept_waveform(chunk)
                        if not vad.empty():
                            spoke = True  # 出了完整语音段 说明说完静音了
                            break
                        if vad.is_speech_detected():
                            spoke = True
                cap = _TALK_CAP_S if spoke or talking_src == "hotkey" else _WAKE_IDLE_S
                _emit(cb_tick, max(0.0, cap - (now - t0)))
                if now - t0 > cap:
                    break  # 说到上限 或 唤醒后一直没开口
                # 实时部分识别 只看最近一段 整段重解会越说越卡
                if buf and now - last_partial >= _PARTIAL_EVERY:
                    last_partial = now
                    try:
                        win = np.concatenate(buf)
                        n_win = int(_PARTIAL_WIN_S * _SR)
                        if len(win) > n_win:
                            win = win[-n_win:]
                        partial = _decode(win)
                        if partial:
                            _emit(cb_partial, partial)
                    except Exception:
                        pass
            if _shutdown.is_set():
                discard = True  # 退出途中不再解码外发
            if talking_src == "wake" and not spoke:
                discard = True  # 误唤醒只录到环境噪音 解出来是幻觉文本 不许外发
            if not discard:
                # 识别解码期间积压的尾音补回来 不然松开瞬间说的话被吃掉
                cap_n = int((_TALK_CAP_S + 2.0) * _SR)
                total = sum(len(c) for c in buf)
                try:
                    while total < cap_n:
                        tail = _audio_q.get_nowait()
                        buf.append(tail)
                        total += len(tail)
                except queue.Empty:
                    pass
            if buf and not discard:
                try:
                    final_text = _decode(np.concatenate(buf))
                except Exception:
                    final_text = ""
            if final_text:
                _emit(cb_final, final_text)  # 先定稿再idle ui按这个顺序收尾
            _emit(cb_state, "idle")
            _capturing = False
            _talk_req.clear()  # 采集期间的重按作废
            _talk_end.clear()
            if ks is not None:
                ks = None  # 唤醒流重建 防残留
    except Exception:
        _emit(cb_state, "idle")
    finally:
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        _drain(_audio_q)
        global _loop_thread
        _capturing = False  # 异常中途退出也不能卡死下一次按键
        with _lock:
            _loop_thread = None
        # 退出的瞬间开关又被打开 比如快速切设置 自己再拉起来 不然听觉静默失效
        if not _shutdown.is_set() and (_enabled or _wake_on):
            _kick()


def _drain(q) -> None:
    try:
        while True:
            q.get_nowait()
    except queue.Empty:
        pass


def _check_stall(stream, last_audio: float):
    """麦克风长时间没出声(系统休眠回来设备易死) 关掉让外层重开"""
    if stream is not None and time.monotonic() - last_audio > _STALL_S:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
        return None
    return stream
