// Fresh, account-bound reads of the existing ledger. No balance cache or local mutation.
const key='ai-closet-stylist-session-v1';
const token=()=>{try{return JSON.parse(sessionStorage.getItem(key)||'null')?.access_token||'';}catch{return '';}};
let generation=0;window.addEventListener('yijian-account-reset',()=>generation++);
export async function readAvailablePoints(){
 const owner=token(),ticket=generation;if(!owner)throw new Error('请先登录后查看可用积分。');
 const response=await fetch('/stylist-api/app/points',{headers:{Authorization:'Bearer '+owner},cache:'no-store'});
 const payload=await response.json().catch(()=>null);
 if(ticket!==generation||owner!==token())throw new DOMException('账号已切换','AbortError');
 if(!response.ok)throw new Error(payload?.message||'暂时无法查询可用积分，请稍后重试。');
 const balance=payload?.data?.total_available;
 if(typeof balance!=='number'||!Number.isFinite(balance)||balance<0)throw new Error('可用积分暂时无法确认，请稍后重试。');
 window.dispatchEvent(new CustomEvent('yijian-points-loaded',{detail:{ownerToken:owner,total_available:balance}}));
 return balance;
}
