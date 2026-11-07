# Teste de componentes candidatos — 07/11/2026

Base: main `bfdf67e`. Experimentos isolados em Python 3.12/Linux; nenhum acesso ao Alpha7, alteracao no servidor Windows ou integracao dessas dependencias no requirements de producao. A V1.2 do PR #1 continua separada.

## Resultado

**20 testes do laboratorio aprovados**, **10 testes existentes do atualizador aprovados**, `pip check` sem conflitos no ambiente experimental.

| Componente | Versao testada | Evidencia | Decisao |
|---|---|---|---|
| price-parser | 0.5.1 | BRL com centavos/milhar, ausencia de preco, percentual e zero | Util com campo de preco bem delimitado; nao interpretar texto de oferta inteira |
| extruct | 0.18.0 | Product/Offer JSON-LD, EAN, moeda, disponibilidade, multiplas ofertas e pagina vazia | Candidato para fontes autorizadas com dados estruturados |
| python-stdnum | 2.2 | checksum valido/invalido, EAN-8, GTIN-14 com zero inicial e entradas invalidas | Util como dependencia, respeitando LGPL; nao comprova identidade/apresentacao do produto |
| APScheduler | 3.11.3 | job executado, fuso America/Sao_Paulo, persistencia SQLite entre instancias do scheduler | Candidato estavel; nao usar branch master 4 prerelease |
| SQLAlchemy | 2.1.8 | suporte ao jobstore SQLite do APScheduler | Dependencia apenas do laboratorio nesta entrega |
| OSMnx | 2.1.1 | distancia geodesica e escolha de rota em grafo sintetico | Funciona localmente; avaliar custo das dependencias geograficas antes de adotar |
| openpyxl / CMED | 3.1.5 | arquivo XLSX sintetico e estrutura de arquivo oficial real | Base para importador dedicado; nao representa motor regulatorio pronto |

Os testes de extracao usam HTML ficticio e nao acessam farmacias. OSMnx nao foi testado contra a fonte geográfica online nesta etapa. Persistencia do scheduler foi testada entre instancias no mesmo processo com banco temporario, sem ativar coleta ou tarefas no servidor. Nenhum preco foi recomendado ou aplicado.

## Limites encontrados na interpretacao de precos

Resultados reais observados do price-parser ao receber a string inteira:

| Entrada | Valor extraido | Problema |
|---|---|---|
| `R$ 1.234,56` | 1234.56 | Caso simples correto |
| `De R$ 19,90 por R$ 12,90` | 19.90 | Extrai o preco anterior |
| `3x de R$ 12,00` | 3 | Extrai quantidade de parcelas |
| `R$ 12,90 no clube` | 12.90 | Nao classifica restricao comercial |
| `Free` | 0 | Precisa de rejeicao pela regra comercial |

Os testes que documentam esses limites passam ao confirmar o comportamento observado, nao por terem corrigido as ambiguidades. Um conector precisa selecionar o campo correto e validar BRL, EAN/apresentacao, preco finito/positivo, condicoes, data, disponibilidade e abrangencia da oferta. JSON-LD de e-commerce nao comprova preco de loja fisica.

## Verificacao da fonte CMED

Pagina oficial consultada: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/precos

Arquivo disponibilizado na pagina durante o teste:
https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/precos/arquivos/lista_pmc__20261009_115232673.xlsx/@@download/file

- Download real por HTTPS: **12.733.415 bytes**.
- SHA-256: `d36148255b4529241b564c6df2e1fdd40e4f37d1d75806bc9a0f1f767aa12019`.
- Publicacao indicada no arquivo: **09/10/2026 17h30min**.
- Abas: `Cabecalho` (nome original com acento) e `Lista PMC`.
- Cabecalho dos dados encontrado na linha 1 da aba `Lista PMC`.
- **73 colunas**, dimensao declarada de **26.635 linhas**; o experimento leu apenas **cinco linhas de dados**, sem importar a lista completa.
- Colunas incluem EAN, PF e PMC, aliquotas diversas, cenarios ALC e sem impostos.

O primeiro teste usando apenas a aba ativa falhou. O probe foi corrigido para procurar o cabecalho nas primeiras 100 linhas de cada aba, preservando notas da capa. Foi acrescentado teste de regressao com uma aba explicativa antes dos dados. Isso evidencia por que nao devemos copiar um importador presumindo um formato fixo.

`cmed_probe.py` e um experimento proprio de leitura estrutural. **O pipeline CMED de terceiros nao foi executado integralmente nem integrado.** O projeto pesquisado serviu como referencia de abordagem; nao copiamos seus dados analiticos como regras regulatorias.

Pendencias: importar todas as linhas; preservar identificadores como texto; reconciliar EANs/registro/apresentacao; validar duplicidades; tratar notas e casos sem PMC; selecionar aliquota/regime aplicavel; verificar vigencia, excecoes e fonte oficial. Nao calcular margem pelo simples intervalo PF/PMC. PMVG nao e PMC.

## Licencas e adocao

Referencias examinadas: [price-parser](https://github.com/scrapinghub/price-parser) e [extruct](https://github.com/scrapinghub/extruct) (BSD-3-Clause); [python-stdnum](https://github.com/arthurdejong/python-stdnum) (LGPL); [APScheduler](https://github.com/agronholm/apscheduler) e [OSMnx](https://github.com/gboeing/osmnx) (MIT); [pipeline CMED](https://github.com/IgorBusnardo/pipeline-precos-medicamentos) (MIT).

Antes de distribuir dependencias com o produto, manter avisos/licencas e cumprir as obrigacoes das versoes escolhidas e suas dependencias. Para EAN isolado, tambem podemos implementar o checksum com base na especificacao e testes, sem incorporar uma biblioteca ampla. Nao copiar codigo de repositorios sem licenca identificada.

## Como repetir sem Git no Windows

Os testes nao sao recebidos pelo atualizador normal: estao em branch experimental e nao alteram a aplicacao. O bloco abaixo baixa essa branch em uma pasta nova, cria outro ambiente virtual e instala as bibliotecas somente nele. **Windows Server 2019 ainda nao foi validado**; este e um ensaio opcional, e falhas devem ser reportadas. Nao precisa parar o Price para esses testes offline. Eles nao escutam na porta 8770 e usam bancos temporarios.

Execute no PowerShell, sem precisar executar arquivo `.ps1`:

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $teste = "C:\SonifarmaPrice\work\componentes_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    New-Item -ItemType Directory -Path $teste | Out-Null
    Invoke-WebRequest -UseBasicParsing -Uri 'https://codeload.github.com/Sonifarma/SonifarmaPrice/zip/refs/heads/test/componentes-precos' -OutFile "$teste\codigo.zip"
    Expand-Archive -LiteralPath "$teste\codigo.zip" -DestinationPath "$teste\codigo"
    $codigo = (Get-ChildItem "$teste\codigo" -Directory | Select-Object -First 1).FullName
    & 'C:\SonifarmaPrice\.venv\Scripts\python.exe' -m venv "$teste\.venv"
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar ambiente de testes.' }
    & "$teste\.venv\Scripts\python.exe" -m pip install -r "$codigo\experiments\componentes\requirements.txt"
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependencias de testes.' }
    & "$teste\.venv\Scripts\python.exe" "$codigo\experiments\componentes\test_componentes.py"
    if ($LASTEXITCODE -ne 0) { throw 'Testes falharam; envie o resultado.' }
}
```

Para repetir aqui no Linux:

```sh
python -m venv work/venv-componentes
work/venv-componentes/bin/python -m pip install -r experiments/componentes/requirements.txt
work/venv-componentes/bin/python experiments/componentes/test_componentes.py
```

A verificacao da planilha real e separada e nao faz parte dos 20 testes offline:

```powershell
# Localizar o ensaio criado acima e informar um XLSX oficial ja baixado.
$teste = (Get-ChildItem 'C:\SonifarmaPrice\work' -Directory -Filter 'componentes_*' | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
$codigo = (Get-ChildItem "$teste\codigo" -Directory | Select-Object -First 1).FullName
& "$teste\.venv\Scripts\python.exe" "$codigo\experiments\componentes\cmed_probe.py" 'C:\Atualizacoes\lista_pmc.xlsx'
```

## Proximo passo recomendado

Validacao de EAN e importador CMED em modulo separado, com testes de duplicidade e tratamento das notas. Em seguida, integrar extracao JSON-LD de uma fonte autorizada identificada, mantendo precos online separados dos confirmados por filial. Agendamento entra apos validar o conector; OSMnx e opcional para trajetos.
