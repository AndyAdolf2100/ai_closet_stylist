"""Garment gender must constrain selected wardrobe items, independently of companion portraits."""

SCENARIOS = {
    'garment_gender_male': [
        ('self', '按我的设置，用衣橱搭一套通勤装，不考虑天气。', False),
        ('shoes', '只换另一双平底鞋，其他单品保留，不考虑天气。', False),
        ('other', '这次改给妹妹搭女装，不考虑天气。', False),
    ],
    'garment_gender_female': [
        ('self', '按我的设置，用衣橱搭一套日常装，不考虑天气。', False),
        ('other', '这次改给哥哥搭男装，不考虑天气。', False),
    ],
    'garment_gender_unset': [
        ('unisex', '没有设置本人性别，先用衣橱的男女通用款搭一套，不考虑天气。', False),
        ('explicit', '这次明确按男装搭一套，不考虑天气。', False),
    ],
    'garment_gender_no_match': [
        ('outfit', '按我的设置，用衣橱搭一套男装，不考虑天气。', False),
        ('reference', '没有匹配的单品就给文字参考，不要拿女款凑成男装。', False),
    ],
}

PURPOSES = {
    'garment_gender_male': '本人设男→真实选款→仅换鞋→改给妹妹；检查实际商品gender，男女助理不得改变穿衣对象。',
    'garment_gender_female': '本人设女→真实选款→改给哥哥；当轮男装覆盖本人资料，通用款仍可复用。',
    'garment_gender_unset': '本人未设性别不从助理推断；先选明确通用款，再按本轮明确男装筛选。',
    'garment_gender_no_match': '候选全部为女款、标签冲突或标题明确相反：不凑图，不把本次无匹配说成整个衣橱为空。',
}

PRODUCTS = [
    {'product_id':'101','class_name':'上衣','title':'男士白色长袖衬衫','gender':'1','color':'白色','material':'棉'},
    {'product_id':'201','class_name':'上衣','title':'女士白色长袖衬衫','gender':'2','color':'白色','material':'棉'},
    {'product_id':'106','class_name':'上衣','title':'男女同款长袖衬衫','gender':'3','color':'白色','material':'棉'},
    {'product_id':'102','class_name':'裤子','title':'男女通用灰色长裤','gender':'3','color':'灰色','material':'棉'},
    {'product_id':'103','class_name':'鞋子','title':'男女同款白色平底运动鞋','gender':'3','color':'白色','material':'棉'},
    {'product_id':'104','class_name':'鞋子','title':'男士黑色平底乐福鞋','gender':'1','color':'黑色','material':'皮革'},
    {'product_id':'204','class_name':'鞋子','title':'女士黑色平底乐福鞋','gender':'2','color':'黑色','material':'皮革'},
    {'product_id':'208','class_name':'上衣','title':'女士衬衫','gender':'1','color':'白色','material':'棉'},
    {'product_id':'209','class_name':'上衣','title':'白色长袖衬衫女2026','gender':'0','color':'白色','material':'棉'},
]


def expected(gender, profile_gender):
    return {'companion_profile': {'user_name':'小夏','agent_name':'知秋','user_gender':profile_gender},
            'task':{'gender':gender}, 'garment_gender':gender, 'require_gender_labels':True,
            'inventory':True, 'no_weather_tools':True}


EXPECTATIONS = {
    'garment_gender_male/self': expected('男', '男'),
    'garment_gender_male/shoes': expected('男', '男'),
    'garment_gender_male/other': expected('女', '男'),
    'garment_gender_female/self': expected('女', '女'),
    'garment_gender_female/other': expected('男', '女'),
    'garment_gender_unset/unisex': {**expected(None, None), 'unisex_items_only':True},
    'garment_gender_unset/explicit': expected('男', None),
    'garment_gender_no_match/outfit': {**expected('男','男'), 'allow_empty_looks':True,
                                      'no_owned_items':True, 'forbid_text':['衣橱为空','衣柜是空的']},
    'garment_gender_no_match/reference': {**expected('男','男'), 'inventory':False,
                                         'allow_empty_looks':True,'no_owned_items':True,
                                         'forbid_text':['衣橱为空','衣柜是空的']},
}
