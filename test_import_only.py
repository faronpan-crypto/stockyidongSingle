#!/usr/bin/env python3
import os
import sys
import time

# 设置环境变量
if sys.platform == "darwin":
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

print("Step 1: Setting up environment")
print(f"Python version: {sys.version}")
print(f"Platform: {sys.platform}")

# 设置数据目录环境变量
os.environ["STOCK_ANALYZER_DATA_DIR"] = os.path.join(os.path.expanduser("~"), "StockAnalyzer")
print(f"STOCK_ANALYZER_DATA_DIR: {os.environ['STOCK_ANALYZER_DATA_DIR']}")

# 确保目录存在
os.makedirs(os.environ["STOCK_ANALYZER_DATA_DIR"], exist_ok=True)

print("\nStep 2: Importing stockyidong module")
start_time = time.time()
import importlib.util

spec = importlib.util.spec_from_file_location("stockyidong", "src/stockyidong mac.py")
stockyidong = importlib.util.module_from_spec(spec)

print("Step 3: Executing module...")
try:
    spec.loader.exec_module(stockyidong)
    elapsed = time.time() - start_time
    print(f"✓ Module loaded successfully in {elapsed:.2f} seconds")
except Exception as e:
    print(f"✗ Failed to load module: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nStep 4: Creating simple Tkinter window")
try:
    root = stockyidong.tk.Tk()
    print("✓ Created Tk root")
    print(f"Root exists: {root.winfo_exists()}")
    
    root.title("Simple Test Window")
    root.geometry("400x300")
    
    label = stockyidong.ttk.Label(root, text="Hello World!")
    label.pack(pady=20)
    
    button = stockyidong.ttk.Button(root, text="Click Me", command=lambda: print("Button clicked"))
    button.pack(pady=10)
    
    print("✓ Added widgets")
    print(f"Root still exists before update: {root.winfo_exists()}")
    
    root.update()
    print(f"✓ After update - Root still exists: {root.winfo_exists()}")
    
    root.update_idletasks()
    print(f"✓ After update_idletasks - Root still exists: {root.winfo_exists()}")
    
    print("\n✓ All basic operations successful!")
    
    root.mainloop()
    
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    try:
        root.destroy()
    except:
        pass
    sys.exit(1)