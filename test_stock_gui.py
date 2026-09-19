import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

print("Python version:", sys.version)
print("Platform:", sys.platform)

# 模拟股票分析程序的初始化过程
class TestStockGUI:
    def __init__(self, root):
        self.root = root
        
        # 安全更新方法
        def _safe_update():
            try:
                if self.root and self.root.winfo_exists():
                    self.root.tk.call('update')
                    return True
                return False
            except Exception as e:
                print(f"safe_update failed: {e}")
                return False
        
        def _safe_update_idletasks():
            try:
                if self.root and self.root.winfo_exists():
                    self.root.tk.call('update', 'idletasks')
                    return True
                return False
            except Exception as e:
                print(f"safe_update_idletasks failed: {e}")
                return False
        
        self._safe_update = _safe_update
        self._safe_update_idletasks = _safe_update_idletasks
        
        # 设置窗口
        try:
            self.root.title("Stock Analyzer Test")
            print("Set title")
        except Exception as e:
            print(f"Failed to set title: {e}")
        
        try:
            self.root.geometry("1580x940")
            print("Set geometry")
        except Exception as e:
            print(f"Failed to set geometry: {e}")
        
        # 创建简单界面
        main_frame = ttk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="按钮1").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="按钮2").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="按钮3").pack(side=tk.LEFT, padx=5)
        
        # 添加标签
        self.status_label = ttk.Label(main_frame, text="初始化中...")
        self.status_label.pack(pady=20)
        
        # 模拟后台任务
        def background_task():
            print("Starting background task")
            # 模拟耗时操作
            time.sleep(2)
            print("Background task done")
            # 更新UI
            try:
                self.root.after(0, lambda: self.status_label.config(text="初始化完成"))
            except Exception as e:
                print(f"Failed to update label: {e}")
        
        threading.Thread(target=background_task, daemon=True).start()
        
        # 更新界面
        self._safe_update()
        print("GUI created successfully")

try:
    if sys.platform == "darwin":
        os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
    
    root = tk.Tk()
    print("Created Tk root")
    
    app = TestStockGUI(root)
    print("Created app")
    
    root.mainloop()
    
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()