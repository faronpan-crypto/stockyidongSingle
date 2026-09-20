"""Web爬虫"""
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

from datetime import datetime, timedelta
import re
import os
import sys
import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class WebMixin:
    """Web爬虫"""

    def launch_keyword_search_app(self):
        """启动关键词搜索:优先 KeywordOpinionProject/legacy_keyword_opinion_app/keyword_search_app.py,否则回退 public_opinion_analyzer。"""
        try:
            import os
            import subprocess
            import sys
            base_dir = os.path.dirname(os.path.abspath(__file__))
            repo_root = os.path.normpath(os.path.join(base_dir, "..", ".."))
            legacy_script = os.path.join(
                repo_root,
                "KeywordOpinionProject",
                "legacy_keyword_opinion_app",
                "keyword_search_app.py",
            )
            fallback_script = os.path.join(repo_root, "public_opinion_analyzer", "keyword_search_app.py")
            if os.path.isfile(legacy_script):
                script_path = legacy_script
            elif os.path.isfile(fallback_script):
                script_path = fallback_script
            else:
                messagebox.showerror(
                    "错误",
                    "未找到关键词搜索入口脚本,已尝试:\n"
                    f"1. {legacy_script}\n"
                    f"2. {fallback_script}",
                    parent=self.root,
                )
                return
            app_dir = os.path.dirname(os.path.abspath(script_path))
            popen_kw = {"cwd": app_dir, "encoding": "utf-8", "errors": "replace"}
            if sys.platform == "win32":
                popen_kw["creationflags"] = subprocess.CREATE_NEW_CONSOLE
            subprocess.Popen([sys.executable, script_path], **popen_kw)
        except Exception as e:
            messagebox.showerror("错误", f"启动关键词搜索失败: {e}", parent=self.root)

    def show_web_crawler(self):
        """打开网站爬虫程序"""
        try:
            win = self._toplevel(self.root)
            win.title("网站爬虫程序")
            win.geometry("1200x800")
            win.transient(self.root)
            win.resizable(True, True)
            # 主容器
            main_frame = ttk.Frame(win, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)
            # 顶部:设置区域
            settings_frame = ttk.LabelFrame(main_frame, text="爬虫设置", padding=10)
            settings_frame.pack(fill=tk.X, pady=(0, 10))
            # 爬取层数设置
            depth_frame = ttk.Frame(settings_frame)
            depth_frame.pack(fill=tk.X, pady=5)
            ttk.Label(depth_frame, text="爬取层数:", width=12).pack(side=tk.LEFT, padx=5)
            depth_var = tk.IntVar(value=3)  # 默认3层
            depth_spinbox = ttk.Spinbox(depth_frame, from_=1, to=10, textvariable=depth_var, width=10)
            depth_spinbox.pack(side=tk.LEFT, padx=5)
            ttk.Label(depth_frame, text="(默认3层)", font=("TkDefaultFont", 8), foreground="gray").pack(side=tk.LEFT, padx=5)
            # 保存目录设置
            save_dir_frame = ttk.Frame(settings_frame)
            save_dir_frame.pack(fill=tk.X, pady=5)
            ttk.Label(save_dir_frame, text="保存目录:", width=12).pack(side=tk.LEFT, padx=5)
            save_dir_var = tk.StringVar(value=os.path.join(D_DATA_DIR, "CrawledWebsites"))
            save_dir_entry = ttk.Entry(save_dir_frame, textvariable=save_dir_var, width=50)
            save_dir_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            def browse_save_dir():
                dir_path = filedialog.askdirectory(title="选择保存目录", initialdir=save_dir_var.get())
                if dir_path:
                    save_dir_var.set(dir_path)
            ttk.Button(save_dir_frame, text="浏览", command=browse_save_dir, width=10).pack(side=tk.LEFT, padx=5)
            # 其他设置
            other_settings_frame = ttk.Frame(settings_frame)
            other_settings_frame.pack(fill=tk.X, pady=5)
            delay_var = tk.DoubleVar(value=1.0)  # 请求延迟(秒)
            ttk.Label(other_settings_frame, text="请求延迟:", width=12).pack(side=tk.LEFT, padx=5)
            delay_spinbox = ttk.Spinbox(other_settings_frame, from_=0.1, to=10.0, increment=0.1,
                                       textvariable=delay_var, width=10, format="%.1f")
            delay_spinbox.pack(side=tk.LEFT, padx=5)
            ttk.Label(other_settings_frame, text="秒", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=5)
            max_pages_var = tk.IntVar(value=100)  # 最大页面数
            ttk.Label(other_settings_frame, text="最大页面数:", width=12).pack(side=tk.LEFT, padx=5)
            max_pages_spinbox = ttk.Spinbox(other_settings_frame, from_=1, to=1000,
                                           textvariable=max_pages_var, width=10)
            max_pages_spinbox.pack(side=tk.LEFT, padx=5)
            # 选中的网址列表
            url_frame = ttk.LabelFrame(main_frame, text="待爬取的网址", padding=10)
            url_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            # 获取选中的爬取项
            selected_urls = []
            crawler_info = {
                'taoguba': {'name': '淘股吧', 'url': 'https://www.taoguba.com.cn/'},
                'jiuyan': {'name': '韭研', 'url': 'https://www.jiuyangongshe.com/'},
                'eastmoney': {'name': '东方财富', 'url': 'https://www.eastmoney.com/'},
                'xueqiu': {'name': '雪球', 'url': 'https://xueqiu.com/'},
                'xuangubao': {'name': '选股宝', 'url': 'https://xuangubao.cn/'},
                'ths': {'name': '同花顺', 'url': 'https://www.10jqka.com.cn/'}
            }
            for key, info in crawler_info.items():
                if key in self.crawler_checkboxes and self.crawler_checkboxes[key].get():
                    selected_urls.append((key, info['name'], info['url']))
            # 获取选中的市场导航项
            if hasattr(self, 'market_nav_checkboxes') and self.market_nav_checkboxes:
                for checkbox_key, checkbox_info in self.market_nav_checkboxes.items():
                    if checkbox_info['var'].get():
                        name = checkbox_info['name']
                        url = checkbox_info['url']
                        if url:
                            selected_urls.append((checkbox_key, name, url))
            # 显示选中的网址
            url_listbox = tk.Listbox(url_frame, height=10, font=("Courier", 11))
            url_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
            for key, name, url in selected_urls:
                url_listbox.insert(tk.END, f"{name}: {url}")
            if not selected_urls:
                url_listbox.insert(tk.END, "未选中任何网址,请在主界面勾选爬取项或市场导航项")
            # 控制按钮
            control_frame = ttk.Frame(main_frame)
            control_frame.pack(fill=tk.X)
            def start_crawl():
                """开始爬取"""
                if not selected_urls:
                    messagebox.showwarning("警告", "请先在主界面勾选要爬取的网址")
                    return
                save_dir = save_dir_var.get()
                if not save_dir:
                    messagebox.showwarning("警告", "请设置保存目录")
                    return
                # 确认开始
                result = messagebox.askyesno("确认",
                    f"将开始爬取 {len(selected_urls)} 个网址\n"
                    f"爬取层数: {depth_var.get()}\n"
                    f"保存目录: {save_dir}\n\n"
                    f"是否继续?")
                if not result:
                    return
                # 在新线程中执行爬取
                thread = threading.Thread(
                    target=self._web_crawler_thread,
                    args=(selected_urls, save_dir, depth_var.get(), delay_var.get(), max_pages_var.get()),
                    daemon=True
                )
                thread.start()
                messagebox.showinfo("提示", "爬取任务已启动,请查看日志输出")
            ttk.Button(control_frame, text="开始爬取", command=start_crawl, width=15).pack(side=tk.LEFT, padx=5)
            ttk.Button(control_frame, text="刷新列表",
                      command=lambda: self.show_web_crawler(), width=15).pack(side=tk.LEFT, padx=5)
            ttk.Button(control_frame, text="关闭", command=win.destroy, width=15).pack(side=tk.RIGHT, padx=5)
            # 日志显示区域
            log_frame = ttk.LabelFrame(main_frame, text="爬取日志", padding=5)
            log_frame.pack(fill=tk.BOTH, expand=True)
            log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD, font=("Courier", 11))
            log_text.pack(fill=tk.BOTH, expand=True)
            log_text.insert("1.0", f"已选择 {len(selected_urls)} 个网址待爬取\n")
            log_text.insert(tk.END, f"默认爬取层数: {depth_var.get()}\n")
            log_text.insert(tk.END, f"保存目录: {save_dir_var.get()}\n")
            log_text.config(state=tk.DISABLED)
            # 保存日志引用以便线程使用
            win.log_text = log_text
        except Exception as e:
            messagebox.showerror("错误", f"打开网站爬虫程序失败: {e}")
            import traceback
            traceback.print_exc()

    def _web_crawler_thread(self, selected_urls, save_dir, max_depth, delay, max_pages):
        """网站爬虫线程(简化版,只使用requests)"""
        try:
            import hashlib
            from urllib.parse import urljoin, urlparse

            import requests
            from bs4 import BeautifulSoup
        except ImportError as e:
            self.root.after(0, lambda e=e: messagebox.showerror("错误", f"缺少必要的库: {e}\n\n请运行: pip install requests beautifulsoup4"))
            return
        visited_urls = set()
        url_queue = []
        page_count = 0
        # 先定义log_message函数,以便后续使用
        def log_message(msg):
            """在UI线程中更新日志"""
            def update_log():
                try:
                    # 查找爬虫窗口
                    for widget in self.root.winfo_children():
                        if isinstance(widget, tk.Toplevel) and widget.title() == "网站爬虫程序":
                            if hasattr(widget, 'log_text'):
                                widget.log_text.config(state=tk.NORMAL)
                                widget.log_text.insert(tk.END, f"{msg}\n")
                                widget.log_text.see(tk.END)
                                widget.log_text.config(state=tk.DISABLED)
                            break
                except:
                    pass
            self.root.after(0, update_log)
        def _is_garbled(text):
            """检测文本是否包含乱码"""
            if not text:
                return False
            # 检查常见乱码模式
            garbled_patterns = [
                '锘', '', '', '',  # 常见的BOM或编码错误标记
            ]
            # 检查是否包含大量乱码字符
            garbled_count = sum(1 for pattern in garbled_patterns if pattern in text)
            if garbled_count > 0:
                return True
            # 检查中文字符比例(如果文本很长但中文字符很少,可能是乱码)
            if len(text) > 100:
                chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
                chinese_ratio = chinese_chars / len(text)
                # 如果文本很长但中文字符比例很低,且包含很多特殊字符,可能是乱码
                if chinese_ratio < 0.01 and len(text) > 500:
                    # 检查是否包含大量不可打印字符
                    unprintable = sum(1 for c in text if ord(c) > 127 and c not in '\u4e00-\u9fff\u3000-\u303f\uff00-\uffef')
                    if unprintable / len(text) > 0.3:
                        return True
            return False
        def get_domain_name(url):
            """从URL获取域名作为目录名"""
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.replace('www.', '').replace('.', '_')
                return domain
            except:
                return "unknown"
        def save_page(url, content, depth, base_dir, encoding='utf-8'):
            """保存页面内容,并确保HTML中设置正确的编码"""
            try:
                domain = get_domain_name(url)
                domain_dir = os.path.join(base_dir, domain)
                os.makedirs(domain_dir, exist_ok=True)
                # 创建深度目录
                depth_dir = os.path.join(domain_dir, f"depth_{depth}")
                os.makedirs(depth_dir, exist_ok=True)
                # 生成文件名(使用URL的hash)
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                parsed = urlparse(url)
                path = parsed.path.strip('/').replace('/', '_') or 'index'
                filename = f"{path}_{url_hash}.html"
                filepath = os.path.join(depth_dir, filename)
                # 确保HTML中设置了正确的charset
                fixed_content = ensure_html_charset(content, encoding)
                # 统一保存为UTF-8编码
                with open(filepath, 'w', encoding='utf-8', errors='replace') as f:
                    f.write(fixed_content)
                return filepath
            except Exception as e:
                log_message(f"保存页面失败 {url}: {e}")
                return None
        def ensure_html_charset(html_content, encoding):
            """确保HTML内容中设置了正确的charset"""
            try:
                # 如果内容已经是字符串,直接处理
                if not isinstance(html_content, str):
                    return html_content
                # 查找并更新charset
                soup = BeautifulSoup(html_content, 'html.parser')
                # 查找现有的charset meta标签
                charset_set = False
                for meta in soup.find_all('meta'):
                    # 检查charset属性
                    if meta.get('charset'):
                        meta['charset'] = 'utf-8'
                        charset_set = True
                        break
                    # 检查http-equiv
                    http_equiv = meta.get('http-equiv', '').lower()
                    if http_equiv == 'content-type':
                        content = meta.get('content', '')
                        if 'charset=' in content.lower():
                            meta['content'] = "text/html; charset=utf-8"
                            charset_set = True
                            break
                # 如果没有找到charset,在head中添加
                if not charset_set:
                    head = soup.find('head')
                    if head:
                        charset_meta = soup.new_tag('meta', charset='utf-8')
                        # 插入到head的最前面
                        if head.contents:
                            head.insert(0, charset_meta)
                        else:
                            head.append(charset_meta)
                    else:
                        # 如果没有head标签,创建一个
                        html_tag = soup.find('html')
                        if html_tag:
                            head = soup.new_tag('head')
                            html_tag.insert(0, head)
                            charset_meta = soup.new_tag('meta', charset='utf-8')
                            head.append(charset_meta)
                return str(soup)
            except Exception as e:
                # 如果处理失败,返回原内容
                log_message(f"  ⚠️ 设置HTML charset失败: {e}")
                return html_content
        def detect_and_fix_encoding(content_bytes, url):
            """检测并修复编码"""
            detected_encoding = None
            fixed_content = None
            # 尝试使用chardet库自动检测
            try:
                import chardet
                result = chardet.detect(content_bytes)
                if result and result['encoding'] and result['confidence'] > 0.7:
                    detected_encoding = result['encoding']
                    log_message(f"  📝 chardet检测编码: {detected_encoding} (置信度: {result['confidence']:.2f})")
            except ImportError:
                pass
            except Exception as e:
                log_message(f"  ⚠️ chardet检测失败: {e}")
            # 尝试从HTML的meta标签中提取编码
            try:
                # 先尝试用检测到的编码或utf-8解析前几KB来查找meta标签
                test_encoding = detected_encoding or 'utf-8'
                try:
                    test_content = content_bytes[:50000].decode(test_encoding, errors='ignore')
                    soup = BeautifulSoup(test_content, 'html.parser')
                    # 查找charset
                    meta_charset = soup.find('meta', charset=True)
                    if meta_charset:
                        meta_encoding = meta_charset.get('charset', '').lower()
                        if meta_encoding:
                            detected_encoding = meta_encoding
                            log_message(f"  📝 从meta标签检测编码: {detected_encoding}")
                    # 查找http-equiv content-type
                    if not detected_encoding:
                        meta_http_equiv = soup.find('meta', attrs={'http-equiv': lambda x: x and x.lower() == 'content-type'})
                        if meta_http_equiv:
                            content_type = meta_http_equiv.get('content', '')
                            if 'charset=' in content_type.lower():
                                meta_encoding = content_type.split('charset=')[-1].split(';')[0].strip().lower()
                                if meta_encoding:
                                    detected_encoding = meta_encoding
                                    log_message(f"  📝 从http-equiv检测编码: {detected_encoding}")
                except:
                    pass
            except Exception as e:
                log_message(f"  ⚠️ meta标签检测失败: {e}")
            # 尝试多种编码方式
            encodings_to_try = []
            if detected_encoding:
                encodings_to_try.append(detected_encoding)
            # 添加常见编码
            common_encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'latin1', 'iso-8859-1', 'windows-1252']
            for enc in common_encodings:
                if enc not in encodings_to_try:
                    encodings_to_try.append(enc)
            # 尝试解码
            for encoding in encodings_to_try:
                try:
                    decoded = content_bytes.decode(encoding, errors='strict')
                    # 检查是否包含乱码字符(常见乱码模式)
                    if _is_garbled(decoded):
                        continue
                    fixed_content = decoded
                    if encoding != 'utf-8':
                        log_message(f"  ✓ 使用编码: {encoding}")
                    return fixed_content, encoding
                except (UnicodeDecodeError, LookupError):
                    continue
                except Exception as e:
                    log_message(f"  ⚠️ 尝试编码 {encoding} 失败: {e}")
                    continue
            # 如果都失败,使用errors='replace'或'ignore'作为最后手段
            try:
                final_encoding = detected_encoding or 'utf-8'
                fixed_content = content_bytes.decode(final_encoding, errors='replace')
                log_message(f"  ⚠️ 使用 {final_encoding} 并替换错误字符")
                return fixed_content, final_encoding
            except:
                # 最后的fallback
                fixed_content = content_bytes.decode('utf-8', errors='replace')
                log_message("  ⚠️ 使用utf-8并替换错误字符(最后手段)")
                return fixed_content, 'utf-8'
        def crawl_url(url, current_depth, base_dir):
            """爬取单个URL(简化版)"""
            nonlocal page_count
            if current_depth > max_depth or page_count >= max_pages:
                return []
            if url in visited_urls:
                return []
            visited_urls.add(url)
            page_count += 1
            try:
                log_message(f"[深度 {current_depth}] 爬取: {url}")
                # 使用requests爬取
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Connection': 'keep-alive',
                }
                response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
                if response.status_code != 200:
                    log_message(f"  ⚠️ HTTP状态码: {response.status_code}")
                    return []
                # 获取原始字节内容
                content_bytes = response.content
                log_message(f"  获取到内容: {len(content_bytes)} 字节")
                # 检测并修复编码
                fixed_content, used_encoding = detect_and_fix_encoding(content_bytes, url)
                if not fixed_content:
                    log_message("  ✗ 页面内容为空,爬取失败")
                    return []
                # 保存页面
                filepath = save_page(url, fixed_content, current_depth, base_dir, used_encoding)
                if filepath:
                    content_size = len(fixed_content) if fixed_content else 0
                    log_message(f"  ✓ 已保存: {os.path.basename(filepath)} (编码: {used_encoding}, 大小: {content_size} 字符)")
                else:
                    log_message("  ✗ 保存页面失败")
                # 如果还没到最大深度,提取链接
                found_urls = []
                if current_depth < max_depth:
                    try:
                        # 使用修复后的内容解析链接
                        soup = BeautifulSoup(fixed_content, 'html.parser')
                        for link in soup.find_all('a', href=True):
                            href = link['href']
                            absolute_url = urljoin(url, href)
                            # 只爬取同域名的链接
                            if urlparse(absolute_url).netloc == urlparse(url).netloc:
                                if absolute_url not in visited_urls and absolute_url not in url_queue:
                                    found_urls.append(absolute_url)
                    except Exception as e:
                        log_message(f"  ⚠️ 解析链接失败: {e}")
                # 延迟
                time.sleep(delay)
                return found_urls
            except Exception as e:
                log_message(f"  ✗ 爬取失败: {e}")
                return []
        # 确保保存目录存在
        os.makedirs(save_dir, exist_ok=True)
        log_message(f"\n{'='*60}")
        log_message("开始爬取任务")
        log_message(f"网址数量: {len(selected_urls)}")
        log_message(f"最大深度: {max_depth}")
        log_message(f"最大页面数: {max_pages}")
        log_message(f"保存目录: {save_dir}")
        log_message(f"{'='*60}\n")
        # 初始化队列
        for key, name, url in selected_urls:
            url_queue.append((url, 1))  # (url, depth)
            log_message(f"添加初始URL: {name} - {url}")
        # 开始爬取
        while url_queue and page_count < max_pages:
            url, depth = url_queue.pop(0)
            found_urls = crawl_url(url, depth, save_dir)
            # 添加找到的链接到队列
            for found_url in found_urls:
                if depth < max_depth:
                    url_queue.append((found_url, depth + 1))
        log_message(f"\n{'='*60}")
        log_message("爬取完成!")
        log_message(f"总共爬取: {page_count} 个页面")
        log_message(f"保存目录: {save_dir}")
        log_message(f"{'='*60}")
        self.root.after(0, lambda: messagebox.showinfo("完成", f"爬取任务完成!\n\n共爬取 {page_count} 个页面\n保存目录: {save_dir}"))

    def _copy_text_to_clipboard(self, text_widget):
        """复制文本到剪贴板"""
        try:
            content = text_widget.get("1.0", tk.END).strip()
            if content:
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                messagebox.showinfo("成功", "结果已复制到剪贴板")
            else:
                messagebox.showinfo("提示", "没有可复制的内容")
        except Exception as e:
            messagebox.showerror("错误", f"复制失败: {e}")

    def _detect_garbled_text(self, text):
        """检测文本是否包含乱码
        Returns:
            bool: True表示可能包含乱码,False表示正常
        """
        if not text or len(text) < 10:
            return False
        # 检测常见乱码特征
        # 1. 检测大量无法识别的Unicode字符(替换字符、控制字符等)
        garbled_chars = ['\ufffd', '\x00', '\x01', '\x02', '\x03', '\x04', '\x05']
        garbled_count = sum(text.count(char) for char in garbled_chars)
        if garbled_count > len(text) * 0.1:  # 超过10%的字符是乱码
            return True
        # 2. 检测是否包含大量非中文字符且非ASCII字符(可能是编码错误)
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        total_chars = len([c for c in text if c.strip()])
        if total_chars > 0:
            chinese_ratio = chinese_chars / total_chars
            # 如果文本很长但中文字符很少,且包含很多特殊字符,可能是乱码
            if len(text) > 100 and chinese_ratio < 0.1 and (total_chars - ascii_chars - chinese_chars) > total_chars * 0.3:
                return True
        # 3. 检测是否包含大量连续的特殊符号(可能是编码错误)
        special_pattern = re.compile(r'[^\w\s\u4e00-\u9fff]{5,}')
        return len(special_pattern.findall(text)) > 3

    def _fix_encoding(self, content_bytes, encodings=None):
        """尝试使用多种编码修正内容
        Args:
            content_bytes: 字节内容
            encodings: 要尝试的编码列表,默认尝试常见编码
        Returns:
            tuple: (修正后的文本, 使用的编码) 或 (None, None) 如果都失败
        """
        if encodings is None:
            encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'utf-16', 'latin-1', 'cp1252']
        for encoding in encodings:
            try:
                decoded_text = content_bytes.decode(encoding, errors='strict')
                # 检查解码后的文本是否还有乱码
                if not self._detect_garbled_text(decoded_text):
                    return decoded_text, encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception:
                continue
        # 如果严格解码都失败,尝试使用errors='replace'或'ignore'
        for encoding in encodings[:3]:  # 只尝试前3个最常用的
            try:
                decoded_text = content_bytes.decode(encoding, errors='replace')
                # 即使有替换字符,也返回结果
                return decoded_text, encoding
            except Exception:
                continue
        return None, None

    def _extract_xuangutong_zhutiku_stocks_from_html(self, html_content: str):
        """从主题库 HTML 提取领涨股。
        选股通 zhutiku 为 Nuxt:股票主要在 __NUXT__.data[0].initialServerData.trendingPlateServiceData
        的 items[].stocks[] 中;静态 HTML 里几乎没有 /stock/ 链接,旧逻辑会「爬不全」或漏股。
        服务端通常只推送少量主题预览(约几条),全量主题在浏览器分页/登录后加载,本方法无法替代浏览器抓全站。
        """
        stocks = []
        seen = set()
        index_codes = {
            "000001",
            "000016",
            "000300",
            "000688",
            "000852",
            "000905",
            "399001",
            "399006",
            "399300",
            "899050",
        }
        try:
            data = self._parse_nuxt_from_html_safe(html_content)
            items = (
                (data.get("data") or [{}])[0]
                .get("initialServerData", {})
                .get("trendingPlateServiceData", {})
                .get("items")
                or []
            )
            for it in items:
                for st in it.get("stocks") or []:
                    sym = str(st.get("symbol") or "").strip().upper().replace(".SS", ".SH")
                    name = str(st.get("name") or "").strip()
                    m = re.match(r"^(\d{6})\.(SZ|SH|BJ)$", sym)
                    if not m:
                        continue
                    code = m.group(1)
                    if code in index_codes or code in seen:
                        continue
                    seen.add(code)
                    stocks.append({"name": name, "code": code})
        except Exception as e:
            print(f"[选股通] Nuxt 解析跳过: {e}")
        soup = BeautifulSoup(html_content, "html.parser")
        stock_pattern = re.compile(r"/stock/(\d{6})\.(SZ|SS|SH|BJ)", re.IGNORECASE)
        name_pct_pattern = re.compile(r"([\u4e00-\u9fa5]{2,})([+-]?\d+\.?\d*%?)")
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            match = stock_pattern.search(href)
            if not match:
                continue
            stock_code = match.group(1)
            if stock_code in index_codes or stock_code in seen:
                continue
            link_text = link.get_text(strip=True)
            name_match = name_pct_pattern.match(link_text)
            stock_name = (
                name_match.group(1)
                if name_match
                else re.sub(r"[+-]?\d+\.?\d*%?", "", link_text).strip()
            )
            if len(stock_name) < 2:
                continue
            seen.add(stock_code)
            stocks.append({"name": stock_name, "code": stock_code})
        if len(stocks) < 3:
            text_content = soup.get_text()
            code_pattern = re.compile(r"(\d{6})\.(SZ|SH|SS|BJ)", re.IGNORECASE)
            for match in code_pattern.finditer(text_content):
                stock_code = match.group(1)
                if stock_code in index_codes or stock_code in seen:
                    continue
                if stock_code.startswith(("0", "3", "6")):
                    seen.add(stock_code)
                    stocks.append({"name": "", "code": stock_code})
        return stocks

    def _enable_text_copy_menu(text_widget, readonly=True):
        """
        给任意 Text / ScrolledText 组件加上:
          1. 右键菜单(复制 / 全选 / 粘贴 / 剪切 / 清空)
          2. Cmd+A (macOS) / Ctrl+A (Win/Linux) 全选快捷键
          3. 拖拽选中 + 双击选词(Tk 自带)
        readonly=True 时只保留 复制/全选,禁用粘贴/剪切/清空
        """
        w = text_widget
        def _copy():
            try:
                sel = w.get("sel.first", "sel.last")
                if sel:
                    w.clipboard_clear()
                    w.clipboard_append(sel)
                    w.update()
            except tk.TclError:
                pass  # 没有选中
        def _select_all():
            w.tag_add("sel", "1.0", "end-1c")
            w.mark_set("insert", "1.0")
            w.see("insert")
        def _paste():
            if readonly:
                return
            try:
                clip = w.clipboard_get()
                if clip:
                    w.insert("insert", clip)
            except tk.TclError:
                pass
        def _cut():
            if readonly:
                return
            try:
                sel = w.get("sel.first", "sel.last")
                if sel:
                    w.clipboard_clear()
                    w.clipboard_append(sel)
                    w.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
        def _clear():
            if readonly:
                return
            w.delete("1.0", tk.END)
        menu = tk.Menu(w, tearoff=0)
        menu.add_command(label="📋 复制 (⌘C)", command=_copy)
        menu.add_command(label="☑️ 全选 (⌘A)", command=_select_all)
        if not readonly:
            menu.add_separator()
            menu.add_command(label="✂️ 剪切 (⌘X)", command=_cut)
            menu.add_command(label="📌 粘贴 (⌘V)", command=_paste)
            menu.add_separator()
            menu.add_command(label="🗑️ 清空", command=_clear)
        def _show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        # macOS 右键是 Button-2,Windows/Linux 是 Button-3
        w.bind("<Button-2>", _show_menu)
        w.bind("<Button-3>", _show_menu)
        # 全选快捷键
        w.bind("<Command-a>", lambda e: (_select_all(), "break"))
        w.bind("<Control-a>", lambda e: (_select_all(), "break"))
        w.bind("<Command-A>", lambda e: (_select_all(), "break"))
        w.bind("<Control-A>", lambda e: (_select_all(), "break"))
        # 复制快捷键(Tk 默认只在 Entry/Spinbox 工作,Text 手动绑定更可靠)
        w.bind("<Command-c>", lambda e: (_copy(), "break"))
        w.bind("<Control-c>", lambda e: (_copy(), "break"))
        w.bind("<Command-C>", lambda e: (_copy(), "break"))
        w.bind("<Control-C>", lambda e: (_copy(), "break"))
        if not readonly:
            w.bind("<Command-v>", lambda e: (_paste(), "break"))
            w.bind("<Control-v>", lambda e: (_paste(), "break"))
            w.bind("<Command-x>", lambda e: (_cut(), "break"))
            w.bind("<Control-x>", lambda e: (_cut(), "break"))
        return w

    def _render_text_to_long_image(text, title="", bg_color="#FFFFFF",
                                    text_color="#212121", title_color="#333333",
                                    width_px=1080, font_size=16, line_height_factor=1.7):
        """把任意长文本渲染成长图 PNG（用 matplotlib，返回文件路径）。
        可设置背景色、标题、字体大小等。"""
        import matplotlib
        matplotlib.use("Agg")
        import os
        import tempfile

        import matplotlib.pyplot as plt
        from matplotlib.font_manager import FontProperties
        # --- 尝试找一个支持中文的字体 ---
        _cjk_fonts = [
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            # Windows fallback
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
        ]
        _font_path = None
        for _f in _cjk_fonts:
            if os.path.exists(_f):
                _font_path = _f
                break
        if _font_path:
            _fp = FontProperties(fname=_font_path, size=font_size)
            _title_fp = FontProperties(fname=_font_path, size=font_size + 4, weight="bold")
            _body_fp = _fp
        else:
            _fp = FontProperties(size=font_size)
            _title_fp = FontProperties(size=font_size + 4, weight="bold")
            _body_fp = _fp
        # --- 把文字按宽度换行（matplotlib 不自动换行） ---
        # 去掉 emoji（Heiti/PingFang 字体不含 emoji 字形）
        import re as _re
        _emoji_pattern = _re.compile(
            "[" "\U0001F000-\U0001FFFF" "\U00002600-\U000027BF"
            "\U0001F300-\U0001F5FF" "\U0001F600-\U0001F64F"
            "\U0001F680-\U0001F6FF" "\U0001F700-\U0001F77F"
            "\U0001F900-\U0001F9FF" "\U000025AA-\U000025FE"
            "\U0001FA00-\U0001FA6F" "\U0001FA70-\U0001FAFF" "]+",
            flags=_re.UNICODE)
        # 估算每个字符占的宽度（中文≈1个fontsize，英文≈0.55）
        char_w = font_size * 0.62
        max_chars_per_line = max(20, int((width_px - 100) / char_w))
        lines_raw = text.split("\n")
        wrapped = []
        for raw in lines_raw:
            # 处理 markdown 粗体 **text** — matplotlib 不支持，去掉 **
            raw_clean = raw.replace("**", "").replace("__", "")
            # 去掉 emoji
            raw_clean = _emoji_pattern.sub("", raw_clean).strip()
            if not raw_clean:
                wrapped.append("")
                continue
            if len(raw_clean) <= max_chars_per_line:
                wrapped.append(raw_clean)
            else:
                # 硬换行
                for j in range(0, len(raw_clean), max_chars_per_line):
                    wrapped.append(raw_clean[j:j + max_chars_per_line])
        # --- 计算图片尺寸（所有像素值 → 最后统一 / dpi 转英寸）---
        margin_top = 60
        margin_bottom = 40
        line_h = font_size * line_height_factor
        title_h = (font_size + 4) * 1.8 if title else 0
        content_h = len(wrapped) * line_h
        total_h_px = int(margin_top + title_h + content_h + margin_bottom + 20)
        # 最小 400px, 最大 6000px 防止 PIL DecompressionBomb
        total_h_px = max(400, min(6000, total_h_px))
        dpi = 100
        w_in = width_px / dpi
        h_in = total_h_px / dpi
        fig = plt.figure(figsize=(w_in, h_in), dpi=dpi)
        fig.patch.set_facecolor(bg_color)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        ax.set_facecolor(bg_color)
        # --- 画标题（坐标用 px，matplotlib 会自动按 dpi 映射）---
        y_cursor = total_h_px - margin_top
        if title:
            ax.text(width_px / 2 / dpi, y_cursor / dpi, title,
                    fontproperties=_title_fp, color=title_color,
                    ha="center", va="top")
            y_cursor -= title_h + 10
            # 分隔线
            ax.plot([60 / dpi, (width_px - 60) / dpi],
                    [(y_cursor - 4) / dpi, (y_cursor - 4) / dpi],
                    color="#CCCCCC", linewidth=1)
            y_cursor -= 20
        # --- 画正文 ---
        x_start = 60
        for line in wrapped:
            ax.text(x_start / dpi, y_cursor / dpi, line,
                    fontproperties=_body_fp, color=text_color,
                    ha="left", va="top")
            y_cursor -= line_h
            if y_cursor < 20:
                break
        # --- 保存 ---
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        fig.savefig(tmp.name, dpi=dpi, bbox_inches="tight", pad_inches=0.1,
                    facecolor=bg_color, edgecolor="none")
        plt.close(fig)
        return tmp.name

    def _pick_custom_bg(current_bg_list, current_text_list, redraw_cb):
        """弹颜色选择器，支持自定义背景色。"""
        from tkinter import colorchooser
        color = colorchooser.askcolor(title="选一个背景色")
        if color and color[1]:
            current_bg_list[0] = color[1]
            # 白色系背景用深字，深色背景用白字
            r, g, b = color[0]
            brightness = (r + g + b) / 3
            current_text_list[0] = "#FFFFFF" if brightness < 128 else "#212121"
            redraw_cb()

    def create_text_tab(self, title, initial_text="", bg_color=None):
        """创建新的文本标签页
        Args:
            title: 标签页标题
            initial_text: 初始文本内容
            bg_color: 背景颜色(可选)
        """
        self.tab_counter += 1
        tab_id = f"tab_{self.tab_counter}"
        # 创建标签页框架
        tab_frame = ttk.Frame(self.text_notebook)
        # 缩短标签页名称(如果太长)
        display_title = title
        if len(title) > 15:
            display_title = title[:12] + "..."
        self.text_notebook.add(tab_frame, text=display_title)
        # 如果没有指定背景色,使用默认白色
        if bg_color is None:
            bg_color = 'white'
        # 根据情绪周期确定背景颜色(如果未指定)
        if bg_color is None or bg_color == 'white':
            if hasattr(self, 'get_emotion_bg_color'):
                bg_color = self.get_emotion_bg_color()
        # 创建文本框和滚动条(固定宽度,不随标签页变化)
        text_widget = tk.Text(tab_frame, height=15, width=45, font=("TkDefaultFont", 16),
                             wrap=tk.WORD, undo=True, maxundo=50, bg=bg_color)
        scrollbar = tk.Scrollbar(tab_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        # 配置颜色标签
        color_tags = [
            ("red", "red"), ("orange", "orange"), ("green", "green"),
            ("blue", "blue"), ("purple", "purple"), ("black", "black")
        ]
        for tag_name, color in color_tags:
            text_widget.tag_configure(tag_name, foreground=color)
        # 绑定事件
        text_widget.bind('<Control-v>', self.on_paste)
        text_widget.bind('<KeyRelease>', self.on_text_change)
        text_widget.bind('<Button-3>', self.show_context_menu)
        # 绑定双击事件,打开全窗口浏览
        text_widget.bind('<Double-Button-1>', lambda e, tid=tab_id: self.open_full_window_viewer(tid))
        # 布局
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 创建顶部工具栏(包含关闭按钮和图片插入按钮)
        toolbar = ttk.Frame(tab_frame)
        toolbar.pack(fill=tk.X, padx=2, pady=2, side=tk.TOP)
        # 如果是咨询标签页,添加图片插入按钮
        if title.startswith("咨询"):
            # 插入图片按钮
            insert_img_btn = ttk.Button(toolbar, text="📷 插入图片",
                                       command=lambda: self.insert_image_to_tab(tab_id))
            insert_img_btn.pack(side=tk.LEFT, padx=2)
            # 粘贴图片按钮
            paste_img_btn = ttk.Button(toolbar, text="📋 粘贴图片",
                                      command=lambda: self.paste_image_to_tab(tab_id))
            paste_img_btn.pack(side=tk.LEFT, padx=2)
        # 关闭按钮(使用×符号,更紧凑)
        close_btn = ttk.Button(toolbar, text="×", width=3,
                              command=lambda: self.close_tab(tab_id))
        close_btn.pack(side=tk.RIGHT, padx=2)
        # 插入初始文本
        if initial_text:
            # 如果文本包含图片标记,使用解析方法
            if "[IMAGE:" in initial_text:
                self.parse_and_display_images(text_widget, initial_text)
            else:
                text_widget.insert("1.0", initial_text)
        # 存储引用
        self.text_widgets[tab_id] = {
            'widget': text_widget,
            'title': title,
            'frame': tab_frame
        }
        # 切换到新标签页
        self.text_notebook.select(tab_frame)
        self.update_text_input_reference()
        return tab_id

    def save_image_file(self, image_path_or_data, is_file_path=True):
        """保存图片文件到日期目录
        Args:
            image_path_or_data: 图片文件路径或图片数据(PIL Image对象)
            is_file_path: True表示是文件路径,False表示是PIL Image对象
        Returns:
            保存的相对路径(相对于D_IMAGES_DIR)
        """
        try:
            image_dir = self.get_image_save_directory()
            today = datetime.now().strftime("%Y-%m-%d")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if is_file_path:
                # 从文件路径复制
                if not os.path.exists(image_path_or_data):
                    return None
                ext = os.path.splitext(image_path_or_data)[1] or '.png'
                filename = f"img_{timestamp}{ext}"
                dest_path = os.path.join(image_dir, filename)
                shutil.copy2(image_path_or_data, dest_path)
            else:
                # 从PIL Image对象保存
                filename = f"img_{timestamp}.png"
                dest_path = os.path.join(image_dir, filename)
                image_path_or_data.save(dest_path, 'PNG')
            # 返回相对路径(相对于D_IMAGES_DIR)
            relative_path = os.path.join(today, filename)
            return relative_path
        except Exception as e:
            messagebox.showerror("错误", f"保存图片失败: {e}")
            return None

    def _fix_encoding(self, text):
        """修复文本乱码"""
        if not text:
            return text
        try:
            # 如果已经是字符串,尝试检测和修复
            if isinstance(text, str):
                # 尝试检测常见的乱码模式
                # 1. 检查是否包含乱码字符(如:锘?、等)
                if '\ufffd' in text or '锘?' in text[:10]:
                    # 尝试用不同编码重新解码
                    for encoding in ['gbk', 'gb2312', 'big5', 'latin1']:
                        try:
                            # 先编码再解码
                            text_bytes = text.encode('latin1', errors='ignore')
                            text = text_bytes.decode(encoding, errors='ignore')
                            break
                        except:
                            continue
                # 2. 修复常见的编码错误
                # 将常见的乱码字符替换
                replacements = {
                    '锘?': '',
                    '\ufffd': '',
                    '': '',
                }
                for old, new in replacements.items():
                    text = text.replace(old, new)
                return text
            else:
                return str(text)
        except Exception as e:
            print(f"修复乱码失败: {e}")
            return text if isinstance(text, str) else str(text)


__all__ = ["WebMixin"]
