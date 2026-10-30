const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('stylist/static/outfit-board.js','utf8');
function setup(){
 const dom=new JSDOM('<button id="before">此前操作</button>',{runScripts:'outside-only',url:'https://wardrobe.invalid'});
 const w=dom.window;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'))};
 w.Image=class {constructor(){this.complete=true;this.naturalWidth=1;}set src(value){this.value=value;queueMicrotask(()=>this.onload?.())}};
 w.OutfitImages={get:async()=>({image_url:'https://photos.invalid/final.png'}),download:async()=>{}};
 w.eval(source);return {dom,w,board:w.OutfitBoard};
}
const item=(slot,extra={})=>({slot,source:'user',title:slot,cutout_image:'https://photos.invalid/cut.png',original_image:'https://photos.invalid/original.jpg',...extra});
const ready=()=>new Promise(resolve=>setTimeout(resolve,0));
test('layers follow garment attributes, outerwear and accessories stay above inner pieces',()=>{
 const {dom,board}=setup();
 const items=[item('outer',{secondary_class_name:'大衣'}),item('top',{secondary_class_name:'毛衣'}),item('accessory'),item('top',{secondary_class_name:'衬衫'}),item('outer',{secondary_class_name:'西装'})];
 const p=board.layout(items);
 assert(p[0].z>p[4].z);assert(p[1].z>p[3].z);assert(p[4].z>p[1].z);assert(p[2].z>p[0].z);
 assert.notEqual(p[1].x,p[3].x);
 const many=board.layout(Array.from({length:8},()=>item('accessory')));
 assert.equal(new Set(many.map(x=>`${x.x}:${x.y}`)).size,8);
 for(const pos of many){assert(pos.x-pos.w/2>=0&&pos.x+pos.w/2<=100);assert(pos.y-pos.h/2>=0&&pos.y+pos.h/2<=100)}
 dom.window.close();
});
test('missing historic categories are inferred only from category evidence',()=>{
 const {dom,board}=setup();assert.equal(board.role({secondary_class_name:'风衣'}),'outer');
 assert.equal(board.role({class_name:'半身裙'}),'bottom');assert.equal(board.role({description:'外套上有包'}),'other');dom.window.close();
});
test('selecting a piece opens its original detail; existing large preview restores detail focus',async()=>{
 const {dom,w,board}=setup();const items=[item('top',{title:'白衬衫',material:'棉',color:'白色'}),item('outer',{title:'风衣'}),item('shoes')];
 const root=board.create({title:'舒服的通勤',items});w.document.body.append(root);await ready();
 root.querySelectorAll('.outfit-piece')[1].click();let modal=w.document.querySelector('dialog');assert(modal.open);
 assert.equal(modal.querySelector('.outfit-item-info h3').textContent,'风衣');
 assert.equal(modal.querySelector('.outfit-original img').src,'https://photos.invalid/original.jpg');
 modal.querySelector('.outfit-thumbnail').click();assert.match(modal.querySelector('dl').textContent,/棉/);
 w.eval(fs.readFileSync('stylist/static/product-preview.js','utf8'));
 const trigger=modal.querySelector('.outfit-original');trigger.click();
 const preview=w.document.getElementById('product-preview');assert(preview.open);assert(modal.open);
 assert.equal(preview.querySelector('img').src,'https://photos.invalid/original.jpg');
 assert(!modal.querySelector('.is-zoomed'));assert(!preview.querySelector('.is-zoomed'));
 assert(preview.querySelector('[aria-label="放大图片"]'));
 const previous=preview.querySelector('[aria-label="上一张商品图片"]');
 const next=preview.querySelector('[aria-label="下一张商品图片"]');
 assert(previous.disabled);assert(!next.disabled);next.click();
 assert.equal(preview.querySelector('img').alt,'风衣');
 preview.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
 assert.equal(preview.querySelector('img').alt,'shoes');assert(next.disabled);
 preview.querySelector('img').click();assert(preview.querySelector('.is-zoomed'));
 preview.querySelector('[aria-label="还原图片大小"]').click();assert(!preview.querySelector('.is-zoomed'));
 const stage=preview.querySelector('.preview-stage');
 for(const [type,property,x] of [['touchstart','touches',20],['touchend','changedTouches',160]]){
  const event=new w.Event(type);Object.defineProperty(event,property,{value:[{clientX:x,clientY:30}]});stage.dispatchEvent(event);
 }
 assert.equal(preview.querySelector('img').alt,'风衣');
 preview.querySelector('[aria-label="关闭图片预览"]').click();assert(!preview.open);assert.equal(w.document.activeElement,trigger);
 modal.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));assert.equal(modal.querySelector('.outfit-item-info h3').textContent,'风衣');
 modal.querySelector('.outfit-original').click();assert.equal(preview.querySelector('img').alt,'风衣');
 assert.match(preview.querySelector('.preview-caption').textContent,/2 \/ 3/);
 modal.close();assert(!w.document.querySelector('.outfit-detail'));assert.equal(w.document.activeElement,root.querySelector('.outfit-expand'));
 assert(!preview.open);
 dom.window.close();
});
test('missing/unsafe images and fallback failures are explicit; text cannot inject HTML',async()=>{
 const {dom,w,board}=setup();
 const root=board.create({items:[item('top',{title:'<img src=x onerror=alert(1)>',cutout_image:'javascript:alert(1)',original_image:''})]});
 w.document.body.append(root);await ready();
 root.querySelector('.outfit-expand').click();assert(!w.document.querySelector('.outfit-item-info img'));assert(!w.document.querySelector('.outfit-original img'));assert.match(w.document.querySelector('dialog').textContent,/暂无图片/);w.document.querySelector('dialog').close();
 const second=board.create({items:[item('top')]});w.document.body.append(second);await ready();second.querySelector('.outfit-expand').click();const img=w.document.querySelector('.outfit-thumbnail img');img.onerror();assert.match(img.src,/original/);img.onerror();assert.match(w.document.querySelector('dialog').textContent,/图片暂不可用/);
 dom.window.close();
});
test('closing on account clear removes all item details and does not leak another outfit',async()=>{
 const {dom,w,board}=setup();const root=board.create({title:'一套',items:[item('dress')]});w.document.body.append(root);await ready();root.querySelector('.outfit-expand').click();
 w.dispatchEvent(new w.CustomEvent('companion-profile-change',{detail:null}));assert(!w.document.querySelector('dialog'));
 const next=board.create({title:'下一套',items:[item('bottom',{title:'长裤'})]});w.document.body.append(next);await ready();next.querySelector('.outfit-expand').click();
 assert.match(w.document.querySelector('dialog h2').textContent,/下一套/);assert.equal(w.document.querySelectorAll('dialog .outfit-thumbnail').length,1);dom.window.close();
});
test('half-processed clothes never render; display and download share the final saved image',async()=>{
 const {dom,w,board}=setup();let complete,downloaded;
 w.OutfitImages={get:()=>new Promise(resolve=>complete=resolve),download:async result=>{downloaded=result.image_url}};
 const root=board.create({items:[item('top'),item('outer')]},{conversationId:'owned',version:1,index:0});w.document.body.append(root);await ready();
 assert(root.querySelector('.outfit-placeholder'));assert(!root.querySelector('img'));assert(!root.querySelector('.outfit-piece'));assert(!root.textContent.includes('去背景'));
 complete({image_url:'https://photos.invalid/saved-oss.png'});await ready();
 assert.equal(root.querySelector('.outfit-final-image').src,'https://photos.invalid/saved-oss.png');
 root.querySelector('.outfit-board-actions .subtle').click();await ready();assert.equal(downloaded,'https://photos.invalid/saved-oss.png');
 assert.equal(root.querySelectorAll('.outfit-hotspot').length,2);dom.window.close();
});
