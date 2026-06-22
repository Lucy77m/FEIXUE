# 工具调用名映射进度文案 渲染计划清单

from __future__ import annotations

from desktop_pet import i18n

PLAN_ICON = {"todo": "○", "doing": "→", "done": "●"}

# 工具名对应i18n键和取细节lambda None表示无细节
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
    """工具调用转一行进度文案 出错退回name"""
    try:
        # args非dict兜成空dict
        return _describe_step(name, args if isinstance(args, dict) else {})
    except Exception:
        return name


def _describe_step(name: str, args: dict) -> str:
    # plan和mcp__是动态名 查表前单独认
    if name == "plan":
        return f"{i18n.t('s_plan')} · {len(args.get('steps', []))} {i18n.t('step_unit')}"
    if name.startswith("mcp__"):
        # 名字格式 mcp__server__tool
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
    """计划清单转markdown"""
    # 行尾俩空格是markdown硬换行
    rows = [f"{PLAN_ICON.get(step['status'], '○')} {step['text']}  " for step in steps]
    return f"**{i18n.t('plan_title')}**\n\n" + "\n".join(rows)
