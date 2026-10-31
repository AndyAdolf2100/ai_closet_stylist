from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.models import ChatRequest, Draft, LookDraft, Plan, Task
from stylist.planning_dates import schedule_dates, schedule_problems
from stylist.store import Store


@pytest.mark.parametrize("day,count,last", [
    ("2026-10-26", 7, "2026-11-01"),
    ("2026-10-31", 2, "2026-11-01"),
    ("2026-11-01", 1, "2026-11-01"),
    ("2026-12-31", 4, "2027-01-03"),
])
def test_calendar_week_not_rolling_seven(day, count, last):
    task = Task(event_date=date.fromisoformat(day))
    dates = schedule_dates(Plan(mode="weekly", weather_scope="week"), task)
    assert len(dates) == count and dates[-1] == last
    assert len(schedule_dates(Plan(mode="weekly", weather_scope="next7"), task)) == 7


def test_detect_out_of_week_dates_in_text_and_cards():
    dates = ["2026-10-31", "2026-11-01"]
    assert schedule_problems(Draft(message="11月2日穿衬衫"), dates)
    assert schedule_problems(Draft(message="2026-11-02 穿衬衫"), dates)
    assert schedule_problems(Draft(message="安排如下", looks=[
        LookDraft(title="周一", why=["通勤"], how=["叠穿"])]), dates)
    assert not schedule_problems(Draft(message="10月31日和11月1日"), dates)


@pytest.mark.asyncio
@pytest.mark.parametrize("repair_success", [True, False])
async def test_week_scope_weather_opt_out_repair_and_followup(tmp_path, monkeypatch, repair_success):
    class Clock:
        @classmethod
        def now(cls, tz):
            # Shanghai is already Saturday while UTC is still Friday.
            return datetime(2026, 10, 30, 16, 30, tzinfo=ZoneInfo("UTC")).astimezone(tz)
    monkeypatch.setattr("stylist.engine.datetime", Clock)

    class Model:
        def __init__(self):
            self.payloads = []
        async def generate(self, name, payload, result_type):
            if name == "plan":
                # Deliberately wrong rolling window; runtime must normalize it.
                return Plan(mode="weekly", weather_scope="next7", use_inventory=False)
            self.payloads.append(payload)
            return Draft(message="2026-10-31 和 2026-11-01 的文字穿法。" if
                         repair_success and "validation_errors" in payload else "2026-11-02 穿衬衫。")
    class Upstream:
        async def identity(self):
            return "synthetic-weekly"
    model = Model()
    engine = Stylist(Settings(), Store(str(tmp_path / "week.db")), model)
    request = ChatRequest(message="本周只给文字穿搭，不考虑天气", weather_policy="ignored",
                          request_id="calendar-week-test")
    if not repair_success:
        with pytest.raises(StylistError, match="outfit_validation_failed"):
            await engine.chat(Upstream(), request)
    else:
        reply = await engine.chat(Upstream(), request)
        assert "2026-11-02" not in reply.message
        await engine.chat(Upstream(), ChatRequest(message="继续按刚才的日期，简洁一点，不考虑天气",
            weather_policy="ignored", request_id="calendar-followup",
            conversation_id=reply.conversation_id, expected_version=reply.version))
    assert all(p["planning_dates"] == ["2026-10-31", "2026-11-01"] for p in model.payloads)
    assert "validation_errors" in model.payloads[-1]
