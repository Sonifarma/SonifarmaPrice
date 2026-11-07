# Auditoria da base V1.1

Base examinada: commit `f9e65a0`, repositorio `Sonifarma/SonifarmaPrice`, em 07/11/2026. Relatorio anterior as alteracoes estruturais da V1.2; nao representa teste no servidor Windows ou no ERP real.

## Estrutura e arquivos

- `app/main.py`: FastAPI, PostgreSQL, CSV demo, SQLite e importacao/comparacao.
- `static/index.html`: interface unica com JavaScript embutido; `modelo_precos.csv`: modelo de importacao.
- `amostras/`: sete CSVs (produto, embalagem, estoque, custo, historico de custo, venda, itemvenda).
- `.env.exemplo`: configuracao ficticia; `.env` local ignorado pelo Git.
- `requirements.txt`: FastAPI, Uvicorn, psycopg2-binary, python-dotenv, python-multipart; intervalos de versao amplos, sem lock.
- `instalar.bat`, `iniciar.bat`: Python 3.12, venv local, servidor em `0.0.0.0:8770`.
- `ATUALIZAR_V1_1.bat`: somente dependencias; `ATUALIZAR_PRICE.bat`, `SONIFARMA_PRICE_CONTROLE.ps1`, `manutencao.py`: atualizacao Git com backup e hashes.
- `tests/test_manutencao.py`: seis testes anteriores para backup, corrupcao, protecao e fast-forward.
- `README.txt`, `LEIA_PRIMEIRO_V1_1.txt`, `OPERACAO_LOCAL.md`: instalacao e operacao existentes.

## Endpoints existentes

| Metodo | Caminho | Funcao |
|---|---|---|
| GET | `/` | HTML local |
| GET | `/static/*` | arquivos estaticos |
| GET | `/api/status` | modo, unidade, automacoes desativadas |
| GET | `/api/products` | busca por descricao, codigo ou EAN, limit 1–500, offset |
| GET | `/api/diagnostic` | nomes de tabelas/colunas do schema atual |
| GET | `/api/mercado/status` | numero de observacoes locais |
| POST | `/api/mercado/importar` | CSV UTF-8, `;`, ate 2 MB/5000 linhas |
| GET | `/api/mercado/comparar` | EAN, coordenadas, raio 0,5–50 km, janela 1–90 dias |

FastAPI tambem disponibiliza OpenAPI e documentacao padrao. Nenhum endpoint modifica o Alpha7.

## Configuracao e SQL

`MODE=demo|postgres`; `A7_HOST`, `A7_PORT`, `A7_DATABASE`, `A7_USER`, `A7_PASSWORD`, `A7_UNIT`. `.env` carregado a partir da raiz; variaveis de ambiente preexistentes prevalecem.

Conexao PostgreSQL: timeout 5s, transacao somente leitura, statement timeout 12s. SQL parametrizado com quatro filtros de unidade; join produto/embalagem; laterais para ultimo custo e estoque pelo maior ID; agregado de vendas/itens em 30 dias com status F. Nao ha DDL no ERP. Escolher maior ID como registro vigente e o significado de status F continuam pressupostos a validar na base real. `historicocusto.csv` nao e utilizado na consulta atual.

Diagnostico consulta `information_schema.columns`; nao valida tipos, indices, plano, semantica dos campos ou consistencia dos resultados. SQLite cria `observacoes` e indice EAN no banco separado `data/mercado.sqlite3`. Precos locais usam REAL; valores monetarios PostgreSQL Decimal sao convertidos a float na resposta.

## Implementado e limites

Produtos, preco, custo, estoque e giro estao presentes no codigo; o usuario relatou funcionamento anterior no servidor. Esta auditoria nao reproduziu esse acesso. CSV possui validacao por linha e rejeita o arquivo inteiro se houver linha invalida. Comparacao usa Haversine e ordena pelo menor preco importado, com aviso de que nao sao precos automaticamente verificados. Margem exibida e bruta simplificada, sem tributos/taxas.

Nao existem descoberta online, coleta de precos, agendamento, ABC, fabricantes na resposta, motor de recomendacao, limites regulatorios, TXT Alpha7, login ou auditoria comercial completa na base V1.1. A interface carrega somente 200 produtos e nao oferece avancar pagina.

## Problemas e riscos

1. **Acesso:** endpoints sem autenticacao, inclusive importacao e diagnostico; bind de rede aberto. Exigir rede interna protegida; autenticacao geral e controle por usuario continuam pendentes.
2. **Dados de preco:** EAN validado apenas como 8–14 digitos, sem digito verificador; importacoes repetidas duplicam observacoes; data futura nao e recusada; comparacao nao confirma apresentacao, fabricante ou condicoes equivalentes. Nenhum desses dados deve acionar precificacao automatica.
3. **Consultas:** giro agregado pode ser pesado, apesar do timeout; custo/estoque por maior ID exigem validacao semantica. Sem acesso real, nao houve EXPLAIN nem confirmacao de tipos.
4. **Recursos:** comparacao carrega todos os registros do EAN na janela, sem paginacao. Conexoes SQLite antigas usam context manager sem fechamento explicito; melhorias devem ser incrementais.
5. **Erros:** falhas PostgreSQL retornam mensagem generica, mas o codigo nao implementa logging explicito do erro apesar de mencionar log.
6. **Amostras:** IDs de produtos e embalagens dos CSVs fornecidos nao se correspondem; `demo_rows()` retorna lista vazia nesta base. Nao corrigido silenciosamente: testes de paginacao usam fixtures coerentes, sem alterar CSVs originais.
7. **Operacao:** instalador original nao verifica imediatamente toda falha de pip; scripts Windows ainda precisam de ensaio no servidor. Dependencias com faixas amplas podem mudar entre instalacoes.
8. **Git:** `.env` e bancos locais nao estao rastreados. Nao foram encontrados segredos literais nos arquivos de configuracao rastreados; exemplos usam placeholders. O repositorio atualmente e publico; o prompt menciona um futuro privado com outro nome. Nenhuma mudanca de visibilidade/nome foi feita sem uma solicitacao especifica sobre o repositorio escolhido.

## Plano aprovado pelo escopo solicitado

1. Documentar base e testes de regressao, mantendo endpoints e SQL antigos.
2. Acrescentar modulo de descoberta com conector OSM, raio limitado e coordenadas confirmadas.
3. Registrar resultados/falhas em tabelas locais novas, sem alterar `observacoes`.
4. Revisar grupos e bloquear fontes, com auditoria e token local exclusivo.
5. Testar regras, API e navegador; entregar em branch/PR. Coleta de precos e automacao comercial seguem desativadas.
