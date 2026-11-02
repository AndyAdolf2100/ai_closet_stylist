"""Mock extraction verifies routing, persistence and zero-write boundaries, not live NLU."""
import pytest

from scripts.dialogue_validation import DialogueUpstream
from scripts.upload_intent_dialogues import EXPECTATIONS, SCENARIOS
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import ChatRequest, CompanionProfile, Draft, Look, Plan, Reply, SessionState, Task
from stylist.store import Store


@pytest.mark.parametrize("persona", ["female_warm_v1", "male_calm_v1"])
@pytest.mark.parametrize("message", [row[1] for row in SCENARIOS["upload_words"]])
async def test_clothing_addition_invites_without_tools_or_overwriting_task(tmp_path, persona, message):
    store = Store(str(tmp_path / 'upload-intent.db'))
    upstream = DialogueUpstream('upload-intent')
    owner = await upstream.identity()
    initial = ChatRequest(message='原通勤搭配', request_id='initial-state')
    cid, claim, state, _ = store.reserve(owner, initial)
    state.task = Task(scene='通勤', excluded_colors=['黄色'], weather_policy='ignored')
    state.looks = [Look(title='原来的搭配', pieces=['白衬衫'])]
    prior_task, prior_looks = state.task.model_copy(deep=True), list(state.looks)
    previous = Reply(conversation_id=cid, version=1, mode='consult', delivery='advice', message='原搭配', task=state.task)
    store.finish(owner, initial, claim, state, previous)
    class Model:
        calls = []
        async def generate(self, name, payload, result_type):
            self.calls.append(name)
            assert name == 'plan'
            return Plan(mode='recommend', upload_intent='garment', upload_evidence=message)
    model = Model()
    request = ChatRequest(message=message, request_id='invite-001', conversation_id=cid, expected_version=1,
                          assistant_persona=persona, confirm_plan=True)
    reply = await Stylist(Settings(), store, model).chat(upstream, request)
    assert reply.upload_intent == 'garment' and reply.upload_suggestion
    assert '？' in reply.message and '衣橱' in reply.message
    assert not reply.looks and not reply.weather and not reply.pending_confirmation
    assert reply.conversation_only and not upstream.calls
    assert model.calls == ['plan']
    with store.connection() as conn:
        saved = SessionState.model_validate_json(conn.execute('SELECT state_json FROM stylist_sessions WHERE id=?', (cid,)).fetchone()[0])
    assert saved.task == prior_task and saved.looks == prior_looks
    replay = await Stylist(Settings(), store, model).chat(upstream, request)
    assert replay == reply and model.calls == ['plan']


@pytest.mark.parametrize('intent,evidence,expected', [('unspecified','我想上传照片','unspecified'),
                                                     ('garment','不是本轮原话',None)])
async def test_photo_purpose_and_missing_original_evidence(tmp_path, intent, evidence, expected):
    class Model:
        async def generate(self, name, payload, result_type):
            return (Plan(mode='consult', conversation_only=True, upload_intent=intent, upload_evidence=evidence)
                    if name == 'plan' else Draft(message='先聊聊。'))
    upstream = DialogueUpstream('upload-intent')
    reply = await Stylist(Settings(), Store(str(tmp_path/'state.db')), Model()).chat(upstream,
        ChatRequest(message='我想上传照片', request_id='photo-purpose'))
    assert reply.upload_intent == expected and not reply.upload_suggestion and not upstream.calls


@pytest.mark.parametrize('message', [row[1] for row in SCENARIOS['upload_boundaries']])
async def test_model_excluded_intents_do_not_receive_clothing_card(tmp_path, message):
    class Model:
        async def generate(self, name, payload, result_type):
            return Plan(mode='consult', conversation_only=True) if name == 'plan' else Draft(message='好的。')
    reply = await Stylist(Settings(), Store(str(tmp_path/'boundary.db')), Model()).chat(
        DialogueUpstream('upload-intent'), ChatRequest(message=message, request_id='boundary'))
    assert reply.upload_intent is None and not reply.upload_suggestion


@pytest.mark.parametrize('detail', ['简洁重点','适中'])
async def test_invitation_respects_response_detail(tmp_path, detail):
    class Model:
        async def generate(self, *args):
            return Plan(mode='consult', upload_intent='garment', upload_evidence='添加衣服')
    reply = await Stylist(Settings(), Store(str(tmp_path/'detail.db')), Model()).chat(DialogueUpstream('upload-intent'),
        ChatRequest(message='添加衣服', request_id='profile-choice', companion_profile=CompanionProfile(reply_detail=detail)))
    assert ('预览并确认后才会上传' in reply.message) == (detail == '简洁重点')


def test_upload_scenarios_have_explicit_structured_acceptance():
    assert len(EXPECTATIONS) == sum(len(rows) for rows in SCENARIOS.values())
    assert all('upload_intent' in expected for expected in EXPECTATIONS.values())


async def test_refusal_suppresses_partial_wardrobe_upload_card(tmp_path):
    class Model:
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                from stylist.models import Change
                return Plan(mode='recommend', upload_declined=True,
                            changes={'weather_policy': Change(value='ignored', evidence='不考虑天气')})
            return Draft(message='先用已有的衣服给你文字参考。')
    reply = await Stylist(Settings(), Store(str(tmp_path/'decline.db')), Model()).chat(DialogueUpstream('empty_wardrobe'),
        ChatRequest(message='不要让我上传衣服，先给我搭配，不考虑天气。', request_id='decline-upload'))
    assert reply.delivery == 'concept' and not reply.upload_suggestion and reply.upload_intent is None
