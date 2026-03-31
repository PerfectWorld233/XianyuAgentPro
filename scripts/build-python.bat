@echo off
echo ===== Building Python bridge with PyInstaller =====
cd /d "%~dp0..\python"

:: 检查 PyInstaller 是否可用
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller not found. Run: pip install pyinstaller
    exit /b 1
)

:: 检查 faiss-cpu 是否已安装
python -c "import faiss" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] faiss-cpu not found. Run: pip install faiss-cpu
    exit /b 1
)

call pyinstaller bridge.spec --distpath ..\build\python-dist --workpath ..\build\python-work --clean --noconfirm

if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed!
    exit /b 1
)

echo ===== Python bridge built successfully =====
echo Output: build\python-dist\bridge\
