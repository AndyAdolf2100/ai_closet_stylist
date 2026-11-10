"""Empty inventory must remain textual even with an active weather location."""
from datetime import timedelta

import pytest

from scripts.dialogue_validation import DialogueUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import Change, ChatRequest, CitySelection, Draft, LookDraft, Plan
from stylist.store import Store
from stylist.weather import today


@pytest.mark.asyncio
@pytest.mark.parametrize('located', [False, True])
@pytest.mark.parametrize('stock', ['empty', 'filtered'])
@pytest.mark.parametrize('persona', ['female_warm_v1', 'male_calm_v1'])
async def test_empty_inventory_never_resolves_model_invented_ids(tmp_path, located, persona, stock):
    class Business(DialogueUpstream):
        async def forecast(self, city):
            self.calls.append('forecast')
            return {'list': [{'data_format': (today()+timedelta(days=i)).isoformat(),
                             'temp_day': 10, 'temp_night': 2, 'condition_day': '阴', 'condition_night': '阴'}
                            for i in range(14)]}
    class Model:
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='recommend', use_inventory=True, changes={'excluded_colors': Change(value=['黄色'], evidence='不选黄色')})
            assert not payload['candidates']
            return Draft(message='已经从衣橱选好了。', looks=[LookDraft(
                title='文字方案', selected_keys=['user:101'], pieces=['衬衫', '长裤', '包脚平底鞋'],
                why=['简洁配色'], how=['领口、袖口整理平整。'])])
    upstream = Business('empty_wardrobe' if stock == 'empty' else 'partial-test')
    if stock == 'filtered':
        upstream.products = [{'product_id':'101','class_name':'上衣','title':'黄色衬衫','color':'黄色','material':'棉'}]
    reply = await Stylist(Settings(), Store(str(tmp_path/'empty.db')), Model()).chat(upstream,
        ChatRequest(message='帮我搭一套，不选黄色', request_id='empty-located-reference', assistant_persona=persona,
                    location=CitySelection(city_name='上海市', province_name='上海市') if located else None))
    assert reply.delivery == 'concept'
    assert reply.reference_reason == ('no_match' if stock == 'filtered' else 'no_candidates')
    assert reply.wardrobe_gap and not reply.new_clothes
    if stock == 'filtered':
        assert '要求' in reply.message and '黄色' in reply.message
    assert reply.looks and all(not x.items for x in reply.looks)
    assert '选好了' not in reply.message
    if located:
        assert reply.weather and 'forecast' in upstream.calls
        assert any('外套' in s for x in reply.looks for s in x.reference_pieces)
    if stock == 'empty':
        assert 'product.resolve' not in upstream.calls
