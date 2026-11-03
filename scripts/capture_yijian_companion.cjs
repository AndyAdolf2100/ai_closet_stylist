// Screenshots of the real H5 with explicitly synthetic data and bundled iOS sample art.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'), path = require('node:path');
(async()=>{
 const assets=process.env.IOS_ASSET_ROOT;if(!assets)throw new Error('Set IOS_ASSET_ROOT to DesignAssets.xcassets');
 const out=path.resolve('var/yijian-companion-preview');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:393,height:852},deviceScaleFactor:2});
 await page.addInitScript(()=>sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'screenshot-fixture',user:{id:'preview'}})));
 await page.route('**/preview-art/*',async route=>{
  const name=new URL(route.request().url()).pathname.split('/').at(-1);
  if(!['fitting_result_mock','fitting_product_mock_shirt','fitting_product_mock_jeans'].includes(name))return route.abort();
  await route.fulfill({contentType:'image/png',body:fs.readFileSync(path.join(assets,`${name}.imageset`,`${name}.png`))});
 });
 await page.route('**/stylist-api/**',async route=>{
  const section=new URL(route.request().url()).pathname.split('/').at(-1);
  let data={list:[]};
  if(section==='album')data={items:[{title:'把午后，穿成喜欢的样子',description:'宽松衬衫与牛仔裤，留一点自在，给今天的小小出走。',finished_at:'2026-11-03T14:00:00+08:00',source_label:'试穿示例',context_text:'午后散步',product_count:2,product_images:[{title:'衬衫示例',image_url:'/preview-art/fitting_product_mock_shirt'},{title:'牛仔裤示例',image_url:'/preview-art/fitting_product_mock_jeans'}],fitting_image_url:'/preview-art/fitting_result_mock'}],has_more:false};
  if(section==='profile')data={nick_name:'体验账号',vip_info:{total_points:200}};
  if(section==='memories')data={items:[{memory_id:'1',status:'active',content:'喜欢柔软舒适的面料'},{memory_id:'2',status:'active',content:'周末想穿得自在一些'}]};
  const body=section==='companion-profile'?{profile:{agent_name:'衣衣',assistant_persona:'female_warm_v1'}}:{data};
  await route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto((process.env.STYLIST_APP_URL||'http://127.0.0.1:8478')+'/app/?design=yijian');
 await page.locator('.album-card').waitFor();await page.evaluate(()=>document.fonts.ready);
 for(const theme of ['female','male','system']){
  await page.evaluate(()=>scrollTo(0,0));await page.locator(`[data-palette="${theme}"]`).click();
  await page.locator('[data-tab="home"]').click();await page.locator('.album-card').waitFor();
  await page.locator('.album-result').evaluate(img=>img.decode());
  await page.evaluate(()=>{const y=document.querySelector('.album-card').getBoundingClientRect().top+scrollY;scrollTo(0,y-64);});
  await page.screenshot({path:path.join(out,`${theme}-album.png`)});
  await page.locator('[data-tab="profile"]').click();await page.locator('.memory-line').last().waitFor();
  await page.locator('.y-letter-photo').evaluate(img=>img.decode());await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:path.join(out,`${theme}-profile.png`)});
  await page.evaluate(()=>{const y=document.querySelector('.memory-card').getBoundingClientRect().top+scrollY;scrollTo(0,y-28);});
  await page.screenshot({path:path.join(out,`${theme}-notebook.png`)});
 }
 const palettes=[['female','奶油绿'],['male','雾蓝'],['system','系统黄']];
 const rows=[['album','造型册 · 一页穿搭手记'],['profile','我的日常 · 陪伴小笺'],['notebook','我的日常 · 收藏与记录']];
 const html=`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>衣间 陪伴风格界面对照</title><style>*{box-sizing:border-box}body{margin:0;padding:32px;background:#f5f3ee;color:#41483e;font:14px -apple-system,'PingFang SC',sans-serif}main{max-width:1260px;margin:auto}h1{font:32px 'Songti SC',serif;margin:0 0 12px}p{line-height:1.8;color:#777468}h2{font:24px 'Songti SC',serif;margin:32px 0 16px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}figure{margin:0}figcaption{margin-bottom:12px;font-size:14px}img{width:100%;display:block;border-radius:18px;border:1px solid #e2ddd3}a{color:inherit}.note{padding:14px 18px;background:#fff;border:1px solid #e2ddd3;border-radius:12px}@media(max-width:700px){body{padding:20px}.grid{grid-template-columns:1fr}}</style><main><h1>衣间 · 日常的陪伴感</h1><p>造型册与个人中心 · 三种配色 · 393 × 852 CSS px，2倍截图</p><p class="note">示例数据，仅用于界面预览；不代表你的穿搭、积分或记忆。穿搭图使用 iOS 内置示例素材，原始素材未修改。没有使用你提供截图中的用户照片。iOS 源码未改。</p>${rows.map(([key,title])=>`<section><h2>${title}</h2><div class="grid">${palettes.map(([id,label])=>`<figure><figcaption>${label}</figcaption><a href="${id}-${key}.png"><img src="${id}-${key}.png" alt="${label} ${title}"></a></figure>`).join('')}</div></section>`).join('')}</main></html>`;
 fs.writeFileSync(path.join(out,'index.html'),html);
 const gallery=await browser.newPage({viewport:{width:1324,height:1000},deviceScaleFactor:1});
 await gallery.goto('file://'+path.join(out,'index.html'));await gallery.locator('img').evaluateAll(imgs=>Promise.all(imgs.map(i=>i.decode())));
 await gallery.screenshot({path:path.join(out,'comparison.png'),fullPage:true});
 await browser.close();console.log('9 screenshots and comparison gallery saved to '+out);
})().catch(e=>{console.error(e);process.exit(1)});
