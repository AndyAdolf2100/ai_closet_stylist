import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from stylist.alerts import AlertService, normalize_feed
from stylist.config import Settings

CITY = {"city_name": "北京市", "province_name": "北京市"}
NOW = datetime(2026, 10, 27, 5, 0, tzinfo=timezone.utc)


def warning(key="rain", level="red", **overrides):
    return {"id": key, "level": level, "event": "暴雨", "title": "暴雨预警",
            "text": "气象台发布的原始防护内容。", "sender": "示例气象台", **CITY,
            "area": "示例区域", "issued_at": (NOW - timedelta(hours=1)).isoformat(),
            "expires_at": (NOW + timedelta(hours=1)).isoformat(), "status": "active", **overrides}


def feed(rows, **overrides):
    return {"observed_at": NOW.isoformat(), "complete": True, "alerts": rows, **overrides}


def test_red_yellow_priority_expiry_cancellation_and_unknown_city_are_not_all_clear():
    red = warning()
    cancelled = warning("cancel", "orange", status="cancelled", issued_at=NOW.isoformat())
    rows = [warning("yellow", "yellow"), warning("cancel", "orange"),
            warning("expired", expires_at=NOW.isoformat()), red, cancelled,
            warning("elsewhere", city_name="上海市")]
    result = normalize_feed(feed(rows), CITY, NOW)
    assert [a["id"] for a in result["alerts"]] == ["rain", "yellow"]
    assert result["alerts"][0]["hazard"] == "rain"
    assert result["status"] == "partial"


def test_empty_current_feed_is_distinct_from_missing_stale_or_malformed_data():
    assert normalize_feed(feed([]), CITY, NOW)["status"] == "ok"
    assert normalize_feed(feed([warning(level="unknown")]), CITY, NOW)["status"] == "partial"
    with pytest.raises(ValueError):
        normalize_feed(feed([], observed_at=(NOW - timedelta(minutes=16)).isoformat()), CITY, NOW)
    with pytest.raises(ValueError):
        normalize_feed({}, CITY, NOW)


@pytest.mark.parametrize("event,hazard", [("台风", "typhoon"), ("大雾", "fog"), ("寒潮", "cold"),
    ("冰雹", "hail"), ("道路结冰", "ice"), ("暴雪", "snow"), ("沙尘暴", "sand"), ("其他", "general")])
def test_disaster_image_mapping_uses_official_type(event, hazard):
    result = normalize_feed(feed([warning(event=event)]), CITY, NOW)
    assert result["alerts"][0]["hazard"] == hazard


@pytest.mark.asyncio
async def test_unconfigured_provider_is_unknown_not_no_warning():
    result = await AlertService(Settings()).lookup(CITY)
    assert result["status"] == "unavailable" and not result["alerts"]
    assert "不代表没有预警" in result["message"]


def test_local_city_catalog_has_municipality_city_not_districts():
    root = Path(__file__).parents[1]
    data = json.loads((root / 'stylist/static/china-cities.json').read_text())
    assert len(data) == 34 and sum(map(len, data.values())) > 350
    for city in ['北京市', '上海市', '天津市', '重庆市']:
        assert data[city] == [city]
    assert '杭州市' in data['浙江省'] and '西湖区' not in data['浙江省']
    assert '大兴安岭地区' in data['黑龙江省']
    assert '阿克苏地区' in data['新疆维吾尔自治区']
    for cities in data.values():
        assert len(cities) == len(set(cities))
        assert all(not x.endswith('县') for x in cities)
