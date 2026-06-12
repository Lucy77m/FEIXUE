# author: bdth
# email: 2074055628@qq.com
# 小品活动定义表 道具名 阶段时长 气泡字 还有几个特殊活动的身体位姿函数

from __future__ import annotations

import math

from desktop_pet.pet.behaviors.easing import ease_in, ease_out, ease_out_back


_ACTIVITIES = {
    "coffee": ("coffee", 0.0, "puff_up", [
        ("pour", 3.2, "～"),
        ("lift", 1.2, ""),
        ("sip", 4.5, "～"),
    ]),
    "fish": ("fishing", 0.35, "jump_spin", [
        ("cast", 2.0, ""),
        ("wait", 6.5, "～"),
        ("bite", 1.0, "!"),
        ("reel", 1.8, ""),
        ("catch", 2.4, "★"),
    ]),
    "sleuth": ("sherlock", 0.5, "celebrate", [
        ("scan", 5.5, "?"),
        ("closer", 3.0, "?"),
        ("aha", 2.0, "!"),
    ]),
    "read": ("book", 0.0, "nod", [
        ("open", 1.2, ""),
        ("read", 7.0, ""),
        ("good", 2.0, "!"),
    ]),
    "music": ("headphones", 0.0, "happy_wiggle", [
        ("on", 1.2, "♪"),
        ("vibe", 8.0, "♫"),
    ]),
    "game": ("gaming", 0.0, "cheer", [
        ("play", 7.0, "✦"),
        ("tense", 2.0, "!"),
        ("win", 1.5, "★"),
    ]),
    "stars": ("telescope", 0.6, "puff_up", [
        ("aim", 2.0, ""),
        ("gaze", 6.5, "★"),
        ("wow", 2.0, "✦"),
    ]),
    "void": ("void", 0.5, "puff_up", [
        ("notice", 3.0, "?"),
        ("crack", 4.0, "…"),
        ("peer", 4.5, "·"),
        ("brace", 2.0, "!"),
        ("leap", 1.4, "✦"),
        ("gone", 3.0, ""),
        ("return", 2.2, "★"),
        ("seal", 3.5, "～"),
    ]),
    "clone": ("clone", 0.0, "happy_wiggle", [
        ("focus", 3.0, "…"),
        ("split", 2.0, "!"),
        ("mirror", 6.0, "♪"),
        ("swap", 4.5, "✦"),
        ("merge", 2.0, "✦"),
    ]),
    "meteor": ("meteor", -0.3, "cheer", [
        ("spot", 3.0, "?"),
        ("fall", 5.0, "✦"),
        ("scramble", 3.0, "!"),
        ("catch", 1.5, "★"),
        ("cradle", 3.0, "♥"),
        ("release", 2.5, "～"),
    ]),
    "sprout": ("sprout", 0.3, "happy_wiggle", [
        ("dig", 3.0, ""),
        ("plant", 2.5, "·"),
        ("water", 4.0, "～"),
        ("wait", 6.0, "…"),
        ("sprout", 4.0, "✦"),
        ("bloom", 3.5, "★"),
        ("sniff", 3.0, "♥"),
    ]),
    "yarn": ("yarn", 0.3, "happy_wiggle", [
        ("eye", 2.2, "?"),
        ("bat", 5.5, "!"),
        ("chase", 4.0, "✦"),
        ("tangle", 3.5, "～"),
        ("rest", 2.5, "♥"),
    ]),
    "bubbles": ("bubbles", 0.0, "happy_wiggle", [
        ("dip", 1.8, ""),
        ("blow", 2.6, "～"),
        ("watch", 4.5, "✦"),
        ("pop", 1.6, "!"),
    ]),
    "balloon": ("balloon", 0.0, "jump_spin", [
        ("grab", 1.6, ""),
        ("bob", 5.0, "～"),
        ("float", 3.0, "♥"),
    ]),
    "icecream": ("icecream", 0.0, "puff_up", [
        ("hold", 1.6, ""),
        ("lick", 5.5, "～"),
        ("melt", 2.6, "～"),
    ]),
    "paperplane": ("paperplane", 0.0, "celebrate", [
        ("fold", 2.2, ""),
        ("throw", 1.0, "!"),
        ("glide", 5.5, "～"),
    ]),
    "kite": ("kite", 0.0, "jump_spin", [
        ("run", 3.0, "～"),
        ("fly", 6.0, "✦"),
    ]),
    "camera": ("camera", 0.0, "celebrate", [
        ("aim", 3.0, "?"),
        ("flash", 0.8, "!"),
        ("aim", 2.0, "♥"),
    ]),
    "bubbletea": ("bubbletea", 0.0, "happy_wiggle", [
        ("hold", 1.6, ""),
        ("sip", 5.5, "～"),
    ]),
    "tanghulu": ("tanghulu", 0.0, "puff_up", [
        ("hold", 1.6, ""),
        ("bite", 5.0, "～"),
    ]),
    "dandelion": ("dandelion", 0.0, "happy_wiggle", [
        ("hold", 1.8, ""),
        ("blow", 2.2, "～"),
        ("watch", 4.0, "✦"),
    ]),
    "guitar": ("guitar", 0.0, "happy_wiggle", [
        ("tune", 1.6, "?"),
        ("strum", 6.0, "✦"),
    ]),
    "watermelon": ("watermelon", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("bite", 5.0, "～"),
    ]),
    "fireworks": ("fireworks", 0.0, "celebrate", [
        ("launch", 2.0, "～"),
        ("burst", 5.0, "✦"),
    ]),
    "yoyo": ("yoyo", 0.0, "jump_spin", [
        ("throw", 1.6, ""),
        ("sleep", 3.5, "✦"),
        ("back", 1.4, "!"),
    ]),
    "painting": ("painting", 0.0, "celebrate", [
        ("setup", 1.6, ""),
        ("paint", 6.0, "✦"),
    ]),
    "watering": ("watering", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("pour", 3.5, "～"),
        ("grow", 2.5, "✦"),
    ]),
    "blocks": ("blocks", 0.0, "celebrate", [
        ("stack", 6.0, "✦"),
        ("done", 1.5, "!"),
    ]),
    "lollipop": ("lollipop", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("lick", 6.0, "～"),
    ]),
    "popcorn": ("popcorn", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("toss", 5.0, "～"),
    ]),
    "pinwheel": ("pinwheel", 0.0, "jump_spin", [
        ("hold", 1.4, ""),
        ("spin", 5.5, "✦"),
    ]),
    "donut": ("donut", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("munch", 5.0, "～"),
    ]),
    "soda": ("soda", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("sip", 5.5, "～"),
    ]),
    "corn": ("corn", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("bite", 5.0, "～"),
    ]),
    "sushi": ("sushi", 0.0, "happy_wiggle", [
        ("pick", 2.0, "?"),
        ("eat", 3.0, "～"),
    ]),
    "rubik": ("rubik", 0.0, "celebrate", [
        ("hold", 1.4, ""),
        ("turn", 6.0, "?"),
    ]),
    "magic": ("magic", 0.0, "celebrate", [
        ("wave", 2.5, "～"),
        ("poof", 2.0, "✦"),
    ]),
    "knitting": ("knitting", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("knit", 6.0, "～"),
    ]),
    "phone": ("phone", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("tap", 6.0, "♥"),
    ]),
    "harmonica": ("harmonica", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("play", 6.0, "～"),
    ]),
    "popsicle": ("popsicle", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("bite", 5.0, "～"),
    ]),
    "butterfly": ("butterfly", 0.0, "jump_spin", [
        ("spot", 2.0, "!"),
        ("chase", 5.0, "✦"),
    ]),
    "fishmoon": ("fishmoon", 0.0, "happy_wiggle", [
        ("cast", 2.0, "～"),
        ("wait", 5.0, "✦"),
    ]),
    "ringtoss": ("ringtoss", 0.0, "celebrate", [
        ("toss", 6.0, "✦"),
        ("done", 1.5, "!"),
    ]),
    "lantern": ("lantern", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("light", 6.0, "✦"),
    ]),
    "cottoncandy": ("cottoncandy", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("eat", 5.5, "～"),
    ]),
    "burger": ("burger", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("munch", 5.0, "～"),
    ]),
    "noodles": ("noodles", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("slurp", 6.0, "～"),
    ]),
    "tea": ("tea", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("sip", 6.0, "～"),
    ]),
    "marshmallow": ("marshmallow", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("roast", 5.5, "✦"),
    ]),
    "calligraphy": ("calligraphy", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("write", 6.0, "✦"),
    ]),
    "darts": ("darts", 0.0, "celebrate", [
        ("aim", 2.0, "?"),
        ("throw", 4.0, "!"),
    ]),
    "paperboat": ("paperboat", 0.0, "happy_wiggle", [
        ("set", 1.6, ""),
        ("float", 6.0, "～"),
    ]),
    "pizza": ("pizza", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("munch", 5.0, "～"),
    ]),
    "spintop": ("spintop", 0.0, "jump_spin", [
        ("hold", 1.4, ""),
        ("spin", 6.0, "✦"),
    ]),
    "crane": ("crane", 0.0, "happy_wiggle", [
        ("fold", 6.0, "～"),
        ("done", 1.5, "✦"),
    ]),
    "piano": ("piano", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("play", 6.0, "✦"),
    ]),
    "piggybank": ("piggybank", 0.0, "celebrate", [
        ("hold", 1.4, ""),
        ("save", 5.0, "✦"),
    ]),
    "crystalball": ("crystalball", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("gaze", 6.0, "✦"),
    ]),
    "cards": ("cards", 0.0, "celebrate", [
        ("hold", 1.4, ""),
        ("fan", 5.5, "?"),
    ]),
    "matryoshka": ("matryoshka", 0.0, "happy_wiggle", [
        ("hold", 1.6, ""),
        ("open", 4.0, "✦"),
    ]),
    "sheep": ("sheep", 0.0, "happy_wiggle", [
        ("count", 6.0, "～"),
    ]),
    "bouquet": ("bouquet", 0.0, "happy_wiggle", [
        ("hold", 2.0, ""),
        ("sniff", 5.0, "♥"),
    ]),
    "sweetpotato": ("sweetpotato", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("eat", 5.0, "～"),
    ]),
    "trumpet": ("trumpet", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("play", 6.0, "✦"),
    ]),
    "frisbee": ("frisbee", 0.0, "jump_spin", [
        ("throw", 2.0, "!"),
        ("watch", 4.0, "✦"),
    ]),
    "cupcake": ("cupcake", 0.0, "celebrate", [
        ("hold", 2.0, ""),
        ("blow", 3.0, "✦"),
    ]),
    "snowglobe": ("snowglobe", 0.0, "happy_wiggle", [
        ("hold", 1.6, ""),
        ("shake", 5.5, "✦"),
    ]),
}
_ACTIVITY_GAP = (150.0, 300.0)
_TRAVEL = "__travel__"


def _void_body(stage, p, t, bw, bh):
    """虚空一跃的身体位姿"""
    if stage == "notice":
        e = ease_out(p)
        return 0.10 * bw * e, 0.0, 6.0 * e, 1.0, 1.0
    if stage == "peer":
        wob = math.sin(t * 4.0) * 3.0
        return 0.20 * bw, 0.05 * bh, 12.0 + wob, 1.03, 0.97
    if stage == "brace":
        e = ease_in(p)
        return 0.18 * bw, 0.10 * bh * e, 8.0, 1.0 + 0.20 * e, 1.0 - 0.28 * e
    if stage == "leap":
        if p < 0.3:
            e = ease_out(p / 0.3)
            return 0.18 * bw, -0.05 * bh * e, 8.0, 1.0 - 0.12 * e, 1.0 + 0.18 * e
        e = ease_in((p - 0.3) / 0.7)
        ox = (0.18 + 0.55 * e) * bw
        oy = (-0.55 * math.sin(e * math.pi) + 0.30 * e) * bh
        s = max(0.06, 1.0 - 0.92 * e)
        return ox, oy, 8.0 + 360.0 * e, s, s
    if stage == "gone":
        return 0.73 * bw, 0.30 * bh, 0.0, 0.001, 0.001
    if stage == "return":
        e = ease_out_back(p)
        ox = (0.73 - 0.73 * e) * bw
        oy = (0.30 - 0.30 * e) * bh - math.sin(p * math.pi) * 0.12 * bh
        s = max(0.06, 0.08 + 0.92 * e)
        return ox, oy, 0.0, s, s
    if stage == "seal":
        return 0.10 * bw * (1.0 - ease_out(p)), 0.0, 4.0 * (1.0 - p), 1.0, 1.0
    return 0.0, 0.0, 0.0, 1.0, 1.0


def _clone_body(stage, p, t, bw, bh):
    """影分身的身体位姿"""
    if stage == "focus":
        e = ease_in(p)
        return 0.0, 0.0, math.sin(t * 20.0) * 2.0 * e, 1.0 + 0.04 * e, 1.0 - 0.06 * e
    if stage == "split":
        e = ease_out(p)
        return -0.16 * bw * e, 0.0, -6.0 * e, 1.0 + 0.10 * math.sin(p * math.pi), 1.0
    if stage == "mirror":
        return math.sin(t * 3.0) * 0.18 * bw, 0.0, math.sin(t * 3.0) * 8.0, 1.0, 1.0
    if stage == "swap":
        return math.cos(t * 1.8) * 0.22 * bw, math.sin(t * 1.8) * 0.10 * bh, 0.0, 1.0, 1.0
    if stage == "merge":
        e = ease_out(p)
        ox = -0.16 * bw * (1.0 - e)
        k = ease_in(max(0.0, (p - 0.7) / 0.3))
        return ox, 0.0, 0.0, 1.0 + 0.18 * k, 1.0 - 0.14 * k
    return 0.0, 0.0, 0.0, 1.0, 1.0


def _meteor_body(stage, p, t, bw, bh):
    """接流星的身体位姿"""
    if stage == "spot":
        e = ease_out(p)
        return -0.05 * bw * e, -0.04 * bh * e, -4.0 * e, 1.0, 1.0
    if stage == "fall":
        return math.sin(t * 2.2) * 0.12 * bw, -0.02 * bh, 0.0, 1.0, 1.0
    if stage == "scramble":
        hop = -abs(math.sin(t * 8.0)) * 0.05 * bh
        return 0.20 * bw * ease_out(p), hop, 0.0, 1.0, 1.0 + 0.04 * abs(math.sin(t * 8.0))
    if stage == "catch":
        up = math.sin(p * math.pi)
        return 0.15 * bw, -0.12 * bh * up, 0.0, 1.0 - 0.08 * up, 1.0 + 0.20 * up
    if stage == "cradle":
        return 0.10 * bw, math.sin(t * 2.0) * 0.03 * bh, 0.0, 1.0, 1.0
    if stage == "release":
        e = ease_out(p)
        return 0.10 * bw * (1.0 - e), -0.04 * bh * math.sin(p * math.pi), 0.0, 1.0, 1.0
    return 0.0, 0.0, 0.0, 1.0, 1.0


def _sprout_body(stage, p, t, bw, bh):
    """种花的身体位姿"""
    if stage == "dig":
        e = ease_out(p)
        return 0.0, 0.06 * bh * e, 6.0 * e, 1.0, 1.0
    if stage in ("plant", "water"):
        sway = math.sin(t * 4.0) * 0.05 * bw if stage == "water" else 0.0
        return sway, 0.06 * bh, 6.0, 1.0, 1.0
    if stage == "wait":
        return math.sin(t * 0.8) * 0.03 * bw, 0.0, math.sin(t * 0.8) * 2.0, 1.0, 1.0
    if stage == "sprout":
        return 0.0, 0.03 * bh * ease_out(p), 0.0, 1.0, 1.0
    if stage == "bloom":
        up = math.sin(p * math.pi)
        return 0.0, -0.04 * bh * up, 0.0, 1.0, 1.0 + 0.05 * up
    if stage == "sniff":
        e = ease_out(p)
        return 0.12 * bw * e, 0.05 * bh * e, 8.0 * e, 1.0, 1.0
    return 0.0, 0.0, 0.0, 1.0, 1.0


def _yarn_body(stage, p, t, bw, bh):
    """玩毛线球的身体位姿"""
    if stage == "eye":
        e = ease_out(p)
        # 歪头盯球 屁股微撅蓄势
        return 0.05 * bw * e, 0.03 * bh * e, 9.0 * e, 1.0 + 0.04 * e, 1.0 - 0.05 * e
    if stage == "bat":
        sw = math.sin(p * math.pi * 4)  # 跟球的节奏扑
        pounce = abs(math.sin(p * math.pi * 8))
        return sw * bw * 0.13, 0.05 * bh + pounce * bh * 0.025, sw * 10, 1 + 0.05 * pounce, 1 - 0.07 * pounce
    if stage == "chase":
        sw = math.sin(p * math.pi * 2)
        return sw * bw * 0.22, 0.04 * bh, sw * 14, 1.02, 0.96
    if stage == "tangle":
        wig = math.sin(t * 7) * ease_out(p)
        return wig * bw * 0.03, 0.05 * bh, wig * 6, 1.0 + 0.03 * abs(wig), 1.0 - 0.04 * abs(wig)
    if stage == "rest":
        e = ease_out(p)
        return 0.05 * bw, 0.08 * bh * e, 4.0, 1.0 - 0.03 * e, 1.0 - 0.04 * e
    return 0.0, 0.0, 0.0, 1.0, 1.0


_ACTIVITY_BODY = {
    "void": _void_body,
    "clone": _clone_body,
    "meteor": _meteor_body,
    "sprout": _sprout_body,
    "yarn": _yarn_body,
}
