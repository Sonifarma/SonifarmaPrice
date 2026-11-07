# Sonifarma Price Intelligence

Painel FastAPI integrado ao Alpha7 exclusivamente para leitura. Base importada do ZIP SonifarmaPrice e evoluida incrementalmente.

## Versao 1.2

- Produtos, custos, estoque e giro via Alpha7, ou amostras no modo demo.
- Importacao CSV e comparacao de observacoes de precos por EAN e raio.
- Descoberta manual de estabelecimentos OSM/Overpass com expansao de raio, historico, classificacao revisavel e bloqueio de fontes.
- Nenhuma coleta online de precos, recomendacao automatica, exportacao TXT ou escrita no ERP.

## Windows

Pasta `C:\SonifarmaPrice`, Python 3.12, porta 8770, ambiente `.venv` proprio. Consulte [operacao, atualizacao e recuperacao](OPERACAO_LOCAL.md).

```powershell
cd C:\SonifarmaPrice
.\instalar.bat
.\iniciar.bat
```

O instalador preserva `.env` existente. Veja `.env.example`; nunca envie credenciais ao Git. Configure `PRICE_ADMIN_TOKEN` no `.env` e reinicie para habilitar a descoberta. Gere o token localmente com `.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"`. Nao compartilhe o resultado.

Na tela, informe o token e coordenadas verificadas da Sonifarma (Rua Iacanga, 1016, Americana/SP). Coordenadas nao sao fornecidas por estimativa. A busca nao limita municipio; o raio maximo e 10 km. Farmacias ficam pendentes para distinguir redes de independentes.

## Desenvolvimento e testes

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8770
```

Os testes usam fontes simuladas e SQLite temporario. Nao consultam ERP real nem confirmam cobertura da fonte em Americana. Modo demo nao necessita credenciais PostgreSQL.

## Documentacao

- [Especificacao de referencia](docs/ESPECIFICACAO_MESTRE.md)
- [Auditoria da base V1.1](docs/AUDITORIA_V1_1.md)
- [Arquitetura e integracoes V1.2](docs/ARQUITETURA_V1_2.md)
- [Historico de versoes](CHANGELOG.md)

A interface V1.1 e suas importacoes ainda nao possuem login. O token novo protege apenas endpoints de descoberta. Mantenha acesso em rede protegida; autenticacao geral e pendencia anterior a exposicao externa. O repositorio escolhido nesta conversa permanece `Sonifarma/SonifarmaPrice`; nao foi criado ou renomeado para outro repositorio.
