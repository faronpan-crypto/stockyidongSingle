#!/usr/bin/env python3
import os
import sys

# 设置环境变量
if sys.platform == "darwin":
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

print("Step 1: Importing Tkinter...")
import tkinter as tk
from tkinter import ttk

print("Step 2: Creating root window...")
root = tk.Tk()
print(f"  Root created, exists: {root.winfo_exists()}")

print("Step 3: Setting window properties...")
try:
    root.title("Test Window")
    root.geometry("400x300")
    print("  Window properties set")
except Exception as e:
    print(f"  Error setting properties: {e}")

print("Step 4: Adding widgets...")
try:
    label = ttk.Label(root, text="Hello World!")
    label.pack(pady=20)
    button = ttk.Button(root, text="Click Me", command=lambda: print("Button clicked"))
    button.pack(pady=10)
    print("  Widgets added")
except Exception as e:
    print(f"  Error adding widgets: {e}")

print("Step 5: Showing window...")
try:
    root.deiconify()
    root.lift()
    print("  Window shown")
except Exception as e:
    print(f"  Error showing window: {e}")

print("Step 6: Starting mainloop...")
print("Window should be visible now!")
root.mainloop()
print("Program completed")
