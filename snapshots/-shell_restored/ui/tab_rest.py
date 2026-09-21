try:
    import jieba
except ImportError:
    jieba = None
"""剩余所有方法"""
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
from logic.stock_names import *  # get_stock_name_by_code 等

from datetime import datetime, timedelta
import re
import json
import os
import sys
import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin
import sqlite3

class RestMixin:
    """catch-all"""

    def insert_image_to_tab(self, tab_id):
        """在指定标签页插入图片"""
        try:
            if tab_id not in self.text_widgets:
                messagebox.showwarning("警告", "标签页不存在")
                return
            # 选择图片文件
            file_path = filedialog.askopenfilename(
                title="选择图片",
                filetypes=[
                    ("图片文件", "*.png *.jpg *.jpeg *.gif *.bmp *.ico"),
                    ("所有文件", "*.*")
                ]
            )
            if not file_path:
                return
            # 保存图片
            relative_path = self.save_image_file(file_path, is_file_path=True)
            if not relative_path:
                return
            # 在文本中插入图片标记
            text_widget = self.text_widgets[tab_id]['widget']
            cursor_pos = text_widget.index(tk.INSERT)
            # 插入图片标记
            image_marker = f"\n[IMAGE:{relative_path}]\n"
            text_widget.insert(cursor_pos, image_marker)
            # 配置图片标记的样式和点击事件
            start_pos = text_widget.index(f"{cursor_pos} linestart")
            end_pos = text_widget.index(f"{cursor_pos} lineend +1c")
            text_widget.tag_add("image_marker", start_pos, end_pos)
            text_widget.tag_config("image_marker", foreground="blue", underline=True)
            text_widget.tag_bind("image_marker", "<Button-1>",
                               lambda e, path=relative_path: self.view_image(path))
            messagebox.showinfo("成功", f"图片已插入: {relative_path}")
        except Exception as e:
            messagebox.showerror("错误", f"插入图片失败: {e}")
            import traceback
            traceback.print_exc()

    def paste_image_to_tab(self, tab_id):
        """从剪贴板粘贴图片到指定标签页"""
        try:
            if tab_id not in self.text_widgets:
                messagebox.showwarning("警告", "标签页不存在")
                return
            # 尝试从剪贴板获取图片
            try:
                # 尝试获取剪贴板中的图片
                clipboard_image = self.root.clipboard_get(type='image/png')
                # 如果成功,说明剪贴板中有图片数据
                # 但tkinter的clipboard_get不支持直接获取图片数据
                # 我们需要使用其他方法
            except:
                pass
            # 使用PIL从剪贴板读取图片
            try:
                from PIL import ImageGrab
                clipboard_image = ImageGrab.grabclipboard()
                if clipboard_image is None:
                    messagebox.showwarning("提示", "剪贴板中没有图片")
                    return
                # 保存图片
                relative_path = self.save_image_file(clipboard_image, is_file_path=False)
                if not relative_path:
                    return
                # 在文本中插入图片标记
                text_widget = self.text_widgets[tab_id]['widget']
                cursor_pos = text_widget.index(tk.INSERT)
                # 插入图片标记
                image_marker = f"\n[IMAGE:{relative_path}]\n"
                text_widget.insert(cursor_pos, image_marker)
                # 配置图片标记的样式和点击事件
                start_pos = text_widget.index(f"{cursor_pos} linestart")
                end_pos = text_widget.index(f"{cursor_pos} lineend +1c")
                text_widget.tag_add("image_marker", start_pos, end_pos)
                text_widget.tag_config("image_marker", foreground="blue", underline=True)
                text_widget.tag_bind("image_marker", "<Button-1>",
                                   lambda e, path=relative_path: self.view_image(path))
                messagebox.showinfo("成功", f"图片已粘贴: {relative_path}")
            except ImportError:
                messagebox.showerror("错误", "需要PIL库支持剪贴板图片功能")
            except Exception as e:
                messagebox.showerror("错误", f"粘贴图片失败: {e}")
                import traceback
                traceback.print_exc()
        except Exception as e:
            messagebox.showerror("错误", f"粘贴图片失败: {e}")
            import traceback
            traceback.print_exc()

    def view_image(self, relative_path):
        """查看图片"""
        try:
            full_path = os.path.join(D_IMAGES_DIR, relative_path)
            if not os.path.exists(full_path):
                messagebox.showerror("错误", f"图片文件不存在: {full_path}")
                return
            # 打开图片查看窗口
            image_window = self._safe_toplevel(self.root)
            image_window.title(f"查看图片 - {os.path.basename(full_path)}")
            image_window.geometry("800x600")
            # 加载并显示图片
            try:
                img = Image.open(full_path)
                # 计算缩放比例以适应窗口
                max_width, max_height = 780, 580
                img_width, img_height = img.size
                scale = min(max_width / img_width, max_height / img_height, 1.0)
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                # 创建标签显示图片
                img_label = tk.Label(image_window, image=photo)
                img_label.image = photo  # 保持引用
                img_label.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
                # 添加图片路径信息
                path_label = tk.Label(image_window, text=f"路径: {full_path}",
                                     font=("Arial", 9), fg="gray")
                path_label.pack(side=tk.BOTTOM, pady=5)
            except Exception as e:
                messagebox.showerror("错误", f"加载图片失败: {e}")
                image_window.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"查看图片失败: {e}")

    def parse_and_display_images(self, text_widget, content):
        """解析文本中的图片标记并显示"""
        try:
            # 清空文本框
            text_widget.delete("1.0", tk.END)
            # 插入内容
            text_widget.insert("1.0", content)
            # 查找所有图片标记 [IMAGE:path]
            import re
            pattern = r'\[IMAGE:([^\]]+)\]'
            matches = list(re.finditer(pattern, content))
            # 为每个图片标记添加样式和点击事件
            for i, match in enumerate(matches):
                start_pos = f"1.0 + {match.start()}c"
                end_pos = f"1.0 + {match.end()}c"
                relative_path = match.group(1)
                # 为每个图片标记创建唯一的tag名称
                tag_name = f"image_marker_{i}"
                text_widget.tag_add(tag_name, start_pos, end_pos)
                text_widget.tag_config(tag_name, foreground="blue", underline=True)
                # 使用lambda的默认参数来捕获path值
                text_widget.tag_bind(tag_name, "<Button-1>",
                                   lambda e, path=relative_path: self.view_image(path))
        except Exception as e:
            print(f"解析图片标记失败: {e}")
            import traceback
            traceback.print_exc()

    def get_active_text_widget(self):
        """获取当前活动标签页的文本框"""
        try:
            selected_tab = self.text_notebook.select()
            if selected_tab:
                for tab_info in self.text_widgets.values():
                    if str(tab_info['frame']) == selected_tab:
                        return tab_info['widget']
        except:
            pass
        # 如果没有找到,返回第一个标签页
        if self.text_widgets:
            first_tab = next(iter(self.text_widgets.values()))
            return first_tab['widget']
        return None

    def get_current_text(self):
        """获取当前标签页的文本"""
        text_widget = self.get_active_text_widget()
        if text_widget:
            return text_widget.get("1.0", tk.END).strip()
        return ""

    def get_active_text_title(self):
        """获取当前活动左侧标签页的标题"""
        try:
            selected_tab = self.text_notebook.select()
            if selected_tab:
                for tab_info in self.text_widgets.values():
                    if str(tab_info['frame']) == selected_tab:
                        return tab_info['title']
        except Exception:
            pass
        # 回退:第一个标签页标题
        if self.text_widgets:
            first_tab = next(iter(self.text_widgets.values()))
            return first_tab.get('title', '未命名')
        return "未命名"

    def iter_text_widgets(self):
        """迭代所有标签页文本框"""
        for tab_info in self.text_widgets.values():
            yield tab_info['widget']

    def get_all_texts(self):
        """获取所有标签页文本"""
        all_texts = []
        for tab_id, tab_info in list(self.text_widgets.items()):  # 使用list()避免迭代时修改字典
            try:
                widget = tab_info.get('widget')
                if widget is None:
                    continue
                # 检查widget是否仍然存在
                if not hasattr(widget, 'winfo_exists') or not widget.winfo_exists():
                    continue
                text = widget.get("1.0", tk.END).strip()
                if text:
                    all_texts.append({
                        'title': tab_info.get('title', '未命名'),
                        'text': text
                    })
            except (tk.TclError, AttributeError) as e:
                # widget已被销毁或无效,跳过
                print(f"跳过无效的widget {tab_id}: {e}")
                continue
        return all_texts

    def update_text_input_reference(self):
        """更新text_input引用,指向当前活动标签页(保持向后兼容)"""
        self.text_input = self.get_active_text_widget()

    def open_full_window_viewer(self, tab_id):
        """打开全窗口浏览界面,类似Word功能"""
        try:
            if tab_id not in self.text_widgets:
                return
            tab_info = self.text_widgets[tab_id]
            text_widget = tab_info['widget']
            title = tab_info['title']
            content = text_widget.get("1.0", tk.END)
            # 创建全窗口
            win = self._safe_toplevel(self.root)
            win.title(f"全窗口浏览 - {title}")
            win.geometry("1200x800")
            win.transient(self.root)
            win.resizable(True, True)
            # 存储窗口状态
            win._is_minimized = False
            win._original_geometry = "1200x800"
            # 配置窗口布局
            win.columnconfigure(0, weight=1)
            win.rowconfigure(1, weight=1)
            # 顶部工具栏
            toolbar = ttk.Frame(win)
            toolbar.pack(fill=tk.X, padx=5, pady=5)
            # 字体控制
            font_frame = ttk.LabelFrame(toolbar, text="字体", padding=5)
            font_frame.pack(side=tk.LEFT, padx=5)
            ttk.Label(font_frame, text="大小:").pack(side=tk.LEFT, padx=2)
            font_size_var = tk.StringVar(value="14")
            font_size_combo = ttk.Combobox(font_frame, textvariable=font_size_var,
                                          values=["10", "12", "14", "16", "18", "20", "24"],
                                          width=5, state="readonly")
            font_size_combo.pack(side=tk.LEFT, padx=2)
            ttk.Label(font_frame, text="字体:").pack(side=tk.LEFT, padx=(10, 2))
            font_family_var = tk.StringVar(value="TkDefaultFont")
            font_family_combo = ttk.Combobox(font_frame, textvariable=font_family_var,
                                            values=["TkDefaultFont", "Microsoft YaHei", "SimHei", "SimSun", "Arial", "Courier"],
                                            width=15, state="readonly")
            font_family_combo.pack(side=tk.LEFT, padx=2)
            # 主内容区域 - 左右分栏
            content_frame = ttk.Frame(win)
            content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            content_frame.columnconfigure(0, weight=1)
            content_frame.columnconfigure(1, weight=1)
            content_frame.rowconfigure(0, weight=1)
            # 左侧:文本查看/编辑区域
            left_panel = ttk.LabelFrame(content_frame, text="文本内容", padding=5)
            left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
            left_panel.columnconfigure(0, weight=1)
            left_panel.rowconfigure(0, weight=1)
            # 根据情绪周期确定背景颜色
            if hasattr(self, 'get_emotion_bg_color'):
                viewer_bg_color = self.get_emotion_bg_color()
            else:
                viewer_bg_color = "white"
            viewer_text = scrolledtext.ScrolledText(left_panel, wrap=tk.WORD,
                                                   font=("TkDefaultFont", 14), undo=True, bg=viewer_bg_color)
            viewer_text.pack(fill=tk.BOTH, expand=True)
            viewer_text.insert("1.0", content)
            self._enable_text_copy_menu(viewer_text, readonly=True)
            # 保存引用以便后续更新背景颜色
            if not hasattr(self, '_browse_window_text_widgets'):
                self._browse_window_text_widgets = []
            self._browse_window_text_widgets.append(viewer_text)
            # 配置查找高亮标签
            viewer_text.tag_config("search_highlight", background="yellow")
            # 右侧:分析结果区域(使用标签页)
            right_panel = ttk.LabelFrame(content_frame, text="分析结果", padding=5)
            right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
            right_panel.columnconfigure(0, weight=1)
            right_panel.rowconfigure(1, weight=1)
            # 右侧按钮框架
            right_button_frame = ttk.Frame(right_panel)
            right_button_frame.pack(fill=tk.X, pady=(0, 5))
            # 创建标签页控件
            result_notebook = ttk.Notebook(right_panel)
            result_notebook.pack(fill=tk.BOTH, expand=True)
            # 存储标签页的字典
            result_tabs = {}
            def get_or_create_tab(tab_name):
                """获取或创建标签页"""
                if tab_name not in result_tabs:
                    # 创建新标签页
                    tab_frame = ttk.Frame(result_notebook)
                    result_notebook.add(tab_frame, text=tab_name)
                    # 根据情绪周期确定背景颜色
                    if hasattr(self, 'get_emotion_bg_color'):
                        tab_bg_color = self.get_emotion_bg_color()
                    else:
                        tab_bg_color = "white"
                    # 创建文本控件
                    tab_text = scrolledtext.ScrolledText(tab_frame, wrap=tk.WORD,
                                                        font=("TkDefaultFont", 12), state=tk.DISABLED, bg=tab_bg_color)
                    tab_text.pack(fill=tk.BOTH, expand=True)
                    # 保存引用以便后续更新背景颜色
                    if not hasattr(self, '_analysis_result_text_widgets'):
                        self._analysis_result_text_widgets = []
                    self._analysis_result_text_widgets.append(tab_text)
                    result_tabs[tab_name] = {
                        'frame': tab_frame,
                        'text': tab_text
                    }
                # 切换到该标签页
                tab_index = list(result_tabs.keys()).index(tab_name)
                result_notebook.select(tab_index)
                return result_tabs[tab_name]['text']
            # 创建默认的"AI分析结果"标签页
            get_or_create_tab("AI分析结果")
            # 查找功能
            search_frame = ttk.LabelFrame(toolbar, text="查找", padding=5)
            search_frame.pack(side=tk.LEFT, padx=5)
            search_entry = ttk.Entry(search_frame, width=20)
            search_entry.pack(side=tk.LEFT, padx=2)
            search_positions = []
            current_search_index = [0]  # 使用列表以便在内部函数中修改
            def do_search():
                """执行查找"""
                search_term = search_entry.get().strip()
                if not search_term:
                    messagebox.showwarning("警告", "请输入要查找的文本")
                    return
                search_positions.clear()
                start = "1.0"
                while True:
                    pos = viewer_text.search(search_term, start, tk.END)
                    if not pos:
                        break
                    search_positions.append(pos)
                    start = pos + "+1c"
                if not search_positions:
                    messagebox.showinfo("查找结果", f"未找到 '{search_term}'")
                    search_pos_label.config(text="")
                    return
                current_search_index[0] = 0
                highlight_search_result()
                search_pos_label.config(text=f"1/{len(search_positions)}")
            def search_next():
                """查找下一个"""
                if not search_positions:
                    messagebox.showwarning("警告", "请先执行查找")
                    return
                current_search_index[0] = (current_search_index[0] + 1) % len(search_positions)
                highlight_search_result()
                search_pos_label.config(text=f"{current_search_index[0] + 1}/{len(search_positions)}")
            def search_prev():
                """查找上一个"""
                if not search_positions:
                    messagebox.showwarning("警告", "请先执行查找")
                    return
                current_search_index[0] = (current_search_index[0] - 1) % len(search_positions)
                highlight_search_result()
                search_pos_label.config(text=f"{current_search_index[0] + 1}/{len(search_positions)}")
            def highlight_search_result():
                """高亮显示查找结果"""
                if not search_positions or current_search_index[0] < 0:
                    return
                # 清除之前的高亮
                viewer_text.tag_remove("search_highlight", "1.0", tk.END)
                # 高亮当前匹配项
                pos = search_positions[current_search_index[0]]
                search_term = search_entry.get().strip()
                end_pos = f"{pos}+{len(search_term)}c"
                # 添加高亮标签
                viewer_text.tag_add("search_highlight", pos, end_pos)
                viewer_text.tag_config("search_highlight", background="yellow")
                # 滚动到匹配位置
                viewer_text.see(pos)
            ttk.Button(search_frame, text="查找", command=do_search).pack(side=tk.LEFT, padx=2)
            ttk.Button(search_frame, text="下一个", command=search_next).pack(side=tk.LEFT, padx=2)
            ttk.Button(search_frame, text="上一个", command=search_prev).pack(side=tk.LEFT, padx=2)
            search_pos_label = ttk.Label(search_frame, text="")
            search_pos_label.pack(side=tk.LEFT, padx=5)
            # 分析按钮
            analyze_frame = ttk.Frame(toolbar)
            analyze_frame.pack(side=tk.LEFT, padx=5)
            def run_analysis():
                """运行AI分析"""
                content = viewer_text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showwarning("警告", "文本内容为空")
                    return
                # 在后台线程中运行AI分析
                def analyze():
                    try:
                        system_prompt = "你是一个专业的文本分析专家,能够深入分析文本内容,提取关键信息,提供有价值的洞察。"
                        user_prompt = f"""请分析以下文本内容,并提供专业的分析:
文本内容:
{content[:3000]}
请提供:
1. 文本主要内容摘要
2. 关键信息和要点
3. 文本的情感倾向和语气
4. 潜在的问题或风险
5. 建议和行动项"""
                        ai_result = self.call_ai_model(user_prompt, system_prompt)
                        if not ai_result:
                            ai_result = "未获取到AI分析结果,请检查配置。"
                        # 从原文提取股票名/代码,附加鱼身鱼尾(与持仓检测同源)
                        try:
                            _stocks_found, _ = extract_stock_names(content)
                            _fish_app = self._build_fish_phase_appendix_from_extracted_stocks(_stocks_found)
                            if _fish_app:
                                ai_result = f"{ai_result}{_fish_app}"
                        except Exception:
                            pass
                    except Exception as e:
                        ai_result = f"AI分析失败: {e}"
                    def update_ui():
                        tab_text = get_or_create_tab("AI分析结果")
                        tab_text.config(state=tk.NORMAL)
                        tab_text.delete("1.0", tk.END)
                        tab_text.insert(tk.END, "【AI分析结果】\n")
                        tab_text.insert(tk.END, "="*80 + "\n\n")
                        tab_text.insert(tk.END, ai_result)
                        tab_text.config(state=tk.DISABLED)
                        tab_text.see("1.0")
                    if hasattr(self, "root") and self.root.winfo_exists():
                        self.root.after(0, update_ui)
                tab_text = get_or_create_tab("AI分析结果")
                tab_text.config(state=tk.NORMAL)
                tab_text.delete("1.0", tk.END)
                tab_text.insert(tk.END, "AI分析中,请稍候...\n")
                tab_text.config(state=tk.DISABLED)
                threading.Thread(target=analyze, daemon=True).start()
            ttk.Button(analyze_frame, text="AI分析", command=run_analysis).pack(side=tk.LEFT, padx=2)
            # 兼容"富媒体双击后:一键分析"的叫法(实际复用同一个分析逻辑)
            ttk.Button(analyze_frame, text="一键分析", command=run_analysis).pack(side=tk.LEFT, padx=2)
            # 思维导图按钮
            def generate_mind_map():
                """生成思维导图:根据分析出的股票和相关逻辑形成思维导图"""
                content = viewer_text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showwarning("警告", "文本内容为空", parent=win)
                    return
                # 在后台线程中生成思维导图
                def generate():
                    try:
                        # 提取股票名称
                        stocks, _ = extract_stock_names(content)
                        if not stocks:
                            # 检查股票数据是否加载成功
                            global STOCK_NAMES_SET, STOCK_CODES_DICT
                            if not STOCK_NAMES_SET or not STOCK_CODES_DICT:
                                result_content = "❌ 股票数据未加载成功,无法识别股票信息。\n\n"
                                result_content += "可能原因:\n"
                                result_content += "1. 网络连接失败,无法从akshare获取股票数据\n"
                                result_content += "2. akshare库未正确安装或配置\n"
                                result_content += "3. 缓存文件不存在或已损坏\n\n"
                                result_content += "解决方案:\n"
                                result_content += "1. 检查网络连接,确保能访问互联网\n"
                                result_content += "2. 重新运行程序,让程序从网络获取并缓存股票数据\n"
                                result_content += "3. 如果持续失败,请检查防火墙设置,确保程序有网络访问权限\n"
                                result_content += "4. 首次运行需要网络连接来下载股票数据,后续会使用本地缓存\n\n"
                                result_content += f"文本长度:{len(content)} 字符\n"
                                result_content += f"文本预览:{content[:200]}..."
                            else:
                                result_content = "未在文本中找到股票信息。\n\n"
                                result_content += "提示:\n"
                                result_content += "1. 请确保文本中包含股票名称(如:贵州茅台、中国平安)或股票代码(如:600519、000001)\n"
                                result_content += "2. 股票代码应为6位数字\n"
                                result_content += "3. 可以尝试在文本中明确写出股票代码(6位数字)以提高识别率\n"
                                result_content += f"4. 当前已加载 {len(STOCK_NAMES_SET)} 个股票名称数据\n\n"
                                result_content += f"文本长度:{len(content)} 字符\n"
                                result_content += f"文本预览:{content[:200]}..."
                            def update_ui():
                                tab_text = get_or_create_tab("思维导图")
                                tab_text.config(state=tk.NORMAL)
                                tab_text.delete("1.0", tk.END)
                                tab_text.insert(tk.END, result_content)
                                tab_text.config(state=tk.DISABLED)
                            if hasattr(self, "root") and self.root.winfo_exists():
                                self.root.after(0, update_ui)
                            return
                        # 获取每个股票的逻辑
                        stock_logics = {}
                        for stock_item in stocks:
                            # 处理股票名称(可能是"代码(名称)"格式)
                            stock_name = stock_item
                            if '(' in stock_item and ')' in stock_item:
                                stock_name = stock_item.split('(')[1].rstrip(')')
                            # 从文本中提取该股票的相关逻辑
                            try:
                                # 查找股票在文本中的上下文
                                stock_code = get_stock_code_by_name(stock_name)
                                if stock_code:
                                    # 从数据库获取逻辑
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
                                        stock_logics[stock_name] = str(row[0])[:500]
                                    else:
                                        # 从文本中提取上下文
                                        import re
                                        pattern = re.compile(rf'.{{0,200}}{re.escape(stock_name)}.{{0,200}}', re.DOTALL)
                                        matches = pattern.findall(content)
                                        if matches:
                                            stock_logics[stock_name] = ' '.join(matches[:3])[:500]
                                        else:
                                            stock_logics[stock_name] = "未找到相关逻辑"
                                    conn.close()
                                else:
                                    stock_logics[stock_name] = "未找到股票代码"
                            except Exception as e:
                                stock_logics[stock_name] = f"获取逻辑失败: {e!s}"
                        # 获取每只股票最近5天大单资金流与最近5日涨跌幅(供思维导图展示)
                        stock_flow_5d = {}
                        stock_pct_5d = {}
                        for stock_item in stocks[:20]:
                            name = stock_item.split('(')[1].rstrip(')') if '(' in stock_item and ')' in stock_item else stock_item
                            code = get_stock_code_by_name(name)
                            if code:
                                stock_flow_5d[name] = self._get_stock_5day_flow_summary(code)
                                time.sleep(0.1)
                                stock_pct_5d[name] = self._get_stock_5day_pct_change(code)
                            else:
                                stock_flow_5d[name] = "最近5天资金流: 无代码"
                                stock_pct_5d[name] = "最近5日涨跌幅: 无代码"
                            time.sleep(0.15)  # 避免请求过快
                        # 归类的板块:按所处行业分组,并获取近3日资金流与前5龙头股
                        def _name(s):
                            return s.split('(')[1].rstrip(')') if '(' in s and ')' in s else s
                        sector_to_stocks = {}
                        for s in stocks[:20]:
                            name = _name(s)
                            sector = get_stock_sector(name)
                            if sector not in sector_to_stocks:
                                sector_to_stocks[sector] = []
                            sector_to_stocks[sector].append(name)
                            time.sleep(0.05)
                        sector_info_list = []
                        for sector in sector_to_stocks:
                            flow_3d = self._get_sector_3day_flow(sector)
                            leaders = self._get_sector_top5_leaders(sector)
                            leaders_str = "; ".join([f"{n}({c}) {p}" for n, c, p in leaders]) if leaders else "暂无"
                            sector_info_list.append((sector, flow_3d, leaders_str))
                            time.sleep(0.2)
                        sector_section_lines = []
                        for sector, flow_3d, leaders_str in sector_info_list:
                            sector_section_lines.append(f"● {sector}\n  近3日资金流入流出: {flow_3d}\n  前5龙头股: {leaders_str}")
                        sector_section_text = chr(10).join(sector_section_lines) if sector_section_lines else "(未获取到板块归类或数据)"
                        sector_prompt_block = chr(10).join([f"- 板块【{s}】: 近3日资金流 {f} | 前5龙头: {l}" for s, f, l in sector_info_list]) if sector_info_list else "无"
                        # 使用AI生成思维导图结构
                        system_prompt = "你是一个专业的思维导图设计专家,能够根据股票信息和相关逻辑,生成结构化的思维导图。"
                        flow_lines = chr(10).join([f"- {s}: {stock_logics.get(_name(s), '无逻辑')} | {stock_flow_5d.get(_name(s), '')} | {stock_pct_5d.get(_name(s), '')}" for s in stocks[:20]])
                        user_prompt = f"""请根据以下股票信息、相关逻辑、最近5天大单资金流、最近5日涨跌幅,以及归类的板块(含近3日资金流入流出、前5龙头股),生成一个思维导图结构。
股票列表(含逻辑、最近5天大单资金流、最近5日涨跌幅):
{flow_lines}
归类的板块(近3日资金流入流出、前5龙头股):
{sector_prompt_block}
文本内容摘要:
{content[:2000]}
请生成思维导图,格式要求:
1. 中心主题:文本核心内容
2. 主要分支:可按板块归类,再按股票展开;每个板块下包含:近3日资金流入流出、前5龙头股、以及该板块下的个股
3. 每个股票分支下包含:股票名称、相关逻辑、关键信息、最近5天大单资金流、最近5日涨跌幅(若已提供)
4. 使用层级结构,用缩进表示层级关系
5. 使用符号(如:●、○、■、□)标记不同层级
思维导图格式示例:
中心主题
├─ 分支1
│  ├─ 子分支1.1
│  └─ 子分支1.2
└─ 分支2
   ├─ 子分支2.1
   └─ 子分支2.2"""
                        ai_result = self.call_ai_model(user_prompt, system_prompt)
                        if not ai_result:
                            ai_result = "未获取到AI分析结果,请检查配置。"
                        # 组合结果
                        from datetime import datetime
                        result_content = f"""【思维导图分析结果】
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*100}
【提取的股票信息】
{chr(10).join([f"{i+1}. {stock}" for i, stock in enumerate(stocks[:20])])}
{'='*100}
【股票逻辑详情】
{chr(10).join([f"● {stock}: {logic}" for stock, logic in list(stock_logics.items())[:20]])}
{'='*100}
【最近5天大单资金流】
{chr(10).join([f"● {stock}: {stock_flow_5d.get(stock, '暂无')}" for stock in list(stock_logics.keys())[:20]])}
{'='*100}
【最近5日涨跌幅】
{chr(10).join([f"● {stock}: {stock_pct_5d.get(stock, '暂无')}" for stock in list(stock_logics.keys())[:20]])}
{'='*100}
【归类的板块】(近3日资金流入流出 + 前5龙头股)
{sector_section_text}
{'='*100}
【AI生成的思维导图结构】
{ai_result}
{'='*100}
"""
                        def update_ui():
                            tab_text = get_or_create_tab("思维导图")
                            tab_text.config(state=tk.NORMAL)
                            tab_text.delete("1.0", tk.END)
                            tab_text.insert(tk.END, result_content)
                            tab_text.config(state=tk.DISABLED)
                            tab_text.see("1.0")
                        if hasattr(self, "root") and self.root.winfo_exists():
                            self.root.after(0, update_ui)
                    except Exception as e:
                        import traceback
                        error_msg = f"生成思维导图失败: {e!s}\n{traceback.format_exc()}"
                        def update_ui():
                            tab_text = get_or_create_tab("思维导图")
                            tab_text.config(state=tk.NORMAL)
                            tab_text.delete("1.0", tk.END)
                            tab_text.insert(tk.END, error_msg)
                            tab_text.config(state=tk.DISABLED)
                        if hasattr(self, "root") and self.root.winfo_exists():
                            self.root.after(0, update_ui)
                # 显示处理中
                tab_text = get_or_create_tab("思维导图")
                tab_text.config(state=tk.NORMAL)
                tab_text.delete("1.0", tk.END)
                tab_text.insert(tk.END, "正在生成思维导图,请稍候...\n")
                tab_text.config(state=tk.DISABLED)
                threading.Thread(target=generate, daemon=True).start()
            ttk.Button(analyze_frame, text="思维导图", command=generate_mind_map).pack(side=tk.LEFT, padx=2)
            # 逻辑表格按钮
            def generate_logic_table():
                """生成逻辑表格:统计股票的逻辑信息"""
                content = viewer_text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showwarning("警告", "文本内容为空", parent=win)
                    return
                # 在后台线程中生成逻辑表格
                def generate():
                    try:
                        # 提取股票名称
                        stocks, _ = extract_stock_names(content)
                        if not stocks:
                            # 检查股票数据是否加载成功
                            global STOCK_NAMES_SET, STOCK_CODES_DICT
                            if not STOCK_NAMES_SET or not STOCK_CODES_DICT:
                                result_content = "❌ 股票数据未加载成功,无法识别股票信息。\n\n"
                                result_content += "可能原因:\n"
                                result_content += "1. 网络连接失败,无法从akshare获取股票数据\n"
                                result_content += "2. akshare库未正确安装或配置\n"
                                result_content += "3. 缓存文件不存在或已损坏\n\n"
                                result_content += "解决方案:\n"
                                result_content += "1. 检查网络连接,确保能访问互联网\n"
                                result_content += "2. 重新运行程序,让程序从网络获取并缓存股票数据\n"
                                result_content += "3. 如果持续失败,请检查防火墙设置,确保程序有网络访问权限\n"
                                result_content += "4. 首次运行需要网络连接来下载股票数据,后续会使用本地缓存\n\n"
                                result_content += f"文本长度:{len(content)} 字符\n"
                                result_content += f"文本预览:{content[:200]}..."
                            else:
                                result_content = "未在文本中找到股票信息。\n\n"
                                result_content += "提示:\n"
                                result_content += "1. 请确保文本中包含股票名称(如:贵州茅台、中国平安)或股票代码(如:600519、000001)\n"
                                result_content += "2. 股票代码应为6位数字\n"
                                result_content += "3. 可以尝试在文本中明确写出股票代码(6位数字)以提高识别率\n"
                                result_content += f"4. 当前已加载 {len(STOCK_NAMES_SET)} 个股票名称数据\n\n"
                                result_content += f"文本长度:{len(content)} 字符\n"
                                result_content += f"文本预览:{content[:200]}..."
                            def update_ui():
                                tab_text = get_or_create_tab("逻辑表格")
                                tab_text.config(state=tk.NORMAL)
                                tab_text.delete("1.0", tk.END)
                                tab_text.insert(tk.END, result_content)
                                tab_text.config(state=tk.DISABLED)
                            if hasattr(self, "root") and self.root.winfo_exists():
                                self.root.after(0, update_ui)
                            return
                        # 准备表格数据
                        table_data = []
                        for stock_item in stocks[:50]:  # 限制最多50只股票
                            # 处理股票名称(可能是"代码(名称)"格式)
                            stock_name = stock_item
                            if '(' in stock_item and ')' in stock_item:
                                stock_name = stock_item.split('(')[1].rstrip(')')
                            stock_code = get_stock_code_by_name(stock_name)
                            # 初始化数据
                            row_data = {
                                '股票名': stock_name,
                                '股票代码': stock_code or '未找到',
                                '逻辑概念文字': '',
                                '所属板块': '',
                                '主线': '',
                                '事件驱动原因': '',
                                '所属概念': '',
                                '5天内涨停次数': 0,
                                '最近涨跌幅': '',
                                '20日涨跌幅': ''
                            }
                            if stock_code:
                                try:
                                    # 1. 获取逻辑概念文字(从数据库)
                                    conn = sqlite3.connect(DB_PATH)
                                    cursor = conn.cursor()
                                    cursor.execute('''
                                        SELECT logic FROM stock_logic
                                        WHERE stock_name = ?
                                        ORDER BY created_at DESC
                                        LIMIT 1
                                    ''', (stock_name,))
                                    logic_row = cursor.fetchone()
                                    if logic_row and logic_row[0]:
                                        row_data['逻辑概念文字'] = str(logic_row[0])[:200]  # 限制长度
                                    # 2. 获取所属板块
                                    try:
                                        if AKSHARE_AVAILABLE:
                                            individual_info = ak.stock_individual_info_em(symbol=stock_code)
                                            if not individual_info.empty:
                                                for _, info_row in individual_info.iterrows():
                                                    if info_row['item'] == '所处行业':
                                                        row_data['所属板块'] = str(info_row['value'])
                                                    elif info_row['item'] == '所属概念':
                                                        row_data['所属概念'] = str(info_row['value'])
                                    except:
                                        pass
                                    # 3. 获取实时涨跌幅
                                    try:
                                        spot_row = get_realtime_spot_row(stock_code, cache_duration=60)
                                        if spot_row is not None:
                                            change_pct = spot_row.get('涨跌幅')
                                            if change_pct is not None:
                                                row_data['最近涨跌幅'] = f"{float(change_pct):+.2f}%"
                                    except:
                                        pass
                                    # 4. 获取历史数据计算20日涨跌幅和5天内涨停次数
                                    try:
                                        if AKSHARE_AVAILABLE:
                                            hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                                            if not hist_data.empty and len(hist_data) >= 20:
                                                # 计算20日涨跌幅
                                                if len(hist_data) >= 20:
                                                    price_20d_ago = float(hist_data.iloc[-20]['收盘'])
                                                    price_current = float(hist_data.iloc[-1]['收盘'])
                                                    change_20d = ((price_current - price_20d_ago) / price_20d_ago) * 100
                                                    row_data['20日涨跌幅'] = f"{change_20d:+.2f}%"
                                                # 计算5天内涨停次数
                                                recent_5days = hist_data.tail(5)
                                                limit_up_count = 0
                                                for _, day_row in recent_5days.iterrows():
                                                    change_pct = float(day_row.get('涨跌幅', 0))
                                                    if change_pct >= 9.8:  # 涨停判断(考虑误差)
                                                        limit_up_count += 1
                                                row_data['5天内涨停次数'] = limit_up_count
                                                # 如果没有实时数据,使用最近交易日数据
                                                if not row_data['最近涨跌幅']:
                                                    latest_change = float(hist_data.iloc[-1].get('涨跌幅', 0))
                                                    row_data['最近涨跌幅'] = f"{latest_change:+.2f}%"
                                    except Exception as e:
                                        print(f"获取 {stock_name} 历史数据失败: {e}")
                                    conn.close()
                                except Exception as e:
                                    print(f"处理 {stock_name} 数据失败: {e}")
                            # 从文本中提取事件驱动原因和主线(简单提取包含股票名的句子)
                            try:
                                import re
                                pattern = re.compile(rf'.{{0,100}}{re.escape(stock_name)}.{{0,100}}', re.DOTALL)
                                matches = pattern.findall(content)
                                if matches:
                                    # 提取包含关键词的句子作为事件驱动原因
                                    event_keywords = ['因为', '由于', '原因', '驱动', '利好', '利空', '事件', '公告', '政策']
                                    for match in matches[:3]:
                                        for keyword in event_keywords:
                                            if keyword in match:
                                                row_data['事件驱动原因'] = match[:150].strip()
                                                break
                                        if row_data['事件驱动原因']:
                                            break
                                    # 提取主线信息(查找主线相关关键词)
                                    mainline_keywords = ['主线', '主题', '热点', '概念', '题材', '板块']
                                    mainline_concepts = ['人工智能', 'AI', '新能源', '光伏', '风电', '储能', '芯片', '半导体',
                                                       '医药', '生物', '消费', '科技', '金融', '地产', '军工', '农业',
                                                       '环保', '碳中和', '5G', '物联网', '云计算', '大数据', '区块链']
                                    for match in matches[:5]:
                                        # 查找主线关键词
                                        for keyword in mainline_keywords:
                                            if keyword in match:
                                                # 提取主线关键词附近的文本
                                                idx = match.find(keyword)
                                                mainline_text = match[max(0, idx-20):idx+50]
                                                if mainline_text.strip():
                                                    row_data['主线'] = mainline_text[:50].strip()
                                                    break
                                        # 查找概念关键词
                                        if not row_data['主线']:
                                            for concept in mainline_concepts:
                                                if concept in match:
                                                    row_data['主线'] = concept
                                                    break
                                        if row_data['主线']:
                                            break
                            except:
                                pass
                            table_data.append(row_data)
                        # 生成表格文本
                        from datetime import datetime
                        result_content = f"""【逻辑表格统计结果】
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
统计股票数量: {len(table_data)}
{'='*150}
"""
                        # 表头
                        headers = ['股票名', '股票代码', '逻辑概念文字', '所属板块', '主线', '事件驱动原因',
                                  '所属概念', '5天内涨停次数', '最近涨跌幅', '20日涨跌幅']
                        col_widths = [12, 10, 30, 15, 10, 25, 20, 8, 12, 12]
                        # 打印表头
                        header_line = " | ".join([f"{h:<{w}}" for h, w in zip(headers, col_widths)])
                        result_content += header_line + "\n"
                        result_content += "-" * len(header_line) + "\n"
                        # 打印数据行
                        for row in table_data:
                            data_line = " | ".join([
                                f"{str(row.get(h, '')).replace(chr(10), ' ').replace(chr(13), '')[:w]:<{w}}"
                                for h, w in zip(headers, col_widths)
                            ])
                            result_content += data_line + "\n"
                        result_content += f"\n{'='*150}\n"
                        def update_ui():
                            tab_text = get_or_create_tab("逻辑表格")
                            tab_text.config(state=tk.NORMAL)
                            tab_text.delete("1.0", tk.END)
                            tab_text.insert(tk.END, result_content)
                            tab_text.config(state=tk.DISABLED)
                            tab_text.see("1.0")
                        if hasattr(self, "root") and self.root.winfo_exists():
                            self.root.after(0, update_ui)
                    except Exception as e:
                        import traceback
                        error_msg = f"生成逻辑表格失败: {e!s}\n{traceback.format_exc()}"
                        def update_ui():
                            tab_text = get_or_create_tab("逻辑表格")
                            tab_text.config(state=tk.NORMAL)
                            tab_text.delete("1.0", tk.END)
                            tab_text.insert(tk.END, error_msg)
                            tab_text.config(state=tk.DISABLED)
                        if hasattr(self, "root") and self.root.winfo_exists():
                            self.root.after(0, update_ui)
                # 显示处理中
                tab_text = get_or_create_tab("逻辑表格")
                tab_text.config(state=tk.NORMAL)
                tab_text.delete("1.0", tk.END)
                tab_text.insert(tk.END, "正在生成逻辑表格,请稍候...\n")
                tab_text.config(state=tk.DISABLED)
                threading.Thread(target=generate, daemon=True).start()
            ttk.Button(analyze_frame, text="逻辑表格", command=generate_logic_table).pack(side=tk.LEFT, padx=2)
            # 多维度高级图表分析按钮
            def generate_advanced_charts():
                """生成多维度高级图表分析:包括股票提及频率、情绪分布、主题分析、风险等级等多维度可视化"""
                content = viewer_text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showwarning("警告", "文本内容为空", parent=win)
                    return
                # 在后台线程中生成图表
                def generate():
                    try:
                        import matplotlib.pyplot as plt
                        import numpy as np
                        from matplotlib.backends.backend_tkagg import (
                            FigureCanvasTkAgg,
                        )
                        from matplotlib.figure import Figure
                        # 提取股票名称
                        stocks, _ = extract_stock_names(content)
                        # 多维度文本分析
                        dimension_analysis = analyze_text_dimensions(content)
                        # 词频分析
                        words = jieba.lcut(content)
                        stop_words = ['的', '了', '是', '在', '有', '和', '就', '不', '人', '都',
                                     '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你',
                                     '会', '着', '没有', '看', '好', '自己', '这']
                        word_freq = Counter([w for w in words if len(w) > 1 and w not in stop_words])
                        top_words = dict(word_freq.most_common(10))
                        # 股票提及频率统计
                        stock_mentions = {}
                        for stock_item in stocks[:20]:  # 限制最多20只股票
                            stock_name = stock_item
                            if '(' in stock_item and ')' in stock_item:
                                stock_name = stock_item.split('(')[1].rstrip(')')
                            # 统计提及次数
                            mention_count = content.count(stock_name)
                            if mention_count > 0:
                                stock_mentions[stock_name] = mention_count
                        # 按提及次数排序
                        sorted_stocks = sorted(stock_mentions.items(), key=lambda x: x[1], reverse=True)[:10]
                        def update_ui():
                            # 如果已存在同名的文本标签页,先删除它
                            if "多维度图表分析" in result_tabs:
                                try:
                                    for i in range(result_notebook.index("end")):
                                        if result_notebook.tab(i, "text") == "多维度图表分析":
                                            result_notebook.forget(i)
                                            break
                                except:
                                    pass
                                del result_tabs["多维度图表分析"]
                            # 创建图表标签页
                            chart_tab_frame = ttk.Frame(result_notebook)
                            result_notebook.add(chart_tab_frame, text="多维度图表分析")
                            # 创建滚动框架
                            from tkinter import Canvas, Scrollbar
                            chart_canvas = Canvas(chart_tab_frame)
                            scrollbar = Scrollbar(chart_tab_frame, orient="vertical", command=chart_canvas.yview)
                            scrollable_frame = ttk.Frame(chart_canvas)
                            scrollable_frame.bind(
                                "<Configure>",
                                lambda e: chart_canvas.configure(scrollregion=chart_canvas.bbox("all"))
                            )
                            chart_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
                            chart_canvas.configure(yscrollcommand=scrollbar.set)
                            chart_canvas.pack(side="left", fill="both", expand=True)
                            scrollbar.pack(side="right", fill="y")
                            # 切换到图表标签页(查找刚添加的标签页)
                            for i in range(result_notebook.index("end")):
                                if result_notebook.tab(i, "text") == "多维度图表分析":
                                    result_notebook.select(i)
                                    break
                            # 图表1: 股票提及频率柱状图
                            if sorted_stocks:
                                fig1 = Figure(figsize=(10, 4), dpi=100)
                                ax1 = fig1.add_subplot(111)
                                stock_names = [s[0] for s in sorted_stocks]
                                mention_counts = [s[1] for s in sorted_stocks]
                                colors = plt.cm.viridis(np.linspace(0, 1, len(stock_names)))
                                bars = ax1.barh(stock_names, mention_counts, color=colors)
                                ax1.set_xlabel('提及次数', fontsize=10)
                                ax1.set_title('股票提及频率分析', fontsize=12, fontweight='bold')
                                ax1.grid(axis='x', alpha=0.3)
                                # 添加数值标签
                                for i, (name, count) in enumerate(sorted_stocks):
                                    ax1.text(count + 0.1, i, str(count), va='center', fontsize=9)
                                fig1.tight_layout()
                                chart_frame1 = ttk.LabelFrame(scrollable_frame, text="图表1: 股票提及频率", padding=10)
                                chart_frame1.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                                canvas1 = FigureCanvasTkAgg(fig1, master=chart_frame1)
                                canvas1.draw()
                                canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                            # 图表2: 情绪分布饼图
                            if dimension_analysis and dimension_analysis.get('sentiment_details'):
                                fig2 = Figure(figsize=(8, 6), dpi=100)
                                ax2 = fig2.add_subplot(111)
                                sentiment_details = dimension_analysis['sentiment_details']
                                labels = ['积极', '消极', '中性']
                                sizes = [
                                    sentiment_details.get('positive', 0),
                                    sentiment_details.get('negative', 0),
                                    sentiment_details.get('neutral', 0)
                                ]
                                # 过滤掉为0的项
                                filtered_data = [(l, s) for l, s in zip(labels, sizes) if s > 0]
                                if filtered_data:
                                    labels, sizes = zip(*filtered_data)
                                    colors_pie = ['#4CAF50', '#F44336', '#FFC107']
                                    ax2.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors_pie[:len(sizes)])
                                    ax2.set_title('情绪分布分析', fontsize=12, fontweight='bold')
                                fig2.tight_layout()
                                chart_frame2 = ttk.LabelFrame(scrollable_frame, text="图表2: 情绪分布", padding=10)
                                chart_frame2.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                                canvas2 = FigureCanvasTkAgg(fig2, master=chart_frame2)
                                canvas2.draw()
                                canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                            # 图表3: 热门主题词云柱状图
                            if dimension_analysis and dimension_analysis.get('hot_themes'):
                                fig3 = Figure(figsize=(10, 5), dpi=100)
                                ax3 = fig3.add_subplot(111)
                                themes = dimension_analysis['hot_themes']
                                if themes:
                                    theme_names = [t[0] for t in themes]
                                    theme_counts = [t[1] for t in themes]
                                    colors_bar = plt.cm.Set3(np.linspace(0, 1, len(theme_names)))
                                    bars = ax3.bar(theme_names, theme_counts, color=colors_bar)
                                    ax3.set_xlabel('热门主题', fontsize=10)
                                    ax3.set_ylabel('提及次数', fontsize=10)
                                    ax3.set_title('热门主题分析', fontsize=12, fontweight='bold')
                                    ax3.tick_params(axis='x', rotation=45)
                                    ax3.grid(axis='y', alpha=0.3)
                                    # 添加数值标签
                                    for bar in bars:
                                        height = bar.get_height()
                                        ax3.text(bar.get_x() + bar.get_width()/2., height,
                                                f'{int(height)}', ha='center', va='bottom', fontsize=9)
                                fig3.tight_layout()
                                chart_frame3 = ttk.LabelFrame(scrollable_frame, text="图表3: 热门主题分析", padding=10)
                                chart_frame3.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                                canvas3 = FigureCanvasTkAgg(fig3, master=chart_frame3)
                                canvas3.draw()
                                canvas3.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                            # 图表4: 关键词词频柱状图
                            if top_words:
                                fig4 = Figure(figsize=(10, 5), dpi=100)
                                ax4 = fig4.add_subplot(111)
                                word_names = list(top_words.keys())
                                word_counts = list(top_words.values())
                                colors_word = plt.cm.coolwarm(np.linspace(0, 1, len(word_names)))
                                bars = ax4.barh(word_names, word_counts, color=colors_word)
                                ax4.set_xlabel('出现次数', fontsize=10)
                                ax4.set_title('关键词词频分析', fontsize=12, fontweight='bold')
                                ax4.grid(axis='x', alpha=0.3)
                                # 添加数值标签
                                for i, (name, count) in enumerate(zip(word_names, word_counts)):
                                    ax4.text(count + 0.1, i, str(count), va='center', fontsize=9)
                                fig4.tight_layout()
                                chart_frame4 = ttk.LabelFrame(scrollable_frame, text="图表4: 关键词词频", padding=10)
                                chart_frame4.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                                canvas4 = FigureCanvasTkAgg(fig4, master=chart_frame4)
                                canvas4.draw()
                                canvas4.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                            # 图表5: 风险等级与市场焦点雷达图(简化版柱状图)
                            if dimension_analysis:
                                fig5 = Figure(figsize=(10, 5), dpi=100)
                                ax5 = fig5.add_subplot(111)
                                metrics = []
                                values = []
                                # 风险等级转换为数值
                                risk_level = dimension_analysis.get('risk_level', 'low')
                                risk_values = {'high': 3, 'medium': 2, 'low': 1}
                                metrics.append('风险等级')
                                values.append(risk_values.get(risk_level, 1))
                                # 市场焦点
                                market_focus = dimension_analysis.get('market_focus_count', 0)
                                metrics.append('市场焦点')
                                values.append(min(market_focus, 10))  # 限制最大值
                                # 情绪强度
                                sentiment_details = dimension_analysis.get('sentiment_details', {})
                                total_sentiment = sum(sentiment_details.values())
                                metrics.append('情绪强度')
                                values.append(min(total_sentiment, 20))
                                # 主题热度
                                hot_themes = dimension_analysis.get('hot_themes', [])
                                theme_total = sum([t[1] for t in hot_themes])
                                metrics.append('主题热度')
                                values.append(min(theme_total, 15))
                                if metrics:
                                    colors_radar = plt.cm.RdYlGn(np.linspace(0.3, 0.7, len(metrics)))
                                    bars = ax5.bar(metrics, values, color=colors_radar)
                                    ax5.set_ylabel('强度值', fontsize=10)
                                    ax5.set_title('多维度综合分析', fontsize=12, fontweight='bold')
                                    ax5.grid(axis='y', alpha=0.3)
                                    # 添加数值标签
                                    for bar in bars:
                                        height = bar.get_height()
                                        ax5.text(bar.get_x() + bar.get_width()/2., height,
                                                f'{int(height)}', ha='center', va='bottom', fontsize=9)
                                fig5.tight_layout()
                                chart_frame5 = ttk.LabelFrame(scrollable_frame, text="图表5: 多维度综合分析", padding=10)
                                chart_frame5.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                                canvas5 = FigureCanvasTkAgg(fig5, master=chart_frame5)
                                canvas5.draw()
                                canvas5.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                            # 添加分析摘要文本
                            summary_frame = ttk.LabelFrame(scrollable_frame, text="分析摘要", padding=10)
                            summary_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)
                            summary_text = scrolledtext.ScrolledText(summary_frame, wrap=tk.WORD, height=8, font=("TkDefaultFont", 12))
                            summary_text.pack(fill=tk.BOTH, expand=True)
                            summary_content = f"""【多维度图表分析摘要】
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}
【股票分析】
识别股票数量: {len(stocks)}
重点提及股票: {', '.join([s[0] for s in sorted_stocks[:5]]) if sorted_stocks else '无'}
"""
                            if dimension_analysis:
                                summary_content += f"""【情绪分析】
整体情绪: {dimension_analysis.get('sentiment', '未知')}
积极词汇: {dimension_analysis.get('sentiment_details', {}).get('positive', 0)} 个
消极词汇: {dimension_analysis.get('sentiment_details', {}).get('negative', 0)} 个
中性词汇: {dimension_analysis.get('sentiment_details', {}).get('neutral', 0)} 个
【市场分析】
市场状况: {dimension_analysis.get('market_status', '未知')}
市场焦点: {'是' if dimension_analysis.get('market_focus', False) else '否'} (关键词出现 {dimension_analysis.get('market_focus_count', 0)} 次)
风险等级: {dimension_analysis.get('risk_level', '未知')} (风险关键词出现 {dimension_analysis.get('risk_count', 0)} 次)
"""
                                if dimension_analysis.get('hot_themes'):
                                    summary_content += f"""【热门主题】
{chr(10).join([f"  • {theme[0]}: 提及 {theme[1]} 次" for theme in dimension_analysis['hot_themes']])}
"""
                            summary_content += f"""【关键词分析】
高频关键词: {', '.join(list(top_words.keys())[:10]) if top_words else '无'}
{'='*80}
"""
                            summary_text.insert("1.0", summary_content)
                            summary_text.config(state=tk.DISABLED)
                            # 更新canvas滚动区域
                            scrollable_frame.update_idletasks()
                            chart_canvas.configure(scrollregion=chart_canvas.bbox("all"))
                            # 存储图表标签页信息
                            result_tabs["多维度图表分析"] = {
                                'frame': chart_tab_frame,
                                'text': None  # 图表标签页没有文本控件
                            }
                        if hasattr(self, "root") and self.root.winfo_exists():
                            self.root.after(0, update_ui)
                    except Exception as e:
                        import traceback
                        error_msg = f"生成多维度图表分析失败: {e!s}\n{traceback.format_exc()}"
                        def update_ui_error():
                            # 如果图表标签页已存在但text为None,使用错误标签页
                            if "多维度图表分析" in result_tabs and result_tabs["多维度图表分析"].get('text') is None:
                                # 删除图表标签页,创建文本标签页显示错误
                                try:
                                    for i in range(result_notebook.index("end")):
                                        if result_notebook.tab(i, "text") == "多维度图表分析":
                                            result_notebook.forget(i)
                                            break
                                except:
                                    pass
                                del result_tabs["多维度图表分析"]
                            tab_text = get_or_create_tab("多维度图表分析-错误")
                            tab_text.config(state=tk.NORMAL)
                            tab_text.delete("1.0", tk.END)
                            tab_text.insert(tk.END, error_msg)
                            tab_text.config(state=tk.DISABLED)
                        if hasattr(self, "root") and self.root.winfo_exists():
                            self.root.after(0, update_ui_error)
                # 显示处理中
                tab_text = get_or_create_tab("多维度图表分析")
                tab_text.config(state=tk.NORMAL)
                tab_text.delete("1.0", tk.END)
                tab_text.insert(tk.END, "正在生成多维度图表分析,请稍候...\n")
                tab_text.config(state=tk.DISABLED)
                threading.Thread(target=generate, daemon=True).start()
            ttk.Button(analyze_frame, text="多维度图表", command=generate_advanced_charts).pack(side=tk.LEFT, padx=2)
            # 保存到资讯按钮
            def save_to_news():
                """保存右侧当前标签页内容到资讯数据库"""
                try:
                    # 获取当前选中的标签页
                    current_tab_index = result_notebook.index(result_notebook.select())
                    current_tab_name = result_notebook.tab(current_tab_index, "text")
                    # 获取当前标签页的文本内容
                    if current_tab_name in result_tabs:
                        tab_text = result_tabs[current_tab_name]['text']
                        content = tab_text.get("1.0", tk.END).strip()
                        if not content:
                            messagebox.showwarning("警告", "当前标签页内容为空", parent=win)
                            return
                        # 自动生成标签页名称:当前标签页名字+时间
                        from datetime import datetime
                        time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                        tab_name = f"{current_tab_name}_{time_str}"
                        # 保存到数据库
                        if save_news_info_to_db(tab_name, content):
                            messagebox.showinfo("成功", f"内容已保存到资讯数据库: {tab_name}", parent=win)
                        else:
                            messagebox.showerror("错误", "保存失败,请检查数据库连接", parent=win)
                    else:
                        messagebox.showwarning("警告", "未找到当前标签页", parent=win)
                except Exception as e:
                    messagebox.showerror("错误", f"保存失败: {e}", parent=win)
            ttk.Button(analyze_frame, text="保存到资讯", command=save_to_news).pack(side=tk.LEFT, padx=2)
            # 一键保存按钮
            def save_all_tabs_to_news():
                """一键保存右侧所有标签页内容到资讯数据库"""
                try:
                    if not result_tabs:
                        messagebox.showwarning("警告", "没有可保存的标签页", parent=win)
                        return
                    from datetime import datetime
                    saved_count = 0
                    failed_count = 0
                    failed_tabs = []
                    # 遍历所有标签页
                    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    tab_index = 0
                    for tab_name, tab_info in result_tabs.items():
                        try:
                            tab_text = tab_info['text']
                            content = tab_text.get("1.0", tk.END).strip()
                            if not content:
                                continue  # 跳过空标签页
                            tab_index += 1
                            # 生成保存名称:标签页名字+时间+序号,避免重名
                            save_tab_name = f"{tab_name}_{time_str}_{tab_index:02d}"
                            # 保存到数据库
                            if save_news_info_to_db(save_tab_name, content):
                                saved_count += 1
                            else:
                                failed_count += 1
                                failed_tabs.append(tab_name)
                        except Exception as e:
                            failed_count += 1
                            failed_tabs.append(tab_name)
                            print(f"保存标签页 {tab_name} 失败: {e}")
                    # 显示保存结果
                    if saved_count > 0 and failed_count == 0:
                        messagebox.showinfo("成功", f"已成功保存 {saved_count} 个标签页到资讯数据库", parent=win)
                    elif saved_count > 0 and failed_count > 0:
                        messagebox.showwarning("部分成功",
                                             f"成功保存 {saved_count} 个标签页\n失败 {failed_count} 个标签页: {', '.join(failed_tabs)}",
                                             parent=win)
                    elif saved_count == 0:
                        messagebox.showwarning("警告", "没有可保存的内容(所有标签页都为空)", parent=win)
                except Exception as e:
                    messagebox.showerror("错误", f"一键保存失败: {e}", parent=win)
            ttk.Button(analyze_frame, text="一键保存", command=save_all_tabs_to_news).pack(side=tk.LEFT, padx=2)
            # 右侧分析结果区域的按钮
            # 保存成截图按钮
            def save_result_screenshot():
                """保存当前标签页为截图"""
                try:

                    from PIL import ImageGrab
                    # 获取当前选中的标签页
                    current_tab_index = result_notebook.index(result_notebook.select())
                    current_tab_name = result_notebook.tab(current_tab_index, "text")
                    # 获取当前标签页的文本控件
                    if current_tab_name in result_tabs:
                        tab_text = result_tabs[current_tab_name]['text']
                        tab_text.update_idletasks()
                        x = tab_text.winfo_rootx()
                        y = tab_text.winfo_rooty()
                        width = tab_text.winfo_width()
                        height = tab_text.winfo_height()
                        # 截图
                        screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
                        # 选择保存路径
                        from datetime import datetime
                        default_filename = f"{current_tab_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        file_path = filedialog.asksaveasfilename(
                            title="保存截图",
                            defaultextension=".png",
                            filetypes=[("PNG图片", "*.png"), ("所有文件", "*.*")],
                            initialfile=default_filename,
                            parent=win
                        )
                        if file_path:
                            screenshot.save(file_path)
                            messagebox.showinfo("成功", f"截图已保存到: {file_path}", parent=win)
                    else:
                        messagebox.showwarning("警告", "未找到当前标签页", parent=win)
                except Exception as e:
                    messagebox.showerror("错误", f"保存截图失败: {e}", parent=win)
            ttk.Button(right_button_frame, text="保存成截图", command=save_result_screenshot).pack(side=tk.LEFT, padx=2)
            # 龙头补涨分析按钮
            def analyze_dragon_stocks():
                """龙头补涨分析:分析股票中的龙头、龙一、龙二、补涨、跟风、切换等"""
                content = viewer_text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showwarning("警告", "文本内容为空", parent=win)
                    return
                # 在后台线程中分析
                def analyze():
                    try:
                        # 提取股票名称
                        stocks, _ = extract_stock_names(content)
                        if not stocks:
                            # 检查股票数据是否加载成功
                            global STOCK_NAMES_SET, STOCK_CODES_DICT
                            if not STOCK_NAMES_SET or not STOCK_CODES_DICT:
                                result_content = "❌ 股票数据未加载成功,无法识别股票信息。\n\n"
                                result_content += "可能原因:\n"
                                result_content += "1. 网络连接失败,无法从akshare获取股票数据\n"
                                result_content += "2. akshare库未正确安装或配置\n"
                                result_content += "3. 缓存文件不存在或已损坏\n\n"
                                result_content += "解决方案:\n"
                                result_content += "1. 检查网络连接,确保能访问互联网\n"
                                result_content += "2. 重新运行程序,让程序从网络获取并缓存股票数据\n"
                                result_content += "3. 如果持续失败,请检查防火墙设置,确保程序有网络访问权限\n"
                                result_content += "4. 首次运行需要网络连接来下载股票数据,后续会使用本地缓存\n\n"
                                result_content += f"文本长度:{len(content)} 字符\n"
                                result_content += f"文本预览:{content[:200]}..."
                            else:
                                result_content = "未在文本中找到股票信息。\n\n"
                                result_content += "提示:\n"
                                result_content += "1. 请确保文本中包含股票名称(如:贵州茅台、中国平安)或股票代码(如:600519、000001)\n"
                                result_content += "2. 股票代码应为6位数字\n"
                                result_content += "3. 可以尝试在文本中明确写出股票代码(6位数字)以提高识别率\n"
                                result_content += f"4. 当前已加载 {len(STOCK_NAMES_SET)} 个股票名称数据\n\n"
                                result_content += f"文本长度:{len(content)} 字符\n"
                                result_content += f"文本预览:{content[:200]}..."
                            def update_ui():
                                tab_text = get_or_create_tab("龙头补涨分析")
                                tab_text.config(state=tk.NORMAL)
                                tab_text.delete("1.0", tk.END)
                                tab_text.insert(tk.END, result_content)
                                tab_text.config(state=tk.DISABLED)
                            if hasattr(self, "root") and self.root.winfo_exists():
                                self.root.after(0, update_ui)
                            return
                        # 定义关键词
                        dragon_keywords = {
                            '龙头': ['龙头', '总龙头', '市场龙头'],
                            '龙一': ['龙一', '第一龙头', '龙头一'],
                            '龙二': ['龙二', '第二龙头', '龙头二'],
                            '补涨': ['补涨', '补涨股', '补涨逻辑'],
                            '跟风': ['跟风', '跟风股', '跟涨'],
                            '切换': ['切换', '切换股', '轮动']
                        }
                        # 分析每只股票
                        stock_analysis = []
                        for stock_item in stocks[:50]:  # 限制最多50只股票
                            stock_name = stock_item
                            if '(' in stock_item and ')' in stock_item:
                                stock_name = stock_item.split('(')[1].rstrip(')')
                            stock_code = get_stock_code_by_name(stock_name)
                            # 初始化数据
                            row_data = {
                                '股票名': stock_name,
                                '股票代码': stock_code or '未找到',
                                '角色': '',
                                '连续涨停板数': 0,
                                '当日涨跌幅': '',
                                '5日涨跌幅': '',
                                '10日涨跌幅': '',
                                '20日涨跌幅': ''
                            }
                            # 查找股票在文本中的角色
                            try:
                                import re
                                pattern = re.compile(rf'.{{0,200}}{re.escape(stock_name)}.{{0,200}}', re.DOTALL)
                                matches = pattern.findall(content)
                                roles_found = []
                                for match in matches:
                                    for role_type, keywords in dragon_keywords.items():
                                        for keyword in keywords:
                                            if keyword in match:
                                                if role_type not in roles_found:
                                                    roles_found.append(role_type)
                                if roles_found:
                                    row_data['角色'] = ', '.join(roles_found)
                            except:
                                pass
                            if stock_code:
                                try:
                                    # 获取实时涨跌幅
                                    try:
                                        spot_row = get_realtime_spot_row(stock_code, cache_duration=60)
                                        if spot_row is not None:
                                            change_pct = spot_row.get('涨跌幅')
                                            if change_pct is not None:
                                                row_data['当日涨跌幅'] = f"{float(change_pct):+.2f}%"
                                    except:
                                        pass
                                    # 获取历史数据计算涨跌幅和连续涨停板数
                                    try:
                                        if AKSHARE_AVAILABLE:
                                            hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                                            if not hist_data.empty:
                                                # 计算连续涨停板数(从最近往前数)
                                                limit_up_days = 0
                                                for i in range(len(hist_data) - 1, -1, -1):
                                                    change_pct = float(hist_data.iloc[i].get('涨跌幅', 0))
                                                    if change_pct >= 9.8:  # 涨停判断
                                                        limit_up_days += 1
                                                    else:
                                                        break
                                                row_data['连续涨停板数'] = limit_up_days
                                                # 计算5日、10日、20日涨跌幅
                                                current_price = float(hist_data.iloc[-1]['收盘'])
                                                if len(hist_data) >= 5:
                                                    price_5d_ago = float(hist_data.iloc[-5]['收盘'])
                                                    change_5d = ((current_price - price_5d_ago) / price_5d_ago) * 100
                                                    row_data['5日涨跌幅'] = f"{change_5d:+.2f}%"
                                                if len(hist_data) >= 10:
                                                    price_10d_ago = float(hist_data.iloc[-10]['收盘'])
                                                    change_10d = ((current_price - price_10d_ago) / price_10d_ago) * 100
                                                    row_data['10日涨跌幅'] = f"{change_10d:+.2f}%"
                                                if len(hist_data) >= 20:
                                                    price_20d_ago = float(hist_data.iloc[-20]['收盘'])
                                                    change_20d = ((current_price - price_20d_ago) / price_20d_ago) * 100
                                                    row_data['20日涨跌幅'] = f"{change_20d:+.2f}%"
                                                # 如果没有实时数据,使用最近交易日数据
                                                if not row_data['当日涨跌幅']:
                                                    latest_change = float(hist_data.iloc[-1].get('涨跌幅', 0))
                                                    row_data['当日涨跌幅'] = f"{latest_change:+.2f}%"
                                    except Exception as e:
                                        print(f"获取 {stock_name} 历史数据失败: {e}")
                                except Exception as e:
                                    print(f"处理 {stock_name} 数据失败: {e}")
                            stock_analysis.append(row_data)
                        # 生成分析结果文本
                        from datetime import datetime
                        result_content = f"""【龙头补涨分析结果】
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
分析股票数量: {len(stock_analysis)}
{'='*120}
"""
                        # 表头
                        headers = ['股票名', '股票代码', '角色', '连续涨停板数', '当日涨跌幅', '5日涨跌幅', '10日涨跌幅', '20日涨跌幅']
                        col_widths = [12, 10, 15, 8, 12, 12, 12, 12]
                        # 打印表头
                        header_line = " | ".join([f"{h:<{w}}" for h, w in zip(headers, col_widths)])
                        result_content += header_line + "\n"
                        result_content += "-" * len(header_line) + "\n"
                        # 按角色分类统计
                        role_stats = {}
                        for row in stock_analysis:
                            role = row.get('角色', '未分类')
                            if role:
                                if role not in role_stats:
                                    role_stats[role] = []
                                role_stats[role].append(row)
                        # 先显示有角色的股票
                        for role, stocks_in_role in role_stats.items():
                            result_content += f"\n【{role}】\n"
                            for row in stocks_in_role:
                                data_line = " | ".join([
                                    f"{str(row.get(h, '')).replace(chr(10), ' ').replace(chr(13), '')[:w]:<{w}}"
                                    for h, w in zip(headers, col_widths)
                                ])
                                result_content += data_line + "\n"
                        # 再显示未分类的股票
                        unclassified = [row for row in stock_analysis if not row.get('角色')]
                        if unclassified:
                            result_content += "\n【未分类股票】\n"
                            for row in unclassified:
                                data_line = " | ".join([
                                    f"{str(row.get(h, '')).replace(chr(10), ' ').replace(chr(13), '')[:w]:<{w}}"
                                    for h, w in zip(headers, col_widths)
                                ])
                                result_content += data_line + "\n"
                        result_content += f"\n{'='*120}\n"
                        # 统计摘要
                        result_content += "\n【统计摘要】\n"
                        result_content += f"龙头: {len([r for r in stock_analysis if '龙头' in r.get('角色', '')])} 只\n"
                        result_content += f"龙一: {len([r for r in stock_analysis if '龙一' in r.get('角色', '')])} 只\n"
                        result_content += f"龙二: {len([r for r in stock_analysis if '龙二' in r.get('角色', '')])} 只\n"
                        result_content += f"补涨: {len([r for r in stock_analysis if '补涨' in r.get('角色', '')])} 只\n"
                        result_content += f"跟风: {len([r for r in stock_analysis if '跟风' in r.get('角色', '')])} 只\n"
                        result_content += f"切换: {len([r for r in stock_analysis if '切换' in r.get('角色', '')])} 只\n"
                        result_content += f"未分类: {len(unclassified)} 只\n"
                        def update_ui():
                            tab_text = get_or_create_tab("龙头补涨分析")
                            tab_text.config(state=tk.NORMAL)
                            tab_text.delete("1.0", tk.END)
                            tab_text.insert(tk.END, result_content)
                            tab_text.config(state=tk.DISABLED)
                            tab_text.see("1.0")
                        if hasattr(self, "root") and self.root.winfo_exists():
                            self.root.after(0, update_ui)
                    except Exception as e:
                        import traceback
                        error_msg = f"龙头补涨分析失败: {e!s}\n{traceback.format_exc()}"
                        def update_ui():
                            tab_text = get_or_create_tab("龙头补涨分析")
                            tab_text.config(state=tk.NORMAL)
                            tab_text.delete("1.0", tk.END)
                            tab_text.insert(tk.END, error_msg)
                            tab_text.config(state=tk.DISABLED)
                        if hasattr(self, "root") and self.root.winfo_exists():
                            self.root.after(0, update_ui)
                # 显示处理中
                tab_text = get_or_create_tab("龙头补涨分析")
                tab_text.config(state=tk.NORMAL)
                tab_text.delete("1.0", tk.END)
                tab_text.insert(tk.END, "正在分析龙头补涨,请稍候...\n")
                tab_text.config(state=tk.DISABLED)
                threading.Thread(target=analyze, daemon=True).start()
            ttk.Button(right_button_frame, text="龙头补涨分析", command=analyze_dragon_stocks).pack(side=tk.LEFT, padx=2)
            # 一键分析按钮
            def run_all_analysis():
                """一键分析:同时执行思维导图、逻辑表格、龙头补涨分析"""
                content = viewer_text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showwarning("警告", "文本内容为空", parent=win)
                    return
                # 依次执行三个分析功能
                generate_mind_map()
                generate_logic_table()
                analyze_dragon_stocks()
            ttk.Button(right_button_frame, text="一键分析", command=run_all_analysis).pack(side=tk.LEFT, padx=2)
            # 保存到txt按钮
            def save_result_to_txt():
                """将当前分析结果标签页内容保存为 txt 文件"""
                try:
                    current_tab_index = result_notebook.index(result_notebook.select())
                    current_tab_name = result_notebook.tab(current_tab_index, "text")
                    if current_tab_name not in result_tabs:
                        messagebox.showwarning("警告", "未找到当前标签页", parent=win)
                        return
                    tab_text = result_tabs[current_tab_name]['text']
                    content = tab_text.get("1.0", tk.END).strip()
                    if not content:
                        messagebox.showwarning("警告", "当前分析结果为空,无可保存内容", parent=win)
                        return
                    from datetime import datetime
                    default_filename = f"{current_tab_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    file_path = filedialog.asksaveasfilename(
                        title="保存分析结果到 txt",
                        defaultextension=".txt",
                        filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                        initialfile=default_filename,
                        parent=win
                    )
                    if file_path:
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        messagebox.showinfo("成功", f"已保存到: {file_path}", parent=win)
                except Exception as e:
                    messagebox.showerror("错误", f"保存到 txt 失败: {e}", parent=win)
            ttk.Button(right_button_frame, text="保存到txt", command=save_result_to_txt).pack(side=tk.LEFT, padx=2)
            # 关闭按钮
            ttk.Button(toolbar, text="关闭", command=win.destroy).pack(side=tk.RIGHT, padx=5)
            # 字体变化处理
            def change_font(*args):
                try:
                    font_size = int(font_size_var.get())
                    font_family = font_family_var.get()
                    viewer_text.configure(font=(font_family, font_size))
                except:
                    pass
            font_size_var.trace('w', change_font)
            font_family_var.trace('w', change_font)
            # 底部按钮栏
            bottom_frame = ttk.Frame(win)
            bottom_frame.pack(fill=tk.X, padx=5, pady=5)
            def save_changes():
                """保存更改回原标签页"""
                new_content = viewer_text.get("1.0", tk.END)
                text_widget.delete("1.0", tk.END)
                text_widget.insert("1.0", new_content)
                messagebox.showinfo("成功", "内容已保存")
            def copy_content():
                """复制内容到剪贴板"""
                content = viewer_text.get("1.0", tk.END).strip()
                if content:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(content)
                    messagebox.showinfo("成功", "内容已复制到剪贴板")
            ttk.Button(bottom_frame, text="保存更改", command=save_changes).pack(side=tk.LEFT, padx=5)
            ttk.Button(bottom_frame, text="复制内容", command=copy_content).pack(side=tk.LEFT, padx=5)
            ttk.Button(bottom_frame, text="清空内容", command=lambda: viewer_text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=5)
            # 窗口控制按钮
            control_btn_frame = ttk.Frame(win)
            control_btn_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
            def toggle_minimize():
                """切换最小化/恢复"""
                if win._is_minimized:
                    win.geometry(win._original_geometry)
                    win._is_minimized = False
                    minimize_btn.config(text="最小化")
                else:
                    win._original_geometry = win.geometry()
                    win.geometry("200x50")
                    win._is_minimized = True
                    minimize_btn.config(text="恢复")
            def toggle_maximize():
                """切换最大化/恢复"""
                try:
                    # Windows平台使用state('zoomed')
                    if win.state() == 'zoomed':
                        win.state('normal')
                        win.geometry(win._original_geometry)
                        maximize_btn.config(text="最大化")
                    else:
                        win._original_geometry = win.geometry()
                        win.state('zoomed')
                        maximize_btn.config(text="恢复")
                except:
                    # 如果state不支持,尝试使用geometry
                    try:
                        current_geom = win.geometry()
                        if hasattr(win, '_is_maximized') and win._is_maximized:
                            win.geometry(win._original_geometry)
                            win._is_maximized = False
                            maximize_btn.config(text="最大化")
                        else:
                            win._original_geometry = current_geom
                            # 获取屏幕尺寸
                            screen_width = win.winfo_screenwidth()
                            screen_height = win.winfo_screenheight()
                            win.geometry(f"{screen_width}x{screen_height}+0+0")
                            win._is_maximized = True
                            maximize_btn.config(text="恢复")
                    except Exception as e:
                        messagebox.showinfo("提示", f"最大化功能不可用: {e}")
            minimize_btn = ttk.Button(control_btn_frame, text="最小化", command=toggle_minimize, width=10)
            minimize_btn.pack(side=tk.LEFT, padx=5)
            maximize_btn = ttk.Button(control_btn_frame, text="最大化", command=toggle_maximize, width=10)
            maximize_btn.pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="隐藏", command=win.withdraw, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="显示", command=win.deiconify, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="关闭", command=win.destroy, width=10).pack(side=tk.RIGHT, padx=5)
            # 绑定Ctrl+F快速查找
            def focus_search(event):
                search_entry.focus()
                return "break"
            viewer_text.bind('<Control-f>', focus_search)
            viewer_text.bind('<Control-F>', focus_search)
        except Exception as e:
            messagebox.showerror("错误", f"打开全窗口浏览失败: {e}")
            import traceback
            traceback.print_exc()

    def open_full_window_viewer_from_content(self, content, title="资讯内容"):
        """根据内容和标题打开全窗口浏览界面(用于资讯数据表等场景)"""
        try:
            if not content or not content.strip():
                messagebox.showwarning("警告", "内容为空,无法打开全窗口浏览", parent=self.root)
                return
            # 创建全窗口
            win = self._safe_toplevel(self.root)
            win.title(f"全窗口浏览 - {title}")
            # 获取屏幕尺寸并设置默认最大化
            screen_width = win.winfo_screenwidth()
            screen_height = win.winfo_screenheight()
            # 存储窗口状态
            win._is_maximized = True
            win._is_minimized = False
            win._original_geometry = f"{screen_width}x{screen_height}+0+0"
            # 默认最大化显示
            try:
                win.state("zoomed")  # Windows下最大化
            except:
                win.geometry(f"{screen_width}x{screen_height}+0+0")
            win.transient(self.root)
            win.resizable(True, True)
            # 配置窗口布局
            win.columnconfigure(0, weight=1)
            win.rowconfigure(1, weight=1)
            # 添加窗口控制按钮(最小化/最大化/关闭/隐藏)
            control_frame = ttk.Frame(win)
            control_frame.pack(fill=tk.X, padx=5, pady=5)
            # 最小化按钮
            def minimize():
                try:
                    win.state('normal')
                    win.iconify()
                except Exception as e:
                    try:
                        win.withdraw()
                    except:
                        print(f"最小化窗口失败: {e}")
            # 最大化/还原按钮
            max_btn_text = tk.StringVar(value="还原")
            def toggle_maximize():
                try:
                    if win._is_maximized:
                        win.state("normal")
                        win.geometry("1200x800")
                        win._is_maximized = False
                        max_btn_text.set("最大化")
                    else:
                        win._last_geometry = win.geometry()
                        win.state("zoomed")
                        win._is_maximized = True
                        max_btn_text.set("还原")
                except Exception:
                    # 如果zoomed不可用,手动设置全屏
                    if win._is_maximized:
                        win.geometry("1200x800")
                        win._is_maximized = False
                        max_btn_text.set("最大化")
                    else:
                        win._last_geometry = win.geometry()
                        win.geometry(f"{screen_width}x{screen_height}+0+0")
                        win._is_maximized = True
                        max_btn_text.set("还原")
            # 隐藏按钮
            def hide_window():
                try:
                    win.withdraw()
                except Exception as e:
                    print(f"隐藏窗口失败: {e}")
            # 窗口控制按钮布局
            control_btn_frame = ttk.Frame(control_frame)
            control_btn_frame.pack(side=tk.RIGHT, padx=5)
            max_btn = ttk.Button(control_btn_frame, textvariable=max_btn_text, command=toggle_maximize, width=10)
            max_btn.pack(side=tk.LEFT, padx=2)
            ttk.Button(control_btn_frame, text="最小化", command=minimize, width=10).pack(side=tk.LEFT, padx=2)
            ttk.Button(control_btn_frame, text="隐藏", command=hide_window, width=10).pack(side=tk.LEFT, padx=2)
            ttk.Button(control_btn_frame, text="关闭", command=win.destroy, width=10).pack(side=tk.LEFT, padx=2)
            # 标题标签
            title_label = ttk.Label(control_frame, text=title, font=("TkDefaultFont", 12, "bold"))
            title_label.pack(side=tk.LEFT, padx=10)
            # 字体控制工具栏
            font_toolbar = ttk.Frame(win)
            font_toolbar.pack(fill=tk.X, padx=5, pady=(0, 5))
            font_frame = ttk.LabelFrame(font_toolbar, text="字体", padding=5)
            font_frame.pack(side=tk.LEFT, padx=5)
            ttk.Label(font_frame, text="大小:").pack(side=tk.LEFT, padx=2)
            font_size_var = tk.StringVar(value="14")
            font_size_combo = ttk.Combobox(font_frame, textvariable=font_size_var,
                                          values=["10", "12", "14", "16", "18", "20", "24"],
                                          width=5, state="readonly")
            font_size_combo.pack(side=tk.LEFT, padx=2)
            ttk.Label(font_frame, text="字体:").pack(side=tk.LEFT, padx=(10, 2))
            font_family_var = tk.StringVar(value="TkDefaultFont")
            font_family_combo = ttk.Combobox(font_frame, textvariable=font_family_var,
                                            values=["TkDefaultFont", "Microsoft YaHei", "SimHei", "SimSun", "Arial", "Courier"],
                                            width=15, state="readonly")
            font_family_combo.pack(side=tk.LEFT, padx=2)
            # 字体变化处理
            def change_font(*args):
                try:
                    font_size = int(font_size_var.get())
                    font_family = font_family_var.get()
                    viewer_text.configure(font=(font_family, font_size))
                except:
                    pass
            font_size_var.trace('w', change_font)
            font_family_var.trace('w', change_font)
            # 查找功能
            search_frame = ttk.LabelFrame(font_toolbar, text="查找", padding=5)
            search_frame.pack(side=tk.LEFT, padx=5)
            search_entry = ttk.Entry(search_frame, width=20)
            search_entry.pack(side=tk.LEFT, padx=2)
            search_positions = []
            current_search_index = [0]
            def do_search():
                """执行查找"""
                search_term = search_entry.get().strip()
                if not search_term:
                    messagebox.showwarning("警告", "请输入要查找的文本", parent=win)
                    return
                search_positions.clear()
                start = "1.0"
                while True:
                    pos = viewer_text.search(search_term, start, tk.END)
                    if not pos:
                        break
                    search_positions.append(pos)
                    start = pos + "+1c"
                if not search_positions:
                    messagebox.showinfo("查找结果", f"未找到 '{search_term}'", parent=win)
                    search_pos_label.config(text="")
                    return
                current_search_index[0] = 0
                highlight_search_result()
                search_pos_label.config(text=f"1/{len(search_positions)}")
            def search_next():
                """查找下一个"""
                if not search_positions:
                    messagebox.showwarning("警告", "请先执行查找", parent=win)
                    return
                current_search_index[0] = (current_search_index[0] + 1) % len(search_positions)
                highlight_search_result()
                search_pos_label.config(text=f"{current_search_index[0] + 1}/{len(search_positions)}")
            def search_prev():
                """查找上一个"""
                if not search_positions:
                    messagebox.showwarning("警告", "请先执行查找", parent=win)
                    return
                current_search_index[0] = (current_search_index[0] - 1) % len(search_positions)
                highlight_search_result()
                search_pos_label.config(text=f"{current_search_index[0] + 1}/{len(search_positions)}")
            def highlight_search_result():
                """高亮显示查找结果"""
                if not search_positions or current_search_index[0] < 0:
                    return
                viewer_text.tag_remove("search_highlight", "1.0", tk.END)
                pos = search_positions[current_search_index[0]]
                search_term = search_entry.get().strip()
                end_pos = f"{pos}+{len(search_term)}c"
                viewer_text.tag_add("search_highlight", pos, end_pos)
                viewer_text.see(pos)
            ttk.Button(search_frame, text="查找", command=do_search).pack(side=tk.LEFT, padx=2)
            ttk.Button(search_frame, text="下一个", command=search_next).pack(side=tk.LEFT, padx=2)
            ttk.Button(search_frame, text="上一个", command=search_prev).pack(side=tk.LEFT, padx=2)
            search_pos_label = ttk.Label(search_frame, text="")
            search_pos_label.pack(side=tk.LEFT, padx=5)
            # 主内容区域
            content_frame = ttk.Frame(win)
            content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            content_frame.columnconfigure(0, weight=1)
            content_frame.rowconfigure(0, weight=1)
            # 文本查看/编辑区域
            text_panel = ttk.LabelFrame(content_frame, text="完整内容", padding=5)
            text_panel.grid(row=0, column=0, sticky="nsew")
            text_panel.columnconfigure(0, weight=1)
            text_panel.rowconfigure(0, weight=1)
            # 根据情绪周期确定背景颜色
            if hasattr(self, 'get_emotion_bg_color'):
                viewer_bg_color = self.get_emotion_bg_color()
            else:
                viewer_bg_color = "white"
            viewer_text = scrolledtext.ScrolledText(text_panel, wrap=tk.WORD,
                                                   font=("TkDefaultFont", 16), undo=True, bg=viewer_bg_color)
            viewer_text.pack(fill=tk.BOTH, expand=True)
            viewer_text.insert("1.0", content)
            viewer_text.config(state=tk.NORMAL)
            self._enable_text_copy_menu(viewer_text, readonly=True)
            # 保存引用以便后续更新背景颜色
            if not hasattr(self, '_browse_window_text_widgets'):
                self._browse_window_text_widgets = []
            self._browse_window_text_widgets.append(viewer_text)
            # 配置查找高亮标签
            viewer_text.tag_config("search_highlight", background="yellow")
            # 聚焦到文本区域
            viewer_text.focus_set()
        except Exception as e:
            messagebox.showerror("错误", f"打开全窗口浏览失败: {e}", parent=self.root)
            import traceback
            traceback.print_exc()

    def close_tab(self, tab_id):
        """关闭指定标签页"""
        if tab_id in self.text_widgets:
            tab_info = self.text_widgets[tab_id]
            self.text_notebook.forget(tab_info['frame'])
            del self.text_widgets[tab_id]
            self.update_text_input_reference()

    def create_result_tab(self, title):
        """创建新的结果标签页"""
        self.result_tab_counter += 1
        tab_id = f"result_tab_{self.result_tab_counter}"
        # 创建标签页框架
        tab_frame = ttk.Frame(self.result_notebook)
        self.result_notebook.add(tab_frame, text=title)
        # 创建顶部工具栏(包含关闭按钮)
        toolbar = ttk.Frame(tab_frame)
        toolbar.pack(fill=tk.X, padx=2, pady=2, side=tk.TOP)
        # 关闭按钮(使用×符号,更紧凑)
        close_btn = ttk.Button(toolbar, text="×", width=3,
                              command=lambda: self.close_result_tab(tab_id))
        close_btn.pack(side=tk.RIGHT, padx=2)
        # 如果是OCR识别器标签页,添加特殊功能
        if title == "OCR识别器":
            # OCR识别器工具栏
            ocr_toolbar = ttk.Frame(tab_frame)
            ocr_toolbar.pack(fill=tk.X, padx=5, pady=5)
            ttk.Button(ocr_toolbar, text="识别截图", command=self.ocr_recognize_screenshots, width=12).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(ocr_toolbar, text="选择图片", command=self.ocr_select_image, width=12).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(ocr_toolbar, text="粘贴图片", command=self.ocr_paste_image, width=12).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(ocr_toolbar, text="同花顺识别", command=self.ocr_recognize_ths, width=12).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(ocr_toolbar, text="保存到分析", command=self.save_ocr_to_analysis, width=12).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(ocr_toolbar, text="保存为资讯", command=self.save_ocr_to_news, width=12).pack(side=tk.LEFT, padx=(0, 5))
            # 清空按钮将在text_widget创建后绑定
            clear_btn = ttk.Button(ocr_toolbar, text="清空", width=8)
            clear_btn.pack(side=tk.LEFT, padx=(0, 5))
            # 截图目录显示
            dir_frame = ttk.Frame(tab_frame)
            dir_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
            ttk.Label(dir_frame, text="截图目录:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(0, 5))
            self.ocr_dir_var = tk.StringVar(value=self.screenshot_save_dir if hasattr(self, 'screenshot_save_dir') else "")
            dir_entry = ttk.Entry(dir_frame, textvariable=self.ocr_dir_var, width=50)
            dir_entry.pack(side=tk.LEFT, padx=(0, 5), fill=tk.X, expand=True)
            ttk.Button(dir_frame, text="浏览", command=self.browse_screenshot_dir, width=8).pack(side=tk.LEFT)
        # 创建文本框和滚动条
        text_widget = scrolledtext.ScrolledText(tab_frame, height=26, width=200,
                                               font=("TkDefaultFont", 16))
        text_widget.pack(fill=tk.BOTH, expand=True)
        # 配置文本颜色标签
        self._configure_result_text_tags(text_widget)
        self._enable_clickable_links(text_widget)
        # 如果是OCR识别器标签页,绑定清空按钮
        if title == "OCR识别器":
            # 找到清空按钮并绑定命令
            for widget in tab_frame.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for btn in widget.winfo_children():
                        if isinstance(btn, ttk.Button) and btn.cget("text") == "清空":
                            btn.config(command=lambda: text_widget.delete("1.0", tk.END))
                            break
        # 存储引用
        self.result_tabs[tab_id] = {
            'widget': text_widget,
            'title': title,
            'frame': tab_frame
        }
        # 切换到新标签页
        self.result_notebook.select(tab_frame)
        return tab_id

    def close_result_tab(self, tab_id):
        """关闭指定的结果标签页"""
        if tab_id in self.result_tabs:
            tab_info = self.result_tabs[tab_id]
            self.result_notebook.forget(tab_info['frame'])
            del self.result_tabs[tab_id]

    def _configure_result_text_tags(self, text_widget):
        """配置结果文本框的颜色标签"""
        text_widget.tag_configure("five_day_daily", foreground="black", font=("TkDefaultFont", 16))
        text_widget.tag_configure("five_day_total", foreground="red", font=("TkDefaultFont", 17, "bold"))
        text_widget.tag_configure("ten_day_total", foreground="orange", font=("TkDefaultFont", 17, "bold"))
        text_widget.tag_configure("twenty_day_total", foreground="green", font=("TkDefaultFont", 17, "bold"))
        text_widget.tag_configure("sixty_day_total", foreground="purple", font=("TkDefaultFont", 17, "bold"))
        text_widget.tag_configure("positive", foreground="red", font=("TkDefaultFont", 16, "bold"))
        text_widget.tag_configure("negative", foreground="green", font=("TkDefaultFont", 16, "bold"))
        text_widget.tag_configure("error", foreground="red")

    def _refresh_clickable_links(self, text_widget):
        """刷新文本框中的链接高亮与双击打开范围。"""
        try:
            full_text = text_widget.get("1.0", tk.END)
            text_widget.tag_remove("hyperlink", "1.0", tk.END)
            for m in re.finditer(r"https?://[^\s<>\"]+", full_text):
                start_idx = f"1.0+{m.start()}c"
                end_idx = f"1.0+{m.end()}c"
                text_widget.tag_add("hyperlink", start_idx, end_idx)
        except Exception:
            pass

    def _enable_clickable_links(self, text_widget):
        """让文本框中的 URL 自动变蓝并支持双击打开。"""
        if getattr(text_widget, "_hyperlink_enabled", False):
            return
        text_widget._hyperlink_enabled = True
        text_widget.tag_configure("hyperlink", foreground="#1D4ED8", underline=True)
        def _open_link_on_double_click(event):
            idx = text_widget.index(f"@{event.x},{event.y}")
            for start, end in zip(text_widget.tag_ranges("hyperlink")[0::2], text_widget.tag_ranges("hyperlink")[1::2]):
                if text_widget.compare(idx, ">=", start) and text_widget.compare(idx, "<", end):
                    url = text_widget.get(start, end).strip()
                    if url:
                        webbrowser.open(url)
                    return "break"
            return None
        def _on_text_modified(_event=None):
            if getattr(text_widget, "_hyperlink_refreshing", False):
                return
            if not text_widget.edit_modified():
                return
            text_widget._hyperlink_refreshing = True
            try:
                self._refresh_clickable_links(text_widget)
            finally:
                text_widget.edit_modified(False)
                text_widget._hyperlink_refreshing = False
        text_widget.bind("<Double-Button-1>", _open_link_on_double_click, add="+")
        text_widget.bind("<<Modified>>", _on_text_modified, add="+")
        self._refresh_clickable_links(text_widget)

    def get_active_result_widget(self):
        """获取当前活动的结果标签页文本框"""
        try:
            selected_tab = self.result_notebook.select()
            if selected_tab:
                for tab_info in self.result_tabs.values():
                    if str(tab_info['frame']) == selected_tab:
                        return tab_info['widget']
        except:
            pass
        # 如果没有找到,返回第一个标签页
        if self.result_tabs:
            first_tab = next(iter(self.result_tabs.values()))
            return first_tab['widget']
        return None

    def run_crawler_script(self, crawler_type="taoguba"):
        """执行爬虫脚本并实时显示输出"""
        # 映射爬虫类型到脚本文件名
        script_map = {
            "taoguba": "taoguba_100_posts_crawler.py",
            "jiuyan": "jiuyan_gongshe_crawler.py",
            "eastmoney": "eastmoney_hot_crawler.py",
            "xueqiu": "xueqiu_daily_crawler.py"
        }
        script_name = script_map.get(crawler_type, script_map["taoguba"])
        # 获取脚本路径(支持多种查找方式,包括打包后的环境)
        script_path = None
        tried_paths = []
        # 1. 尝试使用 PyInstaller 打包后的路径(sys._MEIPASS)
        if hasattr(sys, '_MEIPASS'):
            meipass_path = os.path.join(sys._MEIPASS, script_name)
            tried_paths.append(f"1. {meipass_path}")
            if os.path.exists(meipass_path):
                script_path = meipass_path
        # 2. 尝试可执行文件所在目录的 _internal 子目录(PyInstaller onefile=False 模式)
        if not script_path:
            exe_dir = os.path.dirname(os.path.abspath(sys.executable if hasattr(sys, 'frozen') else __file__))
            internal_path = os.path.join(exe_dir, '_internal', script_name)
            tried_paths.append(f"2. {internal_path}")
            if os.path.exists(internal_path):
                script_path = internal_path
        # 3. 尝试与主程序同目录
        if not script_path:
            same_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
            tried_paths.append(f"3. {same_dir_path}")
            if os.path.exists(same_dir_path):
                script_path = same_dir_path
        # 3b. 拆分项目后:仓库根目录与各 *_project/src
        if not script_path:
            pmono = find_script_path_in_monorepo(script_name, tried_paths)
            if pmono:
                script_path = pmono
        # 4. 尝试可执行文件所在目录(对于 onefile=False 模式)
        if not script_path and hasattr(sys, 'frozen'):
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            exe_dir_path = os.path.join(exe_dir, script_name)
            tried_paths.append(f"4. {exe_dir_path}")
            if os.path.exists(exe_dir_path):
                script_path = exe_dir_path
        # 5. 尝试当前工作目录
        if not script_path:
            cwd_path = os.path.join(os.getcwd(), script_name)
            tried_paths.append(f"5. {cwd_path}")
            if os.path.exists(cwd_path):
                script_path = cwd_path
        # 6. 尝试相对路径
        if not script_path:
            tried_paths.append(f"6. {script_name}")
            if os.path.exists(script_name):
                script_path = script_name
        # 如果都找不到,报错
        if not script_path or not os.path.exists(script_path):
            error_msg = f"爬虫脚本不存在: {script_name}\n\n已尝试路径:\n" + "\n".join(tried_paths)
            error_msg += "\n\n请确保脚本文件已正确打包或放置在可执行文件目录中。"
            messagebox.showerror("错误", error_msg)
            return
        # 在后台线程中执行
        def run_script():
            try:
                import importlib.util
                import io
                import subprocess
                import sys
                # 获取结果文本框
                result_widget = self._get_result_text_for_crawler()
                if not result_widget:
                    return
                # 实时显示输出函数
                def append_output(text, tag=""):
                    if hasattr(self, "root") and self.root.winfo_exists():
                        if tag:
                            self.root.after(0, lambda: result_widget.insert(tk.END, text, tag))
                        else:
                            self.root.after(0, lambda: result_widget.insert(tk.END, text))
                        self.root.after(0, lambda: result_widget.see(tk.END))
                        self._safe_update_idletasks()
                # 显示开始信息
                append_output(f"\n{'='*80}\n")
                append_output(f"开始执行: {script_name}\n")
                append_output(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                append_output(f"{'='*80}\n\n")
                # 检查是否为打包后的环境
                is_frozen = hasattr(sys, 'frozen') or hasattr(sys, '_MEIPASS')
                # 设置环境变量,确保UTF-8编码(无论是否打包)
                os.environ['PYTHONIOENCODING'] = 'utf-8'
                os.environ['PYTHONUTF8'] = '1'
                if sys.platform == 'win32':
                    os.environ['PYTHONLEGACYWINDOWSSTDIO'] = '0'
                if is_frozen:
                    # 打包后的环境:直接导入并执行脚本模块
                    try:
                        script_dir = os.path.dirname(script_path)
                        original_cwd = os.getcwd()
                        # 打包后使用统一可写目录 D_EXPORT_DIR,避免脚本目录为只读导致无法生成 Excel
                        try:
                            os.makedirs(D_EXPORT_DIR, exist_ok=True)
                            os.chdir(D_EXPORT_DIR)
                        except Exception:
                            os.chdir(script_dir)
                        # 创建模块规范
                        module_name = os.path.splitext(script_name)[0]  # 去掉 .py 扩展名
                        spec = importlib.util.spec_from_file_location(module_name, script_path)
                        if spec is None or spec.loader is None:
                            os.chdir(original_cwd)  # 恢复工作目录
                            append_output(f"[错误] 无法加载模块: {script_name}\n", "error")
                            append_output(f"脚本路径: {script_path}\n", "error")
                            return
                        # 创建模块
                        module = importlib.util.module_from_spec(spec)
                        # 保存原始的 sys.stdout 和 sys.stderr
                        original_stdout = sys.stdout
                        original_stderr = sys.stderr
                        # 创建自定义的输出捕获器(支持UTF-8编码)
                        class OutputCapture:
                            def __init__(self, output_func, prefix="[OUT]"):
                                self.output_func = output_func
                                self.prefix = prefix
                                self.buffer = io.StringIO()
                            def write(self, text):
                                try:
                                    # 确保文本是字符串类型
                                    if isinstance(text, bytes):
                                        text = text.decode('utf-8', errors='replace')
                                    elif not isinstance(text, str):
                                        text = str(text)
                                    # 清理文本,处理可能的编码问题
                                    text = text.replace('\r\n', '\n').replace('\r', '\n')
                                    if text and text.strip():
                                        # 实时输出到界面(确保UTF-8)
                                        self.output_func(f"{self.prefix} {text}")
                                        # 同时保存到缓冲区
                                        self.buffer.write(text)
                                        return len(text)
                                except Exception:
                                    # 如果编码转换失败,使用替换字符
                                    try:
                                        safe_text = text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                                        self.output_func(f"{self.prefix} {safe_text}")
                                        self.buffer.write(safe_text)
                                    except:
                                        self.output_func(f"{self.prefix} [编码错误: 无法显示内容]\n")
                                    return len(text) if text else 0
                            def flush(self):
                                try:
                                    self.buffer.flush()
                                except:
                                    pass
                            def readable(self):
                                return False
                            def writable(self):
                                return True
                            def seekable(self):
                                return False
                            def encoding(self):
                                return 'utf-8'
                            def errors(self):
                                return 'replace'
                        # 创建输出捕获器
                        stdout_capture = OutputCapture(append_output, "[OUT]")
                        stderr_capture = OutputCapture(lambda text: append_output(text, "error"), "[ERR]")
                        # 重定向输出
                        sys.stdout = stdout_capture
                        sys.stderr = stderr_capture
                        try:
                            # 执行模块(仅加载,不会执行 if __name__ == "__main__")
                            spec.loader.exec_module(module)
                            # 打包环境下必须显式调用 main(),否则爬虫不会真正运行
                            if hasattr(module, 'main') and callable(module.main):
                                if crawler_type == 'jiuyan':
                                    module.main(limit=None, output=D_EXPORT_DIR)
                                else:
                                    module.main()
                            # 恢复输出
                            sys.stdout = original_stdout
                            sys.stderr = original_stderr
                            os.chdir(original_cwd)  # 恢复工作目录
                            # 显示完成信息
                            append_output(f"\n{'='*80}\n")
                            append_output("执行完成: 成功\n")
                            append_output(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            append_output(f"{'='*80}\n\n")
                        except Exception as e:
                            # 恢复输出和工作目录
                            sys.stdout = original_stdout
                            sys.stderr = original_stderr
                            os.chdir(original_cwd)
                            # 处理错误信息编码
                            try:
                                error_msg = str(e)
                                if isinstance(error_msg, bytes):
                                    error_msg = error_msg.decode('utf-8', errors='replace')
                                append_output(f"执行脚本时出错: {error_msg}\n", "error")
                            except:
                                append_output("执行脚本时出错: [编码错误,无法显示详细信息]\n", "error")
                            import traceback
                            try:
                                traceback_output = traceback.format_exc()
                                if isinstance(traceback_output, bytes):
                                    traceback_output = traceback_output.decode('utf-8', errors='replace')
                                append_output(f"\n详细错误信息:\n{traceback_output}\n", "error")
                            except:
                                append_output("\n详细错误信息: [编码错误,无法显示堆栈信息]\n", "error")
                            return
                    except Exception as e:
                        if 'original_cwd' in locals():
                            os.chdir(original_cwd)  # 确保恢复工作目录
                        try:
                            error_msg = str(e)
                            if isinstance(error_msg, bytes):
                                error_msg = error_msg.decode('utf-8', errors='replace')
                            append_output(f"导入模块失败: {error_msg}\n", "error")
                        except:
                            append_output("导入模块失败: [编码错误,无法显示详细信息]\n", "error")
                        import traceback
                        try:
                            traceback_output = traceback.format_exc()
                            if isinstance(traceback_output, bytes):
                                traceback_output = traceback_output.decode('utf-8', errors='replace')
                            append_output(f"\n详细错误信息:\n{traceback_output}\n", "error")
                        except:
                            append_output("\n详细错误信息: [编码错误,无法显示堆栈信息]\n", "error")
                        return
                else:
                    # 开发环境:使用 subprocess 执行脚本
                    # 设置环境变量
                    env = os.environ.copy()
                    env['PYTHONIOENCODING'] = 'utf-8'
                    # 执行脚本(开发环境)
                    # 确保使用正确的Python解释器
                    python_exe = sys.executable
                    # 设置环境变量,确保UTF-8编码
                    env['PYTHONIOENCODING'] = 'utf-8'
                    env['PYTHONUTF8'] = '1'
                    if sys.platform == 'win32':
                        env['PYTHONLEGACYWINDOWSSTDIO'] = '0'
                    process = subprocess.Popen(
                        [python_exe, script_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env,
                        cwd=os.path.dirname(script_path),
                        encoding='utf-8',
                        errors='replace',
                        bufsize=1,
                        text=True,  # 使用 text=True 替代 universal_newlines
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                    )
                    # 读取stdout(处理编码问题)
                    for line in iter(process.stdout.readline, ''):
                        if line:
                            try:
                                # 清理行尾字符
                                line = line.rstrip('\n\r')
                                # 确保是UTF-8字符串
                                if isinstance(line, bytes):
                                    line = line.decode('utf-8', errors='replace')
                                # 移除可能的BOM
                                line = line.removeprefix('\ufeff')
                                append_output(f"[STDOUT] {line}\n")
                            except Exception:
                                # 如果编码失败,尝试用错误替换
                                try:
                                    safe_line = line.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                                    append_output(f"[STDOUT] {safe_line}\n")
                                except:
                                    append_output("[STDOUT] [编码错误: 无法显示该行内容]\n", "error")
                    # 读取stderr(处理编码问题)
                    for line in iter(process.stderr.readline, ''):
                        if line:
                            try:
                                # 清理行尾字符
                                line = line.rstrip('\n\r')
                                # 确保是UTF-8字符串
                                if isinstance(line, bytes):
                                    line = line.decode('utf-8', errors='replace')
                                # 移除可能的BOM
                                line = line.removeprefix('\ufeff')
                                append_output(f"[STDERR] {line}\n", "error")
                            except Exception:
                                # 如果编码失败,尝试用错误替换
                                try:
                                    safe_line = line.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                                    append_output(f"[STDERR] {safe_line}\n", "error")
                                except:
                                    append_output("[STDERR] [编码错误: 无法显示该行内容]\n", "error")
                    # 等待进程完成
                    return_code = process.wait()
                    # 显示完成信息
                    status = "成功" if return_code == 0 else "失败"
                    append_output(f"\n{'='*80}\n")
                    append_output(f"执行完成: {status} (返回码: {return_code})\n")
                    append_output(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    append_output(f"{'='*80}\n\n")
                # 查找生成的Excel文件并保存到配置文件(无论是否打包)
                script_dir = os.path.dirname(script_path)
                excel_files = []
                # 打包后爬虫统一输出到 D_EXPORT_DIR,优先在该目录查找
                export_dir = D_EXPORT_DIR if (hasattr(sys, 'frozen') or hasattr(sys, '_MEIPASS')) else None
                # 根据爬虫类型查找对应的Excel文件
                if crawler_type == "jiuyan":
                    # 韭研公社:查找 jiuyang_gongshe_*.xlsx
                    search_patterns = ["jiuyang_gongshe_", "jiuyan_"]
                    search_dirs = [export_dir, script_dir, os.getcwd()] if export_dir else [script_dir, os.getcwd()]
                elif crawler_type == "taoguba":
                    # 淘股吧:查找 taoguba_100_posts_*.xlsx
                    search_patterns = ["taoguba_100_posts_", "taoguba_"]
                    search_dirs = (
                        [export_dir, os.path.join(script_dir, "taoguba_exports"), script_dir, os.getcwd()]
                        if export_dir
                        else [os.path.join(script_dir, "taoguba_exports"), script_dir, os.getcwd()]
                    )
                else:
                    # 其他爬虫:查找对应的Excel文件
                    search_patterns = [crawler_type]
                    search_dirs = [export_dir, script_dir, os.getcwd()] if export_dir else [script_dir, os.getcwd()]
                search_dirs = [d for d in search_dirs if d and os.path.exists(d)]
                for search_dir in search_dirs:
                    if os.path.exists(search_dir):
                        try:
                            for file in os.listdir(search_dir):
                                if file.endswith(".xlsx"):
                                    for pattern in search_patterns:
                                        if pattern.lower() in file.lower():
                                            file_path = os.path.join(search_dir, file)
                                            excel_files.append((os.path.getmtime(file_path), file_path))
                                            break
                        except Exception as e:
                            print(f"查找Excel文件时出错 {search_dir}: {e}")
                if excel_files:
                    # 按修改时间排序,获取最新的文件
                    excel_files.sort(reverse=True)
                    latest_excel = excel_files[0][1]
                    # 保存到配置文件
                    source_map = {
                        "jiuyan": "韭研公社",
                        "taoguba": "淘股吧",
                        "eastmoney": "东方财富",
                        "xueqiu": "雪球"
                    }
                    source = source_map.get(crawler_type, crawler_type)
                    try:
                        self._save_excel_file_to_config(latest_excel, source=source)
                        self.root.after(0, lambda: messagebox.showinfo(
                            "成功", f"爬虫脚本执行完成: {script_name}\n\nExcel文件已保存:\n{os.path.basename(latest_excel)}\n路径: {latest_excel}"))
                    except Exception as e:
                        self.root.after(0, lambda e=e: messagebox.showinfo(
                            "成功", f"爬虫脚本执行完成: {script_name}\n\nExcel文件: {os.path.basename(latest_excel)}\n但保存配置失败: {e}"))
                else:
                    self.root.after(0, lambda: messagebox.showinfo(
                        "成功", f"爬虫脚本执行完成: {script_name}\n\n未找到Excel文件,请检查脚本输出"))
            except Exception as e:
                error_msg = f"执行爬虫脚本失败: {e!s}"
                result_widget = self._get_result_text_for_crawler()
                if result_widget:
                    self.root.after(0, lambda: result_widget.insert(
                        tk.END, f"\n[错误] {error_msg}\n"))
                    self.root.after(0, lambda: result_widget.see(tk.END))
                self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        # 配置错误标签颜色(为所有结果文本框配置)
        def configure_error_tag():
            result_widget = self._get_result_text_for_crawler()
            if result_widget:
                result_widget.tag_configure("error", foreground="red")
        self.root.after(0, configure_error_tag)
        # 启动线程
        thread = threading.Thread(target=run_script, daemon=True)
        thread.start()

    def load_excel(self):
        """从Excel文件加载内容(支持多文件上传和多标签页,支持彩色文本显示)"""
        # 首先尝试从配置文件读取最新的Excel文件
        recent_files = self._get_recent_excel_files()
        if recent_files:
            # 创建选择窗口
            select_window = self._safe_toplevel(self.root)
            select_window.title("选择Excel文件")
            select_window.geometry("600x400")
            select_window.transient(self.root)
            ttk.Label(select_window, text="最近保存的Excel文件(双击选择):", font=("TkDefaultFont", 12, "bold")).pack(pady=10)
            # 创建列表框
            listbox_frame = ttk.Frame(select_window)
            listbox_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            scrollbar = ttk.Scrollbar(listbox_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, font=("TkDefaultFont", 11))
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)
            # 添加文件到列表
            file_paths_list = []
            for file_info in recent_files:
                file_path = file_info.get('path', '')
                file_name = os.path.basename(file_path)
                timestamp = file_info.get('timestamp', '')
                source = file_info.get('source', '')
                display_text = f"[{source}] {file_name} ({timestamp})"
                listbox.insert(tk.END, display_text)
                file_paths_list.append(file_path)
            selected_files = []
            def on_double_click(event):
                selection = listbox.curselection()
                if selection:
                    idx = selection[0]
                    selected_files.append(file_paths_list[idx])
                    select_window.destroy()
                    self._load_excel_files(selected_files)
            def on_select_all():
                selected_files.extend(file_paths_list)
                select_window.destroy()
                self._load_excel_files(selected_files)
            def on_cancel():
                select_window.destroy()
                # 如果取消,使用文件对话框
                file_paths = filedialog.askopenfilenames(filetypes=[("Excel files", "*.xlsx *.xls")])
                if file_paths:
                    self._load_excel_files(file_paths)
            listbox.bind("<Double-Button-1>", on_double_click)
            # 按钮框架
            button_frame = ttk.Frame(select_window)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="全选", command=on_select_all).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="取消(使用文件对话框)", command=on_cancel).pack(side=tk.LEFT, padx=5)
        else:
            # 如果没有配置文件,直接使用文件对话框
            file_paths = filedialog.askopenfilenames(filetypes=[("Excel files", "*.xlsx *.xls")])
            if file_paths:
                self._load_excel_files(file_paths)

    def paste_webpage(self):
        """从剪贴板粘贴网页内容(仅文字)"""
        try:
            # 获取剪贴板内容
            clipboard_content = self.root.clipboard_get()
            # 清理HTML标签
            text = extract_text_from_html(clipboard_content)
            text_widget = self.get_active_text_widget()
            if text_widget:
                text_widget.delete("1.0", tk.END)
                text_widget.insert("1.0", text)
        except Exception as e:
            print(f"从剪贴板粘贴网页内容失败: {e}")

    def paste_webpage_with_images(self):
        """从剪贴板粘贴网页内容(包含图片)"""
        try:
            # 获取剪贴板内容
            clipboard_content = self.root.clipboard_get()
            # 解析HTML内容,提取文字和图片
            parsed_content = self.parse_html_content(clipboard_content)
            # 清空文本框
            self.text_input.delete("1.0", tk.END)
            # 插入解析后的内容
            self.insert_parsed_content(parsed_content)
            # messagebox.showinfo("成功", f"从剪贴板粘贴网页内容成功\n\n包含:\n- 文字段落: {parsed_content['text_blocks']} 个\n- 图片: {parsed_content['images']} 个")
        except Exception as e:
            print(f"从剪贴板粘贴网页内容失败: {e}")

    def parse_html_content(self, html_content):
        """解析HTML内容,提取文字和图片"""
        try:
            import re

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            # 移除脚本和样式标签
            for script in soup(["script", "style"]):
                script.decompose()
            parsed_content = {
                'text_blocks': [],
                'images': []
            }
            # 提取文字段落
            for element in soup.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span']):
                text = element.get_text().strip()
                if text and len(text) > 10:  # 只保留有意义的文字
                    parsed_content['text_blocks'].append(text)
            # 提取图片
            for img in soup.find_all('img'):
                src = img.get('src')
                if src:
                    # 处理相对URL
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = 'https://example.com' + src
                    elif not src.startswith('http'):
                        src = 'https://example.com/' + src
                    alt_text = img.get('alt', '')
                    parsed_content['images'].append({
                        'src': src,
                        'alt': alt_text
                    })
            return parsed_content
        except ImportError:
            # 如果没有BeautifulSoup,使用简单的正则表达式
            return self.parse_html_simple(html_content)
        except Exception as e:
            print(f"解析HTML内容失败: {e}")
            return {'text_blocks': [extract_text_from_html(html_content)], 'images': []}

    def parse_html_simple(self, html_content):
        """简单的HTML解析(不使用BeautifulSoup)"""
        import re
        # 移除HTML标签,保留文字
        text = re.sub(r'<[^>]+>', ' ', html_content)
        text = re.sub(r'\s+', ' ', text).strip()
        # 提取图片URL
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
        images = []
        for match in re.finditer(img_pattern, html_content, re.IGNORECASE):
            src = match.group(1)
            if src:
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = 'https://example.com' + src
                elif not src.startswith('http'):
                    src = 'https://example.com/' + src
                images.append({'src': src, 'alt': ''})
        return {
            'text_blocks': [text] if text else [],
            'images': images
        }

    def insert_parsed_content(self, parsed_content, text_widget=None):
        """将解析后的内容插入到富媒体编辑器中"""
        try:
            if text_widget is None:
                text_widget = self.get_active_text_widget()
            if not text_widget:
                return
            current_pos = "1.0"
            # 插入文字内容
            for i, text_block in enumerate(parsed_content['text_blocks']):
                if i > 0:
                    text_widget.insert(current_pos, "\n\n")
                    current_pos = text_widget.index(tk.INSERT)
                text_widget.insert(current_pos, text_block)
                current_pos = text_widget.index(tk.INSERT)
            # 插入图片链接
            for img_info in parsed_content['images']:
                text_widget.insert(current_pos, "\n\n")
                current_pos = text_widget.index(tk.INSERT)
                # 下载并保存图片,插入链接
                image_path = self.insert_image_from_url(img_info['src'], img_info['alt'], text_widget)
                if image_path:
                    text_widget.insert(current_pos, f"[图片] {image_path}\n")
                    current_pos = text_widget.index(tk.INSERT)
                else:
                    text_widget.insert(current_pos, f"[图片加载失败: {img_info['src']}]\n")
                    current_pos = text_widget.index(tk.INSERT)
        except Exception as e:
            print(f"插入解析内容失败: {e}")

    def insert_image_from_url(self, image_url, alt_text="", text_widget=None):
        """从URL下载图片,保存到指定目录并返回路径"""
        try:
            from io import BytesIO

            import requests
            # 下载图片
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            # 创建图片对象
            image_data = BytesIO(response.content)
            image = Image.open(image_data)
            # 创建图片保存目录
            image_dir = os.path.join(D_OUTPUT_DIR, "Images")
            os.makedirs(image_dir, exist_ok=True)
            # 确定文件扩展名
            content_type = response.headers.get('content-type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = '.jpg'
            elif 'png' in content_type:
                ext = '.png'
            elif 'gif' in content_type:
                ext = '.gif'
            else:
                # 从URL推断或默认PNG
                url_lower = image_url.lower()
                if '.jpg' in url_lower or '.jpeg' in url_lower:
                    ext = '.jpg'
                elif '.gif' in url_lower:
                    ext = '.gif'
                else:
                    ext = '.png'
            # 生成文件名(带时间戳)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            image_filename = f"downloaded_image_{timestamp}{ext}"
            image_path = os.path.join(image_dir, image_filename)
            # 保存图片
            image.save(image_path, ext[1:].upper() if ext.upper() == '.JPG' else ext[1:].upper())
            print(f"✅ 图片已下载并保存: {image_path}")
            return image_path
        except Exception as e:
            print(f"下载并保存图片失败: {e}")
            # 如果图片下载失败,返回None
            return None

    def paste_text(self):
        """从剪贴板粘贴文本内容"""
        try:
            # 获取剪贴板内容
            clipboard_content = self.root.clipboard_get()
            text_widget = self.get_active_text_widget()
            if text_widget:
                text_widget.delete("1.0", tk.END)
                text_widget.insert("1.0", clipboard_content)
        except Exception as e:
            messagebox.showerror("错误", f"从剪贴板粘贴文本内容失败: {e}")

    def load_text_file(self):
        """读取文本文件"""
        file_path = filedialog.askopenfilename(filetypes=[
            ("Text files", "*.txt"),
            ("All files", "*.*")
        ])
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                text_widget = self.get_active_text_widget()
                if text_widget:
                    text_widget.delete("1.0", tk.END)
                    text_widget.insert("1.0", content)
                messagebox.showinfo("成功", f"从文本文件加载内容成功: {file_path}")
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='gbk') as f:
                        content = f.read()
                    text_widget = self.get_active_text_widget()
                    if text_widget:
                        text_widget.delete("1.0", tk.END)
                        text_widget.insert("1.0", content)
                    messagebox.showinfo("成功", f"从文本文件加载内容成功: {file_path}")
                except Exception as e:
                    messagebox.showerror("错误", f"读取文件失败: {e}")
            except Exception as e:
                messagebox.showerror("错误", f"读取文件失败: {e}")

    def clear_content(self):
        """清空当前标签页的文本输入框"""
        text_widget = self.get_active_text_widget()
        if text_widget:
            text_widget.delete("1.0", tk.END)

    def merge_upload(self):
        """合并上传功能 - 支持图片、Excel、Word、TXT等文件"""
        # 选择文件
        file_path = filedialog.askopenfilename(
            title="选择要合并的文件",
            filetypes=[
                ("所有支持的文件", "*.png *.jpg *.jpeg *.gif *.bmp *.xlsx *.xls *.docx *.doc *.txt"),
                ("图片文件", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("Excel文件", "*.xlsx *.xls"),
                ("Word文件", "*.docx *.doc"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*")
            ]
        )
        if not file_path:
            return
        try:
            # 获取文件扩展名
            file_ext = os.path.splitext(file_path)[1].lower()
            # 根据文件类型处理
            if file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                # 图片文件 - OCR功能已停用
                messagebox.showinfo("提示", "图片文件处理功能已暂时停用")
                return
            elif file_ext in ['.xlsx', '.xls']:
                # Excel文件
                extracted_text = extract_text_from_excel(file_path)
                self.append_text_to_input(extracted_text, "Excel", file_path)
            elif file_ext in ['.docx', '.doc']:
                # Word文件
                extracted_text = extract_text_from_docx(file_path)
                self.append_text_to_input(extracted_text, "Word", file_path)
            elif file_ext == '.txt':
                # 文本文件
                extracted_text = extract_text_from_txt(file_path)
                self.append_text_to_input(extracted_text, "TXT", file_path)
            else:
                messagebox.showwarning("警告", f"不支持的文件类型: {file_ext}")
                return
        except Exception as e:
            messagebox.showerror("错误", f"处理文件失败: {e!s}")

    def append_text_to_input(self, extracted_text, file_type, file_path):
        """将提取的文本添加到输入框"""
        try:
            text_widget = self.get_active_text_widget()
            if not text_widget:
                return
            # 添加文件信息标题
            file_info = f"\n\n=== {file_type}文件内容 ({os.path.basename(file_path)}) ===\n"
            text_widget.insert(tk.END, file_info)
            # 添加提取的文本
            text_widget.insert(tk.END, extracted_text)
            # 添加分隔线
            text_widget.insert(tk.END, "\n" + "="*50 + "\n")
            messagebox.showinfo("成功", f"已成功加载{file_type}文件内容")
        except Exception as e:
            messagebox.showerror("错误", f"添加文本到输入框失败: {e!s}")

    def get_from_url(self):
        """从URL获取内容"""
        try:
            url = simpledialog.askstring("输入URL", "请输入要获取内容的URL:")
            if not url:
                return
            # 这里可以添加URL内容获取逻辑
            messagebox.showinfo("提示", "URL内容获取功能暂未实现")
        except Exception as e:
            messagebox.showerror("错误", f"获取URL内容失败: {e!s}")

    def on_paste(self, event):
        """粘贴剪贴板内容 - 支持文本和图片"""
        try:
            text_widget = self.get_active_text_widget()
            if not text_widget:
                return
            # 首先尝试获取剪贴板中的图片
            if self.paste_clipboard_image(text_widget):
                return "break"  # 如果成功粘贴图片,阻止默认行为
            # 如果没有图片,尝试粘贴文本
            try:
                clipboard_text = self.root.clipboard_get()
                if clipboard_text:
                    text_widget.insert(tk.INSERT, clipboard_text)
                    return "break"  # 阻止默认粘贴行为
            except:
                # 如果文本粘贴失败,尝试粘贴HTML内容
                try:
                    self.paste_clipboard_html(text_widget)
                    return "break"
                except:
                    pass
        except Exception as e:
            print(f"粘贴失败: {e}")

    def merge_upload(self):
        """合并上传功能 - 支持图片、Excel、Word、TXT等文件"""
        # 选择文件
        file_path = filedialog.askopenfilename(
            title="选择要合并的文件",
            filetypes=[
                ("所有支持的文件", "*.png *.jpg *.jpeg *.gif *.bmp *.xlsx *.xls *.docx *.doc *.txt"),
                ("图片文件", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("Excel文件", "*.xlsx *.xls"),
                ("Word文档", "*.docx *.doc"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*")
            ]
        )
        if not file_path:
            return
        # 检查文件是否存在
        if not os.path.exists(file_path):
            messagebox.showerror("错误", f"文件不存在: {file_path}")
            return
        # 显示处理进度
        self.append_text_to_input("正在处理文件,请稍候...", "系统", file_path)
        # 在后台线程中处理文件
        def process_file():
            try:
                # 获取文件扩展名
                file_ext = os.path.splitext(file_path)[1].lower()
                file_name = os.path.basename(file_path)
                print(f"开始处理文件: {file_name} (类型: {file_ext})")
                # 根据文件类型提取文字
                if file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                    # 图片文件 - 保存到指定目录并插入链接
                    print("保存图片文件...")
                    # 创建图片保存目录
                    image_dir = os.path.join(D_OUTPUT_DIR, "Images")
                    os.makedirs(image_dir, exist_ok=True)
                    # 生成文件名(带时间戳)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                    image_filename = f"uploaded_image_{timestamp}{file_ext}"
                    image_save_path = os.path.join(image_dir, image_filename)
                    # 复制图片到指定目录
                    shutil.copy2(file_path, image_save_path)
                    # 生成图片链接文本
                    extracted_text = f"[图片] {image_save_path}\n"
                    file_type = "图片"
                elif file_ext in ['.xlsx', '.xls']:
                    # Excel文件
                    print("提取Excel文件内容...")
                    extracted_text = extract_text_from_excel(file_path)
                    file_type = "Excel"
                elif file_ext in ['.docx', '.doc']:
                    # Word文档
                    print("提取Word文档内容...")
                    extracted_text = extract_text_from_docx(file_path)
                    file_type = "Word"
                elif file_ext == '.txt':
                    # 文本文件
                    print("读取文本文件内容...")
                    extracted_text = extract_text_from_txt(file_path)
                    file_type = "TXT"
                else:
                    extracted_text = f"不支持的文件类型: {file_ext}\n\n支持的文件类型:\n- 图片: PNG, JPG, JPEG, GIF, BMP\n- Excel: XLSX, XLS\n- Word: DOCX, DOC\n- 文本: TXT"
                    file_type = "未知"
                print(f"文件处理完成: {file_name}")
                # 在主线程中更新UI
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after(0, lambda: self.append_text_to_input(extracted_text, file_type, file_path))
            except Exception as e:
                error_msg = f"处理文件失败: {e!s}\n\n文件路径: {file_path}\n\n可能的原因:\n1. 文件损坏或格式不支持\n2. 文件被其他程序占用\n3. 权限不足"
                print(f"文件处理错误: {error_msg}")
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        # 启动处理线程
        process_thread = threading.Thread(target=process_file, daemon=True)
        process_thread.start()
        # 显示处理中消息
        messagebox.showinfo("处理中", "正在处理文件,请稍候...")

    def append_text_to_input(self, extracted_text, file_type, file_path):
        """将提取的文字追加到文本框"""
        try:
            text_widget = self.get_active_text_widget()
            if not text_widget:
                return
            # 获取当前文本框内容
            current_content = text_widget.get("1.0", tk.END).strip()
            # 构建追加内容
            separator = "\n" + "="*50 + "\n"
            file_info = f"📁 文件来源: {file_type} - {os.path.basename(file_path)}\n"
            timestamp = f"⏰ 添加时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            # 如果当前内容不为空,添加分隔符
            if current_content:
                new_content = current_content + separator + file_info + timestamp + "\n" + extracted_text
            else:
                new_content = file_info + timestamp + "\n" + extracted_text
            # 更新文本框内容
            text_widget.delete("1.0", tk.END)
            text_widget.insert("1.0", new_content)
            # 滚动到末尾
            text_widget.see(tk.END)
            # 显示成功消息
            messagebox.showinfo("成功", f"已成功从{file_type}文件中提取文字并添加到文本框\n\n文件: {os.path.basename(file_path)}\n提取文字长度: {len(extracted_text)} 字符")
        except Exception as e:
            messagebox.showerror("错误", f"添加文字到文本框失败: {e!s}")

    def get_from_url(self):
        """从URL获取内容"""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("警告", "请输入URL")
            return
        try:
            response = requests.get(url, timeout=10)
            response.encoding = response.apparent_encoding
            text = extract_text_from_html(response.text)
            text_widget = self.get_active_text_widget()
            if text_widget:
                text_widget.delete("1.0", tk.END)
                text_widget.insert("1.0", text)
            messagebox.showinfo("成功", "从URL获取内容成功")
        except Exception as e:
            messagebox.showerror("错误", f"获取URL内容失败: {e}")

    def process_clipboard_image(self, image_data):
        """处理剪贴板图片数据"""
        try:
            from io import BytesIO
            # 将DIB数据转换为PIL图片
            image = Image.open(BytesIO(image_data))
            # 调整图片大小
            max_width = 300
            max_height = 200
            # 计算缩放比例
            width_ratio = max_width / image.width
            height_ratio = max_height / image.height
            ratio = min(width_ratio, height_ratio, 1)
            new_width = int(image.width * ratio)
            new_height = int(image.height * ratio)
            # 调整图片大小
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            # 转换为PhotoImage
            photo = ImageTk.PhotoImage(image)
            # 存储图片引用
            self.image_counter += 1
            image_key = f"clipboard_image_{self.image_counter}"
            self.images[image_key] = photo
            # 在图片显示区域显示图片
            self.display_image_in_frame(photo, f"📷 剪贴板图片 {self.image_counter}", image, "clipboard")
            messagebox.showinfo("成功", "已粘贴剪贴板中的图片!\n点击[🔍 OCR识别]可以识别图片中的文字。")
        except Exception as e:
            print(f"处理剪贴板图片失败: {e}")

    def on_text_change(self, event):
        """文本变化时高亮股票代码(绑定到当前活动标签页)"""
        try:
            # 延迟执行,避免频繁触发
            if hasattr(self, 'highlight_timer') and self.highlight_timer:
                try:
                    self.root.after_cancel(self.highlight_timer)
                except:
                    pass  # 如果timer已经不存在或无效,忽略错误
            # 更新text_input引用
            self.update_text_input_reference()
            try:
                self.highlight_timer = self.root.after(500, self.highlight_stock_codes)
            except Exception as e:
                # 如果after调用失败,记录但不中断程序
                print(f"设置高亮定时器失败: {e}")
                self.highlight_timer = None
        except Exception as e:
            print(f"文本变化处理失败: {e}")

    def highlight_stock_codes(self):
        """高亮股票代码并在右边插入股票名"""
        try:
            text_widget = self.get_active_text_widget()
            if not text_widget:
                return
            # 清除之前的高亮
            text_widget.tag_remove("stock_code", "1.0", tk.END)
            text_widget.tag_remove("stock_name", "1.0", tk.END)
            # 获取当前文本
            text = text_widget.get("1.0", tk.END)
            # 提取股票代码位置
            _stock_names, stock_code_positions = extract_stock_names(text)
            if not stock_code_positions:
                return
            # 按位置倒序排列,避免插入文本后位置变化
            stock_code_positions.sort(key=lambda x: x['start'], reverse=True)
            # 为每个股票代码添加高亮和股票名
            for pos_info in stock_code_positions:
                pos_info['code']
                name = pos_info['name']
                start_pos = pos_info['start']
                end_pos = pos_info['end']
                # 转换为tkinter位置格式
                start_line = text[:start_pos].count('\n') + 1
                start_char = start_pos - text.rfind('\n', 0, start_pos) - 1
                end_line = text[:end_pos].count('\n') + 1
                end_char = end_pos - text.rfind('\n', 0, end_pos) - 1
                start_tk = f"{start_line}.{start_char}"
                end_tk = f"{end_line}.{end_char}"
                # 高亮股票代码
                text_widget.tag_add("stock_code", start_tk, end_tk)
                text_widget.tag_config("stock_code", background="yellow")
                # 在股票代码后面插入股票名(红色宋体)
                text_widget.tag_add("stock_name", end_tk, f"{end_line}.{end_char + 1}")
                text_widget.tag_config("stock_name", foreground="red", font=("宋体", 16))
                # 插入股票名
                text_widget.insert(end_tk, f"({name})")
        except Exception as e:
            print(f"高亮股票代码失败: {e}")

    def increase_font_size(self):
        """增加字体大小"""
        try:
            current_size = int(self.font_size_var.get())
            if current_size < 24:
                new_size = current_size + 1
                self.font_size_var.set(str(new_size))
                self.change_font_size()
        except Exception as e:
            print(f"增大字体失败: {e}")

    def decrease_font_size(self):
        """减少字体大小"""
        try:
            current_size = int(self.font_size_var.get())
            if current_size > 10:
                new_size = current_size - 1
                self.font_size_var.set(str(new_size))
                self.change_font_size()
        except Exception as e:
            print(f"减小字体失败: {e}")

    def change_font_size(self, event=None):
        """改变字体大小"""
        try:
            font_size = int(self.font_size_var.get())
            # 更新所有结果文本框字体
            for tab_info in self.result_tabs.values():
                result_widget = tab_info['widget']
                result_widget.configure(font=("TkDefaultFont", font_size))
            # 更新文本颜色标签的字体大小
                result_widget.tag_configure("five_day_daily", foreground="black", font=("TkDefaultFont", font_size))
                result_widget.tag_configure("five_day_total", foreground="red", font=("TkDefaultFont", font_size + 1, "bold"))
                result_widget.tag_configure("ten_day_total", foreground="orange", font=("TkDefaultFont", font_size + 1, "bold"))
                result_widget.tag_configure("twenty_day_total", foreground="green", font=("TkDefaultFont", font_size + 1, "bold"))
                result_widget.tag_configure("sixty_day_total", foreground="blue", font=("TkDefaultFont", font_size + 1, "bold"))
            if getattr(self, "font_size_label", None):
                try:
                    self.font_size_label.config(text=str(font_size))
                except Exception:
                    pass
            print(f"字体大小已更改为: {font_size}")
        except Exception as e:
            print(f"更改字体大小失败: {e}")

    def search_text(self):
        """查找文本"""
        search_term = self.search_entry.get().strip()
        if not search_term:
            messagebox.showwarning("警告", "请输入要查找的文本")
            return
        text_widget = self.get_active_text_widget()
        if not text_widget:
            return
        # 查找所有匹配位置
        self.search_positions = []
        start = "1.0"
        while True:
            pos = text_widget.search(search_term, start, tk.END)
            if not pos:
                break
            self.search_positions.append(pos)
            start = pos + "+1c"
        if not self.search_positions:
            messagebox.showinfo("查找结果", f"未找到 '{search_term}'")
            return
        # 高亮第一个匹配项
        self.current_search_index = 0
        self.highlight_search_result()
        messagebox.showinfo("查找结果", f"找到 {len(self.search_positions)} 个匹配项")

    def search_next(self):
        """查找下一个"""
        if not self.search_positions:
            messagebox.showwarning("警告", "请先执行查找")
            return
        self.current_search_index = (self.current_search_index + 1) % len(self.search_positions)
        self.highlight_search_result()

    def search_prev(self):
        """查找上一个"""
        if not self.search_positions:
            messagebox.showwarning("警告", "请先执行查找")
            return
        self.current_search_index = (self.current_search_index - 1) % len(self.search_positions)
        self.highlight_search_result()

    def highlight_search_result(self):
        """高亮显示查找结果"""
        if not self.search_positions or self.current_search_index < 0:
            return
        text_widget = self.get_active_text_widget()
        if not text_widget:
            return
        # 清除之前的高亮
        text_widget.tag_remove("search_highlight", "1.0", tk.END)
        # 高亮当前匹配项
        pos = self.search_positions[self.current_search_index]
        search_term = self.search_entry.get().strip()
        end_pos = f"{pos}+{len(search_term)}c"
        # 添加高亮标签
        text_widget.tag_add("search_highlight", pos, end_pos)
        text_widget.tag_config("search_highlight", background="yellow")
        # 滚动到匹配位置
        text_widget.see(pos)
        # 更新位置信息
        total = len(self.search_positions)
        current = self.current_search_index + 1
        self.search_pos_label.configure(text=f"{current}/{total}")

    def export_to_excel_ui(self):
        """导出分析结果和词云数据到Excel"""
        try:
            # 检查是否有分析结果
            if not hasattr(self, 'last_analysis_result') or not self.last_analysis_result:
                messagebox.showwarning("警告", "请先进行股票分析,然后再导出结果")
                return
            # 选择保存路径,不设置初始文件名,让用户自由命名
            filepath = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[
                    ("Excel files", "*.xlsx"),
                    ("CSV files", "*.csv"),
                    ("All files", "*.*")
                ],
                initialdir=D_EXPORT_DIR,
                title="保存分析结果文件"
            )
            if filepath:
                # 显示导出进度
                progress_window = self._safe_toplevel(self.root)
                progress_window.title("导出中...")
                progress_window.geometry("300x100")
                progress_window.resizable(False, False)
                # 居中显示
                progress_window.transient(self.root)
                progress_window.grab_set()
                # 进度标签
                progress_label = ttk.Label(progress_window, text="正在导出分析结果...", font=("Arial", 10))
                progress_label.pack(pady=20)
                # 进度条
                progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
                progress_bar.pack(pady=10, padx=20, fill=tk.X)
                progress_bar.start()
                def run_excel_export():
                    try:
                        print(f"开始导出到: {filepath}")
                        success = self.export_to_excel(filepath)
                        # 关闭进度窗口
                        if hasattr(self, 'root') and self.root.winfo_exists():
                            self.root.after(0, progress_window.destroy)
                        if success:
                            # 检查是否实际生成了文件
                            if os.path.exists(filepath):
                                self.root.after(0, lambda: messagebox.showinfo(
                                    "导出成功",
                                    f"分析结果已成功导出到:\n{filepath}\n\n文件大小: {os.path.getsize(filepath)} 字节"
                                ))
                            else:
                                # 检查是否有CSV文件
                                csv_filepath = filepath.replace('.xlsx', '.csv')
                                if os.path.exists(csv_filepath):
                                    self.root.after(0, lambda: messagebox.showinfo(
                                        "导出成功",
                                        f"分析结果已导出为CSV文件:\n{csv_filepath}\n\n文件大小: {os.path.getsize(csv_filepath)} 字节"
                                    ))
                                else:
                                    self.root.after(0, lambda: messagebox.showerror("导出失败", "文件未生成,请检查错误信息"))
                        else:
                            self.root.after(0, lambda: messagebox.showerror("导出失败", "导出过程中发生错误,请查看控制台输出"))
                    except Exception as e:
                        print(f"导出线程异常: {e}")
                        import traceback
                        traceback.print_exc()
                        if hasattr(self, 'root') and self.root.winfo_exists():
                            self.root.after(0, progress_window.destroy)
                            self.root.after(0, lambda e=e: messagebox.showerror("导出错误", f"导出失败:{e!s}"))
                # 在后台线程中执行导出
                export_thread = threading.Thread(target=run_excel_export, daemon=True)
                export_thread.start()
        except Exception as e:
            print(f"导出UI异常: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", f"导出失败:{e!s}")

    def export_to_excel(self, filepath):
        """导出分析结果到Excel文件,保留文字格式"""
        try:
            print(f"开始导出Excel文件到: {filepath}")
            # 获取股票分析结果框的所有文字内容
            result_text = ""
            result_widget = self.get_active_result_widget()
            if result_widget:
                result_text = result_widget.get("1.0", tk.END).strip()
            # 如果没有结果文字,使用分析结果
            if not result_text and hasattr(self, 'last_analysis_result') and self.last_analysis_result:
                result_text = self.last_analysis_result
            if not result_text:
                print("没有分析结果可导出")
                return False
            # 将结果文字按行分割,便于在Excel中显示
            result_lines = result_text.split('\n')
            # 创建更详细的数据结构,使用多列来更好地组织内容
            export_data = []
            # 添加标题行
            export_data.append(['股票分析结果导出', '', '', ''])
            export_data.append(['导出时间', datetime.now().strftime("%Y-%m-%d %H:%M:%S"), '', ''])
            export_data.append(['导出工具', '股票分析工具', '', ''])
            export_data.append(['文件版本', 'v1.0', '', ''])
            export_data.append(['', '', '', ''])  # 空行
            # 添加分析结果内容标题
            export_data.append(['分析结果内容:', '', '', ''])
            export_data.append(['', '', '', ''])  # 空行
            # 将每一行结果添加到数据中,保持原有格式
            for line in result_lines:
                if line.strip():  # 只添加非空行
                    # 检查是否是表格行(包含多个空格分隔的数据)
                    if '  ' in line and not line.startswith('#'):
                        # 尝试按多个空格分割表格数据
                        import re
                        # 使用正则表达式按多个空格分割
                        parts = re.split(r'\s{2,}', line.strip())
                        if len(parts) > 1:
                            # 表格行,使用多列显示
                            row_data = parts[:4]  # 最多4列
                            while len(row_data) < 4:
                                row_data.append('')
                            export_data.append(row_data)
                        else:
                            # 普通行
                            export_data.append([line, '', '', ''])
                    else:
                        # 普通行,保持原有的缩进和格式
                        export_data.append([line, '', '', ''])
                else:
                    export_data.append(['', '', '', ''])  # 保留空行
            # 转换为DataFrame,使用多列来更好地显示内容
            df = pd.DataFrame(export_data, columns=['内容', '列2', '列3', '列4'])
            # 尝试不同的导出方法
            try:
                # 方法1: 使用openpyxl
                print("尝试使用openpyxl引擎导出...")
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    # 创建股票分析结果工作表
                    df.to_excel(writer, sheet_name='股票分析结果', index=False)
                    # 如果有词云图片,将图片拷贝到第二个sheet
                    wordcloud_path = os.path.join(D_OUTPUT_DIR, "wordcloud.png")
                    if os.path.exists(wordcloud_path):
                        print("发现词云图片,正在添加到Excel...")
                        try:
                            from openpyxl.drawing.image import Image
                            from openpyxl.utils import get_column_letter
                            # 创建词云工作表
                            wordcloud_sheet = writer.book.create_sheet("词云图片")
                            # 添加词云图片
                            img = Image(wordcloud_path)
                            # 调整图片大小以适应Excel
                            img.width = 400
                            img.height = 300
                            wordcloud_sheet.add_image(img, 'A1')
                            # 添加图片信息
                            wordcloud_sheet['A15'] = '词云图片信息'
                            wordcloud_sheet['A16'] = f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                            wordcloud_sheet['A17'] = f'图片文件: {wordcloud_path}'
                            wordcloud_sheet['A18'] = f'图片路径: {os.path.abspath(wordcloud_path)}'
                            print("词云图片已成功添加到Excel")
                        except Exception as img_error:
                            print(f"添加词云图片失败: {img_error}")
                            # 如果图片添加失败,创建词云信息sheet
                            wordcloud_info = {
                                '词云信息': [
                                    '词云图片已生成',
                                    f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                                    '词云图片文件: wordcloud.png',
                                    '图片路径: ' + os.path.abspath("wordcloud.png"),
                                    f'图片添加失败: {img_error!s}'
                                ]
                            }
                            wordcloud_df = pd.DataFrame(wordcloud_info)
                            wordcloud_df.to_excel(writer, sheet_name='词云信息', index=False)
                    else:
                        print("未找到词云图片文件")
                print("Excel文件导出成功!")
                return True
            except ImportError as e:
                print(f"openpyxl不可用: {e}")
                try:
                    # 方法2: 使用xlsxwriter
                    print("尝试使用xlsxwriter引擎导出...")
                    with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
                        df.to_excel(writer, sheet_name='股票分析结果', index=False)
                        # 如果有词云图片,添加词云信息
                        wordcloud_path = "wordcloud.png"
                        if os.path.exists(wordcloud_path):
                            print("发现词云图片,正在添加词云信息...")
                            wordcloud_info = {
                                '词云信息': [
                                    '词云图片已生成',
                                    f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                                    '词云图片文件: wordcloud.png',
                                    '图片路径: ' + os.path.abspath("wordcloud.png"),
                                    '注意: xlsxwriter不支持直接插入图片,请查看wordcloud.png文件'
                                ]
                            }
                            wordcloud_df = pd.DataFrame(wordcloud_info)
                            wordcloud_df.to_excel(writer, sheet_name='词云信息', index=False)
                    print("Excel文件导出成功!")
                    return True
                except ImportError as e2:
                    print(f"xlsxwriter也不可用: {e2}")
                    try:
                        # 方法3: 使用默认引擎
                        print("尝试使用默认引擎导出...")
                        df.to_excel(filepath, sheet_name='股票分析结果', index=False)
                        print("Excel文件导出成功!")
                        return True
                    except Exception as e3:
                        print(f"默认引擎也失败: {e3}")
                        # 方法4: 导出为CSV作为备选
                        print("尝试导出为CSV文件...")
                        csv_filepath = filepath.replace('.xlsx', '.csv')
                        df.to_csv(csv_filepath, index=False, encoding='utf-8-sig')
                        print(f"已导出为CSV文件: {csv_filepath}")
                        return True
            except Exception as e:
                print(f"Excel导出过程中出错: {e}")
                # 最后的备选方案:导出为CSV
                try:
                    print("尝试导出为CSV文件作为备选...")
                    csv_filepath = filepath.replace('.xlsx', '.csv')
                    df.to_csv(csv_filepath, index=False, encoding='utf-8-sig')
                    print(f"已导出为CSV文件: {csv_filepath}")
                    return True
                except Exception as csv_e:
                    print(f"CSV导出也失败: {csv_e}")
                    return False
        except Exception as e:
            print(f"导出Excel失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def create_long_image(self, filepath):
        """创建长图,包含分析结果和词云"""
        try:
            # 检查词云图片是否存在
            wordcloud_path = "wordcloud.png"
            if not os.path.exists(wordcloud_path):
                raise FileNotFoundError("词云图片不存在,请先生成词云")
            # 创建画布
            # 加载词云图片
            wordcloud_img = Image.open(wordcloud_path)
            wordcloud_width, wordcloud_height = wordcloud_img.size
            # 计算分析结果文本的高度
            result_text = self.last_analysis_result
            lines = result_text.split('\n')
            # 设置字体和行高
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 16)
            except:
                font = ImageFont.load_default()
            # 获取行高(兼容不同版本的PIL)
            try:
                # 新版本PIL
                line_height = font.getbbox("测试")[3] + 5
            except:
                try:
                    # 旧版本PIL
                    line_height = font.getsize("测试")[1] + 5
                except:
                    line_height = 20  # 默认行高
            text_height = len(lines) * line_height
            # 计算总高度和宽度
            total_height = text_height + wordcloud_height + 100  # 100是间距
            total_width = max(800, wordcloud_width)  # 至少800像素宽
            # 创建长图
            long_image = Image.new('RGB', (total_width, total_height), 'white')
            draw = ImageDraw.Draw(long_image)
            # 绘制标题
            title = "股票分析结果报告"
            try:
                title_font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 24)
            except:
                title_font = ImageFont.load_default()
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (total_width - title_width) // 2
            draw.text((title_x, 20), title, fill='black', font=title_font)
            # 绘制分析结果文本
            y_offset = 80
            for line in lines:
                if line.strip():
                    draw.text((20, y_offset), line, fill='black', font=font)
                y_offset += line_height
            # 绘制分隔线
            separator_y = y_offset + 20
            draw.line([(20, separator_y), (total_width - 20, separator_y)], fill='gray', width=2)
            # 绘制词云标题
            wordcloud_title = "词云分析"
            wordcloud_title_bbox = draw.textbbox((0, 0), wordcloud_title, font=title_font)
            wordcloud_title_width = wordcloud_title_bbox[2] - wordcloud_title_bbox[0]
            wordcloud_title_x = (total_width - wordcloud_title_width) // 2
            draw.text((wordcloud_title_x, separator_y + 20), wordcloud_title, fill='black', font=title_font)
            # 粘贴词云图片
            wordcloud_x = (total_width - wordcloud_width) // 2
            wordcloud_y = separator_y + 60
            long_image.paste(wordcloud_img, (wordcloud_x, wordcloud_y))
            # 绘制时间戳
            timestamp = datetime.now().strftime("生成时间:%Y-%m-%d %H:%M:%S")
            timestamp_bbox = draw.textbbox((0, 0), timestamp, font=font)
            timestamp_width = timestamp_bbox[2] - timestamp_bbox[0]
            timestamp_x = total_width - timestamp_width - 20
            timestamp_y = total_height - 30
            draw.text((timestamp_x, timestamp_y), timestamp, fill='gray', font=font)
            # 保存长图
            long_image.save(filepath, 'PNG', quality=95)
        except Exception as e:
            raise Exception(f"创建长图失败:{e!s}")

    def update_result_text(self, result):
        """更新结果文本框(线程安全)"""
        try:
            result_widget = self.get_active_result_widget()
            if result_widget:
                result_widget.delete("1.0", tk.END)
                if result:
                    result_widget.insert("1.0", result)
                    print(f"✅ 分析结果已更新,长度: {len(result)} 字符")
                else:
                    result_widget.insert("1.0", "❌ 分析结果为空")
                    print("⚠️ 分析结果为空")
        except Exception as e:
            print(f"更新结果文本框失败: {e}")

    def create_context_menu(self):
        """创建右键菜单"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="📋 粘贴", command=self.on_paste)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📋 粘贴网页内容", command=self.paste_webpage_with_images)
        self.context_menu.add_command(label="📋 粘贴纯文本", command=self.paste_text)
        self.context_menu.add_separator()
        # OCR识别菜单项已移除
        self.context_menu.add_separator()
        def get_text_widget():
            return self.get_active_text_widget()
        self.context_menu.add_command(label="✂️ 剪切", command=lambda: get_text_widget().event_generate("<<Cut>>") if get_text_widget() else None)
        self.context_menu.add_command(label="📄 复制", command=lambda: get_text_widget().event_generate("<<Copy>>") if get_text_widget() else None)
        self.context_menu.add_command(label="🗑️ 删除", command=lambda: get_text_widget().event_generate("<<Clear>>") if get_text_widget() else None)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🔄 全选", command=lambda: get_text_widget().event_generate("<<SelectAll>>") if get_text_widget() else None)
        self.context_menu.add_command(label="🧹 清空", command=self.clear_content)

    def show_context_menu(self, event):
        """显示右键菜单"""
        try:
            # 更新菜单状态
            self.update_context_menu_state()
            # 显示菜单
            self.context_menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            print(f"显示右键菜单失败: {e}")

    def update_context_menu_state(self):
        """更新右键菜单状态"""
        try:
            text_widget = self.get_active_text_widget()
            # 检查是否有选中文本
            try:
                if text_widget:
                    selected_text = text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
                    has_selection = bool(selected_text.strip())
                else:
                    has_selection = False
            except:
                has_selection = False
            # 检查是否有剪贴板内容
            try:
                clipboard_content = self.root.clipboard_get()
                has_clipboard = bool(clipboard_content.strip())
            except:
                has_clipboard = False
            # 检查是否有图片
            if text_widget:
                text_widget.get("1.0", tk.END)
            else:
                pass
            # 更新菜单项状态
            self.context_menu.entryconfig("✂️ 剪切", state="normal" if has_selection else "disabled")
            self.context_menu.entryconfig("📄 复制", state="normal" if has_selection else "disabled")
            self.context_menu.entryconfig("🗑️ 删除", state="normal" if has_selection else "disabled")
            self.context_menu.entryconfig("📋 粘贴", state="normal" if has_clipboard else "disabled")
            # OCR识别菜单状态配置已移除
        except Exception as e:
            print(f"更新右键菜单状态失败: {e}")

    def insert_colored_result(self, result):
        """插入带颜色的分析结果"""
        try:
            result_widget = self.get_active_result_widget()
            if not result_widget:
                return
            lines = result.split('\n')
            current_pos = "1.0"
            for line in lines:
                # 插入文本
                result_widget.insert(current_pos, line + '\n')
                # 应用颜色标签
                if "5日涨跌幅" in line and "总计" not in line:
                    # 五日涨跌幅用黑色
                    start_pos = current_pos
                    end_pos = result_widget.index(f"{current_pos}+{len(line)}c")
                    result_widget.tag_add("five_day_daily", start_pos, end_pos)
                elif "5日总计" in line:
                    # 5日总计用红色
                    start_pos = current_pos
                    end_pos = result_widget.index(f"{current_pos}+{len(line)}c")
                    result_widget.tag_add("five_day_total", start_pos, end_pos)
                elif "10日总计" in line:
                    # 10日总计用橙色
                    start_pos = current_pos
                    end_pos = result_widget.index(f"{current_pos}+{len(line)}c")
                    result_widget.tag_add("ten_day_total", start_pos, end_pos)
                elif "20日总计" in line:
                    # 20日总计用绿色
                    start_pos = current_pos
                    end_pos = result_widget.index(f"{current_pos}+{len(line)}c")
                    result_widget.tag_add("twenty_day_total", start_pos, end_pos)
                # 检查涨跌幅数值的颜色
                import re
                change_pattern = r'([+-]?\d+\.?\d*%)'
                matches = re.finditer(change_pattern, line)
                for match in matches:
                    start_pos = result_widget.index(f"{current_pos}+{match.start()}c")
                    end_pos = result_widget.index(f"{current_pos}+{match.end()}c")
                    # 根据行内容确定颜色标签
                    if "5日涨跌幅" in line and "总计" not in line:
                        # 五日涨跌幅数值用黑色
                        result_widget.tag_add("five_day_daily", start_pos, end_pos)
                    elif "5日总计" in line:
                        # 5日总计数值用红色
                        result_widget.tag_add("five_day_total", start_pos, end_pos)
                    elif "10日总计" in line:
                        # 10日总计数值用橙色
                        result_widget.tag_add("ten_day_total", start_pos, end_pos)
                    elif "20日总计" in line:
                        # 20日总计数值用绿色
                        result_widget.tag_add("twenty_day_total", start_pos, end_pos)
                    else:
                        # 其他情况根据正负值设置颜色
                        value = match.group(1)
                        if value.startswith('+') or (not value.startswith('-') and float(value.replace('%', '')) > 0):
                            result_widget.tag_add("positive", start_pos, end_pos)
                        elif value.startswith('-') or float(value.replace('%', '')) < 0:
                            result_widget.tag_add("negative", start_pos, end_pos)
                # 更新位置
                current_pos = result_widget.index(tk.END + "-1c")
        except Exception as e:
            # 如果彩色插入失败,使用普通插入
            result_widget = self.get_active_result_widget()
            if result_widget:
                result_widget.insert("1.0", result)
            print(f"彩色文本插入失败,使用普通插入: {e}")

    def display_image_in_frame(self, photo, title, image, image_type):
        """在图片显示区域显示图片"""
        try:
            # 创建图片容器
            image_container = ttk.Frame(self.image_display_frame)
            image_container.pack(fill=tk.X, pady=2)
            # 创建标题标签
            title_label = ttk.Label(image_container, text=title, font=("TkDefaultFont", 12, "bold"))
            title_label.pack(anchor=tk.W)
            # 创建图片标签
            image_label = ttk.Label(image_container, image=photo)
            image_label.pack(anchor=tk.W, pady=(2, 0))
            # OCR按钮已移除
            # 存储图片引用
            image_label.image = photo  # 保持引用
        except Exception as e:
            print(f"显示图片失败: {e}")

    def show_market_overview(self):
        """显示大盘一览界面"""
        try:
            # 创建新窗口
            market_window = self._safe_toplevel(self.root)
            market_window.title("📊 大盘一览 - A股市场分析")
            market_window.geometry("1200x800")
            market_window.configure(bg='#f0f0f0')
            market_window.resizable(True, True)
            # 存储窗口状态
            market_window._is_minimized = False
            market_window._original_geometry = "1200x800"
            # 设置窗口图标
            try:
                market_window.iconbitmap('icon.ico')
            except:
                pass
            # 创建主框架
            main_frame = ttk.Frame(market_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            # 标题
            title_label = ttk.Label(main_frame, text="📊 A股大盘一览", font=("Arial", 16, "bold"))
            title_label.pack(pady=(0, 10))
            # 创建滚动框架
            canvas = tk.Canvas(main_frame, bg='#f0f0f0')
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            # 加载数据按钮
            load_button = ttk.Button(scrollable_frame, text="🔄 刷新数据",
                                   command=lambda: self.load_market_data(scrollable_frame))
            load_button.pack(pady=(0, 10))
            # 初始加载数据
            self.load_market_data(scrollable_frame)
            # 布局滚动组件
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            # 绑定鼠标滚轮事件
            def _on_mousewheel(event):
                try:
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                except (tk.TclError, AttributeError, RuntimeError):
                    pass
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            # 窗口关闭时解绑事件
            def on_closing():
                try:
                    canvas.unbind_all("<MouseWheel>")
                except:
                    pass
                market_window.destroy()
            market_window.protocol("WM_DELETE_WINDOW", on_closing)
            # 窗口控制按钮
            control_btn_frame = ttk.Frame(market_window)
            control_btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            def toggle_minimize():
                """切换最小化/恢复"""
                if market_window._is_minimized:
                    market_window.geometry(market_window._original_geometry)
                    market_window._is_minimized = False
                    minimize_btn.config(text="最小化")
                else:
                    market_window._original_geometry = market_window.geometry()
                    market_window.geometry("200x50")
                    market_window._is_minimized = True
                    minimize_btn.config(text="恢复")
            def toggle_maximize():
                """切换最大化/恢复"""
                try:
                    if market_window.state() == 'zoomed':
                        market_window.state('normal')
                        market_window.geometry(market_window._original_geometry)
                        maximize_btn.config(text="最大化")
                    else:
                        market_window._original_geometry = market_window.geometry()
                        market_window.state('zoomed')
                        maximize_btn.config(text="恢复")
                except:
                    try:
                        current_geom = market_window.geometry()
                        if hasattr(market_window, '_is_maximized') and market_window._is_maximized:
                            market_window.geometry(market_window._original_geometry)
                            market_window._is_maximized = False
                            maximize_btn.config(text="最大化")
                        else:
                            market_window._original_geometry = current_geom
                            screen_width = market_window.winfo_screenwidth()
                            screen_height = market_window.winfo_screenheight()
                            market_window.geometry(f"{screen_width}x{screen_height}+0+0")
                            market_window._is_maximized = True
                            maximize_btn.config(text="恢复")
                    except Exception as e:
                        messagebox.showinfo("提示", f"最大化功能不可用: {e}")
            minimize_btn = ttk.Button(control_btn_frame, text="最小化", command=toggle_minimize, width=10)
            minimize_btn.pack(side=tk.LEFT, padx=5)
            maximize_btn = ttk.Button(control_btn_frame, text="最大化", command=toggle_maximize, width=10)
            maximize_btn.pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="隐藏", command=market_window.withdraw, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="显示", command=market_window.deiconify, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="关闭", command=on_closing, width=10).pack(side=tk.RIGHT, padx=5)
        except Exception as e:
            messagebox.showerror("错误", f"打开大盘一览失败: {e!s}")

    def load_market_data(self, parent_frame):
        """加载市场数据到界面"""
        try:
            # 清除现有内容(除了刷新按钮)
            for widget in parent_frame.winfo_children():
                if isinstance(widget, ttk.Button) and "刷新数据" in widget.cget("text"):
                    continue
                widget.destroy()
            # 显示加载状态
            loading_label = ttk.Label(parent_frame, text="🔄 正在获取市场数据...", font=("Arial", 12))
            loading_label.pack(pady=10)
            parent_frame.update()
            # 获取市场数据
            market_data = get_market_overview_data()
            # 移除加载标签
            loading_label.destroy()
            if not market_data:
                error_label = ttk.Label(parent_frame, text="❌ 获取市场数据失败,请稍后重试",
                                      font=("Arial", 12), foreground="red")
                error_label.pack(pady=10)
                return
            # 显示主要指数
            if any(key in market_data for key in ['上证指数', '深证成指', '创业板指']):
                self.create_index_section(parent_frame, market_data)
            # 显示市场估值
            if '市场PE' in market_data:
                self.create_valuation_section(parent_frame, market_data['市场PE'])
            # 显示债券市场
            if '债券市场' in market_data:
                self.create_bond_section(parent_frame, market_data['债券市场'])
            # 显示资金流向
            if '北向资金' in market_data or '融资融券' in market_data:
                self.create_money_flow_section(parent_frame, market_data)
            # 显示热门指数
            if '热门指数' in market_data:
                self.create_hot_indices_section(parent_frame, market_data['热门指数'])
            # 显示行业板块
            if '行业板块' in market_data:
                self.create_industry_section(parent_frame, market_data['行业板块'])
            # 显示更新时间
            update_time = ttk.Label(parent_frame, text=f"📅 数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                  font=("Arial", 10), foreground="gray")
            update_time.pack(pady=(20, 0))
        except Exception as e:
            print(f"加载市场数据失败: {e}")
            error_label = ttk.Label(parent_frame, text=f"❌ 加载数据失败: {e!s}",
                                  font=("Arial", 12), foreground="red")
            error_label.pack(pady=10)

    def create_index_section(self, parent, data):
        """创建主要指数显示区域"""
        # 指数框架
        index_frame = ttk.LabelFrame(parent, text="📈 主要指数", padding=10)
        index_frame.pack(fill=tk.X, pady=(0, 10))
        # 创建网格布局
        for i, (index_name, index_data) in enumerate(data.items()):
            if index_name in ['上证指数', '深证成指', '创业板指']:
                # 每个指数一行
                index_row = ttk.Frame(index_frame)
                index_row.pack(fill=tk.X, pady=2)
                # 指数名称
                name_label = ttk.Label(index_row, text=index_name, font=("Arial", 12, "bold"), width=8)
                name_label.pack(side=tk.LEFT, padx=(0, 10))
                # 最新价
                price = index_data.get('最新价', 0)
                price_label = ttk.Label(index_row, text=f"{price:.2f}", font=("Arial", 12, "bold"))
                price_label.pack(side=tk.LEFT, padx=(0, 10))
                # 涨跌幅
                change_pct = index_data.get('涨跌幅', 0)
                change_color = "red" if change_pct > 0 else "green" if change_pct < 0 else "black"
                change_label = ttk.Label(index_row, text=f"{change_pct:+.2f}%",
                                       font=("Arial", 12, "bold"), foreground=change_color)
                change_label.pack(side=tk.LEFT, padx=(0, 10))
                # 涨跌额
                change_amt = index_data.get('涨跌额', 0)
                change_amt_label = ttk.Label(index_row, text=f"{change_amt:+.2f}",
                                           font=("Arial", 11), foreground=change_color)
                change_amt_label.pack(side=tk.LEFT, padx=(0, 10))
                # 成交额
                amount = index_data.get('成交额', 0)
                amount_label = ttk.Label(index_row, text=f"成交额: {amount/100000000:.1f}亿",
                                       font=("Arial", 10))
                amount_label.pack(side=tk.LEFT)

    def create_valuation_section(self, parent, pe_data):
        """创建市场估值显示区域"""
        valuation_frame = ttk.LabelFrame(parent, text="💰 市场估值", padding=10)
        valuation_frame.pack(fill=tk.X, pady=(0, 10))
        # PE数据
        pe_value = pe_data.get('整体PE', 0)
        pb_value = pe_data.get('整体PB', 0)
        date = pe_data.get('日期', '')
        pe_label = ttk.Label(valuation_frame, text=f"整体PE: {pe_value}", font=("Arial", 12, "bold"))
        pe_label.pack(anchor=tk.W)
        pb_label = ttk.Label(valuation_frame, text=f"整体PB: {pb_value}", font=("Arial", 12, "bold"))
        pb_label.pack(anchor=tk.W)
        if date:
            date_label = ttk.Label(valuation_frame, text=f"数据日期: {date}", font=("Arial", 10), foreground="gray")
            date_label.pack(anchor=tk.W)

    def create_bond_section(self, parent, bond_data):
        """创建债券市场显示区域"""
        bond_frame = ttk.LabelFrame(parent, text="🏦 债券市场", padding=10)
        bond_frame.pack(fill=tk.X, pady=(0, 10))
        bond_yield = bond_data.get('10年期国债收益率', 0)
        date = bond_data.get('日期', '')
        yield_label = ttk.Label(bond_frame, text=f"10年期国债收益率: {bond_yield}%",
                              font=("Arial", 12, "bold"))
        yield_label.pack(anchor=tk.W)
        if date:
            date_label = ttk.Label(bond_frame, text=f"数据日期: {date}", font=("Arial", 10), foreground="gray")
            date_label.pack(anchor=tk.W)

    def create_money_flow_section(self, parent, data):
        """创建资金流向显示区域"""
        money_frame = ttk.LabelFrame(parent, text="💸 资金流向", padding=10)
        money_frame.pack(fill=tk.X, pady=(0, 10))
        # 北向资金
        if '北向资金' in data:
            northbound = data['北向资金']
            net_buy = northbound.get('净买入额', 0)
            buy_amount = northbound.get('买入额', 0)
            sell_amount = northbound.get('卖出额', 0)
            date = northbound.get('日期', '')
            net_color = "red" if net_buy > 0 else "green" if net_buy < 0 else "black"
            net_label = ttk.Label(money_frame, text=f"北向资金净买入: {net_buy/100000000:.2f}亿",
                                font=("Arial", 12, "bold"), foreground=net_color)
            net_label.pack(anchor=tk.W)
            buy_label = ttk.Label(money_frame, text=f"买入: {buy_amount/100000000:.2f}亿", font=("Arial", 11))
            buy_label.pack(anchor=tk.W)
            sell_label = ttk.Label(money_frame, text=f"卖出: {sell_amount/100000000:.2f}亿", font=("Arial", 11))
            sell_label.pack(anchor=tk.W)
            if date:
                date_label = ttk.Label(money_frame, text=f"数据日期: {date}", font=("Arial", 10), foreground="gray")
                date_label.pack(anchor=tk.W)
        # 融资融券
        if '融资融券' in data:
            margin = data['融资融券']
            margin_balance = margin.get('融资余额', 0)
            short_balance = margin.get('融券余额', 0)
            margin_buy = margin.get('融资买入额', 0)
            margin_label = ttk.Label(money_frame, text=f"融资余额: {margin_balance/100000000:.2f}亿",
                                   font=("Arial", 11))
            margin_label.pack(anchor=tk.W)
            short_label = ttk.Label(money_frame, text=f"融券余额: {short_balance/100000000:.2f}亿",
                                  font=("Arial", 11))
            short_label.pack(anchor=tk.W)
            buy_label = ttk.Label(money_frame, text=f"融资买入: {margin_buy/100000000:.2f}亿",
                                font=("Arial", 11))
            buy_label.pack(anchor=tk.W)

    def create_industry_section(self, parent, industries):
        """创建行业板块显示区域"""
        industry_frame = ttk.LabelFrame(parent, text="🏭 行业板块排行", padding=10)
        industry_frame.pack(fill=tk.X, pady=(0, 10))
        # 表头
        header_frame = ttk.Frame(industry_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(header_frame, text="板块名称", font=("Arial", 10, "bold"), width=15).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="涨跌幅", font=("Arial", 10, "bold"), width=10).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="涨跌额", font=("Arial", 10, "bold"), width=10).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="成交额", font=("Arial", 10, "bold"), width=15).pack(side=tk.LEFT)
        # 分隔线
        separator = ttk.Separator(industry_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=2)
        # 行业数据
        for industry in industries[:10]:  # 显示前10个
            row_frame = ttk.Frame(industry_frame)
            row_frame.pack(fill=tk.X, pady=1)
            name = industry.get('板块名称', '')
            change_pct = industry.get('涨跌幅', 0)
            change_amt = industry.get('涨跌额', 0)
            amount = industry.get('成交额', 0)
            # 涨跌幅颜色
            change_color = "red" if change_pct > 0 else "green" if change_pct < 0 else "black"
            ttk.Label(row_frame, text=name, width=15).pack(side=tk.LEFT)
            ttk.Label(row_frame, text=f"{change_pct:+.2f}%", width=10,
                     foreground=change_color).pack(side=tk.LEFT)
            ttk.Label(row_frame, text=f"{change_amt:+.2f}", width=10,
                     foreground=change_color).pack(side=tk.LEFT)
            ttk.Label(row_frame, text=f"{amount/100000000:.1f}亿", width=15).pack(side=tk.LEFT)

    def translate_left_tab_to_right_result(self):
        """将左侧活动标签页内容翻译到右侧新结果标签页"""
        text = self.get_current_text()
        if not text:
            messagebox.showwarning("警告", "左侧标签页没有可翻译的内容")
            return
        self.translation_stop_flag = False
        try:
            self.translate_run_btn.state(['disabled'])
            self.translate_stop_btn.state(['!disabled'])
        except Exception:
            pass
        # 生成右侧标签名:左边前5字 + "翻译"
        left_title = self.get_active_text_title() or "未命名"
        new_tab_title = f"{left_title[:5]}翻译"
        tab_id = self.create_result_tab(new_tab_title)
        result_widget = self.result_tabs[tab_id]['widget']
        result_widget.delete("1.0", tk.END)
        result_widget.insert(tk.END, "翻译中,请稍候...\n")
        def translate_worker():
            try:
                sentences = re.split(r'[。!?;;.!?\n]+', text)
                sentences = [re.sub(r'\s+', '', s).strip() for s in sentences if re.sub(r'\s+', '', s).strip()]
                if not sentences:
                    self.root.after(0, lambda: (
                        result_widget.delete("1.0", tk.END),
                        result_widget.insert(tk.END, "没有可翻译的句子。")
                    ))
                    return
                # 读取语言和引擎设置
                try:
                    src_lang = self.languages.get(getattr(self, 'source_lang_var', tk.StringVar(value="中文")).get(), "zh")
                    tgt_lang = self.languages.get(getattr(self, 'target_lang_var', tk.StringVar(value="英语")).get(), "en")
                except Exception:
                    src_lang, tgt_lang = "zh", "en"
                engine = getattr(self, 'engine_var', tk.StringVar(value="有道翻译")).get()
                total = len(sentences)
                for idx, s in enumerate(sentences):
                    if self.translation_stop_flag:
                        def stopped_msg():
                            result_widget.insert(tk.END, f"\n已终止,已翻译 {idx}/{total} 句。")
                            result_widget.see(tk.END)
                        self.root.after(0, stopped_msg)
                        break
                    try:
                        if engine == "百度翻译":
                            dst = self._baidu_translate(s, src_lang, tgt_lang)
                        elif engine == "有道翻译":
                            dst = self._youdao_translate(s, src_lang, tgt_lang)
                        elif engine == "Google翻译":
                            dst = self._google_translate(s, src_lang, tgt_lang)
                        else:
                            dst = "不支持的翻译引擎"
                    except Exception as inner_e:
                        dst = f"翻译失败: {inner_e!s}"
                    def append_once(src=s, tgt=dst):
                        result_widget.insert(tk.END, f"{src}  →  {tgt}\n")
                        result_widget.see(tk.END)
                    self.root.after(0, append_once)
                    time.sleep(0.2)
                def finish_ok():
                    result_widget.insert(tk.END, "\n翻译完成。")
                    result_widget.see(tk.END)
                    try:
                        messagebox.showinfo("成功", f"翻译完成,共 {total} 句")
                    except Exception:
                        pass
                self.root.after(0, finish_ok)
            except Exception as e:
                def finish_err(e=e):
                    result_widget.delete("1.0", tk.END)
                    result_widget.insert(tk.END, f"翻译失败: {e}")
                    try:
                        messagebox.showerror("错误", f"翻译失败: {e}")
                    except Exception:
                        pass
                self.root.after(0, finish_err)
            finally:
                def reset_btns():
                    try:
                        self.translate_run_btn.state(['!disabled'])
                        self.translate_stop_btn.state(['disabled'])
                    except Exception:
                        pass
                self.root.after(0, reset_btns)
        threading.Thread(target=translate_worker, daemon=True).start()

    def stop_translation_to_right(self):
        """终止翻译"""
        self.translation_stop_flag = True

    def _youdao_translate(self, text, source_lang, target_lang):
        """有道翻译(参照 translator_gui.py)"""
        app_id = "3d7d5287500ee1ef"
        app_key = "U4uLG6Ar04XzVj8ajJ3JTkW74QcRWcC7"
        api_url = "https://openapi.youdao.com/api"
        if not text:
            return ""
        import hashlib
        import random
        salt = str(random.randint(10000, 99999))
        sign_str = app_id + text + salt + app_key
        sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
        params = {
            'q': text,
            'from': source_lang,
            'to': target_lang,
            'appKey': app_id,
            'salt': salt,
            'sign': sign
        }
        response = requests.post(api_url, data=params, timeout=20)
        result = response.json()
        if 'translation' in result:
            return result['translation'][0]
        return f"翻译失败: {result.get('errorMessage', '未知错误')}"

    def _baidu_translate(self, text, source_lang, target_lang):
        """百度翻译"""
        config = self.translation_engines.get("百度翻译", {})
        app_id = config.get("app_id")
        app_key = config.get("app_key")
        api_url = config.get("api_url")
        if not (app_id and app_key and api_url):
            return "请配置百度翻译API密钥"
        import hashlib
        import random
        salt = str(random.randint(32768, 65536))
        sign_raw = app_id + text + salt + app_key
        sign = hashlib.md5(sign_raw.encode()).hexdigest()
        params = {
            'q': text,
            'from': source_lang,
            'to': target_lang,
            'appid': app_id,
            'salt': salt,
            'sign': sign
        }
        response = requests.get(api_url, params=params, timeout=20)
        result = response.json()
        if 'trans_result' in result:
            return result['trans_result'][0]['dst']
        return f"翻译失败: {result.get('error_msg', '未知错误')}"

    def _google_translate(self, text, source_lang, target_lang):
        """Google翻译"""
        config = self.translation_engines.get("Google翻译", {})
        api_url = config.get("api_url")
        api_key = config.get("api_key")
        if not (api_url and api_key) or api_key == "YOUR_GOOGLE_API_KEY":
            return "请配置Google翻译API密钥"
        params = {
            'q': text,
            'source': source_lang,
            'target': target_lang,
            'key': api_key
        }
        response = requests.post(api_url, data=params, timeout=20)
        result = response.json()
        if 'data' in result and 'translations' in result['data']:
            return result['data']['translations'][0]['translatedText']
        return f"翻译失败: {result.get('error', {}).get('message', '未知错误')}"

    def show_reference_overview(self):
        """参考一览:可新增/删除/修改 名称和链接,支持爬取"""
        try:
            win = self._safe_toplevel(self.root)
            win.title("参考一览")
            win.geometry("1200x700")
            win.resizable(True, True)
            # 存储窗口状态
            win._is_minimized = False
            win._original_geometry = "1200x700"
            refs_path = os.path.join(_APP_CONFIG_DIR, "references.json")
            default_sites = [
                # 国内主流财经
                ("东方财富", "https://www.eastmoney.com/"),
                ("同花顺财经", "https://news.10jqka.com.cn/"),
                ("上证报", "https://www.cnstock.com/"),
                ("证券时报", "https://www.stcn.com/"),
                ("第一财经", "https://www.yicai.com/"),
                ("新浪财经", "https://finance.sina.com.cn/"),
                ("财联社", "https://www.cls.cn/"),
                ("选股宝", "https://xuangubao.cn/"),
                ("淘股吧", "https://www.taoguba.com.cn/"),
                ("东方财富股吧", "https://guba.eastmoney.com/"),
                ("雪球", "https://xueqiu.com/"),
                ("21财经", "https://www.21jingji.com/"),
                ("和讯财经", "https://www.hexun.com/"),
                ("华尔街见闻", "https://wallstreetcn.com/"),
                ("央视财经", "https://finance.cctv.com/"),
                ("界面新闻", "https://www.jiemian.com/finance.shtml"),
                ("蓝鲸财经", "https://www.lanjinger.com/"),
                ("每日经济新闻", "https://www.nbd.com.cn/"),
                ("财新网", "https://www.caixin.com/"),
                ("中国基金报", "https://www.chnfund.com/"),
                ("券商中国", "https://www.stcn.com/qs/"),
                ("中证网", "http://www.cs.com.cn/"),
                ("经济参考网", "http://www.jjckb.cn/"),
                ("中新经纬", "https://www.jwview.com/"),
                ("证券日报网", "http://www.zqrb.cn/"),
                ("中国新闻网财经", "https://www.chinanews.com.cn/finance/"),
                ("网易财经", "https://money.163.com/"),
                ("搜狐财经", "https://business.sohu.com/"),
                ("凤凰财经", "https://finance.ifeng.com/"),
                ("腾讯财经", "https://finance.qq.com/"),
                ("韭研公社", "https://www.gogudata.com/"),
                # A股内参及24小时实时信息
                ("财联社内参", "https://www.cls.cn/telegraph"),
                ("选股宝内参", "https://xuangubao.cn/neican"),
                ("同花顺内参", "https://news.10jqka.com.cn/stock/"),
                ("东方财富内参", "https://finance.eastmoney.com/news/"),
                ("雪球24小时", "https://xueqiu.com/statuses/hot"),
                ("淘股吧实时", "https://www.taoguba.com.cn/Article"),
                ("韭研公社实时", "https://www.gogudata.com/"),
                # 国际英语主流经济新闻(国内可访问)
                ("Reuters", "https://www.reuters.com/finance/"),
                ("Bloomberg", "https://www.bloomberg.com/markets"),
                ("Financial Times", "https://www.ft.com/"),
                ("WSJ", "https://www.wsj.com/"),
                ("CNBC", "https://www.cnbc.com/world/?region=world"),
                ("Yahoo Finance", "https://finance.yahoo.com/"),
                ("MarketWatch", "https://www.marketwatch.com/"),
                ("Barron's", "https://www.barrons.com/"),
                ("The Economist", "https://www.economist.com/"),
                ("Business Insider", "https://www.businessinsider.com/"),
                ("Forbes", "https://www.forbes.com/"),
                ("Fortune", "https://fortune.com/"),
                ("NPR Business", "https://www.npr.org/sections/business/"),
                ("AP Business", "https://apnews.com/hub/business"),
                ("New York Times Business", "https://www.nytimes.com/section/business"),
                ("Washington Post Business", "https://www.washingtonpost.com/business/"),
                ("The Atlantic Economy", "https://www.theatlantic.com/economy/"),
                ("Morningstar", "https://www.morningstar.com/"),
                ("Seeking Alpha", "https://seekingalpha.com/"),
                ("Investopedia", "https://www.investopedia.com/"),
                ("BBC Business", "https://www.bbc.com/news/business"),
                ("The Guardian Business", "https://www.theguardian.com/uk/business"),
                ("Al Jazeera Business", "https://www.aljazeera.com/economy/"),
                # 日语主流经济新闻(国内可访问)
                ("日経新聞", "https://www.nikkei.com/"),
                ("日本経済新聞", "https://www.nikkei.com/"),
                ("東洋経済", "https://toyokeizai.net/"),
                ("ダイヤモンド", "https://diamond.jp/"),
                ("週刊エコノミスト", "https://weekly-economist.mainichi.jp/"),
                ("日本経済新聞 中国", "https://cn.nikkei.com/"),
            ]
            def load_refs():
                try:
                    if os.path.exists(refs_path):
                        with open(refs_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if not isinstance(data, list):
                                data = []
                    else:
                        data = []
                    # 合并默认站点(去重)
                    existing = {(d.get("name",""), d.get("url","")) for d in data}
                    for name, url in default_sites:
                        if (name, url) not in existing:
                            data.append({"name": name, "url": url})
                    return data
                except Exception:
                    return [{"name": n, "url": u} for n, u in default_sites]
            def save_refs(data):
                try:
                    with open(refs_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    return True
                except Exception as e:
                    messagebox.showerror("错误", f"保存失败: {e}")
                    return False
            # 主框架:左侧显示列表,右侧操作按钮
            main_frame = ttk.Frame(win)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            # 左侧:三列显示区域
            left_frame = ttk.Frame(main_frame)
            left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
            top_label = ttk.Label(left_frame, text="参考网站列表(点击名称打开链接,双击名称可编辑,勾选后点击爬取)", font=("TkDefaultFont", 12, "bold"))
            top_label.pack(anchor=tk.W, pady=(0, 5))
            # 创建Canvas和Scrollbar用于滚动
            canvas_frame = ttk.Frame(left_frame)
            canvas_frame.pack(fill=tk.BOTH, expand=True)
            canvas = tk.Canvas(canvas_frame, bg="white")
            scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            # 绑定鼠标滚轮事件
            def _on_mousewheel(event):
                try:
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                except (tk.TclError, AttributeError, RuntimeError):
                    pass
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            # 窗口关闭时解绑事件
            def on_closing():
                try:
                    canvas.unbind_all("<MouseWheel>")
                except:
                    pass
                win.destroy()
            win.protocol("WM_DELETE_WINDOW", on_closing)
            # 更新滚动区域
            def update_scroll_region(event=None):
                try:
                    if canvas.winfo_exists():
                        canvas.update_idletasks()
                        canvas.configure(scrollregion=canvas.bbox("all"))
                except (tk.TclError, AttributeError):
                    pass
            scrollable_frame.bind("<Configure>", update_scroll_region)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            # 存储所有参考项和对应的Entry控件
            all_refs_data = []
            ref_entries = []  # 存储(name_entry, url_entry)的列表
            def refresh():
                # 清空现有控件
                for widget in scrollable_frame.winfo_children():
                    widget.destroy()
                ref_entries.clear()
                all_refs_data.clear()
                items = load_refs()
                all_refs_data.extend(items)
                # 按三列显示
                num_cols = 3
                for row_idx in range((len(items) + num_cols - 1) // num_cols):
                    row_frame = ttk.Frame(scrollable_frame)
                    row_frame.pack(fill=tk.X, pady=2)
                    for col_idx in range(num_cols):
                        item_idx = row_idx * num_cols + col_idx
                        if item_idx < len(items):
                            item = items[item_idx]
                            item_name = item.get("name", "")
                            item_url = item.get("url", "")
                            # 每个单元格:只显示名称
                            cell_frame = ttk.LabelFrame(row_frame, text="", padding=5)
                            cell_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
                            # 名称显示和编辑区域
                            name_frame = ttk.Frame(cell_frame)
                            name_frame.pack(fill=tk.X, pady=(0, 3))
                            # 使用Label显示名称(点击打开链接),Entry用于编辑(双击显示)
                            name_var = tk.StringVar(value=item_name)
                            name_label = tk.Label(
                                name_frame,
                                text=item_name,
                                cursor="hand2",
                                fg="blue",
                                font=("TkDefaultFont", 12, "underline")
                            )
                            name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
                            # 隐藏的Entry用于编辑
                            name_entry = ttk.Entry(name_frame, textvariable=name_var, width=30)
                            # 编辑状态标志
                            is_editing = [False]
                            def start_edit(event=None):
                                """开始编辑"""
                                is_editing[0] = True
                                name_label.pack_forget()
                                name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                                name_entry.focus()
                                name_entry.select_range(0, tk.END)
                            def finish_edit(event=None):
                                """结束编辑"""
                                if is_editing[0]:
                                    is_editing[0] = False
                                    new_name = name_var.get().strip()
                                    name_var.set(new_name)
                                    name_entry.pack_forget()
                                    name_label.config(text=new_name)
                                    name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
                            # 点击Label打开链接
                            def open_link(event=None):
                                if not is_editing[0] and item_url:
                                    try:
                                        webbrowser.open(item_url)
                                    except Exception as e:
                                        messagebox.showerror("错误", f"打开链接失败: {e}")
                            name_label.bind("<Button-1>", open_link)
                            name_label.bind("<Double-1>", start_edit)
                            # Entry失去焦点时结束编辑
                            name_entry.bind("<FocusOut>", finish_edit)
                            name_entry.bind("<Return>", finish_edit)
                            name_entry.bind("<Escape>", finish_edit)
                            # 复选框用于选择
                            check_var = tk.BooleanVar()
                            check_btn = ttk.Checkbutton(cell_frame, text="选择", variable=check_var)
                            check_btn.pack(pady=(3, 0))
                            # 保存引用(链接不显示但保存)
                            ref_entries.append({
                                'name_entry': name_entry,
                                'name_label': name_label,
                                'name_var': name_var,
                                'url': item_url,  # 保存原始URL,不显示
                                'check_var': check_var,
                                'item_idx': item_idx,
                                'is_editing': is_editing
                            })
                        else:
                            # 空单元格占位
                            empty_frame = ttk.Frame(row_frame)
                            empty_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
            # 右侧:操作 & 结果区域
            right_frame = ttk.LabelFrame(main_frame, text="操作 / 爬取结果", padding=10)
            right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0), expand=True)
            right_buttons_frame = ttk.Frame(right_frame)
            right_buttons_frame.pack(fill=tk.X)
            ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
            ttk.Label(right_frame, text="爬取结果标签页(最新在最右侧)", font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W)
            result_notebook = ttk.Notebook(right_frame, height=10)
            result_notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
            crawl_tab_counter = [0]
            def close_result_tab(tab_frame):
                """关闭指定的爬取结果标签页"""
                try:
                    tab_index = result_notebook.index(tab_frame)
                    result_notebook.forget(tab_index)
                except tk.TclError:
                    pass
            def on_save_all():
                """保存所有修改"""
                # 先结束所有正在编辑的项
                for ref_entry in ref_entries:
                    if ref_entry.get('is_editing') and ref_entry['is_editing'][0]:
                        # 触发结束编辑
                        ref_entry['name_entry'].event_generate("<FocusOut>")
                data = load_refs()
                for ref_entry in ref_entries:
                    item_idx = ref_entry['item_idx']
                    if item_idx < len(data):
                        new_name = ref_entry['name_var'].get().strip()
                        # URL保持不变,只更新名称
                        if new_name:
                            data[item_idx]['name'] = new_name
                if save_refs(data):
                    messagebox.showinfo("成功", "已保存所有修改")
                    refresh()
            def on_add():
                dlg = self._toplevel(win)
                dlg.title("新增参考")
                dlg.geometry("420x160")
                f = ttk.Frame(dlg)
                f.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                ttk.Label(f, text="名称").grid(row=0, column=0, sticky=tk.W, pady=6)
                name_var = tk.StringVar()
                name_entry = ttk.Entry(f, textvariable=name_var, width=40)
                name_entry.grid(row=0, column=1, pady=6)
                ttk.Label(f, text="链接").grid(row=1, column=0, sticky=tk.W, pady=6)
                url_var = tk.StringVar()
                url_entry = ttk.Entry(f, textvariable=url_var, width=40)
                url_entry.grid(row=1, column=1, pady=6)
                btns = ttk.Frame(f)
                btns.grid(row=2, column=0, columnspan=2, pady=(8,0))
                def do_save():
                    name, url = name_var.get().strip(), url_var.get().strip()
                    if not name or not url:
                        messagebox.showwarning("警告", "名称和链接均不能为空")
                        return
                    data = load_refs()
                    data.append({"name": name, "url": url})
                    if save_refs(data):
                        refresh()
                        dlg.destroy()
                ttk.Button(btns, text="保存", command=do_save).pack(side=tk.LEFT, padx=5)
                ttk.Button(btns, text="取消", command=dlg.destroy).pack(side=tk.LEFT, padx=5)
            def on_delete():
                """删除选中的项"""
                selected_indices = []
                for ref_entry in ref_entries:
                    if ref_entry['check_var'].get():
                        selected_indices.append(ref_entry['item_idx'])
                if not selected_indices:
                    messagebox.showwarning("警告", "请先选择要删除的项(勾选复选框)")
                    return
                if not messagebox.askyesno("确认", f"确认删除 {len(selected_indices)} 项?"):
                    return
                data = load_refs()
                # 按索引从大到小删除,避免索引变化
                for idx in sorted(selected_indices, reverse=True):
                    if idx < len(data):
                        data.pop(idx)
                if save_refs(data):
                    refresh()
            def on_crawl():
                """爬取选中的网站"""
                selected_items = []
                data = load_refs()
                for ref_entry in ref_entries:
                    if ref_entry['check_var'].get():
                        item_idx = ref_entry['item_idx']
                        if item_idx < len(data):
                            item = data[item_idx]
                            name = ref_entry['name_var'].get().strip() or item.get("name", "")
                            url = ref_entry.get('url') or item.get("url", "")  # 使用保存的URL
                            if name and url:
                                selected_items.append((name, url))
                if not selected_items:
                    messagebox.showwarning("警告", "请先选择要爬取的网站(勾选复选框)")
                    return
                # 创建新的爬取结果标签页
                crawl_tab_counter[0] += 1
                tab_label = f"爬取结果{crawl_tab_counter[0]}"
                tab_frame = ttk.Frame(result_notebook)
                result_notebook.add(tab_frame, text=tab_label)
                result_notebook.select(tab_frame)
                toolbar = ttk.Frame(tab_frame)
                toolbar.pack(fill=tk.X, pady=(0, 5))
                status_var = tk.StringVar(value=f"准备爬取 {len(selected_items)} 个网站...")
                status_label = ttk.Label(toolbar, textvariable=status_var)
                status_label.pack(side=tk.LEFT, padx=(0, 10))
                def save_tab_to_news():
                    """保存当前标签内容到资讯表"""
                    content = result_text.get("1.0", tk.END).strip()
                    if not content:
                        messagebox.showwarning("警告", "内容为空,无法保存")
                        return
                    tab_name = f"参考爬取 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    if save_news_info_to_db(tab_name, content):
                        messagebox.showinfo("成功", f"已保存资讯:{tab_name}")
                    else:
                        messagebox.showerror("错误", "保存失败")
                ttk.Button(toolbar, text="保存到资讯表", command=save_tab_to_news).pack(side=tk.LEFT, padx=5)
                ttk.Button(toolbar, text="关闭标签", command=lambda: close_result_tab(tab_frame)).pack(side=tk.RIGHT, padx=5)
                result_text = scrolledtext.ScrolledText(tab_frame, height=30, wrap=tk.WORD, font=("TkDefaultFont", 12))
                result_text.pack(fill=tk.BOTH, expand=True)
                # 在后台线程中执行爬取
                def crawl_thread():
                    result_text.insert(tk.END, f"开始爬取 {len(selected_items)} 个网站...\n")
                    try:
                        result_text.insert(tk.END, "="*80 + "\n\n")
                        result_text.update_idletasks()
                        all_content = []
                        for idx, (name, url) in enumerate(selected_items, 1):
                            try:
                                result_text.insert(tk.END, f"[{idx}/{len(selected_items)}] 正在爬取: {name} ({url})\n")
                                result_text.see(tk.END)
                                result_text.update_idletasks()
                                # 使用编码修正的爬取函数
                                headers = {
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36",
                                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                                    "Accept-Encoding": "gzip, deflate, br",
                                    "Connection": "keep-alive",
                                    "Upgrade-Insecure-Requests": "1"
                                }
                                html_content, used_encoding = self._fetch_with_encoding_fix(url, headers, max_retries=2)
                                if html_content:
                                    if self._detect_garbled_text(html_content):
                                        result_text.insert(tk.END, f"⚠️ 警告: {name} 内容可能包含乱码,已尝试修正\n")
                                    soup = BeautifulSoup(html_content, 'html.parser')
                                    for script in soup(["script", "style", "noscript"]):
                                        script.decompose()
                                    text_content = soup.get_text(separator='\n', strip=True)
                                    lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                                    cleaned_text = '\n'.join(lines)
                                    if cleaned_text:
                                        content_block = f"\n{'='*80}\n"
                                        content_block += f"来源: {name}\n"
                                        content_block += f"链接: {url}\n"
                                        content_block += f"编码: {used_encoding}\n"
                                        content_block += f"{'='*80}\n"
                                        content_block += f"{cleaned_text}\n"
                                        all_content.append(content_block)
                                        result_text.insert(tk.END, f"✅ {name} 爬取成功,内容长度: {len(cleaned_text)} 字符\n\n")
                                    else:
                                        result_text.insert(tk.END, f"⚠️ {name} 爬取成功但内容为空\n\n")
                                else:
                                    result_text.insert(tk.END, f"❌ {name} 爬取失败,无法获取内容\n\n")
                                result_text.see(tk.END)
                                result_text.update_idletasks()
                                time.sleep(1)  # 延迟避免请求过快
                            except Exception as e:
                                result_text.insert(tk.END, f"❌ {name} 爬取失败: {e!s}\n\n")
                                result_text.see(tk.END)
                                result_text.update_idletasks()
                                continue
                        # 显示合并后的内容
                        if all_content:
                            result_text.insert(tk.END, "\n" + "="*80 + "\n")
                            result_text.insert(tk.END, "合并后的完整内容:\n")
                            result_text.insert(tk.END, "="*80 + "\n\n")
                            full_content = '\n'.join(all_content)
                            result_text.insert(tk.END, full_content)
                            result_text.see(tk.END)
                            result_text.insert(tk.END, f"\n\n{'='*80}\n")
                            result_text.insert(tk.END, f"爬取完成!共成功爬取 {len(all_content)}/{len(selected_items)} 个网站\n")
                        else:
                            result_text.insert(tk.END, "\n⚠️ 未能获取到任何内容\n")
                        result_text.see(tk.END)
                        result_text.update_idletasks()
                        status_var.set(f"爬取完成:成功 {len(all_content)}/{len(selected_items)} 个网站")
                    except Exception as e:
                        result_text.insert(tk.END, f"\n❌ 爬取过程发生错误: {e!s}\n")
                        result_text.see(tk.END)
                        result_text.update_idletasks()
                        status_var.set(f"爬取失败:{e!s}")
                threading.Thread(target=crawl_thread, daemon=True).start()
            # 右侧按钮
            ttk.Button(right_buttons_frame, text="保存所有修改", command=on_save_all, width=20).pack(pady=3, fill=tk.X)
            ttk.Button(right_buttons_frame, text="新增", command=on_add, width=20).pack(pady=3, fill=tk.X)
            ttk.Button(right_buttons_frame, text="删除选中", command=on_delete, width=20).pack(pady=3, fill=tk.X)
            ttk.Button(right_buttons_frame, text="刷新", command=refresh, width=20).pack(pady=3, fill=tk.X)
            ttk.Separator(right_buttons_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
            ttk.Button(right_buttons_frame, text="🚀 爬取选中网站", command=on_crawl, width=20).pack(pady=3, fill=tk.X)
            refresh()
            # 窗口控制按钮
            control_btn_frame = ttk.Frame(win)
            control_btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            def toggle_minimize():
                """切换最小化/恢复"""
                if win._is_minimized:
                    win.geometry(win._original_geometry)
                    win._is_minimized = False
                    minimize_btn.config(text="最小化")
                else:
                    win._original_geometry = win.geometry()
                    win.geometry("200x50")
                    win._is_minimized = True
                    minimize_btn.config(text="恢复")
            def toggle_maximize():
                """切换最大化/恢复"""
                try:
                    if win.state() == 'zoomed':
                        win.state('normal')
                        win.geometry(win._original_geometry)
                        maximize_btn.config(text="最大化")
                    else:
                        win._original_geometry = win.geometry()
                        win.state('zoomed')
                        maximize_btn.config(text="恢复")
                except:
                    try:
                        current_geom = win.geometry()
                        if hasattr(win, '_is_maximized') and win._is_maximized:
                            win.geometry(win._original_geometry)
                            win._is_maximized = False
                            maximize_btn.config(text="最大化")
                        else:
                            win._original_geometry = current_geom
                            screen_width = win.winfo_screenwidth()
                            screen_height = win.winfo_screenheight()
                            win.geometry(f"{screen_width}x{screen_height}+0+0")
                            win._is_maximized = True
                            maximize_btn.config(text="恢复")
                    except Exception as e:
                        messagebox.showinfo("提示", f"最大化功能不可用: {e}")
            minimize_btn = ttk.Button(control_btn_frame, text="最小化", command=toggle_minimize, width=10)
            minimize_btn.pack(side=tk.LEFT, padx=5)
            maximize_btn = ttk.Button(control_btn_frame, text="最大化", command=toggle_maximize, width=10)
            maximize_btn.pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="隐藏", command=win.withdraw, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="显示", command=win.deiconify, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="关闭", command=win.destroy, width=10).pack(side=tk.RIGHT, padx=5)
        except Exception as e:
            messagebox.showerror("错误", f"打开参考一览失败: {e}")

    def _mark_links_in_text(self, text_widget, content):
        """在文本中标记链接,使其可点击"""
        try:
            import re
            # 先清除所有现有的link tag
            text_widget.tag_delete("link")
            # 匹配 [标题](URL) 格式的链接
            link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
            matches = list(re.finditer(link_pattern, content))
            # 从后往前处理,避免位置偏移
            for match in reversed(matches):
                start = match.start()
                end = match.end()
                title = match.group(1)
                url = match.group(2)
                # 获取文本位置
                try:
                    start_pos = text_widget.index(f"1.0 + {start} chars")
                    end_pos = text_widget.index(f"1.0 + {end} chars")
                    # 替换为标题文本
                    text_widget.delete(start_pos, end_pos)
                    text_widget.insert(start_pos, title)
                    # 重新计算位置
                    new_end_pos = text_widget.index(f"{start_pos} + {len(title)} chars")
                    # 添加链接tag(使用唯一名称)
                    tag_name = f"link_{start}"
                    text_widget.tag_add(tag_name, start_pos, new_end_pos)
                    text_widget.tag_config(tag_name, foreground="blue", underline=True)
                    # 绑定事件
                    text_widget.tag_bind(tag_name, "<Button-1>",
                                         lambda e, u=url: webbrowser.open(u))
                    text_widget.tag_bind(tag_name, "<Enter>",
                                         lambda e: text_widget.config(cursor="hand2"))
                    text_widget.tag_bind(tag_name, "<Leave>",
                                         lambda e: text_widget.config(cursor=""))
                except Exception as e:
                    print(f"标记链接位置 {start}-{end} 失败: {e}")
                    continue
            # 同时匹配直接的URL链接(http://或https://开头)
            url_pattern = r'(https?://[^\s\)]+)'
            url_matches = list(re.finditer(url_pattern, content))
            for match in reversed(url_matches):
                start = match.start()
                end = match.end()
                url = match.group(1)
                try:
                    start_pos = text_widget.index(f"1.0 + {start} chars")
                    end_pos = text_widget.index(f"1.0 + {end} chars")
                    # 添加链接tag(不删除原文本)
                    tag_name = f"url_{start}"
                    text_widget.tag_add(tag_name, start_pos, end_pos)
                    text_widget.tag_config(tag_name, foreground="blue", underline=True)
                    # 绑定事件
                    text_widget.tag_bind(tag_name, "<Button-1>",
                                         lambda e, u=url: webbrowser.open(u))
                    text_widget.tag_bind(tag_name, "<Enter>",
                                         lambda e: text_widget.config(cursor="hand2"))
                    text_widget.tag_bind(tag_name, "<Leave>",
                                         lambda e: text_widget.config(cursor=""))
                except Exception as e:
                    print(f"标记URL {url} 失败: {e}")
                    continue
        except Exception as e:
            print(f"标记链接失败: {e}")
            import traceback
            traceback.print_exc()

    def _open_link_from_text(self, event, text_widget):
        """从文本中打开链接"""
        try:
            # 获取点击位置
            index = text_widget.index(f"@{event.x},{event.y}")
            # 查找该位置的tag
            tags = text_widget.tag_names(index)
            if "link" in tags:
                # 获取链接文本
                start = text_widget.index(f"{index} linestart")
                end = text_widget.index(f"{index} lineend")
                text_widget.get(start, end)
                # 尝试从文本中提取URL
                import re
                # 查找URL模式
                url_pattern = r'https?://[^\s\)]+'
                urls = re.findall(url_pattern, text_widget.get("1.0", tk.END))
                if urls:
                    webbrowser.open(urls[0])
        except Exception as e:
            print(f"打开链接失败: {e}")

    def show_investment_system(self):
        """打开投资系统界面"""
        try:
            win = self._safe_toplevel(self.root)
            win.title("投资系统工作台")
            win.geometry("1200x720")
            win.transient(self.root)
            # 投资系统选项
            system_options = {
                "价值投资": "本杰明·格雷厄姆和沃伦·巴菲特的价值投资体系,关注企业内在价值、安全边际、长期持有",
                "海龟交易法则": "理查德·丹尼斯的海龟交易系统,基于趋势跟踪、仓位管理、风险控制",
                "量化投资": "基于数学模型和算法的量化投资策略,包括因子投资、统计套利、机器学习等",
                "技术分析": "基于价格和成交量图表的技术分析方法,包括趋势、形态、指标等",
                "基本面分析": "基于公司财务数据、行业状况、宏观经济的基本面分析方法",
                "成长投资": "菲利普·费雪的成长投资策略,关注高成长性公司的长期投资价值",
                "动量投资": "基于价格动量和相对强度的动量投资策略",
                "均值回归": "基于价格偏离均值的均值回归投资策略",
                "因子投资": "基于多因子模型的因子投资策略,包括价值、成长、质量、动量等因子",
                "资产配置": "现代投资组合理论,包括马科维茨模型、风险平价、目标日期基金等"
            }
            self._create_analysis_window(
                win,
                "请选择投资系统,查看系统说明和应用建议",
                system_options,
                "投资系统",
                self._get_system_prompt,
                "你是一位资深的投资系统专家,熟悉各种主流投资理论和实践方法。"
            )
        except Exception as e:
            messagebox.showerror("错误", f"打开投资系统界面失败: {e}")
            import traceback
            traceback.print_exc()

    def _index_tag_for_stock_code(self, code, hs300, zz500, kc50) -> str:
        """返回 Treeview 标签:沪深300→红,中证500→棕,科创50→绿;优先级 300>500>50。"""
        c6 = self._normalize_stock_code_6(code)
        if not c6:
            return ""
        if c6 in hs300:
            return "idx_hs300"
        if c6 in zz500:
            return "idx_zz500"
        if c6 in kc50:
            return "idx_kc50"
        return ""

    def _dedupe_elevator_stocks_by_code(self, stocks):
        """问财结果按 6 位代码去重,保留首次出现顺序。"""
        seen = set()
        out = []
        for s in stocks or []:
            if not isinstance(s, dict):
                continue
            c = str(s.get("code", "") or "").strip()
            if not c:
                continue
            c = c.zfill(6) if c.isdigit() and len(c) <= 6 else c
            if c in seen:
                continue
            seen.add(c)
            ns = dict(s)
            ns["code"] = c
            out.append(ns)
        return out

    def _tushare_local_filter(self, question):
        """用 tushare 拉全市场数据,本地解析简单查询条件做兜底选股。
        支持的条件关键词: 市盈率/pe, 市净率/pb, 市值/总市值, 流通市值, 换手率, 成交额, 成交量,
        涨跌幅/涨幅, ROE/roe, 股息率, 价格/股价。
        复杂条件(均线形态/概念热点等)无法本地复现,会尽量匹配简单条件。
        """
        import re as _re
        try:
            import tushare as _ts
            _pro = _ts.pro_api()
        except Exception:
            return []
        # 1) 确定交易日
        _today = datetime.now().strftime("%Y%m%d")
        _td = _today
        try:
            _cal = _pro.trade_cal(exchange="SSE", start_date=_today, end_date=_today)
            if _cal is not None and len(_cal) > 0 and str(_cal.iloc[0]["is_open"]) != "1":
                # 往前推
                _td_dt = datetime.now() - timedelta(days=7)
                _cal2 = _pro.trade_cal(exchange="SSE", start_date=_td_dt.strftime("%Y%m%d"), end_date=_today)
                if _cal2 is not None and len(_cal2) > 0:
                    _open = _cal2[_cal2["is_open"] == 1]["cal_date"]
                    if len(_open) > 0:
                        _td = str(_open.iloc[-1])
        except Exception:
            pass
        # 2) 拉 daily_basic (PE/PB/换手率/市值等)
        try:
            _basic = _pro.daily_basic(trade_date=_td, fields="ts_code,close,turnover_rate,pe_ttm,pb,total_mv,circ_mv,volume_ratio")
        except Exception:
            _basic = None
        # 3) 拉 daily (涨跌幅/成交量/成交额)
        try:
            _daily = _pro.daily(trade_date=_td, fields="ts_code,pct_chg,vol,amount,open,high,low")
        except Exception:
            _daily = None
        if _basic is None or len(_basic) == 0:
            return []
        # 4) 合并
        _df = _basic.copy()
        if _daily is not None and len(_daily) > 0:
            _df = _df.merge(_daily, on="ts_code", how="left")
        # 4b) 获取股票名称映射
        _name_map = {}
        try:
            _sb = _pro.stock_basic(exchange="", list_status="L", fields="ts_code,name")
            if _sb is not None:
                for _, _r in _sb.iterrows():
                    _name_map[str(_r["ts_code"])] = str(_r["name"])
        except Exception:
            pass
        # 5) 解析查询条件
        _conds = []  # [(col_or_callable, op, value), ...]
        def _add_col_cond(col, pattern, cast=float, op="lt"):
            nonlocal _conds
            m = _re.search(pattern, question)
            if m:
                try:
                    val = cast(m.group(1))
                    _conds.append((col, op, val))
                except Exception:
                    pass
        _q = question.lower()
        # 市盈率条件
        if _re.search(r"市盈率|pe", _q):
            _add_col_cond("pe_ttm", r"pe[^0-9<>=]*([0-9.]+)")
            _add_col_cond("pe_ttm", r"pe[^0-9<>=]*>[0-9.]*<([0-9.]+)", float, "lt")
            m_gt = _re.search(r"pe[^0-9<>=]*>([0-9.]+)", _q)
            if m_gt:
                try:
                    _conds.append(("pe_ttm", "gt", float(m_gt.group(1))))
                except Exception:
                    pass
        # 市值条件 (单位:万元 → 转亿元 /10000)
        if _re.search(r"总市值|市值", _q):
            m = _re.search(r"市值[^0-9<>=]*([0-9.]+)\s*亿", question)
            if m:
                val_yi = float(m.group(1))
                _conds.append(("total_mv_yi", "lt", val_yi))
            m2 = _re.search(r"市值[^0-9<>=]*>([0-9.]+)\s*亿", question)
            if m2:
                _conds.append(("total_mv_yi", "gt", float(m2.group(1))))
        # 流通市值
        if _re.search(r"流通市值", _q):
            m = _re.search(r"流通市值[^0-9<>=]*([0-9.]+)\s*亿", question)
            if m:
                _conds.append(("circ_mv_yi", "lt", float(m.group(1))))
        # 换手率条件
        if _re.search(r"换手率", _q):
            m = _re.search(r"换手率[^0-9<>=]*([0-9.]+)\s*%", question)
            if m:
                _conds.append(("turnover_rate", "lt", float(m.group(1))))
            m2 = _re.search(r"换手率[^0-9<>=]*>([0-9.]+)\s*%", question)
            if m2:
                _conds.append(("turnover_rate", "gt", float(m2.group(1))))
        # 涨跌幅条件
        if _re.search(r"涨跌幅|涨幅", _q):
            m = _re.search(r"(?:涨跌幅|涨幅)[^0-9<>=]*([0-9.]+)\s*%", question)
            if m:
                _conds.append(("pct_chg", "lt", float(m.group(1))))
        # 6) 应用条件筛选
        if _conds:
            # 添加辅助列
            if "total_mv" in _df.columns:
                _df["total_mv_yi"] = _df["total_mv"].astype(float) / 10000.0
            if "circ_mv" in _df.columns:
                _df["circ_mv_yi"] = _df["circ_mv"].astype(float) / 10000.0
            for col, op, val in _conds:
                if col not in _df.columns:
                    continue
                _df[col] = pd.to_numeric(_df[col], errors="coerce")
                if op == "lt":
                    _df = _df[_df[col].notna() & (_df[col] < val)]
                elif op == "gt":
                    _df = _df[_df[col].notna() & (_df[col] > val)]
                elif op == "le":
                    _df = _df[_df[col].notna() & (_df[col] <= val)]
                elif op == "ge":
                    _df = _df[_df[col].notna() & (_df[col] >= val)]
        # 7) 排除 ST/*ST/退 (用名称映射)
        if _name_map:
            _df["_name"] = _df["ts_code"].map(_name_map).fillna("")
            _df = _df[~_df["_name"].str.contains("ST|退", case=False, na=False)]
            _df = _df.drop(columns=["_name"])
        # 8) 排除科创板(688)/北交所(8/4开头)可按需筛选 —— 默认保留全部
        # 保留主板+创业板+科创板+北交所
        if len(_df) == 0:
            return []
        # 9) 排序+取前100:有条件按成交额优先,无条件直接返回热门股Top100
        if "amount" in _df.columns:
            _df = _df.sort_values("amount", ascending=False)
        _df = _df.head(100)
        # 10) 转为标准 dict
        stocks = []
        for _, row in _df.iterrows():
            _tsc = str(row.get("ts_code", "") or "")
            _code = _tsc.split(".")[0]
            if not _code or len(_code) != 6:
                continue
            _name = _name_map.get(_tsc, "")
            stocks.append({
                "code": _code,
                "name": _name,
                "price": float(row.get("close", 0) or 0),
                "change_pct": float(row.get("pct_chg", 0) or 0),
                "volume": int(row.get("vol", 0) or 0),
                "turnover": float(row.get("amount", 0) or 0),
                "market_cap": float(row.get("total_mv_yi", 0) or 0),
                "pe_ratio": float(row.get("pe_ttm", 0) or 0),
                "wr2": 0.0,
                "d": 0.0,
                "bias3": 0.0,
                "diff": 0.0,
            })
        return stocks

    def show_trading_system(self):
        """打开交易体系界面"""
        try:
            win = self._safe_toplevel(self.root)
            win.title("交易体系管理")
            win.geometry("1600x900")
            win.transient(self.root)
            win.resizable(True, True)
            # 主容器框架
            main_container = ttk.Frame(win, padding=10)
            main_container.pack(fill=tk.BOTH, expand=True)
            # 创建上下分栏
            top_paned = ttk.PanedWindow(main_container, orient=tk.VERTICAL)
            top_paned.pack(fill=tk.BOTH, expand=True)
            # 上半部分:策略选择和市场环境
            top_frame = ttk.Frame(top_paned)
            top_paned.add(top_frame, weight=1)
            # 创建左右分栏
            top_horizontal = ttk.PanedWindow(top_frame, orient=tk.HORIZONTAL)
            top_horizontal.pack(fill=tk.BOTH, expand=True)
            # 左侧:策略选择和市场环境
            left_top = ttk.LabelFrame(top_horizontal, text="策略选择与市场环境", padding=10)
            top_horizontal.add(left_top, weight=1)
            # 策略选择区域
            strategy_frame = ttk.LabelFrame(left_top, text="交易策略", padding=10)
            strategy_frame.pack(fill=tk.X, pady=(0, 10))
            strategy_var = tk.StringVar(value="核心-卫星策略")
            strategies = [
                "核心-卫星策略(70%稳健+30%机动)",
                "价值投资策略",
                "成长投资策略",
                "动量投资策略",
                "均值回归策略",
                "量化策略",
                "技术分析策略",
                "基本面驱动策略"
            ]
            ttk.Label(strategy_frame, text="选择策略:", font=("TkDefaultFont", 12)).pack(anchor=tk.W, pady=(0, 5))
            strategy_combo = ttk.Combobox(strategy_frame, textvariable=strategy_var, values=strategies,
                                         width=40, state="readonly")
            strategy_combo.pack(fill=tk.X, pady=(0, 10))
            # 策略说明
            strategy_desc_text = scrolledtext.ScrolledText(strategy_frame, height=4, wrap=tk.WORD,
                                                          font=("TkDefaultFont", 11))
            strategy_desc_text.pack(fill=tk.X, pady=(0, 5))
            # 策略说明按钮区域
            strategy_btn_frame = ttk.Frame(strategy_frame)
            strategy_btn_frame.pack(fill=tk.X)
            # 加载策略说明(从文件或数据库)
            strategy_descriptions_file = os.path.join(D_DATA_DIR, "strategy_descriptions.json")
            strategy_descriptions = {
                "核心-卫星策略(70%稳健+30%机动)": "70%资金配置稳健资产(蓝筹股、ETF),30%用于机动仓位(成长股、主题投资)。适合风险偏好中等的投资者。",
                "价值投资策略": "关注企业内在价值,寻找被低估的股票,长期持有。适合有耐心、注重基本面的投资者。",
                "成长投资策略": "投资高成长性公司,关注业绩增长和行业前景。适合风险承受能力较强的投资者。",
                "动量投资策略": "跟随市场趋势,买入强势股,卖出弱势股。适合技术分析能力强的投资者。",
                "均值回归策略": "在价格偏离均值时买入,回归均值时卖出。适合震荡市场。",
                "量化策略": "基于数学模型和算法的量化投资,系统化执行。适合有编程能力的投资者。",
                "技术分析策略": "基于价格和成交量图表进行交易决策。适合短线交易者。",
                "基本面驱动策略": "基于公司财务数据、行业状况进行选股。适合中长线投资者。"
            }
            # 加载保存的策略说明
            try:
                if os.path.exists(strategy_descriptions_file):
                    with open(strategy_descriptions_file, 'r', encoding='utf-8') as f:
                        saved_descriptions = json.load(f)
                        strategy_descriptions.update(saved_descriptions)
            except:
                pass
            # 保存策略说明到文件
            def save_strategy_descriptions():
                try:
                    os.makedirs(D_DATA_DIR, exist_ok=True)
                    with open(strategy_descriptions_file, 'w', encoding='utf-8') as f:
                        json.dump(strategy_descriptions, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    messagebox.showerror("错误", f"保存策略说明失败: {e}")
            def update_strategy_desc(event=None):
                selected = strategy_var.get()
                desc = strategy_descriptions.get(selected, "请选择策略")
                strategy_desc_text.delete("1.0", tk.END)
                strategy_desc_text.insert("1.0", desc)
            def show_strategy_ai_detail():
                """显示策略AI详细说明"""
                selected_strategy = strategy_var.get()
                if not selected_strategy:
                    messagebox.showwarning("警告", "请先选择策略")
                    return
                detail_window = self._toplevel(win)
                detail_window.title(f"{selected_strategy} - AI详细说明")
                detail_window.geometry("800x600")
                detail_window.transient(win)
                main_frame = ttk.Frame(detail_window, padding=10)
                main_frame.pack(fill=tk.BOTH, expand=True)
                # 说明编辑区域
                ttk.Label(main_frame, text="策略详细说明(可编辑):", font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
                detail_text = scrolledtext.ScrolledText(main_frame, height=20, wrap=tk.WORD, font=("TkDefaultFont", 12))
                detail_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
                # 加载现有说明或生成AI说明
                current_detail = strategy_descriptions.get(selected_strategy, "")
                if not current_detail or len(current_detail) < 100:
                    # 如果说明太短,生成AI详细说明
                    detail_text.insert("1.0", "正在生成AI详细说明...")
                    detail_window.update()
                    try:
                        ai_prompt = f"""请详细分析并说明以下交易策略:
策略名称:{selected_strategy}
请从以下维度进行详细分析:
1. 策略核心原理和理论基础
2. 适用市场环境
3. 适合的投资者类型
4. 具体操作方法和步骤
5. 风险控制要点
6. 成功案例和注意事项
7. 与其他策略的对比
请提供详细、专业、实用的说明,字数不少于500字。"""
                        ai_detail = self.call_ai_model(ai_prompt, "你是一位资深的投资策略分析专家,能够深入分析各种交易策略并提供专业建议。")
                        if ai_detail:
                            detail_text.delete("1.0", tk.END)
                            detail_text.insert("1.0", ai_detail)
                        else:
                            detail_text.delete("1.0", tk.END)
                            detail_text.insert("1.0", current_detail or f"{selected_strategy}的详细说明待补充。")
                    except Exception as e:
                        detail_text.delete("1.0", tk.END)
                        detail_text.insert("1.0", current_detail or f"生成AI说明失败: {e}")
                else:
                    detail_text.insert("1.0", current_detail)
                # 按钮区域
                btn_frame = ttk.Frame(main_frame)
                btn_frame.pack(fill=tk.X, pady=(10, 0))
                def save_detail():
                    """保存详细说明"""
                    new_detail = detail_text.get("1.0", tk.END).strip()
                    strategy_descriptions[selected_strategy] = new_detail
                    save_strategy_descriptions()
                    update_strategy_desc()
                    messagebox.showinfo("成功", "策略说明已保存")
                    detail_window.destroy()
                def delete_detail():
                    """删除详细说明"""
                    if messagebox.askyesno("确认", f"确定要删除 '{selected_strategy}' 的详细说明吗?"):
                        if selected_strategy in strategy_descriptions:
                            del strategy_descriptions[selected_strategy]
                            save_strategy_descriptions()
                            update_strategy_desc()
                            messagebox.showinfo("成功", "策略说明已删除")
                            detail_window.destroy()
                def regenerate_ai():
                    """重新生成AI说明"""
                    detail_text.delete("1.0", tk.END)
                    detail_text.insert("1.0", "正在重新生成AI详细说明...")
                    detail_window.update()
                    try:
                        ai_prompt = f"""请详细分析并说明以下交易策略:
策略名称:{selected_strategy}
请从以下维度进行详细分析:
1. 策略核心原理和理论基础
2. 适用市场环境
3. 适合的投资者类型
4. 具体操作方法和步骤
5. 风险控制要点
6. 成功案例和注意事项
7. 与其他策略的对比
请提供详细、专业、实用的说明,字数不少于500字。"""
                        ai_detail = self.call_ai_model(ai_prompt, "你是一位资深的投资策略分析专家,能够深入分析各种交易策略并提供专业建议。")
                        if ai_detail:
                            detail_text.delete("1.0", tk.END)
                            detail_text.insert("1.0", ai_detail)
                        else:
                            messagebox.showwarning("警告", "AI说明生成失败,请检查AI配置")
                    except Exception as e:
                        messagebox.showerror("错误", f"生成AI说明失败: {e}")
                ttk.Button(btn_frame, text="保存", command=save_detail, width=12).pack(side=tk.LEFT, padx=5)
                ttk.Button(btn_frame, text="删除", command=delete_detail, width=12).pack(side=tk.LEFT, padx=5)
                ttk.Button(btn_frame, text="重新生成AI说明", command=regenerate_ai, width=15).pack(side=tk.LEFT, padx=5)
                ttk.Button(btn_frame, text="关闭", command=detail_window.destroy, width=12).pack(side=tk.RIGHT, padx=5)
            ttk.Button(strategy_btn_frame, text="AI详细说明", command=show_strategy_ai_detail, width=15).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(strategy_btn_frame, text="管理说明", command=lambda: manage_strategy_descriptions(), width=15).pack(side=tk.LEFT)
            def manage_strategy_descriptions():
                """管理策略说明"""
                manage_window = self._toplevel(win)
                manage_window.title("管理策略说明")
                manage_window.geometry("600x500")
                manage_window.transient(win)
                manage_frame = ttk.Frame(manage_window, padding=10)
                manage_frame.pack(fill=tk.BOTH, expand=True)
                ttk.Label(manage_frame, text="策略说明列表:", font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
                listbox = tk.Listbox(manage_frame, height=15)
                listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
                def load_list():
                    listbox.delete(0, tk.END)
                    for strategy in strategies:
                        listbox.insert(tk.END, strategy)
                def edit_selected():
                    selection = listbox.curselection()
                    if selection:
                        selected = listbox.get(selection[0])
                        strategy_var.set(selected)
                        show_strategy_ai_detail()
                        manage_window.destroy()
                def delete_selected():
                    selection = listbox.curselection()
                    if selection:
                        selected = listbox.get(selection[0])
                        if messagebox.askyesno("确认", f"确定要删除 '{selected}' 的说明吗?"):
                            if selected in strategy_descriptions:
                                del strategy_descriptions[selected]
                                save_strategy_descriptions()
                                update_strategy_desc()
                                messagebox.showinfo("成功", "说明已删除")
                btn_frame = ttk.Frame(manage_frame)
                btn_frame.pack(fill=tk.X)
                ttk.Button(btn_frame, text="编辑", command=edit_selected, width=12).pack(side=tk.LEFT, padx=5)
                ttk.Button(btn_frame, text="删除", command=delete_selected, width=12).pack(side=tk.LEFT, padx=5)
                ttk.Button(btn_frame, text="关闭", command=manage_window.destroy, width=12).pack(side=tk.RIGHT, padx=5)
                load_list()
            strategy_combo.bind("<<ComboboxSelected>>", update_strategy_desc)
            update_strategy_desc()
            # 市场环境区域
            market_env_frame = ttk.LabelFrame(left_top, text="市场环境", padding=10)
            market_env_frame.pack(fill=tk.BOTH, expand=True)
            # 大盘情况
            market_row1 = ttk.Frame(market_env_frame)
            market_row1.pack(fill=tk.X, pady=2)
            ttk.Label(market_row1, text="大盘情况:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(0, 5))
            market_status_var = tk.StringVar(value="待评估")
            market_status_label = ttk.Label(market_row1, textvariable=market_status_var,
                                          font=("TkDefaultFont", 12, "bold"), foreground="blue")
            market_status_label.pack(side=tk.LEFT, padx=(0, 20))
            def update_market_status():
                """更新大盘情况"""
                try:
                    # 获取主界面的总分值(通过self访问)
                    if hasattr(self, 'position_vars') and 'total_score_var' in self.position_vars:
                        # 尝试从主界面获取总分
                        try:
                            # 通过主界面变量获取
                            total_score_var_ref = self.position_vars['total_score_var']
                            score_text = total_score_var_ref.get().replace("总分: ", "").strip()
                            score = int(score_text) if score_text.isdigit() else 0
                        except:
                            # 如果无法获取,使用默认值
                            score = 0
                    else:
                        score = 0
                    if score > 60:
                        market_status_var.set(f"强势 ({score}分)")
                        market_status_label.config(foreground="green")
                    elif score > 40:
                        market_status_var.set(f"中性 ({score}分)")
                        market_status_label.config(foreground="orange")
                    else:
                        market_status_var.set(f"弱势 ({score}分)")
                        market_status_label.config(foreground="red")
                except:
                    market_status_var.set("待评估")
            ttk.Button(market_row1, text="更新", command=update_market_status, width=8).pack(side=tk.LEFT)
            update_market_status()
            # 外围情绪
            market_row2 = ttk.Frame(market_env_frame)
            market_row2.pack(fill=tk.X, pady=2)
            ttk.Label(market_row2, text="外围情绪:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(0, 5))
            peripheral_sentiment_var = tk.StringVar(value="待输入")
            peripheral_entry = ttk.Entry(market_row2, textvariable=peripheral_sentiment_var, width=15)
            peripheral_entry.pack(side=tk.LEFT, padx=(0, 5))
            ttk.Label(market_row2, text="分", font=("TkDefaultFont", 11)).pack(side=tk.LEFT)
            # 股票板块
            market_row3 = ttk.Frame(market_env_frame)
            market_row3.pack(fill=tk.X, pady=2)
            ttk.Label(market_row3, text="关注板块:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(0, 5))
            sector_var = tk.StringVar()
            sector_combo = ttk.Combobox(market_row3, textvariable=sector_var, width=20)
            sector_combo.pack(side=tk.LEFT, padx=(0, 5))
            # 板块管理
            def manage_sectors():
                """管理板块列表,支持从同花顺获取概念板块和基本板块"""
                manage_window = self._toplevel(win)
                manage_window.title("管理板块")
                manage_window.geometry("800x600")
                manage_window.transient(win)
                main_frame = ttk.Frame(manage_window, padding=10)
                main_frame.pack(fill=tk.BOTH, expand=True)
                # 顶部:操作按钮区域
                top_frame = ttk.Frame(main_frame)
                top_frame.pack(fill=tk.X, pady=(0, 10))
                # 左侧:板块列表
                left_frame = ttk.LabelFrame(main_frame, text="当前板块列表", padding=10)
                left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
                ttk.Label(left_frame, text="板块列表:", font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
                sector_listbox = tk.Listbox(left_frame, height=20)
                sector_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
                # 右侧:同花顺板块选择
                right_frame = ttk.LabelFrame(main_frame, text="同花顺板块选择", padding=10)
                right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
                # 板块类型选择
                sector_type_var = tk.StringVar(value="概念板块")
                ttk.Label(right_frame, text="板块类型:", font=("TkDefaultFont", 11)).pack(anchor=tk.W, pady=(0, 5))
                type_frame = ttk.Frame(right_frame)
                type_frame.pack(fill=tk.X, pady=(0, 10))
                ttk.Radiobutton(type_frame, text="概念板块", variable=sector_type_var,
                               value="概念板块", command=lambda: load_ths_sectors("概念")).pack(side=tk.LEFT, padx=(0, 10))
                ttk.Radiobutton(type_frame, text="基本板块", variable=sector_type_var,
                               value="基本板块", command=lambda: load_ths_sectors("基本")).pack(side=tk.LEFT)
                # 搜索框
                search_frame = ttk.Frame(right_frame)
                search_frame.pack(fill=tk.X, pady=(0, 5))
                ttk.Label(search_frame, text="搜索:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(0, 5))
                search_var = tk.StringVar()
                search_entry = ttk.Entry(search_frame, textvariable=search_var, width=20)
                search_entry.pack(side=tk.LEFT, padx=(0, 5))
                def filter_sectors():
                    search_text = search_var.get().strip().lower()
                    ths_listbox.delete(0, tk.END)
                    for sector in all_ths_sectors:
                        if search_text in sector.lower():
                            ths_listbox.insert(tk.END, sector)
                ttk.Button(search_frame, text="搜索", command=filter_sectors, width=8).pack(side=tk.LEFT)
                # 同花顺板块列表
                ttk.Label(right_frame, text="同花顺板块列表:", font=("TkDefaultFont", 11, "bold")).pack(anchor=tk.W, pady=(5, 5))
                ths_listbox = tk.Listbox(right_frame, height=15)
                ths_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
                all_ths_sectors = []  # 存储所有同花顺板块
                def load_ths_sectors(sector_type="概念"):
                    """加载同花顺板块"""
                    ths_listbox.delete(0, tk.END)
                    all_ths_sectors.clear()
                    try:
                        if sector_type == "概念":
                            # 获取概念板块
                            df = safe_call(ak.stock_board_concept_name_em, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_em")
                            if not df.empty and '板块名称' in df.columns:
                                sectors = df['板块名称'].tolist()
                                all_ths_sectors.extend(sectors)
                                for sector in sectors[:200]:  # 限制显示前200个
                                    ths_listbox.insert(tk.END, sector)
                        else:
                            # 获取基本板块(行业板块)
                            df = safe_call(ak.stock_board_industry_name_em, fallback=pd.DataFrame(), label="ak.stock_board_industry_name_em")
                            if not df.empty and '板块名称' in df.columns:
                                sectors = df['板块名称'].tolist()
                                all_ths_sectors.extend(sectors)
                                for sector in sectors[:200]:  # 限制显示前200个
                                    ths_listbox.insert(tk.END, sector)
                    except Exception as e:
                        messagebox.showerror("错误", f"加载同花顺板块失败: {e}")
                        ths_listbox.insert(tk.END, f"加载失败: {e}")
                # 初始加载概念板块
                load_ths_sectors("概念")
                def load_sectors():
                    """加载当前板块列表"""
                    sector_listbox.delete(0, tk.END)
                    for s in sector_list:
                        sector_listbox.insert(tk.END, s)
                def add_sector():
                    """添加板块(手动输入)"""
                    new_sector = simpledialog.askstring("添加板块", "请输入板块名称:")
                    if new_sector and new_sector.strip():
                        sector_name = new_sector.strip()
                        if sector_name not in sector_list:
                            sector_list.append(sector_name)
                            load_sectors()
                            sector_combo['values'] = sector_list
                            messagebox.showinfo("成功", f"已添加板块: {sector_name}")
                        else:
                            messagebox.showwarning("警告", "该板块已存在")
                def add_from_ths():
                    """从同花顺板块列表添加"""
                    selection = ths_listbox.curselection()
                    if selection:
                        sector_name = ths_listbox.get(selection[0])
                        if sector_name not in sector_list:
                            sector_list.append(sector_name)
                            load_sectors()
                            sector_combo['values'] = sector_list
                            messagebox.showinfo("成功", f"已添加板块: {sector_name}")
                        else:
                            messagebox.showwarning("警告", "该板块已存在")
                    else:
                        messagebox.showwarning("警告", "请先选择要添加的板块")
                def edit_sector():
                    """编辑板块"""
                    selection = sector_listbox.curselection()
                    if selection:
                        index = selection[0]
                        old_sector = sector_list[index]
                        new_sector = simpledialog.askstring("编辑板块", "请输入新的板块名称:", initialvalue=old_sector)
                        if new_sector and new_sector.strip():
                            sector_list[index] = new_sector.strip()
                            load_sectors()
                            sector_combo['values'] = sector_list
                            messagebox.showinfo("成功", f"已更新板块: {old_sector} -> {new_sector.strip()}")
                    else:
                        messagebox.showwarning("警告", "请先选择要编辑的板块")
                def delete_sector():
                    """删除板块"""
                    selection = sector_listbox.curselection()
                    if selection:
                        index = selection[0]
                        sector_name = sector_list[index]
                        if messagebox.askyesno("确认", f"确定要删除板块 '{sector_name}' 吗?"):
                            sector_list.pop(index)
                            load_sectors()
                            sector_combo['values'] = sector_list
                            messagebox.showinfo("成功", f"已删除板块: {sector_name}")
                    else:
                        messagebox.showwarning("警告", "请先选择要删除的板块")
                # 按钮区域
                left_btn_frame = ttk.Frame(left_frame)
                left_btn_frame.pack(fill=tk.X)
                ttk.Button(left_btn_frame, text="添加", command=add_sector, width=10).pack(side=tk.LEFT, padx=2)
                ttk.Button(left_btn_frame, text="编辑", command=edit_sector, width=10).pack(side=tk.LEFT, padx=2)
                ttk.Button(left_btn_frame, text="删除", command=delete_sector, width=10).pack(side=tk.LEFT, padx=2)
                right_btn_frame = ttk.Frame(right_frame)
                right_btn_frame.pack(fill=tk.X)
                ttk.Button(right_btn_frame, text="添加到列表", command=add_from_ths, width=15).pack(side=tk.LEFT, padx=2)
                ttk.Button(right_btn_frame, text="刷新板块", command=lambda: load_ths_sectors("概念" if sector_type_var.get() == "概念板块" else "基本"), width=12).pack(side=tk.LEFT, padx=2)
                # 底部按钮
                bottom_frame = ttk.Frame(main_frame)
                bottom_frame.pack(fill=tk.X, pady=(10, 0))
                ttk.Button(bottom_frame, text="关闭", command=manage_window.destroy).pack(side=tk.RIGHT, padx=5)
                load_sectors()
            sector_list = ["科技", "医药", "消费", "金融", "新能源", "人工智能", "芯片", "军工"]
            sector_combo['values'] = sector_list
            ttk.Button(market_row3, text="管理", command=manage_sectors, width=8).pack(side=tk.LEFT)
            # 右侧:仓位管理规则
            right_top = ttk.LabelFrame(top_horizontal, text="仓位管理规则", padding=10)
            top_horizontal.add(right_top, weight=1)
            position_rules_text = """仓位管理规则(基于AI分析建议):
1. 单只股票仓位限制:
   - 单只股票持仓不超过总资金的10%
   - 避免过度集中风险
2. 行业仓位限制:
   - 单个行业暴露不超过总资金的20%
   - 保持行业分散化
3. 分批建仓原则(334原则):
   - 首次建仓:30%
   - 回调补仓:30%
   - 突破加仓:40%
4. 现金仓位管理:
   - 始终维持10%-20%现金
   - 应对极端市场波动
5. 核心持仓数量:
   - 聚焦5-8只核心股票
   - 避免过度分散化
6. 止盈止损规则:
   - 刚性止损:-8%
   - 移动止盈:盈利后回落20%平仓
   - 动态调整:根据市场情况灵活调整"""
            position_rules_text_widget = scrolledtext.ScrolledText(right_top, height=15, wrap=tk.WORD,
                                                                   font=("TkDefaultFont", 12))
            position_rules_text_widget.pack(fill=tk.BOTH, expand=True)
            position_rules_text_widget.insert("1.0", position_rules_text)
            position_rules_text_widget.config(state=tk.DISABLED)
            # 下半部分:股票配置管理
            bottom_frame = ttk.LabelFrame(top_paned, text="股票配置管理", padding=10)
            top_paned.add(bottom_frame, weight=2)
            # 股票列表和配置建议
            stock_config_frame = ttk.Frame(bottom_frame)
            stock_config_frame.pack(fill=tk.BOTH, expand=True)
            # 左侧:股票列表
            left_bottom = ttk.LabelFrame(stock_config_frame, text="股票列表", padding=10)
            left_bottom.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
            # 添加股票区域
            add_stock_frame = ttk.Frame(left_bottom)
            add_stock_frame.pack(fill=tk.X, pady=(0, 10))
            ttk.Label(add_stock_frame, text="股票/ETF代码名称:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(0, 5))
            # 创建输入框框架
            input_frame = ttk.Frame(add_stock_frame)
            input_frame.pack(side=tk.LEFT, padx=(0, 5))
            # 创建输入框(替代下拉框)
            stock_input_var = tk.StringVar()
            stock_input = ttk.Entry(input_frame, textvariable=stock_input_var, width=25, font=("TkDefaultFont", 12))
            stock_input.pack(side=tk.LEFT, padx=(0, 5))
            # 从数据库选取股票
            def select_from_stock_db():
                """从股票数据库选取"""
                db_window = self._toplevel(win)
                db_window.title("股票数据库")
                db_window.geometry("1000x600")
                db_window.transient(win)
                main_frame = ttk.Frame(db_window, padding=10)
                main_frame.pack(fill=tk.BOTH, expand=True)
                # 搜索框
                search_frame = ttk.Frame(main_frame)
                search_frame.pack(fill=tk.X, pady=(0, 10))
                ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT, padx=(0, 5))
                search_var = tk.StringVar()
                search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
                search_entry.pack(side=tk.LEFT, padx=(0, 5))
                def search_stocks():
                    search_text = search_var.get().strip()
                    # 清空表格
                    for item in tree.get_children():
                        tree.delete(item)
                    # 重新加载数据
                    load_stock_data(search_text)
                ttk.Button(search_frame, text="搜索", command=search_stocks).pack(side=tk.LEFT, padx=(0, 5))
                ttk.Button(search_frame, text="刷新", command=lambda: load_stock_data("")).pack(side=tk.LEFT)
                # 表格
                columns = ("股票代码", "股票名称", "日期", "价格", "涨跌幅", "成交量", "成交额", "市值", "市盈率", "板块", "主题")
                tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=20)
                for col in columns:
                    tree.heading(col, text=col)
                    tree.column(col, width=100, anchor=tk.CENTER)
                scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
                tree.configure(yscrollcommand=scrollbar.set)
                tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                def load_stock_data(search_text=""):
                    """加载股票数据"""
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        if search_text:
                            cursor.execute('''
                                SELECT DISTINCT stock_code, stock_name, date, price, change_pct,
                                       volume, turnover, market_cap, pe_ratio, sector, theme
                                FROM stock_data
                                WHERE stock_code LIKE ? OR stock_name LIKE ?
                                ORDER BY date DESC, stock_code
                                LIMIT 500
                            ''', (f'%{search_text}%', f'%{search_text}%'))
                        else:
                            cursor.execute('''
                                SELECT DISTINCT stock_code, stock_name, date, price, change_pct,
                                       volume, turnover, market_cap, pe_ratio, sector, theme
                                FROM stock_data
                                ORDER BY date DESC, stock_code
                                LIMIT 500
                            ''')
                        rows = cursor.fetchall()
                        conn.close()
                        # 清空表格
                        for item in tree.get_children():
                            tree.delete(item)
                        # 填充数据
                        for row in rows:
                            values = (
                                row[0] or "",  # stock_code
                                row[1] or "",  # stock_name
                                row[2] or "",  # date
                                f"{row[3]:.2f}" if row[3] else "",  # price
                                f"{row[4]:+.2f}%" if row[4] else "",  # change_pct
                                f"{row[5]:,.0f}" if row[5] else "",  # volume
                                f"{row[6]:,.0f}" if row[6] else "",  # turnover
                                f"{row[7]:,.0f}" if row[7] else "",  # market_cap
                                f"{row[8]:.2f}" if row[8] else "",  # pe_ratio
                                row[9] or "",  # sector
                                row[10] or ""  # theme
                            )
                            tree.insert('', tk.END, values=values)
                    except Exception as e:
                        messagebox.showerror("错误", f"加载数据失败: {e}")
                def on_select(event):
                    """选中股票后填入输入框"""
                    selection = tree.selection()
                    if selection:
                        item = tree.item(selection[0])
                        values = item['values']
                        if values:
                            stock_code = values[0]
                            stock_name = values[1]
                            # 优先使用股票名称,如果没有则使用代码
                            display_text = f"{stock_name}({stock_code})" if stock_name else stock_code
                            stock_input_var.set(display_text)
                            db_window.destroy()
                tree.bind("<Double-Button-1>", on_select)
                # 按钮区域
                btn_frame = ttk.Frame(main_frame)
                btn_frame.pack(fill=tk.X, pady=(10, 0))
                def select_and_close():
                    selection = tree.selection()
                    if selection:
                        item = tree.item(selection[0])
                        values = item['values']
                        if values:
                            stock_code = values[0]
                            stock_name = values[1]
                            display_text = f"{stock_name}({stock_code})" if stock_name else stock_code
                            stock_input_var.set(display_text)
                            db_window.destroy()
                    else:
                        messagebox.showwarning("警告", "请先选择一条记录")
                ttk.Button(btn_frame, text="选择", command=select_and_close).pack(side=tk.LEFT, padx=(0, 5))
                ttk.Button(btn_frame, text="关闭", command=db_window.destroy).pack(side=tk.LEFT)
                # 初始加载数据
                load_stock_data()
            # 从批量数据库选取股票
            def select_from_batch_db():
                """从批量数据库选取"""
                db_window = self._toplevel(win)
                db_window.title("批量数据库")
                db_window.geometry("1200x600")
                db_window.transient(win)
                main_frame = ttk.Frame(db_window, padding=10)
                main_frame.pack(fill=tk.BOTH, expand=True)
                # 搜索框
                search_frame = ttk.Frame(main_frame)
                search_frame.pack(fill=tk.X, pady=(0, 10))
                ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT, padx=(0, 5))
                search_var = tk.StringVar()
                search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
                search_entry.pack(side=tk.LEFT, padx=(0, 5))
                def search_stocks():
                    search_text = search_var.get().strip()
                    # 清空表格
                    for item in tree.get_children():
                        tree.delete(item)
                    # 重新加载数据
                    load_batch_data(search_text)
                ttk.Button(search_frame, text="搜索", command=search_stocks).pack(side=tk.LEFT, padx=(0, 5))
                ttk.Button(search_frame, text="刷新", command=lambda: load_batch_data("")).pack(side=tk.LEFT)
                # 表格
                columns = ("股票代码", "股票名称", "当前价格", "筹码成本价", "价格差价", "价格差价%",
                          "5日统计涨跌幅", "10日统计涨跌幅", "筹码均价涨跌幅", "分析日期", "是否血筹", "血筹排名")
                tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=20)
                column_widths = {
                    "股票代码": 100,
                    "股票名称": 120,
                    "当前价格": 90,
                    "筹码成本价": 100,
                    "价格差价": 90,
                    "价格差价%": 90,
                    "5日统计涨跌幅": 120,
                    "10日统计涨跌幅": 120,
                    "筹码均价涨跌幅": 120,
                    "分析日期": 100,
                    "是否血筹": 80,
                    "血筹排名": 80
                }
                for col in columns:
                    tree.heading(col, text=col)
                    tree.column(col, width=column_widths.get(col, 100), anchor=tk.CENTER)
                scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
                tree.configure(yscrollcommand=scrollbar.set)
                tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                def load_batch_data(search_text=""):
                    """加载批量分析数据"""
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        if search_text:
                            cursor.execute('''
                                SELECT stock_code, stock_name, current_price, chip_cost, price_diff, price_diff_pct,
                                       stat_5day, stat_10day, chip_avg_change, analysis_date, is_blood_chip, blood_chip_rank
                                FROM batch_analysis_results
                                WHERE stock_code LIKE ? OR stock_name LIKE ?
                                ORDER BY created_at DESC, stock_code
                                LIMIT 500
                            ''', (f'%{search_text}%', f'%{search_text}%'))
                        else:
                            cursor.execute('''
                                SELECT stock_code, stock_name, current_price, chip_cost, price_diff, price_diff_pct,
                                       stat_5day, stat_10day, chip_avg_change, analysis_date, is_blood_chip, blood_chip_rank
                                FROM batch_analysis_results
                                ORDER BY created_at DESC, stock_code
                                LIMIT 500
                            ''')
                        rows = cursor.fetchall()
                        conn.close()
                        # 清空表格
                        for item in tree.get_children():
                            tree.delete(item)
                        # 填充数据
                        for row in rows:
                            values = (
                                row[0] or "",  # stock_code
                                row[1] or "",  # stock_name
                                f"{row[2]:.2f}" if row[2] else "",  # current_price
                                f"{row[3]:.2f}" if row[3] else "",  # chip_cost
                                f"{row[4]:.2f}" if row[4] else "",  # price_diff
                                f"{row[5]:+.2f}%" if row[5] else "",  # price_diff_pct
                                f"{row[6]:+.2f}%" if row[6] else "",  # stat_5day
                                f"{row[7]:+.2f}%" if row[7] else "",  # stat_10day
                                f"{row[8]:+.2f}%" if row[8] else "",  # chip_avg_change
                                row[9] or "",  # analysis_date
                                "是" if row[10] else "否",  # is_blood_chip
                                str(row[11]) if row[11] else ""  # blood_chip_rank
                            )
                            tree.insert('', tk.END, values=values)
                    except Exception as e:
                        messagebox.showerror("错误", f"加载数据失败: {e}")
                def on_select(event):
                    """选中股票后填入输入框"""
                    selection = tree.selection()
                    if selection:
                        item = tree.item(selection[0])
                        values = item['values']
                        if values:
                            stock_code = values[0]
                            stock_name = values[1]
                            # 优先使用股票名称,如果没有则使用代码
                            display_text = f"{stock_name}({stock_code})" if stock_name else stock_code
                            stock_input_var.set(display_text)
                            db_window.destroy()
                tree.bind("<Double-Button-1>", on_select)
                # 按钮区域
                btn_frame = ttk.Frame(main_frame)
                btn_frame.pack(fill=tk.X, pady=(10, 0))
                def select_and_close():
                    selection = tree.selection()
                    if selection:
                        item = tree.item(selection[0])
                        values = item['values']
                        if values:
                            stock_code = values[0]
                            stock_name = values[1]
                            display_text = f"{stock_name}({stock_code})" if stock_name else stock_code
                            stock_input_var.set(display_text)
                            db_window.destroy()
                    else:
                        messagebox.showwarning("警告", "请先选择一条记录")
                ttk.Button(btn_frame, text="选择", command=select_and_close).pack(side=tk.LEFT, padx=(0, 5))
                ttk.Button(btn_frame, text="关闭", command=db_window.destroy).pack(side=tk.LEFT)
                # 初始加载数据
                load_batch_data()
            # 按钮框架
            btn_frame = ttk.Frame(input_frame)
            btn_frame.pack(side=tk.LEFT)
            ttk.Button(btn_frame, text="从数据库选取", command=select_from_stock_db, width=12).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(btn_frame, text="从批量数据库选取", command=select_from_batch_db, width=15).pack(side=tk.LEFT)
            # 创建多选列表框(用于显示已选择的项)
            selected_frame = ttk.LabelFrame(add_stock_frame, text="已选择", padding=5)
            selected_frame.pack(fill=tk.X, pady=(5, 0))
            selected_listbox = tk.Listbox(selected_frame, height=3, selectmode=tk.EXTENDED)
            selected_listbox.pack(fill=tk.X)
            selected_items = []  # 存储已选择的项
            def add_to_selected():
                """添加到已选择列表"""
                selected = stock_input_var.get().strip()
                if selected and selected not in selected_items:
                    selected_items.append(selected)
                    update_selected_listbox()
                    # 清空输入框
                    stock_input_var.set("")
            def remove_from_selected():
                """从已选择列表移除"""
                selection = selected_listbox.curselection()
                if selection:
                    indices = sorted(selection, reverse=True)
                    for idx in indices:
                        selected_items.pop(idx)
                    update_selected_listbox()
            def update_selected_listbox():
                """更新已选择列表框"""
                selected_listbox.delete(0, tk.END)
                for item in selected_items:
                    selected_listbox.insert(tk.END, item)
            # 选择按钮
            select_btn_frame = ttk.Frame(add_stock_frame)
            select_btn_frame.pack(fill=tk.X, pady=(5, 0))
            ttk.Button(select_btn_frame, text="添加到选择", command=add_to_selected, width=12).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(select_btn_frame, text="移除选择", command=remove_from_selected, width=12).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(select_btn_frame, text="清空选择", command=lambda: [selected_items.clear(), update_selected_listbox()], width=12).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(select_btn_frame, text="持仓计算", command=self._open_holding_calculator, width=12).pack(side=tk.LEFT)
            # 初始化默认列表(已改为输入框,不再需要更新下拉框)
            # stock_etf_list = ["000001", "平安银行", "600000", "浦发银行", "159919", "300ETF", "510300", "沪深300ETF"]
            # 批量分析策略选择
            batch_strategy_frame = ttk.LabelFrame(add_stock_frame, text="批量分析策略选择", padding=5)
            batch_strategy_frame.pack(fill=tk.X, pady=(5, 0))
            use_strategy_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(batch_strategy_frame, text="使用特定策略进行分析",
                           variable=use_strategy_var).pack(side=tk.LEFT, padx=(0, 10))
            batch_strategy_var = tk.StringVar(value="核心-卫星策略(70%稳健+30%机动)")
            batch_strategy_combo = ttk.Combobox(batch_strategy_frame, textvariable=batch_strategy_var,
                                               values=strategies, width=30, state="readonly")
            batch_strategy_combo.pack(side=tk.LEFT, padx=(0, 5))
            # 存储股票配置数据
            stock_configs = {}  # {stock_code: {name, sector, position, stop_loss, take_profit, target_price, strategy, ...}}
            # 存储策略建议数据
            strategy_advice_data = {}  # {stock_code: {strategy, advice, position, stop_loss, take_profit, target_price, ...}}
            def batch_analyze_stocks():
                """批量分析选中的股票/ETF"""
                if not selected_items:
                    messagebox.showwarning("警告", "请先选择要分析的股票/ETF")
                    return
                if len(selected_items) > 10:
                    if not messagebox.askyesno("确认", f"已选择{len(selected_items)}项,批量分析可能需要较长时间,是否继续?"):
                        return
                # 显示进度
                progress_window = self._toplevel(win)
                progress_window.title("批量分析中...")
                progress_window.geometry("400x150")
                progress_window.transient(win)
                progress_frame = ttk.Frame(progress_window, padding=20)
                progress_frame.pack(fill=tk.BOTH, expand=True)
                progress_label = ttk.Label(progress_frame, text=f"正在分析 0/{len(selected_items)}...", font=("TkDefaultFont", 12))
                progress_label.pack(pady=10)
                progress_bar = ttk.Progressbar(progress_frame, length=300, mode='determinate', maximum=len(selected_items))
                progress_bar.pack(pady=10)
                def analyze_in_thread():
                    """在线程中执行分析"""
                    try:
                        analyzed_count = 0
                        for idx, stock_input in enumerate(selected_items):
                            try:
                                # 更新进度
                                progress_window.after(0, lambda i=idx+1, total=len(selected_items):
                                    [progress_label.config(text=f"正在分析 {i}/{total}..."),
                                     progress_bar.config(value=i)])
                                # 解析股票信息(支持"股票名称(代码)"格式)
                                stock_code = stock_input
                                stock_name = stock_input
                                # 尝试解析"名称(代码)"格式
                                import re
                                match = re.match(r'(.+?)\((\d+)\)', stock_input)
                                if match:
                                    stock_name = match.group(1).strip()
                                    stock_code = match.group(2).strip()
                                else:
                                    # 如果只是代码或名称,尝试判断
                                    if stock_input.isdigit() or (len(stock_input) == 6 and stock_input.isdigit()):
                                        stock_code = stock_input
                                        stock_name = stock_input  # 如果没有名称,使用代码
                                    else:
                                        stock_name = stock_input
                                        stock_code = stock_input  # 如果没有代码,使用名称
                                # 判断是否为ETF代码
                                if stock_code.startswith(('159', '510', '511', '512', '513', '515', '516', '517', '518', '588')):
                                    stock_type = "ETF"
                                else:
                                    stock_type = "股票"
                                # 确定使用的策略
                                if use_strategy_var.get():
                                    selected_strategy = batch_strategy_var.get()
                                else:
                                    selected_strategy = strategy_var.get()
                                # 生成配置建议
                                config_advice = self._generate_stock_config_advice(
                                    stock_code, stock_name,
                                    selected_strategy,
                                    market_status_var.get(),
                                    peripheral_sentiment_var.get(),
                                    sector_var.get(),
                                    stock_type
                                )
                                # 如果使用特定策略,生成策略专项建议
                                strategy_specific_advice = ""
                                if use_strategy_var.get():
                                    strategy_specific_advice = self._generate_strategy_specific_advice(
                                        stock_code, stock_name, selected_strategy,
                                        market_status_var.get(), peripheral_sentiment_var.get(),
                                        sector_var.get(), stock_type
                                )
                                # 添加到股票列表
                                if stock_code not in stock_configs:
                                    stock_configs[stock_code] = {
                                        'code': stock_code,
                                        'name': stock_name,
                                        'type': stock_type,
                                        'sector': sector_var.get() or "未分类",
                                        'strategy': selected_strategy,
                                        'position': 0,
                                        'stop_loss': 0,
                                        'take_profit': 0,
                                        'target_price': 0,
                                        'advice': config_advice,
                                        'strategy_advice': strategy_specific_advice
                                    }
                                    # 如果使用特定策略,保存策略建议数据
                                    if use_strategy_var.get() and strategy_specific_advice:
                                        strategy_advice_data[stock_code] = {
                                            'code': stock_code,
                                            'name': stock_name,
                                            'strategy': selected_strategy,
                                            'advice': strategy_specific_advice
                                    }
                                    analyzed_count += 1
                            except Exception as e:
                                print(f"分析 {stock_input} 失败: {e}")
                                continue
                        # 更新界面
                        progress_window.after(0, lambda: [
                            update_stock_list(),
                            progress_window.destroy(),
                            messagebox.showinfo("完成", f"批量分析完成!成功分析 {analyzed_count} 只股票/ETF")
                        ])
                    except Exception as e:
                        progress_window.after(0, lambda e=e: [
                            progress_window.destroy(),
                            messagebox.showerror("错误", f"批量分析失败: {e}")
                        ])
                # 启动分析线程
                threading.Thread(target=analyze_in_thread, daemon=True).start()
            ttk.Button(add_stock_frame, text="批量分析", command=batch_analyze_stocks, width=12).pack(side=tk.LEFT, padx=(10, 0))
            # 保存和加载按钮
            save_load_frame = ttk.Frame(left_bottom)
            save_load_frame.pack(fill=tk.X, pady=(0, 10))
            # 定义DB显示窗口函数(需要在按钮之前定义)
            def show_db_table_window(parent_window):
                """显示数据库表格窗口"""
                db_window = self._toplevel(parent_window)
                db_window.title("交易体系数据库管理")
                db_window.geometry("1400x800")
                db_window.transient(parent_window)
                db_window.resizable(True, True)
                # 主容器
                main_frame = ttk.Frame(db_window, padding=10)
                main_frame.pack(fill=tk.BOTH, expand=True)
                # 顶部工具栏
                toolbar_frame = ttk.Frame(main_frame)
                toolbar_frame.pack(fill=tk.X, pady=(0, 10))
                # 搜索框
                search_frame = ttk.Frame(toolbar_frame)
                search_frame.pack(side=tk.LEFT, padx=(0, 10))
                ttk.Label(search_frame, text="搜索:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(0, 5))
                search_var = tk.StringVar()
                search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
                search_entry.pack(side=tk.LEFT, padx=(0, 5))
                def perform_search():
                    """执行搜索"""
                    search_text = search_var.get().strip().lower()
                    if not search_text:
                        load_data()
                        return
                    # 清空表格
                    for item in db_tree.get_children():
                        db_tree.delete(item)
                    # 搜索数据
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT id, stock_code, stock_name, stock_type, sector, strategy,
                                   market_status, peripheral_sentiment, position, stop_loss,
                                   take_profit, target_price, created_at, updated_at
                            FROM trading_system_configs
                            WHERE stock_code LIKE ? OR stock_name LIKE ? OR sector LIKE ?
                               OR strategy LIKE ? OR market_status LIKE ?
                            ORDER BY updated_at DESC
                        ''', (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%',
                              f'%{search_text}%', f'%{search_text}%'))
                        records = cursor.fetchall()
                        conn.close()
                        for record in records:
                            db_tree.insert("", tk.END, values=record)
                    except Exception as e:
                        messagebox.showerror("错误", f"搜索失败: {e}")
                ttk.Button(search_frame, text="搜索", command=perform_search, width=8).pack(side=tk.LEFT)
                search_entry.bind("<Return>", lambda e: perform_search())
                # 操作按钮
                button_frame = ttk.Frame(toolbar_frame)
                button_frame.pack(side=tk.RIGHT)
                def refresh_data():
                    """刷新数据"""
                    search_var.set("")
                    load_data()
                def add_record():
                    """添加记录"""
                    add_window = self._toplevel(db_window)
                    add_window.title("添加记录")
                    add_window.geometry("600x500")
                    add_window.transient(db_window)
                    form_frame = ttk.Frame(add_window, padding=20)
                    form_frame.pack(fill=tk.BOTH, expand=True)
                    fields = [
                        ("股票代码", "stock_code"),
                        ("股票名称", "stock_name"),
                        ("类型", "stock_type"),
                        ("板块", "sector"),
                        ("策略", "strategy"),
                        ("大盘情况", "market_status"),
                        ("外围情绪", "peripheral_sentiment"),
                        ("仓位%", "position"),
                        ("止损%", "stop_loss"),
                        ("止盈%", "take_profit"),
                        ("目标价", "target_price")
                    ]
                    entry_vars = {}
                    for i, (label, key) in enumerate(fields):
                        row = ttk.Frame(form_frame)
                        row.pack(fill=tk.X, pady=5)
                        ttk.Label(row, text=f"{label}:", width=15).pack(side=tk.LEFT)
                        var = tk.StringVar()
                        entry = ttk.Entry(row, textvariable=var, width=30)
                        entry.pack(side=tk.LEFT, padx=(5, 0))
                        entry_vars[key] = var
                    def save_new_record():
                        try:
                            conn = sqlite3.connect(DB_PATH)
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO trading_system_configs
                                (stock_code, stock_name, stock_type, sector, strategy, market_status,
                                 peripheral_sentiment, position, stop_loss, take_profit, target_price)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                entry_vars['stock_code'].get(),
                                entry_vars['stock_name'].get(),
                                entry_vars['stock_type'].get() or '股票',
                                entry_vars['sector'].get() or '未分类',
                                entry_vars['strategy'].get(),
                                entry_vars['market_status'].get(),
                                float(entry_vars['peripheral_sentiment'].get() or 0),
                                float(entry_vars['position'].get() or 0),
                                float(entry_vars['stop_loss'].get() or 0),
                                float(entry_vars['take_profit'].get() or 0),
                                float(entry_vars['target_price'].get() or 0)
                            ))
                            conn.commit()
                            conn.close()
                            messagebox.showinfo("成功", "记录已添加")
                            add_window.destroy()
                            refresh_data()
                        except Exception as e:
                            messagebox.showerror("错误", f"添加失败: {e}")
                    ttk.Button(form_frame, text="保存", command=save_new_record, width=15).pack(pady=10)
                def edit_record():
                    """编辑记录"""
                    selection = db_tree.selection()
                    if not selection:
                        messagebox.showwarning("警告", "请先选择要编辑的记录")
                        return
                    item = db_tree.item(selection[0])
                    record_id = item['values'][0]
                    edit_window = self._toplevel(db_window)
                    edit_window.title("编辑记录")
                    edit_window.geometry("600x500")
                    edit_window.transient(db_window)
                    form_frame = ttk.Frame(edit_window, padding=20)
                    form_frame.pack(fill=tk.BOTH, expand=True)
                    # 获取原数据
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT stock_code, stock_name, stock_type, sector, strategy, market_status,
                                   peripheral_sentiment, position, stop_loss, take_profit, target_price
                            FROM trading_system_configs WHERE id = ?
                        ''', (record_id,))
                        record = cursor.fetchone()
                        conn.close()
                        if not record:
                            messagebox.showerror("错误", "记录不存在")
                            edit_window.destroy()
                            return
                    except Exception as e:
                        messagebox.showerror("错误", f"获取数据失败: {e}")
                        edit_window.destroy()
                        return
                    fields = [
                        ("股票代码", "stock_code"),
                        ("股票名称", "stock_name"),
                        ("类型", "stock_type"),
                        ("板块", "sector"),
                        ("策略", "strategy"),
                        ("大盘情况", "market_status"),
                        ("外围情绪", "peripheral_sentiment"),
                        ("仓位%", "position"),
                        ("止损%", "stop_loss"),
                        ("止盈%", "take_profit"),
                        ("目标价", "target_price")
                    ]
                    entry_vars = {}
                    for i, (label, key) in enumerate(fields):
                        row = ttk.Frame(form_frame)
                        row.pack(fill=tk.X, pady=5)
                        ttk.Label(row, text=f"{label}:", width=15).pack(side=tk.LEFT)
                        var = tk.StringVar(value=str(record[i] if record[i] is not None else ''))
                        entry = ttk.Entry(row, textvariable=var, width=30)
                        entry.pack(side=tk.LEFT, padx=(5, 0))
                        entry_vars[key] = var
                    def save_edited_record():
                        try:
                            conn = sqlite3.connect(DB_PATH)
                            cursor = conn.cursor()
                            cursor.execute('''
                                UPDATE trading_system_configs
                                SET stock_code=?, stock_name=?, stock_type=?, sector=?, strategy=?,
                                    market_status=?, peripheral_sentiment=?, position=?, stop_loss=?,
                                    take_profit=?, target_price=?, updated_at=datetime('now')
                                WHERE id=?
                            ''', (
                                entry_vars['stock_code'].get(),
                                entry_vars['stock_name'].get(),
                                entry_vars['stock_type'].get() or '股票',
                                entry_vars['sector'].get() or '未分类',
                                entry_vars['strategy'].get(),
                                entry_vars['market_status'].get(),
                                float(entry_vars['peripheral_sentiment'].get() or 0),
                                float(entry_vars['position'].get() or 0),
                                float(entry_vars['stop_loss'].get() or 0),
                                float(entry_vars['take_profit'].get() or 0),
                                float(entry_vars['target_price'].get() or 0),
                                record_id
                            ))
                            conn.commit()
                            conn.close()
                            messagebox.showinfo("成功", "记录已更新")
                            edit_window.destroy()
                            refresh_data()
                        except Exception as e:
                            messagebox.showerror("错误", f"更新失败: {e}")
                    ttk.Button(form_frame, text="保存", command=save_edited_record, width=15).pack(pady=10)
                def delete_record():
                    """删除记录"""
                    selection = db_tree.selection()
                    if not selection:
                        messagebox.showwarning("警告", "请先选择要删除的记录")
                        return
                    if not messagebox.askyesno("确认", "确定要删除选中的记录吗?"):
                        return
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        for item_id in selection:
                            item = db_tree.item(item_id)
                            record_id = item['values'][0]
                            cursor.execute('DELETE FROM trading_system_configs WHERE id=?', (record_id,))
                        conn.commit()
                        conn.close()
                        messagebox.showinfo("成功", "记录已删除")
                        refresh_data()
                    except Exception as e:
                        messagebox.showerror("错误", f"删除失败: {e}")
                def copy_record():
                    """复制记录"""
                    selection = db_tree.selection()
                    if not selection:
                        messagebox.showwarning("警告", "请先选择要复制的记录")
                        return
                    try:
                        item = db_tree.item(selection[0])
                        values = item['values']
                        # 格式化复制内容
                        copy_text = f"""股票代码: {values[1]}
股票名称: {values[2]}
类型: {values[3]}
板块: {values[4]}
策略: {values[5]}
大盘情况: {values[6]}
外围情绪: {values[7]}
仓位%: {values[8]}
止损%: {values[9]}
止盈%: {values[10]}
目标价: {values[11]}
创建时间: {values[12]}
更新时间: {values[13]}"""
                        db_window.clipboard_clear()
                        db_window.clipboard_append(copy_text)
                        messagebox.showinfo("成功", "记录已复制到剪贴板")
                    except Exception as e:
                        messagebox.showerror("错误", f"复制失败: {e}")
                def save_long_image():
                    """保存长图"""
                    try:
                        # 获取表格数据
                        data = []
                        for item in db_tree.get_children():
                            values = db_tree.item(item)['values']
                            data.append(values)
                        if not data:
                            messagebox.showwarning("警告", "没有数据可保存")
                            return
                        # 创建图像

                        from PIL import Image, ImageDraw, ImageFont
                        # 计算图像尺寸
                        row_height = 30
                        header_height = 40
                        col_widths = [80, 100, 120, 60, 100, 120, 100, 80, 80, 80, 80, 100, 150, 150]
                        img_width = sum(col_widths) + 40
                        img_height = header_height + len(data) * row_height + 40
                        # 创建图像
                        img = Image.new('RGB', (img_width, img_height), 'white')
                        draw = ImageDraw.Draw(img)
                        # 尝试加载字体
                        try:
                            font = ImageFont.truetype("simhei.ttf", 14)
                            header_font = ImageFont.truetype("simhei.ttf", 16)
                        except:
                            font = ImageFont.load_default()
                            header_font = ImageFont.load_default()
                        # 绘制表头
                        x = 20
                        y = 20
                        headers = ["ID", "代码", "名称", "类型", "板块", "策略", "大盘", "外围", "仓位%", "止损%", "止盈%", "目标价", "创建时间", "更新时间"]
                        for i, header in enumerate(headers):
                            draw.rectangle([x, y, x + col_widths[i], y + header_height], outline='black', width=1)
                            draw.text((x + 5, y + 10), header, fill='black', font=header_font)
                            x += col_widths[i]
                        # 绘制数据
                        y = header_height + 20
                        for row_data in data:
                            x = 20
                            for i, value in enumerate(row_data):
                                draw.rectangle([x, y, x + col_widths[i], y + row_height], outline='black', width=1)
                                draw.text((x + 5, y + 5), str(value)[:20] if value else '', fill='black', font=font)
                                x += col_widths[i]
                            y += row_height
                        # 保存图像
                        file_path = filedialog.asksaveasfilename(
                            title="保存长图",
                            defaultextension=".png",
                            filetypes=[("PNG图片", "*.png"), ("所有文件", "*.*")]
                        )
                        if file_path:
                            img.save(file_path)
                            messagebox.showinfo("成功", f"长图已保存到:\n{file_path}")
                    except Exception as e:
                        messagebox.showerror("错误", f"保存长图失败: {e}")
                        import traceback
                        traceback.print_exc()
                ttk.Button(button_frame, text="刷新", command=refresh_data, width=10).pack(side=tk.LEFT, padx=2)
                ttk.Button(button_frame, text="添加", command=add_record, width=10).pack(side=tk.LEFT, padx=2)
                ttk.Button(button_frame, text="编辑", command=edit_record, width=10).pack(side=tk.LEFT, padx=2)
                ttk.Button(button_frame, text="删除", command=delete_record, width=10).pack(side=tk.LEFT, padx=2)
                ttk.Button(button_frame, text="复制", command=copy_record, width=10).pack(side=tk.LEFT, padx=2)
                ttk.Button(button_frame, text="保存长图", command=save_long_image, width=12).pack(side=tk.LEFT, padx=2)
                # 数据表格
                table_frame = ttk.Frame(main_frame)
                table_frame.pack(fill=tk.BOTH, expand=True)
                # 创建滚动条
                scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
                scrollbar_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
                # 创建表格
                db_columns = ("ID", "代码", "名称", "类型", "板块", "策略", "大盘", "外围", "仓位%", "止损%", "止盈%", "目标价", "创建时间", "更新时间")
                db_tree = ttk.Treeview(table_frame, columns=db_columns, show="headings",
                                      yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
                # 配置列
                col_widths = {"ID": 50, "代码": 100, "名称": 120, "类型": 60, "板块": 100,
                             "策略": 120, "大盘": 100, "外围": 80, "仓位%": 80, "止损%": 80,
                             "止盈%": 80, "目标价": 100, "创建时间": 150, "更新时间": 150}
                for col in db_columns:
                    db_tree.heading(col, text=col)
                    db_tree.column(col, width=col_widths.get(col, 100))
                scrollbar_y.config(command=db_tree.yview)
                scrollbar_x.config(command=db_tree.xview)
                db_tree.grid(row=0, column=0, sticky="nsew")
                scrollbar_y.grid(row=0, column=1, sticky="ns")
                scrollbar_x.grid(row=1, column=0, sticky="ew")
                table_frame.grid_rowconfigure(0, weight=1)
                table_frame.grid_columnconfigure(0, weight=1)
                def load_data():
                    """加载数据"""
                    # 清空表格
                    for item in db_tree.get_children():
                        db_tree.delete(item)
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT id, stock_code, stock_name, stock_type, sector, strategy,
                                   market_status, peripheral_sentiment, position, stop_loss,
                                   take_profit, target_price, created_at, updated_at
                            FROM trading_system_configs
                            ORDER BY updated_at DESC
                        ''')
                        records = cursor.fetchall()
                        conn.close()
                        for record in records:
                            db_tree.insert("", tk.END, values=record)
                    except Exception as e:
                        messagebox.showerror("错误", f"加载数据失败: {e}")
                # 初始加载
                load_data()
            def save_to_db():
                """保存当前配置到数据库"""
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    # 确保strategy和strategy_advice列存在
                    try:
                        cursor.execute("ALTER TABLE trading_system_configs ADD COLUMN strategy TEXT")
                    except:
                        pass  # 列已存在
                    try:
                        cursor.execute("ALTER TABLE trading_system_configs ADD COLUMN strategy_advice TEXT")
                    except:
                        pass  # 列已存在
                    saved_count = 0
                    for code, config in stock_configs.items():
                        try:
                            cursor.execute('''
                                INSERT OR REPLACE INTO trading_system_configs
                                (stock_code, stock_name, stock_type, sector, strategy, market_status,
                                 peripheral_sentiment, position, stop_loss, take_profit, target_price,
                                 config_advice, strategy_advice, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                            ''', (
                                config.get('code', ''),
                                config.get('name', ''),
                                config.get('type', '股票'),
                                config.get('sector', '未分类'),
                                config.get('strategy', strategy_var.get()),  # 使用配置中的策略名
                                market_status_var.get(),
                                float(peripheral_sentiment_var.get() or 0),
                                float(config.get('position', 0) or 0),
                                float(config.get('stop_loss', 0) or 0),
                                float(config.get('take_profit', 0) or 0),
                                float(config.get('target_price', 0) or 0),
                                config.get('advice', ''),
                                config.get('strategy_advice', '')  # 添加策略专项建议
                            ))
                            saved_count += 1
                        except Exception as e:
                            print(f"保存配置 {code} 失败: {e}")
                            continue
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("成功", f"已保存 {saved_count} 条配置到数据库")
                except Exception as e:
                    messagebox.showerror("错误", f"保存失败: {e}")
            def load_from_db(show_message=False):
                """从数据库加载前10条数据"""
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    # 检查strategy_advice列是否存在
                    cursor.execute("PRAGMA table_info(trading_system_configs)")
                    columns = [col[1] for col in cursor.fetchall()]
                    has_strategy_advice = 'strategy_advice' in columns
                    if has_strategy_advice:
                        cursor.execute('''
                            SELECT stock_code, stock_name, stock_type, sector, strategy, market_status,
                                   peripheral_sentiment, position, stop_loss, take_profit, target_price,
                                   config_advice, strategy_advice
                            FROM trading_system_configs
                            ORDER BY updated_at DESC
                            LIMIT 10
                        ''')
                    else:
                        cursor.execute('''
                            SELECT stock_code, stock_name, stock_type, sector, strategy, market_status,
                                   peripheral_sentiment, position, stop_loss, take_profit, target_price, config_advice
                            FROM trading_system_configs
                            ORDER BY updated_at DESC
                            LIMIT 10
                        ''')
                    records = cursor.fetchall()
                    conn.close()
                    if not records:
                        if show_message:
                            messagebox.showinfo("提示", "数据库中没有保存的配置")
                        return
                    # 清空现有配置
                    stock_configs.clear()
                    # 加载数据
                    for record in records:
                        if has_strategy_advice and len(record) >= 13:
                            code, name, stock_type, sector_val, strategy_val, market_status_val, \
                            peripheral_val, position_val, stop_loss_val, take_profit_val, target_price_val, \
                            advice, strategy_advice_val = record
                        else:
                            code, name, stock_type, sector_val, strategy_val, _market_status_val, \
                            _peripheral_val, position_val, stop_loss_val, take_profit_val, target_price_val, advice = record
                            strategy_advice_val = ''
                        stock_configs[code] = {
                            'code': code,
                            'name': name,
                            'type': stock_type or '股票',
                            'sector': sector_val or '未分类',
                            'strategy': strategy_val or '',  # 加载策略名
                            'position': position_val or 0,
                            'stop_loss': stop_loss_val or 0,
                            'take_profit': take_profit_val or 0,
                            'target_price': target_price_val or 0,
                            'advice': advice or '',
                            'strategy_advice': strategy_advice_val or ''  # 加载策略专项建议
                        }
                    # 更新界面
                    update_stock_list()
                    if show_message:
                        messagebox.showinfo("成功", f"已加载 {len(records)} 条配置")
                except Exception as e:
                    if show_message:
                        messagebox.showerror("错误", f"加载失败: {e}")
            ttk.Button(save_load_frame, text="保存到数据库", command=save_to_db, width=15).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(save_load_frame, text="从数据库加载", command=lambda: load_from_db(show_message=True), width=15).pack(side=tk.LEFT, padx=(0, 5))
            # 定义DB显示窗口函数
            def show_db_table_window(parent_window):
                """显示数据库表格窗口"""
                db_window = self._toplevel(parent_window)
                db_window.title("交易体系数据库管理")
                db_window.geometry("1400x800")
                db_window.transient(parent_window)
                db_window.resizable(True, True)
                # 主容器
                main_frame = ttk.Frame(db_window, padding=10)
                main_frame.pack(fill=tk.BOTH, expand=True)
                # 顶部工具栏
                toolbar_frame = ttk.Frame(main_frame)
                toolbar_frame.pack(fill=tk.X, pady=(0, 10))
                # 搜索框
                search_frame = ttk.Frame(toolbar_frame)
                search_frame.pack(side=tk.LEFT, padx=(0, 10))
                ttk.Label(search_frame, text="搜索:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(0, 5))
                search_var = tk.StringVar()
                search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
                search_entry.pack(side=tk.LEFT, padx=(0, 5))
                def perform_search():
                    """执行搜索"""
                    search_text = search_var.get().strip().lower()
                    if not search_text:
                        load_data()
                        return
                    # 清空表格
                    for item in db_tree.get_children():
                        db_tree.delete(item)
                    # 搜索数据
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT id, stock_code, stock_name, stock_type, sector, strategy,
                                   market_status, peripheral_sentiment, position, stop_loss,
                                   take_profit, target_price, created_at, updated_at
                            FROM trading_system_configs
                            WHERE stock_code LIKE ? OR stock_name LIKE ? OR sector LIKE ?
                               OR strategy LIKE ? OR market_status LIKE ?
                            ORDER BY updated_at DESC
                        ''', (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%',
                              f'%{search_text}%', f'%{search_text}%'))
                        records = cursor.fetchall()
                        conn.close()
                        for record in records:
                            db_tree.insert("", tk.END, values=record)
                    except Exception as e:
                        messagebox.showerror("错误", f"搜索失败: {e}")
                ttk.Button(search_frame, text="搜索", command=perform_search, width=8).pack(side=tk.LEFT)
                search_entry.bind("<Return>", lambda e: perform_search())
                # 操作按钮
                button_frame = ttk.Frame(toolbar_frame)
                button_frame.pack(side=tk.RIGHT)
                def refresh_data():
                    """刷新数据"""
                    search_var.set("")
                    load_data()
                def add_record():
                    """添加记录"""
                    add_window = self._toplevel(db_window)
                    add_window.title("添加记录")
                    add_window.geometry("600x500")
                    add_window.transient(db_window)
                    form_frame = ttk.Frame(add_window, padding=20)
                    form_frame.pack(fill=tk.BOTH, expand=True)
                    fields = [
                        ("股票代码", "stock_code"),
                        ("股票名称", "stock_name"),
                        ("类型", "stock_type"),
                        ("板块", "sector"),
                        ("策略", "strategy"),
                        ("大盘情况", "market_status"),
                        ("外围情绪", "peripheral_sentiment"),
                        ("仓位%", "position"),
                        ("止损%", "stop_loss"),
                        ("止盈%", "take_profit"),
                        ("目标价", "target_price")
                    ]
                    entry_vars = {}
                    for i, (label, key) in enumerate(fields):
                        row = ttk.Frame(form_frame)
                        row.pack(fill=tk.X, pady=5)
                        ttk.Label(row, text=f"{label}:", width=15).pack(side=tk.LEFT)
                        var = tk.StringVar()
                        entry = ttk.Entry(row, textvariable=var, width=30)
                        entry.pack(side=tk.LEFT, padx=(5, 0))
                        entry_vars[key] = var
                    def save_new_record():
                        try:
                            conn = sqlite3.connect(DB_PATH)
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO trading_system_configs
                                (stock_code, stock_name, stock_type, sector, strategy, market_status,
                                 peripheral_sentiment, position, stop_loss, take_profit, target_price)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                entry_vars['stock_code'].get(),
                                entry_vars['stock_name'].get(),
                                entry_vars['stock_type'].get() or '股票',
                                entry_vars['sector'].get() or '未分类',
                                entry_vars['strategy'].get(),
                                entry_vars['market_status'].get(),
                                float(entry_vars['peripheral_sentiment'].get() or 0),
                                float(entry_vars['position'].get() or 0),
                                float(entry_vars['stop_loss'].get() or 0),
                                float(entry_vars['take_profit'].get() or 0),
                                float(entry_vars['target_price'].get() or 0)
                            ))
                            conn.commit()
                            conn.close()
                            messagebox.showinfo("成功", "记录已添加")
                            add_window.destroy()
                            refresh_data()
                        except Exception as e:
                            messagebox.showerror("错误", f"添加失败: {e}")
                    ttk.Button(form_frame, text="保存", command=save_new_record, width=15).pack(pady=10)
                def edit_record():
                    """编辑记录"""
                    selection = db_tree.selection()
                    if not selection:
                        messagebox.showwarning("警告", "请先选择要编辑的记录")
                        return
                    item = db_tree.item(selection[0])
                    record_id = item['values'][0]
                    edit_window = self._toplevel(db_window)
                    edit_window.title("编辑记录")
                    edit_window.geometry("600x500")
                    edit_window.transient(db_window)
                    form_frame = ttk.Frame(edit_window, padding=20)
                    form_frame.pack(fill=tk.BOTH, expand=True)
                    # 获取原数据
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT stock_code, stock_name, stock_type, sector, strategy, market_status,
                                   peripheral_sentiment, position, stop_loss, take_profit, target_price
                            FROM trading_system_configs WHERE id = ?
                        ''', (record_id,))
                        record = cursor.fetchone()
                        conn.close()
                        if not record:
                            messagebox.showerror("错误", "记录不存在")
                            edit_window.destroy()
                            return
                    except Exception as e:
                        messagebox.showerror("错误", f"获取数据失败: {e}")
                        edit_window.destroy()
                        return
                    fields = [
                        ("股票代码", "stock_code"),
                        ("股票名称", "stock_name"),
                        ("类型", "stock_type"),
                        ("板块", "sector"),
                        ("策略", "strategy"),
                        ("大盘情况", "market_status"),
                        ("外围情绪", "peripheral_sentiment"),
                        ("仓位%", "position"),
                        ("止损%", "stop_loss"),
                        ("止盈%", "take_profit"),
                        ("目标价", "target_price")
                    ]
                    entry_vars = {}
                    for i, (label, key) in enumerate(fields):
                        row = ttk.Frame(form_frame)
                        row.pack(fill=tk.X, pady=5)
                        ttk.Label(row, text=f"{label}:", width=15).pack(side=tk.LEFT)
                        var = tk.StringVar(value=str(record[i] if record[i] is not None else ''))
                        entry = ttk.Entry(row, textvariable=var, width=30)
                        entry.pack(side=tk.LEFT, padx=(5, 0))
                        entry_vars[key] = var
                    def save_edited_record():
                        try:
                            conn = sqlite3.connect(DB_PATH)
                            cursor = conn.cursor()
                            cursor.execute('''
                                UPDATE trading_system_configs
                                SET stock_code=?, stock_name=?, stock_type=?, sector=?, strategy=?,
                                    market_status=?, peripheral_sentiment=?, position=?, stop_loss=?,
                                    take_profit=?, target_price=?, updated_at=datetime('now')
                                WHERE id=?
                            ''', (
                                entry_vars['stock_code'].get(),
                                entry_vars['stock_name'].get(),
                                entry_vars['stock_type'].get() or '股票',
                                entry_vars['sector'].get() or '未分类',
                                entry_vars['strategy'].get(),
                                entry_vars['market_status'].get(),
                                float(entry_vars['peripheral_sentiment'].get() or 0),
                                float(entry_vars['position'].get() or 0),
                                float(entry_vars['stop_loss'].get() or 0),
                                float(entry_vars['take_profit'].get() or 0),
                                float(entry_vars['target_price'].get() or 0),
                                record_id
                            ))
                            conn.commit()
                            conn.close()
                            messagebox.showinfo("成功", "记录已更新")
                            edit_window.destroy()
                            refresh_data()
                        except Exception as e:
                            messagebox.showerror("错误", f"更新失败: {e}")
                    ttk.Button(form_frame, text="保存", command=save_edited_record, width=15).pack(pady=10)
                def delete_record():
                    """删除记录"""
                    selection = db_tree.selection()
                    if not selection:
                        messagebox.showwarning("警告", "请先选择要删除的记录")
                        return
                    if not messagebox.askyesno("确认", "确定要删除选中的记录吗?"):
                        return
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        for item_id in selection:
                            item = db_tree.item(item_id)
                            record_id = item['values'][0]
                            cursor.execute('DELETE FROM trading_system_configs WHERE id=?', (record_id,))
                        conn.commit()
                        conn.close()
                        messagebox.showinfo("成功", "记录已删除")
                        refresh_data()
                    except Exception as e:
                        messagebox.showerror("错误", f"删除失败: {e}")
                def copy_record():
                    """复制记录"""
                    selection = db_tree.selection()
                    if not selection:
                        messagebox.showwarning("警告", "请先选择要复制的记录")
                        return
                    try:
                        item = db_tree.item(selection[0])
                        values = item['values']
                        # 格式化复制内容
                        copy_text = f"""股票代码: {values[1]}
股票名称: {values[2]}
类型: {values[3]}
板块: {values[4]}
策略: {values[5]}
大盘情况: {values[6]}
外围情绪: {values[7]}
仓位%: {values[8]}
止损%: {values[9]}
止盈%: {values[10]}
目标价: {values[11]}
创建时间: {values[12]}
更新时间: {values[13]}"""
                        db_window.clipboard_clear()
                        db_window.clipboard_append(copy_text)
                        messagebox.showinfo("成功", "记录已复制到剪贴板")
                    except Exception as e:
                        messagebox.showerror("错误", f"复制失败: {e}")
                def save_long_image():
                    """保存长图"""
                    try:
                        # 获取表格数据
                        data = []
                        for item in db_tree.get_children():
                            values = db_tree.item(item)['values']
                            data.append(values)
                        if not data:
                            messagebox.showwarning("警告", "没有数据可保存")
                            return
                        # 创建图像

                        from PIL import Image, ImageDraw, ImageFont
                        # 计算图像尺寸
                        row_height = 30
                        header_height = 40
                        col_widths = [80, 100, 120, 60, 100, 120, 100, 80, 80, 80, 80, 100, 150, 150]
                        img_width = sum(col_widths) + 40
                        img_height = header_height + len(data) * row_height + 40
                        # 创建图像
                        img = Image.new('RGB', (img_width, img_height), 'white')
                        draw = ImageDraw.Draw(img)
                        # 尝试加载字体
                        try:
                            font = ImageFont.truetype("simhei.ttf", 14)
                            header_font = ImageFont.truetype("simhei.ttf", 16)
                        except:
                            font = ImageFont.load_default()
                            header_font = ImageFont.load_default()
                        # 绘制表头
                        x = 20
                        y = 20
                        headers = ["ID", "代码", "名称", "类型", "板块", "策略", "大盘", "外围", "仓位%", "止损%", "止盈%", "目标价", "创建时间", "更新时间"]
                        for i, header in enumerate(headers):
                            draw.rectangle([x, y, x + col_widths[i], y + header_height], outline='black', width=1)
                            draw.text((x + 5, y + 10), header, fill='black', font=header_font)
                            x += col_widths[i]
                        # 绘制数据
                        y = header_height + 20
                        for row_data in data:
                            x = 20
                            for i, value in enumerate(row_data):
                                draw.rectangle([x, y, x + col_widths[i], y + row_height], outline='black', width=1)
                                draw.text((x + 5, y + 5), str(value)[:20] if value else '', fill='black', font=font)
                                x += col_widths[i]
                            y += row_height
                        # 保存图像
                        file_path = filedialog.asksaveasfilename(
                            title="保存长图",
                            defaultextension=".png",
                            filetypes=[("PNG图片", "*.png"), ("所有文件", "*.*")]
                        )
                        if file_path:
                            img.save(file_path)
                            messagebox.showinfo("成功", f"长图已保存到:\n{file_path}")
                    except Exception as e:
                        messagebox.showerror("错误", f"保存长图失败: {e}")
                        import traceback
                        traceback.print_exc()
                ttk.Button(button_frame, text="刷新", command=refresh_data, width=10).pack(side=tk.LEFT, padx=2)
                ttk.Button(button_frame, text="添加", command=add_record, width=10).pack(side=tk.LEFT, padx=2)
                ttk.Button(button_frame, text="编辑", command=edit_record, width=10).pack(side=tk.LEFT, padx=2)
                ttk.Button(button_frame, text="删除", command=delete_record, width=10).pack(side=tk.LEFT, padx=2)
                ttk.Button(button_frame, text="复制", command=copy_record, width=10).pack(side=tk.LEFT, padx=2)
                ttk.Button(button_frame, text="保存长图", command=save_long_image, width=12).pack(side=tk.LEFT, padx=2)
                # 数据表格
                table_frame = ttk.Frame(main_frame)
                table_frame.pack(fill=tk.BOTH, expand=True)
                # 创建滚动条
                scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
                scrollbar_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
                # 创建表格
                db_columns = ("ID", "代码", "名称", "类型", "板块", "策略", "大盘", "外围", "仓位%", "止损%", "止盈%", "目标价", "创建时间", "更新时间")
                db_tree = ttk.Treeview(table_frame, columns=db_columns, show="headings",
                                      yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
                # 配置列
                col_widths = {"ID": 50, "代码": 100, "名称": 120, "类型": 60, "板块": 100,
                             "策略": 120, "大盘": 100, "外围": 80, "仓位%": 80, "止损%": 80,
                             "止盈%": 80, "目标价": 100, "创建时间": 150, "更新时间": 150}
                for col in db_columns:
                    db_tree.heading(col, text=col)
                    db_tree.column(col, width=col_widths.get(col, 100))
                scrollbar_y.config(command=db_tree.yview)
                scrollbar_x.config(command=db_tree.xview)
                db_tree.grid(row=0, column=0, sticky="nsew")
                scrollbar_y.grid(row=0, column=1, sticky="ns")
                scrollbar_x.grid(row=1, column=0, sticky="ew")
                table_frame.grid_rowconfigure(0, weight=1)
                table_frame.grid_columnconfigure(0, weight=1)
                def load_data():
                    """加载数据"""
                    # 清空表格
                    for item in db_tree.get_children():
                        db_tree.delete(item)
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT id, stock_code, stock_name, stock_type, sector, strategy,
                                   market_status, peripheral_sentiment, position, stop_loss,
                                   take_profit, target_price, created_at, updated_at
                            FROM trading_system_configs
                            ORDER BY updated_at DESC
                        ''')
                        records = cursor.fetchall()
                        conn.close()
                        for record in records:
                            db_tree.insert("", tk.END, values=record)
                    except Exception as e:
                        messagebox.showerror("错误", f"加载数据失败: {e}")
                # 初始加载
                load_data()
            ttk.Button(save_load_frame, text="DB显示", command=lambda: show_db_table_window(win), width=12).pack(side=tk.LEFT)
            # 打开时自动加载前10条数据
            load_from_db()
            # 股票列表
            stock_list_frame = ttk.Frame(left_bottom)
            stock_list_frame.pack(fill=tk.BOTH, expand=True)
            # 创建表格显示股票
            columns = ("代码", "名称", "类型", "板块", "策略", "仓位%", "止损%", "止盈%", "目标价")
            stock_tree = ttk.Treeview(stock_list_frame, columns=columns, show="headings", height=10)
            column_widths = {"代码": 100, "名称": 120, "类型": 60, "板块": 100, "策略": 150, "仓位%": 80, "止损%": 80, "止盈%": 80, "目标价": 100}
            for col in columns:
                stock_tree.heading(col, text=col)
                stock_tree.column(col, width=column_widths.get(col, 100))
            stock_tree.pack(fill=tk.BOTH, expand=True)
            # 绑定选择事件
            def on_stock_select(event):
                selection = stock_tree.selection()
                if selection:
                    item = stock_tree.item(selection[0])
                    stock_code = item['values'][0]
                    show_stock_config(stock_code)
            stock_tree.bind("<<TreeviewSelect>>", on_stock_select)
            def update_stock_list():
                """更新股票列表"""
                # 清空现有项
                for item in stock_tree.get_children():
                    stock_tree.delete(item)
                # 添加股票
                for config in stock_configs.values():
                    stock_tree.insert("", tk.END, values=(
                        config['code'],
                        config['name'],
                        config.get('type', '股票'),
                        config['sector'],
                        config.get('strategy', ''),
                        f"{config['position']:.1f}",
                        f"{config['stop_loss']:.1f}",
                        f"{config['take_profit']:.1f}",
                        f"{config['target_price']:.2f}"
                    ))
            # 右侧:配置建议和编辑
            right_bottom = ttk.LabelFrame(stock_config_frame, text="配置建议与编辑", padding=10)
            right_bottom.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
            # 配置建议显示(使用Notebook支持多个标签页)
            advice_notebook = ttk.Notebook(right_bottom)
            advice_notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            # 基础建议标签页
            basic_advice_tab = ttk.Frame(advice_notebook)
            advice_notebook.add(basic_advice_tab, text="基础建议")
            # AI分析按钮区域
            ai_analyze_btn_frame = ttk.Frame(basic_advice_tab)
            ai_analyze_btn_frame.pack(fill=tk.X, pady=(0, 5))
            advice_text = scrolledtext.ScrolledText(basic_advice_tab, height=15, wrap=tk.WORD,
                                                    font=("TkDefaultFont", 12), state=tk.DISABLED)
            advice_text.pack(fill=tk.BOTH, expand=True)
            # 策略专项建议标签页
            strategy_advice_tab = ttk.Frame(advice_notebook)
            advice_notebook.add(strategy_advice_tab, text="策略专项建议")
            strategy_advice_text = scrolledtext.ScrolledText(strategy_advice_tab, height=15, wrap=tk.WORD,
                                                             font=("TkDefaultFont", 12), state=tk.DISABLED)
            strategy_advice_text.pack(fill=tk.BOTH, expand=True)
            # 策略建议操作按钮
            strategy_advice_btn_frame = ttk.Frame(strategy_advice_tab)
            strategy_advice_btn_frame.pack(fill=tk.X, pady=(5, 0))
            def insert_strategy_advice_to_config():
                """将策略建议插入到配置中"""
                if current_stock_code[0] and current_stock_code[0] in stock_configs:
                    code = current_stock_code[0]
                    config = stock_configs[code]
                    strategy_advice = config.get('strategy_advice', '')
                    if not strategy_advice:
                        messagebox.showwarning("警告", "该股票没有策略专项建议")
                        return
                    # 解析策略建议中的关键数据
                    try:
                        # 尝试从策略建议中提取仓位、止损、止盈、目标价等信息
                        # 这里使用简单的正则表达式提取
                        import re
                        # 提取仓位
                        position_match = re.search(r'仓位[::]\s*(\d+(?:\.\d+)?)%', strategy_advice)
                        if position_match:
                            config['position'] = float(position_match.group(1))
                        # 提取止损
                        stop_loss_match = re.search(r'止损[::]\s*(-?\d+(?:\.\d+)?)%', strategy_advice)
                        if stop_loss_match:
                            config['stop_loss'] = float(stop_loss_match.group(1))
                        # 提取止盈
                        take_profit_match = re.search(r'止盈[::]\s*(\d+(?:\.\d+)?)%', strategy_advice)
                        if take_profit_match:
                            config['take_profit'] = float(take_profit_match.group(1))
                        # 提取目标价
                        target_price_match = re.search(r'目标[价价位][::]\s*(\d+(?:\.\d+)?)', strategy_advice)
                        if target_price_match:
                            config['target_price'] = float(target_price_match.group(1))
                        update_stock_list()
                        show_stock_config(code)  # 刷新显示
                        messagebox.showinfo("成功", "策略建议数据已插入到配置中")
                    except Exception as e:
                        messagebox.showerror("错误", f"解析策略建议失败: {e}")
                else:
                    messagebox.showwarning("警告", "请先选择股票")
            def batch_insert_all_strategy_advice():
                """一键插入所有策略建议到配置"""
                if not strategy_advice_data:
                    messagebox.showwarning("警告", "没有策略建议数据可插入")
                    return
                inserted_count = 0
                for code, advice_data in strategy_advice_data.items():
                    if code in stock_configs:
                        config = stock_configs[code]
                        strategy_advice = advice_data.get('advice', '')
                        if strategy_advice:
                            config['strategy_advice'] = strategy_advice
                            # 解析并插入数据
                            try:
                                import re
                                position_match = re.search(r'仓位[::]\s*(\d+(?:\.\d+)?)%', strategy_advice)
                                if position_match:
                                    config['position'] = float(position_match.group(1))
                                stop_loss_match = re.search(r'止损[::]\s*(-?\d+(?:\.\d+)?)%', strategy_advice)
                                if stop_loss_match:
                                    config['stop_loss'] = float(stop_loss_match.group(1))
                                take_profit_match = re.search(r'止盈[::]\s*(\d+(?:\.\d+)?)%', strategy_advice)
                                if take_profit_match:
                                    config['take_profit'] = float(take_profit_match.group(1))
                                target_price_match = re.search(r'目标[价价位][::]\s*(\d+(?:\.\d+)?)', strategy_advice)
                                if target_price_match:
                                    config['target_price'] = float(target_price_match.group(1))
                                inserted_count += 1
                            except:
                                pass
                update_stock_list()
                messagebox.showinfo("成功", f"已插入 {inserted_count} 条策略建议数据到配置中")
            ttk.Button(strategy_advice_btn_frame, text="插入到配置", command=insert_strategy_advice_to_config, width=15).pack(side=tk.LEFT, padx=5)
            ttk.Button(strategy_advice_btn_frame, text="一键插入全部", command=batch_insert_all_strategy_advice, width=15).pack(side=tk.LEFT, padx=5)
            # 配置编辑区域
            config_edit_frame = ttk.LabelFrame(right_bottom, text="配置参数", padding=10)
            config_edit_frame.pack(fill=tk.X)
            current_stock_code = [None]  # 使用列表以便在嵌套函数中修改
            def show_stock_config(stock_code):
                """显示股票配置"""
                if stock_code not in stock_configs:
                    return
                current_stock_code[0] = stock_code
                config = stock_configs[stock_code]
                # 显示基础建议
                advice_text.config(state=tk.NORMAL)
                advice_text.delete("1.0", tk.END)
                current_advice = config.get('advice', '暂无建议')
                advice_text.insert("1.0", current_advice)
                advice_text.config(state=tk.DISABLED)
                # 更新AI分析按钮(如果当前没有建议或建议太短,显示"AI分析"按钮)
                # 清空按钮区域
                for widget in ai_analyze_btn_frame.winfo_children():
                    widget.destroy()
                # 添加AI分析按钮
                def run_ai_analysis():
                    """对当前股票进行AI分析"""
                    if not current_stock_code[0]:
                        messagebox.showwarning("警告", "请先选择股票")
                        return
                    code = current_stock_code[0]
                    if code not in stock_configs:
                        return
                    stock_config = stock_configs[code]
                    stock_name = stock_config.get('name', code)
                    stock_type = stock_config.get('type', '股票')
                    stock_sector = stock_config.get('sector', '未分类')
                    stock_strategy = stock_config.get('strategy', strategy_var.get())
                    # 在后台线程中执行AI分析
                    def analyze_in_thread():
                        try:
                            # 更新界面显示"分析中..."
                            win.after(0, lambda: [
                                advice_text.config(state=tk.NORMAL),
                                advice_text.delete("1.0", tk.END),
                                advice_text.insert("1.0", "正在AI分析中,请稍候..."),
                                advice_text.config(state=tk.DISABLED)
                            ])
                            # 生成AI分析
                            ai_advice = self._generate_stock_config_advice(
                                code, stock_name, stock_strategy,
                                market_status_var.get(),
                                peripheral_sentiment_var.get(),
                                stock_sector,
                                stock_type
                            )
                            # 保存到配置中
                            stock_configs[code]['advice'] = ai_advice
                            # 更新界面显示结果
                            win.after(0, lambda: [
                                advice_text.config(state=tk.NORMAL),
                                advice_text.delete("1.0", tk.END),
                                advice_text.insert("1.0", ai_advice),
                                advice_text.config(state=tk.DISABLED),
                                show_stock_config(code)  # 刷新显示,更新配置参数
                            ])
                        except Exception as e:
                            error_msg = f"AI分析失败: {e!s}"
                            win.after(0, lambda: [
                                advice_text.config(state=tk.NORMAL),
                                advice_text.delete("1.0", tk.END),
                                advice_text.insert("1.0", error_msg),
                                advice_text.config(state=tk.DISABLED)
                            ])
                    # 启动分析线程
                    threading.Thread(target=analyze_in_thread, daemon=True).start()
                # 如果当前没有建议或建议太短,显示"AI分析"按钮
                if not current_advice or current_advice == '暂无建议' or len(current_advice) < 100:
                    ttk.Button(ai_analyze_btn_frame, text="AI分析", command=run_ai_analysis, width=12).pack(side=tk.LEFT, padx=5)
                else:
                    # 如果有建议,显示"重新分析"按钮
                    ttk.Button(ai_analyze_btn_frame, text="重新AI分析", command=run_ai_analysis, width=12).pack(side=tk.LEFT, padx=5)
                # 显示策略专项建议
                strategy_advice_text.config(state=tk.NORMAL)
                strategy_advice_text.delete("1.0", tk.END)
                strategy_advice = config.get('strategy_advice', '')
                if strategy_advice:
                    strategy_advice_text.insert("1.0", strategy_advice)
                else:
                    strategy_advice_text.insert("1.0", "暂无策略专项建议\n\n提示:在批量分析时勾选【使用特定策略进行分析】可生成策略专项建议")
                strategy_advice_text.config(state=tk.DISABLED)
                # 更新编辑区域
                for widget in config_edit_frame.winfo_children():
                    widget.destroy()
                # 解析AI建议中的配置参数
                def parse_ai_config_params(advice_text):
                    """从AI建议文本中解析配置参数"""
                    import re
                    params = {
                        'position': None,
                        'stop_loss': None,
                        'take_profit': None,
                        'target_price': None
                    }
                    # 提取仓位
                    position_match = re.search(r'仓位[::]\s*(\d+(?:\.\d+)?)%', advice_text)
                    if position_match:
                        params['position'] = float(position_match.group(1))
                    # 提取止损
                    stop_loss_match = re.search(r'止损[::]\s*(-?\d+(?:\.\d+)?)%', advice_text)
                    if stop_loss_match:
                        params['stop_loss'] = float(stop_loss_match.group(1))
                    # 提取止盈
                    take_profit_match = re.search(r'止盈[::]\s*(\d+(?:\.\d+)?)%', advice_text)
                    if take_profit_match:
                        params['take_profit'] = float(take_profit_match.group(1))
                    # 提取目标价
                    target_price_match = re.search(r'目标[价价位][::]\s*(\d+(?:\.\d+)?)', advice_text)
                    if target_price_match:
                        params['target_price'] = float(target_price_match.group(1))
                    return params
                # 从基础建议和策略建议中解析AI配置参数
                basic_advice = config.get('advice', '')
                strategy_advice = config.get('strategy_advice', '')
                ai_params = {}
                # 优先从策略建议中提取
                if strategy_advice:
                    ai_params = parse_ai_config_params(strategy_advice)
                # 如果策略建议中没有,从基础建议中提取
                if not any(ai_params.values()) and basic_advice:
                    ai_params = parse_ai_config_params(basic_advice)
                # 显示AI建议的配置参数(如果有)
                if any(ai_params.values()):
                    ai_info_label = ttk.Label(config_edit_frame,
                                             text="AI分析指导的配置参数:",
                                             font=("TkDefaultFont", 11, "bold"),
                                             foreground="blue")
                    ai_info_label.pack(anchor=tk.W, pady=(0, 5))
                    ai_params_frame = ttk.Frame(config_edit_frame)
                    ai_params_frame.pack(fill=tk.X, pady=(0, 10))
                    ai_params_text = []
                    if ai_params.get('position') is not None:
                        ai_params_text.append(f"仓位: {ai_params['position']:.1f}%")
                    if ai_params.get('stop_loss') is not None:
                        ai_params_text.append(f"止损: {ai_params['stop_loss']:.1f}%")
                    if ai_params.get('take_profit') is not None:
                        ai_params_text.append(f"止盈: {ai_params['take_profit']:.1f}%")
                    if ai_params.get('target_price') is not None:
                        ai_params_text.append(f"目标价: {ai_params['target_price']:.2f}")
                    if ai_params_text:
                        ttk.Label(ai_params_frame, text=" | ".join(ai_params_text),
                                 font=("TkDefaultFont", 11), foreground="green").pack(anchor=tk.W)
                # 分隔线
                separator = ttk.Separator(config_edit_frame, orient=tk.HORIZONTAL)
                separator.pack(fill=tk.X, pady=5)
                # 当前配置参数标题
                current_config_label = ttk.Label(config_edit_frame,
                                                 text="当前配置参数:",
                                                 font=("TkDefaultFont", 11, "bold"))
                current_config_label.pack(anchor=tk.W, pady=(5, 5))
                # 仓位
                row1 = ttk.Frame(config_edit_frame)
                row1.pack(fill=tk.X, pady=2)
                ttk.Label(row1, text="仓位(%):", width=12).pack(side=tk.LEFT)
                # 如果有AI建议,优先使用AI建议的值
                position_value = ai_params.get('position') if ai_params.get('position') is not None else config['position']
                position_var = tk.StringVar(value=str(position_value))
                position_entry = ttk.Entry(row1, textvariable=position_var, width=15)
                position_entry.pack(side=tk.LEFT, padx=(0, 10))
                if ai_params.get('position') is not None:
                    ttk.Label(row1, text=f"(AI建议: {ai_params['position']:.1f}%)",
                             font=("TkDefaultFont", 8), foreground="green").pack(side=tk.LEFT)
                # 止损
                ttk.Label(row1, text="止损(%):", width=12).pack(side=tk.LEFT)
                stop_loss_value = ai_params.get('stop_loss') if ai_params.get('stop_loss') is not None else config['stop_loss']
                stop_loss_var = tk.StringVar(value=str(stop_loss_value))
                stop_loss_entry = ttk.Entry(row1, textvariable=stop_loss_var, width=15)
                stop_loss_entry.pack(side=tk.LEFT)
                if ai_params.get('stop_loss') is not None:
                    ttk.Label(row1, text=f"(AI建议: {ai_params['stop_loss']:.1f}%)",
                             font=("TkDefaultFont", 8), foreground="green").pack(side=tk.LEFT)
                # 止盈
                row2 = ttk.Frame(config_edit_frame)
                row2.pack(fill=tk.X, pady=2)
                ttk.Label(row2, text="止盈(%):", width=12).pack(side=tk.LEFT)
                take_profit_value = ai_params.get('take_profit') if ai_params.get('take_profit') is not None else config['take_profit']
                take_profit_var = tk.StringVar(value=str(take_profit_value))
                take_profit_entry = ttk.Entry(row2, textvariable=take_profit_var, width=15)
                take_profit_entry.pack(side=tk.LEFT, padx=(0, 10))
                if ai_params.get('take_profit') is not None:
                    ttk.Label(row2, text=f"(AI建议: {ai_params['take_profit']:.1f}%)",
                             font=("TkDefaultFont", 8), foreground="green").pack(side=tk.LEFT)
                # 目标价
                ttk.Label(row2, text="目标价:", width=12).pack(side=tk.LEFT)
                target_price_value = ai_params.get('target_price') if ai_params.get('target_price') is not None else config['target_price']
                target_price_var = tk.StringVar(value=str(target_price_value))
                target_price_entry = ttk.Entry(row2, textvariable=target_price_var, width=15)
                target_price_entry.pack(side=tk.LEFT)
                if ai_params.get('target_price') is not None:
                    ttk.Label(row2, text=f"(AI建议: {ai_params['target_price']:.2f})",
                             font=("TkDefaultFont", 8), foreground="green").pack(side=tk.LEFT)
                # 保存按钮
                def save_config():
                    try:
                        config['position'] = float(position_var.get() or 0)
                        config['stop_loss'] = float(stop_loss_var.get() or 0)
                        config['take_profit'] = float(take_profit_var.get() or 0)
                        config['target_price'] = float(target_price_var.get() or 0)
                        update_stock_list()
                        messagebox.showinfo("成功", "配置已保存")
                    except ValueError:
                        messagebox.showerror("错误", "请输入有效的数字")
                ttk.Button(config_edit_frame, text="保存配置", command=save_config, width=15).pack(pady=5)
                # 删除按钮
                def delete_stock():
                    if messagebox.askyesno("确认", f"确定要删除 {config['name']} 吗?"):
                        del stock_configs[stock_code]
                        update_stock_list()
                        advice_text.config(state=tk.NORMAL)
                        advice_text.delete("1.0", tk.END)
                        advice_text.config(state=tk.DISABLED)
                        for widget in config_edit_frame.winfo_children():
                            widget.destroy()
                ttk.Button(config_edit_frame, text="删除股票", command=delete_stock, width=15).pack()
        except Exception as e:
            messagebox.showerror("错误", f"打开交易体系界面失败: {e}")
            import traceback
            traceback.print_exc()

    def _generate_strategy_specific_advice(self, stock_code, stock_name, strategy,
                                          market_status, peripheral_sentiment, sector, stock_type="股票"):
        """生成策略专项建议(包含买进卖出、仓位管理、止盈止损)"""
        try:
            prompt = f"""请根据以下{stock_type}和选择的交易策略,提供详细的交易建议:
{stock_type}信息:
- 代码:{stock_code}
- 名称:{stock_name}
- 类型:{stock_type}
- 板块:{sector or '未分类'}
市场环境:
- 大盘情况:{market_status}
- 外围情绪:{peripheral_sentiment}分
选择的交易策略:{strategy}
请严格按照该策略的特点,提供以下方面的详细建议:
1. **买进建议**:
   - 是否适合买进(明确回答:适合/不适合)
   - 买进时机(具体价位或技术条件)
   - 买进方式(一次性/分批建仓,具体比例)
2. **卖出建议**:
   - 卖出时机(目标价位或技术条件)
   - 卖出方式(一次性/分批卖出,具体比例)
   - 止盈策略
3. **仓位管理**:
   - 建议仓位比例(具体百分比)
   - 仓位调整策略(何时加仓/减仓)
   - 风险控制措施
4. **止盈止损**:
   - 止损价位(具体价格或百分比)
   - 止盈价位(具体价格或百分比)
   - 动态调整规则
5. **策略执行要点**:
   - 该策略下的关键操作要点
   - 需要特别注意的事项
   - 与其他策略的配合建议
请提供详细、具体、可执行的建议,格式清晰易读。"""
            system_prompt = f"""你是一位精通{strategy}的交易专家。你能够根据该策略的核心原理和特点,为股票提供专业的买进卖出、仓位管理、止盈止损建议。
你的建议必须严格遵循{strategy}的原则和方法,不能偏离策略核心思想。"""
            ai_result = self.call_ai_model(prompt, system_prompt)
            if not ai_result:
                return f"""策略专项建议:{stock_name} ({stock_code})
策略:{strategy}
【买进建议】
待AI分析
【卖出建议】
待AI分析
【仓位管理】
待AI分析
【止盈止损】
待AI分析
注:AI分析暂时不可用,请检查AI配置。"""
            return ai_result
        except Exception as e:
            return f"生成策略专项建议失败: {e!s}"

    def _paste_stocks(self, text_widget, parent_window):
        """粘贴股票"""
        try:
            clipboard_text = parent_window.clipboard_get()
            text_widget.delete("1.0", tk.END)
            text_widget.insert("1.0", clipboard_text)
        except:
            messagebox.showwarning("警告", "剪贴板为空或无法获取", parent=parent_window)

    def _attach_window_controls(self, win, button_container=None):
        """给窗口添加常用控制按钮(最小化/最大化/关闭)"""
        frame = button_container or ttk.Frame(win)
        if not button_container:
            frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        win._is_maximized = False
        win._last_geometry = win.geometry()
        def minimize():
            try:
                # 确保窗口可以最小化
                win.state('normal')  # 先确保窗口是正常状态
                win.iconify()  # 最小化窗口
            except Exception as e:
                print(f"最小化窗口失败: {e}")
                # 如果iconify失败,尝试使用withdraw
                try:
                    win.withdraw()
                except Exception as e2:
                    print(f"withdraw也失败: {e2}")
        def toggle_maximize():
            try:
                if win._is_maximized:
                    win.state("normal")
                    if win._last_geometry:
                        win.geometry(win._last_geometry)
                    win._is_maximized = False
                    max_btn.config(text="最大化")
                else:
                    win._last_geometry = win.geometry()
                    win.state("zoomed")
                    win._is_maximized = True
                    max_btn.config(text="还原")
            except Exception:
                if win._is_maximized:
                    if win._last_geometry:
                        win.geometry(win._last_geometry)
                    win._is_maximized = False
                    max_btn.config(text="最大化")
                else:
                    win._last_geometry = win.geometry()
                    screen_width = win.winfo_screenwidth()
                    screen_height = win.winfo_screenheight()
                    win.geometry(f"{screen_width}x{screen_height}+0+0")
                    win._is_maximized = True
                    max_btn.config(text="还原")
        ttk.Button(frame, text="最小化", width=10, command=minimize).pack(side=tk.RIGHT, padx=3)
        max_btn = ttk.Button(frame, text="最大化", width=10, command=toggle_maximize)
        max_btn.pack(side=tk.RIGHT, padx=3)
        ttk.Button(frame, text="关闭", width=10, command=win.destroy).pack(side=tk.RIGHT, padx=3)

    def _copy_result(self, result_text):
        """复制结果"""
        try:
            content = result_text.get("1.0", tk.END).strip()
            if content:
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                messagebox.showinfo("成功", "结果已复制到剪贴板")
            else:
                messagebox.showinfo("提示", "没有可复制的内容")
        except Exception as e:
            messagebox.showerror("错误", f"复制失败: {e}")

    def _add_to_consultation(self, result_text):
        """将分析结果添加到咨询标签页"""
        try:
            content = result_text.get("1.0", tk.END).strip()
            if not content:
                messagebox.showwarning("提示", "没有可添加的内容")
                return
            # 生成标签页名称:咨询+时间
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tab_name = f"咨询{current_time}"
            # 创建新标签页
            tab_id = self.create_text_tab(tab_name)
            # 获取新创建的文本框
            text_widget = self.text_widgets[tab_id]['widget']
            # 添加内容,包含标题和时间戳
            initial_content = "【咨询分析】\n"
            initial_content += f"时间:{current_time}\n"
            initial_content += "="*50 + "\n\n"
            initial_content += content + "\n"
            text_widget.insert("1.0", initial_content)
            messagebox.showinfo("成功", "分析结果已添加到咨询标签页")
        except Exception as e:
            messagebox.showerror("错误", f"添加到咨询失败: {e}")
            import traceback
            traceback.print_exc()

    def load_crawler_config(self):
        """加载爬取按钮配置(打包后优先 D:\\StockAnalyzer,其次 exe 同目录)"""
        default_config = [
            {"key": "taoguba", "name": "爬取淘股吧", "url": "https://www.taoguba.com.cn/", "bg_color": "#FF6B6B", "fg_color": "white", "command": "crawl_taoguba_direct", "sort_order": 1},
            {"key": "jiuyan", "name": "爬取韭研", "url": "https://www.jiuyangongshe.com/", "bg_color": "#FFA500", "fg_color": "white", "command": "run_crawler_script:jiuyan", "sort_order": 2},
            {"key": "eastmoney", "name": "爬取东方财富", "url": "https://www.eastmoney.com/", "bg_color": "#FFD700", "fg_color": "black", "command": "crawl_eastmoney_web", "sort_order": 3},
            {"key": "xueqiu", "name": "爬取雪球", "url": "https://xueqiu.com/", "bg_color": "#32CD32", "fg_color": "white", "command": "crawl_xueqiu_web", "sort_order": 4},
            {"key": "xuangubao", "name": "爬取选股宝", "url": "https://xuangubao.cn/", "bg_color": "#00CED1", "fg_color": "white", "command": "crawl_xuangubao_web", "sort_order": 5},
            {"key": "ths", "name": "爬取同花顺", "url": "https://www.10jqka.com.cn/", "bg_color": "#4169E1", "fg_color": "white", "command": "crawl_ths_web", "sort_order": 6}
        ]
        config_path = _resolve_crawler_config_path()
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    if isinstance(user_config, list) and len(user_config) > 0:
                        # 验证并清理配置
                        sanitized = []
                        for item in user_config:
                            if not isinstance(item, dict):
                                continue
                            key = str(item.get("key", "")).strip()
                            name = str(item.get("name", "")).strip()
                            url = str(item.get("url", "")).strip()
                            if not key or not name or not url:
                                continue
                            entry = {"key": key, "name": name, "url": url}
                            # 保留其他字段
                            for field in ["bg_color", "fg_color", "command", "sort_order"]:
                                if field in item:
                                    entry[field] = item[field]
                            # 如果没有排序字段,设置一个
                            if "sort_order" not in entry:
                                entry["sort_order"] = len(sanitized) + 1
                            sanitized.append(entry)
                        if sanitized:
                            return sanitized
        except Exception as e:
            print(f"加载爬取按钮配置失败: {e}")
        return default_config

    def save_crawler_config(self):
        """保存爬取按钮配置(打包后写入 D:\\StockAnalyzer 或 exe 同目录)"""
        config_path = _resolve_crawler_config_path()
        try:
            if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
                parent = os.path.dirname(config_path)
                if parent and parent != os.path.dirname(sys.executable):
                    os.makedirs(parent, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.crawler_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存爬取按钮配置失败: {e}")

    def show_crawler_editor(self):
        """显示爬取按钮编辑窗口"""
        try:
            if hasattr(self, '_crawler_editor_window') and self._crawler_editor_window and self._crawler_editor_window.winfo_exists():
                self._crawler_editor_window.lift()
                self._crawler_editor_window.focus_force()
                return
        except Exception:
            self._crawler_editor_window = None
        win = self._safe_toplevel(self.root)
        win.title("编辑爬取按钮")
        win.geometry("800x600")
        win.transient(self.root)
        self._crawler_editor_window = win
        # 创建表格
        columns = ("name", "url", "bg_color", "fg_color", "command")
        headings = ("名称", "URL", "背景色", "文字色", "命令")
        tree_frame = ttk.Frame(win, padding=10)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        for col, heading in zip(columns, headings):
            width = 150 if col == "url" else 120 if col == "command" else 100
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor=tk.W)
        # 编辑表单
        form_frame = ttk.LabelFrame(win, text="编辑", padding=10)
        form_frame.pack(fill=tk.X, padx=10, pady=10)
        name_var = tk.StringVar()
        url_var = tk.StringVar()
        bg_color_var = tk.StringVar()
        fg_color_var = tk.StringVar()
        command_var = tk.StringVar()
        ttk.Label(form_frame, text="名称:").grid(row=0, column=0, sticky="e", pady=5)
        ttk.Entry(form_frame, textvariable=name_var, width=30).grid(row=0, column=1, sticky="w", pady=5, padx=(5, 0))
        ttk.Label(form_frame, text="URL:").grid(row=1, column=0, sticky="e", pady=5)
        ttk.Entry(form_frame, textvariable=url_var, width=50).grid(row=1, column=1, sticky="w", pady=5, padx=(5, 0))
        # 颜色选择
        color_frame = ttk.Frame(form_frame)
        color_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        ttk.Label(color_frame, text="背景色:").pack(side=tk.LEFT, padx=(0, 5))
        bg_color_entry = ttk.Entry(color_frame, textvariable=bg_color_var, width=15)
        bg_color_entry.pack(side=tk.LEFT, padx=(0, 10))
        def choose_bg_color():
            color = self._choose_color(bg_color_var.get() or "lightgray")
            if color:
                bg_color_var.set(color)
        ttk.Button(color_frame, text="选择", command=choose_bg_color, width=8).pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(color_frame, text="文字色:").pack(side=tk.LEFT, padx=(0, 5))
        fg_color_entry = ttk.Entry(color_frame, textvariable=fg_color_var, width=15)
        fg_color_entry.pack(side=tk.LEFT, padx=(0, 10))
        def choose_fg_color():
            color = self._choose_color(fg_color_var.get() or "black")
            if color:
                fg_color_var.set(color)
        ttk.Button(color_frame, text="选择", command=choose_fg_color, width=8).pack(side=tk.LEFT, padx=(0, 20))
        # 颜色预览
        color_preview = tk.Label(color_frame, text="预览", width=10, relief=tk.SUNKEN)
        color_preview.pack(side=tk.LEFT, padx=(20, 0))
        def update_color_preview(*args):
            bg = bg_color_var.get() or "lightgray"
            fg = fg_color_var.get() or "black"
            try:
                color_preview.config(bg=bg, fg=fg)
            except:
                pass
        bg_color_var.trace("w", update_color_preview)
        fg_color_var.trace("w", update_color_preview)
        update_color_preview()
        # 命令选择
        ttk.Label(form_frame, text="命令:").grid(row=3, column=0, sticky="e", pady=5)
        command_combo = ttk.Combobox(form_frame, textvariable=command_var, width=30, state="readonly")
        command_combo['values'] = (
            "crawl_taoguba_direct",
            "crawl_eastmoney_web",
            "crawl_xueqiu_web",
            "crawl_xuangubao_web",
            "crawl_ths_web",
            "run_crawler_script:jiuyan"
        )
        command_combo.grid(row=3, column=1, sticky="w", pady=5, padx=(5, 0))
        def refresh_tree():
            tree.delete(*tree.get_children())
            sorted_config = sorted(self.crawler_config, key=lambda x: x.get("sort_order", 999))
            for item in sorted_config:
                values = (
                    item.get("name", ""),
                    item.get("url", ""),
                    item.get("bg_color", ""),
                    item.get("fg_color", ""),
                    item.get("command", "")
                )
                tree.insert("", tk.END, values=values, tags=(item.get("key", ""),))
        def clear_form():
            name_var.set("")
            url_var.set("")
            bg_color_var.set("")
            fg_color_var.set("")
            command_var.set("")
        def get_selected_key():
            selection = tree.selection()
            if not selection:
                return None
            tags = tree.item(selection[0])['tags']
            return tags[0] if tags else None
        def on_tree_select(event):
            key = get_selected_key()
            if key:
                item = next((x for x in self.crawler_config if x.get("key") == key), None)
                if item:
                    name_var.set(item.get("name", ""))
                    url_var.set(item.get("url", ""))
                    bg_color_var.set(item.get("bg_color", ""))
                    fg_color_var.set(item.get("fg_color", ""))
                    command_var.set(item.get("command", ""))
        tree.bind("<<TreeviewSelect>>", on_tree_select)
        def add_entry():
            name = name_var.get().strip()
            url = url_var.get().strip()
            if not name or not url:
                messagebox.showwarning("提示", "请填写名称和URL")
                return
            # 生成唯一的key
            key = name.lower().replace("爬取", "").replace(" ", "_")
            # 确保key唯一
            existing_keys = {item.get("key") for item in self.crawler_config}
            counter = 1
            original_key = key
            while key in existing_keys:
                key = f"{original_key}_{counter}"
                counter += 1
            entry = {
                "key": key,
                "name": name,
                "url": url,
                "bg_color": bg_color_var.get().strip() or "lightgray",
                "fg_color": fg_color_var.get().strip() or "black",
                "command": command_var.get().strip() or "",
                "sort_order": len(self.crawler_config) + 1
            }
            self.crawler_config.append(entry)
            self.save_crawler_config()
            if hasattr(self, 'crawler_row1') and hasattr(self, 'crawler_row2'):
                self._build_crawler_buttons(self.crawler_row1, self.crawler_row2)
            refresh_tree()
            clear_form()
        def update_entry():
            key = get_selected_key()
            if not key:
                messagebox.showwarning("提示", "请选择需要修改的项")
                return
            item = next((x for x in self.crawler_config if x.get("key") == key), None)
            if not item:
                return
            name = name_var.get().strip()
            url = url_var.get().strip()
            if not name or not url:
                messagebox.showwarning("提示", "请填写名称和URL")
                return
            item["name"] = name
            item["url"] = url
            item["bg_color"] = bg_color_var.get().strip() or "lightgray"
            item["fg_color"] = fg_color_var.get().strip() or "black"
            item["command"] = command_var.get().strip() or ""
            self.save_crawler_config()
            if hasattr(self, 'crawler_row1') and hasattr(self, 'crawler_row2'):
                self._build_crawler_buttons(self.crawler_row1, self.crawler_row2)
            refresh_tree()
        def delete_entry():
            key = get_selected_key()
            if not key:
                messagebox.showwarning("提示", "请选择需要删除的项")
                return
            if messagebox.askyesno("确认", "确定要删除该按钮吗?"):
                self.crawler_config = [x for x in self.crawler_config if x.get("key") != key]
                self.save_crawler_config()
                if hasattr(self, 'crawler_row1') and hasattr(self, 'crawler_row2'):
                    self._build_crawler_buttons(self.crawler_row1, self.crawler_row2)
                refresh_tree()
                clear_form()
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(button_frame, text="新增", width=10, command=add_entry).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_frame, text="更新", width=10, command=update_entry).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_frame, text="删除", width=10, command=delete_entry).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_frame, text="清空", width=10, command=clear_form).pack(side=tk.LEFT, padx=4)
        refresh_tree()

    def _open_market_link(self, url):
        """在浏览器中打开链接"""
        if not url:
            return
        try:
            webbrowser.open_new(url)
        except Exception as exc:
            messagebox.showerror("错误", f"无法打开链接: {exc}")

    def _open_search_engine(self, base_url, query):
        """根据查询词打开对应搜索引擎"""
        if not base_url:
            return
        query = (query or "").strip()
        # 修复乱码
        query = self._fix_encoding(query)
        url = base_url
        if "{query}" in base_url:
            try:
                from urllib.parse import quote_plus
                encoded = quote_plus(query) if query else ""
                url = base_url.format(query=encoded)
            except Exception:
                url = base_url.format(query=query)
        self._open_market_link(url)
        if query:
            self._add_search_history(query)

    def _add_search_history(self, query):
        """记录最近搜索词并保存到配置文件"""
        if not query:
            return
        query = query.strip()
        if not query:
            return
        if not hasattr(self, "search_history"):
            self.search_history = []
        if query in self.search_history:
            self.search_history.remove(query)
        self.search_history.insert(0, query)
        self.search_history = self.search_history[:100]
        self._refresh_search_history_widget()
        # 保存到配置文件
        if not hasattr(self, "market_nav_config"):
            self.market_nav_config = self.load_market_nav_config()
        if "ai_search_questions" not in self.market_nav_config:
            self.market_nav_config["ai_search_questions"] = []
        questions = self.market_nav_config["ai_search_questions"]
        if query in questions:
            questions.remove(query)
        questions.insert(0, query)
        self.market_nav_config["ai_search_questions"] = questions[:100]  # 最多保存100条
        self.save_market_nav_config()
        # 刷新问题列表显示
        if hasattr(self, "ai_questions_listbox"):
            self._refresh_ai_questions_widget()

    def _refresh_search_history_widget(self):
        """刷新搜索记录显示"""
        if hasattr(self, "search_history_listbox") and self.search_history_listbox:
            self.search_history_listbox.delete(0, tk.END)
            for item in getattr(self, "search_history", []):
                self.search_history_listbox.insert(tk.END, item)

    def _choose_color(self, initial_color="lightgray"):
        """打开颜色选择器"""
        try:
            from tkinter import colorchooser
            color = colorchooser.askcolor(initialcolor=initial_color, title="选择颜色")
            if color and color[1]:
                return color[1]
        except Exception as e:
            print(f"打开颜色选择器失败: {e}")
        return None

    def _update_managed_stock_cache(self):
        names = []
        for entry in self.managed_stocks[-100:]:
            name = entry.get("name")
            if name and name not in names:
                names.append(name)
        self.managed_stock_names = names[-100:]
        self._update_waiting_combo_values()

    def build_stock_management_tab(self, container, as_tab=True):
        """构建股票管理界面,可作为Notebook标签或独立面板"""
        if as_tab:
            stock_tab = ttk.Frame(container, padding=5)
            container.add(stock_tab, text="股票管理")
            parent_frame = stock_tab
        else:
            parent_frame = container
        manage_paned = ttk.PanedWindow(parent_frame, orient=tk.HORIZONTAL)
        manage_paned.pack(fill=tk.BOTH, expand=True)
        left_panel = ttk.Frame(manage_paned, padding=5)
        manage_paned.add(left_panel, weight=2)
        right_panel = ttk.Frame(manage_paned, padding=5)
        manage_paned.add(right_panel, weight=3)
        managed_status_var = tk.StringVar(value="当前管理 0 只股票(最多100)")
        ttk.Label(left_panel, textvariable=managed_status_var, font=("TkDefaultFont", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))
        list_frame = ttk.LabelFrame(left_panel, text="在管股票列表", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True)
        managed_columns = ("名称", "代码", "涨跌幅", "距5日最高", "距5日最低", "来源", "备注", "时间")
        managed_tree = ttk.Treeview(list_frame, columns=managed_columns, show="headings", height=12)
        column_widths = {"名称": 120, "代码": 90, "涨跌幅": 80, "距5日最高": 90, "距5日最低": 90, "来源": 100, "备注": 80, "时间": 140}
        for col in managed_columns:
            managed_tree.heading(col, text=col)
            if col in ["涨跌幅", "距5日最高", "距5日最低", "代码"]:
                managed_tree.column(col, width=column_widths.get(col, 90), anchor=tk.CENTER)
            else:
                managed_tree.column(col, width=column_widths.get(col, 100), anchor=tk.W)
        tree_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=managed_tree.yview)
        managed_tree.configure(yscrollcommand=tree_scrollbar.set)
        managed_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        paste_frame = ttk.LabelFrame(left_panel, text="粘贴文本 / 聊天记录 / 资讯内容", padding=3)
        paste_frame.pack(fill=tk.X, expand=False, pady=(3, 0))
        paste_text = scrolledtext.ScrolledText(paste_frame, height=4, wrap=tk.WORD)
        paste_text.pack(fill=tk.BOTH, expand=True)
        button_frame = ttk.Frame(left_panel)
        button_frame.pack(fill=tk.X, pady=(3, 0))
        detail_header_var = tk.StringVar(value="请选择左侧股票")
        ttk.Label(right_panel, textvariable=detail_header_var, font=("TkDefaultFont", 11, "bold"),
                  foreground="#1f77b4").pack(anchor=tk.W, pady=(0, 3))
        logic_frame = ttk.LabelFrame(right_panel, text="股票逻辑", padding=4)
        logic_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 3))
        logic_status_var = tk.StringVar(value="逻辑:未选择")
        ttk.Label(logic_frame, textvariable=logic_status_var, font=("TkDefaultFont", 11)).pack(anchor=tk.W)
        logic_text = scrolledtext.ScrolledText(logic_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        logic_text.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        detection_frame = ttk.LabelFrame(right_panel, text="技术检测", padding=4)
        detection_frame.pack(fill=tk.BOTH, expand=True)
        detection_status_var = tk.StringVar(value="技术检测:未选择")
        ttk.Label(detection_frame, textvariable=detection_status_var, font=("TkDefaultFont", 11)).pack(anchor=tk.W)
        detection_text = scrolledtext.ScrolledText(detection_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        detection_text.pack(fill=tk.BOTH, expand=True, pady=(2, 2))
        action_frame = ttk.Frame(detection_frame)
        action_frame.pack(fill=tk.X, pady=(0, 0))
        selected_stock_context = {"name": None, "code": None}
        detection_worker = {"thread": None}
        def set_status(message):
            managed_status_var.set(f"{message} | 当前 {len(self.managed_stocks)} 只")
        def sync_managed_history():
            self._update_managed_stock_cache()
        def get_stock_change_pct(stock_code):
            """获取股票实时涨跌幅"""
            if not stock_code or len(stock_code) != 6:
                return "--"
            try:
                # 使用akshare获取实时数据
                try:
                    import akshare as ak
                    spot_data = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
                    stock_data = spot_data[spot_data['代码'] == stock_code]
                    if not stock_data.empty:
                        change_pct = stock_data.iloc[0]['涨跌幅']
                        return f"{change_pct:+.2f}%"
                except ImportError:
                    pass
            except Exception:
                pass
            return "--"
        def get_5day_high_low_data(stock_code, current_price=None):
            """获取股票最近5天的最高价和最低价
            Args:
                stock_code: 股票代码
                current_price: 当前实时价格(如果提供,则使用实时价格;否则使用最新收盘价)
            Returns:
                (current_price, max_high, min_low) 或 (None, None, None)
            """
            if not stock_code or len(stock_code) != 6:
                return None, None, None
            try:
                import akshare as ak
                # 获取最近5天的历史数据
                hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                if hist_data.empty or len(hist_data) < 5:
                    return None, None, None
                # 取最近5天数据
                recent_5days = hist_data.tail(5)
                # 获取最高价和最低价
                high_prices = recent_5days['最高'].values
                low_prices = recent_5days['最低'].values
                max_high = float(max(high_prices))
                min_low = float(min(low_prices))
                # 如果提供了实时价格,使用实时价格;否则使用最新收盘价
                if current_price is not None:
                    price = float(current_price)
                else:
                    price = float(recent_5days.iloc[-1]['收盘'])
                return price, max_high, min_low
            except Exception as e:
                print(f"获取{stock_code}的5天高低点数据失败: {e}")
                return None, None, None
        def refresh_managed_tree_thread():
            """在后台线程中刷新自选股列表,包含实时涨跌幅和5天高低点涨跌幅(使用Tushare)"""
            def update_ui():
                set_status("正在更新涨跌幅和5天高低点数据(使用Tushare)...")
            parent_frame.after(0, update_ui)
            # 批量获取涨跌幅数据
            stock_codes = [entry.get("code", "") for entry in self.managed_stocks[-100:] if entry.get("code")]
            change_pct_dict = {}
            high_low_dict = {}  # {code: (current_price, max_high, min_low)}
            if stock_codes:
                try:
                    # 使用Tushare获取实时数据
                    if not TS_AVAILABLE:
                        def show_error():
                            set_status("错误: Tushare未安装,请先安装: pip install tushare")
                        parent_frame.after(0, show_error)
                        return
                    # 确保Tushare客户端已初始化
                    try:
                        client = self._ensure_tushare_client()
                    except Exception as e:
                        def show_error(e=e):
                            set_status(f"错误: Tushare初始化失败: {e}")
                        parent_frame.after(0, show_error)
                        return
                    # 获取今日日期
                    today = datetime.now().strftime("%Y%m%d")
                    # 批量获取今日行情数据
                    ts_codes = []
                    code_mapping = {}  # {ts_code: original_code}
                    for code in stock_codes:
                        if code and len(code) == 6:
                            ts_code = self._format_ts_code(code)
                            ts_codes.append(ts_code)
                            code_mapping[ts_code] = code
                    if ts_codes:
                        # 分批获取(tushare可能有单次请求限制)
                        batch_size = 50
                        for i in range(0, len(ts_codes), batch_size):
                            batch_codes = ts_codes[i:i+batch_size]
                            try:
                                # 获取今日行情数据
                                df_daily = client.daily(trade_date=today, ts_code=",".join(batch_codes))
                                if df_daily is not None and not df_daily.empty:
                                    for _, row in df_daily.iterrows():
                                        ts_code = row['ts_code']
                                        original_code = code_mapping.get(ts_code)
                                        if original_code:
                                            # 获取涨跌幅
                                            pct_chg = row.get('pct_chg', 0)  # 涨跌幅百分比
                                            change_pct_dict[original_code] = float(pct_chg)
                                            # 获取当前价格(收盘价,如果是实时数据则用最新价)
                                            current_price = row.get('close', 0)
                                            if current_price:
                                                current_price = float(current_price)
                                                # 获取5天高低点数据(使用当前价格)
                                                price, max_high, min_low = get_5day_high_low_data(original_code, current_price)
                                                if price is not None and max_high is not None and min_low is not None:
                                                    high_low_dict[original_code] = (price, max_high, min_low)
                            except Exception as e:
                                print(f"获取Tushare数据批次失败: {e}")
                                # 如果批量获取失败,尝试单个获取
                                for ts_code in batch_codes:
                                    original_code = code_mapping.get(ts_code)
                                    if original_code:
                                        try:
                                            df_single = client.daily(trade_date=today, ts_code=ts_code)
                                            if df_single is not None and not df_single.empty:
                                                row = df_single.iloc[0]
                                                pct_chg = row.get('pct_chg', 0)
                                                change_pct_dict[original_code] = float(pct_chg)
                                                current_price = row.get('close', 0)
                                                if current_price:
                                                    current_price = float(current_price)
                                                    price, max_high, min_low = get_5day_high_low_data(original_code, current_price)
                                                    if price is not None and max_high is not None and min_low is not None:
                                                        high_low_dict[original_code] = (price, max_high, min_low)
                                        except Exception as e2:
                                            print(f"获取{original_code}数据失败: {e2}")
                except Exception as e:
                    print(f"批量获取Tushare数据失败: {e}")
                    import traceback
                    traceback.print_exc()
                    def show_error(e=e):
                        set_status(f"获取数据失败: {str(e)[:50]}")
                    parent_frame.after(0, show_error)
            # 在主线程中更新UI
            def update_tree():
                managed_tree.delete(*managed_tree.get_children())
                # 插入数据
                for entry in reversed(self.managed_stocks[-100:]):
                    code = entry.get("code", "") or ""
                    # 当前涨跌幅
                    if code in change_pct_dict:
                        change_pct = change_pct_dict[code]
                        change_pct_str = f"{change_pct:+.2f}%"
                    else:
                        change_pct_str = "--"
                    # 距5日最高点涨跌幅
                    if code in high_low_dict:
                        current_price, max_high, min_low = high_low_dict[code]
                        # 计算当前价格相对于最高点的涨跌幅
                        high_change_pct = ((current_price - max_high) / max_high) * 100
                        high_change_str = f"{high_change_pct:+.2f}%"
                        # 计算当前价格相对于最低点的涨跌幅
                        low_change_pct = ((current_price - min_low) / min_low) * 100
                        low_change_str = f"{low_change_pct:+.2f}%"
                    else:
                        high_change_str = "--"
                        low_change_str = "--"
                    item_id = managed_tree.insert(
                        "",
                        tk.END,
                        values=(
                            entry.get("name", ""),
                            code,
                            change_pct_str,
                            high_change_str,
                            low_change_str,
                            entry.get("source", ""),
                            entry.get("remark", ""),  # 备注字段
                            entry.get("added_at", "")
                        )
                    )
                    # 根据涨跌幅设置标签颜色(红色下跌,绿色上涨)
                    if code in change_pct_dict:
                        change_pct = change_pct_dict[code]
                        if change_pct > 0:
                            managed_tree.set(item_id, "涨跌幅", f"+{change_pct:.2f}%")
                        elif change_pct < 0:
                            managed_tree.set(item_id, "涨跌幅", f"{change_pct:.2f}%")
                set_status(f"管理列表已更新 | 共{len(self.managed_stocks)}只股票")
            parent_frame.after(0, update_tree)
        def refresh_managed_tree():
            """刷新自选股列表(同步版本,用于初始加载)"""
            refresh_managed_tree_thread()
        def resolve_stock_identity(name_or_code, explicit_code=None):
            if not name_or_code:
                return None, None
            candidate = name_or_code.strip()
            load_stock_names()
            code = explicit_code.strip() if explicit_code else None
            name = candidate
            if code and len(code) == 6 and code.isdigit():
                name = STOCK_CODES_DICT.get(code, name)
            else:
                if candidate.isdigit() and len(candidate) == 6:
                    code = candidate
                    name = STOCK_CODES_DICT.get(code, name)
                else:
                    code = get_stock_code_by_name(candidate)
                    if code and STOCK_CODES_DICT:
                        name = STOCK_CODES_DICT.get(code, name)
            return name, code
        def add_managed_stock_entry(name_or_code, source="手动添加", code_hint=None, remark=""):
            name, code = resolve_stock_identity(name_or_code, code_hint)
            if not name:
                return False
            added_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            updated = False
            for entry in self.managed_stocks:
                if entry.get("name") == name or (code and entry.get("code") == code):
                    entry.update({
                        "name": name,
                        "code": code or entry.get("code"),
                        "source": source,
                        "added_at": added_at,
                        "remark": remark  # 更新备注
                    })
                    updated = True
                    break
            if not updated:
                self.managed_stocks.append({
                    "name": name,
                    "code": code or "",
                    "source": source,
                    "added_at": added_at,
                    "remark": remark  # 添加备注
                })
                if len(self.managed_stocks) > 100:
                    self.managed_stocks = self.managed_stocks[-100:]
            sync_managed_history()
            refresh_managed_tree()
            self._save_managed_stocks_to_file()
            return True
        def extract_names_from_text(text):
            import re
            tokens = re.findall(r'\d{6}|[\u4e00-\u9fa5]{2,6}', text or "")
            if not tokens:
                return []
            load_stock_names()
            valid_tokens = []
            for token in tokens:
                candidate = token.strip()
                if not candidate:
                    continue
                if candidate.isdigit() and len(candidate) == 6:
                    if candidate in STOCK_CODES_DICT:
                        valid_tokens.append(candidate)
                else:
                    if candidate in STOCK_NAME_TO_CODE:
                        valid_tokens.append(candidate)
            return valid_tokens
        def add_from_text():
            raw = paste_text.get("1.0", tk.END).strip()
            if not raw:
                messagebox.showwarning("提示", "请先粘贴包含股票的文本")
                return
            tokens = extract_names_from_text(raw)
            if not tokens:
                messagebox.showwarning("提示", "未解析到疑似股票名称或代码")
                return
            added = 0
            for token in tokens:
                if add_managed_stock_entry(token, source="文本解析", remark="文本分析"):
                    added += 1
            messagebox.showinfo("完成", f"已解析并加入 {added} 只股票")
        def remove_selected():
            selections = managed_tree.selection()
            if not selections:
                messagebox.showwarning("提示", "请先在列表中选择股票")
                return
            targets = []
            for item_id in selections:
                values = managed_tree.item(item_id)['values']
                if values:
                    targets.append((values[0], values[1]))
            self.managed_stocks = [
                entry for entry in self.managed_stocks
                if (entry.get("name"), entry.get("code") or "") not in targets
            ]
            sync_managed_history()
            refresh_managed_tree()
            logic_text.config(state=tk.NORMAL)
            logic_text.delete("1.0", tk.END)
            logic_text.config(state=tk.DISABLED)
            detection_text.config(state=tk.NORMAL)
            detection_text.delete("1.0", tk.END)
            detection_text.config(state=tk.DISABLED)
            selected_stock_context["name"] = None
            detail_header_var.set("请选择左侧股票")
            logic_status_var.set("逻辑:未选择")
            detection_status_var.set("技术检测:未选择")
            self._save_managed_stocks_to_file()
        def import_from_stock_db():
            def on_stock_selected(stock_name):
                if stock_name and add_managed_stock_entry(stock_name, source="股票数据表"):
                    messagebox.showinfo("成功", f"已加入 {stock_name} 到管理列表")
            self.show_unified_db_display(default_tab="stock", on_stock_double_click=on_stock_selected)
        def batch_import_from_stock_table():
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT DISTINCT stock_name, stock_code
                    FROM stock_data
                    ORDER BY date DESC
                    LIMIT 100
                ''')
                rows = cursor.fetchall()
                conn.close()
                added = 0
                for name, code in rows:
                    if name and add_managed_stock_entry(name, source="股票数据表", code_hint=code):
                        added += 1
                messagebox.showinfo("完成", f"已批量导入 {added} 只股票")
            except Exception as e:
                messagebox.showerror("错误", f"批量导入失败: {e}")
        def import_from_news_records():
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT tab_name, content
                    FROM news_info
                    WHERE tab_name LIKE '开新仓%'
                    ORDER BY created_at DESC
                    LIMIT 80
                ''')
                rows = cursor.fetchall()
                conn.close()
                import re
                added = 0
                for tab_name, content in rows:
                    candidate = None
                    parts = str(tab_name or "").split("-")
                    for part in parts:
                        part = part.strip()
                        if part and "开新仓" not in part and part not in ["绩优股", "朋友", "强势股", "龙头", "均值回归"]:
                            candidate = part
                            break
                    if not candidate:
                        match = re.search(r"股票名称[::]\s*([^\s\n]+)", content or "")
                        if match:
                            candidate = match.group(1)
                    if candidate and add_managed_stock_entry(candidate, source="资讯记录"):
                        added += 1
                messagebox.showinfo("完成", f"已从资讯记录导入 {added} 只股票")
            except Exception as e:
                messagebox.showerror("错误", f"导入资讯记录失败: {e}")
        def parse_friend_chat():
            raw = paste_text.get("1.0", tk.END).strip()
            if not raw:
                messagebox.showwarning("提示", "请先粘贴聊天记录或文本")
                return
            tokens = extract_names_from_text(raw)
            if not tokens:
                messagebox.showwarning("提示", "未解析到股票名称")
                return
            added = 0
            for token in tokens:
                if add_managed_stock_entry(token, source="聊天记录", remark="聊天"):
                    added += 1
            messagebox.showinfo("完成", f"已从聊天记录解析 {added} 只股票")
        def refresh_logic_display(content, status_text):
            logic_text.config(state=tk.NORMAL)
            logic_text.delete("1.0", tk.END)
            logic_text.insert("1.0", content)
            logic_text.config(state=tk.DISABLED)
            logic_status_var.set(status_text)
        def refresh_detection_display(message, content=None):
            detection_status_var.set(message)
            detection_text.config(state=tk.NORMAL)
            detection_text.delete("1.0", tk.END)
            if content:
                detection_text.insert("1.0", content)
            detection_text.config(state=tk.DISABLED)
        def load_logic_for_stock(stock_name):
            if not stock_name:
                refresh_logic_display("请选择股票查看逻辑", "逻辑:未选择")
                return
            data = get_stock_logic_from_db(stock_name=stock_name)
            if data:
                entry = data[0]
                logic = entry.get("logic") or "无逻辑内容"
                date_text = entry.get("date") or entry.get("created_at") or ""
                source_text = entry.get("source") or "-"
                refresh_logic_display(logic, f"逻辑:{date_text} | 来源:{source_text}")
            else:
                refresh_logic_display("数据库中暂无该股票的逻辑记录", "逻辑:暂无记录")
        def compute_detection(stock_name, stock_code):
            code = stock_code or get_stock_code_by_name(stock_name)
            if not code:
                return {"error": "未找到股票代码"}
            try:
                try:
                    _, closes = self._fetch_recent_daily_closes(code, days=40, source="akshare")
                except Exception as first_err:
                    try:
                        _, closes = self._fetch_recent_daily_closes(code, days=40, source="tushare")
                    except Exception as second_err:
                        return {"error": f"AKShare失败: {first_err}; Tushare失败: {second_err}"}
                if not closes:
                    return {"error": "无法获取日线数据"}
                price = closes[-1]
                result = {"code": code, "price": price}
                for period in (5, 10, 20):
                    if len(closes) >= period:
                        ma_value = sum(closes[-period:]) / period
                        diff = price - ma_value
                        pct = diff / ma_value * 100 if ma_value else 0
                        status = "站上" if diff >= 0 else "未站上"
                        result[f"ma{period}"] = ma_value
                        result[f"ma{period}_diff"] = diff
                        result[f"ma{period}_pct"] = pct
                        result[f"ma{period}_status"] = status
                    else:
                        result[f"ma{period}"] = None
                        result[f"ma{period}_status"] = "数据不足"
                return result
            except Exception as e:
                return {"error": str(e)}
        def load_detection_for_stock(stock_name, stock_code):
            if not stock_name:
                refresh_detection_display("技术检测:未选择")
                return
            refresh_detection_display("技术检测:抓取中...")
            def worker():
                result = compute_detection(stock_name, stock_code)
                def update_ui():
                    if result.get("error"):
                        refresh_detection_display(f"技术检测:{result['error']}", result['error'])
                    else:
                        lines = [
                            f"股票代码: {result.get('code')}  最新价: {result.get('price'):.2f}",
                        ]
                        for period in (5, 10, 20):
                            ma_value = result.get(f"ma{period}")
                            status = result.get(f"ma{period}_status", "")
                            if ma_value:
                                diff = result.get(f"ma{period}_diff", 0)
                                pct = result.get(f"ma{period}_pct", 0)
                                lines.append(
                                    f"{period}日均线: {ma_value:.2f} | {status} ({diff:+.2f}, {pct:+.2f}%)"
                                )
                            else:
                                lines.append(f"{period}日均线: 数据不足")
                        refresh_detection_display("技术检测:完成", "\n".join(lines))
                self.root.after(0, update_ui)
            detection_worker["thread"] = threading.Thread(target=worker, daemon=True)
            detection_worker["thread"].start()
        def on_tree_select(event=None):
            selection = managed_tree.selection()
            if not selection:
                return
            values = managed_tree.item(selection[0])['values']
            if not values:
                return
            name, code = values[0], values[1]
            selected_stock_context["name"] = name
            selected_stock_context["code"] = code
            detail_header_var.set(f"{name} ({code or '无代码'})")
            load_logic_for_stock(name)
            load_detection_for_stock(name, code)
        managed_tree.bind("<<TreeviewSelect>>", on_tree_select)
        ttk.Button(button_frame, text="从股票数据表选择", command=import_from_stock_db, width=18).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="批量导入股票数据", command=batch_import_from_stock_table, width=18).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="导入资讯记录", command=import_from_news_records, width=16).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="解析文本添加", command=add_from_text, width=14).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="聊天记录分析", command=parse_friend_chat, width=14).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="删除选中", command=remove_selected, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="刷新涨跌幅", command=lambda: threading.Thread(target=refresh_managed_tree_thread, daemon=True).start(), width=12).pack(side=tk.LEFT, padx=2)
        def clear_managed_stocks():
            if not self.managed_stocks:
                return
            if messagebox.askyesno("确认", "确定清空自选股池吗?", parent=parent_frame):
                self.managed_stocks.clear()
                sync_managed_history()
                refresh_managed_tree()
                self._save_managed_stocks_to_file()
        ttk.Button(
            button_frame,
            text="清空",
            command=clear_managed_stocks,
            width=8
        ).pack(side=tk.LEFT, padx=2)
        def refresh_selected_detection():
            if selected_stock_context["name"]:
                load_detection_for_stock(selected_stock_context["name"], selected_stock_context["code"])
        def copy_logic_to_clipboard():
            content = logic_text.get("1.0", tk.END).strip()
            if not content:
                messagebox.showwarning("提示", "当前没有可复制的逻辑内容")
                return
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                messagebox.showinfo("成功", "逻辑内容已复制到剪贴板")
            except Exception as e:
                messagebox.showerror("错误", f"复制失败: {e}")
        ttk.Button(action_frame, text="刷新检测", command=refresh_selected_detection, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="复制逻辑", command=copy_logic_to_clipboard, width=10).pack(side=tk.LEFT, padx=3)
        refresh_managed_tree()

    def _update_waiting_combo_values(self):
        combos = getattr(self, "waiting_combo_widgets", None)
        if not combos:
            return
        options = getattr(self, "managed_stock_names", []) or []
        values = options[-100:]
        for combo in combos:
            current = combo.get()
            combo["values"] = values
            if current and current in values:
                combo.set(current)

    def _open_growth_multi_selector(self, title, options, selected_values, summary_var):
        """多选弹窗:用于指数范围和股票类型。"""
        win = self._safe_toplevel(self.root)
        win.title(title)
        win.geometry("320x420")
        win.transient(self.root)
        win.grab_set()
        body = ttk.Frame(win, padding=10)
        body.pack(fill=tk.BOTH, expand=True)
        ttk.Label(body, text=title, font=("Microsoft YaHei", 11, "bold")).pack(anchor=tk.W, pady=(0, 8))
        vars_map = {}
        for opt in options:
            v = tk.BooleanVar(value=(opt in selected_values))
            vars_map[opt] = v
            ttk.Checkbutton(body, text=opt, variable=v).pack(anchor=tk.W, pady=2)
        btn_row = ttk.Frame(body)
        btn_row.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
        def save_and_close():
            picked = [k for k, vv in vars_map.items() if vv.get()]
            if not picked:
                picked = [options[0]]
            selected_values[:] = picked
            summary_var.set("、".join(picked))
            win.destroy()
        ttk.Button(btn_row, text="确认", command=save_and_close).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_row, text="取消", command=win.destroy).pack(side=tk.RIGHT, padx=4)

    def _open_growth_index_selector(self):
        self._open_growth_multi_selector(
            "选择指数范围",
            getattr(self, "growth_index_options", ["中证"]),
            self.growth_index_selections,
            self.growth_index_summary_var,
        )

    def _open_growth_type_selector(self):
        self._open_growth_multi_selector(
            "选择股票类型",
            getattr(self, "growth_type_options", ["成长股"]),
            self.growth_type_selections,
            self.growth_type_summary_var,
        )

    def _refresh_growth_candidates(self):
        """成长标签页:支持指数范围与股票类型复选组合拉取。"""
        index_selected = getattr(self, "growth_index_selections", ["中证"])
        type_selected = getattr(self, "growth_type_selections", ["成长股"])
        index_query_map = {
            "科创": "科创50 成份股",
            "上证": "上证指数 成份股",
            "中证": "中证500 成份股",
            "创业板": "创业板 成份股",
            "半导体": "半导体 概念股",
            "人工智能": "人工智能 概念股",
        }
        type_query_map = {
            "成长股": "成长股",
            "周期股": "周期股",
            "蓝筹": "蓝筹股",
            "问财-高股息": "高股息",
            "问财-低估值": "低估值",
            "问财-高景气": "高景气",
            "Skill-情绪龙头": "龙头股",
            "Skill-趋势加强": "趋势强势股",
            "Skill-机构偏好": "机构重仓",
        }
        queries = []
        for idx in index_selected:
            idx_q = index_query_map.get(idx, idx)
            for tp in type_selected:
                tp_q = type_query_map.get(tp, tp)
                queries.append(f"{idx_q} {tp_q}")
        all_stocks = []
        for q in queries:
            stocks = self._query_iwencai_stocks(q) or []
            all_stocks.extend(stocks)
        stocks = self._dedupe_elevator_stocks_by_code(all_stocks)
        disp = []
        for s in stocks[:120]:
            code = str(s.get("code", "") or "").strip()
            name = str(s.get("name", "") or "").strip()
            if code and name:
                disp.append(f"{name} ({code})")
            elif code:
                disp.append(code)
            elif name:
                disp.append(name)
        self.growth_candidate_list = disp
        txt = getattr(self, "growth_text_widget", None)
        cmb = getattr(self, "growth_stock_combo", None)
        if cmb is not None:
            cmb["values"] = disp
            if disp:
                cmb.set(disp[0])
            else:
                cmb.set("")
        if txt is not None:
            txt.config(state=tk.NORMAL)
            txt.delete("1.0", tk.END)
            txt.insert(tk.END, f"指数范围:{'、'.join(index_selected)}\n")
            txt.insert(tk.END, f"股票类型:{'、'.join(type_selected)}\n")
            txt.insert(tk.END, f"问财条件组合数:{len(queries)}\n")
            for q in queries[:20]:
                txt.insert(tk.END, f"- {q}\n")
            if len(queries) > 20:
                txt.insert(tk.END, f"... 其余 {len(queries) - 20} 条条件省略\n")
            txt.insert(tk.END, f"结果数量:{len(disp)}\n\n")
            for i, item in enumerate(disp[:80], start=1):
                txt.insert(tk.END, f"{i}. {item}\n")
            if not disp:
                txt.insert(tk.END, "未获取到候选结果(请检查 Node/pywencai/网络,或减少筛选组合)。\n")
            txt.config(state=tk.DISABLED)

    def show_market_data_detection(self):
        """全市场数据检测:检测主流30个ETF的持仓股均线检测"""
        # 创建检测窗口
        if hasattr(self, "_market_detection_window") and self._market_detection_window:
            if self._market_detection_window.winfo_exists():
                self._market_detection_window.deiconify()
                self._market_detection_window.lift()
                return
            self._market_detection_window = None
        dialog = self._safe_toplevel(self.root)
        dialog.title("全市场数据检测 - ETF持仓股均线检测")
        dialog.geometry("1600x900")
        dialog.transient(self.root)
        dialog.resizable(True, True)
        self._market_detection_window = dialog
        # 主框架
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # 标题和统计信息
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header_frame, text="主流30个ETF持仓股均线检测",
                 font=("TkDefaultFont", 14, "bold")).pack(side=tk.LEFT)
        status_label = ttk.Label(header_frame, text="正在检测...",
                                font=("TkDefaultFont", 12))
        status_label.pack(side=tk.RIGHT, padx=(10, 0))
        # 创建滚动框架
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        stocks_frame = ttk.Frame(canvas)
        stocks_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=stocks_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 存储股票标签的列表
        stock_labels = []
        # 定义主流30个ETF列表
        etf_configs = [
            ('510050', '上证50ETF'), ('588000', '科创50ETF'), ('510500', '中证500ETF'),
            ('512480', '半导体ETF'), ('515980', '人工智能ETF'), ('512570', '航空ETF'),
            ('512880', '证券ETF'), ('512660', '军工ETF'), ('159928', '消费ETF'),
            ('510300', '沪深300ETF'), ('159919', '沪深300ETF'), ('512100', '中证1000ETF'),
            ('159915', '创业板ETF'), ('512760', '芯片ETF'), ('515050', '5G ETF'),
            ('515880', '人工智能ETF'), ('512170', '医疗ETF'), ('512690', '酒ETF'),
            ('512980', '传媒ETF'), ('515030', '新基建ETF'), ('512200', '地产ETF'),
            ('512800', '银行ETF'), ('512340', '环保ETF'), ('159995', '芯片ETF'),
            ('159949', '华安创业板50ETF'), ('159915', '易方达创业板ETF'), ('512000', '券商ETF'),
            ('512010', '医药ETF'), ('512170', '医疗ETF'), ('515220', '煤炭ETF')
        ]
        # 在后台线程中执行检测
        def detect_market_data():
            """检测主流30个ETF的持仓股并进行均线检测,如果获取不到则使用资金流入股票"""
            try:
                import time

                import akshare as ak
                all_etf_stocks = []  # 存储所有ETF的持仓股
                etf_failed_count = 0  # 统计失败的ETF数量
                # 遍历每个ETF,获取持仓股
                for idx, (etf_code, etf_name) in enumerate(etf_configs):
                    try:
                        self.root.after(0, lambda e=etf_name, i=idx+1, t=len(etf_configs):
                                      status_label.config(text=f"正在获取 {e} 持仓股... ({i}/{t})"))
                        stocks_list = []
                        # 特殊处理:国家大基金持股使用概念板块
                        if etf_code == '国家大基金':
                            try:
                                concept_data = safe_call(ak.stock_board_concept_name_em, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_em")
                                if not concept_data.empty:
                                    target_concept = None
                                    for _, row in concept_data.iterrows():
                                        concept_name = str(row.get('板块名称', ''))
                                        if '国家大基金' in concept_name or '大基金' in concept_name:
                                            target_concept = concept_name
                                            break
                                    if target_concept:
                                        cons_data = ak.stock_board_concept_cons_em(symbol=target_concept)
                                        if cons_data is not None and not cons_data.empty:
                                            code_col = None
                                            name_col = None
                                            for col in cons_data.columns:
                                                col_str = str(col).lower()
                                                col_name = str(col)
                                                if code_col is None and ('代码' in col_name or 'code' in col_str):
                                                    code_col = col
                                                if name_col is None and ('名称' in col_name or 'name' in col_str):
                                                    name_col = col
                                            if code_col and name_col:
                                                for _, row in cons_data.iterrows():
                                                    try:
                                                        code = str(row[code_col]).strip()
                                                        name = str(row[name_col]).strip()
                                                        if code.isdigit():
                                                            code = code.zfill(6)
                                                            stocks_list.append((code, name, etf_name))
                                                    except:
                                                        continue
                            except Exception as e:
                                print(f"获取 {etf_name} 概念板块失败: {e}")
                                etf_failed_count += 1
                        else:
                            # 普通ETF:尝试多种方式获取ETF成分股
                            success = False
                            # 方法1:使用fund_etf_hold_sina
                            try:
                                cons_data = ak.fund_etf_hold_sina(symbol=etf_code)
                                if cons_data is not None and not cons_data.empty:
                                    code_col = None
                                    name_col = None
                                    for col in cons_data.columns:
                                        col_str = str(col).lower()
                                        col_name = str(col)
                                        if code_col is None and ('代码' in col_name or 'code' in col_str or '成分代码' in col_name or 'symbol' in col_str):
                                            code_col = col
                                        if name_col is None and ('名称' in col_name or 'name' in col_str or '成分名称' in col_name or '股票名称' in col_name):
                                            name_col = col
                                    if code_col and name_col:
                                        for _, row in cons_data.iterrows():
                                            try:
                                                code = str(row[code_col]).strip()
                                                name = str(row[name_col]).strip()
                                                if code.isdigit():
                                                    code = code.zfill(6)
                                                    stocks_list.append((code, name, etf_name))
                                                    success = True
                                            except:
                                                continue
                            except Exception as e1:
                                print(f"方法1获取 {etf_name}({etf_code}) 失败: {e1}")
                            # 方法2:尝试使用fund_etf_category_sina
                            if not success:
                                try:
                                    cons_data = ak.fund_etf_category_sina(symbol=etf_code)
                                    if cons_data is not None and not cons_data.empty:
                                        # 尝试解析数据
                                        for col in cons_data.columns:
                                            col_str = str(col).lower()
                                            col_name = str(col)
                                            if '代码' in col_name or 'code' in col_str or 'symbol' in col_str:
                                                for _, row in cons_data.iterrows():
                                                    try:
                                                        code = str(row[col]).strip()
                                                        if code.isdigit():
                                                            code = code.zfill(6)
                                                            # 尝试获取名称
                                                            name = str(row.get('名称', code)) if '名称' in cons_data.columns else code
                                                            stocks_list.append((code, name, etf_name))
                                                            success = True
                                                    except:
                                                        continue
                                except Exception as e2:
                                    print(f"方法2获取 {etf_name}({etf_code}) 失败: {e2}")
                            if not success:
                                etf_failed_count += 1
                                print(f"所有方法都无法获取 {etf_name}({etf_code}) 的持仓股")
                        all_etf_stocks.extend(stocks_list)
                        if stocks_list:
                            print(f"成功获取 {etf_name} 的 {len(stocks_list)} 只持仓股")
                        time.sleep(0.5)  # 避免请求过快
                    except Exception as e:
                        print(f"获取 {etf_name} 持仓股失败: {e}")
                        etf_failed_count += 1
                        continue
                # 去重(按股票代码)
                seen_codes = set()
                unique_stocks = []
                for code, name, etf_name in all_etf_stocks:
                    if code not in seen_codes:
                        seen_codes.add(code)
                        unique_stocks.append((code, name, etf_name))
                total_stocks = len(unique_stocks)
                print(f"ETF持仓股获取完成: 成功{len(etf_configs) - etf_failed_count}个,失败{etf_failed_count}个,共找到{total_stocks}只股票")
                # 如果获取不到ETF持仓股,改用资金流入股票
                if total_stocks == 0:
                    self.root.after(0, lambda: status_label.config(text="ETF持仓股获取失败,改用资金流入股票..."))
                    print("ETF持仓股获取失败,改用资金流入股票")
                    try:
                        # 获取资金流入排名前200的股票
                        self.root.after(0, lambda: status_label.config(text="正在获取资金流入股票..."))
                        # 尝试多种方式获取资金流入数据
                        fund_flow_data = None
                        # 方法1:使用stock_fund_flow_rank
                        try:
                            fund_flow_data = ak.stock_fund_flow_rank(indicator="今日")
                            print("使用stock_fund_flow_rank获取资金流入数据")
                        except Exception as e1:
                            print(f"stock_fund_flow_rank失败: {e1}")
                            # 方法2:使用stock_fund_flow_individual获取所有股票的资金流向
                            try:
                                # 获取所有A股列表
                                stock_list = safe_call(ak.stock_info_a_code_name, fallback=pd.DataFrame(), label="ak.stock_info_a_code_name")
                                if not stock_list.empty:
                                    # 取前500只股票尝试获取资金流向
                                    fund_flow_list = []
                                    for idx, row in stock_list.head(500).iterrows():
                                        try:
                                            code = str(row['code']).zfill(6)
                                            flow_data = ak.stock_fund_flow_individual(symbol=code, indicator="今日")
                                            if flow_data is not None and not flow_data.empty:
                                                # 提取净流入数据
                                                net_inflow = 0
                                                for col in flow_data.columns:
                                                    if '净流入' in str(col) or 'net' in str(col).lower():
                                                        try:
                                                            net_inflow = float(flow_data[col].iloc[-1] if len(flow_data) > 0 else 0)
                                                            break
                                                        except:
                                                            pass
                                                if net_inflow > 0:  # 只保留净流入为正的
                                                    fund_flow_list.append({
                                                        'code': code,
                                                        'name': row['name'],
                                                        'net_inflow': net_inflow
                                                    })
                                            time.sleep(0.1)  # 避免请求过快
                                        except:
                                            continue
                                    # 按净流入排序,取前200
                                    fund_flow_list.sort(key=lambda x: x['net_inflow'], reverse=True)
                                    fund_flow_data = pd.DataFrame(fund_flow_list[:200])
                                    print(f"通过个股资金流向获取到{len(fund_flow_data)}只股票")
                            except Exception as e2:
                                print(f"方法2也失败: {e2}")
                        # 如果还是获取不到,使用实时行情数据按涨跌幅排序
                        if fund_flow_data is None or fund_flow_data.empty:
                            try:
                                self.root.after(0, lambda: status_label.config(text="使用实时行情数据..."))
                                spot_data = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
                                if spot_data is not None and not spot_data.empty:
                                    # 找到涨跌幅列
                                    pct_col = None
                                    for col in spot_data.columns:
                                        if '涨跌幅' in str(col) or 'pct' in str(col).lower() or 'change' in str(col).lower():
                                            pct_col = col
                                            break
                                    if pct_col:
                                        # 按涨跌幅降序排序,取前200
                                        spot_data_sorted = spot_data.sort_values(by=pct_col, ascending=False).head(200)
                                        # 提取代码和名称
                                        code_col = None
                                        name_col = None
                                        for col in spot_data_sorted.columns:
                                            if '代码' in str(col) or 'code' in str(col).lower():
                                                code_col = col
                                            if '名称' in str(col) or 'name' in str(col).lower():
                                                name_col = col
                                        if code_col and name_col:
                                            fund_flow_data = spot_data_sorted[[code_col, name_col]].copy()
                                            fund_flow_data.columns = ['code', 'name']
                                            fund_flow_data['code'] = fund_flow_data['code'].astype(str).str.zfill(6)
                                            print(f"使用实时行情数据获取到{len(fund_flow_data)}只股票")
                            except Exception as e3:
                                print(f"使用实时行情数据失败: {e3}")
                        # 转换为统一格式
                        if fund_flow_data is not None and not fund_flow_data.empty:
                            unique_stocks = []
                            for _, row in fund_flow_data.iterrows():
                                try:
                                    code = str(row.get('code', row.iloc[0])).strip().zfill(6)
                                    name = str(row.get('name', row.iloc[1] if len(row) > 1 else code)).strip()
                                    if code.isdigit() and len(code) == 6:
                                        unique_stocks.append((code, name, "资金流入"))
                                except:
                                    continue
                            total_stocks = len(unique_stocks)
                            print(f"资金流入股票获取完成,共{total_stocks}只")
                            self.root.after(0, lambda: status_label.config(text=f"共找到 {total_stocks} 只资金流入股票,开始均线检测..."))
                        else:
                            self.root.after(0, lambda: status_label.config(text="无法获取股票数据"))
                            return
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        self.root.after(0, lambda e=e: status_label.config(text=f"获取资金流入股票失败: {e!s}"))
                        return
                else:
                    self.root.after(0, lambda: status_label.config(text=f"共找到 {total_stocks} 只持仓股,开始均线检测..."))
                # 对每个持仓股进行均线检测
                detection_results = []
                for idx, (stock_code, stock_name, etf_name) in enumerate(unique_stocks):
                    try:
                        if (idx + 1) % 10 == 0:
                            self.root.after(0, lambda i=idx+1, t=total_stocks:
                                          status_label.config(text=f"正在检测: {i}/{t}"))
                        # 使用三维一体检测进行均线检测
                        detection_result = self._three_dimensional_detection(stock_name, stock_code)
                        if detection_result and detection_result.get('success'):
                            ma_status = detection_result['technical']['ma_status']
                            can_open = detection_result['technical']['can_open']
                            kelly_percent = detection_result['position']['kelly_percent']
                            detection_results.append({
                                'code': stock_code,
                                'name': stock_name,
                                'etf': etf_name,
                                'ma_status': ma_status,
                                'can_open': can_open,
                                'kelly_percent': kelly_percent
                            })
                        time.sleep(0.1)  # 避免请求过快
                    except Exception as e:
                        print(f"检测 {stock_name}({stock_code}) 失败: {e}")
                        continue
                # 更新UI显示
                def update_ui():
                    # 清空现有标签
                    for label in stock_labels:
                        try:
                            label.destroy()
                        except:
                            pass
                    stock_labels.clear()
                    # 按一行8个显示
                    row = 0
                    col = 0
                    for result in detection_results:
                        stock_code = result['code']
                        stock_name = result['name']
                        etf_name = result['etf']
                        ma_status = result['ma_status']
                        can_open = result['can_open']
                        kelly_percent = result['kelly_percent']
                        # 创建股票标签框架
                        stock_frame = ttk.Frame(stocks_frame)
                        stock_frame.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
                        # 创建标签按钮
                        label = tk.Label(
                            stock_frame,
                            text=f"{stock_name}\n({stock_code})\n{etf_name}\n[{kelly_percent:.1f}%]",
                            font=("TkDefaultFont", 11),
                            bg="white",
                            relief=tk.RAISED,
                            padx=5,
                            pady=5,
                            cursor="hand2",
                            wraplength=180,
                            justify=tk.CENTER
                        )
                        label.pack(fill=tk.BOTH, expand=True)
                        # 根据均线状态设置颜色
                        if can_open:
                            label.config(fg="red", bg="white")
                        elif ma_status.get('near_ma10', False):
                            label.config(fg="orange", bg="white")
                        else:
                            label.config(fg="green", bg="white")
                        # 绑定双击事件
                        def make_click_handler(code=stock_code, name=stock_name):
                            def on_click(event):
                                self._show_stock_analysis_dialog(code, name)
                            return on_click
                        label.bind("<Double-Button-1>", make_click_handler())
                        stock_labels.append(label)
                        # 更新行列位置
                        col += 1
                        if col >= 8:
                            col = 0
                            row += 1
                    # 配置网格权重
                    for i in range(8):
                        stocks_frame.columnconfigure(i, weight=1)
                    status_label.config(text=f"检测完成!共检测 {len(detection_results)} 只股票")
                self.root.after(0, update_ui)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda e=e: status_label.config(text=f"检测失败: {e!s}"))
        # 启动检测线程
        thread = threading.Thread(target=detect_market_data, daemon=True)
        thread.start()
        def on_close():
            if self._market_detection_window:
                self._market_detection_window.destroy()
            self._market_detection_window = None
        dialog.protocol("WM_DELETE_WINDOW", on_close)

    def show_market_situation(self):
        """全市场情况:获取当天A股市场情况"""
        try:
            # 创建全市场情况窗口
            market_window = self._safe_toplevel(self.root)
            market_window.title("全市场情况")
            market_window.geometry("1200x800")
            market_window.transient(self.root)
            # 创建滚动框架
            canvas = tk.Canvas(market_window)
            scrollbar = ttk.Scrollbar(market_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            # 显示加载提示
            loading_label = ttk.Label(scrollable_frame, text="正在从同花顺接口获取市场数据...",
                                     font=("TkDefaultFont", 12))
            loading_label.pack(pady=20)
            market_window.update()
            # 在后台线程中获取数据
            def load_market_data():
                try:

                    import akshare as ak
                    market_data = {}
                    # 1. 获取个股涨跌幅统计
                    try:
                        spot_df = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
                        if spot_df is not None and not spot_df.empty:
                            total_stocks = len(spot_df)
                            up_stocks = len(spot_df[spot_df['涨跌幅'] > 0])
                            down_stocks = len(spot_df[spot_df['涨跌幅'] < 0])
                            flat_stocks = len(spot_df[spot_df['涨跌幅'] == 0])
                            market_data['stock_stats'] = {
                                'total': total_stocks,
                                'up': up_stocks,
                                'down': down_stocks,
                                'flat': flat_stocks,
                                'up_pct': round(up_stocks / total_stocks * 100, 2) if total_stocks > 0 else 0
                            }
                            market_data['spot_df'] = spot_df
                    except Exception as e:
                        print(f"获取个股统计失败: {e}")
                    # 2. 获取涨跌停板统计
                    try:
                        zt_df = safe_call(ak.stock_zt_pool_dtgc_em, fallback=[], label="ak.stock_zt_pool_dtgc_em")
                        if zt_df is not None and not zt_df.empty:
                            limit_up = len(zt_df[zt_df['类型'] == '涨停'])
                            limit_down = len(zt_df[zt_df['类型'] == '跌停'])
                            market_data['limit_stats'] = {
                                'limit_up': limit_up,
                                'limit_down': limit_down,
                                'zt_df': zt_df
                            }
                    except Exception as e:
                        print(f"获取涨跌停统计失败: {e}")
                    # 3. 获取热门板块涨幅(同花顺接口)
                    try:
                        concept_df = safe_call(ak.stock_board_concept_name_ths, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_ths")
                        if concept_df is not None and not concept_df.empty:
                            concept_df_sorted = concept_df.sort_values('涨跌幅', ascending=False).head(20)
                            market_data['hot_concepts'] = concept_df_sorted
                    except Exception as e:
                        print(f"获取概念板块失败: {e}")
                    # 4. 获取行业板块涨幅(同花顺接口)
                    try:
                        industry_df = safe_call(ak.stock_board_industry_name_ths, fallback=pd.DataFrame(), label="ak.stock_board_industry_name_ths")
                        if industry_df is not None and not industry_df.empty:
                            industry_df_sorted = industry_df.sort_values('涨跌幅', ascending=False).head(20)
                            market_data['hot_industries'] = industry_df_sorted
                    except Exception as e:
                        print(f"获取行业板块失败: {e}")
                    # 5. 获取最热门100只股票(按涨跌幅排序)
                    try:
                        spot_df = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
                        if spot_df is not None and not spot_df.empty:
                            # 按涨跌幅降序排序,取前100只
                            hot_100_stocks = spot_df.sort_values('涨跌幅', ascending=False).head(100)
                            market_data['hot_100_stocks'] = hot_100_stocks[['代码', '名称', '最新价', '涨跌幅', '涨跌额', '成交量', '成交额']]
                    except Exception as e:
                        print(f"获取最热门100只股票失败: {e}")
                    # 6. 获取龙虎榜股票
                    try:
                        from datetime import datetime, timedelta
                        lhb_stocks = []
                        # 获取最近5个交易日的龙虎榜数据
                        for i in range(10):
                            try:
                                check_date = datetime.now() - timedelta(days=i)
                                if check_date.weekday() >= 5:  # 跳过周末
                                    continue
                                date_str = check_date.strftime('%Y%m%d')
                                lhb_df = ak.stock_lhb_detail_em(start_date=date_str, end_date=date_str)
                                if lhb_df is not None and not lhb_df.empty:
                                    for _, row in lhb_df.iterrows():
                                        stock_code = row.get('代码', '')
                                        stock_name = row.get('名称', '')
                                        if stock_code and stock_name:
                                            # 去重
                                            if not any(s['代码'] == stock_code for s in lhb_stocks):
                                                lhb_stocks.append({
                                                    '代码': stock_code,
                                                    '名称': stock_name,
                                                    '日期': date_str
                                                })
                                if len(lhb_stocks) >= 50:  # 最多取50只
                                    break
                            except Exception as e:
                                print(f"获取{date_str}龙虎榜失败: {e}")
                                continue
                        market_data['lhb_stocks'] = lhb_stocks
                    except Exception as e:
                        print(f"获取龙虎榜股票失败: {e}")
                    # 7. 获取整体A股历史市盈率
                    try:
                        pe_df = safe_call(ak.stock_market_pe_lg, fallback=[], label="ak.stock_market_pe_lg")
                        if pe_df is not None and not pe_df.empty:
                            latest_pe = pe_df.iloc[-1]
                            market_data['market_pe'] = {
                                'pe': latest_pe.get('pe', 0),
                                'pb': latest_pe.get('pb', 0),
                                'date': latest_pe.get('date', ''),
                                'history': pe_df
                            }
                    except Exception as e:
                        print(f"获取市场PE失败: {e}")
                    # 8. 获取资金流入流出情况(北向资金)
                    try:
                        north_df = safe_call(ak.stock_connect_northbound_summary_em, fallback=[], label="ak.stock_connect_northbound_summary_em")
                        if north_df is not None and not north_df.empty:
                            latest = north_df.iloc[-1]
                            market_data['north_money'] = {
                                'net_buy': latest.get('净买入额', 0),
                                'buy_amount': latest.get('买入额', 0),
                                'sell_amount': latest.get('卖出额', 0),
                                'date': latest.get('日期', '')
                            }
                    except Exception as e:
                        print(f"获取北向资金失败: {e}")
                    # 9. 获取振幅最大80只股票
                    try:
                        if 'spot_df' in market_data:
                            spot_df = market_data['spot_df']
                            if spot_df is not None and not spot_df.empty and '振幅' in spot_df.columns:
                                amplitude_stocks = spot_df.sort_values('振幅', ascending=False).head(80)
                                market_data['amplitude_80_stocks'] = amplitude_stocks[['代码', '名称', '最新价', '涨跌幅', '振幅']]
                    except Exception as e:
                        print(f"获取振幅最大80只股票失败: {e}")
                    # 10. 获取5日线向上穿过20日线的股票(60分钟周期)
                    try:
                        import pandas as pd
                        ma5_cross_ma20_stocks = []
                        if 'spot_df' in market_data:
                            spot_df = market_data['spot_df']
                            if spot_df is not None and not spot_df.empty:
                                # 只检查前500只股票(避免超时)
                                check_stocks = spot_df.head(500)
                                for _, row in check_stocks.iterrows():
                                    try:
                                        stock_code = str(row.get('代码', '')).zfill(6)
                                        if not stock_code or stock_code == '000000':
                                            continue
                                        # 获取60分钟K线数据
                                        kline_60m = ak.stock_zh_a_hist_min_em(symbol=stock_code, period="60", adjust="")
                                        if kline_60m is not None and not kline_60m.empty and len(kline_60m) >= 20:
                                            # 计算5日和20日均线
                                            kline_60m['MA5'] = kline_60m['收盘'].rolling(window=5).mean()
                                            kline_60m['MA20'] = kline_60m['收盘'].rolling(window=20).mean()
                                            # 检查当前和前一根K线,判断是否向上穿过
                                            if len(kline_60m) >= 2:
                                                prev_ma5 = kline_60m['MA5'].iloc[-2]
                                                prev_ma20 = kline_60m['MA20'].iloc[-2]
                                                curr_ma5 = kline_60m['MA5'].iloc[-1]
                                                curr_ma20 = kline_60m['MA20'].iloc[-1]
                                                # 5日线向上穿过20日线:前一根5日线<20日线,当前5日线>=20日线
                                                if not pd.isna(prev_ma5) and not pd.isna(prev_ma20) and not pd.isna(curr_ma5) and not pd.isna(curr_ma20):
                                                    if prev_ma5 < prev_ma20 and curr_ma5 >= curr_ma20:
                                                        ma5_cross_ma20_stocks.append({
                                                            '代码': stock_code,
                                                            '名称': row.get('名称', ''),
                                                            '最新价': row.get('最新价', 0),
                                                            '涨跌幅': row.get('涨跌幅', 0)
                                                        })
                                    except Exception:
                                        continue
                                market_data['ma5_cross_ma20_stocks'] = ma5_cross_ma20_stocks
                    except Exception as e:
                        print(f"获取5日线穿过20日线股票失败: {e}")
                    # 11. 获取股价上穿15日线的股票
                    try:
                        price_cross_ma15_stocks = []
                        if 'spot_df' in market_data:
                            spot_df = market_data['spot_df']
                            if spot_df is not None and not spot_df.empty:
                                check_stocks = spot_df.head(500)
                                for _, row in check_stocks.iterrows():
                                    try:
                                        stock_code = str(row.get('代码', '')).zfill(6)
                                        if not stock_code or stock_code == '000000':
                                            continue
                                        # 获取15分钟K线数据
                                        kline_15m = ak.stock_zh_a_hist_min_em(symbol=stock_code, period="15", adjust="")
                                        if kline_15m is not None and not kline_15m.empty and len(kline_15m) >= 15:
                                            # 计算15日均线
                                            kline_15m['MA15'] = kline_15m['收盘'].rolling(window=15).mean()
                                            current_price = row.get('最新价', 0)
                                            if len(kline_15m) >= 2:
                                                prev_close = kline_15m['收盘'].iloc[-2]
                                                prev_ma15 = kline_15m['MA15'].iloc[-2]
                                                curr_ma15 = kline_15m['MA15'].iloc[-1]
                                                # 股价上穿15日线:前一根收盘价<15日线,当前价>=15日线
                                                if not pd.isna(prev_ma15) and not pd.isna(curr_ma15) and current_price > 0:
                                                    if prev_close < prev_ma15 and current_price >= curr_ma15:
                                                        price_cross_ma15_stocks.append({
                                                            '代码': stock_code,
                                                            '名称': row.get('名称', ''),
                                                            '最新价': current_price,
                                                            '涨跌幅': row.get('涨跌幅', 0)
                                                        })
                                    except Exception:
                                        continue
                                market_data['price_cross_ma15_stocks'] = price_cross_ma15_stocks
                    except Exception as e:
                        print(f"获取股价上穿15日线股票失败: {e}")
                    # 12. 获取昨天涨停的股票中,近十天来第一次涨停的股票
                    try:
                        from datetime import datetime, timedelta

                        import pandas as pd
                        yesterday_first_limit_up_stocks = []
                        # 找到最近一个交易日的日期
                        yesterday_date_str = None
                        for i in range(1, 6):
                            check_date = datetime.now() - timedelta(days=i)
                            if check_date.weekday() >= 5:  # 跳过周末
                                continue
                            yesterday_date_str = check_date.strftime('%Y%m%d')
                            break
                        if yesterday_date_str:
                            try:
                                # 获取昨天所有涨停股票
                                zt_df = ak.stock_zt_pool_em(date=yesterday_date_str)
                                if zt_df is not None and not zt_df.empty:
                                    # 遍历每只涨停股票,检查是否是近10天第一次涨停
                                    for _, zt_row in zt_df.iterrows():
                                        try:
                                            stock_code = str(zt_row.get('代码', '')).zfill(6)
                                            if not stock_code or stock_code == '000000':
                                                continue
                                            # 获取最近10天的历史数据
                                            hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                                            if hist_data is not None and not hist_data.empty and len(hist_data) >= 10:
                                                # 取最近10天数据
                                                recent_10 = hist_data.tail(10)
                                                # 检查最近10天中是否只有昨天涨停
                                                # 涨停判断:涨跌幅 >= 9.5%(考虑科创板、创业板等可能是20%)
                                                limit_up_count = 0
                                                for _, day_row in recent_10.iterrows():
                                                    change_pct = day_row.get('涨跌幅', 0)
                                                    # 涨停:涨跌幅>=9.5%(主板10%,科创板/创业板20%)
                                                    if change_pct >= 9.5:
                                                        limit_up_count += 1
                                                # 如果最近10天只有1次涨停,说明昨天是近10天第一次涨停
                                                if limit_up_count == 1:
                                                    yesterday_first_limit_up_stocks.append({
                                                        '代码': stock_code,
                                                        '名称': zt_row.get('名称', ''),
                                                        '最新价': zt_row.get('最新价', 0),
                                                        '涨跌幅': zt_row.get('涨跌幅', 0),
                                                        '日期': yesterday_date_str
                                                    })
                                        except Exception:
                                            continue
                            except Exception as e:
                                print(f"获取昨天涨停股票数据失败: {e}")
                        market_data['yesterday_first_limit_up'] = yesterday_first_limit_up_stocks
                    except Exception as e:
                        print(f"获取昨天第一次涨停股票失败: {e}")
                    # 13. 获取量增价涨的股票
                    try:
                        volume_price_up_stocks = []
                        if 'spot_df' in market_data:
                            spot_df = market_data['spot_df']
                            if spot_df is not None and not spot_df.empty:
                                # 量增价涨:成交量增加且价格上涨
                                for _, row in spot_df.iterrows():
                                    try:
                                        volume = row.get('成交量', 0)
                                        change_pct = row.get('涨跌幅', 0)
                                        # 筛选条件:涨跌幅>0 且 成交量>0
                                        if change_pct > 0 and volume > 0:
                                            volume_price_up_stocks.append({
                                                '代码': row.get('代码', ''),
                                                '名称': row.get('名称', ''),
                                                '最新价': row.get('最新价', 0),
                                                '涨跌幅': change_pct,
                                                '成交量': volume
                                            })
                                    except Exception:
                                        continue
                                # 按涨跌幅排序,取前100只
                                if volume_price_up_stocks:
                                    volume_price_up_stocks = sorted(volume_price_up_stocks, key=lambda x: x.get('涨跌幅', 0), reverse=True)[:100]
                                market_data['volume_price_up_stocks'] = volume_price_up_stocks
                    except Exception as e:
                        print(f"获取量增价涨股票失败: {e}")
                    # 14. 获取5日10日20日多头发散且股价靠近10日线的股票
                    try:
                        import pandas as pd
                        ma5_10_20_bullish_near_ma10_stocks = []
                        if 'spot_df' in market_data:
                            spot_df = market_data['spot_df']
                            if spot_df is not None and not spot_df.empty:
                                # 检查前300只股票(避免超时)
                                check_stocks = spot_df.head(300)
                                for _, row in check_stocks.iterrows():
                                    try:
                                        stock_code = str(row.get('代码', '')).zfill(6)
                                        if not stock_code or stock_code == '000000':
                                            continue
                                        current_price = row.get('最新价', 0)
                                        if current_price <= 0:
                                            continue
                                        # 获取日线数据
                                        hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                                        if hist_data is not None and not hist_data.empty and len(hist_data) >= 20:
                                            # 计算5日、10日、20日均线
                                            hist_data['MA5'] = hist_data['收盘'].rolling(window=5).mean()
                                            hist_data['MA10'] = hist_data['收盘'].rolling(window=10).mean()
                                            hist_data['MA20'] = hist_data['收盘'].rolling(window=20).mean()
                                            latest = hist_data.iloc[-1]
                                            ma5 = latest['MA5']
                                            ma10 = latest['MA10']
                                            ma20 = latest['MA20']
                                            if not pd.isna(ma5) and not pd.isna(ma10) and not pd.isna(ma20):
                                                # 多头发散条件:MA5 > MA10 > MA20
                                                if ma5 > ma10 > ma20:
                                                    # 股价靠近10日线条件:股价与10日线的差距在3%以内
                                                    price_diff_pct = abs(current_price - ma10) / ma10 * 100
                                                    if price_diff_pct <= 3:
                                                        ma5_10_20_bullish_near_ma10_stocks.append({
                                                            '代码': stock_code,
                                                            '名称': row.get('名称', ''),
                                                            '最新价': current_price,
                                                            '涨跌幅': row.get('涨跌幅', 0),
                                                            'MA5': round(ma5, 2),
                                                            'MA10': round(ma10, 2),
                                                            'MA20': round(ma20, 2),
                                                            '距MA10': f"{price_diff_pct:.2f}%"
                                                        })
                                    except Exception:
                                        continue
                                market_data['ma5_10_20_bullish_near_ma10'] = ma5_10_20_bullish_near_ma10_stocks
                    except Exception as e:
                        print(f"获取5日10日20日多头发散且靠近10日线股票失败: {e}")
                    # 15. 获取1日3日5日10日20日多头发散的股票
                    try:
                        import pandas as pd
                        ma1_3_5_10_20_bullish_stocks = []
                        if 'spot_df' in market_data:
                            spot_df = market_data['spot_df']
                            if spot_df is not None and not spot_df.empty:
                                # 检查前300只股票(避免超时)
                                check_stocks = spot_df.head(300)
                                for _, row in check_stocks.iterrows():
                                    try:
                                        stock_code = str(row.get('代码', '')).zfill(6)
                                        if not stock_code or stock_code == '000000':
                                            continue
                                        current_price = row.get('最新价', 0)
                                        if current_price <= 0:
                                            continue
                                        # 获取日线数据
                                        hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                                        if hist_data is not None and not hist_data.empty and len(hist_data) >= 20:
                                            # 计算1日(当日收盘价)、3日、5日、10日、20日均线
                                            hist_data['MA3'] = hist_data['收盘'].rolling(window=3).mean()
                                            hist_data['MA5'] = hist_data['收盘'].rolling(window=5).mean()
                                            hist_data['MA10'] = hist_data['收盘'].rolling(window=10).mean()
                                            hist_data['MA20'] = hist_data['收盘'].rolling(window=20).mean()
                                            latest = hist_data.iloc[-1]
                                            ma1 = current_price  # 1日线就是当前价格
                                            ma3 = latest['MA3']
                                            ma5 = latest['MA5']
                                            ma10 = latest['MA10']
                                            ma20 = latest['MA20']
                                            if not pd.isna(ma3) and not pd.isna(ma5) and not pd.isna(ma10) and not pd.isna(ma20):
                                                # 多头发散条件:MA1 > MA3 > MA5 > MA10 > MA20
                                                if ma1 > ma3 > ma5 > ma10 > ma20:
                                                    ma1_3_5_10_20_bullish_stocks.append({
                                                        '代码': stock_code,
                                                        '名称': row.get('名称', ''),
                                                        '最新价': current_price,
                                                        '涨跌幅': row.get('涨跌幅', 0),
                                                        'MA1': round(ma1, 2),
                                                        'MA3': round(ma3, 2),
                                                        'MA5': round(ma5, 2),
                                                        'MA10': round(ma10, 2),
                                                        'MA20': round(ma20, 2)
                                                    })
                                    except Exception:
                                        continue
                                market_data['ma1_3_5_10_20_bullish'] = ma1_3_5_10_20_bullish_stocks
                    except Exception as e:
                        print(f"获取1日3日5日10日20日多头发散股票失败: {e}")
                    # 在主线程中更新UI
                    def update_ui():
                        try:
                            self._display_market_data(scrollable_frame, loading_label, market_data)
                        except Exception as e:
                            print(f"更新UI失败: {e}")
                    self.root.after(0, update_ui)
                except Exception as e:
                    error_msg = f"获取市场数据失败: {e!s}"
                    print(error_msg)
                    import traceback
                    traceback.print_exc()
                    def show_error():
                        try:
                            loading_label.config(text=error_msg, foreground="red")
                        except Exception as e2:
                            print(f"显示错误信息失败: {e2}")
                    self.root.after(0, show_error)
            # 启动后台线程
            threading.Thread(target=load_market_data, daemon=True).start()
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
        except Exception as e:
            messagebox.showerror("错误", f"打开全市场情况窗口失败: {e!s}", parent=self.root)

    def _display_market_data(self, parent_frame, loading_label, market_data):
        """显示市场数据"""
        loading_label.destroy()
        # 创建两列布局的主容器
        main_container = ttk.Frame(parent_frame)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 左列
        left_column = ttk.Frame(main_container)
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        # 右列
        right_column = ttk.Frame(main_container)
        right_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        # 1. 个股涨跌幅统计(左列)
        if 'stock_stats' in market_data:
            stats = market_data['stock_stats']
            stats_frame = ttk.LabelFrame(left_column, text="个股涨跌幅统计", padding=10)
            stats_frame.pack(fill=tk.X, padx=5, pady=5)
            stats_text = f"总股票数: {stats['total']} | 上涨: {stats['up']} ({stats['up_pct']}%) | 下跌: {stats['down']} | 平盘: {stats['flat']}"
            ttk.Label(stats_frame, text=stats_text, font=("TkDefaultFont", 12)).pack(anchor=tk.W)
        # 2. 涨跌停板统计(左列)
        if 'limit_stats' in market_data:
            limit_stats = market_data['limit_stats']
            limit_frame = ttk.LabelFrame(left_column, text="涨跌停板统计", padding=10)
            limit_frame.pack(fill=tk.X, padx=5, pady=5)
            limit_text = f"涨停: {limit_stats['limit_up']} 只 | 跌停: {limit_stats['limit_down']} 只"
            ttk.Label(limit_frame, text=limit_text, font=("TkDefaultFont", 12)).pack(anchor=tk.W)
        # 3. 热门概念板块(右列)
        if 'hot_concepts' in market_data:
            concept_frame = ttk.LabelFrame(right_column, text="热门概念板块 TOP20", padding=10)
            concept_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            concept_tree = ttk.Treeview(concept_frame, columns=('涨跌幅', '涨跌额', '成交额'), show='tree headings', height=10)
            concept_tree.heading('#0', text='板块名称')
            concept_tree.heading('涨跌幅', text='涨跌幅(%)')
            concept_tree.heading('涨跌额', text='涨跌额')
            concept_tree.heading('成交额', text='成交额')
            for _, row in market_data['hot_concepts'].iterrows():
                concept_tree.insert('', 'end', text=row.get('板块名称', ''),
                                  values=(f"{row.get('涨跌幅', 0):.2f}",
                                         row.get('涨跌额', ''),
                                         row.get('成交额', '')))
            concept_scroll = ttk.Scrollbar(concept_frame, orient=tk.VERTICAL, command=concept_tree.yview)
            concept_tree.configure(yscrollcommand=concept_scroll.set)
            concept_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            concept_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        # 4. 热门行业板块(右列)
        if 'hot_industries' in market_data:
            industry_frame = ttk.LabelFrame(right_column, text="热门行业板块 TOP20", padding=10)
            industry_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            industry_tree = ttk.Treeview(industry_frame, columns=('涨跌幅', '涨跌额', '成交额'), show='tree headings', height=10)
            industry_tree.heading('#0', text='板块名称')
            industry_tree.heading('涨跌幅', text='涨跌幅(%)')
            industry_tree.heading('涨跌额', text='涨跌额')
            industry_tree.heading('成交额', text='成交额')
            for _, row in market_data['hot_industries'].iterrows():
                industry_tree.insert('', 'end', text=row.get('板块名称', ''),
                                   values=(f"{row.get('涨跌幅', 0):.2f}",
                                          row.get('涨跌额', ''),
                                          row.get('成交额', '')))
            industry_scroll = ttk.Scrollbar(industry_frame, orient=tk.VERTICAL, command=industry_tree.yview)
            industry_tree.configure(yscrollcommand=industry_scroll.set)
            industry_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            industry_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        # 5. 最热门100只股票(左列,一列显示)
        if 'hot_100_stocks' in market_data:
            hot_stocks_frame = ttk.LabelFrame(left_column, text="最热门100只股票", padding=10)
            hot_stocks_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            # 创建可复制文本区域
            hot_stocks_text_frame = ttk.Frame(hot_stocks_frame)
            hot_stocks_text_frame.pack(fill=tk.BOTH, expand=True)
            hot_stocks_text = tk.Text(hot_stocks_text_frame, height=20, wrap=tk.WORD, font=("TkDefaultFont", 11))
            hot_stocks_scroll = ttk.Scrollbar(hot_stocks_text_frame, orient=tk.VERTICAL, command=hot_stocks_text.yview)
            hot_stocks_text.configure(yscrollcommand=hot_stocks_scroll.set)
            # 构建可复制文本(一列显示)
            text_content = ""
            stocks_df = market_data['hot_100_stocks']
            if stocks_df is not None and not stocks_df.empty:
                for idx, (_, stock_row) in enumerate(stocks_df.iterrows(), 1):
                    stock_code = stock_row.get('代码', '')
                    stock_name = stock_row.get('名称', '')
                    stock_pct = stock_row.get('涨跌幅', 0)
                    # 格式化显示:名称(代码) 涨跌幅%
                    text_content += f"{stock_name}({stock_code}) {stock_pct:+.2f}%\n"
            else:
                text_content = "暂无数据,请稍后重试或检查网络连接。\n"
            hot_stocks_text.insert("1.0", text_content)
            hot_stocks_text.config(state=tk.NORMAL)  # 允许复制和选择
            hot_stocks_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            hot_stocks_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        else:
            # 如果数据获取失败,显示提示信息
            error_frame = ttk.LabelFrame(left_column, text="最热门100只股票", padding=10)
            error_frame.pack(fill=tk.X, padx=5, pady=5)
            error_label = ttk.Label(error_frame, text="数据获取失败,请稍后重试或检查网络连接",
                                   font=("TkDefaultFont", 12), foreground="red")
            error_label.pack(anchor=tk.W)
        # 6. 龙虎榜股票(左列)
        if 'lhb_stocks' in market_data:
            lhb_frame = ttk.LabelFrame(left_column, text="龙虎榜股票", padding=10)
            lhb_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            # 创建可复制文本区域
            lhb_text_frame = ttk.Frame(lhb_frame)
            lhb_text_frame.pack(fill=tk.BOTH, expand=True)
            lhb_text = tk.Text(lhb_text_frame, height=15, wrap=tk.WORD, font=("TkDefaultFont", 12))
            lhb_scroll = ttk.Scrollbar(lhb_text_frame, orient=tk.VERTICAL, command=lhb_text.yview)
            lhb_text.configure(yscrollcommand=lhb_scroll.set)
            # 构建可复制文本
            lhb_text_content = ""
            for stock in market_data['lhb_stocks']:
                lhb_text_content += f"{stock['名称']}({stock['代码']})\n"
            lhb_text.insert("1.0", lhb_text_content)
            lhb_text.config(state=tk.NORMAL)  # 允许复制
            lhb_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            lhb_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        # 7. 整体A股历史市盈率(左列)
        if 'market_pe' in market_data:
            pe_data = market_data['market_pe']
            pe_frame = ttk.LabelFrame(left_column, text="整体A股历史市盈率", padding=10)
            pe_frame.pack(fill=tk.X, padx=5, pady=5)
            pe_text = f"当前PE: {pe_data.get('pe', 0):.2f} | PB: {pe_data.get('pb', 0):.2f} | 日期: {pe_data.get('date', '')}"
            ttk.Label(pe_frame, text=pe_text, font=("TkDefaultFont", 12)).pack(anchor=tk.W)
        # 8. 资金流入流出情况(左列)
        if 'north_money' in market_data:
            money_data = market_data['north_money']
            money_frame = ttk.LabelFrame(left_column, text="北向资金流向", padding=10)
            money_frame.pack(fill=tk.X, padx=5, pady=5)
            money_text = f"净买入额: {money_data.get('net_buy', 0)} 亿元 | 买入额: {money_data.get('buy_amount', 0)} 亿元 | 卖出额: {money_data.get('sell_amount', 0)} 亿元 | 日期: {money_data.get('date', '')}"
            ttk.Label(money_frame, text=money_text, font=("TkDefaultFont", 12)).pack(anchor=tk.W)
        # 9. 振幅最大80只股票(左列,一列显示)
        if 'amplitude_80_stocks' in market_data:
            amplitude_frame = ttk.LabelFrame(left_column, text="振幅最大80只股票", padding=10)
            amplitude_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            amplitude_text_frame = ttk.Frame(amplitude_frame)
            amplitude_text_frame.pack(fill=tk.BOTH, expand=True)
            amplitude_text = tk.Text(amplitude_text_frame, height=15, wrap=tk.WORD, font=("TkDefaultFont", 11))
            amplitude_scroll = ttk.Scrollbar(amplitude_text_frame, orient=tk.VERTICAL, command=amplitude_text.yview)
            amplitude_text.configure(yscrollcommand=amplitude_scroll.set)
            text_content = ""
            stocks_df = market_data['amplitude_80_stocks']
            if stocks_df is not None and not stocks_df.empty:
                for _, stock_row in stocks_df.iterrows():
                    stock_code = stock_row.get('代码', '')
                    stock_name = stock_row.get('名称', '')
                    stock_amplitude = stock_row.get('振幅', 0)
                    stock_pct = stock_row.get('涨跌幅', 0)
                    text_content += f"{stock_name}({stock_code}) 振幅:{stock_amplitude:.2f}% 涨跌幅:{stock_pct:+.2f}%\n"
            else:
                text_content = "暂无数据,请稍后重试或检查网络连接。\n"
            amplitude_text.insert("1.0", text_content)
            amplitude_text.config(state=tk.NORMAL)
            amplitude_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            amplitude_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        # 10. 5日线向上穿过20日线的股票(右列,60分钟周期,一列显示)
        if 'ma5_cross_ma20_stocks' in market_data:
            ma5_cross_frame = ttk.LabelFrame(right_column, text="5日线向上穿过20日线的股票(60分钟周期)", padding=10)
            ma5_cross_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            ma5_cross_text_frame = ttk.Frame(ma5_cross_frame)
            ma5_cross_text_frame.pack(fill=tk.BOTH, expand=True)
            ma5_cross_text = tk.Text(ma5_cross_text_frame, height=10, wrap=tk.WORD, font=("TkDefaultFont", 11))
            ma5_cross_scroll = ttk.Scrollbar(ma5_cross_text_frame, orient=tk.VERTICAL, command=ma5_cross_text.yview)
            ma5_cross_text.configure(yscrollcommand=ma5_cross_scroll.set)
            text_content = ""
            stocks_list = market_data['ma5_cross_ma20_stocks']
            if stocks_list:
                for stock in stocks_list:
                    text_content += f"{stock.get('名称', '')}({stock.get('代码', '')}) 涨跌幅:{stock.get('涨跌幅', 0):+.2f}%\n"
            else:
                text_content = "暂无数据,请稍后重试或检查网络连接。\n"
            ma5_cross_text.insert("1.0", text_content)
            ma5_cross_text.config(state=tk.NORMAL)
            ma5_cross_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            ma5_cross_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        # 11. 股价上穿15日线的股票(右列,一列显示)
        if 'price_cross_ma15_stocks' in market_data:
            price_cross_frame = ttk.LabelFrame(right_column, text="股价上穿15日线的股票", padding=10)
            price_cross_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            price_cross_text_frame = ttk.Frame(price_cross_frame)
            price_cross_text_frame.pack(fill=tk.BOTH, expand=True)
            price_cross_text = tk.Text(price_cross_text_frame, height=10, wrap=tk.WORD, font=("TkDefaultFont", 11))
            price_cross_scroll = ttk.Scrollbar(price_cross_text_frame, orient=tk.VERTICAL, command=price_cross_text.yview)
            price_cross_text.configure(yscrollcommand=price_cross_scroll.set)
            text_content = ""
            stocks_list = market_data['price_cross_ma15_stocks']
            if stocks_list:
                for stock in stocks_list:
                    text_content += f"{stock.get('名称', '')}({stock.get('代码', '')}) 涨跌幅:{stock.get('涨跌幅', 0):+.2f}%\n"
            else:
                text_content = "暂无数据,请稍后重试或检查网络连接。\n"
            price_cross_text.insert("1.0", text_content)
            price_cross_text.config(state=tk.NORMAL)
            price_cross_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            price_cross_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        # 12. 昨天第一个涨停的股票(右列,一列显示)
        if 'yesterday_first_limit_up' in market_data:
            yesterday_zt_frame = ttk.LabelFrame(right_column, text="昨天涨停的股票中,近十天来第一次涨停", padding=10)
            yesterday_zt_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            yesterday_zt_text_frame = ttk.Frame(yesterday_zt_frame)
            yesterday_zt_text_frame.pack(fill=tk.BOTH, expand=True)
            yesterday_zt_text = tk.Text(yesterday_zt_text_frame, height=5, wrap=tk.WORD, font=("TkDefaultFont", 11))
            yesterday_zt_scroll = ttk.Scrollbar(yesterday_zt_text_frame, orient=tk.VERTICAL, command=yesterday_zt_text.yview)
            yesterday_zt_text.configure(yscrollcommand=yesterday_zt_scroll.set)
            text_content = ""
            stocks_list = market_data['yesterday_first_limit_up']
            if stocks_list:
                for stock in stocks_list:
                    text_content += f"{stock.get('名称', '')}({stock.get('代码', '')}) 涨跌幅:{stock.get('涨跌幅', 0):+.2f}%\n"
            else:
                text_content = "暂无数据,请稍后重试或检查网络连接。\n"
            yesterday_zt_text.insert("1.0", text_content)
            yesterday_zt_text.config(state=tk.NORMAL)
            yesterday_zt_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            yesterday_zt_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        # 13. 量增价涨的股票(右列,一列显示)
        if 'volume_price_up_stocks' in market_data:
            volume_price_frame = ttk.LabelFrame(right_column, text="量增价涨的股票", padding=10)
            volume_price_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            volume_price_text_frame = ttk.Frame(volume_price_frame)
            volume_price_text_frame.pack(fill=tk.BOTH, expand=True)
            volume_price_text = tk.Text(volume_price_text_frame, height=15, wrap=tk.WORD, font=("TkDefaultFont", 11))
            volume_price_scroll = ttk.Scrollbar(volume_price_text_frame, orient=tk.VERTICAL, command=volume_price_text.yview)
            volume_price_text.configure(yscrollcommand=volume_price_scroll.set)
            text_content = ""
            stocks_list = market_data['volume_price_up_stocks']
            if stocks_list:
                for stock in stocks_list:
                    text_content += f"{stock.get('名称', '')}({stock.get('代码', '')}) 涨跌幅:{stock.get('涨跌幅', 0):+.2f}%\n"
            else:
                text_content = "暂无数据,请稍后重试或检查网络连接。\n"
            volume_price_text.insert("1.0", text_content)
            volume_price_text.config(state=tk.NORMAL)
            volume_price_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            volume_price_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        # 14. 5日10日20日多头发散且股价靠近10日线的股票(右列)
        if 'ma5_10_20_bullish_near_ma10' in market_data:
            ma5_10_20_frame = ttk.LabelFrame(right_column, text="5日10日20日多头发散+股价靠近10日线", padding=10)
            ma5_10_20_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            ma5_10_20_text_frame = ttk.Frame(ma5_10_20_frame)
            ma5_10_20_text_frame.pack(fill=tk.BOTH, expand=True)
            ma5_10_20_text = tk.Text(ma5_10_20_text_frame, height=10, wrap=tk.WORD, font=("TkDefaultFont", 11))
            ma5_10_20_scroll = ttk.Scrollbar(ma5_10_20_text_frame, orient=tk.VERTICAL, command=ma5_10_20_text.yview)
            ma5_10_20_text.configure(yscrollcommand=ma5_10_20_scroll.set)
            text_content = ""
            stocks_list = market_data['ma5_10_20_bullish_near_ma10']
            if stocks_list:
                for stock in stocks_list:
                    text_content += f"{stock.get('名称', '')}({stock.get('代码', '')}) 涨跌幅:{stock.get('涨跌幅', 0):+.2f}% 距MA10:{stock.get('距MA10', '')}\n"
            else:
                text_content = "暂无符合条件的股票\n"
            ma5_10_20_text.insert("1.0", text_content)
            ma5_10_20_text.config(state=tk.NORMAL)
            ma5_10_20_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            ma5_10_20_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        # 15. 1日3日5日10日20日多头发散的股票(右列)
        if 'ma1_3_5_10_20_bullish' in market_data:
            ma1_3_5_10_20_frame = ttk.LabelFrame(right_column, text="1日3日5日10日20日多头发散", padding=10)
            ma1_3_5_10_20_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            ma1_3_5_10_20_text_frame = ttk.Frame(ma1_3_5_10_20_frame)
            ma1_3_5_10_20_text_frame.pack(fill=tk.BOTH, expand=True)
            ma1_3_5_10_20_text = tk.Text(ma1_3_5_10_20_text_frame, height=10, wrap=tk.WORD, font=("TkDefaultFont", 11))
            ma1_3_5_10_20_scroll = ttk.Scrollbar(ma1_3_5_10_20_text_frame, orient=tk.VERTICAL, command=ma1_3_5_10_20_text.yview)
            ma1_3_5_10_20_text.configure(yscrollcommand=ma1_3_5_10_20_scroll.set)
            text_content = ""
            stocks_list = market_data['ma1_3_5_10_20_bullish']
            if stocks_list:
                for stock in stocks_list:
                    text_content += f"{stock.get('名称', '')}({stock.get('代码', '')}) 涨跌幅:{stock.get('涨跌幅', 0):+.2f}%\n"
            else:
                text_content = "暂无符合条件的股票\n"
            ma1_3_5_10_20_text.insert("1.0", text_content)
            ma1_3_5_10_20_text.config(state=tk.NORMAL)
            ma1_3_5_10_20_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            ma1_3_5_10_20_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _url_from_series_any_cell(self, row) -> str | None:
        """在整行各列中找第一个 http(s) 片段(列名变化时兜底)。"""
        import re
        parts = []
        try:
            for k in row.index:
                try:
                    v = row[k]
                    if v is None or pd.isna(v):
                        continue
                    parts.append(str(v))
                except Exception:
                    continue
        except Exception:
            return None
        blob = " ".join(parts)
        m = re.search(r"https?://[^\s'\"<>)]+", blob)
        if not m:
            return None
        href = m.group(0)
        while href and href[-1] in ".,;:!?)】』\"'、,。)]}>":
            href = href[:-1]
        return self._normalize_news_item_url(href)

    def _apply_hyperlinks_to_text_widget(self, wgt):
        """识别 Text/ScrolledText 中的 http(s) 链接,设为蓝色下划线,点击用浏览器打开。"""
        import re
        import webbrowser
        text = wgt.get("1.0", "end-1c")
        for tname in list(wgt.tag_names()):
            if str(tname).startswith("u_link_"):
                wgt.tag_delete(tname)
        pat = re.compile(r"https?://[^\s]+", re.IGNORECASE)
        li = 0
        for m in pat.finditer(text):
            raw = m.group(0)
            href = raw
            while href and href[-1] in ".,;:!?)】』\"'、,。)]}>":
                href = href[:-1]
            if not href.startswith("http"):
                continue
            start_c = m.start()
            end_c = m.start() + len(href)
            if end_c <= start_c:
                continue
            tname = f"u_link_{li}"
            li += 1
            wgt.tag_add(tname, f"1.0+{start_c}c", f"1.0+{end_c}c")
            wgt.tag_configure(tname, foreground="#0B57D0", underline=True)
            def _open_u(_e, h=href):
                try:
                    webbrowser.open(h)
                except Exception:
                    pass
                return "break"
            wgt.tag_bind(tname, "<Button-1>", _open_u)
            wgt.tag_bind(
                tname,
                "<Enter>",
                lambda e, tw=wgt: tw.config(cursor="hand2"),
            )
            wgt.tag_bind(
                tname,
                "<Leave>",
                lambda e, tw=wgt: tw.config(cursor="arrow"),
            )

    def _ia_load(self, top_win):
        """盘中警告弹窗后台加载"""
        import threading as _th
        top_win.config(cursor="watch")

        def _run():
            try:
                alert = self._fetch_intraday_alert_data()
                self.root.after(0, lambda: self._ia_render(alert))
            except Exception as e:
                import traceback; traceback.print_exc()
                self.root.after(0, lambda e=e: self._ia_render(None, err=str(e)))
        _th.Thread(target=_run, daemon=True).start()

    def _ia_render(self, alert, err=None):
        """盘中警告弹窗主线程渲染"""
        try:
            top = self.root
            # 找弹窗实例
            for w in top.winfo_children():
                if isinstance(w, tk.Toplevel) and "盘中警告" in w.title():
                    w.config(cursor="")

            if err:
                self._ia_timestamp_var.set(f"❌ 拉取失败: {err}")
                return
            if not alert:
                self._ia_timestamp_var.set("❌ 无数据")
                return

            self._ia_timestamp_var.set(
                f"⏱ {alert['timestamp']}  {'交易时段' if alert['is_trading'] else '非交易时段'}")

            comp = alert["composite"]
            score = comp["score"]
            level = comp["level"]
            level_cn = comp["level_cn"]
            signal = comp["signal"]

            # === 综合评分大卡片 ===
            cv = self._ia_score_canvas
            cv.delete("all")
            # 背景色
            bg_map = {"excellent": "#E8F5E9", "good": "#E3F2FD",
                      "warning": "#FFF8E1", "danger": "#FFEBEE"}
            fg_map = {"excellent": "#2E7D32", "good": "#1565C0",
                      "warning": "#F57F17", "danger": "#C62828"}
            cv.create_rectangle(2, 2, cv.winfo_width()-2, 78,
                                fill=bg_map.get(level, "#F5F5F5"),
                                outline=fg_map.get(level, "#333"), width=2)
            # 大分数字
            cv.create_text(80, 40, text=f"{score}", font=("", 36, "bold"),
                           fill=fg_map.get(level, "#333"))
            cv.create_text(80, 65, text="综合评分", font=("", 8),
                           fill="#666")
            # 等级灯+等级文字
            cv.create_text(200, 35, text=f"{signal} {level_cn}",
                           font=("", 20, "bold"), fill=fg_map.get(level, "#333"))
            cv.create_text(200, 58, text=f"盘面状态判定: {self._ia_judge_text(level)}",
                           font=("", 9), fill="#555")

            # === 指数涨跌表格 ===
            for row in self._ia_idx_tree.get_children():
                self._ia_idx_tree.delete(row)
            for it in alert.get("indices", []):
                pct = it["pct"]
                pct_str = f"{pct:+.2f}%"
                self._ia_idx_tree.insert("", tk.END, values=(
                    it["name"], f"{it['close']:.2f}", pct_str))
                # 按涨跌染色行
                tags = ("up",) if pct > 0 else (("down",) if pct < 0 else ())
                self._ia_idx_tree.item(self._ia_idx_tree.get_children()[-1], tags=tags)
            self._ia_idx_tree.tag_configure("up", foreground="#C62828")
            self._ia_idx_tree.tag_configure("down", foreground="#2E7D32")

            # === 涨跌广度 ===
            br = alert["breadth"]
            up, dn = br.get("up", 0), br.get("down", 0)
            zt, dt = br.get("zt", 0), br.get("dt", 0)
            ratio = up / max(dn, 1)
            ratio_txt = f"{ratio:.2f}"
            zt_rate = zt / max(br.get("total", 1), 1) * 100
            txt = (f"涨 {up} / 跌 {dn} / 平 {br.get('flat',0)}   "
                   f"涨跌比 {ratio_txt}   "
                   f"涨停 {zt} ({zt_rate:.1f}%)   跌停 {dt}")
            self._ia_br_var.set(txt)

            # === 5维度详细判别 ===
            self._ia_dim_txt.config(state=tk.NORMAL)
            self._ia_dim_txt.delete("1.0", tk.END)
            for d in comp.get("details", []):
                emoji = d[0]
                if emoji == "🟢":
                    tag = "good"
                elif emoji == "🟡":
                    tag = "warn"
                else:
                    tag = "bad"
                self._ia_dim_txt.insert(tk.END, d + "\n", tag)
            self._ia_dim_txt.config(state=tk.DISABLED)

            # === 操作建议 ===
            advice = self._ia_build_advice(alert)
            self._ia_advice_var.set(advice)

        except Exception:
            import traceback; traceback.print_exc()

    def _ia_judge_text(self, level):
        """等级描述"""
        return {
            "excellent": "多头强势, 积极做多",
            "good": "偏多震荡, 可正常操作",
            "warning": "震荡偏弱, 谨慎追高",
            "danger": "空头主导, 严控仓位!"
        }.get(level, "观望为主")

    def _lc_update_card(self, code, name, result, skip_reason, trade_date, skip_count):
        """后台线程回调: 更新生命周期弹窗中的一张卡"""
        for w in self.root.winfo_children():
            if isinstance(w, tk.Toplevel) and hasattr(w, '_on_stock_done'):
                try: w._on_stock_done(code, name, result, skip_reason, trade_date, skip_count)
                except Exception: pass
                return

    def _lc_scan_finished(self, g_hash, holder):
        """全部扫描完毕 — 通知弹窗 + 缓存"""
        _cache_hit_list = []
        _cache_skipped = []
        try:
            for w in self.root.winfo_children():
                if isinstance(w, tk.Toplevel) and hasattr(w, '_on_all_done'):
                    w._on_all_done()
                    _cache_hit_list = getattr(w, '_lc_hit_list', [])
                    _cache_skipped = getattr(w, '_lc_skipped_list', [])
                    break
        except Exception: pass
        self._lifecycle_cache = {"ts": time.time(), "groups": g_hash,
            "data": {"trade_date": holder.get("trade_date",""), "stocks": _cache_hit_list,
                     "_skipped_list": _cache_skipped,
                     "skip_count": holder.get("skip_count",{})}}

    def _run_volume_price_scan(self):
        """📈 量价齐升选股后台计算: 拉全市场行情 + 均线 + 板块匹配 → 综合排名
        Returns:
            dict: {"trade_date": str, "stocks": list, "total_found": int}
        """
        import datetime as _dt_mod
        import os as _os_env

        import tushare as _ts_pro

        # --- 1. 初始化 tushare ---
        _token = (_os_env.environ.get("TUSHARE_TOKEN", "") or getattr(self, "ts_token", "") or TS_DEFAULT_TOKEN or "").strip()
        if not _token:
            return {"trade_date": "", "stocks": [], "total_found": 0, "error": "TUSHARE_TOKEN 未配置"}
        _ts_pro.set_token(_token)
        pro = _ts_pro.pro_api()

        # --- 2. 找最近交易日 ---
        today = _dt_mod.date.today()
        cal = pro.trade_cal(
            exchange="SSE",
            start_date=(today - _dt_mod.timedelta(days=10)).strftime("%Y%m%d"),
            end_date=today.strftime("%Y%m%d"),
            is_open="1"
        )
        if cal is None or len(cal) == 0:
            # 兜底: 取今天
            trade_date = today.strftime("%Y%m%d")
        else:
            trade_date = str(cal["cal_date"].iloc[0])  # tushare trade_cal 默认降序, iloc[0]=最新!

        # --- 3. 批量拉申万行业映射(一次性, 避免限流) ---
        sector_map = self._build_sw_sector_map(pro)

        # --- 4. 拉全市场 daily(单日) + daily_basic + stock_basic ---
        print(f"[量价齐升] 扫描交易日={trade_date} ...")
        df_daily = pro.daily(trade_date=trade_date)
        if df_daily is None or len(df_daily) == 0:
            return {"trade_date": trade_date, "stocks": [], "total_found": 0, "error": "daily 数据为空(可能非交易日)"}

        df_basic = pro.daily_basic(
            trade_date=trade_date,
            fields="ts_code,pe,pb,total_mv,circ_mv,turnover_rate,volume_ratio"
        )
        df_sb = pro.stock_basic(exchange="", list_status="L", fields="ts_code,name,industry,list_date")
        self._last_stock_basic_df = df_sb  # 缓存给 _build_sw_sector_map 用

        # Merge
        df = df_daily.copy()
        if df_basic is not None and len(df_basic) > 0:
            df = df.merge(df_basic, on="ts_code", how="left")
        if df_sb is not None and len(df_sb) > 0:
            df = df.merge(df_sb, on="ts_code", how="left")

        print(f"[量价齐升] 全市场 {len(df)} 只, 开始粗筛 ...")

        # --- 5. 粗筛 ---
        # 确保列存在
        for col in ["volume_ratio", "turnover_rate", "name", "pct_chg", "close"]:
            if col not in df.columns:
                df[col] = np.nan

        df["volume_ratio"] = pd.to_numeric(df["volume_ratio"], errors="coerce")
        df["pct_chg"] = pd.to_numeric(df["pct_chg"], errors="coerce")
        df["turnover_rate"] = pd.to_numeric(df["turnover_rate"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["high"] = pd.to_numeric(df.get("high", np.nan), errors="coerce")
        df["low"] = pd.to_numeric(df.get("low", np.nan), errors="coerce")

        # 基础筛选
        cond_pct = df["pct_chg"] > 1.0
        cond_vr = df["volume_ratio"] > 1.3
        cond_name_st = ~df["name"].fillna("").str.contains("ST|退", regex=True, na=False)
        cond_tr = df["turnover_rate"].between(0.5, 25)
        # 排除一字涨停: 振幅<1% 且 涨停
        cond_not_zt = ~((df.get("high", df["close"]) - df.get("low", df["close"])) / df["close"] < 0.01) | (df["pct_chg"] < 9.5)

        candidates = df[cond_pct & cond_vr & cond_name_st & cond_tr & cond_not_zt].copy()

        # 排除上市 < 60 天的次新股
        if "list_date" in candidates.columns:
            try:
                candidates["list_date"] = pd.to_datetime(candidates["list_date"], errors="coerce")
                min_list = today - _dt_mod.timedelta(days=60)
                candidates = candidates[candidates["list_date"] <= pd.Timestamp(min_list)]
            except Exception:
                pass

        print(f"[量价齐升] 粗筛后 {len(candidates)} 只, 开始精算均线 ...")

        # --- 6. 对候选股拉历史K线算MA + 判断连续量价齐升 ---
        results = []
        max_iter = min(60, len(candidates))  # 限流保护: 最多60只K线拉取
        for idx, (_, row) in enumerate(candidates.head(80).iterrows()):
            if idx >= max_iter:
                break
            tsc = row.get("ts_code", "")
            if not tsc or not isinstance(tsc, str):
                continue
            name = str(row.get("name", "")) if pd.notna(row.get("name")) else ""
            code = tsc.split(".")[0]

            # 拉历史K线 (节流保护: 0.25s/次 → 240次/分钟 < 300限制)
            try:
                time.sleep(0.25)
                hist = pro.daily(
                    ts_code=tsc,
                    start_date=(today - _dt_mod.timedelta(days=150)).strftime("%Y%m%d"),
                    end_date=trade_date
                )
            except Exception:
                continue
            if hist is None or len(hist) < 30:
                continue
            hist = hist.sort_values("trade_date").reset_index(drop=True)
            cl = hist["close"].values.astype(float)
            vo = hist["vol"].values.astype(float)

            # MA
            if len(cl) < 20:
                continue
            m5 = float(np.mean(cl[-5:]))
            m10 = float(np.mean(cl[-10:]))
            m20 = float(np.mean(cl[-20:]))

            # 均线多头
            ma_bull = m5 > m10 > m20

            # 连续量价齐升天数(从最近一天往前数)
            streak = 0
            n_hist = len(cl)
            for i in range(-1, -min(6, n_hist), -1):
                # 价涨: close[i] > close[i-1]
                # 量增: vol[i] > 近20日均量
                vol_ref = np.mean(vo[max(0, i-20):i]) if abs(i) >= 20 else np.mean(vo[:i])
                if abs(i-1) > n_hist:
                    break
                try:
                    if cl[i] > cl[i-1] and vo[i] > vol_ref:
                        streak += 1
                    else:
                        break
                except Exception:
                    break

            if not ma_bull:
                continue  # 必须均线多头

            # --- 基本面评分 ---
            pe = row.get("pe")
            mv = row.get("total_mv")
            tr = row.get("turnover_rate")
            vr = row.get("volume_ratio")
            pct = float(row.get("pct_chg", 0)) if pd.notna(row.get("pct_chg")) else 0
            price = float(row.get("close", 0)) if pd.notna(row.get("close")) else 0

            fund_score = 50
            if pd.notna(pe) and 10 < pe < 30:
                fund_score += 20
            elif pd.notna(pe) and pe > 60:
                fund_score -= 20
            if pd.notna(mv):
                mv_yi = float(mv) * 1e-4
                if 50 < mv_yi < 1000:
                    fund_score += 15
                elif mv_yi > 2000:
                    fund_score -= 10
            if pd.notna(tr) and 3 < float(tr) < 12:
                fund_score += 10
            if pd.notna(vr) and float(vr) > 2.0:
                fund_score += 5

            # --- 技术面评分 ---
            tech_score = min(100, streak * 20)
            if pd.notna(vr) and float(vr) > 2:
                tech_score += 10
            if 2 < pct < 7:
                tech_score += 10

            # --- 综合分 ---
            total_score = int(max(0, min(100, fund_score * 0.4 + tech_score * 0.6)))

            # --- 板块 ---
            sector = sector_map.get(tsc, self._fallback_sector_by_name(name))

            # --- 上涨原因 ---
            reasons = []
            if streak >= 2:
                reasons.append(f"连续{streak}天量价齐升")
            if pd.notna(vr) and float(vr) > 2.0:
                reasons.append(f"放量明显(量比{float(vr):.1f})")
            if pct > 5:
                reasons.append("涨幅较大")
            if ma_bull:
                reasons.append("均线多头排列")
            reasons.append(f"所属板块: {sector}")

            results.append({
                "code": code,
                "name": name,
                "ts_code": tsc,
                "price": price,
                "pct": pct,
                "vr": float(vr) if pd.notna(vr) else 0,
                "tr": float(tr) if pd.notna(tr) else 0,
                "pe": float(pe) if pd.notna(pe) else None,
                "mv_yi": float(mv) * 1e-4 if pd.notna(mv) else None,
                "m5": m5,
                "m10": m10,
                "m20": m20,
                "ma_bull": ma_bull,
                "streak": streak,
                "fund_score": int(fund_score),
                "tech_score": int(tech_score),
                "total_score": total_score,
                "sector": sector,
                "reasons": reasons,
            })

        # --- 7. 按综合分排序取Top30 ---
        results.sort(key=lambda x: x["total_score"], reverse=True)
        print(f"[量价齐升] ✅ 完成, 均线多头 {len(results)} 只, 返回 Top {min(30, len(results))}")

        return {"trade_date": trade_date, "stocks": results[:30], "total_found": len(results)}

    def _gather_major_index_spot_text(self):
        """主要指数即时行情短表(东财),供 AI 员工等模块复用。"""
        try:
            import akshare as ak
            df = safe_call(ak.stock_zh_index_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_index_spot_em")
            if df is None or df.empty:
                return "(无数据)"
            name_col = "名称" if "名称" in df.columns else df.columns[1]
            sub = df[
                df[name_col].astype(str).str.contains(
                    "上证指数|深证成指|创业板指|沪深300|科创50|中证500|北证50",
                    regex=True,
                    na=False,
                )
            ]
            if sub.empty:
                return df.head(10).to_string(index=False)
            keep = [c for c in ["代码", "名称", "最新价", "涨跌幅", "涨跌额", "成交量", "成交额"] if c in sub.columns]
            return sub[keep].head(12).to_string(index=False)
        except Exception as e:
            return f"(获取失败:{e})"

    def _collect_focus_indices_spot_text(self):
        """沪深300、中证500、科创50 等指数即时行;同花顺情绪指数以概念日线为准(见上文)。"""
        try:
            import akshare as ak
            df = safe_call(ak.stock_zh_index_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_index_spot_em")
            if df is None or df.empty:
                return "(指数即时表为空)"
            name_col = "名称" if "名称" in df.columns else df.columns[1]
            pat = r"沪深300|中证500|科创50|上证50|创业板指|深证成指|上证指数"
            sub = df[df[name_col].astype(str).str.contains(pat, regex=True, na=False)]
            if sub.empty:
                return df.head(12).to_string(index=False)
            keep = [c for c in ["代码", "名称", "最新价", "涨跌幅", "涨跌额", "成交量", "成交额"] if c in sub.columns]
            return sub[keep].head(20).to_string(index=False)
        except Exception as e:
            return f"(获取失败:{e})"

    def _collect_system_judgment_raw_context(self):
        """系统研判:汇总 1~6 类原始材料(不含 AI 结论)。"""
        blocks = []
        blocks.append(
            "【系统研判 · 原始汇总】"
            + datetime.now().strftime(" %Y-%m-%d %H:%M:%S")
            + "\n说明:龙头股/15Min/Main 三池为程序内近似映射;可与您的实际用法对照调整。"
        )
        # 1 左侧三池 + 仓位面评分
        try:
            st = self._collect_holding_pool_stats()
            lbls, cnts = st["labels"], st["counts"]
            blocks.append(
                "══ 1)左侧指标选股池(数量与质量近似)══\n"
                f"· {lbls[0]}:已填 {cnts[0]} / 80,填充率 {st['fill_rates'][0]:.1%}\n"
                f"· {lbls[1]}:已填 {cnts[1]} / 80,填充率 {st['fill_rates'][1]:.1%}\n"
                f"· {lbls[2]}:已填 {cnts[2]} / 80,填充率 {st['fill_rates'][2]:.1%}\n"
                f"· 三池代码同时重叠数:{st['triple_overlap_n']}(越多表示三类信号共振标的越多)\n"
                f"· 两两重叠:龙头∩15Min={st['pair_23']},龙头∩Main={st['pair_24']},15Min∩Main={st['pair_34']}\n"
            )
        except Exception as e:
            blocks.append(f"══ 1)左侧选股池 ══\n(统计失败:{e})")
        try:
            fv = int(self.fundamental_var.get() or 0)
            tv = int(self.technical_var.get() or 0)
            sv = int(self.sentiment_var.get() or 0)
            blocks.append(
                f"· 仓位区「基本面/技术面/情绪面」主观打分(各0~30):{fv} / {tv} / {sv},合计 {fv + tv + sv}\n"
            )
        except Exception:
            blocks.append("· 仓位区三维度打分:无法读取\n")
        # 2 情绪按钮相关:与「情绪」弹窗同源的指标快照 + 同花顺情绪日线 + 界面状态
        blocks.append("══ 2)情绪环境与「情绪」按钮相关指标(与 AI 员工分析师上下文同源)══")
        try:
            blocks.append(self._gather_ai_staff_analyst_context())
        except Exception as e:
            blocks.append(f"(失败:{e})")
        # 3 实时新闻
        blocks.append("\n══ 3)实时新闻(与「实时新闻」按钮同源 · 纯文本)══")
        try:
            blocks.append(self._collect_realtime_world_us_snapshot())
        except Exception as e:
            blocks.append(f"(失败:{e})")
        # 4 大盘波动率 + 能量聚集/发散(避免与第2节全文重复,仅摘 VXX 相关行 + 上证能量)
        blocks.append("\n══ 4)大盘波动率与能量聚集/发散 ══")
        try:
            snap = self._collect_market_sentiment_snapshot()
            excerpt = [ln for ln in snap.splitlines() if "VXX" in ln or "波动率短期期货" in ln][:25]
            if excerpt:
                blocks.append("【全球风险偏好 · VXX 等节选】\n" + "\n".join(excerpt))
            else:
                blocks.append("(未在快照中匹配到 VXX 行;完整美股 ETF 段请打开「情绪」弹窗查看)")
        except Exception as e:
            blocks.append(f"(波动率节选失败:{e})")
        try:
            blocks.append(self._collect_shanghai_volatility_and_energy_text())
        except Exception as e:
            blocks.append(f"(上证波动/能量:{e})")
        # 5 主要指数 + 同花顺情绪
        blocks.append("\n══ 5)沪深300、中证500、科创50 与 同花顺情绪指数 ══")
        blocks.append("【重点指数即时】\n" + self._collect_focus_indices_spot_text())
        blocks.append("\n【同花顺情绪指数 · 概念日线】")
        try:
            ths_txt, _ = self._prediction_fetch_ths_sentiment_daily()
            blocks.append(ths_txt or "未能拉取。")
        except Exception as e:
            blocks.append(f"(失败:{e})")
        return "\n".join(blocks)

    def _quant_strategy_skill_catalog(self):
        """市面常见 A 股量化框架:择时 / 择股 / 仓位 / 风控(偏主流量化与风控口径,不构成投资建议)。"""
        return [
            {
                "id": "timing_trend",
                "cat": "择时",
                "title": "趋势跟踪(双均线/海龟/通道)",
                "desc": "用指数或基准的多头排列、突破、唐奇安通道等定义风险敞口;适合情绪上行、波动可控阶段;下行周期应降杠杆或空仓。",
            },
            {
                "id": "timing_sentiment",
                "cat": "择时",
                "title": "情绪周期择时",
                "desc": "将市场赚钱效应、涨停家数、同花顺情绪指数、资金面等合成「仓位开关」;与本软件情绪周期红绿灯、同花顺勾选联动思路一致。",
            },
            {
                "id": "timing_vol",
                "cat": "择时",
                "title": "波动率择时",
                "desc": "低波动抬升风险预算、高波动压缩仓位(如目标波动率、VIX/隐波代理);震荡市常用。",
            },
            {
                "id": "timing_erp",
                "cat": "择时",
                "title": "股债性价比/ERP 择时",
                "desc": "用盈利收益率与国债收益率差值刻画股票相对债券吸引力;偏中长期资产配置,短线需配合趋势过滤。",
            },
            {
                "id": "stock_multifactor",
                "cat": "择股",
                "title": "多因子选股(价值/成长/质量)",
                "desc": "Barra/沪深300增强同类思路:盈利、估值、动量、质量、波动等因子合成得分;适合基本面分高、情绪不过热的阶段分批换仓。",
            },
            {
                "id": "stock_sector_mom",
                "cat": "择股",
                "title": "行业轮动·龙头动量",
                "desc": "强板块内选相对强度高的龙头;与「主流板块」联动,适合情绪上行且板块一致性强时。",
            },
            {
                "id": "stock_meanrev",
                "cat": "择股",
                "title": "均值回归/区间交易",
                "desc": "震荡市在布林带、RSI 超买超卖、筹码密集区做反向;需严格止损,情绪下行避免左侧重仓。",
            },
            {
                "id": "stock_div_lowvol",
                "cat": "择股",
                "title": "红利低波",
                "desc": "高股息+低波动防御组合;适合情绪下行或宏观不确定时的底仓配置思路(非短线暴利)。",
            },
            {
                "id": "stock_smallcap_rel",
                "cat": "择股",
                "title": "小盘/中证1000 相对强度",
                "desc": "用中证1000 vs 沪深300 的相对强弱刻画风格;小盘跑赢时常伴题材活跃,注意退潮日波动。",
            },
            {
                "id": "stock_northbound",
                "cat": "择股",
                "title": "北向与聪明钱(趋势化)",
                "desc": "以北向多日累计净流入、席位龙虎榜等为辅助,不做单一追涨;更适合与宽基趋势、情绪绿灯共振时筛票。",
            },
            {
                "id": "stock_consensus",
                "cat": "择股",
                "title": "一致预期·业绩兑现",
                "desc": "围绕分析师上调、预告/快报 vs 一致预期的剪刀差;财报季防利好出尽,侧重「预期差」而非纯高增长标签。",
            },
            {
                "id": "stock_etf_rotate",
                "cat": "择股",
                "title": "ETF 轮动·行业 β",
                "desc": "用行业/主题 ETF 的资金流与相对强度代替单笔个股,降低择股噪声;适合轮动快、主线不清阶段。",
            },
            {
                "id": "stock_limit_up_ladder",
                "cat": "择股",
                "title": "涨停梯队·连板接力",
                "desc": "情绪高标与连板高度反映接力意愿;仅适合短线纪律,需配合情绪周期与仓位上限,禁止无脑顶一字。",
            },
            {
                "id": "stock_event",
                "cat": "择股",
                "title": "事件驱动(重组/定增/政策窗口)",
                "desc": "按披露日历与催化时间轴布局,提前评估兑现日与博弈资金;信息不对称风险高,宜小仓位验证。",
            },
            {
                "id": "pos_kelly",
                "cat": "仓位",
                "title": "凯利/半凯利",
                "desc": "按历史胜率与盈亏比估算最优仓位;本程序有凯利设定入口,建议半凯利或带上限防止过拟合。",
            },
            {
                "id": "pos_vol_target",
                "cat": "仓位",
                "title": "目标波动率",
                "desc": "组合波动恒定:高波动减负、低波动可加;与「牌权/值搏率」结合可理解为风险预算。",
            },
            {
                "id": "pos_pyramid",
                "cat": "仓位",
                "title": "金字塔加减仓",
                "desc": "试探仓→确认加仓→趋势末端减半;适合趋势明确、情绪周期绿灯阶段。",
            },
            {
                "id": "risk_stop",
                "cat": "风控",
                "title": "止损止盈(固定%/ATR)",
                "desc": "与「是否止损」下拉一致:结合分时/日线结构破位与 ATR 倍数;单票与账户双层止损。",
            },
            {
                "id": "risk_dd",
                "cat": "风控",
                "title": "最大回撤/单日亏损熔断",
                "desc": "账户或策略净值回撤超阈值强制降仓;情绪红灯时建议同步禁止开新仓。",
            },
            {
                "id": "risk_concentration",
                "cat": "风控",
                "title": "行业与单票集中度",
                "desc": "单票、单行业、单风格上限;轮动快时防止「主流板块」过度集中。",
            },
        ]

    def _compose_quant_skill_detailed_desc(self, skill_item, snap=None, spot=None, concept_lines=None):
        """左下 Skill 详细说明:给出具体示例 + 当下配置建议 + 可在线参考资料。"""
        it = skill_item or {}
        sid = str(it.get("id") or "")
        cat = str(it.get("cat") or "")
        title = str(it.get("title") or "")
        desc = str(it.get("desc") or "")
        m = (snap or {}).get("metrics", {}) or {}
        m1 = (m.get("m1_today") or {}).get("value")
        m5 = m.get("m5_avg")
        if isinstance(m5, dict):
            m5 = m5.get("value")
        mk = m.get("m2_market") if isinstance(m.get("m2_market"), dict) else {}
        up, down = mk.get("up"), mk.get("down")
        strength = "中性"
        if isinstance(m1, (int, float)) and isinstance(m5, (int, float)):
            if m1 >= 0.6 and m5 >= 0.2:
                strength = "偏强"
            elif m1 <= -0.6 and m5 <= -0.2:
                strength = "偏弱"
        if isinstance(up, (int, float)) and isinstance(down, (int, float)) and up + down > 0:
            if up > down * 1.25:
                strength = "偏强"
            elif down > up * 1.25:
                strength = "偏弱"
        examples = {
            "timing_trend": "示例:以沪深300做20/60日均线。20上穿60且放量→开仓;20下穿60→降仓到20%以内。",
            "timing_sentiment": "示例:同花顺情绪指数>60且涨跌家数显著偏多时,执行“开仓许可“;跌破40并连弱时转防守。",
            "timing_vol": "示例:以近20日波动率为阈值,波动放大时仓位从60%降到30%,波动收敛再恢复。",
            "timing_erp": "示例:ERP高位(股债性价比改善)且指数趋势向上时逐步提高权益仓位。",
            "stock_multifactor": "示例:在同一行业内按估值+盈利质量+动量排序,选前20%做候选池。",
            "stock_sector_mom": "示例:从“主流板块“里找3日强于中证1000的龙头,回踩不破5日线分批介入。",
            "stock_meanrev": "示例:震荡市里,RSI<30且到前低支撑附近轻仓试错,反抽到压力位减仓。",
            "stock_div_lowvol": "示例:底仓优先高股息低波ETF/个股,目标是回撤小于市场而非短线弹性最大。",
            "stock_smallcap_rel": "示例:当中证1000/沪深300相对强度持续抬升时,提高小盘风格暴露。",
            "stock_northbound": "示例:北向连续净流入叠加板块共振时,优先筛选机构拥挤度可控标的。",
            "stock_consensus": "示例:财报窗口选“业绩超预期+估值未透支“标的,公告落地后评估是否兑现减仓。",
            "stock_etf_rotate": "示例:主线不清时用行业ETF轮动替代单票,按相对强弱每周调仓。",
            "stock_limit_up_ladder": "示例:仅在情绪上行周期参与,按连板梯队做分级仓位,单票止损更紧。",
            "stock_event": "示例:政策窗口/并购重组前后分两段交易,第一段博预期,第二段看兑现。",
            "pos_kelly": "示例:胜率55%、盈亏比1.5时用半凯利;若回撤放大,仓位上限再打7折。",
            "pos_vol_target": "示例:组合目标波动率10%,当前波动率升至15%则仓位按比例下调。",
            "pos_pyramid": "示例:先20%试仓,确认趋势后加到50%-70%,破位则先减半再评估。",
            "risk_stop": "示例:单票固定止损-6% + ATR止损双保险;达到止盈目标后提高跟踪止损。",
            "risk_dd": "示例:账户日内回撤超过2%暂停开新仓,超过4%执行强制降仓。",
            "risk_concentration": "示例:单票不超15%,单行业不超35%,避免主题退潮时净值同步回撤。",
        }
        config_by_cat = {
            "择时": [
                "参数建议:指数基准=沪深300/中证1000;确认周期=日线,执行周期=30/60分钟。",
                "当下配置:偏强→允许开仓并分批上仓;偏弱→仅观察仓或空仓等待修复。",
            ],
            "择股": [
                "参数建议:先板块后个股,候选池30-50只,剔除ST/流动性差标的。",
                "当下配置:偏强可偏向龙头动量,偏弱切换红利低波或ETF替代。",
            ],
            "仓位": [
                "参数建议:总仓位上限先定,再用单票上限与加减仓阶梯约束执行。",
                "当下配置:偏强参考50%-75%,中性25%-45%,偏弱0%-25%。",
            ],
            "风控": [
                "参数建议:单票止损 + 账户回撤熔断 + 行业集中度上限三层并行。",
                "当下配置:偏弱时提高止损灵敏度并缩短持仓观察周期。",
            ],
        }
        refs = {
            "择时": [
                ("BigQuant 量化择时专题", "https://bigquant.com/wiki/topic/37fa3048b9?page=4"),
                ("中证投服:量化投资策略解析", "https://www.investor.org.cn/xxzx/tjzl/tjnrgmjytx/bk/kj/202303/P020230320379381064879.pdf"),
            ],
            "择股": [
                ("S&P:因子策略在中国A股市场表现", "https://www.spglobal.com/spdji/zh/documents/research/research-examining-factor-strategies-in-china-a-share-market-cn.pdf"),
                ("聚宽:盈利小市值周轮动策略", "https://www.joinquant.com/post/35abf0613a18d199edd58b2101b67dd5"),
            ],
            "仓位": [
                ("动态仓位案例研究", "https://www.myinvestpilot.com/docs/primitives/advanced/dynamic-position-strategy"),
                ("宏观策略框架(仓位管理章节)", "https://pdf.dfcfw.com/pdf/H301_AP202601211818192761_1.pdf"),
            ],
            "风控": [
                ("策略回测与止损配置实践", "https://cloud.tencent.com/developer/article/2635337"),
                ("A股量化风控通用方法(检索关键词)", "https://bigquant.com/wiki/topic/37fa3048b9?page=4"),
            ],
        }
        lines = [
            f"【{cat}】{title}",
            "",
            "一、策略定义",
            desc or "(无)",
            "",
            "二、A股实战例子",
            examples.get(sid, f"示例:按「{title}」在A股执行时,先小仓位验证,再根据趋势与回撤动态调整。"),
            "",
            "三、当下如何配置(结合当前盘面)",
            f"当前盘面判定:{strength}  (m1={m1},m5均值={m5},涨跌家数={up}/{down})",
        ]
        lines.extend(config_by_cat.get(cat, ["参数建议:先定义进出场与仓位上限,再执行。"]))
        lines.extend(
            [
                "",
                "四、可在线参考资料(同类策略)",
            ]
        )
        for idx, (nm, url) in enumerate(refs.get(cat, []), 1):
            lines.append(f"{idx}. {nm}:{url}")
        lines.extend(
            [
                "",
                "检索关键词建议:A股 量化 " + cat + " " + title + " 实盘/回测/风控",
                "",
                "(以上为策略研究与配置参考,不构成投资建议。)",
            ]
        )
        return "\n".join(lines)

    def _recommend_quant_strategies(self):
        """据当前情绪与三维分等给出择时/择股/仓位/风控的文字建议(规则化,可对照左侧 Skill)。"""
        try:
            cycle = self.emotion_cycle_var.get()
        except Exception:
            cycle = "震荡"
        try:
            ths = self.ths_sentiment_trend_var.get()
        except Exception:
            ths = "震荡"
        try:
            f, t, s = int(self.fundamental_var.get()), int(self.technical_var.get()), int(self.sentiment_var.get())
        except Exception:
            f, t, s = 20, 20, 20
        tot = f + t + s
        try:
            conf_ok = self.sentiment_index_ma1_uptrend_var.get() and self.sentiment_index_ma1_above_var.get()
        except Exception:
            conf_ok = False
        try:
            new_ok = self.new_position_var.get() == "可以开新仓"
        except Exception:
            new_ok = False
        parts = []
        parts.append("══ 与当前状态匹配度较高的量化组合(规则摘要)══\n")
        # 择时
        if cycle == "下行" or ths == "下行":
            parts.append("【择时】防守/空仓窗口:趋势策略关闭或极低仓位;以波动率与 ERP 监控为主,等待情绪周期修复。")
        elif cycle == "上行" and conf_ok:
            parts.append("【择时】趋势/情绪共振:可对照「趋势跟踪」「情绪周期择时」提高风险敞口;仍以破位为出场信号。")
        else:
            parts.append("【择时】震荡/过渡:侧重「波动率择时」与区间工具,避免单边满仓;可小步试错。")
        # 择股
        if cycle == "下行" or tot < 45:
            parts.append("【择股】防御:红利低波、质量因子为主;减少题材追高与小盘纯动量。")
        elif tot >= 65 and f >= t and f >= s:
            parts.append("【择股】基本面驱动:多因子偏价值/质量,叠加财报与行业景气过滤。")
        elif tot >= 65 and (t >= f or s >= f):
            parts.append("【择股】动量/龙头:行业轮动+相对强度;对齐当前「主流板块」。")
        else:
            parts.append("【择股】均衡:多因子打底,少量动量增强;控制单票波动。")
        # 仓位
        if not new_ok or cycle == "下行":
            parts.append("【仓位】禁开新仓或仅试错仓:凯利/目标波动率输出应贴近下限;金字塔只减仓不加。")
        elif cycle == "上行" and conf_ok:
            parts.append("【仓位】可阶梯加仓:半凯利或目标波动率约束内,用金字塔确认趋势。")
        else:
            parts.append("【仓位】中性风险预算:牌权/值搏率与仓位演算一致,避免情绪面单日打满。")
        # 风控
        parts.append("【风控】严格执行界面「是否止损」规则;下行周期叠加账户回撤熔断与行业集中度上限。")
        if not conf_ok and cycle != "下行":
            parts.append("(补充)同花顺 1 日线条件未齐:量化上视为「趋势未确认」,择时信号应降档。")
        parts.append("\n左侧点选具体 Skill 可查看适用场景与实现要点。")
        return "\n".join(parts)

    def _quant_board_structure_lines(self, snap, spot):
        """对比上证/创业板/沪深300/中证500/科创50 等强弱(东财即时为主,情绪快照问财三指为辅)。"""
        lines = ["══ 2 指数强弱与风格(上证 vs 中证 vs 创业板 等)══"]
        merged = {}
        if spot:
            for k in (
                "上证指数",
                "深证成指",
                "创业板指",
                "沪深300",
                "中证500",
                "科创50",
                "中证1000",
                "北证50",
            ):
                if k in spot and isinstance(spot[k], (int, float)):
                    merged[k] = float(spot[k])
        m = (snap or {}).get("metrics") or {}
        for label, key in (
            ("沪深300(情绪区·问财)", "m5_hs300"),
            ("中证500(情绪区·问财)", "m5_zz500"),
            ("科创30(情绪区·问财名)", "m5_kc30"),
        ):
            o = m.get(key) or {}
            v = o.get("value")
            if isinstance(v, (int, float)):
                merged[label] = float(v)
        if not merged:
            lines.append("(暂无指数涨跌幅,请检查网络或 AKShare)")
            return lines
        items = sorted(merged.items(), key=lambda x: x[1], reverse=True)
        lines.append("排序(涨幅高→低):")
        lines.append("  " + " · ".join(f"{a} {b:+.2f}%" for a, b in items))
        hi, lo = items[0], items[-1]
        lines.append(f"今日相对最强:{hi[0]}({hi[1]:+.2f}%);最弱:{lo[0]}({lo[1]:+.2f}%)。")
        sh = merged.get("上证指数")
        cyb = merged.get("创业板指")
        zz5 = merged.get("中证500")
        hs3 = merged.get("沪深300")
        kc = merged.get("科创50")
        if isinstance(sh, float) and isinstance(cyb, float):
            if cyb > sh + 0.25:
                lines.append("风格:创业板指明显强于上证 → 偏成长/赛道弹性、小票情绪往往更活跃。")
            elif sh > cyb + 0.25:
                lines.append("风格:上证强于创业板 → 偏蓝筹/权重、大盘与价值风格相对占优。")
            else:
                lines.append("风格:上证与创业板接近 → 大小盘分化不大或同涨同跌。")
        if isinstance(zz5, float) and isinstance(hs3, float) and zz5 > hs3 + 0.2:
            lines.append("中证500 相对 沪深300 更强 → 中盘/主题弹性可能优于大盘权重。")
        if isinstance(kc, float) and isinstance(sh, float) and kc > sh + 0.35:
            lines.append("科创50 显著强于上证 → 硬科技/科创板情绪偏热。")
        lines.append("(补充:可与右上「情绪区间」问5 的沪深300/中证500/科创30 对照。)")
        return lines

    def _quant_market_network_sources_header(self):
        """量化弹窗右侧:大盘情绪所用网络数据源说明(便于对照实盘)。"""
        return [
            "┏━━━━━━━━ 量化参考 · 大盘情绪(以下为即时网络拉取,非界面缓存) ━━━━━━━━┓",
            "【数据获取源(优先级)】",
            "  · 主要指数涨跌幅 → Tushare Pro `index_daily`(已配置 token 时优先);缺项再用东财现货 · AKShare `stock_zh_index_spot_em`",
            "  · 全 A 涨跌家数 → AKShare `stock_zh_a_spot_em`;失败则 Tushare `daily` 按最近交易日统计",
            "  · 情绪五问中宽基/涨跌家数 → 问财 `pywencai` + 上述 Tushare 自动补缺",
            "  · 同花顺情绪指数、问财技术条件家数 → `pywencai`(需 Node);情绪指数还可回退 Tushare/AKShare 日线",
            "  · 题材/概念热度 → 同花顺概念 · AKShare `stock_board_concept_name_ths`;失败则选股通主题库网页解析",
            "(本地仅「仓位」标签与 Skill 建议取自主界面变量;其余大盘字段均以本次联网结果为准。)",
            "",
        ]

    def _collect_quant_market_from_network(self):
        """量化弹窗专用:统一从网络采集大盘情绪相关数据(供右侧全文)。"""
        bundle = {"snap": None, "spot": {}, "concept_lines": [], "errors": []}
        try:
            bundle["snap"] = self._collect_sentiment_zone_snapshot()
        except Exception as e:
            bundle["errors"].append(f"情绪区间/问财快照: {e}")
        try:
            bundle["spot"] = self._get_major_index_pct_dict() or {}
        except Exception as e:
            bundle["errors"].append(f"主要指数涨跌幅: {e}")
        try:
            cl, _ = self._fetch_concept_board_leader_summary(18)
            bundle["concept_lines"] = cl or []
        except Exception as e:
            bundle["concept_lines"] = [f"(概念板块获取失败:{e})"]
            bundle["errors"].append(f"概念板块: {e}")
        return bundle

    def _resolve_latest_price_for_ma(self, stock_code, closes_list):
        """与 _check_ma_status 一致:优先 Tushare 实时/当日日K 收盘,否则取 closes_list 最后一根。"""
        if not closes_list:
            return None
        try:
            closes_list = [float(x) for x in closes_list]
        except Exception:
            return None
        realtime_price = None
        try:
            if TS_AVAILABLE and (self.ts_token or TS_DEFAULT_TOKEN):
                import tushare as ts
                ts_token = self.ts_token or TS_DEFAULT_TOKEN
                os.environ["TUSHARE_TOKEN"] = ts_token
                ts_code = self._format_ts_code(stock_code)
                try:
                    df = ts.realtime_quote(ts_code=ts_code, src='dc')
                    if df is not None and not df.empty and 'price' in df.columns:
                        realtime_price = float(df.iloc[0]['price'])
                        if not (0.01 < realtime_price < 10000):
                            realtime_price = None
                except Exception:
                    pass
                if realtime_price is None:
                    pass  # 跳过 daily fallback, 实时失败用其他渠道
        except Exception:
            pass
        if realtime_price and realtime_price > 0:
            return float(realtime_price)
        try:
            code = str(stock_code).zfill(6)
            spot = self._get_realtime_spot_row_for_holding(code, cache_duration=30)
            if spot and spot.get('最新价') is not None:
                p = float(spot['最新价'])
                if p > 0.01:
                    return p
        except Exception:
            pass
        return float(closes_list[-1])

    def _signal_stock_recent_stats_for_log(self, stock_code):
        """信号检测日志:近30个交易日涨停次数、30日日均涨跌幅、5/10/20日累计涨跌幅。
        返回可贴在日志后的短文本;失败返回空串。"""
        try:
            code = str(stock_code).strip().zfill(6)
            if not code:
                return ""
            result = self._fetch_recent_daily_closes(
                code, days=55, source="default", token=self.ts_token, return_volume=False
            )
            if isinstance(result, tuple) and len(result) >= 2:
                closes = result[1]
            else:
                closes = result if isinstance(result, list) else []
            if not closes or len(closes) < 6:
                return ""
            closes = [float(x) for x in closes]
            n = len(closes)
            lim_thr = self._a_share_limit_up_threshold_pct(code)
            # 最近30个交易日:31根收盘 → 30个日涨跌幅
            want = min(31, n)
            seg = closes[-want:]
            daily_pcts = []
            for i in range(1, len(seg)):
                p0, p1 = seg[i - 1], seg[i]
                if p0 <= 0:
                    continue
                daily_pcts.append((p1 - p0) / p0 * 100.0)
            if len(daily_pcts) > 30:
                daily_pcts = daily_pcts[-30:]
            zt_count = sum(1 for pc in daily_pcts if pc >= lim_thr - 0.05)
            avg_pct = sum(daily_pcts) / len(daily_pcts) if daily_pcts else None
            def span_ret(ndays):
                if n < ndays + 1:
                    return None
                a, b = closes[-ndays - 1], closes[-1]
                if a <= 0:
                    return None
                return (b - a) / a * 100.0
            r5 = span_ret(5)
            r10 = span_ret(10)
            r20 = span_ret(20)
            parts = [f"30日涨停{zt_count}次"]
            if avg_pct is not None:
                parts.append(f"30日日均{avg_pct:+.2f}%")
            if r5 is not None:
                parts.append(f"5日{r5:+.2f}%")
            if r10 is not None:
                parts.append(f"10日{r10:+.2f}%")
            if r20 is not None:
                parts.append(f"20日{r20:+.2f}%")
            return " ".join(parts)
        except Exception as e:
            print(f"[信号统计] {stock_code}: {e}")
            return ""

    def save_stock_data_to_db(self):
        """保存股票数据到数据库(从左边文本分析识别出来的股票)"""
        try:
            # 获取左边文本框的所有文本内容
            all_texts = self.get_all_texts()
            if not all_texts:
                messagebox.showwarning("警告", "左边文本框没有内容,请先输入或导入文本")
                return
            # 合并所有标签页的文本
            combined_text = "\n\n".join([item['text'] for item in all_texts])
            if not combined_text.strip():
                messagebox.showwarning("警告", "左边文本框内容为空")
                return
            # 从文本中提取股票信息
            stock_names, _ = extract_stock_names(combined_text)
            if not stock_names:
                messagebox.showwarning("警告", "未识别出股票信息,请确保文本中包含股票名称或代码")
                return
            # 提取每只股票的逻辑
            stock_data = []
            current_date = datetime.now().strftime('%Y-%m-%d')
            for stock_name in stock_names:
                # 提取股票逻辑
                logic = get_stock_logic(combined_text, stock_name)
                if not logic or logic == "未找到明确逻辑":
                    # 尝试从上下文中提取
                    context = extract_stock_context(combined_text, [stock_name])
                    contexts = context.get(stock_name, [])
                    if contexts and contexts[0] != "未找到相关内容":
                        logic = contexts[0][:500]  # 限制长度
                    else:
                        logic = "无详细逻辑"
                # 清理股票名称(去除代码部分)
                clean_name = stock_name
                if '(' in stock_name and ')' in stock_name:
                    # 提取股票名称部分
                    clean_name = stock_name.split('(')[0].strip()
                stock_data.append({
                    'name': clean_name,
                    'logic': logic,
                    'date': current_date,
                    'source': '文本分析'
                })
            if not stock_data:
                messagebox.showwarning("警告", "未提取到股票数据")
                return
            # 显示保存对话框
            save_window = self._safe_toplevel(self.root)
            save_window.title("保存股票数据到数据库")
            save_window.geometry("700x500")
            # 创建表格显示要保存的数据
            tree_frame = ttk.Frame(save_window)
            tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            # 创建Treeview
            columns = ("股票名称", "逻辑", "日期", "来源")
            tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
            for col in columns:
                tree.heading(col, text=col)
                if col == "逻辑":
                    tree.column(col, width=300)
                else:
                    tree.column(col, width=120)
            # 填充数据
            for stock in stock_data:
                logic_text = stock['logic'][:100] + '...' if len(stock['logic']) > 100 else stock['logic']
                tree.insert("", tk.END, values=(
                    stock['name'],
                    logic_text,
                    stock['date'],
                    stock['source']
                ))
            # 滚动条
            scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            # 翻译功能(参照translator_gui.py)
            translation_engines = {
                "百度翻译": {
                    "api_url": "https://fanyi-api.baidu.com/api/trans/vip/translate",
                    "app_id": "20191105000352960",
                    "app_key": "ZKPLQb3WUi1NJ0TnhcZN"
                },
                "有道翻译": {
                    "api_url": "https://openapi.youdao.com/api",
                    "app_id": "3d7d5287500ee1ef",
                    "app_key": "U4uLG6Ar04XzVj8ajJ3JTkW74QcRWcC7"
                }
            }
            languages = {
                "中文": "zh",
                "英语": "en",
                "日语": "ja",
                "韩语": "ko",
                "法语": "fr",
                "德语": "de",
                "西班牙语": "es",
                "俄语": "ru"
            }
            def translate_text(text, source_lang="zh", target_lang="en", engine="百度翻译"):
                """翻译文本"""
                try:
                    import hashlib
                    import random
                    if not text or not text.strip() or text == "无详细逻辑":
                        return text
                    if engine == "百度翻译":
                        config = translation_engines["百度翻译"]
                        app_id = config["app_id"]
                        app_key = config["app_key"]
                        api_url = config["api_url"]
                        salt = random.randint(32768, 65536)
                        sign = app_id + text + str(salt) + app_key
                        sign = hashlib.md5(sign.encode()).hexdigest()
                        params = {
                            'q': text,
                            'from': source_lang,
                            'to': target_lang,
                            'appid': app_id,
                            'salt': salt,
                            'sign': sign
                        }
                        response = requests.get(api_url, params=params, timeout=10)
                        result = response.json()
                        if 'trans_result' in result:
                            return result['trans_result'][0]['dst']
                        else:
                            return f"翻译失败: {result.get('error_msg', '未知错误')}"
                    elif engine == "有道翻译":
                        config = translation_engines["有道翻译"]
                        app_id = config["app_id"]
                        app_key = config["app_key"]
                        api_url = config["api_url"]
                        salt = str(random.randint(10000, 99999))
                        sign_str = app_id + text + salt + app_key
                        sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
                        params = {
                            'q': text,
                            'from': source_lang,
                            'to': target_lang,
                            'appKey': app_id,
                            'salt': salt,
                            'sign': sign
                        }
                        response = requests.post(api_url, data=params, timeout=10)
                        result = response.json()
                        if 'translation' in result:
                            return result['translation'][0]
                        else:
                            return f"翻译失败: {result.get('errorMessage', '未知错误')}"
                    else:
                        return "不支持的翻译引擎"
                except Exception as e:
                    return f"翻译失败: {e!s}"
            # 翻译选项框架
            translate_frame = ttk.LabelFrame(save_window, text="翻译选项", padding=10)
            translate_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            translate_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(translate_frame, text="启用翻译", variable=translate_var).pack(side=tk.LEFT, padx=5)
            ttk.Label(translate_frame, text="翻译引擎:").pack(side=tk.LEFT, padx=(20, 5))
            engine_var = tk.StringVar(value="百度翻译")
            engine_combo = ttk.Combobox(translate_frame, textvariable=engine_var,
                                       values=list(translation_engines.keys()), width=12, state="readonly")
            engine_combo.pack(side=tk.LEFT, padx=5)
            ttk.Label(translate_frame, text="目标语言:").pack(side=tk.LEFT, padx=(20, 5))
            target_lang_var = tk.StringVar(value="英语")
            target_lang_combo = ttk.Combobox(translate_frame, textvariable=target_lang_var,
                                           values=list(languages.keys()), width=12, state="readonly")
            target_lang_combo.pack(side=tk.LEFT, padx=5)
            # 保存按钮
            def save_to_db():
                try:
                    saved_count = 0
                    translate_count = 0
                    need_translate = translate_var.get()
                    engine = engine_var.get()
                    target_lang = languages.get(target_lang_var.get(), "en")
                    for stock in stock_data:
                        # 先翻译股票逻辑(如果需要)
                        combined_logic = stock['logic']
                        if need_translate and stock['logic'] and stock['logic'] != "无详细逻辑":
                            try:
                                translated_logic = translate_text(stock['logic'], "zh", target_lang, engine)
                                if translated_logic and not translated_logic.startswith("翻译失败"):
                                    # 追加翻译到原逻辑后面
                                    combined_logic = f"{stock['logic']}\n\n[{target_lang_var.get()}翻译]\n{translated_logic}"
                                    translate_count += 1
                            except Exception as e:
                                print(f"翻译股票 {stock['name']} 的逻辑失败: {e}")
                        # 保存数据(包含翻译后的逻辑)
                        if save_stock_logic_to_db(
                            stock_name=stock['name'],
                            logic=combined_logic,
                            date=stock['date'],
                            source=stock['source']
                        ):
                            saved_count += 1
                    message = f"成功保存 {saved_count} 条股票数据到数据库"
                    if translate_count > 0:
                        message += f"\n成功翻译 {translate_count} 条股票逻辑"
                    messagebox.showinfo("成功", message)
                    save_window.destroy()
                except Exception as e:
                    messagebox.showerror("错误", f"保存失败: {e}")
            button_frame = ttk.Frame(save_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)
            ttk.Button(button_frame, text="直接保存", command=lambda: save_to_db_with_translate(False)).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="保存并翻译", command=lambda: save_to_db_with_translate(True)).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="取消", command=save_window.destroy).pack(side=tk.LEFT, padx=5)
            def save_to_db_with_translate(use_translate):
                """保存到数据库,根据参数决定是否翻译"""
                translate_var.set(use_translate)
                save_to_db()
        except Exception as e:
            messagebox.showerror("错误", f"保存股票数据失败: {e}")

    def _clean_logic_text(self, text):
        """清理逻辑文本,去除垃圾文字
        Args:
            text: 原始文本
        Returns:
            str: 清理后的文本
        """
        if not text:
            return ""
        # 去除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 去除URL
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        # 去除特殊字符和多余空格
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9,。!?、;:\s]', '', text)
        text = re.sub(r'\s+', ' ', text)
        # 去除过短的句子(可能是垃圾文字)
        sentences = re.split(r'[。!?\n]', text)
        clean_sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        return '。'.join(clean_sentences)

    def _deduplicate_logic(self, logic_list):
        """对逻辑列表进行去重
        Args:
            logic_list: 逻辑文本列表
        Returns:
            list: 去重后的逻辑列表
        """
        if not logic_list:
            return []
        seen = set()
        deduplicated = []
        for logic in logic_list:
            # 清理并标准化文本用于比较
            clean_logic = self._clean_logic_text(logic)
            if not clean_logic:
                continue
            # 使用前50个字符作为唯一性判断(避免完全相同的内容)
            signature = clean_logic[:50]
            if signature not in seen:
                seen.add(signature)
                deduplicated.append(clean_logic)
        return deduplicated

    def _perform_batch_stock_logic_query(self, stock_list, parent_window):
        """执行批量股票逻辑查询
        Args:
            stock_list: 股票名称列表
            parent_window: 父窗口
        """
        # 创建结果显示窗口
        result_window = self._toplevel(parent_window)
        result_window.title("股票批量逻辑查询结果")
        result_window.geometry("1200x800")
        result_window.transient(parent_window)
        # 主框架
        main_frame = ttk.Frame(result_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # 工具栏
        toolbar_frame = ttk.Frame(main_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 10))
        # 状态标签
        status_label = ttk.Label(toolbar_frame, text=f"共 {len(stock_list)} 只股票,正在查询...", font=("TkDefaultFont", 12))
        status_label.pack(side=tk.LEFT, padx=5)
        # 结果显示区域
        result_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=("TkDefaultFont", 12))
        result_text.pack(fill=tk.BOTH, expand=True)
        # 保存按钮框架
        save_frame = ttk.Frame(main_frame)
        save_frame.pack(fill=tk.X, pady=(10, 0))
        # 存储所有查询结果
        all_results = []
        current_stock_index = [0]  # 使用列表以便在嵌套函数中修改
        def save_to_news():
            """保存结果到资讯"""
            if not all_results:
                messagebox.showwarning("警告", "没有可保存的结果", parent=result_window)
                return
            try:
                # 生成报告文本
                report_text = "股票批量逻辑查询报告\n"
                report_text += f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report_text += f"查询股票数量: {len(stock_list)}\n"
                report_text += "=" * 80 + "\n\n"
                for result in all_results:
                    stock_name = result['stock_name']
                    stock_code = result.get('stock_code', '')
                    matches = result['matches']
                    price_data = result.get('price_data', {})
                    report_text += f"\n【{stock_name}】"
                    if stock_code:
                        report_text += f" ({stock_code})"
                    report_text += "\n"
                    report_text += "-" * 80 + "\n"
                    # 显示价格数据
                    price_info = []
                    if price_data.get('change_pct') is not None:
                        price_info.append(f"最近涨跌幅: {price_data['change_pct']:+.2f}%")
                    if price_data.get('low5_diff_pct') is not None:
                        price_info.append(f"5日最低点差值: {price_data['low5_diff_pct']:+.2f}%")
                    if price_data.get('ma5_diff_pct') is not None:
                        price_info.append(f"5日均线差值: {price_data['ma5_diff_pct']:+.2f}%")
                    if price_data.get('ma10_diff_pct') is not None:
                        price_info.append(f"10日均线差值: {price_data['ma10_diff_pct']:+.2f}%")
                    if price_info:
                        report_text += " | ".join(price_info) + "\n"
                        report_text += "-" * 80 + "\n"
                    if matches:
                        report_text += f"找到 {len(matches)} 条去重后的逻辑:\n\n"
                        for idx, match in enumerate(matches, 1):
                            report_text += f"\n逻辑 {idx}:\n"
                            report_text += f"来源: {match['tab_name']}\n"
                            report_text += f"时间: {match['time']}\n"
                            report_text += f"逻辑内容:\n{match.get('logic', match.get('content_preview', ''))}\n"
                            report_text += "\n"
                    else:
                        report_text += "未找到相关逻辑\n"
                    report_text += "\n" + "=" * 80 + "\n"
                # 保存到资讯数据库
                tab_name = f"股票批量逻辑查询_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                if save_news_info_to_db(tab_name, report_text):
                    messagebox.showinfo("成功", f"查询结果已保存到资讯数据库: {tab_name}", parent=result_window)
                else:
                    messagebox.showerror("错误", "保存到资讯数据库失败", parent=result_window)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=result_window)
        def save_to_txt():
            """保存结果为txt文件"""
            if not all_results:
                messagebox.showwarning("警告", "没有可保存的结果", parent=result_window)
                return
            try:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                    initialfile=f"股票批量逻辑查询_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                )
                if filename:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(result_text.get("1.0", tk.END))
                    messagebox.showinfo("成功", f"已保存到: {filename}", parent=result_window)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=result_window)
        def save_to_excel():
            """保存结果为Excel文件"""
            if not all_results:
                messagebox.showwarning("警告", "没有可保存的结果", parent=result_window)
                return
            try:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".xlsx",
                    filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")],
                    initialfile=f"股票批量逻辑查询_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                )
                if filename:
                    import xlsxwriter
                    workbook = xlsxwriter.Workbook(filename)
                    worksheet = workbook.add_worksheet()
                    # 设置标题格式
                    header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3'})
                    # 写入标题
                    worksheet.write(0, 0, "股票名称", header_format)
                    worksheet.write(0, 1, "股票代码", header_format)
                    worksheet.write(0, 2, "最近涨跌幅%", header_format)
                    worksheet.write(0, 3, "5日最低点差值%", header_format)
                    worksheet.write(0, 4, "5日均线差值%", header_format)
                    worksheet.write(0, 5, "10日均线差值%", header_format)
                    worksheet.write(0, 6, "序号", header_format)
                    worksheet.write(0, 7, "来源", header_format)
                    worksheet.write(0, 8, "时间", header_format)
                    worksheet.write(0, 9, "逻辑内容", header_format)
                    row = 1
                    for result in all_results:
                        stock_name = result['stock_name']
                        stock_code = result.get('stock_code', '')
                        matches = result['matches']
                        price_data = result.get('price_data', {})
                        if matches:
                            for idx, match in enumerate(matches, 1):
                                worksheet.write(row, 0, stock_name)
                                worksheet.write(row, 1, stock_code)
                                worksheet.write(row, 2, price_data.get('change_pct', ''))
                                worksheet.write(row, 3, price_data.get('low5_diff_pct', ''))
                                worksheet.write(row, 4, price_data.get('ma5_diff_pct', ''))
                                worksheet.write(row, 5, price_data.get('ma10_diff_pct', ''))
                                worksheet.write(row, 6, idx)
                                worksheet.write(row, 7, match['tab_name'])
                                worksheet.write(row, 8, match['time'])
                                worksheet.write(row, 9, match.get('logic', match.get('content_preview', '')))
                                row += 1
                        else:
                            worksheet.write(row, 0, stock_name)
                            worksheet.write(row, 1, stock_code)
                            worksheet.write(row, 2, price_data.get('change_pct', ''))
                            worksheet.write(row, 3, price_data.get('low5_diff_pct', ''))
                            worksheet.write(row, 4, price_data.get('ma5_diff_pct', ''))
                            worksheet.write(row, 5, price_data.get('ma10_diff_pct', ''))
                            worksheet.write(row, 6, "无")
                            worksheet.write(row, 7, "未找到相关逻辑")
                            row += 1
                    workbook.close()
                    messagebox.showinfo("成功", f"已保存到: {filename}", parent=result_window)
            except ImportError:
                messagebox.showerror("错误", "需要安装 xlsxwriter 库: pip install xlsxwriter", parent=result_window)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=result_window)
        def save_to_image():
            """保存结果为图片"""
            if not all_results:
                messagebox.showwarning("警告", "没有可保存的结果", parent=result_window)
                return
            try:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    filetypes=[("图片文件", "*.png"), ("所有文件", "*.*")],
                    initialfile=f"股票批量逻辑查询_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                )
                if filename:
                    # 获取文本内容
                    text_content = result_text.get("1.0", tk.END)
                    # 使用PIL创建图片
                    import textwrap

                    from PIL import Image, ImageDraw, ImageFont
                    # 尝试加载中文字体
                    try:
                        font = ImageFont.truetype("simhei.ttf", 16)
                    except:
                        try:
                            font = ImageFont.truetype("msyh.ttc", 16)
                        except:
                            font = ImageFont.load_default()
                    # 计算文本尺寸
                    lines = text_content.split('\n')
                    max_width = 1200
                    wrapped_lines = []
                    for line in lines:
                        wrapped_lines.extend(textwrap.wrap(line, width=100))
                    line_height = 25
                    img_height = len(wrapped_lines) * line_height + 100
                    img = Image.new('RGB', (max_width, img_height), 'white')
                    draw = ImageDraw.Draw(img)
                    # 绘制文本
                    y = 20
                    for line in wrapped_lines:
                        draw.text((20, y), line, fill='black', font=font)
                        y += line_height
                    img.save(filename)
                    messagebox.showinfo("成功", f"已保存到: {filename}", parent=result_window)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=result_window)
        def copy_screenshot():
            """截图并复制到剪贴板"""
            try:
                # 获取窗口截图
                result_window.update()
                x = result_window.winfo_rootx()
                y = result_window.winfo_rooty()
                width = result_window.winfo_width()
                height = result_window.winfo_height()
                # 使用PIL截图
                from PIL import ImageGrab
                screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
                # 复制到剪贴板
                try:
                    from io import BytesIO

                    import win32clipboard
                    output = BytesIO()
                    screenshot.save(output, 'BMP')
                    data = output.getvalue()[14:]  # 跳过BMP头
                    output.close()
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                    win32clipboard.CloseClipboard()
                    messagebox.showinfo("成功", "截图已复制到剪贴板", parent=result_window)
                except ImportError:
                    messagebox.showerror("错误", "需要安装 pywin32 库: pip install pywin32", parent=result_window)
            except Exception as e:
                messagebox.showerror("错误", f"截图失败: {e}", parent=result_window)
        # 保存按钮
        ttk.Button(save_frame, text="保存到资讯", command=save_to_news, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(save_frame, text="保存为TXT", command=save_to_txt, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(save_frame, text="保存为Excel", command=save_to_excel, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(save_frame, text="保存为图片", command=save_to_image, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(save_frame, text="截图复制", command=copy_screenshot, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(save_frame, text="关闭", command=result_window.destroy, width=12).pack(side=tk.RIGHT, padx=5)
        # 查询函数
        def query_next_stock():
            """查询下一只股票"""
            if current_stock_index[0] >= len(stock_list):
                # 查询完成
                status_label.config(text=f"查询完成!共 {len(stock_list)} 只股票")
                return
            stock_name = stock_list[current_stock_index[0]]
            current_stock_index[0] += 1
            # 更新状态
            status_label.config(text=f"正在查询: {stock_name} ({current_stock_index[0]}/{len(stock_list)})")
            result_window.update()
            try:
                # 获取股票代码
                stock_code = get_stock_code_by_name(stock_name)
                # 获取价格数据
                price_data = self._get_stock_price_data(stock_name, stock_code)
                # 查询资讯表
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, tab_name, content, created_at, updated_at
                    FROM news_info
                    WHERE content LIKE ?
                    ORDER BY created_at DESC
                    LIMIT 50
                ''', (f'%{stock_name}%',))
                rows = cursor.fetchall()
                conn.close()
                # 提取逻辑并去重
                all_logic_texts = []
                for row in rows:
                    news_id, tab_name, content, created_at, updated_at = row
                    # 提取股票逻辑
                    logic = get_stock_logic(content, stock_name)
                    if logic and logic != "未找到明确逻辑":
                        # 清理垃圾文字
                        clean_logic = self._clean_logic_text(logic)
                        if clean_logic:
                            all_logic_texts.append({
                                'news_id': news_id,
                                'tab_name': tab_name,
                                'time': updated_at or created_at,
                                'logic': clean_logic,
                                'original_content': content[:200] + '...' if len(content) > 200 else content
                            })
                # 去重逻辑
                self._deduplicate_logic([item['logic'] for item in all_logic_texts])
                # 构建去重后的匹配结果(保留前10条)
                matches = []
                seen_logics = set()
                for item in all_logic_texts:
                    if len(matches) >= 10:
                        break
                    logic_signature = item['logic'][:50]
                    if logic_signature not in seen_logics:
                        seen_logics.add(logic_signature)
                        matches.append({
                            'news_id': item['news_id'],
                            'tab_name': item['tab_name'],
                            'time': item['time'],
                            'logic': item['logic'],
                            'content_preview': item['original_content']
                        })
                # 保存结果
                all_results.append({
                    'stock_name': stock_name,
                    'stock_code': stock_code,
                    'matches': matches,
                    'price_data': price_data
                })
                # 实时显示结果
                def update_display():
                    result_text.insert(tk.END, f"\n{'='*80}\n")
                    result_text.insert(tk.END, f"【{stock_name}】")
                    if stock_code:
                        result_text.insert(tk.END, f" ({stock_code})")
                    result_text.insert(tk.END, "\n")
                    result_text.insert(tk.END, f"{'-'*80}\n")
                    # 显示价格数据
                    price_info = []
                    if price_data.get('change_pct') is not None:
                        price_info.append(f"最近涨跌幅: {price_data['change_pct']:+.2f}%")
                    if price_data.get('low5_diff_pct') is not None:
                        price_info.append(f"5日最低点差值: {price_data['low5_diff_pct']:+.2f}%")
                    if price_data.get('ma5_diff_pct') is not None:
                        price_info.append(f"5日均线差值: {price_data['ma5_diff_pct']:+.2f}%")
                    if price_data.get('ma10_diff_pct') is not None:
                        price_info.append(f"10日均线差值: {price_data['ma10_diff_pct']:+.2f}%")
                    if price_info:
                        result_text.insert(tk.END, " | ".join(price_info) + "\n")
                        result_text.insert(tk.END, f"{'-'*80}\n")
                    if matches:
                        result_text.insert(tk.END, f"找到 {len(matches)} 条去重后的逻辑:\n\n")
                        for idx, match in enumerate(matches, 1):
                            result_text.insert(tk.END, f"逻辑 {idx}:\n")
                            result_text.insert(tk.END, f"来源: {match['tab_name']}\n")
                            result_text.insert(tk.END, f"时间: {match['time']}\n")
                            result_text.insert(tk.END, f"逻辑内容:\n{match['logic']}\n")
                            result_text.insert(tk.END, "\n")
                    else:
                        result_text.insert(tk.END, "未找到相关逻辑\n")
                    result_text.see(tk.END)  # 滚动到底部
                    result_window.update()
                    # 继续查询下一只股票
                    result_window.after(100, query_next_stock)
                result_window.after(0, update_display)
            except Exception as e:
                print(f"查询股票 {stock_name} 失败: {e}")
                # 即使失败也继续查询下一只
                result_window.after(100, query_next_stock)
        # 开始查询
        result_window.after(100, query_next_stock)

    def _signal_tab_label_for_group(self, group_index):
        """信号检测日志里显示的标签页名称。"""
        names = {1: "持仓", 2: "龙头股", 3: "15Min", 4: "Main", 5: "持仓历史股", 6: "同花顺"}
        if group_index in names:
            return names[group_index]
        if 7 <= group_index <= 14:
            try:
                tab_names = self.ai_config_manager.config.get("holding_tab_names", {})
                return str(tab_names.get(str(group_index), f"持仓{group_index - 6}"))
            except Exception:
                return f"持仓{group_index - 6}"
        return f"组{group_index}"

    def _signal_clean_stock_display_name(self, stock_name):
        """信号侧栏用:去掉「持仓」及括号内代码,匹配咨询库股票名。"""
        if not stock_name:
            return ""
        s = str(stock_name).replace("持仓", "").strip()
        if "(" in s and ")" in s:
            left = s.split("(")[0].strip()
            if left:
                s = left
        return s

    def _signal_stock_sidebar_text(self, stock_name, stock_code):
        """板块/概念 + 咨询库基本面(stock_logic),供信号窗右侧展示。"""
        lines = []
        name_clean = self._signal_clean_stock_display_name(stock_name)
        code = str(stock_code or "").strip().zfill(6)
        lines.append(f"【{name_clean or '-'}】 {code}")
        # 行业(板块)
        sec = "-"
        try:
            if not hasattr(self, "_signal_sector_cache"):
                self._signal_sector_cache = {}
            ckey = code if code.isdigit() else name_clean
            if ckey and ckey in self._signal_sector_cache:
                sec = self._signal_sector_cache[ckey]
            elif name_clean and AKSHARE_AVAILABLE:
                sec = get_stock_sector(name_clean) or "-"
                if ckey:
                    self._signal_sector_cache[ckey] = sec
        except Exception:
            sec = "获取失败"
        lines.append(f"板块/行业:{sec}")
        # 概念(同花顺,代码)
        try:
            if code.isdigit() and AKSHARE_AVAILABLE:
                concept_info = ak.stock_board_concept_cons_ths(symbol=code)
                if concept_info is not None and not concept_info.empty:
                    col = "概念名称" if "概念名称" in concept_info.columns else None
                    if col:
                        th = "、".join(concept_info[col].head(5).astype(str).tolist())
                        if th:
                            lines.append(f"概念:{th}")
        except Exception:
            pass
        lines.append("咨询/基本面:")
        logic_snip = "(无咨询库记录)"
        try:
            rows = get_stock_logic_from_db(stock_name=name_clean) if name_clean else []
            if not rows and stock_name and str(stock_name).strip() != name_clean:
                rows = get_stock_logic_from_db(stock_name=str(stock_name).strip())
            if rows:
                r0 = rows[0]
                lt = (r0.get("logic") or "").strip()
                if len(lt) > 500:
                    lt = lt[:500] + "..."
                logic_snip = f"{r0.get('date', '')} | {r0.get('source', '')}\n{lt}"
        except Exception as e:
            logic_snip = f"读取失败:{e}"
        lines.append(logic_snip)
        lines.append("─" * 36)
        return "\n".join(lines) + "\n"

    def _calculate_ma_values(self, stock_code, current_price):
        """计算股票的5日、10日、15日、20日均线值
        Args:
            stock_code: 股票代码
            current_price: 当前价格
        Returns:
            dict: {'ma5': float, 'ma10': float, 'ma15': float, 'ma20': float, 'ma5_distance': float, 'ma10_distance': float, 'ma15_distance': float, 'ma20_distance': float}
        """
        try:
            # 获取最近收盘价数据
            result = self._fetch_recent_daily_closes(stock_code, days=45, source="default", token=self.ts_token, return_volume=False)
            if isinstance(result, tuple) and len(result) >= 2:
                dates, closes = result[:2]
            else:
                _dates, closes = result, []
            if not closes or len(closes) < 3:
                return None
            # 转换为浮点数
            closes = [float(c) for c in closes]
            ma_result = {
                'ma5': None,
                'ma10': None,
                'ma15': None,
                'ma20': None,
                'ma5_distance': None,
                'ma10_distance': None,
                'ma15_distance': None,
                'ma20_distance': None
            }
            # 计算5日均线
            if len(closes) >= 5:
                ma5_values = closes[-5:]
                ma5 = sum(ma5_values) / len(ma5_values)
                ma_result['ma5'] = ma5
                if ma5 > 0:
                    ma_result['ma5_distance'] = ((current_price - ma5) / ma5) * 100  # 正数表示高于均线,负数表示低于均线
            # 计算10日均线
            if len(closes) >= 10:
                ma10_values = closes[-10:]
                ma10 = sum(ma10_values) / len(ma10_values)
                ma_result['ma10'] = ma10
                if ma10 > 0:
                    ma_result['ma10_distance'] = ((current_price - ma10) / ma10) * 100
            # 计算15日均线
            if len(closes) >= 15:
                ma15_values = closes[-15:]
                ma15 = sum(ma15_values) / len(ma15_values)
                ma_result['ma15'] = ma15
                if ma15 > 0:
                    ma_result['ma15_distance'] = ((current_price - ma15) / ma15) * 100
            # 计算20日均线
            if len(closes) >= 20:
                ma20_values = closes[-20:]
                ma20 = sum(ma20_values) / len(ma20_values)
                ma_result['ma20'] = ma20
                if ma20 > 0:
                    ma_result['ma20_distance'] = ((current_price - ma20) / ma20) * 100
            return ma_result
        except Exception as e:
            print(f"计算均线失败 {stock_code}: {e}")
            return None

    def _display_cb_arbitrage_window(self, rows):
        """在主线程中显示可转债套利弹窗"""
        win = self._safe_toplevel(self.root)
        win.title("A股活跃可转债 - 价格、溢价、强赎与套利提示")
        win.geometry("1400x750")
        win.transient(self.root)
        main = ttk.Frame(win, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        ttk.Label(main, text="可转债与正股价格、换手/成交额、涨跌幅、溢价率、强赎日期、剩余规模(按套利公式提示机会)",
                  font=("TkDefaultFont", 12, "bold")).pack(pady=(0, 5))
        # 中间区域:左侧表格 + 右侧AI分析(可左右拖动调整宽度)
        content_paned = ttk.PanedWindow(main, orient=tk.HORIZONTAL)
        content_paned.pack(fill=tk.BOTH, expand=True)
        # 左侧:可转债列表
        left_frame = ttk.Frame(content_paned)
        content_paned.add(left_frame, weight=3)
        cols = (
            "债券简称", "正股简称", "债现价", "债券涨跌幅%", "正股价",
            "正股涨跌幅%", "转股溢价率%", "换手/成交额", "强赎/到期", "剩余规模", "套利提示"
        )
        tree = ttk.Treeview(left_frame, columns=cols, show="headings", height=25)
        for c in cols:
            tree.heading(c, text=c)
            if c in ("债券简称", "正股简称"):
                width = 90
            elif c in ("债现价", "债券涨跌幅%", "正股价", "正股涨跌幅%", "转股溢价率%"):
                width = 100
            elif c in ("换手/成交额", "强赎/到期", "剩余规模"):
                width = 110
            else:  # 套利提示
                width = 150
            tree.column(c, width=width)
        vsb = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        # 行样式:转债名字加粗、不同颜色区分
        from tkinter import font as tkfont  # 局部导入
        base_font = tkfont.nametofont("TkDefaultFont")
        bond_bold_font = base_font.copy()
        bond_bold_font.configure(weight="bold")
        color_palette = [
            "#1a73e8", "#d93025", "#188038", "#b80672",
            "#f9ab00", "#673ab7", "#00838f", "#795548",
        ]
        row_iids = []
        for idx, r in enumerate(rows):
            iid = tree.insert("", tk.END, values=tuple(r.get(c, "-") for c in cols))
            row_iids.append(iid)
            tag = f"bond_row_{idx}"
            color = color_palette[idx % len(color_palette)]
            tree.item(iid, tags=(tag,))
            tree.tag_configure(tag, foreground=color, font=bond_bold_font)
        # 套利机会行额外高亮背景
        tree.tag_configure("opportunity", background="#e8f5e9")
        for iid, r in zip(row_iids, rows):
            if "存在套利机会" in str(r.get("套利提示", "")):
                current_tags = tree.item(iid, "tags") or ()
                tree.item(iid, tags=(*current_tags, "opportunity"))
        # 点击行打开东方财富该转债链接
        def on_open_bond_url(evt, rows_list=rows):
            sel = tree.selection()
            if not sel:
                return
            try:
                idx = tree.get_children().index(sel[0])
                if 0 <= idx < len(rows_list) and rows_list[idx].get("url"):
                    webbrowser.open(rows_list[idx]["url"])
            except (ValueError, IndexError, KeyError):
                pass
        tree.bind("<Double-1>", on_open_bond_url)
        tree.bind("<Return>", on_open_bond_url)
        # 右侧:AI 转债分析
        right_frame = ttk.Frame(content_paned, padding=(10, 0, 0, 0))
        content_paned.add(right_frame, weight=2)
        ttk.Label(
            right_frame,
            text="AI 可转债分析:优质标的、负溢价/大幅低开套利机会、高风险标的(仅供参考)",
            font=("TkDefaultFont", 11, "bold")
        ).pack(pady=(0, 5))
        # 字体大小控制
        font_ctrl_frame = ttk.Frame(right_frame)
        font_ctrl_frame.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(font_ctrl_frame, text="字体大小:").pack(side=tk.LEFT)
        from tkinter import font as tkfont  # 复用 tkfont
        ai_font = tkfont.nametofont("TkDefaultFont").copy()
        ai_font.configure(size=9)
        font_size_var = tk.IntVar(value=9)
        def _change_ai_font(delta):
            new_size = max(8, min(18, font_size_var.get() + delta))
            font_size_var.set(new_size)
            ai_font.configure(size=new_size)
        ttk.Button(font_ctrl_frame, text="-", width=2, command=lambda: _change_ai_font(-1)).pack(side=tk.LEFT, padx=(2, 2))
        ttk.Button(font_ctrl_frame, text="+", width=2, command=lambda: _change_ai_font(1)).pack(side=tk.LEFT)
        ai_status_label = ttk.Label(right_frame, text="正在准备可转债数据...")
        ai_status_label.pack(anchor=tk.W, pady=(0, 5))
        ai_text = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, font=ai_font)
        ai_text.pack(fill=tk.BOTH, expand=True)
        ai_text.insert("1.0", "AI 分析将自动生成,请稍候...\n")
        ai_text.config(state=tk.DISABLED)
        def run_cb_ai_analysis(rows_snapshot):
            try:
                # 构建明细文本:供 AI 识别负溢价、大幅低开等
                detail_lines = []
                for r in rows_snapshot[:80]:
                    bond_name = r.get("债券简称", "")
                    stock_name = r.get("正股简称", "-")
                    bond_price = r.get("债现价", "-")
                    bond_chg = r.get("债券涨跌幅%", "-")
                    stock_price = r.get("正股价", "-")
                    stock_chg = r.get("正股涨跌幅%", "-")
                    premium = r.get("转股溢价率%", "-")
                    remain = r.get("剩余规模", "-")
                    redeem = r.get("强赎/到期", "-")
                    tip = r.get("套利提示", "-")
                    detail_lines.append(
                        f"{bond_name} / 正股:{stock_name} | 债现价:{bond_price} | 债券涨跌幅:{bond_chg} | "
                        f"正股价:{stock_price} | 正股涨跌幅:{stock_chg} | 溢价率:{premium} | 剩余规模:{remain} | "
                        f"强赎/到期:{redeem} | 套利提示:{tip}"
                    )
                detail_block = "\n".join(detail_lines) if detail_lines else "(无数据)"
                # 统计概要:负溢价、明显高溢价
                neg_list = []
                high_prem_list = []
                risk_list = []
                for r in rows_snapshot:
                    prem_str = r.get("转股溢价率%", "-")
                    prem_val = None
                    try:
                        s = str(prem_str).replace("%", "")
                        prem_val = float(s)
                    except Exception:
                        pass
                    name_pair = f"{r.get('债券简称', '')}/{r.get('正股简称', '-')}"
                    if prem_val is not None:
                        if prem_val < 0:
                            neg_list.append(name_pair)
                        if prem_val > 40:
                            high_prem_list.append(name_pair)
                    if "高溢价" in str(r.get("套利提示", "")) or "注意风险" in str(r.get("套利提示", "")):
                        risk_list.append(name_pair)
                summary_block = (
                    f"负溢价或接近零溢价可转债(可能存在套利机会,仅为初筛):\n"
                    f"{'、'.join(neg_list[:20]) if neg_list else '无明显负溢价'}\n\n"
                    f"溢价率很高(>40%)的可转债(估值偏贵、风险较大):\n"
                    f"{'、'.join(high_prem_list[:20]) if high_prem_list else '无明显高溢价'}\n\n"
                    f"模型初筛为“高溢价/需警惕风险“的可转债:\n"
                    f"{'、'.join(risk_list[:20]) if risk_list else '暂无'}\n"
                )
                prompt = f"""你是一位熟悉 A 股可转债市场的专业转债分析师。
下面是当前市场中一批较为活跃的可转债及其关键数据(价格、当日涨跌幅、溢价率、剩余规模、强赎/到期信息以及简单套利提示):
【一、可转债明细】
{detail_block}
【二、简单统计概要(供你参考,可自行修正判断)】
{summary_block}
请你结合这些表内数据,并参考你对可转债市场的一般认知(可适当参考网上公开资料,但如无法实时获取则以表中数据为准),从以下角度进行分析:
1. 哪些属于相对"优质"的可转债(正股基本面较好、溢价率合理、流动性较好,强赎风险可控),应该重点关注?请给出理由。
2. 指出哪些可转债目前转股溢价率为负或接近 0%,或者当日明显低开(债券涨跌幅远低于正股),可能存在套利机会?请按机会大小大致分层说明,并提示可能的风险点。
3. 指出哪些可转债溢价率很高、估值明显偏贵,或强赎/到期在中短期内可能触发,存在较大风险?说明风险来源。
4. 总结当前可转债整体性价比、市场情绪与风险收益特征,并给出整体操作建议(适合保守型 / 稍激进型投资者如何配置)。
要求:
- 明确列出具体可转债名称(债券简称/正股简称),而不是只讲原则。
- 语言偏实战、通俗,但论据要尽量基于"溢价率、涨跌幅、剩余规模、强赎风险"等可量化信息。
- 不需要非常长篇大论,但要有条理、有重点,并明确区分"机会"和"风险"。
- 所有结论仅为分析参考,不构成投资建议。
"""
                system_prompt = "你是一名专业的 A 股可转债与资产配置分析师,擅长从溢价率、强赎条款、正股质地和市场情绪角度评估机会与风险。"
                # 为可转债分析单独降低 max_tokens、提高超时时间,尽量减少超时概率
                config_override = None
                try:
                    base_cfg = self.ai_config_manager.get_active_provider_config() or {}
                    cfg = dict(base_cfg)
                    # 生成内容不需要太长,限制 tokens 减少耗时
                    if not cfg.get("max_tokens") or cfg.get("max_tokens", 0) > 2600:
                        cfg["max_tokens"] = 2000
                    # 超时时间至少 90 秒,避免偶发超时
                    cfg["timeout"] = max(int(cfg.get("timeout", 60)), 90)
                    config_override = cfg
                except Exception:
                    config_override = None
                ai_result = self.call_ai_model(prompt, system_prompt=system_prompt, config_override=config_override)
                def _update_ui_ok():
                    ai_text.config(state=tk.NORMAL)
                    ai_text.delete("1.0", tk.END)
                    ai_text.insert("1.0", ai_result or "AI 分析失败或未配置,可根据左侧明细自行观察负溢价与高溢价标的。\n")
                    ai_text.config(state=tk.DISABLED)
                    ai_status_label.config(text="AI 分析完成(仅供参考,不构成投资建议)")
                self.root.after(0, _update_ui_ok)
            except Exception as e:
                def _update_ui_err(e=e):
                    ai_text.config(state=tk.NORMAL)
                    ai_text.insert(tk.END, f"\nAI 分析出错:{e}\n")
                    ai_text.config(state=tk.DISABLED)
                    ai_status_label.config(text="AI 分析出错")
                self.root.after(0, _update_ui_err)
        threading.Thread(target=lambda: run_cb_ai_analysis(list(rows)), daemon=True).start()
        ttk.Label(main, text="提示:双击行或选中后按回车,在浏览器打开东方财富该转债页面", font=("TkDefaultFont", 11)).pack(pady=(5, 0))
        win.lift()
        win.focus_force()

    def _on_auto_collect_toggle(self):
        """自动化采集开关切换"""
        enabled = self.auto_collect_var.get()
        self.auto_collect_enabled = enabled
        self.ai_config_manager.config["auto_collect_enabled"] = enabled
        self.ai_config_manager.save_config()
        if enabled:
            print("[自动化采集] 已开启,将自动执行采集任务")
            # 启动自动化采集
            self._start_auto_collect()
        else:
            print("[自动化采集] 已关闭")

    def _auto_upload_excel_files(self):
        """自动上传Excel文件到富媒体输入框,返回创建的标签页ID列表"""
        try:
            import glob
            import os
            # 查找最近生成的Excel文件(淘股吧和韭研)
            excel_dir = D_EXPORT_DIR
            taoguba_files = sorted(glob.glob(os.path.join(excel_dir, "taoguba_*.xlsx")),
                                   key=os.path.getmtime, reverse=True)
            jiuyan_files = sorted(glob.glob(os.path.join(excel_dir, "jiuyang_gongshe_*.xlsx")),
                                  key=os.path.getmtime, reverse=True)
            files_to_upload = []
            if taoguba_files:
                files_to_upload.append(taoguba_files[0])
            if jiuyan_files:
                files_to_upload.append(jiuyan_files[0])
            tab_ids = []
            if files_to_upload:
                # 在主线程中执行上传,返回标签页ID
                for file_path in files_to_upload:
                    tab_id = self._load_excel_file(file_path)
                    if tab_id:
                        tab_ids.append(tab_id)
            return tab_ids
        except Exception as e:
            print(f"[自动上传Excel] 失败: {e}")
            return []

    def _upload_excel_files_to_editor(self, file_paths):
        """上传Excel文件到富媒体编辑器"""
        try:
            for file_path in file_paths:
                if os.path.exists(file_path):
                    # 调用load_excel函数,但直接传入文件路径
                    self._load_excel_file(file_path)
        except Exception as e:
            print(f"[上传Excel到编辑器] 失败: {e}")

    def _find_and_click_buttons_in_popup(self, popup_window):
        """在弹出窗口中查找并点击一键分析和一键保存按钮"""
        try:
            # 递归查找所有按钮
            def find_buttons_recursive(widget):
                buttons_found = []
                try:
                    if isinstance(widget, (ttk.Button, tk.Button)):
                        text = widget.cget("text") if hasattr(widget, 'cget') else ""
                        if "一键分析" in text or "一键保存" in text or "批量保存" in text:
                            buttons_found.append((widget, text))
                    # 递归查找子控件
                    for child in widget.winfo_children():
                        buttons_found.extend(find_buttons_recursive(child))
                except:
                    pass
                return buttons_found
            buttons = find_buttons_recursive(popup_window)
            # 按顺序点击:先一键分析,再一键保存
            for button, text in buttons:
                if "一键分析" in text:
                    print("[弹出框操作] 找到一键分析按钮,准备点击...")
                    self.root.after(1000, lambda b=button: self._simulate_button_click(b))
                elif "一键保存" in text or "批量保存" in text:
                    print("[弹出框操作] 找到一键保存按钮,准备点击...")
                    self.root.after(15000, lambda b=button: self._simulate_button_click(b))  # 延迟15秒,等待分析完成
        except Exception as e:
            print(f"[查找弹出框按钮] 失败: {e}")

    def _three_dimensional_detection(self, stock_name, stock_code, days=20):
        """
        三维一体检测(技术仓位资金检测)
        整合均线检测(技术)、凯利公式计算(仓位)、大单获取(资金)三个维度
        Args:
            stock_name: 股票名称
            stock_code: 股票代码
            days: 获取大单数据的天数,默认20天
        Returns:
            dict: 包含三个维度检测结果的字典
            {
                'technical': {  # 技术维度(均线检测)
                    'ma_status': dict,  # 均线状态
                    'can_open': bool,   # 是否满足开新仓条件
                },
                'position': {   # 仓位维度(凯利公式)
                    'kelly_ratio': float,  # 凯利百分比(0-1)
                    'kelly_percent': float, # 凯利百分比(0-100)
                    'b': float,            # 盈亏比
                    'p': float,            # 胜率
                },
                'capital': {    # 资金维度(大单数据)
                    'daily': list,         # 最近N日大单净流入
                    'accumulation': dict,  # 累计大单净流入
                },
                'stock_code': str,
                'stock_name': str,
                'success': bool,  # 检测是否成功
                'error': str      # 错误信息(如果有)
            }
        """
        result = {
            'technical': {'ma_status': {}, 'can_open': False},
            'position': {'kelly_ratio': 0.0, 'kelly_percent': 0.0, 'b': 0.0, 'p': 0.0},
            'capital': {'daily': [], 'accumulation': {}},
            'stock_code': stock_code,
            'stock_name': stock_name,
            'success': False,
            'error': None
        }
        try:
            # 获取股票代码
            if not stock_code:
                stock_code = get_stock_code_by_name(stock_name)
                result['stock_code'] = stock_code
            if not stock_code:
                result['error'] = "无法获取股票代码"
                return result
            # ========== 技术维度:均线检测 ==========
            ma_status = self._check_ma_status(stock_code)
            result['technical']['ma_status'] = ma_status
            # 判断是否满足开新仓条件(所有均线都满足)
            can_open = True
            for ma_key in ['ma1', 'ma5', 'ma10', 'ma20']:
                if ma_key in ma_status and not ma_status[ma_key]:
                    can_open = False
                    break
            result['technical']['can_open'] = can_open
            # ========== 仓位维度:凯利公式计算 ==========
            b, p = self._calculate_kelly_params(ma_status)
            kelly_ratio = self._calculate_kelly_ratio(b, p)
            result['position'] = {
                'kelly_ratio': kelly_ratio,
                'kelly_percent': kelly_ratio * 100,
                'b': b,
                'p': p
            }
            # ========== 资金维度:大单净流入 ==========
            capital_data = self._get_large_order_net_inflow_with_accumulation(stock_code, days=days)
            result['capital'] = capital_data
            result['success'] = True
            return result
        except Exception as e:
            result['error'] = str(e)
            print(f"三维一体检测失败: {e}")
            return result

    def _calculate_5day_low_diff(self, group_index=1, max_count=None):
        """计算所有持仓股的5日最低点差%(类似批量计算的起爆点计算)
        Args:
            group_index: 持仓组索引(1-5)
            max_count: 最大计算数量(None表示计算所有)
        """
        # 获取对应组的数据结构
        holding_stocks, _holding_labels, _holding_kelly_results, holding_low_diff_results = self._get_holding_group_data(group_index)
        if not any(holding_stocks):
            messagebox.showwarning("警告", "请先导入持仓股", parent=self.root)
            return
        # 在新线程中执行计算
        def calculate_thread():
            for i, holding in enumerate(holding_stocks):
                if holding and (max_count is None or i < max_count):
                    stock_name, stock_code = holding
                    if not stock_code:
                        continue
                    try:
                        # 获取当前股价和5日最低点
                        current_price, _max_high, min_low = self._get_5day_high_low_data(stock_code)
                        if current_price is not None and min_low is not None and min_low > 0:
                            # 计算股价-5日最低点差%
                            low_diff = current_price - min_low
                            low_diff_pct = (low_diff / min_low) * 100
                            # 存储结果
                            holding_low_diff_results[i] = {
                                'low_diff_pct': low_diff_pct,
                                'current_price': current_price,
                                'min_low': min_low
                            }
                            # 在主线程中更新UI
                            def update_ui(idx=i, gidx=group_index):
                                self._update_holding_label(idx, check_conditions=False, group_index=gidx)
                            self.root.after(0, update_ui)
                        else:
                            # 获取失败,清除结果
                            holding_low_diff_results[i] = None
                    except Exception as e:
                        print(f"计算持仓股 {stock_name} 的5日最低点差%失败: {e}")
                        holding_low_diff_results[i] = None
                    # 每个股票计算间隔0.5秒,避免请求过快
                    time.sleep(0.5)
        thread = threading.Thread(target=calculate_thread, daemon=True)
        thread.start()
        messagebox.showinfo("提示", "5日最低点计算已开始,正在后台执行...", parent=self.root)

    def _calculate_sharpe_ratio(self, kline_data, stock_name, risk_free_rate=0.02):
        """计算夏普比率。
        夏普比率公式:Sharpe Ratio = (Rp - Rf) / σp
        其中:
        - Rp = 投资组合平均收益率
        - Rf = 无风险利率(年化,默认2%)
        - σp = 投资组合收益率标准差
        Returns:
            dict: 包含夏普比率、年化收益率、波动率等详细信息
        """
        result = {
            'success': False,
            'message': '',
            'sharpe_ratio': 0.0,
            'annualized_return': 0.0,
            'volatility': 0.0,
            'daily_returns': [],
            'calculation_steps': [],
            'analysis': []
        }
        try:
            data = kline_data['data']
            n = len(data)
            if n < 30:
                result['message'] = '数据不足,至少需要30条K线'
                return result
            closes = data['收盘'].values
            steps = []
            # 计算每日收益率
            daily_returns = []
            for i in range(1, n):
                prev_close = float(closes[i-1])
                curr_close = float(closes[i])
                if prev_close > 0:
                    ret = (curr_close - prev_close) / prev_close
                    daily_returns.append(ret)
            result['daily_returns'] = daily_returns
            steps.append(f"【步骤1】计算每日收益率:共 {len(daily_returns)} 个交易日")
            if len(daily_returns) < 20:
                result['message'] = '有效收益率数据不足'
                return result
            # 计算平均每日收益率
            avg_daily_return = sum(daily_returns) / len(daily_returns)
            steps.append(f"【步骤2】平均每日收益率:avg_daily = {avg_daily_return:.6f}")
            # 年化收益率(假设252个交易日)
            annualized_return = (1 + avg_daily_return) ** 252 - 1
            result['annualized_return'] = round(annualized_return * 100, 2)
            steps.append(f"【步骤3】年化收益率:Rp = (1 + {avg_daily_return:.6f})^252 - 1 = {annualized_return * 100:.2f}%")
            # 计算收益率标准差
            variance = sum((r - avg_daily_return) ** 2 for r in daily_returns) / len(daily_returns)
            daily_std = variance ** 0.5
            steps.append(f"【步骤4】每日收益率标准差:daily_std = {daily_std:.6f}")
            # 年化波动率
            volatility = daily_std * (252 ** 0.5)
            result['volatility'] = round(volatility * 100, 2)
            steps.append(f"【步骤5】年化波动率:σp = {daily_std:.6f} × √252 = {volatility * 100:.2f}%")
            # 无风险利率(年化)
            steps.append(f"【步骤6】无风险利率:Rf = {risk_free_rate * 100:.1f}%")
            # 计算夏普比率
            excess_return = annualized_return - risk_free_rate
            if volatility > 0:
                sharpe_ratio = excess_return / volatility
                result['sharpe_ratio'] = round(sharpe_ratio, 4)
                steps.append(f"【步骤7】夏普比率:Sharpe = ({excess_return * 100:.2f}% - {risk_free_rate * 100:.1f}%) / {volatility * 100:.2f}% = {sharpe_ratio:.4f}")
            else:
                result['sharpe_ratio'] = 0.0
                steps.append("【步骤7】夏普比率:波动率为0,夏普比率 = 0")
            result['calculation_steps'] = steps
            # 生成分析说明
            analysis = []
            analysis.append(f"夏普比率:{result['sharpe_ratio']:.4f}")
            analysis.append(f"年化收益率:{result['annualized_return']:.2f}%")
            analysis.append(f"年化波动率:{result['volatility']:.2f}%")
            sharpe = result['sharpe_ratio']
            if sharpe >= 2.0:
                analysis.append("评价:夏普比率优秀,风险调整后收益很高")
            elif sharpe >= 1.0:
                analysis.append("评价:夏普比率良好,风险调整后收益不错")
            elif sharpe >= 0.5:
                analysis.append("评价:夏普比率一般,需要关注风险")
            elif sharpe >= 0:
                analysis.append("评价:夏普比率较低,收益不足以覆盖风险")
            else:
                analysis.append("评价:夏普比率为负,投资表现不如无风险资产")
            result['analysis'] = analysis
            result['success'] = True
            result['message'] = '计算完成'
        except Exception as e:
            result['message'] = f'计算失败: {e}'
        return result

    def _calculate_dragon_head(self, kline_data, stock_name):
        """龙头战法分析。
        基于涨停板、连板、成交量、换手率等指标判断股票是否具备龙头特征,
        预测后续上涨空间。
        核心逻辑:
        1. 涨停板数量和连续性
        2. 封板质量(封单金额、开板次数)
        3. 换手率和成交量
        4. 均线位置和趋势
        """
        result = {
            'success': False,
            'message': '',
            'analysis': [],
            'calculation_steps': [],
            'prediction': {
                'next_day': {'direction': 'neutral', 'probability': 50, 'expected_return': 0},
                'next_week': {'direction': 'neutral', 'probability': 50, 'expected_return': 0}
            },
            'dragon_score': 0,
            'is_dragon': False
        }
        try:
            data = kline_data['data']
            ma_values = kline_data['ma_values']
            n = len(data)
            if n < 10:
                result['message'] = '数据不足,至少需要10条K线'
                return result
            closes = data['收盘'].values
            opens = data['开盘'].values
            highs = data['最高'].values
            data['最低'].values
            volumes = data['成交量'].values
            import numpy as np
            result['calculation_steps'].append("【步骤1:涨停板分析】")
            limit_up_count = 0
            consecutive_limit_up = 0
            max_consecutive = 0
            for i in range(n):
                if opens[i] > 0:
                    change_pct = (closes[i] - opens[i]) / opens[i] * 100
                    if change_pct >= 9.8:
                        limit_up_count += 1
                        consecutive_limit_up += 1
                        max_consecutive = max(max_consecutive, consecutive_limit_up)
                    else:
                        consecutive_limit_up = 0
            result['calculation_steps'].append(f"  近{n}日涨停次数:{limit_up_count}次")
            result['calculation_steps'].append(f"  最大连板数:{max_consecutive}板")
            limit_score = 0
            if limit_up_count >= 3:
                limit_score += 20
                if max_consecutive >= 2:
                    limit_score += 15
                    result['calculation_steps'].append("  ✓ 具备连板潜力")
                if max_consecutive >= 3:
                    limit_score += 15
                    result['calculation_steps'].append("  ✓ 强势连板龙头")
            elif limit_up_count >= 1:
                limit_score += 5
            result['calculation_steps'].append("\n【步骤2:封板质量分析】")
            seal_score = 0
            recent_highs = highs[-5:]
            recent_closes = closes[-5:]
            seal_count = 0
            for i in range(len(recent_highs)):
                if recent_highs[i] > 0 and recent_closes[i] > 0:
                    if abs(recent_highs[i] - recent_closes[i]) / recent_highs[i] < 0.001:
                        seal_count += 1
            seal_rate = seal_count / len(recent_highs)
            result['calculation_steps'].append(f"  近5日封板率:{seal_rate:.0%}")
            if seal_rate >= 0.8:
                seal_score += 15
                result['calculation_steps'].append("  ✓ 封板质量高")
            elif seal_rate >= 0.5:
                seal_score += 5
            result['calculation_steps'].append("\n【步骤3:换手率分析】")
            turnover_score = 0
            recent_vol_mean = np.mean(volumes[-10:])
            if recent_vol_mean > 0:
                recent_turnover_ratio = volumes[-1] / recent_vol_mean
                result['calculation_steps'].append(f"  今日量比:{recent_turnover_ratio:.2f}")
                if recent_turnover_ratio > 2:
                    turnover_score += 10
                    result['calculation_steps'].append("  ✓ 放量上涨")
                elif recent_turnover_ratio > 1.3:
                    turnover_score += 5
            result['calculation_steps'].append("\n【步骤4:均线位置分析】")
            ma_score = 0
            ma5 = np.array(ma_values.get('ma5', []))
            ma10 = np.array(ma_values.get('ma10', []))
            ma20 = np.array(ma_values.get('ma20', []))
            if len(ma5) >= 1 and len(ma10) >= 1 and len(ma20) >= 1:
                if closes[-1] > ma5[-1] and closes[-1] > ma10[-1] and closes[-1] > ma20[-1]:
                    ma_score += 15
                    result['calculation_steps'].append("  ✓ 股价远离均线(强势)")
                    distance_ratio = (closes[-1] - ma10[-1]) / ma10[-1] * 100
                    result['calculation_steps'].append(f"  距MA10距离:{distance_ratio:.1f}%")
                    if distance_ratio > 10:
                        ma_score -= 5
                        result['calculation_steps'].append("  ~ 乖离率较大,注意回调风险")
            total_score = limit_score + seal_score + turnover_score + ma_score
            result['dragon_score'] = total_score
            result['is_dragon'] = total_score >= 40
            result['calculation_steps'].append("\n【综合评分】")
            result['calculation_steps'].append(f"  涨停分:{limit_score}")
            result['calculation_steps'].append(f"  封板质量分:{seal_score}")
            result['calculation_steps'].append(f"  换手率分:{turnover_score}")
            result['calculation_steps'].append(f"  均线位置分:{ma_score}")
            result['calculation_steps'].append(f"  总分:{total_score}")
            if total_score >= 50:
                result['prediction']['next_day']['direction'] = 'up'
                result['prediction']['next_day']['probability'] = 75
                result['prediction']['next_day']['expected_return'] = 8
                result['prediction']['next_week']['direction'] = 'up'
                result['prediction']['next_week']['probability'] = 70
                result['prediction']['next_week']['expected_return'] = 15
                result['analysis'].append("【龙头判断】★★★ 强势龙头股")
                result['analysis'].append("【预测】明日涨停概率 75%")
                result['analysis'].append("【预测】下周涨幅预期 +15%")
                result['analysis'].append("【建议】持有为主,不破5日线不减仓")
            elif total_score >= 30:
                result['prediction']['next_day']['direction'] = 'up'
                result['prediction']['next_day']['probability'] = 60
                result['prediction']['next_day']['expected_return'] = 3
                result['prediction']['next_week']['direction'] = 'up'
                result['prediction']['next_week']['probability'] = 55
                result['prediction']['next_week']['expected_return'] = 8
                result['analysis'].append("【龙头判断】★★ 具备龙头特征")
                result['analysis'].append("【预测】明日上涨概率 60%")
                result['analysis'].append("【预测】下周涨幅预期 +8%")
                result['analysis'].append("【建议】可适量参与")
            else:
                result['prediction']['next_day']['direction'] = 'neutral'
                result['prediction']['next_day']['probability'] = 50
                result['prediction']['next_week']['direction'] = 'neutral'
                result['prediction']['next_week']['probability'] = 50
                result['analysis'].append("【龙头判断】★ 非龙头股")
                result['analysis'].append("【预测】无明显龙头特征")
                result['analysis'].append("【建议】不建议按龙头战法操作")
            result['success'] = True
            result['message'] = '计算完成'
        except Exception as e:
            result['message'] = f'计算失败: {e}'
        return result

    def _calculate_overbought_bounce(self, kline_data, stock_name):
        """超跌反弹分析。
        基于价格跌幅、成交量萎缩、技术指标超卖等判断是否具备反弹条件,
        预测反弹概率和目标价位。
        核心逻辑:
        1. 近期跌幅深度
        2. 成交量萎缩程度
        3. RSI、KDJ等超卖信号
        4. 支撑位测试
        """
        result = {
            'success': False,
            'message': '',
            'analysis': [],
            'calculation_steps': [],
            'prediction': {
                'next_day': {'direction': 'neutral', 'probability': 50, 'expected_return': 0},
                'next_week': {'direction': 'neutral', 'probability': 50, 'expected_return': 0}
            },
            'bounce_score': 0,
            'support_levels': [],
            'target_levels': []
        }
        try:
            data = kline_data['data']
            ma_values = kline_data['ma_values']
            n = len(data)
            if n < 15:
                result['message'] = '数据不足,至少需要15条K线'
                return result
            closes = data['收盘'].values
            volumes = data['成交量'].values
            import numpy as np
            result['calculation_steps'].append("【步骤1:跌幅深度分析】")
            recent_high_20 = max(closes[-20:])
            recent_high_60 = max(closes[-60:]) if n >= 60 else recent_high_20
            current_price = closes[-1]
            drop_20 = (current_price - recent_high_20) / recent_high_20 * 100
            drop_60 = (current_price - recent_high_60) / recent_high_60 * 100
            result['calculation_steps'].append(f"  距20日高点跌幅:{drop_20:.1f}%")
            result['calculation_steps'].append(f"  距60日高点跌幅:{drop_60:.1f}%")
            drop_score = 0
            if drop_20 <= -15:
                drop_score += 20
                result['calculation_steps'].append("  ✓ 短期超跌(跌幅>15%)")
                if drop_20 <= -25:
                    drop_score += 10
                    result['calculation_steps'].append("  ✓ 严重超跌(跌幅>25%)")
            elif drop_20 <= -10:
                drop_score += 10
            result['calculation_steps'].append("\n【步骤2:成交量萎缩分析】")
            vol_score = 0
            recent_vol_mean_10 = np.mean(volumes[-10:])
            recent_vol_mean_20 = np.mean(volumes[-20:])
            if recent_vol_mean_20 > 0:
                vol_ratio = recent_vol_mean_10 / recent_vol_mean_20
                result['calculation_steps'].append(f"  近10日/20日均量比:{vol_ratio:.2f}")
                if vol_ratio < 0.6:
                    vol_score += 15
                    result['calculation_steps'].append("  ✓ 成交量严重萎缩(量能衰竭)")
                elif vol_ratio < 0.8:
                    vol_score += 5
                    result['calculation_steps'].append("  ~ 成交量有所萎缩")
            result['calculation_steps'].append("\n【步骤3:RSI超卖分析】")
            rsi_score = 0
            deltas = np.diff(closes)
            gains = deltas.copy()
            gains[gains < 0] = 0
            losses = -deltas.copy()
            losses[losses < 0] = 0
            avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else 0
            avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else 0
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
                result['calculation_steps'].append(f"  RSI(14):{rsi:.1f}")
                if rsi < 30:
                    rsi_score += 15
                    result['calculation_steps'].append("  ✓ RSI超卖(<30)")
                    if rsi < 20:
                        rsi_score += 10
                        result['calculation_steps'].append("  ✓ RSI严重超卖(<20)")
                elif rsi < 40:
                    rsi_score += 5
            else:
                rsi_score += 10
                result['calculation_steps'].append("  ✓ 连续上涨,无超卖")
            result['calculation_steps'].append("\n【步骤4:支撑位分析】")
            support_score = 0
            np.array(ma_values.get('ma5', []))
            np.array(ma_values.get('ma10', []))
            ma20 = np.array(ma_values.get('ma20', []))
            ma60 = np.array(ma_values.get('ma60', []))
            support_levels = []
            if len(ma60) >= 1:
                support_levels.append(('MA60', ma60[-1]))
            if len(ma20) >= 1:
                support_levels.append(('MA20', ma20[-1]))
            recent_lows_20 = sorted(closes[-20:])[:3]
            for i, low in enumerate(recent_lows_20):
                support_levels.append((f'近期低点{i+1}', low))
            result['support_levels'] = support_levels
            for name, level in support_levels[:3]:
                if abs(current_price - level) / level < 0.02:
                    support_score += 10
                    result['calculation_steps'].append(f"  ✓ 接近{name}支撑位 {level:.2f}")
            total_score = drop_score + vol_score + rsi_score + support_score
            result['bounce_score'] = total_score
            result['calculation_steps'].append("\n【综合评分】")
            result['calculation_steps'].append(f"  跌幅分:{drop_score}")
            result['calculation_steps'].append(f"  缩量分:{vol_score}")
            result['calculation_steps'].append(f"  RSI超卖分:{rsi_score}")
            result['calculation_steps'].append(f"  支撑位分:{support_score}")
            result['calculation_steps'].append(f"  总分:{total_score}")
            if total_score >= 50:
                result['prediction']['next_day']['direction'] = 'up'
                result['prediction']['next_day']['probability'] = 70
                result['prediction']['next_day']['expected_return'] = 5
                result['prediction']['next_week']['direction'] = 'up'
                result['prediction']['next_week']['probability'] = 65
                result['prediction']['next_week']['expected_return'] = 10
                result['target_levels'] = [
                    {'level': current_price * 1.05, 'name': '第一目标位(+5%)'},
                    {'level': current_price * 1.10, 'name': '第二目标位(+10%)'}
                ]
                result['analysis'].append("【超跌判断】★★★ 强烈超跌,反弹概率高")
                result['analysis'].append("【预测】明日反弹概率 70%")
                result['analysis'].append("【预测】下周反弹幅度 +10%")
                result['analysis'].append(f"【支撑位】{', '.join([f'{n}: {v:.2f}' for n, v in support_levels[:3]])}")
                result['analysis'].append("【目标位】第一目标 +5%,第二目标 +10%")
                result['analysis'].append("【建议】适量低吸,设好止损")
            elif total_score >= 30:
                result['prediction']['next_day']['direction'] = 'up'
                result['prediction']['next_day']['probability'] = 55
                result['prediction']['next_day']['expected_return'] = 2
                result['prediction']['next_week']['direction'] = 'up'
                result['prediction']['next_week']['probability'] = 55
                result['prediction']['next_week']['expected_return'] = 5
                result['analysis'].append("【超跌判断】★★ 中度超跌")
                result['analysis'].append("【预测】明日反弹概率 55%")
                result['analysis'].append("【预测】下周反弹幅度 +5%")
                result['analysis'].append("【建议】可小仓位试错")
            else:
                result['prediction']['next_day']['direction'] = 'neutral'
                result['prediction']['next_day']['probability'] = 50
                result['prediction']['next_week']['direction'] = 'neutral'
                result['prediction']['next_week']['probability'] = 50
                result['analysis'].append("【超跌判断】★ 未达到超跌标准")
                result['analysis'].append("【预测】无明显反弹信号")
                result['analysis'].append("【建议】等待更明确的信号")
            result['success'] = True
            result['message'] = '计算完成'
        except Exception as e:
            result['message'] = f'计算失败: {e}'
        return result

    def _calculate_multi_factor(self, kline_data, stock_name):
        """多因子评分分析。
        综合多个技术因子对股票进行评分,预测未来走势概率。
        核心因子:
        1. 动量因子(近期涨幅)
        2. 波动率因子(ATR)
        3. 成交量因子(量比)
        4. 均线因子(均线排列)
        5. 反转因子(RSI超买超卖)
        """
        result = {
            'success': False,
            'message': '',
            'analysis': [],
            'calculation_steps': [],
            'prediction': {
                'next_day': {'direction': 'neutral', 'probability': 50, 'expected_return': 0},
                'next_week': {'direction': 'neutral', 'probability': 50, 'expected_return': 0}
            },
            'factor_scores': {},
            'total_score': 0
        }
        try:
            data = kline_data['data']
            ma_values = kline_data['ma_values']
            n = len(data)
            if n < 20:
                result['message'] = '数据不足,至少需要20条K线'
                return result
            closes = data['收盘'].values
            highs = data['最高'].values
            lows = data['最低'].values
            volumes = data['成交量'].values
            import numpy as np
            factor_scores = {}
            result['calculation_steps'].append("【因子1:动量因子】")
            momentum_5 = (closes[-1] - closes[-5]) / closes[-5] * 100 if closes[-5] > 0 else 0
            momentum_10 = (closes[-1] - closes[-10]) / closes[-10] * 100 if closes[-10] > 0 else 0
            momentum_20 = (closes[-1] - closes[-20]) / closes[-20] * 100 if closes[-20] > 0 else 0
            momentum_score = 0
            if momentum_5 > 3:
                momentum_score += 8
            elif momentum_5 < -3:
                momentum_score -= 8
            if momentum_10 > 5:
                momentum_score += 7
            elif momentum_10 < -5:
                momentum_score -= 7
            if momentum_20 > 8:
                momentum_score += 5
            elif momentum_20 < -8:
                momentum_score -= 5
            factor_scores['动量因子'] = momentum_score
            result['calculation_steps'].append(f"  5日涨幅:{momentum_5:.1f}%")
            result['calculation_steps'].append(f"  10日涨幅:{momentum_10:.1f}%")
            result['calculation_steps'].append(f"  20日涨幅:{momentum_20:.1f}%")
            result['calculation_steps'].append(f"  得分:{momentum_score}")
            result['calculation_steps'].append("\n【因子2:波动率因子】")
            tr_list = []
            for i in range(1, n):
                high = highs[i]
                low = lows[i]
                prev_close = closes[i-1]
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_list.append(tr)
            atr = np.mean(tr_list[-14:]) if len(tr_list) >= 14 else 0
            price_level = closes[-1]
            atr_ratio = atr / price_level * 100 if price_level > 0 else 0
            volatility_score = 0
            if atr_ratio > 3:
                volatility_score += 5
                result['calculation_steps'].append("  ✓ 高波动(趋势可能延续)")
            elif atr_ratio < 1:
                volatility_score -= 5
                result['calculation_steps'].append("  ~ 低波动(可能变盘)")
            factor_scores['波动率因子'] = volatility_score
            result['calculation_steps'].append(f"  ATR比率:{atr_ratio:.1f}%")
            result['calculation_steps'].append(f"  得分:{volatility_score}")
            result['calculation_steps'].append("\n【因子3:成交量因子】")
            recent_vol_mean = np.mean(volumes[-20:])
            vol_ratio = volumes[-1] / recent_vol_mean if recent_vol_mean > 0 else 1
            volume_score = 0
            if vol_ratio > 1.5:
                if closes[-1] > closes[-2]:
                    volume_score += 10
                    result['calculation_steps'].append("  ✓ 价涨量增")
                else:
                    volume_score -= 5
                    result['calculation_steps'].append("  ✗ 价跌量增")
            elif vol_ratio < 0.7:
                if closes[-1] > closes[-2]:
                    volume_score += 5
                    result['calculation_steps'].append("  ✓ 价涨量缩(惜售)")
                else:
                    volume_score -= 5
                    result['calculation_steps'].append("  ~ 缩量下跌")
            factor_scores['成交量因子'] = volume_score
            result['calculation_steps'].append(f"  量比:{vol_ratio:.2f}")
            result['calculation_steps'].append(f"  得分:{volume_score}")
            result['calculation_steps'].append("\n【因子4:均线因子】")
            ma5 = np.array(ma_values.get('ma5', []))
            ma10 = np.array(ma_values.get('ma10', []))
            ma20 = np.array(ma_values.get('ma20', []))
            ma60 = np.array(ma_values.get('ma60', []))
            ma_score = 0
            if len(ma5) >= 1 and len(ma10) >= 1 and len(ma20) >= 1:
                if ma5[-1] > ma10[-1] and ma10[-1] > ma20[-1]:
                    ma_score += 10
                    result['calculation_steps'].append("  ✓ 均线多头排列")
                elif ma5[-1] < ma10[-1] and ma10[-1] < ma20[-1]:
                    ma_score -= 10
                    result['calculation_steps'].append("  ✗ 均线空头排列")
                if len(ma60) >= 1:
                    if closes[-1] > ma60[-1]:
                        ma_score += 5
                        result['calculation_steps'].append("  ✓ 站在60日均线上方")
                    else:
                        ma_score -= 5
            factor_scores['均线因子'] = ma_score
            result['calculation_steps'].append(f"  得分:{ma_score}")
            result['calculation_steps'].append("\n【因子5:反转因子(RSI)】")
            deltas = np.diff(closes)
            gains = deltas.copy()
            gains[gains < 0] = 0
            losses = -deltas.copy()
            losses[losses < 0] = 0
            avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else 0
            avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else 0
            rsi_score = 0
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
                if rsi < 30:
                    rsi_score += 8
                    result['calculation_steps'].append(f"  ✓ RSI超卖({rsi:.1f})")
                elif rsi > 70:
                    rsi_score -= 8
                    result['calculation_steps'].append(f"  ✗ RSI超买({rsi:.1f})")
            else:
                rsi_score += 5
            factor_scores['反转因子'] = rsi_score
            result['calculation_steps'].append(f"  RSI(14):{rsi:.1f}" if 'rsi' in locals() else "  RSI:无数据")
            result['calculation_steps'].append(f"  得分:{rsi_score}")
            total_score = sum(factor_scores.values())
            result['factor_scores'] = factor_scores
            result['total_score'] = total_score
            result['calculation_steps'].append("\n【综合评分】")
            for factor, score in factor_scores.items():
                result['calculation_steps'].append(f"  {factor}:{score}")
            result['calculation_steps'].append(f"  总分:{total_score}")
            if total_score >= 20:
                result['prediction']['next_day']['direction'] = 'up'
                result['prediction']['next_day']['probability'] = min(70, 50 + total_score)
                result['prediction']['next_day']['expected_return'] = total_score * 0.3
                result['prediction']['next_week']['direction'] = 'up'
                result['prediction']['next_week']['probability'] = min(65, 50 + total_score * 0.8)
                result['prediction']['next_week']['expected_return'] = total_score * 0.8
                result['analysis'].append("【综合判断】★★★ 看多信号")
                result['analysis'].append(f"【预测】明日上涨概率 {result['prediction']['next_day']['probability']}%")
                result['analysis'].append(f"【预测】下周上涨概率 {result['prediction']['next_week']['probability']}%")
                result['analysis'].append("【建议】买入或增持")
            elif total_score <= -15:
                result['prediction']['next_day']['direction'] = 'down'
                result['prediction']['next_day']['probability'] = min(70, 50 - total_score)
                result['prediction']['next_day']['expected_return'] = total_score * 0.3
                result['prediction']['next_week']['direction'] = 'down'
                result['prediction']['next_week']['probability'] = min(65, 50 - total_score * 0.8)
                result['prediction']['next_week']['expected_return'] = total_score * 0.8
                result['analysis'].append("【综合判断】★★★ 看空信号")
                result['analysis'].append(f"【预测】明日下跌概率 {result['prediction']['next_day']['probability']}%")
                result['analysis'].append(f"【预测】下周下跌概率 {result['prediction']['next_week']['probability']}%")
                result['analysis'].append("【建议】卖出或减仓")
            else:
                result['prediction']['next_day']['direction'] = 'neutral'
                result['prediction']['next_day']['probability'] = 50
                result['prediction']['next_week']['direction'] = 'neutral'
                result['prediction']['next_week']['probability'] = 50
                result['analysis'].append("【综合判断】★★ 中性信号")
                result['analysis'].append("【预测】方向不明,震荡为主")
                result['analysis'].append("【建议】观望或轻仓操作")
            result['success'] = True
            result['message'] = '计算完成'
        except Exception as e:
            result['message'] = f'计算失败: {e}'
        return result

    def _calculate_buy_point_prediction(self, kline_data, stock_name):
        """计算买点预测。
        基于三个条件识别买点:
        1. MACD快线(DIF) > MACD慢线(DEA)
        2. 均线多头发散(MA5 > MA10 > MA20)
        3. WR低位(WR(2) < -80)
        将满足条件的点用竖线连接,计算间距,推导后续买点。
        Returns:
            dict: 包含买点列表、间距分析、预测买点等详细信息
        """
        result = {
            'success': False,
            'message': '',
            'buy_points': [],
            'predicted_points': [],
            'spacing_analysis': [],
            'calculation_steps': [],
            'analysis': []
        }
        try:
            data = kline_data['data']
            ma_values = kline_data['ma_values']
            n = len(data)
            if n < 30:
                result['message'] = '数据不足,至少需要30条K线'
                return result
            closes = data['收盘'].values
            highs = data['最高'].values
            lows = data['最低'].values
            data['开盘'].values
            steps = []
            # 计算MACD
            ema12 = self._ema_np(closes, 12)
            ema26 = self._ema_np(closes, 26)
            dif = ema12 - ema26
            dea = self._ema_np(dif, 9)
            steps.append("【步骤1】计算MACD指标(12/26/9)")
            # 计算WR(2)
            wr = self._williams_r_n(highs, lows, closes, 2)
            steps.append("【步骤2】计算WR(2)指标")
            # 获取均线数据
            ma5 = np.asarray(ma_values.get('ma5', []), dtype=float) if ma_values.get('ma5') else np.zeros(n)
            ma10 = np.asarray(ma_values.get('ma10', []), dtype=float) if ma_values.get('ma10') else np.zeros(n)
            ma20 = np.asarray(ma_values.get('ma20', []), dtype=float) if ma_values.get('ma20') else np.zeros(n)
            # 对齐均线数据长度
            start_idx = max(len(closes) - len(ma5), len(closes) - len(ma10), len(closes) - len(ma20))
            steps.append("【步骤3】获取MA5/MA10/MA20均线数据")
            # 识别买点(同时满足三个条件)
            buy_points = []
            for i in range(start_idx, n):
                ma5_val = ma5[i - (len(closes) - len(ma5))] if len(ma5) > 0 else closes[i]
                ma10_val = ma10[i - (len(closes) - len(ma10))] if len(ma10) > 0 else closes[i]
                ma20_val = ma20[i - (len(closes) - len(ma20))] if len(ma20) > 0 else closes[i]
                # 条件1: MACD快线 > 慢线
                cond1 = dif[i] > dea[i]
                # 条件2: 均线多头发散(MA5 > MA10 > MA20)
                cond2 = ma5_val > ma10_val > ma20_val
                # 条件3: WR低位(WR(2) < -80)
                cond3 = wr[i] < -80
                if cond1 and cond2 and cond3:
                    buy_points.append({
                        'index': i,
                        'date': kline_data.get('trade_dates', [str(j) for j in range(n)])[i],
                        'price': float(closes[i]),
                        'dif': float(dif[i]),
                        'dea': float(dea[i]),
                        'wr': float(wr[i]),
                        'ma5': float(ma5_val),
                        'ma10': float(ma10_val),
                        'ma20': float(ma20_val)
                    })
            steps.append(f"【步骤4】识别买点:共找到 {len(buy_points)} 个满足条件的点")
            result['buy_points'] = buy_points
            # 计算间距分析
            spacing_analysis = []
            if len(buy_points) >= 2:
                spacings = []
                for i in range(1, len(buy_points)):
                    spacing = buy_points[i]['index'] - buy_points[i-1]['index']
                    spacings.append(spacing)
                    spacing_analysis.append(f"买点{i}与买点{i+1}间距:{spacing}个交易日")
                avg_spacing = sum(spacings) / len(spacings)
                min_spacing = min(spacings)
                max_spacing = max(spacings)
                spacing_analysis.append(f"平均间距:{avg_spacing:.1f}个交易日")
                spacing_analysis.append(f"最小间距:{min_spacing}个交易日")
                spacing_analysis.append(f"最大间距:{max_spacing}个交易日")
                steps.append(f"【步骤5】间距分析:平均{avg_spacing:.1f}日,最小{min_spacing}日,最大{max_spacing}日")
                # 推导后续买点
                predicted_points = []
                if buy_points:
                    last_point = buy_points[-1]
                    last_index = last_point['index']
                    # 基于平均间距预测下一个买点
                    predicted_index_1 = int(last_index + avg_spacing)
                    if predicted_index_1 < n:
                        predicted_price_1 = float(closes[predicted_index_1])
                    else:
                        # 预测未来价格(基于最近趋势)
                        if n >= 5:
                            trend = (closes[-1] - closes[-5]) / 5
                            predicted_price_1 = float(closes[-1] + trend * (predicted_index_1 - (n-1)))
                        else:
                            predicted_price_1 = float(closes[-1])
                    predicted_points.append({
                        'index': predicted_index_1,
                        'type': '基于平均间距',
                        'spacing': f"+{avg_spacing:.1f}日",
                        'predicted_price': predicted_price_1,
                        'confidence': '中'
                    })
                    # 基于最小间距预测
                    predicted_index_2 = int(last_index + min_spacing)
                    if predicted_index_2 < n:
                        predicted_price_2 = float(closes[predicted_index_2])
                    else:
                        if n >= 5:
                            trend = (closes[-1] - closes[-5]) / 5
                            predicted_price_2 = float(closes[-1] + trend * (predicted_index_2 - (n-1)))
                        else:
                            predicted_price_2 = float(closes[-1])
                    predicted_points.append({
                        'index': predicted_index_2,
                        'type': '基于最小间距',
                        'spacing': f"+{min_spacing}日",
                        'predicted_price': predicted_price_2,
                        'confidence': '高'
                    })
                    # 基于最大间距预测
                    predicted_index_3 = int(last_index + max_spacing)
                    if predicted_index_3 < n:
                        predicted_price_3 = float(closes[predicted_index_3])
                    else:
                        if n >= 5:
                            trend = (closes[-1] - closes[-5]) / 5
                            predicted_price_3 = float(closes[-1] + trend * (predicted_index_3 - (n-1)))
                        else:
                            predicted_price_3 = float(closes[-1])
                    predicted_points.append({
                        'index': predicted_index_3,
                        'type': '基于最大间距',
                        'spacing': f"+{max_spacing}日",
                        'predicted_price': predicted_price_3,
                        'confidence': '低'
                    })
                steps.append(f"【步骤6】预测买点:共预测 {len(predicted_points)} 个未来买点")
            result['predicted_points'] = predicted_points
            result['spacing_analysis'] = spacing_analysis
            result['calculation_steps'] = steps
            # 生成分析说明
            analysis = []
            analysis.append(f"识别到 {len(buy_points)} 个历史买点(MACD金叉+均线多头+WR低位)")
            if buy_points:
                analysis.append("\n历史买点详情:")
                for i, point in enumerate(buy_points, 1):
                    analysis.append(f"  买点{i}:日期={point['date']}, 价格={point['price']:.2f}, DIF={point['dif']:.4f}, DEA={point['dea']:.4f}, WR={point['wr']:.2f}")
            if spacing_analysis:
                analysis.append("\n间距分析:")
                for item in spacing_analysis:
                    analysis.append(f"  {item}")
            if predicted_points:
                analysis.append("\n预测买点:")
                for point in predicted_points:
                    analysis.append(f"  {point['type']}:约{point['spacing']}, 预测价格={point['predicted_price']:.2f}, 置信度={point['confidence']}")
            if not buy_points:
                analysis.append("未找到满足条件的买点,请调整参数或查看更多历史数据")
            result['analysis'] = analysis
            result['success'] = True
            result['message'] = '计算完成'
        except Exception as e:
            result['message'] = f'计算失败: {e}'
            import traceback
            traceback.print_exc()
        return result

    def _calculate_ema(self, data, period):
        """计算EMA"""
        if len(data) < period:
            return np.zeros(len(data))
        ema = np.zeros(len(data))
        ema[period-1] = np.mean(data[:period])
        multiplier = 2 / (period + 1)
        for i in range(period, len(data)):
            ema[i] = data[i] * multiplier + ema[i-1] * (1 - multiplier)
        return ema

    def _calculate_ma(self, data, period):
        """计算MA"""
        if len(data) < period:
            return np.zeros(len(data))
        ma = np.zeros(len(data))
        ma[period-1:] = np.convolve(data, np.ones(period)/period, mode='valid')
        return ma

    def _calculate_wr(self, high, low, close, period):
        """计算WR"""
        if len(close) < period:
            return np.zeros(len(close))
        wr = np.zeros(len(close))
        for i in range(period-1, len(close)):
            h_n = np.max(high[i-period+1:i+1])
            l_n = np.min(low[i-period+1:i+1])
            if h_n == l_n:
                wr[i] = -50
            else:
                wr[i] = (h_n - close[i]) / (h_n - l_n) * (-100)
        return wr

    def _calculate_cci(self, high, low, close, period):
        """计算CCI"""
        if len(close) < period:
            return np.zeros(len(close))
        tp = (high + low + close) / 3
        cci = np.zeros(len(close))
        for i in range(period-1, len(close)):
            ma_tp = np.mean(tp[i-period+1:i+1])
            md = np.mean(np.abs(tp[i-period+1:i+1] - ma_tp))
            if md == 0:
                cci[i] = 0
            else:
                cci[i] = (tp[i] - ma_tp) / (0.015 * md)
        return cci

    def _calculate_obv(self, close, volume):
        """计算OBV"""
        obv = np.zeros(len(close))
        obv[0] = volume[0]
        for i in range(1, len(close)):
            if close[i] > close[i-1]:
                obv[i] = obv[i-1] + volume[i]
            elif close[i] < close[i-1]:
                obv[i] = obv[i-1] - volume[i]
            else:
                obv[i] = obv[i-1]
        return obv

    def _calculate_dmi(self, high, low, close, period):
        """计算DMI"""
        if len(close) < period + 1:
            return {'plus_di': np.zeros(len(close)), 'minus_di': np.zeros(len(close)), 'adx': np.zeros(len(close))}
        # 计算TR
        tr = np.zeros(len(close))
        tr[0] = high[0] - low[0]
        for i in range(1, len(close)):
            tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
        # 计算+DM和-DM
        plus_dm = np.zeros(len(close))
        minus_dm = np.zeros(len(close))
        for i in range(1, len(close)):
            up_move = high[i] - high[i-1]
            down_move = low[i-1] - low[i]
            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            if down_move > up_move and down_move > 0:
                minus_dm[i] = down_move
        # 计算+DI和-DI
        plus_di = np.zeros(len(close))
        minus_di = np.zeros(len(close))
        atr = np.zeros(len(close))
        atr[period-1] = np.mean(tr[:period])
        for i in range(period, len(close)):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
            plus_di[i] = (np.sum(plus_dm[i-period+1:i+1]) / atr[i]) * 100
            minus_di[i] = (np.sum(minus_dm[i-period+1:i+1]) / atr[i]) * 100
        # 计算ADX
        adx = np.zeros(len(close))
        dx = np.zeros(len(close))
        for i in range(period, len(close)):
            if plus_di[i] + minus_di[i] == 0:
                dx[i] = 0
            else:
                dx[i] = abs(plus_di[i] - minus_di[i]) / (plus_di[i] + minus_di[i]) * 100
        for i in range(period * 2 - 1, len(close)):
            adx[i] = np.mean(dx[i-period+1:i+1])
        return {'plus_di': plus_di, 'minus_di': minus_di, 'adx': adx}

    def _ema_np(self, arr, span):
        """指数移动平均(pandas ewm,与常见行情软件可略有差异)。"""
        s = pd.Series(np.asarray(arr, dtype=float))
        return s.ewm(span=float(span), adjust=False).mean().values

    def _risk_filter_stock(self, stock_code, stock_name="", kline_data=None, fundamental=None):
        """T5: 全局风控过滤器"""
        result = {"pass": True, "reasons": [], "warnings": []}
        try:
            close_price = None
            if kline_data and kline_data.get('data') is not None:
                df = kline_data['data']
                if len(df) > 0:
                    close_price = float(df['收盘'].values[-1])
            if close_price is not None and close_price < 20:
                result["pass"] = False
                result["reasons"].append(f"股价{close_price:.2f}元<20元,不满足硬标准")
            if kline_data and kline_data.get('data') is not None:
                df = kline_data['data']
                if len(df) >= 60:
                    closes = df['收盘'].values
                    pct_change = (closes[-1] / closes[-60] - 1) * 100
                    if pct_change > 100:
                        result["pass"] = False
                        result["reasons"].append(f"近60日涨幅{pct_change:.1f}%>100%,回避")
                    elif pct_change > 50:
                        result["warnings"].append(f"近60日涨幅{pct_change:.1f}%较高,注意风险")
            if kline_data and kline_data.get('data') is not None:
                p_phase = self._p_phase_classify(kline_data)
                if p_phase.get("phase") == "P3":
                    result["pass"] = False
                    result["reasons"].append("P3狂热期(出货区),不碰")
                elif p_phase.get("phase") == "P0":
                    result["warnings"].append("P0衰退期,需谨慎")
            if fundamental and isinstance(fundamental, dict):
                market_cap = fundamental.get("market_cap", 0)
                if market_cap and market_cap < 100e8:
                    result["warnings"].append(f"市值{market_cap/1e8:.0f}亿<100亿,偏小盘")
                revenue_growth = fundamental.get("revenue_growth", 0)
                if revenue_growth and revenue_growth < 15:
                    result["warnings"].append(f"营收增长{revenue_growth:.1f}%<15%")
        except Exception as e:
            result["warnings"].append(f"风控检查异常: {e}")
        return result

    def _duanji_score(self, stock_code, kline_data=None, fundamental=None):
        """T2-DJ: 段基(段永平)7维基本面评分系统,总分105"""
        scores = {"商业模式": 0, "盈利质量": 0, "成长性": 0, "现金流": 0, "安全边际": 0, "护城河": 0, "估值": 0}
        details = {}
        try:
            if kline_data and kline_data.get('data') is not None:
                df = kline_data['data']
                if len(df) > 0:
                    close_price = float(df['收盘'].values[-1])
                    if len(df) >= 20:
                        closes = df['收盘'].values
                        ret_20d = (closes[-1] / closes[-20] - 1) * 100
                        scores["成长性"] = 12 if ret_20d > 10 else (8 if ret_20d > 0 else 4)
                        details["近20日涨幅"] = f"{ret_20d:.1f}%"
                    if len(df) >= 20:
                        vols = df['成交量'].values[-20:]
                        vol_cv = float(np.std(vols) / (np.mean(vols) + 1e-9))
                        scores["现金流"] = 12 if vol_cv < 0.5 else (8 if vol_cv < 1.0 else 4)
                        details["量能波动率"] = f"{vol_cv:.2f}"
                    if len(df) >= 60:
                        closes = df['收盘'].values
                        mean_60 = float(np.mean(closes[-60:]))
                        deviation = (close_price / mean_60 - 1) * 100
                        scores["安全边际"] = 13 if deviation < -5 else (10 if deviation < 0 else (7 if deviation < 10 else 3))
                        details["偏离60日均值"] = f"{deviation:.1f}%"
                    if 'ma_values' in kline_data:
                        ma20 = kline_data['ma_values'].get('ma20', [])
                        if ma20 and len(ma20) > 0:
                            ma20_val = float(ma20[-1])
                            pe_proxy = close_price / ma20_val
                            scores["估值"] = 13 if pe_proxy < 0.95 else (10 if pe_proxy < 1.05 else (6 if pe_proxy < 1.15 else 3))
                            details["价格/MA20"] = f"{pe_proxy:.2f}"
            if fundamental and isinstance(fundamental, dict):
                roe = fundamental.get("roe", 0)
                if roe:
                    scores["盈利质量"] = 14 if roe > 20 else (10 if roe > 10 else 5)
                    details["ROE"] = f"{roe:.1f}%"
                rev_growth = fundamental.get("revenue_growth", 0)
                if rev_growth and rev_growth > 20:
                    scores["成长性"] = max(scores["成长性"], 13)
                inst_hold = fundamental.get("institutional_holding", 0)
                if inst_hold:
                    scores["护城河"] = 14 if inst_hold > 50 else (10 if inst_hold > 30 else 5)
                    scores["商业模式"] = 12 if inst_hold > 50 else (9 if inst_hold > 30 else 6)
                    details["机构持仓"] = f"{inst_hold:.1f}%"
            for k in scores:
                if scores[k] == 0:
                    scores[k] = 7
        except Exception:
            pass
        total = sum(scores.values())
        verdict = "优秀(值得深入研究)" if total >= 80 else ("良好(可关注)" if total >= 65 else ("一般(需谨慎)" if total >= 50 else "较差(建议回避)"))
        return {"total": total, "max": 105, "scores": scores, "verdict": verdict, "details": details}

    def _munger_5pct_scan(self, stock_code, kline_data=None, market_data=None):
        """T2-MG: 芒格5%机会扫描器(大周期反转)"""
        result = {"triggered": False, "group": "", "signal": "", "details": {}}
        try:
            if kline_data and kline_data.get('data') is not None:
                df = kline_data['data']
                if len(df) >= 20:
                    closes = df['收盘'].values
                    ret_20d = (closes[-1] / closes[-20] - 1) * 100
                    ret_5d = (closes[-1] / closes[-5] - 1) * 100 if len(closes) >= 5 else 0
                    result["details"]["近5日跌幅"] = f"{ret_5d:.1f}%"
                    result["details"]["近20日跌幅"] = f"{ret_20d:.1f}%"
                    if ret_20d < -40:
                        result.update({"triggered": True, "group": "D-极端恐慌", "signal": "🔴极端恐慌,大周期反转机会"})
                    elif ret_20d < -20:
                        result.update({"triggered": True, "group": "C-个股超跌", "signal": "🟡个股超跌>20%,关注反弹"})
                    elif ret_5d < -10:
                        result.update({"triggered": True, "group": "C-短期超跌", "signal": "🟡短期超跌,观察支撑"})
            if market_data and isinstance(market_data, dict):
                up_count = market_data.get("up_count", 0)
                if up_count and up_count < 800:
                    result.update({"triggered": True, "group": "A-大盘恐慌", "signal": "🔴大盘恐慌(上涨<800),系统性机会"})
        except Exception as e:
            result["details"]["error"] = str(e)
        return result

    def _p_phase_classify(self, kline_data):
        """T2-PP: P阶段分类(P0衰退/P1低估/P2改善/P3狂热)"""
        result = {"phase": "P1", "score": {}, "description": ""}
        try:
            if kline_data and kline_data.get('data') is not None:
                df = kline_data['data']
                closes = df['收盘'].values
                vols = df['成交量'].values
                n = len(closes)
                if n < 20:
                    return result
                ma20 = float(np.mean(closes[-20:])) if n >= 20 else float(np.mean(closes))
                ma60 = float(np.mean(closes[-60:])) if n >= 60 else ma20
                close = float(closes[-1])
                val_score = 2 if close < ma20 * 0.95 else (1 if close < ma20 * 1.05 else (4 if close > ma60 * 1.15 else 3))
                ret_20d = (closes[-1] / closes[-20] - 1) * 100 if n >= 20 else 0
                fund_score = 2 if ret_20d < -10 else (3 if ret_20d < 5 else (4 if ret_20d < 20 else 5))
                vol_ratio = float(vols[-1] / (np.mean(vols[-20:]) + 1e-9)) if n >= 20 else 1.0
                deviation = abs(close / ma20 - 1) * 100
                emo_score = 1 if (vol_ratio < 0.8 and deviation < 3) else (2 if vol_ratio < 1.2 else (3 if vol_ratio < 2.0 else (4 if vol_ratio < 3.0 else 5)))
                result["score"] = {"估值": val_score, "基本面": fund_score, "情绪": emo_score, "近20日涨跌": f"{ret_20d:.1f}%", "量比": f"{vol_ratio:.2f}"}
                total = val_score + fund_score + emo_score
                if total <= 5:
                    result.update({"phase": "P0", "description": "衰退期(估值低+基本面差+情绪冰点)"})
                elif total <= 8:
                    result.update({"phase": "P1", "description": "低估期(估值偏低+基本面待改善)"})
                elif total <= 11:
                    result.update({"phase": "P2", "description": "改善期(估值合理+基本面向好+情绪活跃)"})
                else:
                    result.update({"phase": "P3", "description": "狂热期(估值高+涨幅大+情绪亢奋,出货区)"})
        except Exception:
            pass
        return result

    def _elevator_signal(self, kline_data):
        """T2-ZT: 坐电梯指标(通达信上下电梯)"""
        result = {"signal": "无", "fast": 0.0, "slow": 0.0, "action": "观望"}
        try:
            if kline_data and kline_data.get('data') is not None:
                df = kline_data['data']
                closes = df['收盘'].values
                n = len(closes)
                if n < 12:
                    return result
                N = 9
                ema = np.zeros(n)
                k = 2 / (N + 1)
                ema[0] = closes[0]
                for i in range(1, n):
                    ema[i] = closes[i] * k + ema[i-1] * (1 - k)
                if n >= 7:
                    ref_up = (ema[1:] > ema[:-1]).astype(float)
                    fast = np.sum(ref_up[-3:]) / 3 * 100
                    slow = np.sum(ref_up[-6:]) / 6 * 100
                    result["fast"] = float(fast)
                    result["slow"] = float(slow)
                    if n >= 8:
                        fast_prev = np.sum(ref_up[-4:-1]) / 3 * 100
                        slow_prev = np.sum(ref_up[-7:-1]) / 6 * 100
                        if fast > slow and fast_prev <= slow_prev:
                            result.update({"signal": "金叉", "action": "低买/进场"})
                        elif fast < slow and fast_prev >= slow_prev:
                            result.update({"signal": "死叉", "action": "高卖/出场"})
                        elif fast > slow:
                            result.update({"signal": "多头", "action": "持有"})
                        else:
                            result.update({"signal": "空头", "action": "观望"})
        except Exception:
            pass
        return result

    def _find_local_extrema(arr, window=3):
        """
        手动滑窗找局部波峰/波谷。
        返回 (peaks, troughs),每个是 [(index, value), ...] 按时间升序。
        window 至少 3,越大越"严格"(波峰/波谷之间需要至少 window 个点)。
        """
        import numpy as np
        arr = np.array(arr, dtype=float)
        n = len(arr)
        if n < window * 2 + 1:
            return [], []
        peaks = []
        troughs = []
        half = window // 2
        for i in range(half, n - half):
            left = arr[i - half:i]
            right = arr[i + 1:i + 1 + half]
            v = arr[i]
            if v > left.max() and v > right.max():
                peaks.append((i, v))
            elif v < left.min() and v < right.min():
                troughs.append((i, v))
        return peaks, troughs

    def _detect_divergence(self, prices, dif_arr, window=5, min_price_pct=0.0015, min_dif_diff=0.0):
        """
        检测价格-DIF 背离。
        window: 极值窗口(越大越严格)
        min_price_pct: 峰/谷之间最小价格变动百分比(默认0.15%,过滤噪音)
        min_dif_diff: DIF 差异最小值(绝对值)
        返回列表: [{'type': 'top'/'bottom', 'price1': ..., 'price2': ...,
                    'dif1': ..., 'dif2': ..., 'idx1': ..., 'idx2': ..., 'trigger_idx': ...,
                    'price_pct': ..., 'dif_diff': ...}, ...]
        """
        import numpy as np
        prices = np.array(prices, dtype=float)
        dif_arr = np.array(dif_arr, dtype=float)
        peaks, troughs = self._find_local_extrema(prices, window=window)
        results = []
        # 顶背离:价格波峰1→波峰2更高,但 DIF 更低 → 适合卖
        for i in range(len(peaks) - 1):
            idx1, p1 = peaks[i]
            idx2, p2 = peaks[i + 1]
            d1 = dif_arr[idx1]
            d2 = dif_arr[idx2]
            # 价格创新高 + DIF 降低 → 顶背离
            if p2 > p1 and d2 < d1:
                price_pct = (p2 - p1) / p1
                dif_diff = abs(d2 - d1)
                # 幅度过滤
                if price_pct < min_price_pct and dif_diff < min_dif_diff + 0.01:
                    continue
                results.append({
                    "type": "top",
                    "label": "顶背离",
                    "advice": "适合卖出(做T高抛)",
                    "price1": float(p1), "price2": float(p2),
                    "dif1": float(d1), "dif2": float(d2),
                    "idx1": idx1, "idx2": idx2,
                    "trigger_idx": idx2,
                    "price_pct": float(price_pct * 100),
                    "dif_diff": float(dif_diff),
                })
        # 底背离:价格波谷1→波谷2更低,但 DIF 更高 → 适合买
        for i in range(len(troughs) - 1):
            idx1, p1 = troughs[i]
            idx2, p2 = troughs[i + 1]
            d1 = dif_arr[idx1]
            d2 = dif_arr[idx2]
            # 价格创新低 + DIF 抬高 → 底背离
            if p2 < p1 and d2 > d1:
                price_pct = abs(p2 - p1) / p1
                dif_diff = abs(d2 - d1)
                if price_pct < min_price_pct and dif_diff < min_dif_diff + 0.01:
                    continue
                results.append({
                    "type": "bottom",
                    "label": "底背离",
                    "advice": "适合买入(做T低吸)",
                    "price1": float(p1), "price2": float(p2),
                    "dif1": float(d1), "dif2": float(d2),
                    "idx1": idx1, "idx2": idx2,
                    "trigger_idx": idx2,
                    "price_pct": float(price_pct * 100),
                    "dif_diff": float(dif_diff),
                })
        # 过滤过近的背离(idx差太小)
        filtered = []
        last_idx = -1000
        for r in results:
            if r["idx2"] - last_idx >= window * 2:
                filtered.append(r)
                last_idx = r["idx2"]
        # 按时间排序
        filtered.sort(key=lambda r: r["trigger_idx"])
        return filtered

    def _determine_market_stage(ma5, ma10, ma20, ma60, current_price):
        """
        判断大盘阶段 S1-S4（基于 MA 排列 + 价格位置）
        S1 强势上涨: MA5>MA10>MA20>MA60 且全部向上, 价>MA60较远
        S2 震荡上行: MA5>MA10>MA20, MA60可能还没跟上, 价在MA60上方
        S3 震荡下行: MA5<MA10<MA20, 价在MA60附近或略低
        S4 弱势下跌: MA5<MA10<MA20<MA60 且全部向下, 价<MA60较远
        """
        if None in (ma5, ma10, ma20, ma60, current_price):
            return "未知", "数据不足"
        # 多头/空头排列
        bull = ma5 > ma10 > ma20 > ma60
        bear = ma5 < ma10 < ma20 < ma60
        price_above_ma60 = current_price > ma60
        dist_pct = (current_price - ma60) / ma60 * 100
        if bull and price_above_ma60 and dist_pct > 1.5:
            return "S1", "强势上涨"
        if ma5 > ma10 > ma20 and price_above_ma60:
            return "S2", "震荡上行"
        if ma5 < ma10 < ma20 and not bear:
            return "S3", "震荡下行"
        if bear and not price_above_ma60 and dist_pct < -1.5:
            return "S4", "弱势下跌"
        # 兜底
        if price_above_ma60: return "S2", "震荡上行(价格在MA60之上)"
        return "S3", "震荡下行(价格在MA60附近)"

    def _show_market_risk_dashboard(self):
        """🚦 大盘风险仪表盘：估值+杠杆+量能+利率 四维度打分，输出逃顶/抄底信号"""
        import subprocess as _sp
        import tkinter as tk
        from tkinter import scrolledtext, ttk
        win = self._safe_toplevel(self.root)
        win.title("🚦 大盘风险仪表盘 · 逃顶/抄底")
        win.geometry("1200x820")
        win.transient(self.root)
        # ===== 顶部 Banner（风险等级配色）=====
        banner = tk.Frame(win, bg="#2F4F4F", height=60)
        banner.pack(fill=tk.X)
        banner.pack_propagate(False)
        bi = tk.Frame(banner, bg="#2F4F4F")
        bi.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
        tk.Label(bi, text="🚦 大盘风险仪表盘", font=("", 16, "bold"),
                 fg="white", bg="#2F4F4F").pack(side=tk.LEFT)
        risk_score_lbl = tk.Label(bi, text="--", font=("", 22, "bold"),
                                   fg="#FFD700", bg="#2F4F4F")
        risk_score_lbl.pack(side=tk.LEFT, padx=14)
        risk_level_lbl = tk.Label(bi, text="--", font=("", 14, "bold"),
                                   fg="white", bg="#2F4F4F")
        risk_level_lbl.pack(side=tk.LEFT)
        risk_action_lbl = tk.Label(bi, text="", font=("", 11),
                                    fg="#AAA", bg="#2F4F4F")
        risk_action_lbl.pack(side=tk.LEFT, padx=12)
        # ===== 控制栏 =====
        ctrl = tk.Frame(win)
        ctrl.pack(fill=tk.X, padx=10, pady=6)
        # 日期选择器
        import datetime as _dt3
        _today = _dt3.date.today().strftime("%Y-%m-%d")
        tk.Label(ctrl, text="📅 选择日期:", fg="#555").pack(side=tk.LEFT)
        date_var = tk.StringVar(value=_today)
        date_entry = tk.Entry(ctrl, textvariable=date_var, width=12, font=("", 11))
        date_entry.pack(side=tk.LEFT, padx=2)
        tk.Label(ctrl, text="(YYYY-MM-DD)", fg="#999", font=("", 9)).pack(side=tk.LEFT)
        trade_day_lbl = tk.Label(ctrl, text="", fg="#1565C0", font=("", 10))
        trade_day_lbl.pack(side=tk.LEFT, padx=6)
        # 快速跳转
        def _set_date(days_ago):
            d = _dt3.date.today() - _dt3.timedelta(days=days_ago)
            date_var.set(d.strftime("%Y-%m-%d"))
        tk.Button(ctrl, text="今天", command=lambda: _set_date(0), cursor="hand2").pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl, text="5天前", command=lambda: _set_date(5), cursor="hand2").pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl, text="1月前", command=lambda: _set_date(30), cursor="hand2").pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl, text="3月前", command=lambda: _set_date(90), cursor="hand2").pack(side=tk.LEFT, padx=2)
        tk.Label(ctrl, text="  |  ", fg="#CCC").pack(side=tk.LEFT)
        run_btn = tk.Button(ctrl, text="🔍 拉取数据 + 计算风险",
                            font=("", 11, "bold"), bg="#2F4F4F", fg="white",
                            padx=12, pady=3, cursor="hand2")
        run_btn.pack(side=tk.LEFT, padx=4)
        tk.Label(ctrl, text="四维度共振打分：估值40% + 杠杆25% + 量能20% + 利率15%",
                 fg="#666").pack(side=tk.LEFT, padx=14)
        # ===== 主内容区 =====
        main_frame = ttk.Frame(win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))
        # 左：4 维度条形图 + 原始数据卡片
        left = ttk.LabelFrame(main_frame, text="📊 四维度打分（共振越强越危险）", padding=8)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        dims_frame = tk.Frame(left, bg="white")
        dims_frame.pack(fill=tk.X, pady=(0, 10))
        # 动态创建维度条
        dim_widgets = {}  # name -> (canvas, score_lbl, desc_lbl)
        def _add_dim_row(parent, name, max_score, weight_color):
            row = tk.Frame(parent, bg="white")
            row.pack(fill=tk.X, pady=6)
            tk.Label(row, text=f"  {name}", font=("", 11, "bold"),
                     bg="white", width=8, anchor="w", fg="#333").pack(side=tk.LEFT)
            canvas = tk.Canvas(row, height=26, bg="#EEE", highlightthickness=0, width=400)
            canvas.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
            score_lbl = tk.Label(row, text="0/0", font=("", 11, "bold"),
                                  bg="white", fg="#555", width=8, anchor="e")
            score_lbl.pack(side=tk.LEFT, padx=4)
            desc_lbl = tk.Label(row, text="", font=("", 10), bg="white", fg="#888", width=22, anchor="e")
            desc_lbl.pack(side=tk.LEFT)
            dim_widgets[name] = (canvas, score_lbl, desc_lbl, max_score)
            return canvas
        _add_dim_row(dims_frame, "估值", 40, "#1976D2")
        _add_dim_row(dims_frame, "杠杆", 25, "#FF9800")
        _add_dim_row(dims_frame, "量能", 20, "#4CAF50")
        _add_dim_row(dims_frame, "利率", 15, "#9C27B0")
        # 原始数据卡片
        raw_card = tk.Frame(left, bg="#F5F5DC")
        raw_card.pack(fill=tk.BOTH, expand=True)
        ttk.Label(raw_card, text="📋 原始数据", font=("", 11, "bold")).pack(anchor=tk.W, padx=8, pady=(6, 2))
        raw_txt = scrolledtext.ScrolledText(raw_card, wrap=tk.WORD, height=12,
                                             font=("Menlo", 10), bg="#FDFBF0")
        raw_txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        # 右：报告 + 逃顶/抄底方法论
        right = ttk.LabelFrame(main_frame, text="📝 分析报告 + 逃顶/抄底方法论", padding=8)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        report_txt = scrolledtext.ScrolledText(right, wrap=tk.WORD,
                                                font=("Microsoft YaHei", 10))
        report_txt.pack(fill=tk.BOTH, expand=True)
        report_txt.insert("1.0",
            "🚦 大盘风险仪表盘 — 四维度共振打分\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "维度          权重    数据源\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 估值层      40%    全市场PB 10年分位\n"
            "📈 杠杆层      25%    融资余额 1年分位\n"
            "💰 量能层      20%    两市成交额\n"
            "🏦 利率层      15%    10年国债收益率 5年分位\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "逃顶组合信号（单一易骗线，共振才行动）：\n"
            "  估值顶  = PE/PB 破历史 90% 分位 + 巴菲特指标>120%\n"
            "  资金顶  = 融资天量 + 新基爆款 + 散户开户暴增\n"
            "  技术顶  = 天量 + 顶背离 + 年线大乖离\n"
            "  政策顶  = 监管降温 + 官媒喊话\n\n"
            "抄底（顶部反向）：\n"
            "  估值底 = PE/PB 历史低位\n"
            "  政策底 = 国家队/降准/重要会议\n"
            "  市场底 = 缩量最后一跌 + 恐慌抛售\n"
            "  情绪底 = 基金冰点 + 销户潮 + 无人谈股\n\n"
            "💡 多维度共振才动手，单一信号容易假突破！\n\n"
            "点击「🔍 拉取最新数据」开始...")
        # ===== 状态条 =====
        status_var = tk.StringVar(value="就绪 · 每周五 16:30 自动跑（cron）")
        ttk.Label(win, textvariable=status_var, anchor=tk.W).pack(fill=tk.X, padx=10, pady=(0, 4))
        # ===== 填充维度条形图 =====
        def _draw_bar(canvas, pct, color="#E74C3C", label=""):
            canvas.delete("all")
            w = canvas.winfo_width() or 400
            h = 26
            canvas.create_rectangle(0, 0, w, h, fill="#F0F0F0", outline="")
            bw = int(w * min(pct, 1.0))
            if bw > 0:
                # 渐变效果：绿→黄→红
                if pct < 0.4: color = "#27AE60"
                elif pct < 0.7: color = "#F39C12"
                else: color = "#E74C3C"
                canvas.create_rectangle(0, 0, bw, h, fill=color, outline="")
            canvas.create_text(w // 2, h // 2, text=label, fill="white", font=("", 10, "bold"))
        def _update_risk_ui(data):
            risk = data.get("risk", {})
            score = risk.get("risk_score", 0)
            level = risk.get("level", "--")
            action = risk.get("action", "")
            # 颜色映射
            if score >= 82: bg, fg = "#8B0000", "#FFD700"       # 极度危险
            elif score >= 65: bg, fg = "#C62828", "white"       # 高风险
            elif score >= 45: bg, fg = "#E67E22", "white"       # 正常偏热
            elif score >= 25: bg, fg = "#27AE60", "white"       # 正常偏低
            else: bg, fg = "#1B5E20", "#FFD700"                 # 底部区域
            banner.configure(bg=bg); bi.configure(bg=bg)
            risk_score_lbl.configure(bg=bg, fg=fg, text=f"{score}")
            risk_level_lbl.configure(bg=bg, fg="white", text=f" [{level}]")
            risk_action_lbl.configure(bg=bg, fg="#FFD700", text=action)
            # 4 维度条形图
            dims = risk.get("dims", {})
            for name, info in dims.items():
                w = dim_widgets.get(name)
                if not w: continue
                canvas, score_lbl, desc_lbl, max_s = w
                sc = info.get("score", 0)
                pct = sc / max_s if max_s else 0
                _draw_bar(canvas, pct, label=f"{sc}/{max_s}  ({pct*100:.0f}%)")
                score_lbl.configure(text=f"{sc}/{max_s}")
                desc_lbl.configure(text=info.get("desc", ""))
            # 原始数据
            raw = data.get("data", {})
            lines = ["═══ 原始数据 ═══", ""]
            # 查询日/实际交易日
            qd = raw.get("query_date", "")
            ad = raw.get("actual_date", "")
            if qd and ad and qd != ad:
                lines.append(f"📅 查询日 {qd} → 实际交易日 {ad}（非交易日自动回退）")
            elif qd == ad:
                lines.append(f"📅 交易日 {qd}")
            lines.append("")
            pb = raw.get("pb", {})
            if pb:
                q_qtl = pb.get('pb_quantile_10y')
                q_str = f"{q_qtl*100:.1f}%" if q_qtl is not None else "N/A"
                lines.append("💎 PB/PE (10年分位):")
                lines.append(f"   上证 {pb.get('close','?')}  PB={pb.get('middlePB','?')}  分位={q_str}")
            margin = raw.get("margin", {})
            if margin:
                m_pct = margin.get('balance_pct_1y')
                m_str = f"{m_pct*100:.1f}%" if m_pct is not None else "N/A"
                lines.append("📈 融资余额:")
                lines.append(f"   沪深合计 {margin.get('balance_total_yi',0):.0f}亿  买入={margin.get('buy_yi',0):.0f}亿  1年分位={m_str}")
            turnover = raw.get("turnover", {})
            if turnover:
                lines.append("💰 两市成交:")
                if turnover.get('total_trillion') is not None:
                    lines.append(f"   沪 {turnover.get('sh_amount_yi',0):.0f}亿 + 深 {turnover.get('sz_amount_yi',0):.0f}亿 = 合计 {turnover.get('total_trillion',0):.2f}万亿")
                else:
                    lines.append(f"   {turnover.get('_note','历史缺失')}")
            bond = raw.get("bond", {})
            if bond:
                b_pct = bond.get('yield_pct_5y')
                b_str = f"{b_pct*100:.1f}%" if b_pct is not None else "N/A"
                lines.append("🏦 10年国债收益率:")
                lines.append(f"   {bond.get('yield_10y',0):.2f}%  5年分位={b_str}")
            lines.append("")
            lines.append(f"⏰ 更新时间: {data.get('time', '?')}")
            raw_txt.delete("1.0", tk.END)
            raw_txt.insert("1.0", "\n".join(lines))
            # 四指数涨跌统计表格
            idx_ret = data.get("index_returns", {})
            for row_id in idx_tv.get_children():
                idx_tv.delete(row_id)
            if idx_ret and "indices" in idx_ret:
                def _pct_fmt(v):
                    if v is None: return "—", ""
                    s = f"{v:+.2f}%"
                    tag = "up" if v > 0 else ("down" if v < 0 else "")
                    return s, tag
                for idx_name, info in idx_ret["indices"].items():
                    if "error" in info:
                        idx_tv.insert("", tk.END, values=(idx_name, "ERR", "—", "—", "—", "—"))
                        continue
                    bc = f"{info.get('base_close', 0):.2f}"
                    p5, t5 = _pct_fmt(info.get("5d", {}).get("pct"))
                    p10, t10 = _pct_fmt(info.get("10d", {}).get("pct"))
                    p20, t20 = _pct_fmt(info.get("20d", {}).get("pct"))
                    pnow, tnow = _pct_fmt(info.get("till_now", {}).get("pct"))
                    tags = (t5, t10, t20, tnow)
                    idx_tv.insert("", tk.END, values=(idx_name, bc, p5, p10, p20, pnow), tags=tags)
                idx_tv.tag_configure("up", foreground="#C62828")
                idx_tv.tag_configure("down", foreground="#2E7D32")
            else:
                for _ in range(4):
                    idx_tv.insert("", tk.END, values=("—", "—", "—", "—", "—", "—"))
            # 报告
            report_txt.delete("1.0", tk.END)
            report_txt.insert("1.0", self._format_dashboard_report(data))
        # ===== 四指数涨跌统计表格（嵌入原始数据卡片下方）=====
        idx_card = tk.Frame(left, bg="#E8F5E9")
        idx_card.pack(fill=tk.X, pady=(6, 0))
        tk.Label(idx_card, text="📈 后续涨跌统计（基准日 → +5/+10/+20 交易日 → 至今）",
                 font=("", 10, "bold"), bg="#E8F5E9", fg="#2E7D32").pack(anchor=tk.W, padx=8, pady=(4, 2))
        idx_cols = ("指数", "基准收盘", "+5日", "+10日", "+20日", "至今")
        idx_tv = ttk.Treeview(idx_card, columns=idx_cols, show="headings", height=5)
        for c, w in [("指数", 80), ("基准收盘", 80), ("+5日", 72), ("+10日", 72), ("+20日", 72), ("至今", 72)]:
            idx_tv.heading(c, text=c)
            idx_tv.column(c, width=w, anchor="center")
        idx_tv.pack(fill=tk.X, padx=8, pady=(0, 6))
        # 空行占位
        for _ in range(4):
            idx_tv.insert("", tk.END, values=("—", "—", "—", "—", "—", "—"))
        # ===== 跑 CLI =====
        import threading
        def _run():
            status_var.set("拉取数据中...")
            try:
                cmd = [sys.executable, self.SKILL_DASHBOARD_SCRIPT, "--json"]
                sel_date = date_var.get().strip()
                if sel_date and sel_date != _today:
                    cmd += ["--date", sel_date]
                proc = _sp.run(cmd, capture_output=True, text=True, timeout=90)
                out = proc.stdout.strip()
                i = out.find("{")
                if i < 0:
                    raise RuntimeError(f"无 JSON 输出: {out[:200]}")
                data = json.loads(out[i:])
                # 显示交易日回退提示
                qd = data.get("data", {}).get("query_date", "")
                ad = data.get("data", {}).get("actual_date", "")
                if qd and ad and qd != ad:
                    win.after(0, lambda: trade_day_lbl.configure(
                        text=f"📂 {qd} 为非交易日 → 回退到 {ad}", fg="#E65100"))
                else:
                    win.after(0, lambda: trade_day_lbl.configure(
                        text=f"📂 交易日 {ad}", fg="#1565C0"))
                win.after(0, lambda: _update_risk_ui(data))
                win.after(0, lambda: status_var.set("✅ 完成"))
            except Exception as e:
                win.after(0, lambda e=e: status_var.set(f"❌ 失败: {e}"))
                win.after(0, lambda e=e: report_txt.delete("1.0", tk.END))
                win.after(0, lambda e=e: report_txt.insert("1.0", f"❌ 拉取失败: {e}"))
        run_btn.configure(command=lambda: threading.Thread(target=_run, daemon=True).start())
        # 立即拉一次
        threading.Thread(target=_run, daemon=True).start()

    def _show_wall_street_traffic_light(self):
        """🏦 华尔街红绿灯: 6 大量化情绪指标 → 综合红黄绿判定 + AI 解读"""
        import datetime
        import json
        import os
        import ssl
        import threading
        import tkinter as tk
        from tkinter import scrolledtext
        ssl._create_default_https_context = ssl._create_unverified_context
        DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(DATA_DIR, exist_ok=True)
        CACHE_FILE = os.path.join(DATA_DIR, "wall_street_cache.json")
        win = self._safe_toplevel(self.root)
        win.title("🏦 华尔街红绿灯 · 市场情绪量化判定")
        win.geometry("1280x920")
        win.minsize(1100, 780)
        now = datetime.datetime.now()
        banner_color = "#BF360C"  # 橙红色
        # ===== Banner =====
        banner = tk.Frame(win, bg=banner_color, height=56); banner.pack(fill=tk.X)
        tk.Label(banner, text="🏦 华尔街红绿灯", bg=banner_color, fg="white",
                 font=("", 16, "bold")).pack(side=tk.LEFT, padx=14, pady=10)
        tk.Label(banner, text=(
            "CNN恐慌贪婪 · VIX · AAII散户 · 融资债务 · 市场广度 · 综合情绪 — "
            f"{now.strftime('%Y-%m-%d %H:%M')}"
        ), bg=banner_color, fg="#FFCCBC", font=("", 11)).pack(side=tk.LEFT, pady=14)
        # ===== 控制区 =====
        ctrl = tk.Frame(win); ctrl.pack(fill=tk.X, padx=10, pady=6)
        ai_var = tk.BooleanVar(value=True)
        tk.Checkbutton(ctrl, text="📝 自动AI解读", variable=ai_var, font=("", 10)).pack(side=tk.LEFT)
        scan_btn = tk.Button(ctrl, text="🔍 扫描华尔街情绪", font=("", 11, "bold"),
                             bg=banner_color, fg="white", padx=16, pady=3, cursor="hand2")
        scan_btn.pack(side=tk.LEFT, padx=10)
        status_var = tk.StringVar(value="⏳ 等待扫描...")
        tk.Label(ctrl, textvariable=status_var, font=("", 10), fg="#666").pack(side=tk.LEFT, padx=10)
        # ===== 上半: 6 大指标红绿灯卡片 =====
        top_frame = tk.Frame(win); top_frame.pack(fill=tk.X, padx=10, pady=8)
        indicator_cards = {}  # name -> {'card': Frame, 'light': Label, 'val': Label, 'desc': Label}
        INDICATORS = [
            ("CNN 恐慌贪婪", "cnn_fng", "综合情绪指标 0-100", "#5D4037"),
            ("VIX 恐慌指数", "vix", "期权波动率 恐慌/贪婪", "#4A148C"),
            ("美股指数MA", "us_idx", "标普/纳指/道指趋势", "#01579B"),
            ("量能活跃度", "volume", "5日/20日成交量比", "#1B5E20"),
            ("黄金避险", "gold", "黄金5日涨跌幅", "#FF6F00"),
            ("密歇根信心", "umich", "美国消费者信心指数", "#880E4F"),
        ]
        for i, (title, key, desc, color) in enumerate(INDICATORS):
            card = tk.Frame(top_frame, bg="white", highlightbackground="#DDD",
                           highlightthickness=2, padx=10, pady=10)
            card.grid(row=i // 3, column=i % 3, padx=6, pady=6, sticky="nsew")
            top_frame.grid_columnconfigure(i % 3, weight=1, uniform="col")
            # 标题行
            header = tk.Frame(card, bg="white")
            header.pack(fill=tk.X)
            tk.Label(header, text=title, font=("", 11, "bold"), fg=color,
                     bg="white").pack(side=tk.LEFT)
            # 红绿灯 + 当前值
            row1 = tk.Frame(card, bg="white"); row1.pack(fill=tk.X, pady=4)
            light = tk.Label(row1, text="⚫", font=("", 28), bg="white")
            light.pack(side=tk.LEFT)
            val = tk.Label(row1, text="--", font=("", 14, "bold"), fg="#333",
                          bg="white")
            val.pack(side=tk.LEFT, padx=8)
            # 描述
            desc_label = tk.Label(card, text=desc, font=("", 9), fg="#888",
                                 bg="white", wraplength=180, justify="left")
            desc_label.pack(fill=tk.X, pady=(2, 0))
            indicator_cards[key] = {'card': card, 'light': light, 'val': val, 'desc': desc_label}
        # ===== 中间: 综合红绿灯大卡片 =====
        mid_frame = tk.Frame(win, bg="white", highlightbackground="#DDD",
                            highlightthickness=2, padx=20, pady=14)
        mid_frame.pack(fill=tk.X, padx=10, pady=8)
        mid_left = tk.Frame(mid_frame, bg="white"); mid_left.pack(side=tk.LEFT, fill=tk.Y)
        traffic_light = tk.Label(mid_left, text="⚫", font=("", 64), bg="white")
        traffic_light.pack(side=tk.LEFT, padx=10)
        mid_right = tk.Frame(mid_frame, bg="white"); mid_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(mid_right, text="🏁 华尔街综合红绿灯", font=("", 14, "bold"),
                 bg="white", fg="#333").pack(anchor="w")
        score_var = tk.StringVar(value="综合评分: --/100")
        tk.Label(mid_right, textvariable=score_var, font=("", 22, "bold"),
                 bg="white", fg=banner_color).pack(anchor="w", pady=4)
        level_var = tk.StringVar(value="等待扫描...")
        tk.Label(mid_right, textvariable=level_var, font=("", 13),
                 bg="white", fg="#555").pack(anchor="w")
        signals_var = tk.StringVar(value="")
        tk.Label(mid_right, textvariable=signals_var, font=("", 10),
                 bg="white", fg="#666", wraplength=600, justify="left").pack(anchor="w", pady=(6, 0))
        # ===== 底部: AI 解读区 =====
        ai_frame = tk.LabelFrame(win, text="📝 AI 策略解读", font=("", 11, "bold"),
                                fg="#333", padx=8, pady=6)
        ai_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))
        report_txt = scrolledtext.ScrolledText(ai_frame, font=("", 10), wrap=tk.WORD,
                                              height=12, bg="#FAFAFA")
        report_txt.pack(fill=tk.BOTH, expand=True)
        # ===== 核心: 数据采集函数 =====
        def _scan_wall_street():
            """采集 6 类指标数据"""
            import akshare as ak
            data = {'signals': []}
            # 1️⃣ CNN 恐慌贪婪
            try:
                r = requests.get("https://api.alternative.me/fng/?limit=10", timeout=15,
                                 headers={'User-Agent': 'Mozilla/5.0'})
                d = r.json()
                fng = int(d['data'][0]['value'])
                fng_class = d['data'][0]['value_classification']
                fng_avg = sum(int(x['value']) for x in d['data']) / len(d['data'])
                data['cnn_fng'] = {'current': fng, 'class': fng_class, 'avg10': fng_avg}
            except Exception as e:
                data['cnn_fng'] = {'error': str(e)[:60]}
            # 2️⃣ 美股指数 (akshare)
            idx_results = {}
            for sym, name in [(".INX", "标普500"), (".IXIC", "纳指"), (".DJI", "道指")]:
                try:
                    df = ak.index_us_stock_sina(symbol=sym)
                    if df is not None and len(df) >= 60:
                        cur = float(df['close'].iloc[-1])
                        ma20 = float(df['close'].tail(20).mean())
                        ma60 = float(df['close'].mean())
                        chg_5 = (cur / float(df['close'].iloc[-5]) - 1) * 100 if len(df) >= 5 else 0
                        chg_20 = (cur / float(df['close'].iloc[-20]) - 1) * 100
                        vol_5 = float(df['volume'].tail(5).mean())
                        vol_20 = float(df['volume'].tail(20).mean())
                        vol_ratio = vol_5 / vol_20 if vol_20 > 0 else 1
                        ma_trend = ("多头" if cur > ma20 > ma60 else
                                    "空头" if cur < ma20 < ma60 else "震荡")
                        idx_results[name] = {
                            'close': cur, 'ma20': ma20, 'ma60': ma60,
                            'chg_5d': chg_5, 'chg_20d': chg_20, 'vol_ratio': vol_ratio,
                            'ma_trend': ma_trend
                        }
                except Exception as e:
                    idx_results[name] = {'error': str(e)[:60]}
            data['indices'] = idx_results
            # 3️⃣ 黄金
            try:
                df = ak.futures_main_sina(symbol="AU0", start_date="20260801", end_date="20260831")
                if df is not None and len(df) >= 5:
                    cur_g = float(df['收盘价'].iloc[-1])
                    chg_g = (cur_g / float(df['收盘价'].iloc[-5]) - 1) * 100
                    data['gold'] = {'price': cur_g, 'chg_5d': chg_g}
            except Exception as e:
                data['gold'] = {'error': str(e)[:60]}
            # 4️⃣ 密歇根信心
            try:
                df = safe_call(ak.macro_usa_michigan_consumer_sentiment, fallback=[], label="ak.macro_usa_michigan_consumer_sentiment")
                if df is not None and len(df) > 0:
                    row = df.tail(1).iloc[0]
                    cur_val = row.get('今值', None)
                    prev_val = row.get('前值', None)
                    if cur_val is not None and str(cur_val) != 'nan':
                        data['umich'] = {'current': float(cur_val),
                                         'prev': float(prev_val) if prev_val and str(prev_val) != 'nan' else None}
            except Exception as e:
                data['umich'] = {'error': str(e)[:60]}
            # 5️⃣ VIX (yfinance 可能限流, 跳过)
            try:
                import yfinance as yf
                v = yf.Ticker('^VIX')
                h = v.history(period='3mo')
                if h is not None and len(h) >= 5:
                    vix_cur = float(h['Close'].iloc[-1])
                    vix_ma20 = float(h['Close'].tail(20).mean())
                    data['vix'] = {'current': vix_cur, 'ma20': vix_ma20}
            except Exception as e:
                data['vix'] = {'error': str(e)[:40]}
            return data
        # ===== 综合红绿灯判定 =====
        def _judge_light(key, data):
            """返回 (color, icon, text) color=red/yellow/green/gray"""
            if key == 'cnn_fng':
                if 'error' in data: return ('gray', '⚫', '接口错误')
                f = data['current']
                c = data['class']
                if f >= 80: return ('red', '🔴', f'{f}({c}) 极度贪婪')
                if f >= 65: return ('yellow', '🟡', f'{f}({c}) 贪婪')
                if f <= 20: return ('green', '🟢', f'{f}({c}) 极度恐慌')
                if f <= 35: return ('yellow', '🟡', f'{f}({c}) 恐慌')
                return ('green', '🟢' if f >= 45 else '⚪', f'{f}({c}) 中性')
            if key == 'vix':
                if 'error' in data: return ('gray', '⚫', f'限流:{data["error"]}')
                v = data['current']
                if v > 30: return ('red', '🔴', f'VIX={v:.1f} 恐慌加剧')
                if v > 20: return ('yellow', '🟡', f'VIX={v:.1f} 温和恐慌')
                if v < 15: return ('green', '🟢', f'VIX={v:.1f} 市场平静')
                return ('green', '🟢', f'VIX={v:.1f} 正常')
            if key == 'us_idx':
                idx = data
                bull = sum(1 for v in idx.values() if isinstance(v, dict) and v.get('ma_trend') == '多头')
                bear = sum(1 for v in idx.values() if isinstance(v, dict) and v.get('ma_trend') == '空头')
                if bull >= 2:
                    details = [f"{n}={v['close']:.0f}({v['ma_trend']})" for n, v in idx.items() if isinstance(v, dict)]
                    return ('green', '🟢', f'{bull}/3多头 | ' + ' '.join(details))
                if bear >= 2:
                    details = [f"{n}={v['close']:.0f}({v['ma_trend']})" for n, v in idx.items() if isinstance(v, dict)]
                    return ('red', '🔴', f'{bear}/3空头 | ' + ' '.join(details))
                details = [f"{n}={v['close']:.0f}({v['ma_trend']})" for n, v in idx.items() if isinstance(v, dict)]
                return ('yellow', '🟡', '趋势分化 | ' + ' '.join(details))
            if key == 'volume':
                idx = data
                vols = [v.get('vol_ratio', 1) for v in idx.values() if isinstance(v, dict) and 'vol_ratio' in v]
                if not vols: return ('gray', '⚫', '无数据')
                avg_vol = sum(vols) / len(vols)
                if avg_vol > 1.3: return ('yellow', '🟡', f'量比={avg_vol:.2f} 放量活跃')
                if avg_vol < 0.7: return ('gray', '⚫', f'量比={avg_vol:.2f} 缩量冷清')
                return ('green', '🟢', f'量比={avg_vol:.2f} 正常')
            if key == 'gold':
                if 'error' in data: return ('gray', '⚫', '接口错误')
                if data['chg_5d'] > 3: return ('red', '🔴', f'黄金+{data["chg_5d"]:.1f}% 避险升温')
                if data['chg_5d'] > 1: return ('yellow', '🟡', f'黄金+{data["chg_5d"]:.1f}% 温和避险')
                if data['chg_5d'] < -2: return ('green', '🟢', f'黄金{data["chg_5d"]:.1f}% 风险偏好↑')
                return ('green', '🟢', f'黄金={data["price"]} 稳定')
            if key == 'umich':
                if 'error' in data or 'current' not in data: return ('gray', '⚫', '暂无新数据')
                u = data['current']
                if u < 55: return ('red', '🔴', f'密歇根={u} 悲观')
                if u > 70: return ('green', '🟢', f'密歇根={u} 乐观')
                return ('yellow', '🟡', f'密歇根={u} 中性')
            return ('gray', '⚫', '未知')
        def _update_card(card_key, color, icon, text):
            """UI 线程安全更新"""
            info = indicator_cards[card_key]
            info['light'].config(text=icon)
            info['val'].config(text=text, fg={
                'red': '#C62828', 'yellow': '#E65100',
                'green': '#2E7D32', 'gray': '#999'
            }.get(color, '#333'))
        def _calc_composite(data):
            """综合评分 0-100 (高=安全, 低=危险)"""
            score = 50
            signals = []
            # CNN FNG
            if 'cnn_fng' in data and 'error' not in data['cnn_fng']:
                f = data['cnn_fng']['current']
                if f >= 80: score -= 18; signals.append(('🔴', f'CNN FNG={f} 极度贪婪 风险放大'))
                elif f >= 65: score -= 8; signals.append(('🟡', f'CNN FNG={f} 贪婪 警惕回调'))
                elif f <= 20: score += 18; signals.append(('🟢', f'CNN FNG={f} 极度恐慌 或已筑底'))
                elif f <= 35: score += 8; signals.append(('🟡', f'CNN FNG={f} 恐慌 关注反弹'))
                else: signals.append(('⚪', f'CNN FNG={f} 中性'))
            # 美股指数
            if 'indices' in data:
                bull = sum(1 for v in data['indices'].values() if isinstance(v, dict) and v.get('ma_trend') == '多头')
                bear = sum(1 for v in data['indices'].values() if isinstance(v, dict) and v.get('ma_trend') == '空头')
                if bull >= 2: score += 12; signals.append(('🟢', f'{bull}/3美股指数多头排列 趋势健康'))
                elif bear >= 2: score -= 12; signals.append(('🔴', f'{bear}/3美股指数空头排列 趋势走坏'))
                else: signals.append(('⚪', '美股指数趋势分化'))
            # 量能
            if 'indices' in data:
                vols = [v.get('vol_ratio', 1) for v in data['indices'].values() if isinstance(v, dict)]
                if vols:
                    avg_v = sum(vols) / len(vols)
                    if avg_v > 1.3: score -= 3; signals.append(('🟡', f'量比={avg_v:.2f} 放量警惕过热'))
                    elif avg_v < 0.7: score += 2; signals.append(('⚪', f'量比={avg_v:.2f} 缩量观望'))
            # 黄金
            if 'gold' in data and 'error' not in data['gold']:
                g = data['gold']['chg_5d']
                if g > 3: score -= 6; signals.append(('🔴', f'黄金+{g:.1f}% 避险情绪急升'))
                elif g > 1: score -= 2; signals.append(('🟡', f'黄金+{g:.1f}% 温和避险'))
                elif g < -2: score += 4; signals.append(('🟢', f'黄金{g:.1f}% 风险偏好回升'))
            # VIX
            if 'vix' in data and 'error' not in data['vix']:
                v = data['vix']['current']
                if v > 30: score -= 10; signals.append(('🔴', f'VIX={v:.1f} 恐慌急升'))
                elif v > 20: score -= 4; signals.append(('🟡', f'VIX={v:.1f} 温和恐慌'))
                elif v < 15: score += 6; signals.append(('🟢', f'VIX={v:.1f} 市场平静'))
            # 密歇根信心
            if 'umich' in data and 'current' in data['umich']:
                u = data['umich']['current']
                if u < 55: score -= 4; signals.append(('🟡', f'密歇根信心={u} 偏低'))
                elif u > 70: score += 4; signals.append(('🟢', f'密歇根信心={u} 乐观'))
            score = max(0, min(100, score))
            level = ('🟢 绿灯·安全 (低仓位可加仓)' if score >= 65 else
                     '🟡 黄灯·警惕 (控制仓位)' if score >= 40 else
                     '🔴 红灯·危险 (减仓避险)')
            return score, level, signals
        # ===== 扫描按钮 =====
        def _run_scan():
            scan_btn.config(state=tk.DISABLED)
            status_var.set("⏳ 扫描华尔街情绪指标...")
            def _work():
                try:
                    data = _scan_wall_street()
                    # 更新 6 个卡片
                    card_keys = [
                        ('cnn_fng', 'cnn_fng'), ('vix', 'vix'),
                        ('us_idx', 'indices'), ('volume', 'indices'),
                        ('gold', 'gold'), ('umich', 'umich'),
                    ]
                    for card_key, data_key in card_keys:
                        d = data.get(data_key, {})
                        color, icon, text = _judge_light(card_key, d)
                        win.after(0, lambda c=card_key, cl=color, ic=icon, tx=text: _update_card(c, cl, ic, tx))
                    # 综合评分
                    score, level, signals = _calc_composite(data)
                    win.after(0, lambda: score_var.set(f"综合评分: {score}/100"))
                    win.after(0, lambda: level_var.set(level))
                    # 红绿灯颜色
                    if score >= 65:
                        traffic_light.config(text="🟢")
                    elif score >= 40:
                        traffic_light.config(text="🟡")
                    else:
                        traffic_light.config(text="🔴")
                    sig_text = "  ".join([f"{i}{d}" for i, d in signals[:6]])
                    win.after(0, lambda: signals_var.set(sig_text))
                    # 存缓存
                    try:
                        with open(CACHE_FILE, 'w') as f:
                            json.dump({**data, 'score': score, 'level': level,
                                      'signals': signals, 'time': now.strftime('%Y-%m-%d %H:%M')},
                                     f, default=str, ensure_ascii=False)
                    except Exception:
                        pass
                    # AI 解读
                    if ai_var.get():
                        win.after(0, lambda: status_var.set("🤖 AI 解读中..."))
                        _ai_interpret(data, score, level, signals)
                    else:
                        win.after(0, lambda: status_var.set(f"✅ 扫描完成! 评分 {score}/100"))
                except Exception as e:
                    import traceback
                    err = traceback.format_exc()
                    win.after(0, lambda: report_txt.delete("1.0", tk.END))
                    win.after(0, lambda e=e: report_txt.insert("1.0", f"❌ 扫描失败:\n{err[:2000]}"))
                    win.after(0, lambda e=e: status_var.set(f"❌ {str(e)[:60]}"))
                finally:
                    win.after(0, lambda: scan_btn.config(state=tk.NORMAL))
            threading.Thread(target=_work, daemon=True).start()
        def _ai_interpret(data, score, level, signals):
            """AI 解读华尔街情绪"""
            # 拼装数据摘要
            summary_lines = [f"【时间】{now.strftime('%Y-%m-%d %H:%M')}",
                            f"【综合评分】{score}/100 → {level}"]
            for icon, desc in signals:
                summary_lines.append(f"  {icon} {desc}")
            # 各指标详情
            if 'cnn_fng' in data and 'error' not in data['cnn_fng']:
                f = data['cnn_fng']
                summary_lines.append(f"\nCNN FNG: {f['current']}({f['class']}) 10日均={f['avg10']:.1f}")
            if 'indices' in data:
                for n, v in data['indices'].items():
                    if isinstance(v, dict) and 'close' in v:
                        summary_lines.append(
                            f"{n}: {v['close']:.2f} MA20={v['ma20']:.2f} MA60={v['ma60']:.2f} "
                            f"5日={v['chg_5d']:+.1f}% 20日={v['chg_20d']:+.1f}% 趋势={v['ma_trend']}")
            if 'vix' in data and 'error' not in data.get('vix', {}):
                summary_lines.append(f"VIX: {data['vix']['current']:.1f}")
            if 'gold' in data and 'error' not in data.get('gold', {}):
                summary_lines.append(f"黄金: {data['gold']['price']} 5日={data['gold']['chg_5d']:+.1f}%")
            prompt = f"""基于以下华尔街情绪数据，判断当前美股阶段并给出操作建议。
{chr(10).join(summary_lines)}
请输出:
【一句话判定】红灯/黄灯/绿灯 + 操作建议（减仓/观望/低吸）
【衍生品信号】PCR/VIX 解读
【散户机构剪刀差】密歇根信心/CNN FNG 解读
【杠杆与广度】美股指数MA/量比解读
【A股关联】美股情绪如何传导到A股港股
【风险预警】黑天鹅信号
要求: 数据说话、结论明确、不要模棱两可。"""
            try:
                result = self.call_ai_model(prompt,
                                            system_prompt="你是华尔街跨市场情绪分析师，擅长从衍生品、资金、市场结构三维度量化判断市场见顶/见底。",
                                            max_tokens=1500)
                win.after(0, lambda: report_txt.delete("1.0", tk.END))
                win.after(0, lambda: report_txt.insert("1.0",
                    f"═══ 🏦 华尔街红绿灯 AI 解读 ═══\n"
                    f"⏰ {now.strftime('%Y-%m-%d %H:%M')}  |  评分 {score}/100 → {level}\n\n"
                    f"【分项信号】\n" + "\n".join([f"  {i}{d}" for i, d in signals]) + f"\n\n"
                    f"【AI 分析】\n{result or '(AI未返回)'}"
                ))
                win.after(0, lambda: status_var.set(f"✅ 分析完成! 评分 {score}/100"))
            except Exception as e:
                win.after(0, lambda e=e: report_txt.delete("1.0", tk.END))
                win.after(0, lambda e=e: report_txt.insert("1.0", f"❌ AI 调用失败: {e}\n\n原始数据:\n{summary_lines}"))
                win.after(0, lambda e=e: status_var.set(f"AI 失败: {str(e)[:40]}"))
        scan_btn.configure(command=_run_scan)
        # ===== 首次加载缓存 =====
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r') as f:
                    cached = json.load(f)
                # 显示缓存数据
                for card_key, data_key in [('cnn_fng','cnn_fng'),('vix','vix'),
                                           ('us_idx','indices'),('volume','indices'),
                                           ('gold','gold'),('umich','umich')]:
                    d = cached.get(data_key, {})
                    color, icon, text = _judge_light(card_key, d)
                    _update_card(card_key, color, icon, text)
                score = cached.get('score', 50)
                level = cached.get('level', '')
                signals = cached.get('signals', [])
                score_var.set(f"综合评分: {score}/100")
                level_var.set(level)
                sig_text = "  ".join([f"{i}{d}" for i, d in signals[:6]])
                signals_var.set(sig_text)
                traffic_light.config(text="🟢" if score >= 65 else ("🟡" if score >= 40 else "🔴"))
                status_var.set(f"📂 已加载缓存 ({cached.get('time', '')}) — 点🔍更新")
        except Exception:
            pass
        win.after(100, _run_scan)  # 自动扫描

    def _show_a_share_traffic_light(self):
        """🇨🇳 A股红绿灯: 融资·北向·涨跌停·指数MA·换手·活跃度 → 综合判定 + AI解读"""
        import datetime
        import json
        import os
        import ssl
        import threading
        import tkinter as tk
        from tkinter import scrolledtext
        ssl._create_default_https_context = ssl._create_unverified_context
        DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(DATA_DIR, exist_ok=True)
        CACHE_FILE = os.path.join(DATA_DIR, "a_share_traffic_cache.json")
        win = self._safe_toplevel(self.root)
        win.title("🇨🇳 A股红绿灯 · 市场情绪量化判定")
        win.geometry("1280x920")
        win.minsize(1100, 780)
        now = datetime.datetime.now()
        banner_color = "#C62828"  # A股红
        # ===== Banner =====
        banner = tk.Frame(win, bg=banner_color, height=56); banner.pack(fill=tk.X)
        tk.Label(banner, text="🇨🇳 A股红绿灯", bg=banner_color, fg="white",
                 font=("", 16, "bold")).pack(side=tk.LEFT, padx=14, pady=10)
        tk.Label(banner, text=(
            "融资融券 · 北向资金 · 涨跌停广度 · 指数MA · 换手率 · 成交额 — "
            f"{now.strftime('%Y-%m-%d %H:%M')}"
        ), bg=banner_color, fg="#FFCDD2", font=("", 11)).pack(side=tk.LEFT, pady=14)
        # ===== 控制区 =====
        ctrl = tk.Frame(win); ctrl.pack(fill=tk.X, padx=10, pady=6)
        ai_var = tk.BooleanVar(value=True)
        tk.Checkbutton(ctrl, text="📝 自动AI解读", variable=ai_var, font=("", 10)).pack(side=tk.LEFT)
        scan_btn = tk.Button(ctrl, text="🔍 扫描A股情绪", font=("", 11, "bold"),
                             bg=banner_color, fg="white", padx=16, pady=3, cursor="hand2")
        scan_btn.pack(side=tk.LEFT, padx=10)
        status_var = tk.StringVar(value="⏳ 等待扫描...")
        tk.Label(ctrl, textvariable=status_var, font=("", 10), fg="#666").pack(side=tk.LEFT, padx=10)
        # ===== 上半: 6 大指标红绿灯卡片 =====
        top_frame = tk.Frame(win); top_frame.pack(fill=tk.X, padx=10, pady=8)
        indicator_cards = {}
        INDICATORS = [
            ("融资融券", "margin", "杠杆资金 融资余额变化", "#311B92"),
            ("北向资金", "north", "外资净流入/流出", "#006064"),
            ("涨跌停广度", "breadth", "涨停/跌停/涨跌家数", "#B71C1C"),
            ("指数MA趋势", "idx_ma", "上证/深证/创业板", "#1A237E"),
            ("换手率", "turnover", "全市场换手活跃度", "#33691E"),
            ("成交额", "volume", "成交额/量比变化", "#E65100"),
        ]
        for i, (title, key, desc, color) in enumerate(INDICATORS):
            card = tk.Frame(top_frame, bg="white", highlightbackground="#DDD",
                           highlightthickness=2, padx=10, pady=10)
            card.grid(row=i // 3, column=i % 3, padx=6, pady=6, sticky="nsew")
            top_frame.grid_columnconfigure(i % 3, weight=1, uniform="col")
            header = tk.Frame(card, bg="white"); header.pack(fill=tk.X)
            tk.Label(header, text=title, font=("", 11, "bold"), fg=color,
                     bg="white").pack(side=tk.LEFT)
            row1 = tk.Frame(card, bg="white"); row1.pack(fill=tk.X, pady=4)
            # Canvas 小圆灯 (50x50) 替代 emoji
            small_light = tk.Canvas(row1, width=50, height=50, bg="white", highlightthickness=0)
            small_light.pack(side=tk.LEFT, padx=(0, 6))
            # 画一个灰色初始圆
            small_light.create_oval(8, 8, 42, 42, fill="#BDBDBD", outline="#757575", width=2)
            val = tk.Label(row1, text="--", font=("", 11, "bold"), fg="#333",
                          bg="white")
            val.pack(side=tk.LEFT, padx=2)
            desc_label = tk.Label(card, text=desc, font=("", 9), fg="#888",
                                 bg="white", wraplength=180, justify="left")
            desc_label.pack(fill=tk.X, pady=(2, 0))
            indicator_cards[key] = {'card': card, 'light': small_light, 'val': val, 'desc': desc_label}
        # ===== 中间: 综合红绿灯大卡片 — Canvas 真圆灯 + 整行背景联动 =====
        mid_frame = tk.Frame(win, bg="#F5F5F5", highlightbackground="#DDD",
                            highlightthickness=2, padx=20, pady=16)
        mid_frame.pack(fill=tk.X, padx=10, pady=8)
        # 左侧: Canvas 画的大圆灯 (160x160)
        mid_left = tk.Frame(mid_frame, bg=mid_frame["bg"]); mid_left.pack(side=tk.LEFT, fill=tk.Y)
        light_canvas = tk.Canvas(mid_left, width=160, height=160, bg=mid_frame["bg"],
                                 highlightthickness=0)
        light_canvas.pack(side=tk.LEFT, padx=10, pady=5)
        # Canvas 画圆灯函数 (带高光渐变效果)
        def _draw_circle_light(canvas, cx, cy, r, color, glow=False):
            """画一个带立体渐变的圆形灯"""
            # 阴影层
            canvas.create_oval(cx - r + 4, cy - r + 8, cx + r + 4, cy + r + 8,
                               fill="#9E9E9E", outline="")
            # 主色圆
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                               fill=color, outline="#424242", width=3)
            # 高光 (左上白色半透明椭圆)
            canvas.create_oval(cx - r * 0.65, cy - r * 0.7,
                               cx + r * 0.15, cy - r * 0.05,
                               fill="white", outline="", stipple="gray25")
            # 脉冲圈 (可选 — 红灯时才显示)
            if glow:
                canvas.create_oval(cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6,
                                   outline=color, width=3)
        # 初始化一个灰色灯
        _draw_circle_light(light_canvas, 80, 80, 58, "#BDBDBD", glow=False)
        mid_right = tk.Frame(mid_frame, bg=mid_frame["bg"]); mid_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(mid_right, text="🏁 A股综合红绿灯", font=("", 14, "bold"),
                 bg=mid_frame["bg"], fg="#333").pack(anchor="w")
        score_var = tk.StringVar(value="综合评分: --/100")
        tk.Label(mid_right, textvariable=score_var, font=("", 24, "bold"),
                 bg=mid_frame["bg"], fg=banner_color).pack(anchor="w", pady=4)
        level_var = tk.StringVar(value="⏳ 等待扫描...")
        level_lbl = tk.Label(mid_right, textvariable=level_var, font=("", 15, "bold"),
                 bg=mid_frame["bg"], fg="#555")
        level_lbl.pack(anchor="w")
        signals_var = tk.StringVar(value="")
        tk.Label(mid_right, textvariable=signals_var, font=("", 11),
                 bg=mid_frame["bg"], fg="#555", wraplength=700, justify="left").pack(anchor="w", pady=(8, 0))
        # 方向指示箭头 (大图标)
        arrow_var = tk.StringVar(value="➤ 等待扫描")
        arrow_lbl = tk.Label(mid_right, textvariable=arrow_var, font=("", 13, "bold"),
                              bg=mid_frame["bg"], fg="#555")
        arrow_lbl.pack(anchor="e")
        # ===== 中部: 🗺️ 情绪地图 (独立可见区, 不藏在 Notebook 里) =====
        import json as _js_sent
        import os as _os_sent
        import subprocess as _sp_sent
        import threading as _th_sent
        EMOTION_SKILL_DIR = _os_sent.path.expanduser("~/.qclaw/workspace-agent-85985980")
        EMOTION_JSON = _os_sent.path.join(EMOTION_SKILL_DIR, "market_sentiment_data.json")
        EMOTION_PY = _os_sent.path.join(EMOTION_SKILL_DIR, "market_sentiment.py")
        emo_frame = tk.Frame(win, bg="#E8EAF6", highlightbackground="#3F51B5",
                             highlightthickness=2)
        emo_frame.pack(fill=tk.X, padx=10, pady=6)
        emo_header = tk.Frame(emo_frame, bg="#3F51B5"); emo_header.pack(fill=tk.X)
        tk.Label(emo_header, text="🗺️ 市场情绪地图 · 情绪分热力图 + 涨跌停趋势",
                 bg="#3F51B5", fg="white", font=("", 11, "bold")).pack(side=tk.LEFT, padx=10, pady=5)
        emo_status = tk.StringVar(value="⏳ 点击下方按钮加载数据...")
        tk.Button(emo_header, text="🔄 更新情绪数据", bg="#C62828", fg="white",
                  font=("", 10, "bold"), padx=10, pady=1, cursor="hand2",
                  command=lambda: _bg_load_emo()).pack(side=tk.RIGHT, padx=8, pady=3)
        tk.Label(emo_header, textvariable=emo_status, bg="#3F51B5", fg="#FFD54F",
                 font=("", 9)).pack(side=tk.RIGHT, padx=10)

        emo_body = tk.Frame(emo_frame, bg="#E8EAF6"); emo_body.pack(fill=tk.X, padx=6, pady=4)
        # 左: 趋势图 + 热力条 (上下堆叠)
        emo_left = tk.Frame(emo_body, bg="#E8EAF6"); emo_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # 右上: 热力条 Canvas (彩色方块)
        emo_right = tk.Frame(emo_body, bg="#E8EAF6", width=220); emo_right.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))
        emo_right.pack_propagate(False)
        tk.Label(emo_right, text="⚡ 最新快照", bg="#E8EAF6", fg="#1A237E",
                 font=("", 10, "bold")).pack(anchor="w", padx=4, pady=(2, 2))
        snap_box = tk.LabelFrame(emo_right, text="情绪数据", bg="#E8EAF6", font=("", 9, "bold"))
        snap_box.pack(fill=tk.X, padx=4, pady=4)
        snap_lbl = tk.Label(snap_box, text="⏳ 等待加载...", bg="#E8EAF6", fg="#333",
                            font=("", 9), justify=tk.LEFT, wraplength=200)
        snap_lbl.pack(anchor="w", padx=6, pady=6)

        # 趋势图 Canvas (上)
        tk.Label(emo_left, text="📈 情绪分趋势 + 涨跌幅", bg="#E8EAF6", fg="#1A237E",
                 font=("", 10, "bold")).pack(anchor="w", padx=4, pady=(2, 0))
        canvas_trend = tk.Canvas(emo_left, bg="white", height=150, highlightthickness=1,
                                 highlightbackground="#C5CAE9")
        canvas_trend.pack(fill=tk.X, expand=False, padx=4, pady=3)
        canvas_trend.create_text(300, 75, text="⏳ 点🔄加载情绪数据...",
                                 fill="#999", font=("", 11))

        # 热力条 Canvas (下)
        tk.Label(emo_left, text="📊 情绪热力条 (红=热≥60 黄=暖45-59 灰=中性35-44 绿=冷<35)",
                 bg="#E8EAF6", fg="#1A237E", font=("", 10, "bold")).pack(anchor="w", padx=4, pady=(2, 0))
        canvas_bar = tk.Canvas(emo_left, bg="white", height=110, highlightthickness=1,
                               highlightbackground="#C5CAE9")
        canvas_bar.pack(fill=tk.X, expand=False, padx=4, pady=3)
        canvas_bar.create_text(300, 55, text="⏳ 等待数据...", fill="#999", font=("", 11))

        def _emo_col(s):
            if s >= 70: return "#C62828"
            if s >= 60: return "#E53935"
            if s >= 55: return "#FF7043"
            if s >= 45: return "#F57F17"
            if s >= 35: return "#455A64"
            if s >= 25: return "#66BB6A"
            return "#2E7D32"

        def _draw_emo(sent_data):
            """渲染情绪图 (趋势+热力条)"""
            try:
                dl = sent_data.get("data", []) if sent_data else []
                if not dl:
                    canvas_trend.delete("all"); canvas_bar.delete("all")
                    canvas_trend.create_text(300, 75, text="暂无数据", fill="#999", font=("", 11))
                    canvas_bar.create_text(300, 55, text="暂无数据", fill="#999", font=("", 11))
                    snap_lbl.config(text="暂无数据")
                    return
                # ===== 趋势图 =====
                canvas_trend.delete("all")
                Wt = max(canvas_trend.winfo_width(), 600)
                pad_l, pad_r, pad_t, pad_b = 40, 10, 20, 30
                pt_w = Wt - pad_l - pad_r
                pt_h = 150 - pad_t - pad_b
                n = len(dl); gap = pt_w / n
                max_chg = max(max(abs(d.get("sh_chg", 0)) for d in dl), 1)
                zero_y = pad_t + pt_h / 2
                canvas_trend.create_line(pad_l, zero_y, pad_l + pt_w, zero_y, fill="#BDBDBD", dash=(3,2))
                # 柱状 (涨跌幅)
                bar_w = max(4, gap * 0.6)
                for i, d in enumerate(dl):
                    chg = d.get("sh_chg", 0)
                    xc = pad_l + i * gap + gap / 2
                    hb = abs(chg) / max_chg * (pt_h/2 - 2)
                    x1, x2 = xc - bar_w/2, xc + bar_w/2
                    if chg >= 0:
                        canvas_trend.create_rectangle(x1, zero_y - hb, x2, zero_y, fill="#C62828", outline="")
                    else:
                        canvas_trend.create_rectangle(x1, zero_y, x2, zero_y + hb, fill="#2E7D32", outline="")
                # 情绪分折线 (平滑近似)
                sent_pts = []
                for i, d in enumerate(dl):
                    x = pad_l + i * gap + gap / 2
                    s = d.get("sentiment_score", 50)
                    y = pad_t + pt_h - s / 100 * pt_h
                    sent_pts.extend([x, y])
                if len(sent_pts) >= 4:
                    canvas_trend.create_line(*sent_pts, fill="#FF6F00", width=2, smooth=True)
                    for i in range(0, len(sent_pts), 2):
                        canvas_trend.create_oval(sent_pts[i]-3, sent_pts[i+1]-3,
                                                 sent_pts[i]+3, sent_pts[i+1]+3,
                                                 fill="#FF6F00", outline="")
                # X 轴标签
                for i, d in enumerate(dl):
                    if i % 3 == 0 or i == n-1:
                        x = pad_l + i * gap + gap / 2
                        canvas_trend.create_text(x, 150 - pad_b + 12, text=d.get("date","")[-4:],
                                                 fill="#555", font=("", 7))
                # 图例
                canvas_trend.create_rectangle(pad_l+4, 4, pad_l+14, 12, fill="#C62828", outline="")
                canvas_trend.create_text(pad_l+18, 8, text="涨", fill="#333", font=("", 8), anchor="w")
                canvas_trend.create_rectangle(pad_l+34, 4, pad_l+44, 12, fill="#2E7D32", outline="")
                canvas_trend.create_text(pad_l+48, 8, text="跌", fill="#333", font=("", 8), anchor="w")
                canvas_trend.create_line(pad_l+68, 8, pad_l+82, 8, fill="#FF6F00", width=2)
                canvas_trend.create_text(pad_l+86, 8, text="情绪分", fill="#FF6F00", font=("", 8), anchor="w")

                # ===== 热力条 =====
                canvas_bar.delete("all")
                Wb = max(canvas_bar.winfo_width(), 600)
                pb_l, pb_r = 10, 10
                n2 = len(dl); cg = 2
                cw = max(8, (Wb - pb_l - pb_r - cg*(n2-1)) / n2)
                for i, d in enumerate(reversed(dl)):
                    x1 = pb_l + i * (cw + cg); x2 = x1 + cw
                    s = d.get("sentiment_score", 50); chg = d.get("sh_chg", 0)
                    zt = d.get("zt_count", 0); dt2 = d.get("date", "")
                    col = _emo_col(s)
                    # 上方块: 情绪分
                    canvas_bar.create_rectangle(x1, 18, x2, 52, fill=col, outline="white", width=1)
                    canvas_bar.create_text((x1+x2)//2, 35, text=f"{s:.0f}", fill="white", font=("", 8, "bold"))
                    # 下方块: 涨跌
                    bc = "#C62828" if chg >= 0 else "#2E7D32"
                    canvas_bar.create_rectangle(x1, 58, x2, 76, fill=bc, outline="white", width=1)
                    canvas_bar.create_text((x1+x2)//2, 67, text=f"{chg:+.1f}", fill="white", font=("", 7))
                    # 日期
                    if i % 2 == 0 or i == n2-1:
                        canvas_bar.create_text((x1+x2)//2, 88, text=dt2[-4:], fill="#555", font=("", 7))
                    canvas_bar.create_text((x1+x2)//2, 100, text=f"zt{zt}", fill="#888", font=("", 7))
                # 图例
                canvas_bar.create_rectangle(pb_l, 2, pb_l+12, 10, fill="#C62828", outline="")
                canvas_bar.create_text(pb_l+16, 6, text="≥60热", fill="#C62828", font=("", 7), anchor="w")
                canvas_bar.create_rectangle(pb_l+60, 2, pb_l+72, 10, fill="#F57F17", outline="")
                canvas_bar.create_text(pb_l+76, 6, text="45暖", fill="#F57F17", font=("", 7), anchor="w")
                canvas_bar.create_rectangle(pb_l+110, 2, pb_l+122, 10, fill="#455A64", outline="")
                canvas_bar.create_text(pb_l+126, 6, text="35中性", fill="#455A64", font=("", 7), anchor="w")
                canvas_bar.create_rectangle(pb_l+170, 2, pb_l+182, 10, fill="#2E7D32", outline="")
                canvas_bar.create_text(pb_l+186, 6, text="<35冷", fill="#2E7D32", font=("", 7), anchor="w")

                # ===== 快照 =====
                snap = sent_data.get("latest_snapshot") or {}
                up = snap.get("up", 0); dn = snap.get("down", 0)
                ft = snap.get("flat", 0); snap.get("total", up+dn+ft)
                last = dl[-1]
                snap_txt = (f"📅 {last.get('date','')}\n"
                           f"上证 {last.get('index_close','')}\n"
                           f"📈涨{up} 📉跌{dn} ➖平{ft}\n"
                           f"🎯情绪 {last.get('sentiment_score','')}\n"
                           f"涨停{last.get('zt_count','')} 跌停{last.get('dt_count','')}")
                snap_lbl.config(text=snap_txt)
                print(f"[情绪地图] ✅ 渲染完成 {n}天", flush=True)
            except Exception as e:
                import traceback; traceback.print_exc()
                canvas_trend.delete("all"); canvas_bar.delete("all")
                canvas_trend.create_text(300, 75, text=f"❌ 渲染错误: {str(e)[:40]}",
                                         fill="#C62828", font=("", 10))

        def _bg_load_emo():
            """后台加载情绪数据"""
            emo_status.set("⏳ 运行 market_sentiment.py ...")
            def _run():
                try:
                    if _os_sent.path.exists(EMOTION_JSON):
                        with open(EMOTION_JSON) as f:
                            sd = _js_sent.load(f)
                        win.after(0, lambda: _draw_emo(sd))
                        meta = sd.get("meta", {})
                        win.after(0, lambda: emo_status.set(
                            f"✅ {meta.get('start_date','')}~{meta.get('end_date','')} {len(sd.get('data',[]))}天"))
                    else:
                        emo_status.set("❌ 无缓存, 运行 skill ...")
                        try:
                            _sp_sent.run(["python3", EMOTION_PY], capture_output=True, text=True, timeout=60)
                            if _os_sent.path.exists(EMOTION_JSON):
                                with open(EMOTION_JSON) as f:
                                    sd = _js_sent.load(f)
                                win.after(0, lambda: _draw_emo(sd))
                        except Exception as e2:
                            emo_status.set(f"❌ 运行失败: {str(e2)[:30]}")
                except Exception as e:
                    emo_status.set(f"❌ 加载失败: {str(e)[:30]}")
            _th_sent.Thread(target=_run, daemon=True).start()
        # 自动加载缓存
        def _auto_emo():
            import time as _t; _t.sleep(1.5)
            try:
                if _os_sent.path.exists(EMOTION_JSON):
                    with open(EMOTION_JSON) as f: sd = _js_sent.load(f)
                    win.after(0, lambda: _draw_emo(sd))
                    meta = sd.get("meta", {})
                    win.after(0, lambda: emo_status.set(
                        f"📂 缓存 {meta.get('start_date','')}~{meta.get('end_date','')} {len(sd.get('data',[]))}天"))
                    print("[情绪地图] 📂 自动加载缓存成功", flush=True)
            except Exception as e:
                print(f"[情绪地图] ⚠️ 自动加载失败: {e}", flush=True)
        _th_sent.Thread(target=_auto_emo, daemon=True).start()

        # ===== 底部: Notebook — AI解读 =====
        from tkinter import ttk as _ttk_as
        bot_nb = _ttk_as.Notebook(win); bot_nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))
        # --- Tab1: 📝 AI 策略解读 (不再有情绪地图Tab) ---
        tab_ai = tk.Frame(bot_nb, bg="#FAFAFA"); bot_nb.add(tab_ai, text=" 📝 AI 策略解读 ")
        report_txt = scrolledtext.ScrolledText(tab_ai, font=("", 11), wrap=tk.WORD,
                                              height=12, bg="#FAFAFA")
        report_txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        # 🎨 AI 解读区 tag 体系
        report_txt.tag_config("hdr",       foreground="#1565C0", font=("", 12, "bold"))
        report_txt.tag_config("meta",      foreground="#607D8B", font=("", 10))
        report_txt.tag_config("sep",       foreground="#B0BEC5")
        report_txt.tag_config("green_tag", foreground="#2E7D32", font=("", 11, "bold"))
        report_txt.tag_config("red_tag",   foreground="#C62828", font=("", 11, "bold"))
        report_txt.tag_config("yellow_tag",foreground="#E65100", font=("", 11, "bold"))
        report_txt.tag_config("green_bg",  foreground="#1B5E20", background="#E8F5E9")
        report_txt.tag_config("red_bg",    foreground="#B71C1C", background="#FFEBEE")
        report_txt.tag_config("yellow_bg", foreground="#F57F17", background="#FFFDE7")
        def _render_ai_report(text, score, level, signals):
            """把 AI 报告按情绪面打上彩色 tag"""
            report_txt.config(state=tk.NORMAL)
            report_txt.delete("1.0", tk.END)
            # Header
            report_txt.insert(tk.END, "═══ 🇨🇳 A股红绿灯 AI 解读 ═══\n", "hdr")
            report_txt.insert(tk.END, f"⏰ {now.strftime('%Y-%m-%d %H:%M')}  |  评分 ", "meta")
            # 评分数字按颜色
            if score >= 65: report_txt.insert(tk.END, f"{score}/100 ", "green_tag")
            elif score >= 40: report_txt.insert(tk.END, f"{score}/100 ", "yellow_tag")
            else: report_txt.insert(tk.END, f"{score}/100 ", "red_tag")
            # 级别也按颜色
            report_txt.insert(tk.END, "→ ")
            if "绿灯" in level or "安全" in level: report_txt.insert(tk.END, level + "\n\n", "green_tag")
            elif "黄灯" in level or "警惕" in level: report_txt.insert(tk.END, level + "\n\n", "yellow_tag")
            elif "红灯" in level or "危险" in level: report_txt.insert(tk.END, level + "\n\n", "red_tag")
            else: report_txt.insert(tk.END, level + "\n\n")
            # 分项信号 (按 emoji 颜色打 tag)
            report_txt.insert(tk.END, "【分项信号】\n", "hdr")
            for icon, desc in signals:
                if "🟢" in icon: report_txt.insert(tk.END, f"  {icon} {desc}\n", "green_bg")
                elif "🔴" in icon: report_txt.insert(tk.END, f"  {icon} {desc}\n", "red_bg")
                elif "🟡" in icon: report_txt.insert(tk.END, f"  {icon} {desc}\n", "yellow_bg")
                else: report_txt.insert(tk.END, f"  {icon} {desc}\n")
            # AI 正文逐行染色
            report_txt.insert(tk.END, "\n【AI 分析】\n", "hdr")
            for line in (text or "(AI未返回)").split("\n"):
                stripped = line.strip()
                if not stripped:
                    report_txt.insert(tk.END, "\n"); continue
                # 情绪词命中 → 整行染色
                if any(kw in line for kw in ["绿灯", "安全", "加仓", "低吸", "积极", "上涨", "多头", "突破"]):
                    report_txt.insert(tk.END, line + "\n", "green_bg")
                elif any(kw in line for kw in ["红灯", "危险", "减仓", "避险", "清仓", "下跌", "空头", "破位", "恐慌", "止损"]):
                    report_txt.insert(tk.END, line + "\n", "red_bg")
                elif any(kw in line for kw in ["黄灯", "警惕", "控制", "观望", "震荡", "谨慎"]):
                    report_txt.insert(tk.END, line + "\n", "yellow_bg")
                else:
                    report_txt.insert(tk.END, line + "\n")
            report_txt.config(state=tk.DISABLED)
        # ===== 核心: 数据采集 =====
        def _scan_a_share():
            import akshare as ak
            data = {'signals': []}
            # 1️⃣ 融资融券 (沪深合计)
            try:
                sh = ak.macro_china_market_margin_sh()
                sz = ak.macro_china_market_margin_sz()
                sh_col = [c for c in sh.columns if '融资' in c or '余额' in c][-1]
                sz_col = [c for c in sz.columns if '融资' in c or '余额' in c][-1]
                sh_cur = float(sh[sh_col].iloc[-1])
                sz_cur = float(sz[sz_col].iloc[-1])
                sh_chg = (sh_cur / float(sh[sh_col].iloc[-7]) - 1) * 100
                sz_chg = (sz_cur / float(sz[sz_col].iloc[-7]) - 1) * 100
                data['margin'] = {
                    'sh_yi': sh_cur / 1e8, 'sz_yi': sz_cur / 1e8,
                    'total_yi': (sh_cur + sz_cur) / 1e8,
                    'sh_chg_7d': sh_chg, 'sz_chg_7d': sz_chg,
                    'avg_chg': (sh_chg + sz_chg) / 2
                }
            except Exception as e:
                import traceback as _tb
                _tb.print_exc()
                data['margin'] = {'error': str(e)[:60]}
            # 2️⃣ 北向资金 (tushare)
            try:
                import tushare as _ts
                with open(os.path.expanduser("~/.tushare/token")) as _tf:
                    _tk = _tf.read().strip()
                _pro = _ts.pro_api(_tk)
                _end = now.strftime('%Y%m%d')
                _start = (now - datetime.timedelta(days=14)).strftime('%Y%m%d')
                df = _pro.moneyflow_hsgt(start_date=_start, end_date=_end)
                if df is not None and len(df) >= 3:
                    recent = df.sort_values('trade_date', ascending=False).head(5)
                    # north_money 是累计值, 用差分算每日净流入
                    # ⚠️ tushare moneyflow_hsgt 单位是万元, 需 /10000 转亿元
                    north_vals = recent['north_money'].astype(float).tolist()
                    daily_flows_wan = [north_vals[i] - north_vals[i+1] for i in range(len(north_vals)-1)]
                    net_3d_yi = sum(daily_flows_wan[:3]) / 10000.0  # 万元→亿元
                    north_trend = "持续流入" if all(f > 0 for f in daily_flows_wan[:3]) else (
                        "持续流出" if all(f < 0 for f in daily_flows_wan[:3]) else "流入流出交替")
                    data['north'] = {
                        'net_3d_yi': net_3d_yi,
                        'trend': north_trend,
                        'latest': float(recent.iloc[0]['north_money']) / 10000.0  # 累计值也转亿
                    }
            except Exception as e:
                data['north'] = {'error': str(e)[:60]}
            # 3️⃣ 涨跌停广度 (legu 上游页面挂了, 改用东方财富涨停/跌停池 + tushare daily)
            try:
                limit_up = limit_down = up = down = flat = 0
                # 3a. 涨停/跌停池 (akshare 东方财富源)
                try:
                    zt_df = ak.stock_zt_pool_em(date=now.strftime('%Y%m%d'))
                    limit_up = len(zt_df) if zt_df is not None else 0
                except Exception:
                    limit_up = 0
                try:
                    dt_df = ak.stock_zt_pool_dtgc_em(date=now.strftime('%Y%m%d'))
                    limit_down = len(dt_df) if dt_df is not None else 0
                except Exception:
                    limit_down = 0
                # 3b. 上涨/下跌/平盘 (tushare daily)
                try:
                    import tushare as _tsb
                    with open(os.path.expanduser("~/.tushare/token")) as _tf2:
                        _tk2 = _tf2.read().strip()
                    _pro2 = _tsb.pro_api(_tk2)
                    _d_end = now.strftime('%Y%m%d')
                    daily_df = _pro2.daily(trade_date=_d_end, fields='ts_code,pct_chg')
                    if daily_df is not None and len(daily_df) > 0:
                        up = int((daily_df['pct_chg'] > 0).sum())
                        down = int((daily_df['pct_chg'] < 0).sum())
                        flat = int((daily_df['pct_chg'] == 0).sum())
                except Exception:
                    up = down = flat = 0
                breadth = up / (up + down + flat) * 100 if (up + down + flat) > 0 else 50
                data['breadth'] = {
                    'up': up, 'down': down, 'flat': flat,
                    'limit_up': limit_up, 'limit_down': limit_down,
                    'breadth_pct': breadth, 'active': f"{up}/{down}"
                }
            except Exception as e:
                data['breadth'] = {'error': str(e)[:60]}
            # 4️⃣ A股指数 MA 趋势 (双数据源: akshare → tushare 备用)
            idx_results = {}
            # tushare code 映射
            _ts_code_map = {"000001": "000001.SH", "399001": "399001.SZ", "399006": "399006.SZ"}
            for code, name in [("000001", "上证指数"), ("399001", "深证成指"), ("399006", "创业板指")]:
                _got_data = False
                # 尝试 akshare
                try:
                    import time as _t
                    _t.sleep(0.3)
                    df = ak.index_zh_a_hist(symbol=code, period="daily",
                                           start_date="20260601",
                                           end_date=now.strftime('%Y%m%d'))
                    if df is not None and len(df) >= 60:
                        cur = float(df['收盘'].iloc[-1])
                        ma20 = float(df['收盘'].tail(20).mean())
                        ma60 = float(df['收盘'].mean())
                        chg_5 = (cur / float(df['收盘'].iloc[-5]) - 1) * 100
                        vol_5 = float(df['成交额'].tail(5).mean())
                        vol_20 = float(df['成交额'].tail(20).mean())
                        vol_ratio = vol_5 / vol_20 if vol_20 > 0 else 1
                        trend = ("多头" if cur > ma20 > ma60 else
                                 "空头" if cur < ma20 < ma60 else "震荡")
                        idx_results[name] = {
                            'close': cur, 'ma20': ma20, 'ma60': ma60,
                            'chg_5d': chg_5, 'vol_ratio': vol_ratio,
                            'ma_trend': trend, 'amount_yi': float(df['成交额'].iloc[-1]) / 1e8
                        }
                        _got_data = True
                except Exception:
                    pass
                # akshare 失败 → 切换 tushare index_daily
                if not _got_data:
                    try:
                        import tushare as _ts_fallback
                        with open(os.path.expanduser("~/.tushare/token")) as _tf2:
                            _tk2 = _tf2.read().strip()
                        _pro2 = _ts_fallback.pro_api(_tk2)
                        ts_code = _ts_code_map[code]
                        _end = now.strftime('%Y%m%d')
                        _start_60 = (now - datetime.timedelta(days=120)).strftime('%Y%m%d')
                        df2 = _pro2.index_daily(ts_code=ts_code, start_date=_start_60, end_date=_end)
                        if df2 is not None and len(df2) >= 60:
                            df2 = df2.sort_values('trade_date').reset_index(drop=True)
                            cur = float(df2['close'].iloc[-1])
                            ma20 = float(df2['close'].tail(20).mean())
                            ma60 = float(df2['close'].tail(60).mean())
                            chg_5 = (cur / float(df2['close'].iloc[-5]) - 1) * 100
                            vol_5 = float(df2['amount'].tail(5).mean())
                            vol_20 = float(df2['amount'].tail(20).mean())
                            vol_ratio = vol_5 / vol_20 if vol_20 > 0 else 1
                            trend = ("多头" if cur > ma20 > ma60 else
                                     "空头" if cur < ma20 < ma60 else "震荡")
                            idx_results[name] = {
                                'close': cur, 'ma20': ma20, 'ma60': ma60,
                                'chg_5d': chg_5, 'vol_ratio': vol_ratio,
                                'ma_trend': trend,
                                'amount_yi': float(df2['amount'].iloc[-1]) / 1e5,
                                'src': 'tushare'
                            }
                            _got_data = True
                    except Exception as e2:
                        idx_results[name] = {'error': f'akshare+tushare双失败: {str(e2)[:50]}'}
                if not _got_data and name not in idx_results:
                    idx_results[name] = {'error': '无可用数据源'}
            data['indices'] = idx_results
            # 5️⃣ 换手率 (tushare index_dailybasic)
            try:
                import tushare as _ts2
                with open(os.path.expanduser("~/.tushare/token")) as _tf2:
                    _tk2 = _tf2.read().strip()
                _pro2 = _ts2.pro_api(_tk2)
                df = _pro2.index_dailybasic(ts_code='000001.SH',
                                           start_date=_start, end_date=_end)
                if df is not None and len(df) >= 2:
                    turnover = float(df.tail(1).iloc[-1]['turnover_rate'])
                    turnover_prev = float(df.tail(2).iloc[0]['turnover_rate'])
                    data['turnover'] = {
                        'current': turnover,
                        'prev': turnover_prev,
                        'chg': turnover - turnover_prev
                    }
            except Exception as e:
                data['turnover'] = {'error': str(e)[:60]}
            return data
        # ===== 红绿灯判定 =====
        def _judge_light(key, d):
            if key == 'margin':
                if 'error' in d: return ('gray', '⚫', '接口错误')
                chg = d['avg_chg']
                if chg > 3: return ('red', '🔴', f'融资+{chg:.1f}% 杠杆过热')
                if chg > 0.5: return ('yellow', '🟡', f'融资+{chg:.1f}% 温和加杠杆')
                if chg < -2: return ('green', '🟢', f'融资{chg:.1f}% 杠杆清洗')
                return ('green', '🟢', f'融资{chg:+.1f}% 稳定 合计{d["total_yi"]:.0f}亿')
            if key == 'north':
                if 'error' in d: return ('gray', '⚫', '接口错误')
                if d['trend'] == '持续流入': return ('green', '🟢', f'北向持续流入 3日净流入={d["net_3d_yi"]:.0f}亿')
                if d['trend'] == '持续流出': return ('red', '🔴', f'北向持续流出 3日净流出={d["net_3d_yi"]:.0f}亿')
                return ('yellow', '🟡', f'北向{d["trend"]} 3日={d["net_3d_yi"]:+.0f}亿')
            if key == 'breadth':
                if 'error' in d: return ('gray', '⚫', '接口错误')
                b = d['breadth_pct']
                lu = d['limit_up']; ld = d['limit_down']
                if lu >= 80 and ld <= 5: return ('green', '🟢', f'涨停{lu}/跌停{ld} 普涨')
                if lu <= 10 and ld >= 30: return ('red', '🔴', f'涨停{lu}/跌停{ld} 普跌')
                if b >= 70: return ('green', '🟢', f'上涨占比{b:.0f}% {d["active"]}')
                if b <= 40: return ('red', '🔴', f'上涨占比{b:.0f}% {d["active"]}')
                return ('yellow', '🟡', f'上涨{int(d["up"])}/下跌{int(d["down"])} {d["active"]}')
            if key == 'idx_ma':
                idx = d
                # 只统计有效数据(有 close 且无 error)
                valid_items = {n: v for n, v in idx.items()
                              if isinstance(v, dict) and 'close' in v and 'error' not in v}
                bull = sum(1 for v in valid_items.values() if v.get('ma_trend') == '多头')
                bear = sum(1 for v in valid_items.values() if v.get('ma_trend') == '空头')
                total_valid = len(valid_items)
                if total_valid == 0:
                    return ('gray', '⚫', '指数接口异常 暂无数据')
                details = [f"{n}={v['close']:.0f}({v['ma_trend']})" for n, v in valid_items.items()]
                if bull >= 2:
                    return ('green', '🟢', f'{bull}/{total_valid}多头 | ' + ' '.join(details))
                if bear >= 2:
                    return ('red', '🔴', f'{bear}/{total_valid}空头 | ' + ' '.join(details))
                return ('yellow', '🟡', '震荡分化 | ' + ' '.join(details))
            if key == 'turnover':
                if 'error' in d: return ('gray', '⚫', '接口错误')
                t = d['current']
                if t > 2: return ('yellow', '🟡', f'换手率={t:.2f}% 交投活跃')
                if t < 0.5: return ('gray', '⚫', f'换手率={t:.2f}% 冷清')
                return ('green', '🟢', f'换手率={t:.2f}% 正常')
            if key == 'volume':
                idx = d
                valid = {n: v for n, v in idx.items()
                        if isinstance(v, dict) and 'vol_ratio' in v and 'error' not in v}
                if not valid: return ('gray', '⚫', '指数接口异常')
                vols = [v['vol_ratio'] for v in valid.values()]
                avg_v = sum(vols) / len(vols)
                amounts = [v.get('amount_yi', 0) for v in valid.values()]
                total_yi = sum(amounts)
                if avg_v > 1.5: return ('red', '🔴', f'量比={avg_v:.2f} 放量过热 合计{total_yi:.0f}亿')
                if avg_v > 1.2: return ('yellow', '🟡', f'量比={avg_v:.2f} 温和放量 合计{total_yi:.0f}亿')
                if avg_v < 0.6: return ('gray', '⚫', f'量比={avg_v:.2f} 缩量 合计{total_yi:.0f}亿')
                return ('green', '🟢', f'量比={avg_v:.2f} 正常 合计{total_yi:.0f}亿')
            return ('gray', '⚫', '未知')
        # 颜色映射 (交通灯语义)
        LIGHT_COLORS = {
            'red': '#E53935',      # 亮红
            'yellow': '#FDD835',   # 亮黄
            'green': '#43A047',    # 亮绿
            'gray': '#BDBDBD',     # 灰
        }
        BG_COLORS = {
            'red': '#FFEBEE',      # 淡红底
            'yellow': '#FFFDE7',   # 淡黄底
            'green': '#E8F5E9',    # 淡绿底
            'gray': '#F5F5F5',     # 灰底
        }
        TEXT_COLORS = {
            'red': '#B71C1C',
            'yellow': '#F57F17',
            'green': '#1B5E20',
            'gray': '#757575',
        }
        ARROW_MAP = {
            'red': '▼ 减仓避险',
            'yellow': '▶ 控制仓位',
            'green': '▲ 积极加仓',
            'gray': '➤ 等待扫描',
        }
        def _draw_small_light(canvas, color_key):
            """重绘小圆灯"""
            c = LIGHT_COLORS.get(color_key, '#BDBDBD')
            canvas.delete("all")
            # 外环 (厚边框 = 更醒目)
            canvas.create_oval(4, 4, 46, 46, fill=c, outline="#424242", width=2)
            # 高光
            canvas.create_oval(10, 8, 28, 24, fill="white", outline="", stipple="gray25")
            # 脉冲 (红灯时)
            if color_key == 'red':
                canvas.create_oval(0, 0, 50, 50, outline=c, width=2)
        def _update_card(key, color, icon, text):
            info = indicator_cards[key]
            # Canvas 圆灯
            _draw_small_light(info['light'], color)
            # 文字
            fg = TEXT_COLORS.get(color, '#333')
            info['val'].config(text=text, fg=fg)
            # 卡片背景联动
            bg_c = BG_COLORS.get(color, 'white')
            info['card'].config(bg=bg_c)
            for child in info['card'].winfo_children():
                try: child.config(bg=bg_c)
                except: pass
            # 更新 row1 内部组件背景
            for sub in info['val'].master.winfo_children():
                try: sub.config(bg=bg_c)
                except: pass
        def _update_composite_light(color_key):
            """更新综合大圆灯 + 整行背景联动"""
            c = LIGHT_COLORS.get(color_key, '#BDBDBD')
            bg = BG_COLORS.get(color_key, '#F5F5F5')
            fg = TEXT_COLORS.get(color_key, '#333')
            # 重绘大圆灯
            light_canvas.delete("all")
            _draw_circle_light(light_canvas, 80, 80, 58, c, glow=(color_key == 'red'))
            # 整行背景
            mid_frame.config(bg=bg)
            for child in mid_frame.winfo_children():
                try: child.config(bg=bg)
                except:
                    for sub in child.winfo_children():
                        try: sub.config(bg=bg)
                        except:
                            for sub2 in sub.winfo_children():
                                try: sub2.config(bg=bg)
                                except: pass
            level_lbl.config(fg=fg)
            arrow_lbl.config(fg=fg, text=ARROW_MAP.get(color_key, '➤'))
        def _calc_composite(data):
            score = 50
            signals = []
            # 融资融券
            if 'margin' in data and 'error' not in data['margin']:
                c = data['margin']['avg_chg']
                if c > 3: score -= 10; signals.append(('🔴', f'融资+{c:.1f}% 杠杆过热警惕回调'))
                elif c > 0.5: score -= 3; signals.append(('🟡', f'融资+{c:.1f}% 温和加杠杆'))
                elif c < -2: score += 8; signals.append(('🟢', f'融资{c:.1f}% 杠杆清洗接近底部'))
                else: signals.append(('⚪', '融资余额稳定'))
            # 北向资金
            if 'north' in data and 'error' not in data['north']:
                n = data['north']
                if n['trend'] == '持续流入': score += 12; signals.append(('🟢', '北向持续流入 外资看多'))
                elif n['trend'] == '持续流出': score -= 12; signals.append(('🔴', '北向持续流出 外资减持'))
                else: signals.append(('🟡', '北向趋势不明'))
            # 涨跌停广度
            if 'breadth' in data and 'error' not in data['breadth']:
                b = data['breadth']
                lu = b['limit_up']; ld = b['limit_down']; br = b['breadth_pct']
                if lu >= 80 and ld <= 5: score += 15; signals.append(('🟢', '涨停潮 市场亢奋'))
                elif lu <= 10 and ld >= 30: score -= 15; signals.append(('🔴', '跌停潮 恐慌蔓延'))
                elif br >= 70: score += 6; signals.append(('🟡', f'上涨{int(b["up"])}:{int(b["down"])} 偏多'))
                elif br <= 40: score -= 6; signals.append(('🟡', f'下跌{int(b["down"])}:{int(b["up"])} 偏空'))
                else: signals.append(('⚪', '涨跌平衡'))
            # 指数 MA (过滤 error)
            if 'indices' in data:
                valid_idx = [v for v in data['indices'].values()
                            if isinstance(v, dict) and 'close' in v and 'error' not in v]
                bull = sum(1 for v in valid_idx if v.get('ma_trend') == '多头')
                bear = sum(1 for v in valid_idx if v.get('ma_trend') == '空头')
                if bull >= 2: score += 10; signals.append(('🟢', f'{bull}/{len(valid_idx)}指数多头排列 趋势向上'))
                elif bear >= 2: score -= 10; signals.append(('🔴', f'{bear}/{len(valid_idx)}指数空头排列 趋势向下'))
                elif valid_idx: signals.append(('⚪', '指数震荡分化'))
            # 换手率
            if 'turnover' in data and 'error' not in data['turnover']:
                t = data['turnover']['current']
                if t > 2: score -= 3; signals.append(('🟡', f'换手率{t:.2f}% 过热'))
                elif t < 0.5: score -= 2; signals.append(('⚪', f'换手率{t:.2f}% 冷清'))
                else: signals.append(('🟢', f'换手率{t:.2f}% 适中'))
            # 成交额 (过滤 error)
            if 'indices' in data:
                valid_idx2 = [v for v in data['indices'].values()
                             if isinstance(v, dict) and 'vol_ratio' in v and 'error' not in v]
                if valid_idx2:
                    avg_v = sum(v['vol_ratio'] for v in valid_idx2) / len(valid_idx2)
                    if avg_v > 1.5: score -= 3; signals.append(('🔴', '放量警惕过热'))
                    elif avg_v < 0.6: score += 2; signals.append(('⚪', '缩量观望'))
                    else: signals.append(('🟢', '量比正常'))
            score = max(0, min(100, score))
            level = ('🟢 绿灯·安全 (可积极加仓)' if score >= 65 else
                     '🟡 黄灯·警惕 (控制仓位)' if score >= 40 else
                     '🔴 红灯·危险 (减仓避险)')
            return score, level, signals
        # ===== 扫描按钮 =====
        def _run_scan():
            scan_btn.config(state=tk.DISABLED)
            status_var.set("⏳ 扫描A股情绪指标...")
            def _work():
                try:
                    data = _scan_a_share()
                    card_keys = [
                        ('margin', 'margin'), ('north', 'north'),
                        ('breadth', 'breadth'), ('idx_ma', 'indices'),
                        ('turnover', 'turnover'), ('volume', 'indices'),
                    ]
                    for ck, dk in card_keys:
                        d = data.get(dk, {})
                        color, icon, text = _judge_light(ck, d)
                        win.after(0, lambda c=ck, cl=color, ic=icon, tx=text: _update_card(c, cl, ic, tx))
                    score, level, signals = _calc_composite(data)
                    win.after(0, lambda: score_var.set(f"综合评分: {score}/100"))
                    win.after(0, lambda: level_var.set(level))
                    # ✅ Canvas 大圆灯 + 整行背景联动
                    if score >= 65: win.after(0, lambda: _update_composite_light('green'))
                    elif score >= 40: win.after(0, lambda: _update_composite_light('yellow'))
                    else: win.after(0, lambda: _update_composite_light('red'))
                    sig_text = "  ".join([f"{i}{d}" for i, d in signals[:6]])
                    win.after(0, lambda: signals_var.set(sig_text))
                    # 缓存
                    try:
                        with open(CACHE_FILE, 'w') as f:
                            json.dump({**data, 'score': score, 'level': level,
                                      'signals': signals, 'time': now.strftime('%Y-%m-%d %H:%M')},
                                     f, default=str, ensure_ascii=False)
                    except Exception:
                        pass
                    if ai_var.get():
                        win.after(0, lambda: status_var.set("🤖 AI 解读中..."))
                        _ai_interpret(data, score, level, signals)
                    else:
                        win.after(0, lambda: status_var.set(f"✅ 扫描完成! 评分 {score}/100"))
                except Exception as e:
                    import traceback
                    err = traceback.format_exc()
                    win.after(0, lambda: report_txt.delete("1.0", tk.END))
                    win.after(0, lambda e=e: report_txt.insert("1.0", f"❌ 扫描失败:\n{err[:2000]}"))
                    win.after(0, lambda e=e: status_var.set(f"❌ {str(e)[:60]}"))
                finally:
                    win.after(0, lambda: scan_btn.config(state=tk.NORMAL))
            threading.Thread(target=_work, daemon=True).start()
        def _ai_interpret(data, score, level, signals):
            summary = [f"【时间】{now.strftime('%Y-%m-%d %H:%M')}",
                      f"【综合评分】{score}/100 → {level}"]
            for i, d in signals: summary.append(f"  {i} {d}")
            if 'margin' in data and 'error' not in data['margin']:
                m = data['margin']
                summary.append(f"\n融资融券: 沪{m['sh_yi']:.0f}亿+深{m['sz_yi']:.0f}亿 7日={m['avg_chg']:+.1f}%")
            if 'north' in data and 'error' not in data['north']:
                n = data['north']
                summary.append(f"北向资金: {n['trend']} 3日={n['net_3d_yi']:+.0f}亿")
            if 'breadth' in data and 'error' not in data['breadth']:
                b = data['breadth']
                summary.append(f"涨跌广度: 涨停{b['limit_up']:.0f}/跌停{b['limit_down']:.0f} 上涨{b['breadth_pct']:.0f}%")
            if 'indices' in data:
                for nm, v in data['indices'].items():
                    if isinstance(v, dict) and 'close' in v:
                        summary.append(f"{nm}: {v['close']:.0f} 5日={v['chg_5d']:+.1f}% {v['ma_trend']} 量比={v['vol_ratio']:.2f}")
            if 'turnover' in data and 'error' not in data['turnover']:
                summary.append(f"换手率: {data['turnover']['current']:.2f}%")
            prompt = f"""基于以下A股市场情绪数据，判断当前大盘阶段并给出操作建议。
{chr(10).join(summary)}
请输出:
【一句话判定】红灯/黄灯/绿灯 + 操作建议（减仓/观望/低吸/加仓）
【杠杆信号】融资融券解读
【外资信号】北向资金解读
【市场结构】涨跌停广度 + 指数MA解读
【操作策略】仓位建议、买卖方向、重点板块
【风险预警】今日/近期黑天鹅信号
要求: 数据说话、结论明确、可执行。"""
            try:
                result = self.call_ai_model(prompt,
                                            system_prompt="你是A股市场情绪分析师，擅长从杠杆、外资、市场结构三维度量化判断大盘见顶/见底。",
                                            max_tokens=1500)
                win.after(0, lambda: _render_ai_report(result, score, level, signals))
                win.after(0, lambda: status_var.set(f"✅ 分析完成! 评分 {score}/100"))
            except Exception as e:
                win.after(0, lambda e=e: _render_ai_report(f"❌ AI 失败: {e}\n\n{chr(10).join(summary)}", score, level, signals))
                win.after(0, lambda e=e: status_var.set(f"AI 失败: {str(e)[:40]}"))
        scan_btn.configure(command=_run_scan)
        # 首次加载缓存
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r') as f:
                    cached = json.load(f)
                for ck, dk in [('margin','margin'),('north','north'),
                               ('breadth','breadth'),('idx_ma','indices'),
                               ('turnover','turnover'),('volume','indices')]:
                    d = cached.get(dk, {})
                    color, icon, text = _judge_light(ck, d)
                    _update_card(ck, color, icon, text)
                s = cached.get('score', 50); lv = cached.get('level', '')
                sigs = cached.get('signals', [])
                score_var.set(f"综合评分: {s}/100"); level_var.set(lv)
                signals_var.set("  ".join([f"{i}{d}" for i, d in sigs[:6]]))
                if s >= 65: _update_composite_light('green')
                elif s >= 40: _update_composite_light('yellow')
                else: _update_composite_light('red')
                status_var.set(f"📂 已加载缓存 ({cached.get('time', '')})")
        except Exception:
            pass
        win.after(100, _run_scan)  # 自动扫描

    def _show_divergence_t_v2(self):
        """背离做T v2：盘中实时/盘后大盘S1-S4分析 + AI建议 + 资讯表保存"""
        import datetime as dt
        import threading
        import tkinter as tk
        from tkinter import messagebox, scrolledtext, ttk
        win = self._safe_toplevel(self.root)
        win.title("📈 背离做T · 大盘阶段分析 + AI建议")
        win.geometry("1200x920")
        win.minsize(1000, 780)
        now = dt.datetime.now()
        is_trading = self._is_a_share_trading_time(now)
        # ===== Banner =====
        banner_color = "#C62828" if is_trading else "#1565C0"
        banner = tk.Frame(win, bg=banner_color, height=56); banner.pack(fill=tk.X)
        tk.Label(banner, text="📈 背离做T", bg=banner_color, fg="white",
                 font=("", 16, "bold")).pack(side=tk.LEFT, padx=14, pady=10)
        tk.Label(banner, text=(
            f"⏰ 盘中实时模式（{now.strftime('%H:%M')}）— 分钟级背离检测"
            if is_trading else
            f"🌙 盘后分析模式（{now.strftime('%Y-%m-%d %H:%M')}）— 大盘S1-S4阶段 + AI建议"
        ), bg=banner_color, fg="#FFE0B2" if is_trading else "#BBDEFB",
                 font=("", 11)).pack(side=tk.LEFT, pady=14)
        # ===== 顶部控制 =====
        ctrl = tk.Frame(win); ctrl.pack(fill=tk.X, padx=10, pady=6)
        INDEX_DEFS = [("上证指数", "000001"), ("深证成指", "399001"), ("创业板指", "399006")]
        idx_names = [d[0] for d in INDEX_DEFS]
        tk.Label(ctrl, text="📊 指数:", font=("", 10)).pack(side=tk.LEFT)
        idx_var = tk.StringVar(value=idx_names[0])
        ttk.Combobox(ctrl, textvariable=idx_var, values=idx_names,
                     state="readonly", width=10).pack(side=tk.LEFT, padx=4)
        if is_trading:
            tk.Label(ctrl, text=" 周期:", font=("", 10)).pack(side=tk.LEFT)
            period_var = tk.StringVar(value="5分钟")
            ttk.Combobox(ctrl, textvariable=period_var,
                         values=["1分钟", "5分钟", "15分钟", "30分钟"],
                         state="readonly", width=8).pack(side=tk.LEFT, padx=4)
        tk.Label(ctrl, text=" 历史对比天数:", font=("", 10)).pack(side=tk.LEFT, padx=(12, 0))
        hist_var = tk.IntVar(value=3)
        tk.Spinbox(ctrl, from_=0, to=30, width=4, textvariable=hist_var).pack(side=tk.LEFT, padx=4)
        analyze_btn = tk.Button(ctrl, text="🔍 开始分析", font=("", 11, "bold"),
                                    bg=banner_color, fg="white", padx=16, pady=3, cursor="hand2")
        analyze_btn.pack(side=tk.LEFT, padx=10)
        # ===== 🎯 做T5大方法 + 一键检测 =====
        _method_frame = ttk.LabelFrame(win, text="🎯 做T5大方法 · 核心原则", padding=6)
        _method_frame.pack(fill=tk.X, padx=10, pady=(2, 4))
        _method_txt = tk.Text(_method_frame, height=6, font=("PingFang SC", 10),
                              wrap=tk.WORD, bg="#FFFDE7", relief=tk.FLAT)
        _method_txt.pack(fill=tk.X, side=tk.LEFT, expand=True)
        _METHOD_CONTENT = """
🎯 方法① 15分钟K线体系: MA5/MA10金叉死叉 + MACD + KDJ + 布林带 + 量价配合 — 日内波段的"路标"
🎯 方法② 分时均线法则: 白线(股价) vs 黄线(均价线)位置乖离 — 跑远均价线→迟早回来
🎯 方法③ 大小周期共振: 日线定方向→60分钟定波段→15分钟找买点 — 大周期指路,小周期动手
🎯 方法④ 情绪周期法: 9:30开盘确立方向 / 10:00前日高日低 / 14:30尾盘窗口 — 关键时间做关键决策
🎯 方法⑤ 乖离率BIAS辅助: BIAS±2.5%视为超买超卖 — 偏离均值太多→物极必反
💡 核心原则: 大盘指引方向,个股决定操作
  大盘日线向上 → 回调买T,反弹卖T (顺势)
  大盘日线向下 → 谨慎做T,轻仓快出
  大盘单边下跌 → 不接飞刀
""".strip()
        _method_txt.insert("1.0", _METHOD_CONTENT)
        _method_txt.config(state=tk.DISABLED)
        # 一键跑5大方法量化检测按钮
        _detect_btn = tk.Button(_method_frame, text="⚡ 跑5大方法检测",
                                    font=("", 10, "bold"), bg="#FF6F00", fg="white",
                                    padx=10, pady=4, cursor="hand2")
        _detect_btn.pack(side=tk.RIGHT, padx=(6, 0))
        # ===== 早盘 S-T 指导 Skill 按钮 =====
        SKILL_MORNING_DIR = os.path.expanduser("~/.qclaw/skills/早盘S-T指导")
        SKILL_MORNING_SCRIPT = os.path.join(SKILL_MORNING_DIR, "scripts", "morning_run.py")
        def _run_morning_skill():
            """调用早盘 S-T 指导 Skill (morning_run.py --json)"""
            import json as _json
            import subprocess
            if not os.path.isfile(SKILL_MORNING_SCRIPT):
                messagebox.showwarning("Skill 未找到",
                    f"早盘S-T指导 Skill 不存在:\n{SKILL_MORNING_SCRIPT}\n\n"
                    f"请先在 Skill 浏览器里安装: ☀️早盘S-T指导")
                return
            report_txt.delete("1.0", tk.END)
            report_txt.insert("1.0", "⏳ 调用早盘 S-T 指导 Skill...\n(腾讯行情接口拉 5 个数字 → 权重打分 → S1-S4 判定)\n")
            def _mwork():
                try:
                    import subprocess as _sp
                    proc = _sp.run(
                        [sys.executable, SKILL_MORNING_SCRIPT, "--json"],
                        capture_output=True, text=True, timeout=20,
                        env={**os.environ, "PATH": "/Library/Frameworks/Python.framework/Versions/3.11/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"})
                    out = proc.stdout.strip()
                    err = proc.stderr.strip()
                    # 找 JSON（防止前面有日志打印）
                    _json_str = out
                    _start = out.find("{")
                    if _start > 0:
                        _json_str = out[_start:]
                    data = _json.loads(_json_str)
                    # 格式化输出
                    phase = data.get("phase", "?")
                    phase_name = data.get("phase_name", "")
                    direction = data.get("direction", "")
                    conf_stars = data.get("confidence_stars", "")
                    details = data.get("details", {})
                    advice_list = data.get("advice", [])
                    inputs = data.get("inputs", {})
                    score = data.get("phase_score", 0)
                    # 顶部卡片更新
                    _d_map2 = {"S1": ("S1", "强势上涨"), "S2": ("S2", "震荡上行"),
                               "S3": ("S3", "震荡下行"), "S4": ("S4", "弱势下跌")}
                    _ss, _dd = _d_map2.get(phase, (phase, phase_name))
                    for _n, _c in INDEX_DEFS:
                        try:
                            stage_labels[_n]["price"].configure(text="现价: Skill拉取中...")
                            stage_labels[_n]["ma"].configure(text="MA: Skill打分", fg="#666")
                            stage_labels[_n]["stage"].configure(
                                    text=f"{_ss} {_dd} [早盘Skill]",
                                    fg={"S1": "#C62828", "S2": "#E65100",
                                    "S3": "#1565C0", "S4": "#2E7D32"}.get(_ss, "#888"))
                            stage_labels[_n]["suggest"].configure(text=f"做T: {direction[:25]}",
                                    fg={"S1": "#C62828", "S2": "#E65100",
                                    "S3": "#1565C0", "S4": "#2E7D32"}.get(_ss, "#888"))
                        except Exception: pass
                    # 做T建议摘要
                    win.after(0, lambda: t_summary_var.set(
                        f"☀️ 早盘Skill判定: {phase}({phase_name}) {direction} ★{conf_stars} 得分={score:.1f}"))
                    # 格式化大报告
                    _report_lines = [
                        "═══ ☀️ 早盘S-T指导 Skill 报告 ═══",
                        f"⏰ {now.strftime('%Y-%m-%d %H:%M')}  |  数据来源: 腾讯财经 qt.gtimg.cn",
                        "",
                        "═══ 一、阶段判定 ═══",
                        f"· 大盘阶段: {phase} {phase_name}",
                        f"· 做T方向: {direction}",
                        f"· 置信度: {conf_stars}  (得分={score:.2f})",
                        "",
                        "═══ 二、5 维度打分详情 ═══",
                    ]
                    _w_map = {"隔夜外盘":20, "昨日涨幅":20, "昨成交额":10, "集合竞价":25, "9:45位":25}
                    for _k, _v in details.items():
                        _w = _w_map.get(_k, 0)
                        _score = _v.get("score", 0)
                        _contrib = _v.get("contribution", 0)
                        _label = _v.get("label", "")
                        _bar = "█" * int(_score/5) + "░" * (20 - int(_score/5))
                        _report_lines.append(
                            f"  {_k} [{_w}%] {_label}  得分={_score:.1f} 贡献={_contrib:+.1f}  {_bar}")
                    _report_lines += [
                        "",
                        "═══ 三、原始输入数字 ═══",
                        (f"  外盘={inputs.get('overnight', '?'):+.2f}%  昨涨={inputs.get('prev_pct', '?'):+.2f}%  "
                        f"昨额={inputs.get('prev_volume', '?'):.1f}亿  竞价={inputs.get('auction', '?'):+.2f}%  "
                        f"9:45={inputs.get('m15', '?'):+.2f}%"),
                        "",
                        "═══ 四、操作建议 ═══",
                    ]
                    for _i, _a in enumerate(advice_list, 1):
                        _report_lines.append(f"  {_i}. {_a}")
                    _report_lines += [
                        "",
                        "═══ 五、与自研盘面诊断对比 ═══",
                        f"  Skill: {phase}({phase_name}) {direction}",
                        "  自研DB: 从资讯表读（盘面诊断 tab_name 里的 S 阶段）",
                        "  → 两者方向一致就大胆做T，矛盾就观望",
                    ]
                    if err:
                        _report_lines += ["", f"(stderr: {err[:300]})"]
                    win.after(0, lambda: report_txt.delete("1.0", tk.END))
                    win.after(0, lambda: report_txt.insert("1.0", "\n".join(_report_lines)))
                    win.after(0, lambda: status_var.set(f"☀️ 早盘Skill完成: {phase}({phase_name})"))
                except subprocess.TimeoutExpired:
                    win.after(0, lambda: report_txt.insert(tk.END, "\n⏰ Skill 执行超时（20s）"))
                except Exception as _e:
                    import traceback as _tb
                    win.after(0, lambda _e=_e: report_txt.insert(tk.END,
                        f"\n❌ Skill 执行失败: {_e}\n\n{_tb.format_exc()[:1500]}"))
            threading.Thread(target=_mwork, daemon=True).start()
        morning_btn = tk.Button(ctrl, text="☀️ 早盘S-T指导", font=("", 11, "bold"),
                                    bg="#F57F17", fg="white", padx=14, pady=3, cursor="hand2",
                                    activebackground="#E65100", activeforeground="white")
        morning_btn.pack(side=tk.LEFT, padx=6)
        morning_btn.configure(command=_run_morning_skill)
        # ===== 大盘 S1-S4 卡片（盘后模式更详细）=====
        market_frame = tk.LabelFrame(win, text="🗺️ 大盘阶段诊断 S1-S4",
                                      font=("", 11, "bold"), fg=banner_color)
        market_frame.pack(fill=tk.X, padx=10, pady=(0, 6))
        stage_labels = {}  # key -> label
        for i, (name, _code) in enumerate(INDEX_DEFS):
            row_f = tk.Frame(market_frame); row_f.pack(fill=tk.X, padx=8, pady=2)
            tk.Label(row_f, text=f"【{name}】", font=("", 10, "bold"), width=10,
                     anchor="w").pack(side=tk.LEFT)
            stage_labels[name] = {
                "price": tk.Label(row_f, text="现价: --", font=("", 10)),
                "ma": tk.Label(row_f, text="MA5/10/20/60: --", font=("", 10), fg="#666"),
                "stage": tk.Label(row_f, text="阶段: --", font=("", 11, "bold"), fg="#888"),
                "suggest": tk.Label(row_f, text="做T方向: --", font=("", 10)),
            }
            for k, lbl in stage_labels[name].items():
                lbl.pack(side=tk.LEFT, padx=(4 if k != "stage" else 14, 4))
        # ===== 做T建议摘要 =====
        t_frame = tk.LabelFrame(win, text="💡 今日做T方向建议",
                                 font=("", 11, "bold"), fg=banner_color)
        t_frame.pack(fill=tk.X, padx=10, pady=(0, 6))
        t_summary_var = tk.StringVar(
            value="点击「🔍开始分析」获取大盘阶段诊断 + 做T方向建议")
        tk.Label(t_frame, textvariable=t_summary_var, font=("", 12, "bold"),
                 fg=banner_color, wraplength=1100, justify="left",
                 anchor="w", bg="#FFF8E1" if banner_color == "#C62828" else "#E3F2FD",
                 padx=10, pady=8).pack(fill=tk.X, padx=6, pady=6)
        # ===== 主结果区 =====
        main_paned = ttk.Panedwindow(win, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        # 左：分析报告
        left_f = tk.Frame(main_paned); main_paned.add(left_f, weight=3)
        report_f = tk.LabelFrame(left_f, text="📋 AI 分析报告",
                                  font=("", 11, "bold"), fg=banner_color)
        report_f.pack(fill=tk.BOTH, expand=True)
        report_txt = scrolledtext.ScrolledText(report_f, font=("", 11), wrap=tk.WORD,
                                                padx=12, pady=10, bg="#FAFAFA")
        report_txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._enable_text_copy_menu(report_txt, readonly=False)
        # ===== ⚡ 5大做T方法 · 量化检测 =====
        def _detect_5_methods():
            """基于当前选中的指数,跑5大做T方法的量化信号检测"""
            import math as _math
            report_txt.delete("1.0", tk.END)
            report_txt.insert("1.0", "⏳ 正在跑 5 大做T方法量化检测...\n\n")
            report_txt.update()
            def _worker():
                try:
                    import akshare as _ak
                    _idx_code = "000001" if idx_var.get() == "上证指数" else (
                        "399001" if idx_var.get() == "深证成指" else "399006")
                    # tushare ts_code 映射
                    _ts_map = {"000001": "000001.SH", "399001": "399001.SZ", "399006": "399006.SZ"}
                    _ts_code = _ts_map.get(_idx_code, _idx_code + ".SH")
                    report_txt.after(0, lambda: report_txt.insert(tk.END,
                        f"📊 数据源: akshare/tushare 指数日线, 标的={idx_var.get()}\n"))
                    # 统一列名适配: 把 tushare 英文列转成中文, 跟 akshare 对齐
                    def _normalize_df(_d):
                        if _d is None or len(_d) == 0:
                            return None
                        # tushare -> akshare 列名映射
                        _rename = {"close": "收盘", "open": "开盘", "high": "最高", "low": "最低",
                                   "vol": "成交量", "amount": "成交额", "trade_date": "日期"}
                        _d = _d.rename(columns=_rename)
                        # 确保日期是字符串且排序正确
                        if "日期" in _d.columns:
                            _d = _d.sort_values("日期").reset_index(drop=True)
                        return _d
                    # 拉日线数据(60天) — akshare 优先, tushare 备用
                    _df = None
                    try:
                        _df = _ak.index_zh_a_hist(symbol=_idx_code, period="daily",
                                                  start_date=(dt.datetime.now() - dt.timedelta(days=90)).strftime("%Y%m%d"),
                                                  end_date=dt.datetime.now().strftime("%Y%m%d"))
                        if _df is not None and len(_df) >= 10:
                            report_txt.after(0, lambda: report_txt.insert(tk.END,
                                    f"✅ akshare日线 OK: {len(_df)} 行\n"))
                    except Exception as _e1:
                        report_txt.after(0, lambda: report_txt.insert(tk.END,
                            "⚠️ akshare日线断,尝试 tushare 备用...\n"))
                        _df = None
                    if _df is None or len(_df) < 10:
                        try:
                            import tushare as _ts
                            _pro = _ts.pro_api()
                            _df = _pro.index_daily(ts_code=_ts_code,
                                                   start_date=(dt.datetime.now() - dt.timedelta(days=120)).strftime("%Y%m%d"),
                                                   end_date=dt.datetime.now().strftime("%Y%m%d"))
                            _df = _normalize_df(_df)
                            report_txt.after(0, lambda: report_txt.insert(tk.END,
                                    f"✅ tushare日线 OK: {len(_df) if _df is not None else 0} 行\n"))
                        except Exception as _e2:
                            report_txt.after(0, lambda _e2=_e2: report_txt.insert(tk.END,
                                    f"❌ tushare也失败: {_e2}\n"))
                            _df = None
                    # 拉15分钟线(盘中才拉,没tushare备用)
                    _df_15 = None
                    if is_trading:
                        try:
                            _df_15 = _ak.index_zh_a_hist_min_em(symbol=_idx_code, period="15")
                        except Exception:
                            _df_15 = None
                    results = []
                    # === 方法① 15分钟K线体系 ===
                    m1_signals = []
                    if _df_15 is not None and len(_df_15) >= 20:
                        _c15 = _df_15["收盘"].astype(float).values
                        ma5_15 = sum(_c15[-5:]) / 5
                        ma10_15 = sum(_c15[-10:]) / 10
                        ma20_15 = sum(_c15[-20:]) / 20
                        # MACD 简化: EMA12 - EMA26
                        def _ema(arr, n):
                            k = 2 / (n + 1)
                            ema = [arr[0]]
                            for i in range(1, len(arr)):
                                    ema.append(arr[i] * k + ema[-1] * (1 - k))
                            return ema[-1]
                        ema12 = _ema(_c15, 12)
                        ema26 = _ema(_c15, 26)
                        dif = ema12 - ema26
                        # 金叉死叉
                        if ma5_15 > ma10_15 > ma20_15: m1_signals.append("✅MA多头排列(MA5>MA10>MA20)")
                        elif ma5_15 < ma10_15 < ma20_15: m1_signals.append("⚠️MA空头排列")
                        else: m1_signals.append("🔄MA交叉震荡")
                        if dif > 0: m1_signals.append("✅MACD柱正(多头)")
                        else: m1_signals.append("⚠️MACD柱负(空头)")
                        # 布林带位置
                        std20 = _math.sqrt(sum((x - ma20_15)**2 for x in _c15[-20:]) / 20)
                        boll_up = ma20_15 + 2 * std20
                        boll_low = ma20_15 - 2 * std20
                        cur = _c15[-1]
                        boll_pct = (cur - boll_low) / (boll_up - boll_low) * 100 if boll_up != boll_low else 50
                        if boll_pct < 20: m1_signals.append(f"✅布林位置{boll_pct:.0f}%(近下轨,关注反弹)")
                        elif boll_pct > 80: m1_signals.append(f"⚠️布林位置{boll_pct:.0f}%(近上轨,警惕回调)")
                        else: m1_signals.append(f"➖布林位置{boll_pct:.0f}%(中轨附近)")
                    else:
                        m1_signals.append("⏸️非盘中/数据不足,跳过15分钟K线检测")
                    results.append(("① 15分钟K线体系", m1_signals))
                    # === 方法② 分时均线法则 (日线版) ===
                    m2_signals = []
                    if _df is not None and len(_df) >= 10:
                        _c = _df["收盘"].astype(float).values
                        ma5_d = sum(_c[-5:]) / 5
                        sum(_c[-10:]) / 10
                        cur_d = _c[-1]
                        # 股价 vs MA5 乖离
                        bias5 = (cur_d - ma5_d) / ma5_d * 100
                        if bias5 > 2.5: m2_signals.append(f"⚠️白线(价)↑远黄线(MA5) 乖离+{bias5:.2f}% 超买,考虑卖T")
                        elif bias5 < -2.5: m2_signals.append(f"✅白线(价)↓远黄线(MA5) 乖离{bias5:.2f}% 超卖,考虑买T")
                        else: m2_signals.append(f"➖白线黄线乖离{bias5:+.2f}% 在正常区间")
                    else:
                        m2_signals.append("⏸️日线数据不足,跳过检测")
                    results.append(("② 分时均线法则", m2_signals))
                    # === 方法③ 大小周期共振 ===
                    m3_signals = []
                    if _df is not None and len(_df) >= 60:
                        _c = _df["收盘"].astype(float).values
                        sum(_c[-5:]) / 5
                        sum(_c[-10:]) / 10
                        ma20 = sum(_c[-20:]) / 20
                        ma60 = sum(_c[-60:]) / 60
                        cur = _c[-1]
                        # 大周期(日线)方向
                        if ma20 > ma60 and cur > ma60:
                            m3_signals.append("📈日线大周期向上 (MA20>MA60,价>MA60) → 顺势做T方向:回调买T,反弹卖T")
                            # 小周期(15分钟)找买点
                            if _df_15 is not None:
                                    m3_signals.append("🔍建议在15分钟K线回踩MA10/MA20时买T")
                        elif ma20 < ma60 and cur < ma60:
                            m3_signals.append("📉日线大周期向下 (MA20<MA60,价<MA60) → 谨慎做T,轻仓快出,不接飞刀")
                        else:
                            m3_signals.append("🔄日线大周期震荡 → 高抛低吸,控制仓位")
                    else:
                        m3_signals.append("⏸️日线数据不足60天,跳过大小周期共振")
                    results.append(("③ 大小周期共振", m3_signals))
                    # === 方法④ 情绪周期法 (时间节点提醒) ===
                    m4_signals = []
                    _now_time = dt.datetime.now()
                    _t_min = _now_time.hour * 60 + _now_time.minute
                    if _now_time.weekday() >= 5:
                        m4_signals.append("🌙 今日周末,无情绪周期信号")
                    elif 9*60+25 <= _t_min <= 9*60+35:
                        m4_signals.append("⏰ 9:25-9:35 开盘集合竞价结束→开盘方向确立的关键10分钟!看高开/低开/平开决定今日做T方向")
                    elif 9*60+55 <= _t_min <= 10*60+5:
                        m4_signals.append("⏰ 9:55-10:05 开盘后前30分钟→前日高/低点是否突破确立! 突破前高→顺势买T,跌破前低→观望")
                    elif 10*60 <= _t_min <= 11*60+30:
                        m4_signals.append("⏰ 10:00-11:30 早盘主升浪阶段→上午10点左右往往是全天高点/低点形成时间")
                    elif 13*60 <= _t_min <= 14*60:
                        m4_signals.append("⏰ 13:00-14:00 午盘重启→上午尾盘方向确立后,午后做T跟随")
                    elif 14*60+20 <= _t_min <= 14*60+40:
                        m4_signals.append("⏰ 14:20-14:40 尾盘窗口! 最后20分钟是当天做T的黄金买卖时间")
                    elif 14*60+50 <= _t_min <= 15*60:
                        m4_signals.append("⏰ 14:50-15:00 尾盘竞价→持仓过夜或清仓的最终决策时间")
                    else:
                        m4_signals.append(f"⏰ 当前时间 {_now_time.strftime('%H:%M')} 非关键窗口, 等待下一个节点")
                    results.append(("④ 情绪周期法", m4_signals))
                    # === 方法⑤ 乖离率BIAS辅助 ===
                    m5_signals = []
                    if _df is not None and len(_df) >= 20:
                        _c = _df["收盘"].astype(float).values
                        cur = _c[-1]
                        bias5 = (cur - sum(_c[-5:])/5) / (sum(_c[-5:])/5) * 100
                        bias10 = (cur - sum(_c[-10:])/10) / (sum(_c[-10:])/10) * 100
                        bias20 = (cur - sum(_c[-20:])/20) / (sum(_c[-20:])/20) * 100
                        if bias5 > 2.5: m5_signals.append(f"⚠️BIAS5={bias5:+.2f}% 超买>2.5% → 卖T信号!")
                        elif bias5 < -2.5: m5_signals.append(f"✅BIAS5={bias5:+.2f}% 超卖<-2.5% → 买T信号!")
                        else: m5_signals.append(f"➖BIAS5={bias5:+.2f}% 在±2.5%正常区间")
                        if bias10 > 2.5: m5_signals.append(f"⚠️BIAS10={bias10:+.2f}% 超买")
                        elif bias10 < -2.5: m5_signals.append(f"✅BIAS10={bias10:+.2f}% 超卖")
                        else: m5_signals.append(f"➖BIAS10={bias10:+.2f}% 正常")
                        if bias20 > 3.5: m5_signals.append(f"⚠️BIAS20={bias20:+.2f}% 中期超买")
                        elif bias20 < -3.5: m5_signals.append(f"✅BIAS20={bias20:+.2f}% 中期超卖")
                        else: m5_signals.append(f"➖BIAS20={bias20:+.2f}% 正常")
                    else:
                        m5_signals.append("⏸️日线数据不足,跳过乖离率检测")
                    results.append(("⑤ 乖离率BIAS辅助", m5_signals))
                    # 汇总判定
                    buy_hits = sum(1 for _, sigs in results for s in sigs if "✅" in s)
                    sell_hits = sum(1 for _, sigs in results for s in sigs if "⚠️" in s)
                    if buy_hits >= 3 and sell_hits <= 1:
                        overall = "🟢 建议: 今日偏买入做T方向 (买T信号多)"
                    elif sell_hits >= 3 and buy_hits <= 1:
                        overall = "🔴 建议: 今日偏卖出/观望 (卖T信号多,谨慎)"
                    elif buy_hits >= 2 and sell_hits >= 2:
                        overall = "🟡 建议: 今日震荡为主,高抛低吸,控制仓位"
                    else:
                        overall = "⚪ 建议: 信号不明确,观望为主"
                    # 输出到 report_txt
                    _out_lines = [f"## ⚡ 5大做T方法检测结果 — {idx_var.get()}\n",
                                  f"📅 {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
                    for _title, _sigs in results:
                        _out_lines.append(f"\n### {_title}")
                        for _s in _sigs:
                            _out_lines.append(f"  {_s}")
                    _out_lines.append(f"\n---\n**综合判定**: {overall}")
                    _out_lines.append("\n💡 核心原则: 大盘指引方向,个股决定操作 — 大盘向上回调买T/反弹卖T,大盘向下谨慎做T轻仓快出!")
                    report_txt.after(0, lambda: (
                        report_txt.delete("1.0", tk.END),
                        report_txt.insert("1.0", "\n".join(_out_lines))
                    ))
                except Exception as _e:
                    report_txt.after(0, lambda _e=_e: report_txt.insert(tk.END,
                        f"\n❌ 检测出错: {type(_e).__name__}: {_e}\n请检查 akshare/tushare 数据源"))
            threading.Thread(target=_worker, daemon=True).start()
        _detect_btn.config(command=_detect_5_methods)
        # 右：历史对比 + 保存
        right_f = tk.Frame(main_paned); main_paned.add(right_f, weight=2)
        hist_f = tk.LabelFrame(right_f, text="📜 历史做T分析记录（从资讯表）",
                                    font=("", 11, "bold"), fg=banner_color)
        hist_f.pack(fill=tk.BOTH, expand=True)
        hist_txt = scrolledtext.ScrolledText(hist_f, font=("", 10), wrap=tk.WORD,
                                              padx=10, pady=8, bg="#FFFDE7")
        hist_txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._enable_text_copy_menu(hist_txt, readonly=True)
        # 按钮
        btn_row = tk.Frame(right_f); btn_row.pack(fill=tk.X, pady=(6, 0))
        tk.Button(btn_row, text="💾 保存到资讯表", font=("", 10, "bold"),
                  bg="#2E7D32", fg="white", padx=10, pady=2, cursor="hand2").pack(
            side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="📜 刷新历史", font=("", 10), padx=10, pady=2,
                  cursor="hand2").pack(side=tk.LEFT, padx=4)
        # ===== 状态栏 =====
        status_var = tk.StringVar(value=f"💡 当前: {'盘中' if is_trading else '盘后'} | 指数: {idx_var.get()}")
        tk.Label(win, textvariable=status_var, anchor="w", font=("", 10),
                 bg="#ECEFF1", fg="#37474F", padx=10, pady=3).pack(fill=tk.X, side=tk.BOTTOM)
        # ===== 核心：开始分析 =====
        _busy = [False]
        def _load_history():
            """从资讯表读取最近 N 天的做T分析记录"""
            try:
                import sqlite3
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute(
                    "SELECT tab_name, content, created_at FROM news_info "
                    "WHERE tab_name LIKE '做T%' OR tab_name LIKE '大盘%阶段%' "
                    "ORDER BY created_at DESC LIMIT 20")
                rows = cur.fetchall(); conn.close()
                if not rows:
                    hist_txt.delete("1.0", tk.END)
                    hist_txt.insert("1.0", "（暂无历史做T分析记录）\n\n点「🔍开始分析」→ 「💾保存到资讯表」后这里会出现记录。")
                    return
                hist_txt.delete("1.0", tk.END)
                for tab, content, created in rows:
                    short = content[:200].replace('\n', ' ') if content else ""
                    hist_txt.insert(tk.END,
                        f"═══ {created} / {tab} ═══\n{short}...\n\n")
            except Exception as e:
                hist_txt.delete("1.0", tk.END)
                hist_txt.insert("1.0", f"读取历史失败: {e}")
        def _save_to_news():
            body = report_txt.get("1.0", tk.END).strip()
            if not body or "⏳" in body[:20]:
                messagebox.showinfo("提示", "请先点「🔍开始分析」生成报告")
                return
            tab_name = f"做T分析_{now.strftime('%m%d_%H%M')}_{idx_var.get()}"
            try:
                if save_news_info_to_db(tab_name, body):
                    messagebox.showinfo("✅", f"已保存到资讯表:\n{tab_name}")
                    _load_history()
                    status_var.set(f"✅ 已保存: {tab_name}")
                else:
                    messagebox.showerror("❌", "保存失败")
            except Exception as e:
                messagebox.showerror("❌", f"保存异常: {e}")
        def _run_analysis():
            nonlocal _busy
            if _busy[0]: return
            _busy[0] = True; analyze_btn.config(state=tk.DISABLED)
            report_txt.delete("1.0", tk.END)
            report_txt.insert("1.0", "⏳ 读取自研盘面诊断 + AI 分析中...")
            def _work():
                import sqlite3 as _sqlite3
                # ===== 1. 自研系统数据源（秒读DB，零网络请求）=====
                diy_diagnosis = ""
                diy_sentiment = ""
                diy_news = ""
                diy_stage_hint = ""
                index_data = {}  # 始终空 —— 不再拉指数
                stage_results = []
                try:
                    conn = _sqlite3.connect(DB_PATH); cur = conn.cursor()
                    # 1a. 盘面诊断
                    cur.execute("SELECT tab_name, content, created_at FROM news_info "
                                    "WHERE tab_name LIKE '[盘面诊断]%' ORDER BY id DESC LIMIT 1")
                    row = cur.fetchone()
                    if row:
                        tname, tcontent, tcreated = row
                        diy_stage_hint = tname.split("_")[-1] if "_S" in tname else ""
                        diy_diagnosis = f"（{tcreated} 自研盘面诊断，阶段{diy_stage_hint}）\n{tcontent}"
                    # 1b. sentiment_history 快照
                    cur.execute("SELECT snapshot_date, m1_today, m2_up, m2_down, m5_hs300, m5_zz500, m5_kc30, m5_avg FROM sentiment_history ORDER BY id DESC LIMIT 1")
                    srow = cur.fetchone()
                    if srow:
                        diy_sentiment = f"（{srow[0]}）"
                        if srow[1] is not None: diy_sentiment += f" m1={srow[1]:+.2f}%"
                        if srow[2] is not None: diy_sentiment += f" 涨跌比={srow[2]}/{srow[3]}"
                        if srow[4] is not None: diy_sentiment += f" 沪深300={srow[4]:+.2f}%"
                        if srow[5] is not None: diy_sentiment += f" 中证500={srow[5]:+.2f}%"
                        if srow[6] is not None: diy_sentiment += f" 科创50={srow[6]:+.2f}%"
                        if srow[7] is not None: diy_sentiment += f" 平均={srow[7]:+.2f}%"
                    # 1c. 3 大来源舆情 (缩减)
                    cur.execute("SELECT tab_name, content FROM news_info WHERE tab_name IN "
                                    "('东方财富','同花顺','雪球') ORDER BY id DESC LIMIT 3")
                    news_rows = cur.fetchall()
                    if news_rows:
                        news_parts = []
                        for nt, nc in news_rows:
                            short = (nc or "")[:150].replace('\n', ' ')
                            news_parts.append(f"【{nt}】{short}")
                        diy_news = "\n".join(news_parts)
                    conn.close()
                except Exception as e:
                    print(f"自研数据源读取失败: {e}")
                # ===== 2. 从自研盘面诊断生成三指数 stage_results =====
                proxy_stage = diy_stage_hint or "S3"
                _d_map = {"S1": ("S1", "强势上涨"), "S2": ("S2", "震荡上行"),
                          "S3": ("S3", "震荡下行"), "S4": ("S4", "弱势下跌")}
                _s, _d = _d_map.get(proxy_stage, ("S3", "震荡下行"))
                _dir = "先卖后买（高抛低吸）" if _s in ("S1", "S2") else "先买后卖（低吸高抛）"
                for _n, _c in INDEX_DEFS:
                    stage_results.append((_n, None, None, None, None, None, _s, _d, _dir, "自研·盘面诊断"))
                # 更新顶部卡片
                for item in stage_results:
                    name, cur, ma5, ma10, ma20, ma60, stage, desc, direction, src = item
                    try:
                        stage_labels[name]["price"].configure(
                            text=f"现价: {cur:.2f}" if cur else "现价: 自研",
                            fg="#C62828" if (cur and ma20 and cur > ma20) else "#2E7D32")
                        stage_labels[name]["ma"].configure(
                            text=f"MA5={ma5:.2f} MA10={ma10:.2f} MA20={ma20:.2f} MA60={ma60:.2f}"
                                    if ma5 else f"MA: {src or '自研'}", fg="#666")
                        stage_color = {"S1": "#C62828", "S2": "#E65100",
                                       "S3": "#1565C0", "S4": "#2E7D32"}.get(stage, "#888")
                        src_tag = f" [{src}]" if src else ""
                        stage_labels[name]["stage"].configure(
                            text=f"{stage} {desc}{src_tag}", fg=stage_color)
                        stage_labels[name]["suggest"].configure(
                            text=f"做T: {direction[:20]}", fg=stage_color)
                    except Exception:
                        pass
                # 汇总做T方向
                s_counts = {}
                for _, _, _, _, _, _, stage, _, _, _ in stage_results:
                    s_counts[stage] = s_counts.get(stage, 0) + 1
                if s_counts.get("S1", 0) + s_counts.get("S2", 0) >= 2:
                    overall_dir = "🟢 先卖后买（高抛为主）"
                elif s_counts.get("S3", 0) + s_counts.get("S4", 0) >= 2:
                    overall_dir = "🔵 先买后卖（低吸为主）"
                else:
                    overall_dir = "⚪ 混合信号，轻仓谨慎做T"
                # ===== 盘中分钟线拉取：已禁用（全部走自研系统，秒出）=====
                divergence_info = []
                # ===== 组装 AI prompt =====
                stage_summary_lines = []
                for name, cur, ma5, ma10, ma20, ma60, stage, desc, direction, src in stage_results:
                    src_note = f"（数据源: {src}）" if src else ""
                    stage_summary_lines.append(
                        f"【{name}】现价={cur:.2f if cur else '未知'} "
                        f"MA5={ma5:.2f if ma5 else '-'} MA10={ma10:.2f if ma10 else '-'} "
                        f"MA20={ma20:.2f if ma20 else '-'} MA60={ma60:.2f if ma60 else '-'} "
                        f"→ 阶段{stage}({desc}) → 建议: {direction}{src_note}")
                stage_summary = "\n".join(stage_summary_lines)
                if divergence_info:
                    div_lines = ["【盘中实时背离检测】"]
                    for d in divergence_info:
                        sig = ""
                        if d["dif_last"] > 0 and d["hist_last"] > 0: sig = "DIF正+柱正→多头"
                        elif d["dif_last"] < 0 and d["hist_last"] < 0: sig = "DIF负+柱负→空头"
                        elif d["dif_last"] > 0 and d["hist_last"] < 0: sig = "柱缩→警惕顶背离"
                        elif d["dif_last"] < 0 and d["hist_last"] > 0: sig = "柱增→警惕底背离"
                        div_lines.append(f"  · {d['name']}({d['period']}): 价={d['last_price']:.2f} DIF={d['dif_last']:.3f} DEA={d['dea_last']:.3f} {sig}")
                    "\n".join(div_lines)
                hist_var.get()
                # 判断数据源类型（实时拉取 vs 自研兜底）
                _src_tag = "实时行情" if index_data else "自研系统·盘面诊断+舆情"
                _mode_tag = ("盘中实时" if is_trading else "盘后分析") + f"（数据源: {_src_tag}）"
                # 拼装自研系统上下文
                _diy_ctx_parts = []
                if diy_diagnosis:
                    _diy_ctx_parts.append(f"【自研盘面诊断】\n{diy_diagnosis}")
                if diy_sentiment:
                    _diy_ctx_parts.append(f"【自研情绪快照】{diy_sentiment}")
                if diy_news:
                    _diy_ctx_parts.append(f"【近期舆情（6大来源）】\n{diy_news}")
                _diy_ctx = "\n\n".join(_diy_ctx_parts) if _diy_ctx_parts else "（自研系统暂无数据）"
                prompt = f"""当前 {now.strftime('%Y-%m-%d %H:%M')} [{_mode_tag}]
大盘S1-S4阶段:
{stage_summary}
三指数整体方向: {overall_dir}
{_diy_ctx}
请直接输出做T分析，不要废话。格式：
【一句话方向】: 🟢先卖后买/🔵先买后卖/🟡减仓/🟢增仓/⚪观望
【操作要点】: 仓位(≤30%)、买卖位置、止损位
【个股提示】: 适合做T的板块3-5个 + 不适合的2-3个
【风险】: 舆情里的黑天鹅信号
要求: 数据说话、结论明确、不要说"仅供参考"
"""
                system = "A股T+0做T策略师，极简、结论先行、方向明确。"
                try:
                    result = self.call_ai_model(prompt, system_prompt=system, max_tokens=2000)
                    # 顶部摘要
                    t_summary = f"{overall_dir}  |  三指数多数处于 {s_counts} → 建议方向已结合"
                    win.after(0, lambda: t_summary_var.set(t_summary))
                    win.after(0, lambda: report_txt.delete("1.0", tk.END))
                    win.after(0, lambda: report_txt.insert("1.0",
                        f"═══ 背离做T分析报告 ═══\n"
                        f"时间: {now.strftime('%Y-%m-%d %H:%M')}  模式: {'盘中实时' if is_trading else '盘后分析'}\n"
                        f"大盘整体方向: {overall_dir}\n\n"
                        f"{result or '(AI未返回内容)'}"
                    ))
                    win.after(0, lambda: status_var.set("✅ 分析完成！💾可保存到资讯表"))
                    win.after(0, _load_history)
                except Exception as e:
                    import traceback
                    err = f"❌ AI 调用失败: {e}\n\n{traceback.format_exc()}"
                    win.after(0, lambda: report_txt.delete("1.0", tk.END))
                    win.after(0, lambda: report_txt.insert("1.0", err[:3000]))
                    win.after(0, lambda: status_var.set(err[:60]))
                finally:
                    _busy[0] = False
                    try: win.after(0, lambda: analyze_btn.config(state=tk.NORMAL))
                    except Exception: pass
            threading.Thread(target=_work, daemon=True).start()
        analyze_btn.configure(command=_run_analysis)
        # 绑定按钮
        for w in btn_row.winfo_children():
            pass  # 按钮已在之前创建但没绑定
        # 重新绑定保存/刷新
        for w in btn_row.winfo_children():
            try:
                txt = w.cget("text")
                if "保存" in txt: w.configure(command=_save_to_news)
                elif "刷新" in txt: w.configure(command=_load_history)
            except Exception:
                pass
        # 首次加载历史
        _load_history()

    def _show_panpan_diagnosis(self):
        """📊 盘面诊断:综合多数据源判断「做T 还是 持股」--参考悟空四阶段 + 龙虾盘面分析逻辑"""
        import datetime as _dt
        import sqlite3 as _sqlite3
        import threading

        import akshare as _ak
        today = _dt.datetime.now().strftime("%m月%d日")
        win = self._safe_toplevel(self.root)
        win.title(f"📊 盘面诊断 - {today} 做T还是持股")
        win.geometry("920x780")
        win.transient(self.root)
        # ============ Canvas 仪表盘(零依赖、原生绘图) ============
        dashboard = tk.Canvas(win, width=900, height=190, bg="#FAFAFA", highlightthickness=1, highlightbackground="#DDD")
        dashboard.pack(fill=tk.X, padx=6, pady=(6, 2))
        def _draw_dashboard(stage, energy, sentiment, market, ma_pos, verdict, scores):
            """用 Canvas 原生绘图,四个可视化模块一目了然"""
            try:
                # ===== A 股统一颜色常量(红涨绿跌)=====
                _RED_UP = "#C62828"; _RED_UP_LIGHT = "#EF5350"     # 涨/好/积极 → 红
                _GREEN_DOWN = "#2E7D32"; _GREEN_DOWN_LIGHT = "#66BB6A"  # 跌/坏/消极 → 绿
                _ORANGE_T = "#FF9800"    # 做T(中性偏积极)
                _BLUE = "#2196F3"; _YELLOW = "#FFC107"; _GRAY = "#9E9E9E"
                c = dashboard
                c.delete("all")
                # 顶部标题
                c.create_text(20, 14, anchor=tk.W, text="📊 盘面诊断仪表盘", font=("Microsoft YaHei", 11, "bold"), fill="#37474F")
                # verdict 颜色:持股(积极)→ 红,做T(中性)→ 橙,锁利/减仓/恐慌 → 绿
                verdict_clr = _RED_UP if "持股" in verdict else (_ORANGE_T if "做T" in verdict else _GREEN_DOWN)
                c.create_text(880, 14, anchor=tk.E, text=verdict, font=("Microsoft YaHei", 13, "bold"),
                              fill=verdict_clr)
                # 竖分隔线
                c.create_line(260, 25, 260, 185, fill="#E0E0E0")
                c.create_line(520, 25, 520, 185, fill="#E0E0E0")
                c.create_line(700, 25, 700, 185, fill="#E0E0E0")
                # ── 1 S 阶段信号灯(圆圈 + 标签) ──
                stage_colors = {"S1": _RED_UP, "S2": _YELLOW, "S3": _ORANGE_T, "S4": _GREEN_DOWN}  # A股: S1红/S4绿
                stage_names = {"S1": "上升趋势", "S2": "震荡轮动", "S3": "分化防御", "S4": "恐慌退潮"}
                x_circle = 130; y_circle = 105; r = 42
                # 四个小指示灯在左侧垂直排列
                stages_list = ["S1", "S2", "S3", "S4"]
                for i, s in enumerate(stages_list):
                    cx = 35 + i * 55
                    cy = 60
                    color = stage_colors[s]
                    outline = stage_colors[stage] if s == stage else "#BDBDBD"
                    width = 4 if s == stage else 1
                    c.create_oval(cx - 16, cy - 16, cx + 16, cy + 16, fill=(color if s == stage else "white"),
                                  outline=outline, width=width)
                    c.create_text(cx, cy, text=s, font=("Microsoft YaHei", 9, "bold"),
                                  fill=("white" if s == stage else stage_colors[s]))
                    c.create_text(cx, cy + 34, text=stage_names[s], font=("Microsoft YaHei", 8), fill="#666")
                # 当前阶段大圆圈
                c.create_oval(x_circle - r, y_circle - r, x_circle + r, y_circle + r,
                              fill=stage_colors.get(stage, "#999"), outline="white", width=3)
                c.create_text(x_circle, y_circle - 6, text=stage, font=("Microsoft YaHei", 22, "bold"), fill="white")
                c.create_text(x_circle, y_circle + 20, text=stage_names.get(stage, ""), font=("Microsoft YaHei", 10), fill="white")
                c.create_text(130, 162, text=f"量能 {energy} | 情绪 {sentiment}", font=("Microsoft YaHei", 9), fill="#555")
                # ── 2 做T vs 持股 得分条 ──
                bx0, bx1 = 275, 505; y1_center = 55; y2_center = 95
                c.create_text(bx0, y1_center - 20, anchor=tk.W, text="🎯 决策得分对比", font=("Microsoft YaHei", 9, "bold"), fill="#37474F")
                max_s = max(scores.get("做T", 0), scores.get("持股", 0), 1)
                # 做T → 橙色(中性偏积极)
                s1 = scores.get("做T", 0)
                w1 = int((bx1 - bx0 - 80) * s1 / max_s)
                c.create_text(bx0, y1_center, anchor=tk.W, text="做T  ", font=("Microsoft YaHei", 10, "bold"), fill=_ORANGE_T)
                c.create_rectangle(bx0 + 48, y1_center - 10, bx0 + 48 + w1, y1_center + 10, fill="#FFB74D", outline="")
                c.create_text(bx0 + 48 + w1 + 6, y1_center, anchor=tk.W, text=str(s1), font=("Microsoft YaHei", 9), fill=_ORANGE_T)
                # 持股 → 红色(积极信号)
                s2 = scores.get("持股", 0)
                w2 = int((bx1 - bx0 - 80) * s2 / max_s)
                c.create_text(bx0, y2_center, anchor=tk.W, text="持股  ", font=("Microsoft YaHei", 10, "bold"), fill=_RED_UP)
                c.create_rectangle(bx0 + 48, y2_center - 10, bx0 + 48 + w2, y2_center + 10, fill=_RED_UP_LIGHT, outline="")
                c.create_text(bx0 + 48 + w2 + 6, y2_center, anchor=tk.W, text=str(s2), font=("Microsoft YaHei", 9), fill=_RED_UP)
                # 底部三维度小标签
                reasons_preview = []
                if "S" in f"{stage}": reasons_preview.append(f"S{stage[1]}")
                reasons_preview.append(energy)
                reasons_preview.append(ma_pos.get("sh", "").split("(")[0][:10])
                c.create_text(bx0, 128, anchor=tk.W, text="维度: " + " | ".join(reasons_preview[:3]), font=("Microsoft YaHei", 8), fill="#888")
                # 今日适配结论
                c.create_text((bx0 + bx1) // 2, 165, text=f"→ {verdict}",
                              font=("Microsoft YaHei", 12, "bold"), fill=verdict_clr)
                # ── 3 涨跌比分裂条 + 停板 ──
                cx0, cx1 = 535, 690
                c.create_text(cx0, 42, anchor=tk.W, text="📈 涨跌比", font=("Microsoft YaHei", 9, "bold"), fill="#37474F")
                up = market.get("up", 0); down = market.get("down", 0)
                total = up + down
                if total == 0: total = 1
                half_w = (cx1 - cx0 - 20) // 2
                # 上涨 → 红(A股惯例!)
                c.create_rectangle(cx0 + 10 + half_w - int(half_w * up / total), 55, cx0 + 10 + half_w, 75,
                                   fill=_RED_UP_LIGHT, outline="")
                c.create_text(cx0 + 10, 65, anchor=tk.W, text=f"涨 {up}", font=("Microsoft YaHei", 9, "bold"), fill=_RED_UP)
                # 下跌 → 绿(A股惯例!)
                c.create_rectangle(cx0 + 10 + half_w, 55, cx0 + 10 + half_w + int(half_w * down / total), 75,
                                   fill=_GREEN_DOWN_LIGHT, outline="")
                c.create_text(cx1 - 5, 65, anchor=tk.E, text=f"{down} 跌", font=("Microsoft YaHei", 9, "bold"), fill=_GREEN_DOWN)
                # 涨停 / 跌停 - 涨停红、跌停绿
                zt = market.get("zt", 0); dt = market.get("dt", 0)
                c.create_text(cx0, 98, anchor=tk.W, text=f"涨停 {zt}", font=("Microsoft YaHei", 9), fill=_RED_UP)
                c.create_text(cx1, 98, anchor=tk.E, text=f"跌停 {dt}", font=("Microsoft YaHei", 9), fill=_GREEN_DOWN)
                # 指数涨跌 - 涨红跌绿
                sh_pct = market.get("sh_pct", 0); cy_pct = market.get("cy_pct", 0); cyb_pct = market.get("cyb_pct", 0)
                c.create_text(cx0, 128, anchor=tk.W, text=f"沪指 {sh_pct:+.2f}%", font=("Microsoft YaHei", 8),
                              fill=(_RED_UP if sh_pct >= 0 else _GREEN_DOWN))
                c.create_text(cx0, 144, anchor=tk.W, text=f"深成 {cy_pct:+.2f}%", font=("Microsoft YaHei", 8),
                              fill=(_RED_UP if cy_pct >= 0 else _GREEN_DOWN))
                c.create_text(cx0, 160, anchor=tk.W, text=f"创业 {cyb_pct:+.2f}%", font=("Microsoft YaHei", 8),
                              fill=(_RED_UP if cyb_pct >= 0 else _GREEN_DOWN))
                # ── 4 量能仪表(水平条 + 情绪标签) ──
                dx0, dx1 = 710, 885
                c.create_text(dx0, 42, anchor=tk.W, text="💧 量能", font=("Microsoft YaHei", 9, "bold"), fill="#37474F")
                amount = market.get("amount_yi", 0)
                # 背景条
                c.create_rectangle(dx0, 55, dx1, 75, fill="#ECEFF1", outline="")
                # 填充:amount 0~20000亿映射到 width
                ratio = min(amount / 20000.0, 1.0)
                energy_color = {"放量": _RED_UP, "平量": _BLUE, "缩量": _YELLOW, "硬缩量": _GRAY}.get(energy, _GRAY)
                c.create_rectangle(dx0, 55, dx0 + int((dx1 - dx0) * ratio), 75, fill=energy_color, outline="")
                c.create_text((dx0 + dx1) // 2, 65, text=f"{amount:.0f}亿", font=("Microsoft YaHei", 9, "bold"), fill="white")
                # 阶段标签
                c.create_rectangle(dx0, 82, dx0 + 60, 102, fill=energy_color, outline="")
                c.create_text(dx0 + 30, 92, text=energy, font=("Microsoft YaHei", 9, "bold"), fill="white")
                c.create_text(dx0 + 70, 92, anchor=tk.W, text=f"情绪 {sentiment}", font=("Microsoft YaHei", 9),
                              fill=(_RED_UP if sentiment == "热" else (_GREEN_DOWN if sentiment == "冷" else _ORANGE_T)))
                # 沪指均线位置
                c.create_text(dx0, 122, anchor=tk.W, text=f"沪指均线: {ma_pos.get('sh', '-')[:18]}",
                              font=("Microsoft YaHei", 8), fill="#555")
                c.create_text(dx0, 138, anchor=tk.W, text=f"创业均线: {ma_pos.get('cyb', '-')[:18]}",
                              font=("Microsoft YaHei", 8), fill="#555")
                c.create_text(dx0, 165, anchor=tk.W, text="← 5日线    → 20日线", font=("Microsoft YaHei", 8), fill="#AAA")
            except Exception as e:
                print(f"_draw_dashboard 异常: {e}")
        ttk.Label(win, text="📊 正在拉取多数据源,请稍候...", font=("Microsoft YaHei", 10), foreground="#666").pack(pady=4)
        text = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Microsoft YaHei", 10), height=28)
        text.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        btn_bar = ttk.Frame(win); btn_bar.pack(fill=tk.X, padx=6, pady=4)
        def _write(msg, tag=None):
            text.insert(tk.END, msg, tag); text.see(tk.END)
        text.tag_config("title", font=("Microsoft YaHei", 14, "bold"), foreground="#1565C0")
        text.tag_config("h2", font=("Microsoft YaHei", 12, "bold"), foreground="#C62828")
        text.tag_config("h3", font=("Microsoft YaHei", 10, "bold"), foreground="#37474F")
        text.tag_config("good", foreground="#2E7D32")
        text.tag_config("bad", foreground="#C62828")
        text.tag_config("dim", foreground="#888")
        def load_yesterday_context():
            """从 news_info 表查最近一条 wukong/定时Skill 的昨日 S 阶段判定"""
            ctx = {"y_stage": "", "y_energy": "", "y_high_count": 0}
            try:
                conn = _sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("""
                    SELECT content, created_at FROM news_info
                    WHERE tab_name LIKE '%wukong%' OR tab_name LIKE '%定时Skill%' OR tab_name LIKE '%盘面诊断%'
                    ORDER BY created_at DESC LIMIT 5
                """)
                rows = cur.fetchall(); conn.close()
                for content, created_at in rows:
                    if not content: continue
                    # 提取阶段
                    m = re.search(r'阶段判定[::]\s*([S1234])', content)
                    if not m:
                        m = re.search(r'\bS[1234]\b', content)
                    if m:
                        ctx["y_stage"] = m.group(1)
                    em = re.search(r'量能[=::]\s*([^\s,,))]+)', content)
                    if em: ctx["y_energy"] = em.group(1)
                    if ctx["y_stage"]: break
            except Exception:
                pass
            return ctx
        def fetch_today_market():
            """拉今日实时行情 + 指数 - 三源互备:新浪 → 东财 → 日线(收盘后)"""
            result = {"up": 0, "down": 0, "zt": 0, "dt": 0, "amount_yi": 0.0,
                      "top_sectors": [], "bottom_sectors": [],
                      "sh_pct": 0.0, "cy_pct": 0.0, "cyb_pct": 0.0,
                      "spot_ok": False, "spot_source": "", "is_historical": False}
            spot_df = None
            spot_source = ""
            # 源 1:新浪 stock_zh_a_spot(大部分时候最稳)
            try:
                df = _ak.stock_zh_a_spot()
                if df is not None and len(df) > 1000:
                    spot_df = df; spot_source = "sina"
            except Exception: pass
            # 源 2:东财 spot_em(盘中常能用)
            if spot_df is None:
                try:
                    df = _ak.stock_zh_a_spot_em()
                    if df is not None and len(df) > 1000:
                        spot_df = df; spot_source = "em"
                except Exception: pass
            # 源 3:tushare daily_basic(盘中/盘后都能用)
            if spot_df is None:
                try:
                    import os as _os
                    tk = _os.environ.get("TUSHARE_TOKEN") or getattr(self, "_tushare_token", None)
                    if tk:
                        import tushare as _ts
                        _ts.set_token(tk)
                        pro = _ts.pro_api()
                        import datetime as _dt
                        td = _dt.datetime.now().strftime("%Y%m%d")
                        for _try_date in [td, (_dt.datetime.now() - _dt.timedelta(days=1)).strftime("%Y%m%d"),
                                          (_dt.datetime.now() - _dt.timedelta(days=2)).strftime("%Y%m%d")]:
                            daily = pro.daily(trade_date=_try_date)
                            if daily is not None and len(daily) > 1000:
                                    spot_df = daily; spot_source = f"tushare({_try_date})"
                                    result["is_historical"] = (_try_date != td)
                                    break
                except Exception: pass
            if spot_df is not None:
                pct_col = None
                for c in spot_df.columns:
                    if "涨跌" in c and "幅" in c: pct_col = c; break
                if pct_col is None:
                    # tushare daily: pct_chg
                    for c in spot_df.columns:
                        if "pct_chg" in c.lower(): pct_col = c; break
                amount_col = None
                for c in spot_df.columns:
                    if "成交额" in c or ("成交" in c and "额" in c): amount_col = c; break
                if pct_col:
                    s_pct = spot_df[pct_col].astype(float)
                    result["up"] = int((s_pct > 0).sum())
                    result["down"] = int((s_pct < 0).sum())
                    result["zt"] = int((s_pct >= 9.5).sum())
                    result["dt"] = int((s_pct <= -9.5).sum())
                    result["spot_ok"] = (result["up"] + result["down"]) > 0
                    result["spot_source"] = spot_source
                if amount_col:
                    try:
                        amt = float(spot_df[amount_col].sum())
                        result["amount_yi"] = amt / 1e8
                    except Exception: pass
            # 指数 - 用 sina 实时源(日线接口非盘中,收盘后才更新)
            try:
                spot_idx = _ak.stock_zh_index_spot_sina()
                if spot_idx is not None and len(spot_idx) > 0:
                    code_col_idx = next(c for c in spot_idx.columns if "代码" in c)
                    pct_col_idx = next(c for c in spot_idx.columns if "涨跌幅" in c)
                    for idx_sym, key in [("sh000001", "sh_pct"), ("sz399001", "cy_pct"), ("sz399006", "cyb_pct")]:
                        row = spot_idx[spot_idx[code_col_idx] == idx_sym]
                        if len(row) > 0:
                            result[key] = round(float(row[pct_col_idx].iloc[0]), 2)
                    result["source_index"] = "sina_realtime"
            except Exception:
                # 回退:日线接口(可能是昨日数据,标注)
                for idx_name, idx_sym, key in [("沪指", "sh000001", "sh_pct"), ("深成指", "sz399001", "cy_pct"), ("创业板", "sz399006", "cyb_pct")]:
                    try:
                        d = _ak.stock_zh_index_daily(symbol=idx_sym)
                        if d is not None and len(d) >= 2:
                            cls = d.iloc[-1]["close"]; pre = d.iloc[-2]["close"]
                            result[key] = round((cls - pre) / pre * 100, 2)
                    except Exception: pass
                result["source_index"] = "daily_fallback(可能非盘中实时)"
            return result
        def fetch_index_ma():
            """取沪指/创业板 5/10/20 日线判断位置(cur 用实时价,ma 用历史日线)"""
            ma_pos = {"sh": "", "cyb": ""}
            # 先拿实时价(sina)
            cur_price = {}
            try:
                spot_idx = _ak.stock_zh_index_spot_sina()
                if spot_idx is not None and len(spot_idx) > 0:
                    code_col_i = next(c for c in spot_idx.columns if "代码" in c)
                    price_col_i = next(c for c in spot_idx.columns if "最新价" in c)
                    for idx_sym, key in [("sh000001", "sh"), ("sz399006", "cyb")]:
                        row = spot_idx[spot_idx[code_col_i] == idx_sym]
                        if len(row) > 0:
                            cur_price[key] = float(row[price_col_i].iloc[0])
            except Exception: pass
            for idx_sym, key in [("sh000001", "sh"), ("sz399006", "cyb")]:
                try:
                    d = _ak.stock_zh_index_daily(symbol=idx_sym)
                    if d is None or len(d) < 20: continue
                    closes = d["close"].astype(float).values
                    cur = cur_price.get(key, closes[-1])   # 优先实时价
                    ma5 = closes[-5:].mean()
                    ma10 = closes[-10:].mean()
                    ma20 = closes[-20:].mean()
                    if cur > ma5 > ma10: pos = "多头排列(站上5/10/20)"
                    elif cur > ma10 and cur < ma5: pos = "跌破5日线(站10日线)"
                    elif cur < ma10 and cur > ma20: pos = "跌破10日线(站20日线)"
                    elif cur < ma20: pos = "空头排列(破20日线)"
                    else: pos = "均线纠缠"
                    ma_pos[key] = pos
                    ma_pos[f"{key}_cur"] = cur
                    ma_pos[f"{key}_ma5"] = ma5
                    ma_pos[f"{key}_ma10"] = ma10
                except Exception: pass
            return ma_pos
        def judge_s_stage(market, ma_pos):
            """悟空四阶段判定(对齐龙虾 7 维度标准)
            S1 放量启动/主升初期:量能显著放大 + 情绪热 + 指数方向向上(站上5/10日线任一)
            S2 震荡轮动:平量 + 情绪中性 + 均线纠缠
            S3 分化防御:缩量 + 情绪冷 + 跌破均线
            S4 恐慌退潮:硬缩量 + 情绪冷 + 空头排列
            """
            up = market.get("up", 0); down = market.get("down", 0)
            amount = market.get("amount_yi", 0)
            sh_pct = market.get("sh_pct", 0); cy_pct = market.get("cy_pct", 0); cyb_pct = market.get("cyb_pct", 0)
            zt = market.get("zt", 0); market.get("dt", 0)
            # 1 量能粗判(放量=今日量/近5日均>1.2 或 今日>1.5万亿)
            if amount >= 15000: energy = "放量"
            elif amount >= 10000: energy = "平量"
            elif amount >= 7000: energy = "缩量"
            else: energy = "硬缩量"
            # 2 情绪(涨跌比 + 停板)
            total = up + down
            if total == 0: sentiment = "数据不足"
            elif up > down * 1.5 and zt >= 30: sentiment = "热"      # 涨跌>1.5倍 + 涨停30+
            elif up > down * 1.2: sentiment = "偏多"                # 偏多但涨停不够
            elif down > up * 1.3: sentiment = "冷"
            else: sentiment = "中性"
            # 3 指数位置
            sh_pos = ma_pos.get("sh", "")
            ma_pos.get("cyb", "")
            # 方向向上:三指数同涨 或 沪指站上ma5
            upward = (sh_pct > 0 and cy_pct > 0 and cyb_pct > 0) or "站上5" in sh_pos or "多头" in sh_pos
            # 多头排列:cur > ma5 > ma10
            full_bull = "多头" in sh_pos
            # 空头排列 或 跌破10日线
            bearish = ("空头" in sh_pos) or ("跌破10" in sh_pos) or ("跌破20" in sh_pos)
            # 4 阶段判定(对齐龙虾 7 维度)
            # S1 放量启动 / 主升初期
            if energy == "放量" and sentiment in ("热", "偏多") and upward:
                stage = "S1"
            elif energy == "放量" and sentiment == "热" and (sh_pct > 0.5 and cyb_pct > 1.0):
                # 三指同涨 + 放量 + 热情绪,即使均线未完全多头也判 S1(放量突破型)
                stage = "S1"
            # S4 恐慌退潮
            elif energy == "硬缩量" and (sentiment == "冷" or bearish):
                stage = "S4"
            # S3 分化防御
            elif energy in ("缩量", "硬缩量") and (sentiment == "冷" or bearish):
                stage = "S3"
            # S2 震荡轮动(平量、均线纠缠、情绪中性)
            elif energy == "平量" or "纠缠" in sh_pos or sentiment == "中性":
                stage = "S2"
            # 兜底:放量但情绪不够热 → S2(放量滞涨)
            else:
                stage = "S2"
            # index_state 描述
            if full_bull: index_state = "多头排列"
            elif upward and not bearish: index_state = "方向向上"
            elif bearish: index_state = "空头/破位"
            else: index_state = "均线纠缠"
            return stage, energy, sentiment, index_state
        def judge_t_vs_hold(stage, energy, market, ma_pos):
            """做T vs 持股 三维度判定(对齐龙虾 7 维度)"""
            reasons = []; scores = {"做T": 0, "持股": 0}
            up = market.get("up", 0); down = market.get("down", 0)
            sh_pct = market.get("sh_pct", 0); cyb_pct = market.get("cyb_pct", 0)
            sh_pos = ma_pos.get("sh", "")
            # 维度1:S阶段(权重最大)
            if stage == "S1":
                scores["持股"] += 3; reasons.append("S1 放量启动→持股为主(方向向上,不轻易下车)")
            elif stage == "S2":
                scores["持股"] += 1; scores["做T"] += 1; reasons.append("S2 震荡轮动→灵活做T(不追高,低吸为主)")
            elif stage == "S3":
                scores["做T"] += 3; reasons.append("S3 分化防御→做T优先(冲高减磅,控仓)")
            elif stage == "S4":
                scores["做T"] += 3; reasons.append("S4 恐慌退潮→做T/观望(不抄底,等企稳信号)")
            # 维度2:量能
            if energy == "放量":
                scores["持股"] += 2; reasons.append("放量→增量资金进场,持股看趋势(S3/S4 例外)")
            elif energy in ("硬缩量", "缩量"):
                scores["做T"] += 2; reasons.append(f"{energy}→反弹持续性存疑,不宜锁仓")
            # 维度3:指数位置(方向)
            upward = (sh_pct > 0 and cyb_pct > 0) or "站上5" in sh_pos or "多头" in sh_pos
            bearish = ("空头" in sh_pos) or ("跌破10" in sh_pos) or ("跌破20" in sh_pos)
            if upward and not bearish:
                scores["持股"] += 2; reasons.append("指数方向向上→趋势向好,持股为上")
            elif bearish:
                scores["做T"] += 2; reasons.append(f"指数{sh_pos}→破位风险,高位减磅避险")
            # 维度4:涨跌比
            if up > down * 1.5:
                scores["持股"] += 1; reasons.append(f"上涨 {up} / 下跌 {down}(约 {up//max(down,1)}:1)→ 多方占优")
            elif down > up * 1.3:
                scores["做T"] += 1; reasons.append(f"下跌 {down} > 上涨 {up}({down/max(up,1):.1f}:1)→ 弱势")
            # 综合
            verdict = "持股 > 做T" if scores["持股"] > scores["做T"] else "做T > 锁利"
            return verdict, scores, reasons
        def fetch_holdings_advice(market, verdict, stage):
            """持仓股逐只做T/锁利/持有建议"""
            import akshare as _ak2
            advices = []
            holding_stocks, *_ = self._get_holding_group_data(1)
            # 同时拿 group4 (Main持仓)
            h4, *_ = self._get_holding_group_data(4)
            all_holdings = []
            for arr in [holding_stocks, h4]:
                for s in arr:
                    if s and s[0] and s[1] and s not in all_holdings:
                        all_holdings.append(s)
            if not all_holdings:
                return advices
            try:
                df = _ak2.stock_zh_a_spot_em()
                if df is None: return advices
                code_col = next(c for c in df.columns if "代码" in c)
                next(c for c in df.columns if "名称" in c)
                pct_col = next(c for c in df.columns if "涨跌" in c and "幅" in c)
                close_col = next(c for c in df.columns if "最新价" in c) if any("最新价" in c for c in df.columns) else None
                df.index = df[code_col].astype(str).str.zfill(6)
            except Exception:
                return advices
            for name, code in all_holdings[:15]:
                code6 = str(code).zfill(6)
                if code6 not in df.index:
                    advices.append((name, code, "-", "无行情数据", "跳过"))
                    continue
                row = df.loc[code6]
                pct = float(row[pct_col])
                float(row[close_col]) if close_col else 0.0
                if verdict.startswith("做T") and stage in ("S3", "S4"):
                    if pct >= 3:
                        advice = "✅ 高开冲高→先减(1/3~1/2),下午低位接回"
                    elif pct <= -3:
                        advice = "⚠️ 补跌风险→若破昨日均价则优先减仓锁利"
                    else:
                        advice = "横盘→观望,若有利润可先落袋"
                elif verdict.startswith("持股") or stage == "S1":
                    if pct <= -2:
                        advice = "小幅调整→S1趋势中,不破5日线继续持有"
                    else:
                        advice = "强势→持股待涨,均线多头不卖"
                else:
                    if pct > 0: advice = "盈利中→可考虑落袋一部分"
                    else: advice = "亏损中→看支撑位,跌破则减"
                advices.append((name, code, f"{pct:+.2f}%", advice, "-"))
            return advices
        def work():
            try:
                ctx = load_yesterday_context()
                market = fetch_today_market()
                ma_pos = fetch_index_ma()
                stage, energy, sentiment, index_state = judge_s_stage(market, ma_pos)
                verdict, scores, reasons = judge_t_vs_hold(stage, energy, market, ma_pos)
                # 昨日背景 - 从 news_info 找最近 S 阶段
                y_stage_str = ctx.get("y_stage") or "-"
                y_energy_str = ctx.get("y_energy") or "-"
                # 生成报告
                out = []
                out.append(f"\n📊 当前盘面诊断 - {today} 做T还是持股\n")
                out.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                # 1 昨日背景
                out.append("【昨日背景】\n")
                if y_stage_str in ("S1", "S2", "S3", "S4"):
                    stage_names = {"S1": "上升趋势", "S2": "震荡轮动", "S3": "分化防御", "S4": "恐慌退潮"}
                    out.append(f"· 昨日阶段判定:{y_stage_str}({stage_names.get(y_stage_str, '')})\n")
                    out.append(f"· 昨日量能:{y_energy_str}\n")
                    out.append(f"· 策略延续:今日为 {y_stage_str} 余震后的行情 → 关注「阶段是否切换」\n\n")
                else:
                    out.append("· 无昨日 S 阶段记录(可能今日首次诊断)\n\n")
                # 2 今日盘面
                out.append("【今日盘面】\n")
                m = market
                spot_src = m.get("spot_source") or "无数据"
                hist_tag = "(上一交易日)" if m.get("is_historical") else ""
                out.append(f"· 指数: 沪指 {m.get('sh_pct', 0):+.2f}% | 深成指 {m.get('cy_pct', 0):+.2f}% | 创业板 {m.get('cyb_pct', 0):+.2f}%\n")
                out.append(f"· 量能: 成交约 {m.get('amount_yi', 0):.0f} 亿 → 判定为「{energy}」\n")
                spot_ok = m.get("spot_ok", False)
                if spot_ok:
                    out.append(f"· 涨跌比: 上涨 {m.get('up', 0)} 家 / 下跌 {m.get('down', 0)} 家 {hist_tag} → 情绪「{sentiment}」 [数据源:{spot_src}]\n")
                else:
                    out.append(f"· 涨跌比: ⚠️ 未获取到(数据源:{spot_src},可能非交易时段) → 情绪判定改用指数\n")
                out.append(f"· 停板: 涨停 {m.get('zt', 0)} 家 / 跌停 {m.get('dt', 0)} 家\n")
                out.append(f"· 沪指位置: {ma_pos.get('sh', '-')}\n")
                out.append(f"· 创业板位置: {ma_pos.get('cyb', '-')}\n\n")
                # 3 今日 S 阶段 + 三维度
                out.append(f"【今日阶段判定】{stage}\n")
                stage_names = {"S1": "上升趋势", "S2": "震荡轮动", "S3": "分化防御", "S4": "恐慌退潮"}
                out.append(f"· 策略方向: {stage_names.get(stage, '')}\n")
                out.append(f"· 量能={energy} | 情绪={sentiment} | 指数={index_state}\n\n")
                # ============ 📜 历史三次4000点关口对比 + 当前定位 + 做T策略 ============
                out.append("📜 历史三次4000点关口对比 (做T方法论参考)\n")
                out.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                out.append("┌──────────────┬────────────┬────────────┬────────────┐\n")
                out.append("│              │ 2007股改牛 │ 2015杠杆牛 │ 2025-26科技牛│\n")
                out.append("├──────────────┼────────────┼────────────┼────────────┤\n")
                out.append("│ PE           │ 40倍       │ 20倍       │ 14.65倍    │\n")
                out.append("│ 突破后涨幅   │ +53%(5月)  │ +30%(2月)  │ 震荡上行中  │\n")
                out.append("│ 回调幅度     │ 13%-15%    │ 9%         │ 3%-5%      │\n")
                out.append("│ 做T区间      │ 5%-8%      │ 3%-5%      │ 2%-3%      │\n")
                out.append("└──────────────┴────────────┴────────────┴────────────┘\n\n")
                out.append("📍 当前定位 (2026年9月初)\n")
                out.append("  大势: 慢牛震荡,4000点关口反复整固,向下空间有限\n\n")
                out.append("  外部扰动:\n")
                out.append("  · 美伊冲突 → 油价冲90美元\n")
                out.append("  · 美债收益率4.797%(年内新高)\n")
                out.append("  · 美股科技普跌,费城半导体-2.14%\n\n")
                out.append("  内部韧性:\n")
                out.append("  · 8月PMI回升至49.8%\n")
                out.append("  · 中报净利同比+19.4%\n")
                out.append("  · 央行8月降准0.5pct\n")
                out.append("  · 北向资金连续5个月净流入\n\n")
                out.append("🎯 关键点位\n")
                out.append("  支撑: 3960 → 3930 → 3900\n")
                out.append("  压力: 3995-4000 → 4010-4030\n\n")
                out.append("💡 4000点关口做T策略 (index-t Skill)\n")
                out.append("  · 3960-3970企稳 → 买T(与个股共振时)\n")
                out.append("  · 3995-4010受阻 → 卖T\n")
                out.append("  · 跌破3960 → 减仓做T,等3930\n")
                out.append("  · 板块轮动: 科技看承接、农业消费回调买、油气不追高\n\n")
                out.append("  ⚠️ 本轮是估值最低、节奏最缓的4000点突破\n")
                out.append("  → 适合精细化做T、重个股轻指数\n")
                out.append("  → 历史不会简单重演,但韵律总是相似 ✨\n\n")
                out.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n")
                out.append(f"🎯 结论:{verdict}\n\n")
                out.append("【三维度判断】\n")
                for i, r in enumerate(reasons, 1):
                    out.append(f"  {i}. {r}\n")
                out.append(f"\n· 得分:做T={scores['做T']} vs 持股={scores['持股']}\n\n")
                # 做T/持股对比
                out.append("【做T vs 锁利 操作节奏对比】\n")
                out.append("┌─────────────────┬────────────────────────┬────────────────────────┐\n")
                out.append("│                  │        做T              │        锁利             │\n")
                out.append("├─────────────────┼────────────────────────┼────────────────────────┤\n")
                out.append("│ 适用场景         │ 高位筹码多、接近压力位   │ 利润垫厚、成本极低       │\n")
                out.append("│ 主要风险         │ 做反了两边挨打           │ 利润随回落被侵蚀         │\n")
                out.append(f"│ 今日适配性       │ {'✅ 建议做T' if verdict.startswith('做T') else '❌ 非优先'}      │ {'✅ 建议锁利' if verdict.startswith('持股') else '❌ 非优先'}         │\n")
                out.append("└─────────────────┴────────────────────────┴────────────────────────┘\n\n")
                if verdict.startswith("做T"):
                    out.append("【做T操作节奏】\n")
                    out.append("  上午冲高卖:开盘高开/早盘冲高时先减一部分(1/3~1/2)\n")
                    out.append("  下午低位接:下午跌回均线附近、量能萎缩不破位→接回\n")
                    out.append("  底线:当天T出去的筹码,收盘前必须接回来\n\n")
                else:
                    out.append("【持股操作节奏】\n")
                    out.append("  持有为主:趋势向上、均线多头排列,不轻易下车\n")
                    out.append("  止损原则:若跌破 10 日线 + 放量 → 减仓避险\n")
                    out.append("  加码原则:回踩 5 日线不破 + 缩量 → 可加仓\n\n")
                # 4 持仓股逐一建议
                out.append("【持仓股逐一建议】\n")
                advices = fetch_holdings_advice(market, verdict, stage)
                if advices:
                    for name, code, pct, advice, _ in advices:
                        out.append(f"  · {name}({code})  {pct}%\n    → {advice}\n")
                else:
                    out.append("  (无持仓数据,请先在持仓组填入股票)\n")
                # 5 一句话总结
                out.append("\n📌 一句话总结\n")
                if verdict.startswith("做T"):
                    out.append(f"  今天做T,锁利优先,不贪不恋。市场处于 {stage} 余震后的弱修复,\n  高开不追,冲高减磅,下午低位接回,收盘前清空隔夜短线筹码。\n")
                else:
                    out.append(f"  今天持股为主,趋势延续。市场处于 {stage} 上升/震荡阶段,\n  均线多头排列,不轻易下车,回踩是机会不是风险。\n")
                out.append("\n⚠️ 声明:以上为客观盘面分析,不构成投资建议。\n")
                report = "".join(out)
                win.after(0, lambda: (text.delete("1.0", tk.END), _write(report),
                    _draw_dashboard(stage, energy, sentiment, market, ma_pos, verdict, scores)))
                # 自动入库 news_info
                try:
                    now = _dt.datetime.now()
                    tab_name = f"[盘面诊断]{now.strftime('%m%d%H%M')}_{stage}"
                    save_news_info_to_db(tab_name, report)
                    win.after(0, lambda: _write("\n✅ 已自动入库 news_info(可在资讯查询中查看)\n", "dim"))
                except Exception as e:
                    win.after(0, lambda e=e: _write(f"\n⚠️ 入库失败: {e}\n", "bad"))
            except Exception as e:
                import traceback as _tb
                win.after(0, lambda e=e: (text.delete("1.0", tk.END),
                    _write(f"❌ 诊断失败: {e}\n\n{_tb.format_exc()}", "bad")))
        threading.Thread(target=work, daemon=True).start()
        # 工具栏按钮(复用保存模式)
        def _save_txt():
            import tkinter.filedialog as fd
            p = fd.asksaveasfilename(defaultextension=".txt", filetypes=[("TXT", "*.txt")], title="保存为TXT")
            if p:
                with open(p, "w", encoding="utf-8") as f: f.write(text.get("1.0", tk.END))
                messagebox.showinfo("已保存", p, parent=win)
        def _save_img():
            try:
                import tkinter.filedialog as fd

                from PIL import Image, ImageDraw, ImageFont
                w, h = 900, 1200
                img = Image.new("RGB", (w, h), "white"); d = ImageDraw.Draw(img)
                text_content = text.get("1.0", tk.END)
                font = None
                for fp in ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/Songti.ttc"]:
                    if os.path.isfile(fp):
                        font = ImageFont.truetype(fp, 22); break
                if not font: font = ImageFont.load_default()
                y = 20
                for line in text_content.splitlines():
                    d.text((30, y), line, fill="black", font=font); y += 32
                p = fd.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
                if p: img.save(p); messagebox.showinfo("已保存", p, parent=win)
            except Exception as e: messagebox.showerror("错误", str(e), parent=win)
        ttk.Button(btn_bar, text="💾 保存TXT", command=_save_txt).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_bar, text="🖼️ 生成图片", command=_save_img).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_bar, text="复制全部", command=lambda: win.clipboard_clear() or win.clipboard_append(text.get("1.0", tk.END))).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_bar, text="关闭", command=win.destroy).pack(side=tk.RIGHT, padx=4)

    def _run_scheduled_task(self, task, trigger_hm=""):
        """后台线程执行定时任务并入库 news_info"""
        import datetime as _dt
        import subprocess
        import threading
        def _work():
            try:
                skill_name = task.get("skill_name", "")
                params = task.get("params") or []
                # 找 skill 目录
                skill_dir = os.path.expanduser(f"~/.qclaw/skills/{skill_name}")
                scripts_dir = os.path.join(skill_dir, "scripts")
                if not os.path.isdir(scripts_dir):
                    self._log_skill_scheduler(f"  ⚠️ {skill_name} scripts 目录不存在")
                    return
                # 找第一个带 __main__ 的 .py
                script_path = None
                for fn in sorted(os.listdir(scripts_dir)):
                    if fn.endswith(".py"):
                        p = os.path.join(scripts_dir, fn)
                        try:
                            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                                    if "__main__" in f.read():
                                        script_path = p
                                        break
                        except Exception:
                            continue
                if not script_path:
                    # 退化:第一个 .py
                    pys = [os.path.join(scripts_dir, fn) for fn in sorted(os.listdir(scripts_dir)) if fn.endswith(".py")]
                    script_path = pys[0] if pys else None
                if not script_path:
                    self._log_skill_scheduler(f"  ⚠️ {skill_name} 无可用脚本")
                    return
                # python 路径
                py_candidates = [sys.executable,
                                 "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",
                                 "/usr/bin/python3", "/usr/local/bin/python3"]
                py_bin = py_candidates[0]
                for p in py_candidates:
                    if os.path.isfile(p):
                        py_bin = p
                        break
                cmd = [py_bin, script_path] + params
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                                      cwd=skill_dir,
                                      env={**dict(os.environ),
                                           'PYTHONIOENCODING': 'utf-8',
                                           'PYTHONPATH': skill_dir})
                # 入库
                if proc.stdout:
                    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    tab_name = f"[定时Skill]{skill_name}_{_dt.datetime.now().strftime('%m%d%H%M')}{trigger_hm}"
                    content = (f"触发时间: {ts}(预定 {trigger_hm})\n"
                               f"脚本: {os.path.basename(script_path)}\n"
                               f"参数: {' '.join(params) or '(无)'}\n"
                               f"退出码: {proc.returncode}\n\n"
                               f"{proc.stdout.strip()}")
                    if proc.stderr:
                        content += f"\n\n[stderr]\n{proc.stderr.strip()}"
                    try:
                        # 带重试的入库(防 SQLite 'database is locked')
                        for attempt in range(3):
                            try:
                                    save_news_info_to_db(tab_name, content)
                                    break
                            except Exception:
                                    if attempt < 2:
                                        import time as _time
                                        _time.sleep(1 + attempt)  # 等 1s, 2s
                                    else:
                                        raise
                        self._log_skill_scheduler(f"  ✅ {skill_name} 已入库 news_info")
                    except Exception as e2:
                        self._log_skill_scheduler(f"  ⚠️ {skill_name} 入库失败(重试3次): {e2}")
                else:
                    self._log_skill_scheduler(f"  ⚠️ {skill_name} 无 stdout 输出(退出码 {proc.returncode})")
            except subprocess.TimeoutExpired:
                self._log_skill_scheduler(f"  ⚠️ {task.get('skill_name')} 超时")
            except Exception as e:
                self._log_skill_scheduler(f"  ❌ {task.get('skill_name')} 执行异常: {e}")
        threading.Thread(target=_work, daemon=True).start()

    def _scan_qclaw_skills(self):
        """扫描 ~/.qclaw/skills/ 下所有已建好的 skill,提取元信息
        返回: [{"name":str, "dir":str, "description":str, "trigger":str, "scripts":[{path, args}],
                "has_scripts":bool, "category":str, "exec_type":str("可执行"/"文档型"),
                "installed_at":str, "version":int, "source":str("local"/"remote"),
                "custom_category":str(段永平7类), "trigger_phrases":[str]}]
        """
        import glob
        import json as _json
        import os
        import re
        # ====== 段永平精选 28 skill → 7 类 + 触发词 ======
        _CATEGORY_28 = {
            "大盘/情绪": ["sentiment-cycle", "quant-trap-check", "overbought-oversold", "market-sentiment-guard", "stock-market-emotion"],
            "个股/板块技术": ["breakout-detector", "stock-tech-signals", "blood-chips-scanner", "hot-sector-intensity", "main-wave-scanner", "low-break20", "main-line-tracker"],
            "资金/龙虎榜": ["dragon-tiger-analysis", "capital-concentration"],
            "每日流程": ["ashare-morning-scan", "stock-premarket-scan", "daily-evening-report", "taojiu-emotion"],
            "价值/基本面": ["buffett-style-ashare", "gestalt-investing", "china-stock-quant", "quant-strategy", "stock-quant-backtest"],
            "外围/宏观": ["macro-economy-brief", "hithink-mcp", "tongdaxin-mcp"],
            "其他": ["stock-smart-picker", "intraday-rhythm"],
        }
        _TRIGGER_PHRASES = {
            "sentiment-cycle": ["扫描今天的情绪周期", "现在情绪到哪个阶段了", "大盘情绪分析"],
            "quant-trap-check": ["检查有没有量化陷阱", "量化陷阱排查", "今天容易踩什么坑"],
            "overbought-oversold": ["超买超卖检测", "哪些票超买了", "超跌反弹机会"],
            "market-sentiment-guard": ["情绪守护", "情绪预警", "大盘情绪风控"],
            "stock-market-emotion": ["大盘情绪指数", "现在市场情绪怎么样", "涨跌家数"],
            "breakout-detector": ["检测一下XXX有没有起爆信号", "突破信号", "起爆检测", "哪些票刚突破"],
            "stock-tech-signals": ["技术信号扫描", "股票技术分析", "K线信号"],
            "blood-chips-scanner": ["筹码扫描", "血筹", "筹码集中度", "主力筹码"],
            "hot-sector-intensity": ["热点板块强度", "哪个板块最热", "板块热度"],
            "main-wave-scanner": ["主升浪扫描", "主升浪机会", "抓主升浪"],
            "low-break20": ["跌破20日线机会", "20日线破位反弹", "low break 20"],
            "main-line-tracker": ["主线追踪", "现在主线是什么", "热点主线"],
            "dragon-tiger-analysis": ["分析一下龙虎榜", "龙虎榜解读", "游资动向"],
            "capital-concentration": ["资金集中度", "主力资金分布", "筹码集中"],
            "ashare-morning-scan": ["今天开盘有哪些机会", "早盘扫描", "开盘机会"],
            "stock-premarket-scan": ["盘前扫描", "盘前准备", "盘前分析"],
            "daily-evening-report": ["今日盘后总结", "收盘报告", "复盘报告"],
            "taojiu-emotion": ["淘股吧情绪", "股吧情绪", "韭菜情绪"],
            "buffett-style-ashare": ["巴菲特风格选股", "价值投资", "巴菲特A股"],
            "gestalt-investing": ["格式塔投资", "趋势形态", "结构投资"],
            "china-stock-quant": ["A股量化选股", "量化筛选", "因子选股"],
            "quant-strategy": ["量化策略", "策略分析", "因子策略"],
            "stock-quant-backtest": ["量化回测", "策略回测", "回测分析"],
            "macro-economy-brief": ["帮我看看外围市场", "宏观经济简报", "外围行情"],
            "hithink-mcp": ["同花顺数据", "同花顺MCP", "问财调用"],
            "tongdaxin-mcp": ["通达信数据", "通达信MCP"],
            "stock-smart-picker": ["智能选股", "帮我挑股票", "选股"],
            "intraday-rhythm": ["日内节奏", "盘中节奏", "做T节奏"],
        }
        _NAME_TO_28_GROUP = {}
        for _g, _names in _CATEGORY_28.items():
            for _n in _names: _NAME_TO_28_GROUP[_n] = _g
        skills_dir = os.path.expanduser("~/.qclaw/skills")
        if not os.path.isdir(skills_dir):
            return []
        # 读取龙虾远程元数据(installed_at/version/sha256),用于排序和比对新增
        remote_meta = {}
        remote_meta_path = os.path.join(skills_dir, ".remote-skills-meta.json")
        try:
            if os.path.isfile(remote_meta_path):
                with open(remote_meta_path, "r", encoding="utf-8", errors="ignore") as f:
                    rm = _json.load(f) or {}
                remote_meta = rm.get("skills", {}) if isinstance(rm, dict) else {}
        except Exception:
            pass
        # 读取龙虾同步历史清单(lastSkillName/history),用于"最新skill"提示
        sync_manifest = {"lastSkillName": "", "history": []}
        sync_manifest_path = os.path.join(skills_dir, ".skill-sync-manifest.json")
        try:
            if os.path.isfile(sync_manifest_path):
                with open(sync_manifest_path, "r", encoding="utf-8", errors="ignore") as f:
                    sm = _json.load(f) or {}
                sync_manifest = sm if isinstance(sm, dict) else sync_manifest
        except Exception:
            pass
        results = []
        for skill_name in sorted(os.listdir(skills_dir)):
            skill_path = os.path.join(skills_dir, skill_name)
            if not os.path.isdir(skill_path) or skill_name.startswith("."):
                continue
            info = {"name": skill_name, "dir": skill_path, "description": "",
                    "trigger": "", "scripts": [], "has_scripts": False, "category": "其他",
                    "exec_type": "文档型", "installed_at": "", "version": 0, "source": "local",
                    "custom_category": _NAME_TO_28_GROUP.get(skill_name, ""),
                    "trigger_phrases": _TRIGGER_PHRASES.get(skill_name, [])}
            # 从远程元数据补 installed_at/version/source
            rm_entry = remote_meta.get(skill_name, {})
            if rm_entry:
                info["installed_at"] = str(rm_entry.get("installed_at", "") or "")
                try:
                    info["version"] = int(rm_entry.get("version", 0) or 0)
                except Exception:
                    info["version"] = 0
                info["source"] = "remote"
            # 读取 SKILL.md
            skill_md = os.path.join(skill_path, "SKILL.md")
            md_content = ""
            if os.path.isfile(skill_md):
                try:
                    with open(skill_md, "r", encoding="utf-8", errors="ignore") as f:
                        md_content = f.read()
                except Exception:
                    pass
            # 提取 YAML frontmatter
            if md_content.startswith("---"):
                fm_match = re.match(r"^---\n(.*?)\n---", md_content, re.DOTALL)
                if fm_match:
                    fm = fm_match.group(1)
                    desc_m = re.search(r"^description:\s*(.+?)(?=\n[a-z]|\n---|\Z)", fm, re.MULTILINE | re.DOTALL)
                    if desc_m:
                        info["description"] = desc_m.group(1).strip().strip('"').strip("'").rstrip("|").strip()
                    name_m = re.search(r"^name:\s*(.+)", fm, re.MULTILINE)
                    if name_m:
                        info["name"] = name_m.group(1).strip()
            else:
                # 无 frontmatter,取第一行标题
                first_line = md_content.split("\n")[0] if md_content else ""
                if first_line:
                    info["description"] = first_line.lstrip("# ").strip()
            # 提取触发词
            trigger_m = re.search(r"(?:触发词|触发|关键词)[::]\s*(.+?)(?:\n##|\n#|\Z)", md_content, re.DOTALL)
            if trigger_m:
                info["trigger"] = trigger_m.group(1).strip()[:200]
            # 提取核心能力/用途
            if not info["description"]:
                ability_m = re.search(r"(?:核心能力|用途|功能|简介|角色)[::]\s*(.+?)(?:\n##|\n#|\Z)", md_content, re.DOTALL)
                if ability_m:
                    info["description"] = ability_m.group(1).strip()[:300]
            # 扫描 scripts 目录
            scripts_dir = os.path.join(skill_path, "scripts")
            if os.path.isdir(scripts_dir):
                for py_file in sorted(glob.glob(os.path.join(scripts_dir, "*.py"))):
                    script_info = {"path": py_file, "name": os.path.basename(py_file), "args": [], "doc": "", "has_argparse": False, "has_cli": False}
                    try:
                        with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                            code = f.read()
                        # 提取模块文档字符串
                        doc_m = re.search(r'^""".*?"""|^\s*""".*?"""', code, re.DOTALL | re.MULTILINE)
                        if doc_m:
                            script_info["doc"] = doc_m.group(0).strip('"""').strip()[:200]
                        # 提取 argparse 参数
                        if "argparse" in code:
                            script_info["has_argparse"] = True
                            arg_matches = re.findall(r'add_argument\(\s*["\'](--[\w-]+)["\'].*?(?:help\s*=\s*["\'](.+?)["\'])?', code)
                            for arg_name, arg_help in arg_matches:
                                    script_info["args"].append({"name": arg_name, "help": arg_help or ""})
                            req_m = re.findall(r'add_argument\(\s*["\'](--[\w-]+)["\'].*?required\s*=\s*True', code)
                            for arg_name in req_m:
                                    for a in script_info["args"]:
                                        if a["name"] == arg_name:
                                            a["required"] = True
                        # 直接运行的 CLI(无 argparse 但有 if __name__ == '__main__')
                        if "__main__" in code or "if __name__ ==" in code:
                            script_info["has_cli"] = True
                    except Exception:
                        pass
                    info["scripts"].append(script_info)
            if info["scripts"]:
                info["has_scripts"] = True
                # 回退1:没有 SKILL.md 或描述为空,用脚本 docstring
                if not info["description"] and info["scripts"][0].get("doc"):
                    info["description"] = info["scripts"][0]["doc"][:200]
                # 判定 exec_type:任一脚本含 if __name__ == '__main__' → 可执行;否则为导入型(文档型)
                if any(sc.get("has_cli") for sc in info["scripts"]):
                    info["exec_type"] = "可执行"
                else:
                    info["exec_type"] = "导入型"
            else:
                info["exec_type"] = "文档型"
            # 回退2:还是没有描述,用目录名
            if not info["description"]:
                info["description"] = skill_name
            # 分类(更全的关键词)
            stock_keywords = ["stock", "股", "trade", "trading", "quant", "backtest", "breakout", "dragon", "tiger", "选股", "交易", "量化", "龙虎", "策略", "仓位", "择时", "买", "卖", "ma", "macd", "rsi", "boll", "kdj", "趋势", "阶段", "扫描", "alert", "crash", "guard", "market", "sentiment", "情绪", "盘", "涨停", "跌停", "资金", "hot", "main", "wave", "phase", "trend", "overbought", "oversold", "超跌", "超涨", "段基", "芒格", "凯利", "kelly", "sharpe", "夏普", "均值", "回归", "动量", "抱团", "龙头", "热点", "板块", "指数", "etf", "fund", "premarket", "morning", "intraday", "daily", "evening", "weekly", "wukong", "悟空", "s6060", "6060", "lobster", "龙虾", "gestalt", "gestalt", "sparrow", "麻雀", "capital", "集中度", "buffett", "低吸", "建仓", "动量", "position", "premarket", "盘前", "主力", "机构", "持仓", "组合", "分散"]
            if any(kw.lower() in skill_name.lower() for kw in stock_keywords):
                info["category"] = "股票量化"
            elif any(kw in skill_name.lower() for kw in ["email", "mail", "docx", "pdf", "xlsx", "notion", "tencent", "figma", "lark", "wechat", "wecom", "kdocs", "weiyun", "wendao", "qqmusic", "tarot", "book", "meituan", "image", "aippt", "bi-report", "cloud", "flyai", "baidu", "qcc", "contract", "esign", "meeting", "survey", "news", "musician", "ads", "map", "miniprogram", "crm", "pan", "storage", "upload", "backup"]):
                info["category"] = "工具集成"
            elif any(kw in skill_name.lower() for kw in ["ai", "engineer", "prompt", "persona", "expert", "consulting", "strategy", "agent", "skill", "creator", "rules", "env", "cron", "find", "generate", "srt", "quality", "merge"]):
                info["category"] = "AI/开发"
            elif any(kw in skill_name.lower() for kw in ["macro", "economy", "brief", "announcement", "radar", "kol", "price", "chain", "hotspot", "jiuyan", "taojiu", "wuchen", "yuandian", "zhang", "lexiang", "library", "related", "舆情", "资讯", "宏", "链", "预测", "研究", "报告", "announcement", "news"]):
                info["category"] = "资讯研究"
            results.append(info)
        # 保存龙虾同步清单信息供浏览器比对新增用
        self._qclaw_sync_manifest = sync_manifest
        return results

    def _detect_new_qclaw_skills(self, all_skills, last_known_count=None):
        """比对龙虾 qclaw 同步清单,检测是否有新增 skill。
        判定方式:
        1) 同步清单 .skill-sync-manifest.json 的 history 里,比 self._qclaw_last_seen_time 更新的条目
        2) 或本地 skills 总数比上次扫描多
        返回: [{"name":str, "action":str, "timestamp":str}] 新增的 skill 列表
        """
        new_skills = []
        try:
            sm = getattr(self, "_qclaw_sync_manifest", {}) or {}
            history = sm.get("history", [])
            last_seen = getattr(self, "_qclaw_last_seen_time", None)
            # 首次打开浏览器:基线 = 同步清单的最新时间,避免误报
            if last_seen is None:
                if history:
                    last_seen = max((h.get("timestamp", "") for h in history), default="")
                else:
                    last_seen = ""
            new_history = [h for h in history if h.get("timestamp", "") > last_seen and h.get("action") == "create"]
            for h in new_history:
                new_skills.append({"name": h.get("skillName", ""), "action": h.get("action", "create"),
                                   "timestamp": h.get("timestamp", "")})
        except Exception:
            pass
        # 同时用本地总数比对(manifest 未更新但目录有新增的兜底)
        try:
            if last_known_count is not None and len(all_skills) > last_known_count:
                known_names = set(getattr(self, "_qclaw_known_names", set()))
                for s in all_skills:
                    if s["name"] not in known_names:
                        if not any(ns["name"] == s["name"] for ns in new_skills):
                            new_skills.append({"name": s["name"], "action": "create",
                                               "timestamp": s.get("installed_at", "")})
        except Exception:
            pass
        return new_skills

    def _show_qclaw_skills_browser(self):
        """显示 QClaw Skill 浏览器对话框"""
        win = self._safe_toplevel(self.root)
        win.title("QClaw Skill 浏览器")
        win.geometry("1200x800")
        win.transient(self.root)
        # 保存最后一次 skill 运行结果,供手动点"📊 图形"按钮弹出
        # 用列表容器(引用传递,闭包里不需要 nonlocal 就能修改)
        _last_result = {"stdout": "", "skill_info": None}
        # 顶部:搜索 + 分类筛选 + 维度筛选 + 排序
        top_frame = ttk.Frame(win, padding=6)
        top_frame.pack(fill=tk.X)
        ttk.Label(top_frame, text="🔍 搜索:", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(top_frame, textvariable=search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=4)
        ttk.Label(top_frame, text="分类:", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(10, 2))
        category_var = tk.StringVar(value="全部")
        category_combo = ttk.Combobox(top_frame, textvariable=category_var, width=10, state="readonly")
        category_combo.pack(side=tk.LEFT, padx=4)
        ttk.Label(top_frame, text="类型:", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(10, 2))
        exec_type_var = tk.StringVar(value="全部")
        exec_type_combo = ttk.Combobox(top_frame, textvariable=exec_type_var, width=10, state="readonly", values=["全部", "可执行", "文档型", "导入型"])
        exec_type_combo.pack(side=tk.LEFT, padx=4)
        ttk.Label(top_frame, text="排序:", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(10, 2))
        sort_var = tk.StringVar(value="名称↑")
        sort_combo = ttk.Combobox(top_frame, textvariable=sort_var, width=14, state="readonly",
                                  values=["名称↑", "名称↓", "分类↑", "脚本数↓", "安装时间新→旧", "安装时间旧→新"])
        sort_combo.pack(side=tk.LEFT, padx=4)
        ttk.Label(top_frame, text="🎯段永平精选:", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(10, 2))
        bry28_var = tk.StringVar(value="全部")
        bry28_combo = ttk.Combobox(top_frame, textvariable=bry28_var, width=12, state="readonly",
                                   values=["全部", "大盘/情绪", "个股/板块技术", "资金/龙虎榜", "每日流程", "价值/基本面", "外围/宏观", "其他"])
        bry28_combo.pack(side=tk.LEFT, padx=4)
        # 右侧操作按钮
        new_btn = ttk.Button(top_frame, text="🆕龙虾新增", width=10)
        new_btn.pack(side=tk.RIGHT, padx=4)
        refresh_btn = ttk.Button(top_frame, text="🔄刷新", width=6)
        refresh_btn.pack(side=tk.RIGHT, padx=4)
        count_label = ttk.Label(top_frame, text="共0个Skill", font=("Microsoft YaHei", 9))
        count_label.pack(side=tk.RIGHT, padx=10)
        # 主区域:左列表 + 右详情
        paned = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        # 左:Skill 列表
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=2)
        list_scroll = ttk.Scrollbar(left_frame)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        columns = ("name", "category", "exec_type", "scripts", "installed")
        skill_list = ttk.Treeview(left_frame, columns=columns, show="headings", height=25, yscrollcommand=list_scroll.set)
        list_scroll.config(command=skill_list.yview)
        skill_list.heading("name", text="Skill名称")
        skill_list.heading("category", text="分类")
        skill_list.heading("exec_type", text="类型")
        skill_list.heading("scripts", text="脚本数")
        skill_list.heading("installed", text="安装时间")
        skill_list.column("name", width=180)
        skill_list.column("category", width=80)
        skill_list.column("exec_type", width=70)
        skill_list.column("scripts", width=50, anchor="center")
        skill_list.column("installed", width=130)
        skill_list.pack(fill=tk.BOTH, expand=True)
        # 右:详情
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)
        detail_text = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, font=("Microsoft YaHei", 10))
        detail_text.pack(fill=tk.BOTH, expand=True)
        self._configure_ai_staff_text_tags(detail_text)
        # 参数输入区
        param_frame = ttk.LabelFrame(right_frame, text="参数输入(格式: --参数名 值)", padding=6)
        param_frame.pack(fill=tk.X, pady=(4, 0))
        param_var = tk.StringVar()
        param_entry = ttk.Entry(param_frame, textvariable=param_var, width=60)
        param_entry.pack(fill=tk.X, pady=2)
        ttk.Label(param_frame, text="示例: --date 2026-08-26 --stock 600519", font=("Microsoft YaHei", 8), foreground="gray").pack()
        # 按钮区
        btn_frame = ttk.Frame(right_frame)
        btn_frame.pack(fill=tk.X, pady=4)
        run_btn = ttk.Button(btn_frame, text="▶ 运行脚本")
        run_btn.pack(side=tk.LEFT, padx=4)
        schedule_btn = ttk.Button(btn_frame, text="⏰ 定时执行(当前skill)")
        schedule_btn.pack(side=tk.LEFT, padx=4)
        graph_btn = ttk.Button(btn_frame, text="📊 图形", width=12)
        graph_btn.pack(side=tk.LEFT, padx=4)
        manager_btn = ttk.Button(btn_frame, text="📋 定时任务管理")
        manager_btn.pack(side=tk.LEFT, padx=4)
        save_db_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(btn_frame, text="运行结果入库 news_info", variable=save_db_var).pack(side=tk.LEFT, padx=8)
        output_label = ttk.Label(btn_frame, text="", font=("Microsoft YaHei", 9))
        output_label.pack(side=tk.LEFT, padx=10)
        # 输出区
        ttk.Label(right_frame, text="运行结果:", font=("Microsoft YaHei", 10, "bold")).pack(anchor=tk.W, pady=(6, 2))
        # 结果工具栏
        result_toolbar = ttk.Frame(right_frame)
        result_toolbar.pack(fill=tk.X, pady=(0, 2))
        ttk.Button(result_toolbar, text="📋复制", width=6, command=lambda: output_text.event_generate("<<Copy>>")).pack(side=tk.LEFT, padx=2)
        ttk.Button(result_toolbar, text="📑粘贴", width=6, command=lambda: output_text.event_generate("<<Paste>>")).pack(side=tk.LEFT, padx=2)
        ttk.Button(result_toolbar, text="✂️剪切", width=6, command=lambda: output_text.event_generate("<<Cut>>")).pack(side=tk.LEFT, padx=2)
        ttk.Button(result_toolbar, text="全选", width=5, command=lambda: output_text.tag_add(tk.SEL, "1.0", tk.END)).pack(side=tk.LEFT, padx=2)
        ttk.Button(result_toolbar, text="🗑️清空", width=6, command=lambda: output_text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=2)
        ttk.Label(result_toolbar, text="|", foreground="gray").pack(side=tk.LEFT, padx=4)
        ttk.Button(result_toolbar, text="💾TXT", width=6, command=lambda: self._save_skill_output(output_text, "txt", win)).pack(side=tk.LEFT, padx=2)
        ttk.Button(result_toolbar, text="📄Word", width=6, command=lambda: self._save_skill_output(output_text, "docx", win)).pack(side=tk.LEFT, padx=2)
        ttk.Button(result_toolbar, text="🖼️图片", width=6, command=lambda: self._save_skill_output(output_text, "image", win)).pack(side=tk.LEFT, padx=2)
        ttk.Label(result_toolbar, text="|", foreground="gray").pack(side=tk.LEFT, padx=4)
        ttk.Button(result_toolbar, text="🔲最大化", width=8, command=lambda: self._maximize_skill_output(output_text, win)).pack(side=tk.LEFT, padx=2)
        output_text = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, font=("Courier New", 9), height=10)
        output_text.pack(fill=tk.BOTH, expand=True)
        # 右键菜单
        def _show_ctx_menu(event):
            ctx_menu = tk.Menu(output_text, tearoff=0)
            ctx_menu.add_command(label="复制", command=lambda: output_text.event_generate("<<Copy>>"))
            ctx_menu.add_command(label="粘贴", command=lambda: output_text.event_generate("<<Paste>>"))
            ctx_menu.add_command(label="剪切", command=lambda: output_text.event_generate("<<Cut>>"))
            ctx_menu.add_separator()
            ctx_menu.add_command(label="全选", command=lambda: output_text.tag_add(tk.SEL, "1.0", tk.END))
            ctx_menu.add_command(label="清空", command=lambda: output_text.delete("1.0", tk.END))
            ctx_menu.add_separator()
            ctx_menu.add_command(label="保存为TXT", command=lambda: self._save_skill_output(output_text, "txt", win))
            ctx_menu.add_command(label="保存为Word", command=lambda: self._save_skill_output(output_text, "docx", win))
            ctx_menu.add_command(label="生成为图片", command=lambda: self._save_skill_output(output_text, "image", win))
            ctx_menu.add_separator()
            ctx_menu.add_command(label="最大化查看", command=lambda: self._maximize_skill_output(output_text, win))
            ctx_menu.tk_popup(event.x_root, event.y_root)
        output_text.bind("<Button-3>", _show_ctx_menu)
        # 双击最大化
        output_text.bind("<Double-Button-1>", lambda e: self._maximize_skill_output(output_text, win))
        # 快捷键
        output_text.bind("<Command-c>", lambda e: output_text.event_generate("<<Copy>>"))
        output_text.bind("<Command-v>", lambda e: output_text.event_generate("<<Paste>>"))
        output_text.bind("<Command-x>", lambda e: output_text.event_generate("<<Cut>>"))
        output_text.bind("<Command-a>", lambda e: output_text.tag_add(tk.SEL, "1.0", tk.END))
        output_text.bind("<Control-c>", lambda e: output_text.event_generate("<<Copy>>"))
        output_text.bind("<Control-v>", lambda e: output_text.event_generate("<<Paste>>"))
        output_text.bind("<Control-a>", lambda e: output_text.tag_add(tk.SEL, "1.0", tk.END))
        # 数据
        all_skills = self._scan_qclaw_skills()
        categories = ["全部"] + sorted({s["category"] for s in all_skills})
        category_combo['values'] = categories
        # 记录当前已知 skill 名单 + 总数 + 最近一次扫描时间,用于"龙虾新增"比对
        self._qclaw_known_names = {s["name"] for s in all_skills}
        self._qclaw_known_count = len(all_skills)
        try:
            sm = getattr(self, "_qclaw_sync_manifest", {}) or {}
            hist = sm.get("history", [])
            # 基线为本次扫描时同步清单的最新时间戳
            self._qclaw_last_seen_time = max((h.get("timestamp", "") for h in hist), default="")
        except Exception:
            self._qclaw_last_seen_time = ""
        current_skill = {"info": None}
        def _fmt_installed(s):
            ts = (s.get("installed_at") or "").strip()
            if not ts:
                return "-"
            # 2026-08-26T11:38:56.077Z → 08-26 11:38
            try:
                d = ts.replace("T", " ").split("+")[0].split(".")[0]
                return d[5:16] if len(d) >= 16 else d
            except Exception:
                return ts[:16]
        def update_list():
            kw = search_var.get().strip().lower()
            cat = category_var.get()
            et = exec_type_var.get()
            sk = sort_var.get()
            skill_list.delete(*skill_list.get_children())
            filtered = [s for s in all_skills
                        if (cat == "全部" or s["category"] == cat)
                        and (et == "全部" or s["exec_type"] == et)
                        and (bry28_var.get() == "全部" or s.get("custom_category") == bry28_var.get())
                        and (not kw or kw in s["name"].lower() or kw in s["description"].lower()
                             or any(kw in p.lower() for p in s.get("trigger_phrases", [])))]
            # 排序
            if sk == "名称↑":
                filtered.sort(key=lambda s: s["name"].lower())
            elif sk == "名称↓":
                filtered.sort(key=lambda s: s["name"].lower(), reverse=True)
            elif sk == "分类↑":
                filtered.sort(key=lambda s: (s.get("custom_category") or s["category"], s["name"].lower()))
            elif sk == "脚本数↓":
                filtered.sort(key=lambda s: len(s["scripts"]), reverse=True)
            elif sk == "安装时间新→旧":
                filtered.sort(key=lambda s: (s.get("installed_at") or ""), reverse=True)
            elif sk == "安装时间旧→新":
                filtered.sort(key=lambda s: (s.get("installed_at") or ""))
            for s in filtered:
                cat_display = s.get("custom_category") or s["category"]
                skill_list.insert("", tk.END, values=(s["name"], cat_display, s["exec_type"],
                                                     len(s["scripts"]), _fmt_installed(s)))
            count_label.config(text=f"共{len(filtered)}个Skill")
        def on_select(event):
            sel = skill_list.selection()
            if not sel:
                return
            vals = skill_list.item(sel[0], "values")
            skill_name = vals[0]
            info = next((s for s in all_skills if s["name"] == skill_name), None)
            if not info:
                return
            current_skill["info"] = info
            detail_text.delete("1.0", tk.END)
            detail_text.insert(tk.END, f"📋 Skill: {info['name']}\n", "title_tag")
            detail_text.insert(tk.END, f"📁 目录: {info['dir']}\n")
            display_cat = info.get("custom_category") or info["category"]
            bry_flag = "🎯" if info.get("custom_category") else ""
            detail_text.insert(tk.END, f"🏷️ 分类: {bry_flag}{display_cat} ")
            detail_text.insert(tk.END, f"⚙️ 类型: {info['exec_type']} ")
            detail_text.insert(tk.END, f"📦 版本: v{info.get('version',0)} ")
            detail_text.insert(tk.END, f"🌐 来源: {info.get('source','local')}\n")
            detail_text.insert(tk.END, f"🕒 安装: {info.get('installed_at') or '-'}\n")
            detail_text.insert(tk.END, f"📝 脚本数: {len(info['scripts'])}\n\n")
            # 💬 段永平触发词帮助(28 精选里的 skill 显示)
            if info.get("trigger_phrases"):
                detail_text.insert(tk.END, "💬 你可以说:\n", "section_tag")
                for phrase in info["trigger_phrases"]:
                    detail_text.insert(tk.END, f"  👉 \"{phrase}\"\n", "subtitle_tag")
                detail_text.insert(tk.END, "\n")
            detail_text.insert(tk.END, f"【说明】\n{info['description']}\n\n", "section_tag")
            if info["trigger"]:
                detail_text.insert(tk.END, f"【触发词(目录内定义)】\n{info['trigger']}\n\n", "section_tag")
            if info["scripts"]:
                detail_text.insert(tk.END, "【脚本列表】\n", "section_tag")
                for sc in info["scripts"]:
                    detail_text.insert(tk.END, f"\n🔹 {sc['name']}\n", "subtitle_tag")
                    if sc["doc"]:
                        detail_text.insert(tk.END, f"   说明: {sc['doc']}\n")
                    if sc["args"]:
                        detail_text.insert(tk.END, "   参数:\n")
                        for a in sc["args"]:
                            req = " (必填)" if a.get("required") else ""
                            detail_text.insert(tk.END, f"     {a['name']}{req}: {a['help']}\n")
                    elif sc.get("has_cli"):
                        detail_text.insert(tk.END, "   参数: 无(直接运行,无需参数)\n")
                    else:
                        detail_text.insert(tk.END, "   参数: 无(导入型模块,非CLI)\n")
            else:
                detail_text.insert(tk.END, "\n(此Skill为文档型,无Python脚本)\n", "warn_tag")
            detail_text.insert(tk.END, "\n【运行方式】\n", "section_tag")
            if info["scripts"]:
                first_script = info["scripts"][0]
                detail_text.insert(tk.END, f"  python3 {first_script['path']}")
                if first_script["args"]:
                    detail_text.insert(tk.END, " " + " ".join(a["name"] for a in first_script["args"]))
                detail_text.insert(tk.END, "\n")
            detail_text.insert(tk.END, "\n【SKILL.md原文】\n", "section_tag")
            skill_md_path = os.path.join(info["dir"], "SKILL.md")
            try:
                with open(skill_md_path, "r", encoding="utf-8", errors="ignore") as f:
                    detail_text.insert(tk.END, f.read()[:2000])
            except Exception:
                detail_text.insert(tk.END, "(读取失败)")
            self._apply_ai_staff_keyword_highlights(detail_text)
        def _resolve_py_bin():
            import sys as _sys
            py_candidates = [
                _sys.executable,
                "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",
                "/usr/bin/python3",
                "/usr/local/bin/python3",
            ]
            for p in py_candidates:
                try:
                    import os as _os
                    if _os.path.isfile(p):
                        return p
                except Exception:
                    continue
            return py_candidates[0]
        def _try_popup_skill_dashboard(stdout_text, skill_info, output_widget=None):
            """解析 skill 脚本 stdout 的 JSON,弹出中文 Canvas 仪表盘"""
            import json as _json
            import math as _math
            import re as _re
            # 安全获取可用的父窗口(win 可能已被用户关闭)
            try:
                _parent = win if win.winfo_exists() else self.root
            except Exception:
                _parent = self.root
            # ====== 英文 key → 中文标签 映射 ======
            _ZH_MAP = {
                # 大盘情绪
                "up_count": "上涨家数", "down_count": "下跌家数",
                "zt": "涨停数", "dt": "跌停数", "zt_count": "涨停数", "dt_count": "跌停数",
                "amount": "成交额(亿)", "amount_yi": "成交额(亿)", "volume": "成交量",
                "energy": "量能级别", "phase": "阶段", "score": "情绪得分",
                "sentiment_score": "情绪得分", "market_phase": "市场阶段",
                # 资金/集中度
                "hhi": "资金集中度HHI", "top10_share": "前10占比",
                "capital_concentration": "资金集中度", "turnover_rate": "换手率",
                "turnover": "换手率", "main_flow": "主力净流入",
                # 指数
                "sh_pct": "沪指涨跌幅", "cy_pct": "深成指涨跌幅", "cyb_pct": "创业板涨跌幅",
                "index_return": "指数收益率",
                # 板块
                "top_sectors": "领涨板块", "hot_sectors": "热门板块", "sector_count": "板块数",
                # 个股
                "breakout_count": "起爆信号数", "breakout": "起爆信号",
                "trap_count": "陷阱数", "volatility_trap_count": "波动陷阱",
                "oversold_count": "超跌数", "overbought_count": "超买数",
                "main_wave_count": "主升浪数", "low_break_count": "跌破20日线数",
                # 估值
                "pe": "市盈率PE", "pb": "市净率PB", "pe_ratio": "PE估值", "pb_ratio": "PB估值",
                # 技术指标
                "rsi": "RSI指标", "macd": "MACD值", "ma_score": "均线得分",
                "tech_score": "技术得分", "factor_score": "因子得分",
                # 策略
                "win_rate": "胜率", "total_return": "总收益率", "sharpe": "夏普比率",
                "max_drawdown": "最大回撤", "profit_factor": "盈亏比",
                # 选股
                "top_stocks_count": "精选股数", "picker_score": "选股评分",
                # 韭菜情绪
                "taojiu_score": "韭菜情绪指数", "emotion_index": "情绪指数",
            }
            # 闭包内缓存股票代码→名称,避免每次都查字典/文件/网络
            _code_cache = {}
            def _get_cached_name(code6):
                if code6 in _code_cache: return _code_cache[code6]
                try:
                    nm = get_stock_name_by_code(code6) or ""
                except Exception:
                    nm = ""
                _code_cache[code6] = nm
                return nm
            def _zh_label(path):
                label = path.split("/")[-1] if path else path
                # 尝试全路径查
                if path in _ZH_MAP: return _ZH_MAP[path]
                if label in _ZH_MAP: return _ZH_MAP[label]
                # 子串匹配
                for eng, zh in _ZH_MAP.items():
                    if eng in label or eng in path: return zh
                # === 股票代码智能识别(先快速短路,避免无意义的正则+查名)===
                _has_code = False
                # 快速检查:label 或 path 里含 6 位数字?
                if label and len(label) == 6 and label.isdigit() or path and _re.search(r'\d{6}', path):
                    _has_code = True
                if not _has_code:
                    return label.replace("_", " ")
                # ---- 有 6 位代码才跑以下逻辑 ----
                # 1) label 本身就是 6 位纯数字
                if label and len(label) == 6 and label.isdigit():
                    nm = _get_cached_name(label)
                    return f"{nm}({label})" if nm else label
                # 2) path 里含 6 位数字 → 替换为 "股票名(代码)"
                full_with_name = _re.sub(r'(?<!\d)(\d{6})(?!\d)',
                                         lambda mm: (lambda nm_c: f"{nm_c}({mm.group(1)})" if nm_c else mm.group(1))(_get_cached_name(mm.group(1))),
                                         path)
                if full_with_name != path:
                    return full_with_name.split("/")[-1]
                return label.replace("_", " ")
            # 找 JSON
            data = None
            for line in stdout_text.splitlines():
                line = line.strip()
                if line.startswith('{') and line.endswith('}'):
                    try: data = _json.loads(line); break
                    except: pass
            if data is None:
                m = _re.search(r'\{[\s\S]*\}', stdout_text)
                if m:
                    try: data = _json.loads(m.group())
                    except: pass
            if data is None:
                if output_widget is not None:
                    output_widget.insert(tk.END, "\ni️ stdout 中未找到有效 JSON,跳过可视化\n")
                    output_widget.see(tk.END)
                return
            def _collect_numbers(obj, prefix=""):
                items = []
                if obj is None: return items
                if isinstance(obj, dict):
                    # === 股票代码智能识别(用闭包内缓存,避免重复查名)===
                    stock_prefix = prefix
                    _code_val = obj.get("code") or obj.get("stock_code") or obj.get("symbol") or obj.get("stock")
                    if _code_val and isinstance(_code_val, str) and len(_code_val) == 6 and _code_val.isdigit():
                        _nm = _get_cached_name(_code_val)
                        if _nm:
                            stock_prefix = f"{prefix}/{_nm}({_code_val})" if prefix else f"{_nm}({_code_val})"
                    # 跳过纯股票代码字段本身(不是数值指标)
                    _skip_keys = {"code", "stock_code", "symbol", "stock", "name", "reason", "note", "tag", "tags", "source", "output_dir", "skill", "error", "success", "message", "summary", "analysis"}
                    for k, v in obj.items():
                        if k in _skip_keys: continue
                        items.extend(_collect_numbers(v, f"{stock_prefix}/{k}" if stock_prefix else k))
                elif isinstance(obj, (list, tuple)):
                    for i, v in enumerate(obj[:50]):
                        items.extend(_collect_numbers(v, f"{prefix}[{i}]"))
                elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
                    items.append((prefix, float(obj), _zh_label(prefix)))
                elif isinstance(obj, str) and obj and any(c.isdigit() for c in obj) and len(obj) < 120:
                    # 跳过 6 位数字字符串(股票代码不是数值指标)
                    if _re.match(r'^\d{6}$', obj.strip()):
                        pass  # 纯 6 位数字 = 股票代码,不是指标
                    else:
                        m2 = _re.search(r'-?\d+(?:\.\d+)?', obj)
                        if m2:
                            try: items.append((prefix, float(m2.group()), _zh_label(prefix)))
                            except: pass
                return items
            nums = _collect_numbers(data)
            if len(nums) < 2:
                # 没有足够的数值做图,但如果 output_widget 可用就提示
                if output_widget is not None:
                    if data and isinstance(data, dict):
                        if not data.get("success", True):
                            err = data.get("error", "未知错误")
                            output_widget.insert(tk.END, f"\n⚠️ Skill 执行失败:{err[:120]}\n")
                        else:
                            # success=true 但数值太少
                            output_widget.insert(tk.END, f"\ni️ 无可视化指标(数值字段仅 {len(nums)} 个)\n")
                    else:
                        output_widget.insert(tk.END, "\ni️ stdout 不是有效 JSON,跳过可视化\n")
                    output_widget.see(tk.END)
                return
            # ====== 自动推荐图表类型 ======
            def _recommend_chart(nums):
                vals = [v for _, v, _ in nums]
                n = len(nums)
                all_pos = all(v >= 0 for v in vals)
                in_0_100 = all(0 <= v <= 100 for v in vals)
                # 雷达图:3-8 维度,归一化后都正值
                if 3 <= n <= 10 and all_pos: return "radar"
                # 饼图:占比型(和接近某个整数、全正、5-8项)
                if 3 <= n <= 8 and all_pos:
                    total = sum(vals)
                    if total > 0:
                        ratios = [v/total for v in vals]
                        if all(0.01 <= r <= 0.8 for r in ratios):
                            return "pie"
                # 数值仪表盘:1-4 个 0-100 得分
                if 1 <= n <= 5 and in_0_100: return "gauge"
                # 默认柱状图
                return "bar"
            # ====== 弹窗 ======
            try:
                dlg = tk.Toplevel(_parent)
                dlg.transient(_parent)
            except Exception:
                dlg = tk.Toplevel(self.root)
                try: dlg.transient(self.root)
                except: pass
            dlg.title(f"📊 {skill_info.get('name','Skill')} 结果可视化")
            dlg.geometry("960x720")
            # macOS 上 -topmost + focus_force 会卡主循环几秒,去掉
            dlg.lift()
            _BG = "#1e1e2e"; _FG = "#cdd6f4"; _ACCENT = "#89b4fa"
            _COLORS = ["#f38ba8","#fab387","#f9e2af","#a6e3a1","#94e2d5","#89b4fa","#cba6f7","#f5c2e7","#74c7ec","#b4befe"]
            # 顶部切换栏(框架先建,按钮后加)
            top_bar = tk.Frame(dlg, bg=_BG)
            top_bar.pack(fill=tk.X, padx=8, pady=(8, 4))
            tk.Label(top_bar, text=f"📊 {skill_info.get('name','')}  |  分类: {skill_info.get('custom_category') or skill_info.get('category','')}  |  共 {len(nums)} 项指标",
                     bg=_BG, fg="#a6adc8", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
            chart_type_var = tk.StringVar(value=_recommend_chart(nums))
            types_fr = tk.Frame(top_bar, bg=_BG); types_fr.pack(side=tk.RIGHT)
            chart_options = [
                ("bar","📊柱"), ("hbar","📈横柱"), ("line","📉折线"), ("area","🌊面积"),
                ("radar","🕸️雷达"), ("pie","🥧饼图"), ("donut","🍩环形"),
                ("gauge","🎯仪表"), ("funnel","⚗️漏斗"), ("rose","🌹玫瑰"),
            ]
            canvas = tk.Canvas(dlg, bg=_BG, highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
            # ====== 先定义所有绘图函数(避免 command 引用未定义的函数)======
            def _redraw():
                canvas.delete("all")
                canvas.update_idletasks()
                chart_type = chart_type_var.get()
                m = {"bar":_draw_bar,"hbar":_draw_hbar,"line":_draw_line,"area":_draw_area,
                     "radar":_draw_radar,"pie":_draw_pie,"donut":_draw_donut,
                     "gauge":_draw_gauge,"funnel":_draw_funnel,"rose":_draw_rose}
                fn = m.get(chart_type, _draw_bar); fn()
            # ====== 图表 1: 柱状图(中英文标签)======
            def _draw_bar():
                W = max(int(canvas.winfo_width()), 920); H = max(int(canvas.winfo_height()), 620)
                vals = [(v, l) for _, v, l in nums[:30]]
                n = len(vals); max_v = max((abs(v) for v, _ in vals), default=1)
                bar_h = max(14, min(28, (H - 80) // max(n, 1) - 4))
                chart_top = 50; chart_left = 200; chart_w = W - 260
                canvas.create_text(W//2, 20, text="📊 数值柱状图(中文标签)",
                                   fill=_ACCENT, font=("Microsoft YaHei", 12, "bold"))
                for i, (val, label) in enumerate(vals):
                    y0 = chart_top + i * (bar_h + 4)
                    y1 = y0 + bar_h
                    color = _COLORS[i % len(_COLORS)]
                    display_label = f"{i+1}. {label}"[:32]
                    canvas.create_text(chart_left - 8, (y0+y1)//2, text=display_label,
                                       fill=_FG, anchor="e", font=("Microsoft YaHei", 10))
                    if max_v > 0:
                        bar_w = int(abs(val) / max_v * chart_w)
                    else: bar_w = 0
                    if val >= 0:
                        canvas.create_rectangle(chart_left, y0, chart_left + bar_w, y1, fill=color, outline="")
                        canvas.create_text(chart_left + bar_w + 6, (y0+y1)//2,
                                           text=f"{val:g}", fill=_FG, anchor="w", font=("Microsoft YaHei", 10, "bold"))
                    else:
                        canvas.create_rectangle(chart_left - bar_w, y0, chart_left, y1, fill="#f38ba8", outline="")
                        canvas.create_text(chart_left - bar_w - 6, (y0+y1)//2,
                                           text=f"{val:g}", fill="#f38ba8", anchor="e", font=("Microsoft YaHei", 10, "bold"))
                    canvas.create_line(chart_left - 2, y0 - 2, chart_left + chart_w + 50, y0 - 2,
                                       fill="#313244", dash=(2, 2))
            # ====== 图表 2: 雷达图 ======
            def _draw_radar():
                W = max(int(canvas.winfo_width()), 920); H = max(int(canvas.winfo_height()), 620)
                cx, cy = W//2, H//2 + 20
                r = min(W, H)//2 - 120
                vals = [(v, l) for _, v, l in nums[:10]]
                n = len(vals)
                if n < 3:
                    canvas.create_text(W//2, H//2, text="雷达图至少需要 3 个维度",
                                       fill="#f38ba8", font=("Microsoft YaHei", 14))
                    _draw_bar(); return
                # 归一化到 0-1(雷达图只接受正值)
                raw = [max(0, v) for v, _ in vals]
                maxv = max(raw) if max(raw) > 0 else 1
                norm_vals = [v / maxv for v in raw]
                canvas.create_text(W//2, 20, text="🕸️ 多维度雷达图",
                                   fill=_ACCENT, font=("Microsoft YaHei", 12, "bold"))
                # 网格(5 层同心圆)
                for g in range(1, 6):
                    rr = r * g / 5
                    canvas.create_oval(cx - rr, cy - rr, cx + rr, cy + rr,
                                       outline="#45475a", dash=(2, 2))
                # 轴线
                for i in range(n):
                    ang = -_math.pi/2 + 2 * _math.pi * i / n
                    x = cx + r * _math.cos(ang); y = cy + r * _math.sin(ang)
                    canvas.create_line(cx, cy, x, y, fill="#45475a")
                # 画数据多边形
                points = []
                for i, nv in enumerate(norm_vals):
                    ang = -_math.pi/2 + 2 * _math.pi * i / n
                    x = cx + r * nv * _math.cos(ang)
                    y = cy + r * nv * _math.sin(ang)
                    points.extend([x, y])
                if len(points) >= 6:
                    canvas.create_polygon(*points, fill="#89b4fa44", outline="#89b4fa", width=2, smooth=True)
                # 数据点
                for i, nv in enumerate(norm_vals):
                    ang = -_math.pi/2 + 2 * _math.pi * i / n
                    x = cx + r * nv * _math.cos(ang)
                    y = cy + r * nv * _math.sin(ang)
                    canvas.create_oval(x-4, y-4, x+4, y+4, fill="#f38ba8", outline="")
                # 中文标签(放圆外)
                for i, (_, label) in enumerate(vals):
                    ang = -_math.pi/2 + 2 * _math.pi * i / n
                    lx = cx + (r + 32) * _math.cos(ang)
                    ly = cy + (r + 32) * _math.sin(ang)
                    anchor = "center"
                    if _math.cos(ang) > 0.3: anchor = "w"
                    elif _math.cos(ang) < -0.3: anchor = "e"
                    canvas.create_text(lx, ly, text=label[:14], fill=_FG,
                                       anchor=anchor, font=("Microsoft YaHei", 10))
                # 图例(数值)
                for i, (v, l) in enumerate(vals):
                    ty = cy + r + 40 + i * 20
                    if ty < H - 20:
                        canvas.create_text(20, ty, text=f"● {l}: {v:g}", fill=_FG,
                                           anchor="w", font=("Microsoft YaHei", 10))
            # ====== 图表 3: 饼图 ======
            def _draw_pie():
                W = max(int(canvas.winfo_width()), 920); H = max(int(canvas.winfo_height()), 620)
                cx, cy = 300, H//2 + 10
                r = min(260, H//2 - 80)
                vals = [(v, l) for _, v, l in nums[:10]]
                # 只取正值最大的 8 项
                vals = sorted([(max(0, v), l) for v, l in vals if max(0, v) > 0], key=lambda x: -x[0])[:8]
                if len(vals) < 2:
                    canvas.create_text(W//2, H//2, text="饼图至少需要 2 个正值指标",
                                       fill="#f38ba8", font=("Microsoft YaHei", 14))
                    _draw_bar(); return
                total = sum(v for v, _ in vals) or 1
                canvas.create_text(cx, 30, text="🥧 占比饼图",
                                   fill=_ACCENT, font=("Microsoft YaHei", 12, "bold"))
                # 画扇形
                start = 0
                for i, (v, label) in enumerate(vals):
                    span = v / total * 360
                    color = _COLORS[i % len(_COLORS)]
                    canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                                       start=start, extent=span, fill=color, outline=_BG, width=2)
                    # 百分比
                    mid = start + span / 2
                    rad = _math.radians(mid)
                    tx = cx + r * 0.6 * _math.cos(rad)
                    ty = cy + r * 0.6 * _math.sin(rad)
                    if span > 15:
                        canvas.create_text(tx, ty, text=f"{v/total*100:.1f}%",
                                           fill="white", font=("Microsoft YaHei", 9, "bold"))
                    start += span
                # 图例(右边)
                lx = cx + r + 40; ly = cy - r
                canvas.create_text(lx, ly - 10, text="📋 图例(点击切换)",
                                   fill=_FG, anchor="w", font=("Microsoft YaHei", 10, "bold"))
                for i, (v, label) in enumerate(vals):
                    ty2 = ly + i * 24
                    color = _COLORS[i % len(_COLORS)]
                    canvas.create_rectangle(lx, ty2, lx + 14, ty2 + 14, fill=color, outline="")
                    canvas.create_text(lx + 20, ty2 + 7,
                                       text=f"{label[:24]}  {v:g}  ({v/total*100:.1f}%)",
                                       fill=_FG, anchor="w", font=("Microsoft YaHei", 10))
            # ====== 图表 4: 数值仪表盘(0-100 分数型指标)======
            def _draw_gauge():
                W = max(int(canvas.winfo_width()), 920); max(int(canvas.winfo_height()), 620)
                # 把所有指标归一化到 0-100 显示
                raw = [(v, l) for _, v, l in nums[:8]]
                all_v = [v for v, _ in raw]
                # 计算合理的最大值(避免极端值压扁)
                sorted_v = sorted(all_v)
                p90 = sorted_v[int(len(sorted_v) * 0.9)] if sorted_v else 100
                display_max = max(abs(p90) * 1.3, 1)
                len(raw)
                gauges_per_row = 3
                for gi, (val, label) in enumerate(raw):
                    row = gi // gauges_per_row; col = gi % gauges_per_row
                    gcx = 160 + col * 260
                    gcy = 180 + row * 260
                    gr = 100
                    # 归一化到 0-1(仪表盘半圆 0-180 度)
                    norm = max(0, min(1, abs(val) / display_max))
                    if val < 0: norm = -norm
                    span_deg = 180 * abs(norm)
                    # 背景弧(半圆 180°)
                    canvas.create_arc(gcx - gr, gcy - gr, gcx + gr, gcy + gr,
                                       start=180, extent=180, style="arc",
                                       outline="#45475a", width=14)
                    # 彩色弧(根据值正负/大小)
                    if norm >= 0:
                        c = "#a6e3a1" if norm > 0.5 else "#f9e2af" if norm > 0.25 else "#fab387"
                    else:
                        c = "#f38ba8"
                    canvas.create_arc(gcx - gr, gcy - gr, gcx + gr, gcy + gr,
                                       start=180, extent=span_deg, style="arc",
                                       outline=c, width=14)
                    # 刻度值
                    canvas.create_text(gcx, gcy + 20, text=f"{val:g}",
                                       fill=_ACCENT, font=("Microsoft YaHei", 18, "bold"))
                    # 标签
                    canvas.create_text(gcx, gcy + 55, text=label[:20],
                                       fill=_FG, font=("Microsoft YaHei", 10))
                canvas.create_text(W//2, 25, text="🎯 数值仪表盘(多指标并列)",
                                   fill=_ACCENT, font=("Microsoft YaHei", 12, "bold"))
            # ====== 图表 5: 横向柱状图 ======
            def _draw_hbar():
                W = max(int(canvas.winfo_width()), 920); H = max(int(canvas.winfo_height()), 620)
                vals = [(v, l) for _, v, l in nums[:30]]
                n = len(vals); max_v = max((abs(v) for v, _ in vals), default=1)
                bar_h = max(14, min(26, (H - 80) // max(n, 1) - 4))
                chart_top = 50; chart_left = 180; chart_w = W - 240
                canvas.create_text(W//2, 20, text="📈 横向柱状图(对比排序)",
                                   fill=_ACCENT, font=("Microsoft YaHei", 12, "bold"))
                for i, (val, label) in enumerate(vals):
                    y0 = chart_top + i * (bar_h + 4)
                    y1 = y0 + bar_h
                    color = _COLORS[i % len(_COLORS)]
                    display_label = f"{i+1}. {label}"[:32]
                    canvas.create_text(chart_left - 8, (y0+y1)//2, text=display_label,
                                       fill=_FG, anchor="e", font=("Microsoft YaHei", 10))
                    if max_v > 0: bar_w = int(abs(val) / max_v * chart_w)
                    else: bar_w = 0
                    cx = chart_left + bar_w
                    if val >= 0:
                        canvas.create_rectangle(chart_left, y0, cx, y1, fill=color, outline="")
                        canvas.create_text(cx + 6, (y0+y1)//2, text=f"{val:g}",
                                           fill=_FG, anchor="w", font=("Microsoft YaHei", 10, "bold"))
                    else:
                        canvas.create_rectangle(cx - bar_w, y0, chart_left, y1, fill="#f38ba8", outline="")
                        canvas.create_text(cx - bar_w - 6, (y0+y1)//2, text=f"{val:g}",
                                           fill="#f38ba8", anchor="e", font=("Microsoft YaHei", 10, "bold"))
            # ====== 图表 6: 折线图(自动生成 x 轴序号)======
            def _draw_line():
                W = max(int(canvas.winfo_width()), 920); H = max(int(canvas.winfo_height()), 620)
                vals = [(v, l) for _, v, l in nums[:30]]
                n = len(vals)
                if n < 2:
                    canvas.create_text(W//2, H//2, text="折线图至少需要 2 个点",
                                       fill="#f38ba8", font=("Microsoft YaHei", 14)); _draw_bar(); return
                top=70; bottom=H-50; left=80; right=W-40
                max_v = max(v for v,_ in vals); min_v = min(v for v,_ in vals)
                rng = max(max_v - min_v, abs(max_v) * 0.05, 1)
                x_step = (right - left) / max(n-1, 1)
                canvas.create_text(W//2, 20, text="📉 折线图(趋势)",
                                   fill=_ACCENT, font=("Microsoft YaHei", 12, "bold"))
                # 网格 + y 轴刻度
                for gi in range(5):
                    yy = top + (bottom - top) * gi / 4
                    canvas.create_line(left, yy, right, yy, fill="#313244", dash=(2,2))
                    tv = max_v - rng * gi / 4
                    canvas.create_text(left - 8, yy, text=f"{tv:.2g}", fill="#6c7086",
                                       anchor="e", font=("Microsoft YaHei", 9))
                # 折线点
                pts = []
                for i, (v, _) in enumerate(vals):
                    x = left + i * x_step
                    y = bottom - (v - min_v) / rng * (bottom - top)
                    pts.append(x); pts.append(y)
                if len(pts) >= 4:
                    canvas.create_line(*pts, fill=_ACCENT, width=2, smooth=True)
                for i, (v, label) in enumerate(vals):
                    x = left + i * x_step
                    y = bottom - (v - min_v) / rng * (bottom - top)
                    color = _COLORS[i % len(_COLORS)]
                    canvas.create_oval(x-5, y-5, x+5, y+5, fill=color, outline="white", width=1)
                    canvas.create_text(x, y - 14, text=f"{v:g}", fill=_FG,
                                       font=("Microsoft YaHei", 9, "bold"))
                    if n <= 15:
                        canvas.create_text(x, bottom + 12, text=label[:8], fill="#a6adc8",
                                           font=("Microsoft YaHei", 8), anchor="n")
            # ====== 图表 7: 面积图 ======
            def _draw_area():
                W = max(int(canvas.winfo_width()), 920); H = max(int(canvas.winfo_height()), 620)
                vals = [(v, l) for _, v, l in nums[:30]]
                n = len(vals)
                if n < 2: _draw_bar(); return
                top=70; bottom=H-50; left=80; right=W-40
                allv = [max(0, v) for v,_ in vals]  # 面积图只取正
                max_v = max(allv) if allv else 1
                x_step = (right - left) / max(n-1, 1)
                canvas.create_text(W//2, 20, text="🌊 面积图(累积趋势)",
                                   fill=_ACCENT, font=("Microsoft YaHei", 12, "bold"))
                # 多边形(折线 + 底边闭合成面)
                pts = [left, bottom]
                for i, v in enumerate(allv):
                    x = left + i * x_step
                    y = bottom - v / max(max_v, 1) * (bottom - top)
                    pts.extend([x, y])
                pts.extend([right, bottom])
                if len(pts) >= 6:
                    canvas.create_polygon(*pts, fill="#89b4fa33", outline=_ACCENT, width=2, smooth=True)
                # 顶点 + 数值
                for i, (v, label) in enumerate(vals):
                    x = left + i * x_step
                    y = bottom - max(0, v) / max(max_v, 1) * (bottom - top)
                    canvas.create_oval(x-4, y-4, x+4, y+4, fill=_COLORS[i % len(_COLORS)], outline="")
                    canvas.create_text(x, y - 12, text=f"{v:g}", fill=_FG,
                                       font=("Microsoft YaHei", 9, "bold"))
            # ====== 图表 8: 环形甜甜圈图 ======
            def _draw_donut():
                W = max(int(canvas.winfo_width()), 920); H = max(int(canvas.winfo_height()), 620)
                cx, cy = W//2 - 80, H//2 + 10
                r = min(H//2 - 80, 280); inner = r * 0.55
                vals = sorted([(max(0,v), l) for _, v, l in nums[:10]], key=lambda x:-x[0])[:8]
                vals = [(v,l) for v,l in vals if v > 0]
                if len(vals) < 2: canvas.create_text(W//2, H//2, text="环形图需 ≥2 正值", fill="#f38ba8", font=("Microsoft YaHei", 14)); _draw_bar(); return
                total = sum(v for v,_ in vals) or 1
                canvas.create_text(cx, 25, text="🍩 环形甜甜圈图",
                                   fill=_ACCENT, font=("Microsoft YaHei", 12, "bold"))
                start = 0
                for i, (v, label) in enumerate(vals):
                    span = v / total * 360
                    c = _COLORS[i % len(_COLORS)]
                    # 用两个弧合成环形(外弧 + 内弧反向 → 填充环)
                    canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=start, extent=span, fill=c, outline=_BG, width=2)
                    canvas.create_arc(cx-inner, cy-inner, cx+inner, cy+inner, start=start, extent=span, fill=_BG, outline=_BG)
                    start += span
                # 中心文字
                canvas.create_text(cx, cy - 10, text="总指标", fill="#a6adc8", font=("Microsoft YaHei", 10))
                canvas.create_text(cx, cy + 15, text=f"{total:.3g}", fill=_ACCENT, font=("Microsoft YaHei", 20, "bold"))
                canvas.create_text(cx, cy + 40, text=f"{len(vals)} 项占比", fill="#6c7086", font=("Microsoft YaHei", 9))
                # 图例
                lx = cx + r + 40; ly = cy - r + 20
                for i, (v, label) in enumerate(vals):
                    ty = ly + i * 24
                    c = _COLORS[i % len(_COLORS)]
                    canvas.create_oval(lx, ty, lx + 12, ty + 12, fill=c, outline="")
                    pct = v/total*100
                    canvas.create_text(lx + 18, ty + 6,
                                       text=f"{label[:26]}  {v:g}  ({pct:.1f}%)",
                                       fill=_FG, anchor="w", font=("Microsoft YaHei", 10))
            # ====== 图表 9: 漏斗图 ======
            def _draw_funnel():
                W = max(int(canvas.winfo_width()), 920); H = max(int(canvas.winfo_height()), 620)
                vals = [(v, l) for _, v, l in nums[:8]]
                if len(vals) < 2: _draw_bar(); return
                canvas.create_text(W//2, 25, text="⚗️ 漏斗图(转化率/层级)",
                                   fill=_ACCENT, font=("Microsoft YaHei", 12, "bold"))
                n = len(vals)
                layer_h = min(60, (H - 100) // max(n, 1))
                cy = 70; funnel_w = W - 280; top_w = funnel_w
                # 按最大值归一化宽度
                max_v = max(v for v,_ in vals) or 1
                for i, (v, label) in enumerate(vals):
                    ratio = (v / max_v) if max_v > 0 else 0
                    bw = int(top_w * (0.3 + 0.7 * ratio))
                    x0 = W//2 - bw//2; x1 = W//2 + bw//2
                    y0 = cy + i * layer_h; y1 = y0 + layer_h - 4
                    c = _COLORS[i % len(_COLORS)]
                    canvas.create_rectangle(x0, y0, x1, y1, fill=c, outline=_BG, width=2)
                    # 层内文字(中文 + 值)
                    display = f"{label[:22]}   {v:g}"
                    canvas.create_text((x0+x1)//2, (y0+y1)//2, text=display,
                                       fill="white", font=("Microsoft YaHei", 11, "bold"))
                    # 侧边转化率(和上一层比)
                    if i > 0:
                        prev_v = vals[i-1][0]
                        conv = v / prev_v * 100 if prev_v != 0 else 0
                        canvas.create_text(W//2 + funnel_w//2 + 30, (y0+y1)//2,
                                           text=f"转化率 {conv:.1f}%", fill="#fab387",
                                           font=("Microsoft YaHei", 10))
                # 漏斗尖
                last = vals[-1]
                y0 = cy + n * layer_h - 4
                y1 = y0 + 30; x0 = W//2 - 20; x1 = W//2 + 20
                canvas.create_polygon(x0, y0, x1, y0, W//2, y1, fill=_COLORS[n % len(_COLORS)], outline=_BG)
                canvas.create_text(W//2, y1 + 14, text=f"剩余 {last[1]}: {last[0]:g}",
                                   fill="#a6e3a1", font=("Microsoft YaHei", 10))
            # ====== 图表 10: 南丁格尔玫瑰图 ======
            def _draw_rose():
                W = max(int(canvas.winfo_width()), 920); H = max(int(canvas.winfo_height()), 620)
                cx, cy = W//2, H//2 + 20
                r_base = min(W, H)//2 - 120
                vals = [(max(0,v), l) for _, v, l in nums[:12]]
                vals = [(v,l) for v,l in vals if v > 0]
                n = len(vals)
                if n < 2: canvas.create_text(W//2, H//2, text="玫瑰图需 ≥2 正值", fill="#f38ba8", font=("Microsoft YaHei", 14)); _draw_bar(); return
                max_v = max(v for v,_ in vals) or 1
                canvas.create_text(W//2, 20, text="🌹 南丁格尔玫瑰图(半径=数值)",
                                   fill=_ACCENT, font=("Microsoft YaHei", 12, "bold"))
                span = 360 / n
                for i, (v, label) in enumerate(vals):
                    c = _COLORS[i % len(_COLORS)]
                    r = r_base * (0.2 + 0.8 * v / max_v)
                    a0 = 90 + i * span - span/2
                    a0 + span
                    # 扇形(半径随值变化)
                    canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                                       start=a0, extent=span, fill=c, outline=_BG, width=2)
                    # 半径线段
                    ang = _math.radians(90 + i * span)
                    xr = cx + r * _math.cos(ang); yr = cy - r * _math.sin(ang)
                    canvas.create_line(cx, cy, xr, yr, fill=_BG)
                    # 中值标记(文字放扇形中间)
                    mid_a = _math.radians(90 + i * span)
                    tx = cx + (r + 18) * _math.cos(mid_a)
                    ty = cy - (r + 18) * _math.sin(mid_a)
                    canvas.create_text(tx, ty, text=f"{v:g}", fill="white",
                                       font=("Microsoft YaHei", 9, "bold"))
                # 外圈标签
                for i, (_, label) in enumerate(vals):
                    mid_a = _math.radians(90 + i * span)
                    tx = cx + (r_base + 40) * _math.cos(mid_a)
                    ty = cy - (r_base + 40) * _math.sin(mid_a)
                    anchor = "center"
                    if _math.cos(mid_a) > 0.3: anchor = "w"
                    elif _math.cos(mid_a) < -0.3: anchor = "e"
                    canvas.create_text(tx, ty, text=label[:12], fill=_FG,
                                       anchor=anchor, font=("Microsoft YaHei", 10))
                # 图例
                for i, (v, label) in enumerate(vals):
                    ty = cy + r_base + 30 + i * 20
                    if ty < H - 20:
                        canvas.create_text(20, ty, text=f"● {label[:20]} = {v:g}",
                                           fill=_FG, anchor="w", font=("Microsoft YaHei", 10))
            # ====== 图表类型下拉框(解决小屏幕点击不准的问题)======
            tk.Label(types_fr, text="图表:", bg=_BG, fg="#a6adc8", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(0, 4))
            _chart_labels = [f"{lb}  ({t})" for t, lb in chart_options]
            _chart_values = [t for t, _ in chart_options]
            # 找到推荐类型对应的 index
            _cur_idx = _chart_values.index(chart_type_var.get()) if chart_type_var.get() in _chart_values else 0
            _combo_var = tk.StringVar(value=_chart_labels[_cur_idx])
            def _on_combo_change(_evt=None):
                # 从下拉标签反查类型 code
                sel = _combo_var.get()
                for i, lb in enumerate(_chart_labels):
                    if lb == sel:
                        chart_type_var.set(_chart_values[i])
                        _redraw()
                        break
            _combo = ttk.Combobox(types_fr, textvariable=_combo_var, values=_chart_labels,
                                  width=14, state="readonly", font=("Microsoft YaHei", 9))
            _combo.pack(side=tk.LEFT)
            _combo.bind("<<ComboboxSelected>>", _on_combo_change)
            # ====== 创建底部按钮(所有函数已定义,安全引用)======
            btn_frame = tk.Frame(dlg, bg=_BG)
            btn_frame.pack(fill=tk.X, padx=8, pady=(4, 8))
            ttk.Button(btn_frame, text="💾保存为PNG",
                       command=lambda: _save_canvas_png(canvas, skill_info.get('name','skill'))).pack(side=tk.LEFT, padx=4)
            ttk.Button(btn_frame, text="📋复制JSON",
                       command=lambda: dlg.clipboard_clear() or dlg.clipboard_append(_json.dumps(data, ensure_ascii=False, indent=2))).pack(side=tk.LEFT, padx=4)
            ttk.Button(btn_frame, text="🔄重绘", command=_redraw).pack(side=tk.LEFT, padx=4)
            ttk.Button(btn_frame, text="关闭", command=dlg.destroy).pack(side=tk.RIGHT, padx=4)
            # 首次绘制 - 用 dlg.after 而不是 win.after(win 可能已被关闭)
            def _safe_after():
                if dlg.winfo_exists():
                    canvas.update_idletasks()
                    _redraw()
            dlg.after(150, _safe_after)  # 等 canvas 布局完 + 强制刷新
        def _save_canvas_png(canvas_widget, name):
            """Canvas 导出 PNG(先转 PostScript,再用 PIL 转 PNG)"""
            try:
                import os as _os
                import tempfile
                ps_path = _os.path.join(tempfile.gettempdir(), f"skill_{name.replace('/','_')}.ps")
                canvas_widget.postscript(file=ps_path, colormode='color')
                from PIL import Image
                img = Image.open(ps_path)
                png_path = _os.path.expanduser(f"~/Desktop/{name}_结果.png")
                img.save(png_path, "png")
                _os.remove(ps_path)
                import tkinter.messagebox as _mb
                _mb.showinfo("已保存", f"✅ PNG 已保存到:\n{png_path}")
            except Exception as e:
                import tkinter.messagebox as _mb
                _mb.showwarning("保存失败", f"{e}\n\n尝试保存到临时目录...")
                try:
                    png_path = _os.path.join(tempfile.gettempdir(), f"skill_{name}.png")
                    from PIL import Image
                    img = Image.open(ps_path) if _os.path.exists(ps_path) else None
                    if img: img.save(png_path, "png")
                except Exception: pass
        def _exec_skill(info, params, output_widget, label_widget, save_to_db=False, tag_prefix=""):
            """执行指定 skill 的首个脚本,结果写入 output_widget;save_to_db=True 时入库 news_info"""
            import subprocess
            import threading
            # 安全投递到主线程 - win 可能已被用户关闭
            def _safe_after(callback):
                try:
                    if win.winfo_exists():
                        win.after(0, callback)
                    else:
                        self.root.after(0, callback)
                except Exception:
                    self.root.after(0, callback)
            def _safe_insert_text(widget, text):
                """安全向 output_widget 插入文本(widget 可能已被销毁)"""
                try:
                    if widget and widget.winfo_exists():
                        widget.insert(tk.END, text)
                        widget.see(tk.END)
                except Exception:
                    pass
            def _safe_label_config(lw, text):
                try:
                    if lw and lw.winfo_exists():
                        lw.config(text=text)
                except Exception:
                    pass
            if not info or not info.get("scripts"):
                _safe_insert_text(output_widget, f"{tag_prefix}此Skill无Python脚本(文档型),跳过\n")
                _safe_label_config(label_widget, "跳过")
                return
            script_path = info["scripts"][0]["path"]
            py_bin = _resolve_py_bin()
            _safe_insert_text(output_widget, f"{tag_prefix}运行: {py_bin} {script_path} {' '.join(params)}\n")
            _safe_insert_text(output_widget, "=" * 60 + "\n")
            _safe_label_config(label_widget, "运行中...")
            def work():
                try:
                    cmd = [py_bin, script_path] + params
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=info["dir"], env={**dict(__import__('os').environ), 'PYTHONIOENCODING': 'utf-8', 'PYTHONPATH': info["dir"]})
                    result_text = ""
                    if proc.stdout:
                        result_text += proc.stdout + "\n"
                    if proc.stderr:
                        result_text += f"[错误输出]\n{proc.stderr}\n"
                    result_text += f"\n退出码: {proc.returncode}\n"
                    def show_result():
                        _safe_insert_text(output_widget, result_text)
                        _safe_label_config(label_widget, f"完成 (退出码{proc.returncode})")
                        # 入库 news_info
                        if save_to_db and proc.stdout:
                            try:
                                    tab_name = f"[Skill]{info['name']}_{__import__('datetime').datetime.now().strftime('%m%d%H%M')}"
                                    content = f"脚本: {os.path.basename(script_path)}\n参数: {' '.join(params)}\n运行时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n退出码: {proc.returncode}\n\n{proc.stdout.strip()}"
                                    save_news_info_to_db(tab_name, content)
                                    _safe_insert_text(output_widget, "\n✅ 结果已入库 news_info 表\n")
                            except Exception as e:
                                    _safe_insert_text(output_widget, f"\n⚠️ 入库失败: {e}\n")
                        # 保存最后一次结果(供手动点"📊 图形"按钮弹出)
                        _last_result["stdout"] = proc.stdout or ""
                        _last_result["skill_info"] = info
                        # 自动弹窗已改为手动:用户点"📊 图形"按钮时才弹出
                        # if proc.stdout:
                        #     try:
                        #         _try_popup_skill_dashboard(proc.stdout.strip(), info, output_widget)
                        #     except Exception as e:
                        #         print(f"[dashboard error] {info.get('name')}: {e}", file=_sys.stderr)
                    _safe_after(show_result)
                except subprocess.TimeoutExpired:
                    def show_timeout():
                        _safe_insert_text(output_widget, f"{tag_prefix}❌ 超时(120秒)\n")
                        _safe_label_config(label_widget, "超时")
                    _safe_after(show_timeout)
                except Exception as e:
                    def show_err(e=e):
                        _safe_insert_text(output_widget, f"{tag_prefix}❌ 运行失败: {e}\n")
                        _safe_label_config(label_widget, "失败")
                    _safe_after(show_err)
            threading.Thread(target=work, daemon=True).start()
        def run_script():
            info = current_skill.get("info")
            if not info:
                messagebox.showwarning("提示", "请先选择一个Skill", parent=win)
                return
            if not info["scripts"]:
                messagebox.showinfo("提示", "此Skill无Python脚本,为文档型Skill", parent=win)
                return
            params = param_var.get().strip().split()
            output_text.delete("1.0", tk.END)
            _exec_skill(info, params, output_text, output_label, save_to_db=save_db_var.get())
        run_btn.config(command=run_script)
        def _open_graph_dashboard():
            """手动弹出 skill 结果图形界面"""
            _out = _last_result.get("stdout", "")
            _info = _last_result.get("skill_info") or {}
            if not _out or not _out.strip():
                messagebox.showinfo("提示", "请先运行一个 Skill,然后再点此按钮查看图形", parent=win)
                return
            try:
                _try_popup_skill_dashboard(_out.strip(), _info, output_text)
            except Exception as e:
                print(f"[dashboard error] {e}", file=_sys.stderr)
                messagebox.showerror("图形生成失败", str(e), parent=win)
        graph_btn.config(command=_open_graph_dashboard)
        def _parse_times_from_text(raw):
            """HH:MM,14:30 → ['11:00','14:30']"""
            if not raw.strip():
                return []
            times = []
            for t in raw.replace(",", ",").split(","):
                t = t.strip()
                if not t:
                    continue
                if ":" not in t and len(t) >= 3:
                    t = t[:-2] + ":" + t[-2:]
                try:
                    h, m = t.split(":")
                    if 0 <= int(h) <= 23 and 0 <= int(m) <= 59:
                        times.append(f"{int(h):02d}:{int(m):02d}")
                except Exception:
                    continue
            return sorted(set(times))
        def open_schedule_for_current_skill():
            """⏰ 定时执行(针对左 Treeview 当前选中的 skill--轻量小弹窗)"""
            info = current_skill.get("info")
            if not info:
                messagebox.showwarning("提示", "请先在左侧 Skill 列表中选中一个 skill", parent=win); return
            if info.get("exec_type") != "可执行":
                messagebox.showwarning("提示", f"「{info['name']}」是文档型 skill,无可执行脚本", parent=win); return
            dlg = self._toplevel(win)
            dlg.title(f"⏰ 定时执行 - {info['name']}")
            dlg.geometry("420x260"); dlg.transient(win); dlg.grab_set()
            # 只读显示当前 skill(不是下拉框)
            ttk.Label(dlg, text="📌 当前 Skill:", font=("Microsoft YaHei", 10, "bold")).grid(row=0, column=0, sticky=tk.W, padx=12, pady=(14, 6))
            ttk.Label(dlg, text=info["name"], foreground="#1565C0", font=("Microsoft YaHei", 10, "bold")).grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=4, pady=(14, 6))
            ttk.Label(dlg, text=f"{info.get('category', '')} | {info.get('exec_type', '')} | {len(info.get('scripts', []))} 个脚本",
                      foreground="gray", font=("Microsoft YaHei", 8)).grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=4)
            ttk.Label(dlg, text="🕒 执行时间点:").grid(row=2, column=0, sticky=tk.W, padx=12, pady=(12, 4))
            time_var = tk.StringVar(value="11:00,14:30")
            ttk.Entry(dlg, textvariable=time_var, width=30).grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=4, pady=(12, 4))
            ttk.Label(dlg, text="例: 11:00,14:30 (多个用逗号)", foreground="gray", font=("Microsoft YaHei", 8)).grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=4)
            ttk.Label(dlg, text="⚙️ 脚本参数:").grid(row=4, column=0, sticky=tk.W, padx=12, pady=6)
            p_var = tk.StringVar(value=param_var.get())  # 自动带入右面板已填参数
            ttk.Entry(dlg, textvariable=p_var, width=30).grid(row=4, column=1, columnspan=2, sticky=tk.W, padx=4, pady=6)
            ttk.Label(dlg, text="(可选,格式 --参数名 值)", foreground="gray", font=("Microsoft YaHei", 8)).grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=4)
            def _parse_times(raw):
                if not raw.strip(): return []
                tms = []
                for t in raw.replace(",", ",").split(","):
                    t = t.strip()
                    if not t: continue
                    if ":" not in t and len(t) >= 3: t = t[:-2] + ":" + t[-2:]
                    try:
                        h, m = t.split(":")
                        if 0 <= int(h) <= 23 and 0 <= int(m) <= 59: tms.append(f"{int(h):02d}:{int(m):02d}")
                    except Exception: pass
                return sorted(set(tms))
            def add_to_schedule():
                times = _parse_times(time_var.get())
                if not times:
                    messagebox.showwarning("提示", "时间点无效(格式 HH:MM,多个用逗号)", parent=dlg); return
                params = p_var.get().strip().split()
                # 检查重复
                for t in self._scheduled_skills:
                    if t.get("skill_name") == info["name"] and set(t.get("times", [])) == set(times):
                        messagebox.showinfo("已存在", f"定时任务已存在:{info['name']} → {','.join(times)}\n可在「📋定时管理」中查看/修改", parent=dlg); return
                import uuid as _uuid
                self._scheduled_skills.append({
                    "id": _uuid.uuid4().hex[:8], "skill_name": info["name"],
                    "params": params, "times": times, "active": True,
                    "last_fired": {}, "last_run": "",
                    "notes": "Skill浏览器添加"
                })
                self._save_scheduled_skills()
                self._log_skill_scheduler(f"➕ 新增定时任务: {info['name']} → {','.join(times)} (已启用)")
                messagebox.showinfo("✅ 已加入定时",
                    f"定时任务已添加:\n  Skill: {info['name']}\n  时间: {', '.join(times)}\n  参数: {' '.join(params) or '(无)'}\n\n可在「📋定时管理」中查看所有任务",
                    parent=dlg)
                dlg.destroy()
            def run_now():
                params = p_var.get().strip().split()
                self._exec_skill(info, params, output_text, output_label, save_to_db=save_db_var.get(), tag_prefix="[手动] ")
                self._log_skill_scheduler(f"⚡ 手动执行(轻量弹窗): {info['name']}")
                dlg.destroy()
            btns = ttk.Frame(dlg); btns.grid(row=6, column=0, columnspan=3, pady=14)
            ttk.Button(btns, text="⚡ 立即执行一次", width=16, command=run_now).pack(side=tk.LEFT, padx=6)
            ttk.Button(btns, text="➕ 加入定时任务", width=16, command=add_to_schedule).pack(side=tk.LEFT, padx=6)
            ttk.Button(btns, text="关闭", width=8, command=dlg.destroy).pack(side=tk.LEFT, padx=6)
        def open_schedule_dialog():
            """📋 定时任务管理(全局:展示所有定时任务,增删改启停)"""
            nonlocal all_skills
            sched_win = self._toplevel(win)
            sched_win.title("📋 Skill 定时任务管理(全局)")
            sched_win.geometry("920x640")
            sched_win.transient(win)
            sched_win.minsize(820, 540)
            def _next_id():
                import uuid as _uuid
                return _uuid.uuid4().hex[:8]
            # ====== 顶部状态栏 ======
            top_bar = ttk.Frame(sched_win, padding=(6, 4))
            top_bar.pack(fill=tk.X)
            status_var = tk.StringVar(value="初始化中...")
            ttk.Label(top_bar, textvariable=status_var, font=("Microsoft YaHei", 10, "bold"), foreground="#1976D2").pack(side=tk.LEFT, padx=4)
            ttk.Label(top_bar, text="提示:在左侧 Skill 浏览器选中 skill → 点「⏰定时执行」来添加新定时任务",
                      foreground="gray", font=("Microsoft YaHei", 8)).pack(side=tk.RIGHT, padx=4)
            # Treeview:任务列表
            cols = ("skill", "times", "active", "params", "last_run")
            tree_frame = ttk.Frame(sched_win)
            tree_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
            task_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=10)
            task_tree.heading("skill", text="Skill名称")
            task_tree.heading("times", text="执行时间点")
            task_tree.heading("active", text="状态")
            task_tree.heading("params", text="参数")
            task_tree.heading("last_run", text="上次执行")
            task_tree.column("skill", width=180)
            task_tree.column("times", width=180)
            task_tree.column("active", width=70, anchor="center")
            task_tree.column("params", width=140)
            task_tree.column("last_run", width=160)
            task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=task_tree.yview)
            tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            task_tree.configure(yscrollcommand=tree_scroll.set)
            # 调度器日志
            log_lf = ttk.LabelFrame(sched_win, text="调度器日志(最近 200 条)", padding=4)
            log_lf.pack(fill=tk.BOTH, expand=False, padx=6, pady=(0, 6))
            log_text = scrolledtext.ScrolledText(log_lf, wrap=tk.WORD, font=("Courier New", 9), height=6, state="disabled")
            log_text.pack(fill=tk.BOTH, expand=True)
            def _task_to_values(t):
                times_str = ",".join(t.get("times", []))
                active_str = "✅ 启用" if t.get("active", True) else "⏸ 暂停"
                params_str = " ".join(t.get("params") or []) or "(无)"
                if len(params_str) > 20:
                    params_str = params_str[:18] + "..."
                return (t.get("skill_name", ""), times_str, active_str, params_str, t.get("last_run") or "-")
            def refresh_tree():
                task_tree.delete(*task_tree.get_children())
                for t in self._scheduled_skills:
                    tid = t.get("id") or ""
                    task_tree.insert("", tk.END, iid=tid, values=_task_to_values(t))
                active_count = sum(1 for t in self._scheduled_skills if t.get("active", True))
                status_var.set(f"共 {len(self._scheduled_skills)} 个定时任务 / {active_count} 个激活  |  调度器全局运行中(每 20s 轮询)")
            def refresh_log():
                log_text.config(state="normal")
                log_text.delete("1.0", tk.END)
                for ts, msg in self._skill_scheduler_log[-80:]:
                    log_text.insert(tk.END, f"[{ts}] {msg}\n")
                log_text.see(tk.END)
                log_text.config(state="disabled")
            def _get_selected_task():
                sel = task_tree.selection()
                if not sel:
                    messagebox.showwarning("提示", "请先在列表中选择一个定时任务", parent=sched_win)
                    return None
                tid = sel[0]
                for t in self._scheduled_skills:
                    if t.get("id") == tid:
                        return t
                return None
            def open_edit_subdialog(task=None):
                """新增/编辑子对话框"""
                is_edit = task is not None
                title = "✏️ 修改定时任务" if is_edit else "➕ 新增定时任务"
                sub = self._toplevel(sched_win)
                sub.title(title)
                sub.geometry("520x360")
                sub.transient(sched_win); sub.grab_set()
                exec_skills_sub = [s for s in all_skills if s["exec_type"] == "可执行"]
                default_skill = (task.get("skill_name") if task else "") or ""
                cur2 = current_skill.get("info")
                if not default_skill and cur2 and cur2.get("exec_type") == "可执行":
                    default_skill = cur2["name"]
                default_times = ",".join(task.get("times", [])) if task else "11:00,14:30"
                default_params = " ".join(task.get("params") or []) if task else ""
                default_notes = task.get("notes", "") if task else ""
                ttk.Label(sub, text="Skill:", font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky=tk.W, padx=8, pady=(12, 4))
                sub_skill_var = tk.StringVar(value=default_skill)
                sub_skill_combo = ttk.Combobox(sub, textvariable=sub_skill_var, width=45, state="readonly",
                                               values=[s["name"] for s in exec_skills_sub])
                sub_skill_combo.grid(row=0, column=1, sticky=tk.W, padx=4)
                ttk.Label(sub, text=f"可执行: {len(exec_skills_sub)} 个", foreground="gray").grid(row=0, column=2, padx=4)
                ttk.Label(sub, text="时间点 (HH:MM):").grid(row=1, column=0, sticky=tk.W, padx=8, pady=4)
                sub_time_var = tk.StringVar(value=default_times)
                ttk.Entry(sub, textvariable=sub_time_var, width=48).grid(row=1, column=1, sticky=tk.W, padx=4)
                ttk.Label(sub, text="例: 11:00,14:30", foreground="gray").grid(row=1, column=2, padx=4)
                ttk.Label(sub, text="参数 (可选):").grid(row=2, column=0, sticky=tk.W, padx=8, pady=4)
                sub_param_var = tk.StringVar(value=default_params)
                ttk.Entry(sub, textvariable=sub_param_var, width=48).grid(row=2, column=1, sticky=tk.W, padx=4)
                ttk.Label(sub, text="备注 (可选):").grid(row=3, column=0, sticky=tk.W, padx=8, pady=4)
                sub_notes_var = tk.StringVar(value=default_notes)
                ttk.Entry(sub, textvariable=sub_notes_var, width=48).grid(row=3, column=1, sticky=tk.W, padx=4)
                sub_active_var = tk.BooleanVar(value=(task.get("active", True) if task else True))
                ttk.Checkbutton(sub, text="✅ 启动后立即激活", variable=sub_active_var).grid(row=4, column=0, columnspan=3, sticky=tk.W, padx=8, pady=8)
                def _save():
                    skill_name = sub_skill_var.get().strip()
                    if not skill_name:
                        messagebox.showwarning("提示", "请选择 Skill", parent=sub); return
                    times = _parse_times_from_text(sub_time_var.get())
                    if not times:
                        messagebox.showwarning("提示", "时间点无效", parent=sub); return
                    params = sub_param_var.get().strip().split()
                    notes = sub_notes_var.get().strip()
                    active = sub_active_var.get()
                    new_task = {
                        "id": (task.get("id") if task else _next_id()),
                        "skill_name": skill_name, "params": params, "times": times,
                        "active": active, "last_fired": task.get("last_fired", {}) if task else {},
                        "last_run": task.get("last_run", "") if task else "", "notes": notes
                    }
                    if is_edit:
                        for i, t in enumerate(self._scheduled_skills):
                            if t.get("id") == task.get("id"):
                                    self._scheduled_skills[i] = new_task; break
                    else:
                        self._scheduled_skills.append(new_task)
                    self._save_scheduled_skills(); refresh_tree()
                    self._log_skill_scheduler(f"{'修改' if is_edit else '新增'}定时任务: {skill_name} → {','.join(times)} {'(已启用)' if active else '(已暂停)'}")
                    refresh_log(); sub.destroy()
                btn_row = ttk.Frame(sub); btn_row.grid(row=5, column=0, columnspan=3, pady=12)
                ttk.Button(btn_row, text="💾 保存", command=_save).pack(side=tk.LEFT, padx=6)
                ttk.Button(btn_row, text="取消", command=sub.destroy).pack(side=tk.LEFT, padx=6)
            # ====== 底部 CRUD 按钮 ======
            bottom_bar = ttk.Frame(sched_win, padding=4)
            bottom_bar.pack(fill=tk.X, padx=6, pady=(0, 4))
            ttk.Button(bottom_bar, text="➕ 新增(子对话框)", command=lambda: open_edit_subdialog()).pack(side=tk.RIGHT, padx=2)
            ttk.Button(bottom_bar, text="🗑️ 删除", command=lambda: (lambda t: (self._scheduled_skills.remove(t), self._save_scheduled_skills(), refresh_tree(), self._log_skill_scheduler(f"删除定时任务: {t.get('skill_name')}"), refresh_log()) if t else None)(_get_selected_task())).pack(side=tk.RIGHT, padx=2)
            ttk.Button(bottom_bar, text="✏️ 修改", command=lambda: (lambda t: open_edit_subdialog(t) if t else None)(_get_selected_task())).pack(side=tk.RIGHT, padx=2)
            ttk.Button(bottom_bar, text="⏸ 暂停", command=lambda: (lambda t: (t.update({"active": False}), self._save_scheduled_skills(), refresh_tree(), self._log_skill_scheduler(f"暂停: {t.get('skill_name')}"), refresh_log()) if t else None)(_get_selected_task())).pack(side=tk.RIGHT, padx=2)
            ttk.Button(bottom_bar, text="▶ 启用", command=lambda: (lambda t: (t.update({"active": True}), self._save_scheduled_skills(), refresh_tree(), self._log_skill_scheduler(f"启用: {t.get('skill_name')}"), refresh_log()) if t else None)(_get_selected_task())).pack(side=tk.RIGHT, padx=2)
            ttk.Button(bottom_bar, text="⚡ 执行选中", command=lambda: (lambda t: (self._run_scheduled_task(t, "手动"), self._log_skill_scheduler(f"手动触发: {t.get('skill_name')}"), refresh_log()) if t else None)(_get_selected_task())).pack(side=tk.RIGHT, padx=2)
            # 双击行 → 编辑
            def on_double_click(e):
                sel = task_tree.selection()
                if not sel: return
                tid = sel[0]
                for t in self._scheduled_skills:
                    if t.get("id") == tid:
                        open_edit_subdialog(t); break
            task_tree.bind("<Double-Button-1>", on_double_click)
            # 初始显示 + 3 秒后自动刷新日志和任务列表
            refresh_tree()
            refresh_log()
            def auto_refresh_all():
                try:
                    if sched_win.winfo_exists():
                        refresh_tree()
                        refresh_log()
                        sched_win.after(3000, auto_refresh_all)
                except Exception:
                    pass
            sched_win.after(3000, auto_refresh_all)
            # 底部关闭按钮
            bottom_bar = ttk.Frame(sched_win)
            bottom_bar.pack(fill=tk.X, padx=6, pady=(0, 6))
            ttk.Button(bottom_bar, text="关闭窗口", command=sched_win.destroy).pack(side=tk.RIGHT, padx=4)
        schedule_btn.config(command=open_schedule_for_current_skill)
        manager_btn.config(command=open_schedule_dialog)
        def show_new_skills():
            """比对龙虾同步清单,列出新增 skill"""
            new_list = self._detect_new_qclaw_skills(all_skills, last_known_count=self._qclaw_known_count)
            if not new_list:
                messagebox.showinfo("龙虾新增", "未检测到新增 Skill(与上次扫描一致)", parent=win)
                return
            msg_lines = [f"🦞 龙虾 qclaw 新增 {len(new_list)} 个 Skill:\n"]
            for ns in new_list:
                msg_lines.append(f"  • {ns['name']}  ({ns.get('timestamp','')[:19]})")
            messagebox.showinfo("龙虾新增", "\n".join(msg_lines), parent=win)
            # 在列表里筛选出新增项
            new_names = {ns["name"] for ns in new_list}
            search_var.set("")
            category_var.set("全部")
            exec_type_var.set("全部")
            update_list()
            # 高亮新增项
            for item in skill_list.get_children():
                vals = skill_list.item(item, "values")
                if vals and vals[0] in new_names:
                    skill_list.selection_add(item)
                    skill_list.see(item)
        new_btn.config(command=show_new_skills)
        skill_list.bind("<<TreeviewSelect>>", on_select)
        search_var.trace_add("write", lambda *_: update_list())
        category_combo.bind("<<ComboboxSelected>>", lambda e: update_list())
        exec_type_combo.bind("<<ComboboxSelected>>", lambda e: update_list())
        sort_combo.bind("<<ComboboxSelected>>", lambda e: update_list())
        bry28_combo.bind("<<ComboboxSelected>>", lambda e: update_list())
        def refresh_skills():
            nonlocal all_skills, categories
            all_skills = self._scan_qclaw_skills()
            categories = ["全部"] + sorted({s["category"] for s in all_skills})
            category_combo['values'] = categories
            # 更新已知名单 + 基线时间
            self._qclaw_known_names = {s["name"] for s in all_skills}
            self._qclaw_known_count = len(all_skills)
            try:
                sm = getattr(self, "_qclaw_sync_manifest", {}) or {}
                hist = sm.get("history", [])
                self._qclaw_last_seen_time = max((h.get("timestamp", "") for h in hist), default="")
            except Exception:
                self._qclaw_last_seen_time = ""
            update_list()
        refresh_btn.config(command=refresh_skills)
        # 配置标签
        detail_text.tag_config("title_tag", font=("Microsoft YaHei", 14, "bold"), foreground="#1a73e8")
        detail_text.tag_config("section_tag", font=("Microsoft YaHei", 11, "bold"), foreground="#0d6efd")
        detail_text.tag_config("subtitle_tag", font=("Microsoft YaHei", 10, "bold"), foreground="#155724")
        detail_text.tag_config("warn_tag", font=("Microsoft YaHei", 10, "italic"), foreground="#856404")
        # 初始加载
        update_list()

    def _maximize_skill_output(self, text_widget, parent_win):
        """双击/点击最大化按钮:弹出全屏查看窗口"""
        text = text_widget.get("1.0", tk.END)
        big_win = self._toplevel(parent_win)
        big_win.title("Skill运行结果 · 最大化查看")
        big_win.geometry("1200x800")
        big_win.transient(parent_win)
        # 工具栏
        toolbar = ttk.Frame(big_win, padding=4)
        toolbar.pack(fill=tk.X)
        big_text = scrolledtext.ScrolledText(big_win, wrap=tk.WORD, font=("Courier New", 12))
        big_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        big_text.insert("1.0", text)
        big_text.config(state=tk.NORMAL)
        # 快捷键
        big_text.bind("<Command-c>", lambda e: big_text.event_generate("<<Copy>>"))
        big_text.bind("<Command-a>", lambda e: big_text.tag_add(tk.SEL, "1.0", tk.END))
        big_text.bind("<Control-c>", lambda e: big_text.event_generate("<<Copy>>"))
        big_text.bind("<Control-a>", lambda e: big_text.tag_add(tk.SEL, "1.0", tk.END))
        # 工具栏按钮
        ttk.Button(toolbar, text="📋复制全部", command=lambda: (big_text.tag_add(tk.SEL, "1.0", tk.END), big_text.event_generate("<<Copy>>"))).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="💾保存TXT", command=lambda: self._save_skill_output(big_text, "txt", big_win)).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📄保存Word", command=lambda: self._save_skill_output(big_text, "docx", big_win)).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🖼️生成图片", command=lambda: self._save_skill_output(big_text, "image", big_win)).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🔄刷新", command=lambda: big_text.delete("1.0", tk.END) or big_text.insert("1.0", text_widget.get("1.0", tk.END))).pack(side=tk.LEFT, padx=3)
        ttk.Label(toolbar, text="  双击结果区可打开此窗口", foreground="gray").pack(side=tk.LEFT, padx=10)
        # 右键菜单
        def _ctx(event):
            m = tk.Menu(big_text, tearoff=0)
            m.add_command(label="复制", command=lambda: big_text.event_generate("<<Copy>>"))
            m.add_command(label="全选", command=lambda: big_text.tag_add(tk.SEL, "1.0", tk.END))
            m.add_separator()
            m.add_command(label="保存为TXT", command=lambda: self._save_skill_output(big_text, "txt", big_win))
            m.add_command(label="保存为Word", command=lambda: self._save_skill_output(big_text, "docx", big_win))
            m.add_command(label="生成为图片", command=lambda: self._save_skill_output(big_text, "image", big_win))
            m.tk_popup(event.x_root, event.y_root)
        big_text.bind("<Button-3>", _ctx)


__all__ = ["RestMixin"]
