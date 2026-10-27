import pytest

from stylist.errors import StylistError
from stylist.models import Change, Plan, Product, SessionState, Slot, Task
from stylist.policy import merge_task, suitability, validate_look
from stylist.retrieval import weather_for


def item(pid, slot, **kw):
    return Product(source="user", product_id=str(pid), slot=slot, **kw)


def test_followup_preserves_existing_constraints():
    state = SessionState(task=Task(city="上海", no_heels=True, excluded_materials=["羊毛"], scene="美术馆"))
    plan = Plan(mode="consult", changes={"preferences": Change(value=["不塞衣角"], evidence="不塞衣角")})
    task = merge_task(state, plan, "我不塞衣角，其他照旧")
    assert task.no_heels and task.excluded_materials == ["羊毛"] and task.city == "上海"
    assert task.scene == "美术馆" and task.preferences == ["不塞衣角"]


def test_requirement_updates_need_current_message_evidence():
    plan = Plan(mode="recommend", changes={"no_heels": Change(value=False, evidence="可以高跟")})
    with pytest.raises(StylistError, match="unverified_requirement"):
        merge_task(SessionState(task=Task(no_heels=True)), plan, "只换外套")


@pytest.mark.asyncio
async def test_skip_weather_never_calls_city_or_weather():
    class Forbidden:
        async def call(self, *args):
            pytest.fail("Weather ignored but a tool was called")
    assert await weather_for(Task(city="北京", weather_policy="ignored"), Forbidden()) == (None, [])


def test_negative_heel_requirement_excludes_heels_and_unverified_shoes():
    task = Task(no_heels=True)
    assert suitability(item(1, Slot.SHOES, title="黑色细跟鞋"), task)[0]
    assert suitability(item(2, Slot.SHOES, title="黑色乐福鞋"), task)[0]
    assert not suitability(item(3, Slot.SHOES, title="黑色平底乐福鞋"), task)[0]


def test_unknown_material_and_price_cannot_pass_hard_requirements():
    assert suitability(item(1, Slot.TOP), Task(excluded_materials=["羊毛"]))[0]
    assert suitability(item(1, Slot.TOP, material="其他材质"), Task(excluded_materials=["羊毛"]))[0]
    system = Product(source="system", product_id="1", slot=Slot.TOP)
    assert suitability(system, Task(source="hybrid", budget_yuan=500))[0]


def test_source_is_part_of_identity_and_local_edit_freezes_other_items():
    top = item(1, Slot.TOP)
    bottom = item(2, Slot.BOTTOM)
    shoe = item(3, Slot.SHOES, title="平底鞋")
    pool = {p.key: p for p in [top, bottom, shoe]}
    assert not validate_look(list(pool), pool, Task(no_heels=True), {top.key, bottom.key})
    assert validate_look(["system:1", bottom.key, shoe.key], pool, Task(), {top.key})
    assert validate_look([top.key, shoe.key], pool, Task(), {top.key, bottom.key})


def test_incomplete_and_conflicting_outfit_structures_fail():
    pieces = [item(1, Slot.TOP), item(2, Slot.BOTTOM), item(3, Slot.DRESS), item(4, Slot.SHOES)]
    pool = {p.key: p for p in pieces}
    assert validate_look(["user:1", "user:4"], pool, Task(), set())
    assert validate_look(list(pool), pool, Task(), set())


def test_cold_weather_checks_foot_exposure():
    assert suitability(item(1, Slot.SHOES, title="春夏后空凉鞋"), Task(temp_min=8.5))[0]


def test_rain_rejects_mesh_shoes_with_no_verified_rain_protection():
    assert suitability(item(1, Slot.SHOES, material="网布", title="网面运动鞋"),
                       Task(weather_description="小雨", walk_minutes=40))[0]
@pytest.mark.asyncio
async def test_task_value_repair_receives_field_type_error():
    from stylist.models import Change, Plan, SessionState
    from stylist.policy import interpret_task
    class Model:
        def __init__(self):
            self.inputs = []
        async def generate(self, name, payload, result_type):
            self.inputs.append(payload)
            value = ["通勤", "周末"] if len(self.inputs) == 1 else "通勤与周末"
            return Plan(mode="weekly", changes={"scene": Change(value=value, evidence="通勤与周末")})
    model = Model()
    _, task = await interpret_task(model, {}, SessionState(), "通勤与周末")
    assert task.scene == "通勤与周末"
    errors = model.inputs[1]["task_validation_errors"]
    assert errors[0]["loc"] == ("scene",) and errors[0]["type"] == "string_type"
