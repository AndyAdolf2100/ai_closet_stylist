# 模型用量上报与商业化接口方案

日期：2026-11-04。状态：用户已明确职责分工，Agent最小采集／投递已本地实现，Server契约待真实联调；未探测或宣称 Server 已有接口，不修改正式运行逻辑，不授权真实扣费。

## 用户确认的职责（2026-11-04）

同级aicloset-server由同事后续提供接收接口，并自行定价。Stylist通知谁、使用模型、真实token、业务动作及对话追溯ID；不由Agent算价格。本轮不改Server或实际扣费。Agent已新增usage.py和stylist_model_usage，接入llm每次HTTP尝试、已验证对话上下文及应用后台发送器；当前实现以最小Server契约为准。详细字段、JSON样例、幂等回执和PostgreSQL查询见[Server接入契约](MODEL_USAGE_SERVER_CONTRACT.md)。

## 当前代码

- `stylist/llm.py:LanguageModel.generate` 是正式文字模型 HTTP 入口，当前只提取 content 并做结构校验，没有持久化 model、usage 或供应商请求标识。内部可能因 JSON 校验失败再调用一次。
- `stylist/engine.py` 包含理解、生成、修复阶段及节点重试；`stylist/policy.py` 也会调用 plan。只统计最终 style 会漏计。
- `engine.chat` 从上游身份取得 owner，Store.reserve 按账号／request_id 处理重复请求，命中回放不再运行模型。RunManager 保持浏览器断开后的任务存活。商业事件应关联这些身份和请求，而不是使用前端自报的用户 ID。
- `LanguageModel.check` 同样调用模型，必须标记 internal_healthcheck，不能算作用户消费。

## 建议边界

Agent 记录真实模型资源使用；Server 验证事件、按自身价格版本计算成本，并决定会员额度、积分或其他计费规则。资源成本不等于用户收费，模型失败但产生用量的情况也需要保留。Agent 不直接写 Server 数据库，不由模型决定扣费或上报地址。

第一阶段只接用量统计。若之后需要余额不足禁止执行，应另设计执行前授权／预占、执行后结算和失败释放；不能依靠事后异步回调实现余额保护。现有试穿等独立收费流程不因新增 token 上报重复收费。

## 当前最小方案（2026-11-04用户收敛）

以[最小Server契约](MODEL_USAGE_SERVER_CONTRACT.md)为准：仅每次直接模型调用一条，event_id同时作为调用标识；不再要求独立run_id/call_id和终态汇总回调。传用户、对话／操作ID、业务、模型和真实token及必要状态。试穿和数字人生图由原服务计费，不重复通过本回调上报。下方双事件及扩展字段为早期备选设计，非本次接入要求。

## 历史备选：事件粒度与字段

建议固定内部 POST 接口（路径待 Server 约定），发送两类不可变事件：

1. `model_call.recorded`：每次真实 HTTP 调用一个事件。内部修复、节点重试均独立记录；投递重试必须沿用同一个 event_id。
2. （本次不采用）`agent_run.finished`：本次执行最终结果、实际业务类型、调用 ID 列表、已知用量汇总及完整性。汇总只用于聚合对账，不作为另一笔重复用量。

共同字段：schema_version、event_id、occurred_at、environment、owner_id、conversation_id、request_id、run_id。request_id 表示用户操作，run_id 表示一次实际执行，call_id 表示一次实际模型调用；恢复重跑如再次产生模型请求必须新建 call_id，不能误去重真实成本。

调用字段：

| 字段 | 含义 |
| --- | --- |
| business_action | 闲聊、文字咨询、衣橱搭配、周计划等受控分类；理解阶段未确认时允许 unknown，最终事件补充分类 |
| stage | understand、respond、repair、internal_healthcheck 等程序指定阶段，不由模型任意填写 |
| attempt / retry_reason | 重试序号及结构修复／节点重试等原因 |
| provider / configured_model / actual_model | 供应商、请求使用的模型或接入点、响应确认的真实模型；响应缺失时 actual_model 为 null |
| provider_request_id | 供应商响应提供的请求标识；无标识则为空，不伪造 |
| usage | input_tokens、output_tokens、total_tokens、cached_input_tokens、reasoning_tokens，未知为 null |
| usage_status | known、partial、unknown；缺失 usage 不得填写为零 |
| transport_status / output_status | 调用是否成功与结果是否通过校验分别记录 |
| duration_ms / error_code | 耗时及经过白名单处理的错误类型，不上报含密钥或正文的错误原文 |

缓存 token 是输入 token 的子集；推理 token 通常是输出明细，不叠加重复计费。供应商适配层应明确计数口径；多模态按供应商实际可用字段扩展，图片任务不得虚构 token。不传聊天正文、提示词、用户图片、手机号、Authorization 或模型密钥。

## 接入与可靠性

1. `engine.chat` 身份校验及任务领取后建立请求上下文，使用显式参数或请求级 ContextVar 传递；禁止把当前用户写进共享 LanguageModel 实例字段，避免并发串号。
2. `llm.generate` 在发请求前登记 call_id／pending；解析供应商 envelope 后先提取用量，即使后续内容结构校验失败，也保存该次用量。所有实际 HTTP 尝试覆盖网络错误、超时和取消路径。pending 不代表已发生用量。
3. 在本项目独立数据库增加调用记录与待发送事件表；收到响应后的调用状态和待发事件在同一个短事务落库。终态事件尽可能与请求完成状态同事务保存，覆盖成功、失败、取消与恢复；不跨外部 HTTP 持有数据库事务。
4. 后台发送器领取事件、调用固定 Server 接口，按退避与抖动重试；进程重启仍可继续。不能只用未持久化的后台 task。多实例使用租约，唯一约束阻止重复建事件。
5. Server 按生产者及 event_id 唯一去重，提交入账记录后才回 ACK；HTTP 成功仍需校验业务码和回执 ID。重复相同事件返回相同确认，ID 相同内容不同应拒绝并告警。
6. 网络超时／限流／5xx 重试；身份配置错误／契约错误进入人工排查，不能无限快速重试。回调超时不触发模型重新生成。后台使用独立服务凭证，不持久化用户 Bearer；环境隔离并校验账号归属，防止测试事件进入正式计费。
7. 外部模型响应成功后进程崩溃、响应丢失等窗口无法靠本地事务完全消除。保留 pending／unknown 与供应商请求 ID，通过供应商日志或账单补对；若供应商不提供查询能力，明确无法精确恢复，不把“无记录”当免费。

上报失败可先积压以保障对话体验；用量本地落库失败时继续还是暂停新请求，需按商业规则明确，不能默认为零成本成功。服务间鉴权、保留周期、积压告警及对账任务在接入时一并约定。

## 验收要求（待实现）

- 一轮 plan＋style 正好记录两次；内部 JSON 修复、policy 调用、节点重试及业务修复全部计入。
- 同一请求回放不新增模型用量；确实再次请求模型则新增 call_id。
- 内容校验失败仍记录已知 usage；超时未知与真实零用量可区分。
- 重复投递、ACK 丢失、进程重启和双实例抢占不重复入账；汇总不重复计费。
- 账号并发、切换与后台延迟上报不串用户；健康检查、演示及测试环境不算用户消费。
- 回调失败不重跑模型；既有试穿／上传收费不受影响。
- 本地 mock 回归与真实 Server 只读探测／测试环境回调证据分开记录；未经核实不宣称真实扣费验收。

需要与 Server 确认：接口路径与回执格式、服务间鉴权、业务枚举、模型价格版本归属、仅统计还是同时扣积分、失败／修复费用规则、是否需要预占额度。
