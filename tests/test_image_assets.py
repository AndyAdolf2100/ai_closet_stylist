"""Image outsourcing keeps code local and rejects stale release mappings."""
import hashlib
import json

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from scripts.package_deployment import release_files
from stylist.image_assets import ImageStaticFiles, image_assets

URL = "https://aicloset-test-oss.wxbjq.net.cn/aicloset-server/fixture/image.png"


def manifest(static, **overrides):
    static.mkdir(parents=True, exist_ok=True)
    value = {"url": URL, "sha256": hashlib.sha256(b"fixture-image").hexdigest(), "bytes": 13}
    value.update(overrides)
    (static / "image-oss-manifest.json").write_text(json.dumps({"version": 1, "images": {"photo.png": value}}))


def test_public_images_redirect_even_when_original_is_not_bundled_and_code_stays_local(tmp_path):
    manifest(tmp_path)
    (tmp_path / "app.js").write_text("const fixture = true;")
    app = Starlette()
    app.mount("/static", ImageStaticFiles(directory=tmp_path))
    with TestClient(app, follow_redirects=False) as client:
        for method in [client.get, client.head]:
            result = method("/static/photo.png?v=1")
            assert result.status_code == 307
            assert result.headers["location"] == URL
            assert result.headers["cache-control"] == "no-cache"
        assert client.get("/static/app.js").text == "const fixture = true;"
        assert client.get("/static/missing.png").status_code == 404
        assert client.post("/static/photo.png").status_code == 405


@pytest.mark.parametrize("url", ["http://aicloset-test-oss.wxbjq.net.cn/image.png", "https://other.invalid/a.png",
                                "https://secret@aicloset-test-oss.wxbjq.net.cn/a.png",
                                "https://aicloset-test-oss.wxbjq.net.cn/a.png?token=private"])
def test_manifest_rejects_unknown_hosts_and_credential_urls(tmp_path, url):
    manifest(tmp_path, url=url)
    with pytest.raises(ValueError, match="URL"):
        image_assets(tmp_path)


def test_release_omits_verified_images_keeps_manifest_and_rejects_modified_originals(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.package_deployment.FILES", [])
    static = tmp_path / "stylist/static"
    manifest(static)
    (static / "photo.png").write_bytes(b"fixture-image")
    (static / "app.js").write_text("// fixture")
    names = {path.relative_to(tmp_path).as_posix() for path in release_files(tmp_path)}
    assert "stylist/static/photo.png" not in names
    assert "stylist/static/app.js" in names
    assert "stylist/static/image-oss-manifest.json" in names
    (static / "photo.png").write_bytes(b"new-source")
    with pytest.raises(ValueError, match="Image changed"):
        release_files(tmp_path)


def test_packaging_can_use_real_saved_image_without_contacting_docker(tmp_path, monkeypatch):
    import io
    import tarfile

    from scripts.package_deployment import package

    monkeypatch.setattr("scripts.package_deployment.FILES", [])
    root = tmp_path / "source"
    (root / "stylist").mkdir(parents=True)
    (root / "stylist/main.py").write_text("# runtime fixture")
    image = tmp_path / "image.tar"
    with tarfile.open(image, "w") as saved:
        raw = json.dumps([{"Config": "fixture.json", "RepoTags": ["fixture:offline"], "Layers": []}]).encode()
        entry = tarfile.TarInfo("manifest.json")
        entry.size = len(raw)
        saved.addfile(entry, io.BytesIO(raw))
    def unexpected_docker(*args, **kwargs):
        raise AssertionError("Docker must not be called for an explicit saved image")
    monkeypatch.setattr("scripts.package_deployment.subprocess.run", unexpected_docker)
    output = tmp_path / "release.tar.gz"
    package(output, image="fixture:offline", image_archive=image, root=root, runtime_only=True)
    with tarfile.open(output) as release:
        assert release.extractfile("aicloset-assistant/image.tar").read() == image.read_bytes()
    with pytest.raises(ValueError, match="tag"):
        package(tmp_path / "wrong.tar.gz", image="other:tag", image_archive=image, root=root)


def test_release_blocks_new_unmapped_image_instead_of_silently_bloating_package(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.package_deployment.FILES", [])
    static = tmp_path / "stylist/static"
    manifest(static)
    (static / "new.jpeg").write_bytes(b"new image")
    with pytest.raises(ValueError, match="needs an OSS mapping"):
        release_files(tmp_path)


def test_docker_release_validation_accepts_removed_oss_sources_but_keeps_runtime(tmp_path):
    from stylist.image_assets import validate_release_images
    manifest(tmp_path)
    (tmp_path / "runtime.wasm").write_bytes(b"runtime")
    (tmp_path / "model.onnx").write_bytes(b"model")
    (tmp_path / "icon.svg").write_text("<svg/>")
    assert "photo.png" in validate_release_images(tmp_path)
    assert (tmp_path / "runtime.wasm").exists()
