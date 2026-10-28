const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const { runInNewContext } = require('node:vm');

const context = {};
runInNewContext(readFileSync(join(__dirname, '../stylist/static/city-picker.js'), 'utf8'), context);
const Picker = context.CityPicker;
const catalog = JSON.parse(readFileSync(join(__dirname, '../stylist/static/china-cities.json'), 'utf8'));
const rows = Picker.records(catalog);
const plain = value => JSON.parse(JSON.stringify(value));

test('city names can be searched nationally without selecting a province', () => {
  assert.deepEqual(plain(Picker.search(rows, '杭州')), [{ province_name: '浙江省', city_name: '杭州市' }]);
  assert.equal(Picker.search(rows, '不存在的城市').length, 0);
});

test('province and city queries can be combined and whitespace is ignored', () => {
  assert.deepEqual(plain(Picker.search(rows, ' 浙江  杭州 ')), [{ province_name: '浙江省', city_name: '杭州市' }]);
  assert.equal(Picker.search(rows, '浙江').length, catalog['浙江省'].length);
  assert.equal(Picker.search(rows, '浙江 上海').length, 0);
});

test('saved and geolocated municipalities and autonomous regions use canonical names', () => {
  assert.deepEqual(plain(Picker.resolve(catalog, { province_name: '上海', city_name: '上海' })),
    { province_name: '上海市', city_name: '上海市' });
  assert.deepEqual(plain(Picker.resolve(catalog, { province_name: '广西', city_name: '南宁' })),
    { province_name: '广西壮族自治区', city_name: '南宁市' });
  assert.equal(Picker.resolve(catalog, { province_name: '浙江省', city_name: '上海市' }), null);
  assert.equal(Picker.resolve(catalog, {}), null);
});

test('ambiguous names require an explicit province instead of selecting the first match', () => {
  const sample = { '甲省': ['同名市', '同名市'], '乙省': ['同名市'] };
  assert.equal(Picker.records(sample).length, 2);
  assert.equal(Picker.search(Picker.records(sample), '同名').length, 2);
  assert.equal(Picker.resolve(sample, { city_name: '同名市' }), null);
  assert.deepEqual(plain(Picker.resolve(sample, { province_name: '乙省', city_name: '同名市' })),
    { province_name: '乙省', city_name: '同名市' });
});
