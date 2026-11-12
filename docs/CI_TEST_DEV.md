# test／dev CI自动部署

已获用户授权提交并推送company/test触发首次流水线；运行结果待验证。

## 入口

根目录.gitlab-ci.yml的DEPLOY_ENV取test或dev，默认test。test分支推送自动构建部署；其他分支推送不部署，在GitLab Run pipeline中手动运行时可选择DEPLOY_ENV。这保留原普通分支手工打包习惯，不把main自动对应到生产。

| DEPLOY_ENV | 页面／ops／stylist-api域名 | Server与MCP | 宿主端口 |
|---|---|---|---|
| test | https://aicloset-agent.wxbjq.top | https://aicloset-test.wxbjq.top 与/mcp | 8465 |
| dev | https://aicloset-assistant.wxbjq.top | https://aicloset-dev.wxbjq.top 与/mcp | 8466 |

用户最新指定PostgreSQL分库：dev为aicloset_stylist，test为aicloset_stylist_test；当前连接实例和账号可沿用原配置，但库名不得交叉。不复制／迁移弃用Agent旧库。检查点默认跟随本环境业务库；显式设置检查点DSN也必须匹配本环境库名。结算环境沿用当前test。Langfuse暂不使用：不要求相关配置，部署时过滤旧LANGFUSE配置并显式停用追踪。

## 新的脚本链路

沿用devops-test Runner与172.16.0.91内网上传／SSH通道；不再调用服务器的未知deploy-aicloset-agent.sh，也不再写CIHOME/.env。

1. scripts/ci_package.sh按白名单打源码包，包名包含环境、流水线ID及提交；排除配置、数据、报告及私有截图。
2. build job上传源码包和SHA256。
3. deploy job通过SSH执行仓库deploy/ci/deploy.sh，不需要预装该脚本或宿主Python。
4. 目标机校验压缩包、构建镜像，在容器里核对Server、MCP、PostgreSQL及模型／ops配置，然后做独立库及结构只读预检。
5. 不绑定宿主端口的候选容器先验收H5、静态资源、ops和API鉴权；通过后才停止选定端口的已知旧容器。
6. 新容器启动后校验公网三个入口及/health中的revision与本次提交一致。失败停止新容器、恢复实际旧容器；部署不执行数据库结构变更。
7. 全部成功后更新环境配置和current-test／current-dev。各发布保留独立配置快照，密钥不打印／不进入构建上下文。

服务器flock串行化部署，避免并行发布或共享端口竞争；不停止未知服务。不修改Nginx，现有域名必须已经代理到表中对应端口，代理不匹配会验收失败并恢复旧服务。

普通dev离线安装器可识别本脚本创建的dev容器，后续手工安装仍可切换回Compose；成功后保留旧容器为previous，失败恢复原CI容器，不影响test环境。

## 一次性私密配置

实际配置仅保存在部署服务器，不经GitLab上传，不放源码包／镜像：

```text
/opt/aicloset-agent/config/
├── test.env
├── dev.env
└── login-public.pem
```

DEPLOY_ENV=test读取test.env，dev读取dev.env；env权限0600。公钥也可复用既有/opt/aicloset-assistant/config/login-public.pem。GitLab只保留DEPLOY_ENV等非敏感部署参数，不需要STYLIST_TEST_ENV_FILE、STYLIST_DEV_ENV_FILE等私密File变量。

模板为deploy/test.env.example和deploy/dev.env.example。PostgreSQL库名按模板分别填写，不能把dev.env直接复制成test.env而不改库名；MySQL账户只读查询配置暂沿用现有值。env使用原始KEY=value，不额外加shell引号。Langfuse已移除，不必配置密钥；旧配置中的LANGFUSE行也不会载入容器。实际配置不进Git／报告／镜像。仅设置CI变量而不将业务配置加载进目标容器，不构成配置生效。

仍需实际验证新GitLab项目可使用devops-test Runner及其SSH权限。此次本地验证采用假Docker／Nginx及临时库，不代表远程构建、域名代理、上游带身份API、数美或试穿扣费已验收；候选页面／API检查不执行收费。

## 传输与构建优化（2026-11-12）

CI不反复传完整离线镜像：Runner只传源码白名单包，服务器保留Docker镜像和构建缓存。打包按.dockerignore中由OSS清单生成的排除段跳过远程图片，保留运行所需ONNX和WASM；本机实测262,466,946字节缩为8,667,924字节（250.31→8.27MiB，约减少96.7%）。这是本轮样本，不保证后续包固定大小。

Dockerfile先安装uv与锁定依赖，再复制业务源码并安装本项目。代码变化不再使前置依赖层失效；依赖锁文件变化仍正常重装。首次构建需要拉基础镜像／依赖，缓存被清理或更换服务器后也需重新准备。未测目标服务器构建耗时，不承诺固定部署秒数。

手动离线包交付方式保留。以后若已有镜像仓库，可再改为Runner构建及推送、目标拉取缺少的层；目前不为了CI另引入仓库与权限配置。

本轮本机Docker冷构建通过；从CI压缩包解出的同一构建目录再做代码单独变更，uv安装与锁定依赖步骤均显示CACHED，仅项目安装步骤约5.2秒。隔离无网络容器检查H5、ops、API鉴权、212条OSS重定向及2个ONNX／WASM资源通过；不代表目标服务器或OSS外网下载已实测。

环境校验在任何停服之前运行：test仅接受aicloset_stylist_test，dev仅接受aicloset_stylist，同时校验Server、MCP及用量回调。CI不会自动建库或回退其他数据库；预检默认仍保护手工dev部署，test显式传--database-name aicloset_stylist_test。CI设置STYLIST_REQUIRE_MIGRATIONS=true，使stylist/migrate.py和Store仅校验既有结构；本地开发保留自动初始化。

## 当前完整建表 SQL

运维执行 `stylist/migrations/postgresql/001_initial.sql`：包含当前全部业务表、LangGraph检查点表及索引，不按历史增量拆分，也不增加自定义迁移台账。dev连接 `aicloset_stylist`，test连接 `aicloset_stylist_test`；脚本不创建或切换数据库。CI先校验环境库名，再只读检查表和索引；缺少时停止部署，交由运维执行SQL。已有旧表缺列不能靠CREATE IF NOT EXISTS修复，需要单独核对后处理。

历史列表沿用 `(owner_id, updated_at)` 索引；消息增加 `(owner_id, conversation_id, version)` 索引，支持账户隔离、正反序及版本范围查询。消息正文和卡片JSON不加入索引，避免索引膨胀；主键及唯一约束已自动建立对应索引。

验证：32项定向回归通过；隔离PostgreSQL 17.6上首次建表和重复执行通过。1000会话／10万条模拟消息中，正序历史读取与倒序版本范围读取均命中stylist_messages_owner_conversation_version，无额外排序；此为本机模拟数据，不代表远程性能。真实dev/test数据库未执行本SQL。

部署SQL边界：仅CI禁止自动执行建库、建表、索引及检查点迁移，缺少结构就中止，由运维手动执行SQL。本地开发仍可自动初始化，普通手动入口不因本条受限。

## 同机dev/test与Nginx一次性准备

两个环境同机：服务器config下分别放dev.env、test.env，共用login-public.pem；代码和脚本由CI上传，无需手动预装。test数据库手工创建并执行001_initial.sql。test域名aicloset-agent.wxbjq.top应整站代理127.0.0.1:8465；dev域名aicloset-assistant.wxbjq.top继续8466。仓库新增deploy/nginx/aicloset-agent.locations.inc供替换原-agent HTTPS server内的location，保留既有证书及监听；不是完整server配置，不可直接覆盖整个站点文件。旧更具体的location可能覆盖新代理，需核对nginx -T后处理。现有服务器配置尚未读取，不据此认定一定需要修改。CI不修改Nginx。

2026-11-12 用户提供服务器nginx -T：已加载assistant→8466，未匹配agent站点；新增独立agent→8465模板deploy/nginx/aicloset-agent.centos7.conf，复用现有证书路径，独立AgentTLS缓存区，不修改assistant／test Server站点。尚需服务器nginx -t、reload及DNS／HTTPS实际验证，不据当前输出认定DNS已指向本机。

2026-11-12 CI复核：修复.gitignore临时文件规则误忽略.sql，收窄为*.sw[a-z]；30项CI／SQL／数据库预检回归通过，实际生成源码包并确认包含001_initial.sql、预检模块及启动脚本，排除私密配置和编辑器交换文件。未触发真实流水线。

2026-11-12 GitLab旧版兼容修复：首次流水线197492报jobs:workflow config contains unknown keys: rules；按同级aicloset-server的基础结构改为variables/stages及job内script/tags/only，移除workflow/default/resource_group/environment。only=test或web，推送test自动运行，其他分支只接受网页手动运行；DEPLOY_ENV仍由脚本校验test/dev，服务器flock保留并发锁。

兼容修复验证：直接调用本机GitLab实例/api/v4/ci/lint返回HTTP 200、status=valid、errors=[]；20项定向回归通过。此为目标实例语法验证，不代表构建／部署完成。
