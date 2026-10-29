# 本地 MySQL 调试

仅用于当前 `ai_closet_stylist`。不修改旧 Agent，不连接远端数据库，不迁移现有 SQLite 历史。
默认 SQLite 保留；本机 `config/local.yaml` 指定数据库后，本地启动使用 MySQL。
环境变量 `STYLIST_DATABASE`、`STYLIST_CHECKPOINT_DATABASE` 优先于本机文件。

## 启动

Docker Desktop 启动后，运行：

```sh
uv run python scripts/setup_mysql_local.py
sh run-local.sh
```

初始化脚本只选择本机已有 MySQL 镜像，Compose 设置 `pull_policy: never`，不下载安装包或拉取镜像。
没有现成镜像或 Docker 未就绪时会退出并说明原因。

独立容器默认只绑定 `127.0.0.1:13306`，数据库 `stylist_local`，账号 `stylist`。
随机凭证仅保存到被 Git 忽略的 `config/mysql-local.env` 和 `config/local.yaml`，权限为 0600，不输出凭证。
数据持久化在独立 Docker 卷 `stylist-local_stylist-mysql`；停止容器不会删除数据。

脚本可重复运行，复用已有凭证与数据。可用 `--image 本机镜像:标签` 指定已有镜像。

```sh
docker compose --env-file config/mysql-local.env -f compose.mysql-local.yaml ps
docker compose --env-file config/mysql-local.env -f compose.mysql-local.yaml stop
```

恢复 SQLite：删除 `config/local.yaml` 中的 `database`、`checkpoint_database` 两项或用环境变量覆盖。
旧 SQLite 文件保留，MySQL 与 SQLite 的历史不互相同步。

## 存储范围

- `stylist_companion_profiles`：按账号保存称呼、角色及定制偏好。
- `stylist_sessions`、`stylist_requests`、`stylist_messages`：会话、幂等请求及历史。
- `stylist_image_actions`：试穿报价及执行状态，不代表真实扣费已验收。
- `stylist_checkpoints`、`stylist_checkpoint_writes`：LangGraph 检查点及节点结果，支持失败恢复和需求确认。

全部为本项目自己的表。身份、衣橱及业务积分仍通过原有 Go 服务接口访问。
这次适配没有新增旧 Agent 的长期记忆功能。
MySQL 连接串为 `mysql://用户名:URL编码后的密码@主机:端口/独立库名`；不接受查询参数。
禁止使用 `aicloset_dev`、`aicloset_test` 及系统库，避免误写旧数据域。
当前为单主 Agent 的本地调试方案：短业务事务采用数据库级命名锁，执行检查点使用请求级命名锁；不代表多副本生产压测通过。

## 验证

常规 `uv run pytest -q` 使用临时 SQLite 和模拟外部服务。
显式 MySQL 回归使用一次性本地测试数据库，通过 `scripts/check_mysql_local.py` 创建和删除，
沿用当前本机连接但拒绝非回环主机；不调用真实模型、衣橱写接口或付费生成。

```sh
uv run python scripts/check_mysql_local.py
```

## 本机验收记录（2026-10-29）

- 已复用现有 `mysql:8.0` 镜像启动 `stylist-local-mysql-1`，健康检查通过；未拉取镜像。
- 本机配置已选择 `127.0.0.1:13306/stylist_local`，七张本项目表已建立，SQLite 原文件保留。
- 一次性本机 MySQL 测试库中 22 项回归通过，测试后清理测试库；覆盖设置／偏好更新与重开读取、账号隔离、幂等重放、并发竞争、事务回滚、过期执行者拒绝、确认／取消／重启恢复、硬中断进程恢复、检查点无 Bearer，以及模拟试穿重复确认与未知状态。
- 外部服务均为模拟，没有调用真实模型或付费图像生成，不表示真实收费／退款通过。
- 本地 8466 服务已重启并通过 `/health/ready`，当前使用 MySQL；无测试会话写入 `stylist_local`。
- 常规回归 367 项通过，22 项真实 MySQL 用例默认跳过、由上述显式命令单独执行；Ruff 和 Git 差异格式检查通过。

## 长记忆扩展（2026-10-29）

新增本项目表 `stylist_memory_books`，启动时通过已有幂等建表流程创建，不迁移旧业务数据。长记忆相关回归纳入真实本地一次性库验证，本轮共40项通过（外部服务仍模拟）。接口、快照与验收范围见 [LONG_TERM_MEMORY.md](LONG_TERM_MEMORY.md)。
