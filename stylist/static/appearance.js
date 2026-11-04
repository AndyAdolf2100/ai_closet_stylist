'use strict';

// Appearance selects expression for new requests. Never use it as Task.gender.
(() => {
  const key = 'ai-closet-stylist-appearance-v1';
  const root = document.documentElement;
  const normalize = value => value === 'female' ? 'female' : 'male';
  const copy = {
    female: {
      eyebrow: 'A LITTLE CARE, EVERY DAY',
      title: '今天，穿得喜欢。',
      intro: '我是衣衣，你的日常搭配助理。\n从天气到衣橱，一起搭出舒服又像你的样子。',
      sidebar: '让已有的衣服，\n穿出喜欢的自己。',
      today: '今天，陪我挑一套',
      week: '把这周，慢慢安排好',
      wardrobe: '旧衣服，换个新心情',
      placeholder: '和衣衣说说今天的安排、喜欢的风格…',
      hero: '女版衣衣倚在窗边，托着脸微笑，轻轻眨眼',
    },
    male: {
      eyebrow: 'LESS EFFORT, MORE YOU',
      title: '今天，穿出你的节奏。',
      intro: '我是衣衣，你的日常搭配助理。\n少一点纠结，多一点从容。一起找到适合你的穿法。',
      sidebar: '穿得自在，\n也穿得有自己的样子。',
      today: '今天的穿搭，一起选',
      week: '这周剩下的，我来安排',
      wardrobe: '熟悉的衣服，试点新意',
      placeholder: '今天去哪儿？聊聊你的安排和想穿的感觉…',
      hero: '男版衣衣倚在窗边，托着脸放松地看向你，轻轻眨眼',
    },
  };

  let gender = 'male',colorScheme='companion';
  try { gender = normalize(localStorage.getItem(key)); } catch { /* Private mode can deny storage. */ }
  // This script runs in <head>, before CSS paints the saved appearance.
  root.dataset.stylistGender = gender;
  root.dataset.colorScheme = colorScheme;

  function apply(value, announce = false,scheme=colorScheme) {
    gender = normalize(value);
    root.dataset.stylistGender = gender;
    colorScheme=scheme==='system'?'system':'companion';root.dataset.colorScheme=colorScheme;
    const current = copy[gender];
    const agentName = window.CompanionSettings?.agentName() || '衣衣';
    const named = text => text.replaceAll('衣衣', agentName);
    document.querySelectorAll('[data-stylist-copy]').forEach(node => {
      const text = current[node.dataset.stylistCopy];
      if (text !== undefined) node.textContent = named(text);
    });
    document.querySelectorAll('button[data-stylist-gender]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.stylistGender === gender));
    });
    const input = document.getElementById('message');
    if (input) input.placeholder = named(current.placeholder);
    document.querySelectorAll('.hero-mascot').forEach(node => node.setAttribute('aria-label', `${agentName}，${root.dataset.companionCharacter || (gender === 'male' ? '男版助理' : '女版助理')}，安静守候并轻轻眨眼`));
    const status = document.getElementById('appearance-status');
    if (announce && status) status.textContent = `已切换为${gender === 'male' ? '男' : '女'}版${agentName}，后续新请求使用对应回复风格`;
  }

  document.addEventListener('DOMContentLoaded', () => {
    apply(gender);
    document.querySelectorAll('button[data-stylist-gender]').forEach(button => {
      button.addEventListener('click', () => {
        apply(button.dataset.stylistGender, true);
        try { localStorage.setItem(key, gender); } catch { /* Switching still works without persistence. */ }
        window.dispatchEvent(new CustomEvent('stylist-appearance-selected', { detail: gender }));
      });
    });
  }, { once: true });

  // Draft previews update visuals without saving preferences or profile data.
  window.addEventListener('stylist-appearance-preview', event => apply(typeof event.detail==='string'?event.detail:event.detail?.gender,false,typeof event.detail==='object'?event.detail?.color_scheme:colorScheme));

  window.addEventListener('companion-profile-change', event => apply(event.detail?.assistant_persona?.startsWith('female_') ? 'female' : 'male',false,event.detail?.color_scheme==='system'?'system':'companion'));

  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) apply(event.key === null ? 'male' : event.newValue);
  });
})();
