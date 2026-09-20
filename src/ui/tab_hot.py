try:
    import jieba
except ImportError:
    jieba = None
"""HotMixin - 热门/板块/北向/hotmoney"""
import os, sys, re, json, time, threading, traceback
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
from utils.network import safe_call
from utils.config import *  # 路径/配置/Token
from data.snapshot import *  # get_news_stocks_* 函数
from logic.crawlers import *  # TaogubaCrawler
from logic.spot import *
from logic.stock_names import *  # get_stock_name_by_code 等

from datetime import datetime, timedelta
import re
import json
import os
import time
import threading
import traceback
import sqlite3

class HotMixin:
    """热门板块/选股/北向资金/hotmoney"""

    def _create_hot_navigation_tab_in_notebook(self, notebook):
        """在market_notebook中创建热点导航标签页(仅创建框架,内容由_create_hot_navigation_tab填充)"""
        # 检查标签页是否已存在
        for i in range(notebook.index("end")):
            if notebook.tab(i, "text") == "热点导航":
                return  # 已存在,不重复创建
        # 创建新标签页
        tab_frame = ttk.Frame(notebook, padding=10)
        # 找到"市场指数"标签页的位置,在其后插入
        market_indices_index = None
        for i in range(notebook.index("end")):
            if notebook.tab(i, "text") == "市场指数":
                market_indices_index = i
                break
        if market_indices_index is not None:
            # 检查插入位置是否在有效范围内
            insert_pos = market_indices_index + 1
            if insert_pos < notebook.index("end"):
                notebook.insert(insert_pos, tab_frame, text="热点导航")
            else:
                # 如果插入位置超出范围,使用add添加到末尾
                notebook.add(tab_frame, text="热点导航")
        else:
            # 如果notebook为空,使用add;否则使用insert
            if notebook.index("end") == 0:
                notebook.add(tab_frame, text="热点导航")
            else:
                notebook.insert(0, tab_frame, text="热点导航")
        # 保存引用,供后续填充内容
        self.market_notebook = notebook

    def _create_hot_navigation_tab(self):
        """创建热点导航标签页(在market_notebook中)"""
        if not hasattr(self, 'market_notebook') or not self.market_notebook:
            return
        # 检查标签页是否已存在
        existing_index = None
        for i in range(self.market_notebook.index("end")):
            if self.market_notebook.tab(i, "text") == "热点导航":
                existing_index = i
                break
        if existing_index is None:
            # 创建新标签页,找到"市场指数"标签页的位置,在其后插入
            market_indices_index = None
            for i in range(self.market_notebook.index("end")):
                if self.market_notebook.tab(i, "text") == "市场指数":
                    market_indices_index = i
                    break
            tab_frame = ttk.Frame(self.market_notebook, padding=10)
            if market_indices_index is not None:
                self.market_notebook.insert(market_indices_index + 1, tab_frame, text="热点导航")
            else:
                self.market_notebook.insert(0, tab_frame, text="热点导航")
        else:
            # 获取现有标签页
            tab_frame = self.market_notebook.nametowidget(self.market_notebook.tabs()[existing_index])
            # 清空内容
            for widget in tab_frame.winfo_children():
                widget.destroy()
        # 继续创建内容
        # 清空原有的文本框
        for widget in tab_frame.winfo_children():
            if isinstance(widget, tk.Text):
                widget.destroy()
            elif isinstance(widget, ttk.Frame) and widget.winfo_children():
                # 检查是否是工具栏
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Button) and child.cget("text") == "×":
                        continue
                    widget.destroy()
        # 创建滚动框架
        canvas_frame = ttk.Frame(tab_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # 合并portals和hot_sources数据
        portals = self.market_nav_config.get("portals", [])
        hot_sources = self.market_nav_config.get("hot_sources", [])
        all_nav_data = portals + hot_sources
        # 确保每个项目都有排序字段
        for item in all_nav_data:
            if "sort_order" not in item:
                item["sort_order"] = len(all_nav_data)
        # 按排序字段排序
        all_nav_data = sorted(all_nav_data, key=lambda x: x.get("sort_order", 999))
        # 创建链接按钮
        for idx, item in enumerate(all_nav_data):
            name = item.get("name", "")
            url = item.get("url", "")
            sort_order = item.get("sort_order", idx + 1)
            # 判断是否为排名/热榜类按钮(包含"榜"、"排名"、"热"等关键词)
            is_rank_hot = any(keyword in name for keyword in ["榜", "排名", "热", "排行", "统计", "明细", "天梯"])
            # 根据排序和类型设置字体大小和颜色
            if is_rank_hot:
                # 排名和热榜类按钮:红色、橘黄色,加大加粗
                if sort_order == 1:
                    font_size = 18
                    bg_color = "red"
                elif sort_order == 2:
                    font_size = 16
                    bg_color = "orange"
                else:
                    font_size = 14
                    bg_color = "#FF6B35"  # 橘红色
            else:
                # 普通按钮:根据排序设置
                if sort_order == 1:
                    font_size = 18
                    bg_color = "red"
                elif sort_order == 2:
                    font_size = 16
                    bg_color = "orange"
                elif sort_order == 3:
                    font_size = 14
                    bg_color = "blue"
                else:
                    font_size = 12
                    bg_color = "lightgray"
            # 创建链接按钮(纯按钮,无说明文字)
            def open_link(u=url, n=name):
                import webbrowser
                if u:
                    webbrowser.open(u)
                    # 复制链接到剪贴板
                    self.root.clipboard_clear()
                    self.root.clipboard_append(u)
                    self._safe_update()
                else:
                    messagebox.showwarning("提示", f"按钮 '{n}' 的链接未配置")
            link_btn = tk.Button(
                scrollable_frame,
                text=name,
                font=("TkDefaultFont", font_size, "bold" if is_rank_hot or sort_order <= 3 else "normal"),
                bg=bg_color,
                fg="black",
                cursor="hand2",
                relief=tk.RAISED,
                bd=2,
                padx=10,
                pady=5,
                command=lambda u=url, n=name: open_link(u, n)
            )
            link_btn.pack(fill=tk.X, padx=5, pady=3)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 添加编辑按钮
        edit_frame = ttk.Frame(tab_frame)
        edit_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(edit_frame, text="编辑排序", command=self._edit_hot_navigation_sort).pack(side=tk.LEFT, padx=5)

    def _create_merged_market_hot_tab(self):
        """创建合并的市场指数&热点导航标签页(二列布局)"""
        if not hasattr(self, 'market_notebook') or not self.market_notebook:
            return
        # 检查标签页是否已存在
        existing_index = None
        for i in range(self.market_notebook.index("end")):
            if self.market_notebook.tab(i, "text") == "市场指数&热点导航":
                existing_index = i
                break
        if existing_index is None:
            # 创建新标签页
            tab_frame = ttk.Frame(self.market_notebook, padding=10)
            # 如果notebook为空,使用add;否则使用insert插入到第一个位置
            if self.market_notebook.index("end") == 0:
                self.market_notebook.add(tab_frame, text="市场指数&热点导航")
            else:
                self.market_notebook.insert(0, tab_frame, text="市场指数&热点导航")
        else:
            # 获取现有标签页
            tab_frame = self.market_notebook.nametowidget(self.market_notebook.tabs()[existing_index])
            # 清空内容
            for widget in tab_frame.winfo_children():
                widget.destroy()
        # 创建滚动框架
        canvas_frame = ttk.Frame(tab_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # 创建三列网格布局框架
        grid_frame = ttk.Frame(scrollable_frame)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 配置三列,每列权重相等
        for col in range(3):
            grid_frame.columnconfigure(col, weight=1, uniform="equal")
        # 获取市场指数数据(创建副本,避免修改原始数据)
        indices_data = [item.copy() for item in self.market_nav_config.get("indices", [])]
        # 为市场指数数据添加类型标记
        for item in indices_data:
            item["_type"] = "indices"
        # 获取热点导航数据(portals和hot_sources)(创建副本)
        portals = [item.copy() for item in self.market_nav_config.get("portals", [])]
        hot_sources = [item.copy() for item in self.market_nav_config.get("hot_sources", [])]
        # 为热点导航数据添加类型标记
        for item in portals:
            item["_type"] = "portals"
        for item in hot_sources:
            item["_type"] = "hot_sources"
        # 合并所有数据
        all_data = indices_data + portals + hot_sources
        # 确保每个项目都有排序字段
        for item in all_data:
            if "sort_order" not in item:
                item["sort_order"] = len(all_data)
        # 按排序字段排序
        all_data = sorted(all_data, key=lambda x: x.get("sort_order", 999))
        # 存储按钮引用,用于拖拽
        button_refs = []
        # 创建按钮(三列布局,由上到下,由左到右)
        for idx, item in enumerate(all_data):
            name = item.get("name", "")
            url = item.get("url", "")
            sort_order = item.get("sort_order", idx + 1)
            item_type = item.get("_type", "")
            # 判断是否为排名/热榜类按钮
            is_rank_hot = any(keyword in name for keyword in ["榜", "排名", "热", "排行", "统计", "明细", "天梯"])
            # 优先使用配置的颜色,否则根据排序和类型设置字体大小和颜色(保持原有大小)
            bg_color = item.get("bg_color", "")
            fg_color = item.get("fg_color", "")
            if not bg_color or not fg_color:
                # 如果没有配置颜色,使用默认逻辑
                if is_rank_hot:
                    if sort_order == 1:
                        font_size = 18
                        bg_color = bg_color or "red"
                        fg_color = fg_color or "white"
                    elif sort_order == 2:
                        font_size = 16
                        bg_color = bg_color or "orange"
                        fg_color = fg_color or "white"
                    else:
                        font_size = 14
                        bg_color = bg_color or "#FF6B35"
                        fg_color = fg_color or "white"
                else:
                    if sort_order == 1:
                        font_size = 18
                        bg_color = bg_color or "red"
                        fg_color = fg_color or "white"
                    elif sort_order == 2:
                        font_size = 16
                        bg_color = bg_color or "orange"
                        fg_color = fg_color or "white"
                    elif sort_order == 3:
                        font_size = 14
                        bg_color = bg_color or "blue"
                        fg_color = fg_color or "white"
                    else:
                        font_size = 12
                        bg_color = bg_color or "lightgray"
                        fg_color = fg_color or "black"
            else:
                # 如果配置了颜色,根据字体大小设置(如果没有配置字体大小,使用默认值)
                if is_rank_hot or sort_order <= 3:
                    font_size = item.get("font_size", 14)
                else:
                    font_size = item.get("font_size", 12)
            def open_link(u=url, n=name):
                import webbrowser
                if u:
                    webbrowser.open(u)
                    self.root.clipboard_clear()
                    self.root.clipboard_append(u)
                    self._safe_update()
                else:
                    messagebox.showwarning("提示", f"按钮 '{n}' 的链接未配置")
            # 计算网格位置(三列布局)
            row = idx // 3
            col = idx % 3
            # 创建复选框和按钮的容器框架
            btn_frame = ttk.Frame(grid_frame)
            btn_frame.grid(row=row, column=col, padx=4, pady=3, sticky="ew")
            # 创建复选框,加载保存的状态
            checkbox_key = f"merged_{idx}"
            saved_state = self.market_nav_checkbox_states.get(checkbox_key, False)
            checkbox_var = tk.BooleanVar(value=saved_state)
            if not hasattr(self, 'market_nav_checkboxes'):
                self.market_nav_checkboxes = {}
            self.market_nav_checkboxes[checkbox_key] = {
                'var': checkbox_var,
                'name': name,
                'url': url,
                'config_key': item_type
            }
            checkbox = ttk.Checkbutton(btn_frame, variable=checkbox_var,
                                       command=lambda k=checkbox_key, v=checkbox_var: self._save_market_nav_checkbox_state(k, v.get()))
            checkbox.pack(side=tk.LEFT, padx=(0, 3))
            link_btn = tk.Button(
                btn_frame,
                text=name,
                font=("TkDefaultFont", font_size, "bold" if is_rank_hot or sort_order <= 3 else "normal"),
                bg=bg_color,
                fg="black",
                cursor="hand2",
                relief=tk.RAISED,
                bd=2,
                padx=10,
                pady=5,
                command=lambda u=url, n=name: open_link(u, n)
            )
            link_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            # 存储按钮信息用于拖拽(注意:现在按钮在btn_frame中)
            button_info = {
                "button": link_btn,
                "button_frame": btn_frame,  # 添加按钮框架引用
                "item": item,
                "row": row,
                "col": col,
                "index": idx
            }
            button_refs.append(button_info)
            # 实现拖拽功能
            def on_drag_start(event, btn_info=button_info):
                btn_info["drag_start_x"] = event.x
                btn_info["drag_start_y"] = event.y
                btn_info["drag_start_root_x"] = event.x_root
                btn_info["drag_start_root_y"] = event.y_root
                btn_info["dragging"] = False  # 初始为False,只有移动一定距离后才开始拖拽
                btn_info["drag_threshold"] = 5  # 拖拽阈值(像素)
                btn_info["original_row"] = btn_info["row"]
                btn_info["original_col"] = btn_info["col"]
                # 保存原始位置(使用button_frame)
                btn_info["original_x"] = btn_info["button_frame"].winfo_x()
                btn_info["original_y"] = btn_info["button_frame"].winfo_y()
            def on_drag_motion(event, btn_info=button_info):
                # 计算移动距离
                dx = abs(event.x_root - btn_info["drag_start_root_x"])
                dy = abs(event.y_root - btn_info["drag_start_root_y"])
                distance = (dx**2 + dy**2)**0.5
                # 如果移动距离超过阈值,开始拖拽
                if not btn_info.get("dragging", False) and distance > btn_info["drag_threshold"]:
                    btn_info["dragging"] = True
                    # 提升按钮框架到最上层(通过临时使用place)
                    btn_info["button_frame"].grid_remove()
                    btn_info["button_frame"].place(x=btn_info["original_x"], y=btn_info["original_y"])
                    btn_info["button_frame"].lift()
                if btn_info.get("dragging", False):
                    # 计算新位置(相对于原始位置)
                    new_x = btn_info["original_x"] + (event.x - btn_info["drag_start_x"])
                    new_y = btn_info["original_y"] + (event.y - btn_info["drag_start_y"])
                    # 限制在grid_frame范围内
                    frame_x = grid_frame.winfo_x()
                    frame_y = grid_frame.winfo_y()
                    frame_width = grid_frame.winfo_width()
                    frame_height = grid_frame.winfo_height()
                    btn_width = btn_info["button_frame"].winfo_width()
                    btn_height = btn_info["button_frame"].winfo_height()
                    # 限制在框架内
                    new_x = max(frame_x, min(new_x, frame_x + frame_width - btn_width))
                    new_y = max(frame_y, min(new_y, frame_y + frame_height - btn_height))
                    btn_info["button_frame"].place(x=new_x, y=new_y)
            def on_drag_end(event, btn_info=button_info):
                was_dragging = btn_info.get("dragging", False)
                btn_info["dragging"] = False
                if was_dragging:
                    # 计算新网格位置(相对于grid_frame)
                    btn_x = btn_info["button_frame"].winfo_x() - grid_frame.winfo_x()
                    btn_y = btn_info["button_frame"].winfo_y() - grid_frame.winfo_y()
                    # 计算目标行列
                    cell_width = grid_frame.winfo_width() // 3
                    # 估算行高(按钮框架高度 + padding)
                    btn_height = btn_info["button_frame"].winfo_height()
                    if btn_height == 1:  # 如果按钮框架还没渲染,使用估算值
                        btn_height = 50
                    cell_height = btn_height + 6  # 6是pady*2
                    target_col = min(2, max(0, int(btn_x / cell_width)))
                    target_row = max(0, int(btn_y / cell_height))
                    target_idx = target_row * 3 + target_col
                    # 限制在有效范围内
                    target_idx = min(len(button_refs) - 1, max(0, target_idx))
                    # 恢复grid布局
                    btn_info["button_frame"].place_forget()
                    btn_info["button_frame"].grid(row=btn_info["row"], column=btn_info["col"], padx=4, pady=3, sticky="ew")
                    # 如果位置改变,更新排序
                    if target_idx != btn_info["index"]:
                        # 重新排列按钮
                        self._reorder_buttons(button_refs, btn_info["index"], target_idx)
                else:
                    # 如果没有拖拽,只是点击,正常执行按钮的command
                    pass
            # 绑定拖拽事件
            link_btn.bind("<Button-1>", on_drag_start)
            link_btn.bind("<B1-Motion>", on_drag_motion)
            link_btn.bind("<ButtonRelease-1>", on_drag_end)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 保存按钮引用到实例变量,供重新排列函数使用
        if not hasattr(self, '_merged_tab_button_refs'):
            self._merged_tab_button_refs = []
        self._merged_tab_button_refs = button_refs
        # 添加编辑按钮
        edit_frame = ttk.Frame(tab_frame)
        edit_frame.pack(fill=tk.X, padx=5, pady=5)
        # 编辑导航按钮(打开编辑导航窗口,可以编辑所有内容)
        ttk.Button(edit_frame, text="编辑导航", command=self.show_market_nav_editor).pack(side=tk.LEFT, padx=5)
        # 编辑市场指数按钮(打开编辑导航窗口并定位到市场指数标签页)
        ttk.Button(edit_frame, text="编辑市场指数", command=lambda: self.show_market_nav_editor(default_tab=0)).pack(side=tk.LEFT, padx=5)
        # 编辑热点导航按钮(打开编辑导航窗口,热点导航包含portals和hot_sources两个标签页)
        ttk.Button(edit_frame, text="编辑热点导航", command=lambda: self.show_market_nav_editor(default_tab=1)).pack(side=tk.LEFT, padx=5)
        # 排序按钮(仅编辑排序)
        ttk.Button(edit_frame, text="市场指数排序", command=self._edit_market_indices_sort).pack(side=tk.LEFT, padx=5)
        ttk.Button(edit_frame, text="热点导航排序", command=self._edit_hot_navigation_sort).pack(side=tk.LEFT, padx=5)
        # 设定为默认按钮(将当前配置保存为新的默认值)
        ttk.Button(edit_frame, text="设定为默认", command=self.set_merged_as_default_config).pack(side=tk.LEFT, padx=5)
        # 界面创建完成,立即显示窗口并强制刷新
        self.root.deiconify()  # 确保窗口可见
        self._safe_update()
        self._safe_update_idletasks()
        self.root.lift()  # 将窗口置于最前
        self.root.focus_force()  # 强制获得焦点
        # 延迟初始化耗时操作(在后台线程中执行,不阻塞界面)
        def delayed_init():
            try:
                # 先加载配置文件(较快)
                if not self.market_nav_config:
                    self.market_nav_config = self.load_market_nav_config()
                if not self.crawler_config:
                    self.crawler_config = self.load_crawler_config()
                # 加载管理的股票列表(较快)
                self._load_managed_stocks_from_file()
            except Exception as e:
                print(f"延迟初始化失败: {e}")
            # 爬虫初始化较耗时,再延后 2 秒执行,不阻塞首屏
            def _deferred_crawler_init():
                try:
                    if self.taoguba_crawler is None:
                        self.taoguba_crawler = TaogubaCrawler()
                    if self.jiuyangongshe_crawler is None:
                        self.jiuyangongshe_crawler = JiuYangGongSheCrawler()
                except Exception as e:
                    print(f"爬虫延迟初始化失败: {e}")
            self.root.after(15000, _deferred_crawler_init)  # 延后 15s
            # Skill 定时调度器(全局每 20s 轮询),延后 6 秒等 UI 就绪
            def _deferred_skill_scheduler():
                try:
                    self._start_skill_scheduler()
                except Exception as e:
                    print(f"Skill 调度器启动失败: {e}")
            self.root.after(25000, _deferred_skill_scheduler)  # 延后 25s
        # 在界面显示后延迟执行耗时操作(500ms,让UI先渲染)
        self.root.after(500, delayed_init)

    def _edit_hot_navigation_sort(self):
        """编辑热点导航排序"""
        # 合并portals和hot_sources
        portals = self.market_nav_config.get("portals", [])
        hot_sources = self.market_nav_config.get("hot_sources", [])
        # 如果数据为空,尝试从默认配置加载
        if not portals:
            default_portals = DEFAULT_MARKET_NAV_CONFIG.get("portals", [])
            if default_portals:
                portals = default_portals
                self.market_nav_config["portals"] = portals
        if not hot_sources:
            default_hot_sources = DEFAULT_MARKET_NAV_CONFIG.get("hot_sources", [])
            if default_hot_sources:
                hot_sources = default_hot_sources
                self.market_nav_config["hot_sources"] = hot_sources
        if portals or hot_sources:
            self.save_market_nav_config()
        all_data = portals + hot_sources
        # 创建临时配置用于编辑
        win = self._safe_toplevel(self.root)
        win.title("热点导航排序")
        win.geometry("600x500")
        # 创建列表和排序控件
        list_frame = ttk.Frame(win)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        # 列表显示
        listbox = tk.Listbox(list_frame, height=15)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # 排序按钮
        sort_btn_frame = ttk.Frame(list_frame)
        sort_btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        ttk.Button(sort_btn_frame, text="↑", command=lambda: self._move_item_up(listbox, all_data)).pack(pady=2)
        ttk.Button(sort_btn_frame, text="↓", command=lambda: self._move_item_down(listbox, all_data)).pack(pady=2)
        # 刷新列表
        def refresh_list():
            listbox.delete(0, tk.END)
            if not all_data:
                listbox.insert(tk.END, "暂无数据,请在编辑导航中添加")
            else:
                # 按排序字段排序
                sorted_list = sorted(all_data, key=lambda x: x.get("sort_order", 999))
                for idx, item in enumerate(sorted_list):
                    sort_order = item.get("sort_order", idx + 1)
                    name = item.get("name", "")
                    listbox.insert(tk.END, f"{sort_order}. {name}")
        refresh_list()
        # 保存按钮
        def save_sort():
            # 更新排序字段
            for idx, item in enumerate(all_data):
                item["sort_order"] = idx + 1
            # 分别保存到portals和hot_sources
            portal_count = len(portals)
            for idx, item in enumerate(all_data):
                if idx < portal_count:
                    if idx < len(portals):
                        portals[idx]["sort_order"] = item.get("sort_order", idx + 1)
                else:
                    hot_idx = idx - portal_count
                    if hot_idx < len(hot_sources):
                        hot_sources[hot_idx]["sort_order"] = item.get("sort_order", idx + 1)
            self.market_nav_config["portals"] = portals
            self.market_nav_config["hot_sources"] = hot_sources
            self.save_market_nav_config()
            self._create_merged_market_hot_tab()  # 刷新合并标签页
            win.destroy()
        ttk.Button(win, text="保存", command=save_sort).pack(pady=10)

    def _enrich_hot_stocks_with_quote(self, stocks):
        """为热门股列表补充涨跌幅、资金流入流出、主力净量。正数红、负数绿,用于弹窗显示。"""
        if not stocks or not AKSHARE_AVAILABLE:
            return stocks
        try:
            # 1) 实时行情 -> 涨跌幅
            spot_df = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
            code_to_pct = {}
            if spot_df is not None and not spot_df.empty and '涨跌幅' in spot_df.columns:
                spot_df['_code'] = spot_df['代码'].astype(str).str.zfill(6)
                for _, row in spot_df.iterrows():
                    code_to_pct[row['_code']] = row['涨跌幅']
            # 2) 今日个股资金流排名 -> 资金流入、主力净量
            flow_rank = None
            try:
                flow_rank = ak.stock_individual_fund_flow_rank(indicator="今日")
            except Exception:
                pass
            code_to_flow = {}
            code_to_main_ratio = {}
            if flow_rank is not None and not flow_rank.empty:
                flow_rank['_code'] = flow_rank['代码'].astype(str).str.zfill(6)
                flow_amt_col = None
                flow_ratio_col = None
                da_col = None  # 大单净流入
                chaoda_col = None  # 超大单净流入
                for col in flow_rank.columns:
                    cs = str(col)
                    if flow_amt_col is None and '主力净流入' in cs and '净额' in cs:
                        flow_amt_col = col
                    if flow_ratio_col is None and (('主力净流入' in cs and '占比' in cs) or '主力净量' in cs):
                        flow_ratio_col = col
                    if da_col is None and '大单净流入' in cs and '占比' not in cs:
                        da_col = col
                    if chaoda_col is None and '超大单净流入' in cs and '占比' not in cs:
                        chaoda_col = col
                if flow_amt_col is None and (da_col or chaoda_col):
                    flow_amt_col = '_sum'
                elif flow_amt_col is None:
                    for col in flow_rank.columns:
                        if '净流入' in str(col) and '占比' not in str(col):
                            flow_amt_col = col
                            break
                for _, row in flow_rank.iterrows():
                    c = row.get('_code', '')
                    if not c:
                        continue
                    try:
                        if flow_amt_col == '_sum':
                            total = 0
                            if da_col and da_col in row and pd.notna(row.get(da_col)):
                                total += float(row[da_col])
                            if chaoda_col and chaoda_col in row and pd.notna(row.get(chaoda_col)):
                                total += float(row[chaoda_col])
                            if total != 0:
                                code_to_flow[c] = total
                        elif flow_amt_col and flow_amt_col in row:
                            v = row[flow_amt_col]
                            if pd.notna(v):
                                code_to_flow[c] = float(v)
                    except (TypeError, ValueError):
                        pass
                    try:
                        if flow_ratio_col and flow_ratio_col in row:
                            v = row[flow_ratio_col]
                            if pd.notna(v):
                                code_to_main_ratio[c] = float(v)
                    except (TypeError, ValueError):
                        pass
            # 3) 写回每只股票
            for s in stocks:
                code = (s.get('code') or '')[-6:].zfill(6) if s.get('code') else ''
                s['涨跌幅'] = code_to_pct.get(code)
                s['资金流入'] = code_to_flow.get(code)
                s['主力净量'] = code_to_main_ratio.get(code)
        except Exception as e:
            print(f"补充涨跌幅/资金流失败: {e}")
            import traceback
            traceback.print_exc()
        return stocks

    def _crawl_hot_stocks_combined(self):
        """爬取热门股:依次执行龙头股(选股通)和同花顺热榜爬取,合并去重后在弹窗显示,可保存到txt或股票数据表。"""
        progress_window = self._safe_toplevel(self.root)
        progress_window.title("爬取热门股")
        progress_window.geometry("420x160")
        progress_window.transient(self.root)
        progress_label = ttk.Label(progress_window, text="正在爬取:选股通 → 同花顺热榜...", font=("TkDefaultFont", 11))
        progress_label.pack(pady=25)
        progress_bar = ttk.Progressbar(progress_window, mode='indeterminate', length=320)
        progress_bar.pack(pady=10)
        progress_bar.start()
        progress_window.update()
        def do_crawl():
            try:
                progress_label.config(text="正在爬取选股通主题库...")
                progress_window.update()
                leaders = self._fetch_xuangutong_leaders_stocks()
                progress_label.config(text="正在爬取同花顺热榜...")
                progress_window.update()
                ths = self._fetch_ths_hot_stocks()
                seen = set()
                merged = []
                for s in (leaders + ths):
                    code = s.get('code', '')
                    if code and code not in seen:
                        seen.add(code)
                        merged.append({'name': s.get('name', ''), 'code': code})
                progress_label.config(text="正在获取涨跌幅与资金流...")
                progress_window.update()
                merged = self._enrich_hot_stocks_with_quote(merged)
                def show_popup():
                    progress_window.destroy()
                    self._show_hot_stocks_result_popup(merged)
                self.root.after(0, show_popup)
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                def show_err(e=e):
                    progress_window.destroy()
                    messagebox.showerror("错误", f"爬取热门股失败: {e!s}", parent=self.root)
                self.root.after(0, show_err)
        threading.Thread(target=do_crawl, daemon=True).start()

    def _crawl_hot_stocks_full_no_dedup(self):
        """爬取选股通题材库+同花顺热门题材股全部,不去重,弹窗显示;可保存为 txt/excel/股票资讯表,可双击全窗口浏览。"""
        progress_window = self._safe_toplevel(self.root)
        progress_window.title("热门股非去重")
        progress_window.geometry("420x160")
        progress_window.transient(self.root)
        progress_label = ttk.Label(progress_window, text="正在爬取:选股通 + 同花顺 热门股(非去重)...", font=("TkDefaultFont", 11))
        progress_label.pack(pady=25)
        progress_bar = ttk.Progressbar(progress_window, mode='indeterminate', length=320)
        progress_bar.pack(pady=10)
        progress_bar.start()
        progress_window.update()
        def do_crawl():
            try:
                progress_label.config(text="正在爬取选股通题材库...")
                progress_window.update()
                xuangu = self._fetch_xuangutong_full_no_dedup()
                progress_label.config(text="正在爬取同花顺热榜...")
                progress_window.update()
                ths = self._fetch_ths_full_no_dedup()
                merged = list(xuangu) + list(ths)
                def show_popup():
                    progress_window.destroy()
                    self._show_hot_stocks_no_dedup_popup(merged)
                self.root.after(0, show_popup)
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                def show_err(e=e):
                    progress_window.destroy()
                    messagebox.showerror("错误", f"爬取热门股非去重失败: {e!s}", parent=self.root)
                self.root.after(0, show_err)
        threading.Thread(target=do_crawl, daemon=True).start()

    def _show_hot_stocks_result_popup(self, stocks):
        """弹窗显示爬取的热门股列表,右侧显示涨跌幅、资金流入流出、主力净量(正红负绿);可保存到txt、股票数据表。"""
        if not stocks:
            messagebox.showinfo("提示", "未爬取到任何股票", parent=self.root)
            return
        win = self._safe_toplevel(self.root)
        win.title("爬取热门股 - 结果")
        win.geometry("780x520")
        win.transient(self.root)
        top = ttk.Frame(win, padding=10)
        top.pack(fill=tk.BOTH, expand=True)
        ttk.Label(top, text=f"共 {len(stocks)} 只股票(选股通 + 同花顺热榜,已去重)", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        list_frame = ttk.Frame(top)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 8))
        text_widget = tk.Text(list_frame, height=20, font=("Consolas", 12), wrap=tk.NONE)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=text_widget.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=text_widget.xview)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        text_widget.config(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        text_widget.tag_configure("red", foreground="#c00")
        text_widget.tag_configure("green", foreground="#080")
        # 表头
        text_widget.insert(tk.END, "代码\t名称\t涨跌幅\t资金流入流出\t主力净量\n", "header")
        text_widget.tag_configure("header", font=("Consolas", 12, "bold"))
        def _fmt_pct(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return "--"
            try:
                x = float(v)
                return f"{x:+.2f}%"
            except (TypeError, ValueError):
                return str(v) if v != "" else "--"
        def _fmt_flow(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return "--"
            try:
                x = float(v)
                if abs(x) >= 1e8:
                    return f"{x/1e8:+.2f}亿"
                if abs(x) >= 1e4:
                    return f"{x/1e4:+.2f}万"
                return f"{x:+.0f}"
            except (TypeError, ValueError):
                return str(v) if v != "" else "--"
        def _tag(val):
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            try:
                x = float(val)
                return "red" if x > 0 else "green" if x < 0 else None
            except (TypeError, ValueError):
                return None
        for s in stocks:
            code = s.get('code', '') or ''
            name = s.get('name', '') or ''
            pct = s.get('涨跌幅')
            flow = s.get('资金流入')
            main_q = s.get('主力净量')
            text_widget.insert(tk.END, f"{code}\t{name}\t", "default")
            # 涨跌幅
            tag_pct = _tag(pct)
            text_widget.insert(tk.END, _fmt_pct(pct) + "\t", tag_pct or "default")
            # 资金流入
            tag_flow = _tag(flow)
            text_widget.insert(tk.END, _fmt_flow(flow) + "\t", tag_flow or "default")
            # 主力净量
            tag_main = _tag(main_q)
            text_widget.insert(tk.END, _fmt_pct(main_q) if main_q is not None else "--", tag_main or "default")
            text_widget.insert(tk.END, "\n", "default")
        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill=tk.X)
        def copy_all_text():
            lines = ["代码\t名称\t涨跌幅\t资金流入流出\t主力净量"]
            for s in stocks:
                lines.append(f"{s.get('code', '')}\t{s.get('name', '')}\t{_fmt_pct(s.get('涨跌幅'))}\t{_fmt_flow(s.get('资金流入'))}\t{_fmt_pct(s.get('主力净量')) if s.get('主力净量') is not None else '--'}")
            text = "\n".join(lines)
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                messagebox.showinfo("已复制", "结果已复制到剪贴板,可直接粘贴为文字。", parent=win)
            except Exception as e:
                messagebox.showerror("错误", f"复制失败: {e}", parent=win)
        ttk.Button(btn_frame, text="复制全部", command=copy_all_text, width=12).pack(side=tk.LEFT, padx=(0, 8))
        def save_to_txt():
            path = tk.filedialog.asksaveasfilename(
                parent=win, title="保存到文本文件",
                defaultextension=".txt", filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
            )
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("代码\t名称\t涨跌幅\t资金流入流出\t主力净量\n")
                    for s in stocks:
                        f.write(f"{s.get('code', '')}\t{s.get('name', '')}\t{_fmt_pct(s.get('涨跌幅'))}\t{_fmt_flow(s.get('资金流入'))}\t{_fmt_pct(s.get('主力净量')) if s.get('主力净量') is not None else '--'}\n")
                messagebox.showinfo("成功", f"已保存 {len(stocks)} 条到\n{path}", parent=win)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=win)
        def save_to_db():
            today = datetime.now().strftime("%Y-%m-%d")
            saved = 0
            for s in stocks:
                code = s.get('code', '')
                name = s.get('name', '') or code
                if code and save_stock_to_db(code, name, today):
                    saved += 1
            messagebox.showinfo("成功", f"已保存 {saved} 条到股票数据表(stock_data),日期 {today}", parent=win)
        ttk.Button(btn_frame, text="保存到 TXT 文件", command=save_to_txt, width=16).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="保存到股票数据表", command=save_to_db, width=18).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="关闭", command=win.destroy, width=10).pack(side=tk.LEFT)

    def _show_hot_stocks_no_dedup_popup(self, data_list):
        """弹窗显示热门股非去重结果:选股通板块数据(黑色)、同花顺股票+逻辑(红色);可保存 txt/excel/股票资讯表/股票数据表。"""
        if not data_list:
            messagebox.showinfo("提示", "未爬取到任何数据", parent=self.root)
            return
        win = self._safe_toplevel(self.root)
        win.title("热门股非去重 - 结果")
        win.geometry("900x580")
        win.transient(self.root)
        top = ttk.Frame(win, padding=10)
        top.pack(fill=tk.BOTH, expand=True)
        # 分离选股通板块数据和同花顺股票数据
        xuangu_sectors = [d for d in data_list if d.get('来源') == '选股通']
        ths_stocks = [d for d in data_list if d.get('来源') == '同花顺']
        ths_stat_line1 = ths_stat_line2 = ths_stat_line3 = None
        ths_sum_big_total_str = ths_sum_big_avg_str = None
        day_avg_strs = day_up_strs = None  # 同花顺 近1~10 日汇总(Excel 用)
        xuangu_stat_line = None
        xuangu_excel_row = None
        # 为同花顺热股补充最近10个交易日的每日涨跌幅(近1日~近10日)及与10日均线的百分比距离
        day_headers = [f"近{i}日" for i in range(1, 11)]
        ma10_col = "距10日线%"
        for s in ths_stocks:
            code = s.get('code', '')
            for k in range(1, 11):
                s[f'近{k}日'] = ''
            s[ma10_col] = ''
            if code:
                changes, ma10_dist = self._get_stock_recent_10day_and_ma10(code)
                if changes and len(changes) >= 10:
                    # 近1日=最近1个交易日,近10日=最近第10个交易日;changes[0]=10天前,changes[9]=最近1天
                    for k in range(1, 11):
                        s[f'近{k}日'] = changes[10 - k]
                if ma10_dist is not None:
                    s[ma10_col] = ma10_dist
        fish_phase_col = '鱼身鱼尾'
        for s in ths_stocks:
            s[fish_phase_col] = ''
            code = (s.get('code') or '').strip()
            if code:
                code6 = code[-6:].zfill(6)
                try:
                    _ms_f = self._check_ma_status(code6)
                    if _ms_f.get('fish_body'):
                        s[fish_phase_col] = '鱼身'
                    elif _ms_f.get('fish_tail'):
                        s[fish_phase_col] = '鱼尾'
                except Exception:
                    pass
        golden_col = '黄金股'
        for s in ths_stocks:
            s[golden_col] = ''
            code = (s.get('code') or '').strip()
            name = (s.get('name') or '').strip()
            if code:
                try:
                    if self._check_golden_stock_recent_20d(code, name):
                        s[golden_col] = '黄金股'
                except Exception:
                    pass
        # 五日最低阈值附近 + 站上1日线(与「信号」红五星同源 _holding_red_star_signal_5d_low_ma1)
        star_col = '★'
        for s in ths_stocks:
            s[star_col] = ''
            code = (s.get('code') or '').strip()
            if code:
                code6 = code[-6:].zfill(6)
                try:
                    if self._holding_red_star_signal_5d_low_ma1(code6):
                        s[star_col] = '★'
                except Exception:
                    pass
        # 日K 昨未站上1日线、今收站上 → ▲(与「信号」/持仓检测同源)
        tri_col = '▲'
        for s in ths_stocks:
            s[tri_col] = ''
            code = (s.get('code') or '').strip()
            if code:
                code6 = code[-6:].zfill(6)
                try:
                    if self._signal_ma1_close_crossed_up_last_bar(code6):
                        s[tri_col] = '▲'
                except Exception:
                    pass
        # 同花顺:补充东财今日大单净流入;底部汇总为近1~10 每日的日均涨跌%、上涨占比,及大单合计/均值
        if ths_stocks:
            big_order_map = self._map_codes_to_big_order_net_amount()
            for s in ths_stocks:
                code = (s.get('code') or '')[-6:].zfill(6) if s.get('code') else ''
                s['大单净额'] = big_order_map.get(code) if code else None
            def _fmt_flow_popup(v):
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    return "--"
                try:
                    x = float(v)
                    if abs(x) >= 1e8:
                        return f"{x/1e8:+.2f}亿"
                    if abs(x) >= 1e4:
                        return f"{x/1e4:+.2f}万"
                    return f"{x:+.0f}"
                except (TypeError, ValueError):
                    return "--"
            day_avg_strs = []
            day_up_strs = []
            for k in range(1, 11):
                key = f'近{k}日'
                vals = []
                for s in ths_stocks:
                    v = s.get(key)
                    try:
                        if v not in (None, ''):
                            vals.append(float(v))
                    except (TypeError, ValueError):
                        pass
                n_valid = len(vals)
                if n_valid:
                    avg_k = sum(vals) / n_valid
                    n_up = sum(1 for x in vals if x > 0)
                    pct = 100.0 * n_up / n_valid
                    day_avg_strs.append(f"{avg_k:+.2f}%")
                    day_up_strs.append(f"{pct:.1f}%(涨{n_up}/{n_valid})")
                else:
                    day_avg_strs.append("--")
                    day_up_strs.append("--")
            big_vals = []
            for s in ths_stocks:
                x = s.get('大单净额')
                if x is None or (isinstance(x, float) and pd.isna(x)):
                    continue
                try:
                    big_vals.append(float(x))
                except (TypeError, ValueError):
                    pass
            sum_big = sum(big_vals) if big_vals else None
            avg_big = (sum_big / len(big_vals)) if big_vals else None
            sum_str = _fmt_flow_popup(sum_big)
            avg_big_str = _fmt_flow_popup(avg_big)
            ths_sum_big_total_str, ths_sum_big_avg_str = sum_str, avg_big_str
            n_cols = 18  # 代码/名称/鱼身鱼尾/黄金股/★/▲/逻辑 + 近1..10 + 距10日线%
            r1 = ['-', '【同花顺汇总】', '', '', '', '', '近1~10日均涨跌%'] + day_avg_strs + ['--']
            r2 = ['-', '', '', '', '', '', '上涨家数占比'] + day_up_strs + ['--']
            r3 = ['-', '', '', '', '', '', f'大单净额合计{sum_str}', f'大单平均净额{avg_big_str}'] + [''] * (n_cols - 8)
            ths_stat_line1 = '\t'.join(r1)
            ths_stat_line2 = '\t'.join(r2)
            ths_stat_line3 = '\t'.join(r3)
        # 选股通板块汇总:平均涨跌幅、涨跌家数合计及占比、涨停合计及占「涨+跌+平」合计%、资金流向合计(亿)
        if xuangu_sectors:
            def _xg_parse_pct_zhangfu(v):
                if v is None or v == '':
                    return None
                s = str(v).strip().rstrip('%')
                try:
                    return float(s)
                except (TypeError, ValueError):
                    m = re.search(r'([+-]?\d+\.?\d*)', s)
                    if m:
                        try:
                            return float(m.group(1))
                        except ValueError:
                            pass
                    return None
            def _xg_parse_jdjs(v):
                """涨跌家数 如 13/18/0 → 涨跌平;无法解析返回 (None,None,None)"""
                if v is None or str(v).strip() == '':
                    return None, None, None
                s = str(v).strip()
                m = re.match(r'^(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*$', s)
                if m:
                    return int(m.group(1)), int(m.group(2)), int(m.group(3))
                m2 = re.match(r'^(\d+)\s*/\s*(\d+)\s*$', s)
                if m2:
                    return int(m2.group(1)), int(m2.group(2)), 0
                return None, None, None
            def _xg_parse_zt(v):
                if v is None or str(v).strip() == '':
                    return None
                try:
                    return int(float(str(v).strip()))
                except (TypeError, ValueError):
                    return None
            def _xg_parse_flow_yi_units(v):
                """资金流向 → 以『亿』为单位的 float,无法解析返回 None"""
                if v is None or str(v).strip() == '':
                    return None
                s = str(v).strip().replace(',', '')
                m = re.search(r'([+-]?\d+\.?\d*)\s*亿', s)
                if m:
                    return float(m.group(1))
                m = re.search(r'([+-]?\d+\.?\d*)\s*万', s)
                if m:
                    return float(m.group(1)) / 10000.0
                m = re.search(r'([+-]?\d+\.?\d*)', s)
                if m:
                    return float(m.group(1))
                return None
            pcts = []
            tu = td = tf = 0
            sum_zt = 0
            flows_yi = []
            for s in xuangu_sectors:
                pct = _xg_parse_pct_zhangfu(s.get('涨跌幅'))
                if pct is not None:
                    pcts.append(pct)
                u, d, f = _xg_parse_jdjs(s.get('涨跌家数'))
                if u is not None:
                    tu += u
                    td += d
                    tf += f
                zt = _xg_parse_zt(s.get('涨停数'))
                if zt is not None:
                    sum_zt += zt
                fy = _xg_parse_flow_yi_units(s.get('资金流向'))
                if fy is not None:
                    flows_yi.append(fy)
            avg_pct = sum(pcts) / len(pcts) if pcts else None
            avg_str = f"{avg_pct:+.2f}%" if avg_pct is not None else "--"
            tot_udf = tu + td + tf
            if tot_udf > 0:
                jdjs_str = (
                    f"合计{tu}/{td}/{tf} "
                    f"涨{100.0 * tu / tot_udf:.1f}% "
                    f"跌{100.0 * td / tot_udf:.1f}% "
                    f"平{100.0 * tf / tot_udf:.1f}%"
                )
                p_zt = 100.0 * sum_zt / tot_udf
                zt_col = f"合计{sum_zt}(占总体{p_zt:.1f}%)"
            else:
                jdjs_str = "--"
                zt_col = f"合计{sum_zt}" if sum_zt else "--"
            flow_sum = sum(flows_yi) if flows_yi else None
            flow_str = f"{flow_sum:+.2f}亿" if flow_sum is not None else "--"
            xuangu_stat_line = (
                f"-\t【{len(xuangu_sectors)}板块汇总】\t平均{avg_str}\t{jdjs_str}\t{zt_col}\t{flow_str}\t"
            )
            xuangu_excel_row = {
                '板块名': '-',
                '涨跌幅': f'平均 {avg_str}',
                '涨跌家数': jdjs_str,
                '涨停数': zt_col,
                '资金流向': flow_str,
                '领涨股': '',
            }
        ttk.Label(top, text=f"选股通板块 {len(xuangu_sectors)} 条(黑色) + 同花顺股票 {len(ths_stocks)} 条(红色)", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        list_frame = ttk.Frame(top)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 8))
        text_widget = tk.Text(list_frame, height=22, font=("Consolas", 12), wrap=tk.NONE)
        scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=text_widget.yview)
        scroll_x = ttk.Scrollbar(top, orient=tk.HORIZONTAL, command=text_widget.xview)
        text_widget.config(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(fill=tk.X)
        text_widget.tag_configure("xuangutong", foreground="black")
        text_widget.tag_configure("tonghuashun", foreground="red")
        text_widget.tag_configure("tonghuashun_near_ma10", foreground="blue")  # 距10日线%绝对值<3%时名称和距10日线%蓝色;10日涨跌幅中跌幅蓝色
        text_widget.tag_configure("fish_body", foreground="#b71c1c", font=("Consolas", 12, "bold"))
        text_widget.tag_configure("fish_tail", foreground="#1b5e20", font=("Consolas", 12, "bold"))
        text_widget.tag_configure("golden_stock", foreground="#b8860b", font=("Consolas", 12, "bold"))
        text_widget.tag_configure("red_star_hot", foreground="red", font=("Consolas", 12, "bold"))
        text_widget.tag_configure("red_tri_hot", foreground="red", font=("Consolas", 12, "bold"))
        text_widget.tag_configure("header", foreground="blue", font=("TkDefaultFont", 12, "bold"))
        # 显示选股通板块数据
        if xuangu_sectors:
            text_widget.insert("end", "===== 选股通板块数据 =====\n", "header")
            text_widget.insert("end", "板块名\t涨跌幅\t涨跌家数\t涨停数\t资金流向\t领涨股\n", "xuangutong")
            for s in xuangu_sectors:
                line = f"{s.get('板块名', '')}\t{s.get('涨跌幅', '')}\t{s.get('涨跌家数', '')}\t{s.get('涨停数', '')}\t{s.get('资金流向', '')}\t{s.get('领涨股', '')}\n"
                text_widget.insert("end", line, "xuangutong")
            if xuangu_stat_line:
                text_widget.insert("end", xuangu_stat_line + "\n", "header")
            text_widget.insert("end", "\n")
        # 显示同花顺股票数据(含最近10日涨跌幅、距10日线%)
        # 距10日线%绝对值<3%时名称和距10日线%蓝色;10日涨跌幅中涨幅红、跌幅蓝
        if ths_stocks:
            text_widget.insert("end", "===== 同花顺热股+逻辑 =====\n", "header")
            header_row = (
                "代码\t名称\t鱼身鱼尾\t黄金股\t★\t▲\t逻辑/概念标签\t"
                + "\t".join(day_headers)
                + "\t"
                + ma10_col
                + "\n"
            )
            text_widget.insert("end", header_row, "tonghuashun")
            for s in ths_stocks:
                logic = s.get('逻辑', '') or ''
                ma10_val = s.get(ma10_col, '')
                fish_txt = (s.get(fish_phase_col, '') or '').strip()
                star_txt = (s.get(star_col, '') or '').strip()
                tri_txt = (s.get(tri_col, '') or '').strip()
                try:
                    ma10_abs = abs(float(ma10_val)) if ma10_val not in (None, '') else 999
                    near_ma10 = ma10_abs < 3.0
                except (TypeError, ValueError):
                    near_ma10 = False
                name_tag = "tonghuashun_near_ma10" if near_ma10 else "tonghuashun"
                ma10_tag = "tonghuashun_near_ma10" if near_ma10 else "tonghuashun"
                text_widget.insert("end", f"{s.get('code', '')}\t", "tonghuashun")
                text_widget.insert("end", f"{s.get('name', '')}\t", name_tag)
                if fish_txt == '鱼身':
                    text_widget.insert("end", f"{fish_txt}\t", "fish_body")
                elif fish_txt == '鱼尾':
                    text_widget.insert("end", f"{fish_txt}\t", "fish_tail")
                else:
                    text_widget.insert("end", f"{fish_txt}\t", "tonghuashun")
                gold_txt = (s.get(golden_col, '') or '').strip()
                if gold_txt == '黄金股':
                    text_widget.insert("end", f"{gold_txt}\t", "golden_stock")
                else:
                    text_widget.insert("end", "\t", "tonghuashun")
                if star_txt == '★':
                    text_widget.insert("end", f"{star_txt}\t", "red_star_hot")
                else:
                    text_widget.insert("end", "\t", "tonghuashun")
                if tri_txt == '▲':
                    text_widget.insert("end", f"{tri_txt}\t", "red_tri_hot")
                else:
                    text_widget.insert("end", "\t", "tonghuashun")
                text_widget.insert("end", f"{logic}\t", "tonghuashun")
                for i in range(1, 11):
                    val = s.get(f'近{i}日', '')
                    val_str = str(val)
                    try:
                        v = float(val)
                    except (TypeError, ValueError):
                        v = 0
                    day_tag = "tonghuashun" if v >= 0 else "tonghuashun_near_ma10"
                    text_widget.insert("end", val_str, day_tag)
                    text_widget.insert("end", "\t" if i < 10 else "", "tonghuashun")
                text_widget.insert("end", f"\t{ma10_val}\n", ma10_tag)
            if ths_stat_line1:
                text_widget.insert("end", ths_stat_line1 + "\n", "header")
            if ths_stat_line2:
                text_widget.insert("end", ths_stat_line2 + "\n", "header")
            if ths_stat_line3:
                text_widget.insert("end", ths_stat_line3 + "\n", "header")
        def get_full_text():
            lines = []
            if xuangu_sectors:
                lines.append("===== 选股通板块数据 =====")
                lines.append("板块名\t涨跌幅\t涨跌家数\t涨停数\t资金流向\t领涨股")
                for s in xuangu_sectors:
                    lines.append(f"{s.get('板块名', '')}\t{s.get('涨跌幅', '')}\t{s.get('涨跌家数', '')}\t{s.get('涨停数', '')}\t{s.get('资金流向', '')}\t{s.get('领涨股', '')}")
                if xuangu_stat_line:
                    lines.append(xuangu_stat_line.rstrip('\t'))
                lines.append("")
            if ths_stocks:
                lines.append("===== 同花顺热股+逻辑 =====")
                lines.append(
                    "代码\t名称\t鱼身鱼尾\t黄金股\t★\t▲\t逻辑/概念标签\t"
                    + "\t".join(day_headers)
                    + "\t"
                    + ma10_col
                )
                for s in ths_stocks:
                    day_cols = "\t".join(str(s.get(f'近{i}日', '')) for i in range(1, 11))
                    ma10_val = s.get(ma10_col, '')
                    fp = s.get(fish_phase_col, '') or ''
                    gld = s.get(golden_col, '') or ''
                    st = s.get(star_col, '') or ''
                    tr = s.get(tri_col, '') or ''
                    lines.append(
                        f"{s.get('code', '')}\t{s.get('name', '')}\t{fp}\t{gld}\t{st}\t{tr}\t{s.get('逻辑', '')}\t{day_cols}\t{ma10_val}"
                    )
                if ths_stat_line1:
                    lines.append(ths_stat_line1)
                if ths_stat_line2:
                    lines.append(ths_stat_line2)
                if ths_stat_line3:
                    lines.append(ths_stat_line3)
            return "\n".join(lines)
        def open_full_view():
            content = get_full_text()
            if not content.strip():
                messagebox.showinfo("提示", "内容为空", parent=win)
                return
            self.open_full_window_viewer_from_content(content, "热门股非去重")
        text_widget.bind("<Double-Button-1>", lambda e: open_full_view())
        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill=tk.X)
        def save_to_txt():
            path = tk.filedialog.asksaveasfilename(
                parent=win, title="保存为文本文件",
                defaultextension=".txt", filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
            )
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(get_full_text())
                messagebox.showinfo("成功", f"已保存到\n{path}", parent=win)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=win)
        def save_to_excel():
            path = tk.filedialog.asksaveasfilename(
                parent=win, title="保存为 Excel",
                defaultextension=".xlsx", filetypes=[("Excel 文件", "*.xlsx"), ("所有文件", "*.*")]
            )
            if not path:
                return
            try:
                with pd.ExcelWriter(path, engine='openpyxl') as writer:
                    if xuangu_sectors:
                        df1 = pd.DataFrame(xuangu_sectors)
                        if xuangu_excel_row is not None:
                            er = {c: xuangu_excel_row.get(c, '') for c in df1.columns}
                            df1 = pd.concat([df1, pd.DataFrame([er])], ignore_index=True)
                        df1.to_excel(writer, sheet_name='选股通板块', index=False)
                    if ths_stocks:
                        df2 = pd.DataFrame(ths_stocks)
                        if 'code' in df2.columns:
                            df2 = df2.rename(columns={'code': '代码', 'name': '名称', '逻辑': '逻辑/概念'})
                        # 列顺序:代码、名称、鱼身鱼尾、黄金股、★、▲、逻辑/概念、近1日~近10日、距10日线%、大单净额
                        col_order = (
                            ['代码', '名称', fish_phase_col, golden_col, star_col, tri_col, '逻辑/概念']
                            + [f'近{i}日' for i in range(1, 11)]
                            + [ma10_col, '大单净额']
                        )
                        df2 = df2.reindex(columns=[c for c in col_order if c in df2.columns])
                        if day_avg_strs is not None:
                            blank = {c: '' for c in df2.columns}
                            r_avg = blank.copy()
                            r_avg['代码'] = '-'
                            r_avg['名称'] = '【汇总】'
                            if fish_phase_col in r_avg:
                                r_avg[fish_phase_col] = ''
                            if golden_col in r_avg:
                                r_avg[golden_col] = ''
                            if star_col in r_avg:
                                r_avg[star_col] = ''
                            if tri_col in r_avg:
                                r_avg[tri_col] = ''
                            r_avg['逻辑/概念'] = '近1~10日均涨跌%'
                            for i in range(1, 11):
                                cn = f'近{i}日'
                                if cn in r_avg:
                                    r_avg[cn] = day_avg_strs[i - 1]
                            if ma10_col in r_avg:
                                r_avg[ma10_col] = ''
                            if '大单净额' in r_avg:
                                r_avg['大单净额'] = ''
                            r_up = blank.copy()
                            r_up['代码'] = '-'
                            r_up['名称'] = ''
                            if fish_phase_col in r_up:
                                r_up[fish_phase_col] = ''
                            if golden_col in r_up:
                                r_up[golden_col] = ''
                            if star_col in r_up:
                                r_up[star_col] = ''
                            if tri_col in r_up:
                                r_up[tri_col] = ''
                            r_up['逻辑/概念'] = '上涨家数占比'
                            for i in range(1, 11):
                                cn = f'近{i}日'
                                if cn in r_up:
                                    r_up[cn] = day_up_strs[i - 1]
                            if ma10_col in r_up:
                                r_up[ma10_col] = ''
                            if '大单净额' in r_up:
                                r_up['大单净额'] = ''
                            r_big = blank.copy()
                            r_big['代码'] = '-'
                            r_big['名称'] = '【汇总】大单'
                            if fish_phase_col in r_big:
                                r_big[fish_phase_col] = ''
                            if golden_col in r_big:
                                r_big[golden_col] = ''
                            if star_col in r_big:
                                r_big[star_col] = ''
                            if tri_col in r_big:
                                r_big[tri_col] = ''
                            r_big['逻辑/概念'] = f'大单净额合计 {ths_sum_big_total_str}'
                            r_big['近1日'] = f'大单平均净额 {ths_sum_big_avg_str}'
                            df2 = pd.concat([df2, pd.DataFrame([r_avg, r_up, r_big])], ignore_index=True)
                        df2.to_excel(writer, sheet_name='同花顺热股', index=False)
                messagebox.showinfo("成功", f"已保存到\n{path}\n(选股通板块 + 同花顺热股 两个工作表)", parent=win)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=win)
        def save_to_news_info():
            tab_name = f"热门股非去重_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                if save_news_info_to_db(tab_name, get_full_text()):
                    messagebox.showinfo("成功", f"已保存到股票资讯表(news_info),标题: {tab_name}", parent=win)
                else:
                    messagebox.showerror("错误", "保存到股票资讯表失败", parent=win)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=win)
        def save_to_stock_data():
            today = datetime.now().strftime("%Y-%m-%d")
            saved = 0
            # 只保存同花顺的股票数据(有code字段)
            for s in ths_stocks:
                code = s.get('code', '')
                name = s.get('name', '') or code
                logic = s.get('逻辑', '')
                if code and save_stock_to_db(code, name, today, theme='同花顺', analysis_result=logic):
                    saved += 1
            if saved:
                messagebox.showinfo("成功", f"已保存 {saved} 条同花顺股票到股票数据表,日期 {today},逻辑已写入 analysis_result 列。", parent=win)
            else:
                messagebox.showinfo("提示", "未找到有效股票代码,未写入股票数据表。", parent=win)
        ttk.Button(btn_frame, text="保存为 TXT", command=save_to_txt, width=12).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="保存为 Excel", command=save_to_excel, width=12).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="保存到股票资讯表", command=save_to_news_info, width=16).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="保存到股票数据表", command=save_to_stock_data, width=16).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="全窗口浏览", command=open_full_view, width=12).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="关闭", command=win.destroy, width=10).pack(side=tk.LEFT)
        ttk.Label(
            top,
            text="提示:选股通板块(黑色)含涨跌家数/涨停数/资金流向;同花顺(红色)含鱼身鱼尾、黄金股、"
            "★(近5日低阈值附近且站上1日线)、▲(与「信号」相同:日K昨未站上1日线且今收站上)。双击可全窗口浏览。",
            font=("TkDefaultFont", 11),
        ).pack(anchor="w", pady=(4, 0))

    def create_hot_indices_section(self, parent, indices):
        """创建热门指数显示区域 - 包含涨跌幅数据"""
        indices_frame = ttk.LabelFrame(parent, text="🔥 热门指数/ETF (30个) - 含涨跌幅统计", padding=10)
        indices_frame.pack(fill=tk.X, pady=(0, 10))
        # 说明信息
        info_frame = ttk.Frame(indices_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(info_frame, text="📋 以下为30个热门指数和ETF的实时数据,包含5日每日涨跌幅和统计涨跌幅",
                 font=("Arial", 10), foreground="blue").pack()
        # 统计信息
        if indices:
            total_count = len(indices)
            index_count = len([i for i in indices if i.get('type', '') == '指数'])
            etf_count = len([i for i in indices if i.get('type', '') == 'ETF'])
            # 统计信息行
            stats_frame = ttk.Frame(indices_frame)
            stats_frame.pack(fill=tk.X, pady=(0, 10))
            ttk.Label(stats_frame, text=f"总计: {total_count}个", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 20))
            ttk.Label(stats_frame, text=f"指数: {index_count}个", font=("Arial", 10), foreground="blue").pack(side=tk.LEFT, padx=(0, 20))
            ttk.Label(stats_frame, text=f"ETF: {etf_count}个", font=("Arial", 10), foreground="green").pack(side=tk.LEFT)
        # 表头 - 调整宽度和对齐
        header_frame = ttk.Frame(indices_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(header_frame, text="名称", font=("Arial", 9, "bold"), width=12).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Label(header_frame, text="代码", font=("Arial", 9, "bold"), width=10).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Label(header_frame, text="类型", font=("Arial", 9, "bold"), width=6).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Label(header_frame, text="最新价", font=("Arial", 9, "bold"), width=10).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Label(header_frame, text="涨跌幅", font=("Arial", 9, "bold"), width=10).pack(side=tk.LEFT, padx=(0, 2))
        # 5日分析列已移除
        ttk.Label(header_frame, text="10日总计", font=("Arial", 9, "bold"), width=10).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Label(header_frame, text="20日总计", font=("Arial", 9, "bold"), width=10).pack(side=tk.LEFT, padx=(0, 2))
        # 分隔线
        separator = ttk.Separator(indices_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=2)
        # 指数数据 - 按类型分组显示
        index_types = {}
        for index in indices:
            index_type = index.get('type', '其他')
            if index_type not in index_types:
                index_types[index_type] = []
            index_types[index_type].append(index)
        # 按类型显示
        for type_name, type_indices in index_types.items():
            # 类型标题
            type_label = ttk.Label(indices_frame, text=f"📊 {type_name} ({len(type_indices)}个)",
                                 font=("Arial", 11, "bold"), foreground="blue")
            type_label.pack(anchor=tk.W, pady=(10, 5))
            # 该类型的指数数据
            for index in type_indices:
                row_frame = ttk.Frame(indices_frame)
                row_frame.pack(fill=tk.X, pady=1)
                name = index.get('name', '')
                code = index.get('code', '')
                index_type = index.get('type', '')
                latest_price = index.get('最新价', 0)
                change_pct = index.get('涨跌幅', 0)
                ten_day_total = index.get('10日总计涨跌幅', 0)
                twenty_day_total = index.get('20日总计涨跌幅', 0)
                # 涨跌幅颜色
                change_color = "red" if change_pct > 0 else "green" if change_pct < 0 else "black"
                ten_day_color = "red" if ten_day_total > 0 else "green" if ten_day_total < 0 else "black"
                twenty_day_color = "red" if twenty_day_total > 0 else "green" if twenty_day_total < 0 else "black"
                ttk.Label(row_frame, text=name, width=12, font=("Arial", 8)).pack(side=tk.LEFT, padx=(0, 2))
                ttk.Label(row_frame, text=code, width=10, font=("Arial", 8)).pack(side=tk.LEFT, padx=(0, 2))
                ttk.Label(row_frame, text=index_type, width=6, font=("Arial", 8)).pack(side=tk.LEFT, padx=(0, 2))
                ttk.Label(row_frame, text=f"{latest_price:.2f}", width=10, font=("Arial", 8)).pack(side=tk.LEFT, padx=(0, 2))
                ttk.Label(row_frame, text=f"{change_pct:+.2f}%", width=10, font=("Arial", 8),
                         foreground=change_color).pack(side=tk.LEFT, padx=(0, 2))
                # 5日数据列已移除
                ttk.Label(row_frame, text=f"{ten_day_total:+.2f}%", width=10, font=("Arial", 8),
                         foreground=ten_day_color).pack(side=tk.LEFT, padx=(0, 2))
                ttk.Label(row_frame, text=f"{twenty_day_total:+.2f}%", width=10, font=("Arial", 8),
                         foreground=twenty_day_color).pack(side=tk.LEFT, padx=(0, 2))
        # 添加说明信息
        info_frame = ttk.Frame(indices_frame)
        info_frame.pack(fill=tk.X, pady=(15, 0))
        ttk.Label(info_frame, text="💡 以上数据包含实时涨跌幅统计,红色表示上涨,绿色表示下跌",
                 font=("Arial", 9), foreground="gray").pack()

    def show_hotlists_overview(self):
        """热点一览:当天保存的股票数据生成词云图"""
        try:
            win = self._safe_toplevel(self.root)
            win.title("热点一览 - 股票词云图")
            win.geometry("1400x900")
            # 通用数据获取函数(支持日期范围)
            def get_stock_data_by_date_range(start_date, end_date):
                """从数据库获取指定日期范围的股票数据"""
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    # 检查表是否存在
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stock_data'")
                    if not cursor.fetchone():
                        conn.close()
                        return []
                    # 检查列是否存在
                    cursor.execute("PRAGMA table_info(stock_data)")
                    columns = [col[1] for col in cursor.fetchall()]
                    # 构建查询,只查询存在的列
                    select_cols = []
                    if 'stock_code' in columns:
                        select_cols.append('stock_code')
                    if 'stock_name' in columns:
                        select_cols.append('stock_name')
                    if 'price' in columns:
                        select_cols.append('price')
                    if 'change_pct' in columns:
                        select_cols.append('change_pct')
                    if 'volume' in columns:
                        select_cols.append('volume')
                    if 'turnover' in columns:
                        select_cols.append('turnover')
                    if 'market_cap' in columns:
                        select_cols.append('market_cap')
                    if 'pe_ratio' in columns:
                        select_cols.append('pe_ratio')
                    if 'sector' in columns:
                        select_cols.append('sector')
                    if 'theme' in columns:
                        select_cols.append('theme')
                    if 'analysis_result' in columns:
                        select_cols.append('analysis_result')
                    if not select_cols:
                        conn.close()
                        return []
                    # 检查是否有date列
                    if 'date' not in columns:
                        # 如果没有date列,尝试从stock_logic表获取
                        cursor.execute('''
                            SELECT DISTINCT stock_name
                            FROM stock_logic
                            WHERE date >= ? AND date <= ?
                        ''', (start_date, end_date))
                        logic_rows = cursor.fetchall()
                        conn.close()
                        stocks = []
                        for row in logic_rows:
                            stocks.append({
                                'code': '',
                                'name': row[0] if row else '',
                                'price': 0,
                                'change_pct': 0,
                                'volume': 0,
                                'turnover': 0,
                                'market_cap': 0,
                                'pe_ratio': 0,
                                'sector': '',
                                'theme': '',
                                'analysis_result': ''
                            })
                        return stocks
                    query = f'''
                        SELECT {', '.join(select_cols)}
                        FROM stock_data
                        WHERE date >= ? AND date <= ?
                        ORDER BY change_pct DESC
                    '''
                    cursor.execute(query, (start_date, end_date))
                    rows = cursor.fetchall()
                    conn.close()
                    stocks = []
                    for row in rows:
                        stock = {}
                        col_idx = 0
                        if 'stock_code' in select_cols:
                            stock['code'] = row[col_idx] if col_idx < len(row) else ''
                            col_idx += 1
                        else:
                            stock['code'] = ''
                        if 'stock_name' in select_cols:
                            stock['name'] = row[col_idx] if col_idx < len(row) else ''
                            col_idx += 1
                        else:
                            stock['name'] = ''
                        if 'price' in select_cols:
                            stock['price'] = row[col_idx] if col_idx < len(row) else 0
                            col_idx += 1
                        else:
                            stock['price'] = 0
                        if 'change_pct' in select_cols:
                            stock['change_pct'] = row[col_idx] if col_idx < len(row) else 0
                            col_idx += 1
                        else:
                            stock['change_pct'] = 0
                        if 'volume' in select_cols:
                            stock['volume'] = row[col_idx] if col_idx < len(row) else 0
                            col_idx += 1
                        else:
                            stock['volume'] = 0
                        if 'turnover' in select_cols:
                            stock['turnover'] = row[col_idx] if col_idx < len(row) else 0
                            col_idx += 1
                        else:
                            stock['turnover'] = 0
                        if 'market_cap' in select_cols:
                            stock['market_cap'] = row[col_idx] if col_idx < len(row) else 0
                            col_idx += 1
                        else:
                            stock['market_cap'] = 0
                        if 'pe_ratio' in select_cols:
                            stock['pe_ratio'] = row[col_idx] if col_idx < len(row) else 0
                            col_idx += 1
                        else:
                            stock['pe_ratio'] = 0
                        if 'sector' in select_cols:
                            stock['sector'] = row[col_idx] if col_idx < len(row) else ''
                            col_idx += 1
                        else:
                            stock['sector'] = ''
                        if 'theme' in select_cols:
                            stock['theme'] = row[col_idx] if col_idx < len(row) else ''
                            col_idx += 1
                        else:
                            stock['theme'] = ''
                        if 'analysis_result' in select_cols:
                            stock['analysis_result'] = row[col_idx] if col_idx < len(row) else ''
                            col_idx += 1
                        else:
                            stock['analysis_result'] = ''
                        stocks.append(stock)
                    return stocks
                except Exception as e:
                    print(f"获取股票数据失败: {e}")
                    import traceback
                    traceback.print_exc()
                    return []
            # 获取当天股票数据
            def get_today_stock_data():
                """从数据库获取当天的股票数据"""
                today = datetime.now().strftime('%Y-%m-%d')
                return get_stock_data_by_date_range(today, today)
            # 获取周股票数据(最近7天)
            def get_week_stock_data():
                """从数据库获取最近一周的股票数据"""
                end_date = datetime.now()
                start_date = end_date - timedelta(days=7)
                return get_stock_data_by_date_range(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            # 获取月股票数据(最近30天)
            def get_month_stock_data():
                """从数据库获取最近一个月的股票数据"""
                end_date = datetime.now()
                start_date = end_date - timedelta(days=30)
                return get_stock_data_by_date_range(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            # 主布局:左侧词云图,右侧参数调整
            main_frame = ttk.Frame(win)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            # 左侧:词云图显示区域(使用Notebook创建标签页)
            left_frame = ttk.Frame(main_frame)
            left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
            # 右侧:参数调整区域
            right_frame = ttk.LabelFrame(main_frame, text="词云参数调整", padding=10)
            right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0), width=350)
            # 词云参数变量(所有标签页共享)
            width_var = tk.IntVar(value=1000)
            height_var = tk.IntVar(value=600)
            max_words_var = tk.IntVar(value=200)
            background_color_var = tk.StringVar(value="white")
            colormap_var = tk.StringVar(value="viridis")
            font_size_var = tk.IntVar(value=60)
            min_font_size_var = tk.IntVar(value=10)
            # 创建Notebook(标签页容器)
            notebook = ttk.Notebook(left_frame)
            notebook.pack(fill=tk.BOTH, expand=True)
            # 存储每个标签页的数据和组件
            tab_data = {
                'today': {'data': [], 'figure': None, 'canvas': None, 'frame': None, 'control_frame': None},
                'week': {'data': [], 'figure': None, 'canvas': None, 'frame': None, 'control_frame': None},
                'month': {'data': [], 'figure': None, 'canvas': None, 'frame': None, 'control_frame': None}
            }
            # 定义所有函数(在创建按钮之前)
            def collect_all_text_content(stocks):
                """收集所有股票的所有文本内容"""
                all_text = []
                for stock in stocks:
                    # 收集股票名称(重复多次以增加权重)
                    name = stock.get('name', '').strip()
                    if name:
                        # 根据涨跌幅决定重复次数
                        change_pct = abs(stock.get('change_pct', 0))
                        repeat_times = max(1, int(change_pct / 2) + 1)
                        all_text.extend([name] * repeat_times)
                    # 收集板块信息
                    sector = stock.get('sector', '').strip()
                    if sector:
                        all_text.append(sector)
                    # 收集主题信息
                    theme = stock.get('theme', '').strip()
                    if theme:
                        all_text.append(theme)
                    # 收集分析结果
                    analysis = stock.get('analysis_result', '').strip()
                    if analysis:
                        all_text.append(analysis)
                return ' '.join(all_text)
            def process_text_for_wordcloud(text):
                """处理文本,提取关键词用于词云"""
                if not text:
                    return {}
                # 使用jieba分词
                words = jieba.cut(text)
                # 过滤停用词和单字
                stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
                             '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
                             '自己', '这', '等', '为', '与', '及', '或', '但', '而', '如果', '因为', '所以',
                             '股票', '代码', '价格', '涨跌', '成交', '市值', '市盈', '板块', '主题'}
                word_freq = {}
                for word in words:
                    word = word.strip()
                    if len(word) > 1 and word not in stop_words and not word.isdigit():
                        word_freq[word] = word_freq.get(word, 0) + 1
                return word_freq
            def create_wordcloud(stocks, title="股票热点词云图"):
                """创建词云图"""
                try:
                    if not stocks:
                        return None
                    # 收集所有文本内容
                    all_text = collect_all_text_content(stocks)
                    if not all_text.strip():
                        return None
                    # 处理文本,获取词频
                    word_freq = process_text_for_wordcloud(all_text)
                    if not word_freq:
                        return None
                    # 获取参数
                    width = width_var.get()
                    height = height_var.get()
                    max_words = max_words_var.get()
                    bg_color = background_color_var.get()
                    colormap = colormap_var.get()
                    font_size = font_size_var.get()
                    min_font_size = min_font_size_var.get()
                    # 创建词云
                    wordcloud = WordCloud(
                        width=width,
                        height=height,
                        max_words=max_words,
                        background_color=bg_color,
                        colormap=colormap,
                        font_path=None,  # 使用默认字体
                        relative_scaling=0.5,
                        min_font_size=min_font_size,
                        max_font_size=font_size,
                        prefer_horizontal=0.7,
                        margin=10
                    ).generate_from_frequencies(word_freq)
                    # 创建matplotlib图形
                    fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
                    ax.imshow(wordcloud, interpolation='bilinear')
                    ax.axis('off')
                    plt.title(title, fontsize=16, weight='bold', pad=20)
                    plt.tight_layout(pad=0)
                    return fig
                except Exception as e:
                    print(f"创建词云图失败: {e}")
                    import traceback
                    traceback.print_exc()
                    return None
            # 为每个标签页创建独立的函数
            def create_tab_functions(tab_key, get_data_func, tab_title):
                """为每个标签页创建独立的函数"""
                tab_info = tab_data[tab_key]
                def update_wordcloud():
                    """更新词云图"""
                    if not tab_info['data']:
                        messagebox.showwarning("警告", "请先加载股票数据")
                        return
                    try:
                        if not tab_info['frame']:
                            messagebox.showerror("错误", "标签页框架未初始化")
                            return
                        control_frame = tab_info.get('control_frame')
                        for widget in list(tab_info['frame'].winfo_children()):
                            if widget != control_frame:
                                widget.destroy()
                        if tab_info['canvas']:
                            try:
                                tab_info['canvas'].get_tk_widget().destroy()
                            except Exception:
                                pass
                            tab_info['canvas'] = None
                        wordcloud_frame = ttk.Frame(tab_info['frame'])
                        wordcloud_frame.pack(fill=tk.BOTH, expand=True)
                        loading_label = ttk.Label(wordcloud_frame, text="正在生成词云图...",
                                                 font=("TkDefaultFont", 12))
                        loading_label.pack(expand=True)
                        win.update_idletasks()
                        fig = create_wordcloud(tab_info['data'], tab_title)
                        for widget in wordcloud_frame.winfo_children():
                            widget.destroy()
                        if fig:
                            tab_info['figure'] = fig
                            try:
                                from matplotlib.backends.backend_tkagg import (
                                    FigureCanvasTkAgg,
                                )
                                tab_info['canvas'] = FigureCanvasTkAgg(fig, wordcloud_frame)
                                tab_info['canvas'].draw()
                                tab_info['canvas'].get_tk_widget().pack(fill=tk.BOTH, expand=True)
                            except Exception as exc:
                                print(f"显示词云图失败: {exc}")
                                import traceback
                                traceback.print_exc()
                                error_label = ttk.Label(
                                    wordcloud_frame,
                                    text=f"显示词云图失败: {exc!s}",
                                    foreground="red",
                                    font=("TkDefaultFont", 12),
                                )
                                error_label.pack(expand=True)
                        else:
                            error_label = ttk.Label(
                                wordcloud_frame,
                                text="词云图创建失败,请检查数据",
                                foreground="red",
                                font=("TkDefaultFont", 12),
                            )
                            error_label.pack(expand=True)
                    except Exception as exc:
                        print(f"更新词云图失败: {exc}")
                        import traceback
                        traceback.print_exc()
                        if tab_info.get('frame'):
                            error_label = ttk.Label(
                                tab_info['frame'],
                                text=f"更新词云图失败: {exc!s}",
                                foreground="red",
                                font=("TkDefaultFont", 12),
                            )
                            error_label.pack(expand=True)
                        else:
                            messagebox.showerror("错误", f"更新词云图失败: {exc!s}")
                def load_data_and_generate():
                    """加载数据并生成词云图(在主线程中执行)"""
                    try:
                        if not tab_info['frame']:
                            messagebox.showerror("错误", "标签页框架未初始化")
                            return
                        control_frame = tab_info.get('control_frame')
                        for widget in list(tab_info['frame'].winfo_children()):
                            if widget != control_frame:
                                widget.destroy()
                        wordcloud_frame = ttk.Frame(tab_info['frame'])
                        wordcloud_frame.pack(fill=tk.BOTH, expand=True)
                        loading_label = ttk.Label(wordcloud_frame, text="正在加载数据...",
                                                 font=("TkDefaultFont", 12))
                        loading_label.pack(expand=True)
                        win.update_idletasks()
                        tab_info['data'] = get_data_func()
                        for widget in wordcloud_frame.winfo_children():
                            widget.destroy()
                        if not tab_info['data']:
                            no_data_label = ttk.Label(
                                wordcloud_frame,
                                text=f"没有找到{tab_title}的股票数据,请先保存股票数据",
                                foreground="orange",
                                font=("TkDefaultFont", 12),
                            )
                            no_data_label.pack(expand=True)
                            messagebox.showwarning("警告", f"没有找到{tab_title}的股票数据,请先保存股票数据")
                            return
                        update_wordcloud()
                    except Exception as exc:
                        print(f"加载数据失败: {exc}")
                        import traceback
                        traceback.print_exc()
                        if tab_info.get('frame'):
                            error_label = ttk.Label(
                                tab_info['frame'],
                                text=f"加载数据失败: {exc!s}",
                                foreground="red",
                                font=("TkDefaultFont", 12),
                            )
                            error_label.pack(expand=True)
                        messagebox.showerror("错误", f"加载数据失败: {exc!s}")
                return load_data_and_generate, update_wordcloud
            # 创建参数调整界面
            def create_parameter_controls():
                """创建参数调整控件"""
                # 宽度
                ttk.Label(right_frame, text="宽度:").grid(row=0, column=0, sticky=tk.W, pady=5)
                width_scale = ttk.Scale(right_frame, from_=400, to=2000, variable=width_var,
                                      orient=tk.HORIZONTAL, length=200)
                width_scale.grid(row=0, column=1, sticky=tk.EW, padx=5)
                width_label = ttk.Label(right_frame, textvariable=width_var)
                width_label.grid(row=0, column=2, padx=5)
                # 高度
                ttk.Label(right_frame, text="高度:").grid(row=1, column=0, sticky=tk.W, pady=5)
                height_scale = ttk.Scale(right_frame, from_=300, to=1200, variable=height_var,
                                        orient=tk.HORIZONTAL, length=200)
                height_scale.grid(row=1, column=1, sticky=tk.EW, padx=5)
                height_label = ttk.Label(right_frame, textvariable=height_var)
                height_label.grid(row=1, column=2, padx=5)
                # 最大词数
                ttk.Label(right_frame, text="最大词数:").grid(row=2, column=0, sticky=tk.W, pady=5)
                max_words_scale = ttk.Scale(right_frame, from_=50, to=500, variable=max_words_var,
                                           orient=tk.HORIZONTAL, length=200)
                max_words_scale.grid(row=2, column=1, sticky=tk.EW, padx=5)
                max_words_label = ttk.Label(right_frame, textvariable=max_words_var)
                max_words_label.grid(row=2, column=2, padx=5)
                # 最大字体大小
                ttk.Label(right_frame, text="最大字体:").grid(row=3, column=0, sticky=tk.W, pady=5)
                font_size_scale = ttk.Scale(right_frame, from_=20, to=200, variable=font_size_var,
                                           orient=tk.HORIZONTAL, length=200)
                font_size_scale.grid(row=3, column=1, sticky=tk.EW, padx=5)
                font_size_label = ttk.Label(right_frame, textvariable=font_size_var)
                font_size_label.grid(row=3, column=2, padx=5)
                # 最小字体大小
                ttk.Label(right_frame, text="最小字体:").grid(row=4, column=0, sticky=tk.W, pady=5)
                min_font_size_scale = ttk.Scale(right_frame, from_=5, to=50, variable=min_font_size_var,
                                              orient=tk.HORIZONTAL, length=200)
                min_font_size_scale.grid(row=4, column=1, sticky=tk.EW, padx=5)
                min_font_size_label = ttk.Label(right_frame, textvariable=min_font_size_var)
                min_font_size_label.grid(row=4, column=2, padx=5)
                # 背景颜色
                ttk.Label(right_frame, text="背景颜色:").grid(row=5, column=0, sticky=tk.W, pady=5)
                bg_colors = ["white", "black", "gray", "lightblue"]
                bg_combo = ttk.Combobox(right_frame, textvariable=background_color_var,
                                       values=bg_colors, state="readonly", width=15)
                bg_combo.grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=5)
                # 颜色方案
                ttk.Label(right_frame, text="颜色方案:").grid(row=6, column=0, sticky=tk.W, pady=5)
                colormaps = ["viridis", "plasma", "inferno", "magma", "coolwarm", "RdYlGn",
                           "Set2", "Set3", "tab20", "Pastel1", "Pastel2"]
                colormap_combo = ttk.Combobox(right_frame, textvariable=colormap_var,
                                             values=colormaps, state="readonly", width=15)
                colormap_combo.grid(row=6, column=1, columnspan=2, sticky=tk.W, padx=5)
                # 配置列权重
                right_frame.columnconfigure(1, weight=1)
                # 注意:参数变化不会自动更新词云,需要点击"刷新词云"按钮
            # 创建参数调整界面
            create_parameter_controls()
            # 创建3个标签页
            # 1. 当日词云标签页
            today_frame = ttk.Frame(notebook)
            notebook.add(today_frame, text="当日词云")
            tab_data['today']['frame'] = today_frame
            today_control_frame = ttk.Frame(today_frame)
            today_control_frame.pack(fill=tk.X, pady=(0, 10))
            tab_data['today']['control_frame'] = today_control_frame
            today_load_func, today_update_func = create_tab_functions('today', get_today_stock_data, "当日股票热点词云图")
            ttk.Button(today_control_frame, text="生成当日词云", command=today_load_func).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(today_control_frame, text="刷新词云", command=today_update_func).pack(side=tk.LEFT, padx=(0, 10))
            today_initial_label = ttk.Label(today_frame, text="请点击'生成当日词云'按钮加载数据并生成词云",
                                            font=("TkDefaultFont", 12), foreground="gray")
            today_initial_label.pack(expand=True)
            # 2. 周词云标签页
            week_frame = ttk.Frame(notebook)
            notebook.add(week_frame, text="周词云")
            tab_data['week']['frame'] = week_frame
            week_control_frame = ttk.Frame(week_frame)
            week_control_frame.pack(fill=tk.X, pady=(0, 10))
            tab_data['week']['control_frame'] = week_control_frame
            week_load_func, week_update_func = create_tab_functions('week', get_week_stock_data, "周股票热点词云图")
            ttk.Button(week_control_frame, text="生成周词云", command=week_load_func).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(week_control_frame, text="刷新词云", command=week_update_func).pack(side=tk.LEFT, padx=(0, 10))
            week_initial_label = ttk.Label(week_frame, text="请点击'生成周词云'按钮加载最近7天的数据并生成词云",
                                           font=("TkDefaultFont", 12), foreground="gray")
            week_initial_label.pack(expand=True)
            # 3. 月词云标签页
            month_frame = ttk.Frame(notebook)
            notebook.add(month_frame, text="月词云")
            tab_data['month']['frame'] = month_frame
            month_control_frame = ttk.Frame(month_frame)
            month_control_frame.pack(fill=tk.X, pady=(0, 10))
            tab_data['month']['control_frame'] = month_control_frame
            month_load_func, month_update_func = create_tab_functions('month', get_month_stock_data, "月股票热点词云图")
            ttk.Button(month_control_frame, text="生成月词云", command=month_load_func).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(month_control_frame, text="刷新词云", command=month_update_func).pack(side=tk.LEFT, padx=(0, 10))
            month_initial_label = ttk.Label(month_frame, text="请点击'生成月词云'按钮加载最近30天的数据并生成词云",
                                            font=("TkDefaultFont", 12), foreground="gray")
            month_initial_label.pack(expand=True)
        except Exception as e:
            import traceback
            error_msg = f"打开热点一览失败: {e!s}\n\n详细错误信息:\n{traceback.format_exc()}"
            print(error_msg)
            traceback.print_exc()
            try:
                messagebox.showerror("错误", f"打开热点一览失败: {e!s}")
            except:
                print("无法显示错误对话框,错误信息已打印到控制台")

    def show_jiutao_hot_spot_analysis(self):
        """显示韭淘热点分析对话框"""
        win = tk.Toplevel(self.root)
        win.title("韭淘热点分析")
        win.geometry("900x700")
        win.transient(self.root)
        # 日期选择区域
        date_frame = ttk.Frame(win)
        date_frame.pack(fill=tk.X, pady=10, padx=10)
        ttk.Label(date_frame, text="起始日期:").pack(side=tk.LEFT, padx=5)
        start_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        start_date_entry = ttk.Entry(date_frame, textvariable=start_date_var, width=12)
        start_date_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text="结束日期:").pack(side=tk.LEFT, padx=5)
        end_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        end_date_entry = ttk.Entry(date_frame, textvariable=end_date_var, width=12)
        end_date_entry.pack(side=tk.LEFT, padx=5)
        # 分析按钮
        analyze_frame = ttk.Frame(win)
        analyze_frame.pack(fill=tk.X, pady=10, padx=10)
        status_var = tk.StringVar(value="就绪")
        ttk.Label(analyze_frame, textvariable=status_var).pack(side=tk.LEFT, padx=10)
        # 结果显示区域
        result_frame = ttk.Frame(win)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)
        result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, font=('Microsoft YaHei', 11))
        result_text.pack(fill=tk.BOTH, expand=True)
        # 配置文本标签
        result_text.tag_config("jiuyan", background="#E6F3FF", font=('Microsoft YaHei', 11, 'bold'))
        result_text.tag_config("taoguba", background="#FFF3E6", font=('Microsoft YaHei', 11, 'italic'))
        result_text.tag_config("sector1", foreground="#FF5722", font=('Microsoft YaHei', 11, 'bold'))
        result_text.tag_config("sector2", foreground="#4CAF50", font=('Microsoft YaHei', 11, 'bold'))
        result_text.tag_config("sector3", foreground="#2196F3", font=('Microsoft YaHei', 11, 'bold'))
        result_text.tag_config("sector4", foreground="#9C27B0", font=('Microsoft YaHei', 11, 'bold'))
        def run_jiutao_analysis():
            start_date = start_date_var.get().strip()
            end_date = end_date_var.get().strip()
            if not start_date or not end_date:
                messagebox.showwarning("提示", "请输入起始和结束日期。", parent=win)
                return
            status_var.set("分析中...")
            result_text.delete("1.0", tk.END)
            result_text.insert("1.0", f"正在分析{start_date}至{end_date}的韭研和淘股吧数据...\n")
            win.update()
            def work():
                try:
                    # 从资讯表获取数据
                    jiuyan_data = []
                    taoguba_data = []
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        # 获取韭研数据
                        cursor.execute('''
                            SELECT content, created_at FROM news_info
                            WHERE created_at BETWEEN ? AND ?
                            AND content LIKE ?
                            ORDER BY created_at DESC
                        ''', (start_date, end_date, '%韭研%'))
                        jiuyan_rows = cursor.fetchall()
                        jiuyan_data = [(row[0], row[1]) for row in jiuyan_rows]
                        # 获取淘股吧数据
                        cursor.execute('''
                            SELECT content, created_at FROM news_info
                            WHERE created_at BETWEEN ? AND ?
                            AND content LIKE ?
                            ORDER BY created_at DESC
                        ''', (start_date, end_date, '%淘股吧%'))
                        taoguba_rows = cursor.fetchall()
                        taoguba_data = [(row[0], row[1]) for row in taoguba_rows]
                        conn.close()
                    except Exception as e:
                        print(f"从数据库获取数据失败: {e}")
                    # 构建分析结果
                    result = f"韭淘热点分析报告({start_date} - {end_date})\n\n"
                    # 1. 热点板块分析
                    result += "="*80 + "\n"
                    result += "【热点板块分析】\n"
                    result += "="*80 + "\n"
                    # 提取板块信息
                    sectors = {}
                    # 从韭研数据提取板块
                    for content, date in jiuyan_data:
                        # 简单提取板块信息
                        import re
                        matches = re.findall(r'[\u4e00-\u9fa5]+板块', content)
                        for match in matches:
                            if match not in sectors:
                                sectors[match] = {'count': 0, 'sources': []}
                            sectors[match]['count'] += 1
                            sectors[match]['sources'].append(('韭研', date))
                    # 从淘股吧数据提取板块
                    for content, date in taoguba_data:
                        # 简单提取板块信息
                        import re
                        matches = re.findall(r'[\u4e00-\u9fa5]+板块', content)
                        for match in matches:
                            if match not in sectors:
                                sectors[match] = {'count': 0, 'sources': []}
                            sectors[match]['count'] += 1
                            sectors[match]['sources'].append(('淘股吧', date))
                    # 排序板块
                    sorted_sectors = sorted(sectors.items(), key=lambda x: x[1]['count'], reverse=True)
                    if sorted_sectors:
                        for i, (sector, info) in enumerate(sorted_sectors[:4]):
                            result += f"{i+1}. {sector}(提及{info['count']}次)\n"
                            for source, date in info['sources'][:3]:
                                result += f"   - {source} ({date})\n"
                            result += "\n"
                    else:
                        result += "未找到热点板块信息\n\n"
                    # 2. 推荐股票分析
                    result += "="*80 + "\n"
                    result += "【推荐股票分析】\n"
                    result += "="*80 + "\n"
                    # 提取推荐股票
                    stocks = {}
                    # 从韭研数据提取股票
                    for content, date in jiuyan_data:
                        # 简单提取股票信息
                        import re
                        matches = re.findall(r'[\u4e00-\u9fa5]+\(\d{6}\)', content)
                        for match in matches:
                            if match not in stocks:
                                stocks[match] = {'count': 0, 'sources': []}
                            stocks[match]['count'] += 1
                            stocks[match]['sources'].append(('韭研', date))
                    # 从淘股吧数据提取股票
                    for content, date in taoguba_data:
                        # 简单提取股票信息
                        import re
                        matches = re.findall(r'[\u4e00-\u9fa5]+\(\d{6}\)', content)
                        for match in matches:
                            if match not in stocks:
                                stocks[match] = {'count': 0, 'sources': []}
                            stocks[match]['count'] += 1
                            stocks[match]['sources'].append(('淘股吧', date))
                    # 排序股票
                    sorted_stocks = sorted(stocks.items(), key=lambda x: x[1]['count'], reverse=True)
                    if sorted_stocks:
                        for i, (stock, info) in enumerate(sorted_stocks[:10]):
                            result += f"{i+1}. {stock}(推荐{info['count']}次)\n"
                            for source, date in info['sources'][:3]:
                                result += f"   - {source} ({date})\n"
                            result += "\n"
                    else:
                        result += "未找到推荐股票信息\n\n"
                    # 3. 韭研数据摘录
                    result += "="*80 + "\n"
                    result += "【韭研数据摘录】\n"
                    result += "="*80 + "\n"
                    if jiuyan_data:
                        for i, (content, date) in enumerate(jiuyan_data[:5]):
                            result += f"{i+1}. 日期: {date}\n"
                            # 提取关键内容
                            lines = content.split('\n')
                            for line in lines[:10]:  # 只取前10行
                                if line.strip():
                                    result += f"   {line.strip()}\n"
                            result += "\n"
                    else:
                        result += "未找到韭研数据\n\n"
                    # 4. 淘股吧数据摘录
                    result += "="*80 + "\n"
                    result += "【淘股吧数据摘录】\n"
                    result += "="*80 + "\n"
                    if taoguba_data:
                        for i, (content, date) in enumerate(taoguba_data[:5]):
                            result += f"{i+1}. 日期: {date}\n"
                            # 提取关键内容
                            lines = content.split('\n')
                            for line in lines[:10]:  # 只取前10行
                                if line.strip():
                                    result += f"   {line.strip()}\n"
                            result += "\n"
                    else:
                        result += "未找到淘股吧数据\n\n"
                    # 5. AI分析
                    result += "="*80 + "\n"
                    result += "【AI分析】\n"
                    result += "="*80 + "\n"
                    # 构建AI分析提示
                    ai_prompt = f"请分析{start_date}至{end_date}的韭研和淘股吧数据,\n"
                    ai_prompt += f"热点板块:{[sector for sector, _ in sorted_sectors[:5]]}\n"
                    ai_prompt += f"推荐股票:{[stock for stock, _ in sorted_stocks[:10]]}\n"
                    ai_prompt += "请给出当前市场热点分析、投资建议和风险提示。"
                    # 调用AI模型
                    sys_p = "你是资深股票市场分析师,熟悉A股市场的热点板块和游资动向。根据提供的韭研和淘股吧数据,分析当前市场热点、推荐股票的投资价值,并给出风险提示。"
                    ai_result = self.call_ai_model(ai_prompt, sys_p, max_tokens=2048)
                    if ai_result:
                        result += ai_result + "\n"
                    else:
                        result += "AI分析失败,未获取到分析结果。\n"
                except Exception as e:
                    result = f"分析失败:{e}\n"
                def _done():
                    result_text.delete("1.0", tk.END)
                    result_text.insert("1.0", result)
                    # 应用标签样式
                    # 这里可以添加更复杂的标签应用逻辑
                    status_var.set("完成")
                win.after(0, _done)
            import threading
            threading.Thread(target=work, daemon=True).start()
        ttk.Button(analyze_frame, text="开始分析", command=run_jiutao_analysis, width=12).pack(side=tk.RIGHT, padx=5)
        # 关闭按钮
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=10)

    def _get_sector_3day_flow(self, sector_name: str) -> str:
        """获取板块近3日资金流入流出,返回简短描述(供思维导图归类的板块使用)"""
        if not sector_name or sector_name == "未知板块":
            return "近3日资金流: 无板块"
        try:
            if not AKSHARE_AVAILABLE:
                return "近3日资金流: 需akshare"
            # 东方财富行业/概念资金流:先尝试 3 日,部分版本支持 indicator 参数
            for indicator in ("3日", "今日", "5日"):
                try:
                    try:
                        df = ak.stock_sector_fund_flow_rank(indicator=indicator)
                    except (TypeError, Exception):
                        df = ak.stock_sector_fund_flow_rank() if indicator == "3日" else None
                        if df is None:
                            continue
                    if df is None or df.empty:
                        continue
                    # 列名可能是 名称/板块名称/行业名称 等
                    name_col = None
                    for c in ("名称", "板块名称", "行业名称", "板块"):
                        if c in df.columns:
                            name_col = c
                            break
                    if not name_col:
                        name_col = df.columns[0]
                    net_col = None
                    for c in df.columns:
                        if "主力" in str(c) and "净" in str(c) and ("额" in str(c) or "流入" in str(c)):
                            net_col = c
                            break
                    if not net_col and "净流入" in str(df.columns.tolist()):
                        for c in df.columns:
                            if "净流入" in str(c) and "占比" not in str(c):
                                net_col = c
                                break
                    for _, row in df.iterrows():
                        sn = str(row.get(name_col, "")).strip()
                        if sn == sector_name or (sector_name in sn or sn in sector_name):
                            if net_col and net_col in row:
                                try:
                                    val = float(row[net_col])
                                    if abs(val) >= 1e8:
                                        s = f"{val/1e8:+.2f}亿"
                                    elif abs(val) >= 1e4:
                                        s = f"{val/1e4:+.2f}万"
                                    else:
                                        s = f"{val:+.2f}"
                                    return f"近3日资金流({indicator}): {s}"
                                except (TypeError, ValueError):
                                    pass
                            return f"近3日资金流({indicator}): 已找到板块"
                except Exception:
                    continue
            return "近3日资金流: 暂无数据"
        except Exception as e:
            return f"近3日资金流: 获取失败({str(e)[:20]})"

    def _get_sector_top5_leaders(self, sector_name: str) -> list:
        """获取板块前5个龙头股(按涨跌幅排序),返回 [(名称, 代码, 涨跌幅), ...]"""
        if not sector_name or sector_name == "未知板块":
            return []
        try:
            if not AKSHARE_AVAILABLE:
                return []
            cons = ak.stock_board_industry_cons_em(symbol=sector_name)
            if cons is None or cons.empty:
                return []
            # 涨跌幅列名可能是 涨跌幅/涨幅
            pct_col = None
            for c in ("涨跌幅", "涨幅", "涨跌"):
                if c in cons.columns:
                    pct_col = c
                    break
            name_col = next((c for c in ("名称", "股票名称", "简称") if c in cons.columns), cons.columns[1] if len(cons.columns) > 1 else None)
            code_col = next((c for c in ("代码", "股票代码", "序号") if c in cons.columns), cons.columns[0] if len(cons.columns) > 0 else None)
            if not pct_col or not name_col:
                return []
            cons = cons.sort_values(by=pct_col, ascending=False)
            top5 = []
            for _, row in cons.head(5).iterrows():
                try:
                    name = str(row.get(name_col, ""))
                    code = str(row.get(code_col, ""))
                    pct = row.get(pct_col, 0)
                    if isinstance(pct, (int, float)):
                        pct_str = f"{pct:+.2f}%"
                    else:
                        pct_str = str(pct)
                    top5.append((name, code, pct_str))
                except Exception:
                    continue
            return top5
        except Exception:
            return []

    def _fetch_sector_cons(self, sector_name):
        """获取板块成分股列表 [多源 fallback], 返回 [(code, name, pct_chg), ...]"""
        import re
        result = []
        # 源1: 东财行业成分股 (交易时段可用)
        try:
            import akshare as ak
            df = ak.stock_board_industry_cons_em(symbol=sector_name)
            if df is not None and len(df) > 0:
                code_col = "代码" if "代码" in df.columns else df.columns[0]
                name_col = "名称" if "名称" in df.columns else df.columns[1]
                pct_col = "涨跌幅" if "涨跌幅" in df.columns else None
                for _, r in df.iterrows():
                    m = re.search(r"(\d{6})", str(r[code_col]).strip())
                    if not m: continue
                    code6 = m.group(1)
                    name = str(r[name_col]).strip()
                    pct = float(r[pct_col]) if pct_col and pct_col in df.columns else 0
                    result.append((code6, name, pct))
                result.sort(key=lambda x: x[2], reverse=True)
                print(f"[板块] ✅ {sector_name} 东财行业: {len(result)}只")
                return result[:50]
        except Exception as e:
            print(f"[板块] 东财 {sector_name} fail: {str(e)[:50]}")
        # 源2: 东财概念成分股
        try:
            import akshare as ak
            df2 = ak.stock_board_concept_cons_em(symbol=sector_name)
            if df2 is not None and len(df2) > 0:
                code_col = "代码" if "代码" in df2.columns else df2.columns[0]
                name_col = "名称" if "名称" in df2.columns else df2.columns[1]
                pct_col = "涨跌幅" if "涨跌幅" in df2.columns else None
                for _, r in df2.iterrows():
                    m = re.search(r"(\d{6})", str(r[code_col]).strip())
                    if not m: continue
                    code6 = m.group(1)
                    name = str(r[name_col]).strip()
                    pct = float(r[pct_col]) if pct_col and pct_col in df2.columns else 0
                    result.append((code6, name, pct))
                result.sort(key=lambda x: x[2], reverse=True)
                print(f"[板块] ✅ {sector_name} 东财概念: {len(result)}只")
                return result[:50]
        except Exception as e:
            print(f"[板块] 东财概念 {sector_name} fail: {str(e)[:50]}")
        # 源3 (稳定): tushare 申万行业 index_classify + index_member + daily + stock_basic
        try:
            import time as _time

            import tushare as _ts
            _pro = _ts.pro_api()
            # 3a. 概念→申万行业关键词映射表 (同花顺/东财概念名 → 申万L2关键词)
            _CONCEPT_TO_SW = {
                "猪肉": "养殖", "养殖": "养殖", "禽": "养殖", "水产": "养殖",
                "酿酒": "白酒", "白酒": "白酒", "黄酒": "白酒", "啤酒": "食品",
                "饮料": "食品", "食品": "食品", "乳业": "食品",
                "新能源": "电力设备", "光伏": "电力设备", "风电": "电力设备",
                "锂电池": "电池", "电池": "电池", "储能": "电池",
                "半导体": "半导体", "芯片": "半导体", "集成电路": "半导体",
                "人工智能": "软件开发", "AI": "软件开发", "算力": "软件开发",
                "计算机": "软件开发", "软件": "软件开发",
                "医药": "医疗服务", "生物": "医疗服务", "医疗": "医疗服务",
                "银行": "银行", "证券": "证券", "保险": "保险", "券商": "证券",
                "地产": "房地产", "房地产": "房地产",
                "汽车": "汽车整车", "新能源车": "汽车整车", "智能驾驶": "汽车零部件",
                "军工": "航空装备", "航天": "航空装备", "国防": "航空装备",
                "机器人": "自动化设备", "智能制造": "自动化设备", "自动化": "自动化设备",
                "消费": "美容护理", "免税": "美容护理", "旅游": "酒店餐饮",
                "煤炭": "煤炭", "有色": "工业金属", "钢铁": "钢铁", "化工": "化学制品",
                "电力": "电力", "燃气": "燃气",
                "通信": "通信设备", "5G": "通信设备", "光纤": "通信设备",
                "传媒": "数字媒体", "游戏": "数字媒体", "影视": "数字媒体",
                "教育": "教育",
            }
            # 尝试映射: 遍历关键词表, 看 sector_name 里包含哪个关键词
            _mapped_name = sector_name
            for _key, _sw_kw in _CONCEPT_TO_SW.items():
                if _key in sector_name:
                    _mapped_name = _sw_kw; break
            # 3b. 模糊匹配板块名 → 申万二级行业
            _cls = _pro.index_classify(level="L2", src="SW2021")
            if _cls is None or len(_cls) == 0:
                print("[板块] tushare index_classify 空"); return result
            # 先用映射后的关键词匹配, 再用原名匹配
            _matches = _cls[_cls["industry_name"].str.contains(_mapped_name[:2], na=False)]
            if len(_matches) == 0 and _mapped_name != sector_name:
                # 映射后也没匹配, 试映射后的完整词
                _matches = _cls[_cls["industry_name"].str.contains(_mapped_name, na=False)]
            if len(_matches) == 0:
                # 最后兜底: 原名
                _matches = _cls[_cls["industry_name"].str.contains(sector_name[:2], na=False)]
            if len(_matches) == 0:
                print(f"[板块] tushare 找不到行业匹配 {sector_name}(映射→{_mapped_name})"); return result
            # 取第一个匹配
            _icode = _matches["index_code"].values[0]
            _iname = _matches["industry_name"].values[0]
            print(f"[板块] tushare匹配: {sector_name} → {_icode}({_iname})")
            # 3b. 拿成分股
            _mem = _pro.index_member(index_code=_icode)
            if _mem is None or len(_mem) == 0:
                print("[板块] tushare index_member 空"); return result
            _codes = _mem["con_code"].tolist()
            # 3c. 拿 stock_basic 做代码→名称映射
            _sb = _pro.stock_basic(exchange="", list_status="L")
            _code_to_name = dict(zip(_sb["ts_code"], _sb["name"])) if _sb is not None else {}
            # 3d. 找最近交易日 + 拉 daily 拿涨跌幅
            _today = _time.strftime("%Y%m%d")
            _cal = _pro.trade_cal(exchange="SSE", start_date="20260801", end_date=_today, is_open="1")
            if _cal is not None and len(_cal) > 0:
                _td = max(_cal["cal_date"].tolist())
            else:
                _td = _today
            _daily = _pro.daily(trade_date=_td)
            if _daily is not None:
                _daily_map = dict(zip(_daily["ts_code"], _daily["pct_chg"]))
            else:
                _daily_map = {}
            # 组装结果
            for _tc in _codes[:80]:  # 最多取80只
                _m = re.search(r"(\d{6})", _tc)
                if not _m: continue
                _code6 = _m.group(1)
                _name = _code_to_name.get(_tc, _tc)
                _pct = float(_daily_map.get(_tc, 0)) if _tc in _daily_map else 0
                result.append((_code6, _name, _pct))
            result.sort(key=lambda x: x[2], reverse=True)
            print(f"[板块] ✅ {sector_name} tushare: {len(result)}只 (交易日={_td})")
            return result[:50]
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"[板块] tushare {sector_name} fail: {e}")
        return result  # 空

    def _build_sw_sector_map(self, pro, df_candidates=None):
        """📈 轻量板块映射: 用 stock_basic 的 industry 字段 (0次额外API!) + 名称关键词兜底"""
        sector_map = {}
        try:
            # stock_basic 已在 L43948 拉过, 里面有 industry 字段!
            # 这里如果有传入候选股的 stock_basic, 直接用
            # 复用 self._last_sb 如果有缓存, 否则临时拉一次全市场(1次API)
            sb_cache = getattr(self, "_last_stock_basic_df", None)
            if sb_cache is None:
                sb_cache = pro.stock_basic(exchange="", list_status="L",
                    fields="ts_code,name,industry,area,list_date")
                self._last_stock_basic_df = sb_cache
            if sb_cache is not None and len(sb_cache) > 0:
                for _, row in sb_cache.iterrows():
                    tsc = row.get("ts_code", "")
                    ind = str(row.get("industry", "") or "").strip()
                    if tsc and ind:
                        sector_map[tsc] = ind
            print(f"[量价齐升] 板块映射: {len(sector_map)} 只 (stock_basic)")
        except Exception as e:
            print(f"[量价齐升] stock_basic 板块映射失败: {e}, 用名称关键词兜底")
        return sector_map

    def _fallback_sector_by_name(self, name):
        """兜底: 根据股票名关键词匹配板块"""
        if not name:
            return "其他"
        name_map = [
            ("银行", "银行"), ("证券", "证券"), ("保险", "保险"), ("券商", "证券"),
            ("白酒", "白酒"), ("啤酒", "食品饮料"), ("饮料", "食品饮料"), ("食品", "食品饮料"),
            ("医药", "医药生物"), ("生物", "医药生物"), ("医疗", "医药生物"),
            ("半导体", "电子"), ("芯片", "电子"), ("集成电路", "电子"),
            ("软件", "计算机"), ("计算机", "计算机"), ("科技", "计算机"),
            ("电子", "电子"),
            ("新能源", "电力设备"), ("光伏", "电力设备"), ("风电", "电力设备"), ("电池", "电力设备"),
            ("汽车", "汽车"),
            ("地产", "房地产"), ("房产", "房地产"),
            ("煤炭", "煤炭"), ("钢铁", "钢铁"), ("有色", "有色金属"),
            ("化工", "化工"), ("石油", "石油石化"),
            ("农业", "农林牧渔"), ("养殖", "农林牧渔"),
            ("机械", "机械设备"), ("设备", "机械设备"),
            ("建筑", "建筑装饰"),
            ("通信", "通信设备"),
            ("传媒", "传媒"), ("游戏", "传媒"),
            ("军工", "国防军工"), ("航天", "国防军工"),
            ("环保", "环保"),
        ]
        for kw, sec in name_map:
            if kw in name:
                return sec
        return "其他"

    def _open_sector_detail(self, sector_name):
        """双击板块卡片 → 弹窗显示成分股列表 + 批量游资心法扫描"""
        win = tk.Toplevel(self.root)
        win.title(f"📂 {sector_name} - 板块成分股")
        win.geometry("720x520"); win.transient(self.root)
        win.grab_set()
        # 顶栏: 标题+状态
        top = tk.Frame(win, bg="#1A237E"); top.pack(fill=tk.X)
        tk.Label(top, text=f"📂 {sector_name}", bg="#1A237E", fg="white",
                 font=("", 12, "bold")).pack(side=tk.LEFT, padx=8, pady=4)
        status_var = tk.StringVar(value="⏳ 正在加载成分股...")
        tk.Label(top, textvariable=status_var, bg="#1A237E", fg="#FFD54F",
                 font=("", 9)).pack(side=tk.LEFT, padx=8)
        tk.Button(top, text="🔄", bg="#C62828", fg="white", font=("", 9, "bold"),
                  padx=6, pady=0,
                  command=lambda: self._bg_load_sector_cons(sector_name, tree, status_var)).pack(side=tk.RIGHT, padx=6)

        # 操作按钮栏
        btn_row = tk.Frame(win); btn_row.pack(fill=tk.X, padx=4, pady=3)
        tk.Button(btn_row, text="🦅 批量游资心法扫描 (选中行)", bg="#C62828", fg="white",
                  font=("", 9, "bold"), padx=8, pady=2,
                  command=lambda: self._batch_hotmoney_from_sector(tree)).pack(side=tk.LEFT)
        tk.Button(btn_row, text="📊 扫描全部 Top 10", bg="#1565C0", fg="white",
                  font=("", 9), padx=8, pady=2,
                  command=lambda: self._batch_hotmoney_topn(tree, 10)).pack(side=tk.LEFT, padx=4)
        tk.Label(btn_row, text="💡 双击行 = 直接打开该股游资心法", fg="#888",
                 font=("", 8)).pack(side=tk.RIGHT)

        # Treeview 成分股列表
        cols = ("code", "name", "pct", "scan")
        tree_frame = tk.Frame(win); tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="extended")
        tree.heading("code", text="代码"); tree.heading("name", text="股票名称")
        tree.heading("pct", text="涨跌幅%"); tree.heading("scan", text="心法")
        tree.column("code", width=80, anchor="center")
        tree.column("name", width=120, anchor="w")
        tree.column("pct", width=80, anchor="e")
        tree.column("scan", width=60, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); vsb.pack(side=tk.RIGHT, fill=tk.Y)
        # 保存引用
        win._sector_tree = tree; win._sector_name = sector_name
        # 双击行 → 调已有的完整游资心法弹窗 (auto触发)
        def _on_tree_dblclick(e):
            sel = tree.selection()
            if not sel: return
            item = tree.item(sel[0])
            code = str(item["values"][0]); name = str(item["values"][1])
            self._open_hotmoney_single_dialog(auto_code=code, auto_name=name)
        tree.bind("<Double-1>", _on_tree_dblclick)

        # 后台加载
        self._bg_load_sector_cons(sector_name, tree, status_var)

    def _bg_load_sector_cons(self, sector_name, tree, status_var):
        """后台线程拉板块成分股 → 填 Treeview"""
        def worker():
            try:
                cons = self._fetch_sector_cons(sector_name)
                self.root.after(0, lambda: self._fill_sector_tree(tree, cons, status_var, sector_name))
            except Exception as e:
                self.root.after(0, lambda e=e: status_var.set(f"❌ 加载失败: {e}"))
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _fill_sector_tree(self, tree, cons, status_var, sector_name):
        """主线程填成分股 Treeview"""
        tree.delete(*tree.get_children())
        if not cons:
            tree.insert("", tk.END, values=("--", "⚠️ 无成分股数据 (东财交易时段才通)", "--", "--"))
            status_var.set(f"❌ {sector_name}: 无成分股数据")
            return
        for code, name, pct in cons:
            pct_s = f"{pct:+.2f}" if pct != 0 else "--"
            tag = "up" if pct > 0 else ("dn" if pct < 0 else "flat")
            tree.insert("", tk.END, values=(code, name, pct_s, "待扫描"), tags=(tag,))
        tree.tag_configure("up", foreground="#C62828")
        tree.tag_configure("dn", foreground="#2E7D32")
        tree.tag_configure("flat", foreground="#666")
        status_var.set(f"✅ {sector_name}: {len(cons)} 只成分股  (双击行 = 个股心法)")

    def _batch_hotmoney_from_sector(self, tree):
        """批量扫描选中行的游资心法"""
        sel = tree.selection()
        if not sel:
            sel = tree.get_children()[:10]  # 没选中就扫前10
        self._do_batch_hotmoney(tree, list(sel))

    def _batch_hotmoney_topn(self, tree, n=10):
        """批量扫描 Top N"""
        self._do_batch_hotmoney(tree, list(tree.get_children()[:n]))

    def _do_batch_hotmoney(self, tree, sel_items):
        """批量游资心法扫描核心逻辑 (后台线程 + 进度)"""
        if not sel_items: return
        # 收集股票列表
        stocks = []
        for iid in sel_items:
            vals = tree.item(iid)["values"]
            if vals and vals[0] != "--":
                stocks.append((str(vals[0]), str(vals[1]), iid))
        if not stocks: return
        # 进度窗口
        prog_win = tk.Toplevel(self.root)
        prog_win.title(f"🦅 批量扫描 {len(stocks)} 只股票")
        prog_win.geometry("400x200"); prog_win.transient(self.root)
        tk.Label(prog_win, text=f"🦅 正在扫描 {len(stocks)} 只股票的游资心法...",
                 font=("", 11, "bold")).pack(pady=10)
        prog_bar = ttk.Progressbar(prog_win, maximum=len(stocks), length=340)
        prog_bar.pack(pady=4)
        prog_lbl = tk.Label(prog_win, text="0/0", fg="#555"); prog_lbl.pack()
        done_var = {"n": 0}
        # 批量处理
        def worker():
            results = []
            for idx, (code, name, _iid) in enumerate(stocks):
                try:
                    res = self._quick_hotmoney_score(code, name)
                    results.append((code, name, res))
                except Exception as e:
                    results.append((code, name, {"error": str(e)}))
                done_var["n"] = idx + 1
                self.root.after(0, lambda i=idx+1, t=len(stocks): (
                    prog_bar.configure(value=i), prog_lbl.configure(text=f"{i}/{t}")
                ))
            self.root.after(0, lambda: self._show_batch_hotmoney_results(results, prog_win))
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _quick_hotmoney_score(self, code, name):
        """快速单只游资评分 (供批量扫描用, 返回字典)"""
        import akshare as ak
        import numpy as np
        try:
            # 拉K线
            df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                    start_date=(__import__("datetime").date.today()-__import__("datetime").timedelta(days=200)).strftime("%Y%m%d"),
                                    end_date=__import__("datetime").date.today().strftime("%Y%m%d"),
                                    adjust="qfq")
            if df is None or len(df) < 60:
                return {"error": "K线数据不足"}
            close = df["收盘"].values
            pct = df["涨跌幅"].values if "涨跌幅" in df.columns else np.diff(df["收盘"])/df["收盘"][:-1]*100
            # 简单量化指标
            m5 = np.mean(close[-5:]); m10 = np.mean(close[-10:]); m20 = np.mean(close[-20:]); m60 = np.mean(close[-60:])
            ma_ok = m5 > m10 > m20 > m60
            ma_bad = m5 < m10 < m20 < m60
            last_pct = pct[-1] if len(pct) > 0 else 0
            vol_shrink = df["成交量"].iloc[-1] < df["成交量"].rolling(20).mean().iloc[-1] * 0.7 if "成交量" in df.columns else False
            up_20d = (close[-1] / close[-20] - 1) * 100
            dist60h = (close[-1] / np.max(close[-60:]) - 1) * 100
            # 7位游资简单打分
            scores = {}
            scores["赵老哥"] = 80 if ma_ok and last_pct > 3 else (30 if ma_bad else 50)
            scores["炒股养家"] = 75 if up_20d > 10 and not vol_shrink else (40 if ma_bad else 55)
            scores["方新侠"] = 70 if ma_ok and dist60h < -5 else (45 if ma_bad else 55)
            scores["章盟主"] = 85 if ma_ok and up_20d > 5 else (35 if ma_bad else 55)
            scores["葛卫东"] = 70 if dist60h < -15 else (50 if dist60h < -5 else 40)
            scores["作手新一"] = 65 if vol_shrink and ma_ok else (40 if ma_bad else 50)
            scores["瑞鹤仙"] = 60 if ma_ok and last_pct > 0 else (30 if ma_bad else 45)
            avg = sum(scores.values()) / len(scores)
            return {"scores": scores, "avg": round(avg, 1), "ma_ok": ma_ok, "ma_bad": ma_bad,
                    "last_pct": round(last_pct, 2), "up_20d": round(up_20d, 2), "dist60h": round(dist60h, 2)}
        except Exception as e:
            return {"error": str(e)}

    def _show_batch_hotmoney_results(self, results, prog_win):
        """显示批量扫描结果: Treeview 表格, 每行可双击打开详情"""
        try: prog_win.destroy()
        except Exception: pass
        win = tk.Toplevel(self.root)
        win.title("🦅 板块成分股 - 游资心法批量扫描结果")
        win.geometry("900x500"); win.transient(self.root)
        # 顶栏统计
        ok_results = [r for r in results if "scores" in r[2]]
        fail = [r for r in results if "error" in r[2]]
        total_avg = np.mean([r[2]["avg"] for r in ok_results]) if ok_results else 0
        tk.Label(win, text=f"✅ 成功 {len(ok_results)} / ❌ 失败 {len(fail)}  综合均分 {total_avg:.1f}",
                 bg="#1A237E", fg="#FFD54F", font=("", 11, "bold")).pack(fill=tk.X)
        # Treeview
        cols = ("code", "name", "avg", "zg", "cj", "fx", "zm", "gw", "zs", "rh", "up20d", "dist60h", "ma")
        headings = ("代码", "名称", "均分", "赵老哥", "炒股养家", "方新侠", "章盟主", "葛卫东", "作手新一", "瑞鹤仙", "20d%", "距60H", "MA")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c, h in zip(cols, headings):
            tree.heading(c, text=h)
            tree.column(c, width=65, anchor="center")
        tree.column("name", width=90, anchor="w")
        tree.column("avg", width=70, anchor="center")
        tree.column("up20d", width=75, anchor="e")
        tree.column("dist60h", width=75, anchor="e")
        tree.column("ma", width=50, anchor="center")
        tree.column("code", width=75, anchor="center")
        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); vsb.pack(side=tk.RIGHT, fill=tk.Y)
        # 填数据
        for code, name, res in results:
            if "error" in res: continue
            s = res["scores"]
            tag = "good" if res["avg"] >= 65 else ("mid" if res["avg"] >= 50 else "bad")
            ma_str = "多头↑" if res["ma_ok"] else ("空头↓" if res["ma_bad"] else "震荡")
            tree.insert("", tk.END, values=(
                code, name, f"{res['avg']:.1f}",
                s["赵老哥"], s["炒股养家"], s["方新侠"], s["章盟主"],
                s["葛卫东"], s["作手新一"], s["瑞鹤仙"],
                f"{res['up_20d']:+.2f}", f"{res['dist60h']:.1f}%", ma_str
            ), tags=(tag,))
        tree.tag_configure("good", background="#FFEBEE")
        tree.tag_configure("mid", background="#FFF8E1")
        tree.tag_configure("bad", background="#E8F5E9")
        # 双击 → 打开单只心法详情
        def _on_dbl(e):
            sel = tree.selection()
            if not sel: return
            item = tree.item(sel[0])
            code = str(item["values"][0]); name = str(item["values"][1])
            self._open_hotmoney_single_dialog(auto_code=code, auto_name=name)
        tree.bind("<Double-1>", _on_dbl)

    def _extract_quant_hot_concepts_from_lines(self, concept_lines, top_n=6):
        """从概念行中提取涨幅靠前题材名。"""
        import re
        out = []
        for ln in concept_lines or []:
            m = re.match(r"\s*·\s*([^::]+)\s*[::]\s*([+-]?\d+\.?\d*)%", str(ln))
            if not m:
                continue
            nm = m.group(1).strip()
            try:
                p = float(m.group(2))
            except ValueError:
                continue
            out.append((nm, p))
        out.sort(key=lambda x: x[1], reverse=True)
        return out[:top_n]

    def _sync_sector_index_combo_values(self):
        """主线程刷新板块下拉框(后台线程拉完列表后调用)。"""
        try:
            combo = getattr(self, "sector_index_combo", None)
            if combo is not None:
                combo["values"] = list(self.sector_index_list or [])
        except Exception:
            pass

    def _load_sector_index_list(self):
        """加载板块指数列表,并自动获取同花顺热门板块前30(每天自动更新)"""
        try:
            self.sector_index_list = self.ai_config_manager.config.get("sector_index_list", [])
            if not isinstance(self.sector_index_list, list):
                self.sector_index_list = []
            # 检查是否需要更新(每天自动更新一次)
            last_update_date = self.ai_config_manager.config.get("sector_index_last_update", "")
            today = datetime.now().strftime("%Y-%m-%d")
            need_update = (last_update_date != today) or (len(self.sector_index_list) < 30)
            # 每天自动获取热门板块前30:网络请求放到后台线程,避免阻塞主窗口首次显示
            if need_update:
                def _sector_fetch_worker():
                    try:
                        import akshare as ak
                        concept_df = None
                        source = ""
                        new_list = []
                        try:
                            concept_df = safe_call(ak.stock_board_concept_name_em, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_em")
                            if concept_df is not None and not concept_df.empty and '涨跌幅' in concept_df.columns:
                                hot_sectors = concept_df.sort_values('涨跌幅', ascending=False).head(30)
                                new_list = hot_sectors['板块名称'].tolist()[:30]
                                source = "东方财富"
                        except Exception as em_e:
                            print(f"东方财富接口获取板块列表失败: {em_e}")
                        if not new_list or len(new_list) < 10:
                            try:
                                concept_df = safe_call(ak.stock_board_concept_name_em, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_em")
                                if concept_df is not None and not concept_df.empty and '涨跌幅' in concept_df.columns:
                                    hot_sectors = concept_df.sort_values('涨跌幅', ascending=False).head(30)
                                    new_list = hot_sectors['板块名称'].tolist()[:30]
                                    source = "东方财富"
                            except Exception as em_e:
                                print(f"东方财富接口获取板块列表失败: {em_e}")
                        if new_list and len(new_list) >= 10:
                            self.sector_index_list = new_list
                            self.ai_config_manager.config["sector_index_last_update"] = today
                            self._save_sector_index_list()
                            print(f"已自动更新强势板块列表({source},{today}): {len(self.sector_index_list)}个")
                        try:
                            self.root.after(0, self._sync_sector_index_combo_values)
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"自动获取热门板块失败: {e}")
                threading.Thread(target=_sector_fetch_worker, daemon=True).start()
        except Exception:
            self.sector_index_list = []

    def _refresh_sector_index_list(self):
        """手动刷新板块指数列表(强制更新为当天最新强势板块,优先使用同花顺接口)"""
        try:
            import akshare as ak
            concept_df = None
            # 方法1:尝试同花顺接口
            try:
                concept_df = safe_call(ak.stock_board_concept_name_ths, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_ths")
                if concept_df is not None and not concept_df.empty:
                    # 同花顺接口的列名可能不同,查找涨跌幅列
                    pct_col = None
                    name_col = None
                    for col in concept_df.columns:
                        if '涨跌' in str(col) or '涨幅' in str(col):
                            pct_col = col
                        if '板块' in str(col) or '名称' in str(col):
                            name_col = col
                    if pct_col and name_col:
                        hot_sectors = concept_df.sort_values(pct_col, ascending=False).head(30)
                        hot_sector_names = hot_sectors[name_col].tolist()
                        self.sector_index_list = hot_sector_names[:30]
                        today = datetime.now().strftime("%Y-%m-%d")
                        self.ai_config_manager.config["sector_index_last_update"] = today
                        self._save_sector_index_list()
                        return True, f"已从同花顺刷新为当天最新强势板块({len(self.sector_index_list)}个)"
            except Exception as ths_e:
                print(f"同花顺接口获取板块列表失败: {ths_e}")
            # 方法2:尝试东方财富接口
            try:
                concept_df = safe_call(ak.stock_board_concept_name_em, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_em")
                if concept_df is not None and not concept_df.empty and '涨跌幅' in concept_df.columns:
                    hot_sectors = concept_df.sort_values('涨跌幅', ascending=False).head(30)
                    hot_sector_names = hot_sectors['板块名称'].tolist()
                    self.sector_index_list = hot_sector_names[:30]
                    today = datetime.now().strftime("%Y-%m-%d")
                    self.ai_config_manager.config["sector_index_last_update"] = today
                    self._save_sector_index_list()
                    return True, f"已从东方财富刷新为当天最新强势板块({len(self.sector_index_list)}个)"
            except Exception as em_e:
                print(f"东方财富接口获取板块列表失败: {em_e}")
            return False, "获取板块数据失败(同花顺和东方财富接口均失败)"
        except Exception as e:
            return False, f"刷新失败: {e}"

    def _save_sector_index_list(self):
        """保存板块指数列表"""
        try:
            self.ai_config_manager.config["sector_index_list"] = self.sector_index_list
            self.ai_config_manager.save_config()
        except Exception as e:
            print(f"保存板块指数列表失败: {e}")

    def _manage_sector_index_list(self):
        """维护板块指数列表"""
        manage_window = self._safe_toplevel(self.root)
        manage_window.title("板块指数维护(最多30个)")
        manage_window.geometry("500x400")
        main_frame = ttk.Frame(manage_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # 标题
        ttk.Label(main_frame, text="板块指数列表(最多30个)", font=("TkDefaultFont", 12, "bold")).pack(pady=(0, 10))
        # 列表显示
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        listbox = tk.Listbox(list_frame, height=15)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.configure(yscrollcommand=scrollbar.set)
        # 刷新列表显示
        def refresh_list():
            listbox.delete(0, tk.END)
            for item in self.sector_index_list:
                listbox.insert(tk.END, item)
        refresh_list()
        # 输入框和按钮
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(input_frame, text="板块/指数名称:").pack(side=tk.LEFT, padx=(0, 5))
        entry = ttk.Entry(input_frame, width=25)
        entry.pack(side=tk.LEFT, padx=(0, 5))
        def add_item():
            """添加板块指数"""
            item = entry.get().strip()
            if not item:
                messagebox.showwarning("警告", "请输入板块/指数名称")
                return
            if len(self.sector_index_list) >= 30:
                messagebox.showwarning("警告", "最多只能添加30个板块指数")
                return
            if item in self.sector_index_list:
                messagebox.showwarning("警告", "该板块/指数已存在")
                return
            self.sector_index_list.append(item)
            self._save_sector_index_list()
            self.sector_index_combo['values'] = self.sector_index_list
            refresh_list()
            entry.delete(0, tk.END)
            messagebox.showinfo("成功", f"已添加: {item}")
        def delete_item():
            """删除选中的板块指数"""
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("警告", "请先选择要删除的板块/指数")
                return
            index = selection[0]
            item = self.sector_index_list[index]
            if messagebox.askyesno("确认", f"确定要删除 '{item}' 吗?"):
                self.sector_index_list.pop(index)
                self._save_sector_index_list()
                self.sector_index_combo['values'] = self.sector_index_list
                refresh_list()
                messagebox.showinfo("成功", f"已删除: {item}")
        ttk.Button(input_frame, text="添加", command=add_item).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(input_frame, text="删除", command=delete_item).pack(side=tk.LEFT)
        # 从同花顺板块添加(支持多选和批量导入)
        def add_from_ths():
            """从同花顺板块添加(支持多选和批量导入)"""
            try:
                from tkinter import simpledialog

                import akshare as ak
                # 选择板块类型
                sector_type = simpledialog.askstring("选择板块类型", "请输入板块类型(概念/行业):", initialvalue="概念")
                if not sector_type:
                    return
                if sector_type == "概念":
                    df = safe_call(ak.stock_board_concept_name_em, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_em")
                elif sector_type == "行业":
                    df = safe_call(ak.stock_board_industry_name_em, fallback=pd.DataFrame(), label="ak.stock_board_industry_name_em")
                else:
                    messagebox.showwarning("警告", "请输入'概念'或'行业'")
                    return
                if df.empty:
                    messagebox.showwarning("警告", "获取板块列表失败")
                    return
                # 创建选择窗口(支持多选)
                select_window = self._toplevel(manage_window)
                select_window.title(f"选择{sector_type}板块(支持多选)")
                select_window.geometry("500x600")
                # 顶部按钮区域
                button_frame_top = ttk.Frame(select_window)
                button_frame_top.pack(fill=tk.X, padx=10, pady=(10, 5))
                ttk.Label(button_frame_top, text=f"共 {len(df)} 个{sector_type}板块",
                         font=("TkDefaultFont", 11)).pack(side=tk.LEFT)
                def select_all():
                    """全选"""
                    select_listbox.selection_set(0, tk.END)
                def clear_selection():
                    """清空选择"""
                    select_listbox.selection_clear(0, tk.END)
                ttk.Button(button_frame_top, text="全选", command=select_all, width=8).pack(side=tk.RIGHT, padx=(5, 0))
                ttk.Button(button_frame_top, text="清空", command=clear_selection, width=8).pack(side=tk.RIGHT, padx=(5, 0))
                # 搜索框
                search_frame = ttk.Frame(select_window)
                search_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
                ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT, padx=(0, 5))
                search_var = tk.StringVar()
                search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
                search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                # 列表显示(支持多选)
                list_frame = ttk.Frame(select_window)
                list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
                select_listbox = tk.Listbox(list_frame, height=20, selectmode=tk.EXTENDED)
                select_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=select_listbox.yview)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                select_listbox.configure(yscrollcommand=scrollbar.set)
                sectors = df['板块名称'].tolist()
                filtered_sectors = sectors.copy()
                def update_list():
                    """更新列表显示"""
                    select_listbox.delete(0, tk.END)
                    for sector in filtered_sectors:
                        select_listbox.insert(tk.END, sector)
                def filter_list(*args):
                    """过滤列表"""
                    search_text = search_var.get().strip().lower()
                    if not search_text:
                        filtered_sectors[:] = sectors
                    else:
                        filtered_sectors[:] = [s for s in sectors if search_text in s.lower()]
                    update_list()
                search_var.trace_add("write", filter_list)
                update_list()
                # 底部按钮区域
                button_frame_bottom = ttk.Frame(select_window)
                button_frame_bottom.pack(fill=tk.X, padx=10, pady=(0, 10))
                def confirm_add():
                    """添加选中的板块"""
                    selections = select_listbox.curselection()
                    if not selections:
                        messagebox.showwarning("警告", "请先选择板块(可多选)")
                        return
                    selected_items = [filtered_sectors[i] for i in selections]
                    added_count = 0
                    skipped_count = 0
                    for item in selected_items:
                        if len(self.sector_index_list) >= 30:
                            messagebox.showwarning("警告", f"最多只能添加30个板块指数,已添加 {added_count} 个,跳过 {len(selected_items) - added_count} 个")
                            break
                        if item in self.sector_index_list:
                            skipped_count += 1
                            continue
                        self.sector_index_list.append(item)
                        added_count += 1
                    if added_count > 0:
                        self._save_sector_index_list()
                        self.sector_index_combo['values'] = self.sector_index_list
                        refresh_list()
                        messagebox.showinfo("成功", f"已添加 {added_count} 个板块" + (f",跳过 {skipped_count} 个已存在的板块" if skipped_count > 0 else ""))
                    if added_count > 0:
                        select_window.destroy()
                ttk.Button(button_frame_bottom, text="添加选中(支持多选)", command=confirm_add).pack(side=tk.LEFT, padx=(0, 5))
                ttk.Button(button_frame_bottom, text="取消", command=select_window.destroy).pack(side=tk.RIGHT)
            except Exception as e:
                messagebox.showerror("错误", f"从同花顺添加板块失败: {e}")
                import traceback
                traceback.print_exc()
        ttk.Button(main_frame, text="从同花顺板块导入(支持多选)", command=add_from_ths).pack(pady=(0, 10))
        # 关闭按钮
        ttk.Button(main_frame, text="关闭", command=manage_window.destroy).pack()

    def _on_hot_stock_15min_monitor_toggle(self):
        """15分钟热门股监测开关切换"""
        self.hot_stock_15min_monitor_enabled = self.hot_stock_15min_monitor_var.get()
        if self.hot_stock_15min_monitor_enabled:
            print("[15分钟热门股监测] 已开启")
            self._start_hot_stock_15min_monitor()
            self._show_hot_stock_15min_monitor()
        else:
            print("[15分钟热门股监测] 已关闭")
            self._stop_hot_stock_15min_monitor()

    def _start_hot_stock_15min_monitor(self):
        """启动15分钟热门股监测"""
        if self.hot_stock_15min_monitor_running:
            return
        self.hot_stock_15min_monitor_running = True
        def monitor_loop():
            while self.hot_stock_15min_monitor_running:
                try:
                    if self.hot_stock_15min_monitor_enabled:
                        self._update_hot_stock_15min_monitor()
                except Exception as e:
                    print(f"15分钟热门股监测错误: {e}")
                # 等待5分钟(300秒)
                for _ in range(300):
                    if not self.hot_stock_15min_monitor_running:
                        break
                    time.sleep(1)
        self.hot_stock_15min_monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.hot_stock_15min_monitor_thread.start()
        print("[15分钟热门股监测] 监测已启动,每5分钟刷新一次")

    def _stop_hot_stock_15min_monitor(self):
        """停止15分钟热门股监测"""
        self.hot_stock_15min_monitor_running = False
        print("[15分钟热门股监测] 监测已停止")

    def _show_hot_stock_15min_monitor(self):
        """显示日K热门股监测窗口(数据来自Tushare)"""
        # 如果窗口已存在,则显示并刷新
        if self.hot_stock_15min_monitor_window is not None:
            try:
                self.hot_stock_15min_monitor_window.deiconify()
                self.hot_stock_15min_monitor_window.lift()
                self._update_hot_stock_15min_monitor()
                return
            except:
                # 窗口已销毁,重新创建
                self.hot_stock_15min_monitor_window = None
        # 创建新窗口
        monitor_window = self._safe_toplevel(self.root)
        monitor_window.title("日K热门股监测 - K线图(Tushare)")
        monitor_window.geometry("1600x1000")
        self.hot_stock_15min_monitor_window = monitor_window
        # 主框架
        main_frame = ttk.Frame(monitor_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # 标题和刷新按钮
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header_frame, text="日K热门股监测(每5分钟自动刷新,数据Tushare)",
                 font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT)
        refresh_btn = ttk.Button(header_frame, text="立即刷新",
                                command=lambda: self._update_hot_stock_15min_monitor())
        refresh_btn.pack(side=tk.RIGHT, padx=(10, 0))
        # 滚动框架(容纳所有热门股的K线图:3列)
        canvas = tk.Canvas(main_frame, bg="white")
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # 配置网格布局:3列
        cols = 3
        for i in range(cols):
            scrollable_frame.columnconfigure(i, weight=1, uniform="chart")
        # 存储图表组件
        chart_widgets = []
        def create_chart_frame(row, col, stock_name, stock_code):
            """创建单个热门股K线图框架"""
            chart_frame = ttk.LabelFrame(scrollable_frame,
                                        text=f"{stock_name} ({stock_code})",
                                        padding=5)
            chart_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            try:
                import matplotlib.pyplot as plt
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                from matplotlib.figure import Figure
                fig = Figure(figsize=(5, 3), dpi=80)
                ax = fig.add_subplot(111)
                canvas_widget = FigureCanvasTkAgg(fig, chart_frame)
                canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                # 显示加载中
                ax.text(0.5, 0.5, "加载中...", ha='center', va='center',
                       transform=ax.transAxes, fontsize=10)
                canvas_widget.draw()
                chart_widgets.append({
                    'stock_name': stock_name,
                    'stock_code': stock_code,
                    'fig': fig,
                    'ax': ax,
                    'canvas': canvas_widget
                })
            except ImportError:
                error_label = tk.Label(chart_frame, text="matplotlib未安装",
                                     font=("TkDefaultFont", 11), fg="red")
                error_label.pack(fill=tk.BOTH, expand=True)
        # 获取热门股票列表
        hot_stocks = self._query_wenwen_stocks()
        # 创建热门股K线图框架(3列)
        for idx, (stock_code, stock_name) in enumerate(hot_stocks):
            row = idx // cols
            col = idx % cols
            create_chart_frame(row, col, stock_name, stock_code)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 存储图表组件到窗口对象
        monitor_window.chart_widgets = chart_widgets
        # 初始加载数据
        self._update_hot_stock_15min_monitor()
        # 窗口关闭事件
        def on_closing():
            self.hot_stock_15min_monitor_window = None
            monitor_window.destroy()
        monitor_window.protocol("WM_DELETE_WINDOW", on_closing)

    def _update_hot_stock_15min_monitor(self):
        """更新日K热门股监测窗口的K线图(数据来自Tushare)"""
        if self.hot_stock_15min_monitor_window is None:
            return
        try:
            chart_widgets = getattr(self.hot_stock_15min_monitor_window, 'chart_widgets', [])
            if not chart_widgets:
                return
            def _fmt_date(s):
                if not s or len(s) != 8:
                    return str(s)
                return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
            def update_chart(chart_info):
                """更新单个图表(日K,Tushare)"""
                try:
                    stock_name = chart_info['stock_name']
                    stock_code = chart_info['stock_code']
                    ax = chart_info['ax']
                    fig = chart_info['fig']
                    canvas = chart_info['canvas']
                    ax.clear()
                    try:
                        kline_data = self._get_daily_kline_data_tushare(str(stock_code).zfill(6), days=60)
                        if kline_data is None:
                            ax.text(0.5, 0.5, "暂无日K数据\n(请检查Tushare)", ha='center', va='center',
                                   transform=ax.transAxes, fontsize=9)
                            canvas.draw()
                            return
                        data = kline_data['data']
                        ma_values = kline_data['ma_values']
                        trade_dates = kline_data.get('trade_dates') or []
                        closes = data['收盘'].values
                        opens = data['开盘'].values
                        highs = data['最高'].values
                        lows = data['最低'].values
                        n = len(closes)
                        dates = list(range(n))
                        # 绘制日K蜡烛图
                        for i in range(n):
                            color = 'red' if closes[i] >= opens[i] else 'green'
                            body_bottom = min(float(opens[i]), float(closes[i]))
                            body_top = max(float(opens[i]), float(closes[i]))
                            ax.bar(i, body_top - body_bottom, bottom=body_bottom, color=color, alpha=0.8, width=0.6)
                            ax.plot([i, i], [float(lows[i]), body_bottom], color=color, linewidth=1)
                            ax.plot([i, i], [body_top, float(highs[i])], color=color, linewidth=1)
                        ax.plot(dates, closes, color='black', linewidth=0.5, label='收盘', alpha=0.5, linestyle='--')
                        # 绘制均线
                        period_map = {'ma1': 1, 'ma5': 5, 'ma10': 10, 'ma20': 20}
                        ma_colors = {'ma1': '#FF0000', 'ma5': '#00FF00', 'ma10': '#0000FF', 'ma20': '#FF00FF'}
                        ma_labels = {'ma1': 'MA1', 'ma5': 'MA5', 'ma10': 'MA10', 'ma20': 'MA20'}
                        for ma_name in ['ma1', 'ma5', 'ma10', 'ma20']:
                            if ma_name not in ma_values or len(ma_values[ma_name]) == 0:
                                continue
                            ma_data = ma_values[ma_name]
                            period = period_map[ma_name]
                            start_idx = min(period - 1, n - 1)
                            ma_indices = list(range(start_idx, start_idx + len(ma_data)))
                            min_len = min(len(ma_indices), len(ma_data))
                            if min_len > 0:
                                ax.plot(ma_indices[:min_len], ma_data[:min_len], color=ma_colors[ma_name],
                                       linewidth=0.8, label=ma_labels[ma_name], alpha=0.8)
                        ax.set_title(f"{stock_name} ({stock_code}) - 日K", fontsize=8, fontweight='bold')
                        ax.set_xlabel('日期', fontsize=6)
                        ax.set_ylabel('价格', fontsize=6)
                        ax.legend(loc='upper left', fontsize=5)
                        ax.grid(True, alpha=0.3)
                        step = max(1, len(trade_dates) // 10)
                        ax.set_xticks(dates[::step])
                        ax.set_xticklabels([_fmt_date(trade_dates[i]) if i < len(trade_dates) else str(i) for i in dates[::step]], rotation=45, ha='right', fontsize=5)
                        fig.tight_layout()
                        canvas.draw()
                    except Exception as e:
                        print(f"获取 {stock_code} 日K线失败: {e}")
                        ax.text(0.5, 0.5, f"加载失败:\n{str(e)[:30]}", ha='center', va='center',
                               transform=ax.transAxes, fontsize=8, wrap=True)
                        canvas.draw()
                except Exception as e:
                    print(f"更新热门股 {chart_info.get('stock_name', '未知')} K线图失败: {e}")
                    try:
                        ax = chart_info.get('ax')
                        canvas = chart_info.get('canvas')
                        if ax and canvas:
                            ax.clear()
                            ax.text(0.5, 0.5, f"加载失败:\n{str(e)[:30]}", ha='center', va='center',
                                   transform=ax.transAxes, fontsize=8, wrap=True)
                            canvas.draw()
                    except:
                        pass
            # 在后台线程中更新所有图表
            def update_all_charts():
                for chart_info in chart_widgets:
                    update_chart(chart_info)
            # 使用线程更新,避免阻塞UI
            threading.Thread(target=update_all_charts, daemon=True).start()
        except Exception as e:
            print(f"更新日K热门股监测失败: {e}")
            import traceback
            traceback.print_exc()

    def _fetch_and_show_top16_sectors(self):
        """获取同花顺涨幅最大前16板块,持仓1-8各在股票最下面显示2个板块名"""
        try:
            import akshare as ak
            concept_df = safe_call(ak.stock_board_concept_name_ths, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_ths")
            if concept_df is None or concept_df.empty:
                self.top16_sector_names = []
                self._update_holding_tabs_sector_labels()
                return
            pct_col = None
            name_col = None
            for col in concept_df.columns:
                if '涨跌' in str(col) or '涨幅' in str(col):
                    pct_col = col
                if '板块' in str(col) or '名称' in str(col):
                    name_col = col
            if not pct_col or not name_col:
                self.top16_sector_names = []
                self._update_holding_tabs_sector_labels()
                return
            hot = concept_df.sort_values(pct_col, ascending=False).head(16)
            self.top16_sector_names = hot[name_col].tolist()
            self._update_holding_tabs_sector_labels()
        except Exception as e:
            print(f"[同花顺涨幅板块] 获取前16板块失败: {e}")
            self.top16_sector_names = []
            self._update_holding_tabs_sector_labels()

    def _show_sector_detail_popup(self, sector_name, sector_type="概念"):
        """显示板块详情弹窗(K线图和10个龙头股)"""
        # 创建新窗口
        detail_window = self._safe_toplevel(self.root)
        detail_window.title(f"{sector_name} - 板块详情")
        detail_window.geometry("1200x700")
        # 主框架
        main_frame = ttk.Frame(detail_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # 标题
        title_label = ttk.Label(main_frame, text=f"{sector_name} - 15分钟K线图",
                               font=("TkDefaultFont", 14, "bold"))
        title_label.pack(pady=(0, 10))
        # 创建水平布局:左侧K线图,右侧龙头股列表
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        # 左侧:K线图(更大)
        kline_frame = ttk.LabelFrame(content_frame, text="15分钟K线图", padding=10)
        kline_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        # 右侧:龙头股列表
        leader_stocks_frame = ttk.LabelFrame(content_frame, text="龙头股(前10)", padding=10)
        leader_stocks_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=(10, 0))
        try:
            import akshare as ak
            import matplotlib.pyplot as plt
            import numpy as np
            import pandas as pd
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            # 创建更大的K线图
            fig = Figure(figsize=(10, 6), dpi=100)
            ax = fig.add_subplot(111)
            canvas_widget = FigureCanvasTkAgg(fig, kline_frame)
            canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            # 显示加载中
            ax.text(0.5, 0.5, "加载中...", ha='center', va='center',
                   transform=ax.transAxes, fontsize=14)
            canvas_widget.draw()
            # 创建龙头股列表(使用Text widget,支持滚动)
            leader_stocks_text = tk.Text(leader_stocks_frame, width=25, height=30,
                                        font=("TkDefaultFont", 12), wrap=tk.WORD)
            leader_stocks_scrollbar = ttk.Scrollbar(leader_stocks_frame, orient=tk.VERTICAL,
                                                   command=leader_stocks_text.yview)
            leader_stocks_text.configure(yscrollcommand=leader_stocks_scrollbar.set)
            leader_stocks_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            leader_stocks_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            leader_stocks_text.insert("1.0", "加载中...")
            leader_stocks_text.config(state=tk.DISABLED)  # 只读
            # 在后台线程中加载数据
            def load_data():
                try:
                    # 获取板块成分股
                    if sector_type == "概念":
                        stock_list = ak.stock_board_concept_cons_em(symbol=sector_name)
                    else:
                        stock_list = ak.stock_board_industry_cons_em(symbol=sector_name)
                    leader_stocks_list = []  # 存储龙头股列表
                    kline_data = None
                    if stock_list is not None and not stock_list.empty:
                        # 获取龙头股前10(按涨跌幅排序)
                        try:
                            # 获取名称和代码列
                            name_col = None
                            code_col = None
                            pct_col = None
                            for col in stock_list.columns:
                                col_str = str(col).lower()
                                if name_col is None and ('名称' in str(col) or 'name' in col_str):
                                    name_col = col
                                if code_col is None and ('代码' in str(col) or 'code' in col_str):
                                    code_col = col
                                if pct_col is None and ('涨跌幅' in str(col) or 'pct' in col_str or 'change' in col_str):
                                    pct_col = col
                            if name_col and code_col:
                                # 按涨跌幅排序(如果有涨跌幅列)
                                if pct_col:
                                    sorted_stocks = stock_list.sort_values(pct_col, ascending=False)
                                else:
                                    sorted_stocks = stock_list
                                # 取前10只股票
                                for idx, (_, row) in enumerate(sorted_stocks.head(10).iterrows()):
                                    stock_name = str(row.get(name_col, '')).strip()
                                    stock_code = str(row.get(code_col, '')).strip()
                                    if stock_name and stock_code:
                                        pct_str = ""
                                        if pct_col:
                                            try:
                                                pct_val = float(row.get(pct_col, 0))
                                                pct_str = f" {pct_val:+.2f}%"
                                            except:
                                                pass
                                        leader_stocks_list.append(f"{idx+1}. {stock_name}({stock_code}){pct_str}")
                        except Exception as e:
                            print(f"获取板块 {sector_name} 龙头股失败: {e}")
                            leader_stocks_list = ["获取失败"]
                        # 获取K线数据
                        code_col = None
                        for col in ['代码', 'code', '股票代码']:
                            if col in stock_list.columns:
                                code_col = col
                                break
                        if code_col:
                            # 取前5只成分股的平均值
                            codes = stock_list[code_col].head(5).tolist()
                            all_closes = []
                            all_times = []
                            for code in codes:
                                try:
                                    # 获取15分钟K线数据
                                    stock_kline = ak.stock_zh_a_hist_min_em(symbol=str(code).zfill(6), period="15", adjust="")
                                    if stock_kline is not None and not stock_kline.empty:
                                        # 获取收盘价列和时间列
                                        close_col = None
                                        time_col = None
                                        for col in stock_kline.columns:
                                            col_str = str(col).lower()
                                            if close_col is None and ('收盘' in str(col) or 'close' in col_str):
                                                close_col = col
                                            if time_col is None and ('时间' in str(col) or 'time' in col_str or 'date' in str(col)):
                                                time_col = col
                                        if close_col:
                                            closes = stock_kline[close_col].astype(float).tolist()
                                            times = stock_kline[time_col].tolist() if time_col else range(len(closes))
                                            if len(closes) > 0:
                                                all_closes.append(closes)
                                                if not all_times:
                                                    all_times = times
                                except Exception as e:
                                    print(f"获取 {code} 15分钟K线失败: {e}")
                                    continue
                            if all_closes:
                                # 计算平均值
                                max_len = max(len(c) for c in all_closes)
                                avg_closes = []
                                for i in range(max_len):
                                    values = [c[i] for c in all_closes if i < len(c)]
                                    if values:
                                        avg_closes.append(np.mean(values))
                                if avg_closes:
                                    kline_data = pd.DataFrame({
                                        '时间': all_times[:len(avg_closes)],
                                        '收盘': avg_closes
                                    })
                    # 更新UI(在主线程中)
                    def update_ui():
                        try:
                            # 更新K线图
                            ax.clear()
                            if kline_data is not None and not kline_data.empty:
                                close_col = None
                                time_col = None
                                for col in kline_data.columns:
                                    col_str = str(col).lower()
                                    if close_col is None and ('收盘' in str(col) or 'close' in col_str):
                                        close_col = col
                                    if time_col is None and ('时间' in str(col) or 'time' in col_str or 'date' in str(col)):
                                        time_col = col
                                if close_col:
                                    closes = kline_data[close_col].astype(float).tolist()
                                    times = kline_data[time_col].tolist() if time_col else range(len(closes))
                                    # 计算均线
                                    periods = {
                                        'ma1': 16,   # 1日 = 16根15分钟K线
                                        'ma5': 80,   # 5日 = 80根15分钟K线
                                        'ma10': 160, # 10日 = 160根15分钟K线
                                        'ma20': 320  # 20日 = 320根15分钟K线
                                    }
                                    ma1_values = []
                                    ma5_values = []
                                    ma10_values = []
                                    ma20_values = []
                                    for i in range(len(closes)):
                                        if i >= periods['ma1'] - 1:
                                            ma1_values.append(sum(closes[i-periods['ma1']+1:i+1]) / periods['ma1'])
                                        else:
                                            ma1_values.append(None)
                                        if i >= periods['ma5'] - 1:
                                            ma5_values.append(sum(closes[i-periods['ma5']+1:i+1]) / periods['ma5'])
                                        else:
                                            ma5_values.append(None)
                                        if i >= periods['ma10'] - 1:
                                            ma10_values.append(sum(closes[i-periods['ma10']+1:i+1]) / periods['ma10'])
                                        else:
                                            ma10_values.append(None)
                                        if i >= periods['ma20'] - 1:
                                            ma20_values.append(sum(closes[i-periods['ma20']+1:i+1]) / periods['ma20'])
                                        else:
                                            ma20_values.append(None)
                                    # 绘制K线
                                    ax.plot(times, closes, 'b-', linewidth=2, label=sector_name, alpha=0.8)
                                    # 绘制均线
                                    if any(v is not None for v in ma1_values):
                                        ma1_plot = [v if v is not None else closes[i] for i, v in enumerate(ma1_values)]
                                        ax.plot(times, ma1_plot, 'r--', linewidth=1.5, label='MA1', alpha=0.7)
                                    if any(v is not None for v in ma5_values):
                                        ma5_plot = [v if v is not None else closes[i] for i, v in enumerate(ma5_values)]
                                        ax.plot(times, ma5_plot, 'orange', linewidth=1.5, label='MA5', alpha=0.7)
                                    if any(v is not None for v in ma10_values):
                                        ma10_plot = [v if v is not None else closes[i] for i, v in enumerate(ma10_values)]
                                        ax.plot(times, ma10_plot, 'green', linewidth=1.5, label='MA10', alpha=0.7)
                                    if any(v is not None for v in ma20_values):
                                        ma20_plot = [v if v is not None else closes[i] for i, v in enumerate(ma20_values)]
                                        ax.plot(times, ma20_plot, 'purple', linewidth=1.5, label='MA20', alpha=0.7)
                                    ax.set_title(f"{sector_name} - 15分钟K线图", fontsize=14, fontweight='bold')
                                    ax.set_xlabel('时间', fontsize=12)
                                    ax.set_ylabel('价格', fontsize=12)
                                    ax.legend(loc='upper left', fontsize=10)
                                    ax.grid(True, alpha=0.3)
                                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
                                    fig.tight_layout()
                                else:
                                    ax.text(0.5, 0.5, "暂无K线数据", ha='center', va='center',
                                           transform=ax.transAxes, fontsize=14)
                            else:
                                ax.text(0.5, 0.5, "暂无K线数据", ha='center', va='center',
                                       transform=ax.transAxes, fontsize=14)
                            canvas_widget.draw()
                            # 更新龙头股列表
                            leader_stocks_text.config(state=tk.NORMAL)
                            leader_stocks_text.delete("1.0", tk.END)
                            if leader_stocks_list:
                                leader_stocks_text.insert("1.0", "\n".join(leader_stocks_list))
                            else:
                                leader_stocks_text.insert("1.0", "暂无数据")
                            leader_stocks_text.config(state=tk.DISABLED)
                        except Exception as e:
                            print(f"更新板块详情UI失败: {e}")
                            ax.clear()
                            ax.text(0.5, 0.5, f"加载失败:\n{str(e)[:50]}", ha='center', va='center',
                                   transform=ax.transAxes, fontsize=12, wrap=True)
                            canvas_widget.draw()
                    # 在主线程中更新UI
                    self.root.after(0, update_ui)
                except Exception as e:
                    print(f"加载板块 {sector_name} 详情失败: {e}")
                    def show_error(e=e):
                        ax.clear()
                        ax.text(0.5, 0.5, f"加载失败:\n{str(e)[:50]}", ha='center', va='center',
                               transform=ax.transAxes, fontsize=12, wrap=True)
                        canvas_widget.draw()
                        leader_stocks_text.config(state=tk.NORMAL)
                        leader_stocks_text.delete("1.0", tk.END)
                        leader_stocks_text.insert("1.0", f"加载失败: {str(e)[:100]}")
                        leader_stocks_text.config(state=tk.DISABLED)
                    self.root.after(0, show_error)
            # 启动后台线程加载数据
            threading.Thread(target=load_data, daemon=True).start()
        except ImportError:
            error_label = tk.Label(kline_frame, text="matplotlib未安装",
                                 font=("TkDefaultFont", 12), fg="red")
            error_label.pack(fill=tk.BOTH, expand=True)
            import traceback
            traceback.print_exc()

    def _show_hotmoney_check(self):
        """🦅 游资心法速查: 多游资 × 多股票 → 各心法打分 + 双击详情"""
        import threading as _th
        import tkinter as tk
        from datetime import datetime as _dt_now
        from tkinter import scrolledtext as _st

        import tushare as _ts_pro
        # ===== 6 大游资心法定义 (name, 心法要点列表, 打分函数) =====
        # 打分函数签名: (closes, highs, lows, vols, opens, vr, dma, pct_3m, ma5, ma10, ma20, turnover_rate, pe, total_mv) -> (score, [维度明细])
        def _score_zhaoge(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            """赵老哥 - 涨停板战法: 只做强势, 连板优先, 量能配合"""
            dims = []; s = 50
            ma_ok = m5 > m10 > m20
            if ma_ok: s += 20; dims.append(("均线多头", "🟢", "+20"))
            else: s -= 15; dims.append(("均线排列", "🔴", "-15"))
            if vr >= 1.2 and vr <= 3.0: s += 15; dims.append(("量能配合", "🟢", "+15"))
            elif vr > 4: s -= 10; dims.append(("量能", "🟡", "-10 天量"))
            else: dims.append(("量能", "🟡", "0"))
            if pct3 >= -10: s += 10; dims.append(("位置", "🟢", "+10 接近新高"))
            elif pct3 <= -20: s -= 15; dims.append(("位置", "🔴", "-15 深套"))
            else: dims.append(("位置", "🟡", "0"))
            # 近5日涨跌幅 (强势)
            if len(cl) >= 5:
                r5 = (cl[-1] - cl[-5]) / cl[-5] * 100
                if r5 > 8: s += 15; dims.append(("5日涨幅", "🟢", f"+15 ({r5:+.1f}%)"))
                elif r5 < -8: s -= 10; dims.append(("5日涨幅", "🔴", f"-10 ({r5:+.1f}%)"))
                else: dims.append(("5日涨幅", "🟡", "0"))
            return max(0, min(100, s)), dims, "只做强势股, 顺势而为, 不抄底"
        def _score_chai(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            """炒股养家 - 集合竞价/情绪周期: 高换手, 热门题材"""
            dims = []; s = 50
            if tr and tr > 8: s += 15; dims.append(("换手率", "🟢", f"+15 ({tr:.1f}%)"))
            elif tr and tr > 3: dims.append(("换手率", "🟡", "0"))
            else: s -= 10; dims.append(("换手率", "🔴", "-10 低换手"))
            if vr >= 1.5 and vr <= 4: s += 15; dims.append(("量能活跃", "🟢", "+15"))
            else: dims.append(("量能", "🟡", "0"))
            if m5 > m10 > m20: s += 15; dims.append(("均线多头", "🟢", "+15"))
            else: s -= 10; dims.append(("均线", "🔴", "-10"))
            if pct3 > 0: s += 10; dims.append(("新高", "🟢", "+10 创新高"))
            else: dims.append(("位置", "🟡", "0"))
            # 波动率 (近期振幅)
            if len(hi) >= 10:
                amp = (max(hi[-10:]) - min(lo[-10:])) / min(lo[-10:]) * 100
                if amp > 20: s += 10; dims.append(("10日振幅", "🟢", f"+10 ({amp:.1f}%)"))
                elif amp < 8: s -= 5; dims.append(("10日振幅", "🔴", "-5 死水一潭"))
            return max(0, min(100, s)), dims, "情绪周期为王, 高换手热门股优先"
        def _score_fang(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            """方新侠 - 大资金波段: 低吸高抛, 趋势为王"""
            dims = []; s = 50
            if mv and mv > 100: s += 15; dims.append(("市值", "🟢", f"+15 ({mv/1e8:.0f}亿)"))
            elif mv and mv > 30: dims.append(("市值", "🟡", "0"))
            else: s -= 10; dims.append(("市值", "🔴", "-10 偏小"))
            # 低吸: 偏离MA20负 (回调) 但均线仍多头
            if m5 > m10 > m20 and dma < -3 and dma > -8:
                s += 20; dims.append(("低吸区间", "🟢", f"+20 回调到位 ({dma:+.1f}%)"))
            elif m5 > m10 > m20: s += 10; dims.append(("均线多头", "🟢", "+10"))
            elif m5 < m10 < m20: s -= 20; dims.append(("均线空头", "🔴", "-20"))
            else: dims.append(("均线", "🟡", "0"))
            if pct3 < -15 and pct3 > -30: s += 10; dims.append(("位置", "🟢", f"+10 深跌后 ({pct3:.1f}%)"))
            elif pct3 > 5: s -= 10; dims.append(("位置", "🔴", "-10 偏高追涨"))
            return max(0, min(100, s)), dims, "大资金波段, 低吸高抛, 趋势为王"
        def _score_zhang(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            """章盟主 - 大资金龙头: 低估值, 大成交, 行业龙头"""
            dims = []; s = 50
            if pe and 0 < pe < 30: s += 20; dims.append(("PE估值", "🟢", f"+20 ({pe:.1f})"))
            elif pe and pe > 80: s -= 15; dims.append(("PE估值", "🔴", f"-15 ({pe:.1f} 泡沫)"))
            else: dims.append(("PE", "🟡", "0"))
            if mv and mv > 200: s += 15; dims.append(("大市值", "🟢", f"+15 ({mv/1e8:.0f}亿)"))
            else: dims.append(("市值", "🟡", "0"))
            if vr >= 1.0 and vr <= 2.5: s += 10; dims.append(("量能温和", "🟢", "+10"))
            elif vr > 3.5: s -= 10; dims.append(("量能", "🔴", "-10 天量"))
            if m5 > m20: s += 10; dims.append(("趋势向上", "🟢", "+10"))
            else: s -= 10; dims.append(("趋势", "🔴", "-10"))
            return max(0, min(100, s)), dims, "大资金价值投资, 低估值+行业龙头"
        def _score_ge(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            """葛卫东 - 混沌趋势: 只做大级别趋势, 不预测只跟随"""
            dims = []; s = 50
            if len(cl) >= 60:
                # 60日趋势斜率
                from numpy.polynomial import polynomial as P
                x60 = list(range(60)); y60 = cl[-60:]
                slope = P.polyfit(x60, y60, 1)[1]
                slope_pct = slope / cl[-60] * 100 * 60  # 年化%
                if slope_pct > 20: s += 25; dims.append(("60日斜率", "🟢", f"+25 ({slope_pct:+.1f}%)"))
                elif slope_pct < -20: s -= 20; dims.append(("60日斜率", "🔴", f"-20 ({slope_pct:+.1f}%)"))
                else: dims.append(("60日斜率", "🟡", "0 震荡"))
            # 均线完美多头
            if m5 > m10 > m20 > (sum(cl[-60:])/60 if len(cl)>=60 else cl[-1]):
                s += 15; dims.append(("完美多头", "🟢", "+15"))
            elif m5 < m10 < m20: s -= 15; dims.append(("空头排列", "🔴", "-15"))
            return max(0, min(100, s)), dims, "混沌理论, 只跟随大级别趋势, 不预测"
        def _score_xin(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            """作手新一 - 新生代情绪: 情绪周期, 快速止损"""
            dims = []; s = 50
            # 近3日涨跌 (情绪)
            if len(cl) >= 3:
                r3 = (cl[-1] - cl[-3]) / cl[-3] * 100
                if r3 > 5: s += 15; dims.append(("3日涨幅", "🟢", f"+15 ({r3:+.1f}%)"))
                elif r3 < -5: s -= 10; dims.append(("3日涨幅", "🔴", f"-10 ({r3:+.1f}%)"))
            if tr and tr > 5: s += 15; dims.append(("换手率", "🟢", f"+15 ({tr:.1f}%)"))
            elif tr and tr < 1: s -= 10; dims.append(("换手率", "🔴", "-10 死水"))
            if vr >= 1.5: s += 10; dims.append(("量能放大", "🟢", "+10"))
            else: dims.append(("量能", "🟡", "0"))
            if m5 > m10 > m20: s += 10; dims.append(("均线多头", "🟢", "+10"))
            else: s -= 5; dims.append(("均线", "🟡", "-5"))
            # 情绪冷却: 离高点越近越容易继续冲
            if pct3 > -5: s += 10; dims.append(("创新高", "🟢", "+10"))
            elif pct3 < -15: s -= 10; dims.append(("深套", "🔴", "-10"))
            return max(0, min(100, s)), dims, "情绪周期+龙头战法, 快速止损不扛单"
        def _score_rhx(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            """瑞鹤仙 - 只做强势, 均线多头, 量能活跃, 不追高"""
            dims = []; s = 50
            if m5 > m10 > m20: s += 25; dims.append(("均线多头", "🟢", "+25"))
            elif m5 < m10 < m20: s -= 25; dims.append(("均线空头", "🔴", "-25"))
            else: dims.append(("均线", "🟡", "0"))
            if 1.0 <= vr <= 2.0: s += 15; dims.append(("量能活跃", "🟢", "+15"))
            elif vr < 0.6: s -= 10; dims.append(("量能", "🔴", "-10 冷门"))
            elif vr > 3.0: s -= 15; dims.append(("量能", "🔴", "-15 天量"))
            if dma > 10: s -= 20; dims.append(("追高风险", "🔴", f"-20 ({dma:+.1f}%)"))
            elif -3 <= dma <= 3: s += 8; dims.append(("位置合理", "🟢", f"+8 ({dma:+.1f}%)"))
            if pct3 > -5: s += 10; dims.append(("接近新高", "🟢", f"+10 ({pct3:+.1f}%)"))
            elif pct3 < -20: s -= 15; dims.append(("深套", "🔴", f"-15 ({pct3:.1f}%)"))
            return max(0, min(100, s)), dims, "只做强势, 量能活跃, 不追高, 纪律至上"
        # 六大游资流派 + 每位归属
        SCHOOLS = [
            ("情绪周期流", "#7B1FA2", "养家/92科比/陈小群", "情绪阶段(冰点→高潮)+仓位管理", "🔴 量化最难替代: 情绪无法被机器完全捕捉"),
            ("龙头战法流", "#C62828", "赵老哥/Asking/刺客", "二板定龙+弱转强+分歧一致", "🟡 部分失效: 量化打板吞噬机会, 弱转强仍可"),
            ("低吸反包流", "#F57F17", "乔帮主/作手新一", "强势股缩量回踩+资金回流", "🟡 部分失效: 反包板减少, 但缩量回踩仍有效"),
            ("趋势波段流", "#2E7D32", "章盟主/方新侠/孙哥", "主升持有+下降通道空仓", "🟢 仍有效: 大级别趋势是量化盲区"),
            ("首板隔日套利流", "#1565C0", "佛山/成都帮/上塘路", "打首板隔日必走", "🔴 几乎失效: 量化抢跑严重, 首板溢价被吃"),
            ("分仓复利悟道流", "#4527A0", "退学/北京炒家/涅槃", "账户风控总闸+连亏熔断", "🟢 永远有效: 风控是人性, 量化管不了账户总闸"),
        ]
        # 游资 -> 流派映射
        TRA_TO_SCHOOL = {
            "赵老哥": "龙头战法流",
            "炒股养家": "情绪周期流",
            "方新侠": "趋势波段流",
            "章盟主": "趋势波段流",
            "葛卫东": "趋势波段流",
            "作手新一": "低吸反包流",
            "瑞鹤仙": "龙头战法流",
        }
        HOTMONEY_HEART = {
            # ===== 情绪周期流 =====
            "炒股养家": {
                "school": "情绪周期流",
                "title": "情绪流鼻祖 · 心法最系统",
                "theory": "基于对市场情绪的揣摩 → 判断风险收益比 → 指导实际操作；群体博弈：场外潜在买入者的钱+倾向 > 场内筹码+卖出倾向 → 买",
                "quotes": [
                    "高手买入龙头，**超级高手卖出龙头**",
                    "别人贪婪时我更贪婪，别人恐慌时我更恐慌",
                    "敢于大盘低位空仓，敢于大盘高位满仓；**心中无顶底，操作自随心**",
                    "买入机会，卖出风险，只做对的交易，胜负交给概率",
                    "得散户心者得天下，**人气所向，牛股所在**",
                    "永不止损，永不止盈，只有进场，出局",
                ],
                "risk": [
                    "不看好了就卖出，管它是不是止损",
                    "回避系统性崩溃",
                    "不要因套了几个点而犹豫",
                ],
                "position": "<60%观望 ｜ 60-70%小仓 ｜ 70-80%中仓 ｜ 80-90%大仓 ｜ 90%+满仓",
                "buy_rule": "有赚钱效应做热点，有恐慌效应做超跌；超跌稳住→强势机会大",
            },
            "92科比": {
                "school": "情绪周期流", "title": "情绪周期高低切换",
                "theory": "行情初期做低位，行情末期做高位，中位股是大坑",
                "quotes": ["高位看情绪，低位看逻辑，中位尽量少参与", "计划你的交易，交易你的计划", "确定性小用试错仓，确定性大才上主仓"],
                "risk": ["避中位股", "不在高潮入场"], "position": "试错仓→主仓 分级", "buy_rule": "阶段切换点",
            },
            "陈小群": {
                "school": "情绪周期流", "title": "人气龙头博弈",
                "theory": "龙头死于加速，分歧才能走得更远",
                "quotes": ["该弱不弱，即为强；该强不强，即为弱", "龙头死于加速，分歧才能走得更远", "被重点监控、人气消散的妖股坚决回避"],
                "risk": ["避监控妖股", "人气散了立刻走"], "position": "主升浪中等", "buy_rule": "人气龙头分歧回踩",
            },
            # ===== 龙头战法流 =====
            "赵老哥": {
                "school": "龙头战法流", "title": "八年一万倍 · 龙头打板集大成者",
                "theory": "只做龙头、只做主升、只做惯性；跟风股三不：不看、不买、不研究",
                "quotes": [
                    "**二板定龙头，一板能看出个毛**",
                    "有新题材，坚决抛弃旧题材",
                    "买在分歧，卖在一致；弱转强是买点，强转弱是卖点",
                    "有三必有五，有五必成妖",
                ],
                "risk": ["亏 5% 必割", "次日竞价割肉", "错误单不过夜", "退潮期不逆势"],
                "position": "启动期试错→发酵期加仓→高潮期减仓→退潮期空仓",
                "buy_rule": "二板确认龙头→打板/回封",
            },
            "Asking": {
                "school": "龙头战法流", "title": "龙头战法鼻祖",
                "theory": "只做超强势股，下跌趋势的股票再便宜也不看",
                "quotes": ["龙头多条命，跟风死得快", "炒股炒的是想象力，题材想象力决定高度"],
                "risk": ["不看便宜", "只追超强势"], "position": "集中龙头", "buy_rule": "超强势股打板",
            },
            "著名刺客": {
                "school": "龙头战法流", "title": "小资金跟随主流",
                "theory": "小资金想要做大，唯有跟随主流，只做最强",
                "quotes": ["小资金想要做大，唯有跟随主流，**只做最强**", "天下模式万法归宗，核心就是**弱转强**", "买点放在分歧，卖点放在一致"],
                "risk": ["无换手不参与", "无量一字板少碰"], "position": "跟随主流仓位", "buy_rule": "弱转强+有换手",
            },
            # ===== 低吸反包流 =====
            "乔帮主": {
                "school": "低吸反包流", "title": "强势股低吸鼻祖 · 42个月500倍",
                "theory": "低吸=强势股回踩，不是越跌越买抄底下跌趋势",
                "quotes": ["低吸赚追涨人的钱，追涨赚打板人的钱", "无量不参与，资金回流才是买点", "超短买入，不涨停就要择机离场"],
                "risk": ["无量不参与", "不抄底下跌趋势"], "position": "低吸仓位", "buy_rule": "强势股缩量回踩+资金回流",
            },
            "作手新一": {
                "school": "低吸反包流", "title": "分歧低吸龙头",
                "theory": "龙头是走出来的，不是猜出来的；没有板块效应的孤板尽量少碰",
                "quotes": ["**龙头是走出来的，不是猜出来的**", "买入机会，卖出风险，胜负交给概率"],
                "risk": ["不追一致加速", "等资金确认"], "position": "2-4天有格局", "buy_rule": "板块分歧+龙头炸板大跌当天逆势低吸",
            },
            # ===== 趋势波段流 =====
            "章盟主": {
                "school": "趋势波段流", "title": "老牌稳健 · 百亿级",
                "theory": "只做龙头，只做主升，只做惯性；下降通道赚钱是偶然，亏钱是必然",
                "quotes": [
                    "**不会空仓的人，永远不会战斗**",
                    "假设自己是空仓，你还愿意买入这只票吗？",
                    "宁可错过，不可做错",
                ],
                "risk": ["忘记成本", "下降通道空仓"], "position": "主升持有", "buy_rule": "政策驱动+行业龙头+主升",
            },
            "方新侠": {
                "school": "趋势波段流", "title": "大格局趋势龙头锁仓",
                "theory": "短线做波段，看懂趋势拿住主升；人气票容错率最高",
                "quotes": [
                    "**高位放量滞涨，当天无条件减仓**",
                    "先手吃肉，后手买单；龙头死于加速，分歧才可走远",
                    "大题材才值得格局，小题材速战速决",
                ],
                "risk": ["高位放量滞涨减仓", "小市值勿格局"], "position": "大成交趋势锁仓", "buy_rule": "人气大票+主升段",
            },
            "孙哥": {
                "school": "趋势波段流", "title": "溧阳路 · 机构协同大票",
                "theory": "偏好科技AI、连板妖股与趋势加速，嗅觉敏锐；常与机构协同",
                "quotes": ["退潮看LV"], "risk": ["机构协同节奏"], "position": "中大盘", "buy_rule": "科技AI+趋势加速",
            },
            "葛卫东": {
                "school": "趋势波段流", "title": "混沌理论 · 只跟随大级别趋势",
                "theory": "混沌理论，不预测只跟随；大级别趋势一旦形成很难逆转",
                "quotes": ["在混沌中发现秩序，让趋势带你走"],
                "risk": ["不做震荡市", "只做60日级趋势"], "position": "大级别重仓", "buy_rule": "60日趋势斜率向上+完美多头",
            },
            # ===== 首板隔日套利流 =====
            "佛山无影脚": {
                "school": "首板隔日套利流", "title": "独食首板 · 隔日砸盘王",
                "theory": "擅长超跌首板、地天板，封板坚决；隔夜顶板暴力套利，隔日必砸",
                "quotes": ["独食首板，隔日必走"],
                "risk": ["佛山上榜隔日极易 A字杀，需规避"], "position": "低价小盘", "buy_rule": "超跌首板+筹码干净",
            },
            "成都帮": {
                "school": "首板隔日套利流", "title": "首板挖掘机 · 一日游",
                "theory": "超跌小盘首板，隔日兑现为主",
                "quotes": ["一日游，不恋战"],
                "risk": ["次日常砸"], "position": "小盘首板", "buy_rule": "超跌小盘首板",
            },
            # ===== 分仓复利悟道流 =====
            "退学炒股": {
                "school": "分仓复利悟道流", "title": "《我和小明》 · 回撤控制第一",
                "theory": "会空仓的，才是祖师爷；市场永远不缺机会，本金没了机会跟你无关",
                "quotes": ["**会空仓的，才是祖师爷**", "连续亏损，停止操作，不要急于回本", "看不懂就不做，不要为了交易而交易"],
                "risk": ["连续亏停止操作", "建错题集"], "position": "分仓小资金", "buy_rule": "空仓智慧",
            },
            "北京炒家": {
                "school": "分仓复利悟道流", "title": "分仓复利代表",
                "theory": "放弃暴富幻想，接受小亏小赚，靠分仓复利滚大资金",
                "quotes": ["不要单票重仓，把风险控制在可承受范围"],
                "risk": ["不单票重仓"], "position": "分散分仓", "buy_rule": "分仓控制风险",
            },
            "涅槃重升": {
                "school": "分仓复利悟道流", "title": "周期悟道",
                "theory": "行情在绝望中诞生，在犹豫中成长，在疯狂中灭亡",
                "quotes": ["行情在绝望中诞生，在犹豫中成长，在疯狂中灭亡"],
                "risk": ["情绪拐点"], "position": "底部布局", "buy_rule": "情绪绝望拐点",
            },
            # ===== 强势股+大盘方向（已工程化） =====
            "瑞鹤仙": {
                "school": "强势股+均线+大盘方向", "title": "24条心法 · 三层过滤",
                "theory": "只做强势顺势，**逆势选股转势买股**；分歧时买，一致时卖；本质：右侧验证+风控闭环",
                "quotes": [
                    "只做强势顺势，逆势选股转势买股",
                    "分歧时买，一致时卖",
                    "不融资不梭哈，设止损不扛单",
                    "盘前计划，盘中不临时决策",
                    "复盘重亏损，记情绪日记",
                ],
                "risk": ["破均线止损", "月 30% 连续小胜"], "position": "金字塔 2-3 成首仓", "buy_rule": "阻力最小方向→金字塔加仓",
            },
        }
        # 跨流派通用铁律
        UNIVERSAL_RULES = [
            ("只做最强/龙头", "不做杂毛、不碰跟风；龙头多条命，跟风死得快"),
            ("买分歧，卖一致", "分歧低吸，一致（高潮）卖出；弱转强买，强转弱卖"),
            ("严格止损", "亏损 3-5% 必割，错误单不过夜，不扛单"),
            ("空仓智慧", "退潮期/无主线/看不懂 → 空仓；会空仓才是祖师爷"),
            ("忘记成本", "假设自己空仓还愿不愿买；不被持仓成本绑架决策"),
            ("不补仓摊薄", "被套加仓是大忌，越补越套"),
            ("计划交易", "盘前计划，盘中不临时起意"),
            ("情绪周期", "启动试错→发酵加仓→高潮减仓→退潮空仓"),
        ]
        # 推荐决策链路
        DECISION_CHAIN = [
            ("分仓复利悟道流", "动不动手"),
            ("情绪周期流", "该不该激进"),
            ("瑞鹤仙", "大盘方向"),
            ("龙头/低吸/趋势/首板", "选流派买点"),
            ("fibonacci-070-786", "结构回踩买点"),
            ("costline_alert", "成本风控"),
        ]
        HOTMONEY = [
            ("赵老哥", _score_zhaoge, "涨停板战法", True),
            ("炒股养家", _score_chai, "集合竞价/情绪周期", True),
            ("方新侠", _score_fang, "大资金波段/低吸", True),
            ("章盟主", _score_zhang, "低估值+行业龙头", False),
            ("葛卫东", _score_ge, "混沌大级别趋势", False),
            ("作手新一", _score_xin, "新生代情绪龙头", False),
            ("瑞鹤仙", _score_rhx, "只做强势/均线多头", True),
        ]
        # ===== UI: 参照持股仪表盘 =====
        win = tk.Toplevel(self.root); win.title("🦅 游资心法速查")
        win.geometry("1100x750"); win.configure(bg="white")
        banner = tk.Frame(win, bg="#1A237E"); banner.pack(fill=tk.X)
        tk.Label(banner, text="🦅 游资心法速查  —  7大游资 × 多股票同时扫描",
                 bg="#1A237E", fg="white", font=("", 13, "bold")).pack(side=tk.LEFT, padx=12, pady=6)
        status_var = tk.StringVar(value="请勾选标签页 + 游资 → 点 🦅 扫描游资心法")
        tk.Label(banner, textvariable=status_var, bg="#1A237E", fg="#FFD54F",
                 font=("", 10)).pack(side=tk.RIGHT, padx=12)
        # ===== 流派地图 (可折叠, 默认展开) =====
        map_frame = tk.Frame(win, bg="#ECEFF1")
        map_frame.pack(fill=tk.X, padx=8, pady=(4, 0))
        def _toggle_map():
            if map_inner.winfo_ismapped():
                map_inner.pack_forget(); toggle_btn.config(text="📖 流派地图 ▼ (点击展开)")
            else:
                map_inner.pack(fill=tk.X, padx=6, pady=2); toggle_btn.config(text="📖 流派地图 ▲ (点击折叠)")
        toggle_btn = tk.Button(map_frame, text="📖 流派地图 ▲ (点击折叠)", bg="#ECEFF1",
                               fg="#1A237E", font=("", 9, "bold"), relief=tk.FLAT, cursor="hand2",
                               command=_toggle_map)
        toggle_btn.pack(anchor="w", padx=6, pady=2)
        map_inner = tk.Frame(map_frame, bg="#ECEFF1")
        for sname, scolor, speople, skill, remark in SCHOOLS:
            row = tk.Frame(map_inner, bg="#ECEFF1"); row.pack(fill=tk.X, padx=4, pady=1)
            tk.Label(row, text=sname, bg=scolor, fg="white", font=("", 9, "bold"),
                     padx=8, pady=1).pack(side=tk.LEFT, padx=(0, 6))
            tk.Label(row, text=f"👤 {speople}", bg="#ECEFF1", fg="#333", font=("", 9)).pack(side=tk.LEFT, padx=(0, 12))
            tk.Label(row, text=f"💡 {skill}", bg="#ECEFF1", fg="#555", font=("", 8)).pack(side=tk.LEFT, padx=(0, 12))
            tk.Label(row, text=remark, bg="#ECEFF1", fg=scolor, font=("", 8, "bold")).pack(side=tk.RIGHT)
        tk.Label(map_inner, text="⚠️ 游资心法仅供参考, 量化围猎时代多数已失效. 核心价值: 风控+情绪周期+大级别趋势",
                 bg="#ECEFF1", fg="#C62828", font=("", 8, "italic")).pack(anchor="w", padx=6, pady=(4, 2))
        # 标签页选择 (复用 ALL_GROUPS)
        ALL_GROUPS_HM = [
            (1,"自持股",True),(2,"龙头股",True),(4,"Main",True),(6,"同花顺",True),
            (5,"持仓历史股",False),(3,"15Min",False),
            (7,"标签1",False),(8,"标签2",False),(9,"标签3",False),(10,"标签4",False),
            (11,"标签5",False),(12,"标签6",False),(13,"标签7",False),(14,"标签8",False),
        ]
        def _get_group_stocks(gi):
            hs = getattr(self, "holding_stocks" if gi==1 else f"holding_stocks_{gi}", [None]*80)
            return [(i, h) for i,h in enumerate(hs) if h]
        def _count_group(gi):
            return len(_get_group_stocks(gi))
        def _pull_holdings(gis):
            import re as _re
            seen = set(); out = []
            for gi in gis:
                for _, h in _get_group_stocks(gi):
                    try:
                        nm, cd = h[0], str(h[1])
                        m = _re.search(r"(\d{6})", cd)
                        pure = m.group(1) if m else cd
                        ts = pure + (".BJ" if pure[:2] in ("43","83","87","92") else
                                     ".SH" if pure[:1] in ("6","5","9") else ".SZ")
                        key = (nm.strip(), pure)
                        if key in seen: continue
                        seen.add(key)
                        out.append({"name": nm.strip(), "code": pure, "ts_code": ts, "group": gi})
                    except:
                        continue
            return out
        ctrl = tk.Frame(win, bg="#F5F5F5"); ctrl.pack(fill=tk.X, padx=8, pady=4)
        # 标签页
        tk.Label(ctrl, text="📋 持仓:", bg="#F5F5F5", font=("", 9, "bold")).grid(row=0, column=0, padx=4, sticky="w")
        group_vars_hm = {}
        for idx, (gi, gn, def_on) in enumerate(ALL_GROUPS_HM):
            cnt = _count_group(gi)
            v = tk.BooleanVar(value=def_on); group_vars_hm[gi] = v
            tk.Checkbutton(ctrl, text=f"{gn}({cnt})", variable=v, bg="#F5F5F5",
                           font=("", 8)).grid(row=idx//7+1, column=idx%7, padx=2, sticky="w")
        # 游资选择提示 (7 位默认全扫, 去掉可勾选 — 没意义)
        tk.Label(ctrl, text="🦅 游资: 赵老哥/炒股养家/方新侠/章盟主/葛卫东/作手新一/瑞鹤仙 (全扫)",
                 bg="#F5F5F5", font=("", 9), fg="#666").grid(row=len(ALL_GROUPS_HM)//7+2, column=0,
                                                            columnspan=8, padx=4, sticky="w")
        scan_btn = tk.Button(ctrl, text="🦅 扫描游资心法", bg="#1A237E", fg="white", font=("", 11, "bold"), relief=tk.FLAT, padx=12)
        scan_btn.grid(row=len(ALL_GROUPS_HM)//7+3, column=0, padx=4, pady=4, sticky="w")
        # ===== 🆕 游资卡片模式 Checkbutton =====
        _card_mode_var = tk.BooleanVar(value=False)
        card_cb = tk.Checkbutton(ctrl, text="🧬 游资卡片 (带生命周期检查)", variable=_card_mode_var,
                                  bg="#F5F5F5", fg="#1A237E", font=("", 9, "bold"), cursor="hand2")
        card_cb.grid(row=len(ALL_GROUPS_HM)//7+3, column=1, padx=4, pady=4, sticky="w")
        # ===== 游资资讯按钮 =====
        def _show_youzi_news():
            """游资资讯窗口: 纯粹查本程序资讯DB (news_info 表) 的最近历史数据"""
            import sqlite3 as _sq3
            win2 = tk.Toplevel(win); win2.title("🦁 游资资讯速查 (本地DB)"); win2.geometry("1200x640")
            # 顶部工具条
            top = tk.Frame(win2, bg="#ECEFF1"); top.pack(fill=tk.X, pady=4, padx=6, side=tk.TOP)
            tk.Label(top, text="📅 最近", bg="#ECEFF1", font=("", 10)).pack(side=tk.LEFT, padx=(0, 4))
            days_var = tk.StringVar(value="30")
            for d in [3, 7, 15, 30, 60, 180]:
                tk.Radiobutton(top, text=f"{d}天", variable=days_var, value=str(d),
                               bg="#ECEFF1", font=("", 10)).pack(side=tk.LEFT, padx=2)
            tk.Label(top, text="   🔎 关键词:", bg="#ECEFF1", font=("", 10)).pack(side=tk.LEFT, padx=(12, 4))
            kw_var = tk.StringVar(value="游资,赵老哥,炒股养家,方新侠,章盟主,葛卫东,作手新一,瑞鹤仙,陈小群,92科比,佛山,成都帮,上塘路,刺客,Asking,养家心法")
            tk.Entry(top, textvariable=kw_var, width=55).pack(side=tk.LEFT, padx=4)
            go_btn = tk.Button(top, text="🔍 查DB", bg="#C62828", fg="white",
                               font=("", 10, "bold"), relief=tk.FLAT, padx=10, cursor="hand2")
            go_btn.pack(side=tk.LEFT, padx=8)
            tk.Label(top, text="   💡 双击行看全文 | Ctrl+多选", bg="#ECEFF1", font=("", 9), fg="#666").pack(side=tk.RIGHT, padx=6)

            # ---- 先放底部元素 (pack BOTTOM 优先) ----
            status_var = tk.StringVar(value="就绪")
            tk.Label(win2, textvariable=status_var, bg="#ECEFF1", fg="#666", font=("", 9)).pack(fill=tk.X, side=tk.BOTTOM)

            # AI 分析条 (在 status 上方)
            ai_bar = tk.Frame(win2, bg="#FFF8E1"); ai_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 2))
            sel_var = tk.StringVar(value="0")
            tk.Label(ai_bar, textvariable=sel_var, bg="#FFF8E1", fg="#C62828", font=("", 10, "bold")).pack(side=tk.LEFT, padx=(6, 2))
            tk.Label(ai_bar, text="条被选中", bg="#FFF8E1", fg="#666", font=("", 10)).pack(side=tk.LEFT)
            tk.Label(ai_bar, text="  |  ⌘A全选 / Ctrl+点击多选", bg="#FFF8E1", fg="#888", font=("", 9)).pack(side=tk.LEFT)
            # 按钮先创建占位, 后面 _ai_analyze 函数定义完再绑定 command
            ai_btn = tk.Button(ai_bar, text="🤖 AI分析选中", bg="#1A237E", fg="white", font=("", 10, "bold"),
                               relief=tk.FLAT, padx=10, cursor="hand2")
            ai_btn.pack(side=tk.RIGHT, padx=6, pady=3)

            # ---- 结果区: Treeview (最后 pack, expand 占满剩余) ----
            body = tk.Frame(win2); body.pack(fill=tk.BOTH, expand=True, padx=6, pady=4, side=tk.TOP)
            # Treeview 列表 (extended=Ctrl多选)
            import tkinter.ttk as _ttk
            cols = ("日期", "来源", "匹配关键词", "内容摘要")
            tree_n = _ttk.Treeview(body, columns=cols, show="headings", height=14, selectmode="extended")
            tree_n.heading("日期", text="📅 日期")
            tree_n.heading("来源", text="📋 来源")
            tree_n.heading("匹配关键词", text="🏷️ 匹配关键词")
            tree_n.heading("内容摘要", text="📝 内容摘要")
            tree_n.column("日期", width=140, anchor="w")
            tree_n.column("来源", width=180, anchor="w")
            tree_n.column("匹配关键词", width=160, anchor="w")
            tree_n.column("内容摘要", width=700, anchor="w")
            sb_n = tk.Scrollbar(body, orient=tk.VERTICAL, command=tree_n.yview)
            tree_n.configure(yscrollcommand=sb_n.set)
            tree_n.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb_n.pack(side=tk.RIGHT, fill=tk.Y)

            # 全局存储全文: id -> full_content
            _full_map = {}

            def _open_full(event=None):
                """双击打开完整内容"""
                sel = tree_n.selection()
                if not sel: return
                rid = sel[0]
                full = _full_map.get(rid, "")
                if not full: return
                win3 = tk.Toplevel(win2); win3.title(f"📄 资讯详情 #{rid}"); win3.geometry("900x600")
                tab = tree_n.set(rid, "来源")
                dtm = tree_n.set(rid, "日期")
                head = tk.Frame(win3, bg="#ECEFF1"); head.pack(fill=tk.X)
                tk.Label(head, text=f"📋 {tab}  |  📅 {dtm}", bg="#ECEFF1", font=("", 11, "bold"),
                         fg="#1A237E").pack(pady=8)
                txt3 = _st.ScrolledText(win3, font=("Menlo", 10), wrap=tk.WORD, bg="white")
                txt3.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
                txt3.insert(tk.END, full)
                txt3.config(state=tk.DISABLED)

            tree_n.bind("<Double-1>", _open_full)
            # 右键菜单
            right_menu = tk.Menu(win2, tearoff=0)
            right_menu.add_command(label="📄 查看全文 (双击)", command=_open_full)
            right_menu.add_command(label="📋 复制摘要", command=lambda: win2.clipboard_append(tree_n.set(tree_n.selection()[0], "内容摘要") if tree_n.selection() else ""))
            tree_n.bind("<Button-3>", lambda e: right_menu.tk_popup(e.x_root, e.y_root))

            def _on_select(event=None):
                sel_var.set(str(len(tree_n.selection())))
            tree_n.bind("<<TreeviewSelect>>", _on_select)

            def _ai_analyze(btn_widget):
                """后台线程调 AI, 提取游资→股票→逻辑"""
                sel_ids = tree_n.selection()
                if not sel_ids:
                    status_var.set("⚠️ 请先选中至少一条资讯 (Ctrl+点击 多选)")
                    return
                # 拼接全文 (单条 2000 上限, 总计 15000 上限)
                MAX_TOTAL = 15000; MAX_ONE = 2000
                chunks = []; total = 0
                for rid in sel_ids:
                    full = _full_map.get(rid, "")
                    piece = full[:MAX_ONE]
                    if total + len(piece) > MAX_TOTAL:
                        piece = piece[:MAX_TOTAL - total]
                    chunks.append(f"--- #{rid} [{tree_n.set(rid,'日期')}] 来源:{tree_n.set(rid,'来源')} ---\n{piece}")
                    total += len(piece)
                    if total >= MAX_TOTAL: break
                text_block = "\n\n".join(chunks)
                # 禁用按钮 + 状态
                btn_widget.config(state=tk.DISABLED, text="🤖 AI分析中...")
                status_var.set(f"🤖 分析 {len(chunks)} 条资讯 ({total} 字符)...")

                def _worker():
                    try:
                        system_prompt = (
                            "你是A股游资/私募/龙虎榜分析专家。从用户提供的资讯文本中，"
                            "按以下结构化格式输出：\n"
                            "1) 每个游资一行：**游资名** — 提及次数N次 — 活跃逻辑简述(20字内)\n"
                            "2) 每个游资下列出关联股票(代码+名称)和操作逻辑：\n"
                            "   - 代码 名称：操作方向(买入/卖出/打板/低吸/锁仓/砸盘) + 具体逻辑(引用资讯中原文的关键信息)\n"
                            "3) 最后给一句总评：当前游资生态风格(龙头/趋势/低吸/首板) + 可跟随操作建议\n"
                            "信息不足时如实说'未提及', 不要编造。"
                        )
                        user_prompt = f"以下是选中的资讯原文 (共{len(chunks)}条, {total}字符), 请分析：\n\n{text_block}"
                        result = self.call_ai_model(user_prompt, system_prompt, max_tokens=2000)
                        # UI 切回主线程
                        def _show_result():
                            btn_widget.config(state=tk.NORMAL, text="🤖 AI分析选中")
                            status_var.set(f"✅ AI 分析完成 ({len(chunks)} 条)")
                            # 弹窗展示
                            wr = tk.Toplevel(win2); wr.title(f"🤖 AI 游资分析 ({len(chunks)} 条)"); wr.geometry("960x640")
                            hdr = tk.Frame(wr, bg="#1A237E"); hdr.pack(fill=tk.X)
                            tk.Label(hdr, text=f"🤖 AI 游资资讯分析  —  {len(chunks)} 条 / {total} 字符",
                                     bg="#1A237E", fg="white", font=("", 11, "bold")).pack(pady=6)
                            txt_w = _st.ScrolledText(wr, font=("Menlo", 11), wrap=tk.WORD, bg="#FAFAFA")
                            txt_w.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
                            # 配色 tag
                            txt_w.tag_configure("hotmoney", foreground="#C62828", font=("", 11, "bold"))
                            txt_w.tag_configure("stock", foreground="#1565C0", font=("", 11, "bold"))
                            txt_w.tag_configure("logic", foreground="#2E7D32")
                            txt_w.tag_configure("header", foreground="#1A237E", font=("", 12, "bold"))
                            txt_w.insert(tk.END, result)
                            # 自动高亮 **text** 和 - 开头的股票行
                            import re as _re3
                            content = txt_w.get("1.0", tk.END)
                            txt_w.delete("1.0", tk.END); txt_w.insert(tk.END, result)
                            # 给 **bold** 上色 (简单处理)
                            for m in _re3.finditer(r'\*\*(.+?)\*\*', content):
                                txt_w.tag_add("hotmoney", f"1.0+{m.start()}c", f"1.0+{m.end()}c")
                            txt_w.config(state=tk.DISABLED)
                            tk.Button(wr, text="📋 复制全部", command=lambda: (wr.clipboard_clear(), wr.clipboard_append(content)),
                                      bg="#ECEFF1", font=("", 10)).pack(pady=4)
                        win2.after(0, _show_result)
                    except Exception as e:
                        def _err(e=e):
                            btn_widget.config(state=tk.NORMAL, text="🤖 AI分析选中")
                            status_var.set(f"❌ AI 分析失败: {str(e)[:60]}")
                            tk.messagebox.showerror("AI分析失败", str(e))
                        win2.after(0, _err)
                _th.Thread(target=_worker, daemon=True).start()

            # 绑定按钮 command (在函数定义后)
            ai_btn.config(command=lambda: _ai_analyze(ai_btn))
            # 全选快捷键 (仅当焦点在 tree_n 上时生效, 避免污染全局)
            tree_n.bind("<Command-a>", lambda e: [tree_n.selection_add(i) for i in tree_n.get_children()])
            tree_n.bind("<Control-a>", lambda e: [tree_n.selection_add(i) for i in tree_n.get_children()])

            def _load_news():
                days = int(days_var.get())
                kws = [k.strip() for k in kw_var.get().split(",") if k.strip()]
                status_var.set(f"⏳ 查本地资讯DB (最近 {days} 天, {len(kws)} 个关键词)...")
                win2.update_idletasks()
                # 清空
                for i in tree_n.get_children(): tree_n.delete(i)
                _full_map.clear()
                if not kws:
                    status_var.set("⚠️ 请输入至少一个关键词")
                    return

                try:
                    conn = _sq3.connect(DB_PATH)
                    cur = conn.cursor()
                    # 聚合SQL: 所有关键词 OR 组合, 一次查询搞定
                    like_parts = []
                    params = []
                    for kw in kws:
                        like_parts.append("(content LIKE ? OR tab_name LIKE ?)")
                        kw_like = f"%{kw}%"
                        params.extend([kw_like, kw_like])
                    where_clause = "(" + " OR ".join(like_parts) + ")"
                    # 加日期条件
                    date_sql = "datetime(created_at) >= datetime('now', ?)"
                    params.append(f"-{days} day")

                    sql = f"""
                        SELECT id, tab_name, content, created_at
                        FROM news_info
                        WHERE {where_clause} AND {date_sql}
                        ORDER BY created_at DESC LIMIT 500
                    """
                    cur.execute(sql, params)
                    rows = cur.fetchall()
                    conn.close()
                except Exception as e:
                    status_var.set(f"❌ DB查询失败: {str(e)[:80]}")
                    return

                total = len(rows)
                if total == 0:
                    status_var.set(f"📭 DB内无匹配记录 (最近{days}天, 请先在主界面爬取资讯)")
                    return

                # 去重 + 填充
                seen_ids = set()
                shown = 0
                for rid, tab, content, ctime in rows:
                    if rid in seen_ids: continue
                    seen_ids.add(rid)
                    content_str = str(content or "")
                    # 找出命中的关键词
                    hit_kws = [k for k in kws if k and (k in content_str or k in str(tab or ""))]
                    # 生成摘要: 去掉多余空行, 取前 180 字符
                    import re as _re2
                    clean = _re2.sub(r'\n{2,}', '\n', content_str).strip()
                    # 找到第一个命中关键词的位置, 取上下文
                    summary_start = 0
                    for hk in hit_kws:
                        idx = clean.find(hk)
                        if idx >= 0:
                            summary_start = max(0, idx - 30)
                            break
                    summary = clean[summary_start:summary_start+180].replace('\n', ' ')
                    if len(clean) > summary_start + 180:
                        summary += "..."

                    tab_display = (str(tab or "")[:28] + "..") if tab and len(str(tab)) > 28 else str(tab or "")
                    tree_n.insert("", tk.END, iid=str(rid),
                                  values=(ctime, tab_display, ",".join(hit_kws[:5]), summary))
                    _full_map[str(rid)] = content_str
                    shown += 1

                # 统计各来源分布
                tab_counts = {}
                for _, tab, _, _ in rows:
                    t = str(tab or "")[:20]
                    tab_counts[t] = tab_counts.get(t, 0) + 1
                top_tabs = sorted(tab_counts.items(), key=lambda x: -x[1])[:5]

                status_var.set(f"✅ 共 {total} 条匹配 (去重后 {shown} 条) | TOP来源: " +
                               " | ".join(f"{t}:{c}" for t, c in top_tabs))

            go_btn.config(command=_load_news); _load_news()
        youzi_btn = tk.Button(ctrl, text="🦁 游资资讯", bg="#C62828", fg="white", font=("", 10, "bold"),
                              relief=tk.FLAT, padx=10, cursor="hand2", command=_show_youzi_news)
        youzi_btn.grid(row=len(ALL_GROUPS_HM)//7+3, column=1, padx=4, pady=4, sticky="w")
        # ===== 主显示区: ScrolledText =====
        body = tk.Frame(win, bg="white"); body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        tree = _st.ScrolledText(body, font=("Menlo", 10), wrap=tk.NONE, bg="white", fg="#333")
        tree.pack(fill=tk.BOTH, expand=True)
        tree.tag_configure("rhx", background="#E8F5E9")
        tree.tag_configure("yhx", background="#FFF8E1")
        tree.tag_configure("bhx", background="#FFEBEE")
        tree.tag_configure("stk", foreground="#1A237E", font=("Menlo", 10, "bold"))
        tree.tag_configure("gn", foreground="#2E7D32", font=("Menlo", 10, "bold"))
        tree.tag_configure("rn", foreground="#C62828", font=("Menlo", 10, "bold"))
        tree.tag_configure("yn", foreground="#F57F17", font=("Menlo", 10, "bold"))
        tree._line_data = {}  # 行号 -> data dict
        # ===== 扫描 worker =====
        def _scan():
            sel_gis = [gi for gi,vv in group_vars_hm.items() if vv.get()]
            [(n,f,d) for (n,f,d,_) in HOTMONEY]  # 7 位游资默认全扫, 不再可勾选
            if not sel_gis: tk.messagebox.showinfo("提示", "请勾选持仓标签页"); return
            holdings = _pull_holdings(sel_gis)
            if not holdings: tk.messagebox.showwarning("提示", "所选标签页无股票"); return
            scan_btn.config(state=tk.DISABLED, text="⏳ 拉取当日行情...")
            win.after(0, lambda: tree.config(state=tk.NORMAL)); win.after(0, lambda: tree.delete("1.0", tk.END))
            win.after(0, lambda: tree.insert(tk.END, "⏳ 拉取当日行情 (2 次 API)..."))
            win.after(0, lambda: status_var.set(f"📊 拉 {len(holdings)} 只当日行情 (仅 2 次 API)..."))

            def worker():
                import json as _json_hm
                import os as _os_hm
                import subprocess as _sp_hm
                import time as _time

                try:
                    # === 独立 tushare 实例 ===
                    _pro = _ts_pro.pro_api()
                    today = _dt_now.now().strftime("%Y%m%d")
                    win.after(0, lambda: status_var.set("⏳ 算交易日历..."))
                    try:
                        _cal = _pro.trade_cal(exchange="SSE", start_date="20250601",
                                              end_date=today, is_open="1")
                        td = sorted(_cal["cal_date"].tolist()) if len(_cal) else [today]
                        latest = td[-1]
                    except Exception as e:
                        print(f"  trade_cal fail: {e}"); td = []; latest = today
                    holdings_list = [h["ts_code"] for h in holdings]

                    # ===== 情绪引擎 (qclaw skill) =====
                    win.after(0, lambda: status_var.set("⏳ 调用情绪周期流引擎..."))
                    emo_data = None; emo_stage = "震荡"
                    skill_py = _os_hm.path.expanduser("~/.qclaw/workspace-ek2hwmmwwhxi3mz3/skills/情绪周期流/scripts/情绪周期流_engine.py")
                    if _os_hm.path.exists(skill_py):
                        try:
                            r = _sp_hm.run(["python3", skill_py, "--market", "--json"],
                                           capture_output=True, text=True, timeout=8)
                            if r.returncode == 0 and r.stdout.strip(): emo_data = _json_hm.loads(r.stdout.strip())
                        except: pass
                    emo_stage = emo_data.get("emotion_stage", emo_data.get("stage", "震荡")) if emo_data else "震荡"
                    print(f"  🌊 情绪: {emo_stage}")

                    # ===== 5 线程并行拉每只股票 K 线 (仪表盘成功模式, 58只≈3s) =====
                    win.after(0, lambda: status_var.set(f"⏳ 并行拉 {len(holdings)} 只历史K线..."))
                    _t0 = _time.time()
                    hmap = {}
                    import concurrent.futures as _cf
                    def _one_fetch(tsc_b):
                        for attempt in range(3):
                            try:
                                _time.sleep(0.2 + attempt * 0.3)  # 首次200ms, 重试500/800ms
                                df_one = _pro.daily(ts_code=tsc_b, start_date="20250601", end_date=latest)
                                if df_one is not None and len(df_one) > 0:
                                    return tsc_b, df_one.sort_values("trade_date")
                            except Exception as e:
                                if attempt == 2:
                                    print(f"  ⚠️ {tsc_b} 3次失败: {str(e)[:40]}")
                                else:
                                    _time.sleep(0.5)
                        return tsc_b, None
                    with _cf.ThreadPoolExecutor(max_workers=5) as _pool:
                        for tsc_b, df_ok in _pool.map(_one_fetch, holdings_list):
                            if df_ok is not None:
                                hmap[tsc_b] = df_ok
                    ok_count = sum(1 for v in hmap.values() if v is not None and len(v) > 0)
                    print(f"  📊 K线: {_time.time()-_t0:.1f}s, 成功 {ok_count}/{len(holdings_list)}")

                    # ===== daily_basic (当日 1 次) =====
                    win.after(0, lambda: status_var.set("⏳ 拉 daily_basic..."))
                    bmap = {}
                    try:
                        df_b = _pro.daily_basic(trade_date=latest,
                                                fields="ts_code,pe_ttm,total_mv,turnover_rate,amount")
                        if df_b is not None and len(df_b) > 0:
                            for _, r2 in df_b.iterrows():
                                bmap[r2["ts_code"]] = r2
                    except: pass

                    # ===== 逐只计算 7 位游资评分 =====
                    win.after(0, lambda: status_var.set(f"⏳ 算 {len(holdings)} 只 × 7 位游资评分 (情绪【{emo_stage}】)..."))
                    results = []
                    for h in holdings:
                        tsc = h["ts_code"]
                        df = hmap.get(tsc)
                        b = bmap.get(tsc)
                        row = {"name": h["name"], "code": h["code"], "ts_code": tsc, "group": h["group"],
                               "scores": {}, "dims_map": {}}
                        price = None; pct = None; kline_data = None
                        if df is not None and len(df) >= 30:
                            df = df.sort_values("trade_date")
                            cl = df["close"].astype(float).tolist()
                            hi = df["high"].astype(float).tolist()
                            lo = df["low"].astype(float).tolist()
                            vo = df["vol"].astype(float).tolist()
                            op = df["open"].astype(float).tolist()
                            m5 = sum(cl[-5:])/5 if len(cl)>=5 else cl[-1]
                            m10 = sum(cl[-10:])/10 if len(cl)>=10 else cl[-1]
                            m20 = sum(cl[-20:])/20 if len(cl)>=20 else cl[-1]
                            price = cl[-1]; pct = (cl[-1]-cl[-2])/cl[-2]*100 if len(cl)>=2 else 0
                            vr = vo[-1]/(sum(vo[-20:])/20) if len(vo)>=20 and sum(vo[-20:])>0 else 1.0
                            dma = (price - m20)/m20*100
                            pct3 = (price - max(cl[-60:]))/max(cl[-60:])*100 if len(cl)>=60 else 0
                            tr = float(b["turnover_rate"]) if b is not None and b.get("turnover_rate") else None
                            kline_data = (cl, hi, lo, vo, op, tsc)
                            for nm, fn, desc, _ in HOTMONEY:
                                sc, dims, phi = fn(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, None, None)
                                if emo_data and emo_stage != "震荡":
                                    sch = TRA_TO_SCHOOL.get(nm, "")
                                    if sch in ("情绪周期流", "龙头战法流", "低吸反包流"):
                                        if emo_stage in ("冰点", "退潮"): sc -= 15; dims.append((f"情绪{emo_stage}","🔴","-15"))
                                        elif emo_stage in ("发酵", "高潮"): sc += 12; dims.append((f"情绪{emo_stage}","🟢","+12"))
                                        elif emo_stage == "启动": sc += 5; dims.append(("情绪启动","🟡","+5"))
                                sc = max(0, min(100, sc))
                                row["scores"][nm] = {"score": sc, "dims": dims, "phi": phi, "desc": desc}
                        row["price"] = price; row["pct"] = pct; row["kline_data"] = kline_data
                        row["emo_stage"] = emo_stage; row["turnover"] = tr
                        results.append(row)

                    # ===== 渲染 =====
                    is_card = _card_mode_var.get()
                    if is_card:
                        # --- 🧬 卡片模式: 先跑生命周期扫描, 再合并游资心法分 ---
                        win.after(0, lambda: status_var.set("⏳ 跑生命周期扫描 + 合并游资心法评分..."))
                        try:
                            # 把 holdings 转成 monitor_pool 格式
                            pool = [(h["name"], h["code"], h["group"]) for h in holdings]
                            # 调生命周期扫描 (内部已含 tushare token 初始化)
                            lc_data = self._run_lifecycle_scan(monitor_pool=pool)
                            lc_stocks = lc_data.get("stocks", [])
                        except Exception as _e_lc:
                            import traceback; traceback.print_exc()
                            lc_stocks = []
                            win.after(0, lambda _e_lc=_e_lc: status_var.set(f"⚠️ 生命周期扫描出错(降级文本): {_e_lc}"))

                        # 把游资心法的 avg_score / best_sch 合并进 lc_stocks
                        _code_map = {r["code"]: r for r in results}
                        for lc in lc_stocks:
                            r = _code_map.get(str(lc["code"]))
                            if r:
                                # 计算 avg + best
                                sc_vals = [d["score"] for d in r["scores"].values() if d and d.get("score") is not None]
                                lc["hm_avg"] = round(sum(sc_vals)/len(sc_vals), 1) if sc_vals else 0
                                sch_agg = {}
                                for hmn, sd in r["scores"].items():
                                    sch = TRA_TO_SCHOOL.get(hmn, "")
                                    if sch and sd: sch_agg.setdefault(sch, []).append(sd["score"])
                                lc["hm_sch"] = max(sch_agg.items(), key=lambda x: sum(x[1])/len(x[1]))[0][:8] if sch_agg else "-"
                            else:
                                lc["hm_avg"] = 0; lc["hm_sch"] = "-"

                        def _render_cards():
                            scan_btn.config(state=tk.NORMAL, text="🦅 重新扫描")
                            if not lc_stocks:
                                status_var.set(f"📭 所选股票均未命中生命周期筹码转折点信号 (共 {len(results)} 只)")
                                tk.messagebox.showinfo("🧬 游资卡片",
                                    f"共扫描 {len(results)} 只股票\n没有命中生命周期筹码转折点信号\n可取消'🧬游资卡片'勾选看普通游资心法分数")
                                return
                            # 调用已有的卡片弹窗展示
                            self._show_lifecycle_dialog({"trade_date": lc_data.get("trade_date",""), "stocks": lc_stocks,
                                                          "skip_count": lc_data.get("skip_count",{})})
                            status_var.set(f"✅ {len(lc_stocks)}/{len(results)} 只命中生命周期  | 🌊 情绪【{emo_stage}】")
                        win.after(0, _render_cards)
                    else:
                        # --- 文本表格模式 (原来的 _render) ---
                        def _render():
                            print(f"  🎨 _render called, results={len(results)}", flush=True)
                            tree.config(state=tk.NORMAL); tree.delete("1.0", tk.END); tree._line_data = {}
                            tree.tag_configure("red_fg", foreground="#C62828")
                            tree.tag_configure("green_fg", foreground="#2E7D32")
                            tree.tag_configure("bold", font=("", 9, "bold"))
                            tree.tag_configure("strong", foreground="#C62828", font=("", 9, "bold"))
                            tree.tag_configure("mid", foreground="#F57F17", font=("", 9, "bold"))
                            tree.tag_configure("weak", foreground="#2E7D32", font=("", 9, "bold"))
                            hotmoney_names = [n for (n,_,_,_) in HOTMONEY]
                            hdr_stk = f"{'股票':<10} {'代码':<10} {'组':<4} {'现价':>7} {'涨跌%':>7}"
                            hdr_hm = "".join(f" {n[:4]:>5}" for n in hotmoney_names)
                            hdr_end = f" {'总分':>5} {'流派':<8}"
                            tree.insert(tk.END, hdr_stk + hdr_hm + hdr_end + "\n", ("stk","bold"))
                            tree.insert(tk.END, "─" * 80 + "\n", ("stk",))
                            lc = 0
                            for r in results:
                                p = r.get("price"); pct = r.get("pct")
                                price_s = f"{p:.2f}" if p else "-"
                                pct_s = f"{pct:+.2f}" if pct is not None else "-"
                                line_parts = [f"{r['name']:<10}", f"{r['code']:<10}", f"{r['group']:<4}",
                                              f"{price_s:>7}", f"{pct_s:>7}"]
                                score_tags = []
                                for hmn in hotmoney_names:
                                    sc_dict = r["scores"].get(hmn)
                                    sc = sc_dict["score"] if sc_dict else None
                                    if sc is not None:
                                        col_tag = "strong" if sc >= 65 else ("mid" if sc >= 45 else "weak")
                                        score_tags.append((f" {sc:>5.0f}", (col_tag,)))
                                    else:
                                        score_tags.append((f" {'-':>5}", ()))
                                sc_vals = [d["score"] for d in r["scores"].values() if d and d.get("score") is not None]
                                total = sum(sc_vals) / len(sc_vals) if sc_vals else 0
                                sch_agg = {}
                                for hmn, sd in r["scores"].items():
                                    sch = TRA_TO_SCHOOL.get(hmn, "")
                                    if sch and sd: sch_agg.setdefault(sch, []).append(sd["score"])
                                best_sch = max(sch_agg.items(), key=lambda x: sum(x[1])/len(x[1]))[0] if sch_agg else "-"
                                total_tag = "strong" if total >= 65 else ("mid" if total >= 45 else "weak")
                                tree.insert(tk.END, "".join(line_parts))
                                for st, sts in score_tags:
                                    tree.insert(tk.END, st, sts)
                                tree.insert(tk.END, f" {total:>5.1f}", (total_tag, "bold"))
                                tree.insert(tk.END, f" {best_sch[:8]:<8}\n")
                                tree._line_data[lc] = r
                                lc += 1
                            tree.config(state=tk.DISABLED)
                            scan_btn.config(state=tk.NORMAL, text="🦅 重新扫描")
                            win.after(0, lambda: status_var.set(
                                f"✅ {lc}只 × 7游资 扫描完成 | 🌊 情绪【{emo_stage}】| 双击看详细评分"))
                        _render()

                except Exception as e:
                    import traceback; traceback.print_exc()
                    win.after(0, lambda e=e: status_var.set(f"❌ 扫描失败: {e}"))
                    win.after(0, lambda: scan_btn.config(state=tk.NORMAL, text="🦅 重新扫描"))
            _th.Thread(target=worker, daemon=True).start()
        scan_btn.config(command=_scan)
        # ===== 双击弹窗: 直接用预计算数据开弹窗 =====
        def _on_double(event):
            try:
                line = int(tree.index(f"@{event.x},{event.y}").split(".")[0]) - 1
                data = tree._line_data.get(line)
                if not data: return
                # scores 为空说明 K 线没拉到, 现场补算
                if not data.get("scores") or not data.get("kline_data"):
                    import tkinter.messagebox as _mb
                    _mb.showinfo("提示", f"{data['name']} 历史K线数据不足, 无法计算游资心法")
                    return
                _open_hm_detail(data)
            except Exception:
                import traceback; traceback.print_exc()

        # ===== 真正的弹窗渲染 =====
        def _open_hm_detail(data):
            try:
                print("  🦅=== _open_hm_detail START ===", flush=True)
                import tkinter.ttk as _ttk2

                import matplotlib
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                from matplotlib.figure import Figure
                matplotlib.use("TkAgg")

                # ===== 安全默认值 (防止 UnboundLocalError) =====
                m5 = m10 = m20 = m60 = 0.0
                boll_up = boll_mid = boll_lo = [50.0]
                dif = dea = [0.0]
                macd_hist = [0.0]
                kdj_k = kdj_d = kdj_j = [50.0]
                bias6 = bias12 = bias24 = [0.0]
                kline_cl = None
                _k2 = data.get("kline_data")
                if _k2 and len(_k2) == 6:
                    kline_cl, _kline_hi, _kline_lo, _kline_vo, _kline_op, _ = _k2
                    if kline_cl and len(kline_cl) >= 5:
                        m5 = sum(kline_cl[-5:])/5
                    if kline_cl and len(kline_cl) >= 10:
                        m10 = sum(kline_cl[-10:])/10
                    if kline_cl and len(kline_cl) >= 20:
                        m20 = sum(kline_cl[-20:])/20
                    if kline_cl and len(kline_cl) >= 60:
                        m60 = sum(kline_cl[-60:])/60
                print(f"  🦅 _open_hm_detail: {data['name']} m5={m5:.2f} m20={m20:.2f} kline={'OK' if kline_cl else '无'}", flush=True)

                top = tk.Toplevel(self.root)
                top.title(f"🦅 {data['name']} 游资心法全解")
                top.geometry("1280x820"); top.configure(bg="white")
                # Banner (左: 当前股票 | 中: 切换选择器 | 右: 最强流派)
                bn = tk.Frame(top, bg="#1A237E"); bn.pack(fill=tk.X)
                tk.Label(bn, text=f"🦅 {data['name']}({data['code']})  现价 {data.get('price','-')}",
                         font=("", 13, "bold"), bg="#1A237E", fg="white").pack(side=tk.LEFT, padx=14, pady=8)
                # ==== 切换股票区域 ====
                switch_f = tk.Frame(bn, bg="#1A237E"); switch_f.pack(side=tk.LEFT, padx=10)
                tk.Label(switch_f, text="🔄 切换:", bg="#1A237E", fg="#FFD54F", font=("", 9, "bold")).pack(side=tk.LEFT, padx=(0,4))
                # 候选列表: 从 table._line_data 拿 (所有扫描过的股票)
                candidates = []
                for _rd in tree._line_data.values():
                    candidates.append(f"{_rd['name']}({_rd['code']})")
                candidates = sorted(set(candidates))
                try:
                    cb = _ttk2.Combobox(switch_f, values=candidates, width=18, state="readonly", font=("", 9))
                    cb.set(f"{data['name']}({data['code']})")
                except:
                    cb = None
                if cb: cb.pack(side=tk.LEFT, padx=2)
                ent = tk.Entry(switch_f, width=10, font=("", 9), relief=tk.FLAT, bg="white")
                ent.pack(side=tk.LEFT, padx=2)
                ent.insert(0, "")
                tk.Label(switch_f, text="代码/名称", bg="#1A237E", fg="#B0BEC5", font=("", 7)).pack(side=tk.LEFT)

                def _switch_stock():
                    """解析选择器 → 找到目标股票 → 重新算游资心法 → 刷新弹窗"""
                    target_code = None; target_name = None; target_tsc = None
                    # 1) 优先看 Entry (手输代码或名称)
                    manual = ent.get().strip()
                    combo_val = cb.get() if cb else ""
                    search = manual or combo_val
                    if not search: return
                    # 先从已扫描的 _line_data 里找
                    for _rd in tree._line_data.values():
                        c = str(_rd.get("code", "")); n = str(_rd.get("name", "")); t = str(_rd.get("ts_code", ""))
                        if search in (c, n) or search in t or search in f"{n}({c})":
                            target_code = c; target_name = n; target_tsc = t
                            break
                    # 2) 没找到: 假设手输的是代码, 推断市场后缀
                    if not target_tsc and manual and manual.isdigit() and len(manual) == 6:
                        mc = manual
                        if mc.startswith(("6","9","5")): target_tsc = mc + ".SH"
                        elif mc.startswith(("0","3","2")): target_tsc = mc + ".SZ"
                        elif mc.startswith(("4","8","9")): target_tsc = mc + ".BJ"
                        target_code = mc
                        target_name = mc  # 暂时用代码当名字, 后面可能会从 tushare 拿真实名
                    if not target_tsc:
                        # 弹窗提示
                        import tkinter.messagebox as _mb
                        _mb.showinfo("提示", f"没找到股票: {search}\n请确认代码或名称正确")
                        return
                    # 构造新 data (先只放基础字段, 后续线程里补)
                    new_data = {"name": target_name, "code": target_code, "ts_code": target_tsc,
                                    "group": data.get("group", "-"), "price": None,
                                    "turnover": None, "amount": None}
                    # 如果是已扫描过的, 把基础行情带上
                    for _rd in tree._line_data.values():
                        if _rd.get("ts_code") == target_tsc:
                            new_data["price"] = _rd.get("price")
                            new_data["turnover"] = _rd.get("turnover")
                            break
                    # 关闭当前弹窗 → 后台算 → 重开
                    try: top.destroy()
                    except: pass
                    # 复用 _calc_and_open 的逻辑: 后台线程拉K线+情绪+评分 → 开新弹窗
                    def _bg_calc():
                        import json as _js3
                        import os as _os3
                        import subprocess as _sp3
                        _pro3 = _ts_pro.pro_api()
                        _today3 = _dt_now.now().strftime("%Y%m%d")
                        try:
                            _cal3 = _pro3.trade_cal(exchange="SSE", start_date="20250601",
                                                    end_date=_today3, is_open="1")
                            _latest3 = _cal3["cal_date"].max() if len(_cal3) else _today3
                        except: _latest3 = _today3
                        tsc3 = target_tsc
                        print(f"  🦅 切换股票: {tsc3}, latest={_latest3}", flush=True)
                        try:
                            df_k3 = _pro3.daily(ts_code=tsc3, start_date="20250601", end_date=_latest3)
                            print(f"  🦅 daily OK: {len(df_k3)} rows", flush=True)
                        except Exception as e:
                            print(f"  🦅 daily FAIL: {str(e)[:80]}", flush=True); df_k3 = None
                        # 情绪引擎
                        emo3 = None; emo_stage3 = "震荡"
                        skill_py3 = _os3.path.expanduser("~/.qclaw/workspace-ek2hwmmwwhxi3mz3/skills/情绪周期流/scripts/情绪周期流_engine.py")
                        if _os3.path.exists(skill_py3):
                            try:
                                    r3 = _sp3.run(["python3", skill_py3, "--market", "--json"],
                                              capture_output=True, text=True, timeout=8)
                                    if r3.returncode == 0 and r3.stdout.strip(): emo3 = _js3.loads(r3.stdout.strip())
                            except: pass
                        emo_stage3 = emo3.get("emotion_stage", emo3.get("stage", "震荡")) if emo3 else "震荡"
                        scores3 = {}; kline3 = None; price3 = new_data.get("price")
                        if df_k3 is not None and len(df_k3) >= 30:
                            df_k3 = df_k3.sort_values("trade_date")
                            cl3 = df_k3["close"].astype(float).tolist()
                            hi3 = df_k3["high"].astype(float).tolist()
                            lo3 = df_k3["low"].astype(float).tolist()
                            vo3 = df_k3["vol"].astype(float).tolist()
                            op3 = df_k3["open"].astype(float).tolist()
                            m5_3 = sum(cl3[-5:])/5 if len(cl3)>=5 else cl3[-1]
                            m10_3 = sum(cl3[-10:])/10 if len(cl3)>=10 else cl3[-1]
                            m20_3 = sum(cl3[-20:])/20 if len(cl3)>=20 else cl3[-1]
                            price3 = cl3[-1]
                            vr3 = vo3[-1]/(sum(vo3[-20:])/20) if len(vo3)>=20 and sum(vo3[-20:])>0 else 1.0
                            dma3 = (price3 - m20_3)/m20_3*100
                            pct3_3 = (price3 - max(cl3[-60:]))/max(cl3[-60:])*100 if len(cl3)>=60 else 0
                            kline3 = (cl3, hi3, lo3, vo3, op3, tsc3)
                            for nm, fn, desc in [(n,f,d) for (n,f,d,_) in HOTMONEY]:
                                    sc3, dims3, phi3 = fn(cl3, hi3, lo3, vo3, op3, vr3, dma3, pct3_3,
                                                     m5_3, m10_3, m20_3, None, None, None)
                                    if emo3 and emo_stage3 != "震荡":
                                        sch3 = TRA_TO_SCHOOL.get(nm, "")
                                    if sch3 in ("情绪周期流", "龙头战法流", "低吸反包流"):
                                        if emo_stage3 in ("冰点", "退潮"):
                                            sc3 -= 15; dims3.append((f"情绪{emo_stage3}", "🔴", "-15"))
                                        elif emo_stage3 in ("发酵", "高潮"):
                                            sc3 += 12; dims3.append((f"情绪{emo_stage3}", "🟢", "+12"))
                                        elif emo_stage3 == "启动":
                                            sc3 += 5; dims3.append(("情绪启动", "🟡", "+5"))
                                    scores3[nm] = {"score": max(0,min(100,sc3)), "dims": dims3, "phi": phi3, "desc": desc}
                        new_data["scores"] = scores3
                        new_data["kline_data"] = kline3
                        new_data["price"] = price3
                        new_data["emo_stage"] = emo_stage3
                        # 刷新 UI: 重新开弹窗
                        win.after(0, lambda: _open_hm_detail(new_data))
                    _th.Thread(target=_bg_calc, daemon=True).start()

                tk.Button(switch_f, text="▶ 确认", command=_switch_stock, bg="#FFD54F",
                          fg="#1A237E", font=("", 9, "bold"), relief=tk.FLAT, padx=8, pady=1).pack(side=tk.LEFT, padx=(2,0))

                sch_agg = {}
                for nm, d in data["scores"].items():
                    sch = TRA_TO_SCHOOL.get(nm, "")
                    sch_agg.setdefault(sch, []).append(d["score"])
                    best_sch = max(sch_agg.items(), key=lambda x: sum(x[1]))[0] if sch_agg else "-"
                tk.Label(bn, text=f"🏆 最强流派: {best_sch}", bg="#1A237E", fg="#FFD54F",
                         font=("", 11, "bold")).pack(side=tk.RIGHT, padx=14)

                # ===== Notebook 4 标签页 =====
                # ===== 公共量化指标 (Tab3/Tab4 复用) =====
                _q = {"ma_ok": False, "vr": 1.0, "up5": 0, "dn5": 0, "pct3": 0,
                      "bias20": 0, "limit_up": False, "limit_dn": False, "pc": 0, "p": 0,
                      "ema_rising": False, "vol_shrink": False, "vol_expand": False}
                _k2 = data.get("kline_data")
                _p2 = data.get("price"); _pc2 = data.get("pct") or 0
                _emo2 = data.get("emo_stage") or "震荡"
                if _k2 and _p2:
                    _cl2, _hi2, _lo2, _vo2, _op2, _ = _k2
                    _lst2 = len(_cl2)-1
                    _q.update({
                        "ma_ok": m5 > m10 > m20,
                        "ma60_ok": m20 > m60 if m60 else True,
                        "vr": _vo2[_lst2]/(sum(_vo2[-20:])/20) if len(_vo2)>=20 and sum(_vo2[-20:])>0 else 1.0,
                        "up5": sum(1 for i in range(-5,0) if i-1>=0 and _cl2[i]>_cl2[i-1]) if len(_cl2)>=6 else 0,
                        "dn5": sum(1 for i in range(-5,0) if i-1>=0 and _cl2[i]<_cl2[i-1]) if len(_cl2)>=6 else 0,
                        "pct3": (_p2 - max(_cl2[-60:]))/max(_cl2[-60:])*100 if len(_cl2)>=60 else 0,
                        "bias20": (_p2 - m20)/m20*100 if m20 else 0,
                        "limit_up": _pc2 >= 9.5, "limit_dn": _pc2 <= -9.5,
                        "pc": _pc2, "p": _p2,
                        "vol_shrink": _vo2[_lst2] < sum(_vo2[-5:])/5 * 0.7 if len(_vo2)>=5 else False,
                        "vol_expand": _vo2[_lst2] > sum(_vo2[-5:])/5 * 1.5 if len(_vo2)>=5 else False,
                    })
                _q["emo"] = _emo2

                nb = _ttk2.Notebook(top); nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
                sel_hm_now = [n for (n,_,_,_) in HOTMONEY if n in data.get("scores", {})]

                # ===== Tab1: 📊 心法评分 =====
                tab1 = tk.Frame(nb, bg="#F5F5F5"); nb.add(tab1, text=" 📊 心法评分 ")
                print("  🦅 Tab1 已创建", flush=True)
                # 左侧 = 游资卡片 (Canvas 滚动), 右侧 = K线+量能副图
                pw = _ttk2.PanedWindow(tab1, orient=tk.HORIZONTAL); pw.pack(fill=tk.BOTH, expand=True)
                left_f = tk.Frame(pw, bg="#F5F5F5"); pw.add(left_f, weight=3)
                right_f = tk.Frame(pw, bg="#FAFAFA"); pw.add(right_f, weight=5)
                # right_f 内部再分: K线图(left) + 信息面板(right, 同花顺风格)
                kline_f = tk.Frame(right_f, bg="#FAFAFA"); kline_f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                info_f = tk.Frame(right_f, bg="white", width=200); info_f.pack(side=tk.RIGHT, fill=tk.Y)
                info_f.pack_propagate(False)
                # 左侧: 卡片网格
                canvas = tk.Canvas(left_f, bg="#F5F5F5", highlightthickness=0)
                sb_c = tk.Scrollbar(left_f, orient=tk.VERTICAL, command=canvas.yview)
                canvas.configure(yscrollcommand=sb_c.set)
                sb_c.pack(side=tk.RIGHT, fill=tk.Y); canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                inner = tk.Frame(canvas, bg="#F5F5F5")
                canvas.create_window((0, 0), window=inner, anchor="nw")
                inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

                def _draw_progress(cv, x, y, score, w=180, h=14):
                    """Canvas 画彩色进度条: 灰底 → 红/黄/绿渐块 → 中间文字"""
                    cv.create_rectangle(x, y, x+w, y+h, fill="#E0E0E0", outline="", tags="bar")
                    color = "#2E7D32" if score >= 65 else ("#F57F17" if score >= 45 else "#C62828")
                    fill_w = max(4, int(score / 100.0 * w))
                    cv.create_rectangle(x, y, x+fill_w, y+h, fill=color, outline="", tags="bar")
                    cv.create_text(x + w/2, y + h/2, text=f"{score}", fill="white",
                                   font=("", 9, "bold"), tags="bar")

                for idx, nm in enumerate(sel_hm_now):
                    d = data["scores"][nm]
                    score = d["score"]
                    sch_nm = TRA_TO_SCHOOL.get(nm, "-")
                    sch_col = next((c for sn,c,_,_,_ in SCHOOLS if sn==sch_nm), "#555")
                    info = HOTMONEY_HEART.get(nm, {})
                    # 卡片
                    card = tk.Frame(inner, bg="white", relief=tk.RIDGE, bd=1)
                    card.grid(row=idx//2, column=idx%2, padx=6, pady=5, sticky="nsew")
                    # 头部
                    head = tk.Frame(card, bg=sch_col); head.pack(fill=tk.X)
                    tk.Label(head, text=f"🦅 {nm}", bg=sch_col, fg="white",
                             font=("", 11, "bold")).pack(side=tk.LEFT, padx=6, pady=3)
                    tk.Label(head, text=sch_nm, bg=sch_col, fg="white",
                             font=("", 8, "italic")).pack(side=tk.RIGHT, padx=6)
                    # 心法一句话
                    tk.Label(card, text=info.get("title", d["desc"]), bg="white", fg="#555",
                             font=("", 8), anchor="w").pack(fill=tk.X, padx=6, pady=(3, 0))
                    # Canvas 进度条 + 分数
                    cv = tk.Canvas(card, height=24, bg="white", highlightthickness=0)
                    cv.pack(fill=tk.X, padx=6, pady=4)
                    _draw_progress(cv, 0, 4, score, w=260)
                    # 维度明细 (grid 两列)
                    dv = tk.Frame(card, bg="white"); dv.pack(fill=tk.X, padx=4, pady=2)
                    for j, (ln, mark, pts) in enumerate(d["dims"]):
                        fg_dv = {"🟢": "#2E7D32", "🔴": "#C62828", "🟡": "#F57F17"}.get(mark, "#555")
                        tk.Label(dv, text=f"{mark} {ln}", bg="white", fg=fg_dv, font=("", 8)
                                 ).grid(row=j//2, column=j%2*2, sticky="w", padx=2, pady=1)
                        tk.Label(dv, text=pts, bg="white", fg=fg_dv, font=("", 8, "bold")
                                 ).grid(row=j//2, column=j%2*2+1, sticky="e", padx=2, pady=1)
                    # 风控快查
                    risks = info.get("risk", [])
                    if risks:
                        tk.Label(card, text="🛡️ " + "  |  ".join(risks[:2]), bg="white", fg="#666",
                                 font=("", 7, "italic"), anchor="w", wraplength=260, justify=tk.LEFT
                                 ).pack(fill=tk.X, padx=6, pady=(3, 4))

                # 右侧: K线图 + 指标副图 (同花顺风格: 主图叠加指标 + 副图切换 MACD/KDJ/BIAS)
                kd = data.get("kline_data")
                if kd:
                    from matplotlib.backends.backend_tkagg import (
                        FigureCanvasTkAgg,
                        NavigationToolbar2Tk,
                    )
                    cl, hi, lo, vo, op, _tsc = kd
                    # === 指标计算 (全部手写, 无 talib 依赖) ===
                    import math as _m
                    def _sma(a, n):
                        return [sum(a[max(0,i-n+1):i+1])/(i-max(0,i-n+1)+1) for i in range(len(a))]
                    def _ema(a, n):
                        k = 2/(n+1); r = [a[0]]
                        for i in range(1, len(a)): r.append(a[i]*k + r[-1]*(1-k))
                        return r
                    def _std(a, n):
                        r = [float("nan")]*len(a)
                        for i in range(n-1, len(a)):
                            seg = a[i-n+1:i+1]; m = sum(seg)/n
                            r[i] = (_m.sqrt(sum((x-m)**2 for x in seg)/n))
                        return r
                    # MA
                    m5 = _sma(cl, 5); m10 = _sma(cl, 10); m20 = _sma(cl, 20); m60 = _sma(cl, 60)
                    # BOLL (20 日, 2 倍标准差)
                    boll_mid = _sma(cl, 20); boll_std = _std(cl, 20)
                    boll_up = [boll_mid[i] + 2*boll_std[i] if not _m.isnan(boll_std[i]) else float("nan") for i in range(len(cl))]
                    boll_lo = [boll_mid[i] - 2*boll_std[i] if not _m.isnan(boll_std[i]) else float("nan") for i in range(len(cl))]
                    # MACD (12,26,9)
                    ema12 = _ema(cl, 12); ema26 = _ema(cl, 26)
                    dif = [ema12[i]-ema26[i] for i in range(len(cl))]
                    dea = _ema(dif, 9)
                    macd_hist = [2*(dif[i]-dea[i]) for i in range(len(cl))]
                    # KDJ (9,3,3)
                    kdj_k = [50.0]*len(cl); kdj_d = [50.0]*len(cl)
                    for i in range(len(cl)):
                        lo9 = min(lo[max(0,i-8):i+1]); hi9 = max(hi[max(0,i-8):i+1])
                        rsv = (cl[i]-lo9)/(hi9-lo9)*100 if hi9 != lo9 else 50
                        if i == 0: kdj_k[i]=kdj_d[i]=rsv
                        else:
                            kdj_k[i] = 2/3*kdj_k[i-1] + 1/3*rsv
                            kdj_d[i] = 2/3*kdj_d[i-1] + 1/3*kdj_k[i]
                    kdj_j = [3*kdj_k[i]-2*kdj_d[i] for i in range(len(cl))]
                    # BIAS (6,12,24)
                    bias6 = [(cl[i]-m5[i])/m5[i]*100 if m5[i] else 0 for i in range(len(cl))]  # 近5日
                    bias12 = [(cl[i]-m10[i])/m10[i]*100 if m10[i] else 0 for i in range(len(cl))]
                    bias24 = [(cl[i]-m20[i])/m20[i]*100 if m20[i] else 0 for i in range(len(cl))]

                    current_indicator = ["MACD"]  # 默认 MACD
                    def _draw_chart():
                        # 根据指标数量决定 subplot 布局 (K线 + 量能 + 指标副图)
                        fig.clear()
                        n_panels = 3  # K线 + 量能 + 指标
                        gs = fig.add_gridspec(n_panels, 1, height_ratios=[3, 1, 1], hspace=0.05)
                        ax_k = fig.add_subplot(gs[0], facecolor="#FAFAFA")
                        ax_v = fig.add_subplot(gs[1], facecolor="#FAFAFA", sharex=ax_k)
                        ax_i = fig.add_subplot(gs[2], facecolor="#FAFAFA", sharex=ax_k)
                        x = list(range(len(cl)))
                        cols_k = ["#C62828" if c >= o else "#2E7D32" for c, o in zip(cl, op)]
                        # ===== 主图: K线 + MA + BOLL =====
                        ax_k.bar(x, [h - l for h, l in zip(hi, lo)], bottom=lo, width=0.6, color=cols_k, alpha=0.5)
                        ax_k.bar(x, [abs(c - o) for c, o in zip(cl, op)], bottom=[min(c, o) for c, o in zip(cl, op)], width=0.6, color=cols_k)
                        ax_k.plot(range(len(cl)), m5, color="#FF9800", lw=1, label="MA5")
                        ax_k.plot(range(len(cl)), m10, color="#9C27B0", lw=1, label="MA10")
                        ax_k.plot(range(len(cl)), m20, color="#2196F3", lw=1.2, label="MA20")
                        ax_k.plot(range(len(cl)), m60, color="#6D4C41", lw=1.2, label="MA60", ls="--")
                        ax_k.plot(range(len(cl)), boll_up, color="#FF5722", lw=0.8, ls=":", label="BOLL上轨")
                        ax_k.plot(range(len(cl)), boll_mid, color="#FF5722", lw=0.8, ls="-", label="BOLL中轨")
                        ax_k.plot(range(len(cl)), boll_lo, color="#FF5722", lw=0.8, ls=":", label="BOLL下轨")
                        ax_k.set_title(f"{data['name']}({data['code']})  日K线  |  指标: {'/'.join(current_indicator)}", fontsize=10)
                        ax_k.legend(fontsize=6, loc="upper left", ncol=4); ax_k.grid(True, alpha=0.2)
                        ax_k.tick_params(labelbottom=False, labelsize=8)
                        # ===== 量能 =====
                        ax_v.bar(x, vo, color=cols_k, width=0.6, alpha=0.8)
                        if len(vo) >= 20:
                            mv20 = sum(vo[-20:]) / 20
                            ax_v.axhline(mv20, color="#2196F3", lw=0.8, ls="--", label="VOL_MA20")
                        ax_v.set_ylabel("成交量", fontsize=8); ax_v.legend(fontsize=7); ax_v.grid(True, alpha=0.2)
                        ax_v.tick_params(labelbottom=False, labelsize=8)
                        # ===== 指标副图 =====
                        ind = current_indicator[0]
                        if ind == "MACD":
                            ax_i.bar(x, macd_hist, color=["#C62828" if v >= 0 else "#2E7D32" for v in macd_hist], width=0.6, alpha=0.8)
                            ax_i.plot(x, dif, color="#FF9800", lw=1, label="DIF")
                            ax_i.plot(x, dea, color="#2196F3", lw=1, label="DEA")
                            ax_i.axhline(0, color="#999", lw=0.5)
                            ax_i.set_ylabel("MACD", fontsize=8)
                        elif ind == "KDJ":
                            ax_i.plot(x, kdj_k, color="#FF9800", lw=1, label="K")
                            ax_i.plot(x, kdj_d, color="#2196F3", lw=1, label="D")
                            ax_i.plot(x, kdj_j, color="#9C27B0", lw=1, label="J")
                            ax_i.axhline(80, color="#C62828", lw=0.5, ls="--"); ax_i.axhline(20, color="#2E7D32", lw=0.5, ls="--")
                            ax_i.set_ylabel("KDJ", fontsize=8); ax_i.set_ylim(-20, 120)
                        elif ind == "BIAS":
                            ax_i.plot(x, bias6, color="#FF9800", lw=1, label="BIAS6")
                            ax_i.plot(x, bias12, color="#2196F3", lw=1, label="BIAS12")
                            ax_i.plot(x, bias24, color="#9C27B0", lw=1, label="BIAS24")
                            ax_i.axhline(0, color="#999", lw=0.5)
                            ax_i.set_ylabel("BIAS%", fontsize=8)
                        elif ind == "BOLL":
                            # BOLL 已在主图叠加, 这里显示 %B 和带宽
                            pct_b = [(cl[i]-boll_lo[i])/(boll_up[i]-boll_lo[i]) if not _m.isnan(boll_up[i]-boll_lo[i]) else float("nan") for i in range(len(cl))]
                            ax_i.plot(x, pct_b, color="#2196F3", lw=1, label="%B")
                            ax_i.axhline(1, color="#C62828", lw=0.5, ls="--"); ax_i.axhline(0, color="#2E7D32", lw=0.5, ls="--")
                            ax_i.set_ylabel("BOLL %B", fontsize=8); ax_i.set_ylim(-0.5, 1.5)
                        ax_i.legend(fontsize=7, loc="upper left"); ax_i.grid(True, alpha=0.2)
                        cv2.draw_idle()

                    # 初始化 Figure
                    fig = Figure(figsize=(8, 8.5), dpi=90, facecolor="#FAFAFA")
                    cv2 = FigureCanvasTkAgg(fig, master=kline_f); cv2.draw()
                    # ① matplotlib 官方导航工具栏
                    tool_frame = tk.Frame(kline_f, bg="#FAFAFA")
                    tool_frame.pack(fill=tk.X, side=tk.TOP)
                    toolbar = NavigationToolbar2Tk(cv2, tool_frame)
                    toolbar.update()
                    # ② 快捷按钮 + 指标切换
                    btn_f = tk.Frame(kline_f, bg="#FAFAFA"); btn_f.pack(fill=tk.X, side=tk.TOP, padx=2, pady=1)
                    ind_f = tk.Frame(kline_f, bg="#FAFAFA"); ind_f.pack(fill=tk.X, side=tk.TOP, padx=2, pady=1)
                    full_xlim = (0, len(cl))
                    cv2._full_xlim = full_xlim
                    def _zoom_factory(factor):
                        def _zoom(event=None):
                            cur = fig.axes[0].get_xlim(); span = cur[1]-cur[0]
                            new_span = span*factor; center = (cur[0]+cur[1])/2
                            fig.axes[0].set_xlim(max(0,center-new_span/2), min(len(cl),center+new_span/2))
                            fig.canvas.draw_idle()
                        return _zoom
                    for t,f in [("10%",0.1),("25%",0.25),("50%",0.5)]:
                        tk.Button(btn_f, text=t, command=_zoom_factory(f), bg="#E3F2FD", font=("",8), relief=tk.FLAT).pack(side=tk.LEFT, padx=1)
                    tk.Button(btn_f, text="全部", command=lambda: (fig.axes[0].set_xlim(full_xlim), fig.canvas.draw_idle()), bg="#C8E6C9", font=("",8), relief=tk.FLAT).pack(side=tk.LEFT, padx=1)
                    tk.Button(btn_f, text="最新▶", command=lambda: (fig.axes[0].set_xlim(max(0,len(cl)-60),len(cl)), fig.canvas.draw_idle()), bg="#FFE0B2", font=("",8), relief=tk.FLAT).pack(side=tk.LEFT, padx=1)
                    tk.Label(btn_f, text="  🔍 滚轮缩放 | 🖱️ Shift+拖拽平移", bg="#FAFAFA", fg="#666", font=("",8)).pack(side=tk.RIGHT, padx=4)
                    # 指标切换按钮组
                    tk.Label(ind_f, text="📊 指标副图:", bg="#FAFAFA", font=("",9, "bold")).pack(side=tk.LEFT, padx=(0,4))
                    def _ind_factory(name, color):
                        def _switch():
                            current_indicator[0] = name
                            for b,_ in ind_btns: b.config(bg="#FFD54F" if b==btn else "#E0E0E0")
                            _draw_chart()
                        return _switch
                    ind_btns = []
                    for nm, col in [("MACD","#FF9800"),("KDJ","#9C27B0"),("BIAS","#2196F3"),("BOLL","#FF5722")]:
                        btn = tk.Button(ind_f, text=nm, command=_ind_factory(nm, col), bg="#FFD54F" if nm=="MACD" else "#E0E0E0",
                                        font=("",9, "bold"), relief=tk.FLAT, padx=6, pady=1)
                        btn.pack(side=tk.LEFT, padx=2); ind_btns.append((btn, nm))
                    tk.Label(ind_f, text="  (BOLL已在主图叠加, 此处%B)", bg="#FAFAFA", fg="#888", font=("",7)).pack(side=tk.LEFT, padx=4)
                    # 初始绘制
                    _draw_chart()
                    cv2.get_tk_widget().pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM)
                    # ③ 滚轮以鼠标位置为中心缩放
                    def _on_wheel(event):
                        if event.button not in (4,5): return
                        ax = fig.axes[0]; cur = ax.get_xlim(); span = cur[1]-cur[0]
                        try: mx = cur[0] + event.x/cv2.get_tk_widget().winfo_width()*span
                        except: mx = span/2
                        factor = 0.8 if event.button==4 else 1.25
                        new_span = max(3, span*factor)
                        new_left = mx - new_span*(mx-cur[0])/span
                        new_right = mx + new_span*(cur[1]-mx)/span
                        if new_left<0: new_left,new_right = 0,new_span
                        if new_right>len(cl): new_left,new_right = len(cl)-new_span,len(cl)
                        ax.set_xlim(new_left, new_right); fig.canvas.draw_idle()
                    cv2.get_tk_widget().bind("<Button-4>", _on_wheel)
                    cv2.get_tk_widget().bind("<Button-5>", _on_wheel)

                    # ===== 同花顺风格: 右侧信息面板 =====
                    last = len(cl) - 1  # 最新一根 K 线索引
                    prev_close = cl[-2] if len(cl) >= 2 else cl[0]
                    cur_price = cl[last]
                    chg_pct = (cur_price - prev_close) / prev_close * 100
                    color_up = "#C62828"; color_dn = "#2E7D32"
                    cur_col = color_up if chg_pct >= 0 else color_dn
                    # 信息面板分区
                    tk.Label(info_f, text=f"{data['name']}({data['code']})",
                             font=("", 11, "bold"), bg="white", fg="#1A237E").pack(pady=(10,2))
                    tk.Label(info_f, text=f"现价  {cur_price:.2f}",
                             font=("", 18, "bold"), bg="white", fg=cur_col).pack()
                    tk.Label(info_f, text=f"涨跌  {cur_price-prev_close:+.2f}  {chg_pct:+.2f}%",
                             font=("", 10, "bold"), bg="white", fg=cur_col).pack(pady=(0,6))
                    # 行情概览 (grid)
                    sec1 = tk.LabelFrame(info_f, text="📋 行情", bg="white", fg="#555",
                                         font=("", 8, "bold"), relief=tk.FLAT)
                    sec1.pack(fill=tk.X, padx=6, pady=2)
                    rows_info = [
                        ("今开", f"{op[last]:.2f}"),
                        ("最高", f"{hi[last]:.2f}", color_up if hi[last]>=op[last] else color_dn),
                        ("最低", f"{lo[last]:.2f}", color_dn if lo[last]<=op[last] else color_up),
                        ("昨收", f"{prev_close:.2f}"),
                        ("成交量", f"{vo[last]/1e4:.1f}万手"),
                    ]
                    for i, row in enumerate(rows_info):
                        tk.Label(sec1, text=row[0], bg="white", fg="#888", font=("", 8)
                                 ).grid(row=i, column=0, sticky="w", padx=4, pady=1)
                        col = row[2] if len(row) > 2 else "#333"
                        tk.Label(sec1, text=row[1], bg="white", fg=col, font=("", 8, "bold")
                                 ).grid(row=i, column=1, sticky="e", padx=4, pady=1)
                    # MA
                    sec2 = tk.LabelFrame(info_f, text="📈 均线 MA", bg="white", fg="#555",
                                         font=("", 8, "bold"), relief=tk.FLAT)
                    sec2.pack(fill=tk.X, padx=6, pady=2)
                    ma_items = [
                        ("MA5", m5[-1] if m5 else None, "#FF9800"),
                        ("MA10", m10[-1] if m10 else None, "#9C27B0"),
                        ("MA20", m20[-1] if m20 else None, "#2196F3"),
                        ("MA60", m60[-1] if m60 else None, "#6D4C41"),
                    ]
                    for i, (nm, val, col) in enumerate(ma_items):
                        if val is None: continue
                        diff_pct = (cur_price - val) / val * 100
                        dcol = color_up if diff_pct >= 0 else color_dn
                        tk.Label(sec2, text=nm, bg="white", fg=col, font=("", 8, "bold")
                                 ).grid(row=i, column=0, sticky="w", padx=4, pady=1)
                        tk.Label(sec2, text=f"{val:.2f}", bg="white", fg="#333", font=("", 8)
                                 ).grid(row=i, column=1, sticky="e", padx=4, pady=1)
                        tk.Label(sec2, text=f"{diff_pct:+.2f}%", bg="white", fg=dcol, font=("", 8, "bold")
                                 ).grid(row=i, column=2, sticky="e", padx=4, pady=1)
                    # BOLL
                    sec3 = tk.LabelFrame(info_f, text="🎯 布林 BOLL", bg="white", fg="#555",
                                         font=("", 8, "bold"), relief=tk.FLAT)
                    sec3.pack(fill=tk.X, padx=6, pady=2)
                    for i, (nm, val) in enumerate([
                        ("上轨", boll_up[last]),
                        ("中轨", boll_mid[last]),
                        ("下轨", boll_lo[last]),
                    ]):
                        if _m.isnan(val): continue
                        d_pct = (cur_price - val)/val*100
                        tk.Label(sec3, text=nm, bg="white", fg="#FF5722", font=("", 8, "bold")
                                 ).grid(row=i, column=0, sticky="w", padx=4, pady=1)
                        tk.Label(sec3, text=f"{val:.2f}", bg="white", fg="#333", font=("", 8)
                                 ).grid(row=i, column=1, sticky="e", padx=4, pady=1)
                        tk.Label(sec3, text=f"{d_pct:+.1f}%", bg="white",
                                 fg=color_up if d_pct>=0 else color_dn, font=("", 8, "bold")
                                 ).grid(row=i, column=2, sticky="e", padx=4, pady=1)
                    # MACD
                    sec4 = tk.LabelFrame(info_f, text="📊 MACD/KDJ/BIAS", bg="white", fg="#555",
                                         font=("", 8, "bold"), relief=tk.FLAT)
                    sec4.pack(fill=tk.X, padx=6, pady=2)
                    macd_val = macd_hist[last]
                    macd_col = color_up if macd_val >= 0 else color_dn
                    for i, (nm, val, col) in enumerate([
                        ("DIF", dif[last], "#FF9800"),
                        ("DEA", dea[last], "#2196F3"),
                        ("MACD", macd_val, macd_col),
                        ("K", kdj_k[last], "#FF9800"),
                        ("D", kdj_d[last], "#2196F3"),
                        ("J", kdj_j[last], "#9C27B0"),
                        ("BIAS6", bias6[last], "#FF9800"),
                        ("BIAS12", bias12[last], "#2196F3"),
                        ("BIAS24", bias24[last], "#9C27B0"),
                    ]):
                        tk.Label(sec4, text=nm, bg="white", fg=col, font=("", 8, "bold")
                                 ).grid(row=i, column=0, sticky="w", padx=4, pady=0)
                        tk.Label(sec4, text=f"{val:+.2f}" if nm.startswith("B") else f"{val:.2f}",
                                 bg="white", fg="#333", font=("", 8)
                                 ).grid(row=i, column=1, sticky="e", padx=4, pady=0)

                # ===== Tab2: 📖 心法语录 =====
                tab2 = tk.Frame(nb, bg="#FAFAFA"); nb.add(tab2, text=" 📖 心法语录 ")
                print("  🦅 Tab2 已创建", flush=True)
                txt2 = _st.ScrolledText(tab2, font=("Menlo", 10), wrap=tk.WORD, bg="#FAFAFA")
                txt2.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
                txt2.tag_configure("sch", foreground="#1A237E", font=("", 12, "bold"),
                                   background="#E8EAF6")
                txt2.tag_configure("hotm", foreground="#C62828", font=("", 11, "bold"))
                txt2.tag_configure("quote", foreground="#1565C0", font=("Menlo", 10, "italic"))
                txt2.tag_configure("bold", foreground="#C62828", font=("", 10, "bold"))
                txt2.tag_configure("theory", foreground="#424242", font=("", 9))
                txt2.tag_configure("risk", foreground="#2E7D32", font=("", 9))
                txt2.tag_configure("sep", foreground="#BDBDBD")

                # 按流派分组
                seen_sch = []
                for nm in sel_hm_now:
                    sch = TRA_TO_SCHOOL.get(nm, "-")
                    if sch not in seen_sch:
                        seen_sch.append(sch)
                for sch in seen_sch:
                    txt2.insert(tk.END, f"\n{'═'*60}\n")
                    txt2.insert(tk.END, f"🏛️  {sch}\n", "sch")
                    txt2.insert(tk.END, f"{'═'*60}\n", "sep")
                    for nm in sel_hm_now:
                        if TRA_TO_SCHOOL.get(nm) != sch: continue
                        info = HOTMONEY_HEART.get(nm, {})
                        txt2.insert(tk.END, f"\n🦅  {nm}", "hotm")
                        if info.get("title"):
                            txt2.insert(tk.END, f"  —  {info['title']}\n")
                        else:
                            txt2.insert(tk.END, "\n")
                        if info.get("theory"):
                            txt2.insert(tk.END, f"  📌 理论: {info['theory']}\n", "theory")
                        for q in info.get("quotes", []):
                            # 处理 **bold**
                            import re as _re_q
                            parts = _re_q.split(r'(\*\*.*?\*\*)', q)
                            txt2.insert(tk.END, "    💬 ")
                            for p in parts:
                                    if p.startswith("**") and p.endswith("**"):
                                        txt2.insert(tk.END, p[2:-2], "bold")
                                    else:
                                        txt2.insert(tk.END, p, "quote")
                            txt2.insert(tk.END, "\n")
                        risks = info.get("risk", [])
                        if risks:
                            txt2.insert(tk.END, "    🛡️ 风控: ", "risk")
                            txt2.insert(tk.END, " | ".join(risks) + "\n", "risk")
                        if info.get("position"):
                            txt2.insert(tk.END, "    📊 仓位: ", "risk")
                            txt2.insert(tk.END, info["position"] + "\n", "risk")
                        if info.get("buy_rule"):
                            txt2.insert(tk.END, "    🎯 买点: ", "risk")
                            txt2.insert(tk.END, info["buy_rule"] + "\n", "risk")

                # ===== 流派诊断函数 (供 Tab3 使用) =====
                def _school_judge(sn):
                    """返回 (emoji, 颜色, 判断句, 匹配度%)"""
                    q = _q; emo = q["emo"]
                    if sn == "情绪周期流":
                        # 核心: 换手率高 + 情绪匹配 + 不逆势
                        match = 0
                        if emo in ("冰点", "退潮"): match -= 30
                        if emo in ("启动", "发酵"): match += 20
                        if q["vr"] >= 1.2: match += 15
                        if q["pc"] >= 0: match += 10
                        if q["limit_up"]: match += 25
                        match = max(0, min(100, 50 + match))
                        if q["limit_up"] and emo in ("发酵", "高潮"):
                            return ("🟢", "#2E7D32", "✅ 情绪高潮+涨停, 情绪流最佳参与点", match)
                        elif emo in ("冰点", "退潮"):
                            return ("🔴", "#C62828", f"❌ 情绪【{emo}】, 情绪流原则上应空仓, 逆势必亏", match)
                        elif q["pc"] >= 3 and q["vr"] >= 1.2:
                            return ("🟢", "#2E7D32", "✅ 放量上涨+情绪配合, 情绪流可参与", match)
                        else:
                            return ("🟡", "#F57F17", f"⚠️ 情绪【{emo}】, 情绪特征不明显, 观望", match)
                    elif sn == "龙头战法流":
                        # 核心: 均线多头 + 强趋势 + 量能
                        match = 50
                        if q["ma_ok"]: match += 20
                        if q["limit_up"]: match += 25
                        if q["vr"] >= 1.5: match += 10
                        if q["pct3"] >= -5: match += 10  # 接近前高或创新高
                        if q["dn5"] >= 2: match -= 20
                        match = max(0, min(100, match))
                        if q["limit_up"] and q["ma_ok"]:
                            return ("🟢", "#2E7D32", "✅ 涨停+均线多头, 龙头战法核心标的", match)
                        elif q["ma_ok"] and q["vr"] >= 1.2:
                            return ("🟢", "#2E7D32", "✅ 均线多头+量能配合, 可关注龙头候选", match)
                        elif q["dn5"] >= 2 or not q["ma_ok"]:
                            return ("🔴", "#C62828", "❌ 均线空头或连跌, 龙头战法不做下降趋势", match)
                        else:
                            return ("🟡", "#F57F17", "⚠️ 特征中性, 是否龙头需结合板块地位", match)
                    elif sn == "低吸反包流":
                        # 核心: 强势股回调缩量 + 均线支撑
                        match = 50
                        if q["pc"] <= -2 and q["vol_shrink"]: match += 25
                        if q["bias20"] >= -3 and q["bias20"] <= 0: match += 15  # 靠近MA20
                        if q["ma_ok"]: match += 10
                        if q["dn5"] >= 3: match -= 15
                        match = max(0, min(100, match))
                        if q["pc"] <= -2 and q["vol_shrink"] and q["ma_ok"]:
                            return ("🟢", "#2E7D32", "✅ 回调缩量+均线多头, 低吸反包完美候选", match)
                        elif q["bias20"] >= -5 and q["bias20"] <= 0:
                            return ("🟡", "#F57F17", f"⚠️ 接近MA20支撑(偏离{q['bias20']:+.1f}%), 等待止跌信号", match)
                        elif q["dn5"] >= 3:
                            return ("🔴", "#C62828", f"❌ 连跌{q['dn5']}天, 可能继续下探, 别急着抄底", match)
                        else:
                            return ("🟡", "#F57F17", "⚠️ 无典型低吸特征, 耐心等缩量回踩", match)
                    elif sn == "趋势波段流":
                        # 核心: 均线多头 + 大级别趋势
                        match = 50
                        if q["ma_ok"] and q.get("ma60_ok", True): match += 25
                        if q["pct3"] >= 0: match += 10  # 创新高或接近
                        if q["pc"] >= 0: match += 5
                        if not q["ma_ok"]: match -= 30
                        match = max(0, min(100, match))
                        if q["ma_ok"] and q["pct3"] >= -5:
                            return ("🟢", "#2E7D32", "✅ 均线多头+接近前高, 趋势波段最佳持有/买入点", match)
                        elif q["ma_ok"]:
                            return ("🟢", "#2E7D32", "✅ 均线多头排列, 趋势向上, 可波段持有", match)
                        else:
                            return ("🔴", "#C62828", "❌ 均线空头排列, 下降通道, 趋势流应空仓", match)
                    elif sn == "首板隔日套利流":
                        # 核心: 低价小盘 + 首板涨停 (无法直接判断, 给中性判断)
                        if q["limit_up"] and q["vr"] >= 2.0:
                            return ("🟡", "#F57F17", "⚠️ 涨停+爆量, 若为首板可考虑, 但注意A字杀风险", 60)
                        elif q["limit_up"]:
                            return ("🟡", "#F57F17", "⚠️ 涨停, 首板套利需确认封板时间+封单量", 50)
                        else:
                            return ("🔴", "#C62828", "❌ 未涨停, 首板套利流无操作机会", 20)
                    elif sn == "分仓复利悟道流":
                        # 核心: 风险控制 — 永远适用, 但在退潮期特别重要
                        if emo in ("冰点", "退潮"):
                            return ("🟢", "#2E7D32", f"✅ 情绪【{emo}】, 分仓风控尤其重要, 建议降低仓位", 80)
                        elif q["dn5"] >= 2:
                            return ("🟢", "#2E7D32", f"✅ 连跌{q['dn5']}天, 分仓复利要求严格控回撤, 谨慎加仓", 75)
                        else:
                            return ("🟢", "#2E7D32", "✅ 分仓复利是总闸, 永远适用, 严格执行仓位纪律", 70)
                    return ("🟡", "#555", "—", 50)

                # ===== Tab3: 🗺️ 流派诊断 + 综合建议 (左右布局) =====
                tab3 = tk.Frame(nb, bg="#FAFAFA"); nb.add(tab3, text=" 🗺️ 流派诊断 ")
                print("  🦅 Tab3 已创建", flush=True)
                # 标题 + 量化概览
                tk.Label(tab3, text=f"🗺️ {data['name']}({data['code']}) 六大流派适配诊断 + 操作建议",
                         bg="#FAFAFA", fg="#1A237E", font=("", 12, "bold")).pack(anchor="w", padx=10, pady=(8,2))
                tk.Label(tab3, text=f"📊 现价 {_q['p']:.2f} | 涨跌 {_q['pc']:+.2f}% | 情绪【{_q['emo']}】| VR={_q['vr']:.1f}x | MA多头={'✅' if _q['ma_ok'] else '❌'} | 距60日高 {_q['pct3']:+.1f}%",
                         bg="#FAFAFA", fg="#555", font=("", 9)).pack(anchor="w", padx=10, pady=(0, 4))
                # 主体: 左流派卡片 + 右综合建议
                body3 = tk.Frame(tab3, bg="#FAFAFA"); body3.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
                # 左: 流派卡片 (可滚动)
                left3_host = tk.Frame(body3, bg="#FAFAFA"); left3_host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                left3_canvas = tk.Canvas(left3_host, bg="#FAFAFA", highlightthickness=0)
                left3_scroll = tk.Scrollbar(left3_host, orient=tk.VERTICAL, command=left3_canvas.yview)
                left3_canvas.configure(yscrollcommand=left3_scroll.set)
                left3_scroll.pack(side=tk.RIGHT, fill=tk.Y)
                left3_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                left3_inner = tk.Frame(left3_canvas, bg="#FAFAFA")
                left3_canvas.create_window((0,0), window=left3_inner, anchor="nw")
                left3_inner.bind("<Configure>", lambda e: left3_canvas.configure(scrollregion=left3_canvas.bbox("all")))

                # 右: 综合建议面板 (320px 固定宽)
                right3 = tk.Frame(body3, bg="#1A237E", width=320); right3.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
                right3.pack_propagate(False)
                tk.Label(right3, text="💡 综合操作建议", bg="#1A237E", fg="white",
                         font=("", 11, "bold"), pady=6).pack(fill=tk.X)
                advice_txt = scrolledtext.ScrolledText(right3, font=("", 9), wrap=tk.WORD,
                                                       bg="#0D1B3E", fg="#ECEFF1", height=26,
                                                       padx=8, pady=6)
                advice_txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
                advice_txt.tag_config("a_h", foreground="#FFD54F", font=("", 10, "bold"))
                advice_txt.tag_config("a_g", foreground="#66BB6A")  # 绿
                advice_txt.tag_config("a_r", foreground="#EF5350")  # 红
                advice_txt.tag_config("a_b", foreground="#64B5F6")  # 蓝
                advice_txt.tag_config("a_y", foreground="#FFD54F")  # 黄
                advice_txt.tag_config("a_w", foreground="#ECEFF1")  # 白

                # 先收集 6 大流派匹配度 (后面综合建议要用)
                school_scores = {}
                SCHOOL_CONDITIONS = {
                    "情绪周期流": "✅ 情绪发酵/高潮 + 量能放大\n❌ 冰点/退潮应空仓",
                    "龙头战法流": "✅ 均线多头 + 连板/涨停\n❌ 均线空头/下降通道不做",
                    "低吸反包流": "✅ 强势股缩量回调+MA20支撑\n❌ 连跌趋势别急抄底",
                    "趋势波段流": "✅ MA5>MA10>MA20>MA60主升浪\n❌ 下降通道坚决空仓",
                    "首板隔日套利流": "✅ 低价小盘首板+封板坚决\n❌ 非涨停无机会,警惕A字杀",
                    "分仓复利悟道流": "✅ 永远适用—严格控仓/不重仓\n❌ 任何时候都不能忘风控",
                }
                for i, (sn, col, reps, act, valid) in enumerate(SCHOOLS):
                    emoji, color, judge, pct = _school_judge(sn)
                    school_scores[sn] = {"pct": pct, "judge": judge, "color": color, "emoji": emoji}
                    card = tk.Frame(left3_inner, bg="white", relief=tk.RIDGE, bd=1)
                    card.pack(fill=tk.X, padx=8, pady=2)
                    left_c = tk.Frame(card, bg="white"); left_c.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    head = tk.Frame(left_c, bg="white"); head.pack(anchor="w", padx=6, pady=(4, 0))
                    tk.Label(head, text=f"🏛️ {sn}", bg=col, fg="white", font=("", 10, "bold"),
                             padx=6, pady=0).pack(side=tk.LEFT)
                    tk.Label(head, text=f"  👥{reps}", bg="white", fg="#666",
                             font=("", 8)).pack(side=tk.LEFT)
                    tk.Label(head, text=f"  {valid}", bg="white", fg="#888",
                             font=("", 8)).pack(side=tk.LEFT)
                    cond_text = SCHOOL_CONDITIONS.get(sn, "")
                    tk.Label(left_c, text=f"📋 {cond_text}", bg="white", fg="#555",
                             font=("", 8), justify=tk.LEFT).pack(anchor="w", padx=6, pady=(1, 4))
                    right_c = tk.Frame(card, bg="white"); right_c.pack(side=tk.RIGHT, fill=tk.Y, padx=4)
                    cv3 = tk.Canvas(right_c, width=110, height=14, bg="#EEEEEE",
                                    highlightthickness=0); cv3.pack(pady=(6, 1), anchor="w")
                    bar_col = "#2E7D32" if pct >= 65 else ("#F57F17" if pct >= 45 else "#C62828")
                    cv3.create_rectangle(0, 0, min(pct*1.1, 110), 14, fill=bar_col, outline="")
                    cv3.create_text(55, 7, text=f"{pct:.0f}%", fill="white", font=("", 8, "bold"))
                    tk.Label(right_c, text=judge, bg="white", fg=color, font=("", 9, "bold"),
                             wraplength=260, justify=tk.LEFT, anchor="w").pack(anchor="w", pady=(1, 4))

                # ===== 综合建议逻辑 =====
                def _gen_advice(q, ss):
                    """基于量化指标 + 流派匹配度生成操作建议"""
                    emo = q["emo"]; pc = q["pc"]; ma_ok = q["ma_ok"]
                    vr = q["vr"]; pct3 = q["pct3"]; limit_up = q["limit_up"]; limit_dn = q["limit_dn"]
                    dn5 = q["dn5"]; up5 = q["up5"]
                    lines = []
                    # 1. 操作方向 (最高匹配度流派决定)
                    best_sn = max(ss, key=lambda k: ss[k]["pct"])
                    best_pct = ss[best_sn]["pct"]
                    lines.append(("a_h", "🎯 操作方向判断\n"))
                    if emo in ("冰点", "退潮") and pc < 0:
                        lines.append(("a_r", "🔴 核心建议: 空仓观望\n"))
                        lines.append(("a_w", f"  情绪【{emo}】+ 当日跌 {pc:.1f}%, 逆势操作胜率极低\n"))
                    elif limit_up and ma_ok and vr >= 1.5:
                        lines.append(("a_g", "🟢 核心建议: 可考虑追涨买入\n"))
                        lines.append(("a_w", "  涨停 + 均线多头 + 量能放大, 属于强势龙头特征\n"))
                    elif ma_ok and pct3 < -3 and q["vol_shrink"]:
                        lines.append(("a_b", "🔵 核心建议: 低吸买入 (等缩量回踩)\n"))
                        lines.append(("a_w", f"  均线多头 + 距前高回撤 {abs(pct3):.1f}% + 缩量, 低吸反包机会\n"))
                    elif not ma_ok and pc <= -3 and dn5 >= 2:
                        lines.append(("a_r", "🔴 核心建议: 卖出止损, 勿抄底\n"))
                        lines.append(("a_w", f"  均线空头 + 连跌{dn5}天, 下降通道坚决空仓\n"))
                    else:
                        lines.append(("a_y", "🟡 核心建议: 观望为主\n"))
                        lines.append(("a_w", "  信号不明确, 等待更清晰的形态出现\n"))
                    # 2. 最佳适配流派
                    lines.append(("a_h", f"\n🏆 最佳适配流派: {best_sn} ({best_pct:.0f}%)\n"))
                    lines.append(("a_w", f"  {ss[best_sn]['judge']}\n"))
                    # 3. 风险预警 (从铁律提取)
                    lines.append(("a_h", "\n⚠️ 风险预警 (铁律联动)\n"))
                    risks = []
                    if emo in ("冰点", "退潮"): risks.append(("a_r", f"  · 情绪【{emo}】, 原则上应空仓\n"))
                    if limit_dn or pc <= -5: risks.append(("a_r", "  · 当日跌超5%, 已触止损线\n"))
                    if not ma_ok and dn5 >= 2: risks.append(("a_r", f"  · 均线空头 + 连跌{dn5}天, 下降通道\n"))
                    if not ma_ok and vr < 0.8: risks.append(("a_r", "  · 缩量 + 均线空头, 非强势\n"))
                    if pct3 > 15: risks.append(("a_y", f"  · 距60日高 +{pct3:.1f}%, 注意回调风险\n"))
                    if not risks:
                        lines.append(("a_g", "  ✅ 当前无明显铁律风险, 可正常操作\n"))
                    else:
                        for t, txt in risks: lines.append((t, txt))
                    # 4. 建议仓位
                    lines.append(("a_h", "\n💰 建议仓位 (分仓复利)\n"))
                    if emo in ("冰点", "退潮"):
                        lines.append(("a_r", "  🛡️ 0% — 情绪退潮期应空仓\n"))
                    elif emo == "高潮":
                        lines.append(("a_y", "  🛡️ ≤20% — 高潮期逐步减仓, 防止接盘\n"))
                    elif best_pct >= 75 and ma_ok:
                        lines.append(("a_g", "  ✅ 60-80% — 多流派匹配度高, 均线多头\n"))
                    elif best_pct >= 55:
                        lines.append(("a_y", "  ⚠️ 30-50% — 信号中等, 试错仓为主\n"))
                    else:
                        lines.append(("a_r", "  🛡️ 0-20% — 信号弱, 谨慎或空仓\n"))
                    # 5. 具体执行步骤
                    lines.append(("a_h", "\n📋 执行步骤\n"))
                    steps = []
                    if emo in ("冰点", "退潮"):
                        steps.append(("a_r", "  ① 空仓等待情绪拐点\n"))
                    elif limit_up:
                        steps.append(("a_g", "  ① 涨停价附近排队, 或次日竞价观察\n"))
                        steps.append(("a_b", "  ② 次日高开3%内可试错买入\n"))
                        steps.append(("a_r", "  ③ 次日低开>5%或炸板, 离场观望\n"))
                    elif best_sn == "低吸反包流" and ma_ok:
                        steps.append(("a_b", "  ① 等缩量回踩 MA20 附近\n"))
                        steps.append(("a_g", "  ② 触及后放倍量收阳, 买入\n"))
                        steps.append(("a_r", "  ③ 跌破 MA20, 止损离场\n"))
                    elif best_sn == "趋势波段流" and ma_ok:
                        steps.append(("a_b", "  ① 沿 MA20 持有, 不破不走\n"))
                        steps.append(("a_g", "  ② 每次放量突破前高, 可加仓\n"))
                        steps.append(("a_r", "  ③ MA20 拐头向下 + 放量, 减仓\n"))
                    else:
                        steps.append(("a_y", "  ① 先观察, 等明确信号出现\n"))
                        steps.append(("a_b", "  ② 可加入自选池跟踪\n"))
                    for t, txt in steps: lines.append((t, txt))
                    # 6. 逻辑依据
                    lines.append(("a_h", "\n📊 量化逻辑依据\n"))
                    lines.append(("a_w", f"  · 均线多头: {'✅' if ma_ok else '❌'}   · 涨停: {'✅' if limit_up else '❌'}\n"))
                    lines.append(("a_w", f"  · 量比 VR: {vr:.1f}x   · 距60日高: {pct3:+.1f}%\n"))
                    lines.append(("a_w", f"  · 情绪阶段: {emo}   · 当日涨跌: {pc:+.2f}%\n"))
                    lines.append(("a_w", f"  · 连涨{up5}天 连跌{dn5}天\n"))
                    return lines

                # 渲染综合建议
                adv_lines = _gen_advice(_q, school_scores)
                advice_txt.config(state=tk.NORMAL)
                advice_txt.delete("1.0", tk.END)
                for tag, txt in adv_lines:
                    advice_txt.insert(tk.END, txt, tag)
                advice_txt.config(state=tk.DISABLED)

                # 底部: 决策链路 (保留, 放左流派卡片下方)
                bot3 = tk.LabelFrame(left3_inner, text="🔗 推荐决策链路 (从上往下走)",
                                     bg="#FAFAFA", font=("", 9, "bold"))
                bot3.pack(fill=tk.X, padx=8, pady=6)
                for j, (step, desc) in enumerate(DECISION_CHAIN):
                    arrow = "▶" if j < len(DECISION_CHAIN) - 1 else "🎯"
                    tk.Label(bot3, text=f"{arrow} {step}  →  {desc}", bg="#FAFAFA",
                             font=("", 9), anchor="w").pack(fill=tk.X, padx=8, pady=2)

                # ===== Tab4: ⚡ 通用铁律 + 量化判断 (复用公共 _q) =====
                tab4 = tk.Frame(nb, bg="#FAFAFA"); nb.add(tab4, text=" ⚡ 铁律诊断 ")
                print(f"  🦅 Tab4 已创建, _q={_q}", flush=True)
                tk.Label(tab4, text=f"⚡ {data['name']}({data['code']}) 当日铁律诊断",
                         bg="#FAFAFA", fg="#1A237E", font=("", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
                tk.Label(tab4, text=f"📊 现价 {_q['p']:.2f} | 涨跌 {_q['pc']:+.2f}% | 情绪【{_q['emo']}】| VR={_q['vr']:.1f}x | MA多头={'✅' if _q['ma_ok'] else '❌'}",
                         bg="#FAFAFA", fg="#555", font=("", 9)).pack(anchor="w", padx=10, pady=(0, 6))

                def _judge_rule(idx):
                    q = _q; emo = q["emo"]; pc = q["pc"]
                    if idx == 0:  # 只做最强/龙头
                        if q["limit_up"] and q["ma_ok"]:
                            return ("🟢", "#2E7D32", "✅ 涨停+均线多头, 属于市场关注焦点")
                        elif q["ma_ok"] and q["vr"] >= 1.5:
                            return ("🟢", "#2E7D32", "✅ 均线多头+量能放大, 强势特征明显")
                        elif q["vr"] < 0.7 and not q["ma_ok"]:
                            return ("🔴", "#C62828", "❌ 缩量+均线空头, 非最强股, 注意跟风风险")
                        return ("🟡", "#F57F17", "⚠️ 特征中性, 是否最强需结合板块判断")
                    elif idx == 1:  # 买分歧卖一致
                        if pc <= -3 and q["vol_shrink"] and q["ma_ok"]:
                            return ("🟢", "#2E7D32", "✅ 分歧回调+量缩+均线多头, 适合低吸买入点")
                        elif pc >= 7 and q["vr"] > 2.0:
                            return ("🔴", "#C62828", "❌ 高潮大涨+爆量, 一致度高, 适合卖出而非买入")
                        return ("🟡", "#F57F17", "⚠️ 非典型分歧/一致, 观望为主")
                    elif idx == 2:  # 严格止损
                        if pc <= -5:
                            return ("🔴", "#C62828", "❌ 当日跌超5%, 已触3-5%止损线, 该割!")
                        elif q["dn5"] >= 3 and q["pct3"] < -8:
                            return ("🔴", "#C62828", f"❌ 近5日连跌{q['dn5']}天, 距60日高点{q['pct3']:+.1f}%, 止损预警!")
                        return ("🟢", "#2E7D32", "✅ 当前状态良好, 尚未触发止损阈值")
                    elif idx == 3:  # 空仓智慧
                        if emo in ("冰点", "退潮") and pc < 0:
                            return ("🔴", "#C62828", f"❌ 情绪【{emo}】+当日下跌, 空仓更安全, 别逆势!")
                        elif emo in ("冰点", "退潮"):
                            return ("🟡", "#F57F17", f"⚠️ 情绪【{emo}】, 原则上应空仓, 谨慎开新仓")
                        return ("🟢", "#2E7D32", f"✅ 情绪【{emo}】, 可积极操作")
                    elif idx == 4:  # 忘记成本
                        if not q["ma_ok"] and q["vr"] < 1.0:
                            return ("🔴", "#C62828", "❌ 均线空头+缩量, 假设空仓你还会买吗? 别被成本绑架!")
                        elif q["ma_ok"] and q["vr"] >= 1.0:
                            return ("🟢", "#2E7D32", "✅ 均线多头+量正常, 空仓状态下也值得买入, 成本不影响决策")
                        return ("🟡", "#F57F17", "⚠️ 特征混合, 建议客观评估而非锚定成本")
                    elif idx == 5:  # 不补仓摊薄
                        if q["dn5"] >= 2 and not q["ma_ok"]:
                            return ("🔴", "#C62828", f"❌ 连跌{q['dn5']}天+均线空头, 切勿补仓摊薄!")
                        return ("🟢", "#2E7D32", "✅ 当前无被套迹象, 无摊薄风险")
                    elif idx == 6:  # 计划交易
                        return ("🟡", "#F57F17", "⚠️ 需自行确认: 今天操作是否在盘前计划内?")
                    elif idx == 7:  # 情绪周期
                        if emo in ("启动", "发酵"):
                            return ("🟢", "#2E7D32", f"✅ 情绪【{emo}】, 启动试错/发酵加仓阶段, 可积极")
                        elif emo == "高潮":
                            return ("🟡", "#F57F17", f"⚠️ 情绪【{emo}】, 高潮阶段应逐步减仓")
                        elif emo in ("退潮", "冰点"):
                            return ("🔴", "#C62828", f"❌ 情绪【{emo}】, 退潮/冰点应空仓, 不逆势!")
                        return ("🟡", "#F57F17", f"⚠️ 情绪【{emo}】, 震荡阶段谨慎操作")
                    return ("🟡", "#555", "—")

                for i, (rule, desc) in enumerate(UNIVERSAL_RULES):
                    emoji, color, judge = _judge_rule(i)
                    card4 = tk.Frame(tab4, bg="white", relief=tk.RIDGE, bd=1)
                    card4.pack(fill=tk.X, padx=8, pady=2)
                    # 左: 铁律名 (红) + 描述 (灰小号, 同右对齐靠近)
                    left = tk.Frame(card4, bg="white"); left.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    tk.Label(left, text=f"{'⚔️' if i < 3 else '🛡️'}  {rule}",
                             bg="white", fg="#C62828", font=("", 10, "bold")
                             ).pack(side=tk.LEFT, padx=(6, 4), pady=4)
                    tk.Label(left, text=f"· {desc}", bg="white", fg="#888",
                             font=("", 8)).pack(side=tk.LEFT, pady=4)
                    # 右: 判断 (左对齐, 靠近铁律)
                    right = tk.Frame(card4, bg="white"); right.pack(side=tk.RIGHT, fill=tk.Y, padx=4)
                    tk.Label(right, text=judge, bg="white", fg=color,
                             font=("", 9, "bold"), anchor="w", justify=tk.LEFT, wraplength=300
                             ).pack(padx=4, pady=4)
                # 免责
                tk.Label(tab4, text="⚠️ 本文仅为历史交易理念复盘科普，不构成投资建议。股市有风险，入市需谨慎。",
                         bg="#FAFAFA", fg="#999", font=("", 8, "italic")).pack(anchor="w", padx=10, pady=12)
                print(f"  🦅=== _open_hm_detail DONE, Tab数={len(nb.tabs())} ===", flush=True)
            except Exception as ex:
                import traceback; traceback.print_exc()
                print(f"  🦅❌ _open_hm_detail EXCEPTION: {ex}", flush=True)
        tree.bind("<Double-1>", _on_double)

        # ===== 板块双击注入: 跳过扫描, 直接用完整弹窗 =====
        if getattr(self, '_hm_single_override', None):
            ov = self._hm_single_override
            self._hm_single_override = None
            # 注入 _line_data 让 _open_hm_detail 的切换区域也能引用
            tree._line_data[ov.get("code","")] = ov
            # ⚠️ 注意: 不能用 win 当 parent (它马上要被销毁), 用 self.root
            # 先开完整弹窗, 再关扫描弹窗 (顺序不能反!)
            def _do_open():
                _open_hm_detail(ov)   # 先开完整弹窗 (内部会创建 Toplevel)
                win.destroy()         # 再关扫描弹窗
            self.root.after(50, _do_open)
            return

    def _open_hotmoney_single_dialog(self, parent_win=None, current_stock_data=None,
                                      auto_code=None, auto_name=None):
        """🦅 游资心法全解 - 单股版: 下拉框选股票 → 确定 → 展示 7 位游资评分 + 综合建议
        auto_code/auto_name: 板块双击场景, 预填代码并自动触发分析"""
        import re
        import tkinter as tk
        from tkinter import ttk

        # ===== 7 位游资打分函数 (内嵌独立副本) =====
        def _score_zhaoge(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            dims = []; s = 50
            ma_ok = m5 > m10 > m20
            if ma_ok: s += 20; dims.append(("均线多头", "🟢", "+20"))
            else: s -= 15; dims.append(("均线排列", "🔴", "-15"))
            if vr >= 1.2 and vr <= 3.0: s += 15; dims.append(("量能配合", "🟢", "+15"))
            elif vr > 4: s -= 10; dims.append(("量能", "🟡", "-10 天量"))
            else: dims.append(("量能", "🟡", "0"))
            if pct3 >= -10: s += 10; dims.append(("位置", "🟢", "+10 接近新高"))
            elif pct3 <= -20: s -= 15; dims.append(("位置", "🔴", "-15 深套"))
            if len(cl) >= 5:
                r5 = (cl[-1] - cl[-5]) / cl[-5] * 100
                if r5 > 8: s += 15; dims.append(("5日涨幅", "🟢", f"+15 ({r5:+.1f}%)"))
                elif r5 < -8: s -= 10; dims.append(("5日涨幅", "🔴", f"-10 ({r5:+.1f}%)"))
            return max(0, min(100, s)), dims, "只做强势股, 顺势而为, 不抄底"
        def _score_chai(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            dims = []; s = 50
            if tr and tr > 8: s += 15; dims.append(("换手率", "🟢", f"+15 ({tr:.1f}%)"))
            elif tr and tr > 3: dims.append(("换手率", "🟡", "0"))
            else: s -= 10; dims.append(("换手率", "🔴", "-10 低换手"))
            if vr >= 1.5 and vr <= 4: s += 15; dims.append(("量能活跃", "🟢", "+15"))
            if m5 > m10 > m20: s += 15; dims.append(("均线多头", "🟢", "+15"))
            else: s -= 10; dims.append(("均线", "🔴", "-10"))
            if pct3 > 0: s += 10; dims.append(("新高", "🟢", "+10 创新高"))
            if len(hi) >= 10:
                amp = (max(hi[-10:]) - min(lo[-10:])) / min(lo[-10:]) * 100
                if amp > 20: s += 10; dims.append(("10日振幅", "🟢", f"+10 ({amp:.1f}%)"))
            return max(0, min(100, s)), dims, "情绪周期为王, 高换手热门股优先"
        def _score_fang(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            dims = []; s = 50
            if mv and mv > 100: s += 15; dims.append(("市值", "🟢", f"+15 ({mv/1e8:.0f}亿)"))
            elif mv and mv > 30: dims.append(("市值", "🟡", "0"))
            else: s -= 10; dims.append(("市值", "🔴", "-10 偏小"))
            if m5 > m10 > m20 and -8 < dma < -3: s += 20; dims.append(("低吸区间", "🟢", f"+20 ({dma:+.1f}%)"))
            elif m5 > m10 > m20: s += 10; dims.append(("均线多头", "🟢", "+10"))
            elif m5 < m10 < m20: s -= 20; dims.append(("均线空头", "🔴", "-20"))
            return max(0, min(100, s)), dims, "大资金波段, 低吸高抛, 趋势为王"
        def _score_zhang(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            dims = []; s = 50
            if pe and 0 < pe < 30: s += 20; dims.append(("PE估值", "🟢", f"+20 ({pe:.1f})"))
            elif pe and pe > 80: s -= 15; dims.append(("PE估值", "🔴", "-15 泡沫"))
            if mv and mv > 200: s += 15; dims.append(("大市值", "🟢", f"+15 ({mv/1e8:.0f}亿)"))
            if 1.0 <= vr <= 2.5: s += 10; dims.append(("量能温和", "🟢", "+10"))
            if m5 > m20: s += 10; dims.append(("趋势向上", "🟢", "+10"))
            else: s -= 10; dims.append(("趋势", "🔴", "-10"))
            return max(0, min(100, s)), dims, "大资金价值投资, 低估值+行业龙头"
        def _score_ge(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            dims = []; s = 50
            if len(cl) >= 60:
                from numpy.polynomial import polynomial as P
                x60 = list(range(60)); y60 = cl[-60:]
                slope = P.polyfit(x60, y60, 1)[1]
                slope_pct = slope / cl[-60] * 100 * 60
                if slope_pct > 20: s += 25; dims.append(("60日斜率", "🟢", f"+25 ({slope_pct:+.1f}%)"))
                elif slope_pct < -20: s -= 20; dims.append(("60日斜率", "🔴", f"-20 ({slope_pct:+.1f}%)"))
            if m5 > m10 > m20: s += 15; dims.append(("完美多头", "🟢", "+15"))
            elif m5 < m10 < m20: s -= 15; dims.append(("空头排列", "🔴", "-15"))
            return max(0, min(100, s)), dims, "混沌理论, 只跟随大级别趋势, 不预测"
        def _score_xin(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            dims = []; s = 50
            if len(cl) >= 3:
                r3 = (cl[-1] - cl[-3]) / cl[-3] * 100
                if r3 > 5: s += 15; dims.append(("3日涨幅", "🟢", f"+15 ({r3:+.1f}%)"))
                elif r3 < -5: s -= 10; dims.append(("3日涨幅", "🔴", f"-10 ({r3:+.1f}%)"))
            if tr and tr > 5: s += 15; dims.append(("换手率", "🟢", f"+15 ({tr:.1f}%)"))
            elif tr and tr < 1: s -= 10; dims.append(("换手率", "🔴", "-10 死水"))
            if vr >= 1.5: s += 10; dims.append(("量能放大", "🟢", "+10"))
            if pct3 > -5: s += 10; dims.append(("创新高", "🟢", "+10"))
            elif pct3 < -15: s -= 10; dims.append(("深套", "🔴", "-10"))
            return max(0, min(100, s)), dims, "情绪周期+龙头战法, 快速止损不扛单"
        def _score_rhx(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            dims = []; s = 50
            if m5 > m10 > m20: s += 25; dims.append(("均线多头", "🟢", "+25"))
            elif m5 < m10 < m20: s -= 25; dims.append(("均线空头", "🔴", "-25"))
            if 1.0 <= vr <= 2.0: s += 15; dims.append(("量能活跃", "🟢", "+15"))
            elif vr < 0.6: s -= 10; dims.append(("量能", "🔴", "-10 冷门"))
            elif vr > 3.0: s -= 15; dims.append(("量能", "🔴", "-15 天量"))
            if dma > 10: s -= 20; dims.append(("追高风险", "🔴", f"-20 ({dma:+.1f}%)"))
            elif -3 <= dma <= 3: s += 8; dims.append(("位置合理", "🟢", f"+8 ({dma:+.1f}%)"))
            if pct3 > -5: s += 10; dims.append(("接近新高", "🟢", f"+10 ({pct3:+.1f}%)"))
            elif pct3 < -20: s -= 15; dims.append(("深套", "🔴", f"-15 ({pct3:.1f}%)"))
            return max(0, min(100, s)), dims, "只做强势, 量能活跃, 不追高, 纪律至上"

        # ===== 7 位游资定义 + 流派映射 =====
        HM_LIST = [
            ("赵老哥", _score_zhaoge, "涨停板战法", True),
            ("炒股养家", _score_chai, "情绪周期", True),
            ("方新侠", _score_fang, "大资金波段", True),
            ("章盟主", _score_zhang, "大资金龙头", True),
            ("葛卫东", _score_ge, "混沌趋势", True),
            ("作手新一", _score_xin, "新生代情绪", True),
            ("瑞鹤仙", _score_rhx, "强势纪律", True),
        ]
        TRA_TO_SCHOOL = {
            "赵老哥": "龙头战法流", "炒股养家": "情绪周期流",
            "方新侠": "趋势波段流", "章盟主": "趋势波段流",
            "葛卫东": "趋势波段流", "作手新一": "低吸反包流",
            "瑞鹤仙": "龙头战法流",
        }

        # ===== 选择窗口 =====
        sel_win = tk.Toplevel(parent_win or self.root)
        sel_win.title("🦅 游资心法全解 - 选择股票")
        sel_win.geometry("520x220"); sel_win.configure(bg="#1A237E")
        sel_win.transient(parent_win or self.root)

        # Banner
        tk.Label(sel_win, text="🦅 游资心法全解 · 单股深度分析",
                 font=("", 14, "bold"), bg="#1A237E", fg="white").pack(pady=(14, 10))
        tk.Label(sel_win, text="下拉框选择持仓股，或手动输入6位代码/名称 → 确定",
                 font=("", 9), bg="#1A237E", fg="#FFD54F").pack(pady=(0, 8))

        # 选择区
        sel_frame = tk.Frame(sel_win, bg="#1A237E"); sel_frame.pack(pady=6)
        tk.Label(sel_frame, text="股票:", font=("", 11, "bold"), bg="#1A237E", fg="white").pack(side=tk.LEFT, padx=6)

        # 下拉框数据: 所有标签页的持仓股
        combo_items = []
        seen = set()
        try:
            all_h = self._get_all_holding_stocks()
            for sn, sc, gi, _pi in all_h:
                if sc not in seen:
                    seen.add(sc)
                    gi_name = {1: "持仓", 2: "龙头", 4: "Main", 6: "同花顺"}.get(gi, f"G{gi}")
                    combo_items.append(f"{sn}({sc})[{gi_name}]")
        except Exception:
            pass
        # 确保有默认热门股
        if not combo_items:
            try:
                from src.akshare_utils import get_news_stocks_merged_recent_days
                hot = get_news_stocks_merged_recent_days(ndays=3)
                for nm, cd in hot[:20]:
                    combo_items.append(f"{nm}({cd})[热门]")
            except Exception:
                pass

        stock_var = tk.StringVar(value="")
        cb = ttk.Combobox(sel_frame, textvariable=stock_var, values=combo_items,
                          width=24, font=("", 11), state="normal")
        cb.pack(side=tk.LEFT, padx=4)
        # 如果来自K线弹窗的当前股票，预填
        if current_stock_data:
            cn = current_stock_data.get("stock_name", "")
            if cn and combo_items:
                for item in combo_items:
                    if item.startswith(cn):
                        cb.set(item); break
                else:
                    cb.set(cn)
        # 板块双击场景: 预填代码+名称
        elif auto_code:
            auto_full = f"{auto_name or ''}({auto_code})[板块]"
            cb.set(auto_full)

        # 状态提示
        status_var = tk.StringVar(value="")
        tk.Label(sel_win, textvariable=status_var, font=("", 9), bg="#1A237E", fg="#FFCDD2").pack()

        # 确定按钮
        def _on_confirm():
            raw = stock_var.get().strip()
            if not raw:
                status_var.set("⚠️ 请选择或输入股票"); return
            # 解析代码和名称
            code_match = re.search(r"(\d{6})", raw)
            stock_code = code_match.group(1) if code_match else None
            name_match = re.match(r"([^(\[]+)", raw)
            stock_name = name_match.group(1).strip() if name_match else raw
            if not stock_code:
                # 尝试从名称反查
                try:
                    stock_code = get_stock_code_by_name(stock_name)
                except Exception:
                    pass
            if not stock_code:
                status_var.set("⚠️ 无法识别股票代码，请输入6位数字"); return
            sel_win.destroy()
            # 后台线程分析
            self._run_hotmoney_single_analysis(stock_code, stock_name, HM_LIST, TRA_TO_SCHOOL)

        tk.Button(sel_win, text="确定分析 →", command=_on_confirm,
                  font=("", 11, "bold"), bg="#FF6F00", fg="white",
                  padx=20, pady=4, cursor="hand2").pack(pady=(10, 6))

        # 板块双击场景: 弹窗创建后自动触发确定分析
        if auto_code:
            sel_win.title(f"🦅 游资心法全解 · 自动分析 {auto_name or auto_code}")
            sel_win.geometry("520x260")
            # 显示"自动分析中"提示, 200ms后自动点击确定
            tk.Label(sel_win, text=f"⏳ 正在自动分析 {auto_name}({auto_code})...",
                     font=("", 11, "bold"), bg="#1A237E", fg="#FFD54F").pack(pady=(6, 0))
            sel_win.after(250, _on_confirm)

    def _run_hotmoney_single_analysis(self, stock_code, stock_name, hm_list, tra_to_school):
        """后台线程: 拉K线 → 算分 → 弹窗展示"""
        import subprocess as _sp
        import threading as _th
        from datetime import datetime as _dt_now

        import tushare as _ts_pro

        # ===== 内嵌默认评分函数 (当外部传 None 时使用) =====
        def _score_zhaoge(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            dims = []; s = 50; ma_ok = m5 > m10 > m20
            s += 20 if ma_ok else -15; dims.append(("均线", "🟢" if ma_ok else "🔴", "+20" if ma_ok else "-15"))
            if 1.2 <= vr <= 3.0: s += 15; dims.append(("量能", "🟢", "+15"))
            if pct3 >= -10: s += 10; dims.append(("位置", "🟢", "+10"))
            elif pct3 <= -20: s -= 15; dims.append(("位置", "🔴", "-15"))
            if len(cl) >= 5:
                r5 = (cl[-1] - cl[-5]) / cl[-5] * 100
                if r5 > 8: s += 15; dims.append(("5日涨", "🟢", f"+15 ({r5:+.1f})"))
            return max(0, min(100, s)), dims, "只做强势股"
        def _score_chai(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            dims = []; s = 50
            if tr and tr > 8: s += 15; dims.append(("换手", "🟢", f"+15 ({tr:.1f})"))
            elif tr and tr < 1: s -= 10; dims.append(("换手", "🔴", "-10"))
            if 1.5 <= vr <= 4: s += 15; dims.append(("量能", "🟢", "+15"))
            ma_ok = m5 > m10 > m20
            s += 15 if ma_ok else -10; dims.append(("均线", "🟢" if ma_ok else "🔴", "+15" if ma_ok else "-10"))
            if pct3 > 0: s += 10; dims.append(("新高", "🟢", "+10"))
            return max(0, min(100, s)), dims, "情绪周期为王"
        def _score_fang(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            dims = []; s = 50
            if mv and mv > 100: s += 15; dims.append(("市值", "🟢", f"+15 ({mv/1e8:.0f}亿)"))
            elif mv and mv < 30: s -= 10; dims.append(("市值", "🔴", "-10"))
            if m5 > m10 > m20 and -8 < dma < -3: s += 20; dims.append(("低吸区", "🟢", f"+20 ({dma:+.1f}%)"))
            elif m5 < m10 < m20: s -= 20; dims.append(("空头", "🔴", "-20"))
            return max(0, min(100, s)), dims, "大资金波段"
        def _score_zhang(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            dims = []; s = 50
            if pe and 0 < pe < 30: s += 20; dims.append(("PE", "🟢", f"+20 ({pe:.1f})"))
            elif pe and pe > 80: s -= 15; dims.append(("PE", "🔴", "-15 泡沫"))
            if mv and mv > 200: s += 15; dims.append(("大市值", "🟢", "+15"))
            if 1.0 <= vr <= 2.5: s += 10; dims.append(("量能", "🟢", "+10"))
            if m5 > m20: s += 10; dims.append(("趋势", "🟢", "+10"))
            else: s -= 10; dims.append(("趋势", "🔴", "-10"))
            return max(0, min(100, s)), dims, "大资金价值投资"
        def _score_ge(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            dims = []; s = 50
            if len(cl) >= 60:
                from numpy.polynomial import polynomial as _P
                slope_pct = _P.polyfit(list(range(60)), cl[-60:], 1)[1] / cl[-60] * 100 * 60
                if slope_pct > 20: s += 25; dims.append(("60日斜率", "🟢", f"+25 ({slope_pct:+.1f})"))
                elif slope_pct < -20: s -= 20; dims.append(("60日斜率", "🔴", "-20"))
            ma_ok = m5 > m10 > m20
            s += 15 if ma_ok else -15; dims.append(("多头", "🟢" if ma_ok else "🔴", "+15" if ma_ok else "-15"))
            return max(0, min(100, s)), dims, "混沌大级别趋势"
        def _score_xin(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            dims = []; s = 50
            if len(cl) >= 3:
                r3 = (cl[-1] - cl[-3]) / cl[-3] * 100
                if r3 > 5: s += 15; dims.append(("3日涨", "🟢", f"+15 ({r3:+.1f})"))
                elif r3 < -5: s -= 10; dims.append(("3日涨", "🔴", "-10"))
            if tr and tr > 5: s += 15; dims.append(("换手", "🟢", f"+15 ({tr:.1f})"))
            if vr >= 1.5: s += 10; dims.append(("量能", "🟢", "+10"))
            if pct3 > -5: s += 10; dims.append(("创新高", "🟢", "+10"))
            return max(0, min(100, s)), dims, "情绪+龙头, 快速止损"
        def _score_rhx(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            dims = []; s = 50
            ma_ok = m5 > m10 > m20
            s += 25 if ma_ok else -25; dims.append(("均线", "🟢" if ma_ok else "🔴", "+25" if ma_ok else "-25"))
            if 1.0 <= vr <= 2.0: s += 15; dims.append(("量能", "🟢", "+15"))
            elif vr > 3.0: s -= 15; dims.append(("量能", "🔴", "-15 天量"))
            if dma > 10: s -= 20; dims.append(("追高", "🔴", f"-20 ({dma:+.1f}%)"))
            if pct3 > -5: s += 10; dims.append(("新高", "🟢", "+10"))
            return max(0, min(100, s)), dims, "强势纪律, 不追高"

        _DEFAULT_HM = [
            ("赵老哥", _score_zhaoge, "涨停板战法", True),
            ("炒股养家", _score_chai, "情绪周期", True),
            ("方新侠", _score_fang, "大资金波段", True),
            ("章盟主", _score_zhang, "大资金龙头", True),
            ("葛卫东", _score_ge, "混沌趋势", True),
            ("作手新一", _score_xin, "新生代情绪", True),
            ("瑞鹤仙", _score_rhx, "强势纪律", True),
        ]
        _DEFAULT_SCHOOL = {
            "赵老哥": "龙头战法流", "炒股养家": "情绪周期流",
            "方新侠": "趋势波段流", "章盟主": "趋势波段流",
            "葛卫东": "趋势波段流", "作手新一": "低吸反包流",
            "瑞鹤仙": "龙头战法流",
        }

        # 进度窗口
        prog = tk.Toplevel(self.root)
        prog.title(f"🦅 {stock_name} 游资心法分析中...")
        prog.geometry("400x160"); prog.configure(bg="#1A237E"); prog.transient(self.root)
        tk.Label(prog, text=f"🦅 正在分析 {stock_name}({stock_code})",
                 font=("", 12, "bold"), bg="#1A237E", fg="white").pack(pady=(20, 10))
        prog_status = tk.StringVar(value="⏳ 拉取K线数据...")
        tk.Label(prog, textvariable=prog_status, font=("", 10), bg="#1A237E", fg="#FFD54F").pack()

        def _bg():
            try:
                # ⚠️ 兜底: 如果外部传了 None, 用内嵌默认值
                nonlocal hm_list, tra_to_school
                if hm_list is None or len(hm_list) == 0:
                    hm_list = _DEFAULT_HM
                if tra_to_school is None or len(tra_to_school) == 0:
                    tra_to_school = _DEFAULT_SCHOOL
                # ⚠️ Treeview 会把全数字 str 转成 int, 这里强制转回 str
                nonlocal stock_code, stock_name
                stock_code = str(stock_code); stock_name = str(stock_name)

                _pro = _ts_pro.pro_api()
                today = _dt_now.now().strftime("%Y%m%d")
                # 交易日历
                try:
                    _cal = _pro.trade_cal(exchange="SSE", start_date="20250601",
                                          end_date=today, is_open="1")
                    td = sorted(_cal["cal_date"].tolist()) if len(_cal) else [today]
                    latest = td[-1]
                except Exception:
                    latest = today

                # 推断ts_code
                tsc = stock_code
                if stock_code.startswith(("6", "9", "5")): tsc += ".SH"
                elif stock_code.startswith(("0", "3", "2")): tsc += ".SZ"
                elif stock_code.startswith(("4", "8")): tsc += ".BJ"
                else: tsc += ".SZ"

                prog.after(0, lambda: prog_status.set("⏳ 拉取历史K线..."))
                df = _pro.daily(ts_code=tsc, start_date="20240601", end_date=latest)
                if df is None or len(df) < 30:
                    prog.after(0, lambda: prog_status.set("❌ K线数据不足"))
                    import tkinter.messagebox as _mb
                    prog.after(200, prog.destroy)
                    _mb.showwarning("提示", f"{stock_name} K线数据不足30天", parent=self.root)
                    return

                df = df.sort_values("trade_date")
                cl = df["close"].astype(float).tolist()
                hi = df["high"].astype(float).tolist()
                lo = df["low"].astype(float).tolist()
                vo = df["vol"].astype(float).tolist()
                op = df["open"].astype(float).tolist()
                dt_list = df["trade_date"].astype(str).tolist()  # 日期列表, 20240601格式
                m5 = sum(cl[-5:])/5 if len(cl)>=5 else cl[-1]
                m10 = sum(cl[-10:])/10 if len(cl)>=10 else cl[-1]
                m20 = sum(cl[-20:])/10 if len(cl)>=20 else cl[-1]  # 修正: /20
                m20 = sum(cl[-20:])/20 if len(cl)>=20 else cl[-1]
                m60 = sum(cl[-60:])/60 if len(cl)>=60 else cl[-1]
                price = cl[-1]
                pct_day = (cl[-1]-cl[-2])/cl[-2]*100 if len(cl)>=2 else 0
                vr = vo[-1]/(sum(vo[-20:])/20) if len(vo)>=20 and sum(vo[-20:])>0 else 1.0
                dma = (price - m20)/m20*100
                pct3 = (price - max(cl[-60:]))/max(cl[-60:])*100 if len(cl)>=60 else 0

                # daily_basic
                tr = pe = mv = None
                try:
                    df_b = _pro.daily_basic(ts_code=tsc, trade_date=latest,
                                            fields="turnover_rate,pe_ttm,total_mv")
                    if df_b is not None and len(df_b) > 0:
                        tr = float(df_b.iloc[0]["turnover_rate"]) if df_b.iloc[0].get("turnover_rate") else None
                        pe = float(df_b.iloc[0]["pe_ttm"]) if df_b.iloc[0].get("pe_ttm") else None
                        mv = float(df_b.iloc[0]["total_mv"]) if df_b.iloc[0].get("total_mv") else None
                except Exception:
                    pass

                # 情绪引擎
                prog.after(0, lambda: prog_status.set("⏳ 调用情绪周期流引擎..."))
                emo_stage = "震荡"
                skill_py = os.path.expanduser("~/.qclaw/workspace-ek2hwmmwwhxi3mz3/skills/情绪周期流/scripts/情绪周期流_engine.py")
                if os.path.exists(skill_py):
                    try:
                        r = _sp.run(["python3", skill_py, "--market", "--json"],
                                    capture_output=True, text=True, timeout=8)
                        if r.returncode == 0 and r.stdout.strip():
                            emo_data = json.loads(r.stdout.strip())
                            emo_stage = emo_data.get("emotion_stage", emo_data.get("stage", "震荡"))
                    except Exception:
                        pass

                # 计算 7 位游资评分
                prog.after(0, lambda: prog_status.set(f"⏳ 算 7 位游资评分 (情绪【{emo_stage}】)..."))
                scores = {}
                dims_map = {}
                for nm, fn, _desc, _ in hm_list:
                    sc, dims, phi = fn(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv)
                    # 情绪修正
                    if emo_stage != "震荡":
                        sch = tra_to_school.get(nm, "")
                        if sch in ("情绪周期流", "龙头战法流", "低吸反包流"):
                            if emo_stage in ("冰点", "退潮"):
                                    sc = max(0, sc - 15); dims.append((f"情绪{emo_stage}", "🔴", "-15"))
                            elif emo_stage in ("发酵", "高潮"):
                                    sc = min(100, sc + 12); dims.append((f"情绪{emo_stage}", "🟢", "+12"))
                            elif emo_stage == "启动":
                                    sc = min(100, sc + 5); dims.append(("情绪启动", "🟡", "+5"))
                    # ⚠️ 嵌套 dict 格式, 与正常扫描路径 _show_hotmoney_check 保持一致
                    scores[nm] = {"score": sc, "dims": dims, "phi": phi, "desc": _desc}
                    dims_map[nm] = (dims, phi)

                # 聚合流派
                sch_agg = {}
                for nm, d in scores.items():
                    sc = d["score"]  # 嵌套格式 → 取 .score
                    sch = tra_to_school.get(nm, "")
                    if sch: sch_agg.setdefault(sch, []).append(sc)
                    best_sch = max(sch_agg.items(), key=lambda x: sum(x[1])/len(x[1]))[0] if sch_agg else "-"
                avg_score = sum(d["score"] for d in scores.values()) / len(scores) if scores else 0

                # 关闭进度窗 → 开快速爬取的完整游资心法弹窗
                prog.after(0, prog.destroy)
                # 构造完整 data 字典, 注入 _show_hotmoney_check 用已有的完整弹窗
                data_dict = {
                    "code": stock_code, "name": stock_name,
                    "price": price, "ts_code": tsc,
                    "pct": pct_day, "pct_chg": pct_day,  # 两个都给, 兼容不同读取方
                    "kline_data": (cl, hi, lo, vo, op, dt_list or []),
                    "scores": scores, "dims_map": dims_map,
                    "tra_to_school": tra_to_school,
                    "avg_score": avg_score, "emo_stage": emo_stage,
                    "m5": m5, "m10": m10, "m20": m20, "m60": m60,
                    "vr": vr, "dma": dma, "pct3": pct3, "tr": tr,
                    "best_sch": best_sch,
                }
                self._hm_single_override = data_dict  # 让 _show_hotmoney_check 用
                self._show_hotmoney_check()

            except Exception as e:
                import traceback; traceback.print_exc()
                prog.after(0, prog.destroy)
                import tkinter.messagebox as _mb
                _mb.showerror("错误", f"分析失败: {e}", parent=self.root)

        _th.Thread(target=_bg, daemon=True).start()

    def _show_hotmoney_result_window(self, stock_code, stock_name, price, pct_day,
                                     scores, dims_map, tra_to_school, best_sch,
                                     avg_score, emo_stage, cl, hi, lo, vo, op,
                                     m5, m10, m20, m60, vr, dma, pct3, tr, dt_list=None):
        """展示单股游资心法结果 (4 Tab: 心法评分[含matplotlib K线] / 心法语录 / 流派诊断 / 铁律诊断)"""
        import tkinter as tk
        from tkinter import scrolledtext
        from tkinter import ttk as _ttk2

        import matplotlib
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti SC", "SimHei"]
        plt.rcParams["axes.unicode_minus"] = False

        top = tk.Toplevel(self.root)
        top.title(f"🦅 {stock_name}({stock_code}) 游资心法全解")
        top.geometry("1100x720"); top.configure(bg="white")

        # Banner
        bn = tk.Frame(top, bg="#1A237E"); bn.pack(fill=tk.X)
        pct_s = f"{pct_day:+.2f}%" if pct_day is not None else "-"
        tk.Label(bn, text=f"🦅 {stock_name}({stock_code})  现价 {price:.2f}  {pct_s}  "
                          f"🌊 情绪【{emo_stage}】  总分 {avg_score:.1f}  🏆 {best_sch}",
                 font=("", 12, "bold"), bg="#1A237E", fg="white").pack(padx=14, pady=10)

        # Notebook
        nb = _ttk2.Notebook(top); nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ===== Tab1: 📊 心法评分 (matplotlib K线 + 7游资卡片 + 右指标) =====
        tab1 = tk.Frame(nb, bg="#FAFAFA"); nb.add(tab1, text=" 📊 心法评分 ")

        # --- matplotlib K线图区 (左侧, 占大部分空间) ---
        fig = Figure(figsize=(7.5, 5.5), dpi=95, facecolor="#FAFAFA")
        ax1 = fig.add_subplot(3, 1, 1)   # K线主图
        ax2 = fig.add_subplot(3, 1, 2, sharex=ax1)  # 成交量
        ax3 = fig.add_subplot(3, 1, 3, sharex=ax1)  # MACD
        fig.subplots_adjust(left=0.07, right=0.98, top=0.92, bottom=0.08, hspace=0.05)

        # 准备数据
        import numpy as np
        n = len(cl)
        x_idx = np.arange(n)
        # 日期标签
        if dt_list:
            # 只显示首尾 + 每隔20天
            show_idx = [0] + list(range(20, n, max(20, n//8))) + [n-1]
            show_idx = sorted(set(show_idx))
            date_labels = [dt_list[i][4:6]+"/"+dt_list[i][6:8] for i in show_idx]
        else:
            show_idx = []; date_labels = []
        # MA 序列
        def _ma_series(arr, w):
            if len(arr) < w: return [np.nan]*len(arr)
            return [np.mean(arr[max(0,i-w+1):i+1]) if i+1>=w else np.nan for i in range(len(arr))]
        ma5_s  = _ma_series(cl, 5)
        ma10_s = _ma_series(cl, 10)
        ma20_s = _ma_series(cl, 20)
        # MACD: DIF=EMA12-EMA26, DEA=EMA9(DIF), MACD=2*(DIF-DEA)
        def _ema(arr, period):
            result = []; k = 2/(period+1); ema = arr[0]
            for v in arr: ema = v*k + ema*(1-k); result.append(ema)
            return result
        dif = _ema(cl, 12); dif = [d - e for d, e in zip(dif, _ema(cl, 26))]
        dea = _ema(dif, 9); macd_h = [2*(d-e) for d, e in zip(dif, dea)]

        # 画K线 (简化版 OHLC bar, 红涨绿跌)
        for i in range(n):
            up = cl[i] >= op[i]
            c = "#C62828" if up else "#2E7D32"
            # 影线 (high-low vertical)
            ax1.plot([i, i], [lo[i], hi[i]], color=c, linewidth=0.7)
            # 实体 (open-close)
            body_lo = min(op[i], cl[i]); body_hi = max(op[i], cl[i])
            ax1.bar(i, body_hi - body_lo, bottom=body_lo, width=0.6, color=c, edgecolor=c, linewidth=0.7)
        ax1.plot(x_idx, ma5_s,  color="#FF6F00", linewidth=0.8, label="MA5", zorder=5)
        ax1.plot(x_idx, ma10_s, color="#1565C0", linewidth=0.8, label="MA10", zorder=5)
        ax1.plot(x_idx, ma20_s, color="#6A1B9A", linewidth=0.8, label="MA20", zorder=5)
        # 筹码成本转折点 (用 MA20 代替, 找下降→上升 + 上升→下降 的拐点)
        ma20_arr = np.array(ma20_s)
        # 一阶差分: diff[i] = ma20[i+1] - ma20[i]
        diff = np.diff(ma20_arr)
        # 有效索引 (diff[i] 对应 ma20_arr[i+1] 位置)
        bottom_turns = []  # 下降→上升 (diff 从负变正)
        top_turns = []     # 上升→下降 (diff 从正变负)
        min_gap = 5        # 相邻转折点至少间隔5天, 避免密集标记
        for i in range(1, len(diff)):
            if np.isnan(diff[i]) or np.isnan(diff[i-1]):
                continue
            if diff[i-1] < 0 and diff[i] >= 0:  # 斜率由负转正 → 底部
                pos = i + 1  # 对应 ma20_arr 的索引
                ma_val = ma20_arr[pos]
                # 去重: 与上一个已记录的底部间隔足够远
                if not bottom_turns or (pos - bottom_turns[-1][0]) >= min_gap:
                    bottom_turns.append((pos, float(ma_val)))
            elif diff[i-1] > 0 and diff[i] <= 0:  # 斜率由正转负 → 顶部
                pos = i + 1
                ma_val = ma20_arr[pos]
                if not top_turns or (pos - top_turns[-1][0]) >= min_gap:
                    top_turns.append((pos, float(ma_val)))
        # 在K线上画转折点标记
        # 底部转折点: 黄色三角形向上 (放在K线下方)
        for pos, ma_val in bottom_turns:
            if pos < len(lo):
                y_pos = min(cl[pos], lo[pos]) * 0.995  # 略低于当日低点
                ax1.annotate("", xy=(pos, y_pos), xytext=(pos, y_pos * 0.988),
                             arrowprops={"arrowstyle": "->", "color": "#FFD600", "lw": 1.8})
                ax1.scatter([pos], [y_pos], marker="^", color="#FFD600", s=35, zorder=10,
                            edgecolors="#F57F17", linewidths=0.8, label="_底部转折")
        # 顶部转折点: 红色三角形向下 (放在K线上方)
        for pos, ma_val in top_turns:
            if pos < len(hi):
                y_pos = max(cl[pos], hi[pos]) * 1.005  # 略高于当日高点
                ax1.annotate("", xy=(pos, y_pos), xytext=(pos, y_pos * 1.012),
                             arrowprops={"arrowstyle": "->", "color": "#FF1744", "lw": 1.8})
                ax1.scatter([pos], [y_pos], marker="v", color="#FF1744", s=35, zorder=10,
                            edgecolors="#B71C1C", linewidths=0.8, label="_顶部转折")
        # 只添加一次图例条目
        if bottom_turns or top_turns:
            from matplotlib.lines import Line2D
            _legend_extra = []
            _legend_labels = []
            if bottom_turns:
                _legend_extra.append(Line2D([0], [0], marker="^", color="w",
                                            markerfacecolor="#FFD600", markeredgecolor="#F57F17", markersize=8))
                _legend_labels.append("成本底转折")
            if top_turns:
                _legend_extra.append(Line2D([0], [0], marker="v", color="w",
                                            markerfacecolor="#FF1744", markeredgecolor="#B71C1C", markersize=8))
                _legend_labels.append("成本顶转折")
            ax1.legend(list(ax1.get_legend_handles_labels()[0]) + _legend_extra,
                       list(ax1.get_legend_handles_labels()[1]) + _legend_labels,
                       fontsize=7, loc="upper left", framealpha=0.7, ncol=3)
        ax1.set_ylabel("价格", fontsize=8, color="#555")
        ax1.tick_params(colors="#555", labelsize=7)
        if not (bottom_turns or top_turns):
            ax1.legend(fontsize=7, loc="upper left", framealpha=0.7, ncol=3)
        ax1.grid(True, alpha=0.2)
        ax1.set_facecolor("#FAFAFA")

        # 成交量
        for i in range(n):
            up = cl[i] >= op[i]
            c = "#C62828" if up else "#2E7D32"
            ax2.bar(i, vo[i]/1e4, width=0.6, color=c, alpha=0.8)
        ax2.set_ylabel("量(万)", fontsize=8, color="#555")
        ax2.tick_params(colors="#555", labelsize=7, labelbottom=False)
        ax2.grid(True, alpha=0.2)
        ax2.set_facecolor("#FAFAFA")

        # MACD
        macd_colors = ["#C62828" if v >= 0 else "#2E7D32" for v in macd_h]
        ax3.bar(x_idx, macd_h, color=macd_colors, width=0.7, alpha=0.8)
        ax3.plot(x_idx, dif, color="#FF6F00", linewidth=0.7, label="DIF")
        ax3.plot(x_idx, dea, color="#1565C0", linewidth=0.7, label="DEA")
        ax3.axhline(0, color="#888", linewidth=0.5)
        ax3.set_ylabel("MACD", fontsize=8, color="#555")
        ax3.tick_params(colors="#555", labelsize=7)
        if date_labels:
            ax3.set_xticks(show_idx); ax3.set_xticklabels(date_labels, fontsize=7)
        ax3.legend(fontsize=7, loc="upper left", framealpha=0.7)
        ax3.grid(True, alpha=0.2)
        ax3.set_facecolor("#FAFAFA")

        canvas = FigureCanvasTkAgg(fig, master=tab1)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4,0), pady=4)

        # --- 右侧: 指标面板 + 7 游资卡片 (300px) ---
        right1 = tk.Frame(tab1, bg="#FAFAFA", width=300); right1.pack(side=tk.RIGHT, fill=tk.Y, padx=4, pady=4)
        right1.pack_propagate(False)
        tk.Label(right1, text="📈 关键指标", font=("", 10, "bold"),
                 bg="#FAFAFA", fg="#1A237E").pack(anchor="w")
        metrics_text = (
            f"现价: {price:.2f}\n"
            f"涨跌: {pct_day:+.2f}%\n"
            f"MA5:  {m5:.2f}\n"
            f"MA10: {m10:.2f}\n"
            f"MA20: {m20:.2f}\n"
            f"MA60: {m60:.2f}\n"
            f"VR量比: {vr:.2f}\n"
            f"BIAS20: {dma:+.2f}%\n"
            f"距60日高: {pct3:.1f}%"
        )
        if tr: metrics_text += f"\n换手率: {tr:.2f}%"
        tk.Label(right1, text=metrics_text, font=("", 9), bg="white", fg="#333",
                 justify=tk.LEFT, padx=8, pady=6,
                 highlightbackground="#DDD", highlightthickness=1).pack(fill=tk.X, pady=4)

        # 综合判定
        judge_lines = []
        judge_lines.append(f"📊 总分: {avg_score:.1f}/100 ({'强' if avg_score>=65 else '中' if avg_score>=45 else '弱'})")
        judge_lines.append(f"🎯 最强流派: {best_sch}")
        judge_lines.append(f"🌊 情绪: {emo_stage}")
        if avg_score >= 65: judge_lines.append("✅ 多游资看好, 可以考虑买入")
        elif avg_score >= 50: judge_lines.append("⚠️ 部分游资看好, 观察回踩再入")
        elif avg_score >= 40: judge_lines.append("🔶 情绪分化, 轻仓试探")
        else: judge_lines.append("❌ 多数游资不看好, 观望为宜")
        tk.Label(right1, text="🏆 综合判定", font=("", 10, "bold"),
                 bg="#FAFAFA", fg="#C62828").pack(anchor="w", pady=(6, 2))
        tk.Label(right1, text="\n".join(judge_lines), font=("", 9), bg="#E3F2FD", fg="#1565C0",
                 justify=tk.LEFT, padx=8, pady=6, anchor="w",
                 highlightbackground="#90CAF9", highlightthickness=1).pack(fill=tk.X, pady=2)

        # 7 游资评分卡片 (垂直堆叠)
        tk.Label(right1, text="🦅 7位游资评分", font=("", 10, "bold"),
                 bg="#FAFAFA", fg="#1A237E").pack(anchor="w", pady=(6, 2))
        hm_names = list(scores.keys())
        def _score_color(s):
            return "#C62828" if s >= 65 else ("#F57F17" if s >= 45 else "#2E7D32")
        for nm in hm_names:
            sc = scores[nm]
            col_fg = _score_color(sc)
            row = tk.Frame(right1, bg="white", highlightbackground="#EEE",
                           highlightthickness=1, padx=6, pady=3)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=f"{nm}", font=("", 8, "bold"), bg="white", fg="#333").pack(side=tk.LEFT)
            # 小进度条
            bar = tk.Canvas(row, height=10, bg="#EEEEEE", highlightthickness=0, width=100)
            bar.pack(side=tk.RIGHT, padx=4)
            bar.create_rectangle(0, 0, sc, 10, fill=col_fg, outline="")
            tk.Label(row, text=f"{sc:.0f}", font=("", 8, "bold"), bg="white", fg=col_fg).pack(side=tk.RIGHT)

        # ===== Tab2: 📖 心法语录 (精简版) =====
        tab2 = tk.Frame(nb, bg="#FAFAFA"); nb.add(tab2, text=" 📖 心法语录 ")
        txt2 = scrolledtext.ScrolledText(tab2, font=("", 10), bg="#FAFAFA", wrap=tk.WORD)
        txt2.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        txt2.tag_config("hm_name", foreground="#C62828", font=("", 12, "bold"))
        txt2.tag_config("hm_sch", foreground="#1565C0", font=("", 9, "italic"))
        for nm in hm_names:
            sc = scores[nm]
            _, phi = dims_map[nm]
            sch = tra_to_school.get(nm, "")
            txt2.insert(tk.END, f"\n{'─'*40}\n")
            txt2.insert(tk.END, f"🎯 {nm}  ", "hm_name")
            txt2.insert(tk.END, f"[{sch}]  评分: {sc:.0f}/100\n", "hm_sch")
            txt2.insert(tk.END, f"💡 {phi}\n")

        # ===== Tab3: 🗺️ 流派诊断 (量化判断) =====
        tab3 = tk.Frame(nb, bg="#FAFAFA"); nb.add(tab3, text=" 🗺️ 流派诊断 ")
        txt3 = scrolledtext.ScrolledText(tab3, font=("", 10), bg="#FAFAFA", wrap=tk.WORD)
        txt3.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        txt3.tag_config("sch_name", foreground="#1A237E", font=("", 11, "bold"))
        txt3.tag_config("sch_hot", foreground="#C62828", font=("", 11, "bold"))
        txt3.tag_config("phi", foreground="#1565C0", font=("", 9, "italic"))

        SCHOOLS_INFO = [
            ("情绪周期流", "情绪阶段(冰点→高潮)+仓位管理", ["炒股养家"]),
            ("龙头战法流", "二板定龙+弱转强+分歧一致", ["赵老哥", "瑞鹤仙"]),
            ("低吸反包流", "强势股缩量回踩+资金回流", ["作手新一"]),
            ("趋势波段流", "主升持有+下降通道空仓", ["方新侠", "章盟主", "葛卫东"]),
        ]
        txt3.insert(tk.END, f"═════════ 🗺️ {stock_name} 流派匹配诊断 ═════════\n\n")
        for sch_name, sch_core, hms in SCHOOLS_INFO:
            txt3.insert(tk.END, f"【{sch_name}】\n", "sch_name")
            txt3.insert(tk.END, f"  核心: {sch_core}\n")
            sc_list = [scores[h] for h in hms if h in scores]
            avg_s = sum(sc_list)/len(sc_list) if sc_list else 0
            # 匹配度进度条 (文字版)
            match_bar = "█" * int(avg_s/5) + "░" * (20 - int(avg_s/5))
            col_tag = "sch_hot" if avg_s >= 60 else ""
            txt3.insert(tk.END, f"  匹配度: [{match_bar}] {avg_s:.0f}分\n", col_tag)
            for h in hms:
                if h in scores:
                    sc = scores[h]
                    _, phi = dims_map[h]
                    dims, _ = dims_map[h]
                    top_dims = " | ".join(f"{ic}{label}" for ic, label, _v in dims[:4])
                    txt3.insert(tk.END, f"    🎯 {h}: {sc:.0f}分 → {top_dims}\n")
                    txt3.insert(tk.END, f"      💡 {phi}\n", "phi")
            txt3.insert(tk.END, "\n")

        # ===== Tab4: ⚡ 铁律诊断 (通用8条铁律) =====
        tab4 = tk.Frame(nb, bg="#FAFAFA"); nb.add(tab4, text=" ⚡ 铁律诊断 ")
        txt4 = scrolledtext.ScrolledText(tab4, font=("", 10), bg="#FAFAFA", wrap=tk.WORD)
        txt4.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        txt4.tag_config("pass", foreground="#2E7D32", font=("", 10, "bold"))
        txt4.tag_config("fail", foreground="#C62828", font=("", 10, "bold"))

        # 公共量化字典
        ma_ok = m5 > m10 > m20
        m60_ok = m20 > m60
        q = {
            "ma_ok": ma_ok, "m60_ok": m60_ok, "vr": vr, "dma": dma,
            "pct3": pct3, "price": price, "tr": tr, "emo": emo_stage,
            "cl": cl, "pct_day": pct_day,
        }

        RULES = [
            ("⚔️ 只做最强/龙头", "均线多头(MA5>MA10>MA20) + 接近前高",
             lambda q: q["ma_ok"] and q["pct3"] > -15,
             lambda q: f"MA排列={'✅多头' if q['ma_ok'] else '❌非多头'}, 距60日高={q['pct3']:.1f}%"),
            ("⚔️ 买分歧卖一致", "情绪退潮不追高, 发酵/高潮期买分歧",
             lambda q: q["emo"] not in ("高潮", "退潮") or not q["ma_ok"],
             lambda q: f"情绪={q['emo']}, 均线={'多头' if q['ma_ok'] else '非多头'}"),
            ("⚔️ 严格止损", "MA20是生命线, 跌破要警觉",
             lambda q: q["dma"] > -5,
             lambda q: f"BIAS20={q['dma']:+.2f}% ({'安全区' if q['dma']>-5 else '跌破风险'})"),
            ("⚔️ 情绪周期", "冰点/退潮期空仓, 启动/发酵期积极",
             lambda q: q["emo"] not in ("冰点", "退潮"),
             lambda q: f"情绪阶段={q['emo']}"),
            ("🛡️ 量能配合", "VR 0.8~3.0 之间为佳, 天量要警惕",
             lambda q: 0.6 <= q["vr"] <= 4.0,
             lambda q: f"VR={q['vr']:.2f} ({'活跃' if 1<=q['vr']<=2.5 else '异常' if q['vr']>3 else '偏低'})"),
            ("🛡️ 位置合理", "不追高(BIAS20<10%), 不抄底(距高>20%要小心)",
             lambda q: q["dma"] < 10 and q["pct3"] > -30,
             lambda q: f"BIAS20={q['dma']:+.2f}%, 距60日高={q['pct3']:.1f}%"),
            ("🛡️ 大周期趋势", "MA20 > MA60 = 上升趋势, 反之下降",
             lambda q: q["m60_ok"],
             lambda q: f"MA20>MA60={'✅上升' if q['m60_ok'] else '❌下降'}"),
            ("🛡️ 情绪共振", "情绪+技术双确认: 好情绪+好技术 = 加分",
             lambda q: (q["emo"] in ("发酵", "高潮") and q["ma_ok"]) or q["emo"] in ("冰点", "退潮"),
             lambda q: f"情绪={q['emo']}, 技术={'多头' if q['ma_ok'] else '震荡'}"),
        ]

        txt4.insert(tk.END, f"═════════ ⚡ {stock_name} 8 条铁律诊断 ═════════\n\n")
        pass_cnt = 0
        for title, desc, check_fn, detail_fn in RULES:
            ok = check_fn(q); pass_cnt += 1 if ok else 0
            tag = "pass" if ok else "fail"
            icon = "✅" if ok else "❌"
            txt4.insert(tk.END, f"{icon} {title}\n", tag)
            txt4.insert(tk.END, f"   判定: {detail_fn(q)}\n")
            txt4.insert(tk.END, f"   要点: {desc}\n\n")
        txt4.insert(tk.END, f"═══ 综合: {pass_cnt}/8 条通过 {'🟢 状态良好' if pass_cnt >= 6 else '🟡 部分满足' if pass_cnt >= 4 else '🔴 需谨慎'} ═══\n")

        # 免责
        tk.Label(tab4, text="⚠️ 本文仅为历史交易理念复盘科普，不构成投资建议。股市有风险，入市需谨慎。",
                 bg="#FAFAFA", fg="#999", font=("", 8, "italic")).pack(anchor="w", padx=10, pady=8)

    def _lookup_sector_leaders(cls, sector_name):
        """从静态字典里模糊匹配板块龙头(支持部分匹配)"""
        if not sector_name:
            return []
        # 精确匹配
        if sector_name in cls._SECTOR_LEADERS:
            return cls._SECTOR_LEADERS[sector_name]
        # 模糊匹配(key 包含或被包含)
        for k, v in cls._SECTOR_LEADERS.items():
            if sector_name in k or k in sector_name:
                return v
        return []


__all__ = ["HotMixin"]
