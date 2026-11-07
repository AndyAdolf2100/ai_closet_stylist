// Actual App components + isolated synthetic HTTP. Never reuse a browser profile or credentials.
const{chromium}=require(process.env.PLAYWRIGHT_MODULE||'/tmp/stylist-three-lines-20261102/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path');
const base=process.env.GUIDE_APP_URL||'http://127.0.0.1:8466',dir='stylist/static/closet-app/first-visit',assets='/static/closet-app/first-visit/assets/';
(async()=>{
 const browser=await chromium.launch({channel:'chrome'}),context=await browser.newContext({viewport:{width:393,height:852}}),p=await context.newPage();p.setDefaultTimeout(10000);
 let custom=false,confirmed=false;const manifest={captured_at:new Date().toISOString(),source:base+'/app/?design=yijian',data:'isolated synthetic fixtures; no real business requests',scenes:[]};
 const pic='https://guide-preview.invalid/portrait.png',resultPic='https://guide-preview.invalid/result.png',shirt='https://guide-preview.invalid/shirt.png',jeans='https://guide-preview.invalid/jeans.png';
 const twin=()=>({need_gender:false,default_confirmed:confirmed,default_twin_key:confirmed?'custom':'system-demo',profile_version:1,profile:{height_cm:165,weight_kg:55,skin_tone:"natural"},selection_version:1,available_points:500,system_twins:[{twin_key:'system-demo',name:'基础试穿形象',image_url:pic}],custom_twin:custom?{name:'我的试穿形象',image_url:pic}:null});
 const garment={action_id:'guide-garment',kind:'garment',status:'completed',result:{result_image_url:shirt,class_name:'上衣',message:'衣物已入柜'}};
 const generated={action_id:'guide-generation',kind:'generation',status:'completed',result:{result_image_url:pic,can_confirm:true,task_id:'guide-task'}};
 const tryon={action_id:'guide-tryon',conversation_id:'guide-conversation',version:1,look_index:0,title:'周末散步',status:'completed',result:{result_image_url:resultPic}};
 const media=[garment,generated];
 await p.addInitScript(()=>{sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'tour-fixture-not-real',user:{id:'tour-fixture'}}));for(const v of ['v1','v2'])for(const tour of ['upload','profile','memory','chat'])localStorage.setItem(`closet-guide:${v}:user:tour-fixture:${tour}`,'seen')});
 await p.route('**/*',async r=>{
  const u=new URL(r.request().url()),pathname=u.pathname,method=r.request().method();
  if(u.hostname==='guide-preview.invalid'){const name={'/portrait.png':'/static/closet-app/assets/private-tryon-portrait-v1.png','/result.png':assets+'tryon-example.png','/shirt.png':assets+'shirt-example.png','/jeans.png':assets+'jeans-example.png','/outfit.png':assets+'outfit-example.png'}[pathname];if(!name)throw Error('Unexpected fixture image '+pathname);return r.fulfill({contentType:'image/png',body:fs.readFileSync('stylist'+name.replace('/static','/static'))})}
  if(u.origin!==base)return r.abort();
  if(!pathname.startsWith('/stylist-api/'))return r.continue();
  let json;
  if(pathname.endsWith('/companion-profile'))json={profile:{user_name:'小禾',user_gender:'女',agent_name:'衣衣',assistant_persona:'male_calm_v1',color_scheme:'companion'}};
  else if(pathname.endsWith('/app/points'))json={data:{total_available:500}};
  else if(pathname.endsWith('/app/profile'))json={data:{nick_name:'小禾',image_url:'/static/closet-app/assets/user_avatar_default_icon.png',vip_info:{is_vip:false,total_points:500}}};
  else if(pathname.endsWith('/memories'))json={entries:[],enabled:true,revision:0};
  else if(pathname.endsWith('/twins/options'))json={height_cm:{min:100,max:230,step:0.1},weight_kg:{min:30,max:150,step:0.1},skin_tone:[{code:'natural',label:'自然肤色'}]};
  else if(pathname.endsWith('/twins'))json=twin();
  else if(pathname.endsWith('/twins/use-candidate')){custom=true;json={ok:true}}
  else if(pathname.endsWith('/twins/default')){confirmed=true;json={ok:true}}
  else if(pathname.endsWith('/media/uploads')){const body=r.request().postDataJSON();json=body.kind==='person'?{action_id:'guide-person',kind:'person',status:'completed',result:{result_image_url:pic,allowed_hat_actions:['none'],message:'照片检查完成'}}:garment}
  else if(pathname.endsWith('/generation-quote'))json={action_id:'guide-generation',points_cost:100};
  else if(pathname==='/stylist-api/media/guide-generation/confirm')json={...generated,status:'processing',result:{}};
  else if(pathname==='/stylist-api/media/guide-generation')json=generated;
  else if(pathname==='/stylist-api/images/quote')json={action_id:'guide-tryon',points_cost:200,item_count:2,title:tryon.title,portrait:{image_url:pic,name:'我的试穿形象'},notices:['本次试穿需要200积分。','人物创建和搭配试穿分别确认积分。']};
  else if(pathname==='/stylist-api/images/guide-tryon/confirm')json={...tryon,status:'processing',result:{}};
  else if(pathname==='/stylist-api/images/guide-tryon')json=tryon;
  else if(pathname==='/stylist-api/media')json=media;
  else if(pathname==='/stylist-api/images')json=[];
  else if(pathname.endsWith('/composition'))json={status:'completed',image_url:'https://guide-preview.invalid/outfit.png'};
  else if(pathname.endsWith('/app/checkin'))json={data:{signed:false,days:[]}};
  else if(pathname.endsWith('/conversations'))json=[];
  else if(method==='GET')json={data:{list:[],items:[],total_count:0}};
  else throw Error('Unexpected fixture mutation '+method+' '+pathname);
  return r.fulfill({json});
 });
 const chatOnly=process.argv.includes('--chat-only');
 async function save(name){
  if(chatOnly&&!['chat','chat-outfit','tryon-quote'].includes(name))return;
  await p.evaluate(()=>{window.PreviewMessage?.hide();document.querySelector('#companion-notification')?.setAttribute('hidden','')});await p.waitForTimeout(120);
  const html=await p.evaluate(({assets,name,captured})=>{
   const root=document.documentElement.cloneNode(true);root.querySelectorAll('a').forEach(e=>e.removeAttribute('href'));root.querySelectorAll('form').forEach(e=>{e.removeAttribute('action');e.removeAttribute('method')});
   root.querySelectorAll('script,iframe,link[rel="modulepreload"],#first-visit-guide,[data-guide-help],#companion-notification,.preview-message').forEach(e=>e.remove());
   root.querySelectorAll('input,textarea').forEach(e=>{const live=document.getElementById(e.id);if(e.tagName==='TEXTAREA')e.textContent=live?.value||'';if(e.type==='checkbox'&&live?.checked)e.setAttribute('checked','')});
   const images={'portrait.png':'/static/closet-app/assets/private-tryon-portrait-v1.png','result.png':assets+'tryon-example.png','shirt.png':assets+'shirt-example.png','jeans.png':assets+'jeans-example.png','outfit.png':assets+'outfit-example.png'};
   root.querySelectorAll('img').forEach(e=>{if(e.src.startsWith('blob:'))e.src=name.startsWith('person')?images['portrait.png']:images['shirt.png'];if(e.src.startsWith('https://guide-preview.invalid/'))e.src=images[e.src.split('/').pop()]});
   root.querySelector('head').insertAdjacentHTML('afterbegin','<base href="/app/"><meta name="guide-captured-at" content="'+captured+'">');
   root.querySelector('head').insertAdjacentHTML('beforeend','<style>*{animation:none!important;transition:none!important}html{scrollbar-width:none}body{pointer-events:none!important}button,input,textarea{pointer-events:none!important}::-webkit-scrollbar{display:none}</style>');return '<!doctype html>'+root.outerHTML;
  },{assets,name,captured:manifest.captured_at});
  fs.writeFileSync(dir+'/scenes/'+name+'.html',html.replace(/[ \t]+$/gm,'').replace(/\n*$/,'\n'));manifest.scenes.push(name);console.log('captured',name);
 }
 async function pick(filename){await p.locator('#journey-photo-input').setInputFiles(filename);await p.locator('.journey-submitbar .primary:not([disabled])').waitFor()}
 if(process.argv.includes('--home-only')){
  const previous=JSON.parse(fs.readFileSync(dir+'/scenes/manifest.json','utf8'));
  await p.goto(base+'/app/?design=yijian');await p.locator('.y-talk').waitFor();await save('home');
  await p.locator('[data-tab=wardrobe]').click();await p.locator('#wardrobe-sections .section-heading button').first().waitFor();await save('wardrobe');
  await p.locator('[data-tab=profile]').click();await p.locator('.identity').waitFor();await save('profile');
  const captures={...(previous.scene_captured_at||Object.fromEntries(previous.scenes.map(n=>[n,previous.captured_at]))),...Object.fromEntries(manifest.scenes.map(n=>[n,manifest.captured_at]))};
  fs.writeFileSync(dir+'/scenes/manifest.json',JSON.stringify({...previous,scenes:[...new Set([...previous.scenes,...manifest.scenes])],scene_captured_at:captures,last_partial_refresh:{captured_at:manifest.captured_at,source:manifest.source,scenes:manifest.scenes,data:manifest.data}},null,2)+'\n');
  await browser.close();console.log('Refreshed homepage guide scenes only');return;
 }
 if(!chatOnly){
 await p.goto(base+'/app/?design=yijian');await p.locator('.y-talk').waitFor();await save('home');await p.locator('#create-toggle').click();await save('create');await p.locator('[data-agent=upload]').click();await p.locator('#journey-photo-input').waitFor({state:'attached'});await save('upload');await pick(dir+'/assets/shirt-example.png');await save('upload-preview');await p.locator('.journey-submitbar .primary').click();await p.locator('.journey-state').filter({hasText:'已完成'}).waitFor();await save('upload-completed');
 await p.goto(base+'/app/?design=yijian#profile');await p.locator('.memory-card').waitFor();await save('profile');await p.locator('.memory-card').click();await p.locator('#memory-add').waitFor();await save('memory');await p.locator('#memory-add').click();await p.locator('#memory-list textarea').fill('我喜欢宽松、舒服的衣服。');await save('memory-edit');await p.locator('#memory-close').click();
 await p.evaluate(()=>dispatchEvent(new CustomEvent('yijian-agent-open',{detail:'twins'})));await p.locator('.journey-portrait-upload').waitFor();await p.locator('.journey-body-form').waitFor();await save('twins-empty');await p.locator('.journey-portrait-upload').click();await p.locator('#journey-photo-input').waitFor({state:'attached'});await save('person-upload');await pick('stylist/static/closet-app/assets/private-tryon-portrait-v1.png');await save('person-preview');await p.locator('.journey-submitbar .primary').click();await p.getByRole('button',{name:'查看人物生成费用',exact:true}).waitFor();await save('person-checked');await p.getByRole('button',{name:'查看人物生成费用',exact:true}).click();await p.getByRole('button',{name:'确认消耗 100 积分并生成',exact:true}).waitFor();await save('generation-quote');await p.getByRole('button',{name:'确认消耗 100 积分并生成',exact:true}).click();await p.locator('.journey-dialog[data-status=processing]').waitFor();await save('generation-processing');await p.getByRole('button',{name:'确认使用这个试穿形象',exact:true}).waitFor();await save('generation-result');await p.getByRole('button',{name:'确认使用这个试穿形象',exact:true}).click();await p.locator('.journey-portrait[data-twin-key=custom]').waitFor();await p.locator('.journey-body-form').waitFor();await save('twins-ready');await p.locator('.journey-heading button').click();
 }else{custom=true;confirmed=true;}
 await p.goto(base+'/app/?design=yijian');await p.locator('.y-talk').click();await p.locator('#message').waitFor();await save('chat');
 const look={title:'周末散步',wardrobe_complete:true,why:['衬衫搭配牛仔裤，适合轻松的周末散步。'],how:['按自己的舒适程度调整。'],notes:['早晚偏凉时可以加一件外套。'],items:[{source:'user',product_id:'1001',title:'棉质衬衫',class_name:'上衣',slot:'top',original_image:shirt,cutout_image:shirt},{source:'user',product_id:'1002',title:'直筒牛仔裤',class_name:'裤子',slot:'bottom',original_image:jeans,cutout_image:jeans}]};
 const png=await p.evaluate(async look=>{const images=await Promise.all(look.items.map(item=>new Promise(resolve=>{const image=new Image();image.onload=()=>resolve(image);image.src='/static/closet-app/first-visit/assets/'+(item.product_id==='1001'?'shirt-example.png':'jeans-example.png')})));const canvas=document.createElement('canvas');canvas.width=960;canvas.height=1200;const ctx=canvas.getContext('2d');for(const {p,i}of OutfitBoard.layout(look.items).map((p,i)=>({p,i})).sort((a,b)=>a.p.z-b.p.z)){const image=images[i],scale=Math.min(p.w/100*960/image.naturalWidth,p.h/100*1200/image.naturalHeight);ctx.drawImage(image,p.x/100*960-image.naturalWidth*scale/2,p.y/100*1200-image.naturalHeight*scale/2,image.naturalWidth*scale,image.naturalHeight*scale)}return canvas.toDataURL('image/png').split(',')[1]},look);fs.writeFileSync(dir+'/assets/outfit-example.png',Buffer.from(png,'base64'));
 await p.evaluate(look=>showReply({conversation_id:'guide-conversation',version:1,delivery:'outfit',message:'这件衬衫搭配牛仔裤，舒服又利落，周末散步可以这样穿。',looks:[look]}),look);await p.locator('.outfit-expand:not([disabled])').waitFor();await save('chat-outfit');
 await p.getByRole('button',{name:'用数字人试穿这套 ↗',exact:true}).click();if(!chatOnly){await p.locator('.journey-portrait[data-twin-key=custom]').waitFor();await p.locator('.journey-portrait[data-twin-key=custom]').click();await save('tryon-select');await p.getByRole('button',{name:'确认形象，继续查看试穿费用',exact:true}).click();}await p.getByRole('button',{name:'确认消耗 200 积分并试穿',exact:true}).waitFor();await save('tryon-quote');await p.getByRole('button',{name:'确认消耗 200 积分并试穿',exact:true}).click();await p.locator('.journey-dialog[data-status=processing]').waitFor();await save('tryon-processing');await p.locator('.journey-dialog').getByRole('button',{name:'看看试穿进展',exact:true}).click();await p.locator('.journey-dialog[data-status=completed]').waitFor();await save('tryon-result');await p.locator('.journey-heading button').click();await p.evaluate(()=>WardrobeJourney.history());await p.locator('.journey-history-item').first().waitFor().catch(()=>{});await save('records');
 if(chatOnly){const previous=JSON.parse(fs.readFileSync(dir+'/scenes/manifest.json','utf8'));manifest.scene_captured_at={...(previous.scene_captured_at||Object.fromEntries(previous.scenes.map(n=>[n,previous.captured_at]))),...Object.fromEntries(manifest.scenes.map(n=>[n,manifest.captured_at]))};manifest.last_partial_refresh={captured_at:manifest.captured_at,source:manifest.source,scenes:manifest.scenes,data:manifest.data};manifest.captured_at=previous.captured_at;manifest.scenes=[...new Set([...previous.scenes,...manifest.scenes])];}
 fs.writeFileSync(dir+'/scenes/manifest.json',JSON.stringify(manifest,null,2)+'\n');await browser.close();console.log('Saved',manifest.scenes.length,'latest App scenes');
})().catch(e=>{console.error(e);process.exit(1)});
