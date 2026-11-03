"""System KB adapter and source-policy regressions; synthetic transport and products only."""
import asyncio
import json

import httpx
import pytest

from scripts.dialogue_validation import DialogueUpstream
from stylist.catalog import CatalogSearch, parse_chunk
from stylist.catalog_config import CatalogConfig
from stylist.catalog_retrieval import category_conflicts
from stylist.catalog_signing import SigningContext
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import AuthenticationExpired, StylistError
from stylist.models import Change, ChatRequest, Draft, LookDraft, Plan, Slot, Task
from stylist.retrieval import from_row, retrieve
from stylist.store import Store
from stylist.upstream import Upstream


def config(**changes):
    return CatalogConfig(enabled=True, ak='synthetic-access', sk='synthetic-secret',
                         collection='fixture', document='doc_id_system', **changes)


def chunk(row, document='doc_id_system'):
    return {'chunk_id': 999999, 'doc_info': {'doc_id': document},
            'table_chunk_fields': [{'field_name': k, 'field_value': v} for k, v in row.items()]}


def item(identity, category='上衣', title='男式长袖衬衫', gender='男'):
    return {'product_id': str(identity), 'source': 'system', 'class_name': category, 'title': title,
            'gender': gender, 'original_image': 'https://example.invalid/catalog.png', 'style': '休闲、简约'}


@pytest.mark.asyncio
async def test_signed_catalog_request_uses_system_document_and_hard_filters():
    seen = []
    def handler(request):
        assert request.url.host == 'api-knowledgebase.mlp.cn-beijing.volces.com'
        assert request.url.path == '/api/knowledge/collection/search_knowledge'
        assert request.headers['authorization'].startswith('HMAC-SHA256 ')
        assert 'Bearer' not in request.headers['authorization']
        data = json.loads(request.content)
        seen.append(data)
        return httpx.Response(200, json={'code': 0, 'data': {'result_list': [chunk(item('321'))]}})
    rows = await CatalogSearch(config(), httpx.MockTransport(handler)).search(query='男装衬衫', category='上衣', gender='男', limit=8)
    assert rows[0]['product_id'] == '321'  # Never use chunk_id=999999.
    assert seen[0]['query_param']['doc_filter'] == {'op': 'and', 'conds': [
        {'op': 'must', 'field': 'doc_id', 'conds': ['doc_id_system']},
        {'op': 'must', 'field': 'class_name', 'conds': ['上衣']},
        {'op': 'must', 'field': 'gender', 'conds': ['男', '男女同款']}]}
    assert seen[0]['limit'] == 8


@pytest.mark.asyncio
@pytest.mark.parametrize('response', [
    {'code': 1}, {'code': 0, 'data': []}, {'code': 0, 'data': {'result_list': {}}},
])
async def test_malformed_or_error_response_is_not_empty_inventory(response):
    def handler(request):
        return httpx.Response(200, json=response)
    with pytest.raises(StylistError, match='catalog_unavailable'):
        await CatalogSearch(config(), httpx.MockTransport(handler)).search(query='衬衫', category='上衣', gender='男', limit=8)


@pytest.mark.asyncio
async def test_wrong_document_never_enters_system_candidates():
    def handler(request):
        return httpx.Response(200, json={'data': {'result_list': [chunk(item('321'), 'doc_id_123')]}})
    with pytest.raises(StylistError, match='catalog_source_mismatch'):
        await CatalogSearch(config(), httpx.MockTransport(handler)).search(query='衬衫', category='上衣', gender='男', limit=8)


def test_parser_prefers_business_id_and_supports_content_without_chunk_id_fallback():
    assert parse_chunk(chunk({**item('321'), 'id': '888'}))['product_id'] == '321'
    assert parse_chunk({'chunk_id': 4, 'content': 'title: 衬衫', 'doc_info': {'doc_id': 'doc_id_system'}}) is None
    result = parse_chunk({'content': 'id: 321\nclass_name: 上衣\ngender: 男', 'doc_info': {'doc_id': 'doc_id_system'}})
    assert result['product_id'] == '321'
    assert 'synthetic-secret' not in repr(config())
    assert 'synthetic-secret' not in repr(SigningContext('synthetic-access', 'synthetic-secret'))


def test_configuration_reuses_legacy_profile_and_refuses_personal_document():
    loaded = CatalogConfig.load({'db_knowledge': {'enabled': True, 'ak': 'test', 'sk': 'secret',
        'collection_name': 'old', 'filter': {'doc_id_value': 'doc_id_system'},
        'profiles': {'legacy': {'collection_name': 'legacy-system'}}}})
    assert loaded.available and loaded.collection == 'legacy-system'
    from dataclasses import replace
    assert not replace(loaded, document='doc_id_123').available
    assert not replace(loaded, host='evil.invalid').available
    assert not replace(loaded, document='').available
    assert not CatalogConfig().available


class SystemWardrobe(DialogueUpstream):
    catalog_available = True

    def __init__(self, widening=False, conflict=False):
        super().__init__('catalog-policy')
        self.searches, self.widening, self.conflict = [], widening, conflict
        self.system = {str(800 + index): item(800+index, category, title)
                       for index, (category, title) in enumerate([
                           ('上衣', '男式长袖衬衫'), ('裤子', '男式直筒长裤'), ('鞋子', '男式平底运动鞋')])}

    async def search_catalog(self, **arguments):
        self.searches.append(arguments)
        self.calls.append('direct_catalog')
        if self.widening and not (arguments['query'].startswith('日常穿搭') and arguments['limit'] == 16):
            return []
        return [p for p in self.system.values() if p['class_name'] == arguments['category']]

    async def call(self, name, args):
        if name == 'kb_search':
            pytest.fail('Configured direct KB must not rely on optional MCP kb_search')
        if name == 'product.resolve':
            result = await super().call(name, args)
            for ref in args['items']:
                if ref['source'] == 'system' and ref['product_id'] in self.system:
                    product = self.system[ref['product_id']]
                    if self.conflict and ref['product_id'] == '801':
                        product = {**product, 'class_name': '外套', 'secondary_class_name': '西装外套'}
                    result['items'].append(product)
            return result
        return await super().call(name, args)

    async def get(self, path, params):
        if path == '/api/product/list':
            pytest.fail('Do not fall back to generic list when direct KB has suitable products')
        return await super().get(path, params)


@pytest.mark.asyncio
async def test_direct_recall_widens_without_relaxing_gender_or_class_and_keeps_partial():
    upstream, trace = SystemWardrobe(widening=True), {}
    pool, warnings, _ = await retrieve(upstream, upstream, Task(source='hybrid', gender='男', style='通勤'),
                                      '男生办公室', allow_system=True, diagnostics=trace)
    systems = [p for p in pool.values() if p.source == 'system']
    assert {p.slot for p in systems} == {Slot.TOP, Slot.BOTTOM, Slot.SHOES}
    assert all(p.gender == '男' and p.original_image for p in systems)
    assert all(q['gender'] == '男' for q in upstream.searches)
    top = [q for q in upstream.searches if q['category'] == '上衣']
    assert [q['limit'] for q in top] == [8, 8, 16]
    assert '男生办公室' in top[0]['query'] and top[1]['query'].startswith('日常穿搭')
    assert trace['catalog']['provider'] == 'knowledge_base' and trace['catalog']['eligible'] == 3
    assert not any('还没能顺利查到' in w for w in warnings)


@pytest.mark.asyncio
async def test_closed_source_never_calls_catalog_even_if_task_source_is_hybrid():
    upstream = SystemWardrobe()
    pool, _, _ = await retrieve(upstream, upstream, Task(source='hybrid', gender='男'), '日常', allow_system=False)
    assert not upstream.searches and all(p.source == 'user' for p in pool.values())


@pytest.mark.asyncio
async def test_conflicting_resolve_category_is_rejected_without_relabeling():
    upstream = SystemWardrobe(conflict=True)
    pool, warnings, rejected = await retrieve(upstream, upstream, Task(gender='男'), '日常', allow_system=True)
    assert 'system:801' not in pool
    assert 'system:800' in pool and 'system:802' in pool
    assert any('冲突' in reason for reason in rejected)
    assert any('分类信息不一致' in w for w in warnings)
    assert upstream.system['801']['class_name'] == '裤子'


@pytest.mark.parametrize('row,reason', [
    (item('1','外套','男式休闲长裤'), '系统商品标题与分类冲突'),
    (item('1','帽子','男式20寸登机箱'), '系统商品不是可穿戴单品'),
])
def test_original_failure_rows_are_not_reintroduced(row, reason):
    assert reason in category_conflicts(from_row(row, 'system'))


@pytest.mark.asyncio
async def test_catalog_is_reserved_even_when_personal_top_quota_is_full():
    upstream = SystemWardrobe()
    upstream.products = [{**upstream.products[0], 'product_id': str(100+i), 'gender':'男'} for i in range(15)]
    pool, _, _ = await retrieve(upstream, upstream, Task(gender='男'), '日常', allow_system=True)
    assert 'system:800' in pool
    assert sum(p.slot == Slot.TOP for p in pool.values()) == 10
    assert sum(p.source == 'user' and p.slot == Slot.TOP for p in pool.values()) == 9


@pytest.mark.asyncio
async def test_exact_user_phrase_returns_selected_system_items_and_saved_diagnostics(tmp_path):
    class Model:
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='recommend', changes={'weather_policy':Change(value='ignored', evidence='不考虑天气'),
                                                       'gender':Change(value='男', evidence='男装')})
            assert payload['retrieval_diagnostics']['catalog']['eligible'] == 3
            return Draft(message='这次从参考衣橱挑了三件。', looks=[LookDraft(title='日常男装',
                selected_keys=['system:800','system:801','system:802'], why=['配色协调'], how=['自然穿着'])])
    upstream = SystemWardrobe()
    reply = await Stylist(Settings(), Store(str(tmp_path/'system.db')), Model()).chat(upstream,
        ChatRequest(message='帮我搭配一i套我没有的衣服，男装，不考虑天气', request_id='actual-user-phrase-fixture'))
    assert reply.new_clothes and reply.new_clothes_auto_enabled and reply.delivery == 'outfit'
    assert len(reply.looks[0].items) == 3 and all(p.source == 'system' and p.original_image for p in reply.looks[0].items)
    assert reply.retrieval_diagnostics['catalog']['provider'] == 'knowledge_base'


@pytest.mark.asyncio
async def test_expired_identity_does_not_read_system_kb():
    def handler(request):
        assert request.url.host == 'upstream.invalid'
        return httpx.Response(401)
    upstream = Upstream(Settings(server_url='https://upstream.invalid', catalog=config()), 'Bearer fixture', httpx.MockTransport(handler))
    with pytest.raises(AuthenticationExpired):
        await upstream.search_catalog(query='日常', category='上衣', gender='男', limit=8)


@pytest.mark.asyncio
async def test_catalog_authentication_is_shared_by_parallel_class_reads():
    identities = []
    def handler(request):
        if request.url.host == 'upstream.invalid':
            identities.append(request)
            assert request.headers['Authorization'] == 'Bearer fixture'
            return httpx.Response(200, json={'code': 0, 'data': {'id':1}})
        assert not request.headers['Authorization'].startswith('Bearer')
        return httpx.Response(200, json={'data': {'result_list':[]}})
    upstream = Upstream(Settings(server_url='https://upstream.invalid', catalog=config()), 'Bearer fixture', httpx.MockTransport(handler))
    await asyncio.gather(*(upstream.search_catalog(query='日常', category=c, gender='男', limit=8) for c in ['上衣','裤子','鞋子']))
    assert len(identities) == 1


@pytest.mark.asyncio
async def test_fallback_continues_past_full_page_even_when_placeholder_total_is_one():
    class Fallback(SystemWardrobe):
        def __init__(self):
            super().__init__()
            self.pages = []
            self.system.update({str(900+i):item(900+i, gender='女') for i in range(50)})

        async def search_catalog(self, **arguments):
            raise StylistError('catalog_unavailable', '模拟知识库不可用')

        async def get(self, path, params):
            if path != '/api/product/list':
                return await super().get(path, params)
            assert params['gender'] == 1
            self.pages.append(params['page'])
            rows = [p for key, p in self.system.items() if int(key) >= 900] if params['page'] == 1 else [self.system[str(i)] for i in [800,801,802]]
            return {'list': rows, 'pagination': {'total':1}}
    upstream, trace = Fallback(), {}
    pool, warnings, rejected = await retrieve(upstream, upstream, Task(gender='男'), '日常',
                                              allow_system=True, diagnostics=trace)
    assert upstream.pages == [1,2] and trace['catalog']['fallback_pages'] == 2
    assert {p.slot for p in pool.values() if p.source == 'system'} == {Slot.TOP,Slot.BOTTOM,Slot.SHOES}
    assert all(p.gender != '女' for p in pool.values())
    assert rejected and not any('还没能顺利查到' in w for w in warnings)


@pytest.mark.asyncio
async def test_one_class_failure_does_not_discard_other_class_candidates():
    class Partial(SystemWardrobe):
        async def search_catalog(self, **arguments):
            if arguments['category'] == '上衣':
                raise StylistError('catalog_unavailable', '模拟单一品类失败')
            return await super().search_catalog(**arguments)
    upstream, trace = Partial(), {}
    pool, warnings, _ = await retrieve(upstream, upstream, Task(gender='男'), '日常', allow_system=True, diagnostics=trace)
    assert 'system:800' not in pool and 'system:801' in pool and 'system:802' in pool
    assert trace['catalog']['classes']['上衣']['attempts'][0]['error'] == 'catalog_unavailable'
    assert trace['catalog']['outcome'] == 'ok'
    assert any('部分系统品类' in w for w in warnings)


@pytest.mark.asyncio
async def test_personal_failure_can_still_use_authorized_catalog():
    class PersonalDown(SystemWardrobe):
        async def get(self, path, params):
            if path == '/api/user_product/quick_edit_list':
                raise StylistError('upstream_unavailable', '模拟个人衣橱不可用')
            return await super().get(path, params)
    upstream, trace = PersonalDown(), {}
    pool, _, _ = await retrieve(upstream, upstream, Task(gender='男'), '日常', allow_system=True, diagnostics=trace)
    assert trace['personal']['unavailable'] and trace['catalog']['outcome'] == 'ok'
    assert len(pool) == 3 and all(p.source == 'system' for p in pool.values())


@pytest.mark.asyncio
async def test_soft_widening_never_relaxes_no_heels():
    upstream = SystemWardrobe(widening=True)
    upstream.system['802'] = item('802', '鞋子', '男式高跟皮鞋')
    pool, _, rejected = await retrieve(upstream, upstream, Task(gender='男', no_heels=True), '日常', allow_system=True)
    assert 'system:802' not in pool and 'system:800' in pool and 'system:801' in pool
    assert any('高跟' in reason for reason in rejected)
