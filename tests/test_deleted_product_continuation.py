"""Deleted wardrobe items must not strand a conversation or become candidates again."""
import pytest

from scripts.dialogue_validation import DialogueUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.models import ChatRequest, Draft, LookDraft, Plan, Slot, Task
from stylist.retrieval import saved_candidates
from stylist.store import Store


class Model:
    def __init__(self, mode='recommend'):
        self.mode = mode
        self.payload = None

    async def generate(self, name, payload, result_type):
        if name == 'plan':
            return Plan(mode=self.mode, use_inventory=True,
                        replace_slots=[Slot.SHOES] if self.mode == 'modify' else [])
        self.payload = payload
        keys = [p['key'] for p in payload['candidates'] if p['key'] in {'user:102', 'user:103'}]
        assert 'user:101' not in payload['frozen_keys']
        assert all(p['key'] != 'user:101' for p in payload['candidates'])
        return Draft(message='原单品已不可用，继续按当前衣橱搭配。', looks=[LookDraft(
            title='日常搭配', selected_keys=keys, pieces=[] if keys else ['衬衫', '长裤', '平底鞋'],
            why=['按当前可用单品选择'], how=['自然穿着'])])


@pytest.mark.asyncio
@pytest.mark.parametrize('empty', [False, True])
async def test_deleted_subject_continues_and_preserves_history(tmp_path, empty):
    upstream = DialogueUpstream('deleted-subject')
    model = Model()
    store = Store(str(tmp_path / 'subject.db'))
    engine = Stylist(Settings(), store, model)
    entry = await engine.chat(upstream, ChatRequest(
        subject_product={'source': 'user', 'product_id': '101'}, request_id='deleted-entry'))
    upstream.products = [] if empty else [p for p in upstream.products if p['product_id'] != '101']
    reply = await engine.chat(upstream, ChatRequest(
        message='用这件搭配下，不考虑天气', request_id='deleted-pair', pair_subject_product=True,
        conversation_id=entry.conversation_id, expected_version=entry.version, weather_policy='ignored'))
    assert reply.version == 2
    assert reply.delivery == ('concept' if empty else 'outfit')
    assert any('不可用' in text for text in reply.warnings)
    assert model.payload['frozen_keys'] == []
    assert all(p.product_id != '101' for look in reply.looks for p in look.items)
    history = store.history(await upstream.identity(), entry.conversation_id)
    assert history['messages'][0]['reply']['product_entry']['product']['product_id'] == '101'
    # The next normal turn remains usable as well.
    following = await engine.chat(upstream, ChatRequest(
        message='再帮我搭一套，不考虑天气', request_id='deleted-continue',
        conversation_id=reply.conversation_id, expected_version=reply.version, weather_policy='ignored'))
    assert following.version == 3


@pytest.mark.asyncio
async def test_deleted_item_entry_returns_continuable_conversation(tmp_path):
    upstream = DialogueUpstream('deleted-entry')
    upstream.products = []
    engine = Stylist(Settings(), Store(str(tmp_path / 'entry.db')), Model())
    reply = await engine.chat(upstream, ChatRequest(
        subject_product={'source': 'user', 'product_id': '101'}, request_id='deleted-entry'))
    assert reply.product_entry is None and not reply.looks
    assert reply.follow_ups == ['从当前衣橱帮我搭一套']
    following = await engine.chat(upstream, ChatRequest(
        message=reply.follow_ups[0], request_id='deleted-next', conversation_id=reply.conversation_id,
        expected_version=reply.version, weather_policy='ignored'))
    assert following.delivery == 'concept' and following.version == 2


@pytest.mark.asyncio
async def test_saved_outfit_snapshot_cannot_reintroduce_deleted_item():
    class Upstream(DialogueUpstream):
        async def call(self, name, args):
            if name == 'outfit.search-saved':
                return {'matches': [{'outfit_id': 1}]}
            if name == 'outfit.resolve':
                return {'items': self.snapshot}
            return await super().call(name, args)
    upstream = Upstream('stale-saved')
    upstream.snapshot = list(upstream.products)
    upstream.products = [p for p in upstream.products if p['product_id'] != '101']
    items = await saved_candidates(upstream, Task())
    assert items and all(p.product_id != '101' for p in items)


@pytest.mark.asyncio
async def test_lookup_outage_is_not_reported_as_deleted(tmp_path):
    class Upstream(DialogueUpstream):
        async def call(self, name, args):
            if name == 'product.resolve':
                raise StylistError('product_entry_unavailable', '读取失败', 503)
            return await super().call(name, args)
    engine = Stylist(Settings(), Store(str(tmp_path / 'outage.db')), Model())
    with pytest.raises(StylistError) as error:
        await engine.chat(Upstream('outage'), ChatRequest(
            subject_product={'source': 'user', 'product_id': '101'}, request_id='deleted-entry'))
    assert error.value.status == 503


@pytest.mark.asyncio
async def test_local_edit_releases_only_missing_frozen_item(tmp_path):
    class Upstream(DialogueUpstream):
        async def call(self, name, args):
            if name == 'outfit.resolve':
                return {'source': 'user', 'outfit_id': 1, 'title': '原搭配',
                        'items': [{**p, 'source': 'user'} for p in self.products[:2]]}
            return await super().call(name, args)
    upstream = Upstream('deleted-modify')
    model = Model('modify')
    engine = Stylist(Settings(), Store(str(tmp_path / 'modify.db')), model)
    entry = await engine.chat(upstream, ChatRequest(
        subject_outfit={'source': 'user', 'outfit_id': 1}, request_id='outfit-entry'))
    upstream.products = [p for p in upstream.products if p['product_id'] != '101']
    reply = await engine.chat(upstream, ChatRequest(
        message='换双鞋，其他保留，不考虑天气', request_id='modify-deleted',
        conversation_id=entry.conversation_id, expected_version=entry.version, weather_policy='ignored'))
    assert reply.delivery == 'outfit'
    assert model.payload['frozen_keys'] == ['user:102']
    assert any(p.product_id == '102' for p in reply.looks[0].items)
    assert any('不可用' in warning for warning in reply.warnings)


@pytest.mark.asyncio
async def test_deleted_uploaded_anchor_continues(tmp_path):
    import json
    upstream = DialogueUpstream('deleted-upload')
    upstream.products = [p for p in upstream.products if p['product_id'] != '101']
    store = Store(str(tmp_path / 'upload.db'))
    action = 'med_' + 'a' * 32
    with store.connection() as conn:
        conn.execute('INSERT INTO stylist_media_actions(id,owner_id,kind,digest,status,snapshot_json,result_json) VALUES(?,?,?,?,?,?,?)',
                     (action, await upstream.identity(), 'garment', 'fixture', 'completed', '{}',
                      json.dumps({'user_product_id': '101'})))
    reply = await Stylist(Settings(), store, Model()).chat(upstream, ChatRequest(
        message='用这件搭配下，不考虑天气', request_id='deleted-upload', upload_action_id=action,
        weather_policy='ignored'))
    assert reply.delivery == 'outfit'
    assert any('不可用' in warning for warning in reply.warnings)
    assert all(p.product_id != '101' for look in reply.looks for p in look.items)
