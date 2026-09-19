@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 检查虚拟环境
if not exist "venv" (
    echo 正在创建虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 安装依赖
echo 正在安装依赖...
pip install -r requirements.txt -q

REM 启动应用
echo 正在启动股票分析工具...
cd src
python "stockyidong mac.py"
