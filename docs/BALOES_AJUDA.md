# Balões de ajuda — V1.7.0

Textos explicativos, avisos, mensagens de consulta e condições extensas agora ficam em balões abertos por clique. O padrão vale para produtos, pesquisa de mercado, concorrentes, importação, centro da pesquisa, integração Alpha7 e ficha do produto, incluindo conteúdo carregado depois da abertura da página.

- **? Ajuda / Status:** informação em azul.
- **! Atenção:** aviso em amarelo. Fontes podem mostrar o nome da rede com esse ícone quando houver coleta anterior ou ausência de oferta.
- **! Erro:** falha em vermelho, persistente até o estado ser atualizado. O detalhe é lido ao clicar, e erros são anunciados para leitores de tela.
- **Condições / Pix:** condições de uma oferta dentro da célula da tabela. Pix continua identificado no botão, sem apresentar preço condicionado como oferta comum.

Clique novamente, no ×, fora do balão ou pressione Esc para fechar. Esc retorna o foco ao botão e não fecha a ficha do produto quando um balão está aberto dentro dela. O balão é reposicionado para caber no celular e dentro da ficha. Links de fontes continuam acessíveis no conteúdo aberto.

Preços, gráficos, campos, dados dos produtos, resultados e ações permanecem visíveis. As mensagens completas continuam no DOM como conteúdo original, recolhido somente depois de o JavaScript criar o botão. Os balões clonam esse conteúdo sem executar HTML vindo das mensagens. Mensagens atualizadas também atualizam um balão já aberto; mensagens vazias removem o botão.

O componente compartilhado está em `static/help.js`. Novas orientações podem ser marcadas com `data-help-label` e `data-help-kind="info|warning|error"`; avisos existentes com notice/warning/error e mensagens cadastradas usam o mesmo padrão. `data-help-keep="true"` preserva dados que precisam continuar visíveis. Campos e botões de ação não são convertidos em ajuda.

Verificação: testes de navegador para todas as telas, abertura por clique, fechamento, foco, ficha modal, texto de erro seguro, atualizações dinâmicas, células da tabela e celular; fluxo completo de consultas, filtros, exportação e gráficos. Nenhuma alteração em consultas ou dados do ERP.
