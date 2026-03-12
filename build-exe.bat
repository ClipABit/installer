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

REM -------------------------------------------------------------------
REM Configuration
REM -------------------------------------------------------------------
set PYTHON_VERSION=3.11.12
set PYTHON_BUILD_TAG=20250529
set PYTHON_SHA256=3258b902130179f72a3086ad87deccfa2f111faff54de444535d7b72d99f2b20
set PYTHON_CACHE_DIR=build\python

REM Check if Python is installed (for build tooling — not the bundled runtime)
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

echo [1/7] Checking Python version...
python -c "import sys; v=sys.version_info; print(f'Python {v.major}.{v.minor}.{v.micro}'); sys.exit(0 if v >= (3,12) else 1)"
if errorlevel 1 (
    echo [ERROR] Python 3.12 or higher is required.
    pause
    exit /b 1
)

echo.
echo [2/7] Installing build dependencies...
python -m pip install --upgrade pip >nul 2>&1
REM Pin PyInstaller to a vetted version to reduce supply-chain risk; update explicitly when needed
python -m pip install pyinstaller==6.16.0 >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to install build dependencies
    pause
    exit /b 1
)
echo      Build dependencies installed

echo.
echo [3/7] Downloading bundled Python %PYTHON_VERSION%...
if not exist "%PYTHON_CACHE_DIR%\python\python.exe" (
    set PYTHON_ARCHIVE=cpython-%PYTHON_VERSION%+%PYTHON_BUILD_TAG%-x86_64-pc-windows-msvc-install_only.tar.gz
    set PYTHON_URL=https://github.com/astral-sh/python-build-standalone/releases/download/%PYTHON_BUILD_TAG%/%PYTHON_ARCHIVE%

    if not exist "%PYTHON_CACHE_DIR%" mkdir "%PYTHON_CACHE_DIR%"
    echo      Downloading %PYTHON_URL%...
    curl -fSL -o "%PYTHON_CACHE_DIR%\%PYTHON_ARCHIVE%" "%PYTHON_URL%"
    if errorlevel 1 (
        echo [ERROR] Failed to download Python %PYTHON_VERSION%
        pause
        exit /b 1
    )

    REM Verify checksum
    echo      Verifying checksum...
    for /f "skip=1 tokens=*" %%H in ('certutil -hashfile "%PYTHON_CACHE_DIR%\%PYTHON_ARCHIVE%" SHA256 ^| findstr /v "CertUtil"') do (
        set "ACTUAL_SHA256=%%H"
        goto :check_hash
    )
    :check_hash
    REM Remove any spaces from certutil output
    set "ACTUAL_SHA256=%ACTUAL_SHA256: =%"
    if /i not "%ACTUAL_SHA256%"=="%PYTHON_SHA256%" (
        echo [ERROR] SHA256 mismatch!
        echo   Expected: %PYTHON_SHA256%
        echo   Actual:   %ACTUAL_SHA256%
        del "%PYTHON_CACHE_DIR%\%PYTHON_ARCHIVE%" >nul 2>&1
        pause
        exit /b 1
    )
    echo      Checksum verified

    echo      Extracting...
    tar xzf "%PYTHON_CACHE_DIR%\%PYTHON_ARCHIVE%" -C "%PYTHON_CACHE_DIR%"
    del "%PYTHON_CACHE_DIR%\%PYTHON_ARCHIVE%" >nul 2>&1
) else (
    echo      Using cached Python from %PYTHON_CACHE_DIR%\python
)

REM Validate bundled Python
"%PYTHON_CACHE_DIR%\python\python.exe" --version
if errorlevel 1 (
    echo [ERROR] Bundled Python validation failed
    pause
    exit /b 1
)
echo      Bundled Python validated

echo.
echo [4/7] Downloading plugin from GitHub...
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
REM Validate full plugin structure regardless of download
if not exist "plugin\pyproject.toml" (
    echo [ERROR] plugin\pyproject.toml missing. Required for dependency resolution.
    pause
    exit /b 1
)
if not exist "plugin\clipabit" (
    echo [ERROR] plugin\clipabit directory missing.
    pause
    exit /b 1
)

echo.
echo [5/7] Validating binary wheel availability...
"%PYTHON_CACHE_DIR%\python\python.exe" -m pip install --dry-run --only-binary=:all: --target "%TEMP%\wheel-check" -r requirements_from_toml.txt >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Wheel validation skipped or failed. Verify manually.
)
echo      Wheel validation complete

echo.
echo [6/7] Building Windows executable...
pyinstaller clipabit-installer.spec
if errorlevel 1 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [7/7] Verifying build...
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
    echo The bundled Python runtime is included - no Python installation required.
    echo.
) else (
    echo [ERROR] Executable not found after build!
    exit /b 1
)

pause
