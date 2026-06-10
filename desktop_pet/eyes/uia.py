# author: bdth
# email: 2074055628@qq.com
# uiautomation读前台可交互控件并执行操作

from __future__ import annotations

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
# 遍历上限
_MAX_NODES = 400
_MAX_DEPTH = 14


def available() -> bool:
    return _auto is not None


_UIA_IS_PASSWORD = 30019


def focused_is_password() -> bool:
    """当前焦点控件是不是密码框"""
    if _auto is None:
        return False
    try:
        ctrl = _auto.GetFocusedControl()
        if ctrl is None:
            return False
        return bool(ctrl.GetPropertyValue(_UIA_IS_PASSWORD))
    except Exception:
        return False


def _window(title: str | None):
    """按标题找窗口 无标题取前台"""
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
    queue = deque([(root, 0)])
    seen = 0
    while queue and seen < _MAX_NODES:
        ctrl, depth = queue.popleft()
        yield ctrl
        seen += 1
        if depth < _MAX_DEPTH:
            try:
                queue.extend((child, depth + 1) for child in ctrl.GetChildren())
            except Exception:
                pass
    # 提前退了标记截断
    if state is not None and queue:
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
    # 削掉control尾巴
    try:
        return ctrl.ControlTypeName.replace("Control", "")
    except Exception:
        return ""


_INVOKABLE_KINDS = {"Button", "MenuItem", "Hyperlink", "CheckBox", "RadioButton", "ListItem", "TabItem", "SplitButton"}
_MAX_ELEMENTS = 80


def interactive_elements(title: str | None = None) -> tuple[list[dict], bool]:
    """扫前台窗口可交互控件"""
    if _auto is None:
        return [], False
    win = _window(title)
    if win is None:
        return [], False
    from desktop_pet.eyes.capture import current_geom, set_geom

    # 临时切坐标系扫完还原
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
                # 零尺寸的跳过
                if rect.width() <= 0 or rect.height() <= 0:
                    continue
                box = (rect.left, rect.top, rect.right, rect.bottom)
                center = (rect.xcenter(), rect.ycenter())
            except Exception:
                continue
            out.append({
                "kind": kind, "name": name, "rect_abs": box, "center_abs": center,
                "ctrl": ctrl, "invokable": kind in _INVOKABLE_KINDS,
            })
            # 收够就收手标记截断
            if len(out) >= _MAX_ELEMENTS:
                state["truncated"] = True
                break
    finally:
        set_geom(saved_geom)
    return out, state["truncated"]


def invoke(ctrl) -> bool:
    """不动鼠标触发控件 各pattern依次试"""
    try:
        pattern = ctrl.GetInvokePattern()
        if pattern is not None:
            pattern.Invoke()
            return True
    except Exception:
        pass
    try:
        pattern = ctrl.GetTogglePattern()
        if pattern is not None:
            pattern.Toggle()
            return True
    except Exception:
        pass
    try:
        pattern = ctrl.GetSelectionItemPattern()
        if pattern is not None:
            pattern.Select()
            return True
    except Exception:
        pass
    try:
        pattern = ctrl.GetExpandCollapsePattern()
        if pattern is not None:
            pattern.Expand()
            return True
    except Exception:
        pass
    try:
        pattern = ctrl.GetLegacyIAccessiblePattern()
        if pattern is not None:
            pattern.DoDefaultAction()
            return True
    except Exception:
        pass
    return False


def native_hwnd(ctrl) -> int:
    # 拿底层hwnd 没有就0
    try:
        return int(ctrl.NativeWindowHandle or 0)
    except Exception:
        return 0


def set_value(ctrl, text: str) -> bool:
    """value pattern直接灌值"""
    try:
        pattern = ctrl.GetValuePattern()
        if pattern is not None:
            pattern.SetValue(text)
            return True
    except Exception:
        pass
    return False


