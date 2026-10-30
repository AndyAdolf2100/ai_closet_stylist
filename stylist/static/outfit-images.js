'use strict';
(() => {
  let persistence=null,owner=null,epoch=0;
  const jobs=new Map(),previews=new Set();
  const theme=()=>document.documentElement.dataset.stylistGender==='male'?'male':'female';
  const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  async function pixels(look){
    const urls=await Promise.all(look.items.map(item=>window.LocalCutout.get(item)));
    const images=await Promise.all(urls.map(url=>new Promise((resolve,reject)=>{
      const img=new Image(),timeout=setTimeout(()=>reject(Error('图片加载超时，请重试。')),15000);
      img.onload=()=>{clearTimeout(timeout);resolve(img)};img.onerror=()=>{clearTimeout(timeout);reject(Error('衣物图片暂时无法加载。'))};img.src=url;
    })));
    const canvas=document.createElement('canvas');canvas.width=960;canvas.height=1200;
    // Keep alpha untouched: assistant theme backgrounds belong to CSS, never the OSS image.
    const ctx=canvas.getContext('2d');
    for(const {p,i} of OutfitBoard.layout(look.items).map((p,i)=>({p,i})).sort((a,b)=>a.p.z-b.p.z)){
      const img=images[i],w=p.w/100*960,h=p.h/100*1200,s=Math.min(w/img.naturalWidth,h/img.naturalHeight);
      ctx.drawImage(img,p.x/100*960-img.naturalWidth*s/2,p.y/100*1200-img.naturalHeight*s/2,img.naturalWidth*s,img.naturalHeight*s);
    }
    return canvas.toDataURL('image/png');
  }
  function get(look,ref,retry=false){
    const gender=theme(),key=JSON.stringify([owner,ref,look.items.map(p=>[p.product_id,p.original_image,p.cutout_image])]);
    if(jobs.has(key))return jobs.get(key);
    const version=epoch;
    const current=()=>{if(version!==epoch)throw Error('cancelled');};
    const task=(async()=>{
      let saved={status:'missing'};
      if(ref){
        if(!persistence||!owner)throw Error('请先连接衣橱，再查看这套搭配。');
        saved=await persistence.load({...ref,theme:gender});current();
        for(let i=0;saved.status==='processing'&&i<15;i++){
          await pause(2000);current();saved=await persistence.load({...ref,theme:gender});current();
        }
        if(saved.status==='completed')return {...saved,ref:{...ref,theme:gender}};
        if(saved.status!=='missing'&&!retry)throw Error('搭配图尚未保存完成，请重试。');
      }
      const data=await pixels(look);current();
      if(ref){const result=await persistence.save({...ref,theme:gender,image_data:data,retry});current();return {...result,ref:{...ref,theme:gender}};}
      const blob=await(await fetch(data)).blob();current();const url=URL.createObjectURL(blob);previews.add(url);
      return {status:'completed',image_url:url,theme:gender};
    })().catch(error=>{if(jobs.get(key)===task)jobs.delete(key);throw error;});
    jobs.set(key,task);return task;
  }
  async function download(result){
    const version=epoch;
    const blob=result.ref?await persistence.download(result.ref):await(await fetch(result.image_url)).blob();
    if(version!==epoch)return;
    // Display/storage stay transparent; the user explicitly requested white-background downloads.
    const image=await createImageBitmap(blob),canvas=document.createElement('canvas');
    canvas.width=image.width;canvas.height=image.height;const ctx=canvas.getContext('2d');
    ctx.fillStyle='#ffffff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(image,0,0);image.close();
    const output=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
    if(version!==epoch)return;
    if(!output)throw Error('图片下载未完成，请重试。');
    const url=URL.createObjectURL(output),link=document.createElement('a');link.href=url;link.download='yiyi-outfit.png';link.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
  }
  window.OutfitImages={get,download,configure(value){persistence=value},setOwner(value){
    if(owner===value)return;owner=value;epoch++;jobs.clear();previews.forEach(url=>URL.revokeObjectURL(url));previews.clear();
    window.dispatchEvent(new CustomEvent('outfit-images-owner-change',{detail:!!value}));
  }};
})();
