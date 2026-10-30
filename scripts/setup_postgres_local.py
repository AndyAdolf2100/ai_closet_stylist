"""Start an isolated local database using an existing Docker image; never pull."""
import argparse
import asyncio
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

import yaml

ROOT = Path(__file__).resolve().parents[1]


def docker(*args):
    result = subprocess.run(["docker", *args], cwd=ROOT, text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError("Docker 操作失败，请确认 Docker Desktop 引擎已启动；未拉取任何镜像。")
    return result.stdout.strip()


def private_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", help="已有的 PostgreSQL 镜像标签")
    args = parser.parse_args()
    docker("info", "--format", "{{.ServerVersion}}")
    images = docker("image", "ls", "--format", "{{.Repository}}:{{.Tag}}").splitlines()
    choices = sorted((i for i in images if i.startswith(("postgres:16", "postgres:17"))),
                     key=lambda i: (i != "postgres:17.6", i == "postgres:latest", i))
    image = args.image or (choices[0] if choices else None)
    if image not in images:
        raise RuntimeError("没有找到已有的 PostgreSQL 镜像；按要求未下载。请先提供本机镜像或导入已有镜像包。")
    env_path = ROOT / "config/postgres-local.env"
    if env_path.exists():
        env = dict(line.split("=", 1) for line in env_path.read_text().splitlines() if line and not line.startswith("#"))
        if args.image and env.get("STYLIST_POSTGRES_IMAGE") != args.image:
            raise RuntimeError("已有本地配置使用其他镜像，保留原配置；不自动切换数据卷的 PostgreSQL 版本。")
    else:
        env = {
            "STYLIST_POSTGRES_IMAGE": image, "STYLIST_POSTGRES_PORT": "15432",
            "STYLIST_POSTGRES_PASSWORD": secrets.token_hex(24),
        }
        private_write(env_path, "".join(f"{key}={value}\n" for key, value in env.items()))
    command = ("compose", "--env-file", str(env_path), "-f", "compose.postgres-local.yaml")
    docker(*command, "up", "-d", "--pull", "never")
    container = docker(*command, "ps", "-q", "postgres")
    print("本地 PostgreSQL 容器已启动，等待健康检查；未拉取镜像。", flush=True)
    for _ in range(60):
        if docker("inspect", "--format", "{{.State.Health.Status}}", container) == "healthy":
            break
        time.sleep(2)
    else:
        raise RuntimeError("PostgreSQL 未通过健康检查；保留原应用配置与容器数据，请检查容器日志。")
    local_path = ROOT / "config/local.yaml"
    local = yaml.safe_load(local_path.read_text()) or {} if local_path.exists() else {}
    local["database"] = (
        f"postgresql://stylist:{quote(env['STYLIST_POSTGRES_PASSWORD'], safe='')}@127.0.0.1:"
        f"{env['STYLIST_POSTGRES_PORT']}/aicloset_stylist"
    )
    local.pop("checkpoint_database", None)
    # Initialize before selecting PostgreSQL for normal local app startup.
    from stylist.store import Store

    Store(local["database"])

    from stylist.config import Settings
    from stylist.engine import Stylist

    async def initialize():
        async with Stylist(Settings(database=local["database"]), Store(local["database"]), None).checkpoints() as saver:
            await saver.setup()
    asyncio.run(initialize())
    private_write(local_path, yaml.safe_dump(local, allow_unicode=True))
    print("已切换本地 stylist 到 PostgreSQL：127.0.0.1:" + env["STYLIST_POSTGRES_PORT"] + "/aicloset_stylist。")
    print("会话、设置和图检查点均存本地 PostgreSQL；既有数据与远端数据保留。可运行 sh run-local.sh。")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(str(exc) if isinstance(exc, RuntimeError) else "Docker 操作超时，未下载镜像。", file=sys.stderr)
        sys.exit(1)
