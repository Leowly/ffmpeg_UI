@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

set INSTALL_DIR=%USERPROFILE%\.local\bin
set TEMP_DIR=%TEMP%\ffmpeg_bootstrap
set FFMPEG_URL=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full.7z
set SEVENZIP_URL=https://www.7-zip.org/a/7zr.exe

:: Check uv
where uv >nul 2>&1
if %errorlevel% neq 0 (
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

    where uv >nul 2>&1
    if !errorlevel! neq 0 (
        set "UV_PATH=%USERPROFILE%\.local\bin"
        if exist "!UV_PATH!\uv.exe" (
            set "PATH=!UV_PATH!;!PATH!"
        ) else (
            echo uv installation failed
            pause
            exit /b 1
        )
    )
)

:: Check FFmpeg
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (

    mkdir "%INSTALL_DIR%" >nul 2>nul
    mkdir "%TEMP_DIR%" >nul 2>nul

    set ARCHIVE=%TEMP_DIR%\ffmpeg.7z
    set SEVENZIP=%TEMP_DIR%\7zr.exe

    powershell -Command "Invoke-WebRequest '%FFMPEG_URL%' -OutFile '%ARCHIVE%'"
    if not exist "%ARCHIVE%" (
        echo ffmpeg download failed
        pause
        exit /b 1
    )

    powershell -Command "Invoke-WebRequest '%SEVENZIP_URL%' -OutFile '%SEVENZIP%'"
    if not exist "%SEVENZIP%" (
        echo extractor download failed
        pause
        exit /b 1
    )

    "%SEVENZIP%" x "%ARCHIVE%" -o"%TEMP_DIR%" -y >nul

    del "%INSTALL_DIR%\ffmpeg.exe" >nul 2>&1
    del "%INSTALL_DIR%\ffprobe.exe" >nul 2>&1
    del "%INSTALL_DIR%\ffplay.exe" >nul 2>&1

    for /r "%TEMP_DIR%" %%f in (ffmpeg.exe ffprobe.exe ffplay.exe) do (
        copy "%%f" "%INSTALL_DIR%" >nul
    )

    if not exist "%INSTALL_DIR%\ffmpeg.exe" (
        echo ffmpeg installation failed
        pause
        exit /b 1
    )

    rmdir /s /q "%TEMP_DIR%"
)

uv run --project backend python runtime/run_backend.py

pause