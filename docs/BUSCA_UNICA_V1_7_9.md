# Busca única automática — V1.7.9

O filtro Produto, EAN ou código reúne a pesquisa por descrição, apresentação, código Alpha7 e código de barras. A busca encontra o texto em qualquer parte desses campos, preservando zeros à esquerda. O seletor “Pesquisar por” foi removido e o campo ocupa toda a largura.

Ao digitar, a lista é consultada automaticamente após uma pausa de 350 ms. Enter e Consultar produtos aplicam a consulta imediatamente e cancelam o agendamento pendente. Limpar o texto recarrega a lista mantendo os outros filtros; Limpar filtros continua restaurando os padrões do formulário.

Uma nova digitação interrompe a requisição anterior e impede que uma resposta antiga substitua a consulta mais recente. A rolagem incremental fica suspensa enquanto o filtro está pendente e a nova lista começa no primeiro lote. Os demais filtros continuam disponíveis e são respeitados na busca automática.

Validação: 120 testes Python; testes de navegador da consulta completa, dos balões e da busca automática passaram. A busca específica verifica descrição parcial, EAN, código Alpha7, agrupamento da digitação rápida, Enter sem requisição duplicada, troca de consultas com resposta atrasada, limpeza do campo, composição de texto e celular. Os testes usam modo demo e dados fictícios.
