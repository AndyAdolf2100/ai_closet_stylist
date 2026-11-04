const $=s=>document.querySelector(s);
let codeStage=false;
const live=new URLSearchParams(location.search).get('live')==='1'||new URLSearchParams(location.search).get('screen')==='login';
if(live){document.body.dataset.live='true';document.querySelector('.login-page').setAttribute('aria-label','登录爱搭衣橱');document.querySelector('.code-destination').firstChild.textContent='当前登录手机号 ';$('#send').textContent='如何获取验证码';}
if(!live){$('.login-home').href='../comparison/index.html#preview';document.querySelector('.studio>a').href='../comparison/index.html#preview';}
let submitting=false;
function valid(){return /^1[3-9][0-9]{9}$/.test($('#phone').value)&&$('#agree').checked;}
function update(){
  $('#login').disabled=!valid();
  $('#code').value=$('#code').value.replace(/\D/g,'').slice(0,6);
  $('#verify').disabled=!/^[0-9]{6}$/.test($('#code').value);
  document.querySelectorAll('.otp-cells span').forEach((cell,i)=>{cell.textContent=$('#code').value[i]||'';cell.classList.toggle('current',i===Math.min($('#code').value.length,5));});
}
function showCode(show){
  codeStage=show;$('.login-scroll').hidden=show;$('.verification-page').hidden=!show;
  $('.login-home').setAttribute('aria-label',show?'返回手机号输入':'返回爱搭衣橱');
  $('#sample').textContent=show?'填入示例验证码':'填入示例手机号';
  if(show){$('#destination').textContent='+86 '+$('#phone').value.replace(/(\d{3})(\d{4})(\d{4})/,'$1 $2 $3');$('#code').focus();}
  else{$('#code').value='';PreviewMessage.hide();$('#phone').focus();}
  update();
}
$('#phone').addEventListener('input',update);$('#code').addEventListener('input',update);$('#agree').addEventListener('change',update);
$('#sample').onclick=()=>{if(codeStage)$('#code').value='123456';else $('#phone').value='13800000000';update();};
$('#send').onclick=()=>{PreviewMessage.notify(live?'请通过现有 AI Closet App 获取验证码，再回到这里填写。当前网页尚未接入短信发送。':'预览不发送短信，可使用页面外的示例验证码。');};
$('#login-form').onsubmit=e=>{e.preventDefault();if(!valid()){PreviewMessage.notify('请填写正确的手机号，并阅读同意用户协议与隐私政策。');return;}history.pushState({loginCode:true},'', location.pathname+location.search+'#verification');showCode(true);};
$('#verification-form').onsubmit=async e=>{e.preventDefault();if(submitting)return;if(!valid()||!/^[0-9]{6}$/.test($('#code').value)){PreviewMessage.notify('请输入六位数字验证码。');return;}if(!live){location.href='../onboarding/index.html';return;}submitting=true;$('#verify').disabled=true;$('#back-phone').disabled=true;const previous=sessionStorage.getItem('ai-closet-stylist-session-v1');try{let device=sessionStorage.getItem('stylist-device-id');if(!device){device='stylist-'+crypto.randomUUID();sessionStorage.setItem('stylist-device-id',device);}const response=await fetch('/stylist-api/auth/mobile-login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mobile:$('#phone').value,code:$('#code').value,device_id:device})});const data=await response.json();if(sessionStorage.getItem('ai-closet-stylist-session-v1')!==previous)throw Error('账号状态已变化，请重新登录。');if(!response.ok||!data.access_token)throw Error(data.message||'登录未成功，请核对验证码。');sessionStorage.setItem('ai-closet-stylist-session-v1',JSON.stringify(data));$('#code').value='';location.replace('/app/?design=yijian');}catch(error){PreviewMessage.notify(error.message);}finally{submitting=false;$('#back-phone').disabled=false;update();}};
const backToPhone=()=>{if(submitting)return;if(history.state?.loginCode)history.back();else showCode(false);};
$('#back-phone').onclick=backToPhone;
$('.login-home').onclick=event=>{if(codeStage){event.preventDefault();backToPhone();}};
window.addEventListener('popstate',()=>showCode(location.hash==='#verification'&&valid()));
// A refreshed preview has no authenticated session or stored phone number.
if(location.hash==='#verification')history.replaceState(null,'',location.pathname+location.search);
$('#wechat-installed').onchange=e=>{$('#wechat').hidden=!e.target.checked;};
document.querySelectorAll('[data-vendor]').forEach(b=>b.onclick=()=>{PreviewMessage.notify($('#agree').checked?`${b.dataset.vendor} 授权入口预览；实际授权与必要的手机号绑定沿用 App 流程。`:'请先阅读并同意用户协议与隐私政策。');});
document.querySelectorAll('[data-policy]').forEach(b=>b.onclick=()=>{if(live){window.open('https://h5.aidacloset.com/'+(b.dataset.policy==='用户协议'?'protocolUser':'protocolPrivacy'),'_blank','noopener,noreferrer');return;}$('#policy-title').textContent=b.dataset.policy+' · 预览';$('#policy').showModal();});$('#close-policy').onclick=()=>$('#policy').close();
update();
