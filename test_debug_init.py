#!/usr/bin/env python3
import os
import sys

if sys.platform == "darwin":
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

os.environ["STOCK_ANALYZER_DATA_DIR"] = os.path.join(os.path.expanduser("~"), "StockAnalyzer")
os.makedirs(os.environ["STOCK_ANALYZER_DATA_DIR"], exist_ok=True)

import importlib.util

spec = importlib.util.spec_from_file_location("stockyidong", "src/stockyidong mac.py")
stockyidong = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stockyidong)

print("Step 1: Creating Tkinter root")
root = stockyidong.tk.Tk()
root.title("Stock Analyzer")
root.geometry("1580x940")

print("\nStep 2: Creating GUI with detailed debugging")
print("  This will take a while...")

# 添加调试到 __init__
original_init = stockyidong.StockKeywordAnalyzerGUI.__init__

def debug_init(self, root_param):
    print("  [DEBUG] __init__ started")
    try:
        print("  [DEBUG] Calling original __init__")
        original_init(self, root_param)
        print("  [DEBUG] __init__ completed successfully")
    except Exception as e:
        print(f"  [DEBUG] __init__ failed: {e}")
        import traceback
        traceback.print_exc()
        raise

stockyidong.StockKeywordAnalyzerGUI.__init__ = debug_init

try:
    app = stockyidong.StockKeywordAnalyzerGUI(root)
except Exception as e:
    print(f"Error creating GUI: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nStep 3: Verifying widgets created")
widgets = root.winfo_children()
print(f"Total widgets: {len(widgets)}")
for i, widget in enumerate(widgets):
    print(f"  Widget {i}: {type(widget).__name__}")
    # 检查子控件
    children = widget.winfo_children()
    if children:
        print(f"    {len(children)} children:")
        for j, child in enumerate(children[:5]):
            print(f"      Child {j}: {type(child).__name__}")
        if len(children) > 5:
            print(f"      ... and {len(children) - 5} more")

print("\nStep 4: Starting mainloop for 10 seconds")
root.after(10000, root.quit)
root.mainloop()

print("\nStep 5: Done")
