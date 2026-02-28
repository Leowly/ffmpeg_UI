@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

:: Check FFmpeg
echo [1/3] Checking FFmpeg...
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] FFmpeg not found. Please install FFmpeg first.
    echo.
    echo Opening FFmpeg download page...
    start https://ffmpeg.org/download.html
    echo.
    echo Please download FFmpeg, add it to PATH, then run this script again.
    echo.
    pause
    exit /b 1
)
echo       FFmpeg OK

:: Check uv
echo.
echo [2/3] Checking uv...
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo       uv not found, installing...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    
    :: Refresh environment
    where uv >nul 2>&1
    if !errorlevel! neq 0 (
        :: Try user profile path
        set "UV_PATH=%USERPROFILE%\.local\bin"
        if exist "!UV_PATH!\uv.exe" (
            set "PATH=!UV_PATH!;!PATH!"
        ) else (
            echo.
            echo [ERROR] uv installation failed. Please install manually:
            echo        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
            pause
            exit /b 1
        )
    )
)
echo       uv OK

:: Start backend
echo.
echo [3/3] Starting server...
echo ========================================
echo.

uv run --project backend python runtime/run_backend.py

pause
