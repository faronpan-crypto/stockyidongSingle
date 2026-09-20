"""Auto-extracted DatabaseMixin"""
import os, sys, sqlite3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext
from data.db import save_stock_to_db, save_article_to_db, save_news_info_to_db, get_stock_logic_from_db, delete_stock_logic_from_db, update_stock_logic_in_db
from utils.config import *  # 路径/配置/Token
from data.snapshot import *  # get_news_stocks_* 函数
from logic.crawlers import *  # TaogubaCrawler
from logic.spot import *
from logic.stock_names import *  # get_stock_name_by_code 等

from datetime import datetime, timedelta
import re
import os
import sys
import time
import threading
import traceback
from urllib.parse import urljoin
import sqlite3

class DatabaseMixin:
    """DatabaseMixin"""

    def show_unified_db_display(self, default_tab="stock", on_stock_double_click=None):
        """统一的数据库管理窗口,包含股票数据表和资讯数据表两个标签页
        Args:
            default_tab: 默认显示的标签页,"stock"表示股票数据表,"news"表示资讯数据表
            on_stock_double_click: 双击股票时的回调函数,接收股票名称作为参数
        """
        try:
            db_window = self._toplevel(self.root)
            db_window.title("数据库管理")
            db_window.geometry("1400x900")
            db_window.resizable(True, True)
            # 存储窗口状态
            db_window._is_minimized = False
            db_window._original_geometry = "1400x900"
            # 存储回调函数(如果提供)
            if on_stock_double_click:
                db_window._on_stock_double_click = on_stock_double_click
            # 创建主框架
            main_frame = ttk.Frame(db_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            # 创建主标签页,用于切换股票数据表和资讯数据表
            main_notebook = ttk.Notebook(main_frame)
            main_notebook.pack(fill=tk.BOTH, expand=True)
            # ==================== 股票数据表标签页 ====================
            stock_tab = ttk.Frame(main_notebook)
            main_notebook.add(stock_tab, text="股票数据表")
            # 将原来的show_db_display内容移到这里(简化版)
            # 按钮区域(在查询条件上方)
            button_frame = ttk.Frame(stock_tab)
            button_frame.pack(fill=tk.X, pady=(0, 10))
            ttk.Button(button_frame, text="持仓计算", command=self._open_holding_calculator, width=12).pack(side=tk.LEFT, padx=(0, 5))
            # 均线仓位检测按钮将在stock_tree创建后添加到这里
            # 查询条件框架
            query_frame = ttk.LabelFrame(stock_tab, text="查询条件", padding=10)
            query_frame.pack(fill=tk.X, pady=(0, 10))
            date_frame = ttk.Frame(query_frame)
            date_frame.pack(fill=tk.X, pady=(0, 5))
            date_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(date_frame, text="起始日期:").pack(side=tk.LEFT, padx=5)
            start_date_var = tk.StringVar()
            start_date_entry = ttk.Entry(date_frame, textvariable=start_date_var, width=12)
            start_date_entry.pack(side=tk.LEFT, padx=5)
            start_date_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
            ttk.Label(date_frame, text="结束日期:").pack(side=tk.LEFT, padx=5)
            end_date_var = tk.StringVar()
            end_date_entry = ttk.Entry(date_frame, textvariable=end_date_var, width=12)
            end_date_entry.pack(side=tk.LEFT, padx=5)
            end_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
            ttk.Label(date_frame, text="股票名称:").pack(side=tk.LEFT, padx=5)
            stock_name_var = tk.StringVar()
            stock_name_entry = ttk.Entry(date_frame, textvariable=stock_name_var, width=20)
            stock_name_entry.pack(side=tk.LEFT, padx=5)
            # 添加逻辑内容查询输入框
            ttk.Label(date_frame, text="逻辑内容:").pack(side=tk.LEFT, padx=5)
            logic_content_var = tk.StringVar()
            logic_content_entry = ttk.Entry(date_frame, textvariable=logic_content_var, width=30)
            logic_content_entry.pack(side=tk.LEFT, padx=5)
            # 数据表格和逻辑详情(左右布局)
            content_frame = ttk.Frame(stock_tab)
            content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            # 左侧:数据表格(使用Notebook包含多个标签页)
            left_content = ttk.Frame(content_frame)
            left_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
            # 左侧:股票数据列表(不再使用Notebook,直接显示表格)
            table_label = ttk.Label(left_content, text="股票数据列表", font=("TkDefaultFont", 12, "bold"))
            table_label.pack(anchor=tk.W, pady=(0, 5))
            table_frame = ttk.Frame(left_content)
            table_frame.pack(fill=tk.BOTH, expand=True)
            columns = ("ID", "股票名称", "逻辑预览", "日期", "来源", "创建时间")
            stock_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=25)
            # 排序状态:记录每列的排序方向(None=未排序, True=升序, False=降序)
            sort_directions = {col: None for col in columns}
            def sort_treeview(col, reverse=False):
                """对Treeview进行排序"""
                # 获取所有数据
                items = [(stock_tree.set(item, col), item) for item in stock_tree.get_children('')]
                # 尝试转换为数字进行排序
                try:
                    items.sort(key=lambda t: float(t[0]) if t[0] else 0, reverse=reverse)
                except (ValueError, TypeError):
                    # 如果无法转换为数字,则按字符串排序
                    items.sort(key=lambda t: str(t[0]).lower(), reverse=reverse)
                # 重新排列
                for index, (val, item) in enumerate(items):
                    stock_tree.move(item, '', index)
                # 更新列标题显示排序方向
                for c in columns:
                    if c == col:
                        sort_directions[c] = reverse
                        arrow = " ↓" if reverse else " ↑"
                        stock_tree.heading(c, text=c + arrow, command=lambda c=c: sort_treeview(c, not sort_directions[c]))
                    else:
                        sort_directions[c] = None
                        stock_tree.heading(c, text=c, command=lambda c=c: sort_treeview(c, False))
            for col in columns:
                stock_tree.heading(col, text=col, command=lambda c=col: sort_treeview(c, False))
                if col == "ID":
                    stock_tree.column(col, width=50, anchor=tk.CENTER)
                elif col == "股票名称":
                    stock_tree.column(col, width=120, anchor=tk.CENTER)
                elif col == "逻辑预览":
                    stock_tree.column(col, width=250)
                elif col == "日期" or col == "来源":
                    stock_tree.column(col, width=100, anchor=tk.CENTER)
                elif col == "创建时间":
                    stock_tree.column(col, width=150, anchor=tk.CENTER)
            stock_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=stock_tree.yview)
            stock_tree.configure(yscrollcommand=stock_scrollbar.set)
            stock_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            stock_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            # 均线仓位检测函数(必须在stock_tree创建后定义)
            def open_ma_position_detection():
                """打开均线仓位检测弹出窗口:对选中的股票逐个进行检测"""
                try:
                    selections = stock_tree.selection()
                    if not selections:
                        messagebox.showwarning("提示", "请先选择要检测的股票记录(可多选)", parent=db_window)
                        return
                    # 获取选中的股票名称列表
                    selected_stocks = []
                    for item_id in selections:
                        item = stock_tree.item(item_id)
                        values = item['values']
                        if len(values) >= 2:
                            stock_name = values[1]  # 股票名称在第二列
                            # 确保stock_name是字符串类型
                            if stock_name is not None:
                                stock_name = str(stock_name).strip()
                                if stock_name:
                                    selected_stocks.append(stock_name)
                    if not selected_stocks:
                        messagebox.showwarning("提示", "没有选中有效的股票", parent=db_window)
                        return
                    # 去重
                    selected_stocks = list(dict.fromkeys(selected_stocks))
                    # 创建弹出窗口
                    detection_window = self._toplevel(db_window)
                    detection_window.title(f"均线仓位检测 - {len(selected_stocks)}只股票")
                    detection_window.geometry("1200x800")
                    # 工具栏
                    toolbar_frame = ttk.Frame(detection_window)
                    toolbar_frame.pack(fill=tk.X, padx=5, pady=5)
                    # 保存按钮
                    def save_as_text():
                        """保存为文本文件"""
                        try:
                            content = result_text.get("1.0", tk.END)
                            if not content.strip():
                                messagebox.showwarning("提示", "没有内容可保存", parent=detection_window)
                                return
                            filename = filedialog.asksaveasfilename(
                                defaultextension=".txt",
                                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                                initialfile=f"均线仓位检测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                            )
                            if filename:
                                with open(filename, 'w', encoding='utf-8') as f:
                                    f.write(content)
                                messagebox.showinfo("成功", f"已保存到: {filename}", parent=detection_window)
                        except Exception as e:
                            messagebox.showerror("错误", f"保存失败: {e!s}", parent=detection_window)
                    def save_as_image():
                        """保存为图片文件"""
                        try:
                            content = result_text.get("1.0", tk.END)
                            if not content.strip():
                                messagebox.showwarning("提示", "没有内容可保存", parent=detection_window)
                                return
                            filename = filedialog.asksaveasfilename(
                                defaultextension=".png",
                                filetypes=[("图片文件", "*.png"), ("所有文件", "*.*")],
                                initialfile=f"均线仓位检测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                            )
                            if filename:
                                # 使用PIL创建图片
                                import textwrap

                                from PIL import Image, ImageDraw, ImageFont
                                # 尝试加载中文字体
                                try:
                                    font_normal = ImageFont.truetype("simhei.ttf", 16)
                                    font_large = ImageFont.truetype("simhei.ttf", 18)  # 加大2号
                                    font_bold = ImageFont.truetype("simhei.ttf", 18)
                                except:
                                    try:
                                        font_normal = ImageFont.truetype("msyh.ttc", 16)
                                        font_large = ImageFont.truetype("msyh.ttc", 18)
                                        font_bold = ImageFont.truetype("msyh.ttc", 18)
                                    except:
                                        font_normal = ImageFont.load_default()
                                        font_large = ImageFont.load_default()
                                        font_bold = ImageFont.load_default()
                                # 解析内容,识别需要特殊样式的部分
                                lines = content.split('\n')
                                max_width = 1000
                                # 先分析哪些股票是均线全部通过的
                                ma_all_pass_stocks = set()
                                i = 0
                                while i < len(lines):
                                    line = lines[i]
                                    if "【均线仓位检测详情】" in line:
                                        # 查找该股票的信息
                                        stock_name = None
                                        ma_all_pass = False
                                        # 查找股票名称和代码
                                        j = i + 1
                                        while j < len(lines) and j < i + 10:
                                            if "股票名称:" in lines[j]:
                                                stock_name = lines[j].split("股票名称:")[1].strip()
                                            if "股票代码:" in lines[j]:
                                                lines[j].split("股票代码:")[1].strip()
                                            if "检测结果: 满足开新仓条件" in lines[j]:
                                                # 检查站上均线是否包含1日、5日、10日、20日
                                                k = j + 1
                                                while k < len(lines) and k < j + 5:
                                                    if "站上均线:" in lines[k]:
                                                        ma_line = lines[k]
                                                        if "1日" in ma_line and "5日" in ma_line and "10日" in ma_line and "20日" in ma_line:
                                                            ma_all_pass = True
                                                        break
                                                    k += 1
                                                break
                                            j += 1
                                        if stock_name and ma_all_pass:
                                            ma_all_pass_stocks.add(stock_name)
                                    i += 1
                                # 包装文本并标记样式
                                wrapped_lines = []
                                line_styles = []
                                current_in_ma_all_pass_section = False
                                current_stock_name = None
                                for i, line in enumerate(lines):
                                    # 检查是否进入均线全部通过的股票区域
                                    if "【均线仓位检测详情】" in line:
                                        # 查找股票名称
                                        if i + 1 < len(lines):
                                            next_line = lines[i + 1]
                                            if "股票名称:" in next_line:
                                                current_stock_name = next_line.split("股票名称:")[1].strip()
                                                current_in_ma_all_pass_section = current_stock_name in ma_all_pass_stocks
                                            else:
                                                current_in_ma_all_pass_section = False
                                        else:
                                            current_in_ma_all_pass_section = False
                                    # 检查是否离开当前股票区域(遇到下一个股票区域或分隔线)
                                    if line.strip() == "="*80 and current_stock_name:
                                        # 检查下一行是否是新的股票区域
                                        if i + 1 < len(lines):
                                            next_line = lines[i + 1]
                                            if "【均线仓位检测详情】" in next_line:
                                                current_in_ma_all_pass_section = False
                                                current_stock_name = None
                                    elif line.strip() == "" and current_stock_name:
                                        # 空行后检查是否是新的股票区域
                                        if i + 1 < len(lines):
                                            next_line = lines[i + 1]
                                            if "【均线仓位检测详情】" in next_line:
                                                current_in_ma_all_pass_section = False
                                                current_stock_name = None
                                    # 包装文本
                                    wrapped = textwrap.wrap(line, width=80)
                                    for w in wrapped:
                                        wrapped_lines.append(w)
                                        is_stock_name_line = current_stock_name and current_stock_name in w and "股票名称:" in w
                                        is_title = "【" in w and "】" in w
                                        line_styles.append({
                                            'is_ma_all_pass': current_in_ma_all_pass_section,
                                            'is_stock_name': is_stock_name_line,
                                            'is_title': is_title
                                        })
                                line_height = 25
                                img_height = len(wrapped_lines) * line_height + 100
                                img = Image.new('RGB', (max_width, img_height), 'white')
                                draw = ImageDraw.Draw(img)
                                # 绘制标题
                                draw.text((20, 20), f"均线仓位检测报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                         fill='black', font=font_bold)
                                # 绘制内容
                                y = 60
                                for i, (line, style) in enumerate(zip(wrapped_lines, line_styles)):
                                    # 应用样式
                                    if style['is_ma_all_pass'] and style['is_stock_name']:
                                        # 股票名称:红色,加大字体,黄色背景
                                        draw.rectangle([10, y-2, max_width-10, y+line_height+2], fill='yellow')
                                        draw.text((20, y), line, fill='red', font=font_large)
                                    elif style['is_ma_all_pass'] and not style['is_title']:
                                        # 其他内容:黄色背景,加大字体
                                        draw.rectangle([10, y-2, max_width-10, y+line_height+2], fill='yellow')
                                        draw.text((20, y), line, fill='black', font=font_large)
                                    elif style['is_title']:
                                        # 标题行:加粗
                                        draw.text((20, y), line, fill='black', font=font_bold)
                                    else:
                                        # 普通行
                                        draw.text((20, y), line, fill='black', font=font_normal)
                                    y += line_height
                                img.save(filename)
                                messagebox.showinfo("成功", f"已保存到: {filename}", parent=detection_window)
                        except Exception as e:
                            messagebox.showerror("错误", f"保存失败: {e!s}", parent=detection_window)
                            import traceback
                            traceback.print_exc()
                    def save_as_news():
                        """保存为资讯"""
                        try:
                            content = result_text.get("1.0", tk.END)
                            if not content.strip():
                                messagebox.showwarning("提示", "没有内容可保存", parent=detection_window)
                                return
                            tab_name = f"均线仓位检测_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                            # 保存到数据库
                            if save_news_info_to_db(tab_name, content):
                                # 创建标签页
                                try:
                                    tab_id = self.create_text_tab(tab_name)
                                    text_widget = self.text_widgets[tab_id]['widget']
                                    if text_widget:
                                        text_widget.insert("1.0", content)
                                except:
                                    pass
                                messagebox.showinfo("成功", f"已保存为资讯: {tab_name}", parent=detection_window)
                            else:
                                messagebox.showerror("错误", "保存到数据库失败", parent=detection_window)
                        except Exception as e:
                            messagebox.showerror("错误", f"保存失败: {e!s}", parent=detection_window)
                    ttk.Button(toolbar_frame, text="保存为文本", command=save_as_text, width=12).pack(side=tk.LEFT, padx=5)
                    ttk.Button(toolbar_frame, text="保存为图片", command=save_as_image, width=12).pack(side=tk.LEFT, padx=5)
                    ttk.Button(toolbar_frame, text="保存为资讯", command=save_as_news, width=12).pack(side=tk.LEFT, padx=5)
                    # 结果显示区域
                    result_frame = ttk.Frame(detection_window)
                    result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                    result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD,
                                                            font=("TkDefaultFont", 12), height=40)
                    result_text.pack(fill=tk.BOTH, expand=True)
                    # 配置文本标签(用于颜色和字体)
                    result_text.tag_configure("ma_all_pass_name", foreground="red", font=("TkDefaultFont", 12, "bold"))
                    result_text.tag_configure("ma_all_pass_text", background="yellow", font=("TkDefaultFont", 12))
                    result_text.tag_configure("title", font=("TkDefaultFont", 12, "bold"))
                    result_text.tag_configure("normal", font=("TkDefaultFont", 12))
                    result_text.tag_configure("ma15_diff_bg", background="lightblue", font=("TkDefaultFont", 12))  # 15日均线差值小于3%的浅蓝色背景
                    # 插入初始提示
                    result_text.insert("1.0", "【均线仓位检测报告】\n")
                    result_text.insert(tk.END, f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    result_text.insert(tk.END, f"待检测股票数量: {len(selected_stocks)}\n")
                    result_text.insert(tk.END, "="*80 + "\n\n")
                    result_text.config(state=tk.DISABLED)
                    # 逐个处理股票
                    def process_stocks_one_by_one():
                        """逐个处理股票:检测->计算->显示"""
                        current_index = [0]  # 使用列表以便在嵌套函数中修改
                        def process_next_stock():
                            """处理下一个股票"""
                            if current_index[0] >= len(selected_stocks):
                                # 所有股票处理完成
                                result_text.config(state=tk.NORMAL)
                                result_text.insert(tk.END, "\n" + "="*80 + "\n")
                                result_text.insert(tk.END, f"检测完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                result_text.insert(tk.END, f"共检测 {len(selected_stocks)} 只股票\n")
                                result_text.config(state=tk.DISABLED)
                                result_text.see(tk.END)
                                return
                            stock_name = selected_stocks[current_index[0]]
                            stock_code = get_stock_code_by_name(stock_name)
                            # 更新进度
                            result_text.config(state=tk.NORMAL)
                            result_text.insert(tk.END, f"\n正在检测 {current_index[0]+1}/{len(selected_stocks)}: {stock_name} ({stock_code or '无代码'})...\n")
                            result_text.see(tk.END)
                            result_text.config(state=tk.DISABLED)
                            detection_window.update()
                            # 执行检测和计算(在后台线程中)
                            def check_and_calculate():
                                try:
                                    if not stock_code:
                                        def show_error():
                                            result_text.config(state=tk.NORMAL)
                                            result_text.insert(tk.END, f"❌ {stock_name}: 无法获取股票代码\n\n")
                                            result_text.config(state=tk.DISABLED)
                                            result_text.see(tk.END)
                                            current_index[0] += 1
                                            detection_window.after(500, process_next_stock)
                                        detection_window.after(0, show_error)
                                        return
                                    # 1. 执行均线检测
                                    detection_result = self._three_dimensional_detection(stock_name, stock_code)
                                    # 2. 获取历史数据计算最低点和最高点差值百分比
                                    import akshare as ak
                                    hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                                    # 在主线程中更新UI
                                    def update_ui():
                                        result_text.config(state=tk.NORMAL)
                                        # 判断是否均线全部通过
                                        ma_all_pass = False
                                        if detection_result and detection_result.get('success'):
                                            technical_result = detection_result.get('technical', {})
                                            ma_status = technical_result.get('ma_status', {})
                                            ma_all_pass = all(ma_status.get(ma_key, False) for ma_key in ['ma1', 'ma5', 'ma10', 'ma20'])
                                        # 插入股票信息
                                        result_text.insert(tk.END, "\n" + "="*80 + "\n")
                                        # 股票名称(如果均线全部通过,使用特殊样式)
                                        if ma_all_pass:
                                            result_text.insert(tk.END, "【均线仓位检测详情】\n", "title")
                                            result_text.insert(tk.END, f"股票名称: {stock_name}\n", "ma_all_pass_name")
                                            result_text.insert(tk.END, f"股票代码: {stock_code}\n", "ma_all_pass_text")
                                        else:
                                            result_text.insert(tk.END, "【均线仓位检测详情】\n", "title")
                                            result_text.insert(tk.END, f"股票名称: {stock_name}\n", "normal")
                                            result_text.insert(tk.END, f"股票代码: {stock_code}\n", "normal")
                                        # 均线检测结果
                                        if detection_result and detection_result.get('success'):
                                            technical_result = detection_result.get('technical', {})
                                            ma_status = technical_result.get('ma_status', {})
                                            can_open = technical_result.get('can_open', False)
                                            ma_list = []
                                            if ma_status.get('ma1', False):
                                                ma_list.append("1日")
                                            if ma_status.get('ma5', False):
                                                ma_list.append("5日")
                                            if ma_status.get('ma10', False):
                                                ma_list.append("10日")
                                            if ma_status.get('ma20', False):
                                                ma_list.append("20日")
                                            if ma_all_pass:
                                                result_text.insert(tk.END, f"检测结果: {'满足开新仓条件' if can_open else '不满足开新仓条件'}\n", "ma_all_pass_text")
                                                result_text.insert(tk.END, f"站上均线: {', '.join(ma_list) if ma_list else '无'}\n", "ma_all_pass_text")
                                            else:
                                                result_text.insert(tk.END, f"检测结果: {'满足开新仓条件' if can_open else '不满足开新仓条件'}\n", "normal")
                                                result_text.insert(tk.END, f"站上均线: {', '.join(ma_list) if ma_list else '无'}\n", "normal")
                                            # 获取当前价格
                                            try:
                                                result = self._fetch_recent_daily_closes(stock_code, days=45, source="default", token=self.ts_token, return_volume=False)
                                                if isinstance(result, tuple) and len(result) >= 2:
                                                    dates, closes = result[:2]
                                                else:
                                                    _dates, closes = result, []
                                                if closes and len(closes) > 0:
                                                    current_price = float(closes[-1])
                                                    if ma_all_pass:
                                                        result_text.insert(tk.END, f"当前价格: {current_price:.2f}\n", "ma_all_pass_text")
                                                    else:
                                                        result_text.insert(tk.END, f"当前价格: {current_price:.2f}\n", "normal")
                                            except:
                                                pass
                                        else:
                                            if ma_all_pass:
                                                result_text.insert(tk.END, "均线检测失败\n", "ma_all_pass_text")
                                            else:
                                                result_text.insert(tk.END, "均线检测失败\n", "normal")
                                        # 仓位计算(凯利公式)
                                        if detection_result and detection_result.get('success'):
                                            position_result = detection_result.get('position', {})
                                            kelly_ratio = position_result.get('kelly_ratio', 0)
                                            kelly_percent = position_result.get('kelly_percent', 0)
                                            b = position_result.get('b', 0)
                                            p = position_result.get('p', 0)
                                            if ma_all_pass:
                                                result_text.insert(tk.END, "\n【仓位计算(凯利公式)】\n", "title")
                                                result_text.insert(tk.END, f"凯利比例: {kelly_ratio:.4f} ({kelly_percent:.2f}%)\n", "ma_all_pass_text")
                                                result_text.insert(tk.END, f"参数b: {b:.4f}\n", "ma_all_pass_text")
                                                result_text.insert(tk.END, f"参数p: {p:.4f}\n", "ma_all_pass_text")
                                            else:
                                                result_text.insert(tk.END, "\n【仓位计算(凯利公式)】\n", "title")
                                                result_text.insert(tk.END, f"凯利比例: {kelly_ratio:.4f} ({kelly_percent:.2f}%)\n", "normal")
                                                result_text.insert(tk.END, f"参数b: {b:.4f}\n", "normal")
                                                result_text.insert(tk.END, f"参数p: {p:.4f}\n", "normal")
                                        # 最低点和最高点差值百分比
                                        if not hist_data.empty and len(hist_data) >= 20:
                                            # 获取当前价格
                                            current_price = None
                                            try:
                                                spot_row = get_realtime_spot_row(stock_code, cache_duration=60)
                                                if spot_row is not None:
                                                    price = spot_row.get('最新价')
                                                    if price is not None:
                                                        current_price = float(price)
                                            except:
                                                pass
                                            if current_price is None:
                                                current_price = float(hist_data.iloc[-1]['收盘'])
                                            if ma_all_pass:
                                                result_text.insert(tk.END, "\n【最低点差值百分比】\n", "title")
                                            else:
                                                result_text.insert(tk.END, "\n【最低点差值百分比】\n", "title")
                                            # 5日最低点
                                            if len(hist_data) >= 5:
                                                recent_5days = hist_data.tail(5)
                                                min_low_5 = float(recent_5days['最低'].min())
                                                if min_low_5 > 0:
                                                    low_diff_5 = current_price - min_low_5
                                                    low_diff_pct_5 = (low_diff_5 / min_low_5) * 100
                                                    if ma_all_pass:
                                                        result_text.insert(tk.END, f"5日最低点: {min_low_5:.2f}, 差值: {low_diff_5:.2f}, 差值%: {low_diff_pct_5:.2f}%\n", "ma_all_pass_text")
                                                    else:
                                                        result_text.insert(tk.END, f"5日最低点: {min_low_5:.2f}, 差值: {low_diff_5:.2f}, 差值%: {low_diff_pct_5:.2f}%\n", "normal")
                                            # 10日最低点
                                            if len(hist_data) >= 10:
                                                recent_10days = hist_data.tail(10)
                                                min_low_10 = float(recent_10days['最低'].min())
                                                if min_low_10 > 0:
                                                    low_diff_10 = current_price - min_low_10
                                                    low_diff_pct_10 = (low_diff_10 / min_low_10) * 100
                                                    if ma_all_pass:
                                                        result_text.insert(tk.END, f"10日最低点: {min_low_10:.2f}, 差值: {low_diff_10:.2f}, 差值%: {low_diff_pct_10:.2f}%\n", "ma_all_pass_text")
                                                    else:
                                                        result_text.insert(tk.END, f"10日最低点: {min_low_10:.2f}, 差值: {low_diff_10:.2f}, 差值%: {low_diff_pct_10:.2f}%\n", "normal")
                                            # 20日最低点
                                            if len(hist_data) >= 20:
                                                recent_20days = hist_data.tail(20)
                                                min_low_20 = float(recent_20days['最低'].min())
                                                if min_low_20 > 0:
                                                    low_diff_20 = current_price - min_low_20
                                                    low_diff_pct_20 = (low_diff_20 / min_low_20) * 100
                                                    if ma_all_pass:
                                                        result_text.insert(tk.END, f"20日最低点: {min_low_20:.2f}, 差值: {low_diff_20:.2f}, 差值%: {low_diff_pct_20:.2f}%\n", "ma_all_pass_text")
                                                    else:
                                                        result_text.insert(tk.END, f"20日最低点: {min_low_20:.2f}, 差值: {low_diff_20:.2f}, 差值%: {low_diff_pct_20:.2f}%\n", "normal")
                                            if ma_all_pass:
                                                result_text.insert(tk.END, "\n【最高点差值百分比】\n", "title")
                                            else:
                                                result_text.insert(tk.END, "\n【最高点差值百分比】\n", "title")
                                            # 5日最高点
                                            if len(hist_data) >= 5:
                                                recent_5days = hist_data.tail(5)
                                                max_high_5 = float(recent_5days['最高'].max())
                                                if max_high_5 > 0:
                                                    high_diff_5 = current_price - max_high_5
                                                    high_diff_pct_5 = (high_diff_5 / max_high_5) * 100
                                                    if ma_all_pass:
                                                        result_text.insert(tk.END, f"5日最高点: {max_high_5:.2f}, 差值: {high_diff_5:.2f}, 差值%: {high_diff_pct_5:.2f}%\n", "ma_all_pass_text")
                                                    else:
                                                        result_text.insert(tk.END, f"5日最高点: {max_high_5:.2f}, 差值: {high_diff_5:.2f}, 差值%: {high_diff_pct_5:.2f}%\n", "normal")
                                            # 10日最高点
                                            if len(hist_data) >= 10:
                                                recent_10days = hist_data.tail(10)
                                                max_high_10 = float(recent_10days['最高'].max())
                                                if max_high_10 > 0:
                                                    high_diff_10 = current_price - max_high_10
                                                    high_diff_pct_10 = (high_diff_10 / max_high_10) * 100
                                                    if ma_all_pass:
                                                        result_text.insert(tk.END, f"10日最高点: {max_high_10:.2f}, 差值: {high_diff_10:.2f}, 差值%: {high_diff_pct_10:.2f}%\n", "ma_all_pass_text")
                                                    else:
                                                        result_text.insert(tk.END, f"10日最高点: {max_high_10:.2f}, 差值: {high_diff_10:.2f}, 差值%: {high_diff_pct_10:.2f}%\n", "normal")
                                            # 20日最高点
                                            if len(hist_data) >= 20:
                                                recent_20days = hist_data.tail(20)
                                                max_high_20 = float(recent_20days['最高'].max())
                                                if max_high_20 > 0:
                                                    high_diff_20 = current_price - max_high_20
                                                    high_diff_pct_20 = (high_diff_20 / max_high_20) * 100
                                                    if ma_all_pass:
                                                        result_text.insert(tk.END, f"20日最高点: {max_high_20:.2f}, 差值: {high_diff_20:.2f}, 差值%: {high_diff_pct_20:.2f}%\n", "ma_all_pass_text")
                                                    else:
                                                        result_text.insert(tk.END, f"20日最高点: {max_high_20:.2f}, 差值: {high_diff_20:.2f}, 差值%: {high_diff_pct_20:.2f}%\n", "normal")
                                        result_text.config(state=tk.DISABLED)
                                        result_text.see(tk.END)
                                        # 处理下一个股票(延迟1秒)
                                        current_index[0] += 1
                                        detection_window.after(1000, process_next_stock)
                                    detection_window.after(0, update_ui)
                                except Exception as e:
                                    def show_error(e=e):
                                        result_text.config(state=tk.NORMAL)
                                        result_text.insert(tk.END, f"❌ {stock_name}: 检测失败 - {e!s}\n\n")
                                        result_text.config(state=tk.DISABLED)
                                        result_text.see(tk.END)
                                        current_index[0] += 1
                                        detection_window.after(1000, process_next_stock)
                                    detection_window.after(0, show_error)
                                    import traceback
                                    traceback.print_exc()
                            # 在后台线程中执行检测
                            threading.Thread(target=check_and_calculate, daemon=True).start()
                        # 开始处理第一个股票
                        process_next_stock()
                    # 延迟执行,确保窗口已完全显示
                    detection_window.after(500, process_stocks_one_by_one)
                except Exception as e:
                    messagebox.showerror("错误", f"打开检测窗口失败: {e!s}", parent=db_window)
                    import traceback
                    traceback.print_exc()
            # 在button_frame中添加均线仓位检测按钮(函数已定义,现在可以绑定)
            # 注意:由于button_frame已经pack,我们需要确保它仍然可见
            ma_detection_btn = ttk.Button(button_frame, text="均线仓位检测", command=open_ma_position_detection, width=15)
            ma_detection_btn.pack(side=tk.LEFT, padx=(0, 5))
            # 右侧:逻辑详情
            right_content = ttk.Frame(content_frame)
            right_content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
            logic_label = ttk.Label(right_content, text="逻辑详情", font=("TkDefaultFont", 12, "bold"))
            logic_label.pack(anchor=tk.W, pady=(0, 5))
            logic_frame = ttk.LabelFrame(right_content, text="完整逻辑内容", padding=5)
            logic_frame.pack(fill=tk.BOTH, expand=True)
            logic_text = scrolledtext.ScrolledText(logic_frame, height=12, wrap=tk.WORD,
                                                   font=("TkDefaultFont", 12))
            logic_text.pack(fill=tk.BOTH, expand=True)
            # 双击逻辑详情弹出框
            def show_logic_popup(event=None):
                """双击逻辑详情弹出大窗口"""
                content = logic_text.get("1.0", tk.END).strip()
                if not content or content == "请选择股票记录以查看完整逻辑":
                    return
                popup = self._toplevel(db_window)
                popup.title("完整逻辑内容")
                popup.geometry("1000x700")
                popup.resizable(True, True)
                # 创建滚动文本框
                popup_frame = ttk.Frame(popup, padding=10)
                popup_frame.pack(fill=tk.BOTH, expand=True)
                popup_text = scrolledtext.ScrolledText(popup_frame, wrap=tk.WORD,
                                                      font=("TkDefaultFont", logic_font_size.get()))
                popup_text.pack(fill=tk.BOTH, expand=True)
                popup_text.insert("1.0", content)
                popup_text.config(state=tk.DISABLED)
                # 字体控制
                font_frame = ttk.Frame(popup_frame)
                font_frame.pack(fill=tk.X, pady=(5, 0))
                ttk.Label(font_frame, text="字体大小:").pack(side=tk.LEFT, padx=5)
                popup_font_size = tk.IntVar(value=logic_font_size.get())
                def update_popup_font():
                    popup_text.config(state=tk.NORMAL)
                    popup_text.config(font=("TkDefaultFont", popup_font_size.get()))
                    popup_text.config(state=tk.DISABLED)
                def increase_popup_font():
                    size = popup_font_size.get()
                    if size < 24:
                        popup_font_size.set(size + 1)
                        update_popup_font()
                def decrease_popup_font():
                    size = popup_font_size.get()
                    if size > 8:
                        popup_font_size.set(size - 1)
                        update_popup_font()
                ttk.Button(font_frame, text="放大", command=increase_popup_font, width=8).pack(side=tk.LEFT, padx=2)
                ttk.Button(font_frame, text="缩小", command=decrease_popup_font, width=8).pack(side=tk.LEFT, padx=2)
            logic_text.bind("<Double-1>", show_logic_popup)
            # 字体大小控制按钮
            font_control_frame = ttk.Frame(right_content)
            font_control_frame.pack(fill=tk.X, pady=(5, 0))
            ttk.Label(font_control_frame, text="字体大小:").pack(side=tk.LEFT, padx=5)
            logic_font_size = tk.IntVar(value=10)
            def increase_stock_font():
                size = logic_font_size.get()
                if size < 24:
                    logic_font_size.set(size + 1)
                    logic_text.config(font=("TkDefaultFont", size + 1))
            def decrease_stock_font():
                size = logic_font_size.get()
                if size > 8:
                    logic_font_size.set(size - 1)
                    logic_text.config(font=("TkDefaultFont", size - 1))
            ttk.Button(font_control_frame, text="放大", command=increase_stock_font, width=8).pack(side=tk.LEFT, padx=2)
            ttk.Button(font_control_frame, text="缩小", command=decrease_stock_font, width=8).pack(side=tk.LEFT, padx=2)
            # 右侧信息标签页区域(包含股票介绍、近日涨跌幅、历史涨跌分析、外部链接)
            right_info_notebook = ttk.Notebook(right_content)
            right_info_notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 5))
            # 第一个标签页:股票介绍(默认显示)
            intro_tab = ttk.Frame(right_info_notebook)
            right_info_notebook.add(intro_tab, text="股票介绍")
            # 创建垂直布局:上方文本区域,下方搜索按钮区域
            intro_content_frame = ttk.Frame(intro_tab)
            intro_content_frame.pack(fill=tk.BOTH, expand=True)
            intro_text = scrolledtext.ScrolledText(intro_content_frame, wrap=tk.WORD, font=("TkDefaultFont", 12))
            intro_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            intro_text.insert("1.0", "请选择股票记录以查看股票介绍")
            intro_text.config(state=tk.DISABLED)
            # 搜索按钮区域(初始隐藏)
            search_button_frame = ttk.Frame(intro_content_frame)
            search_button_frame.pack(fill=tk.X, padx=5, pady=5)
            search_button_frame.pack_forget()  # 初始隐藏
            # 第二个标签页:大单分析
            moneyflow_tab = ttk.Frame(right_info_notebook)
            right_info_notebook.add(moneyflow_tab, text="大单分析")
            moneyflow_text = scrolledtext.ScrolledText(moneyflow_tab, wrap=tk.WORD, font=("TkDefaultFont", 12))
            moneyflow_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            moneyflow_text.insert("1.0", "请选择股票记录以查看大单分析")
            moneyflow_text.config(state=tk.DISABLED)
            # 第三个标签页:近日涨跌幅
            change_tab = ttk.Frame(right_info_notebook)
            right_info_notebook.add(change_tab, text="近日涨跌幅")
            change_text = scrolledtext.ScrolledText(change_tab, wrap=tk.WORD, font=("TkDefaultFont", 12))
            change_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            change_text.insert("1.0", "请选择股票记录以查看近日涨跌幅")
            change_text.config(state=tk.DISABLED)
            # 第三个标签页:历史涨跌分析
            history_tab = ttk.Frame(right_info_notebook)
            right_info_notebook.add(history_tab, text="历史涨跌分析")
            history_tree_frame = ttk.Frame(history_tab)
            history_tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            history_columns = ("日期", "N日", "最低差值", "最低差%", "最高差值", "最高差%", "区间位置")
            history_tree = ttk.Treeview(history_tree_frame, columns=history_columns, show="headings", height=20)
            for col in history_columns:
                history_tree.heading(col, text=col)
                history_tree.column(col, width=100, anchor=tk.CENTER)
            history_scrollbar = ttk.Scrollbar(history_tree_frame, orient=tk.VERTICAL, command=history_tree.yview)
            history_tree.configure(yscrollcommand=history_scrollbar.set)
            history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            # 第四个标签页:外部链接
            link_tab = ttk.Frame(right_info_notebook)
            right_info_notebook.add(link_tab, text="外部链接")
            link_frame = ttk.Frame(link_tab, padding=5)
            link_frame.pack(fill=tk.BOTH, expand=True)
            def normalize_stock_code(raw_code):
                if not raw_code:
                    return None, None
                code = raw_code.lower()
                core = code[-6:]
                if code.startswith(("sh", "sz")):
                    prefix = code[:2]
                else:
                    prefix = "sh" if core.startswith(("5", "6")) else "sz"
                return prefix, core
            def build_link(label, code, name):
                prefix, core = normalize_stock_code(code) if code else (None, None)
                # 股票网站链接
                if label == "同花顺" and core:
                    return f"https://basic.10jqka.com.cn/{core}/"
                if label == "东方财富" and prefix and core:
                    return f"https://quote.eastmoney.com/{prefix}{core}.html"
                if label == "股吧" and prefix and core:
                    return f"https://xueqiu.com/S/{prefix.upper()}{core}"
                if label == "东财股吧" and prefix and core:
                    return f"https://guba.eastmoney.com/list,{prefix}{core}.html"
                if label == "雪球" and prefix and core:
                    return f"https://xueqiu.com/S/{prefix.upper()}{core}"
                if label == "新浪财经" and prefix and core:
                    return f"https://finance.sina.com.cn/realstock/company/{prefix}{core}/nc.shtml"
                if label == "腾讯财经" and prefix and core:
                    return f"https://stock.finance.qq.com/cgi-bin/sstock/q_stock_info?code={prefix.upper()}{core}"
                if label == "和讯网" and prefix and core:
                    return f"http://stock.hexun.com/{prefix}{core}.shtml"
                if label == "金融界" and prefix and core:
                    return f"http://stock.jrj.com.cn/share,{prefix}{core}.shtml"
                if label == "证券之星" and prefix and core:
                    return f"http://stock.quote.stockstar.com/{prefix}{core}.shtml"
                # 搜索引擎和社交平台链接(使用股票名称搜索)
                if name:
                    from urllib.parse import quote
                    encoded_name = quote(name)
                    search_term = f"{encoded_name}%20股票"
                    if label == "百度":
                        return f"https://www.baidu.com/s?wd={search_term}"
                    if label == "知乎":
                        return f"https://www.zhihu.com/search?q={search_term}"
                    if label == "小红书":
                        return f"https://www.xiaohongshu.com/search_result?keyword={search_term}"
                    if label == "抖音":
                        return f"https://www.douyin.com/search/{search_term}"
                return None
            link_labels = ["同花顺", "东方财富", "股吧", "东财股吧", "雪球", "新浪财经", "腾讯财经", "和讯网", "金融界", "证券之星", "百度", "知乎", "小红书", "抖音"]
            current_link_urls = {label: None for label in link_labels}
            link_buttons = {}
            def open_stock_link(label):
                """打开外部链接,如果URL不存在则根据当前选中的股票或输入的股票名称构建链接"""
                url = current_link_urls.get(label)
                # 如果URL不存在,尝试从当前选中的股票记录或输入的股票名称获取股票名称并构建链接
                if not url:
                    stock_name_to_use = None
                    # 首先尝试从当前选中的股票记录获取
                    selection = stock_tree.selection()
                    if selection:
                        item = stock_tree.item(selection[0])
                        values = item['values']
                        if len(values) >= 2:
                            stock_name_to_use = values[1].strip() if values[1] else None
                    # 如果从选中记录无法获取,尝试从输入的股票名称获取
                    if not stock_name_to_use:
                        stock_name_to_use = stock_name_var.get().strip() if stock_name_var.get().strip() else None
                    if stock_name_to_use:
                        # 获取股票代码
                        stock_code = get_stock_code_by_name(stock_name_to_use)
                        # 构建链接
                        url = build_link(label, stock_code, stock_name_to_use)
                if url:
                    webbrowser.open(url)
                else:
                    messagebox.showwarning("提示", "请先输入或选择股票记录")
            # 使用网格布局,每行显示多个按钮
            row = 0
            col = 0
            cols_per_row = 5  # 每行显示5个按钮
            for label in link_labels:
                btn = ttk.Button(
                    link_frame,
                    text=label,
                    width=10,
                    command=lambda l=label: open_stock_link(l),
                    state=tk.NORMAL
                )
                btn.grid(row=row, column=col, padx=3, pady=3, sticky="ew")
                link_buttons[label] = btn
                col += 1
                if col >= cols_per_row:
                    col = 0
                    row += 1
            # 配置列权重,使按钮均匀分布
            for i in range(cols_per_row):
                link_frame.columnconfigure(i, weight=1)
            # 第五个标签页:图表分析
            chart_analysis_tab = ttk.Frame(right_info_notebook)
            right_info_notebook.add(chart_analysis_tab, text="图表分析")
            # 图表分析控制区域
            chart_control_frame = ttk.LabelFrame(chart_analysis_tab, text="分析选项", padding=10)
            chart_control_frame.pack(fill=tk.X, padx=5, pady=5)
            # 分析类型选择
            analysis_type_frame = ttk.Frame(chart_control_frame)
            analysis_type_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(analysis_type_frame, text="数据源:").pack(side=tk.LEFT, padx=5)
            chart_analysis_type = tk.StringVar(value="大单分析")
            analysis_type_combo = ttk.Combobox(analysis_type_frame, textvariable=chart_analysis_type,
                                               values=["大单分析", "最近5天股价分析"], state="readonly", width=20)
            analysis_type_combo.pack(side=tk.LEFT, padx=5)
            # 图表类型选择
            chart_type_frame = ttk.Frame(chart_control_frame)
            chart_type_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(chart_type_frame, text="图表类型:").pack(side=tk.LEFT, padx=5)
            chart_type_var = tk.StringVar()
            # 大单分析图表类型
            moneyflow_chart_types = [
                ("📊 大单净流入对比", "moneyflow_comparison"),
                ("📈 主力净额趋势", "main_net_trend"),
                ("💰 超大单和大单对比", "elg_lg_comparison"),
                ("🌊 资金流向分析", "fund_flow_analysis"),
                ("📉 净流入柱状图", "net_inflow_bar"),
                ("📊 综合大单分析", "comprehensive_moneyflow")
            ]
            # 股价分析图表类型
            price_chart_types = [
                ("📈 收盘价趋势", "price_trend"),
                ("📊 涨跌幅变化", "change_bar"),
                ("📉 价格波动分析", "price_volatility"),
                ("💰 价格和涨跌幅对比", "price_change_comparison"),
                ("📊 综合股价分析", "comprehensive_price")
            ]
            chart_type_combo = ttk.Combobox(chart_type_frame, textvariable=chart_type_var,
                                            state="readonly", width=30)
            chart_type_combo.pack(side=tk.LEFT, padx=5)
            # 更新图表类型选项
            def update_chart_types(*args):
                analysis_type = chart_analysis_type.get()
                if analysis_type == "大单分析":
                    chart_type_combo['values'] = [text for text, _ in moneyflow_chart_types]
                    chart_type_var.set(moneyflow_chart_types[0][0])
                else:  # 最近5天股价分析
                    chart_type_combo['values'] = [text for text, _ in price_chart_types]
                    chart_type_var.set(price_chart_types[0][0])
            chart_analysis_type.trace('w', update_chart_types)
            update_chart_types()  # 初始化
            # 创建图表类型映射
            chart_type_map = {}
            chart_type_map.update({text: value for text, value in moneyflow_chart_types})
            chart_type_map.update({text: value for text, value in price_chart_types})
            # 生成图表按钮
            button_frame = ttk.Frame(chart_control_frame)
            button_frame.pack(fill=tk.X)
            ttk.Button(button_frame, text="生成图表", command=lambda: generate_chart_analysis()).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="清除图表", command=lambda: clear_chart_display()).pack(side=tk.LEFT, padx=5)
            # 图表显示区域
            chart_display_frame = ttk.LabelFrame(chart_analysis_tab, text="图表显示", padding=10)
            chart_display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            chart_canvas_widget = None
            chart_figure = None
            def generate_chart_analysis():
                """生成图表分析"""
                nonlocal chart_canvas_widget, chart_figure
                # 清除旧图表
                if chart_canvas_widget:
                    chart_canvas_widget.get_tk_widget().destroy()
                    chart_canvas_widget = None
                if chart_figure:
                    plt.close(chart_figure)
                    chart_figure = None
                analysis_type = chart_analysis_type.get()
                # 获取当前选中的股票或输入的股票名称
                stock_name = None
                selection = stock_tree.selection()
                if selection:
                    item = stock_tree.item(selection[0])
                    values = item['values']
                    if len(values) >= 2:
                        stock_name = values[1].strip() if values[1] else None
                # 如果从选中记录无法获取,尝试从输入的股票名称获取
                if not stock_name:
                    stock_name = stock_name_var.get().strip() if stock_name_var.get().strip() else None
                if not stock_name:
                    messagebox.showwarning("提示", "请先输入或选择股票记录")
                    return
                stock_code = get_stock_code_by_name(stock_name)
                if not stock_code:
                    messagebox.showwarning("提示", f"无法获取股票代码: {stock_name}")
                    return
                try:
                    chart_type_text = chart_type_var.get()
                    chart_type = chart_type_map.get(chart_type_text, "moneyflow_comparison")
                    if analysis_type == "大单分析":
                        # 获取大单分析数据
                        moneyflow_data = self._fetch_moneyflow_data(stock_code, stock_name)
                        if not moneyflow_data or not isinstance(moneyflow_data, dict) or "days" not in moneyflow_data:
                            messagebox.showwarning("提示", "无法获取大单分析数据,请先在大单分析标签页获取数据")
                            return
                        days_data = moneyflow_data["days"]
                        if not days_data:
                            messagebox.showwarning("提示", "大单分析数据为空")
                            return
                        # 反转数据,确保从左到右是从旧到新(days_data是从近到远,需要反转)
                        days_data = list(reversed(days_data))
                        # 准备图表数据
                        dates = [day["date"] for day in days_data]
                        elg_nets = [day["elg_net"] for day in days_data]
                        lg_nets = [day["lg_net"] for day in days_data]
                        total_nets = [day["total_lg_net"] for day in days_data]
                        net_mf_amounts = [day["net_mf_amount"] for day in days_data]
                        # 根据图表类型生成不同的图表
                        if chart_type == "moneyflow_comparison":
                            # 大单净流入对比
                            fig, ax = plt.subplots(1, 1, figsize=(10, 6))
                            fig.suptitle(f"{stock_name} ({stock_code}) - 大单净流入对比", fontsize=14, fontweight='bold')
                            x = range(len(dates))
                            width = 0.35
                            ax.bar([i - width/2 for i in x], elg_nets, width, label='超大单净流入', color='red', alpha=0.7)
                            ax.bar([i + width/2 for i in x], lg_nets, width, label='大单净流入', color='blue', alpha=0.7)
                            ax.set_xlabel('日期(从左到右:旧→新)')
                            ax.set_ylabel('净流入额(万元)')
                            ax.set_xticks(x)
                            ax.set_xticklabels(dates, rotation=45, ha='right')
                            ax.legend()
                            ax.grid(True, alpha=0.3)
                            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                        elif chart_type == "main_net_trend":
                            # 主力净额趋势
                            fig, ax = plt.subplots(1, 1, figsize=(10, 6))
                            fig.suptitle(f"{stock_name} ({stock_code}) - 主力净额趋势", fontsize=14, fontweight='bold')
                            x = range(len(dates))
                            colors = ['red' if net > 0 else 'green' for net in total_nets]
                            ax.bar(x, total_nets, color=colors, alpha=0.7, label='主力净额')
                            ax.set_xlabel('日期(从左到右:旧→新)')
                            ax.set_ylabel('主力净额(万元)')
                            ax.set_xticks(x)
                            ax.set_xticklabels(dates, rotation=45, ha='right')
                            ax.legend()
                            ax.grid(True, alpha=0.3)
                            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                        elif chart_type == "elg_lg_comparison":
                            # 超大单和大单对比
                            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
                            fig.suptitle(f"{stock_name} ({stock_code}) - 超大单和大单对比", fontsize=14, fontweight='bold')
                            x = range(len(dates))
                            ax1.plot(x, elg_nets, marker='o', linewidth=2, markersize=6, color='red', label='超大单净流入')
                            ax1.set_xlabel('日期(从左到右:旧→新)')
                            ax1.set_ylabel('超大单净流入(万元)')
                            ax1.set_xticks(x)
                            ax1.set_xticklabels(dates, rotation=45, ha='right')
                            ax1.legend()
                            ax1.grid(True, alpha=0.3)
                            ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                            ax2.plot(x, lg_nets, marker='s', linewidth=2, markersize=6, color='blue', label='大单净流入')
                            ax2.set_xlabel('日期(从左到右:旧→新)')
                            ax2.set_ylabel('大单净流入(万元)')
                            ax2.set_xticks(x)
                            ax2.set_xticklabels(dates, rotation=45, ha='right')
                            ax2.legend()
                            ax2.grid(True, alpha=0.3)
                            ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                        elif chart_type == "fund_flow_analysis":
                            # 资金流向分析
                            fig, ax = plt.subplots(1, 1, figsize=(10, 6))
                            fig.suptitle(f"{stock_name} ({stock_code}) - 资金流向分析", fontsize=14, fontweight='bold')
                            x = range(len(dates))
                            colors = ['red' if mf > 0 else 'green' for mf in net_mf_amounts]
                            ax.bar(x, net_mf_amounts, color=colors, alpha=0.7, label='资金流向净流入额')
                            ax.set_xlabel('日期(从左到右:旧→新)')
                            ax.set_ylabel('资金流向净流入额(万元)')
                            ax.set_xticks(x)
                            ax.set_xticklabels(dates, rotation=45, ha='right')
                            ax.legend()
                            ax.grid(True, alpha=0.3)
                            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                        elif chart_type == "net_inflow_bar":
                            # 净流入柱状图
                            fig, ax = plt.subplots(1, 1, figsize=(10, 6))
                            fig.suptitle(f"{stock_name} ({stock_code}) - 净流入柱状图", fontsize=14, fontweight='bold')
                            x = range(len(dates))
                            width = 0.25
                            ax.bar([i - width*1.5 for i in x], elg_nets, width, label='超大单', color='red', alpha=0.7)
                            ax.bar([i - width*0.5 for i in x], lg_nets, width, label='大单', color='blue', alpha=0.7)
                            ax.bar([i + width*0.5 for i in x], total_nets, width, label='主力净额', color='orange', alpha=0.7)
                            ax.bar([i + width*1.5 for i in x], net_mf_amounts, width, label='资金流向', color='green', alpha=0.7)
                            ax.set_xlabel('日期(从左到右:旧→新)')
                            ax.set_ylabel('净流入额(万元)')
                            ax.set_xticks(x)
                            ax.set_xticklabels(dates, rotation=45, ha='right')
                            ax.legend()
                            ax.grid(True, alpha=0.3)
                            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                        elif chart_type == "comprehensive_moneyflow":
                            # 综合大单分析
                            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 10))
                            fig.suptitle(f"{stock_name} ({stock_code}) - 综合大单分析", fontsize=14, fontweight='bold')
                            x = range(len(dates))
                            # 超大单
                            ax1.bar(x, elg_nets, color='red', alpha=0.7)
                            ax1.set_title('超大单净流入')
                            ax1.set_xticks(x)
                            ax1.set_xticklabels(dates, rotation=45, ha='right', fontsize=8)
                            ax1.grid(True, alpha=0.3)
                            ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                            # 大单
                            ax2.bar(x, lg_nets, color='blue', alpha=0.7)
                            ax2.set_title('大单净流入')
                            ax2.set_xticks(x)
                            ax2.set_xticklabels(dates, rotation=45, ha='right', fontsize=8)
                            ax2.grid(True, alpha=0.3)
                            ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                            # 主力净额
                            colors = ['red' if net > 0 else 'green' for net in total_nets]
                            ax3.bar(x, total_nets, color=colors, alpha=0.7)
                            ax3.set_title('主力净额')
                            ax3.set_xlabel('日期(从左到右:旧→新)')
                            ax3.set_xticks(x)
                            ax3.set_xticklabels(dates, rotation=45, ha='right', fontsize=8)
                            ax3.grid(True, alpha=0.3)
                            ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                            # 资金流向
                            mf_colors = ['red' if mf > 0 else 'green' for mf in net_mf_amounts]
                            ax4.bar(x, net_mf_amounts, color=mf_colors, alpha=0.7)
                            ax4.set_title('资金流向净流入额')
                            ax4.set_xlabel('日期(从左到右:旧→新)')
                            ax4.set_xticks(x)
                            ax4.set_xticklabels(dates, rotation=45, ha='right', fontsize=8)
                            ax4.grid(True, alpha=0.3)
                            ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                        plt.tight_layout()
                        chart_figure = fig
                    elif analysis_type == "最近5天股价分析":
                        # 获取股价涨跌幅数据
                        change_data = self._fetch_recent_changes(stock_code, stock_name)
                        if not change_data or "最近10日涨跌幅" not in change_data:
                            messagebox.showwarning("提示", "无法获取股价涨跌幅数据,请先在近日涨跌幅标签页获取数据")
                            return
                        # 解析涨跌幅数据
                        lines = change_data.split('\n')
                        dates = []
                        changes = []
                        prices = []
                        in_changes_section = False
                        for line in lines:
                            if "最近10日涨跌幅" in line:
                                in_changes_section = True
                                continue
                            if "=" in line and in_changes_section:
                                if len(dates) > 0:  # 如果已经有数据,说明到了下一个部分
                                    break
                                continue
                            if in_changes_section and ":" in line and "收盘价" in line:
                                try:
                                    # 解析格式:日期: 收盘价 X.XX, 涨跌幅 +/-X.XX%
                                    parts = line.split(":")
                                    if len(parts) >= 2:
                                        date = parts[0].strip()
                                        rest = parts[1].strip()
                                        price_part = rest.split(",")[0].replace("收盘价", "").strip()
                                        change_part = rest.split(",")[1].replace("涨跌幅", "").strip().replace("%", "")
                                        dates.append(date)
                                        prices.append(float(price_part))
                                        changes.append(float(change_part))
                                        if len(dates) >= 5:  # 只取最近5天
                                            break
                                except:
                                    continue
                        if len(dates) < 2:
                            messagebox.showwarning("提示", "股价涨跌幅数据不足,无法生成图表")
                            return
                        # 反转数据,确保从左到右是从旧到新(dates是从近到远,需要反转)
                        dates = list(reversed(dates))
                        prices = list(reversed(prices))
                        changes = list(reversed(changes))
                        # 根据图表类型生成不同的图表
                        if chart_type == "price_trend":
                            # 收盘价趋势
                            fig, ax = plt.subplots(1, 1, figsize=(10, 6))
                            fig.suptitle(f"{stock_name} ({stock_code}) - 收盘价趋势", fontsize=14, fontweight='bold')
                            x = range(len(dates))
                            ax.plot(x, prices, marker='o', linewidth=2, markersize=8, color='blue', label='收盘价')
                            ax.set_xlabel('日期(从左到右:旧→新)')
                            ax.set_ylabel('收盘价(元)')
                            ax.set_xticks(x)
                            ax.set_xticklabels(dates, rotation=45, ha='right')
                            ax.legend()
                            ax.grid(True, alpha=0.3)
                        elif chart_type == "change_bar":
                            # 涨跌幅变化
                            fig, ax = plt.subplots(1, 1, figsize=(10, 6))
                            fig.suptitle(f"{stock_name} ({stock_code}) - 涨跌幅变化", fontsize=14, fontweight='bold')
                            x = range(len(dates))
                            colors = ['red' if chg > 0 else 'green' for chg in changes]
                            ax.bar(x, changes, color=colors, alpha=0.7, label='涨跌幅')
                            ax.set_xlabel('日期(从左到右:旧→新)')
                            ax.set_ylabel('涨跌幅(%)')
                            ax.set_xticks(x)
                            ax.set_xticklabels(dates, rotation=45, ha='right')
                            ax.legend()
                            ax.grid(True, alpha=0.3)
                            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                        elif chart_type == "price_volatility":
                            # 价格波动分析
                            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
                            fig.suptitle(f"{stock_name} ({stock_code}) - 价格波动分析", fontsize=14, fontweight='bold')
                            x = range(len(dates))
                            # 收盘价趋势
                            ax1.plot(x, prices, marker='o', linewidth=2, markersize=6, color='blue', label='收盘价')
                            ax1.fill_between(x, prices, alpha=0.3, color='blue')
                            ax1.set_xlabel('日期(从左到右:旧→新)')
                            ax1.set_ylabel('收盘价(元)')
                            ax1.set_xticks(x)
                            ax1.set_xticklabels(dates, rotation=45, ha='right')
                            ax1.legend()
                            ax1.grid(True, alpha=0.3)
                            # 涨跌幅
                            colors = ['red' if chg > 0 else 'green' for chg in changes]
                            ax2.bar(x, changes, color=colors, alpha=0.7)
                            ax2.set_xlabel('日期(从左到右:旧→新)')
                            ax2.set_ylabel('涨跌幅(%)')
                            ax2.set_xticks(x)
                            ax2.set_xticklabels(dates, rotation=45, ha='right')
                            ax2.grid(True, alpha=0.3)
                            ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                        elif chart_type == "price_change_comparison":
                            # 价格和涨跌幅对比
                            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
                            fig.suptitle(f"{stock_name} ({stock_code}) - 价格和涨跌幅对比", fontsize=14, fontweight='bold')
                            x = range(len(dates))
                            # 收盘价
                            ax1.plot(x, prices, marker='o', linewidth=2, markersize=8, color='blue', label='收盘价')
                            ax1.set_xlabel('日期(从左到右:旧→新)')
                            ax1.set_ylabel('收盘价(元)')
                            ax1.set_xticks(x)
                            ax1.set_xticklabels(dates, rotation=45, ha='right')
                            ax1.legend()
                            ax1.grid(True, alpha=0.3)
                            # 涨跌幅
                            colors = ['red' if chg > 0 else 'green' for chg in changes]
                            ax2.bar(x, changes, color=colors, alpha=0.7, label='涨跌幅')
                            ax2.set_xlabel('日期(从左到右:旧→新)')
                            ax2.set_ylabel('涨跌幅(%)')
                            ax2.set_xticks(x)
                            ax2.set_xticklabels(dates, rotation=45, ha='right')
                            ax2.legend()
                            ax2.grid(True, alpha=0.3)
                            ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                        elif chart_type == "comprehensive_price":
                            # 综合股价分析
                            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 10))
                            fig.suptitle(f"{stock_name} ({stock_code}) - 综合股价分析", fontsize=14, fontweight='bold')
                            x = range(len(dates))
                            # 收盘价折线图
                            ax1.plot(x, prices, marker='o', linewidth=2, markersize=6, color='blue')
                            ax1.set_title('收盘价趋势')
                            ax1.set_xticks(x)
                            ax1.set_xticklabels(dates, rotation=45, ha='right', fontsize=8)
                            ax1.grid(True, alpha=0.3)
                            # 涨跌幅柱状图
                            colors = ['red' if chg > 0 else 'green' for chg in changes]
                            ax2.bar(x, changes, color=colors, alpha=0.7)
                            ax2.set_title('涨跌幅变化')
                            ax2.set_xticks(x)
                            ax2.set_xticklabels(dates, rotation=45, ha='right', fontsize=8)
                            ax2.grid(True, alpha=0.3)
                            ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                            # 收盘价柱状图
                            ax3.bar(x, prices, color='blue', alpha=0.7)
                            ax3.set_title('收盘价柱状图')
                            ax3.set_xlabel('日期(从左到右:旧→新)')
                            ax3.set_xticks(x)
                            ax3.set_xticklabels(dates, rotation=45, ha='right', fontsize=8)
                            ax3.grid(True, alpha=0.3)
                            # 涨跌幅折线图
                            ax4.plot(x, changes, marker='s', linewidth=2, markersize=6, color='red', label='涨跌幅')
                            ax4.set_title('涨跌幅趋势')
                            ax4.set_xlabel('日期(从左到右:旧→新)')
                            ax4.set_xticks(x)
                            ax4.set_xticklabels(dates, rotation=45, ha='right', fontsize=8)
                            ax4.legend()
                            ax4.grid(True, alpha=0.3)
                            ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                        plt.tight_layout()
                        chart_figure = fig
                    # 显示图表
                    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                    chart_canvas_widget = FigureCanvasTkAgg(chart_figure, chart_display_frame)
                    chart_canvas_widget.draw()
                    chart_canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                except Exception as e:
                    messagebox.showerror("错误", f"生成图表失败: {e!s}")
                    import traceback
                    traceback.print_exc()
            def clear_chart_display():
                """清除图表显示"""
                nonlocal chart_canvas_widget, chart_figure
                if chart_canvas_widget:
                    chart_canvas_widget.get_tk_widget().destroy()
                    chart_canvas_widget = None
                if chart_figure:
                    plt.close(chart_figure)
                    chart_figure = None
            # 均线仓位检测标签页
            ma_position_tab = ttk.Frame(right_info_notebook)
            right_info_notebook.add(ma_position_tab, text="均线仓位检测")
            # 创建滚动文本框显示详情
            ma_position_text_frame = ttk.Frame(ma_position_tab)
            ma_position_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            ma_position_text = scrolledtext.ScrolledText(ma_position_text_frame, wrap=tk.WORD,
                                                         font=("TkDefaultFont", 12), height=30)
            ma_position_text.pack(fill=tk.BOTH, expand=True)
            ma_position_text.insert("1.0", "请选择股票数据表中的股票以查看均线检测和仓位计算结果")
            ma_position_text.config(state=tk.DISABLED)
            def update_ma_position_detection(stock_name, stock_code):
                """更新均线仓位检测显示"""
                if not stock_code:
                    ma_position_text.config(state=tk.NORMAL)
                    ma_position_text.delete("1.0", tk.END)
                    ma_position_text.insert("1.0", f"无法获取股票代码: {stock_name}")
                    ma_position_text.config(state=tk.DISABLED)
                    return
                # 在后台线程中执行计算
                def calculate_and_display():
                    try:
                        content = "【均线仓位检测详情】\n"
                        content += f"股票名称: {stock_name}\n"
                        content += f"股票代码: {stock_code}\n"
                        content += "="*80 + "\n\n"
                        # 1. 均线检测
                        content += "【均线检测结果】\n"
                        detection_result = self._three_dimensional_detection(stock_name, stock_code)
                        if detection_result and detection_result.get('success'):
                            technical_result = detection_result.get('technical', {})
                            ma_status = technical_result.get('ma_status', {})
                            can_open = technical_result.get('can_open', False)
                            content += f"检测结果: {'满足开新仓条件' if can_open else '不满足开新仓条件'}\n\n"
                            # 显示各均线状态
                            ma_list = []
                            if ma_status.get('ma1', False):
                                ma_list.append("1日")
                            if ma_status.get('ma5', False):
                                ma_list.append("5日")
                            if ma_status.get('ma10', False):
                                ma_list.append("10日")
                            if ma_status.get('ma20', False):
                                ma_list.append("20日")
                            content += f"站上均线: {', '.join(ma_list) if ma_list else '无'}\n"
                            if ma_status.get('below_ma20', False):
                                content += "⚠ 股价低于20日线\n"
                            # 获取当前价格
                            try:
                                result = self._fetch_recent_daily_closes(stock_code, days=45, source="default", token=self.ts_token, return_volume=False)
                                if isinstance(result, tuple) and len(result) >= 2:
                                    dates, closes = result[:2]
                                else:
                                    _dates, closes = result, []
                                if closes and len(closes) > 0:
                                    current_price = float(closes[-1])
                                    content += f"当前价格: {current_price:.2f}\n"
                            except:
                                pass
                            content += "\n"
                        else:
                            content += "均线检测失败\n\n"
                        # 2. 仓位计算(凯利公式)
                        content += "【仓位计算(凯利公式)】\n"
                        if detection_result and detection_result.get('success'):
                            position_result = detection_result.get('position', {})
                            kelly_ratio = position_result.get('kelly_ratio', 0)
                            kelly_percent = position_result.get('kelly_percent', 0)
                            b = position_result.get('b', 0)
                            p = position_result.get('p', 0)
                            content += f"凯利比例: {kelly_ratio:.4f} ({kelly_percent:.2f}%)\n"
                            content += f"参数b: {b:.4f}\n"
                            content += f"参数p: {p:.4f}\n"
                            content += "\n"
                        else:
                            content += "仓位计算失败\n\n"
                        # 3. 获取历史数据计算最低点和最高点差值百分比
                        try:
                            import akshare as ak
                            hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                            if not hist_data.empty and len(hist_data) >= 20:
                                # 获取当前价格
                                current_price = None
                                try:
                                    spot_row = get_realtime_spot_row(stock_code, cache_duration=60)
                                    if spot_row is not None:
                                        price = spot_row.get('最新价')
                                        if price is not None:
                                            current_price = float(price)
                                except:
                                    pass
                                if current_price is None:
                                    current_price = float(hist_data.iloc[-1]['收盘'])
                                content += "【最低点差值百分比】\n"
                                # 5日最低点
                                if len(hist_data) >= 5:
                                    recent_5days = hist_data.tail(5)
                                    min_low_5 = float(recent_5days['最低'].min())
                                    if min_low_5 > 0:
                                        low_diff_5 = current_price - min_low_5
                                        low_diff_pct_5 = (low_diff_5 / min_low_5) * 100
                                        content += f"5日最低点: {min_low_5:.2f}, 差值: {low_diff_5:.2f}, 差值%: {low_diff_pct_5:.2f}%\n"
                                # 10日最低点
                                if len(hist_data) >= 10:
                                    recent_10days = hist_data.tail(10)
                                    min_low_10 = float(recent_10days['最低'].min())
                                    if min_low_10 > 0:
                                        low_diff_10 = current_price - min_low_10
                                        low_diff_pct_10 = (low_diff_10 / min_low_10) * 100
                                        content += f"10日最低点: {min_low_10:.2f}, 差值: {low_diff_10:.2f}, 差值%: {low_diff_pct_10:.2f}%\n"
                                # 20日最低点
                                if len(hist_data) >= 20:
                                    recent_20days = hist_data.tail(20)
                                    min_low_20 = float(recent_20days['最低'].min())
                                    if min_low_20 > 0:
                                        low_diff_20 = current_price - min_low_20
                                        low_diff_pct_20 = (low_diff_20 / min_low_20) * 100
                                        content += f"20日最低点: {min_low_20:.2f}, 差值: {low_diff_20:.2f}, 差值%: {low_diff_pct_20:.2f}%\n"
                                content += "\n"
                                content += "【最高点差值百分比】\n"
                                # 5日最高点
                                if len(hist_data) >= 5:
                                    recent_5days = hist_data.tail(5)
                                    max_high_5 = float(recent_5days['最高'].max())
                                    if max_high_5 > 0:
                                        high_diff_5 = current_price - max_high_5
                                        high_diff_pct_5 = (high_diff_5 / max_high_5) * 100
                                        content += f"5日最高点: {max_high_5:.2f}, 差值: {high_diff_5:.2f}, 差值%: {high_diff_pct_5:.2f}%\n"
                                # 10日最高点
                                if len(hist_data) >= 10:
                                    recent_10days = hist_data.tail(10)
                                    max_high_10 = float(recent_10days['最高'].max())
                                    if max_high_10 > 0:
                                        high_diff_10 = current_price - max_high_10
                                        high_diff_pct_10 = (high_diff_10 / max_high_10) * 100
                                        content += f"10日最高点: {max_high_10:.2f}, 差值: {high_diff_10:.2f}, 差值%: {high_diff_pct_10:.2f}%\n"
                                # 20日最高点
                                if len(hist_data) >= 20:
                                    recent_20days = hist_data.tail(20)
                                    max_high_20 = float(recent_20days['最高'].max())
                                    if max_high_20 > 0:
                                        high_diff_20 = current_price - max_high_20
                                        high_diff_pct_20 = (high_diff_20 / max_high_20) * 100
                                        content += f"20日最高点: {max_high_20:.2f}, 差值: {high_diff_20:.2f}, 差值%: {high_diff_pct_20:.2f}%\n"
                        except Exception as e:
                            content += f"获取高低点数据失败: {e}\n"
                        # 在主线程中更新UI
                        def update_ui():
                            ma_position_text.config(state=tk.NORMAL)
                            ma_position_text.delete("1.0", tk.END)
                            ma_position_text.insert("1.0", content)
                            ma_position_text.config(state=tk.DISABLED)
                        if hasattr(self, 'root') and self.root.winfo_exists():
                            self.root.after(0, update_ui)
                    except Exception as e:
                        error_content = f"计算失败: {e!s}\n"
                        import traceback
                        error_content += traceback.format_exc()
                        def show_error():
                            ma_position_text.config(state=tk.NORMAL)
                            ma_position_text.delete("1.0", tk.END)
                            ma_position_text.insert("1.0", error_content)
                            ma_position_text.config(state=tk.DISABLED)
                        if hasattr(self, 'root') and self.root.winfo_exists():
                            self.root.after(0, show_error)
                # 在后台线程中执行
                threading.Thread(target=calculate_and_display, daemon=True).start()
            # 设置默认显示股票介绍标签页
            right_info_notebook.select(intro_tab)
            # 均线检测区域(替换原来的股票基础数据)
            analysis_frame = ttk.LabelFrame(right_content, text="均线检测", padding=5)
            analysis_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
            # 创建左右布局:左边检测区域,右边按钮区域
            detection_paned = ttk.PanedWindow(analysis_frame, orient=tk.HORIZONTAL)
            detection_paned.pack(fill=tk.BOTH, expand=True)
            # 左侧:检测内容区域
            detection_content = ttk.Frame(detection_paned)
            detection_paned.add(detection_content, weight=3)  # 占75%
            # 右侧:按钮区域
            button_sidebar = ttk.Frame(detection_paned)
            detection_paned.add(button_sidebar, weight=1)  # 占25%
            # 创建2x2布局:上排1日/5日,下排10日/20日
            ma_top_row = ttk.Frame(detection_content)
            ma_top_row.pack(fill=tk.X, pady=(0, 6))
            ma_bottom_row = ttk.Frame(detection_content)
            ma_bottom_row.pack(fill=tk.X, pady=(0, 6))
            # 检测相关的变量定义(稍后在选择股票时初始化)
            ma_vars = {
                'stock_code_var': tk.StringVar(value="--"),
                'current_price_var': tk.StringVar(value="--"),
                'ma1_reference_var': tk.StringVar(value="--"),
                'ma1_prev_var': tk.StringVar(value="--"),
                'ma1_status_var': tk.StringVar(value="未检测"),
                'ma1_source_var': tk.StringVar(value="数据来源: 未检测"),
                'ma5_reference_var': tk.StringVar(value="--"),
                'ma5_prev_var': tk.StringVar(value="--"),
                'ma5_status_var': tk.StringVar(value="未检测"),
                'ma10_reference_var': tk.StringVar(value="--"),
                'ma10_prev_var': tk.StringVar(value="--"),
                'ma10_status_var': tk.StringVar(value="未检测"),
                'ma20_reference_var': tk.StringVar(value="--"),
                'ma20_prev_var': tk.StringVar(value="--"),
                'ma20_status_var': tk.StringVar(value="未检测"),
            }
            def reset_detection_ui(message="请选择股票记录以查看均线检测"):
                """重置检测界面"""
                nonlocal current_stock_record
                # 注意:不重置 current_query_stock_name,保持查询的股票名称
                current_stock_record = None
                for label in link_labels:
                    current_link_urls[label] = None
                    # 按钮始终保持可用状态
                    link_buttons[label].config(state=tk.NORMAL)
                # 重置所有检测变量
                ma_vars['stock_code_var'].set("--")
                ma_vars['current_price_var'].set("--")
                ma_vars['ma1_reference_var'].set("--")
                ma_vars['ma1_prev_var'].set("--")
                ma_vars['ma1_status_var'].set("未检测")
                ma_vars['ma1_source_var'].set("数据来源: 未检测")
                ma_vars['ma5_reference_var'].set("--")
                ma_vars['ma5_prev_var'].set("--")
                ma_vars['ma5_status_var'].set("未检测")
                ma_vars['ma10_reference_var'].set("--")
                ma_vars['ma10_prev_var'].set("--")
                ma_vars['ma10_status_var'].set("未检测")
                ma_vars['ma20_reference_var'].set("--")
                ma_vars['ma20_prev_var'].set("--")
                ma_vars['ma20_status_var'].set("未检测")
            reset_detection_ui()
            # 创建检测UI组件(参考开新仓的样式)
            # 1日线检测区域(上排左边)
            ma1_frame = ttk.LabelFrame(ma_top_row, text="1日线检测", padding=5)
            ma1_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
            ttk.Label(ma1_frame, text="股票代码:", width=10).pack(anchor=tk.W)
            ma1_code_label = tk.Label(ma1_frame, textvariable=ma_vars['stock_code_var'],
                                     foreground="blue", font=("TkDefaultFont", 11, "bold"))
            ma1_code_label.pack(anchor=tk.W)
            ttk.Label(ma1_frame, text="最新价:", width=8).pack(anchor=tk.W)
            tk.Label(ma1_frame, textvariable=ma_vars['current_price_var'],
                    foreground="green", font=("TkDefaultFont", 11)).pack(anchor=tk.W)
            ttk.Label(ma1_frame, text="参考1日线:", width=10).pack(anchor=tk.W)
            tk.Label(ma1_frame, textvariable=ma_vars['ma1_reference_var'],
                    foreground="green", font=("TkDefaultFont", 11)).pack(anchor=tk.W)
            ma1_status_label = tk.Label(ma1_frame, textvariable=ma_vars['ma1_status_var'],
                                       foreground="blue", font=("TkDefaultFont", 8))
            ma1_status_label.pack(anchor=tk.W, pady=2)
            # 5日线检测区域(上排右边)
            ma5_frame = ttk.LabelFrame(ma_top_row, text="5日线检测", padding=5)
            ma5_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
            ttk.Label(ma5_frame, text="参考5日线:", width=10).pack(anchor=tk.W)
            tk.Label(ma5_frame, textvariable=ma_vars['ma5_reference_var'],
                    foreground="green", font=("TkDefaultFont", 11)).pack(anchor=tk.W)
            ma5_status_label = tk.Label(ma5_frame, textvariable=ma_vars['ma5_status_var'],
                                       foreground="blue", font=("TkDefaultFont", 8))
            ma5_status_label.pack(anchor=tk.W, pady=2)
            # 10日线检测区域(下排左边)
            ma10_frame = ttk.LabelFrame(ma_bottom_row, text="10日线检测", padding=5)
            ma10_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
            ttk.Label(ma10_frame, text="参考10日线:", width=10).pack(anchor=tk.W)
            tk.Label(ma10_frame, textvariable=ma_vars['ma10_reference_var'],
                    foreground="green", font=("TkDefaultFont", 11)).pack(anchor=tk.W)
            ma10_status_label = tk.Label(ma10_frame, textvariable=ma_vars['ma10_status_var'],
                                        foreground="blue", font=("TkDefaultFont", 8))
            ma10_status_label.pack(anchor=tk.W, pady=2)
            # 20日线检测区域(下排右边)
            ma20_frame = ttk.LabelFrame(ma_bottom_row, text="20日线检测", padding=5)
            ma20_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
            ttk.Label(ma20_frame, text="参考20日线:", width=10).pack(anchor=tk.W)
            tk.Label(ma20_frame, textvariable=ma_vars['ma20_reference_var'],
                    foreground="green", font=("TkDefaultFont", 11)).pack(anchor=tk.W)
            ma20_status_label = tk.Label(ma20_frame, textvariable=ma_vars['ma20_status_var'],
                                        foreground="blue", font=("TkDefaultFont", 8))
            ma20_status_label.pack(anchor=tk.W, pady=2)
            # 右侧按钮区域
            # Tushare登录按钮
            tushare_login_frame = ttk.LabelFrame(button_sidebar, text="Tushare登录", padding=5)
            tushare_login_frame.pack(fill=tk.X, pady=(0, 10))
            ts_status_var_db = tk.StringVar(value="未登录" if not self.ts_client else "已登录")
            ts_status_label_db = tk.Label(tushare_login_frame, textvariable=ts_status_var_db,
                                         foreground="gray" if not self.ts_client else "green",
                                         font=("TkDefaultFont", 11))
            ts_status_label_db.pack(pady=5)
            def login_tushare_for_db():
                """在数据库窗口中登录Tushare"""
                if not TS_AVAILABLE:
                    messagebox.showerror("错误", "当前环境未安装tushare,请先安装", parent=db_window)
                    return
                try:
                    self._ensure_tushare_client(self.ts_token or TS_DEFAULT_TOKEN)
                    ts_status_var_db.set("已登录")
                    ts_status_label_db.configure(foreground="green")
                    messagebox.showinfo("成功", "Tushare 登录成功", parent=db_window)
                except Exception as e:
                    ts_status_var_db.set("登录失败")
                    ts_status_label_db.configure(foreground="red")
                    messagebox.showerror("错误", f"Tushare 登录失败: {e}", parent=db_window)
            ttk.Button(tushare_login_frame, text="登录Tushare",
                      command=login_tushare_for_db, width=15).pack(pady=5)
            # 开新仓按钮区域
            new_position_btn_frame = ttk.LabelFrame(button_sidebar, text="开新仓", padding=5)
            new_position_btn_frame.pack(fill=tk.X, pady=(0, 10))
            def open_new_position_with_stock(position_type):
                # 优先使用当前查询的股票名称,如果没有则使用选中的记录
                stock_name = None
                if current_query_stock_name:
                    stock_name = current_query_stock_name.strip()
                elif current_stock_record:
                    stock_name = current_stock_record.get('stock_name', '').strip()
                if not stock_name:
                    messagebox.showwarning("警告", "请先输入或选择股票", parent=db_window)
                    return
                self._trigger_new_position_dialog(position_type, stock_name, parent=db_window)
            ttk.Button(new_position_btn_frame, text="开新仓-龙头",
                      command=lambda: open_new_position_with_stock("龙头"), width=15).pack(pady=2)
            ttk.Button(new_position_btn_frame, text="开新仓-强势股",
                      command=lambda: open_new_position_with_stock("强势股"), width=15).pack(pady=2)
            ttk.Button(new_position_btn_frame, text="开新仓-绩优股",
                      command=lambda: open_new_position_with_stock("绩优股"), width=15).pack(pady=2)
            ttk.Button(new_position_btn_frame, text="开新仓-朋友",
                      command=lambda: open_new_position_with_stock("朋友"), width=15).pack(pady=2)
            ttk.Button(new_position_btn_frame, text="开新仓-均值回归",
                      command=lambda: open_new_position_with_stock("均值回归"), width=15).pack(pady=2)
            def format_number(value, suffix=""):
                if value is None:
                    return "-"
                try:
                    return f"{float(value):.2f}{suffix}"
                except Exception:
                    return f"{value}{suffix}"
            def format_percent(value):
                if value is None:
                    return "-"
                try:
                    return f"{float(value):.2f}%"
                except Exception:
                    return "-"
            def format_market_cap(value):
                if value is None:
                    return "-"
                try:
                    val = float(value)
                    if val >= 1e8:
                        return f"{val / 1e8:.2f} 亿"
                    if val >= 1e4:
                        return f"{val / 1e4:.2f} 万"
                    return f"{val:.2f}"
                except Exception:
                    return "-"
            # 防抖处理:避免快速切换股票时频繁更新
            _update_timer = None
            _current_updating_stock = None
            _detection_results = {}  # 存储检测结果
            def perform_ma_detection(stock_name, stock_code):
                """执行均线检测(复用开新仓的检测逻辑)"""
                try:
                    # 使用默认数据源进行检测(优先Tushare,失败则AKShare)
                    result = self._fetch_recent_daily_closes(
                        stock_code, days=45, source="default", token=self.ts_token, return_volume=False
                    )
                    if isinstance(result, tuple) and len(result) >= 2:
                        dates, closes = result[:2]
                    else:
                        dates, closes = result, []
                    if not closes or len(closes) < 3:
                        return None
                    latest_price = float(closes[-1])
                    # 检测结果字典
                    detection_result = {
                        'stock_code': stock_code,
                        'current_price': latest_price,
                        'dates': dates,
                        'closes': closes,
                    }
                    # 1日线检测
                    if len(closes) >= 3:
                        ref_price = float(closes[-2])
                        prev_price = float(closes[-3])
                        crossed = latest_price >= ref_price
                        uptrend = ref_price >= prev_price
                        detection_result['ma1'] = {
                            'ref': ref_price,
                            'prev': prev_price,
                            'crossed': crossed,
                            'uptrend': uptrend
                        }
                    # 5日线检测
                    if len(closes) >= 7:
                        ma5_values = [float(closes[i]) for i in range(len(closes)-5, len(closes))]
                        ref_ma5 = sum(ma5_values) / len(ma5_values)
                        prev_ma5_values = [float(closes[i]) for i in range(len(closes)-10, len(closes)-5)]
                        prev_ma5 = sum(prev_ma5_values) / len(prev_ma5_values) if len(prev_ma5_values) >= 5 else ref_ma5
                        crossed = latest_price >= ref_ma5
                        uptrend = ref_ma5 >= prev_ma5
                        detection_result['ma5'] = {
                            'ref': ref_ma5,
                            'prev': prev_ma5,
                            'crossed': crossed,
                            'uptrend': uptrend
                        }
                    # 10日线检测
                    if len(closes) >= 12:
                        ma10_values = [float(closes[i]) for i in range(len(closes)-10, len(closes))]
                        ref_ma10 = sum(ma10_values) / len(ma10_values)
                        prev_ma10_values = [float(closes[i]) for i in range(len(closes)-20, len(closes)-10)]
                        prev_ma10 = sum(prev_ma10_values) / len(prev_ma10_values) if len(prev_ma10_values) >= 10 else ref_ma10
                        crossed = latest_price >= ref_ma10
                        uptrend = ref_ma10 >= prev_ma10
                        detection_result['ma10'] = {
                            'ref': ref_ma10,
                            'prev': prev_ma10,
                            'crossed': crossed,
                            'uptrend': uptrend
                        }
                    # 20日线检测
                    if len(closes) >= 22:
                        ma20_values = [float(closes[i]) for i in range(len(closes)-20, len(closes))]
                        ref_ma20 = sum(ma20_values) / len(ma20_values)
                        prev_ma20_values = [float(closes[i]) for i in range(len(closes)-40, len(closes)-20)]
                        prev_ma20 = sum(prev_ma20_values) / len(prev_ma20_values) if len(prev_ma20_values) >= 20 else ref_ma20
                        crossed = latest_price >= ref_ma20
                        uptrend = ref_ma20 >= prev_ma20
                        detection_result['ma20'] = {
                            'ref': ref_ma20,
                            'prev': prev_ma20,
                            'crossed': crossed,
                            'uptrend': uptrend
                        }
                    return detection_result
                except Exception as e:
                    print(f"均线检测失败: {e}")
                    return None
            def update_detection_ui(detection_result, stock_name, stock_code):
                """更新检测界面显示"""
                if not detection_result:
                    reset_detection_ui()
                    return
                # 更新基础信息
                ma_vars['stock_code_var'].set(stock_code)
                ma_vars['current_price_var'].set(f"{detection_result['current_price']:.2f}")
                # 更新1日线
                if 'ma1' in detection_result:
                    ma1 = detection_result['ma1']
                    ma_vars['ma1_reference_var'].set(f"{ma1['ref']:.2f}")
                    ma_vars['ma1_prev_var'].set(f"{ma1['prev']:.2f}")
                    cross_text = "已站上" if ma1['crossed'] else "未站上"
                    trend_text = "向上" if ma1['uptrend'] else "未向上"
                    ma_vars['ma1_status_var'].set(f"{cross_text}1日线,1日线{trend_text}")
                    if ma1['crossed']:
                        ma1_status_label.configure(foreground="red", font=("TkDefaultFont", 8, "bold"))
                    else:
                        ma1_status_label.configure(foreground="green", font=("TkDefaultFont", 8))
                    ma_vars['ma1_source_var'].set("数据来源: 默认")
                # 更新5日线
                if 'ma5' in detection_result:
                    ma5 = detection_result['ma5']
                    ma_vars['ma5_reference_var'].set(f"{ma5['ref']:.2f}")
                    ma_vars['ma5_prev_var'].set(f"{ma5['prev']:.2f}")
                    cross_text = "已站上" if ma5['crossed'] else "未站上"
                    trend_text = "向上" if ma5['uptrend'] else "未向上"
                    ma_vars['ma5_status_var'].set(f"{cross_text}5日线,5日线{trend_text}")
                    if ma5['crossed']:
                        ma5_status_label.configure(foreground="red", font=("TkDefaultFont", 8, "bold"))
                    else:
                        ma5_status_label.configure(foreground="green", font=("TkDefaultFont", 8))
                # 更新10日线
                if 'ma10' in detection_result:
                    ma10 = detection_result['ma10']
                    ma_vars['ma10_reference_var'].set(f"{ma10['ref']:.2f}")
                    ma_vars['ma10_prev_var'].set(f"{ma10['prev']:.2f}")
                    cross_text = "已站上" if ma10['crossed'] else "未站上"
                    trend_text = "向上" if ma10['uptrend'] else "未向上"
                    ma_vars['ma10_status_var'].set(f"{cross_text}10日线,10日线{trend_text}")
                    if ma10['crossed']:
                        ma10_status_label.configure(foreground="red", font=("TkDefaultFont", 8, "bold"))
                    else:
                        ma10_status_label.configure(foreground="green", font=("TkDefaultFont", 8))
                # 更新20日线
                if 'ma20' in detection_result:
                    ma20 = detection_result['ma20']
                    ma_vars['ma20_reference_var'].set(f"{ma20['ref']:.2f}")
                    ma_vars['ma20_prev_var'].set(f"{ma20['prev']:.2f}")
                    cross_text = "已站上" if ma20['crossed'] else "未站上"
                    trend_text = "向上" if ma20['uptrend'] else "未向上"
                    ma_vars['ma20_status_var'].set(f"{cross_text}20日线,20日线{trend_text}")
                    if ma20['crossed']:
                        ma20_status_label.configure(foreground="red", font=("TkDefaultFont", 8, "bold"))
                    else:
                        ma20_status_label.configure(foreground="green", font=("TkDefaultFont", 8))
                # 保存检测结果供后续使用
                _detection_results[stock_code] = detection_result
            def update_stock_links_and_analysis(stock_name):
                """异步更新股票链接和均线检测数据"""
                nonlocal _update_timer, _current_updating_stock
                if not stock_name:
                    reset_detection_ui()
                    # 重置新标签页
                    # 清理intro_tab中的所有组件(包括可能的网页嵌入组件)
                    for widget in intro_tab.winfo_children():
                        widget.destroy()
                    # 重新创建intro_text和搜索按钮框架
                    nonlocal intro_text
                    # 创建垂直布局:上方文本区域,下方搜索按钮区域
                    intro_content_frame = ttk.Frame(intro_tab)
                    intro_content_frame.pack(fill=tk.BOTH, expand=True)
                    intro_text = scrolledtext.ScrolledText(intro_content_frame, wrap=tk.WORD, font=("TkDefaultFont", 12))
                    intro_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                    intro_text.insert("1.0", "请选择股票记录以查看股票介绍")
                    intro_text.config(state=tk.DISABLED)
                    # 创建搜索按钮区域(初始隐藏)
                    search_button_frame = ttk.Frame(intro_content_frame)
                    search_button_frame.pack(fill=tk.X, padx=5, pady=5)
                    search_button_frame.pack_forget()  # 初始隐藏
                    change_text.config(state=tk.NORMAL)
                    change_text.delete("1.0", tk.END)
                    change_text.insert("1.0", "请选择股票记录以查看近日涨跌幅")
                    change_text.config(state=tk.DISABLED)
                    moneyflow_text.config(state=tk.NORMAL)
                    moneyflow_text.delete("1.0", tk.END)
                    moneyflow_text.insert("1.0", "请选择股票记录以查看大单分析")
                    moneyflow_text.config(state=tk.DISABLED)
                    for item in history_tree.get_children():
                        history_tree.delete(item)
                    return
                # 取消之前的更新任务
                if _update_timer:
                    self.root.after_cancel(_update_timer)
                    _update_timer = None
                # 立即更新链接(不需要网络请求,很快)
                stock_code = get_stock_code_by_name(stock_name)
                for label in link_labels:
                    url = build_link(label, stock_code, stock_name)
                    current_link_urls[label] = url
                    # 按钮始终保持可用状态
                    link_buttons[label].config(state=tk.NORMAL)
                # 更新均线仓位检测标签页
                if stock_code:
                    update_ma_position_detection(stock_name, stock_code)
                # 重置检测界面
                reset_detection_ui()
                ma_vars['stock_code_var'].set(stock_code or "--")
                ma_vars['ma1_status_var'].set("检测中...")
                ma_vars['ma5_status_var'].set("检测中...")
                ma_vars['ma10_status_var'].set("检测中...")
                ma_vars['ma20_status_var'].set("检测中...")
                if not stock_code:
                    ma_vars['ma1_status_var'].set("无法获取股票代码")
                    return
                # 标记当前正在更新的股票
                _current_updating_stock = stock_name
                # 在后台线程中执行检测和获取新标签页数据
                def fetch_detection():
                    try:
                        detection_result = perform_ma_detection(stock_name, stock_code)
                        # 获取股票介绍数据
                        intro_data = self._fetch_stock_intro(stock_code, stock_name)
                        # 获取大单分析数据(添加错误处理)
                        moneyflow_data = None
                        try:
                            if stock_code:
                                moneyflow_data = self._fetch_moneyflow_data(stock_code, stock_name)
                            else:
                                moneyflow_data = "无法获取股票代码,无法进行大单分析"
                        except Exception as e:
                            moneyflow_data = f"获取大单分析数据时发生错误: {e!s}"
                            print(f"大单分析错误 ({stock_name}, {stock_code}): {e}")
                        # 获取近日涨跌幅数据
                        change_data = None
                        try:
                            if stock_code:
                                change_data = self._fetch_recent_changes(stock_code, stock_name)
                            else:
                                change_data = "无法获取股票代码,无法获取近日涨跌幅"
                        except Exception as e:
                            change_data = f"获取近日涨跌幅数据时发生错误: {e!s}"
                        # 获取历史涨跌分析数据
                        history_data = None
                        try:
                            history_data = self._fetch_history_analysis(stock_name)
                        except Exception as e:
                            history_data = []
                            print(f"历史涨跌分析错误 ({stock_name}): {e}")
                        # 在主线程中更新UI
                        def update_ui():
                            nonlocal _current_updating_stock, intro_text, moneyflow_text, change_text, history_tree
                            # 检查是否还是当前股票(防止快速切换导致的数据错乱)
                            if _current_updating_stock != stock_name:
                                return
                            if detection_result:
                                update_detection_ui(detection_result, stock_name, stock_code)
                            else:
                                ma_vars['ma1_status_var'].set("检测失败")
                                ma_vars['ma5_status_var'].set("检测失败")
                                ma_vars['ma10_status_var'].set("检测失败")
                                ma_vars['ma20_status_var'].set("检测失败")
                            # 更新股票介绍标签页
                            # 检查是否是网页嵌入类型
                            if isinstance(intro_data, dict) and intro_data.get("type") == "web_embed":
                                # 清空intro_tab,创建网页嵌入界面
                                for widget in intro_tab.winfo_children():
                                    widget.destroy()
                                # 创建提示信息框架
                                info_frame = ttk.Frame(intro_tab, padding=20)
                                info_frame.pack(fill=tk.BOTH, expand=True)
                                stock_code_web = intro_data.get("stock_code", "")
                                stock_name_web = intro_data.get("stock_name", "")
                                # 显示提示信息
                                ttk.Label(info_frame, text="数据获取失败,正在加载网页介绍...",
                                         font=("TkDefaultFont", 12)).pack(pady=10)
                                # 创建按钮框架
                                button_frame = ttk.Frame(info_frame)
                                button_frame.pack(pady=20)
                                # 构建搜索URL
                                from urllib.parse import quote
                                search_term = f"{stock_name_web} {stock_code_web} 股票"
                                encoded_term = quote(search_term)
                                baidu_url = f"https://www.baidu.com/s?wd={encoded_term}"
                                sina_url = f"https://finance.sina.com.cn/realstock/company/{stock_code_web}/nc.shtml"
                                # 百度搜索按钮
                                def open_baidu():
                                    import webbrowser
                                    webbrowser.open(baidu_url)
                                def open_sina():
                                    import webbrowser
                                    webbrowser.open(sina_url)
                                ttk.Button(button_frame, text="打开百度搜索", command=open_baidu, width=20).pack(side=tk.LEFT, padx=10)
                                ttk.Button(button_frame, text="打开新浪财经", command=open_sina, width=20).pack(side=tk.LEFT, padx=10)
                                # 尝试使用tkinterhtml嵌入网页(如果可用)
                                try:
                                    import tkinterhtml
                                    # 创建HTML显示区域
                                    html_frame = ttk.Frame(intro_tab)
                                    html_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                                    # 创建HTML显示组件
                                    html_widget = tkinterhtml.HtmlFrame(html_frame, horizontal_scrollbar="auto")
                                    html_widget.pack(fill=tk.BOTH, expand=True)
                                    # 加载百度搜索页面(使用iframe)
                                    html_content = f"""
                                    <!DOCTYPE html>
                                    <html>
                                    <head>
                                        <meta charset="UTF-8">
                                        <title>{stock_name_web} - 股票介绍</title>
                                    </head>
                                    <body style="margin:0; padding:10px;">
                                        <h2>{stock_name_web} ({stock_code_web})</h2>
                                        <p>正在加载网页内容...</p>
                                        <iframe src="{baidu_url}" width="100%" height="600" frameborder="0"></iframe>
                                    </body>
                                    </html>
                                    """
                                    html_widget.set_content(html_content)
                                except ImportError:
                                    # 如果tkinterhtml不可用,尝试使用tkinterweb
                                    try:
                                        # 在后台线程中执行,避免阻塞UI,同时抑制所有错误
                                        def load_webpage_safely():
                                            # 设置环境变量禁用TkinterWeb的调试消息
                                            import os
                                            os.environ['TKINTERWEB_MESSAGES_ENABLED'] = '0'
                                            with suppress_tkinterweb_errors():
                                                try:
                                                    import tkinterweb
                                                    # 在主线程中创建UI组件
                                                    db_window.after(0, lambda: create_web_widget())
                                                    def create_web_widget():
                                                        with suppress_tkinterweb_errors():
                                                            try:
                                                                html_frame = ttk.Frame(intro_tab)
                                                                html_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                                                                html_widget = tkinterweb.HtmlFrame(html_frame, messages_enabled=False)
                                                                html_widget.pack(fill=tk.BOTH, expand=True)
                                                                # 在后台线程中加载网站,持续抑制错误
                                                                def load_site():
                                                                    with suppress_tkinterweb_errors():
                                                                        try:
                                                                            html_widget.load_website(baidu_url)
                                                                        except Exception:
                                                                            pass
                                                                threading.Thread(target=load_site, daemon=True).start()
                                                            except Exception:
                                                                pass
                                                except (ImportError, Exception):
                                                    pass
                                        threading.Thread(target=load_webpage_safely, daemon=True).start()
                                    except Exception:
                                        # 如果都不可用或出错,显示提示信息
                                        ttk.Label(info_frame,
                                                 text="提示:如需查看网页内容,请点击上方按钮在浏览器中打开",
                                                 font=("TkDefaultFont", 12),
                                                 foreground="gray").pack(pady=10)
                                except Exception:
                                    # 捕获所有其他异常,避免影响主程序
                                    try:
                                        # 尝试使用tkinterweb作为备选
                                        def load_webpage_safely2():
                                            # 设置环境变量禁用TkinterWeb的调试消息
                                            import os
                                            os.environ['TKINTERWEB_MESSAGES_ENABLED'] = '0'
                                            with suppress_tkinterweb_errors():
                                                try:
                                                    import tkinterweb
                                                    db_window.after(0, lambda: create_web_widget2())
                                                    def create_web_widget2():
                                                        with suppress_tkinterweb_errors():
                                                            try:
                                                                html_frame = ttk.Frame(intro_tab)
                                                                html_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                                                                html_widget = tkinterweb.HtmlFrame(html_frame, messages_enabled=False)
                                                                html_widget.pack(fill=tk.BOTH, expand=True)
                                                                def load_site2():
                                                                    with suppress_tkinterweb_errors():
                                                                        try:
                                                                            html_widget.load_website(baidu_url)
                                                                        except Exception:
                                                                            pass
                                                                threading.Thread(target=load_site2, daemon=True).start()
                                                            except Exception:
                                                                pass
                                                except Exception:
                                                    pass
                                        threading.Thread(target=load_webpage_safely2, daemon=True).start()
                                    except Exception:
                                        # 如果都不可用,显示提示信息
                                        ttk.Label(info_frame,
                                                 text="提示:如需查看网页内容,请点击上方按钮在浏览器中打开",
                                                 font=("TkDefaultFont", 12),
                                                 foreground="gray").pack(pady=10)
                            else:
                                # 正常显示文本内容
                                # 检查intro_text是否存在,如果不存在则重新创建
                                intro_text_exists = False
                                intro_content_frame = None
                                search_button_frame = None
                                # 查找现有的框架和组件
                                for widget in intro_tab.winfo_children():
                                    if isinstance(widget, ttk.Frame):
                                        # 检查是否是内容框架
                                        for child in widget.winfo_children():
                                            if isinstance(child, scrolledtext.ScrolledText):
                                                intro_text_exists = True
                                                intro_text = child
                                                intro_content_frame = widget
                                                # 查找搜索按钮框架
                                                for frame_child in widget.winfo_children():
                                                    if isinstance(frame_child, ttk.Frame) and frame_child != child:
                                                        search_button_frame = frame_child
                                                break
                                if not intro_text_exists:
                                    # 清空intro_tab,重新创建
                                    for widget in intro_tab.winfo_children():
                                        widget.destroy()
                                    # 创建垂直布局:上方文本区域,下方搜索按钮区域
                                    intro_content_frame = ttk.Frame(intro_tab)
                                    intro_content_frame.pack(fill=tk.BOTH, expand=True)
                                    intro_text = scrolledtext.ScrolledText(intro_content_frame, wrap=tk.WORD, font=("TkDefaultFont", 12))
                                    intro_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                                    # 创建搜索按钮区域
                                    search_button_frame = ttk.Frame(intro_content_frame)
                                    search_button_frame.pack(fill=tk.X, padx=5, pady=5)
                                    search_button_frame.pack_forget()  # 初始隐藏
                                intro_text.config(state=tk.NORMAL)
                                intro_text.delete("1.0", tk.END)
                                intro_text.insert("1.0", intro_data)
                                intro_text.config(state=tk.DISABLED)
                                # 检查内容是否有效(如果内容很少或包含错误信息,显示搜索按钮)
                                intro_data_str = str(intro_data) if intro_data else ""
                                has_valid_content = (
                                    len(intro_data_str) > 50 and
                                    "获取股票介绍失败" not in intro_data_str and
                                    "无法获取股票介绍信息" not in intro_data_str and
                                    "获取股票信息失败" not in intro_data_str
                                )
                                # 如果没有有效内容,显示搜索按钮
                                if not has_valid_content and search_button_frame:
                                    # 清空搜索按钮框架
                                    for widget in search_button_frame.winfo_children():
                                        widget.destroy()
                                    # 显示搜索按钮
                                    search_button_frame.pack(fill=tk.X, padx=5, pady=5)
                                    # 构建搜索URL
                                    from urllib.parse import quote
                                    search_term = f"{stock_name} {stock_code} 股票"
                                    encoded_term = quote(search_term)
                                    baidu_url = f"https://www.baidu.com/s?wd={encoded_term}"
                                    sina_url = f"https://finance.sina.com.cn/realstock/company/{stock_code}/nc.shtml" if stock_code else None
                                    # 百度搜索按钮
                                    def open_baidu_search():
                                        import webbrowser
                                        webbrowser.open(baidu_url)
                                    ttk.Label(search_button_frame, text="未获取到股票介绍信息,您可以:",
                                             font=("TkDefaultFont", 12)).pack(side=tk.LEFT, padx=(0, 10))
                                    ttk.Button(search_button_frame, text="百度搜索", command=open_baidu_search, width=15).pack(side=tk.LEFT, padx=5)
                                    if sina_url:
                                        def open_sina_search():
                                            import webbrowser
                                            webbrowser.open(sina_url)
                                        ttk.Button(search_button_frame, text="新浪财经", command=open_sina_search, width=15).pack(side=tk.LEFT, padx=5)
                                else:
                                    # 如果有有效内容,隐藏搜索按钮
                                    if search_button_frame:
                                        search_button_frame.pack_forget()
                            # 更新近日涨跌幅标签页
                            change_text.config(state=tk.NORMAL)
                            change_text.delete("1.0", tk.END)
                            change_text.insert("1.0", change_data)
                            change_text.config(state=tk.DISABLED)
                            # 更新大单分析标签页
                            moneyflow_text.config(state=tk.NORMAL)
                            moneyflow_text.delete("1.0", tk.END)
                            # 配置文本标签
                            moneyflow_text.tag_configure("red", foreground="red")
                            moneyflow_text.tag_configure("green", foreground="green")
                            moneyflow_text.tag_configure("bold_red", foreground="red", font=("TkDefaultFont", 12, "bold"))
                            moneyflow_text.tag_configure("bold_green", foreground="green", font=("TkDefaultFont", 12, "bold"))
                            if moneyflow_data:
                                # 检查是否是结构化数据
                                if isinstance(moneyflow_data, dict) and "header" in moneyflow_data and "days" in moneyflow_data:
                                    # 插入标题
                                    for line in moneyflow_data["header"]:
                                        moneyflow_text.insert(tk.END, line + "\n")
                                    # 插入每天的数据,应用颜色和加粗
                                    for day_data in moneyflow_data["days"]:
                                        date = day_data["date"]
                                        elg_net = day_data["elg_net"]
                                        lg_net = day_data["lg_net"]
                                        total_lg_net = day_data["total_lg_net"]  # 主力净额
                                        net_mf_amount = day_data["net_mf_amount"]
                                        # 插入日期
                                        moneyflow_text.insert(tk.END, f"\n日期: {date}\n")
                                        # 超大单:根据正负值显示红色或绿色
                                        elg_color = "red" if elg_net > 0 else "green" if elg_net < 0 else ""
                                        moneyflow_text.insert(tk.END, "  超大单: ")
                                        if elg_color:
                                            moneyflow_text.insert(tk.END, f"{elg_net:>,.2f}", elg_color)
                                        else:
                                            moneyflow_text.insert(tk.END, f"{elg_net:>,.2f}")
                                        moneyflow_text.insert(tk.END, " 万元\n")
                                        # 大单:根据正负值显示红色或绿色
                                        lg_color = "red" if lg_net > 0 else "green" if lg_net < 0 else ""
                                        moneyflow_text.insert(tk.END, "  大单: ")
                                        if lg_color:
                                            moneyflow_text.insert(tk.END, f"{lg_net:>,.2f}", lg_color)
                                        else:
                                            moneyflow_text.insert(tk.END, f"{lg_net:>,.2f}")
                                        moneyflow_text.insert(tk.END, " 万元\n")
                                        # 净额(主力净额):加粗显示,红色或绿色
                                        net_color = "red" if total_lg_net > 0 else "green" if total_lg_net < 0 else ""
                                        moneyflow_text.insert(tk.END, "  净额: ")
                                        if net_color:
                                            moneyflow_text.insert(tk.END, f"{total_lg_net:>,.2f}", f"bold_{net_color}")
                                        else:
                                            moneyflow_text.insert(tk.END, f"{total_lg_net:>,.2f}", "bold_red")
                                        moneyflow_text.insert(tk.END, " 万元\n")
                                        # 资金流向净流入额:根据正负值显示红色或绿色
                                        mf_color = "red" if net_mf_amount > 0 else "green" if net_mf_amount < 0 else ""
                                        moneyflow_text.insert(tk.END, "  资金流向净流入额: ")
                                        if mf_color:
                                            moneyflow_text.insert(tk.END, f"{net_mf_amount:>,.2f}", mf_color)
                                        else:
                                            moneyflow_text.insert(tk.END, f"{net_mf_amount:>,.2f}")
                                        moneyflow_text.insert(tk.END, " 万元\n")
                                else:
                                    # 兼容旧格式(字符串)
                                    moneyflow_str = str(moneyflow_data)
                                    moneyflow_text.insert("1.0", moneyflow_str)
                            else:
                                moneyflow_text.insert("1.0", "未获取到大单分析数据")
                            moneyflow_text.config(state=tk.DISABLED)
                            # 更新历史涨跌分析标签页
                            for item in history_tree.get_children():
                                history_tree.delete(item)
                            for row in history_data:
                                history_tree.insert("", tk.END, values=row)
                        if hasattr(self, "root") and self.root.winfo_exists():
                            self.root.after(0, update_ui)
                    except Exception as e:
                        def show_error(e=e):
                            nonlocal _current_updating_stock
                            if _current_updating_stock != stock_name:
                                return
                            ma_vars['ma1_status_var'].set(f"检测失败: {str(e)[:20]}")
                            ma_vars['ma5_status_var'].set("检测失败")
                            ma_vars['ma10_status_var'].set("检测失败")
                            ma_vars['ma20_status_var'].set("检测失败")
                        if hasattr(self, "root") and self.root.winfo_exists():
                            self.root.after(0, show_error)
                # 启动后台线程
                threading.Thread(target=fetch_detection, daemon=True).start()
            stock_data_cache = []
            current_stock_record = None
            # 保存当前查询的股票名称(即使查询不到结果也保存)
            current_query_stock_name = None
            def resolve_stock_for_record(record):
                """根据记录解析股票名称与代码"""
                logic_content = record.get('logic', '') or ''
                def try_get_code(name):
                    if not name:
                        return None
                    return get_stock_code_by_name(name)
                stock_name = (record.get('stock_name') or '').strip()
                if stock_name:
                    code = try_get_code(stock_name)
                    if code:
                        return stock_name, code
                if logic_content:
                    stocks, _ = extract_stock_names(logic_content)
                    for candidate in stocks:
                        code = try_get_code(candidate)
                        if code:
                            return candidate, code
                    match = re.search(r'\b\d{6}\b', logic_content)
                    if match:
                        code = match.group(0)
                        global STOCK_CODES_DICT
                        if STOCK_CODES_DICT is None:
                            load_stock_names()
                        name = STOCK_CODES_DICT.get(code, code)
                        return name, code
                return None, None
            reset_detection_ui()
            # 按钮框架
            stock_button_frame = ttk.Frame(stock_tab)
            stock_button_frame.pack(fill=tk.X)
            status_label = ttk.Label(stock_button_frame, text="", font=("TkDefaultFont", 11))
            status_label.pack(side=tk.LEFT, padx=10)
            def refresh_stock_data():
                """刷新股票数据(异步优化版本)"""
                nonlocal stock_data_cache, current_query_stock_name
                # 立即清空并显示加载状态
                for item in stock_tree.get_children():
                    stock_tree.delete(item)
                reset_detection_ui()
                status_label.config(text="正在查询数据...")
                start_date = start_date_var.get().strip() if start_date_var.get().strip() else None
                end_date = end_date_var.get().strip() if end_date_var.get().strip() else None
                stock_name = stock_name_var.get().strip() if stock_name_var.get().strip() else None
                logic_content = logic_content_var.get().strip() if logic_content_var.get().strip() else None
                # 保存当前查询的股票名称(无论是否查询到结果都保存)
                current_query_stock_name = stock_name
                def query_and_update():
                    """在后台线程中查询数据"""
                    nonlocal current_query_stock_name
                    try:
                        data = get_stock_logic_from_db(
                            start_date=start_date,
                            end_date=end_date,
                            stock_name=stock_name,
                            logic_content=logic_content
                        )
                        # 准备插入数据(批量处理)
                        insert_items = []
                        for item in data:
                            logic_preview = item.get('logic', '')
                            if len(logic_preview) > 50:
                                logic_preview = logic_preview[:50] + '...'
                            insert_items.append((
                                item.get('id', ''),
                                item.get('stock_name', ''),
                                logic_preview,
                                item.get('date', ''),
                                item.get('source', ''),
                                item.get('created_at', '')
                            ))
                        # 在主线程中更新UI
                        def update_ui():
                            nonlocal current_query_stock_name
                            # 清空现有数据
                            for item in stock_tree.get_children():
                                stock_tree.delete(item)
                            # 批量插入(减少UI更新次数)
                            for values in insert_items:
                                stock_tree.insert("", tk.END, values=values)
                            status_label.config(text=f"共查询到 {len(data)} 条记录")
                            # 如果输入了股票名称,无论是否查询到结果,都根据此股票名称更新右侧显示
                            # 使用保存的查询股票名称
                            query_stock_name = current_query_stock_name or stock_name
                            if query_stock_name:
                                stock_name_clean = query_stock_name.strip()
                                if data:
                                    # 如果查询到结果,查找匹配的股票记录
                                    matched_record = None
                                    for item in data:
                                        if item.get('stock_name', '').strip() == stock_name_clean:
                                            matched_record = item
                                            break
                                    # 如果找到匹配的记录,使用记录中的股票信息
                                    if matched_record:
                                        stock_name_resolved, stock_code_resolved = resolve_stock_for_record(matched_record)
                                        if stock_name_resolved:
                                            # 延迟一点执行,确保UI已更新
                                            def update_with_code(sn=stock_name_resolved, sc=stock_code_resolved):
                                                update_stock_links_and_analysis(sn)
                                                if sc:
                                                    update_ma_position_detection(sn, sc)
                                            self.root.after(100, update_with_code)
                                    else:
                                        # 如果查询到结果但没有匹配的记录,直接使用输入的股票名称
                                        # 尝试获取股票代码
                                        stock_code_resolved = get_stock_code_by_name(stock_name_clean)
                                        if stock_code_resolved:
                                            # 延迟一点执行,确保UI已更新
                                            def update_with_code(sn=stock_name_clean, sc=stock_code_resolved):
                                                update_stock_links_and_analysis(sn)
                                                if sc:
                                                    update_ma_position_detection(sn, sc)
                                            self.root.after(100, update_with_code)
                                        else:
                                            # 即使无法获取代码,也尝试更新(可能会显示错误信息)
                                            self.root.after(100, lambda sn=stock_name_clean: update_stock_links_and_analysis(sn))
                                else:
                                    # 如果查询不到结果,直接根据输入的股票名称更新右侧显示
                                    # 尝试获取股票代码
                                    stock_code_resolved = get_stock_code_by_name(stock_name_clean)
                                    if stock_code_resolved:
                                        # 延迟一点执行,确保UI已更新
                                        def update_with_code(sn=stock_name_clean, sc=stock_code_resolved):
                                            update_stock_links_and_analysis(sn)
                                            if sc:
                                                update_ma_position_detection(sn, sc)
                                        self.root.after(100, update_with_code)
                                    else:
                                        # 即使无法获取代码,也尝试更新(可能会显示错误信息)
                                        self.root.after(100, lambda sn=stock_name_clean: update_stock_links_and_analysis(sn))
                            # 自动选择第一条(仅在查询到结果时)
                            if data:
                                first_item = stock_tree.get_children()
                                if first_item:
                                    stock_tree.selection_set(first_item[0])
                                    stock_tree.focus(first_item[0])
                                    on_stock_select(None)
                        if hasattr(self, "root") and self.root.winfo_exists():
                            self.root.after(0, update_ui)
                    except Exception as e:
                        def show_error(e=e):
                            messagebox.showerror("错误", f"查询失败: {e}")
                            status_label.config(text="查询失败")
                        if hasattr(self, "root") and self.root.winfo_exists():
                            self.root.after(0, show_error)
                # 在后台线程中执行查询
                threading.Thread(target=query_and_update, daemon=True).start()
            # 防抖定时器
            _select_timer = None
            def on_stock_select(event):
                """股票数据选择事件(带防抖处理)"""
                nonlocal current_stock_record, _select_timer
                # 取消之前的定时器
                if _select_timer:
                    self.root.after_cancel(_select_timer)
                # 设置新的定时器(300ms防抖)
                def do_select():
                    selection = stock_tree.selection()
                    if selection:
                        item = stock_tree.item(selection[0])
                        values = item['values']
                        if len(values) >= 1:
                            logic_id = values[0]
                            record = None
                            for d in stock_data_cache:
                                if str(d.get('id')) == str(logic_id):
                                    record = d
                                    break
                            if record is None:
                                data = get_stock_logic_from_db()
                                for d in data:
                                    if str(d.get('id')) == str(logic_id):
                                        record = d
                                        break
                            if record:
                                # 立即更新逻辑文本(本地数据,很快)
                                logic_text.delete("1.0", tk.END)
                                logic_text.insert("1.0", record.get('logic', ''))
                                stock_name_resolved, stock_code_resolved = resolve_stock_for_record(record)
                                if stock_name_resolved:
                                    update_stock_links_and_analysis(stock_name_resolved)
                                    # 更新均线仓位检测标签页
                                    if stock_code_resolved:
                                        update_ma_position_detection(stock_name_resolved, stock_code_resolved)
                                else:
                                    reset_detection_ui("该记录缺少有效的股票名称/代码,无法生成链接和数据")
                            else:
                                reset_detection_ui("未找到匹配的股票记录")
                    else:
                        reset_detection_ui()
                _select_timer = self.root.after(300, do_select)
            stock_tree.bind("<<TreeviewSelect>>", on_stock_select)
            # 添加双击事件处理
            def on_stock_double_click_event(event):
                """双击股票记录事件"""
                selection = stock_tree.selection()
                if selection:
                    item = stock_tree.item(selection[0])
                    values = item['values']
                    if len(values) >= 2:
                        selected_stock_name = values[1]  # 股票名称在第二列
                        if selected_stock_name:
                            # 使用窗口属性中的回调函数
                            callback = getattr(db_window, '_on_stock_double_click', None)
                            if callback:
                                callback(selected_stock_name)
            stock_tree.bind("<Double-1>", on_stock_double_click_event)
            ttk.Button(query_frame, text="查询", command=refresh_stock_data).pack(side=tk.LEFT, padx=(10, 0))
            # 一键导入按钮 - 导入选中的股票到开新仓流程的下拉框
            def batch_import_to_new_position():
                """批量导入选中的股票到开新仓流程的下拉框"""
                selections = stock_tree.selection()
                if not selections:
                    messagebox.showwarning("提示", "请先选择要导入的股票记录(可多选)", parent=db_window)
                    return
                imported_stocks = []
                for item_id in selections:
                    item = stock_tree.item(item_id)
                    values = item['values']
                    if len(values) >= 2:
                        stock_name = values[1]  # 股票名称在第二列
                        if stock_name and stock_name.strip():
                            imported_stocks.append(stock_name.strip())
                if imported_stocks:
                    # 去重
                    imported_stocks = list(dict.fromkeys(imported_stocks))
                    # 尝试找到开新仓流程的股票下拉框并导入
                    try:
                        # 查找主窗口中的开新仓对话框
                        found = False
                        for widget in self.root.winfo_children():
                            if isinstance(widget, tk.Toplevel):
                                try:
                                    title = widget.title()
                                    if "新仓" in title:
                                        # 递归查找股票名称输入框
                                        def find_stock_combo(parent):
                                            for child in parent.winfo_children():
                                                if isinstance(child, ttk.Combobox):
                                                    # 检查是否是股票名称输入框(通过父框架的标签判断)
                                                    try:
                                                        parent_widget = child.master
                                                        if isinstance(parent_widget, ttk.Frame):
                                                            # 查找父框架的标签或文本
                                                            for sibling in parent_widget.winfo_children():
                                                                if isinstance(sibling, ttk.Label):
                                                                    label_text = sibling.cget("text")
                                                                    if "股票名称" in label_text or "股票" in label_text:
                                                                        return child
                                                    except:
                                                        pass
                                                # 递归查找子组件
                                                result = find_stock_combo(child)
                                                if result:
                                                    return result
                                            return None
                                        stock_combo = find_stock_combo(widget)
                                        if stock_combo:
                                            # 找到股票下拉框,添加股票
                                            current_values = list(stock_combo['values'])
                                            for stock in imported_stocks:
                                                if stock not in current_values:
                                                    current_values.append(stock)
                                            # 限制为50个
                                            if len(current_values) > 50:
                                                current_values = current_values[-50:]
                                            stock_combo['values'] = current_values
                                            messagebox.showinfo("成功", f"已导入 {len(imported_stocks)} 只股票到开新仓流程", parent=db_window)
                                            found = True
                                            break
                                except Exception as e:
                                    print(f"查找开新仓对话框失败: {e}")
                                    continue
                        if not found:
                            # 如果没找到开新仓对话框,提示用户先打开
                            messagebox.showinfo("提示", f"已准备导入 {len(imported_stocks)} 只股票\n请先打开开新仓流程界面,然后再次点击导入按钮", parent=db_window)
                    except Exception as e:
                        messagebox.showerror("错误", f"导入失败: {e}", parent=db_window)
                else:
                    messagebox.showwarning("提示", "选中的记录中没有有效的股票名称", parent=db_window)
            ttk.Button(stock_button_frame, text="一键导入到开新仓", command=batch_import_to_new_position, width=18).pack(side=tk.LEFT, padx=5)
            ttk.Button(stock_button_frame, text="刷新", command=refresh_stock_data).pack(side=tk.LEFT, padx=5)
            ttk.Button(stock_button_frame, text="关闭", command=db_window.destroy).pack(side=tk.RIGHT, padx=5)
            # 初始加载股票数据
            refresh_stock_data()
            # ==================== 资讯数据表标签页 ====================
            news_tab = ttk.Frame(main_notebook)
            main_notebook.add(news_tab, text="资讯数据表")
            # 查询条件框架
            news_query_frame = ttk.LabelFrame(news_tab, text="查询条件", padding=10)
            news_query_frame.pack(fill=tk.X, pady=(0, 10))
            name_frame = ttk.Frame(news_query_frame)
            name_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(name_frame, text="标签页名称:").pack(side=tk.LEFT, padx=5)
            tab_name_var = tk.StringVar()
            tab_name_entry = ttk.Entry(name_frame, textvariable=tab_name_var, width=30)
            tab_name_entry.pack(side=tk.LEFT, padx=5)
            # 内容查询框
            content_query_frame = ttk.Frame(news_query_frame)
            content_query_frame.pack(fill=tk.X, pady=(5, 0))
            ttk.Label(content_query_frame, text="内容查询:").pack(side=tk.LEFT, padx=5)
            content_query_var = tk.StringVar()
            content_query_entry = ttk.Entry(content_query_frame, textvariable=content_query_var, width=40)
            content_query_entry.pack(side=tk.LEFT, padx=5)
            def search_content():
                """搜索资讯内容"""
                search_text = content_query_var.get().strip()
                if not search_text:
                    messagebox.showwarning("警告", "请输入要查询的内容")
                    return
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id, tab_name, content, created_at, updated_at
                        FROM news_info
                        WHERE content LIKE ?
                        ORDER BY created_at DESC
                    ''', (f'%{search_text}%',))
                    rows = cursor.fetchall()
                    conn.close()
                    if not rows:
                        messagebox.showinfo("提示", f"未找到包含 '{search_text}' 的资讯")
                        return
                    # 显示搜索结果弹出框
                    show_content_search_results(search_text, rows)
                except Exception as e:
                    messagebox.showerror("错误", f"查询失败: {e}")
            # 绑定回车键
            content_query_entry.bind('<Return>', lambda e: search_content())
            ttk.Button(content_query_frame, text="搜索内容", command=search_content, width=12).pack(side=tk.LEFT, padx=5)
            # 词云分析按钮
            def show_wordcloud_analysis():
                """词云分析功能:对选中的多条资讯进行股票词云分析"""
                selection = news_tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择至少一条资讯", parent=db_window)
                    return
                try:
                    # 获取选中的资讯内容
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    selected_contents = []
                    selected_news_ids = []
                    for item_id in selection:
                        item = news_tree.item(item_id)
                        news_id = item['values'][0]
                        cursor.execute('SELECT id, tab_name, content FROM news_info WHERE id = ?', (news_id,))
                        row = cursor.fetchone()
                        if row:
                            news_id, _tab_name, content = row
                            selected_contents.append(content or "")
                            selected_news_ids.append(news_id)
                    conn.close()
                    if not selected_contents:
                        messagebox.showwarning("警告", "选中的资讯没有内容", parent=db_window)
                        return
                    # 合并所有内容
                    merged_content = "\n".join(selected_contents)
                    # 提取股票名称
                    stock_names, _ = extract_stock_names(merged_content)
                    if not stock_names:
                        messagebox.showinfo("提示", "未识别出股票名称", parent=db_window)
                        return
                    # 统计词频
                    stock_counter = Counter(stock_names)
                    # 创建词云分析窗口
                    wordcloud_window = self._toplevel(db_window)
                    wordcloud_window.title(f"股票词云分析 - {len(selection)}条资讯")
                    wordcloud_window.geometry("1400x800")
                    wordcloud_window.transient(db_window)
                    # 主框架(词云占满整个窗口)
                    main_frame = ttk.Frame(wordcloud_window)
                    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                    # 工具栏
                    toolbar_frame = ttk.Frame(main_frame)
                    toolbar_frame.pack(fill=tk.X, pady=(0, 10))
                    def save_wordcloud():
                        """保存词云图片"""
                        try:
                            filename = filedialog.asksaveasfilename(
                                defaultextension=".png",
                                filetypes=[("PNG图片", "*.png"), ("所有文件", "*.*")],
                                initialfile=f"股票词云_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                            )
                            if filename and hasattr(wordcloud_window, '_wordcloud_image'):
                                wordcloud_window._wordcloud_image.save(filename)
                                messagebox.showinfo("成功", f"已保存到: {filename}", parent=wordcloud_window)
                        except Exception as e:
                            messagebox.showerror("错误", f"保存失败: {e}", parent=wordcloud_window)
                    def screenshot_wordcloud():
                        """截图词云区域"""
                        try:
                            filename = filedialog.asksaveasfilename(
                                defaultextension=".png",
                                filetypes=[("PNG图片", "*.png"), ("所有文件", "*.*")],
                                initialfile=f"词云截图_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                            )
                            if filename and hasattr(wordcloud_window, '_wordcloud_canvas'):
                                # 获取Canvas的截图
                                canvas = wordcloud_window._wordcloud_canvas
                                x = canvas.winfo_rootx()
                                y = canvas.winfo_rooty()
                                width = canvas.winfo_width()
                                height = canvas.winfo_height()
                                from PIL import ImageGrab
                                screenshot = ImageGrab.grab(bbox=(x, y, x+width, y+height))
                                screenshot.save(filename)
                                messagebox.showinfo("成功", f"已保存到: {filename}", parent=wordcloud_window)
                        except Exception as e:
                            messagebox.showerror("错误", f"截图失败: {e}", parent=wordcloud_window)
                    ttk.Button(toolbar_frame, text="保存词云", command=save_wordcloud, width=12).pack(side=tk.LEFT, padx=5)
                    ttk.Button(toolbar_frame, text="截图", command=screenshot_wordcloud, width=12).pack(side=tk.LEFT, padx=5)
                    # 照片墙按钮
                    def show_photo_wall():
                        """显示照片墙:将股票按频次排序,以卡片形式显示"""
                        try:
                            # 创建照片墙窗口
                            photo_wall_window = self._toplevel(wordcloud_window)
                            photo_wall_window.title(f"股票照片墙 - {len(selection)}条资讯")
                            photo_wall_window.geometry("1600x900")
                            photo_wall_window.transient(wordcloud_window)
                            # 主框架
                            main_wall_frame = ttk.Frame(photo_wall_window)
                            main_wall_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                            # 工具栏
                            wall_toolbar = ttk.Frame(main_wall_frame)
                            wall_toolbar.pack(fill=tk.X, pady=(0, 10))
                            ttk.Label(wall_toolbar, text="照片墙说明:卡片字体根据频次变化,背景色根据板块,有游资的股票名称显示为红色,双击查看详情",
                                     font=("TkDefaultFont", 11), foreground="gray").pack(side=tk.LEFT, padx=5)
                            # 截图按钮
                            def screenshot_photo_wall():
                                """截取照片墙前3页为长图"""
                                try:
                                    # 保存当前滚动位置
                                    scroll_y = wall_canvas.canvasy(0)
                                    # 获取窗口和Canvas的尺寸
                                    photo_wall_window.winfo_width()
                                    window_height = photo_wall_window.winfo_height()
                                    # 计算3页的高度(每页高度 = 窗口可见高度)
                                    pages = 3
                                    page_height = window_height - 100  # 减去工具栏等高度
                                    total_height = page_height * pages
                                    # 获取实际内容高度
                                    actual_content_height = wall_inner_frame.winfo_height()
                                    # 计算要截取的高度(不超过实际内容高度)
                                    screenshot_height = min(total_height, actual_content_height)
                                    # 确保从顶部开始
                                    wall_canvas.yview_moveto(0)
                                    photo_wall_window.update()
                                    photo_wall_window.update_idletasks()
                                    # 使用PIL截图
                                    import time

                                    from PIL import ImageGrab
                                    # 等待界面更新
                                    time.sleep(0.3)
                                    # 获取窗口在屏幕上的位置
                                    photo_wall_window.update_idletasks()
                                    window_x = photo_wall_window.winfo_rootx()
                                    window_y = photo_wall_window.winfo_rooty()
                                    # 计算Canvas在屏幕上的位置
                                    # 需要加上窗口边框、标题栏、工具栏等的高度
                                    title_bar_height = photo_wall_window.winfo_rooty() - photo_wall_window.winfo_y()
                                    toolbar_height = wall_toolbar.winfo_height()
                                    # Canvas在窗口中的相对位置
                                    canvas_rel_x = scroll_frame.winfo_x() + main_wall_frame.winfo_x()
                                    canvas_rel_y = scroll_frame.winfo_y() + main_wall_frame.winfo_y()
                                    # Canvas在屏幕上的绝对位置
                                    canvas_screen_x = window_x + canvas_rel_x
                                    canvas_screen_y = window_y + title_bar_height + toolbar_height + canvas_rel_y
                                    canvas_width = wall_canvas.winfo_width()
                                    # 如果内容高度小于3页,使用实际内容高度
                                    if actual_content_height < total_height:
                                        screenshot_height = actual_content_height
                                    # 分页截图并拼接
                                    images = []
                                    scroll_position = 0
                                    page_count = 0
                                    while scroll_position < screenshot_height and page_count < pages:
                                        # 滚动到当前位置
                                        if actual_content_height > 0:
                                            wall_canvas.yview_moveto(scroll_position / actual_content_height)
                                        photo_wall_window.update()
                                        photo_wall_window.update_idletasks()
                                        time.sleep(0.2)  # 等待滚动完成
                                        # 计算当前页要截取的高度
                                        current_page_height = min(page_height, screenshot_height - scroll_position)
                                        # 截图当前可见区域
                                        current_region = (
                                            canvas_screen_x,
                                            canvas_screen_y,
                                            canvas_screen_x + canvas_width,
                                            canvas_screen_y + current_page_height
                                        )
                                        img = ImageGrab.grab(bbox=current_region)
                                        if img:
                                            images.append(img)
                                        scroll_position += page_height
                                        page_count += 1
                                    # 拼接所有图片
                                    if images:
                                        # 计算总高度
                                        total_img_height = sum(img.height for img in images)
                                        max_width = max(img.width for img in images)
                                        # 创建长图
                                        long_image = Image.new('RGB', (max_width, total_img_height), 'white')
                                        y_offset = 0
                                        for img in images:
                                            long_image.paste(img, (0, y_offset))
                                            y_offset += img.height
                                        # 保存截图
                                        from datetime import datetime
                                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                        screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Screenshots")
                                        os.makedirs(screenshot_dir, exist_ok=True)
                                        screenshot_path = os.path.join(screenshot_dir, f"照片墙截图_{timestamp}.png")
                                        long_image.save(screenshot_path, 'PNG')
                                        # 恢复滚动位置
                                        if actual_content_height > 0:
                                            wall_canvas.yview_moveto(scroll_y / actual_content_height)
                                        messagebox.showinfo("成功", f"截图已保存:\n{screenshot_path}\n\n共截取 {len(images)} 页", parent=photo_wall_window)
                                    else:
                                        messagebox.showwarning("警告", "未能截取到图片内容", parent=photo_wall_window)
                                except Exception as e:
                                    messagebox.showerror("错误", f"截图失败:{e}", parent=photo_wall_window)
                                    import traceback
                                    traceback.print_exc()
                                    # 尝试恢复滚动位置
                                    try:
                                        if actual_content_height > 0:
                                            wall_canvas.yview_moveto(scroll_y / actual_content_height)
                                    except:
                                        pass
                            ttk.Button(wall_toolbar, text="📷 截图前3页", command=screenshot_photo_wall, width=15).pack(side=tk.RIGHT, padx=5)
                            # 滚动框架
                            scroll_frame = ttk.Frame(main_wall_frame)
                            scroll_frame.pack(fill=tk.BOTH, expand=True)
                            # 创建Canvas和滚动条
                            wall_canvas = tk.Canvas(scroll_frame, bg="white")
                            wall_scrollbar = ttk.Scrollbar(scroll_frame, orient=tk.VERTICAL, command=wall_canvas.yview)
                            wall_inner_frame = ttk.Frame(wall_canvas)
                            wall_inner_frame.bind(
                                "<Configure>",
                                lambda e: wall_canvas.configure(scrollregion=wall_canvas.bbox("all"))
                            )
                            wall_canvas.create_window((0, 0), window=wall_inner_frame, anchor="nw")
                            wall_canvas.configure(yscrollcommand=wall_scrollbar.set)
                            wall_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                            wall_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                            # 获取板块颜色映射
                            default_main_sectors = ["新能源", "人工智能", "芯片", "医药", "消费", "金融", "地产", "基建"]
                            main_sectors = self.ai_config_manager.config.get("main_sectors", default_main_sectors.copy()) if hasattr(self, 'ai_config_manager') else default_main_sectors
                            # 板块颜色映射
                            sector_colors = {
                                "新能源": "#90EE90", "人工智能": "#FF69B4", "芯片": "#87CEEB",
                                "医药": "#FFB6C1", "消费": "#FFD700", "金融": "#4682B4",
                                "地产": "#DDA0DD", "基建": "#20B2AA"
                            }
                            # 根据股票名称推断板块
                            def get_stock_sector(stock_name):
                                """根据股票名称推断板块"""
                                for sector in main_sectors:
                                    if sector in stock_name:
                                        return sector
                                return None
                            # 游资席位关键词列表(更完整)
                            speculator_keywords = [
                                '章盟主', '章建平', '中信证券杭州延安路', '国泰君安上海江苏路',
                                '赵老哥', '赵强', '银河证券绍兴营业部',
                                '徐翔', '宁波涨停板敢死队',
                                '陈小群', '小群', '小群哥', '群哥',
                                '流沙河', '喻悌奇',
                                '炒股养家', '林广昌', '华鑫证券上海宛平南路',
                                '佛山无影脚', '廖国沛', '光大证券佛山绿景路',
                                '上海溧阳路', '孙哥', '孙煜',
                                '作手新一', '国泰君安南京太平南路',
                                '小鳄鱼', '方新侠',
                                '呼家楼', '呼家楼营业部',
                                '宁波桑田路', '桑田路', '宁波桑田路营业部',
                                '消闲派', '消闲', '消闲哥',
                                '车库哥', '车库',
                                '营业部', '席位', '游资', '龙虎榜', '机构席位', '买入', '卖出'
                            ]
                            # 游资梯队、热度、风格信息(根据用户提供的资料)
                            # 游资关键词到游资名称的映射(用于查找游资信息)
                            speculator_keyword_map = {
                                '章盟主': '章盟主', '章建平': '章盟主', '中信证券杭州延安路': '章盟主', '国泰君安上海江苏路': '章盟主',
                                '赵老哥': '赵老哥', '赵强': '赵老哥', '银河证券绍兴营业部': '赵老哥',
                                '陈小群': '陈小群', '小群': '陈小群', '小群哥': '陈小群', '群哥': '陈小群',
                                '作手新一': '作手新一', '国泰君安南京太平南路': '作手新一',
                                '方新侠': '方新侠',
                                '呼家楼': '呼家楼', '呼家楼营业部': '呼家楼',
                                '宁波桑田路': '宁波桑田路', '桑田路': '宁波桑田路', '宁波桑田路营业部': '宁波桑田路',
                                '消闲派': '消闲派', '消闲': '消闲派', '消闲哥': '消闲派',
                                '炒股养家': '炒股养家', '林广昌': '炒股养家', '华鑫证券上海宛平南路': '炒股养家',
                                '车库哥': '车库哥', '车库': '车库哥',
                                '上海溧阳路': '上海溧阳路孙哥', '孙哥': '上海溧阳路孙哥', '孙煜': '上海溧阳路孙哥',
                                '佛山无影脚': '佛山无影脚', '廖国沛': '佛山无影脚', '光大证券佛山绿景路': '佛山无影脚',
                                '小鳄鱼': '小鳄鱼'
                            }
                            # 获取股票涨跌幅
                            def get_stock_daily_change(stock_name):
                                """获取股票当天涨跌幅"""
                                try:
                                    stock_code = get_stock_code_by_name(stock_name)
                                    if not stock_code:
                                        return None
                                    stock_data = ak.stock_zh_a_spot_em()
                                    stock_row = stock_data[stock_data['代码'] == stock_code]
                                    if not stock_row.empty:
                                        change_pct = float(stock_row.iloc[0]['涨跌幅'])
                                        return change_pct
                                    return None
                                except Exception:
                                    return None
                            # 获取股票逻辑内容(包含游资席位标注)
                            def get_stock_logic_content(stock_name):
                                """获取股票的逻辑内容,并标注游资席位"""
                                try:
                                    conn = sqlite3.connect(DB_PATH)
                                    cursor = conn.cursor()
                                    all_logic_texts = []
                                    has_speculator = False
                                    for news_id in selected_news_ids:
                                        cursor.execute('SELECT content FROM news_info WHERE id = ?', (news_id,))
                                        row = cursor.fetchone()
                                        if row:
                                            content = row[0] or ""
                                            # 提取包含该股票的段落
                                            lines = content.split('\n')
                                            stock_logic = []
                                            for i, line in enumerate(lines):
                                                if stock_name in line:
                                                    # 包含该行的前后几行作为上下文
                                                    start = max(0, i - 2)
                                                    end = min(len(lines), i + 10)
                                                    stock_logic.extend(lines[start:end])
                                                    break
                                            if stock_logic:
                                                # 检查这段逻辑是否包含游资席位
                                                logic_text = "\n".join(stock_logic)
                                                for keyword in speculator_keywords:
                                                    if keyword in logic_text:
                                                        has_speculator = True
                                                        break
                                                all_logic_texts.append(logic_text)
                                    conn.close()
                                    result_text = "\n\n---\n\n".join(all_logic_texts) if all_logic_texts else "未找到逻辑信息"
                                    return result_text, has_speculator
                                except Exception as e:
                                    return f"获取逻辑失败: {e}", False
                            # 按频次排序股票(确保所有股票都被包含)
                            sorted_stocks = sorted(stock_counter.items(), key=lambda x: x[1], reverse=True)
                            # 计算最大频次(用于字体大小和卡片大小计算)
                            max_count = max(stock_counter.values()) if stock_counter else 1
                            # 确保所有股票都被处理(调试信息)
                            print(f"照片墙:共 {len(sorted_stocks)} 只股票待显示")
                            # 批量加载配置
                            batch_size = 12  # 每批加载12个卡片
                            loaded_count = [0]  # 使用列表以便在嵌套函数中修改
                            # 照片墙容器(使用grid布局,每行5列,自动换行)
                            photo_wall_container = tk.Frame(wall_inner_frame, bg="white")
                            photo_wall_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                            # 每行显示的卡片数量(5列)
                            cards_per_row = 5
                            # 配置grid列权重,使列均匀分布
                            for i in range(cards_per_row):
                                photo_wall_container.columnconfigure(i, weight=1, uniform="card")
                            # 快速检查是否有游资(只检查股票相关逻辑内容,返回具体游资名字)
                            def quick_check_speculator(stock_name):
                                """快速检查股票是否有游资,返回游资名字列表或'游资'字符串
                                只检查股票相关的逻辑段落,而不是整个资讯内容"""
                                try:
                                    conn = sqlite3.connect(DB_PATH)
                                    cursor = conn.cursor()
                                    found_speculators = set()
                                    has_generic_speculator = False
                                    # 过滤掉通用关键词,只保留具体的游资关键词
                                    specific_keywords = [kw for kw in speculator_keywords if kw in speculator_keyword_map]
                                    for news_id in selected_news_ids:
                                        cursor.execute('SELECT content FROM news_info WHERE id = ?', (news_id,))
                                        row = cursor.fetchone()
                                        if row:
                                            content = row[0] or ""
                                            # 提取包含该股票的段落(与get_stock_logic_content逻辑一致)
                                            lines = content.split('\n')
                                            stock_logic = []
                                            for i, line in enumerate(lines):
                                                if stock_name in line:
                                                    # 包含该行的前后几行作为上下文
                                                    start = max(0, i - 2)
                                                    end = min(len(lines), i + 10)
                                                    stock_logic.extend(lines[start:end])
                                                    break
                                            if stock_logic:
                                                # 只在这段股票相关的逻辑中检查游资
                                                logic_text = "\n".join(stock_logic)
                                                # 先检查是否有具体游资名
                                                for keyword in specific_keywords:
                                                    if keyword in logic_text:
                                                        # 通过映射找到具体的游资名字
                                                        speculator_name = speculator_keyword_map.get(keyword)
                                                        if speculator_name:
                                                            found_speculators.add(speculator_name)
                                                # 检查是否有"游资"两字(且没有找到具体游资名)
                                                if '游资' in logic_text and not found_speculators:
                                                    has_generic_speculator = True
                                    conn.close()
                                    # 如果有具体游资名,返回具体名称列表
                                    if found_speculators:
                                        return list(found_speculators)
                                    # 如果只有"游资"两字,返回['游资']
                                    elif has_generic_speculator:
                                        return ['游资']
                                    else:
                                        return None
                                except Exception:
                                    return None
                            # 检测均线(1日、5日、10日、20日)
                            def check_moving_averages(stock_name):
                                """检测股票的1日、5日、10日、20日均线,返回检测结果"""
                                try:
                                    stock_code = get_stock_code_by_name(stock_name)
                                    if not stock_code:
                                        return {'ma1': False, 'ma5': False, 'ma10': False, 'ma20': False}
                                    # 获取历史数据(至少需要20日)
                                    hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq", start_date="")
                                    if hist_data.empty or len(hist_data) < 20:
                                        return {'ma1': False, 'ma5': False, 'ma10': False, 'ma20': False}
                                    # 取最近20日数据
                                    recent_data = hist_data.tail(20)
                                    close_prices = recent_data['收盘'].values
                                    current_price = close_prices[-1]
                                    # 计算均线
                                    ma1 = close_prices[-1]  # 1日均线就是当前价格
                                    ma5 = sum(close_prices[-5:]) / 5 if len(close_prices) >= 5 else current_price
                                    ma10 = sum(close_prices[-10:]) / 10 if len(close_prices) >= 10 else current_price
                                    ma20 = sum(close_prices[-20:]) / 20 if len(close_prices) >= 20 else current_price
                                    # 检测:当前价格是否在均线之上(通过=红色,未通过=绿色)
                                    # 通过条件:当前价格 >= 均线
                                    return {
                                        'ma1': current_price >= ma1,  # 1日均线总是通过
                                        'ma5': current_price >= ma5,
                                        'ma10': current_price >= ma10,
                                        'ma20': current_price >= ma20
                                    }
                                except Exception:
                                    return {'ma1': False, 'ma5': False, 'ma10': False, 'ma20': False}
                            # 创建单个卡片的函数
                            def create_stock_card(parent, stock, count, sector, bg_color, font_size, change_pct, speculator_names, ma_results):
                                """创建单个股票卡片"""
                                # 卡片容器(带边框和背景色,根据文字大小自适应)
                                card_frame = tk.Frame(parent, bg=bg_color, relief=tk.FLAT, bd=1, highlightthickness=1, highlightbackground="#D0D0D0")
                                # 卡片内容框架(带内边距)
                                card_content = tk.Frame(card_frame, bg=bg_color)
                                card_content.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
                                # 顶部区域:股票名称、涨跌幅
                                top_frame = tk.Frame(card_content, bg=bg_color)
                                top_frame.pack(fill=tk.X, pady=(0, 8))
                                # 股票名称(仅在游资情况下红色加粗,否则黑色加粗)
                                has_speculator = speculator_names is not None and len(speculator_names) > 0
                                stock_name_label = tk.Label(
                                    top_frame,
                                    text=stock,
                                    font=("TkDefaultFont", font_size, "bold"),
                                    bg=bg_color,
                                    fg="red" if has_speculator else "black",
                                    anchor="w",
                                    wraplength=200  # 允许换行
                                )
                                stock_name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
                                # 涨跌幅显示
                                if change_pct is not None:
                                    change_color = "red" if change_pct >= 0 else "green"
                                    change_text = f"{change_pct:+.2f}%"
                                    change_label = tk.Label(
                                        top_frame,
                                        text=change_text,
                                        font=("TkDefaultFont", 11, "bold"),
                                        bg=bg_color,
                                        fg=change_color
                                    )
                                    change_label.pack(side=tk.RIGHT, padx=(5, 0))
                                # 信息行:频次和板块
                                info_frame = tk.Frame(card_content, bg=bg_color)
                                info_frame.pack(fill=tk.X, pady=(8, 0))
                                count_label = tk.Label(
                                    info_frame,
                                    text=f"{count}次",
                                    font=("TkDefaultFont", 8),
                                    bg=bg_color,
                                    fg="#666666"
                                )
                                count_label.pack(side=tk.LEFT)
                                if sector:
                                    sector_label = tk.Label(
                                        info_frame,
                                        text=sector,
                                        font=("TkDefaultFont", 8),
                                        bg=bg_color,
                                        fg="#333333"
                                    )
                                    sector_label.pack(side=tk.LEFT, padx=(10, 0))
                                # 游资标注(显示具体游资名字)
                                if has_speculator and speculator_names:
                                    speculator_text = "、".join(speculator_names[:3])  # 最多显示3个游资名字
                                    if len(speculator_names) > 3:
                                        speculator_text += "..."
                                    speculator_hint = tk.Label(
                                        card_content,
                                        text=f"【{speculator_text}】",
                                        font=("TkDefaultFont", 8, "bold"),
                                        bg=bg_color,
                                        fg="#FF6600",
                                        wraplength=250
                                    )
                                    speculator_hint.pack(side=tk.TOP, pady=(8, 0))
                                # 均线检测结果显示(1日、5日、10日、20日)
                                if ma_results:
                                    ma_frame = tk.Frame(card_content, bg=bg_color)
                                    ma_frame.pack(fill=tk.X, pady=(8, 0))
                                    ma_labels = []
                                    ma_periods = [('ma1', '1日'), ('ma5', '5日'), ('ma10', '10日'), ('ma20', '20日')]
                                    for ma_key, ma_name in ma_periods:
                                        passed = ma_results.get(ma_key, False)
                                        color = "red" if passed else "green"
                                        ma_label = tk.Label(
                                            ma_frame,
                                            text=ma_name,
                                            font=("TkDefaultFont", 7, "bold"),
                                            bg=color,
                                            fg="white",
                                            padx=4,
                                            pady=2
                                        )
                                        ma_label.pack(side=tk.LEFT, padx=2)
                                        ma_labels.append(ma_label)
                                # 提示文本
                                hint_label = tk.Label(
                                    card_content,
                                    text="双击查看详情",
                                    font=("TkDefaultFont", 7),
                                    bg=bg_color,
                                    fg="#999999"
                                )
                                hint_label.pack(side=tk.BOTTOM, pady=(8, 0))
                                return card_frame
                            # 批量加载函数(优化:不获取涨跌幅,延迟加载)
                            def load_batch(start_idx):
                                """批量加载卡片"""
                                end_idx = min(start_idx + batch_size, len(sorted_stocks))
                                for idx in range(start_idx, end_idx):
                                    try:
                                        stock, count = sorted_stocks[idx]
                                        # 计算字体大小(根据频次,最小12,最大20)
                                        font_size = int(12 + (count / max_count) * 8)
                                        font_size = max(12, min(20, font_size))
                                        # 获取板块和颜色
                                        sector = get_stock_sector(stock)
                                        bg_color = sector_colors.get(sector, "#F5F5F5") if sector else "#F5F5F5"
                                        # 快速检查是否有游资(不获取完整逻辑,确保异常不影响显示)
                                        try:
                                            speculator_names = quick_check_speculator(stock)
                                        except Exception:
                                            speculator_names = None  # 出错时默认为无游资
                                        # 检测均线(异步,避免阻塞)
                                        try:
                                            ma_results = check_moving_averages(stock)
                                        except Exception:
                                            ma_results = {'ma1': False, 'ma5': False, 'ma10': False, 'ma20': False}
                                        # 涨跌幅暂时不获取,避免阻塞(可以后续异步更新)
                                        change_pct = None
                                        # 创建卡片(确保所有股票都被创建,无论是否有游资)
                                        card_frame = create_stock_card(photo_wall_container, stock, count, sector, bg_color, font_size, change_pct, speculator_names, ma_results)
                                        # 使用grid布局,每行5列,自动换行
                                        row = idx // cards_per_row
                                        col = idx % cards_per_row
                                        card_frame.grid(row=row, column=col, padx=8, pady=8, sticky="nw")
                                        # 双击事件:弹出详细视图
                                        def on_double_click(e, s=stock, c=count, sec=sector, bg=bg_color):
                                            show_stock_logic_popup(s, c, sec, bg)
                                        # 绑定双击事件到卡片及其所有子组件
                                        def bind_double_click_recursive(widget, handler):
                                            """递归绑定双击事件到所有子组件"""
                                            widget.bind("<Double-Button-1>", handler)
                                            for child in widget.winfo_children():
                                                bind_double_click_recursive(child, handler)
                                        bind_double_click_recursive(card_frame, on_double_click)
                                    except Exception as e:
                                        # 即使单个股票出错,也继续处理其他股票
                                        print(f"创建股票卡片失败 {stock if 'stock' in locals() else 'unknown'}: {e}")
                                        continue
                                loaded_count[0] = end_idx
                                # 如果还有更多,继续加载下一批
                                if end_idx < len(sorted_stocks):
                                    photo_wall_window.after(10, lambda: load_batch(end_idx))  # 减少延迟时间
                                else:
                                    # 所有股票加载完成,更新窗口标题显示总数
                                    photo_wall_window.title(f"股票照片墙 - {len(sorted_stocks)}只股票 - {len(selection)}条资讯")
                                    print(f"照片墙:所有 {len(sorted_stocks)} 只股票已加载完成")
                            # 双击弹出详细视图的函数(使用与持仓股详情相同的弹出框样式)
                            def show_stock_logic_popup(stock_name, stock_count, stock_sector, stock_bg_color):
                                """弹出窗口显示股票逻辑(与持仓股详情相同的样式)"""
                                # 获取股票代码
                                stock_code = get_stock_code_by_name(stock_name)
                                if not stock_code:
                                    messagebox.showwarning("警告", f"无法获取股票代码: {stock_name}", parent=photo_wall_window)
                                    return
                                # 创建弹出窗口(与持仓股详情相同的样式)
                                popup = self._toplevel(photo_wall_window)
                                popup.title(f"持仓详情 - {stock_name} ({stock_code})")
                                popup.geometry("1000x900")
                                popup.transient(photo_wall_window)
                                # 获取股票数据表的逻辑
                                stock_logic_text = ""
                                try:
                                    conn = sqlite3.connect(DB_PATH)
                                    cursor = conn.cursor()
                                    cursor.execute('''
                                        SELECT logic FROM stock_logic
                                        WHERE stock_name = ?
                                        ORDER BY created_at DESC
                                        LIMIT 1
                                    ''', (stock_name,))
                                    row = cursor.fetchone()
                                    if row and row[0]:
                                        stock_logic_text = row[0]
                                    conn.close()
                                except Exception as e:
                                    print(f"获取股票数据表逻辑失败: {e}")
                                # 创建上下分割的PanedWindow(与持仓股详情相同)
                                main_paned = ttk.PanedWindow(popup, orient=tk.VERTICAL)
                                main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                                # 上半部分:逻辑文本和均线检测结果
                                top_frame = ttk.Frame(main_paned)
                                main_paned.add(top_frame, weight=1)
                                # 顶部按钮区域
                                button_frame = ttk.Frame(top_frame)
                                button_frame.pack(fill=tk.X, padx=10, pady=5)
                                # 构建股票链接
                                def build_stock_urls(code):
                                    """构建新浪和东方财富的股票链接"""
                                    urls = {}
                                    if code:
                                        if code.startswith('6'):
                                            urls['新浪'] = f"https://finance.sina.com.cn/realstock/company/sh{code}/nc.shtml"
                                            urls['东方财富'] = f"https://quote.eastmoney.com/sh{code}.html"
                                        else:
                                            urls['新浪'] = f"https://finance.sina.com.cn/realstock/company/sz{code}/nc.shtml"
                                            urls['东方财富'] = f"https://quote.eastmoney.com/sz{code}.html"
                                    return urls
                                stock_urls = build_stock_urls(stock_code)
                                def open_url(url_name):
                                    """打开股票链接"""
                                    import webbrowser
                                    url = stock_urls.get(url_name)
                                    if url:
                                        webbrowser.open(url)
                                # 链接按钮
                                if stock_urls.get('新浪'):
                                    ttk.Button(button_frame, text="新浪", command=lambda: open_url('新浪'), width=10).pack(side=tk.LEFT, padx=5)
                                if stock_urls.get('东方财富'):
                                    ttk.Button(button_frame, text="东方财富", command=lambda: open_url('东方财富'), width=12).pack(side=tk.LEFT, padx=5)
                                # 大单按钮
                                def load_big_order_data():
                                    """加载大单和股票详情"""
                                    detail_text.config(state=tk.NORMAL)
                                    detail_text.insert(tk.END, "\n【正在获取大单和股票详情...】\n")
                                    detail_text.see(tk.END)
                                    detail_text.config(state=tk.DISABLED)
                                    popup.update()
                                    try:
                                        order_data = self._get_large_order_net_inflow_with_accumulation(stock_code, days=20)
                                        detail_text.config(state=tk.NORMAL)
                                        detail_text.insert(tk.END, "\n【大单净流入数据】\n")
                                        if order_data['daily']:
                                            detail_text.insert(tk.END, "最近5日大单净流入:\n")
                                            for item in order_data['daily']:
                                                net_inflow = item['net_inflow']
                                                color_tag = "red_normal" if net_inflow > 0 else "green_normal"
                                                detail_text.insert(tk.END, f"  {item['date']}: {net_inflow:+,.2f} 万元\n", color_tag)
                                            detail_text.insert(tk.END, "\n")
                                        if order_data['accumulation']:
                                            detail_text.insert(tk.END, "累计大单净流入:\n")
                                            for period, value in order_data['accumulation'].items():
                                                color_tag = "red_normal" if value > 0 else "green_normal"
                                                detail_text.insert(tk.END, f"  {period}累计: {value:+,.2f} 万元\n", color_tag)
                                            detail_text.insert(tk.END, "\n")
                                        detail_text.config(state=tk.DISABLED)
                                        detail_text.see(tk.END)
                                    except Exception as e:
                                        detail_text.config(state=tk.NORMAL)
                                        detail_text.insert(tk.END, f"获取大单数据失败: {e}\n\n")
                                        detail_text.config(state=tk.DISABLED)
                                ttk.Button(button_frame, text="大单", command=load_big_order_data, width=10).pack(side=tk.LEFT, padx=5)
                                # 创建滚动文本框显示详情(与持仓股详情相同)
                                text_frame = ttk.Frame(top_frame)
                                text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                                detail_text = tk.Text(text_frame, wrap=tk.WORD, font=("TkDefaultFont", 12))
                                scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=detail_text.yview)
                                detail_text.configure(yscrollcommand=scrollbar.set)
                                detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                                # 配置文本标签(与持仓股详情相同)
                                detail_text.tag_configure("red_normal", foreground="red", font=("TkDefaultFont", 12))
                                detail_text.tag_configure("red_bold", foreground="red", font=("TkDefaultFont", 12, "bold"))
                                detail_text.tag_configure("green_normal", foreground="green", font=("TkDefaultFont", 12))
                                detail_text.tag_configure("green_bold", foreground="green", font=("TkDefaultFont", 12, "bold"))
                                detail_text.tag_configure("speculator", background="#FFF4E6", foreground="#D2691E", font=("TkDefaultFont", 12, "bold"))
                                # 显示基本信息
                                content = "【股票信息】\n"
                                content += f"股票名称: {stock_name}\n"
                                content += f"股票代码: {stock_code}\n"
                                content += f"出现频次: {stock_count}次\n"
                                if stock_sector:
                                    content += f"所属板块: {stock_sector}\n"
                                content += "股票链接: "
                                if stock_urls.get('新浪'):
                                    content += "新浪 | "
                                if stock_urls.get('东方财富'):
                                    content += "东方财富"
                                content += "\n\n"
                                # 在最初位置显示股票数据表的逻辑
                                if stock_logic_text:
                                    content += "="*80 + "\n"
                                    content += "【股票数据表逻辑】\n"
                                    content += "="*80 + "\n"
                                    content += stock_logic_text + "\n"
                                    content += "="*80 + "\n\n"
                                # 获取并显示逻辑内容(标注游资席位)
                                logic_content, has_speculator = get_stock_logic_content(stock_name)
                                if logic_content and logic_content != "未找到逻辑信息":
                                    content += "="*80 + "\n"
                                    content += "【资讯逻辑内容】\n"
                                    content += "="*80 + "\n"
                                    if has_speculator:
                                        content += "【发现游资席位】\n\n"
                                    content += logic_content + "\n"
                                    content += "="*80 + "\n\n"
                                # 显示均线检测结果(获取详细检测信息)
                                def get_detailed_ma_detection():
                                    """获取详细的均线检测结果"""
                                    try:
                                        result = self._fetch_recent_daily_closes(
                                            stock_code, days=45, source="default", token=self.ts_token, return_volume=False
                                        )
                                        if isinstance(result, tuple) and len(result) >= 2:
                                            dates, closes = result[:2]
                                        else:
                                            dates, closes = result, []
                                        if not closes or len(closes) < 3:
                                            return None
                                        latest_price = float(closes[-1])
                                        detection_result = {
                                            'stock_code': stock_code,
                                            'current_price': latest_price,
                                            'dates': dates,
                                            'closes': closes,
                                        }
                                        # 1日线检测
                                        if len(closes) >= 3:
                                            ref_price = float(closes[-2])
                                            prev_price = float(closes[-3])
                                            crossed = latest_price >= ref_price
                                            uptrend = ref_price >= prev_price
                                            detection_result['ma1'] = {
                                                'ref': ref_price,
                                                'prev': prev_price,
                                                'crossed': crossed,
                                                'uptrend': uptrend
                                            }
                                        # 5日线检测
                                        if len(closes) >= 7:
                                            ma5_values = [float(closes[i]) for i in range(len(closes)-5, len(closes))]
                                            ref_ma5 = sum(ma5_values) / len(ma5_values)
                                            prev_ma5_values = [float(closes[i]) for i in range(len(closes)-10, len(closes)-5)]
                                            prev_ma5 = sum(prev_ma5_values) / len(prev_ma5_values) if len(prev_ma5_values) >= 5 else ref_ma5
                                            crossed = latest_price >= ref_ma5
                                            uptrend = ref_ma5 >= prev_ma5
                                            detection_result['ma5'] = {
                                                'ref': ref_ma5,
                                                'prev': prev_ma5,
                                                'crossed': crossed,
                                                'uptrend': uptrend
                                            }
                                        # 10日线检测
                                        if len(closes) >= 12:
                                            ma10_values = [float(closes[i]) for i in range(len(closes)-10, len(closes))]
                                            ref_ma10 = sum(ma10_values) / len(ma10_values)
                                            prev_ma10_values = [float(closes[i]) for i in range(len(closes)-20, len(closes)-10)]
                                            prev_ma10 = sum(prev_ma10_values) / len(prev_ma10_values) if len(prev_ma10_values) >= 10 else ref_ma10
                                            crossed = latest_price >= ref_ma10
                                            uptrend = ref_ma10 >= prev_ma10
                                            detection_result['ma10'] = {
                                                'ref': ref_ma10,
                                                'prev': prev_ma10,
                                                'crossed': crossed,
                                                'uptrend': uptrend
                                            }
                                        # 20日线检测
                                        if len(closes) >= 22:
                                            ma20_values = [float(closes[i]) for i in range(len(closes)-20, len(closes))]
                                            ref_ma20 = sum(ma20_values) / len(ma20_values)
                                            prev_ma20_values = [float(closes[i]) for i in range(len(closes)-40, len(closes)-20)]
                                            prev_ma20 = sum(prev_ma20_values) / len(prev_ma20_values) if len(prev_ma20_values) >= 20 else ref_ma20
                                            crossed = latest_price >= ref_ma20
                                            uptrend = ref_ma20 >= prev_ma20
                                            detection_result['ma20'] = {
                                                'ref': ref_ma20,
                                                'prev': prev_ma20,
                                                'crossed': crossed,
                                                'uptrend': uptrend
                                            }
                                        return detection_result
                                    except Exception as e:
                                        print(f"均线检测失败: {e}")
                                        return None
                                try:
                                    detection_result = get_detailed_ma_detection()
                                    # 显示详细的均线检测信息
                                    if detection_result:
                                        content += "="*80 + "\n"
                                        content += "【均线检测结果】\n"
                                        content += "="*80 + "\n"
                                        # 1日线
                                        if 'ma1' in detection_result:
                                            ma1 = detection_result['ma1']
                                            cross_text = "已站上" if ma1['crossed'] else "未站上"
                                            trend_text = "上升" if ma1['uptrend'] else "未上升"
                                            status_color = "✓" if (ma1['crossed'] and ma1['uptrend']) else "✗"
                                            content += f"{status_color} 1日线: {cross_text}1日线,1日线{trend_text}\n"
                                            content += f"  当前价: {detection_result['current_price']:.2f} / 参考1日线: {ma1['ref']:.2f} / 前值: {ma1['prev']:.2f}\n\n"
                                        # 5日线
                                        if 'ma5' in detection_result:
                                            ma5 = detection_result['ma5']
                                            cross_text = "已站上" if ma5['crossed'] else "未站上"
                                            trend_text = "上升" if ma5['uptrend'] else "未上升"
                                            status_color = "✓" if (ma5['crossed'] and ma5['uptrend']) else "✗"
                                            content += f"{status_color} 5日线: {cross_text}5日线,5日线{trend_text}\n"
                                            content += f"  当前价: {detection_result['current_price']:.2f} / 参考5日线: {ma5['ref']:.2f} / 前值: {ma5['prev']:.2f}\n\n"
                                        # 10日线
                                        if 'ma10' in detection_result:
                                            ma10 = detection_result['ma10']
                                            cross_text = "已站上" if ma10['crossed'] else "未站上"
                                            trend_text = "上升" if ma10['uptrend'] else "未上升"
                                            status_color = "✓" if (ma10['crossed'] and ma10['uptrend']) else "✗"
                                            content += f"{status_color} 10日线: {cross_text}10日线,10日线{trend_text}\n"
                                            content += f"  当前价: {detection_result['current_price']:.2f} / 参考10日线: {ma10['ref']:.2f} / 前值: {ma10['prev']:.2f}\n"
                                            if ma10['ref'] > 0:
                                                distance_pct = abs((detection_result['current_price'] - ma10['ref']) / ma10['ref']) * 100
                                                content += f"  价格距离10日均线: {distance_pct:.2f}%\n"
                                            content += "\n"
                                        # 20日线
                                        if 'ma20' in detection_result:
                                            ma20 = detection_result['ma20']
                                            cross_text = "已站上" if ma20['crossed'] else "未站上"
                                            trend_text = "上升" if ma20['uptrend'] else "未上升"
                                            status_color = "✓" if (ma20['crossed'] and ma20['uptrend']) else "✗"
                                            content += f"{status_color} 20日线: {cross_text}20日线,20日线{trend_text}\n"
                                            content += f"  当前价: {detection_result['current_price']:.2f} / 参考20日线: {ma20['ref']:.2f} / 前值: {ma20['prev']:.2f}\n\n"
                                except Exception as e:
                                    content += f"【均线检测】\n检测失败: {e}\n\n"
                                # 显示内容
                                detail_text.insert(tk.END, content)
                                # 标注游资席位关键词
                                if logic_content and logic_content != "未找到逻辑信息":
                                    for keyword in speculator_keywords:
                                        start = "1.0"
                                        while True:
                                            pos = detail_text.search(keyword, start, tk.END)
                                            if not pos:
                                                break
                                            end_pos = f"{pos}+{len(keyword)}c"
                                            detail_text.tag_add("speculator", pos, end_pos)
                                            start = end_pos
                                detail_text.config(state=tk.DISABLED)
                                popup.update()
                                # 获取并显示最近5天的涨跌幅
                                try:
                                    price_changes = self._get_stock_price_changes(stock_code, days=5)
                                    if price_changes:
                                        detail_text.config(state=tk.NORMAL)
                                        detail_text.insert(tk.END, "【最近5天涨跌幅】\n")
                                        detail_text.insert(tk.END, "=" * 50 + "\n")
                                        for item in price_changes[:5]:
                                            change_pct = item['change_pct']
                                            date = item['date']
                                            if change_pct > 0:
                                                detail_text.insert(tk.END, f"{date}: {change_pct:+.2f}%\n", "red_normal")
                                            elif change_pct < 0:
                                                detail_text.insert(tk.END, f"{date}: {change_pct:+.2f}%\n", "green_normal")
                                            else:
                                                detail_text.insert(tk.END, f"{date}: {change_pct:+.2f}%\n")
                                        detail_text.insert(tk.END, "\n")
                                        detail_text.config(state=tk.DISABLED)
                                except Exception:
                                    pass
                                # 下半部分:日K线图(数据来自Tushare,与持仓详情一致)
                                bottom_frame = ttk.LabelFrame(main_paned, text="日K线图(Tushare)", padding=10)
                                main_paned.add(bottom_frame, weight=1)
                                sentiment_bottom_frame = ttk.LabelFrame(main_paned, text="同花顺情绪指数(日线)", padding=10)
                                main_paned.add(sentiment_bottom_frame, weight=0)
                                # 显示加载中
                                kline_loading_label = ttk.Label(bottom_frame,
                                                               text="正在加载日K线图...",
                                                               font=("TkDefaultFont", 12))
                                kline_loading_label.pack(expand=True)
                                sentiment_loading_label = ttk.Label(sentiment_bottom_frame,
                                                                    text="正在加载同花顺情绪指数...",
                                                                    font=("TkDefaultFont", 12))
                                sentiment_loading_label.pack(expand=True)
                                popup.update()
                                # 在后台线程中加载日K线数据与同花顺情绪指数(Tushare 优先,失败则 AKShare)
                                def load_kline_data():
                                    try:
                                        kline_data = self._get_daily_kline_data_tushare(stock_code, days=60)
                                        sentiment_data = self._get_ths_sentiment_index_daily(days=60)
                                        def update_kline_ui():
                                            kline_loading_label.destroy()
                                            if kline_data:
                                                self._draw_daily_kline_chart(bottom_frame, kline_data, stock_name)
                                            else:
                                                error_label = ttk.Label(bottom_frame,
                                                                       text="无法获取日K线数据(请检查Tushare配置)",
                                                                       font=("TkDefaultFont", 12),
                                                                       foreground="red")
                                                error_label.pack(expand=True)
                                            sentiment_loading_label.destroy()
                                            if sentiment_data:
                                                self._draw_sentiment_index_chart(sentiment_bottom_frame, sentiment_data)
                                            else:
                                                ttk.Label(sentiment_bottom_frame,
                                                         text="无法获取同花顺情绪指数日线(请检查网络或 Tushare/AKShare)",
                                                         font=("TkDefaultFont", 12),
                                                         foreground="gray").pack(expand=True)
                                        popup.after(0, update_kline_ui)
                                    except Exception as e:
                                        def show_error(e=e):
                                            kline_loading_label.destroy()
                                            error_label = ttk.Label(bottom_frame,
                                                                   text=f"加载日K线图失败: {e}",
                                                                   font=("TkDefaultFont", 12),
                                                                   foreground="red")
                                            error_label.pack(expand=True)
                                            sentiment_loading_label.destroy()
                                            ttk.Label(sentiment_bottom_frame, text=f"加载同花顺情绪指数失败: {e}",
                                                     font=("TkDefaultFont", 12), foreground="gray").pack(expand=True)
                                        popup.after(0, show_error)
                                        import traceback
                                        traceback.print_exc()
                                threading.Thread(target=load_kline_data, daemon=True).start()
                            # 开始批量加载(先加载第一批)
                            load_batch(0)
                        except Exception as e:
                            messagebox.showerror("错误", f"显示照片墙失败: {e}", parent=wordcloud_window)
                            import traceback
                            traceback.print_exc()
                    ttk.Button(toolbar_frame, text="照片墙", command=show_photo_wall, width=12).pack(side=tk.LEFT, padx=5)
                    # 词云显示区域(占满大部分空间)
                    wordcloud_canvas_frame = ttk.Frame(main_frame)
                    wordcloud_canvas_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
                    wordcloud_canvas = tk.Canvas(wordcloud_canvas_frame, bg="white", highlightthickness=1, highlightbackground="gray")
                    wordcloud_canvas.pack(fill=tk.BOTH, expand=True)
                    wordcloud_window._wordcloud_canvas = wordcloud_canvas
                    # 股票列表(小字体,显示在词云下方)
                    stock_list_frame = ttk.Frame(main_frame)
                    stock_list_frame.pack(fill=tk.X, pady=(0, 0))
                    stock_list_label = ttk.Label(stock_list_frame, text="股票列表(点击查看逻辑):", font=("TkDefaultFont", 8))
                    stock_list_label.pack(side=tk.LEFT, padx=(0, 5))
                    # 股票名称显示区域(小字体,横向排列)
                    stock_names_frame = ttk.Frame(stock_list_frame)
                    stock_names_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    # 创建滚动框架(垂直滚动,分5行显示)
                    stock_list_canvas = tk.Canvas(stock_names_frame, height=120, highlightthickness=0)
                    stock_list_scrollbar = ttk.Scrollbar(stock_names_frame, orient=tk.VERTICAL, command=stock_list_canvas.yview)
                    stock_list_inner_frame = ttk.Frame(stock_list_canvas)
                    stock_list_inner_frame.bind(
                        "<Configure>",
                        lambda e: stock_list_canvas.configure(scrollregion=stock_list_canvas.bbox("all"))
                    )
                    stock_list_canvas.create_window((0, 0), window=stock_list_inner_frame, anchor="nw")
                    stock_list_canvas.configure(yscrollcommand=stock_list_scrollbar.set)
                    stock_list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    stock_list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                    # 为每个股票分配不同颜色
                    # 生成颜色列表(使用HSV色彩空间,确保颜色分布均匀)
                    def generate_colors(n):
                        """生成n个不同的颜色"""
                        colors = []
                        for i in range(n):
                            hue = (i * 360 / n) % 360
                            saturation = 0.7 + (i % 3) * 0.1  # 0.7-0.9
                            value = 0.6 + (i % 2) * 0.2  # 0.6-0.8
                            # 转换为RGB
                            import colorsys
                            r, g, b = colorsys.hsv_to_rgb(hue/360, saturation, value)
                            colors.append(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")
                        return colors
                    # 生成词云数据(股票名称和词频)
                    word_freq = {}
                    stock_colors_map = {}  # 存储每个股票对应的颜色
                    # 为每个股票分配颜色
                    unique_stocks = list(stock_counter.keys())
                    stock_colors = generate_colors(len(unique_stocks))
                    for i, stock in enumerate(unique_stocks):
                        word_freq[stock] = stock_counter[stock]
                        stock_colors_map[stock] = stock_colors[i]
                    # 创建颜色函数(每个股票使用不同颜色)
                    def color_func(word, font_size, position, orientation, random_state=None, **kwargs):
                        """为每个股票分配不同颜色"""
                        return stock_colors_map.get(word, "#000000")
                    # 获取中文字体路径
                    def get_chinese_font_path():
                        """获取中文字体路径"""
                        font_paths = [
                            'C:/Windows/Fonts/simhei.ttf',  # 黑体
                            'C:/Windows/Fonts/msyh.ttc',    # 微软雅黑
                            'C:/Windows/Fonts/simsun.ttc',  # 宋体
                            'C:/Windows/Fonts/msyhbd.ttc',  # 微软雅黑 Bold
                        ]
                        for font_path in font_paths:
                            if os.path.exists(font_path):
                                return font_path
                        return None
                    chinese_font_path = get_chinese_font_path()
                    # 生成词云和股票列表
                    def generate_wordcloud():
                        try:
                            # 获取窗口实际大小(占满整个窗口)
                            wordcloud_window.update_idletasks()
                            window_width = wordcloud_window.winfo_width()
                            window_height = wordcloud_window.winfo_height()
                            # 减去padding和工具栏、股票列表的高度
                            wordcloud_width = window_width - 40  # 减去左右padding
                            wordcloud_height = window_height - 100  # 减去工具栏和股票列表高度
                            if wordcloud_width < 400:
                                wordcloud_width = 1360  # 默认值
                            if wordcloud_height < 300:
                                wordcloud_height = 700  # 默认值
                            # 创建词云对象
                            wc = WordCloud(
                                width=wordcloud_width,
                                height=wordcloud_height,
                                background_color='white',
                                max_words=200,
                                font_path=chinese_font_path,  # 使用中文字体
                                relative_scaling=0.5,
                                color_func=color_func,
                                prefer_horizontal=0.7
                            ).generate_from_frequencies(word_freq)
                            # 转换为PIL图片
                            wordcloud_image = wc.to_image()
                            wordcloud_window._wordcloud_image = wordcloud_image
                            # 在主线程中更新UI
                            def update_ui():
                                # 转换为Tkinter可用的格式
                                from PIL import ImageTk
                                photo = ImageTk.PhotoImage(wordcloud_image)
                                # 清除Canvas并显示词云(居中显示)
                                wordcloud_canvas.delete("all")
                                canvas_width = wordcloud_canvas.winfo_width()
                                canvas_height = wordcloud_canvas.winfo_height()
                                if canvas_width <= 1:
                                    canvas_width = 800
                                if canvas_height <= 1:
                                    canvas_height = 600
                                wordcloud_canvas.create_image(canvas_width//2, canvas_height//2, image=photo, anchor=tk.CENTER)
                                wordcloud_canvas.image = photo  # 保持引用
                                # 创建股票列表(按词频排序,分5行显示)
                                sorted_stocks = sorted(stock_counter.items(), key=lambda x: x[1], reverse=True)
                                # 清除现有列表
                                for widget in stock_list_inner_frame.winfo_children():
                                    widget.destroy()
                                # 计算每行显示的股票数量(分5行)
                                total_stocks = len(sorted_stocks)
                                stocks_per_row = (total_stocks + 4) // 5  # 向上取整,确保分5行
                                # 创建股票标签(小字体,分5行显示)
                                for idx, (stock, count) in enumerate(sorted_stocks):
                                    # 获取股票对应的颜色
                                    color = stock_colors_map.get(stock, "#000000")
                                    # 计算行和列位置
                                    row = idx // stocks_per_row
                                    col = idx % stocks_per_row
                                    # 创建可点击的标签(小字体)
                                    stock_label = tk.Label(
                                        stock_list_inner_frame,
                                        text=f"{stock}({count})",
                                        font=("TkDefaultFont", 7),  # 小字体
                                        fg=color,
                                        cursor="hand2",
                                        anchor="w"
                                    )
                                    stock_label.grid(row=row, column=col, padx=3, pady=1, sticky="w")
                                    # 绑定点击事件
                                    def on_stock_click(stock_name=stock):
                                        show_stock_logic(stock_name)
                                        # 显示逻辑框(如果隐藏)
                                        logic_frame_ref = wordcloud_window._logic_frame
                                        if logic_frame_ref and not logic_frame_ref.winfo_viewable():
                                            wordcloud_window._toggle_logic_frame()
                                    stock_label.bind("<Button-1>", lambda e, s=stock: on_stock_click(s))
                                    stock_label.bind("<Enter>", lambda e, s=stock: on_stock_click(s))
                            wordcloud_window.after(0, update_ui)
                        except Exception as e:
                            wordcloud_window.after(0, lambda e=e: messagebox.showerror("错误", f"生成词云失败: {e}", parent=wordcloud_window))
                            import traceback
                            traceback.print_exc()
                    # 显示股票逻辑的函数
                    def show_stock_logic(stock_name):
                        """显示指定股票的逻辑"""
                        try:
                            conn = sqlite3.connect(DB_PATH)
                            cursor = conn.cursor()
                            all_logic_texts = []
                            for news_id in selected_news_ids:
                                cursor.execute('SELECT content FROM news_info WHERE id = ?', (news_id,))
                                row = cursor.fetchone()
                                if row:
                                    content = row[0] or ""
                                    # 提取包含该股票的段落
                                    lines = content.split('\n')
                                    stock_logic = []
                                    for i, line in enumerate(lines):
                                        if stock_name in line:
                                            # 包含该行的前后几行作为上下文
                                            start = max(0, i - 2)
                                            end = min(len(lines), i + 10)
                                            stock_logic.extend(lines[start:end])
                                            break
                                    if stock_logic:
                                        all_logic_texts.append("\n".join(stock_logic))
                            conn.close()
                            # 更新逻辑文本框
                            logic_text.config(state=tk.NORMAL)
                            logic_text.delete("1.0", tk.END)
                            if all_logic_texts:
                                logic_text.insert(tk.END, f"【{stock_name}】的逻辑信息\n\n", "stock_title")
                                for i, logic in enumerate(all_logic_texts, 1):
                                    logic_text.insert(tk.END, f"--- 来源 {i} ---\n", "source_title")
                                    logic_text.insert(tk.END, logic + "\n\n")
                            else:
                                logic_text.insert(tk.END, f"未找到【{stock_name}】的逻辑信息\n")
                            logic_text.config(state=tk.DISABLED)
                            # 配置标签样式
                            logic_text.tag_config("stock_title", font=("TkDefaultFont", 14, "bold"), foreground="blue")
                            logic_text.tag_config("source_title", font=("TkDefaultFont", 11, "bold"), foreground="gray")
                        except Exception as e:
                            messagebox.showerror("错误", f"获取逻辑失败: {e}", parent=wordcloud_window)
                    # 在后台线程中生成词云
                    threading.Thread(target=generate_wordcloud, daemon=True).start()
                    # 逻辑文本框(显示在底部,可折叠或弹出)
                    logic_frame = ttk.LabelFrame(main_frame, text="股票逻辑", padding=5)
                    logic_frame.pack(fill=tk.BOTH, expand=False, pady=(10, 0))
                    logic_frame.pack_forget()  # 初始隐藏
                    logic_text = scrolledtext.ScrolledText(logic_frame, wrap=tk.WORD, font=("TkDefaultFont", 12), height=8)
                    logic_text.pack(fill=tk.BOTH, expand=True)
                    logic_text.insert("1.0", "点击上方股票列表中的股票名称查看该股票的逻辑信息\n\n")
                    logic_text.config(state=tk.DISABLED)
                    # 显示/隐藏逻辑框的函数
                    def toggle_logic_frame():
                        if logic_frame.winfo_viewable():
                            logic_frame.pack_forget()
                        else:
                            logic_frame.pack(fill=tk.BOTH, expand=False, pady=(10, 0))
                    # 在工具栏添加切换按钮
                    ttk.Button(toolbar_frame, text="显示/隐藏逻辑", command=toggle_logic_frame, width=14).pack(side=tk.LEFT, padx=5)
                    # 保存引用以便在update_ui中使用
                    wordcloud_window._logic_frame = logic_frame
                    wordcloud_window._logic_text = logic_text
                    wordcloud_window._selected_news_ids = selected_news_ids
                    wordcloud_window._stock_counter = stock_counter
                    wordcloud_window._show_stock_logic = show_stock_logic
                    wordcloud_window._toggle_logic_frame = toggle_logic_frame
                except Exception as e:
                    messagebox.showerror("错误", f"词云分析失败: {e}", parent=db_window)
                    import traceback
                    traceback.print_exc()
            ttk.Button(content_query_frame, text="词云分析", command=show_wordcloud_analysis, width=12).pack(side=tk.LEFT, padx=5)
            # 游资分析按钮
            def analyze_speculators():
                """游资分析功能"""
                # 创建日期范围选择对话框
                date_dialog = self._toplevel(db_window)
                date_dialog.title("游资分析 - 选择日期范围")
                date_dialog.geometry("400x200")
                date_dialog.transient(db_window)
                date_dialog.grab_set()
                # 居中显示
                date_dialog.update_idletasks()
                x = (date_dialog.winfo_screenwidth() // 2) - (date_dialog.winfo_width() // 2)
                y = (date_dialog.winfo_screenheight() // 2) - (date_dialog.winfo_height() // 2)
                date_dialog.geometry(f"+{x}+{y}")
                # 日期选择框架
                date_frame = ttk.Frame(date_dialog, padding=20)
                date_frame.pack(fill=tk.BOTH, expand=True)
                # 起始日期
                start_frame = ttk.Frame(date_frame)
                start_frame.pack(fill=tk.X, pady=10)
                ttk.Label(start_frame, text="起始日期:", width=12).pack(side=tk.LEFT, padx=5)
                start_date_var = tk.StringVar()
                start_date_entry = ttk.Entry(start_frame, textvariable=start_date_var, width=20)
                start_date_entry.pack(side=tk.LEFT, padx=5)
                start_date_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
                ttk.Label(start_frame, text="(格式: YYYY-MM-DD)", font=("TkDefaultFont", 8), foreground="gray").pack(side=tk.LEFT, padx=5)
                # 结束日期
                end_frame = ttk.Frame(date_frame)
                end_frame.pack(fill=tk.X, pady=10)
                ttk.Label(end_frame, text="结束日期:", width=12).pack(side=tk.LEFT, padx=5)
                end_date_var = tk.StringVar()
                end_date_entry = ttk.Entry(end_frame, textvariable=end_date_var, width=20)
                end_date_entry.pack(side=tk.LEFT, padx=5)
                end_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
                ttk.Label(end_frame, text="(格式: YYYY-MM-DD)", font=("TkDefaultFont", 8), foreground="gray").pack(side=tk.LEFT, padx=5)
                # 按钮框架
                button_frame = ttk.Frame(date_frame)
                button_frame.pack(fill=tk.X, pady=20)
                def start_analysis():
                    """开始分析"""
                    start_date_str = start_date_var.get().strip()
                    end_date_str = end_date_var.get().strip()
                    if not start_date_str or not end_date_str:
                        messagebox.showwarning("警告", "请输入起始日期和结束日期", parent=date_dialog)
                        return
                    try:
                        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                        if start_date > end_date:
                            messagebox.showwarning("警告", "起始日期不能晚于结束日期", parent=date_dialog)
                            return
                        date_dialog.destroy()
                        # 在新线程中执行分析,避免阻塞UI
                        def analyze_thread():
                            try:
                                # 执行游资分析(使用self调用实例方法)
                                result = self.perform_speculator_analysis(start_date, end_date, db_window)
                                # 在主线程中显示结果
                                db_window.after(0, lambda: self.show_speculator_analysis_result(result, db_window))
                            except Exception as e:
                                db_window.after(0, lambda e=e: messagebox.showerror("错误", f"游资分析失败: {e}", parent=db_window))
                        threading.Thread(target=analyze_thread, daemon=True).start()
                    except ValueError:
                        messagebox.showerror("错误", "日期格式不正确,请使用 YYYY-MM-DD 格式", parent=date_dialog)
                ttk.Button(button_frame, text="开始分析", command=start_analysis, width=12).pack(side=tk.LEFT, padx=10)
                ttk.Button(button_frame, text="取消", command=date_dialog.destroy, width=12).pack(side=tk.LEFT, padx=10)
            ttk.Button(content_query_frame, text="游资分析", command=analyze_speculators, width=12).pack(side=tk.LEFT, padx=5)
            # 股票逻辑查询按钮
            def batch_stock_logic_query():
                """批量股票逻辑查询功能"""
                # 创建输入对话框
                input_dialog = self._toplevel(db_window)
                input_dialog.title("股票批量逻辑查询")
                input_dialog.geometry("600x400")
                input_dialog.transient(db_window)
                input_dialog.grab_set()
                # 居中显示
                input_dialog.update_idletasks()
                x = (input_dialog.winfo_screenwidth() // 2) - (input_dialog.winfo_width() // 2)
                y = (input_dialog.winfo_screenheight() // 2) - (input_dialog.winfo_height() // 2)
                input_dialog.geometry(f"+{x}+{y}")
                # 说明标签
                ttk.Label(input_dialog, text="请粘贴需要查询的股票列表(支持股票名称或代码,每行一个或用逗号/空格分隔)",
                         font=("TkDefaultFont", 11), wraplength=550).pack(anchor=tk.W, padx=10, pady=(10, 5))
                # 输入框
                input_frame = ttk.Frame(input_dialog)
                input_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                input_text = scrolledtext.ScrolledText(input_frame, wrap=tk.WORD, height=15, font=("TkDefaultFont", 12))
                input_text.pack(fill=tk.BOTH, expand=True)
                # 按钮框架
                button_frame = ttk.Frame(input_dialog)
                button_frame.pack(fill=tk.X, padx=10, pady=10)
                def start_query():
                    """开始查询"""
                    text_content = input_text.get("1.0", tk.END).strip()
                    if not text_content:
                        messagebox.showwarning("警告", "请输入股票列表", parent=input_dialog)
                        return
                    # 提取股票名称
                    stock_list, _ = extract_stock_names(text_content)
                    if not stock_list:
                        messagebox.showwarning("警告", "未能识别出股票,请检查输入格式", parent=input_dialog)
                        return
                    # 去重并清理
                    unique_stocks = []
                    seen = set()
                    for stock in stock_list:
                        # 处理格式:可能是"股票名称"或"代码(股票名称)"
                        if '(' in stock and ')' in stock:
                            # 格式:代码(股票名称)
                            stock_name = stock.split('(')[1].rstrip(')')
                        else:
                            stock_name = stock
                        if stock_name not in seen:
                            unique_stocks.append(stock_name)
                            seen.add(stock_name)
                    if not unique_stocks:
                        messagebox.showwarning("警告", "未能识别出有效的股票", parent=input_dialog)
                        return
                    input_dialog.destroy()
                    # 在新线程中执行查询,避免阻塞UI
                    def query_thread():
                        try:
                            # 执行批量查询
                            self._perform_batch_stock_logic_query(unique_stocks, db_window)
                        except Exception as e:
                            db_window.after(0, lambda e=e: messagebox.showerror("错误", f"批量查询失败: {e}", parent=db_window))
                    threading.Thread(target=query_thread, daemon=True).start()
                ttk.Button(button_frame, text="开始查询", command=start_query, width=12).pack(side=tk.LEFT, padx=10)
                ttk.Button(button_frame, text="取消", command=input_dialog.destroy, width=12).pack(side=tk.LEFT, padx=10)
            ttk.Button(content_query_frame, text="股票逻辑查询", command=batch_stock_logic_query, width=12).pack(side=tk.LEFT, padx=5)
            # 数据表格和内容详情(左右布局)
            news_content_frame = ttk.Frame(news_tab)
            news_content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            # 左侧:数据表格
            news_left_content = ttk.Frame(news_content_frame)
            news_left_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
            news_table_label = ttk.Label(news_left_content, text="资讯数据列表", font=("TkDefaultFont", 12, "bold"))
            news_table_label.pack(anchor=tk.W, pady=(0, 5))
            news_table_frame = ttk.Frame(news_left_content)
            news_table_frame.pack(fill=tk.BOTH, expand=True)
            news_columns = ("ID", "标签页名称", "内容预览", "创建时间", "更新时间")
            news_tree = ttk.Treeview(news_table_frame, columns=news_columns, show="headings", height=25)
            for col in news_columns:
                news_tree.heading(col, text=col)
                if col == "ID":
                    news_tree.column(col, width=50, anchor=tk.CENTER)
                elif col == "标签页名称":
                    news_tree.column(col, width=200, anchor=tk.CENTER)
                elif col == "内容预览":
                    news_tree.column(col, width=300)
                elif col == "创建时间" or col == "更新时间":
                    news_tree.column(col, width=150, anchor=tk.CENTER)
            news_scrollbar = ttk.Scrollbar(news_table_frame, orient=tk.VERTICAL, command=news_tree.yview)
            news_tree.configure(yscrollcommand=news_scrollbar.set)
            news_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            news_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            # 右侧:内容详情
            news_right_content = ttk.Frame(news_content_frame)
            news_right_content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
            # 右侧标签页(包含完整内容和起爆点数据表)
            news_right_notebook = ttk.Notebook(news_right_content)
            news_right_notebook.pack(fill=tk.BOTH, expand=True)
            # 第一个标签页:完整内容
            news_content_tab = ttk.Frame(news_right_notebook)
            news_right_notebook.add(news_content_tab, text="完整内容")
            # 导出按钮框架(在内容详情上方)
            news_export_frame = ttk.Frame(news_content_tab)
            news_export_frame.pack(fill=tk.X, pady=(0, 5))
            def export_news_as_text():
                """导出选中的所有资讯为文字,合并后复制到剪贴板"""
                selection = news_tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择至少一条资讯")
                    return
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    # 收集所有选中资讯的内容
                    all_texts = []
                    for item_id in selection:
                        item = news_tree.item(item_id)
                        news_id = item['values'][0]
                        cursor.execute('SELECT tab_name, content, created_at, updated_at FROM news_info WHERE id = ?', (news_id,))
                        row = cursor.fetchone()
                        if row:
                            tab_name, content, created_at, updated_at = row
                            # 去除词云图片链接部分,只保留文本
                            import re
                            text_content = re.sub(r'\[词云图片\].*?图片链接:.*?\n', '', content, flags=re.DOTALL)
                            text_content = re.sub(r'文件路径:.*?\n', '', text_content)
                            # 添加分隔符和标题
                            header = f"【{tab_name}】{created_at or updated_at or ''}\n{'-'*80}\n"
                            all_texts.append(header + text_content.strip())
                    conn.close()
                    if all_texts:
                        # 合并所有文本
                        merged_text = "\n\n".join(all_texts)
                        # 复制到剪贴板
                        try:
                            db_window.clipboard_clear()
                            db_window.clipboard_append(merged_text)
                            messagebox.showinfo("成功", f"已复制 {len(selection)} 条资讯的内容到剪贴板")
                        except Exception as e:
                            messagebox.showerror("错误", f"复制到剪贴板失败: {e}")
                    else:
                        messagebox.showwarning("警告", "没有找到可导出的内容")
                except Exception as e:
                    messagebox.showerror("错误", f"导出失败: {e}")
            def analyze_selected_news():
                """分析选中的所有资讯:股票名统计、情绪分析、AI分析"""
                selection = news_tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择至少一条资讯")
                    return
                # 创建分析窗口
                analysis_window = self._toplevel(db_window)
                analysis_window.title("资讯分析结果")
                analysis_window.geometry("900x700")
                # 创建结果显示区域
                result_text = scrolledtext.ScrolledText(analysis_window, wrap=tk.WORD, font=("Consolas", 12))
                result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                result_text.insert("1.0", "正在分析中,请稍候...\n")
                analysis_window.update()
                def run_analysis():
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        # 收集所有选中资讯的内容和日期
                        all_contents = []
                        date_content_map = {}  # 按日期分组的内容
                        for item_id in selection:
                            item = news_tree.item(item_id)
                            news_id = item['values'][0]
                            cursor.execute('SELECT tab_name, content, created_at, updated_at FROM news_info WHERE id = ?', (news_id,))
                            row = cursor.fetchone()
                            if row:
                                _tab_name, content, created_at, updated_at = row
                                # 去除词云图片链接部分
                                import re
                                text_content = re.sub(r'\[词云图片\].*?图片链接:.*?\n', '', content, flags=re.DOTALL)
                                text_content = re.sub(r'文件路径:.*?\n', '', text_content)
                                all_contents.append(text_content)
                                # 提取日期(只取日期部分,忽略时间)
                                date_str = None
                                if created_at:
                                    try:
                                        dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                                        date_str = dt.strftime("%Y-%m-%d")
                                    except:
                                        date_str = created_at[:10] if len(created_at) >= 10 else created_at
                                elif updated_at:
                                    try:
                                        dt = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
                                        date_str = dt.strftime("%Y-%m-%d")
                                    except:
                                        date_str = updated_at[:10] if len(updated_at) >= 10 else updated_at
                                if date_str:
                                    if date_str not in date_content_map:
                                        date_content_map[date_str] = []
                                    date_content_map[date_str].append(text_content)
                        conn.close()
                        if not all_contents:
                            analysis_window.after(0, lambda: result_text.delete("1.0", tk.END) or
                                                 result_text.insert("1.0", "没有找到可分析的内容"))
                            return
                        # 合并所有文本
                        merged_text = "\n\n".join(all_contents)
                        # 1. 股票名分析
                        result_text.delete("1.0", tk.END)
                        result_text.insert(tk.END, "="*80 + "\n")
                        result_text.insert(tk.END, "资讯分析报告\n")
                        result_text.insert(tk.END, "="*80 + "\n\n")
                        result_text.insert(tk.END, "【一、股票名称统计】\n")
                        result_text.insert(tk.END, "-"*80 + "\n")
                        # 提取所有股票名称
                        stock_names_all, _ = extract_stock_names(merged_text)
                        # 统计每个股票名称出现的总次数
                        stock_count_map = {}
                        for stock in stock_names_all:
                            # 清理股票名称(去除代码部分)
                            clean_name = stock.split('(')[0] if '(' in stock else stock
                            count = merged_text.count(clean_name)
                            if clean_name not in stock_count_map:
                                stock_count_map[clean_name] = 0
                            stock_count_map[clean_name] += count
                        # 按日期统计每个股票出现的次数
                        stock_date_map = {}  # {股票名: {日期: 次数}}
                        for date_str, contents in date_content_map.items():
                            date_text = "\n\n".join(contents)
                            date_stocks, _ = extract_stock_names(date_text)
                            for stock in date_stocks:
                                clean_name = stock.split('(')[0] if '(' in stock else stock
                                if clean_name not in stock_date_map:
                                    stock_date_map[clean_name] = {}
                                if date_str not in stock_date_map[clean_name]:
                                    stock_date_map[clean_name][date_str] = 0
                                stock_date_map[clean_name][date_str] += date_text.count(clean_name)
                        # 显示股票统计结果
                        if stock_count_map:
                            # 按出现次数排序
                            sorted_stocks = sorted(stock_count_map.items(), key=lambda x: x[1], reverse=True)
                            result_text.insert(tk.END, f"共发现 {len(stock_count_map)} 只股票:\n\n")
                            for stock_name, total_count in sorted_stocks:
                                result_text.insert(tk.END, f"股票名称: {stock_name}\n")
                                result_text.insert(tk.END, f"  总出现次数: {total_count}\n")
                                # 显示各日期出现次数
                                if stock_name in stock_date_map:
                                    result_text.insert(tk.END, "  各日期出现情况:\n")
                                    for date_str in sorted(stock_date_map[stock_name].keys()):
                                        count = stock_date_map[stock_name][date_str]
                                        result_text.insert(tk.END, f"    {date_str}: {count} 次\n")
                                result_text.insert(tk.END, "\n")
                            result_text.insert(tk.END, "未发现股票名称\n\n")
                        # 2. 情绪分析
                        result_text.insert(tk.END, "\n【二、情绪分析】\n")
                        result_text.insert(tk.END, "-"*80 + "\n")
                        sentiment_analysis = analyze_text_dimensions(merged_text)
                        if sentiment_analysis:
                            result_text.insert(tk.END, f"整体情绪倾向: {sentiment_analysis.get('sentiment', '未知')}\n")
                            result_text.insert(tk.END, f"市场状况: {sentiment_analysis.get('market_status', '未知')}\n\n")
                            sentiment_details = sentiment_analysis.get('sentiment_details', {})
                            result_text.insert(tk.END, "情绪关键词统计:\n")
                            result_text.insert(tk.END, f"  积极词汇: {sentiment_details.get('positive', 0)} 次\n")
                            result_text.insert(tk.END, f"  消极词汇: {sentiment_details.get('negative', 0)} 次\n")
                            result_text.insert(tk.END, f"  中性词汇: {sentiment_details.get('neutral', 0)} 次\n\n")
                            result_text.insert(tk.END, f"风险等级: {sentiment_analysis.get('risk_level', '未知')} (风险关键词出现 {sentiment_analysis.get('risk_count', 0)} 次)\n")
                            hot_themes = sentiment_analysis.get('hot_themes', [])
                            if hot_themes:
                                result_text.insert(tk.END, "\n热门主题:\n")
                                for theme, count in hot_themes:
                                    result_text.insert(tk.END, f"  {theme}: {count} 次\n")
                        else:
                            result_text.insert(tk.END, "情绪分析失败\n")
                        # 3. AI分析
                        result_text.insert(tk.END, "\n【三、AI深度分析】\n")
                        result_text.insert(tk.END, "-"*80 + "\n")
                        result_text.insert(tk.END, "正在调用AI进行分析,请稍候...\n")
                        analysis_window.update()
                        # 构建AI分析提示词
                        analysis_summary = f"""
根据以上资讯分析结果,请进行深度分析:
股票统计:
{chr(10).join([f"- {name}: 总出现{count}次" for name, count in sorted(stock_count_map.items(), key=lambda x: x[1], reverse=True)[:10]])}
情绪分析:
- 整体情绪: {sentiment_analysis.get('sentiment', '未知') if sentiment_analysis else '未知'}
- 市场状况: {sentiment_analysis.get('market_status', '未知') if sentiment_analysis else '未知'}
- 风险等级: {sentiment_analysis.get('risk_level', '未知') if sentiment_analysis else '未知'}
请基于以上数据,提供:
1. 市场趋势判断
2. 重点关注股票建议
3. 风险提示
4. 投资建议
"""
                        # 调用AI分析(使用主程序的AI配置)
                        try:
                            # 尝试获取主窗口的AI配置管理器和call_ai_model方法
                            main_window = None
                            # 向上查找主窗口
                            current = db_window
                            while current:
                                if hasattr(current, 'call_ai_model') and hasattr(current, 'ai_config_manager'):
                                    main_window = current
                                    break
                                current = getattr(current, 'master', None)
                            if main_window and hasattr(main_window, 'call_ai_model'):
                                ai_result = main_window.call_ai_model(
                                    analysis_summary,
                                    system_prompt="你是一个专业的股票市场分析师,请基于提供的数据进行深度分析。"
                                )
                                analysis_window.after(0, lambda r=ai_result: result_text.insert(tk.END, f"\n{r}\n"))
                            else:
                                # 如果无法获取,直接使用AIConfigManager
                                ai_config_manager = AIConfigManager()
                                provider_config = ai_config_manager.get_active_provider_config()
                                if provider_config and provider_config.get("api_key"):
                                    # 手动调用AI
                                    import requests
                                    base_url = provider_config.get("base_url", "")
                                    model = provider_config.get("model", "")
                                    api_key = provider_config.get("api_key", "")
                                    provider = ai_config_manager.config.get("active_provider", "deepseek")
                                    # 构建URL
                                    if provider == "deepseek":
                                        url = f"{base_url}/chat/completions"
                                    else:
                                        endpoint = provider_config.get("endpoint", "/chat/completions")
                                        url = f"{base_url}{endpoint}"
                                    headers = {
                                        "Content-Type": "application/json",
                                        "Authorization": f"Bearer {api_key}"
                                    }
                                    data = {
                                        "model": model,
                                        "messages": [
                                            {"role": "system", "content": "你是一个专业的股票市场分析师,请基于提供的数据进行深度分析。"},
                                            {"role": "user", "content": analysis_summary}
                                        ],
                                        "temperature": provider_config.get("temperature", 0.3)
                                    }
                                    response = requests.post(url, json=data, headers=headers, timeout=60)
                                    if response.status_code == 200:
                                        result = response.json()
                                        ai_result = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                                        analysis_window.after(0, lambda r=ai_result: result_text.insert(tk.END, f"\n{r}\n"))
                                    else:
                                        analysis_window.after(0, lambda: result_text.insert(tk.END, f"\nAI分析失败: HTTP {response.status_code}\n"))
                                else:
                                    analysis_window.after(0, lambda: result_text.insert(tk.END, "\nAI分析不可用:未配置AI接口\n"))
                        except Exception as e:
                            analysis_window.after(0, lambda e=str(e): result_text.insert(tk.END, f"\nAI分析出错: {e}\n"))
                        result_text.insert(tk.END, "\n" + "="*80 + "\n")
                        result_text.insert(tk.END, "分析完成\n")
                    except Exception as e:
                        analysis_window.after(0, lambda e=e: result_text.delete("1.0", tk.END) or
                                             result_text.insert("1.0", f"分析失败: {e!s}"))
                # 在后台线程中运行分析
                analysis_thread = threading.Thread(target=run_analysis, daemon=True)
                analysis_thread.start()
            def calculate_period_changes(news_tree, parent_window):
                """计算周期涨跌幅 - 从数据资讯表中选中数据进行一键资讯分析后得到的股票"""
                selection = news_tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择至少一条资讯")
                    return
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    # 收集所有选中资讯的内容和日期(与一键资讯分析逻辑一致)
                    all_contents = []
                    all_dates = []  # 存储所有日期
                    news_data_list = []  # 存储每条资讯的完整信息(包括tab_name)
                    for item_id in selection:
                        item = news_tree.item(item_id)
                        news_id = item['values'][0]
                        cursor.execute('SELECT tab_name, content, created_at, updated_at FROM news_info WHERE id = ?', (news_id,))
                        row = cursor.fetchone()
                        if row:
                            tab_name, content, created_at, updated_at = row
                            # 去除词云图片链接部分(与一键资讯分析逻辑一致)
                            import re
                            text_content = re.sub(r'\[词云图片\].*?图片链接:.*?\n', '', content, flags=re.DOTALL)
                            text_content = re.sub(r'文件路径:.*?\n', '', text_content)
                            all_contents.append(text_content)
                            news_data_list.append({
                                'tab_name': tab_name,
                                'content': text_content
                            })
                            # 提取日期(与一键资讯分析逻辑一致)
                            date_str = None
                            if created_at:
                                try:
                                    dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                                    date_str = dt.strftime("%Y-%m-%d")
                                    all_dates.append(dt)
                                except:
                                    date_str = created_at[:10] if len(created_at) >= 10 else created_at
                                    try:
                                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                                        all_dates.append(dt)
                                    except:
                                        pass
                            elif updated_at:
                                try:
                                    dt = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
                                    date_str = dt.strftime("%Y-%m-%d")
                                    all_dates.append(dt)
                                except:
                                    date_str = updated_at[:10] if len(updated_at) >= 10 else updated_at
                                    try:
                                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                                        all_dates.append(dt)
                                    except:
                                        pass
                    conn.close()
                    if not all_contents:
                        messagebox.showwarning("警告", "没有找到可分析的内容")
                        return
                    if not all_dates:
                        messagebox.showwarning("警告", "无法确定判断日期")
                        return
                    # 找到最后一天的生成时间作为判断日(与一键资讯分析逻辑一致)
                    judgment_date = max(all_dates).date()
                    judgment_date_str = judgment_date.strftime("%Y-%m-%d")
                    # 合并所有文本并提取股票名称(与一键资讯分析逻辑一致)
                    merged_text = "\n\n".join(all_contents)
                    # 提取所有股票名称(与一键资讯分析逻辑一致)
                    stock_names_all, _ = extract_stock_names(merged_text)
                    # 统计每个股票名称出现的总次数和来源标签页(与一键资讯分析逻辑一致)
                    stock_count_map = {}
                    stock_source_map = {}  # {股票名: {标签页名: 出现次数}}
                    for stock in stock_names_all:
                        # 清理股票名称(去除代码部分)
                        clean_name = stock.split('(')[0] if '(' in stock else stock
                        count = merged_text.count(clean_name)
                        if clean_name not in stock_count_map:
                            stock_count_map[clean_name] = 0
                            stock_source_map[clean_name] = {}
                        stock_count_map[clean_name] += count
                        # 统计每个标签页中该股票的出现次数
                        for news_data in news_data_list:
                            tab_name = news_data['tab_name']
                            content = news_data['content']
                            if clean_name in content:
                                if tab_name not in stock_source_map[clean_name]:
                                    stock_source_map[clean_name][tab_name] = 0
                                stock_source_map[clean_name][tab_name] += content.count(clean_name)
                    if not stock_count_map:
                        messagebox.showwarning("警告", "未发现股票名称")
                        return
                    # 按出现次数排序(使用股票名称作为标识)
                    sorted_stocks = sorted(stock_count_map.items(), key=lambda x: x[1], reverse=True)
                    # 创建选择窗口,让用户选择要计算前多少个股票
                    select_window = self._toplevel(parent_window)
                    select_window.title("选择计算股票数量")
                    select_window.geometry("600x400")
                    select_window.transient(parent_window)
                    select_window.grab_set()
                    # 居中显示
                    select_window.update_idletasks()
                    x = (select_window.winfo_screenwidth() // 2) - (select_window.winfo_width() // 2)
                    y = (select_window.winfo_screenheight() // 2) - (select_window.winfo_height() // 2)
                    select_window.geometry(f"+{x}+{y}")
                    info_frame = ttk.Frame(select_window, padding=20)
                    info_frame.pack(fill=tk.BOTH, expand=True)
                    ttk.Label(info_frame, text="统计结果", font=("TkDefaultFont", 12, "bold")).pack(pady=(0, 10))
                    ttk.Label(info_frame, text=f"判断日: {judgment_date_str}", font=("TkDefaultFont", 12)).pack(pady=2)
                    ttk.Label(info_frame, text=f"共发现 {len(sorted_stocks)} 只股票", font=("TkDefaultFont", 12)).pack(pady=5)
                    # 显示前10只股票预览(使用股票名称)
                    preview_text = scrolledtext.ScrolledText(info_frame, height=8, width=50, wrap=tk.WORD, font=("Consolas", 11))
                    preview_text.pack(pady=10, fill=tk.BOTH, expand=True)
                    preview_text.insert("1.0", "股票名称统计预览(按出现次数排序):\n\n")
                    for idx, (stock_name, count) in enumerate(sorted_stocks[:10], 1):
                        preview_text.insert(tk.END, f"{idx}. {stock_name}: 出现 {count} 次\n")
                    if len(sorted_stocks) > 10:
                        preview_text.insert(tk.END, f"... 还有 {len(sorted_stocks) - 10} 只股票\n")
                    preview_text.config(state=tk.DISABLED)
                    input_frame = ttk.Frame(info_frame)
                    input_frame.pack(pady=10)
                    ttk.Label(input_frame, text="分析前多少个股票:").pack(side=tk.LEFT, padx=5)
                    count_var = tk.StringVar(value=str(min(100, len(sorted_stocks))))
                    count_entry = ttk.Entry(input_frame, textvariable=count_var, width=10)
                    count_entry.pack(side=tk.LEFT, padx=5)
                    ttk.Label(input_frame, text=f"(最多 {len(sorted_stocks)} 只)").pack(side=tk.LEFT, padx=5)
                    def start_calculation():
                        try:
                            count = int(count_var.get())
                            if count <= 0:
                                messagebox.showwarning("警告", "请输入大于0的数字", parent=select_window)
                                return
                            count = min(count, len(sorted_stocks))
                            select_window.destroy()
                            show_calculation_window(sorted_stocks[:count], stock_source_map, judgment_date_str, judgment_date, parent_window, news_data_list)
                        except ValueError:
                            messagebox.showwarning("警告", "请输入有效的数字", parent=select_window)
                    button_frame = ttk.Frame(info_frame)
                    button_frame.pack(pady=10)
                    ttk.Button(button_frame, text="开始计算", command=start_calculation, width=15).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="取消", command=select_window.destroy, width=15).pack(side=tk.LEFT, padx=5)
                    # 绑定回车键
                    count_entry.bind('<Return>', lambda e: start_calculation())
                    count_entry.focus()
                    return  # 等待用户选择后再继续
                except Exception as e:
                    messagebox.showerror("错误", f"分析失败: {e!s}", parent=parent_window)
                    import traceback
                    traceback.print_exc()
            def show_calculation_window(sorted_stocks, stock_source_map, judgment_date_str, judgment_date, parent_window, news_data_list=None):
                """显示计算窗口并开始计算"""
                # 创建结果窗口
                result_window = self._toplevel(parent_window)
                result_window.title(f"周期涨跌幅分析 - 判断日: {judgment_date_str}")
                result_window.geometry("1200x900")
                # 创建工具栏
                toolbar_frame = ttk.Frame(result_window, padding=5)
                toolbar_frame.pack(fill=tk.X)
                ttk.Label(toolbar_frame, text=f"判断日: {judgment_date_str}", font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT, padx=5)
                ttk.Label(toolbar_frame, text=f"共 {len(sorted_stocks)} 只股票", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=5)
                # 市场情绪分析区域(已移除涨跌停数据获取和计算)
                # sentiment_frame = ttk.LabelFrame(result_window, text="判断日市场情绪分析", padding=10)
                # sentiment_frame.pack(fill=tk.X, padx=10, pady=5)
                #
                # sentiment_info_label = ttk.Label(sentiment_frame, text="正在获取市场数据...", font=("TkDefaultFont", 11))
                # sentiment_info_label.pack(side=tk.LEFT, padx=5)
                #
                # # 温度计画布
                # thermometer_canvas = tk.Canvas(sentiment_frame, width=100, height=200, bg="white", highlightthickness=1, highlightbackground="gray")
                # thermometer_canvas.pack(side=tk.RIGHT, padx=10)
                def analyze_market_sentiment():
                    """分析判断日的市场情绪(已禁用涨跌停数据获取)"""
                    # 已移除市场涨跌停数据获取和计算功能
                    return
                def draw_thermometer(canvas, value, level):
                    """绘制温度计显示市场情绪"""
                    canvas.delete("all")
                    width = 100
                    # 温度计外框
                    canvas.create_rectangle(30, 20, 70, 180, outline="black", width=2)
                    # 温度计底部圆形
                    canvas.create_oval(25, 175, 75, 185, outline="black", width=2)
                    # 根据情绪值填充颜色
                    if level == "狂热":
                        color = "red"
                    elif level == "积极":
                        color = "orange"
                    elif level == "不积极":
                        color = "yellow"
                    else:  # 冰点
                        color = "blue"
                    # 计算填充高度(从底部向上)
                    fill_height = int((value / 100) * 140)  # 140是温度计有效高度
                    fill_top = 180 - fill_height
                    # 填充温度计
                    canvas.create_rectangle(32, fill_top, 68, 178, fill=color, outline="")
                    canvas.create_oval(27, 177, 73, 183, fill=color, outline="")
                    # 刻度线
                    for i in range(0, 101, 20):
                        y_pos = 180 - int((i / 100) * 140)
                        canvas.create_line(28, y_pos, 32, y_pos, width=1)
                        canvas.create_text(20, y_pos, text=f"{i}%", font=("Arial", 8))
                    # 显示情绪等级
                    canvas.create_text(width // 2, 10, text=level, font=("Arial", 12, "bold"), fill=color)
                    canvas.create_text(width // 2, 195, text=f"{value}%", font=("Arial", 10))
                # 市场情绪分析已移除,不再获取涨跌停数据
                # sentiment_thread = threading.Thread(target=analyze_market_sentiment, daemon=True)
                # sentiment_thread.start()
                # 保存按钮
                def save_results():
                    """保存计算结果为资讯"""
                    try:
                        from tkinter import filedialog
                        filename = filedialog.asksaveasfilename(
                            defaultextension=".txt",
                            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                            initialfile=f"周期涨跌幅分析_{judgment_date_str}.txt"
                        )
                        if filename:
                            with open(filename, 'w', encoding='utf-8') as f:
                                f.write(result_text.get("1.0", tk.END))
                            messagebox.showinfo("成功", f"已保存到: {filename}")
                    except Exception as e:
                        messagebox.showerror("错误", f"保存失败: {e}")
                def save_to_news():
                    """保存计算结果到资讯数据库"""
                    try:
                        content = result_text.get("1.0", tk.END)
                        if not content.strip():
                            messagebox.showwarning("警告", "没有可保存的内容")
                            return
                        tab_name = f"周期涨跌幅分析_{judgment_date_str}"
                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO news_info (tab_name, content, created_at, updated_at)
                            VALUES (?, ?, ?, ?)
                        ''', (tab_name, content, current_time, current_time))
                        conn.commit()
                        conn.close()
                        messagebox.showinfo("成功", "已保存到资讯数据库")
                        # 刷新资讯数据表
                        if hasattr(parent_window, 'refresh_news_data'):
                            parent_window.refresh_news_data()
                    except Exception as e:
                        messagebox.showerror("错误", f"保存失败: {e}")
                ttk.Button(toolbar_frame, text="保存为文件", command=save_results, width=12).pack(side=tk.LEFT, padx=5)
                ttk.Button(toolbar_frame, text="保存为资讯", command=save_to_news, width=12).pack(side=tk.LEFT, padx=5)
                # 存储计算结果(用于回测分析)
                stored_results = []
                # 回测分析按钮
                def show_backtest_analysis():
                    """显示回测分析窗口"""
                    # 创建回测分析选择窗口
                    backtest_window = self._toplevel(result_window)
                    backtest_window.title("回测分析")
                    backtest_window.geometry("500x350")
                    backtest_window.transient(result_window)
                    backtest_window.grab_set()
                    # 选择计算类型
                    choice_frame = ttk.LabelFrame(backtest_window, text="选择计算类型", padding=20)
                    choice_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
                    choice_var = tk.IntVar(value=1)
                    ttk.Radiobutton(choice_frame, text="1. 计算所有股票", variable=choice_var, value=1).pack(anchor=tk.W, pady=5)
                    ttk.Radiobutton(choice_frame, text="2. 计算均线全部通过的股票", variable=choice_var, value=2).pack(anchor=tk.W, pady=5)
                    ttk.Radiobutton(choice_frame, text="3. 自定义股票和日期回测", variable=choice_var, value=3).pack(anchor=tk.W, pady=5)
                    def start_backtest():
                        choice = choice_var.get()
                        backtest_window.destroy()
                        if choice == 3:
                            show_custom_backtest_window()
                        else:
                            if not stored_results:
                                messagebox.showwarning("警告", "请先完成周期涨跌幅计算", parent=result_window)
                                return
                            perform_backtest(choice)
                    button_frame = ttk.Frame(backtest_window)
                    button_frame.pack(fill=tk.X, padx=20, pady=10)
                    ttk.Button(button_frame, text="开始回测", command=start_backtest, width=12).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="取消", command=backtest_window.destroy, width=12).pack(side=tk.RIGHT, padx=5)
                def show_custom_backtest_window():
                    """显示自定义回测窗口"""
                    custom_window = self._toplevel(result_window)
                    custom_window.title("自定义回测分析")
                    custom_window.geometry("700x600")
                    custom_window.transient(result_window)
                    custom_window.grab_set()
                    # 股票输入区域
                    stock_frame = ttk.LabelFrame(custom_window, text="股票列表(每行一个股票名称或代码)", padding=10)
                    stock_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                    stock_text = scrolledtext.ScrolledText(stock_frame, height=10, wrap=tk.WORD)
                    stock_text.pack(fill=tk.BOTH, expand=True)
                    # 按钮区域
                    stock_btn_frame = ttk.Frame(stock_frame)
                    stock_btn_frame.pack(fill=tk.X, pady=(5, 0))
                    ttk.Button(stock_btn_frame, text="从文件导入", command=lambda: import_stocks_from_file(stock_text), width=12).pack(side=tk.LEFT, padx=2)
                    ttk.Button(stock_btn_frame, text="粘贴", command=lambda: paste_stocks(stock_text), width=12).pack(side=tk.LEFT, padx=2)
                    ttk.Button(stock_btn_frame, text="清空", command=lambda: stock_text.delete("1.0", tk.END), width=12).pack(side=tk.LEFT, padx=2)
                    # 日期设置区域
                    date_frame = ttk.LabelFrame(custom_window, text="日期设置", padding=10)
                    date_frame.pack(fill=tk.X, padx=10, pady=5)
                    ttk.Label(date_frame, text="买入日期:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
                    buy_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
                    buy_date_entry = ttk.Entry(date_frame, textvariable=buy_date_var, width=12)
                    buy_date_entry.grid(row=0, column=1, padx=5, pady=5)
                    ttk.Button(date_frame, text="今天", command=lambda: buy_date_var.set(datetime.now().strftime("%Y-%m-%d")), width=8).grid(row=0, column=2, padx=5, pady=5)
                    ttk.Label(date_frame, text="卖出日期:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
                    sell_date_var = tk.StringVar(value="")
                    sell_date_entry = ttk.Entry(date_frame, textvariable=sell_date_var, width=12)
                    sell_date_entry.grid(row=1, column=1, padx=5, pady=5)
                    ttk.Label(date_frame, text="(留空表示计算至今)", font=("TkDefaultFont", 8)).grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)
                    def import_stocks_from_file(text_widget):
                        """从文件导入股票"""
                        filename = filedialog.askopenfilename(
                            title="选择股票文件",
                            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
                        )
                        if filename:
                            try:
                                with open(filename, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                text_widget.delete("1.0", tk.END)
                                text_widget.insert("1.0", content)
                            except Exception as e:
                                messagebox.showerror("错误", f"导入失败: {e}", parent=custom_window)
                    def paste_stocks(text_widget):
                        """粘贴股票"""
                        try:
                            clipboard_text = custom_window.clipboard_get()
                            text_widget.delete("1.0", tk.END)
                            text_widget.insert("1.0", clipboard_text)
                        except:
                            messagebox.showwarning("警告", "剪贴板为空或无法获取", parent=custom_window)
                    def start_custom_backtest():
                        """开始自定义回测"""
                        stock_content = stock_text.get("1.0", tk.END).strip()
                        if not stock_content:
                            messagebox.showwarning("警告", "请输入股票列表", parent=custom_window)
                            return
                        # 解析股票列表
                        stock_lines = [line.strip() for line in stock_content.split('\n') if line.strip()]
                        if not stock_lines:
                            messagebox.showwarning("警告", "股票列表为空", parent=custom_window)
                            return
                        # 解析买入日期
                        try:
                            buy_date_str = buy_date_var.get().strip()
                            buy_date = datetime.strptime(buy_date_str, "%Y-%m-%d").date()
                        except:
                            messagebox.showerror("错误", "买入日期格式错误,请使用 YYYY-MM-DD 格式", parent=custom_window)
                            return
                        # 解析卖出日期(可选)
                        sell_date = None
                        sell_date_str = sell_date_var.get().strip()
                        if sell_date_str:
                            try:
                                sell_date = datetime.strptime(sell_date_str, "%Y-%m-%d").date()
                                if sell_date < buy_date:
                                    messagebox.showerror("错误", "卖出日期不能早于买入日期", parent=custom_window)
                                    return
                            except:
                                messagebox.showerror("错误", "卖出日期格式错误,请使用 YYYY-MM-DD 格式", parent=custom_window)
                                return
                        custom_window.destroy()
                        perform_custom_backtest(stock_lines, buy_date, sell_date)
                    button_frame = ttk.Frame(custom_window)
                    button_frame.pack(fill=tk.X, padx=10, pady=10)
                    ttk.Button(button_frame, text="开始回测", command=start_custom_backtest, width=12).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="取消", command=custom_window.destroy, width=12).pack(side=tk.RIGHT, padx=5)
                def perform_backtest(choice):
                    """执行回测分析"""
                    # 筛选股票
                    if choice == 1:
                        # 计算所有股票
                        target_stocks = [r for r in stored_results if 'error' not in r and 'stock_code' in r and r['stock_code'] != '未找到']
                    else:
                        # 只计算均线全部通过的股票
                        target_stocks = []
                        for r in stored_results:
                            if 'error' in r or 'stock_code' not in r or r['stock_code'] == '未找到':
                                continue
                            if r.get('ma_detection'):
                                ma_det = r['ma_detection']
                                ma1_ok = ma_det.get('ma1') and ma_det['ma1'].get('crossed') and ma_det['ma1'].get('uptrend')
                                ma5_ok = ma_det.get('ma5') and ma_det['ma5'].get('crossed') and ma_det['ma5'].get('uptrend')
                                ma10_ok = ma_det.get('ma10') and ma_det['ma10'].get('crossed') and ma_det['ma10'].get('uptrend')
                                ma20_ok = ma_det.get('ma20') and ma_det['ma20'].get('crossed') and ma_det['ma20'].get('uptrend')
                                if ma1_ok and ma5_ok and ma10_ok and ma20_ok:
                                    target_stocks.append(r)
                    if not target_stocks:
                        messagebox.showinfo("提示", "没有符合条件的股票进行回测", parent=result_window)
                        return
                    # 创建回测结果窗口
                    backtest_result_window = self._toplevel(result_window)
                    backtest_result_window.title(f"回测分析结果 - {'所有股票' if choice == 1 else '均线全部通过股票'}")
                    backtest_result_window.geometry("1000x700")
                    # 创建结果显示区域
                    result_text_backtest = scrolledtext.ScrolledText(backtest_result_window, wrap=tk.WORD, font=("Consolas", 11))
                    result_text_backtest.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                    result_text_backtest.insert("1.0", "="*100 + "\n")
                    result_text_backtest.insert(tk.END, "回测分析报告\n")
                    result_text_backtest.insert(tk.END, f"计算类型: {'所有股票' if choice == 1 else '均线全部通过股票'}\n")
                    result_text_backtest.insert(tk.END, f"判断日: {judgment_date_str}\n")
                    result_text_backtest.insert(tk.END, f"回测股票数量: {len(target_stocks)}\n")
                    result_text_backtest.insert(tk.END, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    result_text_backtest.insert(tk.END, "="*100 + "\n\n")
                    result_text_backtest.insert(tk.END, "正在计算回测结果,请稍候...\n\n")
                    backtest_result_window.update_idletasks()
                    # 在后台线程中执行回测
                    def backtest_thread():
                        try:
                            backtest_results = []
                            judgment_date_obj = judgment_date
                            # 本金1000万
                            total_capital = 10000000  # 1000万
                            for stock_result in target_stocks:
                                stock_name = stock_result['stock_name']
                                stock_code = stock_result['stock_code']
                                try:
                                    if not AKSHARE_AVAILABLE:
                                        continue
                                    # 获取历史数据
                                    hist_data = ak.stock_zh_a_hist(
                                        symbol=stock_code,
                                        period="daily",
                                        adjust="qfq"
                                    )
                                    if hist_data is None or hist_data.empty:
                                        continue
                                    # 转换日期格式
                                    hist_data['日期'] = pd.to_datetime(hist_data['日期']).dt.date
                                    # 找到判断日的数据
                                    judgment_data = hist_data[hist_data['日期'] == judgment_date_obj]
                                    if judgment_data.empty:
                                        # 找最近的数据
                                        before_data = hist_data[hist_data['日期'] <= judgment_date_obj]
                                        if before_data.empty:
                                            continue
                                        judgment_data = before_data.tail(1)
                                    judgment_date_actual = judgment_data.iloc[0]['日期']
                                    # 找到判断日次日的开盘价(买入价)
                                    after_judgment = hist_data[hist_data['日期'] > judgment_date_actual].copy()
                                    if after_judgment.empty:
                                        continue
                                    # 判断日次日(第一个交易日)
                                    next_day_data = after_judgment.head(1)
                                    if next_day_data.empty:
                                        continue
                                    next_day = next_day_data.iloc[0]['日期']
                                    open_price = float(next_day_data.iloc[0]['开盘'])
                                    close_price_prev = float(judgment_data.iloc[0]['收盘'])
                                    # 判断是否一字涨停板(开盘价等于或接近涨停价)
                                    # 涨停价 = 前一日收盘价 * 1.1(主板)或 1.2(创业板/科创板)
                                    # 简化处理:如果开盘价 >= 前一日收盘价 * 1.09,认为是涨停板
                                    limit_up_price = close_price_prev * 1.1
                                    if open_price >= limit_up_price * 0.99:  # 允许0.1%误差
                                        # 一字涨停板,买不进,跳过
                                        continue
                                    buy_price = open_price
                                    # 计算各个时间点的盈亏
                                    backtest_data = {
                                        'stock_name': stock_name,
                                        'stock_code': stock_code,
                                        'buy_date': next_day.strftime('%Y-%m-%d'),
                                        'buy_price': buy_price,
                                        'day0_pct': None,  # 当天收盘
                                        'day3_pct': None,  # 持股3天
                                        'day5_pct': None,  # 持股5天
                                        'day10_pct': None,  # 持股10天
                                        'day20_pct': None,  # 持股20天
                                    }
                                    # 当天收盘盈亏
                                    day0_close = float(next_day_data.iloc[0]['收盘'])
                                    backtest_data['day0_pct'] = ((day0_close - buy_price) / buy_price) * 100
                                    # 持股3天盈亏
                                    if len(after_judgment) >= 3:
                                        day3_data = after_judgment.head(3).iloc[-1]
                                        day3_close = float(day3_data['收盘'])
                                        backtest_data['day3_pct'] = ((day3_close - buy_price) / buy_price) * 100
                                    # 持股5天盈亏
                                    if len(after_judgment) >= 5:
                                        day5_data = after_judgment.head(5).iloc[-1]
                                        day5_close = float(day5_data['收盘'])
                                        backtest_data['day5_pct'] = ((day5_close - buy_price) / buy_price) * 100
                                    # 持股10天盈亏
                                    if len(after_judgment) >= 10:
                                        day10_data = after_judgment.head(10).iloc[-1]
                                        day10_close = float(day10_data['收盘'])
                                        backtest_data['day10_pct'] = ((day10_close - buy_price) / buy_price) * 100
                                    # 持股20天盈亏
                                    if len(after_judgment) >= 20:
                                        day20_data = after_judgment.head(20).iloc[-1]
                                        day20_close = float(day20_data['收盘'])
                                        backtest_data['day20_pct'] = ((day20_close - buy_price) / buy_price) * 100
                                    backtest_results.append(backtest_data)
                                except Exception as e:
                                    print(f"回测计算失败 {stock_name}: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    continue
                            # 计算每只股票的买入金额和市值
                            if backtest_results:
                                # 每只股票的买入金额 = 本金 / 股票数量
                                capital_per_stock = total_capital / len(backtest_results)
                                for r in backtest_results:
                                    r['buy_amount'] = capital_per_stock  # 买入金额
                                    # 计算各个时间点的市值
                                    if r['day0_pct'] is not None:
                                        r['day0_value'] = capital_per_stock * (1 + r['day0_pct'] / 100)
                                    if r['day3_pct'] is not None:
                                        r['day3_value'] = capital_per_stock * (1 + r['day3_pct'] / 100)
                                    if r['day5_pct'] is not None:
                                        r['day5_value'] = capital_per_stock * (1 + r['day5_pct'] / 100)
                                    if r['day10_pct'] is not None:
                                        r['day10_value'] = capital_per_stock * (1 + r['day10_pct'] / 100)
                                    if r['day20_pct'] is not None:
                                        r['day20_value'] = capital_per_stock * (1 + r['day20_pct'] / 100)
                            # 计算全仓盈亏(按股票数平均百分比)和总体市值变化
                            def display_backtest_results():
                                try:
                                    result_text_backtest.delete("1.0", tk.END)
                                    result_text_backtest.insert("1.0", "="*100 + "\n")
                                    result_text_backtest.insert(tk.END, "回测分析报告\n")
                                    result_text_backtest.insert(tk.END, f"计算类型: {'所有股票' if choice == 1 else '均线全部通过股票'}\n")
                                    result_text_backtest.insert(tk.END, f"判断日: {judgment_date_str}\n")
                                    result_text_backtest.insert(tk.END, f"回测股票数量: {len(backtest_results)}\n")
                                    result_text_backtest.insert(tk.END, "本金: 1000万元\n")
                                    result_text_backtest.insert(tk.END, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                    result_text_backtest.insert(tk.END, "="*100 + "\n\n")
                                    if not backtest_results:
                                        result_text_backtest.insert(tk.END, "没有符合条件的股票进行回测(可能都是一字涨停板买不进)\n")
                                        return
                                    # 计算总体市值变化(本金1000万,按股票数平均分配)
                                    total_capital = 10000000  # 1000万
                                    capital_per_stock = total_capital / len(backtest_results)
                                    # 计算各个时间点的总体市值
                                    total_value_day0 = sum(r.get('day0_value', 0) for r in backtest_results if 'day0_value' in r)
                                    total_value_day3 = sum(r.get('day3_value', 0) for r in backtest_results if 'day3_value' in r)
                                    total_value_day5 = sum(r.get('day5_value', 0) for r in backtest_results if 'day5_value' in r)
                                    total_value_day10 = sum(r.get('day10_value', 0) for r in backtest_results if 'day10_value' in r)
                                    total_value_day20 = sum(r.get('day20_value', 0) for r in backtest_results if 'day20_value' in r)
                                    # 计算总体盈亏金额和百分比
                                    result_text_backtest.insert(tk.END, "【总体市值变化统计】\n", "bold")
                                    result_text_backtest.insert(tk.END, f"初始本金: {total_capital/10000:.2f}万元\n")
                                    result_text_backtest.insert(tk.END, f"每只股票买入金额: {capital_per_stock/10000:.2f}万元\n\n")
                                    if total_value_day0 > 0:
                                        profit_day0 = total_value_day0 - total_capital
                                        profit_pct_day0 = (profit_day0 / total_capital) * 100
                                        tag = "red" if profit_day0 > 0 else "green"
                                        result_text_backtest.insert(tk.END, f"当天收盘总体市值: {total_value_day0/10000:.2f}万元  ", tag)
                                        result_text_backtest.insert(tk.END, f"盈亏: {profit_day0/10000:.2f}万元 ({profit_pct_day0:+.2f}%)\n", tag)
                                    if total_value_day3 > 0:
                                        profit_day3 = total_value_day3 - total_capital
                                        profit_pct_day3 = (profit_day3 / total_capital) * 100
                                        tag = "red" if profit_day3 > 0 else "green"
                                        result_text_backtest.insert(tk.END, f"持股3天总体市值: {total_value_day3/10000:.2f}万元  ", tag)
                                        result_text_backtest.insert(tk.END, f"盈亏: {profit_day3/10000:.2f}万元 ({profit_pct_day3:+.2f}%)\n", tag)
                                    if total_value_day5 > 0:
                                        profit_day5 = total_value_day5 - total_capital
                                        profit_pct_day5 = (profit_day5 / total_capital) * 100
                                        tag = "red" if profit_day5 > 0 else "green"
                                        result_text_backtest.insert(tk.END, f"持股5天总体市值: {total_value_day5/10000:.2f}万元  ", tag)
                                        result_text_backtest.insert(tk.END, f"盈亏: {profit_day5/10000:.2f}万元 ({profit_pct_day5:+.2f}%)\n", tag)
                                    if total_value_day10 > 0:
                                        profit_day10 = total_value_day10 - total_capital
                                        profit_pct_day10 = (profit_day10 / total_capital) * 100
                                        tag = "red" if profit_day10 > 0 else "green"
                                        result_text_backtest.insert(tk.END, f"持股10天总体市值: {total_value_day10/10000:.2f}万元  ", tag)
                                        result_text_backtest.insert(tk.END, f"盈亏: {profit_day10/10000:.2f}万元 ({profit_pct_day10:+.2f}%)\n", tag)
                                    if total_value_day20 > 0:
                                        profit_day20 = total_value_day20 - total_capital
                                        profit_pct_day20 = (profit_day20 / total_capital) * 100
                                        tag = "red" if profit_day20 > 0 else "green"
                                        result_text_backtest.insert(tk.END, f"持股20天总体市值: {total_value_day20/10000:.2f}万元  ", tag)
                                        result_text_backtest.insert(tk.END, f"盈亏: {profit_day20/10000:.2f}万元 ({profit_pct_day20:+.2f}%)\n", tag)
                                    # 计算全仓盈亏(按股票数平均百分比)
                                    total_day0 = sum(r['day0_pct'] for r in backtest_results if r['day0_pct'] is not None)
                                    total_day3 = sum(r['day3_pct'] for r in backtest_results if r['day3_pct'] is not None)
                                    total_day5 = sum(r['day5_pct'] for r in backtest_results if r['day5_pct'] is not None)
                                    total_day10 = sum(r['day10_pct'] for r in backtest_results if r['day10_pct'] is not None)
                                    total_day20 = sum(r['day20_pct'] for r in backtest_results if r['day20_pct'] is not None)
                                    count_day0 = sum(1 for r in backtest_results if r['day0_pct'] is not None)
                                    count_day3 = sum(1 for r in backtest_results if r['day3_pct'] is not None)
                                    count_day5 = sum(1 for r in backtest_results if r['day5_pct'] is not None)
                                    count_day10 = sum(1 for r in backtest_results if r['day10_pct'] is not None)
                                    count_day20 = sum(1 for r in backtest_results if r['day20_pct'] is not None)
                                    result_text_backtest.insert(tk.END, "\n【全仓盈亏百分比统计】\n", "bold")
                                    if count_day0 > 0:
                                        avg_day0 = total_day0 / count_day0
                                        result_text_backtest.insert(tk.END, f"当天收盘全仓盈亏: {avg_day0:.2f}% (共{count_day0}只股票)\n")
                                    if count_day3 > 0:
                                        avg_day3 = total_day3 / count_day3
                                        result_text_backtest.insert(tk.END, f"持股3天全仓盈亏: {avg_day3:.2f}% (共{count_day3}只股票)\n")
                                    if count_day5 > 0:
                                        avg_day5 = total_day5 / count_day5
                                        result_text_backtest.insert(tk.END, f"持股5天全仓盈亏: {avg_day5:.2f}% (共{count_day5}只股票)\n")
                                    if count_day10 > 0:
                                        avg_day10 = total_day10 / count_day10
                                        result_text_backtest.insert(tk.END, f"持股10天全仓盈亏: {avg_day10:.2f}% (共{count_day10}只股票)\n")
                                    if count_day20 > 0:
                                        avg_day20 = total_day20 / count_day20
                                        result_text_backtest.insert(tk.END, f"持股20天全仓盈亏: {avg_day20:.2f}% (共{count_day20}只股票)\n")
                                    result_text_backtest.insert(tk.END, "\n" + "="*100 + "\n\n")
                                    result_text_backtest.insert(tk.END, "【个股回测详情】\n", "bold")
                                    for idx, r in enumerate(backtest_results, 1):
                                        result_text_backtest.insert(tk.END, f"\n【{idx}】{r['stock_name']} ({r['stock_code']})\n", "bold")
                                        buy_amount = r.get('buy_amount', total_capital / len(backtest_results))
                                        result_text_backtest.insert(tk.END, f"买入日期: {r['buy_date']}  买入价: {r['buy_price']:.2f}  买入金额: {buy_amount/10000:.2f}万元\n")
                                        if r['day0_pct'] is not None:
                                            tag = "red" if r['day0_pct'] > 0 else "green"
                                            day0_value = r.get('day0_value', buy_amount * (1 + r['day0_pct'] / 100))
                                            result_text_backtest.insert(tk.END, f"当天收盘盈亏: {r['day0_pct']:.2f}%  市值: {day0_value/10000:.2f}万元\n", tag)
                                        if r['day3_pct'] is not None:
                                            tag = "red" if r['day3_pct'] > 0 else "green"
                                            day3_value = r.get('day3_value', buy_amount * (1 + r['day3_pct'] / 100))
                                            result_text_backtest.insert(tk.END, f"持股3天盈亏: {r['day3_pct']:.2f}%  市值: {day3_value/10000:.2f}万元\n", tag)
                                        if r['day5_pct'] is not None:
                                            tag = "red" if r['day5_pct'] > 0 else "green"
                                            day5_value = r.get('day5_value', buy_amount * (1 + r['day5_pct'] / 100))
                                            result_text_backtest.insert(tk.END, f"持股5天盈亏: {r['day5_pct']:.2f}%  市值: {day5_value/10000:.2f}万元\n", tag)
                                        if r['day10_pct'] is not None:
                                            tag = "red" if r['day10_pct'] > 0 else "green"
                                            day10_value = r.get('day10_value', buy_amount * (1 + r['day10_pct'] / 100))
                                            result_text_backtest.insert(tk.END, f"持股10天盈亏: {r['day10_pct']:.2f}%  市值: {day10_value/10000:.2f}万元\n", tag)
                                        if r['day20_pct'] is not None:
                                            tag = "red" if r['day20_pct'] > 0 else "green"
                                            day20_value = r.get('day20_value', buy_amount * (1 + r['day20_pct'] / 100))
                                            result_text_backtest.insert(tk.END, f"持股20天盈亏: {r['day20_pct']:.2f}%  市值: {day20_value/10000:.2f}万元\n", tag)
                                    result_text_backtest.insert(tk.END, "\n" + "="*100 + "\n")
                                    result_text_backtest.insert(tk.END, "回测分析完成\n")
                                    # 配置颜色标签
                                    result_text_backtest.tag_config("red", foreground="red")
                                    result_text_backtest.tag_config("green", foreground="green")
                                    result_text_backtest.tag_config("bold", font=("Consolas", 11, "bold"))
                                except Exception as e:
                                    import traceback
                                    traceback.print_exc()
                                    result_text_backtest.delete("1.0", tk.END)
                                    result_text_backtest.insert("1.0", f"显示回测结果失败: {e!s}\n")
                            backtest_result_window.after(0, display_backtest_results)
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            def show_error(e=e):
                                result_text_backtest.delete("1.0", tk.END)
                                result_text_backtest.insert("1.0", f"回测计算失败: {e!s}\n")
                                result_text_backtest.insert(tk.END, traceback.format_exc())
                            backtest_result_window.after(0, show_error)
                    thread = threading.Thread(target=backtest_thread, daemon=True)
                    thread.start()
                def perform_custom_backtest(stock_lines, buy_date, sell_date=None):
                    """执行自定义回测分析"""
                    try:
                        # 解析股票代码
                        target_stocks = []
                        STOCK_NAME_TO_CODE, STOCK_CODES_DICT, _ = load_stock_names()
                        for line in stock_lines:
                            stock_code = None
                            stock_name = None
                            # 尝试提取6位数字代码
                            code_match = re.search(r'(\d{6})', line)
                            if code_match:
                                code = code_match.group(1)
                                if code in STOCK_CODES_DICT:
                                    stock_code = code
                                    stock_name = STOCK_CODES_DICT[code]
                            # 如果没有找到代码,尝试查找名称
                            if not stock_name:
                                clean_name = line.split('(')[0].strip()
                                if clean_name in STOCK_NAME_TO_CODE:
                                    stock_name = clean_name
                                    stock_code = STOCK_NAME_TO_CODE[clean_name]
                                else:
                                    stock_code = get_stock_code_by_name(clean_name)
                                    if stock_code:
                                        stock_name = STOCK_CODES_DICT.get(stock_code, clean_name)
                            if stock_code and stock_name:
                                target_stocks.append((stock_name, stock_code))
                        if not target_stocks:
                            messagebox.showwarning("警告", "没有找到有效的股票", parent=parent_window)
                            return
                        # 创建回测结果窗口(使用result_window作为父窗口,确保窗口存在)
                        try:
                            if not result_window.winfo_exists():
                                messagebox.showerror("错误", "父窗口已关闭")
                                return
                        except:
                            # 如果result_window不存在,尝试使用parent_window
                            try:
                                if not parent_window.winfo_exists():
                                    messagebox.showerror("错误", "父窗口已关闭")
                                    return
                                result_window = parent_window
                            except:
                                messagebox.showerror("错误", "无法创建回测结果窗口")
                                return
                        backtest_result_window = self._toplevel(result_window)
                        buy_date_str = buy_date.strftime('%Y-%m-%d')
                        sell_date_str = sell_date.strftime('%Y-%m-%d') if sell_date else "至今"
                        backtest_result_window.title(f"自定义回测分析结果 - 买入日: {buy_date_str} 卖出日: {sell_date_str}")
                        backtest_result_window.geometry("1000x700")
                        # 创建结果显示区域
                        result_text_backtest = scrolledtext.ScrolledText(backtest_result_window, wrap=tk.WORD, font=("Consolas", 11))
                        result_text_backtest.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                        result_text_backtest.insert("1.0", "="*100 + "\n")
                        result_text_backtest.insert(tk.END, "自定义回测分析报告\n")
                        result_text_backtest.insert(tk.END, f"买入日期: {buy_date_str}\n")
                        result_text_backtest.insert(tk.END, f"卖出日期: {sell_date_str}\n")
                        result_text_backtest.insert(tk.END, f"回测股票数量: {len(target_stocks)}\n")
                        result_text_backtest.insert(tk.END, "本金: 1000万元\n")
                        result_text_backtest.insert(tk.END, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        result_text_backtest.insert(tk.END, "="*100 + "\n\n")
                        result_text_backtest.insert(tk.END, "正在计算回测结果,请稍候...\n\n")
                        backtest_result_window.update_idletasks()
                        # 在后台线程中执行回测
                        def custom_backtest_thread():
                            try:
                                backtest_results = []
                                total_capital = 10000000  # 1000万
                                for stock_name, stock_code in target_stocks:
                                    try:
                                        if not AKSHARE_AVAILABLE:
                                            continue
                                        # 获取历史数据
                                        hist_data = ak.stock_zh_a_hist(
                                            symbol=stock_code,
                                            period="daily",
                                            adjust="qfq"
                                        )
                                        if hist_data is None or hist_data.empty:
                                            continue
                                        # 转换日期格式
                                        hist_data['日期'] = pd.to_datetime(hist_data['日期']).dt.date
                                        # 找到买入日的数据
                                        buy_data = hist_data[hist_data['日期'] == buy_date]
                                        if buy_data.empty:
                                            # 找最近的数据
                                            before_buy = hist_data[hist_data['日期'] <= buy_date]
                                            if before_buy.empty:
                                                continue
                                            buy_data = before_buy.tail(1)
                                        buy_date_actual = buy_data.iloc[0]['日期']
                                        # 找到买入日次日的开盘价(买入价)
                                        after_buy = hist_data[hist_data['日期'] > buy_date_actual].copy()
                                        if after_buy.empty:
                                            continue
                                        # 买入日次日(第一个交易日)
                                        next_day_data = after_buy.head(1)
                                        if next_day_data.empty:
                                            continue
                                        next_day = next_day_data.iloc[0]['日期']
                                        open_price = float(next_day_data.iloc[0]['开盘'])
                                        close_price_prev = float(buy_data.iloc[0]['收盘'])
                                        # 判断是否一字涨停板
                                        limit_up_price = close_price_prev * 1.1
                                        if open_price >= limit_up_price * 0.99:
                                            continue
                                        buy_price = open_price
                                        # 计算卖出价
                                        sell_price = None
                                        sell_date_actual = None
                                        profit_pct = None
                                        if sell_date:
                                            # 有指定卖出日期
                                            sell_data = hist_data[hist_data['日期'] == sell_date]
                                            if sell_data.empty:
                                                # 找最近的数据
                                                before_sell = hist_data[hist_data['日期'] <= sell_date]
                                                if not before_sell.empty:
                                                    sell_data = before_sell.tail(1)
                                            if not sell_data.empty:
                                                sell_date_actual = sell_data.iloc[0]['日期']
                                                sell_price = float(sell_data.iloc[0]['收盘'])
                                                profit_pct = ((sell_price - buy_price) / buy_price) * 100
                                        else:
                                            # 计算至今
                                            latest_data = hist_data.tail(1)
                                            if not latest_data.empty:
                                                sell_date_actual = latest_data.iloc[0]['日期']
                                                sell_price = float(latest_data.iloc[0]['收盘'])
                                                profit_pct = ((sell_price - buy_price) / buy_price) * 100
                                        if sell_price is None:
                                            continue
                                        backtest_data = {
                                            'stock_name': stock_name,
                                            'stock_code': stock_code,
                                            'buy_date': next_day.strftime('%Y-%m-%d'),
                                            'buy_price': buy_price,
                                            'sell_date': sell_date_actual.strftime('%Y-%m-%d') if sell_date_actual else None,
                                            'sell_price': sell_price,
                                            'profit_pct': profit_pct,
                                        }
                                        backtest_results.append(backtest_data)
                                    except Exception as e:
                                        print(f"回测计算失败 {stock_name}: {e}")
                                        import traceback
                                        traceback.print_exc()
                                        continue
                                # 计算每只股票的买入金额和市值
                                if backtest_results:
                                    capital_per_stock = total_capital / len(backtest_results)
                                    for r in backtest_results:
                                        r['buy_amount'] = capital_per_stock
                                        r['sell_value'] = capital_per_stock * (1 + r['profit_pct'] / 100)
                                # 显示结果
                                def display_custom_backtest_results():
                                    try:
                                        result_text_backtest.delete("1.0", tk.END)
                                        result_text_backtest.insert("1.0", "="*100 + "\n")
                                        result_text_backtest.insert(tk.END, "自定义回测分析报告\n")
                                        result_text_backtest.insert(tk.END, f"买入日期: {buy_date_str}\n")
                                        result_text_backtest.insert(tk.END, f"卖出日期: {sell_date_str}\n")
                                        result_text_backtest.insert(tk.END, f"回测股票数量: {len(backtest_results)}\n")
                                        result_text_backtest.insert(tk.END, "本金: 1000万元\n")
                                        result_text_backtest.insert(tk.END, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                        result_text_backtest.insert(tk.END, "="*100 + "\n\n")
                                        if not backtest_results:
                                            result_text_backtest.insert(tk.END, "没有符合条件的股票进行回测(可能都是一字涨停板买不进)\n")
                                            return
                                        # 计算总体市值变化
                                        total_value = sum(r['sell_value'] for r in backtest_results)
                                        total_profit = total_value - total_capital
                                        total_profit_pct = (total_profit / total_capital) * 100
                                        capital_per_stock = total_capital / len(backtest_results) if backtest_results else 0
                                        result_text_backtest.insert(tk.END, "【总体市值变化统计】\n", "bold")
                                        result_text_backtest.insert(tk.END, f"初始本金: {total_capital/10000:.2f}万元\n")
                                        result_text_backtest.insert(tk.END, f"每只股票买入金额: {capital_per_stock/10000:.2f}万元\n\n")
                                        tag = "red" if total_profit > 0 else "green"
                                        result_text_backtest.insert(tk.END, f"总体市值: {total_value/10000:.2f}万元  ", tag)
                                        result_text_backtest.insert(tk.END, f"盈亏: {total_profit/10000:.2f}万元 ({total_profit_pct:+.2f}%)\n", tag)
                                        result_text_backtest.insert(tk.END, "\n" + "="*100 + "\n\n")
                                        result_text_backtest.insert(tk.END, "【个股回测详情】\n", "bold")
                                        for idx, r in enumerate(backtest_results, 1):
                                            result_text_backtest.insert(tk.END, f"\n【{idx}】{r['stock_name']} ({r['stock_code']})\n", "bold")
                                            result_text_backtest.insert(tk.END, f"买入日期: {r['buy_date']}  买入价: {r['buy_price']:.2f}  买入金额: {r['buy_amount']/10000:.2f}万元\n")
                                            if r['sell_date']:
                                                result_text_backtest.insert(tk.END, f"卖出日期: {r['sell_date']}  卖出价: {r['sell_price']:.2f}\n")
                                            else:
                                                result_text_backtest.insert(tk.END, f"当前日期: {r['sell_date']}  当前价: {r['sell_price']:.2f}\n")
                                            tag = "red" if r['profit_pct'] > 0 else "green"
                                            result_text_backtest.insert(tk.END, f"盈亏: {r['profit_pct']:.2f}%  市值: {r['sell_value']/10000:.2f}万元\n", tag)
                                        result_text_backtest.insert(tk.END, "\n" + "="*100 + "\n")
                                        result_text_backtest.insert(tk.END, "回测分析完成\n")
                                        # 配置颜色标签
                                        result_text_backtest.tag_config("red", foreground="red")
                                        result_text_backtest.tag_config("green", foreground="green")
                                        result_text_backtest.tag_config("bold", font=("Consolas", 11, "bold"))
                                    except Exception as e:
                                        import traceback
                                        traceback.print_exc()
                                        result_text_backtest.delete("1.0", tk.END)
                                        result_text_backtest.insert("1.0", f"显示回测结果失败: {e!s}\n")
                                backtest_result_window.after(0, display_custom_backtest_results)
                            except Exception as e:
                                import traceback
                                traceback.print_exc()
                                def show_error(e=e):
                                    result_text_backtest.delete("1.0", tk.END)
                                    result_text_backtest.insert("1.0", f"回测计算失败: {e!s}\n")
                                    result_text_backtest.insert(tk.END, traceback.format_exc())
                                backtest_result_window.after(0, show_error)
                        thread = threading.Thread(target=custom_backtest_thread, daemon=True)
                        thread.start()
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        messagebox.showerror("错误", f"回测分析失败: {e!s}", parent=parent_window)
                ttk.Button(toolbar_frame, text="回测分析", command=show_backtest_analysis, width=12).pack(side=tk.LEFT, padx=5)
                # 创建结果显示区域
                result_text = scrolledtext.ScrolledText(result_window, wrap=tk.WORD, font=("Consolas", 11))
                result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                # 配置文本颜色标签
                result_text.tag_config("red", foreground="red")
                result_text.tag_config("green", foreground="green")
                result_text.tag_config("bold", font=("Consolas", 11, "bold"))
                result_text.tag_config("yellow_spec", foreground="#FFA500")  # 黄色(陈小群等)
                result_text.tag_config("purple_spec", foreground="#9370DB")  # 紫色(藏獒、拉萨等)
                # 均线全部通过的样式:股票名和代码红色加粗11号字体,详细信息黄色背景11号字体
                result_text.tag_config("ma_all_pass_name", font=("Consolas", 13, "bold"), foreground="red")
                result_text.tag_config("ma_all_pass_text", font=("Consolas", 11), background="yellow")
                result_text.tag_config("bold_gold", font=("Consolas", 11, "bold"), foreground="#B8860B")
                result_text.tag_config("bold_fish_body", font=("Consolas", 11, "bold"), foreground="#c62828")
                result_text.tag_config("bold_fish_tail", font=("Consolas", 11, "bold"), foreground="#2e7d32")
                result_text.insert("1.0", "="*100 + "\n")
                result_text.insert(tk.END, "周期涨跌幅分析报告\n")
                result_text.insert(tk.END, "="*100 + "\n\n")
                result_text.insert(tk.END, f"判断日: {judgment_date_str}\n")
                result_text.insert(tk.END, f"分析股票数量: {len(sorted_stocks)}\n")
                result_text.insert(tk.END, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                result_text.insert(tk.END, "="*100 + "\n\n")
                result_text.insert(tk.END, "正在计算,请稍候...\n")
                result_window.update()
                # 定义更新UI的函数(在show_calculation_window作用域中,可以直接访问result_text和result_window)
                def update_ui_with_results(results_list, judgment_date_str_val, sorted_stocks_list):
                    """更新UI显示计算结果"""
                    try:
                        result_text.delete("1.0", tk.END)
                        result_text.insert("1.0", "="*100 + "\n")
                        result_text.insert(tk.END, "周期涨跌幅分析报告\n")
                        result_text.insert(tk.END, "="*100 + "\n\n")
                        result_text.insert(tk.END, f"判断日: {judgment_date_str_val}\n")
                        result_text.insert(tk.END, f"分析股票数量: {len(sorted_stocks_list)}\n")
                        result_text.insert(tk.END, f"成功计算: {len(results_list)} 个\n")
                        result_text.insert(tk.END, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                        result_text.insert(tk.END, "="*100 + "\n\n")
                        for idx, result in enumerate(results_list, 1):
                            # 检查均线测试是否全部通过
                            ma_all_passed = False
                            if result.get('ma_detection'):
                                ma_det = result['ma_detection']
                                # 检查所有均线是否都存在且都通过
                                ma1_ok = ma_det.get('ma1') and ma_det['ma1'].get('crossed') and ma_det['ma1'].get('uptrend')
                                ma5_ok = ma_det.get('ma5') and ma_det['ma5'].get('crossed') and ma_det['ma5'].get('uptrend')
                                ma10_ok = ma_det.get('ma10') and ma_det['ma10'].get('crossed') and ma_det['ma10'].get('uptrend')
                                ma20_ok = ma_det.get('ma20') and ma_det['ma20'].get('crossed') and ma_det['ma20'].get('uptrend')
                                ma_all_passed = ma1_ok and ma5_ok and ma10_ok and ma20_ok
                            # 设置详细信息标签(如果均线全部通过)
                            detail_tag = "ma_all_pass_text" if ma_all_passed else None
                            result_text.insert(tk.END, f"\n【{idx}】", "bold")
                            # 显示股票名称(如果均线全部通过,使用特殊样式)
                            if ma_all_passed:
                                if 'stock_code' in result and result['stock_code'] != '未找到':
                                    result_text.insert(tk.END, f"{result.get('stock_name', '未知')} ({result['stock_code']})", "ma_all_pass_name")
                                else:
                                    result_text.insert(tk.END, f"{result.get('stock_name', '未知')}", "ma_all_pass_name")
                            else:
                                if 'stock_code' in result and result['stock_code'] != '未找到':
                                    result_text.insert(tk.END, f"{result.get('stock_name', '未知')} ({result['stock_code']})")
                                else:
                                    result_text.insert(tk.END, f"{result.get('stock_name', '未知')}")
                            result_text.insert(tk.END, "\n", detail_tag)
                            result_text.insert(tk.END, "-"*100 + "\n", detail_tag)
                            # 显示股票来源信息
                            if result.get('stock_sources'):
                                result_text.insert(tk.END, "股票来源统计:\n", detail_tag)
                                total_source = result.get('total_source_count', 0)
                                for tab_name, source_count in sorted(result['stock_sources'].items(), key=lambda x: x[1], reverse=True):
                                    if total_source > 0:
                                        percentage = (source_count / total_source) * 100
                                        result_text.insert(tk.END, f"  {tab_name}: {source_count} 次 ({percentage:.1f}%)\n", detail_tag)
                                result_text.insert(tk.END, f"  总出现次数: {result.get('total_count', 0)} 次\n\n", detail_tag)
                            if 'error' in result:
                                result_text.insert(tk.END, f"错误: {result['error']}\n", detail_tag)
                            else:
                                result_text.insert(tk.END, f"判断日: {result['judgment_date']}  判断日价格: {result['judgment_price']:.2f}\n", detail_tag)
                                result_text.insert(tk.END, f"最新日期: {result['latest_date']}  最新价格: {result['latest_price']:.2f}  距判断日: {result['days_since_judgment']} 天\n\n", detail_tag)
                                # 涨跌幅信息(带颜色标记)
                                result_text.insert(tk.END, "涨跌幅统计:\n", detail_tag)
                                if result.get('change_5d') is not None:
                                    change_5d_text = f"  5日涨跌幅: {result['change_5d']:.2f}%\n"
                                    if ma_all_passed:
                                        result_text.insert(tk.END, change_5d_text, detail_tag)
                                    elif result['change_5d'] > 10:
                                        result_text.insert(tk.END, change_5d_text, "red")
                                    elif result['change_5d'] < -10:
                                        result_text.insert(tk.END, change_5d_text, "green")
                                    else:
                                        result_text.insert(tk.END, change_5d_text)
                                if result.get('change_10d') is not None:
                                    change_10d_text = f"  10日涨跌幅: {result['change_10d']:.2f}%\n"
                                    if ma_all_passed:
                                        result_text.insert(tk.END, change_10d_text, detail_tag)
                                    elif result['change_10d'] > 10:
                                        result_text.insert(tk.END, change_10d_text, "red")
                                    elif result['change_10d'] < -10:
                                        result_text.insert(tk.END, change_10d_text, "green")
                                    else:
                                        result_text.insert(tk.END, change_10d_text)
                                if result.get('change_20d') is not None:
                                    change_20d_text = f"  20日涨跌幅: {result['change_20d']:.2f}%\n"
                                    if ma_all_passed:
                                        result_text.insert(tk.END, change_20d_text, detail_tag)
                                    elif result['change_20d'] > 10:
                                        result_text.insert(tk.END, change_20d_text, "red")
                                    elif result['change_20d'] < -10:
                                        result_text.insert(tk.END, change_20d_text, "green")
                                    else:
                                        result_text.insert(tk.END, change_20d_text)
                                # 至今涨跌幅(带颜色标记)
                                change_to_now_text = f"  至今涨跌幅: {result['change_to_now']:.2f}%\n"
                                if ma_all_passed:
                                    result_text.insert(tk.END, change_to_now_text, detail_tag)
                                elif result['change_to_now'] > 10:
                                    result_text.insert(tk.END, change_to_now_text, "red")
                                elif result['change_to_now'] < -10:
                                    result_text.insert(tk.END, change_to_now_text, "green")
                                else:
                                    result_text.insert(tk.END, change_to_now_text)
                                result_text.insert(tk.END, "\n", detail_tag)
                                # 形态分析:近20日黄金股、鱼身鱼尾、最新价与10日线(上方≤2%视为靠近)
                                if 'error' not in result:
                                    result_text.insert(tk.END, "【形态分析】\n", "bold")
                                    result_text.insert(tk.END, "  黄金股: ", "bold")
                                    if result.get('is_golden_stock'):
                                        result_text.insert(tk.END, "是\n", "bold_gold")
                                    else:
                                        result_text.insert(tk.END, "否\n", detail_tag)
                                    result_text.insert(tk.END, "  鱼身鱼尾: ", "bold")
                                    if result.get('fish_body'):
                                        result_text.insert(tk.END, "鱼身\n", "bold_fish_body")
                                    elif result.get('fish_tail'):
                                        result_text.insert(tk.END, "鱼尾\n", "bold_fish_tail")
                                    else:
                                        result_text.insert(tk.END, "-\n", detail_tag)
                                    result_text.insert(tk.END, "  靠近10日线(最新价在均线上方且≤2%): ", "bold")
                                    if result.get('ma10_latest_pct') is not None:
                                        pct = result['ma10_latest_pct']
                                        nm = result.get('near_ma10_2pct')
                                        if nm is True:
                                            result_text.insert(tk.END, f"是 ({pct:+.2f}%)\n", detail_tag)
                                        elif nm is False:
                                            result_text.insert(tk.END, f"否 ({pct:+.2f}%)\n", detail_tag)
                                    else:
                                        result_text.insert(tk.END, "数据不足\n", detail_tag)
                                    result_text.insert(tk.END, "\n", detail_tag)
                                # 价格极值统计
                                if 'max_price' in result and 'min_price' in result:
                                    result_text.insert(tk.END, "价格极值统计:\n", detail_tag)
                                    result_text.insert(tk.END, f"  最高价: {result['max_price']:.2f}  (日期: {result['max_date']})  相对判断日涨跌幅: {result['change_to_max']:.2f}%\n", detail_tag)
                                    result_text.insert(tk.END, f"  最低价: {result['min_price']:.2f}  (日期: {result['min_date']})  相对判断日涨跌幅: {result['change_to_min']:.2f}%\n\n", detail_tag)
                                # 显示jiuyan逻辑介绍(如果存在)
                                if result.get('jiuyan_logic'):
                                    result_text.insert(tk.END, "【韭研逻辑介绍】\n", detail_tag)
                                    result_text.insert(tk.END, f"  {result['jiuyan_logic']}\n\n", detail_tag)
                                # 显示游资信息(如果存在)
                                if result.get('speculator_info'):
                                    spec_info = result['speculator_info']
                                    if spec_info and spec_info.get('content'):
                                        if spec_info['type'] == 'yellow':
                                            result_text.insert(tk.END, "【游资信息】", ["yellow_spec", detail_tag] if detail_tag else "yellow_spec")
                                        elif spec_info['type'] == 'purple':
                                            result_text.insert(tk.END, "【游资信息】", ["purple_spec", detail_tag] if detail_tag else "purple_spec")
                                        else:
                                            result_text.insert(tk.END, "【游资信息】", detail_tag)
                                        result_text.insert(tk.END, "\n", detail_tag)
                                        if spec_info['type'] == 'yellow':
                                            result_text.insert(tk.END, f"  {spec_info['content']}\n\n", ["yellow_spec", detail_tag] if detail_tag else "yellow_spec")
                                        elif spec_info['type'] == 'purple':
                                            result_text.insert(tk.END, f"  {spec_info['content']}\n\n", ["purple_spec", detail_tag] if detail_tag else "purple_spec")
                                        else:
                                            result_text.insert(tk.END, f"  {spec_info['content']}\n\n", detail_tag)
                                # 均线检测结果
                                if result.get('ma_detection'):
                                    result_text.insert(tk.END, "【均线检测结果】\n", detail_tag)
                                    ma_det = result['ma_detection']
                                    # 1日线检测
                                    if ma_det.get('ma1'):
                                        ma1 = ma_det['ma1']
                                        ma1_status = "✓" if (ma1['crossed'] and ma1['uptrend']) else "✗"
                                        result_text.insert(tk.END, f"  1日线: {ma1_status}  价格: {result['judgment_price']:.2f} >= 前一日: {ma1['ref_price']:.2f}", detail_tag)
                                        if ma1['uptrend']:
                                            result_text.insert(tk.END, "  (上升趋势)", detail_tag)
                                        else:
                                            result_text.insert(tk.END, "  (下降趋势)", detail_tag)
                                        result_text.insert(tk.END, "\n", detail_tag)
                                    # 5日均线检测
                                    if ma_det.get('ma5'):
                                        ma5 = ma_det['ma5']
                                        ma5_status = "✓" if (ma5['crossed'] and ma5['uptrend']) else "✗"
                                        result_text.insert(tk.END, f"  5日均线: {ma5_status}  价格: {result['judgment_price']:.2f} >= MA5: {ma5['ma_value']:.2f}", detail_tag)
                                        result_text.insert(tk.END, f"  (差值: {ma5['diff_pct']:.2f}%)", detail_tag)
                                        if ma5['uptrend']:
                                            result_text.insert(tk.END, "  MA5上升", detail_tag)
                                        else:
                                            result_text.insert(tk.END, "  MA5下降", detail_tag)
                                        result_text.insert(tk.END, "\n", detail_tag)
                                    # 10日均线检测
                                    if ma_det.get('ma10'):
                                        ma10 = ma_det['ma10']
                                        ma10_status = "✓" if (ma10['crossed'] and ma10['uptrend']) else "✗"
                                        result_text.insert(tk.END, f"  10日均线: {ma10_status}  价格: {result['judgment_price']:.2f} >= MA10: {ma10['ma_value']:.2f}", detail_tag)
                                        result_text.insert(tk.END, f"  (差值: {ma10['diff_pct']:.2f}%)", detail_tag)
                                        if ma10['uptrend']:
                                            result_text.insert(tk.END, "  MA10上升", detail_tag)
                                        else:
                                            result_text.insert(tk.END, "  MA10下降", detail_tag)
                                        result_text.insert(tk.END, "\n", detail_tag)
                                    # 20日均线检测
                                    if ma_det.get('ma20'):
                                        ma20 = ma_det['ma20']
                                        ma20_status = "✓" if (ma20['crossed'] and ma20['uptrend']) else "✗"
                                        result_text.insert(tk.END, f"  20日均线: {ma20_status}  价格: {result['judgment_price']:.2f} >= MA20: {ma20['ma_value']:.2f}", detail_tag)
                                        result_text.insert(tk.END, f"  (差值: {ma20['diff_pct']:.2f}%)", detail_tag)
                                        if ma20['uptrend']:
                                            result_text.insert(tk.END, "  MA20上升", detail_tag)
                                        else:
                                            result_text.insert(tk.END, "  MA20下降", detail_tag)
                                        result_text.insert(tk.END, "\n", detail_tag)
                            result_text.insert(tk.END, "\n", detail_tag)
                        result_text.insert(tk.END, "\n" + "="*100 + "\n")
                        result_text.insert(tk.END, "计算完成\n")
                        result_text.see("1.0")
                    except Exception as e:
                        result_text.delete("1.0", tk.END)
                        result_text.insert("1.0", f"显示结果失败: {e!s}\n")
                        import traceback
                        result_text.insert(tk.END, traceback.format_exc())
                        print(f"显示结果异常: {e}")
                        traceback.print_exc()
                def calculate_changes():
                    """在后台线程中计算涨跌幅"""
                    try:

                        import pandas as pd
                        # news_data_list在外部作用域中,可以直接使用
                        # 立即显示开始计算的提示
                        def show_start_message():
                            try:
                                result_text.delete("1.0", tk.END)
                                result_text.insert("1.0", "="*100 + "\n")
                                result_text.insert(tk.END, "周期涨跌幅分析报告\n")
                                result_text.insert(tk.END, "="*100 + "\n\n")
                                result_text.insert(tk.END, f"判断日: {judgment_date_str}\n")
                                result_text.insert(tk.END, f"分析股票数量: {len(sorted_stocks)}\n")
                                result_text.insert(tk.END, f"开始计算时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                                result_text.insert(tk.END, "="*100 + "\n\n")
                                result_text.insert(tk.END, "正在计算,请稍候...\n\n")
                                result_text.see(tk.END)
                                result_window.update_idletasks()
                            except Exception as e:
                                print(f"显示开始消息失败: {e}")
                        result_window.after(0, show_start_message)
                        time.sleep(0.1)  # 短暂延迟,确保UI更新
                        today = datetime.now().date()
                        results = []
                        for idx, (stock_name, count) in enumerate(sorted_stocks, 1):
                            # 获取该股票的来源信息
                            stock_sources = stock_source_map.get(stock_name, {})
                            total_source_count = sum(stock_sources.values())
                            try:
                                # 更新进度(每个股票都更新,让用户看到进度)
                                def update_progress(idx_val, total, name):
                                    try:
                                        # 追加进度信息,不删除已有内容
                                        result_text.insert(tk.END, f"[{idx_val}/{total}] 正在计算 {name}...\n")
                                        result_text.see(tk.END)
                                        result_window.update_idletasks()
                                    except Exception as e:
                                        print(f"更新进度失败: {e}")
                                # 每个股票都更新进度(使用after确保在主线程中更新UI)
                                result_window.after(0, update_progress, idx, len(sorted_stocks), stock_name)
                                # 添加小延迟,避免请求过快导致网络问题
                                if idx % 10 == 0:  # 每10个股票暂停一下
                                    time.sleep(0.1)
                                # 获取股票代码(从股票名称中提取或查找)
                                stock_code = None
                                # 如果股票名称包含代码(格式:名称(代码)),直接提取
                                if '(' in stock_name and ')' in stock_name:
                                    try:
                                        code_part = stock_name.split('(')[1].split(')')[0]
                                        if len(code_part) == 6 and code_part.isdigit():
                                            stock_code = code_part
                                    except:
                                        pass
                                # 如果没提取到,尝试快速查找
                                if not stock_code:
                                    try:
                                        # 使用快速查找,避免卡住
                                        if STOCK_NAME_TO_CODE and stock_name in STOCK_NAME_TO_CODE:
                                            stock_code = STOCK_NAME_TO_CODE[stock_name]
                                        else:
                                            # 如果快速查找失败,跳过该股票
                                            results.append({
                                                'stock_name': stock_name,
                                                'stock_code': '未找到',
                                                'error': '无法快速获取股票代码,已跳过'
                                            })
                                            continue
                                    except Exception as e:
                                        results.append({
                                            'stock_name': stock_name,
                                            'stock_code': '未找到',
                                            'error': f'获取股票代码失败: {e!s}'
                                        })
                                        continue
                                # 获取历史数据(添加超时保护)
                                try:
                                    if not AKSHARE_AVAILABLE:
                                        results.append({
                                            'stock_name': stock_name,
                                            'stock_code': stock_code,
                                            'error': 'akshare库未安装'
                                        })
                                        continue
                                    # 直接获取历史数据,不使用线程(简化逻辑,加快速度)
                                    try:
                                        hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                                    except Exception as e:
                                        results.append({
                                            'stock_name': stock_name,
                                            'stock_code': stock_code,
                                            'error': f'获取历史数据失败: {e!s}'
                                        })
                                        continue
                                    if hist_data is None or hist_data.empty:
                                        results.append({
                                            'stock_name': stock_name,
                                            'stock_code': stock_code,
                                            'error': '无法获取历史数据'
                                        })
                                        continue
                                    # 转换日期列为日期类型
                                    hist_data['日期'] = pd.to_datetime(hist_data['日期']).dt.date
                                    # 找到判断日的数据
                                    judgment_data = hist_data[hist_data['日期'] == judgment_date]
                                    if judgment_data.empty:
                                        # 如果判断日没有数据,找最近的一个交易日
                                        before_judgment = hist_data[hist_data['日期'] <= judgment_date]
                                        if before_judgment.empty:
                                            results.append({
                                                'stock_name': stock_name,
                                                'stock_code': stock_code,
                                                'error': f'判断日 {judgment_date_str} 无数据'
                                            })
                                            continue
                                        judgment_data = before_judgment.iloc[-1:]
                                    judgment_price = float(judgment_data.iloc[0]['收盘'])
                                    judgment_date_actual = judgment_data.iloc[0]['日期']
                                    # 获取判断日之后的数据
                                    after_judgment = hist_data[hist_data['日期'] > judgment_date_actual].copy()
                                    if after_judgment.empty:
                                        # 如果判断日后没有数据,使用判断日前一天的收盘数据
                                        before_judgment_for_prev = hist_data[hist_data['日期'] < judgment_date_actual].copy()
                                        if not before_judgment_for_prev.empty:
                                            # 使用前一天的收盘数据
                                            prev_day_data = before_judgment_for_prev.iloc[-1:]
                                            judgment_date_actual = prev_day_data.iloc[0]['日期']
                                            judgment_price = float(prev_day_data.iloc[0]['收盘'])
                                            # 重新获取判断日之后的数据(使用新的判断日)
                                            after_judgment = hist_data[hist_data['日期'] > judgment_date_actual].copy()
                                            if after_judgment.empty:
                                                # 如果调整后仍然没有后续数据,则返回错误
                                                results.append({
                                                    'stock_name': stock_name,
                                                    'stock_code': stock_code,
                                                    'judgment_date': judgment_date_actual.strftime('%Y-%m-%d'),
                                                    'judgment_price': judgment_price,
                                                    'error': '调整判断日后仍无后续数据'
                                                })
                                                continue
                                        else:
                                            # 如果判断日前也没有数据,返回错误
                                            results.append({
                                                'stock_name': stock_name,
                                                'stock_code': stock_code,
                                                'judgment_date': judgment_date_actual.strftime('%Y-%m-%d'),
                                                'judgment_price': judgment_price,
                                                'error': '判断日前无数据,无法调整判断日'
                                            })
                                            continue
                                    # 计算至今涨跌幅
                                    latest_data = after_judgment.iloc[-1]
                                    latest_price = float(latest_data['收盘'])
                                    latest_date = latest_data['日期']
                                    days_since_judgment = (latest_date - judgment_date_actual).days
                                    change_to_now = ((latest_price - judgment_price) / judgment_price) * 100
                                    # 计算5日、10日、20日涨跌幅
                                    change_5d = None
                                    change_10d = None
                                    change_20d = None
                                    if days_since_judgment >= 5:
                                        day_5_data = after_judgment.head(5).iloc[-1]
                                        price_5d = float(day_5_data['收盘'])
                                        change_5d = ((price_5d - judgment_price) / judgment_price) * 100
                                    elif days_since_judgment > 0:
                                        change_5d = change_to_now  # 不足5日,使用至今涨跌幅
                                    if days_since_judgment >= 10:
                                        day_10_data = after_judgment.head(10).iloc[-1]
                                        price_10d = float(day_10_data['收盘'])
                                        change_10d = ((price_10d - judgment_price) / judgment_price) * 100
                                    elif days_since_judgment >= 5:
                                        change_10d = change_to_now  # 不足10日但>=5日,使用至今涨跌幅
                                    if days_since_judgment >= 20:
                                        day_20_data = after_judgment.head(20).iloc[-1]
                                        price_20d = float(day_20_data['收盘'])
                                        change_20d = ((price_20d - judgment_price) / judgment_price) * 100
                                    elif days_since_judgment >= 10:
                                        change_20d = change_to_now  # 不足20日但>=10日,使用至今涨跌幅
                                    # 计算最高值、最低值
                                    max_price = float(after_judgment['收盘'].max())
                                    min_price = float(after_judgment['收盘'].min())
                                    max_date = after_judgment[after_judgment['收盘'] == max_price].iloc[0]['日期']
                                    min_date = after_judgment[after_judgment['收盘'] == min_price].iloc[0]['日期']
                                    change_to_max = ((max_price - judgment_price) / judgment_price) * 100
                                    change_to_min = ((min_price - judgment_price) / judgment_price) * 100
                                    # 计算判断日的均线差值百分比
                                    before_judgment_data = hist_data[hist_data['日期'] <= judgment_date_actual].copy()
                                    bias_5 = None
                                    bias_10 = None
                                    bias_20 = None
                                    ma_diff_5 = None
                                    ma_diff_10 = None
                                    ma_diff_20 = None
                                    # 均线检测结果
                                    ma_detection = {
                                        'ma1': None,
                                        'ma5': None,
                                        'ma10': None,
                                        'ma20': None
                                    }
                                    # 均线计算
                                    try:
                                        if len(before_judgment_data) >= 2:
                                            prev_price = float(before_judgment_data.iloc[-2]['收盘'])
                                            prev_prev_price = float(before_judgment_data.iloc[-3]['收盘']) if len(before_judgment_data) >= 3 else prev_price
                                            ma1_crossed = judgment_price >= prev_price
                                            ma1_uptrend = prev_price >= prev_prev_price
                                            ma_detection['ma1'] = {
                                                'crossed': ma1_crossed,
                                                'uptrend': ma1_uptrend,
                                                'ref_price': prev_price,
                                                'prev_price': prev_prev_price
                                            }
                                        if len(before_judgment_data) >= 5:
                                            ma5_prices = before_judgment_data['收盘'].tail(5).values
                                            ma5 = float(np.mean(ma5_prices))
                                            if len(before_judgment_data) >= 10:
                                                prev_ma5_prices = before_judgment_data['收盘'].tail(10).head(5).values
                                                prev_ma5 = float(np.mean(prev_ma5_prices))
                                            else:
                                                prev_ma5 = ma5
                                            if ma5 > 0:
                                                ma_diff_5 = ((judgment_price - ma5) / ma5) * 100
                                                ma5_crossed = judgment_price >= ma5
                                                ma5_uptrend = ma5 >= prev_ma5
                                                ma_detection['ma5'] = {
                                                    'crossed': ma5_crossed,
                                                    'uptrend': ma5_uptrend,
                                                    'ma_value': ma5,
                                                    'prev_ma': prev_ma5,
                                                    'diff_pct': ma_diff_5
                                                }
                                        if len(before_judgment_data) >= 10:
                                            ma10_prices = before_judgment_data['收盘'].tail(10).values
                                            ma10 = float(np.mean(ma10_prices))
                                            if len(before_judgment_data) >= 20:
                                                prev_ma10_prices = before_judgment_data['收盘'].tail(20).head(10).values
                                                prev_ma10 = float(np.mean(prev_ma10_prices))
                                            else:
                                                prev_ma10 = ma10
                                            if ma10 > 0:
                                                ma_diff_10 = ((judgment_price - ma10) / ma10) * 100
                                                ma10_crossed = judgment_price >= ma10
                                                ma10_uptrend = ma10 >= prev_ma10
                                                ma_detection['ma10'] = {
                                                    'crossed': ma10_crossed,
                                                    'uptrend': ma10_uptrend,
                                                    'ma_value': ma10,
                                                    'prev_ma': prev_ma10,
                                                    'diff_pct': ma_diff_10
                                                }
                                        if len(before_judgment_data) >= 20:
                                            ma20_prices = before_judgment_data['收盘'].tail(20).values
                                            ma20 = float(np.mean(ma20_prices))
                                            if len(before_judgment_data) >= 40:
                                                prev_ma20_prices = before_judgment_data['收盘'].tail(40).head(20).values
                                                prev_ma20 = float(np.mean(prev_ma20_prices))
                                            else:
                                                prev_ma20 = ma20
                                            if ma20 > 0:
                                                ma_diff_20 = ((judgment_price - ma20) / ma20) * 100
                                                ma20_crossed = judgment_price >= ma20
                                                ma20_uptrend = ma20 >= prev_ma20
                                                ma_detection['ma20'] = {
                                                    'crossed': ma20_crossed,
                                                    'uptrend': ma20_uptrend,
                                                    'ma_value': ma20,
                                                    'prev_ma': prev_ma20,
                                                    'diff_pct': ma_diff_20
                                                }
                                    except Exception as e:
                                        # 均线计算失败不影响主流程
                                        print(f"均线计算失败 {stock_name}: {e}")
                                except Exception as e:
                                    results.append({
                                        'stock_name': stock_name,
                                        'stock_code': stock_code,
                                        'error': f'获取或处理历史数据失败: {e!s}'
                                    })
                                    continue
                                # 如果股票来源中包含jiuyan相关标签页,获取jiuyan逻辑介绍和游资信息
                                jiuyan_logic = None
                                speculator_info = None  # 存储游资信息:{'type': 'yellow'/'purple', 'content': '...'}
                                # 定义游资名字列表
                                yellow_speculators = ['陈小群', '小群', '小群哥', '群哥']  # 黄色游资
                                purple_speculators = ['藏獒', '拉萨', '拉萨帮', '东财', '东方财富', '散户']  # 紫色游资
                                try:
                                    # 检查是否有jiuyan相关的来源
                                    has_jiuyan_source = False
                                    jiuyan_tab_names = []
                                    for tab_name in stock_sources:
                                        if 'jiuyan' in tab_name.lower() or '韭研' in tab_name or 'jiuyang' in tab_name.lower():
                                            has_jiuyan_source = True
                                            jiuyan_tab_names.append(tab_name)
                                    if has_jiuyan_source:
                                        # 从已选中的资讯数据中提取jiuyan逻辑介绍
                                        try:
                                            jiuyan_contents = []
                                            # 从news_data_list中筛选jiuyan相关的资讯内容
                                            if news_data_list:
                                                for news_data in news_data_list:
                                                    tab_name = news_data.get('tab_name', '')
                                                    content = news_data.get('content', '')
                                                    # 检查是否是jiuyan相关的标签页
                                                    if any(jtn in tab_name for jtn in jiuyan_tab_names):
                                                        if content and stock_name in content:
                                                            jiuyan_contents.append(content)
                                            # 如果从news_data_list中没找到,再从数据库查询(备用方案)
                                            if not jiuyan_contents:
                                                try:
                                                    conn = sqlite3.connect(DB_PATH)
                                                    cursor = conn.cursor()
                                                    for tab_name in jiuyan_tab_names:
                                                        cursor.execute('''
                                                            SELECT content FROM news_info
                                                            WHERE tab_name = ?
                                                            ORDER BY created_at DESC
                                                            LIMIT 5
                                                        ''', (tab_name,))
                                                        rows = cursor.fetchall()
                                                        for row in rows:
                                                            if row[0] and stock_name in row[0]:
                                                                jiuyan_contents.append(row[0])
                                                    conn.close()
                                                except Exception as e:
                                                    print(f"从数据库查询jiuyan资讯失败 {stock_name}: {e}")
                                            # 合并所有jiuyan资讯内容并提取逻辑
                                            if jiuyan_contents:
                                                merged_jiuyan_content = "\n\n".join(jiuyan_contents)
                                                # 使用get_stock_logic提取股票逻辑
                                                jiuyan_logic = get_stock_logic(merged_jiuyan_content, stock_name)
                                                # 如果提取的逻辑太短或无效,尝试使用extract_stock_context
                                                if not jiuyan_logic or jiuyan_logic == "未找到明确逻辑":
                                                    context_dict = extract_stock_context(merged_jiuyan_content, [stock_name])
                                                    if stock_name in context_dict and context_dict[stock_name] != ["未找到相关内容"]:
                                                        jiuyan_logic = " | ".join(context_dict[stock_name][:2])
                                                # 检查并提取游资信息
                                                try:
                                                    # 在包含股票名称的句子附近查找游资名字
                                                    sentences = re.split(r'[。!?\n]', merged_jiuyan_content)
                                                    speculator_sentences = []
                                                    speculator_type = None
                                                    for sentence in sentences:
                                                        if stock_name in sentence:
                                                            # 检查黄色游资
                                                            for speculator in yellow_speculators:
                                                                if speculator in sentence:
                                                                    speculator_sentences.append(sentence.strip())
                                                                    if speculator_type is None:
                                                                        speculator_type = 'yellow'
                                                                    break
                                                            # 检查紫色游资(如果还没有找到黄色游资)
                                                            if speculator_type != 'yellow':
                                                                for speculator in purple_speculators:
                                                                    if speculator in sentence:
                                                                        speculator_sentences.append(sentence.strip())
                                                                        if speculator_type is None:
                                                                            speculator_type = 'purple'
                                                                        break
                                                    if speculator_sentences and speculator_type:
                                                        speculator_info = {
                                                            'type': speculator_type,
                                                            'content': " | ".join(speculator_sentences[:3])  # 最多取3个句子
                                                        }
                                                except Exception as e:
                                                    print(f"提取游资信息失败 {stock_name}: {e}")
                                                    speculator_info = None
                                        except Exception as e:
                                            print(f"获取jiuyan逻辑失败 {stock_name}: {e}")
                                            jiuyan_logic = None
                                            speculator_info = None
                                    # 如果没有jiuyan来源,也要检查所有来源中是否有游资信息
                                    if not has_jiuyan_source and news_data_list and speculator_info is None:
                                        try:
                                            all_content_for_speculator = []
                                            for news_data in news_data_list:
                                                content = news_data.get('content', '')
                                                if content and stock_name in content:
                                                    all_content_for_speculator.append(content)
                                            if all_content_for_speculator:
                                                merged_content = "\n\n".join(all_content_for_speculator)
                                                sentences = re.split(r'[。!?\n]', merged_content)
                                                speculator_sentences = []
                                                speculator_type = None
                                                for sentence in sentences:
                                                    if stock_name in sentence:
                                                        # 检查黄色游资
                                                        for speculator in yellow_speculators:
                                                            if speculator in sentence:
                                                                speculator_sentences.append(sentence.strip())
                                                                if speculator_type is None:
                                                                    speculator_type = 'yellow'
                                                                break
                                                        # 检查紫色游资(如果还没有找到黄色游资)
                                                        if speculator_type != 'yellow':
                                                            for speculator in purple_speculators:
                                                                if speculator in sentence:
                                                                    speculator_sentences.append(sentence.strip())
                                                                    if speculator_type is None:
                                                                        speculator_type = 'purple'
                                                                    break
                                                if speculator_sentences and speculator_type:
                                                    speculator_info = {
                                                        'type': speculator_type,
                                                        'content': " | ".join(speculator_sentences[:3])
                                                    }
                                        except Exception as e:
                                            print(f"提取游资信息失败(非jiuyan来源) {stock_name}: {e}")
                                            speculator_info = None
                                except Exception as e:
                                    print(f"处理jiuyan逻辑失败 {stock_name}: {e}")
                                    jiuyan_logic = None
                                    speculator_info = None
                                is_golden_stock = False
                                fish_body = False
                                fish_tail = False
                                ma10_latest_pct = None
                                near_ma10_2pct = None
                                try:
                                    is_golden_stock = bool(self._check_golden_stock_recent_20d(stock_code, stock_name))
                                except Exception:
                                    pass
                                try:
                                    _ms_f = self._check_ma_status(stock_code)
                                    fish_body = bool(_ms_f.get('fish_body'))
                                    fish_tail = bool(_ms_f.get('fish_tail'))
                                except Exception:
                                    pass
                                try:
                                    _tail10 = hist_data.tail(10)
                                    if len(_tail10) >= 10:
                                        _ma10n = float(_tail10['收盘'].astype(float).mean())
                                        if _ma10n > 0:
                                            ma10_latest_pct = (latest_price - _ma10n) / _ma10n * 100
                                            near_ma10_2pct = bool(0 <= ma10_latest_pct <= 2)
                                except Exception:
                                    pass
                                try:
                                    # 保存所有数据:周期涨跌幅、均线检测、最高最低值、jiuyan逻辑
                                    results.append({
                                        'stock_name': stock_name,
                                        'stock_code': stock_code,
                                        'total_count': count,
                                        'stock_sources': stock_sources,
                                        'total_source_count': total_source_count,
                                        'judgment_date': judgment_date_actual.strftime('%Y-%m-%d'),
                                        'judgment_price': judgment_price,
                                        'latest_date': latest_date.strftime('%Y-%m-%d'),
                                        'latest_price': latest_price,
                                        'days_since_judgment': days_since_judgment,
                                        'change_5d': change_5d,
                                        'change_10d': change_10d,
                                        'change_20d': change_20d,
                                        'change_to_now': change_to_now,
                                        'max_price': max_price,
                                        'max_date': max_date.strftime('%Y-%m-%d'),
                                        'min_price': min_price,
                                        'min_date': min_date.strftime('%Y-%m-%d'),
                                        'change_to_max': change_to_max,
                                        'change_to_min': change_to_min,
                                        'ma_diff_5': ma_diff_5,
                                        'ma_diff_10': ma_diff_10,
                                        'ma_diff_20': ma_diff_20,
                                        'ma_detection': ma_detection,
                                        'jiuyan_logic': jiuyan_logic,
                                        'speculator_info': speculator_info,
                                        'is_golden_stock': is_golden_stock,
                                        'fish_body': fish_body,
                                        'fish_tail': fish_tail,
                                        'ma10_latest_pct': ma10_latest_pct,
                                        'near_ma10_2pct': near_ma10_2pct,
                                    })
                                except Exception as e:
                                    results.append({
                                        'stock_name': stock_name,
                                        'stock_code': stock_code if 'stock_code' in locals() else '未知',
                                        'error': f'计算失败: {e!s}'
                                    })
                            except Exception as e:
                                results.append({
                                    'stock_name': stock_name,
                                    'stock_code': stock_code if 'stock_code' in locals() else '未知',
                                    'error': f'处理股票失败: {e!s}'
                                })
                                continue
                        # 在主线程中显示结果(调用外部定义的update_ui_with_results函数)
                        print(f"计算完成,共 {len(results)} 个结果")
                        if len(results) == 0:
                            def show_no_results():
                                try:
                                    result_text.insert(tk.END, "\n警告:没有计算出任何结果,请检查股票代码是否正确\n")
                                except Exception as e:
                                    print(f"显示无结果警告失败: {e}")
                            result_window.after(0, show_no_results)
                        else:
                            # 调用外部定义的update_ui_with_results函数,传递所有需要的参数
                            def safe_update():
                                try:
                                    print("开始更新UI显示结果...")
                                    # 存储计算结果供回测分析使用
                                    stored_results.clear()
                                    stored_results.extend(results)
                                    update_ui_with_results(results, judgment_date_str, sorted_stocks)
                                    print("UI更新完成")
                                except Exception as e:
                                    print(f"更新UI失败: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    try:
                                        result_text.delete("1.0", tk.END)
                                        result_text.insert("1.0", f"显示结果失败: {e!s}\n")
                                    except:
                                        pass
                            result_window.after(0, safe_update)
                    except Exception as e:
                        def show_error(e_val):
                            try:
                                result_text.delete("1.0", tk.END)
                                result_text.insert("1.0", f"计算失败: {e_val}\n")
                                import traceback
                                error_trace = traceback.format_exc()
                                result_text.insert(tk.END, error_trace)
                                print(f"计算异常: {e_val}")
                                traceback.print_exc()
                            except Exception as e2:
                                print(f"显示错误信息失败: {e2}")
                        result_window.after(0, lambda e=str(e): show_error(e))
                        import traceback
                        traceback.print_exc()
                # 在后台线程中运行计算
                try:
                    calc_thread = threading.Thread(target=calculate_changes, daemon=True)
                    calc_thread.start()
                    print(f"计算线程已启动,共 {len(sorted_stocks)} 个股票需要计算")
                except Exception as e:
                    result_text.delete("1.0", tk.END)
                    result_text.insert("1.0", f"启动计算线程失败: {e!s}\n")
                    import traceback
                    result_text.insert(tk.END, traceback.format_exc())
                    print(f"启动计算线程失败: {e}")
                    traceback.print_exc()
            def export_news_as_excel():
                """导出当前选中的资讯为Excel"""
                selection = news_tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择一条资讯")
                    return
                try:
                    item = news_tree.item(selection[0])
                    news_id = item['values'][0]
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('SELECT tab_name, content, created_at, updated_at FROM news_info WHERE id = ?', (news_id,))
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        tab_name, content, created_at, updated_at = row
                        from tkinter import filedialog
                        # 生成文件名:标签页名_数据时间_out导出时间
                        data_time = updated_at or created_at
                        # 格式化数据时间(转换为YYYYMMDD_HHMMSS格式)
                        if data_time:
                            try:
                                # 尝试解析时间字符串
                                dt = datetime.strptime(data_time, "%Y-%m-%d %H:%M:%S")
                                data_time_str = dt.strftime("%Y%m%d_%H%M%S")
                            except:
                                # 如果解析失败,使用原始字符串(去除特殊字符)
                                data_time_str = data_time.replace(':', '').replace('-', '').replace(' ', '_')[:15]
                        else:
                            data_time_str = ""
                        export_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                        safe_tab_name = "".join(c for c in tab_name if c.isalnum() or c in (' ', '-', '_')).strip()
                        safe_tab_name = safe_tab_name.replace(' ', '_')[:30]  # 限制长度
                        filename_base = f"{safe_tab_name}_{data_time_str}_out{export_time_str}" if data_time_str else f"{safe_tab_name}_out{export_time_str}"
                        filename = filedialog.asksaveasfilename(
                            defaultextension=".xlsx",
                            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")],
                            initialfile=f"{filename_base}.xlsx"
                        )
                        if filename:
                            try:
                                import xlsxwriter
                                workbook = xlsxwriter.Workbook(filename)
                                worksheet = workbook.add_worksheet()
                                # 写入标题行
                                headers = ["标签页名称", "内容", "创建时间", "更新时间"]
                                for col, header in enumerate(headers):
                                    worksheet.write(0, col, header)
                                # 写入数据
                                worksheet.write(1, 0, tab_name)
                                worksheet.write(1, 1, content)
                                worksheet.write(1, 2, created_at)
                                worksheet.write(1, 3, updated_at)
                                workbook.close()
                                messagebox.showinfo("成功", f"已保存到 {filename}")
                            except ImportError:
                                messagebox.showerror("错误", "需要安装 xlsxwriter 库: pip install xlsxwriter")
                            except Exception as e:
                                messagebox.showerror("错误", f"保存失败: {e}")
                except Exception as e:
                    messagebox.showerror("错误", f"导出失败: {e}")
            def export_news_as_long_image():
                """导出当前选中的资讯为长图"""
                selection = news_tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择一条资讯")
                    return
                try:
                    item = news_tree.item(selection[0])
                    news_id = item['values'][0]
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    # 一次查询获取所有需要的信息
                    cursor.execute('SELECT tab_name, content, created_at, updated_at FROM news_info WHERE id = ?', (news_id,))
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        tab_name, content, created_at, updated_at = row
                        data_time = updated_at or created_at
                        from tkinter import filedialog
                        # 生成文件名:标签页名_数据时间_out导出时间
                        # 格式化数据时间(转换为YYYYMMDD_HHMMSS格式)
                        if data_time:
                            try:
                                # 尝试解析时间字符串
                                dt = datetime.strptime(data_time, "%Y-%m-%d %H:%M:%S")
                                data_time_str = dt.strftime("%Y%m%d_%H%M%S")
                            except:
                                # 如果解析失败,使用原始字符串(去除特殊字符)
                                data_time_str = data_time.replace(':', '').replace('-', '').replace(' ', '_')[:15]
                        else:
                            data_time_str = ""
                        export_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                        safe_tab_name = "".join(c for c in tab_name if c.isalnum() or c in (' ', '-', '_')).strip()
                        safe_tab_name = safe_tab_name.replace(' ', '_')[:30]  # 限制长度
                        filename_base = f"{safe_tab_name}_{data_time_str}_out{export_time_str}" if data_time_str else f"{safe_tab_name}_out{export_time_str}"
                        filename = filedialog.asksaveasfilename(
                            defaultextension=".png",
                            filetypes=[("图片文件", "*.png"), ("所有文件", "*.*")],
                            initialfile=f"{filename_base}.png"
                        )
                        if filename:
                            try:
                                # 使用PIL创建长图
                                # 去除词云图片链接部分
                                import re
                                import textwrap

                                from PIL import Image, ImageDraw, ImageFont
                                text_content = re.sub(r'\[词云图片\].*?图片链接:.*?\n', '', content, flags=re.DOTALL)
                                text_content = re.sub(r'文件路径:.*?\n', '', text_content)
                                # 尝试加载中文字体
                                try:
                                    font = ImageFont.truetype("simhei.ttf", 20)
                                except:
                                    try:
                                        font = ImageFont.truetype("msyh.ttc", 20)
                                    except:
                                        font = ImageFont.load_default()
                                # 计算文本尺寸
                                lines = text_content.split('\n')
                                max_width = 800
                                wrapped_lines = []
                                for line in lines:
                                    wrapped_lines.extend(textwrap.wrap(line, width=50))
                                line_height = 30
                                img_height = len(wrapped_lines) * line_height + 100
                                img = Image.new('RGB', (max_width, img_height), 'white')
                                draw = ImageDraw.Draw(img)
                                # 绘制标题
                                draw.text((20, 20), tab_name, fill='black', font=font)
                                # 绘制内容
                                y = 60
                                for line in wrapped_lines:
                                    draw.text((20, y), line, fill='black', font=font)
                                    y += line_height
                                img.save(filename)
                                messagebox.showinfo("成功", f"已保存到 {filename}")
                            except Exception as e:
                                messagebox.showerror("错误", f"保存失败: {e}")
                except Exception as e:
                    messagebox.showerror("错误", f"导出失败: {e}")
            def copy_news_as_long_image():
                """复制当前选中的资讯为长图到剪贴板"""
                selection = news_tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择一条资讯")
                    return
                try:
                    item = news_tree.item(selection[0])
                    news_id = item['values'][0]
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('SELECT tab_name, content FROM news_info WHERE id = ?', (news_id,))
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        tab_name, content = row
                        try:
                            # 使用PIL创建长图
                            # 去除词云图片链接部分
                            import re
                            import textwrap

                            from PIL import Image, ImageDraw, ImageFont
                            text_content = re.sub(r'\[词云图片\].*?图片链接:.*?\n', '', content, flags=re.DOTALL)
                            text_content = re.sub(r'文件路径:.*?\n', '', text_content)
                            # 尝试加载中文字体
                            try:
                                font = ImageFont.truetype("simhei.ttf", 20)
                            except:
                                try:
                                    font = ImageFont.truetype("msyh.ttc", 20)
                                except:
                                    font = ImageFont.load_default()
                            # 计算文本尺寸
                            lines = text_content.split('\n')
                            max_width = 800
                            wrapped_lines = []
                            for line in lines:
                                wrapped_lines.extend(textwrap.wrap(line, width=50))
                            line_height = 30
                            img_height = len(wrapped_lines) * line_height + 100
                            img = Image.new('RGB', (max_width, img_height), 'white')
                            draw = ImageDraw.Draw(img)
                            # 绘制标题
                            draw.text((20, 20), tab_name, fill='black', font=font)
                            # 绘制内容
                            y = 60
                            for line in wrapped_lines:
                                draw.text((20, y), line, fill='black', font=font)
                                y += line_height
                            # 复制到剪贴板
                            try:
                                from io import BytesIO

                                import win32clipboard
                                output = BytesIO()
                                img.save(output, 'BMP')
                                data = output.getvalue()[14:]  # 跳过BMP头
                                output.close()
                                win32clipboard.OpenClipboard()
                                win32clipboard.EmptyClipboard()
                                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                                win32clipboard.CloseClipboard()
                                messagebox.showinfo("成功", "已复制长图到剪贴板")
                            except ImportError:
                                messagebox.showerror("错误", "需要安装 pywin32 库: pip install pywin32")
                            except Exception as e:
                                messagebox.showerror("错误", f"复制失败: {e}")
                        except Exception as e:
                            messagebox.showerror("错误", f"生成图片失败: {e}")
                except Exception as e:
                    messagebox.showerror("错误", f"操作失败: {e}")
            def copy_news_as_text():
                """复制当前选中的资讯为文字到剪贴板"""
                selection = news_tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择一条资讯")
                    return
                try:
                    item = news_tree.item(selection[0])
                    news_id = item['values'][0]
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('SELECT tab_name, content FROM news_info WHERE id = ?', (news_id,))
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        _tab_name, content = row
                        # 去除词云图片链接部分,只保留文本
                        import re
                        text_content = re.sub(r'\[词云图片\].*?图片链接:.*?\n', '', content, flags=re.DOTALL)
                        text_content = re.sub(r'文件路径:.*?\n', '', text_content)
                        # 复制到剪贴板
                        try:
                            db_window.clipboard_clear()
                            db_window.clipboard_append(text_content.strip())
                            messagebox.showinfo("成功", "已复制到剪贴板")
                        except Exception as e:
                            messagebox.showerror("错误", f"复制到剪贴板失败: {e}")
                except Exception as e:
                    messagebox.showerror("错误", f"复制失败: {e}")
            # 添加导出按钮
            ttk.Button(news_export_frame, text="一键导出成文字", command=export_news_as_text, width=15).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(news_export_frame, text="一键资讯分析", command=analyze_selected_news, width=15).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(news_export_frame, text="周期涨跌幅", command=lambda: calculate_period_changes(news_tree, db_window), width=15).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(news_export_frame, text="保存为Excel", command=export_news_as_excel, width=15).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(news_export_frame, text="保存长图", command=export_news_as_long_image, width=15).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(news_export_frame, text="作为长图复制", command=copy_news_as_long_image, width=15).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(news_export_frame, text="作为文字复制", command=copy_news_as_text, width=15).pack(side=tk.LEFT, padx=(0, 0))
            news_content_label = ttk.Label(news_content_tab, text="完整内容", font=("TkDefaultFont", 12, "bold"))
            news_content_label.pack(anchor=tk.W, pady=(0, 5))
            # 内容编辑按钮和缩放控制
            news_content_btn_frame = ttk.Frame(news_content_tab)
            news_content_btn_frame.pack(fill=tk.X, pady=(0, 5))
            content_edit_mode = tk.BooleanVar(value=False)
            current_editing_news_id = [None]
            auto_save_timer = [None]
            # 字体大小控制
            news_font_size = tk.IntVar(value=10)
            def increase_news_font():
                """增大资讯内容字体"""
                size = news_font_size.get()
                if size < 24:
                    news_font_size.set(size + 1)
                    news_content_text.config(font=("TkDefaultFont", size + 1))
            def decrease_news_font():
                """减小资讯内容字体"""
                size = news_font_size.get()
                if size > 8:
                    news_font_size.set(size - 1)
                    news_content_text.config(font=("TkDefaultFont", size - 1))
            ttk.Label(news_content_btn_frame, text="字体大小:").pack(side=tk.LEFT, padx=5)
            ttk.Button(news_content_btn_frame, text="放大", command=increase_news_font, width=8).pack(side=tk.LEFT, padx=2)
            ttk.Button(news_content_btn_frame, text="缩小", command=decrease_news_font, width=8).pack(side=tk.LEFT, padx=2)
            edit_btn = ttk.Button(news_content_btn_frame, text="编辑", command=lambda: [content_edit_mode.set(not content_edit_mode.get()), toggle_news_edit_mode()])
            edit_btn.pack(side=tk.LEFT, padx=(10, 0))
            auto_save_label = ttk.Label(news_content_btn_frame, text="(编辑模式下,修改后1秒自动保存)", font=("TkDefaultFont", 8), foreground="gray")
            auto_save_label.pack(side=tk.LEFT, padx=5)
            def get_current_news_id():
                """获取当前选中的资讯ID"""
                selection = news_tree.selection()
                if not selection:
                    return None
                item = news_tree.item(selection[0])
                return item['values'][0] if item['values'] else None
            def auto_save_news_content():
                """自动保存资讯内容"""
                if not content_edit_mode.get() or not current_editing_news_id[0]:
                    return
                news_id = current_editing_news_id[0]
                if news_id:
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        new_content = news_content_text.get("1.0", tk.END).strip()
                        cursor.execute('''
                            UPDATE news_info
                            SET content = ?, updated_at = ?
                            WHERE id = ?
                        ''', (new_content, current_time, news_id))
                        conn.commit()
                        conn.close()
                        refresh_news_data()
                    except Exception as e:
                        print(f"自动保存失败: {e}")
            def on_news_content_change(event=None):
                """资讯内容变化时触发自动保存"""
                if content_edit_mode.get() and current_editing_news_id[0]:
                    if auto_save_timer[0]:
                        db_window.after_cancel(auto_save_timer[0])
                    auto_save_timer[0] = db_window.after(1000, auto_save_news_content)
            def toggle_news_edit_mode():
                if content_edit_mode.get():
                    news_content_text.config(state=tk.NORMAL)
                    edit_btn.config(text="退出编辑")
                    current_news_id = get_current_news_id()
                    if current_news_id:
                        current_editing_news_id[0] = current_news_id
                        news_content_text.bind('<KeyRelease>', on_news_content_change)
                        news_content_text.bind('<Button-1>', on_news_content_change)
                else:
                    if current_editing_news_id[0]:
                        auto_save_news_content()
                    if auto_save_timer[0]:
                        db_window.after_cancel(auto_save_timer[0])
                        auto_save_timer[0] = None
                    news_content_text.unbind('<KeyRelease>')
                    news_content_text.unbind('<Button-1>')
                    news_content_text.config(state=tk.DISABLED)
                    edit_btn.config(text="编辑")
                    current_editing_news_id[0] = None
            news_content_frame_detail = ttk.LabelFrame(news_content_tab, text="完整内容", padding=5)
            news_content_frame_detail.pack(fill=tk.BOTH, expand=True)
            news_content_text = scrolledtext.ScrolledText(news_content_frame_detail, height=15, wrap=tk.WORD,
                                                          font=("TkDefaultFont", 12), state=tk.DISABLED)
            news_content_text.pack(fill=tk.BOTH, expand=True)
            # 配置链接样式
            news_content_text.tag_config("link", foreground="blue", underline=True)
            news_content_text.tag_bind("link", "<Button-1>", lambda e: self._open_link_from_text(e, news_content_text))
            news_content_text.tag_bind("link", "<Enter>", lambda e: news_content_text.config(cursor="hand2"))
            news_content_text.tag_bind("link", "<Leave>", lambda e: news_content_text.config(cursor=""))
            # 双击打开全窗口浏览
            def open_full_window_from_news_content(event):
                """双击资讯内容打开全窗口浏览"""
                try:
                    content = news_content_text.get("1.0", tk.END).strip()
                    if not content:
                        return
                    # 获取当前选中的资讯标题
                    selection = news_tree.selection()
                    if selection:
                        item = news_tree.item(selection[0])
                        title = item['values'][1] if len(item['values']) > 1 else "资讯内容"
                    else:
                        title = "资讯内容"
                    # 调用全窗口浏览功能(使用内容直接打开)
                    self.open_full_window_viewer_from_content(content, title)
                except Exception as e:
                    messagebox.showerror("错误", f"打开全窗口浏览失败: {e}", parent=db_window)
            news_content_text.bind("<Double-Button-1>", open_full_window_from_news_content)
            # 第二个标签页:起爆点数据表
            news_blast_point_tab = ttk.Frame(news_right_notebook)
            news_right_notebook.add(news_blast_point_tab, text="起爆点数据表")
            # 查询条件框架
            news_blast_query_frame = ttk.LabelFrame(news_blast_point_tab, text="查询条件", padding=10)
            news_blast_query_frame.pack(fill=tk.X, padx=5, pady=5)
            news_blast_date_frame = ttk.Frame(news_blast_query_frame)
            news_blast_date_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(news_blast_date_frame, text="分析日期:").pack(side=tk.LEFT, padx=5)
            news_blast_date_var = tk.StringVar()
            news_blast_date_entry = ttk.Entry(news_blast_date_frame, textvariable=news_blast_date_var, width=12)
            news_blast_date_entry.pack(side=tk.LEFT, padx=5)
            news_blast_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
            ttk.Label(news_blast_date_frame, text="股票名称:").pack(side=tk.LEFT, padx=5)
            news_blast_stock_name_var = tk.StringVar()
            news_blast_stock_name_entry = ttk.Entry(news_blast_date_frame, textvariable=news_blast_stock_name_var, width=20)
            news_blast_stock_name_entry.pack(side=tk.LEFT, padx=5)
            # 数据表格
            news_blast_table_frame = ttk.Frame(news_blast_point_tab)
            news_blast_table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            news_blast_columns = ("ID", "分析日期", "股票代码", "股票名称", "当前价格", "N日最低差%", "10日均线差%", "低差阈值", "均线阈值", "天数", "类型", "创建时间")
            news_blast_tree = ttk.Treeview(news_blast_table_frame, columns=news_blast_columns, show="headings", height=20)
            for col in news_blast_columns:
                news_blast_tree.heading(col, text=col)
                if col == "ID":
                    news_blast_tree.column(col, width=50, anchor=tk.CENTER)
                elif col == "分析日期" or col == "股票代码":
                    news_blast_tree.column(col, width=100, anchor=tk.CENTER)
                elif col == "股票名称":
                    news_blast_tree.column(col, width=120, anchor=tk.CENTER)
                elif col in ("当前价格", "N日最低差%", "10日均线差%", "低差阈值", "均线阈值"):
                    news_blast_tree.column(col, width=100, anchor=tk.CENTER)
                elif col == "天数":
                    news_blast_tree.column(col, width=60, anchor=tk.CENTER)
                elif col == "类型":
                    news_blast_tree.column(col, width=100, anchor=tk.CENTER)
                else:
                    news_blast_tree.column(col, width=150, anchor=tk.CENTER)
            news_blast_scrollbar = ttk.Scrollbar(news_blast_table_frame, orient=tk.VERTICAL, command=news_blast_tree.yview)
            news_blast_tree.configure(yscrollcommand=news_blast_scrollbar.set)
            news_blast_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            news_blast_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            def refresh_news_blast_point_data():
                """刷新起爆点数据"""
                try:
                    # 清空表格
                    for item in news_blast_tree.get_children():
                        news_blast_tree.delete(item)
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    # 确保起爆点数据表存在
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS blast_point_data (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            analysis_date TEXT NOT NULL,
                            stock_code TEXT NOT NULL,
                            stock_name TEXT NOT NULL,
                            current_price REAL,
                            low_diff_pct REAL,
                            ma10_diff_pct REAL,
                            low_threshold REAL,
                            ma10_threshold REAL,
                            days INTEGER,
                            type TEXT,
                            created_at TEXT,
                            updated_at TEXT
                        )
                    ''')
                    conn.commit()
                    # 构建查询条件
                    query = "SELECT * FROM blast_point_data WHERE 1=1"
                    params = []
                    date_filter = news_blast_date_var.get().strip()
                    if date_filter:
                        query += " AND analysis_date = ?"
                        params.append(date_filter)
                    stock_name_filter = news_blast_stock_name_var.get().strip()
                    if stock_name_filter:
                        query += " AND stock_name LIKE ?"
                        params.append(f"%{stock_name_filter}%")
                    query += " ORDER BY analysis_date DESC, created_at DESC"
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    for row in rows:
                        news_blast_tree.insert("", tk.END, values=row)
                    conn.close()
                except Exception as e:
                    messagebox.showerror("错误", f"刷新起爆点数据失败: {e}", parent=db_window)
            ttk.Button(news_blast_query_frame, text="查询", command=refresh_news_blast_point_data).pack(side=tk.LEFT, padx=10)
            ttk.Button(news_blast_query_frame, text="刷新", command=refresh_news_blast_point_data).pack(side=tk.LEFT, padx=5)
            # 初始加载数据
            refresh_news_blast_point_data()
            # 按钮框架
            news_button_frame = ttk.Frame(news_tab)
            news_button_frame.pack(fill=tk.X)
            def refresh_news_data():
                """刷新资讯数据"""
                for item in news_tree.get_children():
                    news_tree.delete(item)
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    tab_name_filter = tab_name_var.get().strip()
                    if tab_name_filter:
                        cursor.execute('''
                            SELECT id, tab_name, content, created_at, updated_at
                            FROM news_info
                            WHERE tab_name LIKE ?
                            ORDER BY created_at DESC
                        ''', (f'%{tab_name_filter}%',))
                    else:
                        cursor.execute('''
                            SELECT id, tab_name, content, created_at, updated_at
                            FROM news_info
                            ORDER BY created_at DESC
                        ''')
                    rows = cursor.fetchall()
                    conn.close()
                    for row in rows:
                        news_id, tab_name, content, created_at, updated_at = row
                        content_preview = content[:100] + "..." if content and len(content) > 100 else (content or "")
                        news_tree.insert("", tk.END, values=(news_id, tab_name, content_preview, created_at, updated_at))
                except Exception as e:
                    messagebox.showerror("错误", f"查询数据失败: {e}")
            def show_content_search_results(search_text, results):
                """显示内容搜索结果弹出框"""
                result_window = self._toplevel(db_window)
                result_window.title(f"内容查询结果 - 找到 {len(results)} 条")
                result_window.geometry("1200x800")
                result_window.resizable(True, True)
                # 主框架
                main_frame = ttk.Frame(result_window, padding=10)
                main_frame.pack(fill=tk.BOTH, expand=True)
                # 顶部:搜索信息和导航
                top_frame = ttk.Frame(main_frame)
                top_frame.pack(fill=tk.X, pady=(0, 10))
                ttk.Label(top_frame, text=f"搜索关键词: {search_text}", font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT, padx=5)
                ttk.Label(top_frame, text=f"找到 {len(results)} 条结果", font=("TkDefaultFont", 11), foreground="blue").pack(side=tk.LEFT, padx=10)
                # 当前结果索引
                current_index = [0]
                def update_current_info():
                    """更新当前结果信息"""
                    if results:
                        info_label.config(text=f"第 {current_index[0] + 1} / {len(results)} 条")
                    else:
                        info_label.config(text="无结果")
                info_label = ttk.Label(top_frame, text="", font=("TkDefaultFont", 11))
                info_label.pack(side=tk.LEFT, padx=10)
                update_current_info()
                # 导航按钮
                nav_frame = ttk.Frame(top_frame)
                nav_frame.pack(side=tk.RIGHT, padx=5)
                def go_to_previous():
                    """上一个结果"""
                    if results and current_index[0] > 0:
                        current_index[0] -= 1
                        display_current_result()
                        update_current_info()
                def go_to_next():
                    """下一个结果"""
                    if results and current_index[0] < len(results) - 1:
                        current_index[0] += 1
                        display_current_result()
                        update_current_info()
                def go_to_first():
                    """第一个结果"""
                    if results:
                        current_index[0] = 0
                        display_current_result()
                        update_current_info()
                def go_to_last():
                    """最后一个结果"""
                    if results:
                        current_index[0] = len(results) - 1
                        display_current_result()
                        update_current_info()
                def locate_in_table():
                    """定位到资讯数据表"""
                    if not results:
                        return
                    news_id = results[current_index[0]][0]
                    # 切换到资讯数据表标签页
                    main_notebook.select(news_tab)
                    # 在Treeview中查找并选中对应的行
                    for item in news_tree.get_children():
                        item_values = news_tree.item(item, 'values')
                        if item_values and len(item_values) > 0 and str(item_values[0]) == str(news_id):
                            news_tree.selection_set(item)
                            news_tree.see(item)
                            news_tree.focus(item)
                            # 触发选择事件以显示内容
                            on_news_select(None)
                            break
                    # 关闭结果窗口
                    result_window.destroy()
                ttk.Button(nav_frame, text="◀ 上一个", command=go_to_previous, width=10).pack(side=tk.LEFT, padx=2)
                ttk.Button(nav_frame, text="下一个 ▶", command=go_to_next, width=10).pack(side=tk.LEFT, padx=2)
                ttk.Button(nav_frame, text="定位", command=locate_in_table, width=10).pack(side=tk.LEFT, padx=2)
                # 结果列表框架(左侧)
                list_frame = ttk.LabelFrame(main_frame, text="结果列表", padding=5)
                list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5))
                list_frame.config(width=300)
                # 结果列表
                result_listbox = tk.Listbox(list_frame, width=35, font=("TkDefaultFont", 11))
                result_listbox.pack(fill=tk.BOTH, expand=True)
                # 填充结果列表
                for idx, (news_id, tab_name, content, created_at, updated_at) in enumerate(results):
                    # 在内容中查找关键词位置
                    if content and search_text.lower() in content.lower():
                        # 找到第一个匹配位置
                        match_pos = content.lower().find(search_text.lower())
                        start = max(0, match_pos - 30)
                        end = min(len(content), match_pos + len(search_text) + 30)
                        preview = content[start:end]
                        if start > 0:
                            preview = "..." + preview
                        if end < len(content):
                            preview = preview + "..."
                    else:
                        preview = (content[:60] + "...") if content and len(content) > 60 else (content or "")
                    display_text = f"[{idx+1}] {tab_name}\n   {preview}"
                    result_listbox.insert(tk.END, display_text)
                def on_listbox_select(event):
                    """列表选择事件"""
                    selection = result_listbox.curselection()
                    if selection:
                        current_index[0] = selection[0]
                        display_current_result()
                        update_current_info()
                result_listbox.bind('<<ListboxSelect>>', on_listbox_select)
                # 内容显示框架(右侧)
                content_frame = ttk.LabelFrame(main_frame, text="内容详情", padding=5)
                content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
                # 内容显示文本框
                content_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD,
                                                        font=("TkDefaultFont", 12))
                content_text.pack(fill=tk.BOTH, expand=True)
                # 配置高亮标签
                content_text.tag_config("highlight", background="yellow", foreground="black")
                content_text.tag_config("summary", font=("TkDefaultFont", 12, "bold"), foreground="blue")
                def display_current_result():
                    """显示当前结果"""
                    if not results or current_index[0] >= len(results):
                        return
                    news_id, tab_name, content, created_at, updated_at = results[current_index[0]]
                    # 清空内容
                    content_text.config(state=tk.NORMAL)
                    content_text.delete("1.0", tk.END)
                    # 显示概要信息
                    summary = f"ID: {news_id} | 标签页: {tab_name}\n"
                    summary += f"创建时间: {created_at} | 更新时间: {updated_at}\n"
                    summary += "=" * 80 + "\n\n"
                    content_text.insert("1.0", summary)
                    content_text.tag_add("summary", "1.0", f"{len(summary.split(chr(10)))}.0")
                    # 显示内容并高亮关键词
                    if content:
                        # 去除词云图片链接部分
                        import re
                        text_content = re.sub(r'\[词云图片\].*?图片链接:.*?\n', '', content, flags=re.DOTALL)
                        text_content = re.sub(r'文件路径:.*?\n', '', text_content)
                        # 插入内容并高亮关键词
                        # 使用更简单的方法:逐行插入并标记
                        lines = text_content.split('\n')
                        summary_lines = len(summary.split('\n'))
                        current_line = summary_lines
                        for line_idx, line in enumerate(lines):
                            if line_idx > 0:
                                content_text.insert(tk.END, '\n')
                                current_line += 1
                            # 在当前行中查找所有匹配的关键词
                            search_lower = search_text.lower()
                            line_lower = line.lower()
                            start_idx = 0
                            while True:
                                pos = line_lower.find(search_lower, start_idx)
                                if pos == -1:
                                    break
                                # 插入关键词之前的内容
                                if pos > start_idx:
                                    content_text.insert(tk.END, line[start_idx:pos])
                                # 插入并高亮关键词
                                highlight_start = content_text.index(tk.END + "-1c")
                                content_text.insert(tk.END, line[pos:pos + len(search_text)])
                                highlight_end = content_text.index(tk.END + "-1c")
                                content_text.tag_add("highlight", highlight_start, highlight_end)
                                start_idx = pos + len(search_text)
                            # 插入剩余内容
                            if start_idx < len(line):
                                content_text.insert(tk.END, line[start_idx:])
                    content_text.config(state=tk.DISABLED)
                    # 滚动到第一个高亮位置
                    try:
                        first_highlight = content_text.tag_ranges("highlight")
                        if first_highlight:
                            content_text.see(first_highlight[0])
                    except:
                        pass
                    # 更新列表选择
                    result_listbox.selection_clear(0, tk.END)
                    result_listbox.selection_set(current_index[0])
                    result_listbox.see(current_index[0])
                # 键盘事件绑定
                def on_key_press(event):
                    """处理键盘事件"""
                    if event.keysym == 'Up':
                        go_to_previous()
                        return "break"
                    elif event.keysym == 'Down':
                        go_to_next()
                        return "break"
                    elif event.keysym == 'Home':
                        go_to_first()
                        return "break"
                    elif event.keysym == 'End':
                        go_to_last()
                        return "break"
                    elif event.keysym == 'Return' and event.state & 0x4:  # Ctrl+Enter
                        locate_in_table()
                        return "break"
                result_window.bind('<KeyPress>', on_key_press)
                content_text.bind('<KeyPress>', on_key_press)
                result_listbox.bind('<KeyPress>', on_key_press)
                # 显示第一个结果
                if results:
                    display_current_result()
                    result_listbox.selection_set(0)
                    result_listbox.see(0)
                # 底部提示
                tip_label = ttk.Label(main_frame,
                    text="提示: 使用 ↑↓ 键切换结果,点击'定位'按钮或按 Ctrl+Enter 定位到资讯数据表",
                    font=("TkDefaultFont", 8), foreground="gray")
                tip_label.pack(side=tk.BOTTOM, pady=(5, 0))
            def on_news_select(event):
                """资讯数据选择事件处理"""
                if content_edit_mode.get() and current_editing_news_id[0]:
                    auto_save_news_content()
                    if auto_save_timer[0]:
                        db_window.after_cancel(auto_save_timer[0])
                        auto_save_timer[0] = None
                selection = news_tree.selection()
                if not selection:
                    return
                item = news_tree.item(selection[0])
                values = item['values']
                if len(values) >= 1:
                    news_id = values[0]
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT content FROM news_info WHERE id = ?
                        ''', (news_id,))
                        row = cursor.fetchone()
                        conn.close()
                        if row:
                            content = row[0]
                            # 清空内容显示区域
                            news_content_text.config(state=tk.NORMAL)
                            news_content_text.delete("1.0", tk.END)
                            # 检查内容中是否包含词云图片链接
                            wordcloud_path = None
                            if "[词云图片]" in content:
                                # 提取词云图片路径
                                import re
                                path_match = re.search(r'文件路径:\s*(.+)', content)
                                if path_match:
                                    wordcloud_path = path_match.group(1).strip()
                            # 如果找到词云图片路径,显示图片
                            if wordcloud_path and os.path.exists(wordcloud_path):
                                try:
                                    # 加载并显示词云图片
                                    wordcloud_image = Image.open(wordcloud_path)
                                    # 调整图片大小(宽度600,保持比例)
                                    original_width, original_height = wordcloud_image.size
                                    aspect_ratio = original_height / original_width
                                    new_width = 600
                                    new_height = int(new_width * aspect_ratio)
                                    wordcloud_image = wordcloud_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                                    wordcloud_photo = ImageTk.PhotoImage(wordcloud_image)
                                    # 插入文本内容(去除词云图片链接部分)
                                    text_content = re.sub(r'\[词云图片\].*?图片链接:.*?\n', '', content, flags=re.DOTALL)
                                    text_content = re.sub(r'文件路径:.*?\n', '', text_content)
                                    if text_content.strip():
                                        news_content_text.insert("1.0", text_content.strip() + "\n\n")
                                    # 插入词云图片
                                    news_content_text.insert(tk.END, "\n[词云图片]\n")
                                    news_content_text.image_create(tk.END, image=wordcloud_photo)
                                    news_content_text.insert(tk.END, "\n")
                                    # 保存图片引用,防止被垃圾回收
                                    if not hasattr(news_content_text, 'wordcloud_images'):
                                        news_content_text.wordcloud_images = []
                                    news_content_text.wordcloud_images.append(wordcloud_photo)
                                    # 标记链接(使用处理后的文本内容)
                                    self._mark_links_in_text(news_content_text, text_content.strip() if text_content.strip() else "")
                                except Exception as e:
                                    print(f"加载词云图片失败: {e}")
                                    # 如果图片加载失败,显示原始内容
                                    news_content_text.insert("1.0", content)
                                    # 标记链接
                                    self._mark_links_in_text(news_content_text, content)
                            else:
                                # 没有词云图片,直接显示文本内容
                                news_content_text.insert("1.0", content)
                                # 标记链接
                                self._mark_links_in_text(news_content_text, content)
                            # 如果不是编辑模式,禁用编辑
                            if not content_edit_mode.get():
                                news_content_text.config(state=tk.DISABLED)
                    except Exception as e:
                        messagebox.showerror("错误", f"加载内容失败: {e}")
                    # 重置编辑模式
                    if not content_edit_mode.get():
                        content_edit_mode.set(False)
                        news_content_text.config(state=tk.DISABLED)
                        edit_btn.config(text="编辑")
                        news_content_text.unbind('<KeyRelease>')
                        news_content_text.unbind('<Button-1>')
                    current_editing_news_id[0] = None
            news_tree.bind("<<TreeviewSelect>>", on_news_select)
            def delete_news():
                """删除选中的资讯"""
                selection = news_tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择一条资讯")
                    return
                if messagebox.askyesno("确认", "确定要删除这条资讯吗?"):
                    try:
                        item = news_tree.item(selection[0])
                        news_id = item['values'][0]
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('DELETE FROM news_info WHERE id = ?', (news_id,))
                        conn.commit()
                        conn.close()
                        refresh_news_data()
                        news_content_text.delete("1.0", tk.END)
                        messagebox.showinfo("成功", "已删除")
                    except Exception as e:
                        messagebox.showerror("错误", f"删除失败: {e}")
            def add_news():
                """新增资讯"""
                add_window = self._toplevel(db_window)
                add_window.title("新增资讯")
                add_window.geometry("600x500")
                ttk.Label(add_window, text="标签页名称:").pack(anchor=tk.W, padx=10, pady=(10, 5))
                tab_name_entry = ttk.Entry(add_window, width=50)
                tab_name_entry.pack(fill=tk.X, padx=10, pady=(0, 10))
                ttk.Label(add_window, text="内容:").pack(anchor=tk.W, padx=10, pady=(0, 5))
                content_text = scrolledtext.ScrolledText(add_window, height=15, wrap=tk.WORD)
                content_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
                def save_new_news():
                    tab_name = tab_name_entry.get().strip()
                    content = content_text.get("1.0", tk.END).strip()
                    if not tab_name:
                        messagebox.showwarning("警告", "请输入标签页名称")
                        return
                    if not content:
                        messagebox.showwarning("警告", "请输入内容")
                        return
                    if save_news_info_to_db(tab_name, content):
                        messagebox.showinfo("成功", "已保存")
                        refresh_news_data()
                        add_window.destroy()
                    else:
                        messagebox.showerror("错误", "保存失败")
                button_frame = ttk.Frame(add_window)
                button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
                ttk.Button(button_frame, text="保存", command=save_new_news).pack(side=tk.LEFT, padx=(0, 5))
                ttk.Button(button_frame, text="取消", command=add_window.destroy).pack(side=tk.LEFT, padx=(0, 0))
            ttk.Button(news_query_frame, text="查询", command=refresh_news_data).pack(side=tk.LEFT, padx=(10, 0))
            ttk.Button(news_query_frame, text="新增", command=add_news).pack(side=tk.LEFT, padx=(5, 0))
            ttk.Button(news_button_frame, text="刷新", command=refresh_news_data).pack(side=tk.LEFT, padx=5)
            ttk.Button(news_button_frame, text="删除", command=delete_news).pack(side=tk.LEFT, padx=5)
            ttk.Button(news_button_frame, text="关闭", command=db_window.destroy).pack(side=tk.RIGHT, padx=5)
            # 初始加载资讯数据
            refresh_news_data()
            # ==================== 龙虎榜数据表标签页 ====================
            lhb_tab = ttk.Frame(main_notebook)
            main_notebook.add(lhb_tab, text="龙虎榜数据表")
            # 查询条件框架
            lhb_query_frame = ttk.LabelFrame(lhb_tab, text="查询条件", padding=10)
            lhb_query_frame.pack(fill=tk.X, pady=(0, 10))
            lhb_date_frame = ttk.Frame(lhb_query_frame)
            lhb_date_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(lhb_date_frame, text="交易日期:").pack(side=tk.LEFT, padx=5)
            lhb_date_var = tk.StringVar()
            lhb_date_entry = ttk.Entry(lhb_date_frame, textvariable=lhb_date_var, width=12)
            lhb_date_entry.pack(side=tk.LEFT, padx=5)
            ttk.Label(lhb_date_frame, text="股票代码/名称:").pack(side=tk.LEFT, padx=5)
            lhb_stock_var = tk.StringVar()
            lhb_stock_entry = ttk.Entry(lhb_date_frame, textvariable=lhb_stock_var, width=20)
            lhb_stock_entry.pack(side=tk.LEFT, padx=5)
            # 数据表格和右侧内容(左右布局)
            lhb_content_frame = ttk.Frame(lhb_tab)
            lhb_content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            # 左侧:数据表格
            lhb_left_content = ttk.Frame(lhb_content_frame)
            lhb_left_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
            lhb_table_label = ttk.Label(lhb_left_content, text="龙虎榜数据列表", font=("TkDefaultFont", 12, "bold"))
            lhb_table_label.pack(anchor=tk.W, pady=(0, 5))
            lhb_tree_frame = ttk.Frame(lhb_left_content)
            lhb_tree_frame.pack(fill=tk.BOTH, expand=True)
            # 右侧:起爆点数据表
            lhb_right_content = ttk.Frame(lhb_content_frame)
            lhb_right_content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
            # 右侧标签页
            lhb_right_notebook = ttk.Notebook(lhb_right_content)
            lhb_right_notebook.pack(fill=tk.BOTH, expand=True)
            # 起爆点数据表标签页
            lhb_blast_point_tab = ttk.Frame(lhb_right_notebook)
            lhb_right_notebook.add(lhb_blast_point_tab, text="起爆点数据表")
            # 查询条件框架
            lhb_blast_query_frame = ttk.LabelFrame(lhb_blast_point_tab, text="查询条件", padding=10)
            lhb_blast_query_frame.pack(fill=tk.X, padx=5, pady=5)
            lhb_blast_date_frame = ttk.Frame(lhb_blast_query_frame)
            lhb_blast_date_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(lhb_blast_date_frame, text="分析日期:").pack(side=tk.LEFT, padx=5)
            lhb_blast_date_var = tk.StringVar()
            lhb_blast_date_entry = ttk.Entry(lhb_blast_date_frame, textvariable=lhb_blast_date_var, width=12)
            lhb_blast_date_entry.pack(side=tk.LEFT, padx=5)
            lhb_blast_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
            ttk.Label(lhb_blast_date_frame, text="股票名称:").pack(side=tk.LEFT, padx=5)
            lhb_blast_stock_name_var = tk.StringVar()
            lhb_blast_stock_name_entry = ttk.Entry(lhb_blast_date_frame, textvariable=lhb_blast_stock_name_var, width=20)
            lhb_blast_stock_name_entry.pack(side=tk.LEFT, padx=5)
            # 数据表格
            lhb_blast_table_frame = ttk.Frame(lhb_blast_point_tab)
            lhb_blast_table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            lhb_blast_columns = ("ID", "分析日期", "股票代码", "股票名称", "当前价格", "N日最低差%", "10日均线差%", "低差阈值", "均线阈值", "天数", "类型", "创建时间")
            lhb_blast_tree = ttk.Treeview(lhb_blast_table_frame, columns=lhb_blast_columns, show="headings", height=20)
            for col in lhb_blast_columns:
                lhb_blast_tree.heading(col, text=col)
                if col == "ID":
                    lhb_blast_tree.column(col, width=50, anchor=tk.CENTER)
                elif col == "分析日期" or col == "股票代码":
                    lhb_blast_tree.column(col, width=100, anchor=tk.CENTER)
                elif col == "股票名称":
                    lhb_blast_tree.column(col, width=120, anchor=tk.CENTER)
                elif col in ("当前价格", "N日最低差%", "10日均线差%", "低差阈值", "均线阈值"):
                    lhb_blast_tree.column(col, width=100, anchor=tk.CENTER)
                elif col == "天数":
                    lhb_blast_tree.column(col, width=60, anchor=tk.CENTER)
                elif col == "类型":
                    lhb_blast_tree.column(col, width=100, anchor=tk.CENTER)
                else:
                    lhb_blast_tree.column(col, width=150, anchor=tk.CENTER)
            lhb_blast_scrollbar = ttk.Scrollbar(lhb_blast_table_frame, orient=tk.VERTICAL, command=lhb_blast_tree.yview)
            lhb_blast_tree.configure(yscrollcommand=lhb_blast_scrollbar.set)
            lhb_blast_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            lhb_blast_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            def refresh_lhb_blast_point_data():
                """刷新起爆点数据"""
                try:
                    # 清空表格
                    for item in lhb_blast_tree.get_children():
                        lhb_blast_tree.delete(item)
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    # 确保起爆点数据表存在
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS blast_point_data (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            analysis_date TEXT NOT NULL,
                            stock_code TEXT NOT NULL,
                            stock_name TEXT NOT NULL,
                            current_price REAL,
                            low_diff_pct REAL,
                            ma10_diff_pct REAL,
                            low_threshold REAL,
                            ma10_threshold REAL,
                            days INTEGER,
                            type TEXT,
                            created_at TEXT,
                            updated_at TEXT
                        )
                    ''')
                    conn.commit()
                    # 构建查询条件
                    query = "SELECT * FROM blast_point_data WHERE 1=1"
                    params = []
                    date_filter = lhb_blast_date_var.get().strip()
                    if date_filter:
                        query += " AND analysis_date = ?"
                        params.append(date_filter)
                    stock_name_filter = lhb_blast_stock_name_var.get().strip()
                    if stock_name_filter:
                        query += " AND stock_name LIKE ?"
                        params.append(f"%{stock_name_filter}%")
                    query += " ORDER BY analysis_date DESC, created_at DESC"
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    for row in rows:
                        lhb_blast_tree.insert("", tk.END, values=row)
                    conn.close()
                except Exception as e:
                    messagebox.showerror("错误", f"刷新起爆点数据失败: {e}", parent=db_window)
            ttk.Button(lhb_blast_query_frame, text="查询", command=refresh_lhb_blast_point_data).pack(side=tk.LEFT, padx=10)
            ttk.Button(lhb_blast_query_frame, text="刷新", command=refresh_lhb_blast_point_data).pack(side=tk.LEFT, padx=5)
            # 初始加载数据
            refresh_lhb_blast_point_data()
            lhb_columns = ("ID", "交易日期", "代码", "名称", "收盘价", "涨跌幅", "换手率",
                          "总成交额", "龙虎榜成交额", "净买入", "净买入占比", "成交占比", "流通市值", "上榜理由")
            lhb_tree = ttk.Treeview(lhb_tree_frame, columns=lhb_columns, show="headings", height=25)
            lhb_headings = {
                "ID": "ID",
                "交易日期": "交易日期",
                "代码": "代码",
                "名称": "名称",
                "收盘价": "收盘价",
                "涨跌幅": "涨跌幅(%)",
                "换手率": "换手率(%)",
                "总成交额": "总成交额(元)",
                "龙虎榜成交额": "龙虎榜成交额(元)",
                "净买入": "净买入(元)",
                "净买入占比": "净买入占比(%)",
                "成交占比": "成交占比(%)",
                "流通市值": "流通市值(元)",
                "上榜理由": "上榜理由"
            }
            lhb_col_widths = {
                "ID": 50,
                "交易日期": 100,
                "代码": 90,
                "名称": 90,
                "收盘价": 80,
                "涨跌幅": 90,
                "换手率": 90,
                "总成交额": 140,
                "龙虎榜成交额": 140,
                "净买入": 140,
                "净买入占比": 110,
                "成交占比": 110,
                "流通市值": 150,
                "上榜理由": 260
            }
            for col in lhb_columns:
                lhb_tree.heading(col, text=lhb_headings.get(col, col))
                lhb_tree.column(col, width=lhb_col_widths.get(col, 100), anchor=tk.CENTER)
            lhb_tree.tag_configure("net_positive", foreground="#d32f2f")
            lhb_tree.tag_configure("net_negative", foreground="#1b5e20")
            lhb_scrollbar = ttk.Scrollbar(lhb_tree_frame, orient=tk.VERTICAL, command=lhb_tree.yview)
            lhb_tree.configure(yscrollcommand=lhb_scrollbar.set)
            lhb_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            lhb_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            def fmt_lhb_value(value, digits=2, suffix=""):
                """格式化龙虎榜数值"""
                if value is None or value == "":
                    return "--"
                try:
                    return f"{float(value):,.{digits}f}{suffix}"
                except Exception:
                    return str(value)
            def fmt_lhb_pct(value):
                """格式化百分比"""
                if value is None or value == "":
                    return "--"
                try:
                    return f"{float(value):+.2f}%"
                except Exception:
                    return str(value)
            def fmt_lhb_large(value):
                """格式化大数值(万元/亿元)"""
                if value is None or value == "":
                    return "--"
                try:
                    v = float(value)
                    if abs(v) >= 1e8:
                        return f"{v/1e8:.2f}亿"
                    if abs(v) >= 1e4:
                        return f"{v/1e4:.2f}万"
                    return f"{v:,.0f}"
                except Exception:
                    return str(value)
            def refresh_lhb_data():
                """刷新龙虎榜数据"""
                for item in lhb_tree.get_children():
                    lhb_tree.delete(item)
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    date_filter = lhb_date_var.get().strip()
                    stock_filter = lhb_stock_var.get().strip()
                    query = '''
                        SELECT id, trade_date, ts_code, name, close, pct_change, turnover_rate,
                               amount, l_amount, net_amount, net_rate, amount_rate, float_values, reason
                        FROM lhb_records
                        WHERE 1=1
                    '''
                    params = []
                    if date_filter:
                        query += " AND trade_date LIKE ?"
                        params.append(f'%{date_filter}%')
                    if stock_filter:
                        query += " AND (ts_code LIKE ? OR name LIKE ?)"
                        params.append(f'%{stock_filter}%')
                        params.append(f'%{stock_filter}%')
                    query += " ORDER BY trade_date DESC, net_amount DESC"
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    conn.close()
                    for row in results:
                        (lhb_id, trade_date, ts_code, name, close, pct_change, turnover_rate,
                         amount, l_amount, net_amount, net_rate, amount_rate, float_values, reason) = row
                        net_amount_val = net_amount or 0
                        tags = []
                        if net_amount_val > 0:
                            tags.append("net_positive")
                        elif net_amount_val < 0:
                            tags.append("net_negative")
                        values = (
                            lhb_id,
                            trade_date,
                            ts_code,
                            name or "--",
                            fmt_lhb_value(close),
                            fmt_lhb_pct(pct_change),
                            fmt_lhb_pct(turnover_rate),
                            fmt_lhb_large(amount),
                            fmt_lhb_large(l_amount),
                            fmt_lhb_large(net_amount),
                            fmt_lhb_pct(net_rate),
                            fmt_lhb_pct(amount_rate),
                            fmt_lhb_large(float_values),
                            reason or "--"
                        )
                        lhb_tree.insert("", tk.END, values=values, tags=tags)
                except Exception as e:
                    messagebox.showerror("错误", f"查询龙虎榜数据失败: {e}")
            ttk.Button(lhb_query_frame, text="查询", command=refresh_lhb_data).pack(side=tk.LEFT, padx=(10, 5))
            # 一键导入按钮
            def import_lhb_to_stock_db():
                """将龙虎榜数据导入到股票数据表"""
                try:
                    # 获取选中的数据或按日期筛选的数据
                    selections = lhb_tree.selection()
                    date_filter = lhb_date_var.get().strip()
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    if selections:
                        # 导入选中的数据
                        records_to_import = []
                        for item_id in selections:
                            item = lhb_tree.item(item_id)
                            values = item['values']
                            if len(values) >= 14:
                                lhb_id = values[0]
                                # 从数据库获取完整记录
                                cursor.execute('''
                                    SELECT trade_date, ts_code, name, close, pct_change,
                                           net_amount, l_amount, reason
                                    FROM lhb_records
                                    WHERE id = ?
                                ''', (lhb_id,))
                                row = cursor.fetchone()
                                if row:
                                    records_to_import.append(row)
                    else:
                        # 按日期筛选导入
                        if not date_filter:
                            messagebox.showwarning("提示", "请选择数据或输入日期进行导入", parent=db_window)
                            conn.close()
                            return
                        cursor.execute('''
                            SELECT trade_date, ts_code, name, close, pct_change,
                                   net_amount, l_amount, reason
                            FROM lhb_records
                            WHERE trade_date LIKE ?
                            ORDER BY trade_date DESC, net_amount DESC
                        ''', (f'%{date_filter}%',))
                        records_to_import = cursor.fetchall()
                    if not records_to_import:
                        messagebox.showwarning("提示", "没有可导入的数据", parent=db_window)
                        conn.close()
                        return
                    # 导入数据到stock_logic表
                    success_count = 0
                    failed_count = 0
                    failed_items = []
                    for record in records_to_import:
                        trade_date, ts_code, name, close, pct_change, net_amount, l_amount, reason = record
                        # 提取股票代码(去掉.SH/.SZ后缀)
                        stock_code = ts_code.split('.')[0] if '.' in ts_code else ts_code
                        stock_name = name or stock_code
                        # 格式化日期
                        if len(trade_date) == 8:
                            formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
                        else:
                            formatted_date = trade_date
                        # 构建逻辑内容:龙虎榜和日期和流入流出资金额
                        logic_parts = []
                        logic_parts.append(f"龙虎榜日期: {formatted_date}")
                        if net_amount is not None:
                            if net_amount > 0:
                                logic_parts.append(f"净买入: {net_amount:,.0f}元")
                            else:
                                logic_parts.append(f"净卖出: {abs(net_amount):,.0f}元")
                        if l_amount is not None:
                            logic_parts.append(f"龙虎榜成交额: {l_amount:,.0f}元")
                        if reason:
                            logic_parts.append(f"上榜理由: {reason}")
                        if close is not None:
                            logic_parts.append(f"收盘价: {close:.2f}")
                        if pct_change is not None:
                            logic_parts.append(f"涨跌幅: {pct_change:.2f}%")
                        logic_content = " | ".join(logic_parts)
                        # 保存到stock_logic表
                        try:
                            cursor.execute('''
                                INSERT INTO stock_logic (stock_name, logic, date, source)
                                VALUES (?, ?, ?, ?)
                            ''', (stock_name, logic_content, formatted_date, "龙虎榜"))
                            success_count += 1
                        except Exception as e:
                            failed_count += 1
                            failed_items.append(f"{stock_name}({stock_code}): {str(e)[:30]}")
                    conn.commit()
                    conn.close()
                    # 显示导入结果
                    result_msg = f"导入完成!\n成功: {success_count} 条"
                    if failed_count > 0:
                        result_msg += f"\n失败: {failed_count} 条"
                        if len(failed_items) <= 10:
                            result_msg += "\n失败详情:\n" + "\n".join(failed_items)
                        else:
                            result_msg += "\n失败详情(前10条):\n" + "\n".join(failed_items[:10])
                    messagebox.showinfo("导入结果", result_msg, parent=db_window)
                    # 如果当前在股票数据表标签页,刷新数据
                    if default_tab == "stock" or main_notebook.index(main_notebook.select()) == 0:
                        # 触发股票数据表的刷新(如果存在)
                        pass
                except Exception as e:
                    messagebox.showerror("错误", f"导入失败: {e}", parent=db_window)
                    import traceback
                    traceback.print_exc()
            ttk.Button(lhb_query_frame, text="一键导入", command=import_lhb_to_stock_db, width=12).pack(side=tk.LEFT, padx=(0, 0))
            # 一键导出功能
            def export_lhb_data():
                """导出龙虎榜数据到Excel"""
                try:
                    # 获取所有数据
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    date_filter = lhb_date_var.get().strip()
                    stock_filter = lhb_stock_var.get().strip()
                    query = '''
                        SELECT trade_date, ts_code, name, close, pct_change, turnover_rate,
                               amount, l_amount, net_amount, net_rate, amount_rate, float_values, reason
                        FROM lhb_records
                        WHERE 1=1
                    '''
                    params = []
                    if date_filter:
                        query += " AND trade_date LIKE ?"
                        params.append(f'%{date_filter}%')
                    if stock_filter:
                        query += " AND (ts_code LIKE ? OR name LIKE ?)"
                        params.append(f'%{stock_filter}%')
                        params.append(f'%{stock_filter}%')
                    query += " ORDER BY trade_date DESC, net_amount DESC"
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    conn.close()
                    if not results:
                        messagebox.showwarning("提示", "没有数据可导出", parent=db_window)
                        return
                    # 转换为DataFrame
                    data = []
                    for row in results:
                        (trade_date, ts_code, name, close, pct_change, turnover_rate,
                         amount, l_amount, net_amount, net_rate, amount_rate, float_values, reason) = row
                        data.append({
                            "交易日期": trade_date,
                            "股票代码": ts_code or "",
                            "股票名称": name or "",
                            "收盘价": close if close is not None else "",
                            "涨跌幅(%)": f"{pct_change:.2f}%" if pct_change is not None else "",
                            "换手率(%)": f"{turnover_rate:.2f}%" if turnover_rate is not None else "",
                            "总成交额(元)": f"{amount:,.0f}" if amount is not None else "",
                            "龙虎榜成交额(元)": f"{l_amount:,.0f}" if l_amount is not None else "",
                            "净买入(元)": f"{net_amount:,.0f}" if net_amount is not None else "",
                            "净买入占比(%)": f"{net_rate:.2f}%" if net_rate is not None else "",
                            "成交占比(%)": f"{amount_rate:.2f}%" if amount_rate is not None else "",
                            "流通市值(元)": f"{float_values:,.0f}" if float_values is not None else "",
                            "上榜理由": reason or ""
                        })
                    df = pd.DataFrame(data)
                    # 选择保存路径
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    default_filename = f"龙虎榜数据_{timestamp}.xlsx"
                    filepath = filedialog.asksaveasfilename(
                        parent=db_window,
                        title="保存龙虎榜数据",
                        defaultextension=".xlsx",
                        filetypes=[("Excel文件", "*.xlsx"), ("CSV文件", "*.csv"), ("所有文件", "*.*")],
                        initialfile=default_filename
                    )
                    if not filepath:
                        return
                    # 导出文件
                    if filepath.endswith('.csv'):
                        df.to_csv(filepath, index=False, encoding='utf-8-sig')
                    else:
                        # 尝试使用openpyxl导出Excel
                        try:
                            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                                df.to_excel(writer, sheet_name='龙虎榜数据', index=False)
                                # 设置列宽
                                worksheet = writer.sheets['龙虎榜数据']
                                from openpyxl.utils import get_column_letter
                                for i, col in enumerate(df.columns, 1):
                                    col_letter = get_column_letter(i)
                                    if col == "上榜理由":
                                        worksheet.column_dimensions[col_letter].width = 50
                                    elif col in ["交易日期", "股票代码", "股票名称"]:
                                        worksheet.column_dimensions[col_letter].width = 15
                                    else:
                                        worksheet.column_dimensions[col_letter].width = 18
                        except ImportError:
                            # 如果没有openpyxl,使用xlsxwriter
                            try:
                                with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
                                    df.to_excel(writer, sheet_name='龙虎榜数据', index=False)
                            except ImportError:
                                # 如果都没有,保存为CSV
                                filepath = filepath.replace('.xlsx', '.csv')
                                df.to_csv(filepath, index=False, encoding='utf-8-sig')
                                messagebox.showinfo("提示", f"已导出为CSV格式(Excel引擎不可用)\n文件路径:{filepath}", parent=db_window)
                                return
                    messagebox.showinfo("成功", f"已成功导出 {len(results)} 条数据\n文件路径:{filepath}", parent=db_window)
                except Exception as e:
                    messagebox.showerror("错误", f"导出失败: {e}", parent=db_window)
                    import traceback
                    traceback.print_exc()
            # 一键拷贝功能
            def copy_lhb_data():
                """复制龙虎榜数据到剪贴板"""
                try:
                    selections = lhb_tree.selection()
                    if not selections:
                        # 如果没有选中,复制所有显示的数据
                        all_items = lhb_tree.get_children()
                        if not all_items:
                            messagebox.showwarning("提示", "没有数据可复制", parent=db_window)
                            return
                        selections = all_items
                    lines = []
                    # 添加表头
                    header_line = "\t".join(lhb_columns)
                    lines.append(header_line)
                    # 添加数据行
                    for item_id in selections:
                        item = lhb_tree.item(item_id)
                        values = item['values']
                        lines.append("\t".join(str(v) for v in values))
                    text = "\n".join(lines)
                    db_window.clipboard_clear()
                    db_window.clipboard_append(text)
                    db_window.update()
                    count = len(selections)
                    messagebox.showinfo("成功", f"已复制 {count} 条数据到剪贴板", parent=db_window)
                except Exception as e:
                    messagebox.showerror("错误", f"复制失败: {e}", parent=db_window)
            ttk.Button(lhb_query_frame, text="一键导出", command=export_lhb_data, width=12).pack(side=tk.LEFT, padx=(5, 0))
            ttk.Button(lhb_query_frame, text="一键拷贝", command=copy_lhb_data, width=12).pack(side=tk.LEFT, padx=(5, 0))
            # 导出选中数据功能
            def export_selected_lhb_to_excel():
                """导出选中的龙虎榜数据到Excel"""
                selections = lhb_tree.selection()
                if not selections:
                    messagebox.showwarning("提示", "请先选择要导出的数据", parent=db_window)
                    return
                try:
                    # 获取选中的数据
                    selected_data = []
                    for item_id in selections:
                        item = lhb_tree.item(item_id)
                        values = item['values']
                        if values:
                            # 从数据库获取完整数据
                            lhb_id = values[0]
                            conn = sqlite3.connect(DB_PATH)
                            cursor = conn.cursor()
                            cursor.execute('''
                                SELECT trade_date, ts_code, name, close, pct_change, turnover_rate,
                                       amount, l_amount, net_amount, net_rate, amount_rate, float_values, reason
                                FROM lhb_records
                                WHERE id = ?
                            ''', (lhb_id,))
                            row = cursor.fetchone()
                            conn.close()
                            if row:
                                (trade_date, ts_code, name, close, pct_change, turnover_rate,
                                 amount, l_amount, net_amount, net_rate, amount_rate, float_values, reason) = row
                                selected_data.append({
                                    "交易日期": trade_date,
                                    "股票代码": ts_code or "",
                                    "股票名称": name or "",
                                    "收盘价": close if close is not None else "",
                                    "涨跌幅(%)": f"{pct_change:.2f}%" if pct_change is not None else "",
                                    "换手率(%)": f"{turnover_rate:.2f}%" if turnover_rate is not None else "",
                                    "总成交额(元)": f"{amount:,.0f}" if amount is not None else "",
                                    "龙虎榜成交额(元)": f"{l_amount:,.0f}" if l_amount is not None else "",
                                    "净买入(元)": f"{net_amount:,.0f}" if net_amount is not None else "",
                                    "净买入占比(%)": f"{net_rate:.2f}%" if net_rate is not None else "",
                                    "成交占比(%)": f"{amount_rate:.2f}%" if amount_rate is not None else "",
                                    "流通市值(元)": f"{float_values:,.0f}" if float_values is not None else "",
                                    "上榜理由": reason or ""
                                })
                    if not selected_data:
                        messagebox.showwarning("提示", "没有可导出的数据", parent=db_window)
                        return
                    df = pd.DataFrame(selected_data)
                    # 选择保存路径
                    from tkinter import filedialog
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    default_filename = f"龙虎榜选中数据_{timestamp}.xlsx"
                    filepath = filedialog.asksaveasfilename(
                        parent=db_window,
                        title="保存龙虎榜数据",
                        defaultextension=".xlsx",
                        filetypes=[("Excel文件", "*.xlsx"), ("CSV文件", "*.csv"), ("所有文件", "*.*")],
                        initialfile=default_filename
                    )
                    if not filepath:
                        return
                    # 导出文件
                    if filepath.endswith('.csv'):
                        df.to_csv(filepath, index=False, encoding='utf-8-sig')
                    else:
                        try:
                            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                                df.to_excel(writer, sheet_name='龙虎榜数据', index=False)
                                # 设置列宽
                                worksheet = writer.sheets['龙虎榜数据']
                                from openpyxl.utils import get_column_letter
                                for i, col in enumerate(df.columns, 1):
                                    col_letter = get_column_letter(i)
                                    if col == "上榜理由":
                                        worksheet.column_dimensions[col_letter].width = 50
                                    elif col in ["交易日期", "股票代码", "股票名称"]:
                                        worksheet.column_dimensions[col_letter].width = 15
                                    else:
                                        worksheet.column_dimensions[col_letter].width = 18
                        except ImportError:
                            try:
                                with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
                                    df.to_excel(writer, sheet_name='龙虎榜数据', index=False)
                            except ImportError:
                                filepath = filepath.replace('.xlsx', '.csv')
                                df.to_csv(filepath, index=False, encoding='utf-8-sig')
                                messagebox.showinfo("提示", f"已导出为CSV格式(Excel引擎不可用)\n文件路径:{filepath}", parent=db_window)
                                return
                    messagebox.showinfo("成功", f"已成功导出 {len(selected_data)} 条数据\n文件路径:{filepath}", parent=db_window)
                except Exception as e:
                    messagebox.showerror("错误", f"导出失败: {e}", parent=db_window)
                    import traceback
                    traceback.print_exc()
            def export_selected_lhb_to_txt():
                """导出选中的龙虎榜数据到TXT"""
                selections = lhb_tree.selection()
                if not selections:
                    messagebox.showwarning("提示", "请先选择要导出的数据", parent=db_window)
                    return
                try:
                    # 获取选中的数据
                    lines = []
                    # 添加表头
                    header_line = "\t".join([lhb_headings.get(col, col) for col in lhb_columns])
                    lines.append(header_line)
                    lines.append("=" * 100)
                    # 添加数据行
                    for item_id in selections:
                        item = lhb_tree.item(item_id)
                        values = item['values']
                        if values:
                            lines.append("\t".join(str(v) for v in values))
                    text_content = "\n".join(lines)
                    # 选择保存路径
                    from tkinter import filedialog
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    default_filename = f"龙虎榜选中数据_{timestamp}.txt"
                    filepath = filedialog.asksaveasfilename(
                        parent=db_window,
                        title="保存龙虎榜数据",
                        defaultextension=".txt",
                        filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                        initialfile=default_filename
                    )
                    if not filepath:
                        return
                    # 保存文件
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(text_content)
                    messagebox.showinfo("成功", f"已成功导出 {len(selections)} 条数据\n文件路径:{filepath}", parent=db_window)
                except Exception as e:
                    messagebox.showerror("错误", f"导出失败: {e}", parent=db_window)
                    import traceback
                    traceback.print_exc()
            # 按钮框架
            lhb_button_frame = ttk.Frame(lhb_tab)
            lhb_button_frame.pack(fill=tk.X)
            ttk.Button(lhb_button_frame, text="导出选中为Excel", command=export_selected_lhb_to_excel).pack(side=tk.LEFT, padx=5)
            ttk.Button(lhb_button_frame, text="导出选中为TXT", command=export_selected_lhb_to_txt).pack(side=tk.LEFT, padx=5)
            ttk.Button(lhb_button_frame, text="刷新", command=refresh_lhb_data).pack(side=tk.LEFT, padx=5)
            ttk.Button(lhb_button_frame, text="关闭", command=db_window.destroy).pack(side=tk.RIGHT, padx=5)
            # 初始加载龙虎榜数据
            refresh_lhb_data()
            # ==================== 股票实时数据标签页 ====================
            ths_realtime_tab = ttk.Frame(main_notebook)
            main_notebook.add(ths_realtime_tab, text="股票实时数据")
            # 查询条件框架
            ths_query_frame = ttk.LabelFrame(ths_realtime_tab, text="查询条件", padding=10)
            ths_query_frame.pack(fill=tk.X, pady=(0, 10))
            ths_date_frame = ttk.Frame(ths_query_frame)
            ths_date_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(ths_date_frame, text="保存日期:").pack(side=tk.LEFT, padx=5)
            ths_date_var = tk.StringVar()
            ths_date_entry = ttk.Entry(ths_date_frame, textvariable=ths_date_var, width=12)
            ths_date_entry.pack(side=tk.LEFT, padx=5)
            ttk.Label(ths_date_frame, text="股票代码/名称:").pack(side=tk.LEFT, padx=5)
            ths_stock_var = tk.StringVar()
            ths_stock_entry = ttk.Entry(ths_date_frame, textvariable=ths_stock_var, width=20)
            ths_stock_entry.pack(side=tk.LEFT, padx=5)
            # 自选股输入框
            ths_stock_list_frame = ttk.Frame(ths_query_frame)
            ths_stock_list_frame.pack(fill=tk.X, pady=(5, 0))
            ttk.Label(ths_stock_list_frame, text="自选股代码(用逗号或换行分隔):").pack(side=tk.LEFT, padx=5)
            ths_stock_list_var = tk.StringVar()
            ths_stock_list_entry = ttk.Entry(ths_stock_list_frame, textvariable=ths_stock_list_var, width=40)
            ths_stock_list_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            # 数据表格
            ths_table_frame = ttk.Frame(ths_realtime_tab)
            ths_table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            ths_table_label = ttk.Label(ths_table_frame, text="股票实时数据列表", font=("TkDefaultFont", 12, "bold"))
            ths_table_label.pack(anchor=tk.W, pady=(0, 5))
            ths_tree_frame = ttk.Frame(ths_table_frame)
            ths_tree_frame.pack(fill=tk.BOTH, expand=True)
            ths_columns = ("ID", "代码", "名称", "现价", "涨幅", "流通市值", "量比", "4分钟涨速",
                          "主力净量", "净额占比", "换手", "市盈", "振幅", "利好", "涨停次数", "保存日期", "保存时间")
            ths_tree = ttk.Treeview(ths_tree_frame, columns=ths_columns, show="headings", height=25)
            ths_headings = {
                "ID": "ID",
                "代码": "代码",
                "名称": "名称",
                "现价": "现价",
                "涨幅": "涨幅(%)",
                "流通市值": "流通市值",
                "量比": "量比",
                "4分钟涨速": "4分钟涨速(%)",
                "主力净量": "主力净量",
                "净额占比": "净额占比(%)",
                "换手": "换手(%)",
                "市盈": "市盈",
                "振幅": "振幅(%)",
                "利好": "利好",
                "涨停次数": "涨停次数",
                "保存日期": "保存日期",
                "保存时间": "保存时间"
            }
            ths_col_widths = {
                "ID": 50,
                "代码": 80,
                "名称": 80,
                "现价": 70,
                "涨幅": 70,
                "流通市值": 100,
                "量比": 60,
                "4分钟涨速": 90,
                "主力净量": 90,
                "净额占比": 90,
                "换手": 70,
                "市盈": 70,
                "振幅": 70,
                "利好": 150,
                "涨停次数": 80,
                "保存日期": 100,
                "保存时间": 80
            }
            for col in ths_columns:
                ths_tree.heading(col, text=ths_headings.get(col, col))
                ths_tree.column(col, width=ths_col_widths.get(col, 100), anchor=tk.CENTER)
            ths_scrollbar = ttk.Scrollbar(ths_tree_frame, orient=tk.VERTICAL, command=ths_tree.yview)
            ths_tree.configure(yscrollcommand=ths_scrollbar.set)
            ths_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            ths_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            def refresh_ths_data():
                """刷新股票实时数据"""
                try:
                    # 清空现有数据
                    for item in ths_tree.get_children():
                        ths_tree.delete(item)
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    # 首先检查表是否存在
                    cursor.execute('''
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name='ths_realtime_data'
                    ''')
                    table_exists = cursor.fetchone()
                    if not table_exists:
                        messagebox.showwarning("提示", "同花顺数据表不存在,请先保存一些数据", parent=db_window)
                        conn.close()
                        return
                    # 检查数据总数
                    cursor.execute('SELECT COUNT(*) FROM ths_realtime_data')
                    total_count = cursor.fetchone()[0]
                    print(f"数据库中同花顺数据总数: {total_count} 条")
                    # 构建查询
                    query = '''
                        SELECT id, stock_code, stock_name, current_price, change_pct,
                               circulation_market_value, volume_ratio, four_min_change_rate,
                               main_net_amount, net_amount_ratio, turnover_rate,
                               pe_ratio, amplitude, good_news, limit_up_count,
                               save_date, save_time
                        FROM ths_realtime_data
                        WHERE 1=1
                    '''
                    params = []
                    date_filter = ths_date_var.get().strip()
                    if date_filter:
                        query += " AND save_date LIKE ?"
                        params.append(f'%{date_filter}%')
                    stock_filter = ths_stock_var.get().strip()
                    if stock_filter:
                        query += " AND (stock_code LIKE ? OR stock_name LIKE ?)"
                        params.append(f'%{stock_filter}%')
                        params.append(f'%{stock_filter}%')
                    query += " ORDER BY save_date DESC, save_time DESC, stock_code"
                    print(f"执行查询: {query}")
                    print(f"查询参数: {params}")
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    print(f"查询结果: {len(results)} 条")
                    conn.close()
                    # 添加到表格
                    for row in results:
                        (id_val, stock_code, stock_name, current_price, change_pct,
                         circulation_market_value, volume_ratio, four_min_change_rate,
                         main_net_amount, net_amount_ratio, turnover_rate,
                         pe_ratio, amplitude, good_news, limit_up_count,
                         save_date, save_time) = row
                        # 格式化数值
                        def fmt_value(val, decimals=2, suffix=""):
                            if val is None:
                                return "--"
                            try:
                                return f"{float(val):,.{decimals}f}{suffix}"
                            except:
                                return str(val) if val else "--"
                        values = (
                            id_val,
                            stock_code or "--",
                            stock_name or "--",
                            fmt_value(current_price),
                            fmt_value(change_pct, 2, "%"),
                            fmt_value(circulation_market_value),
                            fmt_value(volume_ratio),
                            fmt_value(four_min_change_rate, 2, "%"),
                            fmt_value(main_net_amount),
                            fmt_value(net_amount_ratio, 2, "%"),
                            fmt_value(turnover_rate, 2, "%"),
                            fmt_value(pe_ratio),
                            fmt_value(amplitude, 2, "%"),
                            good_news or "--",
                            limit_up_count if limit_up_count is not None else "--",
                            save_date or "--",
                            save_time or "--"
                        )
                        ths_tree.insert("", tk.END, values=values)
                except Exception as e:
                    messagebox.showerror("错误", f"查询股票实时数据失败: {e}", parent=db_window)
            ttk.Button(ths_query_frame, text="查询", command=refresh_ths_data).pack(side=tk.LEFT, padx=(10, 0))
            def get_ths_watchlist_data():
                """获取同花顺自选股实时数据"""
                try:
                    # 获取自选股代码列表
                    stock_list_text = ths_stock_list_var.get().strip()
                    if not stock_list_text:
                        messagebox.showwarning("提示", "请输入自选股代码(用逗号或换行分隔)", parent=db_window)
                        return
                    # 解析股票代码列表
                    stock_codes = []
                    for line in stock_list_text.replace('\n', ',').split(','):
                        code = line.strip()
                        if code:
                            # 确保是6位数字代码
                            if code.isdigit() and len(code) == 6:
                                stock_codes.append(code)
                            elif len(code) == 8 and code[6:] in ['SH', 'SZ']:
                                # 处理带市场后缀的代码,如000001SH
                                stock_codes.append(code[:6])
                    if not stock_codes:
                        messagebox.showwarning("提示", "未找到有效的股票代码(需要6位数字)", parent=db_window)
                        return
                    # 在新线程中获取数据
                    def fetch_data_thread():
                        try:
                            db_window.after(0, lambda: messagebox.showinfo("提示", f"开始获取 {len(stock_codes)} 只股票的实时数据...", parent=db_window))
                            saved_count = 0
                            failed_count = 0
                            # 检查akshare是否可用
                            try:
                                import akshare as ak
                            except ImportError:
                                db_window.after(0, lambda: messagebox.showerror("错误", "需要安装akshare库: pip install akshare", parent=db_window))
                                return
                            # 获取当前日期和时间
                            save_date = datetime.now().strftime('%Y-%m-%d')
                            save_time = datetime.now().strftime('%H:%M:%S')
                            # 获取所有A股实时数据(一次性获取,提高效率)
                            try:
                                all_stocks_df = ak.stock_zh_a_spot_em()
                                # 创建代码到数据的映射
                                stock_data_map = {}
                                for _, row in all_stocks_df.iterrows():
                                    code = str(row.get('代码', '')).strip()
                                    if code:
                                        stock_data_map[code] = row
                            except Exception as e:
                                db_window.after(0, lambda e=str(e): messagebox.showerror("错误", f"获取市场数据失败: {e}", parent=db_window))
                                return
                            # 逐个处理自选股
                            conn = sqlite3.connect(DB_PATH)
                            cursor = conn.cursor()
                            for stock_code in stock_codes:
                                try:
                                    # 从映射中获取数据
                                    if stock_code in stock_data_map:
                                        row = stock_data_map[stock_code]
                                        stock_name = str(row.get('名称', '')).strip()
                                        current_price = row.get('最新价', None)
                                        change_pct = row.get('涨跌幅', None)
                                        circulation_market_value = row.get('流通市值', None)
                                        volume_ratio = row.get('量比', None)
                                        turnover_rate = row.get('换手率', None)
                                        pe_ratio = row.get('市盈率-动态', None)
                                        amplitude = row.get('振幅', None)
                                        # 尝试获取更多数据(4分钟涨速、主力净量等)
                                        four_min_change_rate = None
                                        main_net_amount = None
                                        net_amount_ratio = None
                                        good_news = ""
                                        limit_up_count = None
                                        # 保存到数据库
                                        cursor.execute('''
                                            INSERT INTO ths_realtime_data (
                                                stock_code, stock_name, current_price, change_pct,
                                                circulation_market_value, volume_ratio, four_min_change_rate,
                                                main_net_amount, net_amount_ratio, turnover_rate,
                                                pe_ratio, amplitude, good_news, limit_up_count,
                                                save_date, save_time
                                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                        ''', (
                                            stock_code,
                                            stock_name,
                                            float(current_price) if current_price is not None else None,
                                            float(change_pct) if change_pct is not None else None,
                                            float(circulation_market_value) if circulation_market_value is not None else None,
                                            float(volume_ratio) if volume_ratio is not None else None,
                                            four_min_change_rate,
                                            main_net_amount,
                                            net_amount_ratio,
                                            float(turnover_rate) if turnover_rate is not None else None,
                                            float(pe_ratio) if pe_ratio is not None else None,
                                            float(amplitude) if amplitude is not None else None,
                                            good_news,
                                            limit_up_count,
                                            save_date,
                                            save_time
                                        ))
                                        saved_count += 1
                                    else:
                                        # 如果不在实时数据中,尝试通过其他方式获取基本信息
                                        try:
                                            # 获取股票基本信息
                                            stock_info = ak.stock_individual_info_em(symbol=stock_code)
                                            stock_name = stock_code
                                            if not stock_info.empty:
                                                name_row = stock_info[stock_info['item'] == '股票简称']
                                                if not name_row.empty:
                                                    stock_name = name_row.iloc[0]['value']
                                            # 保存基本信息
                                            cursor.execute('''
                                                INSERT INTO ths_realtime_data (
                                                    stock_code, stock_name, current_price, change_pct,
                                                    circulation_market_value, volume_ratio, four_min_change_rate,
                                                    main_net_amount, net_amount_ratio, turnover_rate,
                                                    pe_ratio, amplitude, good_news, limit_up_count,
                                                    save_date, save_time
                                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                            ''', (
                                                stock_code,
                                                stock_name,
                                                None, None, None, None, None, None, None, None, None, None, "", None,
                                                save_date,
                                                save_time
                                            ))
                                            saved_count += 1
                                        except:
                                            failed_count += 1
                                            continue
                                except Exception as e:
                                    failed_count += 1
                                    print(f"处理股票 {stock_code} 失败: {e}")
                                    continue
                            conn.commit()
                            conn.close()
                            # 刷新显示
                            db_window.after(0, refresh_ths_data)
                            # 显示结果
                            result_msg = f"获取完成!\n成功: {saved_count} 只\n失败: {failed_count} 只"
                            db_window.after(0, lambda: messagebox.showinfo("完成", result_msg, parent=db_window))
                        except Exception as e:
                            db_window.after(0, lambda e=str(e): messagebox.showerror("错误", f"获取数据失败: {e}", parent=db_window))
                            import traceback
                            traceback.print_exc()
                    threading.Thread(target=fetch_data_thread, daemon=True).start()
                except Exception as e:
                    messagebox.showerror("错误", f"获取自选股数据失败: {e}", parent=db_window)
            ttk.Button(ths_query_frame, text="获取同花顺自选股数据", command=get_ths_watchlist_data, width=20).pack(side=tk.LEFT, padx=(10, 0))
            # 按钮框架
            ths_button_frame = ttk.Frame(ths_realtime_tab)
            ths_button_frame.pack(fill=tk.X)
            ttk.Button(ths_button_frame, text="刷新", command=refresh_ths_data).pack(side=tk.LEFT, padx=5)
            ttk.Button(ths_button_frame, text="关闭", command=db_window.destroy).pack(side=tk.RIGHT, padx=5)
            # 初始加载股票实时数据
            refresh_ths_data()
            # 根据参数切换到默认标签页
            if default_tab == "news":
                main_notebook.select(news_tab)
            elif default_tab == "lhb":
                main_notebook.select(lhb_tab)
            elif default_tab == "ths":
                main_notebook.select(ths_realtime_tab)
            else:
                main_notebook.select(stock_tab)
            # 窗口控制按钮
            control_btn_frame = ttk.Frame(db_window)
            control_btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            def toggle_minimize():
                """切换最小化/恢复"""
                if db_window._is_minimized:
                    db_window.geometry(db_window._original_geometry)
                    db_window._is_minimized = False
                    minimize_btn.config(text="最小化")
                else:
                    db_window._original_geometry = db_window.geometry()
                    db_window.geometry("200x50")
                    db_window._is_minimized = True
                    minimize_btn.config(text="恢复")
            def toggle_maximize():
                """切换最大化/恢复"""
                try:
                    # Windows平台使用state('zoomed')
                    if db_window.state() == 'zoomed':
                        db_window.state('normal')
                        db_window.geometry(db_window._original_geometry)
                        maximize_btn.config(text="最大化")
                    else:
                        db_window._original_geometry = db_window.geometry()
                        db_window.state('zoomed')
                        maximize_btn.config(text="恢复")
                except:
                    # 如果state不支持,尝试使用geometry
                    try:
                        current_geom = db_window.geometry()
                        if hasattr(db_window, '_is_maximized') and db_window._is_maximized:
                            db_window.geometry(db_window._original_geometry)
                            db_window._is_maximized = False
                            maximize_btn.config(text="最大化")
                        else:
                            db_window._original_geometry = current_geom
                            # 获取屏幕尺寸
                            screen_width = db_window.winfo_screenwidth()
                            screen_height = db_window.winfo_screenheight()
                            db_window.geometry(f"{screen_width}x{screen_height}+0+0")
                            db_window._is_maximized = True
                            maximize_btn.config(text="恢复")
                    except Exception as e:
                        messagebox.showinfo("提示", f"最大化功能不可用: {e}")
            minimize_btn = ttk.Button(control_btn_frame, text="最小化", command=toggle_minimize, width=10)
            minimize_btn.pack(side=tk.LEFT, padx=5)
            maximize_btn = ttk.Button(control_btn_frame, text="最大化", command=toggle_maximize, width=10)
            maximize_btn.pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="隐藏", command=db_window.withdraw, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="显示", command=db_window.deiconify, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="关闭", command=db_window.destroy, width=10).pack(side=tk.RIGHT, padx=5)
        except Exception as e:
            messagebox.showerror("错误", f"显示数据库失败: {e}")


    def show_db_display(self):
        """显示数据库数据和逻辑,提供增删改功能"""
        # 调用统一的数据管理窗口
        self.show_unified_db_display()
        return
        # 以下是原来的代码,保留作为备份
        try:
            db_window = self._toplevel(self.root)
            db_window.title("股票逻辑数据库管理")
            db_window.geometry("1200x800")
            # 创建主框架
            main_frame = ttk.Frame(db_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            # 查询条件框架
            query_frame = ttk.LabelFrame(main_frame, text="查询条件", padding=10)
            query_frame.pack(fill=tk.X, pady=(0, 10))
            # 第一行:日期范围选择
            date_frame = ttk.Frame(query_frame)
            date_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(date_frame, text="起始日期:").pack(side=tk.LEFT, padx=5)
            start_date_var = tk.StringVar()
            start_date_entry = ttk.Entry(date_frame, textvariable=start_date_var, width=12)
            start_date_entry.pack(side=tk.LEFT, padx=5)
            start_date_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
            ttk.Label(date_frame, text="结束日期:").pack(side=tk.LEFT, padx=5)
            end_date_var = tk.StringVar()
            end_date_entry = ttk.Entry(date_frame, textvariable=end_date_var, width=12)
            end_date_entry.pack(side=tk.LEFT, padx=5)
            end_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
            ttk.Label(date_frame, text="股票名称:").pack(side=tk.LEFT, padx=5)
            stock_name_var = tk.StringVar()
            stock_name_entry = ttk.Entry(date_frame, textvariable=stock_name_var, width=20)
            stock_name_entry.pack(side=tk.LEFT, padx=5)
            # 查询按钮
            ttk.Button(date_frame, text="查询", command=lambda: refresh_data()).pack(side=tk.LEFT, padx=(10, 0))
            # 大单净值分析按钮
            ttk.Button(date_frame, text="大单净值分析", command=lambda: analyze_big_order_net_value()).pack(side=tk.LEFT, padx=(5, 0))
            # 5日差值分析按钮
            ttk.Button(date_frame, text="5日差值分析", command=lambda: analyze_5day_diff()).pack(side=tk.LEFT, padx=(5, 0))
            # 数据表格和逻辑详情(左右布局)
            content_frame = ttk.Frame(main_frame)
            content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            # 左侧:数据表格
            left_content = ttk.Frame(content_frame)
            left_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
            table_label = ttk.Label(left_content, text="股票数据列表", font=("TkDefaultFont", 12, "bold"))
            table_label.pack(anchor=tk.W, pady=(0, 5))
            table_frame = ttk.Frame(left_content)
            table_frame.pack(fill=tk.BOTH, expand=True)
            columns = ("ID", "股票名称", "逻辑预览", "日期", "来源", "创建时间")
            tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=25)
            # 设置列宽
            tree.column("ID", width=50, anchor=tk.CENTER)
            tree.column("股票名称", width=120, anchor=tk.CENTER)
            tree.column("逻辑预览", width=250)
            tree.column("日期", width=100, anchor=tk.CENTER)
            tree.column("来源", width=100, anchor=tk.CENTER)
            tree.column("创建时间", width=150, anchor=tk.CENTER)
            for col in columns:
                tree.heading(col, text=col)
            scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            # 右侧:逻辑详情
            right_content = ttk.Frame(content_frame)
            right_content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
            logic_label = ttk.Label(right_content, text="逻辑详情", font=("TkDefaultFont", 12, "bold"))
            logic_label.pack(anchor=tk.W, pady=(0, 5))
            logic_frame = ttk.LabelFrame(right_content, text="完整逻辑内容", padding=5)
            logic_frame.pack(fill=tk.BOTH, expand=True)
            logic_text = scrolledtext.ScrolledText(logic_frame, height=12, wrap=tk.WORD,
                                                   font=("TkDefaultFont", 12))
            logic_text.pack(fill=tk.BOTH, expand=True)
            # 字体大小控制按钮(放在logic_text定义之后)
            font_control_frame = ttk.Frame(right_content)
            font_control_frame.pack(fill=tk.X, pady=(5, 0))
            ttk.Label(font_control_frame, text="字体大小:").pack(side=tk.LEFT, padx=5)
            current_font_size = tk.IntVar(value=10)
            def increase_font():
                """增大字体"""
                size = current_font_size.get()
                if size < 24:
                    current_font_size.set(size + 1)
                    logic_text.config(font=("TkDefaultFont", size + 1))
            def decrease_font():
                """减小字体"""
                size = current_font_size.get()
                if size > 8:
                    current_font_size.set(size - 1)
                    logic_text.config(font=("TkDefaultFont", size - 1))
            ttk.Button(font_control_frame, text="放大", command=increase_font, width=8).pack(side=tk.LEFT, padx=2)
            ttk.Button(font_control_frame, text="缩小", command=decrease_font, width=8).pack(side=tk.LEFT, padx=2)
            # 右侧下半区:Notebook 包含 AI分析 与 走势 两个标签
            bottom_nb = ttk.Notebook(right_content)
            bottom_nb.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
            # AI分析标签
            ai_tab = ttk.Frame(bottom_nb)
            bottom_nb.add(ai_tab, text="AI分析")
            ai_frame = ttk.LabelFrame(ai_tab, text="AI分析", padding=5)
            ai_frame.pack(fill=tk.BOTH, expand=True)
            # AI分析按钮
            ai_button_frame = ttk.Frame(ai_frame)
            ai_button_frame.pack(fill=tk.X, pady=(0, 5))
            ai_analyze_button = ttk.Button(ai_button_frame, text="AI分析选中数据",
                                           command=lambda: analyze_selected_data())
            ai_analyze_button.pack(side=tk.LEFT, padx=5)
            # AI分析结果显示
            ai_result_text = scrolledtext.ScrolledText(ai_frame, height=10, wrap=tk.WORD,
                                                       font=("TkDefaultFont", 12))
            ai_result_text.pack(fill=tk.BOTH, expand=True)
            # 走势标签
            chart_tab = ttk.Frame(bottom_nb)
            bottom_nb.add(chart_tab, text="走势")
            chart_ctrl = ttk.Frame(chart_tab)
            chart_ctrl.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(chart_ctrl, text="周期:").pack(side=tk.LEFT, padx=5)
            chart_period_var = tk.StringVar(value="日线")
            for label in ["月线", "周线", "日线", "60分钟", "分时"]:
                ttk.Radiobutton(chart_ctrl, text=label, value=label, variable=chart_period_var).pack(side=tk.LEFT, padx=4)
            ttk.Button(chart_ctrl, text="刷新走势", width=10).pack_forget()  # 预留
            # Matplotlib 图区域
            chart_container = ttk.Frame(chart_tab)
            chart_container.pack(fill=tk.BOTH, expand=True)
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            # 字体已在文件开头全局设置,这里不需要重复设置
            fig = Figure(figsize=(5, 3), dpi=100)
            ax_price = fig.add_subplot(211)
            ax_vol = fig.add_subplot(212, sharex=ax_price)
            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=chart_container)
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(fill=tk.BOTH, expand=True)
            current_stock_name = tk.StringVar(value="")
            def get_selected_stock_name():
                sel = tree.selection()
                if not sel:
                    return ""
                it = tree.item(sel[0])
                if len(it['values']) > 1:
                    stock_name = str(it['values'][1])
                    # 确保编码正确
                    try:
                        if isinstance(stock_name, bytes):
                            stock_name = stock_name.decode('utf-8')
                    except:
                        pass
                    return stock_name
                return ""
            def fetch_kline_df(stock_name, period_label):
                """使用 akshare 拉取K线数据"""
                try:
                    code = get_stock_code_by_name(stock_name)
                    if not code:
                        return None
                    if period_label == "日线":
                        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="")
                    elif period_label == "周线":
                        df = ak.stock_zh_a_hist(symbol=code, period="weekly", adjust="")
                    elif period_label == "月线":
                        df = ak.stock_zh_a_hist(symbol=code, period="monthly", adjust="")
                    elif period_label == "60分钟":
                        df = ak.stock_zh_a_hist_min_em(symbol=code, period="60", adjust="")
                    else:
                        # 分时使用 1 分钟
                        df = ak.stock_zh_a_hist_min_em(symbol=code, period="1", adjust="")
                    if df is None or df.empty:
                        return None
                    return df
                except Exception as e:
                    print(f"获取K线失败: {e}")
                    return None
            def plot_chart_for(stock_name, period_label):
                ax_price.clear()
                ax_vol.clear()
                # 获取中文字体
                try:
                    from matplotlib import font_manager
                    font_list = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
                    font_name = None
                    for f in font_list:
                        try:
                            font_manager.findfont(font_manager.FontProperties(family=f))
                            font_name = f
                            break
                        except:
                            continue
                except:
                    font_name = None
                if not stock_name:
                    if font_name:
                        ax_price.set_title("未选择股票", fontfamily=font_name)
                    else:
                        ax_price.set_title("未选择股票")
                    canvas.draw()
                    return
                # 确保股票名称编码正确
                try:
                    if isinstance(stock_name, bytes):
                        stock_name = stock_name.decode('utf-8')
                except:
                    pass
                df = fetch_kline_df(stock_name, period_label)
                if df is None or df.empty:
                    if font_name:
                        ax_price.set_title(f"{stock_name} - {period_label} 数据获取失败", fontfamily=font_name)
                    else:
                        ax_price.set_title(f"{stock_name} - {period_label} 数据获取失败")
                    canvas.draw()
                    return
                # 兼容字段名
                date_col = None
                for c in ["日期", "time", "date", "datetime"]:
                    if c in df.columns:
                        date_col = c
                        break
                close_col = "收盘" if "收盘" in df.columns else "close"
                vol_col = "成交量" if "成交量" in df.columns else ("volume" if "volume" in df.columns else None)
                try:
                    x = pd.to_datetime(df[date_col])
                except Exception:
                    x = list(range(len(df)))
                y_close = pd.to_numeric(df[close_col], errors="coerce")
                ax_price.plot(x, y_close, color="blue", linewidth=1.2)
                # 设置标题,使用中文字体
                if font_name:
                    ax_price.set_title(f"{stock_name} - {period_label}", fontfamily=font_name)
                else:
                    ax_price.set_title(f"{stock_name} - {period_label}")
                ax_price.grid(True, linestyle="--", alpha=0.3)
                if vol_col and vol_col in df.columns:
                    y_vol = pd.to_numeric(df[vol_col], errors="coerce")
                    ax_vol.bar(x, y_vol, color="#9999ff")
                    ax_vol.set_ylabel("成交量")
                    ax_vol.grid(True, linestyle="--", alpha=0.3)
                else:
                    ax_vol.text(0.5, 0.5, "无成交量数据", transform=ax_vol.transAxes, ha="center", va="center")
                    ax_vol.grid(True, linestyle="--", alpha=0.3)
                fig.autofmt_xdate()
                canvas.draw()
            def on_select(event=None):
                name = get_selected_stock_name()
                current_stock_name.set(name)
                plot_chart_for(name, chart_period_var.get())
            def on_period_change(*args):
                name = current_stock_name.get() or get_selected_stock_name()
                if name:
                    plot_chart_for(name, chart_period_var.get())
            # 绑定事件:选择行、切换周期
            tree.bind("<<TreeviewSelect>>", on_select)
            chart_period_var.trace_add("write", lambda *args: on_period_change())
            def analyze_selected_data():
                """对选中的数据进行AI分析"""
                selection = tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择要分析的数据")
                    return
                item = tree.item(selection[0])
                logic_id = item['values'][0]
                # 获取完整数据
                data = get_stock_logic_from_db()
                record = None
                for d in data:
                    if str(d.get('id')) == str(logic_id):
                        record = d
                        break
                if not record:
                    messagebox.showerror("错误", "未找到记录")
                    return
                # 构建分析内容(包含所有字段)
                analysis_content = f"""股票名称: {record.get('stock_name', '')}
日期: {record.get('date', '')}
来源: {record.get('source', '')}
创建时间: {record.get('created_at', '')}
逻辑内容:
{record.get('logic', '')}
"""
                # 清空AI分析结果
                ai_result_text.delete("1.0", tk.END)
                ai_result_text.insert("1.0", "正在分析,请稍候...")
                ai_result_text.update()
                # 在后台线程中执行AI分析
                def run_ai_analysis():
                    try:
                        # 先搜索相关文章
                        stock_name = record.get('stock_name', '')
                        search_keywords = f"{stock_name} 股票分析 投资逻辑"
                        reference_articles = []
                        def search_articles(keywords):
                            """搜索相关文章"""
                            try:
                                # 使用DuckDuckGo搜索(无需API密钥)
                                from urllib.parse import quote_plus
                                encoded_keywords = quote_plus(keywords)
                                search_url = f"https://html.duckduckgo.com/html/?q={encoded_keywords}"
                                headers = {
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                                }
                                response = requests.get(search_url, headers=headers, timeout=10)
                                if response.status_code == 200:
                                    soup = BeautifulSoup(response.text, 'html.parser')
                                    results = []
                                    # 查找搜索结果
                                    for result in soup.find_all('div', class_='result')[:5]:
                                        try:
                                            title_elem = result.find('a', class_='result__a')
                                            snippet_elem = result.find('a', class_='result__snippet')
                                            if title_elem:
                                                title = title_elem.get_text(strip=True)
                                                url = title_elem.get('href', '')
                                                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                                                if title and url:
                                                    results.append({
                                                        'title': title,
                                                        'url': url,
                                                        'snippet': snippet
                                                    })
                                        except:
                                            continue
                                    return results
                            except Exception as e:
                                print(f"搜索失败: {e}")
                                return []
                            return []
                        try:
                            # 搜索相关文章
                            search_results = search_articles(search_keywords)
                            reference_articles = search_results
                        except Exception as e:
                            print(f"搜索相关文章失败: {e}")
                        # 构建参考文章信息(保存原始数据用于链接)
                        reference_text = ""
                        reference_links = []  # 保存链接信息用于双击打开
                        if reference_articles:
                            reference_text = "\n\n【相关参考文章】\n"
                            for i, article in enumerate(reference_articles, 1):
                                title = article['title']
                                url = article['url']
                                snippet = article.get('snippet', '')
                                reference_text += f"{i}. {title}\n"
                                reference_text += f"   链接: {url}\n"
                                if snippet:
                                    reference_text += f"   摘要: {snippet[:100]}...\n"
                                reference_text += "\n"
                                # 保存链接位置信息
                                reference_links.append({
                                    'url': url,
                                    'title': title
                                })
                        # 构建AI提示词
                        prompt = f"""请对以下股票逻辑信息进行详细分析,包括:
1. 逻辑要点总结
2. 投资价值评估
3. 风险提示
4. 建议关注点
信息内容:
{analysis_content}
请提供专业的分析报告。"""
                        # 调用AI模型
                        ai_result = self.call_ai_model(prompt, system_prompt="你是一位专业的股票分析师,擅长分析股票投资逻辑。")
                        # 合并AI分析结果和参考文章
                        final_result = ai_result + reference_text
                        # 在主线程中更新UI(传递链接信息)
                        db_window.after(0, lambda: update_ai_result(final_result, reference_links))
                    except Exception as e:
                        error_msg = f"AI分析失败: {e!s}"
                        db_window.after(0, lambda: update_ai_result(error_msg, []))
                def update_ai_result(result, reference_links=None):
                    """更新AI分析结果,支持链接双击打开"""
                    if reference_links is None:
                        reference_links = []
                    ai_result_text.delete("1.0", tk.END)
                    ai_result_text.insert("1.0", result)
                    # 配置链接标签样式
                    ai_result_text.tag_config("link", foreground="blue", underline=True)
                    ai_result_text.tag_bind("link", "<Button-1>", lambda e: None)  # 防止默认行为
                    # 识别并标记所有URL链接
                    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
                    text_content = result
                    for match in re.finditer(url_pattern, text_content):
                        start_pos = f"1.0 + {match.start()} chars"
                        end_pos = f"1.0 + {match.end()} chars"
                        url = match.group()
                        # 标记链接
                        ai_result_text.tag_add("link", start_pos, end_pos)
                        # 绑定双击事件打开链接
                        ai_result_text.tag_bind("link", "<Double-Button-1>",
                                              lambda e, u=url: webbrowser.open(u))
                    # 为参考文章中的链接添加特殊标记
                    for link_info in reference_links:
                        url = link_info['url']
                        # 查找链接在文本中的位置
                        start_idx = text_content.find(url)
                        if start_idx != -1:
                            start_pos = f"1.0 + {start_idx} chars"
                            end_pos = f"1.0 + {start_idx + len(url)} chars"
                            ai_result_text.tag_add("link", start_pos, end_pos)
                            ai_result_text.tag_bind("link", "<Double-Button-1>",
                                                  lambda e, u=url: webbrowser.open(u))
                    ai_result_text.see(tk.END)
                # 启动分析线程
                analysis_thread = threading.Thread(target=run_ai_analysis, daemon=True)
                analysis_thread.start()
            # 按钮框架
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)
            # 状态标签
            status_label = ttk.Label(button_frame, text="", font=("TkDefaultFont", 11))
            status_label.pack(side=tk.LEFT, padx=10)
            def refresh_data():
                """刷新数据"""
                try:
                    # 清空表格
                    for item in tree.get_children():
                        tree.delete(item)
                    # 获取查询条件
                    start_date = start_date_var.get().strip() if start_date_var.get().strip() else None
                    end_date = end_date_var.get().strip() if end_date_var.get().strip() else None
                    stock_name = stock_name_var.get().strip() if stock_name_var.get().strip() else None
                    # 查询数据
                    data = get_stock_logic_from_db(
                        start_date=start_date,
                        end_date=end_date,
                        stock_name=stock_name
                    )
                    # 填充表格
                    for item in data:
                        logic_preview = item.get('logic', '')
                        if len(logic_preview) > 50:
                            logic_preview = logic_preview[:50] + '...'
                        tree.insert("", tk.END, values=(
                            item.get('id', ''),
                            item.get('stock_name', ''),
                            logic_preview,
                            item.get('date', ''),
                            item.get('source', ''),
                            item.get('created_at', '')
                        ))
                    # 更新状态标签(不弹窗)
                    status_label.config(text=f"共查询到 {len(data)} 条记录")
                except Exception as e:
                    messagebox.showerror("错误", f"查询失败: {e}")
            def on_select(event):
                """选择事件"""
                selection = tree.selection()
                if selection:
                    item = tree.item(selection[0])
                    values = item['values']
                    if len(values) >= 1:
                        # 获取完整逻辑(需要重新查询)
                        logic_id = values[0]
                        data = get_stock_logic_from_db()
                        for d in data:
                            if str(d.get('id')) == str(logic_id):
                                logic_text.delete("1.0", tk.END)
                                logic_text.insert("1.0", d.get('logic', ''))
                                break
            def add_record():
                """添加记录"""
                add_window = self._toplevel(db_window)
                add_window.title("添加股票逻辑")
                add_window.geometry("500x400")
                ttk.Label(add_window, text="股票名称:").pack(anchor=tk.W, padx=10, pady=5)
                name_entry = ttk.Entry(add_window, width=50)
                name_entry.pack(fill=tk.X, padx=10, pady=5)
                ttk.Label(add_window, text="逻辑:").pack(anchor=tk.W, padx=10, pady=5)
                logic_entry = scrolledtext.ScrolledText(add_window, height=10, width=50)
                logic_entry.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                ttk.Label(add_window, text="日期:").pack(anchor=tk.W, padx=10, pady=5)
                date_entry = ttk.Entry(add_window, width=50)
                date_entry.pack(fill=tk.X, padx=10, pady=5)
                date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
                ttk.Label(add_window, text="来源:").pack(anchor=tk.W, padx=10, pady=5)
                source_entry = ttk.Entry(add_window, width=50)
                source_entry.pack(fill=tk.X, padx=10, pady=5)
                def save_add():
                    try:
                        if save_stock_logic_to_db(
                            stock_name=name_entry.get().strip(),
                            logic=logic_entry.get("1.0", tk.END).strip(),
                            date=date_entry.get().strip(),
                            source=source_entry.get().strip()
                        ):
                            messagebox.showinfo("成功", "添加成功")
                            add_window.destroy()
                            refresh_data()
                        else:
                            messagebox.showerror("错误", "添加失败")
                    except Exception as e:
                        messagebox.showerror("错误", f"添加失败: {e}")
                ttk.Button(add_window, text="保存", command=save_add).pack(pady=10)
                ttk.Button(add_window, text="取消", command=add_window.destroy).pack()
            def edit_record():
                """编辑记录"""
                selection = tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择要编辑的记录")
                    return
                item = tree.item(selection[0])
                logic_id = item['values'][0]
                # 获取完整数据
                data = get_stock_logic_from_db()
                record = None
                for d in data:
                    if d.get('id') == logic_id:
                        record = d
                        break
                if not record:
                    messagebox.showerror("错误", "未找到记录")
                    return
                edit_window = self._toplevel(db_window)
                edit_window.title("编辑股票逻辑")
                edit_window.geometry("500x400")
                ttk.Label(edit_window, text="股票名称:").pack(anchor=tk.W, padx=10, pady=5)
                name_entry = ttk.Entry(edit_window, width=50)
                name_entry.pack(fill=tk.X, padx=10, pady=5)
                name_entry.insert(0, record.get('stock_name', ''))
                ttk.Label(edit_window, text="逻辑:").pack(anchor=tk.W, padx=10, pady=5)
                logic_entry = scrolledtext.ScrolledText(edit_window, height=10, width=50)
                logic_entry.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                logic_entry.insert("1.0", record.get('logic', ''))
                ttk.Label(edit_window, text="日期:").pack(anchor=tk.W, padx=10, pady=5)
                date_entry = ttk.Entry(edit_window, width=50)
                date_entry.pack(fill=tk.X, padx=10, pady=5)
                date_entry.insert(0, record.get('date', ''))
                ttk.Label(edit_window, text="来源:").pack(anchor=tk.W, padx=10, pady=5)
                source_entry = ttk.Entry(edit_window, width=50)
                source_entry.pack(fill=tk.X, padx=10, pady=5)
                source_entry.insert(0, record.get('source', ''))
                def save_edit():
                    try:
                        if update_stock_logic_in_db(
                            logic_id=logic_id,
                            stock_name=name_entry.get().strip(),
                            logic=logic_entry.get("1.0", tk.END).strip(),
                            date=date_entry.get().strip(),
                            source=source_entry.get().strip()
                        ):
                            messagebox.showinfo("成功", "更新成功")
                            edit_window.destroy()
                            refresh_data()
                        else:
                            messagebox.showerror("错误", "更新失败")
                    except Exception as e:
                        messagebox.showerror("错误", f"更新失败: {e}")
                ttk.Button(edit_window, text="保存", command=save_edit).pack(pady=10)
                ttk.Button(edit_window, text="取消", command=edit_window.destroy).pack()
            def delete_record():
                """删除记录"""
                selection = tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择要删除的记录")
                    return
                if messagebox.askyesno("确认", "确定要删除这条记录吗?"):
                    item = tree.item(selection[0])
                    logic_id = item['values'][0]
                    try:
                        if delete_stock_logic_from_db(logic_id):
                            messagebox.showinfo("成功", "删除成功")
                            refresh_data()
                        else:
                            messagebox.showerror("错误", "删除失败")
                    except Exception as e:
                        messagebox.showerror("错误", f"删除失败: {e}")
            # 绑定选择事件
            tree.bind("<<TreeviewSelect>>", on_select)
            # 按钮
            ttk.Button(button_frame, text="刷新", command=refresh_data).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="添加", command=add_record).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="编辑", command=edit_record).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="删除", command=delete_record).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="关闭", command=db_window.destroy).pack(side=tk.RIGHT, padx=5)
            # 初始加载数据
            refresh_data()
        except Exception as e:
            messagebox.showerror("错误", f"显示数据库失败: {e}")


    def show_news_db_display(self):
        """显示资讯数据库数据和逻辑,提供增删改功能"""
        # 调用统一的数据管理窗口,并切换到资讯数据表标签页
        self.show_unified_db_display(default_tab="news")
        return
        # 以下是原来的代码,保留作为备份
        try:
            db_window = self._toplevel(self.root)
            db_window.title("资讯数据库管理")
            db_window.geometry("1200x800")
            # 创建主框架
            main_frame = ttk.Frame(db_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            # 查询条件框架
            query_frame = ttk.LabelFrame(main_frame, text="查询条件", padding=10)
            query_frame.pack(fill=tk.X, pady=(0, 10))
            # 第一行:标签页名称搜索
            name_frame = ttk.Frame(query_frame)
            name_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(name_frame, text="标签页名称:").pack(side=tk.LEFT, padx=5)
            tab_name_var = tk.StringVar()
            tab_name_entry = ttk.Entry(name_frame, textvariable=tab_name_var, width=30)
            tab_name_entry.pack(side=tk.LEFT, padx=5)
            # 查询按钮
            ttk.Button(name_frame, text="查询", command=lambda: refresh_data()).pack(side=tk.LEFT, padx=(10, 0))
            # 数据表格和内容详情(左右布局)
            content_frame = ttk.Frame(main_frame)
            content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            # 左侧:数据表格
            left_content = ttk.Frame(content_frame)
            left_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
            table_label = ttk.Label(left_content, text="资讯数据列表", font=("TkDefaultFont", 12, "bold"))
            table_label.pack(anchor=tk.W, pady=(0, 5))
            table_frame = ttk.Frame(left_content)
            table_frame.pack(fill=tk.BOTH, expand=True)
            columns = ("ID", "标签页名称", "内容预览", "创建时间", "更新时间")
            tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=25)
            # 设置列宽
            tree.column("ID", width=50, anchor=tk.CENTER)
            tree.column("标签页名称", width=200, anchor=tk.CENTER)
            tree.column("内容预览", width=300)
            tree.column("创建时间", width=150, anchor=tk.CENTER)
            tree.column("更新时间", width=150, anchor=tk.CENTER)
            for col in columns:
                tree.heading(col, text=col)
            scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            # 右侧:内容详情和评注
            right_content = ttk.Frame(content_frame)
            right_content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
            # 使用Notebook分为内容和评注两个标签
            right_notebook = ttk.Notebook(right_content)
            right_notebook.pack(fill=tk.BOTH, expand=True)
            # 内容标签页
            content_tab = ttk.Frame(right_notebook)
            right_notebook.add(content_tab, text="内容")
            content_label = ttk.Label(content_tab, text="完整内容", font=("TkDefaultFont", 12, "bold"))
            content_label.pack(anchor=tk.W, pady=(0, 5))
            # 内容编辑按钮
            content_btn_frame = ttk.Frame(content_tab)
            content_btn_frame.pack(fill=tk.X, pady=(0, 5))
            content_edit_mode = tk.BooleanVar(value=False)
            current_editing_news_id = [None]  # 使用列表以便在lambda中修改
            auto_save_timer = [None]  # 自动保存定时器
            def auto_save_content():
                """自动保存内容"""
                if not content_edit_mode.get() or not current_editing_news_id[0]:
                    return
                news_id = current_editing_news_id[0]
                if news_id:
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        new_content = content_text.get("1.0", tk.END).strip()
                        cursor.execute('''
                            UPDATE news_info
                            SET content = ?, updated_at = ?
                            WHERE id = ?
                        ''', (new_content, current_time, news_id))
                        conn.commit()
                        conn.close()
                        # 刷新数据以更新更新时间
                        refresh_data()
                    except Exception as e:
                        print(f"自动保存失败: {e}")
            def on_content_change(event=None):
                """内容变化时触发自动保存"""
                if content_edit_mode.get() and current_editing_news_id[0]:
                    # 取消之前的定时器
                    if auto_save_timer[0]:
                        self.root.after_cancel(auto_save_timer[0])
                    # 设置新的定时器,1秒后自动保存
                    auto_save_timer[0] = self.root.after(1000, auto_save_content)
            def toggle_edit_mode():
                if content_edit_mode.get():
                    # 进入编辑模式
                    content_text.config(state=tk.NORMAL)
                    edit_btn.config(text="退出编辑")
                    current_news_id = get_current_news_id()
                    if current_news_id:
                        current_editing_news_id[0] = current_news_id
                        # 绑定内容变化事件
                        content_text.bind('<KeyRelease>', on_content_change)
                        content_text.bind('<Button-1>', on_content_change)
                else:
                    # 退出编辑模式,执行最后一次保存
                    if current_editing_news_id[0]:
                        auto_save_content()
                    # 取消定时器
                    if auto_save_timer[0]:
                        self.root.after_cancel(auto_save_timer[0])
                        auto_save_timer[0] = None
                    # 解绑事件
                    content_text.unbind('<KeyRelease>')
                    content_text.unbind('<Button-1>')
                    content_text.config(state=tk.DISABLED)
                    edit_btn.config(text="编辑")
                    current_editing_news_id[0] = None
            edit_btn = ttk.Button(content_btn_frame, text="编辑", command=lambda: [content_edit_mode.set(not content_edit_mode.get()), toggle_edit_mode()])
            edit_btn.pack(side=tk.LEFT, padx=5)
            # 添加自动保存提示标签
            auto_save_label = ttk.Label(content_btn_frame, text="(编辑模式下,修改后1秒自动保存)", font=("TkDefaultFont", 8), foreground="gray")
            auto_save_label.pack(side=tk.LEFT, padx=5)
            def get_current_news_id():
                """获取当前选中的资讯ID"""
                selection = tree.selection()
                if not selection:
                    return None
                item = tree.item(selection[0])
                return item['values'][0] if item['values'] else None
            content_frame_detail = ttk.LabelFrame(content_tab, text="完整内容", padding=5)
            content_frame_detail.pack(fill=tk.BOTH, expand=True)
            content_text = scrolledtext.ScrolledText(content_frame_detail, height=15, wrap=tk.WORD,
                                                   font=("TkDefaultFont", 12), state=tk.DISABLED)
            content_text.pack(fill=tk.BOTH, expand=True)
            # 评注标签页
            comment_tab = ttk.Frame(right_notebook)
            right_notebook.add(comment_tab, text="评注")
            comment_label = ttk.Label(comment_tab, text="评注管理", font=("TkDefaultFont", 12, "bold"))
            comment_label.pack(anchor=tk.W, pady=(0, 5))
            # 评注输入区域
            comment_input_frame = ttk.LabelFrame(comment_tab, text="添加评注", padding=5)
            comment_input_frame.pack(fill=tk.X, pady=(0, 5))
            # 署名输入
            author_frame = ttk.Frame(comment_input_frame)
            author_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(author_frame, text="署名:").pack(side=tk.LEFT, padx=5)
            author_var = tk.StringVar(value="匿名")
            author_entry = ttk.Entry(author_frame, textvariable=author_var, width=20)
            author_entry.pack(side=tk.LEFT, padx=5)
            # 颜色选择
            color_frame = ttk.Frame(comment_input_frame)
            color_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(color_frame, text="颜色:").pack(side=tk.LEFT, padx=5)
            color_var = tk.StringVar(value="black")
            colors = [("黑色", "black"), ("红色", "red"), ("蓝色", "blue"), ("绿色", "green"),
                     ("橙色", "orange"), ("紫色", "purple"), ("棕色", "brown"), ("灰色", "gray")]
            for text, value in colors:
                ttk.Radiobutton(color_frame, text=text, variable=color_var, value=value).pack(side=tk.LEFT, padx=2)
            # 字体选择
            font_frame = ttk.Frame(comment_input_frame)
            font_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(font_frame, text="字体:").pack(side=tk.LEFT, padx=5)
            font_family_var = tk.StringVar(value="TkDefaultFont")
            font_families = [("默认", "TkDefaultFont"), ("宋体", "SimSun"), ("微软雅黑", "Microsoft YaHei"),
                            ("Arial", "Arial"), ("Times", "Times New Roman")]
            font_family_combo = ttk.Combobox(font_frame, textvariable=font_family_var, values=[f[1] for f in font_families],
                                            state="readonly", width=15)
            font_family_combo.pack(side=tk.LEFT, padx=5)
            ttk.Label(font_frame, text="字号:").pack(side=tk.LEFT, padx=(10, 5))
            font_size_var = tk.IntVar(value=10)
            font_size_spin = ttk.Spinbox(font_frame, from_=8, to=24, textvariable=font_size_var, width=5)
            font_size_spin.pack(side=tk.LEFT, padx=5)
            # 评注内容输入
            ttk.Label(comment_input_frame, text="评注内容:").pack(anchor=tk.W, pady=(5, 0))
            comment_entry = scrolledtext.ScrolledText(comment_input_frame, height=4, wrap=tk.WORD)
            comment_entry.pack(fill=tk.X, pady=(5, 0))
            # 添加评注按钮
            def add_comment():
                current_news_id = get_current_news_id()
                if not current_news_id:
                    messagebox.showwarning("警告", "请先选择一条资讯")
                    return
                comment_text = comment_entry.get("1.0", tk.END).strip()
                if not comment_text:
                    messagebox.showwarning("警告", "请输入评注内容")
                    return
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO news_comments (news_id, comment_text, author, color, font_family, font_size)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (current_news_id, comment_text, author_var.get().strip(), color_var.get(),
                          font_family_var.get(), font_size_var.get()))
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("成功", "评注已添加")
                    comment_entry.delete("1.0", tk.END)
                    refresh_comments()
                except Exception as e:
                    messagebox.showerror("错误", f"添加评注失败: {e}")
            ttk.Button(comment_input_frame, text="添加评注", command=add_comment).pack(pady=5)
            # 评注列表
            comment_list_frame = ttk.LabelFrame(comment_tab, text="评注列表", padding=5)
            comment_list_frame.pack(fill=tk.BOTH, expand=True)
            comment_columns = ("日期", "署名", "内容预览")
            comment_tree = ttk.Treeview(comment_list_frame, columns=comment_columns, show="headings", height=15)
            comment_tree.column("日期", width=150, anchor=tk.CENTER)
            comment_tree.column("署名", width=100, anchor=tk.CENTER)
            comment_tree.column("内容预览", width=300)
            for col in comment_columns:
                comment_tree.heading(col, text=col)
            comment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            comment_scrollbar = ttk.Scrollbar(comment_list_frame, orient=tk.VERTICAL, command=comment_tree.yview)
            comment_tree.configure(yscrollcommand=comment_scrollbar.set)
            comment_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            # 评注操作按钮
            comment_btn_frame = ttk.Frame(comment_tab)
            comment_btn_frame.pack(fill=tk.X, pady=(5, 0))
            def refresh_comments():
                """刷新评注列表"""
                # 清空现有数据
                for item in comment_tree.get_children():
                    comment_tree.delete(item)
                current_news_id = get_current_news_id()
                if not current_news_id:
                    return
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id, comment_text, author, color, font_family, font_size, created_at
                        FROM news_comments
                        WHERE news_id = ?
                        ORDER BY created_at DESC
                    ''', (current_news_id,))
                    rows = cursor.fetchall()
                    conn.close()
                    for row in rows:
                        _comment_id, comment_text, author, color, _font_family, _font_size, created_at = row
                        preview = comment_text[:50] + "..." if len(comment_text) > 50 else comment_text
                        comment_tree.insert("", tk.END, values=(created_at, author or "匿名", preview),
                                           tags=(color or "black",))
                        # 设置标签颜色(如果支持)
                        try:
                            comment_tree.tag_configure(color or "black", foreground=color or "black")
                        except:
                            pass
                except Exception as e:
                    messagebox.showerror("错误", f"加载评注失败: {e}")
            def edit_comment():
                """编辑评注"""
                selection = comment_tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择要编辑的评注")
                    return
                comment_tree.item(selection[0])
                # 从标签中获取comment_id(需要存储)
                current_news_id = get_current_news_id()
                if not current_news_id:
                    return
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id, comment_text, author, color, font_family, font_size
                        FROM news_comments
                        WHERE news_id = ?
                        ORDER BY created_at DESC
                    ''', (current_news_id,))
                    rows = cursor.fetchall()
                    conn.close()
                    # 获取选中项的索引
                    selected_index = comment_tree.index(selection[0])
                    if selected_index >= len(rows):
                        return
                    comment_id, comment_text, author, color, font_family, font_size = rows[selected_index]
                    edit_window = self._toplevel(db_window)
                    edit_window.title("编辑评注")
                    edit_window.geometry("500x400")
                    ttk.Label(edit_window, text="署名:").pack(pady=5)
                    edit_author_var = tk.StringVar(value=author or "匿名")
                    edit_author_entry = ttk.Entry(edit_window, textvariable=edit_author_var, width=30)
                    edit_author_entry.pack(pady=5)
                    ttk.Label(edit_window, text="颜色:").pack(pady=5)
                    edit_color_var = tk.StringVar(value=color or "black")
                    edit_color_frame = ttk.Frame(edit_window)
                    edit_color_frame.pack(pady=5)
                    for text, value in colors:
                        ttk.Radiobutton(edit_color_frame, text=text, variable=edit_color_var, value=value).pack(side=tk.LEFT, padx=2)
                    ttk.Label(edit_window, text="字体:").pack(pady=5)
                    edit_font_frame = ttk.Frame(edit_window)
                    edit_font_frame.pack(pady=5)
                    edit_font_family_var = tk.StringVar(value=font_family or "TkDefaultFont")
                    edit_font_family_combo = ttk.Combobox(edit_font_frame, textvariable=edit_font_family_var,
                                                         values=[f[1] for f in font_families], state="readonly", width=15)
                    edit_font_family_combo.pack(side=tk.LEFT, padx=5)
                    ttk.Label(edit_font_frame, text="字号:").pack(side=tk.LEFT, padx=5)
                    edit_font_size_var = tk.IntVar(value=font_size or 10)
                    edit_font_size_spin = ttk.Spinbox(edit_font_frame, from_=8, to=24, textvariable=edit_font_size_var, width=5)
                    edit_font_size_spin.pack(side=tk.LEFT, padx=5)
                    ttk.Label(edit_window, text="评注内容:").pack(pady=5)
                    edit_comment_entry = scrolledtext.ScrolledText(edit_window, height=8, width=50)
                    edit_comment_entry.insert("1.0", comment_text)
                    edit_comment_entry.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
                    def save_edit():
                        try:
                            conn = sqlite3.connect(DB_PATH)
                            cursor = conn.cursor()
                            cursor.execute('''
                                UPDATE news_comments
                                SET comment_text = ?, author = ?, color = ?, font_family = ?, font_size = ?
                                WHERE id = ?
                            ''', (edit_comment_entry.get("1.0", tk.END).strip(), edit_author_var.get().strip(),
                                  edit_color_var.get(), edit_font_family_var.get(), edit_font_size_var.get(), comment_id))
                            conn.commit()
                            conn.close()
                            messagebox.showinfo("成功", "评注已更新")
                            edit_window.destroy()
                            refresh_comments()
                        except Exception as e:
                            messagebox.showerror("错误", f"更新失败: {e}")
                    ttk.Button(edit_window, text="保存", command=save_edit).pack(pady=10)
                    ttk.Button(edit_window, text="取消", command=edit_window.destroy).pack()
                except Exception as e:
                    messagebox.showerror("错误", f"获取评注失败: {e}")
            def delete_comment():
                """删除评注"""
                selection = comment_tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择要删除的评注")
                    return
                if not messagebox.askyesno("确认", "确定要删除这条评注吗?"):
                    return
                current_news_id = get_current_news_id()
                if not current_news_id:
                    return
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id FROM news_comments
                        WHERE news_id = ?
                        ORDER BY created_at DESC
                    ''', (current_news_id,))
                    rows = cursor.fetchall()
                    selected_index = comment_tree.index(selection[0])
                    if selected_index < len(rows):
                        comment_id = rows[selected_index][0]
                        cursor.execute('DELETE FROM news_comments WHERE id = ?', (comment_id,))
                        conn.commit()
                        conn.close()
                        messagebox.showinfo("成功", "评注已删除")
                        refresh_comments()
                    else:
                        conn.close()
                except Exception as e:
                    messagebox.showerror("错误", f"删除失败: {e}")
            def view_comment():
                """查看评注详情"""
                selection = comment_tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择要查看的评注")
                    return
                current_news_id = get_current_news_id()
                if not current_news_id:
                    return
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT comment_text, author, color, font_family, font_size, created_at
                        FROM news_comments
                        WHERE news_id = ?
                        ORDER BY created_at DESC
                    ''', (current_news_id,))
                    rows = cursor.fetchall()
                    conn.close()
                    selected_index = comment_tree.index(selection[0])
                    if selected_index < len(rows):
                        comment_text, author, color, font_family, font_size, created_at = rows[selected_index]
                        view_window = self._toplevel(db_window)
                        view_window.title("评注详情")
                        view_window.geometry("600x400")
                        info_text = f"日期: {created_at}\n署名: {author or '匿名'}\n颜色: {color}\n字体: {font_family}, 字号: {font_size}\n\n"
                        ttk.Label(view_window, text=info_text, font=("TkDefaultFont", 11)).pack(anchor=tk.W, padx=10, pady=5)
                        ttk.Label(view_window, text="评注内容:", font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 5))
                        view_text = scrolledtext.ScrolledText(view_window, height=15, wrap=tk.WORD,
                                                             font=(font_family or "TkDefaultFont", font_size or 10))
                        view_text.insert("1.0", comment_text)
                        view_text.config(state=tk.DISABLED, fg=color or "black")
                        view_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                        ttk.Button(view_window, text="关闭", command=view_window.destroy).pack(pady=10)
                except Exception as e:
                    messagebox.showerror("错误", f"查看评注失败: {e}")
            ttk.Button(comment_btn_frame, text="查看", command=view_comment).pack(side=tk.LEFT, padx=5)
            ttk.Button(comment_btn_frame, text="编辑", command=edit_comment).pack(side=tk.LEFT, padx=5)
            ttk.Button(comment_btn_frame, text="删除", command=delete_comment).pack(side=tk.LEFT, padx=5)
            ttk.Button(comment_btn_frame, text="刷新", command=refresh_comments).pack(side=tk.LEFT, padx=5)
            # 按钮框架
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)
            def refresh_data():
                """刷新数据"""
                # 清空现有数据
                for item in tree.get_children():
                    tree.delete(item)
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    # 构建查询
                    tab_name_filter = tab_name_var.get().strip()
                    if tab_name_filter:
                        cursor.execute('''
                            SELECT id, tab_name, content, created_at, updated_at
                            FROM news_info
                            WHERE tab_name LIKE ?
                            ORDER BY created_at DESC
                        ''', (f'%{tab_name_filter}%',))
                    else:
                        cursor.execute('''
                            SELECT id, tab_name, content, created_at, updated_at
                            FROM news_info
                            ORDER BY created_at DESC
                        ''')
                    rows = cursor.fetchall()
                    conn.close()
                    # 填充数据
                    for row in rows:
                        news_id, tab_name, content, created_at, updated_at = row
                        # 内容预览(前100字符)
                        content_preview = content[:100] + "..." if content and len(content) > 100 else (content or "")
                        tree.insert("", tk.END, values=(news_id, tab_name, content_preview, created_at, updated_at))
                except Exception as e:
                    messagebox.showerror("错误", f"查询数据失败: {e}")
            def on_select(event):
                """选择事件处理"""
                # 如果正在编辑,先保存当前内容
                if content_edit_mode.get() and current_editing_news_id[0]:
                    auto_save_content()
                    # 取消定时器
                    if auto_save_timer[0]:
                        self.root.after_cancel(auto_save_timer[0])
                        auto_save_timer[0] = None
                    # 退出编辑模式
                    content_edit_mode.set(False)
                    content_text.config(state=tk.DISABLED)
                    edit_btn.config(text="编辑")
                    content_text.unbind('<KeyRelease>')
                    content_text.unbind('<Button-1>')
                    current_editing_news_id[0] = None
                selection = tree.selection()
                if not selection:
                    content_text.delete("1.0", tk.END)
                    content_text.config(state=tk.DISABLED)
                    edit_btn.config(text="编辑")
                    content_edit_mode.set(False)
                    refresh_comments()
                    return
                item = tree.item(selection[0])
                news_id = item['values'][0]
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('SELECT content FROM news_info WHERE id = ?', (news_id,))
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        content_text.config(state=tk.NORMAL)
                        content_text.delete("1.0", tk.END)
                        content_text.insert("1.0", row[0] or "")
                        content_text.config(state=tk.DISABLED)
                        edit_btn.config(text="编辑")
                        content_edit_mode.set(False)
                    # 刷新评注列表
                    refresh_comments()
                except Exception as e:
                    messagebox.showerror("错误", f"获取内容失败: {e}")
            def add_record():
                """添加记录"""
                add_window = self._toplevel(db_window)
                add_window.title("添加资讯")
                add_window.geometry("600x500")
                ttk.Label(add_window, text="标签页名称:").pack(pady=5)
                name_entry = ttk.Entry(add_window, width=50)
                name_entry.pack(pady=5)
                ttk.Label(add_window, text="内容:").pack(pady=5)
                content_entry = scrolledtext.ScrolledText(add_window, height=15, width=70)
                content_entry.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
                def save_add():
                    try:
                        if save_news_info_to_db(
                            tab_name=name_entry.get().strip(),
                            content=content_entry.get("1.0", tk.END).strip()
                        ):
                            messagebox.showinfo("成功", "添加成功")
                            add_window.destroy()
                            refresh_data()
                        else:
                            messagebox.showerror("错误", "添加失败")
                    except Exception as e:
                        messagebox.showerror("错误", f"添加失败: {e}")
                ttk.Button(add_window, text="保存", command=save_add).pack(pady=10)
                ttk.Button(add_window, text="取消", command=add_window.destroy).pack()
            def edit_record():
                """编辑记录"""
                selection = tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择要编辑的记录")
                    return
                item = tree.item(selection[0])
                news_id = item['values'][0]
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('SELECT tab_name, content FROM news_info WHERE id = ?', (news_id,))
                    row = cursor.fetchone()
                    conn.close()
                    if not row:
                        messagebox.showerror("错误", "记录不存在")
                        return
                    edit_window = self._toplevel(db_window)
                    edit_window.title("编辑资讯")
                    edit_window.geometry("600x500")
                    ttk.Label(edit_window, text="标签页名称:").pack(pady=5)
                    name_entry = ttk.Entry(edit_window, width=50)
                    name_entry.insert(0, row[0] or "")
                    name_entry.pack(pady=5)
                    ttk.Label(edit_window, text="内容:").pack(pady=5)
                    content_entry = scrolledtext.ScrolledText(edit_window, height=15, width=70)
                    content_entry.insert("1.0", row[1] or "")
                    content_entry.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
                    def save_edit():
                        try:
                            conn = sqlite3.connect(DB_PATH)
                            cursor = conn.cursor()
                            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            cursor.execute('''
                                UPDATE news_info
                                SET tab_name = ?, content = ?, updated_at = ?
                                WHERE id = ?
                            ''', (name_entry.get().strip(), content_entry.get("1.0", tk.END).strip(), current_time, news_id))
                            conn.commit()
                            conn.close()
                            messagebox.showinfo("成功", "更新成功")
                            edit_window.destroy()
                            refresh_data()
                        except Exception as e:
                            messagebox.showerror("错误", f"更新失败: {e}")
                    ttk.Button(edit_window, text="保存", command=save_edit).pack(pady=10)
                    ttk.Button(edit_window, text="取消", command=edit_window.destroy).pack()
                except Exception as e:
                    messagebox.showerror("错误", f"获取记录失败: {e}")
            def delete_record():
                """删除记录"""
                selection = tree.selection()
                if not selection:
                    messagebox.showwarning("警告", "请先选择要删除的记录")
                    return
                if messagebox.askyesno("确认", "确定要删除这条记录吗?"):
                    item = tree.item(selection[0])
                    news_id = item['values'][0]
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('DELETE FROM news_info WHERE id = ?', (news_id,))
                        conn.commit()
                        conn.close()
                        messagebox.showinfo("成功", "删除成功")
                        refresh_data()
                    except Exception as e:
                        messagebox.showerror("错误", f"删除失败: {e}")
            # 绑定选择事件
            tree.bind("<<TreeviewSelect>>", on_select)
            # 按钮
            ttk.Button(button_frame, text="刷新", command=refresh_data).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="添加", command=add_record).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="编辑", command=edit_record).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="删除", command=delete_record).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="关闭", command=db_window.destroy).pack(side=tk.RIGHT, padx=5)
            # 初始加载数据
            refresh_data()
        except Exception as e:
            messagebox.showerror("错误", f"显示资讯数据库失败: {e}")


__all__ = ["DatabaseMixin"]
