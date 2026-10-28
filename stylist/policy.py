"""Deterministic boundaries; no keyword-based routing of user intentions."""
import re

from pydantic import ValidationError

from .errors import StylistError
from .models import MAX_WEATHER_LOCATIONS, Look, Plan, Product, SessionState, Slot, Task
from .personas import weather_location_limit_message


def merge_task(state: SessionState, plan: Plan, message: str) -> Task:
    data = Task().model_dump() if plan.new_task else state.task.model_dump()
    for field, change in plan.changes.items():
        spans = [change.evidence] if isinstance(change.evidence, str) else change.evidence
        if field not in Task.model_fields or not spans or any(not s or s not in message for s in spans):
            raise StylistError("unverified_requirement", "需求解析不够明确，请换个说法；原要求已保留。", 422)
        data[field] = change.value
    if "city" in plan.changes and "itinerary" not in plan.changes:
        data["itinerary"] = []  # A newly specified single city supersedes an earlier trip.
    task = Task.model_validate(data)
    if task.itinerary:
        task.city = task.itinerary[0].city_name  # Retain the existing single-city field for compatibility.
    elif "city" in plan.changes and task.city and re.search(r"[/→、|;；]", task.city):
        raise StylistError("itinerary_required", "多地行程应逐站填写itinerary，city只能填写一个城市。", 422)
    return task


async def interpret_task(llm, payload, state, message):
    """Repair the model's extraction, rather than asking the user to repair our citation format."""
    previous = None
    validation_errors = []
    for attempt in range(2):
        data = dict(payload)
        if previous is not None:
            invalid = [field for field, change in previous.changes.items()
                       if not change.evidence or any(not span or span not in message for span in
                              ([change.evidence] if isinstance(change.evidence, str) else change.evidence))]
            data.update(previous_plan=previous.model_dump(mode="json"), invalid_evidence_fields=invalid,
                        task_validation_errors=validation_errors,
                        repair_instruction="修复抽取结果，不向用户追问内部格式问题。证据必须逐字来自本条message，禁止省略号拼接。多段原话请用字符串数组；无法精确摘录时直接引用完整原message。修正task_validation_errors指出的字段值，例如event_date只能是YYYY-MM-DD的单日日期，不能填日期范围或本周等文字。保留所有正确要求。")
        previous = await llm.generate("plan", data, Plan)
        if previous.conversation_only:
            previous = previous.model_copy(update={"mode": "consult", "use_inventory": False,
                "weather_scope": "none", "changes": {}, "new_task": False,
                "replace_slots": [], "clarification": None, "weather_only": False,
                "location_limit_exceeded": False})
        else:
            itinerary = previous.changes.get("itinerary")
            if previous.location_limit_exceeded or (
                    itinerary and isinstance(itinerary.value, list) and len(itinerary.value) > MAX_WEATHER_LOCATIONS):
                previous = previous.model_copy(update={"mode": "consult", "use_inventory": False,
                    "weather_only": True, "changes": {}, "replace_slots": [], "new_task": False,
                    "clarification": weather_location_limit_message(payload.get("assistant_persona"))})
                return previous, state.task.model_copy(deep=True)
            if previous.weather_only:
                previous = previous.model_copy(update={"mode": "consult", "use_inventory": False,
                    "replace_slots": [], "weather_scope": previous.weather_scope if previous.weather_scope != "none" else "day"})
        try:
            task = merge_task(state, previous, message)
            # A verified location correction changes the task, not an unspecified garment.
            # Explicit slot replacements and genuine clarification requests keep their path.
            if (previous.mode == "modify" and not previous.replace_slots and not previous.clarification
                    and previous.changes and set(previous.changes) <= {"city", "itinerary"}):
                has_products = any(look.items for look in state.looks)
                mode = "weekly" if state.mode == "weekly" else ("recommend" if has_products else "consult")
                previous = previous.model_copy(update={"mode": mode, "use_inventory": has_products,
                    "weather_scope": previous.weather_scope if previous.weather_scope != "none" else (
                        "week" if mode == "weekly" else "day")})
            if previous.weather_only:
                supplied = previous.changes.get("weather_policy")
                task.weather_policy = "provided" if supplied and supplied.value == "provided" else "auto"
            return previous, task
        except (StylistError, ValidationError) as exc:
            validation_errors = exc.errors(include_input=False, include_url=False) if isinstance(exc, ValidationError) else (
                [{"loc": ["city"], "msg": exc.message}] if exc.code == "itinerary_required" else [])
            if attempt == 1:
                raise StylistError("invalid_requirements", "这次没有准确整理好需求，原输入已保留，请调整表述后重试。", 422) from None


def infer_slot(class_name, secondary=""):
    text = class_name + secondary
    # Dress must precede skirts; taxonomy comes from the server, not model output.
    if any(x in text for x in ["连衣裙", "连体衣", "连体裤"]):
        return Slot.DRESS
    if any(x in text for x in ["鞋", "靴"]):
        return Slot.SHOES
    if any(x in text for x in ["外套", "大衣", "风衣", "羽绒", "夹克"]):
        return Slot.OUTER
    if any(x in text for x in ["裤", "半身裙", "下装", "裙子"]):
        return Slot.BOTTOM
    if any(x in text for x in ["上衣", "上装", "衬衫", "针织", "T恤", "t恤", "毛衣", "背心"]):
        return Slot.TOP
    if any(x in text for x in ["配饰", "包", "帽", "围巾", "项链", "手表", "首饰", "腰带", "眼镜"]):
        return Slot.ACCESSORY
    return None


def suitability(product: Product, task: Task):
    text = product.evidence_text
    reasons, warnings = [], []
    if task.no_heels and product.slot == Slot.SHOES:
        if re.search(r"高跟|中跟|猫跟|细跟|粗跟|坡跟", text):
            reasons.append("鞋跟与不穿高跟要求冲突")
        elif not re.search(r"平底|运动鞋|帆布鞋|板鞋|德训鞋|小白鞋", text):
            reasons.append("无法确认这双鞋为平底")
    for material in task.excluded_materials:
        if not product.material or product.material.strip() in {"其他", "其它", "其他材质", "未知", "不详", "混纺"}:
            reasons.append(f"材质未知，无法确认排除{material}")
        elif material in product.material:
            reasons.append(f"材质包含{material}")
    for color in task.excluded_colors:
        if not product.color:
            reasons.append(f"主色未知，无法确认排除{color}")
        elif color in product.color:
            reasons.append(f"颜色包含{color}")
    for category in task.excluded_categories:
        if category in text:
            reasons.append(f"包含禁止品类{category}")
    if task.no_bare_shoulders and product.slot in {Slot.TOP, Slot.DRESS}:
        if re.search(r"露肩|一字肩|抹胸|吊带|无肩带", text):
            reasons.append("肩部暴露与要求冲突")
        elif not re.search(r"长袖|短袖|衬衫|卫衣|套头|针织衫|毛衣", text):
            reasons.append("缺少肩部覆盖证据")
    if product.source == "system" and task.source == "wardrobe":
        reasons.append("不在个人衣橱范围")
    if product.source == "system" and task.budget_yuan is not None:
        if product.incremental_price_yuan is None:
            reasons.append("新增购买价格未知，无法确认预算")
        elif product.incremental_price_yuan > task.budget_yuan:
            reasons.append("单件超出新增购买预算")
    if product.slot == Slot.SHOES and task.walk_minutes and task.walk_minutes >= 30:
        warnings.append("长时间步行请优先选你实际穿着舒适的鞋；防滑、支撑和脚感需核对实物。")
    if product.slot == Slot.SHOES and task.temp_min is not None and task.temp_min < 15:
        if re.search(r"凉鞋|拖鞋|后空|露趾", text):
            reasons.append("低温条件下脚部覆盖不足，需另选包脚鞋")
    if product.slot == Slot.SHOES and re.search(r"雨|雪|rain|snow", task.weather_description, re.I):
        if re.search(r"网布|网面|mesh", text, re.I):
            reasons.append("雨雪天不优先选择缺少可靠防雨证据的网面鞋")
        if re.search(r"凉鞋|拖鞋|露趾", text):
            reasons.append("雨雪天优先包脚鞋，当前鞋款覆盖不足")
    return reasons, warnings


def validate_look(keys, candidates: dict[str, Product], task: Task, frozen: set[str]):
    if len(keys) != len(set(keys)) or any(key not in candidates for key in keys):
        return ["引用了不存在或重复的候选单品"]
    if not frozen <= set(keys):
        return ["修改了用户要求保留的单品"]
    items = [candidates[key] for key in keys]
    slots = [p.slot for p in items]
    problems = []
    for slot in [Slot.TOP, Slot.BOTTOM, Slot.DRESS, Slot.OUTER, Slot.SHOES]:
        if slots.count(slot) > 1:
            problems.append(f"{slot}位置重复")
    separates = Slot.TOP in slots and Slot.BOTTOM in slots
    if not (Slot.DRESS in slots or separates) or Slot.SHOES not in slots:
        problems.append("缺少完整主体衣物或鞋子")
    if Slot.DRESS in slots and (Slot.TOP in slots or Slot.BOTTOM in slots):
        problems.append("连身衣物与上下装结构冲突")
    for item in items:
        reasons, _ = suitability(item, task)
        problems.extend(reasons)
    if task.budget_yuan is not None:
        cost = sum(p.incremental_price_yuan or 0 for p in items if p.source == "system")
        if cost > task.budget_yuan:
            problems.append("新增购买合计超过预算")
    return list(dict.fromkeys(problems))


def frozen_products(looks: list[Look], replace_slots):
    if not looks:
        return []
    return [p for p in looks[0].items if p.slot not in replace_slots]
