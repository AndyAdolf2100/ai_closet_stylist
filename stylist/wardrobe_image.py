"""Authenticated image reads for browser-side segmentation; never an arbitrary URL proxy."""
from urllib.parse import urlsplit

import httpx

from .errors import StylistError

IMAGE_HOSTS = frozenset({"aicloset-domestic.aidacloset.com", "aicloset-test-oss.wxbjq.net.cn"})
IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
MAX_IMAGE_BYTES = 12 * 1024 * 1024


async def read_wardrobe_image(upstream, product_id: str, transport=None, kind="original"):
    await upstream.identity()
    async with upstream.mcp() as mcp:
        result = await mcp.call("product.resolve", {"items": [{"source": "user", "product_id": product_id}]})
    rows = result.get("items") or []
    if len(rows) != 1 or rows[0].get("source") != "user" or str(rows[0].get("product_id")) != product_id:
        raise StylistError("wardrobe_image_not_found", "这件衣物暂时无法读取。", 404)
    url = str(rows[0].get("cutout_image" if kind == "cutout" else "original_image") or "")
    try:
        parsed = urlsplit(url)
        # Older wardrobe records use HTTP on our CDN; fetch those over TLS too.
        if (parsed.scheme == "http" and parsed.hostname in IMAGE_HOSTS
                and parsed.port in {None, 80} and not parsed.username and not parsed.password):
            url = parsed._replace(scheme="https", netloc=parsed.hostname).geturl()
            parsed = urlsplit(url)
        valid = (parsed.scheme == "https" and parsed.hostname in IMAGE_HOSTS
                 and parsed.port in {None, 443} and not parsed.username and not parsed.password)
    except ValueError:
        valid = False
    if not valid:
        raise StylistError("wardrobe_image_source_unsupported", "这张原图暂不支持现场去背景，先保留原图。", 422)
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False, transport=transport) as client:
            # Do not forward account credentials to the image host or follow redirects.
            async with client.stream("GET", url, headers={"Accept": "image/png,image/jpeg,image/webp,image/gif"}) as response:
                if response.status_code != 200:
                    raise StylistError("wardrobe_image_unavailable", "原图暂时没有加载成功，请稍后重试。", 502)
                media = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if media not in IMAGE_TYPES:
                    raise StylistError("wardrobe_image_type_unsupported", "这张图片格式暂不支持去背景。", 422)
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(content) + len(chunk) > MAX_IMAGE_BYTES:
                        raise StylistError("wardrobe_image_too_large", "原图过大，先保留原图查看。", 413)
                    content.extend(chunk)
                if not content:
                    raise StylistError("wardrobe_image_unavailable", "原图暂时没有加载成功，请稍后重试。", 502)
                return bytes(content), media
    except httpx.HTTPError as exc:
        raise StylistError("wardrobe_image_unavailable", "原图暂时没有加载成功，请稍后重试。", 502) from exc
