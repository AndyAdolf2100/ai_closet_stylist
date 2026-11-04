"""Real loopback HTTP to a Node receiver; supplier replies and identity are fixtures."""
import json
import shutil
import subprocess
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from stylist.config import Settings
from stylist.main import create_app
from stylist.upstream import Upstream


@pytest.fixture(scope='module')
def node_receiver():
    if not shutil.which('node'):
        pytest.skip('Node is required for local receiver integration')
    process = subprocess.Popen(['node', 'scripts/mock_model_usage_server.cjs'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        base = json.loads(process.stdout.readline())['base_url']
        yield base
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@pytest.mark.parametrize('case,endpoint,expected,model_path,expected_calls,expected_input', [
    ('disabled', '', 'queued', '', 2, 100),
    ('success', '/usage', 'delivered', '', 2, 100),
    ('http503', '/usage-fail', 'queued', '', 2, 100),
    ('bad_ack', '/usage-bad-ack', 'blocked', '', 2, 100),
    ('http401', '/usage-unauthorized', 'blocked', '', 2, 100),
    ('http429', '/usage-limited', 'queued', '', 2, 100),
    ('timeout', '/usage-timeout', 'queued', '', 2, 100),
    ('unknown_usage', '/usage', 'delivered', '/no-usage', 2, None),
    ('zero_usage', '/usage', 'delivered', '/zero-usage', 2, 0),
    ('json_retry', '/usage', 'delivered', '/json-retry', 3, 100),
])
def test_real_node_receiver_does_not_block_chat(tmp_path, monkeypatch, node_receiver,
        case, endpoint, expected, model_path, expected_calls, expected_input):
    async def identity(self):
        return '42'
    monkeypatch.setattr(Upstream, 'identity', identity)
    request_id = 'node-usage-' + case
    settings = Settings(database=str(tmp_path / 'node.db'), llm_url=node_receiver + model_path + '/v1',
        llm_model='mock-endpoint', llm_key='local-model-test',
        usage_callback_url=node_receiver + endpoint if endpoint else '', usage_callback_key='local-usage-test')
    app = create_app(settings)
    store = app.state.engine.store
    with TestClient(app) as client, httpx.Client(trust_env=False) as observer:
        started = time.monotonic()
        response = client.post('/stylist-api/chat', headers={'Authorization': 'Bearer local-user-test'},
                               json={'request_id': request_id, 'message': '你好'})
        assert response.status_code == 200, response.text
        assert time.monotonic() - started < 3  # Never waits for callback retry/ACK.
        reply = response.json()
        assert reply['message']
        deadline = time.monotonic() + 30
        while True:
            snapshot = observer.get(node_receiver + '/events').json()
            with store.connection() as conn:
                records = [dict(row) for row in conn.execute('SELECT * FROM stylist_model_usage').fetchall()]
            attempts = [r for r in snapshot['attempts'] if r['request_id'] == request_id]
            if case == 'timeout' and any(r['last_error'] == 'transport_error' for r in records):
                break
            if not endpoint or (len(attempts) >= expected_calls and all(r['state'] == expected for r in records)):
                break
            assert time.monotonic() < deadline, (records, attempts)
            time.sleep(0.1)
        assert len(records) == expected_calls
        assert all(r['state'] in {'queued', 'sending'} if case == 'timeout' else r['state'] == expected for r in records)
        assert all(r['message_version'] == reply['version'] for r in records)
        if not endpoint:
            assert attempts == []
        if endpoint == '/usage':
            received = [e for e in snapshot['events'] if e['request_id'] == request_id]
            assert len(received) == expected_calls
            assert all(e['user_id'] == '42' and e['conversation_id'] == reply['conversation_id'] for e in received)
            assert all(e['input_tokens'] == expected_input for e in received)
            assert all(e['output_tokens'] == (None if expected_input is None else 0 if expected_input == 0 else 20) for e in received)
            if case == 'json_retry':
                assert sum(e['status'] == 'invalid_output' for e in received) == 1
            assert all(e['model'] == 'mock-endpoint' and 'provider' not in e and 'actual_model' not in e for e in received)
            # Same immutable event is accepted again but never creates a second usage row at receiver.
            duplicate = observer.post(node_receiver + '/usage', json=received[0],
                                      headers={'Authorization': 'Bearer local-usage-test'})
            assert duplicate.status_code == 200
            after = observer.get(node_receiver + '/events').json()
            assert len([e for e in after['events'] if e['request_id'] == request_id]) == expected_calls
        replay = client.post('/stylist-api/chat', headers={'Authorization': 'Bearer local-user-test'},
                             json={'request_id': request_id, 'message': '你好'})
        assert replay.status_code == 200 and replay.json() == reply
        with store.connection() as conn:
            assert conn.execute('SELECT COUNT(*) AS n FROM stylist_model_usage').fetchone()['n'] == expected_calls
