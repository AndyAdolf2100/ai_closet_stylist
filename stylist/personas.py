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
        return f"还不确定你说的{city}是哪里，补一下省市会更准确。"
    return f"{city}这一天的天气暂时没查到，先别按确定的温度准备。"


def weather_location_limit_message(persona_id):
    if persona_id == "male_calm_v1":
        return "这次超过10个地区了。一次最多查10个，先选10个，其余的下一轮再查。"
    return "这次超过10个地区了，一次还看不了这么多。先挑10个，我们分开查就好。"


def technical_detail_message(persona_id):
    if persona_id == "male_calm_v1":
        return "这部分技术细节我不太清楚，就不乱说了。"
    return "这部分我不太懂呢，具体的技术细节就不乱猜啦。"


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
