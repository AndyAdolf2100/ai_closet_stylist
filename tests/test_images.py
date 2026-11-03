import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from stylist.errors import StylistError
from stylist.images import ImageQuoteRequest, ImageService
from stylist.models import ChatRequest, Look, Product, Reply, Slot, Task
from stylist.store import Store


class ImageUpstream:
    def __init__(self):
        self.cost, self.commits, self.fail = 2, [], False
    async def identity(self):
        return "1"
    @asynccontextmanager
    async def mcp(self, **kwargs):
        yield self
    async def discover(self):
        return {name: SimpleNamespace(model_dump=lambda **kw: {"schema": "stable"}) for name in
                ["save_recommended_outfit", "digital_twin_tryon"]}
    async def call(self, name, args):
        await asyncio.sleep(0)
        if name == "digital_twin_tryon_quote":
            return {"points_cost": self.cost}
        if name == "digital_twin_overview":
            return {"default_twin_key": "preset-1", "default_confirmed": True, "selection_version": 1}
        if name == "product.resolve":
            return {"items": [{**ref, "class_name": {"1": "上衣", "2": "裤子", "3": "鞋子"}[ref["product_id"]]} for ref in args["items"]]}
        pytest.fail(name)
    async def commit_image(self, name, args):
        self.commits.append(name)
        await asyncio.sleep(0)
        if name == "save_recommended_outfit":
            # Server's PrepareTryOnOutfit accepts only ^sel_[A-Za-z0-9_-]{8,64}$.
            assert args['selection_id'].startswith('sel_') and len(args['selection_id']) == 36
            return {"outfit_id": 12, "status": "completed"}
        if self.fail:
            raise StylistError("mcp_unavailable", "timeout")
        return {"status": "completed", "result_image": "https://example.test/tryon.jpg"}


def setup_service(tmp_path):
    store = Store(str(tmp_path / "state.db"))
    request = ChatRequest(message="通勤", request_id="image-test-seed")
    cid, claim, state, _ = store.reserve("1", request)
    products = [Product(source="user", product_id=str(i), slot=slot) for i, slot in [(1, Slot.TOP), (2, Slot.BOTTOM), (3, Slot.SHOES)]]
    state.looks = [Look(title="通勤装", items=products)]
    store.finish("1", request, claim, state, Reply(conversation_id=cid, version=1, mode="recommend",
                 delivery="outfit", message="搭配", task=Task(), looks=state.looks))
    return ImageService(store), ImageQuoteRequest(conversation_id=cid, version=1), ImageUpstream()


@pytest.mark.asyncio
async def test_quote_and_cancel_do_not_dispatch_or_charge(tmp_path):
    service, request, upstream = setup_service(tmp_path)
    quote = await service.quote(upstream, request)
    assert upstream.commits == [] and quote["points_cost"] == 2
    result = await service.confirm(upstream, quote["action_id"], False)
    assert result["status"] == "cancelled" and upstream.commits == []


async def test_quote_includes_selected_custom_portrait_without_requiring_redundant_key(tmp_path):
    service,request,upstream=setup_service(tmp_path)
    original=upstream.call
    async def call(name,args):
        if name=='digital_twin_overview':
            return {'default_twin_key':'custom','default_confirmed':True,'selection_version':3,
                    'custom_twin':{'image_url':'https://example.test/my-avatar.png'}}
        return await original(name,args)
    upstream.call=call
    quote=await service.quote(upstream,request)
    assert quote['portrait']['twin_key']=='custom'
    assert quote['portrait']['image_url'].endswith('my-avatar.png')
    assert not upstream.commits


@pytest.mark.asyncio
async def test_changed_price_requires_new_confirmation(tmp_path):
    service, request, upstream = setup_service(tmp_path)
    quote = await service.quote(upstream, request)
    upstream.cost = 3
    with pytest.raises(StylistError, match="image_quote_changed"):
        await service.confirm(upstream, quote["action_id"], True)
    assert upstream.commits == []


@pytest.mark.asyncio
async def test_concurrent_confirmation_dispatches_once(tmp_path):
    service, request, upstream = setup_service(tmp_path)
    quote = await service.quote(upstream, request)
    results = await asyncio.gather(*(service.confirm(upstream, quote["action_id"], True) for _ in range(3)), return_exceptions=True)
    assert any(isinstance(r, dict) and r["status"] == "completed" for r in results)
    assert upstream.commits.count("digital_twin_tryon") == 1
    assert upstream.commits.count("save_recommended_outfit") == 1
    assert (await service.confirm(upstream, quote["action_id"], True))["status"] == "completed"
    assert len(upstream.commits) == 2


@pytest.mark.asyncio
async def test_uncertain_dispatch_is_not_automatically_retried(tmp_path):
    service, request, upstream = setup_service(tmp_path)
    quote = await service.quote(upstream, request)
    upstream.fail = True
    with pytest.raises(StylistError, match="image_result_unknown"):
        await service.confirm(upstream, quote["action_id"], True)
    assert service.status("1", quote["action_id"])["status"] == "unknown"
    with pytest.raises(StylistError, match="image_already_submitted"):
        await service.confirm(upstream, quote["action_id"], True)
    assert len(upstream.commits) == 2
    with pytest.raises(StylistError, match="image_action_not_found"):
        service.status("2", quote["action_id"])


@pytest.mark.asyncio
async def test_tryon_reconciliation_reads_original_request_without_charge_or_replay(tmp_path):
    service, request, upstream = setup_service(tmp_path)
    q = await service.quote(upstream, request)
    upstream.fail = True
    with pytest.raises(StylistError):
        await service.confirm(upstream, q['action_id'], True)
    previous = upstream.call
    async def read(name, args):
        if name == 'digital_twin_tryon_status':
            assert args['client_request_id'] == q['action_id']
            return {'status': 'completed', 'result_image_url': 'https://example.test/reconciled.png',
                    'cost_points': 2, 'charged': True, 'refunded': False}
        return await previous(name, args)
    upstream.call = read
    result = await service.refresh(upstream, q['action_id'])
    assert result['status'] == 'completed' and result['result']['charged'] is True
    assert len(upstream.commits) == 2
    assert len(service.list('1', request.conversation_id)) == 1
    assert service.list('2', request.conversation_id) == []
    service.mark('1', q['action_id'], 'failed', {'charged': True, 'refunded': False})
    async def refund_status(name, args):
        assert name == 'digital_twin_tryon_status'
        return {'status': 'failed', 'charged': True, 'refunded': True, 'cost_points': 2}
    upstream.call = refund_status
    assert (await service.refresh(upstream, q['action_id']))['result']['refunded'] is True
    assert len(upstream.commits) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('cached_status', ['unknown', 'completed'])
async def test_reconciliation_accepts_legacy_result_image_without_replaying_paid_generation(tmp_path, cached_status):
    service, request, upstream = setup_service(tmp_path)
    quote = await service.quote(upstream, request)
    service.mark('1', quote['action_id'], cached_status, {})
    async def legacy_status(name, args):
        assert name == 'digital_twin_tryon_status'
        assert args == {'client_request_id': quote['action_id']}
        return {'status': 'completed', 'result_image': 'https://example.test/legacy.png'}
    upstream.call = legacy_status
    result = await service.refresh(upstream, quote['action_id'])
    assert result['status'] == 'completed'
    assert result['result']['result_image'] == 'https://example.test/legacy.png'
    assert upstream.commits == []


@pytest.mark.asyncio
async def test_success_without_image_is_processing_and_points_rejection_is_not_unknown(tmp_path):
    service, request, upstream = setup_service(tmp_path)
    q = await service.quote(upstream, request)
    async def no_image(name, args):
        return {'outfit_id': 12} if name == 'save_recommended_outfit' else {'status': 'processing'}
    upstream.commit_image = no_image
    assert (await service.confirm(upstream, q['action_id'], True))['status'] == 'processing'
    q = await service.quote(upstream, request)
    async def no_points(name, args):
        if name == 'save_recommended_outfit':
            return {'outfit_id': 12}
        raise StylistError('tryon_points_insufficient', '积分不足')
    upstream.commit_image = no_points
    with pytest.raises(StylistError, match='tryon_points_insufficient'):
        await service.confirm(upstream, q['action_id'], True)
    result = service.status('1', q['action_id'])
    assert result['status'] == 'failed' and result['result']['charged'] is False


async def test_history_exposes_original_creation_time_for_cross_kind_sorting(tmp_path):
    service, request, upstream = setup_service(tmp_path)
    quote = await service.quote(upstream, request)
    original = service.get('1', quote['action_id'])['created_at']
    assert original
    assert service.list('1')[0]['created_at'] == original
    await service.confirm(upstream, quote['action_id'], False)
    assert service.list('1')[0]['created_at'] == original
    assert service.list('2') == []
    assert upstream.commits == []
