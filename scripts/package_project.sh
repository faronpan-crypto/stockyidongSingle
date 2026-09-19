#!/bin/bash
# ============================================
# 股票分析工具打包脚本
# 运行此脚本将项目打包为可复制的压缩包
# ============================================

set -e

PROJECT_NAME="stockyidong_project"
CURRENT_DIR=$(pwd)
PROJECT_DIR=$(cd "$(dirname "$0")/.." && pwd)
DIST_DIR="$PROJECT_DIR/dist"
ZIP_NAME="stockyidong_portable_$(date +%Y%m%d_%H%M%S).zip"

echo "============================================"
echo "开始打包股票分析工具..."
echo "项目目录: $PROJECT_DIR"
echo "输出目录: $DIST_DIR"
echo "============================================"

# 创建输出目录
mkdir -p "$DIST_DIR"

# 复制项目文件到临时目录
BUILD_DIR="$DIST_DIR/build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

echo "正在复制项目文件..."

# 复制核心源代码
cp -r "$PROJECT_DIR/src" "$BUILD_DIR/"

# 复制配置文件
cp -r "$PROJECT_DIR/config" "$BUILD_DIR/"

# 复制数据目录（不包含数据库文件）
mkdir -p "$BUILD_DIR/data"
cp -f "$PROJECT_DIR/data/stock_analysis.db" "$BUILD_DIR/data/" 2>/dev/null || true

# 复制脚本
cp -r "$PROJECT_DIR/scripts" "$BUILD_DIR/"

# 复制依赖文件
cp "$PROJECT_DIR/requirements.txt" "$BUILD_DIR/"
cp "$PROJECT_DIR/README.md" "$BUILD_DIR/"

# 创建启动脚本
cat > "$BUILD_DIR/start.sh" << 'EOF'
#!/bin/bash
# 股票分析工具启动脚本（macOS/Linux）

cd "$(dirname "$0")"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "正在创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "正在安装依赖..."
pip install -r requirements.txt -q

# 启动应用
echo "正在启动股票分析工具..."
cd src
python "stockyidong mac.py"
EOF

chmod +x "$BUILD_DIR/start.sh"

# 创建 Windows 启动脚本
cat > "$BUILD_DIR/start.bat" << 'EOF'
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
EOF

# 创建部署说明
cat > "$BUILD_DIR/DEPLOYMENT.md" << 'EOF'
# 股票分析工具 - 部署说明

## 环境要求
- Python 3.8+
- macOS 10.15+ 或 Windows 10+

## 部署步骤

### macOS/Linux
1. 解压压缩包
2. 打开终端，进入解压目录
3. 运行启动脚本：
   ```bash
   chmod +x start.sh
   ./start.sh
   ```

### Windows
1. 解压压缩包
2. 双击运行 start.bat
3. 等待虚拟环境创建和依赖安装完成

## 首次运行
- 首次运行会自动创建虚拟环境并安装依赖
- 安装过程可能需要几分钟，请耐心等待
- 依赖安装完成后会自动启动应用

## 目录结构
```
stockyidong_project/
├── src/           # 源代码
├── config/        # 配置文件
├── data/          # 数据库文件
├── scripts/       # 辅助脚本
├── requirements.txt  # 依赖列表
├── start.sh       # macOS/Linux 启动脚本
├── start.bat      # Windows 启动脚本
└── DEPLOYMENT.md  # 部署说明
```

## 注意事项
1. 确保目标电脑已安装 Python 3.8+
2. 首次运行需要联网下载依赖
3. 建议使用 Python 虚拟环境避免依赖冲突
4. 如果遇到权限问题，请确保脚本有执行权限

## 卸载
只需删除整个项目目录即可

EOF

# 打包为 zip
echo "正在创建压缩包..."
cd "$DIST_DIR"
zip -r "$ZIP_NAME" "build"

# 清理临时文件
rm -rf "$BUILD_DIR"

echo "============================================"
echo "打包完成！"
echo "压缩包位置: $DIST_DIR/$ZIP_NAME"
echo "============================================"

echo ""
echo "部署说明:"
echo "1. 将压缩包复制到目标电脑"
echo "2. 解压压缩包"
echo "3. 根据操作系统运行对应的启动脚本"
echo "4. 首次运行会自动创建虚拟环境并安装依赖"
