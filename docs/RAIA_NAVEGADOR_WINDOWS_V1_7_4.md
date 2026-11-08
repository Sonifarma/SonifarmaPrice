# Raia: navegador do Windows — V1.7.4

O operador confirmou que a página mostra produto e preço ao abrir normalmente no Chrome/Edge do mesmo servidor, enquanto o coletor retorna 403. O modo anterior usava navegador sem interface, JavaScript desativado e bloqueava scripts/estilos/outros recursos. O comportamento de leitura agora distingue esse modo leve da leitura normal da Raia.

## Nova tentativa da Raia

Se o acesso HTTP direto falhar, tenta o navegador instalado no servidor com JavaScript e recursos da página ativos. `PRICE_BROWSER_EXECUTABLE` explícito tem prioridade; sem ele, procura Chrome ou Edge nos caminhos usuais do Windows e usa Chromium do Playwright se nenhum for encontrado.

No Windows o modo automático abre uma janela temporária visível; no Linux permanece sem interface. O perfil é isolado e temporário, sem importar cookies, login ou perfil pessoal. Não altera cabeçalhos para simular terceiros, não resolve CAPTCHA e não pula recusa de robots.txt. A navegação principal continua limitada aos caminhos públicos cadastrados; preço, EAN, vendedor e disponibilidade seguem as mesmas validações.

O modo visível precisa de sessão Windows com área de trabalho disponível. Em execução como serviço sem área de trabalho, `PRICE_RAIA_BROWSER_MODE=headless` mantém a tentativa sem janela, porém não garante que a fonte aceite esse acesso. `visible` força janela e `auto` seleciona pelo sistema operacional. A Todo Dia mantém o modo leve que já retornou preço no servidor.

O leitor aguarda o carregamento normal da página e usa o DOM renderizado. O código não automatiza verificações da fonte. Se houver bloqueio, a consulta permanece sem preço novo e informa o erro.

## Diagnóstico

`python -m app.diagnostico_precos` agora informa modo visível/headless, JavaScript ativo e seleção de navegador do sistema. Os códigos `HTTP_403_ROBOTS` e `HTTP_403_PAGINA` distinguem a fase recusada. Não imprime o caminho do executável, credenciais, cookies ou senhas.

No servidor, pare o Price, atualize e execute o diagnóstico antes de reiniciar:

```powershell
cd C:\SonifarmaPrice
.\.venv\Scripts\python.exe .\manutencao.py update
if ($LASTEXITCODE -eq 0) {
    .\.venv\Scripts\python.exe -m app.diagnostico_precos --ean 7896230304536 --raio 2
    .\iniciar.bat
}
```

Mantenha a sessão do Windows aberta durante o teste e a consulta. Recarregue a interface com Ctrl+F5 e use Atualizar preços online. Se ainda houver 403, o diagnóstico deve ser enviado para confirmar a fase; abrir manualmente no perfil pessoal não comprova que uma sessão automatizada isolada será aceita.

## Validação e limite

112 testes Python verificaram modos, JavaScript, restrição de navegação, recursos da página, fechamento e fases de erro, além das validações de preço existentes. A tentativa com JavaScript e recursos ativos foi executada neste ambiente Linux e retornou R$ 14,99 para EAN 7896230304536 em 08/11/2026. A janela visível do Chrome/Edge no Windows foi verificada por testes de configuração; a aceitação real no servidor Windows ainda precisa do teste do operador. Não se afirma que o bloqueio externo foi resolvido antes desse teste.
