const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.join(__dirname,'../stylist/static');
const tick=()=>new Promise(r=>setTimeout(r,0));
const profile=(name='知秋')=>({user_name:'小夏',user_gender:'女',agent_name:name,assistant_persona:'male_calm_v1'});
async function setup(){
 const dom=new JSDOM('<div id="notice"></div><span data-agent-name>衣衣</span><p data-stylist-copy="intro"></p><input id="message"><div id="appearance-status"></div>',{url:'http://synthetic.invalid/',runScripts:'outside-only'}),w=dom.window;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
 w.eval(fs.readFileSync(path.join(root,'appearance.js'),'utf8'));w.eval(fs.readFileSync(path.join(root,'companion-settings.js'),'utf8'));await tick();
 return {w,dom,$:id=>w.document.getElementById(id),submit:()=>w.document.getElementById('companion-form').dispatchEvent(new w.Event('submit',{cancelable:true}))};
}
test('four steps preserve drafts, save once, apply names and keep user/assistant gender separate',async()=>{
 const {w,dom,$,submit}=await setup();const writes=[];
 await w.CompanionSettings.setOwner('a',async(p,o={})=>{if(o.method==='PUT'){writes.push(JSON.parse(o.body));return {profile:writes.at(-1)};}return {profile:null};});
 assert($('companion-dialog').open);assert.equal($('companion-dialog').dataset.step,'0');
 $('companion-user-name').value='小夏';submit();assert.equal($('companion-dialog').dataset.step,'1');
 w.document.querySelector('[name=companion-user-gender][value="女"]').checked=true;submit();
 $('companion-agent-name').value='知秋';$('companion-back').click();assert.equal($('companion-dialog').dataset.step,'1');submit();assert.equal($('companion-agent-name').value,'知秋');
 submit();assert.equal($('companion-dialog').dataset.step,'3');assert.equal(writes.length,0);
 w.document.querySelector('[name=companion-persona][value="male_calm_v1"]').checked=true;submit();await tick();
 assert.equal(writes.length,1);assert.deepEqual(writes[0],profile());assert(!$('companion-dialog').open);
 assert.equal(w.document.querySelector('[data-agent-name]').textContent,'知秋');assert.equal(w.document.documentElement.dataset.stylistGender,'male');
 assert(w.document.querySelector('[data-stylist-copy=intro]').textContent.includes('知秋'));
 const snapshot=w.CompanionSettings.getProfile();await w.CompanionSettings.open();$('companion-agent-name').value='另一个名字';w.document.querySelector('.companion-close').click();assert.equal(w.CompanionSettings.getProfile().agent_name,'知秋');assert.equal(snapshot.agent_name,'知秋');
 dom.window.close();
});
test('failed save retains the last step and draft, and allows retry',async()=>{
 const {w,dom,$,submit}=await setup();let fail=true;
 await w.CompanionSettings.setOwner('a',async(p,o={})=>{if(o.method==='PUT'){if(fail)throw Error('合成保存失败');return {profile:JSON.parse(o.body)};}return {profile:null};});
 $('companion-user-skip').click();submit();$('companion-agent-name').value='沐沐';submit();submit();await tick();
 assert($('companion-dialog').open);assert.equal($('companion-dialog').dataset.step,'3');assert($('companion-error').textContent.includes('失败'));assert(!$('companion-next').disabled);
 fail=false;submit();await tick();assert(!$('companion-dialog').open);assert.equal(w.CompanionSettings.getProfile().agent_name,'沐沐');dom.window.close();
});
test('late reads and writes cannot apply one account profile to another or logout',async()=>{
 const {w,dom,$,submit}=await setup();let resolveRead;
 const old=w.CompanionSettings.setOwner('a',async()=>new Promise(r=>resolveRead=r));
 await w.CompanionSettings.setOwner('b',async()=>({profile:profile('小林')}),false);resolveRead({profile:profile('小夏')});await old;
 assert.equal(w.CompanionSettings.getProfile().agent_name,'小林');
 let resolveWrite;
 await w.CompanionSettings.setOwner('a',async(p,o={})=>o.method==='PUT'?new Promise(r=>resolveWrite=r):({profile:profile()}),false);
 await w.CompanionSettings.open();submit();submit();submit();submit();await tick();
 await w.CompanionSettings.setOwner('b',async()=>({profile:profile('小林')}),false);resolveWrite({profile:profile('小夏')});await tick();
 assert.equal(w.CompanionSettings.getProfile().agent_name,'小林');assert(!$('companion-next').disabled);
 await w.CompanionSettings.setOwner(null);assert.equal(w.CompanionSettings.getProfile(),null);assert.equal(w.CompanionSettings.agentName(),'衣衣');assert.equal(w.document.querySelector('[data-agent-name]').textContent,'衣衣');dom.window.close();
});
test('manual appearance switching persists names unchanged',async()=>{
 const {w,dom}=await setup();const writes=[];
 await w.CompanionSettings.setOwner('a',async(p,o={})=>{if(o.method==='PUT')writes.push(JSON.parse(o.body));return {profile:profile()};},false);
 w.document.documentElement.dataset.stylistGender='female';w.dispatchEvent(new w.CustomEvent('stylist-appearance-selected',{detail:'female'}));await tick();
 assert.equal(writes[0].assistant_persona,'female_warm_v1');assert.equal(writes[0].agent_name,'知秋');assert.equal(writes[0].user_gender,'女');dom.window.close();
});
