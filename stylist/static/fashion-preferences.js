/* Shared user-gender catalog for onboarding and account preferences, not assistant gender. */
(()=>{
 const styles=['简约','休闲','通勤','温柔','复古','运动','街头','优雅'];
 const common=['舒适自在','方便走动','容易打理','合身自然','适合场合'];
 const female=['轻松舒适','显瘦遮肉','职业干练','温柔甜美','活力阳光'];
 const genderType=value=>value==='男'?'male':value==='女'?'female':null;
 function prioritiesFor(gender){return gender==='女'?[...female]:gender==='男'?[...common]:[];}
 function applyArt(art,label,kind,gender){
  const type=genderType(gender),labels=kind==='style'?styles:[...common,...female];
  const index=labels.indexOf(label)+(kind==='style'?0:8),rows=type==='female'?5:4;
  const visible=Boolean(type)&&labels.includes(label)&&(kind==='style'||prioritiesFor(gender).includes(label));
  art.hidden=!visible;art.style.display=visible?'':'none';art.dataset.userGender=type||'unspecified';art.dataset.fashionLabel=label;
  art.style.backgroundImage=visible?`url('/static/assets/preference-fashion-${type}-v4.png')`:'';
  art.style.backgroundSize=`400% ${rows*100}%`;
  art.style.backgroundPosition=`${index%4*100/3}% ${Math.floor(index/4)*100/(rows-1)}%`;
 }
 globalThis.FashionPreferences={styles:[...styles],commonPriorities:[...common],femalePriorities:[...female],prioritiesFor,genderType,applyArt};
})();
