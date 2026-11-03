const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 require('node:fs').mkdirSync('var/closet-app-parity', {recursive:true});
 const sizes=[[393,852],[320,568],[844,390],[768,1024],[1440,900]];
 let checks=0;
 for(const [width,height] of sizes){
 const context=await browser.newContext({viewport:{width,height}});const page=await context.newPage();
 const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'synthetic-fixture',user:{id:'fixture'}})));
 await page.route('**/stylist-api/**',async route=>{
 const path=new URL(route.request().url()).pathname;
 const payload=path.endsWith('/app/profile')?{nickname:'界面验收',vip_info:{total_points:200}}:path.endsWith('/app/album')||path.endsWith('/app/memories')?{items:[],has_more:false}:path.includes('/app/')?{list:[],page:{total:0}}:path.endsWith('/companion-profile')?{profile:{version:0},version:0}:path.endsWith('/conversations')?{conversations:[]}:{};
 await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(path.includes('/app/')?{data:payload}:payload)});
 });
 await page.goto((process.env.STYLIST_APP_URL || 'http://127.0.0.1:8478') + '/app/');await page.getByText('暂无图像',{exact:true}).waitFor();
 for(const tab of ['home','wardrobe','profile']){
 await page.locator(`[data-tab="${tab}"]`).click();await page.waitForTimeout(200);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));checks++;
 const bad=await page.locator(`.page:not([hidden]) img`).evaluateAll(nodes=>nodes.filter(x=>x.src&&!x.complete||x.complete&&x.src&&x.naturalWidth===0).map(x=>x.src));assert.deepEqual(bad,[]);checks++;
 await page.screenshot({path:`var/closet-app-parity/${tab}-${width}x${height}.png`,fullPage:true});
 }
 await page.locator('#create-toggle').click();assert(await page.locator('#create-overlay').isVisible());checks++;
 await page.screenshot({path:`var/closet-app-parity/create-${width}x${height}.png`});
 await page.keyboard.press('Escape');assert(await page.locator('#create-overlay').isHidden());checks++;
 await page.locator('[data-detail="settings"]').click();await page.getByRole('button',{name:'称呼与形象 ›',exact:true}).click();
 await page.frameLocator('#agent-frame').locator('#companion-dialog').waitFor({state:'visible'});checks++;
 await page.locator('#agent-back').click();assert(await page.locator('#agent-page').isHidden());checks++;
 assert(await page.locator('#detail-page').isVisible()); await page.locator('#detail-back').click(); checks++;
 // Agent document must survive leaving and re-entering the shell.
 await page.evaluate(()=>document.getElementById('agent-frame').contentWindow.__retainedFixture=true);
 await page.locator('#create-toggle').click();await page.locator('[data-agent="chat"]').click();
 assert(await page.evaluate(()=>document.getElementById('agent-frame').contentWindow.__retainedFixture));checks++;
 assert.deepEqual(errors,[]);checks++;
 await context.close();
 }
 // Loaded data, pagination and account replacement use synthetic fixtures only.
 const context=await browser.newContext({viewport:{width:393,height:852}}), page=await context.newPage();
 await page.addInitScript(()=>sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'account-a',user:{id:'a'}})));
 let oldProfileStarted=false;
 await page.route('**/stylist-api/app/**',async route=>{
   const u=new URL(route.request().url()), section=u.pathname.split('/').at(-1), owner=route.request().headers().authorization;
   let data={list:[],items:[]};
   if(section==='album') { const second=u.searchParams.get('page')==='2'; data={items:[{title:owner.endsWith('account-b')?'B的造型':second?'第二页造型':'A的造型',fitting_image_url:'/static/closet-app/assets/home_album_empty.png'}],has_more:!second}; }
   if(section==='profile') { data={nick_name:owner.endsWith('account-b')?'账号B':'迟到的账号A',vip_info:{total_points:20}}; if(owner.endsWith('account-a')){oldProfileStarted=true; await new Promise(r=>setTimeout(r,600));} }
   try { await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({data})}); } catch {}
 });
 await page.goto((process.env.STYLIST_APP_URL || 'http://127.0.0.1:8478')+'/app/');
 await page.getByRole('heading',{name:'A的造型',exact:true}).waitFor();
 await page.getByRole('button',{name:'加载更多',exact:true}).click();
 await page.getByRole('heading',{name:'第二页造型',exact:true}).waitFor();checks++;
 await page.locator('[data-tab="profile"]').click();
 for(let i=0;i<20&&!oldProfileStarted;i++)await page.waitForTimeout(20);
 assert(oldProfileStarted);
 await page.evaluate(()=>{sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'account-b',user:{id:'b'}}));window.dispatchEvent(new StorageEvent('storage',{key:'ai-closet-stylist-session-v1'}));});
 await page.getByRole('heading',{name:'账号B',exact:true}).waitFor(); await page.waitForTimeout(750);
 assert.equal(await page.locator('#account-name').textContent(),'账号B');checks++;
 await page.locator('[data-tab="home"]').click(); await page.getByRole('heading',{name:'B的造型',exact:true}).waitFor();
 assert.equal(await page.getByText('A的造型',{exact:true}).count(),0);checks++;
 await context.close();
 await browser.close();console.log(`${checks} browser checks passed`);
})().catch(e=>{console.error(e);process.exit(1)});
