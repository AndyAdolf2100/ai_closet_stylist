'use strict';
const $ = id => document.getElementById(id);
const KEY = 'ai-closet-stylist-session-v1';
let session = null, conversation = null, version = 0, busy = false, imageAction = null;
let selectedCity = null, forecastScope = 'day', forecastBusy = false, forecastSequence = 0;
const CITY_KEY = 'ai-closet-stylist-city-v1';
try { selectedCity = JSON.parse(sessionStorage.getItem(CITY_KEY) || 'null'); } catch { selectedCity = null; }
try { session = JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch { session = null; }
let lastSessionOwner = session?.user?.id || null;
let cityCatalog = null, warningSequence = 0, historySequence = 0;
const citiesReady = fetch('/static/china-cities.json').then(r => { if (!r.ok) throw new Error('城市列表加载失败，请刷新后重试。'); return r.json(); }).then(data => {
  cityCatalog = data; cityPicker.setCatalog(data); return data;
}).catch(err => { $('location-status').textContent = err.message; return null; });
const el = (tag, cls, text) => { const node = document.createElement(tag); if (cls) node.className = cls; if (text != null) node.textContent = text; return node; };
let locationSequence = 0, locationSaving = false;
const cityPicker = new CityPicker($('city-picker'), { onChange: () => {
  locationSequence++; $('locate-me').disabled = locationSaving;
  $('location-status').textContent = ''; updateLocationSave();
} });
function updateLocationSave() { $('location-save').disabled = locationSaving || !cityPicker.getValue(); }
const error = (code, message) => Object.assign(new Error(message), { code });
function loginStatus() { $('login-open').textContent = session ? '衣橱已连接' : '登录衣橱'; }
function expireSession(message) {
  lastSessionOwner = session?.user?.id || lastSessionOwner;
  session = null; sessionStorage.removeItem(KEY); loginStatus();
  clearHistory();
  warningSequence++; $('official-warnings').replaceChildren(); $('official-warnings').hidden = true;
  $('login-error').textContent = message || '登录状态已失效，请重新登录。原输入和当前对话会保留。';
  $('notice').textContent = $('login-error').textContent;
  for (const id of ['service-dialog', 'location-dialog', 'history-dialog']) if ($(id).open) $(id).close();
  if (!$('login-dialog').open) $('login-dialog').showModal();
}
function headers() { return { 'Content-Type': 'application/json', Authorization: 'Bearer ' + (session?.access_token || '') }; }
function requireLogin() { if (!session) { $('login-dialog').showModal(); return false; } return true; }
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: headers() });
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401) expireSession(data.message);
    throw error(data.code, data.message || '服务暂时未完成请求，请稍后重试。');
  }
  return data;
}
function scrollBottom() { $('feed').scrollTop = $('feed').scrollHeight; }
function mascot(mood = 'greeting', size = '') {
  const node = el('div', 'mascot companion-sprite ' + size); node.dataset.mood = mood;
  // Offset each portrait so a conversation does not blink in unison.
  node.style.setProperty('--blink-delay', `-${(Math.random() * 15).toFixed(2)}s`);
  node.setAttribute('role', 'img'); node.setAttribute('aria-label', { greeting: '衣衣向你打招呼', weather: '衣衣查看天气', wardrobe: '衣衣挑选衣服', thinking: '衣衣认真思考', happy: '衣衣展示搭配', rain: '衣衣撑伞提醒' }[mood] || '衣衣');
  return node;
}
function weatherIcon(text) { return /雪/.test(text) ? '❄' : /雷/.test(text) ? '⛈' : /雨/.test(text) ? '☂' : /雾|霾/.test(text) ? '〰' : /阴|云/.test(text) ? '☁' : '☀'; }
function forecastCard(data, compact = false) {
  const card = el('section', 'forecast-card');
  WeatherVisuals.background(card, data.days);
  const heading = el('div', 'forecast-heading'); const wet = data.days?.some(day => /雨|雪/.test(day.condition_day + day.condition_night)); heading.append(mascot(wet ? 'rain' : 'weather', 'weather-mascot'));
  const title = el('div'); title.append(el('strong', '', `${data.city_name} · ${data.scope === 'week' ? '本周天气' : data.scope === 'next7' ? '未来七天' : '出门天气'}`), el('p', '', '衣衣的天气小叮咛')); heading.append(title);
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
  for (const day of data.days || []) for (const tip of day.reminders || []) {
    const row = el('div', 'weather-tip ' + tip.severity);
    row.append(el('span', 'tip-icon', { rain: '☂', snow: '❄', fog: '〰', wind: '彡', layers: '♡', cold: '❄', heat: '☀', storm: 'ϟ' }[tip.kind] || '✿'));
    const copy = el('div'); copy.append(el('strong', '', (data.days.length > 1 ? `${day.date.slice(5)} ` : '') + tip.title), el('p', '', tip.text)); row.append(copy); alerts.append(row);
  }
  if (alerts.childNodes.length) card.append(alerts);
  const details = el('details', 'weather-evidence'); details.append(el('summary', '', '预报范围与数据说明'));
  for (const text of data.warnings || []) details.append(el('p', '', text));
  if (data.fetched_at) details.append(el('p', '', `查询时间：${new Date(data.fetched_at).toLocaleString('zh-CN')} · ${data.timezone || 'Asia/Shanghai'}`));
  details.append(el('p', '', data.notice)); card.append(details);
  if (compact) card.classList.add('compact');
  return card;
}
function updateCityLabel() { $('location-open').textContent = selectedCity ? '⌖ ' + selectedCity.city_name : '⌖ 选择城市 / 定位'; $('forecast-refresh').hidden = !selectedCity; }
function showWarnings(data) {
  const box = $('official-warnings'); box.replaceChildren(); box.hidden = false;
  if (data.alerts?.length) {
    box.append(el('div', 'official-warning-heading', `${data.city_name} · 当前气象预警`));
    for (const alert of data.alerts) { const card = WeatherVisuals.warningCard(alert); if (card) box.append(card); }
  }
  if (data.status !== 'ok') box.append(el('p', 'warning-feed-notice', data.message || '暂时无法确认最新预警，请查看当地气象台发布。'));
  else if (!data.alerts?.length) box.append(el('p', 'warning-feed-notice', `${data.city_name} · 本次预警数据未返回生效预警，出行前请留意最新发布。`));
}
async function loadWarnings(location = selectedCity) {
  if (!location || !session) return;
  const sequence = ++warningSequence;
  try {
    const data = await api('/api/weather/alerts', { method: 'POST', body: JSON.stringify({ location }) });
    if (sequence === warningSequence && session && selectedCity?.city_name === location.city_name && selectedCity?.province_name === location.province_name) showWarnings(data);
  } catch (err) { if (sequence === warningSequence && session) showWarnings({ status: 'unavailable', alerts: [], message: '预警更新未完成，请留意当地气象台发布；这不代表没有预警。' }); }
}
async function loadForecast(location = selectedCity) {
  if (!location || !requireLogin()) return false;
  const sequence = ++forecastSequence;
  if (location.city_name !== selectedCity?.city_name || location.province_name !== selectedCity?.province_name) {
    warningSequence++; $('official-warnings').replaceChildren(el('p', 'warning-feed-notice', '正在确认新城市，预警信息随后更新…')); $('official-warnings').hidden = false;
  }
  forecastBusy = true; $('forecast-refresh').disabled = true;
  $('location-label').textContent = '衣衣正在看看天气…';
  try {
    const data = await api('/api/weather/forecast', { method: 'POST', body: JSON.stringify({ location, scope: forecastScope }) });
    if (sequence !== forecastSequence) return false;
    selectedCity = { city_name: data.city_name, province_name: data.province_name }; sessionStorage.setItem(CITY_KEY, JSON.stringify(selectedCity)); updateCityLabel();
    loadWarnings(selectedCity);
    let panel = $('weather-panel'); if (!panel) { panel = el('section'); panel.id = 'weather-panel'; $('feed').prepend(panel); }
    panel.hidden = false; panel.replaceChildren();
    const tabs = el('div', 'weather-tabs');
    for (const [scope, label] of [['day', '今天 · 早晚'], ['week', '本周 · 逐日']]) { const button = el('button', forecastScope === scope ? 'active' : '', label); button.onclick = () => { if (forecastBusy) return; forecastScope = scope; loadForecast(); }; tabs.append(button); }
    panel.append(tabs, forecastCard(data, true)); $('location-label').textContent = '出门前，再照顾一下天气';
    return true;
  } catch (err) {
    if (sequence !== forecastSequence) return false;
    if (session) showWarnings({ status: 'unavailable', alerts: [], message: '城市或天气确认未完成，暂时无法核对对应预警。' });
    $('location-label').textContent = '天气暂未取到，可稍后刷新'; $('location-status').textContent = err.message;
    $('notice').textContent = err.message;
    if ($('weather-panel')) { $('weather-panel').replaceChildren(el('p', 'weather-unavailable', '这次没有取到最新天气，先不显示旧预报。可以稍后刷新。')); }
    return false;
  } finally { if (sequence === forecastSequence) { forecastBusy = false; $('forecast-refresh').disabled = false; } }
}
function pendingBubble(persona) {
  const node = bubble('assistant', ''); node.classList.add('pending');
  const body = el('div', 'companion-wait'); const avatar = mascot('thinking'); const copy = el('div');
  const male = persona === 'male_calm_v1';
  const status = el('strong', '', male ? '收到，正在连接服务。' : '收到啦，正在连接服务。');
  const extra = el('p', '', male ? '我会按你这次的要求处理。' : '我会照顾你这次提到的要求。');
  copy.append(status, extra); body.append(avatar, copy); node.append(body);
  const expressions = { connecting: ['greeting', '连接中'], understanding: ['thinking', '整理需求'], weather: ['weather', '核对天气'], wardrobe: ['wardrobe', '挑选衣物'], styling: ['thinking', '构思搭配'], checking: ['happy', '核对方案'] };
  const timer = setInterval(() => { extra.textContent = male ? '还在等待服务返回，结果到了就给你。' : '这次等得久一些，还在等待服务返回。'; }, 15000);
  return { node, update(data) { const state = expressions[data.stage] || expressions.styling; avatar.dataset.mood = state[0]; avatar.setAttribute('aria-label', '衣衣正在' + state[1]); status.textContent = data.message; }, stop() { clearInterval(timer); node.remove(); } };
}
function bubble(role, text) {
  $('welcome')?.remove();
  const node = el('section', 'bubble ' + role);
  if (role === 'assistant') { const author = el('div', 'author'); author.append(mascot('greeting', 'avatar-mini'), el('span', '', '衣衣 · 私人搭配师')); node.append(author); }
  node.append(el('div', '', text)); $('feed').append(node); scrollBottom(); return node;
}
function bulletSection(card, title, items) {
  if (!items?.length) return;
  card.append(el('h4', '', title)); const list = el('ul');
  for (const item of items) list.append(el('li', '', item)); card.append(list);
}
function showReply(reply) {
  conversation = reply.conversation_id; version = reply.version;
  const node = bubble('assistant', reply.message);
  const label = { advice: '穿法建议', outfit: '真实衣橱搭配', concept: '文字参考 · 未完成商品匹配', clarification: '需要你确认' };
  if (!reply.conversation_only) node.prepend(el('div', 'badge', reply.weather_only ? '天气查询' : label[reply.delivery] || '穿搭建议'));
  if (reply.weather?.source === 'itinerary_forecast') {
    const route = el('section', 'itinerary-weather');
    route.setAttribute('aria-label', '行程各地天气');
    for (const stop of reply.weather.locations || []) {
      if (stop.forecast?.days?.length) route.append(forecastCard(stop.forecast));
      else route.append(el('div', 'warning', stop.message || `${stop.city_name}的天气暂时还查不到。`));
    }
    node.append(route);
  } else if (reply.weather?.days?.length) node.append(forecastCard(reply.weather));
  for (const [lookIndex, look] of (reply.looks || []).entries()) {
    const card = el('article', 'look'); card.append(el('h3', '', look.title));
    if (look.items?.length) {
      const grid = el('div', 'products');
      for (const item of look.items) {
        const product = el('div', 'product');
        const url = (item.cutout_image || item.original_image || '').replace(/^http:/i, 'https:');
        if (url && /^https:\/\//i.test(url)) {
          const img = el('img'); img.src = url; img.alt = (item.color || '') + (item.secondary_class_name || item.class_name || '单品');
          img.loading = 'lazy'; img.referrerPolicy = 'no-referrer';
          const imageButton = el('button', 'product-image'); imageButton.type = 'button';
          const original = (item.original_image || '').replace(/^http:/i, 'https:');
          imageButton.dataset.previewSrc = /^https:\/\//i.test(original) ? original : url;
          imageButton.setAttribute('aria-label', '放大查看' + img.alt);
          imageButton.append(img); product.append(imageButton);
        }
        product.append(el('div', '', (item.color || '') + (item.secondary_class_name || item.class_name || item.title || '单品')));
        product.append(el('span', '', item.source === 'user' ? '个人衣橱' : '系统衣橱')); grid.append(product);
      }
      card.append(grid);
    } else { bulletSection(card, '穿什么', look.pieces); }
    bulletSection(card, '为什么这样搭', look.why);
    bulletSection(card, '照着这样穿', look.how);
    bulletSection(card, '穿着提醒', look.notes);
    if (look.items?.length) {
      const preview = el('button', 'subtle', '查看这套的试穿费用 ↗');
      preview.onclick = async () => {
        if (busy || !requireLogin()) return;
        if (conversation !== reply.conversation_id || version !== reply.version) { $('notice').textContent = '这是历史方案，请先打开对应的最新对话。'; return; }
        preview.disabled = true;
        try {
          const quote = await api('/api/images/quote', { method: 'POST', body: JSON.stringify({ conversation_id: conversation, version, look_index: lookIndex }) });
          imageAction = quote.action_id; $('image-details').replaceChildren(el('p', '', quote.title), el('strong', '', `本次将消耗 ${quote.points_cost} 积分`));
          for (const note of quote.notices) $('image-details').append(el('p', '', note));
          $('image-status').textContent = ''; $('image-confirm').disabled = false; $('image-cancel').textContent = '暂不生成'; $('image-dialog').showModal();
        } catch (err) { $('notice').textContent = err.message; } finally { preview.disabled = false; }
      };
      card.append(preview);
    }
    node.append(card);
  }
  for (const warning of reply.warnings || []) node.append(el('div', 'warning', warning));
  if (reply.follow_ups?.length) {
    const actions = el('div', 'followups');
    for (const text of reply.follow_ups) { const button = el('button', '', text); button.onclick = () => { $('message').value = text; $('message').focus(); }; actions.append(button); }
    node.append(actions);
  }
  scrollBottom();
}
function setBusy(value) {
  busy = value; $('send').disabled = value; $('source').disabled = value; $('weather').disabled = value;
  $('new-chat').disabled = value; $('mobile-new').disabled = value; $('send').textContent = value ? '整理中…' : '发送 ↑';
  $('mobile-history').disabled = value; $('history-refresh').disabled = value;
  $('logout').disabled = value; $('login-open').disabled = value;
  $('location-open').disabled = value;
}
async function refreshHistory() {
  if (!session) return;
  const owner = session.user.id, sequence = ++historySequence;
  try {
    const rows = await api('/api/conversations');
    if (session?.user.id !== owner || sequence !== historySequence) return;
    $('history-status').textContent = rows.length ? '' : '还没有历史对话，开始聊聊吧。';
    for (const container of [$('history'), $('mobile-history-list')]) {
      container.replaceChildren();
      for (const row of rows) {
        const button = el('button', '', row.updated_at + ' · ' + row.version + ' 轮'); button.type = 'button';
        if (row.id === conversation) button.setAttribute('aria-current', 'true');
        button.onclick = async () => {
          if (busy || session?.user.id !== owner) return;
          setBusy(true); $('history-status').textContent = '正在打开对话…';
          try {
            const record = await api('/api/conversations/' + row.id);
            if (session?.user.id !== owner) return;
            $('feed').replaceChildren();
            for (const turn of record.messages) { bubble('user', turn.user); showReply(turn.reply); }
            conversation = record.conversation_id; version = record.version;
            $('source').value = ''; $('weather').value = '';
            for (const list of [$('history'), $('mobile-history-list')]) {
              list.querySelectorAll('[aria-current]').forEach(item => item.removeAttribute('aria-current'));
              list.children[rows.indexOf(row)]?.setAttribute('aria-current', 'true');
            }
            $('history-status').textContent = ''; $('history-dialog').close();
          } catch (err) { $('notice').textContent = err.message; $('history-status').textContent = err.message; }
          finally { setBusy(false); }
        };
        container.append(button);
      }
    }
  } catch (err) { if (session?.user.id === owner && sequence === historySequence) { $('notice').textContent = err.message; $('history-status').textContent = err.message; } }
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
  if (value) sessionStorage.setItem(PENDING_KEY, JSON.stringify(value));
  else sessionStorage.removeItem(PENDING_KEY);
}
async function sendMessage(resuming = false) {
  const saved = resuming && pendingRun?.owner === session?.user?.id ? pendingRun : null;
  const text = saved?.request.message || $('message').value.trim();
  if (!text || busy || !requireLogin()) return;
  const request = saved?.request || { message: text, conversation_id: conversation, expected_version: version, request_id: crypto.randomUUID(), confirm_plan: $('confirm-plan').checked };
  if (!saved) request.assistant_persona = document.documentElement.dataset.stylistGender === 'male' ? 'male_calm_v1' : 'female_warm_v1';
  if (!saved && $('source').value) request.source = $('source').value;
  if (!saved && $('weather').value) request.weather_policy = $('weather').value;
  if (!saved && selectedCity) request.location = selectedCity;
  savePending({owner: session.user.id, request});
  bubble('user', text); const pending = pendingBubble(request.assistant_persona);
  setBusy(true); $('notice').textContent = '';
  try {
    let received = false;
    while (!received) {
      try {
        const response = await fetch('/api/chat/stream', { method: 'POST', headers: headers(), body: JSON.stringify(request) });
        if (!response.ok) { const data = await response.json(); throw error(data.code, data.message); }
        const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = '';
        try {
          while (!received) {
            const { value, done } = await reader.read(); buffer += decoder.decode(value, { stream: !done });
            let cut;
            while ((cut = buffer.indexOf('\n\n')) >= 0) {
              const block = buffer.slice(0, cut); buffer = buffer.slice(cut + 2);
              const kind = block.split('\n').find(x => x.startsWith('event: '))?.slice(7);
              const raw = block.split('\n').filter(x => x.startsWith('data: ')).map(x => x.slice(6)).join('\n');
              if (kind === 'error') { const data = JSON.parse(raw); throw error(data.code, data.message); }
              if (kind === 'progress') pending.update(JSON.parse(raw));
              if (kind === 'result') {
                const reply = JSON.parse(raw); pending.stop(); showReply(reply); received = true;
                if (reply.pending_confirmation) showPlanApproval(request);
                else savePending(null);
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
    $('message').value = ''; await refreshHistory();
  } catch (err) {
    if (err.code !== 'authentication_expired') savePending(null);
    pending.stop(); bubble('error', err.message || '请求未完成，请稍后重试。');
    $('notice').textContent = err.code === 'model_output_invalid' ? '输入还在，点「发送」就能重试。' : '输入还在，可以调整后再发给衣衣。';
    if (err.code === 'authentication_expired') expireSession(err.message);
  } finally { pending.stop(); setBusy(false); }
}
function showPlanApproval(request) {
  const actions = el('div', 'followups');
  for (const [approved, text] of [[true, '确认需求，继续搭配'], [false, '取消这次生成']]) {
    const button = el('button', '', text);
    button.onclick = async () => {
      if (busy || !requireLogin()) return;
      setBusy(true);
      try {
        const reply = await api('/api/chat/approval', {method:'POST', body:JSON.stringify({request, approved})});
        savePending(null); actions.remove(); showReply(reply); await refreshHistory();
      } catch (err) { $('notice').textContent = err.message; }
      finally { setBusy(false); }
    };
    actions.append(button);
  }
  $('feed').append(actions); scrollBottom();
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
$('new-chat').onclick = resetChat; $('mobile-new').onclick = resetChat;
$('mobile-history').onclick = async () => {
  if (busy || !requireLogin()) return;
  $('history-dialog').showModal(); $('history-status').textContent = '正在加载历史对话…';
  await refreshHistory();
};
$('history-close').onclick = () => $('history-dialog').close();
$('history-refresh').onclick = async () => {
  $('history-refresh').disabled = true; $('history-status').textContent = '正在刷新…';
  try { await refreshHistory(); } finally { $('history-refresh').disabled = busy; }
};
$('login-open').onclick = () => $('login-dialog').showModal(); $('login-cancel').onclick = () => $('login-dialog').close();
$('logout').onclick = () => { savePending(null); sessionStorage.removeItem(KEY); sessionStorage.removeItem(CITY_KEY); selectedCity = null; forecastSequence++; warningSequence++; $('official-warnings').replaceChildren(); $('official-warnings').hidden = true; forecastBusy = false; session = null; lastSessionOwner = null; conversation = null; version = 0; clearHistory(); $('history-dialog').close(); $('feed').replaceChildren(); updateCityLabel(); $('location-label').textContent = '让穿搭也照顾天气'; loginStatus(); };
$('login-form').onsubmit = async event => {
  event.preventDefault(); $('login-submit').disabled = true; $('login-error').textContent = '';
  try {
    let device = sessionStorage.getItem('stylist-device-id');
    if (!device) { device = 'stylist-' + crypto.randomUUID(); sessionStorage.setItem('stylist-device-id', device); }
    const response = await fetch('/auth/mobile-login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mobile: $('mobile').value, code: $('code').value, device_id: device }) });
    const data = await response.json(); if (!response.ok) throw new Error(data.message || '登录未成功');
    if (lastSessionOwner && lastSessionOwner !== data.user.id) { conversation = null; version = 0; $('feed').replaceChildren(); clearHistory(); }
    session = data; lastSessionOwner = data.user.id; sessionStorage.setItem(KEY, JSON.stringify(data)); $('code').value = ''; $('notice').textContent = ''; $('login-dialog').close(); loginStatus(); await refreshHistory(); if (selectedCity) loadForecast();
  } catch (err) { $('login-error').textContent = err.message; } finally { $('login-submit').disabled = false; }
};
$('check-apis').onclick = async () => {
  if (!requireLogin()) return;
  $('service-dialog').showModal(); $('service-results').textContent = '正在逐项查询，请稍候…';
  try { const report = await api('/api/integrations/check', { method: 'POST' }); $('service-results').textContent = report.results.map(x => `${x.interface}\n  ${x.status} · ${x.code}${x.latency_ms != null ? ' · ' + x.latency_ms + 'ms' : ''}${x.facts ? '\n  ' + JSON.stringify(x.facts) : ''}`).join('\n\n'); }
  catch (err) { $('service-results').textContent = err.message; }
};
$('service-close').onclick = () => $('service-dialog').close();
$('image-cancel').onclick = async () => {
  if ($('image-cancel').disabled) return;
  if (imageAction && !$('image-confirm').disabled) {
    try { await api('/api/images/' + imageAction + '/confirm', { method: 'POST', body: JSON.stringify({ confirmed: false }) }); }
    catch (err) { $('notice').textContent = err.message; }
  }
  $('image-dialog').close(); imageAction = null;
};
$('image-confirm').onclick = async () => {
  if (!imageAction || $('image-confirm').disabled) return;
  $('image-confirm').disabled = true; $('image-cancel').disabled = true;
  const waiting = el('div', 'companion-wait'); waiting.append(mascot('wardrobe'), el('p', '', '已确认本次费用，衣衣正在提交试穿。请稍等，不要重复生成。')); $('image-status').replaceChildren(waiting);
  try {
    const action = await api('/api/images/' + imageAction + '/confirm', { method: 'POST', body: JSON.stringify({ confirmed: true }) });
    $('image-status').textContent = action.status === 'completed' ? '试穿完成' : '状态：' + action.status;
    const image = (action.result?.result_image_url || action.result?.result_image || '').replace(/^http:/i, 'https:');
    if (image && /^https:\/\//i.test(image)) { const img = el('img'); img.src = image; img.alt = '本次搭配的试穿预览'; img.style.width = '100%'; img.referrerPolicy = 'no-referrer'; $('image-details').append(img); }
  } catch (err) { $('image-status').textContent = err.message; }
  finally { $('image-cancel').disabled = false; $('image-cancel').textContent = '关闭'; }
};
$('location-open').onclick = async () => {
  if (!requireLogin()) return;
  const owner = session.user.id;
  await citiesReady;
  if (!session || session.user.id !== owner) return;
  if (!cityCatalog) { $('notice').textContent = '城市列表加载失败，请刷新后重试。'; return; }
  $('location-status').textContent = ''; updateLocationViewport(); $('location-dialog').showModal();
  cityPicker.setValue(selectedCity); updateLocationSave();
  // Keep the software keyboard closed until the user chooses to search.
  $('location-cancel').focus({ preventScroll: true });
};
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
  locationSequence++; $('locate-me').disabled = locationSaving; updateLocationSave();
});
$('locate-me').onclick = async () => {
  if (!requireLogin()) return;
  if (!window.isSecureContext || !navigator.geolocation) { $('location-status').textContent = '当前浏览器环境不支持定位，可以搜索或点选城市。'; return; }
  const sequence = ++locationSequence, owner = session.user.id;
  const current = () => sequence === locationSequence && session?.user.id === owner && $('location-dialog').open;
  $('locate-me').disabled = true; $('location-status').textContent = '请允许浏览器访问位置，也可以直接搜索或点选城市。';
  try {
    const position = await new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }));
    if (!current()) return;
    const city = await api('/api/location/resolve', { method: 'POST', body: JSON.stringify({ latitude: position.coords.latitude, longitude: position.coords.longitude, coordinate_system: 'wgs84' }) });
    await citiesReady;
    if (!current()) return;
    if (!cityPicker.setValue(city)) { $('location-status').textContent = '已识别到 ' + city.city_name + '，请搜索或点选对应城市。'; return; }
    $('location-status').textContent = '找到 ' + city.city_name + (city.district_name ? ' · ' + city.district_name : '') + ' 啦，请确认后使用。' + (position.coords.accuracy > 5000 ? '浏览器定位精度较低，如果不是你所在的城市，请手动修改。' : '');
  } catch (err) { if (current()) $('location-status').textContent = err.code === 1 ? '定位权限未开启，搜索或点选城市也可以。' : err.code === 3 ? '定位超时啦，可以再试一次或搜索城市。' : err.message || '暂时没有定位成功，可以搜索或点选城市。'; }
  finally { if (current()) { $('locate-me').disabled = false; updateLocationSave(); } }
};
$('location-form').onsubmit = async event => {
  event.preventDefault();
  if (locationSaving) return;
  if (forecastBusy) { $('location-status').textContent = '天气正在更新，请稍后再确认。'; return; }
  const city = cityPicker.getValue();
  if (!city) { $('location-status').textContent = '请先从列表中选择一座城市。'; cityPicker.input.focus(); return; }
  locationSequence++; locationSaving = true; $('city-picker').inert = true;
  $('locate-me').disabled = true; updateLocationSave(); $('location-save').textContent = '正在查询天气…';
  try { if (await loadForecast(city)) { $('location-dialog').close(); $('notice').textContent = ''; $('weather-panel')?.scrollIntoView({ block: 'start', behavior: 'smooth' }); } }
  finally {
    locationSaving = false; $('city-picker').inert = false; $('locate-me').disabled = false;
    $('location-save').textContent = '确认城市，看看天气'; updateLocationSave();
  }
};
$('forecast-refresh').onclick = () => { if (!forecastBusy) loadForecast(); };
loginStatus(); updateCityLabel(); if (session) { refreshHistory(); if (selectedCity) loadForecast(); }
setInterval(() => { if (!document.hidden && session && selectedCity && !forecastBusy) loadWarnings(); }, 120000);
document.addEventListener('visibilitychange', () => { if (!document.hidden && session && selectedCity) loadWarnings(); });

if (pendingRun && session && pendingRun.owner === session.user.id) sendMessage(true);
