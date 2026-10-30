# PostgreSQL 私密离线包：打包与部署

更新日期：2026-10-30。当前测试机为 CentOS7、x86_64，前端与 Agent 同容器，数据保存到远程 PostgreSQL 的独立 `aicloset_stylist` 库。

用户已确认版本 `20261030T080643Z-91a41c298fa0-2192` 部署成功，数据库预检、应用及 HTTPS 健康检查通过。地址为 `https://aicloset-assistant.wxbjq.top/`，配置目录为 `/opt/aicloset-assistant/config`。登录、衣橱、模型回复、历史持久化和收费效果分别验收。

## 1. 私密配置

当前已准备的 `config/deploy.env` 包含模型和远程 PostgreSQL 连接，`config/login-public.pem` 为登录公钥。配置文件被 Git 忽略，`deploy.env` 权限为0600；不要输出完整内容。

数据库配置格式如下，示例不含真实凭证：

```dotenv
STYLIST_DATABASE=postgresql://USER:URL_ENCODED_PASSWORD@HOST:5432/aicloset_stylist
STYLIST_CHECKPOINT_DATABASE=
```

检查点留空即使用同一 PostgreSQL 库。用户名与密码须URL编码。服务器使用已核实的内网域名，不写死解析IP；本地调试使用独立 Docker PostgreSQL，不将本地连接配置放入发布包。

首次准备配置可显式从同级项目导入：

```bash
uv run python scripts/prepare_docker_config.py \
  --legacy-config ../ai_closet_agent/config/config.yaml \
  --database-config ../aicloset-server/configs/config.yaml \
  --output-dir config
```

脚本拒绝覆盖已有文件。Server 的 `configs/config.yaml.bak` 中已找到内网连接目标，当前私密配置已采用其 PostgreSQL 内网域名并保留当前凭证。重新导入时须核对目标地址，不能把示例命令当作已选择内网地址。Go风格 `TimeZone=UTC` 自动转换为Python驱动支持的 `options=-c timezone=UTC`。

## 2. 构建与打包

应用代码变更后先构建新的 `linux/amd64` 镜像，不能只将旧镜像重新打包：

```bash
docker buildx build --platform linux/amd64 --provenance=false --sbom=false \
  --load -t aicloset-stylist:release-amd64 .
docker build --platform linux/amd64 --pull=false --network none \
  -f deploy/docker/Dockerfile.compact \
  --build-arg STYLIST_RUNTIME_IMAGE=aicloset-stylist:release-amd64 \
  -t aicloset-stylist:compact-amd64 .
uv run python scripts/package_deployment.py \
  --image aicloset-stylist:compact-amd64 \
  --private-config-dir config \
  --runtime-only \
  --output var/releases/aicloset-assistant-private-amd64.tar.gz
```

输出压缩包及同名 `.sha256` 文件。构建机需要基础镜像和锁定依赖；目标服务器仅加载镜像，不下载依赖。

- 专用私密包含 `image.tar`、安装脚本、Compose、部署文档，以及 `private-config/deploy.env`、`private-config/login-public.pem`，安装时无需填写密码或Key。
- 包和包内私密文件权限为0600，只经私有渠道传输，不提交Git、不公开分发；镜像本身不含凭证。
- `--runtime-only` 去掉已在镜像中的重复应用源码；保留全部运行页面、素材和依赖。此类包必须带镜像，不能用于服务器源码构建。
- 不包含本地调试配置、用户图片、数据库文件或旧项目完整配置。通用包不传 `--private-config-dir`，仍默认排除凭证。

当前已交付且完成服务器安装的是 `aicloset-assistant-private-amd64-v3.tar.gz`，约142.7MiB；镜像 `aicloset-stylist:postgres-compact-amd64`。精简通过合并重复源码层、移除运行时不用的uv工具及包内重复源码完成，未删除产品素材或运行依赖。新构建的实际体积按产物核对，不保证固定大小。

## 3. 上传与安装／更新

通过跳板机将包及校验文件传到实际测试服务器 `/tmp`，而不是只传到跳板机。

下面是已成功执行的v3安装方式。使用其他包名时，替换所有对应文件名：

```bash
cd /tmp
sha256sum -c aicloset-assistant-private-amd64-v3.tar.gz.sha256
tar -xOf /tmp/aicloset-assistant-private-amd64-v3.tar.gz \
  aicloset-assistant/install.sh > /tmp/aicloset-install-v3.sh
sudo bash /tmp/aicloset-install-v3.sh /tmp/aicloset-assistant-private-amd64-v3.tar.gz
```

先解出脚本再从文件运行。不要使用 `tar | bash`：预检容器可能消费管道中的剩余脚本，导致预检成功后不执行后续步骤。工作区脚本已额外将预检stdin重定向到 `/dev/null`；v3服务器成功记录使用的是上述文件执行方式。

安装顺序：校验清单 → 备份并安装包内私密配置 → 加载镜像 → PostgreSQL预检及独立库准备 → 更新应用并检查健康 → 备份更新助理Nginx站点并检查HTTPS。无需再次输入配置。更新采用包内配置；失败时尝试恢复原配置、应用和站点，不删除或反向迁移数据库。

当前工作区预检使用：

```bash
docker compose run --rm -T --no-deps stylist \
  /app/.venv/bin/python -m stylist.database_preflight --create-database </dev/null
```

旧Compose的 `run` 不支持 `--pull`；`-T` 关闭终端分配。镜像已在预检前加载。工作区预检先连接维护库 `postgres` 查询目标库，缺失时创建 `aicloset_stylist`（UTF8），再检查目标库和建表权限；不覆盖同名库中的无关数据。v3安装前该库已由用户在服务器执行诊断命令准备就绪，工作区后续增强不能视为已在v3发布。

## 4. 验证、日志与重启

```bash
curl --max-time 10 -fsS http://127.0.0.1:8466/health/ready
curl --max-time 15 -fsS --resolve aicloset-assistant.wxbjq.top:443:127.0.0.1 \
  https://aicloset-assistant.wxbjq.top/health/ready
sudo docker compose --project-directory /opt/aicloset-assistant/current \
  -p aicloset-assistant -f /opt/aicloset-assistant/current/compose.yaml logs --tail=80 stylist
```

健康接口应返回 `{"ready":true}`。最终需看到安装器“部署成功”，仅数据库预检成功不代表应用已部署。

只重启应用：

```bash
sudo docker compose --project-directory /opt/aicloset-assistant/current \
  -p aicloset-assistant -f /opt/aicloset-assistant/current/compose.yaml restart stylist
```

首次失败且没有current链接时，使用报错中的具体release目录查看日志。不要分享完整环境变量或 `docker compose config` 展开结果。

## 5. 数据与回退

设置、手记、会话、幂等记录、试穿状态和检查点保存在远程 PostgreSQL `aicloset_stylist`，不在应用镜像里。仅更换镜像或重启容器不会清空数据库；既有历史不自动迁移。

```text
/opt/aicloset-assistant/config/   当前私密配置与登录公钥
/opt/aicloset-assistant/releases/ 各发布版本（私密包解包后仍含凭证）
/opt/aicloset-assistant/current   当前成功版本链接
/opt/aicloset-assistant/previous  上一成功版本链接
/opt/aicloset-assistant/backups/  配置和Nginx备份
```

数据库备份使用目标PostgreSQL实例的备份能力或授权的逻辑备份流程；备份恢复尚未实测。配置和证书另行私密备份，不能把应用目录归档当作数据库备份。回退不回滚数据库，需先核对旧版本兼容性。完整服务器路径和站点边界见 [部署总文档](TEST_SERVER_DEPLOYMENT.md)。
