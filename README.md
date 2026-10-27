# 衣间 · AI Closet Stylist

基于现有 AI Closet 表结构和 Go 服务接口的新穿搭 Agent。项目位置为 `backend/ai_closet_stylist`，与旧 Agent、`aicloset-server` 并列，可独立运行。

核心目标：听懂当前需求、尊重禁忌与舒适、给能照着穿的方案，支持连续修改。采用一个主 Agent 的两阶段模型调用：需求整理、造型交付；程序负责商品身份、硬性限制、局部冻结和费用确认。

产品目标、用户流程、免费与付费边界及迭代验收见 [产品需求文档 PRD](docs/PRD_AI_CLOSET_STYLIST.md)。文档明确区分当前实现、待验收能力与规划功能。

省市联动与本地城市列表、自然天气背景、衣衣灾害动作及置顶预警见[专项说明](docs/WEATHER_WARNINGS_AND_CITY_PICKER.md)。真实预警数据源尚未接通，不将普通天气提醒当作红黄色预警；[视觉样式演示](http://127.0.0.1:8466/static/weather-preview.html)中的预警均为演示。

## 启动

```sh
cd /Users/duxiao/workspace/backend/ai_closet_stylist
uv sync --extra dev --locked
sh run-local.sh
```

打开 <http://127.0.0.1:8466/mobile/>，使用现有账号的手机号与验证码登录。接口说明：<http://127.0.0.1:8466/docs>。

`run-local.sh` 默认只读引用相邻旧项目的 `config/config.yaml`，复用现有模型配置、MCP 地址和登录公钥；不导入旧项目代码，也不复制凭证。旧服务的 8465 端口保持独立。账号服务存在单点登录约束，在新页面登录可能使同账号的旧标签页失效。

独立部署时使用环境变量，避免依赖旧项目路径：

```sh
export STYLIST_SERVER_URL=https://your-aicloset-server.example
export STYLIST_MCP_URL=https://your-aicloset-server.example/mcp
export STYLIST_LLM_URL=https://your-compatible-model.example/v1
export STYLIST_LLM_MODEL=your-model-id
export STYLIST_LLM_KEY=your-secret
export STYLIST_LOGIN_PUBLIC_KEY=/absolute/path/to/public-key.pem
sh run-local.sh
```

以上密钥是占位符，不是可用配置。生产环境设置 `STYLIST_ENV=production` 关闭本地手机号登录代理，通过现有 App 提供的 Bearer 登录态访问。当前存储是独立 SQLite，生产多实例部署前需适配共享数据库与执行恢复机制，不能直接把这个本地启动方式当成生产验收完成。

## 已实现

- 纯穿搭咨询及追问：延续已有衣物、活动和穿法偏好。普通穿法原理不读商品或天气；明确今日／本周出行的文字方案也按需查询天气。
- 真实个人衣橱选款，允许用户明确选择系统补充；返回商品来源、理由、穿法与必要提醒。
- 复用已保存搭配的商品，仍按本轮限制检查并提供解释。
- 局部换装：冻结其他商品；无合格候选时保留原方案并给标明性质的文字建议。
- 忽略天气、使用用户提供天气、查询指定城市天气三个独立路径；不默认为北京。
- 一周／多天文字规划；没有逐日天气证据时明确说明。
- 用户主动授权的浏览器定位、手动选城市，以及按日期匹配的今天／本周逐日天气卡；日夜温差、雨雪雾风等提醒以实际可用字段为准。当前上游缺少早间逐小时、风力和能见度，不编造缺失数据。
- 原创Q版女性搭配师「衣衣」，奶油／鼠尾草绿与淡粉界面；六种表情动作配合真实执行阶段，减少等待时的不确定感，支持减少动态效果的系统设置。
- 持久化历史、账号隔离、请求幂等、版本冲突检查及流式响应。
- 可将当前账号的正常衣橱图片导出为本地图库、CSV／JSON清单和ZIP，不读取其他用户衣橱或改动原记录。
- 逐项真实接口检查：账号、衣橱、商品、城市、天气、搭配、模型及图像报价；区分缺失工具、鉴权失效、无测试数据和未执行写操作。
- 整套试穿的报价、确认与执行适配：绑定当前搭配、人物形象、工具契约和费用；用户确认后才保存搭配并调用既有试穿接口。网络状态未知时不自动再次生成。

生图工具已在真实服务中发现、只读报价已验证；本次未真实扣费生成，图像质量、耗时、上游扣费／退款效果仍需单独验收。当前新页面只提供整套试穿；个人形象准备沿用现有 App，数字分身生成、单品美化没有伪装为本页已实现的入口。

## 主动精简的部分

新项目没有复制旧版的多角色 Critics、复杂关键词路由、传统配色评分、隐式画像学习、通用工具选择器、自动衣橱写入及重复数据库层。保留一个需求记录、一条可追踪的执行路径和少量明确接口。

旧项目原有源码、用户数据和未提交改动均保留。本项目只新增自己的运行状态表，不迁移、清空或改动原 MySQL／PostgreSQL 业务表。

## 数据和接口

详见 [表结构与接口映射](docs/API_AND_SCHEMA.md)、[架构与边界](docs/ARCHITECTURE.md)、[接口验收记录](docs/INTEGRATION_CHECK_2026-10-27.md)、[定位天气与衣衣形象交付](docs/WEATHER_AND_YIYI_2026-10-27.md)。

当前远端没有发布 `kb_search`，虽然相邻 Go 仓库保留了对应注册代码。运行时改用已验证的分页商品接口，并明确候选范围；不是全库存语义搜索。知识库工具重新发布后，可通过同一检查入口确认，再启用其召回路径。

## 验证

```sh
uv run pytest -q
uv run ruff check stylist scripts tests
```

测试使用隔离数据库与模拟外部接口，不扣费、不修改真实衣橱。真实语义回归需显式执行：

```sh
export STYLIST_LEGACY_CONFIG=/absolute/path/to/ai_closet_agent/config/config.yaml
uv run python scripts/evaluate_semantics.py
```

`scripts/live_check.py` 支持通过标准输入接收登录凭证并进行真实只读接口检查、完整对话回放。凭证仅留在进程内存，不保存、不打印；不要把凭证写到脚本或提交到 Git。真实生成验收应由用户在页面确认本次费用后单独完成。

本轮机器可读检查产物保存在被忽略的 `var/` 下。测试人物条件为合成场景，不代表账号持有人的真实身体条件或长期偏好。
