'use strict';
(() => {
  const columns = 8, rows = 6;
  function mount(root) {
    const portraits = new Map();
    function fit(card) {
      const item = portraits.get(card);
      if (!item?.aspect || !card.clientWidth || !card.clientHeight) return;
      // Cover each card with one frame, retaining the source aspect ratio.
      const width = Math.max(card.clientWidth, card.clientHeight * item.aspect);
      const height = width / item.aspect;
      item.sprite.style.width = `${width}px`;
      item.sprite.style.height = `${height}px`;
      // Both sources are centered and normalized before packing; never move the body.
      item.sprite.style.top = '0px';
    }
    const resize = new ResizeObserver(entries => { for (const { target } of entries) fit(target); });
    for (const sprite of root.querySelectorAll('.companion-portrait')) {
      const card = sprite.closest('.companion-person');
      const item = { sprite, aspect: null }; portraits.set(card, item); resize.observe(card);
      const preload = new Image();
      const gender = sprite.dataset.portrait === 'male' ? 'male' : 'female';
      const src = `/static/assets/characters/yiyi-${gender}-breeze-atlas-v2.png`;
      preload.onload = () => {
        item.aspect = (preload.naturalWidth / columns) / (preload.naturalHeight / rows);
        if (!Number.isFinite(item.aspect) || item.aspect <= 0) return;
        sprite.style.backgroundImage = `url('${src}')`; fit(card); card.classList.add('portrait-ready');
      };
      // Keep the static portrait if a texture fails; selection must still work.
      preload.src = src;
    }
    const visibility = () => root.classList.toggle('portraits-paused', document.hidden);
    document.addEventListener('visibilitychange', visibility); visibility();
    return () => { resize.disconnect(); document.removeEventListener('visibilitychange', visibility); };
  }
  window.CompanionPortraits = { mount, columns, rows, frames: columns * rows };
})();
