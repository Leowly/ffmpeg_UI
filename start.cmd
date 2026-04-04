@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

:: Check and create .env if not exists
echo Checking for .env file...
if not exist ".env" (
    if exist ".env.example" (
        :: Copy with UTF-8 encoding using PowerShell
        powershell -Command "Get-Content '.env.example' -Encoding UTF8 | Set-Content '.env' -Encoding UTF8"
        
        :: Generate random SECRET_KEY using PowerShell
        for /f "delims=" %%i in ('powershell -Command "[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes([GUID]::NewGuid().ToString() + [GUID]::NewGuid().ToString())) | Out-String"') do set "RANDOM_SECRET=%%i"
        
        :: Replace SECRET_KEY value in .env with UTF-8 encoding
        powershell -Command "(Get-Content '.env' -Encoding UTF8) -replace 'SECRET_KEY=.*', ('SECRET_KEY=' + '!RANDOM_SECRET!') | Set-Content '.env' -Encoding UTF8"
        
        echo .env file created with random SECRET_KEY
    ) else (
        echo Warning: .env.example not found, skipping .env creation
    )
)

set INSTALL_DIR=%USERPROFILE%\.local\bin
set TEMP_DIR=%TEMP%\ffmpeg_bootstrap

set FFMPEG_URL=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full.7z
set ARIA2_URL=https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip
set SEVENZIP_URL=https://www.7-zip.org/a/7zr.exe

:: Check uv
echo Checking for uv...
where uv >nul 2>&1
if %errorlevel% neq 0 (
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

:: Check FFmpeg
echo Checking for FFmpeg...
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (

    mkdir "%INSTALL_DIR%" >nul 2>nul
    mkdir "%TEMP_DIR%" >nul 2>nul

    cd /d "%TEMP_DIR%"

    powershell -Command "Invoke-WebRequest '%ARIA2_URL%' -OutFile aria2.zip"
    powershell -Command "Expand-Archive aria2.zip -DestinationPath aria2tmp"

    for /r aria2tmp %%f in (aria2c.exe) do copy "%%f" aria2c.exe >nul

    aria2c.exe -x16 -s16 -k1M "%FFMPEG_URL%" -o ffmpeg.7z

    powershell -Command "Invoke-WebRequest '%SEVENZIP_URL%' -OutFile 7zr.exe"

    7zr.exe x ffmpeg.7z -y >nul

    del "%INSTALL_DIR%\ffmpeg.exe" >nul 2>&1
    del "%INSTALL_DIR%\ffprobe.exe" >nul 2>&1
    del "%INSTALL_DIR%\ffplay.exe" >nul 2>&1

    for /r "%TEMP_DIR%" %%f in (ffmpeg.exe ffprobe.exe ffplay.exe) do (
        copy "%%f" "%INSTALL_DIR%" >nul
    )

    del aria2.zip >nul 2>&1
    del aria2c.exe >nul 2>&1
    del ffmpeg.7z >nul 2>&1
    del 7zr.exe >nul 2>&1

    rmdir /s /q aria2tmp >nul 2>&1
    rmdir /s /q "%TEMP_DIR%" >nul 2>&1

    cd /d "%~dp0"
)

cd /d "%~dp0backend" && uv run python -m app.main

pause
