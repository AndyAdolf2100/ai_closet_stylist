"""Controlled preference pairs: same message and inventory, distinct profile settings."""
from .companion_dialogues import profile
from .preference_coverage import EXPECTATIONS as COVERAGE_EXPECTATIONS
from .preference_coverage import PRODUCTS as COVERAGE_PRODUCTS
from .preference_coverage import SCENARIOS as COVERAGE_SCENARIOS

CHAT = "今天工作有点不顺，事情堆着不知道怎么开始，陪我聊聊。"
ADVICE = "只咨询穿法：白衬衫、灰色长裤、白色平底鞋，讲讲怎么穿得协调，不查衣橱和天气。"
OUTFIT = "从我的衣橱给我挑一套适合自己的日常搭配，不穿高跟鞋，不考虑天气。"


def settings(**kwargs):
    return {**profile(), **kwargs}


SCENARIOS = {
    "preference_tone_gentle": [("answer", CHAT, True)],
    "preference_tone_direct": [("answer", CHAT, True)],
    "preference_detail_short": [("answer", ADVICE, False)],
    "preference_detail_full": [("answer", ADVICE, False)],
    "preference_outfit_casual": [("answer", OUTFIT, False)],
    "preference_outfit_elegant": [("answer", OUTFIT, False)],
    "preference_priority": [
        ("explicit", "我的默认偏好先放一边，这次从我的衣橱选一套优雅风，不穿高跟鞋，不考虑天气。", False),
        ("friend", "这次给朋友搭配，她明确喜欢优雅，不要套我的喜好。从我的衣橱借一套，不穿高跟鞋，不考虑天气。", False),
    ],
    "preference_zodiac_outfit": [
        ("inspiration", OUTFIT, False),
        ("decline", "不用星座，按我喜欢的休闲风重新搭一套，不穿高跟鞋，不考虑天气。", False),
        ("friend", "给朋友借一套日常衣服，不要套用我的星座，不穿高跟鞋，不考虑天气。", False),
        ("chat", "今天有点累，陪我聊聊就好。", True),
    ],
    "preference_zodiac": [("answer", "我是天蝎座，你能确定我什么性格吗？", True)],
    "preference_update": [
        ("casual", OUTFIT, False),
        ("elegant", "我刚更新了穿搭偏好，重新从我的衣橱选一套，不穿高跟鞋，不考虑天气。", False),
        ("shoes", "只换另一双平底鞋，其余都保留，不穿高跟鞋，不考虑天气。", False),
    ],
}
EXPECTATIONS = {
    "preference_tone_gentle/answer": {"companion_profile": settings(conversation_style="温柔鼓励"),
        "comparison": "tone", "variant": "gentle", "review_focus": "先接住情绪，温柔但不空泛，保留当前男女基础人格。"},
    "preference_tone_direct/answer": {"companion_profile": settings(conversation_style="直接坦诚"),
        "comparison": "tone", "variant": "direct", "review_focus": "直接给出具体可行的建议，避免冗长安慰；不冷硬或命令。"},
    "preference_detail_short/answer": {"companion_profile": settings(reply_detail="简洁重点"),
        "comparison": "detail", "variant": "short", "review_focus": "直接给可执行要点，简洁但不漏掉用户要求。"},
    "preference_detail_full/answer": {"companion_profile": settings(reply_detail="细致解释"),
        "comparison": "detail", "variant": "full", "review_focus": "解释配色、穿法理由及替代穿法，不只是更多套话。"},
    "preference_outfit_casual/answer": {"companion_profile": settings(style_preferences=["休闲"], dressing_priorities=["方便走动"]),
        "comparison": "outfit", "variant": "casual", "selected_style": "休闲", "review_focus": "上衣和下装优先实际休闲衣物，鞋优先平底，解释方便活动的穿法但不保证个人体感。"},
    "preference_outfit_elegant/answer": {"companion_profile": settings(style_preferences=["优雅"], dressing_priorities=["方便走动"]),
        "comparison": "outfit", "variant": "elegant", "selected_style": "优雅", "review_focus": "上衣和下装优先实际优雅衣物，不能因为优雅偏好违反不穿高跟鞋。"},
    "preference_priority/explicit": {"companion_profile": settings(style_preferences=["休闲"]), "selected_style": "优雅", "review_focus": "本轮明确优雅覆盖已保存休闲偏好。"},
    "preference_priority/friend": {"companion_profile": settings(style_preferences=["休闲"]), "selected_style": "优雅", "review_focus": "给朋友搭配不套用本人休闲偏好。"},
    "preference_zodiac/answer": {"companion_profile": settings(zodiac="天蝎座"), "review_focus": "不能根据星座确定性格，不给用户贴神秘、控制欲等标签，不编造运势。"},
    "preference_update/casual": {"companion_profile": settings(style_preferences=["休闲"]), "selected_style": "休闲"},
    "preference_update/elegant": {"companion_profile": settings(style_preferences=["优雅"]), "selected_style": "优雅", "review_focus": "新资料替换旧偏好，必须改变真实选款而非只改标题。"},
    "preference_update/shoes": {"companion_profile": settings(style_preferences=["运动"]), "freeze_except": ["shoes"], "must_change_slots": ["shoes"], "review_focus": "更新默认偏好不能替换用户冻结的优雅上衣和下装。"},
}
for name, focus in {
    "inspiration": "已选天秤座，本轮应主动给简短星座娱乐灵感、灵感色和鼓励性的今日主题，并落实到实际衣物颜色或穿法；不冒充查询到的幸运色、运势，不违背休闲偏好和禁穿。",
    "decline": "用户明确不用星座，本轮不再加入星座解读或幸运色，按休闲偏好实际选款。",
    "friend": "为朋友选衣不沿用本人的天秤座、运势或幸运色。",
    "chat": "纯闲聊不强行加入星座穿搭或运势，不读衣橱或天气。",
}.items():
    EXPECTATIONS[f"preference_zodiac_outfit/{name}"] = {
        "companion_profile": settings(zodiac="天秤座", style_preferences=["休闲"]), "review_focus": focus}
EXPECTATIONS["preference_zodiac_outfit/inspiration"]["selected_style"] = "休闲"
EXPECTATIONS["preference_zodiac_outfit/decline"]["selected_style"] = "休闲"

for scenario, rows in SCENARIOS.items():
    for name, _, chat_only in rows:
        expected = EXPECTATIONS[f"{scenario}/{name}"]
        if not chat_only and (scenario.startswith('preference_outfit') or scenario in {'preference_priority', 'preference_update', 'preference_zodiac_outfit'}):
            expected.update(inventory=True, delivery="outfit", no_weather_tools=True, task={"no_heels": True},
                            forbid_item_ids=["209"])
        else:
            expected.update(no_tools=True)
            if chat_only:
                expected.update(no_looks=True, no_weather=True)

# Matching style evidence exists; no size, comfort or waterproof performance is invented.
PRODUCTS = [
    {"product_id":"201","class_name":"上衣","title":"白色棉质圆领T恤","color":"白色","material":"棉","styles":[{"name":"休闲"}]},
    {"product_id":"202","class_name":"裤子","title":"蓝色棉质牛仔裤","color":"蓝色","material":"棉","styles":[{"name":"休闲"}]},
    {"product_id":"211","class_name":"上衣","title":"米白色衬衫","color":"米白色","material":"棉","styles":[{"name":"优雅"}]},
    {"product_id":"212","class_name":"裙子","title":"灰色半身长裙","color":"灰色","material":"棉","styles":[{"name":"优雅"}]},
    {"product_id":"203","class_name":"鞋子","title":"白色平底运动鞋","color":"白色","material":"帆布"},
    {"product_id":"204","class_name":"鞋子","title":"黑色平底乐福鞋","color":"黑色","material":"皮革"},
    {"product_id":"209","class_name":"鞋子","title":"黑色高跟鞋","color":"黑色","material":"皮革"},
]

SCENARIOS.update(COVERAGE_SCENARIOS)
EXPECTATIONS.update(COVERAGE_EXPECTATIONS)
PRODUCTS.extend(COVERAGE_PRODUCTS)
