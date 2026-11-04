const SESSION='ai-closet-stylist-session-v1',CITY='ai-closet-stylist-city-v1';
const tips={
 female_sweet_v1:'舒服打底，再添一点小巧思呀。',
 female_warm_v1:'先选穿着舒服的，再慢慢搭配。',
 female_regal_v1:'选一处亮点，让搭配更利落。',
 male_artistic_v1:'留一点色彩，给今天添些新意。',
 male_calm_v1:'先定主色，再理清搭配层次。',
 male_confident_v1:'挑你喜欢的，穿得自在就好。'
};
function read(key){try{return JSON.parse(sessionStorage.getItem(key)||'null')}catch{return null}}
function day(){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}
function cityKey(city){return city?.city_name?JSON.stringify([city.province_name||'',city.city_name]):''}
function number(value){return value!==null&&value!==''&&value!==undefined&&Number.isFinite(Number(value))?Number(value):null}
export function weatherSummary(data,city,today=day()){
 const row=data?.days?.find(row=>row.date===today);
 const condition=row?.condition_day||row?.condition_night;
 const low=number(row?.temp_min),high=number(row?.temp_max);
 if(!condition||low===null||high===null||low>high)throw Error('today_weather_unavailable');
 return {city:city.city_name,weather:condition,temperature:low===high?`${low}℃`:`${low}–${high}℃`};
}
export function mountHomeWeatherNote(element){
 let persona='male_calm_v1',sequence=0,controller=null,loadingKey='',owner=read(SESSION)?.user?.id??read(SESSION)?.access_token??null,blockedCity='';
 const cache=new Map();
 function snapshot(){const session=read(SESSION),city=read(CITY);return{session,city,date:day(),owner:session?.user?.id??session?.access_token??null,key:JSON.stringify([session?.access_token||'',cityKey(city),day()])}}
 function invalidate(){sequence++;controller?.abort();controller=null;loadingKey=''}
 function text(value,mode){element.replaceChildren(document.createTextNode(value));element.dataset.mode=mode;element.title=value;element.setAttribute('aria-label',value)}
 function tip(){text(tips[persona]||tips.male_calm_v1,'tip')}
 function display(summary){element.replaceChildren();element.dataset.mode='weather';for(const [index,key]of ['city','weather','temperature'].entries()){if(index){const dot=document.createElement('span');dot.className='y-home-weather-separator';dot.textContent='·';dot.setAttribute('aria-hidden','true');element.append(dot)}const span=document.createElement('span');span.className='y-home-weather-'+key;span.textContent=summary[key];element.append(span)}const label=`今日天气预报：${summary.city} · ${summary.weather} · ${summary.temperature}`;element.title=label;element.setAttribute('aria-label',label)}
 async function refresh({confirmed=false,forecast=null}={}){
  const state=snapshot();
  if(state.owner!==owner){invalidate();cache.clear();owner=state.owner;blockedCity=cityKey(state.city)}
  if(confirmed)blockedCity='';
  if(!state.session?.access_token||!state.city?.city_name||blockedCity===cityKey(state.city)&&blockedCity){invalidate();tip();return}
  if(forecast){try{const summary=weatherSummary(forecast,state.city,state.date);invalidate();cache.set(state.key,{summary,expires:Date.now()+600000});display(summary);return}catch{/* A weekly or incomplete result is not today's summary. */}}
  const saved=cache.get(state.key);if(saved&&saved.expires>Date.now()){display(saved.summary);return}
  if(loadingKey===state.key)return;
  invalidate();const current=sequence;controller=new AbortController();loadingKey=state.key;
  text(`${state.city.city_name} · 正在查看天气…`,'loading');
  try{
   const response=await fetch('/stylist-api/weather/forecast',{method:'POST',headers:{Authorization:'Bearer '+state.session.access_token,'Content-Type':'application/json'},body:JSON.stringify({location:state.city,scope:'day',event_date:state.date}),signal:controller.signal,cache:'no-store'});
   if(!response.ok)throw Error('weather_unavailable');const data=await response.json();
   if(current!==sequence||snapshot().key!==state.key)return;
   const summary=weatherSummary(data,state.city,state.date);cache.set(state.key,{summary,expires:Date.now()+600000});display(summary);
  }catch(error){if(error.name!=='AbortError'&&current===sequence&&snapshot().key===state.key)text(`${state.city.city_name} · 天气暂未取到`,'unavailable')}
  finally{if(current===sequence)loadingKey=''}
 }
 window.addEventListener('stylist-city-change',event=>refresh(event.detail||{}));
 window.addEventListener('yijian-session-change',()=>refresh());
 window.addEventListener('storage',event=>{if([SESSION,CITY].includes(event.key))refresh()});
 window.addEventListener('focus',()=>refresh());
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});
 setInterval(()=>{if(!document.hidden)refresh()},60000);
 refresh();
 return {setPersona(value){persona=value;if(element.dataset.mode==='tip')tip()},refresh};
}
