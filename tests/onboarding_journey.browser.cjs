// All business responses are synthetic; this test never reaches upstream accounts or models.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const base=process.env.ONBOARDING_QA_URL||'http://127.0.0.1:8467';
(async()=>{const browser=await chromium.launch({channel:'chrome'});let scenarios=0;
try{for(const width of [320,393,1440])for(const theme of ['system','male','female']){
 const p=await browser.newPage({viewport:{width,height:852},reducedMotion:'reduce'}),errors=[],writes=[];
 p.on('pageerror',e=>errors.push(e.message));let upload=0,chat=0,confirm=0;const action='med_'+'a'.repeat(32),conversation='sty_'+'b'.repeat(32);
 const reply={conversation_id:conversation,version:1,message:'从白衬衫开始，搭配牛仔裤。',looks:[{title:'自在的一天',items:[{product_id:'101',title:'白衬衫'},{product_id:'102',title:'牛仔裤'}]}]};
 await p.addInitScript(()=>sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify({access_token:'synthetic',user:{id:'onboarding-test'}})));
 await p.route('https://synthetic.test/**',r=>r.fulfill({path:'stylist/static/closet-app/first-visit/assets/shirt-example.png'}));
 await p.route('**/stylist-api/**',async r=>{const request=r.request(),path=new URL(request.url()).pathname,method=request.method();if(method!=='GET')writes.push(path);let json={};
 if(path.endsWith('/companion-profile'))json={profile:{agent_name:'',assistant_persona:theme==='female'?'female_warm_v1':'male_calm_v1',color_scheme:theme==='system'?'system':'companion'},account:{user_name:'模拟用户',user_gender:'女'}};
 else if(path.endsWith('/points'))json={data:{total_available:100}};
 else if(path==='/stylist-api/media/uploads'){upload++;json={kind:'garment',status:'completed',action_id:action,result:{result_image_url:'https://synthetic.test/shirt.png'}};}
 else if(path==='/stylist-api/media/'+action)json={kind:'garment',status:'completed',action_id:action,result:{}};
 else if(path==='/stylist-api/chat'){chat++;const body=request.postDataJSON();assert.equal(body.upload_action_id,action);assert.equal(body.source,'wardrobe');assert.equal(body.new_clothes,false);assert(!('role'in body.companion_profile));json=reply;}
 else if(path==='/stylist-api/conversations/'+conversation)json={conversation_id:conversation,version:1,messages:[{user:'合成测试',reply}]};
 else if(path==='/stylist-api/twins')json={default_confirmed:true,default_twin_key:'system-female',selection_version:1,system_twins:[{twin_key:'system-female',name:'基础形象',image_url:'https://synthetic.test/twin.png'}],profile:{}};
 else if(path.endsWith('/twins/options'))json={height_cm:{min:100,max:220},weight_kg:{min:30,max:200},skin_tone:[]};
 else if(path==='/stylist-api/images/quote'){assert.deepEqual(request.postDataJSON(),{conversation_id:conversation,version:1,look_index:0});json={action_id:'img_test',points_cost:5,item_count:2,title:'自在的一天',portrait:{name:'基础形象',image_url:'https://synthetic.test/twin.png'}};}
 else if(path==='/stylist-api/images/img_test/confirm'){if(request.postDataJSON().confirmed)confirm++;json={action_id:'img_test',status:'completed',conversation_id:conversation,version:1,look_index:0,result:{result_image_url:'https://synthetic.test/result.png'}};}
 else if(path.startsWith('/stylist-api/images/img_test'))json={action_id:'img_test',status:'completed',conversation_id:conversation,version:1,look_index:0,result:{result_image_url:'https://synthetic.test/result.png'}};
 else if(path==='/stylist-api/media'||path==='/stylist-api/images')json=[];
 else throw Error('Unmocked route '+path);
 await r.fulfill({json});});
 await p.goto(base+'/app/?design=yijian&screen=onboarding');await p.waitForFunction(()=>!document.querySelector('#next').disabled);assert(await p.locator('#skip').isHidden());await p.locator('#next').click();if(theme==='female')await p.locator('.role-group').last().click();await p.locator('.roles .choice').first().click();await p.locator('#next').click();assert.equal(writes.length,0);
 await p.getByRole('button',{name:'选择衣物照片',exact:true}).click();await p.locator('#journey-photo-input').setInputFiles('stylist/static/closet-app/first-visit/assets/shirt-example.png');assert.equal(upload,0);await p.getByRole('button',{name:'确认上传',exact:true}).click();await p.getByRole('button',{name:'用这件搭一套',exact:true}).last().click();await p.getByRole('dialog',{name:'从这件开始搭配'}).waitFor();assert.equal(chat,0);await p.getByRole('button',{name:'确认开始搭配',exact:true}).click();await p.locator('.onboarding-look').waitFor();assert.equal(chat,1);assert.equal(upload,1);
 // Reload recovers only by authenticated reads; neither the upload nor chat is re-submitted.
 await p.reload();await p.waitForFunction(()=>!document.querySelector('#next').disabled);await p.locator('#next').click();if(theme==='female')await p.locator('.role-group').last().click();await p.locator('.roles .choice').first().click();await p.locator('#next').click();await p.locator('.onboarding-look').waitFor();assert.equal(chat,1);assert.equal(upload,1);
 await p.locator('#next').click();await p.getByRole('button',{name:'选择或创建数字分身',exact:true}).click();await p.locator('.journey-portrait-upload').waitFor();await p.getByRole('button',{name:'关闭上传与试穿面板'}).click();await p.locator('#next').click();await p.getByRole('button',{name:'暂不定位',exact:true}).click();
 await p.getByRole('button',{name:'查看试穿形象与费用',exact:true}).click();await p.getByRole('button',{name:'确认消耗 5 积分并试穿',exact:true}).waitFor();assert.equal(confirm,0);await p.getByRole('button',{name:'暂不生成',exact:true}).click();assert.equal(confirm,0);
 await p.getByRole('button',{name:'查看试穿形象与费用',exact:true}).click();await p.getByRole('button',{name:'确认消耗 5 积分并试穿',exact:true}).click();await p.locator('#journey-dialog img[alt="本次搭配的数字人试穿结果"]').waitFor();assert.equal(confirm,1);assert.deepEqual(errors,[]);assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));scenarios++;await p.close();
}console.log(JSON.stringify({scenarios,realBusinessCalls:0}));}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
