SONIFARMA PRICE INTELLIGENCE V1.0 - PILOTO
==========================================
REQUISITOS: Windows Server 2019, Python 3.12 ESTAVEL, acesso ao PostgreSQL Alpha7.

1. Extraia o conteudo deste ZIP em C:\SonifarmaPrice
2. Verifique se a porta 8770 esta livre: netstat -ano | findstr :8770
3. Execute instalar.bat como usuario com permissao de instalar pacotes.
4. Execute iniciar.bat e abra http://localhost:8770
5. O modo inicial e DEMO, com os CSVs de amostra enviados (10 linhas por arquivo).
6. Para usar o Alpha7: edite .env, configure MODE=postgres e as credenciais.
   Nao use credenciais de administracao ou de escrita; use conta PostgreSQL SELECT-only.
7. Reinicie iniciar.bat; valide /api/diagnostic e depois /api/products.

IMPORTANTE:
- A conexao PostgreSQL e forçada a transacao read-only com timeout de 12s.
- A consulta de giro pode ser pesada em banco grande; testar fora do horario de pico.
- O status F foi assumido para vendas e itens finalizados; validar com Alpha7.
- A unidade 1 e um valor inicial, confirmar com a administracao do ERP.
- O modo demo exibe amostras, nao e um espelho completo do banco.
- Nenhum preco e atualizado; exportacao TXT, coleta de concorrentes e automacao nao implementadas nesta etapa.
- Nao exponha a porta 8770 diretamente na Internet. Use somente rede local protegida.
- Antes de ativar acesso de rede para varios usuarios, implementar login e controle de acesso.
- Instalacao como servico Windows NAO automatizada nesta entrega; validar primeiro em execucao manual.
- Se o esquema real divergir das amostras, ajustar consulta SQL antes de uso em producao.
