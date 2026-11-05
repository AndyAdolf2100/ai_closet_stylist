const{chromium}=require(process.env.PLAYWRIGHT_MODULE||'/tmp/stylist-three-lines-20261102/node_modules/playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');
const {captureMarked}=require('/Users/duxiao/.codex/skills/red-circle-docs/scripts/capture_marked.cjs');
const reportDate=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()).slice(2);
const base=process.env.GUIDE_APP_URL||'http://127.0.0.1:8466',shots=process.env.GUIDE_REPORT_DIR||`reports/${reportDate}/change-log/docs/assets/first-visit`;fs.mkdirSync(shots,{recursive:true});
(async()=>{
 const b=await chromium.launch({channel:'chrome'});let stepsChecked=0;
 for(const[width,height]of[[320,740],[393,852],[1440,1000]]){
  const context=await b.newContext({viewport:{width,height}}),p=await context.newPage();let errors=[],writes=[],business=[];p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/stylist-api/'))business.push(r.url());if(!['GET','HEAD'].includes(r.method()))writes.push(r.method()+' '+r.url())});
  await p.goto(base+'/static/closet-app/first-visit/index.html?color=system');const counts=await p.evaluate(()=>Object.fromEntries(Object.entries(tours).map(([t,rows])=>[t,rows.length])));let fixed;
  for(const[tour,count]of Object.entries(counts)){
   await p.locator(`[data-tour=${tour}]`).click();
   for(let i=0;i<count;i++){
    await p.waitForFunction(()=>document.querySelector('#app-scene').style.visibility==='visible');
    const state=await p.evaluate(()=>{const f=document.querySelector('#app-scene'),d=current(),target=f.contentDocument.querySelector(d[1]),r=target?.getBoundingClientRect();const guide=document.querySelector('.guide').getBoundingClientRect(),spot=document.querySelector('#hotspot').getBoundingClientRect(),stage=document.querySelector('.live-stage').getBoundingClientRect();return{target:d[1],visible:!!r?.width&&!!r?.height,rect:[guide.x,guide.y,guide.width,guide.height],inside:spot.top>=stage.top-1&&spot.bottom<=stage.bottom+1,overflow:document.querySelector('.speech').scrollHeight>document.querySelector('.speech').clientHeight+1,scripts:f.contentDocument.scripts.length,replies:document.querySelectorAll('#user-line,.reply-choice').length,emphasis:document.querySelectorAll('#line strong').length,stamp:f.contentDocument.querySelector('meta[name=guide-captured-at]')?.content,scene:d[0]}});
    assert(state.visible,`${width} ${tour} ${i}: missing ${state.target}`);if(!fixed)fixed=state.rect;assert.deepEqual(state.rect,fixed);assert(state.inside,`${width} ${tour} ${i}: hotspot outside stage ${JSON.stringify(state)}`);assert(!state.overflow,`${width} ${tour} ${i}: text overflow`);assert.equal(state.scripts,0);assert.equal(state.replies,0);assert(state.emphasis>0,`${width} ${tour} ${i}: no feature emphasis`);assert(state.stamp);
    if(width===393&&(['upload-preview','generation-quote','tryon-quote','tryon-result'].includes(state.scene)||tour==='profile'&&i===0||tour==='memory'&&i===0||tour==='chat'&&[0,3,7].includes(i)))await captureMarked(p,`${shots}/${tour}-${i}-after.png`,['#line']);
    await p.locator('#next').click();stepsChecked++;
   }
  }
  assert.deepEqual(business,[]);assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);await context.close();
 }
 console.log('Standalone:',stepsChecked,'steps, latest captures, emphasized features, stable geometry, zero business requests');
 for(const[width,height]of[[320,740],[393,852],[1440,1000]]){
  const context=await b.newContext({viewport:{width,height}}),p=await context.newPage();p.setDefaultTimeout(10000);let errors=[],writes=[];p.on('pageerror',e=>errors.push(e.message));
  await p.addInitScript(()=>{if(!sessionStorage.getItem('ai-closet-stylist-session-v1'))sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'guide-fixture',user:{id:'guide-A'}}))});
  await p.route('**/stylist-api/**',r=>{const pathname=new URL(r.request().url()).pathname;if(r.request().method()!=='GET')writes.push(pathname);let json={data:{list:[],items:[],total_count:0}};if(pathname.endsWith('/companion-profile'))json={profile:{user_name:'示例用户',user_gender:'女',agent_name:'衣衣',assistant_persona:'male_calm_v1',color_scheme:'system'}};if(pathname.endsWith('/twins'))json={need_gender:false,system_twins:[],custom_twin:null,available_points:500};if(pathname.endsWith('/memories'))json={entries:[],enabled:true,revision:0};if(pathname.endsWith('/app/checkin'))json={data:{signed:false,days:[]}};if(['/conversations','/media','/images'].some(x=>pathname.endsWith(x)))json=[];return r.fulfill({json})});
  await p.goto(base+'/app/?design=yijian');const dialog=p.locator('#first-visit-guide'),frame=p.frameLocator('#first-visit-guide iframe');
  async function expectTour(title){await dialog.waitFor({state:'visible'});assert.equal(await dialog.getAttribute('aria-label'),title);await p.waitForFunction(()=>document.querySelector('#first-visit-guide iframe').contentDocument?.querySelector('#app-scene')?.style.visibility==='visible')}
  async function close(){await frame.locator('#skip').click();await dialog.waitFor({state:'hidden'})}
  await expectTour('添加单品到合成试穿');await close();await p.reload();await p.locator('.y-talk').waitFor();await p.waitForTimeout(100);assert(!await dialog.isVisible());
  await p.locator('[data-tab=profile]').click();await expectTour('我的页面');if(width===393)await captureMarked(p,shots+'/app-profile-after.png');await close();
  assert(!await p.locator('#memory-dialog').isVisible());assert.equal(await p.evaluate(()=>localStorage.getItem('closet-guide:v2:user:guide-A:memory')),null);
  await p.locator('.memory-card').click();await p.locator('#memory-dialog').waitFor({state:'visible'});await expectTour('我们的手记');if(width===393)await captureMarked(p,shots+'/app-memory-after.png');await frame.locator('#skip').click();await dialog.waitFor({state:'hidden'});assert(await p.locator('#memory-dialog').isVisible());await p.locator('#memory-close').click();
  await p.locator('.memory-card').click();await p.locator('#memory-dialog').waitFor({state:'visible'});await p.waitForTimeout(100);assert(!await dialog.isVisible());await p.locator('#memory-close').click();
  await p.locator('[data-tab=home]').click();await p.locator('.y-talk').click();await p.locator('#message').waitFor();await expectTour('开始对话');await close();
  // Replay all four; neither a synthetic parent message nor another window may dismiss the guide.
  for(const tour of ['upload','profile','memory','chat']){await p.evaluate(t=>dispatchEvent(new CustomEvent('closet-guide-open',{detail:t})),tour);await dialog.waitFor({state:'visible'});await close()}
  await p.evaluate(()=>dispatchEvent(new CustomEvent('closet-guide-open',{detail:'upload'})));await dialog.waitFor({state:'visible'});await p.evaluate(()=>{sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'guide-fixture-B',user:{id:'guide-B'}}));dispatchEvent(new Event('yijian-session-change'))});await p.waitForTimeout(150);if(await dialog.isVisible())assert.notEqual(await dialog.getAttribute('aria-label'),'添加单品到合成试穿');assert.equal(await p.evaluate(()=>localStorage.getItem('closet-guide:v2:user:guide-B:upload')),null);
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);await context.close();console.log('Integrated:',width,'profile overview, memory-on-click and return, replay, account isolation, zero writes');
 }
 await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
