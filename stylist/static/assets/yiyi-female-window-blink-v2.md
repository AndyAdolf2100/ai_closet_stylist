# 女版衣衣 · 柔光倚窗眨眼

生成时间：2026-10-28。使用内置 imagegen，以男版倚窗图作为画风、比例、构图和光线参考，以旧女版图作为栗色短发、发夹、耳饰和奶油／鼠尾草绿配色参考。新增独立素材，原图保留。

文件：`yiyi-female-window-blink-v2.png`，1536 × 1024，3 列 × 2 行，每格 512 × 512。女版衣衣采用自然成年人物比例、细腻柔光和安静的倚窗托腮近景，与男版首页保持同一插画风格。

首页固定第一帧的身体、手臂和窗景，仅叠加眼部开合（裁切：顶部 29%、右侧 40%、底部 56%、左侧 28%）；遵循系统减少动态效果设置。预览入口：`/static/greeting-preview.html`，可对照桌面／手机尺寸、睁眼／闭眼效果。

## 最终生成提示词

```text
Use case: illustration-story.
Asset type: accurately registered 6-frame subtle blink sprite sheet for the adult FEMALE Yiyi personal stylist website welcome portrait.
Primary request: make the female counterpart of the beautiful mature male windowsill portrait in reference 1, with exactly the same refined illustration style, natural adult proportions, intimate framing, soft light and quiet mood. Reference 1 (male windowsill sheet) is the PRIMARY STYLE, POSE, COMPOSITION and LIGHTING reference. Reference 2 (old female chibi windowsill sheet) is ONLY an IDENTITY-COLOR reference for her chestnut bob, small sage hair clip, gold earrings and cream/sage clothes. Do NOT copy its chibi proportions or giant eyes.
Subject: original adult woman Yiyi, late twenties, naturally proportioned slender oval face, gentle brown almond eyes of realistic anime size, softly shaped nose and lips, subtle warm skin shading, a graceful closed-mouth half-smile. Chestnut chin-length wavy bob with a side part, one small understated sage-green hair clip, small gold earrings. Cream collared blouse under a muted sage-green finely knitted cardigan. Elegantly grown-up and quietly beautiful; not a child, no huge head, no baby face, no giant round eyes, no exaggerated blush.
Scene / pose: upper-body close portrait, leaning comfortably at a pale oak windowsill. One forearm rests across the sill; the other elbow rests there while her relaxed hand softly supports the side of her jaw. Head tilts gently toward the supporting hand; she looks warmly toward the viewer. Same natural anatomy, camera angle and subject scale as the male in reference 1. Slim ivory window frame at the far left, a lightly blurred pale mint-green and blue view outside, diffuse warm morning sunlight on her hair. Airy and peaceful.
Style / palette: EXACTLY match the male reference's delicate Japanese/Korean painterly anime portrait style: fine linework, natural face, translucent soft sunlight, subtle paper texture and dimensional hair, refined rather than cartoonish. Ivory, sage, warm chestnut, warm wood, gentle skin tones.
Exact layout: EXACT 1536x1024 landscape canvas, exactly 3 columns x 2 rows, six square 512x512 frames, equal grid, NO gaps/borders/labels. Same camera and square crop in all six frames, upper body only, no feet. Match the male reference's framing: hair near local y10, eyes around local x160..300 and y155..225, window sill near local y480; important face and hand details safely inside rounded-square UI crop.
Animation invariants: build frame 1 and duplicate it to all six cells, changing ONLY eyelids. Hair, head position, eyebrows, nose, mouth, hands, body, window, background and lighting MUST remain exactly pixel-registered and frozen. NO head bob, breathing, gesture, changing smile, camera motion, drift or zoom. Row-major blink sequence: 1 both eyes fully open; 2 both eyes 65 percent open; 3 both eyes 20 percent open; 4 both eyes gently fully closed; 5 both eyes 20 percent open; 6 both eyes 65 percent open. Synchronized normal blink, NOT a wink.
No text, no numbers, no logos, no watermarks, no extra characters or men. New sibling asset, preserve both reference files unchanged.
```

