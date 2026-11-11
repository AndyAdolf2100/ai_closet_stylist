"""Optional Langfuse tracing, with credentials and images excluded from observations."""
import logging
import re
from contextlib import contextmanager
from contextvars import ContextVar

logger = logging.getLogger(__name__)
_current = ContextVar('stylist_tracing', default=None)


def text(value):
    value = str(value or '')[:6000]
    value = re.sub(r'(?i)Bearer\s+[A-Za-z0-9._~+/-]+=*', 'Bearer [redacted]', value)
    value = re.sub(r'(?:sk-lf-|pk-lf-)[a-zA-Z0-9-]+', '[redacted]', value)
    value = re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[redacted-jwt]', value)
    value = re.sub(r'(?i)(?:sk-)[A-Za-z0-9_-]{12,}', '[redacted-key]', value)
    value = re.sub(r'data:image/[^\s]+', '[image omitted]', value)
    return value


class Observation:
    def __init__(self, value=None):
        self.value = value

    def update(self, **values):
        if self.value:
            try:
                self.value.update(**values)
            except Exception:
                logger.warning('tracing_update_unavailable')


class Tracing:
    def __init__(self, settings):
        self.client = None
        if not settings.langfuse_enabled:
            return
        if not (settings.langfuse_public_key and settings.langfuse_secret_key and settings.langfuse_base_url):
            logger.warning('langfuse_not_configured')
            return
        try:
            from langfuse import Langfuse
            self.client = Langfuse(public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key, base_url=settings.langfuse_base_url,
                environment=settings.langfuse_environment, timeout=3, flush_at=10, flush_interval=2)
        except Exception:
            logger.warning('langfuse_initialization_unavailable')

    @contextmanager
    def bind(self):
        token = _current.set(self)
        try:
            yield
        finally:
            _current.reset(token)

    def close(self):
        if self.client:
            try:
                self.client.shutdown()
            except Exception:
                logger.warning('langfuse_shutdown_unavailable')


@contextmanager
def observation(name, *, kind='span', **values):
    tracer = _current.get()
    if not tracer or not tracer.client:
        yield Observation()
        return
    manager = None
    try:
        manager = tracer.client.start_as_current_observation(name=name, as_type=kind, **values)
        value = manager.__enter__()
    except Exception:
        logger.warning('langfuse_observation_unavailable')
        yield Observation()
        return
    obs = Observation(value)
    try:
        yield obs
    except BaseException as exc:
        obs.update(level='ERROR', status_message=getattr(exc, 'code', type(exc).__name__))
        raise
    finally:
        try:
            manager.__exit__(None, None, None)
        except Exception:
            logger.warning('langfuse_export_unavailable')
