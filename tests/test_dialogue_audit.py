import json

import pytest

from scripts.exploratory_dialogues import EXPECTATIONS, SCENARIOS, ExploratoryUpstream
from scripts.render_dialogue_report import render
from stylist.models import Reply, Task


def test_exploration_matrix_has_checks_for_every_turn():
    assert set(EXPECTATIONS) == {f"{name}/{turn}" for name, rows in SCENARIOS.items() for turn, _, _ in rows}
    assert len(SCENARIOS) >= 30


@pytest.mark.asyncio
async def test_exploration_reports_missing_destination_evidence():
    upstream = ExploratoryUpstream("explore_multi_city_day")
    response = Reply(conversation_id="sty_" + "1" * 32, version=1, mode="consult", delivery="advice",
                     message="测试回复", task=Task())
    await upstream.forecast({"city_name": "上海市"})
    assert upstream.check(response, {"weather_cities": ["上海市", "三亚市"]}) == ["missing_destination_weather"]
    await upstream.forecast({"city_name": "三亚市"})
    assert upstream.check(response, {"weather_cities": ["上海市", "三亚市"]}) == []


def test_html_report_preserves_raw_question_and_answer_without_executing_markup(tmp_path):
    row = {"case": "male_calm_v1/single/test", "persona": "male_calm_v1",
           "message": "</script><script>unsafe()</script>", "reply": {"message": "原始回答：<不要改写>"}, "errors": []}
    batch = {"kind": "live_text_model_synthetic_adapters", "model": "fixture", "total": 1, "cases": [row],
             "preference_comparisons": [{"group": "tone", "status": "failed", "evidence_a": "原始回答"}]}
    source = tmp_path / "fixture.json"
    source.write_text(json.dumps(batch))
    output = tmp_path / "report.html"
    result = render([source], None, output)
    assert result["preference_comparisons"] == batch["preference_comparisons"]
    assert result["records"][0] == row
    html = output.read_text()
    assert "</script><script>unsafe()" not in html
    payload = html.split('<script id="report-data" type="application/json">')[1].split('</script>')[0]
    assert json.loads(payload)["records"][0] == row
    with pytest.raises(ValueError, match="Duplicate cases"):
        render([source, source], None, output)


@pytest.mark.asyncio
async def test_targeted_rereview_retains_passed_rows_and_first_failed_score(tmp_path, monkeypatch):
    from argparse import Namespace

    from scripts import review_dialogue_results as reviewer
    from scripts.dialogue_validation import PersonaReview
    from stylist.config import Settings

    calls = []

    class Model:
        def __init__(self, settings):
            pass

        async def generate(self, name, payload, result_type):
            calls.append(payload)
            assert payload['companion_profile']['zodiac'] == '天秤座'
            assert payload['reply_parts']['follow_ups'] == ['帮我调整鞋子']
            return PersonaReview(persona_fit=4, naturalness=4, relevance=4, factuality=4,
                                 evidence='合成回答', reason='结构化复审测试')

    monkeypatch.setattr(reviewer, 'LanguageModel', Model)
    monkeypatch.setattr(reviewer.Settings, 'load', lambda: Settings(llm_key='fake', llm_url='https://unused.invalid', llm_model='fake'))
    response = Reply(conversation_id='sty_' + '1' * 32, version=1, mode='consult', delivery='advice',
                     message='合成回答', follow_ups=['帮我调整鞋子'], task=Task()).model_dump(mode='json')
    rows = [{'case': f'male_calm_v1/test/{i}', 'persona': 'male_calm_v1', 'message': '测试',
             'companion_profile': {'zodiac': '天秤座'}, 'reply': response,
             'automatic_errors': [], 'errors': [] if i == 0 else ['persona_review_failed'],
             'persona_review': {'status': 'passed' if i == 0 else 'failed'}} for i in range(2)]
    src, out = tmp_path / 'source.json', tmp_path / 'reviewed.json'
    src.write_text(json.dumps({'kind': 'live_text_model_synthetic_adapters', 'cases': rows}))
    assert await reviewer.run(Namespace(input=str(src), output=str(out), concurrency=2, only_failed=True)) == 0
    result = json.loads(out.read_text())
    assert len(calls) == 1
    assert result['cases'][0]['review_reused'] is True
    assert result['cases'][1]['initial_persona_review']['status'] == 'failed'
    assert result['cases'][1]['reply'] == response
    assert json.loads(src.read_text())['cases'] == rows
