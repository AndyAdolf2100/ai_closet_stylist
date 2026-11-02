# 六种陪伴人格与静态形象选择

2026-11-02。本轮按用户要求，将最新候选图集接入第四步「陪伴的模样」与运行时人格。先图片选女／男，再展示该组3位；前三步、原有用户称呼／性别、助理昵称及可选偏好继续保留。新增人格是同一个主Agent的表达配置，不创建子Agent或增加工具权限。

## 人格与形象映射

| 标签 | assistant_persona | 运行时skill | 静态图片 |
| --- | --- | --- | --- |
| 甜美机灵 | female_sweet_v1 | [companion-sweet](../stylist/skills/companion-sweet/SKILL.md) | female-sweet-clever-turnaround-transparent-v6 |
| 温柔坚定 | female_warm_v1 | [companion-gentle](../stylist/skills/companion-gentle/SKILL.md) | female-gentle-resolute-turnaround-transparent-v6 |
| 高傲自信 | female_regal_v1 | [companion-regal](../stylist/skills/companion-regal/SKILL.md) | female-regal-confident-turnaround-transparent-v6 |
| 浪漫灵动 | male_artistic_v1 | [companion-artistic](../stylist/skills/companion-artistic/SKILL.md) | male-artistic-turnaround-transparent-v6 |
| 冷静可靠 | male_calm_v1 | [companion-composed](../stylist/skills/companion-composed/SKILL.md) | male-composed-turnaround-transparent-v6 |
| 笃定不羁 | male_confident_v1 | [companion-confident](../stylist/skills/companion-confident/SKILL.md) | male-confident-turnaround-transparent-v6 |

图片均在`stylist/static/assets/characters/candidates-v2/`，文件名加`yiyi-`前缀及`.png`。当前使用透明v6三视图，CSS截取正面，按已确认的158／163／175及180／184／188cm设计值等比展示。透明图保留脚下轻柔阴影，背景由CSS随暖色／雾蓝主题变化；旧PNG不覆盖。2026-11-02按最新要求新增六组首页眨眼精灵图及各六张对话／天气静态头像，使用独立守候场景素材；选择卡仍使用透明三视图。详见`../stylist/static/assets/characters/companion-scenes-v1/README.md`；旧动画资产保留历史。提示词及素材清单见候选目录`prompts-transparent-v6.json`，生成式背景提取允许细微纹理差异。

## 性格提炼与参考

参考资料只用来提炼相处方式，六份skill及前端标签、描述、无障碍文本不含原作人物或作品名字，也不搬入其身份、剧情、世界观和原台词。六位均为本项目的成年助理，昵称只来自用户设置。以下是设计提炼与推断，不是官方完整定义或授权人格：

- 甜美机灵：主动、机敏、细心观察，转化为小巧建议与有分寸的俏皮；舍去原设定中的操控或不适合日常服务的关系安排。参考[授权游戏人物介绍](https://www.cs.furyu.jp/toloveru-tp/character/momo.html)。
- 温柔坚定：温和但有主心骨，转化为可靠的回应和可执行安排。参考[动画官方人物介绍](https://www.swordart-online.net/character/index2.html)，本次搜索摘要可读，直接打开403。
- 高傲自信：审美鲜明、自信从容，对亲近者柔和；舍去贬低、特权感与控制。参考[作品官方人物介绍](https://one-piece.com/character/Boa_Hancock/index.html)，本次搜索摘要可读，直接打开403。
- 浪漫灵动、冷静可靠、笃定不羁：分别提炼艺术敏感与健谈、克制专业与规划、自信不羁与玩味；舍去虚构职业、危险行为与操控关系。参考[基于开发者采访的角色介绍](https://apps.apple.com/me/iphone/story/id1806358259)及[制作组人物介绍](https://deepspace.papegames.com/news/3)。

性格不改变用户本轮要求、天气与衣橱策略、禁穿、冻结、记忆授权或费用确认；不以自信保证未知属性，不将玩味变成辱骂、占有或无视拒绝。专业定位与自主选择约定集中在[共同约定](../stylist/skills/companion-contract.md)。

## 配置与兼容

`stylist/personas.py`只从服务端白名单读取对应`SKILL.md`和共同约定，plan与style均注入同一请求的人格。六份skill是随应用发布的运行时配置，不安装为会改变开发助理语气的全局Codex技能。旧的两个ID原样保留，原资料与历史请求无需迁移；新增4个ID复用原CompanionProfile及独立资料表，不新增SQL表或写旧业务库。

第四步切换男女或人物只改草稿、静态预览与男女主题；两组各保留本次选择。返回不丢草稿；取消／Escape恢复原角色与主题；保存失败保留选择；收到成功回执才应用资料。读取、保存、退出及账号切换继续使用归属与序号检查，旧账号迟到结果不可覆盖新账号。保存完整人格ID，不再根据性别重算为默认人格；偏好保存保留角色，发送请求取完整深拷贝快照，进行中的请求／费用确认不随之后切换改变。用户性别与助理性别保持独立。

前端入口：`companion-characters.js`为6人映射及静态预览，`companion-settings.js`为草稿及保存，`companion-characters.css`为静态卡片和头像。无障碍使用原生radio与分组，图片区可键盘选择，手机底部操作固定、内容可滚动；所有输入仍至少16px。原图失败保留角色文字和明确占位。

## 验证记录

- 6份skill通过skill-creator格式校验，内容、文件名和前端无原作名字；六人选择、API回读、昵称及偏好保留、账号隔离、快照与plan/style系统提示均有无费用回归。
- 独立Chromium的1440×1000、844×900、390×844、320×740、320×568、844×390共12组男女画面检查通过：每组3人、图片正常、无内容横向溢出、保存按钮可达、取消恢复与首页静态形象生效；桌面、390px及320px短屏已目视检查。数据与截图在`outputs/six-companion-personas/`，账号保存只用合成内存适配器，无真实账号写入。
- 新增`companion_six_personas`3轮对话矩阵；`evaluate_personas --personas`可显式选择六种，未填仍只执行两种兼容人格，避免自动扩大真实调用范围。题库为200组367步，包含API/UI步骤，清单不等于已跑真实对话。
- 初次接入回归：592项Python通过、85项默认跳过，77项Node通过，Ruff通过；后续68项Python定向复测通过。新增发送函数集成检查，确认完整角色ID、未保存预览及断线重放快照按预期保留；该接入阶段未调用真实文字模型或付费图像。
- 后续六人格真实文字验收已完成1704轮尝试，1702轮有最终回复，自动与补证模型评分同时通过1430轮，仍有称呼／手记、分享误搭配、需求校验和卡片改写问题。同题轻度亲近回应也出现逐字重复，辨识度需改进；未修改运行时消除失败。详见[2026-11-02实测报告](LIVE_DIALOGUE_AUDIT_2026-11-02.md)，当前617项Python／89项前端回归通过；真人满意度、手机真机和收费图像仍未验。

仅预览、不登录可打开`/static/companion-setup-preview.html`；添加`?step=appearance`可直接查看第四步，不写真实账号。正式入口为首页「设置 → 称呼与形象」。本地服务更新与最终回归情况在AGENTS.md记录，不代表远端部署。

## 2026-11-02 本轮表达补修

移除旧两性语气总则及共用情话／笑话反面例句；六份skill增加各自的轻度亲近重心，运行时按当前邀约从所选skill提取reply_focus，而非预写六句固定回复。事实、手记、称呼边界和业务权限不由角色改变。最后六角色心动／玩笑12轮全部自动及模型通过，心动无逐字相同，部分玩笑仍围绕用户分寸要求，辨识度继续观察；不是真人盲测。其余穿搭手记与问题回归详见 CLOTHING_MEMORY_FIXES_2026-11-02.md。
