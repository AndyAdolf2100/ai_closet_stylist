# Langfuse dev追踪与发布

2026-11-11，本地新增；当前打包默认dev，未部署远端Agent。

使用Langfuse Python SDK4（锁定4.18.0），与已探测的自托管3.224.1兼容；使用SDK的OpenTelemetry导出，不使用旧版JSON batch API做自动追踪。

运行时通过LANGFUSE_BASE_URL、LANGFUSE_PUBLIC_KEY、LANGFUSE_SECRET_KEY及LANGFUSE_TRACING_ENVIRONMENT注入。配置齐全时自动开启，可用LANGFUSE_TRACING_ENABLED=false关闭。没有密钥时保持业务可用，不初始化网络客户端。dev映射development，test映射test，prod映射production；计费回调environment独立，仍沿用原test规则，不因追踪环境改变。

每轮有stylist-chat根节点、agent-understand等图节点、model-plan／model-style／model-product_search模型节点、mcp-*工具节点及Server只读路径；记录request_id、conversation_id和最终模型输入／输出Token。固定公开的模型ID和工具名可查看，不上报Authorization、API密钥、附图、请求头、模型完整上下文或原始异常。正文最多6000字符并脱敏常见Bearer／JWT／key；用户输入与最终答复属于追踪内容，团队访问权限按各项目管理。SDK故障记录安全分类并降级，不替代业务异常；进程退出时刷新导出队列。

发布包包含代码和依赖，镜像默认Langfuse环境development。dev密钥另放交付目录aicloset-langfuse-dev.env（600权限），不入镜像或Git。部署时将其安装到/opt/aicloset-assistant/config/langfuse.env；Compose可选加载此文件。升级仍保留既有Server／模型／PostgreSQL配置。其他环境换成对应私有文件，无需把密钥写源码。

真实验证：一轮“我想要一件黑色的衣服，帮我从衣柜里找找”，使用真实文字模型、合成衣橱与临时库，返回黑上衣单品卡；dev可查询7节点，其中model-plan输入9405／输出52、model-product_search输入1040／输出16。工具节点标明synthetic，不宣称真实衣橱或真实积分扣费。证据仅存本地reports/26-11-11/langfuse-probe/agent-dev.json，密钥不进入报告。test／prod没有发送测试追踪。

配置、降级与脱敏5项以及对话、用量回调、单品入口和发布回归88项通过；镜像与离线包验证见交付VERIFICATION.json。本包构建基于f787fad及当时工作区追踪增量；用户随后授权提交这次接入、配置加载及文档测试，打包本身不自动提交或推送。
