const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('stylist/static/wardrobe-journey.js','utf8');
const flush=async()=>{for(let i=0;i<6;i++)await new Promise(resolve=>setImmediate(resolve));};
function setup(api,options={}){
 const dom=new JSDOM('<html><body><button id="opener">入口</button><div id="feed"></div></body></html>',{runScripts:'outside-only',url:'https://local.test'}),w=dom.window;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
 w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
 w.URL.createObjectURL=()=> 'blob:local-preview';w.URL.revokeObjectURL=()=>{};
 w.eval(fs.readFileSync('stylist/static/companion-loading.js','utf8'));
 w.eval(source);const notices=[];w.WardrobeJourney.configure({api,notify:text=>notices.push(text),getConversation:()=> 'current',...options});w.WardrobeJourney.setOwner('1');
 return {dom,w,notices,close:()=>dom.window.close()};
}
const byText=(w,text)=>[...w.document.querySelectorAll('button')].find(b=>b.textContent===text);
test('media history uses kind-specific letters and opens only the original read-only record',async()=>{
 const calls=[];const actions=[{action_id:'med_clothes',kind:'garment',status:'completed',result:{}},{action_id:'med_photo',kind:'person',status:'completed',result:{}},{action_id:'med_portrait',kind:'generation',status:'completed',result:{result_image_url:'https://example.test/portrait.png',can_confirm:true,task_id:'portrait-task'}}];
 const t=setup(async(path,options)=>{calls.push([path,options]);return path.endsWith('/media')?actions:path.endsWith('/images')?[]:actions[2];});
 await t.w.WardrobeJourney.history();const cards=t.w.document.querySelectorAll('.journey-media-letter');assert.equal(cards.length,3);
 assert.equal(t.w.document.querySelector('.journey-body').textContent.includes('查看处理结果'),false);assert.equal(t.w.document.querySelector('.journey-body').textContent.includes('已完成'),false);
 assert.ok(t.w.document.querySelector('[aria-label="打开衣橱来信"]'));assert.ok(t.w.document.querySelector('[aria-label="读读照片回信"]'));
 t.w.document.querySelector('[aria-label="看看新的模样"]').click();await flush();assert.match(t.w.document.querySelector('.journey-body .journey-image img').src,/portrait.png/);
 assert(byText(t.w,'确认使用这个试穿形象'));assert.equal(calls.filter(([,o])=>o?.method==='POST').length,0);assert.equal(calls.at(-1)[0],'/stylist-api/media/med_portrait');t.close();
});
test('media letters distinguish missing images, unconfirmed outcomes and strict refund evidence',async()=>{
 const actions=[{action_id:'med_missing',kind:'generation',status:'completed',result:{}},{action_id:'med_unknown',kind:'generation',status:'unknown',result:{}},{action_id:'med_failed',kind:'generation',status:'failed',result:{refunded:'true'}},{action_id:'med_refunded',kind:'generation',status:'failed',result:{refunded:true}}];
 const t=setup(async path=>path.endsWith('/media')?actions:[]);await t.w.WardrobeJourney.history();const cards=[...t.w.document.querySelectorAll('.journey-media-letter')];
 assert.equal(cards[0].querySelector('button').getAttribute('aria-label'),'打开形象来信');assert.doesNotMatch(cards[0].textContent,/新的模样/);
 assert.match(cards[1].textContent,/没有确切结果/);assert.doesNotMatch(cards[2].textContent,/积分已退回/);assert.match(cards[3].textContent,/积分已退回/);t.close();
});
test('late media-letter reads cannot replace a newer upload panel',async()=>{
 let done;const t=setup(async path=>path.endsWith('/media')?[{action_id:'med_late_letter',kind:'generation',status:'completed',result:{}}]:path.endsWith('/images')?[]:new Promise(r=>done=r));
 await t.w.WardrobeJourney.history();t.w.document.querySelector('[aria-label="打开形象来信"]').click();await flush();t.w.WardrobeJourney.upload('person');done({action_id:'med_late_letter',kind:'generation',status:'completed',result:{result_image_url:'https://example.test/old.png'}});await flush();
 assert.equal(t.w.document.querySelector('#journey-title').textContent,'创建我的试穿形象');assert(t.w.document.querySelector('#journey-photo-input'));t.close();
});
test('shared gallery loading ends on failure rather than continuing to animate indefinitely',async()=>{
 let reject;const t=setup(()=>new Promise((resolve,fail)=>reject=fail));const reading=t.w.WardrobeJourney.twins();
 assert(t.w.document.querySelector('.journey-body .companion-loading'));reject(Error('形象服务暂时不可用'));
 await assert.rejects(reading,/形象服务暂时不可用/);assert.equal(t.w.document.querySelector('.journey-body .companion-loader'),null);t.close();
});
test('a late loader cleanup cannot remove a newer flow after the old read fails',async()=>{
 let reject;const t=setup(()=>new Promise((resolve,fail)=>reject=fail));const reading=t.w.WardrobeJourney.twins();
 t.w.WardrobeJourney.upload('person');reject(Error('旧查询失败'));await assert.rejects(reading,/旧查询失败/);
 assert.equal(t.w.document.querySelector('#journey-title').textContent,'创建我的试穿形象');assert(t.w.document.querySelector('#journey-photo-input'));t.close();
});
test('completed try-on offers one explicit regeneration action and waits for it before re-enabling',async()=>{
 let finish;const received=[];const action={action_id:'img_regenerate',conversation_id:'current',version:2,look_index:1,status:'completed',result:{result_image_url:'https://example.test/result.png'}};
 const t=setup(async()=>[action],{onRegenerate:value=>{received.push(value);return new Promise(resolve=>finish=resolve);}});
 await t.w.WardrobeJourney.restore('current');const b=byText(t.w,'重新生成穿搭');assert(b);
 assert.equal(byText(t.w,'继续调整这套搭配'),undefined);b.click();b.click();assert.equal(received.length,1);
 assert.equal(received[0].look_index,1);assert.equal(received[0].version,2);assert.equal(b.disabled,true);
 finish();await flush();assert.equal(b.disabled,false);t.close();
});
test('a detached result from a previous account cannot invoke regeneration',async()=>{
 let called=0;const t=setup(async()=>[{action_id:'img_old',status:'completed',result:{result_image_url:'https://example.test/old.png'}}],{onRegenerate:()=>called++});
 await t.w.WardrobeJourney.restore('current');const b=byText(t.w,'重新生成穿搭');
 t.w.WardrobeJourney.setOwner('2');b.click();await flush();assert.equal(called,0);t.close();
});
test('refunded failure explains there is no image and never offers a dead result query',async()=>{
 const calls=[],received=[];const action={action_id:'img_refunded',conversation_id:'current',version:2,status:'failed',result:{charged:true,refunded:true}};
 const t=setup(async(path,options)=>{calls.push([path,options]);return [action];},{onRegenerate:a=>received.push(a)});
 await t.w.WardrobeJourney.restore('current');const card=t.w.document.querySelector('.journey-result');
 assert.match(card.textContent,/没能生成图片/);assert.match(card.textContent,/积分已退回/);
 assert.equal(card.querySelector('.journey-letter-photo'),null);assert.equal(card.querySelector('.journey-state'),null);
 for(const text of ['查看这次结果','看看试穿进展','核对积分进展'])assert.equal(byText(t.w,text),undefined);
 byText(t.w,'重新生成穿搭').click();await flush();assert.equal(received.length,1);assert.equal(received[0].status,'failed');assert.equal(calls.length,1);t.close();
});
test('refund reconciliation reads the original task and removes the query once refund is confirmed',async()=>{
 const calls=[];const action={action_id:'img_refund_pending',status:'failed',result:{charged:true,refunded:false}};
 const t=setup(async(path,options)=>{calls.push([path,options]);return path.includes('?')?[action]:{...action,result:{charged:true,refunded:true}};});
 await t.w.WardrobeJourney.restore('current');assert.match(t.w.document.querySelector('.journey-result').textContent,/是否退回还需要核对/);
 byText(t.w,'核对积分进展').focus();byText(t.w,'核对积分进展').click();await flush();
 assert.match(t.w.document.querySelector('.journey-result').textContent,/积分已退回/);assert.equal(byText(t.w,'核对积分进展'),undefined);
 assert.match(t.notices.at(-1),/积分已退回/);assert.equal(t.w.document.activeElement.className,'journey-letter-lead');assert.equal(calls.length,2);assert.ok(calls.every(([,o])=>!o?.method));t.close();
});
test('refund evidence is strict and an unchanged query gives explicit feedback',async()=>{
 const action={action_id:'img_uncertain_refund',status:'failed',result:{refunded:'true'}};
 const t=setup(async path=>path.includes('?')?[action]:action);await t.w.WardrobeJourney.restore('current');
 assert.doesNotMatch(t.w.document.querySelector('.journey-result').textContent,/积分已退回/);
 byText(t.w,'核对积分进展').click();await flush();assert.match(t.notices.at(-1),/是否退回还需要核对/);t.close();
});
test('unknown progress reads are explicit and do not create a blank result dialog',async()=>{
 const action={action_id:'img_unknown',status:'unknown',result:{}};
 const t=setup(async path=>path.includes('?')?[action]:action);await t.w.WardrobeJourney.restore('current');
 byText(t.w,'看看试穿进展').click();await flush();assert.match(t.notices.at(-1),/暂时还没有确切结果/);
 assert.equal(t.w.document.querySelector('dialog').open,false);assert.equal(t.w.document.querySelector('.journey-letter-photo'),null);t.close();
});
test('failed history uses the same refund copy and does not suggest a nonexistent image',async()=>{
 const calls=[];const t=setup(async(path,options)=>{calls.push([path,options]);return path.endsWith('/media')?[]:[{action_id:'img_history_failed',status:'failed',result:{refunded:true}}];});
 await t.w.WardrobeJourney.history();const record=t.w.document.querySelector('.journey-record');assert.match(record.textContent,/积分已退回/);
 assert.equal(record.querySelector('.journey-letter-photo'),null);assert.equal(record.querySelector('button'),null);assert.equal(calls.length,2);t.close();
});
test('a confirmed no-charge failure needs no refund lookup',async()=>{
 const t=setup(async()=>[{action_id:'img_uncharged',status:'failed',result:{charged:false}}]);await t.w.WardrobeJourney.restore('current');
 assert.match(t.w.document.querySelector('.journey-result').textContent,/没有扣积分/);assert.equal(byText(t.w,'核对积分进展'),undefined);t.close();
});
test('late manual checks cannot attach an old image to another account',async()=>{
 let done;const t=setup(async path=>path.includes('?')?[{action_id:'img_late_read',status:'unknown'}]:new Promise(resolve=>done=resolve));
 await t.w.WardrobeJourney.restore('current');byText(t.w,'看看试穿进展').click();await flush();t.w.WardrobeJourney.setOwner('2');
 done({action_id:'img_late_read',status:'completed',result:{result_image:'https://example.test/old-owner.png'}});await flush();
 assert.equal(t.w.document.querySelectorAll('.journey-result').length,0);assert.deepEqual(t.notices,[]);t.close();
});
test('a detached query button cannot read an old task as the new account',async()=>{
 const calls=[];const t=setup(async(path,options)=>{calls.push([path,options]);return [{action_id:'img_detached_query',status:'unknown'}];});
 await t.w.WardrobeJourney.restore('current');const query=byText(t.w,'看看试穿进展');t.w.WardrobeJourney.setOwner('2');query.click();await flush();
 assert.equal(calls.length,1);assert.deepEqual(t.notices,[]);t.close();
});
test('an older manual response cannot replace a result that finished while the read was pending',async()=>{
 let done,reads=0;const processing={action_id:'img_read_race',status:'processing',result:{}};
 const t=setup(async path=>path.includes('?')?[processing]:++reads===1?new Promise(resolve=>done=resolve):{...processing,status:'completed',result:{result_image:'https://example.test/winner.png'}});
 const tick=mockPolling(t.w);await t.w.WardrobeJourney.restore('current');byText(t.w,'看看试穿进展').click();await flush();await tick();
 done({...processing,status:'unknown'});await flush();assert.equal(t.w.document.querySelector('.journey-result').dataset.status,'completed');
 assert.match(t.w.document.querySelector('.journey-letter-photo img').src,/winner.png/);t.close();
});
test('a valid legacy image is displayed even when the newer image field is unusable',async()=>{
 const t=setup(async()=>[{action_id:'img_legacy_display',status:'completed',result:{result_image_url:'data:invalid',result_image:'https://example.test/legacy.png'}}]);
 await t.w.WardrobeJourney.restore('current');assert.match(t.w.document.querySelector('.journey-letter-photo img').src,/legacy.png/);
 assert.equal(t.w.document.querySelector('.journey-result').dataset.status,'completed');t.close();
});
async function selectFile(w){
 const file=new w.File([new Uint8Array([137,80,78,71,13,10,26,10,0,0,0,0,0,0,0,0])],'shirt.png',{type:'image/png'});
 const input=w.document.querySelector('input[type=file]');Object.defineProperty(input,'files',{value:[file],configurable:true});input.dispatchEvent(new w.Event('change'));await flush();
}
for(const kind of ['person','garment'])test(`${kind} upload uses the JPEG signature when a file is named PNG without changing its bytes`,async()=>{
 const requests=[];const t=setup(async(path,options)=>{requests.push(JSON.parse(options.body));throw Error('synthetic stop');});
 t.w.WardrobeJourney.upload(kind);
 const bytes=Uint8Array.from([255,216,255,224,0,16,74,70,73,70,0,1,1,0,0,1]);
 const file=new t.w.File([bytes],'photo.png',{type:'image/png'});
 const input=t.w.document.querySelector('input[type=file]');Object.defineProperty(input,'files',{value:[file],configurable:true});input.dispatchEvent(new t.w.Event('change'));await flush();
 assert.equal(requests.length,0);
 byText(t.w,'确认上传').click();await flush();
 assert.equal(requests.length,1);assert.equal(requests[0].kind,kind);
 assert.equal(requests[0].image_data,'data:image/jpeg;base64,'+Buffer.from(bytes).toString('base64'));
 t.close();
});
test('a supported image without a browser MIME type can be submitted',async()=>{
 const requests=[];const t=setup(async(path,options)=>{requests.push(JSON.parse(options.body));throw Error('synthetic stop');});
 t.w.WardrobeJourney.upload('person');
 const bytes=Uint8Array.from([82,73,70,70,16,0,0,0,87,69,66,80,86,80,56,32]);
 const file=new t.w.File([bytes],'photo',{type:''});
 const input=t.w.document.querySelector('input[type=file]');Object.defineProperty(input,'files',{value:[file],configurable:true});input.dispatchEvent(new t.w.Event('change'));await flush();
 byText(t.w,'确认上传').click();await flush();
 assert.equal(requests.length,1);assert.equal(requests[0].image_data,'data:image/webp;base64,'+Buffer.from(bytes).toString('base64'));t.close();
});
test('non-image content named PNG stays blocked before any upload',async()=>{
 let calls=0;const t=setup(async()=>{calls++;});t.w.WardrobeJourney.upload('person');
 const file=new t.w.File(['this is not an image file'],'photo.png',{type:'image/png'});
 const input=t.w.document.querySelector('input[type=file]');Object.defineProperty(input,'files',{value:[file],configurable:true});input.dispatchEvent(new t.w.Event('change'));await flush();
 assert.equal(byText(t.w,'确认上传').disabled,true);assert.equal(calls,0);
 assert.match(t.notices.join(''),/不是可识别的/);t.close();
});
test('photo remains local until explicit upload; cancel never sends or charges',async()=>{
 const calls=[];const t=setup(async(...args)=>{calls.push(args);return {action_id:'med_a',kind:'garment',status:'completed',result:{user_product_id:17,class_name:'上衣',result_image_url:'https://example.test/cutout.png'}};});
 t.w.WardrobeJourney.upload();await selectFile(t.w);assert.equal(calls.length,0);assert.match(t.w.document.querySelector('.journey-upload-preview img').src,/^blob:/);
 byText(t.w,'关闭 ×').click();assert.equal(calls.length,0);
 t.w.WardrobeJourney.upload();await selectFile(t.w);byText(t.w,'确认上传').click();await flush();
 assert.equal(calls.length,1);assert.equal(JSON.parse(calls[0][1].body).confirmed,true);assert.ok(byText(t.w,'用这件搭一套'));t.close();
});
test('an upload cannot be double-submitted, and closing does not reopen on late response',async()=>{
 let done;let calls=0;const t=setup(()=>{calls++;return new Promise(resolve=>done=resolve);});
 t.w.WardrobeJourney.upload();await selectFile(t.w);const b=byText(t.w,'确认上传');b.click();b.click();assert.equal(calls,1);
 byText(t.w,'关闭 ×').click();done({action_id:'med_a',kind:'garment',status:'completed',result:{user_product_id:1}});await flush();
 assert.equal(t.w.document.querySelector('dialog').open,false);t.close();
});
test('switching accounts discards a late upload response and clears preview',async()=>{
 let done;const t=setup(()=>new Promise(resolve=>done=resolve));t.w.WardrobeJourney.upload();await selectFile(t.w);byText(t.w,'确认上传').click();
 t.w.WardrobeJourney.setOwner('2');done({action_id:'med_a',kind:'garment',status:'completed',result:{user_product_id:17}});await flush();
 assert.equal(t.w.document.querySelector('dialog').open,false);assert.equal(t.w.document.querySelector('.journey-body').textContent,'');assert.deepEqual(t.notices,[]);t.close();
});
test('a late upload cannot replace a newly opened person-photo flow for the same account',async()=>{
 let done;const t=setup(()=>new Promise(resolve=>done=resolve));t.w.WardrobeJourney.upload();await selectFile(t.w);byText(t.w,'确认上传').click();
 byText(t.w,'关闭 ×').click();t.w.WardrobeJourney.upload('person');
 done({action_id:'med_a',kind:'garment',status:'completed',result:{user_product_id:17}});await flush();
 assert.equal(t.w.document.querySelector('#journey-title').textContent,'创建我的试穿形象');assert.ok(byText(t.w,'确认上传'));t.close();
});
test('portrait selection is a draft; only confirmation changes default and no generation is charged',async()=>{
 const calls=[];const overview={default_twin_key:'base-a',default_confirmed:true,selection_version:3,available_points:80,system_twins:[{twin_key:'base-a',name:'基础形象A',image_url:'https://example.test/a.png'},{twin_key:'base-b',name:'基础形象B',image_url:'https://example.test/b.png'}]};
 const t=setup(async(path,options)=>{calls.push([path,options]);return overview;});await t.w.WardrobeJourney.twins();
 assert.equal(t.w.document.querySelector('.journey-steps').hidden,true);
 const tiles=t.w.document.querySelectorAll('.journey-portrait');tiles[1].click();await flush();assert.ok(calls.every(([,options])=>!options?.method||options.method==='GET'),'draft selection must not write; profile option reads are allowed');assert.equal(tiles[1].getAttribute('aria-pressed'),'true');
 byText(t.w,'确认使用所选形象').click();await flush();const writes=calls.filter(([,o])=>o?.method==='POST');assert.equal(writes.length,1);assert.equal(JSON.parse(writes[0][1].body).twin_key,'base-b');t.close();
});
test('person generation has its own quote, and dismissing it sends only cancellation',async()=>{
 const calls=[];const t=setup(async(path,options)=>{
  calls.push([path,options]);
  if(path.endsWith('/uploads'))return {action_id:'med_photo',kind:'person',status:'completed',result:{check_id:'1',allowed_hat_actions:['none'],generation_cost_points:20}};
  if(path.endsWith('/generation-quote'))return {action_id:'med_quote',kind:'generation',status:'quoted',points_cost:20};
  return {status:'cancelled'};
 });
 t.w.WardrobeJourney.upload('person');await selectFile(t.w);byText(t.w,'确认上传').click();await flush();await flush();
 assert.equal(t.w.document.querySelector('.journey-steps').hidden,false);
 assert.match(t.w.document.querySelector('.journey-footer').textContent,/确认消耗 20 积分并生成/);assert.match(t.w.document.querySelector('.journey-body').textContent,/另行确认积分/);
 assert.equal(calls.filter(([p])=>p.endsWith('/confirm')).length,0);byText(t.w,'关闭 ×').click();await flush();
 assert.equal(calls.filter(([p,o])=>p.endsWith('/confirm')&&JSON.parse(o.body).confirmed).length,0);
 assert.equal(calls.filter(([p,o])=>p.endsWith('/confirm')&&!JSON.parse(o.body).confirmed).length,1);t.close();
});
test('try-on result is rendered into conversation; unknown state only offers a read, never replay',async()=>{
 const calls=[];const t=setup(async(path,options)=>{
  calls.push([path,options]);
  if(path==='/stylist-api/twins')return {default_confirmed:true,default_twin_key:'base'};
  if(path.endsWith('/quote'))return {action_id:'img_abc',title:'今日搭配',points_cost:8,item_count:1,notices:[],portrait:{}};
  if(options?.method==='POST')return {action_id:'img_abc',title:'今日搭配',status:'unknown',result:{}};
  return {action_id:'img_abc',title:'今日搭配',status:'completed',result:{result_image_url:'https://example.test/tryon.png'}};
 });
 await t.w.WardrobeJourney.tryon({conversation_id:'current',version:1,look_index:0});assert.equal(t.w.document.querySelector('.journey-steps').hidden,true);byText(t.w,'确认消耗 8 积分并试穿').click();await flush();
 assert.ok(t.w.document.querySelector('#feed [data-image-action="img_abc"]'));byText(t.w,'关闭 ×').click();byText(t.w,'看看试穿进展').click();await flush();
 assert.equal(calls.filter(([,o])=>o?.method==='POST').length,2);assert.match(t.w.document.querySelector('#feed .journey-letter-photo img').src,/tryon.png$/);t.close();
});
test('a delayed history load cannot pollute a different conversation',async()=>{
 const t=setup(async()=>[{action_id:'img_old',status:'completed',result:{result_image_url:'https://example.test/old.png'}}]);await t.w.WardrobeJourney.restore('other');
 assert.equal(t.w.document.querySelectorAll('.journey-result').length,0);await t.w.WardrobeJourney.restore('current');assert.equal(t.w.document.querySelectorAll('.journey-result').length,1);t.close();
});
test('an upload failure preserves the preview and permits a different file without automatic retry',async()=>{
 let writes=0;const t=setup(async()=>{writes++;throw Error('上传暂时失败');});
 t.w.WardrobeJourney.upload();await selectFile(t.w);byText(t.w,'确认上传').click();await flush();
 assert.equal(writes,1);assert.equal(t.w.document.querySelector('input[type=file]').disabled,false);
 assert.ok(t.w.document.querySelector('.journey-upload-preview img'));
 await selectFile(t.w);assert.equal(writes,1);assert.equal(byText(t.w,'确认上传').disabled,false);t.close();
});
test('changing accounts clears the docked fee action and companion scene',async()=>{
 const t=setup(async p=>p.endsWith('/quote')?{action_id:'img_q',title:'搭配',points_cost:8,item_count:1,portrait:{}}:{default_confirmed:true,default_twin_key:'base'});
 await t.w.WardrobeJourney.tryon({conversation_id:'current',version:1,look_index:0});
 assert.match(t.w.document.querySelector('.journey-footer').textContent,/8 积分/);
 t.w.WardrobeJourney.setOwner('2');assert.equal(t.w.document.querySelector('.journey-footer').textContent,'');assert.equal(t.w.document.querySelector('.journey-scene').textContent,'');t.close();
});
test('explicit clothing invitation shows upload steps; only a click opens the local picker',async()=>{
 let calls=0;const t=setup(async()=>{calls++;});
 t.w.WardrobeJourney.offer({upload_intent:'garment',upload_suggestion:true},t.w.document.getElementById('feed'));
 assert.equal(t.w.document.querySelectorAll('.journey-card-steps li').length,3);
 assert.equal(t.w.document.querySelector('dialog').open,false);assert.equal(calls,0);
 byText(t.w,'好，选择衣物照片').click();assert.equal(t.w.document.querySelector('dialog').open,true);
 await selectFile(t.w);assert.equal(calls,0);assert.ok(byText(t.w,'确认上传'));t.close();
});
test('ambiguous photo card offers separate purposes without automatically opening or submitting',async()=>{
 let calls=0;const t=setup(async()=>{calls++;});t.w.WardrobeJourney.offer({upload_intent:'unspecified'},t.w.document.getElementById('feed'));
 assert.ok(byText(t.w,'上传衣物照片'));assert.ok(byText(t.w,'创建本人试穿形象'));
 assert.equal(t.w.document.querySelector('dialog').open,false);assert.equal(calls,0);
 byText(t.w,'上传衣物照片').click();assert.equal(calls,0);assert.ok(byText(t.w,'确认上传'));t.close();
});
test('ordinary reply without upload invitation adds no card',()=>{
 const t=setup(async()=>{});t.w.WardrobeJourney.offer({upload_intent:null,upload_suggestion:false},t.w.document.getElementById('feed'));
 assert.equal(t.w.document.querySelectorAll('.journey-invite').length,0);t.close();
});
test('old partial-outfit upload suggestions are ignored on historical rendering',()=>{
 let calls=0;const t=setup(async()=>{calls++;});const feed=t.w.document.getElementById('feed');
 for(const reply of [
  {upload_suggestion:true,upload_intent:null,delivery:'outfit',looks:[{items:[{product_id:'owned'}],wardrobe_complete:false}]},
  {upload_suggestion:true,delivery:'concept',looks:[]},
 ])t.w.WardrobeJourney.offer(reply,feed);
 assert.equal(feed.querySelectorAll('.journey-invite').length,0);
 assert.equal(t.w.document.querySelector('dialog').open,false);assert.equal(calls,0);t.close();
});
test('an explicit upload intent still shows its card without the legacy suggestion flag',()=>{
 let calls=0;const t=setup(async()=>{calls++;});
 t.w.WardrobeJourney.offer({upload_intent:'garment',upload_suggestion:false},t.w.document.getElementById('feed'));
 assert.ok(byText(t.w,'好，选择衣物照片'));assert.equal(calls,0);
 assert.equal(t.w.document.querySelector('dialog').open,false);t.close();
});
const galleryOverview={default_twin_key:'base-a',default_confirmed:true,selection_version:3,
 system_twins:[{twin_key:'base-a',name:'日常形象',image_url:'https://example.test/a.png'},
 {twin_key:'base-b',name:'清爽形象',image_url:'https://example.test/b.png'}]};
test('dialogue gallery selects a draft, then quotes the exact outfit without charging',async()=>{
 const calls=[];const ref={conversation_id:'current',version:2,look_index:1};
 const t=setup(async(path,options)=>{calls.push([path,options]);return path.endsWith('/quote')?{action_id:'img_q',points_cost:8,item_count:2,title:'第二套',portrait:{}}:galleryOverview;},
 {getContext:()=>({conversation_id:'current',version:2})});
 t.w.WardrobeJourney.offer({avatar_intent:'tryon',tryon_context:ref,tryon_title:'第二套'},t.w.document.getElementById('feed'));await flush();
 assert.equal(calls.length,1);t.w.document.querySelector('[data-twin-key="base-b"]').click();await flush();assert.equal(calls.length,1);
 byText(t.w,'确认形象，查看这次试穿积分').click();await flush();
 assert.equal(JSON.parse(calls.find(([p])=>p.endsWith('/default'))[1].body).twin_key,'base-b');
 assert.deepEqual(JSON.parse(calls.find(([p])=>p.endsWith('/quote'))[1].body),ref);
 assert.equal(calls.filter(([p])=>p.endsWith('/confirm')).length,0);assert.ok(byText(t.w,'确认消耗 8 积分并试穿'));t.close();
});
test('stale dialogue gallery cannot change a default portrait or submit generation',async()=>{
 const calls=[];let version=1;const t=setup(async(...a)=>{calls.push(a);return galleryOverview;},{getContext:()=>({conversation_id:'current',version})});
 t.w.WardrobeJourney.offer({avatar_intent:'tryon',tryon_context:{conversation_id:'current',version:1,look_index:0}},t.w.document.getElementById('feed'));await flush();version=2;
 byText(t.w,'确认形象，查看这次试穿积分').click();await flush();assert.equal(calls.length,1);assert.match(t.notices[0],/已更新/);t.close();
});
test('avatar upload invitation is distinct from adding garments and requires a click',async()=>{
 let calls=0;const t=setup(async()=>{calls++;return galleryOverview;});
 t.w.WardrobeJourney.offer({avatar_intent:'upload'},t.w.document.getElementById('feed'));assert.equal(calls,0);
 assert.equal(t.w.document.querySelector('dialog').open,false);byText(t.w,'选择形象照片').click();await flush();
 assert.equal(calls,1);assert.ok(byText(t.w,'确认上传'));assert.equal(t.w.document.querySelectorAll('.journey-card-steps li').length,3);t.close();
});
test('an unloaded gallery ignores late data after account change',async()=>{
 let done;const t=setup(()=>new Promise(resolve=>done=resolve));
 t.w.WardrobeJourney.offer({avatar_intent:'view'},t.w.document.getElementById('feed'));t.w.WardrobeJourney.setOwner('2');done(galleryOverview);await flush();
 assert.equal(t.w.document.querySelectorAll('.journey-avatar-card').length,0);t.close();
});
function mockPolling(w){
 let next=0;const pending=new Map();w.setTimeout=fn=>{pending.set(++next,fn);return next;};w.clearTimeout=id=>pending.delete(id);
 return async()=>{const item=pending.entries().next().value;assert.ok(item,'Expected a read-only polling timer');pending.delete(item[0]);await item[1]();await flush();};
}
test('restoring a processing task resumes only reads and later displays its result',async()=>{
 const calls=[];const t=setup(async(path,options)=>{
  calls.push([path,options]);
  if(path.includes('?conversation_id='))return [{action_id:'img_restore',conversation_id:'current',status:'processing',result:{}}];
  return {action_id:'img_restore',conversation_id:'current',status:'completed',result:{result_image_url:'https://example.test/restored.png'}};
 });const tick=mockPolling(t.w);await t.w.WardrobeJourney.restore('current');
 assert.ok(t.w.document.querySelector('#feed [role=progressbar]'));await tick();
 assert.match(t.w.document.querySelector('#feed .journey-letter-photo img').src,/restored.png/);
 assert.equal(calls.length,2);assert.ok(calls.every(([,options])=>!options?.method||options.method==='GET'));t.close();
});
test('processing is polled read-only after closing; completion shows one notification and image',async()=>{
 const calls=[];const t=setup(async(path,options)=>{
  calls.push([path,options]);if(path==='/stylist-api/twins')return galleryOverview;
  if(path.endsWith('/quote'))return {action_id:'img_watch',points_cost:8,item_count:1,title:'通勤',portrait:{}};
  if(options?.method==='POST')return {action_id:'img_watch',status:'processing',result:{}};
  return {action_id:'img_watch',status:'completed',result:{result_image_url:'https://example.test/result.png'}};
 });const tick=mockPolling(t.w);
 await t.w.WardrobeJourney.tryon({conversation_id:'current',version:1,look_index:0});byText(t.w,'确认消耗 8 积分并试穿').click();await flush();
 assert.ok(t.w.document.querySelector('#feed [role=progressbar]'));assert.equal(t.w.document.querySelector('#feed [role=progressbar]').hasAttribute('aria-valuenow'),false);
 byText(t.w,'关闭 ×').click();await tick();assert.equal(t.w.document.querySelector('dialog').open,false);
 assert.match(t.w.document.querySelector('#feed .journey-letter-photo img').src,/result.png/);assert.equal(t.notices.filter(n=>n.includes('试穿照到了')).length,1);
 assert.equal(calls.filter(([,o])=>o?.method==='POST').length,2);t.close();
});
test('completion replaces the visible progress panel and uses provider progress without invention',async()=>{
 const t=setup(async(path,options)=>{
  if(path==='/stylist-api/twins')return galleryOverview;
  if(path.endsWith('/quote'))return {action_id:'img_progress',points_cost:8,item_count:1,title:'搭配',portrait:{}};
  if(options?.method==='POST')return {action_id:'img_progress',status:'processing',result:{progress:32}};
  return {action_id:'img_progress',status:'completed',result:{result_image_url:'https://example.test/completed.png'}};
 });const tick=mockPolling(t.w);await t.w.WardrobeJourney.tryon({conversation_id:'current',version:1,look_index:0});byText(t.w,'确认消耗 8 积分并试穿').click();await flush();
 assert.equal(t.w.document.querySelector('.journey-body [role=progressbar]').getAttribute('aria-valuenow'),'32');await tick();
 assert.match(t.w.document.querySelector('.journey-body').textContent,/这一身，想先给你看看/ );assert.ok(t.w.document.querySelector('.journey-body img'));t.close();
});
test('pending progress read cannot display a result or notification for a new account',async()=>{
 let done;const t=setup(async(path,options)=>{
  if(path==='/stylist-api/twins')return galleryOverview;
  if(path.endsWith('/quote'))return {action_id:'img_old_user',points_cost:8,item_count:1,title:'搭配',portrait:{}};
  if(options?.method==='POST')return {action_id:'img_old_user',status:'processing',result:{}};
  return new Promise(resolve=>done=resolve);
 });const tick=mockPolling(t.w);await t.w.WardrobeJourney.tryon({conversation_id:'current',version:1,look_index:0});byText(t.w,'确认消耗 8 积分并试穿').click();await flush();
 const reading=tick();await flush();t.w.WardrobeJourney.setOwner('2');done({action_id:'img_old_user',status:'completed',result:{result_image_url:'https://example.test/foreign.png'}});await reading;
 assert.equal(t.w.document.querySelectorAll('#feed img').length,0);assert.deepEqual(t.notices,[]);t.close();
});
test('completion without a usable result image is not announced as successful',async()=>{
 const t=setup(async path=>path==='/stylist-api/twins'?galleryOverview:path.endsWith('/quote')?{action_id:'img_missing',points_cost:8,item_count:1,title:'搭配',portrait:{}}:{action_id:'img_missing',status:'completed',result:{}});
 mockPolling(t.w);await t.w.WardrobeJourney.tryon({conversation_id:'current',version:1,look_index:0});byText(t.w,'确认消耗 8 积分并试穿').click();await flush();
 assert.match(t.w.document.querySelector('.journey-body').textContent,/这次的试穿，还需要确认/);
 assert.equal(t.notices.filter(n=>n.includes('试穿照到了')).length,0);t.close();
});

test('history merges uploads, avatars and try-ons by creation time rather than kind or update time',async()=>{
 const uploads=[
  {action_id:'med_upload',kind:'garment',status:'completed',created_at:'2026-11-03 02:00:00',result:{}},
  {action_id:'med_avatar',kind:'generation',status:'cancelled',created_at:'2026-11-03T09:00:00+08:00',result:{}},
  {action_id:'med_photo',kind:'person',status:'completed',created_at:'2026-11-03T00:00:00+00',result:{}},
 ];
 const images=[
  {action_id:'img_new',title:'最新试穿',status:'processing',created_at:'2026-11-03T03:00:00Z',result:{}},
  {action_id:'img_old',title:'较早试穿',status:'failed',created_at:'2026-11-02T23:00:00Z',updated_at:'2026-11-04T00:00:00Z',result:{refunded:true}},
 ];
 const t=setup(async path=>path.endsWith('/media')?uploads:images);await t.w.WardrobeJourney.history();
 const order=[...t.w.document.querySelectorAll('.journey-body>.journey-record')].map(c=>c.dataset.mediaAction||c.dataset.imageAction);
 assert.deepEqual(order,['img_new','med_upload','med_avatar','med_photo','img_old']);t.close();
});
test('history preserves stable ties and places legacy undated records last',async()=>{
 const uploads=[{action_id:'med_unknown',kind:'person',status:'completed',result:{}},
  {action_id:'med_tie',kind:'garment',status:'completed',created_at:'2026-11-03 02:00:00',result:{}}];
 const images=[{action_id:'img_tie',status:'failed',created_at:'2026-11-03T02:00:00Z',result:{refunded:true}},
  {action_id:'img_invalid',status:'failed',created_at:'invalid',result:{refunded:true}}];
 const t=setup(async path=>path.endsWith('/media')?uploads:images);await t.w.WardrobeJourney.history();
 assert.deepEqual([...t.w.document.querySelectorAll('.journey-body>.journey-record')].map(c=>c.dataset.mediaAction||c.dataset.imageAction),['med_tie','img_tie','med_unknown','img_invalid']);t.close();
});

test('history filters keep each category descending, restore all records, and never refetch or write',async()=>{
 const calls=[];const uploads=[
  {action_id:'med_old',kind:'garment',status:'completed',created_at:'2026-11-01T01:00:00Z',result:{}},
  {action_id:'med_new',kind:'garment',status:'completed',created_at:'2026-11-03T01:00:00Z',result:{}},
  {action_id:'med_avatar',kind:'generation',status:'cancelled',created_at:'2026-11-02T01:00:00Z',result:{}},
 ];const images=[{action_id:'img_latest',status:'failed',created_at:'2026-11-03T02:00:00Z',result:{refunded:true}}];
 const t=setup(async path=>{calls.push(path);return path.endsWith('/media')?uploads:images;});await t.w.WardrobeJourney.history();
 const shown=()=>[...t.w.document.querySelectorAll('.journey-body>.journey-record')].filter(c=>!c.hidden).map(c=>c.dataset.mediaAction||c.dataset.imageAction);
 assert.deepEqual(shown(),['img_latest','med_new','med_avatar','med_old']);
 for(const [kind,ids]of [['garment',['med_new','med_old']],['generation',['med_avatar']],['tryon',['img_latest']],['person',[]],['all',['img_latest','med_new','med_avatar','med_old']]]){
  t.w.document.querySelector('.journey-history-filters [data-kind="'+kind+'"]').click();await flush();assert.deepEqual(shown(),ids);
  assert.equal(t.w.document.querySelector('.journey-history-filters [aria-pressed=true]').dataset.kind,kind);
  assert.equal(t.w.document.querySelector('.journey-history-empty').hidden,ids.length>0);
 }
 assert.equal(calls.length,2);t.close();
});

test('each try-on confirm checks current funds before consuming the quote or submitting',async()=>{
 const calls=[],checks=[];let allowed=false;
 const t=setup(async(path,options)=>{calls.push([path,options]);if(path==='/stylist-api/twins')return{default_confirmed:true,default_twin_key:'base'};if(path.endsWith('/quote'))return{action_id:'img_funds',title:'示例',points_cost:8,item_count:1,notices:[],portrait:{}};return{action_id:'img_funds',status:'completed',result:{result_image_url:'https://example.test/result.png'}};});
 t.w.AppPayment={checkFunds:async(cost,scene)=>{checks.push([cost,scene]);return allowed;}};
 await t.w.WardrobeJourney.tryon({conversation_id:'current',version:1,look_index:0});
 byText(t.w,'确认消耗 8 积分并试穿').click();await flush();assert.equal(calls.filter(([p])=>p.endsWith('/confirm')).length,0);
 allowed=true;byText(t.w,'确认消耗 8 积分并试穿').click();await flush();assert.equal(calls.filter(([p])=>p.endsWith('/confirm')).length,1);assert.deepEqual(checks,[[8,'tryon'],[8,'tryon']]);t.close();
});

for(const kind of ['person','garment','generation'])test(`${kind} media waits poll every two seconds read-only until terminal status`,async()=>{
 let status='processing',reads=0;const calls=[],pending=new Map();let serial=0;
 const action=()=>({action_id:'med_auto',kind,status,result:{}});
 const t=setup(async(path,options)=>{calls.push([path,options]);if(path.endsWith('/media'))return [action()];if(path.endsWith('/images'))return [];reads++;return action();});
 t.w.setTimeout=(fn,delay)=>{assert.equal(delay,2000);pending.set(++serial,fn);return serial;};t.w.clearTimeout=id=>pending.delete(id);
 await t.w.WardrobeJourney.history();t.w.document.querySelector('.journey-record-open').click();await flush();
 assert.equal(byText(t.w,'查看当前处理结果'),undefined);
 for(let i=0;i<32;i++){assert.equal(pending.size,1);const [id,fn]=pending.entries().next().value;pending.delete(id);await fn();}
 status='completed';const [id,fn]=pending.entries().next().value;pending.delete(id);await fn();
 assert.equal(pending.size,0);assert.equal(t.w.document.querySelector('#journey-dialog').dataset.status,'completed');assert.equal(reads,34);assert(calls.every(([,o])=>!o?.method||o.method==='GET'));t.close();
});
test('media unknown status retries transient read failures, then stops on failed status',async()=>{
 let reads=0;const a={action_id:'med_retry',kind:'person',status:'unknown',result:{}};
 const t=setup(async path=>{if(path.endsWith('/media'))return [a];if(path.endsWith('/images'))return [];if(++reads===2)throw Error('network');return reads>=3?{...a,status:'failed'}:a;});const tick=mockPolling(t.w);
 await t.w.WardrobeJourney.history();t.w.document.querySelector('.journey-record-open').click();await flush();await tick();assert.equal(t.w.document.querySelectorAll('.journey-poll-note').length,1);await tick();assert.equal(t.w.document.querySelector('#journey-dialog').dataset.status,'failed');assert.equal(t.w.document.querySelectorAll('.journey-poll-note').length,0);assert.deepEqual(t.notices,[]);await assert.rejects(tick);t.close();
});
for(const transition of ['close','account','view'])test(`media polling discards a late response after ${transition}`,async()=>{
 let reads=0,resolve;const a={action_id:'med_stale_poll',kind:'person',status:'processing',result:{}};
 const t=setup(async path=>{if(path.endsWith('/media'))return [a];if(path.endsWith('/images'))return [];return ++reads===1?a:new Promise(done=>resolve=done);});const tick=mockPolling(t.w);
 await t.w.WardrobeJourney.history();t.w.document.querySelector('.journey-record-open').click();await flush();const inflight=tick();await flush();
 if(transition==='close')t.w.document.querySelector('#journey-dialog').close();else if(transition==='account')t.w.WardrobeJourney.setOwner('2');else t.w.WardrobeJourney.upload('person');
 resolve({...a,status:'completed'});await inflight;assert.notEqual(t.w.document.querySelector('#journey-dialog').dataset.status,'completed');await assert.rejects(tick);t.close();
});

test('attachment execution guidance opens one fresh single-garment picker and never transfers the chat image',async()=>{
 const calls=[];const t=setup(async(...args)=>calls.push(args));
 const host=t.w.document.getElementById('feed');t.w.WardrobeJourney.offer({upload_intent:'garment',attachment_wardrobe_required:true},host);
 assert.match(host.textContent,/单张上传到个人衣橱/);assert.match(host.textContent,/重新选择.*单件衣物/);
 assert.equal(host.querySelectorAll('button').length,1);assert.equal(calls.length,0);
 assert(!byText(t.w,'创建本人试穿形象'));byText(t.w,'选择单张衣物照片').click();
 const input=t.w.document.querySelector('#journey-photo-input');assert(input);assert.equal(input.multiple,false);assert.equal(input.files.length,0);
 assert.equal(calls.length,0);assert(byText(t.w,'确认上传'));t.close();
});
