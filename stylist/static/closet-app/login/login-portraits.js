// A visual preview only: cycling never selects or saves an account persona.
(() => {
  const root = document.querySelector('.login-portraits');
  if (!root) return;
  const stage = root.querySelector('.login-portrait-stage');
  const pause = root.querySelector('.login-portrait-pause');
  const landing = document.querySelector('.quick-login');
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const personas = [
    ['female_sweet_v1', '甜美机灵'], ['male_calm_v1', '冷静可靠'],
    ['female_warm_v1', '温柔坚定'], ['male_artistic_v1', '浪漫灵动'],
    ['female_regal_v1', '高傲自信'], ['male_confident_v1', '笃定不羁']
  ];
  let index = 0, timer = null, paused = false, hovering = false, focused = false, leaving = false;
  const images = [];
  const canPlay = () => !motion.matches && !paused && !hovering && !focused && !leaving && !document.hidden && !landing.hidden;
  function schedule() {
    clearTimeout(timer); timer = null;
    if (canPlay()) timer = setTimeout(() => { if (canPlay()) show((index + 1) % personas.length); schedule(); }, 5200);
    root.dataset.playing = String(canPlay());
    pause.hidden = motion.matches;
  }
  function show(next) {
    index = next;
    root.dataset.persona = personas[index][0];
    root.dataset.index = String(index);
    stage.setAttribute('aria-label', `切换穿搭助理头像，当前为${personas[index][1]}`);
    images.forEach((image, i) => image.classList.toggle('is-current', i === index));
  }
  personas.forEach(([id], i) => {
    const image = document.createElement('img');
    image.src = `/static/closet-app/assets/care-portraits/${id}-closeup.png`;
    image.alt = ''; image.decoding = 'async'; image.width = image.height = 240;
    image.addEventListener('error', () => { image.hidden = true; });
    stage.append(image); images.push(image);
  });
  stage.onclick = () => { show((index + 1) % personas.length); schedule(); };
  pause.onclick = () => {
    paused = !paused;
    pause.setAttribute('aria-pressed', String(paused));
    pause.setAttribute('aria-label', paused ? '继续头像轮播' : '暂停头像轮播');
    pause.querySelector('path').setAttribute('d', paused ? 'm9 5 10 7-10 7Z' : 'M9 6v12M15 6v12');
    schedule();
  };
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
