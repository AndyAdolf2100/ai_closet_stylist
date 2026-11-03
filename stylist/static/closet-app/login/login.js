const $=s=>document.querySelector(s);
let codeStage=false;
function valid(){return /^1[3-9][0-9]{9}$/.test($('#phone').value)&&$('#agree').checked;}
function update(){
  $('#login').disabled=!valid();
  $('#code').value=$('#code').value.replace(/\D/g,'').slice(0,6);
  $('#verify').disabled=!/^[0-9]{6}$/.test($('#code').value);
  document.querySelectorAll('.otp-cells span').forEach((cell,i)=>{cell.textContent=$('#code').value[i]||'';cell.classList.toggle('current',i===Math.min($('#code').value.length,5));});
}
function showCode(show){
  codeStage=show;$('.login-scroll').hidden=show;$('.verification-page').hidden=!show;
  $('#sample').textContent=show?'填入示例验证码':'填入示例手机号';
  if(show){$('#destination').textContent='+86 '+$('#phone').value.replace(/(\d{3})(\d{4})(\d{4})/,'$1 $2 $3');$('#code').focus();}
  else{$('#code').value='';PreviewMessage.hide();$('#phone').focus();}
  update();
}
$('#phone').addEventListener('input',update);$('#code').addEventListener('input',update);$('#agree').addEventListener('change',update);
$('#sample').onclick=()=>{if(codeStage)$('#code').value='123456';else $('#phone').value='13800000000';update();};
$('#send').onclick=()=>{PreviewMessage.notify('预览不发送短信，可使用页面外的示例验证码。');};
$('#login-form').onsubmit=e=>{e.preventDefault();if(!valid()){PreviewMessage.notify('请填写正确的手机号，并阅读同意用户协议与隐私政策。');return;}history.pushState({loginCode:true},'', '#verification');showCode(true);};
$('#verification-form').onsubmit=e=>{e.preventDefault();if(valid()&&/^[0-9]{6}$/.test($('#code').value))location.href='../onboarding/index.html';else PreviewMessage.notify('请输入六位数字验证码。');};
$('#back-phone').onclick=()=>{if(history.state?.loginCode)history.back();else showCode(false);};
window.addEventListener('popstate',()=>showCode(location.hash==='#verification'&&valid()));
// A refreshed preview has no authenticated session or stored phone number.
if(location.hash==='#verification')history.replaceState(null,'',location.pathname+location.search);
$('#wechat-installed').onchange=e=>{$('#wechat').hidden=!e.target.checked;};
document.querySelectorAll('[data-vendor]').forEach(b=>b.onclick=()=>{PreviewMessage.notify($('#agree').checked?`${b.dataset.vendor} 授权入口预览；实际授权与必要的手机号绑定沿用 App 流程。`:'请先阅读并同意用户协议与隐私政策。');});
document.querySelectorAll('[data-policy]').forEach(b=>b.onclick=()=>{$('#policy-title').textContent=b.dataset.policy+' · 预览';$('#policy').showModal();});$('#close-policy').onclick=()=>$('#policy').close();
update();
