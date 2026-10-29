'use strict';
(() => {
  const dialog = document.createElement('dialog');
  dialog.id = 'product-preview';
  dialog.setAttribute('aria-label', '商品图片预览');
  const toolbar = document.createElement('div'); toolbar.className = 'preview-toolbar';
  const caption = document.createElement('div'); caption.className = 'preview-caption';
  caption.setAttribute('aria-live', 'polite');
  const control = (label, text, action) => {
    const button = document.createElement('button'); button.type = 'button';
    button.textContent = text; button.setAttribute('aria-label', label); button.onclick = action;
    return button;
  };
  const zoom = control('放大图片', '放大', () => setZoom(!zoomed));
  const close = control('关闭图片预览', '关闭 ×', () => dialog.close());
  toolbar.append(caption, zoom, close);
  const stage = document.createElement('div'); stage.className = 'preview-stage';
  const image = document.createElement('img'); image.referrerPolicy = 'no-referrer';
  image.draggable = false;
  const status = document.createElement('div'); status.className = 'preview-status';
  status.setAttribute('role', 'status');
  stage.append(image, status);
  const navigation = document.createElement('div'); navigation.className = 'preview-navigation';
  const previous = control('上一张商品图片', '← 上一张', () => move(-1));
  const hint = document.createElement('span'); hint.textContent = '点击图片放大 · 左右滑动切换';
  const next = control('下一张商品图片', '下一张 →', () => move(1));
  navigation.append(previous, hint, next);
  dialog.append(toolbar, stage, navigation); document.body.append(dialog);
  let gallery = [], index = 0, zoomed = false, touchStart = null, opener = null, swipeAt = 0;

  function setZoom(value) {
    zoomed = value; stage.classList.toggle('is-zoomed', value);
    zoom.textContent = value ? '还原' : '放大';
    zoom.setAttribute('aria-label', value ? '还原图片大小' : '放大图片');
    zoom.setAttribute('aria-pressed', String(value));
    stage.scrollTop = 0; stage.scrollLeft = 0;
  }
  function show() {
    setZoom(false); image.hidden = false; zoom.disabled = false;
    status.textContent = '图片加载中…';
    image.alt = gallery[index].alt;
    caption.textContent = `${gallery[index].alt} · ${index + 1} / ${gallery.length}`;
    previous.disabled = index === 0; next.disabled = index === gallery.length - 1;
    navigation.hidden = gallery.length < 2;
    image.src = gallery[index].src;
  }
  function move(delta) {
    if (index + delta < 0 || index + delta >= gallery.length) return;
    index += delta; show();
  }
  image.onload = () => { status.textContent = ''; };
  image.onerror = () => {
    image.hidden = true; zoom.disabled = true;
    status.textContent = '暂无可显示的图片';
    if (dialog.open) window.CompanionSettings?.notify('图片暂时无法加载，请关闭后重试。');
  };
  image.onclick = () => { if (Date.now() - swipeAt > 500) setZoom(!zoomed); };
  stage.onclick = event => { if (event.target === stage) dialog.close(); };
  dialog.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault(); move(event.key === 'ArrowLeft' ? -1 : 1);
    }
  });
  stage.addEventListener('touchstart', event => {
    touchStart = !zoomed && event.touches.length === 1 ?
      { x: event.touches[0].clientX, y: event.touches[0].clientY } : null;
  }, { passive: true });
  stage.addEventListener('touchmove', event => {
    if (event.touches.length !== 1) touchStart = null;
  }, { passive: true });
  stage.addEventListener('touchend', event => {
    if (!touchStart || zoomed || event.changedTouches.length !== 1) return;
    const dx = event.changedTouches[0].clientX - touchStart.x;
    const dy = event.changedTouches[0].clientY - touchStart.y;
    touchStart = null;
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) {
      swipeAt = Date.now(); move(dx < 0 ? 1 : -1);
    }
  }, { passive: true });
  stage.addEventListener('touchcancel', () => { touchStart = null; });
  dialog.addEventListener('close', () => {
    document.documentElement.classList.remove('preview-open');
    image.removeAttribute('src'); gallery = []; touchStart = null;
    if (opener?.isConnected) opener.focus({ preventScroll: true });
    opener = null;
  });
  document.addEventListener('click', event => {
    const button = event.target.closest('.product-image');
    if (!button) return;
    const buttons = [...button.closest('.products').querySelectorAll('.product-image')];
    gallery = buttons.map(item => ({ src: item.dataset.previewSrc, alt: item.querySelector('img').alt }));
    index = buttons.indexOf(button); opener = button;
    show(); dialog.showModal(); document.documentElement.classList.add('preview-open'); close.focus();
  });
})();
