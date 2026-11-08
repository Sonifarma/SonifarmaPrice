# Tela inicial — V1.4.0

## Rolagem e filtros

A lista carrega lotes de 100 produtos ao rolar até o fim da área da tabela e acumula os itens já exibidos. Carregar mais serve como alternativa por teclado e para repetir uma carga que falhou. Uma falha na continuação preserva os registros anteriores; alterar um filtro interrompe a continuação até uma nova consulta. Resultados e contadores são filtrados no servidor antes do limite e do deslocamento. Identificadores de embalagem repetidos não são duplicados na tela. A exportação usa todos os itens já carregados.

Padrões da tela:

- Tipo de preço: **Liberado**. Opções Liberado, Monitorado e Todos. O Alpha7 usa `produto.tipopreco`, códigos L/M, presentes nas amostras fornecidas.
- Status: **Ativo**. Opções Ativo, Inativo e Todos. Usa `produto.status`, códigos A/I.
- Última compra: **últimos 45 dias**, incluindo hoje e os 44 dias anteriores. Datas inicial e final são editáveis no calendário; editar uma delas seleciona Intervalo personalizado.

Intervalos incluídos: Hoje, Ontem, Até hoje, Semana atual, Semana passada, Mês atual, Início do mês até hoje, Mês passado, Últimos 7/15/30/45 dias, Últimos 3/6/12 meses, Todos os períodos e Intervalo personalizado. Semana começa na segunda-feira; Semana atual e Mês atual usam o intervalo completo; Início do mês até hoje termina hoje. Meses anteriores usam meses de calendário, ajustando o dia para o fim do mês quando necessário. Datas finais são inclusivas, implementadas no SQL com limite exclusivo do dia seguinte. O relógio de referência é America/Sao_Paulo.

A API mantém `periodo=todos` e `data_filtro=entrada` para compatibilidade com consumidores antigos; a tela nova envia `periodo=45`, `data_filtro=compra`, `tipo_preco=liberado` e `status_produto=ativo`. Os filtros de margem/revisão e estoque continuam disponíveis.

## Última compra precisa de fonte confirmada

Os CSVs de notas fiscais enviados identificam a fonte `notafiscal.datahoraentrada`, com vínculo `itemnotafiscal.notafiscalid -> notafiscal.id` e `itemnotafiscal.embalagemid -> embalagem.id -> embalagem.produtoid`. A consulta fiscal calcula MAX por produto, em todas as suas embalagens, na unidade configurada. Usa fornecedor identificado, quantidade positiva, sem bonificação e com movimentação do item. Status da nota, movimento físico e CFOPs de compra precisam ser confirmados no Alpha7 antes da ativação. Os códigos I/C/R encontrados na amostra não foram interpretados por suposição.

As amostras de 10 notas e 10 itens não possuem IDs de nota em comum, portanto não comprovam o vínculo de uma compra real nem a semântica dos status. O histórico de custo pode auxiliar na conferência dos vínculos, mas sua data não substitui a entrada da nota. Os CSVs fiscais não são incluídos no repositório. O ambiente de desenvolvimento não conseguiu conexão com o banco de produção para validar seus metadados.

Por isso, a implementação não transforma A7_ENTRY em A7_PURCHASE automaticamente. Sem a fonte confirmada, o filtro de compra é explicitamente bloqueado e a tela oferece **Consultar sem filtro de última compra**, que seleciona Todos os períodos. Isso permite usar os demais filtros e a rolagem enquanto o mapeamento é concluído, sem apresentar uma lista sem filtro como se fossem os últimos 45 dias.

No PowerShell do servidor, após atualizar:

```powershell
cd C:\SonifarmaPrice
.\.venv\Scripts\python.exe -m app.diagnostico_compras
```

O arquivo `data\diagnostico_compras_*.json` contém somente nomes e tipos de colunas, sem valores de produtos, dados pessoais ou senhas. Não altera o banco. A estrutura permite identificar uma fonte de compras/recebimentos finalizados, sua unidade e o vínculo com produto ou embalagem. Depois de confirmar a semântica, configurar no `.env` existente:

```dotenv
A7_PURCHASE_CONFIRMED=1
A7_PURCHASE_SCHEMA=esquema_confirmado
A7_PURCHASE_TABLE=tabela_confirmada
A7_PURCHASE_ID_KIND=produto
A7_PURCHASE_ID_COLUMN=coluna_confirmada
A7_PURCHASE_UNIT_COLUMN=coluna_confirmada
A7_PURCHASE_DATE_COLUMN=coluna_confirmada
A7_PURCHASE_STATUS_COLUMN=coluna_confirmada
A7_PURCHASE_STATUS_VALUE=status_finalizado_confirmado
```

Os nomes acima são marcadores, não um mapeamento real. A consulta valida nomes, tipos de data e existência das colunas, usa MAX para a última compra na unidade configurada e considera somente o status finalizado confirmado. O preenchimento do `.env` de produção depende da estrutura e semântica do Alpha7 no servidor.

## Fonte fiscal preparada a partir dos CSVs

Depois de confirmar os códigos de notas válidas, movimento que adiciona estoque e CFOPs que representam compras, a integração pronta pode ser ativada no `.env`:

```dotenv
A7_PURCHASE_SOURCE=notafiscal
A7_PURCHASE_CONFIRMED=1
A7_PURCHASE_SCHEMA=public
A7_PURCHASE_STATUS_VALUE=codigo_confirmado
A7_PURCHASE_MOVEMENT_VALUE=codigo_confirmado
A7_PURCHASE_CFOPS=lista_confirmada_separada_por_virgulas
```

Os valores `codigo_confirmado` e `lista_confirmada_separada_por_virgulas` são marcadores e não devem ser copiados literalmente. Não é necessário configurar TABLE/ID_COLUMN/DATE_COLUMN nesta modalidade. O sistema valida as colunas e tipos no servidor antes de executar a consulta. Não usa emissão ou histórico de custo como substitutos. CFOP não é inferido só pelo primeiro dígito: o item importado pode conservar o CFOP de saída do emitente. A lista confirmada deve excluir devoluções, transferências, bonificações e notas que apenas referenciam cupons. Os testes usam códigos de status/movimento fictícios para não transformar uma hipótese sobre o Alpha7 em regra de produção.
