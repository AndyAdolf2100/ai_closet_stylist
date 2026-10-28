import pytest

from scripts.dialogue_validation import PRODUCTS
from scripts.exploratory_dialogues import ExploratoryUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import (
    Change,
    ChatRequest,
    Draft,
    Look,
    LookDraft,
    Plan,
    Product,
    SessionState,
    Slot,
    Task,
)
from stylist.policy import interpret_task
from stylist.store import Store


class Model:
    def __init__(self, plan):
        self.plan = plan

    async def generate(self, name, payload, result_type):
        assert name == "plan"
        return self.plan


def current_look():
    return Look(title="通勤", items=[Product(**p, source="user", slot=slot)
        for p, slot in zip(PRODUCTS[:3], [Slot.TOP, Slot.BOTTOM, Slot.SHOES], strict=True)],
        why=["通勤"], how=["自然穿着"])


@pytest.mark.parametrize("mode,items,expected,inventory", [
    ("recommend", True, "recommend", True),
    ("modify", True, "recommend", True),
    ("consult", False, "consult", False),
    ("weekly", True, "weekly", True),
    ("weekly", False, "weekly", False),
])
@pytest.mark.asyncio
async def test_verified_location_correction_is_not_an_unspecified_garment_change(mode, items, expected, inventory):
    state = SessionState(mode=mode, task=Task(city="上海", occasion="工作", no_heels=True),
                         looks=[current_look()] if items else [])
    plan, task = await interpret_task(Model(Plan(mode="modify", changes={
        "city": Change(value="杭州", evidence="杭州")})), {}, state, "地点说错了，是杭州，其他要求不变。")
    assert plan.mode == expected and plan.use_inventory == inventory and not plan.clarification
    assert plan.weather_scope == ("week" if mode == "weekly" else "day")
    assert task.city == "杭州" and task.occasion == "工作" and task.no_heels


@pytest.mark.parametrize("slots,clarification", [([Slot.SHOES], None), ([], "你想换哪件？")])
@pytest.mark.asyncio
async def test_city_correction_does_not_remove_explicit_replacement_or_real_question(slots, clarification):
    original = Plan(mode="modify", replace_slots=slots, clarification=clarification,
                    changes={"city": Change(value="杭州", evidence="杭州")})
    plan, _ = await interpret_task(Model(original), {}, SessionState(looks=[current_look()]), "杭州")
    assert plan.mode == "modify" and plan.replace_slots == slots and plan.clarification == clarification


@pytest.mark.parametrize("persona", ["male_calm_v1", "female_warm_v1"])
@pytest.mark.parametrize("ignored", [False, True])
@pytest.mark.asyncio
async def test_full_conversation_corrects_city_and_continues_outfit(tmp_path, persona, ignored):
    class DialogueModel:
        def __init__(self):
            self.turn = 0
            self.payloads = []

        async def generate(self, name, payload, result_type):
            if name == "plan":
                self.turn += 1
                if self.turn == 1:
                    return Plan(mode="recommend", weather_scope="day", changes={
                        "city": Change(value="上海", evidence="上海"),
                        "occasion": Change(value="工作", evidence="通勤"),
                        "no_heels": Change(value=True, evidence="不穿高跟鞋"),
                        "weather_policy": Change(value="ignored" if ignored else "auto", evidence="不考虑天气" if ignored else "今天")})
                # Replay the original classifier failure, with no garment slot supplied.
                return Plan(mode="modify", changes={"city": Change(value="杭州", evidence="杭州")})
            self.payloads.append(payload)
            return Draft(message="按这次地点整理好了通勤搭配。", looks=[LookDraft(title="通勤",
                selected_keys=["user:101", "user:102", "user:103", "user:105"],
                why=["保留通勤与平底鞋要求"], how=["按当地天气穿脱外层"])])

    upstream, model = ExploratoryUpstream("explore_city_correct"), DialogueModel()
    stylist = Stylist(Settings(), Store(str(tmp_path / "state.db")), model)
    first = await stylist.chat(upstream, ChatRequest(message="今天上海通勤，不穿高跟鞋，用衣橱搭一套。" + ("不考虑天气" if ignored else ""),
        request_id="city-correct-first", assistant_persona=persona))
    upstream.events.clear()
    upstream.calls.clear()
    reply = await stylist.chat(upstream, ChatRequest(message="地点说错了，是杭州，其他要求不变。",
        request_id="city-correct-second", conversation_id=first.conversation_id,
        expected_version=first.version, assistant_persona=persona))
    assert reply.delivery == "outfit" and reply.mode == "recommend"
    assert reply.task.city == "杭州" and reply.task.no_heels and reply.task.occasion == "工作"
    assert "/api/user_product/quick_edit_list" in upstream.calls
    assert model.payloads[-1]["frozen_keys"] == []
    if ignored:
        assert not any(e["tool"] in {"forecast", "city.resolve"} for e in upstream.events)
        assert reply.weather is None
    else:
        assert [e for e in upstream.events if e["tool"] == "forecast"] == [{"tool": "forecast", "city": "杭州市"}]
        assert reply.weather["city_name"] == "杭州市"
