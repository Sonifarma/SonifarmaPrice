@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0SONIFARMA_PRICE_CONTROLE.ps1" update %*
set "RESULTADO=%ERRORLEVEL%"
pause
exit /b %RESULTADO%
