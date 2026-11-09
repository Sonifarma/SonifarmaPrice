# Carregamento da interface — V1.7.10

O seletor Pesquisar por permanece removido. A busca ampla por descrição, EAN e código está fixa no JavaScript, com atualização ao digitar.

A resposta da tela inicial agora desabilita o armazenamento em cache do HTML. CSS, ajuda e JavaScript recebem URLs com impressão digital do conteúdo, fazendo o navegador buscar uma versão nova quando o arquivo muda. A resposta também identifica a versão do servidor no cabeçalho X-Price-Version.

Após atualizar, pare a instância anterior e reinicie o servidor. Recarregue os navegadores das máquinas da rede com Ctrl+F5; a versão no rodapé deve ser 1.7.10. Se aparecer o seletor, o navegador está recebendo a interface anterior: confira se o processo reiniciado está usando a pasta atualizada.

Validação: resposta HTTP sem seletor e com no-store, três arquivos versionados retornando HTTP 200, e teste de navegador da busca única (descrição parcial, EAN, código, debounce, Enter, resposta atrasada, limpeza, composição e celular).
