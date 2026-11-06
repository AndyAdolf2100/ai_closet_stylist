import json

import httpx
import pytest
from fastapi.testclient import TestClient

from stylist.config import Settings
from stylist.errors import StylistError
from stylist.main import create_app
from stylist.models import CompanionProfile
from stylist.store import Store
from stylist.upstream import Upstream


def test_old_settings_cleaned_without_changing_companion_or_history(tmp_path):
    store = Store(str(tmp_path / 'settings.db'))
    with store.connection() as conn:
        conn.execute('INSERT INTO stylist_companion_profiles(owner_id,profile_json) VALUES(?,?)',
                     ('1', json.dumps({'user_name': '旧昵称', 'user_gender': '男', 'agent_name': '小衣',
                                       'assistant_persona': 'female_warm_v1', 'color_scheme': 'system'})))
    assert store.companion_profile('1').user_name == ''
    assert store.companion_profile('1').user_gender is None
    assert store.remove_legacy_account_settings() == 1
    assert store.remove_legacy_account_settings() == 0
    saved = store.companion_profile('1')
    assert saved.agent_name == '小衣' and saved.assistant_persona == 'female_warm_v1'
    store.save_companion_profile('1', saved.model_copy(update={'user_name': '不能存', 'user_gender': '女'}))
    with store.connection() as conn:
        data = json.loads(conn.execute('SELECT profile_json FROM stylist_companion_profiles').fetchone()['profile_json'])
    assert 'user_name' not in data and 'user_gender' not in data


@pytest.mark.asyncio
async def test_account_updates_only_explicit_fields_and_retries_skip_success():
    account = {'id': 1, 'nick_name': '小林', 'sex': 1}
    posts = []
    fail_gender = True

    def handler(request):
        nonlocal fail_gender
        if request.method == 'GET':
            return httpx.Response(200, json={'code': 0, 'data': dict(account)})
        assert request.headers['authorization'] == 'Bearer test'
        body = json.loads(request.content)
        posts.append((request.url.path, body))
        if request.url.path.endswith('onboarding/profile'):
            account['nick_name'] = body['onboarding_name']
        else:
            if fail_gender:
                fail_gender = False
                return httpx.Response(503)
            account['sex'] = body['sex']
        return httpx.Response(200, json={'code': 0, 'data': None})

    def upstream():
        return Upstream(Settings(server_url='https://server.invalid'), 'Bearer test', httpx.MockTransport(handler))

    u = upstream()
    assert await u.identity() == '1'
    profile = CompanionProfile(user_name='新昵称', user_gender='女')
    with pytest.raises(StylistError, match='account_save_unknown'):
        await u.save_account_identity(profile, ['user_name', 'user_gender'])
    u = upstream()
    await u.identity()
    assert await u.save_account_identity(profile, ['user_name', 'user_gender']) == {
        'user_name': '新昵称', 'user_gender': '女'}
    assert sum(path.endswith('onboarding/profile') for path, _ in posts) == 1
    assert sum(path.endswith('update/sex') for path, _ in posts) == 2


def test_api_hydrates_account_and_does_not_write_stale_preferences(tmp_path, monkeypatch):
    state = {'1': {'user_name': '账号昵称', 'user_gender': '女'},
             '2': {'user_name': '', 'user_gender': None}}
    writes = []

    async def identity(self):
        return self.authorization.split()[-1]

    async def account(self):
        return dict(state[self.authorization.split()[-1]])

    async def save(self, profile, fields):
        writes.append(fields)
        state[self.authorization.split()[-1]].update({f: getattr(profile, f) for f in fields})
        return await account(self)

    monkeypatch.setattr(Upstream, 'identity', identity)
    monkeypatch.setattr(Upstream, 'account_identity', account)
    monkeypatch.setattr(Upstream, 'save_account_identity', save)
    app = create_app(Settings(database=str(tmp_path / 'api.db')))
    with TestClient(app) as client:
        headers = {'Authorization': 'Bearer 1'}
        body = client.get('/stylist-api/companion-profile', headers=headers).json()
        assert body == {'profile': None, 'account': state['1']}
        data = CompanionProfile(user_name='过期昵称', user_gender='男', agent_name='小衣').model_dump()
        response = client.put('/stylist-api/companion-profile', headers=headers, json=data)
        assert response.json()['profile']['user_name'] == '账号昵称'
        assert response.json()['profile']['user_gender'] == '女'
        assert writes == []
        response = client.put('/stylist-api/companion-profile', headers=headers,
                              json={**data, 'account_fields': ['user_name', 'user_gender']})
        assert response.json()['profile']['user_name'] == '过期昵称'
        assert writes == [['user_name', 'user_gender']]
        assert client.get('/stylist-api/companion-profile', headers={'Authorization': 'Bearer 2'}).json()['profile'] is None
        assert app.state.engine.store.companion_profile('1').user_name == ''
        assert app.state.engine.store.companion_profile('1').user_gender is None


@pytest.mark.parametrize('sex,expected', [(0, None), (1, '男'), (2, '女'), ('2', '女'), (99, None)])
@pytest.mark.asyncio
async def test_missing_account_name_and_unknown_sex_never_fall_back(sex, expected):
    def handler(request):
        return httpx.Response(200, json={'code': 0, 'data': {'id': 1, 'sex': sex}})
    upstream = Upstream(Settings(server_url='https://server.invalid'), 'Bearer test', httpx.MockTransport(handler))
    await upstream.identity()
    assert await upstream.account_identity() == {'user_name': '', 'user_gender': expected}


def test_failed_account_save_does_not_save_companion(tmp_path, monkeypatch):
    async def identity(self):
        return '1'
    async def fail(*args):
        raise StylistError('account_save_unknown', '保存未确认', 502)
    monkeypatch.setattr(Upstream, 'identity', identity)
    monkeypatch.setattr(Upstream, 'save_account_identity', fail)
    app = create_app(Settings(database=str(tmp_path / 'failed.db')))
    with TestClient(app) as client:
        data = CompanionProfile(user_name='小夏', user_gender='女').model_dump()
        response = client.put('/stylist-api/companion-profile', headers={'Authorization': 'Bearer 1'},
                              json={**data, 'account_fields': ['user_name', 'user_gender']})
        assert response.status_code == 502
        assert app.state.engine.store.companion_profile('1') is None


@pytest.mark.asyncio
async def test_success_response_without_matching_account_readback_is_not_saved():
    def handler(request):
        return httpx.Response(200, json={'code': 0, 'data': {'id': 1, 'nick_name': '旧昵称', 'sex': 1}
                                        if request.method == 'GET' else None})
    upstream = Upstream(Settings(server_url='https://server.invalid'), 'Bearer test', httpx.MockTransport(handler))
    await upstream.identity()
    with pytest.raises(StylistError) as exc:
        await upstream.save_account_identity(CompanionProfile(user_name='新昵称'), ['user_name'])
    assert exc.value.code == 'account_save_unconfirmed'
