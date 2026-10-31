'use strict';
// Flat lays use real wardrobe photos. Layering is presentation, never a try-on.
(() => {
  const make = (tag, cls, text) => {
    const node = document.createElement(tag); if (cls) node.className = cls;
    if (text != null) node.textContent = text; return node;
  };
  const labels = { top: '上装', outer: '外搭', bottom: '下装', dress: '连衣裙', shoes: '鞋履', accessory: '配饰', other: '单品' };
  function name(item) { return item.title || [item.color, item.secondary_class_name || item.class_name].filter(Boolean).join(' · ') || '衣橱单品'; }
  function safe(value) { const url = String(value || '').replace(/^http:/i, 'https:'); return /^https:\/\//i.test(url) || /^\/static\/[a-z0-9_./-]+$/i.test(url) ? url : ''; }
  function role(item) {
    if (labels[item.slot]) return item.slot;
    const text = [item.secondary_class_name, item.class_name].filter(Boolean).join(' ');
    if (/外套|大衣|风衣|夹克|羽绒|西装/.test(text)) return 'outer';
    if (/连衣裙|连体/.test(text)) return 'dress';
    if (/裤|半身裙/.test(text)) return 'bottom';
    if (/鞋|靴/.test(text)) return 'shoes';
    if (/包|帽|围巾|首饰|项链|腰带|眼镜|手套|袜/.test(text)) return 'accessory';
    if (/衫|上衣|背心/.test(text)) return 'top';
    return 'other';
  }
  function layout(items) {
    const grouped = {};
    items.forEach((item, index) => { const kind = role(item); (grouped[kind] ||= []).push(index); });
    const weight = item => {
      const text = [item.secondary_class_name, item.class_name, item.title].filter(Boolean).join(' ');
      if (role(item) === 'outer') return /大衣|风衣|羽绒|棉服/.test(text) ? 30 : /夹克|外套/.test(text) ? 20 : 10;
      return /毛衣|卫衣|针织|开衫/.test(text) ? 20 : 10;
    };
    Object.values(grouped).forEach(group => group.sort((a, b) => weight(items[a]) - weight(items[b])));
    return items.map((item, index) => {
      const kind = role(item), group = grouped[kind], n = group.indexOf(index), count = group.length;
      // Slight offsets expose the inner garment while keeping outerwear above it.
      const hasOuter = !!grouped.outer, base = {
        top: [hasOuter ? 37 : 46, 23, 43, 39, 20], outer: [57, 27, 47, 49, 40],
        bottom: [44, 64, 39, 49, 10], dress: [45, 45, 49, 73, 15],
        shoes: [48, 91, 40, 17, 50], accessory: [84, 50, 23, 22, 80], other: [16, 73, 22, 22, 60],
      }[kind];
      const [x,y,w,h,z] = base;
      if (kind === 'accessory' || kind === 'other') {
        const columns = count > 4 ? 2 : 1, rows = Math.ceil(count / columns);
        return { kind, x: kind === 'accessory' ? (columns === 2 ? 77 + n % 2 * 14 : 84) : 15,
          y: 16 + Math.floor(n / columns) * (68 / Math.max(rows, 1)), w: columns === 2 ? 15 : 23,
          h: Math.min(21, 64 / rows), z: z + n };
      }
      const delta = (n - (count - 1) / 2) * Math.min(12, 30 / Math.max(count - 1, 1));
      return { kind, x: x + delta, y: y + n * 2, w: w * (count > 2 ? .84 : 1), h, z: z + n };
    });
  }
  function photo(item, original = false, failed) {
    const urls = (original ? [item.original_image, item.cutout_image] : [item.cutout_image, item.original_image]).map(safe).filter(Boolean);
    const image = make('img'); image.alt = name(item); image.referrerPolicy = 'no-referrer'; image.draggable = false;
    if (!urls.length) return make('span', 'outfit-missing', '暂无图片');
    let attempt = 0;
    image.onerror = () => {
      attempt++;
      if (attempt < urls.length) { image.src = urls[attempt]; return; }
      image.replaceWith(make('span', 'outfit-missing', '图片暂不可用')); failed?.();
    };
    image.src = urls[0]; return image;
  }

  function board(items, select, active = -1, imageUrl = null) {
    const root = make('div', 'outfit-flatlay'); root.setAttribute('aria-label', '衣橱已选单品组合');
    if(imageUrl){const final=make('img','outfit-final-image');final.src=imageUrl;final.alt='衣橱单品组合图';root.append(final);}
    const positions = layout(items);
    items.forEach((item, index) => {
      const p = positions[index], button = make('button', 'outfit-piece'); button.type = 'button';
      button.dataset.kind = p.kind; button.dataset.index = index;
      button.setAttribute('aria-label', `查看${name(item)}详情`); button.setAttribute('aria-pressed', String(active === index));
      for (const key of ['x','y','w','h','z']) button.style.setProperty('--' + key, p[key] + (key === 'z' ? '' : '%'));
      if(!imageUrl)button.append(photo(item)); else button.classList.add('outfit-hotspot'); button.onclick = () => select(index); root.append(button);
    });
    return root;
  }
  let modal = null, opener = null;
  function open(look, trigger, initial = 0, result = null) {
    modal?.close();
    const items = look.items || []; if (!items.length) return;
    opener = trigger; const dialog = make('dialog', 'outfit-detail'); modal = dialog;
    dialog.setAttribute('aria-label', `${look.title || '这套搭配'} · 单品详情`);
    const heading = make('div', 'outfit-detail-heading');
    const title = make('div'); title.append(make('span', 'outfit-kicker', look.wardrobe_complete === false ? '这次选中的衣橱单品' : '衣橱里的这一套'), make('h2', '', look.title || '搭配详情'));
    const close = make('button', 'subtle', '关闭 ×'); close.type = 'button'; close.setAttribute('aria-label', '关闭搭配详情'); close.onclick = () => dialog.close();
    heading.append(title, close);
    const content = make('div', 'outfit-detail-content'), overview = make('section', 'outfit-overview');
    const detail = make('section', 'outfit-single'); detail.setAttribute('aria-live', 'polite');
    const strip = make('div', 'outfit-thumbnails'); strip.setAttribute('role', 'group'); strip.setAttribute('aria-label', '选择要查看的单品');
    const canvas = board(items, select, -1, result?.image_url); overview.append(canvas, make('p', 'outfit-help', '轻点单品，看看它的细节'));
    items.forEach((item, i) => {
      const button = make('button', 'outfit-thumbnail'); button.type = 'button'; button.setAttribute('aria-label', `查看${name(item)}`);
      button.append(photo(item), make('span', '', labels[role(item)])); button.onclick = () => select(i); strip.append(button);
    });
    content.append(overview, detail); dialog.append(heading, content, strip); document.body.append(dialog);
    let selected = 0;
    function select(index) {
      selected = index; const item = items[index];
      canvas.querySelectorAll('.outfit-piece').forEach((button, i) => button.setAttribute('aria-pressed', String(index === i)));
      [...strip.children].forEach((button, i) => button.setAttribute('aria-pressed', String(index === i)));
      detail.replaceChildren();
      const imageStage = make('button', 'outfit-original'); imageStage.type = 'button'; imageStage.setAttribute('aria-label', '预览单品大图');
      const image = photo(item, true); imageStage.append(image);
      imageStage.disabled = !safe(item.original_image || item.cutout_image);
      imageStage.onclick = () => window.ProductPreview?.open(
        items.map(piece => ({src: safe(piece.original_image || piece.cutout_image), alt: name(piece)})), index, imageStage);
      const info = make('div', 'outfit-item-info');
      info.append(make('span', 'outfit-kicker', `${index + 1} / ${items.length} · ${item.source === 'user' ? '个人衣橱' : '衣物单品'}`), make('h3', '', name(item)));
      const attrs = make('dl', 'outfit-attributes');
      for (const [label, value] of [['分类', item.secondary_class_name || item.class_name], ['颜色', item.color], ['材质', item.material]]) {
        if (value) attrs.append(make('dt', '', label), make('dd', '', value));
      }
      if (attrs.childNodes.length) info.append(attrs);
      if (item.description) info.append(make('p', 'outfit-description', item.description));
      if (item.warnings?.length) info.append(make('p', 'outfit-description', item.warnings.join('；')));
      const nav = make('div', 'outfit-item-nav');
      for (const [label, delta] of [['← 上一件', -1], ['下一件 →', 1]]) {
        const button = make('button', 'subtle', label); button.type = 'button';
        button.disabled = index + delta < 0 || index + delta >= items.length; button.onclick = () => select(index + delta); nav.append(button);
      }
      info.append(nav); detail.append(imageStage, info);
    }
    dialog.addEventListener('keydown', event => {
      if (['ArrowLeft','ArrowRight'].includes(event.key)) {
        const next = selected + (event.key === 'ArrowLeft' ? -1 : 1);
        if (next >= 0 && next < items.length) { event.preventDefault(); select(next); }
      }
    });
    dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener('close', () => {
      window.ProductPreview?.close();
      document.documentElement.classList.remove('outfit-detail-open'); dialog.remove();
      if (modal === dialog) modal = null;
      if (opener?.isConnected) opener.focus({ preventScroll: true }); opener = null;
    }, { once: true });
    select(initial); dialog.showModal(); document.documentElement.classList.add('outfit-detail-open'); close.focus();
  }
  const cards=new Set();
  function create(look,ref=null) {
    const root=make('section','outfit-composition'),stage=make('div','outfit-board-stage');
    const footer=make('div','outfit-board-footer'),text=make('div');
    const partial = look.wardrobe_complete === false;
    text.append(make('span','outfit-kicker',`${look.items.length} 件${partial ? '衣橱单品 · 部分搭配' : '单品 · 一起穿'}`),
      make('p','',partial ? '图片仅展示衣橱已选单品，其余为文字参考。' : '把喜欢的衣服，放在一起看看。'));
    const actions=make('div','outfit-board-actions');
    const expand=make('button','outfit-expand','展开看看 ↗'),download=make('button','subtle','下载');
    expand.type=download.type='button';actions.append(download,expand);footer.append(text,actions);root.append(stage,footer);
    let sequence=0,started=false,result=null;
    const render=async(retry=false)=>{
      started=true;const current=++sequence;result=null;expand.disabled=download.disabled=true;
      const placeholder=make('div','outfit-placeholder');placeholder.setAttribute('role','status');placeholder.setAttribute('aria-label','搭配图准备中');
      const dots=make('span','outfit-preparing-dots');dots.setAttribute('aria-hidden','true');dots.textContent='· · ·';placeholder.append(dots);stage.replaceChildren(placeholder);
      try{
        const ready=await window.OutfitImages.get(look,ref,retry);
        if(current!==sequence||!root.isConnected)return;
        // Show the saved image atomically after its bytes have loaded.
        const image=new Image();image.src=ready.image_url;
        await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(Error('搭配图暂时无法加载，请重试。'));if(image.complete&&image.naturalWidth)resolve();});
        if(current!==sequence||!root.isConnected)return;
        result=ready;stage.replaceChildren(board(look.items,index=>open(look,expand,index,result),-1,result.image_url));expand.disabled=download.disabled=false;
      }catch(error){
        if(current!==sequence||!root.isConnected||error.message==='cancelled')return;
        const state=make('div','outfit-placeholder');state.append(make('p','','搭配图暂未准备好'));
        const again=make('button','subtle','重试');again.type='button';again.onclick=()=>render(true);state.append(again);stage.replaceChildren(state);
        window.CompanionSettings?.notify(error.message||'搭配图暂时没有保存成功，请重试。');
      }
    };
    expand.onclick=()=>{if(result)open(look,expand,0,result)};
    download.onclick=async()=>{if(!result)return;download.disabled=true;try{await OutfitImages.download(result)}catch(error){window.CompanionSettings?.notify(error.message||'下载未完成，请重试。')}finally{download.disabled=false}};
    const entry={root,render,started:()=>started};cards.add(entry);
    if(typeof IntersectionObserver==='function'){
      const observer=new IntersectionObserver(entries=>{if(entries.some(x=>x.isIntersecting)){observer.disconnect();render();}},{rootMargin:'120px'});observer.observe(root);
    }else queueMicrotask(()=>{if(root.isConnected)render()});
    return root;
  }

  window.OutfitBoard = { create, layout, role, close: () => modal?.close() };
  window.addEventListener('outfit-images-owner-change',event=>{
    if(!event.detail)return;
    for(const card of cards){if(!card.root.isConnected)cards.delete(card);else if(card.started())card.render();}
  });
  window.addEventListener('companion-profile-change', event => { if (!event.detail) modal?.close(); });
})();
