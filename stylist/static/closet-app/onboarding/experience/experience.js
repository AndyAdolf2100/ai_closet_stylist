/* Isolated concept: no authentication, storage, network mutations or real geolocation. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const base = '../../first-visit/assets/';
  const assets = {source: base + 'tryon-example.png', shirt: base + 'shirt-example.png', jeans: base + 'jeans-example.png', outfit: base + 'outfit-example.png', avatar: 'avatar-sample.png'};
  const state = {step: 3, outfit: 'empty', avatar: 'empty', source: null, person: null, sourceCustom: false, personCustom: false, selected: [true, true], city: '', locationAsked: false, result: false, busy: false};
  let pending = null;
  let restoreFocus = null;
  const ownedUrls = new Set();
  const dialog = $('#flow-dialog');
  const screen = $('#screen');
  const sourceImage = () => state.source || assets.source;
  const personImage = () => state.person || assets.avatar;
  const picture = (src, alt, cls = '') => `<img src="${src}" alt="${alt}" class="${cls}">`;
  const button = (action, label, cls = '') => `<button type="button" data-action="${action}" class="${cls}">${label}</button>`;
  const announce = text => { $('#announcement').textContent = text; };
  function modal(content) {
    if (!dialog.open) restoreFocus = document.activeElement;
    dialog.innerHTML = content;
    if (!dialog.open) dialog.showModal();
  }
  function closeModal() { if (dialog.open) dialog.close(); }
  dialog.addEventListener('close', () => { if (restoreFocus?.isConnected) restoreFocus.focus({preventScroll: true}); });
  function resetOutfit() { state.outfit = 'source'; state.selected = [true, true]; state.result = false; }
  function resetAvatar() { state.avatar = 'source'; state.result = false; }
  function navigate(step) {
    if (state.busy) return;
    closeModal();
    state.step = step;
    render();
    const heading = screen.querySelector('h2');
    heading.tabIndex = -1;
    heading.focus({preventScroll: true});
    if (step === 5 && !state.locationAsked) { state.locationAsked = true; locationPrompt(); }
  }
  function locationPrompt() {
    modal(`<p class="dialog-kicker">A LITTLE CARE FOR TODAY</p><div class="dialog-symbol" aria-hidden="true">⌖</div><h2 id="dialog-title">今天，在哪里穿这套？</h2><p>有了所在城市，就可以把天气也放进穿搭的考虑里。只选城市也可以。</p><p class="dialog-hint">定位交互示意 · 此处不会弹系统权限或读取真实位置。</p><div class="dialog-actions">${button('locate', '开启定位 · 示例上海', 'primary')}${button('cities', '手动选择城市')}${button('decline-location', '暂不定位，继续试穿', 'quiet')}</div>`);
  }
  function cityPicker() {
    modal(`<p class="dialog-kicker">YOUR CITY</p><h2 id="dialog-title">选一座城市</h2><p class="dialog-hint">本页城市与天气均为示例，不查询真实天气。</p><div class="dialog-actions city-options">${['上海','北京','杭州','广州'].map(city => button('city-' + city, city)).join('')}</div><div class="dialog-actions">${button('decline-location', '暂不选择', 'quiet')}</div>`);
  }
  function feePrompt(kind) {
    const data = {
      extract: ['把照片里的喜欢，留下来', '穿搭照拆分与单品确认', '正式流程先读取拆衣／入柜报价，确认后才开始处理。', '拆衣与入柜'],
      avatar: ['确认这张试穿形象', '人物形象检查与创建', '正式流程先检查照片，再展示数字形象报价与独立确认。', '数字形象'],
      tryon: ['试着穿上，这一套', '当前搭配 + 已确认的数字形象', '正式流程重新读取试穿报价，余额与积分由服务端返回。', '搭配试穿']
    }[kind];
    modal(`<p class="dialog-kicker">ONE SMALL CONFIRMATION</p><h2 id="dialog-title">${data[0]}</h2><p>${data[1]}</p><div class="cost-lines"><div><span>本次内容</span><strong>${data[3]}</strong></div><div><span>积分费用</span><strong>正式接入后显示报价</strong></div></div><p class="dialog-hint">${data[2]} 本次只展示固定示例，不上传、不创建任务、不扣积分。</p><div class="dialog-actions">${button('confirm-' + kind, '确认，查看示意', 'primary')}${button('close-dialog', '再看看', 'quiet')}</div>`);
  }
  function simulate(kind) {
    if (state.busy) return;
    closeModal();
    state.busy = true;
    render();
    pending = setTimeout(() => {
      pending = null;
      if (kind === 'extract') state.outfit = 'items';
      if (kind === 'avatar') state.avatar = 'ready';
      if (kind === 'tryon') state.result = true;
      state.busy = false;
      render();
      announce('示例已就绪。');
    }, 700);
  }
  function renderOutfit() {
    if (state.outfit === 'empty') return `<div class="demo-gallery"><div class="reference-photo">${picture(assets.source, '内置人物穿搭示例照片')}<span class="photo-label">一张喜欢的穿搭照</span></div><span class="gallery-arrow" aria-hidden="true">→</span><div class="photo-pieces"><div class="photo-piece">${picture(assets.shirt, '蓝色衬衫示例')}<span>拆成单件衣服</span></div><div class="photo-piece">${picture(assets.jeans, '牛仔裤示例')}<span>组成你的搭配</span></div></div></div><p class="under-caption">从喜欢的一张照片，开始整理第一套搭配。</p>${button('sample-source', '先用示例照片体验 ↗', 'text-action sample-action')}<p class="upload-note">选择完整、清楚的穿搭照片，衣服看得见会更好。上方为预期效果示意。</p>`;
    if (state.outfit === 'source') return `<div class="photo-preview">${picture(sourceImage(), '待确认的穿搭照片')}<span class="tag">${state.sourceCustom ? '本地照片预览' : '示例穿搭照'}</span></div><div class="status-line"><span>照片已选好</span>${button('choose-source', '重新选择')}</div><p class="upload-note">${state.sourceCustom ? '照片只留在当前页面。点击继续将展示固定示例，不会识别或处理这张照片。' : '先确认这张照片，再看看里面的单件衣服。'}</p>`;
    if (state.outfit === 'items') return `<div class="section-head"><h3>确认这两件衣服</h3><span class="tag">拆分示例</span></div><div class="item-grid">${[[assets.shirt, '浅蓝衬衫', '上装'], [assets.jeans, '浅蓝牛仔裤', '下装']].map(([src, title, category], i) => `<button class="item-choice" data-action="toggle-${i}" aria-pressed="${state.selected[i]}">${picture(src, title)}<span class="check" aria-hidden="true">✓</span><strong>${title}</strong><small>${category}</small></button>`).join('')}</div><p class="upload-note">示例单品可点按取消或重新选中。这一套需要上装与下装，确认后再组成搭配。</p>${button('choose-source', '换一张穿搭照', 'text-action')}`;
    return `<div class="section-head"><span class="success-label">第一套搭配，准备好了</span><span class="tag">示例搭配</span></div><div class="look-board"><div class="board-images">${picture(assets.shirt, '已确认的浅蓝衬衫')}${picture(assets.jeans, '已确认的浅蓝牛仔裤')}</div><div class="board-title"><strong>把日常，穿得轻松一点</strong><span>2 件单品</span></div></div><div class="flow-mini"><span>穿搭照片</span><span>→</span><span>确认单品</span><span>→</span><b>一套搭配</b></div><p class="upload-note">接下来，选一张用于试穿的人物照片，看看这一套穿在身上的样子。</p>${button('edit-items', '重新确认单品', 'text-action')}`;
  }
  function renderAvatar() {
    const isEmpty = state.avatar === 'empty';
    return `<div class="avatar-frame">${picture(isEmpty ? assets.avatar : personImage(), isEmpty ? '内置数字形象示例' : '已选人物照片')}<span class="tag">${isEmpty ? '人物形象示例' : state.avatar === 'ready' ? '已确认 · 本页示意' : state.personCustom ? '本地照片预览' : '示例人物照片'}</span></div>${state.avatar === 'ready' ? '<p class="under-caption">这张形象，会和上一页的搭配一起用于试穿。</p>' : '<div class="avatar-tips"><span class="avatar-tip">单人正面</span><span class="avatar-tip">全身清楚</span><span class="avatar-tip">自然站立</span></div>'}${isEmpty ? button('sample-avatar', '先用示例形象体验 ↗', 'text-action sample-action') : `<div class="status-line"><span class="${state.avatar === 'ready' ? 'success-label' : ''}">${state.avatar === 'ready' ? '形象已确认' : '人物照片已选好'}</span>${button('choose-avatar', '重新选择')}</div>`}<p class="upload-note">${state.personCustom ? '本地照片仅用于预览。后续试穿展示固定示例，不会把你的照片发送或用于合成。' : '人物形象属于你，与前面选择的陪伴助理不同。创建前会单独确认所需积分。'}</p>`;
  }
  function weather() {
    return `<div class="weather-row"><div><strong>${state.city ? '⌖ ' + state.city + ' · 示例城市' : '⌖ 暂不使用定位'}</strong><small>${state.city ? '示例天气 · 晴，18–23℃ · 仅供流程展示' : '依然可以试穿；本次不参考当地天气。'}</small></div>${button('location', state.city ? '更改' : '选城市')}</div>`;
  }
  function renderTryon() {
    if (state.outfit !== 'ready' || state.avatar !== 'ready') return `${weather()}<div class="missing-card"><p>试穿需要一套搭配，<br>和一张确认过的人物形象。</p>${state.outfit !== 'ready' ? button('goto-3', '先准备搭配') : ''}${state.avatar !== 'ready' ? button('goto-4', '先确认形象') : ''}</div><p class="upload-note">返回补充时，已经确认的内容会留在当前页。</p>`;
    if (state.result) return `<div class="result-card"><div class="result-image">${picture(assets.source, '内置固定试穿结果示意，非当前照片实时合成')}<span class="tag">固定示例 · 非实时合成</span></div><div class="result-copy"><h3>第一套喜欢，穿给自己看。</h3><p>浅蓝衬衫 × 牛仔裤，留一点轻松给今天。<br>真实试穿效果将在接口接入后生成。</p></div></div>${weather()}${button('review-materials', '回看搭配与形象', 'text-action')}`;
    return `${weather()}<div class="section-head"><h3>这套搭配，试在你的形象上</h3><span class="tag">组合示意</span></div><div class="materials"><div class="material-card">${picture(assets.outfit, '前一步组成的两件单品搭配')}<span>刚刚确认的搭配</span><small>浅蓝衬衫 + 牛仔裤</small></div><span class="material-plus" aria-hidden="true">+</span><div class="material-card">${picture(personImage(), '前一步确认的试穿人物照片')}<span>你的试穿形象</span><small>已在上一步确认</small></div></div><p class="upload-note">保留刚刚确认的搭配与人物。天气可以作穿着参考；是否合成试穿，由你确认。</p>`;
  }
  function render() {
    const progress = ['认识你','选助理','拆衣搭配','人物形象','合成试穿'];
    $('#dots').innerHTML = progress.map((label, i) => `<span class="${i + 1 === state.step ? 'active' : i + 1 < state.step ? 'past' : ''}" ${i + 1 === state.step ? 'aria-current="step"' : ''}><small>0${i + 1}</small><em>${label}</em></span>`).join('');
    $('#counter').textContent = `初识 · 0${state.step} / 05`;
    document.querySelectorAll('[data-step]').forEach(b => { if (Number(b.dataset.step) === state.step) b.setAttribute('aria-current','step'); else b.removeAttribute('aria-current'); b.disabled = state.busy; });
    const titles = {3:'把照片里的喜欢，留下来。',4:'让这套衣服，遇见你的模样。',5: state.result ? '第一套穿搭，从这里开始。' : '看看这一套，穿在你身上。'};
    const letters = {3:'选一张喜欢的穿搭照吧。我会把里面的衣服一件件整理出来，再陪你组成一套。',4:'搭配已经有了，再选一张你的人物照片。之后，就能试着看看穿在身上的样子。',5: state.result ? '从一张照片，到第一套穿搭。以后的每一种喜欢，我们都可以慢慢试。' : '先看看你所在城市的天气，再让刚刚选好的搭配，和你的形象一起出场。'};
    const descriptions = {3:'穿搭照片 → 确认单品 → 组成搭配',4:'选择人物照片 → 确认试穿形象',5:'选择城市 → 确认试穿 → 看看效果'};
    const busyCopy = state.step === 3 ? '演示：拆出照片里的单品' : state.step === 4 ? '演示：准备人物数字形象' : '演示：把搭配穿在形象上';
    screen.innerHTML = `<h2>${titles[state.step]}</h2><div class="closer-dialogue"><p>${letters[state.step]}</p></div><p class="description">${descriptions[state.step]}</p>${state.busy ? `<div class="busy" role="status"><span class="busy-mark" aria-hidden="true">✧</span><p>${busyCopy}</p><small>即将显示内置示例，不调用真实接口。</small></div>` : state.step === 3 ? renderOutfit() : state.step === 4 ? renderAvatar() : renderTryon()}`;
    screen.scrollTop = 0;
    $('#back').disabled = state.step === 3 || state.busy;
    $('#skip').textContent = state.step === 5 ? '先到这里' : '稍后体验';
    $('#skip').disabled = state.busy;
    let label;
    if (state.step === 3) label = {empty:'选择穿搭照片',source:'确认照片，拆出单品',items:'确认单品，组成搭配',ready:'继续，准备试穿形象'}[state.outfit];
    else if (state.step === 4) label = {empty:'上传人物照片',source:'确认这张人物形象',ready:'继续，试穿这一套'}[state.avatar];
    else label = state.result ? '开始爱搭衣橱的日常' : '合成我的第一套试穿';
    $('#next').textContent = state.busy ? '正在展示流程…' : label;
    $('#next').disabled = state.busy || (state.step === 3 && state.outfit === 'items' && !state.selected.every(Boolean)) || (state.step === 5 && (state.outfit !== 'ready' || state.avatar !== 'ready'));
  }
  function finish() { modal(`<p class="dialog-kicker">A LITTLE BEGINNING</p><div class="dialog-symbol" aria-hidden="true">✧</div><h2 id="dialog-title">接下来，慢慢穿出你的喜欢。</h2><p>这里衔接爱搭衣橱首页，继续看衣橱、聊穿搭或尝试下一套。</p><p class="dialog-hint">本次流程示意结束。没有保存账号资料、单品、人物或试穿结果。</p><div class="dialog-actions">${button('close-dialog','继续看看示意','primary')}${button('restart','从第3步重新体验','quiet')}</div>`); }
  $('#next').addEventListener('click', () => {
    if ($('#next').disabled) return;
    if (state.step === 3) {
      if (state.outfit === 'empty') $('#source-file').click();
      else if (state.outfit === 'source') feePrompt('extract');
      else if (state.outfit === 'items') { state.outfit = 'ready'; state.result = false; render(); }
      else navigate(4);
    } else if (state.step === 4) {
      if (state.avatar === 'empty') $('#avatar-file').click();
      else if (state.avatar === 'source') feePrompt('avatar');
      else navigate(5);
    } else if (state.result) finish();
    else feePrompt('tryon');
  });
  $('#back').addEventListener('click', () => { if (state.step > 3) navigate(state.step - 1); });
  $('#skip').addEventListener('click', () => state.step < 5 ? navigate(state.step + 1) : finish());
  document.querySelectorAll('[data-step]').forEach(b => b.addEventListener('click', () => navigate(Number(b.dataset.step))));
  document.querySelectorAll('button[data-color]').forEach(b => b.addEventListener('click', () => {
    document.body.dataset.color = b.dataset.color;
    document.querySelectorAll('button[data-color]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  }));
  document.addEventListener('click', event => {
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (!action || state.busy) return;
    if (action === 'sample-source') { state.source = assets.source; state.sourceCustom = false; resetOutfit(); render(); }
    else if (action === 'sample-avatar') { state.person = assets.avatar; state.personCustom = false; resetAvatar(); render(); }
    else if (action === 'choose-source') $('#source-file').click();
    else if (action === 'choose-avatar') $('#avatar-file').click();
    else if (action.startsWith('toggle-')) { const i = Number(action.slice(-1)); state.selected[i] = !state.selected[i]; render(); screen.querySelector(`[data-action="${action}"]`).focus({preventScroll:true}); }
    else if (action === 'edit-items') { state.outfit = 'items'; state.result = false; render(); }
    else if (action === 'location') locationPrompt();
    else if (action === 'locate') { state.city = '上海'; closeModal(); render(); announce('已选择示例城市上海，未读取实际位置。'); }
    else if (action === 'cities') cityPicker();
    else if (action.startsWith('city-')) { state.city = action.slice(5); closeModal(); render(); }
    else if (action === 'decline-location') { state.city = ''; closeModal(); render(); }
    else if (action === 'close-dialog') closeModal();
    else if (action.startsWith('goto-')) navigate(Number(action.slice(-1)));
    else if (action.startsWith('confirm-')) simulate(action.slice(8));
    else if (action === 'review-materials') { state.result = false; render(); }
    else if (action === 'restart') { closeModal(); for (const url of ownedUrls) URL.revokeObjectURL(url); ownedUrls.clear(); Object.assign(state,{step:3,outfit:'empty',avatar:'empty',source:null,person:null,sourceCustom:false,personCustom:false,selected:[true,true],city:'',locationAsked:false,result:false}); render(); }
  });
  function fileChanged(kind) {
    const input = $(kind === 'source' ? '#source-file' : '#avatar-file');
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    if (!['image/jpeg','image/png','image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) {
      modal(`<h2 id="dialog-title">换一张清楚的照片吧</h2><p>支持 JPG、PNG、WebP，每张不超过 10MB。</p><div class="dialog-actions">${button('close-dialog','知道了','primary')}</div>`); return;
    }
    const image = new Image();
    const url = URL.createObjectURL(file);
    ownedUrls.add(url);
    image.onload = () => {
      const old = state[kind === 'source' ? 'source' : 'person'];
      if (ownedUrls.has(old)) { URL.revokeObjectURL(old); ownedUrls.delete(old); }
      if (kind === 'source') { state.source = url; state.sourceCustom = true; resetOutfit(); }
      else { state.person = url; state.personCustom = true; resetAvatar(); }
      render();
    };
    image.onerror = () => { URL.revokeObjectURL(url); ownedUrls.delete(url); modal(`<h2 id="dialog-title">这张照片暂时无法预览</h2><p>请换一张有效图片，已确认的内容会保留。</p><div class="dialog-actions">${button('close-dialog','知道了','primary')}</div>`); };
    image.src = url;
  }
  $('#source-file').addEventListener('change', () => fileChanged('source'));
  $('#avatar-file').addEventListener('change', () => fileChanged('avatar'));
  window.addEventListener('pagehide', () => { if (pending) clearTimeout(pending); for (const url of ownedUrls) URL.revokeObjectURL(url); ownedUrls.clear(); });
  render();
})();
