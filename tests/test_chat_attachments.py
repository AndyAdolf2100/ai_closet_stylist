"""Chat photo references are not wardrobe uploads; no real model or business writes."""
import base64
import json

import httpx
import pytest
from pydantic import BaseModel

from scripts.dialogue_validation import DialogueUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.images import ImageService
from stylist.llm import LanguageModel
from stylist.models import ChatRequest, Draft, Plan
from stylist.store import Store

IMAGE = 'data:image/png;base64,' + base64.b64encode(bytes.fromhex(
    '89504e470d0a1a0a0000000d4948445200000001000000010804000000b51c0c020000000b4944415478da6364f80f00010501012718e3660000000049454e44ae426082')).decode()


@pytest.mark.parametrize('image', ['https://example.com/photo.png', 'data:image/svg+xml;base64,PHN2Zy8+', 'data:image/jpeg;base64,bm90LWEtcGhvdG8='])
def test_reject_non_image_attachments(image):
    with pytest.raises(StylistError):
        ChatRequest(message='看看图片', request_id='attachment-validation', chat_image=image)


async def test_multimodal_transport_does_not_duplicate_image_in_text():
    class Result(BaseModel):
        ok: bool

    def respond(request):
        body = json.loads(request.content)
        content = body['messages'][1]['content']
        assert content[1] == {'type': 'image_url', 'image_url': {'url': IMAGE}}
        assert IMAGE not in content[0]['text']
        assert '不是衣橱库存或入柜授权' in body['messages'][0]['content']
        assert '无论用户是否说确认' in body['messages'][0]['content']
        assert '不能直接用来合成试穿、合成照片或创建数字人' in body['messages'][0]['content']
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"ok":true}'}}]})

    model = LanguageModel(Settings(llm_key='test', llm_model='test', llm_url='https://example.invalid'),
                          transport=httpx.MockTransport(respond))
    assert (await model.generate('plan', {'message': '看看图片', 'chat_image': IMAGE}, Result)).ok


async def test_attachment_reaches_plan_and_reply_without_ingestion_or_persistence(tmp_path):
    seen = []

    class Model:
        async def generate(self, name, payload, result_type):
            seen.append(name)
            assert payload['chat_image'] == IMAGE
            if name == 'plan':
                return Plan(mode='consult', use_inventory=False, conversation_only=True)
            return Draft(message='这张图片可以一起看看，你想聊配色还是穿法？')

    path = tmp_path / 'attachment.db'
    store = Store(str(path))
    upstream = DialogueUpstream('attachment-owner')
    reply = await Stylist(Settings(), store, Model()).chat(upstream, ChatRequest(
        message='请看看这张图片里的穿搭。', request_id='photo-reference-test', chat_image=IMAGE))
    assert reply.message
    assert 'plan' in seen and 'style' in seen
    assert not any('add_product' in call or 'upload' in call for call in upstream.calls)
    with store.connection() as conn:
        assert IMAGE not in '\n'.join(conn.iterdump())


@pytest.mark.parametrize('persona', ['female_sweet_v1', 'female_warm_v1', 'female_regal_v1',
                                    'male_artistic_v1', 'male_calm_v1', 'male_confident_v1'])
@pytest.mark.parametrize('attached', [True, False])
async def test_free_photo_generation_is_pending_not_a_business_action(tmp_path, persona, attached):
    from tests.test_avatar_intent import ReadOnlyUser, seed
    store = Store(str(tmp_path / 'photo-boundary.db'))
    cid, before = seed(store)
    class Model:
        async def generate(self, name, payload, result_type):
            assert name == 'plan'
            return Plan(mode='recommend', unsupported_image_request=True,
                        image_request_evidence='合成一张海边合照', avatar_intent='tryon',
                        avatar_evidence='合成一张海边合照', new_task=True)
    request = ChatRequest(message='用刚才的照片合成一张海边合照', request_id='photo-pending-test',
                          conversation_id=cid, expected_version=1, assistant_persona=persona,
                          chat_image=IMAGE if attached else None)
    reply = await Stylist(Settings(), store, Model()).chat(ReadOnlyUser(), request)
    if attached:
        assert reply.attachment_wardrobe_required and reply.upload_intent == 'garment'
        assert '个人衣橱' in reply.message and '单件' in reply.message
    else:
        assert '未开放' in reply.message or '没开放' in reply.message
        assert '没有生成图片' in reply.message
    assert reply.conversation_only and not reply.looks and not reply.weather
    assert reply.avatar_intent is None and reply.tryon_context is None
    if not attached:
        assert reply.upload_intent is None
    assert ImageService(store).context('avatar-test-owner', cid, reply.version).task == before.task


@pytest.mark.parametrize('kind', ['tryon', 'upload', 'garment'])
async def test_attachment_generation_requests_only_offer_existing_cards(tmp_path, kind):
    from tests.test_avatar_intent import ReadOnlyUser, seed
    store = Store(str(tmp_path / 'photo-cards.db'))
    cid, before = seed(store)
    message = {'tryon': '把这张照片拿去试穿', 'upload': '把这张照片变成数字人',
               'garment': '把图里这件衣服录入衣橱'}[kind]
    class Model:
        async def generate(self, name, payload, result_type):
            assert name == 'plan' and payload['chat_image'] == IMAGE
            return Plan(mode='recommend', avatar_intent=None if kind == 'garment' else kind,
                        avatar_evidence=message, upload_intent='garment' if kind == 'garment' else None,
                        upload_evidence=message)
    reply = await Stylist(Settings(), store, Model()).chat(ReadOnlyUser(), ChatRequest(
        message=message, request_id='attachment-card-test', chat_image=IMAGE,
        conversation_id=cid, expected_version=1))
    assert reply.conversation_only and not reply.looks
    assert reply.avatar_intent is None
    assert reply.upload_intent == 'garment' and reply.attachment_wardrobe_required
    assert ImageService(store).context('avatar-test-owner', cid, reply.version).task == before.task


async def test_uncited_pending_flag_does_not_block_normal_photo_analysis(tmp_path):
    from tests.test_avatar_intent import ReadOnlyUser
    class Model:
        async def generate(self, name, payload, result_type):
            return (Plan(mode='consult', conversation_only=True, use_inventory=False,
                         unsupported_image_request=True, image_request_evidence='不在本轮的原话')
                    if name == 'plan' else Draft(message='可以从配色和层次一起看看。'))
    reply = await Stylist(Settings(), Store(str(tmp_path/'analysis.db')), Model()).chat(
        ReadOnlyUser(), ChatRequest(message='只分析穿搭，不要生成图片', request_id='photo-analysis', chat_image=IMAGE))
    assert reply.message == '可以从配色和层次一起看看。'


@pytest.mark.parametrize('persona', ['female_sweet_v1', 'female_warm_v1', 'female_regal_v1',
                                    'male_artistic_v1', 'male_calm_v1', 'male_confident_v1'])
@pytest.mark.parametrize('message', ['帮我用图里的衣服搭一套', '给这件试穿一下', '合成一下', '给这张图换个背景'])
async def test_attachment_execution_always_invites_single_garment_upload(tmp_path, persona, message):
    from stylist.personas import attachment_wardrobe_invitation
    from tests.test_avatar_intent import ReadOnlyUser, seed
    store = Store(str(tmp_path / 'single-upload.db'))
    cid, before = seed(store)
    seen = []
    class Model:
        async def generate(self, name, payload, result_type):
            seen.append(name)
            return Plan(mode='consult', conversation_only=True, use_inventory=False)
    reply = await Stylist(Settings(), store, Model()).chat(ReadOnlyUser(), ChatRequest(
        message=message, chat_image=IMAGE, request_id='attachment-execute',
        conversation_id=cid, expected_version=1, assistant_persona=persona))
    assert seen == ['plan']
    assert reply.attachment_wardrobe_required and reply.upload_intent == 'garment'
    assert reply.avatar_intent is None and not reply.looks and reply.weather is None
    assert reply.message == attachment_wardrobe_invitation(persona)
    assert ImageService(store).context('avatar-test-owner', cid, reply.version).task == before.task
    with store.connection() as conn:
        assert IMAGE not in '\n'.join(conn.iterdump())


@pytest.mark.parametrize('message', ['只分析穿搭，不要生成图片', '朋友说想试穿，帮我分析这张图的配色',
                                    '假设以后可以合成，原理是什么', '试穿怎么收费'])
async def test_analysis_negation_reported_and_cost_questions_do_not_invite_upload(tmp_path, message):
    from tests.test_avatar_intent import ReadOnlyUser
    class Model:
        async def generate(self, name, payload, result_type):
            return (Plan(mode='consult', conversation_only=True, use_inventory=False,
                         attachment_wardrobe_required=True, attachment_action_evidence=message)
                    if name == 'plan' else Draft(message='先按你的问题看配色和层次。'))
    reply = await Stylist(Settings(), Store(str(tmp_path/'analysis-boundary.db')), Model()).chat(
        ReadOnlyUser(), ChatRequest(message=message, request_id='attachment-analysis-boundary', chat_image=IMAGE))
    assert not reply.attachment_wardrobe_required and reply.upload_intent is None
    assert reply.message == '先按你的问题看配色和层次。'


@pytest.mark.parametrize('message,attached', [('照着这张图整一身', True), ('帮我换个新模样', True),
                                              ('用刚才那张照片试一下', False)])
async def test_cited_semantic_attachment_intent_handles_paraphrases_without_reusing_old_image(tmp_path, message, attached):
    from tests.test_avatar_intent import ReadOnlyUser
    seen = []
    class Model:
        async def generate(self, name, payload, result_type):
            seen.append(name)
            assert payload['chat_image'] == (IMAGE if attached else None)
            return Plan(mode='consult', conversation_only=True, attachment_wardrobe_required=True,
                        attachment_action_evidence=message)
    reply = await Stylist(Settings(), Store(str(tmp_path/'semantic-photo.db')), Model()).chat(
        ReadOnlyUser(), ChatRequest(message=message, request_id='semantic-photo-request',
                                    chat_image=IMAGE if attached else None))
    assert seen == ['plan'] and reply.attachment_wardrobe_required
    assert reply.upload_intent == 'garment' and reply.avatar_intent is None
