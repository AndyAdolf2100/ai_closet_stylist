// Capture the current guide as it actually renders; no business APIs and no user profile.
const{chromium}=require(process.env.PLAYWRIGHT_MODULE||'/tmp/stylist-three-lines-20261102/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path');
const args=new Set(process.argv.slice(2)),base=process.env.GUIDE_APP_URL||'http://127.0.0.1:8466';
const date=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()).slice(2);
const report=process.env.GUIDE_REPORT_DIR||`reports/${date}/change-log/docs/assets/first-visit`,phase=process.env.GUIDE_CAPTURE_PHASE||'after';
(async()=>{
 const browser=await chromium.launch({channel:'chrome'}),p=await browser.newPage({viewport:{width:393,height:852}});let forbidden=[];p.on('request',r=>{if(r.url().includes('/stylist-api/'))forbidden.push(r.url())});
 await p.goto(base+'/static/closet-app/first-visit/index.html?color=system');const config=await p.evaluate(()=>({tours:Object.fromEntries(Object.entries(tours).map(([key,rows])=>[key,rows.length])),roles:roles.map(r=>r.id)}));
 const rolesToCapture=args.has('--all-roles')?config.roles:[process.env.GUIDE_ROLE||'male_calm_v1'];const dest=path.join(report,phase);fs.mkdirSync(dest,{recursive:true});const shots=[];
 for(const role of rolesToCapture){await p.selectOption('#role',role,{force:true});for(const[tour,count]of Object.entries(config.tours)){await p.locator(`[data-tour=${tour}]`).click();const limit=args.has('--all-steps')?count:1;for(let i=0;i<limit;i++){
  await p.waitForFunction(()=>document.querySelector('#app-scene').style.visibility==='visible');await p.waitForFunction(()=>{const img=document.querySelector('#app-scene').contentDocument?.querySelector('.sku-center-art');return !img||(img.dataset.persona===state.role&&img.complete&&img.naturalWidth>0&&img.style.visibility!=='hidden')});const name=`${role}-${tour}-${String(i+1).padStart(2,'0')}.png`,target=path.join(dest,name);await p.screenshot({path:target});shots.push({role,tour,step:i+1,file:name,text:await p.locator('#line').innerText()});await p.locator('#next').click();
 }}}
 if(forbidden.length)throw Error('Unexpected business requests during screenshot capture');fs.writeFileSync(path.join(dest,'manifest.json'),JSON.stringify({captured_at:new Date().toISOString(),source:base,phase,shots},null,2)+'\n');await browser.close();console.log(shots.length+' current screenshots saved to '+dest);
})().catch(e=>{console.error(e);process.exit(1)});
