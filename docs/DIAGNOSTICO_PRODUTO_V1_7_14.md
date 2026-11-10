# Produto ausente na consulta

O diagnostico precisa ser executado no computador que tem a conexao existente ao Alpha7. Ele nao altera cadastro, notas, estoque nem preco. Nao confirma a causa apenas pelo EAN: consulta o cadastro e as regras reais no servidor.

```powershell
cd C:\SonifarmaPrice
.\.venv\Scripts\python.exe -m app.diagnostico_produto 7891000071625 --descricao "LEITE NAN COMFORT 1 800G"
```

A saida mostra o nome cadastrado, a correspondencia com o texto digitado, a ultima compra reconhecida pelo mesmo SQL da tela e ate 100 itens de notas recentes do produto, inclusive embalagens vinculadas ao mesmo produto e outras unidades. Os motivos de exclusao incluem unidade, status, movimento, fornecedor ausente (somente indicador booleano), data de entrada, quantidade, bonificacao, movimentacao e CFOP. Notas rejeitadas pela regra continuam excluidas da consulta normal.

Nao exporta nomes/CNPJs de fornecedores, clientes, chaves de nota, senhas ou dados de conexao. Os CSVs anteriores sao amostras e nao substituem a consulta da nota atual no servidor. Fonte alternativa configurada usa sua propria consulta de ultima compra; o detalhamento de notas so ocorre com a fonte notafiscal.
