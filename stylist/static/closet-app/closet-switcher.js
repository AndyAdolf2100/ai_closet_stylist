// Same catalog and item operations for regular and family closets. Family persistence
// remains gated until the upstream Server supports is_family.
export function createClosetSwitcher({read,write,onSelect,getSelected,getProducts,reload,notify}){
 const el=(t,c,text)=>{const n=document.createElement(t);n.className=c||'';if(text!=null)n.textContent=text;return n;};
 const button=(text,run,cls='')=>{const b=el('button',cls,text);b.type='button';b.onclick=async()=>{if(b.disabled)return;b.disabled=true;try{await run();}catch(e){notify(e.message);}finally{b.disabled=false;}};return b;};
 const token=()=>{try{return JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')||'null')?.access_token||'';}catch{return '';}};
 let rows=[],owner='',titleButton;
 function dialog(title,cls=''){const ownerToken=token(),d=el('dialog','closet-dialog '+cls);d.dataset.appDialog='true';d.setAttribute('aria-label',title);const h=el('header');h.append(el('h2','',title),button('×',()=>d.close(),'closet-close'));d.append(h);document.body.append(d);d.addEventListener('close',()=>d.remove());d.showModal();return {d,current:()=>d.isConnected&&d.open&&token()===ownerToken};}
 function choose(value){onSelect(value);}
 async function addItems(){
  const selected=getSelected();if(!selected)return;
  if(selected.is_family){const {d}=dialog('添加到家人衣橱');d.append(button('从我的衣橱选择',()=>{d.close();return pickItems(selected);}),button('上传新单品',()=>notify('家人衣橱上传功能准备中，尚未上传。')),button('选择系统单品搭配',()=>notify('家人衣橱系统搭配功能准备中，尚未生成。')),el('p','closet-hint','家人衣橱的上传与系统搭配功能准备中，暂不能提交。'));return;}
  return pickItems(selected);
 }
 async function pickItems(selected){
  const {d,current}=dialog('从我的衣橱选择');d.append(el('p','closet-hint','选中的衣物会加入此分类，仍保留在我的衣橱中。'));
  const loading=el('p','closet-hint','正在读取我的衣橱…');d.append(loading);
  try{const [recent,categories]=await Promise.all([read('recent'),read('categories')]);if(!current())return;loading.remove();const seen=new Set(),items=[...(recent.list||[]),...(categories.list||[]).flatMap(c=>c.list||[])].filter(p=>{const id=Number(p.user_product_id);if(!Number.isSafeInteger(id)||id<=0||seen.has(id))return false;seen.add(id);return true;});
   const picked=new Set(),grid=el('div','closet-pick-grid'),count=el('p','closet-hint','已选0件');
   for(const item of items){const label=el('label','closet-pick'),check=el('input');check.type='checkbox';check.onchange=()=>{if(check.checked)picked.add(Number(item.user_product_id));else picked.delete(Number(item.user_product_id));count.textContent=`已选${picked.size}件`;save.disabled=!picked.size;};const image=el('img');const src=item.cutout_image||item.original_image||item.image_url||item.cover_image;try{const url=new URL(src);if(['https:','http:'].includes(url.protocol))image.src=url.href;}catch{}image.alt='';label.append(check,image,el('span','',item.title||item.product_name||item.class_name||'衣物'));grid.append(label);}
   const save=button('确认加入',async()=>{if(!current()||getSelected()?.id!==selected.id)return;await write('closet-items/'+selected.id,{user_product_id:[...picked]});if(!current())return;d.close();await reload();},'closet-primary');save.disabled=true;d.append(grid,count,save);if(!items.length)d.append(el('p','closet-hint','当前已加载库存中暂无可选单品。'));
  }catch(e){if(current()){loading.textContent=e.message;d.append(button('重新读取',()=>{d.close();return addItems();}));}}
 }
 function create(){const {d,current}=dialog('创建分类衣橱');const name=el('input');name.placeholder='衣橱名称';name.maxLength=40;name.required=true;name.setAttribute('aria-label','衣橱名称');
  const save=button('创建',async()=>{if(!name.value.trim()){name.focus();return;}if(!current())return;const result=await write('closet-create',{name:name.value.trim(),remark:'',is_family:false});if(!current())return;if(!result.id)throw Error('创建结果待确认，请刷新衣橱列表核对，勿重复提交。');d.close();await reload();choose(result);},'closet-primary');d.append(name,save);name.focus();}
 function menu(){
  const {d}=dialog('选择衣橱','closet-menu');titleButton.setAttribute('aria-expanded','true');
  const content=el('div','closet-menu-content');d.append(content);
  const group=(label,list)=>{content.append(el('p','closet-group',label));list.forEach(row=>{
   const selected=(row?.id||null)===(getSelected()?.id||null),b=button('',()=>{d.close();choose(row);},'closet-option');b.setAttribute('aria-pressed',String(selected));
   const copy=el('span','closet-option-copy');copy.append(el('strong','',row?.name||'我的衣橱'),el('small','',row?row.is_family?'专属的穿搭小天地':'从我的衣橱收进的喜欢':'你已拥有的衣物'));
   const mark=el('span','closet-monogram',row?row.name?.slice(0,1)||'衣':'');if(!row){mark.classList.add('closet-my-mark');mark.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="3" width="16" height="17" rx="2"/><path d="M12 3v17M9 10v3m6-3v3M6 20v2m12-2v2"/></svg>';}
   b.append(mark,copy,el('span','closet-selected',selected?'✓':''));content.append(b);
  });};
  group('我的衣橱',[null,...rows.filter(r=>!r.is_family)]);
  const add=button('',()=>{d.close();create();},'closet-option closet-create-option'),copy=el('span','closet-option-copy');copy.append(el('strong','','分类衣橱'),el('small','','从已有单品，整理一份喜欢'));add.setAttribute('aria-label','分类衣橱');add.append(el('span','closet-monogram','＋'),copy);content.append(add);
  /* 暂时隐藏家人衣橱分组（含分割线）和创建入口，保留已有数据。
  group('家人衣橱',rows.filter(r=>r.is_family));
  const familyAdd=button('',()=>{d.close();create(true);},'closet-option closet-create-option'),familyCopy=el('span','closet-option-copy');familyAdd.setAttribute('aria-label','家庭衣橱');familyCopy.append(el('strong','','家庭衣橱'),el('small','','为家人，留一处穿搭天地'));familyAdd.append(el('span','closet-monogram','＋'),familyCopy);content.append(familyAdd);
  */
  const position=()=>{const anchor=titleButton.getBoundingClientRect(),shell=document.querySelector('#wardrobe').getBoundingClientRect(),width=Math.min(320,shell.width-40,innerWidth-32),left=Math.max(16,Math.min(shell.left+20,innerWidth-width-16)),top=Math.max(16,Math.min(anchor.bottom+12,innerHeight-160));d.style.width=width+'px';d.style.left=left+'px';d.style.top=top+'px';d.style.setProperty('--closet-menu-height',Math.max(120,innerHeight-top-24)+'px');d.style.setProperty('--closet-arrow-left',Math.max(24,Math.min(anchor.left+58-left,width-32))+'px');};
  position();window.addEventListener('resize',position);d.addEventListener('close',()=>{titleButton.setAttribute('aria-expanded','false');if(!document.querySelector('.closet-dialog[open]'))titleButton.focus({preventScroll:true});window.removeEventListener('resize',position);});
  d.addEventListener('click',event=>{if(event.target!==d)return;const r=d.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)d.close();});
 }

 function update(next){rows=(next||[]).map(r=>({...r,is_family:r.is_family===true||r.is_family===1||r.is_family==='1'}));const nextOwner=token();if(owner&&owner!==nextOwner){document.querySelectorAll('.closet-dialog').forEach(d=>d.close());choose(null);}owner=nextOwner;const h=document.querySelector('#wardrobe h1');if(!h)return;if(!titleButton){titleButton=button('',menu,'closet-title-button');titleButton.setAttribute('aria-haspopup','dialog');h.replaceChildren(titleButton);}const titleName=getSelected()?.name||'我的衣橱',titleLabel=el('span','closet-title-label',titleName),chevron=el('span','closet-title-chevron');chevron.setAttribute('aria-hidden','true');chevron.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m7 10 5 5 5-5"/></svg>';titleButton.replaceChildren(titleLabel,chevron);titleButton.setAttribute('aria-label',titleName+'，选择衣橱');const add=document.querySelector('.y-wardrobe-add');if(add){add.onclick=()=>getSelected()?addItems():window.dispatchEvent(new CustomEvent('yijian-agent-open',{detail:'upload'}));}}
 return {update,create,addItems};
}
