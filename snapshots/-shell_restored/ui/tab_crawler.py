"""爬虫/蜘蛛/抓取"""
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
import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class CrawlerMixin:
    """爬虫/蜘蛛/抓取"""

    def show_spider_reader(self):
        """蜘蛛读取:读取文件夹中的文件,提取中文内容"""
        try:
            # 选择文件夹
            folder_path = filedialog.askdirectory(title="选择要读取的文件夹")
            if not folder_path:
                return
            # 创建读取窗口
            read_window = self._safe_toplevel(self.root)
            read_window.title("蜘蛛读取 - 文件内容提取")
            read_window.geometry("1400x800")
            read_window.transient(self.root)
            read_window.lift()
            read_window.focus_force()
            # 创建工具栏
            toolbar_frame = ttk.Frame(read_window, padding=5)
            toolbar_frame.pack(fill=tk.X)
            ttk.Label(toolbar_frame, text=f"文件夹: {folder_path}", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=5)
            # 创建结果显示区域
            result_frame = ttk.Frame(read_window)
            result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, font=("Consolas", 12))
            result_text.pack(fill=tk.BOTH, expand=True)
            # 状态标签
            status_label = ttk.Label(read_window, text="准备读取文件...", font=("TkDefaultFont", 11))
            status_label.pack(pady=5)
            # 保存到资讯按钮
            def save_to_news():
                """保存内容到资讯数据表"""
                try:
                    content = result_text.get("1.0", tk.END).strip()
                    if not content:
                        messagebox.showwarning("警告", "没有可保存的内容", parent=read_window)
                        return
                    tab_name = f"蜘蛛读取_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    if save_news_info_to_db(tab_name, content):
                        # 创建文本标签页
                        if hasattr(self, 'create_text_tab'):
                            self.create_text_tab(tab_name, content)
                        messagebox.showinfo("成功", "已保存到资讯数据表并创建文本标签页", parent=read_window)
                        # 刷新资讯数据表
                        if hasattr(self, 'refresh_news_data'):
                            self.refresh_news_data()
                    else:
                        messagebox.showerror("错误", "保存到资讯数据表失败", parent=read_window)
                except Exception as e:
                    messagebox.showerror("错误", f"保存失败: {e}", parent=read_window)
            # 文本分析按钮
            def analyze_text():
                """对文本进行AI分析"""
                try:
                    content = result_text.get("1.0", tk.END).strip()
                    if not content:
                        messagebox.showwarning("警告", "没有可分析的内容", parent=read_window)
                        return
                    # 打开AI分析窗口(使用一键思考功能)
                    if hasattr(self, 'show_one_click_thinking'):
                        self.show_one_click_thinking()
                        # 将内容复制到剪贴板,方便用户粘贴
                        try:
                            read_window.clipboard_clear()
                            read_window.clipboard_append(content)
                            messagebox.showinfo("提示", "内容已复制到剪贴板,可在AI分析窗口中粘贴使用", parent=read_window)
                        except:
                            pass
                    else:
                        messagebox.showinfo("提示", "请使用主界面的AI分析功能", parent=read_window)
                except Exception as e:
                    messagebox.showerror("错误", f"分析失败: {e}", parent=read_window)
            ttk.Button(toolbar_frame, text="保存到资讯", command=save_to_news, width=12).pack(side=tk.RIGHT, padx=5)
            ttk.Button(toolbar_frame, text="文本分析", command=analyze_text, width=12).pack(side=tk.RIGHT, padx=5)
            # 在后台线程中读取文件
            def read_files():
                try:
                    import glob
                    import re
                    # 支持的文件扩展名
                    supported_extensions = ['*.txt', '*.docx', '*.doc', '*.xlsx', '*.xls', '*.pdf', '*.html', '*.htm']
                    all_files = []
                    for ext in supported_extensions:
                        all_files.extend(glob.glob(os.path.join(folder_path, ext)))
                        all_files.extend(glob.glob(os.path.join(folder_path, '**', ext), recursive=True))
                    if not all_files:
                        def show_no_files():
                            status_label.config(text="未找到支持的文件(支持:txt, docx, xlsx, pdf, html)")
                            result_text.insert("1.0", "未找到支持的文件格式。\n\n支持的文件格式:\n- .txt\n- .docx / .doc\n- .xlsx / .xls\n- .pdf\n- .html / .htm")
                        read_window.after(0, show_no_files)
                        return
                    # 检查是否包含中文的正则表达式(用于过滤)
                    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
                    total_files = len(all_files)
                    read_count = 0
                    error_count = 0
                    all_content = []
                    def update_status(msg):
                        status_label.config(text=msg)
                    def append_content(text):
                        result_text.insert(tk.END, text)
                        result_text.see(tk.END)
                        read_window.update_idletasks()
                    def filter_chinese_content(text):
                        """过滤文本,保留包含中文的行和段落,保留格式和标点符号"""
                        if not text:
                            return ""
                        # 检查是否包含中文
                        if not chinese_pattern.search(text):
                            return ""  # 不包含中文,返回空
                        # 按行处理,保留包含中文的行
                        lines = text.split('\n')
                        filtered_lines = []
                        for line in lines:
                            # 保留包含中文的行,或者保留空行(用于保持段落格式)
                            if chinese_pattern.search(line) or not line.strip():
                                filtered_lines.append(line)
                        # 如果过滤后内容太少,使用原始内容
                        filtered_text = '\n'.join(filtered_lines)
                        if len(filtered_text.strip()) < 50 and len(text.strip()) >= 50:
                            return text  # 使用原始内容
                        return filtered_text if filtered_text.strip() else text
                    for idx, file_path in enumerate(all_files, 1):
                        file_name = os.path.basename(file_path)
                        read_window.after(0, lambda f=file_name, i=idx, t=total_files:
                                         update_status(f"正在读取 ({i}/{t}): {f}"))
                        try:
                            file_ext = os.path.splitext(file_path)[1].lower()
                            content = ""
                            if file_ext == '.txt':
                                content = extract_text_from_txt(file_path)
                            elif file_ext in ['.docx', '.doc']:
                                content = extract_text_from_docx(file_path)
                            elif file_ext in ['.xlsx', '.xls']:
                                content = extract_text_from_excel(file_path)
                            elif file_ext == '.pdf':
                                # PDF读取需要特殊处理
                                try:
                                    import PyPDF2
                                    with open(file_path, 'rb') as f:
                                        pdf_reader = PyPDF2.PdfReader(f)
                                        pdf_text = []
                                        for page in pdf_reader.pages:
                                            pdf_text.append(page.extract_text())
                                        content = '\n'.join(pdf_text)
                                except:
                                    content = f"PDF文件读取失败: {file_name}(可能需要安装PyPDF2库)"
                            elif file_ext in ['.html', '.htm']:
                                # HTML文件读取
                                try:
                                    # 尝试多种编码读取HTML文件
                                    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']
                                    html_content = None
                                    for encoding in encodings:
                                        try:
                                            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                                                html_content = f.read()
                                            break
                                        except UnicodeDecodeError:
                                            continue
                                    if html_content:
                                        # 使用BeautifulSoup解析HTML并提取文本
                                        soup = BeautifulSoup(html_content, 'html.parser')
                                        # 移除script和style标签
                                        for script in soup(["script", "style"]):
                                            script.decompose()
                                        # 提取文本内容,保留段落格式
                                        # 使用get_text的separator参数保留换行
                                        text_content = soup.get_text(separator='\n')
                                        # 清理文本(去除多余空白,但保留段落结构)
                                        lines = []
                                        for line in text_content.splitlines():
                                            stripped = line.strip()
                                            if stripped:  # 保留非空行
                                                lines.append(stripped)
                                            elif lines and lines[-1]:  # 保留段落之间的空行
                                                lines.append('')
                                        content = '\n'.join(lines)
                                    else:
                                        content = f"HTML文件读取失败: {file_name}(无法识别文件编码)"
                                except Exception as e:
                                    content = f"HTML文件读取失败: {file_name}({e!s})"
                            if content and not content.startswith("文件") and not content.startswith("无法"):
                                # 过滤内容,保留包含中文的部分,同时保留格式、标点符号和段落
                                filtered_content = filter_chinese_content(content)
                                # 如果过滤后没有内容,但原始内容包含中文,使用原始内容
                                if not filtered_content.strip() and chinese_pattern.search(content):
                                    filtered_content = content
                                # 如果过滤后内容有效,使用它
                                if filtered_content.strip():
                                    # 显示文件内容
                                    file_header = f"\n{'='*100}\n"
                                    file_header += f"文件: {file_name}\n"
                                    file_header += f"路径: {file_path}\n"
                                    file_header += f"{'='*100}\n\n"
                                    read_window.after(0, lambda h=file_header, c=filtered_content:
                                                     append_content(h + c + "\n\n"))
                                    all_content.append({
                                        'file': file_name,
                                        'path': file_path,
                                        'content': filtered_content
                                    })
                                    read_count += 1
                                else:
                                    error_count += 1
                                    read_window.after(0, lambda f=file_name:
                                                   append_content(f"\n文件不包含中文内容: {f}\n\n"))
                            else:
                                error_count += 1
                                read_window.after(0, lambda f=file_name:
                                               append_content(f"\n文件读取失败或为空: {f}\n\n"))
                        except Exception as e:
                            error_count += 1
                            error_msg = f"读取文件失败 {file_name}: {e!s}\n"
                            read_window.after(0, lambda msg=error_msg: append_content(msg))
                    # 完成
                    def show_complete():
                        status_label.config(text=f"读取完成 - 成功: {read_count}, 失败: {error_count}")
                        summary = f"\n\n{'='*100}\n"
                        summary += "读取完成\n"
                        summary += f"总文件数: {total_files}\n"
                        summary += f"成功读取: {read_count}\n"
                        summary += f"读取失败: {error_count}\n"
                        summary += f"{'='*100}\n"
                        result_text.insert("1.0", summary)
                        result_text.see("1.0")
                    read_window.after(0, show_complete)
                except Exception as e:
                    import traceback
                    error_msg = f"读取文件夹失败: {e!s}\n{traceback.format_exc()}"
                    def show_error():
                        status_label.config(text="读取失败", foreground="red")
                        result_text.insert("1.0", f"错误: {error_msg}\n")
                    read_window.after(0, show_error)
            # 开始读取
            result_text.insert("1.0", f"开始读取文件夹: {folder_path}\n")
            result_text.insert(tk.END, "="*100 + "\n\n")
            threading.Thread(target=read_files, daemon=True).start()
        except Exception as e:
            messagebox.showerror("错误", f"打开蜘蛛读取失败: {e!s}", parent=self.root)
            import traceback
            traceback.print_exc()

    def _batch_crawl_urls(self, selected_urls, save_dir, max_depth=2, delay=1.0, max_pages=50):
        """批量爬取URL(简化版,只爬取第一层)"""
        try:
            import hashlib
            from urllib.parse import urlparse

            import requests
            from bs4 import BeautifulSoup
            visited_urls = set()
            page_count = 0
            def get_domain_name(url):
                """从URL获取域名作为目录名"""
                try:
                    parsed = urlparse(url)
                    domain = parsed.netloc.replace('www.', '').replace('.', '_')
                    return domain
                except:
                    return "unknown"
            def save_page(url, content, base_dir, encoding='utf-8'):
                """保存页面内容"""
                try:
                    domain = get_domain_name(url)
                    domain_dir = os.path.join(base_dir, domain)
                    os.makedirs(domain_dir, exist_ok=True)
                    # 生成文件名(使用URL的hash)
                    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                    parsed = urlparse(url)
                    path = parsed.path.strip('/').replace('/', '_') or 'index'
                    filename = f"{path}_{url_hash}.html"
                    filepath = os.path.join(domain_dir, filename)
                    # 确保HTML中设置了正确的charset
                    try:
                        soup = BeautifulSoup(content, 'html.parser')
                        # 查找现有的charset meta标签
                        charset_set = False
                        for meta in soup.find_all('meta'):
                            if meta.get('charset'):
                                meta['charset'] = 'utf-8'
                                charset_set = True
                                break
                            http_equiv = meta.get('http-equiv', '').lower()
                            if http_equiv == 'content-type':
                                meta['content'] = "text/html; charset=utf-8"
                                charset_set = True
                                break
                        # 如果没有找到charset,在head中添加
                        if not charset_set:
                            head = soup.find('head')
                            if head:
                                charset_meta = soup.new_tag('meta', charset='utf-8')
                                if head.contents:
                                    head.insert(0, charset_meta)
                                else:
                                    head.append(charset_meta)
                        content = str(soup)
                    except:
                        pass
                    # 统一保存为UTF-8编码
                    with open(filepath, 'w', encoding='utf-8', errors='replace') as f:
                        f.write(content)
                    return filepath
                except Exception:
                    return None
            # 确保保存目录存在
            os.makedirs(save_dir, exist_ok=True)
            # 爬取每个选中的URL(只爬取第一层,不深入)
            for key, name, url in selected_urls:
                if page_count >= max_pages:
                    break
                if url in visited_urls:
                    continue
                visited_urls.add(url)
                page_count += 1
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Connection': 'keep-alive',
                    }
                    response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
                    if response.status_code == 200:
                        # 尝试检测编码
                        content_bytes = response.content
                        try:
                            import chardet
                            result = chardet.detect(content_bytes)
                            encoding = result.get('encoding', 'utf-8') if result and result.get('confidence', 0) > 0.7 else 'utf-8'
                        except:
                            encoding = 'utf-8'
                        try:
                            content = content_bytes.decode(encoding, errors='replace')
                        except:
                            content = content_bytes.decode('utf-8', errors='replace')
                        save_page(url, content, save_dir, encoding)
                    time.sleep(delay)
                except Exception:
                    continue
        except Exception:
            import traceback
            traceback.print_exc()

    def _crawl_eastmoney_sync(self):
        """同步爬取东方财富,返回内容和标签页名称"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            tab_title = f"东方财富{current_time}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://www.eastmoney.com/'
            }
            urls = [
                "https://www.eastmoney.com/",
                "https://quote.eastmoney.com/center/gridlist.html#hs_a_board",
                "https://www.eastmoney.com/news/"
            ]
            all_content = []
            for url in urls:
                try:
                    html_content, used_encoding = self._fetch_with_encoding_fix(url, headers, max_retries=2)
                    if html_content:
                        if self._detect_garbled_text(html_content):
                            print(f"警告: {url} 内容可能包含乱码,已尝试修正")
                        soup = BeautifulSoup(html_content, 'html.parser')
                        for script in soup(["script", "style", "noscript"]):
                            script.decompose()
                        # 提取文章链接
                        article_links = []
                        for link in soup.find_all('a', href=True):
                            href = link.get('href', '')
                            title = link.get_text(strip=True)
                            if href and title and len(title) > 5:
                                # 构建完整URL
                                if href.startswith('http'):
                                    full_url = href
                                elif href.startswith('/'):
                                    from urllib.parse import urlparse
                                    parsed = urlparse(url)
                                    full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                                else:
                                    full_url = f"{url.rstrip('/')}/{href.lstrip('/')}"
                                article_links.append((title, full_url))
                        text_content = soup.get_text(separator='\n', strip=True)
                        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                        cleaned_text = '\n'.join(lines)
                        # 添加文章链接信息
                        link_section = ""
                        if article_links:
                            link_section = "\n文章链接:\n"
                            for title, link_url in article_links[:20]:  # 最多显示20个链接
                                link_section += f"  [{title}]({link_url})\n"
                        if cleaned_text and not self._detect_garbled_text(cleaned_text):
                            all_content.append(f"\n{'='*80}\n来源: {url}\n编码: {used_encoding}{link_section}{'='*80}\n{cleaned_text}\n")
                        elif cleaned_text:
                            all_content.append(f"\n{'='*80}\n来源: {url}\n编码: {used_encoding} (可能包含乱码){link_section}{'='*80}\n{cleaned_text}\n")
                        time.sleep(1)
                    else:
                        print(f"跳过 {url}: 无法获取或修正内容")
                except Exception as e:
                    print(f"爬取 {url} 失败: {e}")
                    continue
            if all_content:
                full_content = '\n'.join(all_content)
                if self._detect_garbled_text(full_content):
                    print("警告: 东方财富爬取内容可能包含乱码")
                return full_content, tab_title
        except Exception as e:
            print(f"爬取东方财富失败: {e}")
            return None, None

    def _crawl_xueqiu_sync(self):
        """同步爬取雪球,返回内容和标签页名称"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            tab_title = f"雪球{current_time}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://xueqiu.com/'
            }
            urls = [
                "https://xueqiu.com/",
                "https://xueqiu.com/hq",
                "https://xueqiu.com/stock/rank"
            ]
            all_content = []
            for url in urls:
                try:
                    html_content, used_encoding = self._fetch_with_encoding_fix(url, headers, max_retries=2)
                    if html_content:
                        if self._detect_garbled_text(html_content):
                            print(f"警告: {url} 内容可能包含乱码,已尝试修正")
                        soup = BeautifulSoup(html_content, 'html.parser')
                        for script in soup(["script", "style", "noscript"]):
                            script.decompose()
                        # 提取文章链接
                        article_links = []
                        for link in soup.find_all('a', href=True):
                            href = link.get('href', '')
                            title = link.get_text(strip=True)
                            if href and title and len(title) > 5:
                                # 构建完整URL
                                if href.startswith('http'):
                                    full_url = href
                                elif href.startswith('/'):
                                    from urllib.parse import urlparse
                                    parsed = urlparse(url)
                                    full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                                else:
                                    full_url = f"{url.rstrip('/')}/{href.lstrip('/')}"
                                article_links.append((title, full_url))
                        text_content = soup.get_text(separator='\n', strip=True)
                        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                        cleaned_text = '\n'.join(lines)
                        # 添加文章链接信息
                        link_section = ""
                        if article_links:
                            link_section = "\n文章链接:\n"
                            for title, link_url in article_links[:20]:  # 最多显示20个链接
                                link_section += f"  [{title}]({link_url})\n"
                        if cleaned_text and not self._detect_garbled_text(cleaned_text):
                            all_content.append(f"\n{'='*80}\n来源: {url}\n编码: {used_encoding}{link_section}{'='*80}\n{cleaned_text}\n")
                        elif cleaned_text:
                            all_content.append(f"\n{'='*80}\n来源: {url}\n编码: {used_encoding} (可能包含乱码){link_section}{'='*80}\n{cleaned_text}\n")
                        time.sleep(1)
                    else:
                        print(f"跳过 {url}: 无法获取或修正内容")
                except Exception as e:
                    print(f"爬取 {url} 失败: {e}")
                    continue
            if all_content:
                full_content = '\n'.join(all_content)
                if self._detect_garbled_text(full_content):
                    print("警告: 雪球爬取内容可能包含乱码")
                return full_content, tab_title
        except Exception as e:
            print(f"爬取雪球失败: {e}")
            return None, None

    def _crawl_xuangutong_leaders(self):
        """爬取选股通主题库领涨领跌股并导入到龙头股标签页(group_index=2)
        数据来源:https://xuangutong.com.cn/zhutiku
        """
        try:
            from tkinter import messagebox
            # 显示进度提示
            progress_window = self._safe_toplevel(self.root)
            progress_window.title("爬取选股通主题库")
            progress_window.geometry("400x150")
            progress_window.transient(self.root)
            progress_label = ttk.Label(progress_window, text="正在爬取选股通主题库领涨领跌股...", font=("TkDefaultFont", 11))
            progress_label.pack(pady=30)
            progress_bar = ttk.Progressbar(progress_window, mode='indeterminate', length=300)
            progress_bar.pack(pady=10)
            progress_bar.start()
            progress_window.update()
            def crawl_thread():
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Referer': 'https://xuangutong.com.cn/'
                    }
                    # 爬取主题库页面
                    url = "https://xuangutong.com.cn/zhutiku"
                    try:
                        response = requests.get(url, headers=headers, timeout=30)
                        response.encoding = 'utf-8'
                        html_content = response.text
                    except Exception as e:
                        print(f"请求失败: {e}")
                        html_content = None
                    if not html_content:
                        def show_error():
                            progress_window.destroy()
                            messagebox.showerror("错误", "无法获取选股通主题库页面内容", parent=self.root)
                        self.root.after(0, show_error)
                        return
                    stocks = self._extract_xuangutong_zhutiku_stocks_from_html(html_content)
                    # 通过akshare补充股票名称
                    if stocks:
                        try:
                            import akshare as ak
                            spot_df = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
                            if spot_df is not None and not spot_df.empty:
                                code_to_name = dict(zip(spot_df['代码'].astype(str), spot_df['名称']))
                                for stock in stocks:
                                    if not stock['name'] or stock['name'] == '':
                                        stock['name'] = code_to_name.get(stock['code'], stock['code'])
                        except Exception as e:
                            print(f"获取股票名称失败: {e}")
                    # 更新UI
                    def update_ui():
                        progress_window.destroy()
                        if not stocks:
                            messagebox.showwarning("提示",
                                "未能从选股通主题库提取到股票信息\n"
                                "可能需要登录或页面结构已变化",
                                parent=self.root)
                            return
                        # 导入到龙头股标签页(group_index=2)
                        holding_stocks, holding_labels, holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(2)
                        # 清空现有持仓
                        for i in range(len(holding_stocks)):
                            holding_stocks[i] = None
                            if i < len(holding_kelly_results):
                                holding_kelly_results[i] = None
                        # 导入股票(最多80个)
                        import_count = min(len(stocks), 80)
                        for i in range(import_count):
                            stock = stocks[i]
                            holding_stocks[i] = (stock['name'], stock['code'])
                        # 更新显示(只更新前20个标签)
                        for i in range(min(import_count, len(holding_labels))):
                            self._update_holding_label(i, group_index=2)
                        # 保存到配置文件
                        self._save_holdings_to_config(2)
                        messagebox.showinfo(
                            "完成",
                            f"已从选股通主题库导入 {import_count} 只领涨股到龙头股标签页。\n\n"
                            "说明:主题库页面为前端分页/懒加载,服务器初次只下发少量主题及其领涨股预览,"
                            "单次请求无法拿到全站全部主题。若需要更多标的,请使用「爬取热门股」或「问财+均线龙头」等。",
                            parent=self.root,
                        )
                    self.root.after(0, update_ui)
                except Exception as e:
                    import traceback
                    error_msg = f"爬取失败: {e!s}\n{traceback.format_exc()}"
                    print(error_msg)
                    def show_error(e=e):
                        progress_window.destroy()
                        messagebox.showerror("错误", f"爬取选股通主题库失败:\n{e!s}", parent=self.root)
                    self.root.after(0, show_error)
            # 启动爬取线程
            threading.Thread(target=crawl_thread, daemon=True).start()
        except Exception as e:
            messagebox.showerror("错误", f"启动爬取失败: {e!s}", parent=self.root)

    def crawl_eastmoney_web(self):
        """自动爬取东方财富网页内容到左边新标签"""
        def crawl_thread():
            try:
                # 创建新标签页用于显示内容
                self.root.after(0, lambda: self.create_text_tab("东方财富"))
                # 更新结果文本框显示进度
                result_widget = self.get_active_result_widget()
                if result_widget:
                    self.root.after(0, lambda: result_widget.insert(tk.END, "正在爬取东方财富网页内容...\n"))
                    self.root.after(0, lambda: result_widget.see(tk.END))
                # 设置请求头
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Referer': 'https://www.eastmoney.com/'
                }
                # 爬取多个页面
                urls = [
                    "https://www.eastmoney.com/",
                    "https://quote.eastmoney.com/center/gridlist.html#hs_a_board",
                    "https://www.eastmoney.com/news/"
                ]
                all_content = []
                for url in urls:
                    try:
                        if result_widget:
                            self.root.after(0, lambda u=url: result_widget.insert(tk.END, f"正在访问: {u}\n"))
                            self.root.after(0, lambda: result_widget.see(tk.END))
                        response = requests.get(url, headers=headers, timeout=15)
                        if response.status_code == 200:
                            # 正确处理编码,避免乱码
                            if response.encoding is None or response.encoding == 'ISO-8859-1':
                                # 尝试从响应头或内容中检测编码
                                response.encoding = response.apparent_encoding
                            if not response.encoding or response.encoding.lower() not in ['utf-8', 'utf8']:
                                # 如果检测到的编码不是UTF-8,尝试使用UTF-8
                                try:
                                    response.encoding = 'utf-8'
                                except:
                                    pass
                            # 解析HTML内容
                            soup = BeautifulSoup(response.text, 'html.parser')
                            # 移除脚本和样式标签
                            for script in soup(["script", "style", "noscript"]):
                                script.decompose()
                            # 提取文本内容
                            text_content = soup.get_text(separator='\n', strip=True)
                            # 清理多余空白
                            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                            cleaned_text = '\n'.join(lines)
                            if cleaned_text:
                                all_content.append(f"\n{'='*50}\n来源: {url}\n{'='*50}\n{cleaned_text}\n")
                                if result_widget:
                                    self.root.after(0, lambda: result_widget.insert(tk.END, f"成功获取内容,长度: {len(cleaned_text)} 字符\n"))
                                    self.root.after(0, lambda: result_widget.see(tk.END))
                        else:
                            if result_widget:
                                self.root.after(0, lambda s=response.status_code: result_widget.insert(tk.END, f"HTTP状态码: {s}\n"))
                                self.root.after(0, lambda: result_widget.see(tk.END))
                        time.sleep(1)  # 延迟避免请求过快
                    except Exception as e:
                        if result_widget:
                            self.root.after(0, lambda err=str(e): result_widget.insert(tk.END, f"访问 {url} 失败: {err}\n"))
                            self.root.after(0, lambda: result_widget.see(tk.END))
                        continue
                # 将所有内容添加到文本框
                if all_content:
                    full_content = '\n'.join(all_content)
                    text_widget = self.get_active_text_widget()
                    if text_widget:
                        self.root.after(0, lambda: text_widget.insert("1.0", full_content))
                        self.root.after(0, lambda: text_widget.see("1.0"))
                    if result_widget:
                        self.root.after(0, lambda: result_widget.insert(tk.END, f"\n爬取完成!总共获取 {len(all_content)} 个页面的内容,总长度: {len(full_content)} 字符\n"))
                        self.root.after(0, lambda: result_widget.see(tk.END))
                else:
                    if result_widget:
                        self.root.after(0, lambda: result_widget.insert(tk.END, "\n未能获取到任何内容\n"))
                        self.root.after(0, lambda: result_widget.see(tk.END))
                    self.root.after(0, lambda: messagebox.showwarning("警告", "未能获取到网页内容"))
            except Exception as e:
                error_msg = f"爬取失败: {e!s}"
                if result_widget:
                    self.root.after(0, lambda: result_widget.insert(tk.END, f"\n{error_msg}\n"))
                    self.root.after(0, lambda: result_widget.see(tk.END))
                self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        # 在后台线程中执行
        threading.Thread(target=crawl_thread, daemon=True).start()

    def crawl_xueqiu_web(self):
        """自动爬取雪球网页内容到左边新标签"""
        def crawl_thread():
            try:
                # 创建新标签页用于显示内容
                self.root.after(0, lambda: self.create_text_tab("雪球"))
                # 更新结果文本框显示进度
                result_widget = self.get_active_result_widget()
                if result_widget:
                    self.root.after(0, lambda: result_widget.insert(tk.END, "正在爬取雪球网页内容...\n"))
                    self.root.after(0, lambda: result_widget.see(tk.END))
                # 设置请求头
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Referer': 'https://xueqiu.com/'
                }
                # 爬取多个页面
                urls = [
                    "https://xueqiu.com/",
                    "https://xueqiu.com/hq",
                    "https://xueqiu.com/stock/rank"
                ]
                all_content = []
                for url in urls:
                    try:
                        if result_widget:
                            self.root.after(0, lambda u=url: result_widget.insert(tk.END, f"正在访问: {u}\n"))
                            self.root.after(0, lambda: result_widget.see(tk.END))
                        response = requests.get(url, headers=headers, timeout=15)
                        if response.status_code == 200:
                            # 正确处理编码,避免乱码
                            if response.encoding is None or response.encoding == 'ISO-8859-1':
                                # 尝试从响应头或内容中检测编码
                                response.encoding = response.apparent_encoding
                            if not response.encoding or response.encoding.lower() not in ['utf-8', 'utf8']:
                                # 如果检测到的编码不是UTF-8,尝试使用UTF-8
                                try:
                                    response.encoding = 'utf-8'
                                except:
                                    pass
                            # 解析HTML内容
                            soup = BeautifulSoup(response.text, 'html.parser')
                            # 移除脚本和样式标签
                            for script in soup(["script", "style", "noscript"]):
                                script.decompose()
                            # 提取文本内容
                            text_content = soup.get_text(separator='\n', strip=True)
                            # 清理多余空白
                            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                            cleaned_text = '\n'.join(lines)
                            if cleaned_text:
                                all_content.append(f"\n{'='*50}\n来源: {url}\n{'='*50}\n{cleaned_text}\n")
                                if result_widget:
                                    self.root.after(0, lambda: result_widget.insert(tk.END, f"成功获取内容,长度: {len(cleaned_text)} 字符\n"))
                                    self.root.after(0, lambda: result_widget.see(tk.END))
                        else:
                            if result_widget:
                                self.root.after(0, lambda s=response.status_code: result_widget.insert(tk.END, f"HTTP状态码: {s}\n"))
                                self.root.after(0, lambda: result_widget.see(tk.END))
                        time.sleep(1)  # 延迟避免请求过快
                    except Exception as e:
                        if result_widget:
                            self.root.after(0, lambda err=str(e): result_widget.insert(tk.END, f"访问 {url} 失败: {err}\n"))
                            self.root.after(0, lambda: result_widget.see(tk.END))
                        continue
                # 将所有内容添加到文本框
                if all_content:
                    full_content = '\n'.join(all_content)
                    text_widget = self.get_active_text_widget()
                    if text_widget:
                        self.root.after(0, lambda: text_widget.insert("1.0", full_content))
                        self.root.after(0, lambda: text_widget.see("1.0"))
                    if result_widget:
                        self.root.after(0, lambda: result_widget.insert(tk.END, f"\n爬取完成!总共获取 {len(all_content)} 个页面的内容,总长度: {len(full_content)} 字符\n"))
                        self.root.after(0, lambda: result_widget.see(tk.END))
                else:
                    if result_widget:
                        self.root.after(0, lambda: result_widget.insert(tk.END, "\n未能获取到任何内容\n"))
                        self.root.after(0, lambda: result_widget.see(tk.END))
                    self.root.after(0, lambda: messagebox.showwarning("警告", "未能获取到网页内容"))
            except Exception as e:
                error_msg = f"爬取失败: {e!s}"
                if result_widget:
                    self.root.after(0, lambda: result_widget.insert(tk.END, f"\n{error_msg}\n"))
                    self.root.after(0, lambda: result_widget.see(tk.END))
                self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        # 在后台线程中执行
        threading.Thread(target=crawl_thread, daemon=True).start()


__all__ = ["CrawlerMixin"]
