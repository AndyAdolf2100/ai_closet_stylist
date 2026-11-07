import asyncio

import pytest
from fastapi.testclient import TestClient

from stylist.config import Settings
from stylist.errors import StylistError
from stylist.main import create_app
from stylist.models import ChatRequest
from stylist.runtime import RunManager


class Identity:
    def __init__(self, authorization='Bearer synthetic'):
        self.authorization = authorization

    async def identity(self):
        return self.authorization


class WaitingEngine:
    def __init__(self):
        self.started = asyncio.Event()
        self.cleaned = asyncio.Event()
        self.calls = 0

    async def chat(self, upstream, request):
        self.calls += 1
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.cleaned.set()


@pytest.mark.asyncio
async def test_explicit_stop_cancels_only_identical_authenticated_request():
    manager, engine, owner = RunManager(), WaitingEngine(), Identity()
    request = ChatRequest(message='模拟需求', request_id='stop-task-001')
    subscriber = asyncio.create_task(manager.run(engine, owner, request))
    await engine.started.wait()
    assert (await manager.stop(Identity('Bearer another'), request))['status'] == 'not_running'
    assert not engine.cleaned.is_set()
    changed = request.model_copy(update={'message': '不同的请求'})
    assert (await manager.stop(owner, changed))['status'] == 'not_running'
    assert not engine.cleaned.is_set()
    assert (await manager.stop(owner, request))['status'] == 'stop_requested'
    assert engine.cleaned.is_set()
    with pytest.raises(asyncio.CancelledError):
        await subscriber
    with pytest.raises(StylistError, match='request_stopped'):
        await manager.run(engine, owner, request)
    assert engine.calls == 1


@pytest.mark.asyncio
async def test_stop_arriving_during_identity_check_prevents_late_start():
    manager, engine = RunManager(), WaitingEngine()
    entered, release = asyncio.Event(), asyncio.Event()

    class SlowIdentity(Identity):
        async def identity(self):
            entered.set()
            await release.wait()
            return await super().identity()

    request = ChatRequest(message='模拟需求', request_id='stop-early-001')
    run = asyncio.create_task(manager.run(engine, SlowIdentity(), request))
    await entered.wait()
    await manager.stop(Identity(), request)
    release.set()
    with pytest.raises(StylistError, match='request_stopped'):
        await run
    assert engine.calls == 0


def test_stop_endpoint_requires_auth_and_validates_identity(tmp_path, monkeypatch):
    app = create_app(Settings(database=str(tmp_path / 'stop.db')))
    body = {'message': '模拟需求', 'request_id': 'stop-api-001'}
    async def identity(self):
        return 'synthetic-owner'
    monkeypatch.setattr('stylist.main.Upstream.identity', identity)
    with TestClient(app) as client:
        assert client.post('/stylist-api/chat/stop', json=body).status_code == 401
        response = client.post('/stylist-api/chat/stop', json=body,
                               headers={'Authorization': 'Bearer synthetic'})
        assert response.status_code == 200
        assert response.json() == {'status': 'not_running'}
