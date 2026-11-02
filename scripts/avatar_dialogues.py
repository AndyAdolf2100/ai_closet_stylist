"""Avatar intentions use real text evaluation, never real image dispatch."""
SCENARIOS = {
    'avatar_upload_words': [
        ('virtual','我想上传虚拟形象。',True),
        ('twin','上传数字分身。',True),
        ('human','我想上传数字人。',True),
        ('selfie','上传我本人的照片，创建试穿形象。',True),
    ],
    'avatar_view_words': [
        ('view','查看虚拟形象。',True),
        ('choose','我想选择一个已有的试穿形象。',True),
        ('switch','看看我的数字分身，换一个已有的形象。',True),
    ],
    'avatar_tryon_context': [
        ('outfit','从我的衣橱选一套女生通勤穿搭，不考虑天气。',False),
        ('start','确认开始生成试穿搭配。',True),
        ('view','先查看可选的虚拟形象。',True),
        ('upload','我想上传数字分身，继续试穿刚才那套。',True),
        ('cancel','先别生成，也不上传，等我想好。',True),
    ],
    'avatar_boundaries': [
        ('no_outfit','开始生成试穿图。',True),
        ('refuse','我不想上传数字人，也不要试穿。',True),
        ('reported','朋友说她想上传数字分身，只是转述，不是我的需求。',True),
        ('example','假设用户说查看虚拟形象，这只是举例。',True),
        ('principle','先只解释一下虚拟形象试穿是什么原理，不要实际生成。',True),
    ],
}
EXPECTATIONS = {}
for name, rows in SCENARIOS.items():
    for turn, _, _ in rows:
        intent = ('upload' if name=='avatar_upload_words' or name=='avatar_tryon_context' and turn=='upload' else
                  'view' if name=='avatar_view_words' or name=='avatar_tryon_context' and turn=='view' else
                  'tryon' if turn in {'start','no_outfit'} else None)
        if turn=='outfit':
            expected={'inventory':True,'no_weather_tools':True,'delivery':'outfit'}
        else:
            expected={'avatar_intent':intent,'upload_intent':None,'upload_suggestion':False,
                      'no_tools':True,'no_looks':True,'no_weather':True,
                      'review_focus':'对话只给乙游风格的上传／选择卡片，绑定原搭配，不直接上传或扣费；费用必须界面单独确认。'}
            if name=='avatar_tryon_context' and intent:
                expected['tryon_reference']=True
            if turn=='no_outfit':
                expected['tryon_reference']=False
        EXPECTATIONS[f'{name}/{turn}']=expected
