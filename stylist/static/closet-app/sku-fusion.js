import {membershipPersona,applyMembershipBanner} from './membership-banners.js';
// Design fixtures only. This module never creates orders, calls StoreKit or changes balances.
export {careCopy} from './care-copy.js';
const products={member:[{id:'m',name:'SVIP 月卡',price:19,term:'一个月 · 单次购买'},{id:'y',name:'SVIP 年卡',price:168,original:228,term:'一年 · 单次购买'},{id:'s',name:'SVIP 连续包月',price:15,term:'¥15／月 · 自动续费',sub:true},{id:'l',name:'VIP 永久会员',price:299,term:'永久 · 单次购买'}],points:[{id:'p1',name:'100 积分',price:12,term:''},{id:'p2',name:'500 积分',price:48,term:''},{id:'p3',name:'1,000 积分',price:88,term:''}]};
let group='member',selected={member:'y',points:'p1'},account=null,payment=null,epoch=0;
let bannerPersona='male_calm_v1',bannerOwner=null;
function bannerSession(){try{return JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')||'null')?.access_token||'';}catch{return '';}}
function resetBanner(){const owner=bannerSession();if(!owner||owner!==bannerOwner){bannerOwner=owner;bannerPersona='male_calm_v1';update();}}
const listeners=new Set();
// History may detach and restore a detail node. Subscribe only while mounted.
customElements.define('sku-purchase-center',class extends HTMLElement{
  connectedCallback(){if(this.render){listeners.add(this.render);this.render();}}
  disconnectedCallback(){listeners.delete(this.render);}
});
function el(tag,cls,text){const e=document.createElement(tag);e.className=cls;if(text)e.textContent=text;return e;}
function button(text,action,cls=''){const b=el('button',cls,text);b.type='button';b.onclick=action;return b;}
function items(){return group==='member'&&Number(account?.vip_info?.vip_type)===5&&account?.vip_info?.is_vip?products.member.filter(p=>p.sub):products[group];}
function current(){return items().find(p=>p.id===selected[group])||items()[0];}
function active(){return account?.vip_info?.is_vip===true||account?.vip_info?.is_vip===1;}
function action(p){return p.sub&&account?.vip_info?.is_subscribing===1?'管理订阅':p.id.startsWith('p')?'购买':active()?'续费':'开通';}
function update(){for(const draw of listeners)draw();}
function closePay(){epoch++;if(payment){payment.close();payment.remove();payment=null;}}
function pay(p){if(payment)return;const dialog=el('dialog','sku-payment');payment=dialog;dialog.dataset.appDialog='sku-payment';dialog.setAttribute('aria-label','购买交互演示');const ticket=++epoch;const close=()=>{closePay();window.PreviewMessage.notify('取消支付（演示）');};dialog.append(button('×',close,'sku-payment-close'),el('p','sku-note','iOS支付交互示意 · 非系统弹窗'),el('h2','','正在支付…'));document.body.append(dialog);dialog.showModal();dialog.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close();}});dialog.addEventListener('cancel',e=>{e.preventDefault();close();});setTimeout(()=>{if(ticket!==epoch)return;dialog.querySelector('h2').textContent=p.name;dialog.append(el('p','',p.term),el('strong','sku-price','¥'+p.price),el('p','',p.sub?'每月自动续费。示例价格，正式资格与条款以App Store为准。':'单次购买，不自动续费。'),el('p','sku-note','仅演示，不创建订单、扣款或变更积分。'),button(action(p)+'（演示）',()=>{closePay();if(action(p)!=='管理订阅'&&!document.querySelector('#detail-page')?.hidden)document.querySelector('#detail-back')?.click();window.PreviewMessage.notify(action(p)==='管理订阅'?'订阅管理尚未接入，此处仅演示。':'购买成功（演示），未发生扣款。');},'sku-pay'),button('取消',close,'sku-cancel'));},250);}
export function skuRail(){const root=el('section','sku-catalog');root.setAttribute('aria-label','会员与积分方案（设计示例）');const scroll={member:0,points:0};function draw(){const old=root.querySelector('.sku-rail');if(old)scroll[root.dataset.group]=old.scrollLeft;root.dataset.group=group;root.replaceChildren();const tabs=el('div','sku-tabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','商品类型');for(const [key,title]of [['member','会员方案'],['points','积分包']]){const tab=button(title,()=>{group=key;update();});tab.setAttribute('role','tab');tab.setAttribute('aria-selected',String(group===key));tab.tabIndex=group===key?0:-1;tab.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();group=e.key==='Home'?'member':e.key==='End'?'points':group==='member'?'points':'member';update();root.querySelector('[aria-selected=true]').focus();}};tabs.append(tab);}root.append(tabs);const rail=el('div','sku-rail');for(const p of items()){const card=el('article','sku-card'+(current().id===p.id?' selected':''));const select=button(p.name,()=>{selected[group]=p.id;update();},'sku-select');select.setAttribute('aria-pressed',String(current().id===p.id));card.append(select);if(p.term)card.append(el('p','sku-term',p.term));const price=el('div','sku-price');price.append(el('small','','¥'),document.createTextNode(String(p.price)));if(p.original)price.append(el('del','','¥'+p.original));const buy=button('',()=>{selected[group]=p.id;update();pay(p);},'sku-pay');buy.append(el('span','sku-buy-label',action(p)),el('span','sku-buy-arrow','→'));buy.lastChild.setAttribute('aria-hidden','true');buy.setAttribute('aria-label',action(p)+' '+p.name);card.append(price,buy);rail.append(card);}root.append(rail);rail.scrollLeft=scroll[group];}listeners.add(draw);draw();root.dispose=()=>listeners.delete(draw);return root;}
export function mountSku(journal,letter){const points=document.querySelector('.points-card');journal.insertBefore(points,letter);journal.insertBefore(skuRail(),letter);journal.classList.add('sku-journal');const css=el('link','');css.rel='stylesheet';css.href='/static/closet-app/sku-fusion.css';document.head.append(css);}
// The purchase center uses the same catalog and selection as the profile rail.
export function skuDetail(options={}){
  if(options.group==='member'||options.group==='points')group=options.group;
  if(group==='points'&&options.group==='points'){
    const needed=Number.isFinite(options.requiredPoints)&&options.requiredPoints>0?options.requiredPoints:0;
    selected.points=(products.points.find((p,i)=>[100,500,1000][i]>=needed)||products.points.at(-1)).id;
  }
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
    tab.append(symbol,el('span','',title));tab.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();choose(e.key==='Home'?'member':e.key==='End'?'points':group==='member'?'points':'member');tabs.querySelector('[aria-selected=true]').focus();}};tabs.append(tab);
  }
  header.append(tabs);root.append(header);
  const hero=el('section','sku-center-hero');hero.setAttribute('aria-label','爱搭衣橱，日常穿搭陪伴');
  const art=el('img','sku-center-art');applyMembershipBanner(art,bannerPersona);art.alt='';art.width=1774;art.height=887;
  const copy=el('div','sku-center-copy');copy.append(el('p','sku-center-brand','爱搭衣橱'),el('h2','','每天怎么穿，\n我陪你选'),el('p','sku-center-subtitle','懂你的衣橱，也在意你的心情'));hero.append(art,copy);root.append(hero);
  const panel=el('div','sku-center-panel');panel.id='sku-center-panel';panel.setAttribute('role','tabpanel');root.append(panel);
  const catalog=el('section','sku-catalog');catalog.setAttribute('aria-label','方案选择');panel.append(catalog);
  const body=el('div','sku-center-information');panel.append(body);
  const dock=el('div','sku-dock');root.append(dock);const scroll={member:0,points:0};
  function agreement(title){return button(title,()=>window.PreviewMessage.notify('此处为设计演示，'+title+'尚未接入。'),'sku-agreement');}
  function draw(){
    applyMembershipBanner(art,bannerPersona);
    const focused=root.contains(document.activeElement)?document.activeElement?.dataset.choice:null;
    const old=catalog.querySelector('.sku-rail');if(old)scroll[catalog.dataset.group]=old.scrollLeft;
    root.dataset.group=group;catalog.dataset.group=group;
    panel.setAttribute('aria-labelledby','sku-center-tab-'+group);
    for(const tab of tabs.children){const yes=tab.dataset.group===group;tab.setAttribute('aria-selected',String(yes));tab.tabIndex=yes?0:-1;}
    const rail=el('div','sku-rail');
    for(const p of items()){
      const card=el('article','sku-card'+(current().id===p.id?' selected':''));
      const select=button('',()=>{selected[group]=p.id;update();},'sku-select');select.dataset.choice=p.id;select.setAttribute('aria-pressed',String(current().id===p.id));select.setAttribute('aria-label',p.name+'，'+p.price+'元'+(p.term?'，'+p.term:''));
      select.append(el('span','sku-product-name',p.name));
      if(p.term)select.append(el('span','sku-term',p.term));
      const price=el('span','sku-price');price.append(el('small','','¥'),document.createTextNode(String(p.price)));if(p.original)price.append(el('del','','¥'+p.original));select.append(price);card.append(select);rail.append(card);
    }
    catalog.replaceChildren(rail);rail.scrollLeft=scroll[group];
    const p=current();body.replaceChildren();
    if(group==='member'){
      if(active())body.append(el('p','sku-status','当前会员有效中'));
      const benefits=el('section','sku-benefits');benefits.innerHTML='<h3>会员权益对比</h3><div class="sku-table-wrap"><table><thead><tr><th scope="col">权益</th><th scope="col">普通用户</th><th scope="col">VIP</th><th scope="col">SVIP</th></tr></thead><tbody><tr><th scope="row">每月赠送积分</th><td>—</td><td>—</td><td>2,000</td></tr><tr><th scope="row">衣橱容量</th><td>示例基础容量</td><td>示例会员容量</td><td>示例会员容量</td></tr><tr><th scope="row">AI试穿</th><td>积分使用</td><td>积分使用</td><td>积分使用</td></tr></tbody></table></div><p class="sku-disclaimer">权益为示例，正式内容以商品页面为准。</p>';body.append(benefits);
      const rules=el('details','sku-center-rules');rules.append(el('summary','','购买与续费说明'));
      for(const text of ['单次月卡、年卡到期不自动续费；连续包月按周期自动续费。永久会员走独立规则。','单次续费只延长服务时长，当前月度周期不重算、不重复发放。连续订阅续费后发放新月度积分，原月度积分按现有规则冻结并留作最后一期发放。','月度积分与衣橱容量由商品权益提供，不等于无限对话或无限试穿。优惠原价及资格以真实商品与StoreKit为准。'])rules.append(el('p','',text));body.append(rules);
    }else{
      const rules=el('section','sku-points-rules');rules.append(el('h3','','积分说明'));const list=el('ul','');for(const text of ["积分有效期为自购买时刻起2年，到期未使用积分自动失效。", "购买积分与会员赠送积分相互独立，消耗时优先扣减会员赠送积分。", "可多次购买积分，每次购买单独计算有效期。购买积分消耗时优先扣减最早到期的积分批次。", "积分不可提现、不可转让，仅限本账号内使用。", "支付成功后积分立即到账，如有问题请根据「个人中心」提供的方式联系我们。"])list.append(el('li','',text));rules.append(list);rules.append(el('p','sku-disclaimer','积分包不开通会员，也不扩大衣橱容量。Agent对话按输入、输出各自累计，每满100万token各使用300积分。'));body.append(rules);
    }
    const help=el('details','sku-center-rules');help.append(el('summary','','服务与帮助'));for(const title of ['会员服务协议','连续订阅服务协议','积分购买协议','购买未到账？'])help.append(agreement(title));body.append(help);
    const row=el('div','sku-dock-row');const price=el('strong','sku-price','¥'+p.price);if(p.original)price.append(el('del','','¥'+p.original));const buy=button(action(p)+' '+p.name,()=>pay(p),'sku-pay');row.append(price,buy);
    const terms=el('div','sku-dock-terms');terms.append(el('span','','购买前请阅读'),agreement(group==='points'?'积分购买协议':'会员服务协议'));if(p.sub)terms.append(agreement('连续订阅服务协议'));
    dock.replaceChildren(row,terms,el('p','sku-note','示例金额 · 购买仅演示，不扣款、不变更积分'));
    if(focused)root.querySelector(`[data-choice="${focused}"]`)?.focus({preventScroll:true});
  }
  root.render=draw;draw();
  return root;
}
window.addEventListener('yijian-account-loaded',e=>{account=e.detail;update();});
window.addEventListener('yijian-account-reset',()=>{account=null;group='member';selected={member:'y',points:'p1'};closePay();update();});
window.addEventListener('yijian-session-change',closePay);

window.addEventListener('yijian-user-profile',e=>{
  const token=bannerSession();
  if(e.detail?.ownerToken!==token)return;
  bannerOwner=token;bannerPersona=membershipPersona(e.detail?.profile?.assistant_persona);update();
});
window.addEventListener('yijian-session-change',resetBanner);
window.addEventListener('yijian-account-reset',resetBanner);
