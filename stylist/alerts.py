"""Official warning feed adapter. No warning level is inferred from ordinary forecasts."""
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

LEVELS = {"red": 4, "orange": 3, "yellow": 2, "blue": 1}
HAZARDS = [("台风", "typhoon"), ("龙卷", "tornado"), ("雷", "thunder"), ("冰雹", "hail"),
           ("道路结冰", "ice"), ("冻雨", "ice"), ("雪", "snow"), ("暴雨", "rain"),
           ("洪", "flood"), ("山洪", "flood"), ("大风", "wind"), ("沙", "sand"),
           ("尘", "sand"), ("雾", "fog"), ("霾", "fog"), ("高温", "heat"),
           ("寒", "cold"), ("低温", "cold"), ("霜冻", "cold"), ("干旱", "drought"), ("火", "fire")]


class OfficialWarning(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(min_length=1, max_length=200)
    level: Literal["red", "orange", "yellow", "blue"]
    event: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=12000)
    sender: str = Field(min_length=1, max_length=200)
    city_name: str = Field(min_length=1, max_length=80)
    province_name: str = Field(min_length=1, max_length=80)
    area: str = Field(min_length=1, max_length=500)
    issued_at: AwareDatetime
    expires_at: AwareDatetime | None = None
    status: Literal["active", "cancelled", "expired"]
    source_url: str = Field(default="", max_length=2000)


def normalize_feed(payload, city, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(payload, dict) or not isinstance(payload.get("alerts"), list):
        raise ValueError("invalid warning feed")
    observed_at = TypeAdapter(AwareDatetime).validate_python(payload.get("observed_at"))
    if not now - timedelta(minutes=15) <= observed_at <= now + timedelta(minutes=5):
        raise ValueError("warning feed is not current")
    invalid, latest = False, {}
    for raw in payload["alerts"]:
        try:
            alert = OfficialWarning.model_validate(raw)
        except ValidationError:
            invalid = True
            continue
        if alert.city_name != city["city_name"] or alert.province_name != city["province_name"]:
            invalid = True
            continue
        if alert.issued_at > now + timedelta(minutes=5):
            invalid = True
            continue
        if alert.id not in latest or alert.issued_at >= latest[alert.id].issued_at:
            latest[alert.id] = alert
    result = []
    for alert in latest.values():
        if alert.status != "active" or (alert.expires_at and alert.expires_at <= now):
            continue
        row = alert.model_dump(mode="json")
        row["hazard"] = next((kind for word, kind in HAZARDS if word in alert.event), "general")
        parsed = urlsplit(row["source_url"])
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            row["source_url"] = ""
        result.append(row)
    result.sort(key=lambda x: (LEVELS[x["level"]], x["issued_at"]), reverse=True)
    complete = payload.get("complete") is True and not invalid
    return {"city_name": city["city_name"], "province_name": city["province_name"],
            "status": "ok" if complete else "partial", "alerts": result,
            "observed_at": observed_at.isoformat(), "checked_at": now.isoformat(),
            "message": "" if complete else "预警数据可能不完整，请同时查看当地气象台发布。"}


class AlertService:
    def __init__(self, settings):
        self.settings = settings

    async def lookup(self, city):
        unavailable = {"city_name": city["city_name"], "province_name": city["province_name"],
                       "status": "unavailable", "alerts": [], "checked_at": datetime.now(timezone.utc).isoformat(),
                       "message": "官方预警信息暂未接通，请留意当地气象台发布；这不代表没有预警。"}
        endpoint = urlsplit(self.settings.alerts_url)
        if endpoint.scheme != "https" or not endpoint.netloc or endpoint.username or endpoint.password:
            return unavailable
        try:
            headers = {"Authorization": "Bearer " + self.settings.alerts_key} if self.settings.alerts_key else {}
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                response = await client.get(self.settings.alerts_url,
                    params={"city_name": city["city_name"], "province_name": city["province_name"]}, headers=headers)
                response.raise_for_status()
                return normalize_feed(response.json(), city)
        except (httpx.HTTPError, ValueError, TypeError, ValidationError):
            return unavailable
