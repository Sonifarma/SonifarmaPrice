# Comparação da Raia e atualização — V1.7.1

A captura com três barras iguais em R$ 21,49 mostra somente uma oferta naquele grupo/condição. Não identifica, sozinha, por que o servidor não apresentou a Raia: pode haver fonte ausente no raio, falha, ausência na coleta, cache ou grupo diferente. A consulta de desenvolvimento confirmou novamente R$ 14,99 para o EAN 7896230304536 em 08/11/2026; isso não prova o resultado obtido pelo servidor do usuário.

## Correções

1. **Atualizar preços online** agora envia `atualizar=true` e ignora caches de EAN, descrição, composição e páginas da Todo Dia. Consultas automáticas ainda usam cache de 15 minutos. Falhas preservam os dados anteriores e a data original com aviso; não inventam uma coleta nova.
2. Preços públicos de uma unidade são agrupados pela mesma condição de comparação, mesmo quando os textos explicativos dos catálogos diferem. Pix, condições desconhecidas, observações importadas e coletas anteriores continuam separados. As condições completas permanecem nos balões de cada oferta.
3. Redes sem loja identificada no cadastro do raio aparecem em balões **Rede — não consultada**, com orientação para conferir cadastro, nome, centro e raio. Não são coletados preços fora do raio para preencher o gráfico.

No mesmo grupo e com duas ofertas públicas atuais, R$ 14,99 e R$ 21,49, o resultado é menor R$ 14,99, média R$ 18,24 e maior R$ 21,49. Esses valores são cenário de teste, não preços fixados. Grupo pendente ou diferente continua separado conforme o cadastro.

## Conferir no servidor

Após atualizar e reiniciar, recarregue com Ctrl+F5 e clique em **Atualizar preços online** na ficha. A tabela de fontes contém os EANs, valores e datas realmente retornados. O balão Droga Raia informa falha ou ausência de oferta; Droga Raia — não consultada indica que a rede não foi identificada no cadastro do raio. O preço encontrado fora da instalação não é adicionado como se fosse uma coleta do servidor.

Testes verificam atualização de cache vazio ainda recente, preservação da coleta após falha, nova leitura de página Todo Dia, explicação de rede não consultada e gráfico com preços públicos de duas redes e textos de condição diferentes.
