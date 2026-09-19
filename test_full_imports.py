import os
import sys

print("Python version:", sys.version)
print("Platform:", sys.platform)

# 按顺序导入库，看看哪个会出问题
try:
    print("Importing tkinter...")
    import tkinter as tk
    from tkinter import ttk
    print("✓ tkinter")
except Exception as e:
    print(f"✗ tkinter: {e}")

try:
    print("Importing requests...")
    print("✓ requests")
except Exception as e:
    print(f"✗ requests: {e}")

try:
    print("Importing re...")
    print("✓ re")
except Exception as e:
    print(f"✗ re: {e}")

try:
    print("Importing jieba...")
    print("✓ jieba")
except Exception as e:
    print(f"✗ jieba: {e}")

try:
    print("Importing akshare...")
    print("✓ akshare")
except Exception as e:
    print(f"✗ akshare: {e}")

try:
    print("Importing pandas...")
    print("✓ pandas")
except Exception as e:
    print(f"✗ pandas: {e}")

try:
    print("Importing PIL...")
    print("✓ PIL")
except Exception as e:
    print(f"✗ PIL: {e}")

try:
    print("Importing matplotlib...")
    print("✓ matplotlib")
except Exception as e:
    print(f"✗ matplotlib: {e}")

try:
    print("Importing wordcloud...")
    print("✓ wordcloud")
except Exception as e:
    print(f"✗ wordcloud: {e}")

print("\nAll imports completed!")

# 现在创建窗口
try:
    print("\nCreating Tkinter window...")
    if sys.platform == "darwin":
        os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
    
    root = tk.Tk()
    root.title("Test with All Imports")
    root.geometry("400x300")
    
    label = ttk.Label(root, text="All imports successful!")
    label.pack(pady=20)
    
    button = ttk.Button(root, text="OK", command=root.destroy)
    button.pack(pady=10)
    
    root.update()
    print("✓ Window created successfully")
    
    root.mainloop()
    
except Exception as e:
    import traceback
    print(f"Error creating window: {e}")
    traceback.print_exc()