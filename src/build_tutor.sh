#!/bin/bash
# 🦊 家教辅导小助手 — 一键打包脚本 (macOS)
# 在 pandamacmini 上执行: bash build_tutor.sh
set -e

cd "$(dirname "$0")"

echo "═══ 🦊 家教辅导小助手 打包 ═══"

# 1. 检查 Python
if ! command -v python3 &>/dev/null; then
    echo "❌ 需要 python3"
    exit 1
fi
PY=$(which python3)
echo "✅ Python: $($PY --version)"

# 2. 创建虚拟环境 + 装 PyInstaller
if [ ! -d "venv" ]; then
    echo "📦 创建 venv..."
    $PY -m venv venv
fi
source venv/bin/activate

pip install --quiet pyinstaller 2>/dev/null || pip install pyinstaller

# 3. 打包
rm -rf build dist *.spec

pyinstaller \
  --noconfirm \
  --windowed \
  --onefile \
  --name "家教辅导小助手" \
  --hidden-import tkinter \
  --hidden-import tkinter.ttk \
  --hidden-import tkinter.scrolledtext \
  tutor_main.py

echo ""
echo "═══ ✅ 打包完成 ═══"
ls -lh dist/家教辅导小助手.app
echo ""
echo "📂 App 位置: $(pwd)/dist/家教辅导小助手.app"
echo "🖱️  双击打开即可使用"
