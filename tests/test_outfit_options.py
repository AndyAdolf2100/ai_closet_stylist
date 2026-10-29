import pytest

from scripts.dialogue_validation import PRODUCTS
from scripts.exploratory_dialogues import EXTRA_PRODUCTS, ExploratoryUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.grounding import attribute_claim_problems, ground_attribute_fallback
from stylist.models import ChatRequest, Draft, Look, LookDraft, Plan, Reply, Slot, Task
from stylist.retrieval import from_row
from stylist.store import Store


def options():
    return [LookDraft(title=title, style_name=style, selected_keys=keys, why=["配色呼应"], how=["按体感穿脱"])
        for title, style, keys in [
            ("衬衫与灰裤", "简约通勤", ["user:101", "user:102", "user:104"]),
            ("蓝T恤与灰裤", "休闲日常", ["user:106", "user:102", "user:103"]),
            ("针织与长裙", "温柔日常", ["user:107", "user:112", "user:109"])]]


@pytest.mark.parametrize("count", [1, 2, 3])
@pytest.mark.asyncio
async def test_style_labels_survive_delivery_and_saved_history(tmp_path, count):
    class Model:
        async def generate(self, name, payload, result_type):
            return Plan(mode="recommend") if name == "plan" else Draft(message="按衣橱整理好了。", looks=options()[:count])

    store = Store(str(tmp_path / "state.db"))
    reply = await Stylist(Settings(), store, Model()).chat(ExploratoryUpstream("options"), ChatRequest(
        message="不考虑天气，从衣橱整理穿搭", request_id="outfit-options-test", weather_policy="ignored"))
    assert reply.delivery == "outfit" and len(reply.looks) == count
    assert [x.style_name for x in reply.looks] == [x.style_name for x in options()[:count]]
    with store.connection() as conn:
        row = conn.execute("SELECT state_json FROM stylist_sessions WHERE id=?", (reply.conversation_id,)).fetchone()
    from stylist.models import SessionState
    saved = SessionState.model_validate_json(row[0])
    assert saved.looks == reply.looks


@pytest.mark.parametrize("selected_index", [0, 1, 2])
@pytest.mark.asyncio
async def test_local_change_uses_the_selected_tab_and_keeps_other_items(tmp_path, selected_index):
    store = Store(str(tmp_path / "state.db"))
    pool = {p.key: p for row in PRODUCTS + EXTRA_PRODUCTS if (p := from_row(row, "user"))}
    initial = ChatRequest(message="三套原搭配", request_id="outfit-options-setup")
    owner = "synthetic-persona-evaluation"
    cid, claim, state, _ = store.reserve(owner, initial)
    state.task = Task(weather_policy="ignored")
    state.looks = [Look(**x.model_dump(exclude={"selected_keys"}), items=[pool[k] for k in x.selected_keys]) for x in options()]
    store.finish(owner, initial, claim, state, Reply(conversation_id=cid, version=1, mode="recommend",
        delivery="outfit", message="三套搭配", task=state.task, looks=state.looks))
    target = options()[selected_index]
    old_shoe = target.selected_keys[-1]
    new_shoe = "user:103" if old_shoe != "user:103" else "user:104"
    expected = target.selected_keys[:-1] + [new_shoe]

    class Model:
        async def generate(self, name, payload, result_type):
            if name == "plan":
                assert payload["selected_look_index"] == selected_index
                return Plan(mode="modify", replace_slots=[Slot.SHOES])
            assert set(payload["frozen_keys"]) == set(target.selected_keys[:-1])
            assert {p["key"] for p in payload["current_selection"]} == set(target.selected_keys)
            assert old_shoe not in {p["key"] for p in payload["candidates"]}
            return Draft(message="其他保留，只换鞋。", looks=[target.model_copy(update={"selected_keys": expected})])

    reply = await Stylist(Settings(), store, Model()).chat(ExploratoryUpstream("tab-change"), ChatRequest(
        message="其他保留，只换鞋", request_id="outfit-options-change", conversation_id=cid,
        expected_version=1, selected_look_index=selected_index))
    assert reply.delivery == "outfit" and {p.key for p in reply.looks[0].items} == set(expected)


@pytest.mark.asyncio
async def test_invalid_selected_tab_does_not_silently_modify_first_outfit(tmp_path):
    class Model:
        async def generate(self, name, payload, result_type):
            assert name == "plan"
            return Plan(mode="modify", replace_slots=[Slot.SHOES])

    with pytest.raises(StylistError, match="look_not_found"):
        await Stylist(Settings(), Store(str(tmp_path / "state.db")), Model()).chat(
            ExploratoryUpstream("invalid-tab"), ChatRequest(message="只换鞋", request_id="invalid-outfit-tab", selected_look_index=2))


def test_legacy_outfits_without_style_label_remain_readable():
    assert Look.model_validate({"title": "旧搭配"}).style_name == ""
    assert LookDraft.model_validate({"title": "旧搭配", "why": ["配色"], "how": ["分层"]}).style_name == ""


def test_style_labels_cannot_bypass_unsupported_attribute_guard():
    draft = Draft(message="按衣橱整理。", looks=[LookDraft(title="日常", style_name="宽松不勒", why=["配色"], how=["试穿核对"])])
    assert any("style_name" in x for x in attribute_claim_problems(draft, {}))
    repaired = ground_attribute_fallback(draft, {}, "female_warm_v1")
    assert repaired.looks[0].style_name == "日常参考"
    assert not attribute_claim_problems(repaired, {})
