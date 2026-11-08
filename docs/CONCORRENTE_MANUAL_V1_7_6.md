# Cadastro por CNPJ e endereço — V1.7.6

Na aba Concorrentes, abra “Adicionar concorrente por CNPJ / endereço”. Os dados informados da Droga Ge ficam preenchidos como ponto de partida, sem cadastro automático nem confirmação cadastral presumida. Consulte o CNPJ para atualizar nome e endereço pela BrasilAPI, ou informe os dados da filial se a fonte estiver indisponível.

Escolha o grupo, localize o endereço e confira o ponto no mapa antes de clicar em “Cadastrar nesta localização”. O sistema exige centro cadastrado e localização dentro do raio atual. Não altera o centro da pesquisa. Se o endereço não for localizado, complete ou corrija a consulta; não usa coordenadas inventadas. Geocodificação usa Nominatim e pode retornar pontos aproximados, por isso a localização precisa ser conferida.

A loja é salva no banco local e passa a integrar o cadastro compartilhado com a pesquisa de mercado. Não cria preços nem integração de coleta para redes ainda não integradas. CNPJ repetido, ponto expirado, endereço alterado ou centro desatualizado são recusados. Fonte manual é identificada sem atribuição indevida ao cadastro de lojas do OSM. Alterações possuem auditoria local.

Validação: 115 testes Python, consulta completa no navegador e teste específico do cadastro manual (consulta, localização, invalidação após editar endereço, persistência, fonte correta, alteração de grupo e celular).
