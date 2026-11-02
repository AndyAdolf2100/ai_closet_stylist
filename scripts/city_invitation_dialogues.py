"""Destination-aware weather invitations; text cases and UI journeys are separate."""
SCENARIOS = {
    'city_invite_missing': [
        ('outfit', '我需要一套穿搭。', False),
        ('city', '在上海穿，其他要求不变。', False),
        ('inherited', '再来一套休闲一点的。', False),
    ],
    'city_invite_explicit': [
        ('shanghai', '我要在上海通勤，帮我搭一套。', False),
        ('sanya', '改成去三亚玩，给我一套度假穿搭。', False),
        ('route', '上海和三亚各搭一套，按两个地方的天气来。', False),
    ],
    'city_invite_opt_out': [
        ('ignored', '我需要一套穿搭，不考虑天气。', False),
        ('restored', '这次要考虑天气，再帮我搭一套。', False),
    ],
    'city_invite_text_outing': [
        ('outing', '今天要出门通勤，只给文字穿法，不查衣橱。', False),
        ('city', '我在上海，按刚才的要求继续。', False),
    ],
    'city_invite_boundaries': [
        ('principle', '只讲配色原理，黑白灰怎么组合？', False),
        ('greeting', '你好，今天心情不错。', True),
        ('upload', '我想上传一件衣服到衣橱。', True),
    ],
    'city_invite_selected': [
        ('selected', '我需要一套通勤穿搭。', False),
        ('destination', '我要去三亚旅行，给我一套当地适合穿的。', False),
    ],
}
PURPOSES = {
    'city_invite_missing': '泛穿搭请求缺城市显示卡片；明确城市后及同城追问不再显示。',
    'city_invite_explicit': '明确目的地与多地行程不索取本人定位，不重复弹城市卡。',
    'city_invite_opt_out': '仅本轮明确忽略天气时跳过，下一轮恢复天气且无城市时显示。',
    'city_invite_text_outing': '只要文字、不查衣橱不等于忽略出行天气；选城市后继续原要求。',
    'city_invite_boundaries': '纯穿法原理、普通闲聊及上传服饰不触发天气城市引导。',
    'city_invite_selected': '已选城市直接使用，本轮明确目的地优先于页面城市。',
}
EXPECTATIONS = {}
for scenario, rows in SCENARIOS.items():
    for turn, _, _ in rows:
        needs_city = (scenario, turn) in {
            ('city_invite_missing', 'outfit'), ('city_invite_opt_out', 'restored'),
            ('city_invite_text_outing', 'outing'),
        }
        expected = {'city_selection_required': needs_city,
                    'review_focus': PURPOSES[scenario]}
        if scenario == 'city_invite_selected':
            expected['location'] = {'city_name': '上海市', 'province_name': '上海市'}
        if scenario in {'city_invite_text_outing', 'city_invite_boundaries'}:
            expected['inventory'] = False
        if scenario == 'city_invite_boundaries':
            expected['no_weather'] = True
        EXPECTATIONS[f'{scenario}/{turn}'] = expected
