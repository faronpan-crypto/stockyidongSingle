@echo off

rem 启动股票异动分析系统
cd "%~dp0src"

rem 检查Python环境是否存在
if exist "..\.venv\Scripts\python.exe" (
    echo 使用虚拟环境运行...
    "..\.venv\Scripts\python.exe" "stockyidong mac.py"
) else (
    echo 虚拟环境不存在，使用系统Python运行...
    python "stockyidong mac.py"
)

pause
