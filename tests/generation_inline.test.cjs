const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const {JSDOM}=require('jsdom');
const source=fs.readFileSync('stylist/static/wardrobe-journey.js','utf8');
const flush=async()=>{for(let i=0;i<8;i++)await new Promise(r=>setImmediate(r));};
async function setup(custom){
 const dom=new JSDOM('<body><div id="feed"></div></body>',{url:'https://fixture.test',runScripts:'outside-only'}),w=dom.window,calls=[],notices=[];
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'))};w.URL.createObjectURL=()=> 'blob:fixture';w.URL.revokeObjectURL=()=>{};
 w.eval(source);w.WardrobeJourney.configure({api:async(path,options)=>{calls.push([path,options]);if(path.endsWith('/uploads'))return {action_id:'photo',kind:'person',status:'completed',result:{allowed_hat_actions:['none','remove']}};return custom(path,options);},notify:t=>notices.push(t)});w.WardrobeJourney.setOwner('a');
 w.WardrobeJourney.upload('person');const input=w.document.querySelector('input[type=file]');Object.defineProperty(input,'files',{value:[new w.File([Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),Buffer.alloc(92)])],'fixture.png',{type:'image/png'})]});input.dispatchEvent(new w.Event('change'));await flush();
 const btn=text=>[...w.document.querySelectorAll('button')].find(b=>b.textContent===text);
 btn('确认上传').click();await flush();return {w,calls,notices,btn,close:()=>w.close()};
}
const q=(id='q',cost=8)=>({action_id:id,points_cost:cost,status:'quoted',kind:'generation'});
test('two steps; quote auto-loads; one explicit click confirms without intermediate page',async()=>{
 const t=await setup(async(path)=>path.endsWith('/generation-quote')?q():{action_id:'q',kind:'generation',status:'completed',result:{can_confirm:false}});
 assert.equal(t.w.document.querySelectorAll('.journey-steps li').length,2);
 assert(!t.w.document.querySelector('.journey-steps').textContent.includes('确认积分'));
 assert.equal(t.calls.filter(([p])=>p.endsWith('/confirm')).length,0);
 const b=t.btn('确认消耗 8 积分并生成');assert(b&&!b.disabled);b.click();b.click();await flush();
 assert.equal(t.calls.filter(([p,o])=>p.endsWith('/confirm')&&JSON.parse(o.body).confirmed).length,1);
 assert.match(t.w.document.querySelector('.journey-steps .is-current').textContent,/查看新模样/);t.close();
});
test('failed quote only retries reading and never dispatches generation',async()=>{
 let attempts=0;const t=await setup(async()=>{if(++attempts===1)throw Error('offline');return q()});
 assert(t.btn('重新读取生成积分'));t.btn('重新读取生成积分').click();await flush();assert(t.btn('确认消耗 8 积分并生成'));
 assert.equal(t.calls.filter(([p])=>p.endsWith('/confirm')).length,0);t.close();
});
test('changing options invalidates cost and rejects late quote results',async()=>{
 const pending=[];const t=await setup(async(p)=>p.endsWith('/generation-quote')?new Promise(r=>pending.push(r)):{});
 assert(t.btn('正在读取生成积分…').disabled);t.btn('摘掉帽子').click();await flush();assert.equal(pending.length,2);
 pending[1](q('new',12));await flush();pending[0](q('old',8));await flush();
 assert(t.btn('确认消耗 12 积分并生成'));assert(!t.btn('确认消耗 8 积分并生成'));
 assert(t.calls.some(([p,o])=>p==='/stylist-api/media/old/confirm'&&!JSON.parse(o.body).confirmed));t.close();
});
test('hair edits invalidate immediately and debounce a fresh quote',async()=>{
 let count=0;const t=await setup(async(p)=>p.endsWith('/generation-quote')?q('q'+ ++count):{});
 const input=t.w.document.querySelector('textarea');input.value='黑色短发';input.dispatchEvent(new t.w.Event('input'));
 assert(t.btn('正在读取生成积分…').disabled);await new Promise(r=>setTimeout(r,400));await flush();
 assert.equal(count,2);const args=t.calls.filter(([p])=>p.endsWith('/generation-quote')).at(-1)[1];assert.equal(JSON.parse(args.body).hair_description,'黑色短发');t.close();
});
test('account switch discards a late quote without making a request as new owner',async()=>{
 let done;const t=await setup(async()=>new Promise(r=>done=r));const count=t.calls.length;t.w.WardrobeJourney.setOwner('b');done(q());await flush();
 assert.equal(t.calls.length,count);assert(!t.btn('确认消耗 8 积分并生成'));t.close();
});
test('closing cancels the quote, never confirms generation',async()=>{
 const t=await setup(async()=>q());t.w.document.querySelector('dialog').close();await flush();
 const confirm=t.calls.find(([p])=>p.endsWith('/confirm'));assert(confirm);assert.equal(JSON.parse(confirm[1].body).confirmed,false);t.close();
});
test('lost confirmation response switches to query-only unknown result without repeat submission',async()=>{
 const t=await setup(async(p)=>{if(p.endsWith('/generation-quote'))return q();if(p.endsWith('/confirm'))throw Error('timeout');return {action_id:'q',kind:'generation',status:'processing',result:{}}});
 t.btn('确认消耗 8 积分并生成').click();await flush();assert.equal(t.w.document.querySelector('dialog').dataset.status,'unknown');assert(!t.btn('确认消耗 8 积分并生成'));assert.equal(t.calls.filter(([p])=>p.endsWith('/confirm')).length,1);t.close();
});
