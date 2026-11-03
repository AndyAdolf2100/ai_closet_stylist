// Account identity is independent of the companion and the generated try-on twin.
// Membership labels match iOS ProfileHeaderView.reloadUser: active type 5 = VIP, otherwise SVIP.
export function accountHeader({make,icon,forward}) {
 const card=make('section','y-account-header');card.setAttribute('aria-label','我的账号');
 const portrait=make('button','y-account-portrait'),fallback=icon('profile'),image=make('img','y-account-image');
 portrait.type='button';portrait.setAttribute('aria-label','更换账号头像');portrait.title='更换头像';
 image.alt='我的账号头像';image.hidden=true;portrait.append(fallback,image);
 const body=make('div','y-account-body'),name=make('h2','','我的账号'),line=make('div','y-account-line');
 const badge=make('button','y-account-membership'),status=make('span','y-account-status'),caption=make('p','y-account-caption','你的喜欢，值得在这里留一页。');
 badge.type='button';badge.hidden=true;badge.onclick=()=>document.querySelector('.points-card [data-detail=membership]')?.click();
 line.append(badge,status);body.append(name,line,caption);
 const login=make('button','y-account-login','登录衣橱');login.type='button';login.onclick=()=>forward('login');
 card.append(portrait,body,login);
 // Temporary display source: Agent user_name. Do not write back to the App account.
 let displayName='',nameOwner='',lastProfile=null,uploading=false,revision=0;
 const token=()=>{try{return JSON.parse(sessionStorage.getItem('ai-closet-stylist-session-v1')||'null')?.access_token||'';}catch{return '';}};
 const logged=()=>!!token();
 const showName=()=>{name.textContent=logged()?(nameOwner===token()&&displayName?displayName:'我的账号'):'欢迎来到衣间';};
 card.setDisplayName=value=>{nameOwner=token();displayName=typeof value==='string'?value.trim():'';showName();};
 function reset(state='loading') {image.hidden=true;image.removeAttribute('src');fallback.hidden=false;badge.hidden=true;badge.textContent='';showName();login.hidden=logged();status.hidden=false;status.textContent=logged()?(state==='error'?'账号信息暂未读取':'正在读取账号'):'登录后，接着记录你的日常';caption.hidden=!logged();}
 image.onerror=()=>{image.hidden=true;image.removeAttribute('src');fallback.hidden=false;};
 image.onload=()=>{if(image.getAttribute('src')){image.hidden=false;fallback.hidden=true;}};
 function render(profile){lastProfile=profile;reset();if(!profile)return;login.hidden=true;showName();const src=profile.image_url||profile.avatar;
  if(typeof src==='string'&&src.trim()){try{const url=new URL(src,location.origin);if(['http:','https:'].includes(url.protocol))image.src=url.href;}catch{}}
  const vip=profile.vip_info;const active=vip?.is_vip===true||vip?.is_vip===1;
  if(active){const level=Number(vip.vip_type)===5?'VIP':'SVIP';const label=make('span','y-account-badge');const crown=make('img','y-membership-crown');crown.src='/static/closet-app/assets/profile-crown.svg';crown.alt='';label.append(crown,make('span','',level),make('span','y-membership-word','会员'));badge.dataset.level=level;badge.replaceChildren(label);badge.setAttribute('aria-label',level+'会员，查看会员与积分');badge.hidden=false;status.hidden=true;}
  else {status.textContent=vip?.is_vip===false||vip?.is_vip===0?'普通账号':'会员信息待同步';}
 }
 window.addEventListener('yijian-account-loaded',e=>render(e.detail));
 window.addEventListener('yijian-account-error',()=>reset('error'));
 window.addEventListener('yijian-account-reset',()=>{revision++;uploading=false;portrait.disabled=false;portrait.removeAttribute('aria-busy');lastProfile=null;displayName='';nameOwner='';reset();});
 const picker=make('input');picker.type='file';picker.accept='image/jpeg,image/png,image/webp';picker.hidden=true;picker.setAttribute('aria-label','选择账号头像');card.append(picker);
 let pickOwner='',pickRevision=0;
 portrait.onclick=()=>{if(!logged()){forward('login');return;}if(uploading)return;pickOwner=token();pickRevision=++revision;picker.value='';picker.click();};
 picker.onchange=async()=>{
  const file=picker.files?.[0];if(!file||pickOwner!==token()||pickRevision!==revision)return;
  const notify=text=>window.PreviewMessage.notify(text);
  if(!/^image\/(jpeg|png|webp)$/.test(file.type)||file.size>10*1024*1024){notify('选一张10MB以内的JPG、PNG或WebP照片吧。');return;}
  const currentOwner=pickOwner,currentRevision=pickRevision,valid=()=>token()===currentOwner&&revision===currentRevision;
  uploading=true;portrait.disabled=true;portrait.setAttribute('aria-busy','true');const url=URL.createObjectURL(file);
  try{
   const source=new Image();source.src=url;await source.decode();if(!valid())return;
   const canvas=document.createElement('canvas');canvas.width=canvas.height=512;const side=Math.min(source.naturalWidth,source.naturalHeight),ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,512,512);ctx.drawImage(source,(source.naturalWidth-side)/2,(source.naturalHeight-side)/2,side,side,0,0,512,512);
   const response=await fetch('/stylist-api/app/avatar',{method:'POST',headers:{Authorization:'Bearer '+currentOwner,'Content-Type':'application/json'},body:JSON.stringify({image_url:canvas.toDataURL('image/jpeg',.9)})});
   const result=await response.json();if(!valid())return;if(!response.ok||!result.data?.image_url)throw Error(result.message||'头像暂时没能保存，请稍后再试。');
   const updated={...(lastProfile||{}),image_url:result.data.image_url};window.dispatchEvent(new CustomEvent('yijian-account-loaded',{detail:updated}));notify('头像换好了。');
  }catch(error){if(valid())notify(error.message||'照片没能读取，请换一张试试。');}
  finally{URL.revokeObjectURL(url);if(valid()){uploading=false;portrait.disabled=false;portrait.removeAttribute('aria-busy');picker.value='';}}
 };
 reset();return card;
}
