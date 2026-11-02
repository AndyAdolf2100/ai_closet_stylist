'use strict';
(() => {
  const base = '/static/assets/characters/candidates-v2/';
  const framing = {"female_sweet_v1":{"scale":0.75799574,"top":20.526969,"left":-3.691365},"female_warm_v1":{"scale":0.75230769,"top":20.260968,"left":-3.288462},"female_regal_v1":{"scale":0.8203125,"top":14.74762,"left":-8.105469},"male_artistic_v1":{"scale":0.85084034,"top":12.425527,"left":-10.267857},"male_calm_v1":{"scale":0.86792453,"top":10.642689,"left":-11.477987},"male_confident_v1":{"scale":0.87487073,"top":9.387321,"left":-11.97001}};
  const blinkEyes = {
    female_sweet_v1: [46.5, 28.6, 58.0, 25.0, 5.2, 3.8],
    female_warm_v1: [47.0, 25.4, 58.6, 23.2, 5.0, 3.8],
    female_regal_v1: [44.5, 23.8, 56.2, 21.7, 5.0, 3.2],
    male_artistic_v1: [42.0, 23.6, 52.3, 20.9, 5.0, 3.2],
    male_calm_v1: [44.6, 26.1, 55.4, 23.1, 5.0, 3.2],
    male_confident_v1: [46.4, 20.1, 55.6, 17.7, 4.5, 3.0],
  };
  const characters = [
    { id: 'female_sweet_v1', gender: 'female', label: '甜美机灵', height: 158,
      image: 'yiyi-female-sweet-clever-turnaround-transparent-v6.png', summary: '细心观察 · 轻巧俏皮',
      greeting: '留一点小巧思，让今天多一个喜欢的理由。' },
    { id: 'female_warm_v1', gender: 'female', label: '温柔坚定', height: 163,
      image: 'yiyi-female-gentle-resolute-turnaround-transparent-v6.png', summary: '温暖可靠 · 认真果断',
      greeting: '慢慢来，我们把喜欢的生活落在小事里。' },
    { id: 'female_regal_v1', gender: 'female', label: '高傲自信', height: 175,
      image: 'yiyi-female-regal-confident-turnaround-transparent-v6.png', summary: '审美鲜明 · 从容有主见',
      greeting: '你的喜欢值得被认真对待，选择也由你来。' },
    { id: 'male_artistic_v1', gender: 'male', label: '浪漫灵动', height: 180,
      image: 'yiyi-male-artistic-turnaround-transparent-v6.png', summary: '艺术敏感 · 轻松健谈',
      greeting: '给日常一点颜色，也给我们一点新灵感。' },
    { id: 'male_calm_v1', gender: 'male', label: '冷静可靠', height: 184,
      image: 'yiyi-male-composed-turnaround-transparent-v6.png', summary: '克制细致 · 踏实温暖',
      greeting: '先把选择收少一点，我们按你的节奏来。' },
    { id: 'male_confident_v1', gender: 'male', label: '笃定不羁', height: 188,
      image: 'yiyi-male-confident-turnaround-transparent-v6.png', summary: '松弛自信 · 直率玩味',
      greeting: '别急着否定自己，先看看你真正喜欢哪一种。' },
  ].map(character => Object.freeze({ ...character, image: base + character.image, framing: Object.freeze(framing[character.id]), blinkEyes: Object.freeze(blinkEyes[character.id]) }));
  const find = id => characters.find(character => character.id === id) || characters[1];
  const gender = id => find(id).gender;
  function apply(id) {
    const character = find(id);
    const root = document.documentElement;
    root.dataset.companionPersona = character.id;
    root.style.setProperty('--companion-character-image', `url("${character.image}")`);
    root.dataset.companionCharacter = character.label;
    const assetBase = '/static/assets/characters/companion-scenes-v1/' + character.id;
    root.style.setProperty('--companion-hero-image', `url("/static/assets/characters/companion-scenes-v2/${character.id}-hero.png")`);
    root.style.setProperty('--companion-avatar-image', `url("${assetBase}-avatar.png")`);
    root.style.setProperty('--companion-weather-image', `url("${assetBase}-weather.png")`);
    ['x1', 'y1', 'x2', 'y2', 'rx', 'ry'].forEach((key, index) => {
      root.style.setProperty('--blink-eye-' + key, character.blinkEyes[index] + '%');
    });
    return character;
  }
  window.CompanionCharacters = Object.freeze({ all: Object.freeze(characters), find, gender, apply });
  window.addEventListener('companion-profile-change', event => apply(event.detail?.assistant_persona));
})();
