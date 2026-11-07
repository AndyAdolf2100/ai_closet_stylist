import {ensureOnboarded,loginURL,sessionToken} from './first-run.js';
import {listRefresh} from './list-refresh.js';
import {emptyArt} from './empty-art.js';
// Mount existing business controllers directly. No iframe or second document.
let ready;
const triggers=new Map();
const ids={login:'login-open',history:'mobile-history',upload:'upload-open',twins:'twin-open',records:'journey-records-open',memory:'memory-open',settings:'companion-open',preferences:'preferences-open',checkin:'checkin-open',logout:'logout'};
const scripts=['appearance','companion-loading','wardrobe-journey','closet-app/checkin-direct','weather-visuals','product-preview','cutout-core','local-cutout','outfit-images','outfit-board','city-picker','companion-characters','companion-settings','fashion-preferences','preferences','memory','app'];
export function mountAgent(){
  if(ready)return ready;
  ready=(async()=>{
    const host=document.createElement('div');host.id='yijian-agent-root';host.style.display='none';
    const response=await fetch('/static/closet-app/agent-fragment.html');if(!response.ok)throw Error('页面暂时没能加载，请重试。');
    host.innerHTML=await response.text();host.querySelector('main>footer>.fine-print')?.remove();document.getElementById('agent-frame')?.remove();document.body.append(host);host.dataset.surface='overlay';
    const scoped=document.createElement('link');scoped.rel='stylesheet';scoped.href='/static/closet-app/agent-scoped.css?v=weather-system-v8';document.head.append(scoped);
    await new Promise((resolve,reject)=>{scoped.onload=resolve;scoped.onerror=reject;});
    const theme=document.createElement('link');theme.rel='stylesheet';theme.href='/static/closet-app/agent-yijian.css';document.head.append(theme);await new Promise((resolve,reject)=>{theme.onload=resolve;theme.onerror=reject;});
    const sync=()=>{for(const a of document.documentElement.attributes)if(a.name.startsWith('data-'))host.setAttribute(a.name,a.value);};
    sync();new MutationObserver(sync).observe(document.documentElement,{attributes:true});
    // Agent modules create their dialogs on body; keep App-owned dialogs in their native modal layer.
    const relocate=()=>{for(const child of [...document.body.children])if(child.matches('dialog:not([data-first-visit]):not([data-app-dialog]),#companion-notification'))host.append(child);};
    const observer=new MutationObserver(relocate);observer.observe(document.body,{childList:true});
    for(const name of scripts){if(name==='app')for(const id of Object.values(ids)){const element=document.getElementById(id);if(element)triggers.set(id,element);}await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='/static/'+name+'.js';script.onload=resolve;script.onerror=()=>reject(Error('组件没能加载，请刷新页面。'));document.body.append(script);});relocate();}
    for(const id of Object.values(ids)){const element=document.getElementById(id);if(element)triggers.set(id,element);}
    const cityBar=document.createElement('div');cityBar.className='y-agent-city';
    const cityButton=document.createElement('button');cityButton.type='button';cityButton.className='y-agent-city-button';cityButton.setAttribute('aria-haspopup','dialog');cityButton.setAttribute('aria-controls','location-dialog');
    cityButton.innerHTML='<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></svg><span></span>';
    const header=document.querySelector('#agent-page>header');
    const heading=document.createElement('div');heading.className='y-agent-heading';
    const cityCaption=document.createElement('span');cityCaption.className='y-agent-city-caption';cityCaption.hidden=true;
    heading.append(header.querySelector(':scope>span'),cityCaption);header.append(heading);
    const headerActions=document.createElement('div');headerActions.className='y-agent-header-actions';
    cityBar.append(cityButton);headerActions.append(cityBar,header.querySelector('#agent-account'));header.append(headerActions);
    const citySource=host.querySelector('#location-open');let locating=false;
    const syncCity=()=>{const text=citySource.textContent.replace(/^⌖\s*/, '');const hasCity=!!text.trim()&&!text.includes('选择城市');const name=hasCity?text:'定位城市';cityButton.dataset.hasCity=String(hasCity);cityCaption.textContent=hasCity?text:'';cityCaption.title=hasCity?text:'';cityCaption.hidden=!hasCity;for(const button of [cityButton,document.querySelector('.y-home-city-button')].filter(Boolean)){button.querySelector('span').textContent=locating?'正在定位…':name;button.disabled=locating||citySource.disabled;button.setAttribute('aria-label',name+'，点击定位，可手动选择城市');button.title=locating?'正在定位…':name;}};
    new MutationObserver(syncCity).observe(citySource,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled']});syncCity();
    // 原生迁移要求：点击这里必须调用系统定位；不是只打开选城列表。
    // Native iOS parity contract: this entry must trigger CLLocationManager location
    // permission + requestLocation() on a user tap (with NSLocationWhenInUseUsageDescription).
    // Feed WGS84 coordinates to the existing authenticated location/resolve contract;
    // retain city confirmation, denial/timeout manual picker, account/close cancellation.
    // Never request permission on launch, silently pick a default city, or auto-send chat.
    // H5 adapter below reuses the browser geolocation implementation and its guards.
    cityButton.onclick=async(event)=>{if(locating||citySource.disabled)return;locating=true;syncCity();try{await window.openCityPicker(null,event?.currentTarget||cityButton);if(host.querySelector('#location-dialog').open)await host.querySelector('#locate-me').onclick();}catch(error){window.PreviewMessage.notify(error.message||'暂时没能定位，可以手动选择城市。');}finally{locating=false;syncCity();}};
    const updateWelcomePortrait=()=>{
      const profile=window.CompanionSettings?.getProfile();
      const character=window.CompanionCharacters.find(profile?.assistant_persona);
      host.querySelector('.welcome-character .hero-mascot')?.setAttribute('aria-label',`${profile?.agent_name||'衣衣'}，${character.label}的陪伴形象`);
    };
    updateWelcomePortrait();window.addEventListener('companion-profile-change',updateWelcomePortrait);
    document.getElementById('new-chat').textContent='＋ 新对话';
    host.querySelector('.journey-entry')?.append(document.getElementById('journey-records-open'));
    const entry=host.querySelector('.journey-entry');
    if(entry){entry.setAttribute('role','group');entry.setAttribute('aria-label','衣橱与试穿快捷入口');
      const entries=[['welcome-upload','添加衣服','收进个人衣橱','m8 3-5 4 3 4 2-2v12h8V9l2 2 3-4-5-4a4 4 0 0 1-8 0'],['twin-open','试穿形象','遇见自己的新模样','M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8M5 21v-2a7 7 0 0 1 14 0v2'],['journey-records-open','生成记录','回看每次小尝试','M5 3h14v18H5zM9 7h6M9 11h6M9 15h4']];
      for(const [id,title,description,path]of entries){const button=document.getElementById(id);if(!button)continue;button.innerHTML='<span class="y-entry-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="'+path+'"/></svg></span><strong class="y-entry-title"></strong><small class="y-entry-description"></small>';button.querySelector('strong').textContent=title;button.querySelector('small').textContent=description;button.setAttribute('aria-label',title+'，'+description);}
    }

    const loginHeading=host.querySelector('#login-dialog h2');if(loginHeading)loginHeading.textContent='很高兴，在这里遇见你。';
    const loginIntro=host.querySelector('#login-form>p');if(loginIntro)loginIntro.textContent='登录已有账号，从你的衣橱开始，慢慢聊聊你的喜欢。';
    const memoryMark=document.querySelector('#memory-empty>span');if(memoryMark)memoryMark.replaceWith(emptyArt('journal'));
    const historyRefresh=document.getElementById('history-refresh');
    historyRefresh.classList.add('y-history-refresh-fallback');
    listRefresh(document.getElementById('history-dialog'),()=>historyRefresh.disabled?Promise.resolve():historyRefresh.onclick());
    const decorateJourney=()=>{
      const historyEmpty=host.querySelector('#history-status');if(historyEmpty?.textContent==='还没有聊过的日常，开始聊聊吧。')historyEmpty.textContent='第一句话，还等你来写。想聊什么，都可以从今天开始。';
      const recordEmpty=host.querySelector('.journey-history-empty');if(recordEmpty?.textContent==='还没有记录，可以先上传一件常穿的衣服。')recordEmpty.textContent='这一页还空着。挑一件常穿的衣服，让今天的小尝试有个开始。';
      const grid=host.querySelector('.journey-portraits');
      if(grid&&!grid.childElementCount){const empty=document.createElement('div');empty.className='y-twin-empty';empty.append(emptyArt('journal'));const caption=document.createElement('p');caption.textContent='这一页，等一个你的模样';empty.append(caption);grid.append(empty);}
      host.querySelectorAll('.journey-dialog button').forEach(button=>{if(button.textContent==='刷新人物状态'){button.classList.add('y-state-update');button.setAttribute('aria-label','更新人物生成状态');button.title='更新人物生成状态';button.textContent='↻';}});
    };
    new MutationObserver(decorateJourney).observe(host,{childList:true,subtree:true});decorateJourney();
    let historyPick=false,historyUpdated=false;
    document.getElementById('mobile-history-list').addEventListener('click',e=>{if(e.target.closest('button')){historyPick=true;historyUpdated=false;}},true);
    new MutationObserver(()=>{if(historyPick)historyUpdated=true;}).observe(document.getElementById('feed'),{childList:true});
    document.getElementById('history-dialog').addEventListener('close',()=>{if(historyPick&&historyUpdated)window.dispatchEvent(new CustomEvent('yijian-agent-open',{detail:'chat'}));historyPick=false;historyUpdated=false;});
    document.getElementById('message').addEventListener('focus',()=>{if(host.dataset.surface==='overlay')window.dispatchEvent(new CustomEvent('yijian-agent-open',{detail:'chat'}));});

    const attachment=host.querySelector('#upload-open');
    attachment.classList.add('y-composer-icon');attachment.setAttribute('aria-label','添加附件');attachment.title='添加附件';
    attachment.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>';
    const voice=document.createElement('button');voice.type='button';voice.id='y-voice-input';voice.className='y-composer-icon';voice.setAttribute('aria-label','语音输入');voice.title='语音输入';
    voice.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 11v2m4-5a6 6 0 0 1 0 8m4-11a10 10 0 0 1 0 14m4-17a14 14 0 0 1 0 20"/></svg>';
    // iOS integration: replace this Web-only notice with native voice input.
    // Request microphone permission only on user action (AVAudioSession); use the existing
    // AgentVoiceInteraction recording/transcription flow, including cancel, interruption and
    // permission denial. Transcription must populate the draft, never auto-send or spend points.
    // Web deliberately does not call getUserMedia, SpeechRecognition or upload audio.
    voice.onclick=()=>{const notify=window.CompanionSettings?.notify||window.PreviewMessage.notify;notify('语音输入将在 iOS App 中提供，当前网页可以先打字或添加图片。');};
    attachment.before(voice);
    const {mountChatAttachments}=await import('./chat-attachments.js');
    mountChatAttachments(host, attachment);
    const {mountCompactComposer}=await import('./compact-composer.js');
    mountCompactComposer(host,voice,attachment);


    // Keep the existing authenticated submit handler while giving login its own two steps.
    const mobile=document.getElementById('mobile'),code=document.getElementById('code'),submit=document.getElementById('login-submit');
    const phoneLabel=mobile.closest('label'),codeLabel=code.closest('label'),actions=submit.parentElement;
    const next=document.createElement('button');next.type='button';next.className='primary';next.textContent='继续';actions.append(next);
    const back=document.createElement('button');back.type='button';back.className='subtle';back.textContent='返回修改手机号';codeLabel.after(back);
    function loginStep(verify){codeLabel.hidden=!verify;back.hidden=!verify;submit.hidden=!verify;next.hidden=verify;code.required=verify;mobile.readOnly=verify;if(!verify)code.value='';}
    next.onclick=()=>{if(!/^1[3-9][0-9]{9}$/.test(mobile.value)){window.PreviewMessage.notify('请填写正确的手机号。');mobile.focus();return;}loginStep(true);code.focus();};back.onclick=()=>{loginStep(false);mobile.focus();};
    document.getElementById('login-dialog').addEventListener('close',()=>{loginStep(false);let session;try{session=JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1'));}catch{}if(!session?.access_token)delete host.dataset.resumeChat;});loginStep(false);

    const accountLabel=document.getElementById('login-label');if(accountLabel)new MutationObserver(()=>{window.dispatchEvent(new CustomEvent('yijian-session-change'));if(host.dataset.resumeChat==='true'){let session;try{session=JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1'));}catch{}if(session?.access_token){delete host.dataset.resumeChat;window.dispatchEvent(new CustomEvent('yijian-agent-open',{detail:'chat'}));}}}).observe(accountLabel,{childList:true,subtree:true});
    for(const id of ['mobile-new','new-chat'])document.getElementById(id).addEventListener('click',()=>{const tab=location.hash.slice(1).split('/')[0]||'home';history.replaceState({tab,view:'agent'},'',`#${tab}/agent`);},true);
    host.addEventListener('close',()=>queueMicrotask(()=>{if(host.dataset.surface==='overlay'&&!host.querySelector('dialog[open]'))window.dispatchEvent(new CustomEvent('yijian-overlay-closed'));}),true);
    host.style.removeProperty('display');
    document.dispatchEvent(new CustomEvent('yijian-agent-mounted'));
    return host;
  })();
  return ready;
}
export async function openIntegratedAgent(action){
  if(action==='login'||(!sessionToken()&&action!=='logout')){location.assign(loginURL());return;}
  if(action!=='logout'&&!await ensureOnboarded())return;
  const host=await mountAgent();
  let authenticated=false;try{authenticated=!!JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')||'null')?.access_token;}catch{}
  if(action==='city'){await document.querySelector('.y-agent-city-button')?.onclick({currentTarget:document.querySelector('.y-home-city-button')});return;}
  if(action==='person-upload'){
    if(!authenticated){host.querySelector('#login-open')?.click();return;}
    const token=JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')).access_token;
    const response=await fetch('/stylist-api/twins',{headers:{Authorization:'Bearer '+token},cache:'no-store'});const overview=await response.json();
    if(JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')||'null')?.access_token!==token)return;
    if(!response.ok)throw Error(overview.message||'分身信息暂未读取，请稍后重试。');
    if(overview.need_gender)await window.WardrobeJourney.twins();else window.WardrobeJourney.upload('person');return;
  }
  if(action==='chat'&&!authenticated){host.dataset.resumeChat='true';host.querySelector('#login-open')?.click();return;}
  if(action==='upload'){window.WardrobeJourney.upload('garment');return;}
  const trigger=ids[action];if(trigger)(triggers.get(trigger)||host.querySelector('#'+trigger))?.click();else host.querySelector('#message')?.focus();
}
export function closeIntegratedAgent(){
  const host=document.getElementById('yijian-agent-root');if(!host)return;
  for(const dialog of host.querySelectorAll('dialog[open]')){dialog.dispatchEvent(new Event('cancel',{cancelable:true}));if(dialog.open)dialog.close();}
}

export function placeIntegratedAgent(chat){const host=document.getElementById('yijian-agent-root');if(!host)return;host.dataset.surface=chat?'chat':'overlay';if(chat)document.getElementById('agent-page').append(host);else document.body.append(host);}
