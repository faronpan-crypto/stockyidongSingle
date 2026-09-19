@echo off

chcp 65001 >nul 2>&1

set "REPO_ROOT=%~dp0..\.."

if not exist "%~dp0..\src\stockyidong.py" (

  echo [ERROR] stockyidong.py not found

  pause

  exit /b 1

)

cd /d "%~dp0..\src"

python -m py_compile stockyidong.py

if errorlevel 1 ( pause & exit /b 1 )

cd /d "%REPO_ROOT%"

if exist build rmdir /s /q build 2>nul

if exist dist rmdir /s /q dist 2>nul

pyinstaller --clean --noconfirm stockyidong.spec

if errorlevel 1 ( pause & exit /b 1 )

echo Build OK

pause

