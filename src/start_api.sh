#!/bin/bash
# ============================================================
# StockAnalyzer API 服务器 —— 一键启动脚本
# 用途：供 iOS App (Stock分析) 调用的 Flask REST 后端
# ============================================================

cd "$(dirname "$0")"

# 1. 设置 Tushare token（macOS 权限问题必须用环境变量）
export TUSHARE_TOKEN="8a12ec4cf932a073f4284fd256cd215d88e10c31b8acce0021174c5c"

# 2. 选择 Python（优先 3.11，因为 akshare/tushare 已装在那个环境）
PYTHON_BIN="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="$(command -v python3.11 || command -v python3)"
fi

# 3. 端口 —— macOS 5000 被 AirPlay 占用，默认 5001
export API_PORT="${API_PORT:-5001}"
export API_HOST="${API_HOST:-0.0.0.0}"

# 4. 杀掉可能残留的旧进程
OLD_PID=$(lsof -ti :"$API_PORT" 2>/dev/null)
if [ -n "$OLD_PID" ]; then
    echo "⚠️  端口 $API_PORT 被 PID=$OLD_PID 占用，先杀掉..."
    kill "$OLD_PID" 2>/dev/null
    sleep 1
fi

# 5. 查 Mac 本机 IP（给 iPhone 用）
MY_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "127.0.0.1")

echo ""
echo "============================================================"
echo "  🚀 StockAnalyzer API 服务器启动中..."
echo "============================================================"
echo "  Python:   $PYTHON_BIN"
echo "  监听端口: $API_PORT"
echo "  本机访问: http://127.0.0.1:$API_PORT"
echo "  手机访问: http://$MY_IP:$API_PORT  ← iPhone 填这个！"
echo "  健康检查: http://$MY_IP:$API_PORT/api/v1/health"
echo "  数据库:   ../data/stock_analysis.db"
echo "============================================================"
echo ""

# 6. 前台启动（保持终端窗口开着，关窗口就停）
"$PYTHON_BIN" api_server.py
