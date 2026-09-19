#!/usr/bin/env python3
import os
import sys

# 设置环境变量
if sys.platform == "darwin":
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

# 先设置 matplotlib
print("Step 1: Setting up matplotlib...")
import matplotlib

matplotlib.use('TkAgg')

# 模拟股票程序的导入
print("Step 2: Importing modules...")
import tkinter as tk
from tkinter import ttk

try:
    import akshare as ak
    print("  akshare imported")
except ImportError:
    pass

import matplotlib

print("Step 3: Creating window...")
root = tk.Tk()
root.title("Test with imports")
root.geometry("400x300")

label = ttk.Label(root, text="Imports test successful!")
label.pack(pady=20)

button = ttk.Button(root, text="Click Me", command=lambda: print("Button clicked"))
button.pack(pady=10)

print("Step 4: Starting mainloop...")
print("Window should be visible now!")
root.mainloop()
