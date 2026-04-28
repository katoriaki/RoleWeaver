@echo off
setlocal

cd /d "%~dp0"

set "BASE_PYTHON="
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "BASE_PYTHON=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined BASE_PYTHON (
  where python >nul 2>nul
  if not errorlevel 1 set "BASE_PYTHON=python"
)
if not defined BASE_PYTHON (
  where py >nul 2>nul
  if not errorlevel 1 set "BASE_PYTHON=py -3"
)

if not defined BASE_PYTHON (
  echo [RoleWeaver Runtime] Python 3.11+ was not found.
  echo [RoleWeaver Runtime] Install Python, then run this script again.
  pause
  exit /b 1
)

echo [RoleWeaver Runtime] Working directory: %CD%
echo [RoleWeaver Runtime] Base Python: %BASE_PYTHON%

if not exist "runtime\Scripts\python.exe" (
  echo [RoleWeaver Runtime] Creating runtime virtual environment...
  %BASE_PYTHON% -m venv runtime
  if errorlevel 1 (
    echo [RoleWeaver Runtime] Failed to create runtime.
    pause
    exit /b 1
  )
)

echo [RoleWeaver Runtime] Upgrading pip...
runtime\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
  echo [RoleWeaver Runtime] pip upgrade failed.
  pause
  exit /b 1
)

echo [RoleWeaver Runtime] Installing RoleWeaver dependencies...
runtime\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo [RoleWeaver Runtime] Dependency installation failed.
  pause
  exit /b 1
)

echo [RoleWeaver Runtime] Installing CUDA 12.8 PyTorch for local NVIDIA GPUs...
runtime\Scripts\python.exe -m pip install --force-reinstall torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 (
  echo [RoleWeaver Runtime] CUDA PyTorch installation failed.
  echo [RoleWeaver Runtime] If this machine has no compatible NVIDIA GPU, edit setup_runtime.bat or install CPU torch manually.
  pause
  exit /b 1
)

echo.
echo [RoleWeaver Runtime] Done.
echo [RoleWeaver Runtime] Main launcher and LINE launcher will now prefer runtime\Scripts\python.exe.
pause
exit /b 0
