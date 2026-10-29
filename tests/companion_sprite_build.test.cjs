const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {createCanvas,loadImage}=require('@napi-rs/canvas');
const {W,H,COUNT,COLUMNS,ROWS,configs}=require('../scripts/build_companion_sprites.cjs');
for(const gender of ['female','male'])test(`${gender}: shipped atlas keeps body/background fixed and blinks without moving the figure`,async()=>{
 const atlas=await loadImage(path.join(__dirname,`../stylist/static/assets/characters/yiyi-${gender}-breeze-atlas-v2.png`));
 assert.equal(atlas.width,W*COLUMNS);assert.equal(atlas.height,H*ROWS);
 const canvas=createCanvas(W,H),ctx=canvas.getContext('2d');
 function frame(index){ctx.clearRect(0,0,W,H);ctx.drawImage(atlas,(index%COLUMNS)*W,Math.floor(index/COLUMNS)*H,W,H,0,0,W,H);return ctx.getImageData(0,0,W,H).data;}
 const base=frame(0);let eyeChanges=0,hairChanges=0;
 for(let index=1;index<COUNT;index++){
  const pixels=frame(index);
  for(let y=0;y<H;y++)for(let x=0;x<W;x++){
   const i=(y*W+x)*4;if(pixels[i]===base[i]&&pixels[i+1]===base[i+1]&&pixels[i+2]===base[i+2]&&pixels[i+3]===base[i+3])continue;
   const eye=configs[gender].eyes.some(([cx,cy,rx,ry])=>Math.abs(x-cx)<=rx+2&&Math.abs(y-cy)<=ry+2);
   const hair=configs[gender].hair.some(points=>{const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);return x>=Math.min(...xs)-2&&x<=Math.max(...xs)+2&&y>=Math.min(...ys)-2&&y<=Math.max(...ys)+2;});
   assert(eye||hair,`unexpected movement outside eyes/hair: frame ${index}, ${x},${y}`);
   if(eye&&!hair){assert([36,37,38].includes(index),'eyelids change only during the blink');eyeChanges++;}else if(hair)hairChanges++;
  }
 }
 assert(eyeChanges>0);assert(hairChanges>0);
});
