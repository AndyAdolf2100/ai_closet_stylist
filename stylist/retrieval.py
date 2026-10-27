import asyncio

from .errors import AuthenticationExpired, StylistError
from .models import Product, ProductRef, Task
from .policy import infer_slot, suitability


def from_row(row, source, extra=None):
    data = {**(extra or {}), **row}
    category = data.get("class_name") or ""
    secondary = data.get("secondary_class_name") or ""
    slot = infer_slot(category, secondary)
    if slot is None:
        return None
    raw_id = row.get("product_id") if source == "system" else row.get("user_product_id", row.get("product_id"))
    ref = ProductRef(source=source, product_id=str(raw_id))
    colors = data.get("colors") or []
    return Product(**ref.model_dump(), slot=slot, title=data.get("title") or "",
                   class_name=category, secondary_class_name=secondary,
                   color=data.get("color") or "、".join(x["name"] for x in colors if x.get("name")),
                   material=data.get("material") or data.get("material_name") or "",
                   description=data.get("features_desc") or data.get("description") or "",
                   styles=[x["name"] for x in (data.get("styles") or []) if x.get("name")],
                   occasions=[x["name"] for x in (data.get("occasions") or []) if x.get("name")],
                   original_image=data.get("original_image") or "", cutout_image=data.get("cutout_image") or "",
                   incremental_price_yuan=0 if source == "user" else None)


async def resolve_products(mcp, refs, extras=None):
    refs = list({r.key: r for r in refs}.values())
    products = []
    extras = extras or {}
    for index in range(0, len(refs), 20):
        chunk = refs[index:index + 20]
        result = await mcp.call("product.resolve", {"items": [r.model_dump() for r in chunk]})
        requested = {r.key for r in chunk}
        for row in result["items"]:
            key = f"{row['source']}:{row['product_id']}"
            if key not in requested:
                raise StylistError("unexpected_product", "商品返回内容与请求不一致。")
            product = from_row(row, row["source"], extras.get(key))
            if product:
                products.append(product)
    return products


async def weather_for(task: Task, mcp):
    if task.weather_policy == "ignored":
        return None, []
    if task.weather_policy == "provided":
        return {"source": "user", "description": task.weather_description,
                "temp_min": task.temp_min, "temp_max": task.temp_max}, []
    if not task.city:
        return None, ["没有提供城市，本次不按实时天气筛选。"]
    try:
        cities = await mcp.call("city.resolve", {"name": task.city})
        if cities["status"] != "resolved" or cities["truncated"] or len(cities["matches"]) != 1:
            return None, ["城市尚未唯一确认，本次不按实时天气筛选；可补充省市。"]
        city = cities["matches"][0]
        params = {"city_name": city["city_name"], "province_name": city["province_name"]}
        if task.event_date:
            params["date"] = task.event_date.isoformat()
        value = await mcp.call("weather.get", params)
        return {"source": "server_mcp", **value}, []
    except AuthenticationExpired:
        raise
    except StylistError as exc:
        return None, [f"本次未获得有效天气，不按实时天气筛选（{exc.code}）。"]


async def retrieve(upstream, mcp, task, query, frozen=()):
    """Bounded retrieval; a limited pool is never presented as the whole inventory."""
    refs, extras, warnings = [], {}, []
    if task.source != "catalog":
        # This read endpoint includes all taxonomy slots and does not reset wardrobe badges.
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
            warnings.append("个人衣橱较多，本次先检查部分候选，不代表全部库存。")
    if task.source in {"catalog", "hybrid"}:
        found = False
        if task.gender:
            try:
                searches = await asyncio.gather(*[mcp.call("kb_search", {
                    "scope": "public", "gender": task.gender,
                    "query": f"{query or task.scene or task.occasion} {category}",
                    "class_name": category, "top_k": 8,
                }) for category in ["上衣", "裤子", "外套", "鞋子", "连衣裙"]])
                for search in searches:
                    for row in search.get("list") or []:
                        raw = str(row.get("id", ""))
                        if raw.isdecimal() and int(raw) > 0:
                            refs.append(ProductRef(source="system", product_id=raw))
                            found = True
            except AuthenticationExpired:
                raise
            except StylistError as exc:
                warnings.append(f"系统语义检索未完成（{exc.code}），改用有限的已发布商品候选。")
        if not found:
            result = await upstream.get("/api/product/list", {"page": 1, "page_size": 50})
            refs.extend(ProductRef(source="system", product_id=str(x["product_id"])) for x in result.get("list") or [])
            warnings.append("系统衣橱仅检查本次返回的候选，不代表全库搜索。")
    refs.extend(ProductRef(source=p.source, product_id=p.product_id) for p in frozen)
    # Preserve attributes from the current result while revalidating its identity.
    for p in frozen:
        extras.setdefault(p.key, p.model_dump())
    products = await resolve_products(mcp, refs, extras)
    valid, excluded = [], {}
    for product in products:
        reasons, caution = suitability(product, task)
        if reasons:
            for reason in reasons:
                excluded[reason] = excluded.get(reason, 0) + 1
        else:
            product.warnings = caution
            valid.append(product)
    def score(p):
        return (10 if p.source == "user" else 0) + sum(
            3 for token in [task.style, task.target_description] if token and token in p.evidence_text)
    valid.sort(key=score, reverse=True)
    # Balance slots before applying the bounded LLM context budget.
    pool, per_slot = {}, {}
    frozen_keys = {p.key for p in frozen}
    for p in valid:
        if p.key in frozen_keys or per_slot.get(p.slot, 0) < 10:
            pool[p.key] = p
            per_slot[p.slot] = per_slot.get(p.slot, 0) + 1
    return pool, warnings, excluded


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
