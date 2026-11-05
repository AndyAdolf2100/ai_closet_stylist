import pytest
from fastapi.testclient import TestClient

from stylist.config import Settings
from stylist.errors import StylistError
from stylist.feedback import OutfitFeedback, read_feedback, save_feedback, style_evidence
from stylist.main import create_app
from stylist.models import Look, Reply, SessionState, Task
from stylist.store import Store

CID = 'sty_' + 'a' * 32


def seed(store, version=1, style='简约休闲', target='', gender='女', delivery='outfit'):
    reply = Reply(conversation_id=CID, version=version, mode='recommend', delivery=delivery,
                  message='模拟搭配', task=Task(gender=gender, target_description=target),
                  looks=[Look(title='模拟搭配', style_name=style)])
    with store.connection() as conn:
        conn.execute('INSERT INTO stylist_sessions(id,owner_id,state_json) VALUES(?,?,?) ON CONFLICT(id) DO NOTHING',
                     (CID, '1', SessionState().model_dump_json()))
        conn.execute('INSERT INTO stylist_messages(conversation_id,owner_id,version,user_message,reply_json) VALUES(?,?,?,?,?)',
                     (CID, '1', version, '帮我搭配', reply.model_dump_json()))


@pytest.fixture
def store(tmp_path):
    value = Store(str(tmp_path / 'feedback.db'))
    seed(value)
    return value


def vote(store, value='like', version=1):
    return save_feedback(store, '1', CID, OutfitFeedback(version=version, look_index=0, vote=value))


def test_repeated_votes_correction_withdrawal_and_reload(store):
    vote(store)
    vote(store)
    assert style_evidence(store, '1', Task(gender='女'))[0]['weight'] == .1
    assert read_feedback(Store(store.path), '1', CID, 1, 0) == {'vote': 'like'}
    vote(store, 'dislike')
    assert style_evidence(store, '1', Task(gender='女')) == []
    vote(store, None)
    assert read_feedback(store, '1', CID, 1, 0) == {'vote': None}


def test_repeated_independent_versions_capped_and_isolated(store):
    vote(store)
    for version in range(2, 6):
        seed(store, version)
        vote(store, version=version)
    evidence = style_evidence(store, '1', Task(gender='女'))
    assert evidence == [{'style_name': '简约休闲', 'positive_versions': 3, 'weight': .3}]
    assert style_evidence(store, '2', Task(gender='女')) == []
    assert style_evidence(store, '1', Task(gender='男')) == []
    assert style_evidence(store, '1', Task(gender='女', target_description='朋友')) == []
    with pytest.raises(StylistError, match='feedback_not_found'):
        save_feedback(store, '2', CID, OutfitFeedback(version=1, look_index=0, vote='like'))
    with pytest.raises(StylistError):
        read_feedback(store, '1', CID, 1, 6)


def test_pause_empty_style_and_other_person_do_not_infer(store):
    vote(store)
    book = store.memory_book('1')
    book.enabled = False
    store.save_memory_book('1', book)
    assert not style_evidence(store, '1', Task(gender='女'))
    book = store.memory_book('1')
    book.enabled = True
    store.save_memory_book('1', book)
    vote(store, None)
    seed(store, 2, style='')
    vote(store, version=2)
    seed(store, 3, target='朋友')
    vote(store, version=3)
    assert not style_evidence(store, '1', Task(gender='女'))
    seed(store, 4, delivery='clarification')
    with pytest.raises(StylistError, match='feedback_not_available'):
        vote(store, version=4)


def test_authenticated_api_and_validation(store, monkeypatch):
    async def identity(self):
        return '2' if self.authorization.endswith('other') else '1'
    monkeypatch.setattr('stylist.main.Upstream.identity', identity)
    app = create_app(Settings(database=store.path))
    with TestClient(app) as client:
        url = f'/stylist-api/conversations/{CID}/feedback'
        body = {'version': 1, 'look_index': 0, 'vote': 'like'}
        assert client.put(url, json=body).status_code == 401
        assert client.put(url, json=body, headers={'Authorization': 'Bearer other'}).status_code == 404
        headers = {'Authorization': 'Bearer mock'}
        saved = client.put(url, json=body, headers=headers).json()
        assert saved['vote'] == 'like'
        assert saved['message']
        assert client.get(url, params={'version':1,'look_index':0}, headers=headers).json() == {'vote':'like'}
        assert client.put(url, json={**body,'vote':'five'}, headers=headers).status_code == 422


@pytest.mark.asyncio
async def test_agent_receives_soft_evidence_without_changing_task(store):
    from stylist.engine import Stylist
    from stylist.models import ChatRequest, Draft, Plan

    vote(store)

    class Upstream:
        async def identity(self):
            return '1'

    class Model:
        def __init__(self):
            self.payload = None
            self.ignore = False

        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='consult', use_inventory=False, use_profile_preferences=not self.ignore)
            self.payload = payload
            return Draft(message='按你的要求聊聊穿搭。')

    model = Model()
    engine = Stylist(Settings(), store, model)
    for ignore in [False, True]:
        model.ignore = ignore
        reply = await engine.chat(Upstream(), ChatRequest(message='只讲文字穿搭，不查衣橱，不考虑天气',
                                  request_id=f'feedback-agent-{ignore}',
                                  companion_profile={'user_gender':'女'}))
        if ignore:
            assert model.payload['outfit_feedback_styles'] == []
        else:
            assert model.payload['outfit_feedback_styles'][0]['style_name'] == '简约休闲'
        assert reply.task.style == ''


@pytest.mark.parametrize('persona', ['male_calm_v1', 'male_artistic_v1', 'male_confident_v1',
                                    'female_warm_v1', 'female_sweet_v1', 'female_regal_v1'])
def test_persona_receipts_only_claim_actual_reference(store, persona):
    request = OutfitFeedback(version=1, look_index=0, vote='like', assistant_persona=persona)
    result = save_feedback(store, '1', CID, request)
    assert '下次' in result['message']
    assert not any(word in result['message'] for word in ['永久', '训练', '手记'])
    book = store.memory_book('1')
    book.enabled = False
    store.save_memory_book('1', book)
    assert '下次' not in save_feedback(store, '1', CID, request)['message']
    result = save_feedback(store, '1', CID, request.model_copy(update={'vote': 'dislike'}))
    assert '下次' not in result['message']
    result = save_feedback(store, '1', CID, request.model_copy(update={'vote': None}))
    assert '撤回' in result['message']
    assert not style_evidence(store, '1', Task(gender='女'))
