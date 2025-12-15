@echo off
REM Build script for Windows
REM Creates a standalone .exe file

echo ============================================================
echo Building Dymo Code for Windows
echo ============================================================

cd /d "%~dp0.."

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

REM Install/upgrade build dependencies
echo Installing build dependencies...
python -m pip install --upgrade pip
python -m pip install pyinstaller

REM Run the build
echo.
echo Starting build...
python build.py --clean

if errorlevel 1 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo Build complete! Check the dist/ folder for the executable.
pause
