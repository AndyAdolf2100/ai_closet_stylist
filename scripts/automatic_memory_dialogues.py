"""Multi-turn automatic-memory fixtures with exact persistent-book expectations."""

# Each turn specifies the complete book, not just a phrase expected in the reply.
CASES = {
    "likes": [
        ("positive", "我喜欢棉质衬衫。", ["我喜欢棉质衬衫"]),
        ("negative", "我不喜欢高跟鞋。", ["我喜欢棉质衬衫", "我不喜欢高跟鞋"]),
        ("repeat", "我喜欢棉质衬衫。", ["我喜欢棉质衬衫", "我不喜欢高跟鞋"]),
    ],
    "multiple": [
        ("both", "我喜欢蓝色，我讨厌羊毛衣。", ["我喜欢蓝色；我讨厌羊毛衣"]),
        ("daily", "我偏爱乌龙茶。", ["我喜欢蓝色；我讨厌羊毛衣", "我偏爱乌龙茶"]),
        ("communication", "我喜欢简洁的回复。", ["我喜欢蓝色；我讨厌羊毛衣", "我偏爱乌龙茶", "我喜欢简洁的回复"]),
    ],
    "temporary": [
        ("today", "今天我喜欢红色。", []),
        ("occasion", "这次我喜欢正式一点的衣服。", []),
        ("tentative", "我最近可能喜欢绿色。", []),
        ("stable", "我一直喜欢蓝色衬衫。", ["我一直喜欢蓝色衬衫"]),
    ],
    "refusal": [
        ("save", "我喜欢红色，不要保存。", []),
        ("note", "我喜欢蓝色，别写入手记。", []),
        ("record", "我喜欢绿色，不用记录。", []),
    ],
    "questions": [
        ("punctuation", "我喜欢蓝色吗？", []),
        ("no_punctuation", "我喜欢蓝色吗", []),
        ("unknown", "我喜欢什么颜色", []),
        ("guess", "你猜我喜欢什么？", []),
    ],
    "reported": [
        ("friend", "我朋友喜欢蓝色。", []),
        ("quote", "她说：我喜欢红色。", []),
        ("example", "比如我喜欢绿色，这只是举例。", []),
        ("hypothesis", "如果我喜欢黑色，你会怎么搭？", []),
    ],
    "context": [
        ("self", "我喜欢蓝色。", ["我喜欢蓝色"]),
        ("friend", "她喜欢绿色，别当作我的偏好。", ["我喜欢蓝色"]),
        ("pronoun", "这个颜色也不错。", ["我喜欢蓝色"]),
        ("new_session", "随便聊聊，不用推荐衣服。", ["我喜欢蓝色"]),
    ],
    "changed": [
        ("before", "我喜欢蓝色。", ["我喜欢蓝色"]),
        ("after", "我不喜欢蓝色。", ["我喜欢蓝色", "我不喜欢蓝色"]),
        ("temporary", "今天还是试试蓝色，不要修改手记。", ["我喜欢蓝色", "我不喜欢蓝色"]),
    ],
    "pause": [
        ("before", "我喜欢白色衬衫。", ["我喜欢白色衬衫"]),
        ("paused", "我喜欢黑色裤子。", ["我喜欢白色衬衫"]),
    ],
    "delete": [
        ("before", "我喜欢白色衬衫。", ["我喜欢白色衬衫"]),
        ("deleted", "聊点别的吧。", []),
    ],
    "compound": [
        ("original", "我喜欢穿短袖，衬衫，不喜欢黄色、绿色",
         ["我喜欢穿短袖，衬衫；不喜欢黄色、绿色"]),
        ("repeat", "我喜欢穿短袖，衬衫，不喜欢黄色、绿色",
         ["我喜欢穿短袖，衬衫；不喜欢黄色、绿色"]),
        ("save_report", "我喜欢穿短袖，衬衫，不喜欢黄色、绿色，不喜欢的没有保存。",
         ["我喜欢穿短袖，衬衫；不喜欢黄色、绿色"]),
        ("recall", "说说刚才提到的衣服和不喜欢的颜色就好。",
         ["我喜欢穿短袖，衬衫；不喜欢黄色、绿色"]),
    ],
    "compound_variants": [
        ("contrast", "我喜欢穿短袖、衬衫，但不喜欢黄色和绿色。",
         ["我喜欢穿短袖、衬衫；但不喜欢黄色和绿色"]),
        ("commas", "我喜欢穿短袖,衬衫,不喜欢黄色,绿色。",
         ["我喜欢穿短袖、衬衫；但不喜欢黄色和绿色", "我喜欢穿短袖,衬衫；不喜欢黄色,绿色"]),
        ("negative_first", "我不喜欢黄色、绿色，喜欢穿短袖和衬衫。",
         ["我喜欢穿短袖、衬衫；但不喜欢黄色和绿色", "我喜欢穿短袖,衬衫；不喜欢黄色,绿色",
          "我不喜欢黄色、绿色；喜欢穿短袖和衬衫"]),
        ("ambiguous_owner", "不喜欢红色。",
         ["我喜欢穿短袖、衬衫；但不喜欢黄色和绿色", "我喜欢穿短袖,衬衫；不喜欢黄色,绿色",
          "我不喜欢黄色、绿色；喜欢穿短袖和衬衫"]),
    ],
    "compound_subject": [
        ("friend", "我朋友喜欢短袖，衬衫，不喜欢黄色、绿色。", []),
        ("switch", "我喜欢穿短袖，我朋友不喜欢黄色，不喜欢绿色。", ["我喜欢穿短袖"]),
        ("topic", "我喜欢穿短袖，去逛街，不喜欢绿色。", ["我喜欢穿短袖"]),
    ],
    "compound_refusal": [
        ("refusal", "我喜欢穿短袖，衬衫，不喜欢黄色、绿色，不要保存。", []),
        ("question", "我喜欢穿短袖，衬衫，不喜欢黄色、绿色吗？", []),
        ("hypothesis", "假如我喜欢穿短袖，衬衫，不喜欢黄色、绿色。", []),
    ],
}
SCENARIOS, EXPECTATIONS = {}, {}
for group, turns in CASES.items():
    scenario = f"memory_auto_{group}"
    SCENARIOS[scenario] = [(name, message, True) for name, message, _ in turns]
    for name, _, contents in turns:
        EXPECTATIONS[f"{scenario}/{name}"] = {
            "memory_contents": contents,
            "no_tools": True,
            "no_looks": True,
            "review_focus": "核对真实手记内容与回执；未保存不得承诺已保存。本人喜恶不外推为身体事实或他人偏好。相反偏好当前只追加，不声称已覆盖或删除旧条目；当轮要求优先。",
            **({"new_conversation": True} if name == "new_session" else {}),
            **({"pause_memories": True} if name == "paused" else {}),
            **({"clear_memories": True} if name == "deleted" else {}),
        }
        if group.startswith("compound"):
            EXPECTATIONS[f"{scenario}/{name}"]["review_focus"] += (
                "同句省略主语沿用明确的本人对象，完整保留短袖、衬衫及黄色、绿色的否定关系。"
                "保存状态抱怨不当作新偏好，不从前轮推断本轮省略主语属于本人；回顾时不能反转喜恶。"
                "目前只按原文内容去重，不把不同标点或同义变体冒充已合并。")
