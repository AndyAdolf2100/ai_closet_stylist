from contextlib import contextmanager

import pytest

from stylist.config import Settings
from stylist.tracing import Tracing, observation, text


def test_trace_text_never_exports_bearer_keys_or_images():
    raw = 'Bearer secret.jwt.value sk-lf-aabbcc sk-test_long_secret_value data:image/png;base64,abc'
    rendered = text(raw)
    assert 'secret.jwt.value' not in rendered and 'aabbcc' not in rendered
    assert 'test_long_secret_value' not in rendered and 'base64' not in rendered


def test_tracing_disabled_does_not_import_or_connect(monkeypatch):
    tracer = Tracing(Settings())
    assert tracer.client is None
    with tracer.bind(), observation('fixture') as span:
        span.update(output='done')
    tracer.close()


def test_sdk_failures_do_not_change_business_results():
    tracer = Tracing(Settings())
    class Broken:
        def start_as_current_observation(self, **values):
            raise RuntimeError('fixture')
    tracer.client = Broken()
    with tracer.bind(), observation('fixture'):
        result = 'business completed'
    assert result == 'business completed'


def test_business_failure_preserved_and_observation_closed():
    events = []
    class Span:
        def update(self, **values):
            events.append(values)
    class Client:
        @contextmanager
        def start_as_current_observation(self, **values):
            events.append(values)
            try:
                yield Span()
            finally:
                events.append('closed')
    tracer = Tracing(Settings())
    tracer.client = Client()
    with pytest.raises(ValueError, match='business-error'):
        with tracer.bind(), observation('fixture'):
            raise ValueError('business-error')
    assert events[-1] == 'closed'
    assert events[-2] == {'level':'ERROR','status_message':'ValueError'}


def test_credentials_not_in_settings_repr(monkeypatch):
    monkeypatch.setenv('LANGFUSE_PUBLIC_KEY','fixture-public')
    monkeypatch.setenv('LANGFUSE_SECRET_KEY','fixture-secret')
    settings = Settings.load()
    assert settings.langfuse_enabled
    assert 'fixture-secret' not in repr(settings) and 'fixture-public' not in repr(settings)
    monkeypatch.setenv('LANGFUSE_TRACING_ENABLED','false')
    assert not Settings.load().langfuse_enabled
