# 六位助理：守候场景与头像 v1

2026-11-02，使用 built-in image_gen，以当前透明v6三视图为身份／服饰参考，独立生成18份PNG。未覆盖旧素材，未处理用户照片。完整实际提示词见 [prompts.json](prompts.json)。

| 人格ID | 场景 |
| --- | --- |
| female_sweet_v1 | 花店窗边 |
| female_warm_v1 | 阳光阅读角 |
| female_regal_v1 | 城市露台 |
| male_artistic_v1 | 海边画室 |
| male_calm_v1 | 雨夜书房 |
| male_confident_v1 | 暮色天台，保留红瞳、坏笑、无胡须 |

每人三份：`{id}-hero.png`为1536×1024、3列2行精灵图，每帧512×512；`{id}-avatar.png`和`{id}-weather.png`为1254×1254静态头像（生成器实际返回尺寸）。

首页按第一行睁眼→半闭眼→闭眼→半闭眼→睁眼循环，每5.4秒眨眼一次；第二行保留生成原稿，不依赖其中可能不一致的回睁中间帧。生成帧存在细微纹理变化，不宣称像素级锁定。系统减少动态效果时固定第一帧。

对话、message通知与完整来信统一使用avatar，天气使用weather；加载头像独立按男女共用，正常比例版分别复用female_warm_v1和male_calm_v1的hero第一行眨眼帧，见 `docs/COMPANION_LOADING.md`；CSS变量按完整人格ID切换，头像不播放动画。选择卡仍用透明三视图。

预览：`/static/companion-scenes-preview.html`。主页已更新JS/CSS缓存版本。

验证：24项角色设置／偏好／手记前端测试通过；Chromium确认18份图片可解码、1440／390／320px无横向溢出、减少动态效果停用动画；六人格×通知／来信共12项计算样式映射均指向各自avatar且无动画。桌面及390px预览已目视；手机真机未验。未部署。

2026-11-02后续修订：用户反馈整帧播放抖动，首页已改用[眼部叠层v2](../companion-scenes-v2/README.md)，本目录首页精灵图保留历史，静态头像继续使用。等待加载图标后续已独立，详见AGENTS.md当前规则。
