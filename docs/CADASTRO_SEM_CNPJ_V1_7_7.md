# Inclusão de loja sem CNPJ — V1.7.7

Na aba Concorrentes, o formulário “Adicionar concorrente por nome e endereço” fica aberto. Informe nome, endereço completo e grupo. O CNPJ é opcional; a consulta cadastral não é necessária para adicionar a loja. Não há preenchimento prévio com dados de outra filial.

Clique em “Localizar para adicionar loja”, confira o ponto no mapa e use “Adicionar concorrente nesta localização”. A inclusão continua respeitando o raio. Sem CNPJ, a loja recebe status “Sem CNPJ” e fonte “Cadastro manual”; o CNPJ pode ser informado depois no cadastro existente. CNPJ informado inválido continua recusado. Nome e endereço equivalentes são verificados para impedir inclusão repetida.

Exemplo: Drogaria Vide Bula, Rua Iacanga, 356, Americana - SP. Complete e confira o endereço antes de salvar.

Validação: 116 testes Python e testes de navegador da consulta e do cadastro manual sem CNPJ (incluindo grupo e celular).
