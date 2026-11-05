// Shared by the real purchase page and its isolated guide snapshots.
export const membershipPersonas=Object.freeze(['female_sweet_v1','female_warm_v1','female_regal_v1','male_artistic_v1','male_calm_v1','male_confident_v1']);
export function membershipPersona(role){return membershipPersonas.includes(role)?role:'male_calm_v1';}
export function applyMembershipBanner(image,role){
  const persona=membershipPersona(role);
  const src=`/static/closet-app/assets/membership-banners/${persona}.png`;
  if(image.getAttribute('src')===src)return;
  image.dataset.persona=persona;
  // Do not leave the previous account's character visible during image loading.
  image.style.visibility='hidden';
  image.onload=()=>{image.style.visibility='';};
  image.onerror=()=>{image.style.visibility='hidden';};
  image.src=src;
}
