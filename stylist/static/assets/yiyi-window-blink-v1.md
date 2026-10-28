# 衣衣窗台眨眼循环

此图为旧版 Q 版素材，已保留归档；2026-10-28 首页改用自然成年比例的[女版柔光倚窗 v3](yiyi-female-window-blink-v3.md)。

2026-10-27，使用内置 imagegen，以原 `yiyi-expressions-v2.png` 为形象参考生成。原挥手素材保留。

文件：`yiyi-window-blink-v1.png`；1536×1024，3列×2行，每帧512×512。固定窗台、身体和头部，以首帧作底，仅叠加眼睛区域（顶部38%、右侧28%、底部43%、左侧28%裁切）进行帧切换，避免整幅生成帧的细小位置变化引起抖动。

每4.8秒循环，前90%为睁眼停留，其后依次半闭、将闭、闭眼、将开、半开，回到首帧。系统减少动态效果时静态显示。预览：`/static/greeting-preview.html`。

## 最终生成提示词

```text
Use case: illustration-story. Asset type: accurately registered 6-frame BLINK sprite sheet, new variant for Yiyi website welcome mascot. Reference image is existing Yiyi character identity: chestnut bob, sage butterfly hairclip, brown eyes, gold earrings, cream shirt and sage vest; original ADULT female stylist in soft chibi anime illustration, warm cream/sage/caramel palette. Create EXACT 1536x1024 landscape sprite sheet, 3 columns x 2 rows, each square cell512x512, equal grid no gaps no borders no numbers. New pose in EVERY cell: frontal medium close-up of Yiyi leaning comfortably on a warm pale wooden windowsill, both forearms folded on the sill and chin resting softly on her arms, looking toward viewer, gentle small closed-mouth smile. A tiny hint of cream window jamb at far side if desired, otherwise clean uniform #fff7f3 background. Crop as upper-body portrait, no feet, no scenery or props. Face centered at local x256 y228, head top y80, windowsill horizontal at y400, arms span x110..400. Everything comfortably inside circular UI crop. ALL SIX CELLS MUST BE EXACTLY IDENTICAL in head location, size, hair, eyebrows, nose, mouth, arms, windowsill and background. Absolutely NO head bob, no breathing, no hand movement, no changing smile, no perspective or zoom shift; create first cell then duplicate its pixels to all other cells changing ONLY eyelids. Sequence row-major: 1 eyes fully open; 2 eyes 65 percent open; 3 eyes 20 percent open; 4 eyes gently fully closed; 5 eyes20 percent open; 6 eyes65 percent open. Both eyes synchronized, normal blink not wink. Cell6 returns to cell1 seamlessly. No extra characters or text/watermark. Registration and minimal differences matter most: same character frozen at windowsill, only eyelids animate. New sibling asset, do not replace reference.
```
