# 衣衣循环挥手精灵图

生成方式：内置 imagegen；2026-10-27。以 `yiyi-expressions-v2.png` 中左上角衣衣作为形象参考，新生成独立素材，原表情图保留。

文件：`yiyi-greeting-loop-v1.png`，1536×1024，3列×2行，每帧512×512。按行播放六帧，CSS `steps(1,end)` 每1.2秒循环；仅首页欢迎角色使用，其他天气、等待、对话角色仍用原表情图。遵循系统 `prefers-reduced-motion`，开启时保持首帧静态。

预览：`/static/greeting-preview.html`。

## 最终生成提示词

```text
Use case: illustration-story. Asset type: production animation SPRITE SHEET for a looping friendly greeting, NOT six different expressions. Reference image: use ONLY the top-left waving character as the exact character/style reference; other cells only support consistency. Original adult woman stylist Yiyi, chibi proportions, chestnut short bob, sage butterfly hairclip, large brown eyes, small gold earrings, cream collared blouse, sage green waistcoat, caramel midi skirt, brown loafers. Preserve the reference face, outfit, colors, warm clean soft anime illustration. Output EXACT 1536x1024 pixels, seamless uniform pale cream blush background #fff7f3, EXACT 3 columns x 2 rows equal 512x512 square cells, no gutters, no dividers, no labels. Six consecutive frames in row-major order of ONE subtle seamless waving loop. Same frontal standing pose with BOTH feet planted, same body/head anchor and scale in every cell: center x256 relative to each cell, hair top y55, shoe baseline y455, full character including waving hand entirely inside x65..447 y45..460, ample safety margins for circular UI crop. Keep head and body almost identical across frames, same smile and open eyes throughout. Animate ONLY the raised greeting forearm and wrist, with tiny hair response: frame1 hand tilted -12deg, frame2 -4deg, frame3 +8deg, frame4 +12deg, frame5 +4deg, frame6 -8deg; frame6 flows back to frame1 with no jump. Free arm relaxed by side identical every frame. No foot movement, no stepping, no props, no extra arms, no alternate outfits, no UI, no words, no watermark. Precision registration across frames matters more than pose variety. This is a new sprite asset, preserve existing reference.
```
