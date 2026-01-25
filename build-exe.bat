@echo off
REM Build ClipABit Windows Installer using PyInstaller

echo ========================================
echo   ClipABit Windows Installer Builder
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo.
    echo Please install Python 3.8+ from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [1/4] Checking Python version...
python --version

echo.
echo [2/4] Installing PyInstaller and dependencies...
python -m pip install --upgrade pip >nul 2>&1
pip install pyinstaller tomli >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo      PyInstaller installed successfully

echo.
echo [3/4] Building Windows executable...
pyinstaller clipabit-installer.spec
if errorlevel 1 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [4/4] Verifying build...
if exist dist\ClipABit-Installer.exe (
    echo.
    echo ========================================
    echo   Build Successful!
    echo ========================================
    echo.
    echo Installer location: dist\ClipABit-Installer.exe
    for %%A in (dist\ClipABit-Installer.exe) do echo File size: %%~zA bytes
    echo.
    echo You can now distribute this .exe file
    echo Users do not need Python installed to run it
    echo.
) else (
    echo [ERROR] Executable not found after build!
    exit /b 1
)

pause
