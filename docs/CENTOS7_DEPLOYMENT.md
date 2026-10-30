# 当前测试机部署补充：CentOS 7

目标机器由用户在2026-10-29提供的实际输出确认：CentOS Linux 7 (Core)、x86_64、Docker 20.10.7。此前按Ubuntu准备的系统包安装命令不适用于这台机器；Docker应用镜像、Compose和Nginx站点内容仍可复用，宿主机工具、证书与网络须单独验证。

完整安装和更新以 [离线部署总文档](TEST_SERVER_DEPLOYMENT.md) 为准。用户已提供版本 `20261030T080643Z-91a41c298fa0-2192` 部署成功输出；本文保留宿主机工具及路径说明。

## Compose 安装

不要在这台机器安装从Ubuntu .deb提取的Compose二进制：已实际观察到它需要GLIBC_2.32/2.34，导致Docker将插件判为不可加载。不要为此替换系统glibc。使用官方GitHub发行的静态链接Linux x86_64版本，离线包为 `compose-centos7-x86_64.tar.gz`，并检查官方SHA256与ELF动态依赖。

通过跳板机上传到 `/tmp` 后：

```sh
cd ~
tar -xzf /tmp/compose-centos7-x86_64.tar.gz
cd compose-centos7-x86_64
sudo sh install.sh
docker compose version
sudo docker compose ls
```

安装脚本先执行新二进制的version，确认实际宿主机能运行，才修改已安装插件。只自动备份并替换此前明确提供的、SHA256已知的Ubuntu版本；其他已有插件不覆盖。不会升级或重启Docker、修改glibc，不依赖dpkg-deb/yum或服务器外网下载。

## 应用与 Nginx

应用仍用项目中的 `compose.yaml`、私密的 `config/` 和单应用容器。远程PostgreSQL连接、私密打包与配置备份方法见 [发布操作入口](SIMPLE_DEPLOYMENT.md)。不要照搬Ubuntu的apt或sites-available/sites-enabled路径。

先检查现有Nginx及实际include位置：

```sh
sudo /usr/local/nginx/sbin/nginx -t
sudo /usr/local/nginx/sbin/nginx -T 2>&1 | grep '^# configuration file'
```

当前测试机实际Nginx程序为 `/usr/local/nginx/sbin/nginx`，主配置为 `/usr/local/nginx/conf/nginx.conf`，已确认加载 `vhost/*.conf`。部署前曾出现证书可用但首页／健康路径返回旧管理后台HTML；后续离线安装已返回成功，安装器确认容器就绪与本机HTTPS代理的JSON检查通过。带身份业务状态需另行验证。

已按当前证书路径准备 `deploy/nginx/aicloset-assistant.centos7.conf`。先启动应用，确认 `http://127.0.0.1:8466/health/ready` 返回JSON，再新增域名站点；不改已有站点配置：

```sh
curl --fail http://127.0.0.1:8466/health/ready
# 先确认没有其他配置已明确声明相同域名，有则检查并备份原配置再处理冲突。
sudo grep -Rn 'server_name.*aicloset-assistant.wxbjq.top' /usr/local/nginx/conf/vhost/
sudo cp deploy/nginx/aicloset-assistant.centos7.conf /usr/local/nginx/conf/vhost/aicloset-assistant.wxbjq.top.conf
sudo /usr/local/nginx/sbin/nginx -t
sudo /usr/local/nginx/sbin/nginx -s reload
```

配置使用现有 `/usr/local/nginx/conf/keys/wxbjq.top/1wxbjq.top.pem` 和 `.key`，仅引用路径，不复制私钥。为兼容旧Nginx/OpenSSL先启用TLSv1.2，核对 `nginx -V` 后再决定是否加TLSv1.3。不要使用不存在的 `/etc/letsencrypt/live/...` 路径，不需要重新安装Nginx。若启用了SELinux且代理返回502/Permission denied，应结合Nginx错误日志和SELinux审计确认网络访问策略，不直接关闭SELinux。

Docker应用端口仍仅绑定 `127.0.0.1:8466`；公网只开放80/443。如果服务器无法访问镜像仓库与Python依赖源，优先在可构建的机器生成相同架构离线镜像，再经跳板机上传，不能将源码包称为无需出网即可安装。

本机未直接登录测试机；用户已提供Docker20.10.7加载镜像、启动应用及健康检查成功的输出。源码构建实际因Docker Hub超时失败，后续使用含镜像离线包。主机glibc与容器内glibc分属不同环境；安装成功不代替真实模型／MCP、账号和持久数据备份恢复验收。
