@echo off
echo ===== Building Python bridge with PyInstaller =====
cd /d "%~dp0..\python"

call pyinstaller bridge.spec --distpath ..\build\python-dist --workpath ..\build\python-work --clean

if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed!
    exit /b 1
)

echo ===== Python bridge built successfully =====
