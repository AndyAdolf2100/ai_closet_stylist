# 表结构与 API 映射

依据：相邻 `aicloset-server/internal/biz`、`internal/controller/mcp/tools`、`internal/server/router.go`，以及旧 Agent 的迁移文件。此处确认的是代码模型与已验证接口；没有直接连接生产库执行 DDL 或检查线上每一列的实际迁移状态。

2026-10-27补充只读核对：已直连当前配置的MySQL，`SELECT DATABASE()`返回`aicloset_dev`。以授权测试账号为范围，`user_product_base`正常状态记录共292条，与本次图库导出的292个个人单品ID及原图／抠图URL路径全部一致。图片字段为URL，文件内容来自对应OSS／CDN；本地`var/stylist.sqlite3`仅保存新Agent状态，不是原始衣橱图片来源。未执行业务数据写入或DDL。

## 1. 原业务表由现有服务负责

| 表／数据域 | 已核对的关键字段／关系 | 新 Agent 如何使用 |
| --- | --- | --- |
| `user` | `id`、账号状态；登录态由现有中间件检查 | `GET /api/user/info` 获取可信 owner；不接受客户端 `user_id` 作为身份 |
| `user_product_base` | `id` 是个人单品 ID；`product_id` 是关联的系统商品 ID；`user_id`、`status`、`is_ai_match_enabled` | 读取本人可参与搭配的衣物；`source=user` 时始终引用个人 `id` |
| `user_product_details` | 个人单品详情、材质等属性 | 通过个人商品属性列表读取，不另建一份业务衣橱 |
| `user_product_multi_attributes` | `user_product_id`、`attribute_code`、属性 ID | 读取颜色、风格、场合等属性；缺失属性保持未知 |
| `product_base`、`product_details`、`product_multi_attributes` | 系统商品及属性；系统商品需要已发布 | 从系统列表召回，按 `source=system` 权威读回 |
| `class`、`attribute_master`、`attribute_option` | 分类层级、属性定义与选项 | 使用接口返回的分类和属性名称，不编造分类 ID |
| `wardrobes`、`wardrobe_items` | 用户衣柜及其 `user_product_id` 关联 | 第一版读取本人全部合格单品，不绕过已有服务按他人 wardrobe_id 查询 |
| `user_outfit` | `id`、`user_id`、`status`、`features_desc`、场合／温度等适用信息 | 搜索、读取本人已存搭配；保存时走现有工具 |
| `user_outfit_item` | `outfit_id`、`user_id`、`user_product_id` | 完整搭配的真实商品引用由服务端解释和验证 |
| `city` | 城市目录、所属省份和行政区信息 | `city.resolve` 消歧；唯一后才 `weather.get` |
| `ai_fitting_list`、`ai_fitting_log` 等试穿数据域 | 既有试穿结果与执行记录 | 沿用现有试穿服务生成和保存，不自行写试穿表或扣积分 |
| 既有积分配置／账本 | 本次积分消耗、扣减、上游失败返还 | 只读报价，用户确认后调用现有业务执行；本地不维护第二套余额 |
| `user_long_term_memories` 等旧 Agent 记忆域 | 显式记忆、版本及操作记录 | `/api/memories` 只读接口已检查；第一版不自动学习、写入或批量应用历史记忆 |

重要身份规则：`user:7` 和 `system:7` 是两个不同实体。个人衣物即使来自系统商品，仍使用其 `user_product_base.id`。商品权威接口会排除他人、已删除或未发布商品；模型只能引用实际候选中的键。

补充源码审查发现：`quick_edit_list`虽接受继承字段`is_ai_outfit`，其`BuildFilterClause`当前没有应用`is_ai_match_enabled`过滤，响应也不带该标志；因此新Agent传`is_ai_outfit=1`不能证明已排除用户关闭参与搭配的衣物。该契约缺口尚待修复，不能把接口成功当作此规则已落实。另外，接口返回的独立`tags`数组尚未映射到新版`Product`模型；当前实际使用的是分类、颜色、材质、风格、场合及描述，未实现完整的数据库tag检索。

`purchase_price` 在已有模型中明确标为分；系统 `price` 在这次核对到的接口契约中没有明确单位证据，因此新 Agent 暂不将其换算为人民币作预算保证。已有衣物复用记新增购买为零；需要新购但价格无法确认的候选不能通过明确预算门禁。

## 2. 固定调用的上游接口

| 接口 | 输入与用途 | 注意事项 |
| --- | --- | --- |
| `POST /users/app/login/mobile/code` | RSA 加密手机号、验证码、设备 ID | 复用现有公钥约定；仅本地登录代理使用 |
| `GET /api/user/info` | Bearer、`version`、`device` | REST 需版本头；43100 可能对应多种情况，不能脱离文案与请求头武断归因 |
| `GET /api/user_product/quick_edit_list` | page、page_size、当前传`is_ai_outfit=1` | 正常状态和归属已在源码落实；参与搭配标志过滤存在上述契约缺口，尚不能保证 |
| `GET /api/product/list` | page、page_size | 读取已发布系统候选，有限分页不等于全库无结果 |
| `GET /api/memories` | 当前登录态 | 此版仅检查接口，未实现长期记忆编辑 UI |
| MCP `tools/list` | 标准 MCP 初始化与目录查询 | 校验实际发布情况；不能把本地源码当作远端已部署 |
| `city.resolve` | name、可选 province_name | resolved、唯一且未截断才用于天气 |
| `weather.get` | city_name、province_name、可选 date | ignored／provided 不调用；不支持日期等故障如实降级 |
| `product.resolve` | 最多 20 个 `{source,product_id}` | 商品身份、归属与发布状态的权威读回；校验返回引用没有越界 |
| `outfit.search-saved` | occasion 等明确条件 | 本版先召回少量搭配商品，再按当前任务重新校验／组合，不宣称直接照搬已验证整套 |
| `outfit.resolve` | source=user、outfit_id、include_presentation | 当前账号完整合法搭配读取 |
| `kb_search`（可选） | query、gender、scope、top_k | 真实服务当前未发布；可选能力缺失不阻断基础搭配 |
| `digital_twin_overview` | 无参数 | 只读检查默认形象，未准备好时引导回现有 App 完成 |
| `digital_twin_tryon_quote` | 无参数 | 实时获取积分费用，不生成、不扣积分 |
| `product_beautify_quote` | 本人上传的 user_product_id | 已做只读接口检查；本版 UI 不执行美化 |
| `save_recommended_outfit` | selection_id、真实 items | 仅整套试穿确认后调用，事先告知保存与系统衣物归入个人衣橱的影响 |
| `digital_twin_tryon` | 已保存 outfit_id、固定 idempotency_key、可选 scene | 仅独立费用确认后调用，不由文字模型授权 |

特意避开 `user_all_list` 和旧商品 `detail` 作为常规读取入口：前者有清理新增提示、特定参数更新优先级的逻辑，后者会清除新增／美化角标。新 Agent 不为选衣服触发这些界面状态变更。

## 3. 新增本地状态表

SQLite 定义见 [`stylist/schema.sql`](../stylist/schema.sql)，默认创建在独立的 `var/stylist.sqlite3`。
本地 Docker MySQL 定义见 [`stylist/schema_mysql.sql`](../stylist/schema_mysql.sql)，使用独立 `stylist_local` 库，
同时保存 `stylist_checkpoints` 和 `stylist_checkpoint_writes`；不迁移 SQLite 或旧业务库。
配置与验证见 [本地 MySQL 调试](MYSQL_LOCAL.md)。

| 表 | 用途与约束 |
| --- | --- |
| `stylist_companion_profiles` | 当前账号称呼、角色与显式定制偏好 |
| `stylist_sessions` | owner、当前 version、任务与方案、当前执行 claim／租约；防止旧请求覆盖新结果 |
| `stylist_requests` | `(owner_id,request_id)` 唯一；内容摘要、状态与响应；同请求重放返回同一结果 |
| `stylist_messages` | 每轮原输入和完整结构化回复；`(conversation_id,version)` 唯一 |
| `stylist_image_actions` | 用户、搭配版本、费用／人物／契约快照、有效期、确认及执行结果 |

不复用旧 `outfit_turns` 和 `chat_request_receipts` 的内部快照格式。二者与旧运行时高度耦合，新服务用少量独立表隔离实现，不修改旧表，也不在启动时搬迁历史对话。

## 4. 新服务对外接口

自有接口统一为 `/stylist-api/`，便于与原 Go `/api/` 在同域名下分流；前后端需一起更新，旧 `/api/` 不保留别名。
上文列出的上游接口保持原路径。Nginx 检测与合并说明见 [共享路由](NGINX_SHARED_ROUTING.md)。

| 方法与路径 | 行为 |
| --- | --- |
| `GET /health` | 只证明服务存活及模型是否配置，不冒充所有上游可用 |
| `POST /stylist-api/auth/mobile-login` | 原账号服务登录代理；生产默认关闭，测试站点可显式开启 `STYLIST_ALLOW_MOBILE_LOGIN=true` |
| `POST /stylist-api/chat` | JSON 请求／结构化回复，包含 request_id、conversation_id、expected_version |
| `POST /stylist-api/chat/stream` | SSE：progress、result、error；错误保留稳定 code，长请求发送心跳 |
| `POST /stylist-api/location/resolve` | 用户点击授权后提交经纬度，降低精度并通过逆地理编码与业务城市目录确认；只返回城市，不持久化精确坐标 |
| `POST /stylist-api/weather/forecast` | 当前用户选定城市与day/week/next7范围，返回逐日白天／夜间预报、数据缺口与穿搭提醒 |
| `GET/PUT /stylist-api/companion-profile` | 当前账号称呼、角色及定制偏好 |
| `GET/PUT /stylist-api/memories` | 当前账号手记，保存校验版本 |
| `GET /stylist-api/conversations` | 本账号最近对话 |
| `GET /stylist-api/conversations/{id}` | 本账号历史及当前版本 |
| `POST /stylist-api/wardrobe/export` | 导出当前账号可见的全部正常衣橱图片与清单到本机私有目录；只读业务数据，图片优先抠图、原图兜底 |
| `POST /stylist-api/integrations/check` | 当前登录态逐项真实只读检查，包含模型小请求；不执行生图、保存或扣费 |
| `POST /stylist-api/images/quote` | 根据当前搭配版本、look_index，生成有期限的费用确认 |
| `POST /stylist-api/images/{action_id}/confirm` | confirmed=true 才执行一次；false 取消未执行动作 |
| `GET /stylist-api/images/{action_id}` | 查询本账号本地执行状态，不会重新生成 |

除登录和存活检查外，业务接口需要现有 Bearer。当前服务是新协议，不能直接用旧 Vue 客户端发送旧 `turn_id` 动作；本项目随附独立移动页面，替换旧 App 接入前需明确做客户端适配。

2026-10-27新增只读业务API `POST /api/weather/get_weather`：服务端按权威解析后的省市读取14天范围，返回列表中的实际日期，供本周匹配。现有远端响应已确认包含`temp_day`、`temp_night`、`condition_day`、`condition_night`与`data_format`，未包含早间逐小时、风力和能见度；不能把日夜温度解释为准确早晚时刻实况。`POST /stylist-api/chat`可额外传`location={city_name,province_name}`；不接受经纬度直接写入对话状态。

定位接口请求为JSON：`{latitude,longitude,coordinate_system?}`，默认`coordinate_system=wgs84`；高德GCJ-02/百度BD-09不直接兼容。成功返回`city_name`、`province_name`、可选区名`district_name`及来源。对于直辖市，OSM中的`city`可能实际是区，需以`ISO3166-2-lvl4`或省级直辖市名称归一后查询天气目录，不能直接将区名当作地级城市。

## 可管理长记忆（PRD-12）

本服务新增 `GET /stylist-api/memories`、`PUT /stylist-api/memories`，必须带当前账号身份。与旧 Go 服务同名探测路径是不同的数据域，不代理旧记忆。请求／响应 `{revision, enabled, entries:[{id, category, content}]}`，拒绝客户端 owner 字段；保存需携带读取时的 revision，冲突返回 409 `memory_conflict`，不覆盖其他窗口修改。

独立表 `stylist_memory_books(owner_id, revision, book_json)`，兼容 SQLite／MySQL／PostgreSQL SQL 适配。每账号最多30条，每条240字；正文纯文本。明确聊天保存与 `Store.finish` 同事务提交，幂等请求不会重复添加；同内容去重。暂停不会删除条目；删除只移除活跃手记，不清除历史对话或检查点快照。详见 [长记忆](LONG_TERM_MEMORY.md)。
