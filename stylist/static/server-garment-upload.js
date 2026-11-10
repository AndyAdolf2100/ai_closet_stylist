'use strict';
(() => {
  const base='https://aicloset-dev.wxbjq.top';
  const session=()=>{try{return JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')||'null')||{};}catch{return {};}};
  const owner=()=>String(session().user?.id||session().user?.user_id||'');
  const key=()=>owner()?'server-garment-tasks:'+owner():null;
  const read=()=>{try{return JSON.parse(sessionStorage.getItem(key())||'[]');}catch{return [];}};
  const memory=new Map();
  function remember(action){if(action.owner!==owner())return action;memory.set(action.action_id,action);if(key()){try{const rows=read().filter(r=>r.action_id!==action.action_id);sessionStorage.setItem(key(),JSON.stringify([action,...rows].slice(0,30)));}catch{/* Storage limits do not prevent the in-memory task from being followed. */}}window.dispatchEvent(new CustomEvent('server-garment-update',{detail:JSON.parse(JSON.stringify(action))}));return JSON.parse(JSON.stringify(action));}
  function get(id){if(!owner())throw Error('请重新登录后查看任务。');const action=memory.get(id)||read().find(r=>r.action_id===id);if(!action||action.owner!==owner())throw Error('当前账号找不到这次上传，请重新查看。');return action;}
  async function request(path,{method='GET',body,form}={}){
    const token=session().access_token;if(!token)throw Error('请先登录。');
    const response=await fetch(base+path,{method,headers:{Authorization:'Bearer '+token,version:'2.1.0',...(body?{'Content-Type':'application/json'}:{})},...(form?{body:form}:body?{body:JSON.stringify(body)}:{}),cache:'no-store'});
    const data=await response.json().catch(()=>null);if(session().access_token!==token)throw Error('账号已变化，已忽略之前的上传结果。');if(!response.ok||data?.code!==0){const error=Error(data?.msg||'上传任务暂未完成，请核对原任务。');error.code=data?.code;error.httpStatus=response.status;throw error;}return data.data;
  }
  async function start(image,requestId){
    if(!owner())throw Error('请重新登录后上传。');const id='server_'+requestId,existing=memory.get(id)||read().find(r=>r.action_id===id);if(existing){if(existing.owner!==owner())throw Error('账号已变化。');return JSON.parse(JSON.stringify(existing));}
    const action={action_id:id,owner:owner(),kind:'garment',created_at:new Date().toISOString(),status:'processing',result:{protocol:'server_direct',stage:'uploading'}};remember(action);
    try{const [header,encoded]=image.split(','),mime=header.slice(5).split(';')[0],bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0)),form=new FormData();form.append('file',new Blob([bytes],{type:mime}),'wardrobe.'+({ 'image/png':'png','image/jpeg':'jpg','image/webp':'webp'}[mime]||'jpg'));form.append('upload_type','product');
      const file=await request('/api/upload/file',{method:'POST',form});if(!file?.url)throw Error('图片地址待确认，请勿重复上传。');action.result.stage='creating_task';remember(action);
      const task=await request('/api/user_product/upload',{method:'POST',body:{urls:[file.url],from_source:1}});if(!task?.task_id)throw Error('任务编号待确认，请勿重复创建。');action.result.task_id=task.task_id;action.result.stage='segmenting';return remember(action);
    }catch(error){const rejected=[43510,43511].includes(error.code);action.status=rejected?'failed':'unknown';action.result.stage=rejected?'capacity_blocked':action.result.stage;action.result.error_code=error.code;action.result.message=rejected?error.message:error.message+' 本次不会自动重交。';remember(action);throw error;}
  }
  function finishProducts(action,products){
    const r=action.result;r.products=products;r.stage='beautifying';
    const done=products.length&&products.every(p=>p.beautify_status===2||(p.beautify_status===1&&Number(p.user_product_id)>0));
    if(done){const completed=products.filter(p=>p.beautify_status===1);r.selection_required=false;r.completed_count=completed.length;r.failed_count=products.length-completed.length;r.stage='finished';action.status=completed.length?'completed':'failed';if(completed.length===1)r.user_product_id=completed[0].user_product_id;}
    return done;
  }
  async function refresh(id){
    const action=get(id),r=action.result;if(!r.task_id||['completed','failed','cancelled'].includes(action.status))return JSON.parse(JSON.stringify(action));
    const detail=await request('/api/user_product/upload/task/detail?task_id='+encodeURIComponent(r.task_id));
    const items=Array.isArray(detail.selection_items)?detail.selection_items:[],state=detail.selection_state;
    Object.assign(r,{progress:detail.progress,selection_state:state,selection_items:items});
    // selection_required marks this upload flow, not whether a choice is still pending.
    if(state===3){r.selection_required=false;r.stage='cancelled';action.status='cancelled';return remember(action);}
    const waiting=Boolean(detail.selection_required)&&(state===1||state==null);
    r.selection_required=waiting;
    if(waiting){r.stage=items.length?'selecting':'segmenting';action.status=items.length?'awaiting_selection':'processing';return remember(action);}
    action.status='processing';
    const selected=state===2?items.filter(p=>p.selection_status===2):[];
    if(state===2){r.selection_submitted_ids=selected.map(p=>p.detail_id);if(finishProducts(action,selected))return remember(action);}
    if(!detail.is_finish&&state!==2){r.stage='segmenting';return remember(action);}
    if(detail.has_segmentation_success===false&&state!==2){action.status='failed';r.message='未能识别出可用单品。';return remember(action);}
    const result=await request('/api/user_product/task_product_detail?task_id='+encodeURIComponent(r.task_id));
    const products=Array.isArray(result?.products)?result.products:[];
    const byId=new Map(products.map(p=>[String(p.user_product_id),p]));
    // Do not finish early when the product projection is still missing a selected item.
    finishProducts(action,selected.length?selected.map(p=>({...p,...(byId.get(String(p.user_product_id))||{})})):products);
    return remember(action);
  }

  async function select(id,ids){const action=get(id),r=action.result,selected=[...new Set(ids)].sort((a,b)=>a-b);if(r.selection_submitted_ids){if(JSON.stringify(r.selection_submitted_ids)!==JSON.stringify(selected))throw Error('本次选择已提交，请查看原任务。');return refresh(id);}
    const valid=new Set((r.selection_items||[]).map(i=>Number(i.detail_id)));if(!r.selection_required||selected.some(n=>!Number.isSafeInteger(n)||!valid.has(n)))throw Error('候选单品已变化，请重新核对。');r.selection_submitted_ids=selected;r.stage='submitting_selection';action.status='processing';remember(action);
    try{await request('/api/user_product/upload/task/selection',{method:'POST',body:{task_id:r.task_id,selected_detail_ids:selected}});r.selection_required=false;r.stage=selected.length?'beautifying':'cancelled';action.status=selected.length?'processing':'cancelled';return remember(action);}catch(error){const rejected=[43510,43511].includes(error.code);action.status=rejected?'failed':'unknown';if(rejected){r.selection_required=false;r.stage='capacity_blocked';}r.message=rejected?error.message:'选择结果待确认，只查询原任务，不会重复提交。';error.action=remember(action);throw error;}
  }
  window.ServerGarmentUpload={start,refresh,select,list:()=>read().filter(a=>a.owner===owner()),clear:()=>memory.clear()};
})();
