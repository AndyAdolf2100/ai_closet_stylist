from contextlib import asynccontextmanager
import pytest
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import ChatRequest,Plan,Look,Product,Reply,Task
from stylist.store import Store


@pytest.mark.asyncio
@pytest.mark.parametrize('kind,message,location',[
    ('product','帮我删除衣橱这件白衬衫','单品详情'),
    ('outfit','把刚才保存的那套搭配删掉','我的搭配'),
    ('both','帮我删除这个单品和这套搭配','我的搭配'),
    ('product','Delete this item from my wardrobe','衣橱'),
])
async def test_deletion_returns_manual_guidance_without_tools_or_changes(tmp_path,kind,message,location):
    class Upstream:
        async def identity(self):return '1'
        async def get(self,*args):raise AssertionError('Deletion guidance is not a lookup')
        @asynccontextmanager
        async def mcp(self):
            raise AssertionError('No deletion, inventory, weather or image operations')
            yield
    class Model:
        def __init__(self):self.calls=[]
        async def generate(self,name,payload,result_type):
            self.calls.append(name);assert name=='plan'
            return Plan(mode='recommend',use_inventory=True,product_search=True,
                        wardrobe_delete_intent=kind,wardrobe_delete_evidence=payload['message'])
    store=Store(str(tmp_path/'delete.db'));seed=ChatRequest(message='已生成搭配',request_id='seed-deletion-guidance')
    cid,claim,state,_=store.reserve('1',seed)
    state.task=Task(scene='通勤');state.looks=[Look(title='原搭配',items=[Product(source='user',product_id='1',slot='top')])]
    store.finish('1',seed,claim,state,Reply(conversation_id=cid,version=1,mode='recommend',delivery='outfit',message='原搭配',task=state.task,looks=state.looks))
    original=state.model_dump();model=Model()
    reply=await Stylist(Settings(),store,model).chat(Upstream(),ChatRequest(message=message,request_id='delete-guidance-001',conversation_id=cid,expected_version=1))
    assert '不能直接删除' in reply.message and location in reply.message and '手动删除' in reply.message
    assert reply.delivery=='advice' and reply.conversation_only and reply.follow_ups==[]
    assert reply.looks==[] and reply.weather is None and not reply.pending_confirmation
    assert model.calls==['plan']
    with store.connection() as conn:
        import json
        saved=json.loads(conn.execute('SELECT state_json FROM stylist_sessions WHERE id=?',(cid,)).fetchone()['state_json'])
    assert saved['looks']==original['looks'] and saved['task']==original['task']


class NoBusiness:
    def __init__(self,owner='1'):self.owner=owner
    async def identity(self):return self.owner
    async def get(self,*args):raise AssertionError('No inventory operations')
    @asynccontextmanager
    async def mcp(self):
        raise AssertionError('No tool operations')
        yield


class DeleteModel:
    def __init__(self,scope='user'):
        self.scope=scope;self.calls=[];self.fail=False
    async def generate(self,name,payload,result_type):
        self.calls.append(name)
        assert name=='plan'
        if self.fail:
            from stylist.errors import StylistError
            raise StylistError('model_timeout','synthetic timeout',503)
        return Plan(mode='recommend',use_inventory=True,saved_outfit_search=True,
                    saved_outfit_search_evidence=payload['message'],recall_outfit_numbers=[1],
                    recall_evidence=payload['message'],wardrobe_delete_intent='product',
                    wardrobe_delete_scope=self.scope,wardrobe_delete_evidence=payload['message'])


def existing_context(tmp_path):
    store=Store(str(tmp_path/'context.db'))
    request=ChatRequest(message='原有搭配',request_id='existing-delete-context')
    cid,claim,state,_=store.reserve('1',request)
    state.looks=[Look(title='原搭配',items=[Product(source='user',product_id='1',slot='top')])]
    state.task=Task(scene='通勤',preferences=['不塞衣角'])
    store.finish('1',request,claim,state,Reply(conversation_id=cid,version=1,mode='recommend',delivery='outfit',message='原搭配',task=state.task,looks=state.looks))
    return store,cid


@pytest.mark.asyncio
@pytest.mark.parametrize('scope,expected',[('user','单品详情'),('system','不能删除系统参考内容'),('other','不能删除其他用户')])
async def test_guidance_scope_overrides_conflicting_lookup_flags_and_replays_once(tmp_path,scope,expected):
    store,cid=existing_context(tmp_path);model=DeleteModel(scope)
    engine=Stylist(Settings(),store,model)
    request=ChatRequest(message='帮我删掉这件',request_id='delete-scope-replay',conversation_id=cid,expected_version=1)
    first=await engine.chat(NoBusiness(),request)
    second=await engine.chat(NoBusiness(),request)
    assert first==second and model.calls==['plan']
    assert expected in first.message and not first.looks
    assert not first.product_search and not first.saved_outfit_search
    assert not first.pending_confirmation
    assert len(store.history('1',cid)['messages'])==2


@pytest.mark.asyncio
@pytest.mark.parametrize('owner,version',[('other',1),('1',0)])
async def test_delete_guidance_does_not_bypass_account_or_version_checks(tmp_path,owner,version):
    from stylist.errors import StylistError
    store,cid=existing_context(tmp_path);model=DeleteModel()
    with pytest.raises(StylistError):
        await Stylist(Settings(),store,model).chat(NoBusiness(owner),ChatRequest(
            message='帮我删掉这件',request_id='delete-account-version',conversation_id=cid,expected_version=version))
    assert model.calls==[]
    assert len(store.history('1',cid)['messages'])==1


@pytest.mark.asyncio
async def test_model_failure_does_not_claim_deletion_or_change_original_outfit(tmp_path):
    from stylist.errors import StylistError
    store,cid=existing_context(tmp_path);model=DeleteModel();model.fail=True
    with pytest.raises(StylistError):
        await Stylist(Settings(),store,model).chat(NoBusiness(),ChatRequest(
            message='帮我删掉这件',request_id='delete-guidance-failure',conversation_id=cid,expected_version=1))
    history=store.history('1',cid)
    assert len(history['messages'])==1
    assert history['messages'][0]['reply']['looks'][0]['items'][0]['product_id']=='1'
