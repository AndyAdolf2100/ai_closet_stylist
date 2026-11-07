// Server is the authority for sale eligibility, SKU order, prices and benefit columns.
// No fixture fallback, cross-account storage, orders or paid operations.
const sections=['member','points','benefits','config'];
const fresh=()=>Object.fromEntries(sections.map(k=>[k,{status:'idle',data:null,error:''}]));
let state=fresh(),owner='',generation=0,controller=null,inflight=null;
const listeners=new Set();
export function purchaseOwner(){try{return JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')||'null')?.access_token||'';}catch{return '';}}
const validAmount=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
function invalid(){throw Error('商品资料不完整，请重新读取。');}
function products(value,points){
  if(!Array.isArray(value))invalid();const ids=new Set();
  return value.map(p=>{
    const id=points?p.id:p.product_id;
    if(!['string','number'].includes(typeof id)||!String(id).trim()||!String(p.name||'').trim()||!validAmount(p.price)||ids.has(String(id)))invalid();
    if(points&&(!Number.isSafeInteger(p.points_amount)||p.points_amount<0))invalid();ids.add(String(id));
    const rawSubscription=p.is_subscription??p.extra?.is_subscription;
    return {id:String(id),name:String(p.name),price:p.price,currency:typeof p.currency==='string'?p.currency:'',
      original:validAmount(p.original_price)&&p.original_price>p.price?p.original_price:null,
      term:typeof p.sub_title==='string'?p.sub_title:'',description:typeof p.description==='string'?p.description:'',
      recommended:p.is_recommend===true,tag:typeof p.tag==='string'?p.tag:'',
      points:points?p.points_amount:null,sub:rawSubscription===true||rawSubscription===1?true:rawSubscription===false||rawSubscription===0?false:null};
  });
}
function normalize(section,data){
  if(!data||typeof data!=='object'||Array.isArray(data))invalid();
  if(section==='member')return products(data.products,false);
  if(section==='points')return products(data.list,true);
  if(section==='benefits'){
    const t=data.benefit_table;
    if(!t||!Array.isArray(t.columns)||!Array.isArray(t.rows))invalid();
    const ids=new Set();
    for(const c of t.columns){if(typeof c.id!=='string'||!c.id||typeof c.header!=='string'||ids.has(c.id))invalid();ids.add(c.id);}
    for(const row of t.rows){if(typeof row.name!=='string'||!Array.isArray(row.values)||row.values.length!==t.columns.length||row.values.some(v=>!v||!['text','check','cross'].includes(v.type)))invalid();}
    return data;
  }
  return data;
}
function notify(){for(const fn of listeners)fn();}
function reset(){generation++;controller?.abort();controller=null;inflight=null;owner=purchaseOwner();state=fresh();notify();}
export function catalogState(){if(owner!==purchaseOwner())reset();return state;}
export function subscribeCatalog(fn){listeners.add(fn);return()=>listeners.delete(fn);}
export function loadCatalog(force=false){
  if(owner!==purchaseOwner())reset();
  if(inflight)return inflight;
  if(!force&&sections.every(k=>state[k].status==='ready'))return Promise.resolve();
  const token=owner;if(!token){state=fresh();notify();return Promise.resolve();}
  const ticket=++generation;controller=new AbortController();const signal=controller.signal;
  for(const k of sections)state[k]={status:'loading',data:null,error:''};notify();
  const job=Promise.all(sections.map(async section=>{
    let next;
    try{
      const response=await fetch('/stylist-api/app/purchase/'+section,{headers:{Authorization:'Bearer '+token},cache:'no-store',signal});
      const body=await response.json();if(!response.ok)throw Error(response.status===401?'登录已过期，请重新连接衣橱。':body.message||'暂时没有读到，请重试。');
      next={status:'ready',data:normalize(section,body.data),error:''};
    }catch(e){if(e.name==='AbortError')return;next={status:'error',data:null,error:e.message||'暂时没有读到，请重试。'};}
    if(ticket!==generation||token!==purchaseOwner())return;
    state[section]=next;notify();
  })).finally(()=>{if(ticket===generation)inflight=null;});
  inflight=job;return job;
}
for(const event of ['yijian-account-reset','yijian-session-change'])window.addEventListener(event,()=>{reset();if(listeners.size)loadCatalog();});
