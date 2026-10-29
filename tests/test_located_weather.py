import json
from datetime import timedelta

import pytest

from scripts.exploratory_dialogues import ExploratoryUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import Change, ChatRequest, CitySelection, Draft, Plan, Reply, Task, TripStop
from stylist.store import Store
from stylist.weather import today


@pytest.mark.parametrize("persona", ["male_calm_v1", "female_warm_v1"])
@pytest.mark.parametrize("explicit", [None, "from_location", "北京", "奥克兰", "route"])
@pytest.mark.asyncio
async def test_located_weather_defaults_to_current_city_but_respects_explicit_places(tmp_path, persona, explicit):
    owner, store = "synthetic-persona-evaluation", Store(str(tmp_path / "state.db"))
    setup = ChatRequest(message="旧行程", request_id="located-weather-setup")
    cid, claim, state, _ = store.reserve(owner, setup)
    state.task = Task(city="三亚", itinerary=[TripStop(city_name="三亚"), TripStop(city_name="北京")],
        event_date=today() + timedelta(days=30), weather_policy="ignored", temp_min=25, temp_max=31,
        weather_description="旧行程天气")
    store.finish(owner, setup, claim, state, Reply(conversation_id=cid, version=1, mode="consult",
        delivery="advice", message="旧行程", task=state.task))

    class Model:
        async def generate(self, name, payload, result_type):
            if name == "plan":
                assert payload["selected_location"] == {"city_name": "上海市", "province_name": "上海市"}
                changes = {}
                if explicit == "route":
                    changes["itinerary"] = Change(value=[{"city_name": "北京"}, {"city_name": "三亚"}], evidence="北京和三亚")
                elif explicit == "from_location":
                    changes["city"] = Change(value="上海市", evidence="")
                elif explicit:
                    changes["city"] = Change(value=explicit, evidence=explicit)
                return Plan(mode="consult", weather_only=True, changes=changes)
            assert payload["task"]["temp_min"] is None and payload["task"]["weather_description"] == ""
            return Draft(message="已查本轮地点的天气。")

    message = "今天天气怎么样？" if explicit in {None, "from_location"} else ("今天北京和三亚的天气？" if explicit == "route" else f"今天{explicit}天气怎么样？")
    upstream = ExploratoryUpstream("located_weather")
    result = await Stylist(Settings(), store, Model()).chat(upstream, ChatRequest(message=message,
        request_id="located-weather-query", conversation_id=cid, expected_version=1, assistant_persona=persona,
        location=CitySelection(city_name="上海市", province_name="上海市"), weather_policy="ignored"))
    assert result.weather_only and not result.looks and result.task.weather_policy == "auto"
    assert result.task.event_date == today()
    forecasts = [event["city"] for event in upstream.events if event["tool"] == "forecast"]
    if explicit == "奥克兰":
        assert result.delivery == "clarification" and result.weather is None and not forecasts
        assert "奥克兰" in result.message and "上海" not in result.message
    elif explicit == "route":
        assert forecasts == ["北京市", "三亚市"]
        assert result.weather["source"] == "itinerary_forecast"
    else:
        city = "北京市" if explicit == "北京" else "上海市"
        assert forecasts == [city] and result.weather["city_name"] == city
        assert result.task.itinerary == []
        assert result.weather["requested_dates"] == [today().isoformat()]
    assert "/api/user_product/quick_edit_list" not in upstream.calls


@pytest.mark.asyncio
async def test_limit_refusal_with_a_location_keeps_existing_trip_unchanged(tmp_path):
    owner, store = "synthetic-persona-evaluation", Store(str(tmp_path / "state.db"))
    setup = ChatRequest(message="旧行程", request_id="located-limit-setup")
    cid, claim, state, _ = store.reserve(owner, setup)
    state.task = Task(city="三亚", itinerary=[TripStop(city_name="三亚")], event_date=today() + timedelta(days=30))
    old_task = state.task.model_copy(deep=True)
    store.finish(owner, setup, claim, state, Reply(conversation_id=cid, version=1, mode="consult", delivery="advice", message="行程", task=state.task))

    class Model:
        async def generate(self, name, *args):
            assert name == "plan"
            return Plan(mode="consult", location_limit_exceeded=True)

    reply = await Stylist(Settings(), store, Model()).chat(ExploratoryUpstream("limit"), ChatRequest(
        message="查11个地区天气", request_id="located-limit-query", conversation_id=cid, expected_version=1,
        location=CitySelection(city_name="上海市", province_name="上海市")))
    assert reply.delivery == "clarification" and reply.task == old_task
    with store.connection() as conn:
        stored = json.loads(conn.execute("SELECT state_json FROM stylist_sessions WHERE id=?", (cid,)).fetchone()[0])
    assert stored["task"] == old_task.model_dump(mode="json")
