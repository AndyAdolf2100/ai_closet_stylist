# 星座、记录、形象、天气与立绘偏位修复

日期：2026-11-03。范围：iOS独立Stylist模块；Web参考675d59a加当前工作区。沿用stylist-ios-parity，不修改后端运行时。

[Web／修复前／修复后对照](../var/ios-four-fix-20261103/index.html)。素材和测试均不含真实用户图片。旧审查报告保留为修复前证据，本文更新这四页及人物裁切状态，不将其他页面差异一并标成已解决。

## 已修改

- **星座两项根因**：父卡片先于图片子视图完成布局时建立空蒙版；现在由图片视图自身layoutSubviews基于有效bounds更新frame与path。修复后发现旧图集仍是zodiac-starfields-v2，经SHA256确认后替换为正式Web的zodiac-illustrated-starfields-v3。现在插画可见，保留三列拱顶与底部圆角，章节改为下划线，补“暂不选择”。图片为本地资源，不是远端接口加载失败。
- **记录页**：补日常小记眉题、对应角色头像与渐变信笺、同款空态说明、上传及形象入口。头像复用角色对话素材，保留网络记录加载和任务入口。
- **试穿形象**：自定义圆角遮罩面板，补信笺、三步说明、照片卡与真实缺图占位、选择勾选、上传入口、积分和固定确认底栏。选择卡仅改变本页草稿，确认按钮继续使用twins/default及selection_version；不因选卡触发图片生成或费用。真实图片与账号保存未执行。
- **天气**：复用8张Web天气场景PNG（逐张SHA256相同），按实际天气选择背景；展示当前角色天气头像、日期、天气图标、温度、日夜描述、逐日提醒及展开数据说明。选择城市后回到主页面内卡片，移除此前单独的纯文字全屏结果页。无温度显示缺省占位，不编造天气；新对话和换号清理本页天气。
- **人物歪／偏位**：此前将三视图左侧1/3裁出后统一居中，遗漏Web逐角色left参数。现在使用完整1536×1024原图，按六角色原始scale、top、left和clip-path inset(0 62% 0 7%)建立布局，保留480/1024画框比例。没有旋转、拉伸人物，也没有重新生成人物。背景改为主题渐变。

## 验证与边界

- 32项核心模拟检查通过，无真实网络或费用。
- iPhone17与SE定向截图和交互检查：记录、星座、形象、城市／天气／返回上传流程；人物选择覆盖男女六张立绘；形象弹层横屏关闭和确认可达。
- 使用本地8477合成接口，UI测试会改变模拟状态；未调用真实账号写入、上传、生成或扣费。人物缺图夹具只验证占位，不算真实图片验收。
- 原始xcresult：`/tmp/StylistFourVerified.xcresult`（双机型逐页及天气）、`/tmp/StylistPortraitAligned.xcresult`（双机型角色）、`/tmp/StylistWeatherVerified.xcresult`（最后天气复测）。以各结果实际状态为准。
- 本轮截图以女主题为主，人物页覆盖男主题；系统色全页面、Duo容器和真机尚未完整复验。字体、部分微间距、人物文案和其他页面仍有差异，不宣称100%像素一致。

## 实现位置

目标仓库 `AICloset/Sources/Module2.0/Stylist/`：

- UI/Shared/StylistArtCards.swift：星座蒙版、立绘完整图裁切、共用信笺。
- UI/Shared/StylistUI.swift、StylistControls.swift：标题、底栏、章节及自定义面板。
- UI/Media/StylistMedia.swift：记录、形象卡与显式确认。
- UI/Chat/StylistCards.swift、StylistViewController.swift：图文天气及主页面承载。
- Resources/StylistAssets.xcassets：当前星座v3、8种天气背景。
- Tests/StylistUITests.swift：页面就绪截图、天气回页和横屏操作可达验证。
