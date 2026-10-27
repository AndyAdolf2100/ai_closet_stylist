import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .alerts import AlertService
from .errors import AuthenticationExpired, StylistError
from .models import Draft, Look, Reply
from .policy import frozen_products, interpret_task, suitability, validate_look
from .progress import report
from .retrieval import retrieve, saved_candidates, weather_for
from .weather import WeatherService, apply_forecast


class Stylist:
    def __init__(self, settings, store, llm):
        self.settings, self.store, self.llm = settings, store, llm
        self.weather = WeatherService()
        self.alerts = AlertService(settings)

    async def chat(self, upstream, request):
        # Authentication is checked against Go on every request, before local state is read.
        owner = await upstream.identity()
        cid, claim, state, replay = await asyncio.to_thread(self.store.reserve, owner, request)
        if replay:
            return replay
        try:
            today = datetime.now(ZoneInfo("Asia/Shanghai"))
            report("understanding", "我是衣衣，先把你的安排和偏好认真记下来。")
            plan, task = await interpret_task(self.llm, {
                "now": today.isoformat(), "message": request.message,
                "current_task": state.task.model_dump(mode="json"), "current_mode": state.mode,
                "history": state.messages[-12:],
                "current_looks": [{"title": x.title, "pieces": x.pieces,
                                   "items": [{"key": p.key, "slot": p.slot, "name": p.display_name} for p in x.items],
                                   "how": x.how} for x in state.looks],
            }, state, request.message)
            if request.weather_policy is not None:
                task.weather_policy = request.weather_policy
            if request.source is not None:
                task.source = request.source
            if request.location and "city" not in plan.changes:
                task.city = request.location.city_name
            if task.event_date is None:
                task.event_date = today.date()
            if task.weather_policy == "ignored":
                task.temp_min = task.temp_max = None
                task.weather_description = ""
            weather, warnings, rejected, pool = None, [], {}, {}
            frozen = []
            if plan.mode == "modify":
                if not state.looks or not state.looks[0].items:
                    # A purely textual previous look is advice, not an editable DB selection.
                    plan.mode = "consult"
                elif not plan.replace_slots:
                    plan.clarification = "你想调整哪一部分？我会保留其余衣物。"
                else:
                    frozen = frozen_products(state.looks, plan.replace_slots)
            if plan.clarification:
                reply = Reply(conversation_id=cid, version=request.expected_version + 1, mode=plan.mode,
                              delivery="clarification", message=plan.clarification, task=task)
            else:
                effective_task = task.model_copy(deep=True)
                service_gap = False
                needs_weather = plan.mode != "consult" or plan.weather_scope != "none"
                if needs_weather and task.weather_policy != "ignored":
                    report("weather", "我来核对出门那天的天气，早晚和雨雪都会留意。")
                    if task.weather_policy == "provided":
                        weather = {"source": "user", "description": task.weather_description,
                                   "temp_min": task.temp_min, "temp_max": task.temp_max}
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
                if plan.mode != "consult" and plan.use_inventory:
                    report("wardrobe", "天气和偏好整理好了，接着看看衣橱里有哪些合适的衣服。" if weather else "我去看看衣橱里有哪些合适的衣服，会保留你的禁忌。")
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
                # A partial or absent candidate pool must not force a fabricated outfit.
                concept = plan.mode != "consult" and plan.use_inventory and (service_gap or not pool)
                draft_payload = {
                    "message": request.message, "task": task.model_dump(mode="json"), "mode": plan.mode,
                    "history": state.messages[-8:], "weather": weather,
                    "candidates": [{"key": p.key, **p.model_dump(exclude={"original_image", "cutout_image"})}
                                   for p in pool.values()],
                    "frozen_keys": [p.key for p in frozen], "replace_slots": plan.replace_slots,
                    "concept_fallback": concept, "warnings": warnings,
                    "excluded_candidate_reasons": rejected,
                }
                report("styling", "正在把配色、层次和具体穿法搭在一起，让你能直接照着穿。")
                draft = await self.llm.generate("style", draft_payload, Draft)
                report("checking", "最后再核对一下：有没有漏掉你的要求，换装有没有动到其他衣服。")
                problems = self.check_draft(draft, pool, effective_task, frozen, plan.mode)
                if problems:
                    draft = await self.llm.generate("style", {**draft_payload, "validation_errors": problems,
                        "instruction": "只修正不合格的选择；没有合法组合就给明确标为文字参考的方案，selected_keys留空。"}, Draft)
                    problems = self.check_draft(draft, pool, effective_task, frozen, plan.mode)
                    if problems:
                        raise StylistError("outfit_validation_failed", "这次选款未通过要求检查，原搭配已保留，请重试或改为文字咨询。", 422)
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
                              delivery=delivery, message=draft.message, task=task, looks=looks, weather=weather,
                              warnings=list(dict.fromkeys(warnings)), follow_ups=draft.follow_ups)
            state.task, state.mode = task, plan.mode
            if reply.delivery != "clarification":
                # Failed replacement advice does not silently overwrite the current real outfit.
                if not (plan.mode == "modify" and reply.delivery == "concept"):
                    state.looks = reply.looks
            state.messages = (state.messages + [
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": json.dumps({"message": reply.message,
                    "looks": [{"title": x.title, "pieces": x.pieces, "how": x.how,
                               "items": [p.display_name for p in x.items]} for x in reply.looks]}, ensure_ascii=False)},
            ])[-16:]
            await asyncio.to_thread(self.store.finish, owner, request, claim, state, reply)
            return reply
        except BaseException:
            await asyncio.to_thread(self.store.release, owner, cid, claim)
            raise

    @staticmethod
    def check_draft(draft, pool, task, frozen, mode):
        problems = []
        for look in draft.looks:
            if mode == "consult" and look.selected_keys:
                problems.append("纯咨询不能选择数据库商品")
            elif look.selected_keys:
                problems.extend(validate_look(look.selected_keys, pool, task, {p.key for p in frozen}))
        return list(dict.fromkeys(problems))
