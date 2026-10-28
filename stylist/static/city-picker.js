'use strict';
// Local catalog only: typed searches are never sent to a geocoding service.
globalThis.CityPicker = class CityPicker {
  static normalize(value) { return String(value || '').normalize('NFKC').trim().toLowerCase(); }
  static records(catalog) {
    return Object.entries(catalog).flatMap(([province_name, cities]) =>
      [...new Set(cities)].map(city_name => ({ province_name, city_name })));
  }
  static search(records, query) {
    const words = CityPicker.normalize(query).split(/\s+/).filter(Boolean);
    return records.filter(city => words.every(word =>
      CityPicker.normalize(city.province_name + ' ' + city.city_name).includes(word)));
  }
  static resolve(catalog, value = {}) {
    const shortProvince = name => CityPicker.normalize(name).replace(/(?:壮族|回族|维吾尔)?自治区$|特别行政区$|省$|市$/, '');
    const shortCity = name => CityPicker.normalize(name).replace(/市$/, '');
    const matches = CityPicker.records(catalog).filter(city =>
      (!value.province_name || shortProvince(city.province_name) === shortProvince(value.province_name)) &&
      shortCity(city.city_name) === shortCity(value.city_name));
    return matches.length === 1 ? matches[0] : null;
  }
  constructor(root, { onChange = () => {} } = {}) {
    this.root = root; this.onChange = onChange; this.catalog = {}; this.rows = [];
    this.province = ''; this.selected = null;
    const make = (tag, className, text = '') => {
      const node = document.createElement(tag); node.className = className; node.textContent = text; return node;
    };
    const label = make('label', 'city-picker-label', '搜索省份或城市');
    this.input = make('input', 'city-picker-input');
    this.input.type = 'search'; this.input.placeholder = '输入城市或省份，如 杭州 / 浙江';
    this.input.autocomplete = 'off'; this.input.spellcheck = false;
    this.input.setAttribute('enterkeyhint', 'search');
    label.append(this.input);
    this.summary = make('div', 'city-picker-summary'); this.summary.setAttribute('role', 'status');
    this.browse = make('div', 'city-picker-browse');
    this.provinces = make('div', 'city-picker-provinces'); this.provinces.setAttribute('role', 'group');
    this.provinces.setAttribute('aria-label', '选择省份');
    this.cities = make('div', 'city-picker-cities'); this.cities.setAttribute('role', 'group');
    this.cities.setAttribute('aria-label', '选择城市');
    this.browse.append(this.provinces, this.cities);
    this.results = make('div', 'city-picker-results'); this.results.setAttribute('role', 'group');
    this.results.setAttribute('aria-label', '城市搜索结果');
    root.replaceChildren(label, this.summary, this.browse, this.results);
    this.input.oninput = () => { this.selected = null; this.render(); this.results.scrollTop = 0; this.onChange(null); };
    this.input.onkeydown = event => {
      if (event.key !== 'Enter' || event.isComposing) return;
      event.preventDefault();
      const matches = CityPicker.search(this.rows, this.input.value);
      if (this.input.value.trim() && matches.length === 1) this.choose(matches[0]);
      else this.results.querySelector('button')?.focus();
    };
    root.addEventListener('keydown', event => {
      if (!event.target.matches('button') || !['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
      const buttons = [...event.target.parentElement.querySelectorAll('button')];
      const position = buttons.indexOf(event.target);
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 :
        Math.max(0, Math.min(buttons.length - 1, position + (event.key === 'ArrowDown' ? 1 : -1)));
      event.preventDefault(); buttons[next]?.focus();
    });
    this.render();
  }
  setCatalog(catalog) { this.catalog = catalog; this.rows = CityPicker.records(catalog); this.render(); }
  getValue() { return this.selected ? { ...this.selected } : null; }
  setValue(value) {
    this.selected = CityPicker.resolve(this.catalog, value || {});
    this.province = this.selected?.province_name || ''; this.input.value = '';
    this.render();
    this.provinces.querySelector('[aria-pressed="true"]')?.scrollIntoView({ block: 'nearest' });
    this.cities.querySelector('[aria-pressed="true"]')?.scrollIntoView({ block: 'nearest' });
    return Boolean(this.selected);
  }
  choose(city) {
    this.selected = city; this.province = city.province_name; this.input.value = '';
    this.input.blur(); this.render(); this.onChange(this.getValue());
    this.provinces.querySelector('[aria-pressed="true"]')?.scrollIntoView({ block: 'nearest' });
    this.cities.querySelector('[aria-pressed="true"]')?.scrollIntoView({ block: 'nearest' });
    this.cities.querySelector('[aria-pressed="true"]')?.focus({ preventScroll: true });
  }
  button(text, active, action, detail = '') {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = text;
    button.setAttribute('aria-pressed', String(active)); button.onclick = action;
    if (detail) { const small = document.createElement('small'); small.textContent = detail; button.append(small); }
    return button;
  }
  render() {
    const query = this.input.value.trim(), provinceScroll = this.provinces.scrollTop;
    this.browse.hidden = Boolean(query); this.results.hidden = !query;
    this.summary.textContent = this.selected ? `已选：${this.selected.province_name} · ${this.selected.city_name}` :
      query ? `找到 ${CityPicker.search(this.rows, query).length} 座城市，请点选后确认` : '先选省份，再选城市；也可以直接搜索城市';
    this.provinces.replaceChildren(...Object.keys(this.catalog).map(province => this.button(province,
      this.province === province, () => {
        this.province = province; this.selected = null;
        const cities = this.catalog[province];
        if (cities.length === 1) this.selected = { province_name: province, city_name: cities[0] };
        this.render(); this.cities.scrollTop = 0; this.onChange(this.getValue());
        this.cities.querySelector('button')?.focus({ preventScroll: true });
      })));
    this.provinces.scrollTop = provinceScroll;
    this.cities.replaceChildren(...(this.catalog[this.province] || []).map(city_name => this.button(city_name,
      this.selected?.city_name === city_name && this.selected?.province_name === this.province,
      () => this.choose({ province_name: this.province, city_name }))));
    if (!this.province) this.cities.textContent = '请选择左侧省份';
    const matches = query ? CityPicker.search(this.rows, query) : [];
    this.results.replaceChildren(...matches.map(city => this.button(city.city_name, false,
      () => this.choose(city), city.province_name)));
    if (query && !matches.length) this.results.textContent = '没有找到匹配城市，试试城市全称或所属省份。';
  }
};
