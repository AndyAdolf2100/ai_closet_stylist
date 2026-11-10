import {readAvailablePoints} from '../points-balance.js';
// Adapt the maintained upload / twin / try-on controller to the first-run shell.
// No sample success states or image-generation implementation lives here.
export function createJourney({live,getToken,ensureAccess,getProfile,getCity,onChange,notify}) {
  const make=(tag,cls,text)=>{const e=document.createElement(tag);e.className=cls||'';if(text)e.textContent=text;return e;};
  const state={upload:null,reply:null,twins:null,busy:false,request:null,subjectProduct:null,subjectPaired:false,subjectContext:null};
  let owner=getToken(),ready,locationShown=false,followup='',uploadSequence=0;
  const feed=make('div','onboarding-results');feed.id='feed';const storage=make('div');storage.hidden=true;storage.append(feed);document.body.append(storage);
  const key=()=>{const id=JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')||'null')?.user?.id;return id?`yijian-onboarding-journey-${id}`:null;};
  const persist=()=>{if(live&&owner&&key())sessionStorage.setItem(key(),JSON.stringify({upload:state.upload?.action_id,conversation:state.reply?.conversation_id,request:state.request,subjectProduct:state.subjectProduct,subjectPaired:state.subjectPaired,subjectContext:state.subjectContext}));};
  const same=()=>owner&&getToken()===owner;
  window.addEventListener('server-garment-update',event=>{if(!same())return;let user;try{user=JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')||'null')?.user;}catch{}if(String(user?.id||user?.user_id||'')!==event.detail.owner)return;if(state.upload?.action_id!==event.detail.action_id){state.reply=null;state.subjectProduct=null;state.subjectPaired=false;state.subjectContext=null;}state.upload=event.detail;persist();onChange();});
  async function api(path,options={}){
    if(!same()){window.WardrobeJourney?.setOwner(null);feed.replaceChildren();throw Error('登录状态已变化，请重新进入引导。');}
    const token=owner,uploadTicket=path==='/stylist-api/media/uploads'?++uploadSequence:0;
    const response=await fetch(path,{...options,headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},cache:'no-store'});
    const result=await response.json();
    if(getToken()!==token){window.WardrobeJourney?.setOwner(null);feed.replaceChildren();throw Error('账号已切换，请重新进入引导。');}
    if(!response.ok)throw Error(result.message||'暂时未完成，请稍后重试。');
    if(result.kind==='garment'&&result.action_id&&((uploadTicket&&uploadTicket===uploadSequence)||result.action_id===state.upload?.action_id)){if(state.upload?.action_id!==result.action_id)state.reply=null;state.upload=result;persist();onChange();}
    if(path==='/stylist-api/twins'&&(!options.method||options.method==='GET')){state.twins=result;onChange();}
    return result;
  }
  async function mount(){
    if(!live){notify('请登录后体验上传与试穿；这里不会上传或生成示例结果。');return false;}
    if(!await ensureAccess())return false;
    if(!owner)owner=getToken();
    if(!same())throw Error('账号已切换，请重新进入引导。');
    if(!ready)ready=(async()=>{
      for(const name of ['server-garment-upload','wardrobe-journey','product-preview'])await new Promise((resolve,reject)=>{const s=document.createElement('script');s.src='/static/'+name+'.js?v=server-terminal-20261111';s.onload=resolve;s.onerror=()=>reject(Error('组件未能加载，请刷新重试。'));document.body.append(s);});
      window.WardrobeJourney.configure({api,notify,onProduct:async id=>{state.subjectProduct=id;state.subjectContext=null;state.subjectPaired=false;state.reply=null;persist();await askStyle();},onStyle:async id=>{try{if(state.request&&id!==state.upload?.action_id){notify('请先核对当前搭配请求，再更换衣物。');return;}if(id!==state.upload?.action_id){state.upload=await api('/stylist-api/media/'+encodeURIComponent(id));state.reply=null;persist();onChange();}await askStyle();}catch(e){notify(e.message);}},getConversation:()=>state.reply?.conversation_id,getContext:()=>({conversation_id:state.reply?.conversation_id,version:state.reply?.version})});
      window.WardrobeJourney.setOwner(owner);
      document.getElementById('journey-dialog').dataset.onboarding='true';
      // This is a presentation adapter only; account writes still happen on the final action.
      window.CompanionSettings={agentName:()=>getProfile().agent_name};
      window.AppPayment={async checkFunds(cost){if(cost!==null&&(!Number.isFinite(cost)||cost<0))throw Error('费用暂未确认，请重新读取。');const points=await readAvailablePoints();if(!same())throw Error('账号已切换。');if(cost===null?points<=0:points<cost){notify('可用积分不足，请稍后从会员与积分页补充后再继续。');return false;}return true;}};
      return true;
    })().catch(error=>{ready=null;throw error;});
    return ready;
  }
  function action(text,run,primary=false){const b=make('button',primary?'journey-main-action':'journey-secondary-action',text);b.type='button';b.disabled=state.busy;b.onclick=async()=>{if(state.busy)return;b.disabled=true;try{await run();}catch(e){notify(e.message);}finally{b.disabled=false;}};return b;}
  function confirm(title,text,run,label='确认继续'){
    const d=make('dialog','onboarding-confirm');d.dataset.appDialog='true';d.setAttribute('aria-label',title);
    const close=action('暂不继续',()=>d.close()),yes=action(label,async()=>{d.close();await run();},true);
    d.append(make('h2','',title),make('p','',text),yes,close);document.body.append(d);d.addEventListener('close',()=>d.remove());d.showModal();close.focus();
  }
  async function askStyle(){
    if(!state.upload||state.upload.status!=='completed'){notify('先确认一件衣服已收入衣橱，再从它开始搭配。');return;}
    confirm('从这件开始搭配','将请求助理结合个人衣橱搭配，按当前服务规则消耗对话积分；数字分身和试穿费用会分别确认。',async()=>{
      if(!await mount()||!await window.AppPayment.checkFunds(null))return;
      state.busy=true;onChange();
      try{
        const directProduct=state.subjectProduct||(state.upload?.result?.protocol==='server_direct'?state.upload.result.user_product_id:null);
        if(state.upload?.result?.protocol==='server_direct'&&!directProduct){notify('请在上传结果中选择具体单品，再从这件开始搭配。');return;}
        if(directProduct&&!state.subjectContext&&!state.reply){const entry=await api('/stylist-api/chat',{method:'POST',body:JSON.stringify({request_id:crypto.randomUUID(),message:'',subject_product:{source:'user',product_id:String(directProduct)}})});state.reply=entry;state.subjectContext={conversation_id:entry.conversation_id,expected_version:entry.version};persist();}
        // Retain the request ID on uncertain transport failures; retry does not create another run.
        state.request ||= {request_id:crypto.randomUUID(),message:followup.trim()||'用我刚上传的这件衣服，结合自己的衣橱搭一套日常穿搭。',...(directProduct&&!state.subjectPaired?{...state.subjectContext,pair_subject_product:true}:state.reply?{conversation_id:state.reply.conversation_id,expected_version:state.reply.version}:{upload_action_id:state.upload.action_id}),source:'wardrobe',new_clothes:false,companion_profile:getProfile(),...(getCity()?{location:getCity()}: {})};persist();
        const reply=await api('/stylist-api/chat',{method:'POST',body:JSON.stringify(state.request)});
        state.reply=reply;if(directProduct&&!reply.pending_confirmation)state.subjectPaired=true;if(!reply.pending_confirmation)state.request=null;followup='';persist();
      }finally{state.busy=false;onChange();}
    },state.request?'继续核对原搭配请求':'确认开始搭配');
  }
  async function open(kind){if(kind==='garment'&&state.request){notify('还有一条搭配请求待核对，请先继续原请求，再更换衣物。');return;}if(!await mount())return;if(kind==='garment')window.WardrobeJourney.upload('garment');else if(kind==='twins')await window.WardrobeJourney.twins();else if(kind==='records')await window.WardrobeJourney.history();else if(kind==='tryon'){
    if(!state.reply?.looks?.length){notify('请先在第三步完成一套真实衣橱搭配。');return;}
    await window.WardrobeJourney.tryon({conversation_id:state.reply.conversation_id,version:state.reply.version,look_index:0});
  }}
  function panel(step){
    if(step!==4)storage.append(feed);
    const root=make('section','onboarding-journey');
    const art=make('div','onboarding-journey-art');art.setAttribute('aria-hidden','true');art.innerHTML='<svg viewBox="0 0 100 100" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true">'+(step===2?'<path d="M35 18 12 32l12 21 11-7v36h30V46l11 7 12-21-23-14c-2 16-28 16-30 0Z"/>':step===3?'<circle cx="50" cy="23" r="12"/><path d="M36 41 26 49l-7 30 9 3 10-25-3 33h30l-3-33 10 25 9-3-7-30-10-8Z"/>':'<path d="M26 24h48v61H26Z M38 15h24v9H38Z m-4 24 9 9 22-22 M36 70h28"/>')+'</svg>';root.append(art);
    if(step===2){
      root.append(make('h3','',state.upload?.status==='completed'?'这件喜欢，已收入衣橱。':'先收进一件喜欢的衣服。'),make('p','','一次可选最多10张照片，拼成一张后预览、确认上传。单品识别结果以处理回信为准。'),action('选择衣物照片',()=>open('garment'),true));
      if(state.upload)root.append(make('p','journey-status',state.upload.status==='completed'?'已入柜，可从这件开始搭配。':'上传结果待确认，可在处理记录中查看原任务。'));
      if(state.upload?.status==='completed')root.append(action(state.reply?.looks?.length?'重新查看搭配说明':'用这件搭一套',()=>state.reply?.looks?.length?notify(state.reply.message):askStyle()));
      if(state.busy)root.append(make('p','journey-status','正在准备搭配，请稍候…'));
      if(state.reply){root.append(make('p','journey-reply',state.reply.message));for(const look of state.reply.looks||[]){const card=make('section','onboarding-look');card.append(make('h4','',look.title));for(const item of look.items||[])card.append(make('span','',item.title||item.class_name||'衣橱单品'));root.append(card);}if(state.reply.pending_confirmation&&state.request){root.append(action('确认需求，继续搭配',async()=>{if(!await mount())return;state.busy=true;onChange();try{state.reply=await api('/stylist-api/chat/approval',{method:'POST',body:JSON.stringify({request:state.request,approved:true})});state.request=null;persist();}finally{state.busy=false;onChange();}}));}else if(!state.reply.looks?.length){const input=make('textarea','journey-followup');input.placeholder='补充场合或偏好，再继续搭配';input.setAttribute('aria-label','补充搭配需求');input.value=followup;input.oninput=()=>followup=input.value;root.append(input,action('补充需求，继续搭配',askStyle));}}
    }else if(step===3){root.append(make('h3','','遇见自己的新模样。'),make('p','','使用已有形象，或上传本人照片创建数字分身。照片检查后，生成积分会单独确认。'),action('选择或创建数字分身',()=>open('twins'),true));if(state.twins?.default_confirmed)root.append(make('p','journey-status','已确认试穿形象，可继续下一步。'));}
    else {root.append(make('h3','','把喜欢，穿在自己身上。'),make('p','',state.reply?.looks?.length?'搭配已准备好，选择形象后查看本次试穿积分。':'还没有准备好搭配也没关系，可以返回第三步，或先进入衣橱慢慢来。'),action('查看试穿形象与费用',()=>open('tryon'),true));root.append(feed);}
    return root;
  }
  function locationNotice(controls){
    if(locationShown)return;locationShown=true;
    const d=make('dialog','onboarding-confirm');d.dataset.appDialog='true';d.setAttribute('aria-label','也想替你，留意晴雨');
    d.append(make('h2','','也想替你，留意晴雨'),make('p','','定位只用于匹配天气。你也可以手动选城，或暂不定位；只有点击开启定位才申请系统权限。'),action('开启定位',()=>{d.close();return controls.openLocation();},true),action('手动选择城市',()=>{d.close();return controls.openManual();}),action('暂不定位',()=>d.close()));
    document.body.append(d);d.addEventListener('close',()=>d.remove());d.showModal();d.querySelector('button:last-child').focus();
  }
  window.addEventListener('pagehide',()=>{window.WardrobeJourney?.setOwner(null);});
  return {panel,locationNotice,busy:()=>state.busy,confirm,async restore(){
    if(!live||!owner||!key())return;
    let saved;try{saved=JSON.parse(sessionStorage.getItem(key())||'null');}catch{}if(!saved)return;
    try{state.request=saved.request||null;state.subjectProduct=saved.subjectProduct||null;state.subjectPaired=saved.subjectPaired||false;state.subjectContext=saved.subjectContext||null;if(saved.upload?.startsWith('server_')){if(await mount())state.upload=await window.ServerGarmentUpload.refresh(saved.upload);}else if(saved.upload)state.upload=await api('/stylist-api/media/'+encodeURIComponent(saved.upload));if(saved.conversation){const record=await api('/stylist-api/conversations/'+encodeURIComponent(saved.conversation));state.reply=record.messages?.at(-1)?.reply||null;}onChange();}catch(e){notify('之前的进度暂未读到，可在处理记录中核对后继续。');}
  }};
}
