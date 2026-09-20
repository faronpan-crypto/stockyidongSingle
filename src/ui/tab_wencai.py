"""
问财/同花顺 Mixin — WencaiMixin

迁移自 stockyidong mac003.py: 27 方法 / ~2243 行
涵盖: iwencai 选股、同花顺热榜、pywencai 解析、skillhub、电梯选股
"""
import os, sys, re, json, time, threading, traceback, requests
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext

try:
    import numpy as np
except ImportError: np = None
try:
    import pandas as pd
except ImportError: pd = None

from utils.network import safe_call
from utils.config import *  # 路径/配置/Token
from data.snapshot import *  # get_news_stocks_* 函数
from logic.stock_names import *  # get_stock_name_by_code 等
try:
    import akshare as ak
except ImportError: ak = None
try:
    from pywencai import get as _pywencai_get
except ImportError: _pywencai_get = None

from datetime import datetime, timedelta
import re
import json
import os
import sys
import time
import threading
import traceback
from urllib.parse import urljoin
import sqlite3

class WencaiMixin:
    """问财/同花顺选股相关方法"""


    def crawl_ths_web(self):
        """自动爬取同花顺网页内容,逐个访问指定网页并拼接"""
        def crawl_thread():
            try:
                # 生成带时间的标签页名称
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                tab_title = f"同花顺{current_time}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1"
                }
                # 指定的网页列表
                target_urls = [
                    "https://www.10jqka.com.cn/",
                    "https://data.10jqka.com.cn/market/longhu/"
                ]
                all_content = []
                # 逐个访问指定网页
                for url in target_urls:
                    try:
                        response = requests.get(url, headers=headers, timeout=15)
                        if response.status_code == 200:
                            # 正确处理编码,避免乱码
                            try:
                                # 先尝试从响应头获取编码
                                if response.encoding is None or response.encoding == 'ISO-8859-1':
                                    # 尝试从响应头或内容中检测编码
                                    response.encoding = response.apparent_encoding
                                # 如果检测到的编码不是UTF-8,尝试使用UTF-8
                                if not response.encoding or response.encoding.lower() not in ['utf-8', 'utf8']:
                                    # 尝试使用UTF-8解码
                                    try:
                                        response.content.decode('utf-8')
                                        response.encoding = 'utf-8'
                                    except UnicodeDecodeError:
                                        # 如果UTF-8失败,使用检测到的编码
                                        if not response.encoding:
                                            response.encoding = 'utf-8'
                                # 确保文本内容正确编码
                                html_content = response.text
                                if isinstance(html_content, bytes):
                                    html_content = html_content.decode(response.encoding or 'utf-8', errors='ignore')
                            except Exception:
                                # 如果编码处理失败,使用UTF-8并忽略错误
                                try:
                                    html_content = response.content.decode('utf-8', errors='ignore')
                                except:
                                    html_content = response.text
                            # 解析HTML内容
                            soup = BeautifulSoup(html_content, 'html.parser')
                            # 移除脚本和样式标签
                            for script in soup(["script", "style", "noscript"]):
                                script.decompose()
                            # 提取文本内容
                            text_content = soup.get_text(separator='\n', strip=True)
                            # 清理多余空白,确保编码正确
                            lines = []
                            for line in text_content.split('\n'):
                                line = line.strip()
                                if line:
                                    # 确保每行都是正确的字符串
                                    if isinstance(line, bytes):
                                        try:
                                            line = line.decode('utf-8', errors='ignore')
                                        except:
                                            continue
                                    lines.append(line)
                            cleaned_text = '\n'.join(lines)
                            if cleaned_text:
                                all_content.append(f"\n{'='*80}\n来源: {url}\n{'='*80}\n{cleaned_text}\n")
                        time.sleep(1)  # 延迟避免请求过快
                    except Exception as e:
                        # 如果某个网页访问失败,继续访问下一个
                        all_content.append(f"\n{'='*80}\n来源: {url}\n{'='*80}\n访问失败: {e!s}\n")
                        continue
                # 将所有内容保存到新创建的标签页
                if all_content:
                    full_content = '\n'.join(all_content)
                    # 确保内容编码正确
                    if isinstance(full_content, bytes):
                        try:
                            full_content = full_content.decode('utf-8', errors='ignore')
                        except:
                            try:
                                full_content = full_content.decode('gbk', errors='ignore')
                            except:
                                full_content = full_content.decode('utf-8', errors='replace')
                    # 在主线程中创建标签页并保存内容
                    def create_and_save():
                        # 创建新标签页
                        tab_id = self.create_text_tab(tab_title)
                        text_widget = self.text_widgets[tab_id]['widget']
                        if text_widget:
                            text_widget.delete("1.0", tk.END)
                            text_widget.insert("1.0", full_content)
                            text_widget.see("1.0")
                    self.root.after(0, create_and_save)
                else:
                    if hasattr(self, 'root') and self.root.winfo_exists():
                        self.root.after(0, lambda: messagebox.showwarning("警告", "未能获取到任何内容"))
            except Exception as e:
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after(0, lambda e=e: messagebox.showerror("错误", f"爬取同花顺失败: {e}"))
        threading.Thread(target=crawl_thread, daemon=True).start()


    def _crawl_ths_sync(self):
        """同步爬取同花顺,返回内容和标签页名称"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            tab_title = f"同花顺{current_time}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            target_urls = [
                "https://www.10jqka.com.cn/",
                "https://data.10jqka.com.cn/market/longhu/"
            ]
            all_content = []
            for url in target_urls:
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
                    print("警告: 同花顺爬取内容可能包含乱码")
                return full_content, tab_title
        except Exception as e:
            print(f"爬取同花顺失败: {e}")
        return None, None


    def _crawl_ths_hot_stocks(self):
        """爬取同花顺热榜股票并导入到同花顺标签页(group_index=6)
        数据来源:https://eq.10jqka.com.cn/frontend/thsTopRank/index.html#/
        """
        try:
            import re
            from tkinter import messagebox
            # 显示进度提示
            progress_window = self._toplevel(self.root)
            progress_window.title("爬取同花顺热榜")
            progress_window.geometry("400x150")
            progress_window.transient(self.root)
            progress_label = ttk.Label(progress_window, text="正在爬取同花顺热榜股票...", font=("TkDefaultFont", 11))
            progress_label.pack(pady=30)
            progress_bar = ttk.Progressbar(progress_window, mode='indeterminate', length=300)
            progress_bar.pack(pady=10)
            progress_bar.start()
            progress_window.update()
            def crawl_thread():
                try:
                    stocks = []
                    # 方法1:尝试通过API获取同花顺热榜数据
                    # 同花顺热榜的数据通常通过API接口获取
                    api_urls = [
                        "https://eq.10jqka.com.cn/open/api/hot_list/?page=1&size=100&type=stock",
                        "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock?stock_type=a&type=hour&list_type=normal",
                        "https://eq.10jqka.com.cn/open/api/hot_list/?page=1&size=80&type=stock&market=ab"
                    ]
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'application/json, text/plain, */*',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Referer': 'https://eq.10jqka.com.cn/frontend/thsTopRank/index.html',
                        'Origin': 'https://eq.10jqka.com.cn'
                    }
                    for api_url in api_urls:
                        try:
                            response = requests.get(api_url, headers=headers, timeout=15)
                            if response.status_code == 200:
                                data = response.json()
                                # 解析不同格式的返回数据
                                stock_list = None
                                if isinstance(data, dict):
                                    # 尝试多种可能的数据结构
                                    stock_list = data.get('data', {}).get('stock_list', [])
                                    if not stock_list:
                                        stock_list = data.get('data', {}).get('list', [])
                                    if not stock_list:
                                        stock_list = data.get('result', {}).get('data', [])
                                    if not stock_list:
                                        stock_list = data.get('data', [])
                                elif isinstance(data, list):
                                    stock_list = data
                                if stock_list:
                                    for item in stock_list[:80]:
                                        code = str(item.get('code', item.get('stock_code', '')))
                                        name = item.get('name', item.get('stock_name', ''))
                                        if code and len(code) == 6:
                                            stocks.append({'name': name, 'code': code})
                                    if stocks:
                                        break
                        except Exception as e:
                            print(f"API请求失败 {api_url}: {e}")
                            continue
                    # 方法2:如果API失败,尝试使用akshare获取热门股票
                    if not stocks:
                        try:
                            import akshare as ak
                            # 使用同花顺人气榜
                            hot_df = safe_call(ak.stock_hot_rank_em, fallback=pd.DataFrame(), label="ak.stock_hot_rank_em")
                            if hot_df is not None and not hot_df.empty:
                                for idx, row in hot_df.head(80).iterrows():
                                    code = str(row.get('代码', row.get('股票代码', '')))
                                    name = row.get('股票名称', row.get('名称', ''))
                                    if code and len(code) == 6:
                                        stocks.append({'name': name, 'code': code})
                        except Exception as e:
                            print(f"akshare获取热门股票失败: {e}")
                    # 方法3:尝试爬取HTML页面
                    if not stocks:
                        try:
                            html_url = "https://eq.10jqka.com.cn/frontend/thsTopRank/index.html"
                            response = requests.get(html_url, headers=headers, timeout=15)
                            if response.status_code == 200:
                                soup = BeautifulSoup(response.text, 'html.parser')
                                # 查找股票代码和名称
                                stock_pattern = re.compile(r'(\d{6})')
                                for element in soup.find_all(['a', 'span', 'div', 'td']):
                                    text = element.get_text(strip=True)
                                    href = element.get('href', '')
                                    # 从链接中提取代码
                                    code_match = stock_pattern.search(href) or stock_pattern.search(text)
                                    if code_match:
                                        code = code_match.group(1)
                                        if code.startswith(('0', '3', '6')) and len(stocks) < 80:
                                            if not any(s['code'] == code for s in stocks):
                                                stocks.append({'name': '', 'code': code})
                        except Exception as e:
                            print(f"HTML爬取失败: {e}")
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
                                "未能从同花顺热榜提取到股票信息\n"
                                "可能需要登录或接口已变化",
                                parent=self.root)
                            return
                        # 导入到同花顺标签页(group_index=6)
                        holding_stocks, holding_labels, holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(6)
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
                            self._update_holding_label(i, group_index=6)
                        # 保存到配置文件
                        self._save_holdings_to_config(6)
                        messagebox.showinfo("完成",
                            f"已从同花顺热榜导入 {import_count} 只股票到同花顺标签页",
                            parent=self.root)
                    self.root.after(0, update_ui)
                except Exception as e:
                    import traceback
                    error_msg = f"爬取失败: {e!s}\n{traceback.format_exc()}"
                    print(error_msg)
                    def show_error(e=e):
                        progress_window.destroy()
                        messagebox.showerror("错误", f"爬取同花顺热榜失败:\n{e!s}", parent=self.root)
                    self.root.after(0, show_error)
            # 启动爬取线程
            threading.Thread(target=crawl_thread, daemon=True).start()
        except Exception as e:
            messagebox.showerror("错误", f"启动爬取失败: {e!s}", parent=self.root)


    def _crawl_iwencai_15min_stocks(self):
        """爬取问财15分钟策略股票并导入到15Min标签页(group_index=3)
        问财语句:15分钟20日的均线上移 5日线10日线20日线均线多头发散 热度排名按照从低到高排列 热点前100排名从前到后
        """
        try:
            import re
            from tkinter import messagebox
            from urllib.parse import quote
            # 显示进度提示
            progress_window = self._toplevel(self.root)
            progress_window.title("爬取问财15分钟策略")
            progress_window.geometry("400x150")
            progress_window.transient(self.root)
            progress_label = ttk.Label(progress_window, text="正在爬取问财15分钟策略股票...", font=("TkDefaultFont", 11))
            progress_label.pack(pady=30)
            progress_bar = ttk.Progressbar(progress_window, mode='indeterminate', length=300)
            progress_bar.pack(pady=10)
            progress_bar.start()
            progress_window.update()
            def crawl_thread():
                _ck15 = (os.environ.get("IWENCAI_COOKIE") or os.environ.get("WENCAI_COOKIE") or "").strip()
                if not _ck15:
                    # 问财挂起: 未配置 Cookie 时问财必 403/空表,直接放弃本次爬取,避免 spawn node 重试白等
                    try:
                        progress_window.destroy()
                    except Exception:
                        pass
                    messagebox.showwarning(
                        "问财已挂起",
                        "未设置 IWENCAI_COOKIE,问财爬取链路已挂起(避免无谓等待)。\n\n"
                        "浏览器登录 https://www.iwencai.com 后,复制整段 Cookie 设置环境变量:\n"
                        "  export IWENCAI_COOKIE='整段cookie'\n\n"
                        "设置后重启程序即可恢复「爬取问财15Min」。",
                        parent=self.root,
                    )
                    return
                iwencai_diag = []  # 失败时在弹窗中展示(pywencai 常因未装 Node 而失败)
                _diag_node_missing = False   # Node 缺失时为 True,用于裁剪下方通用排查提示
                _diag_pywencai_missing = False  # pywencai 未安装时为 True
                try:
                    import shutil
                    stocks = []
                    # 问财查询条件:
                    # 15分钟20日的均线上移 5日线10日线20日线均线多头发散 热度排名按照从低到高排列 热点前100排名从前到后
                    query = "15分钟20日的均线上移 5日线10日线20日线均线多头发散 热度排名按照从低到高排列 热点前100排名从前到后"
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'application/json, text/plain, */*',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Referer': 'https://www.iwencai.com/',
                        'Origin': 'https://www.iwencai.com',
                        'hexin-v': '',  # 问财可能需要的token;完整能力依赖 pywencai+Node 或 Cookie
                    }
                    _iwc = (os.environ.get("IWENCAI_COOKIE") or os.environ.get("WENCAI_COOKIE") or "").strip()
                    if _iwc:
                        headers["Cookie"] = _iwc
                    # 方法1:直接访问问财stockpick接口
                    try:
                        # 使用用户提供的URL格式
                        stockpick_url = "https://www.iwencai.com/stockpick/search"
                        params = {
                            'rsh': '3',
                            'typed': '1',
                            'preParams': '',
                            'ts': '1',
                            'f': '1',
                            'qs': 'result_rewrite',
                            'selfsectsn': '',
                            'querytype': 'stock',
                            'searchfilter': '',
                            'tid': 'stockpick',
                            'w': query,
                            'queryarea': ''
                        }
                        response = requests.get(stockpick_url, params=params, headers=headers, timeout=30)
                        if response.status_code == 200:
                            # 尝试从HTML中提取股票数据
                            soup = BeautifulSoup(response.text, 'html.parser')
                            # 查找股票代码模式
                            stock_pattern = re.compile(r'[036]\d{5}')
                            text_content = soup.get_text()
                            # 从页面文本中提取所有股票代码
                            found_codes = stock_pattern.findall(text_content)
                            seen_codes = set()
                            for code in found_codes:
                                if code not in seen_codes and len(stocks) < 100:
                                    stocks.append({'name': '', 'code': code})
                                    seen_codes.add(code)
                    except Exception as e:
                        print(f"问财stockpick请求失败: {e}")
                    # 方法2:尝试使用问财API接口
                    if not stocks:
                        try:
                            api_url = "https://www.iwencai.com/gateway/urp/v7/landing/getDataList"
                            api_params = {
                                'query': query,
                                'urp_sort_way': 'asc',
                                'page': 1,
                                'perpage': 100,
                                'comp_id': 6836372,
                                'uuid': str(int(time.time() * 1000))
                            }
                            response = requests.get(api_url, params=api_params, headers=headers, timeout=30)
                            if response.status_code == 200:
                                data = response.json()
                                # 解析返回数据
                                if 'answer' in data and 'components' in data['answer']:
                                    for comp in data['answer']['components']:
                                        if 'data' in comp and 'datas' in comp['data']:
                                            for item in comp['data']['datas'][:100]:
                                                code = str(item.get('code', item.get('股票代码', '')))
                                                name = item.get('股票简称', item.get('name', ''))
                                                if code and len(code) == 6:
                                                    stocks.append({'name': name, 'code': code})
                        except Exception as e:
                            print(f"问财API请求失败: {e}")
                    # 方法3:pywencai(pip 安装后仍须本机有 Node.js:库内用 node 跑 hexin-v 生成问财校验头)
                    if not stocks:
                        try:
                            if not shutil.which("node"):
                                iwencai_diag.append(
                                    "• 未检测到 Node.js:pywencai 会调用本机 `node` 生成 hexin-v,仅有 pip 包不够。\n"
                                    "  macOS: brew install node;Windows: 自 https://nodejs.org 安装 LTS 后重启本程序。"
                                )
                                print("[问财/pywencai] 未找到 node,跳过 pywencai")
                                _diag_node_missing = True
                            else:
                                import pywencai
                                _ck = (os.environ.get("IWENCAI_COOKIE") or os.environ.get("WENCAI_COOKIE") or "").strip()
                                _kw = {"query": query, "loop": True, "retry": 15, "sleep": 1}
                                if _ck:
                                    _kw["cookie"] = _ck
                                df = pywencai.get(**_kw)
                                if df is not None and not df.empty:
                                    code_col = None
                                    name_col = None
                                    for col in df.columns:
                                        cs = str(col)
                                        if '代码' in cs or 'code' in cs.lower():
                                            code_col = col
                                        if '简称' in cs or '名称' in cs or 'name' in cs.lower():
                                            name_col = col
                                    if not code_col:
                                        for col in df.columns:
                                            try:
                                                s = df[col].dropna().astype(str).head(5)
                                                if s.astype(str).str.replace(r"\D", "", regex=True).str.len().ge(6).any():
                                                    code_col = col
                                                    break
                                            except Exception:
                                                pass
                                    if code_col:
                                        for idx, row in df.head(100).iterrows():
                                            raw = str(row[code_col])
                                            code = re.sub(r"\D", "", raw.replace('.SH', '').replace('.SZ', '').replace('.BJ', ''))
                                            if len(code) >= 6:
                                                code = code[-6:]
                                            if len(code) == 6 and code.isdigit():
                                                name = str(row[name_col]) if name_col and name_col in row.index else ''
                                                stocks.append({'name': name, 'code': code})
                                    else:
                                        iwencai_diag.append("• pywencai 有返回但未能识别股票代码列,请把列名或报错反馈开发者。")
                                else:
                                    iwencai_diag.append(
                                        "• pywencai 返回为空:问财可能要求登录。\n"
                                        "  可在浏览器登录 iwencai 后复制 Cookie,设置环境变量 IWENCAI_COOKIE 再启动程序。"
                                    )
                        except ImportError:
                            exe = getattr(sys, "executable", "") or "python"
                            iwencai_diag.append("• 当前运行本程序的 Python 未安装 pywencai(与终端 pip 成功不一定同一解释器)。")
                            iwencai_diag.append(f"  解释器路径:{exe}")
                            iwencai_diag.append(f'  请对该解释器安装: "{exe}" -m pip install -U pywencai')
                            iwencai_diag.append("  装好后完全退出再启动本程序。")
                            print("pywencai未安装,跳过此方法")
                            _diag_pywencai_missing = True
                        except Exception as e:
                            iwencai_diag.append(f"• pywencai 异常: {e}")
                            print(f"pywencai查询失败: {e}")
                            # pywencai 在问财返回 403/空数据时会抛 'NoneType' object has no attribute 'get',
                            # 该报错无法区分根因。直接探测 iwencai 真实 HTTP 状态,给出精准诊断
                            try:
                                _ok, _probe_msg = self._probe_iwencai_access(query)
                                iwencai_diag.append("• " + _probe_msg)
                            except Exception as _pe:
                                iwencai_diag.append(f"• 问财探测失败:{_pe}")
                    # ===== tushare 本地兜底: pywencai/HTTP 全空时用 tushare/akshare 选股 =====
                    if not stocks:
                        try:
                            print("[问财兜底] pywencai/HTTP 全空, 尝试 tushare 本地筛选...", flush=True)
                            import datetime as _dt

                            import tushare as _ts
                            _pro_local = _ts.pro_api()
                            _td = _dt.datetime.now().strftime("%Y%m%d")
                            _basic = None
                            for _bd in range(8):
                                _td2 = (_dt.datetime.now() - _dt.timedelta(days=_bd)).strftime("%Y%m%d") if _bd > 0 else _td
                                try:
                                    _basic = _pro_local.daily_basic(trade_date=_td2,
                                        fields="ts_code,code,name,pe,pb,total_mv,turnover_rate,volume_ratio")
                                    if _basic is not None and len(_basic) >= 100: break
                                except Exception:
                                    continue
                            if _basic is not None and len(_basic) >= 100:
                                _df = _basic.dropna(subset=["pe", "total_mv", "turnover_rate"])
                                _df = _df[(_df["pe"] > 0) & (_df["pe"] < 100)]
                                _df = _df[(_df["total_mv"] > 500000) & (_df["total_mv"] < 20000000)]
                                _df = _df[_df["turnover_rate"] > 1]
                                _df["_score"] = (
                                    _df["pe"].rank(ascending=True, pct=True) * 0.3 +
                                    _df["turnover_rate"].rank(ascending=False, pct=True) * 0.4 +
                                    _df["total_mv"].rank(ascending=True, pct=True) * 0.3
                                )
                                _df = _df.sort_values("_score", ascending=False).head(60)
                                for _, row in _df.iterrows():
                                    _code6 = str(row.get("code", row.get("ts_code", "")))[:6]
                                    _nm = str(row.get("name", ""))
                                    if _code6.isdigit() and len(_code6) == 6:
                                        stocks.append({"name": _nm, "code": _code6})
                                print(f"[问财兜底] ✅ tushare PE+换手筛选: {len(stocks)} 只", flush=True)
                        except Exception as _te:
                            print(f"[问财兜底] tushare fail: {_te}", flush=True)
                            try:
                                import akshare as _ak_fb
                                _sp = _ak_fb.stock_zh_a_spot_em()
                                if _sp is not None and len(_sp) > 100:
                                    _sp = _sp.sort_values("成交额", ascending=False).head(60)
                                    for _, row in _sp.iterrows():
                                        stocks.append({"name": str(row["名称"]), "code": str(row["代码"])})
                                    print(f"[问财兜底] ✅ akshare 成交额Top: {len(stocks)} 只", flush=True)
                            except Exception as _ae:
                                print(f"[问财兜底] akshare fail: {_ae}", flush=True)
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
                            # 通用排查提示按实际缺失项裁剪:Node/pywencai 已就绪时不再提示重装,
                            # 重点引导设置 IWENCAI_COOKIE(问财 403 / 要求登录时的真正解法)
                            steps = []
                            if _diag_node_missing:
                                steps.append("1. 安装 Node.js(终端执行 node -v 有版本号);macOS: brew install node")
                            if _diag_pywencai_missing:
                                steps.append(f'{len(steps)+1}. 对启动本程序的 Python 安装: "{getattr(sys,"executable","")}" -m pip install -U pywencai')
                            steps.append(f"{len(steps)+1}. 浏览器登录 https://www.iwencai.com 后复制整段 Cookie,设置环境变量 IWENCAI_COOKIE 再启动程序(403/要求登录时最常见解法)")
                            steps.append(f"{len(steps)+1}. 手动打开问财网页查询,或用导入功能粘贴股票代码")
                            msg = (
                                "未能从问财提取到股票信息。\n\n"
                                + "\n".join(steps)
                                + "\n\n(若 Node 与 pywencai 均已就绪却仍失败,多半是问财返回 403 / 要求登录 Cookie--见下方诊断信息。)\n"
                            )
                            if iwencai_diag:
                                msg += "\n────────\n诊断信息:\n" + "\n".join(iwencai_diag)
                            messagebox.showwarning("问财获取失败", msg, parent=self.root)
                            # 打开问财网页供用户手动查询
                            import webbrowser
                            webbrowser.open("https://www.iwencai.com/stockpick/search?w=" + quote(query))
                            return
                        # 导入到15Min标签页(group_index=3)
                        holding_stocks, holding_labels, holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(3)
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
                            self._update_holding_label(i, group_index=3)
                        # 保存到配置文件
                        self._save_holdings_to_config(3)
                        messagebox.showinfo("完成",
                            f"已从问财15分钟策略导入 {import_count} 只股票到15Min标签页\n"
                            f"查询条件:15分钟20日的均线上移 5日线10日线20日线均线多头发散 热度排名按照从低到高排列 热点前100排名从前到后",
                            parent=self.root)
                    self.root.after(0, update_ui)
                except Exception as e:
                    import traceback
                    error_msg = f"爬取失败: {e!s}\n{traceback.format_exc()}"
                    print(error_msg)
                    def show_error(e=e):
                        progress_window.destroy()
                        messagebox.showerror("错误", f"爬取问财15分钟策略失败:\n{e!s}", parent=self.root)
                    self.root.after(0, show_error)
            # 启动爬取线程
            threading.Thread(target=crawl_thread, daemon=True).start()
        except Exception as e:
            messagebox.showerror("错误", f"启动爬取失败: {e!s}", parent=self.root)


    def _probe_iwencai_access(self, query="今日涨停的股票"):
        """直接探测 iwencai get-robot-data 接口,返回 (是否可访问, 诊断文案)。
        pywencai 在问财返回 403 / 空数据时会抛 'NoneType' object has no attribute 'get',
        该异常无法区分「未装 Node」「未装 pywencai」「IP 被限」「要求登录 Cookie」。
        此处复用 pywencai 的 headers(含 hexin-v)发一次最小请求,用真实 HTTP 状态给出精准诊断。
        """
        try:
            import json as _json

            import requests as _rq
            from pywencai.headers import headers as _wc_headers
            _data = {
                'add_info': '{"urp":{"scene":1,"company":1,"business":1},"contentType":"json","searchInfo":true}',
                'perpage': '10', 'page': 1, 'source': 'Ths_iwencai_Xuangu',
                'log_info': '{"input_type":"click"}', 'version': '2.0',
                'secondary_intent': 'stock', 'question': query,
            }
            _ck = (os.environ.get("IWENCAI_COOKIE") or os.environ.get("WENCAI_COOKIE") or "").strip()
            _h = _wc_headers(None, None)
            if _ck:
                _h['cookie'] = _ck
            res = _rq.request(method='POST',
                url='http://www.iwencai.com/customized/chart/get-robot-data',
                json=_data, headers=_h, timeout=(5, 10))
            code = res.status_code
            try:
                j = _json.loads(res.text)
            except Exception:
                j = None
            if code == 200 and isinstance(j, dict) and j.get('data'):
                return (True, "问财接口可访问(HTTP 200 且有 data)。pywencai 失败可能是查询条件或分页问题,可重试。")
            if code == 403:
                return (False,
                    ("问财返回 HTTP 403 Access Denied:本机 Node 与 pywencai 均正常,但服务器拒绝访问。\n"
                    "  多为 IP 被限或要求登录。请在浏览器登录 https://www.iwencai.com 后,\n"
                    "  复制整段 Cookie 设置环境变量 IWENCAI_COOKIE 再启动本程序:\n"
                    "  macOS:  export IWENCAI_COOKIE='整段cookie'\n"
                    "  Windows: set IWENCAI_COOKIE=整段cookie"))
            if code in (412, 429):
                return (False, f"问财返回 HTTP {code}(限流/校验)。请稍后重试,或设置 IWENCAI_COOKIE 后重启。")
            return (False, f"问财返回 HTTP {code}:{res.text[:120]}")
        except Exception as e:
            return (False, f"问财探测请求异常:{e}")


    def _pywencai_df_to_stock_dicts(self, df):
        """将 pywencai 返回的 DataFrame 转为 [{'name','code'}, ...]。"""
        import re
        out = []
        if df is None or getattr(df, "empty", True):
            return out
        code_col = None
        name_col = None
        for col in df.columns:
            cs = str(col)
            if "代码" in cs or "code" in cs.lower() or cs.strip().lower() == "code":
                code_col = col
            if "简称" in cs or "名称" in cs or "name" in cs.lower():
                name_col = col
        if not code_col:
            for col in df.columns:
                try:
                    s = df[col].dropna().astype(str).head(5)
                    if s.astype(str).str.replace(r"\D", "", regex=True).str.len().ge(6).any():
                        code_col = col
                        break
                except Exception:
                    pass
        if not code_col:
            return out
        for _, row in df.head(120).iterrows():
            raw = str(row[code_col])
            code = re.sub(r"\D", "", raw.replace(".SH", "").replace(".SZ", "").replace(".BJ", ""))
            if len(code) >= 6:
                code = code[-6:]
            if len(code) != 6 or not code.isdigit():
                continue
            name = ""
            if name_col and name_col in row.index:
                name = str(row[name_col]).strip()
            out.append({"name": name, "code": code})
        return out


    def _fetch_wencai_leader_candidates(self):
        """
        分多条问财语句拉取候选股(并集去重),去掉 ST;返回 (codes_ordered, diag_lines)。
        codes_ordered: 按「查询顺序 + 每条内顺序」去重后的代码列表。
        """
        import shutil
        import sys as _sys
        diag = []
        codes_order = []
        seen = set()
        # 问财拉候选(含基本面排序等);本地再用日线严格校验(均线多头+量)
        # 由严到宽多条,避免单条因问财语义/风控返回空表
        queries = [
            "A股,非ST,5日10日20日均线多头发展,价升量涨股票,不是涨停,基本面打分从高到低",
            "A股非ST,5日均线大于10日均线大于20日均线,成交量大于5日均量",
            "A股非ST,均线多头排列,涨幅0到8%",
        ]
        if not shutil.which("node"):
            diag.append("• 未检测到 Node.js:pywencai 依赖本机 node 生成 hexin-v,请先安装 Node(https://nodejs.org/)并重启程序。")
            diag.append("  当前 PATH 下未找到 node,可在终端执行 node -v 确认。")
            return [], diag
        try:
            import pywencai
        except ImportError:
            exe = getattr(_sys, "executable", "") or "python"
            diag.append("• 当前运行本程序的 Python 未安装 pywencai(与终端 pip 成功不一定同一解释器)。")
            diag.append(f"  解释器路径:{exe}")
            diag.append(f'  请对该解释器安装: "{exe}" -m pip install -U pywencai')
            diag.append("  装好后完全退出再启动本程序。")
            return [], diag
        _ck = (os.environ.get("IWENCAI_COOKIE") or os.environ.get("WENCAI_COOKIE") or "").strip()
        if not _ck:
            # 问财挂起: 未配置 Cookie 时 pywencai 必然 403/空表,不再走 retry 白等
            diag.append("• 未设置 IWENCAI_COOKIE,问财链路已挂起(本次直接跳过问财拉候选)。")
            diag.append("  浏览器登录 https://www.iwencai.com 后复制整段 Cookie,设置环境变量 IWENCAI_COOKIE 并重启程序即可恢复。")
            return [], diag
        for qi, query in enumerate(queries):
            try:
                _kw = {"query": query, "loop": True, "retry": 15, "sleep": 1}
                if _ck:
                    _kw["cookie"] = _ck
                df = pywencai.get(**_kw)
                if df is None or getattr(df, "empty", True):
                    diag.append(f"• 第 {qi + 1} 条问财返回空表(约 0 行):「{query[:48]}...」")
                    continue
                stocks = self._pywencai_df_to_stock_dicts(df)
                if not stocks:
                    cols = list(df.columns)[:14]
                    diag.append(
                        f"• 第 {qi + 1} 条返回 {len(df)} 行但未解析出股票代码,列名示例:{cols}"
                    )
                    continue
                n_new = 0
                for s in stocks:
                    code = s.get("code") or ""
                    name = s.get("name") or ""
                    if len(code) != 6:
                        continue
                    if self._is_st_or_delisted_name(name):
                        continue
                    if code in seen:
                        continue
                    seen.add(code)
                    codes_order.append(code)
                    n_new += 1
                if n_new:
                    diag.append(f"• 第 {qi + 1} 条问财命中 {n_new} 只(去重后累计 {len(codes_order)})。")
            except Exception as e:
                diag.append(f"• 第 {qi + 1} 条问财查询异常: {query[:32]}... → {e}")
        if not codes_order and not diag:
            diag.append("• 问财均未解析到股票,请检查网络、Node、pywencai 与 IWENCAI_COOKIE。")
        return codes_order, diag


    def _build_ths_hot_rank_order_map(self):
        """同花顺热榜名次(越小越靠前),用于近似「情绪关注度」排序。返回 code -> rank(1起)。"""
        rank_map = {}
        if not AKSHARE_AVAILABLE:
            return rank_map
        try:
            hot_df = safe_call(ak.stock_hot_rank_em, fallback=pd.DataFrame(), label="ak.stock_hot_rank_em")
            if hot_df is None or hot_df.empty:
                return rank_map
            code_col = None
            for col in hot_df.columns:
                cs = str(col)
                if "代码" in cs or "code" in cs.lower():
                    code_col = col
                    break
            if not code_col:
                return rank_map
            for i, row in hot_df.iterrows():
                raw = str(row.get(code_col, ""))
                code = "".join(c for c in raw if c.isdigit())
                if len(code) >= 6:
                    code = code[-6:]
                if len(code) == 6 and code not in rank_map:
                    rank_map[code] = len(rank_map) + 1
        except Exception as e:
            print(f"[龙头股] 同花顺热榜排序用数据获取失败: {e}")
        return rank_map


    def _import_leader_stocks_from_wencai_ma(self):
        """龙头股:问财拉取候选,本地校验 5/10/20 多头+量;按同花顺热榜人气近似情绪排序;导入 group_index=2(最多 80)。"""
        try:
            from tkinter import messagebox
            progress_window = self._toplevel(self.root)
            progress_window.title("问财+均线筛选龙头股")
            progress_window.geometry("460x170")
            progress_window.transient(self.root)
            pl = ttk.Label(
                progress_window,
                text="正在分次请求问财并校验均线与量能(需 Node + pywencai,可能较慢)...",
                font=("TkDefaultFont", 11),
            )
            pl.pack(pady=22)
            pb = ttk.Progressbar(progress_window, mode="indeterminate", length=340)
            pb.pack(pady=8)
            pb.start()
            progress_window.update()
            def work():
                try:
                    codes, diag = self._fetch_wencai_leader_candidates()
                    if not codes:
                        def _empty():
                            progress_window.destroy()
                            msg = (
                                "未能从问财得到候选股票。\n\n"
                                "请确认:已安装 Node(终端 node -v)、已 pip install pywencai;\n"
                                "若仍失败,浏览器登录同花顺问财后设置环境变量 IWENCAI_COOKIE 再启动。\n"
                            )
                            if diag:
                                msg += "\n────────\n" + "\n".join(diag)
                            messagebox.showwarning("问财+均线龙头", msg, parent=self.root)
                        self.root.after(0, _empty)
                        return
                    passed = []  # (name, code)
                    n_total = len(codes)
                    for i, code in enumerate(codes):
                        try:
                            progress_window.title(f"问财+均线量校验 {i+1}/{n_total} {code}")
                        except Exception:
                            pass
                        ok, name = self._leader_stock_ma_vol_pass(code)
                        if ok:
                            passed.append((name, code))
                    rank_map = self._build_ths_hot_rank_order_map()
                    BIG = 10**9
                    passed.sort(key=lambda x: rank_map.get(x[1], BIG))
                    total_ok = len(passed)
                    results = passed[:80]
                    def _done():
                        progress_window.destroy()
                        if not passed:
                            msg = (
                                "问财已返回候选,但本地校验后暂无满足条件的标的:\n"
                                "5/10/20 日均线多头且三线较昨日走高,且 5 日均量>10 日均量(已排除 ST)。\n"
                                "可检查 AKShare 行情是否可用,或问财与本地公式差异较大。\n"
                            )
                            if diag:
                                msg += "\n────────\n" + "\n".join(diag[:8])
                            messagebox.showwarning("提示", msg, parent=self.root)
                            return
                        holding_stocks, holding_labels, holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(2)
                        for j in range(len(holding_stocks)):
                            holding_stocks[j] = None
                            if j < len(holding_kelly_results):
                                holding_kelly_results[j] = None
                        for j, (name, code) in enumerate(results):
                            holding_stocks[j] = (name, code)
                        for j in range(min(len(results), len(holding_labels))):
                            self._update_holding_label(j, group_index=2, fetch_daily_change=False)
                        self._save_holdings_to_config(2)
                        imported = len(results)
                        messagebox.showinfo(
                            "完成",
                            f"符合条件共 {total_ok} 只;已按同花顺热榜人气排序(个股无情绪指数时近似关注度)。\n"
                            f"已导入 {imported} 只(界面最多 80 只)。",
                            parent=self.root,
                        )
                    self.root.after(0, _done)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    def _err(e=e):
                        progress_window.destroy()
                        messagebox.showerror("错误", str(e), parent=self.root)
                    self.root.after(0, _err)
            threading.Thread(target=work, daemon=True).start()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("错误", str(e), parent=self.root)


    def _load_elevator_wencai_conditions(self):
        """与坐电梯 ElevatorDialog「常用条件」同源:iwencai_condition_options.json 或默认列表。"""
        import json
        default = [
            "近三年净利润同比连续增长",
            "ROE大于15%且净利润率大于10%",
            "主力资金近5日净流入为正",
            "北向资金连续三日增持",
            "股价位于年线之上且成交量放大",
            "最新收盘价大于20日均线",
            "机构评级为买入或增持",
            "PEG小于1且市值小于500亿",
            "半年报预增幅度超过50%",
            "行业为人工智能或算力相关",
        ]
        cfg = os.path.normpath(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..",
                "..",
                "consulting_analysis_gui_project",
                "src",
                "config",
                "iwencai_condition_options.json",
            )
        )
        if os.path.isfile(cfg):
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list) and data:
                    out = [str(x).strip() for x in data if str(x).strip()]
                    if out:
                        return out
            except Exception:
                pass
        return default


    def _start_wencai_indicator_query_for_leader_tab(self, query: str):
        """龙头股页:按选定问财指标执行问财选股,结束后弹窗展示结果。"""
        from tkinter import messagebox
        query = (query or "").strip()
        if not query:
            return
        pw = self._toplevel(self.root)
        pw.title("问财查询")
        pw.geometry("440x130")
        pw.transient(self.root)
        pl = ttk.Label(
            pw,
            text=f"正在查询:{query[:56]}{'...' if len(query) > 56 else ''}",
            font=("TkDefaultFont", 11),
            wraplength=400,
        )
        pl.pack(pady=16)
        pb = ttk.Progressbar(pw, mode="indeterminate", length=320)
        pb.pack(pady=6)
        pb.start()
        pw.update()
        def _finish_ok(win, stocks, q):
            try:
                win.destroy()
            except Exception:
                pass
            self._show_wencai_indicator_result_dialog(q, stocks)
        def _finish_err(win, err):
            try:
                win.destroy()
            except Exception:
                pass
            messagebox.showerror("问财指标", str(err), parent=self.root)
        def work():
            try:
                stocks = self._query_iwencai_stocks(query)
                self.root.after(0, lambda: _finish_ok(pw, stocks, query))
            except Exception as e:
                self.root.after(0, lambda err=e: _finish_err(pw, err))
        try:
            threading.Thread(target=work, daemon=True).start()
        except Exception as e:
            _finish_err(pw, e)


    def _show_wencai_indicator_result_dialog(self, query: str, stocks):
        """弹窗展示该问财指标返回的股票列表(列与条件选股一致)。"""
        from tkinter import messagebox
        from urllib.parse import quote
        win = self._toplevel(self.root)
        win.title(f"问财指标 · 结果({len(stocks or [])} 只)")
        win.geometry("1000x640")
        win.transient(self.root)
        top = ttk.Frame(win, padding=6)
        top.pack(fill=tk.X)
        ttk.Label(top, text="指标:", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
        ttk.Label(top, text=query, font=("Microsoft YaHei", 10), wraplength=720).pack(side=tk.LEFT, fill=tk.X, expand=True)
        btnf = ttk.Frame(win, padding=(6, 0, 6, 6))
        btnf.pack(fill=tk.X)
        def _open_iwc():
            webbrowser.open("https://www.iwencai.com/stockpick/search?w=" + quote(query))
        ttk.Button(btnf, text="浏览器打开问财", command=_open_iwc).pack(side=tk.LEFT, padx=(0, 6))
        paned = ttk.PanedWindow(win, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        table_frame = ttk.Frame(paned)
        paned.add(table_frame, weight=3)
        columns = ("代码", "名称", "价格", "涨跌幅", "成交量", "成交额", "市值", "PE", "WR2", "D", "BIAS3", "DIFF")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=16)
        try:
            tree.tag_configure("idx_hs300", foreground="#c0392b")
            tree.tag_configure("idx_zz500", foreground="#8B4513")
            tree.tag_configure("idx_kc50", foreground="#1e8449")
        except Exception:
            pass
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=76, anchor=tk.CENTER)
        tree.column("名称", width=100)
        tree.column("成交额", width=90)
        tree.column("市值", width=90)
        scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll_y.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        txt_frame = ttk.LabelFrame(paned, text="摘要")
        paned.add(txt_frame, weight=2)
        detail = scrolledtext.ScrolledText(txt_frame, wrap=tk.WORD, height=12, font=("Microsoft YaHei", 10))
        detail.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        stocks = self._dedupe_elevator_stocks_by_code(stocks or [])
        hs300, zz500, kc50 = self._get_cached_index_constituent_code_sets()
        if not stocks:
            detail.insert(
                "1.0",
                "未返回股票。请确认本机已安装 Node 与 pywencai,或设置 IWENCAI_COOKIE 后重试。\n"
                "也可点击「浏览器打开问财」在网页中核对。",
            )
        else:
            for stock in stocks:
                values = (
                    stock.get("code", ""),
                    stock.get("name", ""),
                    f"{stock.get('price', 0):.2f}",
                    f"{stock.get('change_pct', 0):+.2f}%",
                    f"{stock.get('volume', 0):,.0f}",
                    f"{stock.get('turnover', 0):,.0f}",
                    f"{stock.get('market_cap', 0):,.0f}",
                    f"{stock.get('pe_ratio', 0):.2f}",
                    f"{stock.get('wr2', 0):.2f}",
                    f"{stock.get('d', 0):.2f}",
                    f"{stock.get('bias3', 0):.2f}",
                    f"{stock.get('diff', 0):.3f}",
                )
                tag = self._index_tag_for_stock_code(stock.get("code", ""), hs300, zz500, kc50)
                if tag:
                    tree.insert("", tk.END, values=values, tags=(tag,))
                else:
                    tree.insert("", tk.END, values=values)
            lines = [
                f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"条件: {query}",
                f"数量: {len(stocks)}",
                "",
            ]
            for i, stock in enumerate(stocks, 1):
                lines.append(
                    f"{i}. {stock.get('name', '')}({stock.get('code', '')})  "
                    f"价 {stock.get('price', 0):.2f}  涨跌 {stock.get('change_pct', 0):+.2f}%"
                )
            detail.insert("1.0", "\n".join(lines))
        def on_dbl_click(_event):
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            if not vals or len(vals) < 2:
                return
            code = str(vals[0]).strip()
            name = str(vals[1]).strip()
            if len(code) == 6 and code.isdigit():
                try:
                    self._show_stock_detail_direct(name if name else code, code, 1)
                except Exception as ex:
                    messagebox.showerror("错误", str(ex), parent=win)
        tree.bind("<Double-1>", on_dbl_click)
        bottom = ttk.Frame(win, padding=6)
        bottom.pack(fill=tk.X)
        ttk.Button(bottom, text="关闭", command=win.destroy).pack(side=tk.RIGHT)


    def _fetch_ths_hot_stocks(self):
        """仅爬取同花顺热榜股票,返回 [{'name','code'}, ...],不导入界面。供爬取热门股组合使用。"""
        import re
        stocks = []
        api_urls = [
            "https://eq.10jqka.com.cn/open/api/hot_list/?page=1&size=100&type=stock",
            "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock?stock_type=a&type=hour&list_type=normal",
            "https://eq.10jqka.com.cn/open/api/hot_list/?page=1&size=80&type=stock&market=ab"
        ]
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://eq.10jqka.com.cn/frontend/thsTopRank/index.html',
            'Origin': 'https://eq.10jqka.com.cn'
        }
        for api_url in api_urls:
            try:
                response = requests.get(api_url, headers=headers, timeout=15)
                if response.status_code != 200:
                    continue
                data = response.json()
                stock_list = None
                if isinstance(data, dict):
                    stock_list = data.get('data', {}).get('stock_list', []) or data.get('data', {}).get('list', []) or data.get('result', {}).get('data', []) or data.get('data', [])
                elif isinstance(data, list):
                    stock_list = data
                if stock_list:
                    for item in stock_list[:80]:
                        code = str(item.get('code', item.get('stock_code', '')))
                        name = item.get('name', item.get('stock_name', ''))
                        if code and len(code) == 6:
                            stocks.append({'name': name, 'code': code})
                    if stocks:
                        break
            except Exception as e:
                print(f"同花顺API失败 {api_url}: {e}")
        if not stocks:
            try:
                import akshare as ak
                hot_df = safe_call(ak.stock_hot_rank_em, fallback=pd.DataFrame(), label="ak.stock_hot_rank_em")
                if hot_df is not None and not hot_df.empty:
                    for idx, row in hot_df.head(80).iterrows():
                        code = str(row.get('代码', row.get('股票代码', '')))
                        name = row.get('股票名称', row.get('名称', ''))
                        if code and len(code) == 6:
                            stocks.append({'name': name, 'code': code})
            except Exception as e:
                print(f"akshare同花顺人气榜失败: {e}")
        if not stocks:
            try:
                html_url = "https://eq.10jqka.com.cn/frontend/thsTopRank/index.html"
                resp = requests.get(html_url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    stock_pattern = re.compile(r'(\d{6})')
                    for el in soup.find_all(['a', 'span', 'div', 'td']):
                        text = el.get_text(strip=True)
                        href = el.get('href', '')
                        code_match = stock_pattern.search(href) or stock_pattern.search(text)
                        if code_match:
                            code = code_match.group(1)
                            if code.startswith(('0', '3', '6')) and len(stocks) < 80 and not any(s['code'] == code for s in stocks):
                                stocks.append({'name': '', 'code': code})
            except Exception as e:
                print(f"同花顺HTML爬取失败: {e}")
        if stocks:
            try:
                import akshare as ak
                spot_df = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
                if spot_df is not None and not spot_df.empty:
                    code_to_name = dict(zip(spot_df['代码'].astype(str), spot_df['名称']))
                    for s in stocks:
                        if not s.get('name'):
                            s['name'] = code_to_name.get(s['code'], s['code'])
            except Exception as e:
                print(f"同花顺补充名称失败: {e}")
        return stocks


    def _fetch_ths_full_no_dedup(self):
        """爬取同花顺热榜全部股票(热门股非去重专用:不拉取/不拼接概念;逻辑栏仅可有同条 JSON 内的连板信息等,无则空)。"""
        stocks = []
        api_urls = [
            "https://eq.10jqka.com.cn/open/api/hot_list/?page=1&size=100&type=stock",
            "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock?stock_type=a&type=hour&list_type=normal",
            "https://eq.10jqka.com.cn/open/api/hot_list/?page=1&size=80&type=stock&market=ab"
        ]
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://eq.10jqka.com.cn/frontend/thsTopRank/index.html',
            'Origin': 'https://eq.10jqka.com.cn'
        }
        for api_url in api_urls:
            try:
                response = requests.get(api_url, headers=headers, timeout=15)
                if response.status_code != 200:
                    continue
                data = response.json()
                stock_list = None
                if isinstance(data, dict):
                    stock_list = data.get('data', {}).get('stock_list', []) or data.get('data', {}).get('list', []) or data.get('result', {}).get('data', []) or data.get('data', [])
                elif isinstance(data, list):
                    stock_list = data
                if stock_list:
                    # 调试:打印第一条数据的所有字段
                    if len(stock_list) > 0:
                        print(f"[同花顺API] 第一条数据字段: {list(stock_list[0].keys())}")
                        print(f"[同花顺API] 第一条数据内容: {stock_list[0]}")
                    for item in stock_list:
                        code = str(item.get('code', item.get('stock_code', '')))
                        name = item.get('name', item.get('stock_name', ''))
                        if code and len(code) == 6:
                            logic_parts = []
                            if item.get('continuous_board') or item.get('board_days'):
                                board = item.get('continuous_board') or item.get('board_days')
                                logic_parts.append(f"{board}连板" if isinstance(board, int) else str(board))
                            logic = ' '.join(logic_parts) if logic_parts else ''
                            stocks.append({'name': name, 'code': code, '逻辑': logic, '来源': '同花顺'})
                    if stocks:
                        print(f"[同花顺API] 从 {api_url} 获取到 {len(stocks)} 只股票")
                        break
            except Exception as e:
                print(f"同花顺API失败 {api_url}: {e}")
        # akshare 备选(不拼接概念列)
        if not stocks:
            try:
                import akshare as ak
                hot_df = safe_call(ak.stock_hot_rank_em, fallback=pd.DataFrame(), label="ak.stock_hot_rank_em")
                if hot_df is not None and not hot_df.empty:
                    print(f"[akshare同花顺] 列名: {list(hot_df.columns)}")
                    for idx, row in hot_df.iterrows():
                        code = str(row.get('代码', row.get('股票代码', '')))
                        name = row.get('股票名称', row.get('名称', ''))
                        if code and len(code) == 6:
                            stocks.append({'name': name, 'code': code, '逻辑': '', '来源': '同花顺'})
            except Exception as e:
                print(f"akshare同花顺人气榜失败: {e}")
        # 补充名称(不请求个股概念)
        if stocks:
            try:
                import akshare as ak
                spot_df = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
                if spot_df is not None and not spot_df.empty:
                    code_to_name = dict(zip(spot_df['代码'].astype(str), spot_df['名称']))
                    for s in stocks:
                        if not s.get('name'):
                            s['name'] = code_to_name.get(s['code'], s['code'])
            except Exception as e:
                print(f"同花顺补充名称失败: {e}")
        return stocks


    def _show_ths_save_result_dialog(self, title, message, saved_count):
        """显示保存结果对话框,包含打开数据表按钮"""
        def show_dialog():
            # 创建自定义对话框
            dialog = self._toplevel(self.root)
            dialog.title(title)
            dialog.geometry("500x200")
            dialog.transient(self.root)
            dialog.grab_set()
            # 居中显示
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
            y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
            dialog.geometry(f"+{x}+{y}")
            # 消息文本
            msg_label = ttk.Label(dialog, text=message, wraplength=450, justify=tk.LEFT)
            msg_label.pack(pady=20, padx=20)
            # 按钮框架
            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=10)
            def open_data_table():
                """打开数据表窗口"""
                dialog.destroy()
                # 打开数据表窗口,默认显示股票实时数据标签页
                self.show_unified_db_display(default_tab="ths")
            # 打开数据表按钮
            ttk.Button(button_frame, text="打开数据表", command=open_data_table, width=15).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="确定", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=5)
        self.root.after(0, show_dialog)


    def _parse_ths_data(self, text):
        """解析同花顺数据表格"""
        try:
            parsed_data = []
            lines = text.split('\n')
            # 当前日期和时间
            save_date = datetime.now().strftime('%Y-%m-%d')
            save_time = datetime.now().strftime('%H:%M:%S')
            # 尝试识别表格格式
            # 格式1:标准表格(代码、名称、现价、涨幅等)
            # 格式2:简化格式
            # 查找包含股票代码的行(6位数字)
            stock_code_pattern = r'(\d{6})'
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                # 查找包含股票代码的行
                codes = re.findall(stock_code_pattern, line)
                if codes:
                    # 尝试解析这一行及其后续行的数据
                    stock_code = codes[0]
                    # 尝试获取股票名称
                    stock_name = None
                    # 尝试从股票代码获取名称
                    try:
                        # 从代码获取名称(需要反向查找)
                        global STOCK_CODES_DICT
                        if STOCK_CODES_DICT is None:
                            load_stock_names()
                        if STOCK_CODES_DICT:
                            stock_name = STOCK_CODES_DICT.get(stock_code)
                    except:
                        pass
                    # 如果无法从代码获取,尝试从文本中提取
                    if not stock_name:
                        # 查找中文股票名称(通常跟在代码后面)
                        name_pattern = r'[\u4e00-\u9fa5]{2,6}'
                        names = re.findall(name_pattern, line)
                        if names:
                            stock_name = names[0]
                    # 提取数值数据
                    # 现价、涨幅、流通市值、量比、4分钟涨速、主力净量、净额占比、换手、市盈、振幅、涨停次数
                    numbers = re.findall(r'-?\d+\.?\d*', line)
                    data = {
                        'stock_code': stock_code,
                        'stock_name': stock_name or '',
                        'current_price': self._parse_number(numbers, 0),
                        'change_pct': self._parse_number(numbers, 1),
                        'circulation_market_value': self._parse_number(numbers, 2),
                        'volume_ratio': self._parse_number(numbers, 3),
                        'four_min_change_rate': self._parse_number(numbers, 4),
                        'main_net_amount': self._parse_number(numbers, 5),
                        'net_amount_ratio': self._parse_number(numbers, 6),
                        'turnover_rate': self._parse_number(numbers, 7),
                        'pe_ratio': self._parse_number(numbers, 8),
                        'amplitude': self._parse_number(numbers, 9),
                        'good_news': '',
                        'limit_up_count': self._parse_integer(numbers, 10),
                        'save_date': save_date,
                        'save_time': save_time
                    }
                    # 尝试从下一行获取更多信息(如果当前行数据不完整)
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        # 检查是否包含利好信息
                        if '利好' in next_line or '涨停' in next_line:
                            data['good_news'] = next_line[:100]  # 限制长度
                    parsed_data.append(data)
                i += 1
            # 如果标准格式解析失败,尝试更宽松的格式
            if not parsed_data:
                # 使用更简单的模式:查找所有包含股票代码的行
                for line in lines:
                    codes = re.findall(stock_code_pattern, line)
                    if codes:
                        stock_code = codes[0]
                        numbers = re.findall(r'-?\d+\.?\d*', line)
                        # 尝试提取股票名称
                        stock_name = None
                        name_pattern = r'[\u4e00-\u9fa5]{2,6}'
                        names = re.findall(name_pattern, line)
                        if names:
                            stock_name = names[0]
                        data = {
                            'stock_code': stock_code,
                            'stock_name': stock_name or '',
                            'current_price': self._parse_number(numbers, 0) if len(numbers) > 0 else None,
                            'change_pct': self._parse_number(numbers, 1) if len(numbers) > 1 else None,
                            'circulation_market_value': self._parse_number(numbers, 2) if len(numbers) > 2 else None,
                            'volume_ratio': self._parse_number(numbers, 3) if len(numbers) > 3 else None,
                            'four_min_change_rate': self._parse_number(numbers, 4) if len(numbers) > 4 else None,
                            'main_net_amount': self._parse_number(numbers, 5) if len(numbers) > 5 else None,
                            'net_amount_ratio': self._parse_number(numbers, 6) if len(numbers) > 6 else None,
                            'turnover_rate': self._parse_number(numbers, 7) if len(numbers) > 7 else None,
                            'pe_ratio': self._parse_number(numbers, 8) if len(numbers) > 8 else None,
                            'amplitude': self._parse_number(numbers, 9) if len(numbers) > 9 else None,
                            'good_news': '',
                            'limit_up_count': self._parse_integer(numbers, 10) if len(numbers) > 10 else None,
                            'save_date': save_date,
                            'save_time': save_time
                        }
                        parsed_data.append(data)
            return parsed_data
        except Exception as e:
            print(f"解析同花顺数据失败: {e}")
            import traceback
            traceback.print_exc()
            return []


    def _save_ths_data_to_db(self, data_list):
        """保存同花顺数据到数据库"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            saved_count = 0
            failed_count = 0
            error_details = []
            for idx, data in enumerate(data_list, 1):
                try:
                    # 验证必要字段
                    stock_code = data.get('stock_code', '').strip()
                    if not stock_code:
                        error_details.append(f"第{idx}条: 股票代码为空")
                        failed_count += 1
                        continue
                    # 确保save_date和save_time存在
                    save_date = data.get('save_date', '')
                    save_time = data.get('save_time', '')
                    if not save_date or not save_time:
                        now = datetime.now()
                        save_date = save_date or now.strftime('%Y-%m-%d')
                        save_time = save_time or now.strftime('%H:%M:%S')
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
                        data.get('stock_name', '') or '',
                        data.get('current_price'),
                        data.get('change_pct'),
                        data.get('circulation_market_value'),
                        data.get('volume_ratio'),
                        data.get('four_min_change_rate'),
                        data.get('main_net_amount'),
                        data.get('net_amount_ratio'),
                        data.get('turnover_rate'),
                        data.get('pe_ratio'),
                        data.get('amplitude'),
                        data.get('good_news', '') or '',
                        data.get('limit_up_count'),
                        save_date,
                        save_time
                    ))
                    saved_count += 1
                except sqlite3.IntegrityError:
                    # 如果数据已存在,跳过
                    error_details.append(f"第{idx}条({stock_code}): 数据已存在或违反唯一约束")
                    failed_count += 1
                    continue
                except Exception as e:
                    error_msg = f"第{idx}条({data.get('stock_code', 'N/A')}): {e!s}"
                    error_details.append(error_msg)
                    print(f"保存单条数据失败: {error_msg}")
                    failed_count += 1
                    continue
            conn.commit()
            conn.close()
            # 如果有错误,打印详细信息
            if failed_count > 0:
                print("\n保存详情:")
                print(f"成功: {saved_count} 条")
                print(f"失败: {failed_count} 条")
                if len(error_details) <= 10:
                    for detail in error_details:
                        print(f"  - {detail}")
                else:
                    for detail in error_details[:10]:
                        print(f"  - {detail}")
                    print(f"  ... 还有 {len(error_details) - 10} 条错误")
            return saved_count
        except Exception as e:
            error_msg = f"保存同花顺数据失败: {e}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return 0


    def _pywencai_df_to_elevator_stocks(self, df):
        """将 pywencai 返回的 DataFrame 转为条件选股表格行(代码、名称及问财返回的行情/指标列,缺失填 0)。"""
        import re
        stocks = []
        if df is None or getattr(df, "empty", True):
            return stocks
        cols = list(df.columns)
        def pick_col(*subs):
            for sub in subs:
                for c in cols:
                    sc = str(c)
                    if sub in sc or sub.lower() in sc.lower():
                        return c
            return None
        code_col = pick_col("股票代码", "证券代码", "代码")
        if not code_col:
            for c in cols:
                try:
                    s = df[c].dropna().astype(str).head(12)
                    if s.str.replace(r"\D", "", regex=True).str.len().ge(6).any():
                        code_col = c
                        break
                except Exception:
                    pass
        if not code_col:
            return stocks
        name_col = pick_col("股票简称", "证券简称", "简称", "名称")
        price_c = pick_col("最新价", "现价", "收盘价")
        pct_c = pick_col("涨跌幅", "涨跌")
        vol_c = pick_col("成交量")
        amt_c = pick_col("成交额", "成交金额")
        mcap_c = pick_col("总市值", "流通市值", "市值")
        pe_c = pick_col("市盈率", "市盈")
        wr_c = pick_col("WR2", "wr2")
        bias_c = pick_col("BIAS3", "bias3")
        diff_c = pick_col("DIFF", "周线diff", "diff")
        d_c = None
        for c in cols:
            sc = str(c).lower()
            if ("kdj" in sc or "随机" in sc) and "d" in sc:
                d_c = c
                break
        if not d_c:
            d_c = pick_col("D值")
        def to_float(v, default=0.0):
            try:
                if pd.isna(v):
                    return default
                s = str(v).strip().replace(",", "").replace("%", "")
                if not s or s in ("--", "-", "nan"):
                    return default
                return float(s)
            except Exception:
                return default
        for _, row in df.iterrows():
            try:
                raw = row[code_col]
            except Exception:
                continue
            raw = str(raw)
            code = re.sub(r"\D", "", raw.replace(".SH", "").replace(".SZ", "").replace(".BJ", ""))
            if len(code) >= 6:
                code = code[-6:]
            if len(code) != 6 or not code.isdigit():
                continue
            name = ""
            if name_col and name_col in row.index:
                name = str(row[name_col]).strip()
            stocks.append({
                "code": code,
                "name": name,
                "price": to_float(row[price_c]) if price_c and price_c in row.index else 0.0,
                "change_pct": to_float(row[pct_c]) if pct_c and pct_c in row.index else 0.0,
                "volume": to_float(row[vol_c]) if vol_c and vol_c in row.index else 0.0,
                "turnover": to_float(row[amt_c]) if amt_c and amt_c in row.index else 0.0,
                "market_cap": to_float(row[mcap_c]) if mcap_c and mcap_c in row.index else 0.0,
                "pe_ratio": to_float(row[pe_c]) if pe_c and pe_c in row.index else 0.0,
                "wr2": to_float(row[wr_c]) if wr_c and wr_c in row.index else 0.0,
                "d": to_float(row[d_c]) if d_c and d_c in row.index else 0.0,
                "bias3": to_float(row[bias_c]) if bias_c and bias_c in row.index else 0.0,
                "diff": to_float(row[diff_c]) if diff_c and diff_c in row.index else 0.0,
            })
        return self._dedupe_elevator_stocks_by_code(stocks)


    def _query_iwencai_stocks(self, question):
        """同花顺问财选股:优先 pywencai(需本机 Node+可选 Cookie),失败则尝试旧版 HTTP,再失败则 tushare 本地兜底。"""
        import shutil
        question = (question or "").strip()
        if not question:
            return []
        _ck = (os.environ.get("IWENCAI_COOKIE") or os.environ.get("WENCAI_COOKIE") or "").strip()
        _node_ok = bool(shutil.which("node"))
        # 问财挂起守卫: 未配置 IWENCAI_COOKIE 时 pywencai/旧版HTTP 几乎必失败(403/401/NoneType),
        # 且每次都会 spawn node 重试十几轮拖慢界面。挂起后直接走 tushare 本地兜底,配置 Cookie 即自动恢复。
        _wencai_ready = bool(_ck)
        _pywencai_ok = False
        _need_cookie = False
        # 方法1: pywencai (需 Node + IWENCAI_COOKIE)
        if _wencai_ready and _node_ok:
            try:
                import pywencai
                _pywencai_ok = True
                _kw = {"query": question, "loop": True, "retry": 15, "sleep": 1}
                if _ck:
                    _kw["cookie"] = _ck
                df = pywencai.get(**_kw)
                stocks = self._pywencai_df_to_elevator_stocks(df)
                if stocks:
                    print(f"[问财/pywencai] 选股成功,共 {len(stocks)} 只")
                    return stocks
                print("[问财/pywencai] 返回空数据")
            except ImportError:
                exe = getattr(sys, "executable", "") or "python"
                print(f'[问财] pywencai 未装,请执行: "{exe}" -m pip install -U pywencai')
            except Exception as e:
                print(f"[问财/pywencai] 失败: {e}")
                _need_cookie = ("NoneType" in str(e) and "get" in str(e)) or True  # pywencai 几乎都因需要 cookie 而失败
                try:
                    _ok, _probe_msg = self._probe_iwencai_access(question)
                    print(f"[问财/pywencai] 探测: {_probe_msg}")
                except Exception:
                    pass
        # 方法2: 旧版 HTTP (已失效 401,仅作为历史残留; 未配 Cookie 同样跳过)
        if _wencai_ready:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Referer': 'http://www.iwencai.com/',
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Content-Type': 'application/json'
                }
                url = "http://www.iwencai.com/customized/chart/get-robot-data"
                data = {"question": question, "perpage": 100, "page": 1, "secondary_intent": "stock"}
                response = requests.post(url, json=data, headers=headers, timeout=15)
                if response.status_code == 200:
                    result = response.json()
                    stocks = self._parse_iwencai_data(result)
                    if stocks:
                        print(f"[问财/旧版HTTP] 选股成功,共 {len(stocks)} 只")
                        return stocks
                elif response.status_code == 401:
                    print("[问财/旧版HTTP] 401 Unauthorized(接口已废弃)")
                else:
                    print(f"[问财/旧版HTTP] HTTP {response.status_code}")
            except Exception as e:
                print(f"[问财/旧版HTTP] 失败: {e}")
        # 方法3: tushare 本地兜底 (解析简单条件)
        try:
            stocks = self._tushare_local_filter(question)
            if stocks:
                print(f"[tushare本地兜底] 选股成功,共 {len(stocks)} 只(注意:复杂条件可能未完全匹配)")
                return stocks
        except Exception as e:
            print(f"[tushare本地兜底] 失败: {e}")
        # 全部失败 — 返回空列表,让 UI 显示诊断信息
        return []


    def _parse_iwencai_data(self, data):
        """解析问财返回的数据"""
        try:
            stock_list = []
            if not data or 'data' not in data:
                return []
            # 尝试不同的数据结构
            if 'answer' in data['data']:
                answer_data = data['data']['answer']
                if isinstance(answer_data, list) and len(answer_data) > 0:
                    stocks = answer_data[0].get('txt', [])
                    for stock in stocks:
                        if isinstance(stock, dict):
                            stock_info = {
                                'code': stock.get('股票代码', stock.get('code', '')),
                                'name': stock.get('股票简称', stock.get('name', '')),
                                'price': float(stock.get('最新价', stock.get('price', 0))),
                                'change_pct': float(stock.get('涨跌幅', stock.get('change_pct', 0))),
                                'volume': int(stock.get('成交量', stock.get('volume', 0))),
                                'turnover': float(stock.get('成交额', stock.get('turnover', 0))),
                                'market_cap': float(stock.get('总市值', stock.get('market_cap', 0))),
                                'pe_ratio': float(stock.get('市盈率', stock.get('pe_ratio', 0))),
                                'wr2': float(stock.get('WR2', stock.get('wr2', 0))),
                                'd': float(stock.get('D', stock.get('d', 0))),
                                'bias3': float(stock.get('BIAS3', stock.get('bias3', 0))),
                                'diff': float(stock.get('DIFF', stock.get('diff', 0)))
                            }
                            stock_list.append(stock_info)
            return self._dedupe_elevator_stocks_by_code(stock_list)
        except Exception as e:
            print(f"解析问财数据失败: {e}")
            return []


    def _discover_iwencai_skills_from_disk(self):
        """扫描 ~/.aime-skillhub/skills 下已安装技能(含 SKILL.md 与可选 scripts/cli.py)。"""
        import re as _re
        from pathlib import Path
        root = Path.home() / ".aime-skillhub" / "skills"
        out = []
        if not root.is_dir():
            return out
        def _name_from_skill_md(md_path: Path):
            try:
                text = md_path.read_text(encoding="utf-8", errors="ignore")
                if not text.lstrip().startswith("---"):
                    return None
                end = text.find("---", 3)
                if end <= 0:
                    return None
                fm = text[3:end]
                for line in fm.splitlines():
                    m = _re.match(r"^\s*name:\s*(.+)\s*$", line)
                    if m:
                        return m.group(1).strip().strip('"').strip("'")
            except Exception:
                return None
            return None
        for top in sorted(root.iterdir(), key=lambda p: p.name):
            if not top.is_dir() or top.name.startswith("."):
                continue
            skill_md = None
            for md in top.rglob("SKILL.md"):
                skill_md = md
                break
            title = _name_from_skill_md(skill_md) if skill_md else top.name
            cli_path = ""
            if skill_md:
                cand = skill_md.parent / "scripts" / "cli.py"
                if cand.is_file():
                    cli_path = str(cand)
                else:
                    for c in skill_md.parent.rglob("scripts/cli.py"):
                        cli_path = str(c)
                        break
            out.append(
                {
                    "id": top.name,
                    "title": title or top.name,
                    "root": str(top),
                    "cli": cli_path,
                    "skill_md": str(skill_md) if skill_md else "",
                }
            )
        return out


    def _iwencai_skillhub_query2data_http(self, query: str) -> str:
        """同花顺 OpenAPI v1/query2data(通用问财数据),需 IWENCAI_API_KEY / IWENCAI_BASE_URL。"""
        import json as _json
        load_iwencai_env_from_dotfiles()
        q = (query or "").strip()
        if not q:
            return "请输入问题/查询语句。"
        base = (os.environ.get("IWENCAI_BASE_URL") or "https://openapi.iwencai.com").rstrip("/")
        key = (os.environ.get("IWENCAI_API_KEY") or "").strip()
        if not key:
            return (
                "未设置 IWENCAI_API_KEY。\n"
                "程序已尝试从 ~/.zshrc、~/.bash_profile 等读取 export。\n"
                "若仍如此:请在上述文件中添加 export IWENCAI_API_KEY='你的密钥',保存后用终端执行 "
                "`source ~/.zshrc` 并**从该终端**启动本程序;或完全退出后从终端运行 python 启动。"
            )
        url = f"{base}/v1/query2data"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "query": q,
            "source": "test",
            "page": "1",
            "limit": "50",
            "is_cache": "1",
            "expand_index": "true",
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=90)
            try:
                data = r.json()
            except Exception:
                return f"HTTP {r.status_code}\n{r.text[:4000]}"
            return _json.dumps(data, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"请求失败: {e}"


    def _run_iwencai_skill_worker(self, skill_id: str, cli_path: str, query: str):
        """在后台线程执行技能:有 cli 则子进程调用,否则走通用 query2data。"""
        import subprocess
        load_iwencai_env_from_dotfiles()
        q = (query or "").strip()
        if not q:
            return "请输入问题。"
        if skill_id == "__generic__":
            return self._format_skillhub_result_display(self._iwencai_skillhub_query2data_http(q))
        if cli_path and os.path.isfile(cli_path):
            try:
                cwd = os.path.dirname(os.path.dirname(cli_path))
                env = os.environ.copy()
                p = subprocess.run(
                    [sys.executable, cli_path, "--query", q],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=cwd,
                    env=env,
                )
                out = (p.stdout or "").strip()
                err = (p.stderr or "").strip()
                if err:
                    out = (out + "\n\n--- stderr ---\n" + err).strip()
                if p.returncode != 0 and not out:
                    return f"进程退出码 {p.returncode}\n{err or '无输出'}"
                return self._format_skillhub_result_display(out or "(无标准输出)")
            except subprocess.TimeoutExpired:
                return "执行超时(>120s)。"
            except Exception as e:
                return f"调用技能脚本失败: {e}\n\n可改用左侧「通用问财」或直接检查 scripts/cli.py。"
        return self._format_skillhub_result_display(self._iwencai_skillhub_query2data_http(q))


    def _iwencai_query2data_dict(self, query: str, limit: str = "50"):
        """同花顺 OpenAPI v1/query2data,返回 (parsed dict 或 None, 错误说明)。"""
        load_iwencai_env_from_dotfiles()
        q = (query or "").strip()
        if not q:
            return None, "请输入查询语句。"
        base = (os.environ.get("IWENCAI_BASE_URL") or "https://openapi.iwencai.com").rstrip("/")
        key = (os.environ.get("IWENCAI_API_KEY") or "").strip()
        if not key:
            return None, "未设置 IWENCAI_API_KEY。"
        url = f"{base}/v1/query2data"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "query": q,
            "source": "test",
            "page": "1",
            "limit": str(limit),
            "is_cache": "1",
            "expand_index": "true",
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=90)
            try:
                data = r.json()
            except Exception:
                return None, f"HTTP {r.status_code}\n{(r.text or '')[:2000]}"
            if isinstance(data, dict) and data.get("success") is False:
                return None, str(data.get("error", data))
            return data, ""
        except Exception as e:
            return None, f"请求失败: {e}"


    def _stock_candidates_from_wencai_rows(self, rows):
        """将 query2data 的 datas 行或 pywencai 解析后的 dict 列表转为 {code,name,snippet}。"""
        import re
        out = []
        seen = set()
        if not rows:
            return out
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = None
            name = ""
            for k, v in row.items():
                sk = str(k)
                if "代码" in sk and "板块" not in sk:
                    raw = re.sub(r"\D", "", str(v).replace(".SH", "").replace(".SZ", "").replace(".BJ", ""))
                    if len(raw) >= 6:
                        code = raw[-6:]
                        break
            if not code:
                for k, v in row.items():
                    if str(k).strip() in ("code", "股票代码", "证券代码"):
                        raw = re.sub(r"\D", "", str(v))
                        if len(raw) >= 6:
                            code = raw[-6:]
                            break
            if not code or len(code) != 6 or not code.isdigit():
                continue
            if code in seen:
                continue
            seen.add(code)
            for k, v in row.items():
                sk = str(k)
                if any(x in sk for x in ("简称", "名称")) and "板块" not in sk:
                    name = str(v).strip()
                    break
            snippet = ""
            for key_sub in ("新闻", "公告", "原因", "事件", "摘要", "主题"):
                for k, v in row.items():
                    if key_sub in str(k) and v is not None:
                        s = str(v).strip()
                        if s and s not in ("--", "nan"):
                            snippet = s[:120]
                            break
                if snippet:
                    break
            out.append({"code": code, "name": name, "snippet": snippet, "raw": row})
        return out


    def show_iwencai_skillhub_dialog(self):
        """同花顺 Aime SkillHub:左侧选技能,右上输入问题,右下展示运行结果。"""
        import webbrowser
        load_iwencai_env_from_dotfiles()
        win = self._toplevel(self.root)
        win.title("问财技能(SkillHub)")
        win.geometry("1180x780")
        win.transient(self.root)
        # 顶部窗口操作按钮:最小化 / 最大化 / 隐藏
        top_ctrl = ttk.Frame(win, padding=(10, 8, 10, 0))
        top_ctrl.pack(fill=tk.X)
        def _min_window():
            try:
                win.iconify()
            except Exception:
                pass
        def _toggle_max_window():
            try:
                cur = str(win.state())
                if cur == "zoomed":
                    win.state("normal")
                else:
                    win.state("zoomed")
            except Exception:
                # 某些平台对 state("zoomed") 支持不一致,兜底全屏切换
                try:
                    is_full = bool(getattr(win, "_skillhub_fullscreen", False))
                    win.attributes("-fullscreen", not is_full)
                    win._skillhub_fullscreen = not is_full
                except Exception:
                    pass
        def _hide_window():
            try:
                win.withdraw()
                messagebox.showinfo("提示", "窗口已隐藏,可从主界面再次打开该功能。", parent=self.root)
            except Exception:
                pass
        ttk.Button(top_ctrl, text="最小化", width=8, command=_min_window).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(top_ctrl, text="最大化/还原", width=12, command=_toggle_max_window).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(top_ctrl, text="隐藏", width=8, command=_hide_window).pack(side=tk.RIGHT)
        main = ttk.Frame(win, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        main.rowconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        left = ttk.LabelFrame(main, text="技能与说明(~/.aime-skillhub/skills)", padding=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        tip = ttk.Label(
            left,
            text="安装:aime-skillhub-cli install \"技能名」。选中左侧技能可查看 SKILL.md 使用说明。",
            font=("TkDefaultFont", 9),
            wraplength=280,
        )
        tip.grid(row=0, column=0, sticky="w", pady=(0, 6))
        left_paned = ttk.PanedWindow(left, orient=tk.VERTICAL)
        left_paned.grid(row=1, column=0, sticky="nsew", pady=(0, 6))
        list_wrap = ttk.Frame(left_paned)
        usage_frame = ttk.LabelFrame(left_paned, text="使用说明(随选中技能更新)", padding=4)
        left_paned.add(list_wrap, weight=1)
        left_paned.add(usage_frame, weight=2)
        skill_list = tk.Listbox(list_wrap, width=36, height=10, font=("Microsoft YaHei", 11))
        skill_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(list_wrap, orient="vertical", command=skill_list.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        skill_list.configure(yscrollcommand=sb.set)
        usage_text = scrolledtext.ScrolledText(
            usage_frame, wrap=tk.WORD, height=14, font=("Microsoft YaHei", 10)
        )
        usage_text.pack(fill=tk.BOTH, expand=True)
        btn_row = ttk.Frame(left)
        btn_row.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(
            btn_row,
            text="刷新列表",
            command=lambda: _fill_skills(),
            width=10,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            btn_row,
            text="技能中心网页",
            command=lambda: webbrowser.open(
                "https://www.iwencai.com/unifiedwap/skillhub?sign=1775311701879"
            ),
            width=12,
        ).pack(side=tk.LEFT)
        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.rowconfigure(4, weight=2)
        right.columnconfigure(0, weight=1)
        top_right = ttk.Frame(right)
        top_right.grid(row=0, column=0, sticky="ew")
        top_right.columnconfigure(0, weight=1)
        top_right.columnconfigure(1, weight=0)
        top_right.columnconfigure(2, weight=0)
        top_right.columnconfigure(3, weight=0)
        ttk.Label(top_right, text="问题 / 查询语句:", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(top_right, text="量化skill:").grid(row=0, column=1, sticky="e", padx=(8, 4))
        selected_skill_text = tk.StringVar(value="请选择")
        skill_menu_btn = ttk.Menubutton(top_right, textvariable=selected_skill_text, width=28)
        skill_menu_btn.grid(row=0, column=2, sticky="e")
        selected_skill_vars = {}
        def _sync_selected_skills_to_question():
            picked = [name for name, var in selected_skill_vars.items() if var.get()]
            if picked:
                selected_skill_text.set("、".join(picked[:3]) + (f" 等{len(picked)}项" if len(picked) > 3 else ""))
            else:
                selected_skill_text.set("请选择")
            marker_prefix = "【量化skill】"
            all_text = question_text.get("1.0", tk.END)
            lines = all_text.splitlines()
            kept = [ln for ln in lines if not ln.startswith(marker_prefix)]
            if picked:
                head = marker_prefix + " " + "、".join(picked)
                new_text = "\n".join([head] + kept).strip() + "\n"
            else:
                new_text = ("\n".join(kept).strip() + "\n") if kept else ""
            question_text.delete("1.0", tk.END)
            question_text.insert("1.0", new_text)
        skill_dropdown_menu = tk.Menu(skill_menu_btn, tearoff=False)
        skill_menu_btn["menu"] = skill_dropdown_menu
        def _rebuild_skill_dropdown_menu():
            skill_dropdown_menu.delete(0, tk.END)
            selected_skill_vars.clear()
            names = []
            # 下拉框优先展示"量化按钮"左上角同源技能(与量化策略窗口保持一致)
            try:
                q_catalog = self._quant_strategy_skill_catalog() or []
                for it in q_catalog:
                    cat = str(it.get("cat") or "").strip()
                    title = str(it.get("title") or "").strip()
                    if not title:
                        continue
                    names.append(f"[{cat}] {title}" if cat else title)
            except Exception:
                q_catalog = []
            # 若量化技能目录暂不可用,则回退到本地 SkillHub 列表
            if not names:
                for ent in skill_entries:
                    sid = (ent.get("id") or "").strip()
                    if sid == "__generic__":
                        continue
                    title = (ent.get("title") or "").strip() or sid
                    names.append(title)
            # 去重并保持顺序
            seen = set()
            uniq_names = []
            for n in names:
                if n in seen:
                    continue
                seen.add(n)
                uniq_names.append(n)
            if not uniq_names:
                skill_dropdown_menu.add_command(label="(暂无本地量化skill)")
                selected_skill_text.set("暂无技能")
                return
            selected_skill_text.set("请选择")
            for n in uniq_names:
                v = tk.BooleanVar(value=False)
                selected_skill_vars[n] = v
                skill_dropdown_menu.add_checkbutton(
                    label=n,
                    variable=v,
                    command=_sync_selected_skills_to_question,
                )
        q_frame = ttk.Frame(right)
        q_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 8))
        q_frame.rowconfigure(0, weight=1)
        q_frame.columnconfigure(0, weight=1)
        question_text = scrolledtext.ScrolledText(q_frame, wrap=tk.WORD, height=8, font=("Microsoft YaHei", 12))
        question_text.grid(row=0, column=0, sticky="nsew")
        _os1_pf = getattr(self, "_os1_toolbox_prefill", None)
        if _os1_pf:
            try:
                question_text.insert("1.0", str(_os1_pf).strip() + "\n\n")
            finally:
                try:
                    delattr(self, "_os1_toolbox_prefill")
                except Exception:
                    self._os1_toolbox_prefill = None
        run_btn = ttk.Button(right, text="运行技能", width=14)
        run_btn.grid(row=2, column=0, sticky="w", pady=(0, 6))
        ttk.Label(right, text="运行结果:", font=("TkDefaultFont", 10, "bold")).grid(row=3, column=0, sticky="sw")
        out_frame = ttk.Frame(right)
        out_frame.grid(row=4, column=0, sticky="nsew")
        out_frame.rowconfigure(0, weight=1)
        out_frame.columnconfigure(0, weight=1)
        result_text = scrolledtext.ScrolledText(out_frame, wrap=tk.NONE, height=16, font=("Consolas", 11))
        result_text.grid(row=0, column=0, sticky="nsew")
        out_sb = ttk.Scrollbar(out_frame, orient="vertical", command=result_text.yview)
        out_sb.grid(row=0, column=1, sticky="ns")
        out_xscroll = ttk.Scrollbar(out_frame, orient="horizontal", command=result_text.xview)
        out_xscroll.grid(row=1, column=0, sticky="ew")
        result_text.configure(yscrollcommand=out_sb.set, xscrollcommand=out_xscroll.set)
        def _extract_stock_from_line(line_text):
            import re
            s = str(line_text or "").strip()
            if not s:
                return None, None
            m = re.search(r"([^\s()]{2,})\((\d{6})\)", s)
            if m:
                return m.group(2), m.group(1)
            m = re.search(r"(\d{6})(?:\.(?:SH|SZ|BJ))?", s, flags=re.IGNORECASE)
            if not m:
                return None, None
            code6 = m.group(1)
            after = s[m.end():].strip()
            name = ""
            if after:
                toks = after.split()
                if toks:
                    t0 = toks[0].strip()
                    if not re.match(r"^[+-]?\d+(\.\d+)?%?$", t0):
                        name = t0
            if not name:
                try:
                    name = get_stock_name_by_code(code6) or ""
                except Exception:
                    name = ""
            return code6, name
        def _open_stock_detail_from_result(event):
            try:
                idx = result_text.index(f"@{event.x},{event.y}")
                row = idx.split(".")[0]
                line_text = result_text.get(f"{row}.0", f"{row}.end")
                code6, name = _extract_stock_from_line(line_text)
                if not code6:
                    return
                status_var.set(f"打开持仓详情:{name or code6}({code6})")
                try:
                    # 按用户要求:优先打开「持仓详情标签页」
                    self._show_stock_detail_direct(name or code6, code6, 1)
                except Exception:
                    # 兜底再尝试打开股票分析弹窗
                    self._show_stock_analysis_dialog(code6, name or code6)
            except Exception:
                pass
        result_text.bind("<Double-Button-1>", _open_stock_detail_from_result)
        status_var = tk.StringVar(value="就绪")
        ttk.Label(right, textvariable=status_var, font=("TkDefaultFont", 9)).grid(
            row=5, column=0, sticky="w", pady=(6, 0)
        )
        # skill_id|title|cli_path|skill_md - 首项为通用 OpenAPI
        skill_entries = []
        GENERIC_USAGE = """【通用问财 · OpenAPI query2data】
作用:用自然语言调用同花顺开放接口,返回数据(下方展示为「概要 + 表格」)。
用法:在右侧「问题 / 查询语句」中输入查询内容,点击「运行技能」。
环境:需配置 IWENCAI_API_KEY(程序会尝试从 ~/.zshrc 等读取)。
说明:不绑定某一技能包内的 SKILL,为通用 query2data。"""
        def _selected_entry():
            if not skill_list.curselection():
                return None
            i = int(skill_list.curselection()[0])
            if 0 <= i < len(skill_entries):
                return skill_entries[i]
            return None
        def _update_usage_panel(event=None):
            ent = _selected_entry()
            usage_text.delete("1.0", tk.END)
            if not ent:
                usage_text.insert("1.0", "请在左侧选择一个技能。")
                return
            if ent.get("id") == "__generic__":
                usage_text.insert("1.0", GENERIC_USAGE)
                return
            md_path = ent.get("skill_md") or ""
            meta = parse_skill_md_for_usage(md_path)
            chunks = []
            if (meta.get("description") or "").strip():
                chunks.append("【简介】\n" + meta["description"].strip())
            if (meta.get("usage_body") or "").strip():
                chunks.append("【SKILL.md】\n" + meta["usage_body"].strip())
            if not chunks:
                usage_text.insert(
                    "1.0",
                    "(未找到该技能目录下的 SKILL.md)\n\n"
                    "仍可在右侧用自然语言提问;若技能包含 scripts/cli.py,将优先调用脚本。",
                )
                return
            usage_text.insert("1.0", "\n\n".join(chunks))
        def _fill_skills():
            skill_list.delete(0, tk.END)
            skill_entries.clear()
            skill_entries.append(
                {
                    "id": "__generic__",
                    "title": "通用问财(OpenAPI query2data)",
                    "cli": "",
                    "root": "",
                    "skill_md": "",
                }
            )
            skill_list.insert(tk.END, skill_entries[0]["title"])
            for s in self._discover_iwencai_skills_from_disk():
                skill_entries.append(s)
                skill_list.insert(tk.END, f'{s["title"]}  [{s["id"]}]')
            if len(skill_entries) == 1:
                status_var.set("未扫描到本地技能包,可使用「通用问财」或先安装技能后点「刷新列表」。")
            else:
                status_var.set(f"已加载 {len(skill_entries) - 1} 个本地技能,通用接口始终可用。")
            if skill_list.size():
                skill_list.selection_set(0)
            _update_usage_panel()
            _rebuild_skill_dropdown_menu()
        def _do_run():
            ent = _selected_entry()
            if not ent:
                messagebox.showwarning("提示", "请先选择左侧技能。", parent=win)
                return
            q = question_text.get("1.0", tk.END).strip()
            if not q:
                messagebox.showwarning("提示", "请输入问题或查询语句。", parent=win)
                return
            result_text.delete("1.0", tk.END)
            status_var.set("运行中...")
            run_btn.configure(state="disabled")
            def work():
                try:
                    text = self._run_iwencai_skill_worker(ent["id"], ent.get("cli") or "", q)
                    win.after(0, lambda: _done_ok(text))
                except Exception as e:
                    win.after(0, lambda e=e: _done_err(str(e)))
            def _done_ok(text):
                result_text.insert("1.0", text or "")
                status_var.set("完成")
                run_btn.configure(state="normal")
            def _done_err(msg):
                result_text.insert("1.0", msg)
                status_var.set("失败")
                run_btn.configure(state="normal")
            threading.Thread(target=work, daemon=True).start()
        run_btn.configure(command=_do_run)
        skill_list.bind("<Double-Button-1>", lambda e: _do_run())
        skill_list.bind("<<ListboxSelect>>", _update_usage_panel)
        _fill_skills()


    def _fetch_iwencai_metric(self, query, value_hints=None):
        """问财查询:返回命中条数与首个可解析数值(如涨跌幅/家数)。"""
        try:
            _ck_metric = (os.environ.get("IWENCAI_COOKIE") or os.environ.get("WENCAI_COOKIE") or "").strip()
            if not _ck_metric:
                # 问财挂起: 未配置 Cookie → 快速返回空,由上层 tushare 指标补缺逻辑接管
                return {"count": None, "value": None, "msg": "问财未配置(IWENCAI_COOKIE),链路已挂起", "stocks": []}
            import inspect
            if not shutil.which("node"):
                return {"count": None, "value": None, "msg": "未检测到 Node.js(pywencai 依赖 node 生成请求头)"}
            import pywencai
            kw = {"query": query, "loop": True}
            result = pywencai.get(**kw)
            if result is None:
                return {"count": 0, "value": None, "msg": "问财返回空"}
            if isinstance(result, dict):
                return {"count": 0, "value": None, "msg": "问财返回非表格数据"}
            df = result
            value = None
            hints = tuple(value_hints or [])
            if len(df) > 0:
                # 优先按提示词匹配列名提取数值
                candidate_cols = []
                for c in df.columns:
                    cs = str(c)
                    if hints and any(h in cs for h in hints):
                        candidate_cols.append(c)
                if not candidate_cols:
                    # 兜底:常见数值列关键词
                    for c in df.columns:
                        cs = str(c)
                        if any(k in cs for k in ("涨跌幅", "家数", "数量", "值")):
                            candidate_cols.append(c)
                if not candidate_cols:
                    candidate_cols = list(df.columns)
                for c in candidate_cols:
                    s = pd.to_numeric(df[c], errors="coerce")
                    s = s.dropna()
                    if len(s) > 0:
                        value = float(s.iloc[0])
                        break
            # 提取股票列表(股票代码和名称)
            stocks = []
            for _, row in df.iterrows():
                stock_code = None
                stock_name = None
                for c in df.columns:
                    cs = str(c)
                    if "代码" in cs or "股票代码" in cs:
                        stock_code = str(row[c]).strip()
                        # 去掉股票代码中的字母前缀(如SH、SZ)
                        import re
                        code_match = re.search(r'\d{6}', stock_code)
                        if code_match:
                            stock_code = code_match.group()
                    elif "名称" in cs or "股票名称" in cs:
                        stock_name = str(row[c]).strip()
                if stock_code or stock_name:
                    stocks.append({"code": stock_code, "name": stock_name})
            return {"count": len(df), "value": value, "msg": "pywencai", "stocks": stocks}
        except ImportError:
            return {"count": None, "value": None, "msg": "未安装 pywencai", "stocks": []}
        except Exception as e:
            return {"count": None, "value": None, "msg": f"问财异常: {e}", "stocks": []}



__all__ = ["WencaiMixin"]
