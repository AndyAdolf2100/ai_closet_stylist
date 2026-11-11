import {createClosetSwitcher} from './closet-switcher.js';
import {companionPage} from './companion-page.js';
import {readAvailablePoints} from './points-balance.js';
import {mountPaymentDemo,paymentDemoEnabled} from './payment-demo.js';
import {skuDetail} from './sku-fusion.js';
import {emptyArt} from './empty-art.js';
import { collectionPage } from './collection-pages.js';
import { openIntegratedAgent, closeIntegratedAgent, mountAgent, placeIntegratedAgent } from './agent-integration.js';
import { profilePage } from './profile-pages.js';
import {pointsEarningPage} from './points-earning.js';
import { albumCard, inspirationCard, observeWaterfall } from './cards.js';
import {subjectChatButton} from './subject-chat.js';
// App navigation is isolated from the existing Agent document and its state.
const $ = id => document.getElementById(id);
const ASSETS = '/static/closet-app/assets/';
const KEY = 'ai-closet-stylist-session-v1';
const state = { activeCloset:null, tab: 'home', feed: 'album', epoch: 0, page: 1, loading: false, feedVersion: 0, wardrobeVersion: 0, rows: [], products: [], session: '', controller: new AbortController() };
const node = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
const readSession = () => { try { return JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch { return null; } };
const safeURL = value => { try { const u = new URL(value, location.origin); return ['https:', 'http:'].includes(u.protocol) ? u.href : ''; } catch { return ''; } };
function picture(src, alt = '') { const img = node('img'); img.alt = alt; img.loading = 'lazy'; const url = safeURL(src || ''); if (src && url) img.src = url; else img.className = 'image-failed'; img.onerror = () => { img.removeAttribute('src'); img.alt = alt || '图片暂未载入'; img.classList.add('image-failed'); }; return img; }
function button(text, action, cls = 'pill') { const b = node('button', cls, text); b.type = 'button'; b.onclick = action; return b; }
function toast(text) { $('app-notice').textContent = text; $('app-notice').hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => { $('app-notice').hidden = true; }, 3500); }
async function api(section, page = 1, extra = {}) {
  const session = readSession();
  if (!session?.access_token) throw Object.assign(new Error('登录后查看你的衣橱与造型记录'), { login: true });
  const epoch = state.epoch;
  const response = await fetch(`/stylist-api/app/${section}?${new URLSearchParams({page,...extra})}`, { headers: { Authorization: `Bearer ${session.access_token}` }, cache: 'no-store', signal: state.controller.signal });
  const value = await response.json();
  if (epoch !== state.epoch) throw new DOMException('账号已切换', 'AbortError');
  if (!response.ok) throw Object.assign(new Error(response.status === 401 ? '登录已过期，请重新连接衣橱' : (value.message || '暂时没有加载成功，请重试')), { login: response.status === 401 });
  return value.data;
}
async function appWrite(section, body){
 const token=readSession()?.access_token,epoch=state.epoch;if(!token)throw Error('请先登录。');
 const response=await fetch('/stylist-api/app/'+section,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(body),signal:state.controller.signal});const result=await response.json();
 if(epoch!==state.epoch||readSession()?.access_token!==token)throw new DOMException('账号已切换','AbortError');if(!response.ok)throw Error(result.message||'操作未完成，请重试。');return result.data;
}
const closetSwitcher=createClosetSwitcher({read:api,write:appWrite,onSelect:closet=>{state.activeCloset=closet;loadWardrobe();},getSelected:()=>state.activeCloset,getProducts:()=>state.products,reload:loadWardrobe,notify:text=>window.PreviewMessage.notify(text)});
function showError(container, error, retry) {
  if (error.name === 'AbortError') return;
  const box = node('div', 'state'); box.append(node('p', '', error.message), button(error.login ? '连接衣橱' : '重新加载', error.login ? () => openAgent('login') : retry)); container.replaceChildren(box);
}
function loading(container) { container.replaceChildren(node('div', 'state', '正在加载…')); }
function empty(container, asset, label) { const box = node('div', 'empty'); box.append(document.documentElement.dataset.appDesign==='yijian'?emptyArt('journal'):picture(ASSETS + asset), node('p', '', label)); container.append(box); }
function backgroundInert(value) { $('pages').inert = value; document.body.classList.toggle('inert-background', value); }
const detailHistory = new Map(); let detailSerial = 0;
let createOpener;
function setCreate(open) {
  if (open) createOpener = document.activeElement;
  $('create-overlay').hidden = !open; $('create-toggle').setAttribute('aria-expanded', String(open)); backgroundInert(open); document.querySelector('.nav-capsule').inert = open;
  if (open) $('create-overlay').querySelector('.close').focus(); else if (createOpener?.isConnected) createOpener.focus();
}
function selectTab(tab, push = true) {
  if (!['home', 'wardrobe', 'profile'].includes(tab)) return;
  setCreate(false); state.tab = tab;
  for (const page of document.querySelectorAll('.page')) page.hidden = page.id !== tab;
  for (const b of document.querySelectorAll('[data-tab]')) { const active = b.dataset.tab === tab; b.toggleAttribute('aria-current', active); if (active) b.setAttribute('aria-current', 'page'); b.querySelector('img').src = `${ASSETS}navigation_${b.dataset.tab}_${active ? 'selected' : 'normal'}.png`; }
  if (push) history.pushState({tab, view: 'tab'}, '', `#${tab}`);
  if (tab === 'home') loadFeed(); else if (tab === 'wardrobe') loadWardrobe(); else { loadProfile(); loadMemories(); }
}
let stopWaterfall;
async function loadFeed(append = false) {
  const requestVersion = ++state.feedVersion;
  const feed = state.feed, epoch = state.epoch, page = append ? state.page + 1 : 1;
  const container = $('home-feed');
  if (!append) { stopWaterfall?.(); stopWaterfall = null; }
  if (feed === 'activity') {
    container.innerHTML = "<main data-v-192ed08e=\"\" class=\"v2-activities\" aria-label=\"潮流玩法\"><div data-v-192ed08e=\"\" class=\"v2-activities__list\"><article data-v-6d1aa142=\"\" data-v-192ed08e=\"\" class=\"v2-activity-card\" aria-labelledby=\"v2-activity-1\"><div data-v-6d1aa142=\"\" class=\"v2-activity-card__art\" aria-hidden=\"true\" style=\"--card-mask: url(/static/closet-app/assets/activity-app-0.svg);\"><img data-v-6d1aa142=\"\" src=\"/static/closet-app/assets/activity-app-1.png\" alt=\"\"></div><div data-v-6d1aa142=\"\" class=\"v2-activity-card__veil\" aria-hidden=\"true\"></div><div data-v-6d1aa142=\"\" class=\"v2-activity-card__content\"><div data-v-6d1aa142=\"\" class=\"v2-activity-card__copy\"><h2 data-v-6d1aa142=\"\" id=\"v2-activity-1\">搭配测评</h2><p data-v-6d1aa142=\"\">给自己的搭配打个分</p></div><button data-v-6d1aa142=\"\" class=\"v2-activity-card__button\" type=\"button\" aria-label=\"开始：搭配测评\"><span data-v-6d1aa142=\"\">开始</span><img data-v-6d1aa142=\"\" src=\"/static/closet-app/assets/activity-app-2.svg\" alt=\"\" width=\"14\" height=\"14\"></button></div></article><article data-v-6d1aa142=\"\" data-v-192ed08e=\"\" class=\"v2-activity-card\" aria-labelledby=\"v2-activity-9\"><div data-v-6d1aa142=\"\" class=\"v2-activity-card__art\" aria-hidden=\"true\" style=\"--card-mask: url(/static/closet-app/assets/activity-app-0.svg);\"><img data-v-6d1aa142=\"\" src=\"/static/closet-app/assets/activity-app-3.png\" alt=\"\"></div><div data-v-6d1aa142=\"\" class=\"v2-activity-card__veil\" aria-hidden=\"true\"></div><div data-v-6d1aa142=\"\" class=\"v2-activity-card__content\"><div data-v-6d1aa142=\"\" class=\"v2-activity-card__copy\"><h2 data-v-6d1aa142=\"\" id=\"v2-activity-9\">手绘涂鸦站</h2><p data-v-6d1aa142=\"\">把穿搭照片变成超萌手绘涂鸦拼贴图</p></div><button data-v-6d1aa142=\"\" class=\"v2-activity-card__button\" type=\"button\" aria-label=\"开始涂鸦：手绘涂鸦站\"><span data-v-6d1aa142=\"\">开始涂鸦</span><img data-v-6d1aa142=\"\" src=\"/static/closet-app/assets/activity-app-2.svg\" alt=\"\" width=\"14\" height=\"14\"></button></div></article><article data-v-6d1aa142=\"\" data-v-192ed08e=\"\" class=\"v2-activity-card\" aria-labelledby=\"v2-activity-4\"><div data-v-6d1aa142=\"\" class=\"v2-activity-card__art\" aria-hidden=\"true\" style=\"--card-mask: url(/static/closet-app/assets/activity-app-0.svg);\"><img data-v-6d1aa142=\"\" src=\"/static/closet-app/assets/activity-app-4.png\" alt=\"\"></div><div data-v-6d1aa142=\"\" class=\"v2-activity-card__veil\" aria-hidden=\"true\"></div><div data-v-6d1aa142=\"\" class=\"v2-activity-card__content\"><div data-v-6d1aa142=\"\" class=\"v2-activity-card__copy\"><h2 data-v-6d1aa142=\"\" id=\"v2-activity-4\">穿搭手帐薄</h2><p data-v-6d1aa142=\"\">轻松拆解穿搭小细节</p></div><button data-v-6d1aa142=\"\" class=\"v2-activity-card__button\" type=\"button\" aria-label=\"开始：穿搭手帐薄\"><span data-v-6d1aa142=\"\">开始</span><img data-v-6d1aa142=\"\" src=\"/static/closet-app/assets/activity-app-2.svg\" alt=\"\" width=\"14\" height=\"14\"></button></div></article><article data-v-6d1aa142=\"\" data-v-192ed08e=\"\" class=\"v2-activity-card\" aria-labelledby=\"v2-activity-5\"><div data-v-6d1aa142=\"\" class=\"v2-activity-card__art\" aria-hidden=\"true\" style=\"--card-mask: url(/static/closet-app/assets/activity-app-0.svg);\"><img data-v-6d1aa142=\"\" src=\"/static/closet-app/assets/activity-app-5.png\" alt=\"\"></div><div data-v-6d1aa142=\"\" class=\"v2-activity-card__veil\" aria-hidden=\"true\"></div><div data-v-6d1aa142=\"\" class=\"v2-activity-card__content\"><div data-v-6d1aa142=\"\" class=\"v2-activity-card__copy\"><h2 data-v-6d1aa142=\"\" id=\"v2-activity-5\">潮玩孵化仓</h2><p data-v-6d1aa142=\"\">用照片捏出穿搭潮玩</p></div><button data-v-6d1aa142=\"\" class=\"v2-activity-card__button\" type=\"button\" aria-label=\"开始：潮玩孵化仓\"><span data-v-6d1aa142=\"\">开始</span><img data-v-6d1aa142=\"\" src=\"/static/closet-app/assets/activity-app-2.svg\" alt=\"\" width=\"14\" height=\"14\"></button></div></article></div></main>";
    container.querySelectorAll('.v2-activity-card').forEach(card => {
      card.querySelector('button').onclick = () => window.PreviewMessage.notify('「' + card.querySelector('h2').textContent + '」还在准备中，先去试试别的穿搭灵感吧。');
    });
    return;
  }

  if (!append) { state.rows = []; loading(container); }
  state.loading = true;
  try {
    const data = await api(feed, page);
    if (epoch !== state.epoch || feed !== state.feed || requestVersion !== state.feedVersion) return;
    const rows = Array.isArray(data?.items) ? data.items : Array.isArray(data?.list) ? data.list : [];
    state.rows = append ? [...state.rows, ...rows] : rows; state.page = page;
    container.replaceChildren();
    if (!state.rows.length) empty(container, 'home_album_empty.png', feed === 'album' ? '这一页还空着，先和助理聊聊想穿什么吧。' : '这一页的灵感还在准备，稍后再来看看。');
    const grid = node('div', feed === 'album' ? 'album-list' : 'inspiration-grid');
    stopWaterfall?.();
    const helpers = { node, button, picture, openImage, assets: ASSETS };
    state.rows.forEach(item => grid.append(feed === 'album' ? albumCard(item, helpers) : inspirationCard(item, helpers)));
    container.append(grid);
    if (feed === 'inspiration') stopWaterfall = observeWaterfall(grid);
    const hasMore = data?.has_more ?? data?.hasMore ?? rows.length >= 10;
    if (hasMore) container.append(button('加载更多', e => { if (!state.loading) loadFeed(true); }, 'load-more pill'));
    else if (state.rows.length) container.append(node('p', 'state', '已经到底了'));
  } catch (e) { if (feed === state.feed && epoch === state.epoch && requestVersion === state.feedVersion) { if (append) toast(e.message); else showError(container, e, () => loadFeed()); } }
  finally { if (epoch === state.epoch && feed === state.feed && requestVersion === state.feedVersion) state.loading = false; }
}
function productCard(item) {
  const title = item.title || item.name || item.product_name || item.secondary_class_name || item.class_name || item.brand_name || '衣橱单品';
  const src = item.cutout_image || item.original_image || item.image_url || item.cover_image;
  const b = button('', () => {
    const body = node('div', 'detail-body');
    body.append(picture(src, title), node('h3', '', title));
    if (item.last_add_time) body.append(node('p', '', `添加于 ${item.last_add_time}`));
    body.append(subjectChatButton('product', item, {button, openAgent, readSession}));
    detail(title, body);
  }, 'product'); b.append(picture(src, title), node('span', '', title));const description=[item.color,item.material].filter(Boolean).join(' · ');if(description)b.append(node('small','y-product-note',description));return b;
}
function wardrobeSection(title, count, action, label) {
  const section = node('section', 'wardrobe-section'), header = node('header', 'section-heading'); header.append(node('strong', '', title)); if (count != null) header.append(node('span', '', String(count))); if (action) header.append(button(label, action, '')); section.append(header); return section;
}
async function loadWardrobe() {
  const requestVersion = ++state.wardrobeVersion;
  const target = $('wardrobe-sections'), epoch = state.epoch; loading(target);
  const modern=document.documentElement.dataset.appDesign==='yijian';
  const selected=state.activeCloset;
  const results=await Promise.allSettled([selected?api('closet-items',1,{wardrobe_id:selected.id}):api('recent'),api(modern?'closet-options':'closets'),selected?Promise.resolve({list:[]}):api('categories')]);
  if (epoch !== state.epoch || requestVersion !== state.wardrobeVersion) return;
  target.replaceChildren();
  if(modern)closetSwitcher.update(results[1].status==='fulfilled'?results[1].value?.list||[]:[]);
  const names = ['所有单品', '分类衣橱', '单品分类'];
  (document.documentElement.dataset.appDesign==='yijian'?[0,2,1]:[0,1,2]).forEach(i => {
    const result=results[i];
    if(i===1&&modern){if(result.status==='rejected'){const error=node('section','wardrobe-section');showError(error,result.reason,loadWardrobe);target.append(error);}return;}
    if(i===2&&document.documentElement.dataset.appDesign==='yijian'&&result.status==='fulfilled')return;
    if (result.status === 'rejected') { const section = wardrobeSection(names[i]); showError(section, result.reason, loadWardrobe); target.append(section); return; }
    const data = result.value || {};let rows = data.list || [];
    if(i===0&&!selected&&document.documentElement.dataset.appDesign==='yijian'){const categories=results[2].status==='fulfilled'?results[2].value?.list||[]:[];const seen=new Set();rows=[...rows,...categories.flatMap(c=>c.list||[])].filter(p=>{const id=p.user_product_id||p.id;if(!id)return true;if(seen.has(String(id)))return false;seen.add(String(id));return true;});}
    if (i === 0) {
      state.products = rows;
      const section = wardrobeSection(selected?.name||names[i], data.pagination?.total ?? data.page?.total ?? data.page_info?.total ?? rows.length, () => openAgent('upload'), '＋ 添加');
      if (!rows.length) { const box = node('div', 'section-empty'); box.append(document.documentElement.dataset.appDesign==='yijian'?emptyArt('wardrobe'):picture(ASSETS + 'closet_recent_empty.svg'), node('p', '', selected?'这个衣橱还空着，从我的衣橱选几件加入吧。':'先收进一件喜欢的衣服吧'));if(selected)box.append(button('从我的衣橱选择',()=>closetSwitcher.addItems()));section.append(box); }
      else if(document.documentElement.dataset.appDesign!=='yijian'){const rail=node('div','product-rail');rows.forEach(p=>rail.append(productCard(p)));section.append(rail,button('查看最近添加 ›',()=>showProducts(rows,'最近添加')));}
      else { const rail = node('div', 'product-grid y-wardrobe-grid'),search=node('input','search');
        search.type='search';search.placeholder='找一找，今天想穿的那件';search.setAttribute('aria-label','搜索已加载单品');
        let category='全部';const tabs=node('div','y-wardrobe-tabs');tabs.setAttribute('aria-label','单品分类');
        const categories=results[2].status==='fulfilled'?results[2].value?.list||[]:[];
        for(const name of ['全部',...new Set(categories.map(c=>c.class_name).filter(Boolean))]){const tab=button(name,()=>{category=name;tabs.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b===tab)));render();},'');tab.setAttribute('aria-pressed',String(name==='全部'));tabs.append(tab);}
        const render=()=>{const matches=rows.filter(p=>(category==='全部'||p.class_name===category||categories.some(c=>c.class_name===category&&(c.list||[]).some(item=>item===p)))&&[p.title,p.name,p.product_name,p.brand_name].join(' ').includes(search.value.trim()));rail.replaceChildren(...matches.map(productCard));if(!matches.length)rail.append(node('p','state','没有找到这件，换个关键词试试。'));};
        search.oninput=render;render();section.append(search,tabs,rail);
        if(selected&&rows.length<(data.pagination?.total??rows.length)){let page=1;const more=button('加载更多',async()=>{more.disabled=true;try{const next=await api('closet-items',page+1,{wardrobe_id:selected.id});if(epoch!==state.epoch||requestVersion!==state.wardrobeVersion)return;page++;const seen=new Set(rows.map(p=>String(p.user_product_id)));const added=(next.list||[]).filter(p=>!seen.has(String(p.user_product_id)));rows.push(...added);state.products=rows;render();if(!added.length||rows.length>=(next.pagination?.total??rows.length))more.remove();}catch(e){toast(e.message);}finally{more.disabled=false;}},'load-more pill');section.append(more);} }
      target.append(section);
    } else if (i === 1) {
      const section = wardrobeSection(names[i], data.page?.total ?? rows.length, () => openDetail('create-closet'), '＋ 创建衣橱');
      if (!rows.length) { const box = node('div', 'section-empty'); box.append(document.documentElement.dataset.appDesign==='yijian'?emptyArt('wardrobe'):picture(ASSETS + 'profile_outfit_empty.png'), node('p', '', '给常穿的衣服，留一个小天地'), button('创建衣橱', () => openDetail('create-closet'))); section.append(box); }
      else { const rail = node('div', 'product-rail'); rows.forEach(c => { const b = button('', () => { const body = node('div', 'detail-body'); body.append(node('p', '', '此衣橱的完整编辑与分类管理请在 App 中打开。')); detail(c.name || c.wardrobes_name || '分类衣橱', body); }, 'product'); b.append(picture(c.cover_image || c.cover, c.name || '分类衣橱'), node('span', '', c.name || c.wardrobes_name || '分类衣橱')); rail.append(b); }); section.append(rail); } target.append(section);
    } else rows.forEach(c => { const section = wardrobeSection(c.class_name || '单品分类', c.count, () => showProducts(c.list || [], c.class_name), '查看 ›'); const rail = node('div', 'product-rail'); (c.list || []).forEach(p => rail.append(productCard(p))); section.append(rail); target.append(section); });
  });
}
async function loadProfile() {
  $('balance').textContent='–';
  readAvailablePoints().catch(e=>{if(e.name!=='AbortError')$('balance').textContent='暂未查到';});
  try { const p = await api('profile'); $('account-name').textContent = p.nickname || p.nick_name || '我的账号'; const src = safeURL(p.image_url || p.avatar || ''); if (src && (p.image_url || p.avatar)) $('account-avatar').src = src; window.dispatchEvent(new CustomEvent('yijian-account-loaded',{detail:p})); }
  catch (e) { if(e.name !== 'AbortError')window.dispatchEvent(new Event('yijian-account-error')); if (e.name !== 'AbortError' && !e.login) toast(e.message); }
}
async function loadMemories() {
  const card = document.querySelector('.memory-card'), copy = card.querySelector('.memory-copy'), pill = card.querySelector('.pill');
  if(document.documentElement.dataset.appDesign==='yijian'){
    card.onclick=()=>openAgent('memory');pill.textContent='翻开手记';pill.hidden=false;
    const session=readSession(),epoch=state.epoch;
    if(!session?.access_token){copy.textContent='记下穿衣喜好，\n让每一次搭配更贴近你。';return;}
    copy.textContent='正在翻开手记…';
    try{const response=await fetch('/stylist-api/memories',{headers:{Authorization:'Bearer '+session.access_token},cache:'no-store',signal:state.controller.signal});const book=await response.json();if(epoch!==state.epoch)return;if(!response.ok)throw Error(book.message||'手记暂未读取，请稍后重试。');if(!Array.isArray(book.entries))throw Error('手记格式异常，请稍后重试。');copy.replaceChildren();const entries=book.entries.filter(x=>x.category==='穿衣习惯'&&typeof x.content==='string'&&x.content.trim());if(entries.length)entries.slice(0,2).forEach(x=>copy.append(node('span','memory-line',x.content)));else copy.textContent='把穿衣喜好记在这里，\n以后也可以慢慢补充。';}
    catch(error){if(error.name==='AbortError'||epoch!==state.epoch)return;copy.textContent='打开手记，\n继续记录你的穿衣喜好。';window.PreviewMessage.notify(error.message);}
    return;
  }
  copy.textContent = '正在加载记忆…'; pill.hidden = true;
  try {
    const data = await api('memories');
    const items = (data.items || []).filter(x => x.status === 'active' && x.memory_id);
    copy.replaceChildren();
    if (items.length) { items.slice(0, 3).forEach(x => copy.append(node('span', 'memory-line', x.content || x.value || ''))); }
    else copy.textContent = document.documentElement.dataset.appDesign === 'yijian'
      ? '把喜好一点点记下，\n让日常的搭配更贴近你。'
      : '对齐审美偏好，让她比上一秒更懂你\n在这里，塑造一个比谁都懂你的私人造型师。';
    pill.hidden = items.length > 0;
    card.onclick = () => { const body = node('div', 'detail-body'); if (items.length) items.forEach(x => body.append(node('p', 'memory-detail', x.content || x.value || ''))); else body.append(node('p', '', '还没有记忆')); body.append(node('p', 'offline-note', '这里展示 App 中的记忆。爱搭衣橱的对话手记保留在原有页面。'), button('打开爱搭衣橱手记', () => openAgent('memory'))); detail('Memory', body); };
  } catch (e) { if (e.name === 'AbortError') return; copy.textContent = e.login ? '连接衣橱后查看记忆' : '记忆暂不可用，点击重试'; card.onclick = () => e.login ? openAgent('login') : loadMemories(); }
}
let detailOpener;
function detail(title, content) { detailOpener = document.activeElement; setCreate(false); $('detail-title').textContent = title; $('detail-content').replaceChildren(content); $('detail-page').hidden = false; $('detail-page').scrollTop = 0; backgroundInert(true); document.querySelector('.floating-bar').inert = true; ($('detail-content').querySelector('.sku-center-back') || $('detail-back')).focus(); const id = ++detailSerial; detailHistory.set(id, {title, content, opener: detailOpener}); if (detailHistory.size > 30) detailHistory.delete(detailHistory.keys().next().value); history.pushState({tab: state.tab, view: 'detail', id}, '', `#${state.tab}/detail`); }
function closeDetail() { $('detail-page').hidden = true; backgroundInert(false); document.querySelector('.floating-bar').inert = false; if (detailOpener?.isConnected) detailOpener.focus(); }
function openImage(title, src, description, discussion = null) { const body = node('div', 'detail-body'); body.append(picture(src, title), node('h3', '', title)); if (description) body.append(node('p', '', description)); if (discussion) body.append(subjectChatButton('discussion', discussion, {button, openAgent, readSession})); detail(title, body); }
function showProducts(products, title = '衣橱单品') { const wrap = node('div'), search = node('input', 'search'), grid = node('div', 'product-grid'); search.type = 'search'; search.placeholder = '搜索当前列表'; search.setAttribute('aria-label', '搜索当前列表'); const render = () => { grid.replaceChildren(); products.filter(p => JSON.stringify([p.title, p.name, p.product_name, p.brand_name]).includes(search.value)).forEach(p => grid.append(productCard(p))); }; search.oninput = render; render(); wrap.append(search, grid); detail(title, wrap); }
window.addEventListener('yijian-points-earn-open',()=>openDetail('earn-points'));
const details = { 'earn-points':'积分获取', 'generation-records':'生成记录', 'my-outfits':'我的搭配', statistics: '衣橱小记', ootd: 'OOTD', diy: 'DIY搭配', products: '逛逛新品', membership: '会员与积分', orders: '订单记录', messages: '我的消息', feedback: '意见反馈', contact: '联系我们', settings: '设置', import: '电商导入', 'create-closet': '创建衣橱' };
function openDetail(key) {
  const content = node('div', 'detail-body');
  if (key === 'companion') { detail('我的穿搭助理', companionPage(openAgent)); return; }
  if (key === 'settings') {
    content.className = 'detail-menu settings-notebook';
    const intro=node('div','settings-intro');intro.append(node('span','settings-eyebrow','MAKE YOURSELF AT HOME'),node('h3','','让这里，更像你的爱搭衣橱。'));if(document.documentElement.dataset.appDesign!=='yijian')intro.append(node('p','','怎样称呼、怎样相处，都听你的。'));content.append(intro);
    const paths={identity:'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8M5 21v-2a7 7 0 0 1 14 0v2',preference:'m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9Z',memory:'M4 4h6a3 3 0 0 1 3 3v14a5 5 0 0 0-5-3H4Zm16 0h-4a3 3 0 0 0-3 3v14a5 5 0 0 1 5-3h2Z',account:'M14 4h6v16h-6M3 12h12m-4-4 4 4-4 4'};
    const groups=[['关于彼此',[['称呼与形象','你的称呼与性别 · 助理名字与模样','settings','identity'],['了解我','穿搭喜好与聊天习惯','preferences','preference'],['我们的手记','查看与整理已保存的偏好','memory','memory']]],['账号',[['登录 / 切换账号','连接你的个人衣橱','login','account']]]];
    groups.forEach(([label,rows])=>{if(label==='关于彼此'&&document.documentElement.dataset.appDesign==='yijian')return;const group=node('section','settings-group');group.append(node('h4','',label));const card=node('div','settings-card');rows.forEach(([title,description,action,icon])=>{if(action==='memory'&&document.documentElement.dataset.appDesign==='yijian')return;const row=button('',()=>openAgent(action),'settings-row');const mark=node('span','settings-icon');mark.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="'+paths[icon]+'"/></svg>';const text=node('span','settings-row-copy');text.append(node('strong','',title),node('small','',description));row.append(mark,text,node('span','settings-chevron','›'));card.append(row);});group.append(card);content.append(group);});
    content.append(button('退出登录',()=>openAgent('logout'),'settings-logout'),node('p','settings-footnote','按自己的节奏，留下喜欢的设置。'));
  }
  else if(key==='earn-points'){detail(details[key],pointsEarningPage({node,button,openAgent,openPurchase:group=>detail(details.membership,skuDetail({group})),readSession,signal:state.controller.signal}));return;}
  else if(['generation-records','my-outfits'].includes(key)){detail(details[key],collectionPage(key,{node,button,detail,openImage,openAgent,readSession,signal:state.controller.signal}));return;}
  else if (['contact','feedback','messages','orders'].includes(key)) { detail(details[key], profilePage(key,{node,button,detail,openAgent,readSession,signal:state.controller.signal})); return; }
  else if(key==='membership'&&document.documentElement.dataset.appDesign==='yijian'){detail(details[key],skuDetail());return;}
  else if(document.documentElement.dataset.appDesign==='yijian'){content.className='y-unavailable';content.append(node('span','y-unavailable-mark','✧'),node('h3','',details[key]||'此功能'),node('p','','这项功能暂未开放，请先在 AI Closet App 中使用。'));if(key==='diy')content.append(button('和助理聊聊搭配',()=>openAgent('chat'),'y-service-primary'));}
  else { content.append(picture(ASSETS + 'profile_outfit_empty.png')); content.lastChild.className = 'blank-art'; content.append(node('p', 'offline-note', `${details[key] || '此功能'}尚未接入当前 Web，请在 AI Closet App 中使用。`)); if (key === 'diy') content.append(button('让爱搭衣橱帮我搭配', () => openAgent('chat'))); }
  detail(details[key] || '详情', content);
}
document.addEventListener('yijian-purchase-request',e=>{
  const options=e.detail||{},token=readSession()?.access_token;
  if(!token||options.ownerToken!==token||!['member','points'].includes(options.group))return;
  detail(details.membership,skuDetail({group:options.group,requiredPoints:options.requiredPoints}));
});
const agentActions = { login: 'login-open', history: 'mobile-history', upload: 'upload-open', twins: 'twin-open', records: 'journey-records-open', memory: 'memory-open', settings: 'companion-open', preferences: 'preferences-open', checkin: 'checkin-open', logout: 'logout' };
let agentReady, agentOpener;
async function openAgent(action = 'chat', subjectEntry = null) {
  const owner = readSession()?.access_token;
  if(document.documentElement.dataset.appDesign==='yijian'){
    agentOpener=document.activeElement;setCreate(false);
    try{
      await mountAgent();
      if (subjectEntry && readSession()?.access_token !== owner) return;
      const chat=action==='chat'&&!!readSession()?.access_token;
      if(chat){closeDetail();placeIntegratedAgent(true);$('agent-page').hidden=false;backgroundInert(true);document.querySelector('.floating-bar').inert=true;if(history.state?.view!=='agent')history.pushState({tab:state.tab,view:'agent'},'',`#${state.tab}/agent`);}
      else if($('agent-page').hidden)placeIntegratedAgent(false);
      await openIntegratedAgent(action, subjectEntry);
    }catch(error){window.PreviewMessage.notify(error.message||'页面暂时没能加载，请刷新后重试。');}
    return;
  }
  agentOpener = document.activeElement; setCreate(false); closeDetail(); $('agent-page').hidden = false; backgroundInert(true); document.querySelector('.floating-bar').inert = true; if (history.state?.view !== 'agent') history.pushState({tab: state.tab, view: 'agent'}, '', `#${state.tab}/agent`);
  const frame = $('agent-frame');
  if (!agentReady) agentReady = new Promise(resolve => { frame.onload = resolve; frame.src = '/static/index.html'; });
  await agentReady;
  if (subjectEntry) {
    if (readSession()?.access_token !== owner || $('agent-page').hidden) return;
    await frame.contentWindow.openSubjectConversation(subjectEntry); return;
  }
  if ($('agent-page').hidden) return;
  const id = agentActions[action]; if (id) frame.contentDocument.getElementById(id)?.click(); else frame.contentDocument.getElementById('message')?.focus();
}
function closeAgent() { if(document.documentElement.dataset.appDesign==='yijian'){closeIntegratedAgent();placeIntegratedAgent(false);} $('agent-page').hidden = true; backgroundInert(false); document.querySelector('.floating-bar').inert = false; syncAccount(); if (agentOpener?.isConnected) agentOpener.focus(); }
function syncAccount() {
  const current = sessionStorage.getItem(KEY) || '';
  if (current === state.session) return;
  state.session = current; window.dispatchEvent(new Event('yijian-account-reset')); detailHistory.clear(); state.epoch++; state.controller.abort(); state.controller = new AbortController(); state.rows = []; state.products = []; state.loading = false;
  state.activeCloset=null;$('home-feed').replaceChildren(); $('wardrobe-sections').replaceChildren(); $('detail-content').replaceChildren(); $('account-name').textContent = '未登录'; $('account-avatar').src = ASSETS + 'user_avatar_default_icon.png'; $('balance').textContent = '–'; document.querySelector('.memory-copy').textContent = ''; document.querySelector('.memory-card').onclick = () => openAgent('login');
  if (state.tab === 'home') loadFeed(); else if (state.tab === 'wardrobe') loadWardrobe(); else { loadProfile(); loadMemories(); }
}
$('create-toggle').onclick = () => setCreate($('create-overlay').hidden);
for (const b of document.querySelectorAll('[data-close-create]')) b.onclick = () => setCreate(false);
for (const b of document.querySelectorAll('[data-tab]')) b.onclick = () => selectTab(b.dataset.tab);
for (const b of document.querySelectorAll('[data-feed]')) b.onclick = () => { state.feed = b.dataset.feed; document.querySelectorAll('[data-feed]').forEach(x => x.setAttribute('aria-selected', String(x === b))); loadFeed(); };
for (const b of document.querySelectorAll('[data-agent]')) b.onclick = () => openAgent(b.dataset.agent);
for (const b of document.querySelectorAll('[data-detail]')) b.onclick = () => openDetail(b.dataset.detail);
for (const b of document.querySelectorAll('[data-show]')) b.onclick = () => { state.feed = b.dataset.show; document.querySelectorAll('[data-feed]').forEach(x => x.setAttribute('aria-selected', String(x.dataset.feed === state.feed))); selectTab('home'); };
$('detail-back').onclick = () => history.back(); $('agent-back').onclick = () => history.back(); $('agent-account').onclick = () => openAgent(document.documentElement.dataset.appDesign==='yijian'?'history':'login');
if(document.documentElement.dataset.appDesign==='yijian'){$('agent-back').textContent='‹';$('agent-back').setAttribute('aria-label','返回');$('agent-account').innerHTML='<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>';$('agent-account').setAttribute('aria-label','聊过的日常');$('agent-account').title='聊过的日常';$('agent-account').setAttribute('aria-haspopup','dialog');}
window.addEventListener('popstate', event => {
  closeDetail(); closeAgent(); selectTab(event.state?.tab || location.hash.slice(1).split('/')[0] || 'home', false);
  const record = event.state?.view === 'detail' && detailHistory.get(event.state.id);
  if (record) { if(record.content.reopen)record.content=record.content.reopen();$('detail-title').textContent = record.title; $('detail-content').replaceChildren(record.content); $('detail-page').hidden = false; detailOpener = record.opener; backgroundInert(true); document.querySelector('.floating-bar').inert = true; ($('detail-content').querySelector('.sku-center-back') || $('detail-back')).focus(); }
  else if (event.state?.view === 'agent') { if(document.documentElement.dataset.appDesign==='yijian')placeIntegratedAgent(true); $('agent-page').hidden = false; backgroundInert(true); document.querySelector('.floating-bar').inert = true; }
});
window.addEventListener('storage', e => { if (e.key === KEY) syncAccount(); });
window.addEventListener('focus', syncAccount);
document.addEventListener('yijian-agent-mounted',()=>{const root=document.getElementById('yijian-agent-root');root.addEventListener('click',()=>setTimeout(syncAccount,0));root.addEventListener('submit',()=>setTimeout(syncAccount,0));});
window.addEventListener('companion-profile-change',()=>syncAccount());
window.addEventListener('yijian-session-change',syncAccount);
window.addEventListener('yijian-overlay-closed',()=>{if(agentOpener?.isConnected)agentOpener.focus();if(state.tab==='profile')loadMemories();});
window.addEventListener('yijian-agent-open',e=>openAgent(e.detail||'chat'));
window.addEventListener('yijian-companion-open',()=>openDetail('companion'));
window.addEventListener('yijian-checkin-claimed',()=>{if(state.tab==='profile')loadProfile();});
document.addEventListener('keydown', e => {
  if(e.key==='Escape'&&document.querySelector('#yijian-agent-root dialog[open],dialog[data-app-dialog][open]'))return;
  if (e.key === 'Escape') { if (!$('create-overlay').hidden) setCreate(false); else if (!$('agent-page').hidden || !$('detail-page').hidden) history.back(); }
  if (e.key === 'Tab' && !$('create-overlay').hidden) { const list = [...$('create-overlay').querySelectorAll('button'), $('create-toggle')]; const first = list[0], last = list.at(-1); if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); } }
});
state.session = sessionStorage.getItem(KEY) || ''; selectTab(location.hash.slice(1).split('/')[0] || 'home', false);

if(document.documentElement.dataset.appDesign==='yijian'&&location.hash.endsWith('/agent'))openAgent('chat');

if(document.documentElement.dataset.appDesign==='yijian'&&new URLSearchParams(location.search).get('start')==='upload'){
 const url=new URL(location.href);url.searchParams.delete('start');history.replaceState(history.state,'',url);openAgent('upload');
}

// Local UI review is explicit; no session or balance is synthesized.
function mountPaymentEffects(){
 if(document.documentElement.dataset.appDesign!=='yijian')return;
 if(paymentDemoEnabled())document.documentElement.dataset.paymentDemo='true';
 mountPaymentDemo({
  ensureAgent:async()=>{await mountAgent();await window.CompanionSettings?.ready;},
  showAgent:async()=>{
   setCreate(false);closeDetail();placeIntegratedAgent(true);$('agent-page').hidden=false;backgroundInert(true);document.querySelector('.floating-bar').inert=true;
   if(history.state?.view!=='agent')history.pushState({tab:state.tab,view:'agent'},'',`#${state.tab}/agent`);
  },
  showTask:key=>openDetail(key)
 });
}
if(document.readyState==='complete')mountPaymentEffects();else window.addEventListener('load',mountPaymentEffects,{once:true});

window.addEventListener('yijian-points-loaded',e=>{if(e.detail.ownerToken===readSession()?.access_token)$('balance').textContent=new Intl.NumberFormat('en-US',{maximumFractionDigits:20}).format(e.detail.total_available);});
