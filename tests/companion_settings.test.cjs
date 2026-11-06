const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const vm=require('node:vm');
const {JSDOM}=require('jsdom');
const root=path.join(__dirname,'../stylist/static');
const tick=()=>new Promise(r=>setTimeout(r,0));
function choose(w,id){
 w.document.querySelector('[name=companion-assistant-gender][value="'+w.CompanionCharacters.gender(id)+'"]').click();
 w.document.querySelector('[name=companion-persona][value="'+id+'"]').click();
}
const profile=(name='知秋')=>({user_name:'小夏',user_gender:'女',agent_name:name,assistant_persona:'male_calm_v1',color_scheme:'companion'});
async function setup(editPage=false){
 const dom=new JSDOM((editPage?'<html data-app-design="yijian">':'')+'<div id="notice"></div><span data-agent-name>衣衣</span><p data-stylist-copy="intro"></p><input id="message"><div id="appearance-status"></div>',{url:'http://synthetic.invalid/',runScripts:'outside-only'}),w=dom.window;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
 w.eval(fs.readFileSync(path.join(root,'appearance.js'),'utf8'));w.eval(fs.readFileSync(path.join(root,'companion-characters.js'),'utf8'));w.eval(fs.readFileSync(path.join(root,'companion-settings.js'),'utf8'));await tick();
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
 choose(w,'male_calm_v1');submit();await tick();
 assert.equal(writes.length,1);assert.deepEqual(writes[0],{...profile(),account_fields:['user_name','user_gender']});assert(!$('companion-dialog').open);
 assert.equal(w.document.querySelector('[data-agent-name]').textContent,'知秋');assert.equal(w.document.documentElement.dataset.stylistGender,'male');
 assert(w.document.querySelector('[data-stylist-copy=intro]').textContent.includes('知秋'));
 const snapshot=w.CompanionSettings.getProfile();await w.CompanionSettings.open();$('companion-agent-name').value='另一个名字';w.document.querySelector('.companion-close').click();assert.equal(w.CompanionSettings.getProfile().agent_name,'知秋');assert.equal(snapshot.agent_name,'知秋');
 dom.window.close();
});
test('system colors preview immediately, survive persona changes and back, then persist and reopen',async()=>{
 const {w,dom,$,submit}=await setup();let stored=profile();const writes=[];
 await w.CompanionSettings.setOwner('color-a',async(p,o={})=>{if(o.method==='PUT'){stored=JSON.parse(o.body);writes.push(stored);}return {profile:stored};},false);
 await w.CompanionSettings.open();submit();submit();submit();const toggle=$('companion-system-color');
 assert.equal(toggle.checked,false);toggle.click();assert.equal(w.document.documentElement.dataset.colorScheme,'system');assert.equal(writes.length,0);
 toggle.click();assert.equal(w.document.documentElement.dataset.colorScheme,'system');assert.equal(w.document.querySelectorAll('[name=companion-color-scheme]:checked').length,1);
 choose(w,'female_regal_v1');assert.equal(toggle.checked,true);assert.equal(w.document.documentElement.dataset.colorScheme,'system');assert.equal(w.document.documentElement.dataset.stylistGender,'female');
 $('companion-back').click();submit();assert.equal(toggle.checked,true);submit();await tick();
 assert.equal(writes.length,1);assert.equal(stored.color_scheme,'system');assert.equal(stored.assistant_persona,'female_regal_v1');assert.equal(stored.user_gender,'女');
 await w.CompanionSettings.setOwner('color-a',async()=>({profile:stored}),false);await w.CompanionSettings.open();submit();submit();submit();assert.equal(toggle.checked,true);
 assert.equal(w.document.documentElement.dataset.colorScheme,'system');dom.window.close();
});
test('cancel restores both saved color and persona; disabling colors restores the current persona theme',async()=>{
 const {w,dom,$,submit}=await setup();await w.CompanionSettings.setOwner('color-b',async()=>({profile:{...profile(),color_scheme:'system'}}),false);
 await w.CompanionSettings.open();submit();submit();submit();$('companion-color-companion').click();choose(w,'female_sweet_v1');
 assert.equal(w.document.documentElement.dataset.colorScheme,'companion');assert.equal(w.document.documentElement.dataset.stylistGender,'female');
 w.document.querySelector('.companion-close').click();assert.equal(w.document.documentElement.dataset.colorScheme,'system');assert.equal(w.document.documentElement.dataset.companionPersona,'male_calm_v1');
 assert.equal(w.CompanionSettings.getProfile().color_scheme,'system');await w.CompanionSettings.setOwner(null);assert.equal(w.document.documentElement.dataset.colorScheme,'companion');dom.window.close();
});
test('failed color save keeps preview and draft while account switch ignores a late save and clears colors',async()=>{
 const {w,dom,$,submit}=await setup();let fail=true,resolveSave;
 await w.CompanionSettings.setOwner('color-old',async(p,o={})=>{if(o.method==='PUT'){if(fail)throw Error('配色保存失败');return new Promise(r=>resolveSave=r);}return {profile:profile()};},false);
 await w.CompanionSettings.open();submit();submit();submit();$('companion-system-color').click();submit();await tick();
 assert($('companion-dialog').open);assert($('companion-system-color').checked);assert.equal(w.document.documentElement.dataset.colorScheme,'system');assert.equal(w.CompanionSettings.getProfile().color_scheme,'companion');
 fail=false;submit();await tick();assert.equal($('companion-system-color').disabled,true);
 await w.CompanionSettings.setOwner('color-new',async()=>({profile:{...profile(),assistant_persona:'female_warm_v1'}}),false);
 resolveSave({profile:{...profile(),color_scheme:'system'}});await tick();assert.equal(w.document.documentElement.dataset.colorScheme,'companion');assert.equal(w.CompanionSettings.getProfile().assistant_persona,'female_warm_v1');
 await w.CompanionSettings.setOwner(null);assert.equal(w.document.documentElement.dataset.colorScheme,'companion');dom.window.close();
});
test('old profiles default to companion colors and saving other preferences preserves system colors',async()=>{
 const {w,dom}=await setup();const writes=[];const old=profile();delete old.color_scheme;
 await w.CompanionSettings.setOwner('legacy',async()=>({profile:old}),false);assert.equal(w.CompanionSettings.getProfile().color_scheme,'companion');
 await w.CompanionSettings.setOwner('modern',async(p,o={})=>{if(o.method==='PUT'){writes.push(JSON.parse(o.body));return {profile:writes.at(-1)};}return {profile:{...profile(),color_scheme:'system'}};},false);
 await w.CompanionSettings.savePreferences({mbti:'INTJ',zodiac:null,conversation_style:'自然相处',reply_detail:'适中',style_preferences:[],dressing_priorities:[]});
 assert.equal(writes[0].color_scheme,'system');assert.equal(w.CompanionSettings.getProfile().color_scheme,'system');assert.equal(w.document.documentElement.dataset.colorScheme,'system');dom.window.close();
});
test('failed save retains the last step and draft, and allows retry',async()=>{
 const {w,dom,$,submit}=await setup();let fail=true;
 await w.CompanionSettings.setOwner('a',async(p,o={})=>{if(o.method==='PUT'){if(fail)throw Error('合成保存失败');return {profile:JSON.parse(o.body)};}return {profile:null};});
 $('companion-user-skip').click();submit();$('companion-agent-name').value='沐沐';submit();submit();await tick();
 assert($('companion-dialog').open);assert.equal($('companion-dialog').dataset.step,'3');assert($('companion-notification').textContent.includes('失败')); assert.equal($('companion-error').textContent,''); assert.equal($('companion-notification').parentElement,$('companion-dialog'));assert(!$('companion-next').disabled);
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
test('persona selection previews theme immediately, preserves draft on back and restores on cancel',async()=>{
 const {w,dom,$,submit}=await setup();const writes=[];
 await w.CompanionSettings.setOwner('a',async(p,o={})=>{if(o.method==='PUT'){writes.push(JSON.parse(o.body));return {profile:writes.at(-1)};}return {profile:{...profile(),assistant_persona:'female_warm_v1'}};});
 await w.CompanionSettings.open();submit();submit();submit();
 const male=w.document.querySelector('[name=companion-persona][value=male_calm_v1]');
 choose(w,'male_calm_v1');assert.equal(w.document.documentElement.dataset.stylistGender,'male');assert.equal(writes.length,0);
 assert.equal(w.CompanionSettings.getProfile().assistant_persona,'female_warm_v1','draft preview does not change request profile');
 $('companion-back').click();assert.equal(w.document.documentElement.dataset.stylistGender,'male');submit();assert(male.checked);
 w.document.querySelector('.companion-close').click();assert.equal(w.document.documentElement.dataset.stylistGender,'female');
 assert.equal(w.localStorage.getItem('ai-closet-stylist-appearance-v1'),null);assert.equal(writes.length,0);
 await w.CompanionSettings.open();submit();submit();submit();choose(w,'male_calm_v1');submit();await tick();
 assert.equal(writes.length,1);assert.equal(writes[0].assistant_persona,'male_calm_v1');assert.equal(w.document.documentElement.dataset.stylistGender,'male');
 await w.CompanionSettings.open();submit();submit();submit();choose(w,'female_warm_v1');
 assert.equal(w.document.documentElement.dataset.stylistGender,'female');
 $('companion-dialog').dispatchEvent(new w.Event('cancel',{cancelable:true}));assert.equal(w.document.documentElement.dataset.stylistGender,'male');
 dom.window.close();
});
test('failed preview save stays selected and account switch discards its theme',async()=>{
 const {w,dom,$,submit}=await setup();
 await w.CompanionSettings.setOwner('a',async(p,o={})=>{if(o.method==='PUT')throw Error('保存失败');return {profile:{...profile(),assistant_persona:'female_warm_v1'}};});
 await w.CompanionSettings.open();submit();submit();submit();choose(w,'male_calm_v1');submit();await tick();
 assert.equal(w.document.documentElement.dataset.stylistGender,'male');assert($('companion-dialog').open);
 assert.equal(w.CompanionSettings.getProfile().assistant_persona,'female_warm_v1');
 await w.CompanionSettings.setOwner('b',async()=>({profile:{...profile('小林'),assistant_persona:'female_warm_v1'}}),false);
 assert.equal(w.document.documentElement.dataset.stylistGender,'female');assert.equal(w.CompanionSettings.getProfile().agent_name,'小林');
 // A delayed native close event from the previous dialog cannot restore A's preview.
 $('companion-dialog').dispatchEvent(new w.Event('close'));assert.equal(w.document.documentElement.dataset.stylistGender,'female');
 dom.window.close();
});
test('successful save shows a dismissible assistant notification with timed and account cleanup',async()=>{
 const {w,dom,$,submit}=await setup();let pending=null,clears=0;
 w.setTimeout=callback=>{pending=callback;return 1;};w.clearTimeout=()=>{pending=null;clears++;};
 await w.CompanionSettings.setOwner('a',async(p,o={})=>({profile:o.method==='PUT'?JSON.parse(o.body):null}));
 submit();submit();$('companion-agent-name').value='知秋 & 小林';submit();
 choose(w,'male_calm_v1');submit();await tick();
 const toast=$('companion-notification');assert(!toast.hidden);assert.equal(toast.dataset.persona,'male_calm_v1');
 assert.equal(toast.querySelector('strong').textContent,'知秋 & 小林');assert(toast.querySelector('p').textContent.includes('以后就叫我知秋 & 小林吧。'));
 assert.equal($('notice').textContent,'');assert.equal(toast.querySelector('[role=status]').getAttribute('aria-live'),'polite');assert(pending);
 toast.dispatchEvent(new w.Event('mouseenter'));assert.equal(pending,null);toast.dispatchEvent(new w.Event('mouseleave'));assert(pending);
 toast.querySelector('button').focus();assert.equal(pending,null);toast.querySelector('button').blur();await tick();assert(pending);
 pending();assert(!toast.hidden);assert(toast.classList.contains('is-leaving'));
 const ended=new w.Event('animationend');Object.defineProperty(ended,'animationName',{value:'companion-message-out'});toast.dispatchEvent(ended);
 assert(toast.hidden);assert.equal(toast.querySelector('p').textContent,'');
 await w.CompanionSettings.open();submit();submit();submit();submit();await tick();assert(!toast.hidden);
 toast.querySelector('button').click();assert(toast.classList.contains('is-leaving'));assert(!toast.hidden);
 pending();assert(toast.hidden);assert.equal(pending,null);
 await w.CompanionSettings.open();submit();submit();submit();submit();await tick();assert(!toast.hidden);
 await w.CompanionSettings.setOwner(null);assert(toast.hidden);assert.equal(pending,null);assert.equal(toast.textContent.trim(),'×');assert(clears>0);
 dom.window.close();
});
test('notification body opens a complete letter, X only dismisses, and account changes clear detail',async()=>{
 const {w,dom,$,submit}=await setup();
 await w.CompanionSettings.setOwner('a',async(p,o={})=>({profile:o.method==='PUT'?JSON.parse(o.body):null}));
 submit();submit();$('companion-agent-name').value='知秋 & 小林';submit();choose(w,'male_calm_v1');submit();await tick();
 const toast=$('companion-notification'),letter=$('companion-message-dialog'),body=toast.querySelector('p').textContent;
 toast.querySelector('p').click();assert(letter.open);assert(toast.hidden);assert.equal(letter.dataset.persona,'male_calm_v1');
 assert.equal(letter.querySelector('.companion-letter-body').textContent,body);assert.equal($('companion-message-title').textContent,'知秋 & 小林的来信');
 letter.querySelector('.companion-letter-done').click();assert(!letter.open);assert.equal(letter.querySelector('.companion-letter-body').textContent,'');
 await w.CompanionSettings.open();submit();submit();submit();submit();await tick();
 toast.querySelector('.companion-notification-close').click();assert(!letter.open);assert(toast.classList.contains('is-leaving'));
 await w.CompanionSettings.open();submit();submit();submit();submit();await tick();
 const openButton=toast.querySelector('.companion-message-open');assert.equal(openButton.getAttribute('aria-haspopup'),'dialog');openButton.click();assert(letter.open);
 const cancel=new w.Event('cancel',{cancelable:true});letter.dispatchEvent(cancel);assert(cancel.defaultPrevented);assert(!letter.open);
 await w.CompanionSettings.open();submit();submit();submit();submit();await tick();openButton.click();assert(letter.open);
 await w.CompanionSettings.setOwner(null);assert(!letter.open);assert.equal(letter.querySelector('.companion-letter-body').textContent,'');assert.equal($('companion-message-title').textContent,'');
 dom.window.close();
});

test('saving a renamed companion updates existing message labels without rewriting history',async()=>{
 const {w,dom,$,submit}=await setup();
 await w.CompanionSettings.setOwner('a',async(p,o={})=>({profile:o.method==='PUT'?JSON.parse(o.body):profile('知秋')}),false);
 const author=w.document.createElement('span');author.dataset.agentTemplate='衣衣 · 私人搭配师';author.textContent='知秋 · 私人搭配师';
 const avatar=w.document.createElement('div');avatar.dataset.agentAriaTemplate='衣衣向你打招呼';
 const body=w.document.createElement('p');body.textContent='知秋刚才的建议。';w.document.body.append(author,avatar,body);
 await w.CompanionSettings.open();submit();submit();$('companion-agent-name').value='小林';submit();
 assert.equal(author.textContent,'知秋 · 私人搭配师');submit();await tick();
 assert.equal(author.textContent,'小林 · 私人搭配师');assert.equal(avatar.getAttribute('aria-label'),'小林向你打招呼');
 assert.equal(body.textContent,'知秋刚才的建议。');dom.window.close();
});

test('preset error messages follow persona and retain the action to recover',async()=>{
 const {w,dom,$}=await setup();
 for(const [persona,expected] of [['female_warm_v1','先从列表里选一座城市吧'],['male_calm_v1','先从列表选择城市']]){
  await w.CompanionSettings.setOwner(persona,async()=>({profile:{...profile(),assistant_persona:persona}}),false);
  await w.CompanionSettings.open();w.CompanionSettings.notify('请先从列表中选择一座城市。');
  assert($('companion-notification').textContent.includes(expected));
  assert.equal($('companion-notification').parentElement,$('companion-dialog'));
  w.CompanionSettings.notify('报价已失效，需要重新确认费用。');
  assert($('companion-notification').textContent.includes('报价已失效，需要重新确认费用。'));
 }
 dom.window.close();
});

test('picture gender selection exposes three static characters and remembers each draft choice',async()=>{
 const {w,dom,$,submit}=await setup();const writes=[];
 await w.CompanionSettings.setOwner('six-a',async(p,o={})=>{if(o.method==='PUT'){writes.push(JSON.parse(o.body));return {profile:writes.at(-1)};}return {profile:null};});
 submit();submit();submit();
 const visible=()=>[...w.document.querySelectorAll('[data-character-gender]')].filter(card=>!card.hidden);
 assert.equal(visible().length,3);assert(visible().every(card=>card.dataset.characterGender==='male'));
 assert.equal(w.document.querySelectorAll('.companion-assistant-gender img').length,2);
 choose(w,'female_regal_v1');choose(w,'male_confident_v1');
 assert(visible().every(card=>card.dataset.characterGender==='male'));
 assert.equal(w.document.documentElement.dataset.companionPersona,'male_confident_v1');
 assert.equal(w.CompanionSettings.getProfile().assistant_persona,'male_calm_v1');
 w.document.querySelector('[name=companion-assistant-gender][value=female]').click();
 assert(w.document.querySelector('[name=companion-persona][value=female_regal_v1]').checked);
 assert.equal(writes.length,0);assert.equal(w.document.querySelectorAll('.companion-cast-step .companion-portrait').length,0);
 const snapshot=w.CompanionSettings.getProfile();$('companion-back').click();submit();
 assert(w.document.querySelector('[name=companion-persona][value=female_regal_v1]').checked);
 w.document.querySelector('.companion-close').click();
 assert.equal(w.document.documentElement.dataset.companionPersona,'male_calm_v1');
 assert.equal(snapshot.assistant_persona,'male_calm_v1');dom.window.close();
});

test('all six selected personas survive saving, reopen, preferences and independent request snapshots',async()=>{
 const {w,dom,$,submit}=await setup();let saved={...profile(),mbti:'INTJ',zodiac:'天秤座',style_preferences:['简约'],dressing_priorities:['已有衣物优先'],conversation_style:'自然相处',reply_detail:'适中'};
 await w.CompanionSettings.setOwner('six-all',async(p,o={})=>{if(o.method==='PUT')saved=JSON.parse(o.body);return {profile:saved};},false);
 for(const character of w.CompanionCharacters.all){
  await w.CompanionSettings.open();submit();submit();submit();choose(w,character.id);submit();await tick();
  const snapshot=w.CompanionSettings.getProfile();
  assert.equal(snapshot.assistant_persona,character.id);assert.equal(saved.assistant_persona,character.id);
  assert.equal(snapshot.user_gender,'女');assert.equal(snapshot.mbti,'INTJ');assert.deepEqual([...snapshot.style_preferences],['简约']);
  await w.CompanionSettings.open();submit();submit();submit();
  assert(w.document.querySelector('[name=companion-persona]:checked').value===character.id);
  w.document.querySelector('.companion-close').click();
  await w.CompanionSettings.savePreferences({...snapshot,reply_detail:'简洁重点'});
  assert.equal(w.CompanionSettings.getProfile().assistant_persona,character.id);
  snapshot.style_preferences.push('运动');assert.equal(w.CompanionSettings.getProfile().style_preferences.length,1);
 }
 dom.window.close();
});

test('a failed specific-character save keeps the draft and switching accounts rejects its late result',async()=>{
 const {w,dom,$,submit}=await setup();let fail=true,resolveWrite;
 await w.CompanionSettings.setOwner('six-a',async(p,o={})=>{if(o.method==='PUT'){if(fail)throw Error('合成失败');return new Promise(resolve=>resolveWrite=resolve);}return {profile:profile()};},false);
 await w.CompanionSettings.open();submit();submit();submit();choose(w,'male_artistic_v1');submit();await tick();
 assert($('companion-dialog').open);assert(w.document.querySelector('[name=companion-persona][value=male_artistic_v1]').checked);
 assert.equal(w.CompanionSettings.getProfile().assistant_persona,'male_calm_v1');
 fail=false;submit();await tick();
 await w.CompanionSettings.setOwner('six-b',async()=>({profile:{...profile('沐沐'),assistant_persona:'female_sweet_v1'}}),false);
 resolveWrite({profile:{...profile(),assistant_persona:'male_artistic_v1'}});await tick();
 assert.equal(w.CompanionSettings.getProfile().assistant_persona,'female_sweet_v1');
 assert.equal(w.document.documentElement.dataset.companionPersona,'female_sweet_v1');
 await w.CompanionSettings.open();submit();submit();submit();assert(!w.document.querySelector('.companion-assistant-gender').disabled);
 dom.window.close();
});

test('the real send function keeps each full persona ID, ignores preview gender and preserves replay snapshots',async()=>{
 const {w,dom,submit}=await setup();
 const source=fs.readFileSync(path.join(root,'app.js'),'utf8');
 const send=source.slice(source.indexOf('async function sendMessage('),source.indexOf('\nfunction showPlanApproval('));
 let captured;
 const context=vm.createContext({window:w,document:w.document,session:{user:{id:'request-a'}},busy:false,
  conversation:null,version:0,pendingRun:null,selectedCity:null,selectedLook:null,pendingUploadAnchor:null,
  requireLogin:()=>true,$:id=>id==='message'?{value:'只聊配色'}:{checked:false},crypto:{randomUUID:()=> 'synthetic-six-request'},
  savePending:value=>{captured=value;throw Error('captured-before-network');}});
 vm.runInContext(send,context);
 for(const character of w.CompanionCharacters.all){
  await w.CompanionSettings.setOwner('request-a',async()=>({profile:{...profile(),assistant_persona:character.id}}),false);
  await assert.rejects(context.sendMessage(),/captured-before-network/);
  assert.equal(captured.request.assistant_persona,character.id);
  assert.equal(captured.request.companion_profile.assistant_persona,character.id);
  assert.equal(captured.request.companion_profile.user_gender,'女');
 }
 await w.CompanionSettings.open();submit();submit();submit();choose(w,'female_sweet_v1');
 assert.equal(w.document.documentElement.dataset.stylistGender,'female');
 await assert.rejects(context.sendMessage(),/captured-before-network/);
 assert.equal(captured.request.assistant_persona,'male_confident_v1','unsaved visual preview never changes outgoing persona');
 context.pendingRun={owner:'request-a',request:{message:'先前请求',assistant_persona:'female_sweet_v1',companion_profile:{assistant_persona:'female_sweet_v1'}}};
 await assert.rejects(context.sendMessage(true),/captured-before-network/);
 assert.equal(captured.request.assistant_persona,'female_sweet_v1');
 dom.window.close();
});

test('new accounts default to the left male group while saved female roles survive account switches',async()=>{
 const {w,dom,$,submit}=await setup();const writes=[];
 assert.equal(w.document.documentElement.dataset.stylistGender,'male');
 const saved={...profile(),assistant_persona:'female_regal_v1'};
 await w.CompanionSettings.setOwner('existing',async()=>({profile:saved}),false);
 assert.equal(w.CompanionSettings.getProfile().assistant_persona,'female_regal_v1');
 await w.CompanionSettings.setOwner('new',async(p,o={})=>{
  if(o.method==='PUT'){writes.push(JSON.parse(o.body));return {profile:writes.at(-1)};}
  return {profile:null};
 });
 assert.equal(w.CompanionSettings.getProfile().assistant_persona,'male_calm_v1');
 assert.equal(w.document.documentElement.dataset.companionPersona,'male_calm_v1');
 submit();w.document.querySelector('[name=companion-user-gender][value="女"]').checked=true;submit();submit();
 assert.deepEqual(Array.from(w.document.querySelectorAll('[name=companion-assistant-gender]'),x=>x.value),['male','female']);
 assert.equal(w.document.querySelector('[name=companion-assistant-gender]:checked').value,'male');
 assert.equal(w.document.querySelector('[name=companion-persona]:checked').value,'male_calm_v1');
 submit();await tick();assert.equal(writes[0].assistant_persona,'male_calm_v1');assert.equal(writes[0].user_gender,'女');
 await w.CompanionSettings.setOwner('existing',async()=>({profile:saved}),false);
 await w.CompanionSettings.open();submit();submit();submit();
 assert.equal(w.document.querySelector('[name=companion-assistant-gender]:checked').value,'female');
 assert.equal(w.document.querySelector('[name=companion-persona]:checked').value,'female_regal_v1');
 w.document.querySelector('.companion-close').click();
 assert.equal(w.CompanionSettings.getProfile().assistant_persona,'female_regal_v1');
 await w.CompanionSettings.setOwner(null);
 assert.equal(w.document.documentElement.dataset.stylistGender,'male');
 assert.equal(w.document.documentElement.dataset.companionPersona,'male_calm_v1');
 dom.window.close();
});

test('notification read action is scoped to its message and cleared on account reset',async()=>{
 const {w,dom,$}=await setup();let calls=0;
 await w.CompanionSettings.setOwner('demo-a',async()=>({profile:profile()}),false);
 w.CompanionSettings.notify('示例积分来信',{onRead:()=>calls++});
 w.document.querySelector('#companion-notification .companion-message-open').click();
 assert.equal(calls,1);assert(!$('companion-message-dialog').open);
 w.CompanionSettings.notify('普通来信');
 w.document.querySelector('#companion-notification .companion-message-open').click();
 assert.equal(calls,1);assert($('companion-message-dialog').open);
 w.CompanionSettings.notify('账号来信',{onRead:()=>calls++});
 await w.CompanionSettings.setOwner(null);
 w.document.querySelector('#companion-notification .companion-message-open').click();
 assert.equal(calls,1);dom.window.close();
});

for(const userGender of ['男','女',null]) for(const scheme of ['companion','system']) {
 test(`H5 palette follows assistant, not account gender ${userGender}, in ${scheme} mode`,async()=>{
  const {w,dom}=await setup(true);
  const saved={...profile(),user_gender:userGender,color_scheme:scheme};
  await w.CompanionSettings.setOwner('theme-owner',async()=>({profile:saved}),false);
  w.document.documentElement.dataset.appPalette=scheme==='system'?'system':'male';
  await w.CompanionSettings.open();
  assert(w.document.querySelector('#companion-color-companion + span').textContent.includes('随角色变动'));
  choose(w,'female_warm_v1');
  assert.equal(w.document.documentElement.dataset.appPalette,scheme==='system'?'system':'female');
  choose(w,'male_confident_v1');
  assert.equal(w.document.documentElement.dataset.appPalette,scheme==='system'?'system':'male');
  w.document.querySelector('.companion-close').click();
  assert.equal(w.document.documentElement.dataset.appPalette,scheme==='system'?'system':'male');
  assert.equal(w.CompanionSettings.getProfile().user_gender,userGender);
  assert.equal(w.CompanionSettings.getProfile().assistant_persona,'male_calm_v1');
  dom.window.close();
 });
}
