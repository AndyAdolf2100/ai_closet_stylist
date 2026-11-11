"""Read-only single-product discovery; never compose outfits or start image jobs."""
from typing import Literal

from pydantic import Field

from .errors import StylistError
from .models import Model, ProductRef, Task
from .policy import suitability
from .retrieval import resolve_products


class ProductSearchSelection(Model):
    scope: Literal["garment", "shoes", "accessory", "any"] = "any"
    selected_keys: list[str] = Field(default_factory=list, max_length=6)


async def search_products(upstream, llm, request, task, history):
    refs, total = {}, 0
    for page in range(1, 4):
        # Discovery includes items the user disabled for automatic outfit generation.
        result = await upstream.get('/api/user_product/quick_edit_list', {'page': page, 'page_size': 50})
        rows = result.get('list') or []
        for row in rows:
            ref = ProductRef(source='user', product_id=str(row['user_product_id']))
            refs[ref.key] = ref
        total = (result.get('pagination') or {}).get('total', 0)
        if not rows or page * 50 >= total:
            break
    async with upstream.mcp() as mcp:
        products = await resolve_products(mcp, refs.values())
    # A lookup does not inherit yesterday's weather, outfit occasion or frozen slots.
    search_task = Task(gender=task.gender)
    products = [p for p in products if p.source == 'user' and not suitability(p, search_task)[0]]
    partial = total > 150
    if not products:
        return [], partial
    selection = await llm.generate('product_search', {
        'message': request.message, 'history': history[-12:],
        'candidates': [{'key': p.key, **p.model_dump(exclude={'original_image', 'cutout_image'})} for p in products],
    }, ProductSearchSelection)
    pool = {p.key: p for p in products}
    keys = list(dict.fromkeys(selection.selected_keys))
    if len(keys) > 6 or any(key not in pool for key in keys):
        raise StylistError('product_search_invalid_selection', '这次单品筛选结果未能确认，请换个说法再试。', 502)
    slots = {"garment": {"top", "bottom", "outer", "dress"}, "shoes": {"shoes"},
             "accessory": {"accessory"}}.get(selection.scope)
    return [pool[key] for key in keys if slots is None or pool[key].slot in slots], partial
