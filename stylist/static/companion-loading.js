'use strict';

// Shared, CSS-driven loading art. It never starts requests or stores profile data.
(() => {
  const element=(tag,className,text)=>{
    const node=document.createElement(tag);node.className=className;
    if(text!==undefined)node.textContent=text;
    return node;
  };
  function icon({gender,persona,size='medium',label}={}){
    const node=element('span','companion-loading');
    const character=window.CompanionCharacters?.all.find(item=>item.id===persona);
    if(character){
      gender=character.gender;node.dataset.persona=character.id;
      node.style.setProperty("--loading-art", `url("/static/assets/characters/companion-scenes-v1/${character.id}-hero.png")`);
    }
    if(gender==='male'||gender==='female')node.dataset.gender=gender;
    node.dataset.size=['small','medium','large'].includes(size)?size:'medium';
    if(label){node.setAttribute('role','img');node.setAttribute('aria-label',label);}
    else node.setAttribute('aria-hidden','true');
    const portrait=element('span','companion-loading-portrait'),orbit=element('span','companion-loading-orbit');
    node.append(portrait,orbit);
    return node;
  }
  function create({message='正在准备…',detail='',announce=true,...options}={}){
    const node=element('div','companion-loader'),copy=element('div','companion-loader-copy');
    if(announce){node.setAttribute('role','status');node.setAttribute('aria-live','polite');}
    const heading=element('strong','',message),note=element('p','',detail);
    heading.dataset.loadingMessage='';note.dataset.loadingDetail='';note.hidden=!detail;
    copy.append(heading,note);node.append(icon(options),copy);
    return node;
  }
  function update(node,{message,detail}={}){
    if(message!==undefined)node.querySelector('[data-loading-message]').textContent=message;
    if(detail!==undefined){const note=node.querySelector('[data-loading-detail]');note.textContent=detail;note.hidden=!detail;}
  }
  window.CompanionLoading=Object.freeze({icon,create,update});
})();
