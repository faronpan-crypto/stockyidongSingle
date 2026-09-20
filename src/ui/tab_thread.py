"""线程/异步/后台任务/锁"""
import os, sys, re, json, time, threading, traceback, hashlib, urllib.parse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext
try:
    import numpy as np
except ImportError: np = None
try:
    import pandas as pd
except ImportError: pd = None
try:
    import akshare as ak
except ImportError: ak = None
try:
    import tushare as ts
except ImportError: ts = None
try:
    import requests
except ImportError: requests = None
from utils.network import safe_call
from utils.config import *  # 路径/配置/Token
from data.snapshot import *  # get_news_stocks_* 函数

import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class ThreadMixin:
    """线程/异步/后台任务/锁"""

    def _start_auto_collect(self):
        """启动自动化采集"""
        if not self.auto_collect_enabled:
            return
        def auto_collect_worker():
            """自动化采集工作线程"""
            try:
                import time
                # 等待一下,确保界面已加载
                time.sleep(2)
                # 1. 模拟点击爬取淘股吧按钮
                print("[自动化采集] 开始爬取淘股吧...")
                self.root.after(0, lambda: self.run_crawler_script("taoguba"))
                time.sleep(10)  # 等待爬取完成
                # 2. 模拟点击爬取韭研按钮
                print("[自动化采集] 开始爬取韭研...")
                self.root.after(0, lambda: self.run_crawler_script("jiuyan"))
                time.sleep(10)  # 等待爬取完成
                # 3. 等待Excel文件生成
                time.sleep(5)
                # 4. 自动上传Excel文件到富媒体输入框
                print("[自动化采集] 自动上传Excel文件...")
                excel_tab_ids = self._auto_upload_excel_files()
                time.sleep(3)
                # 5. 对上传的Excel内容进行AI分析
                if excel_tab_ids:
                    for tab_id in excel_tab_ids:
                        print(f"[自动化采集] 对标签页 {tab_id} 进行AI分析...")
                        self.root.after(0, lambda tid=tab_id: self._auto_ai_analysis_for_tab(tid))
                        time.sleep(10)  # 等待AI分析完成
                        # 保存分析结果到资讯
                        print(f"[自动化采集] 保存标签页 {tab_id} 到资讯...")
                        self.root.after(0, lambda tid=tab_id: self._auto_save_tab_to_news(tid))
                        time.sleep(2)
                        # 模拟双击富媒体内容,打开弹出框
                        print(f"[自动化采集] 模拟双击标签页 {tab_id}...")
                        self.root.after(0, lambda tid=tab_id: self._auto_double_click_and_analyze(tid))
                        time.sleep(3)
                # 6. 执行黄色按钮:批量爬取资讯
                print("[自动化采集] 执行批量爬取资讯...")
                self.root.after(0, self.batch_crawl_news)
                time.sleep(5)
                # 7. 执行黄色按钮:一键操作
                print("[自动化采集] 执行一键操作...")
                self.root.after(0, self.one_click_pipeline)
                time.sleep(5)
                # 8. 执行黄色按钮:一键截图
                print("[自动化采集] 执行一键截图...")
                self.root.after(0, self.one_click_screenshot)
                print("[自动化采集] 所有任务已完成")
            except Exception as e:
                print(f"[自动化采集] 执行失败: {e}")
                import traceback
                traceback.print_exc()
        # 在后台线程中执行
        threading.Thread(target=auto_collect_worker, daemon=True).start()

    def _start_skill_scheduler(self):
        """启动全局调度器(幂等)"""
        try:
            if self._skill_scheduler_after_id is not None:
                self.root.after_cancel(self._skill_scheduler_after_id)
        except Exception:
            pass
        self._skill_scheduler_after_id = self.root.after(20000, self._skill_scheduler_tick)
        active_count = sum(1 for t in self._scheduled_skills if t.get("active", True))
        self._log_skill_scheduler(f"全局调度器已启动(共 {len(self._scheduled_skills)} 个任务,{active_count} 个激活)")


__all__ = ["ThreadMixin"]
