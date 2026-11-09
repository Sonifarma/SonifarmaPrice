# Sites de concorrentes — V1.7.11

O cadastro compartilhado de concorrentes complementa sites ausentes nas redes informadas pelo operador:

- Tenda Atacado: https://www.tendaatacado.com.br/
- Drogal: https://www.drogal.com.br/
- Higa: https://www.higa.com.br/

A complementação é aplicada na leitura das lojas salvas e funciona tanto na aba Concorrentes quanto em Lojas e sites dentro do raio, sem exigir nova consulta ao OpenStreetMap. A associação é mantida no código e não substitui o campo site já preenchido no banco. Nomes são normalizados por acentos e caixa, usando uma lista explícita de nomes das redes; nomes parecidos não recebem o link automaticamente.

O link complementar é identificado como Site da rede e carrega origem informado_pelo_operador. Não cria novas lojas, não altera coordenadas, grupos ou CNPJ e continua respeitando o raio. O domínio da rede não confirma preço ou estoque da filial. Tenda e Higa continuam sem adaptador de coleta automática de preços; Drogal usa o adaptador existente.

Validação: 123 testes Python; teste de layout de concorrentes no navegador, incluindo link de rede e tamanhos de tela. Cobertura adicional de site vazio, variações de nome, preservação de site preenchido, prevenção de associação por nome parecido e leitura repetida do cadastro com filtro geográfico.
