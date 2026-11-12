"""Find existing personal-library outfits without composing new outfits."""
from secrets import SystemRandom
import json
from urllib.parse import urlsplit
from pydantic import Field
from .models import Model, SavedOutfitRef, Look
from .subject_entry import resolve_outfit_entry
from .retrieval import from_row, resolve_products
from .models import ProductRef
from .errors import AuthenticationExpired, StylistError


class SavedSelection(Model):
    outfit_ids: list[int] = Field(default_factory=list, max_length=100)


def candidate_metadata(key, row):
    def obj(value):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return {}
        return value if isinstance(value, dict) else {}
    canvas = obj(obj(row.get('canvas_info')).get('canvas_data'))
    products = canvas.get('product_list')
    attributes = []
    for product in products[:10] if isinstance(products, list) else []:
        if isinstance(product, dict):
            attributes.append({name: product.get(name) for name in ('title','class_name','secondary_class_name','color','color_name','material')
                               if isinstance(product.get(name), str)})
    return {'outfit_id': key, 'title': row.get('title'), 'summary': row.get('summary'),
            'occasion': row.get('occasion_text'), 'features_desc': row.get('features_desc'), 'products': attributes}


async def search_saved_outfits(upstream, llm, message, *, random_selection=False, history=None, exclude_previous=False):
    cursor = {'outfit_id': 0, 'outfit_id_type': 0}
    candidates, seen_cursors = {}, set()
    partial = False
    for page in range(10):
        result = await upstream.get('/api/ai_outfit_merge_my_outfit/list', cursor)
        rows = result.get('list')
        if not isinstance(rows, list):
            raise StylistError('saved_outfit_search_invalid', '已有搭配列表格式异常，请稍后重试。', 502)
        for row in rows:
            if not isinstance(row, dict):
                continue
            # Same supported personal outfit type as the existing detail entry.
            if str(row.get('outfit_id_type')) == '2' and str(row.get('outfit_id', '')).isdigit() and 0 < int(row['outfit_id']) <= 9007199254740991:
                candidates[int(row['outfit_id'])] = row
        if len(rows) < 10:
            break
        tail = rows[-1]
        if not isinstance(tail, dict):
            raise StylistError('saved_outfit_search_invalid', '已有搭配分页记录格式异常，请稍后重试。', 502)
        next_cursor = {'outfit_id': tail.get('outfit_id'), 'outfit_id_type': tail.get('outfit_id_type')}
        key = tuple(next_cursor.values())
        if None in key or key in seen_cursors:
            partial = True
            break
        seen_cursors.add(key)
        cursor = next_cursor
        partial = page == 9
    if not candidates:
        return [], [], [], partial
    selected = await llm.generate('saved_outfit_search', {
        'message': message, 'history': (history or [])[-12:], 'random_selection': random_selection,
        'candidates': [candidate_metadata(key, row) for key, row in candidates.items()],
    }, SavedSelection)
    ids = list(dict.fromkeys(selected.outfit_ids))
    if any(key not in candidates for key in ids):
        raise StylistError('saved_outfit_search_invalid', '已有搭配筛选结果无法核对，请稍后重试。', 502)
    if exclude_previous:
        for turn in reversed(history or []):
            if turn.get('role') != 'assistant':
                continue
            try:
                previous = json.loads(turn['content'])
            except (ValueError, KeyError, TypeError):
                continue
            ref = previous.get('subject_outfit') if isinstance(previous, dict) else None
            if isinstance(ref, dict):
                ids = [key for key in ids if key != ref.get('outfit_id')]
                break
    if random_selection:
        SystemRandom().shuffle(ids)
    looks, references, entries = [], [], []
    for key in ids:
        try:
            ref = SavedOutfitRef(outfit_id=key)
            entry = await resolve_outfit_entry(upstream, ref)
            info = candidates[key].get('canvas_info')
            if isinstance(info, str):
                try:
                    info = json.loads(info)
                except ValueError:
                    info = None
            covers = [(entry.get('presentation') or {}).get('canvas_image'),
                      candidates[key].get('canvas_image'), candidates[key].get('cover_image'),
                      info.get('canvas_image') if isinstance(info, dict) else None]
            cover = ''
            for value in covers:
                if not isinstance(value, str):
                    continue
                parsed = urlsplit(value)
                if parsed.scheme in {'http','https'} and parsed.hostname:
                    cover = value
                    break
            entry['presentation'] = {'canvas_image': cover} if cover else None
            products = [from_row(row, 'user') for row in entry['items']]
            if any(product is None for product in products):
                continue
            # A saved single skirt/top is not an entire outfit recommendation.
            if len(products) == 1 and products[0].slot != "dress":
                continue
            async with upstream.mcp() as mcp:
                live = await resolve_products(mcp, [ProductRef(source='user', product_id=p.product_id) for p in products])
            if {p.key for p in live} != {p.key for p in products}:
                continue
            looks.append(Look(title=entry['title'] or '我的已有搭配', items=live,
                              pieces=[p.display_name for p in live], wardrobe_complete=True))
            references.append(ref)
            entries.append(entry)
            if len(looks) >= 1:
                break
        except AuthenticationExpired:
            raise
        except StylistError as exc:
            if exc.status == 404:
                continue
            raise
    return looks, references, entries, partial
