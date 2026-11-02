"""Avatar dialogue routing must never authorize paid generation."""
from contextlib import asynccontextmanager

import pytest

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.images import ImageService
from stylist.models import ChatRequest, Draft, Look, Plan, Product, Reply, Task
from stylist.store import Store


class ReadOnlyUser:
    async def identity(self):
        return 'avatar-test-owner'

    @asynccontextmanager
    async def mcp(self, **kwargs):
        raise AssertionError('Avatar dialogue must not call business tools')
        yield


def seed(store, *, empty=False):
    request = ChatRequest(message='已生成的衣橱搭配', request_id='avatar-seed')
    cid, claim, state, _ = store.reserve('avatar-test-owner', request)
    state.task = Task(scene='通勤', excluded_colors=['黄色'])
    state.looks = [] if empty else [Look(title=title, items=[Product(source='user', product_id=str(i), slot='top')])
                                    for i, title in [(101, '第一套'), (102, '第二套')]]
    store.finish('avatar-test-owner', request, claim, state, Reply(conversation_id=cid, version=1,
        mode='recommend', delivery='outfit', message='原搭配', task=state.task, looks=state.looks))
    return cid, state


@pytest.mark.parametrize('persona', ['female_warm_v1','male_calm_v1','female_sweet_v1','female_regal_v1','male_artistic_v1','male_confident_v1'])
@pytest.mark.parametrize('intent', ['upload','view','tryon'])
async def test_avatar_cards_preserve_task_and_bind_confirmed_conversation_version(tmp_path, persona, intent):
    store = Store(str(tmp_path/'avatars.db'))
    cid, before = seed(store)
    class Model:
        calls = []
        async def generate(self, name, payload, result_type):
            self.calls.append(name)
            assert name == 'plan'
            return Plan(mode='recommend', avatar_intent=intent, avatar_evidence='虚拟形象',
                        upload_intent='unspecified', upload_evidence='虚拟形象', avatar_look_index=1)
    model = Model()
    request = ChatRequest(message='用第二套搭配的虚拟形象', request_id='avatar-request',
        conversation_id=cid, expected_version=1, selected_look_index=0, assistant_persona=persona, confirm_plan=True)
    reply = await Stylist(Settings(), store, model).chat(ReadOnlyUser(), request)
    assert reply.avatar_intent == intent and reply.upload_intent is None and not reply.upload_suggestion
    assert reply.conversation_only and not reply.looks and not reply.weather and not reply.pending_confirmation
    assert reply.tryon_context.look_index == 1 and reply.tryon_context.version == 2
    assert reply.tryon_title == '第二套'
    state = ImageService(store).context('avatar-test-owner', cid, reply.version)
    assert state.task == before.task and state.looks == before.looks
    assert state.looks[reply.tryon_context.look_index].items[0].product_id == '102'
    replay = await Stylist(Settings(), store, model).chat(ReadOnlyUser(), request)
    assert replay == reply and model.calls == ['plan']


@pytest.mark.parametrize('empty,index', [(True,0),(False,6)])
async def test_missing_or_invalid_outfit_has_no_generation_reference(tmp_path, empty, index):
    store = Store(str(tmp_path/'empty.db'))
    cid,_ = seed(store, empty=empty)
    class Model:
        async def generate(self, *args):
            return Plan(mode='consult', avatar_intent='tryon', avatar_evidence='开始试穿', avatar_look_index=index)
    reply = await Stylist(Settings(), store, Model()).chat(ReadOnlyUser(), ChatRequest(message='开始试穿',
        request_id='avatar-empty', conversation_id=cid, expected_version=1))
    assert reply.avatar_intent == 'tryon' and reply.tryon_context is None
    assert '还没有' in reply.message


@pytest.mark.parametrize('declined,evidence', [(True,'别试穿'),(False,'不在本轮中的原文')])
async def test_refusal_or_unverified_intent_cannot_trigger_avatar_card(tmp_path, declined, evidence):
    class Model:
        async def generate(self, name, payload, result_type):
            return (Plan(mode='consult', conversation_only=True, avatar_intent='tryon',
                         avatar_evidence=evidence, avatar_declined=declined) if name == 'plan' else Draft(message='先不试穿。'))
    reply = await Stylist(Settings(), Store(str(tmp_path/'refused.db')), Model()).chat(ReadOnlyUser(),
        ChatRequest(message='别试穿', request_id='avatar-refused'))
    assert reply.avatar_intent is None and reply.tryon_context is None


async def test_new_turn_invalidates_a_previous_card_generation_reference(tmp_path):
    store=Store(str(tmp_path/'stale.db'))
    cid,_=seed(store)
    class Model:
        async def generate(self, *args):
            return Plan(mode='consult', avatar_intent='view', avatar_evidence='查看形象')
    first=await Stylist(Settings(),store,Model()).chat(ReadOnlyUser(),ChatRequest(message='查看形象',
        request_id='avatar-view-01',conversation_id=cid,expected_version=1))
    await Stylist(Settings(),store,Model()).chat(ReadOnlyUser(),ChatRequest(message='查看形象',
        request_id='avatar-view-02',conversation_id=cid,expected_version=2))
    with pytest.raises(StylistError,match='stale_version'):
        ImageService(store).context('avatar-test-owner',cid,first.tryon_context.version)
