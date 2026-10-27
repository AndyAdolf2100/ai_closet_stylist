"""Explicit live-model regression; never run from pytest."""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from stylist.config import Settings
from stylist.errors import StylistError
from stylist.llm import LanguageModel
from stylist.models import SessionState, Task
from stylist.policy import interpret_task

CASES = [
    {"name": "negative_garment_is_not_target", "message": "今天在北京通勤，女生，158cm，希望利落有精神。室外大约8–16℃、有小雨，地铁加步行40分钟，办公室22℃。我不穿高跟鞋，也不穿羊毛，预算500元以内，优先用已有衣橱。请给我一套能直接照着穿的搭配，说明穿脱和防雨安排。以上只是这次需求。",
     "mode": "recommend", "expected": {"no_heels": True, "excluded_materials": ["羊毛"], "budget_yuan": 500, "walk_minutes": 40, "weather_policy": "provided", "target_description": None}},
    {"name": "consultation_followup", "message": "针织衫比较厚，我不想塞衣角，也不戴帽子或眼镜。保持这三件，重新给出两种穿法，不用推荐购买新衣服。",
     "state": SessionState(task=Task(scene="周末美术馆", owned_descriptions=["海军蓝针织衫", "米白直筒裤", "白色平底鞋"]), mode="consult"),
     "mode": "consult", "expected": {"scene": "周末美术馆", "owned_descriptions": ["海军蓝针织衫", "米白直筒裤", "白色平底鞋"]}},
    {"name": "ignore_weather", "message": "帮我用已有衣服搭一套休闲装，不考虑天气。", "mode": "recommend", "expected": {"weather_policy": "ignored", "source": "wardrobe"}},
    {"name": "generic_casual_request", "message": "帮我搭一套女生休闲装。", "mode": "recommend", "expected": {"gender": "女"}},
    {"name": "positive_named_garment", "message": "请用我衣橱里的黑色羊毛大衣搭一套通勤装。", "mode": "recommend", "has_target": True, "expected": {"excluded_materials": []}},
    {"name": "local_shoe_change", "message": "其他都保留，只把鞋换成平底鞋，不穿高跟鞋。",
     "state": SessionState(task=Task(scene="工作通勤"), mode="recommend"), "mode": "modify", "slots": ["shoes"], "expected": {"no_heels": True, "scene": "工作通勤"},
     "looks": [{"title": "通勤装", "items": [{"key": "user:1", "slot": "top", "name": "白衬衫"}, {"key": "user:2", "slot": "bottom", "name": "灰裤"}, {"key": "user:3", "slot": "shoes", "name": "黑高跟鞋"}]}]},
]


async def main():
    model = LanguageModel(Settings.load())
    results = []
    for case in CASES:
        state = case.get("state", SessionState())
        payload = {"now": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "message": case["message"], "current_task": state.task.model_dump(mode="json"),
            "current_mode": state.mode, "history": [], "current_looks": case.get("looks", [])}
        errors = []
        try:
            plan, task = await interpret_task(model, payload, state, case["message"])
        except StylistError as exc:
            results.append({"case": case["name"], "passed": False, "errors": [exc.code]})
            print(json.dumps(results[-1]), flush=True)
            continue
        if plan.mode != case["mode"]:
            errors.append(f"mode:{plan.mode}")
        for field, expected in case["expected"].items():
            if getattr(task, field) != expected:
                errors.append(field)
        if case.get("has_target") and not task.target_description:
            errors.append("missing_target")
        if "slots" in case and plan.replace_slots != case["slots"]:
            errors.append("replace_slots")
        results.append({"case": case["name"], "passed": not errors, "errors": errors,
                        "plan": plan.model_dump(mode="json"), "task": task.model_dump(mode="json")})
        print(json.dumps({"case": case["name"], "passed": not errors, "errors": errors}), flush=True)
        Path("var").mkdir(exist_ok=True)
        Path("var/semantics-live.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    Path("var").mkdir(exist_ok=True)
    Path("var/semantics-live.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    if not all(x["passed"] for x in results):
        raise SystemExit(1)


asyncio.run(main())
