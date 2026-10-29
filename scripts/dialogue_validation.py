"""Synthetic dialogue cases and evidence checks; never contacts business services."""
from contextlib import asynccontextmanager
from datetime import timedelta

from pydantic import Field

from stylist.errors import StylistError
from stylist.models import Model
from stylist.weather import today

from .companion_dialogues import EXPECTATIONS as COMPANION_EXPECTATIONS
from .companion_dialogues import SCENARIOS as COMPANION_SCENARIOS
from .preference_dialogues import EXPECTATIONS as PREFERENCE_EXPECTATIONS
from .preference_dialogues import PRODUCTS as PREFERENCE_PRODUCTS
from .preference_dialogues import SCENARIOS as PREFERENCE_SCENARIOS

SCENARIOS = {
    "weather_city_switch": [
        ("sanya", "今天去三亚旅行，先从我的衣橱搭一套，平底鞋。", False),
        ("auckland", "今天奥克兰天气如何？", False),
        ("new_zealand", "奥克兰我指的是新西兰的奥克兰。", False),
    ],
    "weather_to_wardrobe": [
        ("shanghai", "看看上海今天的天气。", False),
        ("followup", "如果你今天要走很多路，我可以把鞋子和层次再调得更舒服一点。", False),
    ],
    "wardrobe_local_change": [
        ("setup", "从我的衣橱搭一套日常装，不考虑天气。", False),
        ("shoes", "只把鞋子换成平底鞋，不穿高跟鞋，其他衣服都保留。", False),
    ],
    "text_only_then_chat": [
        ("setup", "只讲白衬衫、灰裤和平底鞋的穿法，不查衣橱和天气，不塞衣角。", False),
        ("followup", "保持这三件，穿法再简洁一点，不找商品。", False),
        ("chat", "先不聊穿搭了，今天好累，陪我说两句。", True),
    ],
    "empty_wardrobe": [("empty", "用我的衣橱搭一套通勤装，不考虑天气。", False)],
    "weather_failure": [("failed", "上海今天出门怎么穿？只给文字建议，不查衣橱。", False)],
    "ignore_weather": [("ignored", "帮我用衣橱搭一套日常装，不考虑天气。", False)],
    "provided_weather": [("provided", "今天晴天，15到20度，用我的衣橱搭一套日常装，按我说的天气，不用查。", False)],
    "persona_switch": [
        ("setup", "只讲女生白衬衫灰裤的穿法，不查衣橱和天气。", False),
        ("switch", "换个助理，但还是刚才女生那套衣服，不查衣橱和天气，穿法简单一点。", False),
    ],
}

EXPECTATIONS = {
    "weather_city_switch/sanya": {"inventory": True, "weather_city": "三亚市", "delivery": "outfit"},
    "weather_city_switch/auckland": {"city_contains": "奥克兰", "no_weather": True, "no_looks": True,
        "inventory": False, "delivery": "clarification", "forbid_text": ["三亚", "31度", "25度"],
        "must_text": ["奥克兰", "查不到"], "no_style": True},
    "weather_city_switch/new_zealand": {"city_contains": "奥克兰", "no_weather": True, "no_looks": True,
        "inventory": False, "delivery": "clarification", "forbid_text": ["三亚", "31度", "25度"],
        "must_text": ["奥克兰", "查不到"], "no_style": True},
    "weather_to_wardrobe/shanghai": {"weather_city": "上海市", "inventory": False, "no_looks": True},
    "weather_to_wardrobe/followup": {"inventory": True, "delivery": "outfit"},
    "wardrobe_local_change/setup": {"inventory": True, "delivery": "outfit", "no_weather_tools": True},
    "wardrobe_local_change/shoes": {"inventory": True, "delivery": "outfit", "freeze_except": ["shoes"],
        "task": {"no_heels": True}},
    "text_only_then_chat/setup": {"no_tools": True, "delivery": "advice"},
    "text_only_then_chat/followup": {"no_tools": True, "delivery": "advice"},
    "text_only_then_chat/chat": {"no_tools": True, "no_looks": True},
    "empty_wardrobe/empty": {"inventory": True, "delivery": "concept", "no_real_items": True, "allow_empty_looks": True},
    "weather_failure/failed": {"no_weather": True, "inventory": False,
        "forbid_text": ["20度", "15度", "天气晴朗", "今天多云"]},
    "ignore_weather/ignored": {"inventory": True, "no_weather_tools": True,
        "task": {"weather_policy": "ignored"}},
    "provided_weather/provided": {"inventory": True, "no_weather_tools": True,
        "task": {"weather_policy": "provided"}, "weather_source": "user"},
    "persona_switch/setup": {"no_tools": True, "task": {"gender": "女"}},
    "persona_switch/switch": {"no_tools": True, "task": {"gender": "女"}},
}

SCENARIOS["wardrobe_default"] = [
    ("ordinary", "帮我搭一套日常穿搭，不穿高跟鞋，不考虑天气。", False),
    ("consult_word", "咨询一下，白衬衫怎么搭裤子？不穿高跟鞋，不考虑天气。", False),
]
SCENARIOS["wardrobe_opt_out"] = [
    ("text", "不要输出衣柜内容，只给白衬衫灰裤平底鞋的文字穿法，不查天气。", False),
    ("resume", "现在从我的衣橱选一套实际衣服，不穿高跟鞋，不考虑天气。", False),
]
for turn in ["ordinary", "consult_word"]:
    EXPECTATIONS[f"wardrobe_default/{turn}"] = {"inventory": True, "delivery": "outfit", "no_weather_tools": True,
        "review_focus": "未明确排除衣橱，应实际选款；咨询一下不等于只要文字建议。"}
EXPECTATIONS["wardrobe_opt_out/text"] = {"no_tools": True, "delivery": "advice", "no_real_items": True}
EXPECTATIONS["wardrobe_opt_out/resume"] = {"inventory": True, "delivery": "outfit", "no_weather_tools": True,
    "review_focus": "本轮恢复衣橱选款，不能沿用前文文字限定。"}

SCENARIOS.update(PREFERENCE_SCENARIOS)
EXPECTATIONS.update(PREFERENCE_EXPECTATIONS)
SCENARIOS.update(COMPANION_SCENARIOS)
EXPECTATIONS.update(COMPANION_EXPECTATIONS)

PRODUCTS = [
    {"product_id": "101", "class_name": "上衣", "title": "白色长袖衬衫", "color": "白色", "material": "棉"},
    {"product_id": "102", "class_name": "裤子", "title": "灰色长裤", "color": "灰色", "material": "棉"},
    {"product_id": "103", "class_name": "鞋子", "title": "白色平底运动鞋", "color": "白色", "material": "皮革"},
    {"product_id": "104", "class_name": "鞋子", "title": "黑色平底乐福鞋", "color": "黑色", "material": "皮革"},
    {"product_id": "105", "class_name": "外套", "title": "米白色长袖薄外套", "color": "米白色", "material": "棉"},
]


class DialogueUpstream:
    def __init__(self, scenario):
        self.scenario, self.calls = scenario, []
        self.products = PREFERENCE_PRODUCTS if scenario in PREFERENCE_SCENARIOS else PRODUCTS
        if scenario == "preference_no_matching_style":
            self.products = [p for p in self.products if {"name": "复古"} not in p.get("styles", [])]

    async def identity(self):
        return "synthetic-persona-evaluation"

    async def get(self, path, params):
        self.calls.append(path)
        if path != "/api/user_product/quick_edit_list":
            raise AssertionError("Unexpected business endpoint")
        rows = [] if self.scenario == "empty_wardrobe" else [
            {**p, "user_product_id": p["product_id"]} for p in self.products]
        return {"list": rows, "pagination": {"total": len(rows)}}

    async def forecast(self, city):
        self.calls.append("forecast")
        if self.scenario == "weather_failure":
            raise StylistError("forecast_unavailable", "合成测试：天气查询失败")
        low, high = (25, 31) if city["city_name"] == "三亚市" else (15, 20)
        return {"list": [{"data_format": (today() + timedelta(days=i)).isoformat(),
            "temp_day": high, "temp_night": low, "condition_day": "多云", "condition_night": "阴"}
            for i in range(14)]}

    @asynccontextmanager
    async def mcp(self):
        yield self

    async def call(self, name, args):
        self.calls.append(name)
        if name == "city.resolve":
            catalog = {"上海": ("上海市", "上海市"), "上海市": ("上海市", "上海市"),
                       "三亚": ("三亚市", "海南省"), "三亚市": ("三亚市", "海南省")}
            city = catalog.get(args.get("name"))
            return {"status": "resolved" if city else "not_found", "truncated": False,
                    "matches": [{"city_name": city[0], "province_name": city[1]}] if city else []}
        if name == "product.resolve":
            keys = {x["product_id"] for x in args["items"] if x["source"] == "user"}
            return {"items": [{**p, "user_product_id": p["product_id"], "source": "user"}
                              for p in self.products if p["product_id"] in keys]}
        if name == "outfit.search-saved":
            return {"matches": []}
        if name == "weather.get" and self.scenario == "weather_failure":
            raise StylistError("forecast_unavailable", "合成测试：天气查询失败")
        raise AssertionError("Unexpected tool; no real business, image or fee operations are allowed")


def visible_text(reply):
    parts = [reply.message, *reply.warnings, *reply.follow_ups]
    for look in reply.looks:
        parts.extend([look.title, look.style_name, *look.pieces, *look.why, *look.how, *look.notes])
    return "\n".join(parts)


def check_reply(reply, expected, calls, model_calls=(), previous=None):
    errors, text = [], visible_text(reply)
    inventory = "/api/user_product/quick_edit_list" in calls
    if "inventory" in expected and inventory != expected["inventory"]:
        errors.append("inventory_access")
    weather_tools = {"city.resolve", "forecast", "weather.get"}
    if expected.get("no_tools") and calls:
        errors.append("unexpected_tools")
    if expected.get("no_weather_tools") and weather_tools.intersection(calls):
        errors.append("unexpected_weather_query")
    if expected.get("no_weather") and reply.weather is not None:
        errors.append("unexpected_weather")
    for field, key in [("city_name", "weather_city"), ("source", "weather_source")]:
        if key in expected and (reply.weather or {}).get(field) != expected[key]:
            errors.append(key)
    if "delivery" in expected and reply.delivery != expected["delivery"]:
        errors.append("delivery")
    if expected.get("no_looks") and reply.looks:
        errors.append("unexpected_looks")
    if expected.get("no_real_items") and any(look.items for look in reply.looks):
        errors.append("fabricated_items")
    if expected.get("city_contains") and expected["city_contains"] not in (reply.task.city or ""):
        errors.append("requested_city_lost")
    for field, value in expected.get("task", {}).items():
        if getattr(reply.task, field) != value:
            errors.append("task_" + field)
    for field, values in expected.get("task_contains", {}).items():
        if not set(values) <= set(getattr(reply.task, field)):
            errors.append("task_" + field + "_missing")
    if any(token in text for token in expected.get("forbid_text", [])):
        errors.append("stale_or_unsupported_claim")
    if any(token not in text for token in expected.get("must_text", [])):
        errors.append("missing_answer")
    if expected.get("no_style") and any(x["name"] == "style" for x in model_calls):
        errors.append("unsupported_city_reached_styling")
    if expected.get("freeze_except") and previous and previous.looks:
        frozen = {p.key for p in previous.looks[0].items if p.slot not in expected["freeze_except"]}
        retained = {p.key for p in reply.retained_items} if reply.delivery == "concept" else (
            {p.key for p in reply.looks[0].items} if reply.looks else set())
        if not frozen <= retained:
            errors.append("frozen_items_changed")
    if expected.get("must_change_slots") and previous and previous.looks and reply.delivery == "outfit":
        for slot in expected["must_change_slots"]:
            old = {p.key for p in previous.looks[0].items if p.slot == slot}
            for look in reply.looks:
                new = {p.key for p in look.items if p.slot == slot}
                if old and old == new:
                    errors.append("unchanged_replacement")
    if expected.get("no_internal_codes") and any(code in text for code in [
            "forecast_unavailable", "forecast_date_unavailable", "city_needs_selection", "inventory_read_failed", "saved_outfits_failed"]):
        errors.append("internal_error_code_visible")
    if not expected.get("technical_question") and any(token in text for token in
            ["接入", "支持范围", "接口", "数据源", "降级", "结构校验", "selected_keys", "use_inventory"]):
        errors.append("stiff_technical_language")
    if any(token in follow for follow in reply.follow_ups for token in ["我可以", "要不要我"]):
        errors.append("assistant_voice_followup")
    if expected.get("mentioned_zodiac") and expected["mentioned_zodiac"] not in visible_text(reply):
        errors.append("missing_expected_zodiac")
    if expected.get("selected_style"):
        garments = [p for look in reply.looks for p in look.items if p.slot in {"top", "bottom", "dress"}]
        if not garments or any(expected["selected_style"] not in p.styles for p in garments):
            errors.append("selected_items_ignore_style_preference")
    if any(p.product_id in expected.get("forbid_item_ids", []) for look in reply.looks for p in look.items):
        errors.append("selected_forbidden_item")
    return errors


class PersonaReview(Model):
    persona_fit: int = Field(ge=1, le=5)
    naturalness: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)
    factuality: int = Field(ge=1, le=5)
    evidence: str = Field(min_length=1)
    reason: str = Field(min_length=1)


def review_status(review, text):
    if not review.evidence.strip() or review.evidence not in text:
        return "invalid_evidence"
    return "passed" if min(review.persona_fit, review.naturalness, review.relevance, review.factuality) >= 4 else "failed"
