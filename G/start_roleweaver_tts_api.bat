@echo off
setlocal

cd /d "%~dp0"

if not exist "runtime\python.exe" (
  echo [RoleWeaver TTS] Missing runtime python: %CD%\runtime\python.exe
  pause
  exit /b 1
)

echo [RoleWeaver TTS] Starting GPT-SoVITS API...
"runtime\python.exe" "start_roleweaver_tts_api.py"

set EXIT_CODE=%ERRORLEVEL%
echo.
echo [RoleWeaver TTS] Server exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
