const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('stylist/static/app.js','utf8');
const start=source.indexOf('async function api(');
const apiSource=source.slice(start,source.indexOf('\nconst compositionPath',start));
function setup(fetch){
 const expired=[];
 const context=vm.createContext({session:{user:{id:'a'},access_token:'token-a'},fetch,headers:()=>({Authorization:'Bearer synthetic'}),
  expireSession:message=>expired.push(message),error:(code,message)=>Object.assign(new Error(message),{code})});
 vm.runInContext(apiSource,context);return {context,expired};
}
test('a late 401 from the previous account must not log out the current account',async()=>{
 let complete;const t=setup(()=>new Promise(resolve=>complete=resolve));
 const pending=t.context.api('/stylist-api/media');t.context.session={user:{id:'b'},access_token:'token-b'};
 complete({ok:false,status:401,json:async()=>({code:'authentication_expired',message:'旧账号过期'})});
 await assert.rejects(pending,e=>e.code==='stale_account');assert.deepEqual(t.expired,[]);
});
test('an HTML proxy 413 becomes an actionable image-size message',async()=>{
 const t=setup(async()=>({ok:false,status:413,json:async()=>{throw new SyntaxError('html');}}));
 await assert.rejects(t.context.api('/stylist-api/media/uploads'),e=>e.code==='invalid_response'&&e.message.includes('10MB'));
});
test('an unexpected successful HTML page does not masquerade as a saved task',async()=>{
 const t=setup(async()=>({ok:true,status:200,json:async()=>{throw new SyntaxError('html');}}));
 await assert.rejects(t.context.api('/stylist-api/twins'),e=>e.code==='invalid_response');
});
