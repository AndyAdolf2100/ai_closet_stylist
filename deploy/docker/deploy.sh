#!/bin/sh
# Run on the Ubuntu server after privately uploading config/.
set -eu
cd "$(dirname "$0")/../.."

if [ ! -f config/deploy.env ] || [ ! -f config/login-public.pem ]; then
  echo 'Missing config/deploy.env or config/login-public.pem. Prepare and upload config/ first.' >&2
  exit 1
fi
docker info >/dev/null
docker compose config --quiet

if [ -f image.tar ] && [ -f image-name.txt ]; then
  docker load -i image.tar
  STYLIST_IMAGE=$(cat image-name.txt)
  export STYLIST_IMAGE

else
  docker compose build
fi

docker compose run --rm -T --no-deps stylist /app/.venv/bin/python -m stylist.database_preflight --create-database </dev/null
docker compose up -d --no-build --pull never --wait --wait-timeout 180
docker compose ps
echo 'Application started on 127.0.0.1:8466. Configure host Nginx and HTTPS next.'
