# 男版衣衣六表情

生成时间：2026-10-28。使用内置 imagegen；原女版 `yiyi-expressions-v2.png` 仅作画风参考，新建男版角色，未覆盖原图。

文件：`yiyi-male-expressions-v1.png`，1536 × 1024，3 列 × 2 行，每格 512 × 512。按行依次为：挥手问候、查看天气、挑选衣物、认真思考、展示搭配、撑伞提醒。背景为浅雾蓝，服装为奶油衬衫、海军蓝外套、暖灰长裤和棕色乐福鞋。

动态创建的对话头像、等待阶段及天气卡使用同一六格素材；男版预警角色采用思考或撑伞动作，灾害类型、等级、正文和防护提示继续显示真实数据。预警插画仅为辅助表达，不作为应急动作教程。首页已改用独立的[倚窗眨眼近景](yiyi-male-window-blink-v1.md)。

顶部「搭配师形象」切换同时更新角色、配色、欢迎文案、输入提示及按钮选中状态。偏好仅保存在浏览器 `localStorage`；存储不可用时仍可即时切换。首次访问默认女版，恢复已保存偏好时在首屏绘制前应用配色。切换不发送 API 请求，不更改会话、输入、任务性别、天气选择或费用确认。

男女版首页均使用各自的窗边眨眼素材。等待角色沿用轻微呼吸效果，并遵循系统减少动态效果设置。

## 最终生成提示词

```text
Use case: illustration-story. Asset type: production character expression sprite sheet for a Chinese personal stylist web app. Input image 1 is a STYLE REFERENCE only, existing original adult female Yiyi. Create a NEW MALE counterpart of Yiyi, clearly an ADULT young male personal fashion stylist, in the same refined soft chibi anime illustration quality. Short textured dark espresso hair, side part, warm brown eyes, gentle confident smile, no beard, NO hair clips, NO earrings. Cream open-collar shirt, slate navy-blue cardigan jacket, warm taupe straight trousers, brown loafers, subtle watch. Male silhouette and facial features, approachable and professional. Palette navy, mist blue, warm ivory, taupe. EXACT 1536x1024 canvas, exactly 3 columns by 2 rows, each 512x512 square, no gaps/borders. Uniform very light cool ivory background #f0f4f6. Exactly the SAME male character, hair and outfit in all six cells. Each figure centered with 7 percent safe margins and no spill between cells. Row-major poses: 1 smiling and waving hello, 2 checking weather with a small sun and cloud above one open palm, 3 holding two hangers with a navy overshirt and cream jacket, 4 hand on chin thinking thoughtfully, 5 smiling and presenting a neatly coordinated outfit on a hanger, 6 holding an umbrella with a caring serious expression and small raindrops. All six are complete full-body figures, consistent head size, chibi adult proportions like reference. Painterly crisp fine lines, gentle shading, polished website mascot, mature friendly character. No female characters, no text, no letters, no numbers, no watermark. This is a new sibling asset; preserve reference image unchanged.
```
