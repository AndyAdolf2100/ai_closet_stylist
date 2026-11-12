const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const tick=()=>new Promise(r=>setTimeout(r,0));
const initial={revision:1,enabled:true,entries:[{id:'a',category:'穿衣习惯',content:'我不穿高跟鞋'}]};
async function setup(client){
 const dom=new JSDOM('<div id="notice"></div><button id="settings-open"></button><input id="message"><div id="appearance-status"></div>',{url:'http://synthetic.invalid',runScripts:'outside-only'}),w=dom.window;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
 for(const file of ['appearance.js','companion-characters.js','companion-settings.js','companion-loading.js','memory.js'])w.eval(fs.readFileSync('stylist/static/'+file,'utf8'));
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
 $('memory-add').click();const texts=$('memory-list').querySelectorAll('textarea');texts[1].value='我喜欢棉质衬衫';texts[1].dispatchEvent(new w.Event('input'));
 assert.equal($('memory-dialog').querySelectorAll('[role=listbox]').length,0);
 $('memory-list').querySelector('.memory-remove').click();
 $('memory-enabled').checked=false;$('memory-enabled').dispatchEvent(new w.Event('change'));
 submit();await tick();assert.equal(writes[0].entries.length,1);assert.equal(writes[0].entries[0].category,'穿衣习惯');assert.equal(writes[0].enabled,false);assert(!$('memory-dialog').open);
 assert.equal(w.localStorage.length,0);dom.window.close();
});
test('notebook uses shared loading while reading and removes it after a failed read without writing',async()=>{
 let finish;const calls=[];const {w,dom,$}=await setup((p,o)=>{calls.push([p,o]);return new Promise((resolve,reject)=>finish=reject);});
 const read=w.LongTermMemory.open();assert.equal($('memory-loading').hidden,false);assert($('memory-loading').querySelector('.companion-loading'));
 assert.equal($('memory-loading').querySelectorAll('[role=status]').length,0);
 finish(Error('读取失败'));await read;assert.equal($('memory-loading').hidden,true);assert.equal($('memory-retry').hidden,false);
 assert.equal(calls.length,1);assert.equal(calls[0][1],undefined);dom.window.close();
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
 const original=$('memory-text-a').value;$('memory-text-a').value='衣'.repeat(241);$('memory-text-a').dispatchEvent(new w.Event('input'));submit();assert($('companion-notification').textContent.includes('最多可写 240'));
 $('memory-text-a').value=original;$('memory-text-a').dispatchEvent(new w.Event('input'));$('memory-add').click();submit();await tick();
 assert(!$('memory-conflict').hidden);assert($('memory-save').disabled);assert.equal($('memory-text-a').value,'<img src=x onerror=alert(1)>');dom.window.close();
});

test('only clothing notes are offered and legacy categories are not rendered',async()=>{
 const legacy={...initial,entries:[...initial.entries,{id:'daily',category:'日常片段',content:'我喜欢乌龙茶'},{id:'rule',category:'相处约定',content:'以后叫我亲爱的'}]};
 const {w,dom,$,submit}=await setup(async()=>legacy);await w.LongTermMemory.open();
 assert.equal($('memory-list').querySelectorAll('textarea').length,1);
 assert.equal($('memory-list').querySelectorAll('select, [role=listbox], .memory-category-trigger').length,0);
 assert($('memory-list').textContent.includes('穿衣习惯'));
 assert(!$('memory-list').textContent.includes('日常片段'));
 assert($('memory-dialog').querySelector('.memory-footnote').textContent.includes('穿衣习惯'));
 $('memory-add').click();assert.equal($('memory-list').querySelectorAll('textarea').length,2);
 $('memory-cancel').click();await w.LongTermMemory.open();assert.equal($('memory-list').querySelectorAll('textarea').length,1);
 dom.window.close();
});

test('compliance failure from API preserves draft and retry',async()=>{
 let fail=true;const writes=[];const {w,dom,$,submit}=await setup(async(p,o={})=>{if(o.method==='PUT'){writes.push(JSON.parse(o.body));if(fail)throw Object.assign(Error('这段文字暂时还不能收进手记。换个说法再试试吧，刚才写的内容还在。'),{code:'text_check_rejected'});return initial;}return initial;});
 await w.LongTermMemory.open();$('memory-text-a').value='我喜欢乌龙茶';$('memory-text-a').dispatchEvent(new w.Event('input'));submit();await tick();
 assert($('memory-dialog').open);assert.equal($('memory-text-a').value,'我喜欢乌龙茶');assert($('companion-notification').textContent.includes('刚才写的内容还在'));
 $('memory-text-a').value='我喜欢羊毛外套';$('memory-text-a').dispatchEvent(new w.Event('input'));fail=false;submit();await tick();
 assert.equal(writes[1].entries[0].category,'穿衣习惯');assert(!$('memory-dialog').open);dom.window.close();
});

test('saving drops empty new and cleared existing notes while preserving valid content and book settings',async()=>{
 const writes=[];const book={...initial,entries:[...initial.entries,{id:'cleared',category:'穿衣习惯',content:'以前喜欢羊毛'}]};
 const{w,dom,$,submit}=await setup(async(p,o={})=>{if(o.method==='PUT'){writes.push(JSON.parse(o.body));return writes.at(-1)}return book});
 await w.LongTermMemory.open();$('memory-text-a').value='  喜欢棉质衬衫  ';$('memory-text-a').dispatchEvent(new w.Event('input'));
 $('memory-text-cleared').value=' \n\t\u3000 ';$('memory-text-cleared').dispatchEvent(new w.Event('input'));
 $('memory-add').click();$('memory-add').click();$('memory-enabled').checked=false;$('memory-enabled').dispatchEvent(new w.Event('change'));submit();await tick();
 assert.equal(writes.length,1);assert.equal(writes[0].revision,initial.revision);assert.equal(writes[0].enabled,false);assert.deepEqual(writes[0].entries,[{id:'a',category:'穿衣习惯',content:'喜欢棉质衬衫'}]);assert(!$('memory-dialog').open);assert(!$('companion-notification').textContent.includes('1—240'));dom.window.close();
});
test('saving an entirely blank notebook submits an empty list and reopens with no pages',async()=>{
 const writes=[];let book=initial;const{w,dom,$,submit}=await setup(async(p,o={})=>{if(o.method==='PUT'){writes.push(JSON.parse(o.body));book={...writes.at(-1),revision:2};return book}return book});
 await w.LongTermMemory.open();$('memory-text-a').value=' \n\t ';$('memory-text-a').dispatchEvent(new w.Event('input'));$('memory-add').click();submit();await tick();
 assert.deepEqual(writes[0].entries,[]);assert.equal(writes[0].enabled,true);await w.LongTermMemory.open();assert.equal($('memory-list').children.length,0);assert.equal($('memory-empty').hidden,false);dom.window.close();
});
test('failed filtered saves retain the complete draft and retry with the same revision',async()=>{
 let fail=true;const writes=[];const{w,dom,$,submit}=await setup(async(p,o={})=>{if(o.method==='PUT'){writes.push(JSON.parse(o.body));if(fail)throw Error('模拟保存失败');return writes.at(-1)}return initial});
 await w.LongTermMemory.open();$('memory-add').click();submit();await tick();assert($('memory-dialog').open);assert.equal($('memory-list').children.length,2);assert.equal(writes[0].entries.length,1);assert($('companion-notification').textContent.includes('模拟保存失败'));
 fail=false;submit();await tick();assert.deepEqual(writes[1],writes[0]);assert(!$('memory-dialog').open);dom.window.close();
});

test('manual notes without clothing keywords reach the server for compliance review',async()=>{
 const writes=[];const{w,dom,$,submit}=await setup(async(p,o={})=>{if(o.method==='PUT'){writes.push(JSON.parse(o.body));return writes.at(-1)}return initial});
 await w.LongTermMemory.open();$('memory-text-a').value='舒服自在就很好';$('memory-text-a').dispatchEvent(new w.Event('input'));submit();await tick();
 assert.equal(writes.length,1);assert.equal(writes[0].entries[0].content,'舒服自在就很好');assert(!$('memory-dialog').open);dom.window.close();
});

test('compliance service failure retains draft, enabled state, revision and allows retry',async()=>{
 const writes=[];let fail=true;const{w,dom,$,submit}=await setup(async(p,o={})=>{if(o.method==='PUT'){writes.push(JSON.parse(o.body));if(fail)throw Object.assign(Error('这几页还没收好，文字检查暂时没能完成。内容还在，稍后再试一次就好。'),{code:'text_check_unavailable'});return writes.at(-1)}return initial});
 await w.LongTermMemory.open();$('memory-text-a').value='舒服自在就很好';$('memory-text-a').dispatchEvent(new w.Event('input'));$('memory-enabled').checked=false;$('memory-enabled').dispatchEvent(new w.Event('change'));submit();await tick();
 assert($('memory-dialog').open);assert.equal($('memory-text-a').value,'舒服自在就很好');assert.equal($('memory-enabled').checked,false);assert.equal(writes[0].revision,initial.revision);assert(!$('memory-save').disabled);assert($('companion-notification').textContent.includes('内容还在'));
 fail=false;submit();await tick();assert.deepEqual(writes[1],writes[0]);assert(!$('memory-dialog').open);dom.window.close();
});
