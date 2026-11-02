# 男女通用加载图标

2026-11-02，PRD-05。用户要求将 `companion-wait` 中的加载图标做成男女各一版的通用组件，动画可持续循环。

最初实现使用 `companion-loading.js`／`.css`，复用已有的 `companion-scenes-v1/female_warm_v1-hero.png` 和 `companion-scenes-v1/male_calm_v1-hero.png` 正常成人比例男女眨眼图集。没有新增或修改位图。两版仅保留连续转动的细环和循环眨眼，移除头像下方的三个小圆点，不让人物身体左右移动；不受六位角色静态头像的 `.mascot` 规则影响。

当前对话等待以本次请求的 assistant_persona 选择对应角色的眨眼图，六人各自一版，处理阶段变化只更新文案，保留原图标及动画。其他读操作默认跟随当前选中的助理角色，设置预览切换会自动生效。用户性别不参与选择。尊重 `prefers-reduced-motion`，开启后保留静态图标和状态文案。

组件不发起请求，不读写账号／资料／存储，没有循环JS计时器，也不显示虚构百分比。

```js
// 一个装饰性图标；无gender/persona时跟随当前页面选中角色。
const icon = CompanionLoading.icon({gender: 'male', size: 'small'});

// 带可访问状态文案的完整加载行。
const loading = CompanionLoading.create({
  persona: 'female_warm_v1',
  message: '正在整理这次的要求…',
  detail: '按你刚才提到的想法，慢慢选。',
});
target.append(loading);
CompanionLoading.update(loading, {message: '正在核对天气…'});
// 请求完成或失败时移除；组件本身不设置超时或发起重试。
loading.remove();
```

`size` 提供 small（48px）、medium（88px）、large（112px）；对话等待在手机上使用76px。完整行默认 `role=status` 和礼貌播报；装饰图标隐藏于辅助技术，减少重复朗读。已有外层状态语义时用 `announce:false`，单独图标需要描述时可传 `label`。文案使用textContent。

已接入对话等待、试穿形象读取、报价／形象确认、形象画廊、生成记录及手记读取。请求成功或失败后停止显示，旧请求的清理只移除自己的图标，不能清空新流程。对话等待15秒后的提示仅更新一次，动画继续循环，任务结束仍由原请求生命周期移除。

预览：`/static/companion-loading-preview.html`，展示全部六角色、三种尺寸和暂停操作，只读公开素材，不连接账号或业务服务。

本轮必要验证：

- `tests/companion_loading.test.cjs`、`tests/wardrobe_journey.test.cjs`、`tests/memory.test.cjs`、`tests/outfit_regeneration.test.cjs` 共68项通过，覆盖六人格共用男女版、阶段更新、长等待提示、结束／失败清理、迟到清理隔离与已有流程。
- Chromium使用真实前端文件与合成登录／流式请求，18组页面检查覆盖六人格各PC／390px，以及男女320px、横屏和减少动态；另检查2组男女预览页。阶段变化图标节点不替换，全部动画是infinite；把CSS动画时间快进至15分钟后细环仍可继续运动，此为时间快进检查，不是实际等待15分钟。
- 无横向溢出或脚本异常。男女手机与PC预览已目视核对。结束合成流后加载消失；形象／手记读取同样使用共用组件。原始证据在忽略目录 `var/companion-loading-preview/verification.json`、PNG和 `var/companion-loading-node.log`。
- 无需真实模型或付费图片测试，本轮没有调用这些服务，也未远端部署；真机另验。

后续简化（2026-11-02）：按用户反馈移除头像下方三点及对应动画，只保留眨眼与细环；所有复用位置统一更新。8项既有组件测试、1440／390px男女预览检查通过，各图标仅两项无限循环动画，减少动态仍静止。新证据为 `var/companion-loading-preview/verification-no-dots.json` 及同目录 `no-dots-*.png`，未重复全量回归或调用业务接口。


正常比例替换（2026-11-02）：按用户最新要求不再使用Q版加载头像，男女仍各共用一版。原始PNG保持不变，CSS等比放大单帧1.5倍、裁成头肩头像；3列2行图集只取第一行睁眼／半闭眼／闭眼，循环往返，保留持续转动细环及减少动态，不恢复下方三个点。8项既有组件测试和1440／390／320px男女预览检查通过，逐帧核对睁眼→半闭→闭眼→半闭→睁眼，桌面／390px已目视。证据为 `var/companion-loading-preview/verification-adult.json` 和 `adult-*.png`。本轮未新增或编辑位图，未调用生成、模型或账号业务接口。

所选角色修复（2026-11-02）：用户最新要求替代此前男女分组共用图。显式persona只使用角色注册表中有效ID，匹配六份既有v1眨眼图集；未指定角色和性别的读取图标由根节点当前persona匹配，预览和恢复同步生效。对话保留请求的人设快照，阶段变化不替换节点。上传／试穿独立结果卡底部28px与对话一致，避免后续用户气泡贴边。50项组件／上传试穿回归通过，Chrome使用真实静态资源及合成DOM核对六角色×1440／390／320px共18组，显式及继承角色图片均正确且可解码、间距均28px；减少动态静止。已目视六角色预览，未进行真实账号请求、模型或付费生成，真机另验。
