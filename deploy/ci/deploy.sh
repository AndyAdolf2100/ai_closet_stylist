#!/usr/bin/env bash
# Invoked over the existing Runner SSH connection. No host Python required.
set -Eeuo pipefail
umask 077
fail(){ printf 'Deployment failed: %s\n' "$*" >&2; exit 1; }
environment=${1:-}; archive=${2:-}; commit=${3:-}; root=${4:-/opt/aicloset-agent}
case "$environment" in
 test) database=aicloset_stylist_test; port=8465; public_url=https://aicloset-agent.wxbjq.top; legacy_name=recommend-outfit;;
 dev) database=aicloset_stylist; port=8466; public_url=https://aicloset-assistant.wxbjq.top; legacy_name=;;
 *) fail 'DEPLOY_ENV must be test or dev';;
esac
[[ "$commit" =~ ^[a-f0-9]{40}$ && "$root" =~ ^/[a-zA-Z0-9_/-]+$ ]] || fail 'Invalid commit or release root'
[[ "$archive" =~ ^/tmp/aicloset-agent-${environment}-[0-9]+-${commit}\.tar\.gz$ ]] || fail 'Invalid archive path'
[[ $(id -u) == 0 ]] || fail 'Run through the deployment root SSH account'
for command in docker tar sha256sum flock curl ss; do command -v "$command" >/dev/null || fail "Missing $command"; done
mkdir -p "$root/releases/$environment" "$root/config"
exec 9>"$root/deploy.lock"
flock -w 600 9 || fail 'Another deployment is active'
(cd /tmp && sha256sum -c "${archive##*/}.sha256")
tar -tzf "$archive" | awk '/^\// || /(^|\/)\.\.(\/|$)/ {bad=1} END{exit bad}' || fail 'Unsafe archive path'
tar -tvzf "$archive" | awk 'substr($0,1,1)!="-" && substr($0,1,1)!="d" {bad=1} END{exit bad}' || fail 'Archive contains links or special files'
release=$(mktemp -d "$root/releases/$environment/$(date -u +%Y%m%dT%H%M%SZ)-${commit:0:12}-XXXXXX")
mkdir -p "$release/source" "$release/private"
tar --no-same-owner -xzf "$archive" -C "$release/source"
config="$root/config/$environment.env"
[[ -f "$config" && ! -L "$config" ]] || fail "Install private $environment.env on the deployment server"
# Do not load dormant tracing credentials from an older environment file.
awk '!/^LANGFUSE_/' "$config" > "$release/private/runtime.env"
chmod 600 "$release/private/runtime.env"
key="$root/config/login-public.pem"
[[ -f "$key" ]] || key=/opt/aicloset-assistant/config/login-public.pem
[[ -f "$key" && ! -L "$key" ]] || fail 'Install the existing login-public.pem under the configuration directory'
install -m 644 "$key" "$release/private/login-public.pem"
image="aicloset-stylist:ci-$environment-$commit"
app="aicloset-agent-$environment"
candidate="$app-check-$$"
old_id=; renamed=0; new_started=0; success=0
cleanup(){
 status=$?; trap - EXIT; set +e
 docker rm -f "$candidate" >/dev/null 2>&1
 if [[ $success == 0 ]]; then
  if [[ $new_started == 1 ]]; then docker rm -f "$app" >/dev/null 2>&1; fi
  if [[ -n "$old_id" ]]; then
   if [[ $renamed == 1 ]]; then docker rename "$old_id" "$app"; fi
   docker start "$old_id" >/dev/null
  fi
  echo 'Release not activated; previous container restored when it had been stopped. Database migrations are not reversed.' >&2
 fi
 exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
docker build --label "org.opencontainers.image.revision=$commit" -t "$image" "$release/source"
# Validate actual container settings before migrations or stopping any service.
docker run --rm -i --env-file "$release/private/runtime.env" -e LANGFUSE_TRACING_ENABLED=false --entrypoint /app/.venv/bin/python "$image" - "$environment" <<'PY'
import sys
from stylist.config import Settings
from stylist.deploy_config import validate
try:
 validate(Settings.load(), sys.argv[1])
except Exception as error:
 # The validator emits fixed safe messages; parsing failures must not expose env contents.
 print('Environment configuration rejected:', type(error).__name__)
 raise SystemExit(1) from None
print('Environment configuration validated; no credentials printed')
PY
args=(-e "STYLIST_BUILD_COMMIT=$commit" --env-file "$release/private/runtime.env" -e LANGFUSE_TRACING_ENABLED=false -e STYLIST_ENV=production -e STYLIST_REQUIRE_POSTGRES=true -e STYLIST_REQUIRE_MIGRATIONS=true -e STYLIST_LOGIN_PUBLIC_KEY=/run/stylist/login-public.pem --mount "type=bind,source=$release/private/login-public.pem,target=/run/stylist/login-public.pem,readonly")
docker run --rm "${args[@]}" "$image" /app/.venv/bin/python -m stylist.database_preflight --database-name "$database"
docker run --rm "${args[@]}" "$image" /app/.venv/bin/python -m stylist.migrate --check --environment "$environment"
docker run -d --name "$candidate" "${args[@]}" "$image" >/dev/null
probe(){
 docker exec -i "$1" /app/.venv/bin/python - <<'PY'
import json,urllib.request,urllib.error
base='http://127.0.0.1:8000'
for path in ['/health/ready','/app/?design=yijian','/static/app.js','/ops/conversations','/static/ops/console.js']:
 with urllib.request.urlopen(base+path,timeout=5) as r:
  assert r.status==200
  if path=='/health/ready':assert json.load(r).get('ready') is True
try:urllib.request.urlopen(base+'/stylist-api/conversations',timeout=5)
except urllib.error.HTTPError as e:assert e.code==401
else:raise AssertionError('Authentication boundary missing')
with urllib.request.urlopen(base+'/openapi.json',timeout=5) as r:paths=json.load(r)['paths']
for path in ['/stylist-api/chat/stream','/stylist-api/memories','/stylist-api/images/quote','/stylist-api/weather/forecast']:
 assert path in paths,path
PY
}
ready=0
for _ in $(seq 1 60); do if probe "$candidate" >/dev/null 2>&1; then ready=1; break; fi; sleep 2; done
[[ $ready == 1 ]] || fail 'Candidate H5, ops or API checks failed'
docker rm -f "$candidate" >/dev/null
# Only replace known old containers on the selected environment port.
occupants=$(docker ps -q --filter "publish=$port")
for id in $occupants; do
 name=$(docker inspect -f '{{.Name}}' "$id"); name=${name#/}
 if [[ "$name" != "$app" && "$name" != "$legacy_name" ]]; then
  [[ "$environment" == dev ]] || fail 'Port belongs to an unrelated container'
  label=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$id")
  service=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$id")
  [[ "$label" == aicloset-assistant && "$service" == stylist ]] || fail 'Dev port belongs to an unrelated container'
 fi
 [[ -z "$old_id" ]] || fail 'Multiple containers bind deployment port'
 old_id=$id
done
existing=$(docker ps -aq --filter "name=^/${app}$")
[[ -z "$existing" || "$existing" == "$old_id" ]] || fail 'A stopped deployment container already owns the target name; inspect it before retrying'
if [[ -n "$old_id" ]]; then
 docker stop -t 330 "$old_id" >/dev/null
 name=$(docker inspect -f '{{.Name}}' "$old_id")
 if [[ "$name" == "/$app" ]]; then docker rename "$old_id" "$app-previous-$(date +%s)"; renamed=1; fi
fi
# Refuse a non-container listener rather than killing an unknown process.
if ss -lnt | awk -v port="$port" '$4 ~ ":"port"$" {found=1} END{exit !found}'; then fail 'Deployment port is still occupied'; fi
docker volume create "$app-data" >/dev/null
new_started=1
docker run -d --name "$app" --restart unless-stopped --init --label "aicloset.environment=$environment" --label "aicloset.commit=$commit" \
 "${args[@]}" -v "$app-data:/app/var" -p "127.0.0.1:$port:8000" --stop-timeout 330 "$image" >/dev/null
ready=0
for _ in $(seq 1 60); do if probe "$app" >/dev/null 2>&1; then ready=1; break; fi; sleep 2; done
[[ $ready == 1 ]] || fail 'Application did not become ready'
for path in '/app/?design=yijian' /ops/conversations /static/app.js; do curl --fail --silent --show-error --max-time 15 "$public_url$path" >/dev/null; done
curl --fail --silent --show-error --max-time 15 "$public_url/health/ready" | grep -Eq '"ready"[[:space:]]*:[[:space:]]*true' || fail 'Public domain does not route to the new service'
[[ $(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 15 "$public_url/stylist-api/conversations") == 401 ]] || fail 'Public API authentication check failed'
curl --fail --silent --show-error --max-time 15 "$public_url/health" | grep -Eq "\"revision\"[[:space:]]*:[[:space:]]*\"$commit\"" || fail 'Public domain serves a different commit'
# Save working configuration only after activation; prior releases keep snapshots.
install -m 600 "$release/private/runtime.env" "$root/config/$environment.env"
ln -sfn "$release" "$root/current-$environment"
success=1
printf 'Deployed %s commit %s at %s\n' "$environment" "$commit" "$public_url"
