// Surface contract: h5_agent (Web), ios_agent (native iOS), android_agent (native Android).
// Console-only Agent instrumentation. No SDK, network, storage or user content.
export const agentEvents = [
 ['PageView','进入Agent','chat页面实际显示；重复放置不重复记'],['AgentLeave','离开Agent','chat页面离开；耗时为本次可见时长'],
 ['ClickAgentBtn','操作点击','Agent内可操作按钮；btn_type使用固定枚举，点击不代表成功'],
 ['AgentSend','发送尝试','通过本地校验，开始一次请求；重连不新增尝试'],
 ['AgentSendBlocked','余额阻止发送','积分预检查返回不足；不算请求成功'],
 ['AgentRequest','请求发出','每次真正fetch stream之前；重连可多次'],
 ['AgentStage','处理阶段','同一尝试同一已知阶段只记一次'],
 ['AgentFirstText','首次正文','校验正文开始呈现；每次尝试仅一次，含等待秒数'],
 ['AgentResult','结果呈现','最终正文与卡片完成渲染；不在历史回放触发'],
 ['AgentError','请求失败','未完成请求进入失败处理；仅固定错误分类'],
 ['AgentReconnect','连接重试','可恢复断线进入重试；不是新发送'],
 ['AgentAbandon','请求中断','未完成、未失败、未余额阻止即退出本次执行，例如换号'],
 ['AgentNewContentShow','新内容提示曝光','从无未读提示变为有未读提示；按一次出现去重'],
 ['AgentAttachment','附件处理','选取、预览就绪、失败、主动移除；不记录文件名或内容']
].map(([eventName,label,trigger])=>({eventName,label,trigger}));
const names=new Set(agentEvents.map(e=>e.eventName));
const colors={AgentError:'#d44b51',AgentResult:'#23865e',AgentFirstText:'#23865e',PageView:'#7754b3',AgentLeave:'#7754b3'};
const allowed={choice:['like','dislike','undo'],btn_type:['city','history','new_chat','attachment','voice','quick_prompt','followup','source_wardrobe','source_hybrid','scroll_latest','outfit_style','outfit_expand','outfit_feedback','outfit_regenerate','outfit_tryon','upload_garment','twins','records','memory','preferences','settings','city_confirm','city_cancel','locate','photo','camera','journey_confirm','journey_close'],stage:['connecting','understanding','weather','wardrobe','styling','checking','new_clothes'],outcome:['selected','ready','failed','removed'],source:['photo','camera'],error_kind:['auth','network','model','other'],delivery:['advice','outfit','concept','clarification'],palette:['system','male','female']};
const numbers=new Set(['attempt','elapsed_ms','text_length','look_count','retry_count','view_ms','waiting_time','stay_time','outfit_count']);
const booleans=new Set(['has_image','new_clothes','resuming','has_new_content','is_depleted']);
const debugEvents=new Set(['AgentRequest','AgentStage','AgentReconnect']);
for(const item of agentEvents)item.debugOnly=debugEvents.has(item.eventName);
let enabled=true,debug=false,sequence=0,attemptSequence=0,viewStarted=0,entryPage='';
const attempts=new Map();
const visible=()=>document.getElementById('yijian-agent-root')?.dataset.surface==='chat'&&!document.getElementById('agent-page')?.hidden;
export const agentActions=[['.y-agent-city-button','city'],['#agent-account,#mobile-history','history'],['#mobile-new,#new-chat','new_chat'],['#upload-open','attachment'],['#y-voice-input','voice'],['[data-prompt]','quick_prompt'],['.followups button','followup'],['#personal-clothes','source_wardrobe'],['#new-clothes','source_hybrid'],['#scroll-bottom','scroll_latest'],['.outfit-tab','outfit_style'],['.outfit-expand','outfit_expand'],['.outfit-feedback button','outfit_feedback'],['[data-agent-track=outfit_regenerate]','outfit_regenerate'],['[data-agent-track=outfit_tryon]','outfit_tryon'],['#twin-open','twins'],['#journey-records-open','records'],['#welcome-upload','upload_garment'],['#memory-open','memory'],['#preferences-open','preferences'],['#companion-open','settings'],['#location-save','city_confirm'],['#location-cancel','city_cancel'],['#locate-me','locate'],['[data-attachment=photo]','photo'],['[data-attachment=camera]','camera'],['.journey-submitbar .primary','journey_confirm'],['.journey-heading button','journey_close']];
export function installAgentTracking(host){
 if(window.AgentTracking)return;
 function emit(eventName,params={}){
  if(!enabled||!names.has(eventName)||(!visible()&&!['PageView','AgentLeave'].includes(eventName)&&!attempts.has(params.attempt)))return;
  if(debugEvents.has(eventName)&&!debug)return;
  if(eventName==='AgentStage'&&!allowed.stage.includes(params.stage))return;
  if(eventName==='ClickAgentBtn'&&!allowed.btn_type.includes(params.btn_type))return;
  const safe={};for(const [k,v]of Object.entries(params)){
   if(numbers.has(k)&&typeof v==='number'&&Number.isFinite(v))safe[k]=Math.max(0,['waiting_time','stay_time'].includes(k)?Math.round(v*1000)/1000:Math.round(v));
   else if(booleans.has(k)&&typeof v==='boolean')safe[k]=v;
   else if(allowed[k]?.includes(v))safe[k]=v;
  }
  const palette=document.documentElement.dataset.appPalette;
  const properties={event_id:eventName+'_'+String(++sequence).padStart(6,'0'),page_name:'Agent',page_params:'Agent',source_page:attempts.get(params.attempt)??entryPage,surface:'h5_agent',palette:allowed.palette.includes(palette)?palette:'system',...safe};
  if('elapsed_ms' in properties){properties.waiting_time=Math.round(properties.elapsed_ms)/1000;delete properties.elapsed_ms;}
  if('view_ms' in properties){properties.stay_time=Math.round(properties.view_ms)/1000;delete properties.view_ms;}
  if('look_count' in properties){properties.outfit_count=properties.look_count;delete properties.look_count;}
  if(eventName==='AgentSendBlocked')properties.is_depleted=true;
  const payload={eventName,properties};
  try{console.log('%c Agent %c '+eventName+' ',`background:${colors[eventName]||'#3678ad'};color:white;padding:3px 7px;border-radius:5px;font-weight:bold`,'color:#3678ad;font-weight:bold',payload);}catch{/* Logging never blocks business actions. */}
 }
 const tracker={track(eventName,properties={}){if(!visible()&&!attempts.has(properties.attempt))return;emit(eventName,properties);},begin(params){if(!visible())return null;const attempt=++attemptSequence;attempts.set(attempt,entryPage);emit('AgentSend',{...params,attempt});return attempt;},end(attempt){attempts.delete(attempt);},view(chat){if(chat){if(viewStarted)return;entryPage=({home:'Outfit',wardrobe:'Closet',profile:'Personal_center'})[location.hash.slice(1).split('/')[0]]||'';viewStarted=performance.now();emit('PageView');}else if(viewStarted){emit('AgentLeave',{view_ms:performance.now()-viewStarted});viewStarted=0;}},setEnabled(value){enabled=value===true;},setDebug(value){debug=value===true;}};
 window.AgentTracking=Object.freeze(tracker);
 const selectors=agentActions;
 document.addEventListener('click',e=>{
  if(!visible()||!(e.target instanceof Element))return;
  const button=e.target.closest('button,input');if(!button||button.disabled||button.closest('[hidden]')||(!host.contains(button)&&!button.closest('#agent-page>header')))return;
  for(const [selector,action]of selectors)if(button.matches(selector)){const props={btn_type:action};if(action==='outfit_feedback')props.choice=button.dataset.agentVote;if(action==='scroll_latest')props.has_new_content=button.classList.contains('has-new-content');emit('ClickAgentBtn',props);break;}
 },true);
}
