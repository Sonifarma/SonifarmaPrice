@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (pause & exit /b 1)
echo Atualizacao de dependencias concluida. Reinicie iniciar.bat.
pause
