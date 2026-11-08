# Droga Raia e preços de oferta — V1.6.0

A Droga Raia agora integra a consulta por EAN, a busca por descrição e a comparação por composição. Usa a busca pública `/search?w=...` e os dados estruturados das páginas de produto, sem login, checkout ou APIs privadas. O catálogo não é VTEX. Os caminhos de navegação consultados são permitidos pelo robots.txt da fonte; não usa `/catalogsearch`.

A rede só participa quando há loja identificada pelo nome no raio, incluindo Droga Raia, Raia e Droga Raia com nome da filial. A raiz de CNPJ do grupo RD também é usada pela Drogasil e não identifica sozinha uma filial Raia. Não há multiplicação do preço pelo número de filiais.

Na página do produto, exige EAN exato, produto ativo, estoque disponível e venda própria (`is3p=false`, sem vendedor de marketplace). Confere o endereço canônico pelo `url_key`. A descoberta aceita até quatro páginas para EAN e até seis para descrição/composição; ausência não comprova falta de oferta em todo o site. Candidatos com EAN diferente continuam exigindo conferência e escolha.

## Preço de oferta

- Raia: usa o preço de venda atual `liveComposition.livePrice.valueTo`, com alternativa `price_aux.value_to`, e apresenta o preço regular `value_from` quando maior. Se houver `pixPrice` numérico menor, apresenta esse preço com a condição **pagamento no Pix**, separada no gráfico por condição.
- Drogal e São Paulo: usa `commertialOffer.Price`, que é o preço de venda atual, e identifica oferta quando menor que `ListPrice`.
- Todo Dia: usa o preço de venda do SKU, priorizando `PromotionPrice` válido quando menor que `RetailPrice`, e mantém `ListPrice` como referência.

A tabela apresenta **De ... por ...** nas ofertas identificadas. Os gráficos usam o preço efetivamente exibido. Descontos por quantidade, PBM, CPF, clube, cupons ou `bestPrice` sem regras públicas suficientes não são presumidos como preço de uma unidade. As condições permanecem visíveis e separadas nos gráficos. Os valores são preços de site, sem confirmação da filial ou frete. Cache continua em 15 minutos; registros antigos recebem os novos campos de identificação de oferta na próxima coleta.

## Validação

Em 08/11/2026, consulta real por EAN retornou Soro Fisiológico ADV Farma 10 ampolas de 5ml, EAN 7896230304536, R$ 14,99; preço regular e de venda eram iguais, sem desconto identificado. Simeticona Medley 40mg/20 comprimidos, EAN 7896422522823, retornou R$ 14,12 naquela coleta. Valores são evidência de teste e não estão fixados no código.

Testes verificam preço regular/oferta, Pix com condição, quantidade/PBM não aplicados como preço comum, marketplace, EAN e endereço, indisponibilidade, CNPJ compartilhado e inclusão da Raia pelo raio. Teste de navegador confere a exibição De/por e os gráficos existentes.

## Atualização

Sem dependência nova nesta versão. Quem já preparou a Todo Dia na V1.5.1 pode usar os comandos habituais de atualização. O preparo do navegador e catálogo da Todo Dia continua descrito em `TODO_DIA_NAVEGADOR.md` para instalações que ainda não o executaram.

## Alternativa de acesso — V1.7.2

Falhas no acesso direto agora acionam leitura pública por Chromium. A mensagem por EAN não é mais substituída por uma falha posterior de descrição. Veja instalação, diagnóstico e critérios de reconhecimento em [Concorrentes e coleta](CONCORRENTES_E_COLETA_V1_7_2.md).

## Leitura normal no Windows — V1.7.4

A alternativa da Raia agora usa JavaScript ativo e, no Windows, uma janela temporária do navegador do sistema. A Todo Dia conserva seu modo anterior. Veja [configuração, diagnóstico e limites](RAIA_NAVEGADOR_WINDOWS_V1_7_4.md).
