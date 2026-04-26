@echo off
setlocal

cd /d "%~dp0"

set "ROLEWEAVER_HOST=127.0.0.1"
set "ROLEWEAVER_PORT=8000"
set "ROLEWEAVER_CONFIG=roleweaver.config.csv"
set "PYTHON_CMD="

echo [RoleWeaver] Working directory: %CD%

py -3 --version >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
  python --version >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
  echo [RoleWeaver] Python was not found in PATH.
  echo Please install Python 3.10+ or start RoleWeaver from an activated Python environment.
  pause
  exit /b 1
)

if not exist "%ROLEWEAVER_CONFIG%" (
  echo [RoleWeaver] %ROLEWEAVER_CONFIG% was not found.
  echo [RoleWeaver] Creating it from roleweaver.config.example.csv.
  copy /Y "roleweaver.config.example.csv" "%ROLEWEAVER_CONFIG%" >nul
  echo.
  echo Please fill these values before the first real run:
  echo   - base_model_path
  echo   - lora_path
  echo   - skill_file
  echo.
  start "" "%ROLEWEAVER_CONFIG%"
  pause
)

start "" /min powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 3; Start-Process 'http://%ROLEWEAVER_HOST%:%ROLEWEAVER_PORT%/'"

echo [RoleWeaver] Starting API and web frontend...
echo [RoleWeaver] Open http://%ROLEWEAVER_HOST%:%ROLEWEAVER_PORT%/ if the browser does not open automatically.
echo [RoleWeaver] Press Ctrl+C in this window to stop the server.
echo.

%PYTHON_CMD% API.py --config "%ROLEWEAVER_CONFIG%" --host "%ROLEWEAVER_HOST%" --port %ROLEWEAVER_PORT%

endlocal
