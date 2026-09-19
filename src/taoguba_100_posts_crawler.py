import io
import os
import re
import sys
import time

import pandas as pd
import requests

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    print("警告: akshare未安装，股票识别功能可能不可用")
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.styles import Alignment, Font, PatternFill

# 设置UTF-8编码，解决Windows控制台乱码问题
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        # 设置控制台编码，但不隐藏输出
        os.system('chcp 65001')
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception as e:
        print(f"编码设置警告: {e}", flush=True)

def extract_stock_info(text):
    """从文本中提取股票代码（简化版，不使用分词）"""
    stock_codes = []
    stock_names = []
    stock_positions = []  # 记录股票在文本中的位置和类型
    
    # 只提取股票代码（6位数字）
    stock_code_pattern = r'\b(\d{6})\b'
    code_matches = re.finditer(stock_code_pattern, text)
    for match in code_matches:
        code = match.group(1)
        # 简单验证：股票代码通常是6位数字，且以00、30、60开头（A股、创业板、科创板）
        if code.startswith(('00', '30', '60', '68')):
            stock_codes.append(code)
            stock_positions.append({
                'type': 'code',
                'text': code,
                'name': code,
                'start': match.start(),
                'end': match.end()
            })
    
    # 按位置排序
    stock_positions.sort(key=lambda x: x['start'])
    
    return stock_codes, stock_names, stock_positions

def clean_article_content(content, soup=None):
    """清理文章内容，去除垃圾信息"""
    if not content:
        return content
    
    # 移除HTML标签
    if soup:
        # 移除脚本、样式、导航等垃圾元素
        for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 
                                     'ad', 'advertisement', 'ads', 'ad-wrap', 'ad-container']):
            element.decompose()
        
        # 移除常见的页首页尾类
        for element in soup.find_all(class_=lambda x: x and any(
            keyword in str(x).lower() for keyword in 
            ['header', 'footer', 'nav', 'menu', 'sidebar', 'ad', 'advertisement', 
             'copyright', 'copyright-info', 'site-info', 'footer-info', 'header-info',
             'breadcrumb', 'breadcrumbs', 'pagination', 'pager', 'comment', 'comments',
             'share', 'social', 'related', 'recommend', 'hot', 'tag', 'tags']
        )):
            element.decompose()
        
        # 重新获取清理后的文本
        content = soup.get_text(separator='\n', strip=True)
    
    # 移除常见的垃圾信息模式
    junk_patterns = [
        r'版权所有.*?[\n\r]',
        r'Copyright.*?[\n\r]',
        r'©.*?[\n\r]',
        r'ICP.*?[\n\r]',
        r'备案号.*?[\n\r]',
        r'联系我们.*?[\n\r]',
        r'客服热线.*?[\n\r]',
        r'广告.*?[\n\r]',
        r'ADVERTISEMENT.*?[\n\r]',
        r'点击.*?广告.*?[\n\r]',
        r'关注.*?公众号.*?[\n\r]',
        r'扫码.*?关注.*?[\n\r]',
        r'微信.*?公众号.*?[\n\r]',
        r'分享到.*?[\n\r]',
        r'收藏.*?[\n\r]',
        r'点赞.*?[\n\r]',
        r'相关文章.*?[\n\r]',
        r'推荐阅读.*?[\n\r]',
        r'热门文章.*?[\n\r]',
        r'上一篇.*?[\n\r]',
        r'下一篇.*?[\n\r]',
        r'返回.*?首页.*?[\n\r]',
        r'返回.*?列表.*?[\n\r]',
        r'登录.*?[\n\r]',
        r'注册.*?[\n\r]',
        r'会员.*?[\n\r]',
        r'VIP.*?[\n\r]',
    ]
    
    for pattern in junk_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    # 移除过短的行（可能是垃圾信息）
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        # 保留有意义的行
        if len(line) > 5 and not re.match(r'^[\d\s\-\.]+$', line):
            # 过滤明显的垃圾行
            if not any(junk in line for junk in ['版权所有', 'Copyright', 'ICP', '备案', '广告', 'ADVERTISEMENT']):
                cleaned_lines.append(line)
    
    content = '\n'.join(cleaned_lines)
    
    # 移除多余的空行
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # 移除首尾空白
    content = content.strip()
    
    return content

def format_text_with_stock_highlight(text):
    """格式化文本，为股票代码和股票名添加标记（用于Excel显示）"""
    if not text:
        return text, []
    
    # 提取股票信息
    stock_codes, stock_names, stock_positions = extract_stock_info(text)
    
    if not stock_positions:
        return text, []
    
    # 创建RichText对象来支持不同颜色
    # 由于openpyxl的RichText使用复杂，我们采用标记方式
    # 在文本中标记股票，然后在Excel中应用格式
    
    # 按位置倒序处理，避免位置偏移
    marked_positions = []
    for pos in reversed(stock_positions):
        marked_positions.append(pos)
    
    return text, marked_positions

def get_color_palette():
    """获取6种不同的颜色：红橙绿蓝紫黑"""
    colors = [
        'FFE6E6',  # 红色
        'FFF0E6',  # 橙色
        'E6FFE6',  # 绿色
        'E6F3FF',  # 蓝色
        'F0E6FF',  # 紫色
        'F5F5F5',  # 黑色（用浅灰色代替，因为黑色在白色背景上看不清）
    ]
    return colors


TARGET_POST_COUNT = 100

def _is_essence_post(url, title, soup=None):
    """判断是否是精华帖"""
    try:
        # 从URL判断
        if 'jinghua' in url.lower() or 'essence' in url.lower():
            return True
        
        # 从标题判断
        essence_keywords = ['精华', '推荐', '置顶', '热门', '精选']
        for keyword in essence_keywords:
            if keyword in title:
                return True
        
        # 如果有soup对象，从页面内容判断
        if soup:
            # 查找精华标识
            essence_indicators = soup.find_all(['span', 'div', 'label'], 
                                             class_=lambda x: x and any(
                                                 keyword in x.lower() for keyword in 
                                                 ['jinghua', 'essence', 'hot', 'recommend', 'top']
                                             ))
            if essence_indicators:
                return True
            
            # 查找精华文字标识
            essence_text = soup.find_all(text=lambda text: text and any(
                keyword in text for keyword in ['精华', '推荐', '置顶', '热门']
            ))
            if essence_text:
                return True
        
        return False
    except Exception as e:
        print(f"  检查精华帖失败: {e}")
        return False

def _get_read_count(url, soup=None):
    """获取帖子阅读量"""
    try:
        if not soup:
            return None
        
        # 常见的阅读量标识
        read_patterns = [
            'read', 'view', 'click', 'visit',
            '阅读', '浏览', '查看', '点击', '访问',
        ]
        
        # 查找包含阅读量数字的元素
        for pattern in read_patterns:
            elements = soup.find_all(text=lambda text: text and pattern in text)
            for element in elements:
                # 提取数字
                numbers = re.findall(r'[\d,]+', str(element))
                for num_str in numbers:
                    try:
                        # 处理带逗号的数字
                        num = int(num_str.replace(',', ''))
                        if num >= 1000:  # 只考虑大于1000的阅读量
                            return num
                    except ValueError:
                        continue
        return None
    except Exception as e:
        print(f"  获取阅读量失败: {e}")
        return None

def _is_quality_post(url, title, soup=None):
    """判断是否是精华帖"""
    try:
        # 只检查是否是精华帖
        return _is_essence_post(url, title, soup)
    except Exception as e:
        print(f"  检查帖子质量失败: {e}", flush=True)
        return False

def _get_post_date(url, soup=None):
    """获取帖子发布时间"""
    try:
        if not soup:
            return None
        
        # 常见的日期格式（扩展更多格式）
        date_patterns = [
            r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2})',  # 2024-01-15 12:30:45
            r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{1,2})',  # 2024-01-15 12:30
            r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',  # 2024-01-15 或 2024/01/15
            r'(\d{4}年\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{1,2})',      # 2024年1月15日 12:30
            r'(\d{4}年\d{1,2}月\d{1,2}日)',      # 2024年1月15日
            r'(\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{1,2})',            # 01-15 12:30 或 1/15 12:30
            r'(\d{1,2}[-/]\d{1,2})',            # 01-15 或 1/15
            r'(\d{1,2}月\d{1,2}日)',            # 1月15日
        ]
        
        # 优先查找时间相关的元素（class或id包含time、date、publish等）
        time_elements = soup.find_all(['span', 'div', 'p', 'time'], 
                                     class_=lambda x: x and any(
                                         keyword in str(x).lower() for keyword in 
                                         ['time', 'date', 'publish', 'post-time', 'post-date', 
                                          '发布时间', '时间', '日期', 'date-time']
                                     ))
        
        # 也查找所有文本内容
        all_text_elements = soup.find_all(text=True)
        search_elements = time_elements + all_text_elements
        
        # 按优先级查找日期（先找时间元素，再找所有文本）
        for element in search_elements:
            element_text = element.get_text() if hasattr(element, 'get_text') else str(element)
            if not element_text:
                continue
                
            for pattern in date_patterns:
                match = re.search(pattern, element_text)
                if match:
                    date_str = match.group(1).strip()
                    try:
                        # 尝试解析日期
                        if '年' in date_str:
                            date_str = date_str.replace('年', '-').replace('月', '-').replace('日', '')
                        
                        # 处理带时间的格式
                        if ':' in date_str:
                            parts = date_str.split()
                            date_part = parts[0]
                            time_part = parts[1] if len(parts) > 1 else '00:00:00'
                            if len(time_part.split(':')) == 2:
                                time_part += ':00'
                            
                            # 处理日期部分
                            if len(date_part.split('-')) == 3:
                                post_date = datetime.strptime(f"{date_part} {time_part}", '%Y-%m-%d %H:%M:%S')
                            elif len(date_part.split('/')) == 3:
                                post_date = datetime.strptime(f"{date_part} {time_part}", '%Y/%m/%d %H:%M:%S')
                            else:
                                continue
                        # 处理只有日期的格式
                        elif len(date_str.split('-')) == 3:
                            post_date = datetime.strptime(date_str, '%Y-%m-%d')
                        elif len(date_str.split('/')) == 3:
                            post_date = datetime.strptime(date_str, '%Y/%m/%d')
                        elif len(date_str.split('-')) == 2:
                            # 只有月-日，假设是今年
                            year = datetime.now().year
                            post_date = datetime.strptime(f"{year}-{date_str}", '%Y-%m-%d')
                        elif len(date_str.split('/')) == 2:
                            # 只有月/日，假设是今年
                            year = datetime.now().year
                            post_date = datetime.strptime(f"{year}/{date_str}", '%Y/%m/%d')
                        else:
                            continue
                        
                        # 验证日期合理性（不能是未来，也不能太早）
                        now = datetime.now()
                        if post_date > now:
                            # 如果是未来日期，可能是年份错误，尝试用去年
                            post_date = post_date.replace(year=post_date.year - 1)
                        if (now - post_date).days > 365:
                            # 如果超过1年，可能解析错误，跳过
                            continue
                        
                        return post_date
                    except ValueError:
                        continue
        
        # 如果找不到日期，返回None（表示无法判断，继续处理）
        return None
    except Exception as e:
        print(f"  获取日期失败: {e}", flush=True)
        return None

def _is_recent_post(url, soup=None, days=3):
    """判断是否是最近N天的帖子"""
    try:
        post_date = _get_post_date(url, soup)
        if post_date is None:
            # 如果无法获取日期，默认认为是最近的（继续处理）
            return True
        
        # 计算日期差
        days_diff = (datetime.now() - post_date).days
        return days_diff <= days
    except Exception:
        # 如果出错，默认认为是最近的（继续处理）
        return True

def _is_article_link(url, title):
    """判断是否是文章链接（简化版本，确保能获取到足够数据）"""
    if not title or len(title) < 3:
        return False
    
    # 基本过滤条件
    if len(title) >= 5 and not title.isdigit():
        return True
    
    # 排除明显的非内容链接
    exclude_patterns = [
        'javascript:', 'mailto:', '#', 'login', 'register', 'search',
        '广告', 'copyright', '版权', '联系我们', '登录', '注册'
    ]
    
    for pattern in exclude_patterns:
        if pattern in url.lower() or pattern in title.lower():
            return False
    
    return True

def _create_post_record(title, url, color_palette, current_count):
    """创建一个帖子记录，用于跟踪处理状态和颜色"""
    return {
        '标题': title,
        '作者': '未知作者',
        '发布时间': datetime.now().strftime('%Y-%m-%d'),
        '阅读量': 0,
        '点赞数': 0,
        '评论数': 0,
        '帖子链接': url,
        '帖子ID': '',
        '摘要': '',
        '爬取时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '颜色代码': color_palette[current_count % len(color_palette)],
        '颜色索引': current_count % len(color_palette),
        '处理状态': '待处理',
        '帖子内容': '',
        '股票代码': '',
        '股票名称': '',
        '股票位置': []
    }

def crawl_taoguba_100_posts():
    """爬取淘股吧100个精华帖子内容"""
    print("淘股吧精华帖子爬取工具", flush=True)
    print("=" * 50, flush=True)
    print("过滤条件：", flush=True)
    print("1. 精华帖（包含'精华'、'推荐'、'置顶'、'热门'、'精选'等关键词）", flush=True)
    print("2. 目标：爬取100篇精华文章", flush=True)
    print("3. 只采集最近1天的帖子（确保获取最新内容）", flush=True)
    print("4. 无页数限制，持续搜索直到找到足够的最近帖子", flush=True)
    print("=" * 50, flush=True)
    print("功能特性：", flush=True)
    print("1. 自动清理垃圾信息（页首、页尾、广告等）", flush=True)
    print("2. 自动识别股票代码", flush=True)
    print("3. 在Excel中用不同颜色高亮显示股票", flush=True)
    print("=" * 50, flush=True)
    print("开始爬取...", flush=True)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    base_urls = [
        "http://www.taoguba.com.cn/",
        "http://www.taoguba.com.cn/jinghua/",
        "https://www.tgb.cn/",
        "https://www.tgb.cn/bbs/",
        "https://www.tgb.cn/jinghua/",
    ]
    
    all_posts = []
    color_palette = get_color_palette()
    
    # 添加总体超时机制：如果超过20秒没有进展，直接进入保存步骤
    crawl_start_time = time.time()
    last_progress_time = time.time()
    MAX_IDLE_TIME = 20  # 最大空闲时间（秒）
    timeout_triggered = False  # 超时标志
    
    # 尝试多个页面，无页数限制
    pages_to_try = list(range(1, 11))  # 每个入口最多尝试 10 页
    
    for base_url in base_urls:
        if len(all_posts) >= TARGET_POST_COUNT or timeout_triggered:
            break
        print(f"\n尝试访问: {base_url}", flush=True)
        
        for page in pages_to_try:
            if timeout_triggered:
                break
            if len(all_posts) >= TARGET_POST_COUNT:
                break
            try:
                # 尝试不同的分页格式
                if '?' in base_url:
                    url = f"{base_url}&page={page}"
                else:
                    url = f"{base_url}?page={page}"
                
                if page == 1:
                    url = base_url
                
                print(f"正在访问第{page}页: {url}", flush=True)
                sys.stdout.flush()
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    print(f"第{page}页: HTTP状态码 {response.status_code}", flush=True)
                    sys.stdout.flush()
                    # 更新进展时间（成功获取页面也算进展）
                    last_progress_time = time.time()
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 查找所有链接
                    links = soup.find_all('a', href=True)
                    print(f"第{page}页找到 {len(links)} 个链接", flush=True)
                    sys.stdout.flush()
                    
                    page_posts = 0
                    for link in links:
                        # 检查总体超时：如果超过20秒没有进展，直接进入保存步骤
                        current_time = time.time()
                        if current_time - last_progress_time > MAX_IDLE_TIME:
                            print(f"\n⚠️ 警告: 爬取过程超过{MAX_IDLE_TIME}秒没有进展，停止爬取并保存已有数据", flush=True)
                            print(f"   已爬取 {len(all_posts)} 个帖子，将保存到Excel", flush=True)
                            sys.stdout.flush()
                            # 设置超时标志，跳出所有循环
                            timeout_triggered = True
                            break
                        
                        # 检查是否已有足够的精华文章
                        if len(all_posts) >= TARGET_POST_COUNT:
                            print(f"已达到{TARGET_POST_COUNT}个精华帖子，停止搜索", flush=True)
                            break
                        
                        href = link.get('href', '')
                        title = link.get_text(strip=True)
                        
                        # 过滤条件
                        if (title and len(title) > 5 and 
                            href and not href.startswith('#') and
                            not href.startswith('javascript:') and
                            not href.startswith('mailto:')):
                            
                            # 构建完整URL
                            if href.startswith('http'):
                                full_url = href
                            elif href.startswith('/'):
                                parsed = urlparse(base_url)
                                full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                            else:
                                full_url = f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                            
                            # 检查是否已经存在
                            if not any(post['帖子链接'] == full_url for post in all_posts):
                                # 检查是否是文章链接
                                if _is_article_link(full_url, title):
                                    # 检查是否是精华帖
                                    if _is_quality_post(full_url, title, soup):
                                        # 获取更详细的帖子信息
                                        post_info = _create_post_record(title, full_url, color_palette, len(all_posts))
                                        fetch_status = "成功"
                                        content = ""
                                        stock_codes = []
                                        stock_names = []
                                        stock_positions = []
                                        content_soup = None
                                        try:
                                            print(f"正在处理第 {len(all_posts)+1}/{TARGET_POST_COUNT} 个精华帖子: {title[:30]}...", flush=True)
                                            sys.stdout.flush()
                                            content_response = requests.get(full_url, headers=headers, timeout=1)
                                            if content_response.status_code == 200:
                                                content_soup = BeautifulSoup(content_response.text, 'html.parser')
                                                
                                                # 首先获取帖子发布日期，用于过滤旧帖子
                                                post_date = _get_post_date(full_url, content_soup)
                                                if post_date:
                                                    # 只保留最近1天的帖子
                                                    days_diff = (datetime.now() - post_date).days
                                                    if days_diff > 1:
                                                        print(f"  ⏭ 跳过旧帖子: {title[:30]}... (发布日期: {post_date.strftime('%Y-%m-%d')}, 已过 {days_diff} 天)", flush=True)
                                                        sys.stdout.flush()
                                                        continue
                                                    post_info['发布时间'] = post_date.strftime('%Y-%m-%d %H:%M:%S')
                                                    print(f"  📅 帖子日期: {post_info['发布时间']}", flush=True)
                                                else:
                                                    # 如果无法获取日期，默认认为是今天的（继续处理）
                                                    post_info['发布时间'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                                    print("  ⚠ 无法获取日期，假设是今天的帖子", flush=True)
                                                
                                                content_elem = None
                                                # 尝试提取内容
                                                content_selectors = [
                                                    '.article-content', '.post-content', '.content',
                                                    '.article-body', '.post-body', '.main-content',
                                                    '.article', '.post', '.main', '.body',
                                                    '#content', '.text', '.article-text', '.post-text',
                                                    '.news-content', '.news-body', '.news-text',
                                                    '.detail-content', '.detail-body', '.detail-text'
                                                ]
                                                for selector in content_selectors:
                                                    content_elem = content_soup.select_one(selector)
                                                    if content_elem:
                                                        text_content = content_elem.get_text(strip=True)
                                                        if text_content:
                                                            content = text_content
                                                            break
                                                if not content:
                                                    body = content_soup.find('body')
                                                    if body:
                                                        content = body.get_text(strip=True)[:2000]
                                                if content:
                                                    content = clean_article_content(content, content_soup if content_elem else None)
                                                stock_codes, stock_names, stock_positions = extract_stock_info(content or "")
                                            else:
                                                fetch_status = f"HTTP状态码 {content_response.status_code}"
                                                print(f"  ! 内容请求异常: {fetch_status}", flush=True)
                                        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.RequestException) as e:
                                            # 请求异常（超时、连接错误等）：立即跳过当前帖子，继续下一个
                                            print(f"  ⏭ 帖子爬取异常，立即跳过: {title[:30]}... ({type(e).__name__})", flush=True)
                                            sys.stdout.flush()
                                            continue  # 跳过当前帖子，继续下一个
                                        except Exception as e:
                                            fetch_status = f"异常: {e}"
                                            print(f"  ! 处理帖子时出现异常: {e}", flush=True)
                                            import traceback
                                            traceback.print_exc()
                                            content = content or ""
                                            stock_positions = []
                                        post_info['股票代码'] = ', '.join(stock_codes) if stock_codes else ''
                                        post_info['股票名称'] = ', '.join(stock_names) if stock_names else ''
                                        post_info['股票位置'] = stock_positions
                                        post_info['帖子内容'] = content or ""
                                        post_info['获取状态'] = fetch_status
                                        all_posts.append(post_info)
                                        page_posts += 1
                                        # 更新最后进展时间
                                        last_progress_time = time.time()
                                        if fetch_status == "成功":
                                            print(f"  ✓ 收录精华帖: {title[:30]}... (内容长度: {len(content) if content else 0})", flush=True)
                                        else:
                                            print(f"  ⚠ 收录异常帖: {title[:30]}... (状态: {fetch_status})", flush=True)
                                        sys.stdout.flush()
                                        if len(all_posts) >= TARGET_POST_COUNT:
                                            break
                                    else:
                                        pass  # 不输出普通帖子信息，减少输出
                        
                        # 检查是否已有足够的精华文章
                        if len(all_posts) >= TARGET_POST_COUNT:
                            print(f"已达到{TARGET_POST_COUNT}个精华帖子，停止搜索", flush=True)
                            break
                    
                    print(f"第{page}页获取到 {page_posts} 个新帖子", flush=True)
                    print(f"当前已收集帖子总数: {len(all_posts)}/{TARGET_POST_COUNT}", flush=True)
                    sys.stdout.flush()
                    
                    # 如果达到目标数量的精华帖子就停止尝试其他URL
                    if len(all_posts) >= TARGET_POST_COUNT:
                        break
                    
                    # 检查总体超时：如果超过20秒没有进展，直接进入保存步骤
                    current_time = time.time()
                    if current_time - last_progress_time > MAX_IDLE_TIME:
                        print(f"\n⚠️ 警告: 爬取过程超过{MAX_IDLE_TIME}秒没有进展，停止爬取并保存已有数据", flush=True)
                        print(f"   已爬取 {len(all_posts)} 个帖子，将保存到Excel", flush=True)
                        sys.stdout.flush()
                        # 设置超时标志，跳出所有循环
                        timeout_triggered = True
                        break
                else:
                    print(f"第{page}页: HTTP状态码 {response.status_code}", flush=True)
                
                time.sleep(0.3)  # 避免请求过快
                
            except Exception as e:
                print(f"第{page}页获取失败: {e}", flush=True)
                import traceback
                traceback.print_exc()
                sys.stdout.flush()
                continue
        
        # 检查超时标志，如果触发则跳出外层循环
        if timeout_triggered:
            break
    
    total_time = time.time() - crawl_start_time
    print(f"\n总共获取{len(all_posts)}个精华帖子 (耗时: {total_time:.1f}秒)", flush=True)
    sys.stdout.flush()
    
    if all_posts:
        print(f"\n最终精华文章数量: {len(all_posts)}篇", flush=True)
        print("开始保存到Excel...", flush=True)
        sys.stdout.flush()
        # 保存到Excel（带颜色）
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, "taoguba_exports")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"taoguba_100_posts_{timestamp}.xlsx"
        filepath = os.path.join(output_dir, filename)
        
        # 准备数据
        df = pd.DataFrame(all_posts)
        
        # 设置列的顺序（添加股票相关列）
        columns_order = [
            '标题', '作者', '发布时间', '帖子链接', '帖子内容', 
            '股票代码', '股票名称', '阅读量', '点赞数', '评论数', 
            '摘要', '爬取时间', '颜色代码', '颜色索引', '处理状态'
        ]
        
        # 只保留存在的列
        existing_columns = [col for col in columns_order if col in df.columns]
        
        # 创建Excel工作簿
        wb = Workbook()
        ws = wb.active
        ws.title = "淘股吧帖子"
        
        # 写入标题行
        for col_num, column_title in enumerate(existing_columns, 1):
            cell = ws.cell(row=1, column=col_num, value=column_title)
            cell.font = Font(bold=True, size=12, name='微软雅黑')
            cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # 写入数据行（带颜色和股票高亮）
        total_rows = len(df)
        print(f"正在写入Excel数据，共 {total_rows} 行...", flush=True)
        sys.stdout.flush()
        for row_num, (idx, row_data) in enumerate(df.iterrows(), 2):
            if row_num % 10 == 0:  # 每10行显示一次进度
                print(f"  已写入 {row_num-1}/{total_rows} 行...", flush=True)
                sys.stdout.flush()
            for col_num, column_title in enumerate(existing_columns, 1):
                if column_title not in row_data:
                    continue
                    
                cell_value = row_data[column_title]
                
                # 如果是帖子内容列，需要处理股票高亮
                if column_title == '帖子内容' and isinstance(cell_value, str) and cell_value:
                    # 获取股票位置信息
                    stock_positions = row_data.get('股票位置', [])
                    if stock_positions and isinstance(stock_positions, list):
                        # 使用RichText来设置不同颜色的字体
                        try:
                            rich_text = CellRichText()
                            last_pos = 0
                            
                            # 按位置排序
                            sorted_positions = sorted(stock_positions, key=lambda x: x.get('start', 0))
                            
                            for pos_info in sorted_positions:
                                start_pos = pos_info.get('start', 0)
                                end_pos = pos_info.get('end', 0)
                                pos_type = pos_info.get('type', '')
                                
                                # 添加普通文本（股票之前的部分）
                                if start_pos > last_pos:
                                    normal_text = cell_value[last_pos:start_pos]
                                    if normal_text:
                                        rich_text.append(TextBlock(Font(name='微软雅黑', size=10, color='000000'), normal_text))
                                
                                # 添加股票文本（带颜色）
                                if end_pos > start_pos:
                                    stock_text = cell_value[start_pos:end_pos]
                                    if stock_text:
                                        if pos_type == 'code':
                                            # 股票代码用蓝色加粗
                                            rich_text.append(TextBlock(Font(name='微软雅黑', size=10, color='0000FF', bold=True), stock_text))
                                        else:
                                            # 股票名称用红色加粗
                                            rich_text.append(TextBlock(Font(name='微软雅黑', size=10, color='FF0000', bold=True), stock_text))
                                
                                last_pos = end_pos
                            
                            # 添加剩余文本
                            if last_pos < len(cell_value):
                                remaining_text = cell_value[last_pos:]
                                if remaining_text:
                                    rich_text.append(TextBlock(Font(name='微软雅黑', size=10, color='000000'), remaining_text))
                            
                            cell = ws.cell(row=row_num, column=col_num)
                            cell.value = rich_text
                        except Exception as e:
                            # 如果RichText失败，使用普通文本
                            print(f"  设置股票高亮失败 (行{row_num}): {e}")
                            cell = ws.cell(row=row_num, column=col_num, value=cell_value)
                            cell.font = Font(name='微软雅黑', size=10)
                    else:
                        # 没有股票，使用普通文本
                        cell = ws.cell(row=row_num, column=col_num, value=cell_value)
                        cell.font = Font(name='微软雅黑', size=10)
                else:
                    # 其他列使用普通文本
                    cell = ws.cell(row=row_num, column=col_num, value=cell_value)
                    
                    # 设置字体
                    if column_title == '标题':
                        cell.font = Font(bold=True, size=11, name='微软雅黑')
                    elif column_title in ['股票代码', '股票名称']:
                        cell.font = Font(bold=True, size=10, name='微软雅黑', color='0066CC')
                    else:
                        cell.font = Font(size=10, name='微软雅黑')
                
                # 设置对齐方式
                if column_title == '帖子内容':
                    cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                
                # 设置背景颜色
                color_code = row_data.get('颜色代码', 'FFFFFF')
                if color_code:
                    color_fill = PatternFill(start_color=color_code, end_color=color_code, fill_type="solid")
                    cell.fill = color_fill
        
        # 调整列宽
        column_widths = {
            '标题': 30,
            '作者': 15,
            '发布时间': 12,
            '帖子链接': 50,
            '帖子内容': 80,
            '股票代码': 20,
            '股票名称': 30,
            '阅读量': 10,
            '点赞数': 10,
            '评论数': 10,
            '摘要': 40,
            '爬取时间': 20,
            '颜色代码': 12,
            '颜色索引': 10
        }
        
        for col_num, column_title in enumerate(existing_columns, 1):
            if column_title in column_widths:
                ws.column_dimensions[ws.cell(row=1, column=col_num).column_letter].width = column_widths[column_title]
        
        # 设置行高
        for row_num in range(2, len(all_posts) + 2):
            ws.row_dimensions[row_num].height = 60  # 设置行高以显示更多内容
        
        # 保存文件
        print("正在保存Excel文件...", flush=True)
        sys.stdout.flush()
        wb.save(filepath)
        
        print(f"\n数据已保存到: {filepath}", flush=True)
        print(f"共获取 {len(all_posts)} 个帖子", flush=True)
        print(f"使用了 {len(set(post.get('颜色索引', 0) for post in all_posts))} 种不同颜色", flush=True)
        
        # 统计股票信息
        total_stocks = sum(1 for post in all_posts if post.get('股票代码') or post.get('股票名称'))
        print(f"包含股票信息的帖子: {total_stocks} 个", flush=True)
        print("爬取完成！", flush=True)
        sys.stdout.flush()
        
        # 保存到配置文件
        try:
            import json
            config_file = os.path.join("D:\\StockAnalyzer", "excel_files_config.json")
            config_dir = os.path.dirname(config_file)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            
            config = {}
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            if 'excel_files' not in config:
                config['excel_files'] = []
            
            file_path_abs = os.path.abspath(filepath)
            existing = False
            for file_info in config['excel_files']:
                if os.path.abspath(file_info.get('path', '')) == file_path_abs:
                    file_info['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    file_info['source'] = '淘股吧'
                    existing = True
                    break
            
            if not existing:
                config['excel_files'].append({
                    'path': file_path_abs,
                    'source': '淘股吧',
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            
            if len(config['excel_files']) > 50:
                config['excel_files'].sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                config['excel_files'] = config['excel_files'][:50]
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}", flush=True)
        
        return filepath
    else:
        print("未获取到帖子", flush=True)
        sys.stdout.flush()
        return None

def main():
    try:
        print("开始爬取淘股吧100个精华帖子内容...", flush=True)
        sys.stdout.flush()
        filepath = crawl_taoguba_100_posts()
        if filepath:
            print(f"\n爬取完成！数据已保存到: {filepath}", flush=True)
        else:
            print("\n爬取失败", flush=True)
        sys.stdout.flush()
    except KeyboardInterrupt:
        print("\n\n用户中断程序", flush=True)
        sys.stdout.flush()
    except Exception as e:
        print(f"\n\n程序出错: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.stdout.flush()

if __name__ == "__main__":
    main()