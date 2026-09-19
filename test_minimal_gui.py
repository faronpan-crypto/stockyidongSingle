#!/usr/bin/env python3
import os
import sys

# 设置环境变量
if sys.platform == "darwin":
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

print("Step 1: Creating simple Tkinter window")
import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("Simple Test")
root.geometry("400x300")

print("Step 2: Creating frame")
frame = ttk.Frame(root)
frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

print("Step 3: Creating buttons")
btn1 = ttk.Button(frame, text="Button 1")
btn1.pack(side=tk.LEFT, padx=5)

btn2 = ttk.Button(frame, text="Button 2")
btn2.pack(side=tk.LEFT, padx=5)

btn3 = ttk.Button(frame, text="Button 3")
btn3.pack(side=tk.LEFT, padx=5)

print("Step 4: Creating entry")
entry = ttk.Entry(frame)
entry.pack(side=tk.LEFT, padx=5)

print("Step 5: Showing window")
root.deiconify()
root.lift()
root.focus_force()

print("Step 6: Starting mainloop")
root.mainloop()
print("Done")
