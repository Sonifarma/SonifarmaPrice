# Tela inicial — V1.4.0

## Rolagem e filtros

A lista carrega lotes de 100 produtos ao rolar até o fim da área da tabela e acumula os itens já exibidos. Carregar mais serve como alternativa por teclado e para repetir uma carga que falhou. Uma falha na continuação preserva os registros anteriores; alterar um filtro interrompe a continuação até uma nova consulta. Resultados e contadores são filtrados no servidor antes do limite e do deslocamento. Identificadores de embalagem repetidos não são duplicados na tela. A exportação usa todos os itens já carregados.

Padrões da tela:

- Tipo de preço: **Liberado**. Opções Liberado, Monitorado e Todos. O Alpha7 usa `produto.tipopreco`, códigos L/M, presentes nas amostras fornecidas.
- Status: **Ativo**. Opções Ativo, Inativo e Todos. Usa `produto.status`, códigos A/I.
- Última compra: **últimos 45 dias**, incluindo hoje e os 44 dias anteriores. Datas inicial e final são editáveis no calendário; editar uma delas seleciona Intervalo personalizado.

Intervalos incluídos: Hoje, Ontem, Até hoje, Semana atual, Semana passada, Mês atual, Início do mês até hoje, Mês passado, Últimos 7/15/30/45 dias, Últimos 3/6/12 meses, Todos os períodos e Intervalo personalizado. Semana começa na segunda-feira; Semana atual e Mês atual usam o intervalo completo; Início do mês até hoje termina hoje. Meses anteriores usam meses de calendário, ajustando o dia para o fim do mês quando necessário. Datas finais são inclusivas, implementadas no SQL com limite exclusivo do dia seguinte. O relógio de referência é America/Sao_Paulo.

A API mantém `periodo=todos` e `data_filtro=entrada` para compatibilidade com consumidores antigos; a tela nova envia `periodo=45`, `data_filtro=compra`, `tipo_preco=liberado` e `status_produto=ativo`. Os filtros de margem/revisão e estoque continuam disponíveis.

## Última compra — fonte fiscal confirmada na V1.4.1

O usuário confirmou que `notafiscal.status=C` significa concluída e `tipomovimentacaofisica=A` adiciona estoque. A fonte padrão agora usa `notafiscal.datahoraentrada`, com vínculo `itemnotafiscal.notafiscalid -> notafiscal.id` e `itemnotafiscal.embalagemid -> embalagem.id -> embalagem.produtoid`. Calcula MAX por produto, em todas as suas embalagens, na unidade configurada, com fornecedor identificado, quantidade positiva, sem bonificação e sem item sem movimentação. O histórico de custo não fornece a data de compra.

CFOPs padrão: 1102,2102,3102,1403,2403 e os de venda do emitente que podem ser conservados no XML importado: 5101,5102,5401,5403,5405,6101,6102,6401,6403,7101,7102. A lista contempla compras usuais de mercadoria para revenda e exclui devoluções, transferências e notas que referenciam cupons (5929). Operações especiais fora dessa lista não participam até configurar `A7_PURCHASE_CFOPS` com uma lista separada por vírgulas.

Instalações sem configuração anterior passam a usar essa fonte automaticamente após atualizar e reiniciar. Não é necessário alterar o `.env`. Fontes planas anteriormente configuradas continuam preservadas. `A7_PURCHASE_CONFIRMED=0` desabilita explicitamente a fonte; se essa opção tiver sido incluída manualmente, mudar para 1 para ativar. As opções abaixo permitem sobrescrever os padrões:

```dotenv
A7_PURCHASE_SOURCE=notafiscal
A7_PURCHASE_CONFIRMED=1
A7_PURCHASE_SCHEMA=public
A7_PURCHASE_STATUS_VALUE=C
A7_PURCHASE_MOVEMENT_VALUE=A
```

A consulta valida existência e tipos de colunas no servidor antes da leitura. A conexão com o Alpha7 de produção não estava disponível neste ambiente; a validação executada usa SQL em PostgreSQL simulado com os códigos C/A confirmados e fixtures fictícias. Os CSVs fiscais não foram adicionados ao repositório.

Para diagnosticar somente nomes e tipos de colunas, sem valores fiscais nem senhas:

```powershell
cd C:\SonifarmaPrice
.\.venv\Scripts\python.exe -m app.diagnostico_compras
```

O arquivo fica em `data\diagnostico_compras_*.json`. Quando a fonte estiver desativada, a tela oferece uma ação explícita para consultar sem filtro de compra; não apresenta resultados sem datas como se fossem os últimos 45 dias.

V1.7.15: inclui o CFOP 5405 conservado no XML do fornecedor. A ultima compra usa datahoraentrada: nota emitida em 06/11 e recebida em 09/11 aparece como 09/11. Configuracoes explicitas de A7_PURCHASE_CFOPS continuam preservadas.
