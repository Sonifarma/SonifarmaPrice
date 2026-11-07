# Padrao visual Sonifarma — aplicado ao Price

Fonte: tema vigente do SonifarmaCRM, consultado em 07/11/2026. As telas Proffer fornecidas pelo usuario serviram como referencia de organizacao de consulta e grafico; nao houve copia de codigo nem integracao com o servico Proffer.

- Turquesa de marca #00a6ad; botoes principais #00777d para leitura com texto branco.
- Laranja #ff6900 em detalhes de identidade; fundo #f3f9f9; texto #203a3d.
- Logo local, fonte Segoe UI/Arial, cards brancos, bordas leves e estados de foco visiveis.
- Navegacao lateral em desktop e horizontal em telas pequenas.
- Filtros com rotulos, periodo recolhido, datas inicial/final e validacao de intervalo.
- Consultar como acao principal; Limpar com contorno laranja; exportacao com escopo explicito.
- Tabelas compactas com cabecalho fixo, numeros alinhados a direita e paginacao.
- Datas DD/MM/AAAA; valores em reais; badges com texto e motivo, sem depender so de cor.
- Mensagens distintas para carregamento, nenhum resultado, falha e fonte nao configurada.

O CSS em `static/sonifarma-theme.css` concentra os tokens e componentes. O JavaScript continua especifico do Price para nao misturar regras do CRM ou de outros sistemas. A aplicacao nos demais projetos ficou para outra etapa, conforme escolha do usuario.
