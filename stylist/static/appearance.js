'use strict';

// Appearance selects expression for new requests. Never use it as Task.gender.
(() => {
  const key = 'ai-closet-stylist-appearance-v1';
  const root = document.documentElement;
  const normalize = value => value === 'male' ? 'male' : 'female';
  const copy = {
    female: {
      eyebrow: 'A LITTLE CARE, EVERY DAY',
      title: '今天，穿得喜欢。',
      intro: '我是衣衣，你的日常搭配小伙伴。\n从天气到衣橱，一起搭出舒服又像你的样子。',
      sidebar: '让已有的衣服，\n穿出喜欢的自己。',
      today: '今天穿什么 · 早晚都照顾',
      week: '本周穿搭 · 跟着天气安排',
      wardrobe: '旧衣服，也有新感觉',
      placeholder: '和衣衣说说今天的安排、喜欢的风格…',
      hero: '女版衣衣倚在窗边，托着脸微笑，轻轻眨眼',
    },
    male: {
      eyebrow: 'LESS EFFORT, MORE YOU',
      title: '今天，穿出你的节奏。',
      intro: '我是衣衣，你的日常搭配伙伴。\n少一点纠结，多一点从容。一起找到适合你的穿法。',
      sidebar: '穿得自在，\n也穿得有自己的样子。',
      today: '今日出门 · 穿得刚刚好',
      week: '一周搭配 · 提前有个底',
      wardrobe: '衣橱焕新 · 试试新组合',
      placeholder: '今天去哪儿？聊聊你的安排和想穿的感觉…',
      hero: '男版衣衣倚在窗边，托着脸放松地看向你，轻轻眨眼',
    },
  };

  let gender = 'female';
  try { gender = normalize(localStorage.getItem(key)); } catch { /* Private mode can deny storage. */ }
  // This script runs in <head>, before CSS paints the saved appearance.
  root.dataset.stylistGender = gender;

  function apply(value, announce = false) {
    gender = normalize(value);
    root.dataset.stylistGender = gender;
    const current = copy[gender];
    document.querySelectorAll('[data-stylist-copy]').forEach(node => {
      const text = current[node.dataset.stylistCopy];
      if (text !== undefined) node.textContent = text;
    });
    document.querySelectorAll('button[data-stylist-gender]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.stylistGender === gender));
    });
    const input = document.getElementById('message');
    if (input) input.placeholder = current.placeholder;
    document.querySelectorAll('.hero-mascot').forEach(node => node.setAttribute('aria-label', current.hero));
    const status = document.getElementById('appearance-status');
    if (announce && status) status.textContent = `已切换为${gender === 'male' ? '男' : '女'}版衣衣，后续新请求使用对应回复风格`;
  }

  document.addEventListener('DOMContentLoaded', () => {
    apply(gender);
    document.querySelectorAll('button[data-stylist-gender]').forEach(button => {
      button.addEventListener('click', () => {
        apply(button.dataset.stylistGender, true);
        try { localStorage.setItem(key, gender); } catch { /* Switching still works without persistence. */ }
      });
    });
  }, { once: true });

  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) apply(event.key === null ? 'female' : event.newValue);
  });
})();
