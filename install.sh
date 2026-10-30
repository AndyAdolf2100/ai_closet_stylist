#!/usr/bin/env bash
# Single-host source/image release installer. Run with the uploaded archive as $1.
set -Eeuo pipefail
umask 077

fail() { printf '部署失败：%s\n' "$*" >&2; exit 1; }
[[ $(id -u) == 0 ]] || fail '请使用 sudo 执行安装命令。'
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || fail '本发布流程用于 Linux x86_64。'
archive=${1:?请传入发布包的完整路径}
[[ -f "$archive" ]] || fail "找不到发布包：$archive"
archive=$(readlink -f "$archive")
base=${AICLOSET_DEPLOY_ROOT:-/opt/aicloset-assistant}
nginx_bin=${AICLOSET_NGINX_BIN:-/usr/local/nginx/sbin/nginx}
vhost_dir=${AICLOSET_VHOST_DIR:-/usr/local/nginx/conf/vhost}
domain=aicloset-assistant.wxbjq.top
nginx_target="$vhost_dir/$domain.conf"

for program in docker tar curl sha256sum awk grep sed mktemp flock ss; do
  command -v "$program" >/dev/null || fail "缺少命令：$program"
done
[[ -x "$nginx_bin" && -d "$vhost_dir" ]] || fail '找不到当前服务器的 Nginx 程序或站点目录。'
docker info >/dev/null
docker compose version
"$nginx_bin" -t
mkdir -p "$base/config" "$base/releases" "$base/backups"
chmod 700 "$base/config" "$base/backups"
exec 9>"$base/.deploy.lock"
flock -n 9 || fail '已有一次部署正在执行，请等它结束。'

previous=''
if [[ -L "$base/current" ]]; then
  previous=$(readlink -f "$base/current")
elif [[ -e "$base/current" ]]; then
  fail "$base/current 已存在且不是本脚本管理的链接，未修改它。"
fi
for config in "$vhost_dir"/*.conf; do
  [[ -f "$config" && "$config" != "$nginx_target" ]] || continue
  if grep -Eq '^[[:space:]]*server_name[[:space:]].*aicloset-assistant[.]wxbjq[.]top([[:space:];]|$)' "$config"; then
    fail "其他站点已显式配置该域名，请先处理冲突：$config"
  fi
done
if ss -lnt | awk '$4 ~ /:8466$/ { found=1 } END { exit !found }'; then
  running=$(docker ps -q --filter label=com.docker.compose.project=aicloset-assistant --filter label=com.docker.compose.service=stylist)
  [[ -n "$running" && -n "$previous" ]] || fail '8466 已被非本安装流程管理的服务占用，未停止该服务。'
fi

work=''
release=''
image=''
app_changed=0
nginx_changed=0
nginx_backup=''
had_nginx=0
config_changed=0
config_backup=''
compose_at() {
  local directory=$1 reference=$2
  shift 2
  STYLIST_IMAGE="$reference" docker compose --project-name aicloset-assistant \
    --project-directory "$directory" -f "$directory/compose.yaml" "$@"
}
finish() {
  local status=$?
  trap - EXIT
  set +e
  if (( status != 0 )); then
    printf '\n部署未完成，开始恢复原服务；持久数据不会删除。\n' >&2
    if (( nginx_changed )); then
      if (( had_nginx )); then cp -p "$nginx_backup" "$nginx_target"; else rm -f "$nginx_target"; fi
      "$nginx_bin" -t && "$nginx_bin" -s reload
    fi
    if (( config_changed )); then
      for name in deploy.env login-public.pem; do
        if [[ -f "$config_backup/$name" ]]; then
          cp -p "$config_backup/$name" "$base/config/$name"
        else
          rm -f "$base/config/$name"
        fi
      done
    fi
    if (( app_changed )); then
      if [[ -n "$previous" && -f "$previous/.env" ]]; then
        old_image=$(sed -n 's/^STYLIST_IMAGE=//p' "$previous/.env")
        if compose_at "$previous" "$old_image" up -d --no-build --pull never --wait --wait-timeout 180; then
          printf '上一版本已恢复。\n' >&2
        else
          printf '自动恢复未成功，请检查容器日志；数据卷仍保留。\n' >&2
        fi
      else
        compose_at "$release" "$image" stop stylist
      fi
    fi
    [[ -z "$release" ]] || printf '可查看：sudo docker compose -p aicloset-assistant -f %s/compose.yaml logs --tail=80\n' "$release" >&2
  fi
  [[ -z "$work" ]] || rm -rf "$work"
  exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf '\n[1/5] 校验并解压发布包\n'
# Only regular files/directories under the expected root may be extracted as root.
if ! tar -tzf "$archive" | awk '
  /^\// || /(^|\/)\.\.(\/|$)/ || $0 !~ /^aicloset-assistant(\/|$)/ { bad=1 }
  END { exit bad }'; then fail '发布包路径不合法。'; fi
if ! tar -tvzf "$archive" | awk 'substr($0,1,1)!="-" && substr($0,1,1)!="d" { bad=1 } END { exit bad }'; then
  fail '发布包中包含链接或特殊文件。'
fi
work=$(mktemp -d "$base/releases/.extract-XXXXXX")
(umask 022; tar --no-same-owner --no-same-permissions -xzf "$archive" -C "$work")
payload="$work/aicloset-assistant"
[[ -f "$payload/MANIFEST.sha256" && -f "$payload/compose.yaml" && ! -e "$payload/config" ]] || fail '不是有效的应用发布包。'
(cd "$payload" && sha256sum --quiet -c MANIFEST.sha256)
digest=$(sha256sum "$archive" | awk '{print substr($1,1,12)}')
version="$(date -u +%Y%m%dT%H%M%SZ)-$digest-$$"
release="$base/releases/$version"
mv "$payload" "$release"
ln -s "$base/config" "$release/config"

printf '\n[2/5] 准备配置（私密包配置先备份再安装）\n'
if [[ -d "$release/private-config" ]]; then
  [[ -f "$release/private-config/deploy.env" && -f "$release/private-config/login-public.pem" ]] || fail '私密配置不完整。'
  config_backup="$base/backups/config-$version"
  mkdir -m 700 "$config_backup"
  for name in deploy.env login-public.pem; do
    [[ ! -f "$base/config/$name" ]] || cp -p "$base/config/$name" "$config_backup/$name"
  done
  config_changed=1
  install -m 600 "$release/private-config/deploy.env" "$base/config/deploy.env"
  install -m 644 "$release/private-config/login-public.pem" "$base/config/login-public.pem"
fi
if [[ ! -f "$base/config/deploy.env" ]]; then
  if [[ -f /tmp/aicloset-assistant-config/deploy.env ]]; then
    install -m 600 /tmp/aicloset-assistant-config/deploy.env "$base/config/deploy.env"
  else
    [[ -f "$release/deploy/docker/runtime.defaults" ]] || fail '缺少首次配置；请上传 deploy.env 到 /tmp/aicloset-assistant-config/。'
    # Generated from public connection settings; it never contains the model API key.
    source "$release/deploy/docker/runtime.defaults"
    model_key=${STYLIST_LLM_KEY:-}
    if [[ -z "$model_key" ]]; then
      printf '首次部署：请输入原 Agent 的模型 API Key（输入不回显）：' >&2
      IFS= read -r -s model_key </dev/tty || fail '无法读取模型 API Key；请使用交互式 SSH 终端，或预先上传 deploy.env。'
      printf '\n' >&2
    fi
    [[ -n "$model_key" && "$model_key" != *$'\r'* && "$model_key" != *$'\n'* ]] || fail '模型 API Key 不能为空或包含换行。'
    {
      printf 'STYLIST_SERVER_URL=%s\n' "$STYLIST_SERVER_URL"
      printf 'STYLIST_MCP_URL=%s\n' "$STYLIST_MCP_URL"
      printf 'STYLIST_LLM_URL=%s\n' "$STYLIST_LLM_URL"
      printf 'STYLIST_LLM_MODEL=%s\n' "$STYLIST_LLM_MODEL"
      printf 'STYLIST_LLM_KEY=%s\n' "$model_key"
      printf 'STYLIST_DATABASE=postgresql://REPLACE_USER:REPLACE_PASSWORD@REPLACE_HOST:5432/aicloset_stylist\nSTYLIST_CHECKPOINT_DATABASE=\n'
      printf 'STYLIST_LOGIN_APP_VERSION=%s\nSTYLIST_ALLOW_MOBILE_LOGIN=true\n' "$STYLIST_LOGIN_APP_VERSION"
    } >"$base/config/.deploy.env.new"
    chmod 600 "$base/config/.deploy.env.new"
    mv "$base/config/.deploy.env.new" "$base/config/deploy.env"
    unset model_key
  fi
fi
if [[ ! -f "$base/config/login-public.pem" ]]; then
  public_key="$release/deploy/docker/login-public.pem"
  [[ ! -f /tmp/aicloset-assistant-config/login-public.pem ]] || public_key=/tmp/aicloset-assistant-config/login-public.pem
  [[ -f "$public_key" ]] || fail '缺少登录公钥，请上传 login-public.pem 到 /tmp/aicloset-assistant-config/。'
  install -m 644 "$public_key" "$base/config/login-public.pem"
fi
image="aicloset-stylist:$version"
printf 'STYLIST_IMAGE=%s\n' "$image" >"$release/.env"
compose_at "$release" "$image" config --quiet

printf '\n[3/5] 准备镜像（旧版本在构建期间继续运行）\n'
if [[ -f "$release/image.tar" && -f "$release/image-name.txt" ]]; then
  docker load -i "$release/image.tar"
  docker image tag "$(cat "$release/image-name.txt")" "$image"
else
  # docker build works with the existing Docker 20.10 CLI without a separate buildx plugin.
  docker build -t "$image" "$release"
fi

printf '\n检查容器到远程 PostgreSQL 的连接并准备独立库\n'
compose_at "$release" "$image" run --rm -T --no-deps stylist /app/.venv/bin/python -m stylist.database_preflight --create-database </dev/null

printf '\n[4/5] 更新应用并检查健康状态\n'
app_changed=1
compose_at "$release" "$image" up -d --no-build --pull never --wait --wait-timeout 180
response=$(curl --fail --silent --show-error --connect-timeout 3 --max-time 10 http://127.0.0.1:8466/health/ready)
grep -Eq '"ready"[[:space:]]*:[[:space:]]*true' <<<"$response" || fail '应用未返回预期的健康检查结果。'

printf '\n[5/5] 更新该域名的 Nginx 配置并检查 HTTPS\n'
if [[ -e "$nginx_target" ]]; then
  had_nginx=1
  nginx_backup="$base/backups/nginx-$version.conf"
  cp -p "$nginx_target" "$nginx_backup"
fi
nginx_changed=1
install -m 644 "$release/deploy/nginx/aicloset-assistant.centos7.conf" "$vhost_dir/.aicloset-assistant-new-$$"
mv -f "$vhost_dir/.aicloset-assistant-new-$$" "$nginx_target"
"$nginx_bin" -t
"$nginx_bin" -s reload
response=$(curl --fail --silent --show-error --connect-timeout 3 --max-time 15 \
  --resolve "$domain:443:127.0.0.1" "https://$domain/health/ready")
grep -Eq '"ready"[[:space:]]*:[[:space:]]*true' <<<"$response" || fail '域名代理尚未指向新 Agent。'

[[ -z "$previous" ]] || ln -sfn "$previous" "$base/previous"
ln -s "$release" "$base/.current-$$"
mv -Tf "$base/.current-$$" "$base/current"
printf '\n部署成功：https://%s/\n版本：%s\n配置：%s/config\n' "$domain" "$version" "$base"
printf '健康检查通过不代表模型、衣橱或收费接口已完成真实验收。\n'
