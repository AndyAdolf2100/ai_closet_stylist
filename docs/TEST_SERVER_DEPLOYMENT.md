# 测试服务器配置与部署流程

更新日期：2026-10-30。当前采用前端与Agent同容器、远程PostgreSQL独立库和私密amd64离线包。打包、配置导入及安装命令统一见 [发布操作入口](SIMPLE_DEPLOYMENT.md)，本文件维护服务器环境、站点边界与验收记录。

## 0. 当前已部署版本

| 项目 | 已确认结果 |
| --- | --- |
| 版本 | `20261030T080643Z-91a41c298fa0-2192` |
| 发布包 | `aicloset-assistant-private-amd64-v3.tar.gz`，约142.7MiB |
| 入口 | `https://aicloset-assistant.wxbjq.top/`，支持 `/mobile/` |
| 数据库 | 远程 PostgreSQL，独立 `aicloset_stylist` 库 |
| 配置 | `/opt/aicloset-assistant/config` |
| 证据 | 用户提供数据库预检成功及安装器“部署成功”输出 |

服务器通过跳板机访问，以上为用户提供的服务器证据，不是助手直接远程执行结果。应用和HTTPS健康检查通过；登录、衣橱、模型回复、历史持久化和收费业务另行验收。

私密包已包含数据库与模型配置，不需要额外输入密码。包、解包目录和配置备份都含凭证，不提交Git或公开传输。普通包默认不含凭证，镜像始终不含凭证。

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
                                             └─ 远程 PostgreSQL / aicloset_stylist
```

接口约定：Stylist 自有接口为 `/stylist-api/`，登录代理为 `/stylist-api/auth/mobile-login`。
原 Go `/api/`、账号服务 `/users/` 和 MCP `/mcp` 不改名。

**数据库范围：** 使用远程 PostgreSQL 的独立 `aicloset_stylist` 库，配置来自私密 `deploy.env`；会话与图检查点共用此库，不修改旧业务数据域。

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

## 3. 打包、上传与配置

按 [发布操作入口第1～3节](SIMPLE_DEPLOYMENT.md)准备私密配置、构建amd64镜像并打包，经跳板机上传至目标服务器 `/tmp`。当前Server内网连接已从其备份配置核实，模型设置来自同级Agent；文档不保存账号或密码。本地Docker PostgreSQL连接不能作为服务器部署地址。

## 4. 安装前核对

核对包名和 `.sha256`，确认是含镜像的私密包。安装器会备份并应用包内配置，不能假定服务器已有配置总是优先于包内配置。源代码有变化必须先重建镜像。当前测试机不使用需要联网构建的源码包。

## 5. 安装方式

先解出 `install.sh`，再以 `sudo bash 脚本路径 发布包路径` 从文件执行；具体v3命令见 [发布操作入口](SIMPLE_DEPLOYMENT.md#3-上传与安装更新)。不再使用管道执行安装脚本。

安装器验证清单、准备配置、加载镜像，随后从容器预检PostgreSQL，再更新应用与独立助理Nginx站点。等待最终“部署成功”，不是看到数据库预检通过就停止。

配置保存在 `/opt/aicloset-assistant/config`，版本在 `releases/`，`current` 和 `previous` 指向成功版本，备份在 `backups/`。会话、设置、手记、试穿状态和检查点保存在远程库。不要删除已有持久资源或改写旧业务库。

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

**更新：** 重新打包，上传同名 tar 和校验文件，校验后按[离线包安装步骤](SIMPLE_DEPLOYMENT.md#3-上传与安装更新)从文件运行安装脚本。
私密包中的配置经备份后安装，远程数据库保留，前后端同时更新；单实例切换会短暂中断，不承诺零停机。
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

远程PostgreSQL独立库保存本项目业务状态。使用数据库实例的备份能力或经过授权的逻辑备份流程，应用目录打包不能替代数据库备份。私密配置与TLS证书另行备份。实际备份恢复尚未验收，不提供未经核对的覆盖恢复命令。

## 9. 已遇到的问题

| 现象 | 处理与边界 |
| --- | --- |
| 镜像仓库访问超时 | 使用已构建amd64镜像的离线包，服务器不拉取基础镜像 |
| `unknown flag: --pull` | 旧Compose的run不支持此参数，预检已移除 |
| `the input device is not a TTY` | run增加-T，显式关闭TTY |
| 预检成功后直接结束 | 从文件运行install.sh；工作区预检额外重定向stdin到/dev/null |
| `OperationalError; SQLSTATE=none` | 不能仅凭此判断白名单；使用脱敏错误定位。工作区先连postgres维护库检查并创建目标库 |
| GLIBC版本错误 | 使用CentOS7兼容Compose，不更换系统glibc |
| 返回旧管理后台HTML | 检查域名对应站点和location，证书可用不代表代理正确 |
| 502或响应无进度 | 检查容器健康、8466、Nginx上游、SSE缓冲与超时 |

## 10. 当前验收

- 本地复用PostgreSQL17.6 Docker镜像，39项真实临时库回归通过；外部模型和收费接口模拟。
- 精简amd64镜像通过连接本地PostgreSQL、只读文件系统启动及健康检查。
- 安装器回归覆盖私密配置自动安装、失败恢复、离线镜像和旧Compose参数；实际Docker Compose管道stdin预检通过。
- 用户在服务器成功连接维护库、准备目标库，再完成v3安装；版本见第0节。
- 工作区追加的stdin隔离、维护库优先检查和脱敏错误增强尚不能当作v3已发布内容。
- 无真实收费／退款、远程备份恢复验收；手机真机、登录、衣橱及模型表现需分别核对。
