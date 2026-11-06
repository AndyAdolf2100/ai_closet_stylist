import {applyMembershipBanner,membershipPersona} from './membership-banners.js';

const letters={
 female_sweet_v1:'今天的小任务，一起慢慢完成吧。攒下的心意，留给下一次喜欢的搭配。',
 female_warm_v1:'不必一次做完。把日常里的小小认真，慢慢攒成喜欢的模样。',
 female_regal_v1:'按你的节奏来。每一份心意，都留给值得期待的自己。',
 male_artistic_v1:'把平常的一天，收进这封小笺。下一次灵感，就从这里开始。',
 male_calm_v1:'不必赶进度。今天的一小步，也值得收下一份心意。',
 male_confident_v1:'从你想做的那件事开始。剩下的期待，我们慢慢攒。'
};
// Mirror the account service's active flag; lifetime and timed rights may coexist.
export function membershipPrompt(account){
 const vip=account?.vip_info;
 const unknown={title:'会员方案',copy:'看看适合你的会员权益',action:'查看会员',state:'unknown'};
 if(!vip)return unknown;
 const active=vip.is_vip===true||vip.is_vip===1;
 if(!active&&vip.is_vip!==false&&vip.is_vip!==0)return unknown;
 if(!active)return {title:'开通会员',copy:'找到适合你的会员方案',action:'去开通',state:'inactive'};
 const timed=[2,3,4].includes(Number(vip.vip_type));
 const lifetime=vip.is_lifetime_vip===true||vip.is_lifetime_vip===1||Number(vip.vip_type)===5;
 if(lifetime&&!timed)return {title:'会员权益',copy:'看看已经拥有的会员权益',action:'查看权益',state:'lifetime'};
 return {title:'续费会员',copy:'让喜欢的陪伴继续',action:'去续费',state:'active'};
}
// Existing reward interfaces only: explicit check-in and read-only wardrobe milestone status.
export function pointsEarningPage({node,button,openAgent,openPurchase,readSession,signal}){
 const root=node('div','points-earning'),owner=readSession()?.access_token||'',controller=new AbortController();
 let sequence=0,claiming=false,claimUnknown=false,mounted=false,daily=null,disposed=false;
 const current=()=>!disposed&&!signal.aborted&&(readSession()?.access_token||'')===owner&&root.isConnected;
 const hero=node('section','pe-letter'),art=node('img','pe-letter-art');art.alt='';
 const letter=node('div','pe-letter-copy');letter.append(node('span','pe-eyebrow','A LITTLE MOMENT, A LITTLE GIFT'),node('h2','','把小小日常，\n攒成心动。'));
 const words=node('p','pe-letter-words',letters.male_calm_v1);letter.append(words);hero.append(art,letter,node('span','pe-letter-seal','✧'));root.append(hero);
 const balance=node('section','pe-balance'),balanceLabel=node('div'),amount=node('strong','pe-balance-value','—');balanceLabel.append(node('span','pe-eyebrow','留给下一次喜欢'),node('div','pe-balance-number'));balanceLabel.lastChild.append(amount,node('span','','可用积分'));
 const refresh=button('刷新',()=>load(),'pe-refresh');refresh.setAttribute('aria-label','刷新积分和任务状态');balance.append(balanceLabel,refresh);root.append(balance);
 const notice=node('p','pe-notice','');notice.setAttribute('role','status');root.append(notice);
 const dailyHead=node('div','pe-section-heading');dailyHead.append(node('h3','','今日的小约定'),node('span','','01 / DAILY'));root.append(dailyHead);
 const dailyArea=node('div','pe-daily');root.append(dailyArea);
 const wardrobeHead=node('div','pe-section-heading');wardrobeHead.append(node('h3','','衣橱里的小成就'),node('span','','02 / WARDROBE'));root.append(wardrobeHead);
 const wardrobeArea=node('div','pe-wardrobe');root.append(wardrobeArea);
 const purchase=node('aside','pe-purchase-tip');purchase.setAttribute('aria-label','积分包与会员提示');purchase.append(node('p','pe-tip-title','还想陪你，多试几套。'),node('p','pe-tip-note','添一点积分，下一套心动接着来。'));const links=node('div','pe-tip-links');
 for(const [group,title,copy] of [['points','购买积分包','多试几套喜欢的搭配'],['member','开通会员','找到适合你的会员方案']]){const entry=button('',()=>{if(current()&&openPurchase)openPurchase(group);},'pe-tip-link');entry.dataset.purchase=group;const mark=node('span','pe-tip-mark',group==='points'?'✦':'◇');mark.setAttribute('aria-hidden','true');const text=node('span','pe-tip-copy');text.append(node('strong','',title),node('small','',copy));const action=node('span','pe-tip-cta',group==='points'?'去充值':'去开通'),arrow=node('span','pe-tip-arrow','›');arrow.setAttribute('aria-hidden','true');action.append(arrow);entry.append(mark,text,action);links.append(entry);}
 function renderMembership(account){const prompt=membershipPrompt(account),entry=links.querySelector('[data-purchase=member]');entry.querySelector('strong').textContent=prompt.title;entry.querySelector('small').textContent=prompt.copy;entry.querySelector('.pe-tip-cta').firstChild.nodeValue=prompt.action;entry.dataset.membershipState=prompt.state;entry.setAttribute('aria-label',prompt.title+'，'+prompt.action);}
 renderMembership(null);purchase.append(links);root.append(purchase,node('p','pe-closing','不必把每一天都安排得满满的。\n一点点喜欢，也值得被好好收下。'));
 const footer=node('p','pe-rules','签到积分以当日显示为准；衣橱里程碑由系统按实际入柜进度发放，同一档奖励仅一次。');root.append(footer);
 function persona(value){const role=membershipPersona(value);applyMembershipBanner(art,role);words.textContent=letters[role];}
 persona(window.CompanionSettings?.getProfile()?.assistant_persona);
 async function request(path,{method='GET'}={}){
  if(!owner)throw Error('登录后，就能查看属于你的任务与积分。');
  const response=await fetch('/stylist-api/'+path,{method,headers:{Authorization:'Bearer '+owner},cache:'no-store',signal:controller.signal});
  const body=await response.json();if(!current())throw new DOMException('账号已切换','AbortError');
  if(!response.ok)throw Error(response.status===401?'登录已过期，请重新连接衣橱。':body.message||'这一页暂时没能读到，请稍后重试。');return body;
 }
 function task(mark,title,desc,reward){const card=node('section','pe-task'),icon=node('span','pe-task-icon',mark),copy=node('div','pe-task-copy'),top=node('div','pe-task-top');icon.setAttribute('aria-hidden','true');top.append(node('h4','',title));if(reward!=null)top.append(node('span','pe-reward','+'+reward+' 积分'));copy.append(top,node('p','',desc));card.append(icon,copy);return{card,copy};}
 function failure(target,title){const box=node('div','pe-task-error');box.append(node('p','',title),button('重新读取',()=>load(),'pe-secondary'));target.replaceChildren(box);}
 function renderDaily(){
  const t=task('✦','每日签到',daily.signed?'今天的心意，已经为你留好了。':'来这里坐一会儿，收下一份今日心意。',daily.daily_points);
  const action=button(daily.signed?'已收下':claimUnknown?'刷新确认':claiming?'领取中…':'收下心意',()=>claimUnknown?load():claim(),'pe-action');action.disabled=daily.signed||claiming;action.dataset.claim='true';t.card.classList.toggle('is-complete',daily.signed);t.card.append(action);dailyArea.replaceChildren(t.card);
  if(daily.daily_points==null&&!daily.signed)t.copy.append(node('small','pe-quiet','奖励数值暂未读取，领取结果以实际回执为准。'));
 }
 function renderMilestones(data){
  wardrobeArea.replaceChildren();if(!data.tiers.length){wardrobeArea.append(node('p','pe-quiet','新的衣橱小成就，还在准备中。'));return;}
  const summary=node('div','pe-wardrobe-summary');summary.append(node('span','','衣橱已收录'),node('strong','',data.current_item_count+' 件'));wardrobeArea.append(summary);
  const titles=['第一份衣橱心意','渐渐丰盈的衣橱','日常里的小珍藏'];
  for(const [index,tier] of data.tiers.entries()){
   const reached=data.current_item_count>=tier.threshold;
   const t=task(String(index+1).padStart(2,'0'),titles[index]||'衣橱新篇章','收录 '+tier.threshold+' 件衣物，让每一件喜欢都有位置。',tier.reward);
   t.card.classList.toggle('is-complete',tier.granted);const progress=node('div','pe-progress'),track=node('span','pe-progress-track'),fill=node('span','pe-progress-fill');fill.style.width=Math.min(data.current_item_count/tier.threshold*100,100)+'%';track.append(fill);track.setAttribute('role','progressbar');track.setAttribute('aria-label','衣橱单品收录进度');track.setAttribute('aria-valuemin','0');track.setAttribute('aria-valuemax',String(tier.threshold));track.setAttribute('aria-valuenow',String(Math.min(data.current_item_count,tier.threshold)));progress.append(track,node('small','',Math.min(data.current_item_count,tier.threshold)+' / '+tier.threshold+' 件'));t.copy.append(progress);
   const action=button(tier.granted?'已收下':reached?'待同步':'去添衣',()=>{if(current())openAgent('upload');},'pe-action pe-action-soft');action.disabled=tier.granted||reached;t.card.append(action);
   if(reached&&!tier.granted)t.copy.append(node('small','pe-quiet','已达到目标，奖励状态待同步。'));wardrobeArea.append(t.card);
  }
 }
 async function load(){
  if(!current()||claiming)return;const ticket=++sequence;renderMembership(null);refresh.disabled=true;notice.textContent='正在翻开今天的小约定…';
  const results=await Promise.allSettled([request('app/points'),request('app/checkin'),request('app/milestones'),request('companion-profile'),request('app/profile')]);
  if(!current()||ticket!==sequence)return;
  const [points,checkin,milestones,profile,account]=results;
  renderMembership(account.status==='fulfilled'?account.value.data:null);
  if(account.status==='fulfilled'&&account.value.data?.vip_info)window.dispatchEvent(new CustomEvent('yijian-account-loaded',{detail:account.value.data}));
  const validPoints=points.status==='fulfilled'&&typeof points.value.data?.total_available==='number'&&Number.isFinite(points.value.data.total_available)&&points.value.data.total_available>=0;
  amount.textContent=validPoints?points.value.data.total_available.toLocaleString('zh-CN'):'—';
  if(validPoints)window.dispatchEvent(new CustomEvent('yijian-points-loaded',{detail:{ownerToken:owner,total_available:points.value.data.total_available}}));
  if(checkin.status==='fulfilled'&&typeof checkin.value.data?.signed==='boolean'){
   daily=checkin.value.data;claimUnknown=false;renderDaily();
  }else{daily=null;failure(dailyArea,'今日签到状态暂未读到，先别着急。');}
  if(milestones.status==='fulfilled'&&Array.isArray(milestones.value.data?.tiers))renderMilestones(milestones.value.data);else failure(wardrobeArea,'衣橱小成就暂未读到，再试一次就好。');
  if(profile.status==='fulfilled')persona(profile.value.profile?.assistant_persona);
  notice.textContent=validPoints?'':'可用积分暂未读到，可以刷新再看看。';refresh.disabled=false;
 }
 async function claim(){
  if(!current()||claiming||!daily||daily.signed||claimUnknown)return;claiming=true;renderDaily();
  try{
   const result=(await request('app/checkin',{method:'POST'})).data;
   if(!current())return;
   if(typeof result?.granted!=='boolean'||!Number.isInteger(result.points_added)||result.points_added<0)throw Error('领取回执暂未确认');
   notice.textContent=result.granted?'今日心意已到账，+'+result.points_added+' 积分。':'今天的签到已经记下啦。';
   window.dispatchEvent(new CustomEvent('yijian-checkin-claimed'));claiming=false;await load();
   if(current())notice.textContent=result.granted?'今日心意已到账，+'+result.points_added+' 积分。':'今天的签到已经记下啦。';
  }catch(error){if(current()&&error.name!=='AbortError'){claimUnknown=true;notice.textContent='领取结果暂未确认，先刷新状态再看看。';}}
  finally{claiming=false;if(current()&&daily)renderDaily();}
 }
 function dispose(){if(disposed)return;disposed=true;sequence++;controller.abort();observer.disconnect();}
 const observer=new MutationObserver(()=>{if(mounted&&!root.isConnected)dispose();});const host=document.getElementById('detail-content');if(host)observer.observe(host,{childList:true});
 signal.addEventListener('abort',()=>{dispose();root.replaceChildren(node('p','pe-notice','账号已变化，请重新打开积分获取。'));},{once:true});
 window.addEventListener('focus',()=>{if(current())load();},{signal:controller.signal});
 if(!owner){refresh.hidden=true;notice.textContent='登录后，就能查看属于你的任务与积分。';dailyArea.append(button('登录衣橱',()=>openAgent('login'),'pe-action'));wardrobeArea.append(node('p','pe-quiet','让我们从一件喜欢的衣服开始。'));}
 else setTimeout(()=>{mounted=true;if(current())load();else dispose();},0);
 root.reopen=()=>pointsEarningPage({node,button,openAgent,openPurchase,readSession,signal});
 return root;
}
