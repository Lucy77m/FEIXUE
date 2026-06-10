# author: bdth
# email: 2074055628@qq.com
# 定义agent全部工具 分发工具调用到执行器

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from desktop_pet.docs import docs, read_file_text
from desktop_pet.eyes import capture
from desktop_pet.eyes.capture import capture_screen, to_data_url
from desktop_pet.executor import clipboard, devtools, fs, net, shell, sysmem, vision, web
from desktop_pet.executor.pycode import PythonRunner, install_package
from desktop_pet.executor.shell import run_shell
from desktop_pet.hands import keyboard, mouse, windows
from desktop_pet.mcp_hub import mcp_hub
from desktop_pet.memory.store import store
from desktop_pet.reminders import reminders
from desktop_pet.settings import CAPTURE_FULLSCREEN
from desktop_pet.skills import skills

_python = PythonRunner()
_DISPATCH_LOCK = threading.Lock()


@dataclass
class ToolResult:
    text: str
    image_data_url: str | None = None


def _function(name: str, description: str, properties: dict, required: list[str]) -> dict:
    """包装工具schema"""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


# 鼠标工具共用xy参数
_XY = {
    "x": {"type": "integer", "description": "screen X, pixels"},
    "y": {"type": "integer", "description": "screen Y, pixels"},
}

TOOLS = [
    _function(
        "run_shell",
        "Run a PowerShell/cmd command on this machine; returns exit code and output. First choice for files, processes, system settings, launching programs, installing software, etc. "
        "Killed after 120s with no output or 600s total — for servers/watch-mode/long builds set background=true: it returns an id immediately and keeps running; read its output later with check_shell.",
        {
            "command": {"type": "string", "description": "the command to run"},
            "shell": {"type": "string", "enum": ["powershell", "cmd"], "description": "default powershell"},
            "background": {"type": "boolean", "description": "run detached in the background and return an id at once (powershell only); use for dev servers, watchers, long builds"},
        },
        ["command"],
    ),
    _function(
        "check_shell",
        "Check a background shell started by run_shell(background=true): returns output produced since your last check, plus whether it's still running. "
        "Call with no id to list all background shells; kill=true stops one (with its child processes).",
        {
            "id": {"type": "integer", "description": "the background shell id; omit to list all"},
            "kill": {"type": "boolean", "description": "stop it instead of just reading output"},
        },
        [],
    ),
    _function(
        "run_python",
        "Run code in a persistent Python environment (variables/imports survive across calls); returns stdout. pip-install libraries, call APIs, read/write files, drive automation libraries. "
        "Default limit 60s per call — pass timeout (up to 600) for longer work. On timeout the session RESTARTS and all variables are LOST, so keep steps within the limit you set.",
        {
            "code": {"type": "string", "description": "the Python code to run"},
            "timeout": {"type": "integer", "description": "seconds allowed for this call (default 60, max 600); raise it for known-slow work instead of letting it die"},
        },
        ["code"],
    ),
    _function(
        "read_file",
        "Read a file. Text comes back as text (truncated to ~20k chars by default; raise max_chars up to 100k, or continue with offset). "
        "Images (png/jpg/gif/webp/bmp) come back as a picture you actually SEE — use this to look at any local image. PDFs come back as extracted text (scanned pages are OCR'd).",
        {
            "path": {"type": "string", "description": "file path"},
            "offset": {"type": "integer", "description": "character offset to start reading from (use the value given in a previous truncation note); default 0"},
            "max_chars": {"type": "integer", "description": "max characters to return in this call (default 20000, max 100000)"},
        },
        ["path"],
    ),
    _function(
        "write_file",
        "Write content to a file (overwrites; creates parent dirs).",
        {
            "path": {"type": "string", "description": "file path"},
            "content": {"type": "string", "description": "the content to write"},
        },
        ["path", "content"],
    ),
    _function(
        "edit_file",
        "Edit a file by replacing the `old` string with `new` (surgical — safer than rewriting a whole file with write_file). "
        "`old` must carry enough context to be unique. Matching is exact first; if that misses it falls back to ignoring line-ending (CRLF/LF) and whitespace/indentation differences, so you don't have to reproduce indentation byte-perfectly. If `old` isn't found at all, or matches multiple spots without replace_all, you get an error to fix.",
        {
            "path": {"type": "string", "description": "file path"},
            "old": {"type": "string", "description": "the original text to replace; reproduce it as faithfully as you can, but minor whitespace/indentation/line-ending differences are tolerated"},
            "new": {"type": "string", "description": "the replacement text"},
            "replace_all": {"type": "boolean", "description": "replace all occurrences; default replaces only the first (and requires it to be unique)"},
        },
        ["path", "old", "new"],
    ),
    _function(
        "list_dir",
        "List the files and subdirectories in a directory.",
        {"path": {"type": "string", "description": "directory path, default current dir"}},
        [],
    ),
    _function(
        "search_code",
        "Regex-search the contents of code/text files; returns file:line: content (auto-skips .venv/.git/caches). Use to find code, locate symbols, check usage. Set context to also see lines around each hit without a follow-up read.",
        {
            "pattern": {"type": "string", "description": "regular expression"},
            "path": {"type": "string", "description": "search root dir or file, default current dir"},
            "context": {"type": "integer", "description": "lines of surrounding context to show around each match (0-5, default 0)"},
        },
        ["pattern"],
    ),
    _function(
        "glob_files",
        "Find files by name pattern (e.g. *.py, **/test_*.py); returns the matching paths.",
        {
            "pattern": {"type": "string", "description": "glob pattern"},
            "path": {"type": "string", "description": "search root dir, default current dir"},
        },
        ["pattern"],
    ),
    _function(
        "review_diff",
        "Show uncommitted git changes (the working-tree diff). Use this BEFORE touching a code repo to see current state, "
        "and AFTER editing to self-check what you changed. Pass path = the repo directory you're working in (or a single "
        "file/subdir to scope it). staged=true shows already-staged changes. Read-only.",
        {
            "path": {"type": "string", "description": "repo dir, or a file/subdir within it to limit the diff; default current dir"},
            "staged": {"type": "boolean", "description": "true = show staged changes (git diff --staged)"},
        },
        [],
    ),
    _function(
        "run_tests",
        "Run the project's tests and return a pass/fail summary — use it after changing code to confirm you didn't break "
        "anything. Without a command it auto-detects (pytest for Python, npm test for Node). Timeout 5 min "
        "(run_shell is 120s-idle/600s-total). Pass path = the project directory.",
        {
            "command": {"type": "string", "description": "optional custom test command; omit to auto-detect"},
            "path": {"type": "string", "description": "project directory to run tests in; default current dir"},
        },
        [],
    ),
    _function(
        "http_request",
        "Make an HTTP request; returns status code and response body (truncated).",
        {
            "url": {"type": "string", "description": "request URL"},
            "method": {"type": "string", "description": "GET/POST etc., default GET"},
            "body": {"type": "string", "description": "request body, optional"},
            "headers": {"type": "object", "description": "request headers, optional, e.g. {\"Content-Type\": \"application/json\", \"Authorization\": \"Bearer …\"}"},
        },
        ["url"],
    ),
    _function(
        "web_search",
        "Search the web; returns several results (title/link/snippet). Use for real-time, latest, or uncertain info; "
        "then web_fetch to open a link you want to read closely.",
        {"query": {"type": "string", "description": "search query"}},
        ["query"],
    ),
    _function(
        "web_fetch",
        "Open a URL and return its main text (navigation/ads stripped; truncated if long). Usually follows web_search to read one result.",
        {"url": {"type": "string", "description": "web page URL"}},
        ["url"],
    ),
    _function(
        "install_package",
        "pip-install a Python package into the runtime; afterwards run_python can import it directly.",
        {"name": {"type": "string", "description": "package name, e.g. requests"}},
        ["name"],
    ),
    _function(
        "perform",
        "Act out a move or a little skit yourself — call this when the user asks you to dance / have a coffee / fish / play with yarn, etc., and your body really performs it. "
        "Skits (a few-to-ten-second mini-scene): coffee, fish, sleuth, read, music, game, stars, yarn. "
        "One-shot actions: dance, cheer, celebrate, spin, jump_spin, flip, roll, "
        "hop2, bounce, nod, wobble, stretch, yawn, headbang, puff_up, boing, pop, "
        "giggle, purr, snuggle, wave, eating.",
        {"name": {"type": "string", "description": "the action or skit name (see the list above; use the English key)"}},
        ["name"],
    ),
    _function(
        "system_memory",
        "Show this machine's RAM usage: total / used / available, plus the most memory-hungry processes (Task-Manager-style view). "
        "Use when the user asks 'how much memory is used / which program eats the most memory'. Read-only, safe.",
        {"top": {"type": "integer", "description": "list the top-N processes by usage, default 12, max 40"}},
        [],
    ),
    _function(
        "read_process_memory",
        "Read a process's raw memory bytes (Win32 ReadProcessMemory); returns a hex + ASCII dump. "
        "For debugging / forensics / inspecting a value in a process's memory — only when the user explicitly asks to view a process's memory. "
        "Read-only, never modifies; system/protected processes need admin. Find the target pid first with system_memory or list_windows.",
        {
            "pid": {"type": "integer", "description": "target process ID"},
            "address": {"type": "string", "description": "start address, decimal or 0x hex, e.g. 0x7ff6abcd0000"},
            "size": {"type": "integer", "description": "bytes to read, default 256, max 4096"},
        },
        ["pid", "address"],
    ),
    _function(
        "show_image",
        "Show the user an image beside the pet (pinned as a Polaroid). Use when you found an image online, generated/downloaded one, or the user wants to see a picture. "
        "source can be a local path or an http(s) image URL (auto-downloaded).",
        {
            "source": {"type": "string", "description": "local image path or image URL"},
            "caption": {"type": "string", "description": "small caption under the photo (optional)"},
        },
        ["source"],
    ),
    _function(
        "play_gif",
        "Play a GIF beside the user (looped in a little TV). source can be a local path or an http(s) .gif URL (auto-downloaded).",
        {
            "source": {"type": "string", "description": "local GIF path or GIF URL"},
            "caption": {"type": "string", "description": "caption (optional)"},
        },
        ["source"],
    ),
    _function(
        "screenshot",
        "Take a screenshot and return the image to you; the text gives the screen resolution, and mouse coordinates follow it. Use only when you must see the GUI. "
        "Pick the scope: for the whole desktop / locating a window use fullscreen (default); to see the active window clearly use window. "
        "If small text/icons are unreadable (games, videos, dense custom UIs), re-shoot with region to ZOOM into that area at native resolution. "
        "By default you (the pet) are NOT in the shot; set include_self to true only when you actually want to see yourself.",
        {
            "scope": {
                "type": "string",
                "enum": ["fullscreen", "window"],
                "description": "framing: fullscreen = whole screen (default), window = only the active window. Choose by what you need to see.",
            },
            "region": {
                "type": "string",
                "description": "optional ZOOM: left,top,width,height in IMAGE pixels (same coordinate space as the previous screenshot / ocr_screen). "
                "Crops that area at NATIVE resolution so small details become readable — take a fullscreen shot first, then re-shoot zoomed on the part you must see clearly.",
            },
            "include_self": {
                "type": "boolean",
                "description": "whether to include you (the pet window) in the shot. Default false — usually you don't need to see yourself when looking at the screen.",
            },
        },
        [],
    ),
    _function(
        "ocr_screen",
        "OCR the on-screen text and return each segment's CENTER coordinate — unlike eyeballing a screenshot, this tells you exactly "
        "where text is so you can click the coordinate directly. Use to read a lot of on-screen text, or to click a specific piece of text. "
        "Optional region scans just one area.",
        {"region": {"type": "string", "description": "optional, scan only this area: left,top,width,height in IMAGE pixels — the same coordinate space as screenshot images and the coordinates this tool returns; blank = whole screen"}},
        [],
    ),
    _function(
        "find_on_screen",
        "Locate a small template image (an icon/button screenshot) on screen; returns its center coordinate (click it directly). "
        "Use to click elements with no accessibility node — icons in custom-drawn UIs or game screens. Prepare the template image file first. "
        "Matches on edge structure as well as brightness, so a template keeps working across theme / lighting / dark-mode changes (even an inverted palette).",
        {
            "template_path": {"type": "string", "description": "local path of the template image (a small screenshot of the icon/button to find)"},
            "confidence": {"type": "number", "description": "match threshold 0–1, default 0.8; lower it if not found"},
        },
        ["template_path"],
    ),
    _function(
        "screen_elements",
        "BEST way to operate a GUI: detect all actionable elements on the active screen (accessibility controls + on-screen text), draw NUMBERED boxes on a screenshot, and return it plus a numbered list. "
        "Then call act_element with the number — you pick a number instead of guessing pixel coordinates, and the click lands exactly. Prefer this over screenshot+click for any normal app/web UI. "
        "If a dense toolbar / small icons come back unlabeled or merged, pass region to ZOOM in: it re-detects just that area at native resolution, surfacing small elements a full-screen pass misses. "
        "(Won't find much on pure game/canvas surfaces — there fall back to ocr_screen, or raw click/move by coordinate.)",
        {"region": {"type": "string", "description": "optional ZOOM: left,top,width,height in IMAGE pixels (same coordinate space as screenshot / ocr_screen). Re-detects only that area at native resolution for denser/smaller elements; blank = whole screen"}},
        [],
    ),
    _function(
        "act_element",
        "Act on a numbered element from the most recent screen_elements result. "
        "action: click (default) / double / right / type (type needs text). Re-run screen_elements first if the screen changed. "
        "By default (mode=auto) it avoids the user's real mouse: accessibility invoke → synthetic window messages (work even on covered windows), and only falls back to a real click when message delivery itself fails. "
        "It AUTO-VERIFIES: after the action it re-checks the screen and the result says whether anything actually changed. If it reports '⚠ NOTHING changed' (common when games/custom UIs ignore synthetic input), retry with mode=real; only trust '✓ verified' as actually done. "
        "mode=ghost: NEVER touch the real mouse, report failure instead (user asked not to interfere). mode=real: skip ghost, click for real (use after a verified no-effect ghost attempt).",
        {
            "index": {"type": "integer", "description": "the element number from screen_elements"},
            "action": {"type": "string", "enum": ["click", "double", "right", "type"], "description": "default click"},
            "text": {"type": "string", "description": "text to type when action=type"},
            "mode": {"type": "string", "enum": ["auto", "ghost", "real"], "description": "auto (default): no-cursor first, real mouse only if delivery fails; ghost: never touch the real mouse; real: real mouse directly"},
        },
        ["index"],
    ),
    _function("list_windows", "List the titles of all currently visible windows.", {}, []),
    _function(
        "focus_window",
        "Activate and bring a title-matching window to the front (do this before clicking its GUI).",
        {"title": {"type": "string", "description": "window title or part of it"}},
        ["title"],
    ),
    _function(
        "manage_window",
        "Manage a window: minimize / maximize / restore / close, or move / resize it. Use to tidy windows or make room.",
        {
            "title": {"type": "string", "description": "window title or part of it"},
            "action": {"type": "string", "enum": ["minimize", "maximize", "restore", "close", "move", "resize"],
                       "description": "the action to take"},
            "x": {"type": "integer", "description": "top-left X for move (screen pixels)"},
            "y": {"type": "integer", "description": "top-left Y for move (screen pixels)"},
            "width": {"type": "integer", "description": "width for resize (pixels)"},
            "height": {"type": "integer", "description": "height for resize (pixels)"},
        },
        ["title", "action"],
    ),
    _function(
        "read_clipboard",
        "Read the text on the system clipboard (see what the user just copied).",
        {},
        [],
    ),
    _function(
        "recall_clipboard",
        "Recall the most recent INTERESTING thing the user copied (an error / foreign text / code / link), as noticed by the clipboard sense. Use when they refer to 'this error', 'what I just copied', etc. Returns nothing if the feature is off or nothing notable was copied.",
        {},
        [],
    ),
    _function(
        "write_clipboard",
        "Write text to the system clipboard (the user can then paste it).",
        {"text": {"type": "string", "description": "text to put on the clipboard"}},
        ["text"],
    ),
    _function("click", "Left-click at a screen coordinate.", _XY, ["x", "y"]),
    _function("double_click", "Double-click (left) at a screen coordinate.", _XY, ["x", "y"]),
    _function("right_click", "Right-click at a screen coordinate.", _XY, ["x", "y"]),
    _function("move_mouse", "Move the mouse to a screen coordinate.", _XY, ["x", "y"]),
    _function(
        "scroll",
        "Scroll the mouse wheel; positive = up, negative = down.",
        {"amount": {"type": "integer", "description": "scroll amount"}},
        ["amount"],
    ),
    _function(
        "type_text",
        "Type text into the focused field — works for ANY language (Chinese / Japanese / emoji etc. are pasted via the clipboard automatically; English/digits are typed as keystrokes). Click/focus the target field first.",
        {"text": {"type": "string", "description": "the text to type"}},
        ["text"],
    ),
    _function(
        "press_keys",
        'Press a key or key combo, e.g. "enter", "ctrl+c", "alt+f4".',
        {"keys": {"type": "string", "description": "keys; join a combo with +"}},
        ["keys"],
    ),
    _function(
        "set_preference",
        "Remember a long-term preference/habit of the user (recalled automatically at each launch).",
        {
            "key": {"type": "string", "description": "preference name, e.g. music app"},
            "value": {"type": "string", "description": "preference value, e.g. NetEase Music"},
        },
        ["key", "value"],
    ),
    _function(
        "remember",
        "Remember an experience, lesson, or important fact for later reference.",
        {"content": {"type": "string", "description": "what to remember"}},
        ["content"],
    ),
    _function(
        "recall",
        "Search long-term memory for preferences, experiences, and environment facts related to a keyword.",
        {"query": {"type": "string", "description": "search keyword"}},
        ["query"],
    ),
    _function(
        "note_env",
        "Remember a CHANGEABLE environment fact — software install paths, runtime locations, window-title patterns, etc. "
        "Stored separately from set_preference (stable preferences) and remember (lessons); it's a cache that may go stale — "
        "if acting on it fails, re-verify and note_env again to update it.",
        {
            "key": {"type": "string", "description": "env key, e.g. QQMusic.install_path"},
            "value": {"type": "string", "description": "the value"},
        },
        ["key", "value"],
    ),
    _function(
        "forget_memory",
        "Delete your OWN stored memories matching a keyword — use to correct yourself: when a lesson/preference/env fact you saved turns out WRONG or outdated (you discovered it's false, or the user corrected you). "
        "Removes the matching entries from long-term memory (experiences / preferences / env facts) and reports what was removed; then remember the corrected version if there is one.",
        {"query": {"type": "string", "description": "keyword of the memory to remove"}},
        ["query"],
    ),
    _function(
        "schedule_reminder",
        "Schedule a reminder: at the time you'll wake yourself and tell the user the thing in your own voice "
        "(not a popup, not a system notification, not a background script). Use when the user says 'remind me / call me / tell me to do X at <time>'. "
        "Once you call this it's scheduled — don't write any code to sleep / wait for that time; the system wakes you at the time. "
        "Give message (what to say) and one of fire_at or in_minutes. For a RECURRING reminder ('every day / every Monday / every N hours'), "
        "also pass repeat, and set fire_at to the FIRST occurrence.",
        {
            "message": {"type": "string", "description": "what to tell the user at the time, e.g. time for bed"},
            "fire_at": {"type": "string", "description": "absolute time, 24h HH:MM or YYYY-MM-DD HH:MM; for repeats this is the first occurrence; pick one of this / in_minutes"},
            "in_minutes": {"type": "number", "description": "remind after this many minutes; pick one of this / fire_at"},
            "repeat": {"type": "string", "description": "recurrence: 'daily' (same time each day) / 'weekly' (same weekday+time) / 'interval:N' (every N minutes). Omit for a one-shot reminder."},
        },
        ["message"],
    ),
    _function(
        "ingest_docs",
        "Ingest a file or folder into the KNOWLEDGE BASE: contents are chunked, embedded, and stored, then searchable with recall_docs. "
        "Handles text/code/markdown AND PDF (text-layer PDFs are read directly; scanned/image PDFs are OCR'd automatically). "
        "Use when the user gives you material or says 'remember these documents / read this folder / read this PDF'.",
        {"path": {"type": "string", "description": "file or folder path (a single .pdf, a file, or a directory)"}},
        ["path"],
    ),
    _function(
        "recall_docs",
        "Semantic-search the KNOWLEDGE BASE (documents you've ingested); returns the most relevant passages (with source filenames). Use this first when answering questions about the user's material.",
        {"query": {"type": "string", "description": "search question / keywords"}},
        ["query"],
    ),
    _function(
        "list_docs",
        "List which documents are in the knowledge base (filename + chunk count).",
        {},
        [],
    ),
    _function(
        "forget_docs",
        "Remove documents from the knowledge base: give source (a filename fragment) to delete only matches; omit it to clear the whole base.",
        {"source": {"type": "string", "description": "filename fragment of the source to remove; omit to clear everything"}},
        [],
    ),
    _function(
        "schedule_task",
        "Schedule a TASK: at the time the system wakes you to actually CARRY IT OUT yourself in the foreground (with the full toolset: run commands / write code / go online / operate the PC, etc.) — the user sees you do it and can tap you to stop it. "
        "Difference from schedule_reminder — that one just SAYS a line at the time; this one DOES the work. "
        "Use when the user says 'automatically do X / run Y for me at <time> / after <duration>'. Give task (self-contained, stating the wanted outcome) and one of fire_at or in_minutes. "
        "For a RECURRING task ('every day / every N hours back up X'), also pass repeat and set fire_at to the first run.",
        {
            "task": {"type": "string", "description": "the task to run automatically at the time, self-contained, stating the wanted outcome"},
            "fire_at": {"type": "string", "description": "absolute time HH:MM or YYYY-MM-DD HH:MM; for repeats this is the first run; pick one of this / in_minutes"},
            "in_minutes": {"type": "number", "description": "after this many minutes; pick one of this / fire_at"},
            "repeat": {"type": "string", "description": "recurrence: 'daily' / 'weekly' / 'interval:N' (every N minutes). Omit for a one-shot task."},
        },
        ["task"],
    ),
    _function(
        "list_reminders",
        "List all pending reminders and scheduled tasks (their id, time, recurrence, and content). Use when the user asks what's scheduled, or before cancelling one.",
        {},
        [],
    ),
    _function(
        "cancel_reminder",
        "Cancel one pending reminder/task by its id (from list_reminders). Use when the user says 'cancel that reminder / don't remind me anymore'.",
        {"reminder_id": {"type": "number", "description": "the id shown by list_reminders"}},
        ["reminder_id"],
    ),
    _function(
        "list_background_tasks",
        "List the background tasks currently running (their id, how long they've run, and what they are). Use when the user asks 'what are you working on / what's running', or before stopping one.",
        {},
        [],
    ),
    _function(
        "stop_background_task",
        "Stop a running background task by its id (from list_background_tasks). It stops cooperatively — after its current step. Use when the user says 'stop that / cancel the background job'.",
        {"task_id": {"type": "number", "description": "the id shown by list_background_tasks"}},
        ["task_id"],
    ),
    _function(
        "set_screen_watch",
        "Start (or stop) WATCHING the screen on a repeating timer: every interval_minutes you automatically glance at "
        "the user's active window and report what you see about a focus they give you. Use when the user says things like "
        "'every few minutes look at my screen and tell me X', 'keep an eye on my game and warn me', 'monitor this and report'. "
        "This is the ONLY way to act on a recurring timer by yourself — do NOT try to sleep/loop in code. "
        "It runs for this session (resets when the app restarts). To stop, call again with interval_minutes=0 (or when the user says stop).",
        {
            "focus": {"type": "string", "description": "what to look at / report each time, in the user's terms, e.g. 'my game situation — warn me of danger or openings'"},
            "interval_minutes": {"type": "number", "description": "how often to look, in minutes (min 1); use 0 to stop watching"},
        },
        ["focus", "interval_minutes"],
    ),
    _function(
        "create_skill",
        "Save a working piece of Python as a reusable skill (call it later with run_skill, no rewriting). Skill code reads params from the variable args (a dict) and outputs via print.",
        {
            "name": {"type": "string", "description": "skill name, letters/digits/underscore"},
            "code": {"type": "string", "description": "Python code: read params from args, output via print"},
            "desc": {"type": "string", "description": "what this skill does"},
            "params": {"type": "string", "description": "parameter notes, e.g. path: file path"},
        },
        ["name", "code", "desc"],
    ),
    _function(
        "run_skill",
        "Run a skill you already have.",
        {
            "name": {"type": "string", "description": "skill name"},
            "args": {"type": "object", "description": "dict of params passed to the skill, optional"},
        },
        ["name"],
    ),
    _function(
        "edit_skill",
        "Rewrite an existing skill's code (for self-debugging).",
        {
            "name": {"type": "string", "description": "skill name"},
            "code": {"type": "string", "description": "the new full code"},
        },
        ["name", "code"],
    ),
    _function("list_skills", "List the skills you already have.", {}, []),
    _function(
        "spawn_agent",
        "Run a sub-agent on ONE specific subtask and WAIT for its result right here — this BLOCKS your current reply until it finishes, so the user can't chat with you meanwhile. "
        "Use ONLY for a short, self-contained subtask whose result you need RIGHT NOW to continue this same answer. For SEVERAL subtasks at once, prefer spawn_workflow (it reliably parallelizes); calling this multiple times in one turn also runs them concurrently. "
        "Costs extra compute — not for trifles. For anything that will take a while, use start_background_task instead so you stay free to chat.",
        {
            "task": {"type": "string", "description": "the subtask for the sub-agent; make it self-contained and state the wanted outcome."},
            "result_schema": {"type": "string", "description": "optional: describe the JSON shape you want back (e.g. '{\"title\":str,\"score\":number}') so the result is machine-readable; omit for free-text."},
        },
        ["task"],
    ),
    _function(
        "spawn_workflow",
        "Orchestrate SEVERAL sub-agents in one call — the reliable way to fan out or pipeline work. mode='fanout' runs all tasks IN PARALLEL "
        "(up to 4 at once) and returns all results — use for independent subtasks (research N things, review N files). "
        "mode='pipeline' runs tasks IN ORDER, feeding each one's output into the next — use when a later step builds on an earlier one. "
        "Blocks until done (use start_background_task for slow work you don't need now). Best for 3-8 sub-tasks; don't use it for a single task (that's spawn_agent).",
        {
            "mode": {"type": "string", "enum": ["fanout", "pipeline"], "description": "fanout = parallel & independent; pipeline = sequential, each builds on the previous"},
            "tasks": {"type": "array", "items": {"type": "string"}, "description": "the subtasks, each self-contained; order matters for pipeline"},
            "result_schema": {"type": "string", "description": "optional: JSON shape you want each result in (fanout) / the final result in (pipeline)"},
        },
        ["mode", "tasks"],
    ),
    _function(
        "start_background_task",
        "Hand a LONG-RUNNING task off to the background and IMMEDIATELY stay free to keep chatting — a sub-agent finishes it on its own and I'll announce the result when it's done (without cutting off whatever you're saying). "
        "This is the RIGHT choice for slow work the user doesn't need this instant: deep web research, multi-step automation, 'go do X and tell me later'. "
        "Don't grind long work inline or via the blocking spawn_agent — that freezes the conversation. (Note: a backgrounded task starts fresh without this chat's context, so state everything it needs.)",
        {"task": {"type": "string", "description": "the task to background; fully self-contained, state the wanted outcome."}},
        ["task"],
    ),
    _function(
        "plan",
        "Lay out a checklist for the current MULTI-STEP task and update it as you progress — it shows on the blackboard beside you so the user sees progress. "
        "Break down a complex task with it before starting, and update each step's status as you finish it. Send the FULL step list each time (it replaces the previous one). Don't plan a one-or-two-step trifle.",
        {
            "steps": {
                "type": "array",
                "description": "the steps, in order",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "what this step does"},
                        "status": {"type": "string", "enum": ["todo", "doing", "done"], "description": "status, default todo"},
                    },
                    "required": ["text"],
                },
            }
        },
        ["steps"],
    ),
    _function(
        "confirm",
        "Pop an 「执行 / 不执行」(Do it / Don't) button panel beside you and WAIT for the user's click; returns whether they approved. "
        "Use it (1) BEFORE any irreversible / high-risk action — deleting files/folders, overwriting an important file, git push --force, wiping data, shutting down — never do those without an approved confirm; "
        "(2) to PROACTIVELY offer a change and let them decide. Give 'action' as one short clear line of exactly what you'll do.",
        {"action": {"type": "string", "description": "what you're about to do — one short clear line for the user to approve or reject"}},
        ["action"],
    ),
]


# 不碰共享ui输入状态的工具 绕过锁并行跑
_CONCURRENT_SAFE = frozenset(
    {"http_request", "read_file", "list_dir", "run_shell", "run_python", "run_skill",
     "web_search", "web_fetch", "search_code", "glob_files", "recall_docs", "list_docs",
     "system_memory", "read_process_memory", "recall_clipboard",
     "review_diff", "run_tests", "check_shell",
     "install_package"}
)

# 从TOOLS抽必填参数 dispatch先比一遍
_REQUIRED_ARGS: dict[str, tuple[str, ...]] = {
    t["function"]["name"]: tuple(t["function"]["parameters"].get("required") or ())
    for t in TOOLS
}


def _resolve_reminder_time(fire_at: str | None, in_minutes: float | None) -> datetime | None:
    """时间解析成绝对datetime 不认返回None"""
    now = datetime.now()
    if in_minutes is not None:
        try:
            return now + timedelta(minutes=float(in_minutes))
        except (TypeError, ValueError):
            return None
    if not fire_at:
        return None
    text = fire_at.strip().replace("T", " ")  # 容忍iso写法
    # 带日期的当成绝对时刻
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    # 只给时分就落到今天 过了顺到明天
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            clock = datetime.strptime(text, fmt).time()
        except ValueError:
            continue
        fire = now.replace(hour=clock.hour, minute=clock.minute, second=clock.second, microsecond=0)
        if fire < now.replace(second=0, microsecond=0):  # 比到分钟
            fire += timedelta(days=1)
        return fire
    return None


def _parse_repeat(s: str | None) -> str:
    """repeat归一成存储格式"""
    s = (s or "").strip().lower()
    if not s:
        return ""
    if s.startswith("interval:"):
        try:
            return f"interval:{max(1, int(s.split(':', 1)[1].strip()))}"
        except (ValueError, IndexError):
            return ""
    if any(k in s for k in ("week", "周", "星期", "礼拜")):
        return "weekly"
    if any(k in s for k in ("daily", "day", "天", "每日")):
        return "daily"
    return ""


def _repeat_note(repeat: str) -> str:
    if repeat == "daily":
        return "（每天重复）"
    if repeat == "weekly":
        return "（每周重复）"
    if repeat.startswith("interval:"):
        return f"（每 {repeat.split(':', 1)[1]} 分钟重复）"
    return ""


def _schedule_reminder(message: str, fire_at: str | None, in_minutes: float | None, repeat: str | None = None) -> str:
    message = (message or "").strip()
    if not message:
        return "(No reminder content given.)"
    fire = _resolve_reminder_time(fire_at, in_minutes)
    if fire is None:
        return "(Couldn't parse the reminder time — give HH:MM or how many minutes from now.)"
    rep = _parse_repeat(repeat)
    reminders.add(fire, message, repeat=rep)
    return f"OK, at {fire.strftime('%H:%M')} I'll come tell you myself{_repeat_note(rep)}: {message}"


def _schedule_task(task: str, fire_at: str | None, in_minutes: float | None, repeat: str | None = None) -> str:
    task = (task or "").strip()
    if not task:
        return "(No task given to run at the time.)"
    fire = _resolve_reminder_time(fire_at, in_minutes)
    if fire is None:
        return "(Couldn't parse the time — give HH:MM or how many minutes from now.)"
    rep = _parse_repeat(repeat)
    reminders.add(fire, task, kind="do", repeat=rep)
    return f"OK, at {fire.strftime('%H:%M')} I'll go do it automatically{_repeat_note(rep)}: {task}"


def _list_reminders() -> str:
    items = reminders.list_all()
    if not items:
        return "(没有待触发的提醒或任务)"
    lines = []
    for r in items:
        when = r.fire_at.replace("T", " ")
        tag = "任务" if r.kind == "do" else "提醒"
        rep = (" " + _repeat_note(r.repeat)) if r.repeat else ""
        lines.append(f"#{r.id} [{tag}] {when}{rep} — {r.what}")
    return "\n".join(lines)


def _cancel_reminder(reminder_id) -> str:
    try:
        rid = int(reminder_id)
    except (TypeError, ValueError):
        return "(给我要撤销的提醒编号 id；先用 list_reminders 查。)"
    return f"已撤销 #{rid} ✓" if reminders.remove(rid) else f"(没有编号 #{rid} 的提醒——可能已经触发，或编号不对。)"


def _list_background_tasks() -> str:
    from desktop_pet.agent.bgtasks import bg_tasks
    tasks = bg_tasks.snapshot()
    if not tasks:
        return "(现在没有在跑的后台任务)"
    return "\n".join(f"#{tid} 已跑 {int(secs)}s — {task[:60]}" for tid, task, secs in tasks)


def _stop_background_task(task_id) -> str:
    from desktop_pet.agent.bgtasks import bg_tasks
    try:
        tid = int(task_id)
    except (TypeError, ValueError):
        return "(给我要停的后台任务编号 id；先用 list_background_tasks 查。)"
    if bg_tasks.stop(tid):
        return f"已让 #{tid} 停下（它会在当前这步做完后退出）。"
    return f"(没有编号 #{tid} 的后台任务——可能已经做完了。)"


_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"})


def _read_any_file(arguments: dict) -> ToolResult:
    """按扩展名分流 图片回图 pdf抽文本 其余当文本"""
    path = arguments["path"]
    suffix = Path(path).suffix.lower()
    if suffix in _IMAGE_EXTS:
        target = Path(path).expanduser()
        if not target.is_file():
            return ToolResult(f"[not a file or doesn't exist: {path}]")
        try:
            from PIL import Image
            with Image.open(target) as img:
                img.load()
                width, height = img.size
                jpeg, sent_w, sent_h = capture._encode(img)
        except Exception as exc:
            return ToolResult(f"[image read failed: {exc}]")
        return ToolResult(
            f"[image {target.name} {width}x{height}{f' (sent at {sent_w}x{sent_h})' if (sent_w, sent_h) != (width, height) else ''}]",
            to_data_url(jpeg),
        )
    if suffix == ".pdf":
        target = Path(path).expanduser()
        if not target.is_file():
            return ToolResult(f"[not a file or doesn't exist: {path}]")
        text = read_file_text(str(target))
        if text is None or not text.strip():
            return ToolResult(f"[couldn't extract text from this PDF: {path}]")
        return ToolResult(fs.paginate(text, arguments.get("offset", 0), arguments.get("max_chars", 0)))
    return ToolResult(fs.read_file(path, arguments.get("offset", 0), arguments.get("max_chars", 0)))


def dispatch(
    name: str, arguments: dict, *, shell_session=None, py_session=None
) -> ToolResult:
    """工具调用总入口 异常兜成文字"""
    # 必填参数缺了直接退回
    missing = [k for k in _REQUIRED_ARGS.get(name, ()) if k not in (arguments or {})]
    if missing:
        return ToolResult(f"[tool {name} is missing required argument(s): {', '.join(missing)}; fill in and retry]")
    try:
        if name in _CONCURRENT_SAFE:
            return _dispatch_impl(name, arguments, shell_session=shell_session, py_session=py_session)
        with _DISPATCH_LOCK:  # 动光标焦点的工具串行
            return _dispatch_impl(name, arguments, shell_session=shell_session, py_session=py_session)
    except Exception as exc:
        # 工具炸了包成文字回给模型
        return ToolResult(f"[tool {name} failed: {type(exc).__name__}: {exc}]")


def _dispatch_impl(
    name: str, arguments: dict, *, shell_session=None, py_session=None
) -> ToolResult:
    """按工具名分发到执行器"""
    python = py_session or _python  # 没传就用进程级常驻会话
    if name == "run_shell":
        if arguments.get("background"):
            return ToolResult(shell.start_background(arguments["command"]))
        return ToolResult(
            run_shell(arguments["command"], arguments.get("shell", "powershell"), session=shell_session)
        )
    if name == "check_shell":
        try:
            bg_id = int(arguments.get("id") or 0)
        except (TypeError, ValueError):
            bg_id = 0
        return ToolResult(shell.check_background(bg_id, bool(arguments.get("kill", False))))
    if name == "run_python":
        try:
            t = max(10, min(int(arguments.get("timeout") or 60), 600))
        except (TypeError, ValueError):
            t = 60
        return ToolResult(python.run(arguments["code"], timeout=t))
    if name == "read_file":
        return _read_any_file(arguments)
    if name == "write_file":
        return ToolResult(fs.write_file(arguments["path"], arguments["content"]))
    if name == "list_dir":
        return ToolResult(fs.list_dir(arguments.get("path", ".")))
    if name == "edit_file":
        return ToolResult(
            fs.edit_file(arguments["path"], arguments["old"], arguments["new"], bool(arguments.get("replace_all", False)))
        )
    if name == "search_code":
        return ToolResult(fs.search_code(arguments["pattern"], arguments.get("path", "."), context=arguments.get("context", 0)))
    if name == "glob_files":
        return ToolResult(fs.glob_files(arguments["pattern"], arguments.get("path", ".")))
    if name == "review_diff":
        return ToolResult(devtools.review_diff(arguments.get("path", "."), bool(arguments.get("staged", False))))
    if name == "run_tests":
        return ToolResult(devtools.run_tests(arguments.get("command", ""), arguments.get("path", ".")))
    if name == "http_request":
        return ToolResult(net.http_request(
            arguments["url"], arguments.get("method", "GET"), arguments.get("body"), arguments.get("headers")
        ))
    if name == "web_search":
        return ToolResult(web.web_search(arguments["query"]))
    if name == "web_fetch":
        return ToolResult(web.web_fetch(arguments["url"]))
    if name == "install_package":
        result = install_package(arguments["name"])
        python.refresh_native_dlls()  # 刷dll让新装的包当场import得到
        return ToolResult(result)
    if name == "system_memory":
        return ToolResult(sysmem.system_memory(arguments.get("top", 12)))
    if name == "read_process_memory":
        return ToolResult(
            sysmem.read_process_memory(arguments["pid"], arguments["address"], arguments.get("size", 256))
        )
    if name == "screenshot":
        scope = arguments.get("scope") or CAPTURE_FULLSCREEN
        region: tuple[int, int, int, int] | None = None
        raw_region = str(arguments.get("region") or "").strip()
        if raw_region:
            try:
                vals = tuple(int(v) for v in raw_region.split(","))
                if len(vals) != 4:  # 必须正好四个值
                    raise ValueError
                region = vals
            except ValueError:
                return ToolResult("[region must be left,top,width,height (image pixels)]")
        try:
            cap = capture_screen(scope, include_self=bool(arguments.get("include_self", False)), region=region)
        except ValueError as exc:
            return ToolResult(f"[{exc}]")
        if cap.region:
            l, t, w, h = cap.region
            # 给模型坐标换算公式
            mapping = (
                f"ADD ({l}, {t}) to coordinates you measure in this zoomed image"
                if (cap.width, cap.height) == (w, h)
                else f"full_x = {l} + x*{w}/{cap.width}, full_y = {t} + y*{h}/{cap.height}"
            )
            text = (
                f"Zoomed screenshot of region ({l},{t},{w},{h}) at native detail, {cap.width}x{cap.height}. "
                f"To convert a point HERE into full-screen image coordinates (for click / ocr_screen region): {mapping}."
            )
        elif cap.focus_title:
            text = (
                f"Screenshot taken (showing only the active window \"{cap.focus_title}\"; the rest is hidden), "
                f"resolution {cap.width}x{cap.height}; coordinates are still full-screen."
            )
        else:
            text = f"Screenshot taken, resolution {cap.width}x{cap.height}."
        return ToolResult(text, to_data_url(cap.png_bytes))
    if name == "ocr_screen":
        return ToolResult(vision.ocr_screen(arguments.get("region", "")))
    if name == "find_on_screen":
        return ToolResult(vision.find_on_screen(arguments["template_path"], arguments.get("confidence", 0.8)))
    if name == "screen_elements":
        from desktop_pet.eyes import elements
        jpeg, listing = elements.screen_elements(arguments.get("region", ""))
        return ToolResult(listing, to_data_url(jpeg) if jpeg else None)
    if name == "act_element":
        from desktop_pet.eyes import elements
        return ToolResult(
            elements.act_element(
                int(arguments["index"]), arguments.get("action", "click"), arguments.get("text", ""),
                mode=arguments.get("mode", "auto"),
            )
        )
    if name == "list_windows":
        return ToolResult(windows.list_windows())
    if name == "focus_window":
        return ToolResult(windows.focus_window(arguments["title"]))
    if name == "manage_window":
        return ToolResult(windows.manage_window(
            arguments["title"], arguments["action"],
            arguments.get("x"), arguments.get("y"),
            arguments.get("width"), arguments.get("height"),
        ))
    if name == "read_clipboard":
        return ToolResult(clipboard.read_clipboard())
    if name == "recall_clipboard":
        from desktop_pet.clipsampler import sampler
        if not sampler.enabled:
            return ToolResult("(clipboard sense is off — the user hasn't enabled it)")
        latest = sampler.latest_interesting()
        if not latest:
            return ToolResult("(nothing notable copied recently)")
        kind, body = latest
        return ToolResult(f"Most recent copied ({kind}):\n{body[:2000]}")
    if name == "write_clipboard":
        return ToolResult(clipboard.write_clipboard(arguments["text"]))
    if name == "click":
        return ToolResult(mouse.click(arguments["x"], arguments["y"]))
    if name == "double_click":
        return ToolResult(mouse.double_click(arguments["x"], arguments["y"]))
    if name == "right_click":
        return ToolResult(mouse.right_click(arguments["x"], arguments["y"]))
    if name == "move_mouse":
        return ToolResult(mouse.move(arguments["x"], arguments["y"]))
    if name == "scroll":
        return ToolResult(mouse.scroll(arguments["amount"]))
    if name == "type_text":
        return ToolResult(keyboard.type_text(arguments["text"]))
    if name == "press_keys":
        return ToolResult(keyboard.press_keys(arguments["keys"]))
    if name == "set_preference":
        return ToolResult(store.set_preference(arguments["key"], arguments["value"]))
    if name == "remember":
        return ToolResult(store.remember(arguments["content"]))
    if name == "recall":
        return ToolResult(store.recall(arguments["query"]))
    if name == "note_env":
        return ToolResult(store.note_env(arguments["key"], arguments["value"]))
    if name == "forget_memory":
        return ToolResult(store.forget(arguments["query"]))
    if name == "ingest_docs":
        return ToolResult(docs.ingest(arguments["path"]))
    if name == "recall_docs":
        return ToolResult(docs.recall(arguments["query"]))
    if name == "list_docs":
        return ToolResult(docs.summary())
    if name == "forget_docs":
        return ToolResult(docs.forget(arguments.get("source")))
    if name == "schedule_reminder":
        return ToolResult(
            _schedule_reminder(arguments["message"], arguments.get("fire_at"), arguments.get("in_minutes"), arguments.get("repeat"))
        )
    if name == "schedule_task":
        return ToolResult(
            _schedule_task(arguments["task"], arguments.get("fire_at"), arguments.get("in_minutes"), arguments.get("repeat"))
        )
    if name == "list_reminders":
        return ToolResult(_list_reminders())
    if name == "cancel_reminder":
        return ToolResult(_cancel_reminder(arguments.get("reminder_id")))
    if name == "list_background_tasks":
        return ToolResult(_list_background_tasks())
    if name == "stop_background_task":
        return ToolResult(_stop_background_task(arguments.get("task_id")))
    if name == "create_skill":
        return ToolResult(
            skills.create(
                arguments["name"], arguments["code"], arguments["desc"], arguments.get("params", "")
            )
        )
    if name == "run_skill":
        code = skills.code(arguments["name"])
        if code is None:
            return ToolResult(f"No skill named \"{arguments['name']}\"; use list_skills to see what's available.")
        raw_args = arguments.get("args")
        if isinstance(raw_args, str):  # args是字符串就解一层json
            try:
                raw_args = json.loads(raw_args)
            except (ValueError, TypeError):
                raw_args = {}
        if not isinstance(raw_args, dict):
            raw_args = {}
        # 入参用repr注入成全局args
        script = f"args = {raw_args!r}\n\n{code}"
        return ToolResult(python.run(script))
    if name == "edit_skill":
        return ToolResult(skills.edit(arguments["name"], arguments["code"]))
    if name == "list_skills":
        return ToolResult(skills.listing())
    if name.startswith("mcp__"):  # mcp前缀甩给mcp_hub
        return ToolResult(mcp_hub.call(name, arguments))
    return ToolResult(f"[unknown tool: {name}]")
