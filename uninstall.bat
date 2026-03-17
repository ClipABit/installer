@echo off
REM ClipABit Uninstaller for Windows
REM Standalone script — no Python required.
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo ClipABit Uninstaller
echo ============================================================
echo.

REM Resolve directories
set "SHIM=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\ClipABit.py"
set "PLUGIN_PKG=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Modules\clipabit"
REM ClipABit application directories
set "PYTHON_DIR=%LOCALAPPDATA%\ClipABit\python"
set "DEPS_DIR=%LOCALAPPDATA%\ClipABit\deps"
set "CONFIG_FILE=%APPDATA%\ClipABit\config.dat"
set "CLIPABIT_LOCAL=%LOCALAPPDATA%\ClipABit"
set "CLIPABIT_ROAMING=%APPDATA%\ClipABit"

REM Check if Resolve is running
tasklist /FI "IMAGENAME eq Resolve.exe" 2>NUL | find /I "Resolve.exe" >NUL
if %ERRORLEVEL% equ 0 (
    echo   WARNING: DaVinci Resolve is currently running.
    echo   Please close it before uninstalling, or restart it after.
    if /I not "%~1"=="-y" if /I not "%~1"=="--yes" (
        set /p "answer=  Continue anyway? [y/N]: "
        if /I not "!answer!"=="y" if /I not "!answer!"=="yes" (
            echo   Uninstall cancelled.
            goto :eof
        )
    )
)

REM Check what exists
set "found=0"
if exist "%SHIM%" set "found=1"
if exist "%PLUGIN_PKG%" set "found=1"
if exist "%PYTHON_DIR%" set "found=1"
if exist "%DEPS_DIR%" set "found=1"
if exist "%CONFIG_FILE%" set "found=1"

if "%found%"=="0" (
    echo   No ClipABit installation found. Nothing to remove.
    goto :eof
)

REM Display what will be removed
echo   The following will be removed:
echo.
if exist "%SHIM%"       echo     Bootstrap shim:  %SHIM%
if exist "%PLUGIN_PKG%" echo     Plugin package:  %PLUGIN_PKG%
if exist "%PYTHON_DIR%" echo     Python runtime:  %PYTHON_DIR%
if exist "%DEPS_DIR%"   echo     Dependencies:    %DEPS_DIR%
if exist "%CONFIG_FILE%" echo     Configuration:   %CONFIG_FILE%
echo.
echo   Credential Manager entry (clipabit-plugin) will also be cleared.

REM Confirmation
if /I not "%~1"=="-y" if /I not "%~1"=="--yes" (
    echo.
    set /p "answer=  Proceed with uninstall? [y/N]: "
    if /I not "!answer!"=="y" if /I not "!answer!"=="yes" (
        echo   Uninstall cancelled.
        goto :eof
    )
)

echo.

REM Remove files — shim first
if exist "%SHIM%" (
    del /f "%SHIM%" && echo   Removed: Bootstrap shim
)
if exist "%SHIM%.bak" del /f "%SHIM%.bak"
if exist "%PLUGIN_PKG%" (
    rmdir /s /q "%PLUGIN_PKG%" && echo   Removed: Plugin package
)
if exist "%PLUGIN_PKG%.bak" rmdir /s /q "%PLUGIN_PKG%.bak"
if exist "%PYTHON_DIR%" (
    rmdir /s /q "%PYTHON_DIR%" && echo   Removed: Python runtime
)
if exist "%PYTHON_DIR%.bak" rmdir /s /q "%PYTHON_DIR%.bak"
if exist "%DEPS_DIR%" (
    rmdir /s /q "%DEPS_DIR%" && echo   Removed: Dependencies
)
if exist "%DEPS_DIR%.bak" rmdir /s /q "%DEPS_DIR%.bak"
if exist "%CONFIG_FILE%" (
    del /f "%CONFIG_FILE%" && echo   Removed: Configuration
)
if exist "%CONFIG_FILE%.bak" del /f "%CONFIG_FILE%.bak"

REM Clear Credential Manager entry
cmdkey /delete:clipabit-plugin >NUL 2>&1
if %ERRORLEVEL% equ 0 (
    echo   Credential Manager entry removed.
) else (
    echo   No Credential Manager entry found.
)

REM Clean up empty directories
if exist "%CLIPABIT_LOCAL%" (
    dir /b "%CLIPABIT_LOCAL%" 2>NUL | findstr "." >NUL 2>&1
    if errorlevel 1 (
        rmdir "%CLIPABIT_LOCAL%" && echo   Removed empty directory: %CLIPABIT_LOCAL%
    )
)
if exist "%CLIPABIT_ROAMING%" (
    dir /b "%CLIPABIT_ROAMING%" 2>NUL | findstr "." >NUL 2>&1
    if errorlevel 1 (
        rmdir "%CLIPABIT_ROAMING%" && echo   Removed empty directory: %CLIPABIT_ROAMING%
    )
)

echo.
echo ============================================================
echo ClipABit Uninstall Complete
echo ============================================================
echo.

endlocal
