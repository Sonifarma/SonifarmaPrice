# Localização de endereço fiscal — V1.7.8

A consulta de CNPJ agora preenche o endereço para localização como “Rua Iacanga, 356, Americana, SP, Brasil”. Complemento, bairro e CEP continuam nos dados cadastrais, mas não são concatenados ao nome da rua na consulta do mapa.

Quando a consulta completa não retorna pontos, tenta rua e número com cidade e estado estruturados. A última tentativa mantém a rua e a cidade, sem inventar coordenadas para o número. Resultados de trecho de rua são explicitamente marcados como localização aproximada; confira o mapa antes de cadastrar. A busca não usa centro de cidade como substituto da loja.

Para o cadastro já preenchido com endereço fiscal antigo, consulte novamente o CNPJ ou substitua o campo pelo endereço simplificado. O cadastro continua dependendo de seleção explícita do ponto e do raio.

Validação: suíte Python (119 testes antes da sinalização adicional de rua), quatro testes específicos de endereço fiscal e precisão após a alteração; consulta pública real retornou dois trechos da Rua Iacanga, sem confirmação do número 356. JavaScript e diff verificados.
