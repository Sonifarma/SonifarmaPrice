@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Execute instalar.bat primeiro.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" "%~dp0manutencao.py" update %*
set "RESULTADO=%ERRORLEVEL%"
pause
exit /b %RESULTADO%
