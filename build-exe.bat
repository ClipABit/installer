@echo off
REM Build ClipABit Windows Installer using PyInstaller
REM
REM Optional env vars:
REM   CLIPABIT_AUTH0_DOMAIN
REM   CLIPABIT_AUTH0_CLIENT_ID
REM   CLIPABIT_AUTH0_AUDIENCE
REM   CLIPABIT_ENVIRONMENT  (defaults to "prod")

echo ========================================
echo   ClipABit Windows Installer Builder
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo.
    echo Please install Python 3.12+ from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [1/5] Checking Python version...
python -c "import sys; v=sys.version_info; print(f'Python {v.major}.{v.minor}.{v.micro}'); sys.exit(0 if v >= (3,12) else 1)"
if errorlevel 1 (
    echo [ERROR] Python 3.12 or higher is required.
    pause
    exit /b 1
)

echo.
echo [2/5] Installing build dependencies...
python -m pip install --upgrade pip >nul 2>&1
pip install pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to install build dependencies
    pause
    exit /b 1
)
echo      Build dependencies installed

echo.
echo [3/5] Downloading plugin from GitHub...
if not exist "plugin\clipabit.py" (
    python installer-script.py --download-only
    if errorlevel 1 (
        echo [ERROR] Failed to download plugin
        pause
        exit /b 1
    )
) else (
    echo      Plugin already present, skipping download
)

echo.
echo [4/5] Building Windows executable...
pyinstaller clipabit-installer.spec
if errorlevel 1 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [5/5] Verifying build...
if exist dist\ClipABit-Installer.exe (
    echo.
    echo ========================================
    echo   Build Successful!
    echo ========================================
    echo.
    echo Installer location: dist\ClipABit-Installer.exe
    for %%A in (dist\ClipABit-Installer.exe) do echo File size: %%~zA bytes
    echo.
    echo You can now distribute this .exe file.
    echo Users do not need Python installed to run it.
    echo.
) else (
    echo [ERROR] Executable not found after build!
    exit /b 1
)

pause
