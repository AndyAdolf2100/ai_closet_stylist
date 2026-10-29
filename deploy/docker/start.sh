#!/bin/sh
set -eu

if [ "${1:-}" = /app/.venv/bin/uvicorn ]; then
  /app/.venv/bin/python - <<'PY'
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from stylist.config import Settings

s = Settings.load()
missing = [name for name, value in [
    ("STYLIST_SERVER_URL", s.server_url), ("STYLIST_MCP_URL", s.mcp_url),
    ("STYLIST_LLM_URL", s.llm_url), ("STYLIST_LLM_MODEL", s.llm_model),
    ("STYLIST_LLM_KEY", s.llm_key),
] if not value or value.startswith("REPLACE_")]
if missing:
    raise SystemExit("Configure these settings before startup: " + ", ".join(missing))
if s.allow_mobile_login:
    try:
        serialization.load_pem_public_key(Path(s.login_public_key).read_bytes())
    except (OSError, ValueError, TypeError):
        raise SystemExit("STYLIST_LOGIN_PUBLIC_KEY must point to a readable PEM public key") from None
PY
  /app/.venv/bin/python -m stylist.migrate
fi

exec "$@"
