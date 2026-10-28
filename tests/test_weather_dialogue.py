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
            return Draft(message="结果已整理。", looks=[look, look], follow_ups=["帮我调整搭配"])

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
    assert resumed.delivery == "outfit" and not resumed.weather_only
    assert "/api/user_product/quick_edit_list" in upstream.calls
