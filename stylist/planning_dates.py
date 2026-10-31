"""Calendar limits for multi-day outfits, independent of weather availability."""
import re
from datetime import date

from .weather import forecast_dates


def explicit_scope(message):
    if re.search(r"未来[七7]天|接下来[七7]天", message):
        return "next7"
    if re.search(r"本周|这周|本星期|这个星期", message):
        return "week"
    return None


def schedule_dates(plan, task):
    if plan.mode != "weekly" or not task.event_date or plan.weather_scope not in {"week", "next7"}:
        return []
    return forecast_dates(task.event_date, plan.weather_scope)


def schedule_problems(draft, dates):
    if not dates:
        return []
    allowed = set(dates)
    weekdays = {date.fromisoformat(day).isoweekday() for day in dates}
    problems = []
    if len(draft.looks) > len(dates):
        problems.append("planning_dates:逐日方案数量超过允许日期数量")
    texts = [draft.message]
    for look in draft.looks:
        texts.extend([look.title, look.style_name, *look.pieces, *look.why, *look.how, *look.notes])
        for weekday in re.findall(r"(?:周|星期)([一二三四五六日天])", look.title + " " + look.style_name):
            if ("一二三四五六日".find(weekday.replace("天", "日")) + 1) not in weekdays:
                problems.append("planning_dates:方案星期超出本轮日期范围")
    for text in texts:
        for day in re.findall(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)", text):
            if day not in allowed:
                problems.append("planning_dates:输出日期超出允许范围：" + day)
        for month, day in re.findall(r"(?<!\d)(\d{1,2})月(\d{1,2})[日号]", text):
            if not any(int(value[5:7]) == int(month) and int(value[8:]) == int(day) for value in dates):
                problems.append(f"planning_dates:输出日期超出允许范围：{month}月{day}日")
    return list(dict.fromkeys(problems))
