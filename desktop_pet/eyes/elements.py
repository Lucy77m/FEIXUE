# author: bdth
# email: 2074055628@qq.com
# 把屏幕上可操作元素编号、标注并提供按编号点击/输入的能力

from __future__ import annotations

import time
from collections import Counter

from PIL import Image, ImageDraw, ImageFont

from desktop_pet.eyes import capture, detect, uia

_LAST: list[dict] = []
_COLORS = {"uia": (80, 230, 140), "ocr": (90, 190, 255), "icon": (255, 180, 70)}
_LABEL_INK = (16, 16, 22)

# 屏幕没变就复用上次编号结果：小灰度缩略图当指纹，省掉 UIA/OCR/检测整套重算。TTL 2s 兜底，怕指纹漏判。
_CACHE_TTL_S = 2.0
_cache_fp: bytes = b""
_cache_ts: float = 0.0
_cache_result: "tuple[bytes, str] | None" = None

# 点完截图比对，判断"到底有没有生效"。settle 给窗口 0.35s 重绘的时间；
# 差异像素超 _VERIFY_FRAC(0.8%)且单像素灰度差超 _VERIFY_DELTA 才算"变了"，滤掉光标闪烁/时钟跳秒这种噪点。
_VERIFY_SETTLE_S = 0.35
_VERIFY_DELTA = 16
_VERIFY_FRAC = 0.008


def _verify_snapshot():
    """抓活动窗当前帧 → 320×180 灰度 numpy，给点击前后比对当基准；抓不到返回 None(不报错，降级成不验证)。"""
    import numpy as np

    try:
        img = capture.grab_active()
    except Exception:
        return None
    small = img.convert("L").resize((320, 180), Image.Resampling.BILINEAR)
    return np.asarray(small, dtype=np.int16)


def _verify_changed(before):
    """对比 before 快照看屏幕动没动；没基准或尺寸对不上没法判，返回 None。"""
    if before is None:
        return None
    import numpy as np

    after = _verify_snapshot()
    if after is None or after.shape != before.shape:  # 尺寸变了说明窗口本身动过，没法逐像素比，弃判
        return None
    return bool((np.abs(after - before) > _VERIFY_DELTA).mean() > _VERIFY_FRAC)


def _inside(point: tuple[int, int], rect: tuple[int, int, int, int]) -> bool:
    x, y = point
    l, t, r, b = rect
    return l <= x <= r and t <= y <= b


def _fingerprint(img: Image.Image) -> bytes:
    """缩略灰度的原始字节当缓存指纹——逐字节匹配，分辨率固定才比得了。"""
    return img.convert("L").resize((320, 180), Image.Resampling.BILINEAR).tobytes()


def _label_for_icon(icon_rect: tuple[int, int, int, int], ocr_els: list[dict]) -> str:
    """给检测出的图标找它的文字标签：横向对齐(±70%宽)、且在图标内或正下方的 OCR 文本，挑最近的。找不到返回空。"""
    il, it, ir, ib = icon_rect
    iw, ih = ir - il, ib - it
    if iw <= 0 or ih <= 0:
        return ""
    icx = (il + ir) / 2.0
    best, best_score = "", 1e9
    for o in ocr_els:
        ol, ot, orr, ob = o["rect_abs"]
        ocx = (ol + orr) / 2.0
        if abs(ocx - icx) > iw * 0.7:  # 横向偏太多，不是这个图标的标签
            continue
        inside = ot >= it - 2 and ob <= ib + 2
        below = 0 <= ot - ib <= max(26, ih * 0.7)  # 图标正下方一行内——典型托盘/桌面图标的文字摆法
        if not (inside or below):
            continue
        score = abs(ocx - icx) + max(0, ot - ib)  # 越居中、越贴近图标得分越低
        if score < best_score:
            best, best_score = o["text"], score
    return best[:46]


def _font(size: int) -> ImageFont.ImageFont:
    """优先粗体(Segoe→Arial)，编号看得清；系统没装就退默认位图字体(不认 size，会偏小)。"""
    for name in ("segoeuib.ttf", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _annotate(img: Image.Image, elements: list[dict], ox: int, oy: int) -> Image.Image:
    """把每个元素框出来并标编号 → 给模型看的标注图。颜色按来源(uia/ocr/icon)区分。ox/oy 是裁剪偏移，绝对坐标减回去才落在画布上。"""
    canvas = img.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas, "RGBA")
    size = max(15, canvas.height // 55)  # 字号随分辨率走，4K 屏上别小到看不见
    font = _font(size)
    for el in elements:
        l, t, r, b = el["rect_abs"]
        l, t, r, b = l - ox, t - oy, r - ox, b - oy
        color = _COLORS.get(el.get("source", "ocr"), _COLORS["ocr"])
        draw.rectangle((l, t, r, b), outline=color + (235,), width=max(2, size // 8))
        label = str(el["idx"])
        tw = draw.textlength(label, font=font)
        lh = size + 4
        lx, ly = l, max(0, t - lh)
        draw.rectangle((lx, ly, lx + tw + 10, ly + lh), fill=color + (235,))
        draw.text((lx + 5, ly + 1), label, fill=_LABEL_INK, font=font)
    return canvas


def screen_elements(region: str = "") -> tuple[bytes, str]:
    """扫活动窗的可操作元素 → (标注图 jpeg, 编号清单文本)。三路汇总：UIA 控件 + OCR 文本 + 视觉图标，按序去重编号。
    region(left,top,width,height，图像像素)只扫局部，编号会变所以 region 也进缓存指纹。"""
    import numpy as np

    from desktop_pet.executor import vision

    img, geom = capture.grab_active_geom()
    ox, oy, ow, oh = geom
    region_abs: tuple[int, int, int, int] | None = None
    if region.strip():
        from desktop_pet.eyes.capture import _scale
        try:
            left, top, w, h = (int(v) for v in region.split(","))
        except (ValueError, IndexError):
            return b"", "[region must be left,top,width,height (image pixels)]"
        if w <= 0 or h <= 0 or left < 0 or top < 0:
            return b"", "[region 非法：left/top 不能为负、width/height 必须为正]"
        # region 是模型在"缩放后的图"上量的；除以 _scale 换回原始截图像素再裁，不然高 DPI 屏会错位
        s = _scale(ow, oh) or 1.0
        nl, nt = int(left / s), int(top / s)
        nr, nb = min(img.width, int((left + w) / s)), min(img.height, int((top + h) / s))
        if nl >= nr or nt >= nb:
            return b"", "[region 超出屏幕、裁出来是空的——核对 left,top,width,height(图像像素)]"
        img = img.crop((nl, nt, nr, nb))
        ox, oy = ox + nl, oy + nt
        region_abs = (ox, oy, ox + (nr - nl), oy + (nb - nt))

    # region 拼进指纹：同一画面但扫的范围不同，编号不一样，不能复用
    fp = region.encode("utf-8") + _fingerprint(img)
    global _cache_fp, _cache_ts, _cache_result
    if fp == _cache_fp and _cache_result is not None and time.monotonic() - _cache_ts < _CACHE_TTL_S:
        return _cache_result
    from desktop_pet.hands import ghost

    top_hwnd = ghost.foreground_hwnd()  # OCR/图标元素没有自己的 hwnd，统一挂到前台窗口上，给 ghost 点击用
    uia_els, uia_truncated = uia.interactive_elements()
    if region_abs is not None:
        uia_els = [e for e in uia_els if _inside(e["center_abs"], region_abs)]  # UIA 是整窗扫的，手动裁到 region 内
    bgr = np.array(img)[:, :, ::-1].copy()  # PIL 是 RGB，OCR/检测吃 OpenCV 的 BGR，反通道
    ocr_els = vision.ocr_boxes(bgr, ox, oy)

    # 三路优先级 UIA > OCR > 图标：UIA 最准先占坑，后两路落在已占框里的视为重复，跳过
    elements: list[dict] = []
    idx = 1
    taken = [e["rect_abs"] for e in uia_els]
    for e in uia_els:
        elements.append({
            "idx": idx, "source": "uia", "kind": e["kind"], "name": e["name"],
            "rect_abs": e["rect_abs"], "center_abs": e["center_abs"],
            "ctrl": e["ctrl"], "invokable": e["invokable"],
            "hwnd": uia.native_hwnd(e["ctrl"]) or top_hwnd,
        })
        idx += 1
    for o in ocr_els:
        if any(_inside(o["center_abs"], rect) for rect in taken):
            continue
        taken.append(o["rect_abs"])
        elements.append({
            "idx": idx, "source": "ocr", "kind": "text", "name": o["text"],
            "rect_abs": o["rect_abs"], "center_abs": o["center_abs"],
            "ctrl": None, "invokable": False, "hwnd": top_hwnd,
        })
        idx += 1
    # 第三路：视觉元素检测器(可选 GUI 增强)。UIA 在自绘/游戏窗口失效时，它补出"可点区域"。
    # 模型没启用时 detect.detect 返回 []，这里就是空操作。与 UIA/OCR 去重(已覆盖的不重复标)。
    for (l, t, r, b) in detect.detect(img):
        center_abs = ((l + r) // 2 + ox, (t + b) // 2 + oy)
        if any(_inside(center_abs, rect) for rect in taken):
            continue
        rect_abs = (l + ox, t + oy, r + ox, b + oy)
        taken.append(rect_abs)
        elements.append({
            "idx": idx, "source": "icon", "kind": "icon",
            "name": _label_for_icon(rect_abs, ocr_els),
            "rect_abs": rect_abs, "center_abs": center_abs,
            "ctrl": None, "invokable": False, "hwnd": top_hwnd,
        })
        idx += 1

    _LAST[:] = elements
    annotated = _annotate(img, elements, ox, oy)
    jpeg, _w, _h = capture._encode(annotated)

    detector_on = detect.available()
    if not elements:
        msg = "(no actionable elements detected — try a screenshot, or this may be a custom-drawn / game surface"
        if not detector_on:
            msg += "; the visual element detector is OFF — turning on 'GUI enhancement' in Control Panel > About lets me find clickable spots on custom-drawn / game / Qt windows"
        _cache_fp, _cache_ts, _cache_result = fp, time.monotonic(), (jpeg, msg + ")")
        return _cache_result
    _tags = {"uia": "·ctrl", "ocr": "·text", "icon": "·icon"}
    # 统计重名：多个"确定/删除"按钮长一样，光看名字点不对，下面标 ⚠ 逼模型按位置/上下文区分
    name_counts = Counter(el["name"].strip() for el in elements if el["name"].strip())
    lines = ["Numbered actionable elements on screen (call act_element with the number):"]
    for el in elements:
        tag = "▸invoke" if el["invokable"] else _tags.get(el.get("source", "ocr"), "")
        nm = (el["name"][:46] if el["name"] else "(icon)")
        nmkey = el["name"].strip()
        dup = f"  ⚠同名×{name_counts[nmkey]}" if nmkey and name_counts[nmkey] > 1 else ""
        lines.append(f'[{el["idx"]}] {el["kind"]} 「{nm}」 {tag}{dup}')
    text = "\n".join(lines)
    if any(c > 1 for c in name_counts.values()):
        text += ("\n(⚠ marked elements SHARE a name — pick by on-screen position / surrounding context. "
                 "If you still can't tell which is the right one, ASK the user instead of guessing — don't risk the wrong target.)")
    if uia_truncated:
        text += ("\n(note: the control scan hit its limit — this window has MORE controls than listed; "
                 "missing from the list ≠ not on screen. Focus/scroll to the area you need and re-run screen_elements)")
    if not detector_on and not any(e.get("source") == "uia" for e in elements):
        text += ("\n(only text/OCR detected here — the visual element detector is OFF; on custom-drawn "
                 "windows, enabling 'GUI enhancement' in Control Panel > About would let me see icon buttons too)")
    _cache_fp, _cache_ts, _cache_result = fp, time.monotonic(), (jpeg, text)
    return _cache_result


def act_element(index: int, action: str = "click", text: str = "", mode: str = "auto") -> str:
    """对 screen_elements 编过号的元素执行操作(click/double/right/type)。
    mode：auto 先试无光标(UIA invoke / ghost 后台点)，real 直接动真鼠标，ghost 只走后台、失败不降级。
    点完截图比对自动验证有没有生效，没生效会提示重试或换 real。"""
    from desktop_pet.hands import ghost, keyboard, mouse

    el = next((e for e in _LAST if e["idx"] == index), None)
    if el is None:
        return f"(no element numbered {index}; call screen_elements again to refresh the numbers)"
    name = el["name"][:30] or el["kind"]
    ax, ay = el["center_abs"]
    action = (action or "click").lower()
    mode = (mode or "auto").lower()
    oob = (f"([{index}] 「{name}」 的坐标 ({ax}, {ay}) 落在屏幕外，没点——"
           "元素编号可能已过期，重新 screen_elements 取最新编号再来)")

    if action == "type":
        # 优先走 UIA set_value：直接改控件值，不抢焦点不动光标；real 模式跳过它强制真实键入
        if mode != "real" and el["ctrl"] is not None and uia.set_value(el["ctrl"], text):
            return f'typed into [{index}] 「{name}」 via accessibility (replaced old value, no cursor)'
        if mode == "ghost":  # ghost 只认 UIA value pattern，没有就不降级到真键盘，直接报错
            return (f"[couldn't type into [{index}] 「{name}」 in ghost mode — it has no accessibility "
                    "value pattern; only standard input boxes support background typing. "
                    "Retry with mode=real (will move the user's mouse/focus)]")
        if not mouse.click_screen(ax, ay):
            return oob
        keyboard.press_keys("ctrl+a")
        keyboard.type_text(text)
        return f'clicked [{index}] 「{name}」, cleared old text, and typed'

    kind = "double" if action == "double" else ("right" if action == "right" else "click")

    before = _verify_snapshot()  # 动手前先存基准帧，下面比对用
    outcome = ""
    cursorless = False  # 走的是无光标路径(UIA/ghost)——没生效时提示重试 real 才有意义

    if mode != "real":
        # 无光标点击：UIA invoke(最干净) → ghost 后台投递消息(不动用户鼠标) → 都不行才落到下面真实点击
        if action in ("click", "invoke") and el["ctrl"] is not None and uia.invoke(el["ctrl"]):
            outcome = f'invoked [{index}] {el["kind"]} 「{name}」 via accessibility (no cursor moved)'
            cursorless = True
        elif ghost.bg_click(el.get("hwnd", 0), ax, ay, kind):
            outcome = f'posted a ghost {kind} to [{index}] 「{name}」 @({ax}, {ay}) — the user\'s mouse was NOT moved'
            cursorless = True
        elif mode == "ghost":  # 显式 ghost 模式不许降级到真鼠标，直接告诉调用方失败原因
            return (f"[ghost {kind} on [{index}] 「{name}」 failed (window gone/minimized/elevated, "
                    "or the point is outside its client area). Restore the window or retry with mode=real]")

    if not outcome:
        if not mouse.click_screen(ax, ay, kind):
            return oob
        outcome = f'{kind}-clicked [{index}] 「{name}」 @({ax}, {ay})'

    if before is None:
        return outcome + " (couldn't auto-verify — re-run screen_elements to confirm it actually worked)."
    time.sleep(_VERIFY_SETTLE_S)  # 等窗口重绘完再截，太快截会误判"没变"
    changed = _verify_changed(before)
    if changed is True:
        return outcome + " ✓ verified: the screen changed — it took effect."
    if changed is False:
        if cursorless:
            return (outcome + " ⚠ but NOTHING visibly changed — this window likely ignored the synthetic "
                    "input. Retry with mode=real (moves the real mouse).")
        return (outcome + " ⚠ but NOTHING visibly changed — the target may be wrong/non-interactive or need a "
                "different action. Re-run screen_elements and check before telling the user it's done.")
    return outcome + " (couldn't auto-verify — re-run screen_elements to confirm it actually worked)."
