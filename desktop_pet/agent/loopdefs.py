# author: bdth
# email: 2074055628@qq.com
# agent循环的公共常量 工具名单 预算 超时 都集中在这

from __future__ import annotations

import httpx

from desktop_pet.settings import DATA_DIR


_SUBAGENT_BUDGET = (12, 40)
_MAX_EMPTY_RETRIES = 2
_FRESH_AFTER = 25 * 60
_RUN_CANCELLED = "\x00cancelled"
_MAX_SUBAGENT_DEPTH = 1
_SPAWN_TOOL = "spawn_agent"
_BACKGROUND_TOOL = "start_background_task"
_PLAN_TOOL = "plan"
_IMAGE_TOOL = "show_image"
_GIF_TOOL = "play_gif"
_PERFORM_TOOL = "perform"
_CONFIRM_TOOL = "confirm"
_WATCH_TOOL = "set_screen_watch"
_WORKFLOW_TOOL = "spawn_workflow"
_MAX_WORKFLOW_TASKS = 8
_COSMETIC_TOOLS = frozenset({_PERFORM_TOOL, _PLAN_TOOL, _IMAGE_TOOL, _GIF_TOOL})
_REFLECT_MIN_CHARS = 50
_ATTACH_FILE_CHARS = 6000
_SUMMARY_MAX_CHARS = 4_000
_SUMMARY_SRC_MAX_CHARS = 12_000
_SUMMARY_TIMEOUT = 30.0
_SESSION_PATH = DATA_DIR / "session.json"
def _perform_names() -> str:
    from desktop_pet.pet.behaviors import registry
    from desktop_pet.pet.behaviors.registry import Category
    from desktop_pet.pet.activities import _ACTIVITIES
    reactions = sorted(n for n in registry.names(Category.REACTION))
    return "skits: " + " ".join(_ACTIVITIES) + " ; actions: " + " ".join(reactions)


def _is_performable(name: str) -> bool:
    from desktop_pet.pet.behaviors import registry
    from desktop_pet.pet.behaviors.registry import Category
    from desktop_pet.pet.activities import _ACTIVITIES
    if name in _ACTIVITIES:
        return True
    spec = registry.get(name)
    return spec is not None and spec.category == Category.REACTION
_WEB_TOOLS = frozenset({"web_search", "web_fetch", "http_request", "install_package"})
_CONTROL_TOOLS = frozenset({
    "screenshot", "screen_elements", "act_element", "list_windows", "focus_window", "manage_window",
    "click", "double_click", "right_click", "move_mouse", "scroll", "type_text", "press_keys",
    "read_clipboard", "write_clipboard", "read_process_memory", "recall_clipboard",
    _WATCH_TOOL,
})
_SHELL_TOOLS = frozenset({
    "run_shell", "check_shell", "run_python", "run_skill", "create_skill", "edit_skill", "write_file", "edit_file",
    "review_diff", "run_tests",
})
# 真正会接管鼠标键盘去操作电脑的工具 执行期间弹浮层让用户知道 值是给用户看的动作名
_INPUT_TOOL_HINT = {
    "click": "点击", "double_click": "双击", "right_click": "右键点击",
    "move_mouse": "移动鼠标", "scroll": "滚动页面",
    "type_text": "输入文字", "press_keys": "按快捷键", "act_element": "操作界面元素",
}
_MAX_PARALLEL_SUBAGENTS = 4
_HISTORY_TOKEN_BUDGET = 24_000

# 一回合里可以真并发跑的只读工具 无共享会话 不抢鼠标焦点 无远端副作用
# 刻意比 tools._CONCURRENT_SAFE 窄 排除
#   run_shell run_python run_skill install_package 共享单个 shell python 会话或改 pip 环境
#   http_request 可发有副作用的方法 并发会重复触发远端写
#   system_memory 底层 psutil.process_iter 的进程缓存非线程安全 并发可能抛
_PARALLEL_SAFE = frozenset({
    "read_file", "list_dir", "search_code", "glob_files",
    "web_search", "web_fetch",
    "recall_docs", "list_docs", "recall_clipboard", "review_diff",
})
_MAX_PARALLEL_TOOLS = 6
_STUCK_LIMIT = 3  # 同名同参连续失败这么多次 回灌一句别原地打转换思路

_REQUEST_TIMEOUT = httpx.Timeout(connect=8.0, read=90.0, write=30.0, pool=8.0)
_BACKGROUND_TIMEOUT = 45.0
_MAX_RETRIES = 0          # SDK内置重试关掉 退避策略由_complete显式接管

# 瞬时错误退避 限流和5xx和网络抖动才退避 400 401 404快速失败不退
_RETRY_MAX = 3            # 主调用最多额外重试几次
_RETRY_BASE_S = 1.0       # 首次退避基准 之后翻倍
_RETRY_CAP_S = 16.0       # 单次退避上限

