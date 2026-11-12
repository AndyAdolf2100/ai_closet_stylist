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
