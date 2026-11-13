import re
from pathlib import Path
import pytest
from stylist.schema_migrations import DIRECTORY, verify_connection

SQL = (DIRECTORY / '001_initial.sql').read_text()


def test_current_baseline_has_all_business_and_checkpoint_tables_and_indexes():
    business = (Path(__file__).resolve().parents[1] / 'stylist/schema.sql').read_text()
    tables = set(re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)', SQL))
    assert set(re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)', business)) <= tables
    assert len(tables) == 16
    assert 'task_path TEXT NOT NULL' in SQL
    assert 'blob BYTEA,' in SQL
    assert 'ALTER TABLE' not in SQL and 'DROP TABLE' not in SQL and 'PRAGMA' not in SQL
    assert 'stylist_schema_migrations' not in SQL
    assert 'stylist_messages(owner_id, conversation_id, version)' in SQL
    assert 'stylist_sessions(owner_id, updated_at)' in SQL
    from langgraph.checkpoint.postgres.base import BasePostgresSaver
    assert f"({len(BasePostgresSaver.MIGRATIONS)-1}) ON CONFLICT" in SQL


@pytest.mark.parametrize('missing', [False, True])
def test_baseline_check_is_read_only_and_detects_missing_indexes(missing):
    class Connection:
        def execute(self, query):
            assert query.startswith('SELECT')
            if 'pg_tables' in query:
                return [(n,) for n in re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)', SQL)]
            return [] if missing else [(n,) for n in re.findall(r'CREATE INDEX IF NOT EXISTS (\w+)', SQL)]
    if missing:
        with pytest.raises(ValueError): verify_connection(Connection())
    else:
        assert verify_connection(Connection()) == 16


def test_ci_requires_read_only_schema_check():
    text = (Path(__file__).resolve().parents[1] / 'deploy/ci/deploy.sh').read_text()
    assert 'stylist.migrate --check --environment "$environment"' in text


def test_ci_deployment_is_read_only():
    root = Path(__file__).resolve().parents[1]
    text = (root / 'deploy/ci/deploy.sh').read_text()
    assert '--create-database' not in text
    assert 'STYLIST_REQUIRE_MIGRATIONS=true' in text
    assert 'stylist.migrate --check' in text
    assert "os.getenv('STYLIST_REQUIRE_MIGRATIONS'" in (root / 'stylist/migrate.py').read_text()


def test_ci_store_only_checks_schema(monkeypatch):
    from stylist.store import Store
    import psycopg
    import stylist.schema_migrations as schema
    monkeypatch.setenv('STYLIST_REQUIRE_MIGRATIONS', 'true')
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
    conn = Connection()
    monkeypatch.setattr(psycopg, 'connect', lambda _: conn)
    checked = []
    monkeypatch.setattr(schema, 'verify_connection', lambda c: checked.append(c))
    monkeypatch.setattr(Store, 'connection', lambda _: pytest.fail('DDL connection must not be opened'))
    Store('postgresql://unused/aicloset_stylist_test')
    assert checked == [conn]


def test_prod_baseline_accepts_only_prod_database_and_uses_selects(monkeypatch):
    import stylist.schema_migrations as schema
    parameters = []
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, query):
            assert query.startswith('SELECT')
            pattern = r'CREATE TABLE IF NOT EXISTS (\w+)' if 'pg_tables' in query else r'CREATE INDEX IF NOT EXISTS (\w+)'
            return [(name,) for name in re.findall(pattern, SQL)]
    monkeypatch.setattr(schema.psycopg, 'connect', lambda **kwargs: (parameters.append(kwargs) or Connection()))
    assert schema.run('postgresql://fixture@localhost/aicloset_stylist_prod', 'prod') == 16
    assert parameters[0]['dbname'] == 'aicloset_stylist_prod'
    with pytest.raises(ValueError):
        schema.run('postgresql://fixture@localhost/aicloset_stylist_test', 'prod')
    assert len(parameters) == 1
