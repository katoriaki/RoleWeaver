@echo off
setlocal

cd /d "%~dp0..\.."

set "PYTHON_EXE=%CD%\runtime\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo [RoleWeaver Persona Eval] Missing runtime python:
  echo   %PYTHON_EXE%
  echo Run setup_runtime.bat first.
  pause
  exit /b 1
)

set "CONFIG_FILE=%CD%\roleweaver.config.csv"
set "REPORT_DIR=%CD%\eval\persona_regression\reports"
if not exist "%REPORT_DIR%" mkdir "%REPORT_DIR%"

for /f "tokens=1-4 delims=/ " %%a in ("%date%") do set "DATE_PART=%%a-%%b-%%c"
for /f "tokens=1-3 delims=:." %%a in ("%time%") do set "TIME_PART=%%a%%b%%c"
set "REPORT_FILE=%REPORT_DIR%\persona_eval_%DATE_PART%_%TIME_PART%.json"

echo [RoleWeaver Persona Eval] Working directory: %CD%
echo [RoleWeaver Persona Eval] Config: %CONFIG_FILE%
echo [RoleWeaver Persona Eval] Report: %REPORT_FILE%
echo [RoleWeaver Persona Eval] This will load the configured local model.

"%PYTHON_EXE%" eval\persona_regression\run_persona_eval.py --local --config-file "%CONFIG_FILE%" --session-id persona-eval --report "%REPORT_FILE%"

echo.
echo [RoleWeaver Persona Eval] Finished with code %ERRORLEVEL%.
pause
exit /b %ERRORLEVEL%
