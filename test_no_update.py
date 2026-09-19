#!/usr/bin/env python3
import os
import sys

# 设置环境变量
if sys.platform == "darwin":
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

print("Step 1: Testing Tkinter without update()")
print(f"Python version: {sys.version}")
print(f"Platform: {sys.platform}")

print("\nStep 2: Importing Tkinter")
import tkinter as tk
from tkinter import ttk

print("\nStep 3: Creating Tkinter window")
root = tk.Tk()
print("✓ Created Tk root")
print(f"Root exists: {root.winfo_exists()}")

root.title("Tkinter Test - No Update")
root.geometry("400x300")
print("✓ Set title and geometry")

label = ttk.Label(root, text="Tkinter Test - No Update")
label.pack(pady=20)
print("✓ Added label")

button = ttk.Button(root, text="Click Me", command=lambda: print("Button clicked"))
button.pack(pady=10)
print("✓ Added button")

print("\n✓ All widgets added successfully!")
print("Starting main loop...")

root.mainloop()

print("\nProgram completed successfully")