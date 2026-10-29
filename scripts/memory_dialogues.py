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
    'memory_explicit/save': {'memory_contents': ['我喜欢乌龙茶'], 'no_tools': True},
    'memory_explicit/new_chat': {'new_conversation': True, 'memory_contents': ['我喜欢乌龙茶'], 'no_tools': True},
    'memory_explicit/delete': {'clear_memories': True, 'new_conversation': True, 'memory_contents': [], 'no_tools': True},
    'memory_reference/fact': {'memory_contents': [], 'no_tools': True},
    'memory_reference/remember': {'memory_contains': '不穿高跟鞋', 'no_tools': True},
    'memory_reference/outfit': {'inventory': True, 'no_weather_tools': True, 'delivery': 'outfit', 'memory_contains': '不穿高跟鞋'},
    'memory_boundaries/save': {'memory_contains': '不穿高跟鞋', 'no_tools': True},
    'memory_boundaries/other': {'no_tools': True, 'no_real_items': True},
    'memory_boundaries/paused': {'pause_memories': True, 'no_tools': True, 'no_real_items': True},
}
for name, _, _ in SCENARIOS['memory_no_implicit']:
    EXPECTATIONS[f'memory_no_implicit/{name}'] = {'memory_contents': [], 'no_tools': True}
