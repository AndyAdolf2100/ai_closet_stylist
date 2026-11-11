'use strict';
const $ = id => document.getElementById(id);
const agentName = () => window.CompanionSettings?.agentName() || '衣衣';
const agentText = text => text.replaceAll('衣衣', agentName());
const KEY = 'ai-closet-stylist-session-v1';
let session = null, conversation = null, version = 0, busy = false;
let selectedLook = null, activeChatRun = null;
let outfitGroupSequence = 0;
let selectedCity = null, forecastScope = 'day', forecastBusy = false, forecastSequence = 0;
const CITY_KEY = 'ai-closet-stylist-city-v1';
try { selectedCity = JSON.parse(sessionStorage.getItem(CITY_KEY) || 'null'); } catch { selectedCity = null; }
try { session = JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch { session = null; }
let lastSessionOwner = session?.user?.id || null;
let cityCatalog = null, historySequence = 0;
const citiesReady = fetch('/static/china-cities.json').then(r => { if (!r.ok) throw new Error('城市列表加载失败，请刷新后重试。'); return r.json(); }).then(data => {
  cityCatalog = data; cityPicker.setCatalog(data); return data;
}).catch(err => { notifyIssue(err.message); return null; });
const el = (tag, cls, text) => { const node = document.createElement(tag); if (cls) node.className = cls; if (text != null) node.textContent = text; return node; };
let locationSequence = 0, locationSaving = false, locationContinuation = null, locationOpener = null;
const cityPicker = new CityPicker($('city-picker'), { onChange: () => {
  locationSequence++; $('locate-me').disabled = locationSaving;
  $('location-status').textContent = ''; updateLocationSave();
} });
function updateLocationSave() { $('location-save').disabled = locationSaving || !cityPicker.getValue(); }
const error = (code, message) => Object.assign(new Error(message), { code });
const dailyCheckin = window.DailyCheckin.mount({
  onLogin: () => requireLogin(),
  onChat: () => { if (requireLogin()) { $('message').focus(); window.CompanionSettings.notify('聊聊今天的穿搭吧，收到回复后就可以领取签到奖励。'); } }
});
const newClothesNotices = new Set();
let newClothesOwner = session?.user?.id ?? null;
function newClothesExplanation(persona) {
  const lines = {
    female_sweet_v1: '把衣橱之外的可能，也交给我挑挑吧。开启后，你的衣服和衣橱外的参考新款都能加入搭配，一起找点新鲜感。',
    female_warm_v1: '想试点不一样的，就让我陪你看看。开启后，搭配时可以一起挑选你已有的衣服和衣橱外的参考新款。',
    female_regal_v1: '把选择放宽些，新意也值得一试。开启后，我会从你的衣橱和衣橱外的参考新款里一起挑选，看看哪种更衬你。',
    male_artistic_v1: '一起去衣橱之外，找一点新灵感。开启后，你已有的衣服和衣橱外的参考新款都能加入接下来的搭配。',
    male_calm_v1: '想试点不一样的，我陪你去衣橱外找找灵感。搭配时，你已有的衣服和新的参考款，都可以一起选。',
    male_confident_v1: '这次试点新的，我来挑。开启后，你的衣服和衣橱外的参考新款都能加入搭配，喜欢哪种由你定。'
  };
  return lines[persona] || lines.male_calm_v1;
}
function setNewClothes(value, {explain = false} = {}) {
  if ($('new-clothes')) $('new-clothes').checked = !!value;
  if ($('personal-clothes')) $('personal-clothes').checked = !value;
  if (value && explain) {
    const persona = window.CompanionSettings?.getProfile()?.assistant_persona
      || (document.documentElement.dataset.stylistGender === 'female' ? 'female_warm_v1' : 'male_calm_v1');
    window.CompanionSettings?.notify(newClothesExplanation(persona));
  }
}
$('new-clothes')?.addEventListener('change', event => {
  if (!busy && event.target.checked && !event.target.disabled) setNewClothes(true, {explain:true});
});
function loginStatus() {
  window.ChatAttachments?.clear();
  const owner = session?.user?.id ?? null;
  if (owner !== newClothesOwner) { setNewClothes(false); newClothesNotices.clear(); newClothesOwner = owner; }
  window.WardrobeJourney?.setOwner(session?.user?.id ?? null);
  if (!session || pendingAnchorOwner !== session.user.id) { pendingUploadAnchor = null; pendingAnchorOwner = null; updateUploadAnchor(); }
  window.LocalCutout?.setOwner(session?.user?.id ?? null);
  window.OutfitImages?.setOwner(session?.user?.id ?? null);
  $('login-label').textContent = session ? '衣橱已连接' : '登录衣橱';
  $('login-open').classList.toggle('is-connected', !!session);
  $('login-open').setAttribute('aria-label', session ? '衣橱已连接，点击重新登录或切换账号' : '登录衣橱');
  $('login-open').title = session ? '重新登录或切换账号' : '连接你的个人衣橱';
  dailyCheckin.setOwner(session?.user?.id ?? null);
}
let pendingUploadAnchor = null, pendingAnchorOwner = null;
function updateUploadAnchor() {
  const row = $('upload-anchor'); if (!row) return;
  row.hidden = !pendingUploadAnchor; row.replaceChildren();
  if (pendingUploadAnchor) {
    const cancel = el('button', 'journey-anchor-remove', '×'); cancel.type = 'button';
    cancel.setAttribute('aria-label','取消以这件衣物为搭配起点');cancel.title='取消这件单品';
    cancel.onclick = () => { pendingUploadAnchor = null; updateUploadAnchor(); };
    const mark=el('span','journey-anchor-mark','✧');mark.setAttribute('aria-hidden','true');
    row.append(mark,el('span', 'journey-anchor-copy', '从这件开始搭'), cancel);
  }
}
function notifyIssue(message) { window.CompanionSettings.notify(message || '操作未完成，请稍后再试。'); }
function expireSession(message) {
  window.OutfitBoard?.close();
  lastSessionOwner = session?.user?.id || lastSessionOwner;
  session = null; sessionStorage.removeItem(KEY); window.CompanionSettings?.setOwner(null, api); loginStatus();
  clearHistory();
  const loginMessage = message || '登录状态已失效，请重新登录。原输入和当前对话会保留。';
  for (const id of ['service-dialog', 'location-dialog', 'history-dialog', 'companion-dialog']) if ($(id).open) $(id).close();
  if (!$('login-dialog').open) $('login-dialog').showModal();
  notifyIssue(loginMessage);
}
function headers() { return { 'Content-Type': 'application/json', Authorization: 'Bearer ' + (session?.access_token || '') }; }
window.LocalCutout?.setSourceLoader(async (item, signal, kind='original') => {
  if (!session || !['user','system'].includes(item.source) || !/^[1-9][0-9]{0,19}$/.test(item.product_id)) throw Error('image_unavailable');
  const path = item.source === 'system'
    ? '/stylist-api/conversations/' + encodeURIComponent(item._conversation) + '/catalog/' + item.product_id + '/image-source?version=' + item._version + '&kind=' + kind
    : '/stylist-api/wardrobe/' + item.product_id + '/image-source?kind=' + kind;
  const response = await fetch(path, {headers: headers(), signal, cache:'no-store'});
  if (!response.ok) {
    if (response.status === 401) expireSession();
    throw Error('image_unavailable');
  }
  return response.blob();
});
function requireLogin() { if (!session) { $('login-dialog').showModal(); return false; } return true; }
async function api(path, options = {}) {
  const requestOwner = session?.user?.id, requestToken = session?.access_token;
  const response = await fetch(path, { ...options, headers: headers() });
  const data = await response.json().catch(() => null);
  if (requestOwner !== session?.user?.id || requestToken !== session?.access_token) {
    throw error('stale_account', '账号已变化，已忽略上一账号的请求结果。');
  }
  if (!response.ok || data === null) {
    if (response.status === 401) expireSession(data?.message);
    const issue=error(data?.code || 'invalid_response', data?.message || (response.status === 413
      ? '图片过大，请选择10MB以内的图片。' : '服务暂时未完成请求，请稍后重试。'));
    issue.paymentHandled=globalThis.AppPayment?.handleError(issue)===true;
    throw issue;
  }
  if(data?.status==='failed'&&data?.result?.error_code)globalThis.AppPayment?.handleError({code:data.result.error_code,message:data.result.message});
  return data;
}
const compositionPath = ref => '/stylist-api/conversations/' + encodeURIComponent(ref.conversationId) + '/composition';
const compositionQuery = ref => new URLSearchParams({version:ref.version,look_index:ref.index,theme:ref.theme});
window.OutfitImages?.configure({
  load: ref => api(compositionPath(ref)+'?'+compositionQuery(ref)),
  save: ref => api(compositionPath(ref), {method:'POST',body:JSON.stringify({version:ref.version,look_index:ref.index,theme:ref.theme,image_data:ref.image_data,retry:ref.retry})}),
  download: async ref => {
    const response=await fetch(compositionPath(ref)+'/download?'+compositionQuery(ref),{headers:headers(),cache:'no-store'});
    if(!response.ok){if(response.status===401)expireSession();throw Error('下载未完成，请稍后重试。');}
    return response.blob();
  }
});
const savedOutfitPath = ref => '/stylist-api/conversations/' + encodeURIComponent(ref.conversationId) + '/saved-outfit';
window.OutfitLibrary = {
  status: ref => api(savedOutfitPath(ref)+'?'+new URLSearchParams({version:ref.version,look_index:ref.index})),
  save: (ref, includeSystem) => api(savedOutfitPath(ref), {method:'POST',body:JSON.stringify({version:ref.version,look_index:ref.index,include_system:includeSystem})})
};
const feed = $('feed');
let followLatest = false, bottomFrame = null, unreadContent = false;
const bottomButton = $('scroll-bottom');
const newContentLabel=el('span','new-content-label','有新内容');newContentLabel.hidden=true;bottomButton.append(newContentLabel);
function markNewContent(){if(!followLatest){const wasUnread=unreadContent;unreadContent=true;updateBottomButton();if(!wasUnread&&unreadContent)window.AgentTracking?.track('AgentNewContentShow');}}
function updateBottomButton() {
  const atBottom=feed.scrollHeight-feed.clientHeight-feed.scrollTop<=48;
  if(atBottom)unreadContent=false;
  bottomButton.hidden=atBottom;
  bottomButton.classList.toggle('has-new-content',unreadContent);
  newContentLabel.hidden=!unreadContent;
  bottomButton.setAttribute('aria-label',unreadContent?'有新内容，查看最新消息':'回到最新消息');
}
bottomButton.onclick = () => { scrollBottom(); feed.tabIndex = -1; feed.focus({preventScroll:true}); };
function scrollBottom(force = true) {
  if (force) followLatest = true;
  if (!followLatest || bottomFrame !== null) return;
  // Wait until the whole message (including loading/cards) has been inserted.
  bottomFrame = requestAnimationFrame(() => {
    bottomFrame = null;
    if (followLatest) feed.scrollTop = feed.scrollHeight;
    updateBottomButton();
  });
}
feed.addEventListener('scroll', () => {
  followLatest = feed.scrollHeight - feed.clientHeight - feed.scrollTop <= 48;
  updateBottomButton();
}, { passive: true });
// Observe message heights as well as the viewport: images, wrapped progress
// text and the mobile keyboard can all change the bottom after insertion.
const feedResize = new ResizeObserver(() => { updateBottomButton(); scrollBottom(false); });
feedResize.observe(feed);
const observedMessages = new Set();
new MutationObserver(records => {
  if(records.some(r=>!r.target.closest?.('.pending')&&(r.type==='characterData'||[...r.addedNodes].some(n=>(n.nodeType===1&&!n.matches('.pending'))||(n.nodeType===3&&n.textContent.trim())))))markNewContent();
  for (const node of observedMessages) {
    if (node.parentElement !== feed) { feedResize.unobserve(node); observedMessages.delete(node); }
  }
  for (const node of feed.children) {
    if (!observedMessages.has(node)) { feedResize.observe(node); observedMessages.add(node); }
  }
  scrollBottom(false);
}).observe(feed, { childList: true, subtree: true, characterData: true });
for (const node of feed.children) { feedResize.observe(node); observedMessages.add(node); }
function mascot(mood = 'greeting', size = '') {
  const node = el('div', 'mascot companion-sprite ' + size); node.dataset.mood = mood;
  // Offset each portrait so a conversation does not blink in unison.
  node.style.setProperty('--blink-delay', `-${(Math.random() * 15).toFixed(2)}s`);
  node.setAttribute('role', 'img'); node.dataset.agentAriaTemplate = ({ greeting: '衣衣向你打招呼', weather: '衣衣查看天气', wardrobe: '衣衣挑选衣服', thinking: '衣衣认真思考', happy: '衣衣展示搭配', rain: '衣衣撑伞提醒' }[mood] || '衣衣'); node.setAttribute('aria-label', agentText(node.dataset.agentAriaTemplate));
  return node;
}
function weatherIcon(text) { return /雪/.test(text) ? '❄' : /雷/.test(text) ? '⛈' : /雨/.test(text) ? '☂' : /雾|霾/.test(text) ? '〰' : /阴|云/.test(text) ? '☁' : '☀'; }
function forecastCard(data, compact = false) {
  const card = el('section', 'forecast-card');
  if (data.days?.length === 1) card.classList.add('forecast-single');
  WeatherVisuals.background(card, data.days);
  const heading = el('div', 'forecast-heading'); const wet = data.days?.some(day => /雨|雪/.test(day.condition_day + day.condition_night)); heading.append(mascot(wet ? 'rain' : 'weather', 'weather-mascot'));
  const title = el('div'); title.append(el('strong', '', `${data.city_name} · ${data.scope === 'week' ? '本周天气' : data.scope === 'next7' ? '未来七天' : '出门天气'}`), namedElement('p', '', '衣衣的天气小叮咛')); heading.append(title);
  card.append(heading);
  const days = el('div', 'forecast-days');
  for (const day of data.days || []) {
    const tile = el('article', 'forecast-day');
    tile.append(el('span', 'day-date', `${day.date.slice(5)} ${day.weekday}`), el('span', 'weather-symbol', weatherIcon(day.condition_day + day.condition_night)), el('strong', '', `${day.temp_min}–${day.temp_max}°C`), el('span', '', `${day.condition_day} / ${day.condition_night}`));
    days.append(tile);
  }
  card.append(days);
  if (data.days?.length === 1) {
    const periods = el('div', 'weather-periods');
    for (const period of (data.days[0].periods || []).filter(period => period.key !== 'morning')) {
      const part = el('div'); part.append(el('strong', '', period.label), el('p', '', period.temp == null ? '暂无逐小时温度' : `${period.temp}°C · ${period.condition}`));
      part.append(el('small', '', period.note)); periods.append(part);
    }
    if (periods.childNodes.length) card.append(periods);
  }
  const alerts = el('div', 'weather-alerts');
  const groupedTips = data.days?.length > 1;
  if (groupedTips) alerts.classList.add('weather-alerts-by-day');
  for (const day of data.days || []) {
    const tips = day.reminders?.length ? day.reminders : [{
      kind: 'daily', severity: 'notice', title: '日常穿衣小叮咛',
      text: '按当天温度与活动安排增减衣物，出门前留意最新预报。'
    }];
    let container = alerts;
    if (groupedTips) {
      const group = el('section', 'weather-tip-day');
      const heading = el('h4', 'weather-tip-date');
      const date = el('time', '', day.date.slice(5)); date.dateTime = day.date;
      heading.append(date, el('span', '', day.weekday)); group.append(heading);
      container = el('div', 'weather-tip-list'); group.append(container); alerts.append(group);
    }
    for (const tip of tips) {
      const row = el('div', 'weather-tip ' + tip.severity);
      row.append(el('span', 'tip-icon', { rain: '☂', snow: '❄', fog: '〰', wind: '彡', layers: '♡', cold: '❄', cool: '❄', heat: '☀', storm: 'ϟ' }[tip.kind] || '✿'));
      const copy = el('div'); copy.append(el('strong', '', tip.title), el('p', '', tip.text)); row.append(copy); container.append(row);
    }
  }
  if (alerts.childNodes.length) card.append(alerts);
  const details = el('details', 'weather-evidence'); details.append(el('summary', '', '预报范围与数据说明'));
  for (const text of data.warnings || []) details.append(el('p', '', text));
  if (data.fetched_at) details.append(el('p', '', `查询时间：${new Date(data.fetched_at).toLocaleString('zh-CN')} · ${data.timezone || 'Asia/Shanghai'}`));
  details.append(el('p', '', data.notice)); card.append(details);
  if (compact) card.classList.add('compact');
  return card;
}
function updateCityLabel(confirmed=false,forecast=null) { $('location-open').textContent = selectedCity ? '⌖ ' + selectedCity.city_name : '⌖ 选择城市 / 定位'; window.dispatchEvent(new CustomEvent('stylist-city-change',{detail:{confirmed,forecast}})); }
// Official warning UI is paused until a verified provider and message delivery are ready (AGENTS.md TODO-01).
async function loadForecast(location = selectedCity) {
  const explicitlySelected=arguments.length>0;
  if (!location || !requireLogin()) return false;
  const sequence = ++forecastSequence, owner = session?.access_token;
  const current = () => sequence === forecastSequence && session?.access_token === owner;
  forecastBusy = true;
  $('location-label').textContent = agentText('衣衣正在看看天气…');
  let panel = $('weather-panel');
  if (!panel) { panel = el('section'); panel.id = 'weather-panel'; $('feed').prepend(panel); }
  panel.hidden = false; panel.replaceChildren();
  const tabs = el('div', 'weather-tabs'), views = new Map(), buttons = new Map();
  tabs.setAttribute('role', 'tablist');
  const select = scope => {
    if (!current()) return;
    forecastScope = scope;
    for (const [key, view] of views) {
      view.hidden = key !== scope;
      buttons.get(key).classList.toggle('active', key === scope);
      buttons.get(key).setAttribute('aria-selected', String(key === scope));
    }
  };
  panel.append(tabs);
  for (const [scope, label] of [['day', '今天 · 早晚'], ['week', '本周 · 逐日']]) {
    const button = el('button', '', label), view = el('div', 'weather-scope');
    button.type = 'button'; button.setAttribute('role', 'tab');
    button.setAttribute('aria-controls', 'weather-scope-' + scope);
    view.id = 'weather-scope-' + scope; view.setAttribute('role', 'tabpanel');
    view.append(el('p', 'weather-loading', '天气正在加载…'));
    views.set(scope, view); buttons.set(scope, button);
    button.onclick = () => select(scope);
    tabs.append(button); panel.append(view);
  }
  select(forecastScope);
  const results = await Promise.allSettled(['day', 'week'].map(async scope => {
    try {
      const data = await api('/stylist-api/weather/forecast', {
        method: 'POST', body: JSON.stringify({ location, scope })
      });
      if (current()) views.get(scope).replaceChildren(forecastCard(data, true));
      return data;
    } catch (err) {
      if (current()) views.get(scope).replaceChildren(el('p', 'weather-unavailable',
        '这部分天气暂未取到，可以先查看另一页，或重新选择城市重试。'));
      throw err;
    }
  }));
  if (!current()) return false;
  forecastBusy = false;
  const success = results.find(result => result.status === 'fulfilled');
  if (success) {
    const data = success.value;
    selectedCity = { city_name: data.city_name, province_name: data.province_name };
    sessionStorage.setItem(CITY_KEY, JSON.stringify(selectedCity));
    updateCityLabel(explicitlySelected, data);
    $('location-label').textContent = '出门前，再照顾一下天气';
    return true;
  }
  $('location-label').textContent = '天气暂未取到，可重新选择城市重试';
  $('location-status').textContent = '';
  notifyIssue(results[0].reason.message);
  return false;
}

function pendingBubble(persona) {
  const node = bubble('assistant', ''); node.classList.add('pending');
  const lines = {
    female_sweet_v1:['收到啦，让我想一想。','你提到的小细节，我记着呢。','舒服和好看，都想替你顾到。'],
    female_warm_v1:['我在，先想想你的需要。','你的喜欢，我会认真放在心上。','希望这次的建议，让你觉得自在。'],
    female_regal_v1:['你的想法，值得认真对待。','风格可以鲜明，也可以很自在。','合你心意，比追赶潮流更重要。'],
    male_artistic_v1:['收到，给灵感一点空隙。','日常的衣服，也能有新的心情。','想让这次的建议，多一点你的味道。'],
    male_calm_v1:['收到，我想一想。','你说的要求，我都记着。','合适和舒服，我们都顾到。'],
    male_confident_v1:['收到，这次按你的喜欢来。','穿得自在，才是你的主场。','不用急着定风格，喜欢就值得试试。']
  };
  const copy=lines[persona]||lines.male_calm_v1;
  let index=0,ticks=0,stopped=false;
  const body = window.CompanionLoading.create({persona,message:copy[0],detail:'正在等待回复。'});
  body.classList.add('companion-wait');node.append(body);
  const timer=setInterval(()=>{
    if(stopped)return;
    if(!node.isConnected){clearInterval(timer);return;}
    ticks++;index=(index+1)%copy.length;
    window.CompanionLoading.update(body,{message:copy[index],detail:ticks>=5?'这次回复慢一些，还在等待，你可以随时停止。':'正在等待回复。'});
  },6000);
  return {node,update(data){body.dataset.stage=data.stage||'styling';},stop(){stopped=true;clearInterval(timer);node.remove();}};
}

function revealReplyText(text, pendingNode) {
  const node=bubble('assistant','');node.classList.add('reply-preview');
  feed.insertBefore(node,pendingNode);pendingNode.hidden=true;const copy=node.lastElementChild;
  const chars=Array.from(text),reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  let frame=null,finished=false,shown=0,resolve;const done=new Promise(r=>resolve=r),start=performance.now();
  const duration=reduce?0:Math.min(2400,chars.length*16);
  function finish(){if(finished)return;finished=true;if(frame!==null)cancelAnimationFrame(frame);copy.textContent=text;resolve();}
  function tick(now){
    if(finished)return;
    const raw=duration?Math.min(chars.length,Math.ceil((now-start)/duration*chars.length)):chars.length;
    const count=raw===chars.length?raw:Math.floor(raw/3)*3;
    if(count>shown){const part=el('span','reply-text-part',chars.slice(shown,count).join(''));copy.append(part);shown=count;}
    if(count===chars.length&&(reduce||now-start>=duration+240))finish();else frame=requestAnimationFrame(tick);
  }
  frame=requestAnimationFrame(tick);
  return {node,done,finish,cancel(){if(finished)return;finished=true;if(frame!==null)cancelAnimationFrame(frame);resolve();},remove(){finish();node.remove();}};
}
function namedElement(tag, cls, template) {
  const node = el(tag, cls, agentText(template)); node.dataset.agentTemplate = template; return node;
}
function bubble(role, text) {
  $('welcome')?.remove();
  const node = el('section', 'bubble ' + role);
  if (role === 'assistant') { const author = el('div', 'author'); author.append(mascot('greeting', 'avatar-mini'), namedElement('span', '', '衣衣 · 私人搭配师')); node.append(author); }
  node.append(el('div', '', text)); feed.append(node); scrollBottom(role === 'user'); return node;
}
function bulletSection(card, title, items) {
  if (!items?.length) return;
  card.append(el('h4', '', title)); const list = el('ul');
  for (const item of items) list.append(el('li', '', item)); card.append(list);
}
function productGrid(items) {
  const grid = el('div', 'products');
  for (const item of items) {
    const product = el('div', 'product');
    const urls = [item.cutout_image, item.original_image].map(value => (value || '').replace(/^http:/i, 'https:')).filter(value => /^https:\/\//i.test(value));
    const url = urls[0] || '';
    const missing = () => el('div', 'product-image-missing', '暂无衣物图片');
    if (url && /^https:\/\//i.test(url)) {
      const img = el('img'); img.src = url; img.alt = (item.color || '') + (item.secondary_class_name || item.class_name || '单品');
      img.loading = 'lazy'; img.referrerPolicy = 'no-referrer';
      const imageButton = el('button', 'product-image'); imageButton.type = 'button';
      imageButton.dataset.previewSrc = url;
      imageButton.setAttribute('aria-label', '放大查看' + img.alt);
      img.onerror = () => {
        if (urls[1] && img.src !== urls[1]) { img.src = urls[1]; return; }
        imageButton.replaceWith(missing());
      };
      imageButton.append(img); product.append(imageButton);
    }
    if (!url) product.append(missing());
    product.append(el('div', '', (item.color || '') + (item.secondary_class_name || item.class_name || item.title || '单品')));
    product.append(el('span', '', item.source === 'user' ? '个人衣橱' : '参考款 · 未确认拥有')); grid.append(product);
  }
  return grid;
}
function cityInvitation(reply, request) {
  const owner = session?.user?.id;
  const reference = {owner, conversation_id:reply.conversation_id, version:reply.version, request:request ? JSON.parse(JSON.stringify(request)) : null};
  const card = el('section', 'city-invite'); card.setAttribute('aria-label', '穿搭天气城市引导');
  const header = el('div', 'city-invite-heading'), portrait = el('span', 'city-invite-portrait'); portrait.setAttribute('aria-hidden', 'true');
  const art = el('span', 'city-invite-character companion-dialogue-avatar'); art.setAttribute('aria-hidden','true');
  portrait.append(art);
  const copy = el('div', 'city-invite-copy');
  copy.append(namedElement('span', 'city-invite-speaker', '衣衣的小笺'), el('h3', '', '让这套穿搭，也照顾天气'));
  header.append(portrait, copy);
  const body = el('p', '', '选一下你要穿这套衣服的城市，我看看那里的冷暖，再接着搭。');
  const action = el('button', 'city-invite-action', '选择城市 / 定位'); action.type='button';action.setAttribute('aria-haspopup','dialog');
  action.onclick = async () => {
    if (busy) return;
    if (!card.isConnected || session?.user?.id !== owner || conversation !== reference.conversation_id || version !== reference.version) {
      notifyIssue('对话已有更新，请从最新的穿搭需求继续。'); return;
    }
    await openCityPicker(reference, action);
  };
  const star = el('span', 'city-invite-star', '✧');star.setAttribute('aria-hidden','true');
  card.append(star,header,body,action,el('small','city-invite-note','可以搜索城市，也可以使用当前位置'));
  return card;
}
function wardrobeGapCard(reply, request) {
  const owner = session?.user?.id, cid = reply.conversation_id, turn = reply.version;
  const card = el('section', 'journey-invite new-clothes-invite');
  card.setAttribute('aria-label', '搭配还差一点的选择');
  const hasItems = reply.looks?.some(look => look.items?.length);
  const gapText = hasItems ? '这次找到的衣物还没能配齐。' : '这份文字参考还没有匹配到真实单品。';
  const nextText = reply.new_clothes
    ? '可以添加你已有的衣物，或补充具体单品与穿搭要求后再试。'
    : '可以添加你已有的衣物，或开启「邂逅新衣」寻找衣橱之外的参考款。';
  card.append(el('span','journey-card-label','衣橱小笺'), el('strong','','让这次搭配，多一点可能'),
    el('p','',gapText + nextText));
  const current = () => {
    if (busy) return false;
    if (!card.isConnected || session?.user?.id !== owner || conversation !== cid || version !== turn) {
      notifyIssue('对话已有更新，请从最新的搭配继续。'); return false;
    }
    return true;
  };
  const add = el('button','subtle','添加衣物'); add.type = 'button';
  add.onclick = () => { if (current() && requireLogin()) window.WardrobeJourney.upload('garment'); };
  card.append(add);
  if (!reply.new_clothes) {
    const explore = el('button','subtle','开启「邂逅新衣」'); explore.type = 'button';
    explore.onclick = async () => {
      if (!current() || !requireLogin()) return;
      setNewClothes(true, {explain:true});
      await sendMessage(false, null, null, {owner, conversation_id:cid, version:turn});
    };
    card.append(explore);
  }
  return card;
}
function outfitFeedback(reply, index) {
  const box = el('section', 'outfit-feedback'); box.setAttribute('aria-label', '穿搭回音');
  const heading = el('div', 'outfit-feedback-heading');
  const ornament = el('span', 'outfit-feedback-star', '✧'); ornament.setAttribute('aria-hidden', 'true');
  const titles = el('div'); titles.append(el('small', 'outfit-feedback-eyebrow', '穿 搭 回 音'), el('h4', '', '这一套，有没有一点心动？'));
  heading.append(titles, ornament);
  const controls = el('div', 'outfit-feedback-choices');
  const response = el('p', 'outfit-feedback-response', '等我翻一翻这一页…');
  response.setAttribute('role', 'status'); response.setAttribute('aria-live', 'polite');
  const footer = el('div', 'outfit-feedback-footer');
  footer.append(el('small', '', '按你的喜欢，慢慢来。'));
  const capturedSession = session;
  const path = `/stylist-api/conversations/${encodeURIComponent(reply.conversation_id)}/feedback`;
  const query = new URLSearchParams({version:reply.version,look_index:index});
  const profile = window.CompanionSettings?.getProfile?.();
  const persona = profile?.assistant_persona || (document.documentElement.dataset.appearance === 'male' ? 'male_calm_v1' : 'female_warm_v1');
  let current = null, pending = true;
  const buttons = [];
  const active = () => session === capturedSession && box.isConnected;
  function paint(message) {
    box.dataset.vote = current || 'none'; box.setAttribute('aria-busy', String(pending));
    response.textContent = message || (current === 'like' ? '这份喜欢留在这一页了，心意也随时能改。' : current === 'dislike' ? '还没找到对的感觉也没关系，想改哪里，可以说给我听。' : '喜欢可以留下，想换个感觉也可以告诉我。');
    for (const [button, vote] of buttons) {
      button.disabled = pending;
      if (vote !== null) button.setAttribute('aria-pressed', String(current === vote));
      else button.style.visibility = current === null ? 'hidden' : 'visible';
    }
  }
  const heart = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/></svg>';
  const breeze = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h12a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M5 16h4a3 3 0 1 1-3 3"/></svg>';
  for (const [label, accessible, vote, icon] of [['有点心动','喜欢这套','like',heart],['再找找感觉','不喜欢这套','dislike',breeze],['撤回评价','撤回评价',null,'']]) {
    const button = el('button', vote === null ? 'outfit-feedback-undo' : 'outfit-feedback-choice');
    button.type = 'button'; button.dataset.agentVote=vote||'undo'; button.disabled = true; button.setAttribute('aria-label', accessible);
    if (icon) button.innerHTML = icon;
    button.append(el('span', '', label));
    button.onclick = async () => {
      if (pending || !active() || !requireLogin()) return;
      pending = true; paint('把这一点心意，轻轻留在这页…');
      try {
        const saved = await api(path, {method:'PUT',body:JSON.stringify({version:reply.version,look_index:index,vote,assistant_persona:persona})});
        if (active()) { current = saved.vote; pending = false; paint(saved.message); }
      } catch (err) {
        if (active()) { pending = false; paint('这次没能留住，原来的选择还在。稍后再试一次吧。'); notifyIssue(err.message); }
      }
    };
    buttons.push([button,vote]); (vote === null ? footer : controls).append(button);
  }
  box.append(heading, controls, response, footer);
  api(`${path}?${query}`).then(saved => {
    if (active()) { current = saved.vote; pending = false; paint(); }
  }).catch(err => {
    if (active()) { response.textContent = '这一页暂时没能翻开，重新打开对话后再试试吧。'; box.setAttribute('aria-busy','false'); notifyIssue(err.message); }
  });
  return box;
}

function showReply(reply, request = null, previewNode = null) {
  setNewClothes(reply.new_clothes);
  if (request && reply.new_clothes_auto_enabled && reply.new_clothes_notice && !newClothesNotices.has(request.request_id)) {
    notifyIssue(reply.new_clothes_notice); newClothesNotices.add(request.request_id);
  }
  conversation = reply.conversation_id; version = reply.version;
  if (reply.looks?.length) selectedLook = { conversationId: conversation, lookVersion: reply.version, index: 0 };
  else if (selectedLook?.conversationId !== conversation) selectedLook = null;
  const node = previewNode || bubble('assistant', reply.message);
  if(previewNode){node.classList.remove('reply-preview');node.lastElementChild.textContent=reply.message;}
  if (reply.delivery === 'concept') {
    const reasons = {
      no_candidates: '这次没有查到可用于搭配的单品。',
      no_match: '这次候选中暂时没选出符合要求的单品。',
      unavailable: '这次衣物信息读取不完整，不能据此判断衣橱是否为空。'
    };
    const notice = el('p', 'warning concept-notice', (reasons[reply.reference_reason] || '这份建议尚未匹配真实单品。') +
      '以下是穿搭思路，不代表你已拥有这些衣物，目前不能保存或试穿。');
    node.insertBefore(notice, node.children[1] || null);
  }
  for (const item of reply.product_results || []) {
    const card = el('article', 'look subject-entry-card product-search-card');
    card.append(el('h3', '', '衣橱里的单品'), el('p', 'subject-entry-title', item.title || [item.color, item.secondary_class_name || item.class_name].filter(Boolean).join(' · ')));
    const urls = [item.cutout_image, item.original_image].map(v => String(v || '').replace(/^http:/i, 'https:')).filter(v => /^https:\/\//i.test(v));
    if (urls.length) {
      const img = el('img', 'subject-entry-image'); img.src = urls[0]; img.alt = item.title || '单品图片'; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer';
      let index = 0; img.onerror = () => { if (++index < urls.length) img.src = urls[index]; else img.replaceWith(el('p', '', '图片暂不可用')); };
      card.append(img);
    }
    card.append(el('p', '', [item.color, item.secondary_class_name || item.class_name, item.material].filter(Boolean).join(' · ')));
    if (item.description) card.append(el('p', '', item.description));
    const owner = session?.access_token;
    const view = el('button', 'subtle', '查看这件'); view.type = 'button';
    view.onclick = async () => {
      if (busy || !requireLogin() || session?.access_token !== owner || conversation !== reply.conversation_id || version !== reply.version) return;
      if (item.source !== 'user') return;
      await window.openSubjectConversation({subject_product:{source:'user', product_id:item.product_id}});
    };
    card.append(view); node.append(card);
  }
  const productEntry = reply.product_entry;
  const outfitEntry = reply.outfit_entry;
  if (productEntry || outfitEntry) {
    const entryCard = el('article', 'look subject-entry-card');
    const subject = productEntry || outfitEntry;
    entryCard.append(el('h3', '', productEntry ? '当前单品' : (subject.title || '搭配详情')));
    if (productEntry?.title) entryCard.append(el('p', 'subject-entry-title', productEntry.title));
    if (subject.image_url || subject.presentation?.canvas_image) {
      const image = el('img', 'subject-entry-image');
      image.src = subject.image_url || subject.presentation.canvas_image;
      image.alt = subject.title || (productEntry ? '单品图片' : '搭配图片');
      image.loading = 'lazy';
      entryCard.append(image);
    }
    if (subject.description) entryCard.append(el('p', '', subject.description));
    if (outfitEntry?.items?.length) {
      entryCard.append(el('p', '', `这套搭配包含 ${outfitEntry.items.length} 件衣物，可以继续聊怎么调整。`));
    }
    if (productEntry) {
      const owner = session?.access_token;
      const actions = el('div', 'subject-entry-actions');
      const current = () => {
        if (busy || !requireLogin()) return false;
        if (session?.access_token !== owner || conversation !== reply.conversation_id || version !== reply.version) {
          notifyIssue('当前单品或账号已有变化，请重新打开这件单品。'); return false;
        }
        return true;
      };
      const pair = el('button', 'subtle', '用这件搭配下'); pair.type = 'button';
      pair.onclick = async () => {
        if (pair.disabled || !current()) return;
        pair.disabled = true;
        try { await sendMessage(false, null, null, null, null,
          {owner, conversation_id:reply.conversation_id, version:reply.version, title:subject.title}); }
        finally { pair.disabled = false; }
      };
      const tryon = el('button', 'subtle', '试穿这件'); tryon.type = 'button';
      tryon.disabled = !reply.looks?.[0]?.items?.length;
      tryon.onclick = async () => {
        if (tryon.disabled || !current()) return;
        tryon.disabled = true;
        try { await window.WardrobeJourney.tryon({conversation_id:reply.conversation_id, version:reply.version, look_index:0}); }
        catch (err) { notifyIssue(err.message); }
        finally { tryon.disabled = false; }
      };
      actions.append(pair, tryon); entryCard.append(actions);
    }
    node.append(entryCard);
  }
  markNewContent();
  const systemItems = reply.looks?.some(look => look.items?.some(item => item.source === 'system'));
  const partial = reply.looks?.some(look => look.items?.length && look.wardrobe_complete === false);
  const label = { advice: '穿法建议', outfit: systemItems ? '邂逅新衣 · 含未拥有的参考款' : partial ? '衣橱部分搭配' : '真实衣橱搭配', concept: '文字参考 · 非已有单品', clarification: '需要你确认' };
  if (!reply.conversation_only) node.prepend(el('div', 'badge', reply.product_search ? '衣橱单品' : reply.weather_only ? '天气查询' : label[reply.delivery] || '穿搭建议'));
  if (reply.city_selection_required && !selectedCity) node.append(cityInvitation(reply, request));
  if (reply.weather?.source === 'itinerary_forecast') {
    const route = el('section', 'itinerary-weather');
    route.setAttribute('aria-label', '行程各地天气');
    for (const stop of reply.weather.locations || []) {
      if (stop.forecast?.days?.length) route.append(forecastCard(stop.forecast));
      else route.append(el('div', 'warning', stop.message || `${stop.city_name}的天气暂时还查不到。`));
    }
    node.append(route);
  } else if (reply.weather?.days?.length) node.append(forecastCard(reply.weather));
  if (reply.retained_items?.length) {
    const retained = el('article', 'look retained-look');
    retained.append(el('h3', '', '保留的衣物 · 本次未完成替换'),
      el('p', '', '这些衣物仍按你的要求保留，还没有组成新的完整搭配。'), productGrid(reply.retained_items));
    node.append(retained);
  }
  const looks = productEntry ? [] : reply.looks || [], tabs = [], panels = [];
  const options = el('div', 'outfit-options');
  const tabList = el('div', 'outfit-tabs');
  tabList.setAttribute('role', 'tablist'); tabList.setAttribute('aria-label', '本轮搭配风格');
  const groupId = 'outfit-' + (++outfitGroupSequence);
  const activate = index => {
    // Switching styles should keep the tabs in view rather than jump to the
    // bottom of a newly expanded card. Sending again resumes following.
    followLatest = false;
    tabs.forEach((tab, i) => {
      tab.setAttribute('aria-selected', String(i === index)); tab.tabIndex = i === index ? 0 : -1;
      panels[i].hidden = i !== index;
    });
    // Start the newly selected outfit at its heading, within the chat feed.
    feed.scrollTop += options.getBoundingClientRect().top - feed.getBoundingClientRect().top;
    if (selectedLook?.conversationId === reply.conversation_id && selectedLook.lookVersion === reply.version) {
      selectedLook.index = index;
    }
  };
  if (looks.length > 1) options.append(tabList);
  for (const [lookIndex, look] of looks.entries()) {
    const card = el('article', 'look'); card.append(el('h3', '', look.title));
    if (looks.length > 1) {
      // Old conversations predate style_name; use a recognizable style from
      // their title, with a neutral fallback instead of inventing one.
      const legacyStyle = look.title?.match(/简约通勤|休闲运动|温柔日常|法式复古|商务通勤|通勤|休闲|运动|复古|简约|甜美|街头|优雅/);
      const tab = el('button', 'outfit-tab', look.style_name || legacyStyle?.[0] || `搭配 ${lookIndex + 1}`);
      tab.type = 'button'; tab.id = `${groupId}-tab-${lookIndex}`;
      tab.setAttribute('role', 'tab'); tab.setAttribute('aria-selected', String(lookIndex === 0));
      tab.setAttribute('aria-controls', `${groupId}-panel-${lookIndex}`); tab.tabIndex = lookIndex === 0 ? 0 : -1;
      card.id = `${groupId}-panel-${lookIndex}`; card.setAttribute('role', 'tabpanel');
      card.setAttribute('aria-labelledby', tab.id); card.tabIndex = 0; card.hidden = lookIndex !== 0;
      tab.onclick = () => activate(lookIndex);
      tab.onkeydown = event => {
        let index;
        if (event.key === 'ArrowRight') index = (lookIndex + 1) % looks.length;
        else if (event.key === 'ArrowLeft') index = (lookIndex + looks.length - 1) % looks.length;
        else if (event.key === 'Home') index = 0;
        else if (event.key === 'End') index = looks.length - 1;
        else return;
        event.preventDefault(); activate(index); tabs[index].focus();
      };
      tabs.push(tab); panels.push(card); tabList.append(tab);
    }
    if (look.items?.length) {
      for (const item of look.items) { item._conversation = reply.conversation_id; item._version = reply.version; }
      card.append(window.OutfitBoard.create(look, {conversationId:reply.conversation_id,version:reply.version,index:lookIndex}));
    } else { bulletSection(card, '穿什么', look.pieces); }
    bulletSection(card, '其余单品参考 · 未匹配衣橱', look.reference_pieces);
    if (look.wardrobe_complete === false && !look.reference_pieces?.length && look.items?.length) {
      bulletSection(card, '整套穿搭建议 · 图片仅含衣橱部分', look.pieces);
    }
    bulletSection(card, '为什么这样搭', look.why);
    bulletSection(card, '照着这样穿', look.how);
    bulletSection(card, '穿着提醒', look.notes);
    if (look.items?.length) {
      const preview = el('button', 'subtle', look.items.some(item => item.source === 'system') ? '用数字人试穿参考搭配 ↗' : look.wardrobe_complete === false ? '试穿衣橱中已有的单品 ↗' : '用数字人试穿这套 ↗');
      preview.dataset.agentTrack='outfit_tryon';
      preview.onclick = async () => {
        if (busy || !requireLogin()) return;
        if (conversation !== reply.conversation_id || version !== reply.version) { notifyIssue('这是历史方案，请先打开对应的最新对话。'); return; }
        preview.disabled = true;
        try { await window.WardrobeJourney.tryon({conversation_id:conversation,version,look_index:lookIndex}); }
        catch(err) { notifyIssue(err.message); } finally { preview.disabled=false; }
      };
      card.append(preview);
      const regenerate = el('button', 'subtle', '重新生成穿搭'); regenerate.type = 'button';
      regenerate.dataset.agentTrack='outfit_regenerate';
      regenerate.onclick = async () => {
        if (regenerate.disabled) return;
        regenerate.disabled = true;
        try { await regenerateOutfit({status:'completed',conversation_id:reply.conversation_id,version:reply.version,look_index:lookIndex}); }
        finally { regenerate.disabled = false; }
      };
      card.append(regenerate);
    }
    if (reply.delivery === 'outfit' && !reply.pending_confirmation) card.append(outfitFeedback(reply, lookIndex));
    options.append(card);
  }
  if (looks.length) node.append(options);
  window.WardrobeJourney?.offer(reply, node);
  for (const warning of reply.warnings || []) node.append(el('div', 'warning', warning));
  if (reply.follow_ups?.length) {
    const actions = el('div', 'followups');
    for (const text of reply.follow_ups) { const button = el('button', '', text); button.onclick = () => { $('message').value = text; $('message').focus(); }; actions.append(button); }
    node.append(actions);
  }
  if (reply.wardrobe_gap) node.append(wardrobeGapCard(reply, request));
  scrollBottom(false);
}
function completeReplyAtReadingPosition(reply,request,preview,pending) {
  const readingTop=feed.scrollTop;
  followLatest=false;
  pending.stop();
  showReply(reply,request,preview);
  feed.scrollTop=readingTop;
  markNewContent();
}
function stopChatGeneration() {
  const run=activeChatRun;
  if(!run||run.cancelled||run.completed)return;
  run.cancelled=true;run.resolveCancel?.(false);run.controller.abort();run.preview?.cancel();setBusy(true);
  if(session?.access_token!==run.token)return;
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),8000);
  run.stopPromise=fetch('/stylist-api/chat/stop',{method:'POST',headers:run.headers,body:JSON.stringify(run.request),signal:controller.signal})
    .then(async response=>{if(!response.ok)throw Error('stop_unconfirmed');return response.json();})
    .then(()=>{if(session?.access_token===run.token)notifyIssue('已停止接收本次回复，输入已保留。已完成的内容可在聊过的日常查看。');})
    .catch(()=>{if(session?.access_token===run.token)notifyIssue('已停止接收本次回复，后台停止暂未确认。可稍后查看聊过的日常。');})
    .finally(()=>clearTimeout(timeout));
}
function setBusy(value) {
  busy = value;
  window.ChatAttachments?.setBusy(value);
  for (const id of ['personal-clothes', 'new-clothes']) if ($(id)) $(id).disabled = value;
  const running=value&&activeChatRun&&!activeChatRun.completed;
  const canStop=running&&!activeChatRun.cancelled;
  $('send').disabled = value&&!canStop;
  $('send').dataset.state=running?(canStop?'stop':'stopping'):'send';
  $('send').setAttribute('aria-label',canStop?'停止生成':running?'正在停止':'发送');
  $('send').setAttribute('aria-busy',String(value));
  $('new-chat').disabled = value; $('mobile-new').disabled = value; $('send').textContent = canStop?'停止生成':running?'正在停止':'发送';
  $('mobile-history').disabled = value; $('history-refresh').disabled = value;
  $('logout').disabled = value; $('login-open').disabled = value;
  $('location-open').disabled = value; $('companion-open').disabled = value; $('preferences-open').disabled = value;
}
async function refreshHistory() {
  if (!session) return;
  const owner = session.user.id, sequence = ++historySequence;
  try {
    const rows = await api('/stylist-api/conversations');
    if (session?.user.id !== owner || sequence !== historySequence) return;
    $('history-status').textContent = rows.length ? '' : '还没有聊过的日常，开始聊聊吧。';
    for (const container of [$('history'), $('mobile-history-list')]) {
      container.replaceChildren();
      for (const row of rows) {
        const title = (row.title?.trim() || '未命名对话').replace(/^(?:打开单品[：:].*|聊聊这件单品\s*·.*|用这件.*搭配一下|用这件搭一套|用这件搭配下)$/, '帮我查看下这件').replace(/^打开搭配[：:].*$/, '帮我查看下搭配');
        const characters = Array.from(title.replace(/\s+/g, ' '));
        const shortTitle = characters.slice(0, 20).join('') + (characters.length > 20 ? '...' : '');
        const button = el('button', 'history-conversation-title', shortTitle); button.type = 'button';
        button.setAttribute('aria-label', title);
        button.title = title;
        if (row.id === conversation) button.setAttribute('aria-current', 'true');
        button.onclick = async () => {
          if (busy || session?.user.id !== owner) return;
          setBusy(true); $('history-status').textContent = '正在打开对话…';
          try {
            const record = await api('/stylist-api/conversations/' + row.id);
            if (session?.user.id !== owner) return;
            $('feed').replaceChildren();
            for (const turn of record.messages) { bubble('user', turn.reply.product_entry ? '帮我查看下这件' : turn.reply.outfit_entry ? '帮我查看下搭配' : turn.user); showReply(turn.reply); }
            window.ChatAttachments?.clear();
            conversation = record.conversation_id; version = record.version;
            window.WardrobeJourney?.restore(conversation).catch(err=>notifyIssue(err.message));
            for (const list of [$('history'), $('mobile-history-list')]) {
              list.querySelectorAll('[aria-current]').forEach(item => item.removeAttribute('aria-current'));
              for(const entry of list.querySelectorAll('.history-conversation-row'))if(entry.dataset.conversationId===row.id)entry.querySelector('.history-conversation-title')?.setAttribute('aria-current','true');
            }
            $('history-status').textContent = ''; $('history-dialog').close();
          } catch (err) { notifyIssue(err.message); $('history-status').textContent = ''; }
          finally { setBusy(false); }
        };
        const entry=el('div','history-conversation-row');entry.dataset.conversationId=row.id;
        const remove=el('button','history-conversation-delete');remove.type='button';
        const icon=document.createElementNS('http://www.w3.org/2000/svg','svg');
        icon.setAttribute('viewBox','0 0 24 24');icon.setAttribute('width','16');icon.setAttribute('height','16');icon.setAttribute('aria-hidden','true');
        const cross=document.createElementNS('http://www.w3.org/2000/svg','path');
        cross.setAttribute('d','M6 6l12 12M18 6L6 18');cross.setAttribute('fill','none');cross.setAttribute('stroke','currentColor');cross.setAttribute('stroke-width','1.6');cross.setAttribute('stroke-linecap','round');
        icon.append(cross);remove.append(icon);
        remove.setAttribute('aria-label','删除对话：'+title);remove.title='从当前账号删除这条对话';
        remove.onclick=async()=>{
          if(busy||session?.user.id!==owner||sequence!==historySequence||!entry.isConnected)return;
          try{
            await api('/stylist-api/conversations/'+encodeURIComponent(row.id),{method:'DELETE'});
          }catch(err){notifyIssue(err.message);return;}
          if(session?.user.id!==owner)return;
          if(conversation===row.id){
            savePending(null);conversation=null;version=0;selectedLook=null;
            pendingUploadAnchor=null;pendingAnchorOwner=null;updateUploadAnchor();
            window.ChatAttachments?.clear();$('feed').replaceChildren();
          }
          await refreshHistory();
        };
        entry.append(button,remove);container.append(entry);
      }
    }
  } catch (err) { if (session?.user.id === owner && sequence === historySequence) { notifyIssue(err.message); $('history-status').textContent = ''; } }
}
function clearHistory() {
  historySequence++; $('history').replaceChildren(); $('mobile-history-list').replaceChildren();
  $('history-status').textContent = '';
}
const PENDING_KEY = 'stylist-pending-run-v1';
let pendingRun = null;
try { pendingRun = JSON.parse(sessionStorage.getItem(PENDING_KEY) || 'null'); } catch { pendingRun = null; }
function savePending(value) {
  pendingRun = value;
  if (value && !value.request?.chat_image) sessionStorage.setItem(PENDING_KEY, JSON.stringify(value));
  else sessionStorage.removeItem(PENDING_KEY);
}
async function sendMessage(resuming = false, outfitAction = null, cityAction = null, explorationAction = null, subjectEntry = null, pairAction = null, uploadAction = null) {
  const saved = resuming && pendingRun?.owner === session?.user?.id ? pendingRun : null;
  const attachmentOwner = session?.access_token;
  const inputValue = $('message').value;
  const draftImage = !uploadAction && !pairAction && !subjectEntry && !outfitAction && !cityAction && !explorationAction ? window.ChatAttachments?.get() : null;
  const text = uploadAction ? `用这件搭配下。${inputValue.trim() ? '\n'+inputValue.trim() : ''}` : pairAction ? `用当前这件「${pairAction.title || '衣物'}」，从我的衣橱搭一套。${inputValue.trim() ? '\n'+inputValue.trim() : ''}` : subjectEntry ? '' : (explorationAction ? '沿用刚才的搭配要求，开启邂逅新衣，把系统参考款也纳入选择，继续完成刚才的搭配。' : null) || saved?.request.message || cityAction?.request?.message || (cityAction ? '按刚才的穿搭要求，结合选好的城市天气继续搭配。' : outfitAction ? '重新生成穿搭' : (inputValue.trim() || (draftImage ? '请看看这张图片里的穿搭。' : '')));
  const displayText = subjectEntry?.subject_product ? '帮我查看下这件' : subjectEntry?.subject_outfit ? '帮我查看下搭配' : text;
  if ((!text && !subjectEntry) || busy || !requireLogin()) return;
  if (window.CompanionSettings) { await window.CompanionSettings.ready; if (busy || !session) return; }
  if (subjectEntry && attachmentOwner !== session?.access_token) return;
  if (uploadAction) {
    if (session?.access_token !== uploadAction.owner || conversation !== uploadAction.conversation_id || version !== uploadAction.version) return;
    savePending(null); conversation = null; version = 0; selectedLook = null;
    pendingUploadAnchor = null; pendingAnchorOwner = null; updateUploadAnchor();
    window.ChatAttachments?.clear(); setNewClothes(false);
    $('feed').replaceChildren();
  }
  if (pairAction && (session?.access_token !== pairAction.owner || conversation !== pairAction.conversation_id || version !== pairAction.version)) {
    notifyIssue('当前单品已有变化，请重新打开后搭配。'); return;
  }
  if (draftImage && (attachmentOwner !== session?.access_token || draftImage !== window.ChatAttachments?.get())) return;
  if (outfitAction && (session.user.id !== outfitAction.owner || conversation !== outfitAction.conversation_id)) {
    notifyIssue('账号或搭配已有更新，请从当前最新结果重新生成。'); return;
  }
  if (cityAction && (session.user.id !== cityAction.owner || conversation !== cityAction.conversation_id || version !== cityAction.version)) {
    notifyIssue('对话已有更新，请从最新的穿搭需求继续。'); return;
  }
  if (explorationAction && (session.user.id !== explorationAction.owner || conversation !== explorationAction.conversation_id || version !== explorationAction.version)) {
    notifyIssue('对话已有更新，请从最新的搭配继续。'); return;
  }
  const request = saved?.request || { ...(cityAction?.request || {}), message: text,
    conversation_id: subjectEntry ? null : conversation, expected_version: subjectEntry ? 0 : version,
    request_id: crypto.randomUUID(), confirm_plan: false, ...(subjectEntry || {}) };
  if (!saved && !subjectEntry && !cityAction && window.CompanionSettings?.getProfile()) request.companion_profile = window.CompanionSettings.getProfile();
  if (!saved && !subjectEntry && !request.assistant_persona) request.assistant_persona = request.companion_profile?.assistant_persona || (document.documentElement.dataset.stylistGender === 'male' ? 'male_calm_v1' : 'female_warm_v1');
  if (!saved && !subjectEntry) request.new_clothes = $('new-clothes')?.checked || false;
  if (!saved && !subjectEntry && selectedCity) request.location = selectedCity;
  if (!saved && !subjectEntry && !cityAction && selectedLook?.conversationId === conversation) request.selected_look_index = selectedLook.index;
  if (!saved && outfitAction) { request.regenerate_outfit = true; request.selected_look_index = outfitAction.look_index; request.regenerate_from_version = outfitAction.version; }
  if (pairAction) { request.pair_subject_product = true; request.selected_look_index = 0; }
  const uploadAnchorForRequest = !pairAction && !saved && !subjectEntry && !cityAction && !explorationAction
    && !request.regenerate_outfit ? pendingUploadAnchor : null;
  if (uploadAction || uploadAnchorForRequest) request.upload_action_id = uploadAction?.action_id || uploadAnchorForRequest;
  if (!saved && draftImage) request.chat_image = draftImage;
  const chatOwner = session.user.id;
  savePending({owner: chatOwner, request});
  const userBubble = bubble('user', displayText);
  if(request.chat_image){const image=document.createElement('img');image.src=request.chat_image;image.alt='本轮图片附件';image.style.cssText='display:block;max-width:180px;max-height:180px;object-fit:contain;border-radius:12px;margin-top:8px';userBubble.append(image);}
  const pending = pendingBubble(request.assistant_persona);
  let textPreview=null,replyCommitted=false;
  const run={request,token:session.access_token,headers:headers(),controller:new AbortController(),cancelled:false,preview:null,stopPromise:null};activeChatRun=run;run.cancelWait=new Promise(resolve=>run.resolveCancel=resolve);
  const trackingStart=performance.now(),trackingAttempt=window.AgentTracking?.begin({text_length:Array.from(displayText).length,has_image:!!request.chat_image,new_clothes:!!request.new_clothes,resuming:!!saved});
  let trackingOutcome=false,trackingFirstText=false,trackingRetries=0;const trackingStages=new Set();
  const track=(event,params={})=>window.AgentTracking?.track(event,{attempt:trackingAttempt,...params});
  const trackFirstText=()=>{if(!trackingFirstText){trackingFirstText=true;track('AgentFirstText',{elapsed_ms:performance.now()-trackingStart});}};
  setBusy(true); $('notice').textContent = '';
  try {
    let received = false;
    while (!received) {
      try {
        const fundsOk=!!subjectEntry||!window.AppPayment||await Promise.race([window.AppPayment.checkFunds(null,'agent',()=>!run.cancelled&&session?.access_token===run.token),run.cancelWait]);
        if(run.cancelled)return;
        if(!fundsOk){trackingOutcome=true;track('AgentSendBlocked');savePending(null);return;}
        if(run.cancelled||session?.user.id!==chatOwner)return;
        track('AgentRequest',{retry_count:trackingRetries});
        const response = await fetch('/stylist-api/chat/stream', { method: 'POST', headers: headers(), body: JSON.stringify(request),signal:run.controller.signal });
        if (run.cancelled||session?.user.id !== chatOwner) return;
        if (!response.ok) { const data = await response.json(); throw error(data.code, data.message); }
        const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = '';
        try {
          while (!received) {
            const { value, done } = await reader.read();
            if (run.cancelled||session?.user.id !== chatOwner) return;
            buffer += decoder.decode(value, { stream: !done });
            let cut;
            while ((cut = buffer.indexOf('\n\n')) >= 0) {
              const block = buffer.slice(0, cut); buffer = buffer.slice(cut + 2);
              const kind = block.split('\n').find(x => x.startsWith('event: '))?.slice(7);
              const raw = block.split('\n').filter(x => x.startsWith('data: ')).map(x => x.slice(6)).join('\n');
              if (kind === 'error') { const data = JSON.parse(raw); throw error(data.code, data.message); }
              if (kind === 'progress') {
                const progress = JSON.parse(raw);
                if(!trackingStages.has(progress.stage)){trackingStages.add(progress.stage);if(progress.stage!=='reply_text')track('AgentStage',{stage:progress.stage});}
                if(progress.stage==='reply_text'){if(!textPreview&&progress.message){trackFirstText();textPreview=revealReplyText(progress.message,pending.node);run.preview=textPreview;}}
                else if (progress.stage === 'new_clothes') {
                  setNewClothes(true);
                  if (!newClothesNotices.has(request.request_id)) { notifyIssue(progress.message); newClothesNotices.add(request.request_id); }
                } else pending.update(progress);
              }
              if (kind === 'result') {
                const reply = JSON.parse(raw);
                if(!textPreview&&reply.message){trackFirstText();textPreview=revealReplyText(reply.message,pending.node);run.preview=textPreview;}
                if(textPreview)await textPreview.done;
                if(run.cancelled||session?.user.id!==chatOwner)return;
                completeReplyAtReadingPosition(reply,request,textPreview?.node,pending);replyCommitted=true;received=true;run.completed=true;setBusy(true);trackingOutcome=true;track('AgentResult',{elapsed_ms:performance.now()-trackingStart,delivery:reply.delivery,look_count:reply.looks?.length||0,retry_count:trackingRetries});
                if (reply.pending_confirmation) showPlanApproval(request);
                else { savePending(null); if(!subjectEntry)dailyCheckin.completeChat(chatOwner); }
              }
            }
            if (done) break;
          }
        } finally { await reader.cancel().catch(() => {}); }
        if (!received) throw new TypeError('stream_disconnected');
      } catch (err) {
        if(run.cancelled)break;
        if (!(err instanceof TypeError) && !['request_in_progress', 'server_draining'].includes(err.code)) throw err;
        if (!session || session.user.id !== pendingRun?.owner) throw error('authentication_expired', '请重新登录后继续原任务。');
        trackingRetries++;track('AgentReconnect',{retry_count:trackingRetries});
        pending.update({stage: 'connecting', message: '连接正在恢复，已完成的步骤会保留…'});
        await new Promise(resolve => setTimeout(resolve, 2500));
      }
    }
    if(run.cancelled)return;
    if (!pairAction && !subjectEntry && !cityAction && !explorationAction && !request.regenerate_outfit && $('message').value === inputValue) $('message').value = '';
    if(request.chat_image) window.ChatAttachments?.ack(request.chat_image);
    if (uploadAnchorForRequest && pendingUploadAnchor === uploadAnchorForRequest) {
      pendingUploadAnchor = null; pendingAnchorOwner = null; updateUploadAnchor();
    }
    await refreshHistory();
  } catch (err) {
    if(!run.cancelled&&!replyCommitted){trackingOutcome=true;track('AgentError',{elapsed_ms:performance.now()-trackingStart,retry_count:trackingRetries,error_kind:err.code==='authentication_expired'?'auth':err instanceof TypeError?'network':err.code==='model_output_invalid'?'model':'other'});}
    if (session?.user.id !== chatOwner) return;
    if (err.code !== 'authentication_expired') savePending(null);
    pending.stop();
    if (!err.paymentHandled) err.paymentHandled=globalThis.AppPayment?.handleError(err)===true;
    if (!err.paymentHandled && err.code !== 'authentication_expired') notifyIssue((err.message || '请求未完成，请稍后重试。') + '\n' + (err.code === 'model_output_invalid' ? '输入还在，点「发送」就能重试。' : agentText('输入还在，可以调整后再发给衣衣。')));
    if (err.code === 'authentication_expired') expireSession(err.message);
  } finally { if(!trackingOutcome)track('AgentAbandon',{elapsed_ms:performance.now()-trackingStart,retry_count:trackingRetries,reason:run.cancelled?'user_stop':'context_changed'});window.AgentTracking?.end(trackingAttempt);pending.stop();if(!replyCommitted){if(run.cancelled&&textPreview){textPreview.cancel();textPreview.node.classList.remove('reply-preview');textPreview.node.append(el('small','reply-stopped','已停止 · 此段未完成'));}else textPreview?.remove();}if(run.cancelled&&session?.access_token===run.token)savePending(null);if(run.stopPromise)await run.stopPromise;if(activeChatRun===run)activeChatRun=null; if (!session || session.user.id === chatOwner) setBusy(false); }
}
function showPlanApproval(request) {
  // Compatibility for requests already waiting before the composer option was removed.
  const actions = el('div', 'followups');
  for (const [approved, text] of [[true, '确认需求，继续搭配'], [false, '取消这次生成']]) {
    const button = el('button', '', text);
    button.onclick = async () => {
      if (busy || !requireLogin()) return;
      setBusy(true);
      const chatOwner = session.user.id;
      try {
        const reply = await api('/stylist-api/chat/approval', {method:'POST', body:JSON.stringify({request, approved})});
        savePending(null); actions.remove(); showReply(reply);
        if (approved && !reply.pending_confirmation) dailyCheckin.completeChat(chatOwner);
        await refreshHistory();
      } catch (err) { notifyIssue(err.message); }
      finally { setBusy(false); }
    };
    actions.append(button);
  }
  feed.append(actions); scrollBottom(false);
}
$('chat-form').onsubmit = event => { event.preventDefault();if(busy&&activeChatRun)stopChatGeneration();else sendMessage(); };
$('message').onkeydown = event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); sendMessage(); } };
for (const button of document.querySelectorAll('[data-prompt]')) button.onclick = () => { $('message').value = button.dataset.prompt; $('message').focus(); };
function resetChat() {
  if (busy) return;
  // A new chat uses the same welcome page and initialization as a fresh visit.
  // Do not resume a previous request that was waiting for confirmation.
  savePending(null);
  window.location.reload();
}
$('new-chat').addEventListener('click',()=>window.ChatAttachments?.clear());
$('mobile-new').addEventListener('click',()=>window.ChatAttachments?.clear());
$('new-chat').onclick = resetChat; $('mobile-new').onclick = resetChat;
$('mobile-history').onclick = async () => {
  if (busy || !requireLogin()) return;
  $('history-dialog').showModal(); $('history-status').textContent = '正在加载聊过的日常…';
  await refreshHistory();
};
$('history-close').onclick = () => $('history-dialog').close();
$('history-refresh').onclick = async () => {
  $('history-refresh').disabled = true; $('history-status').textContent = '正在刷新…';
  try { await refreshHistory(); } finally { $('history-refresh').disabled = busy; }
};
$('login-open').onclick = () => $('login-dialog').showModal(); $('login-cancel').onclick = () => $('login-dialog').close();
$('logout').onclick = () => { savePending(null); sessionStorage.removeItem(KEY); sessionStorage.removeItem(CITY_KEY); selectedCity = null; forecastSequence++; forecastBusy = false; session = null; window.CompanionSettings?.setOwner(null, api); lastSessionOwner = null; conversation = null; version = 0; clearHistory(); $('history-dialog').close(); $('feed').replaceChildren(); updateCityLabel(); $('location-label').textContent = '让穿搭也照顾天气'; loginStatus(); };
$('login-form').onsubmit = async event => {
  event.preventDefault(); $('login-submit').disabled = true; $('login-error').textContent = '';
  try {
    let device = sessionStorage.getItem('stylist-device-id');
    if (!device) { device = 'stylist-' + crypto.randomUUID(); sessionStorage.setItem('stylist-device-id', device); }
    const response = await fetch('/stylist-api/auth/mobile-login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mobile: $('mobile').value, code: $('code').value, device_id: device }) });
    const data = await response.json(); if (!response.ok) throw new Error(data.message || '登录未成功');
    if (lastSessionOwner && lastSessionOwner !== data.user.id) { conversation = null; version = 0; $('feed').replaceChildren(); clearHistory(); }
    session = data; lastSessionOwner = data.user.id; sessionStorage.setItem(KEY, JSON.stringify(data)); $('code').value = ''; $('notice').textContent = ''; $('login-dialog').close(); loginStatus(); await window.CompanionSettings?.setOwner(data.user.id, api); await refreshHistory(); if (selectedCity) loadForecast();
  } catch (err) { notifyIssue(err.message); } finally { $('login-submit').disabled = false; }
};
$('check-apis').onclick = async () => {
  if (!requireLogin()) return;
  $('service-dialog').showModal(); $('service-results').textContent = '正在逐项查询，请稍候…';
  try { const report = await api('/stylist-api/integrations/check', { method: 'POST' }); $('service-results').textContent = report.results.map(x => `${x.interface}\n  ${x.status} · ${x.code}${x.latency_ms != null ? ' · ' + x.latency_ms + 'ms' : ''}${x.facts ? '\n  ' + JSON.stringify(x.facts) : ''}`).join('\n\n'); }
  catch (err) { $('service-results').textContent = ''; notifyIssue(err.message); }
};
$('service-close').onclick = () => $('service-dialog').close();
$('location-open').onclick = () => openCityPicker();
async function openCityPicker(continuation = null, trigger = $('location-open')) {
  if (!requireLogin()) return;
  const owner = session.user.id;
  await citiesReady;
  if (!session || session.user.id !== owner) return;
  if (continuation && (continuation.owner !== owner || continuation.conversation_id !== conversation || continuation.version !== version)) {
    notifyIssue('对话已有更新，请从最新的穿搭需求继续。'); return;
  }
  if (!cityCatalog) { notifyIssue('城市列表加载失败，请刷新后重试。'); return; }
  locationContinuation = continuation; locationOpener = trigger;
  $('location-save').textContent = continuation ? '确认城市，继续搭配' : '确认城市，看看天气';
  $('location-status').textContent = ''; updateLocationViewport(); $('location-dialog').showModal();
  cityPicker.setValue(selectedCity); updateLocationSave();
  // Keep the software keyboard closed until the user chooses to search.
  $('location-cancel').focus({ preventScroll: true });
}
function updateLocationViewport() {
  const viewport = window.visualViewport;
  const height = viewport?.height || window.innerHeight;
  $('location-dialog').style.setProperty('--city-viewport', `${height}px`);
  $('location-dialog').style.setProperty('--city-top', `${(viewport?.offsetTop || 0) + Math.max(12, height - 780)}px`);
  $('location-dialog').classList.toggle('location-compact', height < 550);
}
window.visualViewport?.addEventListener('resize', updateLocationViewport);
window.visualViewport?.addEventListener('scroll', updateLocationViewport);
window.addEventListener('resize', updateLocationViewport);
$('location-cancel').onclick = () => $('location-dialog').close();
$('location-dialog').addEventListener('close', () => {
  locationContinuation = null;
  locationSequence++; $('locate-me').disabled = locationSaving; updateLocationSave();
  if (locationOpener?.isConnected) locationOpener.focus({preventScroll:true});
  locationOpener = null;
});
$('locate-me').onclick = async () => {
  if (!requireLogin()) return;
  if (!window.isSecureContext || !navigator.geolocation) { notifyIssue('当前浏览器环境不支持定位，可以搜索或点选城市。'); return; }
  const sequence = ++locationSequence, owner = session.user.id;
  const current = () => sequence === locationSequence && session?.user.id === owner && $('location-dialog').open;
  $('locate-me').disabled = true; $('location-status').textContent = '请允许浏览器访问位置，也可以直接搜索或点选城市。';
  try {
    const position = await new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }));
    if (!current()) return;
    const city = await api('/stylist-api/location/resolve', { method: 'POST', body: JSON.stringify({ latitude: position.coords.latitude, longitude: position.coords.longitude, coordinate_system: 'wgs84' }) });
    await citiesReady;
    if (!current()) return;
    if (!cityPicker.setValue(city)) { notifyIssue('已识别到 ' + city.city_name + '，请搜索或点选对应城市。'); return; }
    $('location-status').textContent = '找到 ' + city.city_name + (city.district_name ? ' · ' + city.district_name : '') + ' 啦，请确认后使用。' + (position.coords.accuracy > 5000 ? '浏览器定位精度较低，如果不是你所在的城市，请手动修改。' : '');
  } catch (err) { if (current()) notifyIssue(err.code === 1 ? '定位权限未开启，搜索或点选城市也可以。' : err.code === 3 ? '定位超时啦，可以再试一次或搜索城市。' : err.message || '暂时没有定位成功，可以搜索或点选城市。'); }
  finally { if (current()) { $('locate-me').disabled = false; updateLocationSave(); } }
};
$('location-form').onsubmit = async event => {
  event.preventDefault();
  if (locationSaving) return;
  if (forecastBusy) { notifyIssue('天气正在更新，请稍后再确认。'); return; }
  const city = cityPicker.getValue();
  if (!city) { notifyIssue('请先从列表中选择一座城市。'); cityPicker.input.focus(); return; }
  const continuation = locationContinuation;
  if (continuation && (busy || session?.user?.id !== continuation.owner || conversation !== continuation.conversation_id || version !== continuation.version)) {
    notifyIssue('对话已有更新，请从最新的穿搭需求继续。'); return;
  }
  locationSequence++; locationSaving = true; $('city-picker').inert = true;
  $('locate-me').disabled = true; updateLocationSave(); $('location-save').textContent = '正在查询天气…';
  try {
    if (continuation) {
      selectedCity = city; sessionStorage.setItem(CITY_KEY, JSON.stringify(city)); updateCityLabel(true);
      $('location-dialog').close();
      await sendMessage(false, null, continuation);
    } else if (await loadForecast(city)) { $('location-dialog').close(); $('notice').textContent = ''; $('weather-panel')?.scrollIntoView({ block: 'start', behavior: 'smooth' }); }
  }
  finally {
    locationSaving = false; $('city-picker').inert = false; $('locate-me').disabled = false;
    $('location-save').textContent = '确认城市，看看天气'; updateLocationSave();
  }
};
const settingsMenu = $('settings-menu');
function closeSettingsMenu(restoreFocus = false) {
  settingsMenu.open = false;
  if (restoreFocus) $('settings-open').focus();
}
$('companion-open').onclick = () => {
  if (busy) return;
  closeSettingsMenu(true);
  if (requireLogin()) window.CompanionSettings?.open();
};
$('preferences-open').onclick = async () => {
  if (busy) return;
  closeSettingsMenu(true);
  if (requireLogin()) await window.PersonalPreferences.open();
};
$('memory-open').onclick = async () => {
  closeSettingsMenu(true);
  if (requireLogin()) await window.LongTermMemory.open();
};
document.addEventListener('click', event => {
  if (settingsMenu.open && !settingsMenu.contains(event.target)) closeSettingsMenu();
});
settingsMenu.addEventListener('keydown', event => {
  if (event.key === 'Escape') { event.preventDefault(); closeSettingsMenu(true); }
});
async function regenerateOutfit(action) {
  if (busy || !requireLogin()) return;
  if (pendingRun) { notifyIssue('请先处理当前等待确认的穿搭，再重新生成。'); return; }
  const index = action.look_index ?? 0;
  if (!['completed','failed'].includes(action.status) || conversation !== action.conversation_id || !Number.isInteger(action.version) || action.version < 1 || action.version > version || !Number.isInteger(index) || index < 0 || index > 6) {
    notifyIssue('请打开这套搭配所在的对话，再重新生成。'); return;
  }
  return sendMessage(false, {owner:session.user.id,conversation_id:conversation,version:action.version,look_index:index});
}
window.WardrobeJourney?.configure({api,notify:notifyIssue,getConversation:()=>conversation,getContext:()=>({conversation_id:conversation,version}),onNeedOutfit:()=>{
  if(!$('message').value.trim())$('message').value='先从我的衣橱搭一套适合试穿的日常穿搭。';$('message').focus();
},onRegenerate:regenerateOutfit,onStyle:action=>{
  if (busy || !requireLogin()) return;
  return sendMessage(false, null, null, null, null, null,
    {action_id:action, owner:session.access_token, conversation_id:conversation, version});
}});
for (const id of ['upload-open','welcome-upload']) if ($(id)) $(id).onclick=()=>{if(requireLogin()) window.WardrobeJourney.upload('garment');};
if ($('twin-open')) $('twin-open').onclick=()=>{if(requireLogin()) window.WardrobeJourney.twins().catch(err=>notifyIssue(err.message));};
if ($('journey-records-open')) $('journey-records-open').onclick=()=>{if(requireLogin()) window.WardrobeJourney.history().catch(err=>notifyIssue(err.message));};

if (session) window.CompanionSettings?.setOwner(session.user.id, api);
loginStatus(); updateCityLabel(); if (session) { refreshHistory(); if (selectedCity) loadForecast(); }

if (pendingRun && session && pendingRun.owner === session.user.id) sendMessage(true);

window.openSubjectConversation = async function(entry) {
  if (busy) { notifyIssue('请等当前回复结束，再打开这件单品或搭配。'); return; }
  const product = entry?.subject_product, outfit = entry?.subject_outfit;
  const discussion = entry?.discussion;
  if ([product,outfit,discussion].filter(Boolean).length !== 1
      || (discussion && (typeof discussion.title !== 'string' || typeof discussion.description !== 'string' || !(discussion.title+discussion.description).trim()))
      || (product && (product.source !== 'user' || !/^[1-9][0-9]{0,19}$/.test(product.product_id)))
      || (outfit && (outfit.source !== 'user' || !Number.isSafeInteger(outfit.outfit_id) || outfit.outfit_id <= 0))) {
    notifyIssue('这条单品或搭配信息暂不可用，请返回重新打开。'); return;
  }
  const owner = session?.access_token;
  if (!requireLogin()) return;
  await window.CompanionSettings?.ready;
  if (busy || session?.access_token !== owner) return;
  const context = discussion ? `我想聊聊这套「${discussion.title.slice(0,200)}」。${discussion.description ? '\n页面介绍：'+discussion.description.slice(0,2000) : ''}` : '';
  const draft = $('message').value;
  if (discussion && context.length + draft.length + 2 > 6000) { notifyIssue('草稿较长，请先整理后再带入这套介绍。'); return; }
  savePending(null); conversation = null; version = 0; selectedLook = null;
  pendingUploadAnchor = null; pendingAnchorOwner = null; updateUploadAnchor();
  window.ChatAttachments?.clear();
  $('feed').replaceChildren();
  if (discussion) {
    $('message').value = context + (draft ? '\n\n'+draft : '');
    $('message').dispatchEvent(new Event('input', {bubbles:true}));
    $('message').focus();
    return;
  }
  return sendMessage(false, null, null, null, product
    ? {subject_product: {source:'user',product_id:product.product_id}}
    : {subject_outfit: {source:'user',outfit_id:outfit.outfit_id}});
};
function setupSubjectEntryDebug() {
  const panel = $('subject-entry-debug');
  if (!panel || new URLSearchParams(location.search).get('debug') !== 'subject-entry') return;
  panel.hidden = false;
  const query = new URLSearchParams(location.search);
  $('debug-product-id').value = query.get('product_id') || '12';
  $('debug-outfit-id').value = query.get('outfit_id') || '72';
  $('debug-product-open').onclick = () => {
    const productId = $('debug-product-id').value.trim();
    if (!/^[1-9][0-9]{0,19}$/.test(productId)) return notifyIssue('请输入有效的单品 ID。');
    sendMessage(false, null, null, null, {subject_product: {source: 'user', product_id: productId}});
  };
  $('debug-outfit-open').onclick = () => {
    const outfitId = Number($('debug-outfit-id').value.trim());
    if (!Number.isSafeInteger(outfitId) || outfitId < 1) return notifyIssue('请输入有效的搭配 ID。');
    sendMessage(false, null, null, null, {subject_outfit: {source: 'user', outfit_id: outfitId}});
  };
}
setupSubjectEntryDebug();
// Shared Stylist attachment flow. Wardrobe ingestion remains in its dedicated entry.
if (!document.getElementById('yijian-agent-root')) {
  $('upload-open').textContent='＋';
  $('upload-open').onclick=()=>notifyIssue('附件入口正在准备，请稍等一下。');
  import('/static/closet-app/chat-attachments.js').then(({mountChatAttachments})=>{
    const trigger=$('upload-open');trigger.textContent='＋';
    mountChatAttachments(document,trigger);
  }).catch(()=>notifyIssue('附件入口暂时没能加载，请稍后重新打开页面。'));
}
