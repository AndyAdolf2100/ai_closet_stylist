"""Disabling the catalog must hold beyond the removed UI selector."""
import pytest

from scripts.dialogue_validation import PRODUCTS, DialogueUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import Change, ChatRequest, Draft, LookDraft, Plan, Product, Reply, Slot, Task
from stylist.retrieval import retrieve
from stylist.store import Store
from stylist.upstream import check_integrations


@pytest.mark.parametrize('persona', ['male_calm_v1', 'female_warm_v1'])
@pytest.mark.parametrize('text_only,chat_only', [(False, False), (True, False), (False, True)])
@pytest.mark.asyncio
async def test_clothing_preferences_used_as_outfit_conditions_return_personal_items_and_images(
        tmp_path, persona, text_only, chat_only):
    class Model:
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                # Reproduce the saved local plan: clothing conditions, but consult/no inventory.
                return Plan(mode='consult', use_inventory=False, conversation_only=chat_only, changes={
                    'preferences': Change(value=['喜欢穿短袖', '喜欢穿衬衫'], evidence=['我喜欢穿短袖', '衬衫']),
                    'excluded_colors': Change(value=['黄色', '绿色'], evidence=['不喜欢黄色', '绿色'])})
            return Draft(message='按你的衣物和颜色要求来安排。', looks=[LookDraft(title='衬衫日常穿搭',
                selected_keys=['user:101', 'user:102', 'user:103'] if payload['candidates'] else [],
                pieces=['衬衫', '长裤', '平底鞋'], why=['白灰配色'], how=['按体感调整层次'])])

    upstream = DialogueUpstream('wardrobe_only')
    upstream.products = [{**p, 'original_image': 'https://example.invalid/wardrobe-test.jpg'} for p in PRODUCTS]
    message = '我喜欢穿短袖，衬衫，不喜欢黄色、绿色'
    if text_only:
        message += '，只给文字穿法，不查衣橱。'
    store = Store(str(tmp_path / 'preferences-outfit.db'))
    reply = await Stylist(Settings(), store, Model()).chat(upstream, ChatRequest(
        message=message, request_id='preferences-outfit-photo', assistant_persona=persona))
    if text_only or chat_only:
        assert '/api/user_product/quick_edit_list' not in upstream.calls
        assert not any(look.items for look in reply.looks)
        if chat_only:
            assert not reply.looks
    else:
        assert '/api/user_product/quick_edit_list' in upstream.calls
        assert reply.mode == 'recommend' and reply.delivery == 'outfit'
        assert reply.task.excluded_colors == ['黄色', '绿色']
        assert all(item.source == 'user' and item.original_image for look in reply.looks for item in look.items)
        assert any(look.items for look in reply.looks)
        assert store.memory_book(await upstream.identity()).entries[0].content == '我喜欢穿短袖，衬衫；不喜欢黄色、绿色'


@pytest.mark.parametrize("source", ["catalog", "hybrid"])
@pytest.mark.parametrize("origin", ["request", "history", "model"])
@pytest.mark.asyncio
async def test_catalog_selection_from_legacy_request_history_or_model_uses_personal_clothes(tmp_path, source, origin):
    class Model:
        async def generate(self, name, payload, result_type):
            if name == "plan":
                return Plan(mode="recommend", changes={"source": Change(value=source, evidence="系统衣橱")}
                            if origin == "model" else {})
            assert payload["task"]["source"] == "wardrobe"
            return Draft(message="从个人衣橱选好了。", looks=[LookDraft(title="日常穿搭",
                selected_keys=["user:101", "user:102", "user:103"], why=["配色简洁"], how=["按体感穿脱"])])

    store = Store(str(tmp_path / "state.db"))
    upstream = DialogueUpstream("wardrobe_only")
    previous = None
    if origin == "history":
        initial = ChatRequest(message="旧任务", request_id="wardrobe-only-history")
        cid, claim, state, _ = store.reserve(await upstream.identity(), initial)
        state.task = Task(source=source)
        previous = Reply(conversation_id=cid, version=1, mode="consult", delivery="advice",
                         message="旧范围", task=state.task)
        store.finish(await upstream.identity(), initial, claim, state, previous)
    result = await Stylist(Settings(), store, Model()).chat(upstream, ChatRequest(
        message="从系统衣橱搭一套，不考虑天气", request_id="wardrobe-only-current",
        source=source if origin == "request" else None,
        conversation_id=previous.conversation_id if previous else None,
        expected_version=previous.version if previous else 0))
    assert result.task.source == "wardrobe" and result.delivery == "outfit"
    assert all(item.source == "user" for look in result.looks for item in look.items)
    assert "/api/user_product/quick_edit_list" in upstream.calls
    assert not {"/api/product/list", "kb_search"}.intersection(upstream.calls)


@pytest.mark.asyncio
async def test_service_checks_do_not_read_system_catalog_or_public_search():
    class Upstream(DialogueUpstream):
        async def get(self, path, params=None):
            if path == "/api/memories":
                return {}
            return await super().get(path, params)

        async def discover(self):
            return {}

        async def call(self, name, args):
            if name == "product.resolve":
                assert all(item["source"] == "user" for item in args["items"])
            if name == "kb_search":
                assert args["scope"] == "user"
                return {"list": []}
            if name in {"digital_twin_overview", "digital_twin_tryon_quote"}:
                return {}
            return await super().call(name, args)

    upstream = Upstream("wardrobe_only")
    results = await check_integrations(upstream)
    assert all(row["status"] in {"ok", "blocked", "not_published"} for row in results)
    assert "/api/product/list" not in upstream.calls
    assert not any(row["interface"] in {"GET /api/product/list", "kb_search:public"} for row in results)


@pytest.mark.parametrize("source", ["wardrobe", "catalog", "hybrid"])
@pytest.mark.asyncio
async def test_retrieval_does_not_resolve_system_items_even_from_old_frozen_selections(source):
    class Upstream(DialogueUpstream):
        async def call(self, name, args):
            if name == "product.resolve":
                assert all(item["source"] == "user" for item in args["items"])
            return await super().call(name, args)

    upstream = Upstream("wardrobe_only")
    old_system_item = Product(source="system", product_id="999", slot=Slot.TOP)
    pool, _, _ = await retrieve(upstream, upstream, Task(source=source, gender="女"), "日常", [old_system_item])
    assert set(pool) == {f"user:{row['product_id']}" for row in PRODUCTS}
    assert not {"/api/product/list", "kb_search"}.intersection(upstream.calls)
