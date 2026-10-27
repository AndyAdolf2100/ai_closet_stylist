import json
import time
import uuid
from pathlib import Path

from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.images import ImageQuoteRequest, ImageService
from stylist.llm import LanguageModel
from stylist.models import ChatRequest
from stylist.store import Store


async def run(settings, upstream):
    store = Store(settings.database)
    engine = Stylist(settings, store, LanguageModel(settings))
    results = []

    async def case(name, message, previous=None, **extra):
        request = ChatRequest(message=message, request_id="live-" + uuid.uuid4().hex,
                              conversation_id=previous.conversation_id if previous else None,
                              expected_version=previous.version if previous else 0, **extra)
        start = time.monotonic()
        try:
            reply = await engine.chat(upstream, request)
            result = {"case": name, "status": "completed", "seconds": round(time.monotonic() - start, 2),
                      "request": request.model_dump(mode="json"), "reply": reply.model_dump(mode="json")}
            results.append(result)
            print(json.dumps({"case": name, "delivery": reply.delivery, "mode": reply.mode,
                              "looks": len(reply.looks), "seconds": result["seconds"]}), flush=True)
            return reply
        except StylistError as exc:
            results.append({"case": name, "status": "failed", "code": exc.code,
                            "seconds": round(time.monotonic() - start, 2)})
            print(json.dumps({"case": name, "error": exc.code}), flush=True)
        finally:
            Path("var/live-suite.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
        return None

    consult = await case("museum_advice", "只想咨询穿搭原理，不查衣橱。我158cm，周末去美术馆，已有海军蓝针织衫、米白直筒裤、白色平底鞋。给两种气质的穿法，舒服优先，不要一味显瘦。")
    if consult:
        await case("museum_followup", "针织衫比较厚，不想塞衣角，也不戴帽子或眼镜。保持这三件，重新给两种穿法，不用推荐购买新衣服。", consult)
    await case("complex_commute", "今天在北京通勤，女生，158cm，希望利落有精神。室外8–16℃、小雨，地铁加步行40分钟，办公室22℃。我不穿高跟鞋，也不穿羊毛，预算500元以内，优先用已有衣橱。给一套能照着穿的搭配，说明穿脱和防雨安排。以上只是本次需求。")
    basic = await case("basic_commute", "帮我搭一套今天北京的女士通勤装。")
    if basic and basic.delivery == "outfit":
        await case("replace_shoes", "保留其他所有单品，只把鞋换成平底、适合步行的鞋，不穿高跟鞋。", basic)
        try:
            # Only quote if this remains a current result. Never confirm/dispatch in this suite.
            latest = store.history(await upstream.identity(), basic.conversation_id)
            if latest["version"] == basic.version:
                quote = await ImageService(store).quote(upstream, ImageQuoteRequest(
                    conversation_id=basic.conversation_id, version=basic.version))
                results.append({"case": "image_quote", "status": "quoted_not_generated", "points_cost": quote["points_cost"]})
        except StylistError as exc:
            results.append({"case": "image_quote", "status": "blocked", "code": exc.code})
    await case("ignore_weather", "帮我搭一套女生休闲装。", weather_policy="ignored")
    wedding = await case("wedding", "周六在上海参加同事婚礼，我是女宾。不要白色，不露肩，不穿高跟鞋，希望新增购买预算500元以内，尽量利用已有衣服。给得体不抢新娘风头的搭配，并说明礼仪和舒适性。")
    if wedding:
        await case("wedding_text_fallback", "先不找商品，请按刚才婚礼要求，用普通衣物给我文字方案。不要编造商品价格。", wedding)
    await case("weekly", "只做文字规划：下周一到周三在北京办公室通勤，女，平底鞋，舒适优先。已有蓝衬衫、白T恤、灰色长裤、牛仔裤、薄外套和白运动鞋，不买新衣服。给三天穿搭安排。")
    Path("var/live-suite.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    return {"suite": "finished", "completed": sum(x.get("status") == "completed" for x in results),
            "failed": sum(x.get("status") == "failed" for x in results), "artifact": "var/live-suite.json"}
