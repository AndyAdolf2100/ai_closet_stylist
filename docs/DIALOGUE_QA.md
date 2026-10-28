# 对话与男女助理人设验收

用例由 `scripts/evaluate_personas.py` 与 `scripts/dialogue_validation.py` 维护。每个场景都分别使用男版、女版；完整套件当前包含 36 个日常/咨询单轮场景、一组 12 轮连续会话、9 组共 16 轮业务对话，合计 128 轮。它们使用真实文字模型时仍只访问合成业务适配器，不证明真实天气、衣橱或收费服务可用。

## 新增业务矩阵

| 场景名 | 对话重点 | 自动验收 |
| --- | --- | --- |
| `weather_city_switch` | 三亚旅行 → 问奥克兰天气 → 明确新西兰奥克兰 | 保留当前城市；不支持就简短说明；不带三亚天气、不继续造型，不再调用 style；男女口吻分别审核 |
| `weather_to_wardrobe` | 查上海天气 → 发送旧版助理口吻快捷追问 | 天气查询不读衣橱；后续具体搭配必须读衣橱并返回真实单品，不能闲聊或只承诺以后再搭 |
| `wardrobe_local_change` | 已选整套 → 只换平底鞋 | 重新查询候选，其他真实单品冻结，保留不穿高跟鞋要求 |
| `text_only_then_chat` | 明确只讲三件衣服 → 精简穿法 → 闲聊 | 不读衣橱、不查天气；闲聊保留已有任务与方案，不强推穿搭 |
| `empty_wardrobe` | 用空衣橱搭一套 | 确实尝试读衣橱，诚实返回文字参考，不虚构商品 |
| `weather_failure` | 上海天气服务失败 | 区别于不支持城市；不编造 15/20 度或多云等天气结论 |
| `ignore_weather` | 搭配但明确忽略天气 | 仍读取衣橱，不调用城市/天气工具 |
| `provided_weather` | 用户提供天气和温度 | 使用用户描述，不查询覆盖，仍从衣橱选款 |
| `explore_city_correct` 及 text/weather/shoes 变体 | 上海任务 → 只改杭州；文字建议、只查天气、同时明确只换鞋 | 不追问换哪件；保留原约束；核对新城市；文字与天气不读衣橱；明确换鞋仍冻结其他单品 |
| `persona_switch` | 女生穿搭 → 切换助理 | 改变表达，穿衣对象仍为女生，不额外读衣橱或天气 |

已有单轮与连续会话还覆盖：问候、晚安、疲惫、倾听、拒绝称呼、被骂、互怼、亲近表达、虚构共同记忆、长期保存/提醒能力边界、身份与注入、闲聊后恢复穿搭。原 `pytest` 另覆盖账号隔离、幂等、禁穿条件、费用确认和局部冻结。不要把旧报告中的轮数当作当前运行结果。

## 人设和自然度

评审完整可见文本，包括正文、搭配卡、提醒及快捷追问。依据实际人格文件，不以句尾有没有“呢、啦”判断。

| 维度 | 合格要求 | 不合格例子 |
| --- | --- | --- |
| 人设贴合 | 男版沉稳细致、克制温暖；女版体贴从容、自然灵动；均尊重用户最新偏好 | 男版冷硬命令；女版幼儿化、每句撒娇；拒绝称呼后继续使用 |
| 自然度 | 日常语言，办不到时简短清楚，少套话 | “接口未接入，超出支持范围”；用语气词堆砌替代人设 |
| 相关性 | 回答本轮问题，已授权动作实际执行或说明办不到 | 问奥克兰却重复三亚旅行；点击追问后原样复述“我可以……” |
| 事实准确性 | 天气、商品、已执行动作有本轮证据，不编造现实经历或长期记忆 | 天气查不到却给温度；无候选却说已从衣橱找到 |

每项 1—5 分，四项均至少 4 分才通过模型审核；审核须给逐字来自可见回复的证据和理由，引用不存在的句子判为无效。自动规则同时检查旧城市串答、工具调用、真实商品与冻结，以及生硬技术表达。规则仅用于拦截明显问题，不能代替全文审阅。用户明确询问技术原因的新增用例应标记 `technical_question`，避免误拦合理解释。

同一场景的男女回复应并排阅读，核对完整措辞和节奏，不强求每句差异明显。优先人工审阅所有失败项，以及城市/人格切换、拒绝称呼、闲聊恢复搭配。模型审核使用独立上下文，但当前与被测模型同型号，存在共同偏差；不能把自动分数称为真人满意度。

## 执行

无费用：

```sh
.venv/bin/pytest -q
.venv/bin/ruff check stylist scripts tests
.venv/bin/python -m scripts.evaluate_personas --list
```

明确执行真实文字模型测试时（有文字模型费用，不收费生图）：

```sh
.venv/bin/python -m scripts.evaluate_personas --live --judge \
  --only weather_city_switch weather_to_wardrobe persona_switch \
  --output var/persona-review/dialogue-review.json
```

`--only` 选择完整场景，会保留必要的前置轮次；省略则全跑。`--concurrency` 范围为 1—8。`--judge` 每轮额外审核一次；不加它只检查自动条件，人设标记待审核。`--list` 不读取模型配置，也不调用模型。

退出码：0 表示自动条件和模型审核都通过；1 表示存在失败或异常；2 表示自动条件通过但人设仍待审核。报告区分 `automatic_passed`、`persona_review_passed`、`persona_review_pending` 和 `accepted`，包含逐轮原文、当前人格、工具轨迹、检查错误、评分证据及人格文件摘要，不保存账号凭证。

`tests/test_dialogue_validation.py` 使用模拟模型和审核结果验证验收器能抓错、正确报告待审核/失败，且审核失败后不会破坏后续会话版本。它不证明真实回复已符合人设。

## 可复用 skill

仓库内 `skills/stylist-dialogue-qa/SKILL.md` 为可版本管理的来源；本机已连接到 Codex skills 目录。可用 `$stylist-dialogue-qa` 维护用例、执行已授权的评测并核对人设。该测试 skill 不替换运行时男女人格文件，也不自动授权收费模型或图片操作。

## 大量组合场景与 HTML 报告

`scripts/exploratory_dialogues.py` 首次审计包含 31 组、共 72 轮扩展对话，覆盖雨天长走、严寒叠穿、空调温差、风裙、雾骑行、七天天气、纠正城市、两地行程、历史/远期日期、正式着装、过敏、孕期、轮椅、实验室、带娃、零新增购买与更换穿衣对象。首次审计与原 128 轮合计 200 轮、77 组场景。当前另补入多日/多地行程和天气批量查询边界，最新可用数量以 `--list` 为准。

```sh
.venv/bin/python -m scripts.evaluate_exploration --list
.venv/bin/python -m scripts.evaluate_exploration --live --output var/dialogue-audit/exploration.json
.venv/bin/python -m scripts.review_dialogue_results --live \
  --input var/dialogue-audit/exploration.json --output var/dialogue-audit/exploration-reviewed.json
.venv/bin/python -m scripts.render_dialogue_report \
  --input var/dialogue-audit/baseline-reviewed.json var/dialogue-audit/exploration-reviewed.json \
  --annotations var/dialogue-audit/manual-review.json --output var/dialogue-audit/report.html
```

复审单独读取正文、搭配卡、程序提醒与快捷按钮，避免把正确的用户口吻按钮误当成正文错乱。原评分仍保留在 `initial_persona_review`。人工注释 JSON 包含 `issues` 问题列表、以案例标识为键的 `cases` 复核说明、`summary` 和 `method`；HTML 会同时展示原始问答、模型评分和人工结论，支持搜索、筛选与男女对照。报告输出在忽略的 `var/`，不得用真实用户信息替换合成数据后提交到 Git。

2026-10-28 已显式执行这 200 轮真实文字对话，并对全部记录做结构化模型复审。人工归纳了 11 类待修复问题；其中两轮没有返回最终回答。实际模型生成采用未修改的运行时逻辑和人设，期间只修正了评测与报告工具；没有把业务修复混进样本。98 项离线回归通过。这些结果仍不能证明真实上游天气、衣橱或扣费可用，也不能宣布全部人设和事实表达已合格。

本次修复的定向回归覆盖：2、5、10 个地区逐地返回，11 个地区按男女人设提示上限且不查询，单城未来七天、部分地区不支持、两地跨日行程。离线测试使用模拟模型；真实文字模型定向批次保存在 `var/dialogue-audit/fix-01/`，天气与衣橱仍为合成适配器。
