import pytest

from scripts.exploratory_dialogues import ExploratoryUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import ChatRequest, CitySelection, Draft, Plan, Reply, Task, TripStop
from stylist.store import Store


@pytest.mark.asyncio
@pytest.mark.parametrize("persona", ["male_calm_v1", "female_warm_v1"])
@pytest.mark.parametrize("old_city", [None, "上海市"])
async def test_chat_reply_sees_page_city_without_overwriting_outfit_task(tmp_path, persona, old_city):
    owner = "synthetic-persona-evaluation"
    store = Store(str(tmp_path / "state.db"))
    setup = ChatRequest(message="已有任务", request_id="city-context-setup")
    cid, claim, state, _ = store.reserve(owner, setup)
    state.task = Task(city=old_city, itinerary=[TripStop(city_name=old_city), TripStop(city_name="三亚市")] if old_city else [])
    old_task = state.task.model_dump(mode="json")
    store.finish(owner, setup, claim, state, Reply(conversation_id=cid, version=1,
        mode="consult", delivery="advice", message="已保留任务", task=state.task))
    selected = {"city_name": "北京市", "province_name": "北京市"}
    received = []

    class Model:
        async def generate(self, name, payload, result_type):
            assert payload["selected_location"] == selected
            if name == "plan":
                return Plan(mode="consult", conversation_only=True, use_inventory=False)
            received.append(payload)
            assert payload["task"] == old_task
            return Draft(message="页面当前选择的是北京市。")

    upstream = ExploratoryUpstream("page-city-chat")
    reply = await Stylist(Settings(), store, Model()).chat(upstream, ChatRequest(
        message="你知道我目前选择的城市吗？", request_id="city-context-chat", conversation_id=cid,
        expected_version=1, assistant_persona=persona, location=CitySelection(**selected)))
    assert received and "北京市" in reply.message
    assert reply.task.model_dump(mode="json") == old_task
    assert not upstream.events


@pytest.mark.asyncio
async def test_reply_location_is_per_request_and_not_retained_after_clearing(tmp_path):
    store = Store(str(tmp_path / "state.db"))
    contexts = []

    class Model:
        async def generate(self, name, payload, result_type):
            if name == "plan":
                return Plan(mode="consult", conversation_only=True, use_inventory=False)
            contexts.append(payload["selected_location"])
            return Draft(message="这里只参考本轮页面已选城市，不知道精确位置。")

    stylist = Stylist(Settings(), store, Model())
    upstream = ExploratoryUpstream("page-city-cleared")
    first = await stylist.chat(upstream, ChatRequest(message="当前城市呢？", request_id="location-present",
        location=CitySelection(city_name="北京市", province_name="北京市")))
    await stylist.chat(upstream, ChatRequest(message="现在还选着城市吗？", request_id="location-cleared",
        conversation_id=first.conversation_id, expected_version=first.version))
    assert contexts == [{"city_name": "北京市", "province_name": "北京市"}, None]
    assert not upstream.events
