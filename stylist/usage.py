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
from threading import RLock
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


class UsageTokens:
    """Validated user credentials, memory only and scoped to one application instance."""
    def __init__(self):
        self._values = {}
        self._lock = RLock()

    def register(self, owner, authorization):
        if isinstance(authorization, str) and authorization.startswith('Bearer ') and authorization[7:].strip():
            with self._lock:
                self._values[str(owner)] = authorization

    def owners(self):
        with self._lock:
            return tuple(self._values)

    def get(self, owner):
        with self._lock:
            return self._values.get(str(owner))

    def invalidate(self, owner, authorization):
        with self._lock:
            if self._values.get(str(owner)) == authorization:
                self._values.pop(str(owner), None)


@dataclass
class UsageContext:
    store: object
    settings: object
    owner: str
    conversation: str
    request: str
    business_action: str = 'unknown'

    def begin(self, model=None):
        event = {
            'event_id': str(uuid.uuid4()), 'occurred_at': datetime.now(timezone.utc).isoformat(),
            'environment': self.settings.usage_environment,
            'conversation_id': self.conversation, 'request_id': self.request,
            'business_action': self.business_action,
            'model': model if model is not None else self.settings.llm_model,
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
        event.update(input_tokens=integer(usage.get('prompt_tokens', usage.get('input_tokens'))),
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
    def __init__(self, store, settings, transport=None, tokens=None):
        self.store, self.settings, self.transport = store, settings, transport
        self.tokens = tokens if tokens is not None else UsageTokens()
        if settings.usage_environment not in {'development', 'test', 'production'}:
            raise ValueError('Usage environment must be development, test or production')
        if settings.usage_callback_url:
            url = urlsplit(settings.usage_callback_url)
            if (url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password
                    or url.fragment or url.query):
                raise ValueError('Usage callback requires a fixed HTTP(S) URL')
            if url.scheme != 'https' and url.hostname not in {'localhost', '127.0.0.1', '::1'}:
                raise ValueError('Usage callback requires HTTPS outside loopback')

    def claim(self):
        owners = self.tokens.owners()
        if not owners:
            return None
        now, lease = time.time(), str(uuid.uuid4())
        with self.store.connection() as conn:
            if not self.store.postgres and not self.store.mysql:
                conn.execute('BEGIN IMMEDIATE')
            # Query per owner avoids DB parameter limits and starving authenticated users.
            candidates = []
            for owner in owners:
                candidate = conn.execute('SELECT * FROM stylist_model_usage WHERE owner_id=? AND '
                    '((state=? AND next_attempt<=?) OR (state=? AND lease_until<?)) '
                    'ORDER BY created_at LIMIT 1', (owner, 'queued', now, 'sending', now)).fetchone()
                if candidate:
                    candidates.append(candidate)
            row = min(candidates, key=lambda item: item['created_at']) if candidates else None
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
        authorization = self.tokens.get(row['owner_id'])
        if not authorization:
            await asyncio.to_thread(self.settle, row, lease, 'queued', 'awaiting_user_token')
            return False
        payload = json.loads(row['payload_json'])
        # Historical identity is retained locally; Server derives identity from Authorization.
        payload.pop('user_id', None)
        state, error = 'queued', 'transport_error'
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False,
                                         transport=self.transport) as client:
                response = await client.post(self.settings.usage_callback_url,
                    headers={'Authorization': authorization,
                             'Idempotency-Key': row['event_id']},
                    json=payload)
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
            elif response.status_code in {401, 403}:
                self.tokens.invalidate(row['owner_id'], authorization)
                error = 'awaiting_user_token'
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
