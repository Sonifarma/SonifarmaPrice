# Arquitetura e integracoes V1.2

## Descoberta implementada

`app/discovery.py` define a interface `Connector.discover(latitude, longitude, radius) -> list[dict]` e o adaptador `OverpassConnector`. `app/main.py` apenas inclui o novo router. `static/discovery.js` implementa a tela separada. O restante da interface e dos endpoints V1.1 permanece disponivel.

Fonte: endpoint HTTPS fixo `https://overpass-api.de/api/interpreter`, API publica de consulta OpenStreetMap. Nao ha URL arbitraria do operador, scraping de lojas, autenticacao de terceiros ou tentativa de contornar bloqueios. Referencias: https://wiki.openstreetmap.org/wiki/Overpass_API e https://www.openstreetmap.org/copyright. Dados colaborativos sob ODbL, com atribuicao visivel. Respeitar disponibilidade e politica de uso da instancia; o servico nao garante SLA, cobertura ou atualizacao. Qualquer restricao de acesso e tratada como falha, sem contorno.

Consultas `nwr` incluem supermercado, atacarejo, cosmeticos, perfumaria e farmacia. Nodes usam coordenadas proprias; ways/relations usam centro calculado pela fonte. O centro nao equivale necessariamente a entrada da loja; resultados sao filtrados por distancia em linha reta. Nao ha restricao de cidade. Coordenadas da Sonifarma precisam ser verificadas fora do sistema e confirmadas explicitamente no formulario. Nao ha geocodificacao automatica.

Validacoes: latitude/longitude finitas, raios crescentes entre 0,5 e 10 km, maximo cinco etapas e meta entre 1–100. Padrao: 2, 3, 5, 8 e 10 km, meta dez. A cada etapa, deduplica por tipo/ID OSM e recalcula distancia; encerra ao atingir a meta de estabelecimentos classificados e nao bloqueados. Um mesmo estabelecimento cadastrado como node e way pode ainda aparecer duas vezes: reconciliacao por identidade fisica fica pendente.

Classificacao de supermercados/perfumarias parte da categoria OSM, sem alegar verificacao em campo. Farmacias ficam com grupo nulo e exigem revisao, pois marca nao comprova rede e ausencia de marca nao comprova independencia. Operador pode definir um dos quatro grupos e bloquear/desbloquear pelo ID de origem, sempre com motivo. Correcoes nao reescrevem historico e nao recebem precos.

## Armazenamento local aditivo

No mesmo arquivo SQLite independente do ERP:

- `descoberta_execucoes`: data UTC, parametros, estado e snapshot JSON com resultados, origem, coordenadas, distancia, classificacao, confiabilidade e falhas.
- `descoberta_correcoes`: ID OSM, grupo corrigido, bloqueio, motivo, data UTC.
- `descoberta_auditoria`: estado anterior/posterior da correcao e data UTC.

Nenhuma coluna/tabela Alpha7 ou observacao existente e alterada. Conexoes do modulo novo sao fechadas explicitamente. Os backups existentes incluem o arquivo SQLite com as tabelas novas.

## Endpoints e acesso

| Metodo | Caminho | Comportamento |
|---|---|---|
| POST | `/api/descoberta/pesquisar` | busca manual com coordenadas, confirmacao, raios e meta |
| GET | `/api/descoberta/historico?limit=20` | ultimas execucoes (maximo 100) |
| PUT | `/api/descoberta/fontes/{tipo}/{id}` | grupo, bloqueio e motivo auditados |

Todos exigem header `X-Price-Token` igual a `PRICE_ADMIN_TOKEN` do `.env`. Token vazio desabilita os endpoints (503); token incorreto retorna 401. Comparacao em tempo constante; o token nao e salvo no banco ou localStorage. Trata-se de controle de manutencao com identidade compartilhada, nao login por usuario. A auditoria ainda nao identifica operador individual.

Uma pesquisa por processo de cada vez; intervalo minimo de 60s; maximo cinco consultas externas, timeout de rede 30s por etapa e resposta maxima 5 MB/10 mil elementos. Use um unico worker (comando atual); nao e um limitador distribuido. Resposta parcial da fonte e recusada; falhas sao registradas e encerram a expansao, sem retry automatico. HTTP 502 inclui ID da execucao e eventuais resultados de etapas anteriores. A interface apresenta a falha e o historico permanece consultavel. O painel e outras consultas continuam disponiveis.

## Coleta e agendamento futuros — nao implementados

O conector de descoberta nao e conector de precos. Uma futura interface `PriceConnector.collect(establishment, products, cursor)` devera devolver observacoes com EAN validado por checksum, identidade/apresentacao/fabricante, preco normal/promocional em Decimal, condicoes, disponibilidade, data UTC, URL, abrangencia fisica/nacional e confiabilidade, ou erros tipados. Registrar runs/observacoes separados, identidade idempotente e motivo de rejeicao. Nao reutilizar o CSV V1.1 como se ja tivesse essas garantias.

O scheduler futuro usara fila persistente e lock de execucao, limites por fonte, cancelamento e backoff de falhas. Inicialmente desativado; nao criar tarefa Windows nesta entrega. Credenciais de APIs futuras apenas no ambiente local. Fontes comerciais dependem de validacao tecnica e permissao de acesso. Falha de coleta nao gera preco estimado.

O motor futuro separara elegibilidade, referencia de mercado, custo/margem/tributos, limites de variacao e teto regulatorio em funcoes deterministicas. Sem todos os dados obrigatorios, recusar automacao. TXT Alpha7 exige validar a documentacao oficial; aplicacao no ERP depende de interface homologada. Nada disso esta ativo na V1.2.

## Testes e limites de verificacao

Suite Python cobre expansao, distancia, deduplicacao, parada pela meta, revisao, bloqueio, entrada invalida, falha total/parcial, token, persistencia/auditoria, limite de chamadas e regressao dos endpoints/CSV existentes, alem dos backups.

Teste `node tests/test_discovery_browser.cjs` usa Playwright e Chromium, pagina real e respostas de descoberta simuladas. Verifica pesquisa, revisao, historico, falha parcial, escape de HTML e viewport estreita. `TEST_URL`, `PLAYWRIGHT_MODULE` e `CHROMIUM_EXECUTABLE` permitem ajustar o ambiente. Dependencias de teste Python em `requirements-dev.txt`.

Nao houve consulta ao Alpha7 de producao ou execucao Windows. As tentativas de acessar `/api/status` do Overpass no ambiente de desenvolvimento receberam HTTP 406 e HTTP 502 (capacidade esgotada da instancia): conectividade real desta fonte nao foi validada e nenhuma restricao foi contornada. Cobertura de estabelecimentos perto da Sonifarma depende das coordenadas confirmadas e da disponibilidade da fonte. Os testes nao representam coleta comercial real.
