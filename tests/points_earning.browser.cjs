const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');
const base=process.env.POINTS_QA_URL||'http://127.0.0.1:18470',folder='reports/26-11-06/change-log/docs/assets';fs.mkdirSync(folder,{recursive:true});
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});let passed=0;
 try{
 for(const [width,height,scheme,gender] of [[390,844,'system','女'],[320,640,'system','男'],[1440,1000,'system','女'],[390,844,'companion','女'],[390,844,'companion','男']]){
  const context=await browser.newContext({viewport:{width,height}}),p=await context.newPage();let signed=false,balance=1280,claims=0,failMilestones=false,claimFail=false,role='male_calm_v1',vipInfo={is_vip:false},failProfile=false,gate=null;const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.addInitScript(()=>{sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'qa-points-a',user:{id:'1'}}));for(const t of ['upload','profile','memory','chat'])localStorage.setItem(`closet-guide:v2:user:1:${t}`,'seen');});
  await p.route('**/stylist-api/**',async route=>{const r=route.request(),path=new URL(r.url()).pathname;let body={data:{list:[],pagination:{total:0}}};
   if(path.endsWith('companion-profile'))body={profile:{user_name:'小夏',user_gender:gender,agent_name:'衣衣',assistant_persona:role,color_scheme:scheme}};
   else if(path==='/stylist-api/memories')body={entries:[],enabled:true,revision:0};
   else if(path==='/stylist-api/app/profile'){if(failProfile)return route.fulfill({status:502,json:{message:'模拟会员读取失败'}});body={data:{nick_name:'小夏',vip_info:vipInfo}};}
   else if((path.endsWith('/twins')||path.includes('/twins/overview')))body={custom_twin:null,profile:{gender:'female'},system_twins:[]};
   else if(path.endsWith('/points'))body={data:{total_available:balance}};
   else if(path.endsWith('/checkin')){if(r.method()==='POST'){claims++;if(gate)await gate;signed=true;balance=1290;if(claimFail){claimFail=false;return route.fulfill({status:502,json:{message:'模拟回执丢失'}});}body={data:{granted:true,points_added:10}};}else body={data:{signed,daily_points:10,total_days:3,days:[]}};}
   else if(path.endsWith('/milestones')){if(failMilestones)return route.fulfill({status:502,json:{message:'模拟任务读取失败'}});body={data:{current_item_count:12,tiers:[{level:1,threshold:5,reward:30,granted:true},{level:2,threshold:20,reward:100,granted:false},{level:3,threshold:50,reward:300,granted:false}]}};}
   return route.fulfill({json:body});
  });
  await p.goto(base+'/app/?design=yijian#profile');await p.locator('.y-account-earn').waitFor();
  if(width===390&&scheme==='system')await p.screenshot({path:folder+'/earn-points-entry-after.png'});
  await p.locator('.y-account-earn').click();await p.waitForFunction(()=>document.querySelector('.pe-balance-value')?.textContent==='1,280');
  assert.equal(claims,0);assert.equal(await p.locator('.preview-message:not([hidden])').count(),0);assert.equal(await p.locator('.pe-task').count(),4);assert.equal(await p.locator('.pe-wardrobe .pe-action:disabled').count(),1);assert.match(await p.locator('.pe-wardrobe').textContent(),/12 \/ 20 件/);
  assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await p.screenshot({path:`${folder}/earn-points-page-${width}-${scheme}-${gender==='女'?'female':'male'}.png`});

  assert.equal(await p.locator('.pe-tip-link').count(),2);await p.locator('.pe-purchase-tip').scrollIntoViewIfNeeded();
  if(scheme==='system')await p.screenshot({path:`${folder}/earn-points-purchase-after-${width}.png`});
  for(const group of ['points','member']){await p.locator(`[data-purchase=${group}]`).click();await p.waitForFunction(group=>document.querySelector('#sku-center-tab-'+group)?.getAttribute('aria-selected')==='true',group);assert.equal(claims,0);await p.locator('.sku-center-back').click();await p.waitForFunction(()=>document.querySelector('.pe-balance-value')?.textContent==='1,280');await p.locator('.pe-tip-link').first().waitFor();}
  if(width===390&&scheme==='system'){
   for(const [info,expected] of [[{is_vip:true,vip_type:3},'去续费'],[{is_vip:true,vip_type:1,is_lifetime_vip:true},'查看权益'],[{is_vip:false},'去开通']]){vipInfo=info;await p.locator('.pe-refresh').click();await p.waitForFunction(expected=>document.querySelector('[data-purchase=member] .pe-tip-cta')?.textContent===expected+'›',expected);}
   failProfile=true;await p.locator('.pe-refresh').click();await p.waitForFunction(()=>document.querySelector('[data-purchase=member]').dataset.membershipState==='unknown'&&!document.querySelector('.pe-refresh').disabled);assert.equal(await p.locator('[data-purchase=member] .pe-tip-cta').textContent(),'查看会员›');failProfile=false;await p.locator('.pe-refresh').click();await p.waitForFunction(()=>document.querySelector('[data-purchase=member]').dataset.membershipState==='inactive');
   let release;gate=new Promise(r=>release=r);await p.locator('[data-claim]').evaluate(b=>{b.click();b.click();});await p.waitForFunction(()=>document.querySelector('[data-claim]').disabled);assert.equal(claims,1);assert.equal(await p.locator('.pe-balance-value').textContent(),'1,280');release();
   await p.waitForFunction(()=>document.querySelector('.pe-balance-value').textContent==='1,290');assert.equal(claims,1);assert.equal(await p.locator('[data-claim]').textContent(),'已收下');
   signed=false;balance=1280;await p.locator('.pe-refresh').click();await p.waitForFunction(()=>document.querySelector('[data-claim]')?.textContent==='收下心意');claimFail=true;await p.locator('[data-claim]').click();await p.waitForFunction(()=>document.querySelector('[data-claim]')?.textContent==='刷新确认');assert.equal(claims,2);await p.locator('[data-claim]').click();await p.waitForFunction(()=>document.querySelector('[data-claim]')?.textContent==='已收下');assert.equal(claims,2);
   for(const selected of ['female_sweet_v1','female_warm_v1','female_regal_v1','male_artistic_v1','male_calm_v1','male_confident_v1']){role=selected;await p.locator('.pe-refresh').click();await p.waitForFunction(role=>document.querySelector('.pe-letter-art').dataset.persona===role,role);assert.equal(await p.locator('.pe-letter-art').count(),1);}
   failMilestones=true;await p.locator('.pe-refresh').click();await p.locator('.pe-task-error').waitFor();assert.equal(await p.locator('[data-claim]').textContent(),'已收下');failMilestones=false;await p.getByRole('button',{name:'重新读取',exact:true}).click();await p.waitForFunction(()=>document.querySelectorAll('.pe-wardrobe .pe-task').length===3);
   await p.evaluate(()=>{sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'qa-points-b',user:{id:'2'}}));window.dispatchEvent(new Event('yijian-session-change'));});await p.waitForTimeout(100);assert.equal(await p.locator('.pe-balance-value').count(),0);
  }
  assert.deepEqual(errors,[]);passed++;await context.close();
 }
 // Guest sees the page and a login action without any reward API requests.
 {const context=await browser.newContext({viewport:{width:390,height:844}}),p=await context.newPage();let requests=0;
 await p.addInitScript(()=>{for(const t of ['upload','profile','memory','chat'])localStorage.setItem(`closet-guide:v2:guest:${t}`,'seen');});await p.route('**/stylist-api/**',r=>{requests++;return r.fulfill({json:{data:{list:[]}}});});await p.goto(base+'/app/?design=yijian#profile');await p.locator('.y-account-earn').click();await p.locator('.points-earning').waitFor();assert.equal(await p.locator('.points-earning .pe-action').textContent(),'登录衣橱');assert.equal(requests,0);await context.close();passed++;}
 console.log(JSON.stringify({passed,realClaims:0,realUploads:0}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
