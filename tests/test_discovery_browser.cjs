const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const browser = await chromium.launch({executablePath: process.env.CHROMIUM_EXECUTABLE || '/usr/bin/chromium', headless: true, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    let searchCount = 0, saved = false;
    await page.route('**/api/descoberta/**', async route => {
      const req = route.request();
      assert.equal(req.headers()['x-price-token'], 'local-test');
      if (req.method() === 'PUT') {
        const body = req.postDataJSON();
        assert.equal(body.grupo, 'farmacias_independentes'); assert.equal(body.motivo, 'Confirmado em teste');
        saved = true;
        return route.fulfill({json: {mensagem: 'Aplicado nas proximas pesquisas'}});
      }
      if (req.url().includes('historico')) {
        return route.fulfill({json: {execucoes: [{id: 1, criado_em: '2026-11-07T12:00:00Z', estado: 'concluido', resultado: {validos: 0, raios_consultados: [2,3,5,8,10]}}]}});
      }
      const body = req.postDataJSON();
      assert.equal(body.coordenadas_confirmadas, true); assert.deepEqual(body.raios_km, [2,3,5,8,10]);
      searchCount++;
      return route.fulfill({status: searchCount === 1 ? 200 : 502, json: {
        execucao_id: searchCount, estado: searchCount === 1 ? 'concluido' : 'parcial', validos: 0,
        meta_atingida: false, raios_consultados: [2,3,5,8,10], aviso: 'Cadastro nao confirma precos.',
        falhas: searchCount === 1 ? [] : [{mensagem: 'indisponivel'}],
        estabelecimentos: [{nome: '<img src=x onerror=alert(1)>', fonte_id: 'node/1', grupo: null,
          bloqueado: false, classificacao_motivo: 'farmacia: revisar rede ou independente',
          distancia_km: 1.2, url: 'https://www.openstreetmap.org/node/1'}]
      }});
    });
    await page.goto(process.env.TEST_URL || 'http://127.0.0.1:18770');
    await page.locator('#discovery-token').fill('local-test');
    await page.locator('#discovery-lat').fill('0'); await page.locator('#discovery-lon').fill('0');
    await page.locator('#discovery-confirm').check();
    await page.locator('#discovery-search').click();
    await page.getByText('Execução 1:', {exact: false}).waitFor();
    assert.equal(await page.locator('#discovery-rows img').count(), 0);
    assert.equal(await page.locator('#discovery-rows tr').count(), 1);
    await page.locator('#discovery-rows select').selectOption('farmacias_independentes');
    await page.locator('#discovery-rows input[placeholder="Motivo da correção"]').fill('Confirmado em teste');
    await page.getByRole('button', {name: 'Salvar revisão'}).click();
    await page.getByText('Aplicado nas proximas pesquisas', {exact: true}).waitFor(); assert.ok(saved);
    await page.locator('#discovery-history').click();
    await page.locator('#discovery-runs').filter({hasText: '#1'}).waitFor();
    await page.locator('#discovery-search').click();
    await page.getByText('Execução 2:', {exact: false}).waitFor();
    assert.match(await page.locator('#discovery-message').innerText(), /fonte falhou/);
    await page.setViewportSize({width: 390, height: 844});
    assert.ok(await page.locator('#discovery-search').isVisible());
    assert.deepEqual(errors, []);
    console.log('Browser OK: pesquisa, revisao, historico, falha parcial e escape de HTML.');
  } finally { await browser.close(); }
})().catch(e => {console.error(e); process.exitCode = 1;});
