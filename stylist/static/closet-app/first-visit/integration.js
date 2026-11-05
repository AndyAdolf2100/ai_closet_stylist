// In-App read-only walkthroughs. Real account APIs remain owned by the existing App.
const root=document.documentElement;
if(root.dataset.appDesign==='yijian'&&!new URLSearchParams(location.search).has('screen'))mount();
function mount(){
 const VERSION='v2',KEY='ai-closet-stylist-session-v1',labels={upload:'添加单品到合成试穿',profile:'我的页面',memory:'我们的手记',chat:'开始对话'};
 let active=null,owner='',opener=null,profile=null,profileOwner=null,profileToken='',checkQueued=false;
 const sessionToken=()=>{try{return JSON.parse(sessionStorage.getItem(KEY)||'null')?.access_token||'';}catch{return '';}};
 const volatile=new Set();let unidentifiedToken='',unidentifiedVersion=0;
 function account(){try{const s=JSON.parse(sessionStorage.getItem(KEY)||'null');if(!s?.access_token)return 'guest';const id=s.user?.id??s.user?.user_id??s.user_id??s.owner_id;if(id!=null)return 'user:'+String(id);if(unidentifiedToken!==s.access_token){unidentifiedToken=s.access_token;unidentifiedVersion++}return 'session:'+unidentifiedVersion}catch{return 'guest'}}
 const marker=(who,tour)=>`closet-guide:${VERSION}:${who}:${tour}`;
 function seen(who,tour){if(volatile.has(marker(who,tour)))return true;try{return localStorage.getItem(marker(who,tour))==='seen'}catch{return false}}
 function remember(who,tour){if(who===null)return;volatile.add(marker(who,tour));if(who.startsWith('session:'))return;try{localStorage.setItem(marker(who,tour),'seen')}catch{/* Optional local persistence never blocks the App. */}}
 const dialog=document.createElement('dialog');dialog.id='first-visit-guide';dialog.dataset.firstVisit='true';dialog.setAttribute('aria-label','功能引导');
 dialog.innerHTML='<div class="first-visit-picker" hidden><p>我陪你慢慢熟悉，先从哪件事开始？</p><button data-guide-tour="upload">添加单品 → 创建分身 → 合成试穿</button><button data-guide-tour="profile">我的页面 →</button><button data-guide-tour="memory">我们的手记 →</button><button data-guide-tour="chat">开始对话 →</button><button type="button" data-guide-close>先到这里</button></div><iframe title="功能操作引导" hidden></iframe>';
 document.body.append(dialog);const frame=dialog.querySelector('iframe'),picker=dialog.querySelector('.first-visit-picker');
 const style=document.createElement('link');style.rel='stylesheet';style.href='/static/closet-app/first-visit/integration.css';document.head.append(style);
 function sendProfile(){if(!frame.contentWindow||!active)return;const p=profileOwner===account()&&profileToken===sessionToken()?profile:null;frame.contentWindow.postMessage({type:'closet-guide-profile',profile:p||{},palette:root.dataset.appPalette},location.origin)}
 frame.addEventListener('load',sendProfile);
 function open(tour=null){if(account()===null)return;if(!dialog.open){opener=document.activeElement;owner=account();dialog.showModal()}active=tour;picker.hidden=!!tour;frame.hidden=!tour;dialog.classList.toggle('is-picker',!tour);dialog.setAttribute('aria-label',tour?labels[tour]:'功能引导');if(tour){const url=new URL('/static/closet-app/first-visit/index.html',location.origin);url.searchParams.set('tour',tour);url.searchParams.set('embed','1');if(['system','male','female'].includes(root.dataset.appPalette))url.searchParams.set('app_palette',root.dataset.appPalette);if(root.dataset.appPalette==='system')url.searchParams.set('color','system');frame.src=url.href;}else frame.removeAttribute('src')}
 function close(mark=true){if(mark&&active&&account()===owner)remember(owner,active);active=null;frame.removeAttribute('src');if(dialog.open)dialog.close();if(opener?.isConnected)opener.focus({preventScroll:true})}
 dialog.querySelector('[data-guide-close]').onclick=()=>close();dialog.querySelectorAll('[data-guide-tour]').forEach(b=>b.onclick=()=>open(b.dataset.guideTour));dialog.addEventListener('cancel',e=>{e.preventDefault();close()});
 dialog.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();close()}},true);
 window.addEventListener('message',e=>{if(e.origin!==location.origin||e.source!==frame.contentWindow||e.data?.type!=='closet-guide-finished'||e.data.tour!==active)return;close()});
 function surface(){if(document.querySelector('#memory-dialog[open]'))return 'memory';if(!document.querySelector('#agent-page')?.hidden&&document.querySelector('#message'))return 'chat';if(!document.querySelector('#profile')?.hidden)return 'profile';if(!document.querySelector('#home')?.hidden)return 'upload';return null}
 style.onload=()=>queue();
 function check(){checkQueued=false;if(!style.sheet)return;const who=account();if(dialog.open){if(who!==owner){profile=null;profileOwner=null;close(false)}return}if(who===null||document.querySelector('dialog[open]:not(#memory-dialog),#create-overlay:not([hidden]),#detail-page:not([hidden])'))return;const tour=surface();if(!tour||seen(who,tour))return;if(tour==='memory'&&document.querySelector('#memory-loading:not([hidden]),#memory-retry:not([hidden])'))return;if(tour==='upload'&&!document.querySelector('.y-toolbar'))return;if(tour==='chat'&&!document.querySelector('#message')?.getBoundingClientRect().width)return;open(tour)}
 function queue(){if(!checkQueued){checkQueued=true;requestAnimationFrame(check)}}
 function addHelp(){const toolbar=document.querySelector('.y-toolbar');if(toolbar&&!toolbar.querySelector('[data-guide-help]')){const help=document.createElement('button');help.type='button';help.dataset.guideHelp='true';help.className='first-visit-help';help.textContent='功能引导';help.onclick=()=>open();toolbar.append(help)}}
 // Watch actual visible App surfaces rather than hashes changed via pushState.
 const app=document.querySelector('#app');if(app)new MutationObserver(()=>{addHelp();queue()}).observe(app,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden']});
 for(const event of ['yijian-session-change','storage','popstate'])window.addEventListener(event,()=>{if(dialog.open&&account()!==owner){profile=null;profileOwner=null;close(false)}queue()});
 window.addEventListener('companion-profile-change',e=>{profile=e.detail;profileOwner=account();profileToken=sessionToken();sendProfile();queue()});
 window.addEventListener('yijian-user-profile',e=>{if(e.detail?.ownerToken!==sessionToken())return;profile=e.detail.profile;profileOwner=account();profileToken=sessionToken();sendProfile();queue();});
 new MutationObserver(sendProfile).observe(root,{attributes:true,attributeFilter:['data-app-palette']});
 const watched=new WeakSet();function watchAgent(){const agent=document.getElementById('yijian-agent-root');if(agent&&!watched.has(agent)){watched.add(agent);new MutationObserver(queue).observe(agent,{subtree:true,attributes:true,attributeFilter:['open','hidden']})}queue()}document.addEventListener('yijian-agent-mounted',watchAgent);watchAgent();
 window.addEventListener('closet-guide-open',e=>open(Object.hasOwn(labels,e.detail)?e.detail:null));
 addHelp();queue();
}
