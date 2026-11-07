# Operacao local — atualizacao sem Git

Windows Server 2019, Python 3.12, pasta `C:\SonifarmaPrice`, ambiente `.venv` proprio e porta 8770. Nao altera nem encerra CRM ou outros sistemas.

## Atualizacao normal

Pare o Price com Ctrl+C no terminal de `iniciar.bat`. Nao permita outra inicializacao durante a manutencao. No PowerShell:

```powershell
cd C:\SonifarmaPrice
.\.venv\Scripts\python.exe .\manutencao.py update
if ($LASTEXITCODE -eq 0) { .\iniciar.bat }
```

Ou use `ATUALIZAR_PRICE.bat`, que chama o Python diretamente sem executar PowerShell. Nenhuma assinatura de script ou alteracao de politica do Windows e necessaria.

O atualizador baixa o ZIP da branch `main` do repositorio Sonifarma/SonifarmaPrice por HTTPS. Git nao precisa estar instalado; `.git` e configuracoes de Git nao sao utilizados. O codigo remoto e validado por sintaxe Python, mas isso nao substitui a revisao e testes antes de integrar uma atualizacao a main. Branches/PRs nao integrados nao sao baixados.

Antes de substituir codigo, valida o pacote, cria backup verificado e confirma que a porta esta livre. Copia apenas arquivos reconhecidos do aplicativo (`app/*.py`, arquivos web de `static`, documentacao e scripts explicitamente permitidos). Nunca copia `.env`, `data`, `.venv`, credenciais ou bancos do pacote. Preserva outros arquivos locais e a pasta do ZIP extraido.

Depois instala `requirements.txt` com o mesmo Python usado para chamar o atualizador. Use sempre o Python de `.venv` do Price, como acima. Nao inicia automaticamente o painel.

## Mesmo fluxo do CRM: atualizar de pasta extraida

Baixe o ZIP pelo GitHub e extraia em uma pasta separada. Informe a raiz que contem `app`, `static`, `requirements.txt` e `manutencao.py`:

```powershell
cd C:\SonifarmaPrice
.\.venv\Scripts\python.exe .\manutencao.py update --source 'C:\SonifarmaPrice\SonifarmaPrice-main'
if ($LASTEXITCODE -eq 0) { .\iniciar.bat }
```

Tambem aceita `--source 'C:\Atualizacoes\SonifarmaPrice.zip'`. Uma pasta extraida antiga pode conter versao antiga: prefira o download automatico quando houver acesso a internet. Somente o download do pacote necessita internet; pip pode precisar acesso para dependencias ausentes.

## Backup e verificacao

Destino padrao: `C:\BackupsSonifarmaPrice`. Para outro disco:

```powershell
.\.venv\Scripts\python.exe .\manutencao.py update --destination 'D:\BackupsSonifarmaPrice'
.\.venv\Scripts\python.exe .\manutencao.py backup --destination 'D:\BackupsSonifarmaPrice'
.\.venv\Scripts\python.exe .\manutencao.py verify --archive 'D:\BackupsSonifarmaPrice\SonifarmaPrice_DATA.zip'
```

Pare o painel antes de backup. ZIP inclui codigo reconhecido, amostras, `.env` e dados de `data`. SQLite usa API de backup para incluir transacoes confirmadas no WAL; cada snapshot e restaurado em pasta temporaria e validado com integrity_check. Manifesto SHA-256 verifica todos os arquivos. Venv e historico Git nao entram. Arquivos fora da lista de codigo e das pastas data/amostras precisam de copia propria.

Os backups contem credenciais e dados comerciais: restrinja acesso e prefira outro disco. Nao ha exclusao automatica de backups. Destino nao pode ficar dentro da instalacao.

## Falhas e reversao

Falha de download, validacao ou backup impede a copia de codigo. Falha de copia tenta restaurar apenas arquivos ja tocados e informa explicitamente se a reversao ficar incompleta. Nao ha garantia transacional contra queda de energia.

Se pip falhar, o codigo novo ja foi copiado. Mantenha o painel parado, corrija a falha e execute:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Para reversao manual, pare o painel, preserve o estado atual, verifique o ZIP anterior e extraia em pasta separada. Reponha somente codigo anterior, sem sobrescrever `.env` ou `data`; reinstale dependencias anteriores e valide. Nao ha rollback automatico das dependencias.

O controle `.ps1` continua como opcao para ambientes que permitem scripts assinados. Suporta `-Origem`, `-Destino` e `-Arquivo`, mas nao e necessario para atualizar.

## Primeira adocao desta correcao

Se seu manutencao.py antigo ainda pede Git, baixe apenas o atualizador novo primeiro, preservando a copia anterior. Use o bloco fornecido na entrega desta correcao; depois todas as proximas atualizacoes usam o comando normal. `.env` e dados nao sao envolvidos nessa substituicao inicial.
