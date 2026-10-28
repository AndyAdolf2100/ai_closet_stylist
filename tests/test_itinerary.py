from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from pydantic import ValidationError

from scripts.dialogue_validation import PRODUCTS
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import AuthenticationExpired
from stylist.models import (
    Change,
    ChatRequest,
    CitySelection,
    Draft,
    LookDraft,
    Plan,
    SessionState,
    Task,
    TripStop,
)
from stylist.policy import interpret_task, merge_task
from stylist.store import Store
from stylist.weather import WeatherService, apply_forecast, today

STOPS = [{"city_name": "上海"}, {"city_name": "三亚"}]


class RouteUpstream:
    def __init__(self):
        self.events = []

    async def identity(self):
        return "synthetic-route-user"

    @asynccontextmanager
    async def mcp(self):
        yield self

    async def call(self, name, args):
        self.events.append((name, args))
        if name == "city.resolve":
            city = {"上海": ("上海市", "上海市"), "三亚": ("三亚市", "海南省")}.get(args["name"])
            return {"status": "resolved" if city else "not_found", "truncated": False,
                    "matches": [{"city_name": city[0], "province_name": city[1]}] if city else []}
        if name == "product.resolve":
            return {"items": [{**p, "source": "user", "user_product_id": p["product_id"]} for p in PRODUCTS]}
        if name == "outfit.search-saved":
            return {"matches": []}
        pytest.fail("Unexpected route tool: " + name)

    async def get(self, path, args):
        self.events.append((path, args))
        assert path == "/api/user_product/quick_edit_list"
        return {"list": [{**p, "user_product_id": p["product_id"]} for p in PRODUCTS],
                "pagination": {"total": len(PRODUCTS)}}

    async def forecast(self, city):
        self.events.append(("forecast", city))
        cold = city["city_name"] == "上海市"
        return {"list": [{"data_format": (today() + timedelta(days=i)).isoformat(),
                         "temp_day": (14 if cold else 31) + i, "temp_night": (8 if cold else 25) + i,
                         "condition_day": "小雨" if cold else "晴", "condition_night": "阴"}
                        for i in range(7)]}


def route_plan(mode="recommend"):
    return Plan(mode=mode, use_inventory=mode == "recommend", weather_scope="day", changes={
        "itinerary": Change(value=STOPS, evidence=["上海", "三亚"])})


def test_trip_is_structured_and_a_new_single_city_clears_the_old_route():
    task = merge_task(SessionState(), route_plan(), "今天上海出发去三亚")
    assert task.city == "上海" and [p.city_name for p in task.itinerary] == ["上海", "三亚"]
    changed = merge_task(SessionState(task=task), Plan(mode="consult", changes={
        "city": Change(value="杭州", evidence="杭州")}), "改为只在杭州")
    assert changed.city == "杭州" and changed.itinerary == []
    with pytest.raises(ValidationError):
        TripStop(city_name="上海/三亚")
    with pytest.raises(ValidationError):
        Task(itinerary=[TripStop(city_name="上海")] * 11)


@pytest.mark.asyncio
async def test_joined_city_is_repaired_before_any_tool_call():
    class Model:
        def __init__(self):
            self.inputs = []
        async def generate(self, name, payload, result_type):
            self.inputs.append(payload)
            if len(self.inputs) == 1:
                return Plan(mode="recommend", changes={"city": Change(value="上海/三亚", evidence="上海到三亚")})
            assert "itinerary" in payload["task_validation_errors"][0]["msg"]
            return route_plan()
    model = Model()
    _, task = await interpret_task(model, {}, SessionState(), "上海到三亚")
    assert len(model.inputs) == 2 and task.city == "上海" and len(task.itinerary) == 2


@pytest.mark.asyncio
async def test_city_and_date_evidence_remains_separate_and_filtering_covers_both_stops():
    upstream = RouteUpstream()
    stops = [TripStop(city_name="上海"), TripStop(city_name="三亚", event_date=today() + timedelta(days=1))]
    report = await WeatherService().forecast_itinerary(upstream, stops, start=today())
    assert report["complete"]
    assert [loc["city_name"] for loc in report["locations"]] == ["上海市", "三亚市"]
    assert [loc["forecast"]["days"][0]["date"] for loc in report["locations"]] == [
        today().isoformat(), (today() + timedelta(days=1)).isoformat()]
    effective = apply_forecast(Task(), report)
    assert (effective.temp_min, effective.temp_max) == (8, 32)
    assert "上海市" in effective.weather_description and "三亚市" in effective.weather_description
    assert "小雨" in effective.weather_description


@pytest.mark.asyncio
async def test_same_city_on_different_days_reuses_rows_without_reusing_the_wrong_date():
    upstream = RouteUpstream()
    report = await WeatherService().forecast_itinerary(upstream, [
        TripStop(city_name="上海", event_date=today()),
        TripStop(city_name="上海", event_date=today() + timedelta(days=2))])
    assert [loc["forecast"]["days"][0]["date"] for loc in report["locations"]] == [
        today().isoformat(), (today() + timedelta(days=2)).isoformat()]


@pytest.mark.asyncio
async def test_one_unsupported_stop_never_receives_the_other_city_weather():
    upstream = RouteUpstream()
    report = await WeatherService().forecast_itinerary(upstream, [TripStop(city_name="上海"), TripStop(city_name="奥克兰")])
    assert not report["complete"]
    assert report["locations"][0]["forecast"]["city_name"] == "上海市"
    assert report["locations"][1]["forecast"] is None
    assert report["locations"][1]["reason"] == "weather_city_unsupported"


@pytest.mark.asyncio
async def test_route_auth_failure_is_not_reported_as_a_missing_city():
    class Expired(RouteUpstream):
        async def call(self, *args):
            raise AuthenticationExpired()
    with pytest.raises(AuthenticationExpired):
        await WeatherService().forecast_itinerary(Expired(), [TripStop(city_name="上海"), TripStop(city_name="三亚")])


@pytest.mark.parametrize("persona", ["male_calm_v1", "female_warm_v1"])
@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.asyncio
async def test_engine_queries_route_before_wardrobe_and_delivers_per_city_evidence(tmp_path, persona, partial):
    class Model:
        def __init__(self):
            self.style_payload = None
        async def generate(self, name, payload, result_type):
            if name == "plan":
                plan = route_plan()
                if partial:
                    plan.changes["itinerary"] = Change(value=[{"city_name": "上海"}, {"city_name": "奥克兰"}],
                                                       evidence=["上海", "奥克兰"])
                return plan
            self.style_payload = payload
            return Draft(message="出发时穿外套，抵达后按当地体感穿脱。", looks=[LookDraft(title="一套应付两地",
                selected_keys=["user:101", "user:102", "user:103", "user:105"], why=["外层方便穿脱"],
                how=["按两地各自的预报安排外层"] )])
    upstream, model = RouteUpstream(), Model()
    reply = await Stylist(Settings(), Store(str(tmp_path / "state.db")), model).chat(upstream, ChatRequest(
        message="上海出发到" + ("奥克兰" if partial else "三亚") + "，帮我搭一套",
        request_id="route-engine-test", assistant_persona=persona,
        location=CitySelection(city_name="北京", province_name="北京市")))
    assert reply.delivery == "outfit" and len(reply.looks) == 1
    cities = [args["name"] for name, args in upstream.events if name == "city.resolve"]
    assert cities == ["上海", "奥克兰" if partial else "三亚"]
    assert "北京" not in cities and not any("/" in city for city in cities)
    locations = model.style_payload["weather"]["locations"]
    assert len(locations) == 2 and locations[0]["forecast"]["city_name"] == "上海市"
    assert (locations[1]["forecast"] is None) == partial
    if partial:
        assert "奥克兰" in reply.warnings[-1] and "查不到" in reply.warnings[-1]
    else:
        assert locations[1]["forecast"]["city_name"] == "三亚市"
    assert any(name == "/api/user_product/quick_edit_list" for name, _ in upstream.events)


@pytest.mark.parametrize("policy", ["ignored", "provided"])
@pytest.mark.asyncio
async def test_route_still_respects_no_weather_query_policies(tmp_path, policy):
    class Model:
        async def generate(self, name, payload, result_type):
            return route_plan("consult") if name == "plan" else Draft(message="按你给的条件说穿法。")
    upstream = RouteUpstream()
    result = await Stylist(Settings(), Store(str(tmp_path / "state.db")), Model()).chat(upstream, ChatRequest(
        message="上海到三亚，只讲穿法", request_id="route-no-weather", weather_policy=policy))
    assert not upstream.events
    assert result.weather is None if policy == "ignored" else result.weather["source"] == "user"


@pytest.mark.parametrize("count", [2, 5, 10])
@pytest.mark.asyncio
async def test_weather_only_returns_every_region_without_outfits(tmp_path, count):
    class Upstream(RouteUpstream):
        async def call(self, name, args):
            self.events.append((name, args))
            assert name == "city.resolve"
            return {"status": "resolved", "truncated": False,
                    "matches": [{"city_name": args["name"], "province_name": "测试省"}]}

    class Model:
        async def generate(self, name, payload, result_type):
            if name == "plan":
                return Plan(mode="recommend", weather_only=True, use_inventory=True, changes={
                    "itinerary": Change(value=[{"city_name": f"地区{i}"} for i in range(count)], evidence="查天气")})
            return Draft(message="逐地天气。", follow_ups=["帮我搭衣服"], looks=[LookDraft(
                title="不应出现", selected_keys=[], why=["示例"], how=["示例"])])

    upstream = Upstream()
    result = await Stylist(Settings(), Store(str(tmp_path / "state.db")), Model()).chat(upstream, ChatRequest(
        message="查天气", request_id="weather-count", weather_policy="ignored", confirm_plan=True))
    assert result.weather_only and not result.looks and not result.follow_ups
    assert len(result.weather["locations"]) == count
    assert all(p["status"] == "ok" for p in result.weather["locations"])
    assert len([e for e in upstream.events if e[0] == "forecast"]) == count
    assert not any(e[0].startswith("/api/") for e in upstream.events)


@pytest.mark.parametrize("persona", ["male_calm_v1", "female_warm_v1"])
@pytest.mark.parametrize("flag", [False, True])
@pytest.mark.asyncio
async def test_more_than_ten_stops_responds_in_persona_without_queries(tmp_path, persona, flag):
    class Model:
        async def generate(self, name, payload, result_type):
            assert name == "plan"
            return Plan(mode="consult", weather_only=True, location_limit_exceeded=flag, changes={} if flag else {
                "itinerary": Change(value=[{"city_name": f"地区{i}"} for i in range(11)], evidence="查11个地区")})

    upstream = RouteUpstream()
    result = await Stylist(Settings(), Store(str(tmp_path / "state.db")), Model()).chat(upstream, ChatRequest(
        message="查11个地区", request_id="too-many", assistant_persona=persona))
    assert result.delivery == "clarification" and result.weather_only
    assert "超过10个" in result.message and "先" in result.message
    assert not upstream.events and result.weather is None and not result.looks


@pytest.mark.asyncio
async def test_weather_service_rejects_more_than_ten_before_querying():
    from stylist.errors import StylistError

    upstream = RouteUpstream()
    with pytest.raises(StylistError, match="weather_location_limit"):
        await WeatherService().forecast_itinerary(upstream, [TripStop(city_name="上海")] * 11)
    assert not upstream.events


@pytest.mark.asyncio
async def test_one_region_week_is_seven_days_not_seven_regions(tmp_path):
    class Model:
        async def generate(self, name, payload, result_type):
            if name == "plan":
                return Plan(mode="consult", weather_only=True, weather_scope="next7", changes={
                    "city": Change(value="上海", evidence="上海")})
            return Draft(message="上海这一周的天气。")

    upstream = RouteUpstream()
    result = await Stylist(Settings(), Store(str(tmp_path / "state.db")), Model()).chat(upstream, ChatRequest(
        message="上海未来七天天气", request_id="week-weather", weather_policy="ignored"))
    assert result.weather_only and len(result.weather["days"]) == 7
    assert len([e for e in upstream.events if e[0] == "forecast"]) == 1
