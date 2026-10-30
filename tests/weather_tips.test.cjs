const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');
const source = fs.readFileSync('stylist/static/app.js', 'utf8');
function render(days) {
  const document = new JSDOM('<body></body>').window.document;
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  };
  const code = source.slice(source.indexOf('function weatherIcon('), source.indexOf('function updateCityLabel('));
  const card = new Function('el', 'WeatherVisuals', 'mascot', 'namedElement', code + ';return forecastCard;')(
    el, { background() {} }, () => el('span'), el
  );
  return card({ city_name: '北京市', scope: 'week', days, warnings: [], notice: '预报参考' });
}
const day = (date, low, high, reminders) => ({
  date, weekday: '周六', temp_min: low, temp_max: high,
  condition_day: '多云', condition_night: '多云', reminders
});
test('week keeps every date when the middle day has no condition-specific tips', () => {
  const cold = {kind: 'cold', severity: 'notice', title: '保暖小叮咛', text: '注意保暖'};
  const days = [day('2026-10-30', 4, 20, [cold]), day('2026-10-31', 6, 12, []), day('2026-11-01', 2, 17, [cold])];
  const before = JSON.stringify(days);
  const card = render(days);
  assert.deepEqual([...card.querySelectorAll('.weather-tip-date time')].map(n => n.dateTime), days.map(d => d.date));
  const groups = card.querySelectorAll('.weather-tip-day');
  assert.match(groups[1].textContent, /日常穿衣小叮咛/);
  assert.match(groups[0].textContent, /保暖小叮咛/);
  assert.equal(groups[1].querySelectorAll('.weather-tip').length, 1);
  assert.doesNotMatch(groups[1].textContent, /无风险|没有预警|安全出行/);
  assert.equal(JSON.stringify(days), before);
});
test('missing tips on a single-day forecast still show daily guidance', () => {
  const card = render([day('2026-10-31', 6, 12)]);
  assert.match(card.querySelector('.weather-alerts').textContent, /日常穿衣小叮咛/);
  assert.equal(card.querySelectorAll('.weather-tip-day').length, 0);
});
