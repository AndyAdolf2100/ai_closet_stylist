/* Optional, account-owned preferences; persisted only through CompanionSettings. */
(() => {
  'use strict';
  const zodiac = ['白羊座','金牛座','双子座','巨蟹座','狮子座','处女座','天秤座','天蝎座','射手座','摩羯座','水瓶座','双鱼座'];
  const ranges = ['3.21–4.19','4.20–5.20','5.21–6.21','6.22–7.22','7.23–8.22','8.23–9.22','9.23–10.23','10.24–11.22','11.23–12.21','12.22–1.19','1.20–2.18','2.19–3.20'];
  const groups = {
    conversation_style: ['自然相处','温柔鼓励','直接坦诚','轻松幽默'],
    reply_detail: ['适中','简洁重点','细致解释'],
    style_preferences: ['简约','休闲','通勤','温柔','复古','运动','街头','优雅'],
    dressing_priorities: ['舒适自在','方便走动','容易打理','已有衣物优先','尝试新风格']
  };
  const dialog = document.createElement('dialog'); dialog.id = 'preferences-dialog'; dialog.setAttribute('aria-labelledby','preferences-title');
  dialog.innerHTML = `<form id="preferences-form">
  <div class="preferences-heading"><div><div class="eyebrow">THE LITTLE THINGS ABOUT YOU</div><h2 id="preferences-title">把你的喜欢，慢慢说给我听</h2></div><button type="button" id="preferences-close" class="subtle" aria-label="关闭了解我">×</button></div>
  <div class="preferences-letter"><span class="mascot companion-sprite avatar-mini" data-mood="greeting" aria-hidden="true"></span><div><span id="preferences-speaker"></span><p id="preferences-letter-copy"></p></div><span class="preferences-letter-star" aria-hidden="true">✧</span></div>
  <div class="preferences-tabs" role="tablist" aria-label="了解我的篇章"><button type="button" id="preference-tab-stars" role="tab" aria-controls="preference-page-stars" data-chapter="stars"><small>01</small> 你的星光</button><button type="button" id="preference-tab-talk" role="tab" aria-controls="preference-page-talk" data-chapter="talk"><small>02</small> 相处的节奏</button><button type="button" id="preference-tab-style" role="tab" aria-controls="preference-page-style" data-chapter="style"><small>03</small> 心动的穿搭</button></div>
  <div class="preferences-scroll">
    <section id="preference-page-stars" role="tabpanel" aria-labelledby="preference-tab-stars" tabindex="0"><div class="preferences-page-heading"><span>选一座属于你的星宫</span><button type="button" id="zodiac-clear" class="preference-chip">暂不选择</button></div><div class="zodiac-grid"></div><p class="preferences-hint preferences-star-note">星座是一点聊天的灵感，不是定义你的标签。<br>日期仅作参考，交界日期以你的选择为准。</p></section>
    <section id="preference-page-talk" role="tabpanel" aria-labelledby="preference-tab-talk" tabindex="0" hidden><fieldset><legend>怎样说话，会让你更自在？</legend><div data-preference-group="conversation_style"></div></fieldset><fieldset><legend>你喜欢怎样的回复节奏？</legend><div data-preference-group="reply_detail"></div></fieldset></section>
    <section id="preference-page-style" role="tabpanel" aria-labelledby="preference-tab-style" tabindex="0" hidden><fieldset><legend>哪些风格，会让你多看一眼？ <small>最多 3 项</small></legend><div data-preference-group="style_preferences"></div></fieldset><fieldset><legend>穿在身上，你更在意什么？ <small>最多 3 项</small></legend><div data-preference-group="dressing_priorities"></div></fieldset><p class="preferences-hint">这些只是日常的参考。今天想尝试别的，直接告诉我就好。</p></section>
  </div>
  <div class="preferences-footer"><button type="button" id="preferences-reset" class="subtle">重新选一选</button><span class="preferences-save-note">随时都可以改变心意</span><button type="submit" id="preferences-save" class="primary">把喜欢交给我 <span aria-hidden="true">↗</span></button></div></form>`;
  document.body.append(dialog);
  const $ = id => document.getElementById(id);
  let draft, saving = false, generation = 0;
  const chapterCopy = {
    stars: '不急着了解全部的你。就从一小片星光，开始吧。',
    talk: '有时想被温柔回应，有时只想听一句直接的建议。你喜欢的节奏，我会记着。',
    style: '让你心动的样子，和穿着自在的感觉，我都想照顾到。'
  };
  // All chapter copy shares one grid cell; invisible copies reserve the longest
  // height at the current width/font size without clipping enlarged text.
  const letterCopy = $('preferences-letter-copy');
  const copySlot = document.createElement('div'); copySlot.className = 'preferences-letter-copy-slot';
  letterCopy.replaceWith(copySlot); copySlot.append(letterCopy);
  for (const text of Object.values(chapterCopy)) {
    const measure = document.createElement('p'); measure.className = 'preferences-letter-measure';
    measure.textContent = text; measure.setAttribute('aria-hidden', 'true'); copySlot.append(measure);
  }
  function chapter(name, focus = false) {
    dialog.querySelectorAll('[data-chapter]').forEach(button => {
      const active = button.dataset.chapter === name;
      button.setAttribute('aria-selected', String(active)); button.tabIndex = active ? 0 : -1;
      $(button.getAttribute('aria-controls')).hidden = !active;
      if (active && focus) { button.focus({ preventScroll: true }); button.scrollIntoView?.({ block: 'nearest', inline: 'nearest' }); }
    });
    $('preferences-speaker').textContent = window.CompanionSettings.agentName();
    $('preferences-letter-copy').textContent = chapterCopy[name];
    dialog.querySelector('.preferences-scroll').scrollTop = 0;
  }
  for (const button of dialog.querySelectorAll('[data-chapter]')) {
    button.onclick = () => chapter(button.dataset.chapter);
    button.onkeydown = event => {
      const keys = ['ArrowLeft','ArrowRight','Home','End']; if (!keys.includes(event.key)) return;
      event.preventDefault(); const names = Object.keys(chapterCopy), i = names.indexOf(button.dataset.chapter);
      chapter(names[event.key === 'Home' ? 0 : event.key === 'End' ? 2 : (i + (event.key === 'ArrowRight' ? 1 : 2)) % 3], true);
    };
  }
  const descriptions = {
    '自然相处': '像平常一样，舒服就好', '温柔鼓励': '先接住心情，再一起想办法',
    '直接坦诚': '不用绕弯，告诉我你的建议', '轻松幽默': '认真聊，也可以轻松一点',
    '适中': '刚刚好的解释', '简洁重点': '给我几个好用的重点', '细致解释': '也想听听背后的理由'
  };
  function render() {
    dialog.querySelectorAll('[data-zodiac]').forEach(button => button.setAttribute('aria-pressed',String(draft.zodiac === button.dataset.zodiac)));
    $('zodiac-clear').setAttribute('aria-pressed',String(!draft.zodiac));
    for (const [key] of Object.entries(groups)) dialog.querySelectorAll(`[data-preference-group="${key}"] button`).forEach(button => {
      const value = draft[key]; button.setAttribute('aria-pressed',String(Array.isArray(value) ? value.includes(button.dataset.value) : value === button.dataset.value));
    });
  }
  for (const [i,name] of zodiac.entries()) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'zodiac-card'; button.dataset.zodiac = name;
    const art = document.createElement('span'); art.className = 'zodiac-art'; art.style.backgroundPosition = `${i % 4 * 100 / 3}% ${Math.floor(i / 4) * 50}%`; art.setAttribute('aria-hidden','true');
    const title = document.createElement('strong'); title.textContent = name;
    const date = document.createElement('small'); date.textContent = ranges[i];
    button.append(art,title,date); button.onclick = () => { if (!saving) { draft.zodiac = draft.zodiac === name ? null : name; render(); } };
    dialog.querySelector('.zodiac-grid').append(button);
  }
  for (const [key,values] of Object.entries(groups)) for (const value of values) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'preference-chip'; button.dataset.value = value;
    const label = document.createElement('strong'); label.textContent = value; button.append(label);
    if (descriptions[value]) { const sub = document.createElement('small'); sub.textContent = descriptions[value]; button.append(sub); }
    button.onclick = () => {
      if (saving) return;

      if (Array.isArray(draft[key])) {
        if (draft[key].includes(value)) draft[key] = draft[key].filter(x => x !== value);
        else if (draft[key].length < 3) draft[key].push(value);
        else { window.CompanionSettings.notify('这组最多选 3 项，可以先取消一项。'); return; }
      } else draft[key] = value;
      render();
    };
    dialog.querySelector(`[data-preference-group="${key}"]`).append(button);
  }
  const defaults = () => ({zodiac:null,conversation_style:'自然相处',reply_detail:'适中',style_preferences:[],dressing_priorities:[]});
  function close() { if (saving) return; dialog.close(); $('settings-open')?.focus(); }
  $('preferences-close').onclick = close;
  dialog.addEventListener('cancel',event => { event.preventDefault(); close(); });
  $('zodiac-clear').onclick = () => { if (!saving) { draft.zodiac = null; render(); } };
  $('preferences-reset').onclick = () => { if (!saving) { draft = defaults();  render(); } };
  $('preferences-form').onsubmit = async event => {
    event.preventDefault(); if (saving) return;
    const current = generation; saving = true; $('preferences-save').disabled = true;
    try {
      if (await window.CompanionSettings.savePreferences(draft)) { dialog.close(); $('settings-open')?.focus(); }
    } catch (error) { if (current === generation) window.CompanionSettings.notify(error.message || '还没保存好，你的选择仍在，可以再试一次。'); }
    finally { if (current === generation) { saving = false; $('preferences-save').disabled = false; } }
  };
  window.addEventListener('companion-profile-change', () => {
    generation++; saving = false; $('preferences-save').disabled = false;
    if (dialog.open) dialog.close(); draft = defaults();
  });
  window.PersonalPreferences = { async open() {
    const current = generation;
    await window.CompanionSettings.ready;
    if (current !== generation) return;
    const profile = window.CompanionSettings.getProfile(); if (!profile) return;
    draft = {...defaults(),...profile,style_preferences:[...(profile.style_preferences || [])],dressing_priorities:[...(profile.dressing_priorities || [])]};
     render(); chapter('stars'); dialog.showModal();
  } };
  function viewport() {
    dialog.style.setProperty('--preferences-height',`${window.visualViewport?.height || window.innerHeight}px`);
    dialog.style.setProperty('--preferences-top',`${window.visualViewport?.offsetTop || 0}px`);
  }
  window.visualViewport?.addEventListener('resize',viewport); window.visualViewport?.addEventListener('scroll',viewport); window.addEventListener('resize',viewport); viewport();
})();
