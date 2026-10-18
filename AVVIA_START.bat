@echo off
setlocal
cd /d "%~dp0"
if not exist "runtime\pythonw.exe" (
  echo Estrai tutto lo ZIP. / Extract the entire ZIP first.
  pause
  exit /b 1
)
start "" "%~dp0runtime\pythonw.exe" "%~dp0app.py"
