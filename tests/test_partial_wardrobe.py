"""Only owned clothes enter images, even when an outfit needs more categories."""
import pytest

from scripts.dialogue_validation import DialogueUpstream
from stylist.composition import Compositions
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.models import Change, ChatRequest, Draft, LookDraft, Plan, Product, Slot, Task
from stylist.policy import validate_look
from stylist.store import Store


@pytest.mark.asyncio
@pytest.mark.parametrize('persona', ['male_calm_v1', 'female_warm_v1'])
@pytest.mark.parametrize('message,mode', [
    ('帮我找一件衬衫，不考虑天气', 'consult'),
    ('只给我一套穿搭，不考虑天气', 'consult'),
    ('白衬衫配什么裤子，不考虑天气', 'consult'),
    ('帮我搭一套，不考虑天气', 'recommend'),
    ('约会想穿得年轻一点，不考虑天气', 'consult'),
])
async def test_five_suggestions_with_one_owned_piece_keep_one_photo_and_four_references(tmp_path, persona, message, mode):
    upstream = DialogueUpstream('partial-test')
    upstream.products = [{'product_id': '101', 'class_name': '上衣', 'title': '白色衬衫',
                          'color': '白色', 'original_image': 'https://example.invalid/owned-shirt.jpg'}]
    class Model:
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                # Even an erroneous use_inventory=false must not skip the default read.
                return Plan(mode=mode, use_inventory=False, changes={
                    'occasion': Change(value='约会', evidence='约会')} if '约会' in message else {})
            assert len(payload['candidates']) == 1
            return Draft(message='先用衣橱的衬衫，其余列为品类参考。', looks=[LookDraft(
                title='衬衫日常穿搭', selected_keys=['user:101'],
                pieces=['白色衬衫', '长裤', '外套', '平底鞋', '包'],
                reference_pieces=['长裤', '外套', '平底鞋', '包'],
                why=['使用已有的白色衬衫'], how=['其他品类按实际拥有情况组合'])])
    store = Store(str(tmp_path / 'partial.db'))
    reply = await Stylist(Settings(), store, Model()).chat(upstream, ChatRequest(
        message=message, request_id='partial-one-of-five', assistant_persona=persona, weather_policy='ignored'))
    assert '/api/user_product/quick_edit_list' in upstream.calls
    assert reply.delivery == 'outfit'
    look = reply.looks[0]
    assert [p.key for p in look.items] == ['user:101']
    assert len(look.pieces) == 5 and len(look.reference_pieces) == 4
    assert look.wardrobe_complete is False
    assert look.items[0].original_image == 'https://example.invalid/owned-shirt.jpg'
    # Persistence and the image binding accept this partial look; other accounts cannot access it.
    persisted = Store(store.path).history(await upstream.identity(), reply.conversation_id)['messages'][0]['reply']
    assert persisted['looks'][0]['reference_pieces'] == look.reference_pieces
    assert Compositions(store).get(await upstream.identity(), reply.conversation_id, reply.version, 0, 'female')['status'] == 'missing'
    with pytest.raises(StylistError):
        Compositions(store).get('another-owner', reply.conversation_id, reply.version, 0, 'female')


@pytest.mark.asyncio
async def test_empty_wardrobe_stays_text_only(tmp_path):
    upstream = DialogueUpstream('empty_wardrobe')
    class Model:
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='recommend', use_inventory=False)
            assert payload['candidates'] == []
            return Draft(message='本次衣橱没有返回衣物，先给文字参考。', looks=[LookDraft(
                title='文字参考', pieces=['衬衫', '长裤', '平底鞋'], why=['日常组合'], how=['按已有单品调整'])])
    reply = await Stylist(Settings(), Store(str(tmp_path / 'empty.db')), Model()).chat(upstream, ChatRequest(
        message='帮我推荐一套，不考虑天气', request_id='empty-wardrobe-query', weather_policy='ignored'))
    assert '/api/user_product/quick_edit_list' in upstream.calls
    assert reply.delivery == 'concept' and not reply.looks[0].items


def test_partial_selection_keeps_hard_rules_and_frozen_pieces():
    top = Product(source='user', product_id='1', slot=Slot.TOP, title='衬衫', color='黄色')
    bottom = Product(source='user', product_id='2', slot=Slot.BOTTOM)
    pool = {p.key: p for p in [top, bottom]}
    assert not validate_look([top.key], pool, Task(), set(), require_complete=False)
    assert validate_look([top.key], pool, Task(excluded_colors=['黄色']), set(), require_complete=False)
    assert validate_look([top.key], pool, Task(), {bottom.key}, require_complete=False)
    assert validate_look(['system:1'], pool, Task(), set(), require_complete=False)
    assert Stylist.check_draft(Draft(message='文字', looks=[LookDraft(
        title='建议', why=['搭配'], how=['穿法'])]), pool, Task(), [], 'recommend')


@pytest.mark.asyncio
async def test_weather_failure_does_not_hide_available_personal_piece(tmp_path):
    from stylist.models import CitySelection

    upstream = DialogueUpstream('partial-test')
    upstream.products = [{'product_id': '101', 'class_name': '上衣', 'title': '白衬衫', 'color': '白色'}]
    class Weather:
        async def forecast(self, *args):
            raise StylistError('forecast_unavailable', '模拟天气暂不可用')
    class Model:
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='recommend')
            assert len(payload['candidates']) == 1 and not payload['concept_fallback']
            return Draft(message='天气暂未查到，先用已有衬衫搭配。', looks=[LookDraft(
                title='衬衫搭配', selected_keys=['user:101'], reference_pieces=['长裤', '鞋'],
                why=['保留个人衣物'], how=['按实际体感调整'])])
    engine = Stylist(Settings(), Store(str(tmp_path / 'weather-partial.db')), Model())
    engine.weather = Weather()
    reply = await engine.chat(upstream, ChatRequest(message='推荐一套衣服', request_id='weather-partial-keep',
                                                  location=CitySelection(city_name='示例市')))
    assert reply.delivery == 'outfit' and reply.looks[0].items[0].key == 'user:101'
    assert reply.looks[0].wardrobe_complete is False
