# 会员权益与商品接口同源

2026-11-07。本地已实现，未提交／部署；真实支付仍为H5演示。

| H5只读入口 | Server契约（对照现有iOS） | 数据责任 |
|---|---|---|
| `/stylist-api/app/purchase/member` | `GET /api/vip_product/products` | 商品ID、名称、现价／原价、币种、说明、推荐顺序与会员资格过滤 |
| `/stylist-api/app/purchase/benefits` | `GET /api/vip_product/privileges/compare` | 列顺序、名称列表头、行、提示、text/check/cross值及后台banner |
| `/stylist-api/app/purchase/points` | `GET /api/booster/products` | 积分包ID、名称、数量、价格与顺序 |
| `/stylist-api/app/purchase/config` | `GET /api/app_config/config_check` | 会员说明、试衣／润色费用，只返回购买相关白名单字段 |

复用当前登录身份、部署配置的App版本与PC设备头（Server当前按非Android选择iOS平台商品）。不固定商品数量、价格或按永久会员再次过滤；推荐选择取后台`is_recommend`，后续用户选项仅在仍在售时保留。积分不足入口按真实返回的`points_amount`选择覆盖缺口的方案，无固定三档。

权益购买页沿用iOS仅展示`display_scope=all`；后台列数量和顺序可变。角色陪伴banner是展示素材，保留现有六角色规则；后台权益接口banner响应保留，但H5不渲染其宣传图，避免在权益表后纵向堆叠；不影响后台权益和运营说明。

商品接口价格单位为元，不重复除100。iOS会再由StoreKit填充苹果实际价和订阅类型；H5没有StoreKit，不能把后台价当作苹果实际支付价，也不通过商品ID／名称推断自动续费。若未提供明确订阅字段，不显示“单次不续费”等承诺。真实下单、订阅管理、到账及退款本轮均不接入。

独立设计预览继续有明确标记的样本；真实积分／容量不足弹层不再显示其固定套餐，而进入同一接口商品中心。会员中心删除硬编码2000赠分、四会员／三积分档及300积分token价；缺少API依据的有效期、扣减顺序等不作为当前规则发布，改以正式商品协议及实时确认页为准。

四个接口独立加载；错误／下架／字段异常均不回退示例。所有读取`no-store`，无商品跨账号存储；换号中止旧请求并拒绝迟到结果，退出清空。个人中心商品栏与二级页共用同一数据模块。

协议路径与iOS一致：`/membershipService`、`/continuousSubscription`、`/pointsPurchase`。可选环境变量`STYLIST_PURCHASE_WEB_URL`配置本环境的正式H5根地址（仅HTTPS）；留空时明确地址未提供，不硬编码测试域名。后端配置没有返回积分有效期／模型token积分规则时不杜撰对应配置接口。

证据：48项后端模拟通过；320／393／1440px三组浏览器覆盖动态价格与表格、推荐项、演示弹窗、异常／空商品／重试／换号迟到响应及只GET，零JS异常、零业务写入。两类前后截图见本地`reports/26-11-07/membership-api/`。本地8466按原进程环境重载，ready及新入口未登录401通过。未执行带身份真实远端读取、StoreKit或真实收费验证。

当前工作区全量Node测试180通过／14失败，失败均是既有Agent埋点改动使用`performance`但旧VM测试上下文未注入；未改动这些独立功能，不能将本轮模拟通过称为全量回归通过。

## 2026-11-07 iOS提示信息二次核查（仅核查，以下待接入）

| 范围 | iOS／Server来源 | H5差异与建议 |
|---|---|---|
| 签到规则 | `/api/check_in/recent` 的 `tips`；GetPointsViewController、CheckInCardCell、GetPointsTooltipPresenter | 后端已透传tips，points-earning未展示；固定底部规则不可代替后台签到说明 |
| 上传奖励规则 | `/api/milestones` 的 `tips`；UploadRewardCardCell | closet_app适配丢掉tips，页面只有本地里程碑描述；应透传并展示后台规则，按安全富文本子集处理b标记 |
| 推荐充值／会员提示 | `/api/vip_center/pay_intercept`；PurchaseCardCell与PayInterceptModel | H5未接；后端提供booster/vip的名称、副标题、价格、积分、validity_days／monthly_points／is_subscription等。推荐ID必须与当前在售及资格商品核对，不可覆盖products的资格筛选；某一推荐商品的有效期不可套到全部SKU |
| 积分分类说明 | `/api/vip_center/points_detail` 的 `points_detail_list[].name/descriptions/type/list`、`total_used`；ScoreDetailModel／ScoreRecordCell | 当前H5只提取total_available，未展示分类、到期及使用说明 |
| 积分包批次明细 | `/api/booster/balance` 的 `buy_time/expire_time/remaining_amount/used_amount`；BoosterBalanceModel | H5无对应页面／入口，不能用固定“购买后两年”替代真实批次到期时间 |
| 会员状态提示 | `/api/user/info` 的 `vip_info.vip_type_name/expire_time/monthly_points/cycle_end_time/vip_list`；User.swift | H5已取账号及开通／续费判断，但详情仅“会员有效中”，未完整显示到期与赠分周期信息 |
| 业务失败提示 | Server `code/msg/data`；iOS HTTPS+V3以businessError(msg, code)交付 | `_business_payload`将非零业务码统一成通用错误，原msg未到H5；可按业务码保留面向用户的提示，身份失效与系统异常保持原有兜底，不改变成功／扣费判定 |

已接入：会员商品products、权益benefit_table、后台会员说明vip_tip、积分包产品、试衣／润色配置；订单状态status_text及自动扣款说明也已读取。独立预览样本不是这些接口的替代。

iOS积分购买页的“购买起两年／赠分优先”等五条说明本身是ScorePurchaseViewController内本地数组，未找到专门规则接口，不应误报为已有后台配置。NetworkService还声明积分赠送popup/check与popup/confirm，但在当前iOS源码未找到调用方；后者是状态确认写操作，不作为本轮自动接入项。

以上结论来自本地iOS、Server与H5源码交叉核对，不是远端部署或真实账号接口验证；本次仅新增核查记录，没有修改这些页面或执行确认／支付。

### iOS原生截图复核补充

六张原生模拟器截图及字段定位见本地`reports/26-11-07/ios-membership-prompts/index.html`。会员到期实际位于MembershipViewController的MembershipVipExpiryCell（vip_list）；底部“当前月度周期不重新计算”等是iOS本地说明。cycle_end_time虽在账号模型内，但本次未发现会员页独立展示它的控件，赠分周期说明应参考积分分类descriptions，不将两者误称同一会员状态区域。所有数据均为隔离模拟响应，不证明真实账号或正式配置；未使用用户提供的真实凭证执行积分、会员或支付操作。

### UI-010／011文案前后建议（2026-11-07）

本次带身份只读采集后，UI变更报告新增11项后台文案及4项前端文案对照，详见本地`reports/26-11-07/membership-api/copy-review.md`。这只是评审建议，不是配置已生效。当前测试权益表五行均有测试／占位内容，应先清理而不杜撰真实权益；vip_tip中的无限上传／限免／月赠额度需和实际方案核对，衣橱统计可统一衣橱小记。`booster_product`模型与列表响应均有sub_title字段，但ListProducts组装未赋值，应先补服务端透传再发布商品副标题。前端“后台实时提供”“暂无可用方案”等独立标注为前端固定文案，不归为Server原文。

## 已确认支付墙（2026-11-07）

沿用11月5日评审场景布局，第6项试穿不足、第10项会员只补积分分开。商品卡使用现有可购SKU；已知缺口时按覆盖条件选择最低价，否则沿后台推荐标记或顺序，不将本地计算称作后台推荐。会员状态来自账号vip_info.is_vip。缺少字段由Server补齐：场景pay_intercept商品ID／副标题、SKU有效期／赠分周期、容量增量及Agent计费规则。缺少信息不得回填旧示例金额或权益。UI-011图为隔离模拟布局证据，真实接口取证保留在UI-010。
