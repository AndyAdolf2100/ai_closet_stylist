import asyncio
import base64
import json
import struct
import zlib

import httpx
import pytest

from stylist.composition import CompositionInput, Compositions, validate_png
from stylist.config import Settings
from stylist.errors import StylistError
from stylist.models import ChatRequest, Look, Product, Reply, Slot, Task
from stylist.store import Store
from stylist.upstream import Upstream


def png():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 960, 1200, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + b'\xff\xff\xff\xff' * 960) * 1200)) + chunk(b'IEND', b''))


def setup(tmp_path):
    store = Store(str(tmp_path / 'composition.db'))
    request = ChatRequest(message='一套通勤装', request_id='composition-seed')
    cid, claim, state, _ = store.reserve('1', request)
    state.looks = [Look(title='通勤', items=[Product(source='user', product_id='1', slot=Slot.TOP)])]
    reply = Reply(conversation_id=cid, version=1, mode='recommend', delivery='outfit', message='搭配', task=Task(), looks=state.looks)
    store.finish('1', request, claim, state, reply)
    body = 'data:image/png;base64,' + base64.b64encode(png()).decode()
    return Compositions(store), cid, CompositionInput(version=1, look_index=0, theme='female', image_data=body)


class Upload:
    def __init__(self):
        self.calls = 0
        self.owner = '1'
        self.fail = False

    async def identity(self):
        return self.owner

    async def upload_outfit_image(self, image):
        self.calls += 1
        await asyncio.sleep(.01)
        if self.fail:
            raise StylistError('composition_upload_unknown', 'unknown', 502)
        return {'url': f'https://aicloset-domestic.aidacloset.com/web/{self.calls}.png'}


@pytest.mark.asyncio
async def test_only_completed_image_is_persisted_and_reused_across_service_restarts(tmp_path):
    service, cid, request = setup(tmp_path)
    upstream = Upload()
    assert service.get('1', cid, 1, 0, 'female')['status'] == 'missing'
    first = await service.save(upstream, cid, request)
    second = await Compositions(service.store).save(upstream, cid, request)
    assert first == second
    assert upstream.calls == 1
    assert Compositions(service.store).get('1', cid, 1, 0, 'female')['image_url'] == first['image_url']
    assert service.get('1', cid, 1, 0, 'male')['image_url'] == first['image_url']
    assert (await service.save(upstream, cid, request.model_copy(update={'theme': 'male'})))['image_url'] == first['image_url']
    assert upstream.calls == 1


@pytest.mark.asyncio
async def test_owner_version_and_look_are_bound_before_upload(tmp_path):
    service, cid, request = setup(tmp_path)
    upstream = Upload()
    upstream.owner = '2'
    with pytest.raises(StylistError):
        await service.save(upstream, cid, request)
    for owner, version, index in [('2', 1, 0), ('1', 2, 0), ('1', 1, 1)]:
        with pytest.raises(StylistError):
            service.get(owner, cid, version, index, 'female')
    assert upstream.calls == 0


@pytest.mark.asyncio
async def test_concurrent_saves_dispatch_once_and_download_reads_the_saved_oss_bytes(tmp_path):
    service, cid, request = setup(tmp_path)
    upstream = Upload()
    results = await asyncio.gather(service.save(upstream, cid, request), service.save(upstream, cid, request), return_exceptions=True)
    assert upstream.calls == 1
    assert sum(isinstance(r, dict) for r in results) == 1
    saved = service.get('1', cid, 1, 0, 'female')
    def handler(req):
        assert str(req.url) == saved['image_url']
        assert 'authorization' not in req.headers
        return httpx.Response(200, content=png(), headers={'Content-Type': 'image/png'})
    assert await service.download('1', cid, 1, 0, 'female', httpx.MockTransport(handler)) == png()


@pytest.mark.asyncio
async def test_upload_failure_never_becomes_a_ready_image_or_retries_automatically(tmp_path):
    service, cid, request = setup(tmp_path)
    upstream = Upload()
    upstream.fail = True
    with pytest.raises(StylistError):
        await service.save(upstream, cid, request)
    assert service.get('1', cid, 1, 0, 'female')['status'] == 'failed'
    upstream.fail = False
    with pytest.raises(StylistError):
        await service.save(upstream, cid, request)
    assert upstream.calls == 1
    result = await service.save(upstream, cid, request.model_copy(update={'retry': True}))
    assert result['status'] == 'completed'
    assert upstream.calls == 2


def test_png_validation_rejects_wrong_data_size_corruption_and_non_png():
    image = png()
    assert validate_png('data:image/png;base64,'+base64.b64encode(image).decode()) == image
    for value in ['data:image/svg+xml;base64,AAAA', 'data:image/png;base64,!!!!',
                  'data:image/png;base64,'+base64.b64encode(image[:-8]).decode(),
                  'data:image/png;base64,'+base64.b64encode(image+b'extra').decode()]:
        with pytest.raises(StylistError):
            validate_png(value)


@pytest.mark.asyncio
async def test_upload_uses_existing_server_http_api_without_product_or_tryon_calls():
    calls = []
    def handle(request):
        calls.append(request.url.path)
        assert request.method == 'POST'
        assert request.headers['Authorization'] == 'Bearer owned-test'
        assert json.loads(request.content) == {'upload_type': 'web', 'image_url': 'data:image/png;base64,test'}
        return httpx.Response(200, json={'code': 0, 'data': {'url': 'https://aicloset-domestic.aidacloset.com/final.png'}})
    upstream = Upstream(Settings(server_url='https://server.invalid'), 'Bearer owned-test', httpx.MockTransport(handle))
    assert (await upstream.upload_outfit_image('data:image/png;base64,test'))['url'].endswith('/final.png')
    assert calls == ['/api/upload/base64/image']
