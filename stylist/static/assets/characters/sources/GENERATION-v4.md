# 原构图眨眼 v4

使用内置 imagegen，分别以男女 `standing-v3.jpg` 为编辑目标，各生成一张半闭眼/闭眼双栏图：`yiyi-female-blink-source-v4.png`、`yiyi-male-blink-source-v4.png`。最终运行素材为上一级目录的男女 `breeze-atlas-v4.png`。保留 v3 的原立绘及铺满画布的背景。

## 两次调用使用的提示词

Use case: identity-preserve. Edit target: attached fictional assistant standing portrait. Make a TWO-PANEL horizontal animation keyframe sheet, total 1536x1024, exactly two equal 768x1024 portrait panels side by side, no divider, no margins, no text. Both panels must be an EXACT duplicate of the attached portrait's FULL composition, head size, character centering, head tilt, perspective, clothes, body and background. DO NOT zoom into the face, do not re-pose, do not tilt or translate any part. ONLY EDIT THE EYELIDS. Left panel: eyes naturally halfway closed, the upper eyelids lowering toward the original lower eyelid, pupils partly hidden. Right panel: eyes fully closed in a natural blink. Critical anatomy: EACH original inner and outer eye corner stays at exactly the same location; eyelid lines follow the original eye sockets and the head's existing perspective. Do not independently rotate either eye, do not move eyes up/down/sideways, do not make one eye steeper or droop more. Closed eyelid should sit within the exact original eye shape, with graceful subtly curved lash line; do NOT draw a slanted diagonal line across the cheek, no double lines, no extra pupils, no floating eyelids. Preserve original eyebrows, nose, mouth, face contour and all hair. This is a precise minimal eye edit, NOT a new illustration. Keep original painterly anime style, matching skin tone and fine eyelashes.

## 合成约束

源图每栏保持原立绘的3:4构图，直接等比缩到384×512。不从放大脸部重新映射眼睛，不旋转眼部图像。只允许依据眼部以外的面部区域做最多2像素平移校正；本次两个人物两个状态的实际校正量均为0。局部眼睑蒙版以外仍保留同一基础立绘，不播放模型重画的整个人物。
