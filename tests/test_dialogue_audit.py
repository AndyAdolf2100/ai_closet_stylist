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
    batch = {"kind": "live_text_model_synthetic_adapters", "model": "fixture", "total": 1, "cases": [row]}
    source = tmp_path / "fixture.json"
    source.write_text(json.dumps(batch))
    output = tmp_path / "report.html"
    result = render([source], None, output)
    assert result["records"][0] == row
    html = output.read_text()
    assert "</script><script>unsafe()" not in html
    payload = html.split('<script id="report-data" type="application/json">')[1].split('</script>')[0]
    assert json.loads(payload)["records"][0] == row
    with pytest.raises(ValueError, match="Duplicate cases"):
        render([source, source], None, output)
