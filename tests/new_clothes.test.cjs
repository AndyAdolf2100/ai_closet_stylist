const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const app=fs.readFileSync('stylist/static/app.js','utf8');
const cardCode=app.slice(app.indexOf('function wardrobeGapCard('),app.indexOf('function showReply('));
function setup(enabled=false){
 const dom=new JSDOM('<body></body>',{runScripts:'outside-only'}),w=dom.window,calls=[],notices=[];
 Object.assign(w,{session:{user:{id:'a'}},conversation:'c',version:2,busy:false,
  el:(tag,cls,text)=>{const n=w.document.createElement(tag);n.className=cls||'';n.textContent=text||'';return n},
  requireLogin:()=>true,notifyIssue:t=>notices.push(t),setNewClothes:v=>calls.push(['switch',v]),
  sendMessage:async(...args)=>calls.push(['send',args]),WardrobeJourney:{upload:kind=>calls.push(['upload',kind])}});
 w.eval(cardCode);
 const card=w.wardrobeGapCard({conversation_id:'c',version:2,new_clothes:enabled});w.document.body.append(card);
 return {dom,w,card,calls,notices};
}
test('gap card offers two choices and never acts before a click',()=>{
 const t=setup();assert.deepEqual(t.calls,[]);assert.equal(t.card.querySelectorAll('button').length,2);
 t.card.querySelector('button').click();assert.deepEqual(t.calls,[['upload','garment']]);t.dom.window.close();
});
test('explore card enables switch and continues current workflow without uploading',async()=>{
 const t=setup();t.card.querySelectorAll('button')[1].click();await Promise.resolve();
 assert.equal(t.calls[0][0],'switch');assert.equal(t.calls[0][1],true);
 assert.equal(t.calls[1][0],'send');assert.equal(t.calls[1][1][3].owner,'a');
 assert.equal(t.calls[1][1][3].conversation_id,'c');assert.equal(t.calls[1][1][3].version,2);t.dom.window.close();
});
for(const [name,change] of [
 ['owner',t=>t.w.session={user:{id:'b'}}],['conversation',t=>t.w.conversation='other'],
 ['version',t=>t.w.version=3],['busy',t=>t.w.busy=true],['detached',t=>t.card.remove()],
])test(name+' prevents old gap card actions',()=>{
 const t=setup();change(t);for(const b of t.card.querySelectorAll('button'))b.click();
 assert.deepEqual(t.calls,[]);t.dom.window.close();
});
test('an already enabled result does not ask to enable again',()=>{
 const t=setup(true);assert.equal(t.card.querySelectorAll('button').length,1);t.dom.window.close();
});

const selectionCode=app.slice(app.indexOf('function newClothesExplanation('),app.indexOf('function loginStatus('));
function selectionSetup(persona='male_calm_v1'){
 const dom=new JSDOM('<html data-stylist-gender="male"><body><input type="radio" name="source" id="personal-clothes" checked><input type="radio" name="source" id="new-clothes"></body></html>',{runScripts:'outside-only'});
 const w=dom.window,notices=[];
 Object.assign(w,{busy:false,$:id=>w.document.getElementById(id),CompanionSettings:{getProfile:()=>({assistant_persona:persona}),notify:text=>notices.push(text)}});
 w.eval(selectionCode);return {dom,w,notices,personal:w.document.getElementById('personal-clothes'),fresh:w.document.getElementById('new-clothes')};
}
for(const persona of ['female_sweet_v1','female_warm_v1','female_regal_v1','male_artistic_v1','male_calm_v1','male_confident_v1']){
 test(persona+' manual selection explains personal plus outside reference clothes',()=>{
  const t=selectionSetup(persona);t.fresh.click();assert.equal(t.notices.length,1);
  assert(t.notices[0].includes('衣橱外'));assert(t.notices[0].includes('参考'));assert(/已有的衣服|你的衣服|你的衣橱/.test(t.notices[0]));
  assert.equal(t.fresh.checked,true);assert.equal(t.personal.checked,false);t.dom.window.close();
 });
}
test('selected option clicks, switching back and programmatic restore do not repeat explanation',()=>{
 const t=selectionSetup();t.fresh.click();t.fresh.click();assert.equal(t.notices.length,1);
 t.personal.click();assert.equal(t.notices.length,1);
 t.w.setNewClothes(true);t.w.setNewClothes(false);assert.equal(t.notices.length,1);
 t.fresh.click();assert.equal(t.notices.length,2);t.dom.window.close();
});
test('explicit manual card selection explains; disabled and busy selection do not notify',()=>{
 const t=selectionSetup();t.w.setNewClothes(true,{explain:true});assert.equal(t.notices.length,1);
 t.w.setNewClothes(false);t.fresh.disabled=true;t.fresh.click();assert.equal(t.notices.length,1);
 t.fresh.disabled=false;t.w.busy=true;t.fresh.click();assert.equal(t.notices.length,1);t.dom.window.close();
});
test('six companion explanations are distinct and fallback is calm',()=>{
 const t=selectionSetup();const roles=['female_sweet_v1','female_warm_v1','female_regal_v1','male_artistic_v1','male_calm_v1','male_confident_v1'];
 assert.equal(new Set(roles.map(id=>t.w.newClothesExplanation(id))).size,6);
 assert.equal(t.w.newClothesExplanation(null),t.w.newClothesExplanation('male_calm_v1'));t.dom.window.close();
});
