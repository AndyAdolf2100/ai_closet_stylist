# 衣间个人中心业务页

更新日期：2026-11-03。范围：`/app/?design=yijian` 的联系我们、意见反馈、我的消息、订单记录。iOS源码未修改。

## 页面与交互

- 联系我们：纸面来信介绍、公开邮箱 `Aiyichupm@microdreams.com`，复制邮箱和邮件客户端入口；沿用App公开公司信息，不宣称客服在线状态或响应时效。
- 意见反馈：1～300字，最多9张JPEG／PNG附件，每张不超过5MB。选择仅在本页预览，明确点击提交后逐张上传，再发送反馈。禁止重复点击；失败保留文字和附件，已收到成功回执的图片不重复上传。没有自动重试，也不伪造提交成功。
- 我的消息：真实分页列表、未读标记、正文详情；正文以纯文本展示，防止HTML注入。详情沿用原接口，由原服务处理已读。未调用独立批量标记接口。
- 订单记录：会员／积分两类，展示接口提供的标题、实付金额、状态、订单号、时间、支付类型，以及已有会员子订单记录。字段缺失不编造；不含购买、续费取消或退款操作。
- 登录、错误、复制及提交反馈统一message；空态和加载状态保留在区域内。未登录显示连接入口，不伪装为空记录。
- 沿用yijian三套主题变量、纸面卡片与宋体标题；16px文字输入、44px主要操作区域，短屏允许滚动。

## 固定接口边界

| 本项目入口 | 既有App服务 | 行为 |
| --- | --- | --- |
| GET /stylist-api/app/orders | GET /api/vip_orders/list | 会员订单列表 |
| GET /stylist-api/app/points-orders | GET /api/booster/order_list | 积分订单列表，服务端日期范围为准 |
| GET /stylist-api/app/messages | GET /api/message/list | 分页消息列表，数组规范化为list |
| GET /stylist-api/app/message-detail/{id} | GET /api/message/detail?id= | 当前账号详情，原服务可能标记已读 |
| POST /stylist-api/app/feedback-image | POST /api/upload/base64/image | 固定upload_type=feedback |
| POST /stylist-api/app/feedback | POST /api/feedback/add | 用户明确提交反馈 |

全部业务请求沿用当前登录Authorization及版本头，不保存凭证。使用服务API，不直接读写旧MySQL。只开放固定路径；反馈不作为Agent工具开放。账号切换中断请求，旧响应不得进入新账号页面，详情历史按原账号清理。附件不写入本地仓库或持久存储。

## 证据与未验范围

接口契约已核对本地iOS及Go服务源码，不将源码视为远端已部署。13项模拟后端检查通过；Chromium在320／393／844px执行四页导航、订单切换、消息纯文本详情、反馈必填提示、附件选择与模拟提交通过。截图：`var/yijian-orders.png`。未进行真实账号消息读取、标记已读、真实反馈提交或图片上传，也未验证远端接口可用性；没有真实扣费或退款。

代码：`stylist/closet_app.py`、`stylist/static/closet-app/profile-pages.js`、`profile-pages.css`。专项测试：`tests/test_closet_app.py`。

## 原版App外观同步（2026-11-03）

入口：`/app/`（data-app-design=ios）；衣间入口仍为`/app/?design=yijian`。四页复用相同的固定业务边界和账号隔离，在原版中采用单独样式与必要的DOM分支：

- 联系我们：原App 105px Logo与96×22文字标识，复制邮箱，底部公司名；不显示新版小笺介绍。
- 意见反馈：浅灰114px输入区、字数、方形添加图片按钮、48px提交按钮；空内容禁用，填写后粉紫渐变。手机文本输入保留16px以避免Safari聚焦放大，与原App12px文字输入有意不同。
- 我的消息：无卡片圆框列表、16px标题、红色未读圆点及时间；详情为白底正文。
- 订单记录：居中导航、会员／积分标签、12px圆角边框卡、行式元数据及原App空态素材；仅展示已有信息，不增加交易操作。

读取iOS ContactUsViewController、FeedbackViewController、MessageCell、OrderRecordCell等作为参考，未改iOS源文件。公共素材复制到closet-app/assets/ios-contact-*及ios-order-empty.png，文字标识从原PDF转换PNG。原版和衣间在320／393／844px均通过四页模拟交互回归，原版订单截图已目视：`var/ios-orders-integrated.png`。无实时iOS配对像素验收，平台字体与键盘存在差异，真实账号接口及写入仍未验。

## 个人中心记录路由纠正（2026-11-03）

「生成记录」不是Agent media/images任务：独立页面以试衣／潮流玩法两类读取GET /api/generation_records/list，type固定fitting／trend，通过/stylist-api/app/fitting-records、trend-records提供，不自动进入Agent或启动生成。处理中、失败与不可用结果不当作完成图片。

「我的搭配」复用iOS ProfileMyOutfitsViewController中HomeMineMatch的真实列表GET /api/ai_outfit_merge_my_outfit/list，通过/stylist-api/app/my-outfits提供；传outfit_id、outfit_id_type游标，初始0／0，不混同首页outfit_album或其他user_outfit列表。独立页面显示个人卡片，图片可打开预览，返回个人中心。

两个版本的个人中心卡片共同修正目的地。Agent journey-entry的生成记录仍使用原Agent上传／生成任务域。代码：collection-pages.js、closet_app.py。22项模拟后端及320／393／844px目标、分类、返回与不调用Agent任务接口检查通过；真实账号远端接口可用性仍未验。

### 我的搭配画布封面补齐

iOS HomeMineMatch并非只显示一张canvas_image：无边框成图时，GenerateCoverImageTool会按canvas_data.product_list现场组合。Web新增outfit-preview.js，按center、size归一化坐标、z_index、rotation弧度及flip渲染真实cutout_image，保留canvas_content的颜色和比例。已有封面支持失败后尝试其他保存地址与画布；主列表和放大详情复用渲染器。部分单品失败明确提示，不使用占位穿搭图，不写回服务或上传。AI生成中的任务仍显示实际进度状态，不把它当完成封面。

模拟验证：两层画布图片加载、层级、弧度／翻转及失效封面回退通过，三尺寸业务列表通过。截图var/my-outfit-canvas-preview.png使用项目公共素材作为合成夹具，非真实衣物／真实用户图片验收。真实账号图片URL状态尚未实测。
