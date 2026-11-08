# Busca online pela descrição — V1.3.0

A consulta recebe o EAN e a descrição do Alpha7. Quando o catálogo não traz uma oferta pelo EAN, o Price expande abreviações e pesquisa a descrição nas fontes integradas. Também é possível digitar diretamente uma descrição e clicar em Consultar sites online ou Atualizar preços online. Produtos do cadastro sem EAN podem ser consultados pela descrição na ficha ou na pesquisa de mercado.

| Descrição do sistema | Interpretação usada na conferência |
|---|---|
| 20 BI 30CAP MOME | 20 Bi, 30 cápsulas, Momenta |
| FRD GERIA COTIDIAN CLAS G C/7 | Fralda geriátrica Cotidian Clássica, tamanho G, 7 unidades |
| G SIMETICONA 40MG 20CP MEDL | Simeticona, 40 mg, 20 comprimidos, Medley, genérico |

MOME é tratado como Momenta; não é convertido para “mole”. G no início da descrição de medicamento sinaliza genérico; G na descrição da fralda continua sendo tamanho. A tabela de abreviações fica em app/product_search.py.

## Correspondência e preços

A busca textual usa o endpoint público documentado de pesquisa VTEX, limitado às redes integradas, com os mesmos controles de acesso, robots, tamanho, intervalo e timeout. Resultados são conferidos por nome, dosagem, quantidade, forma, tamanho e fabricante. Uma apresentação explicitamente diferente é descartada. Atributos ausentes ficam sinalizados. Na linha 20 Bi, versões identificadas como Momenta/Eurofarma exigem conferir a embalagem e o fabricante.

O EAN idêntico encontrado pela busca textual pode confirmar a oferta automaticamente. Candidatos com EAN diferente ou sem EAN informado no cadastro aparecem separados do gráfico, com apresentação, EAN da fonte, preço de referência, data e link para conferir a embalagem. Clique em **Usar este produto na consulta** para escolher o correspondente. Somente candidatos efetivamente retornados pela busca podem ser escolhidos; sem oferta disponível, o botão fica desabilitado.

A escolha vale para esse produto, descrição e fonte na sessão do navegador e pode ser refeita. Não altera EAN, descrição ou qualquer dado do Alpha7. O resultado escolhido fica identificado na tabela de preços. A conferência não é uma recomendação de substituição clínica ou terapêutica; o objetivo é identificar a mesma apresentação para comparação comercial.

São armazenados apenas candidatos normalizados no SQLite local, com cache de 15 minutos por fonte e descrição. Não são armazenados HTML bruto, cookies ou tokens. Falhas preservam a data original dos resultados anteriores e a indicação de coleta antiga.

## Fontes de pesquisa externas

Os exemplos de [20 Bi na Drogasil](https://www.drogasil.com.br/20-bi-antidiarreico-30-capsulas.html) e de Simeticona Medley motivam a expansão das descrições. A coleta automática de preços continua sendo das fontes já integradas: Drogal e Drogaria São Paulo. O painel oferece links para pesquisar a descrição normalizada na Drogasil e Droga Raia pelo navegador; são consultas manuais, sem confirmação de presença dessas lojas no raio e sem importar preços de resultados do Google.

Referência técnica do endpoint textual: [VTEX Legacy Search API](https://developers.vtex.com/docs/api-reference/search-api), `GET /api/catalog_system/pub/products/search/{search}`. Não são usados endpoints privados ou credenciais da loja.

Teste real em 08/11/2026: a pesquisa encontrou as apresentações de 20 Bi 30 cápsulas e Simeticona Medley 40 mg 20 comprimidos com oferta no catálogo Drogal. Na Drogaria São Paulo, encontrou Fralda Adulto Cotidian Clássica G com 7 unidades, sem oferta disponível naquele teste. Produtos encontrados não significam automaticamente estoque ou preço disponível na filial física.
