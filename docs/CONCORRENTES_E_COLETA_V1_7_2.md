# Concorrentes e coleta — V1.7.2

## Cadastro no padrão visual do Price

A tela organiza loja/endereço/distância, grupo, sites/fontes e CNPJ em colunas com largura contida. Campos de grupo e CNPJ são compactos; razão social, situação cadastral, CNAE, endereço fiscal e fonte ficam no balão Dados cadastrais. Status consultado, pendente e falha aparecem como etiquetas. O motivo de classificação continua opcional, recolhido em Motivo opcional. Salvar grupo e Consultar CNPJ mantêm os mesmos fluxos do cadastro compartilhado.

Cabeçalho e paginação mostram quantidade e intervalo dos resultados. Até 1200px, cada linha passa a um cartão com campos distribuídos; no celular os campos ficam em uma coluna. Nenhuma rolagem horizontal é necessária para esse cadastro. As demais tabelas não receberam uma alteração global de largura.

## Raia: falha no acesso direto

A captura do servidor confirmou que a rede era reconhecida, mas a busca falhava. A mensagem da descrição sobrescrevia a mensagem da consulta por EAN. A atualização preserva ambos os estágios e inclui um código de erro seguro, sem imprimir credenciais.

Quando o acesso HTTP direto falha ou o formato não pode ser lido, a Raia tenta navegação pública em Chromium, com o mesmo parser de EAN, estoque, vendedor e preço. O navegador lê robots.txt, usa apenas o host e os caminhos públicos permitidos, sem login ou checkout. Se não houver oferta válida em uma consulta direta concluída, não inventa preço nem usa um produto de EAN diferente.

É necessário instalar o Chromium na mesma conta que inicia o Price:

```powershell
cd C:\SonifarmaPrice
.\.venv\Scripts\python.exe -m playwright install chromium
```

O nome Raia passa a reconhecer também Drogaria Raia, DrogaRaia, nomes de filial e o site oficial declarado no cadastro. A raiz de CNPJ compartilhada com a Drogasil continua insuficiente por si só. Nome Drogasil conflitante não é convertido em Raia.

## Todo Dia: C/10 AMP

Foi reproduzida uma falha de descoberta: `SORO FISIOLOGICO C/10 AMP 5ML` gerava chaves literais `C/10` e `AMP` e não localizava a página `SORO FISIOLOGICO ADV 10 AMPOLAS C/ 5ML` no índice. A normalização agora expande ampolas/flaconetes, trata C/10 como quantidade, remove esse marcador das palavras de busca e confere o volume. `C/5ML` não vira cinco unidades. Embalagem de uma ampola e volume de 10ml não são aceitos como correspondência de 10 ampolas de 5ml.

Consulta real por EAN 7896230304536 em 08/11/2026 retornou R$ 12,98 na Todo Dia. A alternativa pelo navegador da Raia retornou R$ 14,99 no mesmo EAN. Valores registram o teste e não estão fixados no código nem garantem disponibilidade futura no servidor do usuário. Após atualizar, usar Atualizar preços online para não reutilizar um cache vazio anterior.

## Diagnóstico no servidor

Se ainda faltar preço após atualizar e instalar o navegador:

```powershell
cd C:\SonifarmaPrice
.\.venv\Scripts\python.exe -m app.diagnostico_precos --ean 7896230304536 --raio 2
```

Use o mesmo raio da tela. Para outro produto, informe também `--descricao "descricao do produto"`. O diagnóstico mostra versão, seleção de lojas Raia/Todo Dia no cadastro do raio e resultado técnico do catálogo. Esses testes públicos são independentes da seleção geográfica e não inserem preço no gráfico como se fosse da filial. Não consulta nem grava no ERP e não imprime senhas; códigos de erro distinguem HTTP, TLS, tempo esgotado e navegador não instalado.

## Validação

Testes cobrem normalização de quantidade/volume, alternativa por navegador, preservação dos erros de EAN/descrição, reconhecimento da rede, diagnóstico sem acesso ao ERP, consultas de CNPJ/grupo e layouts em 1500, 1200, 1024, 768 e 390px. Evidência real de preços foi obtida das páginas públicas; fixtures de cadastro e capturas visuais usam empresas fictícias.
