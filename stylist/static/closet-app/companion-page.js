import '../companion-characters.js';

let currentProfile = null;
const element = (tag, className, text) => {
  const el = document.createElement(tag);
  el.className = className;
  if (text != null) el.textContent = text;
  return el;
};
function render(page) {
  const character = window.CompanionCharacters.find(currentProfile?.assistant_persona);
  const name = currentProfile?.agent_name?.trim() || '衣衣';
  page.style.setProperty('--assistant-fullbody', `url("${character.image}")`);
  page.querySelector('.companion-fullbody').setAttribute('aria-label', `${name}的全身形象`);
  page.querySelector('.companion-page-name').textContent = name;
  page.querySelector('.companion-page-greeting').textContent = character.greeting;
}
export function syncCompanionPage(profile) {
  currentProfile = profile;
  document.querySelectorAll('.companion-page').forEach(render);
}
export function companionPage(openAgent) {
  const page = element('section', 'companion-page');
  page.setAttribute('aria-label', '我的穿搭助理');
  page.append(element('span', 'companion-page-orbit'));
  const figure = element('div', 'companion-fullbody');
  figure.setAttribute('role', 'img');
  page.append(figure);
  const intro = element('div', 'companion-page-intro');
  intro.append(element('span', 'companion-page-eyebrow', 'YOUR PERSONAL STYLIST'),
    element('h1', 'companion-page-name'));
  page.append(intro);
  const letter = element('div', 'companion-page-letter');
  letter.append(element('span', 'companion-page-mark', '✧'), element('p', 'companion-page-greeting'));
  const actions = element('nav', 'companion-page-actions');
  actions.setAttribute('aria-label', '助理与偏好设置');
  for (const [title, subtitle, action, mark] of [
    ['称呼与陪伴', '名字、形象与相处的方式', 'settings', '✧'],
    ['了解我', '慢慢了解你的穿搭喜好', 'preferences', '♡']
  ]) {
    const row = element('button', 'companion-page-action');
    row.type = 'button';
    const copy = element('span', 'companion-action-copy');
    copy.append(element('strong', '', title), element('small', '', subtitle));
    const icon = element('span', 'companion-action-mark', mark);
    icon.setAttribute('aria-hidden', 'true');
    row.append(icon, copy, element('span', 'companion-action-arrow', '↗'));
    row.onclick = () => openAgent(action);
    actions.append(row);
  }
  const footer = element('div', 'companion-page-footer');
  footer.append(letter, actions, element('p', 'companion-page-footnote', '每一种喜欢，都可以慢慢说。'));
  page.append(footer);
  page.reopen = () => { render(page); return page; };
  render(page);
  return page;
}
