"""Apply soft wardrobe style preferences after hard suitability checks."""
import re

from .models import Slot


def preferred_pool(pool, styles, frozen=()):
    if not styles:
        return pool, []
    frozen_keys = {p.key for p in frozen}
    garment_slots = {Slot.TOP, Slot.BOTTOM, Slot.DRESS, Slot.OUTER}
    def matches(p, wanted=styles):
        return any(label in style for label in p.styles for style in wanted)
    matching_slots = {p.slot for p in pool.values() if matches(p)}
    missing = [style for style in styles if not any(matches(p, [style]) for p in pool.values())]
    return {key: p for key, p in pool.items() if key in frozen_keys or p.slot not in garment_slots
            or p.slot not in matching_slots or matches(p)}, missing


def wardrobe_requested(message, history=()):
    """Guard the default for concrete clothing requests, retaining explicit opt-outs."""
    explicit_inventory = re.search(r"(?:用|查|从|恢复|输出).{0,6}(?:衣橱|衣柜)|实际(?:选款|衣服)", message)
    opt_out = re.compile(r"不(?:查|找|用|要|输出).{0,8}(?:衣橱|衣柜|商品)|只(?:讲|给|要|咨询|按口述)|讲原理|只重新说")
    if opt_out.search(message):
        return False
    if not explicit_inventory:
        for row in reversed(history):
            text = row.get("content", "") if row.get("role") == "user" else ""
            if text:
                if opt_out.search(text):
                    return False
                if re.search(r"(?:用|从|查).{0,6}(?:衣橱|衣柜)", text):
                    break
    return bool(explicit_inventory or re.search(r"怎么搭|怎么穿|搭一套|推荐.{0,6}(?:衣服|穿搭|搭配)|选.{0,6}(?:鞋|衣服)", message))
