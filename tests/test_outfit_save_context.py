import pytest
from stylist.store import Store
from stylist.models import ChatRequest, Reply, Look, Product, Task
from stylist.outfit_save import OutfitSaves
from stylist.errors import StylistError


@pytest.mark.parametrize('delivery,pending,product_entry,allowed', [
    ('outfit', False, None, True), ('advice', False, None, True),
    ('clarification', False, None, False), ('concept', False, None, False),
    ('outfit', True, None, False), ('advice', False, {'title': '单品'}, False),
])
def test_save_checks_actual_snapshot_without_relaxing_pending_or_product_entry(tmp_path, delivery, pending, product_entry, allowed):
    store=Store(str(tmp_path/'save.db'))
    request=ChatRequest(message='模拟搭配',request_id='seed-save-context')
    cid,claim,state,_=store.reserve('1',request)
    state.looks=[Look(title='已有实际搭配',items=[Product(source='user',product_id='1',slot='top')])]
    store.finish('1',request,claim,state,Reply(conversation_id=cid,version=1,mode='consult',delivery=delivery,
        message='模拟',task=Task(),looks=state.looks,pending_confirmation=pending,product_entry=product_entry))
    saves=OutfitSaves(store)
    if allowed:
        assert saves.context('1',cid,1,0)[1].items[0].product_id=='1'
        assert saves.get('1',cid,1,0)=={'status':'missing'}
    else:
        with pytest.raises(StylistError):saves.context('1',cid,1,0)
    with pytest.raises(StylistError):saves.context('other',cid,1,0)


@pytest.mark.parametrize('delivery,pending,product_entry,index,expected', [
    ('concept', False, None, 0, '这条消息仍属于穿搭参考，暂不支持保存。请让助理生成一套搭配后再保存。'),
    ('clarification', False, None, 0, '这条消息还在沟通搭配需求，尚未生成搭配结果。请先完成搭配，再保存穿搭。'),
    ('outfit', True, None, 0, '这次搭配还在等待确认，暂时无法保存。请先完成确认，再保存穿搭。'),
    ('outfit', False, None, 1, '这条消息里没有找到你选中的那套搭配。请重新打开对应卡片后再保存。'),
    ('outfit', False, None, -1, '这条消息里没有找到你选中的那套搭配。请重新打开对应卡片后再保存。'),
    ('advice', False, {'title': '单品'}, 0, '这张卡片是单品，不是一套搭配，暂时不能保存。先用它搭一套，再保存吧。'),
])
def test_save_unavailable_reason_is_clear_warm_and_preserves_error_contract(tmp_path, delivery, pending, product_entry, index, expected):
    store=Store(str(tmp_path/'messages.db'))
    request=ChatRequest(message='模拟保存提示',request_id='save-notice')
    cid,claim,state,_=store.reserve('1',request)
    state.looks=[Look(title='示例',items=[Product(source='user',product_id='1',slot='top')])]
    store.finish('1',request,claim,state,Reply(conversation_id=cid,version=1,mode='consult',delivery=delivery,
        message='模拟',task=Task(),looks=state.looks,pending_confirmation=pending,product_entry=product_entry))
    with pytest.raises(StylistError) as error:
        OutfitSaves(store).context('1',cid,1,index)
    assert error.value.code=='feedback_not_available'
    assert error.value.status==422
    assert error.value.message==expected
    with store.connection() as conn:
        assert conn.execute('SELECT COUNT(*) AS n FROM stylist_outfit_saves').fetchone()['n']==0


def test_feedback_notice_does_not_claim_an_outfit_is_being_saved(tmp_path):
    from stylist.feedback import owned_look
    store=Store(str(tmp_path/'votes.db'))
    request=ChatRequest(message='模拟评价',request_id='vote-notice')
    cid,claim,state,_=store.reserve('1',request)
    state.looks=[Look(title='灵感',items=[Product(source='user',product_id='1',slot='top')])]
    store.finish('1',request,claim,state,Reply(conversation_id=cid,version=1,mode='consult',delivery='concept',
        message='模拟',task=Task(),looks=state.looks))
    with store.connection() as conn, pytest.raises(StylistError) as error:
        owned_look(conn,'1',cid,1,0)
    assert '保存' not in error.value.message
    assert error.value.message=='这条消息仍属于穿搭参考，暂时不能评价。等生成搭配后，再告诉我你的喜欢吧。'


@pytest.mark.parametrize('delivery',['outfit','advice'])
def test_completed_historical_snapshot_keeps_its_original_items(tmp_path,delivery):
    store=Store(str(tmp_path/'historical-save.db'))
    first=ChatRequest(message='第一套',request_id='first-outfit')
    cid,claim,state,_=store.reserve('1',first)
    state.looks=[Look(title='第一套',items=[Product(source='user',product_id='1',slot='top')])]
    store.finish('1',first,claim,state,Reply(conversation_id=cid,version=1,mode='consult',delivery=delivery,
        message='第一套',task=Task(),looks=state.looks))
    second=ChatRequest(message='继续聊',conversation_id=cid,expected_version=1,request_id='next-turn')
    _,claim,state,_=store.reserve('1',second)
    state.looks=[Look(title='第二套',items=[Product(source='user',product_id='2',slot='top')])]
    store.finish('1',second,claim,state,Reply(conversation_id=cid,version=2,mode='consult',delivery='outfit',
        message='第二套',task=Task(),looks=state.looks))
    assert OutfitSaves(store).context('1',cid,1,0)[1].items[0].product_id=='1'


def test_save_http_response_explains_reference_card_reason(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from stylist.config import Settings
    from stylist.main import create_app
    settings=Settings(database=str(tmp_path/'http-notice.db'))
    store=Store(settings.database)
    request=ChatRequest(message='灵感',request_id='concept-notice')
    cid,claim,state,_=store.reserve('1',request)
    state.looks=[Look(title='灵感',items=[Product(source='user',product_id='1',slot='top')])]
    store.finish('1',request,claim,state,Reply(conversation_id=cid,version=1,mode='consult',delivery='concept',
        message='模拟',task=Task(),looks=state.looks))
    async def identity(self):return '1'
    monkeypatch.setattr('stylist.main.Upstream.identity',identity)
    with TestClient(create_app(settings)) as client:
        response=client.post(f'/stylist-api/conversations/{cid}/saved-outfit',
            headers={'Authorization':'Bearer synthetic'},json={'version':1,'look_index':0})
    assert response.status_code==422
    assert response.json()=={'code':'feedback_not_available','message':'这条消息仍属于穿搭参考，暂不支持保存。请让助理生成一套搭配后再保存。'}
