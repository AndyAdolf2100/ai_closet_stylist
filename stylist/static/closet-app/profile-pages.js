import {emptyArt} from './empty-art.js';
import {listRefresh} from './list-refresh.js';
// Account-scoped App pages, isolated from the conversation controller.
export function profilePage(key, ctx) {
  const {node,button,detail,openAgent,readSession,signal}=ctx;
  const ios=document.documentElement.dataset.appDesign==='ios';
  const notify=text=>window.PreviewMessage.notify(text);
  const owner=readSession()?.access_token||'';
  const current=()=>!signal.aborted&&(readSession()?.access_token||'')===owner;
  const root=node('div','y-service-page'+(ios?' ios-service-page ios-service-'+key:''));
  async function request(path,body){
    if(!owner)throw Object.assign(new Error('请先连接衣橱，再查看或提交。'),{login:true});
    const response=await fetch('/stylist-api/app/'+path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+owner,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{}),cache:'no-store',signal});
    const payload=await response.json();
    if(!current())throw new DOMException('账号已切换','AbortError');
    if(!response.ok)throw Object.assign(new Error(response.status===401?'登录已过期，请重新连接衣橱。':(payload.message||'暂时没能完成，请稍后重试。')),{login:response.status===401});
    return payload.data;
  }
  function intro(eyebrow,title,text){const head=node('header','y-service-intro');head.append(node('span','y-service-eyebrow',eyebrow),node('h3','',title),node('p','',text));root.append(head);}
  function failure(target,error,retry){if(error.name==='AbortError'||!current())return;notify(error.message);target.replaceChildren(button(error.login?'连接衣橱':'重新加载',error.login?()=>openAgent('login'):retry,'y-service-secondary'));}
  function blank(target,title,text){const box=node('div','y-service-empty');if(ios&&key==='orders'){const img=node('img','ios-order-empty');img.src='/static/closet-app/assets/ios-order-empty.png';img.alt='';box.append(img);}box.append(ios?node('span','y-service-symbol','✧'):emptyArt(key==='orders'?'orders':'letters'),node('strong','',title),node('p','',text));target.append(box);}
  if(key==='contact'){
    intro('A NOTE TO US','有想说的话，可以写给我们。','使用中的疑问，或关于爱搭衣橱的想法，都可以通过邮箱联系我们。');
    const card=node('section','y-service-card y-contact-card');card.append(node('span','y-service-eyebrow','CONTACT EMAIL'),node('strong','y-contact-email','Aiyichupm@microdreams.com'));
    const actions=node('div','y-service-actions');actions.append(button('复制邮箱',async()=>{try{await navigator.clipboard.writeText('Aiyichupm@microdreams.com');notify('邮箱已复制，想说的话可以慢慢写。');}catch{notify('暂时无法复制，可以长按邮箱选择复制。');}},'y-service-primary'));
    const mail=node('a','y-service-secondary','写邮件');mail.href='mailto:Aiyichupm@microdreams.com';actions.append(mail);card.append(actions);root.append(card,node('p','y-service-footnote','北京玲珑象限科技有限公司'));
    if(ios){root.querySelector('.y-service-intro').remove();const branding=node('div','ios-contact-brand');for(const [asset,cls]of[['ios-contact-logo.png','ios-contact-logo'],['ios-contact-wordmark.png','ios-contact-wordmark']]){const img=node('img',cls);img.src='/static/closet-app/assets/'+asset;img.alt=cls.endsWith('wordmark')?'AI衣橱':'';branding.append(img);}root.prepend(branding);card.querySelector('.y-service-eyebrow').remove();card.querySelector('.y-contact-email').textContent='联系方式：Aiyichupm@microdreams.com';card.querySelector('.y-contact-email').tabIndex=0;const copy=()=>actions.querySelector('button').click();card.querySelector('.y-contact-email').onclick=copy;card.querySelector('.y-contact-email').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();copy();}};}

  }
  if(key==='feedback'){
    intro('WE ARE LISTENING','你的想法，我们认真听。','遇到的问题、希望改进的细节，都可以在这里告诉我们。');
    const form=node('form','y-service-card y-feedback-form');form.noValidate=true;
    const label=node('label','','有什么想法，想说给我们听？');label.htmlFor='y-feedback-text';
    const input=node('textarea');input.id='y-feedback-text';input.maxLength=300;input.placeholder='哪里让你用得不顺心，或有什么小期待，都可以写下来。';input.rows=6;if(ios)input.placeholder='请写下您的投诉 or 建议';
    const count=node('span','y-feedback-count','0 / 300');input.oninput=()=>{count.textContent=Array.from(input.value).length+(ios?'/':' / ')+'300';if(ios){send.disabled=!input.value.trim();send.classList.toggle('is-ready',!!input.value.trim());}};
    const file=node('input');file.type='file';file.accept='image/jpeg,image/png';file.multiple=true;file.hidden=true;file.setAttribute('aria-label','选择反馈图片');
    const previews=node('div','y-feedback-images');let images=[],busy=false,reading=false;
    const render=()=>{previews.replaceChildren();images.forEach((image,i)=>{const box=node('div','y-feedback-image'),img=node('img');img.src=image.data;img.alt='反馈附件 '+(i+1);const remove=button('×',()=>{if(!busy){images.splice(i,1);render();}},'y-feedback-remove');remove.setAttribute('aria-label','删除附件 '+(i+1));remove.disabled=busy;box.append(img,remove);previews.append(box);});};
    const add=button('＋ 添加图片',()=>file.click(),'y-service-secondary');
    file.onchange=async()=>{if(busy||reading)return;const selected=[...file.files];file.value='';if(selected.length+images.length>9){notify('最多添加9张图片，可以先移除一张。');return;}reading=true;add.disabled=true;send.disabled=true;for(const f of selected){if(!['image/jpeg','image/png'].includes(f.type)||f.size>5*1024*1024){notify('请选择不大于5MB的JPEG或PNG图片。');continue;}try{const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(f);});if(!current()||!root.isConnected)return;images.push({data,url:null});render();}catch{notify('图片没能读取，请重新选择。');}}reading=false;add.disabled=false;send.disabled=ios&&!input.value.trim();};
    const send=button('提交反馈',()=>{},'y-service-primary');send.type='submit';
    form.append(label,input,count,node('p','y-service-hint','图片选填 · 最多9张，每张不超过5MB'),previews,add,file,send);
    if(ios){const field=node('div','ios-feedback-field');input.before(field);field.append(input,count);send.disabled=true;send.textContent='提交';count.textContent='0/300';add.textContent='＋';add.setAttribute('aria-label','添加反馈图片');}
    form.onsubmit=async e=>{e.preventDefault();if(busy||reading)return;if(!input.value.trim()){notify('请先写下想反馈的内容。');input.focus();return;}if(Array.from(input.value.trim()).length>300){notify('反馈内容请控制在300字以内。');return;}
      busy=true;input.disabled=true;add.disabled=true;send.disabled=true;render();send.textContent='正在提交…';
      try{for(const image of images){if(!image.url){const data=await request('feedback-image',{image_url:image.data});const url=typeof data==='string'?data:(data?.url||data?.image_url||data?.file_url);if(!url||!url.startsWith('https://'))throw new Error('图片上传回执异常，请保留内容后重试。');image.url=url;}}
        await request('feedback',{content:input.value.trim(),urls:images.map(i=>i.url)});if(!current())return;input.value='';count.textContent='0 / 300';images=[];notify('反馈已收到。谢谢你愿意把想法告诉我们。');
      }catch(error){if(error.name!=='AbortError'&&current())notify(error.message);}finally{if(current()){busy=false;input.disabled=false;add.disabled=false;send.disabled=false;send.textContent=ios?'提交':'提交反馈';if(ios){send.disabled=!input.value.trim();send.classList.toggle('is-ready',!!input.value.trim());}render();}}
    };root.append(form);
  }
  if(key==='messages'||key==='orders'){
    intro(key==='messages'?'LETTERS & UPDATES':'YOUR ORDER RECORDS',key==='messages'?'消息，收在这里。':'每一笔记录，清楚留存。',key==='messages'?'查看与你账号相关的通知与更新。':'会员与积分订单分开查看，金额与状态以实际记录为准。');
    let section=key==='messages'?'messages':'orders',page=0,items=[],version=0,busy=false;
    const tabs=node('div','y-service-tabs');if(key==='orders'){tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','订单类型');for(const [id,title]of[['orders','会员订单'],['points-orders','积分订单']]){const tab=button(title,()=>{if(section===id)return;section=id;load(true);},'');tab.dataset.section=id;tab.setAttribute('role','tab');tabs.append(tab);}root.append(tabs);}
    const list=node('div','y-service-list'),status=node('p','y-service-hint');root.append(list,status);
    function orderContent(item){const card=node('article','y-service-card y-order-card');const top=node('div','y-order-top');top.append(node('strong','',item.order_content||item.vip_type_name||(section==='points-orders'?'积分订单':'会员订单')),node('span','y-order-status',item.status_text||'状态未提供'));card.append(top);
      const amount=item.pay_money;if(amount!==undefined&&amount!==null&&Number.isFinite(Number(amount)))card.append(node('p','y-order-amount','¥ '+Number(amount).toFixed(2)));
      const info=node('dl','y-order-meta');for(const [label,value]of[['订单号',item.out_trade_no],['时间',item.created_at||item.order_start_time],['积分',item.points_amount],['支付方式',({1:'Apple',2:'微信',3:'支付宝'})[item.pay_type]]]){if(value!==undefined&&value!==null&&value!=='')info.append(node('dt','',label),node('dd','',label==='积分'&&Number.isFinite(Number(value))?Number(value).toLocaleString('en-US',{maximumFractionDigits:20}):String(value)));}if(ios){const amount=card.querySelector('.y-order-amount');if(amount){info.append(node('dt','','支付金额：'),node('dd','',amount.textContent));amount.remove();}if(item.is_subscription===1&&item.is_subscribing===1){if(item.expire_time)info.append(node('dt','','下次续费：'),node('dd','',item.expire_time));if(item.next_renewal_amount!=null)info.append(node('dt','','续费金额：'),node('dd','','¥ '+Number(item.next_renewal_amount).toFixed(2)));}}
      card.append(info);if(Array.isArray(item.sub_orders)&&item.sub_orders.length){const sub=node('details','y-order-renewals');sub.append(node('summary','','自动扣款记录'));item.sub_orders.forEach(x=>{sub.append(node('p','',[(x.pay_end_time||x.order_start_time),x.status_text,x.pay_money!=null?'¥ '+Number(x.pay_money).toFixed(2):''].filter(Boolean).join(' · ')));});card.append(sub);}return card;}
    async function openMessage(item){const id=Number(item.id);if(!Number.isInteger(id)||id<=0){notify('消息信息不完整，请刷新后重试。');return;}try{const data=await request('message-detail/'+id);if(!root.isConnected)return;const paper=node('article','y-service-page'+(ios?' ios-service-page':''));paper.append(node('span','y-service-eyebrow',data.message_type_name||'MESSAGE'),node('h3','y-message-title',data.title||'消息'),node('p','y-service-hint',data.send_time||''),node('p','y-message-body',data.content||'暂无正文'));item.is_read=1;render();detail('消息详情',paper);}catch(error){if(error.name!=='AbortError')notify(error.message);}}
    function render(){list.replaceChildren();if(!items.length){blank(list,key==='messages'?'这里，还没有新的来信':'这一页，暂时留白',key==='messages'?'有新的账号消息，会收在这一页。先去看看喜欢的穿搭吧。':'有了会员或积分订单，我们会在这里为你整理清楚。');return;}items.forEach(item=>{if(key==='orders')list.append(orderContent(item));else{const row=button('',()=>openMessage(item),'y-service-card y-message-row');const heading=node('span','y-message-heading');heading.append(node('strong','',item.title||'消息'));if(item.is_read===0)heading.append(node('span','y-message-unread','未读'));row.append(heading,node('span','y-message-preview',item.content||''),node('small','',item.send_time_format||item.send_time||''));list.append(row);}});}
    async function load(reset){const ticket=++version;if(reset){items=[];page=0;list.replaceChildren();}busy=true;status.textContent='正在翻开这一页…';tabs.querySelectorAll('button').forEach(t=>t.setAttribute('aria-selected',String(t.dataset.section===section)));more.hidden=true;
      try{const data=await request(section+'?page='+(page+1));if(ticket!==version||!root.isConnected)return;const rows=data.list;if(!Array.isArray(rows))throw new Error('返回的数据格式异常，请稍后重试。');items=reset?rows:[...items,...rows];page++;render();const total=data.pagination?.total;more.hidden=total!=null?items.length>=Number(total):rows.length<10;status.textContent='';}
      catch(error){if(ticket===version){status.textContent='';failure(list,error,()=>load(reset));}}finally{if(ticket===version)busy=false;}}
    const more=button('加载更多',()=>{if(!busy)load(false);},'y-service-secondary y-service-more');root.append(more);more.hidden=true;
    listRefresh(root,()=>busy?Promise.resolve():load(true));
    // Load after detail() attaches this page.
    setTimeout(()=>{if(root.isConnected&&current())load(true);},0);
  }
  return root;
}
