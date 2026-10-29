# Stylist 与 Server 共用 Nginx

Stylist 自有业务接口使用 `/stylist-api/`，包括 `/stylist-api/auth/mobile-login`、
`/stylist-api/chat/stream`、`/stylist-api/conversations`、`/stylist-api/companion-profile` 和 `/stylist-api/memories`。
不再注册旧 `/api/` 和 `/auth/mobile-login` 路由。前端需要与后端一起更新，已有页面需刷新加载新脚本。

Go Server 的 `/api/`、账号服务 `/users/` 和 MCP `/mcp` 保持原有协议及路由。
更改 Stylist 自有前缀不改变它调用的上游 URL，也不改变 Token 鉴权机制。

## 获取服务器现状

当前配置中的上游为 `aicloset-dev.wxbjq.top`，Stylist 站点为 `aicloset-assistant.wxbjq.top`。
同一台服务器可在一个 `.conf` 中放多个域名的 `server` 块，也可以在一个站点按路径分流。
测试H5站点文件已由用户输出确认：`/usr/local/nginx/conf/vhost/aicloset-test-h5.wxbjq.top.conf`；
其中API代理到9071，用户服务代理到9332，算法代理到9191。MCP及dev域名与这些服务的对应关系仍未确认。

```sh
sudo /usr/local/nginx/sbin/nginx -T 2>&1 \
  | grep -E '^# configuration file|^[[:space:]]*(server_name|listen|location|proxy_pass|upstream|include|ssl_certificate)[[:space:]]'
```

根据输出保留原业务代理及证书配置，将有关 `server` 块汇集到同一个站点文件；
原配置备份必须放到 `vhost/*.conf` 加载范围外，避免重复 `server_name`。
目前已获得测试H5的路由摘要，尚未获得完整相关server块，因此没有修改远端、生成可覆盖原业务的合并站点或调整安装脚本目标文件。

## Stylist 路由片段

[`deploy/nginx/stylist-api.location.inc`](../deploy/nginx/stylist-api.location.inc) 可放在原有 HTTPS `server {}` 内。
代理到 `127.0.0.1:8466`，保留完整路径、关闭缓冲与自动重试，支持 SSE。
`proxy_pass http://127.0.0.1:8466;` 末尾不能加 `/`，否则会剥离 `/stylist-api/` 前缀。

同一域名分流时，目标规则为：

| 路径 | 目标 |
| --- | --- |
| `/stylist-api/` | Stylist 的 8466 端口 |
| `/api/` | 原 Go Server 的已核实代理 |
| `/users/` | 原用户服务的已核实代理 |
| `/mcp` | 原 MCP 的已核实代理，包含实际尾斜杠规则 |
| `/`、`/mobile/`、`/static/` | 由站点用途决定；助理域名继续指向 Stylist，原业务域名保留原页面 |

合并配置不等于把原业务域名的首页也替换为助理页面。
现有部署安装脚本仍管理助理域名的独立 `.conf`；正式合并时应一并核对目标文件，避免后续更新产生重复站点。
`/internal/` 继续禁止公网访问。

修改完成后先验证应用和配置，再 reload：

```sh
curl -fsS http://127.0.0.1:8466/health/ready
sudo /usr/local/nginx/sbin/nginx -t
sudo /usr/local/nginx/sbin/nginx -s reload
```

未登录访问 `/stylist-api/conversations` 应返回 Stylist 的 401 JSON；这只能证明路由及鉴权入口，
不能代替带身份的衣橱、账号与 MCP 验收。

## 本地验证（2026-10-29）

405项Python回归通过，46项真实MySQL回归单独执行通过，36项前端回归通过；Ruff与差异格式检查通过。
使用本机已有Nginx镜像在隔离容器中加载上述片段及并列 `/api/`、`/users/`、`/mcp` 路由，语法检查通过。
本机8466服务已重启，验证新接口返回401、登录参数校验422、旧接口404及前端脚本包含新前缀。
这不代表远端CentOS7配置已合并、发布或完成带身份业务验收。
