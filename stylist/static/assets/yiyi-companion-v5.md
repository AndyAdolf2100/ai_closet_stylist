# 双助理 v5：完整发型与居中头像

2026-10-28 使用内置 imagegen，以 v4 男女精灵图分别作为身份参考重新生成。最终素材是 yiyi-female-blink-v5.webp、yiyi-male-blink-v5.webp，各 1536×768，六列三行，每格 256×256，无损 WebP。

三行依次为对话、托腮思考、天气。六帧依次为睁眼、30%闭合、70%闭合、闭眼、70%闭合、30%闭合。保留原来的女版 18 秒、男版 20 秒周期、周期内三次短暂眨眼及减少动态效果支持。

生成后按每行首帧的主体范围归一化、居中并打包。每格内容区 188×188，四边留 34px；原始图不等比例的网格按比例适配，避免拉长人物。每行非眼部像素固定，平移配准后仅保留眼部变化。统一浅色背景，并去掉男版思考行的邻行残片。前端不再使用旧版男版顶部 4% 的裁切补丁。

检查：男女三状态六帧的圆形遮罩预览；发型完整、主体居中、无邻行内容。页面仍使用原有 CSS 精灵播放，未添加眼部 DOM 叠层。当前环境没有可用浏览器连接，圆形裁切检查使用最终素材渲染，未冒充浏览器截图或真人主观验收。

## 最终提示词

女版：

```text
Use case: identity-preserve. Edit target: supplied original Yiyi sprite atlas. Regenerate a production-ready blink sprite atlas matching the SAME character identity, illustration style, colors and clothing. EXACTLY SIX equal square columns by THREE rows (18 cells), canvas aspect 2:1, ideally 1536x768. Row 1 front-facing friendly portrait; row 2 quietly resting chin on hand; row 3 holding umbrella with small sun/cloud. Each row eyelids sequence: open, 30% closed, 70% closed, fully closed, 70% closed, 30% closed. Within each row CLONE identical hair, face, mouth, shoulders, props and pose, change ONLY eyelids. Main correction: character must be horizontally AND vertically CENTERED in each square cell, face center aligned with cell center, complete hairstyle visible with ample even negative space. Head including ALL hair must fit inside central 66% width and 68% height of cell, centered around x50%,y43%; shoulders finish around y87%. Need generous 14-18% side margins, 10% top margin. First-row whole hairstyle must remain safely inside an inscribed circle, not merely inside square: this will display as small circular 56px avatar. No hair touches cell edges. Never shift character right. Keep same scale and coordinates across all columns. No grid lines, labels, text, glow, bulb, watermark. Uniform solid background. Female Yiyi: chestnut bob, green flower hair clip, brown eyes, small gold earrings, cream shirt sage vest. Preserve original adult-chibi identity, gentle smile. Background #fff7f3. Full wide bob must fit in circle with equal visible left/right margins.
```

男版：

```text
Create a BLINK ANIMATION SPRITE SHEET, NOT a single avatar. Edit supplied male Yiyi atlas preserving exact character identity, navy cardigan cream shirt dark chestnut short hair and brown eyes. Deliver exactly 18 portraits in a SIX COLUMN by THREE ROW grid, 2:1 wide canvas. Each cell square, fixed camera and scale. Row1 friendly head and shoulders. Row2 quietly smiling resting chin on hand. Row3 holding umbrella small sun and cloud. ALL SIX frames per row are identical except eyelids: fully open,30%closed,70%closed,fully closed,70%closed,30%closed. Whole hairstyle fits in every cell with 15% blank margins left/right and 12% top. Center character horizontally, equal side margins. Head maximum 66% of cell width. Pale blue solid background #f0f4f6. No circle frame, no gridlines, no text, no gradients, no labels, no glow. IMPORTANT output is a complete 6x3 sheet of 18 heads, not one head.
```

男版第一次生成仅返回单张头像，已弃用；以上男版提示词对应重新生成后的完整精灵图。
