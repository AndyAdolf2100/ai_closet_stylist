# Ubuntu PostgreSQL 单机部署参考

当前已验证测试机是CentOS7；其配置见 [测试服务器部署](TEST_SERVER_DEPLOYMENT.md)。本文只保留Ubuntu环境差异，不能作为已在Ubuntu执行成功的证据。

前端和Agent在同一个容器内，宿主机Nginx通过HTTPS转发到 `127.0.0.1:8466`，容器内8000。设置、会话、手记和执行检查点使用远程PostgreSQL独立库 `aicloset_stylist`；不修改旧业务库。

## 1. 配置与打包

镜像构建、私密包与数据库设置统一见 [发布操作入口](SIMPLE_DEPLOYMENT.md)。运行期需要访问PostgreSQL、现有Go REST/MCP、用户服务、文字模型、天气和图片CDN。

使用当前私密runtime-only包时，解包后先将 `private-config/deploy.env` 与 `private-config/login-public.pem` 安装到该发布目录的 `config/`，权限分别600、644，目录700；已有配置先备份。不要输出配置内容。此包必须加载所带镜像，不能作为源码构建包。

Ubuntu不直接照搬CentOS7安装器的默认Nginx路径；首次环境需要按下节准备独立站点和证书。应用启动入口 `sh deploy/docker/deploy.sh` 会加载包内镜像、预检PostgreSQL并启动应用；它不自动管理Ubuntu的Nginx配置，也不自动安装private-config。

## 2. 宿主机准备

已有Docker无需重复安装。首次安装按 [Docker官方Ubuntu说明](https://docs.docker.com/engine/install/ubuntu/)配置源，安装Engine与Compose插件。`env_file.format: raw` 要求Compose支持该配置；检查时使用 `docker compose config --quiet`，不展示展开后的密钥。

应用端口只绑定回环地址，公网使用80/443。容器内127.0.0.1指容器自身；上游在宿主机时按实际监听地址配置，不猜测服务端口。数据库访问需核对VPC路由、DNS、出站5432、白名单及账号权限。

## 3. Nginx 与 HTTPS

先确认域名 A 记录指向此服务器；如存在 AAAA，IPv6 也须指向可用服务器。服务器安全组/防火墙放行80和443；SSH经过跳板机不影响网页部署，但公网能否访问域名仍取决于网络规则。浏览器定位需要 HTTPS。

首次无证书时，先启用仅用于证书签发的 HTTP 配置；它不接受网页登录：

```sh
apt-get update
apt-get install -y nginx certbot
mkdir -p /var/www/letsencrypt
cp deploy/nginx/aicloset-assistant.http.conf /etc/nginx/sites-available/aicloset-assistant.conf
ln -sfn /etc/nginx/sites-available/aicloset-assistant.conf /etc/nginx/sites-enabled/aicloset-assistant.conf
nginx -t
systemctl enable --now nginx
systemctl reload nginx
certbot certonly --webroot -w /var/www/letsencrypt -d aicloset-assistant.wxbjq.top
```

按 Certbot 提示填邮箱和确认协议。HTTP-01 需要外网访问80；如只能内网访问，请使用已有证书或域名服务商支持的 DNS-01，签发后按实际路径修改配置。

已有证书时直接启用完整配置：

```sh
cp deploy/nginx/aicloset-assistant.conf /etc/nginx/sites-available/aicloset-assistant.conf
# 默认证书路径为 /etc/letsencrypt/live/aicloset-assistant.wxbjq.top/{fullchain,privkey}.pem
nginx -t
systemctl reload nginx
curl --fail https://aicloset-assistant.wxbjq.top/health/ready
```

没有其他相同 `server_name` 的站点块才启用，避免冲突；无需删除服务器已有站点。非标准 Nginx/宝塔目录按实际 include 路径放置同一文件。

配置已关闭代理缓冲、缓存和上游重试，并设置600秒读取超时，适配逐步输出与较慢模型请求；`/internal`排空接口不会暴露到公网。依据 [Nginx 代理文档](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)与 [HTTPS 文档](https://nginx.org/en/docs/http/configuring_https_servers.html)。

设置续期后重载 Nginx，并验证续期：

```sh
install -d /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nnginx -t && systemctl reload nginx\n' > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/reload-nginx
certbot renew --dry-run
```

使用已有证书管理工具时沿用该工具的续期方式。[Certbot 官方说明](https://certbot.eff.org/instructions)。

## 4. 验证与备份

检查应用及HTTPS的 `/health/ready`，再单独验证登录、昵称设置、对话历史与个人衣橱。健康检查不代替模型、MCP或费用验收。真实试穿仍需明确确认费用。

数据库使用PostgreSQL实例备份或授权逻辑备份流程，配置与证书单独私密备份。更新与回退不清空数据库，不承诺零停机；旧版本是否兼容当前表结构需先核对。Ubuntu部署与备份恢复尚未实际验收。
