"""Server-owned expression profiles; never grant tools or change the outfit target."""
from pathlib import Path
from typing import Literal

from .errors import StylistError

PersonaId = Literal["male_calm_v1", "female_warm_v1"]
DEFAULT_PERSONA: PersonaId = "female_warm_v1"
_FILES = {
    "male_calm_v1": "persona_male_v1.md",
    "female_warm_v1": "persona_female_v1.md",
}


def persona_instructions(persona_id=None):
    key = persona_id or DEFAULT_PERSONA
    if key not in _FILES:
        raise StylistError("unknown_persona", "这个助理风格暂不可用，请重新选择。", 422)
    return Path(__file__).with_name("prompts").joinpath(_FILES[key]).read_text()


def unsupported_city_message(persona_id, city):
    if persona_id == "male_calm_v1":
        return f"{city}的天气，我暂时还查不到。"
    return f"{city}的天气，我这边暂时还查不到呢。"


def itinerary_weather_message(persona_id, city, reason):
    if reason == "weather_city_unsupported":
        return unsupported_city_message(persona_id, city)
    if reason == "city_needs_selection":
        return (f"{city}有同名地点，补一下省市会更准确。" if persona_id == "male_calm_v1" else
                f"{city}有同名的地方呢，补一下省市就好。")
    return f"{city}这一天的天气暂时没查到，先别按确定的温度准备。"


def weather_location_limit_message(persona_id):
    if persona_id == "male_calm_v1":
        return "这次超过10个地区了。一次最多查10个，先选10个，其余的下一轮再查。"
    return "这次超过10个地区了，一次还看不了这么多。先挑10个，我们分开查就好。"


def technical_detail_message(persona_id):
    if persona_id == "male_calm_v1":
        return "这部分技术细节我不太清楚，就不乱说了。"
    return "这部分我不太懂呢，具体的技术细节就不乱猜啦。"


def service_notice(persona_id, kind):
    """Human-facing notices; diagnostic codes belong in server logs."""
    male = persona_id == "male_calm_v1"
    messages = {
        "weather": ("这次天气暂时没查到，先不按确定的天气安排。", "这次天气暂时没查到呢，先不按确定的天气安排。"),
        "weather_date": ("这一天的天气暂时查不到，不能拿其他日期的预报代替。", "这一天的天气暂时还查不到呢，先别按确定的预报准备。"),
        "city_selection": ("还需要确认是哪个城市，补一下省市会更准确。", "还需要确认你说的是哪座城市，补一下省市就好。"),
        "city_missing": ("还不知道你在哪座城市，选好城市后才能结合当地天气。", "还不知道你在哪座城市呢，选好城市后就能看看当地天气。"),
        "saved_outfits": ("之前保存的搭配这次没取到，我先看看现有衣物。", "之前保存的搭配这次没取到呢，我先看看现有衣物。"),
        "inventory": ("这次衣橱暂时没取到，我先按已知条件给些文字建议。", "这次暂时没看到衣橱里的衣服呢，我先按已知条件给些文字建议。"),
        "catalog_search": ("我先看看这次找到的系统衣物。", "我先从这次找到的系统衣物里看看。"),
        "inventory_partial": ("衣橱里的衣服比较多，这次只看了其中一部分。", "衣橱里的衣服比较多呢，这次先看了其中一部分。"),
        "catalog_partial": ("这次只看了部分系统衣物，还不能算查遍整个衣橱。", "这次先看了部分系统衣物，还没有查遍整个衣橱呢。"),
        "replacement": ("这次查到的衣物里，没找到合适的不同单品，原搭配先保留。", "这次查到的衣物里，还没找到合适的不同单品呢，先保留原搭配。"),
        "replacement_failed": ("这次换款还没完成，原搭配先保留；其他候选还需要继续核对。", "这次还没换成新的呢，先保留原搭配，其他候选还需要再看看。"),
        "original_retained": ("原搭配仍保留，这次没有换成新的单品。", "原搭配还在，这次没有换成新的单品呢。"),
        "concept": ("这次先给文字参考，还没有组成新的搭配。", "这次先给你文字参考呢，还没有组成新的搭配。"),
    }
    return messages[kind][0 if male else 1]


def progress_message(persona_id, stage):
    male = persona_id == "male_calm_v1"
    messages = {
        "connecting": ("收到，正在连接服务。", "收到啦，正在连接服务。"),
        "understanding": ("我先理清这次的安排和要求。", "我先把这次的安排和喜好理清楚。"),
        "weather": ("正在核对天气信息，留意穿脱和出行需要。", "我看看天气信息，留意需要添减衣服的地方。"),
        "wardrobe": ("正在查看候选衣物，按你的要求筛选。", "我在候选衣物里挑选，先照顾你这次的要求。"),
        "styling": ("正在整理组合和穿法，尽量让你少费心。", "正在搭配颜色和层次，把具体穿法一起整理好。"),
        "checking": ("再核对一次要求和单品信息。", "最后再核对一下要求和单品信息。"),
    }
    return messages[stage][0 if male else 1]
