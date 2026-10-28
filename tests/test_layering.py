import pytest

from scripts.dialogue_validation import PRODUCTS
from scripts.exploratory_dialogues import EXTRA_PRODUCTS, ExploratoryUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import Change, ChatRequest, Draft, Look, LookDraft, Plan, Product, Slot, Task
from stylist.policy import frozen_products, validate_look
from stylist.retrieval import from_row
from stylist.store import Store


def outfit(tops):
    items = [Product(source="user", product_id=str(i), slot=Slot.TOP, title=title, class_name="上衣")
             for i, title in enumerate(tops, 1)]
    items += [Product(source="user", product_id="20", slot=Slot.BOTTOM, title="长裤"),
              Product(source="user", product_id="21", slot=Slot.SHOES, title="平底包脚短靴")]
    return {p.key: p for p in items}


@pytest.mark.parametrize("tops", [
    ["白色长袖衬衫", "米色羊毛针织衫"],
    ["棉T恤", "长袖毛衣"],
    ["保暖打底衫", "衬衫", "针织衫"],
    ["白色T恤", "衬衫"],
    ["长袖上衣"],
])
def test_compatible_top_layers_are_not_duplicate_positions(tops):
    pool = outfit(tops)
    assert not validate_look(list(pool), pool, Task(temp_min=-15), set())


@pytest.mark.parametrize("tops", [
    ["白衬衫", "蓝衬衫"],
    ["羊毛针织衫", "圆领毛衣"],
    ["白色T恤", "黑色T恤"],
    ["羊毛上衣", "纯棉上衣"],
    ["上衣", "针织衫"],
    ["打底衫", "衬衫", "针织衫", "卫衣"],
])
def test_same_or_unverifiable_top_layers_are_still_rejected(tops):
    pool = outfit(tops)
    assert validate_look(list(pool), pool, Task(), set())


def historical_snow_pool():
    products = [from_row(row, "user") for row in PRODUCTS + EXTRA_PRODUCTS]
    return {p.key: p for p in products if p is not None}


# The two actual selections from the failed generation and its repair, using synthetic catalog IDs.
@pytest.mark.parametrize("keys", [
    ["user:108", "user:107", "user:101", "user:102", "user:109"],
    ["user:101", "user:107", "user:108", "user:102", "user:109"],
])
def test_saved_harbin_selection_and_repair_both_pass_structure_check(keys):
    pool = historical_snow_pool()
    assert not validate_look(keys, pool, Task(temp_min=-15, weather_description="下雪"), set())


def test_layering_keeps_duplicate_identity_and_dress_conflict_checks():
    pool = outfit(["衬衫", "针织衫"])
    assert validate_look(list(pool) + ["user:1"], pool, Task(), set())
    dress = Product(source="user", product_id="30", slot=Slot.DRESS, title="连衣裙")
    pool[dress.key] = dress
    assert "连身衣物与上下装结构冲突" in validate_look(list(pool), pool, Task(), set())


@pytest.mark.parametrize("slot", [Slot.BOTTOM, Slot.OUTER, Slot.SHOES])
def test_layering_does_not_allow_two_of_other_main_positions(slot):
    pool = historical_snow_pool()
    keys = ["user:101", "user:107", "user:108", "user:102", "user:109"]
    other = Product(source="user", product_id="99", slot=slot)
    pool[other.key] = other
    assert f"{slot}位置重复" in validate_look(keys + [other.key], pool, Task(), set())


def test_all_top_layers_still_obey_material_and_total_budget_limits():
    pool = historical_snow_pool()
    keys = ["user:101", "user:107", "user:108", "user:102", "user:109"]
    assert "材质包含羊毛" in validate_look(keys, pool, Task(excluded_materials=["羊毛"]), set())
    shirt = pool.pop("user:101").model_copy(update={"source": "system", "incremental_price_yuan": 80})
    knit = pool.pop("user:107").model_copy(update={"source": "system", "incremental_price_yuan": 80})
    pool.update({shirt.key: shirt, knit.key: knit})
    keys[:2] = [shirt.key, knit.key]
    assert "新增购买合计超过预算" in validate_look(keys, pool, Task(source="hybrid", budget_yuan=100), set())


def test_shoe_change_freezes_every_layer_of_an_existing_outfit():
    pool = historical_snow_pool()
    keys = ["user:101", "user:107", "user:108", "user:102", "user:109"]
    look = Look(title="雪天叠穿", items=[pool[k] for k in keys], why=["分层"], how=["先衬衫再针织和羽绒"])
    frozen = {p.key for p in frozen_products([look], [Slot.SHOES])}
    assert frozen == set(keys[:-1])
    replacement = keys[:-1] + ["user:104"]
    assert not validate_look(replacement, pool, Task(), frozen)
    assert "修改了用户要求保留的单品" in validate_look(replacement[1:], pool, Task(), frozen)


@pytest.mark.parametrize("persona", ["male_calm_v1", "female_warm_v1"])
@pytest.mark.parametrize("replacement_missing", [False, True])
@pytest.mark.asyncio
async def test_layered_snow_outfit_delivers_then_only_changes_shoes_without_repair(tmp_path, persona, replacement_missing):
    class Model:
        def __init__(self):
            self.turn = 0
            self.style_payloads = []

        async def generate(self, name, payload, result_type):
            if name == "plan":
                self.turn += 1
                if self.turn == 1:
                    return Plan(mode="recommend", weather_scope="day", changes={
                        "city": Change(value="哈尔滨", evidence="哈尔滨"),
                        "weather_policy": Change(value="provided", evidence="零下十几度、下雪"),
                        "temp_min": Change(value=-15, evidence="零下十几度"),
                        "weather_description": Change(value="下雪", evidence="下雪")})
                return Plan(mode="modify", replace_slots=[Slot.SHOES])
            assert "validation_errors" not in payload, "Valid layering should not need a model repair"
            self.style_payloads.append(payload)
            if self.turn == 2 and replacement_missing:
                return Draft(message="这次没找到适合替换的平底鞋，其他衣物保留。")
            return Draft(message="这套按从内到外分层穿。", looks=[LookDraft(title="雪天叠穿",
                selected_keys=["user:101", "user:107", "user:108", "user:102",
                               "user:109" if self.turn == 1 else "user:104"],
                why=["保留可穿脱的层次"], how=["先穿衬衫，再穿针织衫，最后加羽绒外套。"],
                notes=["实际厚度与鞋底防滑性能还需核对，不保证足够应对严寒。"])])

    class ImageUpstream(ExploratoryUpstream):
        async def call(self, name, args):
            result = await super().call(name, args)
            if name == "product.resolve":
                for row in result["items"]:
                    row["original_image"] = f"https://example.test/items/{row['product_id']}.png"
            return result

    model, upstream = Model(), ImageUpstream("explore_cold_snow")
    engine = Stylist(Settings(), Store(str(tmp_path / "state.db")), model)
    first = await engine.chat(upstream, ChatRequest(assistant_persona=persona, request_id="snow-layers-first",
        message="今天哈尔滨零下十几度、下雪，我要坐公交再走二十分钟，用衣橱搭一套，保暖第一。"))
    assert first.delivery == "outfit" and len(first.looks[0].items) == 5
    assert sum(p.slot == Slot.TOP for p in first.looks[0].items) == 2
    second = await engine.chat(upstream, ChatRequest(assistant_persona=persona, request_id="snow-layers-shoes",
        conversation_id=first.conversation_id, expected_version=first.version,
        message="只换成黑色平底乐福鞋，其余衣服都不动。"))
    if replacement_missing:
        assert second.delivery == "concept" and not second.looks
        assert {p.key for p in second.retained_items} == {"user:101", "user:107", "user:108", "user:102"}
        assert all(p.original_image.startswith("https://example.test/") for p in second.retained_items)
        assert not any(p.slot == Slot.SHOES for p in second.retained_items)
    else:
        assert second.delivery == "outfit" and not second.retained_items
        assert {p.key for p in second.looks[0].items} == {"user:101", "user:107", "user:108", "user:102", "user:104"}
    assert set(model.style_payloads[-1]["frozen_keys"]) == {"user:101", "user:107", "user:108", "user:102"}
    assert len(model.style_payloads) == 2
