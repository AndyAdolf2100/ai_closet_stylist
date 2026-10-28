# 双助理动画 v2

内置 imagegen 生成新的男女活动精灵图，WebP quality 90 编码；原图保留，不覆盖 v1。

- yiyi-female-activity-v2.webp、yiyi-male-activity-v2.webp：1536×1024，6 列×4 行，每帧 256×256。
- 前两行为思考的 12 帧，后两行为天气的 12 帧；每秒 12 帧，1 秒循环。
- 对话头像增至 56px，固定使用 v1 首帧底图，闭眼图仅裁取眼睛区域，并用 opacity 平滑开合。头发、嘴巴、肩部不换帧。
- 天气动画底部手和肩膀使用固定层，避免生成帧的道具变化。等待区域裁除左侧 5% 的邻格道具碎片。
- 保留系统减少动态效果与预览暂停功能；预览 /static/companion-preview.html。

验证：浏览器逐像素对比男女头像的睁眼与闭眼截图，眼睛区域以外像素零变化；眼睛区域存在变化。等待和天气各验证 12 个不同帧位置，男女两套均通过；减少动态效果关闭所有动画，页面无脚本错误。

## 女版生成提示词

```text
Edit/reference: original female Yiyi chestnut bob, sage clip, cream blouse green vest in provided atlas. Produce a NEW animation sheet with exactly SIX columns and FOUR rows, 24 equal square cells, 3:2 landscape. No text, no borders. Uniform cream background #fff7f3. Crisp adult chibi big-head shoulder portraits. Top TWO rows = a SINGLE 12-frame seamless THINKING loop, read left to right then next row: same anchored head and hand at chin, pupils slowly look up, eyelids close then reopen, a small bulb gradually brightens. Bottom TWO rows = a SINGLE 12-frame seamless WEATHER loop: same anchored smiling head with little sun and cloud beside it and closed umbrella at shoulder, cloud gently drifts and sun subtly shines, a slow blink. Use small incremental changes each consecutive frame, NOT 12 different poses. Lock hair outline, face position, face scale, shoulders, mouth and camera across ALL frames in each loop. Head must not bob or drift. Face occupies 70 percent of each cell; props and hair have 8% safe margins. Every cell uniformly aligned on exact mathematical grid, no artwork spills to neighboring cells. The final frame returns toward first. Keep character identity from reference. No labels, no caption, no watermark. This atlas will play at 12 frames per second.
```

## 男版生成提示词

```text
Use provided original MALE Yiyi atlas as character identity/style reference: short dark chestnut hair, brown eyes, navy cardigan cream shirt, no clips or earrings. Produce NEW animation atlas EXACT SIX columns FOUR rows = 24 equal square cells, 3:2 landscape. Flat pale blue #f0f4f6. No grid lines or gaps. Crisp adult chibi big head shoulder portraits. First TWO rows = ONE 12-frame seamless THINKING cycle, row-major: anchored head with hand at chin, pupils slowly move up then forward, eyelids close then reopen, bulb beside head gradually glows. Last TWO rows = ONE 12-frame WEATHER cycle: anchored joyful face, small sun/cloud to side and umbrella, cloud slowly drifts and rays shine, slow blink. Incremental tween changes, NOT different poses. Keep camera, head center, hair silhouette, face size, shoulders and mouth IDENTICAL across all frames within each loop. No bobbing or camera drift. Head occupies70% each cell; keep8% safe margin, no props cross cell boundaries. Last frame leads back to first. Exact regular aligned mathematical grid. No text captions borders watermark. Usable at12fps.
```
