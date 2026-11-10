"""Public OSS image redirects; application scripts and private media stay local."""
import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

MANIFEST_NAME = "image-oss-manifest.json"
OSS_HOST = "aicloset-test-oss.wxbjq.net.cn"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def image_assets(static_dir: Path) -> dict:
    path = static_dir / MANIFEST_NAME
    if not path.is_file():
        return {}
    manifest = json.loads(path.read_text())
    if manifest.get("version") != 1 or not isinstance(manifest.get("images"), dict):
        raise ValueError("Invalid public image manifest")
    images = manifest["images"]
    for name, item in images.items():
        relative = PurePosixPath(name)
        if (relative.is_absolute() or ".." in relative.parts or str(relative) != name
                or "private" in relative.parts or relative.suffix.lower() not in IMAGE_SUFFIXES):
            raise ValueError("Invalid public image path: " + name)
        url = urlsplit(item["url"])
        if (url.scheme != "https" or url.hostname != OSS_HOST or url.port is not None
                or url.username or url.password or url.query or url.fragment):
            raise ValueError("Invalid public image URL: " + name)
        if (not isinstance(item.get("bytes"), int) or item["bytes"] < 1
                or not isinstance(item.get("sha256"), str) or len(item["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in item["sha256"])):
            raise ValueError("Invalid image integrity metadata: " + name)
    return images


def validate_source_image(path: Path, item: dict) -> None:
    """Never silently omit a changed local image from a release."""
    if path.stat().st_size != item["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
        raise ValueError("Image changed; upload it and refresh the OSS manifest: " + str(path))


class ImageStaticFiles(StaticFiles):
    def __init__(self, *, directory, **kwargs):
        super().__init__(directory=directory, **kwargs)
        self.images = image_assets(Path(directory))

    async def get_response(self, path, scope):
        item = self.images.get(path)
        if item is not None and scope["method"] in {"GET", "HEAD"}:
            # Do not cache an old destination when the same logical image is updated.
            return RedirectResponse(item["url"], status_code=307, headers={"Cache-Control": "no-cache"})
        return await super().get_response(path, scope)


def validate_release_images(static_dir: Path) -> dict:
    """Both source archives and Docker builds reject unmapped or changed images."""
    images = image_assets(static_dir)
    for path in static_dir.rglob("*"):
        if not path.is_file() or path.is_symlink() or "private" in path.relative_to(static_dir).parts:
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        name = path.relative_to(static_dir).as_posix()
        if name not in images:
            raise ValueError("Image needs an OSS mapping before release: " + name)
        validate_source_image(path, images[name])
    return images


if __name__ == "__main__":
    validate_release_images(Path(__file__).with_name("static"))
