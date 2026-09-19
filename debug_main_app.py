#!/usr/bin/env python3
import os
import sys
import time

# 设置环境变量
if sys.platform == "darwin":
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

os.environ["STOCK_ANALYZER_DATA_DIR"] = os.path.join(os.path.expanduser("~"), "StockAnalyzer")
os.makedirs(os.environ["STOCK_ANALYZER_DATA_DIR"], exist_ok=True)

print("=== Step 1: Importing stockyidong module ===")
import importlib.util

spec = importlib.util.spec_from_file_location("stockyidong", "src/stockyidong mac.py")
stockyidong = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stockyidong)
print("✓ Module loaded")

print("\n=== Step 2: Creating Tkinter root ===")
root = stockyidong.tk.Tk()
root.title("Stock Analyzer Debug")
root.geometry("1580x940")

print(f"Root created: {root}")
print(f"Root exists: {root.winfo_exists()}")
print(f"Root visible: {root.winfo_viewable()}")

# 显示窗口
root.deiconify()
root.lift()
root.focus_force()

print(f"After deiconify - visible: {root.winfo_viewable()}")
print(f"After deiconify - mapped: {root.winfo_ismapped()}")

print("\n=== Step 3: Creating GUI instance ===")
start_time = time.time()

try:
    app = stockyidong.StockKeywordAnalyzerGUI(root)
    elapsed = time.time() - start_time
    print(f"✓ GUI created in {elapsed:.2f} seconds")
    
    print("\n=== Step 4: Checking window status after GUI creation ===")
    print(f"Root exists: {root.winfo_exists()}")
    print(f"Root visible: {root.winfo_viewable()}")
    print(f"Root mapped: {root.winfo_ismapped()}")
    
    # 检查子控件数量
    children = root.winfo_children()
    print(f"Number of top-level children: {len(children)}")
    
except Exception as e:
    elapsed = time.time() - start_time
    print(f"✗ GUI creation failed after {elapsed:.2f} seconds: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n=== Step 5: Starting mainloop ===")
root.after(10000, root.quit)  # 运行10秒后退出
root.mainloop()

print("\n=== Done ===")
