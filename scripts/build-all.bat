@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   XianyuAutoAgent Full Build Pipeline
echo ============================================

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%..
set BUILD_DIR=%ROOT_DIR%\build

:: Step 1: PyInstaller
echo.
echo [1/4] Building Python bridge...
call "%SCRIPT_DIR%build-python.bat"
if %errorlevel% neq 0 (
    echo [ERROR] Python build failed. Aborting.
    exit /b 1
)

:: Step 2: Vite renderer build
echo.
echo [2/4] Building Vue 3 renderer...
cd /d "%ROOT_DIR%\electron"
call npm run build:renderer
if %errorlevel% neq 0 (
    echo [ERROR] Renderer build failed. Aborting.
    exit /b 1
)

:: Step 3: electron-builder
echo.
echo [3/4] Packaging with electron-builder...
call npm run build:electron
if %errorlevel% neq 0 (
    echo [ERROR] electron-builder failed. Aborting.
    exit /b 1
)

:: Step 4: Inno Setup
echo.
echo [4/4] Creating installer with Inno Setup...
set ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if not exist "%ISCC_PATH%" (
    set ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe
)

if exist "%ISCC_PATH%" (
    mkdir "%BUILD_DIR%\installer-output" 2>nul
    "%ISCC_PATH%" "%ROOT_DIR%\installer\setup.iss"
    if %errorlevel% neq 0 (
        echo [WARNING] Inno Setup failed. Installer not created.
    ) else (
        echo [OK] Installer created in build\installer-output\
    )
) else (
    echo [WARNING] Inno Setup not found at expected path. Skipping installer creation.
    echo           Install Inno Setup 6 and add to PATH to enable installer creation.
)

echo.
echo ============================================
echo   Build complete!
echo   - Python dist : build\python-dist\bridge\
echo   - Electron dir: build\electron-dist\win-unpacked\
echo   - Installer   : build\installer-output\
echo ============================================
