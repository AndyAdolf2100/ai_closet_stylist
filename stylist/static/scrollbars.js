/* Reveal only the scroll containers being used; keep their geometry stable. */
(() => {
  'use strict';
  const timers = new WeakMap(), held = new Set();
  const scrollKeys = new Set(['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown', 'Home', 'End', ' ']);
  function reveal(element) {
    element.classList.add('scrollbar-active');
    clearTimeout(timers.get(element));
    timers.set(element, setTimeout(() => {
      if (!held.has(element)) element.classList.remove('scrollbar-active');
    }, 1200));
  }
  function containers(target) {
    const result = [];
    for (let element = target instanceof Element ? target : document.scrollingElement; element; element = element.parentElement) {
      const style = getComputedStyle(element);
      if ((element.scrollHeight > element.clientHeight && /auto|scroll|overlay/.test(style.overflowY)) ||
          (element.scrollWidth > element.clientWidth && /auto|scroll|overlay/.test(style.overflowX)) ||
          (element === document.scrollingElement && element.scrollHeight > element.clientHeight)) result.push(element);
    }
    return result;
  }
  document.addEventListener('scroll', event => {
    const element = event.target === document ? document.scrollingElement : event.target;
    if (element instanceof Element) reveal(element);
  }, { capture: true, passive: true });
  for (const type of ['pointermove', 'pointerdown', 'wheel', 'focusin', 'keydown']) {
    document.addEventListener(type, event => {
      if (type === 'keydown' && !scrollKeys.has(event.key)) return;
      for (const element of containers(event.target)) {
        if (type === 'pointerdown') held.add(element);
        reveal(element);
      }
    }, { capture: true, passive: true });
  }
  function release() { for (const element of held) reveal(element); held.clear(); }
  document.addEventListener('pointerup', release, true);
  document.addEventListener('pointercancel', release, true);
  window.addEventListener('blur', release);
})();
