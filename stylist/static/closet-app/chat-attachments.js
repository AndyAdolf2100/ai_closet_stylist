// Same interaction as iOS AgentComposerView: one photo, editable draft, explicit send.
// No wardrobe ingestion or generic file upload occurs in this module.
export function mountChatAttachments(host, trigger) {
  if(window.ChatAttachments)return;
  const form=host.querySelector('#chat-form');
  const notify=text=>(window.CompanionSettings?.notify||window.PreviewMessage?.notify)(text);
  let draft=null,epoch=0,busy=false;
  const owner=()=>sessionStorage.getItem('ai-closet-stylist-session-v1');
  const menu=document.createElement('div');menu.className='y-attachment-options';menu.id='y-attachment-options';menu.hidden=true;menu.setAttribute('role','group');menu.setAttribute('aria-label','添加附件');
  const preview=document.createElement('div');preview.className='chat-attachment-preview';preview.hidden=true;
  const photo=document.createElement('img');photo.alt='待发送的图片附件';
  const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.setAttribute('aria-label','移除图片附件');preview.append(photo,remove);
  form.querySelector('textarea').after(preview);form.append(menu);
  const close=()=>{menu.hidden=true;trigger.setAttribute('aria-expanded','false');};
  function clear(){epoch++;draft=null;photo.removeAttribute('src');preview.hidden=true;close();}
  remove.onclick=()=>{if(!busy){if(draft)window.AgentTracking?.track('AgentAttachment',{outcome:'removed'});clear();}};
  const controls=[trigger,remove];
  for(const [label,camera] of [['照片',false],['拍摄',true]]){
    const button=document.createElement('button');button.type='button';button.className='y-attachment-choice';button.dataset.attachment=camera?'camera':'photo';
    button.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true">'+(camera?'<path d="M8 6 9 3h6l1 3h4v14H4V6Z"/><circle cx="12" cy="12" r="4"/>':'<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="8" cy="9" r="1.5"/><path d="m4 17 5-5 4 4 3-3 4 4"/>')+'</svg>';
    const caption=document.createElement('span');caption.textContent=label;button.append(caption);
    const input=document.createElement('input');input.type='file';input.accept='image/jpeg,image/png,image/webp';input.hidden=true;if(camera)input.setAttribute('capture','environment');
    // iOS uses its existing photo picker and camera permission flow; Web capture is a browser hint.
    let pickedOwner,pickedEpoch;
    button.onclick=()=>{if(busy)return;close();pickedOwner=owner();pickedEpoch=++epoch;input.value='';input.click();};
    input.onchange=async()=>{
      const file=input.files?.[0];if(!file)return;
      window.AgentTracking?.track('AgentAttachment',{outcome:'selected',source:camera?'camera':'photo'});
      if(busy||pickedEpoch!==epoch||pickedOwner!==owner())return;
      if(!/^image\/(jpeg|png|webp)$/.test(file.type)||file.size>10*1024*1024){window.AgentTracking?.track('AgentAttachment',{outcome:'failed'});notify('选一张 10MB 以内的 JPG、PNG 或 WebP 图片吧。');return;}
      const ticket=pickedEpoch,url=URL.createObjectURL(file);
      try{
        const image=new Image();image.src=url;await image.decode();
        if(!image.naturalWidth||!image.naturalHeight)throw Error();
        const scale=Math.min(1,2048/Math.max(image.naturalWidth,image.naturalHeight));
        const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(image.naturalWidth*scale));canvas.height=Math.max(1,Math.round(image.naturalHeight*scale));
        const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(image,0,0,canvas.width,canvas.height);
        const data=canvas.toDataURL('image/jpeg',.85);
        if(data.length>13981039)throw Error();
        if(ticket!==epoch||pickedOwner!==owner()||busy)return;
        draft=data;photo.src=data;preview.hidden=false;window.AgentTracking?.track('AgentAttachment',{outcome:'ready'});
      }catch{if(ticket===epoch&&pickedOwner===owner()){window.AgentTracking?.track('AgentAttachment',{outcome:'failed'});notify('这张图片没能读取，换一张试试吧。');}}
      finally{URL.revokeObjectURL(url);input.value='';}
    };
    controls.push(button);menu.append(button,input);
  }
  trigger.setAttribute('aria-label','添加附件');trigger.setAttribute('aria-controls',menu.id);trigger.setAttribute('aria-expanded','false');trigger.removeAttribute('aria-haspopup');
  trigger.onclick=()=>{if(busy)return;menu.hidden=!menu.hidden;trigger.setAttribute('aria-expanded',String(!menu.hidden));};
  form.querySelector('textarea').addEventListener('focus',close);
  menu.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close();trigger.focus();}});
  window.ChatAttachments={get:()=>draft,clear,ack:image=>{if(image===draft)clear();},setBusy:value=>{busy=value;if(value){epoch++;close();}controls.forEach(button=>button.disabled=value);}};
}
