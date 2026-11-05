const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const{chromium}=require(process.env.PLAYWRIGHT_MODULE||'/tmp/stylist-three-lines-20261102/node_modules/playwright');
const base=process.env.GUIDE_APP_URL||'http://127.0.0.1:8466',dir='stylist/static/closet-app/first-visit';
(async()=>{
 const ctx={window:{}};for(const file of['content.js','voices.js'])vm.runInNewContext(fs.readFileSync(dir+'/'+file,'utf8'),ctx);
 const tours=ctx.window.FirstVisitGuideContent,voices=ctx.window.FirstVisitGuideVoices,roles=Object.keys(voices);
 for(const[tour,rows]of Object.entries(tours))for(let step=0;step<rows.length;step++){
  const variants=roles.map(role=>voices[role][tour][step]);assert(variants.every(v=>typeof v==='string'&&v.trim()));assert.equal(new Set(variants).size,roles.length,`${tour} ${step} personality variants repeat`);
 }
 for(const role of roles){const lines=Object.values(voices[role]).flat();assert.equal(new Set(lines).size,lines.length,role+' repeats across functions')}
 const b=await chromium.launch({channel:'chrome'});let checked=0;
 for(const[width,height]of[[320,740],[393,852],[1440,1000]]){
  const p=await b.newPage({viewport:{width,height}}),errors=[],requests=[];p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/stylist-api/'))requests.push(r.url())});await p.goto(base+'/static/closet-app/first-visit/index.html');assert.deepEqual(await p.evaluate(()=>roles.map(r=>r.id).sort()),[...roles].sort());let fixed;
  for(const role of roles){await p.selectOption('#role',role,{force:true});for(const[tour,rows]of Object.entries(tours)){await p.locator(`[data-tour=${tour}]`).click();for(let step=0;step<rows.length;step++){
   await p.waitForFunction(()=>document.querySelector('#app-scene').style.visibility==='visible');const state=await p.evaluate(()=>{const r=document.querySelector('.guide').getBoundingClientRect(),s=document.querySelector('.speech');return{guide:[r.x,r.y,r.width,r.height],text:document.querySelector('#line').innerText,overflow:s.scrollHeight>s.clientHeight+1,emphasis:document.querySelectorAll('#line strong').length,sceneRole:document.querySelector('#app-scene').contentDocument.documentElement.dataset.companionPersona}});
   assert.equal(state.sceneRole,role);assert(state.text.startsWith(voices[role][tour][step]),`${role} ${tour} ${step} maps wrong voice`);assert(state.text.endsWith(rows[step][3]));assert(!state.overflow,`${width} ${role} ${tour} ${step} text overflow`);if(!fixed)fixed=state.guide;assert.deepEqual(state.guide,fixed);assert(state.emphasis>0);await p.locator('#next').click();checked++;
  }}}
  assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);await p.close();console.log('voices',width,'all roles and steps passed');
 }
 await b.close();console.log(JSON.stringify({personalityLines:Object.values(voices).flatMap(v=>Object.values(v).flat()).length,renderedStates:checked,businessRequests:0}));
})().catch(e=>{console.error(e);process.exit(1)});
