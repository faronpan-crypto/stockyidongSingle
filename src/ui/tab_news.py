"""NewsMixin - 新闻/资讯/股吧/爬虫"""
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
    import requests
except ImportError: requests = None
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
import sys
import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin
import sqlite3

class NewsMixin:
    """新闻/资讯/股吧/爬虫"""

    def _schedule_rt_news_link_reapply_under_win(self, win):
        """含实时快讯的 ScrolledText 在改弹窗字号后重绑蓝色可点行。"""
        def walk(w):
            for ch in w.winfo_children():
                try:
                    if isinstance(ch, scrolledtext.ScrolledText) and getattr(
                        ch, "_rt_news_items", None
                    ):
                        ch.after(0, lambda c=ch: self._rt_news_reapply_links(c))
                except Exception:
                    pass
                walk(ch)
        walk(win)

    def show_market_news_sources(self):
        """显示市场行情导航(5列名称显示,双击名称打开链接)"""
        try:
            # 站点列表(名称, 链接)。可持续扩充,目标≈300个(美/欧/日主流经济与新闻站点)。
            sites = [
                # 中国/中文财经主流
                ("东方财富", "https://www.eastmoney.com/"),
                ("同花顺财经", "https://news.10jqka.com.cn/"),
                ("上证报", "https://www.cnstock.com/"),
                ("证券时报", "https://www.stcn.com/"),
                ("第一财经", "https://www.yicai.com/"),
                ("21财经", "https://www.21jingji.com/"),
                ("新浪财经", "https://finance.sina.com.cn/"),
                ("和讯财经", "https://www.hexun.com/"),
                ("华尔街见闻", "https://wallstreetcn.com/"),
                ("央视财经", "https://finance.cctv.com/"),
                ("财联社", "https://www.cls.cn/"),
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
                ("选股宝", "https://xuangubao.cn/"),
                ("淘股吧", "https://www.taoguba.com.cn/"),
                ("东方财富股吧", "https://guba.eastmoney.com/"),
                ("韭研公社", "https://www.gogudata.com/"),
                ("雪球", "https://xueqiu.com/"),
                # 美国/国际英语
                ("Reuters", "https://www.reuters.com/finance/"),
                ("Bloomberg", "https://www.bloomberg.com/markets"),
                ("WSJ", "https://www.wsj.com/"),
                ("Financial Times", "https://www.ft.com/"),
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
                # 欧洲多语
                ("BBC Business", "https://www.bbc.com/news/business"),
                ("The Guardian Business", "https://www.theguardian.com/uk/business"),
                ("Financial Times Alphaville", "https://ftalphaville.ft.com/"),
                ("DW 德国之声", "https://www.dw.com/zh/%E7%BB%8F%E6%B5%8E/s-1432"),
                ("Handelsblatt", "https://www.handelsblatt.com/"),
                ("FAZ Wirtschaft", "https://www.faz.net/aktuell/wirtschaft"),
                ("Der Spiegel Wirtschaft", "https://www.spiegel.de/wirtschaft/"),
                ("Le Monde Économie", "https://www.lemonde.fr/economie/"),
                ("Les Echos", "https://www.lesechos.fr/"),
                ("Le Figaro Économie", "https://www.lefigaro.fr/economie/"),
                ("El País Economía", "https://elpais.com/economia/"),
                ("El Mundo Economía", "https://www.elmundo.es/economia.html"),
                ("Il Sole 24 Ore", "https://www.ilsole24ore.com/"),
                ("La Repubblica Economia", "https://www.repubblica.it/economia/"),
                ("NZZ Wirtschaft", "https://www.nzz.ch/wirtschaft"),
                ("SRF Wirtschaft", "https://www.srf.ch/news/wirtschaft"),
                ("The Times Business", "https://www.thetimes.co.uk/business"),
                ("City A.M.", "https://www.cityam.com/"),
                # 日本与亚洲
                ("Nikkei 日本经济新闻", "https://www.nikkei.com/"),
                ("Nikkei Asia", "https://asia.nikkei.com/"),
                ("NHK Biz", "https://www3.nhk.or.jp/nhkworld/en/news/business/"),
                ("朝日新闻 财经", "https://www.asahi.com/business/"),
                ("读卖新闻 经济", "https://www.yomiuri.co.jp/economy/"),
                ("共同社 经济", "https://china.kyodonews.net/news/economy"),
                ("Jiji Press", "https://www.jiji.com/"),
                ("日经中文网", "https://cn.nikkei.com/"),
                # 其他国际
                ("Bloomberg China", "https://www.bloombergchina.com/"),
                ("路透中文", "https://cn.reuters.com/"),
                ("FT中文网", "https://www.ftchinese.com/"),
                ("华尔街日报中文", "https://cn.wsj.com/"),
                ("Investing.com", "https://www.investing.com/"),
            ]
            win = self._safe_toplevel(self.root)
            win.title("📊 市场行情 - 市场与媒体/大V导航")
            # 窗口大小设置为屏幕70%,并居中
            try:
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                ww = int(sw * 0.7)
                wh = int(sh * 0.7)
                wx = (sw - ww) // 2
                wy = (sh - wh) // 2
                win.geometry(f"{ww}x{wh}+{wx}+{wy}")
            except Exception:
                win.geometry("1000x700")
            win.minsize(800, 500)  # 可调整大小,设置最小尺寸
            # 5列名称(名称1~名称5),每列点击可打开对应站点
            columns = ("名称1", "名称2", "名称3", "名称4", "名称5")
            tree = ttk.Treeview(win, columns=columns, show="headings")
            for col in columns:
                tree.heading(col, text=col)
                try:
                    safe_width = int((ww - 80) / 5)
                except Exception:
                    safe_width = int((win.winfo_screenwidth() * 0.7 - 80) / 5) if win.winfo_screenwidth() else 180
                tree.column(col, width=safe_width, anchor=tk.W)  # 平均宽度
            # 滚动条(横向+纵向)
            yscroll = ttk.Scrollbar(win, orient=tk.VERTICAL, command=tree.yview)
            xscroll = ttk.Scrollbar(win, orient=tk.HORIZONTAL, command=tree.xview)
            tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))
            xscroll.pack(fill=tk.X, padx=10, pady=(0, 10))
            yscroll.place(relx=1.0, rely=0.0, relheight=1.0, anchor='ne')
            # 将站点按行填充,每行最多5个
            sources_map = {}  # item_id -> [(name,url), ... up to 5]
            row = []
            for site in sites:
                row.append(site)
                if len(row) == 5:
                    names = [r[0] for r in row]
                    item_id = tree.insert("", tk.END, values=tuple(names))
                    sources_map[item_id] = row.copy()
                    row = []
            if row:
                # 补齐空列
                names = [r[0] for r in row]
                names += [""] * (5 - len(names))
                item_id = tree.insert("", tk.END, values=tuple(names))
                # 补齐映射
                padded = row + [("", "")] * (5 - len(row))
                sources_map[item_id] = padded
            def on_dbl_click(event):
                # 识别列
                col = tree.identify_column(event.x)  # '#1'..'#5'
                try:
                    col_idx = int(col.replace('#', '')) - 1
                except Exception:
                    col_idx = 0
                item = tree.selection()
                if not item:
                    return
                item_id = item[0]
                mapping = sources_map.get(item_id, [])
                if 0 <= col_idx < len(mapping):
                    _name, url = mapping[col_idx]
                    if url:
                        import webbrowser
                        webbrowser.open(url)
            tree.bind("<Double-1>", on_dbl_click)
        except Exception as e:
            messagebox.showerror("错误", f"打开市场行情失败: {e}")

    def crawl_xuangubao_web(self):
        """自动爬取选股宝网页内容,如果爬取不到则逐个访问指定网页并拼接"""
        def crawl_thread():
            try:
                # 生成带时间的标签页名称
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                tab_title = f"选股宝{current_time}"
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
                    "https://xuangutong.com.cn/",
                    "https://xuangutong.com.cn/live",
                    "https://xuangutong.com.cn/jingxuan",
                    "https://xuangutong.com.cn/ts/home",
                    "https://xuangutong.com.cn/zzd/home",
                    "https://xuangutong.com.cn/zhutiku"
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
                    self.root.after(0, lambda e=e: messagebox.showerror("错误", f"爬取选股宝失败: {e}"))
        threading.Thread(target=crawl_thread, daemon=True).start()

    def one_click_save_news(self):
        """将左边和右边各个标签页逐个保存到资讯表"""
        if not hasattr(self, "text_widgets"):
            messagebox.showwarning("警告", "没有可保存的标签页")
            return
        self.one_click_news_event.clear()
        def save_thread():
            saved_count = 0
            failed_count = 0
            try:
                left_tabs = []
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
                            left_tabs.append({
                                'title': tab_info.get('title') or f"标签页{len(left_tabs)+1}",
                                'content': text
                            })
                    except (tk.TclError, AttributeError) as e:
                        # widget已被销毁或无效,跳过
                        print(f"跳过无效的左侧widget {tab_id}: {e}")
                        continue
                right_tabs = []
                for tab_id, tab_info in list(self.result_tabs.items()):  # 使用list()避免迭代时修改字典
                    try:
                        widget = tab_info.get('widget')
                        if widget is None:
                            continue
                        # 检查widget是否仍然存在
                        if not hasattr(widget, 'winfo_exists') or not widget.winfo_exists():
                            continue
                        text = widget.get("1.0", tk.END).strip()
                        if text:
                            right_tabs.append({
                                'title': tab_info.get('title') or f"分析结果{len(right_tabs)+1}",
                                'content': text
                            })
                    except (tk.TclError, AttributeError) as e:
                        # widget已被销毁或无效,跳过
                        print(f"跳过无效的右侧widget {tab_id}: {e}")
                        continue
                if not left_tabs and not right_tabs:
                    messagebox.showwarning("警告", "没有可保存的标签页内容")
                    return
                for tab_info in left_tabs:
                    title = f"左侧_{tab_info['title']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    if save_news_info_to_db(title, tab_info['content']):
                        saved_count += 1
                    else:
                        failed_count += 1
                for tab_info in right_tabs:
                    title = f"右侧_{tab_info['title']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    if save_news_info_to_db(title, tab_info['content']):
                        saved_count += 1
                    else:
                        failed_count += 1
                total = saved_count + failed_count
                if saved_count > 0:
                    msg = f"一键资讯完成:成功保存 {saved_count}/{total} 个标签页到资讯表"
                    if failed_count > 0:
                        msg += f",失败 {failed_count} 个"
                    messagebox.showinfo("成功", msg)
                else:
                    messagebox.showerror("错误", "所有标签页保存失败")
            except Exception as exc:
                messagebox.showerror("错误", f"一键资讯保存失败: {exc}")
            finally:
                self.one_click_news_event.set()
        threading.Thread(target=save_thread, daemon=True).start()

    def batch_crawl_news(self):
        """批量爬取资讯:获取选中网址,执行爬虫,读取内容,保存到资讯数据表"""
        try:
            # 获取选中的网址
            selected_urls = []
            crawler_info = {
                'taoguba': {'name': '淘股吧', 'url': 'https://www.taoguba.com.cn/'},
                'jiuyan': {'name': '韭研', 'url': 'https://www.jiuyangongshe.com/'},
                'eastmoney': {'name': '东方财富', 'url': 'https://www.eastmoney.com/'},
                'xueqiu': {'name': '雪球', 'url': 'https://xueqiu.com/'},
                'xuangubao': {'name': '选股宝', 'url': 'https://xuangubao.cn/'},
                'ths': {'name': '同花顺', 'url': 'https://www.10jqka.com.cn/'}
            }
            # 获取选中的爬取项
            if hasattr(self, 'crawler_checkboxes'):
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
            if not selected_urls:
                messagebox.showwarning("警告", "请先在主界面勾选要爬取的网址(爬取项或市场导航项)")
                return
            # 确认开始
            result = messagebox.askyesno("确认",
                f"将开始批量爬取 {len(selected_urls)} 个网址\n"
                f"爬取后将自动读取内容并保存到资讯数据表\n\n"
                f"是否继续?")
            if not result:
                return
            # 创建临时保存目录
            temp_dir = os.path.join(D_DATA_DIR, "CrawledWebsites", f"batch_crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(temp_dir, exist_ok=True)
            # 在新线程中执行爬取和读取
            def crawl_and_save():
                try:
                    # 先执行爬虫
                    self._batch_crawl_urls(selected_urls, temp_dir)
                    # 等待一下确保文件已保存
                    time.sleep(2)
                    # 读取爬取的文件内容
                    all_content = self._read_crawled_files(temp_dir)
                    if all_content:
                        # 汇总内容
                        summary_content = "\n\n".join(all_content)
                        # 保存到资讯数据表
                        tab_name = f"批量爬取资讯_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        if save_news_info_to_db(tab_name, summary_content):
                            self.root.after(0, lambda: messagebox.showinfo("成功",
                                f"批量爬取完成!\n\n"
                                f"共爬取 {len(selected_urls)} 个网址\n"
                                f"已保存到资讯数据表:{tab_name}\n"
                                f"临时文件目录:{temp_dir}"))
                            # 刷新资讯数据表(如果存在该方法)
                            if hasattr(self, 'refresh_news_data'):
                                self.root.after(0, self.refresh_news_data)
                        else:
                            self.root.after(0, lambda: messagebox.showerror("错误", "保存到资讯数据表失败"))
                    else:
                        self.root.after(0, lambda: messagebox.showwarning("警告",
                            f"爬取完成,但未能读取到有效内容\n临时文件目录:{temp_dir}"))
                except Exception as e:
                    import traceback
                    error_msg = f"批量爬取失败: {e!s}\n{traceback.format_exc()}"
                    self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
            threading.Thread(target=crawl_and_save, daemon=True).start()
            messagebox.showinfo("提示", "批量爬取任务已启动,请稍候...")
        except Exception as e:
            messagebox.showerror("错误", f"启动批量爬取失败: {e}")
            import traceback
            traceback.print_exc()

    def _crawl_xuangubao_sync(self):
        """同步爬取选股宝,返回内容和标签页名称"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            tab_title = f"选股宝{current_time}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            target_urls = [
                "https://xuangutong.com.cn/",
                "https://xuangutong.com.cn/live",
                "https://xuangutong.com.cn/jingxuan",
                "https://xuangutong.com.cn/ts/home",
                "https://xuangutong.com.cn/zzd/home",
                "https://xuangutong.com.cn/zhutiku"
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
                    print("警告: 选股宝爬取内容可能包含乱码")
                return full_content, tab_title
        except Exception as e:
            print(f"爬取选股宝失败: {e}")
        return None, None

    def _crawl_taoguba_sync(self):
        """同步爬取淘股吧,返回内容和标签页名称"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            tab_title = f"淘股吧{current_time}"
            # 使用TaogubaCrawler爬取
            articles = self.taoguba_crawler.crawl_realtime_articles(max_pages=3)
            if articles:
                all_content = []
                all_content.append(f"\n{'='*80}\n来源: 淘股吧实时文章\n{'='*80}\n")
                for i, article in enumerate(articles, 1):
                    article_url = article.get('url', '')
                    article_text = f"{i}. {article['title']}\n"
                    if article_url:
                        article_text += f"   链接: [点击打开] {article_url}\n"
                    article_text += f"   作者: {article.get('author', '')}\n"
                    article_text += f"   发布时间: {article.get('publish_time', '')}\n"
                    content = article.get('content', '')
                    # 检查内容是否乱码
                    if content and self._detect_garbled_text(content):
                        print(f"警告: 淘股吧文章 {i} 内容可能包含乱码")
                    article_text += f"   内容: {content}\n"
                    article_text += "-"*80 + "\n"
                    all_content.append(article_text)
                full_content = '\n'.join(all_content)
                if self._detect_garbled_text(full_content):
                    print("警告: 淘股吧爬取内容可能包含乱码")
                return full_content, tab_title
        except Exception as e:
            print(f"爬取淘股吧失败: {e}")
            return None, None

    def _crawl_jiuyan_sync(self):
        """同步爬取韭研,返回内容和标签页名称"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            tab_title = f"韭研{current_time}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://www.jiuyangongshe.com/'
            }
            urls = [
                "https://www.jiuyangongshe.com/",
                "https://www.jiuyangongshe.com/?page=2",
                "https://www.jiuyangongshe.com/?page=3"
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
                        text_content = soup.get_text(separator='\n', strip=True)
                        lines = []
                        for line in text_content.split('\n'):
                            line = line.strip()
                            if line:
                                lines.append(line)
                        cleaned_text = '\n'.join(lines)
                        if cleaned_text and not self._detect_garbled_text(cleaned_text):
                            all_content.append(f"\n{'='*80}\n来源: {url}\n编码: {used_encoding}\n{'='*80}\n{cleaned_text}\n")
                        elif cleaned_text:
                            all_content.append(f"\n{'='*80}\n来源: {url}\n编码: {used_encoding} (可能包含乱码)\n{'='*80}\n{cleaned_text}\n")
                        time.sleep(1)
                    else:
                        print(f"跳过 {url}: 无法获取或修正内容")
                except Exception as e:
                    print(f"爬取 {url} 失败: {e}")
                    continue
            if all_content:
                full_content = '\n'.join(all_content)
                if self._detect_garbled_text(full_content):
                    print("警告: 韭研爬取内容可能包含乱码")
                return full_content, tab_title
        except Exception as e:
            print(f"爬取韭研失败: {e}")
            return None, None

    def _crawl_jiuyan_plan_stocks(self):
        """爬取韭研公社计划页面的股票并导入到韭研标签页(group_index=6)"""
        try:
            import re
            from tkinter import messagebox
            # 显示进度提示
            progress_window = self._safe_toplevel(self.root)
            progress_window.title("爬取韭研计划")
            progress_window.geometry("400x150")
            progress_window.transient(self.root)
            progress_label = ttk.Label(progress_window, text="正在爬取韭研公社计划页面...", font=("TkDefaultFont", 11))
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
                        'Referer': 'https://www.jiuyangongshe.com/'
                    }
                    # 爬取计划页面
                    url = "https://www.jiuyangongshe.com/plan"
                    try:
                        response = requests.get(url, headers=headers, timeout=30)
                        response.encoding = 'utf-8'
                        html_content = response.text
                    except Exception as e:
                        print(f"请求失败: {e}")
                        # 尝试使用编码修正方法
                        html_content, _ = self._fetch_with_encoding_fix(url, headers, max_retries=3)
                    if not html_content:
                        def show_error():
                            progress_window.destroy()
                            messagebox.showerror("错误", "无法获取韭研公社计划页面内容", parent=self.root)
                        self.root.after(0, show_error)
                        return
                    # 解析HTML提取股票信息
                    soup = BeautifulSoup(html_content, 'html.parser')
                    # 提取股票名称和代码
                    stocks = []
                    # 方法1:查找包含股票代码的元素(6位数字)
                    stock_code_pattern = re.compile(r'[036]\d{5}')
                    stock_name_pattern = re.compile(r'[\u4e00-\u9fa5]{2,8}')
                    # 查找所有文本内容
                    text_content = soup.get_text()
                    # 查找所有可能的股票代码
                    found_codes = stock_code_pattern.findall(text_content)
                    # 方法2:查找特定的HTML结构(根据网页实际结构调整)
                    # 查找包含股票信息的元素
                    for element in soup.find_all(['div', 'span', 'a', 'td', 'li', 'p']):
                        element_text = element.get_text(strip=True)
                        # 检查是否包含股票代码
                        codes_in_element = stock_code_pattern.findall(element_text)
                        if codes_in_element:
                            for code in codes_in_element:
                                # 尝试在同一元素或附近找到股票名称
                                # 移除代码后查找中文名称
                                text_without_code = element_text.replace(code, '')
                                names = stock_name_pattern.findall(text_without_code)
                                # 过滤掉常见的非股票名称词汇
                                exclude_words = ['计划', '持仓', '买入', '卖出', '涨停', '跌停', '加仓', '减仓',
                                               '韭研', '公社', '股票', '代码', '名称', '价格', '数量', '金额',
                                               '今日', '明日', '本周', '本月', '操作', '建议', '分析', '策略']
                                for name in names:
                                    if name not in exclude_words and len(name) >= 2:
                                        # 检查是否已存在
                                        if not any(s['code'] == code for s in stocks):
                                            stocks.append({
                                                'name': name,
                                                'code': code
                                            })
                                            break
                    # 如果上面方法没找到,尝试直接从代码列表获取
                    if not stocks and found_codes:
                        import akshare as ak
                        for code in found_codes[:80]:  # 最多80个
                            try:
                                # 尝试通过akshare获取股票名称
                                if not any(s['code'] == code for s in stocks):
                                    # 简单验证代码格式
                                    if code.startswith(('0', '3', '6')):
                                        stocks.append({
                                            'name': '',  # 名称稍后通过API获取
                                            'code': code
                                        })
                            except:
                                continue
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
                                "未能从韭研公社计划页面提取到股票信息\n"
                                "可能需要登录或页面结构已变化",
                                parent=self.root)
                            return
                        # 导入到韭研标签页(group_index=6)
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
                            f"已从韭研公社计划页面导入 {import_count} 只股票到韭研标签页",
                            parent=self.root)
                    self.root.after(0, update_ui)
                except Exception as e:
                    import traceback
                    error_msg = f"爬取失败: {e!s}\n{traceback.format_exc()}"
                    print(error_msg)
                    def show_error(e=e):
                        progress_window.destroy()
                        messagebox.showerror("错误", f"爬取韭研公社计划页面失败:\n{e!s}", parent=self.root)
                    self.root.after(0, show_error)
            # 启动爬取线程
            threading.Thread(target=crawl_thread, daemon=True).start()
        except Exception as e:
            messagebox.showerror("错误", f"启动爬取失败: {e!s}", parent=self.root)

    def save_ocr_to_news(self):
        """将OCR识别结果保存为资讯"""
        try:
            # 获取分析标签页的内容(如果为空,则使用OCR识别器的内容)
            analysis_text = self.analysis_tab_widget.get("1.0", tk.END).strip()
            if not analysis_text:
                analysis_text = self.ocr_tab_widget.get("1.0", tk.END).strip()
            if not analysis_text:
                messagebox.showwarning("警告", "没有内容可保存为资讯")
                return
            # 保存到资讯数据库
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            # 生成标题(使用前50个字符)
            title = analysis_text[:50].replace('\n', ' ').strip()
            if not title:
                title = f"OCR识别结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            # 保存到数据库
            cursor.execute('''
                INSERT INTO crawled_articles (source, title, content, crawled_at)
                VALUES (?, ?, ?, ?)
            ''', ("OCR识别", title, analysis_text, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            conn.close()
            messagebox.showinfo("成功", f"OCR识别结果已保存为资讯!\n\n标题: {title}")
        except Exception as e:
            messagebox.showerror("错误", f"保存资讯失败: {e!s}")
            import traceback
            traceback.print_exc()

    def crawl_taoguba_direct(self):
        """直接调用淘股吧爬取程序,使用 run_crawler_script 函数(已正确处理打包环境和编码)"""
        # 使用 run_crawler_script 函数,它已经正确处理了打包环境和编码问题
        # 这个函数会在后台线程中执行,并在完成后查找Excel文件
        self.run_crawler_script("taoguba")

    def crawl_taoguba(self):
        """爬取淘股吧信息并显示在右边文本框"""
        def crawl_thread():
            try:
                result_widget = self._get_result_text_for_crawler()
                if not result_widget:
                    return
                self.root.after(0, lambda: result_widget.insert(tk.END, "\n" + "="*80 + "\n"))
                self.root.after(0, lambda: result_widget.insert(tk.END, "开始爬取淘股吧信息...\n"))
                self.root.after(0, lambda: result_widget.see(tk.END))
                articles = self.taoguba_crawler.crawl_realtime_articles(max_pages=3)
                if articles:
                    result_text = "\n" + "="*80 + "\n"
                    result_text += "淘股吧精华文章\n"
                    result_text += "="*80 + "\n\n"
                    for i, article in enumerate(articles, 1):
                        result_text += f"{i}. {article['title']}\n"
                        result_text += f"   链接: {article['url']}\n"
                        result_text += f"   发布时间: {article['publish_time']}\n"
                        result_text += "-"*80 + "\n\n"
                        # 保存到数据库
                        save_article_to_db(
                            source="淘股吧",
                            title=article['title'],
                            author=article.get('author'),
                            url=article.get('url'),
                            publish_time=article.get('publish_time')
                        )
                    result_text += f"\n共爬取 {len(articles)} 篇文章\n"
                    result_text += "="*80 + "\n"
                    self.root.after(0, lambda: result_widget.insert(tk.END, result_text))
                    self.root.after(0, lambda: result_widget.see(tk.END))
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"成功爬取 {len(articles)} 篇淘股吧文章"))
                else:
                    self.root.after(0, lambda: result_widget.insert(tk.END, "\n未获取到文章\n"))
                    self.root.after(0, lambda: messagebox.showwarning("警告", "未获取到文章"))
            except Exception as e:
                error_msg = f"爬取淘股吧失败: {e!s}"
                result_widget = self._get_result_text_for_crawler()
                if result_widget:
                    self.root.after(0, lambda: result_widget.insert(tk.END, f"\n{error_msg}\n"))
                self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        threading.Thread(target=crawl_thread, daemon=True).start()

    def crawl_jiuyangongshe(self):
        """自动爬取韭研公社网页内容到左边新标签"""
        def crawl_thread():
            try:
                # 生成带时间的标签页名称
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                tab_title = f"韭研{current_time}"
                # 创建新标签页用于显示内容
                tab_id = None
                text_widget_ref = [None]  # 使用列表以便在lambda中修改
                def create_tab():
                    nonlocal tab_id
                    tab_id = self.create_text_tab(tab_title)
                    text_widget_ref[0] = self.get_active_text_widget()
                self.root.after(0, create_tab)
                time.sleep(0.2)  # 等待标签页创建完成
                # 更新结果文本框显示进度
                result_widget = self.get_active_result_widget()
                if result_widget:
                    self.root.after(0, lambda: result_widget.insert(tk.END, "正在爬取韭研公社网页内容...\n"))
                    self.root.after(0, lambda: result_widget.see(tk.END))
                # 设置请求头
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Referer': 'https://www.jiuyangongshe.com/'
                }
                # 爬取多个页面
                urls = [
                    "https://www.jiuyangongshe.com/",
                    "https://www.jiuyangongshe.com/?page=2",
                    "https://www.jiuyangongshe.com/?page=3"
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
                # 将所有内容添加到新创建的标签页文本框
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
                    # 保存到新创建的标签页
                    def save_to_tab():
                        # 查找刚创建的标签页
                        for tab_info in self.text_widgets.values():
                            if tab_info.get('title') == tab_title:
                                text_widget = tab_info.get('widget')
                                if text_widget:
                                    text_widget.delete("1.0", tk.END)
                                    text_widget.insert("1.0", full_content)
                                    text_widget.see("1.0")
                                    # 切换到该标签页
                                    self.text_notebook.select(tab_info.get('frame'))
                                    break
                    self.root.after(0, save_to_tab)
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

    def crawl_taoguba_and_analyze(self):
        """爬取淘股吧并自动分析和保存股票"""
        def crawl_thread():
            try:
                # 显示进度提示
                self.root.after(0, lambda: messagebox.showinfo("提示", "开始爬取淘股吧,请稍候..."))
                # 导入淘股吧爬取模块
                try:
                    import os
                    import sys
                    os.path.dirname(os.path.abspath(__file__))
                    # 支持打包后的环境查找脚本文件
                    script_name = "taoguba_realtime.py"
                    taoguba_path = None
                    # 1. 尝试使用 PyInstaller 打包后的路径(sys._MEIPASS)
                    if hasattr(sys, '_MEIPASS'):
                        meipass_path = os.path.join(sys._MEIPASS, script_name)
                        if os.path.exists(meipass_path):
                            taoguba_path = meipass_path
                    # 2. 尝试可执行文件所在目录的 _internal 子目录
                    if not taoguba_path and hasattr(sys, 'frozen'):
                        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                        internal_path = os.path.join(exe_dir, '_internal', script_name)
                        if os.path.exists(internal_path):
                            taoguba_path = internal_path
                    # 3. 尝试与主程序同目录
                    if not taoguba_path:
                        same_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
                        if os.path.exists(same_dir_path):
                            taoguba_path = same_dir_path
                    # 4. 尝试当前工作目录
                    if not taoguba_path:
                        cwd_path = os.path.join(os.getcwd(), script_name)
                        if os.path.exists(cwd_path):
                            taoguba_path = cwd_path
                    if not taoguba_path or not os.path.exists(taoguba_path):
                        error_msg = f"找不到淘股吧爬取程序:\n{script_name}\n\n"
                        if hasattr(sys, '_MEIPASS'):
                            error_msg += f"已尝试路径:\n1. {os.path.join(sys._MEIPASS, script_name)}\n"
                        if hasattr(sys, 'frozen'):
                            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                            error_msg += f"2. {os.path.join(exe_dir, '_internal', script_name)}\n"
                        error_msg += f"3. {os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)}\n"
                        error_msg += f"4. {os.path.join(os.getcwd(), script_name)}\n"
                        self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
                        return
                    # 动态导入模块
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("taoguba_realtime", taoguba_path)
                    taoguba_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(taoguba_module)
                    # 创建爬虫实例
                    crawler = taoguba_module.TaogubaRealtimeCrawler()
                    # 只爬取淘股吧(调用_get_articles_by_page方法)
                    articles_list = []
                    for page in range(1, 4):  # 爬取3页
                        page_articles = crawler._get_articles_by_page(page)
                        articles_list.extend(page_articles)
                        if page < 3:
                            import time
                            time.sleep(1)  # 延迟避免请求过快
                    if not articles_list:
                        self.root.after(0, lambda: messagebox.showwarning("警告", "未能获取到淘股吧文章数据"))
                        return
                    # 获取文章详细内容
                    articles_data = crawler.enrich_articles_data(articles_list)
                    # 合并所有文章内容为文本
                    combined_text = ""
                    for article in articles_data:
                        title = article.get('标题', '')
                        content = article.get('文章内容', '')
                        author = article.get('作者', '')
                        if title:
                            combined_text += f"标题:{title}\n"
                        if author:
                            combined_text += f"作者:{author}\n"
                        if content:
                            combined_text += f"内容:{content}\n"
                        combined_text += "\n" + "="*80 + "\n\n"
                    if not combined_text.strip():
                        self.root.after(0, lambda: messagebox.showwarning("警告", "未能获取到文章内容"))
                        return
                    # 在主线程中更新UI
                    def update_ui():
                        try:
                            # 切换到文本控制标签页
                            if hasattr(self, 'crawler_control_notebook'):
                                self.crawler_control_notebook.select(1)  # 切换到文本控制标签页
                            # 创建或获取文本标签页
                            if not hasattr(self, 'text_notebook') or not self.text_notebook:
                                messagebox.showerror("错误", "文本输入框未初始化")
                                return
                            # 创建新标签页或使用第一个标签页
                            tab_id = None
                            if hasattr(self, 'text_widgets') and self.text_widgets:
                                # 使用第一个标签页
                                tab_id = next(iter(self.text_widgets.keys()))
                            else:
                                # 创建新标签页
                                self.tab_counter += 1
                                tab_id = f"tab_{self.tab_counter}"
                                tab_frame = ttk.Frame(self.text_notebook)
                                self.text_notebook.add(tab_frame, text=f"淘股吧_{datetime.now().strftime('%H%M%S')}")
                                text_widget = scrolledtext.ScrolledText(tab_frame, wrap=tk.WORD, font=("TkDefaultFont", 14))
                                text_widget.pack(fill=tk.BOTH, expand=True)
                                self.text_widgets[tab_id] = text_widget
                            # 将内容放入文本框
                            text_widget = self.text_widgets[tab_id]
                            text_widget.delete("1.0", tk.END)
                            text_widget.insert("1.0", combined_text)
                            # 切换到该标签页
                            self.text_notebook.select(tab_id)
                            # 自动触发分析
                            self.analyze_and_generate()
                            # 提取股票并保存到数据库
                            stock_names, _ = extract_stock_names(combined_text)
                            if stock_names:
                                current_date = datetime.now().strftime('%Y-%m-%d')
                                saved_count = 0
                                for stock_name in stock_names:
                                    try:
                                        # 保存股票到数据库(备注:淘股吧)
                                        save_stock_logic_to_db(stock_name, combined_text[:500], current_date, source="淘股吧")
                                        saved_count += 1
                                    except Exception as e:
                                        print(f"保存股票 {stock_name} 失败: {e}")
                                messagebox.showinfo("完成", f"爬取完成!\n已分析并保存 {saved_count} 只股票到数据库(备注:淘股吧)")
                            else:
                                messagebox.showinfo("完成", "爬取完成!但未识别到股票")
                        except Exception as e:
                            messagebox.showerror("错误", f"更新界面失败: {e}")
                            import traceback
                            traceback.print_exc()
                    self.root.after(0, update_ui)
                except ImportError as e:
                    self.root.after(0, lambda e=e: messagebox.showerror("错误", f"导入淘股吧爬取模块失败: {e}"))
                except Exception as e:
                    self.root.after(0, lambda e=e: messagebox.showerror("错误", f"爬取淘股吧失败: {e}"))
                    import traceback
                    traceback.print_exc()
            except Exception as e:
                self.root.after(0, lambda e=e: messagebox.showerror("错误", f"操作失败: {e}"))
                import traceback
                traceback.print_exc()
        # 在后台线程中执行爬取
        threading.Thread(target=crawl_thread, daemon=True).start()

    def show_news_data_dialog(self):
        """显示资讯数据表窗口,支持多选和按日期筛选,导出到左边内容标签页"""
        win = self._safe_toplevel(self.root)
        win.title("资讯数据表")
        win.geometry("1400x800")
        # 查询条件框架
        query_frame = ttk.LabelFrame(win, text="查询条件", padding=10)
        query_frame.pack(fill=tk.X, padx=5, pady=5)
        date_frame = ttk.Frame(query_frame)
        date_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(date_frame, text="起始日期:").pack(side=tk.LEFT, padx=5)
        start_date_var = tk.StringVar()
        start_date_entry = ttk.Entry(date_frame, textvariable=start_date_var, width=12)
        start_date_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text="(格式: YYYY-MM-DD)").pack(side=tk.LEFT, padx=2)
        ttk.Label(date_frame, text="结束日期:").pack(side=tk.LEFT, padx=(10, 5))
        end_date_var = tk.StringVar()
        end_date_entry = ttk.Entry(date_frame, textvariable=end_date_var, width=12)
        end_date_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text="(格式: YYYY-MM-DD)").pack(side=tk.LEFT, padx=2)
        ttk.Label(date_frame, text="标签页名称:").pack(side=tk.LEFT, padx=(10, 5))
        tab_name_var = tk.StringVar()
        tab_name_entry = ttk.Entry(date_frame, textvariable=tab_name_var, width=20)
        tab_name_entry.pack(side=tk.LEFT, padx=5)
        # 数据表格
        table_frame = ttk.Frame(win)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        news_columns = ("ID", "标签页名称", "内容预览", "创建时间", "更新时间")
        news_tree = ttk.Treeview(table_frame, columns=news_columns, show="headings", height=25)
        for col in news_columns:
            news_tree.heading(col, text=col)
            if col == "ID":
                news_tree.column(col, width=50, anchor=tk.CENTER)
            elif col == "标签页名称":
                news_tree.column(col, width=200, anchor=tk.CENTER)
            elif col == "内容预览":
                news_tree.column(col, width=400)
            elif col == "创建时间" or col == "更新时间":
                news_tree.column(col, width=150, anchor=tk.CENTER)
        news_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=news_tree.yview)
        news_tree.configure(yscrollcommand=news_scrollbar.set)
        news_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        news_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 按钮框架
        button_frame = ttk.Frame(win, padding=5)
        button_frame.pack(fill=tk.X)
        def refresh_news_data():
            """刷新资讯数据"""
            for item in news_tree.get_children():
                news_tree.delete(item)
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                query = "SELECT id, tab_name, content, created_at, updated_at FROM news_info WHERE 1=1"
                params = []
                start_date = start_date_var.get().strip()
                end_date = end_date_var.get().strip()
                tab_name_filter = tab_name_var.get().strip()
                if start_date:
                    query += " AND created_at >= ?"
                    params.append(f"{start_date} 00:00:00")
                if end_date:
                    query += " AND created_at <= ?"
                    params.append(f"{end_date} 23:59:59")
                if tab_name_filter:
                    query += " AND tab_name LIKE ?"
                    params.append(f'%{tab_name_filter}%')
                query += " ORDER BY created_at DESC"
                cursor.execute(query, params)
                results = cursor.fetchall()
                conn.close()
                for row in results:
                    news_id, tab_name, content, created_at, updated_at = row
                    # 内容预览(前100个字符)
                    content_preview = (content[:100] + "...") if content and len(content) > 100 else (content or "")
                    values = (news_id, tab_name, content_preview, created_at, updated_at)
                    news_tree.insert("", tk.END, values=values)
            except Exception as e:
                messagebox.showerror("错误", f"查询资讯数据失败: {e}", parent=win)
        def export_selected_to_tab():
            """将选中的资讯数据合并导出到左边内容标签页"""
            selections = news_tree.selection()
            if not selections:
                messagebox.showwarning("提示", "请先选择要导出的资讯数据", parent=win)
                return
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                # 收集所有选中的内容
                merged_content = []
                tab_names = []
                for item_id in selections:
                    item = news_tree.item(item_id)
                    values = item['values']
                    if len(values) >= 1:
                        news_id = values[0]
                        cursor.execute('SELECT tab_name, content, created_at FROM news_info WHERE id = ?', (news_id,))
                        row = cursor.fetchone()
                        if row:
                            tab_name, content, created_at = row
                            tab_names.append(tab_name)
                            merged_content.append(f"\n{'='*60}\n")
                            merged_content.append(f"标签页名称: {tab_name}\n")
                            merged_content.append(f"创建时间: {created_at}\n")
                            merged_content.append(f"{'='*60}\n")
                            if content:
                                merged_content.append(content)
                                merged_content.append("\n")
                conn.close()
                if not merged_content:
                    messagebox.showwarning("提示", "没有可导出的内容", parent=win)
                    return
                # 合并所有内容
                final_content = "".join(merged_content)
                # 生成标签页名称
                if len(tab_names) == 1:
                    tab_title = f"资讯_{tab_names[0]}"
                else:
                    # 多个标签页,使用日期范围或数量
                    tab_title = f"资讯_合并_{len(selections)}条"
                    if start_date_var.get() or end_date_var.get():
                        date_part = ""
                        if start_date_var.get():
                            date_part += start_date_var.get().replace("-", "")
                        if end_date_var.get():
                            if date_part:
                                date_part += f"_{end_date_var.get().replace('-', '')}"
                            else:
                                date_part = end_date_var.get().replace("-", "")
                        if date_part:
                            tab_title = f"资讯_{date_part}_{len(selections)}条"
                # 创建标签页并插入内容
                self.create_text_tab(tab_title, final_content)
                # 切换到文本控制标签页
                if hasattr(self, 'crawler_control_notebook'):
                    # 找到文本控制标签页的索引
                    for i in range(self.crawler_control_notebook.index("end")):
                        tab_text = self.crawler_control_notebook.tab(i, "text")
                        if "文本控制" in tab_text or "文本" in tab_text:
                            self.crawler_control_notebook.select(i)
                            break
                messagebox.showinfo("成功", f"已导出 {len(selections)} 条资讯到标签页: {tab_title}", parent=win)
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}", parent=win)
                import traceback
                traceback.print_exc()
        ttk.Button(button_frame, text="查询", command=refresh_news_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="导出到Excel", command=lambda: export_to_excel(), width=14).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="全选", command=lambda: news_tree.selection_set(news_tree.get_children())).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消全选", command=lambda: news_tree.selection_remove(news_tree.get_children())).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="导出选中到标签页", command=export_selected_to_tab, width=18).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="关闭", command=win.destroy).pack(side=tk.RIGHT, padx=5)
        def export_to_excel():
            """导出资讯数据到Excel"""
            try:
                # 获取选中的数据或按日期筛选的数据
                selections = news_tree.selection()
                start_date = start_date_var.get().strip()
                end_date = end_date_var.get().strip()
                tab_name_filter = tab_name_var.get().strip()
                # 确定要导出的数据
                if selections:
                    # 导出选中的数据
                    news_ids = []
                    for item_id in selections:
                        item = news_tree.item(item_id)
                        values = item['values']
                        if len(values) >= 1:
                            news_ids.append(values[0])
                    if not news_ids:
                        messagebox.showwarning("提示", "请先选择要导出的数据", parent=win)
                        return
                    # 查询选中的数据
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    placeholders = ','.join(['?'] * len(news_ids))
                    query = f"SELECT id, tab_name, content, created_at, updated_at FROM news_info WHERE id IN ({placeholders}) ORDER BY created_at DESC"
                    cursor.execute(query, news_ids)
                    results = cursor.fetchall()
                    conn.close()
                else:
                    # 按日期筛选导出
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    query = "SELECT id, tab_name, content, created_at, updated_at FROM news_info WHERE 1=1"
                    params = []
                    if start_date:
                        query += " AND created_at >= ?"
                        params.append(f"{start_date} 00:00:00")
                    if end_date:
                        query += " AND created_at <= ?"
                        params.append(f"{end_date} 23:59:59")
                    if tab_name_filter:
                        query += " AND tab_name LIKE ?"
                        params.append(f'%{tab_name_filter}%')
                    query += " ORDER BY created_at DESC"
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    conn.close()
                    if not results:
                        messagebox.showwarning("提示", "没有符合条件的数据", parent=win)
                        return
                # 选择保存目录
                from tkinter import filedialog
                save_dir = filedialog.askdirectory(title="选择保存目录", parent=win)
                if not save_dir:
                    return
                # 生成文件名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if selections:
                    filename = f"资讯数据_选中{len(results)}条_{timestamp}.xlsx"
                else:
                    if start_date or end_date:
                        date_part = ""
                        if start_date:
                            date_part += start_date.replace("-", "")
                        if end_date:
                            if date_part:
                                date_part += f"_{end_date.replace('-', '')}"
                            else:
                                date_part = end_date.replace("-", "")
                        filename = f"资讯数据_{date_part}_{len(results)}条_{timestamp}.xlsx"
                    else:
                        filename = f"资讯数据_全部_{len(results)}条_{timestamp}.xlsx"
                filepath = os.path.join(save_dir, filename)
                # 准备Excel数据
                excel_data = []
                for row in results:
                    news_id, tab_name, content, created_at, updated_at = row
                    excel_data.append({
                        'ID': news_id,
                        '标签页名称': tab_name,
                        '内容': content or '',
                        '创建时间': created_at,
                        '更新时间': updated_at
                    })
                # 导出到Excel
                df = pd.DataFrame(excel_data)
                df.to_excel(filepath, index=False, engine='openpyxl')
                messagebox.showinfo("成功", f"已导出 {len(results)} 条数据到:\n{filepath}", parent=win)
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}", parent=win)
                import traceback
                traceback.print_exc()
        self._attach_window_controls(win)
        # 初始加载数据
        refresh_news_data()

    def show_news_prediction_analysis(self):
        """资讯AI预测:对最近资讯表出现的股票预测下一交易日涨跌,重点关注热门股非去重中的股票。"""
        try:
            win = self._safe_toplevel(self.root)
            win.title("资讯股票AI预测")
            win.geometry("1200x800")
            win.transient(self.root)
            main = ttk.Frame(win, padding=10)
            main.pack(fill=tk.BOTH, expand=True)
            # 顶部工具栏:进度条 + 状态 + 天数设置
            toolbar = ttk.Frame(main)
            toolbar.pack(fill=tk.X, pady=(0, 8))
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(toolbar, variable=progress_var, length=260, mode="determinate")
            progress_bar.pack(side=tk.LEFT, padx=(0, 10))
            status_var = tk.StringVar(value="点击开始预测按钮开始...")
            status_label = ttk.Label(toolbar, textvariable=status_var)
            status_label.pack(side=tk.LEFT, padx=(0, 10))
            days_var = tk.IntVar(value=30)
            ttk.Label(toolbar, text="天数:").pack(side=tk.LEFT)
            ttk.Spinbox(toolbar, from_=5, to=60, textvariable=days_var, width=4).pack(side=tk.LEFT, padx=(2, 0))
            prov_info_var = tk.StringVar(value="")
            def _refresh_pred_provider_label():
                ap = self.ai_config_manager.config.get("active_provider", "?")
                m = self.ai_config_manager.get_active_provider_config().get("model", "")
                prov_info_var.set(f"当前AI: {ap} / {m or '未设模型'}")
            _refresh_pred_provider_label()
            def _open_ai_config_from_pred():
                self.show_ai_config()
                _refresh_pred_provider_label()
            def _test_ai_from_pred():
                status_var.set("正在测试AI连接...")
                win.update()
                r = self.call_ai_model("请只回复:连接测试成功。", max_tokens=80)
                ok = r and not str(r).startswith("错误") and "API调用失败" not in str(r) and "网络错误" not in str(r) and "AI调用错误" not in str(r)
                if ok:
                    messagebox.showinfo(
                        "测试成功",
                        f"当前提供商: {self.ai_config_manager.config.get('active_provider', '')}\n\n模型回复:\n{r[:400]}",
                        parent=win,
                    )
                    status_var.set("AI连接测试成功")
                else:
                    messagebox.showerror("测试失败", str(r)[:900] if r else "无返回", parent=win)
                    status_var.set("AI连接测试失败")
                _refresh_pred_provider_label()
            ttk.Button(toolbar, text="AI配置", width=10, command=_open_ai_config_from_pred).pack(side=tk.LEFT, padx=(12, 4))
            ttk.Button(toolbar, text="测试连接", width=10, command=_test_ai_from_pred).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Label(toolbar, textvariable=prov_info_var, font=("TkDefaultFont", 11), foreground="gray").pack(side=tk.LEFT, padx=(4, 0))
            # ========== 上方: 预测文本区 ==========
            top_pane = tk.Frame(main)
            top_pane.pack(fill=tk.BOTH, expand=True)
            text = scrolledtext.ScrolledText(top_pane, wrap=tk.WORD, font=("Consolas", 11), height=14)
            text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
            text.tag_configure("title", font=("TkDefaultFont", 12, "bold"), foreground="blue")
            text.tag_configure("section", font=("TkDefaultFont", 11, "bold"), foreground="green")
            text.tag_configure("info", foreground="gray")
            text.tag_configure("positive", foreground="red")
            text.tag_configure("negative", foreground="green")

            # ========== 下方: 股票预测表格区 (初始隐藏, 预测后显示) ==========
            bottom_frame = tk.LabelFrame(main, text="📊 预测股票 + 游资心法评分 (双击行看全解)",
                bg="#FFF8E1", font=("", 10, "bold"), fg="#E65100")
            # 初始不 pack, 预测成功后再 pack

            # Treeview 表格
            pred_cols = ("name", "code", "pred", "logic", "hm_score", "best_sch")
            pred_tree = ttk.Treeview(bottom_frame, columns=pred_cols, show="headings", height=8)
            for col, label, w in [("name","股票",80), ("code","代码",70), ("pred","AI预测",80),
                                   ("logic","逻辑摘要",260), ("hm_score","🦅心法分",80), ("best_sch","最强流派",100)]:
                pred_tree.heading(col, text=label)
                pred_tree.column(col, width=w, anchor="center")
            pred_tree.tag_configure("high", foreground="#C62828")   # 高分红
            pred_tree.tag_configure("mid", foreground="#F57F17")    # 中分橙
            pred_tree.tag_configure("low", foreground="#2E7D32")    # 低分绿
            pred_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5, side=tk.LEFT)
            pred_sb = ttk.Scrollbar(bottom_frame, orient="vertical", command=pred_tree.yview)
            pred_tree.configure(yscrollcommand=pred_sb.set)
            pred_sb.pack(fill="y", side=tk.RIGHT)

            # 双击行 → 游资心法全解 + 预测逻辑
            def _on_pred_tree_double(evt):
                sel = pred_tree.selection()
                if not sel: return
                item = pred_tree.item(sel[0])
                code6 = str(item["values"][1]) if len(item["values"]) > 1 else ""
                name = str(item["values"][0]) if len(item["values"]) > 0 else ""
                if not code6 or not code6.isdigit(): return
                # 收集该股的预测逻辑片段
                pred_logic = ""
                try:
                    ai_full = text.get("1.0", tk.END)
                    # 找该股所在行/段落
                    for line in ai_full.splitlines():
                        if code6 in line or name in line:
                            pred_logic += line + "\n"
                    # 再取前后2行
                    lines = ai_full.splitlines()
                    for i, ln in enumerate(lines):
                        if code6 in ln or (name and name in ln):
                            start = max(0, i - 2); end = min(len(lines), i + 3)
                            pred_logic = "\n".join(lines[start:end])
                            break
                except Exception:
                    pass
                # 弹出详情
                try:
                    from tkinter import Toplevel as _TL
                    detail = _TL(self.root)
                    detail.title(f"🦅 {name}({code6}) 预测详情 + 游资心法全解")
                    detail.geometry("900x700")
                    detail.configure(bg="#F5F5F5")
                    detail.transient(self.root)
                    # 上半: 预测逻辑
                    top_f = tk.LabelFrame(detail, text="📊 AI预测逻辑片段", bg="white", font=("", 10, "bold"))
                    top_f.pack(fill="x", padx=10, pady=(10, 4))
                    st_pred = scrolledtext.ScrolledText(top_f, height=8, font=("", 10), wrap=tk.WORD)
                    st_pred.pack(fill="both", expand=True, padx=5, pady=5)
                    st_pred.insert(tk.END, pred_logic or "(未找到预测逻辑片段)")
                    st_pred.configure(state="disabled")
                    # 下半: 游资心法快照 + 按钮
                    hm_f = tk.LabelFrame(detail, text="🦅 游资心法评分", bg="white", font=("", 10, "bold"))
                    hm_f.pack(fill="both", expand=True, padx=10, pady=4)
                    hm_lbl = tk.Label(hm_f, text="⏳ 正在计算...", bg="white", fg="#666", font=("", 10))
                    hm_lbl.pack(padx=10, pady=20)
                    def _bg_hm():
                        try:
                            hm = self._hm_calc_for_stock(code6)
                            sc = hm.get("avg_score")
                            if sc is None:
                                self.root.after(0, lambda: hm_lbl.configure(text="❌ 计算失败"))
                                return
                            best = hm.get("best_sch", "--")
                            scores_line = "  ".join(
                                f"{n}{i.get('score','-')}" for n, i in hm.get("scores", {}).items())
                            full_txt = (f"🦅 综合 {sc}分  |  最强流派: {best}\n\n"
                                       + scores_line + "\n\n"
                                       + f"📌 均线: MA5={hm.get('kline_info',{}).get('m5','-')}  MA10={hm.get('kline_info',{}).get('m10','-')}  MA20={hm.get('kline_info',{}).get('m20','-')}\n"
                                       + f"📌 DMA(距MA20): {hm.get('kline_info',{}).get('dma','-'):.2f}%  |  VR(量比): {hm.get('kline_info',{}).get('vr','-')}")
                            def _show():
                                hm_lbl.configure(text="")
                                tk.Label(hm_f, text=full_txt, bg="white", fg="#333",
                                    font=("", 11), justify="left", anchor="w").pack(anchor="w", padx=15, pady=10)
                                # 心法全解按钮
                                ttk.Button(hm_f, text="🔮 打开完整游资心法全解弹窗",
                                    command=lambda: (detail.withdraw(),
                                        self._open_hotmoney_single_dialog(auto_code=code6, auto_name=name))
                                ).pack(pady=10)
                            self.root.after(0, _show)
                        except Exception as _he:
                            self.root.after(0, lambda _he=_he: hm_lbl.configure(text=f"❌ {_he}"))
                    threading.Thread(target=_bg_hm, daemon=True).start()
                except Exception as _de:
                    messagebox.showerror("错误", f"打开详情失败: {_de}", parent=win)
            pred_tree.bind("<Double-1>", _on_pred_tree_double)
            def _is_win_alive():
                """检查窗口是否还活着(用户没关)"""
                try:
                    return bool(win.winfo_exists())
                except Exception:
                    return False
            def _tk_safe(action):
                """安全的 Tk 操作封装: 窗口关了就静默跳过"""
                try:
                    if _is_win_alive():
                        action()
                except Exception:
                    pass

            def run_prediction():
                try:
                    _tk_safe(lambda: text.delete("1.0", tk.END))
                    _tk_safe(lambda: text.insert(tk.END, "🤖 资讯股票AI预测\n", "title"))
                    if not _is_win_alive():
                        return
                    from datetime import datetime, timedelta
                    try:
                        ndays = int(days_var.get() or 30)
                    except Exception:
                        ndays = 30
                    ndays = max(5, min(60, ndays))
                    text.insert(tk.END, f"统计范围:最近 {ndays} 天资讯表中出现的股票;重点关注“热门股非去重“中出现的热门股。\n\n“, “info")
                    status_var.set("正在读取资讯表数据...")
                    progress_var.set(10)
                    win.update()
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    start_date = (datetime.now() - timedelta(days=ndays)).strftime("%Y-%m-%d")
                    cursor.execute(
                        """
                        SELECT tab_name, content, created_at
                        FROM news_info
                        WHERE created_at >= ?
                        ORDER BY created_at DESC
                        """,
                        (start_date,),
                    )
                    news_rows = cursor.fetchall()
                    if not news_rows:
                        text.insert(tk.END, "资讯表中在指定天数内没有数据。\n", "negative")
                        conn.close()
                        return
                    # 1) 统计最近 ndays 内资讯中出现的股票(按频次)
                    status_var.set("正在统计最近资讯中的股票...")
                    progress_var.set(25)
                    win.update()
                    try:
                        days_data = get_news_stocks_by_date_and_frequency(ndays=ndays)
                    except Exception:
                        days_data = []
                    from collections import Counter
                    freq_counter = Counter()
                    code_to_name = {}
                    for day_info in days_data:
                        for name, code in day_info.get("stocks", []):
                            if not code:
                                continue
                            freq_counter[code] += 1
                            if code not in code_to_name:
                                code_to_name[code] = name or code
                    # 2) 抓取"热门股非去重"相关的股票代码(最近 ndays)
                    status_var.set("正在识别“热门股非去重“中的股票...")
                    progress_var.set(35)
                    win.update()
                    hot_codes = set()
                    try:
                        cursor.execute(
                            """
                            SELECT tab_name, content
                            FROM news_info
                            WHERE tab_name LIKE '热门股非去重%%' AND created_at >= ?
                            """,
                            (start_date,),
                        )
                        hot_rows = cursor.fetchall()
                        import re
                        for tab_name, content in hot_rows:
                            if not content:
                                continue
                            codes = re.findall(r"\\b\\d{6}\\b", content)
                            for code in codes:
                                hot_codes.add(code)
                    except Exception:
                        pass
                    finally:
                        conn.close()
                    # 生成用于 AI 的股票列表文本(按频次降序)
                    status_var.set("正在准备AI提示词...")
                    progress_var.set(45)
                    win.update()
                    if not freq_counter:
                        text.insert(tk.END, "在指定天数内未能从资讯中解析出股票代码,无法进行预测。\n", "negative")
                        return
                    top_items = freq_counter.most_common(80)
                    stocks_lines = []
                    for code, cnt in top_items:
                        name = code_to_name.get(code, code)
                        is_hot = "是" if code in hot_codes else "否"
                        stocks_lines.append(f"{name}({code}) | 资讯出现次数: {cnt} | 是否热门股非去重股票: {is_hot}")
                    stocks_block = "\n".join(stocks_lines)
                    hot_block = ""
                    if hot_codes:
                        hot_top = [c for c, _ in top_items if c in hot_codes]
                        if hot_top:
                            hot_block = "\n".join(
                                f"{code_to_name.get(code, code)}({code})" for code in hot_top[:40]
                            )
                    # 当日市场:同花顺情绪指数日线 + 网上多篇财经报道摘要
                    status_var.set("正在拉取同花顺情绪指数与网络市场文章...")
                    progress_var.set(48)
                    win.update()
                    sent_txt, sent_ma1_up = self._prediction_fetch_ths_sentiment_daily()
                    articles = self._prediction_fetch_market_article_snippets(max_n=10, body_chars=850)
                    text.insert(tk.END, "\n📈 当日市场 · 同花顺情绪指数(日线)\n", "section")
                    text.insert(tk.END, "-" * 40 + "\n")
                    if sent_txt:
                        text.insert(tk.END, sent_txt + "\n", "info")
                    else:
                        text.insert(tk.END, str(sent_ma1_up) + "\n", "warning")
                    text.insert(tk.END, "\n📰 已抓取的市场分析文章(标题与链接,正文已送交 AI 归纳)\n", "section")
                    text.insert(tk.END, "-" * 40 + "\n")
                    if not articles:
                        text.insert(tk.END, "未能抓取到东方财富财经列表文章(可检查网络)。AI 将仅基于下方资讯表股票做预测。\n", "warning")
                    else:
                        for i, a in enumerate(articles, 1):
                            text.insert(tk.END, f"{i}. {a['title']}\n   {a['url']}\n", "info")
                    doc_blocks = []
                    for i, a in enumerate(articles, 1):
                        doc_blocks.append(
                            f"【文档{i}】标题: {a['title']}\n链接: {a['url']}\n正文摘要:\n{a['snippet']}\n"
                        )
                    web_corpus = "\n".join(doc_blocks) if doc_blocks else "(未抓取到网络文档,请跳过基于网页的归纳。)"
                    # 与富媒体 AI 分析相同:使用 active_provider + providers 配置(call_ai_model)
                    active = self.ai_config_manager.config.get("active_provider", "deepseek")
                    pc = self.ai_config_manager.get_active_provider_config()
                    if not pc.get("api_key", "").strip():
                        text.insert(
                            tk.END,
                            "未配置 API Key。请点击顶部「AI配置」选择提供商并填写密钥,保存后先点「测试连接」再预测。\n",
                            "negative",
                        )
                        return
                    status_var.set(f"正在调用 {active} 进行预测...")
                    progress_var.set(60)
                    win.update()
                    text.insert(
                        tk.END,
                        f"调用模型:提供商【{active}】 Base【{pc.get('base_url', '')}】 模型【{pc.get('model', '')}】\n\n",
                        "info",
                    )
                    sentiment_for_ai = sent_txt or str(sent_ma1_up)
                    system_prompt = (
                        "你是一名专业的A股市场分析师。你需要:"
                        "1根据程序提供的同花顺情绪指数日线与多篇网络财经报道,做当日市场观点归纳(须列出原文链接);"
                        "2再结合资讯表股票列表做次日涨跌概率预测。回答须结构化、简洁。"
                    )
                    user_prompt = f"""## 一、当日市场数据(程序拉取)
### 同花顺情绪指数 · 日线
{sentiment_for_ai}
请在本节结论中明确写出:**同花顺情绪指数 1 日线方向是否向上**(是/否),并一句话说明依据。
### 网络财经报道(程序从东方财富等列表页抓取的多篇正文摘要,每条均含可点击的原文链接)
{web_corpus}
请基于以上文档完成:
**A. 主要观点归纳**(3~8 条,每条后括号内必须写清**来源文章标题 + 完整 URL**)。
**B. 文档中提及或暗示的板块、主题**(列表)。
**C. 文档中明确提到的 A 股股票名称或 6 位代码**(列表;无法识别可写"未明确提及")。
---
## 二、资讯表股票预测任务(最近 {ndays} 天)
【股票列表】(按资讯出现次数)
{stocks_block}
【热门股非去重中出现的重点股票(若有)】
{hot_block or '(最近未识别到热门股非去重相关股票)'}
**D. 股票预测**:挑选最值得关注的至多 20 只,给出下一交易日预测方向(涨/跌/震荡)与大致幅度区间;表格或分点须含:股票名、代码、预测、逻辑、是否热门股非去重。
**E. 整体小结**(看多/空/震荡),并强调仅为概率推演,不构成投资建议。"""
                    ai_text = self.call_ai_model(user_prompt, system_prompt=system_prompt, max_tokens=4096)
                    if not ai_text:
                        ai_text = "未返回内容,请检查网络或增大 AI 配置中的 Timeout(秒)。"
                    # 窗口可能已被用户关闭, 检查后再操作
                    if not _is_win_alive():
                        return
                    _tk_safe(lambda: progress_var.set(90))
                    _tk_safe(lambda: status_var.set("预测完成,正在渲染结果..."))
                    _tk_safe(win.update)
                    _tk_safe(lambda: text.insert(tk.END, "\n📊 预测结果(AI输出)\n", "section"))
                    _tk_safe(lambda: text.insert(tk.END, "-" * 40 + "\n"))
                    _tk_safe(lambda: text.insert(tk.END, ai_text + "\n"))
                    _tk_safe(lambda: progress_var.set(100))
                    _tk_safe(lambda: status_var.set("预测完成"))

                    # ========== 解析AI返回文本 → 填充Treeview + 异步算心法分 ==========
                    def _fill_pred_tree():
                        if not _is_win_alive(): return
                        import re as _re_p
                        # 从 AI 文本提取股票代码(6位)
                        all_codes = _re_p.findall(r"\b(\d{6})\b", ai_text)
                        # 从文本推断预测方向和逻辑
                        tree_rows = []  # [(name, code, pred, logic_snippet), ...]
                        seen_codes = set()
                        lines = ai_text.splitlines()
                        for ln in lines:
                            for c in all_codes:
                                if c in ln and c not in seen_codes:
                                    seen_codes.add(c)
                                    # 从 ln 解析预测方向
                                    pred_dir = "震荡"
                                    if any(k in ln for k in ["涨", "↑", "📈", "看多", "上行", "突破", "涨停"]):
                                        pred_dir = "涨 ↑"
                                    elif any(k in ln for k in ["跌", "↓", "📉", "看空", "下行", "破位", "跌停"]):
                                        pred_dir = "跌 ↓"
                                    # 逻辑摘要: 截取 60 字
                                    logic_snip = ln.strip()
                                    if len(logic_snip) > 60:
                                        logic_snip = logic_snip[:57] + "..."
                                    # code_to_name 是 run_prediction 外层闭包变量, 直接访问
                                    nm = code_to_name.get(c, c)
                                    tree_rows.append((nm, c, pred_dir, logic_snip))
                        tree_rows = tree_rows[:20]

                        if tree_rows and _is_win_alive():
                            # 显示底部表格 (pack 在 main 里, top_pane 之后, 按钮栏之前)
                            _tk_safe(lambda: bottom_frame.pack(fill="x", padx=10, pady=(4, 0)))
                            for nm, c, pd, lg in tree_rows:
                                pred_tree.insert("", "end", values=(nm, c, pd, lg, "⏳计算中", "-"), tags=("mid",))

                            # 后台线程算心法分
                            def _bg_calc_hm():
                                for i, (nm, c, pd, lg) in enumerate(tree_rows):
                                    if not _is_win_alive(): break
                                    try:
                                        hm = self._hm_calc_for_stock(c)
                                        sc = hm.get("avg_score")
                                        best = hm.get("best_sch", "--")
                                        tag = "high" if sc and sc >= 65 else ("mid" if sc and sc >= 45 else "low")
                                        sc_txt = "-" if sc is None else f"{int(sc)}"
                                        def _upd(idx=i, _sc=sc_txt, _tg=tag, _bst=best):
                                            if not _is_win_alive(): return
                                            try:
                                                kids = pred_tree.get_children()
                                                if idx < len(kids):
                                                    pred_tree.item(kids[idx],
                                                        values=(nm, c, pd, lg, _sc, _bst), tags=(_tg,))
                                            except Exception:
                                                pass
                                        self.root.after(0, _upd)
                                    except Exception:
                                        pass
                                    time.sleep(0.3)
                            threading.Thread(target=_bg_calc_hm, daemon=True).start()
                    _tk_safe(_fill_pred_tree)
                except Exception:
                    import traceback
                    err_txt = f"\n预测过程中发生错误:\n{traceback.format_exc()}\n"
                    _tk_safe(lambda: text.insert(tk.END, err_txt, "negative"))
                    _tk_safe(lambda: status_var.set("预测失败"))
            # 底部按钮:开始预测 / 保存到资讯表 / 导出TXT / 导出Excel
            def save_to_news():
                content = text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showinfo("提示", "当前没有可保存的内容。", parent=win)
                    return
                tab_name = f"AI预测_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                if save_news_info_to_db(tab_name, content):
                    messagebox.showinfo("成功", f"已保存到资讯表,标题:{tab_name}", parent=win)
                else:
                    messagebox.showerror("错误", "保存到资讯表失败。", parent=win)
            def export_txt():
                content = text.get("1.0", tk.END)
                if not content.strip():
                    messagebox.showinfo("提示", "当前没有可导出的内容。", parent=win)
                    return
                from tkinter import filedialog
                filename = f"资讯AI预测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                filepath = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=filename)
                if filepath:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    messagebox.showinfo("成功", f"已导出到:\n{filepath}", parent=win)
            def export_excel():
                content = text.get("1.0", tk.END)
                if not content.strip():
                    messagebox.showinfo("提示", "当前没有可导出的内容。", parent=win)
                    return
                try:
                    import pandas as pd
                except Exception:
                    messagebox.showerror("错误", "当前环境未安装 pandas,无法导出为 Excel。", parent=win)
                    return
                from tkinter import filedialog
                filename = f"资讯AI预测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                filepath = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=filename)
                if filepath:
                    lines = [ln for ln in content.splitlines()]
                    df = pd.DataFrame({"预测结果": lines})
                    df.to_excel(filepath, index=False)
                    messagebox.showinfo("成功", f"已导出到:\n{filepath}", parent=win)
            bottom = ttk.Frame(main)
            bottom.pack(fill=tk.X, pady=(8, 0))
            ttk.Button(bottom, text="开始预测", command=lambda: threading.Thread(target=run_prediction, daemon=True).start()).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Button(bottom, text="保存到资讯表", command=save_to_news).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Button(bottom, text="导出TXT", command=export_txt).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Button(bottom, text="导出Excel", command=export_excel).pack(side=tk.LEFT, padx=(0, 8))
        except Exception as e:
            messagebox.showerror("错误", f"打开资讯AI分析窗口失败: {e}")

    def _breaking_news_gather_candidates(self, max_n: int):
        """问财/pywencai → OpenAPI → 东财涨速降级;返回 (candidates, source_note)。"""
        import re
        import shutil
        q_news = "今日A股突发新闻或重大公告涉及的个股,非ST"
        candidates = []
        note_parts = []
        if shutil.which("node"):
            try:
                import pywencai
                load_iwencai_env_from_dotfiles()
                _ck = (os.environ.get("IWENCAI_COOKIE") or os.environ.get("WENCAI_COOKIE") or "").strip()
                if not _ck:
                    # 问财挂起: 未配置 IWENCAI_COOKIE 时 pywencai 必 403,不再 retry 白等,直接降级后续数据源
                    note_parts.append("pywencai: 未设置 IWENCAI_COOKIE,链路已挂起")
                else:
                    _kw = {"query": q_news, "loop": True, "retry": 15, "sleep": 1}
                    _kw["cookie"] = _ck
                    df = pywencai.get(**_kw)
                    stocks = self._pywencai_df_to_elevator_stocks(df)
                    for s in stocks[: max_n * 2]:
                        code = s.get("code") or ""
                        if len(str(code)) != 6:
                            continue
                        candidates.append(
                            {
                                "code": str(code).zfill(6),
                                "name": str(s.get("name") or ""),
                                "snippet": "",
                                "raw": {},
                            }
                        )
                    if candidates:
                        note_parts.append("股票来源:问财 pywencai")
            except ImportError:
                note_parts.append("pywencai 未安装")
            except Exception as e:
                note_parts.append(f"pywencai: {e}")
                # pywencai 在 403/空返回时抛 'NoneType' object has no attribute 'get',探测真实 HTTP 状态
                try:
                    _ok, _probe_msg = self._probe_iwencai_access(q_news)
                    note_parts.append(_probe_msg)
                except Exception:
                    pass
        if not candidates:
            data, err = self._iwencai_query2data_dict(q_news, limit=str(max(30, max_n)))
            if data and isinstance(data, dict):
                datas = data.get("datas")
                if isinstance(datas, list) and datas:
                    candidates = self._stock_candidates_from_wencai_rows(datas)[: max_n * 2]
                    if candidates:
                        note_parts.append("股票来源:问财 OpenAPI query2data")
            elif err:
                note_parts.append(f"query2data: {err[:200]}")
        if not candidates and AKSHARE_AVAILABLE:
            try:
                import akshare as ak
                spot_df = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
                if spot_df is not None and not spot_df.empty:
                    spd_col = None
                    for c in spot_df.columns:
                        sc = str(c)
                        if "涨速" in sc or sc == "5分钟涨跌":
                            spd_col = c
                            break
                    if spd_col is None:
                        spd_col = "涨跌幅" if "涨跌幅" in spot_df.columns else spot_df.columns[-1]
                    code_col = "代码" if "代码" in spot_df.columns else spot_df.columns[0]
                    name_col = "名称" if "名称" in spot_df.columns else spot_df.columns[1]
                    sub = spot_df.copy()
                    try:
                        sub["_s"] = pd.to_numeric(sub[spd_col], errors="coerce")
                        sub = sub.sort_values("_s", ascending=False)
                    except Exception:
                        pass
                    for _, row in sub.head(max_n).iterrows():
                        raw = str(row.get(code_col, ""))
                        code = re.sub(r"\D", "", raw)
                        if len(code) >= 6:
                            code = code[-6:]
                        if len(code) != 6:
                            continue
                        candidates.append(
                            {
                                "code": code,
                                "name": str(row.get(name_col, "")),
                                "snippet": "(东财行情涨速/5分降级,非新闻匹配)",
                                "raw": {},
                            }
                        )
                    if candidates:
                        note_parts.append("股票来源:东财即时行情(问财不可用时的降级)")
            except Exception as e:
                note_parts.append(f"行情降级: {e}")
        # 去重保序
        seen = set()
        uniq = []
        for c in candidates:
            k = c["code"]
            if k in seen:
                continue
            seen.add(k)
            uniq.append(c)
            if len(uniq) >= max_n:
                break
        return uniq, ";".join(note_parts) if note_parts else "无来源说明"

    def show_breaking_news_dialog(self):
        """突发新闻:问财候选股 + 约 3 分钟涨幅扫描;异常拉升标出,可跳转 Skill/问财。"""
        import threading
        import urllib.parse
        import webbrowser
        win = self._safe_toplevel(self.root)
        win.title("突发新闻 · 3分钟异动")
        win.geometry("980x560")
        win.transient(self.root)
        top = ttk.Frame(win, padding=8)
        top.pack(fill=tk.X)
        status_var = tk.StringVar(value="就绪:点击「刷新扫描」")
        thresh_var = tk.StringVar(value="1.5")
        max_scan_var = tk.StringVar(value="35")
        only_spike = tk.BooleanVar(value=True)
        ttk.Label(top, text="异常阈值(%)≥").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(top, textvariable=thresh_var, width=6).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(top, text="最多扫描只数").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(top, textvariable=max_scan_var, width=5).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(top, text="仅显示异常拉升", variable=only_spike).pack(side=tk.LEFT, padx=(0, 12))
        def _open_wencai_web():
            q = "今日A股突发新闻或重大公告涉及的个股,非ST"
            webbrowser.open(
                "https://www.iwencai.com/unifiedwap/result?q=" + urllib.parse.quote(q)
            )
        ttk.Button(top, text="问财网页", command=_open_wencai_web).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top, text="Skill问财", command=self.show_iwencai_skillhub_dialog).pack(side=tk.LEFT, padx=(0, 6))
        mid = ttk.Frame(win, padding=(8, 0))
        mid.pack(fill=tk.BOTH, expand=True)
        cols = ("code", "name", "pct3", "news", "src")
        tree = ttk.Treeview(mid, columns=cols, show="headings", height=18)
        tree.heading("code", text="代码")
        tree.heading("name", text="名称")
        tree.heading("pct3", text="约3分涨跌%")
        tree.heading("news", text="新闻/问财摘要")
        tree.heading("src", text="来源说明")
        tree.column("code", width=72, anchor=tk.CENTER)
        tree.column("name", width=100, anchor=tk.W)
        tree.column("pct3", width=96, anchor=tk.E)
        tree.column("news", width=360, anchor=tk.W)
        tree.column("src", width=200, anchor=tk.W)
        scroll = ttk.Scrollbar(mid, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.tag_configure("spike", background="#ffe4b5")
        bottom = ttk.Frame(win, padding=8)
        bottom.pack(fill=tk.X)
        win._breaking_rows = []
        def _status(msg):
            win.after(0, lambda: status_var.set(msg))
        def _redraw_table():
            try:
                th = float((thresh_var.get() or "1.5").replace(",", "."))
            except Exception:
                th = 1.5
            only = only_spike.get()
            for iid in tree.get_children():
                tree.delete(iid)
            shown = 0
            for r in win._breaking_rows:
                pv = r.get("pct_val")
                spike = pv is not None and pv >= th
                if only and not spike:
                    continue
                pct_s = "--" if pv is None else f"{pv:.2f}"
                tags = ("spike",) if spike else ()
                tree.insert(
                    "",
                    tk.END,
                    values=(r["code"], r["name"], pct_s, r["news"], r.get("src_note") or ""),
                    tags=tags,
                )
                shown += 1
            status_var.set(
                f"显示 {shown}/{len(win._breaking_rows)} 条 · 阈值≥{th}% · "
                + ("仅异常" if only else "全部")
            )
        def _run_scan():
            try:
                nmax = int(max_scan_var.get().strip() or "35")
            except Exception:
                nmax = 35
            nmax = max(5, min(80, nmax))
            def work():
                _status("扫描问财/行情中...")
                cands, src_note = self._breaking_news_gather_candidates(nmax)
                try:
                    th = float((thresh_var.get() or "1.5").replace(",", "."))
                except Exception:
                    th = 1.5
                rows_out = []
                news_fetched = 0
                for i, c in enumerate(cands):
                    code = c["code"]
                    _status(f"分钟线 {i+1}/{len(cands)} {code} ...")
                    pct = self._compute_3min_pct_1m_em(code)
                    news = (c.get("snippet") or "").strip()
                    if (
                        not news
                        and AKSHARE_AVAILABLE
                        and news_fetched < 12
                        and pct is not None
                        and pct >= th
                    ):
                        try:
                            import akshare as ak
                            ndf = ak.stock_news_em(symbol=code)
                            if ndf is not None and not getattr(ndf, "empty", True):
                                title_col = None
                                for col in ndf.columns:
                                    if "标题" in str(col) or "新闻" in str(col):
                                        title_col = col
                                        break
                                if title_col is None and len(ndf.columns):
                                    title_col = ndf.columns[0]
                                if title_col is not None:
                                    news = str(ndf.iloc[0][title_col])[:120]
                                    news_fetched += 1
                        except Exception:
                            pass
                    rows_out.append(
                        {
                            "code": code,
                            "name": c.get("name") or "",
                            "pct_val": pct,
                            "news": news,
                            "src_note": src_note,
                        }
                    )
                def ui_done():
                    win._breaking_rows = rows_out
                    _redraw_table()
                win.after(0, ui_done)
            threading.Thread(target=work, daemon=True).start()
        ttk.Button(bottom, text="刷新扫描", command=_run_scan).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bottom, text="应用筛选", command=_redraw_table).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(bottom, textvariable=status_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _normalize_news_item_url(self, url):
        """将单元格中的链接规范为可打开的 http(s),否则返回 None。"""
        import math
        import re
        try:
            if url is None or (isinstance(url, float) and math.isnan(url)):
                return None
        except Exception:
            pass
        try:
            if pd.isna(url):
                return None
        except Exception:
            pass
        s = str(url).strip()
        if not s or s.lower() == "nan":
            return None
        if s.startswith("//"):
            s = "https:" + s
        elif re.match(r"^www\.", s, re.IGNORECASE):
            s = "https://" + s
        if s.startswith("http"):
            return s
        return None

    def _eastmoney_news_url_from_code(self, code) -> str | None:
        try:
            if code is None or pd.isna(code):
                return None
        except Exception:
            if code is None:
                return None
        c = str(code).strip()
        if not c or not c.isdigit():
            return None
        return f"http://finance.eastmoney.com/a/{c}.html"

    def _append_stock_news_em_rows(
        self, ak, news_items, seen_urls, keyword, line_prefix, max_rows=3
    ):
        """东财关键词新闻:行格式「  · [前缀] 标题」,url 单独绑定;seen_urls 按链接去重。"""
        try:
            ndf = ak.stock_news_em(symbol=keyword)
            if ndf is None or ndf.empty:
                return
            tcol, ucol = None, None
            for col in ndf.columns:
                sc = str(col)
                if tcol is None and ("标题" in sc or sc == "新闻标题"):
                    tcol = col
                if ucol is None and ("链接" in sc or sc.lower() == "url"):
                    ucol = col
            if tcol is None:
                tcol = ndf.columns[0]
            n = min(int(max_rows), len(ndf))
            for j in range(n):
                row = ndf.iloc[j]
                title = str(row[tcol])[:130]
                u = ""
                if ucol is not None and ucol in row.index:
                    try:
                        raw_u = row[ucol]
                        u = "" if pd.isna(raw_u) else str(raw_u).strip()
                    except Exception:
                        u = str(row[ucol] or "").strip()
                uu = self._normalize_news_item_url(u) if u else None
                if not uu:
                    uu = self._url_from_series_any_cell(row)
                if not uu:
                    for cand in ("code", "新闻编号", "编号", "article_id"):
                        if cand in row.index:
                            uu = self._eastmoney_news_url_from_code(row.get(cand))
                            if uu:
                                break
                if uu and uu in seen_urls:
                    continue
                if uu:
                    seen_urls.add(uu)
                news_items.append(
                    {"line": f"  · [{line_prefix}] {title}", "url": uu}
                )
        except Exception:
            pass

    def _rt_news_reapply_links(self, wgt):
        """弹窗统一调字号后会重配 Text;按存储的快讯行重打 rtn_* tag,恢复蓝字与点击打开。"""
        import webbrowser
        try:
            if not wgt.winfo_exists():
                return
        except Exception:
            return
        items = getattr(wgt, "_rt_news_items", None)
        if not items:
            return
        for name in list(wgt.tag_names()):
            if str(name).startswith("rtn_"):
                try:
                    wgt.tag_delete(name)
                except Exception:
                    pass
        anchor = "1.0"
        try:
            pos0 = wgt.search("══ 实时/隔夜相关快讯", "1.0", tk.END, regexp=False)
            if pos0:
                anchor = pos0
        except TypeError:
            pos0 = wgt.search("══ 实时/隔夜相关快讯", "1.0", tk.END)
            if pos0:
                anchor = pos0
        except Exception:
            pass
        pos = anchor
        for i, it in enumerate(items):
            line = ((it or {}).get("line", "") or "")
            url = self._normalize_news_item_url((it or {}).get("url"))
            if not url or not line:
                continue
            try:
                idx = wgt.search(line, pos, tk.END, regexp=False)
            except TypeError:
                idx = wgt.search(line, pos, tk.END)
            if not idx:
                try:
                    idx = wgt.search(line.strip(), anchor, tk.END, regexp=False)
                except TypeError:
                    idx = wgt.search(line.strip(), anchor, tk.END)
            if not idx:
                continue
            try:
                end = wgt.index(f"{idx}+{len(line)}c")
            except Exception:
                continue
            tag = f"rtn_{i}"
            wgt.tag_add(tag, idx, end)
            wgt.tag_configure(tag, foreground="#0B57D0", underline=True)
            def _op(_e, u=url):
                try:
                    webbrowser.open(u)
                except Exception:
                    pass
                return "break"
            wgt.tag_bind(tag, "<Button-1>", _op)
            wgt.tag_bind(tag, "<Enter>", lambda e, tw=wgt: tw.config(cursor="hand2"))
            wgt.tag_bind(tag, "<Leave>", lambda e, tw=wgt: tw.config(cursor="arrow"))
            pos = end

    def _fill_realtime_news_scrolledtext(self, wgt, head: str, news_items, tail: str):
        """快讯行:有 url 则整行可点,不在界面显示 http 地址。"""
        import webbrowser
        wgt._rt_news_items = tuple(news_items or ())
        wgt.delete("1.0", tk.END)
        wgt.insert("1.0", head or "")
        for i, it in enumerate(news_items or []):
            line = (it or {}).get("line", "") or ""
            url = self._normalize_news_item_url((it or {}).get("url"))
            m1, m2 = f"rt_ns_{i}", f"rt_ne_{i}"
            wgt.mark_set(m1, "insert")
            wgt.insert("insert", line)
            wgt.mark_set(m2, "insert")
            wgt.insert("insert", "\n")
            if url:
                tag = f"rtn_{i}"
                wgt.tag_add(tag, m1, m2)
                wgt.tag_configure(tag, foreground="#0B57D0", underline=True)
                def _op(_e, u=url):
                    try:
                        webbrowser.open(u)
                    except Exception:
                        pass
                    return "break"
                wgt.tag_bind(tag, "<Button-1>", _op)
                wgt.tag_bind(tag, "<Enter>", lambda e, tw=wgt: tw.config(cursor="hand2"))
                wgt.tag_bind(tag, "<Leave>", lambda e, tw=wgt: tw.config(cursor="arrow"))
        if tail:
            wgt.insert("insert", "\n" + tail)
        try:
            wgt.after(50, lambda w=wgt: self._rt_news_reapply_links(w))
            wgt.after(480, lambda w=wgt: self._rt_news_reapply_links(w))
        except Exception:
            pass

    def _show_realtime_news_ai_result_dialog(self, parent, content: str):
        """实时新闻 AI 分析结果 - 利多红色 / 利空绿色 / 字体大小按 impact 递减。"""
        import json
        import re
        w = self._toplevel(parent)
        w.title("实时新闻 · AI 分析(利多/利空分类)")
        w.geometry("1040x780")
        w.transient(parent)
        # ---- 解析 JSON ----
        items = []
        raw_text = (content or "").strip()
        # 先直接尝试
        try:
            items = json.loads(raw_text)
        except Exception:
            # 尝试找第一个 [ ... ] 片段
            m = re.search(r'\[.*\]', raw_text, re.DOTALL)
            if m:
                try:
                    items = json.loads(m.group())
                except Exception:
                    pass
        if not isinstance(items, list) or not items:
            # JSON 解析失败 → 降级为纯文本显示
            hdr = ttk.Frame(w, padding=8)
            hdr.pack(fill=tk.X)
            ttk.Label(hdr, text="⚠️ AI 返回格式异常(非 JSON),原始内容如下:",
                      foreground="orange").pack(side=tk.LEFT)
            ttk.Button(hdr, text="关闭", width=8, command=w.destroy).pack(side=tk.RIGHT)
            txt = scrolledtext.ScrolledText(w, wrap=tk.WORD, font=("Microsoft YaHei", 11))
            txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
            txt.insert("1.0", content or "")
            txt.focus_set()
            return
        # ---- 数据清洗 ----
        cleaned = []
        for it in items:
            if not isinstance(it, dict):
                continue
            d = str(it.get("direction", "neutral")).lower()
            if "bull" in d or "利好" in d or "利多" in d:
                direction = "bullish"
            elif "bear" in d or "利空" in d or "利空" in d:
                direction = "bearish"
            else:
                direction = "neutral"
            try:
                impact = int(it.get("impact", 1))
            except Exception:
                impact = 1
            impact = max(1, min(3, impact))
            # 兼容新旧字段名:sectors / tickers
            sectors_raw = it.get("sectors") or it.get("tickers") or []
            if not isinstance(sectors_raw, list):
                sectors_raw = []
            # AI 返回的 leaders,或从 sectors 里的板块名做 fallback 匹配
            leaders_raw = it.get("leaders", [])
            if not isinstance(leaders_raw, list):
                leaders_raw = []
            # 如果 AI 没给 leaders,从 sectors 板块名查静态字典
            if not leaders_raw:
                _fallback = []
                for sec in sectors_raw:
                    if isinstance(sec, (list, tuple)) and len(sec) >= 1:
                        _name = str(sec[0])
                        _fallback.extend(self._lookup_sector_leaders(_name))
                    elif isinstance(sec, str):
                        _fallback.extend(self._lookup_sector_leaders(sec))
                # 去重
                _seen = set()
                _dedup = []
                for l in _fallback:
                    _key = l[1] if len(l) >= 2 else l[0]
                    if _key not in _seen:
                        _seen.add(_key)
                        _dedup.append(l)
                leaders_raw = _dedup[:4]
            cleaned.append({
                "time": str(it.get("time", "")),
                "title": str(it.get("title", "")),
                "sectors": sectors_raw,
                "leaders": leaders_raw,
                "dimension": str(it.get("dimension", "")),
                "impact": impact,
                "direction": direction,
            })
        # 分类 + 排序(impact 从大到小)
        bullish = sorted([x for x in cleaned if x["direction"] == "bullish"], key=lambda x: -x["impact"])
        bearish = sorted([x for x in cleaned if x["direction"] == "bearish"], key=lambda x: -x["impact"])
        neutral = sorted([x for x in cleaned if x["direction"] == "neutral"], key=lambda x: -x["impact"])
        # ---- 头栏 ----
        hdr = ttk.Frame(w, padding=8)
        hdr.pack(fill=tk.X)
        ttk.Label(hdr, text=f"📊 AI 新闻分析  |  利多={len(bullish)}  利空={len(bearish)}  中性={len(neutral)}",
                  font=("Microsoft YaHei", 12, "bold")).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(hdr, text="关闭", width=8, command=w.destroy).pack(side=tk.RIGHT)
        # ---- Text 控件(支持 tag 颜色/字体)----
        txt = tk.Text(w, wrap=tk.WORD, font=("Microsoft YaHei", 11),
                      bg="#1e1e1e", fg="#cccccc", padx=10, pady=8)
        vsb = ttk.Scrollbar(w, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=(0, 8))
        # 定义 tag 样式 - A股惯例:红涨绿跌
        # 利多 = 红色,利空 = 绿色
        _BULL_COLOR = "#E53935"   # 利多红
        _BEAR_COLOR = "#2E7D32"   # 利空绿
        _DIM_LABEL = "#9E9E9E"    # 灰色标签
        _NEUTRAL_COLOR = "#FFA726"
        for impact in [3, 2, 1]:
            fsize = {3: 16, 2: 14, 1: 12}[impact]
            txt.tag_configure(f"bullish_{impact}", foreground=_BULL_COLOR,
                              font=("Microsoft YaHei", fsize, "bold"))
            txt.tag_configure(f"bearish_{impact}", foreground=_BEAR_COLOR,
                              font=("Microsoft YaHei", fsize, "bold"))
            txt.tag_configure(f"neutral_{impact}", foreground=_NEUTRAL_COLOR,
                              font=("Microsoft YaHei", fsize, "bold"))
        txt.tag_configure("dim", foreground=_DIM_LABEL, font=("Microsoft YaHei", 9))
        txt.tag_configure("leaders", foreground="#FFD54F", font=("Microsoft YaHei", 10, "bold"))
        txt.tag_configure("header_bull", foreground=_BULL_COLOR,
                          font=("Microsoft YaHei", 14, "bold"))
        txt.tag_configure("header_bear", foreground=_BEAR_COLOR,
                          font=("Microsoft YaHei", 14, "bold"))
        txt.tag_configure("header_neu", foreground=_NEUTRAL_COLOR,
                          font=("Microsoft YaHei", 14, "bold"))
        txt.tag_configure("sep", foreground="#424242")
        def _format_item(it, prefix):
            """往 txt 里插一条新闻"""
            impact = it["impact"]
            direction = it["direction"]
            tag_map = {
                "bullish": f"bullish_{impact}",
                "bearish": f"bearish_{impact}",
                "neutral": f"neutral_{impact}",
            }
            tag = tag_map[direction]
            stars = "★" * impact + "☆" * (3 - impact)
            # 标题行
            header = f"{stars}  {it['title']}\n"
            txt.insert(tk.END, header, tag)
            # 详情行:时间 + 维度 + 板块
            _t_time = f"[{it['time']}] " if it['time'] else ""
            _t_dim = f"{it['dimension']}  " if it['dimension'] else ""
            # 板块列表(优先 sectors,兼容 tickers)
            _sectors = it.get("sectors") or it.get("tickers") or []
            _sec_txt = ""
            if _sectors:
                parts = []
                for t in _sectors[:5]:
                    if isinstance(t, (list, tuple)) and len(t) >= 2:
                        parts.append(f"{t[0]}")
                    elif isinstance(t, str):
                        parts.append(t)
                _sec_txt = "  📦 板块: " + ", ".join(parts)
            detail = f"  {_t_time}{_t_dim}{_sec_txt}\n"
            txt.insert(tk.END, detail, "dim")
            # 龙头股行(黄色加粗)
            leaders = it.get("leaders", [])
            if leaders:
                lparts = []
                for l in leaders[:4]:
                    if isinstance(l, (list, tuple)) and len(l) >= 2:
                        lparts.append(f"{l[0]}({l[1]})")
                    elif isinstance(l, str):
                        lparts.append(l)
                leader_line = f"  🐉 龙头: {', '.join(lparts)}\n"
                txt.insert(tk.END, leader_line, "leaders")
            txt.insert(tk.END, "\n", "dim")
        # ---- 利多板块 ----
        txt.insert(tk.END, "=" * 56 + "\n", "sep")
        txt.insert(tk.END, f"  📈 利好多头({len(bullish)}条)\n", "header_bull")
        txt.insert(tk.END, "=" * 56 + "\n\n", "sep")
        if bullish:
            for it in bullish:
                _format_item(it, "bull")
        else:
            txt.insert(tk.END, "  (暂无利多新闻)\n\n", "dim")
        # ---- 利空板块 ----
        txt.insert(tk.END, "\n" + "=" * 56 + "\n", "sep")
        txt.insert(tk.END, f"  📉 利空空头({len(bearish)}条)\n", "header_bear")
        txt.insert(tk.END, "=" * 56 + "\n\n", "sep")
        if bearish:
            for it in bearish:
                _format_item(it, "bear")
        else:
            txt.insert(tk.END, "  (暂无利空新闻)\n\n", "dim")
        # ---- 中性板块 ----
        if neutral:
            txt.insert(tk.END, "\n" + "=" * 56 + "\n", "sep")
            txt.insert(tk.END, f"  ⚖️ 中性({len(neutral)}条)\n", "header_neu")
            txt.insert(tk.END, "=" * 56 + "\n\n", "sep")
            for it in neutral:
                _format_item(it, "neu")
        txt.see("1.0")
        txt.focus_set()

    def show_realtime_world_news_dialog(self):
        """实时新闻:隔夜世界快讯、美股收盘与分类涨跌、中概、A股参考与问财指引。"""
        import threading
        import urllib.parse
        import webbrowser
        win = self._safe_toplevel(self.root)
        win.title("实时新闻 · 隔夜外围与美股")
        win.geometry("960x720")
        win.transient(self.root)
        top = ttk.Frame(win, padding=8)
        top.pack(fill=tk.X)
        status_var = tk.StringVar(value="就绪")
        _ai_busy = [False]
        def _open_wencai(q: str):
            webbrowser.open("https://www.iwencai.com/unifiedwap/result?q=" + urllib.parse.quote(q))
        def _ai_analyze():
            if _ai_busy[0]:
                return
            raw = body.get("1.0", "end-1c").strip()
            if not raw or len(raw) < 80:
                messagebox.showwarning(
                    "提示",
                    "请先等待新闻加载完成,或内容过短无法分析。",
                    parent=win,
                )
                return
            if "正在汇总" in raw[:300] or raw.startswith("汇总失败"):
                messagebox.showwarning(
                    "提示",
                    "请先等待新闻加载完成后再试。",
                    parent=win,
                )
                return
            _ai_busy[0] = True
            status_var.set("AI 分析中...")
            _ai_state = {"done": False, "result": None}
            def work():
                try:
                    _user_p = self._build_news_analysis_prompt(raw)
                    _system_p = (
                        "你是资深证券分析师。严格按用户要求的格式输出。"
                        "新闻前必须有具体时间戳;每条关联股票必须有三维标签(维度/力度/方向)。"
                    )
                    _ai_state["result"] = self.call_ai_model(
                        _user_p,
                        _system_p,
                        max_tokens=4096,
                    )
                except Exception as e:
                    _ai_state["result"] = f"分析过程异常:{e}"
                _ai_state["done"] = True
            def _poll_ai_ui():
                if not win.winfo_exists():
                    _ai_busy[0] = False
                    return
                if not _ai_state["done"]:
                    win.after(50, _poll_ai_ui)
                    return
                _ai_busy[0] = False
                status_var.set("AI 分析完成 " + datetime.now().strftime("%H:%M:%S"))
                self._show_realtime_news_ai_result_dialog(win, _ai_state["result"])
            threading.Thread(target=work, daemon=True).start()
            win.after(50, _poll_ai_ui)
        ttk.Button(top, text="刷新", width=8, command=lambda: _refresh()).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top, text="AI分析", width=10, command=_ai_analyze).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            top,
            text="Skill问财",
            width=10,
            command=self.show_iwencai_skillhub_dialog,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            top,
            text="问财·板块龙头",
            width=14,
            command=lambda: _open_wencai("今日主力资金净流入前10的行业板块,每个板块涨幅第一的非ST股票"),
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            top,
            text="问财·半导体",
            width=12,
            command=lambda: _open_wencai("半导体概念,今日涨跌幅排名,前8名,非ST"),
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(top, textvariable=status_var, font=("TkDefaultFont", 9)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        body = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Microsoft YaHei", 11))
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        def _refresh():
            status_var.set("拉取中...")
            body.delete("1.0", tk.END)
            body.insert("1.0", "正在汇总美股指数、分类、中概与新闻,请稍候...")
            _rf_state = {"done": False, "ok": False, "payload": None, "err": None}
            def work():
                try:
                    _rf_state["payload"] = self._collect_realtime_world_us_snapshot_bundle()
                    _rf_state["ok"] = True
                except Exception as e:
                    _rf_state["err"] = e
                    _rf_state["ok"] = False
                _rf_state["done"] = True
            def _poll_refresh_ui():
                if not win.winfo_exists():
                    return
                if not _rf_state["done"]:
                    win.after(50, _poll_refresh_ui)
                    return
                if _rf_state["ok"]:
                    h, items, t = _rf_state["payload"]
                    try:
                        self._fill_realtime_news_scrolledtext(body, h, items, t)
                    except Exception:
                        body.delete("1.0", tk.END)
                        body.insert("1.0", h + "\n".join(x.get("line", "") for x in items) + "\n\n" + t)
                    status_var.set("已更新 " + datetime.now().strftime("%H:%M:%S"))
                else:
                    e = _rf_state["err"]
                    body.delete("1.0", tk.END)
                    body.insert("1.0", f"汇总失败:{e}")
                    status_var.set("失败")
            threading.Thread(target=work, daemon=True).start()
            win.after(50, _poll_refresh_ui)
        _refresh()

    def save_current_tab_to_news_db(self):
        """保存当前标签页到资讯DB(左侧标签页)"""
        try:
            # 获取当前活动的标签页
            current_tab_id = self.text_notebook.select()
            if not current_tab_id:
                messagebox.showwarning("警告", "没有活动的标签页")
                return
            # 获取标签页信息
            self.text_notebook.index(current_tab_id)
            tab_title = self.text_notebook.tab(current_tab_id, "text")
            # 获取标签页对应的文本框
            tab_frame = self.text_notebook.nametowidget(current_tab_id)
            text_widget = None
            for widget in tab_frame.winfo_children():
                if isinstance(widget, tk.Text):
                    text_widget = widget
                    break
            if not text_widget:
                messagebox.showwarning("警告", "无法找到文本框")
                return
            # 获取内容
            content = text_widget.get("1.0", tk.END).strip()
            if not content:
                messagebox.showwarning("警告", "标签页内容为空")
                return
            # 检查是否是词云标签页,如果是,添加词云图片和链接
            if tab_title == "词云" or "词云" in tab_title:
                # 检查是否有词云图片
                wordcloud_path = "wordcloud.png"
                if os.path.exists(wordcloud_path):
                    # 创建词云图片的保存路径(带时间戳)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    wordcloud_save_dir = "wordclouds"
                    if not os.path.exists(wordcloud_save_dir):
                        os.makedirs(wordcloud_save_dir)
                    wordcloud_save_path = os.path.join(wordcloud_save_dir, f"wordcloud_{timestamp}.png")
                    shutil.copy(wordcloud_path, wordcloud_save_path)
                    # 在内容中添加词云图片链接
                    wordcloud_link = f"\n\n[词云图片]\n文件路径: {os.path.abspath(wordcloud_save_path)}\n图片链接: file:///{os.path.abspath(wordcloud_save_path).replace(os.sep, '/')}\n"
                    content += wordcloud_link
            # 保存到数据库
            if save_news_info_to_db(tab_title, content):
                messagebox.showinfo("成功", f"已保存标签页 '{tab_title}' 到资讯数据库")
                # 如果是警世通言记录,更新最近记录显示
                if tab_title.startswith("警示") and hasattr(self, 'update_warning_recent_records'):
                    try:
                        self.update_warning_recent_records()
                    except Exception as e:
                        print(f"更新警世通言最近记录显示失败: {e}")
            else:
                messagebox.showerror("错误", "保存失败")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def save_current_result_tab_to_news_db(self):
        """保存当前结果标签页到资讯DB(右侧标签页)"""
        try:
            # 获取当前活动的结果标签页
            result_widget = self.get_active_result_widget()
            if not result_widget:
                messagebox.showwarning("警告", "没有活动的结果标签页")
                return
            # 获取标签页标题
            try:
                selected_tab = self.result_notebook.select()
                if selected_tab:
                    for tab_info in self.result_tabs.values():
                        if str(tab_info['frame']) == selected_tab:
                            tab_title = tab_info.get('title', '分析结果')
                            break
                    else:
                        tab_title = "分析结果"
                else:
                    tab_title = "分析结果"
            except:
                tab_title = "分析结果"
            # 获取内容
            content = result_widget.get("1.0", tk.END).strip()
            if not content:
                messagebox.showwarning("警告", "结果标签页内容为空")
                return
            # 总是检查并添加词云图片(如果存在)
            wordcloud_path = "wordcloud.png"
            if os.path.exists(wordcloud_path):
                # 创建词云图片的保存路径(带时间戳)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                wordcloud_save_dir = "wordclouds"
                if not os.path.exists(wordcloud_save_dir):
                    os.makedirs(wordcloud_save_dir)
                wordcloud_save_path = os.path.join(wordcloud_save_dir, f"wordcloud_{timestamp}.png")
                shutil.copy(wordcloud_path, wordcloud_save_path)
                # 在内容中添加词云图片链接
                wordcloud_link = f"\n\n[词云图片]\n文件路径: {os.path.abspath(wordcloud_save_path)}\n图片链接: file:///{os.path.abspath(wordcloud_save_path).replace(os.sep, '/')}\n"
                content += wordcloud_link
            # 保存到数据库
            if save_news_info_to_db(tab_title, content):
                messagebox.showinfo("成功", f"已保存结果标签页 '{tab_title}' 到资讯数据库")
            else:
                messagebox.showerror("错误", "保存失败")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def _refresh_main_from_news(self, silent=False, run_hold_checks=False):
        """Main 标签页:资讯表最近 5 日合并正文中的股票,按资讯内出现频次从高到低填入 holding_stocks_4。"""
        from tkinter import messagebox
        news_meta = {}
        stocks = get_news_stocks_merged_recent_days(ndays=5, meta=news_meta)
        if not stocks:
            reason = news_meta.get("reason")
            if not silent:
                if reason == "db_error":
                    msg = (
                        f"读取资讯表失败:{news_meta.get('error', '')}\n\n"
                        f"数据库:{DB_PATH}"
                    )
                elif reason == "no_stock_dict":
                    msg = "未能加载「股票代码-名称」对照表,无法从资讯正文识别六位代码。请检查网络或本地缓存后重试。"
                elif reason == "no_rows":
                    msg = (
                        "资讯表(news_info)里目前没有记录。\n\n"
                        "请先使用「一键资讯」「批量爬取资讯」或各爬虫将内容保存进股票资讯表。"
                    )
                elif reason == "no_valid_dates":
                    msg = news_meta.get("hint") or "资讯记录无法按日期归类(created_at 异常)。"
                else:
                    msg = news_meta.get("hint") or "资讯表中暂无有效 A 股代码,请先保存含六位代码的资讯。"
                try:
                    messagebox.showinfo("Main · 从资讯刷新", msg, parent=self.root)
                except Exception:
                    pass
            return
        holding_stocks, _holding_labels, _holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(4)
        for j in range(80):
            holding_stocks[j] = stocks[j] if j < len(stocks) else None
        for j in range(20):
            self._update_holding_label(j, check_conditions=False, group_index=4, fetch_daily_change=False)
        try:
            self._save_holdings_to_config(4)
        except Exception as e:
            print(f"保存 Main 持仓到配置失败: {e}")
        # 刷新持仓后检查买入信号
        try:
            self._check_buy_signal()
        except Exception as e:
            print(f"检查买入信号失败: {e}")
        if not silent:
            try:
                n = len(stocks)
                dm = news_meta.get("merged_dates_ymd") or []
                days_note = f"合并最近 {len(dm)} 个有资讯的日期" if dm else "最近5日资讯"
                messagebox.showinfo(
                    "Main · 从资讯刷新",
                    f"已按资讯频次填入 {n} 只股票({days_note},高→低)。",
                    parent=self.root,
                )
            except Exception:
                pass
        if run_hold_checks:
            try:
                self._run_holding_checks_for_news_tabs(include_main=True, include_date_tabs=True)
            except Exception as e:
                print(f"Main 资讯刷新后触发持仓检测失败: {e}")

    def _refresh_leader_from_news(self, silent=False):
        """龙头股标签页:资讯表最近10日合并正文中的股票,按提及频次(词频)高→低填入。"""
        from tkinter import messagebox
        news_meta = {}
        stocks = get_news_stocks_merged_recent_days(ndays=10, meta=news_meta)
        if not stocks:
            if not silent:
                reason = news_meta.get("reason")
                if reason == "db_error":
                    msg = f"读取资讯表失败:{news_meta.get('error', '')}\n\n数据库:{DB_PATH}"
                elif reason == "no_rows":
                    msg = "资讯表(news_info)暂无记录,请先执行一键资讯/爬取并保存。"
                else:
                    msg = news_meta.get("hint") or "最近10日资讯里未识别到可用股票代码。"
                try:
                    messagebox.showinfo("龙头股 · 资讯股", msg, parent=self.root)
                except Exception:
                    pass
            return
        holding_stocks, _holding_labels, _holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(2)
        for j in range(80):
            holding_stocks[j] = stocks[j] if j < len(stocks) else None
        for j in range(20):
            self._update_holding_label(j, check_conditions=False, group_index=2, fetch_daily_change=False)
        try:
            self._save_holdings_to_config(2)
        except Exception as e:
            print(f"保存 龙头股(资讯股) 到配置失败: {e}")
        if not silent:
            try:
                messagebox.showinfo(
                    "龙头股 · 资讯股",
                    f"已按最近10日资讯词频导入 {len(stocks)} 只股票(提及最多→最少)。",
                    parent=self.root,
                )
            except Exception:
                pass

    def _auto_save_tab_to_news(self, tab_id):
        """自动保存指定标签页到资讯"""
        try:
            # 切换到该标签页
            if hasattr(self, 'text_notebook') and tab_id:
                try:
                    self.text_notebook.select(tab_id)
                except:
                    pass
            # 调用保存到资讯
            self.save_current_tab_to_news_db()
        except Exception as e:
            print(f"[自动保存到资讯] 失败: {e}")

    def _build_news_analysis_prompt(self, raw_text):
        """构建实时新闻 AI 分析 prompt - 要求输出结构化 JSON(含板块龙头)"""
        return (
            "你是资深证券分析师。请阅读以下实时新闻,提取每条重要新闻并输出严格的 JSON 数组。\n\n"
            "JSON 格式(必须严格遵守,否则无法解析):\n"
            "[\n"
            "  {\n"
            "    \"time\": \"08:30\",\n"
            "    \"title\": \"新闻标题\",\n"
            "    \"sectors\": [[\"白酒\", \"BK0477\"], [\"消费\", \"BK0456\"]],\n"
            "    \"leaders\": [[\"贵州茅台\", \"600519\"], [\"五粮液\", \"000858\"], [\"泸州老窖\", \"000568\"]],\n"
            "    \"dimension\": \"政策面\",\n"
            "    \"impact\": 3,\n"
            "    \"direction\": \"bullish\"\n"
            "  }\n"
            "]\n\n"
            "字段说明:\n"
            "- time: 新闻发布时间(HH:MM 或完整 datetime)\n"
            "- title: 新闻标题(100字内,去重复)\n"
            "- sectors: 直接受影响的板块列表 [板块名, 板块代码BKxxxx],1-5个\n"
            "- leaders: 该板块的龙头股 2-4 只 [股票名, 6位代码],优先一线龙头\n"
            "- dimension: 政策面/基本面/技术面/资金面/情绪面(选最主要一个)\n"
            "- impact: 1/2/3(1=弱★ 2=中★★ 3=强★★★)\n"
            "- direction: bullish(利多利好)/ bearish(利空)/ neutral(中性)\n\n"
            "重要规则:\n"
            "1. 只输出 JSON,不要 markdown code fence(不要 ```json)\n"
            "2. 按 impact 从大到小排序\n"
            "3. leaders 必须列真实存在的股票,优先一线龙头(如白酒→茅台/五粮液/泸州老窖)\n"
            "4. 如果新闻影响某大板块,leaders 列出该板块 2-4 只最具代表性的龙头\n"
            "5. 新闻快照 ===\n" + raw_text[:120000]
        )


__all__ = ["NewsMixin"]
