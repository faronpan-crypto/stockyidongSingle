"""
程序入口 — 只负责导入 App 并启动 mainloop

迁移状态: 📋 占位骨架 — 当前 main() 仍在 stockyidong mac003.py

用法: python3 main.py
"""

import sys
import os

# 确保 src 目录在 sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def main():
    """入口: 导入 App 类并启动"""
    from app import App
    App().run()


if __name__ == "__main__":
    main()
