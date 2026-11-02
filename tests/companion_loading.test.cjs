const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const app=fs.readFileSync('stylist/static/app.js','utf8');
const pending=app.slice(app.indexOf('function pendingBubble('),app.indexOf('\nfunction namedElement('));
function setup(){
 const dom=new JSDOM('<html data-stylist-gender="female"><body><div id="feed"></div></body></html>',{runScripts:'outside-only'}),w=dom.window,timers=new Map();let id=0;
 for(const file of ['companion-characters.js','companion-loading.js'])w.eval(fs.readFileSync('stylist/static/'+file,'utf8'));
 w.setTimeout=(run,ms)=>{timers.set(++id,{run,ms});return id;};w.clearTimeout=key=>timers.delete(key);
 w.setInterval=()=>{throw Error('loading must not need a repeating JavaScript timer');};
 w.bubble=()=>{const node=w.document.createElement('section');w.document.querySelector('#feed').append(node);return node;};
 w.eval(pending+'\nwindow.makePending=pendingBubble;');
 return {w,timers,close:()=>dom.window.close()};
}
for(const persona of ['female_sweet_v1','female_warm_v1','female_regal_v1','male_artistic_v1','male_calm_v1','male_confident_v1']){
 test(persona+' selects its own loading portrait and preserves the same animation through all stages',()=>{
  const t=setup(),male=persona.startsWith('male_');
  t.w.document.documentElement.dataset.stylistGender=male?'female':'male';
  const waiting=t.w.makePending(persona),icon=waiting.node.querySelector('.companion-loading');
  assert.equal(icon.dataset.gender,male?'male':'female');assert.equal(icon.dataset.persona,persona);assert.equal(icon.classList.contains('mascot'),false);
  assert.equal(waiting.node.querySelectorAll('[role=status]').length,1);
  for(const stage of ['connecting','understanding','weather','wardrobe','styling','checking']){
   waiting.update({stage,message:'实际阶段：'+stage});
   assert.equal(waiting.node.querySelector('[data-loading-message]').textContent,'实际阶段：'+stage);
   assert.equal(waiting.node.querySelector('.companion-loading'),icon);
  }
  t.timers.values().next().value.run();assert(icon.isConnected);assert.match(waiting.node.textContent,/还在等待服务返回/);
  waiting.stop();assert.equal(icon.isConnected,false);assert.equal(t.timers.size,0);t.close();
 });
}
test('shared loaders escape supplied text and announce the visible state without animated aria noise',()=>{
 const t=setup(),node=t.w.CompanionLoading.create({message:'<img src=x onerror=alert(1)>',detail:'<b>等待</b>',gender:'male'});
 assert.equal(node.querySelector('img'),null);assert.equal(node.querySelector('b'),null);
 assert.equal(node.getAttribute('role'),'status');assert.equal(node.getAttribute('aria-live'),'polite');
 assert.equal(node.querySelector('.companion-loading').getAttribute('aria-hidden'),'true');
 t.w.CompanionLoading.update(node,{message:'已经读到形象，正在确认费用。',detail:''});
 assert.equal(node.querySelector('[data-loading-detail]').hidden,true);assert.match(node.textContent,/已经读到形象/);t.close();
});
test('two loaders can be updated independently and inherited-theme icons remain free of profile state',()=>{
 const t=setup(),a=t.w.CompanionLoading.create({message:'读取手记',announce:false,size:'small'}),b=t.w.CompanionLoading.create({message:'读取形象',gender:'male'});
 t.w.CompanionLoading.update(a,{message:'手记已读到'});assert.match(a.textContent,/手记已读到/);assert.equal(b.textContent,'读取形象');
 assert.equal(a.querySelector('.companion-loading').hasAttribute('data-gender'),false);assert.equal(a.hasAttribute('role'),false);t.close();
});
