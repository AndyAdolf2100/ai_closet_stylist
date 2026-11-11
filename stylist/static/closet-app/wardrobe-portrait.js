// Each companion cycles their own triptych, resetting to the side view on persona changes.
export function wardrobePortraitMotion(node){
 const overlay=document.createElement('span');overlay.className='y-wardrobe-portrait-fade';overlay.setAttribute('aria-hidden','true');node.append(overlay);
 const reduced=matchMedia('(prefers-reduced-motion: reduce)'),positions=[50,0,100];
 let enabled=false,visible=false,index=0,timer,settle,currentPersona;
 const finish=()=>{clearTimeout(settle);node.style.backgroundPosition=positions[index]+'% 0';overlay.style.transition='none';overlay.style.opacity='0';};
 const pause=()=>{clearTimeout(timer);finish();};
 const active=()=>enabled&&visible&&!document.hidden&&!reduced.matches;
 function schedule(){clearTimeout(timer);if(!active())return;timer=setTimeout(()=>{
   if(!active())return;index=(index+1)%positions.length;overlay.style.backgroundPosition=positions[index]+'% 0';overlay.style.transition='none';overlay.style.opacity='0';void overlay.offsetWidth;overlay.style.transition='opacity 1400ms ease-in-out';overlay.style.opacity='1';
   settle=setTimeout(()=>{finish();schedule();},1400);
 },5200);}
 function sync(){pause();if(reduced.matches){index=0;finish();}schedule();}
 new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();}).observe(node);
 document.addEventListener('visibilitychange',sync);reduced.addEventListener('change',sync);
 return persona=>{if(persona===currentPersona)return;pause();currentPersona=persona;enabled=/^(male_(calm|artistic|confident)|female_(sweet|warm|regal))_v1$/.test(persona);index=0;finish();schedule();};
}
