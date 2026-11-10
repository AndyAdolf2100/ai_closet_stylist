import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest

from stylist.config import Settings
from stylist.errors import StylistError
from stylist.models import ChatRequest, Look, Product, Reply, Slot, Task
from stylist.outfit_save import OutfitSaveRequest, OutfitSaves
from stylist.store import Store


def setup(tmp_path, *, source='user', items=True):
    store = Store(str(tmp_path / 'save.db'))
    req = ChatRequest(message='通勤搭配', request_id='save-fixture')
    cid, claim, state, _ = store.reserve('1', req)
    state.looks = [Look(title='通勤', items=[Product(source=source, product_id='12', slot=Slot.TOP)] if items else [])]
    reply = Reply(conversation_id=cid, version=1, mode='recommend', delivery='outfit', message='搭配', task=Task(), looks=state.looks)
    store.finish('1', req, claim, state, reply)
    return OutfitSaves(store), cid, OutfitSaveRequest(version=1, look_index=0)


class Upstream:
    def __init__(self):
        self.owner = '1'
        self.writes = []
        self.missing = False
        self.fail = None
        self.tool = True

    async def identity(self):
        return self.owner

    @asynccontextmanager
    async def mcp(self, **kwargs):
        yield self

    async def discover(self):
        return {'save_recommended_outfit': SimpleNamespace(inputSchema={'type': 'object'})} if self.tool else {}

    async def call(self, name, args):
        assert name == 'product.resolve'
        return {'items': [] if self.missing else [dict(p, class_name='上衣') for p in args['items']]}

    async def commit_outfit(self, arguments):
        self.writes.append(arguments)
        await asyncio.sleep(.01)
        if self.fail:
            raise self.fail
        return {'outfit_id': 123}


@pytest.mark.asyncio
async def test_save_calls_only_server_save_and_survives_reload(tmp_path):
    service, cid, req = setup(tmp_path)
    upstream = Upstream()
    assert service.get('1', cid, 1, 0) == {'status': 'missing'}
    saved = await service.save(upstream, cid, req)
    assert saved == {'status': 'saved', 'outfit_id': 123, 'outfit_id_type': 2}
    assert upstream.writes[0]['items'] == [{'source': 'user', 'product_id': 12}]
    assert upstream.writes[0]['selection_id'].startswith('sel_')
    assert len(upstream.writes[0]['selection_id']) == 68
    assert await OutfitSaves(service.store).save(upstream, cid, req) == saved
    assert service.get('1', cid, 1, 0) == saved
    assert len(upstream.writes) == 1


@pytest.mark.asyncio
async def test_concurrent_requests_make_one_write(tmp_path):
    service, cid, req = setup(tmp_path)
    upstream = Upstream()
    results = await asyncio.gather(*(service.save(upstream, cid, req) for _ in range(8)))
    assert len(upstream.writes) == 1
    assert {x['status'] for x in results} <= {'saving', 'saved'}


@pytest.mark.asyncio
async def test_unknown_never_replays_including_restart(tmp_path):
    service, cid, req = setup(tmp_path)
    upstream = Upstream()
    upstream.fail = TimeoutError()
    with pytest.raises(StylistError, match='outfit_save_unknown'):
        await service.save(upstream, cid, req)
    assert await OutfitSaves(service.store).save(upstream, cid, req) == {'status': 'unknown'}
    assert len(upstream.writes) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('owner,version,index', [('2', 1, 0), ('1', 2, 0), ('1', 1, 1)])
async def test_ownership_version_and_index_are_authoritative(tmp_path, owner, version, index):
    service, cid, req = setup(tmp_path)
    upstream = Upstream()
    upstream.owner = owner
    with pytest.raises(StylistError):
        await service.save(upstream, cid, req.model_copy(update={'version': version, 'look_index': index}))
    assert not upstream.writes


@pytest.mark.asyncio
async def test_system_clothes_require_explicit_separate_consent(tmp_path):
    service, cid, req = setup(tmp_path, source='system')
    upstream = Upstream()
    with pytest.raises(StylistError, match='outfit_system_confirmation_required'):
        await service.save(upstream, cid, req)
    assert not upstream.writes
    await service.save(upstream, cid, req.model_copy(update={'include_system': True}))
    assert upstream.writes[0]['items'] == [{'source': 'system', 'product_id': 12}]


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['deleted', 'tool', 'text'])
async def test_preflight_failure_never_writes_and_is_retryable(tmp_path, failure):
    service, cid, req = setup(tmp_path, items=failure != 'text')
    upstream = Upstream()
    upstream.missing = failure == 'deleted'
    upstream.tool = failure != 'tool'
    with pytest.raises(StylistError):
        await service.save(upstream, cid, req)
    assert not upstream.writes
    with service.store.connection() as conn:
        assert conn.execute('SELECT count(*) AS n FROM stylist_outfit_saves').fetchone()['n'] == 0


@pytest.mark.asyncio
async def test_old_card_saves_old_items_while_new_conversation_version_exists(tmp_path):
    service, cid, req = setup(tmp_path)
    request = ChatRequest(message='换一件', request_id='second-save-fixture', conversation_id=cid, expected_version=1)
    _, claim, state, _ = service.store.reserve('1', request)
    state.looks = [Look(title='新方案', items=[Product(source='user', product_id='99', slot=Slot.TOP)])]
    reply = Reply(conversation_id=cid, version=2, mode='recommend', delivery='outfit', message='新搭配', task=Task(), looks=state.looks)
    service.store.finish('1', request, claim, state, reply)
    upstream = Upstream()
    await service.save(upstream, cid, req)
    await service.save(upstream, cid, req.model_copy(update={'version': 2}))
    assert [x['items'][0]['product_id'] for x in upstream.writes] == [12, 99]
    assert upstream.writes[0]['selection_id'] != upstream.writes[1]['selection_id']


@pytest.mark.asyncio
async def test_http_auth_schema_and_my_outfit_identity(tmp_path, monkeypatch):
    import stylist.main as main
    service, cid, req = setup(tmp_path)
    upstream = Upstream()
    monkeypatch.setattr(main, 'Upstream', lambda *args: upstream)
    app = main.create_app(Settings(database=service.store.path))
    url = f'/stylist-api/conversations/{cid}/saved-outfit'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.post(url, json=req.model_dump())).status_code == 401
        headers = {'Authorization': 'Bearer synthetic'}
        assert (await client.post(url, headers=headers, json={**req.model_dump(), 'items': [{'product_id': 999}]})).status_code == 422
        result = await client.post(url, headers=headers, json=req.model_dump())
        assert result.status_code == 200
        assert result.json()['outfit_id_type'] == 2
        assert (await client.get(url+'?version=1&look_index=0', headers=headers)).json() == result.json()
        upstream.owner = '2'
        assert (await client.get(url+'?version=1&look_index=0', headers=headers)).status_code == 404
