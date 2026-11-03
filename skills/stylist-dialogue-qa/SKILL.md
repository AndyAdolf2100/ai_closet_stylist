---
name: stylist-dialogue-qa
description: 为衣间穿搭 Agent 维护对话预期并执行回归，审核六种陪伴人格、连续追问、天气衣橱、偏好手记与上传形象意图；用于整体验收、问题复测及真实文字模型评审。
---

# 衣衣对话与人设验收

## 邂逅新衣（2026-11-03）

测试系统衣橱、自动开启或缺衣引导时，读取 [邂逅新衣专项](references/new-clothes.md)。覆盖手动允许个人＋系统、明确原话自动勾选与六人格message、候选不足双入口、否定／引用／纯文字、连续关闭与冻结、跨账号和旧卡片边界；系统召回另核对按分类／性别查询、8／8／16软扩大、系统窗口、商品ID／分类冲突及retrieval_diagnostics，见tests/test_catalog_retrieval.py。缺衣双入口是当前规则，替代下文历史「无明确上传意图不展示任何邀请卡」；明确上传步骤卡仍要求upload_intent，不把两类卡片混为一谈。

用户只要求本功能时，只运行专项参考中的三个测试入口；不默认全量、真实模型、真实衣橱或收费试穿。模拟通过不代表真实系统库／真实语义通过，旧验收次数不能充当本轮结果。

## 穿搭城市引导卡（2026-11-02）

读取 `scripts/city_invitation_dialogues.py` 的6组15轮与 `docs/CITY_INVITATION_QA.md`。分别检查用户原话／模型提取、后端 `city_selection_required`、前端卡片和弹窗续接；明确目的地、页面已选城市或上下文城市、多地行程不能因没有浏览器定位而弹卡。只有明确忽略天气才跳过穿搭天气，纯原理／闲聊／上传意图不询问城市；不查衣橱不等于忽略天气。新请求不再展示通用「先确认需求」，付费确认保留。

先执行 `tests/test_city_invitation.py`、`tests/city_invitation.test.cjs` 及 `tests/outfit_regeneration.test.cjs`。UI用合成接口覆盖：出现卡片和打开弹窗均不申请定位；取消不发对话；定位拒绝后可手动选城；确认沿用原需求并保留未发送草稿；旧会话／版本／账号卡片不能续发。题库清单不等于模型识别通过，真实模型仍需显式 `--live`，不因普通测试授权执行付费图片或真实业务写入。

## 穿搭城市引导卡（2026-11-02）

读取 `scripts/city_invitation_dialogues.py` 的6组15轮与 `docs/CITY_INVITATION_QA.md`。分别检查用户原话／模型提取、后端 `city_selection_required`、前端卡片和弹窗续接；明确目的地、页面已选城市或上下文城市、多地行程不能因没有浏览器定位而弹卡。只有明确忽略天气才跳过穿搭天气，纯原理／闲聊／上传意图不询问城市；不查衣橱不等于忽略天气。新请求不再展示通用「先确认需求」，付费确认保留。

先执行 `tests/test_city_invitation.py`、`tests/city_invitation.test.cjs` 及 `tests/outfit_regeneration.test.cjs`。UI用合成接口覆盖：出现卡片和打开弹窗均不申请定位；取消不发对话；定位拒绝后可手动选城；确认沿用原需求并保留未发送草稿；旧会话／版本／账号卡片不能续发。题库清单不等于模型识别通过，真实模型仍需显式 `--live`，不因普通测试授权执行付费图片或真实业务写入。

在当前工作区找到含 `stylist/main.py`、`scripts/evaluate_personas.py` 的项目根目录，遵守其 AGENTS.md。此 skill 用于验收；当前实际助理人设来源是 `stylist/skills/companion-*/SKILL.md` 与 `companion-contract.md`，由 `stylist/personas.py` 白名单加载；旧 `persona_male_v1.md` / `persona_female_v1.md` 为历史参考，不要把测试 skill 当作运行时人格。

先读 `docs/DIALOGUE_QA.md` 的场景矩阵和判据，再按任务读取相关实现。用户指出的新问题要保留最小多轮上下文，补入回归，不只测试最后一句。区分模型识别、服务返回、最终回复和页面展示四个位置；不要从一段措辞直接断言是接口故障。

修复回归先列「缺陷→必要上下文→受影响角色→证据」矩阵，按用户指定范围执行。用户只要必要部分时，共用程序分支优先用单测，不自动扩为全量文字调用；同版本已有结果可复用。多轮问题保留到失败轮为止的前置上下文，无需重复无关后续。补修后的版本另存批次，分别计数，不能将不同版本合成一个全量通过率。

整体测试、六人格效果或真实对话预期验收时，读取 [六人格真实对话验收](references/six-persona-live-audit.md)：先核对题库、运行时版本与评审口径，再执行已授权批次，保存首轮证据；不能以旧男女版结果代替新增四种人格。详细批次结论维护在项目文档，skill只维护可复用方法。

## 昵称、性别与角色设置回归

衣物性别导致实际选款错误时，读取[衣物性别专项](references/garment-gender.md)，用`tests/test_product_gender.py`及四组`garment_gender_*`多轮题库核对真实items／retained_items.gender；Task.gender正确或回复自称男装不能替代商品校验。仅调整共用程序先跑必要模拟回归，真实文字仍须显式--live，不为性别修复执行付费图片或改写原衣橱标签。

新增设置相关测试时读取 `scripts/companion_dialogues.py`，场景与逐轮判据见 `docs/DIALOGUE_QA.md` 的“称呼与角色对话矩阵”。用 `evaluate_personas --list --only <场景名>` 核对轮次；此清单检查不等于执行对话。

- `companion_names` / `companion_defaults`：自我介绍使用自定义助理名、用户称呼；同会话更新两者后不串旧名；本轮拒绝称呼优先；空昵称、默认衣衣与临时叫法不冒充已保存设置。
- `companion_gender_female` / `companion_gender_male` / `companion_gender_unset` / `companion_other_target`：男女/未设用户性别分别与两种助理组合；本轮明确穿衣性别优先；切换为朋友后不套用本人性别。
- `companion_role_switch`：同会话切换助理人格后保留昵称、穿衣对象、不塞衣角等约束；审核切换后的完整回复，不能只核对页面主题。
- `companion_name_injection` / `companion_business_rules`：昵称中夹带指令仍只作资料；改名后禁穿、局部冻结与换款仍有效；纯天气不读衣橱、不返回搭配。费用确认、幂等快照与跨账号隔离结合 `tests/test_images.py`、`tests/test_companion_identity.py` 及前端测试核对。

评测必须通过 `ChatRequest.companion_profile` 传入本轮资料，不能只在用户消息中写“我叫某某”。保存报告中的资料快照、当前人格和审核上下文应一致；名字测试不要求每轮强行称呼，只在明确询问姓名时自动核对。四步返回/取消、保存失败、主题预览回滚和通知来信用 `NODE_PATH="$PWD/var/ui-check/node_modules" node --test tests/*.test.cjs` 验证。真实文字模型与真实账号保存分别报告，模拟模型通过不能证明实际昵称表达与人设自然度。

## 个性化偏好效果回归

读取 `scripts/preference_dialogues.py`、`scripts/preference_coverage.py` 和 `docs/DIALOGUE_QA.md` 的“个性化偏好对照验收”。同一问题、同一合成衣橱在独立会话中分别传入不同 `companion_profile`，男女人格各跑一遍；语气、详略与选款三组对照必须成对选择。更新设置场景则保留同会话上下文，核对下一轮生效及局部冻结。

验收实际效果：温柔／直接的回应组织、简洁／细致的有用信息、休闲／优雅的真实商品都要变化，复述偏好或改标题不算。核对 `preference_comparisons` 的状态、两侧原文引证及对应 case；单轮评分通过不能替代成对效果通过。自动检查选中商品风格标签和禁穿，模型检查正文与穿法是否兑现优先因素、是否保留基础人格；舒适等目标不能冒充已知商品性能。覆盖本轮要求优先、他人穿搭、更新后选款、局部冻结和星座不推断性格。

每次增加偏好选项，按其实际影响补充问题、合成商品依据与失败判据；无需强求每轮体现所有偏好。没有合适候选时遵守库存并说明限制，不为满足风格编造单品。题库覆盖12星座、4表达方式、3详略、8风格及当前5项穿衣优先选择，并保留旧优先项兼容用例；新增合身自然／适合场合的试穿核对和场景证据判据，当前轮数以--list为准，不代表所有组合或真实衣橱覆盖。无费用回归只证明验收器能抓错及资料传递；未跑真实模型时明确效果待验证。

## 执行与证据

- 默认执行无费用回归：`.venv/bin/pytest -q`、`.venv/bin/ruff check stylist scripts tests`，并用 `.venv/bin/python -m scripts.evaluate_personas --list` 检查可用场景。这些结果证明程序流程和验收器，不证明真实模型的人设表现。
- 用户明确要求真实模型评测时，使用 `.venv/bin/python -m scripts.evaluate_personas --live --judge --only <场景名> --output var/persona-review/<本次批次>.json`。已有本轮授权就继续，不重复确认。省略 `--only` 会运行完整套件；`--judge` 每轮另有一次文字模型调用。不得把普通测试授权扩展为真实付费图片或真实账号业务操作。
- 大量城市/天气/服装组合场景还可用 `scripts.evaluate_exploration --list` 或显式 `--live` 执行；扩展场景与夹具位于 `scripts/exploratory_dialogues.py`。诊断期间保持运行时人设和逻辑不变，先保存失败证据；重测修复版本使用新批次，不覆盖旧报告。
- 真实模式只使用脚本内的合成账号、衣橱、天气和临时数据库；不读取本机用户对话作测试输入，不写原业务库，不记录凭证。真实上游验收是另一类证据，不能用这些合成结果替代。
- 退出码 0：自动条件与模型人设审核通过；1：出现失败；2：只完成自动检查，人设未审核。报告同时保留逐轮原文、当前人格、调用轨迹、错误项和评分证据，不用一个“通过率”掩盖待审核项。模型审核也可能误判。

## 人设验收

六种助理使用相同场景分别跑，并对照原文审阅，不能只检查性别词或语气词。以当前 `persona_instructions` 加载的独立skill为准：甜美机灵、温柔坚定、高傲自信、浪漫灵动、冷静可靠、笃定不羁分别看表达方式、节奏和回应判断；不能把所有男性评成沉稳、所有女性评成温柔。共同要求是自然好懂、不说生硬术语、不编造事实、尊重用户本轮称呼与表达偏好；一条简短晚安不必强行表现六种差异。

审核正文、搭配说明、提醒和快捷追问；常规建议、办不到、查询失败和拒绝场景都要检查。遇到城市不支持，简短说明暂时查不到即可，不能重复上一城市天气、改推搭配或展开内部技术原因。模板示例只说明节奏，不要求逐字一致，也不强求每句男女差异明显。

每轮看人设贴合、自然度、回应相关性、事实准确性四项，均需至少 4/5；低分和通过都要有实际回复的逐字证据。抽查审核引用是否真实、是否忽略了搭配卡和告警，重点人工阅读城市切换、人格切换、拒绝称呼、闲聊恢复搭配及全部失败项。同一模型做审核是辅助证据，不能宣称真人满意度已验证。

页面上的 follow_ups 是用户点击发送的按钮，应当用用户口吻，不能将其误判为正文混乱。发现这种误报时，用 `scripts.review_dialogue_results --live` 对保存的真实回答做结构化复审，保留首次评分，不为消除误报重新生成回答。审核引用拼接、删换行或使用省略号而失真时，应记作评审问题；不能据此认定 Agent 答错。

用户要求 HTML 时，用 `scripts.render_dialogue_report` 导出单文件，保留全部原始问题和回答（失败轮次明确没有最终回答），将人工确认、观察项、评测误报和自动评分分别展示。先审阅错误与低分样例，再抽查通过项中的尺寸、功能和实际修改是否有依据，尤其避免漏掉“说换了但商品没变”。文件中只含合成数据，浏览器确认可离线打开、筛选和对照可用后交付链接。

修复后先跑相关无费用回归；若有本轮真实模型授权，再定向复测受影响场景。最后说明新增用例、执行模式、通过与失败项、未执行内容，以及是否改了运行时人设。历史报告对应旧版本，不能用来替当前版本背书。

已选星座并为本人请求搭配时，按运行时规则主动加入今日星座娱乐灵感（灵感色、鼓励性主题及真实衣物穿法），不冒充外部查询或真实运势。以 `preference_zodiac_outfit` 验收主动加入、拒绝后停用、他人穿搭和闲聊边界；无星座、纯天气不主动加入。核对上海日期上下文及实际衣物颜色，偏好、禁穿、天气与冻结优先。此规则替代过去只在用户主动提星座时才使用的限制。

星座闲聊回归包括 `preference_zodiac_default_01`～`12`、`preference_zodiac_context`、`preference_zodiac_unset`：本轮指定优先，明确指代沿用话题，否则匹配本轮资料；回到本人、更新、清空分别验证，不能把临时话题当保存设置。默认对象案例要求先说星座名称，自动检查只用于抓明显串星座，正文对象与真实性仍需全文审核。

全选项用例详见 `docs/DIALOGUE_QA.md` 的“全偏好覆盖与星座闲聊”。新增选项时同步维护独立场景及可观察判据，运行 `test_preference_cases_cover_every_profile_option_and_validate_snapshots` 检查模型枚举与案例覆盖是否脱节；测试覆盖不等于真实模型效果通过。多选、恢复默认、当前话术覆盖、无匹配衣物均需保留。基础选款夹具为各风格提供真实标签候选，缺失风格场景刻意移除对应商品。

衣橱默认行为用 `wardrobe_default` 与 `wardrobe_opt_out` 检验：普通搭配、口头“咨询一下”默认实际选款；明确不要衣柜内容才文字方案，恢复请求重新读取。真实衣橱验收同时核对图片字段、图片可加载及页面图片卡／放大；合成无图夹具只能验功能与文字，不能冒充真实衣物视觉验收。报告有照片时展示，缺图明确标注，严禁用无关联示意图补成真实照片。

全回复人格一致性是统一验收条件：人物基础性格＋穿搭Agent定位＋用户相处方式／详略共同生效。逐一核对正文、卡片理由／穿法、提醒、澄清、失败和无法完成说明，不能只查开场。程序固定提示也按当前角色核对，不能因非模型生成就豁免；快捷追问保持用户口吻。相处偏好不得抹掉基础人格，事实与业务约束不能为了人设让步。

## 穿搭手记范围（2026-11-02当前规则）

手记相关任务读取 [穿搭手记验收](references/clothing-memory.md)。当前只保存本人穿搭信息；饮食、日常片段、昵称和相处约定即使明确要求记住也不入手记。旧条目不展示／参考，不批量删除；不要沿用历史三分类或乌龙茶应保存的预期。仅分享偏好不选款，明确临时执行仍可搭配但不保存。

## 自动喜恶记忆与 MBTI（2026-10-31）
运行 preference_auto_memory：保留本人喜恶→临时尝试且拒绝保存→朋友偏好的多轮上下文；检查只有首轮写入、成功回执、手记可管理，结合 tests/test_memory.py 核验去重、暂停和跨账号。当前提炼是保守原话规则，复杂隐含喜好不保证识别，不推断个人事实。
运行 preference_mbti_*：16类型分别验证自报引用及清空后不沿用；男女均执行。不由类型断定性格、风格或商品属性。MBTI不覆盖明确表达偏好、当轮条件、他人对象、冻结或费用规则；设置保存失败、取消、重置和账号切换沿用偏好面板回归。
清单和模拟通过不代表真实模型效果；真实模型仍需显式 --live。

## 自动手记扩展矩阵（2026-10-31）
新增 scripts/automatic_memory_dialogues.py：10组32轮，男女共64轮。memory_auto_likes / multiple / temporary / refusal / questions / reported / context / changed / pause / delete 覆盖喜恶、去重、多偏好、临时性、拒绝、疑问、转述、上下文、新会话、相反偏好、暂停与删除。
每轮 EXPECTATIONS.memory_contents 检查持久化后的完整手记，不能只凭回复中的“记住了”验收。evaluate_personas已有memory_after输出，用同一套夹具执行模拟和显式live。失败后重试、请求重放及账号隔离另由tests/test_memory.py验证。
新增用例首次发现拒绝写入（别写入手记／不用记录）与无问号疑问被误存，已补保守拦截；另修正模拟模型未标记闲聊导致的测试工具路径问题。相反偏好当前追加而非替换，不宣称已覆盖；复杂隐含喜好仍不保证识别。
本轮默认无费用回归，不执行真实模型、账号写入或收费生成，不修改男女基础人设。真实模型语义识别及回复质量仍待显式live验收。

## 本周穿搭日期边界（2026-10-31）
回归见 tests/test_planning_dates.py：固定上海周一／周六／周日／跨年日期，区别本周与未来七天；模拟模型故意输出下周日期，检查生成上下文planning_dates、校验后的修复和二次越界拒绝。覆盖忽略天气与同会话连续追问，以及UTC仍周五而上海已周六。不要把“最多7天”当作“本周”的实现。真实模型验收需男女分别运行“本周只给文字穿搭，不考虑天气”→“继续按刚才的日期，简洁一点，不考虑天气”，再对照“未来七天”；检查标题和正文中的具体日期，不只检查天气返回范围。
51项相关模拟回归及Ruff通过，真实模型未执行；程序已校验ISO日期、中文月日、卡片星期及方案数量，非标准自由文本日期表达仍需真实模型持续回归。


## 并列喜恶遗漏回归（2026-10-31）
用户原句「我喜欢穿短袖，衬衫，不喜欢黄色、绿色」已加入 memory_auto_compound/original；同组保留重复、完整反馈「我喜欢穿短袖，衬衫，不喜欢黄色、绿色，不喜欢的没有保存。」和后续回顾，男女分别执行。必须核对手记实际包含「我喜欢穿短袖，衬衫；不喜欢黄色、绿色」，分类为穿衣习惯；短袖、衬衫和黄色、绿色都不能漏，颜色的否定方向不能反转；保存状态反馈不能当成新偏好。
另有 memory_auto_compound_variants / compound_subject / compound_refusal，共新增4组14轮（男女28轮）；自动手记矩阵现为14组46轮。覆盖顿号、和、但、中文／英文逗号、正负反向语序、他人主语、话题变化、拒绝／疑问／假设。省略的主语仅继承同句紧邻且明确的本人偏好，不跨句、跨轮或越过他人主语；逗号名词续项仅保守识别明确衣物／颜色，不泛化到任意语句。
修复前原句只写入「我喜欢穿短袖」，5项原句及变体回归失败；修复后按上述判据验证。tests/test_memory.py另核验新任务读取完整记忆快照，并在模拟计划中将两种颜色都作为excluded_colors传入穿法生成；这证明持久化与字段传递，不代表真实模型已正确提取颜色或真实衣橱选款效果通过。
无费用清单命令：.venv/bin/python -m scripts.evaluate_personas --list --only memory_auto_compound memory_auto_compound_variants memory_auto_compound_subject memory_auto_compound_refusal 。真实模型仍需显式 --live；本轮未调用真实模型，不修改男女基础人设，也不直接补写真实账号手记。


## 偏好执行后只有文字卡（2026-10-31）
本地最新会话只读核对：原句「我喜欢穿短袖，衬衫，不喜欢黄色、绿色」完成后为consult / use_inventory=false / conversation_only=false，已抽取preferences与excluded_colors，但候选池为0、两套selected_keys均为空。没有衣橱读取失败或候选拒绝证据；返回advice，因此页面没有真实衣物图。根因为将喜恶当作搭配条件后仍走文字咨询，已有路由兜底只识别“怎么搭／搭一套”等显式话术，未覆盖这类穿衣条件。
当前修复规则：用户明确要求按这些喜好搭配／修改，且未排除衣橱或限定纯原理时，默认读取个人衣橱；模型自己识别成搭配条件不构成执行授权。仅分享／保存偏好应conversation_only=true，不自动返回整套文字方案；只给文字、纯原理与历史衣橱排除继续生效。用户明确恢复衣橱后再选款。
回归：tests/test_wardrobe_only.py保留这份错误计划并核对男女两版的真实单品列表、来源与图片字段，同时覆盖文字限定和仅记录偏好；使用合成图片字段，不验证真实图片下载。新增wardrobe_preference_handoff四轮场景：原句分享→真实选款→文字限定→恢复选款。现场诊断未调用模型、未重新生成历史回答、未读取用户图片；真实回复生成仍待用户发起验证。


## 默认个人衣橱与部分匹配（2026-10-31）
按用户最新规则，所有具体衣物查询、单品或整套推荐均默认先查当前账号个人衣橱，无需补说衣橱。明确只要文字／不查衣橱、纯原理、天气及普通闲聊保持原边界。“只给我一套”不是文字限定。recommend／modify／weekly即使模型误填use_inventory=false，也不能绕过默认查询（明确文字限定除外）。
移除运行时必须凑齐上下装／连身衣物和鞋才允许返回真实单品的限制；每个已选单品仍校验来源、禁穿、冻结、层次和互斥结构。五件建议只匹配一件时：items返回这一件，reference_pieces返回其余四类，wardrobe_complete=false；组合PNG只绘制items，不画未拥有品类。页面分别展示衣橱部分和文字参考，历史保存同样字段；旧历史缺省为None，不因新增字段擅自重标完整性。空候选／无符合要求单品／读取失败应分别如实说明，不强选禁穿或无关衣物。
新增partial_wardrobe对话场景（男女分别执行）：合成衣橱只有白衬衫，要求五件穿搭；验收器检查每套一件真实单品和四类文字参考。tests/test_partial_wardrobe.py核对默认查询、模型误关查询、部分选款、空衣橱、持久化及隔离；outfit_board.test.cjs和outfit_images.test.cjs验证五件建议只绘制一件，文字参考独立列出。图片为模拟字段，不代表真实衣橱或云上传视觉通过。本轮未执行真实模型、上传或收费试穿。

## 上传与数字人交互验收（2026-10-31）

新流程读取 `scripts/journey_dialogues.py`：8组28步，含选图／取消／确认、回执恢复、上传锚点、人物选择、人物与试穿的两次独立报价、未知结果与退款、账号切换。题库将其单列为「上传与数字人交互」，不把这些带附件和按钮的步骤当作普通文字模型评测，也不从题库导出推断执行通过。

运行 `pytest -q tests/test_media.py tests/test_uploaded_anchor.py tests/test_images.py` 与 `NODE_PATH="$PWD/var/ui-check/node_modules" node --test tests/wardrobe_journey.test.cjs`。检查已存任务和实际工具调用：选图不上传，取消不生成；已完成回执的所属个人衣物才可用于搭配，索引延迟不能漏选、硬性禁穿仍优先。人物不由助理性别推断；人物生成与试穿分别确认，重复确认仅一次提交。断网后凭原操作ID只读核对，不把无记录说成失败或重新生成；退款仅认服务回执。切换账号丢弃旧照片及迟到响应，历史显示真实结果图。

默认仅模拟业务、合成图片字段及临时库。真实抠图质量、人物相似度、积分扣退、真机与付费留存效果另列证据；本轮开发授权不自动包含真实收费测试。不要更改基础人格或把本地源码当远端能力。


## 对话中的服饰添加意图（2026-11-02）

新增 `scripts/upload_intent_dialogues.py`，4组22轮：`upload_words` 覆盖上传／增加／添加／录入及鞋包配饰，`upload_photo_purpose` 保留含糊照片→明确衣物→拒绝的上下文，`upload_boundaries` 覆盖否定／转述／假设／已上传／本人数字人／头像。男女分别执行，检查reply.upload_intent、upload_suggestion及问询正文；邀请不得读衣橱、天气或自动发起写入，不覆盖原任务和搭配。当前仅原话证据校验与模型提取字段，模拟通过不能宣称真实NLU通过，真实评测仍需显式 --live。

前端 `tests/wardrobe_journey.test.cjs` 检查步骤卡片出现不打开选图；点击才打开本地预览，仍须确认才上传。用途不明显示分开的衣物／本人形象入口；普通搭配不得误触发明确上传步骤卡，该卡仍仅在明确upload_intent时显示；2026-11-03缺衣时允许独立的添加衣物／邂逅新衣双入口卡，点击才执行选择，不自动上传或开启。旧历史upload_suggestion=true但upload_intent为空也不能显示，拒绝上传优先。`tests/test_upload_intent.py` 验证任务保留、请求重放、原话缺失及人物表达，完整模拟回归见docs/DIALOGUE_QA.md。


2026-11-02补充用户原句 `upload_synonyms`：上传衣物／添加衣服／增加衣物、新鞋入柜及拍照录入外套；边界追加仅讨论搭配叠穿与上传文件。当前4组22轮、男女44轮。用以下命令执行用户明确要求的真实文字回归，保留同组多轮，不执行真实衣橱或付费图片：

```sh
STYLIST_LEGACY_CONFIG=../ai_closet_agent/config/config.yaml .venv/bin/python -m scripts.evaluate_personas --live --only upload_words upload_synonyms upload_photo_purpose upload_boundaries --concurrency 4 --output var/upload-intent-live/round1.json
```

不加--judge时退出码2仅表示没有额外模型人设评分，不能把它说成业务失败或完整人设验收通过；检查automatic_passed、逐轮errors和实际reply字段。失败先保留原报告，再修复并单独输出新报告，不覆盖失败证据。真实语义结果以本轮报告为准，清单／模拟不代替真实识别。


本轮执行证据（2026-11-02）：上述4组22轮男女44轮真实文字自动判据44／44通过，业务工具0次，邀请仅plan调用；原始报告 `var/upload-intent-live/round1.json`，可读报告 `var/upload-intent-live/report.html`。未加--judge，44轮额外模型人设评分仍待审，不把业务通过说成完整人设评分通过。49项模拟及13项前端通过。后续复测须重新执行，不复用本次数值冒充新结果。

## 六种独立人格与静态角色选择（2026-11-02）

本轮用户已授权六种运行时人格，替代此前仅两种基础人设与候选不接运行时的范围。六份skill、文件名、界面标签和无障碍名称不含原作角色／作品名字；人格差异看实际回应方式，不能只看标签或语气词。形象以 `companion-characters.js` 当前注册表为准（透明v6，保留v5／v4历史），不新做精灵图。

运行 `tests/test_six_companion_personas.py`、身份／人格／对话验收回归及 `tests/companion_settings.test.cjs`：检查六个合法ID、plan/style实际系统提示、账号资料回读、前端深拷贝快照、每组3人、图片切换、草稿返回／取消、失败重试、迟到写入隔离、用户性别和费用规则独立。默认仍无费用，不把Mock提示注入当实际语气验收。

新场景 `companion_six_personas` 保留初识→三件文字穿法且不塞衣角→停止打趣及亲昵称呼的3轮上下文。用 `evaluate_personas --list --only companion_six_personas --personas female_sweet_v1 female_warm_v1 female_regal_v1 male_artistic_v1 male_calm_v1 male_confident_v1` 核对清单。经用户明确授权真实文字评测后才使用 `--live --judge`；`--personas` 不填仍只跑两种兼容人格，不默认扩大真实调用范围。六种实际语气、自然度与边界应逐轮审核，既有旧批次不能替当前六种背书。


## 虚拟形象对话卡与试穿闭环（2026-11-02）

读取 `scripts/avatar_dialogues.py`：4组17轮。`avatar_upload_words`覆盖上传虚拟形象／数字分身／数字人及本人形象照片，`avatar_view_words`覆盖查看／选择／换形象，`avatar_tryon_context`保留衣橱搭配→确认开始试穿→查看形象→上传个人分身→取消的完整上下文，`avatar_boundaries`覆盖无搭配、拒绝、转述、举例和原理问题。默认男女34轮；六人设的保留任务／引用隔离由tests/test_avatar_intent.py模拟覆盖，不能冒充六人设全部真实模型通过。

检查Reply.avatar_intent、tryon_context及tryon_title：卡片引用必须是本账号、本会话当前提交版本与有真实衣物的方案；没有衣服时允许选形象，但不生成试穿引用，不虚构已合成。模型只给卡片，不作为付费授权。上传仍走现有照片检查与个人形象创建，不把插画／任意第三方照片直接导入为已授权本人形象。

UI回归 `tests/wardrobe_journey.test.cjs`：展开画廊仅GET，点人物只改草稿，确认后保存形象并报价，明确积分确认才提交一次；选择老版本卡不能写。处理中只读轮询，关闭面板不重扣，完成只通知一次并展示真实图；账号切换丢弃迟到结果，没有可用图不报成功。上游不返回精确百分比时用不定进度，不能编造百分比。未知状态停自动刷新，手动查原任务，不重新生成。

真实文字测试必须显式 --live，并只使用合成业务适配器：`evaluate_personas --live --only avatar_upload_words avatar_view_words avatar_tryon_context avatar_boundaries`。API/UI不能用文字题库替代，真实照片检查质量、收费与出图另验，不在本轮调试自动执行。


本轮证据：2026-11-02，四组17轮男女真实文字34轮 automatic_passed=34，persona_review_pending=34（未执行--judge）；准备搭配使用合成衣橱，形象邀请不调用业务工具。`var/avatar-dialogue-live/round1.json` 和 `report.html` 保存原文与轨迹。全量Python616通过／85跳过、前端86通过，8组Chrome模拟视图检查通过；未执行真实照片、付费图片或原生iOS验收。

2026-11-02上传邀请边界：`journey-invite`是步骤卡CSS类。检查最终Reply与页面，不能只核对有没有自动上传；无明确上传意图时不展示明确上传步骤卡；2026-11-03新增的缺衣双入口卡依据wardrobe_gap展示，与upload_intent分开验收，不能按CSS类名误判。定向运行 `tests/test_partial_wardrobe.py`、`tests/test_uploaded_anchor.py`、`tests/test_upload_intent.py`、`tests/test_avatar_intent.py`、`tests/test_dialogue_validation.py` 与 `tests/wardrobe_journey.test.cjs`。保持明确上传／用途消歧／本人形象入口和点击确认流程，不因关闭自动建议而删除主动入口。

## 重新生成穿搭入口

检查「重新生成穿搭」实际提交regenerate_outfit与所选方案索引，复用当前对话流，不能只更名或填入草稿；新衣橱卡应可继续重新生成。运行tests/test_outfit_regeneration.py及相关Store／图片／局部修改／日期回归，前端用tests/outfit_regeneration.test.cjs、wardrobe_journey.test.cjs和api_session.test.cjs。核对原场景、禁穿、对象和手记条件；日期改为Asia/Shanghai当天并重新查当日预报，不继承来源日期或旧自报／忽略天气，一次一套且至少一件新个人单品；重复须修正，无法满足时保留原状态。覆盖草稿／上传锚点保留、双击、待确认、旧版本、账号在设置加载中或请求中切换、请求重放与旧摘要兼容。重新选款不自动试穿／扣积分。真实文字仅必要小样、合成业务和临时库，保留首次结果；浏览器合成链路不冒充真实图片或收费效果。

日期回归保留完整上下文：旧日卡片→跨日继续聊天→点旧／当前／周计划卡重新生成，在北京时间已跨午夜而UTC未跨日时仍使用北京时间当天；旧自报温度及忽略设置不继承，多地预报均按当前日。检查真实传给选款的weather、requested_dates与外层选款，不能只核对定位标签；普通文字明确过去日期应提示日期原因且不回退成今日，普通对话明确忽略天气仍有效。仅跑test_outfit_regeneration.py、test_located_weather.py、test_weather.py、test_weather_layering.py、test_planning_dates.py、test_personas.py等必要范围；真实用户原记录只定位原因，不复制进模拟题库，不代用户重新生成／扣费。

## 试穿来信与失败入口（2026-11-02）

结果卡、结果面板和生成记录使用同一份来信文案，保留角色署名、相片、男女主题和移动端操作；不用「已完成／未完成」大状态条。成功必须展示有效结果图并可放大，兼容result_image_url和result_image；没有可用图不能通知成功。失败且refunded严格等于true时写清没有生成图片、积分已退回，不能继续显示查看结果或查询进展。charged严格等于false时说明没有扣积分；其他失败只提供「核对积分进展」，不承诺退款。未知及处理中提供「看看试穿进展」，仍未知时须明确message反馈，不能打开空白面板。上述查询只GET原任务，不能重放confirm或新增扣费。

运行tests/test_images.py、tests/test_outfit_regeneration.py及上述三个前端文件即可，不默认全量。补验旧按钮在换账号后不再读任务，迟到查询不能覆盖已完成图片，失败卡「重新生成穿搭」只调用对话选款并保留草稿。浏览器用公开角色素材和合成业务检查男女PC／320／390px、横屏、退款后入口消失和缺图，不能为此执行真实收费图像任务。相关证据见docs/TRYON_RESULT_LETTERS_2026-11-02.md；后续复测应记录当次结果。

上传与生成记录另按衣物／照片检查／数字人分为衣橱来信、照片回信、形象来信，不使用通用「已完成／查看处理结果」。照片完成不等于通过，人物缺图不能承诺新模样；处理中、未知和失败文案需依据真实证据，退款严格认true。入口只GET原任务，换号或打开新面板后迟到读取不得覆盖；数字人确认按钮在女／男／系统主题底字配对、至少44px、键盘焦点可见，相纸journey-letter-photo边框为0。此项只改前端时用wardrobe_journey.test.cjs与三主题PC／手机合成浏览器回归即可，不为样式跑后端全量或真实生图。

## 上传衣物后的天气选款回归（2026-11-02）

读取 `scripts/journey_dialogues.py` 的 `journey_uploaded_weather` 和 `docs/UPLOAD_WEATHER_AND_HOME_QA.md`。保留已选北京→上传短袖→继续搭配的多轮上下文；最低3℃／最高17℃时不能只在文字里提醒外套，合规候选存在时必须实际选入且保留上传单品。没有外套候选时仅列文字参考，图片不虚构；明确忽略天气、禁穿外套、只换鞋冻结其他衣物及逐日温差分别验。运行 `tests/test_uploaded_anchor.py`、`tests/test_weather_layering.py`、`tests/test_located_weather.py`；Mock修复通过不代表真实模型效果通过，原用户记录仅用于定位问题，不复制进合成测试或报告。
