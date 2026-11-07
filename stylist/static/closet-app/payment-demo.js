import {catalogState,loadCatalog,subscribeCatalog} from './purchase-catalog.js';
import {readAvailablePoints} from './points-balance.js';
import './payment-views.js';
// Shared presentation; actual business errors and explicit demos have separate data paths.
export const paymentDemoEnabled=()=>document.documentElement.dataset.appDesign==='yijian'&&new URLSearchParams(location.search).get('payment_demo')==='1';
const token=()=>{try{return JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')||'null')?.access_token||'';}catch{return '';}};
export function mountPaymentDemo({ensureAgent,showAgent,showTask}){
 if(document.documentElement.dataset.appDesign!=='yijian')return;
 const demo=paymentDemoEnabled(),roots=new Set();let epoch=0,currentOwner=token(),origin='agent',view='letter',purchaseKind='points',selected=1,plan='points',returnState='success',capacityBranch='normal',live=false,opener=null,funds={},memberActive=false;
 const css=document.createElement('link');css.rel='stylesheet';css.href='/static/closet-app/payment-demo.css';document.head.append(css);
 const dialog=document.createElement('dialog');dialog.className='app-payment-dialog';dialog.dataset.appDialog='payment';dialog.setAttribute('aria-label','积分与会员');document.body.append(dialog);
 function createSurface(host){const shadow=host.attachShadow({mode:'open'}),link=document.createElement('link'),root=document.createElement('div');link.rel='stylesheet';link.href='/static/closet-app/payment-views.css';root.className='payment-root';shadow.append(link,root);roots.add(root);return root;}
 const panelHost=document.createElement('div');panelHost.className='app-payment-panel';dialog.append(panelHost);
 const panel=createSurface(panelHost),profile=()=>window.CompanionSettings?.getProfile()||{},role=()=>profile().assistant_persona||'male_calm_v1';
 function theme(){for(const root of roots){if(!root.isConnected){roots.delete(root);continue;}root.dataset.theme=document.documentElement.dataset.appPalette||'system';}}
 new MutationObserver(theme).observe(document.documentElement,{attributes:true,attributeFilter:['data-app-palette']});
 subscribeCatalog(()=>{if(live&&dialog.open)render();});
 window.addEventListener('yijian-account-loaded',e=>{memberActive=e.detail?.vip_info?.is_vip===true||e.detail?.vip_info?.is_vip===1;if(live&&dialog.open)render();});
 function render(){panel.className='payment-root'+(view==='twin'?' twin-view':'');panel.innerHTML=PaymentViews.render({view,scene:origin,role:role(),name:profile().agent_name||'衣衣',assetBase:'/static/closet-app/assets/care-portraits/',purchaseKind,selected,returnState,capacityBranch,live,catalog:live?catalogState():null,memberActive,...funds});theme();dialog.scrollTop=0;}
 const originalView=()=>origin==='agent'||origin==='expanded'?'letter':origin.startsWith('capacity')?'capacity':origin==='return'?'receipt':origin==='twin'?'twin':origin==='vip'?'vip':'points';
 function open(scene,{actual=false,pointsCost,availablePoints}={}){origin=scene;live=actual;funds={pointsCost,availablePoints};capacityBranch=scene==='capacity-vip'?'vip':scene==='capacity-system'?'system':'normal';if(scene.startsWith('capacity'))origin='capacity';returnState='success';view=originalView();plan='points';opener=document.activeElement;render();if(!dialog.open)dialog.showModal();dialog.tabIndex=-1;dialog.focus({preventScroll:true});if(actual)loadCatalog();}
 function close(){dialog.close();}
 dialog.addEventListener('close',()=>{if(opener?.isConnected)opener.focus({preventScroll:true});});dialog.addEventListener('keydown',e=>{if(e.key==='Escape')e.stopPropagation();});
 const notify=text=>{if(window.CompanionSettings)window.CompanionSettings.notify(text);else window.PreviewMessage?.notify(text);};
 panel.addEventListener('click',e=>{const b=e.target.closest('[data-action]');if(!b)return;const action=b.dataset.action;
  if(action==='close'||action==='cancel-task'){close();return;}
  if(action==='plan'||action==='capacity-plan'){plan=b.dataset.value;panel.querySelectorAll('[data-action="'+action+'"]').forEach(x=>{x.classList.toggle('selected',x===b);x.setAttribute('aria-pressed',String(x===b));});const next=panel.querySelector('[data-action=chosen-purchase]');if(next)next.textContent=plan==='points'?'补充积分':'查看会员权益';return;}
  if(live&&['points','member','chosen-purchase','blocked'].includes(action)){
    const group=action==='member'?'member':action==='chosen-purchase'?plan:'points';
    const owner=token();close();document.dispatchEvent(new CustomEvent('yijian-purchase-request',{detail:{group,ownerToken:owner,requiredPoints:typeof funds.pointsCost==='number'&&typeof funds.availablePoints==='number'?Math.max(0,funds.pointsCost-funds.availablePoints):0}}));return;
  }
  if(['points','member','chosen-purchase','blocked'].includes(action)){purchaseKind=action==='member'?'member':action==='chosen-purchase'?plan:'points';selected=purchaseKind==='member'?1:origin==='twin'?0:1;view='purchase';}
  else if(action==='pack'){selected=Number(b.dataset.value);view='purchase';}
  else if(action==='return-origin'){view=originalView();}
  else if(action==='preview-pay'){view='confirm';}
  else if(action==='demo-receipt'){if(live){notify('购买尚未接入，未创建订单或变更积分。');return;}view='receipt';returnState='success';}
  else if(action==='receipt-action'){if(['pending','unknown'].includes(returnState))notify('订单入口预览，未读取真实订单。');else{close();notify('原选择已保留；请重新读取费用，再由你确认。');}return;}
  else if(action==='reselect'){close();return;}
  else if(action==='contact'){notify('请从「我的 → 联系我们」查看帮助。');return;}
  else return;
  render();
 });
 function card(actual=false,amounts={}){const feed=document.getElementById('feed');if(!feed)return;feed.querySelector('[data-payment-inline]')?.remove();const host=document.createElement('section');host.dataset.paymentInline='true';host.className='app-payment-inline';feed.append(host);const root=createSurface(host);root.innerHTML=PaymentViews.render({view:'message',scene:'agent',role:role(),name:profile().agent_name||'衣衣',assetBase:'/static/closet-app/assets/care-portraits/',live:actual,...amounts});theme();root.querySelector('button').onclick=()=>open('agent',{actual,...amounts});host.scrollIntoView({block:'end'});const owner=token(),ticket=epoch;window.CompanionSettings?.notify((actual?'':'【效果演示】')+(PaymentViews.personas[role()]||PaymentViews.personas.male_calm_v1)[1],{onRead:()=>{if(owner===token()&&ticket===epoch)open('agent',{actual,...amounts});}});}
 async function launch(scene){const ticket=epoch;await ensureAgent();if(ticket!==epoch)return;if(scene==='agent'){await showAgent();card();}else{if(['tryon','vip','return'].includes(scene))showTask('my-outfits');open(scene);}}
 function entry(parent,label,options){if(!parent)return;const box=document.createElement('section');box.className='app-payment-demo-entry';const heading=document.createElement('strong');heading.textContent=label+' · 效果演示';box.append(heading);const row=document.createElement('div');for(const[scene,title]of options){const b=document.createElement('button');b.type='button';b.dataset.paymentDemo=scene;b.textContent=title;b.onclick=()=>launch(scene);row.append(b);}box.append(row);parent.append(box);return box;}
 if(demo){entry(document.querySelector('.wardrobe-scene'),'衣橱付费位置',[['beautify','润色积分不足'],['capacity','衣橱容量'],['capacity-vip','会员容量已满'],['capacity-system','系统单品上限']]);const e=entry(document.querySelector('.profile-content'),'形象与搭配付费位置',[['twin','数字分身费用'],['tryon','搭配试穿费用'],['vip','会员积分不足'],['return','购买返回效果']]);if(e)document.querySelector('.identity')?.after(e);entry(document.querySelector('.y-welcome'),'Agent付费位置',[['agent','查看Agent积分提示']]);document.addEventListener('yijian-agent-mounted',()=>entry(document.querySelector('#feed'),'Agent付费位置',[['agent','查看积分提示（演示）']]));const banner=document.createElement('div');banner.className='app-payment-demo-banner';banner.textContent='App内付费效果演示 · 不创建订单或变更积分';const exit=document.createElement('button');exit.textContent='退出演示';exit.onclick=()=>{const u=new URL(location.href);u.searchParams.delete('payment_demo');location.href=u.href;};banner.append(exit);document.querySelector('#app').prepend(banner);}
 const errorScenes={product_upload_capacity_exhausted:'capacity',digital_twin_points_insufficient:'twin',tryon_points_insufficient:'tryon',agent_points_insufficient:'agent',points_insufficient:'agent'};
 window.AppPayment=Object.freeze({
 async checkFunds(cost,scene='agent',isCurrent=()=>true){
  if(cost!==null&&(typeof cost!=='number'||!Number.isFinite(cost)||cost<0))throw new Error('费用暂时无法确认，请重新读取报价。');
  const ticket=epoch,balance=await readAvailablePoints();if(ticket!==epoch||!isCurrent())throw new DOMException('请求已取消或账号已切换','AbortError');
  if(cost===null?balance<=0:balance<cost){const amounts={pointsCost:cost,availablePoints:balance};if(scene==='agent')card(true,amounts);else open(scene,{actual:true,...amounts});return false;}return true;
 },
 handleError(error){const scene=errorScenes[error?.code];if(!scene||!token())return false;if(scene==='agent')card(true);else open(scene==='capacity'?'capacity-vip':scene,{actual:true});return true;}});
 function reset(){memberActive=false;epoch++;close();document.querySelectorAll('[data-payment-inline]').forEach(e=>e.remove());theme();}
 window.addEventListener('popstate',close);
 window.addEventListener('yijian-account-reset',reset);window.addEventListener('yijian-session-change',()=>{const next=token();if(next!==currentOwner){currentOwner=next;reset();}});
}
