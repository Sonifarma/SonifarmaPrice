# Comparação por composição — V1.5.0

Na ficha do produto e na pesquisa de mercado, abaixo do gráfico do EAN, aparece **Mesma composição — todos os laboratórios**. A busca não usa fabricante como filtro. Cada grupo e condição comercial apresenta menor preço, média aritmética de todas as ofertas e maior preço.

Passar o mouse, focar por teclado ou clicar na barra mostra produto, marca/laboratório informado pelo catálogo, rede, EAN, preço, data da coleta e link. Empates exibem todos os produtos. A média lista todas as ofertas usadas, sem atribuir o valor médio a um produto fictício. Uma oferta por rede/EAN, sem multiplicar por filiais. O raio seleciona as redes do cadastro; não confirma preço da filial.

A referência vem dos metadados do EAN exato; referências contraditórias interrompem a comparação. Também reconhece nomes explícitos de princípios ativos simples, como SIMETICONA, nas descrições abreviadas. Não deduz composição de marcas como 20 BI ou Luftal. Quando o catálogo informa o princípio ativo, marcas comerciais podem ser comparadas. Campo `brand` é marca/laboratório declarado pelo catálogo, não comprovação do fabricante legal.

Concentração, forma, quantidade, volume e modificadores de apresentação precisam concordar. Campos incompletos, associações e múltiplas concentrações ficam fora desta primeira versão. Associações precisam de mapeamento estruturado de componente → dose antes de serem suportadas; ordenar os números de doses não comprova a mesma fórmula. A comparação é comercial e não indica intercambialidade terapêutica.

O cache por fonte/composição dura 15 minutos. Em falhas, mantém preços anteriores com data original e identificação de coleta anterior, separados de dados atuais. Não grava preços ou produtos no Alpha7 nem mistura esses preços com observações importadas.

## Drogaria Todo Dia

Em 08/11/2026, as requisições diretas deste ambiente para a página inicial, robots.txt, produto público e caminho de catálogo responderam HTTP 403; uma requisição HEAD também retornou 405/manutenção. Isso pode coexistir com o funcionamento do site no navegador do usuário. O site usa uma estrutura diferente das APIs públicas já integradas; não foi habilitado como se fosse VTEX.

A fonte segue com link manual e sem preços coletados. A mensagem agora distingue acesso no navegador de disponibilidade da integração, identifica a data da verificação e não sugere que preços foram obtidos. Não usa valores de snippets indexados como preços atuais. A integração automática precisa de um acesso público permitido ou API disponibilizada pela loja.

## Validação

Testes cobrem laboratórios diferentes, dosagens/apresentações incompatíveis, associações, metadados contraditórios, cache e falhas, escopo por rede e duplicação. O teste de navegador verifica mínimo/média/máximo e interação por mouse, clique e teclado. Consulta pública real em 08/11/2026 encontrou uma oferta compatível de Simeticona 40mg/20 comprimidos na Drogal; a Drogaria São Paulo não retornou oferta compatível nessa consulta. A disponibilidade varia por coleta.
