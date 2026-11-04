"""Explicit regeneration selects a different owned outfit without image writes."""
import hashlib
from datetime import date, datetime

import pytest

from scripts.dialogue_validation import PRODUCTS, DialogueUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.memory import MemoryBook, MemoryEntry
from stylist.models import (
    Change,
    ChatRequest,
    CitySelection,
    Draft,
    Look,
    LookDraft,
    Plan,
    Product,
    Reply,
    Task,
    TripStop,
)
from stylist.store import Store
from stylist.weather import today


def look(top, title):
    return Look(title=title, items=[Product(source='user', product_id=str(pid), slot=slot)
        for pid, slot in [(top, 'top'), (102, 'bottom'), (103, 'shoes')]])


async def setup(tmp_path, *, weekly=False, no_heels=True, event_date=None, weather_policy='auto', city=None,
                itinerary=None):
    class RegenerationUpstream(DialogueUpstream):
        async def call(self, name, args):
            if name == 'city.resolve' and args.get('name') == '北京市':
                self.calls.append(name)
                return {'status':'resolved','truncated':False,
                        'matches':[{'city_name':'北京市','province_name':'北京市'}]}
            return await super().call(name, args)
    upstream = RegenerationUpstream('regeneration')
    upstream.products = [*PRODUCTS, {**PRODUCTS[0], 'product_id': '202', 'title': '蓝色长袖衬衫', 'color': '蓝色'}]
    store = Store(str(tmp_path / 'regeneration.db'))
    owner = await upstream.identity()
    initial = ChatRequest(message='已生成的衣橱搭配', request_id='seed-regeneration')
    cid, claim, state, _ = store.reserve(owner, initial)
    state.task = Task(scene='通勤', gender='女', city=city, itinerary=itinerary or [],
        event_date=event_date or today(), weather_policy=weather_policy,
        no_heels=no_heels, excluded_colors=['黄色', '绿色'], excluded_materials=['羊毛'], preferences=['不塞衣角'])
    if weather_policy == 'provided':
        state.task.temp_min, state.task.temp_max, state.task.weather_description = 27, 32, '旧日自报炎热天气'
    state.mode = 'weekly' if weekly else 'recommend'
    state.looks = [look(202, '2026-11-02 第一套'), look(101, '2026-11-04 第二套')]
    store.finish(owner, initial, claim, state, Reply(conversation_id=cid, version=1,
        mode=state.mode, delivery='outfit', message='原搭配', task=state.task, looks=state.looks))
    return store, upstream, cid, state


def request(cid, **changes):
    return ChatRequest(message='重新生成穿搭', regenerate_outfit=True, conversation_id=cid,
        expected_version=1, request_id='regenerate-current-outfit', selected_look_index=1, **changes)


def draft(top=202, count=1):
    return Draft(message='沿用通勤与不塞衣角的要求，这次换一件衬衫。', looks=[LookDraft(
        title='新的通勤穿搭', selected_keys=[f'user:{top}', 'user:102', 'user:103'],
        why=['换用不同衬衫'], how=['衣角自然放下']) for _ in range(count)])


class Model:
    def __init__(self, results=None):
        self.payloads = []
        self.results = results or [draft()]

    async def generate(self, name, payload, result_type):
        assert name == 'style', 'The explicit action needs no free-form task interpretation'
        self.payloads.append(payload)
        return self.results[min(len(self.payloads) - 1, len(self.results) - 1)]


@pytest.mark.parametrize('persona', ['female_sweet_v1', 'female_warm_v1', 'female_regal_v1',
                                    'male_artistic_v1', 'male_calm_v1', 'male_confident_v1'])
async def test_regenerate_selected_outfit_preserves_conditions_and_replays_once(tmp_path, persona):
    store, upstream, cid, before = await setup(tmp_path)
    model = Model()
    engine = Stylist(Settings(), store, model)
    current = request(cid, assistant_persona=persona)
    result = await engine.chat(upstream, current)
    assert result.delivery == 'outfit' and len(result.looks) == 1
    assert result.task == before.task and result.mode == 'recommend'
    assert {p.key for p in result.looks[0].items} == {'user:202', 'user:102', 'user:103'}
    assert model.payloads[0]['regenerate_from']['selected_keys'] == ['user:101', 'user:102', 'user:103']
    assert model.payloads[0]['frozen_keys'] == []
    assert '/api/user_product/quick_edit_list' in upstream.calls
    assert not any('twin' in call or 'tryon' in call for call in upstream.calls)
    assert not result.avatar_intent and not result.upload_suggestion
    assert await engine.chat(upstream, current) == result
    assert len(model.payloads) == 1


@pytest.mark.parametrize('bad', ['repeat', 'multiple'])
async def test_repeated_or_multiple_outfits_are_repaired_before_delivery(tmp_path, bad):
    store, upstream, cid, _ = await setup(tmp_path)
    model = Model([draft(101) if bad == 'repeat' else draft(count=2), draft()])
    result = await Stylist(Settings(), store, model).chat(upstream, request(cid))
    assert result.looks[0].items[0].product_id == '202' and len(result.looks) == 1
    assert len(model.payloads) == 2
    assert any(p.startswith('outfit_regeneration:') for p in model.payloads[1]['validation_errors'])


async def test_failure_to_find_a_different_outfit_keeps_the_original_state(tmp_path):
    store, upstream, cid, before = await setup(tmp_path)
    with pytest.raises(StylistError, match='outfit_regeneration_unavailable'):
        await Stylist(Settings(), store, Model([draft(101)])).chat(upstream, request(cid))
    saved = store.history(await upstream.identity(), cid)
    assert saved['version'] == 1 and len(saved['messages']) == 1
    assert saved['messages'][0]['reply']['looks'] == [item.model_dump(mode='json') for item in before.looks]


async def test_weekly_source_regenerates_one_outfit_for_today(tmp_path):
    store, upstream, cid, _ = await setup(tmp_path, weekly=True)
    model = Model()
    result = await Stylist(Settings(), store, model).chat(upstream, request(cid))
    assert result.task.event_date == today()
    assert result.mode == 'recommend' and len(result.looks) == 1
    assert model.payloads[0]['planning_dates'] == []


async def test_a_new_outfit_can_regenerate_again_without_an_intermediate_tryon(tmp_path):
    store, upstream, cid, _ = await setup(tmp_path)
    first = await Stylist(Settings(), store, Model()).chat(upstream, request(cid))
    again = request(cid).model_copy(update={'request_id': 'regenerate-another-outfit',
                                          'expected_version': first.version, 'selected_look_index': 0})
    second = await Stylist(Settings(), store, Model([draft(101)])).chat(upstream, again)
    assert second.version == first.version + 1
    assert second.looks[0].items[0].product_id == '101'
    assert not any('twin' in call or 'tryon' in call for call in upstream.calls)


async def test_saved_memory_defaults_still_apply_without_overwriting_the_task(tmp_path):
    store, upstream, cid, before = await setup(tmp_path, no_heels=False)
    upstream.products.append({**PRODUCTS[2], 'product_id': '209', 'title': '黑色高跟鞋', 'color': '黑色'})
    store.save_memory_book(await upstream.identity(), MemoryBook(entries=[
        MemoryEntry(id='clothing', content='我不穿高跟鞋')]))
    class MemoryModel(Model):
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='consult', conversation_only=True, new_task=True,
                    memory_changes={'no_heels': Change(value=True, evidence='不穿高跟鞋')})
            assert payload['task']['no_heels'] is True
            assert 'user:209' not in {item['key'] for item in payload['candidates']}
            return await super().generate(name, payload, result_type)
    result = await Stylist(Settings(), store, MemoryModel()).chat(upstream, request(cid))
    assert result.task == before.task and not result.task.no_heels


@pytest.mark.parametrize('kind', ['stale', 'foreign', 'missing'])
async def test_invalid_context_never_calls_the_model(tmp_path, kind):
    store, upstream, cid, _ = await setup(tmp_path)
    req = request(cid)
    if kind == 'stale':
        req = req.model_copy(update={'expected_version': 2})
    elif kind == 'foreign':
        async def other():
            return 'another-owner'
        upstream.identity = other
    else:
        req = req.model_copy(update={'selected_look_index': 6})
    model = Model()
    with pytest.raises(StylistError):
        await Stylist(Settings(), store, model).chat(upstream, req)
    assert not model.payloads and not upstream.calls


def test_regeneration_requires_a_source_and_cannot_silently_ignore_new_user_constraints():
    with pytest.raises(ValueError):
        ChatRequest(message='重新生成穿搭', regenerate_outfit=True, request_id='missing-source')
    with pytest.raises(ValueError):
        ChatRequest(message='重新生成穿搭，不穿高跟鞋', regenerate_outfit=True,
            conversation_id='sty_' + '1' * 32, expected_version=1, request_id='extra-constraint')


async def test_ordinary_request_digest_remains_compatible_with_the_previous_schema(tmp_path):
    store, upstream, _, _ = await setup(tmp_path)
    original = ChatRequest(message='普通对话', request_id='legacy-schema-digest')
    store.reserve(await upstream.identity(), original)
    expected = hashlib.sha256(original.model_dump_json(exclude={
        'assistant_persona', 'companion_profile', 'upload_action_id', 'regenerate_outfit', 'regenerate_from_version', 'new_clothes', 'chat_image'}).encode()).hexdigest()
    with store.connection() as conn:
        digest = conn.execute('SELECT digest FROM stylist_requests WHERE request_id=?', (original.request_id,)).fetchone()[0]
    assert digest == expected


async def add_later_outfit(store, upstream, cid):
    owner = await upstream.identity()
    later = ChatRequest(message='改聊旅行搭配',request_id='later-outfit-turn',conversation_id=cid,expected_version=1)
    _, claim, state, _ = store.reserve(owner,later)
    state.task = Task(scene='旅行',city='三亚市',weather_policy='ignored')
    state.looks = [look(202,'后来的旅行搭配')]
    state.messages = [{'role':'user','content':'改聊旅行搭配'}]
    store.finish(owner,later,claim,state,Reply(conversation_id=cid,version=2,mode='recommend',
        delivery='outfit',message='后来的结果',task=state.task,looks=state.looks))


async def test_old_card_uses_its_own_task_and_index_and_appends_to_latest_history(tmp_path):
    from stylist.models import CitySelection
    store,upstream,cid,before=await setup(tmp_path)
    await add_later_outfit(store,upstream,cid)
    model=Model()
    old=request(cid).model_copy(update={'expected_version':2,'regenerate_from_version':1,
        'location':CitySelection(city_name='三亚市')})
    # Preserve the original task's city, even when the toolbar now shows another city.
    before.task.city='北京市'
    with store.connection() as conn:
        row=conn.execute('SELECT reply_json FROM stylist_messages WHERE conversation_id=? AND version=1',(cid,)).fetchone()
        saved=Reply.model_validate_json(row['reply_json'] if isinstance(row,dict) else row[0])
        saved.task.city='北京市'
        conn.execute('UPDATE stylist_messages SET reply_json=? WHERE conversation_id=? AND version=1',(saved.model_dump_json(),cid))
    engine=Stylist(Settings(),store,model)
    result=await engine.chat(upstream,old)
    assert result.version==3 and result.task==before.task
    assert model.payloads[0]['regenerate_from']['title']=='2026-11-04 第二套'
    assert model.payloads[0]['task']['scene']=='通勤'
    assert model.payloads[0]['history']==[]  # Later unrelated requests cannot rewrite the source task.
    history=store.history(await upstream.identity(),cid)
    assert len(history['messages'])==3
    assert history['messages'][1]['reply']['looks'][0]['title']=='后来的旅行搭配'
    assert await engine.chat(upstream,old)==result and len(model.payloads)==1


async def test_same_request_id_cannot_switch_to_another_source_version(tmp_path):
    store,upstream,cid,_=await setup(tmp_path)
    await add_later_outfit(store,upstream,cid)
    old=request(cid).model_copy(update={'expected_version':2,'regenerate_from_version':1})
    engine=Stylist(Settings(),store,Model())
    await engine.chat(upstream,old)
    with pytest.raises(StylistError,match='idempotency_conflict'):
        await engine.chat(upstream,old.model_copy(update={'regenerate_from_version':2}))


@pytest.mark.parametrize('kind',['foreign','missing','stale_head','invalid_index'])
async def test_old_source_still_checks_ownership_existence_and_current_head(tmp_path,kind):
    store,upstream,cid,_=await setup(tmp_path)
    await add_later_outfit(store,upstream,cid)
    req=request(cid).model_copy(update={'expected_version':2,'regenerate_from_version':1})
    if kind=='foreign':
        async def identity():return 'another-owner'
        upstream.identity=identity
    elif kind=='missing':
        with store.connection() as conn:
            conn.execute('DELETE FROM stylist_messages WHERE conversation_id=? AND version=1',(cid,))
    elif kind=='stale_head':
        req=req.model_copy(update={'expected_version':1})
    else:
        req=req.model_copy(update={'selected_look_index':6})
    model=Model()
    with pytest.raises(StylistError):
        await Stylist(Settings(),store,model).chat(upstream,req)
    assert not model.payloads


def test_source_version_is_only_accepted_for_regeneration_and_cannot_be_in_the_future():
    with pytest.raises(ValueError):
        ChatRequest(message='普通对话',request_id='not-regeneration',regenerate_from_version=1,expected_version=1)
    with pytest.raises(ValueError):
        request('sty_'+'1'*32,regenerate_from_version=2)


@pytest.mark.parametrize('source_date,weather_policy,weekly,historical,route', [
    (date(2026, 10, 31), 'auto', False, False, False),
    (date(2026, 10, 31), 'auto', False, True, False),
    (date(2026, 11, 4), 'auto', True, True, False),
    (date(2026, 10, 31), 'provided', False, False, False),
    (date(2026, 10, 31), 'ignored', False, True, False),
    (date(2026, 10, 31), 'auto', True, True, True),
])
async def test_regeneration_fetches_shanghai_today_weather_without_reusing_source_date(
        tmp_path, monkeypatch, source_date, weather_policy, weekly, historical, route):
    # Beijing time has crossed midnight while UTC is still the previous date.
    instant = datetime.fromisoformat('2026-11-03T00:05:00+08:00')
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
    monkeypatch.setattr('stylist.engine.datetime', Clock)
    monkeypatch.setattr('stylist.weather.today', lambda: date(2026, 11, 3))
    stops = [TripStop(city_name='上海市', event_date=source_date),
             TripStop(city_name='北京市', event_date=source_date)] if route else []
    store, upstream, cid, original = await setup(tmp_path, weekly=weekly, event_date=source_date,
        weather_policy=weather_policy, city='北京市', itinerary=stops)
    if historical:
        await add_later_outfit(store, upstream, cid)

    async def forecast(city):
        upstream.calls.append('forecast')
        return {'list':[{'data_format':'2026-11-03','temp_day':17,'temp_night':3,
                         'condition_day':'晴','condition_night':'晴'}]}
    upstream.forecast = forecast

    class TodayModel(Model):
        async def generate(self, name, payload, result_type):
            assert payload['task']['event_date'] == '2026-11-03'
            assert payload['task']['temp_min'] is None and payload['task']['temp_max'] is None
            assert '旧日自报' not in payload['task']['weather_description']
            weather = payload['weather']
            forecasts = [stop['forecast'] for stop in weather['locations']] if route else [weather]
            assert all(f['days'][0]['temp_min'] == 3 and f['days'][0]['temp_max'] == 17 for f in forecasts)
            if not route:
                assert payload['layering_requirements'][0]['temp_min'] == 3
            result = await super().generate(name, payload, result_type)
            result.looks[0].selected_keys.append('user:105')
            return result
    model = TodayModel()
    engine = Stylist(Settings(), store, model)
    req = request(cid, location=CitySelection(city_name='上海市'))
    if historical:
        req = req.model_copy(update={'expected_version':2,'regenerate_from_version':1})
    reply = await engine.chat(upstream, req)
    assert reply.task.event_date == date(2026, 11, 3) and reply.task.weather_policy == 'auto'
    assert reply.task.city == original.task.city and reply.task.scene == original.task.scene
    assert reply.task.no_heels and reply.task.preferences == ['不塞衣角']
    assert reply.task.excluded_colors == ['黄色', '绿色'] and reply.task.excluded_materials == ['羊毛']
    forecasts = [stop['forecast'] for stop in reply.weather['locations']] if route else [reply.weather]
    assert all(f['requested_dates'] == ['2026-11-03'] and f['scope'] == 'day' for f in forecasts)
    assert any(p.slot == 'outer' for p in reply.looks[0].items)
    assert not any('天气暂时没查到' in warning for warning in reply.warnings)
    history = store.history(await upstream.identity(), cid)
    assert history['messages'][0]['reply']['task']['event_date'] == source_date.isoformat()
    calls = list(upstream.calls)
    assert await engine.chat(upstream, req) == reply
    assert upstream.calls == calls and len(model.payloads) == 1


async def test_explicit_past_date_reports_date_problem_without_current_weather_fallback(tmp_path):
    from datetime import timedelta
    past = today() - timedelta(days=2)
    class PastModel(Model):
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='recommend', weather_scope='day', changes={
                    'city':Change(value='北京市', evidence='北京'),
                    'event_date':Change(value=past.isoformat(), evidence=past.isoformat())})
            return await super().generate(name, payload, result_type)
    store, upstream, _, _ = await setup(tmp_path)
    reply = await Stylist(Settings(), store, PastModel()).chat(upstream, ChatRequest(
        message=f'按{past.isoformat()}北京的天气搭一套', request_id='explicit-past-date-outfit'))
    assert reply.weather is None and reply.task.event_date == past
    assert any('过去日期' in warning for warning in reply.warnings)
    assert 'forecast' not in upstream.calls and 'weather.get' not in upstream.calls
