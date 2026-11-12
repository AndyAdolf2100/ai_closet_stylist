"""Deployment-only environment checks. Errors never include connection secrets."""
from .database_preflight import connection_parameters

DATABASES = {'dev': 'aicloset_stylist', 'test': 'aicloset_stylist_test'}


def validate(settings, environment):
    if environment not in DATABASES:
        raise ValueError('Deployment environment must be test or dev')
    server = f'https://aicloset-{environment}.wxbjq.top'
    if settings.server_url != server:
        raise ValueError('Server URL does not match selected environment')
    if settings.mcp_url != server + '/mcp':
        raise ValueError('MCP URL does not match selected environment')
    if settings.usage_callback_url != server + '/api/internal/stylist/model-usage':
        raise ValueError('Usage callback does not match selected environment')
    # This settlement label is intentionally shared; it is not the database selector.
    if settings.usage_environment != 'test':
        raise ValueError('Settlement environment must retain the configured test label')
    if not settings.database:
        raise ValueError('Deployment database is missing')
    for dsn in filter(None, [settings.database, settings.checkpoint_database]):
        try:
            connection_parameters(dsn, target=DATABASES[environment])
        except Exception:
            raise ValueError('PostgreSQL database does not match selected environment') from None
    if not (settings.llm_url and settings.llm_model and settings.llm_key):
        raise ValueError('Model configuration is missing')
    if not settings.ops_mysql_dsn:
        raise ValueError('MySQL ops configuration is missing')
    if settings.langfuse_enabled:
        raise ValueError('Tracing must remain disabled')
