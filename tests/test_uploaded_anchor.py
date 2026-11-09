import pytest

from scripts.dialogue_validation import DialogueUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.media import MediaActions
from stylist.models import ChatRequest, Draft, LookDraft, Plan
from stylist.store import Store


@pytest.mark.parametrize('persona', ['female_warm_v1', 'male_calm_v1'])
async def test_newly_uploaded_item_is_resolved_and_retained_even_before_search_index_updates(tmp_path, persona):
    class Upstream(DialogueUpstream):
        async def call(self, name, args):
            if name == 'product.resolve' and args['items'] == [{'source': 'user', 'product_id': '999'}]:
                return {'items': [{'source': 'user', 'product_id': '999', 'class_name': '上衣',
                                   'title': '刚上传的蓝色衬衫', 'color': '蓝色',
                                   'cutout_image': 'https://example.test/new-shirt.png'}]}
            return await super().call(name, args)
    upstream = Upstream('upload-anchor')
    owner = await upstream.identity()
    store = Store(str(tmp_path/'anchor.db'))
    media = MediaActions(store)
    row, _ = media.reserve(owner, 'uploaded-shirt', 'garment', 'synthetic', {})
    media.save(owner, row['id'], {'status': 'completed', 'user_product_id': 999})
    class Model:
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                # The upload-card action is authoritative even when the model
                # mislabels the generated sentence as another intent.
                return Plan(mode='consult', conversation_only=True, use_inventory=False,
                            technical_question=True, unsupported_image_request=True,
                            avatar_intent='view', upload_intent='garment')
            assert payload['frozen_keys'] == ['user:999']
            assert any(p['key'] == 'user:999' for p in payload['candidates'])
            return Draft(message='围绕刚上传的衬衫来搭配。', looks=[LookDraft(title='新衬衫穿搭',
                selected_keys=['user:999'], pieces=['蓝色衬衫', '长裤', '平底鞋'],
                reference_pieces=['长裤', '平底鞋'], why=['从自己的衣服开始'], how=['按温度增减层次'])])
    reply = await Stylist(Settings(), store, Model()).chat(upstream, ChatRequest(
        message='用我刚上传的这件衣服搭一套，不考虑天气。', request_id='anchor-outfit-001',
        upload_action_id=row['id'], assistant_persona=persona))
    assert reply.looks[0].items[0].product_id == '999'
    assert reply.looks[0].items[0].cutout_image.endswith('new-shirt.png')
    assert not reply.upload_suggestion  # Styling an uploaded item does not request another upload.


async def test_upload_from_another_account_cannot_be_used_as_anchor(tmp_path):
    upstream = DialogueUpstream('upload-anchor')
    store = Store(str(tmp_path/'isolation.db'))
    media = MediaActions(store)
    row, _ = media.reserve('other-account', 'other-upload', 'garment', 'synthetic', {})
    media.save('other-account', row['id'], {'status': 'completed', 'user_product_id': 999})
    class Model:
        async def generate(self, name, payload, result_type):
            return Plan(mode='recommend')
    with pytest.raises(StylistError, match='media_not_found'):
        await Stylist(Settings(), store, Model()).chat(upstream, ChatRequest(message='用刚上传的衣服搭一套，不考虑天气',
            request_id='foreign-anchor-001', upload_action_id=row['id']))


@pytest.mark.parametrize('persona', ['female_warm_v1', 'male_calm_v1'])
async def test_beijing_city_survives_upload_and_missing_outer_is_repaired(tmp_path, persona):
    from stylist.models import Change

    class Upstream(DialogueUpstream):
        async def call(self, name, args):
            if name == 'product.resolve' and args['items'] == [{'source': 'user', 'product_id': '999'}]:
                return {'items': [{'source':'user','product_id':'999','class_name':'上衣',
                                   'title':'刚上传的白色短袖','color':'白色'}]}
            return await super().call(name, args)
    upstream = Upstream('upload-cold')
    store = Store(str(tmp_path/'weather-anchor.db'))
    media = MediaActions(store)
    owner = await upstream.identity()
    row, _ = media.reserve(owner,'cold-shirt','garment','synthetic',{})
    media.save(owner,row['id'],{'status':'completed','user_product_id':999})
    style_calls = []

    class Model:
        async def generate(self,name,payload,result_type):
            if name == 'plan':
                if payload['message'] == '看看北京今天的天气':
                    return Plan(mode='consult',weather_only=True,weather_scope='day',use_inventory=False,
                                changes={'city':Change(value='北京市',evidence='北京')})
                return Plan(mode='recommend')
            if payload['conversation_only'] or payload['weather_only']:
                return Draft(message='好，我们接着聊。')
            assert payload['task']['city']=='北京市'
            assert payload['layering_requirements'][0]['temp_min']==3
            assert payload['layering_requirements']
            assert 'user:999' in payload['frozen_keys']
            style_calls.append(payload)
            keys=['user:999','user:102','user:103']
            if payload.get('validation_errors'):
                assert any('天气外层' in error for error in payload['validation_errors'])
                keys.append('user:105')
            return Draft(message='从新上传的短袖开始搭。',looks=[LookDraft(title='短袖叠穿',
                selected_keys=keys,why=['保留刚上传的衣物'],how=['早晚穿上外套，白天按体感脱减'],
                notes=['外套实际厚度和保暖性需要核对，不能保证夜间足够保暖'])])

    engine=Stylist(Settings(),store,Model())
    async def forecast(_upstream,city,province,scope,event_date):
        assert city=='北京市'
        return {'source':'synthetic','city_name':city,'province_name':'北京市',
                'days':[{'date':event_date.isoformat(),'temp_min':3,'temp_max':17,
                         'condition_day':'晴','condition_night':'晴'}],'warnings':[]}
    engine.weather.forecast=forecast
    first=await engine.chat(upstream,ChatRequest(message='看看北京今天的天气',request_id='cold-first',assistant_persona=persona))
    reply=await engine.chat(upstream,ChatRequest(message='用我刚上传的这件衣服，结合自己的衣橱搭一套。',
        request_id='cold-second',conversation_id=first.conversation_id,expected_version=first.version,
        assistant_persona=persona,upload_action_id=row['id']))
    assert reply.task.city=='北京市' and not reply.city_selection_required
    assert {item.product_id for item in reply.looks[0].items} >= {'999','105'}
    assert len(style_calls)==2  # A prose-only reminder is rejected, then the outfit is repaired.
