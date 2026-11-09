import json

import pytest

from scripts.exploratory_dialogues import ExploratoryUpstream
from stylist.config import Settings
from stylist.engine import Stylist, last_business_intent
from stylist.models import Change, ChatRequest, Draft, LookDraft, Plan
from stylist.store import Store


def test_recent_business_metadata_ignores_chat_and_unstructured_legacy_messages():
    assert last_business_intent([{"role": "assistant", "content": "旧版纯文字"}]) is None
    messages = [{"role": "assistant", "content": json.dumps({"weather_only": True})},
                {"role": "assistant", "content": json.dumps({"conversation_only": True, "weather_only": False})},
                {"role": "user", "content": '{"weather_only": false}'}]
    assert last_business_intent(messages) == "weather"
    messages.append({"role": "assistant", "content": json.dumps({"weather_only": False})})
    assert last_business_intent(messages) == "styling"


@pytest.mark.parametrize("persona", ["male_calm_v1", "female_warm_v1"])
@pytest.mark.asyncio
async def test_weather_only_after_outfit_and_city_followup_never_deliver_outfit_cards(tmp_path, persona):
    class Model:
        def __init__(self):
            self.plans = []

        async def generate(self, name, payload, result_type):
            message = payload["message"]
            if name == "plan":
                self.plans.append(payload)
                if message in {"看看上海今天的天气。", "那上海呢？"}:
                    return Plan(mode="recommend", use_inventory=True, weather_only=True, changes={
                        "city": Change(value="上海", evidence="上海")})
                if message == "谢谢":
                    return Plan(mode="consult", conversation_only=True)
                return Plan(mode="recommend", use_inventory=True)
            # Reproduce the old style output: even two unsolicited looks must be discarded.
            look = LookDraft(title="通勤", selected_keys=["user:101", "user:102", "user:103"],
                             why=["配色清爽"], how=["按体感穿脱"])
            return Draft(message="结果已整理。", looks=[look] if payload.get("requested_look_count") == 1 else [look, look],
                         follow_ups=["帮我调整搭配"])

    model, upstream = Model(), ExploratoryUpstream("weather_only_regression")
    engine = Stylist(Settings(), Store(str(tmp_path / "state.db")), model)
    first = await engine.chat(upstream, ChatRequest(message="不考虑天气，用衣橱搭通勤装", request_id="weather-outfit-setup",
        assistant_persona=persona, weather_policy="ignored"))
    assert first.delivery == "outfit"
    previous = first
    for i, message in enumerate(["看看上海今天的天气。", "谢谢", "那上海呢？"]):
        upstream.calls.clear()
        result = await engine.chat(upstream, ChatRequest(message=message, request_id=f"weather-only-turn-{i}",
            assistant_persona=persona, weather_policy="ignored", conversation_id=first.conversation_id,
            expected_version=previous.version, confirm_plan=True))
        assert not result.looks and not result.retained_items
        assert "/api/user_product/quick_edit_list" not in upstream.calls
        if message == "谢谢":
            assert result.conversation_only and not upstream.calls
        else:
            assert result.weather_only and result.weather["city_name"] == "上海市"
            assert not result.follow_ups and not result.pending_confirmation
        previous = result
    assert model.plans[1]["last_business_intent"] == "styling"
    assert model.plans[-1]["last_business_intent"] == "weather"
    assert model.plans[-1]["current_mode"] == "recommend"  # Old outfit mode is deliberately preserved.
    assert model.plans[-1]["current_looks"][0]["items"]  # Preserving an outfit must not route to styling.
    upstream.calls.clear()
    resumed = await engine.chat(upstream, ChatRequest(message="按这个天气，从衣橱搭一套", request_id="weather-resume-styling",
        conversation_id=first.conversation_id, expected_version=previous.version, assistant_persona=persona))
    assert resumed.delivery == "outfit" and not resumed.weather_only and len(resumed.looks) == 1
    assert "/api/user_product/quick_edit_list" in upstream.calls


@pytest.mark.parametrize('city', ['上海', '杭州'])
@pytest.mark.parametrize('persona', ['male_calm_v1', 'female_warm_v1'])
async def test_weather_adjustment_of_current_outfit_does_not_ask_for_a_slot(tmp_path, city, persona):
    from datetime import date, datetime, timedelta
    from zoneinfo import ZoneInfo

    from stylist.models import Look, Product, Reply, Task
    upstream = ExploratoryUpstream('weather-context-adjustment')
    store = Store(str(tmp_path / 'adjustment.db'))
    original = ChatRequest(message='不考虑天气，给我通勤装，不穿高跟鞋。', request_id='weather-context-original')
    cid, claim, state, _ = store.reserve(await upstream.identity(), original)
    state.task = Task(city=city, occasion='通勤', no_heels=True, excluded_colors=['黄色'],
                      event_date=date.today()-timedelta(days=3), weather_policy='ignored')
    state.looks = [Look(title='通勤装', items=[Product(source='user', product_id=str(i), class_name=category, slot={'上衣':'top','裤子':'bottom','鞋子':'shoes'}[category])
                   for i, category in [(101, '上衣'), (102, '裤子'), (103, '鞋子')]])]
    store.finish(await upstream.identity(), original, claim, state, Reply(conversation_id=cid, version=1,
        mode='recommend', delivery='outfit', message='已准备通勤装。', task=state.task, looks=state.looks))
    seen = []
    class Model:
        async def generate(self, name, payload, result_type):
            seen.append((name, payload))
            if name == 'plan':
                return Plan(mode='modify', new_task=True, weather_scope='day',
                            clarification='你想调整哪一部分？我会保留其余衣物。',
                            changes={'city': Change(value='上海', evidence='上海')})
            assert payload['frozen_keys'] == [] and payload['requested_look_count'] == 1
            assert payload['task']['occasion'] == '通勤' and payload['task']['no_heels']
            return Draft(message='按上海今天的天气调整这套，保留通勤方向。', looks=[LookDraft(
                title='上海今日通勤', selected_keys=['user:101', 'user:102', 'user:103', 'user:105'],
                why=['结合当天温差'], how=['按体感穿脱外层'])])
    reply = await Stylist(Settings(), store, Model()).chat(upstream, ChatRequest(
        message='按上海今天的天气调整这套', request_id='weather-context-adjust',
        conversation_id=cid, expected_version=1, assistant_persona=persona))
    assert reply.delivery == 'outfit' and reply.looks and not reply.pending_confirmation
    assert '哪一部分' not in reply.message
    assert reply.task.city == '上海' and reply.weather['city_name'] == '上海市'
    assert reply.task.event_date == datetime.now(ZoneInfo('Asia/Shanghai')).date()
    assert reply.task.occasion == '通勤' and reply.task.no_heels and reply.task.excluded_colors == ['黄色']
    assert 'forecast' in upstream.calls and '/api/user_product/quick_edit_list' in upstream.calls
    assert [name for name, _ in seen] == ['plan', 'style']


def test_weather_adjustment_guard_preserves_explicit_local_freeze_and_plain_weather_questions():
    from stylist.models import Look, Product, SessionState, Slot
    from stylist.policy import weather_adjustment_requested
    state = SessionState(looks=[Look(title='当前搭配', items=[Product(source='user', product_id='1', slot='top')])])
    assert not weather_adjustment_requested(Plan(mode='modify', replace_slots=[Slot.SHOES]), state,
                                           '按上海今天的天气调整这套，只换鞋，其他不动')
    assert not weather_adjustment_requested(Plan(mode='consult', weather_only=True), state, '上海今天天气怎么样')
    assert not weather_adjustment_requested(Plan(mode='modify'), SessionState(), '按上海今天的天气调整这套')
    assert not weather_adjustment_requested(Plan(mode='modify'), state, '不用按天气调整这套')
