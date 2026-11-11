// Native iOS contracts: garment status/start_garment and outfit start_fitting/progress.
const base='https://aicloset-dev.wxbjq.top', pending=new Map();
const token=()=>{try{return JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')||'null')?.access_token;}catch{return null;}};
const savedKey=t=>{try{const user=JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')).user;return 'detail-fitting:'+String(user.id||user.user_id)+':'+t.kind+':'+t.id;}catch{return null;}};
function remember(action){if(token()!==action.owner)return action;pending.set(action.key,action);const key=savedKey(action.target);if(key){const {owner,...data}=action;try{sessionStorage.setItem(key,JSON.stringify({...data,key:null}));}catch{}}return action;}
async function request(owner,path,body){
 if(!owner||token()!==owner)throw Error('账号已变化，请重新打开详情。');
 const response=await fetch(base+path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+owner,version:'2.1.0',...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{}),cache:'no-store'});
 const json=await response.json();if(token()!==owner)throw Error('账号已变化，已忽略原任务结果。');
 if(!response.ok||json.code!==0)throw Object.assign(Error(json.msg||'试穿信息暂不可用，请稍后重试。'),{business:response.ok&&Number.isInteger(json.code)});
 return json.data;
}
export function detailTryonButton(kind,item,{button,openAgent,readSession}){
 const owner=readSession()?.access_token,id=kind==='product'?String(item.user_product_id??''):String(item.outfit_id??'');
 const valid=/^[1-9][0-9]*$/.test(id)&&Number.isSafeInteger(Number(id))&&(kind==='product'||Number(item.outfit_id_type)===2);
 const control=button('生成试穿',async()=>{if(!valid||control.disabled)return;if(!owner)return openAgent('login');if(readSession()?.access_token!==owner)return;control.disabled=true;try{await openAgent('detail-tryon',{detail_target:{kind,id},title:item.title||item.name||(kind==='product'?'这件单品':'这套搭配')});}finally{control.disabled=!valid;}},'y-service-primary detail-tryon-entry');control.disabled=!valid;return control;
}
window.DetailTryon={
 retry(action){if(token()!==action.owner||action.status!=='failed')throw Error('请先确认原任务状态。');pending.delete(action.key);sessionStorage.removeItem(savedKey(action.target));},
 async inspect(ref){
  const owner=token(),t=ref.detail_target,key=owner+':'+t.kind+':'+t.id;
  if(pending.has(key))return pending.get(key);
  try{const saved=JSON.parse(sessionStorage.getItem(savedKey(t))||'null');if(saved&&['processing','unknown'].includes(saved.status)){const action={...saved,owner,key};pending.set(key,action);return action;}}catch{}
  const data=await request(owner,t.kind==='product'?'/api/user_product/fitting_status?user_product_id='+t.id:'/api/user_outfit/detail?outfit_id='+t.id);
  if(![0,1,2].includes(data?.fitting_status))throw Error('暂未读取到试穿状态，请稍后重试。');
  const action={owner,key,target:t,status:['idle','processing','completed'][data.fitting_status],task_id:data.fitting_id,image:data.fitting_image_url};
  if(action.status==='completed'&&!action.image)throw Error('试穿图片暂未返回，请稍后重新查看。');
  if(action.status!=='idle')remember(action);return action;
 },
 async prepare(action){await request(action.owner,'/algorithm/api/fitting/count');const config=await request(action.owner,'/api/app_config/config_check');if(!Number.isFinite(config.fitting_cost)||config.fitting_cost<0)throw Error('暂未读取到本次试穿积分。');return config.fitting_cost;},
 async start(action){
  if(token()!==action.owner)throw Error('账号已变化，请重新打开详情。');
  if(pending.has(action.key))return pending.get(action.key);
  action.status='unknown';remember(action);
  try{const t=action.target,data=await request(action.owner,t.kind==='product'?'/algorithm/api/fitting/start_garment':'/algorithm/api/fitting/start_fitting',t.kind==='product'?{source_type:'garment',user_product_id:Number(t.id),client_request_id:crypto.randomUUID()}:{fitting_type:1,outfit_id:Number(t.id)});
   if(!Number.isSafeInteger(data?.task_id)||data.task_id<=0)throw Error('提交结果待确认，请勿重复生成。');
   action.task_id=data.task_id;action.status=data.status==='failed'?'failed':'processing';
  }catch(e){action.message=e.message;if(e.business)action.status='failed';}return remember(action);
 },
 async refresh(action){
  const t=action.target;
  if(t.kind==='product'||!action.task_id){const d=await request(action.owner,t.kind==='product'?'/api/user_product/fitting_status?user_product_id='+t.id:'/api/user_outfit/detail?outfit_id='+t.id);
   if(d.fitting_status===2&&d.fitting_image_url){action.status='completed';action.image=d.fitting_image_url;}
   else if(d.fitting_status===1){action.status='processing';action.task_id=d.fitting_id;}
   else if(d.fitting_status===0&&action.task_id){action.status='failed';action.message=d.fitting_failure_message||'本次试穿未成功。';}
  }else{const d=await request(action.owner,'/algorithm/api/fitting/progress',{task_id:action.task_id});if(d.status===1&&d.fitting_image_url){action.status='completed';action.image=d.fitting_image_url;}else if(d.status===2){action.status='failed';action.message='本次试穿未成功。';}}
  return remember(action);
 }
};
