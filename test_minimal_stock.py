import os
import sys

# 设置环境变量
if sys.platform == "darwin":
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

# 只导入必要的模块
print("Importing basic modules...")
import tkinter as tk
from tkinter import ttk

print("Importing sqlite3...")
import sqlite3

print("Importing json...")

# 设置数据目录
D_DATA_DIR = os.path.join(os.path.expanduser("~"), "StockAnalyzer")
os.makedirs(D_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(D_DATA_DIR, "stock_analysis.db")

print(f"Data dir: {D_DATA_DIR}")
print(f"DB path: {DB_PATH}")

# 简化的数据库初始化
def init_database():
    """初始化股票数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                date TEXT NOT NULL,
                UNIQUE(stock_code, date)
            )
        ''')
        conn.commit()
        conn.close()
        print("Database initialized")
        return DB_PATH
    except Exception as e:
        print(f"Failed to init database: {e}")
        return None

# 创建主窗口
try:
    root = tk.Tk()
    root.title("Stock Analyzer - Minimal")
    root.geometry("800x600")
    
    main_frame = ttk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # 初始化数据库
    init_database()
    
    # 添加一些按钮
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=10)
    
    ttk.Button(button_frame, text="按钮1").pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="按钮2").pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="按钮3").pack(side=tk.LEFT, padx=5)
    
    # 添加状态标签
    status_label = ttk.Label(main_frame, text="程序已启动，数据库已初始化")
    status_label.pack(pady=20)
    
    root.update()
    print("GUI created successfully")
    
    root.mainloop()
    
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()