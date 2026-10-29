"""Checkpointed read-only styling graph; image writes remain outside automatic replay."""
import asyncio
import hashlib
import json
import logging
import operator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, TypedDict
from zoneinfo import ZoneInfo

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy, interrupt

from .alerts import AlertService
from .errors import AuthenticationExpired, StylistError
from .grounding import PREFIX, attribute_claim_problems, attribute_context, ground_attribute_fallback
from .models import Draft, Look, Plan, Reply, SessionState, Task
from .personas import (
    itinerary_weather_message,
    progress_message,
    service_notice,
    technical_detail_message,
    unsupported_city_message,
)
from .policy import (
    REPLACEMENT_PREFIX,
    frozen_products,
    interpret_task,
    suitability,
    unchanged_replacement_problems,
    validate_look,
)
from .preferences import preferred_pool, wardrobe_requested
from .progress import report
from .retrieval import retrieve, saved_candidates, weather_for
from .weather import WeatherService, apply_forecast

logger = logging.getLogger(__name__)


class RunState(TypedDict, total=False):
    completed_nodes: Annotated[list[str], operator.add]
    session: dict
    session_id: str
    plan: dict
    task: dict
    effective_task: dict
    weather: dict | None
    warnings: list
    rejected: dict
    pool: dict
    frozen: list
    service_gap: bool
    draft: dict
    problems: list
    reply: dict
    cancelled: bool


def last_business_intent(messages):
    """Use saved server reply metadata; a preserved outfit is not the latest request type."""
    for message in reversed(messages):
        if message.get("role") != "assistant":
            continue
        try:
            reply = json.loads(message["content"])
        except (ValueError, TypeError, KeyError):
            continue
        if not isinstance(reply, dict) or reply.get("conversation_only"):
            continue
        if isinstance(reply.get("weather_only"), bool):
            return "weather" if reply["weather_only"] else "styling"
    return None


def retryable(exc):
    return isinstance(exc, StylistError) and exc.code in {
        "model_timeout", "model_unavailable", "model_http_429", "model_http_502", "model_http_503", "model_http_504"}


class Stylist:
    def __init__(self, settings, store, llm):
        self.settings, self.store, self.llm = settings, store, llm
        if store.postgres and settings.checkpoint_database and not settings.checkpoint_database.startswith(("postgres://", "postgresql://")):
            raise ValueError("PostgreSQL 会话必须搭配共享 PostgreSQL 检查点。")
        self.weather = WeatherService()
        self.alerts = AlertService(settings)

    @asynccontextmanager
    async def checkpoints(self):
        url = self.settings.checkpoint_database or (self.store.path if self.store.postgres else self.store.path + ".checkpoints")
        if url.startswith(("postgres://", "postgresql://")):
            async with AsyncPostgresSaver.from_conn_string(url) as saver:
                yield saver
        else:
            async with AsyncSqliteSaver.from_conn_string(url) as saver:
                yield saver

    @staticmethod
    def thread(owner, request):
        digest = hashlib.sha256((owner + ":" + request.request_id).encode()).hexdigest()
        return {"configurable": {"thread_id": "sty-v1-" + digest}}

    def graph(self, upstream, request, saver):
        from .models import Product

        def unpack(data):
            return Plan.model_validate(data["plan"]), Task.model_validate(data["task"])

        def selected_looks(state):
            if request.selected_look_index is None:
                return state.looks[:1]
            if request.selected_look_index >= len(state.looks):
                raise StylistError("look_not_found", "这套搭配暂时找不到了，请打开最新对话再选一下。", 409)
            return [state.looks[request.selected_look_index]]

        async def understand(data):
            state = SessionState.model_validate(data["session"])
            today = datetime.now(ZoneInfo("Asia/Shanghai"))
            report("understanding", progress_message(request.assistant_persona, "understanding"))
            plan, task = await interpret_task(self.llm, {
                "now": today.isoformat(), "message": request.message,
                "assistant_persona": request.assistant_persona,
                "companion_profile": request.companion_profile.model_dump(mode="json") if request.companion_profile else None,
                "current_task": state.task.model_dump(mode="json"), "current_mode": state.mode,
                "history": state.messages[-12:],
                "last_business_intent": last_business_intent(state.messages),
                "selected_location": request.location.model_dump(mode="json") if request.location else None,
                "selected_look_index": request.selected_look_index,
                "current_looks": [{"title": x.title, "style_name": x.style_name, "pieces": x.pieces,
                                   "items": [{"key": p.key, "slot": p.slot, "name": p.display_name} for p in x.items],
                                   "how": x.how} for x in state.looks],
            }, state, request.message)
            if (plan.mode == "consult" and not plan.conversation_only and not plan.weather_only
                    and not plan.technical_question and wardrobe_requested(request.message, state.messages)):
                plan.mode = "recommend"
                plan.use_inventory = True
            if (request.companion_profile and plan.use_profile_gender and task.gender is None
                    and not plan.conversation_only and not plan.weather_only):
                task.gender = request.companion_profile.user_gender
            if plan.location_limit_exceeded:
                return {"plan": plan.model_dump(mode="json"), "task": task.model_dump(mode="json"), "frozen": []}
            # System catalog selection is temporarily disabled, including legacy requests/history.
            if not plan.conversation_only:
                task.source = "wardrobe"
            explicit_city = plan.changes.get("city")
            explicit_route = plan.changes.get("itinerary")
            if (request.location and not (explicit_city and explicit_city.value)
                    and not (explicit_route and explicit_route.value)
                    and not plan.conversation_only and (plan.weather_only or not task.itinerary)):
                task.city = request.location.city_name
                if plan.weather_only:
                    task.itinerary = []
            if plan.weather_only and "event_date" not in plan.changes:
                task.event_date = today.date()
            if task.event_date is None and not plan.conversation_only:
                task.event_date = today.date()
            if (task.weather_policy == "ignored" or (plan.weather_only and task.weather_policy == "auto")) and not plan.conversation_only:
                task.temp_min = task.temp_max = None
                task.weather_description = ""
            frozen = []
            if plan.mode == "modify":
                current = selected_looks(state)
                if not current or not current[0].items:
                    # A purely textual previous look is advice, not an editable DB selection.
                    plan.mode = "consult"
                elif not plan.replace_slots:
                    plan.clarification = "你想调整哪一部分？我会保留其余衣物。"
                else:
                    frozen = frozen_products(current, plan.replace_slots)
            return {"plan": plan.model_dump(mode="json"), "task": task.model_dump(mode="json"),
                    "frozen": [p.model_dump(mode="json") for p in frozen]}

        def approval(data):
            if request.confirm_plan and not data["plan"].get("conversation_only") and not data["plan"].get("weather_only"):
                approved = interrupt({"kind": "plan_confirmation", "message": "请确认这次穿搭需求，再继续生成。",
                                      "task": data["task"]})
                return {"cancelled": approved is not True}
            return {"cancelled": False}

        async def weather_node(data):
            plan, task = unpack(data)
            weather, warnings = None, []
            effective_task = task.model_copy(deep=True)
            service_gap = False
            needs_weather = plan.mode != "consult" or plan.weather_scope != "none"
            if needs_weather and task.weather_policy != "ignored":
                report("weather", progress_message(request.assistant_persona, "weather"))
                if task.weather_policy == "provided":
                    weather = {"source": "user", "description": task.weather_description,
                               "temp_min": task.temp_min, "temp_max": task.temp_max}
                elif task.itinerary:
                    # The route, not the browser's selected city, determines these lookups.
                    task.temp_min = task.temp_max = None
                    task.weather_description = ""
                    weather = await self.weather.forecast_itinerary(upstream, task.itinerary,
                        plan.weather_scope if plan.weather_scope != "none" else "day", task.event_date)
                    unavailable = []
                    for location in weather["locations"]:
                        if location["status"] == "ok":
                            forecast = location["forecast"]
                            forecast["official_warnings"] = await self.alerts.lookup(forecast)
                            warnings.extend(forecast["city_name"] + "：" + tip for tip in forecast["warnings"])
                        else:
                            reason = location.pop("reason")
                            unavailable.append(reason)
                            location["message"] = itinerary_weather_message(
                                request.assistant_persona, location["city_name"], reason)
                            warnings.append(location["message"])
                    # Never inherit a prior city's temperatures when a route only partially resolves.
                    effective_task.temp_min = effective_task.temp_max = None
                    effective_task.weather_description = ""
                    effective_task = apply_forecast(effective_task, weather)
                    if len(unavailable) == len(task.itinerary) and all(
                            reason == "weather_city_unsupported" for reason in unavailable):
                        plan.clarification = " ".join(warnings)
                        return {"plan": plan.model_dump(mode="json"), "task": task.model_dump(mode="json"),
                                "effective_task": effective_task.model_dump(mode="json"),
                                "weather": weather, "warnings": warnings, "service_gap": False}
                elif not task.city:
                    warnings.append(service_notice(request.assistant_persona, "city_missing"))
                else:
                    scope = plan.weather_scope if plan.weather_scope != "none" else ("week" if plan.mode == "weekly" else "day")
                    province = request.location.province_name if request.location and request.location.city_name == task.city else ""
                    try:
                        weather = await self.weather.forecast(upstream, task.city, province, scope, task.event_date)
                        weather["official_warnings"] = await self.alerts.lookup(weather)
                        effective_task = apply_forecast(task, weather)
                        warnings.extend(weather["warnings"])
                    except AuthenticationExpired:
                        raise
                    except StylistError as exc:
                        if exc.code == "weather_city_unsupported":
                            plan.clarification = unsupported_city_message(request.assistant_persona, task.city)
                            task.temp_min = task.temp_max = None
                            task.weather_description = ""
                            effective_task.temp_min = effective_task.temp_max = None
                            effective_task.weather_description = ""
                            return {"plan": plan.model_dump(mode="json"), "task": task.model_dump(mode="json"),
                                    "effective_task": effective_task.model_dump(mode="json"),
                                    "weather": None, "warnings": [], "service_gap": False}
                        if exc.code == "city_needs_selection" and plan.weather_only:
                            plan.clarification = itinerary_weather_message(request.assistant_persona, task.city, exc.code)
                            return {"plan": plan.model_dump(mode="json"), "task": task.model_dump(mode="json"),
                                    "effective_task": effective_task.model_dump(mode="json"),
                                    "weather": None, "warnings": [], "service_gap": False}
                        logger.warning("Weather forecast failed (%s)", exc.code)
                        kind = {"forecast_date_unavailable": "weather_date", "city_needs_selection": "city_selection"}.get(exc.code, "weather")
                        warnings.append(service_notice(request.assistant_persona, kind))
                        if scope == "day":
                            try:
                                async with upstream.mcp() as mcp:
                                    weather, cautions = await weather_for(task, mcp, request.assistant_persona)
                                warnings.extend(cautions)
                                if weather and weather.get("source") == "server_mcp":
                                    effective_task.temp_min = effective_task.temp_max = weather["temp"]
                                    effective_task.weather_description = weather["condition"]
                            except AuthenticationExpired:
                                raise
                            except StylistError:
                                weather = None
            return {"task": task.model_dump(mode="json"),
                    "effective_task": effective_task.model_dump(mode="json"), "weather": weather,
                    "warnings": warnings, "service_gap": service_gap}

        async def retrieve_node(data):
            plan, task = unpack(data)
            effective_task = Task.model_validate(data["effective_task"])
            warnings = list(data["warnings"])
            frozen = [Product.model_validate(x) for x in data["frozen"]]
            pool, rejected, service_gap = {}, {}, data["service_gap"]
            if plan.mode != "consult" and plan.use_inventory:
                report("wardrobe", progress_message(request.assistant_persona, "wardrobe"))
                try:
                    async with upstream.mcp() as mcp:
                        pool, cautions, rejected = await retrieve(upstream, mcp, effective_task,
                                                                 plan.search_query, frozen, request.assistant_persona)
                        warnings.extend(cautions)
                        if plan.mode == "recommend" and not task.target_description:
                            try:
                                for p in await saved_candidates(mcp, effective_task):
                                    pool.setdefault(p.key, p)
                            except AuthenticationExpired:
                                raise
                            except StylistError as exc:
                                logger.warning("Saved outfits unavailable (%s)", exc.code)
                                warnings.append(service_notice(request.assistant_persona, "saved_outfits"))
                except AuthenticationExpired:
                    raise
                except StylistError as exc:
                    pool, service_gap = {}, True
                    logger.warning("Wardrobe read failed (%s)", exc.code)
                    warnings.append(service_notice(request.assistant_persona, "inventory"))
            profile = request.companion_profile
            styles = [task.style] if task.style else (profile.style_preferences if profile and plan.use_profile_preferences else [])
            pool, missing = preferred_pool(pool, styles, frozen)
            if pool and missing:
                names = "、".join(missing)
                warnings.append((f"这次候选里暂未找到明确标为{names}的衣物，我会用现有单品给你接近的搭配参考。"
                                 if request.assistant_persona == "male_calm_v1" else
                                 f"这次候选里暂时没有明确标为{names}的衣物，我先用现有单品给你一点接近的搭配灵感。"))
            return {"pool": {key: p.model_dump(mode="json") for key, p in pool.items()},
                    "warnings": warnings, "rejected": rejected, "service_gap": service_gap}

        def draft_payload(data):
            plan, task = unpack(data)
            state = SessionState.model_validate(data["session"])
            pool = {key: Product.model_validate(p) for key, p in data["pool"].items()}
            frozen = [Product.model_validate(x) for x in data["frozen"]]
            service_gap, weather, warnings, rejected = (data[k] for k in ("service_gap", "weather", "warnings", "rejected"))
            # A partial or absent candidate pool must not force a fabricated outfit.
            concept = plan.mode != "consult" and plan.use_inventory and (service_gap or not pool)
            current = selected_looks(state) if plan.mode == "modify" else state.looks[:1]
            original_targets = {p.key for p in current[0].items if p.slot in plan.replace_slots} if current and plan.mode == "modify" else set()
            replacement_options = {slot.value: [p.key for p in pool.values() if p.slot == slot and p.key not in original_targets]
                                   for slot in plan.replace_slots} if plan.mode == "modify" else {}
            draft_payload = {
                "now": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                "assistant_persona": request.assistant_persona,
                "companion_profile": request.companion_profile.model_dump(mode="json") if request.companion_profile else None,
                "expression_guidance": ({
                    "直接坦诚": "先用第一句话给具体可执行的下一步，再简短解释和关心；不要先铺一段安慰，不命令或冷硬。",
                    "温柔鼓励": "先具体接住本轮感受，再给轻一点的鼓励和选择空间，不急着安排任务。",
                    "轻松幽默": "场合合适时用一点自然幽默，不强行搞笑或嘲笑用户。",
                }.get(request.companion_profile.conversation_style, "沿用当前基础人格")
                    if request.companion_profile else "沿用当前基础人格"),
                "conversation_only": plan.conversation_only,
                "weather_only": plan.weather_only,
                "message": request.message, "task": task.model_dump(mode="json"), "mode": plan.mode,
                "history": state.messages[-8:], "weather": weather,
                "candidates": [{"key": p.key, **p.model_dump(exclude={"original_image", "cutout_image"})}
                               for p in pool.values() if p.key not in original_targets],
                "replacement_options": replacement_options,
                "frozen_keys": [p.key for p in frozen], "replace_slots": plan.replace_slots,
                "concept_fallback": concept, "warnings": warnings,
                "excluded_candidate_reasons": rejected,
                "attribute_context": attribute_context(pool.values()),
                "current_selection": [{"key": p.key, "slot": p.slot, "title": p.title}
                                      for p in current[0].items] if current else [],
            }
            return draft_payload

        async def style_node(data):
            if data["plan"].get("technical_question"):
                return {"draft": Draft(message=technical_detail_message(request.assistant_persona)).model_dump(mode="json")}
            if not data["plan"].get("conversation_only"):
                report("styling", progress_message(request.assistant_persona, "styling"))
            draft = await self.llm.generate("style", draft_payload(data), Draft)
            if data["plan"].get("conversation_only") or data["plan"].get("weather_only"):
                draft = draft.model_copy(update={"looks": []})
            if data["plan"].get("weather_only"):
                draft = draft.model_copy(update={"follow_ups": []})
            return {"draft": draft.model_dump(mode="json")}

        def validate_node(data):
            if not data["plan"].get("conversation_only"):
                report("checking", progress_message(request.assistant_persona, "checking"))
            problems = self.check_draft(Draft.model_validate(data["draft"]),
                {key: Product.model_validate(p) for key, p in data["pool"].items()},
                Task.model_validate(data["effective_task"]),
                [Product.model_validate(x) for x in data["frozen"]], data["plan"]["mode"])
            if not data["plan"].get("conversation_only") and not data["plan"].get("weather_only"):
                problems.extend(attribute_claim_problems(Draft.model_validate(data["draft"]),
                    {key: Product.model_validate(p) for key, p in data["pool"].items()}))
            if data["plan"]["mode"] == "modify":
                state = SessionState.model_validate(data["session"])
                problems.extend(unchanged_replacement_problems(Draft.model_validate(data["draft"]),
                    selected_looks(state), Plan.model_validate(data["plan"]).replace_slots,
                    {key: Product.model_validate(p) for key, p in data["pool"].items()}))
            return {"problems": problems}

        async def repair_node(data):
            attribute_only = all(problem.startswith(PREFIX) for problem in data["problems"])
            instruction = ("只修正缺少依据的文字，原选款已经通过结构和禁穿检查，保留原造型数量及每套selected_keys；"
                           "不要因尺寸或功能未知就清空衣物，改为具体的试穿核对、选款目标或未知说明。"
                           if attribute_only else
                           "只修正不合格的选择和文字；没有合法组合就给明确标为文字参考的方案，selected_keys留空。")
            draft = await self.llm.generate("style", {**draft_payload(data), "validation_errors": data["problems"],
                "previous_draft": data["draft"], "instruction": instruction}, Draft)
            if attribute_only:
                original = Draft.model_validate(data["draft"])
                if [look.selected_keys for look in draft.looks] != [look.selected_keys for look in original.looks]:
                    draft = ground_attribute_fallback(original,
                        {key: Product.model_validate(p) for key, p in data["pool"].items()}, request.assistant_persona)
            repaired = {**data, "draft": draft.model_dump(mode="json")}
            problems = validate_node(repaired)["problems"]
            if any(problem.startswith(REPLACEMENT_PREFIX) for problem in problems):
                options = draft_payload(data)["replacement_options"]
                kind = "replacement_failed" if any(options.values()) else "replacement"
                draft = Draft(message=service_notice(request.assistant_persona, kind))
                repaired["draft"] = draft.model_dump(mode="json")
                problems = validate_node(repaired)["problems"]
            if problems and all(problem.startswith(PREFIX) for problem in problems):
                draft = ground_attribute_fallback(draft,
                    {key: Product.model_validate(p) for key, p in data["pool"].items()}, request.assistant_persona)
                repaired["draft"] = draft.model_dump(mode="json")
                problems = validate_node(repaired)["problems"]
            if problems:
                raise StylistError("outfit_validation_failed", "这次选款未通过要求检查，原搭配已保留。", 422)
            return {"draft": repaired["draft"], "problems": []}

        def deliver_node(data):
            plan, task = unpack(data)
            if plan.clarification or data.get("cancelled"):
                return {"reply": Reply(conversation_id=data["session_id"], version=request.expected_version + 1,
                    mode=plan.mode, delivery="clarification", message=plan.clarification or "已取消本次生成。",
                    weather_only=plan.weather_only, weather=data.get("weather"), task=task).model_dump(mode="json")}
            cid = data["session_id"]
            draft = Draft.model_validate(data["draft"])
            pool = {key: Product.model_validate(p) for key, p in data["pool"].items()}
            effective_task = Task.model_validate(data["effective_task"])
            weather, warnings = data["weather"], list(data["warnings"])
            looks = []
            for look in draft.looks:
                products = [pool[key] for key in look.selected_keys]
                notes = list(look.notes)
                for p in products:
                    notes.extend(suitability(p, effective_task)[1])
                looks.append(Look(title=look.title, style_name=look.style_name, items=products, pieces=look.pieces,
                                  why=look.why, how=look.how, notes=list(dict.fromkeys(notes))))
            selected = any(look.items for look in looks)
            if plan.mode == "modify" and not selected:
                warnings.append(service_notice(request.assistant_persona, "original_retained"))
            delivery = "advice" if plan.mode == "consult" or not plan.use_inventory else ("outfit" if selected else "concept")
            if delivery == "concept":
                warnings.append(service_notice(request.assistant_persona, "concept"))
            reply = Reply(conversation_id=cid, version=request.expected_version + 1, mode=plan.mode,
                          delivery=delivery, conversation_only=plan.conversation_only,
                          weather_only=plan.weather_only,
                          message=draft.message, task=task, looks=looks, weather=weather,
                          retained_items=([Product.model_validate(p) for p in data["frozen"]]
                                          if plan.mode == "modify" and not selected else []),
                          warnings=list(dict.fromkeys(warnings)), follow_ups=draft.follow_ups)
            return {"reply": reply.model_dump(mode="json")}

        builder = StateGraph(RunState)
        for name, node in [("understand", understand), ("approval", approval), ("weather", weather_node),
                           ("retrieve", retrieve_node), ("style", style_node), ("validate", validate_node),
                           ("repair", repair_node), ("deliver", deliver_node)]:
            async def tracked(data, _node=node, _name=name):
                import inspect
                value = _node(data)
                result = await value if inspect.isawaitable(value) else value
                return {**result, "completed_nodes": [_name]}
            builder.add_node(name, tracked, retry_policy=RetryPolicy(max_attempts=2, retry_on=retryable)
                             if name in {"understand", "style", "repair"} else None)
        builder.add_edge(START, "understand")
        builder.add_conditional_edges("understand", lambda d: "deliver" if d["plan"]["clarification"] else "approval")
        builder.add_conditional_edges("approval", lambda d: "deliver" if d["cancelled"] else "weather")
        builder.add_conditional_edges("weather", lambda d: "deliver" if d["plan"]["clarification"] else "retrieve")
        builder.add_edge("retrieve", "style")
        builder.add_edge("style", "validate")
        builder.add_conditional_edges("validate", lambda d: "repair" if d["problems"] else "deliver")
        builder.add_edge("repair", "deliver")
        builder.add_edge("deliver", END)
        return builder.compile(checkpointer=saver)

    async def chat(self, upstream, request, decision=None):
        owner = await upstream.identity()
        cid, claim, state, replay = await asyncio.to_thread(self.store.reserve, owner, request)
        if replay:
            return replay
        async def heartbeat():
            while True:
                await asyncio.sleep(10)
                await asyncio.to_thread(self.store.renew, owner, cid, claim)
        pulse = asyncio.create_task(heartbeat())
        try:
            async with self.checkpoints() as saver:
                if self.store.postgres:
                    # A lease protects DB commits; a session lock also prevents stale
                    # workers from writing graph checkpoints after another Pod takes over.
                    lock_id = int(self.thread(owner, request)["configurable"]["thread_id"][-15:], 16)
                    row = await (await saver.conn.execute("SELECT pg_try_advisory_lock(%s) AS locked", (lock_id,))).fetchone()
                    if not row["locked"]:
                        raise StylistError("request_in_progress", "原任务仍在执行，请稍候重连。", 409)
                graph = self.graph(upstream, request, saver)
                config = self.thread(owner, request)
                snapshot = await graph.aget_state(config)
                if snapshot.values and (snapshot.values["session_id"] != cid or
                                        SessionState.model_validate(snapshot.values["session"]) != state):
                    raise StylistError("run_context_changed", "任务上下文已变化，请重新发起。", 409)
                paused = any(t.interrupts for t in snapshot.tasks)
                if decision is not None and not paused:
                    raise StylistError("run_not_waiting", "当前任务不在等待确认。", 409)
                if paused and decision is None:
                    output = snapshot.values
                else:
                    value = Command(resume=decision) if paused else (None if snapshot.values else {
                        "session": state.model_dump(mode="json"), "session_id": cid})
                    output = await graph.ainvoke(value, config, durability="sync")
                if "reply" not in output:
                    return Reply(conversation_id=cid, version=request.expected_version, mode=output["plan"]["mode"],
                        delivery="clarification", message="请确认这次穿搭需求，再继续生成。",
                        task=Task.model_validate(output["task"]), pending_confirmation=True, request_id=request.request_id)
                reply = Reply.model_validate(output["reply"])
                task, plan = Task.model_validate(output["task"]), Plan.model_validate(output["plan"])
                if not plan.conversation_only:
                    state.task = task
                    if not plan.weather_only:
                        state.mode = plan.mode
                if reply.delivery != "clarification" and not plan.conversation_only and not plan.weather_only:
                    # Failed replacement advice does not silently overwrite the current real outfit.
                    if not (plan.mode == "modify" and reply.delivery == "concept"):
                        state.looks = reply.looks
                state.messages = (state.messages + [
                    {"role": "user", "content": request.message},
                    {"role": "assistant", "content": json.dumps({"message": reply.message,
                        "weather_only": reply.weather_only, "conversation_only": reply.conversation_only,
                        "follow_ups": reply.follow_ups,
                        "looks": [{"title": x.title, "style_name": x.style_name, "pieces": x.pieces, "how": x.how,
                                   "items": [p.display_name for p in x.items]} for x in reply.looks]}, ensure_ascii=False)},
                ])[-16:]
                await asyncio.to_thread(self.store.finish, owner, request, claim, state, reply)
                return reply
        finally:
            pulse.cancel()
            await asyncio.gather(pulse, return_exceptions=True)
            await asyncio.to_thread(self.store.release, owner, cid, claim)

    @staticmethod
    def check_draft(draft, pool, task, frozen, mode):
        problems = []
        for look in draft.looks:
            if mode == "consult" and look.selected_keys:
                problems.append("纯咨询不能选择数据库商品")
            elif look.selected_keys:
                problems.extend(validate_look(look.selected_keys, pool, task, {p.key for p in frozen}))
        return list(dict.fromkeys(problems))
