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

