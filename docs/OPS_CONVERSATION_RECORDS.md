# 线上会话记录查询（本地 → aicloset-server → aicloset_stylist）

排查线上问题时，本地启动的 Stylist 需要读线上会话，但只掌握**用户 ID**，拿不到会话 ID。
因此接口分两级：**先按用户 ID 列会话（按最近活跃时间倒序），再按会话 ID 取详情**。

接口实现在 `aicloset-server`（不在本仓库），经 `stylist_postgresql` 独立配置只读连接本仓库线上库
`aicloset_stylist`，不建表、不写入。本仓库只保留查询脚本与本文档。

## 一、接口

| # | 方法/路径 | 用途 |
|---|---|---|
| 1 | `GET /api/internal/stylist/records/users/{用户ID}/conversations` | 该用户会话列表，`updated_at` 倒序 |
| 2 | `GET /api/internal/stylist/records/conversations/{会话ID}` | 指定会话的消息与请求原始记录 |

### 1. 会话列表

查询参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `limit` | 20 | 每页条数，1–100，越界返回 400 |
| `offset` | 0 | 偏移量，负数返回 400 |
| `include_deleted` | false | `1`/`true` 时连带软删除会话（排查“会话消失”） |

响应：

```json
{
  "user_id": "1024",
  "total": 2,
  "limit": 20,
  "offset": 0,
  "include_deleted": false,
  "conversations": [
    {
      "conversation_id": "sty_xxx",
      "version": 3,
      "message_count": 3,
      "last_user_message": "再换一套通勤的",
      "created_at": "2026-11-10 09:00:00",
      "updated_at": "2026-11-11 10:00:00",
      "deleted": false,
      "deleted_at": null
    }
  ]
}
```

`total` 是同一过滤条件下的总数（不含已删除时为过滤后的总数），用于判断要不要翻页。
`last_user_message` 只给最近一轮用户原话的截断预览，便于确认是哪条会话；完整内容走详情接口。

### 2. 会话详情

响应含 `session`（元信息 + 软删除标记）、`messages`（按 `version` 升序，`reply` 解析为 JSON）、
`requests`（`request_id`/`status`/`digest`/`response`）。会话不存在返回 404 `conversation_not_found`；
数据库未配置或查询失败返回 503 `stylist_records_unavailable`。

## 二、本地用法

```sh
export AICLOSET_SERVER_BASE_URL=https://<server 域名>

# 1) 先列这个用户的会话，挑出要查的会话 ID
uv run python scripts/ops_conversation_records.py list --user 1024
uv run python scripts/ops_conversation_records.py list --user 1024 --include-deleted --limit 50

# 2) 再拿会话 ID 查详情
uv run python scripts/ops_conversation_records.py show --conversation sty_xxx

# 需要原始 JSON 时加 --json，便于管道处理
uv run python scripts/ops_conversation_records.py show --conversation sty_xxx --json
```

脚本只用标准库，不依赖项目环境；`--base-url` 也可替代环境变量。

## 三、边界与风险

- **无鉴权**：两组接口都不接登录态，经公网域名可直接访问，能读到任意用户完整对话与模型响应。
  2026-11-11 需求确认时已当面提示该风险并由用户接受。会话 ID 为 `sty_` + 32 位随机串，枚举成本较高，
  但泄露面真实存在；后续要收窄可在 nginx 对 `/api/internal/stylist/records/` 加 IP 允许列表，无需改代码。
- **只读**：只走 `SELECT`，不建表、不写入；Stylist 数据写入仍归 Stylist 服务自身，数据归属不变。
- **时间排序**：`stylist_sessions.updated_at` 在库内是文本时间戳，字典序与时间序一致，列表即按它倒序；
  同时间再按会话 ID 倒序兜底，保证分页稳定。
- **连通性**：本地机器不在 RDS 白名单内，真实库连通性需在服务器（同 VPC）验证；
  server 侧 `stylist_postgresql` 段 DSN 走私有配置，不入 Git。

## 四、独立PC查询界面（2026-11-11）

本地地址：`http://127.0.0.1:8466/ops/conversations`。独立于App，普通用户菜单不增加入口。

默认输入手机号，也可显式切换正整数用户ID；两种方式不按数字长度猜测，11位ID不会误认手机号。手机号先经MySQL解析账号ID，然后分页浏览会话，可勾选已软删除会话。选择后，中间显示历史用户原话、回复、单品／搭配／天气以及上传／形象引导的只读卡片；右侧显示会话元信息、请求ID／状态／错误码与可展开原始JSON。错误原因提示仅根据已保存状态和明确错误码，不用状态推断收费，不补造日志或模型调用。

所有消息为只读：不挂载实时聊天控制器，不发送消息，不重试生成、保存、上传、试穿、评价或删除。图片细节复用现有OutfitBoard只读入口，可放大与切换图片；直接使用历史快照，不重新查询衣橱或创建合成图，不重建已失效图片。

回复JSON、卡片数组、单品字段或请求响应格式错误时，逐消息／卡片／字段局部显示“结构异常”、字段路径和原始片段；有效部分及后续轮次继续展示。整个HTTP读取失败则单独显示查询错误，不冒充空记录。会话归属无法核对时不展示详情。

页面使用同源只读桥接：

- `GET /stylist-api/ops/records/resolve-user?mobile={手机号}`：通过参数绑定及MySQL只读事务精确查询用户ID，仅返回ID和脱敏手机号；无匹配404、多账号409，连接未配或失败503。
- `GET /stylist-api/ops/records/users/{user_id}/conversations`，查询参数沿用limit／offset／include_deleted。
- `GET /stylist-api/ops/records/conversations/{conversation_id}?user_id={user_id}`，核对Server返回的owner_id与当前查询用户，防止错配。

桥接仅访问已配置的STYLIST_SERVER_URL，不接受浏览器指定目标URL、不转发App Bearer。手机号映射单独只读查询原MySQL用户域；消息仍由Server查Agent PostgreSQL，不直连会话库。沿用既有运维接口的访问范围，未新增运维登录或角色鉴权机制。响应no-store，查询结果只在页面内存，不存localStorage／sessionStorage，不接入对话埋点或Langfuse。

`stylist/ops_records.py`及`stylist/static/ops/`已被现有Docker源码COPY与发布暂存递归白名单覆盖，6个运行文件纳入检查。助理站点既有`location /`代理可访问此路由；仅代理API的其他站点需自行转发新页面及静态资源。此轮只实现界面，未重新打包或部署。

验证：后台专项及既有API／单品入口共25项通过；局部容错／文本注入／请求结构3项前端通过，OutfitBoard只读及必要详情5项通过。Chrome1280／1440／1920px验证分页、软删筛选、4轮消息／4处局部错误、图片详情和用户切换竞态，16次业务请求全部GET（含手机号解析）、无页面错误或横向溢出。截图为合成用户及模拟业务，报告在本地reports/26-11-11/ops-console/，不含真实用户资料。真实Server仅无效用户0列表探测200确认响应结构；真实用户完整记录、远端实际部署均未验。

### 手机号查询的私有连接

用户后续明确不改Server代码：手机号映射由本服务使用现有pymysql完成。`STYLIST_OPS_MYSQL_DSN=mysql://USER:PASSWORD@HOST:3306/DATABASE`仅放私有`config/ops.env`（600权限、Git忽略），Compose已支持可选加载。用户名／密码中保留字符须URL编码；raw env格式不加额外引号。本机已准备此私有文件，不随源码、镜像或报告提交；下一次部署需将该文件单独安装到服务器配置目录。ID查询不依赖此连接。

实际SQL为只读事务中的参数绑定SELECT id，按mobile精确匹配、排除注销status=3、LIMIT 2。无匹配不伪造ID，多账号不静默选择；始终rollback并关闭连接，不修改用户或会话数据。连接错误不输出DSN／密码。已使用现有私有连接验证只读事务和id／mobile／status字段访问，LIMIT 0未读取真实账号行。真实手机号映射与真实用户完整会话还没有执行；界面验证均为合成资料。

### 消息区域按手机排版

外层保持PC查询三栏，中栏每轮消息与卡片最大440px居中，窄栏按可用宽度收缩；用户气泡最大87%靠右。不改变左右列表／请求面板，不改变查询和只读行为。三PC宽度检查及原有容错、分页、软删、竞态用例通过。修改前截图仅作本地过程取证，最终报告继续以dd02eb5无此页面为基线，展示最终手机消息效果。

### 2026-11-12 排查结果

2026-11-12：运维卡片去重已实现，单品详情不重复显示looks和retained_items，搭配详情优先标准looks；无正文历史卡片保留。5项前端、10项后端、三桌面尺寸16次只读请求检查通过。测试环境手机号503 ops_mysql_not_configured，ID查询200；私有ops.env及加载命令单独准备在var/releases/ops-config-20261112，未远端部署。

测试域名为aicloset-assistant.wxbjq.top；页面和console.js均200。无匹配合成手机号本地404，测试站503；无匹配合成ID列表200。仅证明接口与配置状态，不代表真实用户数据验收。将私有ops.env单独安装到服务器config/ops.env后，必须重建容器加载新增环境，不能仅restart。
