@echo off

chcp 65001 >nul

cd /d "%~dp0..\src"

chcp 65001 >nul
python stockyidong.py
if errorlevel 1 (
    echo.
    echo 程序运行出错，请检查Python环境是否正确安装
    pause
)

