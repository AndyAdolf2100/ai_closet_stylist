"""Tests for the evaluator itself; fixture replies never prove live persona quality."""
from argparse import Namespace

import pytest

from scripts.dialogue_validation import (
    EXPECTATIONS,
    SCENARIOS,
    DialogueUpstream,
    PersonaReview,
    check_reply,
    review_status,
    visible_text,
)
from stylist.config import Settings
from stylist.models import Change, Draft, LookDraft, Plan, Reply, Task


def reply(**changes):
    return Reply(conversation_id="sty_" + "1" * 32, version=1, mode="consult", delivery="clarification",
                 message="奥克兰的天气，我暂时还查不到。", task=Task(city="奥克兰"), **changes)


def test_regression_catches_sanya_answer_to_auckland_even_when_response_is_nonempty():
    bad = reply().model_copy(update={"message": "三亚今天多云，31度，继续刚才的旅行搭配。"})
    errors = check_reply(bad, EXPECTATIONS["weather_city_switch/auckland"], ["city.resolve"])
    assert "stale_or_unsupported_claim" in errors and "missing_answer" in errors
    assert not check_reply(reply(), EXPECTATIONS["weather_city_switch/auckland"], ["city.resolve"])


def test_all_business_turns_have_acceptance_conditions():
    assert set(EXPECTATIONS) == {f"{scenario}/{name}" for scenario, rows in SCENARIOS.items()
                                 for name, _, _ in rows}


def test_tool_traces_and_body_are_both_checked_instead_of_only_delivery_labels():
    bad = reply().model_copy(update={"message": "天气接口尚未接入，超出支持范围。"})
    errors = check_reply(bad, {"no_tools": True, "no_weather_tools": True, "inventory": False},
                         ["city.resolve", "/api/user_product/quick_edit_list"])
    assert {"unexpected_tools", "unexpected_weather_query", "inventory_access", "stiff_technical_language"} <= set(errors)
    bad = reply().model_copy(update={"follow_ups": ["要不要我帮你调整鞋子？"]})
    assert "assistant_voice_followup" in check_reply(bad, {}, [])


@pytest.mark.parametrize("scores,status", [((5, 5, 5, 5), "passed"), ((3, 5, 5, 5), "failed"),
                                         ((5, 3, 5, 5), "failed"), ((5, 5, 5, 2), "failed")])
def test_persona_review_requires_all_dimensions_not_a_particle_or_average(scores, status):
    text = "我暂时还查不到呢。"
    review = PersonaReview(persona_fit=scores[0], naturalness=scores[1], relevance=scores[2],
                           factuality=scores[3], evidence="暂时还查不到", reason="按完整表达审核")
    assert review_status(review, text) == status
    assert review_status(review.model_copy(update={"evidence": "不存在的原文"}), text) == "invalid_evidence"
    assert review_status(review.model_copy(update={"evidence": " "}), text) == "invalid_evidence"


@pytest.mark.asyncio
async def test_synthetic_business_adapter_never_silently_accepts_image_or_fee_calls():
    upstream = DialogueUpstream("weather_city_switch")
    assert (await upstream.call("city.resolve", {"name": "奥克兰"}))["status"] == "not_found"
    with pytest.raises(AssertionError, match="Unexpected tool"):
        await upstream.call("image.generate", {})


@pytest.mark.parametrize("judge,review_fails,expected_exit", [(False, False, 2), (True, False, 0), (True, True, 1)])
@pytest.mark.asyncio
async def test_runner_covers_both_personas_and_marks_unreviewed_results_pending(
        tmp_path, monkeypatch, judge, review_fails, expected_exit):
    from scripts import evaluate_personas as runner

    class FixtureModel:
        def __init__(self, settings):
            pass

        async def generate(self, name, payload, result_type):
            if name == "plan":
                city = "奥克兰" if "奥克兰" in payload["message"] else "三亚"
                return Plan(mode="consult" if city == "奥克兰" else "recommend", weather_scope="day",
                            use_inventory=city != "奥克兰", changes={"city": Change(value=city, evidence=city)})
            if name == "review_dialogue":
                return PersonaReview(persona_fit=3 if review_fails else 4, naturalness=4, relevance=4, factuality=4,
                    evidence=payload["visible_reply"].splitlines()[0], reason="模拟审核，仅验证报告流程")
            return Draft(message="从衣橱挑了这套。", looks=[LookDraft(title="旅行装",
                selected_keys=["user:101", "user:102", "user:103"], why=["方便走动"], how=["按体感穿脱"] )])

    monkeypatch.setattr(runner, "LanguageModel", FixtureModel)
    monkeypatch.setattr(runner.Settings, "load", lambda: Settings(llm_key="fake", llm_url="https://unused.invalid", llm_model="fake"))
    output = tmp_path / "review.json"
    code = await runner.run(Namespace(output=str(output), concurrency=1, only=["weather_city_switch"], judge=judge))
    import json
    report = json.loads(output.read_text())
    assert code == expected_exit and report["total"] == 6
    assert {row["persona"] for row in report["cases"]} == {"male_calm_v1", "female_warm_v1"}
    assert report["persona_review_pending"] == (0 if judge else 6)
    assert report["automatic_passed"] == 6
    assert report["accepted"] == (6 if judge and not review_fails else 0)
    assert all(row["errors"] == (["persona_review_failed"] if review_fails else []) for row in report["cases"])
    assert all(
        "三亚" not in visible_text(Reply.model_validate(row["reply"]))
        for row in report["cases"] if row["case"].endswith(("/auckland", "/new_zealand"))
    )
