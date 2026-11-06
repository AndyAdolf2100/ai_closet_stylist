// Optional onboarding city selection. Coordinates stay in the resolver request only.
export function mountLocation(root,{live,getToken,ownerToken,getAccessToken=getToken,getCity=()=>null,onSelect=()=>{}}){
 const make=(tag,text='')=>{const e=document.createElement(tag);e.textContent=text;return e;};
 const key='ai-closet-stylist-city-v1';let sequence=0,dialog=null,chosen=null,opener=null;
 const current=()=>root.isConnected&&(!live||getToken()===ownerToken);
 root.className='onboarding-location';root.setAttribute('aria-label','穿搭天气城市设置');
 const title=make('h3','也想替你，留意晴雨');
 const copy=make('p','告诉我你所在的城市，让每次搭配，也多一份对天气的照顾。');
 const status=make('p','仅用于穿搭参考天气，可稍后开启。');status.setAttribute('role','status');
 const actions=make('div');actions.className='onboarding-location-actions';
 const locate=make('button','开启定位');locate.className='onboarding-location-enable';locate.setAttribute('aria-label','开启定位');locate.setAttribute('aria-haspopup','dialog');
 for(const b of [locate]){b.type='button';actions.append(b)}
 root.append(title,copy,status,actions);
 if(live){try{const city=getCity()||JSON.parse(sessionStorage.getItem(key)||'null');if(city?.city_name)status.textContent='已选择'+city.city_name+'，之后的穿搭会按需参考这里的天气。';}catch{}}
 const invalidate=()=>{sequence++;dialog?.close();dialog?.remove();dialog=null;};
 const observer=new MutationObserver(()=>{if(!current()){invalidate();observer.disconnect();window.removeEventListener('yijian-session-change',onSession);}});
 observer.observe(document.getElementById('screen'),{childList:true});
 function onSession(){if(!current()){invalidate();status.textContent='账号已变化，请重新进入引导设置城市。';for(const button of [locate])button.disabled=true;}}window.addEventListener('yijian-session-change',onSession);
 async function open(useLocation,trigger){
  if(!current()||dialog)return;
  opener=trigger;const epoch=++sequence;
  dialog=make('dialog');dialog.className='onboarding-city-dialog';dialog.setAttribute('aria-label','选择穿搭城市');
  const heading=make('h2','选择你的城市');heading.id='onboarding-city-title';dialog.setAttribute('aria-labelledby',heading.id);const hint=make('p','定位结果仍需你确认，也可以手动选城。');hint.setAttribute('role','status');
  const pickerRoot=make('div'),confirm=make('button','确认城市'),cancel=make('button','关闭 ×'),retry=make('button','重新定位');confirm.disabled=true;
  for(const b of [confirm,cancel,retry])b.type='button';
  const header=make('header');header.className='onboarding-city-heading';const titleGroup=make('div');const eyebrow=make('small','A LITTLE WEATHER CARE');titleGroup.append(eyebrow,heading);cancel.setAttribute('aria-label','关闭城市选择');header.append(titleGroup,cancel);const intro=make('p','选到城市就好，不需要具体地址。');intro.className='onboarding-city-intro';hint.className='onboarding-city-status';pickerRoot.className='onboarding-city-picker';retry.className='onboarding-city-retry';confirm.className='onboarding-city-confirm';const buttons=make('div');buttons.className='onboarding-city-footer';buttons.append(confirm,make('small','确认后，为之后的穿搭参考天气。'));dialog.append(header,intro,retry,hint,pickerRoot,buttons);document.body.append(dialog);dialog.showModal();cancel.focus();
  const alive=()=>current()&&sequence===epoch&&dialog?.open;
  dialog.addEventListener('close',()=>{sequence++;dialog?.remove();dialog=null;if(opener?.isConnected)opener.focus({preventScroll:true});});
  cancel.onclick=()=>dialog.close();
  let picker,locationAttempt=0;
  try{
   await import('/static/city-picker.js');
   const response=await fetch('/static/china-cities.json');if(!response.ok)throw Error('城市列表暂时没能打开，可以稍后再试。');const catalog=await response.json();if(!alive())return;
   picker=new CityPicker(pickerRoot,{onChange:()=>{locationAttempt++;retry.disabled=false;chosen=picker.getValue();confirm.disabled=!chosen;}});picker.setCatalog(catalog);
  }catch(error){if(alive())hint.textContent=error.message;return;}
  confirm.onclick=()=>{if(!alive()||!picker.getValue())return;const city=picker.getValue();onSelect(city);status.textContent=(live?'已选择':'预览已选择')+city.city_name+'，之后的穿搭会按需参考这里的天气。';dialog.close();};
  async function locateCity(){
   if(!alive()||retry.disabled)return;
   if(!live){picker.setValue({city_name:'上海市',province_name:'上海市'});chosen=picker.getValue();confirm.disabled=!chosen;hint.textContent='预览示例：上海市。未申请定位，也不会保存城市。';return;}
   if(!getAccessToken()){hint.textContent='新账号可先手动选城；完成引导后即可使用定位。';return;}
   if(!window.isSecureContext||!navigator.geolocation){hint.textContent='当前环境暂不支持定位，手动选择城市也可以。';return;}
   // Native iOS must request system location on this tap, then use the same WGS84 resolver.
   const attempt=++locationAttempt;const locating=()=>alive()&&attempt===locationAttempt;retry.disabled=true;hint.textContent='请允许访问位置；不想开启也可以手动选择城市。';
   try{
    const position=await new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,reject,{enableHighAccuracy:true,timeout:15000,maximumAge:60000}));if(!locating())return;
    const response=await fetch('/stylist-api/location/resolve',{method:'POST',headers:{Authorization:'Bearer '+ownerToken,'Content-Type':'application/json'},body:JSON.stringify({latitude:position.coords.latitude,longitude:position.coords.longitude,coordinate_system:'wgs84'})});const city=await response.json();if(!locating())return;
    if(!response.ok)throw Error(city.message||'暂时没能识别城市，请手动选择。');
    if(!picker.setValue(city))throw Error('已识别到'+city.city_name+'，请在列表中选择对应城市。');chosen=picker.getValue();confirm.disabled=!chosen;hint.textContent='找到'+chosen.city_name+'啦，请确认后使用。';
   }catch(error){if(locating())hint.textContent=error.code===1?'定位未开启也没关系，手动选一座城市吧。':error.code===3?'定位等得有点久，可以再试一次，或手动选择。':error.message||'暂时没能定位，可以手动选择城市。';}
   finally{if(locating())retry.disabled=false;}
  }
  retry.onclick=locateCity;if(useLocation)await locateCity();
 }
 locate.onclick=()=>open(true,locate);
}
