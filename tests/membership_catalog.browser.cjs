// Synthetic Server responses; never sends orders, writes account data or invokes StoreKit.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/tmp/stylist-three-lines-20261102/node_modules/playwright');
const assert=require('assert/strict'),fs=require('fs');
const {captureMarked}=require('/Users/duxiao/.codex/skills/red-circle-docs/scripts/capture_marked.cjs');
const folder='reports/26-11-07/membership-api';fs.mkdirSync(folder,{recursive:true});
(async()=>{const browser=await chromium.launch({channel:'chrome'});const results=[];
try{for(const width of [320,393,1440]){
 const p=await browser.newPage({viewport:{width,height:1100}}),errors=[],calls=[];let mode='normal',gate=null;
 p.setDefaultTimeout(10000);p.on('pageerror',e=>errors.push(e.message));
 await p.addInitScript(()=>{sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'member-A',user:{id:'membership-fixture'}}));for(const t of ['upload','profile','memory','chat'])localStorage.setItem('closet-guide:v2:user:membership-fixture:'+t,'seen');});
 await p.route('**/stylist-api/**',async r=>{
  const path=new URL(r.request().url()).pathname,token=r.request().headers().authorization||'';calls.push({path,token,method:r.request().method()});
  if(path.includes('/purchase/')){
   const section=path.split('/').pop(),snapshot=mode;if(gate)await gate;
   if(snapshot==='failure'&&section==='member')return r.fulfill({status:502,json:{message:'商品读取失败（模拟）'}});
   const product={product_id:701,name:token.includes('member-B')?'B账号后台商品':'后台月度方案',price:29.9,currency:'CNY',sub_title:'后台周期说明',description:'后台商品详细说明',is_recommend:false};
   const data=section==='member'?{products:snapshot==='empty'?[]:snapshot==='invalid'?[{...product,price:null}]:[{...product},{...product,product_id:902,name:'后台推荐方案',price:246.5,original_price:307,is_recommend:true}]}:
    section==='points'?{list:[{id:511,name:'运营积分包甲',price:17.8,points_amount:410},{id:722,name:'运营积分包乙',price:37.2,points_amount:910}]}:
    section==='benefits'?{banner:{items:[{image_url:'https://example.invalid/unused-promo.png',title:'不应铺在会员页的宣传图'}]},benefit_table:{name_column_header:'后台权益项目',columns:[{id:'normal',header:'普通后台'},{id:'vip',header:'会员后台'}],rows:[{name:'后台容量',display_scope:'all',tooltip:'后台说明',values:[{type:'text',text:'37件'},{type:'text',text:'602件'}]},{name:'后台功能',display_scope:'all',values:[{type:'cross'},{type:'check'}]},{name:'仅对比页',display_scope:'comparison_only',values:[{type:'text',text:'不在购买页展示'},{type:'text',text:'不在购买页展示'}]}]}}:
    {vip_tip:{title:'后台会员说明',desc_list:['<b>运营可随时调整权益</b>']},fitting_cost:73,prettify_cost:26,agreements:{member:'https://example.invalid/membershipService',points:'https://example.invalid/pointsPurchase',subscription:'https://example.invalid/continuousSubscription'}};
   return r.fulfill({json:{data}});
  }
  if(path.endsWith('/twins'))return r.fulfill({json:{custom_twin:null,system_twins:[],need_gender:false}});
  return r.fulfill({json:path.endsWith('companion-profile')?{profile:{user_name:'示例用户',user_gender:'女',agent_name:'衣衣',assistant_persona:'female_warm_v1',color_scheme:'system'}}:path.endsWith('memories')?{entries:[],enabled:true}:{data:{list:[],items:[],total_available:100,vip_info:{is_vip:false}}}});
 });
 await p.goto((process.env.STYLIST_BASE_URL||'http://127.0.0.1:8466')+'/app/?design=yijian#profile');await p.locator('[data-detail=membership]').click();
 await p.waitForFunction(()=>document.querySelector('.sku-details .sku-dock')?.textContent.includes('246.50'));
 console.log('catalog ready',width);assert.equal(await p.locator('.sku-details .sku-card').count(),2);
 assert.equal(await p.locator('.sku-details [data-choice="902"]').getAttribute('aria-pressed'),'true');
 assert.equal(await p.locator('.sku-benefits thead th').allTextContents().then(x=>x.join('|')),'后台权益项目|普通后台|会员后台');
 assert.equal(await p.locator('.sku-server-banners').count(),0);assert.equal(await p.locator('img[src="https://example.invalid/unused-promo.png"]').count(),0);assert.equal(await p.locator('.sku-center-art').count(),1);assert.equal(await p.locator('.sku-benefits tbody tr').count(),2);assert.match(await p.locator('.sku-benefits').textContent(),/37件/);assert.doesNotMatch(await p.locator('.sku-details').textContent(),/2,000|示例基础容量|每满100万token|积分有效期.*2年/);
 assert.equal(await p.locator('.sku-details a[href="https://example.invalid/membershipService"]').count(),2);
 assert.match(await p.locator('.sku-details').textContent(),/试衣 73 积分/);
 await p.locator('.sku-benefits').scrollIntoViewIfNeeded();await captureMarked(p,folder+'/benefits-after-'+width+'.png',['.sku-benefits']);
 await p.locator('.sku-details .sku-card').first().scrollIntoViewIfNeeded();await captureMarked(p,folder+'/products-after-'+width+'.png',['.sku-details .sku-rail']);
 await p.locator('.sku-dock .sku-pay').click();assert.match(await p.locator('.sku-payment').textContent(),/后台推荐方案/);assert.doesNotMatch(await p.locator('.sku-payment').textContent(),/购买成功|不自动续费/);await p.locator('.sku-payment-close').click();
 await p.locator('#sku-center-tab-points').click();await p.waitForFunction(()=>document.querySelector('.sku-details .sku-card')?.textContent.includes('运营积分包'));
 assert.equal(await p.locator('.sku-details .sku-card').count(),2);assert.match(await p.locator('.sku-details .sku-points-rules').textContent(),/410 积分/);
 console.log('points ready',width);
 // Actual shortage entry must use the shared live catalog, never preview fixture packages.
 await p.evaluate(()=>window.AppPayment.handleError({code:'tryon_points_insufficient'}));
 assert.doesNotMatch(await p.locator('.app-payment-panel').evaluate(e=>e.shadowRoot.textContent),/100 积分包|500 积分包|¥48/);
 assert.match(await p.locator('.app-payment-panel').evaluate(e=>e.shadowRoot.textContent),/积分还差一点|这次还需要补充积分/);
 await p.evaluate(()=>document.fonts.ready);await p.waitForTimeout(1700);
 assert.match(await p.locator('.app-payment-panel').evaluate(e=>e.shadowRoot.textContent),/运营积分包甲/);
 if(width===393)await captureMarked(p,folder+'/paywall-approved-standard-393.png',['.app-payment-panel']);
 await p.evaluate(()=>window.dispatchEvent(new CustomEvent('yijian-account-loaded',{detail:{vip_info:{is_vip:true}}})));
 assert.equal(await p.locator('.app-payment-panel').evaluate(e=>e.shadowRoot.querySelectorAll('[data-action=member]').length),0);
 assert.match(await p.locator('.app-payment-panel').evaluate(e=>e.shadowRoot.textContent),/会员权益生效中/);
 await p.waitForTimeout(1700);
 if(width===393)await captureMarked(p,folder+'/paywall-approved-member-393.png',['.app-payment-panel']);
 await p.evaluate(()=>window.dispatchEvent(new CustomEvent('yijian-account-loaded',{detail:{vip_info:{is_vip:false}}})));
 
 await p.locator('.app-payment-panel').evaluate(e=>e.shadowRoot.querySelector('[data-action=points]').click());await p.locator('#sku-center-tab-points[aria-selected=true]').waitFor();
 console.log('paywall ready',width);if(width===393){
  const refresh=()=>p.evaluate(async()=>{const m=await import('/static/closet-app/purchase-catalog.js');await m.loadCatalog(true);});
  mode='failure';await refresh();await p.locator('#sku-center-tab-member').click();assert.equal(await p.locator('.sku-details .sku-card').count(),0);assert.equal(await p.locator('.sku-dock').isVisible(),false);assert.match(await p.locator('.sku-details .sku-catalog').textContent(),/读取失败/);
  mode='normal';await refresh();assert.equal(await p.locator('.sku-details .sku-card').count(),2);
  mode='empty';await refresh();assert.equal(await p.locator('#sku-center-tab-member').isVisible(),false);assert.equal(await p.locator('#sku-center-tab-points').getAttribute('aria-selected'),'true');assert.equal(await p.locator('.sku-details .sku-card').count(),2);assert.deepEqual(await p.locator('.sku-journal > .sku-catalog [role=tab]').allTextContents(),['积分包']);await p.locator('#sku-center-tab-points').press('Home');assert.equal(await p.locator('#sku-center-tab-points').getAttribute('aria-selected'),'true');
  mode='invalid';await refresh();await p.locator('#sku-center-tab-member').click();assert.equal(await p.locator('.sku-details .sku-card').count(),0);assert.match(await p.locator('.sku-details .sku-catalog').textContent(),/不完整/);
  mode='normal';let release;gate=new Promise(r=>release=r);await p.evaluate(()=>import('/static/closet-app/purchase-catalog.js').then(m=>{m.loadCatalog(true);}));
  await p.evaluate(()=>{sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'member-B',user:{id:'membership-fixture-B'}}));window.dispatchEvent(new Event('yijian-session-change'));});release();gate=null;
  await p.waitForFunction(async()=>{const m=await import('/static/closet-app/purchase-catalog.js');return m.catalogState().member.data?.[0]?.name==='B账号后台商品';});assert.equal(await p.evaluate(async()=>(await import('/static/closet-app/purchase-catalog.js')).catalogState().member.data.some(p=>p.name==='后台月度方案')),false);
  await p.evaluate(()=>{sessionStorage.removeItem('ai-closet-stylist-session-v1');window.dispatchEvent(new Event('yijian-session-change'));});await p.waitForFunction(async()=>{const m=await import('/static/closet-app/purchase-catalog.js');return m.catalogState().member.data===null;});assert.equal(await p.locator('.sku-details .sku-card').count(),0);
 }
 assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);assert(calls.every(c=>c.method==='GET'));results.push({width,readCalls:calls.length,errors,writes:0});await p.close();
}}finally{await browser.close();}fs.writeFileSync(folder+'/browser-verification.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results));})().catch(e=>{console.error(e);process.exit(1)});
