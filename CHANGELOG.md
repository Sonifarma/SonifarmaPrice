# Historico de versoes

## 1.2.0 — 07/11/2026 (branch de desenvolvimento)

- Auditoria da V1.1, guia de arquitetura, README, AGENTS e exemplo `.env.example`.
- Descoberta manual OSM/Overpass com raios configuraveis, origem e historico local.
- Classificacao conservadora, revisao e bloqueio auditados; token exclusivo para novos endpoints.
- Tela de descoberta sem armazenar token no navegador; falhas parciais explicitas.
- Pydantic 2 declarado explicitamente; dependencia httpx separada para testes.
- Validacao: 20 testes Python aprovados, teste de navegador com Playwright/Chromium aprovado e pip check sem conflitos. Fonte real e servidor Windows/ERP ainda nao validados.
- Nenhuma coleta automatica de precos, recomendacao, exportacao TXT ou escrita ERP.

## Base 1.1 e operacao Git

- Importacao do ZIP original, CSV de observacoes e comparacao por raio.
- Atualizacao Git com backup SHA-256, preservacao de .env/data e scripts relativos a propria pasta.
