"""Validate public image mappings and keep Docker exclusions in sync. No credentials are used."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path

import httpx
from package_deployment import ROOT

from stylist.image_assets import IMAGE_SUFFIXES, image_assets, validate_source_image

START = "# BEGIN OSS image exclusions (generated from image-oss-manifest.json)"
END = "# END OSS image exclusions"


def check(root, *, sync=False, remote=False):
    static = root / "stylist/static"
    images = image_assets(static)
    manifest = json.loads((static / "image-oss-manifest.json").read_text())
    path = root / ".dockerignore"
    text = path.read_text()
    block = START + "\n" + "\n".join("stylist/static/" + name for name in sorted(images)) + "\n" + END
    existing = text[text.index(START):text.index(END) + len(END)] if START in text and END in text else None
    if sync:
        text = text.replace(existing, block) if existing else text.rstrip() + "\n\n" + block + "\n"
        path.write_text(text)
    elif existing != block:
        raise ValueError("Docker image exclusions are stale; run --sync-dockerignore")
    for name, item in images.items():
        path = static / name
        if path.is_file():
            validate_source_image(path, item)
    missing = [p.relative_to(static).as_posix() for p in static.rglob("*")
               if p.is_file() and not p.is_symlink() and "private" not in p.relative_to(static).parts
               and p.suffix.lower() in IMAGE_SUFFIXES and p.relative_to(static).as_posix() not in images]
    if missing:
        raise ValueError("Public images still need OSS mappings: " + ", ".join(missing))
    objects = {item["url"]: item for item in [*images.values(), *manifest.get("embedded", {}).values()]}
    if remote:
        def verify(pair):
            url, item = pair
            with httpx.Client(timeout=45, trust_env=False) as client:
                response = client.get(url, headers={"Origin": "https://aicloset-assistant.wxbjq.top"})
                response.raise_for_status()
                if (hashlib.sha256(response.content).hexdigest() != item["remote_sha256"]
                        or len(response.content) != item["remote_bytes"]
                        or item.get("cors_required", True) and response.headers.get("access-control-allow-origin") != "*"):
                    raise ValueError("Remote image integrity or CORS mismatch")
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(verify, objects.items()))
    return {"mapped_paths": len(images), "embedded_images": len(manifest.get("embedded", {})),
            "unique_objects": len(objects), "remote_verified": remote, "unmapped_public_images": len(missing)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--sync-dockerignore", action="store_true")
    parser.add_argument("--verify-remote", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.root, sync=args.sync_dockerignore, remote=args.verify_remote), ensure_ascii=False))
