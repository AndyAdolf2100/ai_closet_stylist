from contextlib import asynccontextmanager

import pytest

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import ChatRequest
from stylist.store import Store


class NoModel:
    async def generate(self, *args, **kwargs):
        raise AssertionError("detail-page entry must not invoke the language model")


class EntryUpstream:
    authorization = "Bearer test"

    def __init__(self, result):
        self.result = result
        self.calls = []

    async def identity(self):
        self.calls.append("identity")
        return "1"

    @asynccontextmanager
    async def mcp(self):
        yield self

    async def call(self, name, args):
        self.calls.append((name, args))
        return self.result


@pytest.mark.asyncio
async def test_product_detail_entry_echoes_authoritative_product_without_model(tmp_path):
    upstream = EntryUpstream({"items": [{
        "source": "user", "product_id": "12", "title": "白衬衫",
        "class_name": "上衣", "secondary_class_name": "衬衫",
        "features_desc": "棉质", "original_image": "https://img/original.png",
        "cutout_image": "https://img/cutout.png", "color": "白色",
    }]})
    engine = Stylist(Settings(), Store(str(tmp_path / "entry.db")), NoModel())
    reply = await engine.chat(upstream, ChatRequest(
        subject_product={"source": "user", "product_id": "12"}, request_id="product-entry-001"))
    assert reply.product_entry["title"] == "白衬衫"
    assert reply.product_entry["image_url"] == "https://img/cutout.png"
    assert reply.subject_product.product_id == "12"
    assert reply.version == 1 and reply.conversation_id.startswith("sty_")
    assert upstream.calls[1][0] == "product.resolve"
    assert engine.store.history("1", reply.conversation_id)["messages"][0]["user"] == "帮我查看下这件"
    replay = await engine.chat(upstream, ChatRequest(
        subject_product={"source": "user", "product_id": "12"}, request_id="product-entry-001"))
    assert replay.conversation_id == reply.conversation_id
    # Replaying still revalidates identity, but must not resolve the product twice.
    assert upstream.calls.count("identity") == 2
    assert sum(isinstance(call, tuple) and call[0] == "product.resolve" for call in upstream.calls) == 1


@pytest.mark.asyncio
async def test_saved_outfit_detail_entry_echoes_canvas_and_items(tmp_path):
    upstream = EntryUpstream({
        "source": "user", "outfit_id": 72, "title": "周末通勤",
        "description": "轻松穿法", "presentation": {"canvas_image": "https://img/canvas.png"},
        "items": [{"source": "user", "product_id": "12", "title": "白衬衫",
                   "class_name": "上衣", "secondary_class_name": "衬衫",
                   "original_image": "https://img/original.png", "cutout_image": "https://img/cutout.png",
                   "description": "棉质", "gender": "女", "color": "白色", "material": "棉"}],
    })
    engine = Stylist(Settings(), Store(str(tmp_path / "outfit-entry.db")), NoModel())
    reply = await engine.chat(upstream, ChatRequest(
        subject_outfit={"source": "user", "outfit_id": 72}, request_id="outfit-entry-001"))
    assert reply.outfit_entry["title"] == "周末通勤"
    assert reply.outfit_entry["presentation"]["canvas_image"].endswith("canvas.png")
    assert reply.looks[0].items[0].product_id == "12"
    assert reply.subject_outfit.outfit_id == 72


def test_detail_entry_requires_a_reference_when_message_is_empty():
    with pytest.raises(ValueError):
        ChatRequest(message="", request_id="entry-invalid")


@pytest.mark.asyncio
async def test_subject_product_pair_action_retains_authoritative_item_even_if_model_misroutes(tmp_path):
    from scripts.dialogue_validation import DialogueUpstream
    from stylist.models import Draft, LookDraft, Plan

    class Model:
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='consult', conversation_only=True, use_inventory=False,
                            technical_question=True, upload_intent='garment')
            assert payload['frozen_keys'] == ['user:101']
            return Draft(message='围绕这件白衬衫搭配。', looks=[LookDraft(
                title='白衬衫穿搭', selected_keys=['user:101', 'user:102', 'user:103'], why=['围绕当前单品'], how=['自然穿着'])])

    upstream = DialogueUpstream('subject-pair')
    engine = Stylist(Settings(), Store(str(tmp_path / 'pair.db')), Model())
    entry = await engine.chat(upstream, ChatRequest(
        subject_product={'source': 'user', 'product_id': '101'}, request_id='subject-entry-pair'))
    assert len(entry.looks) == 1 and entry.looks[0].items[0].product_id == '101'
    reply = await engine.chat(upstream, ChatRequest(
        message='用当前这件，从我的衣橱搭一套。', request_id='subject-pair-action',
        conversation_id=entry.conversation_id, expected_version=entry.version,
        pair_subject_product=True))
    assert reply.delivery == 'outfit'
    assert any(p.product_id == '101' for p in reply.looks[0].items)
    assert not reply.upload_suggestion


@pytest.mark.asyncio
async def test_subject_product_tryon_only_quotes_one_item_without_dispatch(tmp_path):
    from types import SimpleNamespace

    from stylist.images import ImageQuoteRequest, ImageService

    class Upstream(EntryUpstream):
        async def call(self, name, args):
            self.calls.append((name, args))
            if name == 'product.resolve':
                return {'items': [{'source': 'user', 'product_id': '12', 'title': '白衬衫',
                                   'class_name': '上衣', 'cutout_image': 'https://img/shirt.png'}]}
            if name == 'digital_twin_overview':
                return {'default_confirmed': True, 'default_twin_key': 'preset-1'}
            if name == 'digital_twin_tryon_quote':
                return {'points_cost': 2}
            raise AssertionError('Opening or quoting must never dispatch a paid image')

        async def discover(self):
            return {name: SimpleNamespace(model_dump=lambda **kw: {'schema': 'stable'}) for name in
                    ['save_recommended_outfit', 'digital_twin_tryon']}

    upstream = Upstream(None)
    store = Store(str(tmp_path / 'single-tryon.db'))
    entry = await Stylist(Settings(), store, NoModel()).chat(upstream, ChatRequest(
        subject_product={'source': 'user', 'product_id': '12'}, request_id='subject-entry-tryon'))
    q = await ImageService(store).quote(upstream, ImageQuoteRequest(
        conversation_id=entry.conversation_id, version=entry.version, look_index=0))
    assert q['status'] == 'quoted' and q['item_count'] == 1 and q['points_cost'] == 2
    assert not any(isinstance(call, tuple) and call[0] in {'save_recommended_outfit', 'digital_twin_tryon'}
                   for call in upstream.calls)


def test_subject_pair_requires_current_conversation_and_cannot_mix_upload_or_entry():
    for fields in [{}, {'conversation_id': 'sty_'+'1'*32, 'expected_version': 1,
                        'subject_product': {'source': 'user', 'product_id': '12'}}]:
        with pytest.raises(ValueError):
            ChatRequest(message='用这件搭一套', request_id='invalid-subject-pair',
                        pair_subject_product=True, **fields)
