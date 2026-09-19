#!/usr/bin/env python3
import os
import sys

print("Step 1: Starting debug script")
print(f"Python version: {sys.version}")
print(f"Platform: {sys.platform}")

# 设置环境变量
if sys.platform == "darwin":
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
print("Step 2: Set environment variables")

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
print("Step 3: Added to sys.path")

# 测试导入顺序
try:
    print("Step 4: Testing early sqlite temp dir function")
    import importlib.util
    spec = importlib.util.spec_from_file_location("stockyidong", "src/stockyidong mac.py")
    stockyidong = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stockyidong)
    stockyidong._early_sqlite_temp_dir()
    print("✓ _early_sqlite_temp_dir executed")
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback
    traceback.print_exc()

print("Debug script completed")