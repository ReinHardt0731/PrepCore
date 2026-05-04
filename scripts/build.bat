@echo off
REM Build script for PrepCore - Generates PrepCore.exe
REM This script uses PyInstaller to create an executable

echo.
echo ========================================
echo     PrepCore Build Script
echo ========================================
echo.

REM Check if PyInstaller is installed
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INSTALL] PyInstaller not found. Installing...
    python -m pip install pyinstaller pillow
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller
        exit /b 1
    )
)

REM Check if Pillow is installed (for image processing)
python -m pip show pillow >nul 2>&1
if errorlevel 1 (
    echo [INSTALL] Pillow not found. Installing...
    python -m pip install pillow
)

REM Prepare assets (round corners on logo)
echo [PREPARE] Creating rounded corners on Logo...
python scripts\prepare_assets.py
if errorlevel 1 (
    echo [WARN] Asset preparation had issues, but continuing...
)

REM Clean previous builds
if exist "build" (
    echo [CLEAN] Removing old build directory...
    rmdir /s /q build
)
if exist "dist" (
    echo [CLEAN] Removing old dist directory...
    rmdir /s /q dist
)

REM Build the executable
echo.
echo [BUILD] Creating PrepCore.exe...
echo This may take a few minutes...
echo.

pyinstaller --onefile ^
    --windowed ^
    --name PrepCore ^
    --icon=assets\images\icon.png ^
    --add-data "assets;assets" ^
    --hidden-import=PySide6 ^
    --hidden-import=PySide6.QtCore ^
    --hidden-import=PySide6.QtGui ^
    --hidden-import=PySide6.QtWidgets ^
    --hidden-import=PySide6.QtMultimedia ^
    src\main.py

if errorlevel 1 (
    echo [ERROR] Build failed!
    exit /b 1
)

echo.
echo ========================================
echo [SUCCESS] Build completed!
echo ========================================
echo.
echo The executable is located at:
echo   dist\PrepCore.exe
echo.
echo You can now:
echo   1. Run: dist\PrepCore.exe
echo   2. Create a shortcut to dist\PrepCore.exe
echo   3. Share the dist folder with others
echo.
pause
