'use strict';
(() => {
  const defaults = () => ({ user_name: '', user_gender: null, agent_name: '衣衣', assistant_persona: 'female_warm_v1' });
  const dialog = document.createElement('dialog');
  dialog.id = 'companion-dialog'; dialog.setAttribute('aria-labelledby', 'companion-title');
  dialog.innerHTML = `
    <form id="companion-form" novalidate>
      <header class="companion-top"><span class="companion-wordmark">A LITTLE CLOSER</span><button type="button" class="companion-close" aria-label="关闭称呼与形象设置">关闭 ×</button></header>
      <ol class="companion-progress" aria-label="设置进度"><li>认识你</li><li>更懂你</li><li>一个名字</li><li>陪伴的模样</li></ol>
      <div class="companion-body">
        <div class="companion-scene-mark" aria-hidden="true">✧</div>
        <p class="companion-chapter"></p><h2 id="companion-title"></h2>
        <div class="companion-dialogue"><span class="companion-speaker"></span><p class="companion-line" aria-live="polite"></p></div>
        <p class="companion-recall"></p>
        <div class="companion-field" data-step="0"><label for="companion-user-name">你喜欢的称呼</label><input id="companion-user-name" type="text" maxlength="24" autocomplete="nickname" placeholder="写下你喜欢的称呼" aria-describedby="companion-error"><button type="button" class="companion-soft-choice" id="companion-user-skip">先叫我“你”就好</button></div>
        <fieldset class="companion-gender" data-step="1"><legend class="sr-only">选择你的性别</legend><label><input type="radio" name="companion-user-gender" value="女"><span>女生<small>从你的喜好开始</small></span></label><label><input type="radio" name="companion-user-gender" value="男"><span>男生<small>找到自在的穿法</small></span></label><label><input type="radio" name="companion-user-gender" value=""><span>暂不设定<small>慢慢了解也很好</small></span></label><p>仅作为为你搭配时的默认参考，也可以先不选。</p></fieldset>
        <div class="companion-field" data-step="2"><label for="companion-agent-name">你想怎么叫我</label><input id="companion-agent-name" type="text" maxlength="24" autocomplete="off" placeholder="一个你喜欢的名字" aria-describedby="companion-error"><button type="button" class="companion-soft-choice" id="companion-agent-default">就叫“衣衣”吧</button></div>
        <fieldset class="companion-cast" data-step="3"><legend class="sr-only">选择女助理或男助理</legend>
          <label class="companion-person companion-person-female"><input type="radio" name="companion-persona" value="female_warm_v1"><img src="/static/assets/characters/yiyi-female-standing-v3.jpg" alt="女助理，棕色短卷发，米白衬衫与绿色马甲，正常比例上半身站立像" width="384" height="512"><span class="companion-portrait" data-portrait="female" aria-hidden="true"></span><span class="companion-person-copy"><strong>女助理</strong><span>温柔细腻 · 从容灵动</span><small>“你的喜欢，我会慢慢了解。”</small></span><span class="companion-selected" aria-hidden="true">✓</span></label>
          <label class="companion-person companion-person-male"><input type="radio" name="companion-persona" value="male_calm_v1"><img src="/static/assets/characters/yiyi-male-standing-v3.jpg" alt="男助理，棕色短卷发，米白衬衫与藏蓝开衫，正常比例上半身站立像" width="384" height="512"><span class="companion-portrait" data-portrait="male" aria-hidden="true"></span><span class="companion-person-copy"><strong>男助理</strong><span>沉稳细致 · 克制温暖</span><small>“不必着急，我们一起选。”</small></span><span class="companion-selected" aria-hidden="true">✓</span></label>
        </fieldset>
        <p id="companion-error" role="status"></p>
      </div>
      <footer class="companion-footer"><div class="companion-buttons"><button type="button" id="companion-back">上一步</button><button type="submit" id="companion-next" class="primary">继续认识彼此</button></div><p>称呼和模样，以后都可以在这里慢慢调整。</p></footer>
    </form>`;
  document.body.append(dialog);
  window.CompanionPortraits?.mount(dialog);
  const notification = document.createElement('aside');
  notification.id = 'companion-notification'; notification.hidden = true;
  notification.setAttribute('aria-label', '助理消息');
  notification.innerHTML = `<span class="mascot companion-sprite avatar-mini" aria-hidden="true"></span><div class="companion-notification-copy" role="status" aria-live="polite" aria-atomic="true"><strong></strong><p></p></div><button type="button" class="companion-notification-close" aria-label="关闭助理消息">×</button><button type="button" class="companion-message-open" aria-label="阅读完整消息" aria-haspopup="dialog" aria-controls="companion-message-dialog"></button>`;
  document.body.append(notification);
  const messageDialog = document.createElement('dialog');
  messageDialog.id = 'companion-message-dialog';
  messageDialog.setAttribute('aria-labelledby', 'companion-message-title');
  messageDialog.innerHTML = `<div class="companion-letter-top"><span>A MESSAGE FOR YOU</span><button type="button" class="companion-letter-close" aria-label="关闭来信">×</button></div><div class="companion-letter-heading"><span class="mascot companion-sprite avatar-mini" aria-hidden="true"></span><div><p>有一份心意，想让你知道</p><h2 id="companion-message-title"></h2></div><span class="companion-letter-star" aria-hidden="true">✧</span></div><div class="companion-letter-scroll" tabindex="0" aria-label="来信正文"><article class="companion-letter-paper"><p class="companion-letter-body"></p><p class="companion-letter-signature"></p></article></div><div class="companion-letter-footer"><span>把这一刻，留在日常里。</span><button type="button" class="companion-letter-done">读完啦</button></div>`;
  document.body.append(messageDialog);
  let notificationTimer = null, notificationExitTimer = null, notificationMessage = null, messageReturnFocus = null;
  function clearMessage() {
    if (messageDialog.open) messageDialog.close();
    messageDialog.querySelector('.companion-letter-body').textContent = '';
    messageDialog.querySelector('.companion-letter-signature').textContent = '';
    messageDialog.querySelector('h2').textContent = '';
  }
  function closeMessage() { clearMessage(); messageReturnFocus?.focus({ preventScroll: true }); messageReturnFocus = null; }
  messageDialog.querySelector('.companion-letter-close').onclick = closeMessage;
  messageDialog.querySelector('.companion-letter-done').onclick = closeMessage;
  messageDialog.addEventListener('cancel', event => { event.preventDefault(); closeMessage(); });
  function openMessage() {
    if (!notificationMessage || notification.hidden || notification.classList.contains('is-leaving')) return;
    const message = notificationMessage;
    messageReturnFocus = document.getElementById('settings-open') || document.getElementById('companion-open') || document.getElementById('preview-open') || document.getElementById('message');
    hideNotification();
    messageDialog.dataset.persona = message.persona;
    messageDialog.querySelector('h2').textContent = `${message.name}的来信`;
    messageDialog.querySelector('.companion-letter-body').textContent = message.body;
    messageDialog.querySelector('.companion-letter-signature').textContent = `— ${message.name}`;
    messageDialog.querySelector('.companion-letter-scroll').scrollTop = 0;
    messageDialog.showModal();
  }
  function pauseNotification() { clearTimeout(notificationTimer); notificationTimer = null; }
  function hideNotification() {
    pauseNotification();
    clearTimeout(notificationExitTimer); notificationExitTimer = null;
    notification.classList.remove('is-leaving');
    const focused = notification.contains(document.activeElement);
    notification.hidden = true;
    notification.querySelector('strong').textContent = '';
    notification.querySelector('p').textContent = ''; notificationMessage = null;
    if (focused) (document.getElementById('settings-open') || document.getElementById('companion-open'))?.focus({ preventScroll: true });
  }
  function dismissNotification() {
    pauseNotification();
    if (notification.hidden || notification.classList.contains('is-leaving')) return;
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { hideNotification(); return; }
    notification.classList.add('is-leaving');
    // Fallback if the browser drops animationend (e.g. the page is backgrounded).
    notificationExitTimer = setTimeout(hideNotification, 450);
  }
  notification.addEventListener('animationend', event => {
    if (event.target === notification && event.animationName === 'companion-message-out' && notification.classList.contains('is-leaving')) hideNotification();
  });
  function scheduleDismiss() {
    pauseNotification();
    if (!notification.hidden && !notification.classList.contains('is-leaving') && !notification.contains(document.activeElement) && !notification.matches(':hover')) notificationTimer = setTimeout(dismissNotification, 9000);
  }
  function showNotification(saved, body) {
    pauseNotification(); clearTimeout(notificationExitTimer); notificationExitTimer = null; notification.classList.remove('is-leaving');
    notification.dataset.persona = saved.assistant_persona;
    notification.hidden = false;
    notification.querySelector('strong').textContent = saved.agent_name;
    notification.querySelector('p').textContent = body ?? `${saved.user_name ? saved.user_name + '，' : ''}以后就叫我${saved.agent_name}吧。我们的日常，从这里开始。`;
    notificationMessage = { name: saved.agent_name, persona: saved.assistant_persona, body: notification.querySelector('p').textContent };
    notification.querySelector('.companion-message-open').setAttribute('aria-label', `阅读${saved.agent_name}的完整消息`);
    scheduleDismiss();
  }
  notification.querySelector('.companion-notification-close').onclick = event => { event.stopPropagation(); dismissNotification(); };
  notification.querySelector('.companion-message-open').onclick = openMessage;
  notification.addEventListener('click', event => { if (!event.target.closest('.companion-notification-close')) openMessage(); });
  notification.addEventListener('mouseenter', pauseNotification);
  notification.addEventListener('mouseleave', scheduleDismiss);
  notification.addEventListener('focusin', pauseNotification);
  notification.addEventListener('focusout', event => { if (!notification.contains(event.relatedTarget)) queueMicrotask(scheduleDismiss); });

  const $ = id => document.getElementById(id);
  let owner = null, profile = defaults(), draft = defaults(), step = 0, sequence = 0;
  let client = null, loaded = false, saving = false, ready = Promise.resolve();
  let appearanceSave = Promise.resolve(), previewOriginal = null;
  const previewAppearance = gender => window.dispatchEvent(new CustomEvent('stylist-appearance-preview', { detail: gender }));
  function restoreAppearance() {
    if (previewOriginal === null) return;
    const original = previewOriginal; previewOriginal = null; previewAppearance(original);
  }
  const notify = () => {
    document.querySelectorAll('[data-agent-name]').forEach(node => { node.textContent = profile.agent_name; node.title = profile.agent_name; });
    window.dispatchEvent(new CustomEvent('companion-profile-change', { detail: owner ? { ...profile } : null }));
  };
  const rememberStep = () => {
    if (step === 0) draft.user_name = $('companion-user-name').value.trim();
    if (step === 1) draft.user_gender = dialog.querySelector('[name=companion-user-gender]:checked')?.value || null;
    if (step === 2) draft.agent_name = $('companion-agent-name').value.trim();
    if (step === 3) draft.assistant_persona = dialog.querySelector('[name=companion-persona]:checked')?.value || 'female_warm_v1';
  };
  function render() {
    const name = draft.user_name || '你';
    const scenes = [
      ['初识 · 01 / 04', '在开始之前，想先认识你。', '我该怎样称呼你，才会让你觉得亲切？'],
      ['更懂你 · 02 / 04', '让每一份搭配，更贴近你。', `${name === '你' ? '' : name + '，'}再了解你一点，好让衣橱里的选择更合你的心意。`],
      ['一个名字 · 03 / 04', '也想把名字的选择，交给你。', '你愿意怎么叫我？衣衣也很好，你喜欢的另一个名字也很好。'],
      ['陪伴的模样 · 04 / 04', `选一位，和${draft.agent_name}一起开始。`, '同一个名字，两种相处的节奏。哪一种更合你的心意？'],
    ];
    const current = scenes[step]; dialog.dataset.step = String(step);
    dialog.querySelector('.companion-chapter').textContent = current[0];
    $('companion-title').textContent = current[1];
    dialog.querySelector('.companion-speaker').textContent = draft.agent_name || '衣衣';
    dialog.querySelector('.companion-line').textContent = current[2];
    dialog.querySelector('.companion-recall').textContent = step === 0 ? '从一个喜欢的称呼，开始我们的日常。' : `${draft.user_name ? '想被称作 ' + draft.user_name : '先自然地称呼你'}${step > 1 && draft.user_gender ? ' · ' + (draft.user_gender === '女' ? '女生' : '男生') : ''}`;
    dialog.querySelectorAll('[data-step]').forEach(node => { node.hidden = Number(node.dataset.step) !== step; });
    dialog.querySelectorAll('.companion-progress li').forEach((node, index) => {
      node.classList.toggle('complete', index < step);
      if (index === step) node.setAttribute('aria-current', 'step'); else node.removeAttribute('aria-current');
    });
    $('companion-user-name').value = draft.user_name;
    $('companion-agent-name').value = draft.agent_name;
    for (const input of dialog.querySelectorAll('[name=companion-user-gender]')) input.checked = input.value === (draft.user_gender || '');
    for (const input of dialog.querySelectorAll('[name=companion-persona]')) input.checked = input.value === draft.assistant_persona;
    $('companion-back').hidden = step === 0;
    $('companion-next').textContent = step === 3 ? '就这样，开始我们的日常' : ['继续认识彼此', '再靠近一点', '看看陪伴的模样'][step];
    $('companion-error').textContent = '';
    dialog.querySelector('.companion-body').scrollTop = 0;
    // Do not force the mobile keyboard open between dialogue steps.
    $('companion-title').tabIndex = -1; $('companion-title').focus({ preventScroll: true });
  }
  function openLoaded() {
    if (!owner || !loaded || saving || dialog.open) return;
    hideNotification(); messageReturnFocus = null; clearMessage();
    previewOriginal = document.documentElement.dataset.stylistGender === 'male' ? 'male' : 'female';
    draft = { ...profile, assistant_persona: document.documentElement.dataset.stylistGender === 'male' ? 'male_calm_v1' : 'female_warm_v1' }; step = 0;
    if (!dialog.open) dialog.showModal();
    render();
  }
  function setOwner(id, api, autoOpen = true) {
    hideNotification(); messageReturnFocus = null; clearMessage(); restoreAppearance();
    const current = ++sequence; owner = id == null ? null : String(id); client = api;
    loaded = false; profile = defaults(); draft = defaults(); saving = false;
    $('companion-next').disabled = false; $('companion-back').disabled = false;
    if (dialog.open) dialog.close(); notify();
    if (!owner) { ready = Promise.resolve(); return ready; }
    const expectedOwner = owner;
    ready = (async () => {
      try {
        const result = await api('/api/companion-profile');
        if (current !== sequence || owner !== expectedOwner) return;
        profile = result.profile ? { ...defaults(), ...result.profile } : defaults(); loaded = true; notify();
        if (!result.profile && autoOpen) openLoaded();
      } catch (err) {
        if (current === sequence) $('notice').textContent = err.message || '还没能读取称呼设置，稍后再试一下。';
      }
    })();
    return ready;
  }
  async function open() {
    await ready;
    if (!loaded && owner && client) await setOwner(owner, client, false);
    openLoaded();
  }
  $('companion-user-skip').onclick = () => { $('companion-user-name').value = ''; rememberStep(); step = 1; render(); };
  $('companion-agent-default').onclick = () => { $('companion-agent-name').value = '衣衣'; };
  $('companion-back').onclick = () => { if (!saving) { rememberStep(); step = Math.max(0, step - 1); render(); } };
  dialog.querySelector('.companion-cast').addEventListener('change', event => {
    if (saving || !dialog.open || event.target.name !== 'companion-persona') return;
    draft.assistant_persona = event.target.value;
    previewAppearance(draft.assistant_persona === 'male_calm_v1' ? 'male' : 'female');
  });
  dialog.querySelector('.companion-close').onclick = () => { if (!saving) { restoreAppearance(); dialog.close(); } };
  dialog.addEventListener('cancel', event => { if (saving) event.preventDefault(); else restoreAppearance(); });
  dialog.addEventListener('close', () => { if (!dialog.open) restoreAppearance(); });
  $('companion-form').onsubmit = async event => {
    event.preventDefault(); if (saving) return; rememberStep();
    const value = step === 0 ? draft.user_name : step === 2 ? draft.agent_name : '';
    if (/[\u0000-\u001f\u007f<>]/u.test(value) || [...value].length > 24 || (step === 2 && !value)) {
      $('companion-error').textContent = step === 2 && !value ? '给我留一个名字吧，衣衣也很好。' : '用24字以内的普通文字就好。'; return;
    }
    if (step < 3) { step++; render(); return; }
    const current = sequence, expectedOwner = owner, saved = { ...draft };
    saving = true; $('companion-next').disabled = true; $('companion-back').disabled = true;
    try {
      await appearanceSave;
      if (sequence !== current || owner !== expectedOwner) return;
      const result = await client('/api/companion-profile', { method: 'PUT', body: JSON.stringify(saved) });
      if (sequence !== current || owner !== expectedOwner) return;
      profile = result.profile; loaded = true; previewOriginal = null; notify(); dialog.close();
      showNotification(profile);
    } catch (err) { if (sequence === current) $('companion-error').textContent = err.message || '这次还没保存好，你写下的名字还在，再试一下就好。'; }
    finally { if (sequence === current) { saving = false; $('companion-next').disabled = false; $('companion-back').disabled = false; } }
  };
  window.addEventListener('stylist-appearance-selected', event => {
    if (!owner || !loaded || saving) return;
    profile = { ...profile, assistant_persona: event.detail === 'male' ? 'male_calm_v1' : 'female_warm_v1' };
    const current = sequence, expectedOwner = owner, saved = { ...profile }, api = client;
    appearanceSave = appearanceSave.catch(() => {}).then(async () => {
      if (current !== sequence || owner !== expectedOwner) return;
      try { await api('/api/companion-profile', { method: 'PUT', body: JSON.stringify(saved) }); }
      catch (err) { if (current === sequence) $('notice').textContent = err.message || '这次形象还没保存好，稍后再试一下。'; }
    });
  });
  function viewport() {
    dialog.style.setProperty('--companion-viewport', `${window.visualViewport?.height || window.innerHeight}px`);
    dialog.style.setProperty('--companion-viewport-top', `${window.visualViewport?.offsetTop || 0}px`);
    messageDialog.style.setProperty('--companion-viewport', `${window.visualViewport?.height || window.innerHeight}px`);
    messageDialog.style.setProperty('--companion-viewport-top', `${window.visualViewport?.offsetTop || 0}px`);
  }
  window.visualViewport?.addEventListener('resize', viewport); window.visualViewport?.addEventListener('scroll', viewport); window.addEventListener('resize', viewport); viewport();
  window.CompanionSettings = {
    notify: body => showNotification({ ...profile, assistant_persona: document.documentElement.dataset.stylistGender === 'male' ? 'male_calm_v1' : 'female_warm_v1' }, body),
    setOwner, open, get ready() { return ready; }, agentName: () => profile.agent_name,
    getProfile: () => owner && loaded ? { ...profile, assistant_persona: (previewOriginal ?? document.documentElement.dataset.stylistGender) === 'male' ? 'male_calm_v1' : 'female_warm_v1' } : null,
  };
})();
