# author: bdth
# email: 2074055628@qq.com
# 差事mixin 提醒 主动说话 改写 做梦 偷瞄屏幕 反思沉淀

from __future__ import annotations

import copy
import re
import threading
from collections.abc import Callable

from desktop_pet import journal, persona
from desktop_pet.agent import prompts
from desktop_pet.agent.loopdefs import _BACKGROUND_TIMEOUT
from desktop_pet.agent.textops import _parse_json, _strip_think_leak, _strip_toolcall_leak
from desktop_pet.audit import audit
from desktop_pet.memory.store import store


_REFLECT_SEMAPHORE = threading.Semaphore(1)


class DutiesMixin:
    """对话主线之外的零活"""

    def run_timed_task(
        self,
        task: str,
        on_step: Callable[[str], None] | None = None,
        on_think: Callable[[str], None] | None = None,
        on_plan: Callable[[str], None] | None = None,
        on_media: Callable[[str, str, str], None] | None = None,
        on_perform: Callable[[str], bool] | None = None,
        on_control: Callable[[bool, str], None] | None = None,
    ) -> str:
        """跑定时任务 跑完还原对话历史——整套会话状态都要存还原 别让定时任务污染真实对话
        run() 会就地改消息dict(降级旧图片)、清compressed摘要、动known_files/last_active/turn_idx
        所以必须深拷贝 _messages(浅拷贝挡不住就地改dict)并连带快照其它会话字段(对齐 deliver_reminder 的 deepcopy)"""
        snap_messages = copy.deepcopy(self._messages)
        snap_compressed = self._compressed
        snap_known = dict(self._known_files)
        snap_last_active = self._last_active
        snap_turn_idx = self._turn_user_idx
        snap_plan = list(self._plan)
        try:
            return self.run(
                prompts.timed_task_nudge(task), on_step=on_step, on_think=on_think,
                on_plan=on_plan, on_media=on_media, on_perform=on_perform, on_control=on_control,
            )
        finally:
            self._messages = snap_messages
            self._compressed = snap_compressed
            self._known_files = snap_known
            self._last_active = snap_last_active
            self._turn_user_idx = snap_turn_idx
            self._plan = snap_plan
            if self._depth == 0:
                self._save_session()

    def deliver_reminder(self, what: str) -> str:
        """到点提醒 失败退回原文"""
        self._prepare()
        # 在历史副本上发 不写回_messages
        messages = copy.deepcopy(self._messages) + [
            {"role": "user", "content": self._turn_context() + "\n\n" + prompts.reminder_nudge(what)}
        ]
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
            )
            self._meter_response(resp)
            content = (resp.choices[0].message.content or "").strip()
        except Exception:
            content = ""
        content = _strip_toolcall_leak(_strip_think_leak(content))
        if not content:
            content = f"[neutral]\n{what}"
        audit.reply(content, proactive=True)
        return content

    def speak_spontaneously(self, mode: str, context: str = "") -> str:
        """自己主动冒一句 憋不出返回空串"""
        self._prepare()
        nudge = prompts.spontaneous_nudge(mode)
        if context.strip():
            nudge = context.strip() + "\n" + nudge
        # 拿当下情境当线索 让记忆召回聚焦在"此刻相关"的事上 而非泛泛取一把
        messages = copy.deepcopy(self._messages) + [
            {"role": "user", "content": self._turn_context(context or None) + "\n\n" + nudge}
        ]
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
            )
            self._meter_response(resp)
            content = (resp.choices[0].message.content or "").strip()
        except Exception:
            return ""
        content = _strip_think_leak(content)
        if content:
            audit.reply(content, proactive=True)
        return content

    def rewrite_text(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        messages = [
            {"role": "system", "content": prompts.REWRITE_PROMPT},
            {"role": "user", "content": text},
        ]
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
            )
            self._meter_response(resp)
            content = (resp.choices[0].message.content or "").strip()
        except Exception:
            return ""
        return _strip_think_leak(content)

    def transform_clipboard(self, kind: str, text: str) -> str:
        """按kind改写剪贴板文本"""
        text = (text or "").strip()
        if not text:
            return ""
        messages = [
            {"role": "system", "content": prompts.CLIP_ALCHEMY_SYSTEM},
            {"role": "user", "content": f"{prompts.clip_alchemy_instr(kind)}\n\n内容：\n{text[:4000]}"},
        ]
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
            )
            self._meter_response(resp)
            content = (resp.choices[0].message.content or "").strip()
        except Exception:
            return ""
        return _strip_think_leak(content)

    def dream(self) -> str:
        """睡着时把高显著记忆碎片揉成一个梦 材料不够或失败返回空串"""
        frags = store.core_memories(3)
        frags += [e for e in store.recent_experiences(5) if e not in frags]
        frags += [str(it.get("text", "")) for it in journal.recent(4) if it.get("text")]
        frags = [f for f in frags if f][:7]
        if len(frags) < 2:
            return ""  # 还没攒够记忆 做不了梦
        fragments = "\n".join(f"- {f}" for f in frags)
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model,
                messages=[
                    {"role": "system", "content": prompts.DREAM_SYSTEM},
                    {"role": "user", "content": prompts.dream_nudge(fragments)},
                ],
                timeout=_BACKGROUND_TIMEOUT,
            )
            self._meter_response(resp)
            text = _strip_think_leak((resp.choices[0].message.content or "").strip())
        except Exception:
            return ""
        return text[:200]

    def consolidate_memory(self) -> int:
        """夜间记忆合并 把成簇的零碎经验各揉成一条高阶概括 返回揉成了几条
        聚类store自己做 这里只提供给每簇做概括的LLM回调"""
        return store.consolidate(self._summarize_cluster)

    def _summarize_cluster(self, texts: list[str]) -> str:
        """一簇同主题经验揉成一句概括 模型判定不成簇会回NONE 这里据此弃掉"""
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model,
                messages=[
                    {"role": "system", "content": prompts.CONSOLIDATE_SYSTEM},
                    {"role": "user", "content": prompts.consolidate_nudge(texts)},
                ],
                timeout=_BACKGROUND_TIMEOUT,
            )
            self._meter_response(resp)
            text = _strip_think_leak((resp.choices[0].message.content or "").strip())
        except Exception:
            return ""
        if not text or text.strip().upper().lstrip("[").startswith("NONE"):
            return ""  # 模型判定这几条没共同主题 不强揉
        return text[:300]

    def explore_topic(self, topic: str) -> str:
        from desktop_pet.agent.loop import Agent
        worker = Agent(self._settings, depth=self._depth + 1)
        try:
            return worker.run(prompts.explore_nudge(topic))
        except Exception:
            return ""
        finally:
            worker.close()

    def peek_screen(self, trigger: str = "") -> str:
        """偷瞄屏幕主动搭话 没事回空串"""
        from desktop_pet.eyes import capture
        from desktop_pet.settings import CAPTURE_WINDOW
        try:
            cap = capture.capture_screen(CAPTURE_WINDOW)
        except Exception:
            return ""
        if not cap.png_bytes:
            return ""
        prompt = prompts.PEEK_PROMPT
        if trigger.strip():
            prompt = f"（卡住雷达注意到前台窗口「{trigger.strip()[:80]}」可能有问题——重点看看是不是报错/卡住。）\n" + prompt
        content = [
            {"type": "text", "text": self._turn_context() + "\n\n" + prompt},
            {"type": "image_url", "image_url": {"url": capture.to_data_url(cap.png_bytes)}},
        ]
        messages = [self._system_message(), {"role": "user", "content": content}]
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
            )
            self._meter_response(resp)
            text = _strip_think_leak((resp.choices[0].message.content or "").strip())
        except Exception:
            return ""
        if not text or text.strip().upper().lstrip("[").startswith("NONE"):  # 容忍NONE裹在情绪标签里
            return ""
        audit.reply(text, proactive=True)
        return text

    def analyze_screen(self, focus: str) -> str:
        """定时盯屏单次执行 截屏问模型"""
        from desktop_pet.eyes import capture
        from desktop_pet.settings import CAPTURE_WINDOW
        from desktop_pet.watcher import WATCH_FAIL
        try:
            cap = capture.capture_screen(CAPTURE_WINDOW)
        except Exception:
            return WATCH_FAIL
        if not cap.png_bytes:
            return WATCH_FAIL
        content = [
            {"type": "text", "text": self._turn_context() + "\n\n" + prompts.watch_focus_prompt(focus)},
            {"type": "image_url", "image_url": {"url": capture.to_data_url(cap.png_bytes)}},
        ]
        messages = [self._system_message(), {"role": "user", "content": content}]
        try:
            resp = self._client().chat.completions.create(
                model=self._settings.model, messages=messages, timeout=_BACKGROUND_TIMEOUT
            )
            self._meter_response(resp)
            text = _strip_think_leak((resp.choices[0].message.content or "").strip())
        except Exception:
            return WATCH_FAIL
        stripped = re.sub(r"^\s*\[\w+\]\s*", "", text).strip()  # 剥掉情绪标签再判NONE
        if not stripped or stripped.upper() == "NONE":
            return ""
        audit.reply(text, proactive=True)
        return text

    def reflect(self) -> None:
        """一轮聊完后台复盘沉淀记忆"""
        if len(self._messages) <= 2:
            return
        if not self._turn_substantive:
            return
        if not _REFLECT_SEMAPHORE.acquire(blocking=False):
            return
        try:
            snapshot = copy.deepcopy(self._messages)
            peak = getattr(self, "_turn_emotion_peak", 0.5)  # 此刻就抓住本回合情绪峰值 别等 daemon 晚点去读(那时可能被下一回合覆盖)
            threading.Thread(
                target=self._reflect, args=(snapshot, peak), daemon=True, name="star-reflect"
            ).start()
        except Exception:
            _REFLECT_SEMAPHORE.release()

    def _reflect(self, snapshot: list[dict], peak: float = 0.5) -> None:
        """反思线程体 提炼json写进各存储"""
        try:
            epoch0 = store.reset_epoch()  # 开工前记下重置代数 反思要花几秒网络 期间可能被重置/换话题
            core = store.core_memories(4)
            core_block = (
                "\n\n[Your core memories — the formative moments that made you who you are; "
                "keep your self-portrait true to these]:\n- " + "\n- ".join(core)
            ) if core else ""
            reflect_msg = prompts.REFLECT_PROMPT + core_block + "\n\n[Your current self-portrait — evolve THIS gently, don't toss it]:\n" + (persona.get() or "(none yet — this is the first one you're forming)")
            conversation = snapshot + [{"role": "user", "content": reflect_msg}]
            try:
                resp = self._client().chat.completions.create(
                    model=self._settings.model, messages=conversation, timeout=_BACKGROUND_TIMEOUT
                )
                self._meter_response(resp)
                content = resp.choices[0].message.content or ""
            except Exception:
                return
            data = _parse_json(content)
            if not data:
                return
            if store.reset_epoch() != epoch0:
                return  # 反思期间用户重置/换了话题——别把已丢弃的记忆又写回去(重置静默失效)
            for experience in (data.get("experiences") or [])[:5]:
                text, weight = "", 0.3
                if isinstance(experience, dict):  # 新格式 {text, weight}
                    text = str(experience.get("text") or "").strip()
                    try:
                        weight = float(experience.get("weight", 0.3))
                    except (TypeError, ValueError):
                        weight = 0.3
                elif isinstance(experience, str):  # 兼容旧格式 纯字符串
                    text = experience.strip()
                if text:
                    # 模型判断的形成性为主 当下情绪强度为辅;epoch 传进去 锁内再校验一次 嵌入期间被重置就丢弃
                    salience = max(0.0, min(1.0, 0.55 * weight + 0.45 * peak))
                    store.remember(text, salience=salience, epoch=epoch0)
            preferences = data.get("preferences")
            if isinstance(preferences, dict):
                for key, value in preferences.items():
                    if isinstance(key, str) and isinstance(value, (str, int, float)):
                        store.set_preference(key, str(value), epoch=epoch0)
            env = data.get("env")
            if isinstance(env, dict):
                for key, value in env.items():
                    if isinstance(key, str) and isinstance(value, (str, int, float)):
                        store.note_env(key, str(value), epoch=epoch0)
            for op in (data.get("opinions") or [])[:3]:
                if isinstance(op, str) and op.strip():
                    store.add_opinion(op.strip(), epoch=epoch0)
            # journal/persona 没有 epoch 概念 写之前再核一次重置代数——重置/换话题后别把旧日记/旧自我画像写回去
            if store.reset_epoch() != epoch0:
                return
            episode = data.get("episode")
            if isinstance(episode, str) and episode.strip():
                journal.add(episode.strip())
            self_text = data.get("self")
            if isinstance(self_text, str) and self_text.strip():
                persona.update(self_text.strip())
            for stale in (data.get("forget") or [])[:5]:
                if isinstance(stale, str) and stale.strip():
                    store.forget(stale.strip())
        finally:
            _REFLECT_SEMAPHORE.release()
