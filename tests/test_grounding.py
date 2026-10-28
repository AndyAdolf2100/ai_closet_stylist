import pytest

from scripts.exploratory_dialogues import ExploratoryUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.grounding import attribute_claim_problems, attribute_context, ground_attribute_fallback
from stylist.models import ChatRequest, Draft, LookDraft, Plan, Product, Slot
from stylist.store import Store


@pytest.mark.parametrize("text", [
    "坐下来对肚子没有压迫感。",
    "这件衬衫不贴身。",
    "这条裤子宽松不勒。",
    "这条裤子坐下不会勒到腹部。",
    "雨天不容易把鞋面弄湿。",
    "这双鞋更不易被雨水打湿。",
    "裤脚和鞋面相对不容易被雨直接扫到。",
    "裤脚和鞋面相对更不容易直接暴露在雨里。",
    "这件风衣能挡雨。",
    "这双鞋防水，防水性能未确认。",
    "这条裤子宽松。没有尺码信息，要试穿。",
    "这件有弹性，活动时不会紧绷。",
    "如果下雨，这双鞋能防水。",
    "建议选这条裤子，坐下也不会勒。",
    "这件外套最能挡风。",
    "这条是松紧腰。",
    "活动和坐下都比较自在。",
    "长裙对腰腹的约束通常比紧身裤更友好。",
    "比运动鞋和乐福更能减少鞋面直接被雨打到的机会。",
    "鞋面直接被雨点打到的面积会少一些。",
    "能先帮你尽量减少鞋面直接被雨打到的机会。",
    "长半裙腰腹位置通常更容易留出活动空间，坐着聊天会比较放松。",
    "这双鞋走路和久坐都更轻松。",
    "不能保证防水但这条裤子不勒。",
    "防水性能未确认，不过这双鞋更不易淋湿。",
])
def test_unverified_guarantees_are_rejected_even_with_a_later_caveat(text):
    assert attribute_claim_problems(Draft(message=text), {})


@pytest.mark.parametrize("text", [
    "是否合身、腰腹会不会受压，还要看尺寸和试穿感受。",
    "这件穿着是否合身，还要试穿看看腰腹有没有受压。",
    "先坐下活动，确认腰腹不勒再选。",
    "如果这条是松紧腰，再按实际松量调整。",
    "如果穿上没有压迫感，再决定是否保留。",
    "先试穿看看会不会勒肚子。",
    "优先找不勒肚子的裤子。",
    "请选择宽松版型，具体松量要试穿。",
    "你希望不勒肚子，我会把舒适放在前面。",
    "你喜欢宽松，我会以舒适为目标。",
    "以坐下活动都舒服为准。",
    "不能保证这件不贴身，先试穿看看。",
    "还不能确认防水或防滑效果，雨天带好雨具。",
    "防滑和防水性能没有标注。",
    "防水效果还没确认，带伞并尽量走有遮蔽的路线。",
    "目前没有防水资料，不能保证不易淋湿。",
    "鞋子防滑性能未确认。",
    "这双短靴的防滑和支撑情况需要你按实物判断。",
    "鞋子的防滑和脚感很重要。",
    "衣服没有可靠防雨说明，别指望衣服挡雨。",
    "防水/防滑性能未确认。",
    "长时间步行请优先选你实际穿着舒适的鞋；防滑、支撑和脚感需核对实物。",
    "皮革不等于防水。",
    "先试试看这双鞋会不会湿。",
    "衬衫如果偏贴身，避免坐下时腹部堆着不舒服。",
    "先坐下试试，腰腹没有受压再选。",
    "撑伞能减少雨水直接打到鞋面的机会。",
])
def test_unknowns_goals_and_real_try_on_conditions_remain_natural(text):
    assert not attribute_claim_problems(Draft(message=text), {})


def test_catalog_wording_only_supports_attributed_design_not_personal_fit():
    product = Product(source="user", product_id="1", slot=Slot.TOP, title="宽松防水外套")
    pool = {product.key: product}
    look = LookDraft(title="日常", selected_keys=[product.key], why=["配色"], how=["按体感调整"])
    assert not attribute_claim_problems(Draft(message="名称标注宽松，名称标注防水；实际松量和效果还需核对。", looks=[look]), pool)
    assert attribute_claim_problems(Draft(message="这件宽松防水，穿上不贴身。", looks=[look]), pool)
    assert attribute_claim_problems(Draft(message="名称标注宽松。", looks=[look]), {})
    context = attribute_context([product])
    assert context["measurements_and_personal_fit"] == "unknown"
    assert context["catalog_labels"] == [{"key": "user:1", "labels": ["宽松", "防水"]}]


@pytest.mark.parametrize("field", ["title", "pieces", "why", "how", "notes"])
def test_claims_in_every_outfit_region_are_checked(field):
    values = dict(title="日常", pieces=[], why=["顺色"], how=["按体感穿脱"])
    values[field] = "这件衬衫不贴身" if field == "title" else ["这件衬衫不贴身"]
    assert attribute_claim_problems(Draft(message="已整理", looks=[LookDraft(**values)]), {})


@pytest.mark.parametrize("persona", ["male_calm_v1", "female_warm_v1"])
def test_last_resort_rewrites_claims_and_preserves_selected_items(persona):
    original = Draft(message="这套不勒腰，鞋子能防水。", looks=[LookDraft(title="宽松不勒通勤",
        selected_keys=["user:1"], why=["坐下没有压迫感"], how=["这双鞋防水"], notes=["这件衬衫不贴身"])])
    grounded = ground_attribute_fallback(original, {}, persona)
    assert not attribute_claim_problems(grounded, {})
    assert grounded.looks[0].selected_keys == original.looks[0].selected_keys
    assert original.message == "这套不勒腰，鞋子能防水。"


@pytest.mark.parametrize("persona", ["male_calm_v1", "female_warm_v1"])
@pytest.mark.parametrize("second_attempt_bad", [False, True, "drops_items", "changes_items"])
@pytest.mark.asyncio
async def test_engine_repairs_claims_and_still_delivers_when_model_repeats_them(tmp_path, persona, second_attempt_bad):
    class Model:
        def __init__(self):
            self.calls = []

        async def generate(self, name, payload, result_type):
            self.calls.append(name)
            if name == "plan":
                return Plan(mode="recommend")
            assert payload["attribute_context"]["measurements_and_personal_fit"] == "unknown"
            repair = "validation_errors" in payload
            if repair:
                assert all("属性依据不足" in e for e in payload["validation_errors"])
            if repair and second_attempt_bad == "drops_items":
                return Draft(message="先试穿看看。")
            if repair and second_attempt_bad == "changes_items":
                return Draft(message="先试穿看看。", looks=[LookDraft(title="通勤",
                    selected_keys=["user:101", "user:102", "user:104"], why=["配色"], how=["按体感调整"])])
            text = "这条裤子坐下没有压迫感，衬衫不贴身。" if not repair or second_attempt_bad else "先坐下试穿，确认腰腹不勒再选。"
            return Draft(message=text, looks=[LookDraft(title="通勤",
                selected_keys=["user:101", "user:102", "user:103"], why=["配色清爽"], how=["先试穿活动再决定"])])

    model = Model()
    reply = await Stylist(Settings(), Store(str(tmp_path / "state.db")), model).chat(
        ExploratoryUpstream("attribute_test"), ChatRequest(message="帮我用衣橱搭一套，不考虑天气。",
            request_id="attribute-claim-test", assistant_persona=persona, weather_policy="ignored"))
    assert reply.delivery == "outfit" and len(reply.looks[0].items) == 3
    assert {p.key for p in reply.looks[0].items} == {"user:101", "user:102", "user:103"}
    assert not attribute_claim_problems(Draft(message=reply.message), {})
    assert model.calls == ["plan", "style", "style"]
    assert "不会勒" not in reply.message and "没有压迫感" not in reply.message


def test_fallback_preserves_supported_context_in_same_paragraph():
    original = Draft(message="今天上海上班，我按衣橱整理了一套，这条裤子坐下没有压迫感。")
    fixed = ground_attribute_fallback(original, {}, "male_calm_v1")
    assert "今天上海上班" in fixed.message and "按衣橱整理了一套" in fixed.message
    assert not attribute_claim_problems(fixed, {})
