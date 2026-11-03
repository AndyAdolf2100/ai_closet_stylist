const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true}); let checks=0;
 fs.mkdirSync('var/yijian-diary',{recursive:true});
 for(const width of [320,393]){
  const page=await browser.newPage({viewport:{width,height:852}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'fixture',user:{id:'fixture'}})));
  await page.route('**/stylist-api/**',async route=>{
   const path=new URL(route.request().url()).pathname;
   let data={list:[]};
   if(path.endsWith('/album'))data={items:[{title:'午后的一页',description:'合成记录，仅验证页面排版。',finished_at:'2026-11-02T12:00:00+08:00',source_label:'试衣',product_count:4,product_images:Array.from({length:4},()=>({title:'衣物示意',image_url:'/static/closet-app/assets/wardrobe_action_products.png'})),fitting_image_url:'/static/closet-app/assets/home_album_empty.png'}],has_more:false};
   if(path.endsWith('/profile'))data={nick_name:'日常体验',vip_info:{total_points:200}};
   if(path.endsWith('/memories'))data={items:[{memory_id:'a',status:'active',content:'喜欢柔软舒适的面料'},{memory_id:'b',status:'active',content:'周末喜欢轻松一些'}]};
   const body=path.endsWith('/companion-profile')?{profile:{agent_name:'知夏',assistant_persona:'female_warm_v1'}}:{data};
   await route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto((process.env.STYLIST_APP_URL||'http://127.0.0.1:8478')+'/app/?design=yijian');await page.locator('.y-diary-heading').waitFor();
  for(const palette of ['female','male','system']){
   await page.locator(`[data-palette="${palette}"]`).click();
   assert.equal(await page.locator('.y-diary-date').textContent(),'11.02');checks++;
   assert.equal(await page.locator('.album-tile').count(),4);checks++;
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));checks++;
   await page.locator('.album-card').screenshot({path:`var/yijian-diary/${palette}-album-${width}.png`});
   await page.locator('.album-tap').click();assert.equal(await page.locator('#detail-title').textContent(),'午后的一页');checks++;
   await page.locator('#detail-back').click();await page.locator('.album-card').waitFor();
   await page.locator('[data-tab="profile"]').click();await page.getByText('喜欢柔软舒适的面料',{exact:true}).waitFor();
   assert.equal(await page.locator('.y-letter-by').textContent(),'知夏的日常小笺');checks++;
   assert.equal(await page.locator('.y-letter-photo').evaluate(x=>x.src),await page.locator('.y-companion-photo').evaluate(x=>x.src));checks++;
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));checks++;
   await page.screenshot({path:`var/yijian-diary/${palette}-profile-${width}.png`,fullPage:true});
   await page.locator('[data-tab="home"]').click();await page.locator('.album-card').waitFor();await page.evaluate(()=>scrollTo(0,0));
  }
  assert.deepEqual(errors,[]);checks++;await page.close();
 }
 await browser.close();console.log(`${checks} diary and companion-profile checks passed`);
})().catch(e=>{console.error(e);process.exit(1)});
