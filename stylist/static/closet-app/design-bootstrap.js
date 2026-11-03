// A separate visual proposal; the iOS parity version remains at /app/.
(() => {
  const root = document.documentElement;
  const design = new URLSearchParams(location.search).get('design');
  root.dataset.appDesign = design === 'yijian' ? 'yijian' : 'ios';
  root.dataset.appEdition = root.dataset.appDesign;
  // Account preferences are restored by yijian.js; legacy global preview colors are not authoritative.
  root.dataset.appPalette = 'male';
})();
