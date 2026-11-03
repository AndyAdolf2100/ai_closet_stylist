/* Shared message surface for standalone previews; no account/settings initialization. */
(()=>{
  const panel=document.createElement('section');panel.className='preview-message';panel.hidden=true;
  panel.innerHTML='<div class="preview-message-copy" role="status" aria-live="polite" aria-atomic="true"><strong></strong><p></p></div><button type="button" aria-label="关闭消息">×</button>';
  document.body.append(panel);
  let timer;
  const hide=()=>{clearTimeout(timer);panel.hidden=true;};
  const schedule=()=>{clearTimeout(timer);timer=setTimeout(hide,7000);};
  panel.querySelector('button').onclick=hide;
  panel.addEventListener('mouseenter',()=>clearTimeout(timer));panel.addEventListener('mouseleave',schedule);
  panel.addEventListener('focusin',()=>clearTimeout(timer));panel.addEventListener('focusout',schedule);
  panel.addEventListener('keydown',e=>{if(e.key==='Escape')hide();});
  window.PreviewMessage={hide,notify(body,options={}){
    if(window.CompanionSettings?.notify&&(!document.getElementById('yijian-agent-root')||!document.getElementById('agent-page').hidden)){window.CompanionSettings.notify(body);return;}
    const host=[...document.querySelectorAll('dialog[open]')].at(-1)||document.body;
    host.append(panel);panel.querySelector('img')?.remove();
    if(window.CompanionCharacters?.all.some(c=>c.id===options.role)){const avatar=document.createElement('img');avatar.alt='';avatar.src='/static/assets/characters/companion-scenes-v1/'+options.role+'-avatar.png';panel.prepend(avatar);}
    panel.querySelector('strong').textContent=options.name||'衣间';panel.querySelector('p').textContent=body;
    panel.hidden=false;schedule();
  }};
})();
