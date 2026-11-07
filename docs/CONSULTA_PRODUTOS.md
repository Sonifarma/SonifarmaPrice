# Consulta de produtos no padrao SonifarmaCRM

Mudanca incremental sobre a main com a correcao de atualizacao sem Git (PR #2). A descoberta geografica do PR #1 e o laboratorio do PR #3 continuam separados. Nao e uma substituicao de backend nem integracao da Proffer.

## O que mudou

- Tema Sonifarma baseado no CRM: turquesa `#00a6ad`, botoes `#00777d`, laranja `#ff6900`, fundo claro e logo local.
- Navegacao separada para produtos, mercado, importacao e integracao.
- Busca por produto/EAN/codigo, lista compacta, motivo de revisao, estoque, giro e ultima entrada quando disponivel.
- `Mostrar somente itens para revisao` marcado inicialmente. A consulta filtra no servidor antes da paginacao, com contagem completa dos itens filtrados; nao oculta somente linhas da pagina carregada.
- Periodo no formato do CRM: painel recolhido com Hoje, Ontem, Ultimos 7/15/30 dias, Mes atual ate hoje, Mes anterior e intervalo personalizado. Contagem inclusiva: ultimos sete dias = hoje e seis anteriores. Datas calculadas no servidor com fuso America/Sao_Paulo.
- Paginacao de 100 itens e exportacao CSV da pagina carregada. CSV protege campos textuais contra formulas; nao e TXT de importacao Alpha7.
- Botao Consultar mercado leva o EAN para a pesquisa existente. Grafico mostra menor, mediana e maior observacao por grupo **e condicao comercial**, separando preco de clube de preco normal. Observacoes importadas nao sao recomendacoes de preco nem comprovacao de oferta local.
- Importacao CSV/modelo e APIs V1.1 preservados. Tema em `static/sonifarma-theme.css` facilita padronizacao futura; nenhum outro repositorio foi modificado.

## O que significa revisao

A triagem usa apenas dados disponiveis:

1. Preco ausente, nao finito, zero ou negativo: conferir preco atual.
2. Custo ausente, nao finito, zero ou negativo: conferir custo.
3. `(preco - custo) / preco * 100` abaixo do percentual escolhido: margem abaixo do filtro.

O valor inicial de **30% e somente referencia editavel da consulta**, nao uma regra comercial confirmada nem margem liquida. Igualdade com o percentual nao e classificada como abaixo. Custos inconsistentes nao geram preco sugerido. Tributos, taxas, descontos, CMED e concorrencia nao entram nessa triagem. Ficar dentro da faixa nao comprova que o preco esteja adequado ao mercado.

A lista nao aplica alteracoes, nao calcula preco recomendado e nao grava no Alpha7. Itens que nao precisam mudar so podem ser determinados comercialmente apos avaliar fontes e regras; por isso a tela usa o termo **para revisao**, com o motivo explicito.

## Data real da ultima entrada — validacao pendente

Os arquivos existentes fornecem `historicocusto.datahoraconsiderada`, mas isso nao comprova a data de recebimento de mercadoria. O CRM e o Compras consultados tambem nao fornecem um mapeamento validado que possamos reutilizar diretamente. Essa data nao foi usada como substituta.

**Sem mapeamento confirmado, os filtros de data ficam desabilitados e a coluna mostra Nao informada.** A consulta de produtos/margem continua funcionando com Todos os periodos. A API rejeita filtro de data sem fonte configurada, em vez de ignorar silenciosamente o filtro.

Para obter somente estrutura, no servidor e com o `.env` ja configurado:

```powershell
cd C:\SonifarmaPrice
.\.venv\Scripts\python.exe -m app.diagnostico_entradas
```

O comando executa SELECT em information_schema com o usuario somente leitura; retorna ate 600 nomes/tipos de colunas de tabelas candidatas, sem senhas ou dados de pessoas. Se o resultado atingir esse limite, pode ser necessario restringir a busca antes de concluir o mapeamento.

Depois de confirmar fonte, unidade, significado da data e status finalizado, o adaptador suporta uma tabela/view existente com identificador de produto ou embalagem, unidade, data e status na mesma fonte. O mapeamento e feito apenas no `.env` local:

| Variavel | Significado |
|---|---|
| A7_ENTRY_CONFIRMED | `1` somente depois da confirmacao; padrao `0` |
| A7_ENTRY_SCHEMA / A7_ENTRY_TABLE | Schema e tabela/view existente de entradas |
| A7_ENTRY_ID_KIND | `produto` ou `embalagem` |
| A7_ENTRY_ID_COLUMN | Coluna que corresponde ao ID escolhido |
| A7_ENTRY_UNIT_COLUMN | Coluna da unidade, filtrada por A7_UNIT |
| A7_ENTRY_DATE_COLUMN | Data do recebimento confirmado |
| A7_ENTRY_STATUS_COLUMN / A7_ENTRY_STATUS_VALUE | Status que identifica entrada finalizada |

Nao inventar nomes de coluna nem assumir status F sem conferir. O adaptador valida identificadores e a existencia/tipo das colunas antes de consultar. Campos entre tabelas diferentes exigem adaptar o join depois de inspecionar o diagnostico; **nao criar views, indices ou tabelas no ERP** para contornar isso.

A ultima entrada e o MAX da data entre registros da unidade e status configurados. Filtra-se **a ultima entrada**, nao qualquer entrada no periodo. Dia final e inclusivo, com comparacao `< proximo dia`. Timestamp com fuso e convertido para o horario de Sao Paulo antes do filtro. Ordenacao: ultima entrada decrescente, descricao e embalagem como desempate. Fonte em nivel de produto atribui a mesma data as suas embalagens; fonte em nivel de embalagem distingue-as.

## Endpoints e compatibilidade

- GET `/api/revisao/opcoes`: disponibilidade declarada da fonte de entrada e mensagem.
- GET `/api/revisao/produtos`: `q`, `modo`, `periodo`, `inicio`, `fim`, `margem_minima`, `somente_revisar`, `somente_estoque`, `limit` (1–200) e `offset`.
- Endpoints `/api/products`, `/api/status`, `/api/diagnostic` e `/api/mercado/*` existentes permanecem disponiveis.

A nova consulta reutiliza os joins SQL existentes de custo, estoque e giro e os filtros de unidade. Mapeamento de entrada usa identificadores restritos e valores parametrizados. Todas as conexoes novas sao fechadas explicitamente. Limites e timeout somente leitura existentes do Alpha7 permanecem. Contagem global, filtro de margem e agregado de giro podem ser custosos: desempenho e plano precisam ser conferidos no banco real; nenhum indice e criado automaticamente.

A autenticacao geral continua pendente na base V1.1; esta mudanca e visual/consulta e nao deve ser tratada como liberacao para acesso publico.

## Testes executados

- 21 testes Python aprovados: dez de manutencao e onze de regras/API de revisao.
- PostgreSQL embarcado PGlite com tabelas ficticias: unidade, status finalizado, MAX da ultima entrada, exclusao quando ultima entrada ficou fora do periodo, horario 23:59:59, timestamptz, margem/NaN, parametros e filtros antes da paginacao. As consultas foram executadas com default_transaction_read_only=on apos preparar o fixture.
- Playwright/Chromium: tema e assets reais, APIs de triagem com fixture coerente, paginacao, busca, EAN, grafico por condicao, CSV com protecao de formula, HTML escapado, importacao CSV real em SQLite temporario, datas invalidas, bloqueio de datas sem fonte e viewport 390px.
- `pip check`, sintaxe JavaScript e `git diff --check` sem erros.

Os dados de tela usados nos testes sao ficticios. O ERP de producao, Windows Server e mapeamento real de ultima entrada nao foram validados. As amostras CSV antigas permanecem intactas; como os IDs delas nao se relacionam entre produto/embalagem, o modo demo original pode continuar vazio.

Comandos de desenvolvimento:

```sh
MODE=demo .venv/bin/python -m unittest discover -s tests -v
npm install --prefix work/sql-fixture @electric-sql/pglite --no-audit --no-fund
node tests/test_product_review_sql.cjs
```

Para o navegador, em um terminal de desenvolvimento: `.venv/bin/python tests/serve_product_review.py`; em outro: `node tests/test_product_review_browser.cjs`. O servidor de teste usa loopback na porta 18770, fixtures de `tests/test_product_review.py` mais 110 linhas e SQLite temporario; forca MODE=demo e nao consulta o ERP. A fonte de mercado e simulada. `TEST_URL`, `PLAYWRIGHT_MODULE`, `CHROMIUM_EXECUTABLE`, `PGLITE_MODULE` e `PYTHON_EXECUTABLE` permitem ajustar caminhos.

## Atualizacao e reversao

Entregue em branch/PR. Integrar a main somente com autorizacao. A atualizacao padrao baixa main e nao recebe a branch automaticamente. Apos integracao, pare o Price com Ctrl+C:

```powershell
cd C:\SonifarmaPrice
.\.venv\Scripts\python.exe .\manutencao.py update
if ($LASTEXITCODE -eq 0) { .\iniciar.bat }
```

Depois use Ctrl+F5 no navegador. O atualizador sem Git copia os novos `.py`, `.js`, `.css`, `.png` e documentacao permitidos, preserva `.env`, dados e venv, e cria backup verificado. Configure o mapeamento de entrada somente depois de validar o diagnostico; nao altera a configuracao existente.

Para reverter, pare o Price, preserve o estado atual e verifique o backup anterior com `manutencao.py verify --archive CAMINHO`. Extraia em outra pasta e reponha somente codigo anterior, sem sobrescrever `.env` e `data`. Nao ha migracao de banco local nesta entrega. A dependencia nova `tzdata` suporta fuso horario no Windows e pode permanecer instalada. Nenhum outro sistema precisa ser interrompido.

## Ajuste V1.1.2 — pesquisa sem coordenadas

A pedido do usuario, latitude, longitude e raio foram retirados da tela. A pesquisa usa EAN, periodo e grupo e considera observacoes importadas sem restricao geografica; nao presume a localizacao da Sonifarma. A coluna de distancia tambem foi retirada. O filtro geografico fica para uma proxima etapa.

A API existente continua aceitando latitude/longitude juntas para clientes anteriores, mas agora permite omitir ambas. Sem coordenadas retorna filtro_geografico=false, raio_km=null e distancia_km=null. Coordenada isolada e recusada. Dois testes adicionais cobrem a consulta global e a compatibilidade da consulta por raio; o teste de navegador confirma a ausencia dos campos e parametros geograficos.
