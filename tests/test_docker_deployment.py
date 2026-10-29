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
