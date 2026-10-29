"""Explicitly prepare private deployment files from the adjacent legacy configuration.

Never prints credentials. Run locally, transfer config/ separately through your
trusted jump host, and keep it out of images, source archives and Git.
"""
import argparse
import os
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from cryptography.hazmat.primitives import serialization


def prepare(legacy_config: Path, output: Path):
    if (output / "deploy.env").exists() or (output / "login-public.pem").exists():
        raise ValueError("Deployment config already exists; refusing to overwrite it")
    try:
        raw = yaml.safe_load(legacy_config.read_text()) or {}
        llm = dict(raw.get("llm") or {})
        selected = next((m for m in llm.get("models", []) if m.get("id") == llm.get("default_model_id")), {})
        llm.update(selected)
        upstream = next(s for s in (raw.get("mcp_tool_routing") or {}).get("servers", [])
                        if s.get("enabled", True))
        mcp_url = upstream["url"]
        origin = urlsplit(mcp_url)
        if origin.username or origin.password or origin.query or origin.fragment:
            raise ValueError("MCP URL must not embed credentials or query parameters")
        auth = raw.get("upstream_auth") or {}
        key_path = Path(auth["public_key_path"])
        if not key_path.is_absolute():
            candidates = [legacy_config.parent / key_path, legacy_config.parent.parent / key_path]
            key_path = next(p for p in candidates if p.is_file())
        public_key = serialization.load_pem_public_key(key_path.read_bytes())
        pem = public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        values = {
            "STYLIST_SERVER_URL": f"{origin.scheme}://{origin.netloc}",
            "STYLIST_MCP_URL": mcp_url,
            "STYLIST_LLM_URL": llm["base_url"],
            "STYLIST_LLM_MODEL": llm["model"],
            "STYLIST_LLM_KEY": llm["api_key"],
            "STYLIST_LOGIN_APP_VERSION": auth.get("app_version") or "1.2.0",
            "STYLIST_ALLOW_MOBILE_LOGIN": "true",
            "STYLIST_ALERTS_URL": "",
            "STYLIST_ALERTS_KEY": "",
        }
        if any(not values[k] for k in ["STYLIST_SERVER_URL", "STYLIST_MCP_URL", "STYLIST_LLM_URL",
                                       "STYLIST_LLM_MODEL", "STYLIST_LLM_KEY"]):
            raise ValueError("Required connection settings are missing")
        if any(any(c in str(value) for c in "\n\r\0") for value in values.values()):
            raise ValueError("Environment values must be single-line strings")
    except (OSError, TypeError, KeyError, StopIteration, yaml.YAMLError, ValueError):
        raise ValueError("Cannot import deployment settings: check model, enabled MCP server and PEM public key") from None
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output, 0o700)
    # Compose env_file format: raw preserves $, #, quotes and backslashes in API keys.
    with open(output / "deploy.env", "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as file:
        file.write("".join(f"{key}={value}\n" for key, value in values.items()))
    (output / "login-public.pem").write_bytes(pem)
    os.chmod(output / "login-public.pem", 0o644)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-config", type=Path, default=Path("../ai_closet_agent/config/config.yaml"))
    parser.add_argument("--output-dir", type=Path, default=Path("config"))
    args = parser.parse_args()
    try:
        prepare(args.legacy_config.resolve(), args.output_dir)
    except ValueError as exc:
        parser.exit(1, str(exc) + "\n")
    print("Created deploy.env (0600) and login-public.pem; transfer config/ privately, never into Git or the image.")


if __name__ == "__main__":
    main()
