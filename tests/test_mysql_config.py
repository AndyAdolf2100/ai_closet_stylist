import pytest

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.mysql import mysql_connection


def test_local_database_config_and_env_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv("STYLIST_DATABASE", raising=False)
    monkeypatch.delenv("STYLIST_CHECKPOINT_DATABASE", raising=False)
    path = tmp_path / "local.yaml"
    path.write_text("database: mysql://example:private-password@127.0.0.1/stylist_local\n")
    monkeypatch.setenv("STYLIST_LOCAL_CONFIG", str(path))
    settings = Settings.load()
    assert settings.database.startswith("mysql://")
    assert "private-password" not in repr(settings)
    monkeypatch.setenv("STYLIST_DATABASE", "var/override.sqlite3")
    assert Settings.load().database == "var/override.sqlite3"


@pytest.mark.parametrize("database", ["aicloset_dev", "aicloset_test", "mysql", "sys", "information_schema"])
def test_mysql_rejects_legacy_and_system_databases_before_connecting(database):
    with pytest.raises(ValueError, match="独立数据库"):
        with mysql_connection("mysql://unused:unused@127.0.0.1/" + database):
            pytest.fail("must reject before connecting")


def test_mysql_cannot_silently_keep_sqlite_checkpoints():
    from types import SimpleNamespace

    with pytest.raises(ValueError, match="MySQL 检查点"):
        Stylist(Settings(checkpoint_database="var/old.checkpoints"),
                SimpleNamespace(mysql=True, postgres=False), None)
