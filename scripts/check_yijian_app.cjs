const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 fs.mkdirSync('var/yijian-app',{recursive:true}); let checks=0;
 for(const [width,height] of [[320,568],[393,852],[844,390],[1440,900]]){
  const context=await browser.newContext({viewport:{width,height}}), page=await context.newPage(); const errors=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message)); page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))writes.push(r.url());});
  await page.addInitScript(()=>sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'fixture',user:{id:'fixture'}})));
  await page.route('**/stylist-api/**',async route=>{
   const path=new URL(route.request().url()).pathname;
   const data=path.endsWith('/profile')?{nick_name:'日常体验',vip_info:{total_points:200}}:path.endsWith('/memories')?{items:[]}:path.endsWith('/album')?{items:[],has_more:false}:{list:[],page:{total:0}};
   const payload=path.endsWith('/companion-profile')?{profile:{agent_name:'知夏',assistant_persona:'female_warm_v1',color_scheme:'companion'}}:path.includes('/app/')?{data}:{};
   await route.fulfill({contentType:'application/json',body:JSON.stringify(payload)});
  });
  await page.goto((process.env.STYLIST_APP_URL||'http://127.0.0.1:8478')+'/app/?design=yijian');
  await page.getByRole('button',{name:'和知夏聊聊'}).waitFor(); const avatar=await page.locator('.y-companion-photo').getAttribute('src');
  let initialGeometry;
  for(const palette of ['female','male','system']){
   await page.locator(`[data-palette="${palette}"]`).click();
   assert.equal(await page.locator('html').getAttribute('data-app-palette'),palette);checks++;
   assert.equal(await page.locator('.y-companion-photo').getAttribute('src'),avatar);checks++;
   const geometry=await page.locator('.y-welcome').boundingBox();if(initialGeometry)assert.deepEqual(geometry,initialGeometry);else initialGeometry=geometry;checks++;
   for(const tab of ['home','wardrobe','profile']){
    await page.locator(`[data-tab="${tab}"]`).click();await page.waitForTimeout(100);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));checks++;
    assert.equal(await page.locator('.page:not([hidden]) img').evaluateAll(xs=>xs.filter(x=>x.src&&x.complete&&!x.naturalWidth).length),0);checks++;
    await page.screenshot({path:`var/yijian-app/${palette}-${tab}-${width}.png`,fullPage:true});
   }
   await page.locator('#create-toggle').click(); const last=page.locator('.create-wide').last();await last.scrollIntoViewIfNeeded();
   const box=await last.boundingBox(),bar=await page.locator('.floating-bar').boundingBox();assert(box.y+box.height<=bar.y+1);checks++;
   await page.screenshot({path:`var/yijian-app/${palette}-create-${width}.png`});
   await page.keyboard.press('Escape');assert(await page.locator('#create-overlay').isHidden());checks++;
   await page.locator('[data-tab="home"]').click();await page.evaluate(()=>scrollTo(0,0));
  }
  await page.getByRole('button',{name:'和知夏聊聊'}).click();
  await page.frameLocator('#agent-frame').locator('#message').waitFor(); assert(await page.locator('#agent-page').isVisible());checks++;
  await page.locator('#agent-back').click(); assert(await page.locator('#agent-page').isHidden());checks++;
  await page.reload();assert.equal(await page.locator('html').getAttribute('data-app-palette'),'system');checks++;
  assert.deepEqual(writes,[]); assert.deepEqual(errors,[]);checks+=2;
  await context.close();
 }
 await browser.close();console.log(`${checks} Yijian three-palette checks passed`);
})().catch(e=>{console.error(e);process.exit(1)});
