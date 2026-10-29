# 测试服务器：离线包与一条命令部署

适用于当前CentOS7、x86_64、Docker20.10.7、Compose2.30.3测试机。
完整环境、首次准备、Nginx、备份和回退见 [部署总文档](TEST_SERVER_DEPLOYMENT.md)。

当前入口：`https://aicloset-assistant.wxbjq.top/mobile/`。
用户已提供部署成功输出，版本为 `20261029T111906Z-8ca143d32b14-10412`；
配置保存在 `/opt/aicloset-assistant/config`。这证明安装和健康检查通过，带身份业务及模型效果仍需单独验收。

## 1. 开发机打包

在项目根目录构建服务器架构镜像，再导出离线包：

```bash
docker buildx build --platform linux/amd64 --provenance=false --sbom=false --load -t aicloset-stylist:test-amd64 .
uv run python scripts/package_deployment.py \
  --bootstrap-config ../ai_closet_agent/config/config.yaml \
  --image aicloset-stylist:test-amd64 \
  --output var/releases/aicloset-assistant-offline-amd64.tar.gz
```

输出tar及同名 `.sha256` 文件。构建机需要获取基础镜像和Python依赖；测试服务器只加载成品镜像。
包内有前端、Agent、`image.tar`、部署脚本、公开连接默认值及登录公钥，不含真实Key、配置、数据库或用户图片。
源代码变化后需要重新构建镜像，不能只给旧镜像重新打包。不要把约65MiB源码包当作离线包。

## 2. 首次配置（已有配置的更新可跳过）

在开发机生成与本地当前模型一致的私密配置：

```bash
uv run python scripts/prepare_docker_config.py \
  --legacy-config ../ai_closet_agent/config/config.yaml \
  --output-dir var/releases/aicloset-assistant-config
```

将里面的 `deploy.env`、`login-public.pem` 单独上传到服务器 `/tmp/aicloset-assistant-config/`。
设置目录权限700、`deploy.env`权限600。脚本拒绝覆盖开发机已有文件。
安装器优先复用 `/opt/aicloset-assistant/config/`，首次缺失时复制预置目录配置；配置完整时不询问Key。
只有首次缺少配置才提示隐藏输入模型Key，粘贴后回车。Key不是验证码，不写入Nginx。

## 3. 上传并安装／更新

通过跳板机上传到真正的测试服务器：

```text
/tmp/aicloset-assistant-offline-amd64.tar.gz
/tmp/aicloset-assistant-offline-amd64.tar.gz.sha256
```

在服务器执行：

```bash
cd /tmp
sha256sum -c aicloset-assistant-offline-amd64.tar.gz.sha256
sudo bash -o pipefail -c 'tar -xOf /tmp/aicloset-assistant-offline-amd64.tar.gz aicloset-assistant/install.sh | bash -s -- /tmp/aicloset-assistant-offline-amd64.tar.gz'
```

无需手动解压。脚本校验包、复用配置、加载镜像，以固定项目名 `aicloset-assistant` 启动单容器，
并备份更新助理Nginx站点、检查HTTPS。含镜像包不会在服务器执行构建或拉取依赖。
运行期仍需访问模型、Go REST／MCP、用户服务及图片CDN。

Nginx文件固定为 `/usr/local/nginx/conf/vhost/aicloset-assistant.wxbjq.top.conf`，
主配置已有 `include vhost/*.conf;`，无需额外引用。原H5站点保留。
配置将助理域名转发到 `127.0.0.1:8466`，容器内8000，SSE关闭缓冲；公网不开放8466或 `/internal/`。
不要先手工合并成其他站点文件再运行安装器；合并场景需同步修改安装器管理范围。

## 4. 验证和日志

```bash
curl -fsS http://127.0.0.1:8466/health/ready
curl -fsS --resolve aicloset-assistant.wxbjq.top:443:127.0.0.1 \
  https://aicloset-assistant.wxbjq.top/health/ready
```

应返回JSON `{"ready":true}`。浏览器刷新 `/mobile/`，使用已有账号核对本人衣橱、历史、设置／手记及流式回复。
自有接口为 `/stylist-api/`；上游 `/api/`、`/users/`、`/mcp` 协议不变。
健康检查不能代替上游业务验收，付费生成仍需另行确认。

查看容器和日志（不需要普通用户进入管理员目录）：

```bash
sudo docker compose --project-directory /opt/aicloset-assistant/current \
  -p aicloset-assistant -f /opt/aicloset-assistant/current/compose.yaml ps
sudo docker compose --project-directory /opt/aicloset-assistant/current \
  -p aicloset-assistant -f /opt/aicloset-assistant/current/compose.yaml logs --tail=80 stylist
```

首次安装失败且尚无current时，按错误提示的具体release目录查看日志。实际错误一般在“开始恢复原服务”之前。
不要贴完整 `docker compose config`、环境变量或Token；配置验证使用 `config --quiet`。

## 5. 数据保留与回退

```text
/opt/aicloset-assistant/config/   模型Key、上游配置与登录公钥
/opt/aicloset-assistant/releases/ 各发布版本
/opt/aicloset-assistant/current   当前成功版本链接
/opt/aicloset-assistant/previous  上一成功版本链接
/opt/aicloset-assistant/backups/  Nginx备份
Docker卷 aicloset-assistant_stylist-data：SQLite、聊天、设置、手记、试穿状态和检查点
```

当前服务器用SQLite持久卷，不是镜像内预置数据库，也未切到远程MySQL。
换包和重建容器复用数据卷与配置；不要执行 `down -v`、`volume rm` 或删除持久数据。
源码包首次失败时已保存的配置也会保留，改离线包重试不必重新输入Key。

构建、启动或代理检查失败时脚本尝试恢复上一应用和助理站点；首次失败停止本次应用，不删除卷。
回退不反向迁移数据库，不承诺零停机。人工回退与备份步骤见 [部署总文档第8节](TEST_SERVER_DEPLOYMENT.md#8-后续更新与回退)。
以后若切远程MySQL，需要改Compose中的SQLite固定配置，并单独备份、迁移及核对已有数据。
