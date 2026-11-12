# CI/CD部署分析与当前实现

2026-11-12；当前分支test，业务基线60d4c27；部署修改已获授权提交并推送company/test；实际流水线结果待验证。

## 当前规则

以当前ai_closet_stylist项目为唯一代码来源，旧Agent弃用。用户最初要求复用原CI，后明确允许改.gitlab-ci.yml，并由本项目提供自己的部署sh，不再依赖服务器上的未知旧脚本。保留devops-test Runner和172.16.0.91内网传输通道。

根.gitlab-ci.yml中DEPLOY_ENV只接受test／dev，默认test：

- test分支推送自动运行；任意分支可通过GitLab Run pipeline手动运行并选择环境。
- 其他分支普通推送不自动部署，原手工打包／打开目录／给部署命令习惯保留。
- DEPLOY_ENV=test部署aicloset-agent.wxbjq.top，调用aicloset-test.wxbjq.top的Server／MCP。
- DEPLOY_ENV=dev部署aicloset-assistant.wxbjq.top，调用aicloset-dev.wxbjq.top的Server／MCP。
- 用户最新要求PostgreSQL分库：dev=aicloset_stylist，test=aicloset_stylist_test；不碰弃用Agent旧数据域。

## 实现

源码白名单打包→SHA256→Runner上传→SSH执行仓库deploy/ci/deploy.sh→Docker构建→容器环境校验→数据库预检／迁移→候选容器检查→已知服务切换→公网H5／ops／API和revision检查→保留配置快照及回滚入口。

不写旧CIHOME/.env，不要求预装deploy-aicloset-agent.sh，不要求宿主Python，不改变/stylist-api前缀，不改Nginx。部署详情、变量和一次性配置见[CI_TEST_DEV.md](CI_TEST_DEV.md)。源码与镜像均不包含私密env，业务配置只从服务器config/test.env或dev.env加载，不由GitLab上传。Langfuse本期移除配置并停用。

test默认保留原站点的宿主8465端口，dev为8466，均映射容器8000。只停止本环境明确识别的旧容器，未知端口占用中止。现有Nginx实际代理目标须在首次真实流水线验证，不以旧Compose源码端口代替服务器取证。

## 迁移前实测证据

2026-11-12 14:32（Asia/Shanghai），公网只读、无凭证、无业务写入。

| 检查 | aicloset-agent | aicloset-assistant |
|---|---|---|
| / | 200旧站点 | 307到/app/?design=yijian |
| /health/ready | 200旧服务就绪 | 200 |
| OpenAPI | recommend-outfit，26路径 | AI Closet Stylist，58路径 |
| /app/ | 404 | 200 |
| /static/app.js | 404 | 200 |
| GET /stylist-api/conversations未登录 | 404 | 401 |
| /ops/conversations | 404 | 200 |

原始摘要在忽略目录var/deployment-audit/20261112-existing-ci-public.json。上述说明-agent尚为旧程序，不是新版接口已部署但坏了。Server的/api／users／mcp通过后端配置访问，不要求代理到Agent前端域名。

## 验证边界

本轮仅本地测试和公开只读探测。真实GitLab Runner权限、目标主机Docker构建、服务器私密配置加载、域名端口代理及上游带身份业务仍待首次流水线验收。基础路由／401／OpenAPI检查不等于模型、数美、保存或试穿扣费验收。未触发CI，不创建订单，不扣费，不宣称远端已更新。
