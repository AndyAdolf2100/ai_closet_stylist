"""Synthetic memory acceptance conversations, run for both companion personas."""
SCENARIOS = {
    'memory_explicit': [
        ('save', '我喜欢乌龙茶，这件事一定要记住。', True),
        ('new_chat', '你还记得我喜欢喝什么吗？', True),
        ('delete', '我已经在设置删掉那页了，现在手记里还记着什么？', True),
    ],
    'memory_reference': [
        ('fact', '我不穿高跟鞋，平时走路比较多。', True),
        ('remember', '刚才说的这个一定要记住。', True),
        ('outfit', '用我的衣橱搭一套日常穿搭，不查天气。', False),
    ],
    'memory_no_implicit': [
        ('fact', '我喜欢乌龙茶。', True),
        ('quote', '我妈说“一定要记住带伞”，这句话听着好亲切。', True),
        ('negation', '我今天穿红色，但不要记住这件事。', True),
        ('question', '你记住了吗？我只是问问，没有要求保存。', True),
    ],
    'memory_boundaries': [
        ('save', '我不穿高跟鞋，以后都记着。', True),
        ('other', '给朋友讲讲高跟鞋的搭配，只给文字，不查衣橱和天气。', False),
        ('paused', '只给我一些日常穿法建议，不查衣橱和天气。', False),
    ],
}
EXPECTATIONS = {
    'memory_explicit/save': {'memory_contents': [], 'no_tools': True,
        'review_focus': '新范围仅保存穿搭，明确要求记住饮食也不写入，简短说明范围并自然回应。'},
    'memory_explicit/new_chat': {'new_conversation': True, 'memory_contents': [], 'no_tools': True,
        'review_focus': '新会话没有饮食长记忆，不编造知道喜欢乌龙茶。'},
    'memory_explicit/delete': {'clear_memories': True, 'new_conversation': True, 'memory_contents': [], 'no_tools': True},
    'memory_reference/fact': {'memory_contents': [], 'no_tools': True},
    'memory_reference/remember': {'memory_contains': '不穿高跟鞋', 'no_tools': True},
    'memory_reference/outfit': {'inventory': True, 'no_weather_tools': True, 'delivery': 'outfit', 'memory_contains': '不穿高跟鞋'},
    'memory_boundaries/save': {'memory_contains': '不穿高跟鞋', 'no_tools': True},
    'memory_boundaries/other': {'no_tools': True, 'no_real_items': True, 'allow_empty_looks': True},
    'memory_boundaries/paused': {'pause_memories': True, 'no_tools': True, 'no_real_items': True},
}
for name, _, _ in SCENARIOS['memory_no_implicit']:
    EXPECTATIONS[f'memory_no_implicit/{name}'] = {'memory_contents': [], 'no_tools': True}


SCENARIOS['memory_clothing_scope'] = [
    ('daily', '我喜欢乌龙茶。', True),
    ('daily_explicit', '记住：我喜欢乌龙茶。', True),
    ('agreement', '请记住：先听我说完，再给建议。', True),
    ('clothing_explicit', '记住：我不穿高跟鞋', True),
    ('clothing_auto', '我喜欢棉质衬衫，我不喜欢羊毛衣。', True),
    ('mixed', '我喜欢蓝色，我偏爱乌龙茶。', True),
    ('diary', '我昨天穿蓝色衬衫去喝茶。', True),
    ('new_chat', '看看手记，我不穿什么鞋，喜欢什么衬衫和颜色？', True),
    ('cleared', '我在设置清空了手记，现在手记里还有什么？', True),
    ('boundary', '别叫我宝贝，我不喜欢。', True),
]
saved = []
for name, _, _ in SCENARIOS['memory_clothing_scope']:
    if name == 'clothing_explicit':
        saved = ['我不穿高跟鞋']
    elif name == 'clothing_auto':
        saved = [*saved, '我喜欢棉质衬衫；我不喜欢羊毛衣']
    elif name == 'mixed':
        saved = [*saved, '我喜欢蓝色']
    elif name == 'cleared':
        saved = []
    EXPECTATIONS[f'memory_clothing_scope/{name}'] = {
        'memory_contents': saved.copy(), 'no_tools': True, 'no_looks': True,
        'review_focus': '仅本人穿搭信息可入手记；日常、相处约定、饮食即使明确说记住也不保存。回执与实际状态一致，只分享喜好不主动选款。',
        **({'new_conversation': True, 'must_text': ['高跟', '蓝色'], 'must_text_any': [['棉质', '棉']]} if name == 'new_chat' else {}),
        **({'clear_memories': True, 'new_conversation': True} if name == 'cleared' else {}),
    }
