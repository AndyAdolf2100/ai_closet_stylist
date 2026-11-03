// Native-like read-only pull refresh; no writes or paid actions are accepted here.
export function listRefresh(root, reload) {
  if(document.documentElement.dataset.appDesign!=='yijian')return;
  const control=document.createElement('button');control.type='button';control.className='y-pull-refresh';control.textContent='下拉更新';control.setAttribute('aria-label','更新列表');root.prepend(control);
  let start=null,distance=0,busy=false;
  const scroller=()=>root.closest('.detail-page')||root;
  async function run(){if(busy||!root.isConnected)return;busy=true;control.classList.add('is-active');control.textContent='正在更新…';try{await reload();}finally{busy=false;distance=0;control.classList.remove('is-active');control.textContent='下拉更新';}}
  control.onclick=run;
  root.addEventListener('touchstart',e=>{start=!busy&&scroller().scrollTop<=0&&e.touches.length===1?{x:e.touches[0].clientX,y:e.touches[0].clientY}:null;distance=0;},{passive:true});
  root.addEventListener('touchmove',e=>{if(!start)return;const t=e.touches[0],dy=t.clientY-start.y;if(Math.abs(t.clientX-start.x)>Math.abs(dy)){start=null;return;}distance=Math.max(0,dy);if(distance>12){if(e.cancelable)e.preventDefault();control.classList.add('is-active');control.textContent=distance>70?'松开更新':'下拉更新';}},{passive:false});
  root.addEventListener('touchend',()=>{start=null;if(distance>70)run();else{distance=0;control.classList.remove('is-active');}},{passive:true});
  root.addEventListener('touchcancel',()=>{start=null;distance=0;if(!busy)control.classList.remove('is-active');},{passive:true});
}
