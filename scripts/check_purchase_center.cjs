// Synthetic catalog rendering/navigation checks; no live account or payment calls.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/tmp/stylist-three-lines-20261102/node_modules/playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');
const {captureMarked}=require('/Users/duxiao/.codex/skills/red-circle-docs/scripts/capture_marked.cjs');
(async()=>{
 const browser=await chromium.launch({channel:'chrome'}),p=await browser.newPage();const errors=[],writes=[];let cases=0;
 p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/stylist-api/')&&!['GET','HEAD'].includes(r.method()))writes.push(r.url())});
 await p.addInitScript(()=>{sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'fixture',user:{id:'fixture'}}));for(const t of ['upload','profile','memory','chat'])localStorage.setItem('closet-guide:v2:user:fixture:'+t,'seen')});
 await p.route('**/stylist-api/**',r=>{const path=new URL(r.request().url()).pathname;return r.fulfill({json:path.endsWith('/companion-profile')?{profile:{user_name:'示例用户',agent_name:'衣衣',assistant_persona:'male_calm_v1'}}:path.endsWith('/memories')?{entries:[]}:path.endsWith('/profile')?{data:{vip_info:{is_vip:1,vip_type:2,total_points:1280}}}:{data:{list:[],items:[]}}})});
 const dest='reports/26-11-05/change-log/docs/assets/';
 for(const [width,height]of [[320,568],[393,852],[1440,900]]){
  await p.setViewportSize({width,height});await p.goto('http://127.0.0.1:8466/app/?design=yijian#profile');await p.locator('.sku-journal').waitFor();
  await p.locator('.points-card [data-detail=membership]').click();const root=p.locator('.sku-details');await root.locator('.sku-center-art').evaluate(i=>i.decode());
  assert.equal(await p.locator('#detail-page>.detail-header').isVisible(),false);assert(await root.locator('.sku-center-back').evaluate(e=>e===document.activeElement));
  assert.deepEqual(await root.locator('[role=tab]').allTextContents(),['会员','积分']);
  assert.equal(await root.locator('.sku-card').count(),4);assert.deepEqual(await root.locator('.sku-product-name').allTextContents(),['SVIP 月卡','SVIP 年卡','SVIP 连续包月','VIP 永久会员']);
  await root.locator('[data-choice=l]').click();assert((await root.locator('.sku-dock').innerText()).includes('299'));
  await root.locator('[role=tab]').first().focus();await p.keyboard.press('ArrowRight');assert.equal(await root.getAttribute('data-group'),'points');assert.equal(await root.locator('.sku-card').count(),3);
  await root.locator('[data-choice=p2]').click();assert((await root.locator('.sku-dock').innerText()).includes('48'));assert.equal(await root.locator('.sku-benefits').count(),0);
  for(const role of ['male_calm_v1','female_sweet_v1']){
   await p.evaluate(role=>window.dispatchEvent(new CustomEvent('companion-profile-change',{detail:{user_name:'示例用户',agent_name:'衣衣',assistant_persona:role}})),role);
   assert.equal(await root.locator('.sku-dock .sku-pay').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(255, 218, 0)');cases++;
  }
  assert(await root.evaluate(e=>e.scrollWidth<=e.clientWidth+1));
  assert(await root.locator('[role=tab]').evaluateAll(es=>es.every(e=>e.getBoundingClientRect().height>=44)));
  await root.locator('.sku-center-tabs [data-group=member]').click();assert.equal(await root.locator('.selected [data-choice]').getAttribute('data-choice'),'l');
  await root.locator('[data-choice=y]').click();await p.locator('#detail-page').evaluate(e=>e.scrollTop=0);await captureMarked(p,`${dest}yellow-member-${width}.png`,width===393?['.sku-center-tabs']:[]);
  await root.locator('.sku-center-tabs [data-group=points]').click();assert.equal(await root.locator('.selected [data-choice]').getAttribute('data-choice'),'p2');
  await captureMarked(p,`${dest}yellow-points-${width}.png`,width===393?['.sku-details .sku-catalog']:[]);
  await root.locator('.sku-dock .sku-pay').click();await p.locator('.sku-payment h2').filter({hasText:'500 积分'}).waitFor();assert(await p.locator('.sku-payment').evaluate(d=>d.matches(':modal')));await p.keyboard.press('Escape');assert.equal(await p.locator('.sku-payment').count(),0);assert.equal(await root.getAttribute('data-group'),'points');
  await root.locator('.sku-center-back').click();await p.locator('#detail-page').waitFor({state:'hidden'});assert.equal(await p.locator('.sku-journal [data-group=points] .selected .sku-select').textContent(),'500 积分');
  // Browser forward restores the retained detail element and its subscriptions.
  await p.goForward();await root.waitFor();await root.locator('[role=tab]').first().click();assert.equal(await root.locator('.sku-card').count(),4);
  await p.evaluate(()=>window.dispatchEvent(new CustomEvent('yijian-account-loaded',{detail:{vip_info:{is_vip:1,vip_type:5}}})));assert.equal(await root.locator('.sku-card').count(),1);assert.equal(await root.locator('.sku-product-name').textContent(),'SVIP 连续包月');
  await p.evaluate(()=>window.dispatchEvent(new Event('yijian-account-reset')));assert.equal(await root.locator('.sku-card').count(),4);assert.equal(await root.locator('.sku-status').count(),0);assert.equal(await root.locator('.selected [data-choice]').getAttribute('data-choice'),'y');cases++;
 }
 assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);fs.writeFileSync(dest+'yellow-center-check.json',JSON.stringify({cases,errors,writes,synthetic:true},null,2));console.log({cases,errors,writes});await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
