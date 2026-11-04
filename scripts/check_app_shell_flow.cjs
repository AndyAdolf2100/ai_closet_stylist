// Mock-only integration regression: App routes, back navigation, desktop bounds and account gates.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const b=await chromium.launch({channel:'chrome'});
 for(const width of [320,393,1440]){
  const p=await b.newPage({viewport:{width,height:900}});const errors=[];let profile={user_name:'小夏',user_gender:'女',agent_name:'知夏',assistant_persona:'male_calm_v1'};
  p.on('pageerror',e=>errors.push(e.message));
  await p.route('**/stylist-api/**',r=>{const path=new URL(r.request().url()).pathname;let json={data:{list:[],items:[]}};
   if(path.endsWith('/companion-profile'))json={profile};
   if(path.endsWith('/conversations'))json={conversations:[]};
   if(path.endsWith('/auth/mobile-login'))json={access_token:'shell-fixture',user:{id:'shell'}};
   if(path.endsWith('/twins'))json={system_twins:[],custom_twin:null};
   return r.fulfill({json});
  });
  await p.goto('http://127.0.0.1:8478/app/?design=yijian');
  await p.locator('.y-talk').click();await p.waitForURL('**/app/?design=yijian&screen=login');
  await p.locator('#phone').fill('13800000000');await p.locator('#agree').check();await p.locator('#login').click();
  assert(p.url().endsWith('screen=login#verification'));
  await p.locator('.login-home').click();await p.locator('#phone').waitFor({state:'visible'});assert.equal(await p.locator('#phone').inputValue(),'13800000000');
  await p.waitForTimeout(1000);assert.equal(await p.locator('#login-form').evaluate(e=>getComputedStyle(e).opacity),'1');
  await p.locator('#login').click();await p.locator('#code').fill('123456');await p.locator('#verify').click();
  await p.waitForURL('**/app/?design=yijian');await p.locator('.y-talk').click();await p.locator('#message').waitFor({state:'visible'});
  const rects=await p.evaluate(()=>{const a=document.querySelector('#app').getBoundingClientRect(),c=document.querySelector('#chat-form').getBoundingClientRect();return {left:a.left,right:a.right,bottom:a.bottom,cl:c.left,cr:c.right,cb:c.bottom}});
  assert(rects.cl>=rects.left&&rects.cr<=rects.right&&rects.cb<=rects.bottom+1,JSON.stringify(rects));
  await p.locator('#message').fill('保留这段草稿');await p.locator('#upload-open').click();await p.locator('#y-attachment-options').waitFor({state:'visible'});await p.locator('[data-attachment=photo]').focus();await p.keyboard.press('Escape');assert.equal(await p.locator('#message').inputValue(),'保留这段草稿');
  assert(await p.locator('#agent-page').isVisible());assert(await p.locator('#y-attachment-options').isHidden());await p.locator('#agent-back').click();await p.locator('#agent-page').waitFor({state:'hidden'});
  await p.goto('http://127.0.0.1:8478/app/?design=yijian&screen=onboarding');await p.waitForURL('**/app/?design=yijian');
  // Switching/clearing the account must re-enter login, not reuse the old profile.
  await p.evaluate(()=>{sessionStorage.removeItem('ai-closet-stylist-session-v1');dispatchEvent(new Event('yijian-session-change'))});
  await p.locator('.y-talk').click();await p.waitForURL('**/app/?design=yijian&screen=login');
  assert.deepEqual(errors,[]);console.log(width,'login/back/existing profile/chat/attachment/account reset passed');await p.close();
 }
 await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
