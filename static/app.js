(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const present = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const money = value => present(value) ? Number(value).toLocaleString('pt-BR', {style:'currency',currency:'BRL'}) : '—';
  const number = value => present(value) ? Number(value).toLocaleString('pt-BR', {maximumFractionDigits:2}) : '—';
  const dateBR = value => {const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})/);return match ? `${match[3]}/${match[2]}/${match[1]}` : 'Não informada';};
  const groups = {supermercados:'Supermercados e atacarejos',perfumarias:'Perfumarias',farmacias_redes:'Farmácias de rede',farmacias_independentes:'Farmácias independentes'};
  let entryAvailable = false, current = [], applied = null, offset = 0, hasMore = false, dirty = false;
  let controller, requestId = 0, marketController, marketRequest = 0, marketItems = [];
  function tab(name) {
    document.querySelectorAll('.tab').forEach(section => {section.hidden = section.id !== 'tab-' + name;});
    document.querySelectorAll('.nav').forEach(button => {
      const active = button.dataset.tab === name;button.classList.toggle('active', active);
      if (active) button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
    });
  }
  document.querySelectorAll('.nav').forEach(button => button.addEventListener('click', () => tab(button.dataset.tab)));
  function message(id, text, error = false) {$(id).textContent = text;$(id).className = error ? 'error' : 'muted';}
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
    $('previous').disabled = !applied || offset === 0 || dirty;
    $('next').disabled = !applied || !hasMore || dirty;
    $('export').disabled = current.length === 0;
  }
  function periodFields() {
    const custom = entryAvailable && $('period').value === 'intervalo';
    $('date-start').disabled = !custom;$('date-end').disabled = !custom;
    $('date-start').required = custom;$('date-end').required = custom;
    $('date-end').setCustomValidity('');
    $('period-summary').textContent = custom ? ($('date-start').value && $('date-end').value ? `${dateBR($('date-start').value)} a ${dateBR($('date-end').value)}` : 'Selecione as datas') : $('period').selectedOptions[0].textContent;
  }
  function validPeriod() {
    if ($('period').value === 'intervalo' && (!$('date-start').value || !$('date-end').value || $('date-start').value > $('date-end').value)) {
      $('date-end').setCustomValidity('Informe as duas datas, com a final igual ou posterior à inicial.');
      $('period-filter').open=true;$('date-end').reportValidity();return false;
    }
    $('date-end').setCustomValidity('');return true;
  }
  function markDirty() {dirty=true;updatePages();message('msg','Filtros alterados. Clique em Consultar produtos para aplicar.');}
  $('period').addEventListener('change', () => {periodFields();markDirty();});
  ['date-start','date-end'].forEach(id => $(id).addEventListener('input', () => {periodFields();markDirty();}));
  $('period-done').addEventListener('click', () => {if(validPeriod()) $('period-filter').open=false;});
  document.addEventListener('click', event => {if(!$('period-filter').contains(event.target)) $('period-filter').open=false;});
  $('period-filter').addEventListener('keydown', event => {if(event.key==='Escape') {$('period-filter').open=false;$('period-filter').querySelector('summary').focus();}});
  ['q','search-mode','min-margin','only-review','stock-only'].forEach(id => $(id).addEventListener('input',markDirty));
  function parameters() {
    const params = new URLSearchParams({q:$('q').value,modo:$('search-mode').value,periodo:$('period').value,
      margem_minima:$('min-margin').value,somente_revisar:String($('only-review').checked),somente_estoque:String($('stock-only').checked),limit:'100'});
    if($('period').value==='intervalo') {params.set('inicio',$('date-start').value);params.set('fim',$('date-end').value);}
    return params;
  }
  function renderProducts(items) {
    $('rows').replaceChildren();
    if(!items.length) {empty($('rows'),'Nenhum produto encontrado com os filtros aplicados.',9);return;}
    items.forEach(item => {
      const row=document.createElement('tr'), product=cell(row,item.descricao || 'Sem descrição','product');
      const detail=document.createElement('small');detail.textContent=`EAN: ${item.ean || 'não informado'} · Código: ${item.codigo || '—'} · ${item.apresentacao || ''}`;product.append(detail);
      cell(row,money(item.preco),'num');cell(row,money(item.custo),'num');
      cell(row,present(item.margem_bruta)?number(item.margem_bruta)+'%':'—','num');
      cell(row,number(item.estoque),'num');cell(row,number(item.vendas30),'num');cell(row,dateBR(item.ultima_entrada));
      const badge=document.createElement('span');badge.className='badge '+(item.motivo_revisao==='margem_baixa'?'attention':item.revisar?'danger':'ok');badge.textContent=item.motivo_descricao;
      cell(row,'').append(badge);
      const button=document.createElement('button');button.className='small-btn';button.type='button';button.textContent='Consultar mercado';button.disabled=!item.ean;
      button.addEventListener('click',()=>{
        marketController?.abort();marketRequest++;marketItems=[];renderMarket();$('market-search').disabled=false;
        $('eanmerc').value=item.ean;$('selected-product').textContent=item.descricao;
        message('marketmsg','Consulte as observações importadas deste EAN.');tab('mercado');$('market-search').focus();
      });cell(row,'').append(button);$('rows').append(row);
    });
  }
  async function load(params, nextOffset=0) {
    controller?.abort();controller=new AbortController();const token=++requestId;
    params=new URLSearchParams(params);params.set('offset',String(nextOffset));
    $('product-scroll').setAttribute('aria-busy','true');$('previous').disabled=true;$('next').disabled=true;
    message('msg','Consultando produtos no Alpha7…');
    try {
      const data=await json('/api/revisao/produtos?'+params,{signal:controller.signal});
      if(token!==requestId)return;
      current=data.items;offset=nextOffset;hasMore=data.has_more;applied=new URLSearchParams(params);
      const withoutOffset=new URLSearchParams(params);withoutOffset.delete('offset');dirty=withoutOffset.toString()!==parameters().toString();
      renderProducts(current);
      $('total').textContent=number(data.total);$('shown').textContent=number(current.length);
      $('low-margin').textContent=number(current.filter(r=>r.motivo_revisao==='margem_baixa').length);
      $('inconsistent').textContent=number(current.filter(r=>['preco_inconsistente','custo_inconsistente'].includes(r.motivo_revisao)).length);
      $('applied').textContent=`Margem mínima do filtro: ${number(params.get('margem_minima'))}% · ${params.get('somente_revisar')==='true'?'Somente revisão':'Todos os itens'}`;
      $('page-label').textContent=current.length?`${offset+1}–${offset+current.length}${data.total!==null?' de '+number(data.total):''}`:'Nenhum item nesta página';
      message('msg',`${current.length} produtos exibidos${data.demo?' · DEMONSTRAÇÃO com amostras do pacote':''}. ${data.criterio}`+(dirty?' Filtros alterados durante a consulta. Clique em Consultar produtos para aplicar.':''));
    } catch(error) {
      if(error.name==='AbortError'||token!==requestId)return;
      current=[];applied=null;hasMore=false;renderProducts([]);
      ['total','shown','low-margin','inconsistent'].forEach(id=>$(id).textContent='—');$('page-label').textContent='';$('applied').textContent='';
      message('msg',error.message,true);
    } finally {if(token===requestId) {$('product-scroll').setAttribute('aria-busy','false');updatePages();}}
  }
  $('product-form').addEventListener('submit',event=>{event.preventDefault();if(validPeriod()) {$('period-filter').open=false;load(parameters());}});
  $('previous').addEventListener('click',()=>load(applied,Math.max(0,offset-100)));
  $('next').addEventListener('click',()=>load(applied,offset+100));
  $('clear').addEventListener('click',()=>{
    $('product-form').reset();$('date-start').value='';$('date-end').value='';periodFields();$('period-filter').open=false;load(parameters());
  });
  $('export').addEventListener('click',()=>{
    const escape=value=>{let text=String(value??'');if(/^[\s]*[=+\-@]/.test(text))text="'"+text;return '"'+text.replace(/"/g,'""')+'"';};
    const columns=[['codigo','Código'],['ean','EAN'],['descricao','Produto'],['preco','Preço atual'],['custo','Custo'],['margem_bruta','Margem bruta (%)'],['estoque','Estoque'],['ultima_entrada','Última entrada'],['motivo_descricao','Motivo']];
    const lines=[columns.map(c=>escape(c[1])).join(';'),...current.map(row=>columns.map(c=>escape(row[c[0]])).join(';'))];
    const url=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download='SonifarmaPrice_pagina_consultada.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  function renderMarket() {
    const items=marketItems.filter(r=>!$('market-group').value||r.grupo===$('market-group').value);
    $('marketrows').replaceChildren();$('market-chart').replaceChildren();
    if(!items.length) {empty($('marketrows'),'Nenhuma observação neste filtro.',6);$('market-chart').textContent='Consulte um EAN para visualizar as observações.';return;}
    items.forEach(item=>{const row=document.createElement('tr');[groups[item.grupo]||item.grupo,item.estabelecimento,money(item.preco),dateBR(item.coletado_em),item.condicao,item.fonte].forEach(text=>cell(row,text));$('marketrows').append(row);});
    const summaries=new Map();
    items.forEach(item=>{if(!present(item.preco)||Number(item.preco)<=0)return;const key=JSON.stringify([item.grupo,item.condicao||'Sem condição informada']);if(!summaries.has(key))summaries.set(key,[]);summaries.get(key).push(Number(item.preco));});
    const maximum=items.reduce((max,item)=>present(item.preco)?Math.max(max,Number(item.preco)):max,0);
    [...summaries].slice(0,12).forEach(([key,values])=>{
      const [group,condition]=JSON.parse(key);values.sort((a,b)=>a-b);const mid=Math.floor(values.length/2),median=values.length%2?values[mid]:(values[mid-1]+values[mid])/2;
      const box=document.createElement('div');box.className='chart-group';const title=document.createElement('h3');title.textContent=groups[group]||group;
      const note=document.createElement('div');note.className='muted';note.textContent=condition+' · '+values.length+' observações';
      const bars=document.createElement('div');bars.className='bars';
      [['Menor',values[0],''],['Mediana',median,'medium'],['Maior',values.at(-1),'high']].forEach(([label,value,style])=>{
        const col=document.createElement('div');col.className='bar-col';const price=document.createElement('span');price.textContent=money(value);
        const bar=document.createElement('div');bar.className='bar '+style;bar.style.height=(maximum?value/maximum*92:0)+'px';bar.setAttribute('aria-hidden','true');const caption=document.createElement('span');caption.textContent=label;col.append(price,bar,caption);bars.append(col);
      });box.append(title,note,bars);$('market-chart').append(box);
    });
    if(summaries.size>12){const note=document.createElement('p');note.textContent='Gráfico limitado aos primeiros 12 grupos/condições. A tabela mantém todas as observações.';$('market-chart').append(note);}
  }
  ['eanmerc','market-days'].forEach(id=>$(id).addEventListener('input',()=>{
    marketController?.abort();marketRequest++;marketItems=[];renderMarket();$('market-search').disabled=false;
    if(id==='eanmerc')$('selected-product').textContent='Consultar produto';
    message('marketmsg','Filtros alterados. Consulte para carregar as observações.');
  }));
  $('market-group').addEventListener('change',renderMarket);
  $('market-form').addEventListener('submit',async event=>{
    event.preventDefault();marketController?.abort();marketController=new AbortController();const token=++marketRequest;
    const params=new URLSearchParams({ean:$('eanmerc').value,dias:$('market-days').value});
    message('marketmsg','Consultando observações importadas…');$('market-search').disabled=true;
    try {const data=await json('/api/mercado/comparar?'+params,{signal:marketController.signal});if(token!==marketRequest)return;marketItems=data.observacoes;renderMarket();message('marketmsg',marketItems.length+' observações encontradas, sem restrição geográfica. '+data.aviso);}
    catch(error){if(error.name!=='AbortError'&&token===marketRequest){marketItems=[];renderMarket();message('marketmsg',error.message,true);}}
    finally{if(token===marketRequest)$('market-search').disabled=false;}
  });
  $('import-form').addEventListener('submit',async event=>{
    event.preventDefault();const file=$('arquivo').files[0];if(!file)return;
    if(file.size>2000000){message('importmsg','O arquivo excede 2 MB.',true);return;}
    const body=new FormData();body.append('arquivo',file);$('import-button').disabled=true;
    try{const data=await json('/api/mercado/importar',{method:'POST',body});message('importmsg',data.importados+' registros importados no banco local. Alpha7 não alterado.');}
    catch(error){message('importmsg',error.message,true);}finally{$('import-button').disabled=false;}
  });
  async function start() {
    json('/api/status').then(data=>{$('mode').textContent=data.mode==='demo'?'DEMONSTRAÇÃO':'ALPHA7 · SOMENTE LEITURA';}).catch(()=>{$('mode').textContent='Conexão indisponível';});
    try{const data=await json('/api/revisao/opcoes');entryAvailable=data.ultima_entrada_disponivel;message('entry-note',data.mensagem);}
    catch(error){message('entry-note','Não foi possível validar a data de entrada. '+error.message,true);}
    $('period').disabled=!entryAvailable;periodFields();renderMarket();load(parameters());
  }
  start();
})();
