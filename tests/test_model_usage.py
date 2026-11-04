import asyncio
import json
from dataclasses import replace

import httpx
import pytest
from pydantic import BaseModel

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.llm import LanguageModel
from stylist.models import ChatRequest, Draft, Plan
from stylist.store import Store
from stylist.usage import UsageContext, UsageSender, context


class Answer(BaseModel):
    ok: bool


def rows(store):
    with store.connection() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM stylist_model_usage ORDER BY created_at').fetchall()]


def config(tmp_path):
    return Settings(database=str(tmp_path / 'state.db'), llm_url='https://model.example',
                    llm_key='model-secret', llm_model='endpoint-1',
                    usage_callback_url='https://server.example/usage', usage_callback_key='service-secret')


def envelope(content='{"ok":true}', usage=None):
    return {'choices': [{'message': {'content': content}}], 'model': 'actual-model',
            'usage': usage if usage is not None else {'prompt_tokens': 100, 'completion_tokens': 20,
                'prompt_tokens_details': {'cached_tokens': 10}, 'completion_tokens_details': {'reasoning_tokens': 3}}}


async def invoke(store, settings, transport, owner='1', prompt='style'):
    token = context.set(UsageContext(store, settings, owner, 'conv-' + owner, 'req-' + owner))
    try:
        return await LanguageModel(settings, transport).generate(prompt, {'message': 'private body'}, Answer)
    finally:
        context.reset(token)


@pytest.mark.asyncio
async def test_validation_retry_records_both_calls_without_content_or_secrets(tmp_path):
    settings = config(tmp_path)
    store = Store(settings.database)
    responses = iter([envelope('not json'), envelope()])
    await invoke(store, settings, httpx.MockTransport(lambda r: httpx.Response(200, json=next(responses))))
    records = rows(store)
    assert len(records) == 2 and len({r['event_id'] for r in records}) == 2
    events = [json.loads(r['payload_json']) for r in records]
    assert [e['status'] for e in events] == ['invalid_output', 'succeeded']
    assert all(e['input_tokens'] == 100 and e['cached_input_tokens'] == 10 for e in events)
    assert all(e['model'] == 'endpoint-1' and e['reasoning_tokens'] == 3 for e in events)
    assert all('provider' not in e and 'actual_model' not in e for e in events)
    assert all(secret not in str(records) for secret in ['private body', 'model-secret', 'service-secret'])


@pytest.mark.asyncio
async def test_unknown_timeout_and_healthcheck_exclusion(tmp_path):
    settings = config(tmp_path)
    store = Store(settings.database)
    def timeout(request):
        raise httpx.ReadTimeout('private error', request=request)
    with pytest.raises(StylistError, match='model_timeout'):
        await invoke(store, settings, httpx.MockTransport(timeout))
    event = json.loads(rows(store)[0]['payload_json'])
    assert event['status'] == 'timeout' and event['input_tokens'] is None
    await invoke(store, settings, httpx.MockTransport(lambda r: httpx.Response(200, json=envelope())), prompt='check')
    assert len(rows(store)) == 1


@pytest.mark.asyncio
async def test_concurrent_users_are_isolated_and_missing_usage_stays_null(tmp_path):
    settings = config(tmp_path)
    store = Store(settings.database)
    async def handler(request):
        await asyncio.sleep(0.01)
        return httpx.Response(200, json=envelope(usage={'prompt_tokens': True, 'completion_tokens': -1}))
    await asyncio.gather(*(invoke(store, settings, httpx.MockTransport(handler), str(i)) for i in range(1, 5)))
    for row in rows(store):
        event = json.loads(row['payload_json'])
        assert event['conversation_id'] == 'conv-' + event['user_id']
        assert event['request_id'] == 'req-' + event['user_id']
        assert event['input_tokens'] is None and event['output_tokens'] is None
    assert context.get() is None


@pytest.mark.asyncio
async def test_persistent_delivery_retry_ack_and_no_duplicate_claim(tmp_path):
    settings = config(tmp_path)
    store = Store(settings.database)
    await invoke(store, settings, httpx.MockTransport(lambda r: httpx.Response(200, json=envelope())))
    seen = []
    def handler(request):
        data = json.loads(request.content)
        seen.append(data)
        assert request.headers['Authorization'] == 'Bearer service-secret'
        assert request.headers['Idempotency-Key'] == data['event_id']
        if len(seen) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={'accepted': True, 'event_id': data['event_id']})
    sender = UsageSender(store, settings, httpx.MockTransport(handler))
    await sender.send_one()
    assert rows(store)[0]['state'] == 'queued'
    with store.connection() as conn:
        conn.execute('UPDATE stylist_model_usage SET next_attempt=0')
    restarted = UsageSender(Store(settings.database), settings, httpx.MockTransport(handler))
    await asyncio.gather(restarted.send_one(), sender.send_one())
    assert len(seen) == 2 and seen[0] == seen[1]
    assert rows(store)[0]['state'] == 'delivered'
    assert not await restarted.send_one()


@pytest.mark.asyncio
@pytest.mark.parametrize('response', [httpx.Response(401), httpx.Response(302, headers={'Location': 'https://other/'}),
    httpx.Response(200, json={'accepted': True, 'event_id': 'wrong'})])
async def test_bad_ack_or_credentials_block_without_following_redirect(tmp_path, response):
    settings = config(tmp_path)
    store = Store(settings.database)
    await invoke(store, settings, httpx.MockTransport(lambda r: httpx.Response(200, json=envelope())))
    sender = UsageSender(store, settings, httpx.MockTransport(lambda r: response))
    await sender.send_one()
    assert rows(store)[0]['state'] == 'blocked'
    assert not await sender.send_one()


@pytest.mark.asyncio
async def test_engine_links_message_and_replay_adds_no_usage(tmp_path):
    settings = replace(config(tmp_path), usage_callback_url='')
    store = Store(settings.database)
    plan = Plan(mode='consult', conversation_only=True, use_inventory=False, clarification='你好')
    calls = []
    def handler(request):
        calls.append(request)
        value = plan if len(calls) == 1 else Draft(message="你好，今天想聊什么？")
        return httpx.Response(200, json=envelope(value.model_dump_json()))
    class Upstream:
        async def identity(self):
            return '42'
    engine = Stylist(settings, store, LanguageModel(settings, httpx.MockTransport(handler)))
    request = ChatRequest(message='你好', request_id='usage-replay-001')
    reply = await engine.chat(Upstream(), request)
    count = len(rows(store))
    assert count >= 1
    replay = await engine.chat(Upstream(), request)
    assert replay == reply and len(rows(store)) == count
    for row in rows(store):
        assert row['owner_id'] == '42' and row['conversation_id'] == reply.conversation_id
        assert row['message_version'] == reply.version
    assert context.get() is None
    assert not await UsageSender(store, settings).send_one()


@pytest.mark.asyncio
async def test_cancelled_model_call_retains_unknown_cost(tmp_path):
    settings = config(tmp_path)
    store = Store(settings.database)
    started = asyncio.Event()
    async def handler(request):
        started.set()
        await asyncio.Event().wait()
    task = asyncio.create_task(invoke(store, settings, httpx.MockTransport(handler)))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    record = rows(store)[0]
    assert record['state'] == 'queued'
    assert json.loads(record['payload_json'])['status'] == 'cancelled'


@pytest.mark.asyncio
async def test_http_failure_usage_is_retained_and_pending_calls_not_sent(tmp_path):
    settings = config(tmp_path)
    store = Store(settings.database)
    with pytest.raises(StylistError, match='model_http_500'):
        await invoke(store, settings, httpx.MockTransport(lambda r: httpx.Response(500, json=envelope())))
    event = json.loads(rows(store)[0]['payload_json'])
    assert event['input_tokens'] == 100 and event['status'] == 'http_error'
    with store.connection() as conn:
        conn.execute('UPDATE stylist_model_usage SET state=?', ('delivered',))
    UsageContext(store, settings, '1', 'c', 'r').begin()  # Simulates crash before a response is saved.
    assert not await UsageSender(store, settings).send_one()


@pytest.mark.asyncio
async def test_ledger_failure_prevents_supplier_call(tmp_path, monkeypatch):
    settings = config(tmp_path)
    store = Store(settings.database)
    def broken_begin(self, model=None):
        raise RuntimeError('ledger unavailable')
    monkeypatch.setattr(UsageContext, 'begin', broken_begin)
    def handler(request):
        pytest.fail('Supplier must not run without durable pending record')
    with pytest.raises(RuntimeError, match='ledger unavailable'):
        await invoke(store, settings, httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_expired_delivery_lease_can_be_reclaimed(tmp_path):
    settings = config(tmp_path)
    store = Store(settings.database)
    await invoke(store, settings, httpx.MockTransport(lambda r: httpx.Response(200, json=envelope())))
    sender = UsageSender(store, settings)
    record, stale_lease = sender.claim()
    assert sender.claim() is None
    with store.connection() as conn:
        conn.execute('UPDATE stylist_model_usage SET lease_until=0')
    new_record, new_lease = UsageSender(Store(settings.database), settings).claim()
    assert new_record['event_id'] == record['event_id'] and new_lease != stale_lease
    sender.settle(record, stale_lease, 'delivered', '')
    assert rows(store)[0]['state'] == 'sending'
    sender.settle(new_record, new_lease, 'delivered', '')
    assert rows(store)[0]['state'] == 'delivered'


@pytest.mark.parametrize('url,key', [('https://server.example/usage', ''),
    ('http://server.example/usage', 'key'), ('https://user:secret@server.example/usage', 'key'),
    ('https://server.example/usage?secret=bad', 'key')])
def test_callback_configuration_is_service_only(tmp_path, url, key):
    settings = replace(config(tmp_path), usage_callback_url=url, usage_callback_key=key)
    with pytest.raises(ValueError):
        UsageSender(Store(settings.database), settings)


@pytest.mark.asyncio
async def test_callback_timeout_is_queued_without_new_model_call(tmp_path):
    settings = config(tmp_path)
    store = Store(settings.database)
    await invoke(store, settings, httpx.MockTransport(lambda r: httpx.Response(200, json=envelope())))
    def timeout(request):
        raise httpx.ReadTimeout('mock callback timeout', request=request)
    sender = UsageSender(store, settings, httpx.MockTransport(timeout))
    await sender.send_one()
    assert len(rows(store)) == 1 and rows(store)[0]['state'] == 'queued'


@pytest.mark.asyncio
async def test_configured_model_id_is_sent_verbatim_without_supplier_prefix(tmp_path):
    settings = replace(config(tmp_path), llm_model='ep-20260910130610-tjnpm')
    store = Store(settings.database)
    await invoke(store, settings, httpx.MockTransport(lambda r: httpx.Response(200, json=envelope())))
    event = json.loads(rows(store)[0]['payload_json'])
    assert event['model'] == 'ep-20260910130610-tjnpm'
    assert 'provider' not in event and 'actual_model' not in event


@pytest.mark.asyncio
async def test_multiple_model_instances_use_each_actual_request_model(tmp_path):
    settings = config(tmp_path)
    store = Store(settings.database)
    token = context.set(UsageContext(store, settings, '1', 'same-conversation', 'same-request'))
    try:
        for name in ['endpoint-a', 'model-b']:
            model = LanguageModel(replace(settings, llm_model=name),
                httpx.MockTransport(lambda r: httpx.Response(200, json=envelope())))
            await model.generate('style', {}, Answer)
    finally:
        context.reset(token)
    events = [json.loads(row['payload_json']) for row in rows(store)]
    assert [e['model'] for e in events] == ['endpoint-a', 'model-b']
    assert len({e['event_id'] for e in events}) == 2
    assert {e['request_id'] for e in events} == {'same-request'}


@pytest.mark.asyncio
async def test_existing_queued_event_payload_is_not_rewritten(tmp_path):
    settings = config(tmp_path)
    store = Store(settings.database)
    await invoke(store, settings, httpx.MockTransport(lambda r: httpx.Response(200, json=envelope())))
    event = json.loads(rows(store)[0]['payload_json'])
    event.update(provider='legacy-provider', actual_model='legacy-model')
    with store.connection() as conn:
        conn.execute('UPDATE stylist_model_usage SET payload_json=? WHERE event_id=?',
                     (json.dumps(event), event['event_id']))
    def receive(request):
        assert json.loads(request.content) == event
        return httpx.Response(200, json={'accepted': True, 'event_id': event['event_id']})
    await UsageSender(store, settings, httpx.MockTransport(receive)).send_one()
    assert rows(store)[0]['state'] == 'delivered'
