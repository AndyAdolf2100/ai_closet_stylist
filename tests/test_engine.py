from contextlib import asynccontextmanager

import pytest

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import Change, ChatRequest, Draft, Look, LookDraft, Plan, Product, Reply, Slot, Task
from stylist.store import Store


class FakeModel:
    def __init__(self, plan, draft):
        self.plan, self.draft, self.inputs = plan, draft, []

    async def generate(self, name, payload, result_type):
        self.inputs.append((name, payload))
        return self.plan if name == "plan" else self.draft


@pytest.mark.asyncio
async def test_consultation_followup_never_enters_closet_and_keeps_scene(tmp_path):
    class Upstream:
        async def identity(self):
            return "1"
        @asynccontextmanager
        async def mcp(self):
            pytest.fail("Pure advice must not open tools")
            yield
    store = Store(str(tmp_path / "state.db"))
    original = ChatRequest(message="美术馆三件穿法", request_id="advice-first")
    cid, claim, state, _ = store.reserve("1", original)
    state.task = Task(scene="周末美术馆", owned_descriptions=["海军蓝针织衫", "米白裤", "白色平底鞋"])
    state.mode = "consult"
    store.finish("1", original, claim, state, Reply(conversation_id=cid, version=1, mode="consult",
                 delivery="advice", message="两种穿法", task=state.task))
    model = FakeModel(Plan(mode="consult", changes={"preferences": Change(value=["不塞衣角"], evidence="不塞衣角")}),
                      Draft(message="保持这三件，调整穿法。", looks=[LookDraft(title="自然垂放", pieces=["海军蓝针织衫"],
                            why=["轮廓放松"], how=["下摆自然垂放"])]))
    result = await Stylist(Settings(), store, model).chat(Upstream(), ChatRequest(
        message="厚针织衫不塞衣角，保持三件。", request_id="advice-followup", conversation_id=cid, expected_version=1))
    assert result.mode == "consult" and result.delivery == "advice"
    assert result.task.scene == "周末美术馆" and len(result.task.owned_descriptions) == 3
    assert result.task.preferences == ["不塞衣角"]
    assert model.inputs[1][1]["candidates"] == []


@pytest.mark.asyncio
async def test_failed_shoe_replacement_preserves_real_outfit(tmp_path):
    top = Product(source="user", product_id="1", class_name="上衣", slot=Slot.TOP)
    bottom = Product(source="user", product_id="2", class_name="裤子", slot=Slot.BOTTOM)
    shoe = Product(source="user", product_id="3", class_name="鞋子", title="高跟鞋", slot=Slot.SHOES)
    current = Look(title="原通勤装", items=[top, bottom, shoe])
    class MCP:
        async def call(self, name, args):
            assert name == "product.resolve"
            rows = []
            for ref in args["items"]:
                p = {"1": top, "2": bottom, "3": shoe}[ref["product_id"]]
                rows.append({"source": p.source, "product_id": p.product_id, "class_name": p.class_name, "title": p.title})
            return {"items": rows}
    class Upstream:
        async def identity(self):
            return "1"
        async def get(self, *args):
            return {"list": [{"user_product_id": int(p.product_id)} for p in current.items], "pagination": {"total": 3}}
        @asynccontextmanager
        async def mcp(self):
            yield MCP()
    store = Store(str(tmp_path / "state.db"))
    original = ChatRequest(message="通勤装", request_id="outfit-first")
    cid, claim, state, _ = store.reserve("1", original)
    state.looks = [current]
    state.task.weather_policy = "ignored"
    store.finish("1", original, claim, state, Reply(conversation_id=cid, version=1, mode="recommend",
                 delivery="outfit", message="原搭配", task=state.task, looks=[current]))
    model = FakeModel(Plan(mode="modify", replace_slots=[Slot.SHOES], changes={
        "no_heels": Change(value=True, evidence="不穿高跟鞋")}),
        Draft(message="本次未找到可确认平底的替换鞋，原搭配未变。", looks=[LookDraft(
            title="鞋型参考", pieces=["包脚平底鞋"], why=["重视步行舒适"], how=["用自己的舒适平底鞋替代"])]))
    result = await Stylist(Settings(), store, model).chat(Upstream(), ChatRequest(
        message="不穿高跟鞋，只换鞋。", request_id="outfit-replace", conversation_id=cid, expected_version=1))
    assert result.delivery == "concept" and not result.looks[0].items
    with store.connection() as conn:
        from stylist.models import SessionState
        saved = SessionState.model_validate_json(conn.execute("SELECT state_json FROM stylist_sessions WHERE id=?", (cid,)).fetchone()[0])
    assert saved.looks[0].items == current.items
    assert saved.task.no_heels


@pytest.mark.asyncio
async def test_weekly_text_plan_still_checks_weather_and_respects_explicit_opt_out(tmp_path):
    class Upstream:
        async def identity(self):
            return "1"
        @asynccontextmanager
        async def mcp(self):
            pytest.fail("Text planning must not read products")
            yield
    model = FakeModel(Plan(mode="weekly", use_inventory=False, weather_scope="week"),
                      Draft(message="按每天预报安排。"))
    engine = Stylist(Settings(), Store(str(tmp_path / "weather.db")), model)
    calls = []
    class Weather:
        async def forecast(self, upstream, city, province, scope, start):
            calls.append((city, scope))
            return {"city_name": city, "province_name": province, "days": [{"date": start.isoformat(), "temp_min": 2, "temp_max": 8,
                              "condition_day": "雪", "condition_night": "雾"}], "warnings": []}
    engine.weather = Weather()
    from stylist.models import CitySelection
    result = await engine.chat(Upstream(), ChatRequest(message="本周只给文字方案", request_id="weekly-weather-1",
        location=CitySelection(city_name="上海市")))
    assert calls == [("上海市", "week")] and result.weather["days"][0]["condition_day"] == "雪"
    assert model.inputs[-1][1]["candidates"] == []
    calls.clear()
    result = await engine.chat(Upstream(), ChatRequest(message="本周只给文字方案", request_id="weekly-weather-2",
        location=CitySelection(city_name="上海市"), weather_policy="ignored"))
    assert not calls and result.weather is None
