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
