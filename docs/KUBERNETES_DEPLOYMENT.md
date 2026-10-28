# 衣衣 K8s 部署与任务恢复

本方案把常规滚动发布、浏览器连接中断和进程异常死亡分开处理。目标是用户不用重新输入需求，已经完成的步骤可以恢复；不承诺任何故障下都能保住原 SSE 连接、正在执行的模型请求或尚未回传的试穿结果。

代码和部署模板已提供，真实 PostgreSQL、多 Pod 接管、镜像构建和 K8s 发布演练仍需在目标环境验收。不要把本地 SQLite 回归等同于生产可用性保证。

## 部署结构

```mermaid
flowchart LR
  Browser[页面及自动重连] --> Gateway[Ingress 关闭流缓冲]
  Gateway --> A[Stylist Pod A]
  Gateway --> B[Stylist Pod B]
  A --> PG[(专用 PostgreSQL 数据库)]
  B --> PG
  A --> LLM[模型及只读业务接口]
  B --> LLM
```

两个 Pod 共享会话、幂等记录、图检查点和图像动作记录。不使用共享 SQLite 或把本地数据库放在 emptyDir。代码支持 `STYLIST_DATABASE` 为 PostgreSQL URL；本地未配置时仍用 SQLite。数据库事务目前以短期 advisory lock 串行保护业务状态，适合初期试点；并发量增大后应改为会话级行锁，而不是单纯增加 Pod。

PostgreSQL 自身应有独立备份和高可用措施；把单 Pod PostgreSQL 放在同一台节点上不构成服务高可用。数据库只存 stylist 自己的状态，不迁移旧服务的 MySQL 或 Agent 历史。

## 故障时的实际行为

| 情况 | 行为和边界 |
| --- | --- |
| 正常滚动发布 | 新 Pod ready 后，旧 Pod 先 drain、停止接新任务，尽量等在途生成完成 |
| SSE 断开、代理超时 | 任务在后台继续；浏览器使用原 request_id 自动重连，避免重复发起 |
| Pod 强杀、OOM、节点失联 | 连接和当前模型请求会丢失；在租约和数据库锁释放后，由重连恢复已完成步骤，当前节点可能重做 |
| 用户等待需求确认 | checkpoint 持久化暂停，恢复时验证登录态和会话版本 |
| 浏览器关闭且 Pod 随后死亡 | 本版没有独立任务队列，须用户再次打开页面触发恢复 |
| 已尝试付费生成但结果未知 | 保持 unknown/执行中，向上游核对；不自动重放收费请求 |

Kubernetes 会在优雅终止期限耗尽后强杀容器；preStop 时间也包含在期限内。PDB 只约束部分自愿驱逐，不能阻止 OOM、节点故障或直接删除。[Pod 生命周期](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)、[终止连接处理示例](https://kubernetes.io/docs/tutorials/services/pods-and-endpoint-termination-flow/)

## 配置

先建立独立数据库和应用账号，再以 Secret 注入：

```text
STYLIST_DATABASE=postgresql://USER:PASSWORD@HOST:5432/stylist?sslmode=require
STYLIST_CHECKPOINT_DATABASE=postgresql://USER:PASSWORD@HOST:5432/stylist?sslmode=require
STYLIST_SERVER_URL=https://实际Go服务域名
STYLIST_MCP_URL=https://实际MCP地址/mcp
STYLIST_LLM_URL=https://实际模型接口/v1
STYLIST_LLM_MODEL=实际模型标识
STYLIST_LLM_KEY=由Secret注入
```

Secret 名称为 `stylist-runtime`。不要把示例凭证替换为真凭证后提交 Git；使用平台的 Secret 管理方式创建。同一轮发布中，迁移 Job 和所有 Pod 必须指向同一套数据库。检查点自动使用业务 PostgreSQL，也可以指定独立的共享 PostgreSQL；不允许业务 PostgreSQL 配本地检查点。

生产模板设置 `STYLIST_ENV=production`，当前手机号登录代理会关闭。App 登录态接入尚需单独实现、验证；不能直接上线模板后宣称网页登录可用。第一次内部验收可用测试工具携带已有 Bearer，不要通过关闭生产保护来替代正式登录方案。

本模板不包含 Ingress。现有页面、CSS 和接口仍有 `/static`、`/api`、`/auth` 根路径，部署到原域名 `/mobile/` 前需要完成统一前缀适配，避免与旧服务冲突。独立测试域名可先将根路径路由到 Service；浏览器定位需要 HTTPS。

## 构建与发布顺序

1. 在 stylist 仓库运行 `uv sync --frozen --extra dev`、`uv run pytest -q`、`uv run ruff check stylist scripts tests`。
2. 使用仓库 Dockerfile 构建镜像并推送到镜像仓库，以 Git SHA 或 digest 固定版本。
3. 将 `deploy/k8s/migrate.yaml` 和 `stylist.yaml` 中的占位镜像替换为同一个不可变版本，Job 名使用合法的小写版本标识。
4. 执行迁移 Job，并等待成功；Job 创建业务表及 LangGraph 检查点表，不执行模型或收费接口。不要让每个 Pod 并发运行 checkpoint setup。
5. 应用 Deployment、Service、PDB，等待 `kubectl rollout status deployment/stylist`。
6. 验证带身份的只读天气、衣橱、普通咨询、需求确认及断线恢复，再接入业务流量。

GitLab CI 应按“测试 → 构建推送 → 迁移成功 → Deployment 更新 → 等待 rollout → 只读验证”执行。旧项目现有的 scp 加远端部署脚本流水线不能直接替代这些步骤。Kubeconfig、Registry 凭证及数据库配置通过 CI 或集群 Secret 提供；本次没有修改旧项目流水线或操作集群。

## 模板中的排空参数

- `replicas: 2`，`maxUnavailable: 0`，`maxSurge: 1`，新 Pod 连续 ready 10秒。
- preStop 向本机 `/internal/drain` 发请求，使 readiness 立即失败；再等待10秒传播路由变化。该接口仅接受回环地址；Ingress 不应暴露 `/internal`。
- Uvicorn 单进程、优雅等待260秒；lifespan 再给已断开订阅但仍运行的任务最多30秒；容器终止宽限330秒，留出退出余量。
- 模型单次超时默认90秒；节点重试和格式修复可能让总耗时超过排空窗口，因此窗口不是绝对完成保证。
- Ingress/负载均衡必须支持 POST SSE，关闭缓冲，空闲超时大于心跳间隔，并核对最大连接时长与终止连接行为。以实际安装的控制器配置为准，不能把某一厂商注解直接用于所有集群。
- 关闭 HTTP 自动跟随不可信转发头；模板的探针验证进程、业务库连通性和排空状态，不证明上游模型/MCP 已就绪。

不要在滚动发布中删除或重命名未完成执行所需的节点、State 字段和 thread 命名空间。当前执行图标记为 `sty-v1`；破坏性升级应先排空旧任务并制定兼容/迁移策略，不能只换 thread 版本后遗弃旧任务。

## 验收演练

1. 开始模拟的长耗时搭配请求，执行滚动更新；确认后台生成继续，前端原 request_id 最终拿到一次结果。
2. 在 style 执行中强杀 Pod，验证45秒租约到期后的接管；understand/weather/retrieve 不重复，style 允许重做。
3. 暂停需求确认，删除原 Pod，由另一 Pod 确认继续；错误用户和过期会话版本必须拒绝。
4. 断开网络再恢复、刷新浏览器，确认原请求被复用；更改同一个 request_id 的请求体应返回冲突。
5. 原 Pod 与新 Pod 同时尝试接管时，检查图执行锁和数据库提交 claim，最终仅有一条有效会话结果。
6. 使用模拟图像服务验证 unknown 状态不重放；真实扣费、退款和恢复另行明确授权验收。

本地自动回归已覆盖进程被实际 kill 后从磁盘检查点恢复、暂停后重建引擎确认/取消、跨账号隔离、断开订阅和 drain。真实 PostgreSQL、多 Pod、Ingress 行为需要上述环境演练。
