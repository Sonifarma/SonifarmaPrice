@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Execute instalar.bat primeiro.
 pause
 exit /b 1
)
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8770
pause
