document.body.dataset.edition='yijian';
const $=s=>document.querySelector(s);
const flows=[
 {id:'encounter',name:'初见手记',tag:'01 / 角色先行',desc:'先遇见陪伴你的人，再慢慢认识彼此。',steps:[['初次见面，\n今天想从哪里聊起？','有人陪你认真挑选，也有人记得你的小小偏爱。','hero'],['想和怎样的我相遇？','性格与相处方式，由你来选。之后也可以更换。','roles'],['我该怎么称呼你？','一个名字，让每次问候更靠近一点。','name'],['把日常，交给喜欢。','衣橱、天气和你的安排，都可以成为聊天的开始。','finish']]},
 {id:'letter',name:'写给你的第一封信',tag:'02 / 对话先行',desc:'以一来一回的轻对话，建立熟悉感。',steps:[['有一封信，\n想亲手交给你。','不用准备好答案。我们可以从一句问候开始。','letter'],['你好，要怎么称呼你？','你可以用昵称，也可以暂时留白。','name'],['今天，想怎样聊？','先试一种聊天节奏；正式偏好可在设置里调整。','tone'],['下一封，\n从你的日常开始。','想聊穿搭，或只想整理一下今天的想法，都可以。','finish']]},
 {id:'day',name:'从今天的一件小事',tag:'03 / 场景先行',desc:'先看见产品能帮什么，再邀请角色加入。',steps:[['今天的你，\n要去哪里？','从一个小小的安排，发现衣间能帮你的事。','occasion'],['熟悉的衣服，\n也有新的可能。','从个人衣橱找搭配，看看旧衣服的新组合。','wardrobe'],['让日常，多一个伙伴。','穿搭之外，也可以按你喜欢的节奏慢慢聊。','roles'],['准备好，\n开始今天了吗？','登录后连接个人衣橱；也可以先看看首页。','finish']]}
];
const comparing=new URLSearchParams(location.search).get('compare')==='1';
let flow=comparing?(flows.find(x=>x.id===new URLSearchParams(location.search).get('flow'))||flows[0]):flows[0],step=0;
document.body.dataset.comparing=String(comparing);
const draft={name:'',role:'male_calm_v1',tone:'简洁直接',occasion:'日常通勤'};
function el(tag,cls,text){const n=document.createElement(tag);n.className=cls;if(text)n.textContent=text;return n;}
function choice(label,value,field){const b=el('button','choice',label);b.type='button';b.setAttribute('aria-pressed',String(draft[field]===value));b.onclick=()=>{draft[field]=value;render();};return b;}
function portrait(id){const p=CompanionCharacters.find(id),wrap=el('div','portrait'),img=el('img','');img.src=p.image;img.alt=p.label;wrap.style.cssText=`--scale:${p.framing.scale};--top:${p.framing.top}%;--left:${p.framing.left}%`;wrap.append(img);return wrap;}
function render(){
 const [title,desc,type]=flow.steps[step],screen=$('#screen');screen.replaceChildren();$('.device').dataset.scene=type;document.body.dataset.flow=flow.id;
 $('#counter').textContent=`${flow.name} · ${String(step+1).padStart(2,'0')} / 04`;
 $('#flows').replaceChildren(...(comparing?flows:[flows[0]]).map(f=>{const b=el('button','flow');b.setAttribute('aria-pressed',String(f===flow));b.append(el('small','',f.tag),el('strong','',f.name),el('span','',f.desc));b.onclick=()=>{flow=f;step=0;history.replaceState(null,'',`?compare=1&flow=${f.id}`);render();};return b;}));
 screen.append(el('p','eyebrow',paperEdition?`衣间 · 初见手记 / 0${step+1}`:`YIJIAN / ${flow.id.toUpperCase()}`),el('h2','',title),el('p','description',desc));
 if(type==='hero'){screen.append(portrait(draft.role));const quote=el('div','quote');quote.append(el('small','',`衣衣 · ${CompanionCharacters.find(draft.role).label}`),el('p','',`“${CompanionCharacters.find(draft.role).greeting}”`));screen.append(quote);}
 if(type==='letter'){const card=el('div','letter');card.append(el('span','seal','衣'),el('small','','TO / 初次见面的你'),el('h3','','见字如面。'),el('p','','不急着定义你的风格。\n从今天喜欢的一件衣服，\n到明天想尝试的小小变化，\n我们都可以慢慢聊。'),el('p','signature','衣衣'));screen.append(card);}
 if(type==='roles'){const list=el('div','roles');CompanionCharacters.all.forEach(p=>{const b=choice(p.label,p.id,'role');b.prepend(portrait(p.id));list.append(b);});screen.append(list,el('p','hint','助理形象与用户性别独立；本页选择仅作预览。'));}
 if(type==='name'){const box=el('div','name-box');const label=el('label','','希望我怎样称呼你');label.htmlFor='nickname';const input=el('input','');input.id='nickname';input.placeholder='例如：小夏';input.maxLength=20;input.autocomplete='off';input.value=draft.name;input.oninput=()=>{draft.name=input.value;};box.append(label,input,el('p','hint','选填 · 随时可以在正式设置中修改'));screen.append(box,el('div','quote','“不着急。用你最自在的名字就好。”'));}
 if(type==='tone'||type==='occasion'){const list=el('div','choices');const items=type==='tone'?['简洁直接','温柔慢聊','轻松有趣']:['日常通勤','周末散步','特别的见面'];items.forEach((s,i)=>{const b=choice(s,s,type==='tone'?'tone':'occasion');b.prepend(el('small','',`0${i+1} / `));list.append(b);});screen.append(list,el('p','hint','体验选择，不会自动发送请求或保存偏好。'));}
 if(type==='wardrobe'){const card=el('div','wardrobe');const img=el('img','');img.src='/static/closet-app/assets/wardrobe_action_products.png';img.alt='衣物插画';card.append(img,el('small','',draft.occasion),el('h3','','把喜欢，再穿一次。'),el('p','','个人衣橱选款 → 搭配建议 → 按需确认试穿'));screen.append(card,el('p','hint','这里展示流程；不会上传照片或生成搭配。'));}
 if(type==='finish'){const c=CompanionCharacters.find(draft.role);const card=el('div','finish');const img=el('img','');img.src=`/static/assets/characters/companion-scenes-v1/${c.id}-avatar.png`;img.alt=c.label;card.append(img,el('p','',`${draft.name.trim()||'你好'}，很高兴在这里遇见你。`),el('h3','','把喜欢，穿进生活里。'));screen.append(card,el('p','hint','预览结束后进入现有首页；本页选择尚未保存。正式称呼、性别、助理昵称及形象仍在原四步设置中完成。'));}
 if(paperEdition){const caption=el('div','page-caption', ['第一章 · 遇见','第二章 · 陪伴的模样','第三章 · 你的名字','第四章 · 日常的序言'][step]);screen.append(caption);}
 $('#back').disabled=step===0;$('#next').textContent=step===3?'进入衣间 ↗':'继续 →';$('#dots').replaceChildren(...flow.steps.map((_,i)=>{const d=el('span',i===step?'active':'');d.setAttribute('aria-label',`第${i+1}步${i===step?'，当前':''}`);return d;}));
}
$('#next').onclick=()=>{if(step===3)location.href='/app/?design=yijian';else{step++;render();$('#screen h2').tabIndex=-1;$('#screen h2').focus({preventScroll:true});}};
$('#back').onclick=()=>{if(step){step--;render();}};$('#skip').onclick=()=>location.href='/app/?design=yijian';
document.querySelectorAll('button[data-color]').forEach(b=>b.onclick=()=>{document.body.dataset.color=b.dataset.color;document.querySelectorAll('button[data-color]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));});document.querySelector('button[data-color=male]').click();render();
