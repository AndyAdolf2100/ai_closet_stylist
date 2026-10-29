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
from stylist.models import Change, CompanionProfile, Draft, LookDraft, Plan, Reply, Task


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


def test_companion_cases_check_current_names_gender_and_retained_preferences():
    expected = EXPECTATIONS["companion_names/rename"]
    assert not check_reply(reply().model_copy(update={"message": "小林，我叫沐沐。"}), expected, [])
    stale = check_reply(reply().model_copy(update={"message": "小夏，我是衣衣。"}), expected, [])
    assert {"stale_or_unsupported_claim", "missing_answer"} <= set(stale)
    assert "task_gender" in check_reply(reply(), EXPECTATIONS["companion_gender_female/self"], [])
    assert "task_preferences_missing" in check_reply(reply(), EXPECTATIONS["companion_role_switch/switch"], [])
    for key, expected in EXPECTATIONS.items():
        if key.startswith("companion_"):
            CompanionProfile(**expected["companion_profile"])


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


@pytest.mark.parametrize("scenario", ["companion_names", "companion_role_switch", "companion_name_injection"])
@pytest.mark.asyncio
async def test_runner_passes_current_profile_to_both_model_stages_and_reviewer(tmp_path, monkeypatch, scenario):
    """Verify real engine/runner wiring with fixtures, without claiming model quality."""
    import json

    from scripts import evaluate_personas as runner

    observed = []

    class FixtureModel:
        def __init__(self, settings):
            pass

        async def generate(self, name, payload, result_type):
            current = CompanionProfile.model_validate(payload["companion_profile"])
            observed.append((name, current))
            if name == "review_dialogue":
                return PersonaReview(persona_fit=4, naturalness=4, relevance=4, factuality=4,
                    evidence=payload["visible_reply"].splitlines()[0], reason="合成审核，只验证资料传递")
            assert payload["assistant_persona"] == current.assistant_persona
            if name == "plan":
                chat = "只说名字" in payload["message"] or scenario == "companion_names" or "有点累" in payload["message"]
                return Plan(mode="consult", conversation_only=chat, use_inventory=False,
                    changes={} if chat else {
                        "weather_policy": Change(value="ignored", evidence="不查衣橱和天气"),
                        "preferences": Change(value=["不塞衣角"], evidence="不塞衣角"),
                    })
            if "别叫我的名字" in payload["message"]:
                return Draft(message="晚安，好好休息。")
            return Draft(message=f"{current.user_name}，我是{current.agent_name}。", looks=[] if (
                scenario == "companion_names" or "只说名字" in payload["message"] or "有点累" in payload["message"]
            ) else [LookDraft(title="合成文字建议", pieces=["白衬衫", "灰裤", "平底鞋"],
                why=["颜色简洁"], how=["不塞衣角"])])

    monkeypatch.setattr(runner, "LanguageModel", FixtureModel)
    monkeypatch.setattr(runner.Settings, "load", lambda: Settings(llm_key="fake", llm_url="https://unused.invalid", llm_model="fake"))
    output = tmp_path / "companion.json"
    assert await runner.run(Namespace(output=str(output), concurrency=1, only=[scenario], judge=True)) == 0
    report = json.loads(output.read_text())
    assert report["accepted"] == report["total"] == len(SCENARIOS[scenario]) * 2
    assert len(observed) == report["total"] * 3
    for offset in range(0, len(observed), 3):
        stages = observed[offset:offset + 3]
        assert [name for name, _ in stages] == ["plan", "style", "review_dialogue"]
        assert stages[0][1] == stages[1][1] == stages[2][1]
    for row in report["cases"]:
        assert row["companion_profile"]["assistant_persona"] == row["persona"]
        if scenario == "companion_names" and row["case"].endswith("/rename"):
            assert row["companion_profile"]["agent_name"] == "沐沐"
        if scenario == "companion_role_switch" and row["expected"].get("switch_persona"):
            assert row["persona"] != row["case"].split("/")[0]


def test_preference_acceptance_checks_real_items_not_just_claimed_style():
    from stylist.models import Look, Product, Slot
    expected = EXPECTATIONS['preference_outfit_casual/answer']
    bad = reply().model_copy(update={"delivery": "outfit", "task": Task(no_heels=True),
        "message": "已经按你的休闲偏好搭好了。", "looks": [Look(title="休闲搭配", items=[
            Product(source="user", product_id="211", slot=Slot.TOP, styles=["优雅"]),
            Product(source="user", product_id="209", slot=Slot.SHOES)])]})
    errors = check_reply(bad, expected, ['/api/user_product/quick_edit_list'])
    assert 'selected_items_ignore_style_preference' in errors and 'selected_forbidden_item' in errors
    bad.looks[0].items = [Product(source="user", product_id="201", slot=Slot.TOP, styles=["休闲"])]
    assert not check_reply(bad, expected, ['/api/user_product/quick_edit_list'])


def test_paired_review_rejects_unproven_effect_and_invented_quotes():
    from scripts.preference_comparison import PreferenceComparison, comparison_status
    review = PreferenceComparison(meaningful_difference=False, persona_preserved=True, requirements_preserved=True,
                                  evidence_a="甲回复", evidence_b="乙回复", reason="只改了语气词")
    assert comparison_status(review, '甲回复', '乙回复') == 'failed'
    assert comparison_status(review.model_copy(update={'meaningful_difference': True}), '甲回复', '乙回复') == 'passed'
    assert comparison_status(review.model_copy(update={'evidence_a': '不存在的引文'}), '甲回复', '乙回复') == 'invalid_evidence'


@pytest.mark.asyncio
async def test_preference_inventory_resolves_style_evidence_and_avoids_real_services():
    upstream = DialogueUpstream('preference_outfit_casual')
    data = await upstream.get('/api/user_product/quick_edit_list', {})
    ids = {row['product_id'] for row in data['list']}
    assert {'201', '211', '209'} <= ids
    result = await upstream.call('product.resolve', {'items': [{'source': 'user', 'product_id': '211'}]})
    assert result['items'][0]['styles'] == [{'name': '优雅'}]
    with pytest.raises(AssertionError):
        await upstream.call('digital_twin_tryon', {})


@pytest.mark.parametrize('paired_passes,expected_exit', [(True, 0), (False, 1)])
@pytest.mark.asyncio
async def test_preference_pair_runner_checks_profiles_and_propagates_failure(tmp_path, monkeypatch, paired_passes, expected_exit):
    import json

    from scripts import evaluate_personas as runner
    from scripts.preference_comparison import PreferenceComparison

    class FixtureModel:
        def __init__(self, settings):
            pass

        async def generate(self, name, payload, result_type):
            if name == 'review_preferences':
                assert payload['a']['message'] == payload['b']['message']
                assert {payload[side]['companion_profile']['conversation_style'] for side in ('a', 'b')} == {'温柔鼓励', '直接坦诚'}
                return PreferenceComparison(meaningful_difference=paired_passes, persona_preserved=True,
                    requirements_preserved=True, evidence_a=payload['a']['visible_reply'].splitlines()[0],
                    evidence_b=payload['b']['visible_reply'].splitlines()[0], reason='模拟配对结果，仅验证验收器')
            if name == 'review_dialogue':
                return PersonaReview(persona_fit=4, naturalness=4, relevance=4, factuality=4,
                    evidence=payload['visible_reply'].splitlines()[0], reason='模拟单轮审核')
            current = CompanionProfile.model_validate(payload['companion_profile'])
            assert current.conversation_style in {'温柔鼓励', '直接坦诚'}
            if name == 'plan':
                return Plan(mode='consult', conversation_only=True, use_inventory=False)
            return Draft(message='先选一件最小的事情开始。' if current.conversation_style == '直接坦诚' else '今天辛苦了，我们慢慢来。')

    monkeypatch.setattr(runner, 'LanguageModel', FixtureModel)
    monkeypatch.setattr(runner.Settings, 'load', lambda: Settings(llm_key='fake', llm_url='https://unused.invalid', llm_model='fake'))
    output = tmp_path / 'preferences.json'
    assert await runner.run(Namespace(output=str(output), concurrency=2,
        only=['preference_tone_gentle', 'preference_tone_direct'], judge=True)) == expected_exit
    report = json.loads(output.read_text())
    assert report['accepted'] == 4
    assert len(report['preference_comparisons']) == 2
    for pair in report['preference_comparisons']:
        assert pair['status'] == ('passed' if paired_passes else 'failed')
        assert pair['cases'] == sorted(pair['cases'])


def test_preference_cases_cover_every_profile_option_and_validate_snapshots():
    """New UI/model options must acquire executable dialogue expectations."""
    from scripts.preference_dialogues import EXPECTATIONS as expected
    from scripts.preference_dialogues import SCENARIOS as scenarios
    profiles = [CompanionProfile.model_validate(row['companion_profile']) for row in expected.values()]
    schema = CompanionProfile.model_json_schema()['properties']
    for field in ['conversation_style', 'reply_detail', 'style_preferences', 'dressing_priorities', 'zodiac']:
        definition = schema[field]
        if field == 'zodiac':
            options = next(x['enum'] for x in definition['anyOf'] if 'enum' in x)
        else:
            options = definition.get('items', definition)['enum']
        observed = set()
        for profile in profiles:
            value = getattr(profile, field)
            observed.update(value if isinstance(value, list) else [value])
        assert set(options) <= observed, field
    assert {f'{scenario}/{name}' for scenario, rows in scenarios.items() for name, _, _ in rows} == set(expected)


def test_zodiac_acceptance_rejects_wrong_profile_reference():
    assert 'missing_expected_zodiac' in check_reply(reply().model_copy(update={'message': '你是白羊座。'}), {'mentioned_zodiac': '天秤座'}, [])
    assert 'missing_expected_zodiac' not in check_reply(reply().model_copy(update={'message': '聊聊天秤座的传统说法，仅作娱乐。'}), {'mentioned_zodiac': '天秤座'}, [])


@pytest.mark.asyncio
async def test_missing_style_fixture_has_no_matching_inventory():
    upstream = DialogueUpstream('preference_no_matching_style')
    rows = (await upstream.get('/api/user_product/quick_edit_list', {}))['list']
    assert rows and all({'name': '复古'} not in row.get('styles', []) for row in rows)
    full = DialogueUpstream('preference_style_04')
    assert any({'name': '复古'} in row.get('styles', []) for row in (await full.get('/api/user_product/quick_edit_list', {}))['list'])
