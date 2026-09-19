#!/usr/bin/env python3
import os
import sys
import time

# 设置环境变量
if sys.platform == "darwin":
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

print("Step 1: Testing pure Tkinter without stockyidong module")
print(f"Python version: {sys.version}")
print(f"Platform: {sys.platform}")

print("\nStep 2: Importing Tkinter")
import tkinter as tk
from tkinter import ttk

print("\nStep 3: Creating Tkinter window")
root = tk.Tk()
print("✓ Created Tk root")
print(f"Root exists: {root.winfo_exists()}")

root.title("Pure Tkinter Test")
root.geometry("400x300")
print("✓ Set title and geometry")

label = ttk.Label(root, text="Pure Tkinter Test")
label.pack(pady=20)
print("✓ Added label")

button = ttk.Button(root, text="Click Me", command=lambda: print("Button clicked"))
button.pack(pady=10)
print("✓ Added button")

print("\nStep 4: Testing update()")
print(f"Before update - Root exists: {root.winfo_exists()}")
start_time = time.time()
root.update()
elapsed = time.time() - start_time
print(f"✓ update() completed in {elapsed:.2f} seconds")
print(f"After update - Root exists: {root.winfo_exists()}")

print("\nStep 5: Testing update_idletasks()")
start_time = time.time()
root.update_idletasks()
elapsed = time.time() - start_time
print(f"✓ update_idletasks() completed in {elapsed:.2f} seconds")
print(f"After update_idletasks - Root exists: {root.winfo_exists()}")

print("\n✓ All basic operations successful!")
print("Starting main loop...")

root.mainloop()

print("\nProgram completed successfully")