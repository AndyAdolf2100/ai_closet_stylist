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
        self.cost, self.commits, self.commit_args, self.saved_outfits, self.fail = 2, [], [], {}, False
    async def get(self, path):
        assert path == '/api/vip_center/points_detail'
        return {'total_available': 10000}

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
        self.commit_args.append((name, args))
        await asyncio.sleep(0)
        if name == "save_recommended_outfit":
            # Server's PrepareTryOnOutfit accepts only ^sel_[A-Za-z0-9_-]{8,64}$.
            assert args['selection_id'].startswith('sel_') and len(args['selection_id']) == 36
            if args["selection_id"] in self.saved_outfits:
                return {"outfit_id": self.saved_outfits[args["selection_id"]], "outfit_created": False,
                        "status": "completed"}
            self.saved_outfits[args["selection_id"]] = 12
            return {"outfit_id": 12, "outfit_created": True, "status": "completed"}
        if self.fail:
            raise StylistError("mcp_unavailable", "timeout")
        return {"status": "completed", "result_image": "https://example.test/tryon.jpg"}


def setup_service(tmp_path, existing_outfit_id=None):
    store = Store(str(tmp_path / "state.db"))
    request = ChatRequest(message="通勤", request_id="image-test-seed")
    cid, claim, state, _ = store.reserve("1", request)
    products = [Product(source="user", product_id=str(i), slot=slot) for i, slot in [(1, Slot.TOP), (2, Slot.BOTTOM), (3, Slot.SHOES)]]
    state.looks = [Look(title="通勤装", items=products)]
    state.subject_outfit_id = existing_outfit_id
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
async def test_repeated_quote_uses_same_saved_outfit_selection(tmp_path):
    service, request, upstream = setup_service(tmp_path)
    first = await service.quote(upstream, request)
    await service.confirm(upstream, first["action_id"], True)
    second = await service.quote(upstream, request)
    await service.confirm(upstream, second["action_id"], True)

    saved = [args for name, args in upstream.commit_args if name == "save_recommended_outfit"]
    tryons = [args for name, args in upstream.commit_args if name == "digital_twin_tryon"]
    assert len(saved) == 2
    assert saved[0]["selection_id"] == saved[1]["selection_id"]
    assert len(upstream.saved_outfits) == 1
    assert len({args["idempotency_key"] for args in tryons}) == 2


@pytest.mark.asyncio
async def test_existing_saved_outfit_tryon_skips_outfit_creation(tmp_path):
    service, request, upstream = setup_service(tmp_path, existing_outfit_id=72)
    quote = await service.quote(upstream, request)
    await service.confirm(upstream, quote["action_id"], True)

    assert upstream.commits == ["digital_twin_tryon"]
    assert upstream.commit_args[0][1]["outfit_id"] == 72


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

@pytest.mark.asyncio
async def test_each_confirm_reads_balance_and_low_or_failed_read_never_dispatches(tmp_path):
    service, request, upstream=setup_service(tmp_path)
    quote=await service.quote(upstream,request)
    values=[{'total_available':1},{}, {'total_available':2}]
    reads=[]
    async def balance(path):
        reads.append(path)
        return values.pop(0)
    upstream.get=balance
    for expected in ['tryon_points_insufficient','points_balance_invalid']:
        with pytest.raises(StylistError,match=expected):
            await service.confirm(upstream,quote['action_id'],True)
        assert not upstream.commits
    await service.confirm(upstream,quote['action_id'],True)
    assert reads==['/api/vip_center/points_detail']*3
    assert upstream.commits==['save_recommended_outfit','digital_twin_tryon']


def advance_dialogue(service, request):
    import json
    with service.store.connection() as conn:
        row=conn.execute('SELECT state_json FROM stylist_sessions WHERE id=?',(request.conversation_id,)).fetchone()
        data=json.loads(row['state_json'])
        data['looks']=[Look(title='后来搭配',items=[Product(source='user',product_id='3',slot='shoes')]).model_dump(mode='json')]
        data['subject_outfit_id']=99
        conn.execute('UPDATE stylist_sessions SET version=version+1,state_json=? WHERE id=?',(json.dumps(data),request.conversation_id))


@pytest.mark.asyncio
async def test_historical_outfit_quote_and_confirm_keep_original_items_after_later_turns(tmp_path):
    service,request,upstream=setup_service(tmp_path)
    advance_dialogue(service,request)
    quote=await service.quote(upstream,request)
    assert quote['item_count']==3 and quote['title']=='通勤装'
    assert upstream.commits==[]
    advance_dialogue(service,request)
    result=await service.confirm(upstream,quote['action_id'],True)
    assert result['status']=='completed'
    saved=next(args for name,args in upstream.commit_args if name=='save_recommended_outfit')
    assert [x['product_id'] for x in saved['items']]==[1,2,3]
    with service.store.connection() as conn:
        row=conn.execute('SELECT version,state_json FROM stylist_sessions WHERE id=?',(request.conversation_id,)).fetchone()
    assert row['version']==3 and __import__('json').loads(row['state_json'])['looks'][0]['title']=='后来搭配'


@pytest.mark.asyncio
async def test_historical_product_without_looks_recovers_only_its_original_item(tmp_path):
    import json
    service,request,upstream=setup_service(tmp_path)
    with service.store.connection() as conn:
        row=conn.execute('SELECT reply_json FROM stylist_messages WHERE conversation_id=?',(request.conversation_id,)).fetchone()
        reply=json.loads(row['reply_json']);reply.update(looks=[],delivery='advice',
            subject_product={'source':'user','product_id':'2'},product_entry={'title':'原长裤','product':{'source':'user','product_id':'2','class_name':'裤子'}})
        conn.execute('UPDATE stylist_messages SET reply_json=? WHERE conversation_id=?',(json.dumps(reply),request.conversation_id))
    advance_dialogue(service,request)
    quote=await service.quote(upstream,request)
    assert quote['item_count']==1 and quote['title']=='原长裤'
    await service.confirm(upstream,quote['action_id'],True)
    assert upstream.commit_args[0][1]['items']==[{'source':'user','product_id':2}]


@pytest.mark.asyncio
@pytest.mark.parametrize('delivery,pending',[('concept',False),('clarification',False),('outfit',True),('advice',False)])
async def test_non_outfit_historical_messages_never_borrow_latest_items(tmp_path,delivery,pending):
    import json
    service,request,upstream=setup_service(tmp_path)
    with service.store.connection() as conn:
        row=conn.execute('SELECT reply_json FROM stylist_messages WHERE conversation_id=?',(request.conversation_id,)).fetchone()
        reply=json.loads(row['reply_json']);reply.update(looks=[],delivery=delivery,pending_confirmation=pending)
        conn.execute('UPDATE stylist_messages SET reply_json=? WHERE conversation_id=?',(json.dumps(reply),request.conversation_id))
    advance_dialogue(service,request)
    with pytest.raises(StylistError,match='no_real_outfit'):
        await service.quote(upstream,request)
    assert upstream.commits==[]


@pytest.mark.asyncio
async def test_historical_quote_revalidates_deleted_item_before_confirmation(tmp_path):
    service,request,upstream=setup_service(tmp_path)
    advance_dialogue(service,request)
    quote=await service.quote(upstream,request)
    original=upstream.call
    async def missing(name,args):
        if name=='product.resolve':return {'items':[]}
        return await original(name,args)
    upstream.call=missing
    with pytest.raises(StylistError):await service.confirm(upstream,quote['action_id'],True)
    assert upstream.commits==[]
