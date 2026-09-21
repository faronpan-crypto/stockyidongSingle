"""截图/OCR/剪贴板/Chrome 检测"""
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
import json
import os
import sys
import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class ScreenshotMixin:
    """截图/OCR/剪贴板/Chrome 检测"""

    def one_click_screenshot(self):
        """一键截图:对选中的爬取按钮进行打开网页并截图"""
        try:
            # 检查selenium是否可用
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                from selenium.webdriver.chrome.service import Service
            except ImportError:
                messagebox.showerror("错误", "selenium未安装,无法使用截图功能\n\n请运行: pip install selenium")
                return
            # 获取选中的爬取项
            selected_crawlers = []
            crawler_info = {
                'taoguba': {'name': '爬取淘股吧', 'url': 'https://www.taoguba.com.cn/'},
                'jiuyan': {'name': '爬取韭研', 'url': 'https://www.jiuyangongshe.com/'},
                'eastmoney': {'name': '爬取东方财富', 'url': 'https://www.eastmoney.com/'},
                'xueqiu': {'name': '爬取雪球', 'url': 'https://xueqiu.com/'},
                'xuangubao': {'name': '爬取选股宝', 'url': 'https://xuangubao.cn/'},
                'ths': {'name': '爬取同花顺', 'url': 'https://www.10jqka.com.cn/'}
            }
            for key, info in crawler_info.items():
                if key in self.crawler_checkboxes and self.crawler_checkboxes[key].get():
                    selected_crawlers.append((key, info['name'], info['url']))
            # 获取选中的市场导航项
            if hasattr(self, 'market_nav_checkboxes') and self.market_nav_checkboxes:
                for checkbox_key, checkbox_info in self.market_nav_checkboxes.items():
                    if checkbox_info['var'].get():
                        name = checkbox_info['name']
                        url = checkbox_info.get('url', '').strip() if checkbox_info.get('url') else ''
                        # 确保URL不为空且有效
                        if url and (url.startswith(('http://', 'https://')) or '.' in url):
                            # 如果URL没有协议前缀,添加https://
                            if not url.startswith(('http://', 'https://')):
                                url = 'https://' + url
                            selected_crawlers.append((checkbox_key, name, url))
                        elif url:
                            # URL格式可能有问题,但仍然尝试添加
                            if not url.startswith(('http://', 'https://')):
                                url = 'https://' + url
                            selected_crawlers.append((checkbox_key, name, url))
            if not selected_crawlers:
                messagebox.showwarning("提示", "请至少选择一个爬取项或市场导航项进行截图")
                return
            # 选择保存目录
            save_dir = filedialog.askdirectory(
                title="选择截图保存目录",
                initialdir=self.screenshot_save_dir
            )
            if not save_dir:
                return
            self.screenshot_save_dir = save_dir
            # 在新线程中执行截图
            thread = threading.Thread(target=self._screenshot_thread, args=(selected_crawlers, save_dir), daemon=True)
            thread.start()
        except Exception as e:
            messagebox.showerror("错误", f"一键截图失败: {e!s}")
            import traceback
            traceback.print_exc()

    def _screenshot_thread(self, selected_crawlers, save_dir):
        """截图线程"""
        driver = None
        try:
            # 自动检测Chrome路径
            chrome_path = self._auto_detect_chrome()
            if not chrome_path:
                # 提供更详细的错误信息和解决方案,允许用户手动选择
                error_msg = (
                    "未找到Chrome浏览器!\n\n"
                    "解决方案:\n"
                    "1. 安装Google Chrome浏览器\n"
                    "   下载地址: https://www.google.com/chrome/\n\n"
                    "2. 或者手动指定Chrome路径\n"
                    "   点击'是'将打开文件选择对话框,请选择chrome.exe文件\n\n"
                    "3. 安装ChromeDriver(如果需要)\n"
                    "   如果已安装Chrome但仍无法使用,可能需要安装ChromeDriver\n"
                    "   下载地址: https://chromedriver.chromium.org/\n\n"
                    "注意:新版本的Selenium可能自动管理ChromeDriver,"
                    "如果遇到问题,请确保Chrome浏览器已正确安装。"
                )
                # 询问用户是否要手动选择Chrome路径
                result = messagebox.askyesno("未找到Chrome浏览器", error_msg + "\n\n是否现在手动选择Chrome路径?")
                if result:
                    # 打开文件选择对话框
                    chrome_path = filedialog.askopenfilename(
                        title="选择Chrome浏览器",
                        filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")],
                        initialfile="chrome.exe"
                    )
                    if chrome_path and os.path.exists(chrome_path):
                        # 保存配置
                        self._save_chrome_config(chrome_path)
                        # 继续使用选择的路径
                    else:
                        return
                else:
                    return
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            # 尝试使用webdriver-manager自动管理ChromeDriver
            try:
                from selenium.webdriver.chrome.service import Service as ChromeService
                from webdriver_manager.chrome import ChromeDriverManager
                WEBDRIVER_MANAGER_AVAILABLE = True
            except ImportError:
                WEBDRIVER_MANAGER_AVAILABLE = False
            # 配置Chrome选项
            options = Options()
            options.binary_location = chrome_path
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--start-maximized')
            # 创建WebDriver
            driver_created = False
            last_error = None
            # 方法1: 尝试使用webdriver-manager(如果可用)
            if WEBDRIVER_MANAGER_AVAILABLE:
                try:
                    service = ChromeService(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=options)
                    driver_created = True
                except Exception as e:
                    last_error = str(e)
            # 方法2: 尝试使用默认Service
            if not driver_created:
                try:
                    service = Service()
                    driver = webdriver.Chrome(service=service, options=options)
                    driver_created = True
                except Exception as e:
                    last_error = str(e)
            # 方法3: 尝试不使用Service(让Selenium自动查找)
            if not driver_created:
                try:
                    driver = webdriver.Chrome(options=options)
                    driver_created = True
                except Exception as e:
                    last_error = str(e)
            if not driver_created:
                error_msg = (
                    f"无法启动Chrome浏览器!\n\n"
                    f"错误信息: {last_error}\n\n"
                    f"解决方案:\n"
                    f"1. 确保已安装Google Chrome浏览器\n"
                    f"   下载地址: https://www.google.com/chrome/\n\n"
                    f"2. 安装ChromeDriver(如果需要)\n"
                    f"   方法A: 安装webdriver-manager自动管理\n"
                    f"   pip install webdriver-manager\n\n"
                    f"   方法B: 手动下载ChromeDriver\n"
                    f"   下载地址: https://chromedriver.chromium.org/\n"
                    f"   确保ChromeDriver版本与Chrome浏览器版本匹配\n\n"
                    f"3. 检查Chrome路径是否正确\n"
                    f"   当前检测到的路径: {chrome_path}\n\n"
                    f"4. 如果问题仍然存在,请检查防火墙或杀毒软件是否阻止了Chrome"
                )
                self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
                return
            # 逐个截图
            saved_files = []
            for idx, (key, name, url) in enumerate(selected_crawlers, 1):
                try:
                    self.root.after(0, lambda n=name, i=idx, t=len(selected_crawlers):
                        self.ocr_tab_widget.insert(tk.END, f"[{i}/{t}] 正在截图 {n}...\n"))
                    self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                    # 验证URL
                    if not url or not isinstance(url, str) or not url.strip():
                        error_msg = f"无效的URL: {name} (URL为空或格式错误)"
                        self.root.after(0, lambda msg=error_msg:
                            self.ocr_tab_widget.insert(tk.END, f"错误: {msg}\n"))
                        self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                        continue
                    # 确保URL以http://或https://开头
                    url = url.strip()
                    if not url.startswith(('http://', 'https://')):
                        # 尝试添加https://前缀
                        url = 'https://' + url
                    # 打开网页
                    try:
                        driver.get(url)
                        time.sleep(3)  # 等待页面加载
                    except Exception as url_error:
                        error_msg = f"无法打开网页 {name}: {url_error!s}\nURL: {url}"
                        self.root.after(0, lambda msg=error_msg:
                            self.ocr_tab_widget.insert(tk.END, f"错误: {msg}\n"))
                        self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                        continue
                    # 显示等待认证对话框(非阻塞)
                    wait_dialog = None
                    auth_ready = threading.Event()
                    def show_auth_dialog():
                        nonlocal wait_dialog
                        wait_dialog = self._safe_toplevel(self.root)
                        wait_dialog.title("等待认证")
                        wait_dialog.geometry("450x200")
                        wait_dialog.transient(self.root)
                        wait_dialog.attributes('-topmost', True)
                        ttk.Label(
                            wait_dialog,
                            text=f"正在截图:{name}",
                            font=("TkDefaultFont", 11, "bold")
                        ).pack(pady=(15, 5))
                        ttk.Label(
                            wait_dialog,
                            text="如果网站需要认证,请在浏览器中完成认证",
                            font=("TkDefaultFont", 11)
                        ).pack(pady=5)
                        ttk.Label(
                            wait_dialog,
                            text="完成后点击'已认证'按钮继续截图",
                            font=("TkDefaultFont", 11),
                            foreground="blue"
                        ).pack(pady=5)
                        button_frame = ttk.Frame(wait_dialog)
                        button_frame.pack(pady=15)
                        def on_auth_ready():
                            auth_ready.set()
                            if wait_dialog and wait_dialog.winfo_exists():
                                wait_dialog.destroy()
                        def on_skip_auth():
                            auth_ready.set()
                            if wait_dialog and wait_dialog.winfo_exists():
                                wait_dialog.destroy()
                        ttk.Button(
                            button_frame,
                            text="已认证,继续",
                            command=on_auth_ready,
                            width=15
                        ).pack(side=tk.LEFT, padx=5)
                        ttk.Button(
                            button_frame,
                            text="跳过(无需认证)",
                            command=on_skip_auth,
                            width=15
                        ).pack(side=tk.LEFT, padx=5)
                        # 自动关闭提示
                        ttk.Label(
                            wait_dialog,
                            text="(5分钟后自动继续)",
                            font=("TkDefaultFont", 8),
                            foreground="gray"
                        ).pack(pady=(5, 0))
                    # 在主线程中显示对话框
                    self.root.after(0, show_auth_dialog)
                    # 等待用户操作或超时(最多5分钟=300秒)
                    auth_ready.wait(timeout=300)
                    # 关闭对话框(如果还在显示)
                    if wait_dialog and wait_dialog.winfo_exists():
                        self.root.after(0, wait_dialog.destroy)
                    # 再等待2秒,确保页面加载完成
                    time.sleep(2)
                    # 获取全页面尺寸(使用JavaScript)
                    try:
                        # 获取页面总宽度和高度
                        total_width = driver.execute_script("return Math.max(document.body.scrollWidth, document.body.offsetWidth, document.documentElement.clientWidth, document.documentElement.scrollWidth, document.documentElement.offsetWidth);")
                        total_height = driver.execute_script("return Math.max(document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight);")
                        # 确保尺寸合理(最小800x600,最大16000x16000)
                        total_width = max(800, min(16000, total_width))
                        total_height = max(600, min(16000, total_height))
                        # 设置窗口大小为全页面尺寸
                        driver.set_window_size(total_width, total_height)
                        time.sleep(1)  # 等待窗口调整
                        self.root.after(0, lambda n=name, w=total_width, h=total_height:
                            self.ocr_tab_widget.insert(tk.END, f"  页面尺寸: {w}x{h}(全页面)\n"))
                        self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                    except Exception as e:
                        # 如果获取尺寸失败,使用默认窗口大小
                        self.root.after(0, lambda n=name, e=str(e):
                            self.ocr_tab_widget.insert(tk.END, f"  警告: 无法获取全页面尺寸,使用当前窗口大小 ({e})\n"))
                        self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                    # 生成文件名:按钮名+日期+时间
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    # 清理按钮名称中的特殊字符
                    clean_name = name.replace('爬取', '').replace(' ', '_')
                    filename = f"{clean_name}_{timestamp}.png"
                    filepath = os.path.join(save_dir, filename)
                    # 长截图:对整个网页进行滚动截图并拼接
                    try:
                        # 获取页面总高度和视口高度
                        total_height = driver.execute_script("return Math.max(document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight);")
                        viewport_height = driver.execute_script("return window.innerHeight")
                        # 如果页面高度小于等于视口高度,直接截图
                        if total_height <= viewport_height:
                            driver.execute_script("window.scrollTo(0, 0);")
                            time.sleep(0.5)
                            driver.save_screenshot(filepath)
                        else:
                            # 长截图:分段滚动并拼接
                            screenshots = []
                            # 滚动到顶部开始
                            driver.execute_script("window.scrollTo(0, 0);")
                            time.sleep(1)  # 等待页面完全加载
                            # 重新获取实际页面高度(可能因为动态内容变化)
                            total_height = driver.execute_script("return Math.max(document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight);")
                            viewport_height = driver.execute_script("return window.innerHeight")
                            scroll_position = 0
                            segment_index = 0
                            while scroll_position < total_height:
                                # 滚动到当前位置
                                driver.execute_script(f"window.scrollTo(0, {scroll_position});")
                                time.sleep(0.8)  # 等待页面渲染和动态内容加载(增加等待时间)
                                # 再次确认当前视口高度(可能因为页面动态变化)
                                current_viewport = driver.execute_script("return window.innerHeight")
                                # 截取当前视口
                                screenshot_bytes = driver.get_screenshot_as_png()
                                screenshot_img = Image.open(io.BytesIO(screenshot_bytes))
                                # 判断是否是最后一段
                                next_scroll = scroll_position + current_viewport
                                is_last_segment = next_scroll >= total_height
                                if is_last_segment:
                                    # 最后一段:计算需要截取的实际高度
                                    remaining_height = total_height - scroll_position
                                    if remaining_height < screenshot_img.height:
                                        # 如果剩余高度小于截图高度,裁剪图片
                                        img_width = screenshot_img.width
                                        screenshot_img = screenshot_img.crop((0, 0, img_width, remaining_height))
                                screenshots.append(screenshot_img)
                                segment_index += 1
                                # 计算下一个滚动位置(使用实际视口高度,避免重叠)
                                scroll_position += current_viewport
                                # 如果已经到达或超过底部,退出循环
                                if scroll_position >= total_height:
                                    break
                            # 拼接所有截图
                            if screenshots:
                                # 计算总高度(实际截取的图片高度总和)
                                total_img_height = sum(img.height for img in screenshots)
                                img_width = screenshots[0].width
                                # 创建长图
                                long_image = Image.new('RGB', (img_width, total_img_height))
                                # 拼接图片
                                current_height = 0
                                for img in screenshots:
                                    long_image.paste(img, (0, current_height))
                                    current_height += img.height
                                    # 立即释放图片内存
                                    img.close()
                                # 保存长图
                                long_image.save(filepath, 'PNG', quality=95, optimize=True)
                                # 清理内存
                                long_image.close()
                                # 记录长截图信息
                                self.root.after(0, lambda h=total_height, c=len(screenshots), th=total_img_height:
                                    self.ocr_tab_widget.insert(tk.END, f"  长截图完成:页面高度 {h}px,共 {c} 段,拼接后高度 {th}px\n"))
                            else:
                                # 如果没有截图,使用普通截图
                                driver.execute_script("window.scrollTo(0, 0);")
                                time.sleep(0.5)
                                driver.save_screenshot(filepath)
                                self.root.after(0, lambda:
                                    self.ocr_tab_widget.insert(tk.END, "  警告:长截图未生成,已使用普通截图\n"))
                        saved_files.append((name, filepath))
                    except Exception as screenshot_error:
                        # 如果长截图失败,回退到普通截图
                        try:
                            driver.execute_script("window.scrollTo(0, 0);")
                            time.sleep(0.5)
                            driver.save_screenshot(filepath)
                            saved_files.append((name, filepath))
                            self.root.after(0, lambda screenshot_error=str(screenshot_error):
                                self.ocr_tab_widget.insert(tk.END, f"  注意:长截图失败,已使用普通截图: {screenshot_error}\n"))
                        except Exception as fallback_error:
                            raise Exception(f"截图失败: {screenshot_error!s}, 回退截图也失败: {fallback_error!s}")
                    self.root.after(0, lambda n=name, f=filepath:
                        self.ocr_tab_widget.insert(tk.END, f"✓ {n} 截图已保存: {os.path.basename(f)}\n"))
                    self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                    # 立即进行OCR识别
                    self.root.after(0, lambda n=name, f=filepath:
                        self.ocr_tab_widget.insert(tk.END, f"  正在OCR识别 {n}...\n"))
                    self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                    try:
                        # 执行OCR识别
                        ocr_result = self._perform_ocr_on_screenshot(filepath, name)
                        if ocr_result:
                            # 追加识别结果到OCR识别标签页
                            self.root.after(0, lambda r=ocr_result:
                                self.ocr_tab_widget.insert(tk.END, r))
                            self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                            # 同时追加到分析标签页
                            self.root.after(0, lambda r=ocr_result:
                                self.analysis_tab_widget.insert(tk.END, r))
                            self.root.after(0, lambda: self.analysis_tab_widget.see(tk.END))
                            self.root.after(0, lambda n=name:
                                self.ocr_tab_widget.insert(tk.END, f"✓ {n} OCR识别完成\n\n"))
                        else:
                            self.root.after(0, lambda n=name:
                                self.ocr_tab_widget.insert(tk.END, f"✗ {n} OCR识别未获取到文字\n\n"))
                        self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                    except Exception as ocr_error:
                        self.root.after(0, lambda n=name, ocr_error=str(ocr_error):
                            self.ocr_tab_widget.insert(tk.END, f"✗ {n} OCR识别失败: {ocr_error}\n\n"))
                        self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                except Exception as e:
                    self.root.after(0, lambda n=name, e=str(e):
                        self.ocr_tab_widget.insert(tk.END, f"✗ {n} 截图失败: {e}\n"))
                    self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                    continue
            # 关闭浏览器
            if driver:
                driver.quit()
            # 显示完成信息
            if saved_files:
                summary_text = f"\n{'='*80}\n"
                summary_text += "截图和OCR识别完成!\n"
                summary_text += f"共保存 {len(saved_files)} 张图片\n"
                summary_text += f"保存目录: {save_dir}\n"
                summary_text += "OCR识别结果已追加到OCR识别标签页和分析标签页\n"
                summary_text += f"{'='*80}\n\n"
                self.root.after(0, lambda: self.ocr_tab_widget.insert(tk.END, summary_text))
                self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                self.root.after(0, lambda: messagebox.showinfo("成功",
                    f"截图和OCR识别完成!\n\n"
                    f"共保存 {len(saved_files)} 张图片\n"
                    f"保存目录: {save_dir}\n\n"
                    f"OCR识别结果已追加到OCR识别标签页和分析标签页,\n"
                    f"可以直接保存为资讯。"))
            else:
                self.root.after(0, lambda: messagebox.showwarning("警告", "没有成功保存任何截图"))
        except Exception as e:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            self.root.after(0, lambda e=e: messagebox.showerror("错误", f"截图过程出错: {e!s}"))
            import traceback
            traceback.print_exc()

    def _load_chrome_config(self):
        """从配置文件加载Chrome路径"""
        try:
            config_file = os.path.join(_APP_CONFIG_DIR, "chrome_config.json")
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    chrome_path = config.get('chrome_path', '').strip()
                    if chrome_path and os.path.exists(chrome_path):
                        self.chrome_path_config = chrome_path
        except Exception as e:
            print(f"加载Chrome配置失败: {e}")
            self.chrome_path_config = None

    def _save_chrome_config(self, chrome_path):
        """保存Chrome路径到配置文件"""
        try:
            config_file = os.path.join(_APP_CONFIG_DIR, "chrome_config.json")
            config = {'chrome_path': chrome_path}
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.chrome_path_config = chrome_path
        except Exception as e:
            print(f"保存Chrome配置失败: {e}")

    def _auto_detect_chrome(self):
        """自动检测Chrome浏览器路径"""
        # 首先检查配置文件中的路径
        if self.chrome_path_config and os.path.exists(self.chrome_path_config):
            return self.chrome_path_config
        # Windows常见Chrome安装路径(扩展更多路径)
        common_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
            r"D:\Program Files\Google\Chrome\Application\chrome.exe",
            r"D:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"E:\Program Files\Google\Chrome\Application\chrome.exe",
            r"E:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Users\Public\Desktop\Google Chrome.lnk",  # 快捷方式(需要解析)
        ]
        # 检查常见路径
        for path in common_paths:
            if os.path.exists(path):
                # 如果是快捷方式,尝试解析
                if path.endswith('.lnk'):
                    try:
                        import win32com.client
                        shell = win32com.client.Dispatch("WScript.Shell")
                        shortcut = shell.CreateShortCut(path)
                        real_path = shortcut.Targetpath
                        if os.path.exists(real_path):
                            return real_path
                    except:
                        pass
                else:
                    return path
        # 尝试从注册表查找(Windows)
        try:
            import winreg
            reg_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
            ]
            for hkey, path in reg_paths:
                try:
                    key = winreg.OpenKey(hkey, path)
                    chrome_path = winreg.QueryValue(key, None)
                    winreg.CloseKey(key)
                    if os.path.exists(chrome_path):
                        return chrome_path
                except:
                    continue
        except:
            pass
        # 尝试从环境变量PATH中查找
        try:
            import shutil
            chrome_cmd = shutil.which("chrome")
            if chrome_cmd and os.path.exists(chrome_cmd):
                return chrome_cmd
        except:
            pass
        return None

    def open_ocr_crawler(self):
        """打开OCR识别工具"""
        try:
            import os
            import subprocess
            import sys
            # 获取当前脚本所在目录(支持打包后的环境)
            script_name = "web_ocr_crawler.py"
            ocr_script = None
            # 1. 尝试使用 PyInstaller 打包后的路径(sys._MEIPASS)
            if hasattr(sys, '_MEIPASS'):
                meipass_path = os.path.join(sys._MEIPASS, script_name)
                if os.path.exists(meipass_path):
                    ocr_script = meipass_path
            # 2. 尝试可执行文件所在目录的 _internal 子目录
            if not ocr_script and hasattr(sys, 'frozen'):
                exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                internal_path = os.path.join(exe_dir, '_internal', script_name)
                if os.path.exists(internal_path):
                    ocr_script = internal_path
            # 3. 尝试与主程序同目录
            if not ocr_script:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                same_dir_path = os.path.join(current_dir, script_name)
                if os.path.exists(same_dir_path):
                    ocr_script = same_dir_path
            # 4. 尝试当前工作目录
            if not ocr_script:
                cwd_path = os.path.join(os.getcwd(), script_name)
                if os.path.exists(cwd_path):
                    ocr_script = cwd_path
            # 检查文件是否存在
            if not ocr_script or not os.path.exists(ocr_script):
                error_msg = f"找不到OCR识别程序文件:\n{script_name}\n\n"
                if hasattr(sys, '_MEIPASS'):
                    error_msg += f"已尝试路径:\n1. {os.path.join(sys._MEIPASS, script_name)}\n"
                if hasattr(sys, 'frozen'):
                    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                    error_msg += f"2. {os.path.join(exe_dir, '_internal', script_name)}\n"
                error_msg += f"3. {os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)}\n"
                error_msg += f"4. {os.path.join(os.getcwd(), script_name)}\n\n"
                error_msg += "请确保web_ocr_crawler.py文件已正确打包或放置在可执行文件目录中。"
                messagebox.showerror("错误", error_msg)
                return
            # 使用subprocess在新进程中启动OCR程序
            # 检查是否为打包后的环境
            is_frozen = hasattr(sys, 'frozen') or hasattr(sys, '_MEIPASS')
            if is_frozen:
                # 打包后的环境:直接导入并执行模块
                try:
                    import importlib.util
                    module_name = os.path.splitext(script_name)[0]
                    spec = importlib.util.spec_from_file_location(module_name, ocr_script)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        # 在新线程中执行,避免阻塞
                        def run_ocr():
                            try:
                                spec.loader.exec_module(module)
                            except Exception as e:
                                messagebox.showerror("错误", f"执行OCR程序失败: {e}")
                        threading.Thread(target=run_ocr, daemon=True).start()
                    else:
                        messagebox.showerror("错误", f"无法加载OCR模块: {script_name}")
                except Exception as e:
                    messagebox.showerror("错误", f"启动OCR识别工具失败: {e!s}")
            else:
                # 开发环境:使用 subprocess
                if sys.platform == 'win32':
                    subprocess.Popen(
                        [sys.executable, ocr_script],
                        creationflags=subprocess.CREATE_NEW_CONSOLE,
                        cwd=current_dir,
                        encoding='utf-8',
                        errors='replace'
                    )
                else:
                    subprocess.Popen(
                        [sys.executable, ocr_script],
                        cwd=current_dir,
                        encoding='utf-8',
                        errors='replace'
                    )
            messagebox.showinfo("成功", "OCR识别工具已启动!\n\n如果窗口没有出现,请检查控制台输出。")
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", f"启动OCR识别工具失败: {e!s}\n\n请确保已安装必要的依赖库。")

    def browse_screenshot_dir(self):
        """浏览选择截图目录"""
        dir_path = filedialog.askdirectory(
            title="选择截图保存目录",
            initialdir=self.screenshot_save_dir if hasattr(self, 'screenshot_save_dir') else os.getcwd()
        )
        if dir_path:
            self.ocr_dir_var.set(dir_path)
            self.screenshot_save_dir = dir_path

    def ocr_recognize_screenshots(self):
        """识别截图目录中的图片"""
        try:
            # 检查pytesseract是否可用
            try:
                import pytesseract
            except ImportError:
                messagebox.showerror("错误", "pytesseract未安装,无法使用OCR功能\n\n请运行: pip install pytesseract")
                return
            # 获取截图目录
            screenshot_dir = self.ocr_dir_var.get().strip()
            if not screenshot_dir or not os.path.exists(screenshot_dir):
                messagebox.showwarning("警告", "请先选择有效的截图目录")
                return
            # 支持的图片格式
            image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.tif']
            # 获取目录中的所有图片文件
            image_files = []
            for file in os.listdir(screenshot_dir):
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    image_files.append(os.path.join(screenshot_dir, file))
            if not image_files:
                messagebox.showwarning("警告", f"该目录中没有找到图片文件:\n{screenshot_dir}")
                return
            # 按修改时间排序(最新的在前)
            image_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            # 在新线程中执行OCR识别
            thread = threading.Thread(target=self._ocr_recognize_images_thread, args=(image_files,), daemon=True)
            thread.start()
        except Exception as e:
            messagebox.showerror("错误", f"OCR识别失败: {e!s}")
            import traceback
            traceback.print_exc()

    def _ocr_recognize_images_thread(self, image_files):
        """OCR识别图片线程"""
        try:
            import pytesseract
            from PIL import Image
            # 自动检测Tesseract路径
            tesseract_path = self._auto_detect_tesseract_ocr()
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            all_results = []
            for i, image_path in enumerate(image_files, 1):
                try:
                    self.root.after(0, lambda n=os.path.basename(image_path), idx=i, total=len(image_files):
                        self.ocr_tab_widget.insert(tk.END, f"[{idx}/{total}] 正在识别: {n}...\n"))
                    self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                    # 打开图片
                    image = Image.open(image_path)
                    # OCR识别(使用中文+英文)
                    ocr_result = pytesseract.image_to_string(image, lang='chi_sim+eng')
                    if ocr_result.strip():
                        # 添加文件信息
                        filename = os.path.basename(image_path)
                        file_time = datetime.fromtimestamp(os.path.getmtime(image_path)).strftime('%Y-%m-%d %H:%M:%S')
                        result_text = f"\n{'='*80}\n"
                        result_text += f"文件: {filename}\n"
                        result_text += f"时间: {file_time}\n"
                        result_text += f"{'='*80}\n"
                        result_text += ocr_result.strip()
                        result_text += "\n\n"
                        all_results.append(result_text)
                        self.root.after(0, lambda n=filename:
                            self.ocr_tab_widget.insert(tk.END, f"✓ {n} 识别完成\n"))
                    else:
                        self.root.after(0, lambda n=os.path.basename(image_path):
                            self.ocr_tab_widget.insert(tk.END, f"✗ {n} 未识别到文字\n"))
                    self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                except Exception as e:
                    self.root.after(0, lambda n=os.path.basename(image_path), e=str(e):
                        self.ocr_tab_widget.insert(tk.END, f"✗ {n} 识别失败: {e}\n"))
                    self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                    continue
            # 将所有识别结果添加到OCR识别器标签页
            if all_results:
                combined_result = "".join(all_results)
                self.root.after(0, lambda: self.ocr_tab_widget.insert(tk.END,
                    f"\n{'='*80}\n识别完成!共识别 {len(image_files)} 张图片\n{'='*80}\n\n"))
                self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                # 同时显示在分析标签页
                self.root.after(0, lambda: self.analysis_tab_widget.insert(tk.END, combined_result))
                self.root.after(0, lambda: self.analysis_tab_widget.see(tk.END))
                self.root.after(0, lambda: messagebox.showinfo("成功",
                    f"OCR识别完成!\n\n共识别 {len(image_files)} 张图片\n识别结果已显示在分析标签页"))
            else:
                self.root.after(0, lambda: messagebox.showwarning("警告", "没有识别到任何文字"))
        except Exception as e:
            self.root.after(0, lambda e=e: messagebox.showerror("错误", f"OCR识别失败: {e!s}"))
            import traceback
            traceback.print_exc()

    def ocr_select_image(self):
        """选择单个图片进行OCR识别"""
        try:
            # 检查pytesseract是否可用
            try:
                import pytesseract
                from PIL import Image
            except ImportError:
                messagebox.showerror("错误", "pytesseract或PIL未安装,无法使用OCR功能\n\n请运行: pip install pytesseract pillow")
                return
            # 选择图片文件
            file_path = filedialog.askopenfilename(
                title="选择图片文件",
                filetypes=[
                    ("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.tif"),
                    ("PNG文件", "*.png"),
                    ("JPEG文件", "*.jpg *.jpeg"),
                    ("所有文件", "*.*")
                ]
            )
            if not file_path:
                return
            # 在新线程中执行OCR识别
            thread = threading.Thread(target=self._ocr_recognize_single_image_thread, args=(file_path,), daemon=True)
            thread.start()
        except Exception as e:
            messagebox.showerror("错误", f"选择图片失败: {e!s}")

    def _ocr_recognize_single_image_thread(self, file_path):
        """OCR识别单个图片线程"""
        try:
            import pytesseract
            from PIL import Image
            # 自动检测Tesseract路径
            tesseract_path = self._auto_detect_tesseract_ocr()
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            self.root.after(0, lambda: self.ocr_tab_widget.insert(tk.END,
                f"正在识别: {os.path.basename(file_path)}...\n"))
            self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
            # 打开图片
            image = Image.open(file_path)
            # OCR识别(使用中文+英文)
            ocr_result = pytesseract.image_to_string(image, lang='chi_sim+eng')
            if ocr_result.strip():
                # 添加文件信息
                filename = os.path.basename(file_path)
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                result_text = f"\n{'='*80}\n"
                result_text += f"文件: {filename}\n"
                result_text += f"时间: {file_time}\n"
                result_text += f"{'='*80}\n"
                result_text += ocr_result.strip()
                result_text += "\n\n"
                # 显示在OCR识别器标签页
                self.root.after(0, lambda: self.ocr_tab_widget.insert(tk.END, result_text))
                self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                # 同时显示在分析标签页
                self.root.after(0, lambda: self.analysis_tab_widget.insert(tk.END, result_text))
                self.root.after(0, lambda: self.analysis_tab_widget.see(tk.END))
                self.root.after(0, lambda: messagebox.showinfo("成功",
                    f"OCR识别完成!\n\n识别字符数: {len(ocr_result)}\n识别结果已显示在分析标签页"))
            else:
                self.root.after(0, lambda: messagebox.showwarning("警告", "未识别到任何文字"))
        except Exception as e:
            self.root.after(0, lambda e=e: messagebox.showerror("错误", f"OCR识别失败: {e!s}"))
            import traceback
            traceback.print_exc()

    def ocr_paste_image(self):
        """从剪贴板粘贴图片并OCR识别"""
        try:
            # 检查pytesseract和PIL是否可用
            try:
                import pytesseract
                from PIL import Image, ImageGrab
            except ImportError:
                messagebox.showerror("错误", "pytesseract或PIL未安装,无法使用OCR功能\n\n请运行: pip install pytesseract pillow")
                return
            # 在新线程中执行
            thread = threading.Thread(target=self._ocr_paste_image_thread, daemon=True)
            thread.start()
        except Exception as e:
            messagebox.showerror("错误", f"粘贴图片失败: {e!s}")

    def _ocr_paste_image_thread(self):
        """从剪贴板粘贴图片并OCR识别线程"""
        try:
            import io

            import pytesseract
            from PIL import Image, ImageGrab
            # 自动检测Tesseract路径
            tesseract_path = self._auto_detect_tesseract_ocr()
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            self.root.after(0, lambda: self.ocr_tab_widget.insert(tk.END, "正在从剪贴板读取图片...\n"))
            self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
            # 尝试从剪贴板读取图片
            image = None
            # 方法1: 使用win32clipboard (Windows)
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                        data = win32clipboard.GetClipboardData(win32clipboard.CF_DIB)
                        win32clipboard.CloseClipboard()
                        bmp_header = b'BM' + (len(data) + 14).to_bytes(4, 'little') + b'\x00\x00\x00\x00\x36\x00\x00\x00'
                        bmp_data = bmp_header + data
                        image = Image.open(io.BytesIO(bmp_data))
                except Exception:
                    try:
                        win32clipboard.CloseClipboard()
                    except:
                        pass
            except ImportError:
                pass
            except Exception:
                pass
            # 方法2: 使用PIL的ImageGrab
            if image is None:
                try:
                    image = ImageGrab.grabclipboard()
                except Exception:
                    pass
            # 检查是否成功获取图片
            if image is None or not isinstance(image, Image.Image):
                self.root.after(0, lambda: messagebox.showwarning("警告",
                    "剪贴板中没有图片!\n\n请先复制图片到剪贴板"))
                return
            # OCR识别
            self.root.after(0, lambda: self.ocr_tab_widget.insert(tk.END, "正在进行OCR识别...\n"))
            self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
            ocr_result = pytesseract.image_to_string(image, lang='chi_sim+eng')
            if ocr_result.strip():
                result_text = f"\n{'='*80}\n"
                result_text += "来源: 剪贴板图片\n"
                result_text += f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                result_text += f"{'='*80}\n"
                result_text += ocr_result.strip()
                result_text += "\n\n"
                # 显示在OCR识别器标签页
                self.root.after(0, lambda: self.ocr_tab_widget.insert(tk.END, result_text))
                self.root.after(0, lambda: self.ocr_tab_widget.see(tk.END))
                # 同时显示在分析标签页
                self.root.after(0, lambda: self.analysis_tab_widget.insert(tk.END, result_text))
                self.root.after(0, lambda: self.analysis_tab_widget.see(tk.END))
                self.root.after(0, lambda: messagebox.showinfo("成功",
                    f"OCR识别完成!\n\n识别字符数: {len(ocr_result)}\n识别结果已显示在分析标签页"))
            else:
                self.root.after(0, lambda: messagebox.showwarning("警告", "未识别到任何文字"))
        except Exception as e:
            self.root.after(0, lambda e=e: messagebox.showerror("错误", f"OCR识别失败: {e!s}"))
            import traceback
            traceback.print_exc()

    def ocr_recognize_ths(self):
        """同花顺识别:识别OCR结果中的同花顺数据并保存到数据库"""
        try:
            # 获取OCR识别结果
            ocr_text = self.ocr_tab_widget.get("1.0", tk.END).strip()
            if not ocr_text:
                messagebox.showwarning("警告", "请先进行OCR识别,识别结果中需要包含同花顺数据")
                return
            # 解析同花顺数据
            parsed_data = self._parse_ths_data(ocr_text)
            if not parsed_data:
                messagebox.showwarning("警告", "未能从OCR结果中识别到同花顺数据,请确保识别结果包含完整的同花顺表格数据")
                return
            # 显示识别结果并询问是否保存
            result_text = f"识别到 {len(parsed_data)} 条同花顺数据:\n\n"
            for idx, data in enumerate(parsed_data[:10], 1):  # 只显示前10条
                result_text += f"{idx}. {data.get('stock_code', '')} {data.get('stock_name', '')} "
                result_text += f"现价:{data.get('current_price', '')} 涨幅:{data.get('change_pct', '')}\n"
            if len(parsed_data) > 10:
                result_text += f"... 还有 {len(parsed_data) - 10} 条数据\n"
            if messagebox.askyesno("确认保存", f"{result_text}\n是否保存到数据库?"):
                saved_count = self._save_ths_data_to_db(parsed_data)
                if saved_count > 0:
                    # 显示自定义对话框,包含打开数据表按钮
                    self._show_ths_save_result_dialog("成功", f"已成功保存 {saved_count} 条同花顺数据到数据库", saved_count)
                else:
                    messagebox.showerror("失败", "未能保存任何数据到数据库")
        except Exception as e:
            messagebox.showerror("错误", f"同花顺识别失败: {e!s}")
            import traceback
            traceback.print_exc()

    def _perform_ocr_on_screenshot(self, image_path, name):
        """对截图进行OCR识别并返回结果文本"""
        try:
            import pytesseract
            from PIL import Image
            # 自动检测Tesseract路径
            tesseract_path = self._auto_detect_tesseract_ocr()
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            # 打开图片
            image = Image.open(image_path)
            # OCR识别(使用中文+英文)
            ocr_result = pytesseract.image_to_string(image, lang='chi_sim+eng')
            if ocr_result.strip():
                # 添加文件信息
                filename = os.path.basename(image_path)
                file_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                result_text = f"\n{'='*80}\n"
                result_text += f"来源: {name}\n"
                result_text += f"文件: {filename}\n"
                result_text += f"时间: {file_time}\n"
                result_text += f"{'='*80}\n"
                result_text += ocr_result.strip()
                result_text += "\n\n"
                return result_text
            else:
                return None
        except ImportError:
            # pytesseract未安装,返回None但不报错
            return None
        except Exception as e:
            # OCR识别失败,返回None但不中断截图流程
            print(f"OCR识别失败: {e}")
            return None

    def _auto_detect_tesseract_ocr(self):
        """自动检测Tesseract OCR路径"""
        import shutil
        # 检查环境变量PATH中的tesseract
        tesseract_cmd = shutil.which("tesseract")
        if tesseract_cmd:
            return tesseract_cmd
        # 常见安装路径(Windows)
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Tesseract-OCR\tesseract.exe",
            r"D:\Program Files\Tesseract-OCR\tesseract.exe",
            r"D:\Tesseract-OCR\tesseract.exe",
        ]
        # 检查常见路径
        for path in common_paths:
            if os.path.exists(path):
                return path
        return None

    def ocr_image_from_url(self, image_url):
        """从URL识别图片文字"""
        try:
            import tempfile

            import requests
            # 下载图片到临时文件
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                temp_file.write(response.content)
                temp_path = temp_file.name
            try:
                # OCR功能已移除
                ocr_text = "OCR功能已移除"
                # 在当前位置插入OCR结果
                self.text_input.insert(tk.INSERT, "\n")
                self.text_input.insert(tk.INSERT, "🔍 OCR识别结果:\n")
                self.text_input.insert(tk.INSERT, "-" * 30 + "\n")
                self.text_input.insert(tk.INSERT, ocr_text)
                self.text_input.insert(tk.INSERT, "\n" + "-" * 30 + "\n")
                messagebox.showinfo("成功", "图片文字识别完成!")
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_path)
                except:
                    pass
        except Exception as e:
            print(f"OCR识别失败: {e!s}")

    def paste_clipboard_image(self, text_widget=None):
        """粘贴剪贴板中的图片,保存到指定目录并插入链接"""
        try:
            from PIL import ImageGrab
            # 获取剪贴板图片
            image = ImageGrab.grabclipboard()
            if image is None:
                return False
            # 如果没有提供文本框,获取当前活动的文本框
            if text_widget is None:
                text_widget = self.get_active_text_widget()
                if not text_widget:
                    return False
            # 创建图片保存目录(在D盘Output目录下创建Images子目录)
            image_dir = os.path.join(D_OUTPUT_DIR, "Images")
            os.makedirs(image_dir, exist_ok=True)
            # 生成文件名(带时间戳)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 精确到毫秒
            image_filename = f"pasted_image_{timestamp}.png"
            image_path = os.path.join(image_dir, image_filename)
            # 保存图片
            image.save(image_path, "PNG")
            # 生成图片链接文本
            image_link = f"\n[图片] {image_path}\n"
            # 插入到文本框当前光标位置
            text_widget.insert(tk.INSERT, image_link)
            print(f"✅ 图片已保存并插入链接: {image_path}")
            return True
        except Exception as e:
            print(f"粘贴图片失败: {e}")
            return False

    def paste_clipboard_image_alternative(self):
        """替代方法粘贴剪贴板图片"""
        try:
            # 尝试使用PIL检测剪贴板图片
            from PIL import ImageGrab
            # 获取剪贴板图片
            image = ImageGrab.grabclipboard()
            if image is not None:
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
                # 调试信息
                print(f"✅ 剪贴板图片已插入: {image_key}, 尺寸: {new_width}x{new_height}")
                messagebox.showinfo("成功", "已粘贴剪贴板中的图片!\n点击[🔍 OCR识别]可以识别图片中的文字。")
                return True
            else:
                return False
        except Exception as e:
            print(f"替代方法粘贴图片失败: {e}")
            return False

    def ocr_clipboard_image(self, image):
        """识别剪贴板图片中的文字"""
        try:
            import tempfile
            # 保存图片到临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                image.save(temp_file.name)
                temp_path = temp_file.name
            try:
                # OCR功能已移除
                ocr_text = "OCR功能已移除"
                # 在当前位置插入OCR结果
                text_widget = self.get_active_text_widget()
                if text_widget:
                    text_widget.insert(tk.INSERT, "\n")
                    text_widget.insert(tk.INSERT, "🔍 OCR识别结果:\n")
                    text_widget.insert(tk.INSERT, "-" * 30 + "\n")
                    text_widget.insert(tk.INSERT, ocr_text)
                    text_widget.insert(tk.INSERT, "\n" + "-" * 30 + "\n")
                messagebox.showinfo("成功", "剪贴板图片文字识别完成!")
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_path)
                except:
                    pass
        except Exception as e:
            print(f"OCR识别失败: {e!s}")

    def paste_clipboard_html(self, text_widget=None):
        """粘贴剪贴板中的HTML内容"""
        try:
            # 如果没有提供文本框,获取当前活动的文本框
            if text_widget is None:
                text_widget = self.get_active_text_widget()
                if not text_widget:
                    return
            # 尝试获取HTML格式的剪贴板内容
            clipboard_content = self.root.clipboard_get()
            # 检查是否包含HTML标签
            if '<' in clipboard_content and '>' in clipboard_content:
                # 解析HTML内容
                parsed_content = self.parse_html_content(clipboard_content)
                # 插入解析后的内容
                self.insert_parsed_content(parsed_content, text_widget)
                messagebox.showinfo("成功", f"已粘贴HTML内容\n\n包含:\n- 文字段落: {len(parsed_content['text_blocks'])} 个\n- 图片: {len(parsed_content['images'])} 个")
            else:
                # 普通文本内容
                if text_widget:
                    text_widget.insert(tk.INSERT, clipboard_content)
        except Exception as e:
            print(f"粘贴HTML内容失败: {e}")
            # 如果HTML解析失败,直接插入文本
            try:
                clipboard_content = self.root.clipboard_get()
                text_widget = self.get_active_text_widget()
                if text_widget:
                    text_widget.insert(tk.INSERT, clipboard_content)
            except:
                pass

    def _perform_ocr_on_image(self, image_path):
        """对图片执行OCR识别"""
        try:
            # 尝试导入pytesseract
            try:
                import pytesseract
            except ImportError:
                return None
            # 读取图片
            img = Image.open(image_path)
            # 尝试自动检测Tesseract路径
            tesseract_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                r"D:\Program Files\Tesseract-OCR\tesseract.exe",
                r"D:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            tesseract_found = False
            for path in tesseract_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    tesseract_found = True
                    break
            if not tesseract_found:
                # 尝试从环境变量获取
                try:
                    pytesseract.get_tesseract_version()
                    tesseract_found = True
                except:
                    pass
            if not tesseract_found:
                return None
            # 执行OCR(尝试中英文混合识别)
            try:
                # 先尝试中英文混合
                text = pytesseract.image_to_string(img, lang='chi_sim+eng')
            except:
                try:
                    # 如果中文包不可用,只使用英文
                    text = pytesseract.image_to_string(img, lang='eng')
                except:
                    # 如果都失败,使用默认语言
                    text = pytesseract.image_to_string(img)
            return text.strip() if text else None
        except Exception:
            # OCR失败,返回None
            return None


__all__ = ["ScreenshotMixin"]
