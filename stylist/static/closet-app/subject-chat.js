// Detail links carry references only; the authenticated Agent resolves their contents.
export function subjectChatButton(kind, item, {button, openAgent, readSession}) {
  const owner = readSession()?.access_token;
  const product = kind === 'product';
  const discussion = kind === 'discussion';
  // Raw wardrobe APIs return both user_product_id and system product_id.
  const id = product ? String(item.user_product_id ?? '') : Number(item.outfit_id);
  const valid = discussion ? !!String(item.title || item.description || '').trim()
    : product ? /^[1-9][0-9]{0,19}$/.test(id) && (typeof item.user_product_id !== 'number' || Number.isSafeInteger(item.user_product_id))
    : Number.isSafeInteger(id) && id > 0 && Number(item.outfit_id_type) === 2;
  const entry = discussion ? {discussion: {title: String(item.title || '').slice(0,200), description: String(item.description || '').slice(0,2000)}}
    : product ? {subject_product: {source: 'user', product_id: id}}
    : {subject_outfit: {source: 'user', outfit_id: id}};
  const control = button(product ? '帮我查看下这件' : '帮我查看下搭配', async () => {
    if (!valid || control.disabled) return;
    if (!owner) { await openAgent('login'); return; }
    if (readSession()?.access_token !== owner) return;
    control.disabled = true;
    try { await openAgent('chat', entry); }
    finally { if (control.isConnected) control.disabled = !valid; }
  }, 'y-service-primary subject-chat-entry');
  control.disabled = !valid;
  if (!valid) control.title = '当前记录暂不支持从详情进入对话';
  return control;
}
