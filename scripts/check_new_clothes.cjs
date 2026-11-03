const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});fs.mkdirSync('var/new-clothes-ui',{recursive:true});let checks=0;
 for(const width of [1440,390,320,844]){
  const page=await browser.newPage({viewport:{width,height:width===844?390:900}}),errors=[],calls=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'synthetic-only',user:{id:'synthetic'}})));
  await page.route('**/stylist-api/**',async route=>{
   const path=new URL(route.request().url()).pathname;
   if(path.endsWith('/chat/stream')){
    const req=route.request().postDataJSON();calls.push(req);
    const auto=req.message.includes('里面没有'),enabled=auto||req.new_clothes,version=calls.length;
    const reply={conversation_id:'sty_'+'1'.repeat(32),version,mode:'recommend',delivery:'concept',message:'这次找到的衣物还没能配齐，我先把搭配思路留给你。',
     task:{source:enabled?'hybrid':'wardrobe'},new_clothes:enabled,new_clothes_auto_enabled:auto,
     new_clothes_notice:auto?'已为你开启「邂逅新衣」。我陪你看看衣橱之外的新选择。':null,
     wardrobe_gap:!enabled,looks:[{title:'日常搭配',items:[],pieces:['衬衫','长裤'],reference_pieces:['长裤'],why:[],how:[],notes:[]}],warnings:[],follow_ups:[]};
    const progress=auto?'event: progress\ndata: '+JSON.stringify({stage:'new_clothes',message:reply.new_clothes_notice})+'\n\n':'';
    return route.fulfill({contentType:'text/event-stream',body:progress+'event: result\ndata: '+JSON.stringify(reply)+'\n\n'});
   }
   if(path.endsWith('/companion-profile'))return route.fulfill({json:{profile:{user_name:'小夏',user_gender:'女',assistant_name:'衣衣',assistant_persona:'male_calm_v1',color_scheme:'companion'}}});
   return route.fulfill({json:path.endsWith('/conversations')?[]:{entries:[],enabled:true,revision:0}});
  });
  await page.goto('http://127.0.0.1:8466/');await page.waitForFunction(()=>window.CompanionSettings);
  await page.evaluate(()=>window.CompanionSettings.ready);
  await page.evaluate(()=>{window._newClothesMessages=[];const original=window.CompanionSettings.notify;window.CompanionSettings.notify=(text,...args)=>{window._newClothesMessages.push(text);return original(text,...args)}});
  assert.equal(await page.locator('#new-clothes').isChecked(),false);checks++;
  assert(await page.locator('#personal-clothes').isChecked());
  await page.locator('.clothing-source-option:has(#new-clothes)').click();assert(await page.locator('#new-clothes').isChecked());assert.equal(calls.length,0);
  assert.equal(await page.evaluate(()=>window._newClothesMessages.length),1);assert((await page.evaluate(()=>window._newClothesMessages[0])).includes('参考'));
  await page.locator('.clothing-source-option:has(#new-clothes)').click();assert.equal(await page.evaluate(()=>window._newClothesMessages.length),1);checks+=3;
  await page.locator('#new-clothes').focus();await page.keyboard.press('ArrowLeft');assert(await page.locator('#personal-clothes').isChecked());
  assert.equal(await page.locator('.clothing-source-option:has(#personal-clothes)').evaluate(n=>getComputedStyle(n).outlineWidth),'2px');
  await page.evaluate(()=>setBusy(true));assert(await page.locator('#new-clothes').isDisabled());assert(await page.locator('#personal-clothes').isDisabled());await page.evaluate(()=>setBusy(false));checks+=7;
  await page.locator('#message').fill('帮我搭一套，不考虑天气');await page.locator('#send').click();
  await page.locator('.new-clothes-invite').waitFor();assert.equal(calls[0].new_clothes,false);checks++;
  await page.locator('.new-clothes-invite').scrollIntoViewIfNeeded();await page.screenshot({path:`var/new-clothes-ui/${width}-gap.png`});
  await page.locator('#message').fill('还没有发出的草稿');
  await page.locator('.new-clothes-invite button').nth(1).click();await page.waitForFunction(()=>document.getElementById('send').disabled===false);
  assert.equal(calls.length,2);assert.equal(calls[1].new_clothes,true);assert.equal(await page.evaluate(()=>window._newClothesMessages.filter(text=>text.includes('参考')).length),2);checks++;assert.equal(await page.locator('#message').inputValue(),'还没有发出的草稿');checks+=3;
  assert(await page.locator('#new-clothes').isChecked());checks++;
  await page.locator('.clothing-source-option:has(#personal-clothes)').click();await page.locator('#message').fill('我想尝试新的搭配，并且是我衣橱里面没有的');await page.locator('#send').click();
  await page.waitForFunction(()=>document.getElementById('send').disabled===false);
  assert(await page.locator('#new-clothes').isChecked());assert.equal(calls[2].new_clothes,false);checks+=2;
  assert.equal(await page.evaluate(()=>window._newClothesMessages.filter(text=>text.includes('已为你开启「邂逅新衣」')).length),1);checks++;
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));checks++;
  assert.equal(await page.locator('#new-clothes').evaluate(n=>n.closest('label').getBoundingClientRect().height>=44),true);checks++;
  for(const color of ['male','female','system']){
   await page.evaluate(color=>{document.documentElement.dataset.stylistGender=color==='female'?'female':'male';document.documentElement.dataset.colorScheme=color==='system'?'system':'companion'},color);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));checks++;
   const style=await page.locator('.clothing-source-options').evaluate(n=>({border:getComputedStyle(n).borderWidth,labels:[...n.querySelectorAll('label')].map(l=>({background:getComputedStyle(l).backgroundColor,border:getComputedStyle(l).borderWidth,height:l.getBoundingClientRect().height,underline:getComputedStyle(l,'::after').opacity}))}));
   assert.equal(style.border,'0px');assert(style.labels.every(l=>l.border==='0px'&&l.height>=44));assert(style.labels.every(l=>l.background==='rgba(0, 0, 0, 0)'));assert.equal(style.labels[0].underline,'0');assert.equal(style.labels[1].underline,'1');checks+=5;
   const placement=await page.locator('.clothing-source-options').evaluate(n=>({inside:!!n.closest('form'),height:n.getBoundingClientRect().height,gap:document.getElementById('chat-form').getBoundingClientRect().top-n.getBoundingClientRect().bottom}));assert.equal(placement.inside,false);assert.equal(placement.height,32);assert.equal(placement.gap,8);checks+=3;
   await page.screenshot({path:`var/new-clothes-ui/${width}-${color}.png`});
  }
  await page.locator('#logout').evaluate(n=>n.click());assert.equal(await page.locator('#new-clothes').isChecked(),false);checks++;
  assert.deepEqual(errors,[]);checks++;await page.close();
 }
 await browser.close();console.log(`${checks} browser checks passed; synthetic API only; screenshots in var/new-clothes-ui`);
})().catch(e=>{console.error(e);process.exit(1)});
