import json
from contextlib import asynccontextmanager

import pytest

from scripts.dialogue_validation import PRODUCTS
from scripts.exploratory_dialogues import EXTRA_PRODUCTS, ExploratoryUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.models import Change, ChatRequest, Draft, Look, LookDraft, Plan, Reply, SessionState, Slot, Task
from stylist.personas import service_notice
from stylist.policy import interpret_task, merge_task, unchanged_replacement_problems
from stylist.retrieval import from_row
from stylist.store import Store


@pytest.mark.asyncio
async def test_simplify_followup_keeps_old_conditions_without_requiring_new_citations():
    state = SessionState(task=Task(weather_policy="ignored", preferences=["不塞衣角"],
        owned_descriptions=["白衬衫", "灰裤", "平底鞋"]))

    class Model:
        calls = 0

        async def generate(self, *args):
            self.calls += 1
            return Plan(mode="consult", use_inventory=False, changes={
                "preferences": Change(value=["不塞衣角"], evidence="不塞衣角"),
                "owned_descriptions": Change(value=["白衬衫", "灰裤", "平底鞋"], evidence="白衬衫")})

    model = Model()
    plan, task = await interpret_task(model, {}, state, "保持这三件，穿法再简洁一点，不找商品。")
    assert task == state.task and not plan.changes and model.calls == 1


@pytest.mark.parametrize("new_task", [False, True])
@pytest.mark.asyncio
async def test_stale_citation_cannot_change_a_constraint_or_start_a_new_task(new_task):
    class Model:
        async def generate(self, *args):
            return Plan(mode="consult", new_task=new_task, changes={
                "no_heels": Change(value=True if new_task else False, evidence="不穿高跟鞋")})

    state = SessionState(task=Task(no_heels=True))
    with pytest.raises(StylistError, match="invalid_requirements"):
        await interpret_task(Model(), {}, state, "保持其他要求")
    assert state.task.no_heels


@pytest.mark.asyncio
async def test_dropping_stale_provided_weather_does_not_authorize_skipping_a_new_query():
    class Model:
        async def generate(self, *args):
            return Plan(mode="consult", weather_only=True, changes={
                "weather_policy": Change(value="provided", evidence="昨天的晴天")})

    plan, task = await interpret_task(Model(), {}, SessionState(task=Task(weather_policy="provided")), "看看今天天气")
    assert "weather_policy" not in plan.changes and task.weather_policy == "auto"


def pool():
    return {p.key: p for row in PRODUCTS + EXTRA_PRODUCTS if (p := from_row(row, "user"))}


def layered_look():
    products = pool()
    return Look(title="叠穿", items=[products[k] for k in ["user:101", "user:107", "user:108", "user:102", "user:109"]])


def test_identity_comparison_distinguishes_a_real_replacement_and_adding_a_layer():
    products = pool()
    current = [layered_look()]
    unchanged = Draft(message="已经换鞋", looks=[LookDraft(title="换鞋", selected_keys=[p.key for p in current[0].items],
        why=["保留"], how=["按体感穿脱"])])
    assert unchanged_replacement_problems(unchanged, current, [Slot.SHOES], products)
    changed = unchanged.model_copy(deep=True)
    changed.looks[0].selected_keys[-1] = "user:104"
    assert not unchanged_replacement_problems(changed, current, [Slot.SHOES], products)
    # Keeping a shirt while adding knitwear genuinely changes the top selection.
    one_top = current[0].model_copy(update={"items": [p for p in current[0].items if p.key != "user:107"]})
    assert not unchanged_replacement_problems(unchanged, [one_top], [Slot.TOP], products)


@pytest.mark.parametrize("persona", ["male_calm_v1", "female_warm_v1"])
@pytest.mark.parametrize("repair_changes_shoe", [False, True, "no_alternatives"])
@pytest.mark.asyncio
async def test_same_shoe_cannot_be_delivered_as_a_successful_replacement(tmp_path, persona, repair_changes_shoe):
    store = Store(str(tmp_path / "state.db"))
    original = ChatRequest(message="原叠穿", request_id="unchanged-shoe-setup")
    owner = "synthetic-persona-evaluation"
    cid, claim, state, _ = store.reserve(owner, original)
    state.mode, state.task = "recommend", Task(weather_policy="ignored", no_heels=True)
    state.looks = [layered_look()]
    before = state.model_copy(deep=True)
    store.finish(owner, original, claim, state, Reply(conversation_id=cid, version=1, mode="recommend",
        delivery="outfit", message="原搭配", task=state.task, looks=state.looks))

    class Model:
        def __init__(self):
            self.style_calls = 0

        async def generate(self, name, payload, result_type):
            if name == "plan":
                return Plan(mode="modify", replace_slots=[Slot.SHOES])
            self.style_calls += 1
            assert any(p["key"] == "user:109" for p in payload["current_selection"])
            assert not any(p["key"] == "user:109" for p in payload["candidates"])
            if repair_changes_shoe == "no_alternatives":
                assert payload["replacement_options"]["shoes"] == []
            else:
                assert "user:104" in payload["replacement_options"]["shoes"]
            if self.style_calls == 2:
                assert any(p.startswith("替换未发生") for p in payload["validation_errors"])
            shoe = "user:104" if self.style_calls == 2 and repair_changes_shoe is True else "user:109"
            return Draft(message="只把鞋换成了这双。", looks=[LookDraft(title="换鞋版",
                selected_keys=["user:101", "user:107", "user:108", "user:102", shoe],
                why=["其他保持"], how=["按体感穿脱"])])

    class Upstream(ExploratoryUpstream):
        async def get(self, *args):
            result = await super().get(*args)
            if repair_changes_shoe == "no_alternatives":
                result["list"] = [row for row in result["list"] if row["class_name"] != "鞋子" or row["product_id"] == "109"]
                result["pagination"]["total"] = len(result["list"])
            return result

    model = Model()
    result = await Stylist(Settings(), store, model).chat(Upstream("replacement"), ChatRequest(
        message="其他都保留，只换鞋。", request_id="unchanged-shoe-followup", assistant_persona=persona,
        conversation_id=cid, expected_version=1))
    assert model.style_calls == 2
    if repair_changes_shoe is True:
        assert result.delivery == "outfit"
        assert {p.key for p in result.looks[0].items} == {"user:101", "user:107", "user:108", "user:102", "user:104"}
    else:
        assert result.delivery == "concept" and not result.looks
        assert result.message == service_notice(persona, "replacement" if repair_changes_shoe == "no_alternatives" else "replacement_failed")
        assert {p.key for p in result.retained_items} == {"user:101", "user:107", "user:108", "user:102"}
        with store.connection() as conn:
            saved = json.loads(conn.execute("SELECT state_json FROM stylist_sessions WHERE id=?", (cid,)).fetchone()[0])
        assert saved["looks"] == [look.model_dump(mode="json") for look in before.looks]


@pytest.mark.parametrize("persona", ["male_calm_v1", "female_warm_v1"])
@pytest.mark.parametrize("code", ["forecast_unavailable", "forecast_date_unavailable", "city_needs_selection"])
@pytest.mark.asyncio
async def test_weather_warning_codes_remain_in_logs_and_persona_notices_are_visible(tmp_path, caplog, persona, code):
    class Upstream:
        async def identity(self):
            return "synthetic-warning-owner"

        @asynccontextmanager
        async def mcp(self):
            yield self

        async def call(self, *args):
            raise StylistError(code, "仅供诊断的消息")

    class Weather:
        async def forecast(self, *args):
            raise StylistError(code, "仅供诊断的消息")

    class Model:
        async def generate(self, name, payload, result_type):
            return Plan(mode="consult", weather_scope="day", use_inventory=False, changes={
                "city": Change(value="上海", evidence="上海")}) if name == "plan" else Draft(message="天气没查到，先给文字穿法参考。")

    engine = Stylist(Settings(), Store(str(tmp_path / "state.db")), Model())
    engine.weather = Weather()
    result = await engine.chat(Upstream(), ChatRequest(message="上海今天出门怎么穿，只要文字",
        request_id="friendly-warning-test", assistant_persona=persona))
    assert result.warnings and code not in " ".join(result.warnings)
    assert "仅供诊断" not in " ".join(result.warnings)
    assert code in caplog.text
    assert not any(term in " ".join(result.warnings) for term in ["接口", "降级", "语义检索"])


@pytest.mark.parametrize("failure", ["inventory", "saved_outfits"])
@pytest.mark.parametrize("persona", ["male_calm_v1", "female_warm_v1"])
@pytest.mark.asyncio
async def test_inventory_and_saved_outfit_failures_have_human_notices(tmp_path, persona, failure):
    class Upstream(ExploratoryUpstream):
        async def get(self, *args):
            if failure == "inventory":
                raise StylistError("inventory_read_failed", "诊断")
            return await super().get(*args)

        async def call(self, name, args):
            if name == "outfit.search-saved" and failure == "saved_outfits":
                raise StylistError("saved_outfits_failed", "诊断")
            return await super().call(name, args)

    class Model:
        async def generate(self, name, payload, result_type):
            if name == "plan":
                return Plan(mode="recommend")
            return Draft(message="先按当前信息整理。") if failure == "inventory" else Draft(message="从衣橱整理这套。", looks=[
                LookDraft(title="日常", selected_keys=["user:101", "user:102", "user:103"], why=["配色"], how=["按体感穿脱"])])

    result = await Stylist(Settings(), Store(str(tmp_path / "state.db")), Model()).chat(Upstream("notices"), ChatRequest(
        message="不考虑天气，帮我用衣橱搭一套", request_id="inventory-warning-test", weather_policy="ignored", assistant_persona=persona))
    assert service_notice(persona, "inventory" if failure == "inventory" else "saved_outfits") in result.warnings
    assert "_failed" not in " ".join(result.warnings)


def test_new_preferences_append_and_explicit_removal_is_evidenced():
    state = SessionState(task=Task(preferences=["不塞衣角"], excluded_materials=["羊毛", "皮草"]))
    updated = merge_task(state, Plan(mode="consult", changes={"preferences": Change(value=["简洁一点"], evidence="简洁一点")}), "简洁一点")
    assert updated.preferences == ["不塞衣角", "简洁一点"]
    removed = merge_task(state, Plan(mode="consult", changes={"excluded_materials": Change(value=["羊毛"], operation="remove", evidence="可以穿羊毛")}), "现在可以穿羊毛了")
    assert removed.excluded_materials == ["皮草"]
    reset = merge_task(state, Plan(mode="consult", changes={"preferences": Change(value=["可以塞衣角"], operation="replace", evidence="可以塞衣角")}), "现在可以塞衣角")
    assert reset.preferences == ["可以塞衣角"]


@pytest.mark.asyncio
async def test_removing_a_constraint_cannot_be_pruned_as_an_unchanged_value():
    class Model:
        async def generate(self, *args):
            return Plan(mode="consult", changes={"preferences": Change(value=["不塞衣角"], operation="remove", evidence="旧的引用")})
    with pytest.raises(StylistError, match="invalid_requirements"):
        await interpret_task(Model(), {}, SessionState(task=Task(preferences=["不塞衣角"])), "其他不变")


@pytest.mark.asyncio
async def test_nonlocation_city_still_requires_current_evidence():
    class Model:
        async def generate(self, *args):
            return Plan(mode="consult", weather_only=True, changes={"city": Change(value="北京", evidence="")})
    with pytest.raises(StylistError, match="invalid_requirements"):
        await interpret_task(Model(), {"selected_location": {"city_name": "上海市"}}, SessionState(), "今天天气")


def test_evaluator_detects_the_original_same_id_false_success_and_accepts_retention():
    from scripts.dialogue_validation import check_reply
    current = layered_look()
    previous = Reply(conversation_id="sty_" + "1" * 32, version=1, mode="recommend", delivery="outfit",
                     message="原搭配", task=Task(), looks=[current])
    unchanged = previous.model_copy(update={"version": 2, "mode": "modify", "message": "已换成这双"})
    expected = {"must_change_slots": ["shoes"], "freeze_except": ["shoes"]}
    assert "unchanged_replacement" in check_reply(unchanged, expected, [], previous=previous)
    retained = previous.model_copy(update={"version": 2, "mode": "modify", "delivery": "concept", "message": "这次没有换成，原搭配保留。", "looks": [],
        "retained_items": [product for product in current.items if product.slot != Slot.SHOES]})
    assert not check_reply(retained, expected, [], previous=previous)
