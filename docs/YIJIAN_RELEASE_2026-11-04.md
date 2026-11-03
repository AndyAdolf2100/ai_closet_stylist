# 衣间部署包（2026-11-04）

目标：沿用已部署的Linux x86_64测试机、Docker Compose及`/opt/aicloset-assistant/config`配置。只打包，不代为远端安装或改写真实账号。

产物：`var/releases/aicloset-assistant-yijian-amd64-20261104.tar.gz`及同名`.sha256`。内含新的amd64离线镜像和安装脚本；不包含凭证、数据库、真实账号图片。当前依赖锁与已验证运行时一致，在该运行时上替换完整当前源码，随后展平为独立镜像。

## 上传与更新

把压缩包和校验文件都上传到实际应用服务器`/tmp`，再执行：

```bash
cd /tmp
sha256sum -c aicloset-assistant-yijian-amd64-20261104.tar.gz.sha256 && \
tar -xOf aicloset-assistant-yijian-amd64-20261104.tar.gz \
  aicloset-assistant/install.sh > /tmp/aicloset-install-20261104.sh && \
sudo bash /tmp/aicloset-install-20261104.sh \
  /tmp/aicloset-assistant-yijian-amd64-20261104.tar.gz
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

## 对比页截图

本地原生截图中含账号内容，不随包分发。部署包改用新建示例账号环境截图，所有接口被模拟且阻断外部请求；iOS栏明确标为HTML参考，不能当作原生截图或上线验收。页面文字比较仍依据`dev_2.0.0`代码。衣间截图和界面保持最新本地实现。

私有截图目录同时由源码打包、Docker构建和wheel数据清单排除。发布树使用`scripts/prepare_release_tree.py`构建，示例截图由`scripts/capture_release_demo.cjs`生成，不修改本机原对比页的原生证据。
