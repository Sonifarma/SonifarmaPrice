const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const center={endereco:'Centro demonstrativo',latitude:0,longitude:0,versao:1,mapa_url:'https://www.openstreetmap.org/'};
  const stores=[
   {id:1,fonte_id:'node/1',nome:'Farmácia de demonstração — filial com nome completo',endereco:'Rua de demonstração, 786, Bairro de teste',distancia_km:.03,grupo:'farmacias_redes',site:'https://www.drogal.com.br/',fonte_url:'https://www.openstreetmap.org/node/1',cnpj:'00000000000191',cnpj_status:'consultado',dados_cnpj:{razao_social:'Empresa demonstrativa de comércio farmacêutico com nome completo',descricao_situacao_cadastral:'ATIVA',cnae_fiscal:4771701,cnae_fiscal_descricao:'Comércio varejista de produtos farmacêuticos',logradouro:'Rua de demonstração',numero:'786',municipio:'Cidade de teste',uf:'SP',consultado_em:'2026-11-08'}},
   {id:2,fonte_id:'node/2',nome:'Supermercado com nome extenso',endereco:'Avenida de demonstração, 1258, Cidade de teste',distancia_km:1.04,grupo:'supermercados',site:null,fonte_url:'https://www.openstreetmap.org/node/2',cnpj:null,cnpj_status:null,dados_cnpj:null},
   {id:3,fonte_id:'node/3',nome:'Loja de teste',endereco:'Endereço ainda incompleto',distancia_km:1.7,grupo:null,site:null,fonte_url:'https://www.openstreetmap.org/node/3',cnpj:'00000000000191',cnpj_status:'falha_consulta',dados_cnpj:null}
  ];
  await page.route('**/api/mercado/centro',route=>route.fulfill({json:{centro:center}}));
  await page.route('**/api/concorrentes?*',route=>route.fulfill({json:{items:stores,total:3,has_more:false,centro:center}}));
  await page.goto(process.env.TEST_URL||'http://127.0.0.1:18770');await page.locator('#shown').filter({hasText:'100'}).waitFor();
  await page.locator('[data-tab=concorrentes]').click();await page.locator('#competitors-count').filter({hasText:'3 no filtro'}).waitFor();
  assert.equal(await page.locator('#competitors-rows tr').count(),3);assert.equal(await page.locator('#competitors-rows tr:first-child > td').count(),4);
  const first=page.locator('#competitors-rows tr').first();assert.match(await first.innerText(),/0,03 km/);
  assert.equal(await first.locator('.directory-registration [data-help-content]').isVisible(),false);
  await first.getByRole('button',{name:/Dados cadastrais/}).click();assert.match(await page.locator('#price-help-popover').innerText(),/Empresa demonstrativa/);assert.match(await page.locator('#price-help-popover').innerText(),/Endereço cadastral/);await page.keyboard.press('Escape');
  await first.locator('.directory-group-reason summary').click();assert.equal(await first.locator('input[aria-label^="Motivo"]').isVisible(),true);await first.locator('.directory-group-reason summary').click();
  for(const width of [1500,1200,1024,768,390]){
   await page.setViewportSize({width,height:1000});
   assert.ok(await page.locator('.directory-scroll').evaluate(n=>n.scrollWidth<=n.clientWidth+1),'rolagem horizontal em '+width);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'pagina larga em '+width);
   if(width===1500||width===390)await page.screenshot({path:'work/concorrentes-'+width+'.png',fullPage:true});
  }
  assert.deepEqual(errors,[]);console.log('Concorrentes OK: tabela/cartoes sem rolagem horizontal, campos compactos, dados em balao, motivo opcional e cinco larguras.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
