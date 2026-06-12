# author: bdth
# email: 2074055628@qq.com
# uiautomation读前台可交互控件并执行操作
# 所有UIA活全钉在一条常驻STA线程上 对外只发整数token不发live控件
# 根由 COM对象在哪个套间建就只能在哪个套间用和放 跨线程释放直接段错误整个进程
# agent跑在worker线程 子代理后台任务还会孵临时线程 都裸碰UIA必崩 这条独占线程是命门

from __future__ import annotations

import queue
import threading
from collections import deque

try:
    import uiautomation as _auto
except Exception:
    _auto = None


# 只收这些controltype
_INTERACTIVE = {
    "Button", "Edit", "CheckBox", "RadioButton", "ComboBox", "List", "ListItem",
    "MenuItem", "Menu", "Hyperlink", "TabItem", "TreeItem", "Slider", "Spinner", "Document",
}
_INVOKABLE_KINDS = {"Button", "MenuItem", "Hyperlink", "CheckBox", "RadioButton", "ListItem", "TabItem", "SplitButton"}
# 遍历上限
_MAX_NODES = 400
_MAX_DEPTH = 14
_MAX_ELEMENTS = 80
_UIA_IS_PASSWORD = 30019
_CALL_TIMEOUT = 12.0  # 单次UIA调用兜底超时 卡住不拖死调用方


# ── 独占UIA线程 所有控件操作marshal到这里串行执行 ──────────────
_jobs: "queue.Queue" = queue.Queue()
_thread: threading.Thread | None = None
_thread_lock = threading.Lock()
# token到控件的注册表 只这条线程读写 控件的生与死都在这套间内
_registry: dict[int, object] = {}
_next_token = 1


def _pump() -> None:
    """UIA线程主体 立起STA套间后死循环取活干"""
    try:
        import ctypes
        ctypes.windll.ole32.CoInitializeEx(None, 0x2)  # 0x2=APARTMENTTHREADED
    except Exception:
        pass
    while True:
        fn, done, box = _jobs.get()
        try:
            box[0] = fn()
        except Exception as exc:  # 异常也带回去 不让调用方瞎等
            box[1] = exc
        finally:
            done.set()


def _ensure_thread() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    with _thread_lock:
        if _thread is None or not _thread.is_alive():
            t = threading.Thread(target=_pump, name="mochi-uia", daemon=True)
            t.start()
            _thread = t


def _call(fn):
    """把fn丢到UIA线程跑 拿回结果 当前已在该线程就直接调防自死锁"""
    if threading.current_thread() is _thread:
        return fn()
    _ensure_thread()
    done = threading.Event()
    box: list = [None, None]
    _jobs.put((fn, done, box))
    if not done.wait(_CALL_TIMEOUT):
        return None  # 超时按失败处理 不抛
    if box[1] is not None:
        return None
    return box[0]


def available() -> bool:
    return _auto is not None


# ── 以下私有函数全部在UIA线程里跑 不要从外部直接调 ──────────────
def _window(title: str | None):
    if _auto is None:
        return None
    if not title:
        try:
            return _auto.GetForegroundControl()
        except Exception:
            return None
    try:
        for child in _auto.GetRootControl().GetChildren():
            try:
                if title.lower() in (child.Name or "").lower():
                    return child
            except Exception:
                continue
    except Exception:
        return None
    return None


def _walk(root, state: dict | None = None):
    """bfs走控件树"""
    q = deque([(root, 0)])
    seen = 0
    while q and seen < _MAX_NODES:
        ctrl, depth = q.popleft()
        yield ctrl
        seen += 1
        if depth < _MAX_DEPTH:
            try:
                q.extend((child, depth + 1) for child in ctrl.GetChildren())
            except Exception:
                pass
    if state is not None and q:
        state["truncated"] = True


def _sync_geom(win) -> None:
    """坐标系对到窗口所在屏"""
    try:
        from desktop_pet.eyes.capture import set_geom_for_point
        rect = win.BoundingRectangle
        set_geom_for_point(rect.xcenter(), rect.ycenter())
    except Exception:
        pass


def _kind(ctrl) -> str:
    try:
        return ctrl.ControlTypeName.replace("Control", "")
    except Exception:
        return ""


def _native_hwnd(ctrl) -> int:
    try:
        return int(ctrl.NativeWindowHandle or 0)
    except Exception:
        return 0


# 这些控件值得把当前内容读出来 让agent看见框里已有什么 不是只看标签
_VALUE_KINDS = {"Edit", "ComboBox", "Document", "Spinner"}
_VALUE_CAP = 80


def _read_value(ctrl, kind: str) -> str:
    """读输入类控件的当前值 给agent看清框里残留了什么 读不到返回空串"""
    if kind not in _VALUE_KINDS:
        return ""
    try:
        pattern = ctrl.GetValuePattern()
        if pattern is not None:
            val = (pattern.Value or "").strip()
            if val:
                return val[:_VALUE_CAP]
    except Exception:
        pass
    return ""


def _do_scan(title: str | None) -> tuple[list[dict], bool]:
    """在UIA线程扫一遍 旧token先全释放再发新的 控件存进注册表只留token出去"""
    global _next_token
    if _auto is None:
        return [], False
    win = _window(title)
    if win is None:
        return [], False
    from desktop_pet.eyes.capture import current_geom, set_geom

    # 上一轮的控件在这条线程上释放 套间对得上 安全
    _registry.clear()
    saved_geom = current_geom()
    _sync_geom(win)
    out: list[dict] = []
    state = {"truncated": False}
    try:
        for ctrl in _walk(win, state):
            kind = _kind(ctrl)
            if kind not in _INTERACTIVE:
                continue
            try:
                name = (ctrl.Name or "").strip()
                rect = ctrl.BoundingRectangle
                if rect.width() <= 0 or rect.height() <= 0:  # 零尺寸跳过
                    continue
                box = (rect.left, rect.top, rect.right, rect.bottom)
                center = (rect.xcenter(), rect.ycenter())
            except Exception:
                continue
            token = _next_token
            _next_token += 1
            _registry[token] = ctrl
            out.append({
                "token": token, "kind": kind, "name": name,
                "rect_abs": box, "center_abs": center,
                "invokable": kind in _INVOKABLE_KINDS, "hwnd": _native_hwnd(ctrl),
                "value": _read_value(ctrl, kind),
            })
            if len(out) >= _MAX_ELEMENTS:
                state["truncated"] = True
                break
    finally:
        set_geom(saved_geom)
    return out, state["truncated"]


def _do_invoke(ctrl) -> bool:
    """不动鼠标触发控件 各pattern依次试"""
    for getter, action in (
        ("GetInvokePattern", lambda p: p.Invoke()),
        ("GetTogglePattern", lambda p: p.Toggle()),
        ("GetSelectionItemPattern", lambda p: p.Select()),
        ("GetExpandCollapsePattern", lambda p: p.Expand()),
        ("GetLegacyIAccessiblePattern", lambda p: p.DoDefaultAction()),
    ):
        try:
            pattern = getattr(ctrl, getter)()
            if pattern is not None:
                action(pattern)
                return True
        except Exception:
            continue
    return False


def _do_set_value(ctrl, text: str) -> bool:
    try:
        pattern = ctrl.GetValuePattern()
        if pattern is not None:
            pattern.SetValue(text)
            return True
    except Exception:
        pass
    return False


def _do_scroll_into_view(ctrl) -> bool:
    """把控件滚进可视区 长列表里目标在屏外时先滚出来才点得到
    ScrollItemPattern最直接 退而求其次用SetFocus也常能带动滚动"""
    try:
        pattern = ctrl.GetScrollItemPattern()
        if pattern is not None:
            pattern.ScrollIntoView()
            return True
    except Exception:
        pass
    try:
        ctrl.SetFocus()
        return True
    except Exception:
        pass
    return False


# ── 对外接口 全部marshal到UIA线程 参数只收token和纯数据 ──────────
def focused_is_password() -> bool:
    """当前焦点控件是不是密码框"""
    if _auto is None:
        return False

    def job() -> bool:
        ctrl = _auto.GetFocusedControl()
        if ctrl is None:
            return False
        return bool(ctrl.GetPropertyValue(_UIA_IS_PASSWORD))

    return bool(_call(job))


def interactive_elements(title: str | None = None) -> tuple[list[dict], bool]:
    """扫前台窗口可交互控件 返回纯数据元素列表和是否截断 元素里的token拿去invoke"""
    result = _call(lambda: _do_scan(title))
    return result if result is not None else ([], False)


def invoke(token: int) -> bool:
    """按token不动鼠标触发控件 查表也在UIA线程做 控件引用绝不外泄"""
    if not token:
        return False

    def job() -> bool:
        ctrl = _registry.get(token)
        return _do_invoke(ctrl) if ctrl is not None else False

    return bool(_call(job))


def set_value(token: int, text: str) -> bool:
    """按token用value pattern直接灌值"""
    if not token:
        return False

    def job() -> bool:
        ctrl = _registry.get(token)
        return _do_set_value(ctrl, text) if ctrl is not None else False

    return bool(_call(job))


def scroll_into_view(token: int) -> bool:
    """按token把控件滚进可视区"""
    if not token:
        return False

    def job() -> bool:
        ctrl = _registry.get(token)
        return _do_scroll_into_view(ctrl) if ctrl is not None else False

    return bool(_call(job))
