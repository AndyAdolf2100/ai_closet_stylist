const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

const template = fs.readFileSync(path.join(__dirname, '../scripts/report_assets/dialogue_report.html'), 'utf8');
const labels = {
  female_sweet_v1: '女 · 甜美机灵', female_warm_v1: '女 · 温柔坚定', female_regal_v1: '女 · 高傲自信',
  male_artistic_v1: '男 · 浪漫灵动', male_calm_v1: '男 · 冷静可靠', male_confident_v1: '男 · 笃定不羁'
};
function setup() {
  const records = Object.keys(labels).flatMap(persona => Array.from({length: 12}, (_, i) => ({
    case: `${persona}/single/round_${i}`, persona, message: `问题 ${i}`,
    reply: {message: `回答 ${persona} ${i}`, looks: [], warnings: [], follow_ups: []},
    errors: [], automatic_errors: [], persona_review: {status: 'passed'}
  })));
  records.push({...records[0], case: 'future_role/single/round_0', persona: 'future_role'});
  const cases = Object.fromEntries(['confirmed','false_positive','observation'].map((status,i) =>
    [records[i].case, {status,note:'合成人工注释'}]));
  records[1].errors=['persona_review_invalid_evidence'];
  const data = {records, generated_at: '合成时间', batches: [], manual: {issues: [], cases}};
  return new JSDOM(template.replace('__REPORT_DATA__', JSON.stringify(data)), {runScripts: 'dangerously'});
}
function change(w, id, value) {
  const el = w.document.getElementById(id); el.value = value;
  el.dispatchEvent(new w.Event(id === 'search' ? 'input' : 'change'));
}

test('report labels and filters all six roles without classifying new male roles as female', () => {
  const dom = setup(), w = dom.window, $ = id => w.document.getElementById(id);
  for (const [id, label] of Object.entries(labels)) {
    assert.equal($('persona').querySelector(`option[value="${id}"]`).textContent, label);
    change(w, 'persona', id);
    assert.equal(w.document.querySelectorAll('.case').length, 12);
    assert([...w.document.querySelectorAll('.case-head .chip:first-of-type')].every(el => el.textContent === label));
  }
  assert($('meta').textContent.includes('男 · 笃定不羁 12 轮'));
  change(w, 'persona', 'future_role');
  assert.equal(w.document.querySelector('.case-head .chip').textContent, 'future_role');
  dom.window.close();
});

test('manual findings and false-positive evidence remain separate from machine acceptance', () => {
  const dom=setup(),w=dom.window;
  for(const status of ['confirmed','false_positive','observation']){
    change(w,'status',status);
    assert.equal(w.document.querySelectorAll('.case').length,1);
    assert(w.document.querySelector('.manual').textContent.includes('合成人工注释'));
  }
  change(w,'status','focus');
  assert.equal(w.document.querySelectorAll('.case').length,2);
  assert(!w.document.getElementById('records').textContent.includes('评测误报已复核'));
  dom.window.close();
});

test('large report paginates, resets on filters and compares the same question across six roles', () => {
  const dom = setup(), w = dom.window, $ = id => w.document.getElementById(id);
  assert.equal(w.document.querySelectorAll('.case').length, 60);
  assert($('previous-page').disabled); assert(!$('next-page').disabled);
  $('next-page').click();
  assert.equal(w.document.querySelectorAll('.case').length, 13);
  assert($('next-page').disabled);
  change(w, 'persona', 'male_confident_v1');
  assert($('previous-page').disabled);
  assert.equal(w.document.querySelectorAll('.case').length, 12);
  $('reset').click(); $('compare').click();
  assert.equal($('compare').getAttribute('aria-pressed'), 'true');
  change(w, 'search', 'round_11');
  assert.equal(w.document.querySelectorAll('.case').length, 6);
  assert.equal(new Set([...w.document.querySelectorAll('.case-head .chip:first-of-type')].map(el => el.textContent)).size, 6);
  change(w, 'search', '不存在的内容');
  assert.equal(w.document.querySelectorAll('.case').length, 0);
  assert($('previous-page').disabled); assert($('next-page').disabled);
  dom.window.close();
});
