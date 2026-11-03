"""The App shell has a fixed, read-only boundary independent of Agent tools."""
import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from stylist.closet_app import router
from stylist.config import Settings
from stylist.errors import StylistError


def client(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr('stylist.closet_app.httpx.AsyncClient',
                        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)))
    app = FastAPI()

    @app.exception_handler(StylistError)
    async def error_handler(request, exc):
        return JSONResponse({'code': exc.code}, status_code=exc.status)

    app.include_router(router(Settings(server_url='https://upstream.invalid')))
    return TestClient(app)


def test_shell_requires_identity_and_disallows_arbitrary_routes(monkeypatch):
    def never(request):
        pytest.fail('Invalid requests must never reach upstream')
    with client(monkeypatch, never) as web:
        assert web.get('/stylist-api/app/profile').status_code == 401
        assert web.get('/stylist-api/app/delete', headers={'Authorization': 'Bearer fixture'}).status_code == 404
        assert web.get('/stylist-api/app/album?page=0').status_code == 422


def test_shell_forwards_current_account_and_fixed_read_query(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={'code': 0, 'data': {'items': []}})
    with client(monkeypatch, handler) as web:
        for token in ['account-a', 'account-b']:
            result = web.get('/stylist-api/app/album?page=2', headers={'Authorization': f'Bearer {token}'})
            assert result.json() == {'data': {'items': []}}
            assert result.headers['cache-control'] == 'no-store'
    assert [r.headers['authorization'] for r in seen] == ['Bearer account-a', 'Bearer account-b']
    assert all(r.method == 'GET' and r.url.path == '/api/home/outfit_album' for r in seen)
    assert dict(seen[0].url.params) == {'page': '2', 'page_size': '10'}


@pytest.mark.parametrize('status,payload,expected', [
    (200, {'code': 43103}, 401),
    (503, {}, 502),
    (200, {'unexpected': 'shape'}, 503),
])
def test_shell_does_not_present_failures_as_empty_wardrobe(monkeypatch, status, payload, expected):
    with client(monkeypatch, lambda request: httpx.Response(status, json=payload)) as web:
        response = web.get('/stylist-api/app/recent', headers={'Authorization': 'Bearer fixture'})
    assert response.status_code == expected
    assert 'data' not in response.json()

@pytest.mark.parametrize('section,path,payload', [
    ('orders', '/api/vip_orders/list', {'list': [], 'pagination': {'total': 0}}),
    ('points-orders', '/api/booster/order_list', {'list': []}),
    ('messages', '/api/message/list', []),
])
def test_account_pages_use_fixed_routes_and_normalize_messages(monkeypatch, section, path, payload):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={'code': 0, 'data': payload})
    with client(monkeypatch, handler) as web:
        response = web.get(f'/stylist-api/app/{section}?page=2', headers={'Authorization': 'Bearer current'})
    assert response.status_code == 200
    assert response.json()['data']['list'] == []
    assert seen[0].url.path == path
    assert seen[0].url.params['page'] == '2'
    assert seen[0].headers['authorization'] == 'Bearer current'


def test_feedback_requires_valid_body_and_explicit_post(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={'code': 0, 'data': None})
    headers = {'Authorization': 'Bearer current'}
    with client(monkeypatch, handler) as web:
        assert web.post('/stylist-api/app/feedback', json={'content': 'hello'}).status_code == 401
        for body in [{'content': ' '}, {'content': 'x'*301}, {'content': 'hello', 'urls': ['https://x.test/a']*10}]:
            assert web.post('/stylist-api/app/feedback', json=body, headers=headers).status_code == 422
        result = web.post('/stylist-api/app/feedback', json={'content': ' useful idea ', 'urls': []}, headers=headers)
    assert result.status_code == 200
    assert len(seen) == 1
    assert seen[0].method == 'POST' and seen[0].url.path == '/api/feedback/add'
    import json
    assert json.loads(seen[0].content) == {'content': 'useful idea', 'urls': []}


def test_message_detail_validates_returned_identity(monkeypatch):
    with client(monkeypatch, lambda request: httpx.Response(200, json={'code': 0, 'data': {'id': 999}})) as web:
        result = web.get('/stylist-api/app/message-detail/12', headers={'Authorization': 'Bearer current'})
    assert result.status_code == 502


def test_feedback_upload_is_fixed_type_and_invalid_images_do_not_forward(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={'code': 0, 'data': {'url': 'https://image.test/p.png'}})
    with client(monkeypatch, handler) as web:
        for data in ['https://external.test/file', 'data:image/png;base64,invalid!']:
            assert web.post('/stylist-api/app/feedback-image', json={'image_url': data}, headers={'Authorization': 'Bearer current'}).status_code == 422
    assert not seen


def test_feedback_image_upload_uses_feedback_scope(monkeypatch):
    import json
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={'code': 0, 'data': {'url': 'https://image.test/p.png'}})
    value = 'data:image/png;base64,aGVsbG8='
    with client(monkeypatch, handler) as web:
        result = web.post('/stylist-api/app/feedback-image', json={'image_url': value},
                          headers={'Authorization': 'Bearer current'})
    assert result.status_code == 200
    assert seen[0].url.path == '/api/upload/base64/image'
    assert json.loads(seen[0].content) == {'upload_type': 'feedback', 'image_url': value}


def test_feedback_business_failure_is_not_success(monkeypatch):
    with client(monkeypatch, lambda request: httpx.Response(200, json={'code': 999, 'msg': 'failed'})) as web:
        result = web.post('/stylist-api/app/feedback', json={'content': 'valid feedback'},
                          headers={'Authorization': 'Bearer current'})
    assert result.status_code >= 400
    assert 'data' not in result.json()


def test_only_supported_app_designs_are_served(tmp_path):
    from stylist.main import create_app

    with TestClient(create_app(Settings(database=str(tmp_path / 'app-designs.db')))) as web:
        for path in ['/app/', '/app/?design=ios', '/app/?design=yijian']:
            assert web.get(path).status_code == 200
        for path in ['/app/?design=orbit', '/app/?design=unsupported']:
            response = web.get(path, follow_redirects=False)
            assert response.status_code == 404
            assert 'location' not in response.headers
            assert 'design-bootstrap' not in response.text


def test_checkin_reads_real_state_and_config_without_claiming(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        data = {'/api/check_in/today': {'signed': False, 'total_days': 3},
                '/api/check_in/recent': {'days': [], 'tips': 'daily'},
                '/api/app_config/config_check': {'daily_checkin_points': 23}}[request.url.path]
        return httpx.Response(200, json={'code': 0, 'data': data})
    with client(monkeypatch, handler) as web:
        result = web.get('/stylist-api/app/checkin', headers={'Authorization': 'Bearer fixture'})
    assert result.json()['data']['daily_points'] == 23
    assert result.json()['data']['signed'] is False
    assert all(r.method == 'GET' for r in seen)


def test_checkin_does_not_invent_reward_if_config_unavailable(monkeypatch):
    def handler(request):
        if request.url.path.endswith('config_check'):
            return httpx.Response(503)
        data = {'signed': True, 'total_days': 1} if request.url.path.endswith('today') else {'days': []}
        return httpx.Response(200, json={'code': 0, 'data': data})
    with client(monkeypatch, handler) as web:
        result = web.get('/stylist-api/app/checkin', headers={'Authorization': 'Bearer fixture'})
    assert result.json()['data']['daily_points'] is None
    assert result.json()['data']['signed'] is True


@pytest.mark.parametrize('payload', [
    {'granted': True, 'points_added': 23, 'total_days': 4},
    {'granted': False, 'points_added': 0, 'total_days': 4},
])
def test_checkin_claim_uses_upstream_receipt_and_fixed_post(monkeypatch, payload):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={'code': 0, 'data': payload})
    with client(monkeypatch, handler) as web:
        assert web.post('/stylist-api/app/checkin').status_code == 401
        result = web.post('/stylist-api/app/checkin', headers={'Authorization': 'Bearer fixture'})
    assert result.json()['data'] == payload
    assert len(seen) == 1 and seen[0].method == 'POST' and seen[0].url.path == '/api/check_in'


def test_unknown_checkin_receipt_is_failure(monkeypatch):
    with client(monkeypatch, lambda request: httpx.Response(200, json={'code': 0, 'data': {'points_added': 20}})) as web:
        result = web.post('/stylist-api/app/checkin', headers={'Authorization': 'Bearer fixture'})
    assert result.status_code == 502


@pytest.mark.parametrize('section,expected_type', [('fitting-records', 'fitting'), ('trend-records', 'trend')])
def test_app_generation_records_are_not_agent_tasks(monkeypatch, section, expected_type):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={'code': 0, 'data': {'list': [], 'total_count': 0}})
    with client(monkeypatch, handler) as web:
        response = web.get('/stylist-api/app/'+section+'?page=2', headers={'Authorization': 'Bearer fixture'})
    assert response.status_code == 200
    assert seen[0].url.path == '/api/generation_records/list'
    assert dict(seen[0].url.params) == {'type': expected_type, 'page': '2', 'page_size': '10'}


def test_my_outfits_uses_ios_cursor_not_home_album(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={'code': 0, 'data': {'list': []}})
    with client(monkeypatch, handler) as web:
        response = web.get('/stylist-api/app/my-outfits?outfit_id=42&outfit_id_type=2', headers={'Authorization': 'Bearer fixture'})
    assert response.status_code == 200
    assert seen[0].url.path == '/api/ai_outfit_merge_my_outfit/list'
    assert dict(seen[0].url.params) == {'outfit_id': '42', 'outfit_id_type': '2'}


def test_app_runtime_resources_are_included_in_package_data():
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    patterns = tomllib.loads((root / 'pyproject.toml').read_text())['tool']['setuptools']['package-data']['stylist']
    packaged = {path for pattern in patterns for path in (root / 'stylist').glob(pattern) if path.is_file()}
    resources = {path for path in (root / 'stylist/static/closet-app').rglob('*') if path.is_file() and 'private' not in path.relative_to(root / 'stylist/static/closet-app').parts}
    assert resources and resources <= packaged
    assert not any('private' in path.relative_to(root / 'stylist').parts for path in packaged)
