# 双助理动态大头头像

2026-10-28，使用内置 imagegen 生成两套原创角色精灵图，再以 WebP quality 90 编码供浏览器使用；没有调用 CLI 生图或积分试穿。

- 女版：`yiyi-female-companion-v1.webp`
- 男版：`yiyi-male-companion-v1.webp`
- 两套均为 1448 × 1086，4 列 × 3 行，每格 362 × 362。
- 第 1 行：开心睁眼 → 半闭 → 闭眼 → 半睁，4.8 秒循环，长时间停留在睁眼帧。
- 第 2 行：托腮、转动目光、眨眼、灵感灯泡亮起，1.8 秒循环；所有 SSE 等待阶段使用此行，文案仍来自真实阶段。
- 第 3 行：通用天气陪伴，太阳、云朵、雨伞与眨眼，3.2 秒循环；不表示当前实际天气。

对话头像从 35px 全身图改为 48px 大头近景；天气头像 68px；等待头像桌面 100px / 手机 82px。CSS 离散切帧，不使用视频或每次请求实时生成。支持系统减少动态效果。首页窗边素材及天气预警素材不变。思考容器裁掉底部 5% 的邻行道具边缘，避免串帧。

预览：`/static/companion-preview.html`，支持男女切换、暂停动画。

浏览器检查：男女两套资源、六个 SSE 阶段、四个离散帧位置、对话与天气行、手机布局、减少动态效果以及等待节点清理均通过；无脚本错误。截图和临时检查脚本保留在 var/persona-review，不提交。

## 女版最终提示词

```text
Use case: illustration-story. Create a production animation sprite atlas for an original adult personal stylist assistant, using reference only for character identity and illustration style. EXACT regular 4 columns by 3 rows grid, 12 equal square cells, no gaps, no borders, no text. Canvas aspect 4:3. Same aligned fixed camera close-up CHIBI BIG HEAD and tiny shoulders in every cell, face and hair occupy 75 percent of cell, never full body. Keep head center, scale, hair silhouette identical between frames in each row, safe margins. Character: original adult FEMALE, chestnut bob, small sage green flower hair clip, warm brown eyes, cream blouse and sage vest, cheerful warm smile. Fine clear anime lines, simple clean shading legible at 48px. Solid uniform pale cream #fff7f3 background, no transparency. Row1 four animation frames of happy friendly face: eyes open, eyes half shut, both eyes gently fully closed smiling, eyes half open. Exactly same head pose and smile, only eyelids change. Row2 four sequential brainstorming animation frames: chin on one hand, thoughtful but friendly face, eyes glance left, glance up, soft blink, glance forward; tiny idea bulb beside head gradually glows, hand and head aligned, no text. Row3 four sequential general weather companion frames: smiling big head with little sun and fluffy cloud to one side and small closed umbrella handle visible near shoulder, cloud subtly drifts and sun rays vary, eyes open, half closed, closed, open. All weather props stay within cell, balanced visible face. No extra panels, no captions, no watermark. Must be usable as an aligned animation sheet.
```

## 男版最终提示词

```text
Use case: illustration-story. Production animation sprite sheet. Reference image is character identity/style reference only. Original adult MALE stylist: short textured dark chestnut side-parted hair, warm brown eyes, navy cardigan over cream shirt, no hair clips, no earrings. EXACT 4 columns x 3 rows of equal square cells, canvas aspect 4:3, no borders or gaps or text. BIG HEAD CHIBI closeup, hair and face occupy 75% of each cell, tiny shoulders only, never full body. Same aligned head center scale and silhouette within every row. Solid uniform pale blue #f0f4f6 background. Clear crisp anime lines and soft shading, friendly joyful mature character, readable at 48px. ROW1: four sequential frames of friendly smiling face blinking: open eyes, half shut, fully closed, half open. Pose and mouth identical, only eyelids change. ROW2: four sequential brainstorming frames, one hand at chin, thoughtfully happy: eyes glance left, up, gently blink, forward; tiny lightbulb beside head gradually glowing, same aligned head and shoulders. ROW3: four sequential weather companion frames: joyful face with small sun and fluffy cloud to one side and small umbrella handle near shoulder; cloud gently moves, rays vary, eyes open/half closed/closed/open. Props entirely within each cell. Every frame square, safe margins, precise regular grid, no labels, no watermark, no extra panels. This is a functional sprite atlas with 12 frames, not a poster.
```
