'use strict';
const $=s=>document.querySelector(s);
const roles=CompanionCharacters.all;
const words={
 female_sweet_v1:['先请一件常穿的衣服住进来吧，我想看看你的小小偏爱。','一句“今天想穿得轻松点”就很好啦，剩下的我们一起想。','怕我漏掉的小偏好，可以写在这里。以后也能随时改主意哦。','从你喜欢的小事开始，今天就已经有新发现啦。','那就给今天留点活动空间吧。你想用衣橱里的衣服搭一套吗？'],
 female_warm_v1:['从一件穿着舒服的衣服开始就好，不用急着整理整个衣橱。','今天有什么安排、想穿得怎样，都可以慢慢说给我听。','把重要的喜好留在这里。你想修改或删掉的时候，也很方便。','你来决定从哪里开始，我会按你的节奏陪你。','舒服一点很好。告诉我今天的安排，我们再一起挑合适的穿法。'],
 female_regal_v1:['把你愿意穿的衣服留下来。衣橱不必很满，有你的偏爱就好。','喜欢什么，直接告诉我。穿得自在，首先要听自己的。','你的喜好值得有个位置。写下来，也随时保留改变的自由。','从最合心意的那件事开始，选择在你。','当然。穿得舒服也是很好的选择。今天是出门走走，还是待在室内？'],
 male_artistic_v1:['先选一件你喜欢的衣服吧，看看熟悉的日常能搭出什么新意。','想给今天换种感觉？把安排和心情告诉我，一起找点灵感。','把那些小小的喜欢写下来，像给日常夹一枚书签。','我们从一件衣服，或一句话开始，都挺好。','那给今天一点轻快的感觉吧。你想散散步，还是舒服地待一会儿？'],
 male_calm_v1:['先收进一件常穿的。之后需要搭配时，就能从自己的衣橱里选。','告诉我今天的安排和想穿的感觉。没想清楚的，可以一起理一理。','重要的穿衣偏好可以记在这里，你随时能查看、修改或删除。','不用一次做完。从你现在最需要的开始。','可以。今天需要走很多路吗？先把活动安排弄清楚，再考虑怎么穿。'],
 male_confident_v1:['挑一件你想穿的就行。衣橱慢慢添，先从这一件开始。','有想法就说，没有也没关系。咱们从今天去哪儿聊起。','喜欢就记，不喜欢就改。这里留的是你的想法，不是规矩。','选你想做的，第一步不用想得太复杂。','行，舒服这件事不用让步。今天打算去哪儿？我们从那里开始想。']
};
const chapters=[
 {label:'01 / A PLACE FOR YOUR CLOTHES',title:'让熟悉的衣服，<br>有一个小小的位置。',intro:'拍一张，或从相册选一张。先从一件常穿的开始。',expectation:'实际使用时，选图后先预览，确认上传才会收进衣橱。之后可以用它继续搭配。'},
 {label:'02 / A CONVERSATION WITH YOU',title:'今天想怎么穿，<br>都可以和我聊聊。',intro:'说说今天的安排、天气，或者一个还没想好的念头。',expectation:'你可以继续追问、换个想法。需要城市时再选择；收费试穿会另行确认。'},
 {label:'03 / LITTLE THINGS ABOUT YOU',title:'把你的喜欢，<br>留在我们的手账里。',intro:'喜欢的颜色、不想穿的款式，都值得被认真记下。',expectation:'手账里的偏好可以查看、修改或删除。它是参考，每次搭配仍以你当下的想法为先。'}
];
let step=0,done=false,uploaded=false,chatted=false,noted=false;
const params=new URLSearchParams(location.search);
const state={role:roles.some(r=>r.id===params.get('role'))?params.get('role'):'male_calm_v1',name:params.get('name')?.slice(0,24)||'衣衣',color:params.get('color')==='system'?'system':'companion'};
roles.forEach(r=>{const o=document.createElement('option');o.value=r.id;o.textContent=r.label+' · '+(r.gender==='male'?'男助理':'女助理');$('#role').append(o)});
$('#role').value=state.role;$('#companion-name').value=state.name;$('#palette').value=state.color;
const name=()=>state.name.trim()||'衣衣';
const notify=text=>PreviewMessage.notify(text,{name:name(),role:state.role});
const shirt='<svg viewBox="0 0 64 72" aria-hidden="true"><path d="M21 10 10 16 3 30l12 6 5-8v34h25V28l5 8 11-6-7-14-12-6c-4 9-17 9-21 0Z"/><path d="M21 10c1 17 19 17 21 0M20 55h25"/></svg>';
function render(){
 const role=CompanionCharacters.find(state.role),asset='/static/assets/characters/companion-scenes-v1/'+role.id+'-avatar.png';
 document.body.dataset.palette=state.color==='system'?'system':role.gender;
 $('#portrait').src=asset;$('#portrait').alt=role.label+'助理';$('#end-avatar').src=asset;$('#end-avatar').alt=role.label+'助理';
 $('#signature').textContent=name()+' · 写给你';$('#line').textContent=words[role.id][step];$('#end-line').textContent=words[role.id][3];
 $('#chapter').hidden=done;$('#finished').hidden=!done;$('#skip').hidden=done;$('#back').disabled=!done&&step===0;$('#counter').textContent=done?'READY WHEN YOU ARE':`0${step+1} / 03`;$('#next').innerHTML=done?'再看一遍 ↺':step===2?'我知道啦 <span>→</span>':'下一件小事 <span>→</span>';
 document.querySelectorAll('[data-step]').forEach(b=>{b.setAttribute('aria-current',!done&&Number(b.dataset.step)===step?'step':'false')});
 const data=chapters[step];$('#chapter-label').textContent=data.label;$('#title').innerHTML=data.title;$('#intro').textContent=data.intro;$('#expectation').textContent=data.expectation;
 const card=$('#try-card');
 if(step===0){card.innerHTML='<div class="card-caption">MY LITTLE WARDROBE <span>点一下试试</span></div><div class="demo-garment"><div class="garment-art">'+shirt+'</div><div><strong>'+(uploaded?'第一件，收好啦':'一件常穿的上衣')+'</strong><small>'+(uploaded?'示例衣橱 · 1 件衣服':'不用准备好一整个衣橱')+'</small></div></div><div class="card-bottom"><span>相册选图 / 拍摄</span><button class="demo-button" id="try-upload">'+(uploaded?'再体验一次':'＋ 试着收进衣橱')+'</button></div>';$('#try-upload').onclick=()=>{uploaded=!uploaded;render();if(uploaded)notify('示例衣服已放进演示衣橱。实际使用时，会先选图、预览，再由你确认上传。')};}
 if(step===1){card.innerHTML='<div class="card-caption">A LITTLE CHAT <span>点一句，看看回应</span></div><button class="sample-question" id="try-chat">今天想穿得舒服一点。</button><div class="sample-reply"><small id="reply-name"></small><span id="reply-text"></span></div>';$('#reply-name').textContent=name();$('#reply-text').textContent=chatted?words[role.id][4]:'不需要把问题想完整，从一句话开始就好。';$('#try-chat').onclick=()=>{chatted=true;render()};}
 if(step===2){card.innerHTML='<div class="card-caption">OUR LITTLE NOTES <span>一页关于你的喜欢</span></div><div class="journal-line"><small>'+(noted?'已记在这页 · 示例':'试着记下一件小事')+'</small>穿衣服时，我更在意舒服。</div><div class="card-bottom"><span>'+(noted?'可以改，也可以划掉':'你的偏好，由你决定')+'</span><button class="demo-button" id="try-note">'+(noted?'划掉这条':'记下这份喜欢')+'</button></div>';$('#try-note').onclick=()=>{noted=!noted;render();notify(noted?'这份喜欢已留在演示手账里。真实手账中，你也可以随时修改或删除。':'已从演示手账中移除。你的喜好可以改变。')};}
}
function go(n){PreviewMessage.hide();done=false;step=n;render();$('.scroll').scrollTop=0;$('#title').tabIndex=-1;$('#title').focus({preventScroll:true});}
$('#next').onclick=()=>{if(done){go(0);return}if(step<2)go(step+1);else{done=true;render();$('.scroll').scrollTop=0}};
$('#back').onclick=()=>{if(done)go(2);else if(step>0)go(step-1)};
$('#skip').onclick=()=>{done=true;render();$('.scroll').scrollTop=0};
$('#restart').onclick=()=>{uploaded=chatted=noted=false;go(0)};
document.querySelectorAll('[data-step]').forEach(b=>b.onclick=()=>go(Number(b.dataset.step)));
$('#role').onchange=e=>{state.role=e.target.value;PreviewMessage.hide();render()};$('#companion-name').oninput=e=>{state.name=e.target.value;render()};$('#palette').onchange=e=>{state.color=e.target.value;render()};
document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>notify({upload:'这里会打开添加衣服。当前是设计预览，不会选择或上传你的照片。',chat:'这里会进入和'+name()+'的对话。当前演示不发送消息。',memory:'这里会打开我们的手账。当前演示不保存你的资料。'}[b.dataset.action]));
// Future App integration may pass its account-owned profile; this preview never reads a session or calls an API.
window.addEventListener('companion-profile-change',({detail:p})=>{if(!p||!roles.some(r=>r.id===p.assistant_persona))return;state.role=p.assistant_persona;state.name=p.agent_name||'衣衣';state.color=p.color_scheme==='system'?'system':'companion';$('#role').value=state.role;$('#companion-name').value=state.name;$('#palette').value=state.color;render()});
render();
