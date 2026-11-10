'use strict';
(() => {
  let owner=null, epoch=0, api=null, notify=null, onStyle=null,onProduct=null, getConversation=null, getContext=null, onRegenerate=null, onNeedOutfit=null, timer=null, previewURL=null, opener=null;
  let pendingLook=null, activeQuote=null, viewSequence=0,closeLocked=false;
  let activeTryon=null;
  const points=value=>Number.isFinite(Number(value))&&value!==null&&value!==''?Number(value).toLocaleString('en-US',{maximumFractionDigits:20}):'—';
  const watchers=new Map(),finished=new Set();
  const $=id=>document.getElementById(id);
  const el=(tag,cls='',text='')=>{const n=document.createElement(tag);n.className=cls;n.textContent=text;return n;};
  const loading=message=>window.CompanionLoading?.create({message,size:'small'})||el('p','journey-note',message);
  async function readLoading(target,message,read){
    const indicator=loading(message);target.append(indicator);
    try{return await read();}finally{indicator.remove();}
  }
  const button=(text,run,primary=false)=>{const b=el('button',primary?'primary':'',text);b.type='button';b.onclick=()=>guard(b,run);return b;};
  const imageURL=value=>{try{const u=new URL(String(value||'').replace(/^http:/i,'https:'));return u.protocol==='https:'?u.href:'';}catch{return '';}};
  const dialog=el('dialog','journey-dialog');dialog.id='journey-dialog';dialog.setAttribute('aria-labelledby','journey-title');
  const heading=el('div','journey-heading'),title=el('h2');title.id='journey-title';
  const close=button('关闭 ×',()=>{if(!closeLocked)dialog.close();});close.setAttribute('aria-label','关闭上传与试穿面板');
  const chapter=el('span','journey-chapter','爱搭衣橱 · 日常小记');
  const headingCopy=el('div','journey-heading-copy');headingCopy.append(chapter,title);heading.append(headingCopy,close);
  const scene=el('div','journey-scene'),steps=el('ol','journey-steps'),body=el('div','journey-body'),footer=el('div','journey-footer');
  const sheetHandle=el('div','journey-sheet-handle');sheetHandle.setAttribute('aria-hidden','true');dialog.append(sheetHandle,heading,scene,steps,body,footer);document.body.append(dialog);
  function atmosphere(kind='garment',step=0){
    dialog.dataset.flow=kind;
    const male=document.documentElement.dataset.stylistGender==='male';
    const name=window.CompanionSettings?.agentName?.()||'衣衣';
    const portrait=el('span','journey-companion-frame'),art=el('span','journey-companion journey-dialogue-avatar companion-dialogue-avatar');art.setAttribute('aria-hidden','true');
    portrait.append(art);
    const copy=el('div','journey-scene-copy');
    const lines={garment:male?'从一件熟悉的衣服开始，慢慢整理你的日常。':'喜欢的衣服，值得在这里拥有自己的位置。',person:male?'选好试穿的模样，再看看这套衣服。':'先选一个喜欢的模样，再一起看看上身的感觉。',quote:'这一次需要的积分，都写在这里。你决定好了，我们再开始。',history:'每一件新衣、每一次尝试，都收在这里。'};
    copy.append(el('span','journey-speaker',name+' 的小笺'),el('p','',lines[kind]||lines.garment));scene.replaceChildren(portrait,copy,el('span','journey-scene-flower','✧'));
    const labels=kind==='garment'?['选一张照片','整理入衣橱','开始新搭配']:['选择形象','查看新模样'];
    if(kind!=='garment')step=step>0?1:0;
    steps.replaceChildren();steps.hidden=kind==='history';
    labels.forEach((label,i)=>{const item=el('li',i===step?'is-current':i<step?'is-done':'');item.append(el('span','journey-step-number',i<step?'✓':String(i+1).padStart(2,'0')),el('span','',label));if(i===step)item.setAttribute('aria-current','step');steps.append(item);});
  }
  function dock(...controls){footer.replaceChildren(...controls);}
  const current=token=>owner!==null&&token===epoch;
  function validContext(ref){
    if(!ref)return true;
    const state=getContext?.();
    return state?state.conversation_id===ref.conversation_id&&state.version===ref.version:!getConversation||getConversation()===ref.conversation_id;
  }
  function requireContext(ref){if(!validContext(ref))throw Error('这套搭配已更新，请从当前对话重新选择形象。');}
  const sameConversation=action=>!action.conversation_id||!getConversation||getConversation()===action.conversation_id;
  const tryonImage=action=>imageURL(action.result?.result_image_url)||imageURL(action.result?.result_image);
  const verifiedTryon=action=>action.status==='completed'&&!tryonImage(action)?{...action,status:'unknown'}:action;
  const clearTimer=()=>{clearTimeout(timer);timer=null;};
  function releasePhoto(){if(previewURL)URL.revokeObjectURL(previewURL);previewURL=null;}
  function lockClose(value){closeLocked=Boolean(value);close.disabled=closeLocked;dialog.dataset.processing=String(closeLocked);close.title=closeLocked?'正在处理，请稍候':'关闭';}
  function show(name){
    if(!owner)return;
    lockClose(false);viewSequence++;scene.hidden=false;activeTryon=null;clearTimer();releasePhoto();delete dialog.dataset.status;delete dialog.dataset.quoteKind;delete dialog.dataset.panel;title.textContent=name;body.replaceChildren();footer.replaceChildren();atmosphere();
    if(!dialog.open){opener=document.activeElement;dialog.showModal();close.focus();}
  }
  async function guard(control,run){
    if(control.disabled)return;control.disabled=true;const token=epoch;
    try{await run();}catch(e){if(current(token)&&!e.paymentHandled)notify?.(e.message||'操作未完成，请稍后重试。');}
    finally{if(current(token))control.disabled=false;}
  }
  function photo(url,alt){
    const src=imageURL(url);if(!src)return null;
    const b=el('button','journey-image'),img=el('img');img.src=src;img.alt=alt;img.referrerPolicy='no-referrer';
    b.type='button';b.setAttribute('aria-label','放大'+alt);b.append(img);
    b.onclick=()=>window.ProductPreview?.open([{src,alt}],0,b);
    img.onerror=()=>{b.replaceChildren(el('p','','图片暂时无法加载，请稍后查看。'));};return b;
  }
  function appendPhoto(url,alt,target=body){const p=photo(url,alt);if(p)target.append(p);}
  function photoDataURL(value){
    const encoded=String(value).split(',')[1]||'';
    let signature='';try{signature=atob(encoded.slice(0,24));}catch{}
    const mime=signature.startsWith('\x89PNG\r\n\x1a\n')?'image/png':signature.startsWith('\xff\xd8\xff')?'image/jpeg':signature.startsWith('RIFF')&&signature.slice(8,12)==='WEBP'?'image/webp':null;
    if(!mime)throw Error('这张文件不是可识别的JPG、PNG或WebP图片，请重新选择。');
    return `data:${mime};base64,${encoded}`;
  }
  async function composePhotos(files,readPhoto,alive){
    const columns=files.length<=4?2:3,rows=Math.ceil(files.length/columns),gap=16;
    const tile=Math.min(768,Math.floor((3072-gap*(Math.max(columns,rows)+1))/Math.max(columns,rows)));
    const canvas=document.createElement('canvas');canvas.width=columns*tile+(columns+1)*gap;canvas.height=rows*tile+(rows+1)*gap;
    const ctx=canvas.getContext('2d');if(!ctx)throw Error('当前环境暂不能拼图，请重新选择单张照片。');
    ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);
    for(let i=0;i<files.length;i++){
      if(!alive())return null;
      const source=photoDataURL(await readPhoto(files[i]));if(!alive())return null;
      const img=await new Promise((resolve,reject)=>{const picture=new Image();picture.onload=()=>resolve(picture);picture.onerror=()=>reject(Error('第'+(i+1)+'张照片无法读取，请换一张。'));picture.src=source;});
      if(!alive()){img.src='';return null;}
      if(!img.naturalWidth||!img.naturalHeight)throw Error('照片尺寸无效，请重新选择。');
      const scale=Math.min(tile/img.naturalWidth,tile/img.naturalHeight),width=img.naturalWidth*scale,height=img.naturalHeight*scale;
      ctx.drawImage(img,gap+(i%columns)*(tile+gap)+(tile-width)/2,gap+Math.floor(i/columns)*(tile+gap)+(tile-height)/2,width,height);img.src='';
    }
    let result;for(const quality of [.9,.8,.7,.6]){result=canvas.toDataURL('image/jpeg',quality);if(Math.floor((result.length-result.indexOf(',')-1)*3/4)<=10*1024*1024)return result;}
    throw Error('拼图超过10MB，请减少照片后重试。');
  }
  function upload(kind='garment',options={}){
    const maxPhotos=kind==='garment'&&!options.single?10:1;
    show(kind==='garment'?'把喜欢收进衣橱':'创建我的试穿形象');if(kind==='garment'){dialog.dataset.panel='upload';scene.hidden=true;steps.hidden=true;}const token=epoch,view=viewSequence;
    atmosphere(kind);if(kind==='garment'){scene.hidden=true;steps.hidden=true;}
    body.append(el('p','journey-intro',kind==='garment'?(maxPhotos===10?'选择一种添加方式，建立你的私人衣橱。照片最多10张，预览确认再上传。':'请选择一张只含单件衣物的照片，预览确认后再上传。'):'选择本人的清晰正面照片，避免遮挡。照片检查后，会单独展示人物生成所需积分。'));
    const input=el('input');input.type='file';input.accept='image/jpeg,image/png,image/webp';input.setAttribute('aria-label',kind==='garment'?'选择衣物照片':'选择本人照片');
    input.id='journey-photo-input';input.className='journey-file-input';input.multiple=maxPhotos>1;if(kind==='garment')input.setAttribute('aria-description',maxPhotos===10?'最多10张照片，预览确认后上传。':'请选择一张单件衣物照片。');
    const pocket=el(kind==='garment'?'div':'label','journey-photo-pocket');if(kind!=='garment')pocket.htmlFor=input.id;
    const pocketIcon=el('span','journey-pocket-icon','＋'),pocketTitle=el('strong','',kind==='garment'?'从照片添加':'选一张自己的照片'),pocketHint=el('span','journey-pocket-hint','JPG / PNG / WebP · 10MB 以内');
    if(kind==='garment'){pocket.classList.add('journey-batch-photo-card');pocketHint.textContent=maxPhotos===10?'一次最多10张 · 预览后确认':'单张单件衣物 · 预览后确认上传';}
    pocket.append(input,pocketIcon,pocketTitle,pocketHint);
    const pickButtons=[];let activeSource='photo';
    if(kind==='garment'){
      const choices=el('div','journey-photo-sources');choices.setAttribute('role','group');choices.setAttribute('aria-label','选择衣物照片来源');
      for(const [label,camera] of [['照片',false],['拍摄',true]]){
        const pick=button(label,()=>{
          // iOS: use the existing native photo picker / camera permission flow.
          // Web capture is only a browser hint; desktop may open a file picker.
          activeSource=camera?'camera':'photo';fileSequence++;releasePhoto();data=null;requestID=null;submit.disabled=true;preview.replaceChildren();pocket.classList.remove('has-photo');
          input.multiple=!camera&&maxPhotos>1;
          if(camera)input.setAttribute('capture','environment');else input.removeAttribute('capture');
          input.value='';input.click();
        });
        pick.dataset.photoSource=camera?'camera':'photo';
        const icon=el('span');icon.setAttribute('aria-hidden','true');icon.innerHTML='<svg viewBox="0 0 24 24">'+(camera?'<path d="M8 6 9 3h6l1 3h4v14H4V6Z"/><circle cx="12" cy="12" r="4"/>':'<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="8" cy="9" r="1.5"/><path d="m4 17 5-5 4 4 3-3 4 4"/>')+'</svg>';
        const copy=el('span','journey-source-copy'),heading=el('span','journey-source-heading');heading.append(el('strong','',camera?'拍摄':'从照片添加'));if(!camera)heading.append(el('small','journey-source-recommend','推荐'));copy.append(heading,el('small','journey-source-detail',camera?'使用本次拍摄的照片':maxPhotos===10?'一次最多10张 · 预览后确认':'单张单件衣物 · 预览后确认上传'));pick.replaceChildren(icon,copy,el('span','journey-source-arrow','›'));pick.setAttribute('aria-label',camera?'拍摄':maxPhotos===10?'从照片添加，最多10张':'从照片添加，单张衣物');pickButtons.push(pick);choices.append(pick);
      }
      pocketIcon.remove();pocket.append(choices);
    }
    const preview=el('div','journey-upload-preview'),actions=el('div','journey-actions journey-submitbar');
    let data=null,requestID=null,fileSequence=0;
    const submit=button('确认上传',async()=>{
      if(!data||!current(token))return;
      input.disabled=true;submit.disabled=true;pickButtons.forEach(b=>b.disabled=true);if(kind==='garment')lockClose(true);
      try{if(kind==='garment'&&!window.ServerGarmentUpload)throw Error('上传组件未加载，请刷新页面。');const action=kind==='garment'?await window.ServerGarmentUpload.start(data,requestID):await api('/stylist-api/media/uploads',{method:'POST',body:JSON.stringify({request_id:requestID,kind,image_data:data,confirmed:true})});
        if(current(token)){renderUpload(action);if(dialog.open&&view===viewSequence){data=null;renderMedia(action);}}
      }catch(error){if(current(token))lockClose(false);throw error;}finally{if(current(token)){input.disabled=false;pickButtons.forEach(b=>b.disabled=false);}}
    },true);submit.disabled=true;
    input.onchange=async()=>{
      const files=Array.from(input.files||[]);if(!files.length||!current(token)||!dialog.open||view!==viewSequence)return;
      const selectedFile=++fileSequence;releasePhoto();data=null;submit.disabled=true;requestID=crypto.randomUUID();preview.replaceChildren();pocket.classList.remove('has-photo');
      const alive=()=>current(token)&&dialog.open&&view===viewSequence&&selectedFile===fileSequence;
      if(files.length>(activeSource==='camera'?1:maxPhotos)){notify?.(activeSource==='camera'?'拍摄只使用本次的一张照片。':maxPhotos===10?'一次最多选择10张照片，请重新选择。':'请只选择一张照片。');return;}
      if(files.some(file=>file.size<16||file.size>10*1024*1024)){notify?.('每张照片请选择10MB以内的有效JPG、PNG或WebP图片。');return;}
      pocketTitle.textContent=kind==='garment'?'照片选好了，也可以重新选择':'照片选好了，点这里可以换一张';pocketHint.textContent=files.length>1?`已选择${files.length}张 · 正在准备…`:files[0].name;
      const readPhoto=file=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('照片读取失败，请重新选择。'));reader.readAsDataURL(file);});
      const img=el('img');
      try{
        if(files.length===1){previewURL=URL.createObjectURL(files[0]);img.src=previewURL;img.alt='仅在本地预览的待上传照片';preview.append(img,el('span','journey-preview-label','这张照片，还只在你的设备上'));pocket.classList.add('has-photo');const read=await readPhoto(files[0]);if(alive()){data=photoDataURL(read);submit.disabled=false;}}
        else{preview.append(el('p','journey-compose-status','正在准备'+files.length+'张照片…'));const composed=await composePhotos(files,readPhoto,alive);if(!alive()||!composed)return;data=composed;img.src=composed;img.alt=files.length+'张照片拼成的本地待上传图片';preview.replaceChildren(img,el('span','journey-preview-label',`已选择${files.length}张照片，请预览确认`));pocketHint.textContent=`已选择${files.length}张 · 请预览确认`;pocket.classList.add('has-photo');submit.disabled=false;}
      }catch(e){if(alive()){data=null;submit.disabled=true;preview.replaceChildren();pocketHint.textContent=kind==='garment'?maxPhotos===10?'一次最多10张 · 预览后确认':'单张单件衣物 · 预览后确认上传':'JPG / PNG / WebP · 10MB 以内';notify?.(e.message);}}
    };
    actions.append(submit);body.append(pocket,preview);if(kind!=='garment')body.append(el('p','journey-note','确认后会上传并检查照片。人物生成的费用，会在下一步单独确认。'));dock(actions);
  }
  function renderUpload(action){
    if(action.kind!=='garment'||!owner)return;
    const feed=$('feed');let card=feed.querySelector('[data-media-action="'+action.action_id+'"]');
    if(!card){card=el('article','look journey-result');card.dataset.mediaAction=action.action_id;feed.append(card);}
    card.classList.add('journey-tryon-letter','journey-upload-letter');card.dataset.status=action.status;
    const complete=action.status==='completed',male=document.documentElement.dataset.stylistGender==='male';
    card.replaceChildren(letterSender(complete?'衣橱小笺 · 新衣归位':'衣橱小笺 · 整理记录'),
      el('h3','journey-letter-lead',complete?(male?'收好了，从这件开始。':'这件喜欢，替你收好啦。'):['processing','executing'].includes(action.status)?'这件衣服，还在整理中。':'这件衣服的入柜小记。'));
    const state=el('span','journey-upload-state',complete?'✓ 已收入你的衣橱':statusLabel(action.status));card.append(state);
    const actions=el('div','journey-letter-actions');
    if(action.status==='completed'){
      const frame=el('figure','journey-letter-photo'),picture=photo(action.result?.result_image_url,'已入柜的衣物抠图');
      frame.append(picture||el('p','journey-note','衣物已入柜，暂时没有可用预览。'),el('figcaption','','衣橱里，又多了一种喜欢的可能'));card.append(frame);
      card.append(el('p','journey-upload-note',male?'用它和衣橱里的衣服，试试新的组合。':'从这一件出发，一起看看它的新搭配吧。'));
      actions.append(button('用这件搭一套',()=>{if(dialog.open)dialog.close();onStyle?.(action.action_id);},true));
    }else actions.append(button('查看上传结果',async()=>{const token=epoch;const next=await readMedia(action);if(current(token))renderMedia(next);}));
    card.append(actions);
  }
  function mediaLabel(action){return {garment:'衣物入柜',person:'人物照片检查',generation:'数字人生成'}[action.kind]||'处理记录';}
  const statusLabel=status=>({quoted:'等待费用确认',executing:'正在提交',processing:'正在处理中',completed:'已完成',failed:'未完成',unknown:'结果待核对',cancelled:'已取消',expired:'报价已过期'}[status]||'状态待核对');
  const readMedia=action=>action.kind==='garment'?(action.result?.protocol==='server_direct'?window.ServerGarmentUpload.refresh(action.action_id):Promise.resolve(action)):api('/stylist-api/media/'+action.action_id);
  function pollMedia(action,token){
    if(action.kind==='garment'&&action.result?.protocol!=='server_direct')return;
    const view=viewSequence;
    if(!['processing','executing','unknown'].includes(action.status)||!dialog.open||!current(token))return;
    clearTimer();timer=setTimeout(async()=>{
      timer=null;
      if(!current(token)||!dialog.open||view!==viewSequence)return;
      try{
        const next=await readMedia(action);
        if(current(token)&&dialog.open&&view===viewSequence){
          if(JSON.stringify(next)!==JSON.stringify(action)||body.querySelector('.journey-poll-note'))renderMedia(next,false);
          pollMedia(next,token);
        }
      }catch(e){
        if(!current(token)||!dialog.open||view!==viewSequence)return;
        if(e.paymentHandled)return;
        let note=body.querySelector('.journey-poll-note');
        if(!note){note=el('p','journey-note journey-poll-note','暂时未能读取进展，正在重试…');note.setAttribute('role','status');body.append(note);}
        pollMedia(action,token);
      }
    },2000);
  }
  const batchChoices=new Map();
  function renderBatch(action){
    show('添加衣服');dialog.dataset.panel='upload';atmosphere('garment');scene.hidden=true;steps.hidden=true;
    const feed=$('feed'),recordEpoch=epoch;if(feed){let record=feed.querySelector('[data-media-action="'+action.action_id+'"]');if(!record){record=el('article','look journey-result');record.dataset.mediaAction=action.action_id;feed.append(record);}record.replaceChildren(el('strong','',action.status==='completed'?'本次衣物处理已完成':'本次衣物处理记录'),el('p','journey-note',action.result?.message||'打开查看识别、选择与处理结果。'),button('查看识别结果',async()=>{const next=await readMedia(action);if(current(recordEpoch))renderMedia(next);}));}
    const token=epoch,view=viewSequence,result=action.result||{},currentView=()=>current(token)&&dialog.open&&view===viewSequence;
    lockClose(['processing','executing'].includes(action.status)||(action.status==='unknown'&&Boolean(result.task_id)));if(result.selection_required&&!result.selection_submitted_ids)lockClose(false);
    const header=el('div','journey-batch-summary');header.append(el('h3','',result.selection_required?'核对识别结果':action.status==='completed'?'已收入衣橱':action.status==='failed'?'本次添加未完成':action.status==='cancelled'?'本次添加已取消':action.status==='unknown'?'提交结果待核对':'正在整理你的照片'));
    body.append(header);
    if(result.message)body.append(el('p','journey-note',result.message));
    if(result.stage==='segmenting'||result.stage==='creating_task')body.append(el('p','journey-note','正在识别图片里的衣服、鞋履与配饰，识别完成后由你选择保留。'));
    if(typeof result.progress==='number'&&Number.isFinite(result.progress)){const progress=el('progress');progress.max=100;progress.value=Math.max(0,Math.min(100,result.progress));progress.setAttribute('aria-label','识别进度');body.append(progress);}
    if(result.selection_required){
      let chosen=batchChoices.get(action.action_id);if(!chosen){chosen=new Set((result.selection_items||[]).map(i=>i.detail_id));batchChoices.set(action.action_id,chosen);}
      body.append(el('p','journey-note','核对图片后，勾选想要保留的单品，再确认加入衣橱。'));const grid=el('div','journey-batch-grid');
      for(const item of result.selection_items||[]){const label=el('label','journey-batch-item'),check=el('input');check.type='checkbox';check.checked=chosen.has(item.detail_id);check.disabled=Boolean(result.selection_submitted_ids);check.onchange=()=>{if(check.checked)chosen.add(item.detail_id);else chosen.delete(item.detail_id);submit.textContent=chosen.size?'确认加入衣橱 · '+chosen.size+'件':'不保留本次单品';};const image=el('img');image.src=imageURL(item.beautify_image||item.cutout_image);image.alt=item.class_type||'识别出的单品';label.append(image,check,el('strong','',item.name||item.class_type||'候选单品'));grid.append(label);}
      body.append(grid);const submit=button(chosen.size?'确认加入衣橱 · '+chosen.size+'件':'不保留本次单品',async()=>{if(!currentView())return;lockClose(true);try{const next=await window.ServerGarmentUpload.select(action.action_id,[...chosen].map(Number));if(currentView())renderMedia(next);}catch(error){if(currentView()&&error.action)renderMedia(error.action);throw error;}},true);submit.disabled=Boolean(result.selection_submitted_ids);dock(submit);
      if(result.selection_submitted_ids)body.append(el('p','journey-note','本次选择已提交，正在核对原任务，不会重复提交。'));
    }else{
      const grid=el('div','journey-batch-grid');for(const product of result.products||[]){const card=el('div','journey-batch-item'),image=el('img');image.src=imageURL(product.beautify_image||product.cutout_image);image.alt=product.name||'衣橱单品';const status=product.beautify_status===1?'已完成':product.beautify_status===2?'处理未完成':'正在生成';card.append(image,el('strong','',product.name||product.title||'衣橱单品'),el('small','',status));
        if(action.status==='completed'&&product.beautify_status===1)card.append(button('聊聊这件',async()=>{if(currentView()){dialog.close();if(onProduct)await onProduct(product.user_product_id);else notify?.('已收进衣橱，可以从单品详情继续搭配。');}}));grid.append(card);}body.append(grid);
      if(result.failed_count)body.append(el('p','journey-note',result.failed_count+'件未完成，请核对结果。'));
      const done=button(closeLocked?'正在处理中…':'完成',()=>{if(!closeLocked)dialog.close();});done.disabled=closeLocked;dock(done);
    }
    if(action.status==='unknown'&&!result.task_id)body.append(el('p','journey-note','尚未获得任务编号，请稍后核对处理记录，不要重新上传。'));
    if(action.status==='cancelled')body.append(el('p','journey-note','本次未保留单品。'));
  }
  function renderMedia(action,startPolling=true){
    if(action.kind==='garment'&&action.result?.protocol==='server_direct'){renderBatch(action);if(startPolling)pollMedia(action,epoch);return;}
    show(mediaLabel(action));const token=epoch,result=action.result||{};if(action.kind==='garment'){renderUpload(action);body.append(el('p','journey-note','旧版上传记录：仅显示已保存的结果，不再查询或更新。'));}
    atmosphere(action.kind==='garment'?'garment':'person',action.kind==='person'?0:action.status==='completed'?2:1);dialog.dataset.status=action.status;
    body.append(el('p','journey-state',statusLabel(action.status)));
    if(action.kind==='generation'&&['executing','processing'].includes(action.status))body.append(progress(action));
    if(result.message)body.append(el('p','',result.message));
    if(result.result_message)body.append(el('p','',result.result_message));
    appendPhoto(result.result_image_url||result.image_url,mediaLabel(action));
    if(action.status==='unknown'||action.status==='executing')body.append(el('p','journey-note','尚未确认最终结果。请查看原任务或App记录，不要重复提交。'));
    if(action.kind==='garment'&&action.status==='completed'){
      body.append(el('p','',result.class_name?'已识别为'+result.class_name+'，已保存到个人衣橱。':'已保存到个人衣橱，可以从这件开始搭配。'));
      dock(button('用这件搭配下',()=>{dialog.close();onStyle?.(action.action_id);},true));
      body.append(el('p','journey-note','若识别的类别不准确，可以先在App衣橱修改，再回来搭配。'));
    }
    if(action.kind==='person'&&action.status==='completed'&&result.allowed_hat_actions?.length)inlineGeneration(action,token);
    if(action.kind==='generation'&&action.status==='completed'&&result.can_confirm===true){
      body.append(button('确认使用这个试穿形象',async()=>{
        const overview=await api('/stylist-api/twins');if(!current(token))return;
        try{await api('/stylist-api/twins/use-candidate',{method:'POST',body:JSON.stringify({task_id:String(result.task_id),expected_version:overview.selection_version})});}
        catch(err){
          if(current(token)&&dialog.open&&['twin_changed','digital_twin_candidate_unavailable','digital_twin_version_conflict'].includes(err.code))renderMedia({...action,result:{...result,can_confirm:false}},false);
          throw err;
        }
        if(current(token)&&dialog.open){notify?.('已确认使用这个试穿形象。');await twins();}
      },true));
    }
    if(action.status==='failed')body.append(button(action.kind==='garment'?'重新选择衣物照片':'重新选择人物照片',()=>upload(action.kind==='garment'?'garment':'person')));
    if(startPolling)pollMedia(action,token);
  }
  function inlineGeneration(action,token){
    const view=viewSequence,hats=el('div','journey-actions'),hair=el('textarea');
    let selected=action.result.allowed_hat_actions[0],ticket=0,quoted=null,submitting=false;
    const live=()=>current(token)&&dialog.open&&view===viewSequence;
    const cancel=q=>{if(q&&current(token))api('/stylist-api/media/'+q.id+'/confirm',{method:'POST',body:JSON.stringify({confirmed:false})}).catch(()=>{});};
    const lock=value=>{hair.disabled=value;for(const b of hats.children)b.disabled=value;};
    const confirm=button('正在读取生成积分…',async()=>{
      if(!live()||submitting)return;
      if(!quoted){await readQuote();return;}
      if(Date.now()>=quoted.expires){invalidate();await readQuote();return;}
      const pending=quoted;submitting=true;lock(true);
      try{
        if(window.AppPayment&&!await window.AppPayment.checkFunds(pending.cost,'twin'))return;
        if(!live()||quoted!==pending||activeQuote!==pending)return;
        activeQuote=null;quoted=null;
        try{
          const result=await api('/stylist-api/media/'+pending.id+'/confirm',{method:'POST',body:JSON.stringify({confirmed:true})});
          if(live())renderMedia(result);
        }catch(e){
          if(!live())return;
          if(['image_quote_expired','image_quote_changed'].includes(e.code)){await readQuote();throw e;}
          if(e.paymentHandled||e.code==='digital_twin_points_insufficient'){quoted=pending;activeQuote=pending;throw e;}
          // A lost response is not evidence that generation never started.
          renderMedia({action_id:pending.id,kind:'generation',status:'unknown',result:{message:'生成结果暂未确认，正在查询原任务，请勿重复提交。'}});
          throw e;
        }
      }finally{if(live()){submitting=false;lock(false);}}
    },true);
    confirm.disabled=true;
    const invalidate=()=>{
      clearTimer();ticket++;const old=quoted;quoted=null;if(activeQuote===old)activeQuote=null;cancel(old);
      confirm.textContent='正在读取生成积分…';confirm.disabled=true;
    };
    async function readQuote(){
      if(!live())return;
      const request=++ticket;
      try{
        const q=await api('/stylist-api/media/'+action.action_id+'/generation-quote',{method:'POST',body:JSON.stringify({request_id:crypto.randomUUID(),hat_action:selected,hair_description:hair.value})});
        if(!live()||request!==ticket){cancel({id:q.action_id});return;}
        if(!q.action_id||!Number.isInteger(q.points_cost)||q.points_cost<0)throw Error('暂时无法读取生成积分，请重试。');
        quoted={id:q.action_id,kind:'generation',cost:q.points_cost,expires:Date.now()+290000};activeQuote=quoted;
        confirm.textContent=`确认消耗 ${points(q.points_cost)} 积分并生成`;confirm.disabled=false;
      }catch(e){
        if(!live()||request!==ticket)return;
        confirm.textContent='重新读取生成积分';confirm.disabled=false;notify?.(e.message||'暂时无法读取生成积分。');
      }
    }
    hair.maxLength=500;hair.placeholder='摘帽后希望保留的发型，例如：黑色短发（可选）';hair.setAttribute('aria-label','人物发型说明');
    hair.oninput=()=>{if(!live()||submitting)return;invalidate();timer=setTimeout(readQuote,350);};
    for(const value of action.result.allowed_hat_actions){
      const b=button({none:'保持原样',keep:'保留帽子',remove:'摘掉帽子'}[value]||value,()=>{
        if(!live()||submitting||selected===value)return;
        selected=value;for(const other of hats.children)other.setAttribute('aria-pressed',String(other===b));invalidate();return readQuote();
      });
      b.setAttribute('aria-pressed',String(value===selected));hats.append(b);
    }
    body.append(hats,hair,el('p','journey-note','按钮中显示本次人物生成所需积分，点击确认后才开始生成；搭配试穿另行确认积分。'));
    dock(confirm);readQuote();
  }
  async function cancelQuote(){
    const q=activeQuote;activeQuote=null;if(q)await api((q.kind==='generation'?'/stylist-api/media/':'/stylist-api/images/')+q.id+'/confirm',{method:'POST',body:JSON.stringify({confirmed:false})});
    dialog.close();
  }
  function portraitTile(p,selected,onSelect){
    const name=p.name||'试穿形象',tile=button('',onSelect);
    tile.className='journey-portrait';tile.dataset.twinKey=p.twin_key;tile.setAttribute('aria-label',name);tile.setAttribute('aria-pressed',String(selected===p.twin_key));
    const frame=el('span','journey-portrait-photo'),image=el('img'),src=imageURL(p.thumbnail_url||p.image_url);
    image.alt='';image.referrerPolicy='no-referrer';
    const missing=()=>{const placeholder=el('span','journey-portrait-missing','暂无图片');placeholder.setAttribute('aria-label','照片暂未载入');frame.replaceChildren(placeholder);};
    image.onerror=missing;if(src){image.src=src;frame.append(image);}else missing();
    const mark=el('span','journey-portrait-check','✓');mark.setAttribute('aria-hidden','true');
    const caption=el('span','journey-portrait-caption');caption.append(el('span','journey-portrait-name',name),el('span','journey-portrait-source',p.twin_key==='custom'?'我的专属形象':'预设试穿形象'));
    tile.append(frame,mark,caption);return tile;
  }
  async function bodyProfile(overview,token,view){
    const section=el('section','journey-body-profile');
    section.append(el('h3','','身体与外观'));body.append(section);
    let options;
    try{options=await api('/stylist-api/twins/options');if(!options?.height_cm||!options?.weight_kg||!Array.isArray(options.skin_tone))throw Error('身体资料选项暂不可用');}catch(error){
      if(current(token)&&dialog.open&&view===viewSequence){section.append(el('p','journey-note','身体资料暂未读取，请稍后重试。'),button('重新读取',()=>{section.remove();return bodyProfile(overview,token,view);}));}return;
    }
    if(!current(token)||!dialog.open||view!==viewSequence)return;
    const profile=overview.profile||{},form=el('form','journey-body-form'),fields={},dirty=new Set();
    const bmi=el('output','journey-body-bmi');bmi.setAttribute('aria-live','polite');
    const updateBMI=()=>{const h=Number(fields.height_cm?.value),w=Number(fields.weight_kg?.value);bmi.textContent=h>0&&w>0?'BMI（参考）  '+(w/((h/100)**2)).toFixed(1):'BMI（参考）  —';};
    for(const [key,label,unit] of [['height_cm','身高','cm'],['weight_kg','体重','kg']]){
      const range=options[key]||{},row=el('div','journey-measurement'),heading=el('label','journey-measurement-heading'),caption=el('span','',label);
      const input=el('input');input.type='number';input.inputMode='decimal';input.id='twin-'+key;input.setAttribute('aria-label',label);input.placeholder='未填写';input.value=profile[key]??'';
      const valid=Number.isFinite(range.min)&&Number.isFinite(range.max)&&range.max>range.min;
      if(valid){input.min=range.min;input.max=range.max;input.step=range.step>0?range.step:0.1;}else input.disabled=true;
      const value=el('span','journey-measurement-value');value.append(input,el('span','',unit));heading.htmlFor=input.id;heading.append(caption,value);
      if(profile[key+'_is_default'])caption.append(el('small','journey-note',' 默认值'));
      row.append(heading);fields[key]=input;
      if(valid){const slider=el('input','journey-body-slider');slider.type='range';slider.min=input.min;slider.max=input.max;slider.step=input.step;slider.value=input.value||range.min;slider.setAttribute('aria-label','调整'+label);
        slider.oninput=()=>{input.value=slider.value;dirty.add(key);updateBMI();};input.oninput=()=>{if(input.value)slider.value=input.value;dirty.add(key);updateBMI();};row.append(slider);
      }
      form.append(row);
    }
    form.append(bmi);updateBMI();
    const details=el('details','journey-body-description');details.append(el('summary','','身材描述'));
    const description=el('textarea');description.value=profile.body_description||'';description.maxLength=Math.min(options.body_description_max_length||1000,1000);description.placeholder='例如：肩背较宽，喜欢腰腹宽松一些';description.setAttribute('aria-label','身材描述');fields.body_description=description;description.oninput=()=>dirty.add('body_description');
    const suggestions=el('div','journey-body-suggestions');for(const text of ['偏瘦','中等','偏胖'])suggestions.append(button(text,()=>{description.value=text;dirty.add('body_description');}));
    details.append(suggestions,description);form.append(details);
    const skinValue=el('input');skinValue.type='hidden';skinValue.value=profile.skin_tone||'';fields.skin_tone=skinValue;
    const skinNote=el('input');skinNote.type='hidden';skinNote.value=profile.skin_description||'';fields.skin_description=skinNote;
    const skinChoices=(options.skin_tone||[]).map(o=>({value:o.value||o.code||o.id,label:o.label||o.name}));
    const skinLabel=()=>skinChoices.find(o=>o.value===skinValue.value)?.label||(skinValue.value?'已保存的肤色':'未填写');
    const skinEntry=button('',()=>{
      const sheet=el('dialog','journey-skin-sheet');sheet.setAttribute('aria-label','肤色参考');
      const heading=el('div','journey-skin-heading');heading.append(el('h3','','肤色参考'));
      const closeSheet=()=>sheet.close();const cancel=button('取消',closeSheet);heading.append(cancel);
      const content=el('div','journey-skin-content');content.append(el('p','journey-note','选择接近你的肤色，也可以补充描述。'));
      let chosen=skinValue.value;const choices=el('div','journey-skin-options');choices.setAttribute('role','group');choices.setAttribute('aria-label','选择肤色');
      const rows=[{value:'',label:'暂不填写'},...skinChoices];if(chosen&&!rows.some(o=>o.value===chosen))rows.push({value:chosen,label:'已保存的肤色'});
      for(const option of rows){const tile=button(option.label,()=>{chosen=option.value;for(const item of choices.children)item.setAttribute('aria-pressed',String(item===tile));});tile.setAttribute('aria-pressed',String(option.value===chosen));choices.append(tile);}
      const label=el('label','journey-skin-note-label','补充描述（选填）'),note=el('textarea');note.id='twin-skin-note';label.htmlFor=note.id;note.setAttribute('aria-label','肤色补充描述');note.value=skinNote.value;note.maxLength=Math.min(options.skin_description_max_length||500,500);note.placeholder='例如：肤色偏暖，容易晒黑';
      content.append(choices,label,note);
      const actions=el('div','journey-skin-actions');actions.append(el('p','journey-note','完成后，点击“保存身体资料”生效。'),button('完成',()=>{if(chosen!==skinValue.value){skinValue.value=chosen;dirty.add('skin_tone');}if(note.value!==skinNote.value){skinNote.value=note.value;dirty.add('skin_description');}skinSummary.textContent=skinLabel();closeSheet();},true));
      sheet.append(heading,content,actions);section.append(sheet);
      const resize=()=>{const viewport=window.visualViewport;sheet.style.setProperty('--skin-visible-height',(viewport?.height||window.innerHeight)+'px');sheet.style.setProperty('--skin-visible-top',(viewport?.offsetTop||0)+'px');if(document.activeElement===note)requestAnimationFrame(()=>note.scrollIntoView({block:'nearest'}));};
      const observer=new MutationObserver(()=>{if(!dialog.open||!section.isConnected||!current(token)||view!==viewSequence)closeSheet();});observer.observe(dialog,{attributes:true,attributeFilter:['open'],childList:true,subtree:true});
      const onParentClose=()=>closeSheet();dialog.addEventListener('close',onParentClose);window.visualViewport?.addEventListener('resize',resize);window.visualViewport?.addEventListener('scroll',resize);
      sheet.addEventListener('close',()=>{observer.disconnect();dialog.removeEventListener('close',onParentClose);window.visualViewport?.removeEventListener('resize',resize);window.visualViewport?.removeEventListener('scroll',resize);sheet.remove();if(skinEntry.isConnected&&dialog.open)skinEntry.focus();},{once:true});
      resize();sheet.showModal();cancel.focus();
    });skinEntry.className='journey-skin-entry';const skinSummary=el('span','',skinLabel());skinEntry.append(el('span','','肤色参考'),skinSummary,el('span','','›'));form.append(skinValue,skinNote,skinEntry);
    const status=el('p','journey-note');status.setAttribute('role','status');
    const save=button('保存身体资料',async()=>{
      if(!dirty.size){status.textContent='资料没有变化。';return;}
      if(!form.reportValidity())return;
      const payload={expected_version:overview.profile_version};
      for(const key of dirty)payload[key]=['height_cm','weight_kg'].includes(key)?(fields[key].value===''?null:Number(fields[key].value)):key==='skin_tone'?(fields[key].value||null):fields[key].value;
      const disabledBefore=Array.from(form.elements).map(e=>[e,e.disabled]);disabledBefore.forEach(([e])=>e.disabled=true);
      try{const result=await api('/stylist-api/twins/profile',{method:'POST',body:JSON.stringify(payload)});
        if(!current(token)||!dialog.open||view!==viewSequence)return;
        if(!Number.isInteger(result.profile_version))throw Error('资料保存状态暂未确认，请刷新后核对。');
        overview.profile_version=result.profile_version;dirty.clear();status.textContent='身体资料已保存。';
      }finally{if(current(token)&&dialog.open&&view===viewSequence)disabledBefore.forEach(([e,disabled])=>e.disabled=disabled);}
    });save.classList.add('journey-body-save');form.onsubmit=e=>e.preventDefault();form.append(save,status);section.append(form);
  }
  async function twins(){
    show('我的试穿形象');const token=epoch,view=viewSequence;
    atmosphere('person',0);steps.hidden=true;dialog.dataset.panel='portraits';
    const overview=await readLoading(body,'正在读取可用形象…',()=>api('/stylist-api/twins'));if(!current(token)||!dialog.open||view!==viewSequence)return;
    body.replaceChildren(el('h3','journey-twin-section-title','数字分身'));
    if(overview.need_gender){
      body.append(el('p','','先选择试穿人物的性别，系统会提供对应的基础形象。'));
      for(const gender of ['女','男'])body.append(button('使用'+gender+'性人物',async()=>{
        await api('/stylist-api/twins/gender',{method:'POST',body:JSON.stringify({gender,expected_version:overview.profile_version})});if(current(token)&&dialog.open)await twins();
      }));return;
    }
    const portraits=[...(overview.custom_twin?[{...overview.custom_twin,twin_key:'custom',name:'我的试穿形象'}]:[]),...(overview.system_twins||[])];
    const grid=el('div','journey-portraits journey-twin-strip');grid.setAttribute('aria-label','试穿形象选择');let selected=overview.default_twin_key;
    const selection=el('span','journey-selection');selection.setAttribute('aria-live','polite');
    const updateSelection=()=>{const chosen=portraits.find(p=>p.twin_key===selected);selection.textContent=chosen?'已选 · '+(chosen.name||'试穿形象'):'选一个喜欢的形象';};updateSelection();
    for(const p of portraits){
      const tile=portraitTile(p,selected,()=>{selected=p.twin_key;for(const child of grid.children)child.setAttribute('aria-pressed',String(child===tile));updateSelection();});grid.append(tile);
    }
    body.append(grid);
    const selectionInfo=el('div','journey-selection-info');selectionInfo.append(selection);
    if(window.AppPayment){const balanceLabel=el('span','journey-selection-balance','正在查询可用积分…');selectionInfo.append(balanceLabel);api('/stylist-api/app/points').then(result=>{if(balanceLabel.isConnected&&current(token))balanceLabel.textContent=typeof result?.data?.total_available==='number'?`可用 ${points(result.data.total_available)} 积分`:'可用积分暂未查到';}).catch(()=>{if(balanceLabel.isConnected&&current(token))balanceLabel.textContent='可用积分暂未查到';});}
    if(portraits.length)dock(selectionInfo,button(pendingLook?'确认形象，继续查看试穿费用':'确认使用所选形象',async()=>{
      if(!selected){notify?.('请先选一个试穿形象。');return;}
      await api('/stylist-api/twins/default',{method:'POST',body:JSON.stringify({twin_key:selected,expected_version:overview.selection_version})});
      if(!current(token))return;
      if(pendingLook){const ref=pendingLook;pendingLook=null;await tryonQuote(ref);}else{notify?.('已保存试穿形象。');await twins();}
    },true));
    const pending=overview.pending_task;
    if(pending){
      const candidate=el('section','journey-pending-portrait'),preview=el('div','journey-pending-photo'),copy=el('div','journey-pending-copy'),actions=el('div','journey-pending-actions');
      appendPhoto(pending.result_image_url,'待确认的数字人',preview);
      copy.append(el('span','journey-card-label','形象小记'),el('h3','',pending.can_confirm?'新的模样，等你确认':'正在准备的个人形象'));
      if(pending.can_confirm)actions.append(button('确认使用生成的形象',async()=>{
        await api('/stylist-api/twins/use-candidate',{method:'POST',body:JSON.stringify({task_id:String(pending.task_id),expected_version:overview.selection_version})});if(current(token)&&dialog.open)await twins();
      },true));else copy.append(el('p','',pending.status==='failed'?'上次人物生成没有完成，请查看生成记录。':'个人形象正在准备中，稍后可刷新查看。'));
      actions.append(button('刷新人物状态',twins));copy.append(actions);
      if(preview.children.length)candidate.append(preview);else candidate.classList.add('without-photo');
      candidate.append(copy);body.append(candidate);
    }
    if(!portraits.length&&!pending)body.append(el('p','journey-note','这一页还没有形象，先用一张自己的照片开始吧。'));
    const uploadEntry=button('',()=>upload('person'));uploadEntry.className='journey-portrait-upload';
    const plus=el('span','journey-portrait-plus','＋');plus.setAttribute('aria-hidden','true');
    const uploadCopy=el('span','journey-portrait-upload-copy');uploadCopy.append(el('strong','','上传本人照片，创建我的试穿形象'),el('span','','从一张照片，遇见新的自己'));
    const arrow=el('span','journey-portrait-arrow','↗');arrow.setAttribute('aria-hidden','true');uploadEntry.append(plus,uploadCopy,arrow);
    body.append(uploadEntry);
    if(!pendingLook)await bodyProfile(overview,token,view);
  }
  async function tryon(ref){
    requireContext(ref);
    pendingLook=ref;const token=epoch;
    show('准备试穿');steps.hidden=true;
    const overview=await readLoading(body,'正在确认试穿形象…',()=>api('/stylist-api/twins'));if(!current(token)||!dialog.open)return;
    if(!overview.default_confirmed||!overview.default_twin_key){await twins();return;}
    pendingLook=null;await tryonQuote(ref);
  }
  async function tryonQuote(ref){
    requireContext(ref);
    show('试穿这套搭配');const token=epoch,view=viewSequence;
    atmosphere('quote',1);
    dialog.dataset.quoteKind='tryon';steps.hidden=true;
    scene.querySelector('.journey-scene-copy p').textContent='先看看这次的形象与积分。等你点头，我们再开始。';
    const q=await readLoading(body,'正在读取当前费用…',()=>api('/stylist-api/images/quote',{method:'POST',body:JSON.stringify(ref)}));if(!current(token)||!dialog.open||view!==viewSequence)return;
    activeQuote={id:q.action_id,kind:'tryon'};
    const summary=el('section','journey-quote-summary');summary.setAttribute('aria-label','本次试穿搭配与形象');
    const figure=el('figure','journey-quote-figure'),portrait=photo(q.portrait?.thumbnail_url||q.portrait?.image_url,'本次试穿人物');
    if(portrait)figure.append(portrait);else figure.append(el('span','journey-quote-missing','暂无形象预览'));
    figure.append(el('figcaption','',q.portrait?.name||'已选试穿形象'));
    const copy=el('div','journey-quote-copy'),seal=el('span','journey-quote-seal','✦');seal.setAttribute('aria-hidden','true');
    copy.append(el('span','journey-card-label','为这一次的新模样'),el('h3','',q.title||'本次衣橱搭配'),
      el('p','journey-quote-count',Number.isInteger(q.item_count)?`${q.item_count} 件真实衣橱单品`:'当前已选的真实衣橱单品'));
    const fee=el('div','journey-quote-fee'),amount=el('span','journey-quote-amount');
    amount.append(el('strong','',points(q.points_cost)),el('span','','积分'));
    fee.append(el('span','journey-quote-fee-label','本次搭配试穿'),amount);copy.append(fee);
    summary.append(figure,copy,seal);body.replaceChildren(summary);
    if(q.notices?.length){
      const notes=el('section','journey-quote-notes'),list=el('ul');notes.append(el('h3','','在开始之前'));
      for(const note of q.notices)list.append(el('li','',note));notes.append(list);body.append(notes);
    }
    dock(button(`确认消耗 ${points(q.points_cost)} 积分并试穿`,async()=>{
      const pendingQuote=activeQuote;
      if(window.AppPayment&&!await window.AppPayment.checkFunds(q.points_cost,'tryon'))return;
      if(!current(token)||!dialog.open||activeQuote!==pendingQuote)return;
      const quote=activeQuote;activeQuote=null;
      requireContext(ref);
      const waiting={...ref,action_id:quote.id,title:q.title,status:'executing',result:{}};
      showTryonResult(waiting);renderTryon(waiting);monitorTryon(waiting);
      try{const action=await api('/stylist-api/images/'+quote.id+'/confirm',{method:'POST',body:JSON.stringify({confirmed:true})});if(current(token))acceptTryon({...waiting,...action});}
      catch(e){if(current(token)){acceptTryon({...waiting,status:'unknown',result:{message:e.message}});}throw e;}
    },true),button('暂不生成',()=>cancelQuote()));
  }
  function renderTryon(action){
    action=verifiedTryon(action);
    if(!owner||(action.conversation_id&&getConversation&&getConversation()!==action.conversation_id))return;
    const feed=$('feed');let card=feed.querySelector('[data-image-action="'+action.action_id+'"]');
    if(!card){card=el('article','look journey-result');card.dataset.imageAction=action.action_id;feed.append(card);}
    fillTryonLetter(card,action,{regenerate:true,records:true});
    return card;
  }
  function tryonCopy(action){
    const result=action.result||{};
    switch(action.status){
      case 'completed':return {lead:'这一身，想先给你看看。',note:'轻触试穿照，看看搭配的细节。'};
      case 'failed':return {lead:'这次试穿，没能生成图片。',note:result.refunded===true?'这次的积分已退回，原来的穿搭还在。':result.charged===false?'这次没有扣积分，原来的穿搭还在。':'试穿图没有生成，积分是否退回还需要核对。',query:result.refunded!==true&&result.charged!==false?'核对积分进展':null};
      case 'executing':return {lead:'把这一身，送去试穿。',note:'正在提交这次试穿，可以稍后再来看看进展。',query:'看看试穿进展'};
      case 'processing':return {lead:'新的模样，还在慢慢成形。',note:'可以先聊别的，回来时再看看这次的进展。',query:'看看试穿进展'};
      case 'cancelled':return {lead:'这次，就先停在这里。',note:'这次试穿已取消，原来的搭配仍然保留。'};
      case 'expired':return {lead:'这次的试穿确认，已经过期了。',note:'想试穿时，请从当前搭配重新确认积分。'};
      case 'quoted':return {lead:'准备好了，再试试这一身。',note:'还在等你确认这次试穿的积分。'};
      default:return {lead:'这次的试穿，还需要确认。',note:'暂时没收到确切结果。这里只查询原来的进展，不会再次扣积分。',query:'看看试穿进展'};
    }
  }
  function letterSender(label='试爱搭衣橱 · 来信'){
    const sender=el('div','journey-letter-sender'),portrait=el('span','journey-companion-frame journey-letter-avatar'),art=el('span','journey-companion journey-dialogue-avatar companion-dialogue-avatar');art.setAttribute('aria-hidden','true');
    portrait.append(art);
    const copy=el('div','journey-letter-signature');copy.append(el('span','',label),el('strong','',(window.CompanionSettings?.agentName?.()||'衣衣')+' 写给你'));
    const star=el('span','journey-letter-star','✧');star.setAttribute('aria-hidden','true');sender.append(portrait,copy,star);return sender;
  }
  async function checkTryon(action,card,options){
    const token=epoch;
    const next=verifiedTryon({...action,...await api('/stylist-api/images/'+action.action_id)});
    if(!current(token)||options.regenerate&&!sameConversation(action)||finished.has(next.action_id)&&next.status!=='completed')return;
    acceptTryon(next);
    if(card.isConnected)fillTryonLetter(card,next,options);
    if(next.status!=='completed'){
      const copy=tryonCopy(next);
      notify?.(next.status==='failed'?copy.note:next.status==='unknown'?'暂时还没有确切结果，这次只查询了原来的进展，没有再次扣积分。':copy.lead+' '+copy.note);
    }
  }
  function fillTryonLetter(card,action,options={}){
    action=verifiedTryon(action);const copy=tryonCopy(action),token=epoch;
    const focused=card.contains(document.activeElement),focusedLabel=document.activeElement?.textContent;
    card.classList.add('journey-tryon-letter');card.dataset.status=action.status;
    const lead=el('h3','journey-letter-lead',copy.lead),name=el('p','journey-letter-outfit',action.title||'这一次的搭配');
    card.replaceChildren(letterSender(),lead,name);
    if(action.status==='completed'){
      const figure=el('figure','journey-letter-photo');appendPhoto(tryonImage(action),'本次搭配的数字人试穿结果',figure);
      figure.append(el('figcaption','',copy.note));card.append(figure);
    }else{
      card.append(el('p','journey-letter-note',copy.note));
      if(['executing','processing'].includes(action.status))card.append(progress(action));
    }
    const actions=el('div','journey-letter-actions');
    if(copy.query)actions.append(button(copy.query,()=>{if(current(token)&&card.isConnected)return checkTryon(action,card,options);}));
    if(options.regenerate&&['completed','failed'].includes(action.status))actions.append(button('重新生成穿搭',()=>{
      if(!current(token)||!card.isConnected)return;
      if(dialog.contains(card))dialog.close();
      return onRegenerate?.(action);
    },true));
    // 暂停生成记录入口。
    // if(options.records&&action.status==='failed')actions.append(button('查看生成记录',history));
    if(actions.childElementCount)card.append(actions);
    if(focused){
      const target=[...actions.querySelectorAll('button')].find(b=>b.textContent===focusedLabel)||lead;
      if(target===lead)lead.tabIndex=-1;
      target.focus({preventScroll:true});
    }
  }
  function progress(action){
    const wrap=el('div','journey-progress'),track=el('div','journey-progress-track'),fill=el('span');
    const value=action.result?.progress;track.setAttribute('role','progressbar');track.setAttribute('aria-label','试穿合成进度');track.setAttribute('aria-valuemin','0');track.setAttribute('aria-valuemax','100');
    if(typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=100){track.setAttribute('aria-valuenow',String(value));fill.style.width=value+'%';}
    else track.classList.add('is-indeterminate');
    track.append(fill);wrap.append(el('p','',action.kind==='generation'?'正在准备新的个人形象':action.status==='executing'?'正在提交这次试穿':'正在合成新的上身模样'),track,
      el('small','',typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=100?`当前进度 ${value}%`:'还在准备中，可以稍后回到对话查看。'));return wrap;
  }
  function showTryonResult(action,refresh=false){
    action=verifiedTryon(action);
    if(!refresh){show('试穿来信');activeTryon=action.action_id;}
    dialog.dataset.panel='tryon-result';dialog.dataset.status=action.status;
    const letter=refresh&&body.querySelector('.journey-tryon-letter')||el('section');
    fillTryonLetter(letter,action,{regenerate:sameConversation(action)});if(!letter.isConnected)body.replaceChildren(letter);
    // 暂停生成记录入口：button('查看生成记录',history)
    dock(button('回到对话',()=>dialog.close()));
  }
  function stopWatcher(id){const w=watchers.get(id);if(w)clearTimeout(w.timer);watchers.delete(id);}
  function monitorTryon(action){
    if(watchers.has(action.action_id)||finished.has(action.action_id))return;
    const token=epoch,watch={timer:null,count:0};watchers.set(action.action_id,watch);
    const tick=async()=>{
      if(!current(token)||!sameConversation(action)||watchers.get(action.action_id)!==watch){stopWatcher(action.action_id);return;}
      try{const next=await api('/stylist-api/images/'+action.action_id);if(!current(token)||watchers.get(action.action_id)!==watch)return;
        acceptTryon({...action,...next});
      }catch(e){if(current(token))notify?.('暂时没能读取合成进度，可以稍后查看原任务。');stopWatcher(action.action_id);return;}
      if(watchers.get(action.action_id)===watch&&++watch.count<60)watch.timer=setTimeout(tick,3000);
      else stopWatcher(action.action_id);
    };watch.timer=setTimeout(tick,3000);
  }
  function acceptTryon(action){
    action=verifiedTryon(action);
    if(!owner||!sameConversation(action)||finished.has(action.action_id)&&action.status!=='completed')return;
    renderTryon(action);
    if(dialog.open&&activeTryon===action.action_id)showTryonResult(action,true);
    if(action.status==='completed'){
      stopWatcher(action.action_id);
      if(!finished.has(action.action_id)){finished.add(action.action_id);notify?.('这一身的试穿照到了，已经放在对话里。点开照片，就能看看细节。');}
    }else if(['failed','unknown','cancelled','expired'].includes(action.status))stopWatcher(action.action_id);
    else monitorTryon(action);
  }
  async function uploadAvatar(ref=null){
    requireContext(ref);pendingLook=ref;
    show('准备你的试穿形象');atmosphere('person',0);const token=epoch,view=viewSequence;
    body.append(el('p','journey-intro','先确认一下形象设置，再一起选择照片。'));
    const overview=await api('/stylist-api/twins');if(!current(token)||!dialog.open||view!==viewSequence)return;
    if(overview.need_gender){notify?.('先选择试穿人物的性别，选好后就可以上传形象照片。');await twins();}
    else upload('person');
  }
  function avatarCard(reply,node){
    const token=epoch,ref=reply.tryon_context||null,kind=reply.avatar_intent;
    const card=el('section','journey-invite journey-avatar-card');card.setAttribute('aria-label',kind==='upload'?'上传虚拟形象引导':'选择虚拟形象');
    card.append(el('span','journey-card-label','试爱搭衣橱 · 形象手记'),el('strong','',kind==='upload'?'把自己的模样，带进试穿里':'选一个模样，遇见新的搭配'));
    if(kind==='upload'){
      card.append(el('p','','先选形象照片，再预览、检查。创建个人形象与搭配试穿分别确认积分；上传照片不代表已完成本人认证。'));
      const list=el('ol','journey-card-steps');for(const text of ['选图与检查','确认创建积分','确认使用形象'])list.append(el('li','',text));
      card.append(list,button('选择形象照片',()=>uploadAvatar(ref),true),button('先看看已有形象',()=>{pendingLook=ref;return twins();}));node.append(card);return;
    }
    card.append(el('p','',ref?`这次接着「${reply.tryon_title||'当前搭配'}」试穿。先选形象，再单独确认本次积分。`:'先选一个喜欢的形象。还没有可试穿的衣橱搭配时，不会开始合成或扣费。'));
    const content=el('div','journey-avatar-content');card.append(content);node.append(card);
    const load=async()=>{
      if(!current(token)||!card.isConnected)return;content.replaceChildren(loading('正在展开你的形象小画廊…'));
      try{
        const overview=await api('/stylist-api/twins');if(!current(token)||!card.isConnected)return;content.replaceChildren();
        if(overview.need_gender){content.append(el('p','journey-note','先选好试穿人物的性别，再展开对应形象。'),button('设置我的试穿人物',()=>{pendingLook=ref;return twins();}));return;}
        const portraits=[...(overview.custom_twin?[{...overview.custom_twin,twin_key:'custom',name:overview.custom_twin.name||'我的数字分身'}]:[]),...(overview.system_twins||[])];
        const grid=el('div','journey-portraits journey-inline-portraits');grid.setAttribute('aria-label','试穿形象选择');
        let selected=overview.default_twin_key;
        const action=button(ref?'确认形象，查看这次试穿积分':'确认使用所选形象',async()=>{
          if(!current(token))return;requireContext(ref);
          if(!selected){notify?.('先选一个试穿形象，再继续。');return;}
          await api('/stylist-api/twins/default',{method:'POST',body:JSON.stringify({twin_key:selected,expected_version:overview.selection_version})});
          if(!current(token))return;requireContext(ref);
          if(ref){pendingLook=null;await tryonQuote(ref);}else{notify?.('这个模样已经选好了。');await load();}
        },true);
        for(const p of portraits){
          const tile=portraitTile(p,selected,()=>{if(!current(token))return;selected=p.twin_key;action.disabled=false;for(const other of grid.children)other.setAttribute('aria-pressed',String(other===tile));});grid.append(tile);
        }
        if(portraits.length){action.disabled=!portraits.some(p=>p.twin_key===selected);content.append(grid,action);}
        else content.append(el('p','journey-note','还没有可用形象，可以先上传照片创建个人形象。'));
        content.append(button('上传照片，创建新的形象',()=>uploadAvatar(ref)));
        if(!ref)content.append(button('先准备一套衣橱搭配',()=>onNeedOutfit?.()));
        content.append(el('small','journey-card-note',ref?'选择卡片不会直接合成；下一步会展示真实积分费用。':'查看与选择不会生成图片；需要试穿时会另行确认积分。'));
      }catch(e){if(current(token)&&card.isConnected){content.replaceChildren(el('p','journey-note','形象画廊暂时没展开，保留这张卡片，稍后再试。'),button('重新查看形象',load));notify?.(e.message||'暂时无法读取形象。');}}
    };load();
  }
  function recordCreatedAt(action){
    let value=String(action.created_at||'').trim().replace(' ','T');
    // SQLite timestamps are UTC without a suffix; PostgreSQL may emit +00.
    if(!/T.*(?:Z|[+-]\d{2}(?::?\d{2})?)$/i.test(value))value+='Z';
    value=value.replace(/([+-]\d{2})$/, '$1:00');
    const timestamp=Date.parse(value);return Number.isFinite(timestamp)?timestamp:-Infinity;
  }
  async function history(){
    show('我的上传与生成记录');const token=epoch,view=viewSequence;
    atmosphere('history');
    let [uploads,images]=await readLoading(body,'正在读取你的记录…',()=>Promise.all([api('/stylist-api/media'),api('/stylist-api/images')]));if(!current(token)||!dialog.open||view!==viewSequence)return;
    uploads=[...(window.ServerGarmentUpload?.list?.()||[]),...uploads];
    body.replaceChildren();
    const filters=el('div','journey-history-filters'),empty=el('p','journey-history-empty');
    filters.setAttribute('role','group');filters.setAttribute('aria-label','记录分类');empty.setAttribute('role','status');
    const records=[];
    for(const action of uploads){
      if(action.kind==='person')continue;
      const copy=mediaRecordCopy(action),card=el('section','journey-record journey-media-letter'),head=el('div','journey-record-heading'),mark=el('span','journey-record-mark','✧'),text=el('div','journey-record-copy');
      mark.setAttribute('aria-hidden','true');text.append(el('span','journey-record-kicker',copy.kicker),el('h3','',copy.lead));head.append(mark,text);
      const open=button(copy.cta,async()=>{
        if(!current(token)||!card.isConnected)return;
        const next=await readMedia(action);
        if(current(token)&&dialog.open&&view===viewSequence&&card.isConnected)renderMedia(next);
      });open.classList.add('journey-record-open');open.setAttribute('aria-label',copy.cta);
      const arrow=el('span','','↗');arrow.setAttribute('aria-hidden','true');open.append(arrow);
      card.dataset.mediaAction=action.action_id;card.append(head,el('p','journey-record-note',copy.note),open);records.push({card,action,kind:action.kind});
    }
    for(const action of images){
      const card=el('section','journey-record');fillTryonLetter(card,action);
      card.dataset.imageAction=action.action_id;records.push({card,action,kind:'tryon'});
    }
    records.sort((a,b)=>recordCreatedAt(b.action)-recordCreatedAt(a.action));
    const select=(kind,label)=>{
      if(!current(token)||!dialog.open||view!==viewSequence)return;
      for(const tab of filters.children)tab.setAttribute('aria-pressed',String(tab.dataset.kind===kind));
      let count=0;for(const record of records){record.card.hidden=kind!=='all'&&record.kind!==kind;if(!record.card.hidden)count++;}
      empty.hidden=count>0;empty.textContent=kind==='all'?'还没有记录，可以先上传一件常穿的衣服。':`这一页还没有「${label}」记录。`;
    };
    for(const [kind,label] of [['all','全部'],['garment','衣物入柜'],['generation','数字人生成'],['tryon','试穿']]){
      const tab=button(label,()=>select(kind,label));tab.dataset.kind=kind;filters.append(tab);
    }
    body.append(filters,empty,...records.map(record=>record.card));select('all','全部');
    body.append(button('上传一件衣服',()=>upload('garment')),button('我的试穿形象',twins));
  }
  function mediaRecordCopy(action){
    const result=action.result||{},kind=action.kind;
    const copy={kicker:{garment:'衣橱来信',person:'照片回信',generation:'形象来信'}[kind]||'日常来信',lead:'这次的尝试，有一封回信。',note:'这次的记录，替你留在这里。',cta:'打开这封来信'};
    if(action.status==='completed'){
      if(kind==='garment')Object.assign(copy,{lead:'这件衣服，替你收好了。',note:'打开来信，看看这次整理的衣物。',cta:'打开衣橱来信'});
      else if(kind==='person')Object.assign(copy,{lead:'这张照片，有些话想告诉你。',note:'关于这张照片的说明，都收在回信里。',cta:'读读照片回信'});
      else if(kind==='generation')Object.assign(copy,{lead:imageURL(result.result_image_url||result.image_url)?'新的模样，等你来看。':'形象这边，有一封回信。',note:'这次准备的形象与说明，留在这里等你。',cta:imageURL(result.result_image_url||result.image_url)?'看看新的模样':'打开形象来信'});
    }else if(['executing','processing'].includes(action.status))Object.assign(copy,{lead:'还在准备这次的回信。',note:'可以先做别的，稍后再来看看这次的进展。',cta:'看看准备进展'});
    else if(action.status==='unknown')Object.assign(copy,{lead:'这次的消息，还需要核对。',note:'暂时没有确切结果，只查询原记录，不会重复提交。',cta:'核对这次进展'});
    else if(action.status==='failed')Object.assign(copy,{lead:'这次尝试，没能顺利完成。',note:result.refunded===true?'这次的积分已退回，具体反馈留在来信里。':result.charged===false?'这次没有扣积分，可以看看这次的反馈。':'这次已确认的信息，收在这封来信里。',cta:'看看这次的回信'});
    else if(action.status==='cancelled')Object.assign(copy,{lead:'这次，就先停在这里。',note:'这次操作已取消，记录仍留在这里。'});
    else if(action.status==='quoted')Object.assign(copy,{lead:'等你决定，再继续这次尝试。',note:'这次还在等待费用确认。'});
    else if(action.status==='expired')Object.assign(copy,{lead:'这次的确认，已经过期了。',note:'想继续时，可以重新查看这次的说明。'});
    return copy;
  }
  dialog.addEventListener('cancel',event=>{if(closeLocked)event.preventDefault();});
  dialog.addEventListener('click',event=>{if(closeLocked||dialog.dataset.panel!=='upload'||event.target!==dialog)return;const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();});
  dialog.addEventListener('close',()=>{
    lockClose(false);clearTimer();releasePhoto();const q=activeQuote;activeQuote=null;
    if(q&&owner)api((q.kind==='generation'?'/stylist-api/media/':'/stylist-api/images/')+q.id+'/confirm',{method:'POST',body:JSON.stringify({confirmed:false})}).catch(e=>notify?.(e.message));
    if(opener?.isConnected)opener.focus();opener=null;
  });
  window.WardrobeJourney={
    configure(options){onProduct=options.onProduct;api=options.api;notify=options.notify;onStyle=options.onStyle;getConversation=options.getConversation;getContext=options.getContext;onRegenerate=options.onRegenerate;onNeedOutfit=options.onNeedOutfit;},
    setOwner(next){if(String(next??'')===String(owner??''))return;epoch++;viewSequence++;lockClose(false);batchChoices.clear();window.ServerGarmentUpload?.clear();owner=next??null;activeQuote=null;pendingLook=null;activeTryon=null;for(const id of watchers.keys())stopWatcher(id);finished.clear();clearTimer();releasePhoto();if(dialog.open)dialog.close();body.replaceChildren();footer.replaceChildren();scene.replaceChildren();steps.replaceChildren();document.querySelectorAll('.journey-result,.journey-invite').forEach(n=>n.remove());},
    upload,twins,history,tryon,
    offer(reply,node){
      if(reply.avatar_intent){avatarCard(reply,node);return;}
      // Legacy replies may suggest uploads merely because an outfit is incomplete.
      // Only an identified upload intent may create this invitation.
      if(!['garment','unspecified'].includes(reply.upload_intent))return;
      const ambiguous=reply.upload_intent==='unspecified',explicit=reply.upload_intent==='garment',attachment=reply.attachment_wardrobe_required===true;
      const card=el('section','journey-invite');card.setAttribute('aria-label',ambiguous?'选择照片用途':'衣物上传步骤');
      card.append(el('span','journey-card-label','衣橱小记'),el('strong','',attachment?'单张上传到个人衣橱':ambiguous?'这张照片，想用在哪里？':explicit?'把新衣服，收进你的衣橱':'让搭配更像你'));
      card.append(el('p','',attachment?'请重新选择一张只含单件衣物的照片，预览并确认上传后，再从个人衣橱搭配或试穿。聊天附图不会自动转存。':ambiguous?'衣物照片可以整理入柜；本人照片可以用来创建试穿形象，生成费用会单独确认。':'先选照片、看一眼，再由你确认上传。我会帮你抠图识别，收进个人衣橱。'));
      if(!ambiguous){const list=el('ol','journey-card-steps');for(const text of ['选择照片','预览并确认','抠图入衣橱'])list.append(el('li','',text));card.append(list);}
      card.append(button(attachment?'选择单张衣物照片':ambiguous?'上传衣物照片':explicit?'好，选择衣物照片':'上传一件衣服',()=>upload('garment',{single:attachment}),explicit));
      if(ambiguous)card.append(button('创建本人试穿形象',twins));
      card.append(el('small','journey-card-note','点击后先选图，未确认不会上传。'));node.append(card);
    },
    async restore(conversation){const token=epoch;const actions=await api('/stylist-api/images?conversation_id='+encodeURIComponent(conversation));if(current(token)&&(!getConversation||getConversation()===conversation))for(const a of actions)if(!['quoted','cancelled','expired'].includes(a.status)){renderTryon(a);if(['processing','executing'].includes(a.status))monitorTryon(a);}},
    imageURL,statusLabel
  };
})();
