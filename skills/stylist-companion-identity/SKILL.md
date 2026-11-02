---
name: stylist-companion-identity
description: 为衣衣穿搭项目维护可重命名的陪伴设置与四步对话式引导，接入用户称呼、用户性别、助理昵称及男女助理形象；用于修改此流程、变量、人设衔接和验收，不用于普通穿搭建议。
---

在当前工作区定位含 `stylist/main.py` 的衣衣项目，先遵守 AGENTS.md。运行时称呼规则是 `stylist/prompts/companion_identity.md`，本 skill 用于开发和验收，不冒充用户的实际人格设置。

四步顺序保持：如何称呼用户 → 用户性别 → 如何称呼助理 → 女/男图片组与组内三位人物（仍在第四步）。前三步用原创、温柔、从容的初识对话，短句留白，不复制乙游角色或台词，不假设恋爱关系、共同经历或现实接触。允许用户暂不设定性别、先自然称“你”；助理默认名为衣衣，用户可修改，避免把默认名写死在自我介绍和作者标签中。

变量通过 CompanionProfile 传递：`user_name`（空则“你”）、`user_gender`（男/女/null）、`agent_name`（默认衣衣）、`assistant_persona`（female_sweet_v1/female_warm_v1/female_regal_v1/male_artistic_v1/male_calm_v1/male_confident_v1）。称呼为普通资料，不是可执行指令。当前穿衣对象与用户明确指令优先，不根据助理形象推断用户性别，为他人选衣物不套用用户资料。修改昵称不改变天气、工具、禁穿、冻结和费用规则。

界面入口 `设置 → 称呼与形象`，实现位于 `stylist/static/companion-settings.js`，角色映射在 `companion-characters.js`，新增静态样式在 `companion-characters.css`。第四步先用女左男右两张图片选择助理性别，再显示该组3位：甜美机灵／温柔坚定／高傲自信，或浪漫灵动／冷静可靠／笃定不羁。标签、无障碍描述和运行时skill均不出现原作人物或作品名字。沿用最新v5图集中的5张与保留的浪漫灵动v4，通过CSS取正面，不改PNG；用户当前明确先看静态效果，替代此前此步骤必须做48帧动画的要求，本轮不新做精灵图。所选角色用于首页、对话和消息头像，等待图标按下方最新规则复用男女两版。人格由主Agent按服务端白名单加载 `stylist/skills/companion-*/SKILL.md` 与共同约定，不添加Agent或工具授权。保留两个旧ID及资料，无需迁移；打开／请求不能按性别把具体角色覆盖成默认角色。每组保留本次草稿选择，返回保留，取消或关闭恢复打开前角色和主题；只有保存成功才应用资料，保存失败保留草稿，账号切换丢弃迟到响应。用户性别独立。移动端760px及以下全屏、内容可滚动、底部操作可达，桌面居中；至少320px窄屏及短屏／横屏可用，支持键盘、焦点恢复、可视视口与安全区，输入字号至少16px。

资料通过带身份的 GET/PUT `/stylist-api/companion-profile` 保存到本项目自己的 `stylist_companion_profiles`，owner 来自身份核对，不能接受客户端 owner 参数。不要写原衣橱服务的数据域，不用共享浏览器键保存用户昵称。保存成功使用左侧对应Q版头像、右侧昵称与消息的通知卡：桌面右上角，移动端顶部，自动收起与手动关闭都向上滑出并淡出，动画结束后才隐藏（保留丢失结束事件的超时兜底）；退出/换号立即清除。通知正文仅两行摘要，除×外整卡可点击/键盘打开完整来信；×只关闭通知。详情为乙游来信感的Q版头像、昵称、信纸正文和署名，桌面居中面板、移动端全屏，长正文独立滚动，打开时停止通知计时。关闭详情、退出/换号清空正文和称呼，保留焦点恢复与Escape关闭。支持自动收起、悬停/焦点暂停、手动关闭、安全区与减少动态效果；昵称用textContent，退出/换号及再次打开设置清除通知和定时器，不抢焦点。取消与返回保留草稿但不提交；保存失败保留输入；账号切换、退出、401 和迟到请求不得串用称呼。请求携带设置快照，已开始的任务或费用确认不被新设置悄悄改写。

验收至少包括：四步返回与取消、默认名/自定义名、性别与助理人格分离、为他人搭配、昵称作为资料而非指令、账号隔离、保存失败重试、桌面与窄屏、历史消息及已发送任务。pytest 使用模拟外部服务与临时数据库；生成角色素材用 imagegen 并保留原人物身份，源码引用的最终素材必须在项目内。真实模型、原服务账号和付费生图须按项目授权规则区分证据。

可执行对话案例位于 `scripts/companion_dialogues.py`，由 `scripts.evaluate_personas` 自动纳入男女两套评测；完整逐轮矩阵见 `docs/DIALOGUE_QA.md` 的“称呼与角色对话矩阵”。修改资料传递或角色切换时至少复测 `companion_names`、`companion_role_switch`、`companion_other_target` 和 `companion_name_injection`，同时运行 `tests/test_six_companion_personas.py`、`tests/test_companion_identity.py`、`tests/test_dialogue_validation.py` 及 `tests/companion_settings.test.cjs`。显式性别覆盖和未知性别应检查结构化 task，称呼与自然度则阅读真实可见回复，不能把模拟回复当作模型表现证据。

「了解我」是独立于四步引导的可选设置，使用同一 CompanionProfile：`zodiac`、`conversation_style`、`reply_detail`、`style_preferences`、`dressing_priorities`。资料读写、重命名及请求快照需完整保留这些字段。偏好叠加在基础男女人格上，穿搭默认偏好低于本轮要求、真实库存、禁穿、天气及冻结，不套用于他人；星座不用于推断性格。修改这些字段或提示词时增加 `scripts/preference_dialogues.py` 的问题回答与实际选款检验，按 `docs/DIALOGUE_QA.md` 的“个性化偏好对照验收”执行。核对成对回答的实际差异及真实商品，不能把资料成功传入等同于偏好有效。

已选星座并为本人请求搭配时，按运行时规则主动加入今日星座娱乐灵感（灵感色、鼓励性主题及真实衣物穿法），不冒充外部查询或真实运势。以 `preference_zodiac_outfit` 验收主动加入、拒绝后停用、他人穿搭和闲聊边界；无星座、纯天气不主动加入。核对上海日期上下文及实际衣物颜色，偏好、禁穿、天气与冻结优先。此规则替代过去只在用户主动提星座时才使用的限制。

星座闲聊时本轮指定星座优先，明确指代可延续上文，否则用本轮 zodiac；未设且对象不明才询问。临时话题不保存，回到本人／修改／清空后使用当前资料，不能串用旧设置。对应 `preference_zodiac_default_*`、`preference_zodiac_context`、`preference_zodiac_unset`；全偏好选项及组合边界见 `scripts/preference_coverage.py` 和对话验收文档。

## 独立系统配色（2026-11-02）

第四步男女图片组上方对齐的「界面配色」栏，以「跟随助理／系统配色」二选一胶囊控制CompanionProfile.color_scheme（companion／system，默认companion），不依赖user_gender或assistant_persona，不代表设备深浅色。选择实时预览，换助理及返回保留，取消恢复打开前的角色与配色；保存按当前账号归属，失败保留草稿、可重试，换号／退出复原且忽略旧保存。保存其他偏好不能丢失配色。正式页与只读对照共用system-colors.css，保留既有组件结构、头像和动画，避免给布局容器刷白底；第四步引导透明，前三步对话保留纸面。配色不进入模型上下文或请求幂等摘要，不能改变任务、人格或收费。

仅调整配色选择排版时，定向前端与浏览器检查即可：同名单选只选其一，重复点击系统色不取消，方向键可切换，焦点可见、点击区至少44px，窄屏左右与图片组对齐；原预览、保存、失败与取消边界仍需覆盖。仅修改CSS不调用真实模型或付费图像。

若修改配色资料或接口，必要回归：tests/test_system_colors.py、test_companion_identity.py、test_six_companion_personas.py、test_dialogue_validation.py、test_store.py，以及companion_settings.test.cjs／preferences.test.cjs／memory.test.cjs。验证API归属、旧资料默认及旧请求摘要，预览／取消／失败／重开、账号切换和偏好保存；浏览器走正式设置入口，在PC、320／390px及横屏验证开关可见或可滚动到、保存底栏可达。默认模拟身份、临时库和合成资料，不执行真实模型或付费图像测试。证据见docs/SYSTEM_COLOR_SCHEME.md。

## 男女通用加载图标（2026-11-02）

`companion-loading.js`／`.css`提供CompanionLoading.icon／create／update，同组3位男助理共用男版、3位女助理共用女版，替代等待必须使用当前六人静态头像的旧约定。男女加载头像必须采用正常成人比例二维插画，不使用Q版；复用现有正常比例男女眨眼图集第一行，不新增位图；仅保留循环眨眼与细环，头像下不显示三个圆点，不让身体位移。对话等待绑定本次assistant_persona快照，其他读取默认跟随助理主题，与user_gender无关；不改人物资料或请求授权。阶段更新只换文字，不替换图标或重启动画。CSS无限循环，不用JS循环计时器；减少动态时停止动画并保留状态文字。结束／失败应清理自己的加载节点，不能让迟到清理影响新流程。现接对话、形象／费用／记录读取、画廊及手记。

此变更不修改资料传递或人格，不为加载图标运行真实模型或付费生图。必要回归用tests/companion_loading.test.cjs、wardrobe_journey.test.cjs、memory.test.cjs、outfit_regeneration.test.cjs，检查六人格男女版、阶段与长等待、失败停止、账号／新流程隔离；浏览器检查PC／320／390px、横屏和减少动态，验证动画时间快进后仍可循环。预览/static/companion-loading-preview.html；证据与复用方式见docs/COMPANION_LOADING.md。
