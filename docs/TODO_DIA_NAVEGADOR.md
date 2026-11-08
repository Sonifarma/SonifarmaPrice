# Drogaria Todo Dia — V1.5.1

A integração agora usa um navegador Chromium comum, sem login, cookies de usuário ou alteração de mecanismos de proteção. Em 08/11/2026, requisições HTTP diretas recebiam 403/manutenção, mas a navegação normal retornou 200 e os dados públicos do produto.

## Funcionamento

O preparo lê robots.txt, o sitemap indicado pela própria loja e as páginas de produtos do índice. Não usa `/pesquisa`, que está desabilitado para robôs. O índice contém somente URLs e títulos; os preços são lidos na página pública quando o produto é consultado. A descoberta usa a descrição do ERP para selecionar até oito páginas; a oferta só entra como EAN exato quando o UPC do SKU da página confere. EANs ainda não conhecidos precisam de descrição para localizar a página. Uma ausência de resultado não comprova ausência no site: a descoberta é limitada às páginas mais compatíveis e ao índice preparado.

O parser lê JSON público `var product`, sem executar esse texto. Exige EAN válido, preço numérico positivo, SKU disponível/com estoque, venda habilitada, preço visível e ausência de marketplace. Usa o preço de venda do SKU, não o preço de lista, parcela ou mínimo de variações. Ofertas com EAN diferente aparecem como candidatos por descrição e exigem escolha, seguindo o fluxo existente.

A fonte participa do gráfico por EAN e da comparação por composição, conforme os mesmos critérios de apresentação já usados pelo Price. O raio seleciona a rede por suas lojas cadastradas e não confirma preço na filial. Condições de CEP, frete, PBM e descontos por quantidade continuam indicadas na oferta.

## Instalação/atualização no servidor

Pare o Price com Ctrl+C e execute no PowerShell:

```powershell
cd C:\SonifarmaPrice
.\.venv\Scripts\python.exe .\manutencao.py update
if ($LASTEXITCODE -ne 0) { throw 'A atualizacao falhou.' }
.\.venv\Scripts\python.exe -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'A instalacao do navegador falhou.' }
.\.venv\Scripts\python.exe -m app.todo_dia preparar
if ($LASTEXITCODE -eq 0) { .\iniciar.bat }
```

A dependência Python do navegador é instalada pelo atualizador. O comando Playwright instala o Chromium na conta que executará o Price; não requer Git. O primeiro preparo percorre o índice público, mostra progresso e leva alguns minutos. Se houver interrupção, execute `preparar` novamente: retoma páginas recentes já salvas. Um índice incompleto gera aviso explícito e não é tratado como prova de produto ausente.

Para renovar o índice depois de mudanças no catálogo, pare o Price e execute `python -m app.todo_dia preparar` com o Python da `.venv`. Páginas do índice com mais de um dia são renovadas. `--atualizar` força renovar todas. O preparo não coleta todos os preços nem roda periodicamente sozinho.

`PRICE_BROWSER_EXECUTABLE` pode indicar um Chromium já instalado. No desenvolvimento Linux, `/usr/bin/chromium` é usado quando disponível; no Windows, o padrão é o navegador instalado pelo Playwright. O navegador usa perfil isolado temporário, JavaScript desabilitado e só carrega documentos do host cadastrado, sem anúncios, imagens ou rastreadores. Mantém pelo menos um segundo entre documentos e respeita crawl-delay. Não instala serviços nem grava no ERP.

## Cache e falhas

Índice, páginas e ofertas ficam no SQLite local já preservado pelo atualizador. Preços têm cache de 15 minutos e mantêm a data real de leitura da página, mesmo quando reutilizados por outra consulta. Falhas preservam a última coleta e sua data no cache externo; a tela sinaliza coleta anterior. Indisponibilidade do navegador ou mudança de formato não produz preços estimados.

## Validação real

Consulta integrada por EAN e descrição verificada em 08/11/2026: `SIMETICONA 40MG 20CPR MEDLEY`, EAN `7896422522823`, R$ 8,47. O índice preparado continha 17.229 URLs de produtos. Outra página pública verificada: `SIMETICONA 75MG GOTAS 15ML MEDLEY`, EAN `7896422504744`, preço de venda R$ 9,10 em 08/11/2026. A disponibilidade e o preço variam; esse valor não é embutido no código. Os testes usam produtos fictícios para conferir EAN, preço de SKU, indisponibilidade, marketplace, cache, índice incompleto, origem das URLs e integração por raio.
