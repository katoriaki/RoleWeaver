@echo off
setlocal

cd /d "%~dp0.."
echo [RoleWeaver LINE] Working directory: %CD%

if not exist "line\.env" (
  echo [RoleWeaver LINE] line\.env was not found.
  if exist "line\.env.example" (
    copy "line\.env.example" "line\.env" >nul
    echo [RoleWeaver LINE] Created line\.env from line\.env.example.
  )
  echo [RoleWeaver LINE] Please fill LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN in line\.env.
  start "" notepad "line\.env"
  pause
  exit /b 1
)

set "PYTHON_CMD="
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
  where py >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD (
  if exist ".venv\Scripts\python.exe" set "PYTHON_CMD=.venv\Scripts\python.exe"
)
if not defined PYTHON_CMD (
  echo [RoleWeaver LINE] Python was not found. Please install Python 3.11+ or create a .venv.
  pause
  exit /b 1
)

%PYTHON_CMD% -c "import fastapi, uvicorn, dotenv, linebot" >nul 2>nul
if errorlevel 1 (
  echo [RoleWeaver LINE] Missing Python dependencies.
  choice /C YN /M "Install dependencies from line\requirements.txt now"
  if errorlevel 2 (
    echo [RoleWeaver LINE] Install skipped.
    pause
    exit /b 1
  )
  %PYTHON_CMD% -m pip install -r line\requirements.txt
  if errorlevel 1 (
    echo [RoleWeaver LINE] Dependency installation failed.
    pause
    exit /b 1
  )
)

echo [RoleWeaver LINE] Starting bot. Press Ctrl+C to stop.
echo [RoleWeaver LINE] Python: %PYTHON_CMD%
%PYTHON_CMD% -c "import sys; print('[RoleWeaver LINE] Python exe:', sys.executable); import torch; print('[RoleWeaver LINE] torch:', torch.__version__, 'cuda:', torch.cuda.is_available())" 2>nul
%PYTHON_CMD% line\run_line_bot.py

set EXIT_CODE=%ERRORLEVEL%
echo.
echo [RoleWeaver LINE] Server exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
