# author: bdth
# email: 2074055628@qq.com
# 基于 uiautomation 读取前台窗口的可交互控件并执行点击/赋值等操作

from __future__ import annotations

from collections import deque

try:
    import uiautomation as _auto
except Exception:
    _auto = None

# 只收这些 ControlType——纯静态文本/图片不要，否则一屏几百个节点全塞进来。
_INTERACTIVE = {
    "Button", "Edit", "CheckBox", "RadioButton", "ComboBox", "List", "ListItem",
    "MenuItem", "Menu", "Hyperlink", "TabItem", "TreeItem", "Slider", "Spinner", "Document",
}
# 整棵 UIA 树可能上千节点，硬封顶——遇到 Electron/超长列表别把遍历卡死。
_MAX_NODES = 400
_MAX_DEPTH = 14


def available() -> bool:
    return _auto is not None


def _window(title: str | None):
    """无 title 取前台；给了只在桌面根的直接子里按名模糊配——不往深里递归，顶层窗口都挂在这层。"""
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
    """BFS 走控件树，到 _MAX_NODES 就停——宽度优先，先把浅层的控件捞全，深处截断了影响也小。"""
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
    # 队列没空就是撞上 _MAX_NODES 提前退了——告诉上层结果不全，别当成"窗口就这点东西"。
    if state is not None and queue:
        state["truncated"] = True


def _sync_geom(win) -> None:
    """把 capture 的坐标系对到目标窗口所在那块屏——多屏时 UIA 给的是绝对坐标，得让换算认对屏。"""
    try:
        from desktop_pet.eyes.capture import set_geom_for_point

        rect = win.BoundingRectangle
        set_geom_for_point(rect.xcenter(), rect.ycenter())
    except Exception:
        pass


def _kind(ctrl) -> str:
    # UIA 报的是 "ButtonControl" 这种，削掉尾巴对齐 _INTERACTIVE 里的裸名。
    try:
        return ctrl.ControlTypeName.replace("Control", "")
    except Exception:
        return ""


_INVOKABLE_KINDS = {"Button", "MenuItem", "Hyperlink", "CheckBox", "RadioButton", "ListItem", "TabItem", "SplitButton"}
_MAX_ELEMENTS = 80


def interactive_elements(title: str | None = None) -> tuple[list[dict], bool]:
    """扫前台窗口的可交互控件。每项连 ctrl 句柄一起带回去——后面 invoke/set_value 还要拿它直接操作，光有坐标不够。"""
    if _auto is None:
        return [], False
    win = _window(title)
    if win is None:
        return [], False
    from desktop_pet.eyes.capture import current_geom, set_geom

    # 临时把坐标系切到目标窗口那屏，扫完无论成败都得还回去——别污染调用方原来的几何。
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
                # 零尺寸的多半是隐藏/离屏控件——点了也没用，跳过。
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
            # 收够 80 个就收手——丢回去给模型的清单太长反而挑花眼，标记截断让上层知道还有。
            if len(out) >= _MAX_ELEMENTS:
                state["truncated"] = True
                break
    finally:
        set_geom(saved_geom)
    return out, state["truncated"]


def invoke(ctrl) -> bool:
    """不动鼠标直接触发控件：Invoke → Toggle → SelectionItem.Select → ExpandCollapse → Legacy 依次试，哪个成了就返回。"""
    try:
        pattern = ctrl.GetInvokePattern()
        if pattern is not None:
            pattern.Invoke()
            return True
    except Exception:
        pass
    # 勾选框/开关没有 Invoke，只认 Toggle。
    try:
        pattern = ctrl.GetTogglePattern()
        if pattern is not None:
            pattern.Toggle()
            return True
    except Exception:
        pass
    # 列表项/标签页这类要靠 SelectionItem 选中，本身不可 Invoke。
    try:
        pattern = ctrl.GetSelectionItemPattern()
        if pattern is not None:
            pattern.Select()
            return True
    except Exception:
        pass
    # 树节点/下拉只能展开——拿不到点击语义时退而求其次把它撑开。
    try:
        pattern = ctrl.GetExpandCollapsePattern()
        if pattern is not None:
            pattern.Expand()
            return True
    except Exception:
        pass
    # 最后兜底：老式 MSAA 控件(自绘/旧程序)什么现代 pattern 都不给，只剩 DoDefaultAction。
    try:
        pattern = ctrl.GetLegacyIAccessiblePattern()
        if pattern is not None:
            pattern.DoDefaultAction()
            return True
    except Exception:
        pass
    return False


def native_hwnd(ctrl) -> int:
    # 拿底层 HWND——很多控件(尤其子控件)根本没自己的窗口句柄，那就 0，调用方据此回退到坐标点击。
    try:
        return int(ctrl.NativeWindowHandle or 0)
    except Exception:
        return 0


def set_value(ctrl, text: str) -> bool:
    """直接给控件灌值——比模拟逐键输入稳，但只对支持 ValuePattern 的(普通 Edit/ComboBox)管用。"""
    try:
        pattern = ctrl.GetValuePattern()
        if pattern is not None:
            pattern.SetValue(text)
            return True
    except Exception:
        pass
    return False


