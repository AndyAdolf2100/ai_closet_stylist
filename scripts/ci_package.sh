#!/usr/bin/env bash
# Fresh allowlisted source package; no config, data, report or credentials.
set -euo pipefail
case "${1:-}" in test|dev) ;; *) echo 'DEPLOY_ENV must be test or dev' >&2; exit 2;; esac
[[ ${2:-} =~ ^[0-9]+$ && ${3:-} =~ ^[a-f0-9]{40}$ ]] || { echo 'Invalid pipeline or commit ID' >&2; exit 2; }
cd "$(dirname "$0")/.."
mkdir -p var/ci-release
name="aicloset-agent-$1-$2-$3.tar.gz"
excludes=$(mktemp)
trap 'rm -f "$excludes"' EXIT
# This block is generated from the authoritative OSS manifest. Those images are
# served by redirects and are also excluded from Docker's build context.
awk '/^# BEGIN OSS image exclusions/{inside=1;next} /^# END OSS image exclusions/{inside=0} inside && NF && $0 !~ /^#/ {print}' .dockerignore > "$excludes"
COPYFILE_DISABLE=1 tar -czf "var/ci-release/$name" --exclude-from="$excludes" --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='stylist/static/closet-app/comparison/evolution/screenshots/private' \
  Dockerfile .dockerignore pyproject.toml uv.lock README.md stylist deploy/docker/start.sh deploy/ci/deploy.sh deploy/ci/Dockerfile.offline
(cd var/ci-release && sha256sum "$name" > "$name.sha256")
printf 'Prepared %s\n' "$name"
