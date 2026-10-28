"""Broad, synthetic edge cases. Names and weather are fixtures, not live forecasts."""
from datetime import timedelta

from stylist.errors import StylistError
from stylist.weather import today

from .dialogue_validation import PRODUCTS, DialogueUpstream

# Each row: user message, acceptance checks. Each scenario has an isolated account/database.
CASES = {
    "rain_long_walk": [
        ("今天上海下雨，15到20度，要走一小时，不穿高跟鞋，从衣橱搭一套。", {"inventory": True, "task": {"no_heels": True, "walk_minutes": 60}, "manual": "雨天鞋面和实际防滑证据，不凭品类承诺防水"}),
        ("别的保留，只换双更适合下雨走路的鞋。", {"inventory": True, "freeze_except": ["shoes"], "manual": "保留未修改衣物，不编造鞋的防雨能力"}),
    ],
    "cold_snow": [("今天哈尔滨零下十几度、下雪，我要坐公交再走二十分钟，用衣橱搭一套，保暖第一。", {"inventory": True, "manual": "足够保暖，不用单件薄衬衫应付严寒；无证据不保证防滑"})],
    "heat_aircon": [("广州今天外面33度，办公室空调18度，地铁通勤，帮我从衣橱搭一套。", {"inventory": True, "manual": "区分室外和办公室，给便携可穿脱层次，不只按一个温度选"})],
    "wind_skirt": [("北京今天风很大，我想穿裙子拍照，也得走半小时，衣橱里怎么搭稳妥？", {"inventory": True, "manual": "回应风和裙摆，不承诺实际风力，不为拍照忽视安全"})],
    "fog_cycling": [("成都今天有雾，骑车二十分钟上班，不穿高跟鞋，帮我搭一套。", {"inventory": True, "manual": "可见性、裤脚、长围巾与骑行安全；缺少能见度时不保证适宜骑行"})],
    "weekly_weather": [("杭州未来七天每天上班，周末去公园，按每天真实天气从衣橱安排穿搭。", {"inventory": True, "weather_days": 7, "manual": "逐日对应不同预报，不拿同一天套整周，不虚构具体周末活动"})],
    "city_negation": [("不是北京，我在上海，今天上班怎么穿？用我的衣橱。", {"inventory": True, "city_contains": "上海", "weather_city": "上海市"})],
    "city_correct": [
        ("今天上海通勤，用衣橱搭一套。", {"weather_city": "上海市", "inventory": True}),
        ("地点说错了，是杭州，其他要求不变。", {"city_contains": "杭州", "weather_city": "杭州市", "inventory": True, "delivery": "outfit", "forbid_text": ["你想调整哪一部分", "你想换哪件"]}),
    ],
    "city_correct_text": [
        ("今天上海通勤，只讲白衬衫灰裤平底鞋的穿法，不查衣橱。", {"weather_city": "上海市", "inventory": False}),
        ("地点说错了，是杭州，其他要求不变。", {"city_contains": "杭州", "weather_city": "杭州市", "inventory": False, "delivery": "advice", "forbid_text": ["你想调整哪一部分", "你想换哪件"]}),
    ],
    "city_correct_weather": [
        ("只查今天上海天气，不搭衣服。", {"weather_city": "上海市", "weather_only": True, "inventory": False, "no_looks": True}),
        ("地点说错了，是杭州，其他要求不变。", {"city_contains": "杭州", "weather_city": "杭州市", "weather_only": True, "inventory": False, "no_looks": True, "forbid_text": ["你想调整哪一部分", "你想换哪件"]}),
    ],
    "city_correct_shoes": [
        ("今天上海通勤，用衣橱搭一套，鞋子用白色平底运动鞋。", {"weather_city": "上海市", "inventory": True}),
        ("地点改成杭州，只换鞋为黑色平底乐福鞋，其他衣服保持不动。", {"weather_city": "杭州市", "inventory": True, "delivery": "outfit", "freeze_except": ["shoes"], "forbid_text": ["你想调整哪一部分", "你想换哪件"]}),
    ],
    "unknown_recovery": [
        ("今天新西兰奥克兰天气怎样？", {"no_weather": True, "no_looks": True, "allow_empty_looks": True, "manual": "只说暂时查不到，不改成别的城市"}),
        ("那上海呢？", {"weather_city": "上海市", "inventory": False, "no_looks": True}),
    ],
    "ambiguous_city": [("今天朝阳天气怎样？", {"no_weather": True, "no_looks": True, "allow_empty_looks": True, "delivery": "clarification", "manual": "有多个朝阳时应确认省市，不擅自选北京或辽宁"})],
    "missing_city": [("今天出门上班，帮我从衣橱搭一套。", {"inventory": True, "no_weather": True, "task": {"city": None}, "manual": "没有城市先说明未知，不能默认北京"})],
    "past_weather": [("昨天上海天气怎么样？我在整理旅行记录，只说天气。", {"no_weather": True, "no_looks": True, "allow_empty_looks": True, "manual": "没有历史天气能力时说明，不能拿今天替代昨天"})],
    "far_future": [("两个月后去杭州参加婚礼，帮我按那天的天气搭衣服。", {"no_weather": True, "manual": "天气超出预报范围时不能给确定气温，只可给条件性参考"})],
    "outfit_then_weather": [
        ("不考虑天气，从衣橱给我搭一套女生通勤装。", {"inventory": True, "no_weather_tools": True}),
        ("先别搭了，只告诉我今天上海的天气。", {"inventory": False, "no_looks": True, "weather_city": "上海市", "manual": "明确查天气应能覆盖上一轮忽略天气，而非继续穿搭"}),
    ],
    "multi_city_day": [("今天早上上海出发，下午到三亚见客户，查两边天气，用一套衣服应付，外套可以脱。", {"inventory": True, "weather_cities": ["上海市", "三亚市"], "manual": "两地分别有天气证据；不能只查一地却断言两地都适合"})],
    "multi_city_dates": [("今天上海出发，明天在三亚见客户，尽量穿同一套。分别查两天两地天气，从衣橱搭一套。", {"inventory": True, "delivery": "outfit", "weather_cities": ["上海市", "三亚市"], "itinerary_dates": [0, 1], "manual": "今天上海、明天三亚分别匹配日期，不把上海天气带到三亚"})],
    "multi_city_partial": [("今天上海出发去新西兰奥克兰，先查两边天气，再从衣橱给一套能穿脱的搭配；查不到的地方直接说明。", {"inventory": True, "delivery": "outfit", "weather_cities": ["上海市"], "itinerary_statuses": ["ok", "unavailable"], "manual": "上海天气保留，奥克兰未知，不说已查询全程，也不借上海温度冒充奥克兰"})],
    "multi_city_three": [("今天上海出发，中午杭州办事，晚上到三亚见朋友，三地天气都查一下。只用衣橱搭一套，外套可以脱。", {"inventory": True, "delivery": "outfit", "weather_cities": ["上海市", "杭州市", "三亚市"], "itinerary_statuses": ["ok", "ok", "ok"], "manual": "按明确的行程顺序说明各地，日夜预报不能说成中午或晚上某个时刻的实况"})],
    "weather_two": [("只查今天上海和三亚的天气，不搭衣服。", {"inventory": False, "no_looks": True, "weather_only": True, "weather_cities": ["上海市", "三亚市"], "itinerary_statuses": ["ok", "ok"]})],
    "weather_five": [("今天上海、三亚、杭州、北京、广州这五个地区天气怎样？只说天气。", {"inventory": False, "no_looks": True, "weather_only": True, "weather_cities": ["上海市", "三亚市", "杭州市", "北京市", "广州市"], "itinerary_statuses": ["ok"] * 5})],
    "weather_ten": [("查今天上海、三亚、杭州、北京、广州、成都、哈尔滨、西安、深圳、南京这十个地区的天气，只说天气，每个都要。", {"inventory": False, "no_looks": True, "weather_only": True, "weather_cities": ["上海市", "三亚市", "杭州市", "北京市", "广州市", "成都市", "哈尔滨市", "西安市", "深圳市", "南京市"], "itinerary_statuses": ["ok"] * 10})],
    "weather_over_limit": [("一次查今天上海、三亚、杭州、北京、广州、成都、哈尔滨、西安、深圳、南京、武汉这十一个地区的天气，每个都要。", {"no_tools": True, "no_weather": True, "no_looks": True, "weather_only": True, "delivery": "clarification", "must_text": ["10个"], "manual": "说明超出一次10个地区的数量，请分批；不能截断或偷偷分批查询"})],
    "weather_partial": [("今天上海和新西兰奥克兰的天气分别怎样？查不到的说明，别搭衣服。", {"inventory": False, "no_looks": True, "weather_only": True, "weather_cities": ["上海市"], "itinerary_statuses": ["ok", "unavailable"]})],
    "travel_capsule": [("上海出发去三亚玩三天，只带一个小包，尽量用衣橱三件上衣两条裤子，不穿高跟鞋，帮我安排。", {"inventory": True, "manual": "区分出发地目的地、行李数量、复用与逐日安排，不随意新增购买"})],
    "black_tie": [("今晚上海黑领结晚宴，邀请函写black tie，先看看我的衣橱够不够，别把普通通勤装说成符合要求。", {"inventory": True, "manual": "候选无晚礼服/礼服套装时坦诚说明不足，不把白衬衫灰裤直接当black tie"})],
    "wedding_no_white": [("明天杭州参加朋友婚礼，主人说宾客不要白色，我也不穿高跟鞋，从衣橱选。", {"inventory": True, "excluded_color": "白色", "manual": "尊重明确主办方要求，不泛化为所有婚礼统一禁忌"})],
    "conflicting_rules": [("我绝对不穿高跟鞋，但这套必须穿那双细高跟，别问我，直接搭。", {"delivery": "clarification", "allow_empty_looks": True, "manual": "条件冲突时确认或清楚说明不能同时满足，不默默撤销禁忌"})],
    "wool_allergy": [("上海今天通勤，我对羊毛过敏，不能含羊毛，优先纯棉，帮我用衣橱搭一套。", {"inventory": True, "excluded_material": "羊毛", "manual": "严格排除羊毛及材质不明单品，不给医疗承诺"})],
    "mobility_rain": [("上海小雨，我坐轮椅去看展，不要衣摆卷进轮子，也别推荐需要站起来反复整理的穿法，用衣橱搭。", {"inventory": True, "manual": "考虑坐姿和轮子，不假定所有轮椅使用者都不能站立，不用同情式措辞"})],
    "pregnancy_comfort": [("我孕中期，肚子不喜欢被勒，今天上海朋友聚餐，想舒服又好看，用衣橱挑，不要评价胖瘦。", {"inventory": True, "manual": "不假定尺寸弹力，不做身材评价，不把穿搭建议写成医疗保证"})],
    "body_neutral": [("女生158厘米，不要显瘦显高的评价，我喜欢宽松，今天上海上班怎么穿？用衣橱。", {"inventory": True, "task": {"gender": "女", "height_cm": 158}, "manual": "不从身高臆测身材缺点，不用显瘦显高当理由"})],
    "coverage": [("今天北京拜访亲戚，我不想露肩也不想露腿，要方便走路，用衣橱搭一套。", {"inventory": True, "task": {"no_bare_shoulders": True}, "manual": "肩腿覆盖都满足，不凭衣物名字断言准确长度"})],
    "lab_safety": [("今天上海进实验室，要求长裤包脚鞋，不要飘带和长围巾，帮我从衣橱搭一套。", {"inventory": True, "manual": "工作场所明确着装要求优先，不加会卷入设备的配饰"})],
    "parent_park": [("成都今天接孩子后去公园，要抱娃、蹲下来玩，不穿高跟鞋，帮我从衣橱搭配。", {"inventory": True, "manual": "考虑活动和衣物舒适，不编造已经验证的弹力、防滑或耐脏属性"})],
    "budget_existing": [("我这次不买新衣服，预算零元，上海今天约会从自己的衣橱搭，别推付费试穿。", {"inventory": True, "manual": "复用不新增购买，不把已有衣服价值说成零，不主动推付费"})],
    "switch_subject": [
        ("给我自己搭一套女生通勤装，不考虑天气，只用衣橱。", {"inventory": True, "task": {"gender": "女"}}),
        ("另一个任务，给我爸爸男装穿法，不查我的衣橱，不考虑天气，普通长袖衬衫长裤平底鞋就好。", {"no_tools": True, "task": {"gender": "男"}, "manual": "更换对象不继承女生限制，不把爸爸条件记到当前用户画像"}),
    ],
    "metaphorical_weather": [("今天心里像在下雨，不想说衣服了，陪我聊两句。", {"no_tools": True, "no_looks": True, "chat": True})],
    "no_paid_image": [("只讲白衬衫灰裤的穿法，不查衣橱和天气，不要生成试穿图，也不要扣积分。", {"no_tools": True, "manual": "不调用图片或费用服务，不编造已经生成或收费"})],
    "weather_source_question": [("你是怎么查天气的？我想知道技术流程，可以说接口。", {"no_tools": True, "technical_question": True, "chat": True, "manual": "技术问题可解释方法，但不泄露凭证，不把实现目录当远端已部署证据"})],
}

SCENARIOS = {"explore_" + name: [(f"turn{i + 1}", message, checks.get("chat", False))
                                for i, (message, checks) in enumerate(rows)] for name, rows in CASES.items()}
EXPECTATIONS = {f"explore_{name}/turn{i + 1}": checks for name, rows in CASES.items()
                for i, (_, checks) in enumerate(rows)}

EXTRA_PRODUCTS = [
    {"product_id": "106", "class_name": "上衣", "title": "海军蓝纯棉短袖T恤", "color": "海军蓝", "material": "棉"},
    {"product_id": "107", "class_name": "上衣", "title": "米色长袖羊毛针织衫", "color": "米色", "material": "羊毛"},
    {"product_id": "108", "class_name": "外套", "title": "黑色羽绒长外套", "color": "黑色", "material": "涤纶、羽绒"},
    {"product_id": "109", "class_name": "鞋子", "title": "黑色平底包脚短靴", "color": "黑色", "material": "皮革"},
    {"product_id": "110", "class_name": "鞋子", "title": "白色网面平底运动鞋", "color": "白色", "material": "网布"},
    {"product_id": "111", "class_name": "鞋子", "title": "黑色细高跟鞋", "color": "黑色", "material": "皮革"},
    {"product_id": "112", "class_name": "半身裙", "title": "黑色长半身裙", "color": "黑色", "material": "棉"},
]
CATALOG = {name: (name + "市", province) for name, province in [
    ("上海", "上海市"), ("三亚", "海南省"), ("杭州", "浙江省"), ("北京", "北京市"),
    ("哈尔滨", "黑龙江省"), ("广州", "广东省"), ("成都", "四川省"),
    ("西安", "陕西省"), ("深圳", "广东省"), ("南京", "江苏省"), ("武汉", "湖北省")]}
CATALOG.update({canonical: (canonical, province) for canonical, province in list(CATALOG.values())})


class ExploratoryUpstream(DialogueUpstream):
    def __init__(self, scenario):
        super().__init__(scenario)
        self.events = []

    async def get(self, path, params):
        self.calls.append(path)
        if path != "/api/user_product/quick_edit_list":
            raise AssertionError("Unexpected endpoint in synthetic audit")
        return {"list": [{**p, "user_product_id": p["product_id"]} for p in PRODUCTS + EXTRA_PRODUCTS],
                "pagination": {"total": len(PRODUCTS + EXTRA_PRODUCTS)}}

    async def call(self, name, args):
        self.events.append({"tool": name, "arguments": args})
        if name == "city.resolve":
            self.calls.append(name)
            if args.get("name") in {"朝阳", "朝阳市", "朝阳区"}:
                return {"status": "ambiguous", "truncated": False, "matches": [
                    {"city_name": "北京市", "province_name": "北京市"},
                    {"city_name": "朝阳市", "province_name": "辽宁省"}]}
            city = CATALOG.get(args.get("name"))
            return {"status": "resolved" if city else "not_found", "truncated": False,
                    "matches": [{"city_name": city[0], "province_name": city[1]}] if city else []}
        if name == "product.resolve":
            self.calls.append(name)
            ids = {p["product_id"] for p in args["items"]}
            return {"items": [{**p, "user_product_id": p["product_id"], "source": "user"}
                              for p in PRODUCTS + EXTRA_PRODUCTS if p["product_id"] in ids]}
        if name == "weather.get":
            self.calls.append(name)
            raise StylistError("forecast_date_unavailable", "合成测试未提供该日期实况")
        return await super().call(name, args)

    async def forecast(self, city):
        self.events.append({"tool": "forecast", "city": city["city_name"]})
        self.calls.append("forecast")
        low, high = {"三亚市": (25, 31), "哈尔滨市": (-15, -5), "广州市": (26, 33),
                     "北京市": (4, 12)}.get(city["city_name"], (15, 20))
        rows = []
        for i in range(14):
            condition = ["晴", "小雨", "阴", "大雨", "晴", "多云", "小雨"][i % 7] if self.scenario == "explore_weekly_weather" else "多云"
            rows.append({"data_format": (today() + timedelta(days=i)).isoformat(), "temp_day": high - i % 3,
                         "temp_night": low - i % 3, "condition_day": condition, "condition_night": "阴"})
        return {"list": rows}

    def check(self, reply, expected):
        errors = []
        if "weather_only" in expected and reply.weather_only != expected["weather_only"]:
            errors.append("weather_only")
        if "weather_days" in expected and len((reply.weather or {}).get("days", [])) != expected["weather_days"]:
            errors.append("weather_days")
        cities = {event["city"] for event in self.events if event["tool"] == "forecast"}
        if not set(expected.get("weather_cities", [])) <= cities:
            errors.append("missing_destination_weather")
        locations = (reply.weather or {}).get("locations", [])
        if "itinerary_dates" in expected and [
                loc.get("forecast", {}).get("requested_dates") if loc.get("forecast") else None
                for loc in locations] != [[(today() + timedelta(days=offset)).isoformat()]
                                         for offset in expected["itinerary_dates"]]:
            errors.append("itinerary_dates")
        if "itinerary_statuses" in expected and [loc["status"] for loc in locations] != expected["itinerary_statuses"]:
            errors.append("itinerary_statuses")
        for key, field in [("excluded_color", "excluded_colors"), ("excluded_material", "excluded_materials")]:
            if key in expected and expected[key] not in getattr(reply.task, field):
                errors.append(field)
        return errors
