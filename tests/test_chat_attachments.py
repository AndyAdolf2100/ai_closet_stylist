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
