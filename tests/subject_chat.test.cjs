const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const moduleReady=import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync('stylist/static/closet-app/subject-chat.js','utf8')).toString('base64'));
async function setup(kind,item,openAgent=async()=>{}){
 const {subjectChatButton}=await moduleReady;
 let owner='account-a';const calls=[];
 const control=subjectChatButton(kind,item,{
  button:(text,action)=>({text,action,disabled:false,isConnected:true}),
  readSession:()=>({access_token:owner}),
  openAgent:async(...args)=>{calls.push(args);await openAgent();}
 });
 return {control,calls,switchOwner:()=>{owner='account-b';}};
}
test('a product link preserves the exact ID and blocks a stale account',async()=>{
 const t=await setup('product',{user_product_id:'12345678901234567890',product_id:999});
 await t.control.action();assert.deepEqual(t.calls,[['chat',{subject_product:{source:'user',product_id:'12345678901234567890'}}]]);
 t.switchOwner();await t.control.action();assert.equal(t.calls.length,1);
});
test('saved outfit links block duplicate clicks while opening',async()=>{
 let finish;const t=await setup('outfit',{outfit_id:72,outfit_id_type:2},()=>new Promise(resolve=>finish=resolve));
 const pending=t.control.action();await t.control.action();assert.equal(t.calls.length,1);
 assert.deepEqual(t.calls[0],['chat',{subject_outfit:{source:'user',outfit_id:72}}]);
 finish();await pending;assert.equal(t.control.disabled,false);
});
test('missing IDs, unsafe outfit IDs and unsupported generated IDs cannot submit',async()=>{
 for(const [kind,item]of[['product',{}],['product',{product_id:99}],['product',{user_product_id:Number.MAX_SAFE_INTEGER+1}],['outfit',{outfit_id:Number.MAX_SAFE_INTEGER+1}],['outfit',{outfit_id:72,outfit_id_type:1}],['outfit',{outfit_id:72,outfit_id_type:0}]]){
  const t=await setup(kind,item);assert(t.control.disabled);await t.control.action();assert.equal(t.calls.length,0);
 }
});

test('home discussions carry visible copy without pretending to be saved outfits',async()=>{
 const t=await setup('discussion',{id:72,title:'首页造型',description:'白衬衫配灰裤'});
 await t.control.action();assert.deepEqual(t.calls,[['chat',{discussion:{title:'首页造型',description:'白衬衫配灰裤'}}]]);
});

test('H5 entry labels are short while structured references remain unchanged',async()=>{
 const product=await setup('product',{user_product_id:'12'});assert.equal(product.control.text,'聊聊这件');
 const outfit=await setup('outfit',{outfit_id:72,outfit_id_type:2});assert.equal(outfit.control.text,'聊聊这套');
 await product.control.action();await outfit.control.action();
 assert.deepEqual(product.calls,[['chat',{subject_product:{source:'user',product_id:'12'}}]]);
 assert.deepEqual(outfit.calls,[['chat',{subject_outfit:{source:'user',outfit_id:72}}]]);
});
