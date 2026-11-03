/* Real App check-in, mounted only by the Yijian direct integration. */
(()=>{
 const $=id=>document.getElementById(id), read=()=>{try{return JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1'));}catch{return null;}};
 window.DailyCheckin={mount({onLogin}){
  const dialog=$('checkin-dialog');dialog.innerHTML='<div class="checkin-top"><span class="eyebrow">A LITTLE MOMENT FOR YOU</span><button id="checkin-close" class="subtle" aria-label="关闭签到">×</button></div><div class="checkin-hero"><span class="checkin-chapter">日常 · 小笺</span><h2 id="checkin-title">把今天，轻轻记下来。</h2><p id="checkin-state">给今天的你，一份小小的心意。</p></div><div class="checkin-companion-note"><img id="checkin-companion-avatar" alt="" hidden><div><strong id="checkin-companion-name">衣间的小笺</strong><p id="checkin-companion-copy">在这里停一会儿，看看今天的签到小礼。</p></div><span aria-hidden="true">✧</span></div><div class="checkin-stats"><div><strong id="checkin-daily-points">—</strong><small id="checkin-points-label">今日签到奖励</small></div><div><strong id="checkin-total-days">—</strong><small>累计留下的签到 · 天</small></div></div><div class="checkin-week-heading"><h3 class="checkin-week-title">这一周的小记号</h3><span>周一至周日</span></div><div id="checkin-calendar" class="checkin-calendar"></div><button id="checkin-action" class="primary">正在翻开小笺…</button><button id="checkin-reload" class="subtle">再看看签到状态</button><p id="checkin-rules" class="checkin-note"></p>';
  let owner=null,token='',epoch=0,sequence=0,state=null,busy=false,claiming=false,unknown=false;
  const checkinLines={
    female_sweet_v1:'今天的小心意收好啦。也给自己留一点做喜欢的事的时间吧。',
    female_warm_v1:'愿你今天穿得舒服，也有时间做一点喜欢的事。',
    female_regal_v1:'今天也按自己的心意来。你喜欢的风格，值得认真选择。',
    male_artistic_v1:'给今天留一点小小的期待吧，也许就在一件喜欢的衣服里。',
    male_calm_v1:'接下来的安排，可以一件件慢慢理清。今天也记得照顾好自己。',
    male_confident_v1:'今天想穿什么，就大胆试试。搭配上的顾虑，我们一起想办法。'
  };
  const notify=text=>{const profile=window.CompanionSettings?.getProfile();window.PreviewMessage.notify(text,{role:profile?.assistant_persona,name:window.CompanionSettings?.agentName?.()||'衣间'});};
  const signedGreeting=()=>checkinLines[window.CompanionSettings?.getProfile()?.assistant_persona]||'愿今天有一件让你喜欢的小事。';
  const valid=(e,t)=>epoch===e&&read()?.access_token===t;
  async function api(method,e,t){const r=await fetch('/stylist-api/app/checkin',{method,headers:{Authorization:'Bearer '+t},cache:'no-store'});const body=await r.json();if(!valid(e,t))throw new DOMException('账号已切换','AbortError');if(!r.ok)throw Error(body.message||'签到暂时没能完成，请稍后重试。');return body.data;}
  function render(){
    const signed=state?.signed===true,amount=state?.daily_points;
    const profile=window.CompanionSettings?.getProfile(),name=window.CompanionSettings?.agentName()||'衣间';
    $('checkin-companion-name').textContent=name+'的小笺';
    const avatar=$('checkin-companion-avatar');avatar.hidden=!profile?.assistant_persona;if(profile?.assistant_persona)avatar.src='/static/assets/characters/companion-scenes-v1/'+profile.assistant_persona+'-avatar.png';
    $('checkin-companion-copy').textContent=signed?'今天的签到收好了，愿接下来的日常也有小小欢喜。':'很高兴今天在这里见到你。这份签到心意，记得收下。';
    $('checkin-title').textContent=signed?'今天的小记号，收好了。':'把今天，轻轻记下来。';
    $('checkin-entry-label').textContent=signed?'今日已签到':'每日签到';$('checkin-entry-meta').textContent=Number.isInteger(amount)?'每日 '+amount.toLocaleString('en-US')+' 积分':'查看签到奖励';
    $('checkin-points-label').textContent=signed?'每日签到奖励':'今日签到奖励';
    $('checkin-daily-points').textContent=Number.isInteger(amount)?amount.toLocaleString('en-US'):'—';$('checkin-total-days').textContent=Number.isInteger(state?.total_days)?String(state.total_days):'—';
    $('checkin-state').textContent=signed?'这一份日常心意，已经领过了。':unknown?'先确认今天的记录，再收下这份心意。':'给今天的你，一份小小的心意。';
    $('checkin-action').textContent=!owner?'登录，收下今日心意':claiming?'正在收好今日心意…':busy?'正在翻开小笺…':signed?'今日已收下':unknown?'请先确认今日记录':!state?'先看看今日记录':'收下今日心意';
    $('checkin-reload').hidden=!!state&&!unknown;$('checkin-reload').textContent='重新读取签到状态';
    $('checkin-action').disabled=!!owner&&(busy||claiming||signed||unknown||!state);$('checkin-reload').disabled=busy||claiming;
    $('checkin-calendar').replaceChildren();for(const day of state?.days||[]){const tile=document.createElement('div');tile.className='checkin-date'+(day.signed?' is-signed':'');const label=document.createElement('span'),value=document.createElement('small');label.textContent=(day.weekday_name||day.date).replace('周','');value.textContent=day.signed?'✓':'·';const date=document.createElement('em');date.textContent=day.date.slice(5).replace('-','/');tile.append(label,value,date);tile.setAttribute('aria-label',day.date+'，'+(day.signed?'已签到':'未签到'));$('checkin-calendar').append(tile);}
    $('checkin-rules').textContent=state?.tips||'签到奖励以本页实际显示为准。';
  }
  async function refresh(){if(!owner||claiming){render();return;}const e=epoch,t=token,ticket=++sequence;busy=true;render();try{const result=await api('GET',e,t);if(ticket!==sequence)return;if(typeof result?.signed!=='boolean'||!Array.isArray(result.days))throw Error('签到状态格式异常，请稍后重试。');state=result;unknown=false;}catch(error){if(error.name!=='AbortError'&&valid(e,t)){state=null;notify(error.message);}}finally{if(valid(e,t)&&ticket===sequence){busy=false;render();}}}
  $('checkin-open').onclick=()=>{dialog.showModal();refresh();};$('checkin-close').onclick=()=>dialog.close();$('checkin-reload').onclick=refresh;
  $('checkin-action').onclick=async()=>{if(!owner){dialog.close();onLogin();return;}if(busy||claiming||state?.signed||!state||unknown)return;const e=epoch,t=token;claiming=true;render();try{const result=await api('POST',e,t);if(typeof result?.granted!=='boolean'||!Number.isInteger(result.points_added))throw Error('签到回执暂未确认，请刷新状态。');state={...state,signed:true,total_days:result.total_days??state.total_days};notify(result.granted?'签到成功，获得 '+result.points_added.toLocaleString('en-US')+' 积分。\n'+signedGreeting():'今天已经签到过了，没有重复发放积分。');window.dispatchEvent(new CustomEvent('yijian-checkin-claimed'));claiming=false;await refresh();}catch(error){if(error.name!=='AbortError'&&valid(e,t)){unknown=true;notify(error.message+' 请先刷新状态，确认是否已签到。');}}finally{if(valid(e,t)){claiming=false;render();}}};
  render();return{setOwner(next){const nextToken=read()?.access_token||'';if(owner===next&&token===nextToken)return;epoch++;sequence++;owner=next;token=nextToken;state=null;busy=false;claiming=false;unknown=false;if(dialog.open)dialog.close();render();},completeChat(){/* Original App rules have no chat prerequisite. */}};
 }};
})();
