"""Verified forecast dates, honest day/night resolution and user-triggered geolocation.

No precise browser coordinates enter conversations, model prompts or the database.
Public reverse geocoding is bounded to one request/second for this single process.
"""
import asyncio
import math
import os
import re
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from .errors import AuthenticationExpired, StylistError
from .models import MAX_WEATHER_LOCATIONS

TZ = ZoneInfo("Asia/Shanghai")
MUNICIPALITIES = {"CN-BJ": "北京市", "CN-SH": "上海市", "CN-TJ": "天津市", "CN-CQ": "重庆市"}


def administrative_city(address):
    """OSM's `city` can be a district. ISO level 4 identifies China's municipalities."""
    country = str(address.get("country_code") or "").lower()
    if country and country != "cn":
        raise StylistError("location_country_unsupported", "目前天气城市目录仅支持中国大陆，请手动选择可用城市。", 422)
    province = str(address.get("state") or address.get("province") or "").strip()
    iso = str(address.get("ISO3166-2-lvl4") or "").upper()
    municipality = MUNICIPALITIES.get(iso)
    # Some records have only the province name and no ISO code.
    if not municipality:
        municipality = next((name for name in MUNICIPALITIES.values()
                             if province in {name, name.removesuffix("市")}), None)
    if municipality:
        district = next((str(address[k]) for k in ("city_district", "city", "county", "borough")
                         if address.get(k) and str(address[k]).endswith(("区", "县", "旗"))
                         and str(address[k]) != "市辖区"), "")
        return municipality, municipality, district
    name = next((str(address[k]).strip() for k in ("city", "municipality", "state_district", "county", "town")
                 if address.get(k) and str(address[k]).strip()), "")
    if not name:
        # A province alone is not a weather city; never pick a provincial capital.
        raise StylistError("location_city_missing", "位置只识别到了省份，没有确认到城市，请手动填写城市。", 422)
    return name, province, ""


def today():
    return datetime.now(TZ).date()


def forecast_dates(start, scope):
    count = (7 - start.weekday()) if scope == "week" else (7 if scope == "next7" else 1)
    return [(start + timedelta(days=i)).isoformat() for i in range(count)]


def finite(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def reminders(condition, low=None, high=None, wind=None, visibility=None):
    """Forecast-based dressing tips, never presented as official disaster warnings."""
    tips = []
    def add(kind, title, text, severity="notice"):
        tips.append({"kind": kind, "title": title, "text": text, "severity": severity})
    if "雷" in condition:
        add("storm", "雷雨天，先把安全放前面", "尽量减少空旷处停留，出门前查看当地气象预警。", "important")
    if "雨" in condition:
        add("rain", "小伞准备好啦", "记得带雨具，鞋底抓地和防水要核对实物；裤脚别拖地。")
    if "雪" in condition or "冻雨" in condition:
        add("snow", "雪天，把脚下照顾好", "优先保暖包脚、实物确认防滑的鞋，留意湿滑和结冰；防水性能未知时不要冒雨雪试鞋。", "important")
    if "雾" in condition or (visibility is not None and visibility < 1000):
        add("fog", "雾气来啦，慢一点也没关系", "能见度可能受影响，尽量选容易被看见的外层，出行留足时间。")
    if "霾" in condition or "沙" in condition or "尘" in condition:
        add("air", "今天多照顾一下自己", "留意当地空气质量和出行提示，减少衣物大面积敞开。")
    levels = re.findall(r"\d+", str(wind or ""))
    if "大风" in condition or "台风" in condition or any(int(x) >= 6 for x in levels):
        add("wind", "风有点大，帮你收好小细节", "外层尽量能扣合，收好围巾、帽子与飘带；强风时别依赖雨伞，留意当地出行提醒。", "important")
    if low is not None and low <= 5:
        add("cold", "早晚低温，记得保暖", "最低温较低，早晚出门优先保暖外层与包脚鞋，室内再按体感脱减。")
    elif high is not None and high <= 15:
        add("cool", "白天也偏凉，外层别太薄", "最高温也不高，白天出门同样备好保暖外层；按活动量和室内温度灵活增减。")
    if high is not None and high >= 30:
        add("heat", "清爽一点，也记得防晒", "选轻薄透气的穿法，备水并关注当地高温提示。")
    if low is not None and high is not None and high - low >= 7:
        add("layers", "温差有点大，外套陪你出门", "早晚按较凉的情况备可穿脱外层，中午热了再减一层。")
    return tips


def normalize_day(row):
    raw_date = str(row.get("data_format", row.get("predictDate", "")))[:10]
    try:
        parsed = date.fromisoformat(raw_date)
    except ValueError:
        return None
    day = finite(row.get("temp_day", row.get("tempDay")))
    night = finite(row.get("temp_night", row.get("tempNight")))
    if day is None or night is None or not (-90 <= day <= 65 and -90 <= night <= 65):
        return None
    daytime = str(row.get("condition_day", row.get("conditionDay", "")))[:80]
    nighttime = str(row.get("condition_night", row.get("conditionNight", "")))[:80]
    if not daytime or not nighttime:
        return None
    wind_day = row.get("wind_level_day", row.get("windLevelDay"))
    wind_night = row.get("wind_level_night", row.get("windLevelNight"))
    low, high = min(day, night), max(day, night)
    return {"date": parsed.isoformat(), "weekday": "周" + "一二三四五六日"[parsed.weekday()],
            "temp_min": low, "temp_max": high, "day_temp": day, "night_temp": night,
            "condition_day": daytime, "condition_night": nighttime,
            "wind_day": wind_day, "wind_night": wind_night,
            "periods": [
                {"key": "morning", "label": "早间出门", "temp": None,
                 "condition": None, "note": "暂无早间逐小时预报，参考日夜温差备可穿脱外层。"},
                {"key": "day", "label": "白天", "temp": day, "condition": daytime,
                 "note": "白天预报，非指定时刻实况。"},
                {"key": "evening", "label": "晚间参考", "temp": night, "condition": nighttime,
                 "note": "采用夜间预报，不等于傍晚某一小时温度。"}],
            "reminders": reminders(daytime + "、" + nighttime, low, high,
                                   str(wind_day or "") + " " + str(wind_night or ""))}


class WeatherService:
    def __init__(self):
        self._reverse_lock = asyncio.Lock()
        self._reverse_at = 0.0
        self._reverse_cache = {}
        self._forecast_cache = {}

    async def resolve(self, upstream, city_name, province_name=""):
        async with upstream.mcp() as mcp:
            args = {"name": city_name}
            if province_name:
                args["province_name"] = province_name
            data = await mcp.call("city.resolve", args)
        if data.get("status") == "not_found" and not data.get("matches") and not data.get("truncated"):
            raise StylistError("weather_city_unsupported", f"暂时还查不到{city_name}的天气。", 422)
        if data.get("status") != "resolved" or data.get("truncated") or len(data.get("matches", [])) != 1:
            raise StylistError("city_needs_selection", "这个地点还需要确认，请填写更完整的省市名称。", 422)
        return data["matches"][0]

    async def forecast_itinerary(self, upstream, stops, scope="day", start=None):
        """Read each stop independently; one unavailable city cannot replace another's forecast."""
        if len(stops) > MAX_WEATHER_LOCATIONS:
            raise StylistError("weather_location_limit", "一次最多查10个地区的天气。", 422)
        semaphore = asyncio.Semaphore(3)

        async def lookup(stop):
            async with semaphore:
                location = {"city_name": stop.city_name, "province_name": stop.province_name,
                            "event_date": (stop.event_date or start or today()).isoformat()}
                try:
                    forecast = await self.forecast(upstream, stop.city_name, stop.province_name,
                        "day" if stop.event_date else scope, stop.event_date or start)
                except AuthenticationExpired:
                    raise
                except StylistError as exc:
                    return {**location, "status": "unavailable", "reason": exc.code, "forecast": None}
                return {**location, "city_name": forecast["city_name"],
                        "province_name": forecast["province_name"], "status": "ok", "forecast": forecast}

        locations = await asyncio.gather(*(lookup(stop) for stop in stops))
        return {"source": "itinerary_forecast", "locations": locations, "timezone": "Asia/Shanghai",
                "complete": all(location["status"] == "ok" and not location["forecast"].get("missing_dates")
                                for location in locations)}

    async def locate(self, upstream, latitude, longitude):
        # City-level precision is sufficient. Never forward the browser's full precision.
        lat, lon = round(latitude, 2), round(longitude, 2)
        key = (lat, lon)
        async with self._reverse_lock:
            cached = self._reverse_cache.get(key)
            if cached and cached[0] > time.monotonic():
                address = cached[1]
            else:
                await asyncio.sleep(max(0, 1.05 - (time.monotonic() - self._reverse_at)))
                try:
                    async with httpx.AsyncClient(timeout=12, trust_env=False) as client:
                        response = await client.get(os.getenv("STYLIST_GEOCODER_URL", "https://nominatim.openstreetmap.org/reverse"),
                            params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10,
                                    "accept-language": "zh-CN"},
                            headers={"User-Agent": "AiClosetStylist/0.2 (user-requested city weather)"})
                        response.raise_for_status()
                        address = response.json()["address"]
                        if not isinstance(address, dict):
                            raise ValueError("invalid address")
                    if len(self._reverse_cache) >= 128:
                        self._reverse_cache.clear()
                    self._reverse_cache[key] = (time.monotonic() + 1800, address)
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    raise StylistError("location_unavailable", "暂时没能把位置转成城市，可以手动填写城市继续。", 503) from exc
                finally:
                    self._reverse_at = time.monotonic()
        name, province, district = administrative_city(address)
        city = await self.resolve(upstream, name, province)
        return {"city_name": city["city_name"], "province_name": city["province_name"],
                "district_name": district,
                "source": "nominatim", "coordinate_system": "wgs84",
                "attribution": "© OpenStreetMap contributors", "attribution_url": "https://www.openstreetmap.org/copyright",
                "notice": "已转成城市；精确坐标不会写入对话。请确认城市后使用。"}

    async def forecast(self, upstream, city_name, province_name="", scope="day", start=None):
        start = start or today()
        wanted = forecast_dates(start, scope)
        if start < today():
            raise StylistError("forecast_date_past", "过去日期不使用今天预报代替，请选择今天或未来日期。", 422)
        city = await self.resolve(upstream, city_name, province_name)
        key = (city["city_name"], city["province_name"])
        cached = self._forecast_cache.get(key)
        if cached and cached[0] > time.monotonic():
            rows, fetched_at = cached[1], cached[2]
        else:
            result = await upstream.forecast(city)
            rows = [d for row in (result.get("list") or []) if isinstance(row, dict) and (d := normalize_day(row))]
            if not rows:
                raise StylistError("forecast_invalid", "预报数据不完整，暂时不能据此安排穿搭。", 503)
            fetched_at = datetime.now(TZ).isoformat()
            if len(self._forecast_cache) >= 128:
                self._forecast_cache.clear()
            self._forecast_cache[key] = (time.monotonic() + 600, rows, fetched_at)
        days = [d for day in wanted for d in rows if d["date"] == day][:7]
        missing = [d for d in wanted if not any(row["date"] == d for row in days)]
        warnings = ["当前数据为白天／夜间预报，暂无早间逐小时、风力及能见度数据；不能据此确认没有大风或大雾。"]
        if missing:
            warnings.append("以下日期没有取到有效预报，不作天气保证：" + "、".join(missing))
        if not days:
            raise StylistError("forecast_date_unavailable", "这个日期还没有有效预报，可以调整日期后重试。", 422)
        return {"source": "aicloset_forecast", "city_name": city["city_name"],
                "province_name": city["province_name"], "timezone": "Asia/Shanghai", "scope": scope,
                "fetched_at": fetched_at, "resolution": "day_night", "requested_dates": wanted,
                "missing_dates": missing, "days": days, "warnings": warnings,
                "notice": "这是穿搭出行提醒，不是官方气象灾害预警；临出门请再核对当地最新天气。"}


def apply_forecast(task, forecast):
    effective = task.model_copy(deep=True)
    reports = [location["forecast"] for location in forecast["locations"] if location.get("forecast")] if (
        forecast.get("source") == "itinerary_forecast") else [forecast]
    days = [day for report in reports for day in report.get("days", [])]
    if days:
        effective.temp_min = min(d["temp_min"] for d in days)
        effective.temp_max = max(d["temp_max"] for d in days)
        effective.weather_description = "；".join(
            report.get("city_name", "") + " " + d["date"] + " " + d["condition_day"] + "／" + d["condition_night"]
            for report in reports for d in report.get("days", []))
    return effective
