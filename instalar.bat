@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (echo Python launcher nao encontrado.& pause& exit /b 1)
py -3.12 -m venv .venv
if errorlevel 1 (echo Falha ao criar ambiente Python 3.12.& pause& exit /b 1)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if not exist .env copy .env.exemplo .env
if errorlevel 1 (echo Erro na instalacao.& pause& exit /b 1)
echo Instalacao concluida. Execute iniciar.bat.
pause
