@echo off
setlocal
cd /d "%~dp0.."

set "PY="
if exist "G\runtime\python.exe" set "PY=G\runtime\python.exe"
if not defined PY if exist "runtime\Scripts\python.exe" set "PY=runtime\Scripts\python.exe"
if not defined PY if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY set "PY=python"

echo [RoleWeaver] Watching remote Qwen3-Omni LoRA training...
echo [RoleWeaver] Press Ctrl+C to close this monitor. Training keeps running on the server.
echo.
"%PY%" server\watch_remote_training.py --run-dir training_runs/qwen3_omni_shiro_persona/latest

echo.
pause
