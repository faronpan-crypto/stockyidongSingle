# 迁移自 stockyidong mac003.py ranges=[(492, 757), (759, 820), (822, 1006)]
import os
import sys
import re
import time
import json
import base64
import requests
from bs4 import BeautifulSoup
from utils.config import _APP_CONFIG_DIR, CRAWLER_CONFIG_FILE, MARKET_NAV_CONFIG_FILE

class TaogubaCrawler:
    """淘股吧爬虫类"""
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.tgb.cn/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Cache-Control': 'max-age=0'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        # 设置连接池大小和重试
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    def _get_with_retry(self, url, max_retries=3, timeout=30):
        """带重试的GET请求,确保UTF-8编码"""
        for attempt in range(max_retries):
            try:
                # 确保使用UTF-8编码
                response = self.session.get(url, timeout=timeout, allow_redirects=True)
                # 手动设置编码为UTF-8
                if response.encoding is None or response.encoding.lower() in ['iso-8859-1', 'windows-1252']:
                    response.encoding = 'utf-8'
                elif response.encoding.lower() not in ['utf-8', 'utf8']:
                    # 如果响应头指定了其他编码,尝试从内容检测
                    try:
                        import chardet
                        detected = chardet.detect(response.content)
                        if detected and detected.get('encoding'):
                            response.encoding = detected['encoding']
                        else:
                            response.encoding = 'utf-8'
                    except:
                        response.encoding = 'utf-8'
                if response.status_code == 200:
                    return response
                elif response.status_code in [429, 500, 502, 503, 504]:
                    # 服务器错误,等待后重试
                    wait_time = (attempt + 1) * 2
                    print(f"服务器返回 {response.status_code},等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"HTTP状态码: {response.status_code}")
                    return response
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                    requests.exceptions.RequestException) as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"连接失败 (尝试 {attempt + 1}/{max_retries}),等待 {wait_time} 秒后重试: {e}")
                    time.sleep(wait_time)
                else:
                    print(f"连接失败,已重试 {max_retries} 次: {e}")
                    raise
        return None
    def crawl_realtime_articles(self, max_pages=3):
        """爬取淘股吧实时文章"""
        articles = []
        base_url = "https://www.tgb.cn/jinghua/"
        for page in range(1, max_pages + 1):
            try:
                if page == 1:
                    url = base_url
                else:
                    url = f"{base_url}?page={page}"
                print(f"正在爬取第{page}页: {url}")
                # 使用带重试的请求
                response = self._get_with_retry(url, max_retries=3, timeout=30)
                if response and response.status_code == 200:
                    page_articles = self._parse_articles(response.text, page)
                    articles.extend(page_articles)
                    print(f"第{page}页成功获取 {len(page_articles)} 篇文章")
                else:
                    print(f"第{page}页获取失败: HTTP {response.status_code if response else '无响应'}")
                # 增加延迟,避免请求过快
                if page < max_pages:
                    delay = random.uniform(2, 4)
                    print(f"等待 {delay:.1f} 秒后继续...")
                    time.sleep(delay)
            except Exception as e:
                print(f"第{page}页获取失败: {e}")
                import traceback
                traceback.print_exc()
                continue
        return articles
    def _parse_articles(self, html_content, page):
        """解析文章列表,确保UTF-8编码"""
        articles = []
        today = datetime.now().date()
        try:
            # 确保html_content是字符串类型,如果是字节类型则解码
            if isinstance(html_content, bytes):
                try:
                    html_content = html_content.decode('utf-8', errors='replace')
                except:
                    # 如果UTF-8解码失败,尝试使用chardet检测编码
                    try:
                        import chardet
                        detected = chardet.detect(html_content)
                        if detected and detected.get('encoding'):
                            html_content = html_content.decode(detected['encoding'], errors='replace')
                        else:
                            html_content = html_content.decode('utf-8', errors='replace')
                    except:
                        html_content = html_content.decode('utf-8', errors='replace')
            # 使用BeautifulSoup解析,明确指定编码
            soup = BeautifulSoup(html_content, 'html.parser', from_encoding='utf-8')
            # 多种方式查找文章链接
            article_links = []
            # 方法1: 查找当前淘股吧的 base64 风格 /a/xxx 链接(2025-2026 版)
            links_a = soup.find_all('a', href=re.compile(r'/a/[A-Za-z0-9]+'))
            article_links.extend(links_a)
            # 方法2: 查找旧版 /article/ /post/ /数字.html 链接
            links_old = soup.find_all('a', href=re.compile(r'/article/|/post/|/Article/|/Post/'))
            article_links.extend(links_old)
            # 方法3: 查找数字ID的文章链接
            links_num = soup.find_all('a', href=re.compile(r'/\d+\.html|/\d+$|articleId=\d+'))
            article_links.extend(links_num)
            # 方法4: 兜底 — 标题较长的带 href 的链接,排除导航/菜单
            links4 = soup.find_all('a', href=True)
            for link in links4:
                title = link.get_text(strip=True)
                href = link.get('href', '')
                if title and len(title) > 12 and href and not href.startswith('#') and not href.startswith('javascript:'):
                    if any(kw in href.lower() for kw in ['article', 'post', 'thread', 'topic', 'detail', '/a/', '/blog']):
                        article_links.append(link)
            # 去重
            seen_urls = set()
            unique_links = []
            for link in article_links:
                href = link.get('href', '')
                if href and href not in seen_urls:
                    seen_urls.add(href)
                    unique_links.append(link)
            # 处理链接
            for link in unique_links[:30]:  # 限制每页最多30篇
                try:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    if title and len(title) > 5:
                        # 构建完整URL
                        if href.startswith('http'):
                            full_url = href
                        elif href.startswith('/'):
                            full_url = urljoin("https://www.tgb.cn", href)
                        else:
                            full_url = urljoin("https://www.tgb.cn/jinghua/", href)
                        # 提取作者和时间信息(如果存在)
                        author = '未知'
                        publish_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        publish_dt = None
                        last_reply_time = None
                        # 尝试从父元素获取作者和时间
                        parent = link.parent
                        if parent:
                            # 查找作者
                            author_elem = parent.find(text=re.compile(r'作者|发布|发帖'))
                            if not author_elem:
                                author_elem = parent.find('span', class_=re.compile(r'author|user|name'))
                            if author_elem:
                                if isinstance(author_elem, str):
                                    author = author_elem.strip()
                                else:
                                    author = author_elem.get_text(strip=True)
                            # 查找时间
                            time_elem = parent.find(text=re.compile(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}'))
                            if not time_elem:
                                time_elem = parent.find('span', class_=re.compile(r'time|date'))
                            if time_elem:
                                if isinstance(time_elem, str):
                                    publish_time = time_elem.strip()
                                else:
                                    publish_time = time_elem.get_text(strip=True)
                            # 回帖时间(列表页通常展示回帖日期,如 12-09 16:36)
                            reply_elem = parent.find(text=re.compile(r'\d{1,2}[-/]\d{1,2}(\s+\d{1,2}:\d{1,2})?'))
                            if reply_elem:
                                if isinstance(reply_elem, str):
                                    last_reply_time = reply_elem.strip()
                                else:
                                    last_reply_time = reply_elem.get_text(strip=True)
                        # 解析时间,过滤太老的文章(放宽到近 7 天,避免晚间/周末发的文章被过滤)
                        publish_dt = self._parse_datetime_str(publish_time)
                        reply_dt = self._parse_datetime_str(last_reply_time) if last_reply_time else None
                        sort_dt = reply_dt or publish_dt or datetime.now()
                        publish_date = (reply_dt or publish_dt or datetime.now()).date()
                        # 放宽:只要是近 7 天的都保留;如果解析不出时间,也保留(用默认)
                        try:
                            age_days = (today - publish_date).days
                            if age_days > 7:
                                continue
                        except Exception:
                            pass
                        articles.append({
                            'title': title,
                            'url': full_url,
                            'author': author,
                            'publish_time': publish_time,
                            'last_reply_time': last_reply_time or '',
                            'sort_dt': sort_dt,
                            'content': '',
                            'views': 0,
                            'likes': 0,
                            'replies': 0
                        })
                except Exception as e:
                    print(f"  解析单个文章链接失败: {e}")
                    continue
        except Exception as e:
            print(f"解析文章失败: {e}")
            import traceback
            traceback.print_exc()
        # 按最新回复/发帖时间倒序
        articles.sort(key=lambda x: x.get('sort_dt') or datetime.min, reverse=True)
        return articles
    def _parse_datetime_str(self, text):
        """解析日期时间字符串,返回datetime或None"""
        if not text:
            return None
        s = str(text).strip()
        # 将中文格式替换为标准
        s = s.replace('年', '-').replace('月', '-').replace('日', ' ')
        s = re.sub(r'\s+', ' ', s)
        patterns = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d",
        ]
        for fmt in patterns:
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        # 处理仅月日的情况,补全年份
        md = re.match(r"(\d{1,2})[-/](\d{1,2})(\s+\d{1,2}:\d{1,2})?", s)
        if md:
            y = datetime.now().year
            m = int(md.group(1))
            d = int(md.group(2))
            t = md.group(3).strip() if md.group(3) else "00:00"
            try:
                return datetime.strptime(f"{y}-{m:02d}-{d:02d} {t}", "%Y-%m-%d %H:%M")
            except Exception:
                try:
                    return datetime(y, m, d)
                except Exception:
                    return None
        return None

class JiuYangGongSheCrawler:
    """韭研公社爬虫类"""
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    def crawl_articles(self, max_pages=3):
        """爬取韭研公社文章"""
        articles = []
        base_url = "https://www.jiuyangongshe.com/"
        for page in range(1, max_pages + 1):
            try:
                if page == 1:
                    url = base_url
                else:
                    url = f"{base_url}?page={page}"
                response = self.session.get(url, timeout=15)
                if response.status_code == 200:
                    page_articles = self._parse_articles(response.text, page)
                    articles.extend(page_articles)
                    time.sleep(random.uniform(1, 2))
            except Exception as e:
                print(f"爬取第{page}页失败: {e}")
                continue
        return articles
    def _parse_articles(self, html_content, page):
        """解析文章列表"""
        articles = []
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            # 查找文章链接(韭研公社也是 /a/xxx 模式)
            article_links = soup.find_all('a', href=True)
            for link in article_links[:30]:  # 限制每页最多30篇
                try:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    # 匹配韭研的 /a/xxx 文章链接 + 旧版 /article/ /post/
                    is_article = ('/a/' in href
                                  or '/article/' in href.lower()
                                  or '/post/' in href.lower())
                    if title and len(title) > 5 and is_article:
                        full_url = urljoin("https://www.jiuyangongshe.com/", href)
                        articles.append({
                            'title': title,
                            'url': full_url,
                            'author': '未知',
                            'publish_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'content': '',
                            'views': 0,
                            'likes': 0,
                            'replies': 0
                        })
                except:
                    continue
        except Exception as e:
            print(f"解析韭研文章失败: {e}")
        return articles

class AIConfigManager:
    """AI配置管理器"""
    def __init__(self, config_file=None):
        self.config_file = config_file or os.path.join(_APP_CONFIG_DIR, "ai_config.json")
        self.config = self.load_config()
    def load_config(self):
        """加载AI配置"""
        default_config = {
            "active_provider": "deepseek",
            "provider": "deepseek",
            "providers": {
                "deepseek": {
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "",
                    "model": "deepseek-chat",
                    "mode": "chat",
                    "temperature": 0.3,
                    "timeout": 60
                },
                "doubao": {
                    "base_url": "https://ark.cn-beijing.volces.com",
                    "endpoint": "/api/v3/chat/completions",
                    "api_key": "",
                    "model": "doubao-seedance-1-0-pro-250528",
                    "mode": "chat",
                    "temperature": 0.3,
                    "timeout": 60
                },
                "ollama": {
                    "base_url": "http://localhost:11434",
                    "endpoint": "/v1/chat/completions",
                    "model": "qwen2.5:7b",
                    "mode": "chat",
                    "temperature": 0.3,
                    "timeout": 60
                }
            },
            "tushare": {
                "account": "",
                "token": ""
            }
        }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    default_config.update(loaded_config)
            except Exception as e:
                print(f"加载AI配置失败: {e}")
        return default_config
    def save_config(self):
        """保存AI配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存AI配置失败: {e}")
            return False
    def get_active_provider_config(self):
        """获取当前激活的AI提供商配置"""
        provider = self.config.get("active_provider", "deepseek")
        return self.config.get("providers", {}).get(provider, {})
    def get_tushare_config(self):
        """获取Tushare配置"""
        return self.config.get("tushare", {"account": "", "token": ""})
    def set_tushare_config(self, account=None, token=None):
        """设置Tushare配置"""
        if "tushare" not in self.config:
            self.config["tushare"] = {}
        if account is not None:
            self.config["tushare"]["account"] = account
        if token is not None:
            self.config["tushare"]["token"] = token
        self.save_config()
    def call_ai(self, prompt, provider=None):
        """调用AI接口"""
        if provider is None:
            provider = self.config.get("active_provider", "deepseek")
        provider_config = self.config.get("providers", {}).get(provider, {})
        if not provider_config:
            return None
        try:
            api_key = provider_config.get("api_key", "")
            if not api_key:
                return "错误: 未配置API密钥"
            base_url = provider_config.get("base_url", "")
            model = provider_config.get("model", "")
            endpoint = provider_config.get("endpoint", "/chat/completions")
            if provider == "deepseek":
                url = f"{base_url}/chat/completions"
            else:
                url = f"{base_url}{endpoint}"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": provider_config.get("temperature", 0.3)
            }
            response = requests.post(url, json=data, headers=headers,
                                  timeout=provider_config.get("timeout", 60))
            if response.status_code == 200:
                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                return f"API调用失败: {response.status_code} - {response.text}"
        except Exception as e:
            return f"AI调用错误: {e!s}"
    def _copy_tree_selection(self, tree_widget, columns):
        """复制Treeview选中行到剪贴板"""
        selections = tree_widget.selection()
        if not selections:
            messagebox.showwarning("提示", "请先选择需要复制的行")
            return
        lines = []
        header_line = "\t".join(columns)
        lines.append(header_line)
        for item in selections:
            values = tree_widget.item(item, "values")
            formatted = []
            for idx, col in enumerate(columns):
                if idx < len(values):
                    formatted.append(str(values[idx]))
                else:
                    formatted.append("")
            lines.append("\t".join(formatted))
        text = "\n".join(lines)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("成功", "已复制选中数据到剪贴板")
        except Exception as e:
            messagebox.showerror("错误", f"复制失败: {e}")
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

__all__ = ['AIConfigManager', 'JiuYangGongSheCrawler', 'TaogubaCrawler']
