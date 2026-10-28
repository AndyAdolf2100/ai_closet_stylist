# 女版衣衣 · 柔光倚窗眨眼 v3

2026-10-28，使用内置 imagegen 编辑 v2。根据反馈收窄肩宽和上身轮廓，柔化肩颈线条，减少开衫与袖子的厚重体积；保留栗色短发、绿色发夹、耳饰、奶油／鼠尾草绿配色及柔光画风。v2 保留以便比较。

文件：`yiyi-female-window-blink-v3.png`，1536 × 1024，3 列 × 2 行，每格 512 × 512。首页和预览页均使用 v3。固定首帧，仅叠加眼部眨眼，裁切顶部 29%、右侧 40%、底部 56%、左侧 28%，保持原有 4.8 秒循环与减少动态效果设置。

## 最终生成提示词

```text
Use case: style-transfer.
Edit target: supplied female Yiyi six-frame windowsill sprite sheet. Create a revised v3 asset for the stylist homepage.
Primary correction: the current shoulders and upper body look broad and masculine. Make her clearly a graceful adult woman with a noticeably narrower, lighter, naturally feminine frame. Redraw the BODY SILHOUETTE, not merely makeup. Reduce shoulder span and upper torso width by about 25 percent, especially the large shoulder on the viewer's right; bring that shoulder inward so there is visible window/background to its right. Give her gently sloping rounded shoulders, a slender natural neck with softer shading, slim arms, smaller delicate hands and wrists. Cardigan should be fine-gauge, softly draping and lightly fitted, not bulky or oversized; reduce the big folded sleeve volume. Keep realistic adult anatomy and normal head-to-body scale, do not enlarge the head to fake petite proportions, no exaggerated bust or hourglass, no deep neckline.
Face: subtly soften the jaw and chin, slightly finer brows, gentle almond brown eyes of the existing natural size and a warm subtle closed-mouth smile. Feminine mature elegance, not chibi or a child.
Preserve: chestnut short wavy bob, side part, sage flower hairclip, gold earrings, cream blouse and sage green cardigan palette. Keep the SAME refined painterly anime style, delicate linework, soft warm window light, pale oak windowsill, blurred blue-green foliage, relaxed cheek resting on hand pose. Preserve head placement, tilt, face size, eye coordinates as closely as possible. Eyes around local x150..295 y150..218. Hair and face should stay in the existing position while the shoulders become narrower. Maintain the same square framing.
Exact layout: 1536x1024 image, exactly 3 columns by 2 rows, six 512x512 square frames, no gaps, no grid lines, no labels. First produce the corrected portrait then duplicate it into six registered frames changing ONLY eyelids. Row-major: fully open, 65% open, 20% open, fully closed, 20% open, 65% open. Head, shoulders, arms, hands, hair, clothes, background, light and mouth must be frozen, pixel aligned across frames; only eye blink changes. No text, logos, watermarks or extra people.
```
