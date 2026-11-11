import {membershipPersona,applyMembershipBanner} from './membership-banners.js';
import {catalogState,loadCatalog,subscribeCatalog,purchaseOwner} from './purchase-catalog.js';
// Live catalog, presentation-only purchase. No orders, StoreKit calls or balance changes.
export {careCopy} from './care-copy.js';
let group='member',selected={member:null,points:null},account=null,payment=null,epoch=0,requiredPoints=0;
let bannerPersona='male_calm_v1',bannerOwner=null;
function bannerSession(){try{return JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')||'null')?.access_token||'';}catch{return '';}}
function resetBanner(){const owner=bannerSession();if(!owner||owner!==bannerOwner){bannerOwner=owner;bannerPersona='male_calm_v1';update();}}
const listeners=new Set();
// History may detach and restore a detail node. Subscribe only while mounted.
customElements.define('sku-purchase-center',class extends HTMLElement{
  connectedCallback(){if(this.render){listeners.add(this.render);this.render();loadCatalog(true);}}
  disconnectedCallback(){listeners.delete(this.render);}
});
function el(tag,cls,text){const e=document.createElement(tag);e.className=cls;if(text)e.textContent=text;return e;}
function button(text,action,cls=''){const b=el('button',cls,text);b.type='button';b.onclick=action;return b;}
// Only a successful empty catalog means memberships are unavailable.
function memberAvailable(){const member=catalogState().member;return member.status!=='ready'||member.data.length>0;}
function ensureGroup(){if(group==='member'&&!memberAvailable())group='points';}
function keyboardGroup(key){if(!memberAvailable())return 'points';return key==='Home'?'member':key==='End'?'points':group==='member'?'points':'member';}
function items(){const entry=catalogState()[group];return entry.status==='ready'?entry.data:[];}
function current(){const list=items();let p=list.find(p=>p.id===selected[group]);if(!p){p=(group==='points'&&requiredPoints>0?(list.find(p=>p.points>=requiredPoints)||list.reduce((a,b)=>!a||b.points>a.points?b:a,null)):null)||list.find(p=>p.recommended)||list[0];selected[group]=p?.id??null;}return p;}
function active(){return account?.vip_info?.is_vip===true||account?.vip_info?.is_vip===1;}
function action(p){if(group==='points')return '购买';if(p.sub===true&&account?.vip_info?.is_subscribing===1)return '管理订阅';const flag=account?.vip_info?.is_vip;return flag===true||flag===1?'续费':flag===false||flag===0?'开通':'查看';}
function money(p,value=p.price){try{return new Intl.NumberFormat('zh-CN',{style:'currency',currency:p.currency||'CNY',maximumFractionDigits:2}).format(value);}catch{return String(value)+' '+p.currency;}}
function stateMessage(section,retry=true){const value=catalogState()[section],box=el('div','sku-data-state');box.setAttribute('role','status');box.dataset.state=value.status;box.append(el('p','sku-note',!purchaseOwner()?'登录后查看当前商品与权益。':value.status==='loading'||value.status==='idle'?'正在读取…':value.status==='error'?value.error:'当前暂无可用方案。'));if(purchaseOwner()&&retry&&value.status==='error')box.append(button('重新读取',()=>loadCatalog(true),'sku-cancel'));return box;}
function benefitsTable(){
 const section=el('section','sku-benefits');section.append(el('h3','','会员权益对比'));
 const entry=catalogState().benefits;if(entry.status!=='ready'){section.append(stateMessage('benefits'));return section;}
 const t=entry.data.benefit_table,rows=t.rows.filter(r=>!r.display_scope||r.display_scope==='all');
 if(!t.columns.length||!rows.length){section.append(el('p','sku-note','暂无已发布的权益说明。'));return section;}
 const wrap=el('div','sku-table-wrap'),table=el('table',''),head=el('thead',''),tr=el('tr','');
 for(const text of [t.name_column_header||'权益',...t.columns.map(c=>c.header)]){const th=el('th','',text);th.scope='col';tr.append(th);}head.append(tr);table.append(head);
 const body=el('tbody','');for(const row of rows){const tr=el('tr',''),th=el('th','',row.name);th.scope='row';if(row.tooltip){th.append(el('small','sku-benefit-tooltip',' · '+row.tooltip));}tr.append(th);for(const value of row.values){const td=el('td','',value.type==='check'?'✓':value.type==='cross'?'—':String(value.text??''));if(value.type!=='text')td.setAttribute('aria-label',value.type==='check'?'包含':'不包含');tr.append(td);}body.append(tr);}table.append(body);wrap.append(table);section.append(wrap);return section;
}
function update(){ensureGroup();for(const draw of listeners)draw();}
function closePay(){epoch++;if(payment){payment.close();payment.remove();payment=null;}}
function pay(p){
 if(payment||!purchaseOwner()||!items().some(x=>x.id===p.id))return;
 const token=purchaseOwner(),dialog=el('dialog','sku-payment');payment=dialog;dialog.dataset.appDialog='sku-payment';dialog.setAttribute('aria-label','购买交互演示');const ticket=++epoch;
 const close=()=>closePay();dialog.append(button('×',close,'sku-payment-close'),el('p','sku-note','H5购买交互演示 · 非支付窗口'),el('h2','',p.name),el('strong','sku-price',money(p)),el('p','',p.term),el('p','',p.description),el('p','sku-note','商品与金额来自后台；本页仅演示，不创建订单、扣款或变更积分。'),button('知道了',close,'sku-cancel'));
 document.body.append(dialog);if(ticket!==epoch||token!==purchaseOwner()){closePay();return;}dialog.showModal();dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
}
export function skuRail(){const root=el('section','sku-catalog');root.setAttribute('aria-label','会员与积分方案');const scroll={member:0,points:0};function draw(){ensureGroup();const old=root.querySelector('.sku-rail');if(old)scroll[root.dataset.group]=old.scrollLeft;root.dataset.group=group;root.replaceChildren();const tabs=el('div','sku-tabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','商品类型');for(const [key,title]of [['member','会员方案'],['points','积分包']]){if(key==='member'&&!memberAvailable())continue;const tab=button(title,()=>{group=key;update();});tab.setAttribute('role','tab');tab.setAttribute('aria-selected',String(group===key));tab.tabIndex=group===key?0:-1;tab.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();group=keyboardGroup(e.key);update();root.querySelector('[aria-selected=true]').focus();}};tabs.append(tab);}root.append(tabs);const rail=el('div','sku-rail');for(const p of items()){const card=el('article','sku-card'+(current()?.id===p.id?' selected':''));const select=button(p.name,()=>{selected[group]=p.id;update();},'sku-select');select.setAttribute('aria-pressed',String(current()?.id===p.id));card.append(select);if(p.term)card.append(el('p','sku-term',p.term));const price=el('div','sku-price',money(p));if(p.original)price.append(el('del','',money(p,p.original)));const buy=button('',()=>{selected[group]=p.id;update();pay(p);},'sku-pay');buy.append(el('span','sku-buy-label',action(p)),el('span','sku-buy-arrow','→'));buy.lastChild.setAttribute('aria-hidden','true');buy.setAttribute('aria-label',action(p)+' '+p.name);card.append(price,buy);rail.append(card);}if(!items().length)rail.append(stateMessage(group));root.append(rail);rail.scrollLeft=scroll[group];}listeners.add(draw);draw();queueMicrotask(()=>{if(root.isConnected)loadCatalog();});root.dispose=()=>listeners.delete(draw);return root;}
export function mountSku(journal,letter){const points=document.querySelector('.points-card');journal.insertBefore(points,letter);journal.insertBefore(skuRail(),letter);journal.classList.add('sku-journal');const css=el('link','');css.rel='stylesheet';css.href='/static/closet-app/sku-fusion.css';document.head.append(css);}
// The purchase center uses the same catalog and selection as the profile rail.
export function skuDetail(options={}){
  if(options.group==='member'||options.group==='points')group=options.group;
  requiredPoints=Number.isFinite(options.requiredPoints)&&options.requiredPoints>0?options.requiredPoints:0;
  if(group==='points'&&requiredPoints)selected.points=null;
  const root=el('sku-purchase-center','sku-details');
  const header=el('header','sku-center-header');
  header.append(button('‹',()=>document.querySelector('#detail-back')?.click(),'sku-center-back'));
  header.firstChild.setAttribute('aria-label','返回');
  const tabs=el('div','sku-center-tabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','会员与积分');
  function choose(key){group=key;update();root.closest('.detail-page')?.scrollTo({top:0});}
  for(const [key,title,icon] of [['member','会员','crown'],['points','积分','star']]){
    const tab=button('',()=>choose(key));tab.id='sku-center-tab-'+key;tab.dataset.group=key;tab.setAttribute('role','tab');tab.setAttribute('aria-controls','sku-center-panel');
    const symbol=el('span','sku-tab-icon');symbol.setAttribute('aria-hidden','true');
    symbol.innerHTML=icon==='crown'?'<svg viewBox="0 0 24 24"><path d="m3 6 5 5 4-7 4 7 5-5-2 14H5Z"/></svg>':'<svg viewBox="0 0 24 24"><path d="m12 3 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1Z"/></svg>';
    tab.append(symbol,el('span','',title));tab.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();choose(keyboardGroup(e.key));tabs.querySelector('[aria-selected=true]').focus();}};tabs.append(tab);
  }
  header.append(tabs);root.append(header);
  const hero=el('section','sku-center-hero');hero.setAttribute('aria-label','爱搭衣橱，日常穿搭陪伴');
  const art=el('img','sku-center-art');applyMembershipBanner(art,bannerPersona);art.alt='';art.width=1774;art.height=887;
  const copy=el('div','sku-center-copy');copy.append(el('p','sku-center-brand','爱搭衣橱'),el('h2','','每天怎么穿，\n我陪你选'),el('p','sku-center-subtitle','懂你的衣橱，也在意你的心情'));hero.append(art,copy);root.append(hero);
  const panel=el('div','sku-center-panel');panel.id='sku-center-panel';panel.setAttribute('role','tabpanel');root.append(panel);
  const catalog=el('section','sku-catalog');catalog.setAttribute('aria-label','方案选择');panel.append(catalog);
  const body=el('div','sku-center-information');panel.append(body);
  const dock=el('div','sku-dock');root.append(dock);const scroll={member:0,points:0};
  function agreement(title){const key={'会员服务协议':'member','连续订阅服务协议':'subscription','积分购买协议':'points'}[title];const url=catalogState().config.data?.agreements?.[key];if(url&&/^https:\/\//.test(url)){const a=el('a','sku-agreement',title);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;}return button(title,()=>window.PreviewMessage.notify('当前服务暂未提供此协议地址，请在正式App查看。'),'sku-agreement');}
  function draw(){
    ensureGroup();
    applyMembershipBanner(art,bannerPersona);
    const focused=root.contains(document.activeElement)?document.activeElement?.dataset.choice:null;
    const old=catalog.querySelector('.sku-rail');if(old)scroll[catalog.dataset.group]=old.scrollLeft;
    root.dataset.group=group;catalog.dataset.group=group;
    panel.setAttribute('aria-labelledby','sku-center-tab-'+group);
    for(const tab of tabs.children){tab.hidden=tab.dataset.group==='member'&&!memberAvailable();const yes=tab.dataset.group===group;tab.setAttribute('aria-selected',String(yes));tab.tabIndex=yes?0:-1;}
    const rail=el('div','sku-rail');
    for(const p of items()){
      const card=el('article','sku-card'+(current()?.id===p.id?' selected':''));
      const select=button('',()=>{selected[group]=p.id;update();},'sku-select');select.dataset.choice=p.id;select.setAttribute('aria-pressed',String(current()?.id===p.id));select.setAttribute('aria-label',p.name+'，'+money(p)+(p.term?'，'+p.term:''));
      select.append(el('span','sku-product-name',p.name));if(p.tag)select.append(el('span','sku-term',p.tag));
      if(p.term)select.append(el('span','sku-term',p.term));
      const price=el('span','sku-price',money(p));if(p.original)price.append(el('del','',money(p,p.original)));select.append(price);card.append(select);rail.append(card);
    }
    catalog.replaceChildren(rail);rail.scrollLeft=scroll[group];
    const p=current();body.replaceChildren();
    const refresh=button('刷新商品与权益',()=>loadCatalog(true),'sku-cancel');body.append(refresh);
    if(!items().length)catalog.append(stateMessage(group));
    const config=catalogState().config;
    if(group==='member'){
      if(active())body.append(el('p','sku-status','当前会员有效中'));
      body.append(benefitsTable());
      if(config.status==='ready'&&Array.isArray(config.data.vip_tip?.desc_list)){
        const info=el('section','sku-center-rules');info.append(el('h3','',config.data.vip_tip.title||'会员说明'));
        for(const text of config.data.vip_tip.desc_list)if(typeof text==='string')info.append(el('p','',text.replace(/<[^>]*>/g,'')));body.append(info);
      }
    }else{
      const rules=el('section','sku-points-rules');rules.append(el('h3','','积分说明'));
      if(p)rules.append(el('p','',p.name+' · '+p.points.toLocaleString('zh-CN')+' 积分'));
      if(p?.description)rules.append(el('p','',p.description));
      rules.append(el('p','sku-disclaimer','有效期、使用顺序及购买条款以正式商品说明和积分购买协议为准。具体功能费用以操作前的实时确认页为准。'));body.append(rules);
    }
    if(config.status==='ready'){
      const costs=el('p','sku-note');for(const [key,title]of [['fitting_cost','试衣'],['prettify_cost','图片润色']]){const v=config.data[key];if(Number.isSafeInteger(v)&&v>=0)costs.append(document.createTextNode(title+' '+v+' 积分／次；'));}if(costs.textContent)body.append(costs);
    }else body.append(stateMessage('config'));
    if(p?.description&&group==='member')body.append(el('p','sku-note',p.description));
    const help=el('details','sku-center-rules');help.append(el('summary','','服务与帮助'));for(const title of ['会员服务协议','连续订阅服务协议','积分购买协议'])help.append(agreement(title));body.append(help);
    if(!p){dock.replaceChildren();dock.hidden=true;}
    else{dock.hidden=false;const row=el('div','sku-dock-row');const price=el('strong','sku-price',money(p));if(p.original)price.append(el('del','',money(p,p.original)));row.append(price,button(action(p)+' '+p.name,()=>pay(p),'sku-pay'));const terms=el('div','sku-dock-terms');terms.append(el('span','','购买前请阅读'),agreement(group==='points'?'积分购买协议':'会员服务协议'));if(p.sub===true)terms.append(agreement('连续订阅服务协议'));dock.replaceChildren(row,terms,el('p','sku-note','后台商品价格 · H5购买仅演示，不扣款、不变更积分'));}
    if(focused)root.querySelector(`[data-choice="${focused}"]`)?.focus({preventScroll:true});
  }
  root.render=draw;draw();
  return root;
}
window.addEventListener('yijian-account-loaded',e=>{account=e.detail;update();});
window.addEventListener('yijian-account-reset',()=>{account=null;group='member';selected={member:null,points:null};closePay();update();});
window.addEventListener('yijian-session-change',closePay);

window.addEventListener('yijian-user-profile',e=>{
  const token=bannerSession();
  if(e.detail?.ownerToken!==token)return;
  bannerOwner=token;bannerPersona=membershipPersona(e.detail?.profile?.assistant_persona);update();
});
window.addEventListener('yijian-session-change',resetBanner);
window.addEventListener('yijian-account-reset',resetBanner);

subscribeCatalog(update);
