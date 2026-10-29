"""Explicit real-MySQL regression in a disposable, loopback-only database."""
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from stylist.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def admin(sql):
    command = [
        "docker", "compose", "--env-file", "config/mysql-local.env", "-f", "compose.mysql-local.yaml",
        "exec", "-T", "mysql", "sh", "-c", 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot',
    ]
    result = subprocess.run(command, input=sql, cwd=ROOT, text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError("本地 MySQL 测试库管理失败，请先运行 setup_mysql_local.py 并确认容器健康。")


def main():
    url = urlsplit(Settings.load().database)
    if url.scheme != "mysql" or url.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("只允许连接本机 MySQL；请先运行 setup_mysql_local.py。")
    if url.username != "stylist" or url.path != "/stylist_local":
        raise RuntimeError("此脚本只使用专属 stylist_local Docker 配置。")
    database = "stylist_tmp_" + uuid.uuid4().hex
    admin(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin; "
          f"GRANT ALL ON `{database}`.* TO 'stylist'@'%';")
    try:
        env = dict(os.environ, STYLIST_TEST_MYSQL_DSN=urlunsplit(url._replace(path="/" + database)))
        return subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests/test_mysql.py"], cwd=ROOT, env=env,
        ).returncode
    finally:
        admin(f"DROP DATABASE `{database}`; REVOKE ALL ON `{database}`.* FROM 'stylist'@'%';")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(str(exc) if isinstance(exc, RuntimeError) else "本地 Docker 操作超时。", file=sys.stderr)
        sys.exit(1)
