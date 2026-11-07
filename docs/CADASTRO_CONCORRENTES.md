# Cadastro de concorrentes por raio — V1.1.6

Em Pesquisa de mercado, use o centro confirmado e informe o raio (0,5 a 50 km). “Buscar lojas e sites no raio” consulta o OpenStreetMap/Overpass e cadastra automaticamente os resultados no SQLite local. A aba Concorrentes consulta esse cadastro persistente dentro do raio atual, com pesquisa por nome, endereço ou CNPJ e paginação. Repetir a busca atualiza o mesmo identificador OSM. Classificações confirmadas pelo operador são preservadas. Pontos diferentes não são fundidos por nome ou CNPJ.

Se a fonte declarar um CNPJ válido, até três cadastros por busca são enriquecidos em segundo plano pela BrasilAPI, com intervalo mínimo de um segundo e cache de 30 dias. CNPJs ausentes podem ser informados na aba Concorrentes. Confira o CNPJ da filial: o endereço fiscal nunca desloca o ponto geográfico automaticamente. A identidade não é inferida por semelhança do nome. Dados anteriores são preservados se a consulta falhar. Não se armazenam QSA, CPF ou dados de consumidores.

A disponibilidade e a cobertura dessas fontes não são garantidas. Novos resultados exigem uma busca pelo operador; não há varredura contínua. Uma loja pode mudar de identificador OSM ou aparecer como ponto e área; esses casos podem exigir revisão. O cadastro não comprova funcionamento, estoque, preço ou vínculo do site com uma filial. A classificação comercial rede/independente exige confirmação.

## Fontes e limites

- [Metadados oficiais dos dados abertos CNPJ](https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf): endereço, CNAE e situação cadastral; não há preço de produtos ou coordenadas para consulta por raio.
- [BrasilAPI](https://brasilapi.com.br/docs): intermediário comunitário, não API oficial da Receita; consulta por CNPJ identificado. Disponibilidade de CNPJ alfanumérico depende do provedor.
- [OpenStreetMap](https://www.openstreetmap.org/copyright): origem geográfica e sites declarados, atribuição ODbL. Cobertura incompleta.
- [CADESP SP](https://portal.fazenda.sp.gov.br/servicos/cadesp): consulta cadastral estadual; não conectado por automação nesta versão.
- [SAE NFC-e SP](https://portal.fazenda.sp.gov.br/servicos/nfce/Paginas/sae-nfce.aspx): consulta/listagem fiscal do contribuinte com autenticação própria; não oferece listagem pública dos cupons de concorrentes por raio.

## Preços e alternativas

O cadastro geográfico habilita localizar os sites dos concorrentes. Preços continuam provenientes das observações CSV importadas. Próxima integração possível: coletores específicos de páginas públicas ou catálogos autorizados, respeitando acesso e condições comerciais por filial (CEP, clube, entrega, retirada), com EAN, data e URL de origem. Um preço nacional do site não comprova oferta na loja próxima. Não foi ativada coleta genérica de sites nem acesso a documentos fiscais de terceiros.

Se a cobertura OSM for insuficiente, uma base licenciada de estabelecimentos ou Google Places pode complementar a descoberta. [Places Nearby Search](https://developers.google.com/maps/documentation/places/web-service/nearby-search) exige chave, faturamento e observância de regras de armazenamento e exibição; não foi contratado ou ativado automaticamente. Outra alternativa é importar uma lista de lojas/CNPJs identificados e verificar endereços antes de geocodificar. Não há API pública geral da Receita/Fazenda que resolva conjuntamente concorrentes por raio e seus preços.
