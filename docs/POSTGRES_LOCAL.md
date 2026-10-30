# 本地 PostgreSQL 与服务器预检

## 本地运行

本地使用已有 PostgreSQL 16/17 Docker 镜像，不拉取镜像、不连接远程数据库：

```sh
uv run python scripts/setup_postgres_local.py
uv run python scripts/check_postgres_local.py
sh run-local.sh
```

独立Compose项目为 `stylist-postgres-local`，端口 `127.0.0.1:15432`，库名 `aicloset_stylist`。密码仅在被Git忽略的 `config/postgres-local.env` 与 `config/local.yaml` 中，权限0600。容器健康、业务表和检查点初始化完成后才切换本地配置；已有应用进程需重启。既有数据不迁移、不删除。

回归脚本只接受回环地址，创建随机 `stylist_tmp_` 测试库并在结束后清理。外部服务模拟，不调用真实模型或收费生成。

## 服务器配置与预检

远程配置保存在私密 `config/deploy.env`；本地 `config/local.yaml` 不进入发布包。专用私密包按用户授权携带部署配置，安装器自动备份并安装，不再询问密码；普通包默认排除凭证，镜像始终不含凭证。准备配置、打包与安装命令统一见 [发布操作入口](SIMPLE_DEPLOYMENT.md)。

导入器将Go风格 `TimeZone=UTC` 转换为libpq支持的 `options=-c timezone=UTC`。Server的备份配置已确认内网PostgreSQL域名，当前私密配置使用该域名与现行凭证；文档不保存真实凭证或写死解析IP。

当前工作区安装器在替换旧应用前，从相同Compose网络执行：

```sh
docker compose run --rm -T --no-deps stylist \
  /app/.venv/bin/python -m stylist.database_preflight --create-database </dev/null
```

预检先连接维护库 `postgres` 查询目标库；只允许 `aicloset_stylist`，缺失时按需创建UTF8库，需要账号具备建库权限。目标库存在无关表时停止，不清空或覆盖；再检查建表权限。应用启动初始化本项目表与检查点。失败不删除数据库，错误信息脱敏。

服务器需要可用DNS、到数据库的VPC路由、出站5432、来源白名单及账号权限。普通bridge网络通常经宿主机出口访问，不需要给容器设置数据库内网IP；实际可用性必须从目标容器核验。使用 `-T` 并隔离stdin，避免旧Compose的TTY和管道消费问题；`run`不使用其不支持的`--pull`参数。

## 验收记录（2026-10-30）

- 本地复用 `postgres:17.6-bookworm`，容器健康；独立库与检查点初始化完成，8466服务已重启并返回 `{"ready":true}`。
- 39项真实本地临时库回归通过，覆盖会话隔离、需求确认及重启恢复、资料、手记、费用确认和模拟试穿幂等；测试库已清理。
- 精简amd64镜像通过本地PostgreSQL预检、只读文件系统启动和健康检查。真实Docker Compose使用管道stdin的预检通过；安装器模拟测试覆盖私密配置、回退与旧CLI兼容性。
- 用户确认服务器版本 `20261030T080643Z-91a41c298fa0-2192` 部署成功，数据库连接、应用及HTTPS健康检查通过；采用v3私密包、从文件执行安装脚本。
- 工作区后续追加了stdin重定向、维护库优先查询和错误脱敏增强，不将这些变化视为v3已发布内容。
- 登录、衣橱、模型表现、历史持久化、真实费用及备份恢复仍分别验收；用户提供的部署输出不等同于助手远程复测。
