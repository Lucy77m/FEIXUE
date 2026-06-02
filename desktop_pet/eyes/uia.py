# author: bdth
# email: 2074055628@qq.com
# 基于 uiautomation 读取前台窗口的可交互控件并执行点击/赋值等操作

from __future__ import annotations

from collections import deque

try:
    import uiautomation as _auto
except Exception:  # noqa: BLE001
    _auto = None

_INTERACTIVE = {
    "Button", "Edit", "CheckBox", "RadioButton", "ComboBox", "List", "ListItem",
    "MenuItem", "Menu", "Hyperlink", "TabItem", "TreeItem", "Slider", "Spinner", "Document",
}
_MAX_NODES = 400
_MAX_DEPTH = 14
_MAX_LISTED = 60


def available() -> bool:
    return _auto is not None


def _window(title: str | None):
    if _auto is None:
        return None
    if not title:
        try:
            return _auto.GetForegroundControl()
        except Exception:  # noqa: BLE001
            return None
    try:
        for child in _auto.GetRootControl().GetChildren():
            try:
                if title.lower() in (child.Name or "").lower():
                    return child
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        return None
    return None


def _walk(root):
    queue = deque([(root, 0)])  # deque.popleft() 是 O(1)；原来 list.pop(0) 出队是 O(n)，400 节点最坏 ~8 万次搬移
    seen = 0
    while queue and seen < _MAX_NODES:
        ctrl, depth = queue.popleft()
        yield ctrl
        seen += 1
        if depth < _MAX_DEPTH:
            try:
                queue.extend((child, depth + 1) for child in ctrl.GetChildren())
            except Exception:  # noqa: BLE001
                pass


def _sync_geom(win) -> None:
    try:
        from desktop_pet.eyes.capture import set_geom_for_point

        rect = win.BoundingRectangle
        set_geom_for_point(rect.xcenter(), rect.ycenter())
    except Exception:  # noqa: BLE001
        pass


def _kind(ctrl) -> str:
    try:
        return ctrl.ControlTypeName.replace("Control", "")
    except Exception:  # noqa: BLE001
        return ""


_INVOKABLE_KINDS = {"Button", "MenuItem", "Hyperlink", "CheckBox", "RadioButton", "ListItem", "TabItem", "SplitButton"}
_MAX_ELEMENTS = 80


def interactive_elements(title: str | None = None) -> list[dict]:
    if _auto is None:
        return []
    win = _window(title)
    if win is None:
        return []
    from desktop_pet.eyes.capture import current_geom, set_geom

    saved_geom = current_geom()
    _sync_geom(win)
    out: list[dict] = []
    try:
        for ctrl in _walk(win):
            kind = _kind(ctrl)
            if kind not in _INTERACTIVE:
                continue
            try:
                name = (ctrl.Name or "").strip()
                rect = ctrl.BoundingRectangle
                if rect.width() <= 0 or rect.height() <= 0:
                    continue
                box = (rect.left, rect.top, rect.right, rect.bottom)
                center = (rect.xcenter(), rect.ycenter())
            except Exception:  # noqa: BLE001
                continue
            out.append({
                "kind": kind, "name": name, "rect_abs": box, "center_abs": center,
                "ctrl": ctrl, "invokable": kind in _INVOKABLE_KINDS,
            })
            if len(out) >= _MAX_ELEMENTS:
                break
    finally:
        # 本函数返回的是绝对坐标；_sync_geom 对全局 _geom 的改动不应泄漏给后续 raw click/move
        # （多屏下 getActiveWindow 与 GetForegroundControl 分歧时会用错显示器原点）。还原进入时的值。
        set_geom(saved_geom)
    return out


def invoke(ctrl) -> bool:
    try:
        pattern = ctrl.GetInvokePattern()
        if pattern is not None:
            pattern.Invoke()
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        pattern = ctrl.GetTogglePattern()
        if pattern is not None:
            pattern.Toggle()
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def set_value(ctrl, text: str) -> bool:
    try:
        pattern = ctrl.GetValuePattern()
        if pattern is not None:
            pattern.SetValue(text)
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


