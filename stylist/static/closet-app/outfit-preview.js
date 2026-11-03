// Reproduce the saved iOS canvas: normalized center/size, radians, z-index and flips.
const object=value=>{if(typeof value==='string'){try{return JSON.parse(value);}catch{return null;}}return value&&typeof value==='object'?value:null;};
const url=value=>{try{if(typeof value!=='string'||!value.trim())return '';const u=new URL(value.trim(),location.origin);return ['https:','http:'].includes(u.protocol)?u.href:'';}catch{return '';}};
export function outfitPreview(item){
 const root=document.createElement('div');root.className='y-outfit-preview';root.setAttribute('aria-label',item.title||'个人搭配画布');
 const info=object(item.canvas_info)||{},data=object(info.canvas_data)||{},content=object(data.canvas_content)||{};
 const source=Array.isArray(data.product_list)?data.product_list:[];
 const layers=source.filter(p=>p&&Number.isFinite(Number(p.center?.x))&&Number.isFinite(Number(p.center?.y))&&Number.isFinite(Number(p.size?.width))&&Number.isFinite(Number(p.size?.height))&&Number(p.size?.width)>0&&Number(p.size?.height)>0).sort((a,b)=>(Number(a.z_index)||0)-(Number(b.z_index)||0));
 const ratio=Number(content.aspect_ratio);root.style.aspectRatio=Number.isFinite(ratio)&&ratio>0?String(ratio):'300 / 410';
 const color=content.background_color;if(typeof color==='string'&&CSS.supports('color',color))root.style.backgroundColor=color;
 const covers=[...new Set([item.cover_image,item.canvas_image,info.canvas_image].map(url).filter(Boolean))];let attemptedCanvas=false;
 function canvas(){attemptedCanvas=true;root.replaceChildren();root.dataset.preview='canvas';let settled=0,failed=source.length-layers.length,loaded=0;
  const complete=()=>{if(settled!==layers.length)return;root.dataset.state=loaded?(failed?'partial':'loaded'):'failed';if(!loaded){root.replaceChildren();const note=document.createElement('span');note.className='y-outfit-image-note';note.textContent=layers.length?'单品图片暂未载入':'这套搭配暂无可用画布图片';root.append(note);}else if(failed){const note=document.createElement('span');note.className='y-outfit-image-note';note.textContent='部分单品图片暂未载入';root.append(note);}};
  for(const product of layers){const src=url(product.cutout_image);if(!src){settled++;failed++;continue;}const frame=document.createElement('div');frame.className='y-outfit-layer';frame.style.left=Number(product.center.x)*100+'%';frame.style.top=Number(product.center.y)*100+'%';frame.style.width=Number(product.size.width)*100+'%';frame.style.height=Number(product.size.height)*100+'%';frame.style.transform='translate(-50%, -50%) rotate('+(Number(product.rotation)||0)+'rad)';const image=document.createElement('img');image.src=src;image.alt=product.class_name||'搭配单品';image.draggable=false;if(product.flip===1)image.style.transform='scaleX(-1)';if(product.flip===2)image.style.transform='scaleY(-1)';image.onload=()=>{loaded++;settled++;complete();};image.onerror=()=>{failed++;settled++;frame.remove();complete();};frame.append(image);root.append(frame);}complete();
 }
 function saved(index=0){if(index>=covers.length){if(!attemptedCanvas&&layers.length)canvas();else{root.dataset.state='failed';root.textContent='封面图片暂未载入';}return;}root.replaceChildren();root.dataset.preview='image';const image=document.createElement('img');image.className='y-outfit-saved';image.alt=item.title||'我的搭配';image.src=covers[index];image.onload=()=>root.dataset.state='loaded';image.onerror=()=>saved(index+1);root.append(image);}
 if(item.outfit_id_type===1&&item.status===0){root.dataset.state='processing';root.textContent='AI搭配生成中'+(Number.isInteger(item.progress)?' · '+Math.max(0,Math.min(100,item.progress))+'%':'');}
 else if(item.cover_image||Number(content.border?.type)>0||!layers.length){if(covers.length)saved();else canvas();}
 else canvas();
 return root;
}
