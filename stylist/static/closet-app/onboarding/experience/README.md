# 第3～5步完整体验交互示意

日期：2026-11-09。入口：`/static/closet-app/onboarding/experience/index.html`。

此目录是独立概念预览，复用现有Onboarding三色、纸页、小笺、五段进度和底部操作栏，不加载正式引导控制器，也不改变正式App路由。

- 第3步：穿搭照片本地预览／示例 → 拆衣独立确认示意 → 确认上装和下装 → 搭配。
- 第4步：人物照片本地预览／示例 → 形象独立确认示意 → 人物形象。
- 第5步：先弹产品定位说明，可拒绝、示例定位或手选城市 → 组合已确认搭配和形象 → 独立试穿确认 → 固定试穿结果。
- 未确认搭配或形象时阻止试穿并提供补齐入口；返回保留当前页材料，修改照片或单品后清除下游试穿结果。
- 全程无fetch、真实GPS、账号访问或浏览器存储；文件只使用当前页Blob URL，刷新清空。本地选图后固定示例不冒充该照片的识别或合成结果。
- 正式接入、价格、远端处理、持久化续接、账号隔离和真实失败恢复均待实现。示例加载状态只表示演示过场。

## 素材

`../../first-visit/assets/`的tryon-example、shirt-example、jeans-example、outfit-example沿用项目内置合成示例，出处见该目录README；不是用户照片、真实库存或本轮业务生成。

`avatar-sample.png`由内置imagegen工具以tryon-example为参考生成，用于模拟上传人物形象。非付费业务接口效果；项目只引用此目录副本，不依赖本机生成缓存。提示词：

> Use case: identity-preserve. Create ONE photorealistic full-body studio digital fitting avatar photo for a fashion onboarding interactive prototype. Edit target is the referenced AI-generated adult woman. Preserve her face, adult age, long dark hair, body proportions and recognizable identity. Show her standing front-facing in a relaxed neutral pose, both arms slightly away from body, entire head to white sneakers fully inside the frame with margin. Replace outfit with a simple opaque plain white short-sleeve crew-neck T-shirt and slim charcoal straight trousers, no hat, no bag, no drink, no jewelry. Replace street background with a softly lit warm off-white seamless studio background. Natural proportions, understated editorial photography. This is an invented demo person, not a user photo. No text, no watermark, no collage, no UI. Portrait aspect ratio 3:4.

本地前后图、设计审阅与浏览器验证记录在忽略目录`reports/26-11-09/change-log/onboarding-concept/`，不混入正式App变更台账。
