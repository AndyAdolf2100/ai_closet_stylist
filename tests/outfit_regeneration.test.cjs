const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('stylist/static/app.js','utf8');
const sender=source.slice(source.indexOf('async function sendMessage('),source.indexOf('\nfunction showPlanApproval('));
const regenerate=source.slice(source.indexOf('async function regenerateOutfit('),source.indexOf('\nwindow.WardrobeJourney?.configure('));
const action={status:'completed',conversation_id:'sty_'+'1'.repeat(32),version:5,look_index:1};
function setup({ready=Promise.resolve(),wait=null}={}){
 const nodes={message:{value:'我还没发出的新想法'},notice:{textContent:''}};
 const calls=[],notices=[],messages=[];
 const context=vm.createContext({session:{user:{id:'synthetic-owner'}},conversation:action.conversation_id,version:5,busy:false,
  selectedLook:{conversationId:action.conversation_id,index:0},selectedCity:{city_name:'示例市'},pendingRun:null,
  pendingUploadAnchor:'med_'+'2'.repeat(32),window:{CompanionSettings:{ready,getProfile:()=>({assistant_persona:'male_calm_v1',user_gender:'女'})}},
  crypto:{randomUUID:()=> 'regenerate-request-unique'},TextDecoder,TextEncoder,setTimeout,
  $:id=>nodes[id],requireLogin:()=>!!context.session,headers:()=>({Authorization:'Bearer synthetic'}),
  notifyIssue:text=>notices.push(text),agentText:text=>text,error:(code,message)=>Object.assign(Error(message),{code}),
  savePending:value=>{context.pendingRun=value;},bubble:(role,text)=>messages.push({role,text}),
  pendingBubble:()=>({update(){},stop(){}}),setBusy:value=>{context.busy=value;},
  dailyCheckin:{completeChat(){}},updateUploadAnchor(){},showPlanApproval(){},expireSession(){},refreshHistory:async()=>{},
  showReply:reply=>{context.conversation=reply.conversation_id;context.version=reply.version;},
  fetch:async(path,options)=>{
   calls.push({path,request:JSON.parse(options.body)});if(wait)await wait;
   let read=false;
   return {ok:true,body:{getReader:()=>({read:async()=>{
    if(read)return {done:true};read=true;
    return {done:false,value:new TextEncoder().encode('event: result\ndata: '+JSON.stringify({conversation_id:action.conversation_id,version:6})+'\n\n')};
   },cancel:async()=>{}})}};
  }});
 vm.runInContext(sender+'\n'+regenerate,context);
 return {context,nodes,calls,notices,messages};
}
test('regenerate sends a real chat-stream request for the selected result and preserves the draft and upload anchor',async()=>{
 const t=setup();await t.context.regenerateOutfit(action);
 assert.equal(t.calls.length,1);const {path,request}=t.calls[0];
 assert.equal(path,'/stylist-api/chat/stream');assert.equal(request.message,'重新生成穿搭');
 assert.equal(request.regenerate_outfit,true);assert.equal(request.selected_look_index,1);
 assert.equal(request.conversation_id,action.conversation_id);assert.equal(request.expected_version,5);
 assert.equal(request.assistant_persona,'male_calm_v1');assert.equal(request.companion_profile.user_gender,'女');
 assert.equal(request.confirm_plan,false);assert.equal(request.upload_action_id,undefined);
 assert.equal(t.nodes.message.value,'我还没发出的新想法');assert.equal(t.context.pendingUploadAnchor,'med_'+'2'.repeat(32));
 assert.equal(t.messages[0].text,'重新生成穿搭');assert.equal(t.context.version,6);
});
test('concurrent regeneration clicks submit once while the first request is running',async()=>{
 let complete;const wait=new Promise(resolve=>complete=resolve);const t=setup({wait});
 const first=t.context.regenerateOutfit(action);await new Promise(resolve=>setImmediate(resolve));
 await t.context.regenerateOutfit(action);assert.equal(t.calls.length,1);
 complete();await first;
});
test('a failed try-on can regenerate clothing without submitting another paid image task',async()=>{
 const t=setup();await t.context.regenerateOutfit({...action,status:'failed'});
 assert.equal(t.calls.length,1);assert.equal(t.calls[0].path,'/stylist-api/chat/stream');assert.equal(t.calls[0].request.regenerate_outfit,true);
 assert.equal(t.nodes.message.value,'我还没发出的新想法');
});
for(const [name,change]of [
 ['future source',t=>t.context.version=4],['other conversation',t=>t.context.conversation='other'],
 ['pending confirmation',t=>t.context.pendingRun={owner:'synthetic-owner'}],['busy',t=>t.context.busy=true],
 ['signed out',t=>t.context.session=null],
])test(name+' cannot start a regeneration',async()=>{
 const t=setup();change(t);await t.context.regenerateOutfit(action);assert.equal(t.calls.length,0);
 assert.equal(t.nodes.message.value,'我还没发出的新想法');
});
test('an account change while companion settings load cannot send the old result as the new account',async()=>{
 let loaded;const ready=new Promise(resolve=>loaded=resolve);const t=setup({ready});
 const request=t.context.regenerateOutfit(action);t.context.session={user:{id:'another-owner'}};
 loaded();await request;assert.equal(t.calls.length,0);assert(t.notices[0].includes('账号或搭配已有更新'));
});
test('a late regeneration response cannot replace another account conversation',async()=>{
 let complete;const wait=new Promise(resolve=>complete=resolve);const t=setup({wait});
 const request=t.context.regenerateOutfit(action);await new Promise(resolve=>setImmediate(resolve));
 t.context.session={user:{id:'another-owner'}};t.context.conversation='new-account-conversation';t.context.version=2;
 complete();await request;assert.equal(t.context.conversation,'new-account-conversation');assert.equal(t.context.version,2);
 assert.deepEqual(t.notices,[]);assert.equal(t.nodes.message.value,'我还没发出的新想法');
});
test('an ordinary message still consumes its upload anchor and clears only the sent draft',async()=>{
 const t=setup();await t.context.sendMessage();assert.equal(t.calls[0].request.regenerate_outfit,undefined);
 assert.equal(t.calls[0].request.upload_action_id,'med_'+'2'.repeat(32));assert.equal(t.nodes.message.value,'');
});

test('city confirmation continues the original request with the chosen city and keeps the unsent draft',async()=>{
 const t=setup();const original={message:'周五通勤，搭两套，不穿高跟鞋',request_id:'original-city-request',confirm_plan:false,
  upload_action_id:'med_'+'3'.repeat(32),selected_look_index:1,assistant_persona:'female_regal_v1'};
 const before=JSON.stringify(original);
 await t.context.sendMessage(false,null,{owner:'synthetic-owner',conversation_id:action.conversation_id,version:5,request:original});
 assert.equal(t.calls.length,1);const request=t.calls[0].request;
 assert.equal(request.message,original.message);assert.equal(request.location.city_name,'示例市');
 assert.equal(request.expected_version,5);assert.notEqual(request.request_id,original.request_id);
 assert.equal(request.confirm_plan,false);assert.equal(request.upload_action_id,original.upload_action_id);
 assert.equal(request.assistant_persona,'female_regal_v1');assert.equal(JSON.stringify(original),before);
 assert.equal(t.nodes.message.value,'我还没发出的新想法');assert.equal(t.context.pendingUploadAnchor,'med_'+'2'.repeat(32));
});
for(const [name,patch]of [['account',{owner:'other'}],['conversation',{conversation_id:'other'}],['version',{version:4}]]){
 test('an outdated city card cannot resume a different '+name,async()=>{
  const t=setup();await t.context.sendMessage(false,null,{owner:'synthetic-owner',conversation_id:action.conversation_id,version:5,...patch});
  assert.equal(t.calls.length,0);assert.equal(t.nodes.message.value,'我还没发出的新想法');
 });
}

test('an earlier result regenerates using its source version and the current conversation head',async()=>{
 const t=setup();t.context.version=9;await t.context.regenerateOutfit(action);
 assert.equal(t.calls.length,1);assert.equal(t.calls[0].request.expected_version,9);
 assert.equal(t.calls[0].request.regenerate_from_version,5);assert.equal(t.calls[0].request.selected_look_index,1);
 assert.equal(t.nodes.message.value,'我还没发出的新想法');
});
