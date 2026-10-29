const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('stylist/static/app.js','utf8');
function render(item){
 const doc=new JSDOM('<body></body>').window.document;
 const el=(tag,cls,text)=>{const node=doc.createElement(tag);node.className=cls||'';if(text)node.textContent=text;return node};
 const code=source.slice(source.indexOf('function productGrid('),source.indexOf('function showReply('));
 return new Function('el',code+';return productGrid;')(el)([item]);
}
test('wardrobe photo uses cutout, retains original preview and falls back on failure',()=>{
 const grid=render({cutout_image:'https://example.invalid/cutout.png',original_image:'https://example.invalid/original.jpg',source:'user'});
 const img=grid.querySelector('img');assert.equal(img.src,'https://example.invalid/cutout.png');
 assert.equal(grid.querySelector('button').dataset.previewSrc,'https://example.invalid/original.jpg');
 img.onerror();assert.equal(img.src,'https://example.invalid/original.jpg');img.onerror();
 assert(!grid.querySelector('img'));assert(grid.querySelector('.product-image-missing'));
});
test('missing or unsafe photos stay explicit and never execute URLs',()=>{
 for(const item of [{},{cutout_image:'javascript:alert(1)'}]){
  const grid=render(item);assert(!grid.querySelector('img'));assert.match(grid.textContent,/暂无衣物图片/);
 }
 const grid=render({cutout_image:'javascript:alert(1)',original_image:'https://example.invalid/real.jpg'});
 assert.equal(grid.querySelector('img').src,'https://example.invalid/real.jpg');
});
test('report renders photo cards rather than only names and keeps missing photos explicit',()=>{
 const document=new JSDOM('<body></body>').window.document;
 const template=fs.readFileSync('scripts/report_assets/dialogue_report.html','utf8');
 const code=template.slice(template.indexOf('function itemCard('),template.indexOf('function card(row)'));
 const make=(tag,cls,text)=>{const n=document.createElement(tag);n.className=cls||'';if(text)n.textContent=text;return n};
 const card=new Function('make',code+';return itemCard;')(make);
 const item=card({title:'测试衬衫',product_id:'fixture',cutout_image:'https://example.invalid/cut.png',original_image:'https://example.invalid/original.jpg'});
 assert.equal(item.querySelector('img').alt,'测试衬衫');assert.equal(item.querySelector('a').href,'https://example.invalid/original.jpg');
 const img=item.querySelector('img');img.onerror();assert.equal(img.src,'https://example.invalid/original.jpg');img.onerror();assert.match(item.textContent,/加载失败/);
 assert.match(card({original_image:'javascript:alert(1)'}).textContent,/未提供衣物照片/);
});
