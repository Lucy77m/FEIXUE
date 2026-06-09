# author: bdth
# email: 2074055628@qq.com
# 把屏幕上可操作元素编号、标注并提供按编号点击/输入的能力

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from desktop_pet.eyes import capture, detect, uia

_LAST: list[dict] = []
_COLORS = {"uia": (80, 230, 140), "ocr": (90, 190, 255), "icon": (255, 180, 70)}
_LABEL_INK = (16, 16, 22)


def _inside(point: tuple[int, int], rect: tuple[int, int, int, int]) -> bool:
    x, y = point
    l, t, r, b = rect
    return l <= x <= r and t <= y <= b


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("segoeuib.ttf", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _annotate(img: Image.Image, elements: list[dict], ox: int, oy: int) -> Image.Image:
    canvas = img.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas, "RGBA")
    size = max(15, canvas.height // 55)
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


def screen_elements() -> tuple[bytes, str]:
    import numpy as np

    from desktop_pet.executor import vision

    img = capture.grab_active()
    ox, oy, _ow, _oh = capture.current_geom()
    uia_els = uia.interactive_elements()
    bgr = np.array(img)[:, :, ::-1].copy()
    ocr_els = vision.ocr_boxes(bgr, ox, oy)

    elements: list[dict] = []
    idx = 1
    taken = [e["rect_abs"] for e in uia_els]
    for e in uia_els:
        elements.append({
            "idx": idx, "source": "uia", "kind": e["kind"], "name": e["name"],
            "rect_abs": e["rect_abs"], "center_abs": e["center_abs"],
            "ctrl": e["ctrl"], "invokable": e["invokable"],
        })
        idx += 1
    for o in ocr_els:
        if any(_inside(o["center_abs"], rect) for rect in taken):
            continue
        taken.append(o["rect_abs"])
        elements.append({
            "idx": idx, "source": "ocr", "kind": "text", "name": o["text"],
            "rect_abs": o["rect_abs"], "center_abs": o["center_abs"],
            "ctrl": None, "invokable": False,
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
            "idx": idx, "source": "icon", "kind": "icon", "name": "",
            "rect_abs": rect_abs, "center_abs": center_abs,
            "ctrl": None, "invokable": False,
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
        return jpeg, msg + ")"
    _tags = {"uia": "·ctrl", "ocr": "·text", "icon": "·icon"}
    lines = ["Numbered actionable elements on screen (call act_element with the number):"]
    for el in elements:
        tag = "▸invoke" if el["invokable"] else _tags.get(el.get("source", "ocr"), "")
        nm = (el["name"][:46] if el["name"] else "(icon)")
        lines.append(f'[{el["idx"]}] {el["kind"]} 「{nm}」 {tag}')
    text = "\n".join(lines)
    if not detector_on and not any(e.get("source") == "uia" for e in elements):
        text += ("\n(only text/OCR detected here — the visual element detector is OFF; on custom-drawn "
                 "windows, enabling 'GUI enhancement' in Control Panel > About would let me see icon buttons too)")
    return jpeg, text


def act_element(index: int, action: str = "click", text: str = "") -> str:
    from desktop_pet.hands import keyboard, mouse

    el = next((e for e in _LAST if e["idx"] == index), None)
    if el is None:
        return f"(no element numbered {index}; call screen_elements again to refresh the numbers)"
    name = el["name"][:30] or el["kind"]
    ax, ay = el["center_abs"]
    action = (action or "click").lower()
    oob = (f"([{index}] 「{name}」 的坐标 ({ax}, {ay}) 落在屏幕外，没点——"
           "元素编号可能已过期，重新 screen_elements 取最新编号再来)")

    if action == "type":
        if el["ctrl"] is not None and uia.set_value(el["ctrl"], text):
            return f'typed into [{index}] 「{name}」 via accessibility (replaced old value, no cursor)'
        if not mouse.click_screen(ax, ay):
            return oob
        keyboard.press_keys("ctrl+a")
        keyboard.type_text(text)
        return f'clicked [{index}] 「{name}」, cleared old text, and typed'

    if action in ("click", "invoke") and el["ctrl"] is not None and el["invokable"]:
        if uia.invoke(el["ctrl"]):
            return f'invoked [{index}] {el["kind"]} 「{name}」 directly (no cursor moved)'

    kind = "double" if action == "double" else ("right" if action == "right" else "click")
    if not mouse.click_screen(ax, ay, kind):
        return oob
    return f'{kind}-clicked [{index}] 「{name}」 @({ax}, {ay})'
