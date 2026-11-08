const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1366,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.TEST_URL||'http://127.0.0.1:18770');await page.locator('#shown').filter({hasText:'100'}).waitFor();
  assert.equal(await page.locator('#entry-note').isVisible(),false);
  const help=page.locator('[data-help-for="entry-note"]');await help.click();
  const popup=page.locator('#price-help-popover');await popup.waitFor({state:'visible'});
  assert.match(await popup.innerText(),/Última compra/);assert.equal(await help.getAttribute('aria-expanded'),'true');
  await page.keyboard.press('Escape');assert.equal(await popup.isVisible(),false);assert.equal(await help.evaluate(n=>document.activeElement===n),true);
  for(const tab of ['mercado','concorrentes','importacao','local','integracao']){
   await page.locator('[data-tab="'+tab+'"]').click();assert.ok(await page.locator('#tab-'+tab+' .help-trigger').count()>0,tab);
  }
  await page.locator('[data-tab=mercado]').click();
  await page.evaluate(()=>{const p=document.createElement('p');p.id='help-source-test';p.dataset.helpLabel='Raia';p.textContent='Fonte com mensagem completa. ';const a=document.createElement('a');a.href='https://www.drogaraia.com.br/';a.textContent='Conferir fonte';p.append(a);document.querySelector('#online-sources').append(p);});
  await page.locator('[data-help-for=help-source-test]').click();assert.match(await popup.innerText(),/Fonte com mensagem completa/);assert.equal(await popup.locator('a').count(),1);assert.equal(await page.locator('#help-source-test').isVisible(),false);await page.keyboard.press('Escape');
  await page.locator('[data-tab=integracao]').click();
  assert.equal(await page.locator('#tab-integracao pre').isVisible(),false);
  await page.locator('#tab-integracao .panel .help-trigger').first().click();assert.match(await popup.innerText(),/diagnostico_compras/);
  await page.locator('#price-help-popover .help-dismiss').click();
  await page.locator('[data-tab=produtos]').click();
  await page.evaluate(()=>window.PriceHelp.message('msg','Falha <img src=x onerror=alert(1)>. Tente novamente.',true));
  const failure=page.locator('[data-help-for=msg]');assert.equal(await failure.getAttribute('data-kind'),'error');assert.match(await failure.innerText(),/Erro/);
  await failure.click();assert.match(await popup.innerText(),/<img src=x/);assert.equal(await popup.locator('img').count(),0);
  await page.evaluate(()=>window.PriceHelp.message('msg','Consulta retomada. Dados atuais.',false));assert.match(await popup.innerText(),/Consulta retomada/);assert.doesNotMatch(await popup.innerText(),/Falha/);
  await page.evaluate(()=>window.PriceHelp.message('msg','',false));assert.equal(await popup.isVisible(),false);assert.equal(await failure.isVisible(),false);
  await page.evaluate(()=>{const p=document.createElement('p');p.className='warning';p.textContent='Aviso dinâmico: coleta anterior.';document.querySelector('#tab-produtos .panel').append(p);});
  const warning=page.locator('#tab-produtos .help-trigger[data-kind=warning]');await warning.waitFor();await warning.click();assert.match(await popup.innerText(),/coleta anterior/);
  await page.locator('#q').click();assert.equal(await popup.isVisible(),false);
  await page.evaluate(()=>{const row=document.createElement('tr');const td=document.createElement('td');td.className='condition-info';td.textContent='Oferta no Pix; conferir condições.';row.append(td);document.querySelector('#online-rows').append(row);});
  const pix=page.locator('#online-rows .help-trigger').filter({hasText:'Pix'});await pix.waitFor({state:'attached'});
  assert.equal(await page.locator('#online-rows tr:last-child > td').count(),1);assert.equal(await page.locator('#online-rows tr:last-child > span').count(),0);
  await page.evaluate(()=>document.querySelector('#product-dialog').showModal());
  const inside=page.locator('#product-dialog .help-trigger:visible').first();await inside.click();assert.equal(await popup.evaluate(n=>n.parentElement.id),'product-dialog');
  assert.equal(await popup.isVisible(),true);await page.keyboard.press('Escape');assert.equal(await popup.isVisible(),false);assert.equal(await page.locator('#product-dialog').evaluate(n=>n.open),true);
  await page.locator('#detail-close').click();
  await page.setViewportSize({width:390,height:844});await help.click();await popup.waitFor({state:'visible'});
  const rect=await popup.boundingBox();assert.ok(rect.x>=0&&rect.x+rect.width<=390&&rect.y>=0&&rect.y+rect.height<=844);
  await page.screenshot({path:'work/balao-ajuda-mobile.png'});await page.keyboard.press('Escape');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.deepEqual(errors,[]);console.log('Baloes OK: todas as telas, clique, Escape/foco, dialogo, avisos dinamicos, erro, texto seguro e mobile.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
