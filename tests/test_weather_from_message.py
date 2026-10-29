from contextlib import asynccontextmanager

import pytest

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import Change, ChatRequest, CitySelection, Draft, Plan, Reply, SessionState, Task
from stylist.policy import interpret_task
from stylist.store import Store


@pytest.mark.parametrize("old_policy", ["auto", "ignored", "provided"])
@pytest.mark.parametrize("current_policy", [None, "ignored", "provided"])
@pytest.mark.asyncio
async def test_weather_policy_is_current_turn_only(old_policy, current_policy):
    state = SessionState(task=Task(city="上海", weather_policy=old_policy,
        temp_min=28, temp_max=32, weather_description="旧天气", preferences=["不塞衣角"]))
    message = "只换鞋，其他保留"
    changes = {}
    if current_policy == "ignored":
        message += "，不考虑天气"
        changes["weather_policy"] = Change(value="ignored", evidence="不考虑天气")
    elif current_policy == "provided":
        message += "，今天18度"
        changes = {"weather_policy": Change(value="provided", evidence="今天18度"),
                   "temp_max": Change(value=18, evidence="18度")}

    class Model:
        async def generate(self, *args):
            return Plan(mode="recommend", changes=changes)

    _, task = await interpret_task(Model(), {}, state, message)
    assert task.weather_policy == (current_policy or "auto")
    assert task.temp_min is None  # A partially supplied forecast must not inherit old temperature.
    assert task.temp_max == (18 if current_policy == "provided" else None)
    assert task.weather_description == "" and task.preferences == ["不塞衣角"]
    assert state.task.temp_min == 28 and state.task.weather_policy == old_policy


@pytest.mark.parametrize("legacy_policy,current_policy", [("ignored", None), ("provided", None), ("auto", "ignored")])
@pytest.mark.parametrize("persona", ["male_calm_v1", "female_warm_v1"])
@pytest.mark.asyncio
async def test_legacy_select_value_cannot_override_current_message(tmp_path, legacy_policy, current_policy, persona):
    store = Store(str(tmp_path / "state.db"))
    initial = ChatRequest(message="不考虑天气", request_id="weather-message-setup")
    cid, claim, state, _ = store.reserve("synthetic-weather-owner", initial)
    state.task = Task(city="上海", weather_policy="ignored", temp_min=30, temp_max=35)
    store.finish("synthetic-weather-owner", initial, claim, state, Reply(conversation_id=cid, version=1,
        mode="consult", delivery="advice", message="上轮忽略天气。", task=state.task))
    calls = []

    class Upstream:
        async def identity(self):
            return "synthetic-weather-owner"

        @asynccontextmanager
        async def mcp(self):
            pytest.fail("Text advice should not read inventory")
            yield

    class Weather:
        async def forecast(self, upstream, city, province, scope, start):
            calls.append(city)
            return {"city_name": city, "province_name": province, "days": [{"date": start.isoformat(), "temp_min": 10, "temp_max": 16,
                    "condition_day": "阴", "condition_night": "多云"}], "warnings": []}

    class Model:
        async def generate(self, name, payload, result_type):
            if name == "plan":
                return Plan(mode="consult", use_inventory=False, weather_scope="day", changes={
                    "weather_policy": Change(value="ignored", evidence="不考虑天气")} if current_policy else {})
            assert payload["task"]["weather_policy"] == (current_policy or "auto")
            return Draft(message="按这次条件整理穿法。")

    engine = Stylist(Settings(), store, Model())
    engine.weather = Weather()
    reply = await engine.chat(Upstream(), ChatRequest(
        message="今天上班怎么穿，只讲文字" + ("，不考虑天气" if current_policy else ""),
        request_id="weather-message-followup", conversation_id=cid, expected_version=1,
        assistant_persona=persona, location=CitySelection(city_name="上海市"), weather_policy=legacy_policy))
    assert reply.task.weather_policy == (current_policy or "auto")
    assert calls == ([] if current_policy == "ignored" else ["上海市"])
    assert (reply.weather is None) == (current_policy == "ignored")


@pytest.mark.asyncio
async def test_chat_preserves_task_and_does_not_query_weather():
    state = SessionState(task=Task(weather_policy="ignored", temp_min=20))
    class Model:
        async def generate(self, *args):
            return Plan(mode="consult", conversation_only=True)
    _, task = await interpret_task(Model(), {}, state, "你好")
    assert task == state.task
