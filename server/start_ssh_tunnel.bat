@echo off
setlocal

cd /d "%~dp0\.."

if "%ROLEWEAVER_TUNNEL_PYTHON%"=="" (
  if exist "runtime\server_venv\Scripts\python.exe" (
    set "ROLEWEAVER_TUNNEL_PYTHON=runtime\server_venv\Scripts\python.exe"
  ) else if exist ".venv\Scripts\python.exe" (
    set "ROLEWEAVER_TUNNEL_PYTHON=.venv\Scripts\python.exe"
  ) else (
    set "ROLEWEAVER_TUNNEL_PYTHON=python"
  )
)

if "%ROLEWEAVER_TUNNEL_CONFIG%"=="" (
  set "ROLEWEAVER_TUNNEL_CONFIG=server\ssh_tunnel.config.local.csv"
)

echo [RoleWeaver SSH] Working directory: %CD%
echo [RoleWeaver SSH] Config: %ROLEWEAVER_TUNNEL_CONFIG%
echo [RoleWeaver SSH] Python: %ROLEWEAVER_TUNNEL_PYTHON%
echo [RoleWeaver SSH] If paramiko is missing, run:
echo [RoleWeaver SSH]   %ROLEWEAVER_TUNNEL_PYTHON% -m pip install -r server\requirements-tunnel.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
echo.

"%ROLEWEAVER_TUNNEL_PYTHON%" server\ssh_tunnel.py --config "%ROLEWEAVER_TUNNEL_CONFIG%"

echo.
echo [RoleWeaver SSH] Tunnel exited with code %ERRORLEVEL%.
pause
