@echo off
REM Walrio GUI Build Script for Windows
REM Copyright (c) 2025 TAPS OSS
REM Project: https://github.com/TAPSOSS/Walrio
REM Licensed under the BSD-3-Clause License (see LICENSE file for details)

setlocal enabledelayedexpansion

echo.
echo Walrio GUI Build Script for Windows
echo ===================================

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9+ and try again
    pause
    exit /b 1
)

REM Parse command line arguments
set GUI_TYPE=both
set CLEAN_BUILD=0
set DEBUG_MODE=0
set SKIP_DEPS=0

:parse_args
if "%1"=="" goto end_parse
if "%1"=="--main" set GUI_TYPE=main
if "%1"=="--lite" set GUI_TYPE=lite
if "%1"=="--both" set GUI_TYPE=both
if "%1"=="--clean" set CLEAN_BUILD=1
if "%1"=="--debug" set DEBUG_MODE=1
if "%1"=="--skip-deps" set SKIP_DEPS=1
if "%1"=="--help" goto show_help
shift
goto parse_args
:end_parse

REM Build the command
set BUILD_CMD=python build_gui.py --gui %GUI_TYPE%

if %CLEAN_BUILD%==1 (
    set BUILD_CMD=!BUILD_CMD! --clean
)

if %DEBUG_MODE%==1 (
    set BUILD_CMD=!BUILD_CMD! --debug
)

if %SKIP_DEPS%==1 (
    set BUILD_CMD=!BUILD_CMD! --no-deps-check
)

echo.
echo Building Walrio GUIs...
echo Command: !BUILD_CMD!
echo.

REM Execute the build
!BUILD_CMD!

if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo Build completed successfully!
    echo.
    echo Output files are in the 'dist' directory:
    if exist "dist\WalrioMain.exe" echo   - WalrioMain.exe
    if exist "dist\WalrioLite.exe" echo   - WalrioLite.exe
    echo.
    echo You can now run the applications directly.
    echo ============================================
) else (
    echo.
    echo ============================================
    echo Build failed! Check the error messages above.
    echo ============================================
)

pause
exit /b %errorlevel%

:show_help
echo.
echo Usage: %0 [options]
echo.
echo Options:
echo   --main      Build only WalrioMain
echo   --lite      Build only WalrioLite  
echo   --both      Build both applications (default)
echo   --clean     Clean build directories first
echo   --debug     Build in debug mode (onedir)
echo   --skip-deps Skip dependency checking
echo   --help      Show this help message
echo.
echo Examples:
echo   %0                    Build both applications
echo   %0 --main --clean     Clean build and build only WalrioMain
echo   %0 --lite --debug     Build WalrioLite in debug mode
echo.
pause
exit /b 0