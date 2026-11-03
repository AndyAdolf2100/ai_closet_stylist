// Synthetic content exercises native card branches; no user images or business calls.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  fs.mkdirSync('var/closet-app-parity-pass2', {recursive:true});
  let checks = 0;
  for (const [width,height] of [[393,852],[320,568],[844,390]]) {
    const context = await browser.newContext({viewport:{width,height}}), page = await context.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.addInitScript(() => sessionStorage.setItem('ai-closet-stylist-session-v1', JSON.stringify({access_token:'fixture',user:{id:'fixture'}})));
    await page.route('**/stylist-api/app/**', async route => {
      const section = new URL(route.request().url()).pathname.split('/').at(-1);
      const cover = '/static/closet-app/assets/home_album_empty.png';
      const items = [0,1,4,8].map((count,i) => ({id:i,title:`造型 ${count} 件`,description:'仅用于布局检查的合成记录。',fitting_image_url:cover,product_count:count,source_label:'试衣',context_text:'日常',weather:{condition:'晴',temp:'18'},product_images:Array.from({length:count},()=>({title:'单品示意',image_url:'/static/closet-app/assets/wardrobe_action_products.png'}))}));
      const data = section === 'album' ? {items,has_more:false} : {list:[.8,1.5,1,1.2].map((ratio,i)=>({id:i,title:`灵感 ${i}`,summary:'保留原图比例与摘要',cover_image:cover,cover_width:100,cover_height:ratio*100}))};
      await route.fulfill({contentType:'application/json',body:JSON.stringify({data})});
    });
    await page.goto((process.env.STYLIST_APP_URL || 'http://127.0.0.1:8478') + '/app/');
    await page.locator('.album-card').last().waitFor();
    assert.equal(await page.locator('.album-multiple').count(),2); checks++;
    assert.equal(await page.locator('.album-single').count(),2); checks++;
    for (const card of await page.locator('.album-multiple').all()) {
      const geometry = await card.evaluate(c => {
        const stage = c.querySelector('.album-stage').getBoundingClientRect(), rail = c.querySelector('.album-garments').getBoundingClientRect(), image = c.querySelector('.album-result').getBoundingClientRect();
        return {gap:image.left-rail.right,bottom:rail.bottom<=stage.bottom+1,ratio:stage.height/stage.width};
      });
      assert(Math.abs(geometry.gap-5)<1); assert(geometry.bottom); assert(Math.abs(geometry.ratio-388/367)<.01); checks+=3;
    }
    await page.screenshot({path:`var/closet-app-parity-pass2/album-${width}.png`,fullPage:true});
    await page.locator('[data-feed="inspiration"]').click(); await page.locator('.inspiration-card').last().waitFor(); await page.waitForTimeout(150);
    const boxes = await page.locator('.inspiration-card').evaluateAll(cards => cards.map(c=>{const b=c.getBoundingClientRect(),p=c.querySelector('img').getBoundingClientRect();return {x:b.x,y:b.y,bottom:b.bottom,ratio:p.height/p.width};}));
    assert(Math.abs(boxes[0].ratio-.8)<.01); assert(Math.abs(boxes[1].ratio-1.5)<.01); assert.equal(boxes[2].x,boxes[0].x); assert(Math.abs(boxes[2].y-boxes[0].bottom-12)<1); checks+=4;
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)); checks++;
    await page.screenshot({path:`var/closet-app-parity-pass2/inspiration-${width}.png`,fullPage:true});
    await page.locator('#create-toggle').click(); const last = page.locator('.create-wide').last(); await last.scrollIntoViewIfNeeded();
    const rect = await last.boundingBox(), bar = await page.locator('.floating-bar').boundingBox(); assert(rect.y>=0 && rect.y+rect.height<=bar.y+1); checks++;
    assert.deepEqual(errors,[]); checks++;
    await context.close();
  }
  await browser.close(); console.log(`${checks} card and short-screen parity checks passed`);
})().catch(e=>{console.error(e);process.exit(1)});
