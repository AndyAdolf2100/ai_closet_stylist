/* Experience-only check-in: memory state, no storage or reward API writes. */
(function (root) {
  'use strict';
  const dayKey = (now = new Date()) => new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit'
  }).format(now);
  function createStore(clock = () => new Date()) {
    const accounts = new Map();
    let owner = null;
    const account = () => accounts.get(owner);
    return {
      setOwner(value) { owner = value == null ? null : String(value); if (owner !== null && !accounts.has(owner)) accounts.set(owner, { chats: new Set(), days: new Set() }); },
      snapshot() {
        const today = dayKey(clock()), state = account();
        return { today, owner, eligible: !!state?.chats.has(today), signed: !!state?.days.has(today), days: [...(state?.days || [])].sort(), points: (state?.days.size || 0) * 10, reward: 10 };
      },
      completeChat(expectedOwner) {
        if (owner === null || String(expectedOwner) !== owner) return false;
        account().chats.add(dayKey(clock())); return true;
      },
      claim() {
        const state = this.snapshot();
        if (!state.owner || !state.eligible || state.signed) return false;
        account().days.add(state.today); return true;
      }
    };
  }
  function mount({ onChat, onLogin }) {
    const store = createStore(), $ = id => document.getElementById(id);
    const dialog = $('checkin-dialog');
    let month = '', feedback = '';
    const node = (tag, text, cls = '') => { const n = document.createElement(tag); n.textContent = text; n.className = cls; return n; };
    function render() {
      const state = store.snapshot();
      if (!month) month = state.today.slice(0, 7);
      $('checkin-entry-label').textContent = state.signed ? '今日已签到' : state.eligible ? '领取今日积分' : '对话签到';
      $('checkin-entry-meta').textContent = state.signed ? '明天继续见面' : '+10 体验积分';
      $('checkin-total').textContent = state.points;
      $('checkin-days').textContent = state.days.length;
      $('checkin-agent').textContent = root.CompanionSettings?.agentName() || '衣衣';
      $('checkin-state').textContent = state.signed ? '今天的陪伴，已经记下了' : state.eligible ? '聊过天了，收下今天的小奖励吧' : '聊聊今天，为自己攒一点小欢喜';
      $('checkin-task').textContent = state.eligible ? '✓ 今日已完成一轮对话' : '每日完成一轮对话，即可签到领取';
      const action = $('checkin-action');
      action.disabled = state.signed;
      action.textContent = !state.owner ? '登录后，和我聊聊' : state.signed ? '今日已领取 · 明天再来' : state.eligible ? '签到领取 +10 体验积分' : '去聊聊，解锁今日奖励';
      $('checkin-feedback').textContent = feedback;
      const [year, m] = month.split('-').map(Number);
      $('checkin-month').textContent = `${year}年 ${m}月`;
      const grid = $('checkin-calendar'); grid.replaceChildren();
      const offset = (new Date(Date.UTC(year, m - 1, 1)).getUTCDay() + 6) % 7;
      for (let i = 0; i < offset; i++) { const blank = node('span', ''); blank.setAttribute('aria-hidden', 'true'); grid.append(blank); }
      for (let day = 1; day <= new Date(Date.UTC(year, m, 0)).getUTCDate(); day++) {
        const date = `${month}-${String(day).padStart(2, '0')}`, signed = state.days.includes(date), today = date === state.today;
        const tile = node('div', '', 'checkin-date' + (signed ? ' is-signed' : '') + (today ? ' is-today' : ''));
        tile.append(node('span', day), node('small', signed ? '✓' : today ? '今天' : '·'));
        tile.setAttribute('aria-label', `${date}${today ? ' 今天' : ''}，${signed ? '已签到' : date > state.today ? '未到日期' : '未签到'}`);
        if (today) tile.setAttribute('aria-current', 'date');
        grid.append(tile);
      }
    }
    $('checkin-open').onclick = () => { month = store.snapshot().today.slice(0, 7); feedback = ''; render(); dialog.showModal(); };
    $('checkin-close').onclick = () => dialog.close();
    for (const [id, delta] of [['checkin-prev', -1], ['checkin-next', 1]]) $(id).onclick = () => {
      const [year, m] = month.split('-').map(Number), date = new Date(Date.UTC(year, m - 1 + delta, 1));
      month = date.toISOString().slice(0, 7); render();
    };
    $('checkin-action').onclick = () => {
      const state = store.snapshot();
      if (!state.owner) { dialog.close(); onLogin(); return; }
      if (!state.eligible) { dialog.close(); onChat(); return; }
      if (store.claim()) feedback = '签到成功，+10 体验积分已收下。明天也一起聊聊吧。';
      render();
    };
    new MutationObserver(() => render()).observe(document.documentElement, { attributes: true, attributeFilter: ['data-stylist-gender'] });
    document.addEventListener('visibilitychange', () => { if (!document.hidden) render(); });
    // Re-evaluate Shanghai midnight even if the panel stays open overnight.
    setInterval(render, 30000);
    render();
    return {
      setOwner(owner) { store.setOwner(owner); feedback = ''; month = ''; if (dialog.open) dialog.close(); render(); },
      completeChat(owner) { if (store.completeChat(owner)) render(); }
    };
  }
  root.DailyCheckin = { createStore, dayKey, mount };
  if (typeof module !== 'undefined') module.exports = { createStore, dayKey };
})(typeof window === 'undefined' ? globalThis : window);
