#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🦊 家教辅导小助手 — 独立启动入口

用法:
  python3 tutor_launch.py            ← 直接运行
  python3 tutor_launch.py --debug    ← 调试模式 (显示控制台)

打包:
  pyinstaller tutor.spec

发布:
  cp -R dist/家教辅导小助手.app ~/Desktop/
"""

import sys
import os

# 把 src 加进 path
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import tkinter as tk
from ui.tutor_helper import _show_tutor_helper


def main():
    root = tk.Tk()
    root.title("🦊 家教辅导小助手")
    root.geometry("400x300")
    root.configure(bg="#FFF8F0")

    # 先显示一个简单欢迎窗, 点击按钮进入完整界面
    from ui.tutor_helper import PALETTE
    tk.Label(root, text="🦊", font=("Arial", 64),
             bg=PALETTE["bg"]).pack(pady=(30, 6))
    tk.Label(root, text="家教辅导小助手",
             font=("Comic Sans MS", 22, "bold"),
             bg=PALETTE["bg"], fg=PALETTE["pink_dark"]).pack()
    tk.Label(root, text="📚 题库 📝 出题 👨‍🏫 AI批改 📅 历史",
             font=("Arial", 11), bg=PALETTE["bg"], fg="#6B7280").pack(pady=(4, 18))

    def _enter():
        root.destroy()
        # 完整界面是 Toplevel, 我们需要一个隐藏的 root 当父
        main_root = tk.Tk()
        main_root.withdraw()
        _show_tutor_helper(main_root)
        main_root.mainloop()

    tk.Button(root, text="🚀 开始使用", font=("Arial", 14, "bold"),
              bg=PALETTE["pink_dark"], fg="white",
              relief="flat", padx=30, pady=8,
              cursor="hand2", command=_enter).pack()

    tk.Label(root, text="(首次使用请先配置 deepseek API)",
             font=("Arial", 9), bg=PALETTE["bg"], fg="#9CA3AF").pack(pady=(20, 0))

    root.mainloop()


if __name__ == "__main__":
    main()
