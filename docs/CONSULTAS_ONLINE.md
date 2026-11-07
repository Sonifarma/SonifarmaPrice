# Consultas online de preços — V1.2.0

Na Pesquisa de mercado, selecione o produto pela descrição ou informe seu EAN completo. Confira o centro e o raio; as lojas precisam estar no cadastro de concorrentes. Clique em **Consultar sites online**. Os resultados aparecem no painel Preços online dos sites das redes.

## Fontes integradas

- Drogal: catálogo público em `https://www.drogal.com.br/api/catalog_system/pub/products/search`, filtro exato `alternateIds_Ean`.
- Drogaria São Paulo: catálogo público em `https://www.drogariasaopaulo.com.br/api/catalog_system/pub/products/search`, mesmo filtro.

A consulta considera somente redes integradas com lojas cadastradas no raio atual. A associação da rede usa o nome cadastrado exato ou a raiz do CNPJ; não confirma identidade da filial nem suas condições comerciais. Lojas ainda sem coletor aparecem explicitamente como sem integração. O CNPJ não é obrigatório para pesquisar o catálogo de uma rede identificada pelo nome no cadastro.

Cada fonte é consultada uma vez por EAN, sem multiplicar o preço pelo número de filiais. Exige EAN idêntico no SKU retornado, vendedor próprio identificado, disponibilidade positiva do catálogo, preço numérico positivo em reais e link HTTPS na fonte cadastrada. Vendedores de marketplace são excluídos. O título da apresentação fica visível para conferência. Promoções condicionadas presentes na resposta são sinalizadas; nenhum desconto adicional é calculado.

O preço exibido é do site da rede. **Não confirma preço ou estoque da loja física dentro do raio**, atendimento ao CEP, frete, clube, convênio, receita ou benefício pessoal. Não houve simulação de compra, checkout ou alteração de sessão para forçar um preço local. Preços online permanecem em painel separado e nunca são inseridos como observações geográficas da filial ou usados no gráfico de preços locais.

## Operação e disponibilidade

Consulta sob demanda, pelo botão, sem varredura contínua e sem envio de custo, margem, estoque ou dados de clientes do Alpha7. Não exige chave ou contratação paga nas fontes atualmente integradas. Acesso somente a hosts e caminhos de catálogo conhecidos, com robots.txt verificado, intervalo mínimo de um segundo entre requisições a cada host e apenas uma coleta simultânea por fonte neste processo. Redirecionamentos para outros hosts ou HTTP são rejeitados. Resposta limitada a 2 MB e timeout de 12 segundos por requisição. Restrições, bloqueios e indisponibilidade não são contornados.

O resultado normalizado é salvo no SQLite local, por fonte e EAN, com cache de 15 minutos e data da coleta. Ao falhar uma atualização, o estado da fonte e a data antiga são preservados e apresentados como coleta anterior. Uma fonte pode falhar sem ocultar o resultado da outra. Ausência de oferta é diferente de falha da consulta. Não se armazenam respostas brutas, tokens de preço, cookies ou informações de usuários.

No teste real de 07/11/2026 às 14h32 (Brasília), os dois coletores retornaram o EAN 7891058002916, Dorflex 10 comprimidos: R$ 7,29 no catálogo Drogal e R$ 7,49 no catálogo Drogaria São Paulo. Esses valores registram apenas aquele teste e podem mudar; não são dados fixos distribuídos com a aplicação.

Fontes para conferir as ofertas: [Drogal — produto](https://www.drogal.com.br/analgesico-e-relaxante-muscular-dorflex-10-comprimidos/p) e [Drogaria São Paulo — produto](https://www.drogariasaopaulo.com.br/analgesico-dorflex-10-comprimidos/p). As regras podem mudar e novas integrações precisam ser verificadas individualmente.
