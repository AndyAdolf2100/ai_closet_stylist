from contextlib import asynccontextmanager
from datetime import date

import httpx
import pytest

from stylist.errors import StylistError
from stylist.models import Task
from stylist.weather import (
    WeatherService,
    administrative_city,
    apply_forecast,
    forecast_dates,
    normalize_day,
    reminders,
)


def test_week_stops_at_sunday_and_next7_is_distinct():
    start = date(2026, 10, 30)
    assert forecast_dates(start, "week") == ["2026-10-30", "2026-10-31", "2026-11-01"]
    assert len(forecast_dates(start, "next7")) == 7


def test_morning_is_not_fabricated_from_night_forecast():
    day = normalize_day({"data_format": "2026-10-27", "temp_day": 20, "temp_night": 10,
                         "condition_day": "晴", "condition_night": "小雨"})
    assert day["periods"][0]["temp"] is None
    assert day["periods"][0]["condition"] is None
    assert day["night_temp"] == 10
    assert {t["kind"] for t in day["reminders"]} == {"rain", "layers"}
    assert normalize_day({"data_format": "2026-10-27", "temp_day": "nan", "temp_night": 1}) is None


def test_combined_hazards_keep_serious_advice_without_fake_all_clear():
    tips = reminders("雨夹雪、大雾、雷雨", -2, 8, "5-6级", 500)
    assert {t["kind"] for t in tips} >= {"rain", "snow", "fog", "wind", "cold", "layers", "storm"}
    assert reminders("晴", 18, 22) == []
    assert "wind" not in {t["kind"] for t in reminders("阴", 18, 22, "3-4级")}


@pytest.mark.parametrize("low,high,expected", [
    (6, 12, {"cool"}),  # Saturday: colder daytime, but low > 5 and range < 7.
    (4, 20, {"cold", "layers"}),
    (2, 17, {"cold", "layers"}),
    (9, 15, {"cool"}),
    (9, 15.1, set()),
    (5, 12, {"cold", "layers"}),  # Do not duplicate cool/cold advice.
    (None, 12, {"cool"}),
    (None, None, set()),
])
def test_temperature_tips_cover_cool_daytime_and_threshold_edges(low, high, expected):
    assert {tip["kind"] for tip in reminders("多云", low, high)} == expected


def test_beijing_saturday_forecast_has_specific_cool_day_tip():
    day = normalize_day({"data_format": "2026-10-31", "temp_day": 12, "temp_night": 6,
                         "condition_day": "多云", "condition_night": "多云"})
    assert day["weekday"] == "周六"
    assert [tip["kind"] for tip in day["reminders"]] == ["cool"]
    assert "白天也偏凉" in day["reminders"][0]["title"]


class FakeUpstream:
    def __init__(self, rows):
        self.rows, self.calls = rows, 0

    @asynccontextmanager
    async def mcp(self):
        class MCP:
            async def call(self, name, args):
                assert name == "city.resolve"
                return {"status": "resolved", "truncated": False, "matches": [
                    {"city_name": "上海市", "province_name": "上海市", "city_id": 1}]}
        yield MCP()

    async def forecast(self, city):
        self.calls += 1
        return {"list": self.rows}


@pytest.mark.parametrize("resolution,code", [
    ({"status": "not_found", "matches": [], "truncated": False}, "weather_city_unsupported"),
    ({"status": "ambiguous", "matches": [{}, {}], "truncated": False}, "city_needs_selection"),
    ({"status": "not_found", "matches": [], "truncated": True}, "city_needs_selection"),
])
@pytest.mark.asyncio
async def test_city_not_supported_is_distinct_from_ambiguous_or_truncated_results(resolution, code):
    class Upstream:
        @asynccontextmanager
        async def mcp(self):
            class MCP:
                async def call(self, name, args):
                    assert name == "city.resolve"
                    return resolution
            yield MCP()
    with pytest.raises(StylistError) as error:
        await WeatherService().resolve(Upstream(), "奥克兰")
    assert error.value.code == code


@pytest.mark.asyncio
async def test_dates_are_matched_not_assumed_by_row_position_and_cache_retains_fetch_time(monkeypatch):
    monkeypatch.setattr("stylist.weather.today", lambda: date(2026, 10, 27))
    up = FakeUpstream([
        {"data_format": "2026-10-29", "temp_day": 15, "temp_night": 6, "condition_day": "小雨", "condition_night": "雾"},
        {"data_format": "2026-10-27", "temp_day": 22, "temp_night": 14, "condition_day": "晴", "condition_night": "晴"}])
    service = WeatherService()
    week = await service.forecast(up, "上海", scope="week")
    assert [d["date"] for d in week["days"]] == ["2026-10-27", "2026-10-29"]
    assert "2026-10-28" in week["missing_dates"]
    day = await service.forecast(up, "上海")
    assert up.calls == 1 and day["fetched_at"] == week["fetched_at"]
    task = apply_forecast(Task(), week)
    assert task.temp_min == 6 and "雾" in task.weather_description
    with pytest.raises(StylistError, match="forecast_date_past"):
        await service.forecast(up, "上海", start=date(2026, 10, 26))


@pytest.mark.asyncio
async def test_reverse_geocoder_receives_only_rounded_coordinates_and_no_auth(monkeypatch):
    seen = []
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, url, params, headers):
            seen.append((params, headers))
            return httpx.Response(200, json={"address": {"city": "上海市", "state": "上海市"}},
                                  request=httpx.Request("GET", url))
    monkeypatch.setattr("stylist.weather.httpx.AsyncClient", Client)
    service = WeatherService()
    result = await service.locate(FakeUpstream([]), 31.230478, 121.473892)
    assert result["city_name"] == "上海市"
    assert "latitude" not in result and "longitude" not in result
    assert seen[0][0]["lat"] == 31.23 and seen[0][0]["lon"] == 121.47
    assert "Authorization" not in seen[0][1]
    await service.locate(FakeUpstream([]), 31.23048, 121.47389)
    assert len(seen) == 1


@pytest.mark.parametrize("code,city", [("CN-BJ", "北京市"), ("CN-TJ", "天津市"), ("CN-SH", "上海市"), ("CN-CQ", "重庆市")])
def test_municipality_iso_overrides_district_in_city_field(code, city):
    # Real Beijing response has city=东城区 and NO state at zoom 10.
    assert administrative_city({"city": "某区", "ISO3166-2-lvl4": code, "country_code": "cn"}) == (city, city, "某区")


def test_province_only_does_not_silently_choose_a_capital():
    with pytest.raises(StylistError, match="location_city_missing"):
        administrative_city({"state": "浙江省", "country_code": "cn"})
    assert administrative_city({"state": "重庆市", "city": "渝中区"}) == ("重庆市", "重庆市", "渝中区")
    assert administrative_city({"ISO3166-2-lvl4": "CN-CQ", "city": "大溪沟街道"}) == ("重庆市", "重庆市", "")
    assert administrative_city({"state": "浙江省", "state_district": "杭州市", "county": "西湖区"}) == ("杭州市", "浙江省", "")
    with pytest.raises(StylistError, match="location_country_unsupported"):
        administrative_city({"city": "London", "country_code": "gb"})


@pytest.mark.asyncio
async def test_beijing_reverse_response_uses_municipality_for_authoritative_weather_lookup(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, url, **kwargs):
            return httpx.Response(200, json={"address": {"city": "东城区", "ISO3166-2-lvl4": "CN-BJ", "country_code": "cn"}},
                                  request=httpx.Request("GET", url))
    class Upstream:
        @asynccontextmanager
        async def mcp(self):
            class MCP:
                async def call(self, name, args):
                    assert name == "city.resolve"
                    assert args == {"name": "北京市", "province_name": "北京市"}
                    return {"status": "resolved", "truncated": False, "matches": [
                        {"city_name": "北京市", "province_name": "北京市"}]}
            yield MCP()
    monkeypatch.setattr("stylist.weather.httpx.AsyncClient", Client)
    result = await WeatherService().locate(Upstream(), 39.90, 116.40)
    assert result["city_name"] == "北京市" and result["district_name"] == "东城区"
