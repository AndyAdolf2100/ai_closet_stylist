"""Text-intent regressions, distinct from attachment/button journeys."""
SCENARIOS = {
    "upload_words": [
        ("upload", "我想上传一件衣服。", True),
        ("increase", "给我的衣柜增加几件衣物。", True),
        ("add", "添加一条新买的裙子。", True),
        ("record", "怎么把新买的鞋录入衣橱？", True),
        ("bag", "我能拍照把包包收进衣柜吗？", True),
        ("accessory", "想把这条项链也录进去。", True),
    ],
    "upload_photo_purpose": [
        ("photo", "我想上传一个照片。", True),
        ("clothes", "是衣服照片，想添加到衣柜。", True),
        ("decline", "先不上传，等我找好照片。", True),
    ],
    "upload_synonyms": [
        ("upload_clothes", "上传衣物", True),
        ("add_clothes", "添加衣服", True),
        ("increase_clothes", "增加衣物", True),
        ("new_shoes", "刚买了一双鞋，帮我放到我的衣柜里。", True),
        ("scan", "能不能把这件外套拍照录进来？", True),
    ],
    "upload_boundaries": [
        ("negative", "我不想上传衣服。", True),
        ("reported", "朋友说她想添加一件衣服到衣橱，这只是转述。", True),
        ("example", "假设用户说增加一件衣服，这只是举例，不是我要操作。", True),
        ("done", "我刚才已经上传完衣服了，暂时不用搭配。", True),
        ("person", "我想上传本人自拍来创建数字人，不是上传衣物。", True),
        ("avatar", "我要添加一个头像，不是衣服。", True),
        ("layer", "我只是讨论给搭配加一件外套，不是往衣柜新增衣物，先不用生成搭配。", True),
        ("file", "我要上传文件，不是衣服照片，只是说一下，先不用操作。", True),
    ],
}
EXPECTATIONS = {}
for scenario, rows in SCENARIOS.items():
    for turn, _, _ in rows:
        intent = ("garment" if scenario in {"upload_words", "upload_synonyms"} or turn == "clothes" else
                  "unspecified" if turn == "photo" else None)
        EXPECTATIONS[f"{scenario}/{turn}"] = {
            "upload_intent": intent, "upload_suggestion": intent == "garment",
            "inventory": False, "no_tools": True, "no_looks": True, "no_weather": True,
            "upload_question": intent is not None,
            "review_focus": "先按助理人设问询并给上传步骤卡片；卡片只引导选图，不自动上传、写入或收费。用途不明先区分，否定与转述不误触发。",
        }
