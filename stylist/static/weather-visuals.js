'use strict';
(function(root) {
  const make = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const hazards = ['rain','snow','fog','wind','thunder','heat','cold','sand','ice','hail','drought','fire','typhoon','tornado','flood','general'];
  const levels = { red: '红色', orange: '橙色', yellow: '黄色', blue: '蓝色' };
  function mood(days) {
    const text = (days || []).map(d => (d.condition_day || '') + (d.condition_night || '')).join(' ');
    return /雪|冻雨|冰/.test(text) ? 'snow' : /雷/.test(text) ? 'thunder' : /暴雨|大雨/.test(text) ? 'heavy-rain' : /雨/.test(text) ? 'rain' : /雾|霾|沙|尘/.test(text) ? 'fog' : /大风|台风/.test(text) ? 'wind' : /阴|云/.test(text) ? 'cloudy' : 'sunny';
  }
  function background(card, days) {
    const value = mood(days); card.dataset.weather = value;
    card.style.setProperty('--weather-image', `url('/static/assets/weather-${value}-v1.png')`);
  }
  function warningCard(alert, demo = false) {
    if (!levels[alert.level]) return null;
    const node = make('article', 'official-warning warning-' + alert.level);
    node.dataset.level = alert.level;
    const picture = make('div', 'hazard-mascot');
    picture.dataset.hazard = hazards.includes(alert.hazard) ? alert.hazard : 'general';
    const index = Math.max(0, hazards.indexOf(alert.hazard) < 0 ? 15 : hazards.indexOf(alert.hazard));
    picture.style.backgroundPosition = `${(index % 4) * 100 / 3}% ${Math.floor(index / 4) * 100 / 3}%`;
    picture.setAttribute('role', 'img'); picture.setAttribute('aria-label', '衣衣提醒：' + alert.event);
    const content = make('div', 'official-warning-copy');
    content.append(make('span', 'warning-level', (demo ? '演示 · ' : '') + levels[alert.level] + '预警'), make('strong', '', alert.title));
    content.append(make('p', '', '影响区域：' + alert.area));
    const issued = new Date(alert.issued_at);
    content.append(make('small', '', `${alert.sender} · ${Number.isNaN(issued.getTime()) ? '发布时间待核对' : issued.toLocaleString('zh-CN')}`));
    const details = make('details'); details.append(make('summary', '', '查看灾害信息与防护提示'), make('p', '', alert.text));
    if (alert.source_url && /^https:\/\//i.test(alert.source_url)) {
      const link = make('a', '', '查看原始发布'); link.href = alert.source_url; link.target = '_blank'; link.rel = 'noopener noreferrer'; details.append(link);
    }
    content.append(details); node.append(picture, content); return node;
  }
  root.WeatherVisuals = { mood, background, warningCard, hazards, levels };
})(globalThis);
