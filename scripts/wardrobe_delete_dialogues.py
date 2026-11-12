"""Semantic boundaries: database deletion is distinct from outfit editing."""
CASES = [
    ('这件白衬衫帮我从衣橱删掉', 'product'),
    ('把刚才那套搭配从我的搭配里删掉', 'outfit'),
    ('帮我删除这个单品和这套搭配', 'both'),
    ('Delete this item from my wardrobe', 'product'),
    ('帮我删掉这件', 'product'),
    ('不要删除，我只是想看看', None),
    ('这套搭配里不要这个包，其他保留', None),
    ('我已经把白衬衫删了，重新给我搭', None),
    ('删除这个聊天', None),
    ('把手记里不穿红色那条删掉', None),
]

CASES += [
    ('帮我把衣柜里不要的这件外套移除掉', 'product'),
    ('我的衣橱里这双鞋删掉吧', 'product'),
    ('把这只包从个人衣橱清掉', 'product'),
    ('把我的搭配里那套通勤装移除', 'outfit'),
    ('删除我保存的全部搭配', 'outfit'),
    ('把衣橱里的衣服都删掉', 'product'),
    ('能不能帮我删掉这件衣服？', 'product'),
    ('请先删除这件衣服，然后再给我搭一套', 'product'),
    ('Remove this saved outfit from my collection', 'outfit'),
    ('把这个单品delete掉，从我的衣柜移除', 'product'),
    ('别从衣橱删，只是这次不穿', None),
    ('我说的是从这套搭配里去掉外套，不是删除衣橱单品', None),
    ('如果删掉这件衣服，会影响之前的搭配吗？先别操作', None),
    ('我朋友说他把搭配删了', None),
    ('我删错了一件衣服，能恢复吗', None),
    ('把这套搭配的鞋换掉，其他保留', None),
    ('Delete the bag from this outfit, keep the rest; do not delete it from my wardrobe', None),
    ('我不要这条推荐理由，把解释删短一点', None),
    ('删除我的登录账号', None),
    ('把刚才上传的那张人物照片删了', None),
]


def contextual_cases():
    import json
    def assistant(**fields):
        return {'role': 'assistant', 'content': json.dumps(fields, ensure_ascii=False)}
    product = assistant(product_entry={'title': '白衬衫', 'subject': {'source': 'user', 'product_id': '11'}}, product_search=True)
    outfit = assistant(outfit_entry={'title': '已保存通勤搭配', 'subject': {'source': 'user', 'outfit_id': 12}}, saved_outfit_search=True)
    modification = assistant(looks=[{'title': '当前搭配', 'items': [{'source': 'user', 'product_id': '11', 'slot': 'accessory', 'name': '棕色包'}]}], message='这套搭配用白衬衫、长裤和棕色包。')
    return [
        {'message': '删了吧', 'expected': 'product', 'history': [product]},
        {'message': '这件不要了，帮我从衣橱清掉', 'expected': 'product', 'history': [product]},
        {'message': '删了吧', 'expected': 'outfit', 'history': [outfit]},
        {'message': '那就把这套删掉', 'expected': 'outfit', 'history': [outfit]},
        {'message': 'Delete it please', 'expected': 'outfit', 'history': [outfit]},
        {'message': '删了吧', 'expected': 'outfit', 'history': [product, outfit]},
        {'message': '删了吧', 'expected': 'product', 'history': [outfit, product]},
        {'message': '算了，先不删了', 'expected': None, 'history': [product, assistant(message='我不能直接删除，请到衣橱手动删除。')]},
        {'message': '你还是直接帮我删了吧', 'expected': 'product', 'history': [product, assistant(message='我不能直接删除，请到衣橱手动删除。')]},
        {'message': '我现在只想这次别穿这个包，衣橱里留着', 'expected': None, 'history': [modification]},
        {'message': '把这个包从当前方案去掉', 'expected': None, 'history': [modification]},
        {'message': '把这件系统参考款删掉', 'expected': 'product', 'scope': 'system', 'history': [assistant(product_entry={'title': '系统参考上衣', 'subject': {'source': 'system', 'product_id': '23'}})]},
        {'message': '替我把别人衣橱里的那件也删了', 'expected': 'product', 'scope': 'other', 'history': []},
    ]
