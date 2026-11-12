# Agent＋H5 CI 打包与部署完整流程

更新：2026-11-12。适用仓库：`ai_closet_stylist`；GitLab项目：`ai_closet/ai_closet_agent_new`。

本手册覆盖首次配置、日常发布、配置更新、SQL、离线依赖镜像、验收和故障处理。CI负责Agent＋H5，不包含report／UI change log。所有SQL由运维手动执行，CI只读检查结构。

## 1. 环境与入口

两个环境在同一服务器，内网IP为 **172.16.0.90**。旧项目里的172.16.0.91不是当前部署目标。

| 项目 | dev | test |
|---|---|---|
| Git分支 | main | test |
| 分支默认DEPLOY_ENV | dev | test |
| job的only | main、web | test、web |
| 页面域名 | https://aicloset-assistant.wxbjq.top | https://aicloset-agent.wxbjq.top |
| Server | https://aicloset-dev.wxbjq.top | https://aicloset-test.wxbjq.top |
| MCP | Server地址＋/mcp | Server地址＋/mcp |
| PostgreSQL | aicloset_stylist | aicloset_stylist_test |
| ops MySQL | aicloset_dev | aicloset_test |
| 宿主监听 | 127.0.0.1:8466 | 127.0.0.1:8465 |
| 容器名 | aicloset-agent-dev | aicloset-agent-test |
| 服务器配置 | /opt/aicloset-agent/config/dev.env | /opt/aicloset-agent/config/test.env |

容器内部统一监听8000。数据库实例、账号可以按实际授权共用，库名必须分开。`STYLIST_ENV=production`是程序部署模式，不是连接生产业务环境；`DEPLOY_ENV`仅接受`dev`、`test`，不填`development`。当前没有prod自动部署配置。

每个域名的入口：

| 功能 | 路径 |
|---|---|
| H5 | /app/?design=yijian |
| 正式引导入口 | /app/?design=yijian&screen=onboarding，仍受登录及资料状态控制 |
| 运维查询 | /ops/conversations |
| Agent接口 | /stylist-api/…，保留前缀 |
| 存活／提交版本 | /health |
| 就绪检查 | /health/ready |

`/ops`、`/ops/`目前没有路由，404不代表运维页面故障。Server的`/api`、`/users`、`/mcp`走各环境Server地址，不另改成Agent域名。

## 2. 三条发布方式及边界

| 方式 | 交付内容 | 谁执行 |
|---|---|---|
| 本手册CI | 小体积源码包，目标服务器离线构建镜像并部署 | GitLab Runner自动执行 |
| 手工Agent＋H5离线发布 | 完整离线交付包及镜像 | 用户要求打包后单独准备，沿用原安装流程 |
| report／UI change log | 本地reports中的独立文档包 | 单独让Agent打包、打开目录并提供部署命令 |

CI不上传私密env、登录公钥、用户数据、report或私有截图；不修改Nginx，不执行建库／建表／索引SQL，不执行真实收费验收。report截图补传OSS使用当次用户提供的token，不从旧记录寻找或复用token。已有OSS链接不重复上传。

## 3. 先理解CI实际做什么

1. Runner检出提交；`job_build`调用`scripts/ci_package.sh`。
2. 按白名单生成源码压缩包和SHA256，scp到目标机`/tmp/`。
3. `job_deploy`经SSH从标准输入执行仓库的`deploy/ci/deploy.sh`，不依赖服务器旧部署脚本。
4. 服务器使用`flock`串行化部署，校验包摘要、路径及文件类型，解出独立发布目录。
5. 读取所选环境env并建立私密快照，挂载登录公钥；过滤旧`LANGFUSE_`配置。
6. 按`uv.lock`摘要查找已导入的离线运行依赖镜像，验证锁文件及关键依赖。
7. 使用`deploy/ci/Dockerfile.offline`执行`docker build --pull=false --network none`；先删除旧应用目录，再复制当前源码。构建不执行pip／uv在线安装。
8. 在新镜像内校验Server、MCP、回调地址、PostgreSQL库名、模型、ops和Langfuse停用状态。
9. 只读检查数据库连接、所需表名及索引名。当前不是完整的列、类型及索引定义差异审计。
10. 启动不绑定宿主端口的候选容器，检查就绪、H5、静态资源、ops、API鉴权及必要OpenAPI路径。
11. 通过后才停止所选端口的已知旧容器，启动正式新容器；未知端口占用直接中止，不强杀其他服务。
12. 再验证公网H5、ops、静态资源、就绪、API未登录401及`/health`提交版本。
13. 全部成功后更新环境配置和`current-dev`／`current-test`链接。失败时清理候选容器；若旧服务已停止，则尝试恢复旧容器。

本地源码包样本约8～9MiB，大小随资源变化，不是固定值。OSS清单中已有重定向的图片不重复进入源码包；运行所需ONNX、WASM和许可保留，本地资源不因此删除。

## 4. 首次准备：GitLab与服务器

### 4.1 GitLab

- CI文件名为根目录`.gitlab-ci.yml`，不是`.gitlab.yml`。
- 使用与同级Server一致的基础关键字：`variables`、`stages`、job内`script/tags/only`。当前旧GitLab不使用`workflow/rules/default/resource_group`。
- 项目启用标签为`devops-test`的Runner，Runner在线且分支保护设置允许它运行目标分支。
- Runner需要免密SSH到`root@172.16.0.90`并scp到`/tmp/`。用户能经跳板登录不等于Runner具备权限。
- CI默认变量：`DEPLOY_HOST=172.16.0.90`、`DEPLOY_ROOT=/opt/aicloset-agent`。检查项目／组变量是否覆盖它们。
- 数据库、模型等凭证不放GitLab变量；只保存在服务器私密env。

`only`的分支与`web`为“或”：匹配分支推送自动执行，网页Run Pipeline也可以执行；`web`不是分支名。具体支持性已通过目标GitLab的CI Lint验证。

### 4.2 服务器基础条件

需要Bash、Docker、tar、sha256sum、flock、curl、ss，以及可供运维手动检查数据库的psql。宿主机不需要Python或Docker Compose来运行这套CI。

```bash
hostname
hostname -I
sudo docker version
sudo /usr/local/nginx/sbin/nginx -t
```

确认目标IP包含172.16.0.90；172.17／172.18地址通常是容器网桥。需要从容器网络访问数据库、模型及各环境Server；“离线构建”不表示运行时不需要网络。

### 4.3 创建目录、安装配置

本地准备好的文件位于忽略目录`config/ci/dev.env`、`config/ci/test.env`和`config/login-public.pem`。公开模板在`deploy/dev.env.example`、`deploy/test.env.example`，模板占位符必须填写，不能直接部署。

通过跳板把实际文件传到`/tmp/`，再在服务器执行：

```bash
sudo mkdir -p /opt/aicloset-agent/config
sudo chmod 700 /opt/aicloset-agent/config
sudo install -m 600 /tmp/test.env /opt/aicloset-agent/config/test.env
sudo install -m 600 /tmp/dev.env /opt/aicloset-agent/config/dev.env
sudo install -m 644 /tmp/login-public.pem /opt/aicloset-agent/config/login-public.pem
```

`install`是复制并设权限，不是移动。确认成功后手动清理`/tmp`中的私密env副本；不要打印文件全文或发到日志。仅先发布test时可稍后安装dev.env。公钥可复用服务器已有的`/opt/aicloset-assistant/config/login-public.pem`，不需要上传私钥。

不需要手动在`/opt`克隆项目或预装部署sh。CI自动建立：

```text
/opt/aicloset-agent/
├── config/                       # 两份实际env及登录公钥
├── releases/dev/<时间-提交>/
│   ├── source/                   # 当前发布源码
│   └── private/                  # 0600配置快照及公钥
├── releases/test/<时间-提交>/
├── current-dev -> releases/dev/…
├── current-test -> releases/test/…
└── deploy.lock
```

### 4.4 配置项说明

| 配置 | 用途／要求 |
|---|---|
| STYLIST_SERVER_URL | 对应环境Server地址 |
| STYLIST_MCP_URL | 对应环境Server地址＋/mcp |
| STYLIST_LLM_URL／MODEL／KEY | 当前实际对话模型的地址、名称、密钥，必填 |
| STYLIST_LOGIN_APP_VERSION | 发送给Server的登录请求version，当前保留1.2.0，不是Agent版本 |
| STYLIST_ALLOW_MOBILE_LOGIN | H5手机号验证码登录开关，需要时true |
| STYLIST_DATABASE | 本环境PostgreSQL完整DSN，库名见环境表 |
| STYLIST_CHECKPOINT_DATABASE | 可留空，默认跟随业务PostgreSQL，001包含检查点表 |
| STYLIST_ALERTS_URL／KEY | 可选气象预警服务，当前留空；不影响普通天气查询 |
| STYLIST_OPS_MYSQL_DSN | ops手机号查询的只读MySQL，test=aicloset_test，dev=aicloset_dev |
| STYLIST_USAGE_CALLBACK_URL | 本环境Server＋/api/internal/stylist/model-usage |
| STYLIST_USAGE_ENVIRONMENT | 当前两环境结算标签均保留test，不控制数据库选择 |
| STYLIST_REQUIRE_POSTGRES | 部署要求PostgreSQL，true |
| STYLIST_REQUIRE_MIGRATIONS | CI必须true，禁止Store／启动流程自动初始化结构 |
| STYLIST_ENV | 部署模式production，不是业务生产库选择器 |
| STYLIST_LOGIN_PUBLIC_KEY | 容器内/run/stylist/login-public.pem；H5登录加密手机号，与SSH无关 |
| STYLIST_SEED_LLM_KEY／MODEL、STYLIST_DEEPSEEK_LLM_KEY／MODEL | 若旧env仍保留，当前主服务不读取，不会自动切换模型 |

env为原始`KEY=value`，不加shell引号，不source执行。Langfuse当前停用，不需要相关密钥。CI会显式设置构建提交、部署模式和SQL只读开关，不要依赖在env里关闭这些保护。

## 5. 首次准备：手动执行SQL

**本节仅由运维手动执行，不放入CI脚本。** dev和test分别连接自己的库。原MySQL属于Server数据域，不在这里建表或迁移。

初始化文件：[`stylist/migrations/postgresql/001_initial.sql`](../stylist/migrations/postgresql/001_initial.sql)。包含当前完整16张表和必要索引，不按过去的新增顺序拆分。上传到`/tmp/001_initial.sql`。

以下以test为例；dev应使用dev.env及aicloset_stylist。以下维护库DSN写法适用于当前env中不带查询参数的PostgreSQL URI。

```bash
STYLIST_TEST_DSN=$(sudo sed -n 's/^STYLIST_DATABASE=//p' /opt/aicloset-agent/config/test.env)
if [ -z "$STYLIST_TEST_DSN" ]; then
  echo '未读取到STYLIST_DATABASE，请停止并检查配置'
else
  psql "${STYLIST_TEST_DSN%/*}/postgres" -v ON_ERROR_STOP=1 \
    -c "SELECT datname FROM pg_database WHERE datname IN ('aicloset_stylist','aicloset_stylist_test');"
fi
```

仅在test库不存在且变量非空时，手动创建：

```bash
psql "${STYLIST_TEST_DSN%/*}/postgres" -v ON_ERROR_STOP=1 \
  -c 'CREATE DATABASE aicloset_stylist_test;'
```

先确认当前连接是test，再执行SQL：

```bash
psql "$STYLIST_TEST_DSN" -v ON_ERROR_STOP=1 -c 'SELECT current_database();'
# 输出必须是aicloset_stylist_test，确认后再执行下面一条。
psql "$STYLIST_TEST_DSN" -v ON_ERROR_STOP=1 -f /tmp/001_initial.sql
psql "$STYLIST_TEST_DSN" -v ON_ERROR_STOP=1 -c '\dt public.*'
```

应显示COMMIT并列出16张表。检查点表包括checkpoint_migrations、checkpoints、checkpoint_blobs和checkpoint_writes。

已有dev库16张表齐全，但缺消息索引时，仅手动补该索引，不重跑其他DDL：

```bash
STYLIST_DEV_DSN=$(sudo sed -n 's/^STYLIST_DATABASE=//p' /opt/aicloset-agent/config/dev.env)
psql "$STYLIST_DEV_DSN" -v ON_ERROR_STOP=1 -c 'SELECT current_database();'
# 输出必须是aicloset_stylist，确认后再执行。
psql "$STYLIST_DEV_DSN" -v ON_ERROR_STOP=1 <<'SQL'
CREATE INDEX CONCURRENTLY IF NOT EXISTS stylist_messages_owner_conversation_version
ON public.stylist_messages (owner_id, conversation_id, version);
SQL
```

消息联合索引支持owner_id、conversation_id隔离及version正反序／范围读取；历史列表沿用(owner_id, updated_at)索引。不把消息正文和卡片JSON放入索引。

`CREATE IF NOT EXISTS`不会修复旧表缺列，也不会纠正同名但定义错误的索引；有此类结构变化时，先人工审核并执行对应SQL，再部署。失败的并发建索引需要另查有效性，不能只看名字。本地开发仍允许自动初始化，CI禁止。

终端变量被unset或换终端后必须重读；若psql尝试Unix socket而不是远程RDS，先检查变量是否为空，不要误连本机数据库。

## 6. 首次准备：离线运行依赖镜像

服务器不能访问Docker Hub，因此不直接使用在线Dockerfile构建。两个环境共用一份已导入的Linux amd64运行依赖底座。

当前底座：`aicloset-stylist:ci-runtime-7ec3bb1bf0238b32`。标签后缀为uv.lock SHA256前16位。CI还会检查镜像内锁文件摘要和关键Python依赖。

本地当前交付目录：`var/releases/ci-offline-runtime/`，不入Git。里面包括镜像tar.gz、同名.sha256及image-name.txt，镜像包样本约109MiB。

把tar.gz和.sha256传到服务器`/tmp/`，执行：

```bash
cd /tmp
sha256sum -c aicloset-stylist-ci-runtime-amd64.tar.gz.sha256 \
  && sudo docker load -i aicloset-stylist-ci-runtime-amd64.tar.gz
sudo docker image inspect aicloset-stylist:ci-runtime-7ec3bb1bf0238b32 \
  --format '镜像={{.RepoTags}} 平台={{.Os}}/{{.Architecture}}'
```

预期校验OK、Loaded image正确、平台linux/amd64。导入不会启动或替换容器，不执行SQL。仅有python:3.12-slim不够，运行依赖也必须齐全；不以旧recommend-outfit业务镜像代替兼容检查。

以后只改业务代码／资源时不用重复上传底座。uv.lock变化时，先在可联网本机构建并导出匹配底座，再手动导入服务器，最后触发CI。示例在本地仓库根目录执行：

```bash
mkdir -p var/releases/ci-offline-runtime
runtime_hash=$(shasum -a 256 uv.lock | cut -c1-16)
runtime_image="aicloset-stylist:ci-runtime-$runtime_hash"
docker build --platform linux/amd64 -t "$runtime_image" .
docker image inspect "$runtime_image" --format '{{.Os}}/{{.Architecture}}'
# 构建成功且确认linux/amd64后，导出；此过程需要本机Docker及可用网络。
set -o pipefail
docker save "$runtime_image" | gzip -1 \
  > var/releases/ci-offline-runtime/aicloset-stylist-ci-runtime-amd64.tar.gz
(cd var/releases/ci-offline-runtime && \
  shasum -a 256 aicloset-stylist-ci-runtime-amd64.tar.gz \
  > aicloset-stylist-ci-runtime-amd64.tar.gz.sha256)
```

锁文件、依赖及平台需与待部署提交匹配。归档中不包含实际env、公钥私钥、用户资料或报告；不要导出带凭证层的临时镜像作为底座。清理服务器镜像时保留当前底座及必要回退版本。

## 7. 首次准备：Nginx和域名

域名DNS需指向这台服务器对应的公网入口。Nginx独立站点：

| 配置文件 | 目标 |
|---|---|
| /usr/local/nginx/conf/vhost/aicloset-agent.wxbjq.top.conf | 127.0.0.1:8465 |
| /usr/local/nginx/conf/vhost/aicloset-assistant.wxbjq.top.conf | 127.0.0.1:8466 |

完整参考配置：[`deploy/nginx/aicloset-agent.centos7.conf`](../deploy/nginx/aicloset-agent.centos7.conf)、[`deploy/nginx/aicloset-assistant.centos7.conf`](../deploy/nginx/aicloset-assistant.centos7.conf)。agent的locations.inc只是已有HTTPS server内的替换片段，不是完整站点文件。

保留现有证书，确认其覆盖对应域名。整站代理须保留路径，`proxy_pass http://127.0.0.1:8465;`不加末尾斜杠；关闭proxy_buffering／proxy_cache／proxy_next_upstream，设置600秒读写超时以支持流式对话，上传上限16m；禁止公网访问/internal。

创建或修改站点后手动检查并重载：

```bash
sudo /usr/local/nginx/sbin/nginx -t \
  && sudo /usr/local/nginx/sbin/nginx -s reload
```

只改目标站点，不删除dev或Server其他站点。旧的更具体location可能覆盖整站代理，须核对`nginx -T`。后端尚未启动时502并不能单独证明Nginx配置错误。

## 8. 日常发布操作

### 8.1 推送自动发布

确认本分支CI配置、目标库结构和服务器配置后：

```bash
# main分支：自动发布dev
git push company main

# test分支：自动发布test
git push company test
```

只执行当前要发布的一条。公司GitLab流水线入口：

http://112.126.91.233:8090/ai_closet/ai_closet_agent_new/-/pipelines

推送origin GitHub不是这套GitLab部署入口。提交到本地不会部署；推送匹配分支才会触发。main和test当前各自维护CI环境值，跨分支合并时保留main=dev/main-web、test=test/test-web，不能直接把main配置覆盖成test。

### 8.2 网页手动发布

GitLab → CI/CD → Pipelines → Run Pipeline：

1. 选择含当前CI脚本的分支；通常main对应dev，test对应test。
2. 默认使用该分支DEPLOY_ENV。确需其他目标时显式传DEPLOY_ENV=dev或test，检查目标配置及域名。
3. 运行并依次查看job_build、job_deploy。

网页变量／项目／组变量可能覆盖YAML默认值。尤其核对DEPLOY_HOST是否仍被旧172.16.0.91覆盖；DEPLOY_ENV不是环境隔离的唯一保障，部署脚本还会核对Server、PostgreSQL及回调。

### 8.3 只改实际env

本地改好后经跳板上传/tmp/test.env，在服务器复制：

```bash
sudo install -m 600 /tmp/test.env /opt/aicloset-agent/config/test.env
# 确认复制成功后，手动清理/tmp/test.env。
```

dev使用dev.env。也可sudo vim直接编辑正式文件。配置在容器创建时注入，修改磁盘文件不会热更新已有容器；需重新发布。不要在另一个部署进行中同时修改env，因为成功收尾会把本次快照写回正式配置。

同一提交只改服务器配置时，可重试对应deploy任务；若源码压缩包已被清理，则重新运行完整流水线。

## 9. 发布后验收

每个任务成功不等于所有收费业务验收。CI自动检查基础路由和就绪，带身份上游接口、数美、保存、试穿和收费结果另按明确授权验证。

### 9.1 容器与日志

```bash
sudo docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'
sudo docker logs --tail 100 aicloset-agent-test
# dev改为aicloset-agent-dev。
```

共享日志前删除凭证、用户正文和账号资料，不直接粘贴全部容器env。

### 9.2 路由及提交版本

```bash
curl --fail --silent --show-error https://aicloset-agent.wxbjq.top/health
curl --fail --silent --show-error https://aicloset-agent.wxbjq.top/health/ready
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  'https://aicloset-agent.wxbjq.top/app/?design=yijian'
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  https://aicloset-agent.wxbjq.top/ops/conversations
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  https://aicloset-agent.wxbjq.top/stylist-api/conversations
```

health的revision应等于本次完整Git SHA，ready=true，未登录API=401。页面可用GET查看，部分路由不支持HEAD时用`curl -o /dev/null -w '%{http_code}'`。dev将域名替换为assistant。

### 9.3 运行容器实际MySQL目标

先选test容器（dev替换容器名并将expected改为aicloset_dev）：

```bash
sudo docker exec -i aicloset-agent-test /app/.venv/bin/python - <<'PY'
from urllib.parse import urlsplit, unquote
import pymysql
from stylist.config import Settings
p = urlsplit(Settings.load().ops_mysql_dsn)
expected = 'aicloset_test'
print('配置库名:', unquote(p.path.lstrip('/')))
try:
    conn = pymysql.connect(host=p.hostname, port=p.port or 3306,
        user=unquote(p.username or ''), password=unquote(p.password or ''),
        database=unquote(p.path.lstrip('/')), connect_timeout=5,
        read_timeout=5, autocommit=False)
    with conn:
        with conn.cursor() as cursor:
            cursor.execute('START TRANSACTION READ ONLY')
            cursor.execute('SELECT DATABASE()')
            actual = cursor.fetchone()[0]
            print('实际连接库名:', actual)
            print('检查结果:', '正确' if actual == expected else '错误')
        conn.rollback()
except Exception as e:
    print('连接失败:', type(e).__name__)
PY
```

输出配置库名和实际库名都为预期才算生效；不打印密码。页面手机号查询仍需实际请求确认权限及数据。

### 9.4 PostgreSQL和索引

在服务器读取对应env到临时变量，执行只读检查：

```bash
STYLIST_TEST_DSN=$(sudo sed -n 's/^STYLIST_DATABASE=//p' /opt/aicloset-agent/config/test.env)
psql "$STYLIST_TEST_DSN" -v ON_ERROR_STOP=1 <<'SQL'
SELECT current_database();
SELECT count(*) FROM pg_tables WHERE schemaname='public';
SELECT indexname, indexdef FROM pg_indexes
WHERE schemaname='public' AND tablename IN ('stylist_messages','stylist_sessions');
SQL
unset STYLIST_TEST_DSN
```

当前初始化为16表，消息索引含stylist_messages_owner_conversation_version，会话索引含stylist_sessions_owner；未来有新增表时应按当前SQL基线核对，不永久固定总数。

## 10. 失败处理、重试与回退

| 现象／日志 | 原因及处理 |
|---|---|
| yaml invalid，jobs:workflow unknown keys: rules | 旧GitLab不支持；沿用基础only写法，先用目标CI Lint验证 |
| pending | Runner未接走；检查项目启用、devops-test标签、在线／暂停、受保护分支和并发占用 |
| scp／ssh失败 | Runner到172.16.0.90的连接或权限；不是业务登录PEM问题 |
| Install private test.env | 目标机正式路径没文件或是软链接；核对主机IP及ls -l，vim能打开新文件不代表已存在 |
| Docker Hub connect refused | 不使用在线Dockerfile；检查是否已导入与锁文件匹配的离线底座及当前脚本 |
| Load the offline runtime image first | 缺指定tag；导入正确归档，不仅导入python镜像 |
| Runtime dependency lock mismatch | 底座与代码依赖不匹配；重新构建导入，不能强改tag掩盖 |
| Environment configuration rejected | 按环境核对Server、MCP、回调、PostgreSQL库名、模型、ops、Langfuse；日志不打印凭证 |
| Migration check failed | 缺所需表或索引；运维手动补SQL，再重试deploy，不由CI自动修复 |
| PostgreSQL连接超时／MySQL 2003 | 核对容器网络、VPC路由、内网端点、安全组／白名单、端口；本机可连不证明容器可连 |
| Candidate checks failed | 查候选服务错误、配置、公钥、数据库权限、启动日志；旧服务尚未切换 |
| Port belongs to unrelated container | 拒绝停止未知服务；确认占用归属后再处理，不盲目kill或删容器 |
| stopped deployment container owns target name | 目标名称已被旧停止容器占用；先核对版本、标签及用途，再人工重命名／清理 |
| 公网502 | 先curl本机8465／8466，再查对应Nginx代理及容器；可能尚未启动后端 |
| /ops=404但/ops/conversations=200 | 使用完整运维路径 |
| Public domain serves a different commit | DNS／代理／旧服务不匹配；CI会报错并尝试恢复旧容器 |

**重试方式：**修好配置、补齐SQL或导入底座后，在同一流水线只重试失败的job_deploy；job_build已成功且/tmp归档仍在就不必重打包。只有源码变化、归档丢失／损坏、构建阶段失败时才重新跑相应构建或完整流水线。旧流水线重试仍部署旧提交，不会自动带上新代码。

**自动恢复边界：**切换之前失败不停止旧服务；切换之后失败会尝试删除失败的新容器并恢复实际旧容器。数据库SQL本就不由CI执行，也不自动反向撤销；持久数据及外部业务效果不回滚。服务器进程被强杀或主机重启时不能保证shell清理trap完成，需人工核对。

回退业务代码优先在对应分支git revert后正常发布；若依赖锁发生变化，需要保留对应旧底座。不要从另一个环境复制env或交换库名来回退。不提供未经核对的一键删除／清理命令，避免删掉运行底座、回退容器或数据卷。

## 11. report与UI change log

report不随CI源码包或镜像发布。用户需要时单独要求“打包report”，由Agent核对当前本地reports、准备独立交付、打开文件夹并输出该次上传／部署命令。

真实内容以本地reports为准；`docs/UI_CHANGELOG.md/html`为忽略的兼容链接，不随本手册提交。没有新增UI无需为CI配置变更补拍UI。截图OSS补传先取得当次可用token，不把token写进文档、日志或Git。

## 12. 当前证据与维护清单

- 目标GitLab CI Lint已验证基础only配置有效；Runner真实完成过打包、scp和SSH阶段。
- 用户已确认test库16张表及消息／会话索引；dev缺消息索引时CI中止，用户随后手动创建成功。
- 用户已确认离线镜像SHA256、导入及linux/amd64；本地断网构建、H5／ops／API鉴权模拟通过。
- test公网曾读到ed1d55b完整revision，H5及ops为200；用户已确认运行test容器MySQL实际连接aicloset_test。
- dev首次14fd4c7部署在索引预检停止；用户已补索引，后续重试最终状态未在本手册编写时重新取证。
- 基础检查不能代替带身份API、模型质量、数美、真实支付或收费试穿验收。

修改流程时同步核对：`.gitlab-ci.yml`、`scripts/ci_package.sh`、`deploy/ci/deploy.sh`、`deploy/ci/Dockerfile.offline`、两个env模板、SQL基线及相关测试。新增环境／数据库结构／依赖时先准备服务器资源，再触发自动部署。
