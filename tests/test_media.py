import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from stylist.config import Settings
from stylist.errors import StylistError
from stylist.main import create_app
from stylist.media import (
    ConfirmInput,
    GenerationInput,
    MediaActions,
    TwinCandidate,
    TwinSelection,
    UploadInput,
)
from stylist.store import Store

PHOTO = 'data:image/png;base64,iVBORw0KGgoAAAAAAAAAAAAAAAAAAAAAAAAA'


class Business:
    owner = '1'
    fail = False
    def __init__(self):
        self.writes = []
        self.check = {'status': 'completed', 'check_id': '101', 'result': 'pass',
                      'allowed_hat_actions': ['none'], 'generation_cost_points': 20}
        self.overview = {'selection_version': 3, 'system_twins': [{'twin_key': 'base'}],
                         'custom_twin': None, 'pending_task': {'task_id': '202', 'can_confirm': True}}

    async def identity(self):
        return self.owner

    async def get(self, path):
        assert path == '/api/digital_twin/overview'
        return {}

    @asynccontextmanager
    async def mcp(self, **kwargs):
        yield self

    async def call(self, name, args):
        await asyncio.sleep(0)
        if name == 'digital_twin_photo_check_status':
            return self.check.copy()
        if name == 'product_upload_status':
            return {'status': 'completed', 'task_id': args['task_id'], 'user_product_id': 17,
                    'class_name': '上衣', 'result_image_url': 'https://example.test/shirt.png'}
        if name == 'digital_twin_generation_status':
            return {'status': 'completed', 'task_id': args['task_id'], 'can_confirm': True,
                    'result_image_url': 'https://example.test/person.png'}
        if name == 'digital_twin_overview':
            return self.overview.copy()
        if name == 'product_upload_receipt':
            return {'status': 'unknown', 'stage': 'submission'}
        pytest.fail(name)

    async def commit_media(self, name, args):
        self.writes.append((name, args.copy()))
        await asyncio.sleep(0)
        if self.fail:
            raise StylistError('mcp_unavailable', '提交结果未知')
        if name == 'product_add':
            return {'status': 'processing', 'task_id': 'upload-task'}
        if name == 'digital_twin_photo_check':
            return {'status': 'processing', 'check_id': '101'}
        if name == 'digital_twin_generate':
            return {'status': 'processing', 'task_id': '202'}
        return self.overview.copy()


@pytest.fixture
def setup(tmp_path):
    return MediaActions(Store(str(tmp_path/'state.db'))), Business()


def upload(kind='garment', confirmed=True, request_id='upload-case-001'):
    return UploadInput(kind=kind, image_data=PHOTO, confirmed=confirmed, request_id=request_id)


async def quoted(service, business):
    photo = await service.upload(business, upload('person'))
    photo = await service.refresh(business, photo['action_id'])
    q = await service.generation_quote(business, photo['action_id'], GenerationInput(request_id='generation-quote'))
    return photo, q


async def test_upload_only_after_confirmation_and_store_has_no_photo_bytes(setup):
    service, business = setup
    assert (await service.upload(business, upload(confirmed=False)))['status'] == 'cancelled'
    assert business.writes == [] and service.list('1') == []
    first, second = await asyncio.gather(service.upload(business, upload()), service.upload(business, upload()))
    assert first['action_id'] == second['action_id']
    assert [name for name, _ in business.writes] == ['product_add']
    with service.store.connection() as conn:
        row = dict(conn.execute('SELECT * FROM stylist_media_actions').fetchone())
    assert PHOTO not in json.dumps(row) and 'image_data' not in json.dumps(row)
    finished = await service.refresh(business, first['action_id'])
    assert finished['result']['user_product_id'] == 17
    assert finished['status'] == 'completed'
    assert len(business.writes) == 1  # Status retrieval never uploads again.


async def test_unknown_upload_does_not_replay_or_claim_success(setup):
    service, business = setup
    business.fail = True
    with pytest.raises(StylistError):
        await service.upload(business, upload())
    action = service.list('1')[0]
    assert action['status'] == 'unknown'
    assert (await service.upload(business, upload()))['status'] == 'unknown'
    assert (await service.refresh(business, action['action_id']))['status'] == 'unknown'
    assert len(business.writes) == 1


async def test_lost_upload_response_recovers_original_receipt_without_another_upload(setup):
    service, business = setup
    business.fail = True
    with pytest.raises(StylistError):
        await service.upload(business, upload())
    action = service.list('1')[0]
    previous = business.call
    async def read(name, args):
        if name == 'product_upload_receipt':
            assert args == {'idempotency_key': action['action_id']}
            return {'status': 'processing', 'task_id': 'original-task'}
        return await previous(name, args)
    business.call = read
    assert (await service.refresh(business, action['action_id']))['status'] == 'processing'
    assert (await service.refresh(business, action['action_id']))['status'] == 'completed'
    assert len(business.writes) == 1


async def test_same_key_different_image_and_cross_account_reads_rejected(setup):
    service, business = setup
    action = await service.upload(business, upload())
    changed = upload().model_copy(update={'image_data': 'data:image/png;base64,iVBORw0KGgoAAAAAAAAAAAAAAAAAAAAAAAAB'})
    with pytest.raises(StylistError, match='idempotency_conflict'):
        await service.upload(business, changed)
    business.owner = '2'
    with pytest.raises(StylistError, match='media_not_found'):
        await service.refresh(business, action['action_id'])
    assert service.list('2') == []


async def test_generation_quote_is_read_only_and_cancel_is_not_charged(setup):
    service, business = setup
    _, q = await quoted(service, business)
    assert q['points_cost'] == 20 and q['status'] == 'quoted'
    assert [n for n, _ in business.writes] == ['digital_twin_photo_check']
    assert (await service.confirm_generation(business, q['action_id'], False))['status'] == 'cancelled'
    assert (await service.confirm_generation(business, q['action_id'], True))['status'] == 'cancelled'
    assert len(business.writes) == 1


async def test_generation_changed_price_needs_fresh_confirmation(setup):
    service, business = setup
    _, q = await quoted(service, business)
    business.check['generation_cost_points'] = 30
    with pytest.raises(StylistError, match='image_quote_changed'):
        await service.confirm_generation(business, q['action_id'], True)
    assert len(business.writes) == 1


async def test_generation_single_dispatch_and_restart_status_recovery(setup):
    service, business = setup
    _, q = await quoted(service, business)
    await asyncio.gather(*(service.confirm_generation(business, q['action_id'], True) for _ in range(4)))
    writes = [args for name, args in business.writes if name == 'digital_twin_generate']
    assert len(writes) == 1 and writes[0]['expected_cost_points'] == 20
    assert writes[0]['check_id'] == '101'
    restored = MediaActions(service.store)
    completed = await restored.refresh(business, q['action_id'])
    assert completed['status'] == 'completed' and completed['result']['result_image_url']
    assert len(business.writes) == 2


async def test_generation_expired_and_rejected_photo_cannot_charge(setup):
    service, business = setup
    _, q = await quoted(service, business)
    business.check['allowed_hat_actions'] = []
    with pytest.raises(StylistError, match='image_quote_changed'):
        await service.confirm_generation(business, q['action_id'], True)
    assert len(business.writes) == 1


async def test_unknown_generation_never_auto_replayed(setup):
    service, business = setup
    _, q = await quoted(service, business)
    business.fail = True
    with pytest.raises(StylistError):
        await service.confirm_generation(business, q['action_id'], True)
    assert (await service.confirm_generation(business, q['action_id'], True))['status'] == 'unknown'
    assert (await service.refresh(business, q['action_id']))['status'] == 'unknown'
    assert len(business.writes) == 2


async def test_lost_generation_response_matches_owned_request_before_reading_task(setup):
    service, business = setup
    _, q = await quoted(service, business)
    business.fail = True
    with pytest.raises(StylistError):
        await service.confirm_generation(business, q['action_id'], True)
    async def overview(path):
        return {'latest_task': {'request_id': q['action_id'], 'task_id': '202'}}
    business.get = overview
    result = await service.refresh(business, q['action_id'])
    assert result['status'] == 'completed' and result['result']['task_id'] == '202'
    assert len(business.writes) == 2


async def test_select_and_confirm_candidates_require_latest_owned_overview(setup):
    service, business = setup
    with pytest.raises(StylistError, match='twin_changed'):
        await service.select(business, TwinSelection(twin_key='someone-else', expected_version=3))
    with pytest.raises(StylistError, match='twin_changed'):
        await service.use_candidate(business, TwinCandidate(task_id='999', expected_version=3))
    with pytest.raises(StylistError, match='twin_changed'):
        await service.use_candidate(business, TwinCandidate(task_id='202', expected_version=2))
    assert not business.writes
    await service.select(business, TwinSelection(twin_key='base', expected_version=3))
    await service.use_candidate(business, TwinCandidate(task_id='202', expected_version=3))
    assert [n for n, _ in business.writes] == ['digital_twin_set_default', 'digital_twin_confirm']


def test_media_api_rejects_spoofed_owner_cost_and_unconfirmed_photos(tmp_path, monkeypatch):
    async def identity(self):
        return '1'
    monkeypatch.setattr('stylist.main.Upstream.identity', identity)
    with TestClient(create_app(Settings(database=str(tmp_path/'api.db')))) as client:
        assert client.get('/stylist-api/media').status_code == 401
        h = {'Authorization': 'Bearer synthetic'}
        assert client.get('/stylist-api/media', headers=h).json() == []
        for extra in ({'user_id': '2'}, {'points_cost': 0}, {'confirmed': 1}):
            body = {**upload().model_dump(), **extra}
            assert client.post('/stylist-api/media/uploads', headers=h, json=body).status_code == 422
        assert client.post('/stylist-api/media/uploads', headers=h, json=upload(confirmed=False).model_dump()).json()['status'] == 'cancelled'
    with pytest.raises(ValueError):
        ConfirmInput(confirmed='yes')
