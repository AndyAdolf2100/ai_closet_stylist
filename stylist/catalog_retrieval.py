"""Bounded per-class catalog recall with soft widening and authoritative revalidation."""
import asyncio
import re
from collections import Counter

from .catalog import CATEGORIES, business_id
from .errors import AuthenticationExpired, StylistError
from .models import ProductRef
from .personas import service_notice
from .policy import infer_slot, suitability


def category_conflicts(product):
    """Reject clear evidence conflicts; do not relabel the original catalog."""
    title = product.title
    if re.search(r'行李箱|登机箱|旅行箱|收纳箱', title):
        return ['系统商品不是可穿戴单品']
    primary, secondary = infer_slot(product.class_name), infer_slot(product.secondary_class_name)
    if primary and secondary and primary != secondary:
        return ['系统商品一级与二级分类冲突']
    expected = None
    if re.search(r'连衣裙|连体裤|连体衣', title):
        expected = 'dress'
    elif re.search(r'长裤|短裤|休闲裤|牛仔裤|西装裤|弯刀裤|工装裤|束脚裤|半身裙', title):
        expected = 'bottom'
    elif re.search(r'运动鞋|休闲鞋|皮鞋|板鞋|凉鞋|短靴|长靴', title):
        expected = 'shoes'
    elif re.search(r'风衣|大衣|夹克|羽绒服|西装外套', title):
        expected = 'outer'
    # A multi-piece product title is ambiguous, so preserve it for model inspection.
    if expected and not re.search(r'套装|两件套|三件套', title) and product.slot != expected:
        return ['系统商品标题与分类冲突']
    return []


async def collect_catalog(upstream, mcp, task, query, personal, resolve, normalize, rejected, trace, persona_id=None):
    categories = [c for c in CATEGORIES if c not in task.excluded_categories]
    semaphore = asyncio.Semaphore(4)
    trace.update({'provider': 'knowledge_base' if getattr(upstream, 'catalog_available', False) else 'mcp',
                  'classes': {}, 'returned': 0, 'eligible': 0, 'unavailable': False, 'fallback_pages': 0})
    raw_by_id, products, warnings, examined = {}, {}, [], set()
    personal_counts = Counter(p.slot for p in personal)

    async def adopt(rows, category=None, direct=False):
        refs, extras = [], {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            identity = business_id(row)
            if not identity:
                rejected['系统候选缺少有效业务商品ID'] = rejected.get('系统候选缺少有效业务商品ID', 0) + 1
                continue
            if direct and row.get('class_name') != category:
                rejected['知识库返回分类不符'] = rejected.get('知识库返回分类不符', 0) + 1
                continue
            # Do not retry an already examined id under another class/expansion.
            marker = (identity, category)
            if marker in examined:
                continue
            examined.add(marker)
            if identity not in raw_by_id:
                trace['returned'] += 1
            raw_by_id.setdefault(identity, row)
            refs.append(ProductRef(source='system', product_id=identity))
            extras['system:' + identity] = row
        if not refs:
            return []
        try:
            resolved = await resolve(mcp, refs, extras)
        except AuthenticationExpired:
            raise
        except StylistError as exc:
            if exc.code == 'unexpected_product':
                raise
            trace['unavailable'] = True
            trace.setdefault('errors', []).append(exc.code)
            return []
        adopted = []
        for product in resolved:
            raw = raw_by_id[product.product_id]
            problems = category_conflicts(product)
            if direct:
                kb = normalize(raw, 'system')
                if kb is None or kb.slot != product.slot:
                    problems.append('知识库与权威商品分类冲突')
                elif category_conflicts(kb):
                    problems.append('知识库商品标题与分类冲突')
                elif suitability(kb, task)[0]:
                    problems.append('知识库属性不符合本轮硬性条件')
            if category and product.slot != infer_slot(category):
                problems.append('系统候选不属于请求槽位')
            reasons, cautions = suitability(product, task)
            problems.extend(reasons)
            if problems:
                for reason in set(problems):
                    rejected[reason] = rejected.get(reason, 0) + 1
                continue
            product.warnings = cautions
            products[product.key] = product
            adopted.append(product)
        return adopted

    async def search_class(category):
        target = max(2, 4 - personal_counts[infer_slot(category)])
        status = trace['classes'][category] = {'target': target, 'attempts': [], 'eligible': 0}
        direct = getattr(upstream, 'catalog_available', False)
        for level, limit in enumerate((8, 8, 16)):
            descriptors = ' '.join(str(v) for v in [query, task.scene, task.occasion, task.style] if v)
            # Widen semantic descriptors, never remove class, gender, or local hard constraints.
            text = f'{descriptors if level == 0 else "日常穿搭"} {category}'
            if task.weather_policy != 'ignored' and (task.temp_min is not None or task.temp_max is not None):
                text += f' 适合气温{task.temp_min if task.temp_min is not None else "未知"}至{task.temp_max if task.temp_max is not None else "未知"}摄氏度'
            attempt = {'level': level, 'limit': limit, 'returned': 0}
            status['attempts'].append(attempt)
            try:
                async with semaphore:
                    if direct:
                        rows = await upstream.search_catalog(query=text, category=category, gender=task.gender, limit=limit)
                    else:
                        args = {'scope': 'public', 'query': text, 'class_name': category, 'top_k': limit}
                        if task.gender:
                            args['gender'] = task.gender
                        result = await mcp.call('kb_search', args)
                        rows = result.get('list') or []
                    attempt['returned'] = len(rows)
                    added = await adopt(rows, category, direct)
                status['eligible'] += len(added)
                if status['eligible'] >= target:
                    break
            except AuthenticationExpired:
                raise
            except StylistError as exc:
                if exc.code == 'unexpected_product':
                    raise
                attempt['error'] = exc.code
                trace['unavailable'] = True
                break

    # Failure in one category must not discard another category's successful result.
    outcomes = await asyncio.gather(*(search_class(c) for c in categories), return_exceptions=True)
    for outcome in outcomes:
        if isinstance(outcome, BaseException):
            raise outcome
    if not products:
        trace['fallback'] = 'bounded_list'
        for page in range(1, 4):
            params = {'page': page, 'page_size': 50}
            if task.gender in {'男', '女'}:
                params['gender'] = 1 if task.gender == '男' else 2
            try:
                result = await upstream.get('/api/product/list', params)
                trace['fallback_pages'] += 1
                rows = result.get('list') or []
                await adopt(rows)
                # This upstream reports a placeholder total=1, so stop on a short page, not total.
                if len(rows) < 50:
                    break
            except AuthenticationExpired:
                raise
            except StylistError as exc:
                trace['unavailable'] = True
                trace.setdefault('errors', []).append(exc.code)
                break
        if products:
            warnings.append(service_notice(persona_id, 'catalog_partial'))
    trace['eligible'] = len(products)
    trace['outcome'] = 'ok' if products else ('unavailable' if trace['unavailable'] else 'no_match')
    if products:
        if any(any(a.get('error') for a in value['attempts']) for value in trace['classes'].values()) and trace.get('fallback') != 'bounded_list':
            warnings.append('部分系统品类这次暂时没查顺利，我先保留已经核对过的参考款。')
        trace['unavailable'] = False
    else:
        warnings.append('本次系统候选没有找到通过属性核对和穿衣条件检查的参考款，不能据此判断整个系统衣橱没有合适衣物。'
                        if trace['returned'] else service_notice(persona_id, 'catalog_search') if trace['unavailable'] else
                        '本次系统参考衣橱没有返回匹配候选；这只是本次查询范围的结果。')
    if any('冲突' in reason or '不是可穿戴' in reason for reason in rejected):
        warnings.append('部分系统参考款的标题或分类信息不一致，已先排除，避免把不合适的单品放进搭配。')
    return list(products.values()), warnings
