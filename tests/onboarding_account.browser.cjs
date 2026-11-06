// Run with PLAYWRIGHT_MODULE pointing at the locally installed Playwright package.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const base=process.env.ONBOARDING_QA_URL||'http://127.0.0.1:18469';
const folder=process.env.ONBOARDING_QA_ARTIFACTS||'reports/26-11-06/functional-regression/assets';
require('node:fs').mkdirSync(folder,{recursive:true});
const key='ai-closet-stylist-session-v1';
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});let scenarios=0;
 try {
 for(const width of [390,1440]){
  for(const pending of [false,true]){
   const context=await browser.newContext({viewport:{width,height:844}});const page=await context.newPage();
   const posts=[],errors=[];let fail=true,saved=null;
   page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(({key,pending})=>sessionStorage.setItem(key,JSON.stringify(pending?{sex_token:'synthetic-pending',user:{user_name:'账号小夏',user_gender:null}}:{access_token:'synthetic-access',user:{id:'1'}})),{key,pending});
   await page.route('**/stylist-api/**',async route=>{
    const request=route.request(),path=new URL(request.url()).pathname;
    if(request.method()!=='GET')posts.push({path,body:request.postDataJSON()});
    if(path.endsWith('complete-gender'))return route.fulfill({json:{access_token:'synthetic-completed',user:{id:'1'}}});
    if(path.endsWith('companion-profile')&&request.method()==='GET')return route.fulfill({json:{profile:saved||{user_name:'旧称呼',user_gender:'男',agent_name:'',assistant_persona:'male_calm_v1',color_scheme:'system'},account:{user_name:'账号小夏',user_gender:'女'}}});
    if(path.endsWith('companion-profile')&&request.method()==='PUT'){
     if(fail){fail=false;return route.fulfill({status:502,json:{message:'模拟保存失败，草稿保留'}});}
     const {account_fields,...profile}=request.postDataJSON();saved=profile;return route.fulfill({json:{profile}});
    }
    return route.fulfill({json:{}});
   });
   await page.goto(base+'/app/?design=yijian&screen=onboarding');await page.locator('#name').waitFor();
   await page.waitForFunction(()=>!document.querySelector('#next').disabled || document.querySelector('#name').value==='账号小夏');
   assert.equal(await page.locator('#name').inputValue(),'账号小夏');
   if(!pending)assert.equal(await page.locator('#screen .chips button[aria-pressed=true]').textContent(),'女');
   if(pending)await page.locator('#screen .chips button').filter({hasText:'女'}).click();
   if(!pending)await page.screenshot({path:`${folder}/onboarding-account-after-${width}.png`});
   await page.locator('#name').fill('新昵称');await page.locator('#next').click();
   await page.locator('.roles .choice').first().click();await page.locator('#next').click();
   await page.locator('#back').click();await page.locator('#back').click();assert.equal(await page.locator('#name').inputValue(),'新昵称');
   await page.locator('#next').click();await page.locator('#next').click();
   await page.locator('#skip').click();await page.locator('#skip').click();
   assert.equal(posts.length,0,'No step may write before final action');
   await page.locator('.start-action').last().click();
   await page.waitForFunction(()=>!document.querySelector('#next').disabled);
   assert.equal(posts.filter(r=>r.path.endsWith('companion-profile')).length,1);
   assert.equal(posts.filter(r=>r.path.endsWith('complete-gender')).length,pending?1:0);
   // Failure remains on final page; retries use the completed session, not the consumed sex_token.
   assert.match(page.url(),/screen=onboarding/);
   await page.locator('.start-action').last().click();await page.waitForURL(/#home\/agent$/);
   assert.equal(posts.filter(r=>r.path.endsWith('companion-profile')).length,2);
   assert.equal(posts.filter(r=>r.path.endsWith('complete-gender')).length,pending?1:0);
   assert.equal(saved.user_name,'新昵称');assert.equal(saved.user_gender,'女');
   assert.deepEqual(posts.filter(r=>r.path.endsWith('companion-profile'))[0].body.account_fields,['user_name','user_gender']);
   assert.deepEqual(errors,[]);scenarios++;await context.close();
  }
 }
 // Empty authoritative values do not inherit an old PostgreSQL name/gender.
 {const context=await browser.newContext();const p=await context.newPage();await p.addInitScript(key=>{if(!sessionStorage.getItem(key))sessionStorage.setItem(key,JSON.stringify({access_token:'synthetic-access',user:{id:'1'}}));},key);
 await p.route('**/stylist-api/**',r=>r.fulfill({json:{profile:{user_name:'旧称呼',user_gender:'男',agent_name:''},account:{user_name:'',user_gender:null}}}));await p.goto(base+'/app/?design=yijian&screen=onboarding');await p.locator('#name').waitFor();await p.waitForTimeout(150);assert.equal(await p.locator('#name').inputValue(),'');assert.equal(await p.locator('#screen .chips button[aria-pressed=true]').count(),0);await context.close();scenarios++;}
 // A save arriving after account switch must not navigate or overwrite the new session.
 {const context=await browser.newContext();const p=await context.newPage();await p.addInitScript(key=>{if(!sessionStorage.getItem(key))sessionStorage.setItem(key,JSON.stringify({access_token:'synthetic-access',user:{id:'1'}}));},key);let release;const gate=new Promise(r=>release=r);
 await p.route('**/stylist-api/**',async r=>{if(r.request().method()==='PUT'){await gate;return r.fulfill({json:{profile:{agent_name:'衣衣'}}});}return r.fulfill({json:{profile:null,account:{user_name:'账号小夏',user_gender:'女'}}});});await p.goto(base+'/app/?design=yijian&screen=onboarding');await p.waitForFunction(()=>!document.querySelector('#next').disabled);await p.locator('#next').click();await p.locator('.roles .choice').first().click();await p.locator('#next').click();await p.locator('#skip').click();await p.locator('#skip').click();await p.locator('.start-action').last().click();await p.evaluate(key=>sessionStorage.setItem(key,JSON.stringify({access_token:'different-account'})),key);release();await p.waitForURL('**/app/?design=yijian&screen=login');assert.equal(await p.evaluate(key=>JSON.parse(sessionStorage.getItem(key)).access_token,key),'different-account');await context.close();scenarios++;}
 for(const scheme of ['companion','system']){
  const context=await browser.newContext({viewport:{width:390,height:844}});const p=await context.newPage();let gender='女';
  await p.addInitScript(key=>{if(!sessionStorage.getItem(key))sessionStorage.setItem(key,JSON.stringify({access_token:'synthetic-access',user:{id:'1'}}));},key);
  await p.route('**/stylist-api/**',r=>r.fulfill({json:{profile:{user_name:'账号小夏',user_gender:gender,agent_name:'衣衣',assistant_persona:'male_calm_v1',color_scheme:scheme}}}));
  await p.goto(base+'/app/?design=yijian#home/agent');await p.waitForFunction(s=>document.documentElement.dataset.appPalette===(s==='system'?'system':'female'),scheme);
  await p.waitForFunction(()=>window.CompanionSettings?.getProfile()?.user_gender==='女');gender='男';await p.evaluate(()=>window.dispatchEvent(new Event('focus')));
  await p.waitForFunction(s=>document.documentElement.dataset.appPalette===(s==='system'?'system':'male'),scheme);await p.waitForFunction(()=>window.CompanionSettings.getProfile().user_gender==='男');
  assert.equal(await p.evaluate(()=>CompanionSettings.getProfile().assistant_persona),'male_calm_v1');
  if(scheme==='system'){await p.evaluate(()=>CompanionSettings.open());await p.locator('#companion-dialog').waitFor();await p.screenshot({path:folder+'/account-palette-label-after.png'});}
  await context.close();scenarios++;
 }
 console.log(JSON.stringify({passed:scenarios,realAccountWrites:0,paidImages:0}));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
