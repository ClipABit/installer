@echo off
setlocal EnableDelayedExpansion
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
IF "%CLIPABIT_ENVIRONMENT%"=="" SET CLIPABIT_ENVIRONMENT=prod

IF "%CLIPABIT_AUTH0_DOMAIN%"=="" GOTO :MISSING_AUTH0
IF "%CLIPABIT_AUTH0_CLIENT_ID%"=="" GOTO :MISSING_AUTH0
IF "%CLIPABIT_AUTH0_AUDIENCE%"=="" GOTO :MISSING_AUTH0
IF "%CLIPABIT_ENVIRONMENT%"=="" GOTO :MISSING_AUTH0

echo [0/7] Auth0 configuration validated.
GOTO :CONFIG_OK

:MISSING_AUTH0
echo [ERROR] Auth0 environment variables are not fully set.
echo   CLIPABIT_AUTH0_DOMAIN=%CLIPABIT_AUTH0_DOMAIN%
echo   CLIPABIT_AUTH0_CLIENT_ID=%CLIPABIT_AUTH0_CLIENT_ID%
echo   CLIPABIT_AUTH0_AUDIENCE=%CLIPABIT_AUTH0_AUDIENCE%
echo   CLIPABIT_ENVIRONMENT=%CLIPABIT_ENVIRONMENT%
echo.
echo The installer requires these values to be 'baked in' at build time.
echo Please set them in your terminal before running this script.
pause
exit /b 1

:CONFIG_OK
REM IMPORTANT FOR DEVELOPERS:
REM The bundled Python runtime is sourced from python-build-standalone:
REM https://github.com/astral-sh/python-build-standalone/releases
REM
REM If you update PYTHON_VERSION or PYTHON_BUILD_TAG, you MUST update the
REM SHA256 checksums below. This is a security feature (Dependency Pinning)
REM that prevents supply-chain attacks and ensures every installer uses the
REM exact same byte-for-byte runtime.
REM
REM To get new SHAs:
REM 1. Visit the release page for the PYTHON_BUILD_TAG on GitHub.
REM 2. IMPORTANT: Look ONLY for the "install_only" variants (e.g. cpython-...-install_only.tar.gz).
REM    Ignore "debug", "pgo", "lto", or "full" variants as they are much larger and not needed.
REM 3. Find the .sha256 file for the corresponding platform archive OR
REM    calculate it manually after downloading:
REM    certutil -hashfile cpython-<version>+<tag>-<platform>-install_only.tar.gz SHA256
REM -------------------------------------------------------------------
REM -------------------------------------------------------------------
set PYTHON_CACHE_DIR=%TEMP%\clipabit-python-cache
REM -------------------------------------------------------------------

set PYTHON_VERSION=3.11.15
set PYTHON_BUILD_TAG=20260303
set PYTHON_SHA256=6f194e1ede02260fd3d758893bbf1d3bb4084652d436a8300a229da721c3ddf8
REM -------------------------------------------------------------------

REM Check if Python is installed (for build tooling — not the bundled runtime)
REM NOTE: This is the HOST Python used to run PyInstaller, not the bundled
REM Python 3.11 that gets packaged into the .exe for end users.
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
REM Pin PyInstaller to a vetted version to reduce supply-chain risk.
REM Using ==6.16.0 prevents auto-upgrading to potentially compromised versions.
REM Update this pin explicitly after reviewing new PyInstaller releases.
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
    set PYTHON_URL=https://github.com/astral-sh/python-build-standalone/releases/download/%PYTHON_BUILD_TAG%/!PYTHON_ARCHIVE!

    if not exist "%PYTHON_CACHE_DIR%" mkdir "%PYTHON_CACHE_DIR%"
    echo      Downloading !PYTHON_URL!...
    curl -fSL -o "%PYTHON_CACHE_DIR%\!PYTHON_ARCHIVE!" "!PYTHON_URL!"
    if errorlevel 1 (
        echo [ERROR] Failed to download Python %PYTHON_VERSION%
        pause
        exit /b 1
    )

    REM Verify checksum to ensure download integrity (corrupted/MITM detection)
    echo      Verifying checksum...
    for /f "skip=1 tokens=*" %%H in ('certutil -hashfile "%PYTHON_CACHE_DIR%\!PYTHON_ARCHIVE!" SHA256 ^| findstr /v "CertUtil"') do (
        set "ACTUAL_SHA256=%%H"
        goto :check_hash
    )
    :check_hash
    REM Remove any spaces from certutil output
    set "ACTUAL_SHA256=!ACTUAL_SHA256: =!"
    if /i not "!ACTUAL_SHA256!"=="%PYTHON_SHA256%" (
        echo [ERROR] SHA256 mismatch!
        echo   Expected: %PYTHON_SHA256%
        echo   Actual:   !ACTUAL_SHA256!
        del "%PYTHON_CACHE_DIR%\!PYTHON_ARCHIVE!" >nul 2>&1
        pause
        exit /b 1
    )
    echo      Checksum verified

    echo      Extracting...
    tar xzf "%PYTHON_CACHE_DIR%\!PYTHON_ARCHIVE!" -C "%PYTHON_CACHE_DIR%"
    del "%PYTHON_CACHE_DIR%\!PYTHON_ARCHIVE!" >nul 2>&1
) else (
    echo      Using cached Python from %PYTHON_CACHE_DIR%\python
)

REM Validate bundled Python (BUILD-TIME smoke test on developer machine)
REM This catches corrupted downloads before packaging. A separate install-time
REM validation happens on the end user's machine (see installer-script.py).
"%PYTHON_CACHE_DIR%\python\python.exe" --version
if errorlevel 1 (
    echo [ERROR] Bundled Python validation failed
    pause
    exit /b 1
)
echo      Bundled Python validated

echo.
echo [4/7] Retrieving plugin release...
REM Fetch metadata regardless of whether we need to download, to ensure correct labeling.
if "%CLIPABIT_ENVIRONMENT%"=="staging" (
    echo      Staging environment detected. Fetching latest pre-release/release metadata...
    set API_URL=https://api.github.com/repos/ClipABit/Resolve-Plugin/releases
    for /f "delims=" %%i in ('powershell -Command "(Invoke-RestMethod -Uri '%API_URL%')[0].tag_name"') do set LATEST_TAG=%%i
) else if "%CLIPABIT_ENVIRONMENT%"=="prod" (
    echo      Production environment. Fetching latest production release metadata...
    set API_URL=https://api.github.com/repos/ClipABit/Resolve-Plugin/releases/latest
    for /f "delims=" %%i in ('powershell -Command "(Invoke-RestMethod -Uri '%API_URL%').tag_name"') do set LATEST_TAG=%%i
)

if not "!LATEST_TAG!"=="" (
    echo      Latest release tag: !LATEST_TAG!
)

if not exist "plugin\clipabit.py" (
    echo      Plugin not found locally. Downloading from GitHub...
    if "!LATEST_TAG!"=="" (
        echo [ERROR] Could not fetch release tag from GitHub API: !API_URL!
        pause
        exit /b 1
    )

    set ARCHIVE_URL=https://github.com/ClipABit/Resolve-Plugin/archive/refs/tags/!LATEST_TAG!.zip
    
    echo      Downloading !ARCHIVE_URL!...
    curl -fSL -o "%TEMP%\plugin.zip" "!ARCHIVE_URL!"
    if errorlevel 1 (
        echo [ERROR] Failed to download plugin archive.
        pause
        exit /b 1
    )

    echo      Extracting...
    tar xzf "%TEMP%\plugin.zip" -C "%TEMP%"
    
    REM Find the extracted folder and copy its contents
    for /d %%d in ("%TEMP%\Resolve-Plugin-*") do (
        xcopy "%%d" "plugin\" /E /I /Y >nul
        goto :plugin_copied
    )
    :plugin_copied
    del "%TEMP%\plugin.zip" >nul 2>&1
    echo      Plugin downloaded and staged.
) else (
    echo      Plugin already present, skipping download
)
REM Validate full plugin structure regardless of download. Even if plugin/
REM exists from a previous build, ensure it's complete before proceeding.
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
REM IMPORTANT: The bundled Python has NO C compiler. We must verify that all
REM dependencies have pre-built binary wheels (no source-only packages).
REM If this check passes at build time, we guarantee install-time won't fail.

REM Extract dependencies from pyproject.toml to a temporary requirements file
set TEMP_REQS=%TEMP%\clipabit-reqs-%RANDOM%.txt
"%PYTHON_CACHE_DIR%\python\python.exe" -c "import tomllib; data = tomllib.load(open('plugin/pyproject.toml', 'rb')); [print(d) for d in data['project']['dependencies']]" > "%TEMP_REQS%"
if errorlevel 1 (
    echo [ERROR] Failed to extract dependencies from pyproject.toml
    pause
    exit /b 1
)

"%PYTHON_CACHE_DIR%\python\python.exe" -m pip install --dry-run --only-binary=:all: --target "%TEMP%\wheel-check" -r "%TEMP_REQS%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Not all dependencies have binary wheels available.
    echo The bundled Python has no C compiler - sdist-only packages will fail at install time.
    del "%TEMP_REQS%" >nul 2>&1
    pause
    exit /b 1
)
del "%TEMP_REQS%" >nul 2>&1
echo      All dependencies have binary wheels

echo.
echo [6/7] Building Windows executable...
echo      Baking plugin release: %LATEST_TAG%
REM Create release.json for metadata (read by installer-script.py)
echo {"tag": "%LATEST_TAG%", "environment": "%CLIPABIT_ENVIRONMENT%"} > release.json
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
