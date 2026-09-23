#!/bin/bash
# ===== stockyidong venv 环境一键检查脚本 =====
# 在 pandamini 和 pro 上分别运行:  bash venv_check.sh
#
# 核心要求 (mac-mini 基线):
#   Python:       3.11.15 (系统 brew 3.11 也可用)
#   mini-racer:   0.7.0  ← 关键! 0.14.1 会 V8 初始化崩溃
#   akshare:      1.18.xx
#   tushare:      1.4.29
#   TUSHARE_TOKEN: 环境变量必须设

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo "========== stockyidong venv 环境检查 =========="
echo "时间: $(date)"
echo "机器: $(hostname)"
echo ""

# 找 venv
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="$PROJECT_DIR/venv/bin/python"
if [ ! -f "$VENV_PY" ]; then
    echo -e "${RED}❌ 未找到 venv: $VENV_PY${NC}"
    echo "   项目目录: $PROJECT_DIR"
    echo "   检查项目下有没有 venv/ 或 .venv/"
    ls -d "$PROJECT_DIR"/venv* "$PROJECT_DIR"/.venv* 2>/dev/null || echo "   没有任何 venv 目录!"
    exit 1
fi

echo "✅ venv Python: $VENV_PY"
echo ""

# 1. Python 版本
echo "【1. Python 版本】"
PY_VER=$($VENV_PY -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
echo "   $PY_VER"
if [[ "$PY_VER" == 3.11.* ]]; then
    echo -e "   ${GREEN}✅ 3.11.x OK${NC}"
else
    echo -e "   ${YELLOW}⚠️ 建议 3.11.x, 当前 $PY_VER${NC}"
fi

# 2. mini-racer (关键!)
echo ""
echo "【2. mini-racer 版本 (必须 0.7.0!)】"
MR_VER=$($VENV_PY -m pip show mini-racer 2>/dev/null | grep "^Version:" | awk '{print $2}')
if [ -z "$MR_VER" ]; then
    echo -e "   ${RED}❌ mini-racer 未安装!${NC}"
    echo "   修复: $VENV_PY -m pip install mini-racer==0.7.0"
else
    echo "   当前: $MR_VER"
    if [ "$MR_VER" = "0.7.0" ]; then
        echo -e "   ${GREEN}✅ 完美!${NC}"
    else
        echo -e "   ${RED}❌ 版本不对! 0.14.1 会 V8 崩溃!${NC}"
        echo "   修复: $VENV_PY -m pip install mini-racer==0.7.0"
    fi
fi

# 3. akshare / tushare
echo ""
echo "【3. akshare + tushare】"
AK_VER=$($VENV_PY -c "import akshare; print(akshare.__version__)" 2>/dev/null || echo "MISSING")
TS_VER=$($VENV_PY -c "import tushare; print(tushare.__version__)" 2>/dev/null || echo "MISSING")
echo "   akshare: $AK_VER"
echo "   tushare: $TS_VER"
[ "$AK_VER" = "MISSING" ] && echo -e "   ${RED}❌ akshare 缺失${NC}" || echo -e "   ${GREEN}✅ akshare OK${NC}"
[ "$TS_VER" = "MISSING" ] && echo -e "   ${RED}❌ tushare 缺失${NC}" || echo -e "   ${GREEN}✅ tushare OK${NC}"

# 4. TUSHARE_TOKEN
echo ""
echo "【4. TUSHARE_TOKEN】"
if [ -z "$TUSHARE_TOKEN" ]; then
    echo -e "   ${RED}❌ 环境变量 TUSHARE_TOKEN 未设置!${NC}"
    echo "   当前 shell:"
    echo "     export TUSHARE_TOKEN=你的token"
    echo "   持久化: 写入 ~/.zshrc 或 ~/.bash_profile"
else
    echo -e "   ${GREEN}✅ 已设置${NC} (${TUSHARE_TOKEN:0:15}...)"
fi

# 5. API 冒烟测试 (不联网也能测 import)
echo ""
echo "【5. API 冒烟测试 (联网)】"
echo -n "   akshare stock_zh_index_daily... "
if timeout 10 $VENV_PY -u -c "
import akshare as ak, pandas as pd
df = ak.stock_zh_index_daily(symbol='sh000001')
df['date'] = pd.to_datetime(df['date'])
df = df.tail(1)
print(f'✅ {len(df)}行, 最新={df.iloc[-1][\"date\"].strftime(\"%Y-%m-%d\")}')
" 2>/dev/null; then
    echo -e "   ${GREEN}✅ 上证日线 OK${NC}"
else
    echo -e "   ${RED}❌ 失败 (网络/反爬)${NC}"
fi

echo -n "   tushare trade_cal... "
if timeout 10 $VENV_PY -u -c "
import os, tushare as ts
pro = ts.pro_api()
df = pro.trade_cal(exchange='SSE', start_date='20260920', end_date='20260924', is_open='1')
print(f'✅ {len(df)}行')
" 2>/dev/null; then
    echo -e "   ${GREEN}✅ trade_cal OK${NC}"
else
    echo -e "   ${RED}❌ 失败 (Token/熔断)${NC}"
fi

# 6. Git 仓库
echo ""
echo "【6. Git 仓库状态】"
cd "$PROJECT_DIR"
if [ -d ".git" ]; then
    echo "   分支: $(git branch --show-current)"
    echo "   远程: $(git remote -v 2>/dev/null | head -2)"
    LATEST=$(git log --oneline -1 2>/dev/null)
    echo "   最新 commit: $LATEST"
    echo ""
    echo -n "   需要 pull 吗? "
    BEHIND=$(git fetch github-mac003 2>/dev/null; git rev-list --count HEAD..github-mac003/main 2>/dev/null || echo "?")
    if [ "$BEHIND" = "?" ]; then
        echo -e "   ${YELLOW}⚠️ 无法判断 (remote 可能不同)${NC}"
    elif [ "$BEHIND" -eq 0 ]; then
        echo -e "   ${GREEN}✅ 已是最新${NC}"
    else
        echo -e "   ${RED}❌ 落后 $BEHIND 个 commit!${NC}"
        echo "   修复: git pull github-mac003 main"
    fi
else
    echo "   ${YELLOW}⚠️ 不是 git 仓库${NC}"
fi

echo ""
echo "========== 检查完成 =========="
echo ""
echo "如需一键修复 mini-racer:"
echo "  $VENV_PY -m pip install mini-racer==0.7.0"
echo ""
echo "如需 pull 最新代码:"
echo "  cd $PROJECT_DIR && git pull github-mac003 main"
