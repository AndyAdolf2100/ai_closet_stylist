# 搭配卡保存到我的搭配

2026-11-10，2.0.1，基线4297959。本地已实现；真实远端写入／列表回读尚未验收。

搭配卡「下载」改为「保存穿搭」。点击只调用Server MCP `save_recommended_outfit`，不下载图片、不生成试穿、不请求积分扣费。成功显示「已保存」并提示到「我的搭配」查看。系统参考款会被Server归入个人衣橱，点击时明确确认；部分搭配仅保存实际单品，文字参考不包含在内。纯文字方案无保存按钮。试穿的既有费用确认保留。

## 接口与边界

- GET/POST `/stylist-api/conversations/{id}/saved-outfit`，鉴权取当前身份；version、look_index定位原始已完成回复。POST只额外接受include_system，不接受客户端商品、owner或图片数据。
- 历史卡保存历史版本原方案，不保存当前最新方案。Server写入前product.resolve重读可用性；缺件、接口不可用或参数变化直接阻止。
- 本地新增stylist_outfit_saves（SQLite/PostgreSQL及MySQL兼容schema），按账号、会话、版本、方案生成稳定selection_id。原子认领且不持有跨网络事务；已成功重复点击复用记录；多实例重复提交返回saving。
- 派发后出错／进程中止均不能证明远端未写入：结果unknown，不自动或手动盲目重放。saving超过300秒只读显示unknown，提示用户查看我的搭配。后续远端状态对账能力不在当前接口内。
- 成功返回outfit_id与outfit_id_type=2。我的搭配继续每次打开读取既有 `/api/ai_outfit_merge_my_outfit/list`，无需另建本地搭配列表。
- 已核对Server源码：internal/controller/mcp/tools/algorithm.go → internal/service/user_outfit/prepare_tryon.go，创建user_outfit及user_outfit_item，来源user传用户单品ID；system传系统商品ID。此为本地契约证据，不代表远端已部署。
- 网页读状态失败不会自动保存；点击时后端重新鉴权。保存中禁用按钮；换号忽略迟到响应。新页面、刷新和历史卡通过GET恢复状态。

## 验证

39项后端相关测试、15项前端测试通过；47项真实本机PostgreSQL临时库专项通过（含既有回归，不重复计为新增用例）。外部Server、身份和业务均模拟；临时数据库已删除，无真实保存、上传或扣费。浏览器使用真实H5和模拟业务验证保存按钮、成功提示、我的搭配展示及详情入口。

本地前后红圈文档：`reports/26-11-10/change-log/docs/UI_CHANGELOG.html`。截图是系统配色隔离示例，不含真实账号资料。

## 当前本地入口

2026-11-10纠正：8466原先仍运行main旧下载回调；现已通过uvicorn --app-dir加载ai_closet_stylist_features的2.0.1代码，沿用原目录配置。ready与实际静态资源核对通过，保存接口无身份返回401。按钮名称最终为「保存穿搭」，列表入口仍为「我的搭配」。已打开旧页面须刷新加载新脚本，未执行真实远端保存。
