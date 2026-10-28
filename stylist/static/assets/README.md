# 衣衣角色素材

当前运行版本为 [v4 校准精灵图](yiyi-companion-v4.md)：三种状态统一用自然眨眼帧，移除 v2 的整图连续动作和眼睛叠层；人物稳定，无额外光效。下文早期版本仅作历史记录。

2026-10-28 更新：[v2 动画](yiyi-companion-v2.md)固定对话头像，仅眼睛开合；等待与天气各增至 12 帧。

2026-10-28：对话头像、等待状态和天气卡已改用[独立大头动画精灵图](yiyi-companion-v1.md)，男女各一套，支持开心眨眼、托腮思考及通用天气动画。下文六表情在这些位置的使用说明为历史记录。

首页统一采用自然成年人物比例、细腻柔光与放松托腮的窗边近景：[女版 v3](yiyi-female-window-blink-v3.md) 保留栗色短发、绿色发夹与鼠尾草绿服装，[男版](yiyi-male-window-blink-v1.md) 保留短发与海军蓝开衫。身体与窗景固定，仅眼睛开合。男女版可在 `/static/greeting-preview.html` 对照预览。

2026-10-28 新增[男版衣衣六表情](yiyi-male-expressions-v1.md)：海军蓝外套、奶油衬衫、暖灰长裤。主界面顶部可切换女版／男版；原女版素材保留。男版天气预警使用关切思考／撑伞动作，预警等级、正文和安全提示仍以实际数据为准。

旧女版 Q 版窗台眨眼图 `yiyi-window-blink-v1.png` 与原挥手图保留归档；规格及原始提示词见 [旧窗台眨眼说明](yiyi-window-blink-v1.md)。其他位置仍使用下述表情图。

下述六表情素材的生成方式：内置 imagegen；2026-10-27。角色是原创成年女性搭配师，Q版比例，不是小孩。女版对话、等待和天气卡仍使用 `yiyi-expressions-v2.png`，奶油色底，避免复杂透明边缘影响小尺寸显示。`v1`保留为透明底版本。

固定3列×2行，每格512×512。依次为 greeting、weather、wardrobe、thinking、happy、rain；前端用CSS背景位置切换，没有逐帧视频，不是每次等待都实时生图。动作切换对应服务端真实阶段，轻微呼吸动效尊重 reduced-motion 设置。

最终提示词：

> 原创成年女性私人服装搭配师衣衣，Q版大头小身体，栗色短发、鼠尾草绿发夹、奶油色衬衫和绿色马甲、焦糖色中长裙、乐福鞋，温柔专业、清爽的柔和动漫插画。同一人物同一服装，3列2行共六格：微笑挥手、托起太阳云朵查看天气、拿衣架挑选衣服、托腮思考、开心展示搭配、撑伞关心雨天出行。每格完整人物和道具，留安全边距，无文字无水印。v2只将背景改为均匀浅奶油粉（目标#fff7f3），保留人物与六格构图。

禁止把生成的表情当作天气、处理进度或真实试穿成功的证据。相关文字仍以服务端返回为准。

## 天气背景与灾害动作（2026-10-27）

内置imagegen生成并复制至本目录，未使用CLI，未调用积分试穿。

- `weather-sunny-v1.png`：柔和晨光、绿叶、草地。
- `weather-cloudy-v1.png`：阴云、银灰天空与绿色远山。
- `weather-rain-v1.png`：雨中花园、叶片水滴与浅景深。
- `weather-snow-v1.png`：雪枝、雪原与柔和飘雪。
- `weather-fog-v1.png`：雾中森林和层叠山峦。
- `weather-wind-v1.png`：风中弯曲的草地与流动云层。

背景共用提示词：唯美自然摄影，3:2横向移动端天气卡背景，奶油、鼠尾草绿、淡粉的克制色调，左侧和中部保留柔和留白方便叠加深色文字，无人物、可辨识地标、建筑、文字或水印；按上述六种天气分别呈现自然环境。这是氛围图，不是当地天气观测照片。

`yiyi-hazards-v1.png`：以原衣衣六动作图作身份参考，生成4列4行16格素材，成年女性角色保持一致，温柔关切而非在灾害中嬉笑。逐格提示词：撑伞暴雨、围巾雪花、雾中提灯、护帽收围巾的大风、室内雷电、遮阳帽与饮水、厚外套寒潮、防护面罩沙尘、稳健鞋履留意结冰、室内避冰雹、干旱饮水提示、远离火险、室内关窗避台风、室内避龙卷风、远离洪水低地、通用三角警示。统一浅奶油底、无文字无官方标志；图片是辅助表达，不是应急动作教程。

## 新增雷雨与大雨／暴雨背景（2026-10-27）

使用内置 imagegen，以现有 rain、cloudy 图片作为风格参考生成，保留原有素材。两张均为 1536×1024（3:2）。

- `weather-thunder-v1.png`：灰蓝积雨云、远处闪电、柔和绿色山谷；闪电置于右上，适配卡片渐变。
- `weather-heavy-rain-v1.png`：原有花园氛围、密集雨线、叶片流水与水面溅雨。

前端分类保留原有冰雪优先级，其次含「雷」使用雷雨图，含「大雨／暴雨」使用大雨图，其他雨天使用原小雨图。昼夜条件均参与匹配；多日预报仍共用一张氛围背景，不代表每一天都出现同种天气。分类仅依据天气文字，不推断或替代官方预警等级。

### 最终生成提示词

雷雨（引用原 rain、cloudy 两图作为风格参考）：

```text
Use case: photorealistic-natural. Asset type: weather-card background, new THUNDERSTORM sibling asset for an existing gentle weather photo set. Input image 1 (rain garden) and image 2 (cloudy hills) are style and palette references only. Create one landscape 3:2 photo, ideally 1536x1024. Scene: soft sage-green hills and a few wet leaves in the right foreground beneath gray-blue thunderclouds. One unmistakable yet restrained slender branching lightning bolt in the upper-right third, visible even in a small weather card; fine rain streaks on the right. Keep the reference collection's creamy diffuse daylight, desaturated sage greens, subtle blush wildflowers, soft photographic depth and quiet natural elegance. Thunderstorm must be distinguishable from ordinary light rain, without becoming black, neon purple or apocalyptic. Right half holds the lightning/cloud/weather detail; left and center softer, lighter and uncluttered for dark text and CSS fade. This is a new natural scene, not a UI mockup. No text, icons, frames, people, buildings, landmarks or watermarks; no flooding or disaster imagery. Do not bake in a white gradient; natural image edge to edge. Save a new asset, do not replace references.
```

大雨／暴雨（引用原 rain 图作为风格参考）：

```text
Use case: photorealistic-natural. Asset type: new HEAVY RAIN weather-card background sibling of attached reference rain-garden photo. Input image is a style/palette/composition reference. Generate a single new landscape 3:2 photo, ideally 1536x1024, matching its creamy gray daylight, muted sage-green leaves, subtle pale blush flowers, dreamy natural photography and soft depth of field. Make rainfall clearly heavier than the reference: dense visible diagonal rain streaks across the right and upper-middle, heavy droplets running from wet leaves on the right, many overlapping raindrop splashes and concentric ripples on a garden pond at lower right, a soft curtain of rain obscuring distant greenery. Keep it bright enough to use as a warm cream weather UI background; calm overcast daylight, no lightning, no bright sun, no black storm sky, no flooding, no people/buildings/landmarks, no text/icons/watermarks/borders. Most recognizable heavy-rain details in the right half and upper right because left and bottom will fade under CSS. Left third soft and uncluttered but natural, not a painted white fade. Do not create a collage or UI mockup. This is a new sibling image, do not overwrite reference.
```
