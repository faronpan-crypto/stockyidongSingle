#!/usr/bin/env python3
import os
import sys

# 设置环境变量
if sys.platform == "darwin":
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

print("Step 1: Setting up environment")
print(f"Python version: {sys.version}")
print(f"Platform: {sys.platform}")

# 设置数据目录环境变量
os.environ["STOCK_ANALYZER_DATA_DIR"] = os.path.join(os.path.expanduser("~"), "StockAnalyzer")
os.makedirs(os.environ["STOCK_ANALYZER_DATA_DIR"], exist_ok=True)

print("\nStep 2: Importing stockyidong module")
import importlib.util

spec = importlib.util.spec_from_file_location("stockyidong", "src/stockyidong mac.py")
stockyidong = importlib.util.module_from_spec(spec)

print("Step 3: Executing module...")
spec.loader.exec_module(stockyidong)
print("✓ Module loaded")

print("\nStep 4: Creating Tkinter root and showing window immediately")
root = stockyidong.tk.Tk()
root.title("Stock Analyzer - Loading...")
root.geometry("1580x940")
root.minsize(1280, 820)

# 创建一个加载提示
loading_frame = stockyidong.ttk.Frame(root)
loading_frame.pack(fill=stockyidong.tk.BOTH, expand=True)
loading_label = stockyidong.ttk.Label(loading_frame, text="正在加载股票分析程序，请稍候...", font=("Microsoft YaHei UI", 14))
loading_label.pack(pady=50)

# 显示窗口
root.deiconify()
root.lift()
root.focus_force()
print("✓ Window shown with loading message")

print("\nStep 5: Creating StockKeywordAnalyzerGUI...")
print("  This may take a while...")
import time

start = time.time()

try:
    app = stockyidong.StockKeywordAnalyzerGUI(root)
    elapsed = time.time() - start
    print(f"✓ GUI created in {elapsed:.1f} seconds")
except Exception as e:
    elapsed = time.time() - start
    print(f"✗ GUI creation failed after {elapsed:.1f} seconds: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nStep 6: Starting main loop")
root.mainloop()
print("Done")
