from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi.testclient import TestClient

from stylist.config import Settings
from stylist.errors import StylistError
from stylist.main import create_app
from stylist.wardrobe_image import MAX_IMAGE_BYTES, read_wardrobe_image


class ImageRead:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def identity(self):
        self.calls.append('identity')
        return '1'

    @asynccontextmanager
    async def mcp(self):
        yield self

    async def call(self, tool, args):
        self.calls.append((tool, args))
        return {'items': self.rows}


def product(url='https://aicloset-domestic.aidacloset.com/aicloset-sop/cloth.png', **extra):
    return {'source': 'user', 'product_id': '12', 'original_image': url, **extra}


@pytest.mark.asyncio
async def test_image_read_resolves_current_users_item_without_forwarding_credentials():
    upstream = ImageRead([product()])

    def handle(request):
        assert request.url.host == 'aicloset-domestic.aidacloset.com'
        assert 'authorization' not in request.headers
        return httpx.Response(200, headers={'Content-Type': 'image/png'}, content=b'png-bytes')

    result = await read_wardrobe_image(upstream, '12', httpx.MockTransport(handle))
    assert result == (b'png-bytes', 'image/png')
    assert upstream.calls == ['identity', ('product.resolve', {'items': [{'source': 'user', 'product_id': '12'}]})]


@pytest.mark.asyncio
@pytest.mark.parametrize('origin', ['http://aicloset-domestic.aidacloset.com',
                                  'http://aicloset-test-oss.wxbjq.net.cn:80'])
async def test_legacy_cdn_urls_are_fetched_over_https(origin):
    def handle(request):
        assert request.url.scheme == 'https'
        assert request.url.port in {None, 443}
        assert request.url.path == '/cloth.png'
        assert request.url.query == b'v=1'
        assert 'authorization' not in request.headers
        return httpx.Response(200, headers={'Content-Type': 'image/png'}, content=b'png')

    result = await read_wardrobe_image(ImageRead([product(origin + '/cloth.png?v=1')]),
                                     '12', httpx.MockTransport(handle))
    assert result == (b'png', 'image/png')


@pytest.mark.asyncio
@pytest.mark.parametrize('row', [product('http://127.0.0.1/x'), product('https://evil.invalid/x'),
    product('https://user@aicloset-domestic.aidacloset.com/x'), product('https://aicloset-domestic.aidacloset.com:8000/x')])
async def test_untrusted_image_locations_never_make_requests(row):
    def unexpected(request):
        pytest.fail('untrusted image URL was fetched')
    with pytest.raises(StylistError) as exc:
        await read_wardrobe_image(ImageRead([row]), '12', httpx.MockTransport(unexpected))
    assert exc.value.status == 422


@pytest.mark.asyncio
@pytest.mark.parametrize('rows', [[], [product(product_id='99')], [product(source='system')]])
async def test_missing_or_wrong_owner_resolution_is_not_downloaded(rows):
    with pytest.raises(StylistError) as exc:
        await read_wardrobe_image(ImageRead(rows), '12')
    assert exc.value.status == 404


@pytest.mark.asyncio
@pytest.mark.parametrize('status,media,body,expected', [
    (302, 'image/png', b'', 502), (200, 'image/svg+xml', b'<svg/>', 422),
    (200, 'image/png', b'x' * (MAX_IMAGE_BYTES + 1), 413), (200, 'image/png', b'', 502)])
async def test_redirects_unsupported_and_oversized_images_are_rejected(status, media, body, expected):
    def handle(request):
        return httpx.Response(status, headers={'Content-Type': media, 'Location': 'http://127.0.0.1'}, content=body)
    with pytest.raises(StylistError) as exc:
        await read_wardrobe_image(ImageRead([product()]), '12', httpx.MockTransport(handle))
    assert exc.value.status == expected


def test_image_route_requires_auth_and_is_private(tmp_path, monkeypatch):
    async def read(upstream, product_id, kind="original"):
        assert upstream.authorization == 'Bearer test'
        return b'png', 'image/png'
    monkeypatch.setattr('stylist.main.read_wardrobe_image', read)
    with TestClient(create_app(Settings(database=str(tmp_path / 'images.db')))) as client:
        assert client.get('/stylist-api/wardrobe/12/image-source').status_code == 401
        response = client.get('/stylist-api/wardrobe/12/image-source', headers={'Authorization': 'Bearer test'})
        assert response.content == b'png'
        assert response.headers['Cache-Control'] == 'private, no-store'
        assert response.headers['Cross-Origin-Resource-Policy'] == 'same-origin'
        assert client.get('/stylist-api/wardrobe/0/image-source', headers={'Authorization': 'Bearer test'}).status_code == 422
