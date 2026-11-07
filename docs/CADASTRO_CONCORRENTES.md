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

## Filiais identificadas — V1.1.7, pesquisa de 07/11/2026

Ao abrir Concorrentes após atualizar, o Price complementa automaticamente os registros abaixo, já existentes no cadastro local. Não é necessário digitar esses CNPJs ou executar um script adicional. A operação também se aplica às próximas buscas dessas mesmas lojas. Nome e endereço completo, ou um identificador OSM previamente conferido quando o número está ausente, precisam corresponder na região pesquisada. Não são criadas lojas fora do cadastro ou alteradas coordenadas, classificações ou CNPJs existentes. A aplicação fica registrada em auditoria e não repete a gravação em cada acesso.

Os dados cadastrais foram consultados individualmente na BrasilAPI e o endereço de cada resultado foi conferido com a filial pesquisada. A resposta armazenada contém somente os campos cadastrais permitidos pelo coletor. A tela mostra endereço fiscal, data da consulta e link para a fonte. O cadastro pode ser consultado mesmo se o serviço estiver indisponível; a atualização posterior continua sujeita ao cache de 30 dias.

| Loja | Endereço da filial | CNPJ / fonte cadastral consultada |
|---|---|---|
| Drogal | Rua Iacanga, 786 — Americana | [54.375.647/0084-54](https://brasilapi.com.br/api/cnpj/v1/54375647008454) |
| Dia | Rua Iacanga, 803 — Americana | [03.476.811/0292-14](https://brasilapi.com.br/api/cnpj/v1/03476811029214) |
| Danny Cosméticos — Tivoli | Rua do Ósmio, 699, EUC F — Santa Bárbara d’Oeste | [50.028.976/0017-08](https://brasilapi.com.br/api/cnpj/v1/50028976001708) |
| Higa | Rua da Agricultura, 622 — Santa Bárbara d’Oeste | [46.029.724/0004-01](https://brasilapi.com.br/api/cnpj/v1/46029724000401) |
| Assaí | Rua da Agricultura, 1258 — Santa Bárbara d’Oeste | [06.057.223/0462-44](https://brasilapi.com.br/api/cnpj/v1/06057223046244) |
| Todo Dia | Rua da Agricultura, 1580, sala 2 — Santa Bárbara d’Oeste | [12.834.185/0029-10](https://brasilapi.com.br/api/cnpj/v1/12834185002910) |
| Tenda | Rua do Ósmio, 915 — Santa Bárbara d’Oeste | [01.157.555/0027-43](https://brasilapi.com.br/api/cnpj/v1/01157555002743) |
| Pavan | Avenida do Comércio, 351 — Santa Bárbara d’Oeste | [44.609.956/0001-60](https://brasilapi.com.br/api/cnpj/v1/44609956000160) |
| São Vicente | Rua Limeira, 700 — Santa Bárbara d’Oeste | [43.259.548/0004-06](https://brasilapi.com.br/api/cnpj/v1/43259548000406) |
| Drogal | Rua Limeira, 944, sala 3 — Santa Bárbara d’Oeste | [54.375.647/0455-70](https://brasilapi.com.br/api/cnpj/v1/54375647045570) |
| Drogal | Avenida da Amizade, 186 — Santa Bárbara d’Oeste no cadastro fiscal | [54.375.647/0123-03](https://brasilapi.com.br/api/cnpj/v1/54375647012303) |

Foram mantidos pendentes os quatro registros enviados sem identificação suficiente: Mercadona; Drogaria São Paulo; Droga Raia; Todo Dia da Avenida Brasil. Na Avenida Brasil há mais de uma filial Todo Dia identificada no cadastro público; não foi escolhido um CNPJ somente pelo nome da rede. Para concluir esses casos, conferir o número da fachada ou um documento da loja e o ponto no mapa. A pendência cadastral não impede a pesquisa de mercado por produto nem a importação de observações.

Exemplos de conferência: [Assaí — endereço oficial](https://www.assai.com.br/loja/assai-santa-barbara-do-oeste), [Tenda — endereços das ofertas](https://www.tendaatacado.com.br/institucional/nossas-ofertas), [São Vicente — lojas](https://www.svicente.com.br/lojas/), [Pavan — rede publicada pela Prefeitura de Tietê](https://www.tiete.sp.gov.br/public/admin/globalarq/uploads/files/rede_credenciada_mes_pdf_202601121768220972.pdf). O CNPJ da matriz publicado no rodapé de um site de rede não deve substituir o CNPJ da filial.

## Cadastro compartilhado e edição de grupos — V1.1.8

Pesquisa de mercado → Lojas e sites dentro do raio e a aba Concorrentes consultam o mesmo cadastro local, com o mesmo centro e raio. A primeira tela carrega os registros salvos ao abrir, sem exigir nova consulta ao OpenStreetMap. Ambas paginam até 100 lojas por página; o filtro textual da aba Concorrentes restringe essa exibição.

O botão Buscar lojas e sites no raio passa a complementar o cadastro. Enquanto a busca está em andamento, os registros salvos permanecem visíveis. Em caso de indisponibilidade, o sistema informa que não houve atualização online e mantém a lista salva no raio atual. Uma busca posterior que retorne menos lojas não exclui automaticamente as anteriores. As advertências de cobertura, atualização e disponibilidade de ofertas continuam válidas.

O grupo pode ser preenchido diretamente em qualquer uma das telas: selecione uma das quatro categorias, informe o motivo e pressione Confirmar grupo. A alteração é persistida no cadastro e na regra de classificação das futuras buscas em uma única transação, com auditoria. As duas telas mostram o grupo salvo, inclusive com a fonte online indisponível. Identificadores inexistentes não criam classificações avulsas.

Validação: testes de falha da fonte com cadastro existente; equivalência entre o resultado da busca e o cadastro persistente; atualização de grupo sem rede e preservação em nova consulta; navegador com edição pela aba Concorrentes e busca online indisponível mantendo as lojas e o grupo confirmado.
