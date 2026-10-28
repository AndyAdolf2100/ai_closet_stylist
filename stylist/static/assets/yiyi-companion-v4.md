# 双助理 v4：校准后的眨眼精灵图

使用内置 imagegen 重新生成男女各一套三状态眨眼帧，再进行生产素材的网格归一化、平移配准与固定非眼部像素处理。前端只播放打包好的精灵图，不创建眼睛覆盖层，不使用透明度过渡，不添加灯泡、光晕或云朵图层。

文件：yiyi-female-blink-v4.webp、yiyi-male-blink-v4.webp。各 1536×768，6 列×3 行，单格 256×256；无损 WebP，避免压缩造成不同帧的固定区域出现差异。

三行分别是开心对话、安静托腮思考、持伞天气。每行六格：睁眼、30%闭合、70%闭合、闭眼、70%闭合、30%闭合。人物姿势、道具固定。生成的原始帧有轻微位置误差，因此打包时以每行首帧为基准对齐，并固定眼睛之外的像素；这些修正已烘焙在图片内，不在浏览器中叠加。

节奏：女版18秒、男版20秒周期内各眨眼3次，不等间隔约5–7秒，每次约0.22–0.24秒，其余时间停留在睁眼格。动态创建的头像随机错开起始时点，避免同步眨眼。保留减少动态效果、预览暂停；无整个人物位移或缩放。裁去边缘1px采样及男版思考行顶部邻行残片。

验证：男女×对话/思考/天气共六种显示状态的睁眼与闭眼截图比较，眼睛以外的主体像素稳定；检查页面无伪元素图层、无脚本错误，减少动态效果可停在睁眼帧。预览地址 /static/companion-preview.html。不能用自动检查替代用户对眨眼自然程度的主观确认。

## 女版最终生成提示词

```text
Edit reference original female chibi Yiyi. Make a technically aligned ANIMATION SPRITE ATLAS: exactly SIX columns THREE rows, 18 square cells, 2:1 aspect. Each row is SIX consecutive frames of ONE blink. Crucial: clone the EXACT SAME drawing 6 times across each row; change ONLY eyelids. Hair silhouette, face contour, eyes positions, nose, mouth, clothing, hands, background and props must be pixel identical within row. No head tilts, no size changes, no body motion. Row1: happy big head shoulder portrait, front-facing, friendly small smile. Row2: same original woman gently smiling with chin resting on hand, thoughtful expression. NO LIGHT BULB, NO GLOW, NO SPARKLES ANYWHERE. Row3: same original woman holding umbrella with small sun and cloud alongside, props stay completely still. SIX frames in each row: 1 fully open eyes, 2 eyelids 30% down, 3 eyelids 70% down, 4 gently fully closed eyes, 5 eyelids 70% down, 6 eyelids 30% down. Real eyelid motion, no eye translation, no melting face, no closed-eye image crossfade. Warm brown eyes, chestnut bob green hairclip, cream blouse sage vest. Pale cream uniform background #fff7f3. Every cell exact same registration and scale, adult chibi head 75%cell with safe margins. Clean simple crisp lineart. NO labels/borders/watermarks. It must look like animator drew eyelids over a locked base cel, NOT different portraits.
```

## 男版最终生成提示词

```text
Reference original adult male chibi Yiyi. NEW technically aligned ANIMATION SPRITE ATLAS: SIX columns THREE rows,18 equal square cells,2:1 aspect. Each row SIX frames of SAME locked pose blinking. CLONE the EXACT same drawing six times within each row then ONLY change eyelids; hair silhouette, head contour, face placement, nose, mouth, shoulders, hands and props MUST be identical. Do NOT redraw different portraits, no bobbing or head rotation or scaling. Male short dark chestnut hair brown eyes cream shirt navy cardigan no earrings/clips. Row1 happy front-facing bighead shoulder portrait gentle small smile. Row2 thoughtful hand resting at chin smiling gently, NO bulb NO glow NO sparkles. Row3 holding umbrella, little sun/cloud beside face; weather props fully static. Six eyelid stages EACH row:1 fully open,2 30%closed,3 70%closed,4 fully gently closed,5 70%closed,6 30%closed. Eyelids descend naturally without moving eyes or skin; not fading between two eye drawings. Pale blue uniform #f0f4f6 background. Head occupies75%cell, safe margins. Crisp simple shading and elegant anime lines. No text gridlines captions watermark. Exact mathematical registration of all six columns. Think hand-drawn animation with locked base cel and only eyelid drawing changes.
```
