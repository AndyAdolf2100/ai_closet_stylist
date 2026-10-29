const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const tick=()=>new Promise(r=>setTimeout(r,0));
const initial={revision:1,enabled:true,entries:[{id:'a',category:'穿衣习惯',content:'我不穿高跟鞋'}]};
async function setup(client){
 const dom=new JSDOM('<div id="notice"></div><button id="settings-open"></button><input id="message"><div id="appearance-status"></div>',{url:'http://synthetic.invalid',runScripts:'outside-only'}),w=dom.window;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
 for(const file of ['appearance.js','companion-settings.js','memory.js'])w.eval(fs.readFileSync('stylist/static/'+file,'utf8'));
 const api=(p,o)=>p.includes('companion-profile')?Promise.resolve({profile:{agent_name:'知秋',assistant_persona:'male_calm_v1'}}):client(p,o);
 await w.CompanionSettings.setOwner('a',api,false);
 return {w,dom,$:id=>w.document.getElementById(id),submit:()=>w.document.getElementById('memory-form').dispatchEvent(new w.Event('submit',{cancelable:true}))};
}
test('notebook adds edits deletes toggles and only persists on save',async()=>{
 const writes=[]; const {w,dom,$,submit}=await setup(async(p,o={})=>{if(o.method==='PUT'){writes.push(JSON.parse(o.body));return writes.at(-1);}return initial;});
 await w.LongTermMemory.open();assert($('memory-speaker').textContent.includes('知秋'));
 $('memory-text-a').value='平时喜欢平底鞋';$('memory-text-a').dispatchEvent(new w.Event('input'));
 $('memory-cancel').click();assert.equal(writes.length,0);
 await w.LongTermMemory.open();assert.equal($('memory-text-a').value,'我不穿高跟鞋');
 $('memory-add').click();const texts=$('memory-list').querySelectorAll('textarea');texts[1].value='建议可以直接一点';texts[1].dispatchEvent(new w.Event('input'));
 $('memory-list').querySelectorAll('.memory-category-trigger')[1].click();$('memory-dialog').querySelectorAll('[data-category=相处约定]')[1].click();
 $('memory-list').querySelector('.memory-remove').click();
 $('memory-enabled').checked=false;$('memory-enabled').dispatchEvent(new w.Event('change'));
 submit();await tick();assert.equal(writes[0].entries.length,1);assert.equal(writes[0].entries[0].category,'相处约定');assert.equal(writes[0].enabled,false);assert(!$('memory-dialog').open);
 assert.equal(w.localStorage.length,0);dom.window.close();
});
test('failed save preserves draft and message belongs to the modal',async()=>{
 const {w,dom,$,submit}=await setup(async(p,o={})=>{if(o.method==='PUT')throw Error('模拟保存失败');return initial;});
 await w.LongTermMemory.open();$('memory-text-a').value='改写的一页';$('memory-text-a').dispatchEvent(new w.Event('input'));submit();await tick();
 assert($('memory-dialog').open);assert.equal($('memory-text-a').value,'改写的一页');assert(!$('memory-save').disabled);
 assert.equal($('companion-notification').parentElement,$('memory-dialog'));assert($('companion-notification').textContent.includes('模拟保存失败'));dom.window.close();
});
test('late read and write after account change cannot populate another account',async()=>{
 let resolveRead,resolveWrite;let mode='read';
 const {w,dom,$,submit}=await setup(async(p,o={})=>o.method==='PUT'?new Promise(r=>resolveWrite=r):mode==='read'?new Promise(r=>resolveRead=r):initial);
 const open=w.LongTermMemory.open();w.LongTermMemory.setOwner('b',async()=>({revision:0,enabled:true,entries:[]}));resolveRead(initial);await open;
 assert(!$('memory-dialog').open);assert.equal($('memory-list').children.length,0);
 mode='write';w.LongTermMemory.setOwner('a',async(p,o={})=>o.method==='PUT'?new Promise(r=>resolveWrite=r):initial);
 await w.LongTermMemory.open();submit();await tick();w.LongTermMemory.setOwner('b',async()=>({revision:0,enabled:true,entries:[]}));
 resolveWrite(initial);await tick();assert(!$('memory-dialog').open);assert.equal($('memory-list').children.length,0);dom.window.close();
});
test('validation, conflict and load retry remain recoverable; content renders as text',async()=>{
 let failed=true;const {w,dom,$,submit}=await setup(async(p,o={})=>{if(o.method==='PUT')throw Object.assign(Error('手记已有新的修改'),{code:'memory_conflict'});if(failed)throw Error('读取失败');return {...initial,entries:[{...initial.entries[0],content:'<img src=x onerror=alert(1)>'}]};});
 await w.LongTermMemory.open();assert(!$('memory-retry').hidden);assert($('memory-save').disabled);
 failed=false;$('memory-retry').click();await tick();assert.equal($('memory-list').querySelector('img'),null);
 $('memory-add').click();submit();assert($('companion-notification').textContent.includes('1—240'));
 $('memory-list').querySelectorAll('.memory-remove')[1].click();submit();await tick();
 assert(!$('memory-conflict').hidden);assert($('memory-save').disabled);assert.equal($('memory-text-a').value,'<img src=x onerror=alert(1)>');dom.window.close();
});

test('custom category picker supports keyboard, dismissal and draft cancellation',async()=>{
 const {w,dom,$}=await setup(async()=>initial);
 await w.LongTermMemory.open();assert.equal($('memory-list').querySelector('select'),null);
 const trigger=$('memory-list').querySelector('.memory-category-trigger');trigger.click();
 assert.equal(trigger.getAttribute('aria-expanded'),'true');
 const list=$('memory-dialog').querySelector('[role=listbox]');
 list.dispatchEvent(new w.KeyboardEvent('keydown',{key:'End',bubbles:true,cancelable:true}));
 assert.equal(w.document.activeElement.dataset.category,'相处约定');w.document.activeElement.click();
 assert.equal(trigger.textContent,'相处约定⌄');assert.equal(w.document.activeElement,trigger);assert(list.hidden);
 trigger.click();list.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));
 assert($('memory-dialog').open);assert(list.hidden);
 trigger.click();$('memory-text-a').click();assert(list.hidden);
 $('memory-cancel').click();await w.LongTermMemory.open();assert($('memory-list').querySelector('.memory-category-trigger').textContent.includes('穿衣习惯'));
 dom.window.close();
});

for (const width of [320,390,720]) test(`floating category stays within ${width}px dialog without expanding the page`,async()=>{
 const {w,dom,$}=await setup(async()=>initial);await w.LongTermMemory.open();
 const trigger=$('memory-list').querySelector('.memory-category-trigger');
 $('memory-dialog').getBoundingClientRect=()=>({left:0,top:0,right:width,bottom:568,width,height:568});
 trigger.getBoundingClientRect=()=>({left:width-90,top:480,right:width-10,bottom:524,width:80,height:44});
 trigger.click();const list=$('memory-dialog').querySelector('[role=listbox]');
 assert.equal(list.parentElement,$('memory-dialog'));assert(!$('memory-list').contains(list));
 assert(parseFloat(list.style.left)>=0);assert(parseFloat(list.style.left)+parseFloat(list.style.width)<=width);
 assert(parseFloat(list.style.top)<480);assert.equal(trigger.getAttribute('aria-expanded'),'true');
 $('memory-dialog').querySelector('.memory-scroll').dispatchEvent(new w.Event('scroll'));assert(list.hidden);
 dom.window.close();
});
