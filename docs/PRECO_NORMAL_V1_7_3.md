# Preço normal sem promoção — V1.7.3

A regra é promoção pública válida quando houver; caso contrário, preço normal. Preço normal também entra no gráfico e aparece identificado na tabela. Não exige promoção para apresentar um produto com preço válido.

- Drogal/São Paulo: preço atual `Price`; se estiver ausente, usa `ListPrice` normal válido.
- Raia: preço atual `valueTo`/`value_to`; se ambos estiverem ausentes, usa `value_from` normal válido. Pix menor permanece identificado como condição específica.
- Todo Dia: preço atual do SKU `RetailPrice`, com `PromotionPrice` válido menor quando houver. Se `RetailPrice` estiver ausente, usa `ListPrice` normal válido.

Não usa preço regular para esconder um erro de acesso, formato inválido, preço explicitamente inválido, EAN divergente ou indisponibilidade do SKU. EAN, vendedor próprio e disponibilidade continuam sendo conferidos. As mensagens distinguem ausência de preço válido de ausência de promoção.

Para o soro EAN 7896230304536, as páginas públicas canônicas da Raia e Todo Dia já verificadas são tentadas diretamente. A identidade da página e o EAN são conferidos novamente e o preço é lido a cada coleta, sem valor fixo no código. Isso reduz dependência da pesquisa e permite ler esse produto da Todo Dia mesmo se não estiver no índice local. Para os outros produtos, a descoberta normal continua disponível. Erros de leitura da Raia e HTTP do navegador agora têm códigos mais específicos em vez de apenas ValueError.

Validação real da API do Price em 08/11/2026, em banco local temporário sem índice Todo Dia e sem acesso ao ERP: Drogal R$21,49, Raia R$14,99, Todo Dia R$12,98 para o mesmo EAN, todos identificados como preços normais naquela coleta. Valores podem mudar e não estão fixados no código.

Testes cobrem ausência dos campos promocionais com preço normal válido em todas as fontes, caminho público conhecido, rejeição de EAN diferente, preço normal no gráfico/tabela e preservação das demais validações.
