const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync(path.join(__dirname,'../stylist/static/companion-portraits.js'),'utf8');
function setup(width=350,height=400){
 const dom=new JSDOM('<dialog open><label class="companion-person"><img src="fallback.jpg"><span class="companion-portrait" data-portrait="female"></span></label><label class="companion-person"><img src="fallback.jpg"><span class="companion-portrait" data-portrait="male"></span></label></dialog>',{runScripts:'outside-only'}),w=dom.window;
 const images=[],observers=[];let size={width,height};
 w.Image=class{constructor(){images.push(this);this.naturalWidth=3072;this.naturalHeight=3072;}set src(v){this.source=v;}};
 w.ResizeObserver=class{constructor(cb){this.cb=cb;observers.push(this);}observe(){}disconnect(){this.disconnected=true;}};
 const cards=[...w.document.querySelectorAll('.companion-person')];
 for(const card of cards)Object.defineProperties(card,{clientWidth:{get:()=>size.width},clientHeight:{get:()=>size.height}});
 w.eval(source);const root=w.document.querySelector('dialog'),dispose=w.CompanionPortraits.mount(root);
 return{w,dom,images,observers,cards,root,dispose,resize(width,height){size={width,height};observers[0].cb(cards.map(target=>({target})));}};
}
test('male/female atlases use equal cover geometry without stretching faces',()=>{
 const t=setup();assert.equal(t.w.CompanionPortraits.frames,48);
 t.images.forEach(img=>img.onload());
 const sprites=t.cards.map(card=>card.querySelector('.companion-portrait'));
 assert.equal(sprites[0].style.width,sprites[1].style.width);assert.equal(sprites[0].style.height,sprites[1].style.height);
 assert.equal(parseFloat(sprites[0].style.width),350);assert.equal(sprites[0].style.top,'0px');assert.equal(sprites[1].style.top,'0px');assert(Math.abs(parseFloat(sprites[0].style.height)-350/0.75)<0.001);
 assert(t.images[0].source.endsWith('female-breeze-atlas-v2.png'));assert(t.images[1].source.endsWith('male-breeze-atlas-v2.png'));
 t.resize(136,225);assert.equal(parseFloat(sprites[0].style.height),225);assert.equal(parseFloat(sprites[0].style.width),168.75);
 t.dom.window.close();
});
test('hidden/loading portraits retain a static fallback and resize correctly on reveal',()=>{
 const t=setup(0,0);assert(t.cards.every(card=>!card.classList.contains('portrait-ready')));assert(t.cards.every(card=>card.querySelector('img')));
 t.images.forEach(img=>img.onload());assert.equal(t.cards[0].querySelector('span').style.width,'');
 t.resize(150,240);assert.equal(t.cards[0].querySelector('span').style.height,'240px');t.dom.window.close();
});
test('background tabs pause portraits and dispose removes observer/listener',()=>{
 const t=setup();Object.defineProperty(t.w.document,'hidden',{configurable:true,value:true});t.w.document.dispatchEvent(new t.w.Event('visibilitychange'));assert(t.root.classList.contains('portraits-paused'));
 Object.defineProperty(t.w.document,'hidden',{configurable:true,value:false});t.w.document.dispatchEvent(new t.w.Event('visibilitychange'));assert(!t.root.classList.contains('portraits-paused'));
 t.dispose();assert(t.observers[0].disconnected);t.dom.window.close();
});
