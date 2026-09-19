import os
import sys
import tkinter as tk
from tkinter import ttk

print("Python version:", sys.version)
print("Platform:", sys.platform)

try:
    # 设置环境变量
    if sys.platform == "darwin":
        os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
    
    root = tk.Tk()
    root.title("Stock Analyzer - Test")
    root.geometry("800x600")
    
    # 创建简单的界面
    main_frame = ttk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # 添加一些按钮
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=10)
    
    ttk.Button(button_frame, text="按钮1").pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="按钮2").pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="按钮3").pack(side=tk.LEFT, padx=5)
    
    # 添加标签
    label = ttk.Label(main_frame, text="测试界面 - 基本控件正常工作")
    label.pack(pady=20)
    
    root.update()
    print("界面创建成功")
    
    root.mainloop()
    
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()