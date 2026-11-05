import json

import httpx
import pytest
from pydantic import ValidationError

from stylist.config import Settings
from stylist.errors import StylistError
from stylist.media import TwinBodyProfile
from stylist.upstream import Upstream


def test_partial_update_preserves_unedited_fields_and_explicit_clear():
    request = TwinBodyProfile(expected_version=4, height_cm=None)
    assert request.model_dump(exclude_unset=True) == {'expected_version': 4, 'height_cm': None}
    for fields in [{'height_cm': float('nan')}, {'weight_kg': -1}, {'gender': 'male'}, {'user_id': 7}]:
        with pytest.raises(ValidationError):
            TwinBodyProfile(expected_version=4, **fields)


@pytest.mark.asyncio
async def test_body_uses_ios_versioned_endpoint_and_authorization():
    fields = {'height_cm': 178.5, 'skin_tone': None, 'expected_version': 4}
    def handler(request):
        assert request.url.path == '/api/digital_twin/profile/update'
        assert request.headers['authorization'] == 'Bearer fixture'
        assert json.loads(request.content) == fields
        return httpx.Response(200, json={'code': 0, 'data': {'profile_version': 5}})
    upstream = Upstream(Settings(), 'Bearer fixture', httpx.MockTransport(handler))
    assert await upstream.update_twin_body(fields) == {'profile_version': 5}


@pytest.mark.asyncio
async def test_body_version_conflict_never_retries():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'code': 45305})
    upstream = Upstream(Settings(), 'Bearer fixture', httpx.MockTransport(handler))
    with pytest.raises(StylistError, match='profile_version_conflict'):
        await upstream.update_twin_body({'expected_version': 1, 'weight_kg': 60})
    assert len(calls) == 1


def test_body_routes_require_identity_and_preserve_partial_payload(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from stylist.main import create_app
    calls = []
    async def identity(self):
        calls.append('identity')
        return '1'
    async def update(self, fields):
        calls.append(fields)
        return {'profile_version': 2}
    monkeypatch.setattr(Upstream, 'identity', identity)
    monkeypatch.setattr(Upstream, 'update_twin_body', update)
    with TestClient(create_app(Settings(database=str(tmp_path / 'body.db')))) as client:
        assert client.get('/stylist-api/twins/options').status_code == 401
        assert client.post('/stylist-api/twins/profile', json={'expected_version': 1}).status_code == 401
        response = client.post('/stylist-api/twins/profile', headers={'Authorization': 'Bearer fixture'},
                               json={'expected_version': 1, 'height_cm': None})
        assert response.status_code == 200
        assert calls == ['identity', {'expected_version': 1, 'height_cm': None}]
