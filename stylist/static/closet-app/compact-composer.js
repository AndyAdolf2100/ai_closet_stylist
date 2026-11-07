// H5 presentation of the dev_2.0.0 iOS composer; existing send/photo handlers stay attached.
export function mountCompactComposer(host, voice, attachment) {
  const form=host.querySelector('#chat-form'),input=host.querySelector('#message'),send=host.querySelector('#send');
  const row=document.createElement('div');row.className='y-compact-row';
  const slot=document.createElement('div');slot.className='y-composer-action';
  const field=document.createElement('div');field.className='y-composer-field';
  const hint=document.createElement('span');hint.className='y-composer-placeholder';hint.setAttribute('aria-hidden','true');
  const originalPlaceholder=input.placeholder;input.placeholder='';input.rows=1;
  hint.textContent=originalPlaceholder;
  // Persona updates may replace the placeholder after mounting.
  new MutationObserver(()=>{if(input.placeholder){hint.textContent=input.placeholder;input.placeholder='';}}).observe(input,{attributes:true,attributeFilter:['placeholder']});
  for(const [button,file] of [[voice,'voice.svg'],[attachment,'attachment.png']]){
    const img=document.createElement('img');img.src='/static/closet-app/assets/ios-agent/'+file;img.alt='';img.setAttribute('aria-hidden','true');button.replaceChildren(img);
  }
  slot.append(attachment,send);field.append(input,hint);row.append(voice,field,slot);
  form.querySelector('.composer-bottom').hidden=true;
  form.insertBefore(row,form.querySelector('.y-attachment-options'));
  form.classList.add('y-compact-composer');
  function sync(){
    const hasText=!!input.value.trim(),hasPhoto=!!window.ChatAttachments?.get();
    form.dataset.hasDraft=String(hasText||hasPhoto||send.disabled||send.dataset.state==='stop'||send.dataset.state==='stopping');
    const state=send.dataset.state||'send';
    if(send.dataset.iconState!==state||!send.querySelector('img')){const img=document.createElement('img');img.src='/static/closet-app/assets/ios-agent/'+(state==='send'?'send':'stop')+'.png';img.alt='';img.setAttribute('aria-hidden','true');send.replaceChildren(img);send.dataset.iconState=state;}
    if(!send.hasAttribute('aria-label'))send.setAttribute('aria-label','发送');
    hint.hidden=!!input.value;
    input.style.height='44px';
    const height=input.value?Math.min(140,Math.max(44,input.scrollHeight)):44;
    input.style.height=height+'px';input.style.overflowY=height>=140?'auto':'hidden';
  }
  input.addEventListener('input',sync);input.addEventListener('focus',sync);
  form.addEventListener('reset',()=>queueMicrotask(sync));
  new MutationObserver(sync).observe(send,{attributes:true,attributeFilter:['disabled','data-state'],childList:true,subtree:true});
  const preview=form.querySelector('.chat-attachment-preview');
  if(preview)new MutationObserver(sync).observe(preview,{attributes:true,attributeFilter:['hidden']});
  let width=0;new ResizeObserver(()=>{if(input.clientWidth!==width){width=input.clientWidth;sync();}}).observe(field);
  sync();
}
