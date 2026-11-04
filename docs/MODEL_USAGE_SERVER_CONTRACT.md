# Stylist → Server 模型用量通知（最小契约草案）

2026-11-04。Agent端已本地接入采集、持久化及后台投递；Server接口仍待同事提供、真实联调待验。Server同事提供接收接口并自行定价；Agent不上报金额或积分，不接实际扣费。

## 范围

仅报告Stylist直接发起的对话／多模态理解模型调用，包括理解、生成与实际发生的重试。每次真实HTTP调用一条，投递重试沿用event_id；不再单独上报执行汇总，避免复杂度和重复计费。

```json
{
  "event_id": "call_example_001",
  "occurred_at": "2026-11-04T08:00:00Z",
  "environment": "test",
  "user_id": "12345",
  "conversation_id": "conversation_example",
  "request_id": "request_example",
  "business_action": "outfit_recommend",
  "provider": "volcengine_ark",
  "model": "configured-endpoint-example",
  "actual_model": null,
  "input_tokens": 1200,
  "output_tokens": 350,
  "cached_input_tokens": null,
  "reasoning_tokens": null,
  "status": "succeeded"
}
```

样例标识及用量为虚构数据。

| 字段 | 必要用途 |
| --- | --- |
| event_id | 唯一调用／去重ID，投递重试不变；模型重新调用则新ID |
| occurred_at、environment | 调用时间用于价格版本和对账；环境区分测试与生产 |
| user_id | Server验证身份的用户id字符串，等于本项目owner_id |
| conversation_id、request_id | 查整段对话和本次用户操作；不需要额外run_id、call_id |
| business_action | 受控业务类型，如chat、style_consult、outfit_recommend、outfit_modify、outfit_regenerate、weekly_plan、weather_consult、unknown；不传用户原话 |
| provider、model | 供应商和实际请求的模型／接入点，供Server匹配价格；不能仅传展示名 |
| actual_model | 响应明确返回的真实模型；无法取得为null，不能把接入点猜成底层模型 |
| input_tokens、output_tokens | 供应商真实输入／输出数量；未知为null，不估算、不填0；total可由Server在二者已知时相加 |
| cached_input_tokens、reasoning_tokens | 供应商提供时记录，未知为null；是输入／输出明细，不额外相加。Server依据价格规则判断是否足够结算 |
| status | succeeded、invalid_output、http_error、timeout、network_error、cancelled或unknown；失败也可能有真实用量 |

不发正文、图片、密钥、手机号、单价、金额、积分、耗时及其他诊断信息。内部健康检查不作为用户计费事件。业务理解尚未确认时用unknown，不让模型任意指定计费分类；Server若按业务类型定价，unknown需挂起对账。

## 接口及可靠性

- Server提供固定POST URL和服务间鉴权，JSON接收；不保存用户Bearer用于后台回调。
- 建议持久化成功返回 `{"accepted":true,"event_id":"call_example_001"}`。重复event_id内容相同返回相同确认，不重复入账；同ID不同内容拒绝。部署环境／生产者身份参与幂等命名空间。
- Agent先持久化调用记录和待发送事件，再可靠投递；超时、429、5xx重试，回调重试不重跑模型。身份或契约错误暂停并告警。重启后续传。
- 保存模型usage后再校验回复JSON；校验失败仍记录，后续修复调用另外一条。缓存响应回放不新增模型用量。
- 未知用量不能作为免费或零消耗，交Server决定挂起／对账。供应商响应id保存为本地provider_request_id；投递次数及受控错误码仅本地记录，必要时按event_id查。

## PostgreSQL定位

现有表可通过身份和对话ID定位；SQL用参数绑定，并由有权限人员执行。

```sql
SELECT version, user_message, reply_json, created_at
FROM stylist_messages
WHERE owner_id = :user_id AND conversation_id = :conversation_id
ORDER BY version;

SELECT conversation_id, status, response_json
FROM stylist_requests
WHERE owner_id = :user_id AND request_id = :request_id;
```

已新增stylist_model_usage，以event_id关联上述ID及已保存的message_version，精确查某轮；消息和关联轮次在同一事务保存。失败请求可能没有消息记录，不保证完整失败正文可查。

## 生图费用边界（本地代码核对）

| 功能 | 实际链路 | 本次用量回调 |
| --- | --- | --- |
| 穿搭试穿 | Stylist images.py → MCP digital_twin_tryon → Server algorithm.go → algorithm VirtualTryon及试穿执行／积分服务 | 不重复上报生图费用 |
| AI数字人生成 | Stylist media.py → MCP digital_twin_generate → Server digital_twin_upload.go → digital_twin/tasks.go | 不重复上报生图费用 |
| 对话附图理解 | Stylist llm.py直接调用支持图片的聊天模型 | 记录供应商实际返回的token |
| 衣物组合图／浏览器抠图 | 本地浏览器合成／分割及图片上传 | 不伪造生图模型token |

依据：Server数字人tasks.go创建任务并调用DeductDigitalTwinTx；algorithm试穿fitting_execution/garment.go调用DeductPointsInTx并具备失败退款逻辑。数字人任务包含Model、CostPoints、ChargeStatus；试穿有任务与积分流水。MCP只是调用通道，不代表所有MCP工具都自动计费。

现有积分流水不等于已记录生图供应商的实际token或图片成本。若Server需要核算供应商生图成本，应由实际生图服务采集；Stylist不掌握该原始响应，不能推算或重复报账。触发生图前若Stylist确实调用了对话模型，那次对话token仍单独记录；图片费用继续走原有确认和扣费流程。

上述为本地源码证据，未执行真实生图、扣费、退款或远端部署验收。Server只需确认接收URL、服务间鉴权、回执及模型标识与价格映射，价格由他们决定。

## 后端接收后如何处理

1. 验证服务Bearer凭证。此接口仅供服务端调用，user_id是Agent验证身份后提供的Server用户ID，不使用浏览器自报参数。
2. 校验JSON类型：event_id为UUID字符串；occurred_at为UTC ISO8601时间；environment为development/test/production；用户、会话、请求、业务及模型为字符串；actual_model可为null。四种token字段为非负整数或null，布尔值不能当整数。
3. 按服务身份、environment、event_id唯一落库。同ID相同内容返回成功，不能再收费；同ID不同内容返回409。推荐将请求正文原样留存供对账，但没有必要另取聊天正文。
4. 根据provider、model及可用的actual_model匹配自有价格规则；input_tokens和output_tokens分别计价。cached_input_tokens包含在输入中，reasoning_tokens包含在输出中，不能再加一次。缓存明细未知时不要按0断言；实际规则由Server决定。
5. test/development不计生产费用；失败但有真实token的调用仍可能有供应商成本。未知token或模型未映射的记录挂起核对，不当零成本。用户如何收费由Server决定。
6. 只有持久化接收成功才返回HTTP200：`{"accepted":true,"event_id":"原event_id"}`。金额可后算，ACK仅表示已可靠收到。鉴权失败返回401/403，契约错误400/422，临时限流429、临时故障5xx。Agent不接受仅返回通用code但无accepted/event_id的回执。

所有示例字段均会出现；不适用或未知的模型／token明细用null。业务枚举补充wardrobe_upload_intent、avatar_intent，仅表示对话意图理解的模型消耗，不是上传或生图费用。plan结构失败尚不能判断业务时为unknown；不会为补分类重复调用模型。

## Agent配置（同事提供接口后）

在服务器现有私密config/deploy.env增加，随后重建应用容器使环境生效：

```dotenv
STYLIST_USAGE_CALLBACK_URL=https://SERVER_HOST/AGREED_PATH
STYLIST_USAGE_CALLBACK_KEY=REPLACE_WITH_SERVICE_KEY
STYLIST_USAGE_ENVIRONMENT=production
STYLIST_USAGE_PROVIDER=volcengine_ark
```

URL默认空：只本地记录，不发送，不影响正常对话。KEY是新服务间密钥，不能用用户token或模型API key。生产使用HTTPS；仅localhost/127.0.0.1/::1允许HTTP测试。拒绝URL中的账号密码、query和fragment，也不跟随重定向。environment默认test，生产需要显式设置。

上报在后台进行，正常对话不等待ACK。超时10秒；408/429/5xx及网络错误指数退避（最长约一小时）后重试；401/403、其他非成功响应或错误ACK将该条标为blocked并记录受控日志，其他事件继续处理。修正接口或凭证后可按event_id将blocked改回queued，沿用原payload和ID。

## 本地表与查账

应用启动通过幂等CREATE TABLE自动创建独立的stylist_model_usage；不修改Server旧MySQL。SQLite／PostgreSQL／项目独立MySQL均有对应DDL；远端建表需部署并具有建表权限，不是此文档生成时已执行。

| 列 | 含义 |
| --- | --- |
| event_id、owner_id、conversation_id、request_id | 去重及归属／对话定位 |
| message_version | 对话成功保存后的精确轮次；未保存为null |
| payload_json | 实际上报的不可变最小JSON，不含正文和密钥 |
| provider_request_id | 供应商返回的响应id，本地对账用，可空 |
| state | pending尚无完整调用结果；queued待发；sending发送中；delivered已确认；blocked需人工检查 |
| created_at、next_attempt、lease_until | Unix秒：创建、下次投递及发送租约到期 |
| lease、attempts、last_error | 发送租约标识、投递次数、受控错误码 |

```sql
-- 通过Server event_id查精确对话；指定user_id约束归属
SELECT u.event_id, u.owner_id, u.conversation_id, u.request_id,
       u.state, u.payload_json, m.version, m.user_message, m.reply_json
FROM stylist_model_usage u
LEFT JOIN stylist_messages m
  ON m.owner_id = u.owner_id AND m.conversation_id = u.conversation_id
 AND m.version = u.message_version
WHERE u.event_id = :event_id AND u.owner_id = :user_id;

-- 运维查未处理记录，不输出会话正文
SELECT state, COUNT(*) FROM stylist_model_usage GROUP BY state;
```

回调失败不会重跑模型；重放已完成的同一request_id不新增记录。多实例发送通过数据库租约领取，超时可重领，ACK丢失靠Server幂等处理。进程在模型返回前后崩溃可能留下pending，没有可靠用量时不自动补零、不自动收费，需要对账；该状态不由发送器猜测结果。若本地台账写入失败，新调用在发给供应商之前停止；响应后落库失败保留pending并报错，避免静默漏账。该数据库故障边界区别于回调接口失败。

## 本机Node模拟接口

```bash
MOCK_USAGE_PORT=8491 node scripts/mock_model_usage_server.cjs
```

只监听127.0.0.1，无外部模型调用；数据只在进程内存。`POST http://127.0.0.1:8491/usage`接收上述JSON，测试Authorization固定为`Bearer local-usage-test`；`GET /events`查看收到的事件及尝试。`/usage-fail`返回503，`/usage-unauthorized`返回401，`/usage-limited`返回429，`/usage-timeout`模拟超时，`/usage-bad-ack`模拟错误回执。`/v1/chat/completions`仅测试用模型桩，不用于正式配置。该脚本及测试不进入发布镜像。

执行`pytest -q tests/test_model_usage.py tests/test_model_usage_node.py`验证本地采集与Node真实HTTP接收。模型、身份和token均为合成数据，不能冒充真实Server接收／真实供应商用量或收费验收。

## 本轮验证（2026-11-04）

- Python全量921通过、85跳过（外部数据库等显式测试未默认开启）；追加用量边界及Node检查后定向42通过。
- 隔离PostgreSQL17.6：实际建表、并发账号、持久化重试、发送租约及对话轮次／回放5项通过。检查点初次缺表由测试环境初始化补齐后复测通过；未连接远端数据库。
- 另跑Node真实本机HTTP端到端10例全部通过：正常、无地址、503、错误ACK、401、429、超时、usage缺失、真实0token、JSON修复重试。所有Agent请求正常返回，预期记录数量／状态／账号与会话关联正确；未知和0可区分，模型重试多记调用，回放不增记。
- Node模拟服务、供应商回复、用户身份均为合成测试；未使用真实模型或Server计费接口。配置真实URL和服务密钥后仍需测试环境联调。
