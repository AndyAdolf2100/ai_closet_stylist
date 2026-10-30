import pytest

from stylist.database_preflight import connection_parameters


@pytest.mark.parametrize('dsn', [
    'var/stylist.sqlite3',
    'mysql://fixture@localhost/aicloset_stylist',
    'postgresql://fixture@localhost/aicloset_test',
    'postgresql://REPLACE_USER@localhost/aicloset_stylist',
])
def test_preflight_rejects_legacy_or_unconfigured_database_before_connecting(dsn):
    with pytest.raises(ValueError):
        connection_parameters(dsn)


def test_preflight_preserves_ssl_and_bounds_connection_timeout():
    params = connection_parameters('postgresql://fixture@localhost/aicloset_stylist?sslmode=require&connect_timeout=100')
    assert params['dbname'] == 'aicloset_stylist'
    assert params['sslmode'] == 'require'
    assert params['connect_timeout'] == '5'


def test_error_redacts_credentials_and_retains_network_reason():
    from stylist.database_preflight import safe_error

    dsn = "postgresql://fixture_user:secret%40pass@db.invalid/aicloset_stylist"
    message = safe_error(Exception("timeout " + dsn + " password secret@pass user fixture_user"), dsn)
    assert "timeout" in message
    assert "secret" not in message and "fixture_user" not in message


def test_creation_uses_maintenance_catalog_before_target_connection(monkeypatch):
    from stylist.database_preflight import check

    connections, statements = [], []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query, params=None):
            self.query = str(query)
            statements.append(self.query)
            return self

        def fetchone(self):
            return (True,) if "has_schema_privilege" in self.query else None

        def __iter__(self):
            return iter([])

    def connect(**params):
        connections.append(params["dbname"])
        return Connection()

    monkeypatch.setattr("stylist.database_preflight.psycopg.connect", connect)
    check("postgresql://fixture@localhost/aicloset_stylist", create=True)
    assert connections == ["postgres", "aicloset_stylist"]
    assert any("CREATE DATABASE" in query for query in statements)
