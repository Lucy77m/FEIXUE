# author: bdth
# email: 2074055628@qq.com
# 把 agent 工具调用名映射成可读的进度文案，并渲染任务计划清单

from __future__ import annotations

from desktop_pet import i18n

PLAN_ICON = {"todo": "○", "doing": "→", "done": "●"}

# 工具名 → (i18n 文案键, 取细节的 lambda)；lambda 为 None 表示这步没细节、只显标签。
# [:24]/[:30]/[:40] 截短：进度条一行塞不下整条 url/pattern/正文，不截会撑爆。
_STEPS: dict[str, tuple[str, "object"]] = {
    "run_shell": ("s_run_shell", None),
    "run_python": ("s_run_python", None),
    "read_file": ("s_read_file", lambda a: a.get("path", "")),
    "write_file": ("s_write_file", lambda a: a.get("path", "")),
    "edit_file": ("s_edit_file", lambda a: a.get("path", "")),
    "search_code": ("s_search_code", lambda a: a.get("pattern", "")[:24]),
    "glob_files": ("s_glob", lambda a: a.get("pattern", "")[:24]),
    "list_dir": ("s_list_dir", lambda a: a.get("path", ".")),
    "http_request": ("s_http", lambda a: a.get("url", "")[:40]),
    "web_search": ("s_web_search", lambda a: a.get("query", "")[:24]),
    "web_fetch": ("s_web_fetch", lambda a: a.get("url", "")[:36]),
    "install_package": ("s_install", lambda a: a.get("name", "")),
    "perform": ("s_perform", lambda a: a.get("name", "")),
    "system_memory": ("s_sysmem", None),
    "read_process_memory": ("s_read_proc", lambda a: f"pid {a.get('pid', '')}"),
    "screenshot": ("s_screenshot", None),
    "ocr_screen": ("s_ocr", None),
    "find_on_screen": ("s_find", None),
    "list_windows": ("s_list_windows", None),
    "focus_window": ("s_focus", lambda a: a.get("title", "")),
    "manage_window": ("s_manage_window", lambda a: f"{a.get('title', '')} ({a.get('action', '')})"),
    "read_clipboard": ("s_read_clip", None),
    "write_clipboard": ("s_write_clip", None),
    "click": ("s_click", lambda a: f"({a.get('x')}, {a.get('y')})"),
    "double_click": ("s_double_click", lambda a: f"({a.get('x')}, {a.get('y')})"),
    "right_click": ("s_right_click", lambda a: f"({a.get('x')}, {a.get('y')})"),
    "move_mouse": ("s_move_mouse", lambda a: f"({a.get('x')}, {a.get('y')})"),
    "scroll": ("s_scroll", lambda a: str(a.get("amount"))),
    "type_text": ("s_type", lambda a: a.get("text", "")[:30]),
    "press_keys": ("s_press", lambda a: a.get("keys", "")),
    "set_preference": ("s_set_pref", lambda a: a.get("key", "")),
    "remember": ("s_remember", lambda a: a.get("content", "")[:28]),
    "recall": ("s_recall", lambda a: a.get("query", "")),
    "note_env": ("s_note_env", lambda a: a.get("key", "")),
    "ingest_docs": ("s_ingest", lambda a: a.get("path", "")),
    "recall_docs": ("s_recall_docs", lambda a: a.get("query", "")[:24]),
    "list_docs": ("s_list_docs", None),
    "forget_docs": ("s_forget_docs", None),
    "schedule_reminder": ("s_schedule_reminder", lambda a: a.get("message", "")[:20]),
    "schedule_task": ("s_schedule_task", lambda a: a.get("task", "")[:20]),
    "create_skill": ("s_create_skill", lambda a: a.get("name", "")),
    "run_skill": ("s_run_skill", lambda a: a.get("name", "")),
    "edit_skill": ("s_edit_skill", lambda a: a.get("name", "")),
    "list_skills": ("s_list_skills", None),
    "spawn_agent": ("s_spawn", lambda a: a.get("task", "")[:24]),
    "start_background_task": ("s_background", lambda a: a.get("task", "")[:24]),
    "spawn_workflow": ("s_workflow", lambda a: f"{a.get('mode', '')} ×{len(a.get('tasks', []))}"),
    "set_screen_watch": ("s_watch", lambda a: str(a.get("focus", ""))[:20]),
    "review_diff": ("s_review_diff", lambda a: a.get("path", "")),
    "run_tests": ("s_run_tests", lambda a: a.get("path", "")),
    "list_reminders": ("s_list_reminders", None),
    "cancel_reminder": ("s_cancel_reminder", lambda a: f"#{a.get('reminder_id', '')}"),
    "list_background_tasks": ("s_list_bg", None),
    "stop_background_task": ("s_stop_bg", lambda a: f"#{a.get('task_id', '')}"),
    "show_image": ("s_show_image", lambda a: (a.get("caption") or a.get("source", ""))[:24]),
    "play_gif": ("s_play_gif", lambda a: (a.get("caption") or a.get("source", ""))[:24]),
}


def describe_step(name: str, args: dict) -> str:
    """工具调用 → 一行进度文案。这是给 UI 看的，绝不能抛——出岔子就退回原始 name。"""
    try:
        # args 偶尔不是 dict（半截的流式 JSON），兜成 {} 免得 lambda 取键炸了
        return _describe_step(name, args if isinstance(args, dict) else {})
    except Exception:
        return name


def _describe_step(name: str, args: dict) -> str:
    # plan / mcp__ 是动态名，进不了 _STEPS 表，得在查表前先单独认出来。
    if name == "plan":
        return f"{i18n.t('s_plan')} · {len(args.get('steps', []))} {i18n.t('step_unit')}"
    if name.startswith("mcp__"):
        # 名字长这样：mcp__<server>__<tool>
        parts = name.split("__")
        return f"{i18n.t('s_mcp')} · {parts[1] if len(parts) > 1 else ''}/{parts[-1]}"
    entry = _STEPS.get(name)
    if entry is None:
        return name
    key, extract = entry
    label = i18n.t(key)
    if extract is None:
        return label
    detail = str(extract(args))
    return f"{label} · {detail}" if detail else label


def render_plan(steps: list[dict]) -> str:
    """计划清单 → markdown。"""
    # 行尾留俩空格是 markdown 的硬换行——不留的话整张清单会被并成一段。
    rows = [f"{PLAN_ICON.get(step['status'], '○')} {step['text']}  " for step in steps]
    return f"**{i18n.t('plan_title')}**\n\n" + "\n".join(rows)
