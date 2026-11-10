const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('stylist/static/app.js','utf8');
const code=source.slice(source.indexOf('async function loadForecast('),source.indexOf('\nfunction pendingBubble'));
function setup(){
 const w=new JSDOM('<div id="feed"></div><div id="location-label"></div><div id="location-status"></div>',{url:'https://fixture.invalid',runScripts:'outside-only'}).window;
 w.calls=[];w.updates=[];w.notices=[];
 w.eval(`let selectedCity=null,forecastScope='day',forecastBusy=false,forecastSequence=0,session={access_token:'owner-a'};
 const CITY_KEY='city';const $=id=>document.getElementById(id);
 const el=(tag,cls,text)=>{const e=document.createElement(tag);e.className=cls||'';e.textContent=text||'';return e;};
 const requireLogin=()=>true,agentText=t=>t,notifyIssue=t=>window.notices.push(t),updateCityLabel=(...args)=>window.updates.push(args);
 const forecastCard=data=>{const card=el('section','fixture-card',data.label);card.append(el('details'));return card;};
 const api=(url,options)=>new Promise((resolve,reject)=>window.calls.push({url,body:JSON.parse(options.body),resolve,reject}));
 ${code}
 window.loadForecast=loadForecast;window.changeOwner=()=>{session={access_token:'owner-b'};};`);
 return w;
}
const flush=async()=>{await new Promise(resolve=>setImmediate(resolve));};
const data=label=>({city_name:'北京市',province_name:'北京市',label});
test('day/week load concurrently once; switching preserves cards and expanded details',async()=>{
 const w=setup(),pending=w.loadForecast({city_name:'北京市'});
 assert.deepEqual(w.calls.map(x=>x.body.scope),['day','week']);
 w.calls[0].resolve(data('today'));await flush();
 const card=w.document.querySelector('#weather-scope-day .fixture-card');card.querySelector('details').open=true;
 const tabs=w.document.querySelectorAll('[role=tab]');tabs[1].click();
 assert.equal(w.document.querySelector('#weather-scope-week').hidden,false);
 w.calls[1].resolve(data('week'));assert.equal(await pending,true);
 for(let i=0;i<5;i++){tabs[0].click();tabs[1].click();}
 tabs[0].click();assert.equal(w.calls.length,2);
 assert.equal(w.document.querySelector('#weather-scope-day .fixture-card'),card);
 assert.equal(card.querySelector('details').open,true);
 w.close();
});
test('one failed scope does not discard the successful scope or refetch on switching',async()=>{
 const w=setup(),pending=w.loadForecast({city_name:'北京市'});
 w.calls[0].resolve(data('today'));w.calls[1].reject(Error('offline'));
 assert.equal(await pending,true);
 assert.equal(w.document.querySelectorAll('.fixture-card').length,1);
 assert(w.document.querySelector('#weather-scope-week .weather-unavailable'));
 w.document.querySelectorAll('[role=tab]')[1].click();assert.equal(w.calls.length,2);w.close();
});
test('late city responses cannot replace the latest city',async()=>{
 const w=setup(),old=w.loadForecast({city_name:'旧城市'}),latest=w.loadForecast({city_name:'北京市'});
 w.calls[2].resolve(data('new day'));w.calls[3].resolve(data('new week'));await latest;
 w.calls[0].resolve(data('old day'));w.calls[1].resolve(data('old week'));
 assert.equal(await old,false);assert(!w.document.body.textContent.includes('old'));
 assert.equal(w.updates.length,1);w.close();
});
test('account change discards both late responses',async()=>{
 const w=setup(),pending=w.loadForecast({city_name:'北京市'});w.changeOwner();
 w.calls[0].resolve(data('private day'));w.calls[1].resolve(data('private week'));
 assert.equal(await pending,false);assert.equal(w.updates.length,0);
 assert.equal(w.document.querySelectorAll('.fixture-card').length,0);w.close();
});
test('both failures settle and a deliberate new load retries exactly two requests',async()=>{
 const w=setup(),pending=w.loadForecast({city_name:'北京市'});
 w.calls[0].reject(Error('offline'));w.calls[1].reject(Error('offline'));
 assert.equal(await pending,false);assert.equal(w.notices.length,1);
 const retry=w.loadForecast({city_name:'北京市'});assert.equal(w.calls.length,4);
 w.calls[2].resolve(data('day'));w.calls[3].resolve(data('week'));assert.equal(await retry,true);w.close();
});
