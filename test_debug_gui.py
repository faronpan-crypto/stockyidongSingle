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

print("Step 2: Importing stockyidong module")
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

print("Step 4: Creating Tkinter root")
try:
    root = stockyidong.tk.Tk()
    print("✓ Created Tk root")
    print(f"Root exists: {root.winfo_exists()}")
except Exception as e:
    print(f"✗ Failed to create Tk root: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("Step 5: Testing basic Tkinter operations")
try:
    root.title("Test Window")
    print("✓ Set title")
    
    root.geometry("400x300")
    print("✓ Set geometry")
    
    label = stockyidong.ttk.Label(root, text="Test Label")
    label.pack(pady=20)
    print("✓ Created label")
    
    root.update()
    print("✓ Update successful")
    
    print(f"Root still exists: {root.winfo_exists()}")
    
except Exception as e:
    print(f"✗ Failed basic Tkinter operations: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nStep 6: Now testing StockKeywordAnalyzerGUI...")
print("This may take a while, please wait...")

# 添加详细的调试输出
original_init = stockyidong.StockKeywordAnalyzerGUI.__init__

def debug_init(self, root_param):
    print("  - StockKeywordAnalyzerGUI.__init__ started")
    start_time = time.time()
    
    # 调用原始初始化
    try:
        original_init(self, root_param)
        elapsed = time.time() - start_time
        print(f"  - StockKeywordAnalyzerGUI.__init__ completed in {elapsed:.2f} seconds")
    except Exception:
        elapsed = time.time() - start_time
        print(f"  - StockKeywordAnalyzerGUI.__init__ failed after {elapsed:.2f} seconds")
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

print("Step 7: Starting main loop")
root.mainloop()

print("Program completed successfully")