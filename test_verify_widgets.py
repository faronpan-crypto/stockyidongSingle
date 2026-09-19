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

print("Step 2: Creating GUI")
app = stockyidong.StockKeywordAnalyzerGUI(root)

print("\nStep 3: Verifying widgets created")
widgets = root.winfo_children()
print(f"Total widgets: {len(widgets)}")
for i, widget in enumerate(widgets):
    print(f"  Widget {i}: {type(widget).__name__}")

print("\nStep 4: Showing window")
root.deiconify()
root.lift()

print("\nStep 5: Waiting 5 seconds...")
root.after(5000, root.quit)

print("\nStep 6: Starting mainloop")
root.mainloop()

print("\nStep 7: Done")
