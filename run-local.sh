#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -z "${STYLIST_LEGACY_CONFIG:-}" ] && [ -f ../ai_closet_agent/config/config.yaml ]; then
  export STYLIST_LEGACY_CONFIG="$(cd ../ai_closet_agent && pwd)/config/config.yaml"
fi
exec .venv/bin/uvicorn stylist.main:app --host 127.0.0.1 --port "${STYLIST_PORT:-8466}"
