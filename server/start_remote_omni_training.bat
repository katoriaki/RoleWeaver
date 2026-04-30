@echo off
setlocal
cd /d "%~dp0.."

set "PY="
if exist "G\runtime\python.exe" set "PY=G\runtime\python.exe"
if not defined PY if exist "runtime\Scripts\python.exe" set "PY=runtime\Scripts\python.exe"
if not defined PY if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY set "PY=python"

echo [RoleWeaver] Starting remote Qwen3-Omni LoRA training on A800...
echo [RoleWeaver] This will upload the Shiro persona dataset, install remote training dependencies,
echo [RoleWeaver] stop the remote API to free GPU memory, and start training in the background.
echo.
"%PY%" server\start_remote_omni_training.py
set EXIT_CODE=%ERRORLEVEL%

echo.
echo [RoleWeaver] Start command exited with code %EXIT_CODE%.
echo [RoleWeaver] Use server\watch_remote_omni_training.bat to monitor progress.
pause
exit /b %EXIT_CODE%
