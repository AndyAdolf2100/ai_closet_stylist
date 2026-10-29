const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const tick=()=>new Promise(r=>setTimeout(r,0));
async function setup(client){
 const dom=new JSDOM('<div id="notice"></div><button id="settings-open"></button><input id="message"><div id="appearance-status"></div>',{url:'http://synthetic.invalid',runScripts:'outside-only'}),w=dom.window;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
 for(const file of ['appearance.js','companion-settings.js','preferences.js'])w.eval(fs.readFileSync('stylist/static/'+file,'utf8'));
 await w.CompanionSettings.setOwner('a',client,false);
 return {w,dom,$:id=>w.document.getElementById(id),submit:()=>w.document.getElementById('preferences-form').dispatchEvent(new w.Event('submit',{cancelable:true}))};
}
const profile={user_name:'小夏',user_gender:'女',agent_name:'知秋',assistant_persona:'male_calm_v1'};
test('star cards and preferences are optional, cancelable, bounded and saved with identity intact',async()=>{
 const writes=[];const {w,dom,$,submit}=await setup(async(p,o={})=>{if(o.method==='PUT'){writes.push(JSON.parse(o.body));return {profile:writes.at(-1)};}return {profile};});
 await w.PersonalPreferences.open();assert.equal(w.document.querySelectorAll('[data-zodiac]').length,12);
 w.document.querySelector('[data-zodiac="天秤座"]').click();$('preferences-close').click();assert.equal(writes.length,0);
 await w.PersonalPreferences.open();assert.equal($('zodiac-clear').getAttribute('aria-pressed'),'true');
 w.document.querySelector('[data-zodiac="天秤座"]').click();
 $('preference-tab-style').click();assert($('preference-page-stars').hidden);assert(!$('preference-page-style').hidden);
 const styles=w.document.querySelectorAll('[data-preference-group="style_preferences"] button');for(const b of [...styles].slice(0,4))b.click();
 assert.equal(w.document.querySelectorAll('[data-preference-group="style_preferences"] [aria-pressed=true]').length,3);
 assert($('companion-notification').textContent.includes('最多'));assert.equal($('companion-notification').parentElement,$('preferences-dialog'));assert.equal($('preferences-error'),null);
 $('preference-tab-talk').click();assert(!$('preference-page-talk').hidden);
 w.document.querySelector('[data-preference-group="conversation_style"] button:nth-child(3)').click();
 $('preference-tab-talk').dispatchEvent(new w.KeyboardEvent('keydown',{key:'Home',bubbles:true}));
 assert.equal($('preference-tab-stars').getAttribute('aria-selected'),'true');assert.equal(w.document.querySelector('[data-zodiac="天秤座"]').getAttribute('aria-pressed'),'true');
 submit();await tick();
 assert.equal(writes.length,1);assert.equal(writes[0].zodiac,'天秤座');assert.equal(writes[0].conversation_style,'直接坦诚');
 assert.equal(writes[0].assistant_persona,'male_calm_v1');assert.equal(writes[0].agent_name,'知秋');assert(!$('preferences-dialog').open);
 const snapshot=w.CompanionSettings.getProfile();snapshot.style_preferences.push('复古');assert.equal(w.CompanionSettings.getProfile().style_preferences.length,3);
 await w.PersonalPreferences.open();$('preferences-reset').click();submit();await tick();assert.equal(writes[1].zodiac,null);assert.equal(writes[1].style_preferences.length,0);
 dom.window.close();
});
test('save failure retains choices; a late save cannot overwrite a different account',async()=>{
 let fail=true,resolveSave;
 const {w,dom,$,submit}=await setup(async(p,o={})=>{if(o.method!=='PUT')return {profile};if(fail)throw Error('模拟失败');return new Promise(r=>resolveSave=r);});
 await w.PersonalPreferences.open();w.document.querySelector('[data-zodiac="双鱼座"]').click();submit();await tick();
 assert($('preferences-dialog').open);assert($('companion-notification').textContent.includes('模拟失败'));assert.equal(w.document.querySelector('[data-zodiac="双鱼座"]').getAttribute('aria-pressed'),'true');
 fail=false;submit();await tick();await w.CompanionSettings.setOwner('b',async()=>({profile:{...profile,agent_name:'小林'}}),false);
 resolveSave({profile:{...profile,zodiac:'双鱼座'}});await tick();assert.equal(w.CompanionSettings.agentName(),'小林');assert(!$('preferences-dialog').open);
 assert.equal(w.localStorage.getItem('zodiac'),null);dom.window.close();
});
