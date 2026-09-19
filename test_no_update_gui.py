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
import importlib.util

spec = importlib.util.spec_from_file_location("stockyidong", "src/stockyidong mac.py")
stockyidong = importlib.util.module_from_spec(spec)

print("Step 3: Executing module...")
try:
    spec.loader.exec_module(stockyidong)
    print("✓ Module loaded successfully")
except Exception as e:
    print(f"✗ Failed to load module: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nStep 4: Creating Tkinter root")
try:
    root = stockyidong.tk.Tk()
    print("✓ Created Tk root")
    print(f"Root exists: {root.winfo_exists()}")
    
    root.title("Stock Analyzer Test")
    root.geometry("800x600")
    
except Exception as e:
    print(f"✗ Failed to create root: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nStep 5: Testing StockKeywordAnalyzerGUI initialization")
start_time = time.time()

print("  - Creating StockKeywordAnalyzerGUI instance...")
try:
    app = stockyidong.StockKeywordAnalyzerGUI(root)
    elapsed = time.time() - start_time
    print(f"✓ Created GUI successfully in {elapsed:.2f} seconds")
except Exception as e:
    elapsed = time.time() - start_time
    print(f"✗ Failed to create GUI after {elapsed:.2f} seconds: {e}")
    import traceback
    traceback.print_exc()
    try:
        root.destroy()
    except:
        pass
    sys.exit(1)

print("\nStep 6: Starting main loop")
root.mainloop()

print("\nProgram completed successfully")
