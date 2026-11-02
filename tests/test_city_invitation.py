"""City CTA decisions use resolved intent; these tests do not claim live NLU coverage."""
from typing import get_args

import pytest

from scripts.dialogue_validation import DialogueUpstream
from stylist.config import Settings
from stylist.engine import Stylist, needs_outfit_city
from stylist.models import Change, ChatRequest, CitySelection, Draft, LookDraft, Plan, Task
from stylist.personas import PersonaId
from stylist.store import Store


@pytest.mark.parametrize('plan,task,expected', [
    (Plan(mode='recommend'), Task(), True),
    (Plan(mode='weekly'), Task(), True),
    (Plan(mode='modify'), Task(), True),
    (Plan(mode='consult', weather_scope='day'), Task(), True),
    (Plan(mode='consult', weather_scope='none'), Task(), False),
    (Plan(mode='recommend'), Task(city='杭州市'), False),
    (Plan(mode='recommend'), Task(itinerary=[{'city_name':'上海市'}, {'city_name':'杭州市'}]), False),
    (Plan(mode='recommend'), Task(weather_policy='ignored'), False),
    (Plan(mode='recommend'), Task(weather_policy='provided', temp_min=15, temp_max=20), True),
    (Plan(mode='consult', conversation_only=True), Task(), False),
    (Plan(mode='consult', weather_only=True, weather_scope='day'), Task(), False),
    (Plan(mode='consult', technical_question=True, weather_scope='day'), Task(), False),
    (Plan(mode='consult', upload_intent='garment', weather_scope='day'), Task(), False),
    (Plan(mode='consult', avatar_intent='upload', weather_scope='day'), Task(), False),
])
def test_city_prompt_decision(plan, task, expected):
    assert needs_outfit_city(plan, task) is expected


class OutfitModel:
    async def generate(self, name, payload, result_type):
        if name == 'plan':
            text = payload['message']
            changes = {}
            if '上海' in text:
                changes['city'] = Change(value='上海市', evidence='上海')
            if '不考虑天气' in text:
                changes['weather_policy'] = Change(value='ignored', evidence='不考虑天气')
            return Plan(mode='recommend', use_inventory=True, weather_scope='day', changes=changes)
        return Draft(message='从衣橱选择日常搭配。', looks=[LookDraft(title='日常穿搭',
            selected_keys=['user:101', 'user:102', 'user:103'], why=['配色简洁'], how=['自然垂放'])])


@pytest.mark.parametrize('persona', get_args(PersonaId))
@pytest.mark.parametrize('message,location,expected', [
    ('我需要一套穿搭', None, True),
    ('上海通勤，帮我搭一套', None, False),
    ('我需要一套穿搭，不考虑天气', None, False),
    ('我需要一套穿搭', CitySelection(city_name='上海市', province_name='上海市'), False),
])
@pytest.mark.asyncio
async def test_reply_exposes_city_card_for_resolved_outfit_intent(tmp_path, persona, message, location, expected):
    engine = Stylist(Settings(), Store(str(tmp_path / 'state.db')), OutfitModel())
    upstream = DialogueUpstream('city_invitation')
    reply = await engine.chat(upstream, ChatRequest(message=message, location=location,
        request_id='city-invitation-001', assistant_persona=persona))
    assert reply.city_selection_required is expected
    assert not reply.pending_confirmation
    assert reply.looks and '/api/user_product/quick_edit_list' in upstream.calls
    assert ('forecast' in upstream.calls) is (location is not None or '上海' in message)
    assert not any('tryon' in call for call in upstream.calls)


@pytest.mark.asyncio
async def test_missing_city_followed_by_explicit_city_and_inherited_city(tmp_path):
    engine = Stylist(Settings(), Store(str(tmp_path / 'state.db')), OutfitModel())
    upstream = DialogueUpstream('city_invitation')
    first = await engine.chat(upstream, ChatRequest(message='我需要一套穿搭', request_id='city-first'))
    assert first.city_selection_required
    second = await engine.chat(upstream, ChatRequest(message='在上海穿，继续刚才的搭配',
        request_id='city-second', conversation_id=first.conversation_id, expected_version=first.version))
    assert not second.city_selection_required and second.weather['city_name'] == '上海市'
    third = await engine.chat(upstream, ChatRequest(message='再来一套穿搭', request_id='city-third',
        conversation_id=second.conversation_id, expected_version=second.version))
    assert not third.city_selection_required and third.task.city == '上海市'


@pytest.mark.asyncio
async def test_weather_opt_out_is_not_sticky_and_destination_wins_over_page_city(tmp_path):
    engine = Stylist(Settings(), Store(str(tmp_path / 'state.db')), OutfitModel())
    upstream = DialogueUpstream('city_invitation')
    first = await engine.chat(upstream, ChatRequest(message='搭一套，不考虑天气', request_id='city-ignore'))
    assert not first.city_selection_required and 'forecast' not in upstream.calls
    second = await engine.chat(upstream, ChatRequest(message='这次考虑天气，再搭一套', request_id='city-restore',
        conversation_id=first.conversation_id, expected_version=first.version))
    assert second.city_selection_required and second.task.weather_policy == 'auto'
    third = await engine.chat(upstream, ChatRequest(message='上海通勤搭一套', request_id='city-override',
        location=CitySelection(city_name='三亚市', province_name='海南省'),
        conversation_id=second.conversation_id, expected_version=second.version))
    assert not third.city_selection_required and third.weather['city_name'] == '上海市'
