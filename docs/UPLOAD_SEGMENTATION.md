# 多照片拼图与多实例入柜

2026-11-10 当前规则。用户提供 `upload_demo.html` 作为 dev 接口示例；此文替代早期“新衣物入口只能单张、拆衣尚未接入”的对应说明。旧任务与人物照片保留原流程，聊天附图重新选择单张单件衣物的边界仍保留。

- 最多10张，每张不超过10MB；单张保留原字节，多张由浏览器等比排入白底拼图，不裁切，最长边不超过3072px、JPEG不超过10MB。确认前只在本地，不上传图片。
- Agent、衣橱、Onboarding共用入口。蒙层前底部面板上滑，顶部圆角和短横条，主体可滚动、底部确认固定；减少动态直接显示。照片卡使用“从照片添加”，显示最多10张及拼图提示。
- 一次确认只上传一张图片。新衣物使用 protocol=segmentation_v2；人物与历史默认 legacy。仅候选确认后提交保留实例，空选择表示取消。
- 任务与结果按当前用户归属保存，不存照片字节或凭证。两秒串行只读轮询；关闭、换号丢弃迟到结果。上传、创建任务、选择提交结果未知时不自动重发写请求。
- 选择先原子占位，重复点击不重复提交；勾选状态跨轮询保留。美化状态严格1成功、2失败，部分失败展示数量；多结果需点具体成功单品“用这件搭一套”，才能承接原搭配流程。

## dev 固定接口

头 `version: 2.1.0` 和当前账号 Bearer，JSON响应按 code=0/data 处理。

1. POST `/api/upload/file`：multipart `file` 一张，`upload_type=product`，取 `data.url`。
2. POST `/api/user_product/upload`：`urls:[url]`、`from_source:1`，取 `data.task_id`。
3. GET `/api/user_product/upload/task/detail?task_id=`：progress、selection_required、selection_items、is_finish、has_segmentation_success。
4. POST `/api/user_product/upload/task/selection`：task_id、selected_detail_ids，显式提交保留的 detail_id。
5. GET `/api/user_product/task_product_detail?task_id=`：products；beautify_status=1成功、2失败。

浏览器直接访问 `https://aicloset-dev.wxbjq.top` 的上述五个 `/api` 路径，不经 `/stylist-api/media/uploads` 或新建Stylist代理。前端 `server-garment-upload.js` 读取当前登录身份，按HTML原样传参数及2.1.0头。图片只在multipart请求中出现，Server task_id与结果按当前账号保存在本地sessionStorage（不足时退到内存），不存照片字节或额外凭证。人物及旧任务保留原接口，新衣物请求Stylist旧入口409明确要求刷新。

候选和结果在同一抽屉内处理；点击某成功单品“聊聊这件”，通过已有个人单品引用进入Agent，不伪造Stylist媒体action_id。本轮曾增加的Stylist分割代理已撤除，由当前直连规则替代。

没有任务编号时，示例没有提供上传回执查询契约，所以保留未知状态，不重复创建。原图局部对照、单品字段编辑等截图能力，示例未提供相应契约，本轮不伪造保存。

## 本地证据与边界

62项既有后端相关检查、57项共用组件回归通过（此前中转实现的68项结果不作为直连证据）；三尺寸前端拼图测试覆盖1/2/10/11张、单次合成请求、10MB上限、重试同request_id、取消与换号；三尺寸真实H5 Agent内模拟验证底部面板、候选勾选、显式确认及最终结果。

实际 dev 带身份上传、风险检测、分割、入库、美化和费用效果尚未验证，不以Demo或Mock冒充远端验收。汇报图使用合成资料，位于本地 reports/26-11-10/change-log/，不入Git。

环境复核：8467启动命令从原目录config/deploy.env加载，STYLIST_SERVER_URL=https://aicloset-dev.wxbjq.top；新上传适配使用该Server根地址下的/api/upload/file及/api/user_product/路径，不走MCP。对dev task/detail与task_product_detail发起无身份只读请求，均HTTP200、业务code43101“请先登录”；仅证明dev鉴权入口可达，不代表带身份流程验收。未上传图片或使用账号凭证。

503复核：用户实际失败地址为本地Stylist旧上传接口。upstream_business_error来自旧适配对上游非0业务码的统一包装，具体原始业务码未保留。无身份只读dev查询返回43101，OPTIONS上传及建任务均204、允许Origin127.0.0.1:8467。当前三屏宽直连Mock校验五个Server路径、multipart一张、JSON字段和2.1.0头，并禁止新衣物走Stylist媒体POST；这不是带身份生产成功证据。

旧衣物接口停用（用户最终要求）：移除product_add、product_upload_status、product_upload_receipt的执行与白名单。旧记录仅供快照查看，不再向旧服务查询或轮询；人物照片及生成查询保留。新衣物只使用上述dev Server直连五接口。

43511排查：用户请求urls单个地址、from_source=1与HTML一致。当前本机Server源码中43511为ProductCodeWardrobeCapacityVip，CheckWardrobeCapacity统计user_id下product_id=0、status正常的个人单品，并检查currentCount+len(urls)>wardrobeLimit；VIP商品WardrobeLimit=-1时使用vip_upload_total_limit配置。实际dev账号计数／配置未查询，不能推断具体阈值。前端保留原msg与code，43510／43511按明确拒绝记录failed，不当作未知任务或自动重交。

2026-11-11关闭规则：衣物上传／建任务／识别／提交选择／美化处理中×和完成禁用，Esc／蒙层不可关闭；待用户选择、终态或明确失败恢复，换号仍强制清理。标题为“把喜欢收进衣橱”，界面不展示拼图实现说明，实际最多10张前端合成逻辑保留。

2026-11-11来源卡片：从照片添加和拍摄为同级独立等宽卡片；相册最多10张，拍摄只取本次单张并设capture=environment。切来源先清旧预览、数据和异步序列；拍摄后发送本次照片原字节，不拼入之前的相册图片。三尺寸以模拟文件选择器验证，实体摄像头权限／拍照未实际测试。


2026-11-11 上传终态修复：selection_required是选品流程标识，不表示一直待选；selection_state为0不需选择／1待选／2已提交／3取消。已提交仅跟踪selection_status=2的单品，美化状态1成功、2失败；忽略舍弃单品，分割流程has_cutout_success=false不阻止完成。终态停止轮询并恢复关闭，待选阶段先继续查询美化进度，全部结束后才停止轮询等待用户操作。5项状态专项＋57项组件回归及320／393／1440三尺寸直连模拟通过；未重传真实照片或重交真实选品。


2026-11-11 美化后选品已完成：分割后由Server自动美化；H5每2秒只读查询，全部实例美化终态后才展示勾选及确认入柜。成功项默认勾选，失败项标示并禁选；等待中禁止关闭或提交，不提前调用selection。7项状态＋56项组件及320／393／1440三尺寸模拟通过，真实dev美化和部署未验。
源码依据：Server muse_outfit_segmentation_queue.go在2.1分割完成后enqueueBeautifyTasks；upload_selection.go仍负责显式选择后的分类队列。selection_state=1且任一美化未结束或成功但无图片时，前端为preview_beautifying；全部beautify_status=1且有图或=2失败时才进入awaiting_selection。不新增写接口，不自动调用选品接口。


2026-11-11｜PRD-03 美化等待单品预览（本地已实现）：美化等待区展示分割单品两列图，单件完成切换美化图，并标注正在美化／已美化／美化失败。全部结束后才开放勾选；等待中无选框、无提前提交。63项状态及组件测试通过，320／393／1440px三尺寸模拟通过，无真实业务上传。
