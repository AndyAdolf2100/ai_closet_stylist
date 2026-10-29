# Ubuntu 单机 Docker 部署

注意：用户后续确认当前测试机实际为CentOS7，不是Ubuntu。该机器的Compose修复与Nginx目录按 [CentOS7部署补充](CENTOS7_DEPLOYMENT.md) 操作；本文中的应用容器、配置、数据与备份方案仍可复用，apt和sites-enabled命令仅用于Ubuntu。

目标域名：`aicloset-assistant.wxbjq.top`。前端静态文件和 FastAPI Agent 在同一个应用镜像内，Nginx 安装在 Ubuntu 宿主机，统一通过 HTTPS 代理到 `127.0.0.1:8466`。不需要第二个域名、Node 构建服务或额外 MySQL。现有 Go REST/MCP 和文字模型仍是远端依赖，不包含在这个镜像内。

```text
浏览器 → HTTPS :443 → Ubuntu Nginx → 127.0.0.1:8466 → Docker /app :8000
                                                     ├─ 远端 Go REST / MCP
                                                     ├─ 远端文字模型
                                                     └─ 专用 Docker 持久卷（SQLite + 图检查点）
```

单实例、单 worker，持久卷保存昵称/性别/角色、会话、历史、幂等记录及执行检查点。不要使用多副本共享 SQLite。本方案不修改原 MySQL/旧 Agent 数据。迁移在容器启动时自动执行，只创建本项目自己的表。

## 1. 准备文件

源码部署包包含 Dockerfile、锁定依赖、前端与 Agent、Compose 和 Nginx 配置，不含任何本机配置、凭证、用户图片或历史数据。带镜像的离线包还包含 `image.tar` 与 `image-name.txt`。

在本机项目根目录，显式导出需要的连接设置（此操作会生成含模型密钥的私有配置，不打印密钥）：

```sh
.venv/bin/python scripts/prepare_docker_config.py \
  --legacy-config ../ai_closet_agent/config/config.yaml
```

生成 `config/deploy.env`（0600）和 `config/login-public.pem`（登录加密公钥）。只提取选中的文字模型、启用的 MCP 地址与登录公钥；不会复制旧项目整份配置、数据库密码、账号 Token 或私钥。原配置不变；已有部署文件不会覆盖。通过跳板机的文件通道单独将这两个文件放到服务器部署目录的 `config/` 下，不要放进镜像、公开下载地址或 Git。

如需手动配置：

```sh
mkdir -p config
cp deploy/docker/deploy.env.example config/deploy.env
chmod 700 config
chmod 600 config/deploy.env
# 把原项目登录公钥复制为 config/login-public.pem，再修改 deploy.env 的模型配置。
chmod 644 config/login-public.pem
```

`deploy.env` 使用 Compose 的 `env_file.format: raw`：值不加引号，`$`、`#`、引号和反斜杠均按字面保留。要求 Docker Compose ≥2.30。不要执行或分享 `docker compose config` 的完整展开输出，它可能显示环境变量里的密钥；使用 `config --quiet`。

配置中连接旧服务的当前非敏感地址为：

```text
STYLIST_SERVER_URL=https://aicloset-dev.wxbjq.top
STYLIST_MCP_URL=https://aicloset-dev.wxbjq.top/mcp
STYLIST_LLM_URL=https://ark.cn-beijing.volces.com/api/v3
```

服务器须能出站访问这些依赖及图片 CDN，地址存在不等于已验证可达。容器内 `127.0.0.1` 指容器本身；如上游实际在同一宿主机，应配置 `http://host.docker.internal:端口`，并确保宿主机服务监听地址、防火墙允许 Docker 网关访问。

`STYLIST_ALLOW_MOBILE_LOGIN=true` 是本测试站点显式启用网页登录的开关；生产默认仍关闭此代理。登录沿用原服务现有验证码校验，本页目前没有“发送验证码”功能；部署不会新增短信通道。请使用原服务有效验证码，或其已有测试验证码规则，不假定任意验证码可用。登录可能使同账号旧页面失效。对外只通过 HTTPS 访问。

## 2. 本机打包、服务器启动

推荐先用源码包部署：Ubuntu 在本机架构上构建，不受当前 Mac arm64 与服务器 amd64 差异影响。

本机生成可上传的源码包：

```sh
.venv/bin/python scripts/package_deployment.py
```

文件为 `var/releases/aicloset-assistant-source.tar.gz` 及 `.sha256`。通过跳板机上传到服务器，或放到你自己的下载地址让服务器下载；本项目不会自动公开上传。

服务器安装 Docker Engine、Compose 插件；已有 Docker 不必重复安装。按 [Docker 官方 Ubuntu 安装步骤](https://docs.docker.com/engine/install/ubuntu/)配置其 apt 源后安装：

```sh
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker compose version
uname -m
```

服务器解压和启动（以下假设已进入 root shell；非 root 用户为 Docker/系统命令加 sudo）：

```sh
mkdir -p /opt/aicloset
cd /opt/aicloset
# 将上传的 tar.gz 和 .sha256 放到这里。
sha256sum -c aicloset-assistant-source.tar.gz.sha256
tar -xzf aicloset-assistant-source.tar.gz
cd aicloset-assistant
# 通过跳板机上传前述 config/deploy.env、config/login-public.pem 到此目录。
docker compose config --quiet
sh deploy/docker/deploy.sh
docker compose ps
curl --fail http://127.0.0.1:8466/health/ready
```

构建需要下载 Python 基础镜像及锁定的 Python 依赖。Docker Hub/依赖源不可达时，使用已配置的可信镜像代理或下述离线镜像方式，不能认为“上传源码就无需网络”。本机应用端口只绑定回环地址，不对公网开放8466。

如 Ubuntu 是 `x86_64` 且你希望不在服务器构建，在可联网的本机执行：

```sh
docker buildx build --platform linux/amd64 --load -t aicloset-stylist:20261029 .
.venv/bin/python scripts/package_deployment.py \
  --image aicloset-stylist:20261029 \
  --output var/releases/aicloset-assistant-amd64.tar.gz
```

Ubuntu 为 `aarch64` 时改用 `linux/arm64`。解压带镜像包后：

```sh
docker load -i image.tar
export STYLIST_IMAGE="$(cat image-name.txt)"
docker compose config --quiet
docker compose up -d --no-build --pull never --wait --wait-timeout 180
```

也可统一运行 `sh deploy/docker/deploy.sh`，脚本检测到 `image.tar` 时自动使用离线镜像，否则从源码构建。镜像包含程序与前端，私有配置始终单独上传。没有镜像仓库账号时可直接用 `docker save/load`，无需发布公共镜像。相关机制见 [Docker 多平台构建](https://docs.docker.com/build/building/multi-platform/)。

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

## 4. 验证、更新与备份

打开 `https://aicloset-assistant.wxbjq.top/` 或 `/mobile/`：检查登录、昵称角色保存、刷新后历史、只读个人衣橱选款和流式进度。用户点击“检查服务连接”会查询只读业务接口并调用文字模型检查（有文字模型费用），不会扣费生图；不要将健康检查成功等同于这些依赖已经验收。真实试穿另需显式确认费用，当前未做真实扣费/退款验收。

```sh
docker compose logs --tail=100 stylist
docker compose ps
```

源码更新后 `docker compose up -d --build --wait`；离线镜像更新后加载新镜像并设置新的 `STYLIST_IMAGE`，再按离线启动命令重建。单实例更新会短暂不可用，停止窗口最多330秒让在途请求结束；不是零停机部署。固定 Compose 项目名保持同一持久卷，不执行 `down -v`、`volume rm` 或清理数据卷。

完整备份时先停止应用，避免复制中的SQLite/检查点不一致；在项目目录执行：

```sh
mkdir -p backup
chmod 700 backup
docker compose stop stylist
docker compose run --rm --no-deps --entrypoint /bin/sh stylist \
  -c 'tar -C /app/var -czf - .' > "backup/stylist-data-$(date +%Y%m%d-%H%M%S).tar.gz"
docker compose up -d --no-build --wait
chmod 600 backup/*.tar.gz
```

备份包含用户历史和设置，应私密保存；恢复需停应用并在原持久卷内恢复，不覆盖原MySQL。`config/`和TLS证书按服务器私密配置备份机制单独保存。

## 验证与当前测试机差异（2026-10-29）

Ubuntu部署命令是其他目标环境的参考流程，没有在当前CentOS7上执行apt或证书签发。
本机已完成linux/amd64镜像构建、断网／只读／非root容器的初始化与健康检查，以及Nginx片段语法检查。
部署流程的模拟回归覆盖配置保留、离线加载、失败恢复和端口／域名冲突；不代替远端业务验收。
用户已提供CentOS7版本 `20261029T111906Z-8ca143d32b14-10412` 的安装成功输出，
包含镜像加载、容器就绪及本机HTTPS代理检查。当前离线包约218MiB，不含密钥或数据库。
真实模型、MCP、业务身份、收费／退款及备份恢复仍按实际验收分别记录。
