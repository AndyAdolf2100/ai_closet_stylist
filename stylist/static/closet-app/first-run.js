const KEY='ai-closet-stylist-session-v1';
export const onboardingURL='/app/?design=yijian&screen=onboarding';
export function sessionToken(){try{return JSON.parse(sessionStorage.getItem(KEY)||'null')?.access_token||'';}catch{return '';}}
export function loginURL(){return '/app/?design=yijian&screen=login';}
export function needsOnboarding(profile){return typeof profile?.agent_name!=='string'||!profile.agent_name.trim();}
let pending=null,pendingToken='';
export async function ensureOnboarded(){
 const token=sessionToken();if(!token){location.assign(loginURL());return false;}
 if(pending&&pendingToken===token)return pending;
 pendingToken=token;
 const request=(async()=>{try{const response=await fetch('/stylist-api/companion-profile',{headers:{Authorization:'Bearer '+token},cache:'no-store'});const body=await response.json();if(sessionToken()!==token)return false;if(response.status===401){location.assign(loginURL());return false;}if(!response.ok)throw Error(body.message||'暂时没能读取助理资料，请稍后重试。');if(needsOnboarding(body.profile)){location.assign(onboardingURL);return false;}return true;}catch(error){if(sessionToken()===token)window.PreviewMessage?.notify(error.message);return false;}})();
 pending=request;try{return await request;}finally{if(pending===request)pending=null;}
}
