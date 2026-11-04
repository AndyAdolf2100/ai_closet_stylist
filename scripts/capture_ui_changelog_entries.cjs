const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '/tmp/stylist-three-lines-20261102/node_modules/playwright');
const { captureMarked } = require(process.env.RED_CIRCLE_CAPTURE || require('node:path').join(process.env.CODEX_HOME || require('node:path').join(require('node:os').homedir(), '.codex'), 'skills/red-circle-docs/scripts/capture_marked.cjs'));
const assert = require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'chrome'});
 const page=await browser.newPage({viewport:{width:393,height:900},deviceScaleFactor:1});
 await page.addInitScript(()=>sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'documentation-mock',user:{id:'documentation-fixture'}})));
 await page.route('**/stylist-api/**',route=>{
  const pathname=new URL(route.request().url()).pathname;
  let json={data:{list:[]}};
  if(pathname.endsWith('/companion-profile'))json={profile:{user_name:'示例用户',user_gender:'女',agent_name:'衣衣',assistant_persona:'male_calm_v1'}};
  if(pathname.endsWith('/conversations'))json=[];
  return route.fulfill({json});
 });
 await page.goto('http://127.0.0.1:8466/app/?design=yijian');
 await page.locator('.y-home-city-button').waitFor();
 await page.waitForTimeout(350);
 const base='docs/assets/ui-changes-2026-11-04/24-';
 for(const [id,selector] of [['001','.y-home-city-button'],['003','.y-brand'],['004','.agent-orb']]){
  await captureMarked(page,base+`ui-${id}-current.png`,[selector]);
  assert.equal(await page.locator('svg[id^="red-circle-docs-"]').count(),0);
 }
 await page.locator('.agent-orb').click();
 await page.locator('#history-dialog[open] #history-title').waitFor();
 await page.waitForTimeout(300);
 await page.evaluate(()=>document.querySelector('#companion-notification')?.remove());
 await captureMarked(page,base+'ui-005-current.png',['#history-title']);
 assert.equal(await page.locator('svg[id^="red-circle-docs-"]').count(),0);
 await browser.close();
 console.log('PASS four current screenshots, one target per image, native-dialog overlay, marker cleanup');
})().catch(error=>{console.error(error);process.exit(1)});
