const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('stylist/static/app.js','utf8');
const render=source.slice(source.indexOf('  for (const item of reply.product_results || [])'),source.indexOf('  const productEntry = reply.product_entry;'));
function setup(){
 const dom=new JSDOM('<main></main>',{url:'https://wardrobe.invalid'}),w=dom.window;
 let session={access_token:'fixture-a'},conversation='one',version=1;const calls=[];
 w.openSubjectConversation=async entry=>calls.push(entry);
 const el=(tag,cls,text)=>{const n=w.document.createElement(tag);n.className=cls||'';if(text)n.textContent=text;return n;};
 const draw=new Function('reply','node','el','window','session','conversation','version','busy','requireLogin',render);
 return {dom,w,calls,draw:(reply)=>draw(reply,w.document.querySelector('main'),el,w,session,conversation,version,false,()=>true),switchOwner:()=>{session.access_token='fixture-b';}};
}
test('single product results show separate cards with beautified images and real subject links',async()=>{
 const t=setup();t.draw({conversation_id:'one',version:1,product_results:[
  {source:'user',product_id:'12',title:'黑色上衣',cutout_image:'https://images.invalid/beautified.png',original_image:'https://images.invalid/original.jpg'},
  {source:'user',product_id:'13',title:'黑色鞋子',original_image:'https://images.invalid/shoes.jpg'}]});
 const cards=t.w.document.querySelectorAll('.product-search-card');assert.equal(cards.length,2);
 assert.equal(cards[0].querySelector('img').src,'https://images.invalid/beautified.png');
 assert.equal(cards[1].querySelector('img').src,'https://images.invalid/shoes.jpg');assert.equal(t.calls.length,0);
 await cards[0].querySelector('button').onclick();assert.deepEqual(t.calls,[{subject_product:{source:'user',product_id:'12'}}]);
 t.switchOwner();await cards[1].querySelector('button').onclick();assert.equal(t.calls.length,1);
 cards[0].querySelector('img').onerror();assert.match(cards[0].querySelector('img').src,/original/);
 t.dom.window.close();
});
test('unsafe images, text injection and stale conversation cards cannot act',async()=>{
 const t=setup();t.draw({conversation_id:'old',version:1,product_results:[{source:'user',product_id:'12',title:'<script>bad</script>',cutout_image:'javascript:alert(1)'}]});
 assert.equal(t.w.document.querySelectorAll('img,script').length,0);
 assert.match(t.w.document.querySelector('main').textContent,/<script>/);
 await t.w.document.querySelector('button').onclick();assert.equal(t.calls.length,0);t.dom.window.close();
});
