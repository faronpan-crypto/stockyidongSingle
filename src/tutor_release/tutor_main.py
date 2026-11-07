# -*- coding: utf-8 -*-
"""🦊 家教辅导小助手 — 独立可执行程序
用法: python3 tutor_main.py
打包: pyinstaller --noconfirm --windowed --name "家教辅导小助手" tutor_main.py
"""
import sys
import os

# 确保能找到 ui.tutor_helper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from ui.tutor_helper import _show_tutor_helper


def main():
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口, 直接弹家教界面
    _show_tutor_helper(root)
    root.mainloop()


if __name__ == "__main__":
    main()
