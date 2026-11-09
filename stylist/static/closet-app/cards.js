// Layout mirrors HomeFittingAlbumCardView and InspirationCardCell.
export function albumCard(item, { node, button, picture, openImage, assets }) {
  const products = (item.product_images || []).filter(p => p.image_url);
  const multiple = products.length > 1;
  const title = item.title?.trim() || '试衣造型';
  const card = node('article', `album-card ${multiple ? 'album-multiple' : 'album-single'}`);
  const tap = button('', () => openImage(title, item.fitting_image_url, item.description, {title, description:item.description}), 'album-tap');
  tap.setAttribute('aria-label', `查看${title}`);
  const stage = node('div', 'album-stage');
  const result = picture(item.fitting_image_url, '试衣效果图'); result.classList.add('album-result');
  stage.append(result);
  const garments = node('div', 'album-garments');
  garments.style.setProperty('--tile-count', products.length || 1);
  for (const p of products) {
    const tile = node('div', 'album-tile'); tile.append(picture(p.image_url, p.title || '单品')); garments.append(tile);
  }
  if (products.length) stage.append(garments);
  const copy = node('div', 'album-copy'), meta = node('div', 'album-metadata');
  const weather = item.weather;
  const forecast = [weather?.condition, weather?.temp != null && weather.temp !== '' ? `${weather.temp}°` : ''].filter(Boolean).join(' ');
  const context = [item.context_text, forecast].filter(Boolean).join(' · ');
  const source = (item.source_type === 'first_look' || item.product_count === 0
    ? [item.source_label, item.outfit_type_text] : [item.outfit_type_text, item.source_label]).find(x => x?.trim()) || '试衣';
  for (const [text, kind] of [[context, 'context'], [source, 'source']]) {
    if (!text) continue;
    const row = node('span', `album-meta-${kind}`); row.append(picture(`${assets}home_album_${kind}.svg`), node('span', '', text)); meta.append(row);
  }
  if (meta.childElementCount) copy.append(meta);
  copy.append(node('h2', '', title));
  if (item.description) copy.append(node('p', '', item.description));
  if (document.documentElement.dataset.appDesign === 'yijian') {
    const chapter = node('div', 'y-diary-heading');
    chapter.append(node('span', 'y-diary-mark', '✧'), node('span', 'y-diary-label', 'OUTFIT DIARY · 穿搭手记'));
    chapter.firstChild.setAttribute('aria-hidden', 'true');
    const date = typeof item.finished_at === 'string' && item.finished_at.match(/^(\d{4})-(\d{2})-(\d{2})(?:T| |$)/);
    if (date) chapter.append(node('time', 'y-diary-date', `${date[2]}.${date[3]}`));
    const ending = node('div', 'y-diary-ending');
    ending.append(node('span', '', '把喜欢的自己，留在这一页。'), node('span', 'y-diary-open', '翻开这页 ↗'));
    tap.append(chapter, stage, copy, ending);
  } else tap.append(stage, copy);
  card.append(tap); return card;
}

export function inspirationCard(item, { node, button, picture, openImage }) {
  const src = item.cover_image || item.canvas_image || item.canvas_info?.canvas_image;
  const card = button('', () => openImage(item.title || '搭配灵感', src, item.summary, {title:item.title || '搭配灵感',description:item.summary}), 'inspiration-card');
  card.setAttribute('aria-label', item.title || '查看搭配灵感');
  const photo = picture(src, item.title || '搭配灵感');
  // A cover without dimensions is square in iOS; never force it into a 3:4 crop.
  const ratio = Number(item.cover_width) > 0 && Number(item.cover_height) > 0 ? Number(item.cover_height) / Number(item.cover_width) : 1;
  photo.style.aspectRatio = `1 / ${ratio}`;
  card.append(photo);
  if (item.title || item.summary) {
    const copy = node('div', 'inspiration-copy');
    if (item.title) copy.append(node('h2', '', item.title));
    if (item.summary) copy.append(node('p', '', item.summary));
    card.append(copy);
  }
  return card;
}

// Keep source/keyboard order while placing each new card in the shorter column.
export function observeWaterfall(grid) {
  const layout = () => {
    const width = grid.clientWidth;
    if (!width) return;
    const gap = 10, tileWidth = (width - gap) / 2, heights = [0, 0];
    for (const card of grid.children) {
      card.style.width = `${tileWidth}px`;
      const column = heights[0] <= heights[1] ? 0 : 1;
      card.style.transform = `translate(${column * (tileWidth + gap)}px, ${heights[column]}px)`;
      heights[column] += card.offsetHeight + 12;
    }
    grid.style.height = `${Math.max(0, ...heights) - (grid.childElementCount ? 12 : 0)}px`;
  };
  const observer = new ResizeObserver(layout);
  observer.observe(grid);
  for (const card of grid.children) observer.observe(card);
  layout();
  return () => observer.disconnect();
}
