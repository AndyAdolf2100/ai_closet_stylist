/* Account-owned notebook. Drafts stay in memory; only Save writes to the server. */
(() => {
  'use strict';
  const dialog = document.createElement('dialog');
  dialog.id = 'memory-dialog'; dialog.setAttribute('aria-labelledby', 'memory-title');
  dialog.innerHTML = `<form id="memory-form" novalidate>
    <header class="memory-heading"><div><span class="eyebrow">THE THINGS WE KEEP</span><h2 id="memory-title">我们的手记</h2><p>把值得记住的小事，留在这里。</p></div><button type="button" id="memory-close" class="subtle" aria-label="关闭手记">×</button></header>
    <div class="memory-letter"><span class="mascot companion-sprite avatar-mini" data-mood="greeting" aria-hidden="true"></span><div><strong id="memory-speaker"></strong><p>你的喜欢，不必每次从头说起。<br>想留下什么、翻过哪一页，都由你决定。</p></div><span aria-hidden="true">✧</span></div>
    <div class="memory-controls"><label><input type="checkbox" id="memory-enabled"> 聊天时参考这本手记</label><span id="memory-count" aria-live="polite"></span></div>
    <div class="memory-scroll">
      <div id="memory-loading" role="status">正在翻开手记…</div>
      <div id="memory-empty" hidden><span aria-hidden="true">✧</span><h3>第一张纸页，还留着空白</h3><p>可以写下「我不穿高跟鞋」，<br>或「给建议前，先听我说完」。</p></div>
      <div id="memory-list"></div>
      <button type="button" id="memory-add">＋ 留下一件小事</button>
      <div id="memory-conflict" hidden><p>另一处的手记已有更新。当前草稿仍在，可以先复制需要保留的内容。</p><button type="button" id="memory-reload" class="subtle">放弃草稿，重新读取</button></div>
      <button type="button" id="memory-retry" class="subtle" hidden>重新翻开手记</button>
      <p class="memory-footnote">聊天时说「这件事一定要记住」，也能留下手记。普通聊天不会自动收录。<br>保存后跨对话保留；修改、删除或暂停，从下一次新请求生效。旧聊天记录仍保留。</p>
    </div>
    <footer class="memory-footer"><span id="memory-save-note">随时可以改写，也可以忘记</span><div><button type="button" id="memory-cancel" class="subtle">暂不改动</button><button type="submit" id="memory-save" class="primary">收好这几页 ↗</button></div></footer>
  </form>`;
  document.body.append(dialog);
  const $ = id => document.getElementById(id);
  const copy = value => JSON.parse(JSON.stringify(value));
  let owner = null, client = null, generation = 0, draft = null, busy = false, conflict = false;
  const notify = text => window.CompanionSettings.notify(text);
  function speaker() { $('memory-speaker').textContent = `${window.CompanionSettings?.agentName() || '衣衣'} · 写给你`; }
  function controls() {
    $('memory-save').disabled = busy || !draft || conflict;
    $('memory-add').disabled = busy || !draft || draft.entries.length >= 30;
    $('memory-enabled').disabled = busy || !draft;
    $('memory-close').disabled = busy; $('memory-cancel').disabled = busy;
    $('memory-count').textContent = draft ? `${draft.entries.length} / 30 页` : '';
    $('memory-empty').hidden = !draft || draft.entries.length > 0;
    dialog.querySelectorAll('#memory-list textarea, #memory-list button, .memory-category-options button').forEach(el => { el.disabled = busy; });
  }
  function changed() { $('memory-save-note').textContent = '还没收好 · 保存后才会记住'; }
  let activePicker = null;
  function categoryPicker(entry, index) {
    const names = ['穿衣习惯','日常片段','相处约定'];
    const wrapper = document.createElement('div'); wrapper.className = 'memory-category';
    const trigger = document.createElement('button'); trigger.type = 'button'; trigger.className = 'memory-category-trigger';
    trigger.setAttribute('aria-label', `第 ${index + 1} 页分类：${entry.category}`);
    trigger.setAttribute('aria-haspopup', 'listbox'); trigger.setAttribute('aria-expanded', 'false');
    const label = document.createElement('span'); label.textContent = entry.category;
    const arrow = document.createElement('span'); arrow.textContent = '⌄'; arrow.setAttribute('aria-hidden','true'); trigger.append(label, arrow);
    const list = document.createElement('div'); list.className = 'memory-category-options'; list.id = `memory-category-${entry.id}`;
    list.setAttribute('role','listbox'); list.setAttribute('aria-label', `第 ${index + 1} 页分类`); list.hidden = true;
    trigger.setAttribute('aria-controls', list.id);
    function hide(focus = false) { list.hidden = true; trigger.setAttribute('aria-expanded','false'); if (activePicker?.wrapper === wrapper) activePicker = null; if (focus) trigger.focus(); }
    function show() {
      if (busy) return;
      activePicker?.hide(); list.hidden = false;
      const anchor = trigger.getBoundingClientRect(), bounds = dialog.getBoundingClientRect();
      const width = Math.min(196, Math.max(0, bounds.width - 18));
      const below = bounds.bottom - anchor.bottom - 14, above = anchor.top - bounds.top - 14;
      const height = Math.min(list.scrollHeight || 152, Math.max(below, above, 44));
      const top = below >= height || below >= above ? anchor.bottom - bounds.top + 4 : anchor.top - bounds.top - height - 4;
      list.style.width = `${width}px`; list.style.maxHeight = `${height}px`;
      list.style.left = `${Math.max(8, Math.min(anchor.left - bounds.left, bounds.width - width - 10))}px`;
      list.style.top = `${Math.max(8, Math.min(top, bounds.height - height - 10))}px`;
      trigger.setAttribute('aria-expanded','true'); activePicker = {wrapper, list, hide}; options[names.indexOf(entry.category)].focus({preventScroll:true});
    }
    const options = names.map(name => {
      const option = document.createElement('button'); option.type = 'button'; option.setAttribute('role','option'); option.dataset.category = name;
      option.textContent = name; option.setAttribute('aria-selected', String(entry.category === name)); option.tabIndex = -1;
      option.onclick = () => { entry.category = name; label.textContent = name; trigger.setAttribute('aria-label', `第 ${index + 1} 页分类：${name}`); options.forEach(item => item.setAttribute('aria-selected', String(item.dataset.category === name))); changed(); hide(true); };
      list.append(option); return option;
    });
    trigger.onclick = () => list.hidden ? show() : hide();
    trigger.onkeydown = event => { if (['ArrowDown','ArrowUp'].includes(event.key)) { event.preventDefault(); event.stopPropagation(); show(); } };
    const onKey = event => {
      if (list.hidden) return;
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); hide(true); }
      else if (event.key === 'Tab') hide();
      else if (['ArrowDown','ArrowUp','Home','End'].includes(event.key)) {
        event.preventDefault(); const current = options.indexOf(document.activeElement);
        options[event.key === 'Home' ? 0 : event.key === 'End' ? 2 : (current + (event.key === 'ArrowUp' ? 2 : 1)) % 3].focus();
      }
    };
    wrapper.onkeydown = onKey; list.onkeydown = onKey;
    const onBlur = event => { if (!wrapper.contains(event.relatedTarget) && !list.contains(event.relatedTarget)) hide(); };
    wrapper.addEventListener('focusout', onBlur); list.addEventListener('focusout', onBlur);
    wrapper.append(trigger); dialog.append(list); return wrapper;
  }
  document.addEventListener('click', event => { if (activePicker && !activePicker.wrapper.contains(event.target) && !activePicker.list.contains(event.target)) activePicker.hide(); });
  function render(focusId = null) {
    activePicker?.hide();
    dialog.querySelectorAll('.memory-category-options').forEach(list => list.remove());
    $('memory-list').replaceChildren(); $('memory-enabled').checked = draft?.enabled ?? true;
    for (const [index, entry] of (draft?.entries || []).entries()) {
      const card = document.createElement('article'); card.className = 'memory-page';
      const top = document.createElement('div'); top.className = 'memory-page-top';
      const number = document.createElement('span'); number.className = 'memory-page-number'; number.textContent = `PAGE ${String(index + 1).padStart(2, '0')}`;
      const category = categoryPicker(entry, index);
      const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'subtle memory-remove'; remove.textContent = '删去这页'; remove.setAttribute('aria-label', `删除第 ${index + 1} 页`);
      remove.onclick = () => { draft.entries = draft.entries.filter(item => item.id !== entry.id); changed(); render(); $('memory-add').focus(); };
      top.append(number, category, remove);
      const text = document.createElement('textarea'); text.id = `memory-text-${entry.id}`; text.rows = 3; text.maxLength = 480;
      text.setAttribute('aria-label', `第 ${index + 1} 页内容`); text.placeholder = '比如：我不穿高跟鞋，平底鞋更适合我的日常。'; text.value = entry.content;
      const count = document.createElement('small'); count.className = 'memory-length'; count.textContent = `${Array.from(entry.content).length} / 240`;
      text.oninput = () => { entry.content = text.value; count.textContent = `${Array.from(entry.content).length} / 240`; changed(); };
      card.append(top, text, count); $('memory-list').append(card);
    }
    controls(); if (focusId) $(`memory-text-${focusId}`)?.focus();
  }
  function reset() {
    draft = null; busy = false; conflict = false; $('memory-conflict').hidden = true; $('memory-retry').hidden = true;
    $('memory-save-note').textContent = '随时可以改写，也可以忘记'; render();
  }
  function close() { if (busy) return; generation++; dialog.close(); reset(); $('settings-open')?.focus(); }
  async function read() {
    const current = ++generation, api = client; reset(); busy = true; controls(); $('memory-loading').hidden = false;
    try {
      const result = await api('/api/memories'); if (current !== generation) return;
      draft = copy(result); render();
    } catch (error) {
      if (current !== generation) return;
      $('memory-retry').hidden = false; notify(error.message || '还没翻开手记，可以再试一次。');
    } finally { if (current === generation) { busy = false; $('memory-loading').hidden = true; controls(); } }
  }
  $('memory-add').onclick = () => {
    if (busy || !draft || draft.entries.length >= 30) return;
    const id = window.crypto.randomUUID(); draft.entries.push({id,category:'穿衣习惯',content:''}); changed(); render(id);
  };
  $('memory-enabled').onchange = () => { if (draft) { draft.enabled = $('memory-enabled').checked; changed(); } };
  $('memory-close').onclick = close; $('memory-cancel').onclick = close;
  dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
  $('memory-reload').onclick = read; $('memory-retry').onclick = read;
  $('memory-form').onsubmit = async event => {
    event.preventDefault(); if (busy || !draft || conflict) return;
    const saved = copy(draft); saved.entries.forEach(x => { x.content = x.content.trim(); });
    const invalid = saved.entries.find(x => !x.content || Array.from(x.content).length > 240);
    if (invalid) { $(`memory-text-${invalid.id}`).focus(); notify('每一页请留下 1—240 字；空白页也可以先删去。'); return; }
    if (new Set(saved.entries.map(x => x.content)).size !== saved.entries.length) { notify('这件事已经在手记里了，不必再写一遍。'); return; }
    const current = generation, api = client; activePicker?.hide(); busy = true; controls();
    try {
      await api('/api/memories', {method:'PUT',body:JSON.stringify(saved)});
      if (current !== generation) return;
      busy = false; close(); notify(saved.enabled ? '手记收好了。下次聊天，我会参考你留下的这些小事。' : '手记收好了，参考也已暂停。想再用时，回来打开就好。');
    } catch (error) {
      if (current !== generation) return;
      if (error.code === 'memory_conflict') { conflict = true; $('memory-conflict').hidden = false; }
      notify(error.message || '这几页还没保存好，草稿仍在，可以再试一次。');
    } finally { if (current === generation) { busy = false; controls(); } }
  };
  window.addEventListener('companion-profile-change', speaker);
  window.LongTermMemory = {
    setOwner(id, api) { generation++; owner = id == null ? null : String(id); client = api; if (dialog.open) dialog.close(); reset(); },
    async open() { if (!owner || !client) return; speaker(); dialog.showModal(); await read(); }
  };
  $('memory-dialog').querySelector('.memory-scroll').addEventListener('scroll', () => activePicker?.hide(), {passive:true});
  function viewport() { activePicker?.hide(); dialog.style.setProperty('--memory-height', `${window.visualViewport?.height || window.innerHeight}px`); dialog.style.setProperty('--memory-top', `${window.visualViewport?.offsetTop || 0}px`); }
  window.visualViewport?.addEventListener('resize', viewport); window.visualViewport?.addEventListener('scroll', viewport); window.addEventListener('resize', viewport); viewport();
})();
