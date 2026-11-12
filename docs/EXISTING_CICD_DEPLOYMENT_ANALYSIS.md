# CI/CD架构与旧部署迁移说明

更新：2026-11-12。日常操作及完整命令统一见[Agent＋H5 CI打包与部署完整流程](CI_TEST_DEV.md)，本文件只保留架构取舍及历史证据。

## 当前架构

当前项目为唯一代码来源，同级旧`ai_closet_agent`弃用；不把旧项目的Server脚本、配置或数据迁移到当前Agent。

- main默认部署dev，test分支默认部署test；两分支分别维护only=main/web与test/web。
- 沿用Server已有的基础GitLab CI结构及devops-test Runner；不依赖旧GitLab不支持的workflow/rules等功能。
- 实际目标服务器为172.16.0.90。继承旧配置的172.16.0.91曾导致配置缺失错误，已修正。
- Runner传小体积源码包和SHA256，服务器基于预导入的amd64运行依赖镜像离线构建；不访问Docker Hub或在线安装依赖。
- 部署脚本来自当前仓库，经SSH标准输入运行，不依赖服务器未知的旧deploy-aicloset-agent.sh，也不覆盖旧CIHOME/.env。
- 实际私密env在服务器config下，源码和镜像不携带凭证；dev/test配置、数据库、容器及端口独立，运行依赖镜像可共用。
- PostgreSQL分别为aicloset_stylist、aicloset_stylist_test；ops MySQL分别为aicloset_dev、aicloset_test。
- Agent的/stylist-api前缀保留；Server业务请求走对应Server域名，不新增接口转换层。
- CI只读检查SQL结构，运维手动执行DDL；不自动建库、建表或索引。
- Nginx由运维独立维护：assistant→8466，agent→8465。候选容器检查通过才切换，再校验公网revision；失败尝试恢复旧容器。
- report／UI change log继续独立打包和部署，不加入CI。

## 旧站点迁移前证据

2026-11-12 14:32（Asia/Shanghai），公网只读、无凭证、无业务写入。下表是**迁移前历史状态**，不代表当前故障。

| 检查 | aicloset-agent | aicloset-assistant |
|---|---|---|
| / | 200旧站点 | 307到/app/?design=yijian |
| /health/ready | 200旧服务就绪 | 200 |
| OpenAPI | recommend-outfit，26路径 | AI Closet Stylist，58路径 |
| /app/ | 404 | 200 |
| /static/app.js | 404 | 200 |
| GET /stylist-api/conversations未登录 | 404 | 401 |
| /ops/conversations | 404 | 200 |

原始摘要在忽略目录var/deployment-audit/20261112-existing-ci-public.json。旧agent的404当时意味着尚未发布新版，不能解释成新版API失效。

## 后续实际证据与边界

目标GitLab CI Lint通过；Runner真实运行过构建上传与SSH部署。用户已确认test建库／16张表及索引、离线镜像导入、test运行容器连接aicloset_test。公网后续读取test提交ed1d55b，H5及/ops/conversations为200，/ops为404是入口路径问题。

dev首次发布14fd4c7在数据库索引预检停止，旧服务未因此被切换；用户手动创建缺少的消息联合索引成功，后续重试结果需按实际日志和公网revision继续验证。

上述不等于模型质量、带身份业务接口、数美、真实支付或试穿扣费验收。当前报告不包含凭证、用户资料和原始敏感日志。
