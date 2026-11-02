const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('stylist/static/app.js','utf8');
const cardSource=source.slice(source.indexOf('function cityInvitation('),source.indexOf('function showReply('));
function setup(){
 const dom=new JSDOM('<body><div id="feed"></div></body>',{runScripts:'outside-only',url:'https://synthetic.test'}),w=dom.window;
 const calls=[],notices=[];let locations=0;
 Object.assign(w,{session:{user:{id:'owner'}},conversation:'conversation',version:2,busy:false,
  el:(tag,cls,text)=>{const n=w.document.createElement(tag);if(cls)n.className=cls;if(text)n.textContent=text;return n;},
  mascot:()=>w.document.createElement('div'),notifyIssue:text=>notices.push(text),
  openCityPicker:async(...args)=>calls.push(args)});
 w.namedElement=w.el;w.navigator.geolocation={getCurrentPosition:()=>locations++};w.eval(cardSource);
 const request={message:'周五搭两套，不穿黄色',request_id:'original'};
 const card=w.cityInvitation({conversation_id:'conversation',version:2},request);w.document.getElementById('feed').append(card);
 return {dom,w,card,calls,notices,request,locations:()=>locations};
}
test('city card does not request geolocation; click opens the picker with an immutable request snapshot',async()=>{
 const t=setup();assert.equal(t.calls.length,0);assert.equal(t.locations(),0);
 t.request.message='later edit';t.card.querySelector('button').click();await Promise.resolve();
 assert.equal(t.calls.length,1);assert.equal(t.locations(),0);
 assert.equal(t.calls[0][0].request.message,'周五搭两套，不穿黄色');
 assert.equal(t.card.querySelector('button').getAttribute('aria-haspopup'),'dialog');t.dom.window.close();
});
for(const [name,change] of [
 ['account',t=>t.w.session={user:{id:'other'}}],['version',t=>t.w.version=3],
 ['conversation',t=>t.w.conversation='new'],['detached card',t=>t.card.remove()],['busy',t=>t.w.busy=true],
])test(name+' prevents a stale city invitation from reopening or resuming',()=>{
 const t=setup();change(t);t.card.querySelector('button').click();assert.equal(t.calls.length,0);assert.equal(t.locations(),0);t.dom.window.close();
});
