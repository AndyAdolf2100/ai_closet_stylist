"""Explicit option coverage and multi-turn boundaries for preference dialogue QA."""
from .companion_dialogues import profile

SCENARIOS = {}
EXPECTATIONS = {}
PRODUCTS = []


def add(name, rows):
    SCENARIOS[name] = []
    for turn, message, settings, focus, extra in rows:
        outfit = extra.pop('outfit', False)
        advice = extra.pop('advice', False)
        SCENARIOS[name].append((turn, message, not (outfit or advice)))
        expected = {'companion_profile': {**profile(), **settings}, 'review_focus': focus, **extra}
        if outfit:
            expected.update(inventory=True, delivery='outfit', no_weather_tools=True,
                            task={'no_heels': True}, forbid_item_ids=['209'])
        else:
            expected.update(no_tools=True)
            if not advice:
                expected.update(no_looks=True, no_weather=True)
        EXPECTATIONS[f'{name}/{turn}'] = expected


ZODIACS = ['白羊座', '金牛座', '双子座', '巨蟹座', '狮子座', '处女座', '天秤座', '天蝎座', '射手座', '摩羯座', '水瓶座', '双鱼座']
for i, zodiac in enumerate(ZODIACS):
    add(f'preference_zodiac_default_{i + 1:02}', [('answer', '聊聊我的星座吧，先说星座名称，再给我一点轻松的星座话题。',
        {'zodiac': zodiac}, '未在消息里指定星座，应直接采用本轮资料，不重复询问；传统说法明确为娱乐，不断言真实性格。', {'mentioned_zodiac': zodiac})])

add('preference_zodiac_context', [
    ('default', '聊聊我的星座吧，先说星座名称。', {'zodiac': '天秤座'}, '采用资料中的天秤座。', {'mentioned_zodiac': '天秤座'}),
    ('explicit', '这次聊白羊座，先说名称，不要聊我的星座。', {'zodiac': '天秤座'}, '显式白羊优先，不改写已保存资料。', {'mentioned_zodiac': '白羊座'}),
    ('followup', '那它的穿衣灵感呢？只聊配色思路，不查衣橱和天气。', {'zodiac': '天秤座'}, '它指上一轮白羊，继续白羊话题，不能突然换天秤；娱乐灵感不冒充运势。', {'advice': True, 'allow_empty_looks': True}),
    ('self', '回到我自己的星座，先说名称，聊聊吧。', {'zodiac': '天秤座'}, '回到当前资料的天秤，不将临时白羊当已保存星座。', {'mentioned_zodiac': '天秤座'}),
    ('updated', '我修改了设置，聊聊我现在选的星座，先说名称。', {'zodiac': '双鱼座'}, '下一轮使用新资料双鱼，不使用旧天秤。', {'mentioned_zodiac': '双鱼座'}),
    ('cleared', '我取消了星座选择，聊聊我的星座吧。', {'zodiac': None}, '询问想聊哪个星座，不从旧历史恢复双鱼或根据生日猜测。', {}),
])
add('preference_zodiac_unset', [
    ('ask', '聊聊我的星座吧。', {}, '未设置也未指定，应简短询问，不猜星座。', {}),
    ('explicit', '那聊射手座吧，先说名称。', {}, '未设置也能聊明确指定的射手，不强制用户保存资料。', {'mentioned_zodiac': '射手座'}),
    ('fortune', '查询射手座今天真实的幸运色和运势分数。', {}, '坦诚没有可靠当日数据，不编造查询结果或分数，可提供明确区分的娱乐灵感。', {}),
])

CHAT = '今天工作有点不顺，事情堆着不知道怎么开始，陪我聊聊。'
for name, tone, focus in [
    ('natural', '自然相处', '沿用当前男女基础人格，自然回应，不强加鼓励模板或笑话。'),
    ('humorous', '轻松幽默', '有适量自然幽默并回应困扰，不嘲笑用户或强行搞笑，保留男女基础人格。'),
]:
    add(f'preference_tone_{name}', [('answer', CHAT, {'conversation_style': tone}, focus, {})])
add('preference_detail_medium', [('answer', '只咨询穿法：白衬衫、灰色长裤、白色平底鞋，讲讲怎么穿得协调，不查衣橱和天气。',
    {'reply_detail': '适中'}, '适量解释可执行穿法，避免只给一句或长篇堆砌。', {'advice': True})])

OUTFIT = '从我的衣橱给我挑一套适合自己的日常搭配，不穿高跟鞋，不考虑天气。'
for i, (style, top, bottom) in enumerate([
    ('简约', '白色纯色圆领上衣', '黑色直筒裤'), ('通勤', '浅蓝色衬衫', '深灰色西装裤'),
    ('温柔', '淡粉色针织上衣', '米白色半身裙'), ('复古', '棕色格纹衬衫', '深蓝色牛仔裤'),
    ('运动', '灰色运动上衣', '黑色运动裤'), ('街头', '黑色印花T恤', '灰色工装裤'),
]):
    add(f'preference_style_{i + 1:02}', [('answer', OUTFIT, {'style_preferences': [style]},
        f'实际选择有{style}标签的衣物，说明穿法，不只在标题复述设置；不能捏造体感或性能。', {'outfit': True, 'selected_style': style})])
    for offset, title, category in [(0, top, '上衣'), (1, bottom, '裤子' if '裤' in bottom else '裙子')]:
        PRODUCTS.append({'product_id': str(300 + i * 2 + offset), 'title': title, 'class_name': category,
                         'styles': [{'name': style}]})

for i, (priority, focus) in enumerate([
    ('舒适自在', '给可调整松紧、活动试穿等具体建议，不凭名称或棉材质保证不勒、宽松合体。'),
    ('方便走动', '实际选平底鞋，穿法兼顾活动，不保证防滑或久走不累。'),
    ('容易打理', '给可执行的查看洗标、护理建议；没有洗标不能保证机洗、免烫或不易皱。'),
    ('已有衣物优先', '实际使用现有衣橱，不引导购买新衣物或虚构配件为已有。'),
    ('尝试新风格', '给熟悉休闲风一点可执行的新组合或细节点缀，不忽略禁穿，不承诺已改变长期设置。'),
]):
    add(f'preference_priority_{i + 1:02}', [('answer', OUTFIT, {'dressing_priorities': [priority], 'style_preferences': ['休闲']},
        focus, {'outfit': True})])

add('preference_combined_reset', [
    ('combined', OUTFIT, {'zodiac': '水瓶座', 'conversation_style': '轻松幽默', 'reply_detail': '简洁重点',
        'style_preferences': ['简约', '休闲', '运动'], 'dressing_priorities': ['舒适自在', '方便走动', '容易打理']},
        '兼顾多选软偏好，简洁且轻松，加入水瓶娱乐灵感；不需每套体现全部风格，不保证舒适和护理性能。', {'outfit': True}),
    ('override', '这次严肃一点，细致解释我这件白衬衫怎么穿，只讲穿法，不查衣橱和天气，也不用星座。',
        {'zodiac': '水瓶座', 'conversation_style': '轻松幽默', 'reply_detail': '简洁重点'},
        '本轮严肃、细致和不用星座覆盖保存设置，不能继续玩笑或过度简略。', {'advice': True}),
    ('reset', '我已恢复默认，随便陪我聊聊今天吧。', {}, '默认自然相处、适中，无星座无风格偏好，不沿用旧设置或宣称修改资料。', {}),
])
add('preference_no_matching_style', [('answer', OUTFIT, {'style_preferences': ['复古']},
    '夹具没有复古标签的衣物，可给现有衣物的近似灵感但如实说明限制，不编造复古单品。', {'outfit': True})])
