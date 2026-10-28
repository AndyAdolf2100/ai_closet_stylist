"""Checkpointed read-only styling graph; image writes remain outside automatic replay."""
import asyncio
import hashlib
import json
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
from .personas import itinerary_weather_message, progress_message, unsupported_city_message
from .policy import frozen_products, interpret_task, suitability, validate_look
from .progress import report
from .retrieval import retrieve, saved_candidates, weather_for
from .weather import WeatherService, apply_forecast


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

        async def understand(data):
            state = SessionState.model_validate(data["session"])
            today = datetime.now(ZoneInfo("Asia/Shanghai"))
            report("understanding", progress_message(request.assistant_persona, "understanding"))
            plan, task = await interpret_task(self.llm, {
                "now": today.isoformat(), "message": request.message,
                "assistant_persona": request.assistant_persona,
                "current_task": state.task.model_dump(mode="json"), "current_mode": state.mode,
                "history": state.messages[-12:],
                "last_business_intent": last_business_intent(state.messages),
                "current_looks": [{"title": x.title, "pieces": x.pieces,
                                   "items": [{"key": p.key, "slot": p.slot, "name": p.display_name} for p in x.items],
                                   "how": x.how} for x in state.looks],
            }, state, request.message)
            if request.weather_policy is not None and not plan.conversation_only and not plan.weather_only:
                task.weather_policy = request.weather_policy
            if request.source is not None and not plan.conversation_only:
                task.source = request.source
            if request.location and "city" not in plan.changes and not task.itinerary and not plan.conversation_only:
                task.city = request.location.city_name
            if task.event_date is None and not plan.conversation_only:
                task.event_date = today.date()
            if task.weather_policy == "ignored" and not plan.conversation_only:
                task.temp_min = task.temp_max = None
                task.weather_description = ""
            frozen = []
            if plan.mode == "modify":
                if not state.looks or not state.looks[0].items:
                    # A purely textual previous look is advice, not an editable DB selection.
                    plan.mode = "consult"
                elif not plan.replace_slots:
                    plan.clarification = "你想调整哪一部分？我会保留其余衣物。"
                else:
                    frozen = frozen_products(state.looks, plan.replace_slots)
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
                    warnings.append("还不知道你在哪座城市。可以点「使用当前位置」或手动选城市，才能结合真实天气；这次先给穿法参考。")
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
                        warnings.append(f"完整预报暂时没取到（{exc.code}），不能保证早晚或整周天气。")
                        if scope == "day":
                            try:
                                async with upstream.mcp() as mcp:
                                    weather, cautions = await weather_for(task, mcp)
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
                                                                 plan.search_query, frozen)
                        warnings.extend(cautions)
                        if plan.mode == "recommend" and not task.target_description:
                            try:
                                for p in await saved_candidates(mcp, effective_task):
                                    pool.setdefault(p.key, p)
                            except AuthenticationExpired:
                                raise
                            except StylistError as exc:
                                warnings.append(f"本次未复用已保存搭配（{exc.code}）。")
                except AuthenticationExpired:
                    raise
                except StylistError as exc:
                    pool, service_gap = {}, True
                    warnings.append(f"本次衣橱读取未完成（{exc.code}），以下先给文字参考。")
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
            draft_payload = {
                "assistant_persona": request.assistant_persona,
                "conversation_only": plan.conversation_only,
                "weather_only": plan.weather_only,
                "message": request.message, "task": task.model_dump(mode="json"), "mode": plan.mode,
                "history": state.messages[-8:], "weather": weather,
                "candidates": [{"key": p.key, **p.model_dump(exclude={"original_image", "cutout_image"})}
                               for p in pool.values()],
                "frozen_keys": [p.key for p in frozen], "replace_slots": plan.replace_slots,
                "concept_fallback": concept, "warnings": warnings,
                "excluded_candidate_reasons": rejected,
                "attribute_context": attribute_context(pool.values()),
            }
            return draft_payload

        async def style_node(data):
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
                looks.append(Look(title=look.title, items=products, pieces=look.pieces,
                                  why=look.why, how=look.how, notes=list(dict.fromkeys(notes))))
            selected = any(look.items for look in looks)
            if plan.mode == "modify" and not selected:
                warnings.append("本次未完成真实单品替换，原搭配仍保留；当前内容为穿法参考。")
            delivery = "advice" if plan.mode == "consult" or not plan.use_inventory else ("outfit" if selected else "concept")
            if delivery == "concept":
                warnings.append("以下为文字参考，尚未匹配成可确认的真实商品方案。")
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
                        "looks": [{"title": x.title, "pieces": x.pieces, "how": x.how,
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
