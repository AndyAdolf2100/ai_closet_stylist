const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/tmp/stylist-three-lines-20261102/node_modules/playwright');const assert=require('node:assert/strict');const fs=require('node:fs');
(async()=>{const b=await chromium.launch({channel:'chrome'}),p=await b.newPage();const roles=['female_sweet_v1','female_warm_v1','female_regal_v1','male_artistic_v1','male_calm_v1','male_confident_v1'];p.setDefaultTimeout(10000);let checks=0;const errors=[],writes=[];p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/stylist-api/')&&r.method()!=='GET')writes.push(r.url())});
await p.addInitScript(()=>{sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'fixture',user:{id:'fixture'}}));for(const t of ['upload','profile','memory','chat'])localStorage.setItem('closet-guide:v2:user:fixture:'+t,'seen')});
await p.route('**/stylist-api/**',r=>r.fulfill({json:r.request().url().includes('companion-profile')?{profile:{user_name:'示例用户',agent_name:'衣衣',assistant_persona:'female_warm_v1',color_scheme:'system'}}:r.request().url().endsWith('memories')?{entries:[]}:{data:{vip_info:{is_vip:1,vip_type:2,total_points:1280},list:[],items:[]}}}));
const dir='reports/26-11-05/change-log/docs/assets/';
for(const width of [320,393,1440]){console.log('viewport',width);
 await p.setViewportSize({width,height:852});await p.goto('http://127.0.0.1:8466/app/?design=yijian#profile');await p.waitForFunction(()=>document.documentElement.dataset.appPalette==='system');await p.locator('.points-card [data-detail=membership]').click();const root=p.locator('.sku-details'),img=root.locator('.sku-center-art');await img.evaluate(i=>i.decode());assert((await img.getAttribute('src')).includes('female_warm_v1'),await img.getAttribute('src'));
 for(const role of roles){console.log('role',role);await p.evaluate(role=>window.dispatchEvent(new CustomEvent('companion-profile-change',{detail:{agent_name:'衣衣',assistant_persona:role,color_scheme:'system'}})),role);
  for(const [index,group]of ['member','points'].entries()){
   await root.locator('[role=tab]').nth(index).click();await img.evaluate(i=>i.decode());assert((await img.getAttribute('src')).endsWith(role+'.png'));assert.equal(await img.evaluate(i=>getComputedStyle(i).visibility),'visible');assert.equal(await p.locator('html').getAttribute('data-app-palette'),'system');assert(await root.evaluate(e=>e.scrollWidth<=e.clientWidth+1));checks++;
   if(width===393){await p.screenshot({path:dir+`system-${role}-${group}.png`});if(group==='member')await root.locator('.sku-center-hero').screenshot({path:dir+`system-banner-${role}.png`});}
  }
 }
 // A response belonging to another account cannot change this user's banner.
 await p.evaluate(()=>dispatchEvent(new CustomEvent('yijian-user-profile',{detail:{ownerToken:'other',profile:{assistant_persona:'female_sweet_v1'}}})));assert((await img.getAttribute('src')).includes('male_confident_v1'));
 await p.evaluate(()=>dispatchEvent(new CustomEvent('companion-profile-change',{detail:{assistant_persona:'unknown',color_scheme:'system'}})));assert((await img.getAttribute('src')).includes('male_calm_v1'));
 await p.evaluate(()=>{sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'new-fixture',user:{id:'new'}}));dispatchEvent(new Event('yijian-session-change'))});await root.waitFor({state:'detached'});
}
// The isolated guide must update its embedded banner with its selected role too.
await p.setViewportSize({width:393,height:852});await p.goto('http://127.0.0.1:8466/static/closet-app/first-visit/index.html?tour=profile&color=system');for(let n=0;n<3;n++)await p.locator('#next').click();
for(const role of roles){await p.selectOption('#role',role);const img=p.frameLocator('#app-scene').locator('.sku-center-art');await p.waitForFunction(role=>document.querySelector('#app-scene').contentDocument?.querySelector('.sku-center-art')?.getAttribute('src').endsWith(role+'.png'),role);await img.evaluate(i=>i.decode());assert.equal(await p.locator('body').getAttribute('data-palette'),'system');checks++;}
assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);fs.writeFileSync(dir+'system-banner-check.json',JSON.stringify({checks,errors,writes},null,2));console.log({checks,errors,writes});await b.close();})().catch(e=>{console.error(e);process.exit(1)});
