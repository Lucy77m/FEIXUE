# author: bdth
# email: 2074055628@qq.com
# 传感伴生 体征麦克风下载桌面天气和密码守门

from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from desktop_pet import i18n, presence, somatic, stats
from desktop_pet.agent import prompts as agent_prompts
from desktop_pet.emotion.state import emotion

_AWAY_S = 150.0
_SHY_POLL_MS = 2500
_SHY_POP_COOLDOWN_S = 120.0
_VITALS_POLL_MS = 10_000
_HOT_POP_COOLDOWN_S = 600.0
_MEM_POP_COOLDOWN_S = 900.0
_SNUGGLE_COOLDOWN_S = 3600.0
_DL_POLL_MS = 30_000
_MIC_POLL_MS = 30_000
_DESK_POLL_MS = 3600_000
_DESK_LIMIT = 40


class Sensors(QObject):
    _shy_changed = Signal(bool)
    _vitals_ready = Signal(object)
    _dl_found = Signal(str)
    _mic_changed = Signal(bool)
    _desk_crowded = Signal(int)
    _weather_ready = Signal(str)

    def __init__(self, host) -> None:
        super().__init__()
        self._host = host
        self._shy_timer = QTimer(self)
        self._shy_timer.timeout.connect(self._check_password_focus)
        self._shy_now = False
        self._shy_checking = False
        self._shy_last_pop = 0.0
        self._shy_changed.connect(self._on_shy_changed)
        self._vitals_timer = QTimer(self)
        self._vitals_timer.timeout.connect(self._check_vitals)
        self._vitals_busy = False
        self._vitals_ready.connect(self._on_vitals)
        self._dl_timer = QTimer(self)
        self._dl_timer.timeout.connect(self._check_downloads)
        self._dl_busy = False
        self._dl_seen: set[str] = set()
        self._dl_baseline = time.time()
        self._dl_found.connect(self._on_dl_found)
        self._mic_timer = QTimer(self)
        self._mic_timer.timeout.connect(self._check_mic)
        self._mic_busy = False
        self._mic_changed.connect(self._on_mic_changed)
        self._desk_timer = QTimer(self)
        self._desk_timer.timeout.connect(self._check_desktop)
        self._desk_busy = False
        self._desk_crowded.connect(self._on_desk_crowded)
        self._weather_timer = QTimer(self)
        self._weather_timer.timeout.connect(self._check_weather)
        self._weather_busy = False
        self._weather_kind = ""
        self._weather_ready.connect(self._on_weather)
        QTimer.singleShot(60_000, self._check_weather)
        self._hot_on = False
        self._cpu_high_n = 0
        self._hot_last_pop = 0.0
        self._squeeze_on = False
        self._mem_last_pop = 0.0
        self._lowbatt_on = False
        self._blanket_on = False
        self._late_popped_date = ""
        self._cpu_idle_n = 0
        self._cpu_warm_n = 0
        self._snuggle_last = 0.0

    def start(self) -> None:
        self._shy_timer.start(_SHY_POLL_MS)
        self._vitals_timer.start(_VITALS_POLL_MS)
        self._dl_timer.start(_DL_POLL_MS)
        self._mic_timer.start(_MIC_POLL_MS)
        self._desk_timer.start(_DESK_POLL_MS)
        self._weather_timer.start(2 * 3600 * 1000)

    def stop(self) -> None:
        """退出前停全部轮询 不再孵新线程"""
        for t in (self._shy_timer, self._vitals_timer, self._dl_timer,
                  self._mic_timer, self._desk_timer, self._weather_timer):
            try:
                t.stop()
            except Exception:
                pass

    def _check_password_focus(self) -> None:
        """低频看一眼焦点是不是密码框 是就捂眼"""
        if self._shy_checking or not self._host._settings.allow_control:
            return
        if not self._host._pet.isVisible():
            return
        self._shy_checking = True
        threading.Thread(target=self._shy_probe_thread, daemon=True).start()

    def _shy_probe_thread(self) -> None:
        try:
            from desktop_pet.eyes import uia
            is_pwd = uia.focused_is_password()
            if is_pwd != self._shy_now:
                self._shy_changed.emit(is_pwd)
        except Exception:
            pass
        finally:
            self._shy_checking = False

    @Slot(bool)
    def _on_shy_changed(self, shy: bool) -> None:
        self._shy_now = shy
        self._host._pet.set_shy(shy)
        if shy:
            now = time.time()
            if now - self._shy_last_pop > _SHY_POP_COOLDOWN_S:
                self._shy_last_pop = now
                self._host._feed_pop(i18n.t("pwd_shy"))

    def _check_vitals(self) -> None:
        """十秒一次读机器体征 后台线程采"""
        if self._vitals_busy:
            return
        self._vitals_busy = True
        threading.Thread(target=self._vitals_thread, daemon=True).start()

    def _vitals_thread(self) -> None:
        try:
            import psutil
            cpu = psutil.cpu_percent(None)
            mem = psutil.virtual_memory().percent
            b = psutil.sensors_battery()
            batt = (b.percent, b.power_plugged) if b is not None else None
            self._vitals_ready.emit({"cpu": cpu, "mem": mem, "batt": batt})
        except Exception:
            pass
        finally:
            self._vitals_busy = False

    @Slot(object)
    def _on_vitals(self, v: dict) -> None:
        """体征状态机 拟态进退都带迟滞"""
        if not self._host._pet.isVisible():
            return
        now = time.time()
        cpu, mem, batt = v["cpu"], v["mem"], v["batt"]
        # cpu高烧 连续两次85进 70退
        self._cpu_high_n = self._cpu_high_n + 1 if cpu >= 85 else 0
        if not self._hot_on and self._cpu_high_n >= 2:
            self._hot_on = True
            self._host._pet.set_hot(True)
            somatic.set_state("hot", agent_prompts.SOMA_HOT_STATE)
            if now - self._hot_last_pop > _HOT_POP_COOLDOWN_S:
                self._hot_last_pop = now
                self._host._feed_pop(i18n.t("hot_cpu"))
        elif self._hot_on and cpu < 70:
            self._hot_on = False
            self._host._pet.set_hot(False)
            somatic.set_state("hot", None)
        # 内存挤压 88进 80退 95再喊
        if not self._squeeze_on and mem >= 88:
            self._squeeze_on = True
            self._host._pet.set_squeeze(True)
        elif self._squeeze_on and mem < 80:
            self._squeeze_on = False
            self._host._pet.set_squeeze(False)
        if self._squeeze_on and mem >= 95 and now - self._mem_last_pop > _MEM_POP_COOLDOWN_S:
            self._mem_last_pop = now
            self._host._feed_pop(i18n.t("mem_full"))
        # 低电量 20进 25或插电退
        if batt is not None:
            pct, plugged = batt
            if not self._lowbatt_on and pct <= 20 and not plugged:
                self._lowbatt_on = True
                self._host._pet.set_low_batt(True)
                self._host._feed_pop(i18n.t("low_batt").format(pct=int(pct)))
            elif self._lowbatt_on and (pct >= 25 or plugged):
                self._lowbatt_on = False
                self._host._pet.set_low_batt(False)
        # 深夜盖被子 23点半到凌晨5点
        dt_now = datetime.now()
        late = (dt_now.hour == 23 and dt_now.minute >= 30) or dt_now.hour < 5
        if late and not self._blanket_on:
            self._blanket_on = True
            self._host._pet.set_blanket(True)
            today = dt_now.date().isoformat()
            if self._late_popped_date != today and presence.idle_seconds() < _AWAY_S:
                self._late_popped_date = today
                streak = stats.mark_late_night()
                self._host._feed_react("yawn")
                if streak >= 3:
                    self._host._feed_pop(i18n.t("late_night_streak").format(n=streak))
                else:
                    self._host._feed_pop(i18n.t("late_night"))
        elif not late and self._blanket_on:
            self._blanket_on = False
            self._host._pet.set_blanket(False)
        # 冬天机器发热 凑过去蹭暖
        warm_month = dt_now.month in (12, 1, 2)
        self._cpu_warm_n = self._cpu_warm_n + 1 if cpu >= 55 else 0
        if (warm_month and self._cpu_warm_n >= 3 and not self._hot_on
                and now - self._snuggle_last > _SNUGGLE_COOLDOWN_S
                and not self._host._engaged() and not self._host._pet.is_asleep):
            self._snuggle_last = now
            self._host._feed_react("snuggle")
            self._host._feed_pop(i18n.t("snuggle_warm"))
        # 机器真闲了五分钟 拿毛线球出来玩
        self._cpu_idle_n = self._cpu_idle_n + 1 if cpu < 15 else 0
        if (self._cpu_idle_n >= 30 and now - getattr(self, "_yarn_last", 0.0) > 7200
                and not self._host._engaged() and not self._host._pet.is_asleep):
            self._yarn_last = now
            self._cpu_idle_n = 0
            self._host._feed_perform("yarn")

    def _check_downloads(self) -> None:
        """盯下载目录 新文件落地就提一嘴"""
        if self._dl_busy or self._host._meeting_mode or not self._host._pet.isVisible():
            return
        self._dl_busy = True
        threading.Thread(target=self._dl_thread, daemon=True).start()

    def _dl_thread(self) -> None:
        try:
            folder = Path.home() / "Downloads"
            if not folder.is_dir():
                return
            now = time.time()
            for p in folder.iterdir():
                try:
                    if not p.is_file() or p.suffix.lower() in (".crdownload", ".part", ".tmp", ".download"):
                        continue
                    st = p.stat()
                    # 启动之后新出现的 且写完稳定了几秒
                    if st.st_mtime > self._dl_baseline and 4 < now - st.st_mtime < 120 and p.name not in self._dl_seen:
                        self._dl_seen.add(p.name)
                        self._dl_found.emit(p.name)
                        return
                except OSError:
                    continue
        except Exception:
            pass
        finally:
            self._dl_busy = False

    @Slot(str)
    def _on_dl_found(self, name: str) -> None:
        self._host._feed_react("perk_up")
        self._host._feed_pop(i18n.t("dl_done").format(name=name[:36]))

    def _check_mic(self) -> None:
        """读注册表看麦克风是否被占用 开会自动安静"""
        if self._mic_busy:
            return
        self._mic_busy = True
        threading.Thread(target=self._mic_thread, daemon=True).start()

    def _mic_thread(self) -> None:
        try:
            import winreg
            in_use = False
            base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone\NonPackaged"
            try:
                root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, base)
            except OSError:
                root = None
            if root is not None:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(root, i)
                        i += 1
                    except OSError:
                        break
                    try:
                        with winreg.OpenKey(root, sub) as k:
                            stop, _ = winreg.QueryValueEx(k, "LastUsedTimeStop")
                            if int(stop) == 0:  # 还没停就是正在用
                                in_use = True
                                break
                    except OSError:
                        continue
                winreg.CloseKey(root)
            if in_use != self._host._meeting_mode:
                self._mic_changed.emit(in_use)
        except Exception:
            pass
        finally:
            self._mic_busy = False

    @Slot(bool)
    def _on_mic_changed(self, in_use: bool) -> None:
        if in_use and not self._host._meeting_mode:
            self._host._thought.pop(i18n.t("meeting_on"), self._host._pet)  # 进静音前最后说一句
            self._host._meeting_mode = True
            somatic.set_state("meeting", agent_prompts.SOMA_MEETING_STATE)
        elif not in_use and self._host._meeting_mode:
            self._host._meeting_mode = False
            somatic.set_state("meeting", None)
            self._host._thought.pop(i18n.t("meeting_off"), self._host._pet)

    def _check_desktop(self) -> None:
        """桌面图标太多了 让agent提议收拾"""
        if self._desk_busy or self._host._meeting_mode:
            return
        self._desk_busy = True
        threading.Thread(target=self._desk_thread, daemon=True).start()

    def _desk_thread(self) -> None:
        try:
            desk = Path.home() / "Desktop"
            if not desk.is_dir():
                return
            n = sum(1 for p in desk.iterdir() if p.is_file() and p.suffix.lower() != ".lnk")
            if n >= _DESK_LIMIT:
                today = datetime.now().date().isoformat()
                if stats.get_note("desk_tidy") != today:
                    stats.set_note("desk_tidy", today)
                    self._desk_crowded.emit(n)
        except Exception:
            pass
        finally:
            self._desk_busy = False

    @Slot(int)
    def _on_desk_crowded(self, n: int) -> None:
        if self._host._worker.is_running:
            return
        self._host.request_message.emit(agent_prompts.DESK_TIDY_MSG.format(n=n))

    def _check_weather(self) -> None:
        """两小时问一次天气 拟态跟着换 —— 默认关(IP定位常常离谱)；开了才按IP查它自己小世界的天气"""
        if self._weather_busy or not self._host._settings.allow_web:
            return
        if not getattr(self._host._settings, "weather_enabled", False):
            if self._weather_kind:  # 关掉了就把残留的伞和雪收走
                self._weather_ready.emit("")
            return
        self._weather_busy = True
        threading.Thread(target=self._weather_thread, daemon=True).start()

    def _weather_thread(self) -> None:
        try:
            from desktop_pet.settings import build_http_client
            client = build_http_client(self._host._settings.proxy)
            r = client.get("https://wttr.in/?format=j1", timeout=15)
            cur = r.json()["current_condition"][0]
            temp = float(cur.get("temp_C", 20))
            precip = float(cur.get("precipMM", 0) or 0)
            kind = ""
            if temp >= 33:
                kind = "melt"
            elif precip > 0.1:
                kind = "snow" if temp <= 2 else "rain"
            self._weather_ready.emit(kind)
        except Exception:
            pass
        finally:
            self._weather_busy = False

    @Slot(str)
    def _on_weather(self, kind: str) -> None:
        if kind == self._weather_kind:
            return
        self._weather_kind = kind
        self._host._pet.set_weather(kind)
        somatic.set_state("weather", agent_prompts.SOMA_WEATHER.get(kind))
        if kind:
            self._host._feed_pop(i18n.t("weather_" + kind))
