(() => {
  const el = id => document.getElementById('discovery-' + id);
  const groups = {
    supermercados: 'Supermercados / atacarejos', perfumarias: 'Perfumarias',
    farmacias_redes: 'Farmácias de rede', farmacias_independentes: 'Farmácias independentes'
  };
  const headers = () => ({'Content-Type': 'application/json', 'X-Price-Token': el('token').value});
  async function api(url, options) {
    const response = await fetch(url, {...options, headers: headers()});
    const data = await response.json();
    if (!response.ok && !data.execucao_id) {
      throw Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data));
    }
    return data;
  }
  function cell(row, text) {
    const td = document.createElement('td'); td.textContent = text; row.append(td); return td;
  }
  function render(items) {
    el('rows').replaceChildren();
    items.forEach(item => {
      const row = document.createElement('tr');
      const source = cell(row, item.nome + ' ');
      const link = document.createElement('a'); link.textContent = item.fonte_id;
      link.href = item.url; link.target = '_blank'; link.rel = 'noopener'; source.append(link);
      const select = document.createElement('select');
      select.add(new Option('Pendente de classificação', ''));
      Object.entries(groups).forEach(([key, label]) => select.add(new Option(label, key)));
      select.value = item.grupo || ''; cell(row, '').append(select);
      cell(row, item.distancia_km.toLocaleString('pt-BR') + ' km');
      cell(row, item.bloqueado ? 'Bloqueado' : item.classificacao_motivo);
      const action = cell(row, '');
      const blocked = document.createElement('input'); blocked.type = 'checkbox';
      blocked.style.width = 'auto'; blocked.checked = item.bloqueado;
      const label = document.createElement('label'); label.append(blocked, ' Bloquear ');
      const reason = document.createElement('input'); reason.placeholder = 'Motivo da correção'; reason.maxLength = 300;
      const save = document.createElement('button'); save.textContent = 'Salvar revisão';
      save.addEventListener('click', async () => {
        save.disabled = true;
        try {
          const result = await api('/api/descoberta/fontes/' + item.fonte_id, {
            method: 'PUT', body: JSON.stringify({grupo: select.value || null, bloqueado: blocked.checked, motivo: reason.value})
          });
          el('message').textContent = result.mensagem;
        } catch (e) { el('message').textContent = 'Erro: ' + e.message; }
        finally { save.disabled = false; }
      });
      action.append(label, reason, save); el('rows').append(row);
    });
  }
  el('form').addEventListener('submit', async event => {
    event.preventDefault(); el('search').disabled = true;
    el('message').textContent = 'Pesquisando. A expansão pode levar até 150 segundos…';
    try {
      const data = await api('/api/descoberta/pesquisar', {method: 'POST', body: JSON.stringify({
        latitude: Number(el('lat').value), longitude: Number(el('lon').value),
        coordenadas_confirmadas: el('confirm').checked,
        raios_km: el('radii').value.split(';').map(x => Number(x.trim().replace(',', '.'))),
        quantidade: Number(el('target').value)
      })});
      render(data.estabelecimentos);
      el('message').textContent = `Execução ${data.execucao_id}: ${data.estado}. ${data.validos} classificados e não bloqueados. Meta ${data.meta_atingida ? 'atingida' : 'não atingida'}. Raios: ${data.raios_consultados.join(', ')} km. ` + data.aviso + (data.falhas.length ? ' A fonte falhou; nenhum resultado foi inventado.' : '');
    } catch (e) { el('message').textContent = 'Erro: ' + e.message; }
    finally { el('search').disabled = false; }
  });
  el('history').addEventListener('click', async () => {
    try {
      const data = await api('/api/descoberta/historico?limit=20', {method: 'GET'});
      el('runs').textContent = data.execucoes.map(run => `#${run.id} · ${run.criado_em} · ${run.estado} · ${run.resultado.validos} classificados · raios ${run.resultado.raios_consultados.join(', ')} km`).join('\n') || 'Nenhuma execução registrada.';
    } catch (e) { el('message').textContent = 'Erro: ' + e.message; }
  });
})();
