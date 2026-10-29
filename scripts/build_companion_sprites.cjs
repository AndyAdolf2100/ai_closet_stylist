/** Deterministic local motion/packing of imagegen keyframes; no model/API calls. */
const {createCanvas,loadImage}=require('@napi-rs/canvas');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const W=384,H=512,COUNT=48,COLUMNS=8,ROWS=6;
const configs={
 female:{zoom:.84,center:388,top:2,colors:['#fff8ee','#edd7c7'],eyes:[[173,86,16,9],[206,75,16,9]],face:[151,55,78,82],hair:[[[124,72],[148,60],[158,93],[150,127],[129,137],[119,116]],[[237,65],[250,85],[244,126],[224,135],[229,100]]]},
 male:{zoom:1,center:376,top:0,colors:['#f3f8fc','#dce8f1'],eyes:[[161,87,17,9],[199,75,17,9]],face:[139,54,83,87],hair:[[[127,27],[145,12],[164,14],[156,34],[140,47],[125,42]],[[211,18],[228,26],[237,46],[222,58],[213,45]],[[131,54],[149,49],[153,70],[139,78]]]},
};
function polygon(ctx,points){ctx.beginPath();ctx.moveTo(...points[0]);for(const point of points.slice(1))ctx.lineTo(...point);ctx.closePath();}
function prepare(source,side,config,backdrop){
 const canvas=createCanvas(W,H),ctx=canvas.getContext('2d');
 const gradient=ctx.createLinearGradient(0,0,W,H);gradient.addColorStop(0,config.colors[0]);gradient.addColorStop(1,config.colors[1]);ctx.fillStyle=gradient;ctx.fillRect(0,0,W,H);
 if(backdrop)ctx.drawImage(backdrop,0,0,W,H);
 const photo=createCanvas(W,H),p=photo.getContext('2d');
 const pw=source.width/2,ph=source.height,scale=H/ph*config.zoom;
 const dx=W/2-(config.center/768*pw)*scale,dy=config.top;
 p.drawImage(source,side*pw,0,pw,ph,dx,dy,pw*scale,ph*scale);
 // A static feathered background extension allows an accurate medium-distance
 // crop without enlarging the woman's head or leaving rectangular side bars.
 p.globalCompositeOperation='destination-in';
 const mask=p.createLinearGradient(dx,0,dx+pw*scale,0);mask.addColorStop(0,'transparent');mask.addColorStop(backdrop ? .12 : .045,'white');mask.addColorStop(backdrop ? .88 : .955,'white');mask.addColorStop(1,'transparent');p.fillStyle=mask;p.fillRect(0,0,W,H);
 const bottom=p.createLinearGradient(0,dy,0,dy+ph*scale);bottom.addColorStop(0,'white');bottom.addColorStop(.91,'white');bottom.addColorStop(1,'transparent');p.fillStyle=bottom;p.fillRect(0,0,W,H);
 ctx.drawImage(photo,0,0);return canvas;
}
function eyeMask(config){
 const canvas=createCanvas(W,H),ctx=canvas.getContext('2d');
 for(const [x,y,rx,ry]of config.eyes){ctx.save();ctx.translate(x,y);ctx.scale(rx,ry);const fade=ctx.createRadialGradient(0,0,.78,0,0,1);fade.addColorStop(0,'white');fade.addColorStop(1,'transparent');ctx.fillStyle=fade;ctx.beginPath();ctx.arc(0,0,1,0,Math.PI*2);ctx.fill();ctx.restore();}return canvas;
}
function blinkLayers(sheet,base,config){
 // Keyframes use the same full portrait framing as the base. Preserve that
 // perspective: registration allows only a tiny translation, never rotation.
 const reference=base.getContext('2d').getImageData(0,0,W,H).data;
 const offsets=[];
 const layers=[0,1].map(column=>{
  const tile=createCanvas(W,H),t=tile.getContext('2d');
  t.drawImage(sheet,column*sheet.width/2,0,sheet.width/2,sheet.height,0,0,W,H);
  const pixels=t.getImageData(0,0,W,H).data;
  const [x,y,width,height]=config.face;let best={error:Infinity,dx:0,dy:0};
  for(let dy=-2;dy<=2;dy++)for(let dx=-2;dx<=2;dx++){
   let error=0,count=0;
   for(let yy=y;yy<y+height;yy+=2)for(let xx=x;xx<x+width;xx+=2){
    if(config.eyes.some(([cx,cy,rx,ry])=>Math.abs(xx-cx)<rx+3&&Math.abs(yy-cy)<ry+3))continue;
    const i=(yy*W+xx)*4,j=((yy-dy)*W+xx-dx)*4;
    for(let c=0;c<3;c++)error+=Math.abs(reference[i+c]-pixels[j+c]);count++;
   }
   error/=count;if(error<best.error)best={error,dx,dy};
  }
  offsets.push([best.dx,best.dy]);
  const layer=createCanvas(W,H),ctx=layer.getContext('2d');ctx.drawImage(tile,best.dx,best.dy);
  ctx.globalCompositeOperation='destination-in';ctx.drawImage(eyeMask(config),0,0);
  return layer;
 });
 return {layers,offsets};
}
function allowedMask(config){
 const canvas=createCanvas(W,H),ctx=canvas.getContext('2d');ctx.fillStyle='white';
 for(const points of config.hair){const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);ctx.fillRect(Math.min(...xs)-2,Math.min(...ys)-2,Math.max(...xs)-Math.min(...xs)+4,Math.max(...ys)-Math.min(...ys)+4);}
 for(const [x,y,rx,ry]of config.eyes)ctx.fillRect(x-rx-2,y-ry-2,2*rx+4,2*ry+4);
 return canvas.getContext('2d').getImageData(0,0,W,H).data;
}
function render(base,layers,config,index){
 const canvas=createCanvas(W,H),ctx=canvas.getContext('2d');ctx.drawImage(base,0,0);
 const phase=Math.sin(2*Math.PI*index/COUNT);
 config.hair.forEach((points,i)=>{ctx.save();polygon(ctx,points);ctx.clip();ctx.drawImage(base,phase*(i%2?-.5:.6),0);ctx.restore();});
 // Genuine half/closed drawings replace eyelids; never dissolve the iris.
 if(index===36||index===38)ctx.drawImage(layers[0],0,0);
 if(index===37)ctx.drawImage(layers[1],0,0);
 return canvas;
}
async function build(gender,sourcePath,outDir,debugDir,blinkPath){
 const config=configs[gender],source=await loadImage(sourcePath);
 const backdrop=gender==='female'?await loadImage(path.join(path.dirname(blinkPath),'yiyi-female-background-v3.png')):null;
 const base=prepare(source,0,config,backdrop);
 const sheet=await loadImage(blinkPath),{layers,offsets}=blinkLayers(sheet,base,config);
 const fixed=base.getContext('2d').getImageData(0,0,W,H).data,mask=allowedMask(config);
 const atlas=createCanvas(W*COLUMNS,H*ROWS),a=atlas.getContext('2d');let changed=0;
 for(let index=0;index<COUNT;index++){
  const frame=render(base,layers,config,index),pixels=frame.getContext('2d').getImageData(0,0,W,H).data;
  for(let i=0;i<pixels.length;i+=4){const different=pixels[i]!==fixed[i]||pixels[i+1]!==fixed[i+1]||pixels[i+2]!==fixed[i+2]||pixels[i+3]!==fixed[i+3];if(different){assert(mask[i+3]>0,`Frame ${index} changed fixed pixel ${i/4}`);changed++;}}
  a.drawImage(frame,(index%COLUMNS)*W,Math.floor(index/COLUMNS)*H);
  if(debugDir&&[0,12,36,37,38].includes(index))fs.writeFileSync(path.join(debugDir,`${gender}-${index}.png`),frame.toBuffer('image/png'));
 }
 fs.mkdirSync(outDir,{recursive:true});

 const bytes=atlas.toBuffer('image/png');fs.writeFileSync(path.join(outDir,`yiyi-${gender}-breeze-atlas-v4.png`),bytes);
 return{gender,frames:COUNT,width:atlas.width,height:atlas.height,bytes:bytes.length,blinkStates:['open','half','closed'],eyeTranslations:offsets,eyeRotation:0,changedPixels:changed,fixedBodyAndBackground:true};
}
if(require.main===module){
 const root=path.join(__dirname,'../stylist/static/assets/characters'),debug=path.join(__dirname,'../var/portrait-local-motion-v4');fs.mkdirSync(debug,{recursive:true});
 Promise.all(['female','male'].map(gender=>build(gender,path.join(root,'sources',`yiyi-${gender}-blink-source-v2.png`),root,debug,path.join(root,'sources',`yiyi-${gender}-blink-source-v4.png`)))).then(results=>{fs.writeFileSync(path.join(debug,'verification.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));}).catch(error=>{console.error(error);process.exitCode=1;});
}
module.exports={build,prepare,render,configs,W,H,COUNT,COLUMNS,ROWS};
