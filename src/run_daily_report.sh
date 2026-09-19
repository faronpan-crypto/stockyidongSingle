#!/bin/bash
# run_daily_report.sh
# 被定时任务调用：生成日报 → 发送到微信
# 用法：./run_daily_report.sh

SCRIPT_DIR="/Users/faronpan/Agent/stockyidong_project/src"
REPORT_DIR="$SCRIPT_DIR/report"
TARGET="o9cq80z54pjdB4tednhGbb3W9pTk@im.wechat"
LOG="/tmp/stockyidong_daily.log"

echo "[$(date)] 开始生成日报..." >> "$LOG"

# 优先使用项目 venv 的 python（含 python-docx），否则回退系统 python3
VENV_PY="$SCRIPT_DIR/../venv/bin/python3"
if [ -x "$VENV_PY" ]; then
    PY="$VENV_PY"
else
    PY="python3"
fi

cd "$SCRIPT_DIR" || exit 1
"$PY" stockyidong_daily_report_v3.py --no-akshare --no-send >> "$LOG" 2>&1
RC=$?
if [ $RC -ne 0 ]; then
    echo "[$(date)] Python 脚本失败，退出码=$RC" >> "$LOG"
    exit 1
fi

# 找最新生成的 docx
LATEST=$(ls -t "$REPORT_DIR"/daily_report_*.docx 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then
    echo "[$(date)] 找不到报告文件" >> "$LOG"
    exit 1
fi

echo "[$(date)] 发送文件: $LATEST" >> "$LOG"
openclaw message send \
    --channel openclaw-weixin \
    -t "$TARGET" \
    --media "$LATEST" \
    >> "$LOG" 2>&1
SEND_RC=$?

if [ $SEND_RC -eq 0 ]; then
    echo "[$(date)] 发送成功" >> "$LOG"
else
    echo "[$(date)] 发送失败，退出码=$SEND_RC" >> "$LOG"
    exit 1
fi

echo "[$(date)] 完成" >> "$LOG"
