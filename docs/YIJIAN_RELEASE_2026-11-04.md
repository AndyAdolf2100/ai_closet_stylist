# 爱搭衣橱部署包（2026-11-04）

目标：沿用已部署的Linux x86_64测试机、Docker Compose及`/opt/aicloset-assistant/config`配置。只打包，不代为远端安装或改写真实账号。

产物：`var/releases/aicloset-assistant-yijian-amd64-20261104-r2.tar.gz`及同名`.sha256`。内含新的amd64离线镜像和安装脚本；不包含凭证或数据库；按本轮要求包含四张有数据首页对比截图，未包含其他私有账号截图。当前依赖锁与已验证运行时一致，在该运行时上替换完整当前源码，随后展平为独立镜像。

## 上传与更新

把压缩包和校验文件都上传到实际应用服务器`/tmp`，再执行：

```bash
cd /tmp
sha256sum -c aicloset-assistant-yijian-amd64-20261104-r2.tar.gz.sha256 && \
tar -xOf aicloset-assistant-yijian-amd64-20261104-r2.tar.gz \
  aicloset-assistant/install.sh > /tmp/aicloset-install-20261104.sh && \
sudo bash /tmp/aicloset-install-20261104.sh \
  /tmp/aicloset-assistant-yijian-amd64-20261104-r2.tar.gz
```

安装器沿用现有配置，加载镜像、检查数据库、更新容器及现有助理Nginx站点。目标机不需要下载应用镜像或Python依赖。需要现有Docker Compose、Nginx和有效配置；首次全新机器不具备这些条件时，此包不能替代基础环境初始化。

完成后访问：

- `https://aicloset-assistant.wxbjq.top/static/closet-app/comparison/index.html#app-evolution`
- `https://aicloset-assistant.wxbjq.top/app/?design=yijian#profile`
- `https://aicloset-assistant.wxbjq.top/static/design-overview.html`

```bash
curl --fail --silent --show-error https://aicloset-assistant.wxbjq.top/health/ready
```

App登录和数据读取依赖服务器现有业务配置，网页验证码发送未新增；现有`STYLIST_ALLOW_MOBILE_LOGIN`开关需要开启才能校验验证码。

## 对比页截图与本轮更新

本轮包含用户指定的四张有数据首页／搭配列表截图，来自本机只读加载；凭证不随截图或部署包保存。其余原生账号截图不分发，使用独立示例截图替代并标明HTML参考。只通过显式 `--include-comparison-evidence` 加入四张白名单PNG，不复制整个private目录，源截图继续不纳入Git。

基于提交682bc34，包含桌面440px容器、同源旧入口跳转、App内登录与首次引导、顶部单一返回、回复底色协调及附件Esc修复。对比页演示独立，不发送短信或保存资料。新代码全量Python903通过／85跳过、前端166通过；打包后另检查页面和资源。

旧入口 `/`、`/mobile/` 跳转当前服务 `/app/?design=yijian`；正式登录 `/app/?design=yijian&screen=login`，首次引导 `screen=onboarding`。本地跳本地，远程跳当前远程服务。

提交核对：默认不复制四张账号截图，且删除对应展示区域；显式开关仅复制指定四张，源图仍不入Git。本次使用临时合成文件验证两种分支及目标目录防覆盖，不重新生成镜像或执行远端部署；上文r2及验收数为此前发布记录。
