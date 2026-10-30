const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {JSDOM}=require('jsdom');
test('U2Net normalization is planar RGB and guards empty, invalid and full masks',()=>{
 const scope={};vm.runInNewContext(fs.readFileSync('stylist/static/cutout-core.js','utf8'),scope);
 const input=scope.CutoutCore.normalize(new Uint8ClampedArray([255,0,0,255,0,255,0,255]));
 assert.equal(input.length,6);assert(Math.abs(input[0]-(1-.485)/.229)<1e-5);assert(input[1]<0);assert(input[3]>0);
 assert.throws(()=>scope.CutoutCore.maskPixels(new Float32Array([0,0,0,0])));
 assert.throws(()=>scope.CutoutCore.maskPixels(new Float32Array([NaN,1])));
 const mask=scope.CutoutCore.maskPixels(new Float32Array([0,1,.5,0]));assert.equal(mask.length,16);assert.equal(mask[3],0);assert.equal(mask[7],255);
});
test('detached background letters are removed while both shoes and connected detail survive',()=>{
 const scope={};vm.runInNewContext(fs.readFileSync('stylist/static/cutout-core.js','utf8'),scope);
 const w=120,h=90,mask=new Uint8ClampedArray(w*h*4);
 const rect=(left,top,width,height,alpha=255)=>{for(let y=top;y<top+height;y++)for(let x=left;x<left+width;x++)mask[(y*w+x)*4+3]=alpha};
 rect(10,25,35,55);rect(65,25,35,55);rect(5,3,4,3,55);rect(110,7,3,5,70);rect(44,45,10,2,130);
 const cleaned=scope.CutoutCore.cleanMask(mask,w,h);
 assert.equal(cleaned[(3*w+5)*4+3],0);assert.equal(cleaned[(7*w+110)*4+3],0);
 assert.equal(cleaned[(40*w+20)*4+3],255);assert.equal(cleaned[(40*w+75)*4+3],255);
 assert.equal(cleaned[(45*w+52)*4+3],130);
});
function setup(){
 const dom=new JSDOM('',{runScripts:'outside-only'}),w=dom.window;let count=0;const revoked=[];
 w.URL.createObjectURL=()=>`blob:cutout-${++count}`;w.URL.revokeObjectURL=u=>revoked.push(u);
 // An already-transparent source bypasses inference, letting us test lifecycle without a model.
 const data=new Uint8ClampedArray([255,0,0,255,255,255,255,0,255,255,255,0,255,255,255,0]);
 const context={drawImage(){},putImageData(){},getImageData(){return {data}}};
 const create=w.document.createElement.bind(w.document);
 w.document.createElement=tag=>tag==='canvas'?{width:0,height:0,getContext:()=>context,toBlob:fn=>fn(new w.Blob(['png'],{type:'image/png'}))}:create(tag);
 w.createImageBitmap=async()=>({width:2,height:2,close(){}});
 w.ImageData=class {constructor(data,width,height){Object.assign(this,{data,width,height})}};
 w.Worker=class {terminate(){}postMessage(message){queueMicrotask(()=>this.onmessage?.({data:{id:message.id,mask:message.input}}))}};
 w.eval(fs.readFileSync('stylist/static/local-cutout.js','utf8'));
 w.LocalCutout.setOwner('1');return {dom,w,revoked};
}
test('duplicate image work is shared and memory results are cleared on owner changes',async()=>{
 const {dom,w,revoked}=setup();let calls=0;
 w.LocalCutout.setSourceLoader(async()=>{calls++;return new w.Blob(['source'])});
 const item={product_id:'12',original_image:'https://photo.invalid/a.png'};
 const first=w.LocalCutout.get(item),duplicate=w.LocalCutout.get(item);assert.equal(first,duplicate);
 const url=await first;assert.equal(await w.LocalCutout.get(item),url);assert.equal(calls,1);
 w.LocalCutout.setOwner('2');assert.deepEqual(revoked,[url]);await w.LocalCutout.get(item);assert.equal(calls,2);dom.window.close();
});
test('a late image load cannot return an old account result',async()=>{
 const {dom,w}=setup();let release;
 w.LocalCutout.setSourceLoader(()=>new Promise(resolve=>{release=resolve}));
 const task=w.LocalCutout.get({product_id:'12',original_image:'x'});const rejection=assert.rejects(task,/cancelled/);
 await Promise.resolve();await Promise.resolve();w.LocalCutout.setOwner('2');release(new w.Blob(['old']));await rejection;dom.window.close();
});
test('a failed load is not cached and reopening can retry',async()=>{
 const {dom,w}=setup();let calls=0;
 w.LocalCutout.setSourceLoader(async()=>{if(++calls===1)throw Error('network');return new w.Blob(['ok'])});
 const item={product_id:'12',original_image:'x'};await assert.rejects(w.LocalCutout.get(item),/network/);assert.match(await w.LocalCutout.get(item),/^blob:/);assert.equal(calls,2);dom.window.close();
});
