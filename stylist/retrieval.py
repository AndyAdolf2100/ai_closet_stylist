import asyncio
import logging

from .catalog_retrieval import collect_catalog
from .errors import AuthenticationExpired, StylistError
from .models import Product, ProductRef, Task
from .personas import service_notice
from .policy import GENDER_PREFIX, infer_slot, product_gender_problems, suitability

logger = logging.getLogger(__name__)


def attribute_names(value):
    if isinstance(value, str):
        return [item.strip() for item in value.replace('，', ',').replace('、', ',').split(',') if item.strip()]
    return [item.get('name') if isinstance(item, dict) else str(item) for item in value or []
            if (item.get('name') if isinstance(item, dict) else item)]


def from_row(row, source, extra=None):
    data = {**(extra or {}), **row}
    category = data.get("class_name") or ""
    secondary = data.get("secondary_class_name") or ""
    slot = infer_slot(category, secondary)
    if slot is None:
        return None
    raw_id = row.get("product_id") if source == "system" else row.get("user_product_id", row.get("product_id"))
    ref = ProductRef(source=source, product_id=str(raw_id))
    colors = attribute_names(data.get("colors"))
    return Product(**ref.model_dump(), slot=slot, gender=data.get("gender"), title=data.get("title") or "",
                   class_name=category, secondary_class_name=secondary,
                   color=data.get("color") or "、".join(colors),
                   material=data.get("material") or data.get("material_name") or "",
                   description=data.get("features_desc") or data.get("description") or "",
                   styles=attribute_names(data.get("styles") or data.get("style")),
                   occasions=attribute_names(data.get("occasions") or data.get("occasion")),
                   original_image=data.get("original_image") or "", cutout_image=data.get("cutout_image") or "",
                   incremental_price_yuan=0 if source == "user" else None)


async def resolve_products(mcp, refs, extras=None):
    refs = list({r.key: r for r in refs}.values())
    extras = extras or {}
    semaphore = asyncio.Semaphore(3)

    async def resolve_chunk(chunk):
        async with semaphore:
            result = await mcp.call("product.resolve", {"items": [r.model_dump() for r in chunk]})
        requested = {r.key for r in chunk}
        products = []
        for row in result["items"]:
            key = f"{row['source']}:{row['product_id']}"
            if key not in requested:
                raise StylistError("unexpected_product", "商品返回内容与请求不一致。")
            product = from_row(row, row["source"], extras.get(key))
            if product:
                products.append(product)
        return products

    # Finish all sibling reads before closing the shared MCP session on any error.
    batches = await asyncio.gather(*(resolve_chunk(refs[i:i + 20]) for i in range(0, len(refs), 20)),
                                   return_exceptions=True)
    for batch in batches:
        if isinstance(batch, BaseException):
            raise batch
    return [product for batch in batches for product in batch]


async def weather_for(task: Task, mcp, persona_id=None):
    if task.weather_policy == "ignored":
        return None, []
    if task.weather_policy == "provided":
        return {"source": "user", "description": task.weather_description,
                "temp_min": task.temp_min, "temp_max": task.temp_max}, []
    if not task.city:
        return None, [service_notice(persona_id, "city_missing")]
    try:
        cities = await mcp.call("city.resolve", {"name": task.city})
        if cities["status"] != "resolved" or cities["truncated"] or len(cities["matches"]) != 1:
            return None, [service_notice(persona_id, "city_selection")]
        city = cities["matches"][0]
        params = {"city_name": city["city_name"], "province_name": city["province_name"]}
        if task.event_date:
            params["date"] = task.event_date.isoformat()
        value = await mcp.call("weather.get", params)
        return {"source": "server_mcp", **value}, []
    except AuthenticationExpired:
        raise
    except StylistError as exc:
        logger.warning("Weather fallback failed (%s)", exc.code)
        kind = {"forecast_date_past": "weather_past", "forecast_date_unavailable": "weather_date",
                "city_needs_selection": "city_selection"}.get(exc.code, "weather")
        return None, [service_notice(persona_id, kind)]


async def retrieve(upstream, mcp, task, query, frozen=(), persona_id=None, *, allow_system=False, diagnostics=None, style_preferences=()):
    """Personal-first retrieval; catalog requires separately verified permission."""
    task = task.model_copy(update={"source": "hybrid" if allow_system else "wardrobe"})
    frozen = [p for p in frozen if allow_system or p.source == "user"]
    trace = diagnostics if diagnostics is not None else {}
    trace.update({'personal': {'returned': 0, 'eligible': 0}, 'catalog': {'requested': allow_system}})
    refs, extras, warnings, excluded = [], {}, [], {}
    total = 0
    try:
        for page in range(1, 4):
            result = await upstream.get("/api/user_product/quick_edit_list",
                                        {"page": page, "page_size": 50, "is_ai_outfit": 1})
            rows = result.get("list") or []
            for row in rows:
                ref = ProductRef(source="user", product_id=str(row["user_product_id"]))
                refs.append(ref)
                extras[ref.key] = row
            total = (result.get("pagination") or {}).get("total", 0)
            if not rows or page * 50 >= total:
                break
        if total > 150:
            warnings.append(service_notice(persona_id, "inventory_partial"))
    except AuthenticationExpired:
        raise
    except StylistError:
        if not allow_system:
            raise
        trace['personal']['unavailable'] = True
        warnings.append('个人衣橱这次暂时没有取到，我先看看衣橱之外的参考款。')
    trace['personal']['returned'] = len(refs)
    refs.extend(ProductRef(source=p.source, product_id=p.product_id) for p in frozen)
    for product in frozen:
        extras.setdefault(product.key, product.model_dump())
    products = await resolve_products(mcp, refs, extras)
    frozen_keys = {p.key for p in frozen}
    valid = []
    for product in products:
        if product.key in frozen_keys and product_gender_problems(product, task):
            raise StylistError("frozen_gender_conflict",
                "原搭配中要求保留的单品与本轮穿衣性别要求冲突，无法只改其他部分。请重新生成整套，或明确调整这些单品。", 409)
        reasons, caution = suitability(product, task)
        if product.source == 'system':
            from .catalog_retrieval import category_conflicts
            reasons.extend(category_conflicts(product))
            if reasons and product.key in frozen_keys:
                raise StylistError('frozen_catalog_conflict', '需要保留的参考款属性已不符合要求，原搭配先保留，请重新选款。', 409)
        if reasons:
            for reason in reasons:
                excluded[reason] = excluded.get(reason, 0) + 1
        else:
            product.warnings = caution
            valid.append(product)
    trace['personal']['eligible'] = sum(p.source == 'user' for p in valid)
    if allow_system:
        system, cautions = await collect_catalog(upstream, mcp, task, query,
            [p for p in valid if p.source == 'user'], resolve_products, from_row, excluded, trace['catalog'], persona_id=persona_id)
        valid = list({p.key: p for p in [*valid, *system]}.values())
        warnings.extend(cautions)
    if not valid and any(reason.startswith(GENDER_PREFIX) for reason in excluded):
        warnings.append("本次查到的候选未找到同时符合穿衣性别和其他要求的单品，先给文字参考；不代表整个衣橱为空。")
    styles = [task.style] if task.style else style_preferences

    def score(p):
        # Rank before per-slot truncation, so preferences outside the first ten survive.
        style_match = any(label and label in wanted for label in p.styles for wanted in styles)
        occasion_match = any(label and label in (task.occasion or task.scene or "") for label in p.occasions)
        return (int(bool(task.gender) and p.gender in {task.gender, "男女同款"}),
                int(style_match), int(occasion_match),
                (10 if p.source == "user" else 0) + sum(
                    3 for token in [task.style, task.target_description] if token and token in p.evidence_text))
    valid.sort(key=score, reverse=True)
    pool = {p.key: p for p in valid if p.key in frozen_keys}
    # Preserve a catalog window for every slot, even when personal candidates fill the budget.
    for slot in dict.fromkeys(p.slot for p in valid):
        personal = [p for p in valid if p.slot == slot and p.source == 'user' and p.key not in pool]
        system = [p for p in valid if p.slot == slot and p.source == 'system' and p.key not in pool]
        chosen = personal[:6] + system[:4] if allow_system else personal[:10]
        identities = {p.key for p in chosen}
        chosen += [p for p in [*personal, *system] if p.key not in identities][:max(0, 10-len(chosen))]
        pool.update({p.key: p for p in chosen})
    pool = {p.key: p for p in valid if p.key in pool}
    trace['selected_pool'] = {'user': sum(p.source == 'user' for p in pool.values()),
                              'system': sum(p.source == 'system' for p in pool.values())}
    return pool, list(dict.fromkeys(warnings)), excluded


async def saved_candidates(mcp, task):
    params = {"occasion": task.occasion}
    search = await mcp.call("outfit.search-saved", params)
    items = []
    for match in search.get("matches", [])[:3]:
        result = await mcp.call("outfit.resolve", {"source": "user", "outfit_id": match["outfit_id"],
                                                   "include_presentation": True})
        for row in result["items"]:
            p = from_row(row, "user")
            if p and not suitability(p, task)[0]:
                items.append(p)
    return items
