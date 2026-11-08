(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const present = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const money = value => present(value) ? Number(value).toLocaleString('pt-BR', {style:'currency',currency:'BRL'}) : '—';
  const number = value => present(value) ? Number(value).toLocaleString('pt-BR', {maximumFractionDigits:2}) : '—';
  const dateBR = value => {const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})/);return match ? `${match[3]}/${match[2]}/${match[1]}` : 'Não informada';};
  const groups = {supermercados:'Supermercados e atacarejos',perfumarias:'Perfumarias',farmacias_redes:'Farmácias de rede',farmacias_independentes:'Farmácias independentes'};
  let onlineController,onlineRequest=0,onlineScope=null,detailOnlineRequest=0;
  const onlinePending=new Map(),onlineChoices=new Map();
  let entryAvailable = false,periodPresets={},loadingProducts=false,appendFailed=false, current = [], applied = null, offset = 0, hasMore = false, dirty = false;
  let controller, requestId = 0, marketController, marketRequest = 0, marketItems = [];
  let detailController,detailId=0,activeProduct=null,storesController,storesId=0,storesOffset=0;
  let savedCenter=null, chosenCenter=null, centerLookupId=0, centerController;
  let marketSelection=null, lookupController, lookupId=0, lookupTimer, lookupRows=[], lookupQuery="", lookupMore=false;
  function tab(name) {
    if(name==='concorrentes')loadCompetitors();
    if(name==='mercado')loadSavedStores();
    document.querySelectorAll('.tab').forEach(section => {section.hidden = section.id !== 'tab-' + name;});
    document.querySelectorAll('.nav').forEach(button => {
      const active = button.dataset.tab === name;button.classList.toggle('active', active);
      if (active) button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
    });
  }
  document.querySelectorAll('.nav').forEach(button => button.addEventListener('click', () => tab(button.dataset.tab)));
  function message(id, text, error = false) {window.PriceHelp.message(id,text,error);}
  async function json(url, options = {}) {
    const response = await fetch(url, options), data = await response.json();
    if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data));
    return data;
  }
  function cell(row, value, className = '') {
    const td = document.createElement('td');td.textContent = value;td.className = className;row.append(td);return td;
  }
  function empty(body, text, span) {
    body.replaceChildren();const row = document.createElement('tr'), td = cell(row, text, 'empty');td.colSpan=span;body.append(row);
  }
  function updatePages() {
    $('next').disabled=!applied||!hasMore||dirty||loadingProducts;
    $('next').hidden=!hasMore&&!appendFailed;
    $('next').textContent=appendFailed?'Tentar carregar mais novamente':'Carregar mais';
    $('export').disabled=current.length===0;
  }
  function periodFields(syncDates=true) {
    const selected=$('period').value,preset=periodPresets[selected];
    if(syncDates&&selected!=='intervalo'&&preset){$('date-start').value=preset.inicio||'';$('date-end').value=preset.fim||'';}
    $('date-start').disabled=false;$('date-end').disabled=false;
    $('date-start').required=selected==='intervalo';$('date-end').required=selected==='intervalo';
    $('date-end').setCustomValidity('');
    const label=$('period').selectedOptions[0].textContent;
    const range=$('date-start').value&&$('date-end').value?`${dateBR($('date-start').value)} a ${dateBR($('date-end').value)}`:$('date-end').value?'Até '+dateBR($('date-end').value):'';
    $('period-summary').textContent=label+(range?' · '+range:'');
  }
  function validPeriod() {
    if ($('period').value === 'intervalo' && (!$('date-start').value || !$('date-end').value || $('date-start').value > $('date-end').value)) {
      $('date-end').setCustomValidity('Informe as duas datas, com a final igual ou posterior à inicial.');
      $('period-filter').open=true;$('date-end').reportValidity();return false;
    }
    $('date-end').setCustomValidity('');return true;
  }
  function markDirty() {dirty=true;controller?.abort();requestId++;loadingProducts=false;$('product-scroll').setAttribute('aria-busy','false');updatePages();message('msg','Filtros alterados. Clique em Consultar produtos para aplicar.');}
  $('period').addEventListener('change', () => {periodFields();markDirty();});
  ['date-start','date-end'].forEach(id => $(id).addEventListener('input', () => {$('period').value='intervalo';periodFields(false);markDirty();}));
  $('period-done').addEventListener('click', () => {if(validPeriod()) $('period-filter').open=false;});
  document.addEventListener('click', event => {if(!$('period-filter').contains(event.target)) $('period-filter').open=false;});
  $('period-filter').addEventListener('keydown', event => {if(event.key==='Escape') {$('period-filter').open=false;$('period-filter').querySelector('summary').focus();}});
  ['q','search-mode','min-margin','only-review','stock-only','price-type','product-status'].forEach(id => $(id).addEventListener('input',markDirty));
  function parameters() {
    const params = new URLSearchParams({q:$('q').value,modo:$('search-mode').value,periodo:$('period').value,data_filtro:'compra',tipo_preco:$('price-type').value,status_produto:$('product-status').value,
      margem_minima:$('min-margin').value,somente_revisar:String($('only-review').checked),somente_estoque:String($('stock-only').checked),limit:'100'});
    if($('period').value==='intervalo') {params.set('inicio',$('date-start').value);params.set('fim',$('date-end').value);}
    return params;
  }
  function renderProducts(items,append=false) {
    if(!append)$('rows').replaceChildren();
    if(!items.length&&!append) {empty($('rows'),'Nenhum produto encontrado com os filtros aplicados.',9);return;}
    items.forEach(item => {
      const row=document.createElement('tr'), product=cell(row,'','product');row.dataset.embalagemId=String(item.embalagem_id);
      const name=document.createElement('button');name.type='button';name.className='product-link';name.textContent=item.descricao || 'Sem descrição';name.addEventListener('click',()=>openProduct(item));product.append(name);
      const detail=document.createElement('small');detail.textContent=`EAN: ${item.ean || 'não informado'} · Código: ${item.codigo || '—'} · ${item.apresentacao || ''}`;product.append(detail);
      cell(row,money(item.preco),'num');cell(row,money(item.custo),'num');
      cell(row,present(item.margem_bruta)?number(item.margem_bruta)+'%':'—','num');
      cell(row,number(item.estoque),'num');cell(row,number(item.vendas30),'num');cell(row,dateBR(item.ultima_compra));
      const badge=document.createElement('span');badge.className='badge '+(item.motivo_revisao==='margem_baixa'?'attention':item.revisar?'danger':'ok');badge.textContent=item.motivo_descricao;
      cell(row,'').append(badge);
      const button=document.createElement('button');button.className='small-btn';button.type='button';button.textContent='Consultar mercado';button.disabled=!item.ean&&!(item.descricao||'').trim();
      button.addEventListener('click',()=>{
        chooseMarketProduct(item);tab('mercado');$('market-search').focus();
      });cell(row,'').append(button);$('rows').append(row);
    });
  }
  async function load(params,nextOffset=0,append=false) {
    if(append&&(loadingProducts||dirty||!hasMore))return;
    controller?.abort();controller=new AbortController();const token=++requestId;
    params=new URLSearchParams(params);params.set('offset',String(nextOffset));loadingProducts=true;appendFailed=false;
    $('product-scroll').setAttribute('aria-busy','true');updatePages();
    message('msg',append?'Carregando mais produtos…':'Consultando produtos no Alpha7…');
    try {
      const data=await json('/api/revisao/produtos?'+params,{signal:controller.signal});
      if(token!==requestId)return;
      const seen=new Set(append?current.map(row=>String(row.embalagem_id)):[]);
      const incoming=data.items.filter(row=>{const key=String(row.embalagem_id);if(seen.has(key))return false;seen.add(key);return true;});
      current=append?[...current,...incoming]:incoming;offset=nextOffset+data.items.length;hasMore=data.has_more;applied=new URLSearchParams(params);
      const withoutOffset=new URLSearchParams(params);withoutOffset.delete('offset');dirty=withoutOffset.toString()!==parameters().toString();
      renderProducts(incoming,append);if(!append)$('product-scroll').scrollTop=0;
      $('total').textContent=number(data.total);$('shown').textContent=number(current.length);
      $('low-margin').textContent=number(current.filter(r=>r.motivo_revisao==='margem_baixa').length);
      $('inconsistent').textContent=number(current.filter(r=>['preco_inconsistente','custo_inconsistente'].includes(r.motivo_revisao)).length);
      $('applied').textContent=`${{liberado:'Liberado',monitorado:'Monitorado',todos:'Todos os preços'}[params.get('tipo_preco')]} · ${{ativo:'Ativo',inativo:'Inativo',todos:'Todos os status'}[params.get('status_produto')]} · Margem mínima: ${number(params.get('margem_minima'))}%`;
      $('page-label').textContent=current.length?`${current.length} carregados${data.total!==null?' de '+number(data.total):''}`+(hasMore?' · Role para carregar mais':' · Fim da lista'):'Nenhum produto no filtro';
      message('msg',`${current.length} produtos carregados${data.demo?' · DEMONSTRAÇÃO':''}. ${data.criterio}`+(dirty?' Filtros alterados; consulte novamente.':''));
    }catch(error){
      if(error.name==='AbortError'||token!==requestId)return;
      if(append){appendFailed=true;message('msg','Falha ao carregar mais. Itens anteriores preservados. '+error.message,true);}
      else {current=[];applied=null;hasMore=false;renderProducts([]);['total','shown','low-margin','inconsistent'].forEach(id=>$(id).textContent='—');$('page-label').textContent='';$('applied').textContent='';message('msg',error.message,true);}
    }finally{if(token===requestId){loadingProducts=false;$('product-scroll').setAttribute('aria-busy','false');updatePages();}}
  }
  function loadMore(){if(applied&&!loadingProducts&&!dirty&&hasMore)load(applied,offset,true);}
  $('product-form').addEventListener('submit',event=>{event.preventDefault();if(validPeriod()){$('period-filter').open=false;load(parameters());}});
  $('next').addEventListener('click',loadMore);
  $('product-scroll').addEventListener('scroll',()=>{const box=$('product-scroll');if(!appendFailed&&box.scrollTop+box.clientHeight>=box.scrollHeight-100)loadMore();});
  const productObserver=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)&&!appendFailed)loadMore();},{root:$('product-scroll'),rootMargin:'0px 0px 100px 0px'});
  productObserver.observe($('product-sentinel'));
  $('purchase-without-date').addEventListener('click',()=>{$('period').value='todos';periodFields();$('period-filter').open=false;load(parameters());});
  $('clear').addEventListener('click',()=>{$('product-form').reset();periodFields();$('period-filter').open=false;load(parameters());});
  $('export').addEventListener('click',()=>{
    const escape=value=>{let text=String(value??'');if(/^[\s]*[=+\-@]/.test(text))text="'"+text;return '"'+text.replace(/"/g,'""')+'"';};
    const columns=[['codigo','Código'],['ean','EAN'],['descricao','Produto'],['preco','Preço atual'],['custo','Custo'],['margem_bruta','Margem bruta (%)'],['estoque','Estoque'],['ultima_compra','Última compra'],['motivo_descricao','Motivo']];
    const lines=[columns.map(c=>escape(c[1])).join(';'),...current.map(row=>columns.map(c=>escape(row[c[0]])).join(';'))];
    const url=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download='SonifarmaPrice_itens_carregados.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  function resetMarket() {
    clearOnline();
    marketController?.abort();marketRequest++;marketItems=[];renderMarket();$('market-search').disabled=false;clearStores('Centro recarregado. Carregando os concorrentes cadastrados no raio atual.');loadSavedStores();if(marketSelection?.ean||marketSelection?.descricao)loadOnline();
  }
  function showCenter() {
    $('center-current').textContent=savedCenter?savedCenter.endereco:'Nenhum endereço cadastrado.';
    $('center-map').hidden=!savedCenter;
    if(savedCenter)$('center-map').href=savedCenter.mapa_url;
    $('market-center').textContent=savedCenter?'Centro do raio: '+savedCenter.endereco:'Cadastre e confirme o endereço do centro antes de consultar por raio.';
  }
  async function loadCenter() {
    const data=await json('/api/mercado/centro');savedCenter=data.centro;showCenter();
    if(savedCenter)$('center-address').value=savedCenter.endereco;
  }
  $('open-center').addEventListener('click',()=>{tab('local');$('center-address').focus();});
  $('center-return').addEventListener('click',()=>tab('mercado'));
  function cancelCenterLookup() {
    centerController?.abort();centerLookupId++;chosenCenter=null;
    $('center-candidates').replaceChildren();$('center-save').disabled=true;$('center-find').disabled=false;
  }
  $('center-address').addEventListener('input',()=>{cancelCenterLookup();message('center-message','Endereço alterado. Busque e confirme o novo ponto antes de salvar.');});
  $('center-reload').addEventListener('click',async()=>{
    cancelCenterLookup();
    try{await loadCenter();resetMarket();message('center-message','Cadastro recarregado.');}catch(error){message('center-message',error.message,true);}
  });
  const configHeaders=()=>({'Content-Type':'application/json','X-Price-Config':'1'});
  $('center-form').addEventListener('submit',async event=>{
    event.preventDefault();cancelCenterLookup();centerController=new AbortController();const token=++centerLookupId;
    $('center-find').disabled=true;message('center-message','Buscando endereço…');
    try{
      const data=await json('/api/mercado/centro/buscar',{method:'POST',headers:configHeaders(),body:JSON.stringify({endereco:$('center-address').value.trim()}),signal:centerController.signal});
      if(token!==centerLookupId)return;
      data.candidatos.forEach(candidate=>{
        const label=document.createElement('label');label.className='center-option';
        const radio=document.createElement('input');radio.type='radio';radio.name='center-candidate';radio.value=candidate.candidato_id;
        const address=document.createElement('span');address.textContent=candidate.endereco;
        const precision=document.createElement('small');precision.className='muted';precision.style.display='block';precision.textContent=['house','building','entrance','house_number'].includes(candidate.tipo)?'Ponto de endereço/edificação — confira no mapa.':'Ponto aproximado de rua ou região — confira no mapa.';address.append(precision);
        const map=document.createElement('a');map.href=candidate.mapa_url;map.textContent='Conferir no mapa';map.target='_blank';map.rel='noopener';
        radio.addEventListener('change',()=>{chosenCenter=candidate;$('center-save').disabled=false;});
        label.append(radio,address,map);$('center-candidates').append(label);
      });
      message('center-message',data.candidatos.length?'Selecione e confira o ponto encontrado; depois confirme e salve.':'Nenhum endereço encontrado. Inclua número, bairro, cidade, estado e país.');
    }catch(error){if(error.name!=='AbortError'&&token===centerLookupId)message('center-message',error.message,true);}
    finally{if(token===centerLookupId)$('center-find').disabled=false;}
  });
  $('center-save').addEventListener('click',async()=>{
    if(!chosenCenter)return;
    const candidate=chosenCenter,token=centerLookupId;$('center-save').disabled=true;
    try{
      const data=await json('/api/mercado/centro',{method:'PUT',headers:configHeaders(),body:JSON.stringify({candidato_id:candidate.candidato_id,versao:savedCenter?.versao||0})});
      savedCenter=data.centro;showCenter();resetMarket();
      if(token===centerLookupId){$('center-address').value=savedCenter.endereco;cancelCenterLookup();message('center-message','Centro salvo. O raio será aplicado a partir deste endereço.');}
    }catch(error){message('center-message',error.message,true);if(token===centerLookupId)$('center-save').disabled=false;}
  });
  function closeSuggestions() {
    clearTimeout(lookupTimer);lookupController?.abort();lookupId++;
    $('market-suggestions').hidden=true;$('eanmerc').setAttribute('aria-expanded','false');
  }
  function chooseMarketProduct(item) {
    clearOnline();
    closeSuggestions();marketSelection=item;$('eanmerc').value=item.ean||item.descricao||'';
    $('selected-product').textContent=item.descricao || 'Consultar produto';$('selected-product').disabled=!item.embalagem_id;
    marketController?.abort();marketRequest++;marketItems=[];renderMarket();$('market-search').disabled=false;
    message('marketmsg','Produto selecionado. Os preços online serão consultados quando o centro e o raio estiverem válidos.');
    if(savedCenter)loadOnline();else message('online-message','Cadastre o centro da pesquisa para carregar os preços online deste produto.');
  }
  function suggestionMessage(text) {
    const note=document.createElement('div');note.className='suggestion-message';note.textContent=text;
    $('market-suggestions').append(note);
  }
  function renderSuggestions() {
    const box=$('market-suggestions');box.replaceChildren();box.hidden=false;$('eanmerc').setAttribute('aria-expanded','true');
    if(!lookupRows.length)suggestionMessage('Nenhum produto encontrado. Tente outra parte da descrição ou informe o EAN.');
    lookupRows.forEach(item=>{
      const option=document.createElement('button');option.type='button';option.className='product-option';
      option.textContent=item.descricao || 'Sem descrição';
      const detail=document.createElement('small');detail.textContent=`${item.apresentacao || ''} · EAN: ${item.ean || 'não informado'}`;option.append(detail);
      option.disabled=!item.ean&&!(item.descricao||'').trim();
      if(!/^[0-9]{8,14}$/.test(String(item.ean||'')))detail.append(' · Consulta online pela descrição');
      option.addEventListener('click',()=>{chooseMarketProduct(item);$('market-search').focus();});
      box.append(option);
    });
    if(lookupMore){const more=document.createElement('button');more.type='button';more.className='product-option';more.textContent='Carregar mais produtos';more.addEventListener('click',()=>lookupProducts(lookupQuery,true));box.append(more);}
  }
  async function lookupProducts(query, append=false) {
    clearTimeout(lookupTimer);lookupController?.abort();lookupController=new AbortController();const token=++lookupId;
    if(!append){lookupRows=[];lookupQuery=query;}
    const box=$('market-suggestions');box.replaceChildren();box.hidden=false;$('eanmerc').setAttribute('aria-expanded','true');suggestionMessage('Buscando produtos…');
    try {
      const params=new URLSearchParams({q:query,limit:'20',offset:String(append?lookupRows.length:0)});
      const data=await json('/api/mercado/produtos?'+params,{signal:lookupController.signal});
      if(token!==lookupId||$('eanmerc').value.trim()!==query)return false;
      lookupRows=append?lookupRows.concat(data.items):data.items;lookupMore=data.has_more;renderSuggestions();return true;
    } catch(error){if(error.name!=='AbortError'&&token===lookupId){box.replaceChildren();suggestionMessage(error.message);message('marketmsg',error.message,true);}return false;}
  }
  $('eanmerc').addEventListener('input',()=>{
    marketSelection=null;closeSuggestions();const query=$('eanmerc').value.trim();
    if(query.length>=2)lookupTimer=setTimeout(()=>lookupProducts(query),350);
  });
  $('eanmerc').addEventListener('keydown',event=>{
    if(event.key==='ArrowDown'&&!$('market-suggestions').hidden){event.preventDefault();$('market-suggestions').querySelector('button:not(:disabled)')?.focus();}
    if(event.key==='Escape')closeSuggestions();
  });
  $('market-suggestions').addEventListener('keydown',event=>{
    const buttons=[...$('market-suggestions').querySelectorAll('button:not(:disabled)')],index=buttons.indexOf(document.activeElement);
    if(event.key==='Escape'){closeSuggestions();$('eanmerc').focus();}
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();buttons[(index+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length]?.focus();}
  });
  document.addEventListener('click',event=>{if(!event.composedPath().some(node=>node.classList?.contains('product-picker')))closeSuggestions();});
  function renderMarketInto(items,body,chart) {
    body.replaceChildren();chart.replaceChildren();
    if(!items.length) {empty(body,'Nenhuma observação neste filtro.',7);chart.textContent='Nenhuma observação importada neste filtro.';return;}
    items.forEach(item=>{const row=document.createElement('tr');[groups[item.grupo]||item.grupo,item.estabelecimento,number(item.distancia_km)+' km',money(item.preco),dateBR(item.coletado_em),item.condicao,item.fonte].forEach((text,index)=>cell(row,text,index===5?'condition-info':''));body.append(row);});
    renderPriceChart(items,chart,'Nenhum preço disponível neste filtro.');
  }
  function onlineCondition(offer) {
    if(offer.condicao_comparacao)return offer.condicao_comparacao;
    const text=offer.condicao||'Sem condição informada';
    if(text.startsWith('Oferta para pagamento no Pix'))return 'Pagamento no Pix';
    if(['Preco publico no site;','Preco do catalogo;','Preco basico do catalogo;'].some(prefix=>text.startsWith(prefix)))return 'Preço público por unidade';
    return text;
  }
  function renderPriceChart(items,chart,emptyText) {
    chart.replaceChildren();items=items.filter(item=>present(item.preco)&&Number(item.preco)>0);
    if(!items.length){chart.textContent=emptyText;return;}
    const summaries=new Map();
    items.forEach(item=>{if(!present(item.preco)||Number(item.preco)<=0)return;const key=JSON.stringify([item.grupo,item.condicao||'Sem condição informada']);if(!summaries.has(key))summaries.set(key,[]);summaries.get(key).push(Number(item.preco));});
    const maximum=items.reduce((max,item)=>present(item.preco)?Math.max(max,Number(item.preco)):max,0);
    [...summaries].slice(0,12).forEach(([key,values])=>{
      const [group,condition]=JSON.parse(key);values.sort((a,b)=>a-b);const average=values.reduce((sum,value)=>sum+value,0)/values.length;
      const box=document.createElement('div');box.className='chart-group';const title=document.createElement('h3');title.textContent=groups[group]||group;
      const note=document.createElement('div');note.className='muted';note.textContent=condition+' · '+values.length+' observações';
      const bars=document.createElement('div');bars.className='bars';
      [['Menor',values[0],''],['Média',average,'medium'],['Maior',values.at(-1),'high']].forEach(([label,value,style])=>{
        const col=document.createElement('div');col.className='bar-col';const price=document.createElement('span');price.textContent=money(value);
        const bar=document.createElement('div');bar.className='bar '+style;bar.style.height=(maximum?value/maximum*92:0)+'px';col.dataset.price=String(value);col.dataset.summary=label;bar.setAttribute('aria-hidden','true');const caption=document.createElement('span');caption.textContent=label;col.append(price,bar,caption);bars.append(col);
      });box.append(title,note,bars);chart.append(box);
    });
    if(summaries.size>12){const note=document.createElement('p');note.textContent='Gráfico limitado aos primeiros 12 grupos/condições. A tabela mantém todas as observações.';chart.append(note);}
  }
  function renderComposition(data,chart) {
    const panel=document.createElement('section');panel.className='panel composition-panel';
    const heading=document.createElement('h3');heading.textContent='Mesma composição — todos os laboratórios';panel.append(heading);
    const note=document.createElement('p');note.className='muted';note.textContent=data?.mensagem||'Comparação por composição indisponível.';panel.append(note);
    if(!data?.referencia){chart.append(panel);return;}
    const ref=data.referencia,summary=document.createElement('p');summary.textContent=[ref.principio_ativo,ref.doses.join(' + '),ref.forma,ref.quantidade?ref.quantidade+' unidades':'',ref.volumes_ml.length?ref.volumes_ml.join(' / ')+' mL':'',...ref.modificadores].filter(Boolean).join(' · ');panel.append(summary);
    const states=document.createElement('p');states.className='muted';states.textContent=data.fontes.map(s=>s.rede+': '+s.estado+(s.coletado_em?' · '+new Date(s.coletado_em).toLocaleString('pt-BR'):'')).join('; ');panel.append(states);
    const offers=(data.ofertas||[]).filter(o=>Number.isFinite(Number(o.preco))&&Number(o.preco)>0);
    if(!offers.length){const empty=document.createElement('p');empty.textContent='Nenhum preço com composição e apresentação completas nas fontes consultadas.';panel.append(empty);chart.append(panel);return;}
    const groupsFound=new Map();offers.forEach(o=>{const key=JSON.stringify([o.grupo||'Grupo pendente',onlineCondition(o)+(o.desatualizado?' · Coleta anterior':'')]);if(!groupsFound.has(key))groupsFound.set(key,[]);groupsFound.get(key).push(o);});
    const maximum=Math.max(...offers.map(o=>Number(o.preco)));
    [...groupsFound].slice(0,12).forEach(([key,items])=>{
      items.sort((a,b)=>Number(a.preco)-Number(b.preco));const [group,condition]=JSON.parse(key);
      const box=document.createElement('div');box.className='chart-group';const title=document.createElement('h3');title.textContent=groups[group]||group;box.append(title);
      const info=document.createElement('p');info.className='muted';info.textContent=condition+' · '+items.length+' ofertas · passe o mouse, use Tab ou clique nas barras';box.append(info);
      const bars=document.createElement('div');bars.className='bars';const details=document.createElement('div');details.className='composition-details';details.setAttribute('aria-live','polite');
      const show=(label,value,records)=>{
        details.replaceChildren();const caption=document.createElement('p');caption.textContent=label+': '+money(value)+(label==='Média'?' · média aritmética das '+records.length+' ofertas abaixo':'');details.append(caption);
        records.forEach(o=>{const row=document.createElement('p');const link=document.createElement('a');link.href=o.url;link.target='_blank';link.rel='noopener noreferrer';link.textContent=o.produto;row.append(link, ' · '+(o.laboratorio||'Laboratório não informado')+' · '+o.rede+' · EAN '+o.ean+' · '+money(o.preco)+' · '+(o.coletado_em?new Date(o.coletado_em).toLocaleString('pt-BR'):'Data não informada'));details.append(row);});
      };
      const average=items.reduce((sum,o)=>sum+Number(o.preco),0)/items.length;
      [['Menor',Number(items[0].preco),'',items.filter(o=>Number(o.preco)===Number(items[0].preco))],['Média',average,'medium',items],['Maior',Number(items.at(-1).preco),'high',items.filter(o=>Number(o.preco)===Number(items.at(-1).preco))]].forEach(([label,value,style,records])=>{
        const col=document.createElement('button');col.type='button';col.className='bar-col composition-bar';col.dataset.summary=label;col.dataset.price=String(value);col.setAttribute('aria-label',label+' '+money(value)+' — mostrar produtos');col.title=label==='Média'?'Média das ofertas: '+records.map(o=>o.produto+' ('+money(o.preco)+')').join('; '):records.map(o=>o.produto+' · '+o.rede+' · '+money(o.preco)).join('; ');
        const price=document.createElement('span');price.textContent=money(value);const bar=document.createElement('span');bar.className='bar '+style;bar.style.height=(value/maximum*92)+'px';const caption=document.createElement('span');caption.textContent=label;col.append(price,bar,caption);
        ['mouseenter','focus','click'].forEach(event=>col.addEventListener(event,()=>show(label,value,records)));bars.append(col);
      });box.append(bars,details);panel.append(box);
    });chart.append(panel);
  }
  function renderMarket(){renderMarketInto(marketItems.filter(r=>!$('market-group').value||r.grupo===$('market-group').value),$('marketrows'),$('market-chart'));}
  ['eanmerc','market-days','raiomerc'].forEach(id=>$(id).addEventListener('input',()=>{
    marketController?.abort();marketRequest++;marketItems=[];renderMarket();$('market-search').disabled=false;
    if(id==='eanmerc'){$('selected-product').textContent='Consultar produto';$('selected-product').disabled=true;}
    if(id!=='market-days')clearOnline();
    if(id==='raiomerc')clearStores('Raio alterado. Busque novamente as lojas.');
    message('marketmsg','Filtros alterados. Consulte para carregar as observações.');
  }));
  $('market-group').addEventListener('change',renderMarket);
  $('market-form').addEventListener('submit',async event=>{
    event.preventDefault();const query=$('eanmerc').value.trim();
    const ean=marketSelection?.ean || (/^[0-9]{8,14}$/.test(query)?query:null);
    if(!ean){
      if(query.length<2){message('marketmsg','Digite ao menos dois caracteres da descrição ou o EAN.',true);return;}
      if(query.length>=3)loadOnline();
      if(await lookupProducts(query))message('marketmsg','Selecione o produto encontrado para consultar os preços pelo EAN correto.');
      return;
    }
    if(!savedCenter){message('marketmsg','Cadastre o endereço do centro para consultar por raio.',true);tab('local');$('center-address').focus();return;}
    loadOnline();
    closeSuggestions();marketController?.abort();marketController=new AbortController();const token=++marketRequest;
    const params=new URLSearchParams({ean,dias:$('market-days').value,raio:$('raiomerc').value,usar_centro:'true',centro_versao:String(savedCenter.versao)});
    message('marketmsg','Consultando observações importadas…');$('market-search').disabled=true;
    try {const data=await json('/api/mercado/comparar?'+params,{signal:marketController.signal});if(token!==marketRequest)return;marketItems=data.observacoes;renderMarket();message('marketmsg',marketItems.length+' observações no raio de '+number(params.get('raio'))+' km. '+data.aviso);}
    catch(error){if(error.name!=='AbortError'&&token===marketRequest){marketItems=[];renderMarket();message('marketmsg',error.message,true);}}
    finally{if(token===marketRequest)$('market-search').disabled=false;}
  });
  function fetchOnline(body) {
    body={...body,descricao:(body.descricao||'').trim().slice(0,180)};
    const identity=JSON.stringify([body.ean||'',body.descricao]);
    body.selecoes=onlineChoices.get(identity)||{};
    const key=JSON.stringify(body);
    if(onlinePending.has(key))return onlinePending.get(key);
    const pending=json('/api/mercado/online/consultar',{method:'POST',headers:configHeaders(),body:JSON.stringify(body)}).finally(()=>onlinePending.delete(key));
    onlinePending.set(key,pending);return pending;
  }
  function onlineVendorDetails(container,source,offer,data,sameEAN) {
    const detail=document.createElement('div');detail.dataset.helpLabel=source.rede;
    detail.dataset.helpKind=!sameEAN||source.desatualizado?'warning':'info';
    const fields=document.createElement('dl');fields.className='online-offer-data';
    const add=(label,value)=>{const title=document.createElement('dt'),text=document.createElement('dd');title.textContent=label;text.textContent=value;fields.append(title,text);};
    add('Produto no fornecedor',offer.produto||'Não informado');add('EAN no fornecedor',offer.ean||'Não informado');
    if(data.ean)add('EAN consultado no sistema',data.ean);
    add('Correspondência',sameEAN?'Mesmo EAN do produto consultado':data.ean?'EAN diferente — confira o produto escolhido nesta consulta.':'Produto escolhido por descrição — confira EAN e apresentação.');
    if(offer.correspondencia==='descricao_confirmada')add('Seleção','Escolhido por descrição nesta consulta.');
    if(offer.laboratorio)add('Marca / laboratório informado',offer.laboratorio);
    add('Preço no site',money(offer.preco)+(offer.tipo_preco==='normal'?' · normal':''));
    if(offer.em_oferta&&present(offer.preco_regular))add('Preço regular',money(offer.preco_regular));
    add('Condições',offer.condicao+' Preço da filial não confirmado.');
    add('Coleta',(source.coletado_em?new Date(source.coletado_em).toLocaleString('pt-BR'):'Não informada')+(source.desatualizado?' · COLETA ANTERIOR — fonte indisponível':source.cache?' · cache':''));
    add('Grupo',groups[source.grupo]||'Grupo pendente');
    add('Presença no raio',(source.lojas_no_raio||[]).length+' loja(s) cadastrada(s) desta rede');
    detail.append(fields);
    try{const url=new URL(offer.url);if(url.protocol==='https:'&&!url.username&&!url.password){const link=document.createElement('a');link.href=url.href;link.textContent='Abrir oferta no site';link.target='_blank';link.rel='noopener noreferrer';detail.append(link);}}catch{}
    container.append(detail);window.PriceHelp.attach(detail,{label:source.rede,scope:source.rede});
  }
  function renderOnline(data,prefix,systemProduct=null) {
      const systemName=systemProduct&&String(systemProduct.ean||'')===String(data.ean||'')?systemProduct.descricao:'';
      const referenceName=systemName||data.descricao_original||'';
      $(prefix+'-rows').replaceChildren();$(prefix+'-sources').replaceChildren();let count=0;const chartItems=[];
      data.fontes.forEach(source=>{
        const note=document.createElement('p');note.dataset.helpLabel=source.rede;note.dataset.helpKind=source.desatualizado||!source.ofertas.length?'warning':'info';note.textContent=source.rede+' — '+(source.mensagem||(source.ofertas.length?`${source.ofertas.length} oferta(s) ${source.cache?'em cache':'consultada(s)'}.`:'Nenhum preço válido retornado para este EAN, normal ou promocional. Isso não confirma falta de estoque.'));$(prefix+'-sources').append(note);
        if(source.url_consulta){const link=document.createElement('a');link.href=source.url_consulta;link.textContent='Abrir site da '+source.rede+' para consulta manual';link.target='_blank';link.rel='noopener noreferrer';note.append(' ',link);}
        if(source.aviso_descricao){const warning=document.createElement('p');warning.dataset.helpLabel='Aviso da busca';warning.dataset.helpKind='warning';warning.textContent=source.aviso_descricao;$(prefix+'-sources').append(warning);}
        if(source.candidatos?.length){
          const box=document.createElement('details');box.className='online-candidate-list';const heading=document.createElement('summary');heading.textContent=source.rede+' — escolher produto por descrição ('+source.candidatos.length+')';box.append(heading);
          const warning=document.createElement('p');warning.className='notice';warning.textContent='Confira dosagem, quantidade, tamanho, fabricante e embalagem. Candidatos com EAN diferente só entram no gráfico após sua escolha nesta consulta.';box.append(warning);
          source.candidatos.forEach(candidate=>{
            const row=document.createElement('div');row.className='description-candidate';
            const name=document.createElement('strong');name.textContent=candidate.produto+' · EAN '+candidate.ean;
            const details=document.createElement('p');details.textContent=[candidate.marca,candidate.oferta?'Preço de referência no site: '+money(candidate.oferta.preco):'Sem oferta disponível',...candidate.conferencias,...candidate.pendencias].filter(Boolean).join(' · ');
            const link=document.createElement('a');link.href=candidate.url;link.textContent='Conferir embalagem no site';link.target='_blank';link.rel='noopener noreferrer';
            const button=document.createElement('button');button.type='button';button.textContent=candidate.oferta?'Usar este produto na consulta':'Sem oferta disponível';button.disabled=!candidate.oferta;
            button.addEventListener('click',()=>{const identity=JSON.stringify([data.ean||'',data.descricao_original||'']);onlineChoices.set(identity,{...(onlineChoices.get(identity)||{}),[source.fonte]:candidate.ean});if(prefix==='detail-online')loadDetailOnline();else loadOnline();});
            row.append(name,details,link,button);box.append(row);
          });$(prefix+'-sources').append(box);
        }
        source.ofertas.forEach(offer=>{
          count++;chartItems.push({grupo:source.grupo||'Grupo pendente — classificar concorrentes',preco:offer.preco,condicao:onlineCondition(offer)+(source.desatualizado?' · Coleta anterior':'')});
          const row=document.createElement('tr'),sameEAN=Boolean(data.ean)&&String(data.ean)===String(offer.ean);
          row.dataset.eanMatch=sameEAN?'same':data.ean?'different':'unconfirmed';
          const vendor=cell(row,'','online-vendor-cell');vendor.dataset.label='Fornecedor';onlineVendorDetails(vendor,source,offer,data,sameEAN);
          if(!sameEAN){const badge=document.createElement('span');badge.className='badge attention online-ean-badge';badge.textContent=data.ean?'EAN diferente':'Por descrição';vendor.append(badge);}
          const product=cell(row,sameEAN?(referenceName||offer.produto):'Produto selecionado · ver fornecedor','online-product-cell');product.dataset.label='Produto';
          const price=cell(row,(offer.em_oferta&&present(offer.preco_regular)?'De '+money(offer.preco_regular)+' por ':'')+money(offer.preco)+(offer.tipo_preco==='normal'?' · normal':''),'online-price-cell');price.dataset.label='Preço no site';
          const condition=cell(row,offer.condicao+' Preço da filial não confirmado.','condition-info online-condition-cell');condition.dataset.label='Condições';
          const collected=cell(row,'','online-collected-cell');collected.dataset.label='Coleta';
          if(source.coletado_em){const date=new Date(source.coletado_em);collected.append(date.toLocaleDateString('pt-BR'));const time=document.createElement('small');time.textContent=date.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'});collected.append(time);}else collected.textContent='Não informada';
          if(source.desatualizado){const stale=document.createElement('span');stale.className='badge attention';stale.textContent='Coleta anterior';collected.append(stale);}
          $(prefix+'-rows').append(row);
        });
      });
      (data.fontes_nao_consultadas||[]).forEach(source=>{const note=document.createElement('p');note.dataset.helpLabel=source.rede+' — não consultada';note.dataset.helpKind='warning';note.textContent=source.motivo;$(prefix+'-sources').append(note);});
      if(data.links_pesquisa?.length){const links=document.createElement('p');links.dataset.helpLabel='Outros sites';links.textContent='Pesquisa manual pela descrição em outros sites (presença no raio não verificada): ';data.links_pesquisa.forEach(source=>{const link=document.createElement('a');link.href=source.url;link.textContent=source.nome;link.target='_blank';link.rel='noopener noreferrer';links.append(link,' · ');});$(prefix+'-sources').append(links);}
      if(!count)empty($(prefix+'-rows'),'Nenhuma oferta retornada pelas fontes consultadas. Confira o estado de cada fonte acima.',5);
      if(data.sem_integracao.length){const note=document.createElement('p');note.dataset.helpLabel='Redes sem integração';note.dataset.helpKind='warning';note.textContent='Lojas ainda sem integração de preços: '+data.sem_integracao.join(', ')+'.';$(prefix+'-sources').append(note);}
      message(prefix+'-message',`${count} oferta(s) de site para ${data.ean?'EAN '+data.ean:'a descrição informada'}. `+(data.busca_normalizada?' Busca: '+data.busca_normalizada+'. ':'')+(data.fontes.length?data.aviso:'Nenhuma rede integrada foi identificada no cadastro dentro do raio. Busque ou confira os concorrentes cadastrados.'));
      renderPriceChart(chartItems,$(prefix+'-chart'),'Nenhum preço online obtido para este EAN. Confira o estado das fontes acima.');
      renderComposition(data.composicao,$(prefix+'-chart'));
  }
  function clearOnline() {
    onlineController?.abort();onlineRequest++;onlineScope=null;$('online-search').disabled=false;$('online-refresh').disabled=false;$('online-sources').replaceChildren();$('online-chart').replaceChildren();
    empty($('online-rows'),'Selecione um produto para carregar os preços online.',5);message('online-message','A consulta online inicia ao selecionar o produto. Você também pode clicar em Atualizar preços online.');
  }
  async function loadOnline(force=false) {
    const query=$('eanmerc').value.trim(),savedEAN=String(marketSelection?.ean||''),ean=/^[0-9]{8,14}$/.test(savedEAN)?savedEAN:(/^[0-9]{8,14}$/.test(query)?query:null),descricao=(marketSelection?.descricao||(!ean?query:'')).trim().slice(0,180);
    if(!ean&&descricao.length<3){message('online-message','Informe o EAN ou ao menos três caracteres da descrição.',true);return;}
    if(!savedCenter){message('online-message','Cadastre o centro para selecionar as redes dentro do raio.',true);tab('local');return;}
    const radius=Number($('raiomerc').value);
    if(!Number.isFinite(radius)||radius<.5||radius>50){message('online-message','Informe um raio entre 0,5 e 50 km.',true);return;}
    const scope=JSON.stringify([ean,descricao,radius,savedCenter.versao]);
    if(onlineScope===scope&&$('online-search').disabled)return;
    clearOnline();onlineScope=scope;onlineController=new AbortController();const token=++onlineRequest;$('online-search').disabled=true;$('online-refresh').disabled=true;closeSuggestions();
    message('online-message','Consultando catálogos por EAN e descrição normalizada; aguarde as fontes.');
    try {
      const data=await fetchOnline({ean,descricao,raio:radius,centro_versao:savedCenter.versao,atualizar:force===true});
      if(token!==onlineRequest)return;
      renderOnline(data,'online',marketSelection);
    }catch(error){if(error.name!=='AbortError'&&token===onlineRequest){empty($('online-rows'),'Consulta online não concluída. Use Atualizar preços online para tentar novamente.',5);message('online-message',error.message,true);}}
    finally{if(token===onlineRequest){$('online-search').disabled=false;$('online-refresh').disabled=false;}}
  }
  $('online-search').addEventListener('click',()=>loadOnline(true));
  $('online-refresh').addEventListener('click',()=>loadOnline(true));
  function marketScope(ean) {
    if(!savedCenter)throw Error('Cadastre o centro da pesquisa para comparar por grupo e raio.');
    const radius=Number($('raiomerc').value),days=Number($('market-days').value);
    if(!Number.isFinite(radius)||radius<0.5||radius>50||!Number.isInteger(days)||days<1||days>90)throw Error('Confira raio e período da pesquisa.');
    return new URLSearchParams({ean,raio:String(radius),dias:String(days),usar_centro:'true',centro_versao:String(savedCenter.versao)});
  }
  $('selected-product').addEventListener('click',()=>{if(marketSelection?.embalagem_id)openProduct(marketSelection);});
  $('detail-close').addEventListener('click',()=>$('product-dialog').close());
  $('product-dialog').addEventListener('close',()=>{detailController?.abort();detailId++;detailOnlineRequest++;});
  async function openProduct(item) {
    detailController?.abort();detailController=new AbortController();const token=++detailId;activeProduct=null;detailOnlineRequest++;
    $('detail-online-refresh').disabled=true;$('detail-online-sources').replaceChildren();$('detail-online-chart').replaceChildren();empty($('detail-online-rows'),'Carregando produto para consultar os sites…',5);message('detail-online-message','Carregando produto…');
    $('detail-title').textContent=item.descricao || 'Ficha do produto';$('detail-data').replaceChildren();$('detail-classes').replaceChildren();
    $('detail-remarcacao').textContent='';$('detail-market-message').textContent='';$('detail-stores').disabled=true;
    renderMarketInto([],$('detail-market-rows'),$('detail-chart'));message('detail-message','Consultando ficha do produto…');
    if(!$('product-dialog').open)$('product-dialog').showModal();
    try {
      const data=await json('/api/mercado/produtos/'+encodeURIComponent(item.embalagem_id),{signal:detailController.signal});if(token!==detailId)return;
      activeProduct=data.produto;$('detail-title').textContent=activeProduct.descricao;
      [['EAN',activeProduct.ean||'Não informado'],['Código Alpha7',activeProduct.codigo||'Não informado'],['Apresentação',activeProduct.apresentacao||'Não informada'],['Preço atual',money(activeProduct.preco)]].forEach(([label,value])=>{
        const box=document.createElement('div');box.className='detail-field';const name=document.createElement('small');name.textContent=label;const text=document.createElement('strong');text.textContent=value;box.append(name,text);$('detail-data').append(box);
      });
      if(data.classificacao_disponivel&&data.classificacoes.length){data.classificacoes.forEach(group=>{const badge=document.createElement('span');badge.className='classification-chip';badge.textContent=group.nome;$('detail-classes').append(badge);});}
      else $('detail-classes').textContent=data.classificacao_disponivel?'Produto sem classificação cadastrada.':'Classificação não disponível nesta fonte do Alpha7.';
      $('detail-remarcacao').textContent='Grupo de remarcação: '+(data.grupo_remarcacao?.nome||(data.grupo_remarcacao_disponivel?'não cadastrado':'não disponível nesta fonte'));
      message('detail-message',data.classificacoes_limitadas?'Classificações limitadas às primeiras 100.':'Ficha consultada em modo somente leitura.');$('detail-stores').disabled=false;
      $('detail-online-refresh').disabled=false;loadDetailOnline();
      if(!/^[0-9]{8,14}$/.test(String(activeProduct.ean||''))){message('detail-market-message','Produto sem EAN válido; consulta online pela descrição.');return;}
      const params=marketScope(activeProduct.ean);message('detail-market-message','Consultando observações por grupo…');
      const comparison=await json('/api/mercado/comparar?'+params,{signal:detailController.signal});if(token!==detailId)return;
      renderMarketInto(comparison.observacoes,$('detail-market-rows'),$('detail-chart'));
      message('detail-market-message',`Centro: ${savedCenter.endereco} · Raio: ${params.get('raio')} km. `+comparison.aviso);
    }catch(error){if(error.name!=='AbortError'&&token===detailId)message(activeProduct?'detail-market-message':'detail-message',error.message,true);}
  }
  async function loadDetailOnline(force=false) {
    const token=++detailOnlineRequest,product=activeProduct;
    if(!product)return;
    if(!savedCenter){empty($('detail-online-rows'),'Cadastre o centro da pesquisa para consultar os sites.',5);message('detail-online-message','Cadastre e confirme o endereço do centro na tela principal.',true);return;}
    const radius=Number($('raiomerc').value);
    if(!Number.isFinite(radius)||radius<.5||radius>50){message('detail-online-message','Informe um raio entre 0,5 e 50 km na pesquisa de mercado.',true);return;}
    $('detail-online-refresh').disabled=true;message('detail-online-message','Consultando preços online por EAN e descrição do produto…');
    try {
      const data=await fetchOnline({ean:/^[0-9]{8,14}$/.test(String(product.ean||''))?String(product.ean):null,descricao:product.descricao,raio:radius,centro_versao:savedCenter.versao,atualizar:force===true});
      if(token!==detailOnlineRequest||!$('product-dialog').open)return;
      renderOnline(data,'detail-online',product);
    }catch(error){if(token===detailOnlineRequest){$('detail-online-chart').replaceChildren();$('detail-online-sources').replaceChildren();empty($('detail-online-rows'),'Consulta online não concluída.',5);message('detail-online-message',error.message,true);}}
    finally{if(token===detailOnlineRequest)$('detail-online-refresh').disabled=false;}
  }
  $('detail-online-refresh').addEventListener('click',()=>loadDetailOnline(true));
  function clearStores(text='Carregue os concorrentes cadastrados ou busque novas lojas no raio.') {
    storesController?.abort();storesId++;storesOffset=0;empty($('stores-rows'),text,6);$('stores-search').disabled=false;message('stores-message',text);
    $('stores-previous').disabled=true;$('stores-next').disabled=true;$('stores-page').textContent='';
  }
  function groupLabel(row,store,withDistance=false) {
    row.dataset.storeSource=store.fonte_id;row.dataset.storeDistance=withDistance?number(store.distancia_km)+' km':'';
    const label=document.createElement('span');label.dataset.role='store-group';label.textContent=(groups[store.grupo]||'Grupo pendente')+(withDistance?' · '+row.dataset.storeDistance:'');
    return label;
  }
  function groupControls(container,store,messageId,compact=false) {
    const select=document.createElement('select');select.setAttribute('aria-label','Grupo de '+store.nome);select.add(new Option('Selecione o grupo',''));Object.entries(groups).forEach(([key,label])=>select.add(new Option(label,key)));select.value=store.grupo||'';
    const reason=document.createElement('input');reason.placeholder='Motivo (opcional)';reason.maxLength=300;reason.setAttribute('aria-label','Motivo da classificação de '+store.nome);
    const save=document.createElement('button');save.type='button';save.className='small-btn';save.textContent='Confirmar grupo';
    save.addEventListener('click',async()=>{
      if(!select.value){message(messageId,'Selecione o grupo.',true);return;}
      save.disabled=true;
      try {
        const data=await json('/api/mercado/lojas/'+store.fonte_id+'/grupo',{method:'PUT',headers:configHeaders(),body:JSON.stringify({grupo:select.value,motivo:reason.value.trim()})});
        store.grupo=data.grupo;
        document.querySelectorAll('tr[data-store-source]').forEach(row=>{
          if(row.dataset.storeSource!==store.fonte_id)return;
          row.querySelector('[data-role=store-group]').textContent=groups[data.grupo]+(row.dataset.storeDistance?' · '+row.dataset.storeDistance:'');
          row.querySelector('select').value=data.grupo;
        });
        message(messageId,'Grupo confirmado no cadastro compartilhado de concorrentes.');
        if((marketSelection?.ean||marketSelection?.descricao)&&savedCenter)loadOnline();
        if(activeProduct?.ean&&$('product-dialog').open)loadDetailOnline();
      }catch(error){message(messageId,error.message,true);}finally{save.disabled=false;}
    });
    const controls=document.createElement('div');controls.className='store-review';
    if(compact){
      controls.classList.add('directory-group-controls');save.textContent='Salvar';save.setAttribute('aria-label','Confirmar grupo');save.title='Confirmar grupo';
      const extra=document.createElement('details');extra.className='directory-group-reason';const summary=document.createElement('summary');summary.textContent='Motivo opcional';extra.append(summary,reason);controls.append(select,save,extra);
    }else controls.append(select,reason,save);
    container.append(controls);
  }
  function renderStores(rows) {
    $('stores-rows').replaceChildren();if(!rows.length){empty($('stores-rows'),'Nenhum concorrente cadastrado neste raio. Busque novas lojas para complementar o cadastro.',6);return;}
    rows.forEach(store=>{
      const row=document.createElement('tr');cell(row,store.nome);cell(row,'').append(groupLabel(row,store));cell(row,number(store.distancia_km)+' km');
      const site=cell(row,'');
      if(store.site){const link=document.createElement('a');link.href=store.site;link.textContent=new URL(store.site).hostname;link.target='_blank';link.rel='noopener noreferrer';site.append(link);}else site.textContent='Site não informado';
      const source=cell(row,'');const link=document.createElement('a');if(store.fonte_url){link.href=store.fonte_url;link.textContent=store.fonte_id.startsWith('manual/')?'CNPJ informado':'Cadastro OSM';link.target='_blank';link.rel='noopener noreferrer';source.append(link);}else source.textContent='Cadastro manual';
      groupControls(cell(row,''),store,'stores-message');$('stores-rows').append(row);
    });
  }
  async function loadSavedStores(offset=0,notice='',warning=false) {
    if(!savedCenter){clearStores('Cadastre o centro para consultar os concorrentes no raio.');return false;}
    const radius=Number($('raiomerc').value);
    if(!Number.isFinite(radius)||radius<0.5||radius>50){clearStores('Informe um raio entre 0,5 e 50 km.');return false;}
    storesController?.abort();storesController=new AbortController();const token=++storesId;
    message('stores-message','Carregando o cadastro compartilhado de concorrentes…');
    try {
      const data=await json('/api/concorrentes?'+new URLSearchParams({raio:radius,centro_versao:savedCenter.versao,limit:100,offset}),{signal:storesController.signal});
      if(token!==storesId)return false;
      storesOffset=offset;renderStores(data.items);$('stores-previous').disabled=offset===0;$('stores-next').disabled=!data.has_more;
      $('stores-page').textContent=data.total?`${offset+1}–${offset+data.items.length} de ${data.total} concorrentes`:'Nenhum concorrente no filtro';
      message('stores-message',(notice?notice+' ':'')+`${data.total} concorrentes no cadastro compartilhado · raio ${radius} km · ${data.centro.endereco}.`,warning);
      return true;
    }catch(error){if(error.name!=='AbortError'&&token===storesId){clearStores('Cadastro não carregado.');message('stores-message',error.message,true);}return false;}
  }
  async function findStores() {
    if(!savedCenter){message('stores-message','Cadastre o centro antes de buscar lojas.',true);tab('local');$('center-address').focus();return;}
    const radius=Number($('raiomerc').value),version=savedCenter.versao;
    if(!Number.isFinite(radius)||radius<0.5||radius>50){message('stores-message','Informe um raio entre 0,5 e 50 km.',true);return;}
    if(!await loadSavedStores())return;
    if(savedCenter?.versao!==version||Number($('raiomerc').value)!==radius)return;
    storesController?.abort();storesController=new AbortController();const token=++storesId;$('stores-search').disabled=true;
    message('stores-message','Buscando atualizações online; os concorrentes já cadastrados continuam disponíveis. A busca pode levar até 30 segundos.');
    try {
      const data=await json('/api/mercado/lojas/buscar',{method:'POST',headers:configHeaders(),body:JSON.stringify({raio:radius,centro_versao:version}),signal:storesController.signal});
      if(token!==storesId)return;
      if(marketSelection?.ean||marketSelection?.descricao){clearOnline();loadOnline();}
      await loadSavedStores(0,data.fallback?data.aviso:`${data.lojas.length} cadastros no raio. Busca ${data.cache?'em cache':'online'} concluída. ${data.cadastro.adicionados} novos e ${data.cadastro.atualizados} atualizados.`,Boolean(data.fallback));
    }catch(error){if(error.name!=='AbortError'&&token===storesId)await loadSavedStores(0,'A busca online não foi concluída: '+error.message+' Exibindo o cadastro salvo.',true);}
    finally{$('stores-search').disabled=false;}
  }
  $('stores-saved').addEventListener('click',()=>loadSavedStores());
  $('stores-open-directory').addEventListener('click',()=>tab('concorrentes'));
  $('stores-previous').addEventListener('click',()=>loadSavedStores(Math.max(0,storesOffset-100)));
  $('stores-next').addEventListener('click',()=>loadSavedStores(storesOffset+100));
  let competitorOffset=0,competitorRequest=0;
  async function loadCompetitors() {
    const token=++competitorRequest;
    if(!savedCenter){$('competitors-count').textContent='Centro pendente';$('competitors-page').textContent='';empty($('competitors-rows'),'Cadastre o centro da pesquisa para consultar concorrentes.',4);message('competitors-message','Centro ainda não cadastrado.');return;}
    const radius=Number($('raiomerc').value);
    if(!Number.isFinite(radius)||radius<0.5||radius>50){message('competitors-message','Informe um raio entre 0,5 e 50 km na pesquisa de mercado.',true);return;}
    message('competitors-message','Carregando cadastro salvo…');
    try {
      const data=await json('/api/concorrentes?'+new URLSearchParams({raio:radius,centro_versao:savedCenter.versao,q:$('competitors-q').value,offset:competitorOffset,limit:100}));
      if(token!==competitorRequest)return;
      $('competitors-rows').replaceChildren();
      if(!data.items.length)empty($('competitors-rows'),'Nenhum concorrente salvo neste filtro. Busque novas lojas no raio.',4);
      data.items.forEach(store=>{
        const row=document.createElement('tr');row.className='directory-row';
        const location=cell(row,'','directory-location');location.dataset.label='Loja / localização';
        const name=document.createElement('strong');name.textContent=store.nome;
        const address=document.createElement('small');address.textContent=store.endereco||'Endereço não informado';
        const distance=document.createElement('span');distance.className='badge';distance.textContent=number(store.distancia_km)+' km';location.append(name,address,distance);
        const group=cell(row,'','directory-group');group.dataset.label='Grupo';group.append(groupLabel(row,store));groupControls(group,store,'competitors-message',true);
        const links=cell(row,'','directory-sites');links.dataset.label='Sites e fontes';const sites=document.createElement('div');sites.className='directory-site-links';
        for(const [url,label] of [[store.site,'Site da loja'],[store.fonte_url,store.fonte_id.startsWith('manual/')?'CNPJ informado':'Cadastro OSM']])if(url){const a=document.createElement('a');a.href=url;a.textContent=label;a.target='_blank';a.rel='noopener noreferrer';sites.append(a);}
        if(store.fonte_id.startsWith('manual/')){const origin=document.createElement('span');origin.textContent='Cadastro manual';sites.prepend(origin);}
        if(!store.site){const missing=document.createElement('span');missing.className='muted';missing.textContent='Site não informado';sites.prepend(missing);}links.append(sites);
        const details=cell(row,'','directory-registration');details.dataset.label='CNPJ / cadastro';
        const info=store.dados_cnpj,failed=store.cnpj_status==='falha_consulta';
        const identified=store.cnpj_origem?.startsWith('Pesquisa de filial por endereco - ');
        const badge=document.createElement('span');badge.className='badge '+(failed?'danger':info?.descricao_situacao_cadastral==='ATIVA'?'ok':'attention');badge.textContent=failed?'Falha na consulta':info?'CNPJ consultado':store.cnpj?'Aguardando consulta':'Sem CNPJ';details.append(badge);
        const metadata=document.createElement('div');metadata.dataset.helpLabel='Dados cadastrais';metadata.dataset.helpKind=failed||!identified?'warning':'info';
        const text=document.createElement('p');text.textContent=info?`${info.razao_social||''} · ${info.descricao_situacao_cadastral||''} · CNAE ${info.cnae_fiscal||''}: ${info.cnae_fiscal_descricao||''}. Consulta: ${dateBR(info.consultado_em)}. ${identified?'Filial identificada por endereço.':'Confira o vínculo com esta filial.'}`:'CNPJ ainda não identificado com segurança. A loja continua disponível na pesquisa de mercado.';
        metadata.append(text);
        if(info){
          const fiscal=document.createElement('p');fiscal.textContent='Endereço cadastral: '+[info.descricao_tipo_de_logradouro,info.logradouro,info.numero,info.complemento,info.municipio,info.uf].filter(Boolean).join(' · ');metadata.append(fiscal);
          const source=document.createElement('a');source.href='https://brasilapi.com.br/api/cnpj/v1/'+store.cnpj;source.textContent='Fonte dos dados cadastrais';source.target='_blank';source.rel='noopener noreferrer';metadata.append(source);
        }
        if(failed)text.textContent+=' A última tentativa falhou; os dados anteriores foram preservados.';
        details.append(metadata);
        const input=document.createElement('input');input.value=store.cnpj||'';input.maxLength=30;input.inputMode='numeric';input.placeholder='CNPJ desta filial';input.setAttribute('aria-label','CNPJ de '+store.nome);
        const button=document.createElement('button');button.type='button';button.className='small-btn';button.textContent='Consultar CNPJ';
        button.addEventListener('click',async()=>{button.disabled=true;try{const result=await json('/api/concorrentes/'+store.id+'/cnpj',{method:'POST',headers:configHeaders(),body:JSON.stringify({cnpj:input.value})});await loadCompetitors();message('competitors-message',result.mensagem);}catch(error){message('competitors-message',error.message,true);}finally{button.disabled=false;}});
        const fields=document.createElement('div');fields.className='directory-cnpj-row';fields.append(input,button);details.append(fields);$('competitors-rows').append(row);
      });
      $('competitors-previous').disabled=competitorOffset===0;$('competitors-next').disabled=!data.has_more;
      $('competitors-count').textContent=number(data.total)+' no filtro';$('competitors-page').textContent=data.items.length?`${competitorOffset+1}–${competitorOffset+data.items.length} de ${number(data.total)} concorrentes`:'Nenhum concorrente no filtro';
      message('competitors-message',`${data.total} concorrentes salvos no filtro · raio ${radius} km · ${data.centro.endereco}. Exibidos ${data.items.length}.`+(data.cnpjs_preenchidos?` ${data.cnpjs_preenchidos} CNPJs identificados foram preenchidos automaticamente.`:'' ));
    }catch(error){if(token===competitorRequest){$('competitors-count').textContent='Consulta indisponível';$('competitors-page').textContent='';empty($('competitors-rows'),'Cadastro não carregado.',4);message('competitors-message',error.message,true);}}
  }
  Object.entries(groups).forEach(([key,label])=>$('competitor-add-group').add(new Option(label,key)));
  $('competitor-add-lookup').addEventListener('click',async()=>{
    const button=$('competitor-add-lookup');button.disabled=true;$('competitor-add-points').replaceChildren();
    try{const data=await json('/api/concorrentes/cnpj/buscar',{method:'POST',headers:configHeaders(),body:JSON.stringify({cnpj:$('competitor-add-cnpj').value})});$('competitor-add-name').value=data.nome;$('competitor-add-address').value=data.endereco;message('competitor-add-message','Dados consultados. Para adicionar a loja, clique em Localizar para adicionar loja e escolha o ponto.');}
    catch(error){message('competitor-add-message',error.message,true);}finally{button.disabled=false;}
  });
  $('competitor-add-form').addEventListener('input',()=>$('competitor-add-points').replaceChildren());
  $('competitor-add-form').addEventListener('submit',async event=>{
    event.preventDefault();$('competitor-add-points').replaceChildren();
    if(!savedCenter){message('competitor-add-message','Cadastre primeiro o centro da pesquisa.',true);return;}
    const body={cnpj:$('competitor-add-cnpj').value,nome:$('competitor-add-name').value,endereco:$('competitor-add-address').value,grupo:$('competitor-add-group').value||null,site:$('competitor-add-site').value,centro_versao:savedCenter.versao,raio:Number($('raiomerc').value)};
    const submit=event.submitter;submit.disabled=true;
    try{const data=await json('/api/mercado/centro/buscar',{method:'POST',headers:configHeaders(),body:JSON.stringify({endereco:body.endereco})});
      message('competitor-add-message',data.candidatos.length?'Escolha a localização correta da loja para cadastrar.':'Endereço não localizado. Complete ou corrija o endereço e tente novamente.');
      data.candidatos.forEach(point=>{const box=document.createElement('div');box.className='manual-location';const name=document.createElement('p');name.textContent=point.endereco+(point.tipo==='rua_aproximada'?' — Confira o mapa antes de cadastrar.':'');const link=document.createElement('a');link.href=point.mapa_url;link.textContent='Conferir ponto no mapa';link.target='_blank';link.rel='noopener noreferrer';const save=document.createElement('button');save.type='button';save.textContent='Adicionar concorrente nesta localização';save.addEventListener('click',async()=>{save.disabled=true;try{const result=await json('/api/concorrentes/manual',{method:'POST',headers:configHeaders(),body:JSON.stringify({...body,candidato_id:point.candidato_id})});$('competitor-add-points').replaceChildren();$('competitors-q').value='';competitorOffset=0;await loadCompetitors();await loadSavedStores();message('competitor-add-message',result.mensagem+' Distância: '+number(result.distancia_km)+' km.');}catch(error){message('competitor-add-message',error.message,true);}finally{save.disabled=false;}});box.append(name,link,save);$('competitor-add-points').append(box);});
    }catch(error){message('competitor-add-message',error.message,true);}finally{submit.disabled=false;}
  });
  $('competitors-form').addEventListener('submit',event=>{event.preventDefault();competitorOffset=0;loadCompetitors();});
  $('competitors-previous').addEventListener('click',()=>{competitorOffset=Math.max(0,competitorOffset-100);loadCompetitors();});
  $('competitors-next').addEventListener('click',()=>{competitorOffset+=100;loadCompetitors();});
  $('competitors-discover').addEventListener('click',()=>{tab('mercado');findStores();$('stores-panel').scrollIntoView({behavior:'smooth'});});
  $('stores-search').addEventListener('click',findStores);
  $('detail-stores').addEventListener('click',()=>{const product=activeProduct;if(product)chooseMarketProduct(product);$('product-dialog').close();tab('mercado');findStores();$('stores-panel').scrollIntoView({behavior:'smooth',block:'start'});});
  $('import-form').addEventListener('submit',async event=>{
    event.preventDefault();const file=$('arquivo').files[0];if(!file)return;
    if(file.size>2000000){message('importmsg','O arquivo excede 2 MB.',true);return;}
    const body=new FormData();body.append('arquivo',file);$('import-button').disabled=true;
    try{const data=await json('/api/mercado/importar',{method:'POST',body});message('importmsg',data.importados+' registros importados no banco local. Alpha7 não alterado.');}
    catch(error){message('importmsg',error.message,true);}finally{$('import-button').disabled=false;}
  });
  async function start() {
    json('/api/status').then(data=>{$('mode').textContent=data.mode==='demo'?'DEMONSTRAÇÃO':'ALPHA7 · SOMENTE LEITURA';}).catch(()=>{$('mode').textContent='Conexão indisponível';});
    try{const data=await json('/api/revisao/opcoes');entryAvailable=data.ultima_compra_disponivel;$('purchase-without-date').hidden=entryAvailable;periodPresets=Object.fromEntries((data.intervalos||[]).map(item=>[item.id,item]));message('entry-note',data.mensagem_compra||data.mensagem,!entryAvailable);}
    catch(error){message('entry-note','Não foi possível validar a última compra. '+error.message,true);}
    try{await loadCenter();}catch(error){message('market-center','Não foi possível carregar o centro. '+error.message,true);}
    $('period').disabled=false;periodFields();renderMarket();clearStores();load(parameters());
  }
  start();
})();
