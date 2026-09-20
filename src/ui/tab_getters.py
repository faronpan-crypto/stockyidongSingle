"""get/fetch/query 取值方法"""
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


class GettersMixin:
    """get/fetch/query 取值方法"""

    def _read_crawled_files(self, folder_path):
        """读取爬取的文件内容(使用蜘蛛读取的逻辑)"""
        try:
            import glob
            import re
            # 支持的文件扩展名(主要是HTML)
            supported_extensions = ['*.html', '*.htm']
            all_files = []
            for ext in supported_extensions:
                all_files.extend(glob.glob(os.path.join(folder_path, '**', ext), recursive=True))
            if not all_files:
                return []
            # 检查是否包含中文的正则表达式
            chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
            all_content = []
            def filter_chinese_content(text):
                """过滤文本,保留包含中文的行和段落"""
                if not text:
                    return ""
                # 检查是否包含中文
                if not chinese_pattern.search(text):
                    return ""
                # 按行处理,保留包含中文的行
                lines = text.split('\n')
                filtered_lines = []
                for line in lines:
                    if chinese_pattern.search(line) or not line.strip():
                        filtered_lines.append(line)
                filtered_text = '\n'.join(filtered_lines)
                if len(filtered_text.strip()) < 50 and len(text.strip()) >= 50:
                    return text
                return filtered_text if filtered_text.strip() else text
            for file_path in all_files:
                file_name = os.path.basename(file_path)
                try:
                    file_ext = os.path.splitext(file_path)[1].lower()
                    content = ""
                    if file_ext in ['.html', '.htm']:
                        # HTML文件读取
                        try:
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
                                soup = BeautifulSoup(html_content, 'html.parser')
                                # 移除script和style标签
                                for script in soup(["script", "style"]):
                                    script.decompose()
                                # 提取文本内容
                                text_content = soup.get_text(separator='\n')
                                # 清理文本
                                lines = []
                                for line in text_content.splitlines():
                                    stripped = line.strip()
                                    if stripped:
                                        lines.append(stripped)
                                    elif lines and lines[-1]:
                                        lines.append('')
                                content = '\n'.join(lines)
                        except Exception:
                            continue
                    if content and not content.startswith("文件") and not content.startswith("无法"):
                        # 过滤内容,保留包含中文的部分
                        filtered_content = filter_chinese_content(content)
                        if not filtered_content.strip() and chinese_pattern.search(content):
                            filtered_content = content
                        if filtered_content.strip():
                            file_header = f"\n{'='*80}\n文件: {file_name}\n路径: {file_path}\n{'='*80}\n\n"
                            all_content.append(file_header + filtered_content)
                except Exception:
                    continue
            return all_content
        except Exception:
            import traceback
            traceback.print_exc()
            return []

    def _fetch_with_encoding_fix(self, url, headers, max_retries=2):
        """带编码修正的网页获取函数
        Args:
            url: 要获取的URL
            headers: 请求头
            max_retries: 最大重试次数
        Returns:
            tuple: (成功解码的文本, 使用的编码) 或 (None, None) 如果失败
        """
        for attempt in range(max_retries + 1):
            try:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code != 200:
                    if attempt < max_retries:
                        time.sleep(1)
                        continue
                    return None, None
                # 首先尝试使用response的编码
                try:
                    if response.encoding:
                        text = response.text
                        if not self._detect_garbled_text(text):
                            return text, response.encoding
                except:
                    pass
                # 如果检测到乱码或编码失败,尝试修正
                content_bytes = response.content
                fixed_text, used_encoding = self._fix_encoding(content_bytes)
                if fixed_text and not self._detect_garbled_text(fixed_text):
                    return fixed_text, used_encoding
                # 如果还是乱码且还有重试机会,重新请求
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                # 最后一次尝试,即使有乱码也返回
                if fixed_text:
                    return fixed_text, used_encoding
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                print(f"获取 {url} 失败: {e}")
                return None, None
        return None, None

    def _fetch_xuangutong_leaders_stocks(self):
        """仅爬取选股通主题库领涨领跌股,返回 [{'name','code'}, ...],不导入界面。供爬取热门股组合使用。"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://xuangutong.com.cn/'
        }
        try:
            response = requests.get("https://xuangutong.com.cn/zhutiku", headers=headers, timeout=30)
            response.encoding = 'utf-8'
            html_content = response.text
        except Exception as e:
            print(f"选股通请求失败: {e}")
            return []
        if not html_content:
            return []
        stocks = self._extract_xuangutong_zhutiku_stocks_from_html(html_content)
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
                print(f"选股通补充名称失败: {e}")
        return stocks

    def _fetch_xuangutong_full_no_dedup(self):
        """爬取选股通主题库板块数据(板块名、涨跌家数、涨停数、资金流向),返回 [{'板块名','涨跌幅','涨跌家数','涨停数','资金流向','领涨股','来源':'选股通'}, ...]。"""
        import re
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://xuangutong.com.cn/'
        }
        sectors = []
        try:
            response = requests.get("https://xuangutong.com.cn/zhutiku", headers=headers, timeout=30)
            response.encoding = 'utf-8'
            html_content = response.text
        except Exception as e:
            print(f"选股通请求失败: {e}")
            return []
        if not html_content:
            return []
        soup = BeautifulSoup(html_content, 'html.parser')
        # 尝试解析板块表格或列表
        # 方式1: 查找表格行
        rows = soup.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 5:
                text_vals = [c.get_text(strip=True) for c in cells]
                # 检查是否为板块数据行(第一个字段为数字排序或板块名)
                if text_vals[0].isdigit() or (len(text_vals[1]) >= 2 and re.match(r'[\u4e00-\u9fa5]', text_vals[1])):
                    sector = {
                        '板块名': text_vals[1] if text_vals[0].isdigit() else text_vals[0],
                        '涨跌幅': text_vals[2] if len(text_vals) > 2 else '',
                        '涨跌家数': text_vals[3] if len(text_vals) > 3 else '',
                        '涨停数': text_vals[4] if len(text_vals) > 4 else '',
                        '资金流向': text_vals[6] if len(text_vals) > 6 else (text_vals[5] if len(text_vals) > 5 else ''),
                        '领涨股': text_vals[5] if len(text_vals) > 5 and '亿' not in text_vals[5] else '',
                        '来源': '选股通'
                    }
                    if sector['板块名'] and not sector['板块名'].startswith('排序'):
                        sectors.append(sector)
        # 方式2: 如果表格解析失败,尝试解析div结构
        if not sectors:
            for div in soup.find_all('div', class_=re.compile(r'(sector|plate|item|row)', re.IGNORECASE)):
                text = div.get_text(separator='|', strip=True)
                parts = [p.strip() for p in text.split('|') if p.strip()]
                if len(parts) >= 3:
                    # 尝试识别板块名(中文)
                    sector_name = ''
                    for p in parts:
                        if re.match(r'^[\u4e00-\u9fa5]{2,}$', p) and p not in ['涨跌幅', '涨跌家数', '涨停家数', '资金流向']:
                            sector_name = p
                            break
                    if sector_name:
                        sector = {
                            '板块名': sector_name,
                            '涨跌幅': next((p for p in parts if '%' in p), ''),
                            '涨跌家数': next((p for p in parts if '/' in p), ''),
                            '涨停数': next((p for p in parts if p.isdigit()), ''),
                            '资金流向': next((p for p in parts if '亿' in p), ''),
                            '领涨股': '',
                            '来源': '选股通'
                        }
                        sectors.append(sector)
        # 方式3: 从全文提取板块信息
        if not sectors:
            text = soup.get_text()
            # 匹配模式: 板块名 涨跌幅 涨跌家数 涨停数 资金流向
            pattern = re.compile(r'(\d{1,2})\s+([\u4e00-\u9fa5]{2,6})\s+([+-]?\d+\.?\d*%)\s+(\d+/\d+/\d+)\s+(\d+)\s+(.+?)\s+([+-]?\d+\.?\d*亿)')
            for m in pattern.finditer(text):
                sectors.append({
                    '板块名': m.group(2),
                    '涨跌幅': m.group(3),
                    '涨跌家数': m.group(4),
                    '涨停数': m.group(5),
                    '领涨股': m.group(6),
                    '资金流向': m.group(7),
                    '来源': '选股通'
                })
        return sectors

    def _get_result_text_for_crawler(self):
        """获取用于爬虫输出的结果文本框(使用默认标签页)"""
        # 爬虫输出始终使用默认的"分析结果"标签页
        if self.result_tabs:
            # 查找"分析结果"标签页
            for tab_info in self.result_tabs.values():
                if tab_info['title'] == "分析结果":
                    return tab_info['widget']
            # 如果没有找到,返回第一个标签页
            first_tab = next(iter(self.result_tabs.values()))
            return first_tab['widget']
        return None

    def _get_recent_excel_files(self, max_count=10):
        """从配置文件读取最新的Excel文件列表"""
        try:
            if not os.path.exists(EXCEL_FILES_CONFIG_FILE):
                return []
            with open(EXCEL_FILES_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            files = config.get('excel_files', [])
            # 按时间戳排序,最新的在前
            files.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            # 只返回存在的文件
            existing_files = []
            for file_info in files[:max_count]:
                file_path = file_info.get('path', '')
                if os.path.exists(file_path):
                    existing_files.append(file_info)
            return existing_files
        except Exception as e:
            print(f"读取Excel文件配置失败: {e}")
            return []

    def _get_cached_index_constituent_code_sets(self):
        """成份股集合带缓存(默认 6 小时),避免每次问财选股重复拉取。"""
        import time
        ttl = 6 * 3600
        ent = getattr(self, "_idx_constituent_cache", None)
        if ent and len(ent) == 4 and (time.time() - ent[0]) < ttl:
            return ent[1], ent[2], ent[3]
        hs300, zz500, kc50 = self._load_a_share_index_constituent_code_sets()
        self._idx_constituent_cache = (time.time(), hs300, zz500, kc50)
        return hs300, zz500, kc50

    def _get_investment_prompt(self, option_name, option_desc, problem):
        """生成投资分析提示"""
        return f"""请针对以下投资类型进行专业分析:
投资类型:{option_name}
类型说明:{option_desc}
用户问题:{problem}
请提供以下方面的分析:
1. 该投资类型的特点和优势
2. 适合的投资人群和风险承受能力
3. 当前市场环境和投资机会
4. 具体的投资策略和建议
5. 需要注意的风险和注意事项
6. 推荐的配置比例和投资时机"""

    def _get_system_prompt(self, option_name, option_desc, problem):
        """生成投资系统分析提示"""
        return f"""请详细介绍以下投资系统:
投资系统:{option_name}
系统说明:{option_desc}
用户问题:{problem}
请提供以下方面的详细说明:
1. 该投资系统的核心理念和理论基础
2. 系统的具体操作方法和步骤
3. 适用的市场环境和投资标的
4. 系统的优势和局限性
5. 实际应用案例和注意事项
6. 如何结合其他系统进行优化
7. 针对用户问题的具体应用建议"""

    def _get_gambling_prompt(self, option_name, option_desc, problem):
        """生成概率/赌博分析提示"""
        return f"""请进行以下概率和风险分析:
分析工具:{option_name}
工具说明:{option_desc}
用户问题:{problem}
请提供以下方面的分析:
1. 该工具的计算原理和公式
2. 如何应用该工具进行决策
3. 具体的计算步骤和示例
4. 工具的适用场景和局限性
5. 针对用户问题的具体计算和建议
6. 风险提示和注意事项
7. 如何结合其他工具进行综合分析"""

    def _fetch_ai_search_result(self, ai_name, url, query):
        """抓取AI搜索结果并复制到文本标签页"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            # 尝试多种编码
            html_content = None
            used_encoding = None
            for encoding in ['utf-8', 'gbk', 'gb2312', 'big5', response.apparent_encoding]:
                try:
                    if encoding:
                        html_content = response.content.decode(encoding)
                        used_encoding = encoding
                        break
                except (UnicodeDecodeError, LookupError):
                    continue
            if not html_content:
                raise ValueError("未能获取网页内容")
            # 修复乱码
            html_content = self._fix_encoding(html_content)
            soup = BeautifulSoup(html_content, 'html.parser')
            for script in soup(["script", "style", "noscript"]):
                script.decompose()
            text_content = soup.get_text(separator='\n', strip=True)
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            cleaned_text = '\n'.join(lines).strip()
            # 修复乱码
            cleaned_text = self._fix_encoding(cleaned_text)
            if not cleaned_text:
                cleaned_text = f"⚠️ 未提取到有效文本内容。\n\n查询内容:{query}\n\n请手动在打开的AI网站中进行搜索和分析。"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            meta_lines = [
                "=" * 80,
                f"AI工具: {ai_name}",
                f"查询内容: {query}",
                f"链接: {url}",
                f"抓取时间: {timestamp}"
            ]
            if used_encoding:
                meta_lines.append(f"编码: {used_encoding}")
            meta_lines.append("=" * 80)
            header_text = '\n'.join(meta_lines)
            tab_title = f"{ai_name}_{datetime.now().strftime('%H:%M')}"
            full_text = f"{header_text}\n\n{cleaned_text}"
            # 修复乱码
            full_text = self._fix_encoding(full_text)
            def create_tab():
                self.create_text_tab(tab_title, full_text)
            self.root.after(0, create_tab)
        except Exception as exc:
            print(f"抓取AI搜索结果失败 {ai_name} ({url}): {exc}")
            # 即使抓取失败,也创建一个标签页提示用户
            def create_error_tab():
                error_text = f"AI搜索: {ai_name}\n查询: {query}\n链接: {url}\n\n⚠️ 无法自动抓取内容,请手动在打开的AI网站中进行搜索和分析。\n查询内容已复制到剪贴板。"
                self.root.clipboard_clear()
                self.root.clipboard_append(query)
                self._safe_update()
                self.create_text_tab(f"{ai_name}_搜索", error_text)
            self.root.after(0, create_error_tab)
        finally:
            if hasattr(self, "_market_nav_fetching"):
                self._market_nav_fetching.discard(url)

    def _get_stock_5day_flow_summary(self, stock_code: str) -> str:
        """获取单只股票最近5天大单/主力净资金流,返回简短描述字符串(供思维导图等使用)"""
        if not stock_code:
            return "无代码"
        try:
            net_flow_5days = None
            # 方法1: Tushare 主力资金
            if TS_AVAILABLE and (getattr(self, 'ts_token', None) or TS_DEFAULT_TOKEN):
                try:
                    if not getattr(self, 'ts_client', None):
                        self._ensure_tushare_client(self.ts_token or TS_DEFAULT_TOKEN)
                    ts_code = self._format_ts_code(stock_code)
                    end_date = datetime.now().strftime("%Y%m%d")
                    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
                    df = self.ts_client.moneyflow(ts_code=ts_code, start_date=start_date, end_date=end_date)
                    if df is not None and not df.empty:
                        df_sorted = df.sort_values('trade_date', ascending=False).head(5)
                        if len(df_sorted) > 0:
                            if 'net_mf_amount' in df_sorted.columns:
                                net_flow_5days = float(df_sorted['net_mf_amount'].sum()) / 10000
                            elif 'net_amount' in df_sorted.columns:
                                net_flow_5days = float(df_sorted['net_amount'].sum()) / 10000
                except Exception:
                    net_flow_5days = None
            # 方法2: AKShare 历史估算
            if net_flow_5days is None and AKSHARE_AVAILABLE:
                try:
                    hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                    if hist_data is not None and not hist_data.empty and len(hist_data) >= 5:
                        if "日期" in hist_data.columns:
                            hist_data = hist_data.sort_values("日期")
                        recent_5 = hist_data.tail(5)
                        close_col = next((c for c in recent_5.columns if '收盘' in str(c) or str(c).lower() == 'close'), None)
                        vol_col = next((c for c in recent_5.columns if '成交量' in str(c) or 'volume' in str(c).lower()), None)
                        if close_col:
                            total_flow = 0
                            for i in range(1, len(recent_5)):
                                cur, prev = recent_5.iloc[i], recent_5.iloc[i-1]
                                cp, pp = float(cur[close_col]), float(prev[close_col])
                                cv = float(cur.get(vol_col, 0)) if vol_col else 0
                                chg = (cp - pp) / pp if pp > 0 else 0
                                total_flow += (cv * cp * chg * 0.3)
                            net_flow_5days = total_flow / 10000
                except Exception:
                    net_flow_5days = None
            if net_flow_5days is not None:
                return f"最近5天大单资金流: {net_flow_5days:+.2f}万元"
            return "最近5天资金流: 暂无数据"
        except Exception as e:
            return f"最近5天资金流: 获取失败({str(e)[:20]})"

    def _get_stock_5day_pct_change(self, stock_code: str) -> str:
        """获取单只股票最近5日涨跌幅(5个交易日区间),返回简短描述(供思维导图等使用)"""
        if not stock_code:
            return "无代码"
        try:
            if not AKSHARE_AVAILABLE:
                return "最近5日涨跌幅: 需akshare"
            hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
            if hist_data is None or hist_data.empty or len(hist_data) < 5:
                return "最近5日涨跌幅: 暂无数据"
            if "日期" in hist_data.columns:
                hist_data = hist_data.sort_values("日期")
            else:
                hist_data = hist_data.sort_values("date") if "date" in hist_data.columns else hist_data
            recent_5 = hist_data.tail(5)
            close_col = next((c for c in recent_5.columns if '收盘' in str(c) or str(c).lower() == 'close'), None)
            if not close_col:
                return "最近5日涨跌幅: 无收盘列"
            first_close = float(recent_5.iloc[0][close_col])
            last_close = float(recent_5.iloc[-1][close_col])
            if first_close <= 0:
                return "最近5日涨跌幅: 数据异常"
            pct = (last_close - first_close) / first_close * 100
            return f"最近5日涨跌幅: {pct:+.2f}%"
        except Exception as e:
            return f"最近5日涨跌幅: 获取失败({str(e)[:15]})"

    def _fetch_stock_intro(self, stock_code, stock_name):
        """获取股票介绍信息(基本信息、所属板块、同板块股票)"""
        try:
            # 格式化数字为万/亿单位的辅助函数
            def format_large_number(value_str):
                """将大数字格式化为万/亿单位,保留3位小数"""
                try:
                    # 尝试转换为浮点数
                    value = float(value_str)
                    # 格式化:大于等于1亿,用亿;大于等于1万,用万;否则原样显示
                    if abs(value) >= 1e8:
                        # 转换为亿,保留3位小数
                        formatted = f"{value / 1e8:.3f}亿"
                        return formatted
                    elif abs(value) >= 1e4:
                        # 转换为万,保留3位小数
                        formatted = f"{value / 1e4:.3f}万"
                        return formatted
                    else:
                        # 小于1万的数字,如果原始值有小数则保留3位,否则显示整数
                        if value == int(value):
                            return str(int(value))
                        else:
                            return f"{value:.3f}"
                except (ValueError, TypeError):
                    # 如果无法转换为数字,返回原值
                    return value_str
            # 需要格式化的字段名(包含这些关键词的字段都会被格式化)
            numeric_fields = ['总股本', '流通股', '总市值', '流通市值', '市值', '股本',
                            '总资产', '净资产', '净利润', '营业收入', '成交额', '成交量',
                            '换手率', '市盈率', '市净率']
            result_lines = [f"股票名称: {stock_name}", f"股票代码: {stock_code}", ""]
            akshare_success = False
            # 使用akshare获取股票基本信息
            try:
                import akshare as ak
                # 获取股票基本信息
                stock_info = ak.stock_individual_info_em(symbol=stock_code)
                if stock_info is not None and not stock_info.empty:
                    result_lines.append("=== 基本信息 ===")
                    for _, row in stock_info.iterrows():
                        if len(row) >= 2:
                            key = str(row.iloc[0]).strip()
                            value = str(row.iloc[1]).strip()
                            if key and value and value != "nan":
                                # 检查是否需要格式化数字
                                need_format = any(field in key for field in numeric_fields)
                                if need_format:
                                    # 尝试提取数字部分(去除可能的单位符号)
                                    # 例如 "86139015.0" 或 "8217662031.000001"
                                    try:
                                        # 先尝试直接转换
                                        formatted_value = format_large_number(value)
                                        result_lines.append(f"{key}: {formatted_value}")
                                    except:
                                        result_lines.append(f"{key}: {value}")
                                else:
                                    result_lines.append(f"{key}: {value}")
                    result_lines.append("")
                    akshare_success = True
                # 获取所属板块
                try:
                    concept_data = safe_call(ak.stock_board_concept_name_em, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_em")
                    if concept_data is not None and not concept_data.empty:
                        # 查找包含该股票的板块
                        stock_concepts = []
                        for _, row in concept_data.iterrows():
                            concept_name = str(row.get('板块名称', '')).strip()
                            if concept_name:
                                try:
                                    concept_stocks = ak.stock_board_concept_cons_em(symbol=concept_name)
                                    if concept_stocks is not None and not concept_stocks.empty:
                                        codes = concept_stocks.get('代码', [])
                                        if stock_code in [str(c).strip() for c in codes]:
                                            stock_concepts.append(concept_name)
                                except:
                                    continue
                        if stock_concepts:
                            result_lines.append("=== 所属板块 ===")
                            for concept in stock_concepts[:10]:  # 最多显示10个板块
                                result_lines.append(f"• {concept}")
                            result_lines.append("")
                            # 获取同板块股票(取第一个板块)
                            if stock_concepts:
                                try:
                                    same_concept_stocks = ak.stock_board_concept_cons_em(symbol=stock_concepts[0])
                                    if same_concept_stocks is not None and not same_concept_stocks.empty:
                                        result_lines.append(f"=== 同板块股票 ({stock_concepts[0]}) ===")
                                        for idx, (_, row) in enumerate(same_concept_stocks.iterrows()[:20]):  # 最多显示20只
                                            code = str(row.get('代码', '')).strip()
                                            name = str(row.get('名称', '')).strip()
                                            if code and name and code != stock_code:
                                                result_lines.append(f"{idx+1}. {name} ({code})")
                                        result_lines.append("")
                                except:
                                    pass
                except Exception as e:
                    result_lines.append(f"获取板块信息失败: {str(e)[:50]}")
                    result_lines.append("")
            except Exception as e:
                result_lines.append(f"获取股票信息失败: {str(e)[:50]}")
            # 如果akshare失败,尝试使用tushare
            if not akshare_success or len(result_lines) <= 3:
                try:
                    # 转换股票代码格式(tushare使用6位数字,不带前缀)
                    ts_code = stock_code
                    if '.' in stock_code:
                        ts_code = stock_code.split('.')[-1]
                    elif len(stock_code) > 6:
                        ts_code = stock_code[-6:]
                    # 确保tushare客户端可用
                    client = self._ensure_tushare_client()
                    # 获取股票基本信息
                    try:
                        stock_basic = client.stock_basic(ts_code=ts_code, fields='ts_code,symbol,name,area,industry,list_date')
                        if stock_basic is not None and not stock_basic.empty:
                            if not akshare_success:
                                result_lines = [f"股票名称: {stock_name}", f"股票代码: {stock_code}", ""]
                                result_lines.append("=== 基本信息 (Tushare) ===")
                            else:
                                result_lines.append("=== 补充信息 (Tushare) ===")
                            for _, row in stock_basic.iterrows():
                                for col in stock_basic.columns:
                                    key = col
                                    value = str(row[col]).strip()
                                    if value and value != "nan" and value != "None":
                                        # 转换字段名为中文
                                        key_map = {
                                            'ts_code': 'Tushare代码',
                                            'symbol': '股票代码',
                                            'name': '股票名称',
                                            'area': '所在地区',
                                            'industry': '所属行业',
                                            'list_date': '上市日期'
                                        }
                                        key_cn = key_map.get(key, key)
                                        result_lines.append(f"{key_cn}: {value}")
                            result_lines.append("")
                            # 获取股票概念板块
                            try:
                                concept_data = client.concept_detail(ts_code=ts_code, fields='concept_name')
                                if concept_data is not None and not concept_data.empty:
                                    concepts = concept_data['concept_name'].unique().tolist()
                                    if concepts:
                                        result_lines.append("=== 所属概念板块 (Tushare) ===")
                                        for concept in concepts[:10]:
                                            result_lines.append(f"• {concept}")
                                        result_lines.append("")
                            except:
                                pass
                            akshare_success = True  # 标记为成功
                    except Exception as e:
                        if not akshare_success:
                            result_lines.append(f"Tushare获取股票信息失败: {str(e)[:50]}")
                            result_lines.append("")
                except Exception as e:
                    if not akshare_success:
                        result_lines.append(f"Tushare初始化失败: {str(e)[:50]}")
                        result_lines.append("")
            # 如果所有数据源都失败,返回特殊标记用于网页嵌入
            if not akshare_success or len(result_lines) <= 3:
                return {"type": "web_embed", "stock_code": stock_code, "stock_name": stock_name}
            return "\n".join(result_lines) if result_lines else {"type": "web_embed", "stock_code": stock_code, "stock_name": stock_name}
        except Exception:
            return {"type": "web_embed", "stock_code": stock_code, "stock_name": stock_name}

    def _fetch_moneyflow_data(self, stock_code, stock_name):
        """获取股票大单分析数据(使用tushare的moneyflow接口)"""
        try:
            # 转换股票代码格式为tushare格式
            ts_code = stock_code
            if '.' not in stock_code and len(stock_code) == 6:
                if stock_code.startswith(('5', '6')):
                    ts_code = f"{stock_code}.SH"
                else:
                    ts_code = f"{stock_code}.SZ"
            # 获取今日日期
            today = datetime.now().strftime('%Y%m%d')
            # 确保tushare客户端可用
            try:
                client = self._ensure_tushare_client()
            except Exception as e:
                return f"Tushare初始化失败: {e!s}\n\n请先登录Tushare"
            # 调用moneyflow接口获取最近6天的数据
            try:
                # 获取最近6个交易日的数据
                end_date = today
                start_date = (datetime.now() - timedelta(days=14)).strftime('%Y%m%d')  # 扩大范围确保能找到6个交易日
                df = client.moneyflow(ts_code=ts_code, start_date=start_date, end_date=end_date)
                if df is None or df.empty:
                        # 尝试使用akshare获取实时大单数据
                        try:
                            if AKSHARE_AVAILABLE:
                                # 尝试使用akshare获取实时资金流向数据
                                try:
                                    # 获取实时资金流向排名数据,查找目标股票
                                    money_flow_df = ak.stock_individual_fund_flow_rank(indicator="今日")
                                    if money_flow_df is not None and not money_flow_df.empty:
                                        # 查找目标股票
                                        stock_row = money_flow_df[money_flow_df['代码'] == stock_code]
                                        if not stock_row.empty:
                                            row = stock_row.iloc[0]
                                            # 提取实时大单数据
                                            buy_lg_amount_ak = float(row.get('大单净流入', 0)) / 10000  # 转换为万元
                                            buy_elg_amount_ak = float(row.get('超大单净流入', 0)) / 10000  # 转换为万元
                                            # 构建实时数据显示
                                            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                            result_lines_ak = [
                                                f"股票名称: {stock_name}",
                                                f"股票代码: {stock_code}",
                                                f"数据时间: {current_time}(实时数据)",
                                                "",
                                                "=" * 60,
                                                "实时大单分析(akshare数据)",
                                                "=" * 60,
                                                f"大单净流入: {buy_lg_amount_ak:,.2f} 万元",
                                                f"超大单净流入: {buy_elg_amount_ak:,.2f} 万元",
                                                f"大单+超大单净流入: {buy_lg_amount_ak + buy_elg_amount_ak:,.2f} 万元",
                                                "",
                                                "注意:此为实时数据,可能为今日累计或最近60分钟内的数据",
                                            ]
                                            # 如果有大单或超大单,用加粗红色显示
                                            if buy_lg_amount_ak != 0 or buy_elg_amount_ak != 0:
                                                result_lines_ak.append("")
                                                result_lines_ak.append("=" * 60)
                                                result_lines_ak.append("⚠️ 大单异动提示")
                                                result_lines_ak.append("=" * 60)
                                                if buy_lg_amount_ak > 0:
                                                    result_lines_ak.append(f"【大单净流入】{buy_lg_amount_ak:,.2f} 万元")
                                                if buy_elg_amount_ak > 0:
                                                    result_lines_ak.append(f"【超大单净流入】{buy_elg_amount_ak:,.2f} 万元")
                                            return "\n".join(result_lines_ak)
                                    # 如果排名数据中没有,尝试获取个股实时资金流向
                                    try:
                                        # 使用akshare的实时资金流向接口(新版仅 stock + market,无 indicator)
                                        individual_flow = ak.stock_individual_fund_flow(
                                            stock=stock_code, market=_akshare_fund_flow_market(stock_code)
                                        )
                                        if individual_flow is not None and not individual_flow.empty:
                                            # 处理实时资金流向数据
                                            latest_row = individual_flow.iloc[-1] if len(individual_flow) > 0 else None
                                            if latest_row is not None:
                                                def _ff_val(row, *keys):
                                                    for k in keys:
                                                        if k in row.index and row.get(k) is not None:
                                                            try:
                                                                return float(row.get(k))
                                                            except (TypeError, ValueError):
                                                                pass
                                                    return 0.0
                                                buy_lg_ak = _ff_val(latest_row, '大单净流入-净额', '大单净流入') / 10000
                                                buy_elg_ak = _ff_val(latest_row, '超大单净流入-净额', '超大单净流入') / 10000
                                                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                                result_lines_ak = [
                                                    f"股票名称: {stock_name}",
                                                    f"股票代码: {stock_code}",
                                                    f"数据时间: {current_time}(实时数据)",
                                                    "",
                                                    "=" * 60,
                                                    "实时大单分析(akshare数据)",
                                                    "=" * 60,
                                                    f"大单净流入: {buy_lg_ak:,.2f} 万元",
                                                    f"超大单净流入: {buy_elg_ak:,.2f} 万元",
                                                    f"大单+超大单净流入: {buy_lg_ak + buy_elg_ak:,.2f} 万元",
                                                ]
                                                if buy_lg_ak != 0 or buy_elg_ak != 0:
                                                    result_lines_ak.append("")
                                                    result_lines_ak.append("⚠️ 检测到大单或超大单异动")
                                                return "\n".join(result_lines_ak)
                                    except:
                                        pass
                                except Exception:
                                    pass
                        except:
                            pass
                        return f"未获取到 {stock_name} ({stock_code}) 的大单数据\n\n可能原因:\n1. 今日非交易日\n2. 股票代码不正确\n3. Tushare积分不足(需要至少2000积分)\n4. akshare实时数据获取失败"
                # 处理多天数据:获取最近6天的数据
                if df is not None and not df.empty:
                    # 按日期排序(从新到旧,降序)
                    df = df.sort_values('trade_date', ascending=False)
                    # 取最近6条数据(最多6天,已经是按日期降序排列)
                    recent_days = df.head(6)
                    # 构建结果文本(返回结构化数据以便后续应用颜色)
                    result_data = {
                        "header": [
                            f"股票名称: {stock_name}",
                            f"股票代码: {stock_code}",
                            "数据日期范围: 最近6个交易日(从近到远)",
                            "",
                            "=" * 50,
                        ],
                        "days": []
                    }
                    # 遍历每一天的数据(从近到远)
                    for idx, row in recent_days.iterrows():
                        day_trade_date = row.get('trade_date', '')
                        # 格式化日期显示
                        if len(day_trade_date) == 8:
                            formatted_date = f"{day_trade_date[:4]}-{day_trade_date[4:6]}-{day_trade_date[6:8]}"
                        else:
                            formatted_date = day_trade_date
                        # 提取数据
                        buy_lg_amount = float(row.get('buy_lg_amount', 0))  # 大单买入金额(万元)
                        sell_lg_amount = float(row.get('sell_lg_amount', 0))  # 大单卖出金额(万元)
                        buy_elg_amount = float(row.get('buy_elg_amount', 0))  # 特大单买入金额(万元)
                        sell_elg_amount = float(row.get('sell_elg_amount', 0))  # 特大单卖出金额(万元)
                        net_mf_amount = float(row.get('net_mf_amount', 0))  # 净流入额(万元)
                        # 计算各项净流入
                        lg_net = buy_lg_amount - sell_lg_amount  # 大单净流入
                        elg_net = buy_elg_amount - sell_elg_amount  # 特大单净流入
                        total_lg_net = lg_net + elg_net  # 大单+特大单净流入(主力净额)
                        # 存储每天的数据(包含颜色信息)
                        result_data["days"].append({
                            "date": formatted_date,
                            "elg_net": elg_net,
                            "lg_net": lg_net,
                            "total_lg_net": total_lg_net,  # 主力净额
                            "net_mf_amount": net_mf_amount
                        })
                    # 返回结构化数据
                    return result_data
                # 如果没有数据,返回错误信息
                return f"未获取到 {stock_name} ({stock_code}) 的大单数据"
            except Exception as e:
                error_msg = str(e)
                if "2000" in error_msg or "积分" in error_msg:
                    return f"获取大单数据失败: Tushare积分不足\n\n需要至少2000积分才能调用moneyflow接口\n当前错误: {error_msg}"
                return f"获取大单数据失败: {error_msg}"
        except Exception as e:
            return f"获取大单分析失败: {e!s}"

    def _fetch_recent_changes(self, stock_code, stock_name):
        """获取近日涨跌幅:1.最近10日的涨跌幅(从近到远) 2.最近5日、10日、20日、60日的最高值、最低值"""
        try:
            result_lines = [f"股票名称: {stock_name}", f"股票代码: {stock_code}", ""]
            # 尝试使用akshare获取数据
            hist_data = None
            error_msgs = []
            # 方法1: 尝试使用akshare
            try:
                if AKSHARE_AVAILABLE:
                    import akshare as ak
                    # 获取历史数据
                    try:
                        hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                    except Exception as e1:
                        # 如果失败,尝试不使用qfq调整
                        try:
                            hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="")
                        except Exception:
                            error_msgs.append(f"akshare获取失败: {str(e1)[:50]}")
                else:
                    error_msgs.append("akshare不可用")
            except ImportError:
                error_msgs.append("akshare未安装")
            except Exception as e:
                error_msgs.append(f"akshare调用异常: {str(e)[:50]}")
            # 方法2: 如果akshare失败,尝试使用Tushare
            if (hist_data is None or hist_data.empty) and hasattr(self, '_ensure_tushare_client'):
                try:
                    client = self._ensure_tushare_client()
                    # 转换股票代码格式
                    ts_code = stock_code
                    if '.' not in stock_code:
                        if len(stock_code) == 6:
                            if stock_code.startswith(('5', '6')):
                                ts_code = f"{stock_code}.SH"
                            else:
                                ts_code = f"{stock_code}.SZ"
                    # 获取最近60天的日线数据
                    from datetime import datetime, timedelta
                    end_date = datetime.now().strftime('%Y%m%d')
                    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
                    tushare_data = client.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                    if tushare_data is not None and not tushare_data.empty:
                        # 转换为akshare格式的DataFrame
                        import pandas as pd
                        hist_data = pd.DataFrame({
                            '日期': tushare_data['trade_date'],
                            '收盘': tushare_data['close'],
                            '最高': tushare_data['high'],
                            '最低': tushare_data['low'],
                            '开盘': tushare_data['open'],
                            '成交量': tushare_data['vol'],
                            '成交额': tushare_data['amount']
                        })
                except Exception as e:
                    error_msgs.append(f"Tushare获取失败: {str(e)[:50]}")
            if hist_data is not None and not hist_data.empty:
                # 获取需要的列(尝试多种可能的列名)
                close_col = None
                high_col = None
                low_col = None
                date_col = None
                # 查找日期列
                for col in hist_data.columns:
                    col_str = str(col).lower()
                    if '日期' in col_str or 'date' in col_str or 'trade_date' in col_str:
                        date_col = col
                        break
                if date_col is None:
                    date_col = hist_data.columns[0]
                # 查找收盘价列
                for col in hist_data.columns:
                    col_str = str(col).lower()
                    if '收盘' in col_str or 'close' in col_str:
                        close_col = col
                        break
                if close_col is None and len(hist_data.columns) >= 2:
                    close_col = hist_data.columns[-2]  # 通常收盘价在倒数第二列
                # 查找最高价列
                for col in hist_data.columns:
                    col_str = str(col).lower()
                    if '最高' in col_str or 'high' in col_str:
                        high_col = col
                        break
                # 查找最低价列
                for col in hist_data.columns:
                    col_str = str(col).lower()
                    if '最低' in col_str or 'low' in col_str:
                        low_col = col
                        break
                if close_col is None:
                    result_lines.append("错误: 无法找到收盘价列")
                    result_lines.append(f"可用列: {', '.join(hist_data.columns.tolist())}")
                    return "\n".join(result_lines)
                if len(hist_data) > 0:
                    # 确保日期列是字符串类型,然后排序
                    try:
                        hist_data[date_col] = hist_data[date_col].astype(str)
                        # 按日期排序(从旧到新)
                        hist_data = hist_data.sort_values(date_col)
                    except Exception as e:
                        result_lines.append(f"日期排序失败: {str(e)[:50]}")
                        # 如果排序失败,直接使用原始数据
                    # 获取最近的数据(从新到旧)
                    recent_data = hist_data.tail(min(60, len(hist_data))).iloc[::-1]  # 反转,从近到远
                    # 1. 显示最近10日的涨跌幅(从近到远)
                    result_lines.append("=" * 50)
                    result_lines.append("最近10日涨跌幅(从近到远)")
                    result_lines.append("=" * 50)
                    if len(recent_data) >= 2:
                        # 获取最近10天的数据(从近到远)
                        recent_10_days = recent_data.head(10)
                        # 转换为列表以便按位置索引访问
                        recent_10_list = list(recent_10_days.iterrows())
                        for i, (idx, row) in enumerate(recent_10_list):
                            try:
                                date = str(row[date_col])
                                close_price = float(row[close_col])
                            except (ValueError, KeyError) as e:
                                result_lines.append(f"数据解析错误(第{i+1}行): {str(e)[:30]}")
                                continue
                            # 计算涨跌幅(相对于前一天)
                            # recent_data是从近到远排序的,所以i=0是最新的一天
                            # 要计算第i天的涨跌幅,需要与第i+1天(前一天)比较
                            if i < len(recent_10_list) - 1:
                                # 获取前一天的数据
                                _prev_idx, prev_row = recent_10_list[i + 1]
                                prev_close = float(prev_row[close_col])
                                change_pct = ((close_price - prev_close) / prev_close) * 100
                                change_str = f"{change_pct:+.2f}%"
                            else:
                                # 如果是最后一天(最早的一天),无法计算涨跌幅
                                change_str = "--"
                            # 格式化日期显示
                            if len(date) == 10 and '-' in date:
                                formatted_date = date
                            elif len(date) == 8:
                                formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
                            else:
                                formatted_date = date
                            result_lines.append(f"{formatted_date}: 收盘价 {close_price:.2f}, 涨跌幅 {change_str}")
                    else:
                        result_lines.append("数据不足,无法显示最近10日涨跌幅")
                    # 2. 显示最近5日、10日、20日、60日的最高值、最低值
                    result_lines.append("")
                    result_lines.append("=" * 50)
                    result_lines.append("各周期最高值、最低值")
                    result_lines.append("=" * 50)
                    if high_col and low_col:
                        periods = [5, 10, 20, 60]
                        current_price = float(recent_data.iloc[0][close_col])  # 最新价格
                        for period in periods:
                            if len(recent_data) >= period:
                                # 获取最近period天的数据
                                period_data = recent_data.head(period)
                                # 计算最高值和最低值
                                high_values = period_data[high_col].astype(float)
                                low_values = period_data[low_col].astype(float)
                                max_high = high_values.max()
                                min_low = low_values.min()
                                # 计算相对于当前价格的差值
                                high_diff = current_price - max_high
                                low_diff = current_price - min_low
                                high_diff_pct = (high_diff / max_high) * 100 if max_high > 0 else 0
                                low_diff_pct = (low_diff / min_low) * 100 if min_low > 0 else 0
                                result_lines.append(f"\n最近{period}日:")
                                result_lines.append(f"  最高值: {max_high:.2f} (当前价差: {high_diff:+.2f}, {high_diff_pct:+.2f}%)")
                                result_lines.append(f"  最低值: {min_low:.2f} (当前价差: {low_diff:+.2f}, {low_diff_pct:+.2f}%)")
                            else:
                                result_lines.append(f"\n最近{period}日: 数据不足(仅{len(recent_data)}天)")
                    else:
                        result_lines.append("无法获取最高价、最低价数据")
                else:
                    result_lines.append("无法获取价格数据")
            else:
                result_lines.append("无法获取历史数据")
                if error_msgs:
                    result_lines.append("\n错误详情:")
                    for msg in error_msgs:
                        result_lines.append(f"  - {msg}")
            return "\n".join(result_lines) if result_lines else "无法获取涨跌幅信息"
        except Exception as e:
            return f"获取涨跌幅失败: {e!s}\n\n请检查:\n1. 股票代码是否正确\n2. akshare或Tushare是否可用\n3. 网络连接是否正常"

    def _prediction_fetch_market_article_snippets(self, max_n=10, body_chars=900):
        """从东方财富财经列表页抓取多篇报道的标题、链接与正文摘要(供 AI 归纳观点与板块)。"""
        import re
        try:
            import requests
        except Exception:
            return []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        urls = []
        for lp in (
            "https://finance.eastmoney.com/a/cjjyw.html",
            "https://finance.eastmoney.com/a/czpnc.html",
        ):
            try:
                r = requests.get(lp, headers=headers, timeout=18)
                r.encoding = getattr(r, "apparent_encoding", None) or r.encoding or "utf-8"
                for u in re.findall(r"https://finance\.eastmoney\.com/a/\d+\.html", r.text):
                    if u not in urls:
                        urls.append(u)
                    if len(urls) >= max_n * 3:
                        break
            except Exception:
                continue
            if len(urls) >= max_n:
                break
        out = []
        for url in urls[:max_n]:
            try:
                rr = requests.get(url, headers=headers, timeout=14)
                rr.encoding = getattr(rr, "apparent_encoding", None) or rr.encoding or "utf-8"
                m = re.search(r"<title>([^<]+)</title>", rr.text, re.IGNORECASE)
                title = (m.group(1).strip() if m else url).replace("_东方财富网", "").replace("- 东方财富网", "").strip()
                body = re.sub(r"<script[\s\S]*?</script>", " ", rr.text, flags=re.IGNORECASE)
                body = re.sub(r"<style[\s\S]*?</style>", " ", body, flags=re.IGNORECASE)
                body = re.sub(r"<[^>]+>", " ", body)
                body = re.sub(r"\s+", " ", body).strip()[:body_chars]
                if len(body) < 80:
                    continue
                out.append({"title": title, "url": url, "snippet": body})
            except Exception:
                continue
        return out

    def _fetch_ddg_abstract(self, query: str, max_len: int = 520) -> str:
        """DuckDuckGo Instant Answer 摘要,用于子图说明不足时的补充(不保证命中)。"""
        import urllib.parse
        q = (query or "").strip()
        if len(q) < 2:
            return ""
        try:
            url = (
                "https://api.duckduckgo.com/?q="
                + urllib.parse.quote(q[:200])
                + "&format=json&no_html=1&skip_disambig=1"
            )
            r = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (compatible; StockSentiment/1.0)"},
            )
            if r.status_code != 200:
                return ""
            data = r.json()
            abst = (data.get("AbstractText") or "").strip()
            if abst:
                return abst[:max_len]
            for t in data.get("RelatedTopics") or []:
                if isinstance(t, dict):
                    txt = (t.get("Text") or "").strip()
                    if txt:
                        return txt[:max_len]
        except Exception:
            return ""
        return ""

    def _get_next_month_first_trade(self, pro):
        """下月第一个交易日"""
        import datetime as dt
        today = dt.date.today()
        if today.month == 12:
            next_m = dt.date(today.year + 1, 1, 1)
        else:
            next_m = dt.date(today.year, today.month + 1, 1)
        # 找下月的交易日
        cal = pro.trade_cal(exchange="SSE",
            start_date=next_m.strftime("%Y%m%d"),
            end_date=(next_m + dt.timedelta(days=10)).strftime("%Y%m%d"), is_open="1")
        if cal is not None and len(cal) > 0:
            return str(cal["cal_date"].iloc[0])
        return next_m.strftime("%Y%m%d")

    def _get_month_last_trade(self, pro):
        """本月最后一个交易日"""
        import datetime as dt
        today = dt.date.today()
        if today.month == 12:
            next_m = dt.date(today.year + 1, 1, 1)
        else:
            next_m = dt.date(today.year, today.month + 1, 1)
        cal = pro.trade_cal(exchange="SSE",
            start_date=(next_m - dt.timedelta(days=20)).strftime("%Y%m%d"),
            end_date=(next_m - dt.timedelta(days=1)).strftime("%Y%m%d"), is_open="1")
        if cal is not None and len(cal) > 0:
            return str(cal["cal_date"].iloc[-1])
        return (next_m - dt.timedelta(days=1)).strftime("%Y%m%d")

    def _get_major_index_pct_from_tushare(self):
        """主要指数当日涨跌幅:Tushare `index_daily`(需 token;比东财现货接口更稳)。"""
        out = {}
        idx_map = {
            "上证指数": "000001.SH",
            "深证成指": "399001.SZ",
            "创业板指": "399006.SZ",
            "沪深300": "000300.SH",
            "中证500": "000905.SH",
            "科创50": "000688.SH",
            "中证1000": "000852.SH",
            "北证50": "899050.BJ",
        }
        if not TS_AVAILABLE or not (getattr(self, "ts_token", None) or TS_DEFAULT_TOKEN):
            return out
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=15)).strftime("%Y%m%d")
        try:
            self._ensure_tushare_client(self.ts_token or TS_DEFAULT_TOKEN)
            for cn, ts_code in idx_map.items():
                try:
                    df = self.ts_client.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                    if df is None or df.empty:
                        continue
                    df = df.sort_values("trade_date").tail(2).reset_index(drop=True)
                    if len(df) < 2:
                        continue
                    prev_close = float(df.iloc[-2]["close"])
                    close = float(df.iloc[-1]["close"])
                    if prev_close <= 0:
                        continue
                    out[cn] = (close / prev_close - 1.0) * 100.0
                except Exception:
                    continue
        except Exception:
            pass
        return out

    def _get_major_index_pct_from_akshare(self):
        """东财指数现货涨跌幅:AKShare 补缺用。"""
        out = {}
        try:
            import akshare as ak
            df = safe_call(ak.stock_zh_index_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_index_spot_em")
            if df is None or df.empty:
                return out
            name_col = "名称" if "名称" in df.columns else None
            pct_col = "涨跌幅" if "涨跌幅" in df.columns else None
            if not name_col or not pct_col:
                return out
            want = (
                "上证指数",
                "深证成指",
                "创业板指",
                "沪深300",
                "中证500",
                "科创50",
                "中证1000",
                "北证50",
            )
            for _, row in df.iterrows():
                nm = str(row.get(name_col, "")).strip()
                if nm not in want:
                    continue
                p = pd.to_numeric(row.get(pct_col), errors="coerce")
                if pd.notna(p):
                    out[nm] = float(p)
        except Exception:
            pass
        return out

    def _get_major_index_pct_dict(self):
        """指数涨跌幅:优先 Tushare 日线;缺项由东财指数现货 AKShare 补齐。"""
        out = dict(self._get_major_index_pct_from_tushare())
        for k, v in self._get_major_index_pct_from_akshare().items():
            if k not in out or out.get(k) is None:
                out[k] = v
        return out

    def _fetch_concept_board_leader_summary(self, top_n=18):
        """题材热度:优先同花顺概念 AKShare;失败则回退选股通主题库网页解析。"""
        import re
        lines = []
        keywords = (
            "人工智能",
            "AI",
            "券商",
            "证券",
            "半导体",
            "芯片",
            "新能源",
            "锂电池",
            "光伏",
            "机器人",
            "数字经济",
            "华为",
            "算力",
            "信创",
            "传媒",
            "游戏",
            "中特估",
            "红利",
        )
        hits = []
        err_ak = None
        try:
            import akshare as ak
            df = safe_call(ak.stock_board_concept_name_ths, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_ths")
            if df is None or df.empty:
                raise RuntimeError("AKShare 概念榜为空")
            pct_col = "涨跌幅" if "涨跌幅" in df.columns else None
            name_col = "板块名称" if "板块名称" in df.columns else ("名称" if "名称" in df.columns else df.columns[0])
            if pct_col is None:
                raise RuntimeError("无涨跌幅列")
            df = df.copy()
            df["_p"] = pd.to_numeric(df[pct_col], errors="coerce")
            df = df.dropna(subset=["_p"]).sort_values("_p", ascending=False)
            head = df.head(top_n)
            lines.append(f"══ 概念板块涨幅前 {top_n}(同花顺口径 · AKShare,可用时)══")
            for _, row in head.iterrows():
                nm = str(row.get(name_col, "")).strip()
                p = float(row["_p"])
                flag = " ★" if any(k in nm for k in keywords) else ""
                lines.append(f"  · {nm}: {p:+.2f}%{flag}")
                if any(k in nm for k in keywords):
                    hits.append((nm, p))
            strong = [h for h in hits if h[1] > 0]
            if strong:
                lines.append("")
                lines.append("keyword 命中(人工智能/券商/半导体等)涨势居前:" + ",".join(f"{a}({b:+.2f}%)" for a, b in strong[:12]))
            return lines, hits
        except Exception as e_ak:
            err_ak = str(e_ak)
        try:
            sectors = self._fetch_xuangutong_full_no_dedup() or []
            scored = []
            for s in sectors:
                nm = str(s.get("板块名", "")).strip()
                if not nm or nm.startswith("排序"):
                    continue
                raw = s.get("涨跌幅") or ""
                t = str(raw).strip().replace("%", "")
                m = re.search(r"[+-]?\d+\.?\d*", t)
                if not m:
                    continue
                try:
                    p = float(m.group(0))
                except ValueError:
                    continue
                scored.append((nm, p))
            scored.sort(key=lambda x: x[1], reverse=True)
            if not scored:
                raise RuntimeError("选股通未解析到有效板块")
            lines = []
            if err_ak:
                lines.append(f"(同花顺概念 AKShare 不可用:{err_ak})")
            lines.append(f"══ 主题板块涨幅前 {top_n}(选股通 zhutiku · 网页解析)══")
            hits = []
            for nm, p in scored[:top_n]:
                flag = " ★" if any(k in nm for k in keywords) else ""
                lines.append(f"  · {nm}: {p:+.2f}%{flag}")
                if any(k in nm for k in keywords):
                    hits.append((nm, p))
            strong = [h for h in hits if h[1] > 0]
            if strong:
                lines.append("")
                lines.append("keyword 命中涨势居前:" + ",".join(f"{a}({b:+.2f}%)" for a, b in strong[:12]))
            return lines, hits
        except Exception as e_xg:
            tail = err_ak or "AKShare 异常"
            return [f"(概念板块:AKShare「{tail}」;选股通「{e_xg}」)"], []

    def _fetch_recent_daily_closes(self, stock_code: str, days: int = 15,
                                   source: str = "default", token: str | None = None,
                                   return_volume: bool = False):
        """获取近期日K收盘价列表,必要时返回成交量
        优先使用Tushare,如果不可用或失败则使用AKShare"""
        if not stock_code:
            raise ValueError("缺少股票代码")
        days = max(days, 3)
        force_tushare_only = (source == "tushare")
        force_ak_only = (source == "akshare")
        # 优先顺序控制:默认优先Tushare;可强制某一数据源
        token_to_use = token or self.ts_token or TS_DEFAULT_TOKEN
        if force_tushare_only and not TS_AVAILABLE:
            raise ValueError("当前环境未安装Tushare,无法获取数据")
        if _should_skip_akshare():
            force_tushare_only = True
            force_ak_only = False
        use_tushare_first = (not force_ak_only) and (TS_AVAILABLE and token_to_use)
        tushare_error = None
        if use_tushare_first:
            try:
                client = self._ensure_tushare_client(token_to_use)
                ts_code = self._format_ts_code(stock_code)
                end_date = datetime.now().strftime("%Y%m%d")
                start_date = (datetime.now() - timedelta(days=days * 3)).strftime("%Y%m%d")
                df = client.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                if df is not None and not df.empty:
                    df = df.sort_values("trade_date")
                    closes = df["close"].astype(float).tolist()
                    dates = df["trade_date"].tolist()
                    if return_volume:
                        volumes = df["vol"].astype(float).tolist()
                        return dates[-days:], closes[-days:], volumes[-days:]
                    return dates[-days:], closes[-days:]
                else:
                    tushare_error = ValueError("Tushare返回空数据")
                    print(f"Tushare返回空数据,切换到AKShare (股票代码: {stock_code})")
            except Exception as e:
                tushare_error = e
                print(f"Tushare获取数据失败,切换到AKShare (股票代码: {stock_code}): {e!s}")
        if force_tushare_only and tushare_error:
            raise ValueError(f"Tushare获取数据失败: {tushare_error}")
        # 如果Tushare不可用或失败,使用AKShare
        if not force_tushare_only:
            try:
                # 尝试使用akshare获取历史数据
                hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                if hist_data is None or hist_data.empty:
                    raise ValueError("未获取到AKShare日线数据")
                # 确保数据按日期排序
                if "日期" in hist_data.columns:
                    hist_data = hist_data.sort_values("日期")
                elif "date" in hist_data.columns:
                    hist_data = hist_data.sort_values("date")
                hist_data = hist_data.tail(days)
                # 尝试多种可能的列名
                close_col = None
                date_col = None
                volume_col = None
                for col in hist_data.columns:
                    col_lower = str(col).lower()
                    if close_col is None and ('收盘' in str(col) or 'close' in col_lower):
                        close_col = col
                    if date_col is None and ('日期' in str(col) or 'date' in col_lower):
                        date_col = col
                    if volume_col is None and ('成交量' in str(col) or 'volume' in col_lower):
                        volume_col = col
                if close_col is None:
                    raise ValueError(f"未找到收盘价列,可用列: {list(hist_data.columns)}")
                if date_col is None:
                    raise ValueError(f"未找到日期列,可用列: {list(hist_data.columns)}")
                closes = hist_data[close_col].astype(float).tolist()
                dates = hist_data[date_col].astype(str).tolist()
                if return_volume:
                    if volume_col and volume_col in hist_data.columns:
                        volumes = hist_data[volume_col].astype(float).tolist()
                        return dates, closes, volumes
                    else:
                        # 如果没有成交量列,返回空列表
                        volumes = [0.0] * len(closes)
                    return dates, closes, volumes
                return dates, closes
            except Exception as e:
                _mark_akshare_failed(str(e))
                error_msg = f"获取AKShare日线数据失败: {e!s}"
                print(error_msg)
                raise ValueError(error_msg)
        raise ValueError("无法获取日线数据")

    def _fetch_recent_daily_ohlc(self, stock_code: str, days: int = 25,
                                 source: str = "default", token: str | None = None):
        """获取近期日K的日期、最高、最低、收盘,与一键分析同源:优先 Tushare,失败则 AKShare。
        返回 (dates, highs, lows, closes),均为等长列表。"""
        if not stock_code:
            raise ValueError("缺少股票代码")
        days = max(days, 5)
        force_tushare_only = (source == "tushare")
        force_ak_only = (source == "akshare")
        token_to_use = token or self.ts_token or TS_DEFAULT_TOKEN
        if _should_skip_akshare():
            force_tushare_only = True
            force_ak_only = False
        use_tushare_first = (not force_ak_only) and (TS_AVAILABLE and token_to_use)
        tushare_error = None
        if use_tushare_first:
            try:
                client = self._ensure_tushare_client(token_to_use)
                ts_code = self._format_ts_code(stock_code)
                end_date = datetime.now().strftime("%Y%m%d")
                start_date = (datetime.now() - timedelta(days=days * 3)).strftime("%Y%m%d")
                df = client.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                if df is not None and not df.empty:
                    df = df.sort_values("trade_date")
                    dates = df["trade_date"].tolist()[-days:]
                    highs = df["high"].astype(float).tolist()[-days:]
                    lows = df["low"].astype(float).tolist()[-days:]
                    closes = df["close"].astype(float).tolist()[-days:]
                    return dates, highs, lows, closes
                tushare_error = ValueError("Tushare返回空数据")
                print(f"Tushare日K OHLC空数据,切换到AKShare (股票代码: {stock_code})")
            except Exception as e:
                tushare_error = e
                print(f"Tushare日K OHLC失败,切换到AKShare (股票代码: {stock_code}): {e!s}")
        if force_tushare_only and tushare_error:
            raise ValueError(f"Tushare获取日K失败: {tushare_error}")
        if not force_tushare_only:
            try:
                hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                if hist_data is None or hist_data.empty:
                    raise ValueError("未获取到AKShare日线数据")
                if "日期" in hist_data.columns:
                    hist_data = hist_data.sort_values("日期")
                elif "date" in hist_data.columns:
                    hist_data = hist_data.sort_values("date")
                hist_data = hist_data.tail(days)
                date_col = "日期" if "日期" in hist_data.columns else "date"
                high_col = "最高" if "最高" in hist_data.columns else "high"
                low_col = "最低" if "最低" in hist_data.columns else "low"
                close_col = "收盘" if "收盘" in hist_data.columns else "close"
                dates = hist_data[date_col].astype(str).tolist()
                highs = hist_data[high_col].astype(float).tolist()
                lows = hist_data[low_col].astype(float).tolist()
                closes = hist_data[close_col].astype(float).tolist()
                return dates, highs, lows, closes
            except Exception as e:
                _mark_akshare_failed(str(e))
                print(f"AKShare日K OHLC失败 (股票代码: {stock_code}): {e}")
                raise ValueError(f"获取日K OHLC失败: {e}")
        raise ValueError("无法获取日线OHLC数据")

    def _fetch_recent_daily_ohlcv(self, stock_code: str, days: int = 30,
                                  source: str = "default", token: str | None = None):
        """获取近期日K:日期、开、高、低、收、成交量。数据源与 _fetch_recent_daily_closes 一致。"""
        if not stock_code:
            raise ValueError("缺少股票代码")
        days = max(days, 10)
        force_tushare_only = (source == "tushare")
        force_ak_only = (source == "akshare")
        token_to_use = token or self.ts_token or TS_DEFAULT_TOKEN
        use_tushare_first = (not force_ak_only) and (TS_AVAILABLE and token_to_use)
        tushare_error = None
        if use_tushare_first:
            try:
                client = self._ensure_tushare_client(token_to_use)
                ts_code = self._format_ts_code(stock_code)
                end_date = datetime.now().strftime("%Y%m%d")
                start_date = (datetime.now() - timedelta(days=days * 3)).strftime("%Y%m%d")
                df = client.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                if df is not None and not df.empty:
                    df = df.sort_values("trade_date")
                    sl = df.tail(days)
                    dates = sl["trade_date"].tolist()
                    opens = sl["open"].astype(float).tolist()
                    highs = sl["high"].astype(float).tolist()
                    lows = sl["low"].astype(float).tolist()
                    closes = sl["close"].astype(float).tolist()
                    vols = sl["vol"].astype(float).tolist()
                    return dates, opens, highs, lows, closes, vols
                tushare_error = ValueError("Tushare返回空数据")
            except Exception as e:
                tushare_error = e
                print(f"Tushare日K OHLCV失败,切换AKShare ({stock_code}): {e}")
        if force_tushare_only and tushare_error:
            raise ValueError(f"Tushare获取日K OHLCV失败: {tushare_error}")
        if not force_tushare_only:
            try:
                hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                if hist_data is None or hist_data.empty:
                    raise ValueError("未获取到AKShare日线数据")
                if "日期" in hist_data.columns:
                    hist_data = hist_data.sort_values("日期")
                elif "date" in hist_data.columns:
                    hist_data = hist_data.sort_values("date")
                hist_data = hist_data.tail(days)
                date_col = "日期" if "日期" in hist_data.columns else "date"
                open_col = "开盘" if "开盘" in hist_data.columns else "open"
                high_col = "最高" if "最高" in hist_data.columns else "high"
                low_col = "最低" if "最低" in hist_data.columns else "low"
                close_col = "收盘" if "收盘" in hist_data.columns else "close"
                vol_col = None
                for c in hist_data.columns:
                    if "成交量" in str(c) or str(c).lower() == "volume":
                        vol_col = c
                        break
                dates = hist_data[date_col].astype(str).tolist()
                opens = hist_data[open_col].astype(float).tolist()
                highs = hist_data[high_col].astype(float).tolist()
                lows = hist_data[low_col].astype(float).tolist()
                closes = hist_data[close_col].astype(float).tolist()
                if vol_col and vol_col in hist_data.columns:
                    vols = hist_data[vol_col].astype(float).tolist()
                else:
                    vols = [0.0] * len(closes)
                return dates, opens, highs, lows, closes, vols
            except Exception as e:
                print(f"AKShare日K OHLCV失败 ({stock_code}): {e}")
                raise ValueError(f"获取日K OHLCV失败: {e}")
        raise ValueError("无法获取日线OHLCV数据")

    def _get_stock_recent_10day_and_ma10(self, stock_code):
        """获取股票最近10个交易日的每日涨跌幅及与10日均线的百分比距离。
        使用与一键分析相同的数据源逻辑:source='default',优先 Tushare,失败则 AKShare。
        返回 (daily_changes, ma10_distance_pct),失败返回 (None, None)。"""
        if not stock_code:
            return None, None
        try:
            result = self._fetch_recent_daily_closes(
                stock_code, days=15, source="default", token=self.ts_token, return_volume=False
            )
            if isinstance(result, tuple) and len(result) >= 2:
                _dates, closes = result[0], result[1]
            else:
                return None, None
            if not closes or len(closes) < 11:
                return None, None
            closes = [float(c) for c in closes]
            # 取最近11根K线
            last_11 = closes[-11:]
            daily_changes = []
            for i in range(1, len(last_11)):
                if last_11[i - 1] and last_11[i - 1] != 0:
                    pct = round((last_11[i] - last_11[i - 1]) / last_11[i - 1] * 100, 2)
                    daily_changes.append(pct)
                else:
                    daily_changes.append(0.0)
            changes_10 = daily_changes[-10:] if len(daily_changes) >= 10 else None
            # 10日均线 = 最近10日收盘价均值,当前价 = 最后一根收盘价
            last_close = last_11[-1]
            ma10 = sum(last_11[-10:]) / 10
            ma10_dist_pct = round((last_close - ma10) / ma10 * 100, 2) if ma10 and ma10 != 0 else None
            return changes_10, ma10_dist_pct
        except Exception as e:
            print(f"获取 {stock_code} 最近10日涨跌幅/距10日线失败: {e}")
            return None, None

    def _get_safety_prompt(self, option_name, option_desc, problem):
        """生成安全分析提示"""
        return f"""请进行以下安全分析:
安全类型:{option_name}
类型说明:{option_desc}
用户问题:{problem}
请提供以下方面的分析:
1. 该安全类型的具体评估标准和方法
2. 如何识别和防范相关风险
3. 具体的检查清单和评估步骤
4. 风险等级划分和应对策略
5. 针对用户问题的具体安全建议
6. 风险提示和注意事项
7. 如何结合其他安全措施进行综合防护"""

    def _get_liquidity_prompt(self, option_name, option_desc, problem):
        """生成流动性分析提示"""
        return f"""请进行以下流动性分析:
分析类型:{option_name}
类型说明:{option_desc}
用户问题:{problem}
请提供以下方面的分析:
1. 该分析类型的具体检查方法和标准
2. 如何识别流动性风险和不当投资
3. 具体的检查步骤和判断标准
4. 流动性陷阱的识别和规避
5. 针对用户问题的具体流动性评估
6. 风险提示和注意事项
7. 如何结合市场情况判断流动性状况
特别注意:跌停板、停牌、ST股票等不当投资情况会导致流动性缺失,需要重点检查。"""

    def _get_profit_prompt(self, option_name, option_desc, problem):
        """生成利润分析提示"""
        return f"""请进行以下利润分析:
分析类型:{option_name}
类型说明:{option_desc}
用户问题:{problem}
请提供以下方面的分析:
1. 该分析类型的具体技术指标和判断标准
2. 如何识别趋势和盈利机会
3. 具体的分析步骤和操作建议
4. 技术指标的适用场景和局限性
5. 针对用户问题的具体利润评估
6. 买入时机和卖出时机的建议
7. 如何结合多个时间周期进行综合分析
重点关注:
- 月线MACD双金叉:确认长期上涨趋势
- 60分钟非死叉:确认中期上涨趋势
- 15分钟多头排列:确认短期上涨趋势
- 多周期共振:提高盈利概率"""

    def _get_stock_price_data(self, stock_name, stock_code):
        """获取股票价格相关数据
        Args:
            stock_name: 股票名称
            stock_code: 股票代码
        Returns:
            dict: 包含涨跌幅、5日最低点差值、均线差值等数据
        """
        result = {
            'change_pct': None,  # 最近涨跌幅
            'low5_diff_pct': None,  # 5日最低点差值%
            'ma5_diff_pct': None,  # 5日均线差值%
            'ma10_diff_pct': None  # 10日均线差值%
        }
        try:
            if not stock_code:
                stock_code = get_stock_code_by_name(stock_name)
            if not stock_code:
                return result
            # 获取实时价格
            spot_row = get_realtime_spot_row(stock_code, cache_duration=30)
            if spot_row is None:
                return result
            current_price = float(spot_row.get('最新价', 0))
            if current_price <= 0:
                return result
            # 获取历史数据
            try:
                import akshare as ak
                hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                if hist_data.empty or len(hist_data) < 10:
                    return result
                # 计算最近涨跌幅(相对于前一日)
                if len(hist_data) >= 2:
                    prev_close = float(hist_data.iloc[-2]['收盘'])
                    if prev_close > 0:
                        result['change_pct'] = round((current_price - prev_close) / prev_close * 100, 2)
                # 计算5日最低点差值
                if len(hist_data) >= 5:
                    recent_5days = hist_data.tail(5)
                    low5_price = float(recent_5days['最低'].min())
                    if low5_price > 0:
                        result['low5_diff_pct'] = round((current_price - low5_price) / low5_price * 100, 2)
                # 计算5日均线差值
                if len(hist_data) >= 5:
                    recent_5days = hist_data.tail(5)
                    ma5 = float(recent_5days['收盘'].mean())
                    if ma5 > 0:
                        result['ma5_diff_pct'] = round((current_price - ma5) / ma5 * 100, 2)
                # 计算10日均线差值
                if len(hist_data) >= 10:
                    recent_10days = hist_data.tail(10)
                    ma10 = float(recent_10days['收盘'].mean())
                    if ma10 > 0:
                        result['ma10_diff_pct'] = round((current_price - ma10) / ma10 * 100, 2)
            except Exception as e:
                print(f"获取股票 {stock_name} 价格数据失败: {e}")
        except Exception as e:
            print(f"计算股票 {stock_name} 价格数据失败: {e}")
        return result

    def _query_wenwen_stocks(self):
        """查询问询问财获取热门股票列表
        查询条件:15分钟20日的均线上移,60分钟周期diff大于0,5日线10日线20日线均线多头发散
        热度排名按照从低到高排列 近10日同花顺概念股 热点排名前200 按15分钟macd的diff值从小到大排名
        """
        try:
            # 由于问询问财可能需要登录或API,这里使用替代方案:
            # 通过akshare获取同花顺概念股,然后筛选符合条件的股票
            import akshare as ak
            # 获取同花顺概念板块
            concept_df = safe_call(ak.stock_board_concept_name_em, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_em")
            if concept_df.empty:
                return []
            # 获取近10日热门概念(按涨跌幅排序)
            concept_df = concept_df.sort_values('涨跌幅', ascending=False).head(10)
            all_stocks = []
            # 遍历每个概念板块,获取成分股
            for _, concept_row in concept_df.iterrows():
                concept_name = concept_row['板块名称']
                try:
                    # 获取板块成分股
                    stocks_df = ak.stock_board_concept_cons_em(symbol=concept_name)
                    if stocks_df.empty:
                        continue
                    # 获取热点排名前200的股票(按涨跌幅排序)
                    stocks_df = stocks_df.sort_values('涨跌幅', ascending=False).head(200)
                    for _, stock_row in stocks_df.iterrows():
                        stock_code = stock_row.get('代码', '')
                        stock_name = stock_row.get('名称', '')
                        if stock_code and stock_name:
                            all_stocks.append((stock_code, stock_name))
                except Exception as e:
                    print(f"获取概念板块 {concept_name} 成分股失败: {e}")
                    continue
            # 去重
            seen = set()
            unique_stocks = []
            for code, name in all_stocks:
                if code not in seen:
                    seen.add(code)
                    unique_stocks.append((code, name))
            # 筛选符合条件的股票(15分钟20日均线上移,60分钟diff>0,5/10/20日均线多头发散)
            filtered_stocks = []
            for stock_code, stock_name in unique_stocks[:200]:  # 限制处理前200只
                try:
                    # 获取15分钟K线
                    kline_15min = ak.stock_zh_a_hist_min_em(symbol=str(stock_code).zfill(6), period="15", adjust="")
                    if kline_15min is None or kline_15min.empty or len(kline_15min) < 320:
                        continue
                    # 获取60分钟K线
                    kline_60min = ak.stock_zh_a_hist_min_em(symbol=str(stock_code).zfill(6), period="60", adjust="")
                    if kline_60min is None or kline_60min.empty:
                        continue
                    # 获取日线数据(用于计算5/10/20日均线)
                    daily_data = ak.stock_zh_a_hist(symbol=str(stock_code).zfill(6), period="daily", adjust="")
                    if daily_data is None or daily_data.empty or len(daily_data) < 20:
                        continue
                    # 检查条件
                    close_col_15min = None
                    for col in kline_15min.columns:
                        if '收盘' in str(col) or 'close' in str(col).lower():
                            close_col_15min = col
                            break
                    if close_col_15min is None:
                        continue
                    closes_15min = kline_15min[close_col_15min].astype(float).tolist()
                    if len(closes_15min) < 320:
                        continue
                    # 检查15分钟20日均线上移
                    ma20_prev = sum(closes_15min[-321:-1]) / 320
                    ma20_curr = sum(closes_15min[-320:]) / 320
                    if ma20_curr <= ma20_prev:
                        continue
                    # 检查60分钟diff>0(简化:使用收盘价变化)
                    close_col_60min = None
                    for col in kline_60min.columns:
                        if '收盘' in str(col) or 'close' in str(col).lower():
                            close_col_60min = col
                            break
                    if close_col_60min is None:
                        continue
                    closes_60min = kline_60min[close_col_60min].astype(float).tolist()
                    if len(closes_60min) < 2:
                        continue
                    if closes_60min[-1] <= closes_60min[-2]:
                        continue
                    # 检查5/10/20日均线多头发散
                    close_col_daily = None
                    for col in daily_data.columns:
                        if '收盘' in str(col) or 'close' in str(col).lower():
                            close_col_daily = col
                            break
                    if close_col_daily is None:
                        continue
                    closes_daily = daily_data[close_col_daily].astype(float).tolist()
                    if len(closes_daily) < 20:
                        continue
                    ma5 = sum(closes_daily[-5:]) / 5
                    ma10 = sum(closes_daily[-10:]) / 10
                    ma20 = sum(closes_daily[-20:]) / 20
                    current_price = closes_daily[-1]
                    # 多头发散:价格 > MA5 > MA10 > MA20
                    if not (current_price > ma5 > ma10 > ma20):
                        continue
                    # 计算15分钟MACD的diff值(简化:使用价格变化率)
                    # 这里简化处理,使用价格动量作为diff的近似
                    if len(closes_15min) >= 26:
                        ema12 = closes_15min[-1]  # 简化EMA计算
                        ema26 = sum(closes_15min[-26:]) / 26
                        diff_approx = ema12 - ema26
                    else:
                        diff_approx = 0
                    filtered_stocks.append((stock_code, stock_name, diff_approx))
                except Exception as e:
                    print(f"筛选股票 {stock_code} 失败: {e}")
                    continue
            # 按15分钟macd的diff值从小到大排名
            filtered_stocks.sort(key=lambda x: x[2])
            # 返回股票代码和名称列表
            return [(code, name) for code, name, _ in filtered_stocks]
        except Exception as e:
            print(f"查询问询问财股票失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_stock_price_changes(self, stock_code, days=20):
        """获取最近N日的涨跌幅数据"""
        try:
            if not stock_code:
                return []
            # 获取最近收盘价数据
            result = self._fetch_recent_daily_closes(stock_code, days=days+1, source="default", token=self.ts_token, return_volume=False)
            if isinstance(result, tuple) and len(result) >= 2:
                dates, closes = result[:2]
            else:
                dates, closes = result, []
            if not closes or len(closes) < 2:
                return []
            # 计算每日涨跌幅
            price_changes = []
            for i in range(1, min(len(closes), days+1)):
                if i < len(dates):
                    date = dates[i] if isinstance(dates[i], str) else str(dates[i])
                else:
                    date = f"第{i}日"
                prev_price = float(closes[i-1])
                curr_price = float(closes[i])
                change_pct = ((curr_price - prev_price) / prev_price) * 100
                price_changes.append({
                    'date': date,
                    'price': curr_price,
                    'change_pct': round(change_pct, 2)
                })
            return price_changes
        except Exception as e:
            print(f"获取涨跌幅数据失败: {e}")
            return []

    def _get_5day_high_low_data(self, stock_code):
        """获取股票最近5天的最高价和最低价(类方法版本)
        Args:
            stock_code: 股票代码
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
            # 获取当前实时价格(优先使用实时价格)
            current_price = None
            try:
                spot_row = get_realtime_spot_row(stock_code, cache_duration=60)
                if spot_row is not None:
                    price = spot_row.get('最新价')
                    if price is not None:
                        current_price = float(price)
            except:
                pass
            # 如果没有实时价格,使用最新收盘价
            if current_price is None:
                current_price = float(recent_5days.iloc[-1]['收盘'])
            return current_price, max_high, min_low
        except Exception as e:
            print(f"获取{stock_code}的5天高低点数据失败: {e}")
            return None, None, None

    def _get_nday_high_low_percentages(self, stock_code, current_price):
        """获取股票N日(5日、10日、20日)最高值和最低值,并计算距离当前价格的百分比。
        数据源与一键分析一致:_fetch_recent_daily_ohlc(source='default'),优先 Tushare,失败则 AKShare。"""
        result = {
            '5d_high_pct': None,
            '5d_low_pct': None,
            '10d_high_pct': None,
            '10d_low_pct': None,
            '20d_high_pct': None,
            '20d_low_pct': None
        }
        if not stock_code or current_price <= 0:
            return result
        try:
            _dates, highs, lows, _closes = self._fetch_recent_daily_ohlc(
                stock_code, days=25, source="default", token=self.ts_token
            )
            if not highs or not lows or len(highs) < 5:
                return result
            highs = [float(h) for h in highs]
            lows = [float(l) for l in lows]
            if len(highs) >= 5:
                high_5d = max(highs[-5:])
                low_5d = min(lows[-5:])
                if high_5d > 0:
                    result['5d_high_pct'] = round(((current_price - high_5d) / high_5d) * 100, 2)
                if low_5d > 0:
                    result['5d_low_pct'] = round(((current_price - low_5d) / low_5d) * 100, 2)
            if len(highs) >= 10:
                high_10d = max(highs[-10:])
                low_10d = min(lows[-10:])
                if high_10d > 0:
                    result['10d_high_pct'] = round(((current_price - high_10d) / high_10d) * 100, 2)
                if low_10d > 0:
                    result['10d_low_pct'] = round(((current_price - low_10d) / low_10d) * 100, 2)
            if len(highs) >= 20:
                high_20d = max(highs[-20:])
                low_20d = min(lows[-20:])
                if high_20d > 0:
                    result['20d_high_pct'] = round(((current_price - high_20d) / high_20d) * 100, 2)
                if low_20d > 0:
                    result['20d_low_pct'] = round(((current_price - low_20d) / low_20d) * 100, 2)
            return result
        except Exception as e:
            print(f"获取{stock_code}的N日高低点百分比失败: {e}")
            return result

    def _get_large_order_net_inflow_with_accumulation(self, stock_code, days=20):
        """获取最近N日的大单净流入值和累计值"""
        try:
            if not stock_code:
                return {'daily': [], 'accumulation': {}}
            import akshare as ak
            # 获取个股资金流向数据
            try:
                fund_flow = ak.stock_individual_fund_flow(
                    stock=stock_code, market=_akshare_fund_flow_market(stock_code)
                )
                if fund_flow is not None and not fund_flow.empty:
                    # 取最近N日数据
                    recent_data = fund_flow.head(days)
                    daily_data = []
                    for _, row in recent_data.iterrows():
                        date = row.get('日期', '')
                        net_inflow = row.get('大单净流入-净额', row.get('大单净流入', 0))
                        if date and net_inflow is not None:
                            daily_data.append({
                                'date': date,
                                'net_inflow': round(float(net_inflow), 2) if net_inflow else 0
                            })
                    # 计算累计值
                    accumulation = {}
                    if daily_data:
                        # 最近5日累计
                        if len(daily_data) >= 5:
                            accumulation['5日'] = sum([d['net_inflow'] for d in daily_data[:5]])
                        # 累计3日、10日、20日
                        if len(daily_data) >= 3:
                            accumulation['3日'] = sum([d['net_inflow'] for d in daily_data[:3]])
                        if len(daily_data) >= 10:
                            accumulation['10日'] = sum([d['net_inflow'] for d in daily_data[:10]])
                        if len(daily_data) >= 20:
                            accumulation['20日'] = sum([d['net_inflow'] for d in daily_data[:20]])
                    return {'daily': daily_data[:5], 'accumulation': accumulation}
            except Exception as e:
                print(f"获取大单净流入数据失败: {e}")
            return {'daily': [], 'accumulation': {}}
        except Exception as e:
            print(f"获取大单净流入数据异常: {e}")
            return {'daily': [], 'accumulation': {}}

    def _fetch_stock_info(self, stock_name):
        """从本地资讯数据库获取关于股票的热度和信息评价。
        数据来源:本地 news_info 表
        """
        result = {
            'success': False,
            'message': '',
            'hotness': {},
            'news': [],
            'sentiment': []
        }
        try:
            import sqlite3
            from collections import Counter
            result['calculation_steps'] = ["【从本地资讯数据库获取信息...】"]
            conn = sqlite3.connect(self.news_db)
            cursor = conn.cursor()
            # 获取股票代码
            code = ""
            try:
                cursor.execute("SELECT code FROM stocks WHERE name = ?", (stock_name,))
                row = cursor.fetchone()
                if row:
                    code = row[0]
            except Exception:
                pass
            result['calculation_steps'].append(f"股票名称: {stock_name}")
            result['calculation_steps'].append(f"股票代码: {code}")
            # 1. 热度分析:统计股票在资讯中的出现频次
            result['calculation_steps'].append("\n【热度分析】")
            cursor.execute("SELECT id, tab_name, content, created_at FROM news_info ORDER BY created_at DESC")
            rows = cursor.fetchall()
            if not rows:
                result['calculation_steps'].append("~ 资讯数据库为空")
                result['success'] = True
                conn.close()
                return result
            total_count = 0
            daily_count = {}
            for row in rows:
                rid, tab_name, content, created_at = row
                if not content:
                    continue
                if code and code in content:
                    total_count += 1
                    date_ymd = created_at[:10] if created_at and len(created_at) >= 10 else '未知'
                    daily_count[date_ymd] = daily_count.get(date_ymd, 0) + 1
                if stock_name in content:
                    total_count += 1
            result['hotness']['total_mentions'] = total_count
            result['hotness']['days_mentioned'] = len(daily_count)
            result['calculation_steps'].append(f"✓ 总提及次数: {total_count}次")
            result['calculation_steps'].append(f"✓ 提及天数: {len(daily_count)}天")
            # 显示最近7天的热度
            recent_days = sorted(daily_count.keys(), reverse=True)[:7]
            for day in recent_days:
                result['calculation_steps'].append(f"  {day}: {daily_count[day]}次")
            # 2. 相关资讯列表
            result['calculation_steps'].append("\n【相关资讯】")
            news_count = 0
            for row in rows:
                if news_count >= 10:
                    break
                rid, tab_name, content, created_at = row
                if not content:
                    continue
                has_code = code and code in content
                has_name = stock_name in content
                if has_code or has_name:
                    date_str = created_at[:19] if created_at and len(created_at) >= 19 else '未知'
                    snippet = content[:100] + '...' if len(content) > 100 else content
                    result['news'].append({
                        '来源': tab_name,
                        '标题': f"{tab_name} - {date_str}",
                        '时间': date_str,
                        '内容': snippet
                    })
                    news_count += 1
            result['calculation_steps'].append(f"✓ 相关资讯: {len(result['news'])}条")
            # 3. 情感分析(从资讯内容中提取)
            result['calculation_steps'].append("\n【情感分析】")
            positive_words = ['上涨', '涨停', '利好', '增持', '买入', '推荐', '看好', '大涨', '飙升']
            negative_words = ['下跌', '跌停', '利空', '减持', '卖出', '看空', '大跌', '暴跌']
            pos_count = 0
            neg_count = 0
            for row in rows:
                rid, tab_name, content, created_at = row
                if not content:
                    continue
                has_code = code and code in content
                has_name = stock_name in content
                if has_code or has_name:
                    for word in positive_words:
                        pos_count += content.count(word)
                    for word in negative_words:
                        neg_count += content.count(word)
            sentiment_score = pos_count - neg_count
            result['sentiment'].append({
                '正面词汇': pos_count,
                '负面词汇': neg_count,
                '情感得分': sentiment_score
            })
            if sentiment_score > 0:
                sentiment_text = '偏乐观'
            elif sentiment_score < 0:
                sentiment_text = '偏悲观'
            else:
                sentiment_text = '中性'
            result['calculation_steps'].append(f"✓ 正面词汇: {pos_count}个")
            result['calculation_steps'].append(f"✓ 负面词汇: {neg_count}个")
            result['calculation_steps'].append(f"✓ 情感倾向: {sentiment_text}")
            # 4. 资讯来源统计
            result['calculation_steps'].append("\n【资讯来源】")
            source_count = Counter()
            for row in rows:
                _rid, tab_name, content, created_at = row
                if not content:
                    continue
                has_code = code and code in content
                has_name = stock_name in content
                if has_code or has_name:
                    source_count[tab_name] += 1
            for source, count in source_count.most_common(5):
                result['calculation_steps'].append(f"  {source}: {count}条")
            conn.close()
            result['success'] = True
            result['message'] = '信息获取完成'
        except Exception as e:
            result['message'] = f'信息获取失败: {e}'
        return result

    def _get_major_index_changes(self):
        """沪深300/中证500/科创50(用作科创30近似)当日涨跌幅,优先 Tushare。"""
        idx_map = {
            "沪深300": "000300.SH",
            "中证500": "000905.SH",
            "科创50(替代科创30)": "000688.SH",
        }
        out = {}
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
        if TS_AVAILABLE and (getattr(self, "ts_token", None) or TS_DEFAULT_TOKEN):
            try:
                self._ensure_tushare_client(self.ts_token or TS_DEFAULT_TOKEN)
                for name, ts_code in idx_map.items():
                    try:
                        df = self.ts_client.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                        if df is None or df.empty:
                            continue
                        df = df.sort_values("trade_date").tail(2).reset_index(drop=True)
                        if len(df) >= 2:
                            prev_close = float(df.iloc[-2]["close"])
                            close = float(df.iloc[-1]["close"])
                            pct = (close / prev_close - 1.0) * 100.0 if prev_close > 0 else 0.0
                            out[name] = {"close": close, "pct": pct, "source": "Tushare"}
                    except Exception:
                        continue
            except Exception:
                pass
        return out

    def _query_neodata_safe(self, query, data_type="api", retries=3, interval=1.5):
        """T1: 统一 neodata 数据客户端(含重试 + 结构化错误)"""
        import time as _time
        for attempt in range(retries):
            try:
                query_neodata = None
                neodata_paths = [
                    os.path.expanduser("~/.qclaw/skills/neodata-financial-search"),
                    os.path.expanduser("~/Library/Application Support/QClaw/skills/neodata-financial-search"),
                ]
                for p in neodata_paths:
                    if os.path.isdir(p) and p not in sys.path:
                        sys.path.insert(0, p)
                        try:
                            from query import query_neodata as _qn
                            query_neodata = _qn
                            break
                        except ImportError:
                            sys.path.pop(0)
                            continue
                if query_neodata is None:
                    return {"error": "neodata模块未找到", "query": query}
                result = query_neodata(query, data_type)
                if result and not str(result).startswith("错误"):
                    return {"data": result, "query": query, "attempt": attempt + 1}
                if attempt < retries - 1:
                    _time.sleep(interval)
            except Exception as e:
                if attempt < retries - 1:
                    _time.sleep(interval)
                    continue
                return {"error": str(e), "query": query, "attempt": attempt + 1}
        return {"error": f"重试{retries}次后仍失败", "query": query}

    def _neodata_get_stock_ma(self, stock_code, periods=(5, 10, 20, 60)):
        """T1辅助: 通过 neodata 查询股票均线数据"""
        ma_str = "/".join([f"MA{p}" for p in periods])
        result = self._query_neodata_safe(f"{stock_code} 近60日K线行情 收盘价 {ma_str}")
        return result.get("data") if "error" not in result else None

    def _neodata_get_fundamental(self, stock_code):
        """T1辅助: 通过 neodata 查询基本面数据"""
        result = self._query_neodata_safe(f"{stock_code} 市值 营收增长率 机构持股比例 PE PB ROE")
        return result.get("data") if "error" not in result else None

    def _fetch_index_min_data(self, symbol, name, max_lookback_days=10):
        """
        获取指数1分钟分时数据。非交易时段自动往前推最近交易日。
        symbol: '000001'(上证), '399001'(深成), '399006'(创业板)
        返回 dict: {'times': [...], 'prices': [...], 'volumes': [...], 'name': name, 'date': 'YYYYMMDD'}
        """
        import numpy as np
        try:
            if not AKSHARE_AVAILABLE:
                return None
            # 依次尝试今天、昨天、... 最多 max_lookback_days 天
            from datetime import datetime, timedelta

            import akshare as ak
            last_df = None
            last_date_str = None
            for offset in range(max_lookback_days):
                d = datetime.now() - timedelta(days=offset)
                ds = d.strftime("%Y%m%d")
                try:
                    df = ak.index_zh_a_hist_min_em(
                        symbol=symbol,
                        period="1",
                        start_date=ds + " 09:25:00",
                        end_date=ds + " 15:05:00",
                    )
                except Exception:
                    try:
                        df = ak.index_zh_a_hist_min_em(
                            symbol=symbol, period="1")
                        # 如果拿到的是"今天或最近"的全部数据,截取对应日期
                        if df is not None and len(df) > 0:
                            time_col_candidates = ["时间", "日期时间", "datetime", "date_time"]
                            for tc in time_col_candidates:
                                if tc in df.columns:
                                    try:
                                        mask = df[tc].astype(str).str.startswith(ds[:4] + "-" + ds[4:6] + "-" + ds[6:8])
                                        df = df[mask]
                                    except Exception:
                                        pass
                                    break
                    except Exception:
                        df = None
                if df is not None and len(df) >= 30:
                    last_df = df
                    last_date_str = ds
                    # 如果是今天,继续尝试取更早的;如果是历史日期,取到就停
                    if offset == 0:
                        # 今天拿到了,优先用今天
                        break
                    else:
                        # 历史日期拿到了也 break
                        break
            if last_df is None or len(last_df) < 30:
                return None
            df = last_df
            fetch_date = last_date_str or datetime.now().strftime("%Y%m%d")
            # 统一列名(不同版本可能叫 时间/日期/分钟)
            time_col = None
            for c in df.columns:
                if c in ("时间", "日期时间", "datetime", "date_time", "时间戳"):
                    time_col = c
                    break
            if time_col is None:
                for c in df.columns:
                    if "时间" in c or "time" in c.lower():
                        time_col = c
                        break
            price_col = None
            for c in ("收盘", "close", "收盘价", "Close"):
                if c in df.columns:
                    price_col = c
                    break
            if price_col is None:
                for c in df.columns:
                    if "收盘" in c or "close" in c.lower():
                        price_col = c
                        break
            vol_col = None
            for c in ("成交量", "volume", "Volume"):
                if c in df.columns:
                    vol_col = c
                    break
            if time_col is None or price_col is None:
                return None
            times = df[time_col].astype(str).tolist()
            prices = df[price_col].astype(float).tolist()
            volumes = df[vol_col].astype(float).tolist() if vol_col else [0] * len(prices)
            # 过滤非交易时间(午休 11:30-13:00)
            filtered_times, filtered_prices, filtered_vols = [], [], []
            for t, p, v in zip(times, prices, volumes):
                # 解析出小时分钟
                try:
                    t_str = str(t)
                    # 可能格式 "2026-08-28 10:31:00" 或 "10:31"
                    if " " in t_str:
                        hm = t_str.split(" ")[1]
                    else:
                        hm = t_str
                    h = int(hm.split(":")[0])
                    m = int(hm.split(":")[1]) if ":" in hm else 0
                    minutes = h * 60 + m
                    # 过滤午休 11:30 ~ 13:00
                    if 11 * 60 + 30 <= minutes < 13 * 60:
                        continue
                    # 只保留 9:30~11:30, 13:00~15:00
                    if not (9 * 60 + 30 <= minutes <= 15 * 60):
                        continue
                except Exception:
                    pass
                filtered_times.append(t)
                filtered_prices.append(p)
                filtered_vols.append(v)
            if len(filtered_prices) < 30:
                return None
            return {
                "name": name,
                "symbol": symbol,
                "times": filtered_times,
                "prices": np.array(filtered_prices),
                "volumes": np.array(filtered_vols),
                "date": fetch_date,
            }
        except Exception as e:
            print(f"[{name}] 分时数据获取失败: {e}")
            return None


__all__ = ["GettersMixin"]
