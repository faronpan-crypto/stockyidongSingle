"""分析/图表/词频/关键词"""
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
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
except ImportError: plt = None
from utils.network import safe_call
from utils.config import *  # 路径/配置/Token
from data.snapshot import *  # get_news_stocks_* 函数
from logic.stock_names import *  # get_stock_name_by_code 等

from datetime import datetime, timedelta
import re
import os
import sys
import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin
import sqlite3

class AnalysisMixin:
    """分析/图表/词频/关键词"""

    def batch_crawl_and_analyze(self):
        """一键爬取选中的爬取项,保存到资讯表,合并后AI分析"""
        self.batch_crawl_event.clear()
        def batch_crawl_thread():
            try:
                # 获取结果文本框用于显示进度
                result_widget = self.get_active_result_widget()
                if not result_widget:
                    return
                # 获取选中的爬取项
                selected_crawlers = []
                crawler_names = {
                    'taoguba': '淘股吧',
                    'jiuyan': '韭研',
                    'eastmoney': '东方财富',
                    'xueqiu': '雪球',
                    'xuangubao': '选股宝',
                    'ths': '同花顺'
                }
                for key, name in crawler_names.items():
                    if key in self.crawler_checkboxes and self.crawler_checkboxes[key].get():
                        selected_crawlers.append((key, name))
                if not selected_crawlers:
                    self.root.after(0, lambda: result_widget.insert(tk.END, "❌ 警告: 请至少选择一个爬取项\n"))
                    self.root.after(0, lambda: result_widget.see(tk.END))
                    return
                # 在右边文本框显示开始信息
                self.root.after(0, lambda: result_widget.insert(tk.END, f"\n{'='*80}\n"))
                self.root.after(0, lambda: result_widget.insert(tk.END, f"🚀 开始一键爬取,共{len(selected_crawlers)}项...\n"))
                self.root.after(0, lambda: result_widget.insert(tk.END, f"{'='*80}\n\n"))
                self.root.after(0, lambda: result_widget.see(tk.END))
                all_crawled_content = []
                saved_count = 0
                # 逐个执行爬取
                for idx, (crawler_key, crawler_name) in enumerate(selected_crawlers, 1):
                    try:
                        # 在右边文本框显示进度(使用默认参数确保捕获正确的值)
                        def show_progress(name, index, total):
                            result_widget.insert(tk.END, f"[{index}/{total}] 正在爬取 {name}...\n")
                            result_widget.see(tk.END)
                        self.root.after(0, lambda n=crawler_name, i=idx, t=len(selected_crawlers): show_progress(n, i, t))
                        content = None
                        tab_title = None
                        if crawler_key == 'xuangubao':
                            content, tab_title = self._crawl_xuangubao_sync()
                        elif crawler_key == 'ths':
                            content, tab_title = self._crawl_ths_sync()
                        elif crawler_key == 'eastmoney':
                            content, tab_title = self._crawl_eastmoney_sync()
                        elif crawler_key == 'xueqiu':
                            content, tab_title = self._crawl_xueqiu_sync()
                        elif crawler_key == 'taoguba':
                            content, tab_title = self._crawl_taoguba_sync()
                        elif crawler_key == 'jiuyan':
                            content, tab_title = self._crawl_jiuyan_sync()
                        if content and tab_title:
                            timestamp = datetime.now().strftime("%H%M%S")
                            tab_title = f"{crawler_name}_{timestamp}"
                            def create_tab_and_save():
                                # 获取对应的颜色
                                crawler_color = self.crawler_colors.get(crawler_key, '#FFFFFF')
                                tab_id = self.create_text_tab(tab_title, content, bg_color=crawler_color)
                                text_widget = self.text_widgets[tab_id]['widget']
                                if text_widget:
                                    # 设置文本框背景色
                                    text_widget.config(bg=crawler_color)
                                    text_widget.see("1.0")
                            self.root.after(0, create_tab_and_save)
                            if save_news_info_to_db(tab_title, content):
                                saved_count += 1
                                all_crawled_content.append(f"\n{'='*80}\n来源: {crawler_name}\n标签页: {tab_title}\n{'='*80}\n{content}\n")
                                def show_success(name, title):
                                    result_widget.insert(tk.END, f"✅ {name} 爬取成功,已保存到左侧标签和资讯表: {title}\n")
                                    result_widget.see(tk.END)
                                self.root.after(0, lambda n=crawler_name, t=tab_title: show_success(n, t))
                            else:
                                def show_save_fail(name):
                                    result_widget.insert(tk.END, f"⚠️ {name} 已创建标签页,但资讯表保存失败\n")
                                    result_widget.see(tk.END)
                                self.root.after(0, lambda n=crawler_name: show_save_fail(n))
                        else:
                            def show_crawl_fail(name):
                                result_widget.insert(tk.END, f"❌ {name} 爬取失败,未获取到内容\n")
                                result_widget.see(tk.END)
                            self.root.after(0, lambda n=crawler_name: show_crawl_fail(n))
                        time.sleep(1)  # 延迟避免请求过快
                    except Exception as e:
                        def show_error(err, name):
                            result_widget.insert(tk.END, f"❌ 爬取{name}失败: {err}\n")
                            result_widget.see(tk.END)
                        self.root.after(0, lambda e=str(e), n=crawler_name: show_error(e, n))
                        continue
                # 显示爬取总结
                self.root.after(0, lambda: result_widget.insert(tk.END, f"\n{'='*80}\n"))
                self.root.after(0, lambda: result_widget.insert(tk.END, f"📊 爬取完成: 成功保存 {saved_count}/{len(selected_crawlers)} 条数据到资讯表\n"))
                self.root.after(0, lambda: result_widget.insert(tk.END, f"{'='*80}\n\n"))
                self.root.after(0, lambda: result_widget.see(tk.END))
                if not all_crawled_content:
                    self.root.after(0, lambda: result_widget.insert(tk.END, "⚠️ 警告: 未能获取到任何内容,跳过AI分析\n"))
                    self.root.after(0, lambda: result_widget.see(tk.END))
                    return
                # 合并所有内容
                merged_content = '\n'.join(all_crawled_content)
                # 调用AI分析
                self.root.after(0, lambda: result_widget.insert(tk.END, "🤖 开始AI分析...\n"))
                self.root.after(0, lambda: result_widget.see(tk.END))
                try:
                    # 构建AI提示词
                    system_prompt = "你是一个专业的股票市场分析师,擅长分析市场情绪、识别投资机会和风险。"
                    user_prompt = f"""请分析以下合并的股票相关文本内容,这些内容来自多个数据源的爬取结果:
{merged_content[:5000]}  # 限制长度避免超出token限制
请提供:
1. 市场情绪分析
2. 投资机会识别
3. 风险提示
4. 操作建议
5. 重点关注股票(如有)
"""
                    # 调用AI模型
                    ai_result = self.call_ai_model(user_prompt, system_prompt, config_override=None)
                    # 在右边文本框显示分析结果
                    def show_analysis_result():
                        analysis_content = f"\n{'='*80}\n"
                        analysis_content += "📊 一键爬取分析结果\n"
                        analysis_content += f"{'='*80}\n\n"
                        analysis_content += f"爬取来源: {', '.join([name for _, name in selected_crawlers])}\n"
                        analysis_content += f"爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        analysis_content += f"共爬取: {len(selected_crawlers)}项,成功保存: {saved_count}条\n\n"
                        analysis_content += f"{'='*80}\n\n"
                        analysis_content += "🤖 AI分析结果\n"
                        analysis_content += f"{'='*80}\n\n"
                        if ai_result:
                            analysis_content += ai_result
                        else:
                            analysis_content += "AI分析失败,请检查配置。"
                        analysis_content += f"\n\n{'='*80}\n\n"
                        analysis_content += "原始内容摘要\n"
                        analysis_content += f"{'='*80}\n\n"
                        # 添加内容摘要
                        for i, (_, name) in enumerate(selected_crawlers, 1):
                            if i <= len(all_crawled_content):
                                preview = all_crawled_content[i-1][:200] + "..." if len(all_crawled_content[i-1]) > 200 else all_crawled_content[i-1]
                                analysis_content += f"{i}. {name}:\n{preview}\n\n"
                        result_widget.insert(tk.END, analysis_content)
                        result_widget.see(tk.END)
                    self.root.after(0, show_analysis_result)
                    self.root.after(0, lambda: result_widget.insert(tk.END, "\n✅ 一键爬取和分析完成!\n"))
                    self.root.after(0, lambda: result_widget.see(tk.END))
                except Exception as e:
                    self.root.after(0, lambda e=str(e): result_widget.insert(tk.END, f"❌ AI分析失败: {e}\n"))
                    self.root.after(0, lambda e=e: result_widget.see(tk.END))
            except Exception as e:
                result_widget = self.get_active_result_widget()
                if result_widget:
                    self.root.after(0, lambda e=str(e): result_widget.insert(tk.END, f"❌ 一键爬取失败: {e}\n"))
                    self.root.after(0, lambda: result_widget.see(tk.END))
            finally:
                self.batch_crawl_event.set()
        threading.Thread(target=batch_crawl_thread, daemon=True).start()

    def one_click_analyze_tabs(self):
        """对所有左侧标签页内容执行分析,生成右侧分析结果"""
        if not hasattr(self, "text_widgets") or not self.text_widgets:
            messagebox.showwarning("警告", "没有可分析的标签页内容")
            return
        texts_info = []
        for tab_info in self.text_widgets.values():
            widget = tab_info.get('widget')
            if widget:
                text = widget.get("1.0", tk.END).strip()
                if text:
                    texts_info.append({
                        "title": tab_info.get('title') or f"标签页{len(texts_info)+1}",
                        "text": text
                    })
        if not texts_info:
            messagebox.showwarning("警告", "所有标签页内容为空,无法分析")
            return
        result_widget = self.get_active_result_widget()
        if result_widget:
            result_widget.insert(tk.END, f"\n{'='*80}\n🚀 开始一键分析,共 {len(texts_info)} 个标签页\n{'='*80}\n")
            result_widget.see(tk.END)
        self.one_click_analyze_event.clear()
        def analyze_thread():
            combined_sections = []
            try:
                for idx, info in enumerate(texts_info, 1):
                    title = info['title']
                    text = info['text']
                    if result_widget:
                        result_widget.insert(tk.END, f"[{idx}/{len(texts_info)}] 正在分析:{title}\n")
                        result_widget.see(tk.END)
                    try:
                        analysis = analyze_stock_keywords_local(text)
                        result_tab_title = f"{title}_分析"
                        result_tab_id = self.create_result_tab(result_tab_title)
                        result_tab_widget = self.result_tabs[result_tab_id]['widget']
                        result_tab_widget.delete("1.0", tk.END)
                        # 不再单独显示"分析来源",仅保留分析时间等信息
                        result_tab_widget.insert("1.0", f"分析时间:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        result_tab_widget.insert(tk.END, f"{'='*80}\n\n")
                        result_tab_widget.insert(tk.END, analysis)
                        result_tab_widget.insert(tk.END, f"\n\n{'='*80}\n")
                        result_tab_widget.see("1.0")
                        section = f"\n{'='*60}\n{analysis}\n"
                        combined_sections.append(section)
                        if result_widget:
                            result_widget.insert(tk.END, section)
                            result_widget.see(tk.END)
                    except Exception as err:
                        if result_widget:
                            result_widget.insert(tk.END, f"❌ 分析 {title} 失败: {err}\n")
                            result_widget.see(tk.END)
                        continue
                if combined_sections:
                    if result_widget:
                        result_widget.insert(tk.END, "\n✅ 一键分析完成!\n")
                        result_widget.see(tk.END)
                    messagebox.showinfo("成功", "一键分析完成")
                else:
                    messagebox.showwarning("警告", "一键分析未生成有效结果")
            except Exception as exc:
                messagebox.showerror("错误", f"一键分析失败: {exc}")
            finally:
                self.one_click_analyze_event.set()
        threading.Thread(target=analyze_thread, daemon=True).start()

    def save_ocr_to_analysis(self):
        """将OCR识别结果保存到分析标签页"""
        try:
            ocr_text = self.ocr_tab_widget.get("1.0", tk.END).strip()
            if not ocr_text:
                messagebox.showwarning("警告", "OCR识别器中没有内容可保存")
                return
            # 将内容添加到分析标签页
            self.analysis_tab_widget.insert(tk.END, f"\n{'='*80}\n")
            self.analysis_tab_widget.insert(tk.END, f"OCR识别结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.analysis_tab_widget.insert(tk.END, f"{'='*80}\n\n")
            self.analysis_tab_widget.insert(tk.END, ocr_text)
            self.analysis_tab_widget.insert(tk.END, "\n\n")
            self.analysis_tab_widget.see(tk.END)
            messagebox.showinfo("成功", "OCR识别结果已保存到分析标签页")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e!s}")

    def update_analysis_result(self, result):
        """更新分析结果并保存用于导出"""
        self.last_analysis_result = result
        result_widget = self.get_active_result_widget()
        if result_widget:
            result_widget.delete("1.0", tk.END)
            self.insert_colored_result(result)

    def analyze_and_generate(self):
        """同时分析文本并生成词云(处理所有标签页)"""
        # 仅使用当前活动左侧标签页文本
        combined_text = self.get_current_text()
        if not combined_text or not combined_text.strip():
            messagebox.showwarning("警告", "请输入文本内容")
            return
        # 获取标签页名称和时间
        tab_name = self.get_active_text_title()
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 在后台线程中运行分析和词云生成
        def run_analysis_and_wordcloud():
            try:
                # 同时进行文本分析和词云生成
                result = analyze_stock_keywords_local(combined_text)
                # 情绪指标更新(基于多维度文本分析)
                try:
                    dimension_analysis = analyze_text_dimensions(combined_text)
                    if dimension_analysis and hasattr(self, 'root') and self.root.winfo_exists():
                        sentiment_val = dimension_analysis.get('sentiment', '中性')
                        self.root.after(0, lambda: self.update_sentiment_indicator(sentiment_val))
                except Exception:
                    pass
                generate_wordcloud(combined_text, self.wordcloud_callback, tab_name=tab_name, time_str=time_str)
                # 更新分析结果
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after(0, lambda: self.update_analysis_result(result))
                    self.root.after(0, lambda: messagebox.showinfo("成功", "分析完成,词云生成中..."))
            except Exception as e:
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after(0, lambda e=e: messagebox.showerror("错误", f"分析失败: {e}"))
        analysis_thread = threading.Thread(target=run_analysis_and_wordcloud, daemon=True)
        analysis_thread.start()

    def analyze_text(self):
        """分析文本"""
        text = self.get_current_text()
        if not text:
            messagebox.showwarning("警告", "请输入文本内容")
            return
        # 在后台线程中运行分析
        def run_analysis():
            try:
                result = analyze_stock_keywords_local(text)
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after(0, lambda: self.update_result_text(result))
                    self.root.after(0, lambda: messagebox.showinfo("成功", "分析完成"))
            except Exception as e:
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after(0, lambda e=e: messagebox.showerror("错误", f"分析失败: {e}"))
        analysis_thread = threading.Thread(target=run_analysis, daemon=True)
        analysis_thread.start()

    def save_analyzed_stocks(self):
        """保存分析出来的股票(含逻辑和日期等字段)"""
        try:
            # 获取当前分析结果
            result_widget = self.get_active_result_widget()
            if not result_widget:
                messagebox.showwarning("警告", "请先进行分析")
                return
            result_text = result_widget.get("1.0", tk.END).strip()
            if not result_text:
                messagebox.showwarning("警告", "没有分析结果可保存")
                return
            # 从分析结果中提取股票信息(包含逻辑)
            import re
            stocks_data = []
            # 提取股票代码和名称
            stock_pattern = r'(\d{6})[::]\s*([^\n]+)'
            matches = re.findall(stock_pattern, result_text)
            # 提取每只股票的逻辑(从分析结果中查找)
            lines = result_text.split('\n')
            current_stock = None
            current_logic = []
            for i, line in enumerate(lines):
                line = line.strip()
                # 检查是否是股票行
                stock_match = re.search(r'(\d{6})[::]\s*([^\n]+)', line)
                if stock_match:
                    # 保存上一只股票的逻辑
                    if current_stock:
                        stocks_data.append({
                            'code': current_stock['code'],
                            'name': current_stock['name'],
                            'logic': '\n'.join(current_logic).strip(),
                            'date': datetime.now().strftime('%Y-%m-%d')
                        })
                    # 开始新股票
                    current_stock = {
                        'code': stock_match.group(1),
                        'name': stock_match.group(2).split()[0] if stock_match.group(2) else ''
                    }
                    current_logic = []
                elif current_stock and line:
                    # 收集逻辑信息(排除明显的标题行)
                    if not re.match(r'^[=#\-\s]+$', line) and len(line) > 5:
                        current_logic.append(line)
            # 保存最后一只股票
            if current_stock:
                stocks_data.append({
                    'code': current_stock['code'],
                    'name': current_stock['name'],
                    'logic': '\n'.join(current_logic).strip(),
                    'date': datetime.now().strftime('%Y-%m-%d')
                })
            # 如果没有从分析结果中提取到,尝试从文本中提取
            if not stocks_data and matches:
                for match in matches:
                    stock_code = match[0]
                    stock_name = match[1].split()[0] if match[1] else ""
                    # 尝试查找该股票的逻辑(在分析结果中搜索)
                    logic_lines = []
                    for line in lines:
                        if stock_code in line or stock_name in line:
                            if len(line.strip()) > 10 and not re.match(r'^[=#\-\s]+$', line.strip()):
                                logic_lines.append(line.strip())
                    stocks_data.append({
                        'code': stock_code,
                        'name': stock_name,
                        'logic': '\n'.join(logic_lines[:5]).strip() or "无详细逻辑",
                        'date': datetime.now().strftime('%Y-%m-%d')
                    })
            if not stocks_data:
                messagebox.showwarning("警告", "未找到股票信息")
                return
            # 显示保存对话框
            save_window = self._toplevel(self.root)
            save_window.title("保存分析股票")
            save_window.geometry("700x500")
            # 创建表格显示要保存的数据
            tree_frame = ttk.Frame(save_window)
            tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            # 创建Treeview
            columns = ("股票代码", "股票名称", "逻辑", "日期")
            tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
            for col in columns:
                tree.heading(col, text=col)
                if col == "逻辑":
                    tree.column(col, width=300)
                else:
                    tree.column(col, width=100)
            # 填充数据
            for stock in stocks_data:
                logic_text = stock['logic'][:100] + '...' if len(stock['logic']) > 100 else stock['logic']
                tree.insert("", tk.END, values=(
                    stock['code'],
                    stock['name'],
                    logic_text,
                    stock['date']
                ))
            # 滚动条
            scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            # 备注选择(根据当前标签页名称判断来源)
            remark_frame = ttk.Frame(save_window)
            remark_frame.pack(fill=tk.X, padx=10, pady=5)
            ttk.Label(remark_frame, text="备注:").pack(side=tk.LEFT, padx=(0, 5))
            remark_var = tk.StringVar(value="")
            remark_combo = ttk.Combobox(remark_frame, textvariable=remark_var,
                                       values=["聊天", "强势股", "韭研", "淘股吧", "文本分析", ""],
                                       width=15, state="readonly")
            remark_combo.pack(side=tk.LEFT, padx=5)
            # 根据当前标签页名称自动设置备注
            try:
                active_tab_title = self.get_active_text_title() or ""
                if "聊天" in active_tab_title or "chat" in active_tab_title.lower():
                    remark_var.set("聊天")
                elif "强势" in active_tab_title or "strong" in active_tab_title.lower():
                    remark_var.set("强势股")
                elif "韭研" in active_tab_title or "jiuyan" in active_tab_title.lower():
                    remark_var.set("韭研")
                elif "淘股吧" in active_tab_title or "taoguba" in active_tab_title.lower():
                    remark_var.set("淘股吧")
                else:
                    remark_var.set("文本分析")
            except:
                pass
            # 保存按钮
            def save_to_db():
                try:
                    saved_count = 0
                    for stock in stocks_data:
                        if save_stock_logic_to_db(
                            stock_name=stock['name'],
                            logic=stock['logic'],
                            date=stock['date'],
                            source="分析结果"
                        ):
                            saved_count += 1
                    messagebox.showinfo("成功", f"成功保存 {saved_count} 条股票数据到数据库")
                    save_window.destroy()
                except Exception as e:
                    messagebox.showerror("错误", f"保存失败: {e}")
            # 导入到自选股
            def import_to_managed_stocks():
                try:
                    remark_value = remark_var.get().strip()
                    added_count = 0
                    for stock in stocks_data:
                        if stock.get('name'):
                            # 调用自选股管理界面的添加函数
                            if hasattr(self, 'managed_stocks'):
                                # 直接添加到自选股列表
                                added_at = datetime.now().strftime("%Y-%m-%d %H:%M")
                                entry = {
                                    "name": stock['name'],
                                    "code": stock.get('code', ''),
                                    "source": "分析结果",
                                    "added_at": added_at,
                                    "remark": remark_value
                                }
                                # 检查是否已存在
                                exists = False
                                for existing in self.managed_stocks:
                                    if existing.get("name") == stock['name'] or (stock.get('code') and existing.get("code") == stock['code']):
                                        existing.update(entry)
                                        exists = True
                                        break
                                if not exists:
                                    self.managed_stocks.append(entry)
                                    if len(self.managed_stocks) > 100:
                                        self.managed_stocks = self.managed_stocks[-100:]
                                added_count += 1
                    if added_count > 0:
                        self._save_managed_stocks_to_file()
                        messagebox.showinfo("成功", f"成功导入 {added_count} 只股票到自选股管理列表(备注:{remark_value if remark_value else '无'})")
                    else:
                        messagebox.showwarning("警告", "没有可导入的股票")
                except Exception as e:
                    messagebox.showerror("错误", f"导入失败: {e}")
            button_frame = ttk.Frame(save_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)
            ttk.Button(button_frame, text="保存到数据库", command=save_to_db).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="导入到自选股", command=import_to_managed_stocks).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="取消", command=save_window.destroy).pack(side=tk.LEFT, padx=5)
        except Exception as e:
            messagebox.showerror("错误", f"保存分析股票失败: {e}")

    def run_ai_analysis(self):
        """运行AI分析"""
        # 仅获取当前活动左侧标签页文本
        combined_text = self.get_current_text()
        if not combined_text or not combined_text.strip():
            messagebox.showwarning("警告", "请输入文本内容")
            return
        # 在后台线程中运行AI分析
        def run_ai():
            try:
                # 先进行多维度文本分析
                dimension_analysis = analyze_text_dimensions(combined_text)
                # 更新情绪指标
                try:
                    if dimension_analysis and hasattr(self, 'root') and self.root.winfo_exists():
                        sentiment_val = dimension_analysis.get('sentiment', '中性')
                        self.root.after(0, lambda: self.update_sentiment_indicator(sentiment_val))
                except Exception:
                    pass
                # 构建AI提示词
                system_prompt = "你是一个专业的股票市场分析师,擅长分析市场情绪、识别投资机会和风险。"
                user_prompt = f"""请分析以下股票相关文本内容,并提供专业的市场洞察:
文本内容:
{combined_text[:2000]}  # 限制长度避免超出token限制
"""
                # 如果有多维度分析结果,添加到提示词
                if dimension_analysis:
                    user_prompt += f"""
已有分析结果:
- 情绪倾向:{dimension_analysis.get('sentiment', '未知')}
- 市场焦点:{'是' if dimension_analysis.get('market_focus') else '否'}
- 风险等级:{dimension_analysis.get('risk_level', '未知')}
- 市场状况:{dimension_analysis.get('market_status', '未知')}
- 热门主题:{', '.join([t[0] for t in dimension_analysis.get('hot_themes', [])])}
请基于以上信息,提供:
1. 市场情绪分析
2. 投资机会识别
3. 风险提示
4. 操作建议
"""
                # 调用AI模型
                ai_result = self.call_ai_model(user_prompt, system_prompt, config_override=None)
                # 更新分析结果
                if hasattr(self, 'root') and self.root.winfo_exists():
                    if ai_result:
                        # 整合多维度分析和AI分析结果
                        final_result = "🤖 **AI分析结果**\n"
                        final_result += f"{'='*80}\n\n"
                        final_result += ai_result
                        final_result += f"\n\n{'='*80}\n"
                        final_result += "\n📊 **多维度文本分析结果**\n"
                        final_result += f"{'='*80}\n"
                        if dimension_analysis:
                            final_result += f"😊 情绪倾向:{dimension_analysis.get('sentiment', '未知')}\n"
                            final_result += f"🎯 市场焦点:{'是' if dimension_analysis.get('market_focus') else '否'}\n"
                            final_result += f"⚠️ 风险等级:{dimension_analysis.get('risk_level', '未知')}\n"
                            final_result += f"📈 市场状况:{dimension_analysis.get('market_status', '未知')}\n"
                        self.root.after(0, lambda: self.append_ai_analysis(final_result))
                        self.root.after(0, lambda: messagebox.showinfo("成功", "AI分析完成"))
                    else:
                        self.root.after(0, lambda: messagebox.showerror("错误", "AI分析失败,请检查配置"))
            except Exception as e:
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after(0, lambda e=e: messagebox.showerror("错误", f"AI分析失败: {e}"))
        ai_thread = threading.Thread(target=run_ai, daemon=True)
        ai_thread.start()

    def append_ai_analysis(self, content):
        """显示AI分析结果(在新标签页)"""
        try:
            # 以左侧活动标签页前五个字命名
            src_title = self.get_active_text_title()
            prefix = (src_title or "未命名")[:5]
            tab_title = f"{prefix}分析"
            tab_id = self.create_result_tab(tab_title)
            result_widget = self.result_tabs[tab_id]['widget']
            if result_widget:
                result_widget.insert("1.0", content)
                result_widget.see(tk.END)
        except Exception as e:
            print(f"显示AI分析结果失败: {e}")

    def show_consultation_analysis(self):
        """打开咨询分析界面"""
        try:
            # 尝试直接导入consulting_analysis_gui模块(支持打包后的环境)
            try:
                # 1. 尝试使用 PyInstaller 打包后的路径(sys._MEIPASS)
                if hasattr(sys, '_MEIPASS'):
                    meipass_path = os.path.join(sys._MEIPASS, "consulting_analysis_gui.py")
                    if os.path.exists(meipass_path) and os.path.dirname(meipass_path) not in sys.path:
                        sys.path.insert(0, os.path.dirname(meipass_path))
                # 2. 尝试可执行文件所在目录的 _internal 子目录
                if hasattr(sys, 'frozen'):
                    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                    internal_dir = os.path.join(exe_dir, '_internal')
                    if os.path.exists(internal_dir) and internal_dir not in sys.path:
                        sys.path.insert(0, internal_dir)
                # 3. 尝试与主程序同目录
                current_dir = os.path.dirname(os.path.abspath(__file__))
                if current_dir not in sys.path:
                    sys.path.insert(0, current_dir)
                import consulting_analysis_gui
            except ImportError as e:
                error_msg = f"无法导入咨询分析模块: {e}\n\n"
                error_msg += "请确保consulting_analysis_gui.py文件已正确打包或存在于程序目录中。"
                messagebox.showerror("错误", error_msg)
                return
            # 创建咨询分析窗口
            consultation_window = self._toplevel(self.root)
            consultation_window.transient(self.root)  # 设置为父窗口的临时窗口
            # 创建咨询分析应用实例(传入Toplevel窗口和主界面的AI功能)
            # ConsultingAnalysisApp会在__init__中设置title和geometry
            try:
                # 传递主界面的AI配置和AI分析方法
                consulting_analysis_gui.ConsultingAnalysisApp(
                    consultation_window,
                    ai_call_func=self.call_ai_model,
                    ai_config_manager=self.ai_config_manager
                )
                # 确保窗口正确显示
                consultation_window.update()
            except Exception as e:
                error_msg = str(e)
                messagebox.showerror("错误", f"创建咨询分析界面失败: {error_msg}")
                try:
                    consultation_window.destroy()
                except:
                    pass
                import traceback
                traceback.print_exc()
                return
        except Exception as e:
            messagebox.showerror("错误", f"打开咨询分析界面失败: {e}")
            import traceback
            traceback.print_exc()

    def show_investment_analysis(self):
        """打开投资分析界面"""
        try:
            win = self._toplevel(self.root)
            win.title("投资分析工作台")
            win.geometry("1200x720")
            win.transient(self.root)
            # 投资选项
            investment_options = {
                "股票": "股票投资分析,包括个股选择、行业分析、技术面、基本面等",
                "房地产": "房地产投资分析,包括住宅、商业地产、REITs等投资机会",
                "债券": "债券投资分析,包括国债、企业债、可转债等固定收益产品",
                "数字货币": "数字货币投资分析,包括比特币、以太坊等加密货币",
                "基金": "基金投资分析,包括股票基金、债券基金、混合基金、ETF等",
                "期货": "期货投资分析,包括商品期货、金融期货等衍生品",
                "外汇": "外汇投资分析,包括主要货币对、汇率走势等",
                "黄金": "黄金投资分析,包括实物黄金、黄金ETF、黄金期货等",
                "大宗商品": "大宗商品投资分析,包括原油、铜、农产品等",
                "另类投资": "另类投资分析,包括私募股权、对冲基金、艺术品等"
            }
            self._create_analysis_window(
                win,
                "请输入您的投资问题或需求,选择投资类型进行分析",
                investment_options,
                "投资类型",
                self._get_investment_prompt,
                "你是一位资深的投资分析专家,能够提供专业的投资建议和分析。"
            )
        except Exception as e:
            messagebox.showerror("错误", f"打开投资分析界面失败: {e}")
            import traceback
            traceback.print_exc()

    def show_gambling_analysis(self):
        """打开赌博/概率分析界面"""
        try:
            win = self._toplevel(self.root)
            win.title("概率与仓位分析工作台")
            win.geometry("1200x720")
            win.transient(self.root)
            # 赌博/概率分析选项
            gambling_options = {
                "凯利公式": "凯利公式用于计算最优投注比例,基于胜率和赔率",
                "概率计算": "计算各种概率场景,包括胜率、赔率、期望值等",
                "风险收益比": "计算风险收益比,评估投资机会的风险调整后收益",
                "仓位管理": "基于概率和风险的资金管理策略,包括固定比例、动态调整等",
                "期望值分析": "计算投资的期望值,评估长期收益预期",
                "最大回撤": "分析最大回撤风险,评估资金管理的安全性",
                "夏普比率": "计算风险调整后的收益指标,评估投资效率",
                "蒙特卡洛模拟": "使用蒙特卡洛方法模拟投资结果,评估概率分布",
                "VaR风险值": "计算在险价值,评估投资组合的风险敞口",
                "压力测试": "进行压力测试,评估极端情况下的投资表现"
            }
            self._create_analysis_window(
                win,
                "请输入概率和风险相关的问题,选择分析工具进行计算",
                gambling_options,
                "分析工具",
                self._get_gambling_prompt,
                "你是一位概率和风险管理专家,精通各种概率计算、风险分析和仓位管理方法。"
            )
        except Exception as e:
            messagebox.showerror("错误", f"打开概率分析界面失败: {e}")
            import traceback
            traceback.print_exc()

    def show_delivery_analysis(self):
        """打开图文分析界面(支持文本和图片)"""
        try:
            win = self._toplevel(self.root)
            win.title("图文分析")
            win.geometry("1400x800")
            win.transient(self.root)
            win.resizable(True, True)
            # 主容器框架
            main_container = ttk.Frame(win, padding=10)
            main_container.pack(fill=tk.BOTH, expand=True)
            # 创建左右分栏
            paned = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
            paned.pack(fill=tk.BOTH, expand=True)
            # 左侧:数据输入区域
            left_pane = ttk.LabelFrame(paned, text="数据输入(支持文本和图片)", padding=10)
            paned.add(left_pane, weight=1)
            # 导入按钮
            import_frame = ttk.Frame(left_pane)
            import_frame.pack(fill=tk.X, pady=(0, 10))
            # 存储当前文件路径和类型
            current_file_path = [None]  # 使用列表以便在嵌套函数中修改
            current_file_type = [None]  # 'text' 或 'image'
            def import_delivery_file():
                """导入文件(支持文本和图片)"""
                file_path = filedialog.askopenfilename(
                    title="选择文件(文本或图片)",
                    filetypes=[
                        ("文本文件", "*.txt"),
                        ("CSV文件", "*.csv"),
                        ("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif"),
                        ("所有文件", "*.*")
                    ]
                )
                if file_path:
                    try:
                        # 判断文件类型
                        file_ext = os.path.splitext(file_path)[1].lower()
                        image_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
                        if file_ext in image_exts:
                            # 图片文件
                            current_file_path[0] = file_path
                            current_file_type[0] = 'image'
                            # 显示图片预览
                            try:
                                img = Image.open(file_path)
                                # 调整图片大小以适应显示区域
                                max_width = 600
                                max_height = 400
                                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                                photo = ImageTk.PhotoImage(img)
                                # 清空文本框并显示图片
                                delivery_text.delete("1.0", tk.END)
                                delivery_text.image_create("1.0", image=photo)
                                delivery_text.image = photo  # 保持引用
                                delivery_text.insert("1.0", f"\n\n已导入图片: {os.path.basename(file_path)}\n")
                                messagebox.showinfo("成功", "图片导入成功,点击开始分析将使用AI进行图片识别和分析")
                            except Exception as e:
                                messagebox.showerror("错误", f"加载图片失败: {e}")
                        else:
                            # 文本文件
                            current_file_path[0] = file_path
                            current_file_type[0] = 'text'
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        delivery_text.delete("1.0", tk.END)
                        delivery_text.insert("1.0", content)
                        messagebox.showinfo("成功", "文件导入成功")
                    except Exception as e:
                        messagebox.showerror("错误", f"导入文件失败: {e}")
            ttk.Button(import_frame, text="导入文件", command=import_delivery_file).pack(side=tk.LEFT, padx=(0, 5))
            def clear_delivery_text():
                """清空输入框"""
                delivery_text.delete("1.0", tk.END)
                current_file_path[0] = None
                current_file_type[0] = None
            ttk.Button(import_frame, text="清空", command=clear_delivery_text).pack(side=tk.LEFT)
            # 提示标签
            ttk.Label(left_pane, text="请粘贴文本、导入文本文件或导入图片文件:", font=("TkDefaultFont", 11)).pack(anchor=tk.W, pady=(0, 5))
            # 数据输入文本框(支持文本和图片预览)
            delivery_text = scrolledtext.ScrolledText(left_pane, height=30, wrap=tk.WORD, font=("Courier", 11))
            delivery_text.pack(fill=tk.BOTH, expand=True)
            # 右侧:分析结果区域
            right_pane = ttk.LabelFrame(paned, text="分析结果", padding=10)
            paned.add(right_pane, weight=1)
            # AI设置区域
            ai_config_frame = ttk.LabelFrame(right_pane, text="AI设置", padding=5)
            ai_config_frame.pack(fill=tk.X, pady=(0, 10))
            # 存储AI配置(使用列表以便在嵌套函数中修改)
            ai_config_local = {
                "provider": tk.StringVar(value="deepseek"),
                "api_key": tk.StringVar(value=""),
                "base_url": tk.StringVar(value=""),
                "model": tk.StringVar(value=""),
                "endpoint": tk.StringVar(value="/chat/completions")
            }
            # 从全局配置加载默认值
            try:
                active_provider = self.ai_config_manager.config.get("active_provider", "deepseek")
                provider_config = self.ai_config_manager.config.get("providers", {}).get(active_provider, {})
                ai_config_local["provider"].set(active_provider)
                ai_config_local["api_key"].set(provider_config.get("api_key", ""))
                ai_config_local["base_url"].set(provider_config.get("base_url", ""))
                ai_config_local["model"].set(provider_config.get("model", ""))
                ai_config_local["endpoint"].set(provider_config.get("endpoint", "/chat/completions"))
            except:
                pass
            # 提供商选择
            provider_row = ttk.Frame(ai_config_frame)
            provider_row.pack(fill=tk.X, pady=2)
            ttk.Label(provider_row, text="AI提供商:", width=10).pack(side=tk.LEFT, padx=2)
            provider_combo = ttk.Combobox(provider_row, textvariable=ai_config_local["provider"],
                                         values=["deepseek", "doubao", "ollama", "chatbox"],
                                         state="readonly", width=15)
            provider_combo.pack(side=tk.LEFT, padx=2)
            def update_provider_config(*args):
                """更新提供商配置"""
                provider = ai_config_local["provider"].get()
                provider_config = self.ai_config_manager.config.get("providers", {}).get(provider, {})
                if provider_config:
                    ai_config_local["api_key"].set(provider_config.get("api_key", ""))
                    ai_config_local["base_url"].set(provider_config.get("base_url", ""))
                    ai_config_local["model"].set(provider_config.get("model", ""))
                    ai_config_local["endpoint"].set(provider_config.get("endpoint", "/chat/completions"))
                else:
                    # 设置默认值
                    defaults = {
                        "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "endpoint": "/chat/completions"},
                        "doubao": {"base_url": "https://ark.cn-beijing.volces.com", "model": "doubao-seedance-1-0-pro-250528", "endpoint": "/api/v3/chat/completions"},
                        "ollama": {"base_url": "http://localhost:11434", "model": "qwen2.5:7b", "endpoint": "/v1/chat/completions"},
                        "chatbox": {"base_url": "http://localhost:1234", "model": "chatbox", "endpoint": "/v1/chat/completions"}
                    }
                    default = defaults.get(provider, {})
                    ai_config_local["base_url"].set(default.get("base_url", ""))
                    ai_config_local["model"].set(default.get("model", ""))
                    ai_config_local["endpoint"].set(default.get("endpoint", "/chat/completions"))
            provider_combo.bind("<<ComboboxSelected>>", update_provider_config)
            # API Key
            api_key_row = ttk.Frame(ai_config_frame)
            api_key_row.pack(fill=tk.X, pady=2)
            ttk.Label(api_key_row, text="API Key:", width=10).pack(side=tk.LEFT, padx=2)
            api_key_entry = ttk.Entry(api_key_row, textvariable=ai_config_local["api_key"], width=40, show="*")
            api_key_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            # Base URL
            base_url_row = ttk.Frame(ai_config_frame)
            base_url_row.pack(fill=tk.X, pady=2)
            ttk.Label(base_url_row, text="Base URL:", width=10).pack(side=tk.LEFT, padx=2)
            base_url_entry = ttk.Entry(base_url_row, textvariable=ai_config_local["base_url"], width=40)
            base_url_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            # Model
            model_row = ttk.Frame(ai_config_frame)
            model_row.pack(fill=tk.X, pady=2)
            ttk.Label(model_row, text="Model:", width=10).pack(side=tk.LEFT, padx=2)
            model_entry = ttk.Entry(model_row, textvariable=ai_config_local["model"], width=40)
            model_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            # Endpoint
            endpoint_row = ttk.Frame(ai_config_frame)
            endpoint_row.pack(fill=tk.X, pady=2)
            ttk.Label(endpoint_row, text="Endpoint:", width=10).pack(side=tk.LEFT, padx=2)
            endpoint_entry = ttk.Entry(endpoint_row, textvariable=ai_config_local["endpoint"], width=40)
            endpoint_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            # 保存设置按钮
            def save_ai_config():
                """保存AI配置到全局配置"""
                try:
                    provider = ai_config_local["provider"].get()
                    # 更新全局配置
                    if "providers" not in self.ai_config_manager.config:
                        self.ai_config_manager.config["providers"] = {}
                    if provider not in self.ai_config_manager.config["providers"]:
                        self.ai_config_manager.config["providers"][provider] = {}
                    self.ai_config_manager.config["providers"][provider]["api_key"] = ai_config_local["api_key"].get()
                    self.ai_config_manager.config["providers"][provider]["base_url"] = ai_config_local["base_url"].get()
                    self.ai_config_manager.config["providers"][provider]["model"] = ai_config_local["model"].get()
                    self.ai_config_manager.config["providers"][provider]["endpoint"] = ai_config_local["endpoint"].get()
                    self.ai_config_manager.config["active_provider"] = provider
                    self.ai_config_manager.save_config()
                    messagebox.showinfo("成功", f"AI配置已保存({provider})")
                except Exception as e:
                    messagebox.showerror("错误", f"保存配置失败: {e}")
            config_btn_row = ttk.Frame(ai_config_frame)
            config_btn_row.pack(fill=tk.X, pady=2)
            ttk.Button(config_btn_row, text="保存设置", command=save_ai_config, width=12).pack(side=tk.LEFT, padx=2)
            ttk.Button(config_btn_row, text="从全局加载", command=update_provider_config, width=12).pack(side=tk.LEFT, padx=2)
            # 分析按钮
            analyze_frame = ttk.Frame(right_pane)
            analyze_frame.pack(fill=tk.X, pady=(0, 10))
            def analyze_delivery():
                """分析数据(支持文本和图片)"""
                # 获取文本框内容
                delivery_data = delivery_text.get("1.0", tk.END).strip()
                # 判断是图片分析还是文本分析
                # 优先检查是否有图片文件且文本框内容为空或只有图片提示信息
                is_image_analysis = (
                    current_file_type[0] == 'image' and
                    current_file_path[0] and
                    (not delivery_data or
                     delivery_data.startswith("已导入图片:") or
                     len(delivery_data) < 50)  # 如果内容很少,可能是图片提示信息
                )
                if is_image_analysis:
                    # 图片分析
                    try:
                        result_text.config(state=tk.NORMAL)
                        result_text.delete("1.0", tk.END)
                        result_text.insert("1.0", "正在使用AI分析图片,请稍候...\n")
                        result_text.config(state=tk.DISABLED)
                        win.update()
                        # 构建自定义AI配置
                        custom_config = {
                            "api_key": ai_config_local["api_key"].get(),
                            "base_url": ai_config_local["base_url"].get(),
                            "model": ai_config_local["model"].get(),
                            "endpoint": ai_config_local["endpoint"].get(),
                            "temperature": 0.3,
                            "timeout": 120
                        }
                        provider = ai_config_local["provider"].get()
                        # 使用AI分析图片(使用自定义配置)
                        analysis_result = self._analyze_image_with_ai(
                            current_file_path[0],
                            custom_config=custom_config,
                            custom_provider=provider
                        )
                        result_text.config(state=tk.NORMAL)
                        result_text.delete("1.0", tk.END)
                        result_text.insert("1.0", analysis_result)
                        result_text.config(state=tk.DISABLED)
                    except Exception as e:
                        messagebox.showerror("错误", f"图片分析失败: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    # 文本分析
                    if not delivery_data or delivery_data == "":
                        messagebox.showwarning("警告", "请先输入或导入数据(文本或图片)")
                    return
                # 解析交割单数据
                try:
                    analysis_result = self._parse_and_analyze_delivery(delivery_data)
                    result_text.config(state=tk.NORMAL)
                    result_text.delete("1.0", tk.END)
                    result_text.insert("1.0", analysis_result)
                    result_text.config(state=tk.DISABLED)
                except Exception as e:
                    messagebox.showerror("错误", f"分析失败: {e}")
                    import traceback
                    traceback.print_exc()
            ttk.Button(analyze_frame, text="开始分析", command=analyze_delivery, width=15).pack(side=tk.LEFT, padx=(0, 5))
            def export_result():
                """导出分析结果"""
                result = result_text.get("1.0", tk.END).strip()
                if not result:
                    messagebox.showwarning("警告", "没有可导出的分析结果")
                    return
                file_path = filedialog.asksaveasfilename(
                    title="保存分析结果",
                    defaultextension=".txt",
                    filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
                )
                if file_path:
                    try:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(result)
                        messagebox.showinfo("成功", "分析结果已保存")
                    except Exception as e:
                        messagebox.showerror("错误", f"保存失败: {e}")
            ttk.Button(analyze_frame, text="导出结果", command=export_result, width=15).pack(side=tk.LEFT)
            # 分析结果文本框
            result_text = scrolledtext.ScrolledText(right_pane, height=30, wrap=tk.WORD, font=("Microsoft YaHei", 12), state=tk.DISABLED)
            result_text.pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            messagebox.showerror("错误", f"打开交割单分析界面失败: {e}")
            import traceback
            traceback.print_exc()

    def _parse_and_analyze_delivery(self, delivery_data):
        """解析并分析交割单数据"""
        try:
            # 解析交割单数据
            transactions = self._parse_delivery_data(delivery_data)
            if not transactions:
                return "未能解析到有效的交易数据,请检查数据格式。\n\n同花顺交割单通常包含以下信息:\n- 交易日期\n- 股票代码/名称\n- 买卖方向\n- 成交价格\n- 成交数量\n- 成交金额\n- 手续费等"
            # 生成分析报告
            analysis = self._generate_delivery_analysis(transactions)
            # 使用AI进行深度分析
            ai_analysis = self._get_ai_delivery_analysis(transactions, analysis)
            # 组合分析结果
            result = "=" * 80 + "\n"
            result += "交割单分析报告\n"
            result += "=" * 80 + "\n\n"
            result += analysis + "\n\n"
            result += "=" * 80 + "\n"
            result += "AI深度分析\n"
            result += "=" * 80 + "\n\n"
            result += ai_analysis
            return result
        except Exception as e:
            return f"分析过程中发生错误: {e!s}\n\n请检查数据格式是否正确。"

    def _generate_delivery_analysis(self, transactions):
        """生成交割单分析报告"""
        if not transactions:
            return "没有有效的交易数据"
        analysis = ""
        # 统计基本信息
        buy_count = sum(1 for t in transactions if t.get('direction') == '买入')
        sell_count = sum(1 for t in transactions if t.get('direction') == '卖出')
        total_count = len(transactions)
        # 统计股票
        stocks = {}
        for t in transactions:
            stock_name = t.get('name', t.get('code', '未知'))
            if stock_name not in stocks:
                stocks[stock_name] = {'buy': 0, 'sell': 0, 'buy_amount': 0, 'sell_amount': 0}
            direction = t.get('direction', '')
            price = t.get('price', 0)
            quantity = t.get('quantity', 0)
            amount = price * quantity
            if direction == '买入':
                stocks[stock_name]['buy'] += quantity
                stocks[stock_name]['buy_amount'] += amount
            elif direction == '卖出':
                stocks[stock_name]['sell'] += quantity
                stocks[stock_name]['sell_amount'] += amount
        # 生成报告
        analysis += "交易统计\n"
        analysis += "-" * 40 + "\n"
        analysis += f"总交易笔数: {total_count}\n"
        analysis += f"买入笔数: {buy_count}\n"
        analysis += f"卖出笔数: {sell_count}\n"
        analysis += f"涉及股票数: {len(stocks)}\n\n"
        analysis += "股票交易明细\n"
        analysis += "-" * 40 + "\n"
        for stock_name, data in stocks.items():
            analysis += f"\n{stock_name}:\n"
            if data['buy'] > 0:
                avg_buy_price = data['buy_amount'] / data['buy'] if data['buy'] > 0 else 0
                analysis += f"  买入: {data['buy']}股, 平均价格: {avg_buy_price:.2f}元, 总金额: {data['buy_amount']:.2f}元\n"
            if data['sell'] > 0:
                avg_sell_price = data['sell_amount'] / data['sell'] if data['sell'] > 0 else 0
                analysis += f"  卖出: {data['sell']}股, 平均价格: {avg_sell_price:.2f}元, 总金额: {data['sell_amount']:.2f}元\n"
            if data['buy'] > 0 and data['sell'] > 0:
                profit = data['sell_amount'] - data['buy_amount']
                profit_pct = (profit / data['buy_amount'] * 100) if data['buy_amount'] > 0 else 0
                analysis += f"  盈亏: {profit:.2f}元 ({profit_pct:+.2f}%)\n"
        return analysis

    def _get_ai_delivery_analysis(self, transactions, basic_analysis):
        """使用AI进行深度分析"""
        try:
            # 构建AI分析提示
            prompt = f"""请对以下交割单交易数据进行分析,并提供投资建议:
交易数据统计:
{basic_analysis}
请从以下角度进行分析:
1. 交易行为分析:交易频率、买卖比例、持仓结构等
2. 盈亏分析:整体盈亏情况、单只股票盈亏、盈亏原因
3. 交易策略评估:交易时机、仓位管理、风险控制等
4. 投资建议:基于交易数据,提供改进建议和投资策略优化建议
5. 风险提示:识别潜在风险和需要注意的问题
请提供详细、专业的分析和建议。"""
            system_prompt = "你是一位资深的股票交易分析专家,能够深入分析交易数据,识别交易模式,并提供专业的投资建议。"
            ai_result = self.call_ai_model(prompt, system_prompt)
            if not ai_result:
                return "AI分析暂时不可用,请检查AI配置。\n\n" + basic_analysis
            return ai_result
        except Exception as e:
            return f"AI分析失败: {e!s}\n\n" + basic_analysis

    def _analyze_image_with_ai(self, image_path, custom_config=None, custom_provider=None):
        """使用AI分析图片(优先使用豆包/火山引擎,失败则使用OCR+文本分析)
        Args:
            image_path: 图片路径
            custom_config: 自定义AI配置字典(可选)
            custom_provider: 自定义提供商名称(可选)
        """
        # 读取图片并转换为base64
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            return f"读取图片失败: {e!s}"
        # 获取图片格式
        try:
            img = Image.open(image_path)
            image_format = img.format.lower() if img.format else 'png'
            # 修正MIME类型
            mime_map = {
                'jpeg': 'jpeg',
                'jpg': 'jpeg',
                'png': 'png',
                'bmp': 'bmp',
                'gif': 'gif'
            }
            mime_format = mime_map.get(image_format, 'png')
            mime_type = f"image/{mime_format}"
        except Exception as e:
            return f"解析图片格式失败: {e!s}"
        # 构建提示词
        prompt = """请仔细分析这张图片中的内容。如果这是股票交割单、交易记录或财务报表,请:
1. 识别并提取所有交易数据(股票代码、名称、买卖方向、价格、数量、金额、日期等)
2. 分析交易行为(交易频率、买卖比例、持仓结构等)
3. 计算盈亏情况(整体盈亏、单只股票盈亏)
4. 评估交易策略(交易时机、仓位管理、风险控制等)
5. 提供投资建议和风险提示
如果图片内容不是交易相关,请详细描述图片内容并进行分析。
请提供详细、专业的分析报告。"""
        # 构建消息(支持图片的格式)
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_base64}"
                        }
                    }
                ]
            }
        ]
        # 如果提供了自定义配置,优先使用自定义配置
        if custom_config and custom_provider:
            if not custom_config.get("api_key"):
                return "错误: 未配置API密钥。请在AI设置中配置API Key。"
            try:
                result = self._try_image_analysis_with_provider(
                    custom_config, custom_provider, messages, mime_type
                )
                # 检查是否是因为API不支持图片格式而失败
                if result and (
                    "unknown variant" in result.lower() or
                    "image_url" in result.lower() or
                    ("API调用失败" in result and "400" in result) or
                    "invalid_request_error" in result.lower() or
                    "deserialize" in result.lower()
                ):
                    # API不支持图片,使用OCR回退方案
                    return self._analyze_image_with_ocr_fallback(image_path, custom_config, custom_provider)
                if result and not result.startswith("API调用失败") and not result.startswith("错误"):
                    return result
                else:
                    # 尝试OCR回退
                    return self._analyze_image_with_ocr_fallback(image_path, custom_config, custom_provider)
            except Exception as e:
                # 如果出错,尝试OCR回退
                try:
                    return self._analyze_image_with_ocr_fallback(image_path, custom_config, custom_provider)
                except:
                    return f"图片AI分析失败: {e!s}"
        # 如果没有自定义配置,使用默认逻辑
        # 首先尝试使用豆包API
        doubao_config = self.ai_config_manager.config.get("providers", {}).get("doubao", {})
        if doubao_config.get("api_key"):
            try:
                result = self._try_image_analysis_with_provider(
                    doubao_config, "doubao", messages, mime_type
                )
                if result and not result.startswith("API调用失败") and not result.startswith("错误"):
                    return result
            except Exception:
                # 豆包失败,继续尝试其他提供商
                pass
        # 如果豆包失败或不可用,使用当前激活的AI提供商
        try:
            provider_config = self.ai_config_manager.get_active_provider_config()
            provider = self.ai_config_manager.config.get("active_provider", "deepseek")
            if not provider_config or not provider_config.get("api_key"):
                # 如果未配置API,尝试使用OCR
                return self._analyze_image_with_ocr_fallback(image_path)
            result = self._try_image_analysis_with_provider(
                provider_config, provider, messages, mime_type
            )
            # 检查是否是因为API不支持图片格式而失败
            if result and (
                "unknown variant" in result.lower() or
                "image_url" in result.lower() or
                ("API调用失败" in result and "400" in result) or
                "invalid_request_error" in result.lower() or
                "deserialize" in result.lower()
            ):
                # API不支持图片,使用OCR回退方案
                return self._analyze_image_with_ocr_fallback(image_path, provider_config, provider)
            if result:
                return result
            else:
                # 尝试OCR回退
                return self._analyze_image_with_ocr_fallback(image_path, provider_config, provider)
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            # 如果出错,尝试OCR回退
            try:
                return self._analyze_image_with_ocr_fallback(image_path)
            except:
                return f"图片AI分析失败: {e!s}\n\n错误详情:\n{error_detail}"

    def _try_image_analysis_with_provider(self, provider_config, provider, messages, mime_type):
        """尝试使用指定的AI提供商进行图片分析"""
        try:
            api_key = provider_config.get("api_key", "")
            if not api_key:
                return None
            base_url = provider_config.get("base_url", "")
            model = provider_config.get("model", "")
            endpoint = provider_config.get("endpoint", "/chat/completions")
            # 构建URL
            if provider == "deepseek":
                url = f"{base_url}/chat/completions"
            elif provider == "doubao":
                url = f"{base_url}{endpoint}"
            else:
                # 其他提供商使用标准endpoint
                url = f"{base_url}{endpoint}"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            data = {
                "model": model,
                "messages": messages,
                "temperature": provider_config.get("temperature", 0.3)
            }
            # 发送请求
            response = requests.post(url, json=data, headers=headers,
                                  timeout=provider_config.get("timeout", 120))
            if response.status_code == 200:
                result = response.json()
                # 处理响应
                if provider == "doubao":
                    # 豆包格式
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        return f"AI图片分析结果(使用{provider})\n" + "=" * 80 + "\n\n" + content
                    else:
                        return None
                else:
                    # 标准OpenAI格式(支持图片的模型)
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        return f"AI图片分析结果(使用{provider})\n" + "=" * 80 + "\n\n" + content
                    else:
                        return None
            else:
                # 返回完整的错误信息以便检测
                error_text = response.text[:500] if len(response.text) > 500 else response.text
                return f"API调用失败: {response.status_code}\n响应内容: {error_text}"
        except Exception as e:
            return f"错误: {e!s}"

    def _analyze_image_with_ocr_fallback(self, image_path, provider_config=None, provider=None):
        """使用OCR将图片转换为文本,然后使用AI分析文本(当API不支持图片时)"""
        try:
            # 尝试使用OCR识别图片
            ocr_text = self._perform_ocr_on_image(image_path)
            if not ocr_text or len(ocr_text.strip()) < 10:
                return "OCR识别失败: 未能从图片中提取到有效文本。\n\n" + \
                       "可能原因:\n" + \
                       "1. 图片中没有文字内容\n" + \
                       "2. 图片质量较差,无法识别\n" + \
                       "3. 未安装OCR工具(Tesseract)\n\n" + \
                       "建议: 请配置支持图片分析的AI提供商(如豆包/火山引擎)"
            # 使用AI分析OCR识别的文本
            if provider_config and provider:
                # 使用指定的提供商
                prompt = f"""以下是通过OCR从图片中识别出的文本内容:
{ocr_text}
请仔细分析这些内容。如果这是股票交割单、交易记录或财务报表,请:
1. 识别并提取所有交易数据(股票代码、名称、买卖方向、价格、数量、金额、日期等)
2. 分析交易行为(交易频率、买卖比例、持仓结构等)
3. 计算盈亏情况(整体盈亏、单只股票盈亏)
4. 评估交易策略(交易时机、仓位管理、风险控制等)
5. 提供投资建议和风险提示
如果内容不是交易相关,请详细描述并进行分析。
请提供详细、专业的分析报告。"""
                ai_result = self.call_ai_model(prompt, None, provider_config)
                if ai_result and not ai_result.startswith("错误"):
                    return f"AI图片分析结果(使用OCR+{provider})\n" + "=" * 80 + "\n\n" + \
                           f"OCR识别文本:\n{'-' * 80}\n{ocr_text}\n\n" + \
                           f"AI分析结果:\n{'-' * 80}\n{ai_result}"
                else:
                    return f"OCR识别文本:\n{ocr_text}\n\nAI分析失败: {ai_result}"
            else:
                # 使用当前激活的提供商
                prompt = f"""以下是通过OCR从图片中识别出的文本内容:
{ocr_text}
请仔细分析这些内容。如果这是股票交割单、交易记录或财务报表,请:
1. 识别并提取所有交易数据(股票代码、名称、买卖方向、价格、数量、金额、日期等)
2. 分析交易行为(交易频率、买卖比例、持仓结构等)
3. 计算盈亏情况(整体盈亏、单只股票盈亏)
4. 评估交易策略(交易时机、仓位管理、风险控制等)
5. 提供投资建议和风险提示
如果内容不是交易相关,请详细描述并进行分析。
请提供详细、专业的分析报告。"""
                ai_result = self.call_ai_model(prompt)
                if ai_result and not ai_result.startswith("错误"):
                    return "AI图片分析结果(使用OCR+AI)\n" + "=" * 80 + "\n\n" + \
                           f"OCR识别文本:\n{'-' * 80}\n{ocr_text}\n\n" + \
                           f"AI分析结果:\n{'-' * 80}\n{ai_result}"
                else:
                    return f"OCR识别文本:\n{ocr_text}\n\nAI分析失败: {ai_result}"
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            return f"OCR回退分析失败: {e!s}\n\n错误详情:\n{error_detail}"

    def show_fundamental_analysis(self):
        """基本面分析弹窗:输入股票名,生成财务分析模型与行业对比(杜邦、财务比率、DCF、行业对比、事件驱动)。"""
        win = self._toplevel(self.root)
        win.title("基本面分析")
        win.geometry("1000x750")
        win.transient(self.root)
        main = ttk.Frame(win, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        ttk.Label(main, text="基本面分析:财务分析模型 + 行业对比 + 事件驱动", font=("TkDefaultFont", 12, "bold")).pack(pady=(0, 8))
        input_frame = ttk.Frame(main)
        input_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(input_frame, text="股票名称或代码:", width=14).pack(side=tk.LEFT, padx=(0, 5))
        stock_var = tk.StringVar()
        stock_entry = ttk.Entry(input_frame, textvariable=stock_var, width=25)
        stock_entry.pack(side=tk.LEFT, padx=(0, 10))
        result_text = scrolledtext.ScrolledText(main, wrap=tk.WORD, font=("TkDefaultFont", 11))
        result_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        result_text.tag_configure("title", font=("TkDefaultFont", 11, "bold"), foreground="blue")
        result_text.tag_configure("section", font=("TkDefaultFont", 12, "bold"), foreground="green")
        status_var = tk.StringVar(value="输入股票后点击「3. 基本面分析」生成报告")
        status_label = ttk.Label(main, textvariable=status_var, font=("TkDefaultFont", 11), foreground="gray")
        status_label.pack(anchor=tk.W, pady=(5, 0))
        def run_fundamental_analysis():
            name_or_code = (stock_var.get() or "").strip()
            if not name_or_code:
                messagebox.showwarning("提示", "请输入股票名称或代码。", parent=win)
                return
            code = name_or_code
            name = name_or_code
            if not name_or_code.isdigit() or len(name_or_code) != 6:
                code = get_stock_code_by_name(name_or_code)
                if not code:
                    messagebox.showwarning("提示", f"未找到股票: {name_or_code}", parent=win)
                    return
                name = name_or_code
            else:
                try:
                    from . import STOCK_CODES_DICT
                    if STOCK_CODES_DICT and code in STOCK_CODES_DICT:
                        name = STOCK_CODES_DICT.get(code, code)
                except Exception:
                    name = code
            status_var.set("正在生成基本面分析报告,请稍候...")
            win.update()
            def do_analysis():
                try:
                    prompt = f"""请对 A 股股票「{name}({code})」做一份基本面分析报告,结构如下(可基于公开信息与合理假设,若某数据不可得请说明并给出分析框架)。
一、财务分析模型
1. 杜邦分析体系:自动拆解 ROE = 净利率×资产周转率×权益乘数,分析该公司在盈利能力、营运能力、杠杆水平上的表现及趋势。
2. 财务比率横向/纵向对比:选取关键比率(如流动比率、速动比率、资产负债率、毛利率、净利率、ROE、ROA、存货周转率、应收账款周转率等),进行同行业横向对比及近年纵向对比。
3. 现金流折现(DCF)估值模型:简述自由现金流预测思路、WACC 或折现率假设、终值处理,并给出估值区间或结论(可基于典型假设示例)。
二、行业对比
1. 同行业公司关键指标对比:列出 2~4 家同行业可比公司,对比 PE、PB、PS、ROE、营收增速、毛利率等关键指标。
2. 行业景气度分析模型:从供需、政策、景气周期等维度分析该行业当前所处阶段及对该公司的影响。
3. 事件驱动分析:结合财报/季报披露、重大公告、政策变化,分析其与公司基本面的关联及可能影响。
要求:条理清晰,数据或假设需注明来源或前提;若无法获取实时数据,请给出分析框架与需关注的数据项。"""
                    system_prompt = "你是一位资深证券分析师,擅长财务分析、估值与行业研究。请用中文输出,结构清晰,必要时用分点或小标题。"
                    cfg = getattr(self, 'ai_config_manager', None)
                    config_override = None
                    if cfg:
                        pc = cfg.get_active_provider_config() or {}
                        config_override = dict(pc)
                        if config_override:
                            config_override["max_tokens"] = config_override.get("max_tokens") or 4000
                            config_override["timeout"] = max(int(config_override.get("timeout", 60)), 120)
                    result = self.call_ai_model(prompt, system_prompt=system_prompt, config_override=config_override)
                    def update_ui():
                        result_text.delete("1.0", tk.END)
                        result_text.insert(tk.END, f"【{name}({code})】基本面分析报告\n", "title")
                        result_text.insert(tk.END, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n", "section")
                        result_text.insert(tk.END, result or "生成失败或未配置 AI。")
                        status_var.set("分析完成")
                    self.root.after(0, update_ui)
                except Exception as e:
                    self.root.after(0, lambda e=e: status_var.set("分析失败"))
                    self.root.after(0, lambda e=e: messagebox.showerror("错误", str(e), parent=win))
            threading.Thread(target=do_analysis, daemon=True).start()
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frame, text="3. 基本面分析", command=run_fundamental_analysis, width=18).pack(side=tk.LEFT, padx=(0, 5))
        win.lift()
        win.focus_force()

    def analyze_latest_n_stocks(self):
        """分析最新N条股票数据"""
        try:
            # 询问用户N的值
            n_str = simpledialog.askstring("输入数量", "请输入要分析的最新股票数据条数(N):\n留空则直接打开批量分析器", initialvalue="10")
            if not n_str or n_str.strip() == "":
                # 如果为空,直接打开批量分析器界面
                self.show_batch_stock_analyzer()
                return
            try:
                n = int(n_str)
                if n <= 0:
                    messagebox.showerror("错误", "数量必须大于0")
                    return
            except ValueError:
                messagebox.showerror("错误", "请输入有效的数字")
                return
            # 从数据库获取最新N条股票数据
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT DISTINCT stock_name
                    FROM stock_logic
                    WHERE stock_name IS NOT NULL AND stock_name != ''
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (n,))
                results = cursor.fetchall()
                conn.close()
                if not results:
                    messagebox.showwarning("警告", "数据库中没有股票数据")
                    return
                # 提取股票名称列表
                stock_names = [row[0] for row in results]
                # 打开批量分析器窗口(支持打包后的环境)
                script_name = "stock_batch_analyzer.py"
                batch_analyzer_path = None
                # 1. 尝试使用 PyInstaller 打包后的路径(sys._MEIPASS)
                if hasattr(sys, '_MEIPASS'):
                    meipass_path = os.path.join(sys._MEIPASS, script_name)
                    if os.path.exists(meipass_path):
                        batch_analyzer_path = meipass_path
                # 2. 尝试可执行文件所在目录的 _internal 子目录
                if not batch_analyzer_path and hasattr(sys, 'frozen'):
                    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                    internal_path = os.path.join(exe_dir, '_internal', script_name)
                    if os.path.exists(internal_path):
                        batch_analyzer_path = internal_path
                # 3. 尝试与主程序同目录
                if not batch_analyzer_path:
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    same_dir_path = os.path.join(current_dir, script_name)
                    if os.path.exists(same_dir_path):
                        batch_analyzer_path = same_dir_path
                # 4. 尝试当前工作目录
                if not batch_analyzer_path:
                    cwd_path = os.path.join(os.getcwd(), script_name)
                    if os.path.exists(cwd_path):
                        batch_analyzer_path = cwd_path
                if not batch_analyzer_path or not os.path.exists(batch_analyzer_path):
                    error_msg = f"找不到批量股票分析器文件:\n{script_name}\n\n"
                    if hasattr(sys, '_MEIPASS'):
                        error_msg += f"已尝试路径:\n1. {os.path.join(sys._MEIPASS, script_name)}\n"
                    if hasattr(sys, 'frozen'):
                        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                        error_msg += f"2. {os.path.join(exe_dir, '_internal', script_name)}\n"
                    error_msg += f"3. {os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)}\n"
                    error_msg += f"4. {os.path.join(os.getcwd(), script_name)}\n\n"
                    error_msg += "请确保stock_batch_analyzer.py文件已正确打包或放置在可执行文件目录中。"
                    messagebox.showerror("错误", error_msg)
                    return
                # 动态导入模块
                spec = importlib.util.spec_from_file_location("stock_batch_analyzer", batch_analyzer_path)
                batch_analyzer_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(batch_analyzer_module)
                # 创建新窗口
                win = self._toplevel(self.root)
                win.title(f"批量股票分析器 - 最新{n}条数据")
                win.transient(self.root)
                # 实例化批量股票分析器
                batch_analyzer = batch_analyzer_module.StockBatchAnalyzer(win)
                # 设置5日差
                batch_analyzer.days_var.set("5")
                # 填充股票列表到输入框
                stock_text = "\n".join(stock_names)
                batch_analyzer.input_text.delete("1.0", tk.END)
                batch_analyzer.input_text.insert("1.0", stock_text)
                # 延迟自动开始分析(等待窗口完全加载)
                def auto_start_analysis():
                    try:
                        # 开始分析
                        batch_analyzer.start_analysis()
                        # 记录开始时的结果数量
                        initial_result_count = len(batch_analyzer.result_data) if hasattr(batch_analyzer, 'result_data') else 0
                        # 等待分析完成(通过检查分析线程状态和结果数据变化)
                        def check_and_save():
                            try:
                                # 检查分析线程是否还在运行
                                thread_running = (hasattr(batch_analyzer, 'analysis_thread') and
                                                batch_analyzer.analysis_thread is not None and
                                                batch_analyzer.analysis_thread.is_alive())
                                # 检查是否有新的结果数据
                                current_result_count = len(batch_analyzer.result_data) if hasattr(batch_analyzer, 'result_data') else 0
                                has_new_results = current_result_count > initial_result_count
                                if thread_running:
                                    # 如果还在分析,继续等待
                                    win.after(1000, check_and_save)
                                elif has_new_results or current_result_count > 0:
                                    # 分析完成,自动保存
                                    try:
                                        batch_analyzer.batch_insert_to_db()
                                        messagebox.showinfo("完成", f"已自动分析并保存最新{n}条股票数据到数据库\n共保存 {current_result_count} 条分析结果")
                                    except Exception as e:
                                        messagebox.showwarning("提示", f"分析完成,但自动保存失败: {e}\n请手动点击'批量插入数据库'按钮")
                                else:
                                    # 等待一段时间后再次检查(可能分析刚开始)
                                    win.after(2000, check_and_save)
                            except Exception as e:
                                # 如果检查过程中出错,提示用户手动保存
                                messagebox.showwarning("提示", f"自动检测分析状态失败: {e}\n请手动检查分析结果并保存")
                        # 延迟开始检查分析状态(给分析一些启动时间)
                        win.after(3000, check_and_save)
                    except Exception as e:
                        messagebox.showerror("错误", f"自动开始分析失败: {e}")
                # 延迟执行自动开始分析(等待窗口完全加载)
                win.after(500, auto_start_analysis)
            except Exception as e:
                messagebox.showerror("错误", f"获取股票数据失败: {e}")
        except Exception as e:
            messagebox.showerror("错误", f"操作失败: {e}")

    def _analyze_lhb_data(self, tree_widget, analysis_text):
        """AI分析龙虎榜选中数据"""
        selections = tree_widget.selection()
        if not selections:
            messagebox.showwarning("提示", "请先选择需要分析的龙虎榜数据")
            return
        lines = []
        for item in selections:
            values = tree_widget.item(item, 'values')
            if len(values) >= 13:
                trade_date, ts_code, name, close, pct_change, turnover_rate, amount, l_amount, net_amount, net_rate, amount_rate, float_values, reason = values
                lines.append(
                    f"{trade_date} {name}({ts_code}) 收盘价{close} 涨跌幅{pct_change} 换手率{turnover_rate} "
                    f"总成交额{amount} 龙虎榜成交{l_amount} 净买入{net_amount} 净买占比{net_rate} 成交占比{amount_rate} "
                    f"流通市值{float_values} 原因:{reason}"
                )
        if not lines:
            messagebox.showwarning("提示", "选中数据不足以分析")
            return
        prompt = f"""请根据以下龙虎榜数据,分析主力资金动向、市场情绪及潜在机会。请涵盖以下要点:
1. 按净买入额评估资金最关注的股票和交易所;
2. 识别异常的涨跌幅与换手率组合(如大涨伴随巨额净买)并解释可能逻辑;
3. 对资金净流出的股票给出风险提示;
4. 总结整体市场风格(偏进攻/防守)并给出操作建议。
数据:
{chr(10).join(lines)}"""
        analysis_text.config(state=tk.NORMAL)
        analysis_text.delete("1.0", tk.END)
        analysis_text.insert("1.0", "正在分析,请稍候......")
        analysis_text.config(state=tk.DISABLED)
        def analyze_thread():
            try:
                result = self.call_ai(prompt)
                if not result:
                    result = "AI分析失败,请检查AI配置。"
                self._update_analysis_text(analysis_text, result)
            except Exception as e:
                self._update_analysis_text(analysis_text, f"分析失败: {e}")
        threading.Thread(target=analyze_thread, daemon=True).start()

    def _analyze_margin_summary(self, tree_widget, analysis_text):
        """AI分析融资融券汇总数据"""
        items = tree_widget.get_children()
        if not items:
            messagebox.showwarning("提示", "请先查询数据")
            return
        # 收集数据
        data_list = []
        for item in items:
            values = tree_widget.item(item, 'values')
            if len(values) >= 9:
                data_list.append({
                    'trade_date': values[0],
                    'exchange_id': values[1],
                    'rzye': values[2],
                    'rzmre': values[3],
                    'rzche': values[4],
                    'rqye': values[5],
                    'rqmcl': values[6],
                    'rzrqye': values[7],
                    'rqyl': values[8]
                })
        if not data_list:
            messagebox.showwarning("提示", "没有可分析的数据")
            return
        # 构建分析提示
        data_summary = "\n".join([f"{d['trade_date']} {d['exchange_id']}: 融资余额={d['rzye']}, 融资买入={d['rzmre']}, 融资偿还={d['rzche']}, 融券余额={d['rqye']}, 融资融券余额={d['rzrqye']}"
                                 for d in data_list])
        prompt = f"""请分析以下融资融券交易汇总数据,并提供专业的投资分析:
数据说明:
- 融资余额:投资者尚未偿还的融资总额
- 融资买入额:当日融资买入的金额
- 融资偿还额:当日偿还的融资金额
- 融券余额:投资者尚未偿还的融券总额
- 融券卖出量:当日融券卖出的数量
- 融资融券余额:融资余额+融券余额的总和
- 融券余量:尚未偿还的融券数量
数据:
{data_summary}
请从以下角度进行分析:
1. 市场情绪分析(融资买入与偿还的对比,反映市场看多情绪)
2. 资金流向分析(融资余额变化趋势)
3. 风险提示(融券余额变化,反映看空情绪)
4. 投资建议(基于数据给出操作建议)"""
        analysis_text.config(state=tk.NORMAL)
        analysis_text.delete("1.0", tk.END)
        analysis_text.insert("1.0", "正在分析,请稍候...")
        analysis_text.config(state=tk.DISABLED)
        def analyze_thread():
            try:
                result = self.call_ai(prompt)
                if result:
                    self.root.after(0, lambda: self._update_analysis_text(analysis_text, result))
                else:
                    self.root.after(0, lambda: analysis_text.config(state=tk.NORMAL) or analysis_text.delete("1.0", tk.END) or analysis_text.insert("1.0", "AI分析失败,请检查AI配置") or analysis_text.config(state=tk.DISABLED))
            except Exception as e:
                self.root.after(0, lambda e=e: analysis_text.config(state=tk.NORMAL) or analysis_text.delete("1.0", tk.END) or analysis_text.insert("1.0", f"分析失败: {e}") or analysis_text.config(state=tk.DISABLED))
        threading.Thread(target=analyze_thread, daemon=True).start()

    def _analyze_margin_detail(self, tree_widget, analysis_text):
        """AI分析融资融券明细数据"""
        items = tree_widget.get_children()
        if not items:
            messagebox.showwarning("提示", "请先查询数据")
            return
        # 收集数据(取前20条,避免数据过多)
        data_list = []
        for item in list(items)[:20]:
            values = tree_widget.item(item, 'values')
            if len(values) >= 11:
                data_list.append({
                    'trade_date': values[0],
                    'ts_code': values[1],
                    'name': values[2],
                    'rzye': values[3],
                    'rqye': values[4],
                    'rzmre': values[5],
                    'rqyl': values[6],
                    'rzche': values[7],
                    'rqchl': values[8],
                    'rqmcl': values[9],
                    'rzrqye': values[10]
                })
        if not data_list:
            messagebox.showwarning("提示", "没有可分析的数据")
            return
        # 构建分析提示
        data_summary = "\n".join([f"{d['name']}({d['ts_code']}): 融资余额={d['rzye']}, 融资买入={d['rzmre']}, 融资偿还={d['rzche']}, 融券余额={d['rqye']}, 融资融券余额={d['rzrqye']}"
                                 for d in data_list])
        prompt = f"""请分析以下融资融券交易明细数据,并提供专业的投资分析:
数据说明:
- 融资余额:该股票投资者尚未偿还的融资总额
- 融资买入额:当日该股票的融资买入金额
- 融资偿还额:当日该股票的融资偿还金额
- 融券余额:该股票投资者尚未偿还的融券总额
- 融券卖出量:当日该股票的融券卖出数量
- 融资融券余额:融资余额+融券余额的总和
- 融券余量:尚未偿还的融券数量
数据(前20条):
{data_summary}
请从以下角度进行分析:
1. 热门股票识别(融资融券余额较大的股票,反映市场关注度)
2. 市场情绪分析(融资买入与偿还的对比,反映看多情绪)
3. 风险提示(融券余额较大的股票,反映看空情绪)
4. 投资建议(基于数据给出操作建议,重点关注哪些股票)"""
        analysis_text.config(state=tk.NORMAL)
        analysis_text.delete("1.0", tk.END)
        analysis_text.insert("1.0", "正在分析,请稍候...")
        analysis_text.config(state=tk.DISABLED)
        def analyze_thread():
            try:
                result = self.call_ai(prompt)
                if result:
                    self.root.after(0, lambda: self._update_analysis_text(analysis_text, result))
                else:
                    self.root.after(0, lambda: analysis_text.config(state=tk.NORMAL) or analysis_text.delete("1.0", tk.END) or analysis_text.insert("1.0", "AI分析失败,请检查AI配置") or analysis_text.config(state=tk.DISABLED))
            except Exception as e:
                self.root.after(0, lambda e=e: analysis_text.config(state=tk.NORMAL) or analysis_text.delete("1.0", tk.END) or analysis_text.insert("1.0", f"分析失败: {e}") or analysis_text.config(state=tk.DISABLED))
        threading.Thread(target=analyze_thread, daemon=True).start()

    def _update_analysis_text(self, text_widget, content):
        """更新分析文本"""
        text_widget.config(state=tk.NORMAL)
        text_widget.delete("1.0", tk.END)
        text_widget.insert("1.0", content)
        text_widget.config(state=tk.DISABLED)

    def show_batch_stock_analyzer(self):
        """打开批量股票分析器界面"""
        try:
            # 动态导入批量股票分析器模块
            try:
                # 获取当前文件所在目录
                current_dir = os.path.dirname(os.path.abspath(__file__))
                batch_analyzer_path = os.path.join(current_dir, "stock_batch_analyzer.py")
                if not os.path.exists(batch_analyzer_path):
                    messagebox.showerror("错误", f"找不到批量股票分析器文件:\n{batch_analyzer_path}")
                    return
                # 动态导入模块
                spec = importlib.util.spec_from_file_location("stock_batch_analyzer", batch_analyzer_path)
                batch_analyzer_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(batch_analyzer_module)
                # 创建新窗口
                win = self._toplevel(self.root)
                win.title("批量股票分析器")
                win.transient(self.root)
                # 实例化批量股票分析器
                batch_analyzer_module.StockBatchAnalyzer(win)
            except ImportError as e:
                messagebox.showerror("错误", f"导入批量股票分析器失败: {e}\n\n请确保stock_batch_analyzer.py文件存在且可访问。")
            except Exception as e:
                messagebox.showerror("错误", f"打开批量股票分析器失败: {e}")
                import traceback
                traceback.print_exc()
        except Exception as e:
            messagebox.showerror("错误", f"打开批量股票分析器失败: {e}")
            import traceback
            traceback.print_exc()

    def _create_analysis_window(self, win, header_text, options, option_label, prompt_func, system_prompt=None):
        """创建通用的分析窗口"""
        if system_prompt is None:
            system_prompt = "你是一位资深的投资分析专家,能够提供专业的投资建议和分析。"
        # 保存system_prompt供后续使用
        win._system_prompt = system_prompt
        win.columnconfigure(0, weight=1)
        win.columnconfigure(1, weight=1)
        win.rowconfigure(1, weight=1)
        # 存储窗口状态
        win._is_minimized = False
        win._original_geometry = win.geometry()
        win.resizable(True, True)
        # 头部说明
        header = ttk.Label(
            win,
            text=header_text,
            anchor="center",
            font=("Microsoft YaHei", 14, "bold")
        )
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
        # 左侧:问题描述
        left_frame = ttk.LabelFrame(win, text="问题描述", padding=10)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=6)
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(1, weight=1)
        problem_text = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD, height=20, font=("TkDefaultFont", 12))
        problem_text.grid(row=1, column=0, sticky="nsew")
        # 右侧:分析结果
        right_frame = ttk.LabelFrame(win, text="分析结果", padding=10)
        right_frame.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=6)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)
        result_text = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, height=20, font=("TkDefaultFont", 12), state=tk.DISABLED)
        self._enable_clickable_links(result_text)
        result_text.grid(row=1, column=0, sticky="nsew")
        # 底部:选项按钮
        control_frame = ttk.LabelFrame(win, text=option_label, padding=10)
        control_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
        # 创建按钮
        buttons_per_row = 5
        row = 0
        col = 0
        for option_name, option_desc in options.items():
            btn = ttk.Button(
                control_frame,
                text=option_name,
                command=lambda name=option_name, desc=option_desc, sp=system_prompt: self._run_option_analysis(
                    name, desc, problem_text, result_text, prompt_func, sp
                ),
                width=15
            )
            btn.grid(row=row, column=col, padx=6, pady=4, sticky="ew")
            col += 1
            if col >= buttons_per_row:
                col = 0
                row += 1
        # 配置列权重
        for i in range(buttons_per_row):
            control_frame.columnconfigure(i, weight=1)
        # 添加通用按钮
        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=row+1, column=0, columnspan=buttons_per_row, pady=(10, 0), sticky="ew")
        ttk.Button(button_frame, text="AI分析",
                  command=lambda sp=system_prompt: self._run_ai_analysis(problem_text, result_text, sp)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空",
                  command=lambda: self._clear_analysis(problem_text, result_text)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="复制结果",
                  command=lambda: self._copy_result(result_text)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="添加到咨询",
                  command=lambda: self._add_to_consultation(result_text)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="添加到警示",
                  command=lambda: self._add_to_warning(result_text)).pack(side=tk.LEFT, padx=5)
        # 窗口控制按钮
        control_btn_frame = ttk.Frame(win)
        control_btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
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

    def _run_option_analysis(self, option_name, option_desc, problem_text, result_text, prompt_func, system_prompt=None):
        """运行选项分析"""
        if system_prompt is None:
            system_prompt = "你是一位资深的投资分析专家,能够提供专业的投资建议和分析。"
        problem = problem_text.get("1.0", tk.END).strip()
        if not problem:
            problem = f"请分析{option_name}相关内容"
        # 生成提示
        prompt = prompt_func(option_name, option_desc, problem)
        # 显示分析中
        result_text.config(state=tk.NORMAL)
        result_text.delete("1.0", tk.END)
        result_text.insert(tk.END, f"[{option_name}] 正在分析...\n\n")
        result_text.insert(tk.END, f"系统说明:{option_desc}\n\n")
        result_text.config(state=tk.DISABLED)
        # 异步调用AI
        def analyze():
            try:
                ai_result = self.call_ai_model(prompt, system_prompt)
                if not ai_result:
                    ai_result = f"【{option_name}分析】\n\n{option_desc}\n\n请结合您的问题进行深入分析。"
            except Exception as e:
                ai_result = f"AI分析失败: {e}\n\n{option_desc}"
            def update_ui():
                result_text.config(state=tk.NORMAL)
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, f"[{option_name}] 分析结果\n\n")
                result_text.insert(tk.END, f"系统说明:{option_desc}\n\n")
                result_text.insert(tk.END, "="*50 + "\n\n")
                result_text.insert(tk.END, ai_result)
                result_text.config(state=tk.DISABLED)
                result_text.see("1.0")
            if hasattr(self, "root") and self.root.winfo_exists():
                self.root.after(0, update_ui)
        threading.Thread(target=analyze, daemon=True).start()

    def _run_ai_analysis(self, problem_text, result_text, system_prompt=None):
        """运行AI分析"""
        if system_prompt is None:
            system_prompt = "你是一位资深的投资分析专家,能够提供专业的投资建议和分析。"
        problem = problem_text.get("1.0", tk.END).strip()
        if not problem:
            messagebox.showwarning("提示", "请输入问题描述")
            return
        result_text.config(state=tk.NORMAL)
        result_text.delete("1.0", tk.END)
        result_text.insert(tk.END, "AI分析中,请稍候...\n")
        result_text.config(state=tk.DISABLED)
        def analyze():
            try:
                ai_result = self.call_ai_model(problem, system_prompt)
                if not ai_result:
                    ai_result = "未获取到AI分析结果,请检查配置。"
            except Exception as e:
                ai_result = f"AI分析失败: {e}"
            def update_ui():
                result_text.config(state=tk.NORMAL)
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, "AI分析结果\n\n")
                result_text.insert(tk.END, "="*50 + "\n\n")
                result_text.insert(tk.END, ai_result)
                result_text.config(state=tk.DISABLED)
                result_text.see("1.0")
            if hasattr(self, "root") and self.root.winfo_exists():
                self.root.after(0, update_ui)
        threading.Thread(target=analyze, daemon=True).start()

    def _clear_analysis(self, problem_text, result_text):
        """清空分析"""
        problem_text.delete("1.0", tk.END)
        result_text.config(state=tk.NORMAL)
        result_text.delete("1.0", tk.END)
        result_text.config(state=tk.DISABLED)

    def show_safety_analysis(self):
        """打开安全分析界面"""
        try:
            win = self._toplevel(self.root)
            win.title("安全分析工作台")
            win.geometry("1200x720")
            win.transient(self.root)
            # 安全选项
            safety_options = {
                "同花顺情绪指数": "分析同花顺情绪指数883404的日K、60分钟周期、15分钟周期的情绪判断,以及情绪指数相关的重要指标和分析",
                "信用风险": "评估交易对手的信用风险,包括公司财务状况、债务水平、违约概率",
                "市场风险": "评估市场波动带来的风险,包括系统性风险、黑天鹅事件、市场崩盘",
                "流动性风险": "评估资产变现的难易程度,包括交易量、买卖价差、市场深度",
                "操作风险": "评估操作失误带来的风险,包括下单错误、系统故障、人为失误",
                "政策风险": "评估政策变化带来的风险,包括监管政策、税收政策、行业政策",
                "汇率风险": "评估汇率波动带来的风险,包括外汇敞口、汇率对冲、跨境投资",
                "集中度风险": "评估投资过于集中带来的风险,包括行业集中、个股集中、地域集中",
                "杠杆风险": "评估使用杠杆带来的风险,包括融资融券、期货杠杆、衍生品风险",
                "估值风险": "评估资产估值过高带来的风险,包括PE/PB过高、泡沫风险、价值回归"
            }
            self._create_analysis_window(
                win,
                "请输入安全相关问题,选择安全类型进行分析",
                safety_options,
                "安全类型",
                self._get_safety_prompt,
                "你是一位资深的风险管理专家,精通各种投资安全评估和风险控制方法。"
            )
        except Exception as e:
            messagebox.showerror("错误", f"打开安全分析界面失败: {e}")
            import traceback
            traceback.print_exc()

    def show_liquidity_analysis(self):
        """打开流动性分析界面"""
        try:
            win = self._toplevel(self.root)
            win.title("流动性分析工作台")
            win.geometry("1200x720")
            win.transient(self.root)
            # 流动性选项
            liquidity_options = {
                "市场流动性": "评估标的物的市场流动性,包括成交量、换手率、买卖盘深度",
                "跌停板检查": "检查是否处于跌停板状态,跌停板无法买入,缺乏流动性",
                "涨停板检查": "检查是否处于涨停板状态,涨停板难以买入,流动性受限",
                "停牌检查": "检查是否处于停牌状态,停牌期间无法交易,无流动性",
                "ST股票检查": "检查是否为ST股票,ST股票交易受限,流动性较差",
                "成交量分析": "分析成交量变化,评估市场参与度和流动性状况",
                "买卖价差": "分析买卖价差,评估交易成本和流动性质量",
                "大宗交易": "分析大宗交易情况,评估机构参与度和市场深度",
                "限售解禁": "分析限售股解禁情况,评估潜在抛压和流动性冲击",
                "不当投资检查": "检查不当投资情况,如跌停板、停牌、ST等流动性陷阱"
            }
            self._create_analysis_window(
                win,
                "请输入流动性相关问题,选择分析类型进行检查",
                liquidity_options,
                "流动性分析",
                self._get_liquidity_prompt,
                "你是一位资深的流动性分析专家,精通市场流动性和不当投资识别。"
            )
        except Exception as e:
            messagebox.showerror("错误", f"打开流动性分析界面失败: {e}")
            import traceback
            traceback.print_exc()

    def show_profit_analysis(self):
        """打开利润分析界面"""
        try:
            win = self._toplevel(self.root)
            win.title("利润分析工作台")
            win.geometry("1200x720")
            win.transient(self.root)
            # 利润选项
            profit_options = {
                "趋势分析": "分析价格趋势,包括月线MACD双金叉、60分钟短线非死叉、15分钟多头排列",
                "月线MACD双金叉": "月线级别MACD双金叉,确认长期上涨趋势",
                "60分钟非死叉": "60分钟级别MACD未死叉,确认中期上涨趋势",
                "15分钟多头排列": "15分钟级别均线多头排列,确认短期上涨趋势",
                "技术指标": "综合分析各种技术指标,包括MACD、KDJ、RSI、BOLL等",
                "量价关系": "分析成交量与价格的关系,确认上涨的有效性",
                "支撑阻力": "分析关键支撑位和阻力位,确定买入和卖出时机",
                "形态识别": "识别K线形态,包括头肩底、双底、三角形等反转或持续形态",
                "资金流向": "分析主力资金流向,确认资金是否流入",
                "盈利预期": "评估盈利预期,包括目标价位、止损价位、风险收益比"
            }
            self._create_analysis_window(
                win,
                "请输入利润相关问题,选择分析类型进行评估",
                profit_options,
                "利润分析",
                self._get_profit_prompt,
                "你是一位资深的技术分析专家,精通各种技术指标和趋势分析方法。"
            )
        except Exception as e:
            messagebox.showerror("错误", f"打开利润分析界面失败: {e}")
            import traceback
            traceback.print_exc()

    def _fetch_history_analysis(self, stock_name):
        """获取历史涨跌分析数据(从批量分析结果表)"""
        try:
            rows = []
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                # 查询同股票名的历史分析数据
                cursor.execute('''
                    SELECT analysis_date, high_low_days, low_diff, low_diff_pct,
                           high_diff, high_diff_pct, created_at
                    FROM batch_analysis_results
                    WHERE stock_name = ?
                    ORDER BY created_at DESC
                    LIMIT 100
                ''', (stock_name,))
                results = cursor.fetchall()
                conn.close()
                for row in results:
                    date, days, low_diff, low_diff_pct, high_diff, high_diff_pct, created_at = row
                    # 计算区间位置(如果有高低点数据)
                    if low_diff is not None and high_diff is not None:
                        # 简化计算:假设当前价在高低点中间
                        pos_ratio = 0.5
                        if high_diff != low_diff:
                            pos_ratio = abs(low_diff) / (abs(high_diff) + abs(low_diff))
                        pos_str = f"{pos_ratio * 100:.1f}%"
                    else:
                        pos_str = "--"
                    rows.append((
                        date or created_at[:10] if created_at else "--",
                        f"{days}天" if days else "--",
                        f"{low_diff:.2f}" if low_diff is not None else "--",
                        f"{low_diff_pct:+.2f}%" if low_diff_pct is not None else "--",
                        f"{high_diff:.2f}" if high_diff is not None else "--",
                        f"{high_diff_pct:+.2f}%" if high_diff_pct is not None else "--",
                        pos_str
                    ))
            except Exception as e:
                print(f"查询历史分析数据失败: {e}")
            return rows if rows else []
        except Exception as e:
            print(f"获取历史分析失败: {e}")
            return []

    def show_monthly_comprehensive_analysis(self):
        """资讯表AI分析:读取资讯数据表的内容,使用AI进行综合分析"""
        try:
            # 创建分析窗口
            analysis_window = self._toplevel(self.root)
            analysis_window.title("资讯表数据AI分析")
            analysis_window.geometry("1400x900")
            analysis_window.transient(self.root)
            # 主框架
            main_frame = ttk.Frame(analysis_window, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)
            # 标题
            ttk.Label(main_frame, text="🤖 资讯表数据AI分析",
                     font=("TkDefaultFont", 14, "bold")).pack(pady=(0, 10))
            # 按钮栏
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(0, 10))
            # 进度条
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(button_frame, variable=progress_var, length=260, mode='determinate')
            progress_bar.pack(side=tk.LEFT, padx=(0, 10))
            status_label = ttk.Label(button_frame, text="点击开始分析按钮开始...")
            status_label.pack(side=tk.LEFT, padx=(0, 10))
            # 资讯天数设置(用于"数据概览"和每日统计),默认 30 天
            days_var = tk.IntVar(value=30)
            ttk.Label(button_frame, text="天数:").pack(side=tk.LEFT)
            days_spin = ttk.Spinbox(button_frame, from_=1, to=90, textvariable=days_var, width=4)
            days_spin.pack(side=tk.LEFT, padx=(2, 0))
            # 导出按钮栏(右侧)
            def _do_export_txt():
                """导出为 TXT"""
                content = result_text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showwarning("提示", "没有可导出的内容,请先点击开始分析", parent=analysis_window)
                    return
                default_name = f"资讯AI分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                path = filedialog.asksaveasfilename(
                    title="导出为 TXT", defaultextension=".txt",
                    initialfile=default_name,
                    filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                    parent=analysis_window)
                if path:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(content)
                    messagebox.showinfo("成功", f"已导出: {path}", parent=analysis_window)
            def _do_export_excel():
                """导出股票明细为 Excel"""
                try:
                    import pandas as pd
                except Exception:
                    messagebox.showerror("错误", "需要安装 pandas 和 openpyxl", parent=analysis_window)
                    return
                if not stock_detail_list:
                    messagebox.showwarning("提示", "没有股票数据可导出", parent=analysis_window)
                    return
                rows = []
                for s in stock_detail_list:
                    rows.append({
                        "股票名": s.get("name", ""),
                        "代码": s.get("code", ""),
                        "来源": "、".join(s.get("sources", ["综合"])),
                        "同花顺人气排名": s.get("ths_rank") or "",
                        "行业": s.get("ths_industry") or "",
                        "概念": "、".join(s.get("ths_concepts", []) or []),
                        "最近10日涨跌": f"{s.get('pct_10', 0):+.2f}%",
                        "MA朝向": s.get("ma_judge", ""),
                        "10日乖离": f"{s.get('bias10', 0):+.2f}%" if s.get('bias10') is not None else "",
                        "20日乖离": f"{s.get('bias20', 0):+.2f}%" if s.get('bias20') is not None else "",
                        "逻辑": s.get("logic", "")[:200],
                    })
                df = pd.DataFrame(rows)
                default_name = f"资讯AI选股_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                path = filedialog.asksaveasfilename(
                    title="导出为 Excel", defaultextension=".xlsx",
                    initialfile=default_name,
                    filetypes=[("Excel文件", "*.xlsx")],
                    parent=analysis_window)
                if path:
                    df.to_excel(path, index=False, engine="openpyxl")
                    messagebox.showinfo("成功", f"已导出 {len(df)} 只股票到: {path}", parent=analysis_window)
            def _do_export_longimg():
                """导出为长图(PIL 渲染中文)"""
                try:
                    from PIL import Image, ImageDraw, ImageFont
                except Exception:
                    messagebox.showerror("错误", "需要安装 Pillow: pip install Pillow", parent=analysis_window)
                    return
                content = result_text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showwarning("提示", "没有可导出的内容", parent=analysis_window)
                    return
                # 找中文字体
                _font_paths = [
                    "/System/Library/Fonts/PingFang.ttc",
                    "/System/Library/Fonts/STHeiti Medium.ttc",
                    "/Library/Fonts/Songti.ttc",
                ]
                _font_path = None
                for fp in _font_paths:
                    if os.path.exists(fp):
                        _font_path = fp
                        break
                if not _font_path:
                    messagebox.showerror("错误", "找不到中文字体", parent=analysis_window)
                    return
                _FONT_SIZE = 16
                _LINE_H = _FONT_SIZE + 8
                _MAX_W = 1400
                _MARGIN = 40
                font = ImageFont.truetype(_font_path, _FONT_SIZE)
                # 先自动换行, 按 char_width 估计
                sample = "测试中文ABC"
                try:
                    _cw = font.getlength(sample) / len(sample)
                except Exception:
                    _cw = 14
                max_chars_per_line = int((_MAX_W - 2 * _MARGIN) / _cw)
                # 换行
                lines = []
                for raw_line in content.splitlines():
                    if not raw_line.strip():
                        lines.append("")
                        continue
                    # 按 max_chars_per_line 切分
                    while len(raw_line) > max_chars_per_line:
                        lines.append(raw_line[:max_chars_per_line])
                        raw_line = raw_line[max_chars_per_line:]
                    lines.append(raw_line)
                # 计算尺寸
                H = _MARGIN * 2 + len(lines) * _LINE_H + _MARGIN
                W = _MAX_W
                # 限制最大高度 12000px (避免过大)
                if H > 12000:
                    messagebox.showinfo("提示", f"内容过长({len(lines)}行), 将只保存前 12000px", parent=analysis_window)
                    lines = lines[:(12000 - 2 * _MARGIN - _MARGIN) // _LINE_H]
                    H = _MARGIN * 2 + len(lines) * _LINE_H + _MARGIN
                img = Image.new("RGB", (W, H), "white")
                draw = ImageDraw.Draw(img)
                y = _MARGIN
                for ln in lines:
                    draw.text((_MARGIN, y), ln, fill=(30, 30, 30), font=font)
                    y += _LINE_H
                default_name = f"资讯AI分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                path = filedialog.asksaveasfilename(
                    title="导出为长图", defaultextension=".png",
                    initialfile=default_name,
                    filetypes=[("PNG图片", "*.png")],
                    parent=analysis_window)
                if path:
                    img.save(path, "PNG")
                    messagebox.showinfo("成功", f"已保存长图: {path}", parent=analysis_window)
            def _do_copy_all():
                """全选复制到剪贴板"""
                content = result_text.get("1.0", tk.END).strip()
                analysis_window.clipboard_clear()
                analysis_window.clipboard_append(content)
                status_label.config(text=f"✅ 已复制 {len(content)} 字符到剪贴板")
            export_frame = ttk.Frame(main_frame)
            export_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(export_frame, text="📤 导出:").pack(side=tk.LEFT)
            ttk.Button(export_frame, text="📄 TXT", command=_do_export_txt).pack(side=tk.LEFT, padx=3)
            ttk.Button(export_frame, text="📊 Excel", command=_do_export_excel).pack(side=tk.LEFT, padx=3)
            ttk.Button(export_frame, text="🖼️ 长图", command=_do_export_longimg).pack(side=tk.LEFT, padx=3)
            ttk.Button(export_frame, text="📋 复制全部", command=_do_copy_all).pack(side=tk.LEFT, padx=3)
            # 创建滚动文本区域 - 字体加大
            result_frame = ttk.Frame(main_frame)
            result_frame.pack(fill=tk.BOTH, expand=True)
            result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, font=("PingFang SC", 14))
            result_text.pack(fill=tk.BOTH, expand=True)
            # 右键菜单(全选/复制)
            def _show_context_menu(event):
                ctx = tk.Menu(result_text, tearoff=0)
                try:
                    result_text.selection_get()
                    ctx.add_command(label="复制选中", command=lambda: result_text.event_generate("<<Copy>>"))
                except Exception:
                    pass
                ctx.add_command(label="全选", command=lambda: result_text.tag_add(tk.SEL, "1.0", tk.END))
                ctx.add_command(label="复制全部", command=_do_copy_all)
                ctx.tk_popup(event.x_root, event.y_root)
                ctx.grab_release()
            result_text.bind("<Button-3>", _show_context_menu)
            # 配置文本标签 - 字号整体加大 2-4pt
            result_text.tag_configure("title", font=("PingFang SC", 16, "bold"), foreground="blue")
            result_text.tag_configure("section", font=("PingFang SC", 15, "bold"), foreground="green")
            result_text.tag_configure("positive", foreground="red")
            result_text.tag_configure("negative", foreground="green")
            result_text.tag_configure("warning", foreground="orange")
            result_text.tag_configure("info", foreground="gray")
            # MA 方向配色标签
            result_text.tag_configure("ma_all_up", foreground="red")              # 全部向上
            result_text.tag_configure("ma_near5_up", foreground="#FF69B4")        # MA5/10/20 向上且价格靠近并高于 MA5(粉红色)
            result_text.tag_configure("ma_near10_up", foreground="goldenrod")     # MA10/20 向上且价格靠近并高于 MA10(黄色)
            result_text.tag_configure("ma_near20_up", foreground="green")         # MA10/20 向上且价格靠近 MA20(绿色)
            # 每日平均涨跌幅颜色
            result_text.tag_configure("daily_avg_up", foreground="red")
            result_text.tag_configure("daily_avg_down", foreground="green")
            # 日内出现频次对应的字号
            result_text.tag_configure("stock_freq_big", font=("PingFang SC", 15, "bold"))
            result_text.tag_configure("stock_freq_mid", font=("PingFang SC", 14, "bold"))
            result_text.tag_configure("stock_freq_small", font=("PingFang SC", 13))
            # 股价上穿15日线:红色加粗
            result_text.tag_configure("stock_cross15", foreground="red", font=("PingFang SC", 14, "bold"))
            # 同花顺人气/板块标签样式
            result_text.tag_configure("ths_rank", foreground="white", background="#FF6B35", font=("PingFang SC", 12, "bold"))
            result_text.tag_configure("ths_industry", foreground="white", background="#4A90D9", font=("PingFang SC", 11))
            result_text.tag_configure("ths_concept", foreground="#333", background="#F5A623", font=("PingFang SC", 11))
            def _is_logic_boilerplate_only(segment):
                """判断片段是否仅为不需要的表头/文件信息/来源/时间等,不应作为逻辑展示"""
                if not segment or not segment.strip():
                    return True
                import re
                s = segment.strip()
                # 各类表头/文件信息
                # 逻辑/文件表头
                if re.match(r'^逻辑\s*[::]\s*文章标题', s):
                    return True
                if re.match(r'^逻辑\s*[::][^\n]*?文件\s*:[^\n]*?\.xlsx', s):
                    return True
                if re.match(r'^文件\s*:[^\n]*?\.xlsx', s):
                    return True
                # 含 .xlsx 且包含多列字段名的行(各种爬取表头)
                header_keywords = [
                    "文章标题", "标题", "作者昵称", "作者ID", "作者", "帖子内容",
                    "股票代码", "股票名称", "阅读量", "点赞数", "收藏数", "评论数",
                    "转发数", "摘要", "爬取时间", "颜色代码", "颜色索引", "处理状态",
                ]
                if ".xlsx" in s:
                    count = sum(1 for kw in header_keywords if kw in s)
                    if count >= 2:
                        return True
                # 分析来源+时间
                if '分析来源' in s and '分析时间' in s:
                    return True
                # 纯分隔线
                return bool(re.match(r'^=+\s*$', s) or len(s) < 5 and '=' in s)
            def _strip_logic_boilerplate(text):
                """过滤掉不需要获取的字段:逻辑表头/文件信息(文章标题、作者昵称等)、分析来源、分析时间、等号分隔线"""
                if not text or not text.strip():
                    return ""
                import re
                s = text
                # 先去掉「逻辑: 文章标题 作者昵称 作者ID ... 原始HTML」这种整块表头
                s = re.sub(r'逻辑\s*[::]\s*文章标题\s*作者昵称\s*作者ID[\s\S]*?原始HTML\s*', '', s, flags=re.DOTALL)
                # 再按行过滤各种表头/文件信息/来源时间等
                lines = []
                for line in s.splitlines():
                    if _is_logic_boilerplate_only(line):
                        continue
                    lines.append(line)
                s = "\n".join(lines)
                # 去掉长等号分隔线残留
                s = re.sub(r'={20,}\s*\|?\s*', '', s)
                return s.strip()
            def run_analysis():
                """执行资讯表AI分析"""
                try:
                    result_text.delete("1.0", tk.END)
                    result_text.insert(tk.END, "=" * 80 + "\n", "info")
                    result_text.insert(tk.END, "🤖 资讯表数据AI分析报告\n", "title")
                    result_text.insert(tk.END, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n", "info")
                    result_text.insert(tk.END, "=" * 80 + "\n\n", "info")
                    status_label.config(text="正在读取资讯数据表...")
                    progress_var.set(5)
                    analysis_window.update()
                    # 读取用户设定的天数(用于数据概览与每日统计)
                    try:
                        days_for_news = int(days_var.get() or 30)
                    except Exception:
                        days_for_news = 30
                    days_for_news = max(1, min(90, days_for_news))
                    # 1. 读取资讯数据表的内容
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    # 获取最近 N 天的资讯数据(N 由用户设定,默认 30)
                    ten_days_ago = (datetime.now() - timedelta(days=days_for_news)).strftime("%Y-%m-%d")
                    cursor.execute('''
                        SELECT tab_name, content, created_at
                        FROM news_info
                        WHERE created_at >= ?
                        ORDER BY created_at DESC
                    ''', (ten_days_ago,))
                    news_data = cursor.fetchall()
                    # 如果没有最近10天的数据,获取最新的30条
                    if not news_data:
                        cursor.execute('''
                            SELECT tab_name, content, created_at
                            FROM news_info
                            ORDER BY created_at DESC
                            LIMIT 30
                        ''')
                        news_data = cursor.fetchall()
                    conn.close()
                    if not news_data:
                        result_text.insert(tk.END, "⚠️ 资讯数据表中没有数据\n", "warning")
                        result_text.insert(tk.END, "请先在资讯数据表中添加数据\n", "info")
                        status_label.config(text="没有找到数据")
                        return
                    result_text.insert(tk.END, "📋 数据概览\n", "section")
                    result_text.insert(tk.END, "-" * 40 + "\n")
                    result_text.insert(tk.END, f"资讯条目数: {len(news_data)} 条(最近{days_for_news}天)\n\n")
                    progress_var.set(10)
                    status_label.config(text="正在提取资讯中的股票并计算涨跌幅与均线...")
                    analysis_window.update()
                    # 从最近 N 天资讯中提取股票
                    stocks_by_code = {}
                    try:
                        days_data = get_news_stocks_by_date_and_frequency(ndays=days_for_news)
                        for day_info in days_data:
                            for name, code in day_info.get("stocks", []):
                                if code and code not in stocks_by_code:
                                    stocks_by_code[code] = name
                        # 最多分析 60 只,避免过慢
                        stocks_by_code = dict(list(stocks_by_code.items())[:60])
                    except Exception:
                        pass
                    # 按股票匹配资讯表逻辑(提取逻辑内容而非仅出处)+ 同时记录来源标签
                    news_logic_by_code = {}
                    news_logic_by_code_date = {}  # (code, date_ymd) -> [snippets] 每日单独
                    news_source_by_code = {}  # code -> Counter(source -> count)
                    # 来源关键词映射
                    _SOURCE_KEYWORDS = [
                        ("同花顺", ["同花顺", "ths", "10jqka"]),
                        ("选股宝", ["选股宝", "xgbao"]),
                        ("淘股吧", ["淘股吧", "淘股", "taoguba"]),
                        ("韭研公社", ["韭研", "jiuyan"]),
                        ("东方财富", ["东方财富", "eastmoney", "em", "东财"]),
                        ("问财", ["问财", "iwencai"]),
                        ("雪球", ["雪球", "xueqiu", "xq"]),
                        ("财联社", ["财联社", "cls"]),
                        ("新浪", ["新浪", "sina"]),
                        ("微博", ["微博", "weibo"]),
                        ("抖音", ["抖音", "douyin"]),
                    ]
                    def _detect_source(tab_name, content):
                        """从 tab_name 或 content 检测来源"""
                        text = (tab_name or "") + " " + (content or "")[:200]
                        text_lower = text.lower()
                        for label, kws in _SOURCE_KEYWORDS:
                            for kw in kws:
                                if kw.lower() in text_lower:
                                    return label
                        return "综合"
                    for tab_name, content, created_at in news_data:
                        if not content or not content.strip():
                            continue
                        _src_label = _detect_source(tab_name, content)
                        for code, name in list(stocks_by_code.items()):
                            name_d = (name or code).strip()
                            if code in content or (name_d and name_d in content):
                                if code not in news_logic_by_code:
                                    news_logic_by_code[code] = []
                                # 记录来源
                                from collections import Counter as _C
                                if code not in news_source_by_code:
                                    news_source_by_code[code] = _C()
                                news_source_by_code[code][_src_label] += 1
                                if len(news_logic_by_code[code]) < 2:
                                    # 先过滤掉不需要的字段:逻辑表头、分析来源、分析时间、等号分隔线
                                    cleaned = _strip_logic_boilerplate(content)
                                    if not cleaned:
                                        continue
                                    # 取逻辑性更强的片段:去掉多余换行,只保留前几句
                                    snippet = cleaned.replace("\n", " ").strip()
                                    for sep in ["。", "!", "?", ".", "!", "?"]:
                                        snippet = snippet.replace(sep, sep + "|SEP|")
                                    parts = [p.strip() for p in snippet.split("|SEP|") if p.strip() and not _is_logic_boilerplate_only(p.strip())]
                                    logic_core = "。".join(parts[:2])[:160] if parts else (cleaned[:160] if not _is_logic_boilerplate_only(cleaned[:160]) else "")
                                    if logic_core and not _is_logic_boilerplate_only(logic_core):
                                        news_logic_by_code[code].append(logic_core)
                                        # 同时存到按日期维度
                                        try:
                                            if isinstance(created_at, datetime):
                                                _dkey = created_at.strftime("%Y-%m-%d")
                                            elif isinstance(created_at, str):
                                                _dkey = created_at[:10]
                                            else:
                                                _dkey = str(created_at)[:10]
                                            # 只保留资讯日期范围
                                            _dkey_full = f"{_dkey[:4]}-{_dkey[5:7]}-{_dkey[8:10]}" if len(_dkey) >= 10 else _dkey
                                            _k = (code, _dkey_full)
                                            if _k not in news_logic_by_code_date:
                                                news_logic_by_code_date[_k] = []
                                            if len(news_logic_by_code_date[_k]) < 3:
                                                news_logic_by_code_date[_k].append(logic_core)
                                        except Exception:
                                            pass
                    # 每只股:最近10日涨跌幅、是否靠近5/10/20日线 + 均线朝向
                    stock_detail_list = []
                    NEAR_PCT = 2.0  # 距离均线 ±2% 视为靠近
                    for code, name in list(stocks_by_code.items()):
                        try:
                            result = self._fetch_recent_daily_closes(code, days=25, source="default", token=getattr(self, 'ts_token', None), return_volume=True)
                            if not isinstance(result, tuple) or len(result) < 2:
                                continue
                            dates, closes = result[0], result[1]
                            volumes = result[2] if len(result) >= 3 and result[2] else []
                            closes = [float(x) for x in closes if x is not None]
                            if len(closes) < 10:
                                continue
                            price = closes[-1]
                            pct_10 = (closes[-1] / closes[-10] - 1) * 100 if closes[-10] and closes[-10] != 0 else 0
                            # 最近10日逐日涨跌幅序列(左→右:旧→新),并记录每个交易日对应的日期和涨跌幅
                            pct10_series = ""
                            pct10_dates = ""
                            pct10_day_stats = []
                            try:
                                if len(closes) >= 11 and isinstance(dates, (list, tuple)) and len(dates) >= 11:
                                    seg_closes = closes[-11:]
                                    seg_dates = dates[-11:]
                                    daily = []
                                    def _norm_ymd(d):
                                        ds = str(d)
                                        if len(ds) == 8 and ds.isdigit():
                                            return f"{ds[0:4]}-{ds[4:6]}-{ds[6:8]}"
                                        return ds[:10] if len(ds) >= 10 else ds
                                    last_11_dates_ymd = [_norm_ymd(d) for d in seg_dates]
                                    for i in range(10):
                                        prev = float(seg_closes[i])
                                        curr = float(seg_closes[i + 1])
                                        bias10_i = bias20_i = None
                                        cross_15 = False
                                        if len(closes) >= 19 + i:
                                            ma10_i = sum(closes[-19 - i:-9 - i]) / 10
                                            if ma10_i and ma10_i > 0:
                                                bias10_i = (closes[-10 + i] - ma10_i) / ma10_i * 100
                                        if len(closes) >= 29 + i:
                                            ma20_i = sum(closes[-29 - i:-9 - i]) / 20
                                            if ma20_i and ma20_i > 0:
                                                bias20_i = (closes[-10 + i] - ma20_i) / ma20_i * 100
                                        if len(closes) >= 25 and i >= 0:
                                            close_prev = closes[-11 + i] if i > 0 else closes[-11]
                                            close_curr = closes[-10 + i]
                                            ma15_prev = sum(closes[-25 - i:-10 - i]) / 15 if len(closes) >= 25 + i else None
                                            ma15_curr = sum(closes[-24 - i:-9 - i]) / 15 if len(closes) >= 24 + i else None
                                            if ma15_prev and ma15_curr and close_prev < ma15_prev and close_curr >= ma15_curr:
                                                cross_15 = True
                                        if prev != 0:
                                            pct_val = (curr - prev) / prev * 100
                                            daily.append(f"{pct_val:+.2f}%")
                                            pct10_day_stats.append({
                                                "date_ymd": last_11_dates_ymd[i + 1],
                                                "pct": pct_val,
                                                "bias10": bias10_i,
                                                "bias20": bias20_i,
                                                "cross_15": cross_15,
                                            })
                                        else:
                                            daily.append("--")
                                    pct10_series = " ".join(daily)
                                    # 对应的 10 个交易日日期(左→右:旧→新),仅展示 MM-DD
                                    last_10_dates_ymd = last_11_dates_ymd[1:]
                                    pct10_dates = " ".join(d[5:10] if len(d) >= 10 else d for d in last_10_dates_ymd)
                            except Exception:
                                pct10_series = ""
                                pct10_dates = ""
                                pct10_day_stats = []
                            ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else None
                            ma10 = sum(closes[-10:]) / 10
                            ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
                            near_ma5 = (abs(price - ma5) / ma5 * 100 <= NEAR_PCT) if ma5 and ma5 > 0 else False
                            near_ma10 = (abs(price - ma10) / ma10 * 100 <= NEAR_PCT) if ma10 and ma10 > 0 else False
                            near_ma20 = (abs(price - ma20) / ma20 * 100 <= NEAR_PCT) if ma20 and ma20 > 0 else False
                            logic_list = news_logic_by_code.get(code, [])
                            logic_list = [x for x in logic_list[:2] if x and not _is_logic_boilerplate_only(x)]
                            logic_str = " | ".join(x[:120] for x in logic_list) if logic_list else "-"
                            # 1/5/10/20日均线朝向(向上/向下):用当前均线 vs 上一周期均线近似
                            ma1_dir = "↑" if len(closes) >= 2 and closes[-1] >= closes[-2] else "↓"
                            ma5_dir = "-"
                            ma10_dir = "-"
                            ma20_dir = "-"
                            try:
                                if len(closes) >= 6:
                                    ma5_prev = sum(closes[-6:-1]) / 5
                                    ma5_dir = "↑" if ma5 is not None and ma5 >= ma5_prev else "↓"
                                if len(closes) >= 11:
                                    ma10_prev = sum(closes[-11:-1]) / 10
                                    ma10_dir = "↑" if ma10 is not None and ma10 >= ma10_prev else "↓"
                                if len(closes) >= 21 and ma20 is not None:
                                    ma20_prev = sum(closes[-21:-1]) / 20
                                    ma20_dir = "↑" if ma20 >= ma20_prev else "↓"
                            except Exception:
                                pass
                            ma_judgement = f"MA1{ma1_dir} MA5{ma5_dir} MA10{ma10_dir} MA20{ma20_dir}"
                            bias10_cur = (price - ma10) / ma10 * 100 if ma10 and ma10 > 0 else None
                            bias20_cur = (price - ma20) / ma20 * 100 if ma20 and ma20 > 0 else None
                            volumes_float = [float(x) for x in volumes if x is not None] if volumes else []
                            # 🎯 专家评价所需量化指标
                            # 1. RSI14 (Wilder RSI)
                            def _calc_rsi(_closes, _period=14):
                                if len(_closes) < _period + 1:
                                    return None
                                gains, losses = [], []
                                for _i in range(1, len(_closes)):
                                    _diff = _closes[_i] - _closes[_i - 1]
                                    gains.append(max(_diff, 0))
                                    losses.append(max(-_diff, 0))
                                if len(gains) < _period:
                                    return None
                                _avg_gain = sum(gains[:_period]) / _period
                                _avg_loss = sum(losses[:_period]) / _period
                                for _i in range(_period, len(gains)):
                                    _avg_gain = (_avg_gain * (_period - 1) + gains[_i]) / _period
                                    _avg_loss = (_avg_loss * (_period - 1) + losses[_i]) / _period
                                if _avg_loss == 0:
                                    return 100.0
                                _rs = _avg_gain / _avg_loss
                                return 100.0 - (100.0 / (1.0 + _rs))
                            rsi14 = _calc_rsi(closes, 14)
                            # 2. 超跌度:距最近20日最低点回撤幅度
                            _low_20d = min(closes[-20:]) if len(closes) >= 20 else min(closes)
                            _drawdown_20d = (price - _low_20d) / _low_20d * 100 if _low_20d > 0 else 0
                            # 距60日高点回撤
                            if len(closes) >= 60:
                                _high_60d = max(closes[-60:])
                            else:
                                _high_60d = max(closes)
                            _from_high_60d = (price - _high_60d) / _high_60d * 100 if _high_60d > 0 else 0
                            # 3. 支撑线:MA20, MA60(如有), 近期低点
                            _support_ma20 = ma20
                            _support_ma60 = sum(closes[-60:]) / 60 if len(closes) >= 60 else None
                            _support_low_10d = min(closes[-10:]) if len(closes) >= 10 else min(closes)
                            _nearest_support = min(x for x in [_support_ma20, _support_ma60, _support_low_10d] if x and x > 0)
                            _dist_support_pct = (price - _nearest_support) / _nearest_support * 100 if _nearest_support and _nearest_support > 0 else 0
                            # 4. 资金信号:量比(当日量/20日均量)
                            _vol_today = volumes_float[-1] if volumes_float else 0
                            _vol_ma20 = sum(volumes_float[-20:]) / 20 if len(volumes_float) >= 20 else (sum(volumes_float) / len(volumes_float) if volumes_float else 0)
                            _vol_ratio = _vol_today / _vol_ma20 if _vol_ma20 > 0 else 1.0
                            # 近3日量能趋势
                            if len(volumes_float) >= 5:
                                _v3 = sum(volumes_float[-3:]) / 3
                                _v10 = sum(volumes_float[-10:]) / 10
                                _vol_trend = "放量" if _v3 > _v10 * 1.2 else ("缩量" if _v3 < _v10 * 0.8 else "平量")
                            else:
                                _vol_trend = "-"
                            # 5. 布林带位置 (20日, 2倍标准差)
                            import math as _math
                            if len(closes) >= 20 and ma20:
                                _var = sum((x - ma20) ** 2 for x in closes[-20:]) / 20
                                _std = _math.sqrt(_var)
                                _boll_up = ma20 + 2 * _std
                                _boll_low = ma20 - 2 * _std
                                _boll_pct = (price - _boll_low) / (_boll_up - _boll_low) * 100 if _boll_up != _boll_low else 50
                            else:
                                _boll_pct = 50.0
                            stock_detail_list.append({
                                "name": name or code,
                                "code": code,
                                "pct_10": round(pct_10, 2),
                                "pct10_series": pct10_series,
                                "pct10_dates": pct10_dates,
                                "pct10_day_stats": pct10_day_stats,
                                "bias10": bias10_cur,
                                "bias20": bias20_cur,
                                "cross_15_latest": bool(pct10_day_stats and pct10_day_stats[-1].get("cross_15")),
                                "closes": closes,
                                "volumes": volumes_float,
                                "logic": logic_str,
                                "near_ma5": near_ma5,
                                "near_ma10": near_ma10,
                                "near_ma20": near_ma20,
                                "ma_judge": ma_judgement,
                                "ma1_dir": ma1_dir,
                                "ma5_dir": ma5_dir,
                                "ma10_dir": ma10_dir,
                                "ma20_dir": ma20_dir,
                                "price_gt_ma5": bool(ma5 and price > ma5),
                                "price_gt_ma10": bool(ma10 and price > ma10),
                                "price_gt_ma20": bool(ma20 and price > ma20),
                                "sources": [s for s, _ in news_source_by_code.get(code, {}).most_common(2)]
                                           if news_source_by_code.get(code) else ["综合"],
                                # 🎯 专家评价量化字段
                                "rsi14": round(rsi14, 1) if rsi14 is not None else None,
                                "drawdown_20d": round(_drawdown_20d, 2),       # 距20日低点反弹%
                                "from_high_60d": round(_from_high_60d, 2),     # 距60日高点回撤%
                                "dist_support_pct": round(_dist_support_pct, 2),  # 距最近支撑位%
                                "vol_ratio": round(_vol_ratio, 2),             # 量比
                                "vol_trend": _vol_trend,                       # 放量/缩量/平量
                                "boll_pct": round(_boll_pct, 1),               # 布林位置 0-100
                            })
                        except Exception:
                            continue
                    # 🎯 获取同花顺/东方财富人气排名 + 行业板块 + 概念标签(带重试+降级,不阻塞主流程)
                    ths_hot_map = {}       # code -> 排名 (人气榜)
                    ths_industry_map = {}  # code -> 行业名 (tushare stock_basic)
                    ths_concept_map = {}   # code -> [概念列表] (简化:取同花顺行业前10热门)
                    try:
                        # 1. 东方财富人气榜 (Top 500)
                        try:
                            import akshare as _ak
                            _hot_df = _ak.stock_hot_rank_em()
                            for _, _r in _hot_df.iterrows():
                                _c = str(_r['代码']).replace('SZ', '').replace('SH', '').zfill(6)
                                ths_hot_map[_c] = int(_r['当前排名'])
                        except Exception:
                            pass  # 人气榜拿不到不影响
                        # 2. tushare stock_basic 行业(最快最全)
                        try:
                            import tushare as _ts_mod
                            _ts_token = getattr(self, 'ts_token', None) or os.popen(
                                f"cat {os.path.expanduser('~/.tushare/token')}").read().strip()
                            _pro = _ts_mod.pro_api(_ts_token)
                            _codes = [s['code'].zfill(6) for s in stock_detail_list if s.get('code')]
                            # 批量查 stock_basic
                            _bs_df = _pro.stock_basic(
                                ts_code='', list_status='L',
                                fields='ts_code,symbol,name,industry,market')
                            for _, _r in _bs_df.iterrows():
                                _sym = str(_r['symbol']).zfill(6)
                                if _sym in _codes:
                                    ths_industry_map[_sym] = str(_r.get('industry') or '')
                        except Exception:
                            pass
                        # 3. 同花顺热门概念板块(简化:拉热门行业成分股取前10只的板块)
                        try:
                            import akshare as _ak2
                            _ind_df = _ak2.stock_board_industry_name_ths()
                            # 只取成交额前 15 个热门行业(避免太慢)
                            _top_inds = _ind_df.head(15)['name'].tolist() \
                                if 'name' in _ind_df.columns else []
                            for _ind_name in _top_inds:
                                try:
                                    _cons = _ak2.stock_board_industry_cons_ths(symbol=_ind_name)
                                    for _, _c in _cons.iterrows():
                                        _cc = str(_c.get('代码', '')).zfill(6)
                                        if _cc not in ths_concept_map:
                                            ths_concept_map[_cc] = []
                                        if _ind_name not in ths_concept_map[_cc]:
                                            ths_concept_map[_cc].append(_ind_name)
                                except Exception:
                                    continue
                        except Exception:
                            pass
                    except Exception:
                        pass  # 整体也降级
                    # 把 ths 字段注入 stock_detail_list
                    for s in stock_detail_list:
                        _code = s['code'].zfill(6)
                        s['ths_rank'] = ths_hot_map.get(_code, 0)
                        s['ths_industry'] = ths_industry_map.get(_code, '')
                        s['ths_concepts'] = ths_concept_map.get(_code, [])[:3]  # 最多3个
                    # 找到一份通用的 10 日日期序列,作为表头行
                    pct10_dates_header = ""
                    for s in stock_detail_list:
                        if s.get("pct10_dates"):
                            pct10_dates_header = s["pct10_dates"]
                            break
                    stock_detail_lines = []
                    if pct10_dates_header:
                        stock_detail_lines.append(f"日期(左→右): {pct10_dates_header}")
                    for s in stock_detail_list:
                        # 只显示:股票名(含代码)、最近10日每日涨跌幅序列、MA方向、最近10日总涨跌幅
                        pct10_series_str = s.get("pct10_series", "") or "-"
                        pct10_total = s.get("pct_10", None)
                        pct10_total_str = f"{pct10_total:+.2f}%" if isinstance(pct10_total, (int, float)) else "-"
                        b10 = s.get("bias10")
                        b20 = s.get("bias20")
                        bias10_str = f"{b10:+.2f}%" if isinstance(b10, (int, float)) else "-"
                        bias20_str = f"{b20:+.2f}%" if isinstance(b20, (int, float)) else "-"
                        stock_detail_lines.append(
                            f"{s['name']}({s['code']}) | 最近10日涨跌幅(左→右): {pct10_series_str} | "
                            f"MA朝向: {s['ma_judge']} | 10日乖离: {bias10_str} 20日乖离: {bias20_str} | 最近10日总涨跌幅: {pct10_total_str}"
                        )
                    stock_detail_block = "\n".join(stock_detail_lines) if stock_detail_lines else "(无)"
                    progress_var.set(25)
                    status_label.config(text="正在整理资讯内容...")
                    analysis_window.update()
                    # 2. 整理资讯内容(过滤掉逻辑表头、分析来源、分析时间等不需要的字段后再交给AI)
                    all_content = []
                    for tab_name, content, created_at in news_data:
                        if content and content.strip():
                            cleaned = _strip_logic_boilerplate(content)
                            if cleaned:
                                all_content.append(f"【{tab_name}】({created_at})\n{cleaned[:2000]}")
                    combined_content = "\n\n---\n\n".join(all_content[:30])
                    # 📰 每日资讯选股统计(按日期,把当日被资讯选出的股票及其当日涨跌情况做汇总)
                    result_text.insert(tk.END, "📰 每日资讯选股统计(最近10个交易日,有近10日价格数据的部分)\n", "section")
                    result_text.insert(tk.END, "-" * 40 + "\n")
                    # 先构造:按股票+日期的单日涨跌幅、10/20日乖离率、是否上穿15日线
                    stock_daily_pct = {}
                    stock_daily_bias10 = {}
                    stock_daily_bias20 = {}
                    stock_cross_15 = {}   # code -> set of date_ymd
                    for s in stock_detail_list:
                        code = s.get("code")
                        day_stats = s.get("pct10_day_stats") or []
                        if not code or not day_stats:
                            continue
                        mp = stock_daily_pct.setdefault(code, {})
                        mb10 = stock_daily_bias10.setdefault(code, {})
                        mb20 = stock_daily_bias20.setdefault(code, {})
                        cross_set = stock_cross_15.setdefault(code, set())
                        for ds_item in day_stats:
                            d_ymd = ds_item.get("date_ymd")
                            if not d_ymd:
                                continue
                            pct_val = ds_item.get("pct")
                            if pct_val is not None:
                                mp[d_ymd] = pct_val
                            b10 = ds_item.get("bias10")
                            if b10 is not None:
                                mb10[d_ymd] = b10
                            b20 = ds_item.get("bias20")
                            if b20 is not None:
                                mb20[d_ymd] = b20
                            if ds_item.get("cross_15"):
                                cross_set.add(d_ymd)
                    # 再按日期聚合:每日有哪些股票、有数据的平均涨跌、乖离率、上穿15日线
                    from collections import Counter
                    date_stats = {}       # date_ymd -> list of pct
                    date_stocks = {}      # date_ymd -> ordered list of (name, code)
                    date_freq = {}        # date_ymd -> Counter(code -> 频次)
                    date_bias10_list = {}  # date_ymd -> list of bias10
                    date_bias20_list = {}  # date_ymd -> list of bias20
                    date_cross_15_codes = {}  # date_ymd -> set of code
                    if 'days_data' in locals() and days_data:
                        for day_info in days_data:
                            date_ymd = day_info.get("date_ymd")
                            if not date_ymd:
                                continue
                            stocks_today = day_info.get("stocks", [])
                            names_today = []
                            pcts_today = []
                            bias10_today = []
                            bias20_today = []
                            cross_15_today = set()
                            freq_counter = Counter()
                            seen_codes = set()
                            for name, code in stocks_today:
                                if not code or code in seen_codes:
                                    continue
                                seen_codes.add(code)
                                freq_counter[code] += 1
                                names_today.append((name or code, code))
                                pct_map = stock_daily_pct.get(code, {})
                                pct_val = pct_map.get(date_ymd)
                                if pct_val is not None:
                                    pcts_today.append(pct_val)
                                b10 = stock_daily_bias10.get(code, {}).get(date_ymd)
                                if b10 is not None:
                                    bias10_today.append(b10)
                                b20 = stock_daily_bias20.get(code, {}).get(date_ymd)
                                if b20 is not None:
                                    bias20_today.append(b20)
                                if date_ymd in stock_cross_15.get(code, set()):
                                    cross_15_today.add(code)
                            if names_today:
                                date_stocks[date_ymd] = names_today
                            if pcts_today:
                                date_stats[date_ymd] = pcts_today
                            if freq_counter:
                                date_freq[date_ymd] = freq_counter
                            if bias10_today:
                                date_bias10_list[date_ymd] = bias10_today
                            if bias20_today:
                                date_bias20_list[date_ymd] = bias20_today
                            if cross_15_today:
                                date_cross_15_codes[date_ymd] = cross_15_today
                    if not date_stocks:
                        result_text.insert(tk.END, "最近指定天数内未能找到可用于统计的日期/股票组合(可能缺少近10日日K数据)。\n\n", "info")
                    else:
                        # 只展示最近10个交易日
                        for date_ymd in sorted(date_stocks.keys(), reverse=True)[:10]:
                            names_today = date_stocks.get(date_ymd, [])
                            pcts_today = date_stats.get(date_ymd, [])
                            freq_counter = date_freq.get(date_ymd, Counter())
                            total_n = len(names_today)
                            n_with_pct = len(pcts_today)
                            if n_with_pct > 0:
                                avg_pct = sum(pcts_today) / n_with_pct
                                gt5_list = [p for p in pcts_today if p >= 5]
                                gt0_list = [p for p in pcts_today if p > 0]
                                lt0_list = [p for p in pcts_today if p < 0]
                                lt5_list = [p for p in pcts_today if p <= -5]
                                def _ratio(cnt):
                                    return f"{cnt}/{n_with_pct}({cnt / n_with_pct * 100:.1f}%)" if n_with_pct > 0 else "0/0(0.0%)"
                                line1_prefix = (
                                    f"{date_ymd}  选股数: {total_n},有当日涨跌数据: {n_with_pct};"
                                    f"平均涨跌幅: "
                                )
                                line1_value = f"{avg_pct:+.2f}%"
                                line1_suffix = (
                                    f";>=5%: {_ratio(len(gt5_list))};"
                                    f">0: {_ratio(len(gt0_list))};"
                                    f"<0: {_ratio(len(lt0_list))};"
                                    f"<=-5%: {_ratio(len(lt5_list))}"
                                )
                            else:
                                line1_prefix = f"{date_ymd}  选股数: {total_n};缺少当日涨跌数据,无法统计涨跌分布。"
                                line1_value = ""
                                line1_suffix = ""
                            # 插入第一行:平均涨跌幅值用红/绿颜色
                            result_text.insert(tk.END, line1_prefix, "info")
                            if line1_value:
                                avg_tag = "daily_avg_up" if avg_pct > 0 else ("daily_avg_down" if avg_pct < 0 else "info")
                                result_text.insert(tk.END, line1_value, avg_tag)
                            result_text.insert(tk.END, line1_suffix + "\n", "info")
                            # 10日/20日乖离率统计(当日有数据的股票)
                            bias10_list = date_bias10_list.get(date_ymd, [])
                            bias20_list = date_bias20_list.get(date_ymd, [])
                            if bias10_list or bias20_list:
                                parts = []
                                if bias10_list:
                                    avg10 = sum(bias10_list) / len(bias10_list)
                                    parts.append(f"10日乖离率: 平均{avg10:+.2f}% 最大{max(bias10_list):+.2f}% 最小{min(bias10_list):+.2f}%")
                                if bias20_list:
                                    avg20 = sum(bias20_list) / len(bias20_list)
                                    parts.append(f"20日乖离率: 平均{avg20:+.2f}% 最大{max(bias20_list):+.2f}% 最小{min(bias20_list):+.2f}%")
                                result_text.insert(tk.END, "  " + ";".join(parts) + "\n", "info")
                            cross_15_codes_today = date_cross_15_codes.get(date_ymd, set())
                            # 股票名单:按板块分组排序,每只股后跟板块标签;涨跌着色+频次字号+上穿15日线高亮
                            if names_today:
                                # 为每只股票查板块信息(code -> industry 从 ths_industry_map 取,或从 stock_detail_list 注入的字段取)
                                _code_industry = {}
                                _code_near_ma = {}  # 🎯 code -> [near_ma5/10/20]
                                for s in stock_detail_list:
                                    _c = s['code'].zfill(6)
                                    _code_industry[_c] = s.get('ths_industry') or _code_industry.get(_c, '')
                                    _near = []
                                    if s.get("near_ma5"): _near.append("MA5")
                                    if s.get("near_ma10"): _near.append("MA10")
                                    if s.get("near_ma20"): _near.append("MA20")
                                    if _near:
                                        _code_near_ma[_c] = _near
                                _show_items = names_today[:40]
                                _grouped = {}  # industry -> list of (name, code, pct_val)
                                for _name, _code in _show_items:
                                    _c6 = (_code or '').zfill(6)
                                    _ind = _code_industry.get(_c6) or ths_industry_map.get(_c6) or '未分类'
                                    _pv = stock_daily_pct.get(_c6, {}).get(date_ymd)
                                    _grouped.setdefault(_ind, []).append((_name, _c6, _pv))
                                # 按板块名排序
                                _sorted_inds = sorted(_grouped.keys())
                                _show_cnt = sum(len(v) for v in _grouped.values())
                                _more_cnt = max(0, len(names_today) - _show_cnt)
                                result_text.insert(tk.END, "  📦 按板块分组(每只股附当日被选出逻辑):\n", "info")
                                # 每只股票单独一行显示,带逻辑原因
                                for _ind in _sorted_inds:
                                    _items = _grouped[_ind]
                                    # 板块内按当日涨跌幅降序排
                                    _items.sort(key=lambda x: (x[2] if isinstance(x[2], (int, float)) else 0), reverse=True)
                                    # 板块标题
                                    result_text.insert(tk.END, f"  🏭{_ind} ({len(_items)}只)\n", "ths_industry")
                                    # 板块内股票逐个显示(每只一行)
                                    for _name, _code, _pv in _items:
                                        # 颜色着色(涨跌)
                                        _color = "#000000"
                                        if isinstance(_pv, (int, float)):
                                            _v = max(-10.0, min(10.0, float(_pv)))
                                            _t = (_v + 10.0) / 20.0
                                            _r = int(0 + 255 * _t)
                                            _g = int(128 * (1 - _t))
                                            _b = 0
                                            _color = f"#{_r:02X}{_g:02X}{_b:02X}"
                                        _ctag = f"sc_{_color[1:]}"
                                        result_text.tag_configure(_ctag, foreground=_color)
                                        # 左侧缩进 + 序号
                                        result_text.insert(tk.END, "    • ", "info")
                                        # 股票名(颜色+频次字号)
                                        _f = freq_counter.get(_code, 1)
                                        _mr = max(freq_counter.values()) if freq_counter else 1
                                        _ratio = _f / _mr
                                        if _ratio >= 2/3:
                                            _ftag = "stock_freq_big"
                                        elif _ratio >= 1/3:
                                            _ftag = "stock_freq_mid"
                                        else:
                                            _ftag = "stock_freq_small"
                                        if _code in cross_15_codes_today:
                                            result_text.insert(tk.END, _name, ("stock_cross15", _ftag))
                                        else:
                                            result_text.insert(tk.END, _name, (_ctag, _ftag))
                                        # 当日涨跌幅小标签
                                        if isinstance(_pv, (int, float)):
                                            _pv_str = f" {_pv:+.2f}%"
                                            result_text.insert(tk.END, _pv_str, _ctag)
                                        # 🔥人气 / 📡来源 小标签
                                        if _code in ths_hot_map:
                                            result_text.insert(tk.END, f" 🔥#{ths_hot_map[_code]}", "ths_rank")
                                        _src_counter = news_source_by_code.get(_code)
                                        if _src_counter and hasattr(_src_counter, 'most_common'):
                                            _top_src = _src_counter.most_common(1)[0][0]
                                            result_text.insert(tk.END, f" 📡{_top_src}", "ths_concept")
                                        # 🎯 靠近均线小标签(关键!)
                                        _near_list_daily = _code_near_ma.get(_code, [])
                                        if _near_list_daily:
                                            result_text.tag_configure("near_ma_tag", foreground="#FF6F00", font=("PingFang SC", 13, "bold"))
                                            result_text.insert(tk.END, f" 🎯靠近{'/'.join(_near_list_daily)}", "near_ma_tag")
                                        # 🧠 当日逻辑原因(关键!)
                                        _daily_logic = news_logic_by_code_date.get((_code, date_ymd), [])
                                        if _daily_logic:
                                            result_text.insert(tk.END, "\n      🧠 ", "info")
                                            _logic_str = " | ".join(_daily_logic)[:200]
                                            result_text.insert(tk.END, _logic_str, ("info",))
                                        result_text.insert(tk.END, "\n")  # 股票行尾换行
                                if _more_cnt > 0:
                                    result_text.insert(tk.END, f"  等{_more_cnt}只\n", "info")
                                result_text.insert(tk.END, "\n", "info")
                    # 📊 股票明细多列表格(Treeview):充分利用屏幕宽度,列头可排序
                    result_text.insert(tk.END, "📊 股票明细(列头可点击排序 | 🔥人气 🏭行业 🏷️概念 📡来源)\n", "section")
                    result_text.insert(tk.END, "-" * 40 + "\n")
                    # 在 result_text 下方插入一个 Treeview 表格窗口
                    _tv_frame = ttk.Frame(main_frame)
                    # 找到 result_text 后面的位置插入 — 用 window_create
                    _tv_cols = ("name", "code", "sources", "rank", "industry", "concept", "pct10", "rsi", "boll", "vol", "ma", "ai_rate", "kelly")
                    _tv_headings = {
                        "name": ("股票名", 85),
                        "code": ("代码", 55),
                        "sources": ("📡来源", 90),
                        "rank": ("🔥人气", 60),
                        "industry": ("🏭行业", 90),
                        "concept": ("🏷️概念", 120),
                        "pct10": ("10日涨跌", 75),
                        "rsi": ("RSI14", 60),
                        "boll": ("布林%", 55),
                        "vol": ("量比", 50),
                        "ma": ("MA朝向", 140),
                        "ai_rate": ("🎯AI评级", 70),
                        "kelly": ("💰Kelly", 65),
                    }
                    _tv = ttk.Treeview(_tv_frame, columns=_tv_cols, show="headings", height=min(15, len(stock_detail_list)))
                    for _c in _tv_cols:
                        _h, _w = _tv_headings[_c]
                        _tv.heading(_c, text=_h)
                        _tv.column(_c, width=_w, anchor=tk.CENTER, stretch=True)
                    # 滚动条
                    _tv_sb = ttk.Scrollbar(_tv_frame, orient=tk.VERTICAL, command=_tv.yview)
                    _tv.configure(yscrollcommand=_tv_sb.set)
                    _tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    _tv_sb.pack(side=tk.RIGHT, fill=tk.Y)
                    # 放到 result_text 里 window
                    _win_idx = result_text.index(tk.END)
                    result_text.window_create(_win_idx, window=_tv_frame, stretch=True)
                    result_text.insert(tk.END, "\n\n")
                    # 排序状态
                    _sort_state = {"col": None, "reverse": False}
                    def _tv_sort_by(col):
                        if _sort_state["col"] == col:
                            _sort_state["reverse"] = not _sort_state["reverse"]
                        else:
                            _sort_state["col"] = col
                            _sort_state["reverse"] = False
                        items = [(_tv.set(iid, col), iid) for iid in _tv.get_children("")]
                        try:
                            items.sort(key=lambda v: float(v[0].replace("%", "")) if v[0].replace("%", "").replace(".", "").replace("-", "").isdigit() else v[0], reverse=_sort_state["reverse"])
                        except Exception:
                            items.sort(key=lambda v: v[0], reverse=_sort_state["reverse"])
                        for idx, (_, iid) in enumerate(items):
                            _tv.move(iid, "", idx)
                    for _c in _tv_cols:
                        _tv.heading(_c, command=lambda c=_c: _tv_sort_by(c))
                    # 交替行颜色
                    _tv.tag_configure("odd", background="#F7F9FC")
                    _tv.tag_configure("even", background="white")
                    _tv.tag_configure("up", foreground="#E53935")
                    _tv.tag_configure("down", foreground="#43A047")
                    _tv.tag_configure("cross", foreground="red", font=("PingFang SC", 12, "bold"))
                    _tv.tag_configure("bull", foreground="#E53935", font=("PingFang SC", 12, "bold"))
                    # 🎯 靠近均线的行高亮 tag
                    _tv.tag_configure("near_ma5", background="#FFF8E1")   # 浅黄 — 靠近5日线
                    _tv.tag_configure("near_ma10", background="#E3F2FD") # 浅蓝 — 靠近10日线
                    _tv.tag_configure("near_ma20", background="#FCE4EC") # 浅粉 — 靠近20日线
                    _tv.tag_configure("near_multi", background="#E8F5E9") # 浅绿 — 同时靠近多条均线
                    # 填充数据(按板块+涨跌排序)
                    _sorted_list = sorted(stock_detail_list, key=lambda s: (
                        s.get("ths_industry") or "zzz",
                        -(float(s.get("pct_10") or 0)),
                    ))
                    for _idx, _s in enumerate(_sorted_list):
                        _cross = _s.get("cross_15_latest", False)
                        _bull = _s.get('price_gt_ma5') and _s.get('price_gt_ma10') and _s.get('price_gt_ma20')
                        _pct = float(_s.get("pct_10") or 0)
                        _tag = "cross" if _cross else ("bull" if _bull else ("up" if _pct > 0 else "down" if _pct < 0 else ""))
                        _rows_tag = "even" if _idx % 2 == 0 else "odd"
                        _rsi_s = f"{_s.get('rsi14'):.0f}" if _s.get('rsi14') is not None else "-"
                        # 🎯 靠近均线检测:加行背景色 + MA列标注
                        _near_tags = []
                        if _s.get("near_ma5"):
                            _near_tags.append("near_ma5")
                        if _s.get("near_ma10"):
                            _near_tags.append("near_ma10")
                        if _s.get("near_ma20"):
                            _near_tags.append("near_ma20")
                        if len(_near_tags) >= 2:
                            _near_tags = ["near_multi"]  # 多条均线就用综合高亮
                        # MA朝向列里加"靠近N日线"标注
                        _ma_str = _s.get("ma_judge", "")
                        _near_anns = []
                        if _s.get("near_ma5"): _near_anns.append("🎯MA5")
                        if _s.get("near_ma10"): _near_anns.append("🎯MA10")
                        if _s.get("near_ma20"): _near_anns.append("🎯MA20")
                        if _near_anns:
                            _ma_str = f"{_ma_str} [{'/'.join(_near_anns)}]" if _ma_str else f"[{'/'.join(_near_anns)}]"
                        _all_tags = list(set([_rows_tag, _tag] + _near_tags))
                        _tv.insert("", tk.END, values=(
                            _s.get("name", ""),
                            _s.get("code", ""),
                            "、".join(_s.get("sources", ["综合"])),
                            f"#{_s['ths_rank']}" if _s.get("ths_rank") else "-",
                            _s.get("ths_industry") or "-",
                            " ".join(_s.get("ths_concepts", [])[:2]),
                            f"{_pct:+.2f}%",
                            _rsi_s,
                            f"{_s.get('boll_pct', 0):.0f}%",
                            f"{_s.get('vol_ratio', 0):.1f}",
                            _ma_str,
                            "-",  # AI评级 (AI跑完填充)
                            "-",  # Kelly仓位 (AI跑完填充)
                        ), tags=_all_tags)
                    # 更新 AI prompt 里的股票明细字符串(用 Treeview 里已排序的数据 + 量化指标)
                    _lines_for_ai = []
                    for _s in _sorted_list:
                        _src = "、".join(_s.get("sources", ["综合"]))
                        _ind = _s.get("ths_industry") or "-"
                        _rk = f"#{_s['ths_rank']}" if _s.get("ths_rank") else "-"
                        _rsi = _s.get("rsi14")
                        _rsi_s = f"RSI14:{_rsi}" if _rsi is not None else "RSI:-"
                        _bk = _s.get("boll_pct", 50)
                        _dd = _s.get("from_high_60d", 0)
                        _vs = _s.get("dist_support_pct", 0)
                        _vr = _s.get("vol_ratio", 1.0)
                        _vt = _s.get("vol_trend", "-")
                        # 🎯 靠近均线标注
                        _near_list = []
                        if _s.get("near_ma5"): _near_list.append("MA5")
                        if _s.get("near_ma10"): _near_list.append("MA10")
                        if _s.get("near_ma20"): _near_list.append("MA20")
                        _near_s = f"  ⚠️靠近:{'/'.join(_near_list)}" if _near_list else ""
                        _lines_for_ai.append(
                            f"{_s['name']}({_s['code']}) [{_src}] 行业:{_ind} 人气:{_rk}\n"
                            f"  技术面: 10日涨跌:{_s.get('pct_10', 0):+.2f}% {_s.get('ma_judge', '')} {_rsi} 布林:{_bk:.0f}%{_near_s}\n"
                            f"  资金面: 量比:{_vr}({_vt}) 距支撑:{_vs:+.1f}% 距60日高:{_dd:+.1f}%\n"
                            f"  资讯逻辑: {_s.get('logic', '-')[:150]}"
                        )
                    stock_detail_block = "\n".join(_lines_for_ai)
                    progress_var.set(35)
                    status_label.config(text="正在调用AI进行分析...")
                    analysis_window.update()
                    # 3. 调用AI进行分析
                    result_text.insert(tk.END, "🤖 AI专家评价 & 凯利仓位建议\n", "section")
                    result_text.insert(tk.END, "-" * 40 + "\n")
                    # 📖 术语释义区(帮助理解分析中出现的专业概念)
                    _glossary = (
                        "📖 关键概念速查:\n"
                        "  💰凯利公式(Kelly Criterion): f*=(bp-q)/b | 胜率p、赔率b、q=1-p | 建议用 Kelly值的1/2或1/4保守仓位\n"
                        "  📈双均线策略: MA短金叉MA长=买入信号 | MA短死叉MA长=卖出信号 | 经典组合: MA5/MA20、MA10/MA60\n"
                        "  🏢段基评分(段永平基本面): 7维打分(商业模式/盈利质量/成长性/现金流/安全边际/护城河/估值) 满分105 | ≥80优秀/≥65良好/≥50一般\n"
                        "  🧠芒格5%机会扫描: Charlie Munger「只在胜券在握时下注5%仓位」| 触发条件: 大周期超跌+基本面未坏+市场情绪悲观\n"
                        "  📊RSI14: 14日相对强弱指标 | <30超卖(可能反弹) / >70超买(可能回调)\n"
                        "  🛡️布林带: 中轨=MA20 | 下轨=MA20-2σ(超跌区) | 上轨=MA20+2σ(超买区) | 位置%<20=近下轨\n"
                        "  📦均值回归: 价格偏离均值后有向均值回归的统计特性 | RSI<30 或 布林%<20 时概率更高\n"
                        "  📉乖离率BIAS: (现价-MA)/MA×100% | 正值=在均线上方 / 负值=在均线下方 | 绝对值>15%注意回调\n\n"
                    )
                    result_text.insert(tk.END, _glossary, "info")
                    # 🎯 专家级 AI prompt — 逐股7维评价 + Kelly公式仓位
                    ai_prompt = f"""你是一位拥有30年A股实战经验的资深基金经理,精通技术分析(MA/MACD/RSI/布林带)、基本面估值、资金面研判,擅长凯利公式仓位管理。
请基于以下股票明细(含技术面/资金面/资讯逻辑),对每只股票输出结构化的专家评价。
【股票明细】
{stock_detail_block}
【近期资讯摘要(辅助判断热点和情绪)】
{combined_content[:2000]}
---
## 请按以下格式逐股输出评价(每只控制在 100 字内,严格使用 MARKDOWN 格式):
### [股票名](代码) 🏷️评级:⭐⭐⭐⭐⭐/⭐⭐⭐⭐/⭐⭐⭐/⭐⭐/⭐
| 维度 | 判断 | 依据 |
|------|------|------|
| 💎超跌 | 是/否 | RSI14<30 或 距60日高回撤>20% |
| 📈趋势 | 多头/震荡/空头 | MA5/10/20排列+朝向 |
| 💰资金 | 流入/流出/观望 | 量比+量能趋势 |
| 🔥热点 | 是/否 | 是否属近期热点板块 |
| 🛡️支撑 | 近/远 | 距MA20/MA60/近期低点 |
| 🔄均值回归 | 可能/不可能 | 布林位置<20%或RSI<30% |
| 📰资讯逻辑 | 一句话 | 资讯提及的核心原因 |
🎯 **综合评价**: 一句话总结(看涨/看跌/震荡/观望)
📐 **凯利公式**:
- 胜率 p = 估算该模式下历史胜率(%)
- 赔率 b = 预期盈利% / 预期止损%
- Kelly仓位 f* = (bp - q) / b, 其中 q = 1-p
- 建议仓位: **XX%** (Kelly值的 1/2 或 1/4, 保守起见)
---
## 最后加一个汇总表:
| 股票 | 评级 | 推荐仓位 | 理由 |
|------|------|----------|------|
| xxx | ⭐⭐⭐⭐ | 15% | ... |
然后给出**市场整体判断**和**操作建议**。"""
                    # 尝试调用AI
                    ai_response = None
                    try:
                        # 使用现有的AI配置
                        ai_config = self.ai_config_manager.config
                        api_key = ai_config.get('api_key', '')
                        api_base = ai_config.get('api_base', '')
                        model = ai_config.get('model', 'gpt-3.5-turbo')
                        if api_key:
                            import requests
                            headers = {
                                'Authorization': f'Bearer {api_key}',
                                'Content-Type': 'application/json'
                            }
                            api_url = f"{api_base}/chat/completions" if api_base else "https://api.openai.com/v1/chat/completions"
                            payload = {
                                'model': model,
                                'messages': [
                                    {'role': 'system', 'content': (
                                        '你是一位拥有30年A股实战经验的资深基金经理。'
                                        '精通: K线形态、MA/MACD/RSI/布林带、量价关系、资金流向、龙虎榜、基本面估值、行业周期。'
                                        '擅长凯利公式仓位管理。'
                                        '性格: 理性、独立思考、不随波逐流。只讲数据和逻辑,不用华丽辞藻。'
                                        '输出: 结构化 Markdown, 逐股评价, 包含7维判断 + Kelly仓位建议。'
                                    )},
                                    {'role': 'user', 'content': ai_prompt}
                                ],
                                'temperature': 0.6,
                                'max_tokens': 4000
                            }
                            response = requests.post(api_url, headers=headers, json=payload, timeout=60)
                            if response.status_code == 200:
                                ai_response = response.json()['choices'][0]['message']['content']
                    except Exception as e:
                        print(f"AI调用失败: {e}")
                    progress_var.set(80)
                    if ai_response:
                        # 🎯 解析 AI 返回的评级和 Kelly 仓位,回填 Treeview
                        try:
                            import re as _re
                            _tv_items = _tv.get_children("")
                            _code_to_iid = {}
                            for _iid in _tv_items:
                                _vals = _tv.item(_iid, "values")
                                _code_to_iid[str(_vals[1])] = _iid  # code -> iid
                            # 解析 Markdown 里的 ### 标题行: ### 股票名(代码) 🏷️评级:⭐⭐⭐⭐
                            _pattern_rate = _re.compile(
                                r'###\s+([^\s(]+)\((\d{6})\)[^\n]*?评级[:：]\s*([⭐]{1,5})'
                            )
                            # 解析 建议仓位: **XX%**
                            _pattern_kelly = _re.compile(
                                r'建议仓位[^\d]{0,10}\*\*?(\d{1,3})\s*%'
                            )
                            _lines = ai_response.splitlines()
                            _current_code = None
                            _current_rate = None
                            _current_kelly = None
                            _pending_updates = []
                            for _line in _lines:
                                # 匹配 ### 股票名(代码) 评级
                                _rm = _pattern_rate.search(_line)
                                if _rm:
                                    # 先保存上一只的数据
                                    if _current_code and _current_code in _code_to_iid:
                                        _pending_updates.append((_current_code, _current_rate, _current_kelly))
                                    _current_code = _rm.group(2)
                                    _current_rate = _rm.group(3)
                                    _current_kelly = None
                                    continue
                                # 匹配建议仓位
                                _km = _pattern_kelly.search(_line)
                                if _km and _current_code:
                                    _current_kelly = _km.group(1) + "%"
                            # 保存最后一只
                            if _current_code and _current_code in _code_to_iid:
                                _pending_updates.append((_current_code, _current_rate, _current_kelly))
                            # 应用更新
                            for _code, _rate, _kelly in _pending_updates:
                                _iid = _code_to_iid.get(_code)
                                if _iid:
                                    _vals = list(_tv.item(_iid, "values"))
                                    _vals[11] = _rate or "-"
                                    _vals[12] = _kelly or "-"
                                    _tv.item(_iid, values=_vals)
                        except Exception:
                            pass
                        result_text.insert(tk.END, ai_response + "\n\n")
                    else:
                        # 如果AI调用失败,进行简单的关键词分析
                        result_text.insert(tk.END, "(AI接口未配置或调用失败,使用关键词分析)\n\n", "warning")
                        # 关键词分析
                        all_text = " ".join([c for _, c, _ in news_data if c])
                        # 提取股票名称
                        import re
                        stock_pattern = re.compile(r'[\u4e00-\u9fa5]{2,4}(?:股份|科技|电子|新材|能源|医药|生物|智能|数据)')
                        found_stocks = stock_pattern.findall(all_text)
                        stock_counts = {}
                        for s in found_stocks:
                            stock_counts[s] = stock_counts.get(s, 0) + 1
                        # 关键词统计
                        keywords = {
                            '利好': ['利好', '上涨', '突破', '新高', '涨停', '强势', '龙头', '放量'],
                            '利空': ['利空', '下跌', '跌停', '风险', '减持', '亏损', '警示'],
                            '热点': ['AI', '人工智能', '机器人', '半导体', '芯片', '新能源', '锂电', '光伏', '储能']
                        }
                        keyword_stats = {k: 0 for k in keywords}
                        for category, words in keywords.items():
                            for word in words:
                                keyword_stats[category] += all_text.count(word)
                        result_text.insert(tk.END, "📊 关键词分析:\n")
                        result_text.insert(tk.END, f"  利好相关词: {keyword_stats['利好']} 次\n", "positive")
                        result_text.insert(tk.END, f"  利空相关词: {keyword_stats['利空']} 次\n", "negative")
                        result_text.insert(tk.END, f"  热点板块词: {keyword_stats['热点']} 次\n\n")
                        if stock_counts:
                            result_text.insert(tk.END, "📈 提及频率较高的股票:\n")
                            for stock, count in sorted(stock_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                                result_text.insert(tk.END, f"  • {stock}: {count} 次\n")
                        # 简单情绪判断
                        result_text.insert(tk.END, "\n🎯 简单分析结论:\n")
                        if keyword_stats['利好'] > keyword_stats['利空'] * 1.5:
                            result_text.insert(tk.END, "  市场情绪偏乐观,可适当关注热点板块\n", "positive")
                        elif keyword_stats['利空'] > keyword_stats['利好'] * 1.5:
                            result_text.insert(tk.END, "  市场情绪偏谨慎,建议控制仓位\n", "negative")
                        else:
                            result_text.insert(tk.END, "  市场情绪中性,建议观望为主\n", "warning")
                    # 最后增加:找出A股中符合技术指标的股票(上穿15日线 + 15日线向上 + 放量)
                    result_text.insert(tk.END, "\n" + "=" * 80 + "\n", "info")
                    result_text.insert(tk.END, "📌 符合以下技术指标的A股(本统计池内)\n", "section")
                    result_text.insert(tk.END, "条件:1 股价上穿15日线 2 15日线向上发散 3 放量(成交量较前期明显放大)\n", "info")
                    result_text.insert(tk.END, "-" * 40 + "\n")
                    tech_matches = []
                    for s in stock_detail_list:
                        closes_s = s.get("closes") or []
                        volumes_s = s.get("volumes") or []
                        if len(closes_s) < 16:
                            continue
                        # 1 上穿15日线(最近一日)
                        close_prev = closes_s[-2]
                        close_curr = closes_s[-1]
                        ma15_prev = sum(closes_s[-16:-1]) / 15
                        ma15_curr = sum(closes_s[-15:]) / 15
                        cross_15 = close_prev < ma15_prev and close_curr >= ma15_curr
                        # 2 15日线向上发散
                        ma15_up = ma15_curr > ma15_prev
                        # 3 放量:当日量 > 前5日均量的1.5倍(或前10日均量)
                        volume_surge = False
                        if len(volumes_s) >= 6 and volumes_s[-1] and volumes_s[-1] > 0:
                            avg5 = sum(volumes_s[-6:-1]) / 5
                            if avg5 and avg5 > 0:
                                volume_surge = volumes_s[-1] >= 1.5 * avg5
                        elif len(volumes_s) >= 11 and volumes_s[-1] and volumes_s[-1] > 0:
                            avg10 = sum(volumes_s[-11:-1]) / 10
                            if avg10 and avg10 > 0:
                                volume_surge = volumes_s[-1] >= 1.5 * avg10
                        if cross_15 and ma15_up and volume_surge:
                            tech_matches.append((s.get("name") or s.get("code"), s.get("code")))
                    if tech_matches:
                        for name, code in tech_matches:
                            result_text.insert(tk.END, f"  • {name}({code})\n", "positive")
                        result_text.insert(tk.END, f"共 {len(tech_matches)} 只\n", "info")
                    else:
                        result_text.insert(tk.END, "  暂无同时满足三项条件的股票。\n", "info")
                    result_text.insert(tk.END, "\n", "info")
                    progress_var.set(100)
                    status_label.config(text="分析完成!")
                    result_text.insert(tk.END, "\n" + "=" * 80 + "\n", "info")
                    result_text.insert(tk.END, "报告生成完毕\n", "info")
                    result_text.insert(tk.END, "免责声明: 以上分析仅供参考,不构成投资建议\n", "warning")
                except Exception:
                    import traceback
                    result_text.insert(tk.END, f"\n分析过程中发生错误:\n{traceback.format_exc()}\n", "warning")
                    status_label.config(text="分析失败")
            # 开始分析按钮
            start_btn = ttk.Button(button_frame, text="开始分析", command=lambda: threading.Thread(target=run_analysis, daemon=True).start())
            start_btn.pack(side=tk.RIGHT, padx=(10, 0))
            # 导出按钮
            def export_report():
                content = result_text.get("1.0", tk.END)
                if content.strip():
                    filename = f"资讯AI分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    filepath = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=filename)
                    if filepath:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(content)
                        messagebox.showinfo("成功", f"报告已导出到:\n{filepath}")
            export_btn = ttk.Button(button_frame, text="导出报告", command=export_report)
            export_btn.pack(side=tk.RIGHT, padx=(10, 0))
        except Exception as e:
            messagebox.showerror("错误", f"打开资讯AI分析窗口失败: {e}")

    def _show_stock_analysis_dialog(self, stock_code, stock_name):
        """显示股票分析弹窗(带K线和逻辑)"""
        # 创建分析窗口
        analysis_window = self._toplevel(self.root)
        analysis_window.title(f"股票分析 - {stock_name}({stock_code})")
        analysis_window.geometry("1400x800")
        analysis_window.transient(self.root)
        # 主框架
        main_frame = ttk.Frame(analysis_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # 标题
        ttk.Label(main_frame, text=f"{stock_name}({stock_code})",
                 font=("TkDefaultFont", 14, "bold")).pack(pady=(0, 10))
        # K线图框架
        kline_frame = ttk.LabelFrame(main_frame, text="日K线图(Tushare)", padding=10)
        kline_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        # 同花顺情绪指数日线图(放在日K线图下方)
        sentiment_frame = ttk.LabelFrame(main_frame, text="同花顺情绪指数(日线)", padding=10)
        sentiment_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        # 逻辑显示框架
        logic_frame = ttk.LabelFrame(main_frame, text="逻辑分析", padding=10)
        logic_frame.pack(fill=tk.X)
        logic_text = tk.Text(logic_frame, height=10, wrap=tk.WORD)
        logic_text.pack(fill=tk.BOTH, expand=True)
        logic_text.insert("1.0", "正在加载...")
        # 在后台线程中加载K线图、同花顺情绪指数图与逻辑
        def load_stock_analysis():
            try:
                # 获取日K线数据(Tushare)
                kline_data = self._get_daily_kline_data_tushare(str(stock_code).zfill(6), days=60)
                # 获取同花顺情绪指数日线(Tushare 优先,失败则 AKShare)
                sentiment_data = self._get_ths_sentiment_index_daily(days=60)
                def update_ui():
                    if kline_data:
                        self._draw_daily_kline_chart(kline_frame, kline_data, stock_name)
                        last_close = float(kline_data['data']['收盘'].iloc[-1])
                        logic_content = f"""
股票代码: {stock_code}
股票名称: {stock_name}
技术指标分析:
- 当前价格: {last_close}
- K线周期: 日K(Tushare)
逻辑说明:
[此处可以添加更多分析逻辑]
"""
                    else:
                        ttk.Label(kline_frame, text="无法获取日K线数据(请检查Tushare配置)",
                                 font=("TkDefaultFont", 12), foreground="red").pack(expand=True)
                        logic_content = f"""
股票代码: {stock_code}
股票名称: {stock_name}
技术指标分析:
- K线数据: 获取失败(请检查Tushare配置)
- K线周期: 日K(Tushare)
"""
                    if sentiment_data:
                        self._draw_sentiment_index_chart(sentiment_frame, sentiment_data)
                    else:
                        ttk.Label(sentiment_frame, text="无法获取同花顺情绪指数日线(Tushare 若未提供该指数则已尝试 AKShare,请检查网络)",
                                 font=("TkDefaultFont", 12), foreground="gray").pack(expand=True)
                    logic_text.delete("1.0", tk.END)
                    logic_text.insert("1.0", logic_content)
                self.root.after(0, update_ui)
            except Exception as e:
                import traceback
                traceback.print_exc()
                def show_err(e=e):
                    logic_text.delete("1.0", tk.END)
                    logic_text.insert("1.0", f"加载失败: {e!s}")
                self.root.after(0, show_err)
        threading.Thread(target=load_stock_analysis, daemon=True).start()

    def _run_etf20_analysis(self):
        """🎯 六军会师ETF月度动量轮动策略主逻辑"""
        import datetime as dt
        import time

        import numpy as np
        import tushare as ts

        pro = ts.pro_api()

        # 找最近交易日
        cal = pro.trade_cal(exchange="SSE",
            start_date=(dt.date.today()-dt.timedelta(days=10)).strftime("%Y%m%d"),
            end_date=dt.date.today().strftime("%Y%m%d"), is_open="1")
        trade_date = str(cal["cal_date"].iloc[0])

        results = []
        for etf in self.ETF_POOL:
            tsc = etf["ts_code"]
            # 拉60天K线 (算MA20 + 20日涨幅)
            h = pro.fund_daily(ts_code=tsc,
                start_date=(dt.date.today()-dt.timedelta(days=120)).strftime("%Y%m%d"),
                end_date=trade_date)
            time.sleep(0.2)  # 节流
            if h is None or len(h) < 25:
                continue
            h = h.sort_values("trade_date")
            cl = h["close"].values.astype(float)

            ma20 = float(np.mean(cl[-20:]))
            price = float(cl[-1])
            pct20 = float((price - cl[-20]) / cl[-20] * 100)  # 20日涨幅

            # 绿灯判断
            green = pct20 > 0 and price > ma20

            results.append({
                "code": etf["code"], "name": etf["name"], "role": etf["role"],
                "price": price, "ma20": ma20, "pct20": pct20,
                "green": green, "optional": etf.get("optional", False),
                "ts_code": tsc,
            })

        # 模式判定 (只统计核心6只)
        core = [r for r in results if not r["optional"]]
        green_core = [r for r in core if r["green"]]
        mode = "进攻" if len(green_core) >= 2 else "防御"

        # 调仓方案
        plan = []
        if mode == "进攻":
            # 按20日涨幅排序前2, 各50%
            sorted_green = sorted(green_core, key=lambda x: x["pct20"], reverse=True)
            top2 = sorted_green[:2]
            for e in top2:
                plan.append({"name": e["name"], "code": e["code"], "ratio": 50, "reason": f"20日涨幅{e['pct20']:.1f}% 排前2"})
        else:
            # 防御模式: 黄金518880 + 国债511010
            gold = next((r for r in results if r["code"] == "518880"), None)
            bond = next((r for r in results if r["code"] == "511010"), None)
            gold_green = gold and gold["green"]
            bond_green = bond and bond["green"]
            if gold_green and bond_green:
                plan = [{"name": "黄金ETF", "code": "518880", "ratio": 50, "reason": "双绿灯"},
                        {"name": "国债ETF", "code": "511010", "ratio": 50, "reason": "双绿灯"}]
            elif gold_green:
                plan = [{"name": "黄金ETF", "code": "518880", "ratio": 100, "reason": "仅黄金绿灯"}]
            else:
                plan = [{"name": "国债ETF", "code": "511010", "ratio": 100, "reason": "无绿灯, 安全兜底"}]

        # 回测摘要
        backtest = self._etf20_quick_backtest(pro, results, trade_date)

        # 下月调仓日期
        next_month_first = self._get_next_month_first_trade(pro)

        return {
            "trade_date": trade_date,
            "results": results,  # 每只ETF信号
            "mode": mode,
            "green_count": len(green_core),
            "plan": plan,
            "backtest": backtest,
            "next_signal_date": self._get_month_last_trade(pro),
            "next_rebalance_date": next_month_first,
        }

    def _gather_ai_staff_analyst_context(self):
        """股票分析师:强制使用联网实时数据(不使用程序内旧缓存)并附界面状态。"""
        chunks = []
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        chunks.append(f"【实时联网市场上下文】采集时间:{now_ts}")
        chunks.append("(规则:优先 Tushare/问财/选股通/AKShare 实时链路,不读取旧缓存快照)\n")
        try:
            b = self._collect_quant_market_from_network()
            snap = b.get("snap")
            spot = b.get("spot") or {}
            concept_lines = b.get("concept_lines") or []
            errs = b.get("errors") or []
            chunks.append(
                self._compose_quant_dialog_right_text(
                    snap,
                    spot,
                    concept_lines,
                    network_time=now_ts,
                    network_errors=errs if errs else None,
                )
            )
        except Exception as e:
            chunks.append(f"实时联网拉取失败:{e}\n")
        chunks.append("\n【本程序主界面状态(仅作执行约束,不替代实时行情)】\n")
        try:
            chunks.append(
                f"情绪周期(同花顺三档):{self.ths_sentiment_trend_var.get()}\n"
                f"同花顺情绪指数 · 1日线往上:{self.sentiment_index_ma1_uptrend_var.get()}  "
                f"· 在1日线上:{self.sentiment_index_ma1_above_var.get()}\n"
            )
        except Exception:
            chunks.append("(无法读取界面变量)\n")
        return "\n".join(chunks)

    def show_safety_liquidity_profit_analysis(self):
        """打开安全流动利润综合分析界面,整合三个分析界面的所有按钮"""
        try:
            win = self._toplevel(self.root)
            win.title("安全流动利润综合分析工作台")
            win.geometry("1400x800")
            win.transient(self.root)
            win.resizable(True, True)
            # 存储窗口状态
            win._is_minimized = False
            win._original_geometry = "1400x800"
            win.columnconfigure(0, weight=1)
            win.columnconfigure(1, weight=1)
            win.rowconfigure(1, weight=1)
            # 头部说明
            header = ttk.Label(
                win,
                text="安全流动利润综合分析 - 整合安全、流动性、利润三个维度的分析选项",
                anchor="center",
                font=("Microsoft YaHei", 14, "bold")
            )
            header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
            # 左侧:问题描述
            left_frame = ttk.LabelFrame(win, text="问题描述", padding=10)
            left_frame.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=6)
            left_frame.columnconfigure(0, weight=1)
            left_frame.rowconfigure(1, weight=1)
            problem_text = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD, height=25, font=("TkDefaultFont", 12))
            problem_text.grid(row=1, column=0, sticky="nsew")
            # 右侧:分析结果
            right_frame = ttk.LabelFrame(win, text="分析结果", padding=10)
            right_frame.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=6)
            right_frame.columnconfigure(0, weight=1)
            right_frame.rowconfigure(1, weight=1)
            result_text = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, height=25, font=("TkDefaultFont", 12), state=tk.DISABLED)
            self._enable_clickable_links(result_text)
            result_text.grid(row=1, column=0, sticky="nsew")
            # 底部:所有选项按钮(按分类组织)
            control_frame = ttk.LabelFrame(win, text="分析选项", padding=10)
            control_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
            # 定义所有选项(整合三个界面的选项)
            all_options = {
                "安全": {
                    "同花顺情绪指数": "分析同花顺情绪指数883404的日K、60分钟周期、15分钟周期的情绪判断,以及情绪指数相关的重要指标和分析",
                    "信用风险": "评估交易对手的信用风险,包括公司财务状况、债务水平、违约概率",
                    "市场风险": "评估市场波动带来的风险,包括系统性风险、黑天鹅事件、市场崩盘",
                    "流动性风险": "评估资产变现的难易程度,包括交易量、买卖价差、市场深度",
                    "操作风险": "评估操作失误带来的风险,包括下单错误、系统故障、人为失误",
                    "政策风险": "评估政策变化带来的风险,包括监管政策、税收政策、行业政策",
                    "汇率风险": "评估汇率波动带来的风险,包括外汇敞口、汇率对冲、跨境投资",
                    "集中度风险": "评估投资过于集中带来的风险,包括行业集中、个股集中、地域集中",
                    "杠杆风险": "评估使用杠杆带来的风险,包括融资融券、期货杠杆、衍生品风险",
                    "估值风险": "评估资产估值过高带来的风险,包括PE/PB过高、泡沫风险、价值回归"
                },
                "流动性": {
                    "市场流动性": "评估标的物的市场流动性,包括成交量、换手率、买卖盘深度",
                    "跌停板检查": "检查是否处于跌停板状态,跌停板无法买入,缺乏流动性",
                    "涨停板检查": "检查是否处于涨停板状态,涨停板难以买入,流动性受限",
                    "停牌检查": "检查是否处于停牌状态,停牌期间无法交易,无流动性",
                    "ST股票检查": "检查是否为ST股票,ST股票交易受限,流动性较差",
                    "成交量分析": "分析成交量变化,评估市场参与度和流动性状况",
                    "买卖价差": "分析买卖价差,评估交易成本和流动性质量",
                    "大宗交易": "分析大宗交易情况,评估机构参与度和市场深度",
                    "限售解禁": "分析限售股解禁情况,评估潜在抛压和流动性冲击",
                    "不当投资检查": "检查不当投资情况,如跌停板、停牌、ST等流动性陷阱"
                },
                "利润": {
                    "趋势分析": "分析价格趋势,包括月线MACD双金叉、60分钟短线非死叉、15分钟多头排列",
                    "月线MACD双金叉": "月线级别MACD双金叉,确认长期上涨趋势",
                    "60分钟非死叉": "60分钟级别MACD未死叉,确认中期上涨趋势",
                    "15分钟多头排列": "15分钟级别均线多头排列,确认短期上涨趋势",
                    "技术指标": "综合分析各种技术指标,包括MACD、KDJ、RSI、BOLL等",
                    "量价关系": "分析成交量与价格的关系,确认上涨的有效性",
                    "支撑阻力": "分析关键支撑位和阻力位,确定买入和卖出时机",
                    "形态识别": "识别K线形态,包括头肩底、双底、三角形等反转或持续形态",
                    "资金流向": "分析主力资金流向,确认资金是否流入",
                    "盈利预期": "评估盈利预期,包括目标价位、止损价位、风险收益比"
                }
            }
            # 创建滚动框架
            scroll_frame = ttk.Frame(control_frame)
            scroll_frame.pack(fill=tk.BOTH, expand=True)
            canvas = tk.Canvas(scroll_frame, height=250)
            scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            # 添加鼠标滚轮支持
            def on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            canvas.bind("<MouseWheel>", on_mousewheel)
            scrollable_frame.bind("<MouseWheel>", on_mousewheel)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            # 按分类创建按钮
            buttons_per_row = 5
            row = 0
            for category, options in all_options.items():
                # 分类标题
                category_label = ttk.Label(scrollable_frame, text=f"【{category}】",
                                          font=("TkDefaultFont", 12, "bold"))
                category_label.grid(row=row, column=0, columnspan=buttons_per_row, sticky="w", padx=5, pady=(10, 5))
                row += 1
                # 该分类的选项按钮
                col = 0
                for option_name, option_desc in options.items():
                    # 根据分类选择对应的prompt函数
                    if category == "安全":
                        prompt_func = self._get_safety_prompt
                        system_prompt = "你是一位资深的风险管理专家,精通各种投资安全评估和风险控制方法。"
                    elif category == "流动性":
                        prompt_func = self._get_liquidity_prompt
                        system_prompt = "你是一位资深的流动性分析专家,精通市场流动性和不当投资识别。"
                    else:  # 利润
                        prompt_func = self._get_profit_prompt
                        system_prompt = "你是一位资深的技术分析专家,精通各种技术指标和趋势分析方法。"
                    btn = ttk.Button(
                        scrollable_frame,
                        text=option_name,
                        command=lambda name=option_name, desc=option_desc, pf=prompt_func, sp=system_prompt: self._run_option_analysis(
                            name, desc, problem_text, result_text, pf, sp
                        ),
                        width=18
                    )
                    btn.grid(row=row, column=col, padx=4, pady=3, sticky="ew")
                    col += 1
                    if col >= buttons_per_row:
                        col = 0
                        row += 1
                if col > 0:
                    row += 1
            # 配置列权重
            for i in range(buttons_per_row):
                scrollable_frame.columnconfigure(i, weight=1)
            # 添加通用按钮
            button_frame = ttk.Frame(control_frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            ttk.Button(button_frame, text="AI分析",
                      command=lambda: self._run_ai_analysis(problem_text, result_text,
                      "你是一位资深的多维度投资分析专家,能够从安全、流动性、利润三个维度综合分析投资问题。")).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="清空",
                      command=lambda: self._clear_analysis(problem_text, result_text)).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="复制结果",
                      command=lambda: self._copy_result(result_text)).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="添加到咨询",
                      command=lambda: self._add_to_consultation(result_text)).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="添加到警示",
                      command=lambda: self._add_to_warning(result_text)).pack(side=tk.LEFT, padx=5)
            # 窗口控制按钮
            control_btn_frame = ttk.Frame(win)
            control_btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
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
            messagebox.showerror("错误", f"打开安全流动利润综合分析界面失败: {e}")
            import traceback
            traceback.print_exc()

    def perform_speculator_analysis(self, start_date, end_date, parent_window):
        """执行游资分析
        Args:
            start_date: 起始日期
            end_date: 结束日期
            parent_window: 父窗口
        Returns:
            dict: 分析结果
        """
        # 定义游资名单(根据用户提供的资料)
        speculator_names = {
            '章盟主': ['章盟主', '章建平', '中信证券杭州延安路', '国泰君安上海江苏路'],
            '赵老哥': ['赵老哥', '赵强', '银河证券绍兴营业部'],
            '徐翔': ['徐翔', '宁波涨停板敢死队'],
            '陈小群': ['陈小群', '小群', '小群哥', '群哥'],
            '流沙河': ['流沙河', '喻悌奇'],
            '炒股养家': ['炒股养家', '林广昌', '华鑫证券上海宛平南路'],
            '佛山无影脚': ['佛山无影脚', '廖国沛', '光大证券佛山绿景路'],
            '上海溧阳路孙哥': ['上海溧阳路', '孙哥', '孙煜'],
            '作手新一': ['作手新一', '国泰君安南京太平南路'],
            '小鳄鱼': ['小鳄鱼'],
            '方新侠': ['方新侠'],
            '呼家楼': ['呼家楼', '呼家楼营业部'],
            '宁波桑田路': ['宁波桑田路', '桑田路', '宁波桑田路营业部'],
            '消闲派': ['消闲派', '消闲', '消闲哥'],
            '车库哥': ['车库哥', '车库']
        }
        # 游资梯队、热度、风格信息(根据用户提供的资料)
        # 查询指定日期范围内的资讯
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            # 查询日期范围内的资讯
            cursor.execute('''
                SELECT id, tab_name, content, created_at, updated_at
                FROM news_info
                WHERE (created_at >= ? AND created_at <= ?)
                   OR (updated_at >= ? AND updated_at <= ?)
                ORDER BY created_at DESC
            ''', (
                start_date.strftime("%Y-%m-%d %H:%M:%S"),
                end_date.strftime("%Y-%m-%d %H:%M:%S") + " 23:59:59",
                start_date.strftime("%Y-%m-%d %H:%M:%S"),
                end_date.strftime("%Y-%m-%d %H:%M:%S") + " 23:59:59"
            ))
            news_rows = cursor.fetchall()
            conn.close()
            if not news_rows:
                return {
                    'error': f'在 {start_date.strftime("%Y-%m-%d")} 至 {end_date.strftime("%Y-%m-%d")} 期间未找到资讯数据'
                }
            # 分析结果
            analysis_results = {}
            # 遍历每条资讯,查找游资信息
            for news_id, tab_name, content, created_at, updated_at in news_rows:
                if not content:
                    continue
                # 使用更新时间或创建时间
                news_time = updated_at or created_at
                # 检查每条资讯中是否包含游资信息
                for speculator_key, speculator_keywords in speculator_names.items():
                    # 避免重复添加同一条资讯
                    found_speculator = False
                    for keyword in speculator_keywords:
                        if keyword in content and not found_speculator:
                            # 提取包含游资的句子
                            sentences = re.split(r'[。!?\n]', content)
                            relevant_sentences = []
                            for sentence in sentences:
                                if keyword in sentence:
                                    relevant_sentences.append(sentence.strip())
                            if relevant_sentences:
                                found_speculator = True
                                # 提取股票名称(改进的匹配模式)
                                # 匹配股票代码(如:000001、600000、SZ000001、SH600000)
                                stock_code_pattern = r'[A-Z]{0,2}\d{6}'
                                # 匹配股票名称(2-6个中文字符,可能带股份、集团等后缀)
                                stock_name_pattern = r'[\u4e00-\u9fa5]{2,6}(?:股份|集团|科技|电子|生物|医药|医疗|能源|电力|银行|证券|保险|地产|建设|开发|实业|投资|控股|有限|公司)?'
                                stocks_mentioned = []
                                # 提取股票代码
                                codes = re.findall(stock_code_pattern, content)
                                stocks_mentioned.extend(codes)
                                # 提取股票名称
                                names = re.findall(stock_name_pattern, content)
                                stocks_mentioned.extend(names)
                                # 去重并清理(过滤掉太短或明显不是股票名称的内容)
                                stocks_mentioned = list({
                                    s.strip() for s in stocks_mentioned
                                    if len(s.strip()) >= 2 and s.strip() not in ['股份', '集团', '科技', '电子', '生物', '医药', '医疗', '能源', '电力', '银行', '证券', '保险', '地产', '建设', '开发', '实业', '投资', '控股', '有限', '公司']
                                })
                                if speculator_key not in analysis_results:
                                    analysis_results[speculator_key] = []
                                analysis_results[speculator_key].append({
                                    'time': news_time,
                                    'tab_name': tab_name,
                                    'news_id': news_id,
                                    'sentences': relevant_sentences[:5],  # 最多取5个相关句子
                                    'stocks': stocks_mentioned[:10],  # 最多取10只股票
                                    'content_preview': content[:200] + '...' if len(content) > 200 else content
                                })
                                break  # 找到该游资后,跳出关键词循环
                    if found_speculator:
                        break  # 找到游资后,跳出游资循环,避免同一条资讯被重复添加
            # 如果没有找到游资信息
            if not analysis_results:
                return {
                    'error': f'在 {start_date.strftime("%Y-%m-%d")} 至 {end_date.strftime("%Y-%m-%d")} 期间的资讯中未找到游资相关信息',
                    'total_news': len(news_rows)
                }
            return {
                'results': analysis_results,
                'start_date': start_date.strftime("%Y-%m-%d"),
                'end_date': end_date.strftime("%Y-%m-%d"),
                'total_news': len(news_rows),
                'speculator_count': len(analysis_results)
            }
        except Exception as e:
            return {'error': f'分析失败: {e!s}'}

    def show_speculator_analysis_result(self, result, parent_window):
        """显示游资分析结果
        Args:
            result: 分析结果字典
            parent_window: 父窗口
        """
        # 创建结果显示窗口
        result_window = self._toplevel(parent_window)
        result_window.title("游资分析结果")
        result_window.geometry("1200x800")
        result_window.transient(parent_window)
        # 主框架
        main_frame = ttk.Frame(result_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # 工具栏
        toolbar_frame = ttk.Frame(main_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 10))
        # 保存到资讯按钮
        def save_to_news():
            """保存分析结果到资讯"""
            if 'error' in result:
                messagebox.showwarning("警告", "没有可保存的分析结果", parent=result_window)
                return
            try:
                # 生成分析报告文本
                report_text = "游资分析报告\n"
                report_text += f"分析日期范围: {result.get('start_date', '')} 至 {result.get('end_date', '')}\n"
                report_text += f"分析资讯总数: {result.get('total_news', 0)} 条\n"
                report_text += f"发现游资数量: {result.get('speculator_count', 0)} 个\n"
                report_text += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report_text += "=" * 80 + "\n\n"
                if 'results' in result:
                    for speculator_name, records in result['results'].items():
                        report_text += f"\n【{speculator_name}】\n"
                        report_text += "-" * 80 + "\n"
                        for idx, record in enumerate(records, 1):
                            report_text += f"\n记录 {idx}:\n"
                            report_text += f"时间: {record['time']}\n"
                            report_text += f"来源: {record['tab_name']}\n"
                            report_text += f"相关股票: {', '.join(record['stocks']) if record['stocks'] else '未提及具体股票'}\n"
                            report_text += "相关内容:\n"
                            for sentence in record['sentences']:
                                report_text += f"  - {sentence}\n"
                            report_text += "\n"
                        report_text += "\n" + "=" * 80 + "\n"
                # 保存到资讯数据库
                tab_name = f"游资分析_{result.get('start_date', '')}_{result.get('end_date', '')}"
                if save_news_info_to_db(tab_name, report_text):
                    messagebox.showinfo("成功", f"游资分析结果已保存到资讯数据库: {tab_name}", parent=result_window)
                else:
                    messagebox.showerror("错误", "保存到资讯数据库失败", parent=result_window)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=result_window)
        ttk.Button(toolbar_frame, text="保存到资讯", command=save_to_news, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="关闭", command=result_window.destroy, width=12).pack(side=tk.RIGHT, padx=5)
        # 结果显示区域
        result_notebook = ttk.Notebook(main_frame)
        result_notebook.pack(fill=tk.BOTH, expand=True)
        # 如果有错误
        if 'error' in result:
            error_frame = ttk.Frame(result_notebook)
            result_notebook.add(error_frame, text="错误信息")
            error_text = scrolledtext.ScrolledText(error_frame, wrap=tk.WORD, font=("TkDefaultFont", 12))
            error_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            error_text.insert("1.0", result['error'])
            if 'total_news' in result:
                error_text.insert(tk.END, f"\n\n分析资讯总数: {result['total_news']} 条")
            error_text.config(state=tk.DISABLED)
            return
        # 汇总标签页
        summary_frame = ttk.Frame(result_notebook)
        result_notebook.add(summary_frame, text="汇总")
        summary_text = scrolledtext.ScrolledText(summary_frame, wrap=tk.WORD, font=("TkDefaultFont", 12))
        summary_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        summary_text.insert("1.0", "游资分析报告\n")
        summary_text.insert(tk.END, f"{'='*80}\n\n")
        summary_text.insert(tk.END, f"分析日期范围: {result.get('start_date', '')} 至 {result.get('end_date', '')}\n")
        summary_text.insert(tk.END, f"分析资讯总数: {result.get('total_news', 0)} 条\n")
        summary_text.insert(tk.END, f"发现游资数量: {result.get('speculator_count', 0)} 个\n")
        summary_text.insert(tk.END, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        if 'results' in result:
            summary_text.insert(tk.END, f"{'='*80}\n")
            summary_text.insert(tk.END, "游资统计:\n\n")
            for speculator_name, records in result['results'].items():
                summary_text.insert(tk.END, f"{speculator_name}: {len(records)} 条记录\n")
                # 统计提及的股票
                all_stocks = []
                for record in records:
                    all_stocks.extend(record['stocks'])
                unique_stocks = list(set(all_stocks))
                if unique_stocks:
                    summary_text.insert(tk.END, f"  相关股票: {', '.join(unique_stocks[:10])}")
                    if len(unique_stocks) > 10:
                        summary_text.insert(tk.END, f" 等共 {len(unique_stocks)} 只")
                    summary_text.insert(tk.END, "\n")
                summary_text.insert(tk.END, "\n")
        summary_text.config(state=tk.DISABLED)
        # 为每个游资创建详细标签页
        if 'results' in result:
            for speculator_name, records in result['results'].items():
                detail_frame = ttk.Frame(result_notebook)
                result_notebook.add(detail_frame, text=speculator_name)
                # 创建表格显示
                columns = ("时间", "来源", "相关股票", "内容预览")
                tree = ttk.Treeview(detail_frame, columns=columns, show="headings", height=20)
                for col in columns:
                    tree.heading(col, text=col)
                    if col == "时间":
                        tree.column(col, width=150, anchor=tk.CENTER)
                    elif col == "来源" or col == "相关股票":
                        tree.column(col, width=200)
                    else:
                        tree.column(col, width=400)
                # 添加滚动条
                scrollbar = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL, command=tree.yview)
                tree.configure(yscrollcommand=scrollbar.set)
                # 填充数据
                for record in records:
                    stocks_str = ', '.join(record['stocks'][:5]) if record['stocks'] else '未提及'
                    if len(record['stocks']) > 5:
                        stocks_str += f" 等{len(record['stocks'])}只"
                    preview = record['content_preview']
                    tree.insert("", tk.END, values=(
                        record['time'],
                        record['tab_name'],
                        stocks_str,
                        preview
                    ))
                # 布局
                tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
                # 双击查看详情
                def on_double_click(event, spec_name=speculator_name, recs=records):
                    selection = tree.selection()
                    if selection:
                        tree.item(selection[0])
                        idx = tree.index(selection[0])
                        if 0 <= idx < len(recs):
                            record = recs[idx]
                            # 显示详情窗口
                            detail_window = self._toplevel(result_window)
                            detail_window.title(f"{spec_name} - 详细信息")
                            detail_window.geometry("800x600")
                            detail_window.transient(result_window)
                            detail_text = scrolledtext.ScrolledText(detail_window, wrap=tk.WORD, font=("TkDefaultFont", 12))
                            detail_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                            detail_text.insert("1.0", f"游资: {spec_name}\n")
                            detail_text.insert(tk.END, f"时间: {record['time']}\n")
                            detail_text.insert(tk.END, f"来源: {record['tab_name']}\n")
                            detail_text.insert(tk.END, f"资讯ID: {record['news_id']}\n")
                            detail_text.insert(tk.END, f"\n相关股票: {', '.join(record['stocks']) if record['stocks'] else '未提及具体股票'}\n")
                            detail_text.insert(tk.END, "\n相关内容:\n")
                            detail_text.insert(tk.END, "-" * 80 + "\n")
                            for sentence in record['sentences']:
                                detail_text.insert(tk.END, f"{sentence}\n\n")
                            detail_text.config(state=tk.DISABLED)
                            ttk.Button(detail_window, text="关闭", command=detail_window.destroy).pack(pady=10)
                tree.bind("<Double-1>", on_double_click)

    def _show_opportunity_analysis(self):
        """机会分析:资讯表+股票表+选股通+同花顺前100,20日涨跌幅与三类技术提示,AI 简要分类列出关注股票。"""
        win = self._toplevel(self.root)
        win.title("机会分析 - AI 股评")
        win.geometry("1100x800")
        win.transient(self.root)
        main = ttk.Frame(win, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        ttk.Label(main, text="📊 机会分析:资讯表+股票表+选股通+同花顺前100;按连续下跌/回靠均线/上穿15日线等技术信号列出股票与最近10日涨跌幅", font=("TkDefaultFont", 11, "bold")).pack(pady=(0, 5))
        # 顶部按钮栏:进度条 + 状态 + 保存到资讯表
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(main, variable=progress_var, length=400, mode='determinate')
        progress_bar.pack(fill=tk.X, pady=(0, 5))
        status_label = ttk.Label(main, text="准备中...")
        status_label.pack(pady=(0, 5))
        result_text = scrolledtext.ScrolledText(main, wrap=tk.WORD, font=("TkDefaultFont", 12))
        result_text.pack(fill=tk.BOTH, expand=True)
        result_text.tag_configure("title", font=("TkDefaultFont", 12, "bold"), foreground="blue")
        result_text.tag_configure("section", font=("TkDefaultFont", 11, "bold"), foreground="green")
        result_text.tag_configure("positive", foreground="red")
        result_text.tag_configure("negative", foreground="green")
        result_text.tag_configure("alert_red", font=("TkDefaultFont", 12, "bold"), foreground="red")
        result_text.tag_configure("alert_blue", font=("TkDefaultFont", 12, "bold"), foreground="blue")
        result_text.tag_configure("alert_yellow", font=("TkDefaultFont", 12, "bold"), foreground="dark orange")
        result_text.tag_configure("alert_green", font=("TkDefaultFont", 12, "bold"), foreground="green")
        def save_opportunity_to_news():
            """将当前机会分析结果保存到资讯表,便于后续统一分析。"""
            try:
                content = result_text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showinfo("提示", "当前没有可保存的分析内容。", parent=win)
                    return
                tab_name = "机会分析_AI简要分类"
                if save_news_info_to_db(tab_name, content):
                    messagebox.showinfo("成功", "已将机会分析结果保存到资讯表。", parent=win)
                else:
                    messagebox.showerror("错误", "保存到资讯表失败。", parent=win)
            except Exception as e:
                messagebox.showerror("错误", f"保存到资讯表失败: {e}", parent=win)
        toolbar = ttk.Frame(main)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(toolbar, text="保存到资讯表", command=save_opportunity_to_news, width=14).pack(side=tk.LEFT, padx=(0, 5))
        def run_in_thread():
            try:
                def update_status(msg, pct=None):
                    if pct is not None:
                        self.root.after(0, lambda: progress_var.set(pct))
                    self.root.after(0, lambda: status_label.config(text=msg))
                update_status("正在收集资讯表、股票表、选股通、同花顺数据...", 3)
                stocks_by_code = {}
                try:
                    # 资讯表部分:改为最近20天
                    days_data = get_news_stocks_by_date_and_frequency(ndays=20)
                    for day_info in days_data:
                        for name, code in day_info.get("stocks", []):
                            if code and code not in stocks_by_code:
                                stocks_by_code[code] = name
                except Exception as e:
                    print(f"机会分析-资讯表: {e}")
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cur = conn.cursor()
                    cur.execute("SELECT DISTINCT stock_code, stock_name FROM stock_data WHERE stock_code IS NOT NULL AND stock_code != ''")
                    for code, name in cur.fetchall():
                        if code and code not in stocks_by_code:
                            stocks_by_code[code] = (name or "").strip() or code
                    # 同花顺排名前100:取最近保存日期的前100条
                    cur.execute("SELECT stock_code, stock_name FROM ths_realtime_data WHERE save_date = (SELECT MAX(save_date) FROM ths_realtime_data) ORDER BY change_pct DESC LIMIT 100")
                    for code, name in cur.fetchall():
                        if code and code not in stocks_by_code:
                            stocks_by_code[code] = (name or "").strip() or code
                    conn.close()
                except Exception as e:
                    print(f"机会分析-股票表/同花顺: {e}")
                # 选股通/龙头股:持仓2
                for name, code, _, _ in self._get_all_holding_stocks():
                    if code and code not in stocks_by_code:
                        stocks_by_code[code] = (name or "").strip() or code
                if not stocks_by_code:
                    self.root.after(0, lambda: result_text.insert(tk.END, "资讯表、股票表、同花顺中暂无股票数据,请先添加或爬取。\n", "section"))
                    return
                update_status("正在统计各股10日/20日涨跌幅及技术信号...", 10)
                stock_stats = []
                alert_fall = []   # 连续下跌5~10日 -> 红色
                alert_near_ma = []  # 回靠10/20日线 -> 蓝色
                alert_cross_ma15 = []  # 上穿15日线 -> 黄色
                alert_cross_ma60_up = []  # 60日线上行且股价上穿60日线
                alert_cross_ma20_up = []  # 20日线上行且股价上穿20日线
                all_codes = list(stocks_by_code.items())
                for code, name in all_codes[:150]:
                    try:
                        # 为了计算60日线方向与上穿情况,这里取最近70天数据
                        result = self._fetch_recent_daily_closes(code, days=70, source="default", token=self.ts_token, return_volume=False)
                        if not isinstance(result, tuple) or len(result) < 2:
                            continue
                        _, closes = result[0], result[1]
                        closes = [float(x) for x in closes if x is not None]
                        if len(closes) < 60:
                            continue
                        name_disp = name or code
                        last_close = closes[-1] if closes else 0
                        # 预先计算常用均线(用于开新仓条件判断与展示)
                        ma5_curr = sum(closes[-5:]) / 5 if len(closes) >= 5 else None
                        ma5_prev = sum(closes[-6:-1]) / 5 if len(closes) >= 6 else None
                        ma10_curr = sum(closes[-10:]) / 10 if len(closes) >= 10 else None
                        ma10_prev = sum(closes[-11:-1]) / 10 if len(closes) >= 11 else None
                        ma20_curr = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
                        ma20_prev = sum(closes[-21:-1]) / 20 if len(closes) >= 21 else None
                        pct_20 = (closes[-1] - closes[-21]) / closes[-21] * 100 if len(closes) >= 21 and closes[-21] and closes[-21] != 0 else 0
                        pct_10 = (closes[-1] - closes[-11]) / closes[-11] * 100 if len(closes) >= 11 and closes[-11] and closes[-11] != 0 else 0
                        in_fall = in_near = in_cross = False
                        in_cross60_up = in_cross20_up = False
                        # 1) 连续下跌5~10天
                        consec = 0
                        for j in range(len(closes) - 1, 0, -1):
                            if closes[j] < closes[j - 1]:
                                consec += 1
                            else:
                                break
                        if 5 <= consec <= 10:
                            alert_fall.append(f"{name_disp}({code})")
                            in_fall = True
                        # 2) 回靠10日线或20日线(当前价与均线距离在±2%内)
                        if len(closes) >= 10:
                            ma10 = sum(closes[-10:]) / 10
                            dist10 = (closes[-1] - ma10) / ma10 * 100 if ma10 and ma10 != 0 else 999
                            if -2 <= dist10 <= 2:
                                alert_near_ma.append(f"{name_disp}({code})")
                                in_near = True
                        if len(closes) >= 20 and not in_near:
                            ma20 = sum(closes[-20:]) / 20
                            dist20 = (closes[-1] - ma20) / ma20 * 100 if ma20 and ma20 != 0 else 999
                            if -2 <= dist20 <= 2:
                                alert_near_ma.append(f"{name_disp}({code})")
                                in_near = True
                        # 3) 上穿15日线(前一日收在15日线下,当日收在15日线上)
                        if len(closes) >= 16:
                            ma15_prev = sum(closes[-16:-1]) / 15
                            ma15_curr = sum(closes[-15:]) / 15
                            if closes[-2] < ma15_prev and closes[-1] > ma15_curr:
                                alert_cross_ma15.append(f"{name_disp}({code})")
                                in_cross = True
                        # 4) 60日线向上,且股价上穿60日线
                        if len(closes) >= 61:
                            ma60_prev = sum(closes[-61:-1]) / 60
                            ma60_curr = sum(closes[-60:]) / 60
                            if ma60_curr > ma60_prev and closes[-2] < ma60_prev and closes[-1] > ma60_curr:
                                alert_cross_ma60_up.append(f"{name_disp}({code})")
                                in_cross60_up = True
                        # 5) 20日线向上,且股价上穿20日线
                        if len(closes) >= 21:
                            ma20_prev = sum(closes[-21:-1]) / 20
                            ma20_curr = sum(closes[-20:]) / 20
                            if ma20_curr > ma20_prev and closes[-2] < ma20_prev and closes[-1] > ma20_curr:
                                alert_cross_ma20_up.append(f"{name_disp}({code})")
                                in_cross20_up = True
                        stock_stats.append({
                            "code": code,
                            "name": name_disp,
                            "pct_10": round(pct_10, 2),
                            "pct_20": round(pct_20, 2),
                            "last_close": round(last_close, 2),
                            "ma5_curr": round(ma5_curr, 4) if ma5_curr is not None else None,
                            "ma5_prev": round(ma5_prev, 4) if ma5_prev is not None else None,
                            "ma10_curr": round(ma10_curr, 4) if ma10_curr is not None else None,
                            "ma10_prev": round(ma10_prev, 4) if ma10_prev is not None else None,
                            "ma20_curr": round(ma20_curr, 4) if ma20_curr is not None else None,
                            "ma20_prev": round(ma20_prev, 4) if ma20_prev is not None else None,
                            "in_fall": in_fall,
                            "in_near": in_near,
                            "in_cross": in_cross,
                            "in_cross60_up": in_cross60_up,
                            "in_cross20_up": in_cross20_up,
                        })
                    except Exception:
                        continue
                stock_stats.sort(key=lambda x: x["pct_20"], reverse=True)
                # ===== 开新仓条件自动判断(机会按钮按下时)=====
                def _safe_float(v, default=0.0):
                    try:
                        return float(v)
                    except Exception:
                        return default
                # 全局条件:用主界面状态替代"情绪指数勾选框"
                main_total_score = 0
                try:
                    if hasattr(self, "total_score_var") and self.total_score_var is not None:
                        score_text = str(self.total_score_var.get()).replace("总分:", "").replace("总分", "").strip()
                        main_total_score = int(score_text) if score_text.isdigit() else int(float(score_text))
                except Exception:
                    main_total_score = 0
                main_position = 0.0
                try:
                    if hasattr(self, "position_vars") and isinstance(self.position_vars, dict):
                        v = self.position_vars.get("result")
                        if v is not None:
                            position_text = str(v.get()).replace("+", "").replace("%", "").strip()
                            main_position = _safe_float(position_text, 0.0)
                except Exception:
                    main_position = 0.0
                allow_new_position_by_market = None
                try:
                    if hasattr(self, "new_position_button") and self.new_position_button is not None:
                        allow_new_position_by_market = (str(self.new_position_button.cget("state")) == "normal")
                except Exception:
                    allow_new_position_by_market = None
                def eval_open_new_position(s, mode="simplified"):
                    """
                    mode:
                      simplified -> 对齐"朋友/绩优股/均值回归"规则:只看20日线(站上+向上)
                      full       -> 对齐"龙头/强势股"规则:看1/5/10/20站上+均线向上(用日线近似) + 多头发散(用 ma5>ma10>ma20 近似)
                    """
                    reasons = []
                    passed = True
                    code = s.get("code")
                    name = s.get("name")
                    # 价格:优先实时最新价,否则最新收盘价
                    current_price = None
                    price_src = "收盘"
                    try:
                        spot_row = get_realtime_spot_row(code)
                        if spot_row is not None:
                            v = spot_row.get("最新价", None)
                            if v is not None:
                                current_price = float(v)
                                price_src = "实时"
                    except Exception:
                        current_price = None
                    if not current_price or current_price <= 0:
                        current_price = _safe_float(s.get("last_close", 0), 0.0)
                        price_src = "收盘"
                    last_close_local = _safe_float(s.get("last_close", 0), 0.0)
                    ma5_curr_l = s.get("ma5_curr")
                    ma5_prev_l = s.get("ma5_prev")
                    ma10_curr_l = s.get("ma10_curr")
                    ma10_prev_l = s.get("ma10_prev")
                    ma20_curr_l = s.get("ma20_curr")
                    ma20_prev_l = s.get("ma20_prev")
                    # 条件1:主界面总分 > 40
                    if main_total_score <= 40:
                        passed = False
                        reasons.append(f"主界面总分 {main_total_score} <= 40")
                    # 条件2:主界面仓位 >= 30%
                    if main_position < 30:
                        passed = False
                        reasons.append(f"主界面仓位 {main_position:.1f}% < 30%")
                    # 条件3:主界面"可以开新仓"状态(由情绪/周期控制按钮 enable/disable)
                    if allow_new_position_by_market is False:
                        passed = False
                        reasons.append("当前情绪/周期状态:禁止开新仓(主界面按钮为灰色)")
                    # 条件4:均线(按开新仓对话框逻辑近似到日线)
                    if mode == "simplified":
                        if ma20_curr_l is None or ma20_prev_l is None or ma20_curr_l <= 0:
                            passed = False
                            reasons.append("20日线数据不足")
                        else:
                            if current_price <= float(ma20_curr_l):
                                passed = False
                                reasons.append(f"未站上20日线({price_src}价{current_price:.2f} <= MA20{float(ma20_curr_l):.2f})")
                            if float(ma20_curr_l) <= float(ma20_prev_l):
                                passed = False
                                reasons.append(f"20日线未向上(MA20{float(ma20_curr_l):.2f} <= 前一周期{float(ma20_prev_l):.2f})")
                    else:
                        # 1日线:用最新收盘价作为 MA1
                        if last_close_local <= 0:
                            passed = False
                            reasons.append("最新收盘价缺失,无法判断1日线")
                        else:
                            if current_price <= last_close_local:
                                passed = False
                                reasons.append(f"未站上1日线({price_src}价{current_price:.2f} <= 收盘{last_close_local:.2f})")
                        # 5/10/20
                        for (label, curr, prev) in (("5", ma5_curr_l, ma5_prev_l), ("10", ma10_curr_l, ma10_prev_l), ("20", ma20_curr_l, ma20_prev_l)):
                            if curr is None or prev is None or float(curr) <= 0:
                                passed = False
                                reasons.append(f"{label}日线数据不足")
                                continue
                            if current_price <= float(curr):
                                passed = False
                                reasons.append(f"未站上{label}日线({price_src}价{current_price:.2f} <= MA{label}{float(curr):.2f})")
                            if float(curr) <= float(prev):
                                passed = False
                                reasons.append(f"MA{label}未向上(MA{label}{float(curr):.2f} <= 前一周期{float(prev):.2f})")
                        # 多头发散:用 ma5>ma10>ma20 近似(替代原60分钟/15分钟发散勾选)
                        try:
                            if ma5_curr_l is None or ma10_curr_l is None or ma20_curr_l is None:
                                passed = False
                                reasons.append("无法判断多头发散(MA5/10/20不足)")
                            else:
                                if not (float(ma5_curr_l) > float(ma10_curr_l) > float(ma20_curr_l)):
                                    passed = False
                                    reasons.append(f"未满足多头发散近似条件(MA5{float(ma5_curr_l):.2f} > MA10{float(ma10_curr_l):.2f} > MA20{float(ma20_curr_l):.2f} 不成立)")
                        except Exception:
                            passed = False
                            reasons.append("无法判断多头发散(计算异常)")
                    # 条件5:凯利公式(原流程为人工确认,这里提示需要补充)
                    reasons.append("凯利公式:机会分析无法自动确认(需你在开新仓流程里计算/勾选)")
                    return {
                        "passed": passed,
                        "price": current_price,
                        "price_src": price_src,
                        "reasons": reasons,
                        "name": name,
                        "code": code,
                    }
                open_ok_simplified = []
                open_no_simplified = []
                open_ok_full = []
                open_no_full = []
                for s in stock_stats[:80]:
                    r1 = eval_open_new_position(s, mode="simplified")
                    (open_ok_simplified if r1["passed"] else open_no_simplified).append(r1)
                    r2 = eval_open_new_position(s, mode="full")
                    (open_ok_full if r2["passed"] else open_no_full).append(r2)
                def _fmt_open_line(r):
                    rs = ";".join(r.get("reasons", [])[:4])
                    return f"- {r['name']}({r['code']}) {r['price_src']}价:{r['price']:.2f} | {rs}"
                open_analysis_block = []
                open_analysis_block.append("【开新仓条件筛选(机会按钮自动分析)】")
                open_analysis_block.append(f"全局条件:主界面总分>40(当前{main_total_score});主界面仓位>=30%(当前{main_position:.1f}%);情绪/周期允许开新仓(主界面按钮状态={allow_new_position_by_market})")
                open_analysis_block.append("说明:原“龙头/强势股“流程里的60分钟/15分钟多头发散,这里用日线 MA5>MA10>MA20 近似;凯利公式仍需在开新仓流程里人工确认。")
                open_analysis_block.append("")
                open_analysis_block.append("A) 朋友/绩优股/均值回归(简化:站上20日线 + 20日线上行)")
                open_analysis_block.append("可以开新仓(满足自动条件):")
                for r in open_ok_simplified[:25]:
                    open_analysis_block.append(_fmt_open_line(r))
                if not open_ok_simplified:
                    open_analysis_block.append("(无)")
                open_analysis_block.append("不可以开新仓(失败原因截断展示):")
                for r in open_no_simplified[:25]:
                    open_analysis_block.append(_fmt_open_line(r))
                open_analysis_block.append("")
                open_analysis_block.append("B) 龙头/强势股(完整:站上1/5/10/20 + 均线上行 + 多头发散近似)")
                open_analysis_block.append("可以开新仓(满足自动条件):")
                for r in open_ok_full[:25]:
                    open_analysis_block.append(_fmt_open_line(r))
                if not open_ok_full:
                    open_analysis_block.append("(无)")
                open_analysis_block.append("不可以开新仓(失败原因截断展示):")
                for r in open_no_full[:25]:
                    open_analysis_block.append(_fmt_open_line(r))
                open_analysis_text = "\n".join(open_analysis_block)
                update_status("正在读取资讯表逻辑(按股票匹配)...", 22)
                news_logic_by_code = {}
                news_summary = ""
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cur = conn.cursor()
                    twenty_days_ago = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
                    cur.execute("SELECT tab_name, content, created_at FROM news_info WHERE created_at >= ? ORDER BY created_at DESC LIMIT 60", (twenty_days_ago,))
                    rows = cur.fetchall()
                    if not rows:
                        cur.execute("SELECT tab_name, content, created_at FROM news_info ORDER BY created_at DESC LIMIT 60")
                        rows = cur.fetchall()
                    for tab_name, content, created_at in rows:
                        if content and content.strip():
                            news_summary += f"【{tab_name}】({created_at[:10]})\n{content[:2000]}\n\n"
                            for code, name in list(stocks_by_code.items())[:120]:
                                name_d = (name or code).strip()
                                if code in content or (name_d and name_d in content):
                                    snippet = content[:400].replace("\n", " ").strip() if content else ""
                                    if code not in news_logic_by_code:
                                        news_logic_by_code[code] = []
                                    if len(news_logic_by_code[code]) < 2:
                                        news_logic_by_code[code].append(f"[{tab_name}]{snippet[:200]}")
                    conn.close()
                except Exception as e:
                    news_summary = f"读取资讯失败: {e}\n"
                if AKSHARE_AVAILABLE:
                    try:
                        import akshare as ak
                        df = safe_call(ak.stock_board_concept_name_em, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_em")
                        if df is not None and not df.empty and '涨跌幅' in df.columns and '板块名称' in df.columns:
                            df = df.sort_values('涨跌幅', ascending=False).head(25)
                            "\n".join([f"  {row['板块名称']}: {row['涨跌幅']}%" for _, row in df.iterrows()])
                    except Exception:
                        pass
                # 股票明细:每只显示 最近10日涨跌幅、资讯表逻辑、三类提示标记
                stock_detail_lines = []
                for s in stock_stats[:80]:
                    logic_list = news_logic_by_code.get(s["code"], [])
                    logic_str = " | ".join(x[:100] for x in logic_list[:2]) if logic_list else "-"
                    tags = []
                    if s["in_fall"]:
                        tags.append("连续下跌5~10日")
                    if s["in_near"]:
                        tags.append("回靠10/20日线")
                    if s["in_cross"]:
                        tags.append("上穿15日线")
                    tag_str = " | ".join(tags) if tags else "-"
                    # 在股票名称右侧显示最新收盘价
                    stock_detail_lines.append(
                        f"{s['name']}({s['code']}) 收盘价:{s.get('last_close', 0):.2f} | 最近10日涨跌幅{s['pct_10']:+.2f}% | "
                        f"20日涨跌幅{s['pct_20']:+.2f}% | 资讯逻辑: {logic_str} | 提示: {tag_str}"
                    )
                stock_detail_block = "\n".join(stock_detail_lines) if stock_detail_lines else "(无)"
                update_status("正在生成 AI 简要机会列表...", 45)
                prompt = f"""你是一位资深股评员。下面给出的是从资讯表、股票表、每天选股通数据以及同花顺排名前100中筛选出的部分股票。
注意:**所有技术信号(连续下跌、回靠均线、上穿15日线)已经由程序根据股票日K数据和均线计算完毕**,你不需要、也不能再根据文字主观判断股票是否满足条件,只能按给定的"提示类型"或分类名单进行整理和概括。
【一、股票明细(含最近10日/20日涨跌幅、资讯逻辑、技术提示标记)】
每行格式:股票名(代码) | 最近10日涨跌幅 | 20日涨跌幅 | 资讯逻辑 | 提示类型
{stock_detail_block}
【二、技术面三类原始名单(供你参考,可自行增删)】
1) 连续调整下跌5~10天: {', '.join(alert_fall[:25]) if alert_fall else '(无)'}
2) 回靠10日线或20日线: {', '.join(alert_near_ma[:25]) if alert_near_ma else '(无)'}
3) 上穿15日线: {', '.join(alert_cross_ma15[:25]) if alert_cross_ma15 else '(无)'}
4) 60日线向上且股价上穿60日线: {', '.join(alert_cross_ma60_up[:25]) if alert_cross_ma60_up else '(无)'}
5) 20日线向上且股价上穿20日线: {', '.join(alert_cross_ma20_up[:25]) if alert_cross_ma20_up else '(无)'}
请你根据以上数据,输出一个**简短的结果列表**,格式严格按照下面要求:
1 第一部分标题写「一、连续下跌5天以上」,下面每行列出一只股票:
   股票名(代码) 最近10日涨跌幅X.XX%
   (只列出确实满足"连续下跌5~10天"的股票,数量不要太多,可以挑重点)
2 第二部分标题写「二、回靠均线(5/10/20日)」,下面每行列出一只股票:
   股票名(代码) 最近10日涨跌幅X.XX%
   (只列出当前股价回靠5日线、10日线或20日线附近的股票)
3 第三部分标题写「三、股价上穿15日线」,下面每行列出一只股票:
   股票名(代码) 最近10日涨跌幅X.XX%
   (只列出最近出现股价上穿15日线信号的股票)
附加要求:
- 在上述三部分列表的前面或后面,增加一小节「四、主线板块与龙头股」,用 3-5 段话概括:最近的主线板块(可以结合资讯逻辑、股票所属板块等信息进行归纳)、每个主线板块中最具代表性的1-3只龙头股,以及整体资金流入情况(如:样本中属于该板块的股票总数、其中涨停的有多少、涨幅>5%的有多少、哪只股最先涨停或最早启动)。
- 可在适当位置补充两类"趋势性信号"的简要统计:一类是60日线向上且股价上穿60日线的股票;另一类是20日线向上且股价上穿20日线的股票,可与前面三类信号进行对比分析。
- 不需要长篇大论,不要超过约2000字,重点是**列清楚三类(或拓展为五类)股票+最近10日涨跌幅**,并补充对主线板块及龙头股资金活跃度的概括性描述。
- 对每只股票,如能简单结合"资讯逻辑"给出一句简短点评更好,但请保持精简。"""
                system_prompt = "你是资深 A 股股评员。技术信号(连续下跌5~10日、回靠均线、上穿15日线)已由外部程序基于股票价格和均线精确计算好,你只负责根据这些既定标签做分类、排序和简要点评,不要再凭主观文字重新判断股票是否满足条件。中文输出,尽量简短清晰。"
                # 为机会分析单独限制 max_tokens、适当提高超时时间,降低超时概率
                provider_config = self.ai_config_manager.get_active_provider_config() or {}
                config_override = dict(provider_config) if provider_config else None
                if config_override:
                    # 控制生成长度,避免过长导致超时
                    if not config_override.get("max_tokens") or config_override.get("max_tokens", 0) > 2000:
                        config_override["max_tokens"] = 1500
                    # 给一点缓冲,避免接口偶发慢
                    config_override["timeout"] = max(int(config_override.get("timeout", 60)), 90)
                ai_result = self.call_ai_model(prompt, system_prompt=system_prompt, config_override=config_override)
                update_status("分析完成", 100)
                def show_result():
                    result_text.delete("1.0", tk.END)
                    result_text.insert(tk.END, "=" * 60 + "\n", "section")
                    result_text.insert(tk.END, "📊 机会分析 - AI 简要分类(连续下跌 / 回靠均线 / 上穿15日线)\n", "title")
                    result_text.insert(tk.END, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n", "section")
                    result_text.insert(tk.END, "=" * 60 + "\n\n")
                    # 先输出开新仓筛选(程序判断 + 条件过程)
                    try:
                        result_text.insert(tk.END, open_analysis_text + "\n\n", "section")
                    except Exception:
                        pass
                    if not ai_result or ai_result.startswith(("错误", "API")):
                        # 如果 AI 失败,则用本地数据直接列出三类股票,保证有结果
                        result_text.insert(tk.END, (ai_result or "AI 调用失败,改用本地数据生成列表。\n") + "\n", "negative")
                        result_text.insert(tk.END, "一、连续下跌5天以上\n", "alert_red")
                        for s in stock_stats:
                            if s.get("in_fall"):
                                result_text.insert(tk.END, f"  {s['name']}({s['code']}) 最近10日涨跌幅{s['pct_10']:+.2f}%\n")
                        result_text.insert(tk.END, "\n二、回靠均线(5/10/20日)\n", "alert_blue")
                        for s in stock_stats:
                            if s.get("in_near"):
                                result_text.insert(tk.END, f"  {s['name']}({s['code']}) 最近10日涨跌幅{s['pct_10']:+.2f}%\n")
                        result_text.insert(tk.END, "\n三、股价上穿15日线\n", "alert_yellow")
                        for s in stock_stats:
                            if s.get("in_cross"):
                                result_text.insert(tk.END, f"  {s['name']}({s['code']}) 最近10日涨跌幅{s['pct_10']:+.2f}%\n")
                        result_text.insert(tk.END, "\n四、60日线向上且股价上穿60日线\n", "alert_blue")
                        for s in stock_stats:
                            if s.get("in_cross60_up"):
                                result_text.insert(tk.END, f"  {s['name']}({s['code']}) 最近10日涨跌幅{s['pct_10']:+.2f}%\n")
                        result_text.insert(tk.END, "\n五、20日线向上且股价上穿20日线\n", "alert_green")
                        for s in stock_stats:
                            if s.get("in_cross20_up"):
                                result_text.insert(tk.END, f"  {s['name']}({s['code']}) 最近10日涨跌幅{s['pct_10']:+.2f}%\n")
                        return
                    # 插入 AI 正文
                    text = ai_result
                    result_text.insert(tk.END, text)
                self.root.after(0, show_result)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda e=e: status_label.config(text="分析失败"))
                self.root.after(0, lambda e=e: result_text.insert(tk.END, f"机会分析失败: {e}\n", "negative"))
        threading.Thread(target=run_in_thread, daemon=True).start()
        win.lift()
        win.focus_force()

    def _auto_ai_analysis_for_tab(self, tab_id):
        """对指定标签页进行AI分析"""
        try:
            # 切换到该标签页
            if hasattr(self, 'text_notebook') and tab_id:
                try:
                    self.text_notebook.select(tab_id)
                except:
                    pass
            # 调用AI分析
            self.run_ai_analysis()
        except Exception as e:
            print(f"[自动AI分析] 失败: {e}")

    def _auto_double_click_and_analyze(self, tab_id):
        """模拟双击富媒体内容,并在弹出框中执行一键分析和一键保存"""
        try:
            # 打开全窗口浏览器(模拟双击)
            self.open_full_window_viewer(tab_id)
            # 延迟执行,等待窗口打开
            def delayed_analyze_and_save():
                try:
                    import time
                    time.sleep(2)  # 等待窗口完全打开
                    # 查找弹出的全窗口浏览器窗口
                    for widget in self.root.winfo_children():
                        if isinstance(widget, tk.Toplevel):
                            try:
                                title = widget.title()
                                if "全窗口浏览" in title or "full" in title.lower():
                                    # 找到了弹出窗口,查找一键分析和一键保存按钮
                                    self._find_and_click_buttons_in_popup(widget)
                                    break
                            except:
                                pass
                except Exception as e:
                    print(f"[延迟执行弹出框操作] 失败: {e}")
            # 在后台线程中延迟执行
            threading.Thread(target=delayed_analyze_and_save, daemon=True).start()
        except Exception as e:
            print(f"[模拟双击和分析] 失败: {e}")

    def _compute_energy_analysis_report_text(self, stock_code, days=60):
        """持仓详情用:能量学分析(聚集/发散、震荡方向、螺旋/等幅、涨跌角度与力度),基于近 N 日日线 OHLC。"""
        lines = []
        lines.append("【能量学分析(价量时空 · 近60日日线统计)】")
        lines.append(
            "「能量」在此处的含义(便于阅读):用价格波动的宽窄、方向是否清晰、涨跌哪一侧更猛,来近似描述多空博弈的"
            "「激烈程度」和「蓄势/释放」状态--不是物理学能量,也不预测涨跌。"
        )
        lines.append(
            "数据口径:使用近 N 根日 K 的最高价、最低价、收盘价;仅价量时空里的「价」与「时」,本节未直接代入成交量;"
            "结论基于统计摘要,复盘参考用,不构成投资建议。"
        )
        lines.append("如何读下面五条指标:")
        lines.append(
            "  1 聚集/发散--把最近 10 个交易日平均「日内振幅」(高-低)/收盘,与再往前 10 日对比;"
            "振幅收窄多理解为波动降温、筹码交换趋缓,常与蓄势/变盘前奏联系;振幅放大多理解为分歧加大、情绪宣泄。"
        )
        lines.append(
            "  2 震荡/趋势--在近 20 个交易日里,看累计涨跌幅与「日收益率」标准差:"
            "若涨跌不大且波动率低,更像横盘;若涨跌明显或日波动高,更像单边或剧烈博弈。"
        )
        lines.append(
            "  3 螺旋/等幅--用滚动 5 日的「区间宽度」(5 日最高-5 日最低) 看波幅是在逐步收窄(类楔/三角收敛)、"
            "还是各段宽度差不多(箱体/等幅震荡)、或宽窄乱跳(节奏不规则)。"
        )
        lines.append(
            "  4 涨跌角度与线性力度--对「近 60 日(或可得全长)」收盘价做一元线性回归:"
            "斜率表示平均每个交易日价格沿直线爬升/下滑的倾向(元/日、折算为约占均价的%/日);"
            "R2(越接近 1)表示收盘越贴近一条直线、趋势更「干净」;R2 低则噪声大、线性趋势描述力弱。"
            "首尾价差倾角是把整段首尾差价相对时间与价格尺度折合的角度示意,便于和斜率一起看方向。"
        )
        lines.append(
            "  5 多空力度--近 20 个交易日里,只在收阳(涨)的那些天算平均涨幅,只在收阴(跌)的那些天算平均跌幅绝对值,"
            "比较哪一侧平均波动更大:偏大的一侧可理解为短期「进攻/打压」更猛(仍不代表后续方向)。\n"
        )
        try:
            pack = self._fetch_recent_daily_ohlc(
                str(stock_code).zfill(6),
                days=max(days, 30),
                source="default",
                token=getattr(self, "ts_token", None),
            )
            if not pack or len(pack) < 4:
                return "\n".join(lines) + "\n(无法获取日K OHLC,跳过能量学分析)\n"
            _dates, highs, lows, closes = pack[0], pack[1], pack[2], pack[3]
            highs = np.asarray(highs, dtype=float)
            lows = np.asarray(lows, dtype=float)
            closes = np.asarray(closes, dtype=float)
            n = len(closes)
            if n < 22:
                return "\n".join(lines) + "\n(有效交易日不足,暂不分析)\n"
            amp = (highs - lows) / np.clip(closes, 1e-9, None)
            a1 = float(np.mean(amp[-10:]))
            a0 = float(np.mean(amp[-20:-10]))
            ratio_amp = a1 / (a0 + 1e-12)
            if a1 < a0 * 0.88:
                band_word = "振幅收窄 → 能量趋向聚集/蓄势"
            elif a1 > a0 * 1.12:
                band_word = "振幅扩张 → 能量趋向发散/释放"
            else:
                band_word = "振幅与前一阶段相当 → 能量中性过渡"
            lines.append(f"· 能量聚集/发散:{band_word}(近10日/前10日日均振幅比 {ratio_amp:.2f})")
            lines.append(
                f"  解读:比值 = 近10日振幅均值 ÷ 再前10日振幅均值;"
                f"程序阈值约 <0.88 判收窄、>1.12 判扩张,中间为中性过渡。比值 {ratio_amp:.2f} 离 1 越远,收窄/扩张信号越强。"
            )
            ret = np.diff(closes) / np.clip(closes[:-1], 1e-9, None)
            vol20 = float(np.std(ret[-20:]) * 100.0)
            tot20 = float((closes[-1] / closes[-21] - 1.0) * 100.0) if n >= 21 else float(
                (closes[-1] / closes[0] - 1.0) * 100.0
            )
            w = min(20, n)
            xw = np.arange(w, dtype=float)
            yw = closes[-w:]
            m_s, _ = np.polyfit(xw, yw, 1)
            slope_pct = float(m_s / (float(np.mean(yw)) + 1e-9) * 100.0)
            if vol20 < 2.2 and abs(tot20) < 7.0:
                regime = "震荡/盘整特征为主"
                if slope_pct > 0.04:
                    dir_w = f"震荡中重心略上移(回归斜率约 {slope_pct:+.3f}%/日)"
                elif slope_pct < -0.04:
                    dir_w = f"震荡中重心略下移(回归斜率约 {slope_pct:+.3f}%/日)"
                else:
                    dir_w = "震荡中重心横向(多空未决)"
            else:
                regime = "趋势性更明显"
                dir_w = f"近段整体{'上涨' if tot20 >= 0 else '下跌'}约 {tot20:+.2f}%(20日窗口)"
            lines.append(f"· 震荡/趋势与方向:{regime};{dir_w}(近20日日收益标准差约 {vol20:.2f}%)")
            lines.append(
                f"  解读:若同时满足「|20日累计涨跌|<7%」且「日收益标准差<2.2%」,程序标为震荡/盘整;否则标为趋势性更明显。"
                f"标准差 {vol20:.2f}% 越高,单日上下跳动越剧烈。20日窗口涨跌 {tot20:+.2f}% 表示这一段净方向与幅度。"
            )
            win = 5
            ranges = []
            for i in range(n - win + 1):
                ranges.append(float(np.max(highs[i : i + win]) - np.min(lows[i : i + win])))
            ranges = np.asarray(ranges, dtype=float)
            if len(ranges) >= 10:
                early = float(np.mean(ranges[:4]))
                late = float(np.mean(ranges[-4:]))
                rv = float(np.std(ranges[-10:]) / (np.mean(ranges[-10:]) + 1e-9))
                if late < early * 0.82 and late < early:
                    motion = "偏螺旋式收敛(波动区间逐步收窄,易酝酿方向选择)"
                elif rv < 0.24:
                    motion = "偏等幅震荡(多段波动宽度较均匀,箱体特征)"
                else:
                    motion = "波动节奏不规则(多空换手、宽度变化较大)"
            else:
                motion = "(数据不足)"
            lines.append(f"· 波动节奏(螺旋/等幅):{motion}")
            lines.append(
                "  解读:在滚动5日最高价与最低价之差构成的「局部波幅」序列上,比较前段与后段均值及后段离散度;"
                "后段明显低于前段且整体下降,标为螺旋收敛;后段变异系数小,标为等幅震荡;否则为不规则。"
            )
            xv = np.arange(n, dtype=float)
            m_all, inter = np.polyfit(xv, closes, 1)
            pred = m_all * xv + inter
            ss_res = float(np.sum((closes - pred) ** 2))
            ss_tot = float(np.sum((closes - float(np.mean(closes))) ** 2))
            r2 = float(1.0 - ss_res / (ss_tot + 1e-12))
            mean_c = float(np.mean(closes))
            daily_pct = float(m_all / mean_c * 100.0)
            span = float(closes[-1] - closes[0])
            arc_deg = float(
                np.degrees(
                    np.arctan2(span, max(mean_c * 0.35, (n - 1) * mean_c * 0.002))
                )
            )
            arc_deg = max(-85.0, min(85.0, arc_deg))
            lines.append(
                f"· 涨跌角度与线性力度:全样本收盘回归斜率 {m_all:.5f} 元/日(约 {daily_pct:+.4f}%/日),"
                f"R2={r2:.2f}(越接近1趋势越「直」);首尾价差倾角示意约 {arc_deg:+.1f}°"
            )
            if r2 >= 0.65:
                r2_txt = "R2 较高:收盘价较贴近一条直线,趋势描述在本次样本内较可靠。"
            elif r2 >= 0.35:
                r2_txt = "R2 中等:既有方向性也有较多反复,适合把线性斜率当「平均倾向」而非精确轨线。"
            else:
                r2_txt = "R2 较低:涨跌路径曲折,线性回归仅反映很粗的重心漂移,不宜过度解读斜率。"
            lines.append(
                f"  解读:斜率为正表示回归直线随交易日推进上行、为负则下行(相对样本内均价折算约 {daily_pct:+.4f}%/日);"
                f"{r2_txt}"
                f"首尾示意倾角约 {arc_deg:+.1f}° 与整体涨跌方向一致,仅作直观参照(不是单根 K 线实体角度)。"
            )
            ret20 = ret[-20:]
            up = ret20[ret20 > 0]
            dn = ret20[ret20 < 0]
            up_s = float(np.mean(up) * 100.0) if len(up) else 0.0
            dn_s = float(np.mean(-dn) * 100.0) if len(dn) else 0.0
            lines.append(
                f"· 多空力度(近20日涨跌日):上涨日平均幅度 {up_s:.3f}% / 下跌日平均幅度 {dn_s:.3f}%"
            )
            if up_s > dn_s * 1.2 and up_s > 0.15:
                lines.append("  → 多头进攻/回补力度相对更强")
            elif dn_s > up_s * 1.2 and dn_s > 0.15:
                lines.append("  → 空头打压/回调力度相对更强")
            else:
                lines.append("  → 多空力度接近,强弱未显著分化")
            lines.append(
                "  解读:只在「上涨日」对涨幅取平均、在「下跌日」对跌幅绝对值取平均,再比较大小;"
                "因此若上涨日更少但每次涨得更猛,仍可能显示多头力度强。阈值约 1.2 倍且均幅 >0.15% 才标「显著」;"
                "下跌日不足或上涨日不足时,单侧均值为 0,结论会偏保守。"
            )
            lines.append("")
            return "\n".join(lines)
        except Exception as e:
            return "\n".join(lines) + f"\n(能量学分析计算异常:{e})\n"

    def _show_analysis_result_dialog(self, result, stock_name, title, parent_win=None):
        """显示通用分析结果对话框(夏普比率、均值回归等)"""
        dialog = self._toplevel(parent_win or self.root)
        dialog.title(f"{stock_name} - {title}")
        dialog.geometry("600x500")
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        if not result.get('success'):
            ttk.Label(main_frame, text=f"计算失败:{result.get('message', '')}",
                      font=("Microsoft YaHei", 12), foreground='red').pack(pady=20)
            ttk.Button(main_frame, text="关闭", command=dialog.destroy).pack(pady=10)
            return
        # 标题
        title_label = ttk.Label(main_frame, text=f"{stock_name} {title}",
                               font=("Microsoft YaHei", 14, "bold"))
        title_label.pack(pady=(0, 10))
        # 关键指标区域
        key_frame = ttk.LabelFrame(main_frame, text="关键指标", padding=10)
        key_frame.pack(fill=tk.X, pady=(0, 10))
        key_info = []
        if 'sharpe_ratio' in result:
            key_info.append(("夏普比率", f"{result['sharpe_ratio']:.4f}"))
            key_info.append(("年化收益率", f"{result['annualized_return']:.2f}%"))
            key_info.append(("年化波动率", f"{result['volatility']:.2f}%"))
        if 'z_score' in result:
            key_info.append(("Z-score", f"{result['z_score']:.4f}"))
            key_info.append(("当前价格", f"{result['current_price']:.2f}"))
            key_info.append(("均值", f"{result['mean_price']:.2f}"))
            key_info.append(("标准差", f"{result['std_deviation']:.2f}"))
            key_info.append(("回归概率", f"{result['reversion_probability']:.1f}%"))
            key_info.append(("建议仓位", f"{result['suggested_position']:.1f}%"))
        if 'trend_strength' in result:
            key_info.append(("趋势强度", f"{result['trend_strength']}"))
            pred = result.get('prediction', {})
            nd = pred.get('next_day', {})
            nw = pred.get('next_week', {})
            key_info.append(("明日方向", nd.get('direction', 'neutral')))
            key_info.append(("明日概率", f"{nd.get('probability', 50)}%"))
            key_info.append(("下周方向", nw.get('direction', 'neutral')))
            key_info.append(("下周概率", f"{nw.get('probability', 50)}%"))
        if 'dragon_score' in result:
            key_info.append(("龙头评分", f"{result['dragon_score']}"))
            key_info.append(("是否龙头", "是" if result.get('is_dragon') else "否"))
            pred = result.get('prediction', {})
            nd = pred.get('next_day', {})
            nw = pred.get('next_week', {})
            key_info.append(("明日方向", nd.get('direction', 'neutral')))
            key_info.append(("明日概率", f"{nd.get('probability', 50)}%"))
            key_info.append(("下周方向", nw.get('direction', 'neutral')))
            key_info.append(("下周概率", f"{nw.get('probability', 50)}%"))
        if 'bounce_score' in result:
            key_info.append(("反弹评分", f"{result['bounce_score']}"))
            pred = result.get('prediction', {})
            nd = pred.get('next_day', {})
            nw = pred.get('next_week', {})
            key_info.append(("明日方向", nd.get('direction', 'neutral')))
            key_info.append(("明日概率", f"{nd.get('probability', 50)}%"))
            key_info.append(("下周方向", nw.get('direction', 'neutral')))
            key_info.append(("下周概率", f"{nw.get('probability', 50)}%"))
            for level in result.get('support_levels', [])[:3]:
                key_info.append((f"支撑位-{level[0]}", f"{level[1]:.2f}"))
            for level in result.get('target_levels', [])[:2]:
                key_info.append((level.get('name', '目标位'), f"{level.get('level', 0):.2f}"))
        if 'total_score' in result and 'factor_scores' in result:
            key_info.append(("综合评分", f"{result['total_score']}"))
            for factor, score in result.get('factor_scores', {}).items():
                key_info.append((factor, str(score)))
            pred = result.get('prediction', {})
            nd = pred.get('next_day', {})
            nw = pred.get('next_week', {})
            key_info.append(("明日方向", nd.get('direction', 'neutral')))
            key_info.append(("明日概率", f"{nd.get('probability', 50)}%"))
            key_info.append(("下周方向", nw.get('direction', 'neutral')))
            key_info.append(("下周概率", f"{nw.get('probability', 50)}%"))
        for label, value in key_info:
            row = ttk.Frame(key_frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=label, width=15, font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
            if "夏普" in label:
                sharpe_value = float(value)
                color = 'green' if sharpe_value >= 1.0 else 'orange' if sharpe_value >= 0.5 else 'red'
                ttk.Label(row, text=value, font=("Microsoft YaHei", 10, "bold"), foreground=color).pack(side=tk.LEFT, padx=(10, 0))
            elif "建议仓位" in label:
                pos_value = float(value.replace('%', ''))
                if pos_value > 0:
                    color = 'red'
                elif pos_value < 0:
                    color = 'green'
                else:
                    color = 'gray'
                ttk.Label(row, text=value, font=("Microsoft YaHei", 10, "bold"), foreground=color).pack(side=tk.LEFT, padx=(10, 0))
            else:
                ttk.Label(row, text=value, font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(10, 0))
        # 计算步骤区域
        steps_frame = ttk.LabelFrame(main_frame, text="计算过程", padding=10)
        steps_frame.pack(fill=tk.BOTH, expand=True)
        steps_text = tk.Text(steps_frame, height=8, font=("Microsoft YaHei", 9), wrap=tk.WORD)
        steps_text.pack(fill=tk.BOTH, expand=True)
        for step in result.get('calculation_steps', []):
            steps_text.insert(tk.END, step + "\n")
        steps_text.config(state=tk.DISABLED)
        # 分析说明区域
        analysis_frame = ttk.LabelFrame(main_frame, text="分析说明", padding=10)
        analysis_frame.pack(fill=tk.BOTH, expand=True)
        text_widget = tk.Text(analysis_frame, height=5, font=("Microsoft YaHei", 10), wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True)
        for line in result.get('analysis', []):
            text_widget.insert(tk.END, line + "\n")
        text_widget.config(state=tk.DISABLED)
        # 关闭按钮
        ttk.Button(main_frame, text="关闭", command=dialog.destroy).pack(pady=10)

    def _analyze_stock_with_indicator(self, stock_code, stock_name, indicator_name):
        """使用技术指标分析股票"""
        try:
            # 获取K线数据
            kline_data = self._get_daily_kline_data_tushare(stock_code)
            if kline_data is None or kline_data['data'] is None or len(kline_data['data']) < 30:
                return {'success': False, 'message': '获取K线数据失败或数据不足'}
            data = kline_data['data']
            close = data['收盘'].values
            high = data['最高'].values
            low = data['最低'].values
            volume = data['成交量'].values
            result = {'success': True, 'indicator_values': {}, 'signals': [], 'suggestion': ''}
            if indicator_name == 'MACD':
                # 计算MACD
                ema12 = self._calculate_ema(close, 12)
                ema26 = self._calculate_ema(close, 26)
                dif = ema12 - ema26
                dea = self._calculate_ema(dif, 9)
                macd = (dif - dea) * 2
                result['indicator_values'] = {
                    'DIF': f"{dif[-1]:.4f}",
                    'DEA': f"{dea[-1]:.4f}",
                    'MACD柱': f"{macd[-1]:.4f}",
                    'DIF走势': '上升' if dif[-1] > dif[-2] else '下降',
                    'DEA走势': '上升' if dea[-1] > dea[-2] else '下降'
                }
                # 信号判断
                if dif[-1] > dea[-1] and dif[-2] <= dea[-2]:
                    result['signals'].append({'type': 'buy', 'description': 'MACD金叉,买入信号'})
                elif dif[-1] < dea[-1] and dif[-2] >= dea[-2]:
                    result['signals'].append({'type': 'sell', 'description': 'MACD死叉,卖出信号'})
                if macd[-1] > 0 and macd[-2] <= 0:
                    result['signals'].append({'type': 'buy', 'description': 'MACD柱由绿转红,趋势转强'})
                elif macd[-1] < 0 and macd[-2] >= 0:
                    result['signals'].append({'type': 'sell', 'description': 'MACD柱由红转绿,趋势转弱'})
                if dif[-1] > 0 and dea[-1] > 0:
                    result['signals'].append({'type': 'neutral', 'description': 'MACD处于正值区域,多头趋势'})
                elif dif[-1] < 0 and dea[-1] < 0:
                    result['signals'].append({'type': 'neutral', 'description': 'MACD处于负值区域,空头趋势'})
                # 综合建议
                if dif[-1] > dea[-1] and macd[-1] > 0:
                    result['suggestion'] = 'MACD多头排列,建议持有或加仓'
                elif dif[-1] < dea[-1] and macd[-1] < 0:
                    result['suggestion'] = 'MACD空头排列,建议减仓或观望'
                else:
                    result['suggestion'] = 'MACD信号不明确,建议结合其他指标分析'
            elif indicator_name == 'RSI':
                # 计算RSI(6)和RSI(12)
                rsi6 = self._calculate_rsi(close, 6)
                rsi12 = self._calculate_rsi(close, 12)
                result['indicator_values'] = {
                    'RSI(6)': f"{rsi6[-1]:.2f}",
                    'RSI(12)': f"{rsi12[-1]:.2f}",
                    'RSI(6)走势': '上升' if rsi6[-1] > rsi6[-2] else '下降',
                    'RSI(12)走势': '上升' if rsi12[-1] > rsi12[-2] else '下降'
                }
                # 信号判断
                if rsi6[-1] < 30:
                    result['signals'].append({'type': 'buy', 'description': 'RSI(6) < 30,超卖区域,可能反弹'})
                if rsi6[-1] > 70:
                    result['signals'].append({'type': 'sell', 'description': 'RSI(6) > 70,超买区域,可能回调'})
                if rsi6[-1] > rsi12[-1] and rsi6[-2] <= rsi12[-2]:
                    result['signals'].append({'type': 'buy', 'description': 'RSI金叉,买入信号'})
                elif rsi6[-1] < rsi12[-1] and rsi6[-2] >= rsi12[-2]:
                    result['signals'].append({'type': 'sell', 'description': 'RSI死叉,卖出信号'})
                # 综合建议
                if rsi6[-1] < 30:
                    result['suggestion'] = 'RSI处于超卖区域,建议关注反弹机会'
                elif rsi6[-1] > 70:
                    result['suggestion'] = 'RSI处于超买区域,建议减仓或观望'
                else:
                    result['suggestion'] = 'RSI处于正常区域,建议结合其他指标分析'
            elif indicator_name == 'KDJ':
                # 计算KDJ(9,3,3)
                kdj = self._calculate_kdj(high, low, close, 9, 3, 3)
                result['indicator_values'] = {
                    'K值': f"{kdj['k'][-1]:.2f}",
                    'D值': f"{kdj['d'][-1]:.2f}",
                    'J值': f"{kdj['j'][-1]:.2f}",
                    'K走势': '上升' if kdj['k'][-1] > kdj['k'][-2] else '下降',
                    'D走势': '上升' if kdj['d'][-1] > kdj['d'][-2] else '下降'
                }
                # 信号判断
                if kdj['k'][-1] > kdj['d'][-1] and kdj['k'][-2] <= kdj['d'][-2]:
                    result['signals'].append({'type': 'buy', 'description': 'KDJ金叉,买入信号'})
                elif kdj['k'][-1] < kdj['d'][-1] and kdj['k'][-2] >= kdj['d'][-2]:
                    result['signals'].append({'type': 'sell', 'description': 'KDJ死叉,卖出信号'})
                if kdj['j'][-1] > 100:
                    result['signals'].append({'type': 'sell', 'description': 'J值 > 100,超买区域'})
                elif kdj['j'][-1] < 0:
                    result['signals'].append({'type': 'buy', 'description': 'J值 < 0,超卖区域'})
                # 综合建议
                if kdj['k'][-1] > kdj['d'][-1] and kdj['j'][-1] > 0:
                    result['suggestion'] = 'KDJ多头排列,建议持有或加仓'
                elif kdj['k'][-1] < kdj['d'][-1] and kdj['j'][-1] < 100:
                    result['suggestion'] = 'KDJ空头排列,建议减仓或观望'
                else:
                    result['suggestion'] = 'KDJ信号不明确,建议结合其他指标分析'
            elif indicator_name == 'BOLL':
                # 计算布林带(20,2)
                ma20 = self._calculate_ma(close, 20)
                std = np.std(close[-20:])
                upper = ma20[-1] + 2 * std
                lower = ma20[-1] - 2 * std
                result['indicator_values'] = {
                    '中轨(MA20)': f"{ma20[-1]:.2f}",
                    '上轨': f"{upper:.2f}",
                    '下轨': f"{lower:.2f}",
                    '当前价格': f"{close[-1]:.2f}",
                    '通道宽度': f"{upper - lower:.2f}",
                    '价格偏离度': f"{((close[-1] - ma20[-1]) / (upper - lower)) * 100:.2f}%"
                }
                # 信号判断
                if close[-1] >= upper:
                    result['signals'].append({'type': 'sell', 'description': '价格触及上轨,可能回调'})
                elif close[-1] <= lower:
                    result['signals'].append({'type': 'buy', 'description': '价格触及下轨,可能反弹'})
                # 通道宽度变化
                prev_std = np.std(close[-21:-1])
                if std < prev_std * 0.8:
                    result['signals'].append({'type': 'neutral', 'description': '布林带收口,行情即将突破'})
                elif std > prev_std * 1.2:
                    result['signals'].append({'type': 'neutral', 'description': '布林带开口,行情加速'})
                # 综合建议
                if close[-1] <= lower:
                    result['suggestion'] = '价格触及布林带下轨,建议关注反弹机会'
                elif close[-1] >= upper:
                    result['suggestion'] = '价格触及布林带上轨,建议减仓或观望'
                else:
                    result['suggestion'] = '价格在布林带内正常波动,建议持有'
            elif indicator_name == 'MA':
                # 计算MA5, MA10, MA20, MA60
                ma5 = self._calculate_ma(close, 5)
                ma10 = self._calculate_ma(close, 10)
                ma20 = self._calculate_ma(close, 20)
                ma60 = self._calculate_ma(close, 60)
                result['indicator_values'] = {
                    'MA5': f"{ma5[-1]:.2f}",
                    'MA10': f"{ma10[-1]:.2f}",
                    'MA20': f"{ma20[-1]:.2f}",
                    'MA60': f"{ma60[-1]:.2f}",
                    '当前价格': f"{close[-1]:.2f}"
                }
                # 判断均线排列
                if ma5[-1] > ma10[-1] > ma20[-1] > ma60[-1]:
                    result['signals'].append({'type': 'buy', 'description': '均线多头排列,上升趋势'})
                elif ma5[-1] < ma10[-1] < ma20[-1] < ma60[-1]:
                    result['signals'].append({'type': 'sell', 'description': '均线空头排列,下降趋势'})
                else:
                    result['signals'].append({'type': 'neutral', 'description': '均线纠结,震荡行情'})
                # 价格与均线关系
                if close[-1] > ma5[-1]:
                    result['signals'].append({'type': 'buy', 'description': '价格在MA5之上,短期强势'})
                elif close[-1] < ma20[-1]:
                    result['signals'].append({'type': 'sell', 'description': '价格在MA20之下,短期弱势'})
                # 综合建议
                if ma5[-1] > ma10[-1] > ma20[-1]:
                    result['suggestion'] = '均线多头排列,建议持有或加仓'
                elif ma5[-1] < ma10[-1] < ma20[-1]:
                    result['suggestion'] = '均线空头排列,建议减仓或观望'
                else:
                    result['suggestion'] = '均线纠结,建议观望或短线操作'
            elif indicator_name == 'VOL':
                # 计算成交量和均量线
                ma_vol5 = self._calculate_ma(volume, 5)
                ma_vol10 = self._calculate_ma(volume, 10)
                result['indicator_values'] = {
                    '今日成交量': f"{volume[-1]:,.0f}",
                    '5日均量': f"{ma_vol5[-1]:,.0f}",
                    '10日均量': f"{ma_vol10[-1]:,.0f}",
                    '量比': f"{volume[-1] / ma_vol5[-1]:.2f}" if ma_vol5[-1] > 0 else 'N/A',
                    '成交量走势': '放量' if volume[-1] > ma_vol5[-1] * 1.5 else '缩量' if volume[-1] < ma_vol5[-1] * 0.5 else '正常'
                }
                # 判断量价关系
                if close[-1] > close[-2] and volume[-1] > ma_vol5[-1]:
                    result['signals'].append({'type': 'buy', 'description': '价涨量增,趋势健康'})
                elif close[-1] > close[-2] and volume[-1] < ma_vol5[-1]:
                    result['signals'].append({'type': 'sell', 'description': '价涨量缩,上涨乏力'})
                elif close[-1] < close[-2] and volume[-1] > ma_vol5[-1]:
                    result['signals'].append({'type': 'sell', 'description': '价跌量增,恐慌抛售'})
                elif close[-1] < close[-2] and volume[-1] < ma_vol5[-1]:
                    result['signals'].append({'type': 'buy', 'description': '价跌量缩,下跌动能减弱'})
                # 综合建议
                if close[-1] > close[-2] and volume[-1] > ma_vol5[-1]:
                    result['suggestion'] = '价涨量增,趋势健康,建议持有'
                elif close[-1] > close[-2] and volume[-1] < ma_vol5[-1]:
                    result['suggestion'] = '价涨量缩,上涨乏力,建议谨慎'
                else:
                    result['suggestion'] = '成交量信号不明确,建议结合其他指标分析'
            elif indicator_name == 'WR':
                # 计算WR(14)
                wr14 = self._calculate_wr(high, low, close, 14)
                result['indicator_values'] = {
                    'WR(14)': f"{wr14[-1]:.2f}",
                    'WR走势': '上升' if wr14[-1] > wr14[-2] else '下降'
                }
                # 信号判断
                if wr14[-1] > -20:
                    result['signals'].append({'type': 'sell', 'description': 'WR > -20,超买区域,可能回调'})
                elif wr14[-1] < -80:
                    result['signals'].append({'type': 'buy', 'description': 'WR < -80,超卖区域,可能反弹'})
                # 综合建议
                if wr14[-1] < -80:
                    result['suggestion'] = 'WR处于超卖区域,建议关注反弹机会'
                elif wr14[-1] > -20:
                    result['suggestion'] = 'WR处于超买区域,建议减仓或观望'
                else:
                    result['suggestion'] = 'WR处于正常区域,建议结合其他指标分析'
            elif indicator_name == 'CCI':
                # 计算CCI(14)
                cci = self._calculate_cci(high, low, close, 14)
                result['indicator_values'] = {
                    'CCI(14)': f"{cci[-1]:.2f}",
                    'CCI走势': '上升' if cci[-1] > cci[-2] else '下降'
                }
                # 信号判断
                if cci[-1] > 100:
                    result['signals'].append({'type': 'sell', 'description': 'CCI > 100,超买区域'})
                elif cci[-1] < -100:
                    result['signals'].append({'type': 'buy', 'description': 'CCI < -100,超卖区域'})
                # 综合建议
                if cci[-1] < -100:
                    result['suggestion'] = 'CCI处于超卖区域,建议关注反弹机会'
                elif cci[-1] > 100:
                    result['suggestion'] = 'CCI处于超买区域,建议减仓或观望'
                else:
                    result['suggestion'] = 'CCI处于正常区域,建议结合其他指标分析'
            elif indicator_name == 'OBV':
                # 计算OBV
                obv = self._calculate_obv(close, volume)
                result['indicator_values'] = {
                    'OBV': f"{obv[-1]:,.0f}",
                    'OBV走势': '上升' if obv[-1] > obv[-2] else '下降',
                    '价格走势': '上涨' if close[-1] > close[-2] else '下跌'
                }
                # 判断量价关系
                if obv[-1] > obv[-2] and close[-1] > close[-2]:
                    result['signals'].append({'type': 'buy', 'description': 'OBV上升,价格上涨,量价配合'})
                elif obv[-1] > obv[-2] and close[-1] < close[-2]:
                    result['signals'].append({'type': 'buy', 'description': 'OBV上升,价格下跌,底背离'})
                elif obv[-1] < obv[-2] and close[-1] > close[-2]:
                    result['signals'].append({'type': 'sell', 'description': 'OBV下降,价格上涨,顶背离'})
                elif obv[-1] < obv[-2] and close[-1] < close[-2]:
                    result['signals'].append({'type': 'sell', 'description': 'OBV下降,价格下跌,量价配合'})
                # 综合建议
                if obv[-1] > obv[-2] and close[-1] > close[-2]:
                    result['suggestion'] = 'OBV与价格同步上升,量价配合,建议持有'
                elif obv[-1] > obv[-2] and close[-1] < close[-2]:
                    result['suggestion'] = 'OBV上升但价格下跌,底背离,建议关注'
                elif obv[-1] < obv[-2] and close[-1] > close[-2]:
                    result['suggestion'] = 'OBV下降但价格上涨,顶背离,建议谨慎'
                else:
                    result['suggestion'] = 'OBV信号不明确,建议结合其他指标分析'
            elif indicator_name == 'DMI':
                # 计算DMI(14)
                dmi = self._calculate_dmi(high, low, close, 14)
                result['indicator_values'] = {
                    '+DI': f"{dmi['plus_di'][-1]:.2f}",
                    '-DI': f"{dmi['minus_di'][-1]:.2f}",
                    'ADX': f"{dmi['adx'][-1]:.2f}"
                }
                # 信号判断
                if dmi['plus_di'][-1] > dmi['minus_di'][-1]:
                    result['signals'].append({'type': 'buy', 'description': '+DI > -DI,上升趋势'})
                elif dmi['minus_di'][-1] > dmi['plus_di'][-1]:
                    result['signals'].append({'type': 'sell', 'description': '-DI > +DI,下降趋势'})
                if dmi['adx'][-1] > 25:
                    result['signals'].append({'type': 'neutral', 'description': 'ADX > 25,趋势较强'})
                elif dmi['adx'][-1] < 20:
                    result['signals'].append({'type': 'neutral', 'description': 'ADX < 20,趋势较弱或震荡'})
                # 综合建议
                if dmi['plus_di'][-1] > dmi['minus_di'][-1] and dmi['adx'][-1] > 25:
                    result['suggestion'] = '上升趋势明确且强度较高,建议持有或加仓'
                elif dmi['minus_di'][-1] > dmi['plus_di'][-1] and dmi['adx'][-1] > 25:
                    result['suggestion'] = '下降趋势明确且强度较高,建议减仓或观望'
                else:
                    result['suggestion'] = '趋势不明确或较弱,建议观望或短线操作'
            return result
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def _plot_kline_zoom_subpanel(self, ax, key, dates, opens, closes, highs, lows, vol):
        """放大窗副图:VOL / MACD / WR2 / KDJ / BOLL。"""
        x = dates
        n = len(closes)
        o = np.asarray(opens, dtype=float)
        c = np.asarray(closes, dtype=float)
        indicator_descriptions = {
            "VOL": "成交量:反映市场交易活跃度,红色为上涨日,绿色为下跌日",
            "MACD": "MACD:指数平滑异同移动平均线,DIF上穿DEA为金叉,下穿为死叉",
            "WR2": "WR:威廉指标,超买超卖指标,低于-80为超卖,高于-20为超买",
            "KDJ": "KDJ:随机指标,K上穿D为金叉买入信号,80以上超买,20以下超卖",
            "BOLL": "BOLL:布林带,价格突破上轨超买,跌破下轨超卖,中轨为趋势线"
        }
        if key == "VOL":
            v = np.asarray(vol, dtype=float) if vol is not None else np.zeros(n)
            if n < 1 or float(np.nanmax(np.abs(v))) < 1e-9:
                ax.text(0.5, 0.5, "无成交量数据(需 Tushare daily 含 vol)", transform=ax.transAxes, ha="center", fontsize=9)
                ax.set_ylabel("VOL")
                return
            colors = ["#d32f2f" if c[i] >= o[i] else "#388e3c" for i in range(n)]
            ax.bar(x, v, color=colors, alpha=0.75, width=0.65)
            if n >= 5:
                vma = pd.Series(v).rolling(5, min_periods=1).mean()
                ax.plot(x, vma.values, color="#f57c00", linewidth=1.0, label="VOL MA5")
            ax.set_ylabel("成交量(手)")
            ax.legend(loc="upper left", fontsize=7)
            ax.set_title(indicator_descriptions[key], fontsize=7, loc="left", color="#666666", pad=2)
        elif key == "MACD":
            ema12 = self._ema_np(c, 12)
            ema26 = self._ema_np(c, 26)
            dif = ema12 - ema26
            dea = self._ema_np(dif, 9)
            macdh = 2.0 * (dif - dea)
            ax.plot(x, dif, label="DIF", linewidth=1.0, color="#1565c0")
            ax.plot(x, dea, label="DEA", linewidth=1.0, color="#c62828")
            bar_colors = ["#d32f2f" if v >= 0 else "#388e3c" for v in macdh]
            ax.bar(x, macdh, color=bar_colors, alpha=0.45, width=0.55)
            ax.axhline(0, color="gray", linewidth=0.6)
            ax.set_ylabel("MACD")
            ax.legend(loc="upper left", fontsize=7)
            ax.set_title(indicator_descriptions[key], fontsize=7, loc="left", color="#666666", pad=2)
        elif key == "WR2":
            wr = self._williams_r_n(highs, lows, closes, 2)
            ax.plot(x, wr, label="WR(2日)", linewidth=1.0, color="#6a1b9a")
            ax.axhline(-20, color="gray", linestyle="--", linewidth=0.6)
            ax.axhline(-80, color="gray", linestyle="--", linewidth=0.6)
            ax.set_ylabel("WR")
            ax.legend(loc="upper left", fontsize=7)
            ax.set_title(indicator_descriptions[key], fontsize=7, loc="left", color="#666666", pad=2)
        elif key == "KDJ":
            kv, dv, jv = self._kdj_series(highs, lows, closes, 9)
            ax.plot(x, kv, label="K", linewidth=1.0, color="#c62828")
            ax.plot(x, dv, label="D", linewidth=1.0, color="#1565c0")
            ax.plot(x, jv, label="J", linewidth=0.9, color="#6a1b9a", alpha=0.9)
            ax.axhline(80, color="gray", linestyle=":", linewidth=0.5)
            ax.axhline(20, color="gray", linestyle=":", linewidth=0.5)
            ax.set_ylabel("KDJ")
            ax.legend(loc="upper left", fontsize=7)
            ax.set_title(indicator_descriptions[key], fontsize=7, loc="left", color="#666666", pad=2)
        elif key == "BOLL":
            up, mid, lo = self._boll_np(closes, 20, 2.0)
            ax.plot(x, mid, label="MID(20)", color="black", linewidth=1.0)
            ax.plot(x, up, label="UP", color="#d32f2f", linewidth=0.95, alpha=0.9)
            ax.plot(x, lo, label="LOW", color="#2e7d32", linewidth=0.95, alpha=0.9)
            ax.set_ylabel("BOLL")
            ax.legend(loc="upper left", fontsize=7)
            ax.set_title(indicator_descriptions[key], fontsize=7, loc="left", color="#666666", pad=2)
        ax.grid(True, alpha=0.3)

    def _draw_daily_kline_chart(self, parent, kline_data, stock_name, embed_zoom_handler=True):
        """绘制日K线图(Tushare),含均线与支撑/压力线;双击可弹出最大化查看。"""
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            fig = self._build_daily_kline_figure(kline_data, stock_name, figsize=(12, 6))
            canvas = FigureCanvasTkAgg(fig, parent)
            canvas.draw()
            w = canvas.get_tk_widget()
            w.pack(fill=tk.BOTH, expand=True)
            if embed_zoom_handler:
                w.bind("<Double-Button-1>", lambda e: self._show_daily_kline_zoom(kline_data, stock_name))
        except Exception as e:
            print(f"绘制日K线图失败: {e}")
            import traceback
            traceback.print_exc()
            error_label = ttk.Label(parent, text=f"绘制日K线图失败: {e}", font=("TkDefaultFont", 12), foreground="red")
            error_label.pack(expand=True)

    def _draw_15min_kline_chart(self, parent, kline_data, stock_name):
        """绘制15分钟K线图,包含1日、3日、5日、10日、20日均线"""
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            # 创建图表
            fig = Figure(figsize=(12, 6), dpi=100)
            ax = fig.add_subplot(111)
            data = kline_data['data']
            ma_values = kline_data['ma_values']
            # 准备K线数据
            dates = list(range(len(data)))  # 使用索引作为x轴
            if '开盘' in data.columns:
                opens = data['开盘'].values
                closes = data['收盘'].values
                highs = data['最高'].values
                lows = data['最低'].values
            else:
                # 如果列名不同,尝试使用位置索引
                opens = data.iloc[:, 1].values if len(data.columns) > 1 else data.iloc[:, 0].values
                closes = data.iloc[:, 2].values if len(data.columns) > 2 else data.iloc[:, 0].values
                highs = data.iloc[:, 3].values if len(data.columns) > 3 else data.iloc[:, 0].values
                lows = data.iloc[:, 4].values if len(data.columns) > 4 else data.iloc[:, 0].values
            # 绘制K线(使用蜡烛图样式)
            for i in range(len(dates)):
                color = 'red' if closes[i] >= opens[i] else 'green'
                # 绘制实体(开盘到收盘)
                body_bottom = min(opens[i], closes[i])
                body_top = max(opens[i], closes[i])
                ax.bar(i, body_top - body_bottom, bottom=body_bottom, color=color, alpha=0.8, width=0.6)
                # 绘制上下影线
                ax.plot([i, i], [lows[i], body_bottom], color=color, linewidth=1)
                ax.plot([i, i], [body_top, highs[i]], color=color, linewidth=1)
            # 绘制收盘价折线(辅助线)
            ax.plot(dates, closes, color='black', linewidth=0.5, label='收盘价', alpha=0.5, linestyle='--')
            # 绘制均线(不同颜色)
            ma_colors = {
                'ma1': '#FF0000',   # 红色
                'ma3': '#FFA500',   # 橙色
                'ma5': '#00FF00',   # 绿色
                'ma10': '#0000FF',  # 蓝色
                'ma20': '#FF00FF'   # 紫色
            }
            ma_labels = {
                'ma1': '1日均线',
                'ma3': '3日均线',
                'ma5': '5日均线',
                'ma10': '10日均线',
                'ma20': '20日均线'
            }
            period_map = {
                'ma1': 16,
                'ma3': 48,
                'ma5': 80,
                'ma10': 160,
                'ma20': 320
            }
            for ma_name in ['ma1', 'ma3', 'ma5', 'ma10', 'ma20']:
                if ma_name in ma_values and len(ma_values[ma_name]) > 0:
                    ma_data = ma_values[ma_name]
                    # 对齐日期(均线数据从period-1开始)
                    period = period_map[ma_name]
                    start_idx = min(period-1, len(dates)-1)
                    # 创建对应的x轴索引
                    ma_indices = list(range(start_idx, start_idx + len(ma_data)))
                    # 确保数据长度一致
                    min_len = min(len(ma_indices), len(ma_data))
                    if min_len > 0:
                        ax.plot(ma_indices[:min_len], ma_data[:min_len], color=ma_colors[ma_name],
                               linewidth=1.5, label=ma_labels[ma_name], alpha=0.8)
            ax.set_title(f"{stock_name} - 15分钟K线图(10日周期)", fontsize=12, fontweight='bold')
            ax.set_xlabel("K线序号", fontsize=10)
            ax.set_ylabel("价格", fontsize=10)
            ax.legend(loc='upper left', fontsize=8)
            ax.grid(True, alpha=0.3)
            # 设置x轴刻度(显示部分时间点)
            if len(dates) > 0:
                step = max(1, len(dates) // 10)  # 显示约10个刻度
                ax.set_xticks(dates[::step])
                ax.set_xticklabels([f"K{i+1}" for i in dates[::step]], rotation=45, ha='right')
            # 将图表嵌入到tkinter
            canvas = FigureCanvasTkAgg(fig, parent)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            print(f"绘制K线图失败: {e}")
            import traceback
            traceback.print_exc()
            error_label = ttk.Label(parent,
                                   text=f"绘制K线图失败: {e}",
                                   font=("TkDefaultFont", 12),
                                   foreground="red")
            error_label.pack(expand=True)

    def _lightning_analyze(self, stock_code, kline_data=None, kline_15min=None):
        """T2-SD: 闪电交易系统 v3(超短)"""
        result = {"action": "观望", "position": "0%", "signals": [], "details": {}}
        try:
            if kline_data and kline_data.get('data') is not None:
                df = kline_data['data']
                closes = df['收盘'].values
                if len(closes) >= 15:
                    ma15 = float(np.mean(closes[-15:]))
                    close = float(closes[-1])
                    ma15_prev = float(np.mean(closes[-16:-1])) if len(closes) >= 16 else ma15
                    above_ma15 = close > ma15
                    ma15_rising = ma15 > ma15_prev
                    result["details"].update({"收盘": f"{close:.2f}", "MA15": f"{ma15:.2f}", "MA15方向": "上升" if ma15_rising else "下降"})
                    daily_ok = above_ma15 and ma15_rising
                    if len(closes) >= 10:
                        ma10 = float(np.mean(closes[-10:]))
                        dist_10 = abs(close - ma10) / ma10 * 100
                        result["details"]["距MA10"] = f"{dist_10:.1f}%"
                        if dist_10 < 1.0:
                            result["signals"].append("⚠️接近10日线,注意止损")
                    if not above_ma15:
                        result.update({"action": "清仓", "position": "0%"})
                        result["signals"].append("🔴跌破15MA,清仓")
                    elif daily_ok:
                        if kline_15min and kline_15min.get('data') is not None:
                            df15 = kline_15min['data']
                            c15 = df15['收盘'].values
                            if len(c15) >= 60:
                                ma60_15 = float(np.mean(c15[-60:]))
                                ma60_15_prev = float(np.mean(c15[-61:-1])) if len(c15) >= 61 else ma60_15
                                if c15[-1] > ma60_15 > ma60_15_prev:
                                    result.update({"action": "可买入", "position": "50-80%"})
                                    result["signals"].append("🟢日线+15min双多头,可买入")
                                else:
                                    result.update({"action": "观望", "position": "0-20%"})
                                    result["signals"].append("🟡15min未确认多头,观望")
                        else:
                            result.update({"action": "可买入", "position": "30-50%"})
                            result["signals"].append("🟢日线多头,可轻仓买入")
                    else:
                        result["signals"].append("🔴日线未站上15MA或MA下行,观望")
        except Exception as e:
            result["signals"].append(f"分析异常: {e}")
        return result

    def _analyze_market_context(self):
        """分析最近几天的大盘情况(上证/深证/创业板 + 涨跌家数 + 市场情绪)
        返回: {'sentiment': str, 'up_count': int, 'down_count': int, 'sh_change': float, 'sz_change': float, 'cyb_change': float, 'advice': str, 'position_cap': int, 'details': str}
        """
        result = {"sentiment": "未知", "up_count": 0, "down_count": 0,
                  "sh_change": 0, "sz_change": 0, "cyb_change": 0,
                  "advice": "观望", "position_cap": 50, "details": "", "reasoning": []}
        try:
            import akshare as ak
            # 1. 获取上证、深证、创业板指数实时涨跌幅(sina 实时源)
            idx_map = {"sh000001": "sh_change", "sz399001": "sz_change", "sz399006": "cyb_change"}
            try:
                spot_idx = safe_call(ak.stock_zh_index_spot_sina, fallback=pd.DataFrame(), label="ak.stock_zh_index_spot_sina")
                if spot_idx is not None and len(spot_idx) > 0:
                    code_col = next(c for c in spot_idx.columns if "代码" in c)
                    pct_col = next(c for c in spot_idx.columns if "涨跌幅" in c)
                    for sym, key in idx_map.items():
                        row = spot_idx[spot_idx[code_col] == sym]
                        if len(row) > 0:
                            result[key] = round(float(row[pct_col].iloc[0]), 2)
            except Exception:
                # 回退日线
                for idx_code, key in idx_map.items():
                    try:
                        df_idx = ak.stock_zh_index_daily(symbol=idx_code)
                        if df_idx is not None and not df_idx.empty and len(df_idx) >= 2:
                            latest = df_idx.iloc[-1]; prev = df_idx.iloc[-2]
                            result[key] = round(((latest['close'] - prev['close']) / prev['close']) * 100, 2)
                    except Exception: pass
            # 2. 获取全市场涨跌家数
            spot_ok = False
            try:
                spot_df = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
                if spot_df is not None and not spot_df.empty:
                    if '涨跌幅' in spot_df.columns:
                        result["up_count"] = int((spot_df['涨跌幅'] > 0).sum())
                        result["down_count"] = int((spot_df['涨跌幅'] < 0).sum())
                        spot_ok = (result["up_count"] + result["down_count"]) > 0
            except Exception:
                pass
            # 3. 数据展示
            up = result["up_count"]
            down = result["down_count"]
            total = up + down
            sh_chg = result["sh_change"]
            sz_chg = result["sz_change"]
            cyb_chg = result["cyb_change"]
            # 4. 逐步推导市场情绪(带数据支持和推导过程)
            result["reasoning"] = []
            # Step 1: 涨跌家数分析(仅在数据有效时使用)
            if spot_ok:
                result["reasoning"].append(
                    f"【数据】全市场上涨{up}家, 下跌{down}家, 总计{total}家"
                )
                result["reasoning"].append(
                    "【规则】上涨<1600→恐慌(仓位≤20%); 1600-3500→震荡(仓位≤50%); >3500→强势(仓位≤80%)"
                )
            else:
                result["reasoning"].append(
                    f"【数据】涨跌家数获取失败(非交易时段或网络异常),up={up}, down={down}"
                )
                result["reasoning"].append(
                    "【规则】涨跌家数无效时不以此判断情绪,改为依据指数涨跌判断"
                )
            # Step 2: 指数涨跌分析
            result["reasoning"].append(
                f"【数据】上证{sh_chg:+.2f}%, 深证{sz_chg:+.2f}%, 创业板{cyb_chg:+.2f}%"
            )
            result["reasoning"].append(
                "【规则】上证跌幅>2%→急跌(仓位≤15%); 跌0.5%-2%且涨<2000家→偏弱(仓位≤30%)"
            )
            # Step 3: 综合判断(涨跌家数有效时用家数,无效时用指数)
            if spot_ok:
                if up < 1600:
                    result["sentiment"] = "🔴恐慌"
                    result["advice"] = "大盘恐慌,控制仓位≤20%,仅做超跌反弹"
                    result["position_cap"] = 20
                    result["reasoning"].append(f"【推导】上涨{up}家<1600→判定🔴恐慌, 仓位上限20%")
                elif up < 3500:
                    result["sentiment"] = "🟡震荡"
                    result["advice"] = "大盘震荡,仓位30-50%,低吸高抛"
                    result["position_cap"] = 50
                    result["reasoning"].append(f"【推导】上涨{up}家在1600-3500之间→判定🟡震荡, 仓位上限50%")
                else:
                    result["sentiment"] = "🟢强势"
                    result["advice"] = "大盘强势,仓位60-80%,顺势做多"
                    result["position_cap"] = 80
                    result["reasoning"].append(f"【推导】上涨{up}家>3500→判定🟢强势, 仓位上限80%")
            else:
                # 涨跌家数无效,仅用指数涨跌判断
                if sh_chg == 0 and sz_chg == 0 and cyb_chg == 0:
                    result["sentiment"] = "⚪未知"
                    result["advice"] = "大盘数据获取失败,无法判断,建议保守仓位≤40%"
                    result["position_cap"] = 40
                    result["reasoning"].append("【推导】指数涨跌均为0且家数无效→无法判断,默认⚪未知, 仓位上限40%")
                elif sh_chg < -2:
                    result["sentiment"] = "🔴急跌"
                    result["advice"] = "上证跌>2%,大盘急跌,仓位≤15%"
                    result["position_cap"] = 15
                    result["reasoning"].append(f"【推导】上证跌{sh_chg:.2f}%>2%→判定🔴急跌, 仓位上限15%")
                elif sh_chg < -0.5:
                    result["sentiment"] = "🟡偏弱"
                    result["advice"] = "上证跌>0.5%,大盘偏弱,仓位≤30%"
                    result["position_cap"] = 30
                    result["reasoning"].append(f"【推导】上证跌{sh_chg:.2f}%>0.5%→判定🟡偏弱, 仓位上限30%")
                elif sh_chg > 1.0:
                    result["sentiment"] = "🟢偏强"
                    result["advice"] = "上证涨>1%,大盘偏强,仓位60-70%"
                    result["position_cap"] = 70
                    result["reasoning"].append(f"【推导】上证涨{sh_chg:.2f}%>1%→判定🟢偏强, 仓位上限70%")
                else:
                    result["sentiment"] = "🟡震荡"
                    result["advice"] = "指数波动不大,大盘震荡,仓位30-50%"
                    result["position_cap"] = 50
                    result["reasoning"].append(f"【推导】上证涨跌{sh_chg:+.2f}%在±1%内→判定🟡震荡, 仓位上限50%")
            # Step 4: 指数趋势修正(仅在涨跌家数有效时叠加修正)
            if spot_ok and sh_chg < -2:
                result["sentiment"] = "🔴急跌"
                result["advice"] = "大盘急跌,仓位≤15%,防守为主"
                result["position_cap"] = 15
                result["reasoning"].append(f"【修正】上证跌幅{sh_chg:.2f}%>2%→升级为🔴急跌, 仓位上限降至15%")
            elif spot_ok and sh_chg < -0.5 and up < 2000:
                result["advice"] = "大盘偏弱且跌多涨少,仓位≤30%"
                result["position_cap"] = 30
                result["reasoning"].append(f"【修正】上证跌{sh_chg:.2f}%且上涨仅{up}家→仓位上限降至30%")
            # Step 5: 最终结论
            result["reasoning"].append(
                f"【结论】情绪={result['sentiment']}, 仓位上限={result['position_cap']}%, {result['advice']}"
            )
            # 5. 构建详情
            result["details"] = (
                f"上证{sh_chg:+.2f}%, 深证{sz_chg:+.2f}%, 创业板{cyb_chg:+.2f}%\n"
                f"上涨{up}家, 下跌{down}家, 情绪: {result['sentiment']}\n"
                f"仓位上限: {result['position_cap']}%, 建议: {result['advice']}"
            )
        except Exception as e:
            result["details"] = f"大盘分析失败: {e}"
            result["reasoning"] = [f"大盘分析异常: {e}"]
        return result

    def _run_stock_analysis_engine(self, stock_code, stock_name=""):
        """T4: 统一分析引擎入口"""
        report_lines = []
        all_signals = []
        report_lines.append("# 股票分析引擎报告")
        report_lines.append(f"**股票**: {stock_name}({stock_code})")
        report_lines.append(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("---")
        report_lines.append("## 1. 数据获取")
        kline_data = None
        try:
            kline_data = self._get_daily_kline_data_tushare(stock_code)
            if kline_data and kline_data.get('data') is not None:
                df = kline_data['data']
                report_lines.append(f"- K线数据: {len(df)}根, 最新收盘: {df['收盘'].values[-1]:.2f}")
            else:
                report_lines.append("- ❌ 获取K线数据失败")
        except Exception as e:
            report_lines.append(f"- ❌ 数据获取异常: {e}")
        report_lines.append("\n## 2. 大盘环境分析")
        market_ctx = self._analyze_market_context()
        report_lines.append(f"- 情绪: {market_ctx['sentiment']}")
        report_lines.append(f"- 上证: {market_ctx['sh_change']:+.2f}%, 深证: {market_ctx['sz_change']:+.2f}%, 创业板: {market_ctx['cyb_change']:+.2f}%")
        report_lines.append(f"- 上涨{market_ctx['up_count']}家 / 下跌{market_ctx['down_count']}家")
        report_lines.append(f"- 大盘建议: {market_ctx['advice']}")
        report_lines.append(f"- 仓位上限: {market_ctx['position_cap']}%")
        report_lines.append("\n**推导过程**:")
        for step in market_ctx.get("reasoning", []):
            report_lines.append(f"  - {step}")
        all_signals.append({"type": "market", "sentiment": market_ctx["sentiment"], "data": market_ctx})
        report_lines.append("\n## 3. 风控过滤 (T5)")
        risk = self._risk_filter_stock(stock_code, stock_name, kline_data)
        report_lines.append("- ✅ 通过风控过滤" if risk["pass"] else "- ❌ 未通过风控过滤")
        for r in risk["reasons"]:
            report_lines.append(f"  - {r}")
        for w in risk["warnings"]:
            report_lines.append(f"  - ⚠️ {w}")
        all_signals.append({"type": "risk", "pass": risk["pass"], "data": risk})
        report_lines.append("\n## 4. 段基评分 (DJ)")
        dj = self._duanji_score(stock_code, kline_data)
        report_lines.append(f"- 总分: {dj['total']}/{dj['max']}")
        report_lines.append(f"- 判定: {dj['verdict']}")
        for dim, score in dj["scores"].items():
            report_lines.append(f"  - {dim}: {score}/15")
        all_signals.append({"type": "duanji", "score": dj["total"], "data": dj})
        report_lines.append("\n## 5. 芒格5%机会扫描 (MG)")
        mg = self._munger_5pct_scan(stock_code, kline_data, market_ctx)
        if mg["triggered"]:
            report_lines.append(f"- 🔔 触发: {mg['group']}")
            report_lines.append(f"- 信号: {mg['signal']}")
        else:
            report_lines.append("- 未触发5%机会信号")
        all_signals.append({"type": "munger", "triggered": mg["triggered"], "data": mg})
        report_lines.append("\n## 6. 闪电交易系统 (SD)")
        sd = self._lightning_analyze(stock_code, kline_data)
        report_lines.append(f"- 操作: {sd['action']}, 建议仓位: {sd['position']}")
        for sig in sd["signals"]:
            report_lines.append(f"  - {sig}")
        all_signals.append({"type": "lightning", "action": sd["action"], "data": sd})
        report_lines.append("\n## 7. P阶段分类 (PP)")
        pp = self._p_phase_classify(kline_data)
        report_lines.append(f"- 阶段: {pp['phase']} - {pp['description']}")
        for k, v in pp.get("score", {}).items():
            report_lines.append(f"  - {k}: {v}")
        all_signals.append({"type": "p_phase", "phase": pp["phase"], "data": pp})
        report_lines.append("\n## 8. 坐电梯指标 (ZT)")
        zt = self._elevator_signal(kline_data)
        report_lines.append(f"- 信号: {zt['signal']}, 快线: {zt['fast']:.1f}, 慢线: {zt['slow']:.1f}")
        report_lines.append(f"- 操作建议: {zt['action']}")
        all_signals.append({"type": "elevator", "signal": zt["signal"], "data": zt})
        report_lines.append("\n## 9. 均值回归 (布林带)")
        mr = self._mean_reversion_scan_enhanced(stock_code, kline_data)
        report_lines.append(f"- 信号: {mr['signal']}")
        report_lines.append(f"- 布林上轨: {mr['boll_upper']:.2f}, 中轨: {mr['boll_mid']:.2f}, 下轨: {mr['boll_lower']:.2f}")
        if mr["position"]:
            report_lines.append(f"- 位置: {mr['position']}")
        all_signals.append({"type": "mean_reversion", "signal": mr["signal"], "data": mr})
        # 统计买卖信号
        buy_signals = sum(1 for s in all_signals if s.get("type") == "munger" and s.get("triggered"))
        buy_signals += sum(1 for s in all_signals if s.get("type") == "elevator" and s.get("signal") in ("金叉", "多头"))
        buy_signals += sum(1 for s in all_signals if s.get("type") == "lightning" and "买入" in str(s.get("action", "")))
        buy_signals += sum(1 for s in all_signals if s.get("type") == "mean_reversion" and "支撑" in str(s.get("signal", "")))
        sell_signals = sum(1 for s in all_signals if s.get("type") == "elevator" and s.get("signal") in ("死叉", "空头"))
        sell_signals += sum(1 for s in all_signals if s.get("type") == "lightning" and "清仓" in str(s.get("action", "")))
        sell_signals += sum(1 for s in all_signals if s.get("type") == "mean_reversion" and "阻力" in str(s.get("signal", "")))
        report_lines.append("\n## 10. 综合仓位与买卖建议")
        pos_advice = self._calculate_position_advice(
            market_ctx, buy_signals, sell_signals, risk["pass"], dj["total"], pp.get("phase", "P1")
        )
        report_lines.append(f"### 📊 操作建议: {pos_advice['action']}")
        report_lines.append(f"### 💰 建议仓位: {pos_advice['position_pct']}%")
        report_lines.append("\n**推理过程**:")
        report_lines.append(f"  {pos_advice['reasoning']}")
        report_lines.append(f"\n**信号汇总**: 买入{buy_signals}个 / 卖出{sell_signals}个")
        report_lines.append(f"\n**大盘环境**: {market_ctx['sentiment']} (仓位上限{market_ctx['position_cap']}%)")
        if pos_advice['position_pct'] <= 0:
            report_lines.append("\n⚠️ **当前建议空仓**,以下任一原因可能导致:")
            if not risk["pass"]:
                report_lines.append("  - 风控未通过")
            if sell_signals >= 3:
                report_lines.append(f"  - 卖出信号{sell_signals}个,偏空")
            if market_ctx['position_cap'] <= 15:
                report_lines.append("  - 大盘恐慌,系统性风险高")
        report_lines.append("\n---\n⚠️ 免责声明:以上分析为量化模型输出,仅供参考,不构成投资建议。")
        return {"report": "\n".join(report_lines), "signals": all_signals, "buy_count": buy_signals, "sell_count": sell_signals, "risk_pass": risk["pass"], "duanji_score": dj["total"], "position_pct": pos_advice["position_pct"], "market_sentiment": market_ctx["sentiment"]}

    def _save_analysis_report(self, stock_code, stock_name, report_text, report_type="综合分析"):
        """T8: 统一报告格式(frontmatter + 落盘 + 写入news_info)"""
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            workspace_dir = os.path.expanduser("~/.qclaw/workspace")
            os.makedirs(workspace_dir, exist_ok=True)
            filepath = os.path.join(workspace_dir, f"报告_{report_type}_{stock_name}_{timestamp}.md")
            content = f"---\ndate: {date_str}\ntype: {report_type}\nstock: {stock_name}({stock_code})\nsource: stockyidong_mac\n---\n\n{report_text}\n"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO news_info (tab_name, content) VALUES (?, ?)", (f"📊 {report_type}|{date_str}", report_text))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"写入news_info失败: {e}")
            return filepath
        except Exception as e:
            print(f"保存报告失败: {e}")
            return None

    def show_stock_analysis_engine_dialog(self):
        """T4: 股票分析引擎对话框(统一入口)"""
        win = self._toplevel(self.root)
        win.title("股票分析引擎 · 统一分析入口")
        win.geometry("900x700")
        win.transient(self.root)
        top = ttk.Frame(win, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="股票:", font=("Microsoft YaHei", 11)).pack(side=tk.LEFT)
        stock_var = tk.StringVar()
        stock_combo = ttk.Combobox(top, textvariable=stock_var, width=30, state="normal")
        stock_combo.pack(side=tk.LEFT, padx=6)
        # 填充下拉列表:持仓股 + 龙头股 + Main持仓 + 同花顺热门
        stock_values = []
        for attr in ("holding_stocks", "holding_stocks_2", "holding_stocks_4"):
            arr = getattr(self, attr, []) or []
            for it in arr:
                if isinstance(it, (tuple, list)) and len(it) >= 2 and it[0] and it[1]:
                    stock_values.append(f"{it[0]}({it[1]})")
                elif isinstance(it, dict) and it.get('code'):
                    stock_values.append(f"{it.get('name','')}({it.get('code','')})")
        # 追加同花顺热门股(从 get_hot_stocks 获取)
        try:
            hot_stocks = get_hot_stocks(limit=15)
            for hs in hot_stocks:
                code = hs.get('代码', '')
                name = hs.get('名称', '')
                if code and name:
                    stock_values.append(f"{name}({code})")
        except Exception:
            pass
        stock_combo['values'] = list(dict.fromkeys(stock_values))
        ttk.Button(top, text="分析", width=10, command=lambda: self._run_engine_analysis(win, stock_var, result_text, status_var)).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="保存报告", width=10, command=lambda: self._save_engine_report(stock_var, result_text, win)).pack(side=tk.LEFT, padx=6)
        status_var = tk.StringVar(value="就绪")
        ttk.Label(top, textvariable=status_var).pack(side=tk.LEFT, padx=10)
        result_text = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Microsoft YaHei", 10))
        result_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self._configure_ai_staff_text_tags(result_text)

    def _run_engine_analysis(self, win, stock_var, result_text, status_var):
        """执行统一分析引擎"""
        import re
        import threading
        raw = stock_var.get().strip()
        if not raw:
            messagebox.showwarning("提示", "请输入或选择股票", parent=win)
            return
        # 优先从输入中提取6位股票代码
        m = re.search(r"(\d{6})", raw)
        if m:
            stock_code = m.group(1)
            stock_name = raw.replace(stock_code, "").replace("(", "").replace(")", "").strip()
        else:
            # 未找到代码,尝试按股票名称查找
            stock_name = raw.replace("(", "").replace(")", "").strip()
            stock_code = ""
            # 1. 从全局名称→代码缓存查找
            try:
                global STOCK_NAME_TO_CODE
                if STOCK_NAME_TO_CODE and stock_name in STOCK_NAME_TO_CODE:
                    stock_code = STOCK_NAME_TO_CODE[stock_name]
            except Exception:
                pass
            # 2. 模糊匹配(输入名称是全称的一部分)
            if not stock_code:
                try:
                    global STOCK_NAMES_SET, STOCK_CODES_DICT
                    # 确保缓存已加载
                    if not STOCK_NAMES_SET:
                        load_stock_names()
                    # 精确匹配
                    if STOCK_NAME_TO_CODE and stock_name in STOCK_NAME_TO_CODE:
                        stock_code = STOCK_NAME_TO_CODE[stock_name]
                    # 模糊匹配:输入是某股票名子串
                    elif STOCK_NAME_TO_CODE:
                        matches = [n for n in STOCK_NAME_TO_CODE if stock_name in n]
                        if len(matches) == 1:
                            stock_name = matches[0]
                            stock_code = STOCK_NAME_TO_CODE[matches[0]]
                        elif len(matches) > 1:
                            messagebox.showwarning("提示", f"找到多个匹配:{', '.join(matches[:5])},请输入更精确的名称", parent=win)
                            return
                except Exception:
                    pass
            # 3. 查找不到,提示
            if not stock_code:
                messagebox.showwarning("提示", f"无法识别股票「{raw}」,请输入6位代码或完整股票名称", parent=win)
                return
        status_var.set("分析中...")
        result_text.delete("1.0", tk.END)
        result_text.insert("1.0", "正在运行分析引擎,请稍候...\n")
        def work():
            try:
                result = self._run_stock_analysis_engine(stock_code, stock_name)
                def _done():
                    result_text.delete("1.0", tk.END)
                    result_text.insert("1.0", result["report"])
                    self._apply_ai_staff_keyword_highlights(result_text)
                    status_var.set(f"完成(买入{result['buy_count']}/卖出{result['sell_count']}|仓位{result.get('position_pct',0)}%|{result.get('market_sentiment','')})")
                win.after(0, _done)
            except Exception as e:
                def _err(e=e):
                    result_text.delete("1.0", tk.END)
                    result_text.insert("1.0", f"分析失败: {e}")
                    status_var.set("失败")
                win.after(0, _err)
        threading.Thread(target=work, daemon=True).start()


__all__ = ["AnalysisMixin"]
