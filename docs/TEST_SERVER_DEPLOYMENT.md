# 测试服务器配置与部署流程

更新日期：2026-10-29。适用于当前 `ai_closet_stylist`，前端与 Agent 使用同一个应用容器。
本文包含已经确认的服务器信息、发布步骤、Nginx 配置、更新与回退方法。
服务器只能经跳板机访问，尚未由本机直接执行部署；下列“已确认”来自此前服务器命令输出，仍需部署时复核。

## 0. 当前实际采用的方案

使用用户指定的 **`aicloset-assistant.wxbjq.top`**，助理独立站点文件为
`/usr/local/nginx/conf/vhost/aicloset-assistant.wxbjq.top.conf`，原测试H5配置保持不变。
主配置已有 `include vhost/*.conf;`，不用额外引用。
8466在安装前由用户确认未占用；用户随后提供安装器成功输出，确认应用启动、Nginx配置检查／reload及本机HTTPS代理就绪检查已通过。

此前的 `var/releases/aicloset-assistant.tar.gz` 约65.4MiB，是源码包；目标服务器已实际在下载基础镜像时超时。
本次使用 `var/releases/aicloset-assistant-offline-amd64.tar.gz` 离线镜像包，按下面的故障处理命令上传重试。
目标服务器现已返回部署成功，具体版本记录如下；业务接口验收仍单独进行。

### 已部署版本（用户提供服务器输出）

| 项目 | 本次结果 |
| --- | --- |
| 部署日期 | 2026-10-29 |
| 版本 | `20261029T111906Z-8ca143d32b14-10412` |
| 入口 | `https://aicloset-assistant.wxbjq.top/`，前端也可访问 `/mobile/` |
| 配置目录 | `/opt/aicloset-assistant/config` |
| 版本目录 | `/opt/aicloset-assistant/releases/20261029T111906Z-8ca143d32b14-10412` |
| 发布包 | `aicloset-assistant-offline-amd64.tar.gz` |
| 包SHA256 | `8ca143d32b146a974044a3356b56b32f6a5e9633c44d31d56e72857a866f587a` |
| 证据 | 用户粘贴安装器“部署成功”及版本／配置路径输出 |

安装器成功说明镜像加载、容器就绪及通过本机Nginx的HTTPS就绪检查已通过。
未据此确认公网浏览器、上游登录／衣橱／MCP、真实模型回复、手记持久化或收费／退款全部通过。
下一步在页面使用已有账号核对这些业务能力；付费生成仍需单独明确确认。
后续更新复用服务器配置和持久数据卷，无需再次填写Key，不覆盖成开发机MySQL配置。

**后续优先直接读配置：** 本机已生成私密目录 `var/releases/aicloset-assistant-config/`，
将里面的 `deploy.env`、`login-public.pem` 与代码tar分开上传到服务器 `/tmp/aicloset-assistant-config/`。
安装器首先复用 `/opt/aicloset-assistant/config/`，首次缺失时再复制预置目录里的文件；
配置完整时不询问模型Key。私密配置不放进Git、镜像或通用代码tar，不贴文件内容。

本地现用Key来自同级 `ai_closet_agent/config/config.yaml` 当前选中的模型，服务器复用同一份，
无需申请新Key。当前使用火山方舟服务，Key不是手机号验证码、登录Token或数据库密码，不写进Nginx。
如果首次只上传tar且没有配置，安装脚本仍会提示输入Key；输入不回显，粘贴后回车。

### 2026-10-29 实际安装失败与处理

服务器执行到 `[3/5] 准备镜像` 时，`FROM python:3.12-slim` 拉取失败，
报 `registry-1.docker.io/v2/ ... Client.Timeout exceeded while awaiting headers`。
这是构建机访问Docker Hub超时，应用还未启动；`部署未完成，开始恢复原服务` 是后续回退提示。
本次流程到第2步已准备的 `/opt/aicloset-assistant/config/` 会保留，重试不必重新输入模型Key。

对此改用包含 `linux/amd64` 应用镜像的离线包：
`var/releases/aicloset-assistant-offline-amd64.tar.gz`，上传到测试服务器的 `/tmp/` 后执行：

```bash
sudo bash -o pipefail -c 'tar -xOf /tmp/aicloset-assistant-offline-amd64.tar.gz aicloset-assistant/install.sh | bash -s -- /tmp/aicloset-assistant-offline-amd64.tar.gz'
```

脚本在包内发现 `image.tar` 和 `image-name.txt` 后直接 `docker load`，
再以 `--no-build --pull never` 启动；不需要服务器下载基础镜像或Python依赖。
模型、衣橱及天气服务的运行期连接仍需要网络。
旧的约65.4MiB包为源码包，不解决本次镜像下载超时。
本机已成功构建linux/amd64镜像，并在断网、只读文件系统、非root用户容器中验证数据库初始化、就绪检查、新前缀鉴权及旧路由404。
19项部署回归通过，含只load不build/pull的模拟检查。随后用户提供CentOS7目标机部署成功输出；应用安装及健康检查通过，业务链路仍待带身份验证。

## 1. 当前环境与目标

| 项目 | 当前值／状态 |
| --- | --- |
| 系统 | CentOS Linux 7 (Core)，不是 Ubuntu |
| 架构 | x86_64 |
| 公网 IP | `60.205.2.22`，此前服务器查询所得 |
| Docker | `20.10.7` |
| Docker Compose | `v2.30.3`，此前已成功执行 |
| Nginx 程序 | `/usr/local/nginx/sbin/nginx` |
| Nginx 主配置 | `/usr/local/nginx/conf/nginx.conf` |
| 站点加载规则 | `include vhost/*.conf;` |
| 站点目录 | `/usr/local/nginx/conf/vhost/` |
| 助理域名 | `aicloset-assistant.wxbjq.top` |
| 当前上游配置域名 | `aicloset-dev.wxbjq.top`，与助理域名不同；其实际站点和后端端口待复核 |
| HTTPS 证书 | `/usr/local/nginx/conf/keys/wxbjq.top/1wxbjq.top.pem` |
| HTTPS 私钥路径 | `/usr/local/nginx/conf/keys/wxbjq.top/1wxbjq.top.key`，不导出私钥 |
| 应用宿主机端口 | `127.0.0.1:8466`，用户已再次确认未占用，安装器仍检查 |
| 容器内部端口 | `8000` |
| 发布目录 | `/opt/aicloset-assistant/` |

目标访问链路：

```text
浏览器 → HTTPS Nginx → 127.0.0.1:8466 → Stylist 容器:8000
                                             ├─ 文字模型
                                             ├─ Go REST／MCP／用户服务
                                             └─ 独立持久数据卷
```

接口约定：Stylist 自有接口为 `/stylist-api/`，登录代理为 `/stylist-api/auth/mobile-login`。
原 Go `/api/`、账号服务 `/users/` 和 MCP `/mcp` 不改名。

**数据库范围：本轮服务器仍使用 SQLite 持久卷。** 本机开发已支持 Docker MySQL，
但这次不把开发库搬到服务器，也不修改远端 MySQL、PostgreSQL、Redis 或旧 Agent。
当前服务器 `compose.yaml` 显式设置 SQLite；只在 `deploy.env` 加 MySQL URL 不会覆盖此项。

## 2. 部署前在服务器检查

通过跳板机进入服务器，执行：

```bash
cat /etc/os-release
uname -m
sudo docker version
sudo docker compose version
sudo docker ps --format 'table {{.Names}}\t{{.Ports}}'
sudo ss -lntp | grep -E ':(80|443|8466)[[:space:]]'
sudo /usr/local/nginx/sbin/nginx -t
```

80／443 已有 Nginx 使用是正常情况，不再启动第二个 Nginx 抢占端口。
8466 没有匹配行表示本次检查时未监听；如被其他项目占用，先辨明用途，不停止未知服务。
不再安装 Ubuntu `.deb` 版本 Compose，不升级服务器 glibc。

### 查出原 Server 的真实 Nginx 路由

```bash
sudo /usr/local/nginx/sbin/nginx -T 2>&1 \
  | grep -E '^# configuration file|^[[:space:]]*(server_name|listen|location|proxy_pass|upstream|include|ssl_certificate)[[:space:]]'
```

重点核对 `aicloset-dev.wxbjq.top`、助理域名，以及 `/api/`、`/users/`、`/mcp` 的现有代理目标。
不要提供完整私密配置、Authorization 或 API Key；只需上述路由摘要。
如果列表里没有 dev 域名，继续核对它是否由其他代理、通配域名或其他服务器承接，不能认定它已在当前 Nginx 中。

**后续已核对：** 用户提供的 `aicloset-test-h5.wxbjq.top.conf` 摘要中，
`/api` 经 `@go-server` 到 `127.0.0.1:9071`，`/users` 经 `@aippt-user` 到 `127.0.0.1:9332`，
`/algorithm` 到 `127.0.0.1:9191`。尚缺完整server块、MCP路由及dev域名的对应关系。
具体位置和插入写法见 [原API定位与接入](NGINX_API_LOCATION.md)；不根据摘要覆盖整份旧站点。

## 3. 本机生成最新发布包

在开发机项目根目录执行，不在测试服务器执行：

```bash
docker buildx build --platform linux/amd64 --provenance=false --sbom=false --load -t aicloset-stylist:test-amd64 .
uv run python scripts/package_deployment.py \
  --bootstrap-config ../ai_closet_agent/config/config.yaml \
  --image aicloset-stylist:test-amd64 \
  --output var/releases/aicloset-assistant-offline-amd64.tar.gz
```

输出离线tar及同名 `.sha256` 文件。构建机须能下载基础镜像和锁定依赖，并支持linux/amd64构建。
包内包含前端、Agent、部署脚本、`image.tar`、`image-name.txt`及公开连接默认值／登录公钥；
不包含真实模型Key、本机数据库凭证、用户图片、历史数据库或旧Agent整份配置。
程序修改后先重新构建镜像再打包；只重打源码不能让已有镜像更新。

该镜像已完成本机amd64构建与断网启动检查，用户随后提供目标Docker20.10.7安装成功输出。
每次新包仍需核验清单及目标机健康状态，不把某一历史版本成功当作所有后续版本通过。

### 生成与本地一致的私密配置（首次需要）

```bash
uv run python scripts/prepare_docker_config.py \
  --legacy-config ../ai_closet_agent/config/config.yaml \
  --output-dir var/releases/aicloset-assistant-config
```

按 `llm.default_model_id` 选择模型，不显示密钥、不修改旧Agent。已有配置拒绝覆盖。
已有服务器配置的正常更新跳过此步骤；本机配置变化不会自动覆盖服务器现用配置。

### 可选源码包（当前测试机不采用）

仅在目标服务器能下载基础镜像及Python依赖时使用：

```bash
uv run python scripts/package_deployment.py \
  --bootstrap-config ../ai_closet_agent/config/config.yaml \
  --output var/releases/aicloset-assistant-source.tar.gz
```

该包不含 `image.tar`，安装器会在服务器构建。当前测试机已实际遇到Docker Hub超时，继续使用离线包。

## 4. 经跳板机上传

应用tar必须上传到测试服务器，校验文件建议同时上传，不只上传到跳板机自身：

```text
/tmp/aicloset-assistant-offline-amd64.tar.gz
/tmp/aicloset-assistant-offline-amd64.tar.gz.sha256
```

在测试服务器核对：

```bash
ls -lh /tmp/aicloset-assistant-offline-amd64.tar.gz /tmp/aicloset-assistant-offline-amd64.tar.gz.sha256
cd /tmp
sha256sum -c aicloset-assistant-offline-amd64.tar.gz.sha256
```

应显示 `aicloset-assistant-offline-amd64.tar.gz: OK`。上传包名和路径与命令保持一致。

### 预置配置，避免交互输入Key

另外上传本机私密配置目录中的两个文件，服务器路径为：

```text
/tmp/aicloset-assistant-config/deploy.env
/tmp/aicloset-assistant-config/login-public.pem
```

在拥有这些文件的终端设置权限；管理员上传时使用管理员终端：

```bash
chmod 700 /tmp/aicloset-assistant-config
chmod 600 /tmp/aicloset-assistant-config/deploy.env
chmod 644 /tmp/aicloset-assistant-config/login-public.pem
```

不把配置内容发到聊天或写入共享日志。已有 `/opt/aicloset-assistant/config/` 优先，不会被上传的新文件自动覆盖。

## 5. 安装与后续更新

### 当前可执行方式：独立助理站点

当前安装脚本管理 `/usr/local/nginx/conf/vhost/aicloset-assistant.wxbjq.top.conf`，
不自动迁移其他 Server 站点。若其他文件已显式声明助理域名，脚本会拒绝部署；
先检查冲突文件，不直接删除其他站点。

执行：

```bash
sudo bash -o pipefail -c 'tar -xOf /tmp/aicloset-assistant-offline-amd64.tar.gz aicloset-assistant/install.sh | bash -s -- /tmp/aicloset-assistant-offline-amd64.tar.gz'
```

优先读取服务器已有配置，首次可直接读取第4节的预置配置，免手动输入Key。
只有缺少配置时才提示输入本地现用的模型Key，输入不回显，粘贴后回车。
默认上游为 `https://aicloset-dev.wxbjq.top` 和 `https://aicloset-dev.wxbjq.top/mcp`；
这些来自配置，不代表已确认与当前服务器上的哪个服务端口对应。
已有私密配置会保留。测试网页登录显式开启 `STYLIST_ALLOW_MOBILE_LOGIN=true`。

脚本会验证包内清单、准备配置、构建／加载镜像、更新容器、检查就绪状态，
然后备份并更新助理站点、执行 `nginx -t`、reload 和 HTTPS JSON 检查。
失败时按脚本范围尝试恢复上一应用及助理站点；不会回滚数据库内容。

部署后的目录：

```text
/opt/aicloset-assistant/
├── config/
│   ├── deploy.env          模型和上游配置，权限 0600
│   └── login-public.pem    登录加密公钥
├── releases/              每个发布版本
├── current -> releases/…  当前成功版本
├── previous -> releases/… 上一成功版本（首次没有）
└── backups/               助理 Nginx 配置备份

Docker 卷：aicloset-assistant_stylist-data
容器内：/app/var/stylist.sqlite3 及对应检查点文件
```

不要执行 `docker compose down -v`，不要把本机 `config/local.yaml` 或 MySQL 凭证传入发布目录。

## 6. Nginx 配置与统一文件

### 助理域名当前配置

完整模板为 [`deploy/nginx/aicloset-assistant.centos7.conf`](../deploy/nginx/aicloset-assistant.centos7.conf)，
安装脚本负责安装。行为为：80 跳转 HTTPS，443 使用上表已有证书，
`/`、`/mobile/`、`/static/`、`/stylist-api/` 均转发到 `127.0.0.1:8466`，公网 `/internal/` 返回404。
SSE 关闭代理缓冲、缓存和上游自动重试，读取超时600秒。

手工粘贴 `sudo tee ... <<'EOF'` 时，末尾必须单独输入 `EOF` 并回车；它是Shell结束标记，不写入Nginx文件。
终端持续显示 `>` 表示尚未结束输入。保存后先检查，再重新加载：

```bash
sudo /usr/local/nginx/sbin/nginx -t &&
sudo /usr/local/nginx/sbin/nginx -s reload
```

应用未启动时Nginx也可通过语法检查，但访问可能返回502，继续执行第5节安装。
安装器在应用就绪后也会检查并reload，不需要重启整个Nginx进程。

### 可选：与原 Server 放到同一个配置文件（当前不采用）

可以统一为一个 `.conf` 文件，其中放置助理与原 Server 各自的 `server {}` 块。
保留原 Server 的首页、证书及业务 location；助理域名保持 Stylist 页面。
不要求把两个域名改成同一个域名，也不需要更换域名解析。

如果还需要在同一个域名下分流，以下片段放在对应的 HTTPS `server {}` 内：

```nginx
location ^~ /stylist-api/ {
    client_max_body_size 2m;
    proxy_pass http://127.0.0.1:8466;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_cache off;
    proxy_next_upstream off;
    gzip off;
    proxy_connect_timeout 10s;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
}
```

`proxy_pass` 末尾不加 `/`，保留 `/stylist-api/` 前缀。
原 `/api/`、`/users/`、`/mcp` 按检测到的原配置保留，不全部转发到8466。
单独增加这段只提供 Stylist API，不会自动把原业务首页变成助理前端。

正式合并前，将原文件备份到 `/opt/aicloset-assistant/backups/` 等不被 Nginx include 的目录，
并记录哪些旧文件将移出 `vhost/*.conf`；不在该目录留另一份以 `.conf` 结尾的副本。
合并后执行：

```bash
sudo /usr/local/nginx/sbin/nginx -t
sudo /usr/local/nginx/sbin/nginx -s reload
```

**当前安装器仍只管理独立助理站点。** 合并目标文件与原站点内容确认后，还需同步调整安装器的目标和备份范围，
才能继续使用一条命令更新；不要先手工合并为其他文件，再直接运行现有安装器。
当前没有执行远端合并。详细边界见 [共享路由说明](NGINX_SHARED_ROUTING.md)。

## 7. 部署后验收

### 容器与应用

`/opt/aicloset-assistant` 由安装器以管理员权限管理。以下命令先进入管理员终端，避免普通用户 `cd` 权限不足：

```bash
sudo -i
```

完成运维后执行 `exit` 返回原终端。

```bash
cd /opt/aicloset-assistant/current
sudo docker compose -p aicloset-assistant ps
curl -fsS http://127.0.0.1:8466/health/ready
```

就绪接口应为 JSON `{"ready":true}`，HTML 管理后台页不算通过。

### HTTPS 与新前缀

```bash
curl -fsS --resolve aicloset-assistant.wxbjq.top:443:127.0.0.1 \
  https://aicloset-assistant.wxbjq.top/health/ready
curl -i --resolve aicloset-assistant.wxbjq.top:443:127.0.0.1 \
  https://aicloset-assistant.wxbjq.top/stylist-api/conversations
```

第二条未带登录态，预期401及 JSON 鉴权提示；它只证明 Stylist 路由可达。
浏览器打开 `https://aicloset-assistant.wxbjq.top/mobile/`，刷新加载新脚本。
使用已有测试账号登录，核对本人衣橱、历史、设置／手记以及流式回复；切换账号不得读到他人内容。
同账号在 App 或其他页面重复登录可能顶掉当前 Token。
文字对话会产生模型调用成本；试穿只做报价检查，真实收费生成须另行明确确认。

### 日志

```bash
cd /opt/aicloset-assistant/current
sudo docker compose -p aicloset-assistant logs --tail=80 stylist
```

Nginx 日志路径以 `nginx -T` 中 `access_log`／`error_log` 为准，不假设发行版默认路径。
排错时不贴 Token、手机号、验证码、模型 Key 或用户图片。

## 8. 后续更新与回退

**更新：** 重新打包，上传同名 tar 和校验文件，校验后重复第5节安装命令。
配置和数据卷保留，前后端同时更新；单实例切换会短暂中断，不承诺零停机。
如果已经改成合并站点，必须先完成安装器同步后再使用自动更新。

**失败恢复：** 先查看安装输出，脚本已经尝试恢复时不要同时启动另一轮操作。
确认当前／上一成功版本：

```bash
sudo readlink -f /opt/aicloset-assistant/current
sudo readlink -f /opt/aicloset-assistant/previous
sudo ls -lt /opt/aicloset-assistant/backups/
```

需手工回退时，先核对 previous 确实存在及其 `.env` 镜像版本，
在该版本目录用同一 Compose 项目名启动保留的旧镜像：

```bash
cd /opt/aicloset-assistant/previous
sudo docker compose -p aicloset-assistant up -d --no-build --pull never --wait --wait-timeout 180
curl -fsS http://127.0.0.1:8466/health/ready
```

如果目录权限不足，在 `sudo -i` 的管理员终端中进入对应目录，不扩大私密目录权限。
配套恢复与该版本匹配的 Nginx 站点，先 `nginx -t` 再 reload；验证后再调整 current 链接。
特别是跨 `/api/` → `/stylist-api/` 的版本回退，必须同步核对前端、后端及代理路径。
不删除数据卷，不自动反向迁移数据库；旧版本不兼容当前数据结构时，先停止回退并核对备份方案。

### 数据库和备份边界

服务器当前使用SQLite，位于 `aicloset-assistant_stylist-data` 卷中，主文件为 `/app/var/stylist.sqlite3`。
会话、设置、手记、试穿状态及检查点不在发布镜像中；同一项目名的更新复用该卷和 `/opt/aicloset-assistant/config/`。
MySQL代码虽已支持，但当前Compose显式设置SQLite，只改 `deploy.env` 的数据库URL不会生效。
切远程MySQL需独立建库、修改Compose、备份迁移SQLite及核对账号归属，不能只换地址。

完整备份应在无在途请求时停止应用，然后导出整个 `/app/var`（包括检查点及SQLite关联文件），再启动原应用。
例如在管理员终端中执行，备份包含用户数据，保存在700权限目录：

```bash
sudo -i
cd /opt/aicloset-assistant/current
mkdir -p /opt/aicloset-assistant/data-backups
chmod 700 /opt/aicloset-assistant/data-backups
docker compose -p aicloset-assistant stop stylist
docker compose -p aicloset-assistant run --rm --no-deps --pull never --entrypoint /bin/sh stylist \
  -c 'tar -C /app/var -czf - .' > "/opt/aicloset-assistant/data-backups/data-$(date +%Y%m%d-%H%M%S).tar.gz"
docker compose -p aicloset-assistant up -d --no-build --pull never --wait
chmod 600 /opt/aicloset-assistant/data-backups/*.tar.gz
exit
```

示例为停机备份步骤，不是已执行的远端备份证据；备份失败时保留现场并恢复服务，不删除原卷。
私密配置及TLS证书另按服务器备份机制保存。恢复时停应用并核对目标卷，不覆盖原Go业务库。

## 9. 常见故障定位

| 现象 | 首先核对 |
| --- | --- |
| `sudo: nginx: command not found` | 使用 `/usr/local/nginx/sbin/nginx` 完整路径 |
| GLIBC_2.32／2.34 错误 | 不是应用数据库问题；使用已验证的 CentOS7 Compose，不替换 glibc |
| 首次构建超时 | 说明使用了源码包；当前测试机使用含已构建amd64镜像的离线包 |
| 安装器提示域名冲突 | 先检测已有 `server_name`；不要覆盖未知业务配置 |
| 502 | 容器健康、8466监听、代理目标及 SELinux 审计；不直接关闭 SELinux |
| `/stylist-api/` 返回404 | 前后端是否同版、proxy_pass 是否误加尾斜杠、浏览器是否仍缓存旧脚本 |
| 返回旧管理后台HTML | 域名命中了旧站点／旧 location；证书可用不代表代理正确 |
| 回复迟迟不显示进度 | SSE 的缓冲、压缩、超时及自动重试设置 |
| 登录后失效 | 上游 Token 过期或被其他登录替换；换本地数据库不改变登录策略 |

## 10. 验证范围

已验证本地新前缀、历史405项Python／46项真实本机MySQL／36项前端回归及独立Nginx片段语法；具体次数为当时记录。
19项部署回归覆盖模拟安装与回退；amd64镜像已通过本机断网启动检查。
目标服务器由用户实际执行安装，并提供第0节的成功版本输出，证明该版镜像加载、容器就绪及HTTPS代理检查通过。
没有直接登录跳板机或执行远端站点合并、远端数据库迁移、完整备份恢复或真实收费生成；带身份业务另行验收。

### 本轮提交前复核

2026-10-29重新核对文档与脚本：407项Python测试通过，46项需显式连接本机MySQL的用例默认跳过；
36项Node前端测试通过，Ruff、Shell语法和部署文档链接／命令检查通过。
新增回归覆盖首次预置私密配置免Key提示且不覆盖原文件；外部服务为模拟，没有真实模型或付费生成调用。
此次提交文档和必要部署代码，不自动重新打包、更新服务器或推送Git远端。

### iPhone输入自动放大修复（待服务器更新与真机复测）

登录框继承的12px字号、手记的14px字号会触发iPhone Safari输入聚焦放大。
修复将手机宽度及无悬停粗指针设备（含横屏）的聊天、登录、搜索、称呼、手记输入字号设为至少16px，
保留手动双指缩放；主样式和手记样式版本已更新。
36项前端回归、样式分发检查和amd64镜像断网启动检查通过；这不代替iPhone键盘弹出时的真机验收。

对应离线包 `aicloset-assistant-iphone-input-amd64.tar.gz` 上传到服务器 `/tmp/` 后执行：

```bash
sudo bash -o pipefail -c 'tar -xOf /tmp/aicloset-assistant-iphone-input-amd64.tar.gz aicloset-assistant/install.sh | bash -s -- /tmp/aicloset-assistant-iphone-input-amd64.tar.gz'
```

成功后在iPhone刷新页面，检查登录、聊天、城市搜索和手记输入，竖屏／横屏点击后页面不再额外放大，
键盘关闭后仍可正常滚动，手动双指缩放仍可用。此次不声明已经在服务器发布修复。
