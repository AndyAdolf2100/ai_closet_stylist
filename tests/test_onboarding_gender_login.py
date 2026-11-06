import json

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from stylist import auth
from stylist.auth import GenderLoginRequest, LoginRequest
from stylist.config import Settings
from stylist.errors import StylistError


@pytest.mark.asyncio
async def test_pending_gender_login_does_not_set_sex_until_final_action(tmp_path, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = tmp_path / 'public.pem'
    public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,
                                                    serialization.PublicFormat.SubjectPublicKeyInfo))
    paths = []
    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith('mobile/code'):
            return httpx.Response(200, json={'code': 0, 'data': {'sex_token': 'synthetic-pending',
                                           'user_info': {'nick_name': '账号昵称', 'sex': 0}}})
        if request.url.path.endswith('set/sex'):
            assert json.loads(request.content) == {'token': 'synthetic-pending', 'sex': 2}
            return httpx.Response(200, json={'code': 0, 'data': {'token': {'access_token': 'synthetic-access'}}})
        assert request.url.path == '/api/user/info'
        assert request.headers['authorization'] == 'Bearer synthetic-access'
        return httpx.Response(200, json={'code': 0, 'data': {'id': 7, 'nick_name': '账号昵称', 'sex': 2}})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda *a, **kw: original(*a, **{**kw, 'transport': httpx.MockTransport(handler)}))
    settings = Settings(server_url='https://server.invalid', login_public_key=str(public), allow_mobile_login=True)
    result = await auth.login(settings, LoginRequest(mobile='13800000000', code='123456', device_id='test-device'))
    assert result == {'requires_gender': True, 'sex_token': 'synthetic-pending',
                      'user': {'user_name': '账号昵称', 'user_gender': None}}
    assert paths == ['/users/app/login/mobile/code']
    result = await auth.finish_gender_login(settings, GenderLoginRequest(token=result['sex_token'], sex=2, device_id='test-device'))
    assert result['access_token'] == 'synthetic-access' and result['user']['id'] == '7'
    assert paths == ['/users/app/login/mobile/code', '/users/app/login/set/sex', '/api/user/info']


@pytest.mark.asyncio
async def test_new_gender_login_preserves_production_login_switch(monkeypatch):
    monkeypatch.setenv('STYLIST_ENV', 'production')
    with pytest.raises(StylistError) as exc:
        await auth.finish_gender_login(Settings(allow_mobile_login=False),
                                       GenderLoginRequest(token='synthetic', sex=1, device_id='test-device'))
    assert exc.value.code == 'local_login_disabled'
