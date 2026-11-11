// A visual preview only: cycling never selects or saves an account persona.
(() => {
  const root = document.querySelector('.login-portraits');
  if (!root) return;
  const stage = root.querySelector('.login-portrait-stage');
  const landing = document.querySelector('.quick-login');
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const personas = [
    ['female_sweet_v1', '甜美机灵', 'yiyi-female-sweet-clever', 373.64, 35, 0.87, 9.1],
    ['male_calm_v1', '冷静可靠', 'yiyi-male-composed', 347.59, 15, 1.042, 7.62],
    ['female_warm_v1', '温柔坚定', 'yiyi-female-gentle-resolute', 342.04, 12, 0.901, 18.94],
    ['male_artistic_v1', '浪漫灵动', 'yiyi-male-artistic', 335.0, 15, 0.979, 14.12],
    ['female_regal_v1', '高傲自信', 'yiyi-female-regal-confident', 354.4, 15, 0.948, 17.63],
    ['male_confident_v1', '笃定不羁', 'yiyi-male-confident', 325.96, 8, 1.073, 6.82]
  ];
  let index = 0, timer = null, hovering = false, focused = false, leaving = false;
  const frames = [];
  const canPlay = () => !motion.matches && !hovering && !focused && !leaving && !document.hidden && !landing.hidden;
  function schedule() {
    clearTimeout(timer); timer = null;
    if (canPlay()) timer = setTimeout(() => { if (canPlay()) show((index + 1) % personas.length); schedule(); }, 5200);
    root.dataset.playing = String(canPlay());
  }
  function show(next) {
    index = next;
    root.dataset.persona = personas[index][0];
    root.dataset.index = String(index);
    stage.setAttribute('aria-label', `切换穿搭助理头像，当前为${personas[index][1]}`);
    frames.forEach((frame, i) => frame.classList.toggle('is-current', i === index));
  }
  personas.forEach(([id, label, asset, centerX, hairTop, scale, offsetY]) => {
    // Reuse the transparent front view from the three-view atlas. The union
    // clip admits hair above/outside the circle while containing the bust.
    // Preserve each original head pose; match the reference with scale/position only.
    const frame = document.createElement('span');
    frame.className = 'login-portrait-frame';
    frame.style.clipPath = `url("${location.href.split('#')[0]}#login-portrait-head-clip")`;
    const image = document.createElement('img');
    image.src = `/static/assets/characters/candidates-v2/${asset}-turnaround-transparent-v6.png`;
    image.alt = ''; image.decoding = 'async'; image.width = 1536; image.height = 1024;
    const left = 94 - centerX * scale, top = -20 - hairTop * scale + offsetY;
    frame.style.setProperty('--portrait-width', (1536 * scale / 188 * 100) + '%');
    frame.style.setProperty('--portrait-left', (left / 188 * 100) + '%');
    frame.style.setProperty('--portrait-top', (top / 188 * 100) + '%');
    frame.style.setProperty('--portrait-origin-x', (centerX / 1536 * 100) + '%');
    frame.style.setProperty('--portrait-origin-y', ((94 - top) / scale / 1024 * 100) + '%');
    image.addEventListener('error', () => { image.hidden = true; });
    frame.append(image); stage.append(frame); frames.push(frame);
  });
  stage.onclick = () => { show((index + 1) % personas.length); schedule(); };
  root.addEventListener('pointerenter', () => { hovering = true; schedule(); });
  root.addEventListener('pointerleave', () => { hovering = false; schedule(); });
  root.addEventListener('focusin', () => { focused = true; schedule(); });
  root.addEventListener('focusout', event => { if (!root.contains(event.relatedTarget)) { focused = false; schedule(); } });
  new MutationObserver(schedule).observe(landing, { attributes: true, attributeFilter: ['hidden'] });
  document.addEventListener('visibilitychange', schedule);
  motion.addEventListener('change', schedule);
  window.addEventListener('pagehide', () => { leaving = true; schedule(); });
  window.addEventListener('pageshow', () => { leaving = false; schedule(); });
  show(0); schedule();
})();
