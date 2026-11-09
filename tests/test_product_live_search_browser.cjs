const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
const page=await browser.newPage({viewport:{width:1500,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
const queries=[];page.on('request',r=>{if(r.url().includes('/api/revisao/produtos?'))queries.push(new URL(r.url()).searchParams);});
await page.goto('http://127.0.0.1:18770');await page.locator('#shown').filter({hasText:'100'}).waitFor();
assert.equal(await page.locator('#search-mode').count(),0);
await page.locator('#only-review').uncheck();await page.locator('#search').click();await page.locator('#product-scroll[aria-busy=false]').waitFor();
async function search(text,expected){const response=page.waitForResponse(r=>r.url().includes('/api/revisao/produtos?')&&new URL(r.url()).searchParams.get('q')===text);await page.locator('#q').fill(text);await response;await page.locator('#rows').filter({hasText:expected}).waitFor();assert.equal(queries.at(-1).get('modo'),'produto');assert.equal(queries.at(-1).get('offset'),'0');}
await search('duto A','Produto A');assert.equal(await page.locator('#rows tr').count(),1);
await search('96385074','Produto B');assert.equal(await page.locator('#rows tr').count(),1);
await search('209','Produto de teste 109');assert.equal(await page.locator('#rows tr').count(),1);
const before=queries.length;await page.locator('#q').fill('Pro');await page.locator('#q').fill('Produ');await page.locator('#q').fill('Produto A');await page.waitForTimeout(600);assert.equal(queries.length,before+1);
const enterCount=queries.length;await page.locator('#q').fill('001');await page.locator('#q').press('Enter');await page.waitForTimeout(600);assert.equal(queries.length,enterCount+1);assert.match(await page.locator('#rows').innerText(),/Produto A/);
const item=label=>({embalagem_id:999,descricao:label,ean:'4006381333931',codigo:'999',preco:10,custo:8,revisar:true,motivo_descricao:'Teste'});
await page.route('**/api/revisao/produtos?*',async route=>{const q=new URL(route.request().url()).searchParams.get('q');if(!['lento','rapido'].includes(q))return route.continue();if(q==='lento')await new Promise(r=>setTimeout(r,900));await route.fulfill({json:{items:[item(q==='lento'?'RESULTADO ANTIGO':'RESULTADO ATUAL')],total:1,has_more:false,criterio:'Teste'}}).catch(()=>{});});
const slow=page.waitForRequest(r=>r.url().includes('/api/revisao/produtos?')&&new URL(r.url()).searchParams.get('q')==='lento');await page.locator('#q').fill('lento');await slow;
await search('rapido','RESULTADO ATUAL');await page.waitForTimeout(1000);assert.doesNotMatch(await page.locator('#rows').innerText(),/RESULTADO ANTIGO/);
await page.unroute('**/api/revisao/produtos?*');await search('','Produto A');assert.ok(await page.locator('#rows tr').count()>=100);
const composeCount=queries.length;await page.locator('#q').dispatchEvent('compositionstart');await page.locator('#q').fill('Produto A');await page.waitForTimeout(500);assert.equal(queries.length,composeCount);await page.locator('#q').dispatchEvent('compositionend');await page.locator('#rows').filter({hasText:'Produto A'}).waitFor();await page.waitForTimeout(500);assert.equal(queries.length,composeCount+1);
await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
console.log('Busca unica OK: descricao parcial, EAN, codigo, debounce, Enter, resposta antiga, limpeza, composicao e mobile.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
