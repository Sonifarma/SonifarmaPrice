# Laboratorio de componentes

Experimento isolado, sem importar app/main.py, carregar .env ou acessar Alpha7.

Veja [resultados, limites e comandos PowerShell](../../docs/TESTE_COMPONENTES.md).

`requirements.txt` fixa dependencias diretas do ensaio e nao deve ser incorporado ao requirements de producao. `test_componentes.py` executa 20 testes offline, com HTML/grafo/planilha ficticios e SQLite temporario. `cmed_probe.py` recebe um XLSX local para inspecao estrutural separada; nao aplica precos ou define aliquota.
