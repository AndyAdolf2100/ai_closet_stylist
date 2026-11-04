const{chromium}=require(process.env.PLAYWRIGHT_MODULE||'/tmp/stylist-three-lines-20261102/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'chrome'}),page=await browser.newPage({viewport:{width:393,height:1100},deviceScaleFactor:1});
 page.setDefaultTimeout(8000);let resolves=0;
 await page.addInitScript(()=>{
  sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'documentation-mock-location',user:{id:'documentation-fixture'}}));
  window.geoCalls=0;Object.defineProperty(navigator,'geolocation',{value:{getCurrentPosition(ok,no){window.geoCalls++;window.completeLocation=ok;window.failLocation=no;}}});
 });
 await page.route('**/stylist-api/**',route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/companion-profile'))return route.fulfill({json:{profile:{user_name:'示例用户',user_gender:'女',agent_name:''}}});
  if(path.endsWith('/location/resolve')){resolves++;assert.equal(route.request().method(),'POST');return route.fulfill({json:{city_name:'上海市',province_name:'上海市'}})}
  throw Error('Unexpected business request: '+path);
 });
 await page.goto('http://127.0.0.1:8466/static/closet-app/onboarding/index.html?live=1');
 await page.waitForFunction(()=>loaded);await page.evaluate(()=>{Object.assign(draft,{name:'示例用户',gender:'女',agent:'衣衣',role:'male_calm_v1'});step=4;render()});
 const card=page.locator('.onboarding-location'),button=card.getByRole('button',{name:'开启定位',exact:true});await button.waitFor();
 async function shot(name,selector){
  await page.evaluate(()=>document.querySelector('#documentation-state-circle')?.remove());
  if(!await page.locator('.onboarding-city-dialog').count())await card.scrollIntoViewIfNeeded();
  await page.waitForTimeout(350);
  await page.evaluate(selector=>{
   const target=document.querySelector(selector),r=target.getBoundingClientRect(),ns='http://www.w3.org/2000/svg';
   const svg=document.createElementNS(ns,'svg');svg.id='documentation-state-circle';svg.setAttribute('width',innerWidth);svg.setAttribute('height',innerHeight);svg.style='position:fixed;inset:0;z-index:2147483647;pointer-events:none';
   const circle=document.createElementNS(ns,'ellipse');for(const[k,v]of Object.entries({cx:r.x+r.width/2,cy:r.y+r.height/2,rx:r.width/2+5,ry:r.height/2+7,fill:'none',stroke:'#e12626','stroke-width':3}))circle.setAttribute(k,v);svg.append(circle);(document.querySelector('dialog[open]')||document.body).append(svg);
  },selector);
  await page.screenshot({path:`docs/assets/ui-changes-2026-11-04/17-city-after-${name}.png`});
  await page.evaluate(()=>document.querySelector('#documentation-state-circle')?.remove());
 }
 assert.equal(await page.evaluate(()=>geoCalls),0);await shot('01-idle','.onboarding-location-enable');
 await button.click();await page.waitForFunction(()=>geoCalls===1);assert.equal(await page.evaluate(()=>sessionStorage.getItem('ai-closet-stylist-city-v1')),null);
 await shot('02-waiting','.onboarding-city-status');
 // Public example coordinates; no device GPS or real browser permission prompt.
 await page.evaluate(()=>completeLocation({coords:{latitude:31.2,longitude:121.4}}));
 await page.getByText('找到上海市啦，请确认后使用。',{exact:true}).waitFor();assert.equal(resolves,1);assert.equal(await page.evaluate(()=>sessionStorage.getItem('ai-closet-stylist-city-v1')),null);
 await shot('03-located','.onboarding-city-status');
 await page.getByRole('button',{name:'确认城市',exact:true}).click();assert.equal(await page.evaluate(()=>JSON.parse(sessionStorage.getItem('ai-closet-stylist-city-v1')).city_name),'上海市');
 await shot('04-confirmed','.onboarding-location [role=status]');
 await button.click();await page.waitForFunction(()=>geoCalls===2);await page.evaluate(()=>failLocation({code:1}));
 await page.getByText('定位未开启也没关系，手动选一座城市吧。',{exact:true}).waitFor();await shot('05-denied','.onboarding-city-status');
 await page.getByRole('button',{name:'重新定位',exact:true}).click();await page.waitForFunction(()=>geoCalls===3);await page.evaluate(()=>failLocation({code:3}));
 await page.getByText('定位等得有点久，可以再试一次，或手动选择。',{exact:true}).waitFor();await shot('06-timeout','.onboarding-city-status');
 await browser.close();console.log('PASS 6 H5 state screenshots; fixture-only geolocation and resolver, explicit city confirmation verified');
})().catch(error=>{console.error(error);process.exit(1)});
