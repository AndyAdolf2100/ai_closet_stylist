'use strict';
// Shared, deterministic image normalization/mask math; no network or account state.
(() => {
  function normalize(rgba) {
    const pixels = rgba.length / 4, input = new Float32Array(pixels * 3);
    let max = 1;
    for (let i = 0; i < rgba.length; i += 4) for (let c = 0; c < 3; c++) max = Math.max(max, rgba[i+c]);
    const means = [.485,.456,.406], std = [.229,.224,.225];
    for (let i = 0; i < pixels; i++) for (let c = 0; c < 3; c++) input[c*pixels+i] = (rgba[i*4+c]/max-means[c])/std[c];
    return input;
  }
  function maskPixels(values) {
    let min = Infinity, max = -Infinity;
    for (const value of values) { if (!Number.isFinite(value)) throw Error('invalid_mask'); min = Math.min(min,value); max = Math.max(max,value); }
    if (max-min < 1e-6) throw Error('empty_mask');
    const rgba = new Uint8ClampedArray(values.length*4); let foreground = 0;
    for (let i=0;i<values.length;i++) {
      const alpha = Math.round(Math.max(0,Math.min(1,(values[i]-min)/(max-min)))*255);
      if (alpha>128) foreground++;
      rgba[i*4]=rgba[i*4+1]=rgba[i*4+2]=255; rgba[i*4+3]=alpha;
    }
    if (foreground/values.length < .01 || foreground/values.length > .99) throw Error('unreliable_mask');
    return rgba;
  }
  function cleanMask(rgba, width, height) {
    // Background lettering often survives as tiny detached saliency islands.
    // Keep significant disconnected pieces (e.g. a pair of shoes), not just one blob.
    const pixels=width*height,labels=new Int32Array(pixels),queue=new Int32Array(pixels);
    const sizes=[0];let largest=0;
    for(let p=0;p<pixels;p++){
      if(labels[p]||rgba[p*4+3]<=20)continue;
      const label=sizes.length;let head=0,tail=1;queue[0]=p;labels[p]=label;
      while(head<tail){
        const q=queue[head++],x=q%width,y=Math.floor(q/width);
        for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){
          const nx=x+dx,ny=y+dy;if(nx<0||nx>=width||ny<0||ny>=height)continue;
          const next=ny*width+nx;if(!labels[next]&&rgba[next*4+3]>20){labels[next]=label;queue[tail++]=next;}
        }
      }
      sizes.push(tail);largest=Math.max(largest,tail);
    }
    const minimum=Math.max(12,largest*.012);
    for(let p=0;p<pixels;p++)if(!labels[p]||sizes[labels[p]]<minimum)rgba[p*4+3]=0;
    return rgba;
  }
  globalThis.CutoutCore = { normalize, maskPixels, cleanMask };
})();
