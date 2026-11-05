# Stylist → Server 模型用量通知（用户 token 版接入契约）

2026-11-04。Agent端已本地接入采集、持久化及后台投递；Server接口仍待同事提供、真实联调待验。Server同事提供接收接口并自行定价；Agent不上报金额或积分，不接实际扣费。

## 固定接口

```http
POST https://aicloset-dev.wxbjq.top/api/internal/stylist/model-usage
Authorization: Bearer <当前登录用户的token>
Content-Type: application/json
Idempotency-Key: <与JSON中event_id一致>
```

Server路由：`POST /api/internal/stylist/model-usage`。该地址是双方待接入的目标，不代表接口已上线。成功持久化或确认同内容重复事件后，返回HTTP200及 `{"accepted":true,"event_id":"原event_id"}`；不重复计费。Server复用现有登录鉴权，从token解析用户；JSON不传user_id。无需配置服务间密钥。

## 范围

仅报告Stylist直接发起的对话／多模态理解模型调用，包括理解、生成与实际发生的重试。每次真实HTTP调用一条，投递重试沿用event_id；不再单独上报执行汇总，避免复杂度和重复计费。

```json
{
  "event_id": "b78bcb9a-84ea-4d3e-bb0b-f18ae8d5b421",
  "occurred_at": "2026-11-04T08:00:00Z",
  "environment": "test",
  "conversation_id": "conversation_example",
  "request_id": "request_example",
  "business_action": "outfit_recommend",
  "model": "ep-20260910130610-tjnpm",
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
| conversation_id、request_id | 查整段对话和本次用户操作；不需要额外run_id、call_id |
| business_action | 受控业务类型，如chat、style_consult、outfit_recommend、outfit_modify、outfit_regenerate、weekly_plan、weather_consult、unknown；不传用户原话 |
| model | 实际请求中的模型名／接入点ID原样传递，不加供应商前缀。Server以此唯一标识匹配价格，例如ep-20260910130610-tjnpm；不再上报provider和actual_model |
| input_tokens、output_tokens | 供应商真实输入／输出数量；未知为null，不估算、不填0；total可由Server在二者已知时相加 |
| cached_input_tokens、reasoning_tokens | 供应商提供时记录，未知为null；是输入／输出明细，不额外相加。Server依据价格规则判断是否足够结算 |
| status | succeeded、invalid_output、http_error、timeout、network_error、cancelled或unknown；失败也可能有真实用量 |

JSON不发user_id、正文、图片、密钥、手机号、单价、金额、积分、耗时及其他诊断信息。内部健康检查不作为用户计费事件。业务理解尚未确认时用unknown，不让模型任意指定计费分类；Server若按业务类型定价，unknown需挂起对账。

## 接口及可靠性

- 接收地址固定为POST https://aicloset-dev.wxbjq.top/api/internal/stylist/model-usage，Server复用现有用户Bearer鉴权并接收JSON；Agent仅在内存保存通过身份校验的用户Bearer，不写数据库／日志／配置。
- 建议持久化成功返回 `{"accepted":true,"event_id":"b78bcb9a-84ea-4d3e-bb0b-f18ae8d5b421"}`。重复event_id内容相同返回相同确认，不重复入账；同ID不同内容拒绝。按固定来源stylist、environment、event_id全局去重，并校验已保存用户归属；其他用户重复同ID不得变成新账单。
- Agent先持久化调用记录和待发送事件，再可靠投递；超时、429、5xx重试，回调重试不重跑模型。401/403等待该用户重新通过身份校验；契约错误暂停并告警。重启后须同一用户再次发送对话，通过身份校验取得token后才能续传。
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

上述为本地源码证据，未执行真实生图、扣费、退款或远端部署验收。接收URL已确定，Server需确认用户token鉴权、回执及模型标识与价格映射，价格由他们决定。

## 后端接收后如何处理

1. 验证当前用户Bearer凭证，从Server既有登录鉴权结果取得用户ID，映射到本项目owner_id。JSON不接受user_id作为归属依据，token不存入用量表或访问日志。该路由仍须通过网关内网／来源访问控制仅允许Agent服务调用；用户token证明用户身份，不证明用量由Agent产生，不能允许客户端自报token数量触发计费。
2. 校验JSON类型：event_id为UUID字符串；occurred_at为UTC ISO8601时间；environment为development/test/production；会话、请求、业务及模型为字符串。四种token字段为非负整数或null，布尔值不能当整数。
3. 按固定来源stylist、environment、event_id唯一落库，同时保存鉴权所得用户ID。同ID须先校验用户归属，再比较业务内容；相同返回成功，不能再收费，不同返回409。历史事件比较时忽略旧user_id字段（归属单独校验），避免升级后因去掉该字段产生重复收费或冲突。推荐将请求正文原样留存供对账，但没有必要另取聊天正文。
4. 仅根据model匹配自有价格规则；input_tokens和output_tokens分别计价。cached_input_tokens包含在输入中，reasoning_tokens包含在输出中，不能再加一次。缓存明细未知时不要按0断言；实际规则由Server决定。
5. test/development不计生产费用；失败但有真实token的调用仍可能有供应商成本。未知token或模型未映射的记录挂起核对，不当零成本。用户如何收费由Server决定。
6. 只有持久化接收成功才返回HTTP200：`{"accepted":true,"event_id":"原event_id"}`。金额可后算，ACK仅表示已可靠收到。鉴权失败返回401/403，契约错误400/422，临时限流429、临时故障5xx。Agent不接受仅返回通用code但无accepted/event_id的回执。

新事件包含示例中的字段；未知token明细用null，model始终为实际请求配置的模型标识。业务枚举补充wardrobe_upload_intent、avatar_intent，仅表示对话意图理解的模型消耗，不是上传或生图费用。plan结构失败尚不能判断业务时为unknown；不会为补分类重复调用模型。

## Agent配置（同事提供接口后）

在服务器现有私密config/deploy.env增加，随后重建应用容器使环境生效：

```dotenv
STYLIST_USAGE_CALLBACK_URL=https://aicloset-dev.wxbjq.top/api/internal/stylist/model-usage
STYLIST_USAGE_ENVIRONMENT=production
```

URL默认空：只本地记录，不发送，不影响正常对话。不再读取STYLIST_USAGE_CALLBACK_KEY；遗留配置可删除。Authorization来自已通过Server身份校验的当前对话请求，不配置固定token，也不使用模型API key。生产使用HTTPS；仅localhost/127.0.0.1/::1允许HTTP测试。拒绝URL中的账号密码、query和fragment，也不跟随重定向。environment默认test，生产需要显式设置。

上报在后台进行，正常对话不等待ACK。超时10秒；408/429/5xx及网络错误指数退避（最长约一小时）后重试；401/403清除该用户本次失效token，将事件留在queued、last_error=awaiting_user_token；其他用户继续上报。其他非成功响应或错误ACK标为blocked，修正契约后可按event_id改回queued。

**重启补报**：数据库保留未投递事件，用户token仅在当前进程内存。用户下次发送对话（包括已完成request_id的回放），Agent先向Server验证token、取得owner_id，再让后台用该用户token补报其历史queued事件；不能用另一用户token代报。若用户不再发消息则继续等待，不保证无人操作时补报。401/403后同理等待新的有效请求；登录动作或打开页面本身目前不会刷新发送器凭证。多进程各自持有内存token，共享数据库租约防止同时领取；重试不生成新event_id，不重跑模型。

## 本地表与查账

应用启动通过幂等CREATE TABLE自动创建独立的stylist_model_usage；不修改Server旧MySQL。SQLite／PostgreSQL／项目独立MySQL均有对应DDL；远端建表需部署并具有建表权限，不是此文档生成时已执行。

| 列 | 含义 |
| --- | --- |
| event_id、owner_id、conversation_id、request_id | 去重及归属／对话定位 |
| message_version | 对话成功保存后的精确轮次；未保存为null |
| payload_json | 最小JSON，不含正文和密钥；旧记录可能含user_id，发送时复制并移除，数据库原文不重写 |
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

只监听127.0.0.1，无外部模型调用；数据只在进程内存。`POST http://127.0.0.1:8491/usage`接收上述JSON，测试Authorization固定为`Bearer local-user-test`，模拟映射用户42；`GET /events`查看收到的事件及尝试。`/usage-fail`返回503，`/usage-unauthorized`返回401，`/usage-limited`返回429，`/usage-timeout`模拟超时，`/usage-bad-ack`模拟错误回执。`/v1/chat/completions`仅测试用模型桩，不用于正式配置。该脚本及测试不进入发布镜像。

执行`pytest -q tests/test_model_usage.py tests/test_model_usage_node.py`验证本地采集与Node真实HTTP接收。模型、身份和token均为合成数据，不能冒充真实Server接收／真实供应商用量或收费验收。

## 本轮验证（2026-11-04）

- Python全量921通过、85跳过（外部数据库等显式测试未默认开启）；追加用量边界及Node检查后定向42通过。
- 隔离PostgreSQL17.6：实际建表、并发账号、持久化重试、发送租约及对话轮次／回放5项通过。检查点初次缺表由测试环境初始化补齐后复测通过；未连接远端数据库。
- 另跑Node真实本机HTTP端到端10例全部通过：正常、无地址、503、错误ACK、401、429、超时、usage缺失、真实0token、JSON修复重试。所有Agent请求正常返回，预期记录数量／状态／账号与会话关联正确；未知和0可区分，模型重试多记调用，回放不增记。
- Node模拟服务、供应商回复、用户身份均为合成测试；未使用真实模型或Server计费接口。配置真实URL后仍需测试环境联调。以下历史测试记录不代表新版已验收。

## 版本及兼容

V3使用用户token，不传user_id；保留本地owner_id用于账号隔离和查对话。model仍为每次实际调用的模型名／接入点ID，不发provider或actual_model。没有数据库新增列。旧payload不重写，发送时仅去掉user_id，旧provider／actual_model由Server兼容接受，不作为必填。Server去重应先检查归属、再比较忽略历史user_id后的业务字段；不因认证方式变化重新生成event_id或重新计费。旧版blocked事件不自动重发，需要核查原因后处理。

SQL里的:user_id由Server鉴权结果或授权运维查询提供，不是新的JSON字段。历史全量／数据库验证记录仅代表对应旧版本。

V3验证：对话／安装／发布／用量定向64项通过，随后补充身份校验失败及不同用户队列互不阻塞2项通过（用量专项最终24项）；Node本地真实HTTP 10例通过。覆盖重启无token等待、401/403后恢复、换token时旧响应不清除新token、回放刷新认证、token不落库、JSON无user_id及历史事件兼容。amd64只读镜像建表／身份隔离检查通过，402个运行文件哈希一致，精简包6项及全部SHA256通过。未连接真实Server计费接口或执行真实扣费。


## 2026-11-05 用户确认的Agent积分单价（Server待接入）

输入与输出分别按账号跨会话累计，每满1,000,000 token各扣300积分，未满余量结转，不合并输入输出凑整。单次新增应扣为300 ×（输入新增满百万次数＋输出新增满百万次数）；实际扣减为min（应扣，可用余额），余额最低0。必须在Server原子结算并以event_id幂等去重，不能每轮重扣历史阈值；缓存输入与推理输出不重复计数。此规则替代此前每百万1积分及任意自定该项单价的旧假设。超出余额差额的后续处理和平台失败重试收费仍待确认，不擅自追加欠费。当前仅用量采集／回调与余额预检已实现，真实结算未验。
