"""Offline checks for deployment secrets, login opt-in and distributable artifacts."""
import json
import os
import tarfile

import httpx
import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from scripts.package_deployment import FILES, package, public_bootstrap
from scripts.prepare_docker_config import prepare
from stylist.auth import LoginRequest, login
from stylist.config import Settings
from stylist.errors import StylistError


@pytest.fixture
def legacy(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
    pem = key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    (tmp_path / "login.pem").write_bytes(pem)
    raw = {
        "llm": {"default_model_id": "chosen", "models": [
            {"id": "other", "api_key": "unused", "model": "other"},
            {"id": "chosen", "base_url": "https://model.invalid/v1", "model": "fixture-model",
             "api_key": "synthetic$#'\\key"},
        ]},
        "mcp_tool_routing": {"servers": [
            {"enabled": False, "url": "https://ignored.invalid/mcp"},
            {"enabled": True, "url": "https://upstream.invalid/mcp"},
        ]},
        "upstream_auth": {"public_key_path": "login.pem", "app_version": "1.2.0"},
        "conversation_store": {"password": "must-not-export-db-password"},
    }
    path = tmp_path / "legacy.yaml"
    path.write_text(yaml.safe_dump(raw))
    return path, pem


def test_explicit_config_import_selects_current_model_and_does_not_export_other_secrets(legacy, tmp_path, capsys):
    path, pem = legacy
    output = tmp_path / "config"
    prepare(path, output)
    text = (output / "deploy.env").read_text()
    assert "STYLIST_LLM_MODEL=fixture-model\n" in text
    assert "STYLIST_LLM_KEY=synthetic$#'\\key\n" in text
    assert "STYLIST_MCP_URL=https://upstream.invalid/mcp\n" in text
    assert "must-not-export" not in text and "unused" not in text and "ignored.invalid" not in text
    assert "STYLIST_ALLOW_MOBILE_LOGIN=true\n" in text
    assert (output / "login-public.pem").read_bytes() == pem
    assert os.stat(output / "deploy.env").st_mode & 0o777 == 0o600
    assert os.stat(output / "login-public.pem").st_mode & 0o777 == 0o644
    assert capsys.readouterr().out == ""
    with pytest.raises(ValueError, match="refusing to overwrite"):
        prepare(path, output)


def test_invalid_import_does_not_write_partial_private_config(legacy, tmp_path):
    path, _ = legacy
    raw = yaml.safe_load(path.read_text())
    raw["llm"]["models"][1]["api_key"] = "synthetic\nINJECTED=value"
    path.write_text(yaml.safe_dump(raw))
    output = tmp_path / "config"
    with pytest.raises(ValueError, match="Cannot import"):
        prepare(path, output)
    assert not output.exists()


def test_release_archive_excludes_local_config_databases_and_unlisted_deployment_secrets(tmp_path):
    source = tmp_path / "source"
    for name in FILES:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    for name in ["config/deploy.env", "var/stylist.sqlite3", "deploy/docker/credentials.env",
                 "stylist/.env", "stylist/__pycache__/main.pyc"]:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("must-not-archive-secret")
    (source / "stylist/main.py").write_text("# fixture runtime")
    output = tmp_path / "release.tar.gz"
    package(output, root=source)
    with tarfile.open(output) as archive:
        names = archive.getnames()
        assert "aicloset-assistant/stylist/main.py" in names
        assert "aicloset-assistant/compose.yaml" in names
        assert not any("config/deploy.env" in n or "credentials.env" in n or "sqlite3" in n or "__pycache__" in n
                       or n.endswith("/.env") for n in names)
    assert output.with_name(output.name + ".sha256").exists()


def test_public_bootstrap_contains_endpoints_and_public_key_but_never_the_model_secret(legacy):
    path, pem = legacy
    files = public_bootstrap(path)
    defaults = files["deploy/docker/runtime.defaults"].decode()
    assert 'fixture-model' in defaults and 'https://upstream.invalid/mcp' in defaults
    assert 'synthetic' not in defaults and 'STYLIST_LLM_KEY' not in defaults and 'must-not-export' not in defaults
    assert files['deploy/docker/login-public.pem'] == pem


def test_invalid_bootstrap_does_not_replace_a_previous_good_release(legacy, tmp_path):
    path, _ = legacy
    raw = yaml.safe_load(path.read_text())
    raw['llm']['models'][1]['base_url'] = 'https://model.invalid/v1?api_key=must-not-export'
    path.write_text(yaml.safe_dump(raw))
    source = tmp_path / 'source'
    for name in FILES:
        item = source / name
        item.parent.mkdir(parents=True, exist_ok=True)
        item.write_text('fixture')
    output = tmp_path / 'previous.tar.gz'
    output.write_bytes(b'previous-good-release')
    with pytest.raises(ValueError, match='no private configuration'):
        package(output, root=source, bootstrap_config=path)
    assert output.read_bytes() == b'previous-good-release'


@pytest.mark.asyncio
async def test_production_login_stays_disabled_without_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("STYLIST_ENV", "production")
    with pytest.raises(StylistError, match="local_login_disabled"):
        await login(Settings(), LoginRequest(mobile="13800000000", code="1234", device_id="synthetic-device"))


@pytest.mark.asyncio
async def test_explicit_production_web_login_uses_existing_upstream_contract(legacy, tmp_path, monkeypatch):
    _, pem = legacy
    public_key = tmp_path / "public.pem"
    public_key.write_bytes(pem)
    monkeypatch.setenv("STYLIST_ENV", "production")
    monkeypatch.setenv("STYLIST_ALLOW_MOBILE_LOGIN", "true")
    assert Settings.load().allow_mobile_login
    actual_client = httpx.AsyncClient

    def respond(request):
        assert request.url.path == "/users/app/login/mobile/code"
        body = json.loads(request.content)
        assert body["mobile"] != "13800000000" and body["code"] == "1234"
        return httpx.Response(200, json={"code": 0, "data": {"token": {"access_token": "synthetic-token"}}})

    async def identity(self):
        assert self.authorization == "Bearer synthetic-token"
        return "123"

    monkeypatch.setattr("stylist.auth.httpx.AsyncClient", lambda **kwargs: actual_client(
        **kwargs, transport=httpx.MockTransport(respond)))
    monkeypatch.setattr("stylist.auth.Upstream.identity", identity)
    result = await login(Settings(allow_mobile_login=True, login_public_key=str(public_key)),
                         LoginRequest(mobile="13800000000", code="1234", device_id="synthetic-device"))
    assert result == {"access_token": "synthetic-token", "access_token_expires_at": None, "user": {"id": "123"}}


@pytest.mark.parametrize("database,checkpoint,valid", [
    ("var/stylist.sqlite3", "", False),
    ("postgresql://REPLACE_USER:REPLACE_PASSWORD@REPLACE_HOST:5432/aicloset_stylist", "", False),
    ("postgresql://fixture:fixture@db.invalid/aicloset_stylist", "local.sqlite3", False),
    ("postgresql://fixture:fixture@db.invalid/aicloset_stylist", "", True),
])
def test_postgres_release_startup_checks_configuration_without_connecting(monkeypatch, database, checkpoint, valid):
    from pathlib import Path

    monkeypatch.setenv("STYLIST_REQUIRE_POSTGRES", "true")
    settings = Settings(database=database, checkpoint_database=checkpoint,
                        llm_url="https://model.invalid", llm_model="fixture", llm_key="fixture")
    monkeypatch.setattr(Settings, "load", lambda: settings)
    source = Path("deploy/docker/start.sh").read_text().split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
    if valid:
        exec(compile(source, "startup-check", "exec"), {})
    else:
        with pytest.raises(SystemExit, match="STYLIST_"):
            exec(compile(source, "startup-check", "exec"), {})


def test_compose_uses_private_database_configuration():
    from pathlib import Path

    environment = yaml.safe_load(Path("compose.yaml").read_text())["services"]["stylist"]["environment"]
    assert environment["STYLIST_REQUIRE_POSTGRES"] == "true"
    assert "STYLIST_DATABASE" not in environment
    assert "STYLIST_CHECKPOINT_DATABASE" not in environment


def test_explicit_database_import_changes_only_database_name(legacy, tmp_path):
    path, _ = legacy
    database_config = tmp_path / "server.yaml"
    database_config.write_text(yaml.safe_dump({"postgresql": {"default": {
        "source": "postgresql://fixture:synthetic@db.invalid:5432/aicloset_test?sslmode=prefer&connect_timeout=5"
    }}}))
    output = tmp_path / "config"
    prepare(path, output, database_config)
    text = (output / "deploy.env").read_text()
    assert "@db.invalid:5432/aicloset_stylist?sslmode=prefer&connect_timeout=5" in text
    assert "/aicloset_test" not in text


def test_go_postgres_timezone_is_translated_to_libpq_options():
    from psycopg.conninfo import conninfo_to_dict

    from scripts.prepare_docker_config import postgres_deployment_url

    dsn = postgres_deployment_url("postgresql://fixture:synthetic@db.invalid/aicloset_test?sslmode=prefer&connect_timeout=5&TimeZone=UTC")
    params = conninfo_to_dict(dsn)
    assert params["dbname"] == "aicloset_stylist"
    assert params["options"] == "-c timezone=UTC"
    assert params["sslmode"] == "prefer"


def test_private_runtime_bundle_requires_opt_in_and_excludes_duplicate_source(tmp_path, monkeypatch):
    from pathlib import Path

    source = tmp_path / "source"
    for name in FILES:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    (source / "stylist").mkdir()
    (source / "stylist/main.py").write_text("fixture application")
    private = tmp_path / "private"
    private.mkdir()
    (private / "deploy.env").write_text("STYLIST_LLM_KEY=synthetic-private-key\n")
    (private / "login-public.pem").write_text("fixture public key")
    (private / "local.yaml").write_text("must-not-package")

    def save_image(args, check):
        Path(args[args.index("--output") + 1]).write_bytes(b"fixture image")

    monkeypatch.setattr("scripts.package_deployment.subprocess.run", save_image)
    output = tmp_path / "private.tar.gz"
    package(output, image="fixture", root=source, private_config_dir=private, runtime_only=True)
    assert output.stat().st_mode & 0o777 == 0o600
    with tarfile.open(output) as archive:
        names = archive.getnames()
        assert "aicloset-assistant/image.tar" in names
        assert not any("/stylist/" in name or name.endswith("local.yaml") for name in names)
        env = archive.getmember("aicloset-assistant/private-config/deploy.env")
        assert env.mode == 0o600
        assert archive.extractfile(env).read() == (private / "deploy.env").read_bytes()
    with pytest.raises(ValueError, match="requires an image"):
        package(tmp_path / "invalid.tar.gz", root=source, runtime_only=True)
