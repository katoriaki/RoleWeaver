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

"%ROLEWEAVER_TUNNEL_PYTHON%" -m pip install -r server\requirements-tunnel.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
pause
