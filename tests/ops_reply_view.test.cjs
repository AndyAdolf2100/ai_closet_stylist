const {test}=require('node:test');const assert=require('node:assert/strict');const {JSDOM}=require('jsdom');const fs=require('node:fs');
const source=fs.readFileSync('stylist/static/ops/reply-view.js','utf8');const mod=import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
function setup(){const dom=new JSDOM('<main></main>');global.document=dom.window.document;global.window=dom.window;window.OutfitBoard={readOnly:()=>document.createElement('section')};return {dom,host:document.querySelector('main')};}
test('broken reply JSON and bad cards fail locally while remaining messages and sections render',async()=>{
 const {renderMessages}=await mod;const {dom,host}=setup();renderMessages(host,[
 {version:1,user_message:'第一条',reply:'{bad json'},
 {version:2,user_message:'看看黑衣',reply:{message:'有效正文',looks:[{title:'局部卡片',items:[],pieces:['白衬衫'],why:{bad:true},how:['整理袖口']},null],product_results:[{title:'黑色上衣',source:'user',product_id:'1'},42],warnings:['有效提醒'],follow_ups:['看看别的']}},
 null,
 {version:4,user_message:'最后一条',reply:{message:'后续有效消息'}}]);
 assert.match(host.textContent,/第一条/);assert.match(host.textContent,/有效正文/);assert.match(host.textContent,/整理袖口/);assert.match(host.textContent,/后续有效消息/);assert.match(host.textContent,/黑色上衣/);assert.match(host.textContent,/有效提醒/);
 assert(host.querySelectorAll('.part-error').length>=5);assert.equal(host.querySelectorAll('button,form,input').length,0);assert.match(host.textContent,/messages\[1\].reply.looks\[0\].why/);dom.window.close();
});
test('all message contents and raw errors render as text and never execute markup',async()=>{
 const {renderMessages}=await mod;const {dom,host}=setup();renderMessages(host,[{version:1,user_message:'<img src=x onerror=alert(1)>',reply:{message:'<script>bad</script>',product_results:[{source:'user',title:'unsafe',cutout_image:'javascript:alert(1)'}]}}]);
 assert.equal(host.querySelectorAll('script,img').length,0);assert.match(host.textContent,/<script>/);assert.match(host.textContent,/图片地址/);dom.window.close();
});
test('request structure errors do not hide healthy inspector entries',async()=>{
 const {renderInspector}=await mod;const {dom,host}=setup();renderInspector(host,{conversation_id:'fixture',session:{owner_id:'1024'},requests:[null,{request_id:'synthetic-failed',status:'failed',response:'{bad'}, {request_id:'synthetic-completed',status:'completed',response:{}}]});
 assert.match(host.textContent,/synthetic-completed/);assert.match(host.textContent,/synthetic-failed/);assert.equal(host.querySelectorAll('.part-error').length,2);assert.equal(host.querySelectorAll('button').length,0);dom.window.close();
});
test('detail cards and retained snapshots do not duplicate the primary card',async()=>{
 const {renderMessages}=await mod;const {dom,host}=setup();const product={source:'user',title:'白衬衫',product_id:'1'};
 renderMessages(host,[{version:1,reply:{message:'',product_entry:{product},looks:[{title:'重复单品',items:[product]}],retained_items:[product]}},{version:2,reply:{looks:[{title:'通勤搭配',items:[product]}],outfit_entry:{title:'重复搭配',items:[product]},retained_items:[product]}}]);
 assert.equal(host.querySelectorAll('article.look').length,2);assert.equal(host.querySelectorAll('.part-error').length,0);assert.doesNotMatch(host.textContent,/重复单品|重复搭配/);dom.window.close();
});
test('card-only history replay displays cards without adding a text message',async()=>{
 const {renderReply}=await mod;const {dom,host}=setup();renderReply(host,{historical_outfit_replay:true,message:'',looks:[{title:'原搭配',pieces:['白衬衫']}],follow_ups:[]});
 assert.equal(host.querySelectorAll('article.look').length,1);assert.equal(host.querySelectorAll('.turn-message').length,0);assert.equal(host.querySelectorAll('button').length,0);dom.window.close();
});
