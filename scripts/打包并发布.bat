@echo off
chcp 65001 >nul
title Build StockAnalyzer EXE
color 0B
cd /d "%~dp0"

echo.
echo ========================================
echo   Build and Publish StockAnalyzer
echo ========================================
echo.

REM Python: use .venv if exists, else system python
set "PY=python"
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
    echo [INFO] Using .venv
) else (
    echo [INFO] Using system Python
)
echo.

REM Step 1: clean
echo [Step 1/4] Clean old build...
if exist build rmdir /s /q build 2>nul
if exist dist rmdir /s /q dist 2>nul
echo   Done.
echo.

REM Step 2: PyInstaller
echo [Step 2/4] PyInstaller build...
echo   Wait 5-15 min, do not close.
echo.
"%PY%" -m PyInstaller --clean --noconfirm stockyidong.spec
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. See output above.
    pause
    exit /b 1
)
echo.
echo [OK] Build success.
echo.

REM Step 3: find output folder (spec outputs to dist\XXX, one folder)
set "OUTDIR="
for /f "delims=" %%i in ('dir /b /ad dist 2^>nul') do (
    if not defined OUTDIR set "OUTDIR=dist\%%i"
)
if not defined OUTDIR (
    echo [WARN] No folder under dist. Check build.
    pause
    exit /b 0
)

REM exe is same name as folder (from spec name=...)
for %%i in ("%OUTDIR%") do set "FNAME=%%~ni"
set "EXE=%OUTDIR%\%FNAME%.exe"
if not exist "%EXE%" (
    echo [WARN] EXE not found: %EXE%
    pause
    exit /b 0
)

REM Step 4: zip for release
echo [Step 3/4] Create release zip...
set "ZIPNAME=StockAnalyzer_Release"
set "ZIPPATH=dist\%ZIPNAME%.zip"
powershell -NoProfile -Command "Compress-Archive -LiteralPath '%CD%\%OUTDIR%' -DestinationPath '%CD%\%ZIPPATH%' -Force" 2>nul
if exist "%ZIPPATH%" (
    echo   Created: %ZIPPATH%
) else (
    echo   (Zip failed or no PowerShell - zip folder %OUTDIR% by hand)
)
echo.

echo [Step 4/4] Done.
echo.
echo ========================================
echo   Result
echo ========================================
echo   EXE:  %CD%\%EXE%
echo   ZIP:  %CD%\%ZIPPATH%
echo.
echo   Run: double-click the exe in %OUTDIR%
echo   Share: send %ZIPNAME%.zip, extract and run exe
echo   Keep the whole folder, do not copy exe alone.
echo ========================================
echo.
pause
