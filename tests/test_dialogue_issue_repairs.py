"""Regression evidence for natural-dialogue failures, using synthetic services."""
from contextlib import asynccontextmanager

import pytest

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.memory import apply_memory, automatic_preference
from stylist.models import Change, ChatRequest, Draft, Plan, SessionState, Task
from stylist.policy import interpret_task
from stylist.preferences import wardrobe_allowed
from stylist.store import Store


class Model:
    def __init__(self, plan):
        self.plan = plan
        self.calls = []

    async def generate(self, name, payload, result_type):
        self.calls.append(name)
        return self.plan.model_copy(deep=True) if name == 'plan' else Draft(message='白衬衫下摆自然放下，配灰裤和白色平底鞋。')


@pytest.mark.parametrize('message', ['先别翻衣橱，也不用看天气。', '还是别找商品，只讲穿法。', '不用查天气和衣橱，只讲文字。'])
@pytest.mark.asyncio
async def test_model_cannot_override_inventory_opt_out(tmp_path, message):
    class Upstream:
        async def identity(self):
            return 'synthetic-boundary'

        @asynccontextmanager
        async def mcp(self):
            yield self

        async def call(self, *args):
            pytest.fail('Explicit opt-out must prevent all inventory reads')

        async def get(self, *args):
            pytest.fail('Explicit opt-out must prevent HTTP inventory reads')

    model = Model(Plan(mode='recommend', use_inventory=True, weather_scope='none'))
    reply = await Stylist(Settings(), Store(str(tmp_path / 'state.db')), model).chat(
        Upstream(), ChatRequest(message=message, request_id='synthetic-opt-out'))
    assert reply.delivery == 'advice' and not reply.looks
    assert 'style' in model.calls


def test_inventory_opt_out_survives_detour_until_explicit_reenable():
    history = [{'role': 'user', 'content': '先别翻衣橱，只说穿法。'},
               {'role': 'user', 'content': '开会开得好累。'}]
    assert not wardrobe_allowed('说回刚才那三件吧', history)
    assert wardrobe_allowed('现在从衣橱选一套', history)


@pytest.mark.asyncio
async def test_profile_default_does_not_break_current_requirement_evidence():
    model = Model(Plan(mode='recommend', changes={
        'preferences': Change(value=['方便走动'], evidence='方便走动'),
        'no_heels': Change(value=True, evidence='不穿高跟鞋')}))
    plan, task = await interpret_task(model, {'companion_profile': {'dressing_priorities': ['方便走动']}},
                                      SessionState(), '给我搭一套，不穿高跟鞋')
    assert task.no_heels and not task.preferences and model.calls == ['plan']
    assert 'preferences' not in plan.changes


@pytest.mark.asyncio
async def test_saved_memory_uses_its_own_evidence_channel():
    notes = [{'content': '我不喜欢黄色', 'category': '穿衣习惯'}]
    model = Model(Plan(mode='recommend', changes={
        'excluded_colors': Change(value=['黄色'], evidence='不喜欢黄色')}))
    plan, task = await interpret_task(model, {'long_term_memory': notes}, SessionState(), '按刚才的喜好搭一套')
    assert not task.excluded_colors
    assert apply_memory(task, plan, notes).excluded_colors == ['黄色']
    assert not apply_memory(task, plan.model_copy(update={'use_profile_preferences': False}), notes).excluded_colors


@pytest.mark.asyncio
async def test_other_target_change_survives_stale_weather_evidence():
    model = Model(Plan(mode='consult', new_task=True, use_profile_preferences=False, changes={
        'gender': Change(value='男', evidence='我哥'),
        'preferences': Change(value=['不喜欢紧身'], evidence='他不喜欢紧身'),
        'weather_policy': Change(value='ignored', evidence='旧轮不查天气')}))
    _, task = await interpret_task(model, {}, SessionState(), '换成帮我哥想想，他不喜欢紧身')
    assert task.gender == '男' and task.preferences == ['不喜欢紧身'] and task.weather_policy == 'auto'


@pytest.mark.asyncio
async def test_unknown_constraints_still_fail_closed():
    model = Model(Plan(mode='recommend', changes={'no_heels': Change(value=False, evidence='编造的取消要求')}))
    with pytest.raises(StylistError, match='invalid_requirements'):
        await interpret_task(model, {}, SessionState(task=Task(no_heels=True)), '其他不变')


@pytest.mark.asyncio
async def test_generic_weather_question_does_not_reassert_old_city():
    model = Model(Plan(mode='consult', weather_only=True, changes={'city': Change(value='奥克兰', evidence='今天会下雨吗')}))
    plan, _ = await interpret_task(model, {'selected_location': {'city_name': '上海市'},
        'current_task': {'city': '奥克兰'}}, SessionState(task=Task(city='奥克兰')), '今天会下雨吗')
    assert 'city' not in plan.changes
    model.plan.changes['city'] = Change(value='奥克兰', evidence='奥克兰')
    plan, task = await interpret_task(model, {'selected_location': {'city_name': '上海市'},
        'current_task': {'city': '奥克兰'}}, SessionState(), '奥克兰今天下雨吗')
    assert task.city == '奥克兰' and 'city' in plan.changes


def test_natural_long_term_color_preference_and_refusal_boundaries():
    assert automatic_preference('以后搭衣服尽量别选黄色，我真不喜欢。').content == '以后搭衣服尽量别选黄色'
    for message in ['以后搭衣服尽量别选黄色，我真不喜欢。别保存。',
                    '今天搭衣服尽量别选黄色，我真不喜欢。',
                    '以后搭衣服尽量别选黄色，他真不喜欢。',
                    '假如以后搭衣服尽量别选黄色，我真不喜欢。']:
        assert automatic_preference(message) is None


@pytest.mark.asyncio
async def test_profile_defaults_with_mixed_current_and_profile_citations():
    model = Model(Plan(mode='recommend', changes={'preferences': Change(
        value=['休闲', '容易打理'], evidence=['适合自己的日常搭配', '休闲'])}))
    _, task = await interpret_task(model, {'companion_profile': {
        'style_preferences': ['休闲'], 'dressing_priorities': ['容易打理']}},
        SessionState(), '给我一套适合自己的日常搭配')
    assert not task.preferences


@pytest.mark.asyncio
async def test_verified_weather_correction_wins_over_conflicting_chat_flag():
    model = Model(Plan(mode='consult', conversation_only=True, weather_only=True,
                       changes={'city': Change(value='奥克兰', evidence='新西兰的奥克兰')}))
    plan, task = await interpret_task(model, {}, SessionState(), '我指的是新西兰的奥克兰')
    assert plan.weather_only and not plan.conversation_only and task.city == '奥克兰'


def test_save_claim_cleanup_does_not_leave_a_noun_fragment():
    from stylist.memory import strip_save_claims
    assert strip_save_claims('好，我也记下你朋友的口味了。') in {'好。', ''}
    assert strip_save_claims('我记下了：你不穿高跟鞋。') == '你不穿高跟鞋。'


@pytest.mark.asyncio
async def test_distributive_outfit_count_does_not_reject_two_city_looks():
    model = Model(Plan(mode='recommend', requested_look_count=2, look_count_evidence='各搭一套', changes={
        'itinerary': Change(value=[{'city_name': '上海'}, {'city_name': '三亚'}], evidence='上海和三亚')}))
    plan, _ = await interpret_task(model, {}, SessionState(), '上海和三亚各搭一套，按两个地方的天气来。')
    assert plan.requested_look_count == 2


def test_three_piece_limit_checks_hidden_instructions_and_keeps_safe_look():
    from stylist.advice_boundaries import boundary_fallback, boundary_problems
    from stylist.models import LookDraft
    task = Task(owned_descriptions=['白衬衫', '灰裤', '白平底鞋'], preferences=['不塞衣角'])
    safe = LookDraft(title='自然垂放', pieces=['白衬衫', '灰裤', '白平底鞋'], why=['配色清楚。'], how=['衬衫不塞进裤腰。'])
    extra = safe.model_copy(update={'how': ['里面配一件贴身打底。'], 'notes': ['内搭是额外一件，可以选第一种。']})
    tuck = safe.model_copy(update={'how': ['下摆太长可以半塞一侧。']})
    message = '就说说这三件怎么穿'
    original = Draft(message='两种都只用三件。', looks=[safe, extra, tuck])
    assert len(boundary_problems(original, message, task)) == 2
    fixed = boundary_fallback(original, message, task)
    assert fixed.looks == [safe] and not boundary_problems(fixed, message, task)
    assert not boundary_problems(original, '现在可以加一件内搭了', task)


def test_hypothesis_check_preserves_conditional_answer():
    from stylist.advice_boundaries import boundary_problems
    message = '假如我喜欢短袖，不喜欢黄色。'
    assert boundary_problems(Draft(message='短袖是你的偏好。'), message, Task())
    assert not boundary_problems(Draft(message='如果按这个假设，短袖可以配灰裤。'), message, Task())
    assert not boundary_problems(Draft(message='短袖是你的偏好。'), '我喜欢短袖。', Task())


@pytest.mark.asyncio
async def test_repeated_bad_advice_returns_safe_reference_instead_of_interrupting(tmp_path):
    from stylist.models import LookDraft
    class Upstream:
        async def identity(self):
            return 'synthetic-advice'
    class BadModel(Model):
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='consult', use_inventory=False, changes={
                    'owned_descriptions': Change(value=['白衬衫', '灰裤', '白鞋'], evidence='白衬衫灰裤白鞋')})
            return Draft(message='给你两种。', looks=[
                LookDraft(title='垂放', pieces=['白衬衫', '灰裤', '白鞋'], why=['配色清楚。'], how=['下摆自然放下。']),
                LookDraft(title='叠穿', pieces=['白衬衫', '灰裤', '白鞋'], why=['配色清楚。'], how=['里面穿一件打底。'])])
    reply = await Stylist(Settings(), Store(str(tmp_path/'safe.db')), BadModel(None)).chat(Upstream(),
        ChatRequest(message='不查衣橱，只讲白衬衫灰裤白鞋这三件怎么穿', request_id='bounded-advice'))
    assert len(reply.looks) == 1 and reply.looks[0].title == '垂放'
    assert reply.delivery == 'advice'


def test_unsupported_walking_and_care_claims_require_evidence():
    from stylist.grounding import attribute_claim_problems, ground_attribute_fallback
    for text in ['白运动鞋走路省心。', '走沙滩和逛街区都更省心。', '棉质衣物打理起来省心。']:
        draft = Draft(message=text)
        assert attribute_claim_problems(draft, {})
        assert not attribute_claim_problems(ground_attribute_fallback(draft, {}, 'male_calm_v1'), {})
    assert not attribute_claim_problems(Draft(message='不能保证这双鞋走路省心，先试穿确认。'), {})


@pytest.mark.parametrize('text', ['对，你之前说过喜欢短袖和衬衫。', '这就是你喜欢的颜色。', '短袖是你的舒适区。', '衬衫是你的主场。'])
def test_hypothesis_cannot_be_answered_as_a_confirmed_historical_preference(text):
    from stylist.advice_boundaries import boundary_problems
    assert boundary_problems(Draft(message=text), '假如我喜欢短袖和衬衫。', Task())


def test_easy_care_synonym_is_not_supported_by_material_alone():
    from stylist.grounding import attribute_claim_problems
    assert attribute_claim_problems(Draft(message='这三件都是棉质，整体清爽好打理。'), {})
    assert not attribute_claim_problems(Draft(message='你希望好打理，具体护理要求还要看洗标。'), {})


@pytest.mark.asyncio
async def test_receipt_cleanup_cannot_remove_the_hypothetical_premise(tmp_path):
    class Upstream:
        async def identity(self):
            return 'synthetic-hypothesis'
    class HypotheticalModel(Model):
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='consult', conversation_only=True, use_inventory=False)
            return Draft(message='对，你刚才说的是“假如喜欢”——所以这次只当假设记着，不保存。短袖可以多留位置。')
    store = Store(str(tmp_path/'hypothesis.db'))
    reply = await Stylist(Settings(), store, HypotheticalModel(None)).chat(Upstream(),
        ChatRequest(message='假如我喜欢短袖。', request_id='hypothesis-cleanup'))
    assert '假设' in reply.message and not store.memory_book('synthetic-hypothesis').entries
