"""Server-owned expression profiles; never grant tools or change the outfit target."""
import re
from pathlib import Path
from typing import Literal

from .errors import StylistError

PersonaId = Literal["male_calm_v1", "female_warm_v1", "female_sweet_v1", "female_regal_v1",
                    "male_artistic_v1", "male_confident_v1"]
DEFAULT_PERSONA: PersonaId = "female_warm_v1"
_FILES = {
    "male_calm_v1": "companion-composed",
    "female_warm_v1": "companion-gentle",
    "female_sweet_v1": "companion-sweet",
    "female_regal_v1": "companion-regal",
    "male_artistic_v1": "companion-artistic",
    "male_confident_v1": "companion-confident",
}


def is_male_persona(persona_id):
    return persona_id in {"male_calm_v1", "male_artistic_v1", "male_confident_v1"}


def persona_instructions(persona_id=None):
    key = persona_id or DEFAULT_PERSONA
    if key not in _FILES:
        raise StylistError("unknown_persona", "这个助理风格暂不可用，请重新选择。", 422)
    root = Path(__file__).with_name("skills")
    skill = root.joinpath(_FILES[key], "SKILL.md").read_text()
    # Only server-owned, allowlisted files are instructions; omit discovery metadata.
    body = skill.split("---", 2)[2].strip()
    return root.joinpath("companion-contract.md").read_text() + "\n\n" + body


def persona_reply_focus(persona_id, message):
    """Make the selected skill's relevant guidance salient without scripting replies."""
    lines = persona_instructions(persona_id).splitlines()
    if re.search(r"心动|情话", message) and not re.search(r"(?:别|不要|不想).{0,5}(?:心动|情话)", message):
        return next((line for line in lines if line.startswith("轻度亲近时")), "")
    if re.search(r"互怼|吐槽我", message) and not re.search(r"(?:别|不要|不想).{0,5}(?:互怼|吐槽)", message):
        return next((line.partition("专业")[0] for line in lines if line.startswith("聊天方式：")), "")
    return ""


def unsupported_city_message(persona_id, city):
    copies = {
        "female_sweet_v1": f"{city}的天气这次没查到。换个城市选项再试一下吧。",
        "female_regal_v1": f"{city}的天气暂时查不到。先不把未知当作晴天，我们重新选城市。",
        "male_artistic_v1": f"{city}的天气这次还没消息。重新选一下城市，再看看。",
        "male_confident_v1": f"{city}的天气暂时查不到。先保留你的安排，重新选城市再查。",
    }
    if persona_id in copies:
        return copies[persona_id]
    if is_male_persona(persona_id):
        return f"{city}的天气，我暂时还查不到。"
    return f"{city}的天气，我这边暂时还查不到呢。"


def itinerary_weather_message(persona_id, city, reason):
    if reason == "weather_city_unsupported":
        return unsupported_city_message(persona_id, city)
    if reason == "city_needs_selection":
        return (f"{city}有同名地点，补一下省市会更准确。" if is_male_persona(persona_id) else
                f"{city}有同名的地方呢，补一下省市就好。")
    return f"{city}这一天的天气暂时没查到，先别按确定的温度准备。"


def weather_location_limit_message(persona_id):
    if is_male_persona(persona_id) or persona_id == "female_regal_v1":
        return "这次超过10个地区了。一次最多查10个，先选10个，其余的下一轮再查。"
    return "这次超过10个地区了，一次还看不了这么多。先挑10个，我们分开查就好。"


def technical_detail_message(persona_id):
    copies = {
        "female_sweet_v1": "这部分技术细节我不清楚，不能给你编个答案。",
        "female_regal_v1": "这部分技术细节没有可靠依据，我不作猜测。",
        "male_artistic_v1": "这部分技术细节我还不清楚，就不拿想象当答案了。",
        "male_confident_v1": "这部分技术细节我不清楚。不确定的事，不替你下结论。",
    }
    if persona_id in copies:
        return copies[persona_id]
    if is_male_persona(persona_id):
        return "这部分技术细节我不太清楚，就不乱说了。"
    return "这部分我不太懂呢，具体的技术细节就不乱猜啦。"


def service_notice(persona_id, kind):
    """Human-facing notices; diagnostic codes belong in server logs."""
    male = is_male_persona(persona_id) or persona_id == "female_regal_v1"
    messages = {
        "weather": ("这次天气暂时没查到，先不按确定的天气安排。", "这次天气暂时没查到呢，先不按确定的天气安排。"),
        "weather_past": ("这套搭配指定的是过去日期，当前预报不能查询那一天，也不能用今天的天气代替。",
                         "这套搭配指定的是过去日期，现在的预报查不到那一天呢，也不能拿今天的天气代替。"),
        "weather_date": ("这一天的天气暂时查不到，不能拿其他日期的预报代替。", "这一天的天气暂时还查不到呢，先别按确定的预报准备。"),
        "city_selection": ("还需要确认是哪个城市，补一下省市会更准确。", "还需要确认你说的是哪座城市，补一下省市就好。"),
        "city_missing": ("还不知道你在哪座城市，选好城市后才能结合当地天气。", "还不知道你在哪座城市呢，选好城市后就能看看当地天气。"),
        "saved_outfits": ("之前保存的搭配这次没取到，我先看看现有衣物。", "之前保存的搭配这次没取到呢，我先看看现有衣物。"),
        "inventory": ("这次衣橱暂时没取到，我先按已知条件给些文字建议。", "这次暂时没看到衣橱里的衣服呢，我先按已知条件给些文字建议。"),
        "catalog_search": ("衣橱之外的参考款这次还没能顺利查到，我先保留已找到的衣物。", "衣橱之外的参考款这次暂时没查顺利，我先把已找到的衣物留给你。"),
        "inventory_partial": ("衣橱里的衣服比较多，这次只看了其中一部分。", "衣橱里的衣服比较多呢，这次先看了其中一部分。"),
        "catalog_partial": ("这次只看了部分系统衣物，还不能算查遍整个衣橱。", "这次先看了部分系统衣物，还没有查遍整个衣橱呢。"),
        "replacement": ("这次查到的衣物里，没找到合适的不同单品，原搭配先保留。", "这次查到的衣物里，还没找到合适的不同单品呢，先保留原搭配。"),
        "replacement_failed": ("这次换款还没完成，原搭配先保留；其他候选还需要继续核对。", "这次还没换成新的呢，先保留原搭配，其他候选还需要再看看。"),
        "original_retained": ("原搭配仍保留，这次没有换成新的单品。", "原搭配还在，这次没有换成新的单品呢。"),
        "concept": ("这次先给文字参考，还没有组成新的搭配。", "这次先给你文字参考呢，还没有组成新的搭配。"),
    }
    overrides = {
        "female_sweet_v1": {
            "inventory": "这次没能打开衣橱，先按你说的条件整理文字建议。衣服还没查到，不能乱选。",
            "replacement": "这次找到的衣服里，还没有合适的另一件。先把原搭配留好。",
            "concept": "先给你一点文字灵感，这次还没有组成新的搭配。",
        },
        "female_regal_v1": {
            "inventory": "这次衣橱暂时没取到。先给有依据的文字建议，不勉强凑选款。",
            "replacement": "这次候选中没有合适的不同单品。原搭配保留，选款不必将就。",
            "concept": "这次先给文字参考，还没有组成新的搭配。",
        },
        "male_artistic_v1": {
            "inventory": "这次衣橱暂时没打开。先用已知条件聊聊穿法，选款等衣服信息回来再说。",
            "replacement": "这次没找到适合接替的单品，先让原搭配留在这里。",
            "concept": "先把穿法灵感给你，这次还没有组成新的搭配。",
        },
        "male_confident_v1": {
            "inventory": "这次衣橱暂时没取到。先按已知条件给文字建议，未知的衣物不替你乱选。",
            "replacement": "这次没有合适的不同单品。原搭配保留，不为换而换。",
            "concept": "这次是文字参考，新的搭配还没有组成。",
        },
    }
    return overrides.get(persona_id, {}).get(kind, messages[kind][0 if male else 1])


def memory_receipt(persona_id):
    return {
        "female_sweet_v1": "穿搭喜好收进「我们的手记」啦，之后选衣服就有依据了。你随时可以修改或删除。",
        "female_warm_v1": "这条穿搭信息已经记入「我们的手记」，你可以随时修改或删除。",
        "female_regal_v1": "穿搭偏好已记入「我们的手记」。取舍仍由你决定，随时可以改写或删除。",
        "male_artistic_v1": "这条穿搭线索已留在「我们的手记」里。以后选衣服可以接着它聊，随时可以改写或删除。",
        "male_calm_v1": "这条穿搭信息已保存到「我们的手记」，可以随时修改或删除。",
        "male_confident_v1": "穿搭偏好记好了。之后按这个方向选，想改或删都由你定。",
    }.get(persona_id, "这条穿搭信息已保存到「我们的手记」，可以随时修改或删除。")


def boundary_reply(persona_id):
    return {
        "female_sweet_v1": "好，接下来不这样叫你，按你喜欢的方式聊天。",
        "female_warm_v1": "好，我会停止这个称呼，我们正常聊。",
        "female_regal_v1": "好，不这样称呼你。你的感受优先。",
        "male_artistic_v1": "好，这个称呼收起来。我们按你舒服的节奏聊。",
        "male_calm_v1": "好，接下来不用这个称呼，正常说话。",
        "male_confident_v1": "好，到这里。接下来按你舒服的方式说话。",
    }.get(persona_id, "好，接下来不这样称呼你。")


def avatar_invitation(persona_id, intent, profile=None, *, has_outfit=False):
    short = profile and (profile.reply_detail == "简洁重点" or profile.conversation_style == "直接坦诚")
    male = is_male_persona(persona_id)
    if intent == "upload":
        return ("想上传照片创建试穿形象吗？点下方卡片选图，检查通过后再单独确认生成积分。" if short else
                "想把自己的模样带进试穿里吗？从下方卡片选一张形象照片。先预览、检查，再由你决定是否确认积分生成。" if male else
                "想为试穿准备一个自己的模样吗？点下面的卡片选一张形象照片，我们先预览、检查，生成积分会另行请你确认。")
    if intent == "tryon" and not has_outfit:
        return "我们先选一个试穿形象。当前还没有可合成的衣橱搭配，选好后再准备衣服；这一步不会开始生成或扣费。"
    if intent == "tryon":
        return ("先选试穿形象，确认本次积分后再合成。" if short else
                "先选一个形象，看看这套搭配穿在身上的样子。积分会单独写清楚，等你确认后再开始合成。" if male else
                "这套搭配的新模样，就从你选的形象开始吧。先选好，再看清本次积分，等你确认后我再开始合成。")
    copies = {
        "female_sweet_v1": "形象画廊在下面啦，挑一个喜欢的模样。只是看看、选选，不会开始扣费生成。",
        "female_warm_v1": "可用形象放在下面了，你可以慢慢选。选择不会自动生成或扣费。",
        "female_regal_v1": "下面是可选形象。看准喜欢的再定，选择不会触发生成或扣费。",
        "male_artistic_v1": "下面这些模样都可以预览，看看哪一个更合你的感觉。选择不会触发生成或扣费。",
        "male_calm_v1": "下方可以查看、选择已有形象。选择不会自动生成或扣费。",
        "male_confident_v1": "可选形象在下面，挑你看得顺眼的。先选，是否生成和使用积分稍后再确认。",
    }
    return ("下方可以查看和选择试穿形象。选择不会自动生成或扣费。" if short else
            copies.get(persona_id, copies["female_warm_v1"]))


def upload_invitation(persona_id, profile=None, *, unspecified=False):
    short = profile and (profile.reply_detail == "简洁重点" or profile.conversation_style == "直接坦诚")
    if unspecified:
        return ("这张照片是想把衣物收进衣橱，还是创建本人的试穿形象？先选一个用途就好。" if short else
                "可以。你想把照片里的衣物收进衣橱，还是用本人照片创建试穿形象？我们先选好用途。" if is_male_persona(persona_id) else
                "当然可以。你想把照片里的衣物收进衣橱，还是用本人照片创建试穿形象呢？先选好用途就好。")
    if short:
        return "想把衣物添加到自己的衣橱吗？点下方卡片选照片，预览并确认后才会上传。"
    if profile and profile.conversation_style == "轻松幽默":
        return "想让喜欢的单品在衣橱里报个到吗？点下方卡片选一张照片，等你预览、确认后，我再帮你抠图整理。"
    copies = {
        "female_sweet_v1": "想给这件喜欢的单品留个位置吗？点下方卡片选照片，等你预览并确认后，我再帮你整理入柜。",
        "female_regal_v1": "想把这件单品收进自己的衣橱吗？下方选图，预览并确认后，再开始上传整理。决定由你来。",
        "male_artistic_v1": "想让这件单品加入衣橱吗？从下方选照片，等你预览、确认，我们再把它整理好。",
        "male_confident_v1": "想把这件单品添进衣橱吗？下方选照片，你预览并确认后，我再开始整理。先选，是否上传由你定。",
    }
    if persona_id in copies:
        return copies[persona_id]
    return ("想把这件单品添进自己的衣橱吗？从下面选一张照片，等你预览并确认后，我再帮你抠图整理、收进衣橱。" if is_male_persona(persona_id) else
            "想把喜欢的单品收进自己的衣橱吗？点下面的卡片选一张照片，等你看好、确认后，我再帮你抠图整理，让它有自己的位置。")


def progress_message(persona_id, stage):
    male = is_male_persona(persona_id)
    messages = {
        "connecting": ("收到，正在连接服务。", "收到啦，正在连接服务。"),
        "understanding": ("我先理清这次的安排和要求。", "我先把这次的安排和喜好理清楚。"),
        "weather": ("正在核对天气信息，留意穿脱和出行需要。", "我看看天气信息，留意需要添减衣服的地方。"),
        "wardrobe": ("正在查看候选衣物，按你的要求筛选。", "我在候选衣物里挑选，先照顾你这次的要求。"),
        "styling": ("正在整理组合和穿法，尽量让你少费心。", "正在搭配颜色和层次，把具体穿法一起整理好。"),
        "checking": ("再核对一次要求和单品信息。", "最后再核对一下要求和单品信息。"),
    }
    overrides = {
        "female_sweet_v1": ["收到，我来理一理。", "把你提到的小细节先记准。", "看看天气，别漏掉需要添减衣服的地方。", "去候选衣物里找找合适的选择。", "把颜色和层次搭得有一点巧思。", "再看看有没有漏掉你的要求。"],
        "female_regal_v1": ["收到，开始整理。", "先明确这次最重要的条件。", "核对天气，再决定穿搭层次。", "从真实候选中挑出值得留下的单品。", "整理轮廓和重点，让搭配更明确。", "核对单品与要求，不为凑数将就。"],
        "male_artistic_v1": ["收到，看看这次怎么搭。", "先抓住你想要的感觉和条件。", "看看天气给这次出门出了什么题。", "在候选衣物里找找有意思的组合。", "让颜色和层次各有一点节奏。", "灵感之外，再把具体条件核对好。"],
        "male_confident_v1": ["收到，开始处理。", "先抓住重点，再给你选择。", "核对天气，未知的先不下结论。", "从真实衣物里挑，不勉强凑一套。", "把重点留下，组合整理清楚。", "最后核对一次，按你的要求来。"],
    }
    stages = ("connecting", "understanding", "weather", "wardrobe", "styling", "checking")
    if persona_id in overrides:
        return overrides[persona_id][stages.index(stage)]
    return messages[stage][0 if male else 1]


def outfit_feedback_receipt(persona_id, vote, can_reference=True):
    """Acknowledge only committed votes; never claim a permanent profile or training."""
    if vote is None:
        return "这次评价已经撤回。喜欢什么，随时都可以改主意。"
    if vote == "dislike":
        return {
            "male_calm_v1": "好，不勉强。哪一处不合心意，告诉我，我们一起调。",
            "male_artistic_v1": "这次的感觉还没对上。你说说哪里不喜欢，我陪你换个方向。",
            "male_confident_v1": "收到，不合心意就换方向。想改哪里，你来定。",
            "female_warm_v1": "没关系，不用勉强喜欢。哪一点不舒服，我们慢慢调。",
            "female_sweet_v1": "那就再找找感觉呀。你挑一处想改的，我陪你一起看。",
            "female_regal_v1": "你的喜欢最要紧。不合心意的地方，说给我听。",
        }.get(persona_id, "没关系，不用勉强喜欢。哪一点不舒服，我们慢慢调。")
    if not can_reference:
        return "这份喜欢收到了。评价留在这套搭配里，你也随时可以改主意。"
    return {
        "male_calm_v1": "这份喜欢收到了。下次选款，我会多留意这样的风格。",
        "male_artistic_v1": "原来这样的风格，会让你心动。下次挑衣服，我会多留意一点。",
        "male_confident_v1": "好，这个方向收到了。下次搭配，我会多考虑这样的风格。",
        "female_warm_v1": "你喜欢就好。下次挑衣服，我会多照顾一点这样的风格。",
        "female_sweet_v1": "找到一点心动啦。下次搭配，我会多看看这样的风格。",
        "female_regal_v1": "这份喜欢，值得留意。下次选款，我会多考虑这样的风格。",
    }.get(persona_id, "你喜欢就好。下次挑衣服，我会多照顾一点这样的风格。")
