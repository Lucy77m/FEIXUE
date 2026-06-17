# author: bdth
# email: 2074055628@qq.com
# 历史管理mixin 裁剪压缩 会话落盘恢复 图片附件拼装

from __future__ import annotations

import json
import threading
import time

from desktop_pet.agent import prompts
from desktop_pet.agent.loopdefs import (
    _ATTACH_FILE_CHARS,
    _FRESH_AFTER,
    _HISTORY_TOKEN_BUDGET,
    _SESSION_PATH,
    _SUMMARY_MAX_CHARS,
    _SUMMARY_TIMEOUT,
)
from desktop_pet.agent.textops import _estimate_tokens, _render_transcript, _strip_think_leak
from desktop_pet.docs import docs, read_file_text
from desktop_pet.settings import atomic_write_text


class HistoryMixin:
    """对话历史和会话文件那摊事"""

    def _prepare(self) -> None:
        """请求前裁历史 重建system 重算工具单"""
        self._trim_history()
        self._sanitize_tool_args()
        self._messages[0] = self._system_message()
        self._tools = self._build_tools()

    def _sanitize_tool_args(self) -> None:
        """历史里空arguments补成{} 有些网关空串marshal会炸 也救恢复进来的旧会话"""
        for m in self._messages:
            if not isinstance(m, dict):
                continue
            for c in m.get("tool_calls") or []:
                fn = c.get("function") if isinstance(c, dict) else None
                if fn is not None and not (fn.get("arguments") or "").strip():
                    fn["arguments"] = "{}"

    def _history_budget(self) -> int:
        """取历史token预算 非法退回默认"""
        try:
            value = int(self._settings.history_tokens)
        except (TypeError, ValueError, AttributeError):
            return _HISTORY_TOKEN_BUDGET
        if value <= 0:
            return _HISTORY_TOKEN_BUDGET
        return max(8_000, value)

    def _trim_history(self) -> None:
        """从尾往头累计token 超预算裁掉前面压成摘要"""
        n = len(self._messages)
        if n <= 2:
            return
        budget = self._history_budget()
        used = 0
        start = n
        for i in range(n - 1, 0, -1):
            used += _estimate_tokens(self._messages[i])
            if used > budget and i < n - 1:
                break
            start = i
        # 保留段不能以tool消息打头
        while start < n and self._messages[start].get("role") == "tool":
            start += 1
        if start > 1:
            dropped = self._messages[1:start]
            del self._messages[1:start]
            # 裁剪立刻生效保证请求合规 摘要丢后台 不堵当前这轮
            self._queue_compression(dropped)

    def _queue_compression(self, dropped: list[dict]) -> None:
        """被裁段排队等后台摘要 已有worker在跑就只入队 它会自己续上"""
        transcript = _render_transcript(dropped)
        if not transcript:
            return
        with self._compress_lock:
            self._pending_compress.append(transcript)
            if self._compress_busy:
                return  # worker还在 队列它会接着消化
            self._compress_busy = True
        try:
            threading.Thread(target=self._compress_worker, daemon=True, name="mochi-compress").start()
        except RuntimeError:
            # 起不了线程就退回同步做 别把被裁内容丢了
            with self._compress_lock:
                self._compress_busy = False
            self._compress_worker()

    def _compress_worker(self) -> None:
        """后台把队列里的被裁段滚进备忘 一次取空再续 只有这里写_compressed"""
        while True:
            with self._compress_lock:
                if not self._pending_compress:
                    self._compress_busy = False
                    return
                batch = self._pending_compress
                self._pending_compress = []
                prior = self._compressed
                gen = self._compress_gen
            new_summary = self._summarize(prior, batch)
            with self._compress_lock:
                # 摘要期间换了话题或清了记忆 这份就作废 别拿旧内容盖掉新空白
                if gen != self._compress_gen:
                    self._compress_busy = False
                    return
                self._compressed = new_summary[:_SUMMARY_MAX_CHARS]

    def _reset_compressed(self) -> None:
        """清空摘要并作废在途任务 换话题/遗忘/隔夜翻篇调用"""
        with self._compress_lock:
            self._compressed = ""
            self._pending_compress = []
            self._compress_gen += 1

    def _summarize(self, prior: str, batch: list[str]) -> str:
        """把既有摘要和这批被裁对话揉成新备忘 失败就给prior补一句残缺说明"""
        source = ""
        if prior:
            source += "[更早的既有摘要——合并进新备忘]\n" + prior + "\n\n"
        source += "[本次被裁剪的对话]\n" + "\n\n".join(batch)
        model = (getattr(self._settings, "subagent_model", "") or "").strip() or self._settings.model
        content = ""
        try:
            resp = self._client().chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompts.COMPRESS_PROMPT},
                    {"role": "user", "content": source},
                ],
                timeout=_SUMMARY_TIMEOUT,
            )
            self._meter_response(resp)
            content = (resp.choices[0].message.content or "").strip()
        except Exception:
            content = ""
        content = _strip_think_leak(content)
        if content:
            return content
        note = prompts.SUMMARY_LOST_NOTE
        return prior if note in prior else (prior + "\n" + note).strip()

    def _save_session(self) -> None:
        """会话落盘 system消息不存"""
        try:
            data = {
                "saved_at": time.time(),
                "compressed": self._compressed,
                "messages": self._strip_images_for_save(self._messages[1:]),
            }
            atomic_write_text(_SESSION_PATH, json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    @staticmethod
    def _strip_images_for_save(messages: list[dict]) -> list[dict]:
        """落盘前图片消息压成纯文本占位"""
        out: list[dict] = []
        for m in messages:
            m2 = dict(m)
            content = m2.get("content")
            if isinstance(content, list):
                texts = [p.get("text", "") for p in content
                         if isinstance(p, dict) and p.get("type") == "text"]
                m2["content"] = " ".join(t for t in texts if t).strip() or "[图片已在重启时省略]"
            out.append(m2)
        return out

    @staticmethod
    def _clear_session_file() -> None:
        try:
            _SESSION_PATH.unlink(missing_ok=True)
        except OSError:
            pass

    def _try_restore_session(self) -> None:
        """启动时恢复上次会话 过期或脏数据放弃"""
        try:
            data = json.loads(_SESSION_PATH.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(data, dict):
            return
        saved_at = data.get("saved_at")
        if not isinstance(saved_at, (int, float)) or time.time() - saved_at > _FRESH_AFTER:
            return
        messages = data.get("messages")
        if not isinstance(messages, list):
            return
        cleaned = [m for m in messages
                   if isinstance(m, dict) and m.get("role") in ("user", "assistant", "tool")]
        if not cleaned:
            return
        # 削到第一条非tool为止
        while cleaned and cleaned[0].get("role") == "tool":
            cleaned.pop(0)
        if not cleaned:
            return
        compressed = data.get("compressed")
        if isinstance(compressed, str):
            self._compressed = compressed[:_SUMMARY_MAX_CHARS]
        self._messages = [self._system_message()] + cleaned
        self._seal_pending_tool_calls("[这一步执行到一半时程序重启了，没有拿到结果。]")
        self._last_active = time.monotonic()

    def _append_images(self, images: list[str]) -> None:
        """新截图塞进历史 先清旧图"""
        self._drop_old_images()
        content: list[dict] = [{"type": "text", "text": "(screenshot below)"}]
        for url in images:
            content.append({"type": "image_url", "image_url": {"url": url}})
        self._messages.append({"role": "user", "content": content})

    def _drop_old_images(self) -> None:
        """旧图片消息退化成占位 当轮用户图留着"""
        for idx, message in enumerate(self._messages):
            if idx == self._turn_user_idx:
                continue
            if message.get("role") == "user" and isinstance(message.get("content"), list):
                texts = [
                    part.get("text", "")
                    for part in message["content"]
                    if isinstance(part, dict) and part.get("type") == "text"
                ]
                joined = " ".join(t for t in texts if t).strip()
                message["content"] = joined or "[older image omitted]"

    def _compose_user_content(self, text: str, attachments: object, context: str = ""):
        """拼user消息 有图走多模态list"""
        prefix = (context + "\n\n") if context else ""
        if not isinstance(attachments, list) or not attachments:
            return (prefix + text) if text else prefix.rstrip()
        images = [
            a for a in attachments
            if isinstance(a, dict) and a.get("kind") == "image" and a.get("data_url")
        ]
        files = [
            a for a in attachments
            if isinstance(a, dict) and a.get("kind") == "file" and a.get("path")
        ]
        file_ctx = self._ingest_and_read(files)
        full_text = text
        if file_ctx:
            full_text = (text + "\n\n" if text else "") + file_ctx
        if not images:
            return prefix + (full_text or "(用户发来了附件)")
        content: list[dict] = [{"type": "text", "text": prefix + (full_text or "看看这张图。")}]
        for img in images:
            content.append({"type": "image_url", "image_url": {"url": img["data_url"]}})
        return content

    def _ingest_and_read(self, files: list) -> str:
        """附件文件入知识库同时读前6000字喂对话"""
        if not files:
            return ""
        blocks: list[str] = []
        for f in files:
            path = f.get("path")
            name = f.get("name") or path
            if not path:
                continue
            try:
                threading.Thread(target=self._safe_ingest, args=(path,), daemon=True, name="mochi-ingest").start()
            except RuntimeError:
                pass
            text = read_file_text(path)
            if text and text.strip():
                body = text if len(text) <= _ATTACH_FILE_CHARS else text[:_ATTACH_FILE_CHARS] + "\n…（已截断，全文已存入知识库，可用 recall_docs 召回）"
                blocks.append(f"【附件文件：{name}】\n{body}")
            else:
                blocks.append(f"【附件文件：{name}】（无法直接读取文本，可能是二进制或不支持的格式；已尝试存入知识库）")
        return "\n\n".join(blocks)

    @staticmethod
    def _safe_ingest(path: str) -> None:
        try:
            docs.ingest(path)
        except Exception:
            pass
