"""Package an allowlisted release; private config requires explicit opt-in, data is excluded."""
import argparse
import hashlib
import io
import shlex
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parents[1]
FILES = ["Dockerfile", ".dockerignore", "compose.yaml", "install.sh", "pyproject.toml", "uv.lock", "README.md",
         "docs/DOCKER_UBUNTU_DEPLOYMENT.md", "docs/CENTOS7_DEPLOYMENT.md", "scripts/prepare_docker_config.py",
         "docs/SIMPLE_DEPLOYMENT.md", "docs/POSTGRES_LOCAL.md",
         "docs/TEST_SERVER_DEPLOYMENT.md", "docs/NGINX_SHARED_ROUTING.md",
         "docs/NGINX_API_LOCATION.md", "scripts/inspect_nginx_routes.sh",
         "deploy/nginx/stylist-api.location.inc",
         "deploy/docker/Dockerfile.compact", "deploy/docker/start.sh", "deploy/docker/deploy.sh", "deploy/docker/deploy.env.example",
         "deploy/nginx/aicloset-assistant.conf", "deploy/nginx/aicloset-assistant.http.conf",
         "deploy/nginx/aicloset-assistant.centos7.conf"]
ASSET_SUFFIXES = {".py", ".sql", ".md", ".css", ".js", ".json", ".html", ".svg", ".png", ".jpg", ".webp"}


def release_files(root):
    paths = [root / name for name in FILES]
    paths.extend(path for path in (root / "stylist").rglob("*") if path.is_file()
                 and "__pycache__" not in path.parts and path.suffix in ASSET_SUFFIXES)
    for path in paths:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Release input is missing or a symlink: " + str(path.relative_to(root)))
    return sorted(paths)


def public_bootstrap(config):
    """Read only public endpoints, the model identifier and an RSA public key. Never export API keys."""
    try:
        raw = yaml.safe_load(config.read_text())
        llm = dict(raw.get("llm") or {})
        llm.update(next((m for m in llm.get("models", []) if m.get("id") == llm.get("default_model_id")), {}))
        upstream = next(s for s in raw["mcp_tool_routing"]["servers"] if s.get("enabled", True))
        origin = urlsplit(upstream["url"])
        values = {
            "STYLIST_SERVER_URL": f"{origin.scheme}://{origin.netloc}",
            "STYLIST_MCP_URL": upstream["url"],
            "STYLIST_LLM_URL": llm["base_url"],
            "STYLIST_LLM_MODEL": llm["model"],
            "STYLIST_LOGIN_APP_VERSION": raw["upstream_auth"].get("app_version") or "1.2.0",
        }
        for name in ["STYLIST_SERVER_URL", "STYLIST_MCP_URL", "STYLIST_LLM_URL"]:
            parsed = urlsplit(values[name])
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or any([
                    parsed.username, parsed.password, parsed.query, parsed.fragment]):
                raise ValueError("Only public HTTP endpoints without embedded credentials may be bundled")
        if any(not value or any(c in str(value) for c in "\n\r\0") for value in values.values()):
            raise ValueError("Invalid bootstrap values")
        key_path = Path(raw["upstream_auth"]["public_key_path"])
        if not key_path.is_absolute():
            key_path = next(p for p in [config.parent / key_path, config.parent.parent / key_path] if p.is_file())
        key = serialization.load_pem_public_key(key_path.read_bytes())
        pem = key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    except (OSError, ValueError, TypeError, KeyError, StopIteration, yaml.YAMLError):
        raise ValueError("Cannot prepare public bootstrap settings; no private configuration was exported") from None
    defaults = "# Public connection defaults only; the model API key is entered privately on the server.\n"
    defaults += "".join(f"{name}={shlex.quote(str(value))}\n" for name, value in values.items())
    return {"deploy/docker/runtime.defaults": defaults.encode(), "deploy/docker/login-public.pem": pem}


def package(output, image=None, *, root=ROOT, bootstrap_config=None, private_config_dir=None, runtime_only=False):
    paths = release_files(root)
    if runtime_only:
        if not image:
            raise ValueError("Runtime-only package requires an image")
        paths = [p for p in paths if p.relative_to(root).parts[0] != "stylist"]
    private_files = {}
    if private_config_dir:
        for name in ("deploy.env", "login-public.pem"):
            path = Path(private_config_dir) / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Private deployment configuration is incomplete")
            private_files["private-config/" + name] = path.read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".stylist-release-", dir=output.parent) as temp:
        image_tar = Path(temp) / "image.tar"
        archive_path = Path(temp) / "release.tar.gz"
        if image:
            subprocess.run(["docker", "image", "save", "--output", str(image_tar), image], check=True)
        manifest = []
        with tarfile.open(archive_path, "w:gz", compresslevel=1) as archive:
            def add_bytes(name, content, mode=0o644):
                info = tarfile.TarInfo("aicloset-assistant/" + name)
                info.size, info.mode = len(content), mode
                archive.addfile(info, io.BytesIO(content))
                manifest.append(f"{hashlib.sha256(content).hexdigest()}  {name}\n")

            for path in paths:
                add_bytes(str(path.relative_to(root)), path.read_bytes(), path.stat().st_mode & 0o777)
            for name, content in private_files.items():
                add_bytes(name, content, 0o600)
            if bootstrap_config:
                for name, content in public_bootstrap(bootstrap_config).items():
                    add_bytes(name, content)
            if image:
                archive.add(image_tar, arcname="aicloset-assistant/image.tar", recursive=False)
                with image_tar.open("rb") as file:
                    manifest.append(hashlib.file_digest(file, "sha256").hexdigest() + "  image.tar\n")
                add_bytes("image-name.txt", (image + "\n").encode())
            content = "".join(manifest).encode()
            info = tarfile.TarInfo("aicloset-assistant/MANIFEST.sha256")
            info.size, info.mode = len(content), 0o644
            archive.addfile(info, io.BytesIO(content))
        if private_files:
            archive_path.chmod(0o600)
        archive_path.replace(output)
    with output.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    output.with_name(output.name + ".sha256").write_text(f"{digest}  {output.name}\n")
    return len(paths)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("var/releases/aicloset-assistant-source.tar.gz"))
    parser.add_argument("--image", help="Optionally embed an already built single-platform image for docker load")
    parser.add_argument("--bootstrap-config", type=Path, help="Bundle public endpoints/model ID/public key only; never the API key")
    parser.add_argument("--private-config-dir", type=Path, help="Explicit private bundle: include credentials, never distribute publicly")
    parser.add_argument("--runtime-only", action="store_true", help="Omit duplicate application source when an image is embedded")
    args = parser.parse_args()
    count = package(args.output, args.image, bootstrap_config=args.bootstrap_config, private_config_dir=args.private_config_dir, runtime_only=args.runtime_only)
    print(f"Packaged {count} files into {args.output}; " + ("PRIVATE bundle includes deployment credentials." if args.private_config_dir else "runtime config and data excluded."))
