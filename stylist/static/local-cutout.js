'use strict';
(() => {
  let owner=null, epoch=0, loader=null, worker=null, sequence=0, queue=Promise.resolve(), active=null;
  const cache=new Map(), pending=new Map(), controllers=new Set();
  const canvas=(width,height)=>Object.assign(document.createElement('canvas'),{width,height});
  function reset(next=null) {
    owner=next;epoch++;worker?.terminate();worker=null;
    active?.reject(Error('cancelled'));active=null;
    controllers.forEach(c=>c.abort());controllers.clear();
    cache.forEach(url=>URL.revokeObjectURL(url));cache.clear();pending.clear();queue=Promise.resolve();
  }
  function run(input,onProgress,mode='segment',width=320,height=320) {
    if (!worker) worker=new Worker('/static/cutout-worker.js?v=2');
    return new Promise((resolve,reject)=>{
      const id=++sequence;
      const finish=(error,mask)=>{
        clearTimeout(timeout);if (active?.id===id) active=null;
        error?reject(error):resolve(mask);
      };
      const timeout=setTimeout(()=>{worker?.terminate();worker=null;finish(Error('cutout_timeout'));},90000);
      active={id,reject:error=>finish(error)};
      worker.onmessage=({data})=>{if(data.id!==id)return;if(data.stage){onProgress?.(data.stage);return;}finish(data.error?Error(data.error):null,data.mask);};
      worker.onerror=()=>{worker?.terminate();worker=null;finish(Error('cutout_unavailable'));};
      worker.postMessage({id,input,mode,width,height},[input.buffer]);
    });
  }
  async function process(item,onProgress,version,preferExisting) {
    if(version!==epoch||!owner||!loader)throw Error('cancelled');
    onProgress?.('preparing');const control=new AbortController();controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),25000);let blob;
    try {
      if(preferExisting&&item.cutout_image){
        try {blob=await loader(item,control.signal,'cutout');} catch(error){if(version!==epoch||control.signal.aborted)throw error;}
      }
      if(!blob)blob=await loader(item,control.signal,'original');
    } finally {clearTimeout(timeout);controllers.delete(control);}
    if(version!==epoch)throw Error('cancelled');
    if(!(blob instanceof Blob)||blob.size>12*1024*1024)throw Error('image_unavailable');
    const image=await createImageBitmap(blob);
    if(image.width*image.height>24000000){image.close();throw Error('image_too_large');}
    const scale=Math.min(1,1280/Math.max(image.width,image.height));
    const original=canvas(Math.max(1,Math.round(image.width*scale)),Math.max(1,Math.round(image.height*scale)));
    const ctx=original.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0,original.width,original.height);image.close();
    const rgba=ctx.getImageData(0,0,original.width,original.height);let transparent=0;
    for(let i=3;i<rgba.data.length;i+=4)if(rgba.data[i]<240)transparent++;
    if(transparent/(rgba.data.length/4)>=.02){
      const cleaned=await run(rgba.data,onProgress,'alpha',original.width,original.height);
      if(version!==epoch)throw Error('cancelled');
      ctx.putImageData(new ImageData(cleaned,original.width,original.height),0,0);
    }else{
      const resized=canvas(320,320),resizedCtx=resized.getContext('2d');
      resizedCtx.drawImage(original,0,0,320,320);
      const input=CutoutCore.normalize(resizedCtx.getImageData(0,0,320,320).data);
      const pixels=await run(input,onProgress);
      if(version!==epoch)throw Error('cancelled');
      const mask=canvas(320,320);mask.getContext('2d').putImageData(new ImageData(pixels,320,320),0,0);
      ctx.globalCompositeOperation='destination-in';ctx.drawImage(mask,0,0,original.width,original.height);ctx.globalCompositeOperation='source-over';
    }
    // Trim transparent padding so differently cropped source photos share a useful scale.
    const finalPixels=ctx.getImageData(0,0,original.width,original.height).data;
    let left=original.width,top=original.height,right=-1,bottom=-1;
    for(let y=0;y<original.height;y++)for(let x=0;x<original.width;x++)if(finalPixels[(y*original.width+x)*4+3]>24){
      left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);
    }
    if(right<left||bottom<top)throw Error('empty_mask');
    left=Math.max(0,left-4);top=Math.max(0,top-4);right=Math.min(original.width-1,right+4);bottom=Math.min(original.height-1,bottom+4);
    const trimmed=canvas(right-left+1,bottom-top+1);trimmed.getContext('2d').drawImage(original,left,top,trimmed.width,trimmed.height,0,0,trimmed.width,trimmed.height);
    const result=await new Promise(resolve=>trimmed.toBlob(resolve,'image/png'));
    if(version!==epoch||!result)throw Error('cancelled');
    return URL.createObjectURL(result);
  }
  function get(item,{onProgress,preferExisting=true}={}) {
    const key=String(owner)+':'+item.product_id+':'+item.original_image+':'+(preferExisting?item.cutout_image||'':'original');
    if(cache.has(key))return Promise.resolve(cache.get(key));
    if(pending.has(key))return pending.get(key);
    const version=epoch;
    const task=queue.catch(()=>{}).then(()=>process(item,onProgress,version,preferExisting)).then(url=>{
      if(version!==epoch){URL.revokeObjectURL(url);throw Error('cancelled');}
      if(cache.size>=24){const first=cache.keys().next().value;URL.revokeObjectURL(cache.get(first));cache.delete(first);}
      cache.set(key,url);return url;
    }).finally(()=>{if(pending.get(key)===task)pending.delete(key);});
    pending.set(key,task);queue=task.catch(()=>{});return task;
  }
  window.LocalCutout={get,setOwner(next){if(String(next||'')!==String(owner||''))reset(next);},setSourceLoader(fn){loader=fn;},clear:()=>reset(null)};
  window.addEventListener('pagehide',()=>reset(null));
})();
