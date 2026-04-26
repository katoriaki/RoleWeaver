@echo off
setlocal

cd /d "%~dp0"

set "ROLEWEAVER_HOST=127.0.0.1"
set "ROLEWEAVER_PORT=8000"
set "ROLEWEAVER_DEFAULT_PORT=8000"
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

%PYTHON_CMD% -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo [RoleWeaver] Missing HTTP server dependencies: fastapi and/or uvicorn.
  echo [RoleWeaver] These are required for the local web UI.
  echo.
  choice /M "Install FastAPI and Uvicorn into the current Python environment now"
  if errorlevel 2 (
    echo [RoleWeaver] Install skipped.
    echo [RoleWeaver] You can install manually with:
    echo   %PYTHON_CMD% -m pip install fastapi "uvicorn[standard]"
    pause
    exit /b 1
  )

  %PYTHON_CMD% -m pip --version >nul 2>nul
  if errorlevel 1 (
    echo [RoleWeaver] pip was not found. Trying ensurepip...
    %PYTHON_CMD% -m ensurepip --upgrade
    if errorlevel 1 (
      echo [RoleWeaver] Could not enable pip. Please install pip manually.
      pause
      exit /b 1
    )
  )

  %PYTHON_CMD% -m pip install fastapi "uvicorn[standard]"
  if errorlevel 1 (
    echo [RoleWeaver] Failed to install FastAPI/Uvicorn.
    pause
    exit /b 1
  )
)

if not exist "%ROLEWEAVER_CONFIG%" (
  echo [RoleWeaver] %ROLEWEAVER_CONFIG% was not found.
  echo [RoleWeaver] Creating it from roleweaver.config.example.csv.
  copy /Y "roleweaver.config.example.csv" "%ROLEWEAVER_CONFIG%" >nul
  echo.
  echo Please fill these values before the first real run:
  echo   - base_model_path
  echo   - lora_path ^(optional; leave blank to use the base model only^)
  echo   - skill_file or skill_text ^(optional^)
  echo   - quantization_mode ^(default: 4bit^)
  echo.
  start "" "%ROLEWEAVER_CONFIG%"
  pause
)

%PYTHON_CMD% -c "import urllib.request; urllib.request.urlopen('http://%ROLEWEAVER_HOST%:%ROLEWEAVER_PORT%/health', timeout=1).read(64)" >nul 2>nul
if not errorlevel 1 (
  echo [RoleWeaver] RoleWeaver already appears to be running on %ROLEWEAVER_HOST%:%ROLEWEAVER_PORT%.
  start "" "http://%ROLEWEAVER_HOST%:%ROLEWEAVER_PORT%/"
  exit /b 0
)

for /f %%P in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$hostName='%ROLEWEAVER_HOST%'; $start=%ROLEWEAVER_PORT%; for ($port=$start; $port -le ($start+20); $port++) { $listener=$null; try { $listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Parse($hostName), $port); $listener.Start(); $listener.Stop(); Write-Output $port; exit 0 } catch { if ($listener) { try { $listener.Stop() } catch {} } } }; exit 1"') do set "ROLEWEAVER_PORT=%%P"

if not "%ROLEWEAVER_PORT%"=="%ROLEWEAVER_DEFAULT_PORT%" (
  echo [RoleWeaver] Port %ROLEWEAVER_DEFAULT_PORT% is busy. Using %ROLEWEAVER_PORT% instead.
)

start "" /min powershell -NoProfile -ExecutionPolicy Bypass -Command "$hostName='%ROLEWEAVER_HOST%'; $port=%ROLEWEAVER_PORT%; $deadline=(Get-Date).AddSeconds(240); while ((Get-Date) -lt $deadline) { try { $client=New-Object Net.Sockets.TcpClient; $async=$client.BeginConnect($hostName,$port,$null,$null); if ($async.AsyncWaitHandle.WaitOne(1000,$false)) { $client.EndConnect($async); $client.Close(); Start-Process ('http://{0}:{1}/' -f $hostName,$port); exit 0 }; $client.Close() } catch { Start-Sleep -Milliseconds 700 } }; exit 1"

echo [RoleWeaver] Starting API and web frontend...
echo [RoleWeaver] Open http://%ROLEWEAVER_HOST%:%ROLEWEAVER_PORT%/ if the browser does not open automatically.
echo [RoleWeaver] Press Ctrl+C in this window to stop the server.
echo.

%PYTHON_CMD% API.py --config "%ROLEWEAVER_CONFIG%" --host "%ROLEWEAVER_HOST%" --port %ROLEWEAVER_PORT%

set "ROLEWEAVER_EXIT=%ERRORLEVEL%"
echo.
if not "%ROLEWEAVER_EXIT%"=="0" (
  echo [RoleWeaver] Server exited with code %ROLEWEAVER_EXIT%.
  echo [RoleWeaver] Check the error above. Common causes are missing Python packages, invalid model paths, or a missing skill file.
) else (
  echo [RoleWeaver] Server stopped.
)
pause

endlocal
