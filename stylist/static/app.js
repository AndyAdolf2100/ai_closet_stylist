'use strict';
const $ = id => document.getElementById(id);
const agentName = () => window.CompanionSettings?.agentName() || '衣衣';
const agentText = text => text.replaceAll('衣衣', agentName());
const KEY = 'ai-closet-stylist-session-v1';
let session = null, conversation = null, version = 0, busy = false;
let selectedLook = null;
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
    cancel.setAttribute('aria-label','取消以刚上传的衣物为搭配起点');cancel.title='取消这件衣物';
    cancel.onclick = () => { pendingUploadAnchor = null; updateUploadAnchor(); };
    const mark=el('span','journey-anchor-mark','✧');mark.setAttribute('aria-hidden','true');
    row.append(mark,el('span', 'journey-anchor-copy', '从刚上传的这件开始搭'), cancel);
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
    throw error(data?.code || 'invalid_response', data?.message || (response.status === 413
      ? '图片过大，请选择10MB以内的图片。' : '服务暂时未完成请求，请稍后重试。'));
  }
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
const feed = $('feed');
let followLatest = false, bottomFrame = null;
function scrollBottom(force = true) {
  if (force) followLatest = true;
  if (!followLatest || bottomFrame !== null) return;
  // Wait until the whole message (including loading/cards) has been inserted.
  bottomFrame = requestAnimationFrame(() => {
    bottomFrame = null;
    if (followLatest) feed.scrollTop = feed.scrollHeight;
  });
}
feed.addEventListener('scroll', () => {
  followLatest = feed.scrollHeight - feed.clientHeight - feed.scrollTop <= 48;
}, { passive: true });
// Observe message heights as well as the viewport: images, wrapped progress
// text and the mobile keyboard can all change the bottom after insertion.
const feedResize = new ResizeObserver(() => scrollBottom(false));
feedResize.observe(feed);
const observedMessages = new Set();
new MutationObserver(() => {
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
    for (const period of data.days[0].periods || []) {
      const part = el('div'); part.append(el('strong', '', period.label), el('p', '', period.temp == null ? '暂无逐小时温度' : `${period.temp}°C · ${period.condition}`));
      part.append(el('small', '', period.note)); periods.append(part);
    }
    card.append(periods);
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
  const sequence = ++forecastSequence;
  forecastBusy = true;
  $('location-label').textContent = agentText('衣衣正在看看天气…');
  try {
    const data = await api('/stylist-api/weather/forecast', { method: 'POST', body: JSON.stringify({ location, scope: forecastScope }) });
    if (sequence !== forecastSequence) return false;
    selectedCity = { city_name: data.city_name, province_name: data.province_name }; sessionStorage.setItem(CITY_KEY, JSON.stringify(selectedCity)); updateCityLabel(explicitlySelected,data);
    let panel = $('weather-panel'); if (!panel) { panel = el('section'); panel.id = 'weather-panel'; $('feed').prepend(panel); }
    panel.hidden = false; panel.replaceChildren();
    const tabs = el('div', 'weather-tabs');
    for (const [scope, label] of [['day', '今天 · 早晚'], ['week', '本周 · 逐日']]) { const button = el('button', forecastScope === scope ? 'active' : '', label); button.onclick = () => { if (forecastBusy) return; forecastScope = scope; loadForecast(); }; tabs.append(button); }
    panel.append(tabs, forecastCard(data, true)); $('location-label').textContent = '出门前，再照顾一下天气';
    return true;
  } catch (err) {
    if (sequence !== forecastSequence) return false;
    $('location-label').textContent = '天气暂未取到，可重新选择城市重试'; $('location-status').textContent = '';
    notifyIssue(err.message);
    if ($('weather-panel')) { $('weather-panel').replaceChildren(el('p', 'weather-unavailable', '这次没有取到最新天气，先不显示旧预报。可以稍后重新选择城市重试。')); }
    return false;
  } finally { if (sequence === forecastSequence) { forecastBusy = false; } }
}
function pendingBubble(persona) {
  const node = bubble('assistant', ''); node.classList.add('pending');
  const male = window.CompanionCharacters.gender(persona) === 'male';
  const body = window.CompanionLoading.create({persona,
    message:male ? '收到，正在连接服务。' : '收到啦，正在连接服务。',
    detail:male ? '我会按你这次的要求处理。' : '我会照顾你这次提到的要求。'});
  body.classList.add('companion-wait');node.append(body);
  const timer = setTimeout(() => window.CompanionLoading.update(body,{detail:male ? '还在等待服务返回，结果到了就给你。' : '这次等得久一些，还在等待服务返回。'}),15000);
  return {node,update(data){body.dataset.stage=data.stage||'styling';window.CompanionLoading.update(body,{message:data.message});},stop(){clearTimeout(timer);node.remove();}};
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
      const original = (item.original_image || '').replace(/^http:/i, 'https:');
      imageButton.dataset.previewSrc = /^https:\/\//i.test(original) ? original : url;
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
  card.append(el('span','journey-card-label','衣橱小笺'), el('strong','','让这次搭配，多一点可能'),
    el('p','','这次找到的衣物还没能配齐。可以添入你已有的衣服，也可以一起邂逅衣橱之外的新选择。'));
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
    button.type = 'button'; button.disabled = true; button.setAttribute('aria-label', accessible);
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

function showReply(reply, request = null) {
  setNewClothes(reply.new_clothes);
  if (request && reply.new_clothes_auto_enabled && reply.new_clothes_notice && !newClothesNotices.has(request.request_id)) {
    notifyIssue(reply.new_clothes_notice); newClothesNotices.add(request.request_id);
  }
  conversation = reply.conversation_id; version = reply.version;
  if (reply.looks?.length) selectedLook = { conversationId: conversation, lookVersion: reply.version, index: 0 };
  else if (selectedLook?.conversationId !== conversation) selectedLook = null;
  const node = bubble('assistant', reply.message);
  const systemItems = reply.looks?.some(look => look.items?.some(item => item.source === 'system'));
  const partial = reply.looks?.some(look => look.items?.length && look.wardrobe_complete === false);
  const label = { advice: '穿法建议', outfit: systemItems ? '邂逅新衣 · 含未拥有的参考款' : partial ? '衣橱部分搭配' : '真实衣橱搭配', concept: '文字参考 · 未完成商品匹配', clarification: '需要你确认' };
  if (!reply.conversation_only) node.prepend(el('div', 'badge', reply.weather_only ? '天气查询' : label[reply.delivery] || '穿搭建议'));
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
  const looks = reply.looks || [], tabs = [], panels = [];
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
      preview.onclick = async () => {
        if (busy || !requireLogin()) return;
        if (conversation !== reply.conversation_id || version !== reply.version) { notifyIssue('这是历史方案，请先打开对应的最新对话。'); return; }
        preview.disabled = true;
        try { await window.WardrobeJourney.tryon({conversation_id:conversation,version,look_index:lookIndex}); }
        catch(err) { notifyIssue(err.message); } finally { preview.disabled=false; }
      };
      card.append(preview);
      const regenerate = el('button', 'subtle', '重新生成穿搭'); regenerate.type = 'button';
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
function setBusy(value) {
  busy = value;
  window.ChatAttachments?.setBusy(value);
  for (const id of ['personal-clothes', 'new-clothes']) if ($(id)) $(id).disabled = value;
  $('send').disabled = value;
  $('new-chat').disabled = value; $('mobile-new').disabled = value; $('send').textContent = value ? '整理中…' : '发送 ↑';
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
        const title = row.title?.trim() || '未命名对话';
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
            for (const turn of record.messages) { bubble('user', turn.user); showReply(turn.reply); }
            window.ChatAttachments?.clear();
            conversation = record.conversation_id; version = record.version;
            window.WardrobeJourney?.restore(conversation).catch(err=>notifyIssue(err.message));
            for (const list of [$('history'), $('mobile-history-list')]) {
              list.querySelectorAll('[aria-current]').forEach(item => item.removeAttribute('aria-current'));
              list.children[rows.indexOf(row)]?.setAttribute('aria-current', 'true');
            }
            $('history-status').textContent = ''; $('history-dialog').close();
          } catch (err) { notifyIssue(err.message); $('history-status').textContent = ''; }
          finally { setBusy(false); }
        };
        container.append(button);
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
async function sendMessage(resuming = false, outfitAction = null, cityAction = null, explorationAction = null) {
  const saved = resuming && pendingRun?.owner === session?.user?.id ? pendingRun : null;
  const attachmentOwner = session?.access_token;
  const inputValue = $('message').value;
  const draftImage = !outfitAction && !cityAction && !explorationAction ? window.ChatAttachments?.get() : null;
  const text = (explorationAction ? '沿用刚才的搭配要求，开启邂逅新衣，把系统参考款也纳入选择，继续完成刚才的搭配。' : null) || saved?.request.message || cityAction?.request?.message || (cityAction ? '按刚才的穿搭要求，结合选好的城市天气继续搭配。' : outfitAction ? '重新生成穿搭' : (inputValue.trim() || (draftImage ? '请看看这张图片里的穿搭。' : '')));
  if (!text || busy || !requireLogin()) return;
  if (window.CompanionSettings) { await window.CompanionSettings.ready; if (busy || !session) return; }
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
  const request = saved?.request || { ...(cityAction?.request || {}), message: text, conversation_id: conversation, expected_version: version, request_id: crypto.randomUUID(), confirm_plan: false };
  if (!saved && !cityAction && window.CompanionSettings?.getProfile()) request.companion_profile = window.CompanionSettings.getProfile();
  if (!saved && !request.assistant_persona) request.assistant_persona = request.companion_profile?.assistant_persona || (document.documentElement.dataset.stylistGender === 'male' ? 'male_calm_v1' : 'female_warm_v1');
  if (!saved) request.new_clothes = $('new-clothes')?.checked || false;
  if (!saved && selectedCity) request.location = selectedCity;
  if (!saved && !cityAction && selectedLook?.conversationId === conversation) request.selected_look_index = selectedLook.index;
  if (!saved && outfitAction) { request.regenerate_outfit = true; request.selected_look_index = outfitAction.look_index; request.regenerate_from_version = outfitAction.version; }
  if (!saved && !cityAction && !explorationAction && !request.regenerate_outfit && pendingUploadAnchor) { request.upload_action_id = pendingUploadAnchor; pendingUploadAnchor = null; updateUploadAnchor(); }
  if (!saved && draftImage) request.chat_image = draftImage;
  const chatOwner = session.user.id;
  savePending({owner: chatOwner, request});
  const userBubble = bubble('user', text);
  if(request.chat_image){const image=document.createElement('img');image.src=request.chat_image;image.alt='本轮图片附件';image.style.cssText='display:block;max-width:180px;max-height:180px;object-fit:contain;border-radius:12px;margin-top:8px';userBubble.append(image);}
  const pending = pendingBubble(request.assistant_persona);
  setBusy(true); $('notice').textContent = '';
  try {
    let received = false;
    while (!received) {
      try {
        const response = await fetch('/stylist-api/chat/stream', { method: 'POST', headers: headers(), body: JSON.stringify(request) });
        if (session?.user.id !== chatOwner) return;
        if (!response.ok) { const data = await response.json(); throw error(data.code, data.message); }
        const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = '';
        try {
          while (!received) {
            const { value, done } = await reader.read();
            if (session?.user.id !== chatOwner) return;
            buffer += decoder.decode(value, { stream: !done });
            let cut;
            while ((cut = buffer.indexOf('\n\n')) >= 0) {
              const block = buffer.slice(0, cut); buffer = buffer.slice(cut + 2);
              const kind = block.split('\n').find(x => x.startsWith('event: '))?.slice(7);
              const raw = block.split('\n').filter(x => x.startsWith('data: ')).map(x => x.slice(6)).join('\n');
              if (kind === 'error') { const data = JSON.parse(raw); throw error(data.code, data.message); }
              if (kind === 'progress') {
                const progress = JSON.parse(raw);
                if (progress.stage === 'new_clothes') {
                  setNewClothes(true);
                  if (!newClothesNotices.has(request.request_id)) { notifyIssue(progress.message); newClothesNotices.add(request.request_id); }
                } else pending.update(progress);
              }
              if (kind === 'result') {
                const reply = JSON.parse(raw); pending.stop(); showReply(reply, request); received = true;
                if (reply.pending_confirmation) showPlanApproval(request);
                else { savePending(null); dailyCheckin.completeChat(chatOwner); }
              }
            }
            if (done) break;
          }
        } finally { await reader.cancel().catch(() => {}); }
        if (!received) throw new TypeError('stream_disconnected');
      } catch (err) {
        if (!(err instanceof TypeError) && !['request_in_progress', 'server_draining'].includes(err.code)) throw err;
        if (!session || session.user.id !== pendingRun?.owner) throw error('authentication_expired', '请重新登录后继续原任务。');
        pending.update({stage: 'connecting', message: '连接正在恢复，已完成的步骤会保留…'});
        await new Promise(resolve => setTimeout(resolve, 2500));
      }
    }
    if (!cityAction && !explorationAction && !request.regenerate_outfit && $('message').value === inputValue) $('message').value = '';
    if(request.chat_image) window.ChatAttachments?.ack(request.chat_image);
    await refreshHistory();
  } catch (err) {
    if (session?.user.id !== chatOwner) return;
    if (err.code !== 'authentication_expired') savePending(null);
    pending.stop();
    if (err.code !== 'authentication_expired') notifyIssue((err.message || '请求未完成，请稍后重试。') + '\n' + (err.code === 'model_output_invalid' ? '输入还在，点「发送」就能重试。' : agentText('输入还在，可以调整后再发给衣衣。')));
    if (err.code === 'authentication_expired') expireSession(err.message);
  } finally { pending.stop(); if (!session || session.user.id === chatOwner) setBusy(false); }
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
$('chat-form').onsubmit = event => { event.preventDefault(); sendMessage(); };
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
  pendingUploadAnchor=action;pendingAnchorOwner=session?.user?.id;updateUploadAnchor();
  const draft=$('message').value.trim();$('message').value=draft&&!draft.startsWith('用我刚上传')?'用我刚上传的这件衣服，'+draft:'用我刚上传的这件衣服，结合自己的衣橱搭一套。';$('message').focus();
}});
for (const id of ['upload-open','welcome-upload']) if ($(id)) $(id).onclick=()=>{if(requireLogin()) window.WardrobeJourney.upload('garment');};
if ($('twin-open')) $('twin-open').onclick=()=>{if(requireLogin()) window.WardrobeJourney.twins().catch(err=>notifyIssue(err.message));};
if ($('journey-records-open')) $('journey-records-open').onclick=()=>{if(requireLogin()) window.WardrobeJourney.history().catch(err=>notifyIssue(err.message));};

if (session) window.CompanionSettings?.setOwner(session.user.id, api);
loginStatus(); updateCityLabel(); if (session) { refreshHistory(); if (selectedCity) loadForecast(); }

if (pendingRun && session && pendingRun.owner === session.user.id) sendMessage(true);
// Shared Stylist attachment flow. Wardrobe ingestion remains in its dedicated entry.
if (!document.getElementById('yijian-agent-root')) {
  $('upload-open').textContent='＋';
  $('upload-open').onclick=()=>notifyIssue('附件入口正在准备，请稍等一下。');
  import('/static/closet-app/chat-attachments.js').then(({mountChatAttachments})=>{
    const trigger=$('upload-open');trigger.textContent='＋';
    mountChatAttachments(document,trigger);
  }).catch(()=>notifyIssue('附件入口暂时没能加载，请稍后重新打开页面。'));
}
