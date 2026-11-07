# Atualizacao do SonifarmaPrice no Windows

O fluxo segue o CRM: parar, criar backup verificado, atualizar o codigo e iniciar para validar. Estes comandos sao exclusivos do Price (porta 8770); nao encerram o CRM.

## Primeira instalacao com Git

Instale Git para Windows e Python 3.12. Se o Price atual veio do ZIP, pare-o com Ctrl+C no terminal de `iniciar.bat` e mantenha essa instalacao como copia. No PowerShell, crie uma instalacao em outra pasta:

```powershell
git clone https://github.com/Sonifarma/SonifarmaPrice.git C:\SonifarmaPriceGit
Copy-Item C:\SonifarmaPrice\.env C:\SonifarmaPriceGit\.env
if (Test-Path C:\SonifarmaPrice\data) {
    Copy-Item C:\SonifarmaPrice\data C:\SonifarmaPriceGit\data -Recurse
}
cd C:\SonifarmaPriceGit
.\instalar.bat
.\iniciar.bat
```

Ajuste os caminhos se sua instalacao original estiver em outra pasta. Nao execute as duas instalacoes ao mesmo tempo. O novo `.venv` e criado localmente; `.env` existente nao e substituido. Os scripts usam sua propria pasta, sem depender de `C:\SonifarmaPrice`.

## Proximas atualizacoes

1. Pare `iniciar.bat` com Ctrl+C. Garanta que outros operadores nao iniciarao o Price durante a manutencao.
2. Na pasta da instalacao Git, execute:

```powershell
.\ATUALIZAR_PRICE.bat
```

Para escolher o destino do backup, prefira outro disco:

```powershell
.\ATUALIZAR_PRICE.bat -Destino 'D:\BackupsSonifarmaPrice'
```

O comando recusa porta ocupada, branch diferente de `main`, alteracoes locais de codigo e historico divergente. Busca `origin/main` no repositorio Sonifarma/SonifarmaPrice e aplica apenas fast-forward, sem sobrescrever o historico. Se ja estiver na mesma versao, informa que o codigo esta atualizado.

Antes de alterar o codigo, salva os arquivos versionados, `.env` e todos os arquivos de `data`, incluindo arquivos auxiliares SQLite, em ZIP com manifesto SHA-256. Valida a integridade dos bancos SQLite e verifica os hashes do ZIP. `.venv` e `.git` ficam fora do backup. O destino padrao e `BackupsSonifarmaPrice` ao lado da pasta do projeto. Nao ha exclusao automatica de backups. Eles contem credenciais do `.env`: restrinja o acesso ao destino.

Dados em `data`, configuracoes e credenciais nao sao recebidos pelo Git. A atualizacao tambem recusa uma versao remota que tente incluir esses arquivos protegidos.

Depois de atualizar o codigo, instala `requirements.txt` no ambiente virtual existente. Nao inicia o painel automaticamente.

3. Execute `iniciar.bat`, abra http://localhost:8770 e valide consultas e importacao. Use Ctrl+F5 no navegador.

## Backup e verificacao separados

Sempre pare o painel antes do backup:

```powershell
.\SONIFARMA_PRICE_CONTROLE.ps1 backup -Destino 'D:\BackupsSonifarmaPrice'
.\SONIFARMA_PRICE_CONTROLE.ps1 verify -Arquivo 'D:\BackupsSonifarmaPrice\SonifarmaPrice_DATA.zip'
```

Se a politica do Windows bloquear PowerShell, solicite a liberacao/assinatura dos scripts ao administrador. Nao e necessario alterar a politica global. Alternativa usando diretamente o Python:

```powershell
.\.venv\Scripts\python.exe .\manutencao.py update --destination 'D:\BackupsSonifarmaPrice'
```

## Falha ou recuperacao

Se o backup falhar, o codigo nao sera atualizado. Se a instalacao de dependencias falhar depois do Git, o codigo novo ja estara aplicado: mantenha o painel parado, corrija o erro e repita `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` antes de iniciar. O atualizador informa o commit anterior. Nao ha rollback automatico das dependencias.

Para recuperar arquivos, verifique o ZIP, extraia-o em outra pasta e compare o conteudo com a instalacao parada antes de copiar. Preserve o estado atual; nao reverta bancos de dados inadvertidamente. O backup nao inclui o historico Git e nao substitui uma copia em outro disco.

`ATUALIZAR_V1_1.bat` e o comando antigo para instalar dependencias do pacote ZIP; para baixar versoes do GitHub use `ATUALIZAR_PRICE.bat`.

## Adocao da V1.2

A V1.2 e entregue em branch/PR. O comando padrao atualiza apenas `main`; somente recebe esta versao depois de integrar o PR. Nao aplique a branch diretamente na instalacao em producao.

Com o painel parado e o PR integrado:

```powershell
cd C:\SonifarmaPrice
.\ATUALIZAR_PRICE.bat
```

Se a atualizacao concluir, gere um token no proprio servidor:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
notepad .env
```

Acrescente `PRICE_ADMIN_TOKEN=SEU_TOKEN_GERADO` ao `.env`, preservando MODE e todas as variaveis A7 existentes. Nao cole o token no chat ou no GitHub. Nao reutilize senha do PostgreSQL. Inicie com `iniciar.bat`; na tela nova, informe o token e coordenadas verificadas. Nenhuma coordenada foi inventada nesta entrega. Se nao configurar token, as funcoes V1.1 continuam disponiveis e a descoberta permanece desabilitada.

Para reverter o codigo da V1.2, pare o painel, preserve uma copia da instalacao atual e valide o ZIP criado antes da atualizacao com `SONIFARMA_PRICE_CONTROLE.ps1 verify -Arquivo ...`. Extraia esse ZIP em uma pasta separada. Reponha somente os arquivos de codigo da versao anterior (pastas `app` e `static`, `requirements.txt`, scripts e documentacao) a partir da copia verificada; nao copie `.env` ou `data` sobre os arquivos atuais. Reinstale o requirements anterior e valide o painel. Tabelas SQLite novas podem permanecer: o codigo V1.1 nao as utiliza. Dependencias nao possuem rollback automatico. Se a instalacao ficar com alteracoes Git locais, revise-as antes da proxima atualizacao; o atualizador as bloqueia para evitar sobrescrita silenciosa.
