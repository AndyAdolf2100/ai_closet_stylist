"""Real browser -> Stylist HTTP -> simulated original account HTTP -> temporary DB.

Explicit run: STYLIST_BROWSER_FUNCTIONAL=1 PLAYWRIGHT_MODULE=... pytest -q this_file
No external account/model calls, persistent developer DB, or paid image requests.
"""
import asyncio
import json
import os
import socket
import subprocess
import threading
import time
from contextlib import contextmanager

import pytest
import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from stylist.config import Settings
from stylist.main import create_app


@contextmanager
def live_server(app):
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        if not thread.is_alive():
            raise RuntimeError('Isolated test server stopped during startup')
        time.sleep(.02)
    else:
        raise RuntimeError('Isolated test server did not start')
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        server.should_exit = True
        thread.join(timeout=8)
        sock.close()


def account_stub():
    app = FastAPI()
    state = {'users': {'qa-a': {'id': 101, 'nick_name': '账号小夏', 'sex': 2},
                       'qa-b': {'id': 102, 'nick_name': '', 'sex': 0}},
             'writes': [], 'fail_gender': 0, 'hold_gender': False, 'sex_token_used': False,
             'ignore_name': False, 'read_error': False}

    @app.get('/__qa/state')
    async def inspect():
        return state

    @app.post('/__qa/control')
    async def control(request: Request):
        data = await request.json()
        for key in ('fail_gender', 'hold_gender', 'ignore_name', 'read_error'):
            if key in data:
                state[key] = data[key]
        if 'account' in data:
            state['users'][data['account']].update(data.get('fields', {}))
        return {'ok': True}

    @app.api_route('/{path:path}', methods=['GET', 'POST'])
    async def upstream(path: str, request: Request):
        route = '/' + path
        owner = request.headers.get('authorization', '').removeprefix('Bearer ')
        if route == '/users/app/login/mobile/code':
            state['writes'].append({'path': route})
            return {'code': 0, 'data': {'sex_token': 'qa-pending', 'user_info': state['users']['qa-b']}}
        if route == '/users/app/login/set/sex':
            body = await request.json()
            state['writes'].append({'path': route, 'sex': body.get('sex')})
            if state['sex_token_used'] or body.get('token') != 'qa-pending':
                return {'code': 43100, 'data': None}
            state['sex_token_used'] = True
            state['users']['qa-b']['sex'] = body['sex']
            return {'code': 0, 'data': {'token': {'access_token': 'qa-b'}}}
        if owner not in state['users']:
            return JSONResponse({'code': 401, 'data': None}, status_code=401)
        user = state['users'][owner]
        if route == '/api/user/info':
            if state['read_error']:
                return JSONResponse({'code': 500}, status_code=503)
            return {'code': 0, 'data': user}
        if route in ('/api/user/onboarding/profile', '/api/user/update/sex'):
            body = await request.json()
            state['writes'].append({'path': route, 'owner': owner, 'body': body})
            if route.endswith('update/sex'):
                while state['hold_gender']:
                    await asyncio.sleep(.02)
                if state['fail_gender']:
                    state['fail_gender'] -= 1
                    return JSONResponse({'code': 500}, status_code=503)
                user['sex'] = body['sex']
            elif not state['ignore_name']:
                user['nick_name'] = body['onboarding_name']
            return {'code': 0, 'data': None}
        return {'code': 0, 'data': {'list': [], 'total': 0}}

    return app, state


@pytest.mark.skipif(os.getenv('STYLIST_BROWSER_FUNCTIONAL') != '1', reason='explicit isolated browser functional suite')
def test_real_http_onboarding_functional_chain(tmp_path, monkeypatch):
    monkeypatch.delenv('STYLIST_ENV', raising=False)
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key = tmp_path / 'public.pem'
    key.write_bytes(private.public_key().public_bytes(serialization.Encoding.PEM,
                                                    serialization.PublicFormat.SubjectPublicKeyInfo))
    stub, state = account_stub()
    with live_server(stub) as account_url:
        app = create_app(Settings(database=str(tmp_path / 'functional.sqlite3'), server_url=account_url,
                                  mcp_url=account_url + '/mcp', login_public_key=str(key), allow_mobile_login=True,
                                  request_timeout=3))
        with live_server(app) as stylist_url:
            env = {**os.environ, 'ONBOARDING_HTTP_BASE': stylist_url, 'ONBOARDING_HTTP_ACCOUNT': account_url}
            result = subprocess.run(['node', 'tests/onboarding_http.browser.cjs'], env=env,
                                    capture_output=True, text=True, timeout=120)
            assert result.returncode == 0, result.stdout + result.stderr
            print(result.stdout.strip())
    # The persisted settings are configuration only, not duplicated account fields.
    with app.state.engine.store.connection() as conn:
        rows = conn.execute('SELECT profile_json FROM stylist_companion_profiles').fetchall()
    assert len(rows) == 2
    for row in rows:
        stored = json.loads(row['profile_json'])
        assert 'user_name' not in stored and 'user_gender' not in stored
        assert stored['agent_name'] and stored['assistant_persona']
    assert all(w['path'] in ('/users/app/login/mobile/code', '/users/app/login/set/sex',
                             '/api/user/onboarding/profile', '/api/user/update/sex') for w in state['writes'])
    assert state['users']['qa-a']['id'] != state['users']['qa-b']['id']
