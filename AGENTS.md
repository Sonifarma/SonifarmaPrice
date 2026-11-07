# SonifarmaPrice

Preserve o sistema existente; inspecione os arquivos relevantes antes de modificar.

- Windows Server 2019, Python 3.12, `C:\SonifarmaPrice`, `.venv` proprio, porta 8770.
- Nao alterar, interromper ou utilizar bancos, portas e ambientes de outros sistemas.
- Alpha7: somente SELECT, SQL parametrizado, timeouts; nunca DDL ou escrita.
- Dados locais em `data/mercado.sqlite3`. Migracoes aditivas e backups antes de atualizar.
- Nao versionar .env, credenciais, bancos, logs, backups ou exportacoes confidenciais.
- Nao estimar coordenadas da loja nem inventar precos. Fontes devem permitir automacao.
- Precificacao, coleta de precos e aplicacao automatica no ERP permanecem desativadas.
- Alteracoes relevantes em branch e pull request; nao implantar em producao automaticamente.
- Documentar riscos, validacao real e limitacoes. Nunca declarar validacao Windows/ERP sem executa-la.
- Testes: `python -m unittest discover -s tests -v`.
- Ao entregar uma atualizacao, terminar a resposta com comandos PowerShell usando `C:\SonifarmaPrice`; indicar se o PR ainda precisa ser integrado antes de atualizar.
