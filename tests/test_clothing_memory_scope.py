import json
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.memory import (
    MemoryBook,
    MemoryEntry,
    automatic_preference,
    clothing_content,
    explicit_memory,
    strip_save_claims,
)
from stylist.models import Change, ChatRequest, Draft, LookDraft, MemorySave, Plan, SessionState, Task
from stylist.personas import PersonaId, upload_invitation
from stylist.policy import interpret_task
from stylist.store import Store


class User:
    async def identity(self):
        return 'synthetic-clothing-scope'


class ChatModel:
    async def generate(self, name, payload, result_type):
        if name == 'plan':
            return Plan(mode='recommend', use_inventory=True, changes={
                'preferences': Change(value=['喜欢短袖'], evidence=payload['message'])})
        return Draft(message='收到，我们按这次话题聊。')


@pytest.mark.parametrize('text', ['我喜欢乌龙茶', '我喜欢简洁的回复', '以后叫我亲爱的',
                                  '我喜欢蓝色杯子', '我喜欢昨晚的蓝色衬衫合照'])
def test_daily_interaction_and_incidental_color_are_not_clothing_notes(text):
    assert not clothing_content(text)
    assert automatic_preference(text) is None
    assert explicit_memory('记住：' + text) is None


def test_mixed_preference_keeps_clothes_only_without_flipping_polarity():
    entry = automatic_preference('我喜欢蓝色，我偏爱乌龙茶，我不喜欢羊毛衣。')
    assert entry.content == '我喜欢蓝色；我不喜欢羊毛衣'
    assert entry.category == '穿衣习惯'
    entry = automatic_preference('我喜欢裙子，我不喜欢乌龙茶，衬衫。')
    assert entry.content == '我喜欢裙子'


@pytest.mark.parametrize('persona', get_args(PersonaId))
@pytest.mark.asyncio
async def test_address_refusal_cannot_become_a_notebook_request(tmp_path, persona):
    class NoModel:
        async def generate(self, *args):
            raise AssertionError('A clear address boundary needs no model or notebook operation')
    store = Store(str(tmp_path / 'scope.db'))
    reply = await Stylist(Settings(), store, NoModel()).chat(User(), ChatRequest(
        message='别叫我宝贝，我不喜欢。', request_id='address-stop', assistant_persona=persona))
    assert reply.conversation_only and not reply.looks
    assert '保存' not in reply.message and '具体' not in reply.message
    assert not store.memory_book(await User().identity()).entries


@pytest.mark.asyncio
async def test_address_boundary_preserves_requested_one_sentence_goodnight(tmp_path):
    class NoModel:
        async def generate(self, *args):
            raise AssertionError('A one-sentence goodnight needs no extraction')
    reply = await Stylist(Settings(), Store(str(tmp_path / 'scope.db')), NoModel()).chat(User(), ChatRequest(
        message='别开玩笑，也别用亲昵称呼。正常说一句晚安，不用给我安排事情。', request_id='boundary-goodnight'))
    assert reply.message == '晚安。'


@pytest.mark.asyncio
async def test_boundary_does_not_swallow_an_explicit_outfit_request(tmp_path):
    message = '别叫我宝贝，我喜欢短袖，帮我搭一套。'
    plan, task = await interpret_task(ChatModel(), {'message': message}, SessionState(), message)
    assert not plan.conversation_only and plan.memory_save is None
    assert task.preferences == ['喜欢短袖']


@pytest.mark.parametrize('assistant_voice', ['我可以把鞋子换掉', '告诉我你喜欢的颜色，我帮你选'])
def test_shortcuts_remain_in_user_voice(assistant_voice):
    from stylist.grounding import normalize_draft
    draft = normalize_draft(Draft(message='继续聊。', follow_ups=[
        assistant_voice, '帮我换成平底鞋', '我想看看更休闲的穿法']))
    assert draft.follow_ups == ['帮我换成平底鞋', '我想看看更休闲的穿法']


def test_receipt_cleanup_preserves_clothing_acknowledgement_in_same_sentence():
    assert strip_save_claims('记住啦，日常走路多就优先选平底鞋，不穿高跟鞋这点我会帮你避开。') == (
        '日常走路多就优先选平底鞋，不穿高跟鞋这点我会帮你避开。')
    assert strip_save_claims('我记下了：你不穿高跟鞋，而且平时走路比较多。') == '你不穿高跟鞋，而且平时走路比较多。'
    assert strip_save_claims('我还不能确认保存成功，先不说记住了。棉质衬衫很耐看。') == '棉质衬衫很耐看。'
    assert strip_save_claims('羊毛衣我记下你不喜欢，之后做搭配会避开。') == '羊毛衣你不喜欢，之后做搭配会避开。'


def test_selected_skill_focus_is_distinct_and_respects_no_flirting():
    from stylist.personas import persona_reply_focus
    focus = [persona_reply_focus(persona, '想听一句有点心动的话。') for persona in get_args(PersonaId)]
    assert all(focus) and len(set(focus)) == 6
    assert not persona_reply_focus('male_calm_v1', '不要情话，正常说话。')
    assert not persona_reply_focus('male_calm_v1', '今天穿什么？')


@pytest.mark.asyncio
async def test_daily_event_style_payload_separates_episode_from_preferences(tmp_path):
    class Model:
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='consult', conversation_only=True)
            assert payload['current_event_facts']['user_statement'] == '我昨天穿蓝色衬衫去喝茶。'
            assert '不能证明' in payload['current_event_facts']['instruction']
            return Draft(message='蓝色衬衫去喝茶，听着很舒服。')
    reply = await Stylist(Settings(), Store(str(tmp_path/'event.db')), Model()).chat(User(), ChatRequest(
        message='我昨天穿蓝色衬衫去喝茶。', request_id='event-grounding'))
    assert '棉质' not in reply.message


@pytest.mark.parametrize('persona', get_args(PersonaId))
@pytest.mark.asyncio
async def test_mixed_save_receipt_identifies_the_actual_clothing_portion(tmp_path, persona):
    store = Store(str(tmp_path / 'scope.db'))
    reply = await Stylist(Settings(), store, ChatModel()).chat(User(), ChatRequest(
        message='我喜欢蓝色，我偏爱乌龙茶。', request_id='mixed-receipt', assistant_persona=persona))
    assert '记下的穿搭部分：我喜欢蓝色' in reply.message
    assert [entry.content for entry in store.memory_book(await User().identity()).entries] == ['我喜欢蓝色']


@pytest.mark.asyncio
async def test_save_complaint_uses_existing_record_instead_of_model_denial(tmp_path):
    class Model(ChatModel):
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='consult', conversation_only=True)
            return Draft(message='我先不往手记里加新的，等你明确说要保存哪条。棉质衬衫很耐看。')
    store = Store(str(tmp_path / 'scope.db'))
    store.save_memory_book(await User().identity(), MemoryBook(entries=[
        MemoryEntry(id='existing', content='我喜欢棉质衬衫')]))
    reply = await Stylist(Settings(), store, Model()).chat(User(), ChatRequest(
        message='我喜欢棉质衬衫，不喜欢的没有保存。', request_id='existing-record'))
    assert '已经在手记里' in reply.message and '等你明确' not in reply.message
    assert len(store.memory_book(await User().identity()).entries) == 1


def test_wholly_textual_cards_have_one_garment_list_but_partial_owned_cards_keep_references():
    from stylist.grounding import normalize_draft
    text = LookDraft(title='穿法', pieces=['白衬衫', '灰裤'], reference_pieces=['灰裤', '平底鞋'],
                     why=['简洁配色'], how=['整理领口'])
    owned = text.model_copy(update={'selected_keys': ['user:101']})
    result = normalize_draft(Draft(message='穿法。', looks=[text, owned]))
    assert result.looks[0].pieces == ['白衬衫', '灰裤', '平底鞋']
    assert not result.looks[0].reference_pieces
    assert result.looks[1].reference_pieces == ['灰裤', '平底鞋']


@pytest.mark.asyncio
async def test_query_metadata_filter_preserves_a_real_clothing_condition():
    class Model:
        async def generate(self, *args):
            return Plan(mode='consult', use_inventory=False, changes={
                'preferences': Change(value=['只要宽松版型，不查衣橱'], evidence='只要宽松版型，不查衣橱')})
    message = '只要宽松版型，不查衣橱。讲讲怎么穿。'
    plan, task = await interpret_task(Model(), {'message': message}, SessionState(), message)
    assert plan.changes['preferences'].value == ['只要宽松版型，不查衣橱']
    assert task.preferences == ['只要宽松版型，不查衣橱']


@pytest.mark.parametrize('persona', get_args(PersonaId))
@pytest.mark.asyncio
async def test_explicit_daily_save_is_out_of_scope_without_false_receipt(tmp_path, persona):
    store = Store(str(tmp_path / 'scope.db'))
    reply = await Stylist(Settings(), store, ChatModel()).chat(User(), ChatRequest(
        message='记住我喜欢乌龙茶。', request_id='daily-save', assistant_persona=persona))
    assert '只记录穿搭' in reply.message
    assert not store.memory_book(await User().identity()).entries


@pytest.mark.asyncio
async def test_preference_sharing_cannot_trigger_inventory_even_with_bad_model_plan(tmp_path):
    store = Store(str(tmp_path / 'scope.db'))
    reply = await Stylist(Settings(), store, ChatModel()).chat(User(), ChatRequest(
        message='我喜欢穿短袖，衬衫，不喜欢黄色、绿色', request_id='share-only'))
    assert reply.conversation_only and reply.task == Task()
    assert not reply.looks
    assert store.memory_book(await User().identity()).entries[0].content == '我喜欢穿短袖，衬衫；不喜欢黄色、绿色'


@pytest.mark.asyncio
async def test_committed_receipt_removes_model_denial_and_matches_history(tmp_path):
    class ContradictoryModel:
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='consult', conversation_only=True, memory_save=MemorySave(
                    content='我喜欢棉质衬衫', authorization='这个一定要记住'))
            return Draft(message='我还不能确认保存成功，先不说记住了。棉质衬衫很耐看。')
    store = Store(str(tmp_path / 'scope.db'))
    request = ChatRequest(message='对了，我喜欢棉质衬衫，这个一定要记住。', request_id='scope-receipt')
    engine = Stylist(Settings(), store, ContradictoryModel())
    reply = await engine.chat(User(), request)
    assert '我们的手记' in reply.message and '不能确认' not in reply.message
    assert len(store.memory_book(await User().identity()).entries) == 1
    assert await engine.chat(User(), request) == reply
    assert store.history(await User().identity(), reply.conversation_id)['messages'][0]['reply']['message'] == reply.message


def test_legacy_notes_excluded_from_api_without_deleting_original_storage(tmp_path, monkeypatch):
    from stylist.main import create_app
    async def identity(self):
        return 'legacy-owner'
    monkeypatch.setattr('stylist.main.Upstream.identity', identity)
    path = str(tmp_path / 'scope.db')
    store = Store(path)
    old = MemoryBook(revision=3, entries=[
        MemoryEntry(id='daily', category='日常片段', content='我喜欢乌龙茶'),
        MemoryEntry(id='rule', category='相处约定', content='以后叫我亲爱的'),
        MemoryEntry(id='color', category='日常片段', content='我喜欢蓝色'),
    ])
    with store.connection() as conn:
        conn.execute('INSERT INTO stylist_memory_books(owner_id,revision,book_json) VALUES(?,?,?)',
                     ('legacy-owner', 3, old.model_dump_json()))
    with TestClient(create_app(Settings(database=path))) as client:
        headers = {'Authorization': 'Bearer synthetic'}
        response = client.get('/stylist-api/memories', headers=headers)
        assert response.json()['entries'] == [{'id': 'color', 'category': '穿衣习惯', 'content': '我喜欢蓝色'}]
        with store.connection() as conn:
            assert conn.execute('SELECT book_json FROM stylist_memory_books').fetchone()[0] == old.model_dump_json()
        invalid = {**response.json(), 'entries': [{'id': 'bad', 'category': '穿衣习惯', 'content': '我喜欢乌龙茶'}]}
        assert client.put('/stylist-api/memories', headers=headers, json=invalid).status_code == 422
        valid = client.put('/stylist-api/memories', headers=headers, json=response.json())
        assert valid.status_code == 200 and '_retired_entries' not in valid.json()
    with store.connection() as conn:
        raw = json.loads(conn.execute('SELECT book_json FROM stylist_memory_books').fetchone()[0])
    assert any(entry['id'] == 'daily' for entry in raw['_retired_entries'])
    assert store.memory_book('another-owner').entries == []


@pytest.mark.parametrize('gender,word', [('女', '女装'), ('男', '男装')])
@pytest.mark.asyncio
async def test_query_control_paraphrase_does_not_break_verified_target_gender(gender, word):
    class Model:
        async def generate(self, name, payload, result_type):
            return Plan(mode='consult', use_inventory=False, use_profile_gender=False, changes={
                'gender': Change(value=gender, evidence=word),
                'preferences': Change(value=['只讲穿法'], evidence='只讲穿法'),
            })
    from stylist.models import SessionState
    plan, task = await interpret_task(Model(), {}, SessionState(), f'这次只讲{word}白衬衫灰裤的穿法，不查衣橱和天气。')
    assert task.gender == gender and not plan.changes.get('preferences')


@pytest.mark.parametrize('persona', get_args(PersonaId))
def test_upload_invitation_does_not_mislabel_shoes_bags_or_jewelry(persona):
    assert '衣服' not in upload_invitation(persona)


def test_attribute_rewrite_keeps_garment_labels_and_complete_sentences():
    from stylist.grounding import attribute_claim_problems, ground_attribute_fallback, normalize_draft
    original = Draft(message='这双鞋不会湿。', looks=[LookDraft(title='蓝衬衫+灰裤+灰裤+平底鞋',
        pieces=['宽松针织上衣', '灰裤', '灰裤'], why=['配色清楚。'],
        how=['领口整理平整。', '整体保持“整齐但不紧绷”。'], notes=['这条裤子不会勒腰。'])])
    fixed = ground_attribute_fallback(normalize_draft(original), {}, 'male_calm_v1')
    assert fixed.looks[0].pieces == ['宽松针织上衣', '灰裤']
    assert fixed.looks[0].title == '蓝衬衫+灰裤+平底鞋'
    assert '领口整理平整。' in fixed.looks[0].how
    assert not any(line.endswith(('，', ',', '“')) for look in fixed.looks for line in [*look.how, *look.notes])
    assert not attribute_claim_problems(fixed, {})
