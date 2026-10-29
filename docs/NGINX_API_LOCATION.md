# 定位原 /api/ 配置并接入 Stylist

## 先明确两个文件位置

- 测试 H5 的 `/api/` 所在文件已确认：`/usr/local/nginx/conf/vhost/aicloset-test-h5.wxbjq.top.conf`。
- 新助理站点文件：`/usr/local/nginx/conf/vhost/aicloset-assistant.wxbjq.top.conf`。

已确认 Nginx 为 `/usr/local/nginx/sbin/nginx`，主配置加载 `vhost/*.conf`。
当前 Stylist 上游配置指向 `aicloset-dev.wxbjq.top`，不是助理域名。

2026-10-29 用户提供的服务器配置摘要确认：

| 路径 | 命名 location | 代理目标 |
| --- | --- | --- |
| `location ~* ^/api` | `@go-server` | `http://127.0.0.1:9071` |
| `location ~* ^/users` | `@aippt-user` | `http://127.0.0.1:9332` |
| `location ~* ^/algorithm` | `@algorithm-server` | `http://127.0.0.1:9191` |

这证明测试 H5 的配置指向这些端口，不证明当前 dev 域名指向同一个后端，也不证明 MCP 已在9071提供。
当前包保留原上游连接设置，尚未切换账号／衣橱环境。

## 1. 在测试服务器找原 /api/ 属于哪个文件

直接执行下面命令，无需先安装应用：

```bash
sudo /usr/local/nginx/sbin/nginx -T 2>&1 | awk '
  /^# configuration file / { file=$0 }
  /server_name.*aicloset-dev[.]wxbjq[.]top/ || /^[[:space:]]*location.*\/api/ {
    print file
    print $0
  }
'
```

输出中的 `# configuration file /实际路径/某文件.conf:` 就是需要继续核对的文件。
同一个 `/api/` 可能在多个域名下配置，必须结合相应 `server_name` 确定，不能只取第一个结果。
如果没有匹配，不代表没有 API：它可能由 `location /`、正则规则、通配域名或其他代理承接。

如需同时查看代理目标，上传发布包后先解压诊断文件：

```bash
mkdir -p /tmp/aicloset-inspect
tar -xzf /tmp/aicloset-assistant.tar.gz -C /tmp/aicloset-inspect \
  aicloset-assistant/scripts/inspect_nginx_routes.sh
sudo bash /tmp/aicloset-inspect/aicloset-assistant/scripts/inspect_nginx_routes.sh
```

它只输出活动配置中的文件名、域名、location、代理目标、监听和证书路径；不会修改或 reload。
不会输出 Authorization／API Key 指令；代理 URL 中的用户信息及查询串会隐藏。
把路由摘要用于核对 Go Server、用户服务和 MCP 的实际代理目标，不提供完整私密配置。

## 2. 当前可直接使用的助理配置位置

推荐先按完整部署文档运行安装脚本，它会备份并写入：

```text
/usr/local/nginx/conf/vhost/aicloset-assistant.wxbjq.top.conf
```

对应包内完整模板：

```text
aicloset-assistant/deploy/nginx/aicloset-assistant.centos7.conf
```

该模板适用于目前已确认的证书路径和 `127.0.0.1:8466`。
HTTP跳转HTTPS，助理页面及 `/stylist-api/` 交给 Stylist，公网 `/internal/` 禁止访问。
默认不改原 Server 的 `/api/` 配置；Stylist 服务端继续通过原上游域名调用它。

## 3. 想在原 Server 的 HTTPS 站点里接入 Stylist API，怎么写

若要通过测试 H5 域名访问 Stylist API，编辑：

```bash
sudo vi /usr/local/nginx/conf/vhost/aicloset-test-h5.wxbjq.top.conf
```

在对应 HTTPS `server {}` 内加入下面片段；保留原 `location /`、API、用户与算法代理：

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

必须放在 `server {}` 内，不嵌套进另一个 `location`。
`proxy_pass` 末尾不加 `/`，否则会剥掉新前缀。
保留该站点原有 `/api/`、`/users/`、`/algorithm` 及首页配置；此片段只接入 Stylist API，不接管原业务首页。
本次摘要没有看到 `/mcp` 配置，不直接添加猜测路由。

编辑前备份到 `/opt/aicloset-assistant/backups/` 等不被 `vhost/*.conf` 加载的位置。
确认应用已启动后：

```bash
curl -fsS http://127.0.0.1:8466/health/ready
sudo /usr/local/nginx/sbin/nginx -t
sudo /usr/local/nginx/sbin/nginx -s reload
```

## 4. 两个域名放同一个 .conf

可以将两个域名的完整 `server` 块集中保存，但必须取得完整的相关 `server` 块，保留原代理、rewrite、证书和PHP规则。
合并时移走原重复站点，备份不能保留在自动加载范围内。
当前安装器仍管理固定的助理站点文件；改成其他合并文件前，还要同步调整安装器的写入和回退范围。
原测试H5的9071／9332／9191端口已由配置摘要确认；尚未自动合并站点或改安装器。

## 5. 若要把 Stylist 上游切到测试环境

先检查测试域名的MCP路由，以及9071是否实际提供MCP。无凭证初步探测可在服务器执行：

```bash
curl -i --connect-timeout 3 --max-time 5 http://127.0.0.1:9071/mcp
curl -i --connect-timeout 3 --max-time 5 https://aicloset-test-h5.wxbjq.top/mcp
```

401可表明存在鉴权入口，但不等于MCP协议与工具可用；404或H5 HTML说明不能据此接入。
最终仍需带身份的标准MCP初始化和工具目录验证。
确认同一测试环境的REST、账号及MCP后，才统一修改部署私密配置里的
`STYLIST_SERVER_URL`、`STYLIST_MCP_URL`，避免登录在测试环境、选衣仍在开发环境。

完整打包、上传、安装、验证和回退流程见 [测试服务器部署文档](TEST_SERVER_DEPLOYMENT.md)。
