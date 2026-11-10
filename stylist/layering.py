"""Keep cold-weather layering in actual selections, not only in prose."""
import re

from .models import Slot
from .policy import suitability

OUTER_WORDS = re.compile(r"外套|外层|外搭|大衣|风衣|夹克|棉服|羽绒服")


def layering_requirements(task, plan, weather):
    # Explicit boundaries and partial edits must never be overridden by weather.
    if (task.weather_policy == 'ignored' or plan.mode == 'consult'
            or plan.conversation_only or plan.weather_only
            or (plan.mode == 'modify' and Slot.OUTER not in plan.replace_slots)
            or any(x in {'外套', '外搭', '外层'} for x in task.excluded_categories)
            or re.search(r'只在室内|全天室内|不出门', task.scene)):
        return []
    # Route forecasts need city/date pairing; never apply one city's low to another.
    if task.itinerary:
        return []
    days = (weather or {}).get('days', [])
    if not days and plan.mode != 'weekly':
        days = [{'date': task.event_date.isoformat() if task.event_date else '',
                 'temp_min': task.temp_min, 'temp_max': task.temp_max}]
    requirements = []
    for day in days:
        low, high = day.get('temp_min'), day.get('temp_max')
        reasons = []
        if low is not None and low <= 5:
            reasons.append('早晚低温')
        if high is not None and high <= 15:
            reasons.append('白天偏凉')
        if low is not None and high is not None and high - low >= 7 and low < 18:
            reasons.append('温差较大，早晚偏凉')
        if reasons:
            requirements.append({'date': day.get('date', ''), 'temp_min': low,
                                 'temp_max': high, 'reason': '、'.join(reasons)})
    return requirements


def layering_problems(draft, pool, task, plan, weather, dates=()):
    requirements = layering_requirements(task, plan, weather)
    if not requirements:
        return []
    eligible = [p for p in pool.values() if p.slot == Slot.OUTER and not suitability(p, task)[0]]
    problems = []
    for i, look in enumerate(draft.looks):
        # Weekly look order is checked separately against planning_dates.
        date = str(dates[i]) if i < len(dates) else ''
        applicable = [r for r in requirements if plan.mode != 'weekly' or r['date'] == date]
        if not applicable or any(pool[k].slot == Slot.OUTER for k in look.selected_keys if k in pool):
            continue
        if eligible:
            problems.append(f'天气外层：第{i + 1}套需要可穿脱外层，候选中有合规外套，必须实际选入selected_keys，'
                            '保留上传衣物及冻结项；不能仅在how或notes中说加外套。厚度保暖性能未知时如实说明。')
        elif not any(OUTER_WORDS.search(piece) for piece in look.reference_pieces):
            problems.append(f'天气外层：第{i + 1}套需要外层，但本次候选没有合规外套；保留已有衣物，'
                            '把保暖外套列入reference_pieces并说明未匹配，不虚构衣物或图片。')
    return problems


def ensure_weather_references(draft, task, plan, weather, dates=()):
    """Keep a missing cold-weather layer explicit in a text-only fallback."""
    requirements = layering_requirements(task, plan, weather)
    if not requirements:
        return draft
    result = draft.model_copy(deep=True)
    for i, look in enumerate(result.looks):
        date = str(dates[i]) if i < len(dates) else ''
        applicable = [r for r in requirements if plan.mode != 'weekly' or r['date'] == date]
        if not applicable or any(OUTER_WORDS.search(piece) for piece in look.reference_pieces):
            continue
        look.reference_pieces.append('保暖外套（本次候选未匹配）')
    return result
