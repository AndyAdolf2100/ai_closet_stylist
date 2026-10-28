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
