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


def wardrobe_allowed(message, history=()):
    """Only explicit text/principle requests opt out of personal wardrobe reads."""
    explicit_inventory = re.search(r"(?:用|查|从|恢复|输出).{0,6}(?:衣橱|衣柜)|实际(?:选款|衣服)", message)
    opt_out = re.compile(r"不(?:查|找|用|要|输出).{0,8}(?:衣橱|衣柜|商品)|只(?:讲|给|要|提供).{0,8}(?:文字|原理|口述)"
                         r"|只(?:咨询|按口述|记录|保存|记下)"
                         r"|(?:讲|聊|讨论).{0,6}(?:原理|原则)|不(?:用|要)?(?:搭配|推荐|选款)|只重新说")
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
    return True


def wardrobe_requested(message, history=(), *, clothing_preferences=False):
    """Guard all concrete clothing queries without requiring the word 'wardrobe'."""
    if not wardrobe_allowed(message, history):
        return False
    explicit_inventory = re.search(r"(?:用|查|从|恢复|输出).{0,6}(?:衣橱|衣柜)|实际(?:选款|衣服)", message)
    return bool(explicit_inventory or clothing_preferences or re.search(
        r"怎么搭|怎么穿|穿什么|配什么|搭一套|搭配一套|推荐一套|推荐.{0,12}(?:衣|穿搭|搭配|裙|裤|鞋|衫|帽|包|围巾|首饰|腰带)"
        r"|(?:给|来|要).{0,5}一套.{0,6}(?:穿搭|搭配|衣服)|(?:穿衣|穿搭|搭配).{0,6}(?:建议|推荐|方案)"
        r"|(?:选|挑|找|查|看看).{0,12}(?:衣服|衣物|穿搭|衬衫|短袖|长袖|外套|毛衣|卫衣|背心|马甲|西装|T恤|裙|裤|鞋|靴|帽|围巾|包|手套|袜|配饰|首饰|项链|腰带)"
        r"|(?:衬衫|短袖|长袖|外套|毛衣|裙|裤|鞋).{0,6}(?:怎么样|配|搭|推荐)|再来.{0,3}[件套双]", message))
