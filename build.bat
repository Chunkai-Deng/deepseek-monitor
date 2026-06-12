@echo off
:: ============================================================
:: DeepSeek Monitor — Build Script (Windows)
:: Clean previous artifacts and compile a fresh .exe
:: Usage: build.bat   (or double-click in Explorer)
:: ============================================================
setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo ========================================
echo  DeepSeek Monitor — Build
echo ========================================

:: ---- Step 1: Clean previous build artifacts ----
echo.
echo [1/3] Cleaning previous build artifacts...

if exist "%PROJECT_DIR%build" (
    rmdir /s /q "%PROJECT_DIR%build"
)
if exist "%PROJECT_DIR%dist" (
    rmdir /s /q "%PROJECT_DIR%dist"
)
if exist "%PROJECT_DIR%DeepSeekMonitor.spec" (
    del /q "%PROJECT_DIR%DeepSeekMonitor.spec"
)

echo        Done

:: ---- Step 2: Verify dependencies ----
echo.
echo [2/3] Verifying dependencies...

python -c "import PySide6; import requests; import pandas; import numpy" >nul 2>&1
if errorlevel 1 (
    echo        Missing dependencies, installing...
    pip install -r "%PROJECT_DIR%requirements.txt"
    pip install pyinstaller
)
echo        Done

:: ---- Step 3: Compile ----
echo.
echo [3/3] Compiling standalone exe...
echo.

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "DeepSeekMonitor" ^
    --add-data "requirements.txt;." ^
    "%PROJECT_DIR%main.py"

if errorlevel 1 (
    echo.
    echo ========================================
    echo  Build FAILED!
    echo ========================================
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Build complete!
echo  Output: %PROJECT_DIR%dist\DeepSeekMonitor.exe
echo ========================================
pause
