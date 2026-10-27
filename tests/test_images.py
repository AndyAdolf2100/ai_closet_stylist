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
