"""Persistent metering of direct conversational model calls, never image/MCP billing."""
import asyncio
import json
import logging
import random
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx

context = ContextVar('stylist_model_usage', default=None)
logger = logging.getLogger(__name__)


def integer(value):
    return value if type(value) is int and value >= 0 else None


def action(plan):
    if getattr(plan, 'conversation_only', False):
        return 'chat'
    if getattr(plan, 'weather_only', False):
        return 'weather_consult'
    if getattr(plan, 'upload_intent', None):
        return 'wardrobe_upload_intent'
    if getattr(plan, 'avatar_intent', None):
        return 'avatar_intent'
    return {'consult': 'style_consult', 'recommend': 'outfit_recommend',
            'modify': 'outfit_modify', 'weekly': 'weekly_plan'}.get(getattr(plan, 'mode', ''), 'unknown')


@dataclass
class UsageContext:
    store: object
    settings: object
    owner: str
    conversation: str
    request: str
    business_action: str = 'unknown'

    def begin(self):
        event = {
            'event_id': str(uuid.uuid4()), 'occurred_at': datetime.now(timezone.utc).isoformat(),
            'environment': self.settings.usage_environment, 'user_id': self.owner,
            'conversation_id': self.conversation, 'request_id': self.request,
            'business_action': self.business_action,
            'provider': self.settings.usage_provider or urlsplit(self.settings.llm_url).hostname or 'unknown',
            'model': self.settings.llm_model, 'actual_model': None,
            'input_tokens': None, 'output_tokens': None, 'cached_input_tokens': None,
            'reasoning_tokens': None, 'status': 'unknown',
        }
        # Fail before calling the supplier if the accounting ledger cannot be written.
        with self.store.connection() as conn:
            conn.execute('INSERT INTO stylist_model_usage '
                         '(event_id,owner_id,conversation_id,request_id,payload_json,state,created_at) '
                         'VALUES(?,?,?,?,?,?,?)',
                         (event['event_id'], self.owner, self.conversation, self.request,
                          json.dumps(event), 'pending', time.time()))
        return event

    def finish(self, event, envelope, status):
        envelope = envelope if isinstance(envelope, dict) else {}
        usage = envelope.get('usage')
        usage = usage if isinstance(usage, dict) else {}
        def detail(key, field):
            value = usage.get(key)
            return integer(value.get(field)) if isinstance(value, dict) else None
        actual = envelope.get('model')
        event.update(actual_model=actual[:256] if isinstance(actual, str) else None,
                     input_tokens=integer(usage.get('prompt_tokens', usage.get('input_tokens'))),
                     output_tokens=integer(usage.get('completion_tokens', usage.get('output_tokens'))),
                     cached_input_tokens=detail('prompt_tokens_details', 'cached_tokens'),
                     reasoning_tokens=detail('completion_tokens_details', 'reasoning_tokens'),
                     status=status, business_action=self.business_action)
        supplier_id = envelope.get('id')
        supplier_id = supplier_id[:256] if isinstance(supplier_id, str) else None
        try:
            with self.store.connection() as conn:
                conn.execute('UPDATE stylist_model_usage SET payload_json=?,state=?,provider_request_id=? '
                             'WHERE event_id=?',
                             (json.dumps(event), 'queued', supplier_id, event['event_id']))
        except Exception:
            logger.error('Model usage result could not be saved: event_id=%s; pending requires reconciliation',
                         event['event_id'])
            raise



class UsageSender:
    def __init__(self, store, settings, transport=None):
        self.store, self.settings, self.transport = store, settings, transport
        if settings.usage_environment not in {'development', 'test', 'production'}:
            raise ValueError('Usage environment must be development, test or production')
        if settings.usage_callback_url:
            url = urlsplit(settings.usage_callback_url)
            if (url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password
                    or url.fragment or url.query or not settings.usage_callback_key):
                raise ValueError('Usage callback requires a fixed HTTP(S) URL and service key')
            if url.scheme != 'https' and url.hostname not in {'localhost', '127.0.0.1', '::1'}:
                raise ValueError('Usage callback requires HTTPS outside loopback')

    def claim(self):
        now, lease = time.time(), str(uuid.uuid4())
        with self.store.connection() as conn:
            if not self.store.postgres and not self.store.mysql:
                conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM stylist_model_usage WHERE '
                               '(state=? AND next_attempt<=?) OR (state=? AND lease_until<?) '
                               'ORDER BY created_at LIMIT 1', ('queued', now, 'sending', now)).fetchone()
            if not row:
                return None
            changed = conn.execute('UPDATE stylist_model_usage SET state=?,lease=?,lease_until=?,attempts=attempts+1 '
                                   'WHERE event_id=? AND ((state=? AND next_attempt<=?) OR '
                                   '(state=? AND lease_until<?))',
                                   ('sending', lease, now + 60, row['event_id'], 'queued', now, 'sending', now))
            if changed.rowcount != 1:
                return None
            return dict(row), lease

    def settle(self, row, lease, state, error):
        delay = min(3600, 2 ** min(row['attempts'] + 1, 11)) + random.uniform(0, 2)
        with self.store.connection() as conn:
            conn.execute('UPDATE stylist_model_usage SET state=?,last_error=?,next_attempt=?,lease_until=0 '
                         'WHERE event_id=? AND lease=? AND state=?',
                         (state, error, time.time() + delay, row['event_id'], lease, 'sending'))

    async def send_one(self):
        if not self.settings.usage_callback_url:
            return False
        claimed = await asyncio.to_thread(self.claim)
        if not claimed:
            return False
        row, lease = claimed
        state, error = 'queued', 'transport_error'
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False,
                                         transport=self.transport) as client:
                response = await client.post(self.settings.usage_callback_url,
                    headers={'Authorization': 'Bearer ' + self.settings.usage_callback_key,
                             'Idempotency-Key': row['event_id']},
                    json=json.loads(row['payload_json']))
            if response.status_code == 200:
                try:
                    ack = response.json()
                except ValueError:
                    ack = None
                if (isinstance(ack, dict) and ack.get('accepted') is True
                        and ack.get('event_id') == row['event_id']):
                    state, error = 'delivered', ''
                else:
                    state, error = 'blocked', 'invalid_ack'
            elif response.status_code in {408, 429} or response.status_code >= 500:
                error = 'retryable_http'
            else:
                state, error = 'blocked', 'rejected_http'
        except httpx.HTTPError:
            pass
        await asyncio.to_thread(self.settle, row, lease, state, error)
        if state == 'blocked':
            logger.error('Model usage delivery blocked: event_id=%s code=%s', row['event_id'], error)
        return True

    async def run(self):
        while True:
            try:
                sent = await self.send_one()
            except Exception:
                logger.error('Model usage delivery unavailable; retained for retry')
                sent = False
            await asyncio.sleep(0.1 if sent else 5)
