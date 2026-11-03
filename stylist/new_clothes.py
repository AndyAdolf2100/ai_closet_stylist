"""Explicit permission for catalog exploration; legacy source values grant nothing."""
import json
import re


def direct_words(message):
    for opening, closing in [('「', '」'), ('“', '”'), ('"', '"'), ('【', '】')]:
        message = message.replace(opening + '邂逅新衣' + closing, '邂逅新衣')
    return re.sub(r'[“「『"].*?[”」』"]', '', message)


def personal_only(message):
    message = direct_words(message)
    return bool(re.search(r"(?:只|仅)(?:用|从|穿|选).{0,10}(?:我|自己|已有|现有|个人).{0,8}(?:衣|服)|关闭.{0,4}邂逅新衣|(?:不(?:要|用)?|别)(?:开启|打开|启用).{0,4}邂逅新衣|不要.{0,4}(?:新衣|系统衣橱|参考款)", message))


def explicit_new_clothes(message, model_intent=False, evidence=""):
    # Remove reported/quoted examples; a model assertion alone never grants access.
    text = direct_words(message)
    if personal_only(text) or re.search(r"只(?:讲|给|要|提供).{0,8}(?:文字|原理|口述)|不(?:查|找).{0,6}(?:商品|衣橱|衣柜)|只咨询", text):
        return False
    if re.search(r"举例|比如|例如|转述|(?:朋友|别人|她|他)说|不是.{0,6}(?:想|要)|不想|不要开启", text):
        return False
    outside = re.search(r"(?:衣橱|衣柜).{0,8}(?:没有|之外|以外)|(?:衣橱|衣柜)(?:里|里面|中)?(?:没有|之外|以外)|我(?:现在|目前|还|暂时)?没(?:有|买|拥有).{0,5}(?:衣|款)|系统衣橱|参考衣橱", text)
    request = re.search(r"(?:想|要|帮我|给我|试试|尝试|看看|推荐|搭|找|选|开启|打开)", text)
    explicit_switch = re.search(r"(?:开启|打开|启用|勾选).{0,4}邂逅新衣", text)
    directed = outside and request and (request.start() < outside.start() or "系统衣橱" in text or "参考衣橱" in text)
    semantic = (model_intent and evidence and evidence in text and request
                and re.search(r"未拥有|未入手|没入手|从没买|没买过|不在.{0,5}(?:衣橱|衣柜)", evidence))
    return bool(explicit_switch or directed or semantic)


def enabled(request, plan, previous=False):
    if personal_only(request.message):
        return False, False
    automatic = explicit_new_clothes(request.message, plan.new_clothes_intent, plan.new_clothes_evidence)
    selected = request.new_clothes if request.new_clothes is not None else previous
    return bool(selected or automatic), bool(automatic and not selected)


def invitation(persona):
    lines = {
        'female_sweet_v1': '已为你开启「邂逅新衣」。一起去衣橱之外，找找让你眼前一亮的搭配吧。',
        'female_warm_v1': '已为你开启「邂逅新衣」。我陪你看看衣橱之外的选择，慢慢找到喜欢的搭配。',
        'female_regal_v1': '已为你开启「邂逅新衣」。把选择放宽些，我来为你挑一套更出彩的搭配。',
        'male_artistic_v1': '已为你开启「邂逅新衣」。一起看看衣橱之外，今天会遇见怎样的新灵感。',
        'male_calm_v1': '已为你开启「邂逅新衣」。我会把衣橱之外的参考款也纳入选择，陪你找合适的新搭配。',
        'male_confident_v1': '已为你开启「邂逅新衣」。跟我看看新的选择，这次试点不一样的。',
    }
    return lines.get(persona, lines['male_calm_v1'])


def previous_enabled(state):
    for row in reversed(state.messages):
        if row.get("role") == "assistant":
            try:
                return bool(json.loads(row["content"]).get("new_clothes", False))
            except (ValueError, TypeError, AttributeError, KeyError):
                return False
    return False
