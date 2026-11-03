"""Synthetic catalog permission and continuation regressions; no live service calls."""
from typing import get_args

import pytest

from scripts.dialogue_validation import PRODUCTS, DialogueUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.models import Change, ChatRequest, Draft, LookDraft, Plan, Task
from stylist.new_clothes import enabled, explicit_new_clothes, invitation
from stylist.personas import PersonaId
from stylist.progress import events
from stylist.retrieval import retrieve
from stylist.store import Store


@pytest.mark.parametrize('text,wanted', [
    ('我想尝试新的搭配，并且是我衣橱里面没有的', True),
    ('帮我搭一套我衣柜里没有的衣服', True),
    ('从系统衣橱搭一套', True),
    ('我想尝试衣橱之外的搭配', True),
    ('请开启「邂逅新衣」', True),
    ('我想看看从没买过的新衣服', True),
    ('开启邂逅新衣，继续刚才的搭配', True),
    ('旧衣服搭出新鲜感', False),
    ('只给文字，帮我搭一套我衣橱里没有的搭配', False),
    ('不查商品，我想尝试我衣橱里没有的搭配', False),
    ('我想尝试新的搭配', False),
    ('我衣柜里没有外套，帮我搭一套', False),
    ('不要开启邂逅新衣', False),
    ('不开启邂逅新衣', False),
    ('只用我衣橱里的衣服，不要新衣', False),
    ('朋友说“我想尝试我衣橱里没有的搭配”', False),
    ('比如我说我想尝试衣柜里没有的衣服', False),
    ('我不想要我衣橱之外的衣服', False),
])
def test_original_words_gate(text, wanted):
    assert explicit_new_clothes(text, True, text) is wanted


class Catalog(DialogueUpstream):
    def __init__(self, *, partial=False, fail=False):
        super().__init__('new_clothes')
        self.products = PRODUCTS[:1] if partial else PRODUCTS
        self.catalog = [{**p, 'product_id': str(900 + i), 'gender': '男女同款'} for i, p in enumerate(PRODUCTS)]
        self.fail = fail

    async def get(self, path, params):
        if path == '/api/product/list':
            self.calls.append(path)
            if self.fail:
                raise StylistError('catalog_unavailable', '合成系统库失败')
            return {'list': self.catalog}
        return await super().get(path, params)

    async def call(self, name, args):
        if name == 'kb_search':
            self.calls.append(name)
            if self.fail:
                raise StylistError('catalog_unavailable', '合成系统库失败')
            return {'list': [{'id': p['product_id']} for p in self.catalog]}
        if name == 'product.resolve':
            personal = await super().call(name, args)
            keys = {r['product_id'] for r in args['items'] if r['source'] == 'system'}
            return {'items': personal['items'] + [{**p, 'source': 'system'} for p in self.catalog if p['product_id'] in keys]}
        return await super().call(name, args)


class Model:
    async def generate(self, name, payload, result_type):
        if name == 'plan':
            return Plan(mode='recommend', changes={'weather_policy': Change(value='ignored', evidence='不考虑天气')})
        pool = payload['candidates']
        keys = [p['key'] for p in pool if p['source'] == ('system' if payload['task']['source'] == 'hybrid' else 'user')][:3]
        return Draft(message='这次的搭配在这里。', looks=[LookDraft(title='日常', selected_keys=keys,
            reference_pieces=['长裤', '鞋子'] if len(keys) == 1 else [], why=['配色协调'], how=['自然穿着'])])


@pytest.mark.parametrize('persona', get_args(PersonaId))
@pytest.mark.parametrize('manual', [True, False])
@pytest.mark.asyncio
async def test_manual_and_automatic_select_catalog_then_continue_and_disable(tmp_path, persona, manual):
    import asyncio
    engine = Stylist(Settings(), Store(str(tmp_path/'state.db')), Model())
    upstream, queue = Catalog(), asyncio.Queue()
    token = events.set(queue)
    try:
        first = await engine.chat(upstream, ChatRequest(message=(
            '帮我搭一套，不考虑天气' if manual else '我想尝试新的搭配，并且是我衣橱里面没有的，不考虑天气'),
            new_clothes=manual, request_id='new-clothes-first', assistant_persona=persona))
    finally:
        events.reset(token)
    assert first.new_clothes and first.new_clothes_auto_enabled is (not manual)
    assert first.new_clothes_notice == (None if manual else invitation(persona))
    stages = [queue.get_nowait()['stage'] for _ in range(queue.qsize())]
    if not manual:
        assert stages.index('new_clothes') < stages.index('wardrobe')
    assert first.task.source == 'hybrid'
    assert all(p.source == 'system' for look in first.looks for p in look.items)
    assert '/api/user_product/quick_edit_list' in upstream.calls and ('kb_search' in upstream.calls or '/api/product/list' in upstream.calls)
    second = await engine.chat(upstream, ChatRequest(message='继续搭一套，不考虑天气', request_id='new-clothes-second',
        conversation_id=first.conversation_id, expected_version=first.version))
    assert second.new_clothes and not second.new_clothes_auto_enabled
    upstream.calls.clear()
    third = await engine.chat(upstream, ChatRequest(message='只用我已有的衣服搭一套，不考虑天气', new_clothes=True,
        request_id='new-clothes-third', conversation_id=second.conversation_id, expected_version=second.version))
    assert not third.new_clothes and third.task.source == 'wardrobe'
    assert '/api/product/list' not in upstream.calls and 'kb_search' not in upstream.calls
    assert all(p.source == 'user' for look in third.looks for p in look.items)


@pytest.mark.asyncio
async def test_gap_offers_choice_without_automatically_querying_catalog(tmp_path):
    upstream = Catalog(partial=True)
    reply = await Stylist(Settings(), Store(str(tmp_path/'state.db')), Model()).chat(upstream,
        ChatRequest(message='搭一套，不考虑天气', request_id='gap-clothes-first'))
    assert reply.wardrobe_gap and not reply.new_clothes
    assert '/api/product/list' not in upstream.calls and 'kb_search' not in upstream.calls
    assert not reply.upload_intent and not reply.upload_suggestion


@pytest.mark.asyncio
async def test_catalog_failure_retains_personal_candidates():
    upstream = Catalog(fail=True)
    pool, warnings, _ = await retrieve(upstream, upstream, Task(gender='女'), '日常', allow_system=True)
    assert pool and all(p.source == 'user' for p in pool.values())
    assert warnings


def test_new_switch_beats_legacy_source_and_manual_disable_beats_previous():
    plan = Plan(mode='recommend', new_clothes_intent=True, new_clothes_evidence='幻觉')
    assert enabled(ChatRequest(message='搭一套', request_id='new-switch-test', source='hybrid'), plan) == (False, False)
    assert enabled(ChatRequest(message='搭一套', request_id='new-switch-test', new_clothes=False), plan, True) == (False, False)


@pytest.mark.asyncio
async def test_inventory_failure_does_not_offer_a_false_gap(tmp_path):
    class Broken(Catalog):
        async def get(self, path, params):
            raise StylistError('upstream_unavailable', '模拟衣橱读取失败')
    reply = await Stylist(Settings(), Store(str(tmp_path/'state.db')), Model()).chat(Broken(),
        ChatRequest(message='搭一套，不考虑天气', request_id='gap-read-failure'))
    assert not reply.wardrobe_gap and not reply.new_clothes


def test_catalog_images_require_a_saved_selection_owned_by_the_account(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from stylist.main import create_app
    from stylist.models import Look, Product, Reply, Slot
    from stylist.upstream import Upstream
    settings = Settings(database=str(tmp_path/'state.db'))
    store = Store(settings.database)
    request = ChatRequest(message='搭配', new_clothes=True, request_id='system-image-owner')
    cid, claim, state, _ = store.reserve('a', request)
    state.looks = [Look(title='参考款', items=[Product(source='system', product_id='900', slot=Slot.TOP)])]
    reply = Reply(conversation_id=cid, version=1, mode='recommend', delivery='outfit', message='参考款',
                  task=Task(source='hybrid'), looks=state.looks, new_clothes=True)
    store.finish('a', request, claim, state, reply)
    calls = []

    async def identity(self):
        return 'a' if self.authorization == 'Bearer account-a' else 'b'

    async def read(upstream, product_id, kind='original', *, source='user'):
        calls.append((product_id, source))
        return b'png', 'image/png'

    monkeypatch.setattr(Upstream, 'identity', identity)
    monkeypatch.setattr('stylist.main.read_wardrobe_image', read)
    url = f'/stylist-api/conversations/{cid}/catalog/900/image-source?version=1'
    with TestClient(create_app(settings)) as client:
        assert client.get(url).status_code == 401
        assert client.get(url, headers={'Authorization': 'Bearer account-b'}).status_code == 404
        assert client.get(url.replace('900/', '901/'), headers={'Authorization': 'Bearer account-a'}).status_code == 404
        response = client.get(url, headers={'Authorization': 'Bearer account-a'})
        assert response.status_code == 200 and response.content == b'png'
        assert response.headers['cache-control'] == 'private, no-store'
    assert calls == [('900', 'system')]
    from stylist.composition import Compositions
    assert Compositions(store).get('a', cid, 1, 0, 'male')['status'] == 'missing'
    with pytest.raises(StylistError):
        Compositions(store).get('b', cid, 1, 0, 'male')


@pytest.mark.asyncio
async def test_disabling_catalog_cannot_silently_replace_frozen_system_items(tmp_path):
    class Modify(Model):
        async def generate(self, name, payload, result_type):
            if name == 'plan' and '只换鞋' in payload['message']:
                return Plan(mode='modify', replace_slots=['shoes'])
            return await super().generate(name, payload, result_type)
    store = Store(str(tmp_path/'state.db'))
    engine, upstream = Stylist(Settings(), store, Modify()), Catalog()
    first = await engine.chat(upstream, ChatRequest(message='搭一套，不考虑天气', new_clothes=True,
        request_id='freeze-system-first'))
    with pytest.raises(StylistError, match='frozen_source_conflict'):
        await engine.chat(upstream, ChatRequest(message='只换鞋', new_clothes=False,
            request_id='freeze-system-second', conversation_id=first.conversation_id, expected_version=first.version))
    with store.connection() as conn:
        row = conn.execute('SELECT version FROM stylist_sessions WHERE id=?', (first.conversation_id,)).fetchone()
    assert row['version'] == first.version
