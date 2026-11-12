from contextlib import asynccontextmanager

import pytest

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import Change, ChatRequest, Draft, Look, LookDraft, Plan, Product, Reply, Slot, Task
from stylist.store import Store
from scripts.outfit_recall_dialogues import CASES as RECALL_CASES


class FakeModel:
    def __init__(self, plan, draft):
        self.plan, self.draft, self.inputs = plan, draft, []

    async def generate(self, name, payload, result_type):
        self.inputs.append((name, payload))
        return self.plan if name == "plan" else self.draft


@pytest.mark.parametrize("persona,expected", [
    ("male_calm_v1", "奥克兰的天气，我暂时还查不到。"),
    ("female_warm_v1", "奥克兰的天气，我这边暂时还查不到呢。"),
    (None, "奥克兰的天气，我这边暂时还查不到呢。"),
])
@pytest.mark.parametrize("mode", ["consult", "recommend"])
@pytest.mark.asyncio
async def test_unsupported_city_replies_in_persona_without_reusing_old_city_weather(tmp_path, persona, expected, mode):
    from stylist.models import CitySelection

    calls = []
    class Upstream:
        async def identity(self):
            return "1"
        @asynccontextmanager
        async def mcp(self):
            class MCP:
                async def call(self, name, args):
                    calls.append(name)
                    assert name == "city.resolve"
                    assert args == {"name": "奥克兰"}
                    return {"status": "not_found", "matches": [], "truncated": False}
            yield MCP()
        async def get(self, *args):
            pytest.fail("Unsupported cities must not proceed to wardrobe retrieval")

    store = Store(str(tmp_path / "state.db"))
    original = ChatRequest(message="去三亚旅行", request_id="sanya-weather-first")
    cid, claim, state, _ = store.reserve("1", original)
    state.task = Task(city="三亚", temp_min=25, temp_max=31, weather_description="多云")
    state.looks = [Look(title="三亚旅行", pieces=["短袖"], why=["适合旅行"], how=["按体感穿脱"])]
    state.messages = [{"role": "assistant", "content": "三亚今天多云，25—31度，推荐两套旅行装。"}]
    store.finish("1", original, claim, state, Reply(conversation_id=cid, version=1,
        mode="recommend", delivery="advice", message="三亚天气", task=state.task, looks=state.looks))
    model = FakeModel(Plan(mode=mode, use_inventory=mode == "recommend", weather_scope="day",
        changes={"city": Change(value="奥克兰", evidence="奥克兰")}),
        Draft(message="三亚今天多云，25—31度。"))
    reply = await Stylist(Settings(), store, model).chat(Upstream(), ChatRequest(
        message="今天奥克兰天气如何", conversation_id=cid, expected_version=1, request_id="auckland-weather",
        assistant_persona=persona, location=CitySelection(city_name="三亚", province_name="海南省")))
    assert reply.message == expected and reply.delivery == "clarification"
    assert reply.weather is None and reply.looks == [] and reply.follow_ups == []
    assert reply.task.city == "奥克兰" and reply.task.temp_min is None and reply.task.temp_max is None
    assert reply.task.weather_description == ""
    assert calls == ["city.resolve"]
    assert [name for name, _ in model.inputs] == ["plan"]


@pytest.mark.asyncio
async def test_weather_advice_followup_can_select_real_wardrobe_without_previous_products(tmp_path):
    rows = [
        {"user_product_id": 1, "class_name": "上衣", "title": "长袖T恤"},
        {"user_product_id": 2, "class_name": "裤子", "title": "休闲长裤"},
        {"user_product_id": 3, "class_name": "鞋子", "title": "平底运动鞋"},
    ]
    calls = []

    class MCP:
        async def call(self, name, args):
            calls.append(name)
            if name == "outfit.search-saved":
                return {"matches": []}
            assert name == "product.resolve"
            return {"items": [{**row, "source": "user", "product_id": str(row["user_product_id"])}
                              for row in rows]}

    class Upstream:
        async def identity(self):
            return "1"

        async def get(self, path, params):
            calls.append(path)
            assert path == "/api/user_product/quick_edit_list"
            return {"list": rows, "pagination": {"total": 3}}

        @asynccontextmanager
        async def mcp(self):
            yield MCP()

    store = Store(str(tmp_path / "state.db"))
    original = ChatRequest(message="看看上海的天气", request_id="weather-advice-first")
    cid, claim, state, _ = store.reserve("1", original)
    state.mode = "consult"
    state.task = Task(city="上海", weather_policy="ignored")
    state.looks = [Look(title="文字参考", pieces=["长袖T恤", "长裤"],
                        why=["方便活动"], how=["按体感加减外层"])]
    store.finish("1", original, claim, state, Reply(conversation_id=cid, version=1, mode="consult",
                 delivery="advice", message="天气穿法参考", task=state.task, looks=state.looks))
    model = FakeModel(Plan(mode="recommend", use_inventory=True), Draft(
        message="从衣橱中选这套。", looks=[LookDraft(title="方便走路的一套",
        selected_keys=["user:1", "user:2", "user:3"], why=["鞋型适合日常活动"],
        how=["长袖T恤配长裤和运动鞋"])]))
    engine = Stylist(Settings(), store, model)
    class Weather:
        async def forecast(self, upstream, city, province, scope, start):
            calls.append("forecast")
            return {"city_name": city, "province_name": province, "days": [], "warnings": []}
    engine.weather = Weather()
    result = await engine.chat(Upstream(), ChatRequest(
        message="鞋子和层次再调得舒服一点", request_id="weather-outfit-followup",
        conversation_id=cid, expected_version=1))
    assert model.inputs[0][1]["current_mode"] == "consult"
    assert "forecast" in calls and result.task.weather_policy == "auto"
    assert "/api/user_product/quick_edit_list" in calls and "product.resolve" in calls
    assert result.delivery == "outfit"
    assert [p.key for p in result.looks[0].items] == ["user:1", "user:2", "user:3"]
    assert all(p.source == "user" for p in result.looks[0].items)


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
        message="厚针织衫不塞衣角，保持三件，不查衣橱，只重新说穿法。", request_id="advice-followup", conversation_id=cid, expected_version=1))
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
    assert {p.key for p in result.retained_items} == {top.key, bottom.key}
    assert shoe.key not in {p.key for p in result.retained_items}
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
    model.plan.changes["weather_policy"] = Change(value="ignored", evidence="不考虑天气")
    result = await engine.chat(Upstream(), ChatRequest(message="本周只给文字方案，不考虑天气", request_id="weekly-weather-2",
        location=CitySelection(city_name="上海市"), weather_policy="ignored"))
    assert not calls and result.weather is None


@pytest.mark.asyncio
@pytest.mark.parametrize('message,expected', RECALL_CASES)
@pytest.mark.parametrize('single_round', [True, False])
async def test_recall_original_card_without_retrieval_or_generation(tmp_path, message, expected, single_round):
    class Upstream:
        async def identity(self):
            return '1'
        @asynccontextmanager
        async def mcp(self):
            raise AssertionError('Recall must not retrieve wardrobe or weather')
            yield
        async def get(self, *args):
            pytest.fail('Recall must not query business inventory')

    store = Store(str(tmp_path / 'recall.db'))
    cid = None
    originals = [Look(title=f'原搭配{i}', pieces=[f'单品{i}'], how=['自然垂放']) for i in range(1, 6)]
    rounds = [originals] if single_round else [[look] for look in originals]
    for version, looks in enumerate(rounds, 1):
        title = '生成搭配' if version == 1 else '基于刚才那套再生成一套'
        request = ChatRequest(message=title, request_id=f'original-{version}',
                              conversation_id=cid, expected_version=version - 1)
        cid, claim, state, _ = store.reserve('1', request)
        state.looks = looks
        store.finish('1', request, claim, state, Reply(conversation_id=cid, version=version,
                     mode='recommend', delivery='outfit', message=title, task=Task(), looks=state.looks))
    if message == '输出一下':
        follow = ChatRequest(message='我刚才第一套搭配是啥来着', request_id='follow-recall-text',conversation_id=cid,expected_version=version)
        _,claim,state,_=store.reserve('1',follow)
        version+=1
        store.finish('1',follow,claim,state,Reply(conversation_id=cid,version=version,mode='consult',delivery='advice',message='第一套是原搭配1。',task=Task(),conversation_only=True))
    model = FakeModel(Plan(mode='consult', recall_outfit_numbers=expected, recall_evidence=message), Draft(message='不应调用'))
    reply = await Stylist(Settings(), store, model).chat(Upstream(), ChatRequest(
        message=message, request_id='recall-first', conversation_id=cid, expected_version=version))
    assert reply.historical_outfit_replay
    assert reply.message == ""
    assert reply.follow_ups == []
    assert reply.weather is None
    assert [look.model_dump() for look in reply.looks] == [originals[number - 1].model_dump() for number in expected]
    assert reply.looks[0].how == ['自然垂放']
    assert [name for name, _ in model.inputs] == ['plan']
    assert [row['outfit_number'] for row in model.inputs[0][1]['outfit_history']] == [1, 2, 3, 4, 5]
    from stylist.outfit_history import outfit_catalog
    assert len(outfit_catalog(store.history('1', cid)['messages'])) == 5


def test_latest_library_intent_survives_conversation_only_flag():
    import json
    from stylist.engine import last_business_intent
    for flag,expected in [('saved_outfit_search','saved_outfit_search'),('product_search','product_search'),('historical_outfit_replay','outfit_recall')]:
        assert last_business_intent([{'role':'assistant','content':json.dumps({flag:True,'conversation_only':True,'weather_only':False})}])==expected
