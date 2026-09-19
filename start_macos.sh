#!/bin/bash
# 股票分析工具启动脚本 (macOS)

cd "$(dirname "$0")"

# 设置 TCL/TK 环境变量
export TCL_LIBRARY=/opt/homebrew/Cellar/tcl-tk@8/8.6.18/lib/tcl8.6
export TK_LIBRARY=/opt/homebrew/Cellar/tcl-tk@8/8.6.18/lib/tk8.6
export DYLD_FALLBACK_FRAMEWORK_PATH=/opt/homebrew/Cellar/tcl-tk@8/8.6.18
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/Cellar/tcl-tk@8/8.6.18/lib

# 使用系统已安装 tushare 的 Python 3.11（不使用 venv，避免虚拟环境缺包导致K线获取失败）
PYTHON_BIN="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
    # 回退：尝试 homebrew 的 python3.11
    PYTHON_BIN="$(command -v python3.11 || command -v python3)"
fi
echo "使用 Python: $PYTHON_BIN"
"$PYTHON_BIN" --version

# 设置 Tushare token 环境变量（避免 ts.set_token 写主目录 tk.csv 的权限问题）
export TUSHARE_TOKEN="8a12ec4cf932a073f4284fd256cd215d88e10c31b8acce0021174c5c"

# 启动应用
echo "正在启动股票分析工具..."
"$PYTHON_BIN" "src/stockyidong mac.py"
