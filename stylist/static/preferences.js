/* Optional, account-owned preferences; persisted only through CompanionSettings. */
(() => {
  'use strict';
  const zodiac = ['白羊座','金牛座','双子座','巨蟹座','狮子座','处女座','天秤座','天蝎座','射手座','摩羯座','水瓶座','双鱼座'];
  const ranges = ['3.21–4.19','4.20–5.20','5.21–6.21','6.22–7.22','7.23–8.22','8.23–9.22','9.23–10.23','10.24–11.22','11.23–12.21','12.22–1.19','1.20–2.18','2.19–3.20'];
  const groups = {
    mbti: ['INFJ', 'INFP', 'INTJ', 'INTP', 'ISFJ', 'ISFP', 'ISTJ', 'ISTP', 'ENFJ', 'ENFP', 'ENTJ', 'ENTP', 'ESFJ', 'ESFP', 'ESTJ', 'ESTP'],
    conversation_style: ['自然相处','温柔鼓励','直接坦诚','轻松幽默'],
    reply_detail: ['适中','简洁重点','细致解释'],
    style_preferences: ['简约','休闲','通勤','温柔','复古','运动','街头','优雅'],
    dressing_priorities: ['舒适自在','方便走动','容易打理','已有衣物优先','尝试新风格']
  };
  // Concise Chinese paraphrases of the Foundation's descriptions; not official translations.
  const mbtiSummaries = {
    "INFJ": "关注意义与联系，以坚定价值观和清晰愿景服务共同利益。",
    "INFP": "重视理想与价值一致性，探索可能，并帮助他人成长。",
    "INTJ": "善于发现模式、形成长期构想，独立地推动目标实现。",
    "INTP": "寻求逻辑解释，喜欢抽象思考，深入分析感兴趣的问题。",
    "ISFJ": "认真履行责任，留意他人细节，营造有序和谐的环境。",
    "ISFP": "珍惜当下与个人空间，忠于价值，不强加自己的看法。",
    "ISTJ": "务实可靠，依逻辑稳步做事，重视秩序、传统与忠诚。",
    "ISTP": "灵活观察，分析实际问题的成因，迅速寻找有效解法。",
    "ENFJ": "关注他人的需要与潜能，促进群体成长，带动大家行动。",
    "ENFP": "热情而富于想象，联结不同信息，灵活探索新的可能。",
    "ENTJ": "果断组织行动，识别低效环节，善于长期规划和建系统。",
    "ENTP": "善于构想新可能并策略分析，喜欢挑战，不拘泥于惯例。",
    "ESFJ": "热心合作，关注日常需要，认真完成任务并维护和谐。",
    "ESFP": "友好外向，享受与人合作，在亲身尝试中灵活学习。",
    "ESTJ": "务实果断，组织人与项目，以清晰标准高效落实计划。",
    "ESTP": "关注眼前实际结果，灵活行动，通过亲身实践学习。"
};
  const mbtiTitles = Object.fromEntries(groups.mbti.map(type => [type, type + ' 型人格']));
  const mbtiDimensions = {
    I:['内向','能量与注意更多朝向内在世界'], E:['外向','能量与注意更多朝向外部世界'],
    S:['实感','关注具体事实和已有经验'], N:['直觉','关注联系、意义和新的可能'],
    T:['思考','作决定时侧重逻辑与一致性'], F:['情感','作决定时侧重价值与对人的影响'],
    J:['判断','倾向安排和确定下一步'], P:['知觉','倾向保持开放并灵活调整']
  };
  const dialog = document.createElement('dialog'); dialog.id = 'preferences-dialog'; dialog.setAttribute('aria-labelledby','preferences-title');
  dialog.innerHTML = `<form id="preferences-form">
  <div class="preferences-heading"><div><div class="eyebrow">THE LITTLE THINGS ABOUT YOU</div><h2 id="preferences-title">把你的喜欢，慢慢说给我听</h2></div><button type="button" id="preferences-close" class="subtle" aria-label="关闭了解我">×</button></div>
  <div class="preferences-letter"><span class="mascot companion-sprite avatar-mini" data-mood="greeting" aria-hidden="true"></span><div><span id="preferences-speaker"></span><p id="preferences-letter-copy"></p></div><span class="preferences-letter-star" aria-hidden="true">✧</span></div>
  <div class="preferences-tabs" role="tablist" aria-label="了解我的篇章"><button type="button" id="preference-tab-stars" role="tab" aria-controls="preference-page-stars" data-chapter="stars"><small>01</small> 你的星光</button><button type="button" id="preference-tab-talk" role="tab" aria-controls="preference-page-talk" data-chapter="talk"><small>02</small> 相处的节奏</button><button type="button" id="preference-tab-style" role="tab" aria-controls="preference-page-style" data-chapter="style"><small>03</small> 心动的穿搭</button></div>
  <div class="preferences-scroll">
    <section id="preference-page-stars" role="tabpanel" aria-labelledby="preference-tab-stars" tabindex="0"><div class="preferences-page-heading"><span>选一座属于你的星宫</span><button type="button" id="zodiac-clear" class="preference-chip">暂不选择</button></div><div class="zodiac-grid"></div></section>
    <section id="preference-page-talk" role="tabpanel" aria-labelledby="preference-tab-talk" tabindex="0" hidden><fieldset class="mbti-field"><legend>十六种认识自己的方式 <small>MBTI · 可选</small></legend><div data-preference-group="mbti" aria-label="选择 MBTI 类型"></div><article id="mbti-detail" class="mbti-detail" aria-labelledby="mbti-detail-title"><div class="mbti-illustration" aria-hidden="true"><span class="mbti-companion-art" hidden></span></div><div class="mbti-detail-copy" aria-live="polite" aria-atomic="true"><h3 id="mbti-detail-title">你比四个字母更丰富</h3><p id="mbti-detail-summary">选一个熟悉的类型，让我们从这里开始。</p></div><dl id="mbti-dimensions"></dl></article><div class="mbti-actions"><button type="button" id="mbti-clear" class="subtle">暂不选择</button><span id="mbti-draft-note">保存后才会更新资料</span></div></fieldset><fieldset><legend>怎样说话，会让你更自在？</legend><div data-preference-group="conversation_style"></div></fieldset><fieldset><legend>你喜欢怎样的回复节奏？</legend><div data-preference-group="reply_detail"></div></fieldset></section>
    <section id="preference-page-style" role="tabpanel" aria-labelledby="preference-tab-style" tabindex="0" hidden><fieldset><legend>哪些风格，会让你多看一眼？ <small>最多 3 项</small></legend><div data-preference-group="style_preferences"></div></fieldset><fieldset><legend>穿在身上，你更在意什么？ <small>最多 3 项</small></legend><div data-preference-group="dressing_priorities"></div></fieldset></section>
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
  function renderMbti() {
    const type = draft.mbti, known = Object.hasOwn(mbtiTitles, type);
    $('mbti-detail-title').textContent = known ? mbtiTitles[type] : '你比四个字母更丰富';
    $('mbti-detail-summary').textContent = known
      ? mbtiSummaries[type]
      : '选一个熟悉的类型，让我们从这里开始。不确定也没关系，可以暂时留白。';
    const art = dialog.querySelector('.mbti-companion-art');
    art.hidden = false;
    art.classList.toggle('mbti-default-art', !known);
    art.dataset.mbti = known ? type : '';
    const index = groups.mbti.indexOf(type);
    art.style.backgroundPosition = known ? (index % 4 * 100 / 3) + '% ' + (Math.floor(index / 4) * 100 / 3) + '%' : '';
    $('mbti-dimensions').replaceChildren();
    if (known) for (const letter of type) {
      const row = document.createElement('div'), term = document.createElement('dt'), description = document.createElement('dd');
      term.textContent = letter + ' · ' + mbtiDimensions[letter][0];
      description.textContent = mbtiDimensions[letter][1];
      row.append(term, description); $('mbti-dimensions').append(row);
    }
    $('mbti-clear').setAttribute('aria-pressed', String(!known));
    $('mbti-draft-note').textContent = known ? type + ' 已选 · 保存后生效' : '可留白 · 保存后生效';
  }
  function render() {
    renderMbti();
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
    if (key === 'style_preferences' || key === 'dressing_priorities') {
      const index = values.indexOf(value) + (key === 'dressing_priorities' ? 8 : 0);
      const art = document.createElement('span'); art.className = 'style-sprite'; art.setAttribute('aria-hidden','true');
      art.style.backgroundPosition = (index % 4 * 100 / 3) + '% ' + (Math.floor(index / 4) * 100 / 3) + '%';
      button.classList.add('has-style-art'); button.append(art);
    }
    const label = document.createElement('strong'); label.textContent = value; button.append(label);
    if (key === 'mbti') { const title = document.createElement('small'); title.textContent = [...value].map(letter => mbtiDimensions[letter][0]).join(' · '); button.append(title); button.setAttribute('aria-controls', 'mbti-detail'); }
    if (descriptions[value]) { const sub = document.createElement('small'); sub.textContent = descriptions[value]; button.append(sub); }
    button.onclick = () => {
      if (saving) return;

      if (Array.isArray(draft[key])) {
        if (draft[key].includes(value)) draft[key] = draft[key].filter(x => x !== value);
        else if (draft[key].length < 3) draft[key].push(value);
        else { window.CompanionSettings.notify('这组最多选 3 项，可以先取消一项。'); return; }
      } else draft[key] = key === 'mbti' && draft[key] === value ? null : value;
      render();
    };
    dialog.querySelector(`[data-preference-group="${key}"]`).append(button);
  }
  const defaults = () => ({mbti:null,zodiac:null,conversation_style:'自然相处',reply_detail:'适中',style_preferences:[],dressing_priorities:[]});
  function close() { if (saving) return; dialog.close(); $('settings-open')?.focus(); }
  $('preferences-close').onclick = close;
  dialog.addEventListener('cancel',event => { event.preventDefault(); close(); });
  $('mbti-clear').onclick = () => { if (!saving) { draft.mbti = null; render(); } };
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
