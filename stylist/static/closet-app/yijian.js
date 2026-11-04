import {mountHomeWeatherNote} from './home-weather-note.js';
import {needsOnboarding,onboardingURL} from './first-run.js';
import '../companion-characters.js';
import {accountHeader} from './account-header.js';
import {ownTwinCard} from './own-twin.js';
// Presentation only: theme changes never save account or assistant settings.
if (document.documentElement.dataset.appDesign === 'yijian') {
  const root = document.documentElement;
  document.title = '爱搭衣橱 · 日常穿搭与陪伴';
  const $ = id => document.getElementById(id);
  const make = (tag, cls, text) => { const el = document.createElement(tag); el.className = cls; if (text) el.textContent = text; return el; };
  const paths = {
    home: 'M3 10 12 3l9 7M5 9v12h5v-7h4v7h5V9',
    wardrobe: 'M5 3h14v18H5zM12 3v18M9 10v3m6-3v3',
    profile: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 21v-2a8 8 0 0 1 16 0v2',
    add: 'M12 5v14M5 12h14',
    stats: 'M4 20V10m8 10V4m8 16v-7',
    ootd: 'M5 5h14v16H5zM8 3v4m8-4v4M5 10h14M9 14h6',
    diy: 'm8 3-5 4 3 4 2-2v12h8V9l2 2 3-4-5-4a4 4 0 0 1-8 0',
    products: 'M4 8h16l-1 13H5zM8 8V6a4 4 0 0 1 8 0v2',
    chat: 'M4 4h16v13H9l-5 4zM8 8h8M8 12h5',
    records: 'M6 3h12v18H6zM9 7h6M9 11h6M9 15h4',
    mail: 'M3 5h18v14H3zM3 5l9 7 9-7',
    settings: 'M4 6h16M4 12h16M4 18h16M8 4v4m8 2v4m-6 2v4',
    arrow: 'M5 12h14m-5-5 5 5-5 5',
    sparkle: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z'
  };
  function icon(kind) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('aria-hidden','true'); svg.classList.add('y-icon');
    const path = document.createElementNS(svg.namespaceURI,'path'); path.setAttribute('d',paths[kind] || paths.sparkle); svg.append(path); return svg;
  }
  function forward(action) { document.querySelector(`[data-agent="${action}"]`)?.click(); }
  const toolbar = make('header','y-toolbar');
  const brand = make('a','y-brand','爱搭衣橱'); brand.href = '/app/?design=yijian'; brand.append(make('small','','A LITTLE CARE, EVERY DAY'));
  function applyPalette(palette) {
    root.dataset.appPalette = palette;
    document.querySelector('meta[name="theme-color"]').content = palette === 'female' ? '#fbf7f2' : palette === 'system' ? '#ffffff' : '#f4f6f8';
  }
  const homeCity=make('button','y-home-city-button');homeCity.type='button';homeCity.setAttribute('aria-haspopup','dialog');homeCity.setAttribute('aria-controls','location-dialog');homeCity.setAttribute('aria-label','定位城市，点击定位，可手动选择城市');homeCity.innerHTML='<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></svg><span>定位城市</span>';homeCity.onclick=()=>window.dispatchEvent(new CustomEvent('yijian-agent-open',{detail:'city'}));
  const syncHomeCity=()=>{if(document.querySelector('#location-open'))return;let city;try{city=JSON.parse(sessionStorage.getItem('ai-closet-stylist-city-v1')||'null');}catch{}const name=city?.city_name||'定位城市';homeCity.querySelector('span').textContent=name;homeCity.setAttribute('aria-label',name+'，点击定位，可手动选择城市');};syncHomeCity();window.addEventListener('yijian-session-change',syncHomeCity);window.addEventListener('stylist-city-change',syncHomeCity);
  toolbar.append(brand,homeCity); $('app').prepend(toolbar); applyPalette(root.dataset.appPalette);
  const hero = make('section','y-welcome'); hero.setAttribute('aria-label','爱搭衣橱日常');
  const copy=make('div','y-welcome-copy'); copy.append(make('span','y-eyebrow','A LITTLE MOMENT WITH YOU'),make('h1','','今天，穿得像自己。'),make('p','','今天的心情，想用哪件衣服表达？'));
  const heading = copy.querySelector('h1'); heading.replaceChildren(make('span','','今天，'),make('span','','穿得像自己。'));
  const talk=make('button','y-talk','和衣衣聊聊'); talk.append(icon('arrow')); talk.onclick=()=>forward('chat'); copy.append(talk);
  const portrait=make('div','y-portrait'); const avatar=make('div','y-companion-photo'); avatar.setAttribute('role','img'); const scene=make('span','y-companion-scene'); avatar.append(scene); const caption=make('span','y-portrait-caption','衣衣 · 陪你慢慢挑'); portrait.append(avatar,caption);
  const invitation=make('div','y-daily-invitation');invitation.append(make('span','y-daily-mark','✧'),make('p','','不急着决定，先说说今天想怎么过。'));const daily=make('button','y-home-checkin','每日签到');daily.type='button';daily.onclick=()=>window.dispatchEvent(new CustomEvent('yijian-agent-open',{detail:'checkin'}));invitation.append(daily);hero.append(copy,portrait,invitation); $('home').prepend(hero);const homeWeatherNote=mountHomeWeatherNote(invitation.querySelector('p'));
  // Read-only homepage status; claiming still requires the check-in dialog.
  const checkinSession=()=>sessionStorage.getItem('ai-closet-stylist-session-v1') || '';
  const checkinDay=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  let checkinVersion=0,checkinDate=checkinDay();
  function showCheckin(signed){daily.textContent=signed?'已签到':'每日签到';daily.classList.toggle('is-signed',signed);daily.setAttribute('aria-label',signed?'今日已签到，查看签到记录':'每日签到');}
  async function refreshHomeCheckin(){
    const version=++checkinVersion,session=checkinSession(),day=checkinDay();checkinDate=day;showCheckin(false);
    let token;try{token=JSON.parse(session)?.access_token;}catch{}if(!token)return;
    try{const response=await fetch('/stylist-api/app/checkin',{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(!response.ok)return;const body=await response.json();if(version===checkinVersion&&session===checkinSession()&&day===checkinDay())showCheckin(body.data?.signed===true);}catch{/* Unknown status keeps the neutral entry; the dialog offers retry. */}
  }
  window.addEventListener('yijian-session-change',refreshHomeCheckin);
  window.addEventListener('yijian-checkin-claimed',refreshHomeCheckin);
  window.addEventListener('focus',refreshHomeCheckin);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshHomeCheckin();});
  window.addEventListener('storage',e=>{if(e.key==='ai-closet-stylist-session-v1')refreshHomeCheckin();});
  setInterval(()=>{if(!document.hidden&&checkinDate!==checkinDay())refreshHomeCheckin();},60000);
  refreshHomeCheckin();
  const sectionTitle=make('div','y-section-title'); sectionTitle.append(make('span','y-eyebrow','THE DAYS WE KEEP'),make('h2','','把喜欢的搭配，收进这一页。'));
  const feedCopy={album:['THE DAYS WE KEEP','把喜欢的搭配，收进这一页。'],inspiration:['A LITTLE INSPIRATION','看看别样的穿搭，遇见新的灵感。'],activity:['A LITTLE PLAYFULNESS','换一种玩法，发现不一样的自己。']};
  const syncFeedCopy=()=>{const key=document.querySelector('[data-feed][aria-selected="true"]')?.dataset.feed||'album';const text=feedCopy[key]||feedCopy.album;sectionTitle.querySelector('.y-eyebrow').textContent=text[0];sectionTitle.querySelector('h2').textContent=text[1];};
  const feedObserver=new MutationObserver(syncFeedCopy);document.querySelectorAll('[data-feed]').forEach(tab=>feedObserver.observe(tab,{attributes:true,attributeFilter:['aria-selected']}));syncFeedCopy(); $('home-feed').before(sectionTitle);
  const wardrobeTitle=make('div','y-page-intro'); wardrobeTitle.append(make('span','y-eyebrow','YOUR OWN WARDROBE'),make('p','','让已有的衣服，穿出新的心情。')); document.querySelector('.wardrobe-scene h1').after(wardrobeTitle);
  document.querySelector('.profile-top h1').textContent='我的日常';
  document.querySelector('.profile-top [data-agent=checkin]')?.remove();
  const account=accountHeader({make,icon,forward});
  const accountJournal=make('section','y-account-journal');accountJournal.setAttribute('aria-label','我的日常与助理小笺');
  document.querySelector('.profile-top').after(accountJournal);accountJournal.append(account);
  const letter = make('section','y-companion-letter'); letter.setAttribute('aria-label','陪伴小笺');
  const letterPhoto = make('img','y-letter-photo');
  const letterBody = make('div','y-letter-body');
  const letterBy = make('span','y-letter-by','衣衣的日常小笺');
  const letterTitle = make('h2','','今天，也想听听你的想法。');
  const letterCopy = make('p','','一件想穿的衣服，一点今天的心情，都可以聊聊。');
  const letterAction = make('button','y-letter-action','聊聊今天'); letterAction.append(icon('arrow')); letterAction.onclick=()=>forward('chat');
  letterBody.append(letterBy,letterTitle,letterCopy,letterAction);
  letter.append(letterPhoto,letterBody);
  const seal=make('span','y-letter-seal','✧');seal.setAttribute('aria-hidden','true');letter.append(seal);
  accountJournal.append(letter);
  accountJournal.after(document.querySelector('.points-card'));

  document.querySelector('.memory-title').textContent='我们的手记';
  document.querySelector('.memory-card').prepend(make('span','y-memory-kicker','LITTLE THINGS ABOUT YOU'));
  document.querySelector('.profile-menu').before(make('div','y-menu-heading','日常事务 · 在这里打理'));
  const memoryCaption=document.querySelector('.memory-card .pill'); memoryCaption.textContent='翻开手记';
  for (const button of document.querySelectorAll('[data-tab]')) button.prepend(icon(button.dataset.tab));
  const add=$('create-toggle'); add.replaceChildren(icon('add')); add.classList.add('y-add');
  document.querySelectorAll('.quick-actions button').forEach((b,i)=>b.replaceChild(icon(['stats','ootd','diy','products'][i]),b.querySelector('img')));
  document.querySelectorAll('.profile-top .pill').forEach((b,i)=>b.replaceChild(icon(i?'sparkle':'stats'),b.querySelector('img')));
  const wardrobeNote=document.querySelector('.profile-top [data-detail=statistics]');
  wardrobeNote.className='y-wardrobe-note';
  const wardrobeNoteCopy=make('span','y-wardrobe-note-copy');
  wardrobeNoteCopy.append(make('strong','','衣橱小记'),make('small','','查看衣橱统计'));
  wardrobeNote.replaceChildren(icon('stats'),wardrobeNoteCopy,make('span','y-wardrobe-note-arrow','›'));
  document.querySelector('.feature-cards').after(wardrobeNote);
  document.querySelectorAll('.feature-cards button').forEach((b,i)=>b.replaceChild(icon(i?'diy':'records'),b.querySelector('img')));
  document.querySelectorAll('.profile-menu button').forEach((b,i)=>b.replaceChild(icon(['records','mail','chat','mail','settings'][i]),b.querySelector('img')));
  document.querySelectorAll('.create-scroll button:not(.close)').forEach((b,i)=>b.replaceChild(icon(['chat','diy','products','diy','ootd'][i]),b.querySelector('img')));
  document.querySelector('.create-scroll > p').textContent='从一件衣服开始，慢慢找到喜欢的自己。';
  document.querySelector('.create-scroll h2').textContent='给日常，添一笔';
  document.querySelector('.identity .pencil').hidden=true;
  const identity=document.querySelector('.identity'),identityCopy=identity.querySelector('div');
  document.querySelector('.memory-card').after(identity);
  const portraitButton=identity.querySelector('.avatar'),selfPortrait=make('div','y-identity-photo');selfPortrait.append(icon('profile'),$('account-avatar'));portraitButton.replaceWith(selfPortrait);
  identityCopy.classList.add('y-identity-copy');identityCopy.prepend(make('span','y-identity-eyebrow','爱搭衣橱 · 我的日常'));
  const shapeLink=identityCopy.querySelector('.identity-edit');shapeLink.textContent='挑选试穿模样';shapeLink.setAttribute('aria-label','挑选我的试穿形象');shapeLink.append(icon('arrow'));
  const identityDescription=make('p','y-identity-description','喜欢的衣服，也想看看穿上的样子。');shapeLink.before(identityDescription);
  ownTwinCard({card:identity,photo:selfPortrait,copy:identityCopy,action:shapeLink,make});


  // Names/images come from the saved companion, never from the palette selection.
  const personas = new Set(['female_sweet_v1','female_warm_v1','female_regal_v1','male_artistic_v1','male_calm_v1','male_confident_v1']);
  let welcomeBank=null, latestWelcomeProfile=null;
  const welcomePicks=new Map();
  fetch('/static/closet-app/welcome-copy.json').then(r=>{if(!r.ok)throw new Error('copy');return r.json();}).then(bank=>{welcomeBank=bank;renderCompanion(latestWelcomeProfile);}).catch(()=>{});
  function renderCompanion(profile) {
    latestWelcomeProfile=profile;
    const persona=personas.has(profile?.assistant_persona)?profile.assistant_persona:'male_calm_v1';homeWeatherNote.setPersona(persona);
    const name=profile?.agent_name || '衣衣';
    const variants=welcomeBank?.[persona];
    if(variants?.length){
      if(!welcomePicks.has(persona)){
        let previous=-1;try{previous=Number(sessionStorage.getItem('yijian-welcome-'+persona)??-1);}catch{}
        let index=Math.floor(Math.random()*variants.length);
        if(index===previous)index=(index+1+Math.floor(Math.random()*(variants.length-1)))%variants.length;
        welcomePicks.set(persona,index);try{sessionStorage.setItem('yijian-welcome-'+persona,String(index));}catch{}
      }
      const selected=variants[welcomePicks.get(persona)];
      const comma=selected.title.indexOf('，');
      heading.replaceChildren(...(comma>=0?[selected.title.slice(0,comma+1),selected.title.slice(comma+1)]:[selected.title]).map(line=>make('span','',line)));
      copy.querySelector('p').textContent=selected.description;
    }

    const character=window.CompanionCharacters.find(persona);
    avatar.style.setProperty('--scene-image',`url("/static/assets/characters/companion-scenes-v2/${persona}-hero.png")`);
    ['x1','y1','x2','y2','rx','ry'].forEach((key,index)=>avatar.style.setProperty('--eye-'+key,character.blinkEyes[index]+'%'));
    letterPhoto.src=`/static/assets/characters/companion-scenes-v1/${persona}-avatar.png`; letterPhoto.alt=`${name}，你的搭配助理`; letterBy.textContent=`${name}的日常小笺`;
    avatar.setAttribute('aria-label',`${name}，日常搭配助理`); caption.textContent=`${name} · 陪你慢慢挑`; talk.firstChild.textContent=`和${name}聊聊`;
  }
  function applySavedProfile(profile) {
    let ownerToken='';try{ownerToken=JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')||'null')?.access_token||'';}catch{}
    window.dispatchEvent(new CustomEvent('yijian-user-profile',{detail:{profile,ownerToken}}));
    account.setDisplayName(profile?.user_name);
    renderCompanion(profile);
    applyPalette(profile?.color_scheme === 'system' ? 'system' : profile?.assistant_persona?.startsWith('female_') ? 'female' : 'male');
  }
  let version=0;
  async function refreshCompanion() {
    const request=++version; renderCompanion(null);
    let session; try { session=JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')); } catch {}
    if (!session?.access_token) { applySavedProfile(null); return; }
    try {
      const response=await fetch('/stylist-api/companion-profile',{headers:{Authorization:`Bearer ${session.access_token}`},cache:'no-store'});
      if (!response.ok) return;
      const body=await response.json(); if (request===version && JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1') || 'null')?.access_token === session.access_token) { if(needsOnboarding(body.profile)){location.assign(onboardingURL);return;} applySavedProfile(body.profile); }
    } catch {}
  }
  window.addEventListener('companion-profile-change',e=>{version++;applySavedProfile(e.detail);});
  $('agent-frame').addEventListener('load',()=>{
    $('agent-frame').contentWindow.addEventListener('companion-profile-change',e=>{version++;applySavedProfile(e.detail);});
  });
  window.addEventListener('storage',e=>{
    if (e.key==='ai-closet-stylist-session-v1') refreshCompanion();
  });
  window.addEventListener('yijian-session-change', refreshCompanion);
  const layers = [$('create-overlay'), $('detail-page'), $('agent-page')];
  const modalObserver = new MutationObserver(() => { toolbar.inert = layers.some(layer => !layer.hidden); });
  layers.forEach(layer => modalObserver.observe(layer, {attributes:true, attributeFilter:['hidden']}));
  refreshCompanion();
}
