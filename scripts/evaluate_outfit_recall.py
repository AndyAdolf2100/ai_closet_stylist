"""Live text evaluation; run python -m scripts.evaluate_outfit_recall --live explicitly."""
import asyncio,json,os,tempfile,shlex,time
from pathlib import Path
from contextlib import asynccontextmanager
from stylist.config import Settings
from stylist.llm import LanguageModel
from stylist.engine import Stylist
from stylist.store import Store
from stylist.models import ChatRequest,Reply,Task,Look
class Upstream:
 async def identity(self):return 'recall-fixture'
 async def get(self,*args):raise AssertionError('Unexpected inventory read')
 @asynccontextmanager
 async def mcp(self):
  raise AssertionError('Unexpected business tool')
  yield
class Model(LanguageModel):
 def __init__(self,s):super().__init__(s);self.calls=[]
 async def generate(self,name,payload,result_type):
  self.calls.append(name)
  if name!='plan':raise AssertionError('Unexpected generation instead of recall')
  value=await super().generate(name,payload,result_type)
  self.last=value.model_dump(mode='json')
  return value
async def main():
 for line in Path('config/deploy.env').read_text().splitlines():
  if '=' in line and not line.lstrip().startswith('#'):
   key,value=line.split('=',1)
   if key in {'STYLIST_LLM_URL','STYLIST_LLM_MODEL','STYLIST_LLM_KEY'}:
    values=shlex.split(value);os.environ[key]=values[0] if values else ''
 s=Settings.load();assert s.llm_key and s.llm_model
 from scripts.outfit_recall_dialogues import CASES
 cases=CASES
 results=[]
 with tempfile.TemporaryDirectory() as tmp:
  for n,(message,expected) in enumerate(cases):
   store=Store(str(Path(tmp)/f'{n}.sqlite'));request=ChatRequest(message='忽略天气，给我生成5套搭配',request_id='initial-outfits');cid,claim,state,_=store.reserve('recall-fixture',request)
   state.looks=[Look(title=f'第{i}套：'+title,pieces=[title],how=['按原方案搭配']) for i,title in enumerate(['白衬衫与牛仔裤','灰针织衫与长裤','黑西装与直筒裤','蓝衬衫与卡其裤','米色外套与黑裤'],1)]
   store.finish('recall-fixture',request,claim,state,Reply(conversation_id=cid,version=1,mode='recommend',delivery='outfit',message='这五套搭配供你选。',task=Task(weather_policy='ignored'),looks=state.looks))
   model=Model(s);start=time.monotonic()
   try:
    reply=await Stylist(s,store,model).chat(Upstream(),ChatRequest(message=message,request_id=f'recall-test-{n}',conversation_id=cid,expected_version=1))
    actual=[int(x.title[1]) for x in reply.looks];passed=actual==expected and reply.historical_outfit_replay and not reply.message and model.calls==['plan']
    row={'message':message,'expected':expected,'actual':actual,'passed':passed,'message_text':reply.message,'model_calls':model.calls,'plan':model.last}
   except Exception as e:row={'message':message,'expected':expected,'passed':False,'error':type(e).__name__,'model_calls':model.calls,'plan':getattr(model,'last',None)}
   row['seconds']=round(time.monotonic()-start,2);results.append(row);print(json.dumps({k:v for k,v in row.items() if k!='plan'},ensure_ascii=False),flush=True)
   out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'kind':'real_text_model_synthetic_saved_five_outfits','model':s.llm_model,'generated_initial_outfits':False,'results':results},ensure_ascii=False,indent=2))
if __name__ == '__main__':
 import argparse
 parser=argparse.ArgumentParser(description='Explicit paid text model recall check; five saved outfits are synthetic fixtures.')
 parser.add_argument('--live', action='store_true', required=True, help='Authorize real text model calls; no image generation')
 parser.add_argument('--output', default='var/dialogue-qa/outfit-recall-live.json')
 args=parser.parse_args()
 asyncio.run(main())
