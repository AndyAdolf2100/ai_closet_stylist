import asyncio
from contextlib import asynccontextmanager

import pytest

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.models import ChatRequest, Draft, LookDraft, Plan
from stylist.runtime import RunManager
from stylist.store import Store


class Upstream:
    authorization = 'Bearer test-secret-not-in-checkpoint'

    def __init__(self, owner='owner-1'):
        self.owner = owner

    async def identity(self):
        return self.owner

    @asynccontextmanager
    async def mcp(self):
        pytest.fail('Plain advice must not query tools')
        yield


class Model:
    def __init__(self):
        self.calls = []
        self.fail_style = False

    async def generate(self, name, payload, result_type):
        self.calls.append(name)
        if name == 'plan':
            return Plan(mode='consult', use_inventory=False)
        if self.fail_style:
            raise StylistError('model_output_invalid', '模拟失败')
        return Draft(message='保持现有衣物，调整穿法。', looks=[LookDraft(title='自然垂放', pieces=['针织衫'], why=['保留偏好'], how=['下摆自然垂放'])])


@pytest.mark.asyncio
async def test_restart_resumes_failed_node_without_repeating_understanding(tmp_path):
    path = str(tmp_path / 'state.db')
    model = Model()
    model.fail_style = True
    req = ChatRequest(message='只咨询穿法', request_id='restart-test-001')
    with pytest.raises(StylistError, match='model_output_invalid'):
        await Stylist(Settings(), Store(path), model).chat(Upstream(), req)
    assert model.calls == ['plan', 'style']
    model.fail_style = False
    restarted = Stylist(Settings(), Store(path), model)
    reply = await restarted.chat(Upstream(), req)
    assert reply.delivery == 'advice'
    assert model.calls == ['plan', 'style', 'style']
    assert await restarted.chat(Upstream(), req) == reply
    assert model.calls == ['plan', 'style', 'style']
    assert b'test-secret-not-in-checkpoint' not in (tmp_path / 'state.db.checkpoints').read_bytes()


@pytest.mark.asyncio
async def test_confirmation_survives_restart_and_cancel_never_generates(tmp_path):
    path = str(tmp_path / 'state.db')
    model = Model()
    req = ChatRequest(message='只咨询穿法', request_id='approval-test-001', confirm_plan=True)
    reply = await Stylist(Settings(), Store(path), model).chat(Upstream(), req)
    assert reply.pending_confirmation and reply.version == 0
    assert model.calls == ['plan']
    restarted = Stylist(Settings(), Store(path), model)
    waiting = await restarted.chat(Upstream(), req)
    assert waiting.pending_confirmation and model.calls == ['plan']
    reply = await restarted.chat(Upstream(), req, decision=True)
    assert reply.version == 1 and not reply.pending_confirmation
    assert model.calls == ['plan', 'style']
    second = ChatRequest(message='咨询另一种穿法', request_id='cancel-test-001', confirm_plan=True)
    await restarted.chat(Upstream(), second)
    before = list(model.calls)
    cancelled = await restarted.chat(Upstream(), second, decision=False)
    assert cancelled.message == '已取消本次生成。' and model.calls == before


@pytest.mark.asyncio
async def test_confirmation_is_owner_scoped_and_new_user_cannot_resume(tmp_path):
    engine = Stylist(Settings(), Store(str(tmp_path / 'state.db')), Model())
    req = ChatRequest(message='只咨询穿法', request_id='owner-test-001', confirm_plan=True)
    await engine.chat(Upstream(), req)
    with pytest.raises(StylistError, match='run_not_waiting'):
        await engine.chat(Upstream('other-owner'), req, decision=True)
    assert (await engine.chat(Upstream(), req)).pending_confirmation


@pytest.mark.asyncio
async def test_disconnected_subscriber_does_not_cancel_generation_and_drain_rejects_new():
    started, release = asyncio.Event(), asyncio.Event()
    class Engine:
        calls = 0
        async def chat(self, upstream, request):
            self.calls += 1
            started.set()
            await release.wait()
            return 'done'
    engine, manager, upstream = Engine(), RunManager(), Upstream()
    req = ChatRequest(message='只咨询穿法', request_id='detach-test-001')
    subscriber = asyncio.create_task(manager.run(engine, upstream, req))
    await started.wait()
    subscriber.cancel()
    with pytest.raises(asyncio.CancelledError):
        await subscriber
    manager.draining = True
    resumed = asyncio.create_task(manager.run(engine, upstream, req))
    with pytest.raises(StylistError, match='server_draining'):
        await manager.run(engine, upstream, req.model_copy(update={'request_id':'another-test-001'}))
    release.set()
    assert await resumed == 'done' and engine.calls == 1
    await manager.close()


@pytest.mark.asyncio
async def test_hard_killed_process_resumes_from_disk(tmp_path):
    import sys
    path, marker = str(tmp_path / 'state.db'), tmp_path / 'in_style'
    code = '''
import asyncio,sys
from pathlib import Path
from stylist.engine import Stylist
from stylist.config import Settings
from stylist.models import Plan,ChatRequest
from stylist.store import Store
class U:
    async def identity(self): return 'owner-1'
class M:
    async def generate(self,name,payload,result_type):
        if name=='plan': return Plan(mode='consult',use_inventory=False)
        Path(sys.argv[2]).write_text('style_started')
        await asyncio.Event().wait()
asyncio.run(Stylist(Settings(),Store(sys.argv[1]),M()).chat(U(),ChatRequest(message='只咨询穿法',request_id='killed-process-001')))
'''
    child = await asyncio.create_subprocess_exec(sys.executable, '-c', code, path, str(marker))
    try:
        async with asyncio.timeout(10):
            while not marker.exists():
                await asyncio.sleep(.05)
    finally:
        if child.returncode is None:
            child.kill()
        await child.wait()
    store = Store(path)
    # Simulate passage of the 45-second lease without slowing the regression suite.
    with store.connection() as conn:
        conn.execute('UPDATE stylist_sessions SET lease_until=0')
    model = Model()
    reply = await Stylist(Settings(), store, model).chat(Upstream(), ChatRequest(
        message='只咨询穿法', request_id='killed-process-001'))
    assert reply.delivery == 'advice' and model.calls == ['style']


@pytest.mark.asyncio
async def test_stale_confirmation_cannot_override_newer_conversation(tmp_path):
    engine = Stylist(Settings(), Store(str(tmp_path / 'state.db')), Model())
    req = ChatRequest(message='只咨询穿法', request_id='stale-approval-001', confirm_plan=True)
    paused = await engine.chat(Upstream(), req)
    newer = ChatRequest(message='先回答另一种穿法', request_id='newer-turn-001', conversation_id=paused.conversation_id)
    await engine.chat(Upstream(), newer)
    with pytest.raises(StylistError, match='stale_version'):
        await engine.chat(Upstream(), req, decision=True)


@pytest.mark.asyncio
async def test_transient_model_failure_retries_only_style_node(tmp_path):
    class Flaky(Model):
        async def generate(self, name, payload, result_type):
            if name == 'style' and self.calls.count('style') == 0:
                self.calls.append(name)
                raise StylistError('model_timeout', '模拟超时')
            return await super().generate(name, payload, result_type)
    model = Flaky()
    engine = Stylist(Settings(), Store(str(tmp_path / 'state.db')), model)
    await engine.chat(Upstream(), ChatRequest(message='只咨询穿法', request_id='retry-node-001'))
    assert model.calls == ['plan', 'style', 'style']


def test_approval_status_api_and_draining(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from stylist.main import create_app
    async def identity(self):
        return self.authorization.removeprefix('Bearer ')
    monkeypatch.setattr('stylist.main.Upstream.identity', identity)
    app = create_app(Settings(database=str(tmp_path / 'state.db')))
    app.state.engine.llm = Model()
    headers = {'Authorization': 'Bearer owner-1'}
    body = {'message':'只咨询穿法', 'request_id':'api-approval-001', 'confirm_plan':True}
    with TestClient(app) as client:
        waiting = client.post('/stylist-api/chat', headers=headers, json=body)
        assert waiting.status_code == 200 and waiting.json()['pending_confirmation']
        status = client.get('/stylist-api/runs/api-approval-001', headers=headers).json()
        assert status['status'] == 'awaiting_confirmation' and status['next_nodes'] == ['approval']
        assert status['completed_nodes'] == ['understand']
        assert client.get('/stylist-api/runs/api-approval-001', headers={'Authorization':'Bearer other'}).status_code == 404
        assert client.post('/stylist-api/chat/approval', headers=headers, json={'request':{**body,'message':'篡改内容'},'approved':True}).status_code == 409
        result = client.post('/stylist-api/chat/approval', headers=headers, json={'request':body,'approved':True})
        assert result.status_code == 200 and result.json()['delivery'] == 'advice'
        assert client.get('/stylist-api/runs/api-approval-001', headers=headers).json()['status'] == 'completed'
        assert client.post('/internal/drain').status_code == 403
        app.state.runs.draining = True
        assert client.get('/health/ready').status_code == 503
        assert client.post('/stylist-api/chat', headers=headers, json={**body,'request_id':'drained-test-001'}).status_code == 503
