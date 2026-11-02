from datetime import date

import pytest

from stylist.layering import layering_problems, layering_requirements
from stylist.models import Draft, LookDraft, Plan, Product, Slot, Task


def fixture(outer=True):
    pool = {'user:1': Product(source='user', product_id='1', slot=Slot.TOP, title='白色短袖T恤')}
    if outer:
        pool['user:2'] = Product(source='user', product_id='2', slot=Slot.OUTER, title='长袖外套', color='黑色')
    draft = Draft(message='今天这样穿', looks=[LookDraft(title='短袖搭配', selected_keys=['user:1'],
        why=['保留上传的短袖'], how=['早晚加一件外套'])])
    return pool, draft


@pytest.mark.parametrize('low,high', [(3,17),(10,14),(12,22)])
def test_cold_outfit_needs_real_outer_not_just_a_reminder(low, high):
    pool, draft = fixture()
    task = Task(city='北京市',temp_min=low,temp_max=high)
    assert layering_problems(draft,pool,task,Plan(mode='recommend'),None)
    draft.looks[0].selected_keys.append('user:2')
    assert not layering_problems(draft,pool,task,Plan(mode='recommend'),None)


def test_missing_eligible_outer_requires_text_reference_and_keeps_real_items():
    pool, draft = fixture(False)
    task = Task(temp_min=3,temp_max=17)
    assert layering_problems(draft,pool,task,Plan(mode='recommend'),None)
    draft.looks[0].reference_pieces=['保暖外套（本次候选未匹配）']
    assert not layering_problems(draft,pool,task,Plan(mode='recommend'),None)
    assert draft.looks[0].selected_keys == ['user:1']


@pytest.mark.parametrize('task,plan', [
    (Task(temp_min=3,temp_max=17,weather_policy='ignored'),Plan(mode='recommend')),
    (Task(temp_min=3,temp_max=17,excluded_categories=['外套']),Plan(mode='recommend')),
    (Task(temp_min=3,temp_max=17,scene='全天室内，不出门'),Plan(mode='recommend')),
    (Task(temp_min=3,temp_max=17),Plan(mode='modify',replace_slots=[Slot.SHOES])),
    (Task(temp_min=3,temp_max=17),Plan(mode='consult')),
    (Task(temp_min=22,temp_max=30),Plan(mode='recommend')),
    (Task(),Plan(mode='recommend')),
])
def test_weather_never_overrides_explicit_boundaries_or_invents_temperatures(task,plan):
    assert not layering_requirements(task,plan,None)


def test_forbidden_outer_is_not_a_valid_weather_candidate():
    pool,draft=fixture()
    task=Task(temp_min=3,temp_max=17,excluded_colors=['黑色'])
    problems=layering_problems(draft,pool,task,Plan(mode='recommend'),None)
    assert 'reference_pieces' in problems[0]


def test_weekly_only_cold_dates_need_outer():
    pool,draft=fixture()
    draft.looks.append(draft.looks[0].model_copy(deep=True))
    days=[{'date':'2026-11-02','temp_min':3,'temp_max':17},
          {'date':'2026-11-03','temp_min':23,'temp_max':29}]
    task=Task(event_date=date(2026,11,2),temp_min=3,temp_max=29)
    problems=layering_problems(draft,pool,task,Plan(mode='weekly'),{'days':days},[d['date'] for d in days])
    assert len(problems)==1 and '第1套' in problems[0]
