from contextlib import asynccontextmanager
import pytest
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import ChatRequest, Plan
from stylist.saved_outfit_search import SavedSelection
from stylist.store import Store
from stylist.errors import StylistError


class Library:
    def __init__(self, empty=False, broken=False):
        self.calls=[]; self.empty=empty; self.broken=broken
    async def identity(self): return '1'
    async def get(self,path,params):
        self.calls.append((path,params))
        assert path=='/api/ai_outfit_merge_my_outfit/list'
        if self.broken: raise StylistError('upstream_unavailable','fixture',503)
        return {'list':[] if self.empty else [{'outfit_id':11,'outfit_id_type':2,'title':'原有通勤搭配'},
                                              {'outfit_id':12,'outfit_id_type':1,'title':'其他类型记录'}]}
    @asynccontextmanager
    async def mcp(self): yield self
    async def call(self,name,args):
        self.calls.append((name,args))
        items=[{'source':'user','product_id':'1','title':'白衬衫','class_name':'上衣','color':'白色'},
               {'source':'user','product_id':'2','title':'长裤','class_name':'裤子','color':'灰色'}]
        if name=='outfit.resolve':return {'source':'user','outfit_id':args['outfit_id'],'title':'原有通勤搭配','items':items}
        assert name=='product.resolve'
        return {'items':items}


class Model:
    def __init__(self):self.calls=[]
    async def generate(self,name,payload,result_type):
        self.calls.append(name)
        if name=='plan':return Plan(mode='consult',conversation_only=True,saved_outfit_search=True,
            saved_outfit_search_evidence=payload['message'],random_selection=True,recall_outfit_numbers=[1])
        assert name=='saved_outfit_search', 'Do not compose a new outfit'
        assert [c['outfit_id'] for c in payload['candidates']]==[11]
        return SavedSelection(outfit_ids=[11])


@pytest.mark.asyncio
@pytest.mark.parametrize('empty,broken',[(False,False),(True,False),(False,True)])
async def test_saved_library_route_is_independent_of_chat_history(tmp_path,empty,broken):
    model=Model();upstream=Library(empty,broken)
    reply=await Stylist(Settings(),Store(str(tmp_path/'library.db')),model).chat(upstream,ChatRequest(
        message='从我的已有搭配里随机挑一套，不用重新搭',request_id='library-random-001'))
    assert reply.saved_outfit_search
    assert reply.conversation_only
    assert reply.weather is None and not reply.product_results
    if not empty and not broken:
        assert reply.outfit_entry is None
        assert reply.looks[0].title=='原有通勤搭配'
        assert len(reply.looks[0].items)==2
        assert reply.looks[0].items[0].product_id=='1'
        assert reply.message==''
        assert model.calls==['plan','saved_outfit_search']
    else:
        assert reply.looks==[] and reply.message
        assert model.calls==['plan']
    assert all('weather' not in name for name,_ in upstream.calls)


@pytest.mark.asyncio
async def test_saved_library_uses_cursor_and_can_match_beyond_first_page():
    from stylist.saved_outfit_search import search_saved_outfits
    class PagedLibrary(Library):
        async def get(self,path,params):
            self.calls.append((path,dict(params)))
            if params['outfit_id']==0:
                return {'list':[{'outfit_id':i,'outfit_id_type':2,'title':f'搭配{i}'} for i in range(1,11)]}
            assert params=={'outfit_id':10,'outfit_id_type':2}
            return {'list':[{'outfit_id':11,'outfit_id_type':2,'title':'第二页搭配'}]}
    class Selector:
        async def generate(self,name,payload,result_type):
            assert name=='saved_outfit_search'
            assert len(payload['candidates'])==11
            return SavedSelection(outfit_ids=[11])
    upstream=PagedLibrary()
    looks,refs,entries,partial=await search_saved_outfits(upstream,Selector(),'从我的已有搭配里找一套')
    assert refs[0].outfit_id==11 and len(looks)==len(entries)==1 and not partial
    assert len([x for x in upstream.calls if x[0].startswith('/api/')])==2


@pytest.mark.asyncio
async def test_another_saved_outfit_excludes_previous_reference_and_passes_context():
    import json
    from stylist.saved_outfit_search import search_saved_outfits
    history=[{'role':'user','content':'从已有搭配随机挑一套'}, {'role':'assistant','content':json.dumps({'saved_outfit_search':True,'subject_outfit':{'source':'user','outfit_id':11}})}]
    class Two(Library):
        async def get(self,path,params):
            return {'list':[{'outfit_id':key,'outfit_id_type':2} for key in [11,13]]}
    class Selector:
        async def generate(self,name,payload,result_type):
            assert payload['history']==history
            return SavedSelection(outfit_ids=[11,13])
    _,refs,_,_=await search_saved_outfits(Two(),Selector(),'换一套',history=history,exclude_previous=True)
    assert [ref.outfit_id for ref in refs]==[13]


@pytest.mark.asyncio
@pytest.mark.parametrize('message',['随便帮我找一套搭配','找下我衣橱里面的搭配'])
async def test_library_source_intent_wins_over_old_generation_and_history_flags(tmp_path,message):
    class SourceModel(Model):
        async def generate(self,name,payload,result_type):
            if name=='plan':
                self.calls.append(name)
                return Plan(mode='recommend',use_inventory=True,outfit_request_kind='saved_library',
                    outfit_request_evidence=payload['message'],saved_outfit_search=False,
                    recall_outfit_numbers=[1],recall_evidence=payload['message'])
            return await super().generate(name,payload,result_type)
    model=SourceModel();upstream=Library()
    reply=await Stylist(Settings(),Store(str(tmp_path/'source-intent.db')),model).chat(upstream,
        ChatRequest(message=message,request_id='library-source-intent'))
    assert reply.saved_outfit_search and reply.subject_outfit.outfit_id==11
    assert not reply.historical_outfit_replay and len(reply.looks)==1
    assert model.calls==['plan','saved_outfit_search']


def test_real_library_list_shape_exposes_scene_and_canvas_attributes_without_images():
    import json
    from stylist.saved_outfit_search import candidate_metadata
    row={'outfit_id':11,'outfit_id_type':2,'occasion_text':'通勤',
         'canvas_info':json.dumps({'canvas_data':{'product_list':[{'class_name':'上衣','color_name':'白色',
                                                                 'cutout_image':'https://private.invalid/photo.png'}]}})}
    data=candidate_metadata(11,row)
    assert data['occasion']=='通勤'
    assert data['products']==[{'class_name':'上衣','color_name':'白色'}]
    assert 'private.invalid' not in json.dumps(data)


@pytest.mark.asyncio
async def test_saved_outfit_with_cover_uses_single_detail_card(tmp_path):
    class Covered(Library):
        async def call(self,name,args):
            result=await super().call(name,args)
            if name=='outfit.resolve':result['presentation']={'canvas_image':'https://images.invalid/saved.png'}
            return result
    reply=await Stylist(Settings(),Store(str(tmp_path/'cover.db')),Model()).chat(Covered(),
        ChatRequest(message='从我的搭配随机找一套',request_id='library-covered-card'))
    assert reply.outfit_entry['presentation']['canvas_image']=='https://images.invalid/saved.png'
    assert reply.looks==[] and reply.message==''


@pytest.mark.asyncio
async def test_single_skirt_is_not_recommended_as_an_entire_outfit(tmp_path):
    class Skirt(Library):
        async def call(self,name,args):
            result=await super().call(name,args)
            assert name=='outfit.resolve', 'A single skirt must be rejected before further processing'
            result['items']=[{'source':'user','product_id':'9','title':'棕色半身裙','class_name':'裙子','secondary_class_name':'半身裙'}]
            return result
    model=Model()
    reply=await Stylist(Settings(),Store(str(tmp_path/'skirt.db')),model).chat(Skirt(),
        ChatRequest(message='从我的搭配随便找一套',request_id='library-single-skirt'))
    assert reply.outfit_entry is None and reply.looks==[]
    assert '没有找到' in reply.message
    assert model.calls==['plan','saved_outfit_search']


@pytest.mark.asyncio
async def test_missing_cover_falls_back_to_original_products_and_composition_context(tmp_path):
    from stylist.composition import Compositions
    store=Store(str(tmp_path/'no-cover.db'))
    reply=await Stylist(Settings(),store,Model()).chat(Library(),
        ChatRequest(message='随机找一套已有搭配',request_id='library-no-cover'))
    assert reply.outfit_entry is None and len(reply.looks)==1
    assert [p.product_id for p in reply.looks[0].items]==['1','2']
    assert reply.delivery=='outfit' and not reply.message
    from stylist.images import ImageService
    assert ImageService(store).context('1',reply.conversation_id,reply.version).subject_outfit_id == 11
    assert Compositions(store).get('1',reply.conversation_id,reply.version,0,'female')['status']=='missing'
