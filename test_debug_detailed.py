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
    
    # 添加一个标签来显示程序正在启动
    label = stockyidong.ttk.Label(root, text="Initializing...")
    label.pack(pady=20)
    root.update()
    
except Exception as e:
    print(f"✗ Failed to create root: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nStep 5: Testing StockKeywordAnalyzerGUI initialization")
start_time = time.time()

# 替换 __init__ 来添加调试输出
original_init = stockyidong.StockKeywordAnalyzerGUI.__init__

def debug_init(self, root_param):
    print("  - StockKeywordAnalyzerGUI.__init__ started")
    
    # 调用原始初始化，但捕获异常
    try:
        original_init(self, root_param)
        elapsed = time.time() - start_time
        print(f"  - StockKeywordAnalyzerGUI.__init__ completed in {elapsed:.2f} seconds")
    except Exception:
        elapsed = time.time() - start_time
        print(f"  - StockKeywordAnalyzerGUI.__init__ failed after {elapsed:.2f} seconds")
        import traceback
        traceback.print_exc()
        raise

stockyidong.StockKeywordAnalyzerGUI.__init__ = debug_init

print("  - Creating StockKeywordAnalyzerGUI instance...")
try:
    app = stockyidong.StockKeywordAnalyzerGUI(root)
    print("✓ Created GUI successfully")
except Exception as e:
    print(f"✗ Failed to create GUI: {e}")
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
