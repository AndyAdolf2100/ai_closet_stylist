# 男版衣衣 · 倚窗眨眼

生成时间：2026-10-28。使用内置 imagegen。以女版窗台图作构图参考、男版六表情图作人物与服装参考，新增独立近景素材，原素材均保留。

文件：`yiyi-male-window-blink-v1.png`，1536 × 1024，3 列 × 2 行，每帧 512 × 512。男版衣衣倚在浅木窗台边，放松地托着脸，身穿奶油衬衫与海军蓝开衫；采用更自然的成年人物比例和柔和的窗边光线。

仅男版首页使用此图，其他对话、天气及等待表情继续使用六表情素材。首页以第一帧为固定底图，仅叠加眼睛区域播放六帧，避免头部、手臂与窗景在帧间抖动。每 5.6 秒循环一次，先保持睁眼，末段完成轻柔的开合。系统开启减少动态效果时保留静态首帧。

实际成图为轻微倾斜的倚窗姿态；眼部叠加裁切采用顶部 29%、右侧 40%、底部 56%、左侧 27%，覆盖两只眼睛，保留首帧的头部、鼻子、嘴、手臂及背景。

预览：`/static/greeting-preview.html`，可切换女版／男版，对照桌面／手机尺寸，并查看自动眨眼、静态睁眼与闭眼效果。

## 最终生成提示词

```text
Use case: illustration-story.
Asset type: accurately registered 6-frame subtle blink sprite sheet for an adult male personal stylist website welcome portrait.
Primary request: redesign the male homepage character as a beautiful, serene adult man leaning at a sunlit window, like the intimate relaxed windowsill portrait in reference 1, blinking gently. Reference 1 is COMPOSITION / POSE reference only (female windowsill sprite); reference 2 is MALE CHARACTER IDENTITY / clothing reference only (male six expressions). Create a new sibling asset; do not alter either reference.
Subject: original adult male stylist Yiyi, approximately late twenties, softly tousled short dark chestnut hair with a natural side part, warm brown eyes, a refined quietly handsome masculine face, cream open-collar shirt and slate navy cardigan. Maintain recognizability with reference 2, but make this close portrait more elegant and mature, with smaller naturally proportioned eyes, subtle facial shading and a soft closed-mouth half-smile. No childish baby face, no exuberant wave or goofy grin.
Scene / pose: waist-up intimate portrait, leaning comfortably against a pale oak windowsill. Forearms rest loosely crossed on the sill, one relaxed hand supporting the side of his jaw; head tilted only slightly toward that hand, looking warmly toward the viewer. Relaxed shoulders. A slim ivory window frame at the far left, diffuse soft morning light, lightly blurred pale blue-green view outside. Airy, peaceful, delicate and romantic in the sense of a beautiful quiet everyday moment. No extra objects.
Style / palette: refined soft Japanese/Korean storybook anime illustration with delicate linework, painterly translucent light, subtly textured paper, dreamy but clean; pale ivory, muted powder blue, navy, warm wood and warm skin. Bust portrait instead of full-body mascot; natural adult proportions, no huge chibi head or giant sparkling eyes.
Exact layout: EXACT 1536x1024 landscape canvas, exactly 3 columns x 2 rows of square 512x512 frames, equal grid, NO gaps, NO borders, NO labels. Same camera and crop in every frame. Head top approximately local y55, face centered x256 y225, eyes centered near local y240, windowsill horizontal at y405. Keep both eyes within local x140..370 and y210..278. Leave calm airy margins, all important details inside rounded-square UI crop.
Animation invariants: build frame 1, duplicate it to all cells, and change ONLY the eyelids within the eye region. All six frames MUST have exactly the same hair, head position, eyebrows, nose, mouth, hand, body, window, background, lighting, and pixel registration. NO head bob, breathing, hand movement, smile changes, zoom, drift or perspective shift. Row-major sequence: 1 eyes fully open; 2 eyes 65 percent open; 3 eyes 20 percent open; 4 both eyes gently fully closed; 5 eyes 20 percent open; 6 eyes 65 percent open. Normal synchronized blink, NOT a wink. Stable body and scene for a CSS eye-only animation.
No text, no numbers, no logos, no watermarks, no extra characters, no women.
```
