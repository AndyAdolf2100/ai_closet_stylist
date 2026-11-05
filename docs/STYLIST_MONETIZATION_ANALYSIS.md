# Stylist 商业化现状与接入分析

整理日期：2026-10-31。范围：当前 Stylist、Agent、Server 和 iOS 工作区，以及本轮只读查询的 MySQL 测试库 `aicloset_dev`。

当前最适合接入 Stylist 的商业化路径是：用户获得搭配建议后，按需使用个人形象生成试穿图；上传个人衣物后，按需购买图片补全与美化。试穿、数字分身和美化消耗同一上游业务积分，积分包与会员提供购买承接。

**测试库非会员个人衣物容量实际为 300 件。此前讨论中的 2000 件来自源码初始化脚本，不是测试库当前值。** 会员上传保护阈值实际为 3000 件，系统基础单品独立上限实际为 222 件；会员具体容量仍取决于对应商品配置。

本轮完成代码分析、数据库配置只读核对和文档整理。以下接入顺序为建议，尚未新增商业化功能，也未验证真实支付、扣积分、退款或生成质量。

## 商业化项目与当前实现

| 项目 | 当前业务规则 | 三端现状 | Stylist 接入位置 |
| --- | --- | --- | --- |
| 整套试穿 | 实时报价，用户明确确认后消耗积分并提交生成 | Server 有试穿与报价 MCP；Agent、iOS 有调用流程；Stylist 已有整套试穿报价与确认执行主体 | 搭配结果下方提供“用我的形象试穿” |
| 个人数字分身 | 当前 Server 代码固定为每次生成 100 积分 | Server、Agent、iOS 有照片检查和形象生成流程；Stylist 目前引导用户到 App 准备形象 | 首次试穿缺少形象时，以及设置中的“我的形象” |
| 衣物补全与美化 | 按个人单品消耗积分，实际费用读取配置 | Server 有报价及执行 MCP；iOS 有单件和批量入口；Stylist 只接了报价读取 | 个人衣物上传成功卡、单品详情 |
| 积分包 | 购买业务积分，供试穿、美化、数字分身使用 | Server 有商品、订单和发放实现；iOS 有购买流程；Stylist 未接购买 | 费用确认卡余额不足时，以及“会员与积分”入口 |
| 会员 | 支持时段会员、连续订阅和永久会员；展示与权益以实际商品为准 | Server、iOS 已有体系；Stylist 未接会员购买流程 | 设置常驻入口，积分不足或容量不足时按需展示 |
| 个人衣物容量升级 | 达到账号个人上传容量后拦截，普通用户可引导升级 | Server 有容量检查，iOS 有会员购买弹窗；Stylist 上传仍是待办 | 上传前检查容量，不在普通咨询中插入 |

美化和试穿的源码初始化值分别为 200、300 积分／次，只能用于解释初始化配置，不能当作测试服务器或线上当前报价。数字分身的 100 积分是当前代码规则，也不代表目标环境已发布该版本。具体人民币价格、月度赠送积分和商品有效期应读取实际商品与费用接口。

永久会员身份与时段订阅分开维护，永久会员本身不发月度积分。不能把“永久会员”宣传为永久获得 AI 积分。

## Stylist 接入优先级

### 优先完善试穿和真实积分展示

用户已经看中一套搭配，此时想查看个人上身效果，付费目的最明确。沿用当前试穿流程，补齐真实积分余额、余额不足承接、处理状态与真实结果展示。

建议操作顺序：

1. 用户在搭配结果点击“用我的形象试穿”。
2. 检查默认形象，读取本次报价与真实可用积分。
3. 展示费用、目标搭配及必要说明，用户明确确认。
4. 提交任务，分别展示处理中、成功、失败和结果未知。
5. 成功后展示真实试穿图，支持历史恢复、放大和下载。

余额不足时保留原搭配，提供积分包与会员选择；取消购买仍可继续普通搭配。购买到账后返回原任务，重新核对余额和报价，再由用户确认提交。

当前免费的衣物组合图与付费试穿图需要明确区分。组合图是所选衣物图片的排布，不能作为实际试穿效果；此次商业化分析不改变组合图、逐件详情和现有下载功能的规则。

### 接入积分包与会员购买承接

只想完成本次操作的用户可以购买积分包；持续使用者可以查看会员套餐、每月赠送积分与容量权益。在设置中提供“会员与积分”常驻入口，展示余额、状态和记录。

Server 的 `pay_intercept` 当前按价格返回较便宜的积分包和会员，不保证推荐积分包足够支付本次操作，也不保证适合用户已有会员状态。展示时需要结合本次缺少积分、用户当前权益和商品可购条件判断。

不能直接把 iOS 的 Apple 内购页面搬到独立网页。Server 已有微信 Native 和支付宝扫码下单代码，支持会员和积分包，但这两类入口在代码中标为“测试用”。网页正式收款仍需核对渠道启用、商品平台、下单、回调、到账、订单查询及失败恢复；PC 扫码与手机网页的操作方式也需分别验证。

### 接入个人数字分身

在首次试穿缺少个人形象时，让用户选择已有形象，或上传照片创建形象。需要补照片检查、处理选项、费用确认、生成进度、失败恢复、候选结果确认及默认形象选择。

创建形象和生成试穿图是两次独立操作。应提前说明各自费用，避免用户以为创建形象已包含后续试穿。同一照片重新生成也可能产生新费用；结果未知时先查原任务，不能自动重新生成。

### 上传个人衣物后提供可选美化

上传成功卡可提供“用这件搭一套”和“补全／美化图片”。基础上传、审核、识别和抠图沿用正式上传流程，只有用户主动选择美化、确认费用后才提交付费操作。

已美化或正在美化的衣物应按服务端状态处理，不重复收费提交。iOS 批量美化当前单次最多选 5 件，按件数计算消耗；Stylist 可先从单件接入，批量作为后续扩展。

### 容量升级以实际权益差异为前提

测试库非会员容量是 300 件，达到容量时可形成升级入口。但升级后究竟增加多少，需要读取对应会员商品，不能把 3000 件保护阈值直接当作所有会员的套餐容量，也不能承诺真正无限上传。

上传功能同时让用户建立个人衣橱，承接后续搭配、美化和试穿。是否主要依靠容量付费，需要结合实际用户到达上限的情况验证，本次没有增长或转化率证据。

## 个人衣物上传流程与限制

### 用户操作

iOS 从底部“＋ → 添加单品”进入相册或拍照；网页图片通过电商导入进入。前端先检查容量，再上传文件获得 URL，创建衣物处理任务，回到衣橱展示进度。后台审核、检测、分割或抠图、分类打标后自动归档，用户可后续修正属性。

Agent 对话上传则是用户附上图片并明确要求加入衣橱，调用上传 MCP，再轮询结果。Stylist 目前尚无图片附件请求、上传卡片和任务恢复，需要补这些衔接；无需自行重建识别与抠图服务，也无需通过旧 Agent 中转。

建议 Stylist 首期采用单张上传：“选择照片 → 预览并明确加入衣橱 → 处理中 → 入柜成功 → 用这件搭一套”。仅发图片咨询不应自动保存到衣橱。

### 每批张数与账号总容量

| 限制项 | 当前规则或测试库快照 |
| --- | --- |
| iOS 相册上传 | 每批最多 10 张 |
| iOS 网页导入 | 每批最多 10 张 |
| 拍照 | 每次 1 张 |
| 当前 Agent 聊天选图及 `product_add` | 单次 1 张 |
| Server 常规上传请求 | 每批 1 至 10 个图片 URL |
| iOS 相册原始图片 | 选择器拦截超过 20MB 的图片 |
| MCP Base64 图片 | JPEG、PNG、WebP，解码后最多 10MiB |
| 非会员个人上传衣物 | 测试库配置 300 件，按账号统计 |
| 会员个人上传衣物 | 由对应商品配置决定；“不限”配置转而读取保护阈值 |
| 会员上传保护阈值 | 测试库配置 3000 件 |
| 系统基础单品 | 独立统计，测试库上限 222 件 |

个人容量统计当前账号 `product_id=0` 且正常状态的衣物，不是每个分类衣橱分别享有容量，也不是累计上传图片次数。系统基础单品不占个人上传容量。

容量校验目前按“已有正常个人衣物数＋本次图片张数”计算。一张人物照片可能分割成多件衣物，尚未完成的任务也未纳入该正常状态计数；归档路径未看到再次校验最终容量，因此存在分割或连续提交导致超过配置上限的可能。

iOS 会员弹窗包含“无限上传”和“批量上传”等宣传，但后端仍有容量保护阈值，普通用户相册也可批量选择 10 张。不能仅依据宣传文案将批量上传认定为会员专享。

## 可复用的 MCP 与 REST

以下为源码中现有能力，新增接入前仍需带登录态确认目标环境的实际发布情况。Stylist 对浏览器继续使用自有 `/stylist-api/` 路由，由后端携带身份调用固定上游接口。

| 能力 | 现成接口或 MCP | 接入说明 |
| --- | --- | --- |
| 上传并录入个人衣物 | MCP `product_add` | `image_data` 与 HTTPS `image_url` 二选一，传固定 `idempotency_key`，先返回任务编号 |
| 上传进度与结果 | MCP `product_upload_status` | 传 `task_id`，完成后返回个人单品 ID、图片和分类等信息 |
| 文件存储 | `POST /api/upload/file`、`POST /api/upload/base64/image` | 仅获得文件 URL，不等于已录入衣橱 |
| 批量衣物处理 | `POST /api/user_product/upload` | 图片 URL 数组，每批最多 10 张 |
| 上传前容量检查 | `GET /api/user_product/product_privileges_check` | 个人图片使用 `type=2` 及本次 `count` |
| 上传任务读取 | `GET /api/user_product/upload/task/detail`、`GET /api/user_product/upload/pending_tasks` | 查询任务详情及未完成任务 |
| 衣物美化 | MCP `product_beautify_quote`、`product_beautify` | 个人单品报价与执行分开，不能在上传后自动执行 |
| 形象与生成 | MCP `digital_twin_overview`、`digital_twin_generate` 等 | 还需配套照片检查与形象确认流程 |
| 试穿 | MCP `digital_twin_tryon_quote`、`digital_twin_tryon` | Stylist 已有整套费用确认流程，保存搭配另复用 `save_recommended_outfit` |
| 真实积分余额 | `GET /api/vip_center/points_detail` | 2026-11-05已本地接入固定同源代理，读取total_available；每次确认与后端生成／试穿执行前查询，不缓存、不维护本地余额；真实带身份上游另验 |
| 积分流水 | `GET /api/user_points/list` | 用于业务积分记录展示 |
| 会员商品与权益 | `GET /api/vip_product/products`、`GET /api/vip_product/privileges/compare` | 按商品与用户实际状态展示 |
| 余额不足推荐商品 | `GET /api/vip_center/pay_intercept` | 当前按较低价格推荐，需结合任务缺额及已有权益判断 |
| 微信扫码下单 | `POST /api/vip_orders/wechat/native_create_order` | 源码标为测试用，支持会员与积分包 |
| 支付宝扫码下单 | `POST /api/vip_orders/alipay/qrcode_create_order` | 源码标为测试用，支持会员与积分包 |

名称需区分：`product_add` MCP 是上传个人图片；`POST /api/user_product/add_product` 是把系统商品加入衣橱；Stylist 已有的 `upload_outfit_image()` 只保存组合图到文件存储，不录入衣橱。

当前 Stylist 的 MCP 白名单尚未开放上传和美化执行，聊天请求也没有图片附件字段。新增这些能力需要固定业务入口、账号归属校验、持久化任务状态及幂等处理，不能仅将工具加入模型提示词后开放任意调用。

## 测试服务器配置的只读核对记录

查询日期：2026-10-31。连接配置来自现有 Server 本机配置，实际连接数据库为 `aicloset_dev`，MySQL 返回版本为 `5.7.44-log`。数据库返回时间为 `2026-10-31 14:45:29`。

连接设置 `SET SESSION TRANSACTION READ ONLY`，使用 `START TRANSACTION READ ONLY`，确认 `@@session.tx_read_only=1`。查询结束执行回滚并关闭连接，没有修改业务数据或表结构。

| 配置键 | 查询值 | 数据库更新时间 |
| --- | --- | --- |
| `wardrobe_limit_normal` | `300` | 2026-04-20 13:56:42 |
| `vip_upload_total_limit` | `3000` | 2026-10-14 10:01:04 |
| `system_product_total_limit` | `222` | 2026-06-09 15:34:02 |

仅查询上述配置及必要的数据库元信息，未读取账号资料、用户图片或业务订单。本文件不保存连接串、密码和登录令牌。

核心查询：

```sql
SELECT config_key, value, remark, updated_at
FROM vip_global_config
WHERE config_key IN (
  'wardrobe_limit_normal',
  'vip_upload_total_limit',
  'system_product_total_limit'
)
ORDER BY config_key;
```

另尝试 `GET https://aicloset-dev.wxbjq.top/api/user_product/product_privileges_check?type=2&count=1`，未携带登录态，HTTP 返回 200，业务码 `43101`，文案“请先登录”。因此容量数值证据来自数据库实际查询，尚未完成带非会员登录态的接口交叉验证，也不证明目标进程运行配置与本地配置完全相同。

## 保持的业务边界

- 基础聊天、文字搭配、称呼、人设、偏好和已有手记暂不新增收费限制。现有代码没有对应的完整收费与权益机制。
- Stylist 签到的 10 体验积分仅在前端内存存在，刷新清空，不能支付真实试穿，也不能与上游业务积分合并。
- 新手首张 Look 在现有 Server 契约中是不扣积分、同一用户复用唯一任务的体验，不应与常规付费试穿混为一项。
- 未确认费用不提交付费操作；取消停止后续执行；结果未知先查原任务，不自动再次扣费生成。
- 用户切换账号后关闭旧面板并忽略迟到结果，上传、余额、订单和结果按认证账号隔离。
- 真实扣费、失败返还、支付退款和图片生成质量分别验收，报价或 Mock 测试通过不能替代这些证据。
- 角色新服装、主题、语音和专题陪伴可以作为后续探索，但需要新增内容商品与权益管理，不属于当前现成功能。

## 代码依据与后续验证

| 依据 | 关键位置 |
| --- | --- |
| Stylist 当前试穿、调用白名单及请求结构 | [images.py](../stylist/images.py)、[upstream.py](../stylist/upstream.py)、[models.py](../stylist/models.py) |
| Stylist 上传、数字分身及结果预览待办 | [AGENTS.md](../AGENTS.md) 中 TODO-02 至 TODO-04 |
| Server 上传与美化 MCP | [product.go](../../aicloset-server/internal/controller/mcp/tools/product.go)、[image.go](../../aicloset-server/internal/controller/mcp/tools/image.go) |
| Server 上传编排与自动归档 | [mcp_upload.go](../../aicloset-server/internal/controller/user_product/mcp_upload.go)、[upload.go](../../aicloset-server/internal/controller/user_product/upload.go)、[user_product_finalizer.go](../../aicloset-server/internal/cron/user_product_finalizer.go) |
| 容量规则与初始化值 | [upload_check.go](../../aicloset-server/internal/service/feature_gate/upload_check.go)、[wardrobe_capacity_check.go](../../aicloset-server/internal/service/feature_gate/wardrobe_capacity_check.go)、[vip_global_config_init.go](../../aicloset-server/cmd/script/command/vip_global_config_init.go) |
| 数字分身生成价格 | [policy.go](../../aicloset-server/internal/service/digital_twin/policy.go) |
| 支付入口及商品推荐 | [router.go](../../aicloset-server/internal/server/router.go)、[pay_intercept.go](../../aicloset-server/internal/controller/vip_center/pay_intercept.go)、[wechat_native_create_order.go](../../aicloset-server/internal/controller/vip_orders/wechat_native_create_order.go)、[alipay_qrcode_create_order.go](../../aicloset-server/internal/controller/vip_orders/alipay_qrcode_create_order.go) |
| Agent 上传任务与费用确认参考 | [tool_execution.py](../../ai_closet_agent/app/tool_execution.py) |
| iOS 上传和商业化入口 | [GarmentCreateViewModel.swift](../../../ios/aicloset-IOS/AICloset/Sources/Module/Garment/Create/Paging/GarmentCreateViewModel.swift)、[PurchaseCenterViewController.swift](../../../ios/aicloset-IOS/AICloset/Sources/Module2.0/Purchase/PurchaseCenterViewController.swift) |

核对时本地提交：Stylist `11aed35`，Agent `66ced4f`，Server `bc5629b7`，iOS `1b75a72f`；分析也包含相关工作区现状，提交号不代表远端部署版本。

下一步先用非会员测试账号只读核对容量与商品、余额和工具目录，再确定网页支付方式。功能实现后分别验证上传恢复与账号隔离、费用变更与重复确认、支付到账、失败返还及真实结果图；真实支付和生成测试需单独明确执行。
