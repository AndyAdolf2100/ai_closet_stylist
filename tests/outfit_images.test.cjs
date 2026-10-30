const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('stylist/static/outfit-images.js','utf8');
function setup(){
 const dom=new JSDOM('<html data-stylist-gender="female"></html>',{runScripts:'outside-only'}),w=dom.window;
 const create=w.document.createElement.bind(w.document);
 w.document.createElement=tag=>tag==='canvas'?{width:0,height:0,getContext:()=>({fillRect(){},drawImage(){}}),toBlob:fn=>fn(new w.Blob(['white']))}:create(tag);
 w.createImageBitmap=async()=>({width:960,height:1200,close(){}});
 w.eval(source);w.OutfitImages.setOwner('1');return dom;
}
test('reopening a saved conversation reads its OSS URL without segmentation, canvas work or upload',async()=>{
 const dom=setup(),w=dom.window;let loads=0,downloads=0;
 w.LocalCutout={get(){assert.fail('saved image must not rerun segmentation')}};
 w.OutfitImages.configure({
  load:async ref=>{loads++;assert.equal(ref.conversationId,'owned');return {status:'completed',image_url:'https://images.invalid/saved.png'}},
  save:()=>assert.fail('saved image must not upload again'),
  download:async ref=>{downloads++;assert.equal(ref.theme,'female');return new w.Blob(['same-oss-bytes'])}
 });
 const look={items:[{product_id:'1',original_image:'https://images.invalid/original.png'}]},ref={conversationId:'owned',version:2,index:0};
 const first=await w.OutfitImages.get(look,ref);assert.equal(first.image_url,'https://images.invalid/saved.png');
 assert.equal((await w.OutfitImages.get(look,ref)).image_url,first.image_url);assert.equal(loads,1);
 w.URL.createObjectURL=()=> 'blob:download';w.URL.revokeObjectURL=()=>{};w.HTMLAnchorElement.prototype.click=function(){};
 const timer=w.setTimeout;w.setTimeout=fn=>{fn();return 0};await w.OutfitImages.download(first);w.setTimeout=timer;assert.equal(downloads,1);dom.window.close();
});
test('themes reuse the same transparent image; accounts remain isolated',async()=>{
 const dom=setup(),w=dom.window,seen=[];
 w.OutfitImages.configure({load:async ref=>{seen.push(ref.theme);return {status:'completed',image_url:'https://images.invalid/transparent.png'}}});
 const look={items:[{product_id:'1'}]},ref={conversationId:'a',version:1,index:0};
 const first=await w.OutfitImages.get(look,ref);
 w.document.documentElement.dataset.stylistGender='male';assert.equal((await w.OutfitImages.get(look,ref)).image_url,first.image_url);
 w.OutfitImages.setOwner('2');await w.OutfitImages.get(look,ref);assert.deepEqual(seen,['female','male']);dom.window.close();
});
test('failed upload state requires explicit retry and never starts fresh work on historical reload',async()=>{
 const dom=setup(),w=dom.window;w.OutfitImages.configure({load:async()=>({status:'failed'})});
 w.LocalCutout={get:()=>assert.fail('must wait for manual retry')};
 await assert.rejects(w.OutfitImages.get({items:[{product_id:'1'}]},{conversationId:'a',version:1,index:0}),/重试/);dom.window.close();
});
test('download mattes the saved transparent image onto white regardless of assistant theme',async()=>{
 const dom=setup(),w=dom.window,events=[];w.document.documentElement.dataset.stylistGender='male';
 const raw=new w.Blob(['transparent']),output=new w.Blob(['white-output']);
 w.OutfitImages.configure({download:async()=>raw});
 const create=w.document.createElement.bind(w.document),ctx={fillStyle:'',fillRect(x,y,width,height){events.push(['fill',this.fillStyle,width,height])},drawImage(){events.push(['draw'])}};
 w.document.createElement=tag=>tag==='canvas'?{getContext:()=>ctx,toBlob:fn=>fn(output)}:create(tag);
 w.URL.createObjectURL=blob=>{assert.equal(blob,output);assert.notEqual(blob,raw);return 'blob:white'};
 w.URL.revokeObjectURL=()=>{};w.HTMLAnchorElement.prototype.click=function(){};w.setTimeout=fn=>{fn();return 0};
 await w.OutfitImages.download({ref:{conversationId:'a',version:1,index:0}});
 assert.deepEqual(events,[['fill','#ffffff',960,1200],['draw']]);dom.window.close();
});
