const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('stylist/static/app.js','utf8');
const component=source.slice(source.indexOf('function outfitFeedback('),source.indexOf('\nfunction showReply('));
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function setup(api){
 const dom=new JSDOM('<body></body>'),w=dom.window;
 w.CompanionSettings={getProfile:()=>({assistant_persona:'male_calm_v1'})};
 const session={user:{id:'mock'}};
 const el=(tag,cls,text)=>{const e=w.document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e;};
 const notices=[];
 const factory=new Function('window','document','el','api','requireLogin','notifyIssue','session',component+';return {mount:outfitFeedback,switchAccount:()=>{session={};}};');
 const app=factory(w,w.document,el,api,()=>true,t=>notices.push(t),session);
 const box=app.mount({conversation_id:'sty_mock',version:4},1);w.document.body.append(box);
 return {dom,w,box,notices,...app};
}
test('letter votes wait for saved receipt and allow correction and withdrawal',async()=>{
 const calls=[];let complete;
 const view=setup(async(path,options)=>{calls.push([path,options]);if(!options)return {vote:null};return await new Promise(resolve=>complete=resolve);});
 await tick();const buttons=view.box.querySelectorAll('button');
 assert.equal(buttons[0].getAttribute('aria-label'),'喜欢这套');
 assert.equal(buttons[1].getAttribute('aria-label'),'不喜欢这套');
 buttons[0].click();assert.equal(buttons[0].getAttribute('aria-pressed'),'false');assert.equal(buttons[0].disabled,true);
 const body=JSON.parse(calls[1][1].body);assert.deepEqual(body,{version:4,look_index:1,vote:'like',assistant_persona:'male_calm_v1'});
 complete({vote:'like',message:'模拟助理回音'});await tick();assert.equal(buttons[0].getAttribute('aria-pressed'),'true');
 assert.equal(view.box.querySelector('[role=status]').textContent,'模拟助理回音');
 buttons[1].click();complete({vote:'dislike',message:'可以再调整'});await tick();assert.equal(buttons[1].getAttribute('aria-pressed'),'true');
 buttons[2].click();complete({vote:null,message:'已经撤回'});await tick();assert.equal(buttons[0].getAttribute('aria-pressed'),'false');
 assert.equal(buttons[2].style.visibility,'hidden');view.dom.window.close();
});
test('save failure preserves the original vote and can retry',async()=>{
 const view=setup(async(path,options)=>{if(options)throw Error('模拟失败');return {vote:'like'};});
 await tick();view.box.querySelectorAll('button')[1].click();await tick();
 assert.equal(view.box.dataset.vote,'like');assert.equal(view.box.querySelector('button').disabled,false);
 assert.match(view.box.querySelector('[role=status]').textContent,/原来的选择还在/);assert.deepEqual(view.notices,['模拟失败']);view.dom.window.close();
});
test('late account responses cannot paint old receipts or errors',async()=>{
 let complete;const view=setup(async(path,options)=>options?await new Promise(resolve=>complete=resolve):{vote:null});
 await tick();view.box.querySelector('button').click();view.switchAccount();complete({vote:'like',message:'旧账号回音'});await tick();
 assert.notEqual(view.box.dataset.vote,'like');assert(!view.box.textContent.includes('旧账号回音'));assert.equal(view.notices.length,0);view.dom.window.close();
});
