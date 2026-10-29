#!/usr/bin/env bash
# Read-only route summary for the existing CentOS7 nginx installation.
set -euo pipefail
nginx_bin=${AICLOSET_NGINX_BIN:-/usr/local/nginx/sbin/nginx}
[[ -x "$nginx_bin" ]] || { printf '找不到 Nginx：%s\n' "$nginx_bin" >&2; exit 1; }
printf '只读检测：不修改配置、不 reload。关注 /api/、/users/、/mcp 及相关域名。\n'
"$nginx_bin" -T 2>&1 | awk '
  /^# configuration file / { file=$0; shown=0; next }
  /^[[:space:]]*(server_name|listen|location|proxy_pass|upstream|include|ssl_certificate|ssl_certificate_key)[[:space:]]/ ||
  /^[[:space:]]*server[[:space:]]+[^{}]+;/ {
    if (!shown) { print ""; print file; shown=1 }
    line=$0
    gsub(/\/\/[^\/[:space:]]*@/, "//<redacted>@", line)
    sub(/\?.*/, "?<redacted>;", line)
    print line
  }
  /^nginx: / { print }
'
