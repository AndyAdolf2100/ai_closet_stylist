# Agent＋H5：K8s＋Nacos 运维交接

日期：2026-11-11。代码核对基线：454b481；最近已构建离线包为17b72e8，之后的头像破圆与空白手记修复尚未重新打包。本文为迁移建议与交接清单，尚无已验收的K8s清单、Nacos同步器或集群部署。

## 1. 当前支持范围

- 应用是Python/FastAPI，同一镜像包含Agent API及H5。监听8000，Linux amd64；容器非root UID/GID 10001。
- Settings.load()在创建应用时读取配置，没有Nacos客户端、配置监听或全量热更新。NACOS_SERVER_ADDR等变量当前不会自动生效。
- 推荐首期：Nacos普通配置 → 运维平台同步到ConfigMap → envFrom注入；Secret单独注入。配置版本变化触发受控Pod更新。同步器由运维现有平台提供，否则需新增实现。
- 也可用initContainer拉取配置到共享卷，但STYLIST_*配置必须由启动包装器解析成环境变量；把任意YAML挂进去不会自动变成这些环境变量。不要直接source未经校验的配置文本。
- Nacos的namespace/group/dataId由运维按实际版本确定；下面的名字仅建议，不是现有资源。开发、测试、生产使用不同namespace和Secret。

## 2. 可以放Nacos的普通配置

建议Group：AICLOSET_STYLIST；Data ID：stylist-runtime.env。通过平台转成ConfigMap键值后注入环境变量。

| 当前有效变量 | 用途与交接口径 |
|---|---|
| STYLIST_SERVER_URL | Server根地址，按环境填写；生产优先使用可达的受信任服务地址 |
| STYLIST_MCP_URL | 同环境MCP完整地址；域名、路径、鉴权与Server确认 |
| STYLIST_USAGE_CALLBACK_URL | 模型用量接收完整地址；为空会停止投递，不等于关闭本地计量；非loopback地址须HTTPS |
| STYLIST_USAGE_ENVIRONMENT | test/development/production由业务确认；与STYLIST_ENV独立，不能仅因上K8s就切production扣费 |
| STYLIST_LLM_URL | 真实模型API根地址；不含key |
| STYLIST_LLM_MODEL | 实际开通的模型ID |
| STYLIST_LOGIN_APP_VERSION | 传给账号服务的App版本，当前示例1.2.0，需与Server确认 |
| STYLIST_ALLOW_MOBILE_LOGIN | 本次K8s部署设false，复用App／宿主Bearer，不开启依赖旧PEM的独立手机号入口 |
| STYLIST_PURCHASE_WEB_URL | 正式H5根地址，用于协议等链接；不要带用户token |
| STYLIST_ALERTS_URL | 可选官方预警服务地址，无提供商则留空 |
| STYLIST_GEOCODER_URL | 可选反向地理编码地址，当前默认nominatim.openstreetmap.org/reverse；需确认出网及服务条款 |
| LANGFUSE_BASE_URL | 当前环境Langfuse服务地址；须从Pod内验证可达 |
| LANGFUSE_TRACING_ENABLED | true/false追踪开关；还需同时配置两项项目密钥才启用 |
| LANGFUSE_TRACING_ENVIRONMENT | development/test/production追踪标签；与业务扣费环境独立 |

普通配置建议例（必须由运维替换占位值后发布）：

```properties
STYLIST_SERVER_URL=https://<server-host>
STYLIST_MCP_URL=https://<server-host>/mcp
STYLIST_USAGE_CALLBACK_URL=https://<server-host>/api/internal/stylist/model-usage
STYLIST_USAGE_ENVIRONMENT=test
STYLIST_LLM_URL=https://<model-provider>/api/v3
STYLIST_LLM_MODEL=<actual-model-id>
STYLIST_LOGIN_APP_VERSION=1.2.0
STYLIST_ALLOW_MOBILE_LOGIN=false
STYLIST_PURCHASE_WEB_URL=
STYLIST_ALERTS_URL=
```

接口地址使用当前系统既有路由，不在此次迁移中转换/api与/stylist-api前缀。真实扣费环境、价格规则和Server侧Agent来源限制单独联调。

## 3. Secret与文件配置

| 内容 | 建议载体 | 当前接入方式 |
|---|---|---|
| 模型API Key | Secret或企业密钥服务 | 环境变量STYLIST_LLM_KEY |
| PostgreSQL连接串（含账号密码） | Secret | STYLIST_DATABASE，完整postgresql://连接串，用户名密码须URL编码 |
| 检查点库连接串 | Secret | STYLIST_CHECKPOINT_DATABASE；留空使用同一业务PG库 |
| 预警服务密钥 | Secret | STYLIST_ALERTS_KEY，可选 |
| 系统知识库AK/SK | Secret＋受限生成文件 | 当前读取local.yaml的db_knowledge，见下节；没有对应STYLIST_CATALOG_AK之类环境变量 |
| Nacos自身访问凭据 | 供同步器/initContainer的Secret | 当前应用不消费Nacos认证变量 |

新增私密配置：`LANGFUSE_PUBLIC_KEY`与`LANGFUSE_SECRET_KEY`作为同一环境的项目凭证由Secret注入，不进入镜像或普通Nacos配置。`STYLIST_OPS_MYSQL_DSN`仅在需要手机号解析时配置，建议使用最小只读权限的MySQL账号；代码只读事务精确查询有效用户ID，不写旧MySQL数据域。未配置时仍可显式用用户ID查询会话。

用户2026-11-11确认登录公钥PEM已不再使用，本次K8s交接不配置STYLIST_LOGIN_PUBLIC_KEY，也不创建PEM挂载。按复用App／宿主Bearer的部署方式，STYLIST_ALLOW_MOBILE_LOGIN=false。代码核对发现旧手机号验证码入口仍有RSA加密依赖，开启该旧入口会重新触发PEM要求；该兼容代码与旧单机Compose挂载尚未移除，不能把本交接结论理解为已修改Server登录协议。若实际仍需H5独立手机号登录，需先确认新登录接口契约并改造，而不是直接删除加密。

同一个key只由一个来源管理，避免envFrom覆盖顺序造成错误。不要把用户Bearer、手机号、对话内容、用户图片或数据库数据放Nacos。

## 4. 系统知识库不能漏迁

邂逅新衣的知识库配置由CatalogConfig.load读取，支持STYLIST_LOCAL_CONFIG指向的YAML中的db_knowledge（以及可选legacy配置）。该文件不是通用Settings全部字段的YAML映射。

- 普通字段可由Nacos管理：enabled、api_endpoint、collection_name、project、doc_id_field/doc_id_value、签名region/service、search.dense_weight、rerank_enabled/rerank_model、default_model/default_model_version、timeout_s。
- AK/SK走Secret。由平台或initContainer安全合并成受限YAML，应用用户10001须可读；程序不会自动替换YAML里的`${SECRET}`。
- 推荐STYLIST_LOCAL_CONFIG=/run/stylist/local.yaml。直接db_knowledge或其profiles.legacy内容必须沿用CatalogConfig.load实际字段结构。
- 必须迁移正确collection和doc_id筛选范围，不能只迁移主模型配置。缺失时知识库不可用，系统检索会按现有兼容路径尝试MCP，不等于原检索能力已迁移成功。
- STYLIST_LEGACY_CONFIG仅作旧配置兼容，首期也可挂载受限文件；不要把整个旧项目或含密钥的配置提交到Git/镜像。

## 5. 固定在K8s部署模板中的配置

| 项 | 交接要求 |
|---|---|
| STYLIST_ENV | 固定production，影响登录边界；不决定模型用量是否扣费 |
| STYLIST_REQUIRE_POSTGRES | 字符串true，防止容器误用默认SQLite |
| LANGSMITH_TRACING | 保持false，除非另行批准与配置追踪 |
| STYLIST_LOCAL_CONFIG | 只有迁移知识库/本地YAML时设置成实际挂载路径 |
| workers | 初期保持1，每个Pod一个进程 |
| replicas | 初期1，扩容前验证跨Pod行为；滚动期间也可能短暂出现多Pod |
| 资源、镜像digest、端口、探针、卷 | Deployment/Service/Ingress管理，不作为业务Nacos配置 |

重要：request_timeout、llm_timeout、image_timeout、max_candidates、cors_origins虽存在于Settings数据类，但Settings.load没有相应环境变量入口。不能编造STYLIST_LLM_TIMEOUT/STYLIST_CORS_ORIGINS等键并假设已生效；需要开发先补接入和回归。

## 6. 镜像与启动交接

本地最近已验证完整包：`var/releases/agent-h5-dev-20261111-17b72e8/delivery/`，基于17b72e8，不包含之后已提交的65c88d2与454b481。准备发布当前main前应重新构建，不把旧包视为最新源码。

- 包内image.tar是离线镜像，可在受控构建机docker load后，改tag推至企业镜像仓库；Deployment使用仓库地址及实际digest。该已构建镜像tag为`aicloset-stylist:agent-h5-dev-20261111-17b72e8-amd64`；迁入企业仓库后使用实际仓库digest。
- 不在K8s里执行install.sh：该脚本管理单机/opt目录、Docker Compose、宿主Nginx。K8s负责这些职责的替代。
- 容器默认ENTRYPOINT为/bin/sh /usr/local/bin/stylist-start，CMD为/app/.venv/bin/uvicorn stylist.main:app --host 0.0.0.0 --port 8000 --workers 1 --timeout-graceful-shutdown 260 --no-proxy-headers。
- 保持ENTRYPOINT时优先用args覆盖CMD。随意设置command会绕过现有预检与迁移。
- 现有启动入口执行python -m stylist.migrate；迁移也可作为独立Job运行，但当前入口没有SKIP_MIGRATIONS开关，职责拆分需开发改造并验证，不能由运维假设已支持。
- PG是专属Stylist库；不迁移/写入旧MySQL数据域。所有Pod用同一业务PG和共享检查点库，不把SQLite放到共享PVC冒充多副本数据库。
- /app/var与/tmp需可写，可评估emptyDir；数据库持久数据放PG，不依赖Pod本地文件。启用readOnlyRootFilesystem时保留这些可写挂载与用户权限。

## 7. 探针、流式请求与网络

- startupProbe：/health/ready，按PG初始化/迁移耗时设置启动预算。
- readinessProbe：/health/ready，包含数据库探测和draining状态。
- livenessProbe：/health，避免将PG故障直接变成应用不断被重启。
- Service targetPort=8000；Ingress使用实际控制器支持的SSE设置，关闭缓冲，读/写空闲超时先参照既有Nginx的600秒，并验证网关全链路。
- 放行至PG、Server/MCP、模型供应商、OSS图片域名；启用知识库/地理编码/预警时相应放行。
- 启用Langfuse时，从Pod内验证其health与实际trace入库；SDK加载、enabled=true和client创建成功不能证明网络可达或记录已入库。默认dev包的追踪标签为development，不据此更改STYLIST_USAGE_ENVIRONMENT。
- 运维手机号入口另需可达的只读MySQL连接。`/ops/conversations`与`/stylist-api/ops/records/*`当前没有独立管理员登录，应由内部Ingress／网关限制访问；普通用户Bearer不等于运维权限。
- /internal/drain不能暴露外网；代码只接受loopback请求，preStop需在容器内exec Python向127.0.0.1:8000发POST，不能用普通HTTP GET钩子代替。

## 8. 更新与多副本的当前限制

- 可参考现有330秒退出预算，但K8s的terminationGracePeriodSeconds覆盖preStop和退出全过程；这个值不是“对话必定不中断”的承诺。
- 当前RunManager.tasks和停止标记在进程内，跨Pod停止不可靠；粘性路由只能缓解，不代替共享停止控制。
- 停机时RunManager.close()仅等待后台任务30秒；Uvicorn另有260秒优雅退出参数，两者作用不同。断开流后的后台任务、Pod强杀仍可能影响进行中的调用。
- 用量事件已落数据库，但回调需要的用户Bearer缓存在进程内；重启后待投递记录可能等待该用户再次提供有效token。运维不能把这一点当成Nacos可恢复的配置。
- 单Pod/单worker也不保证滚动期间单进程。两副本、HPA、maxUnavailable=0都不能直接宣称无损发布；上线前需跨Pod重连/停止、幂等、费用上报与排空专项验收。
- PG连接预算需覆盖滚动时的新旧Pod、检查点和请求并发；目前Store按操作连接，没有统一业务连接池/全局并发准入，不按历史在线人数直接设置HPA上限。

## 9. 双方交付与验收

开发提供：镜像/源码版本、有效配置键清单、Secret引用格式、应用启动/探针路径、依赖服务清单、当前限制与回归证据。实际密钥由受控渠道提供，不写本文。

运维提供：K8s namespace、企业registry/digest、Nacos版本与namespace ID/group/data ID、配置同步组件及负责人、Secret托管方案、PG连接额度、Ingress控制器/域名/TLS、出网策略、资源额度、更新与回滚流程。

首期验收：

1. 缺少模型key/PG配置时启动拒绝；正确配置正常ready，重启后历史仍可读。
2. Nacos普通配置更新后由平台触发受控Pod更新，确认新进程实际生效；不能只看Nacos发布成功。
3. 使用App／宿主已验证的Bearer测试账号，验证身份鉴权、SSE、停止、重连、历史及软删除的账号隔离。
4. 有库存未匹配/空候选＋定位天气时返回文字原因与双入口；开启邂逅新衣后真实系统检索可用。
5. 模型用量上报200、稳定event_id幂等、失败重试；重启后的待投递事件恢复单独验证。真实扣费须另行授权与对应价格规则。
6. 验证照片风险拒绝422、检测暂不可用503和原回执恢复；收费图片/上传需单独明确范围。
7. 核对更新排空和回滚，先记录真实中断边界，再决定是否允许多副本/HPA。

## 官方参考

- Nacos配置维度与职责：https://nacos.io/en/docs/v3.2/manual/user/config/overview/ （示例文档版本不代表集群实际版本）
- ConfigMap环境变量更新需要替换Pod：https://kubernetes.io/docs/tutorials/configuration/updating-configuration-via-a-configmap/
- Pod退出与preStop预算：https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/
