"""实时行情/快照/监控"""
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


class RealtimeMixin:
    """实时行情/快照/监控"""

    def start_realtime_update(self):
        """启动实时数据更新"""
        def update_loop():
            while True:
                try:
                    if hasattr(self, 'root') and self.root.winfo_exists():
                        self.update_realtime_data()
                    time.sleep(1)  # 每秒更新一次
                except Exception as e:
                    print(f"实时更新错误: {e}")
                    time.sleep(5)  # 出错时等待5秒
        update_thread = threading.Thread(target=update_loop, daemon=True)
        update_thread.start()

    def update_realtime_data(self):
        """更新实时数据"""
        try:
            # 获取当前文本中的股票
            text = self.get_current_text()
            if not text:
                return
            stock_names, _ = extract_stock_names(text)
            if not stock_names:
                return
            # 更新实时数据
            realtime_info = "🕐 实时数据更新中...\n\n"
            for stock_name in stock_names[:10]:  # 最多显示10只股票
                # 获取股票实时数据
                stock_data = None  # 实时数据获取功能已移除
                if stock_data:
                    # 获取板块信息
                    sector = get_stock_sector(stock_name)
                    # 获取板块内其他股票(最多3只)
                    sector_stocks = []  # 板块股票获取功能已移除
                    related_stocks = [s for s in sector_stocks if s != stock_name][:3]
                    # 显示主股票信息
                    change_emoji = "📈" if stock_data['change_pct'] > 0 else "📉" if stock_data['change_pct'] < 0 else "➡️"
                    realtime_info += f"【{stock_name}】{change_emoji}\n"
                    realtime_info += f"   💰 价格: {stock_data['price']:.2f}\n"
                    realtime_info += f"   📊 涨跌幅: {stock_data['change_pct']:.2f}%\n"
                    realtime_info += f"   🏢 板块: {sector}\n"
                    # 显示关联板块股票
                    if related_stocks:
                        realtime_info += "   🔗 关联股票:\n"
                        for related_stock in related_stocks:
                            related_data = None  # 实时数据获取功能已移除
                            if related_data:
                                rel_change_emoji = "📈" if related_data['change_pct'] > 0 else "📉" if related_data['change_pct'] < 0 else "➡️"
                                realtime_info += f"      {related_stock}: {rel_change_emoji} {related_data['change_pct']:.2f}%\n"
                    realtime_info += "\n" + "─" * 40 + "\n\n"
            # 更新时间戳
            realtime_info += f"⏰ 最后更新: {datetime.now().strftime('%H:%M:%S')}\n"
            # 更新显示
            if hasattr(self, 'realtime_text') and self.realtime_text.winfo_exists():
                self.realtime_text.delete("1.0", tk.END)
                self.realtime_text.insert("1.0", realtime_info)
        except Exception as e:
            print(f"更新实时数据失败: {e}")

    def show_paste_realtime_stats(self):
        """显示粘贴股票的实时统计"""
        try:
            # 创建输入窗口
            input_window = self._toplevel(self.root)
            input_window.title("粘贴股票列表")
            input_window.geometry("600x500")
            input_window.transient(self.root)
            input_window.grab_set()
            # 居中显示
            input_window.update_idletasks()
            x = (input_window.winfo_screenwidth() // 2) - (input_window.winfo_width() // 2)
            y = (input_window.winfo_screenheight() // 2) - (input_window.winfo_height() // 2)
            input_window.geometry(f"+{x}+{y}")
            # 说明标签
            info_label = ttk.Label(input_window, text="请输入股票列表(每行一个股票名称或代码)", font=("TkDefaultFont", 12))
            info_label.pack(pady=10)
            # 股票输入区域
            stock_frame = ttk.LabelFrame(input_window, text="股票列表", padding=10)
            stock_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            stock_text = scrolledtext.ScrolledText(stock_frame, height=15, wrap=tk.WORD)
            stock_text.pack(fill=tk.BOTH, expand=True)
            # 按钮区域
            btn_frame = ttk.Frame(input_window)
            btn_frame.pack(fill=tk.X, padx=10, pady=10)
            def paste_stocks():
                """粘贴股票"""
                try:
                    clipboard_text = input_window.clipboard_get()
                    stock_text.delete("1.0", tk.END)
                    stock_text.insert("1.0", clipboard_text)
                except:
                    messagebox.showwarning("警告", "剪贴板为空或无法获取", parent=input_window)
            def clear_stocks():
                """清空股票列表"""
                stock_text.delete("1.0", tk.END)
            ttk.Button(btn_frame, text="粘贴", command=paste_stocks, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="清空", command=clear_stocks, width=10).pack(side=tk.LEFT, padx=5)
            def start_analysis():
                """开始分析"""
                stock_content = stock_text.get("1.0", tk.END).strip()
                if not stock_content:
                    messagebox.showwarning("警告", "请输入股票列表", parent=input_window)
                    return
                # 解析股票列表
                stock_lines = [line.strip() for line in stock_content.split('\n') if line.strip()]
                if not stock_lines:
                    messagebox.showwarning("警告", "股票列表为空", parent=input_window)
                    return
                # 解析股票名称和代码
                all_holdings = []
                STOCK_NAME_TO_CODE, STOCK_CODES_DICT, _ = load_stock_names()
                for line in stock_lines:
                    stock_code = None
                    stock_name = None
                    # 尝试提取6位数字代码
                    code_match = re.search(r'(\d{6})', line)
                    if code_match:
                        code = code_match.group(1)
                        if STOCK_CODES_DICT and code in STOCK_CODES_DICT:
                            stock_code = code
                            stock_name = STOCK_CODES_DICT[code]
                    # 如果没有找到代码,尝试查找名称
                    if not stock_name:
                        clean_name = line.split('(')[0].strip()
                        if STOCK_NAME_TO_CODE and clean_name in STOCK_NAME_TO_CODE:
                            stock_name = clean_name
                            stock_code = STOCK_NAME_TO_CODE[clean_name]
                        else:
                            stock_code = get_stock_code_by_name(clean_name)
                            if stock_code:
                                if STOCK_CODES_DICT:
                                    stock_name = STOCK_CODES_DICT.get(stock_code, clean_name)
                                else:
                                    stock_name = clean_name
                    if stock_code and stock_name:
                        all_holdings.append({
                            'stock_name': stock_name,
                            'stock_code': stock_code,
                            'group': '粘贴股票'
                        })
                if not all_holdings:
                    messagebox.showwarning("警告", "没有找到有效的股票,请检查股票列表格式", parent=input_window)
                    return
                # 关闭输入窗口
                input_window.destroy()
                # 创建实时统计窗口(复用持仓实时统计的代码)
                self._show_realtime_stats_window(all_holdings, "粘贴实时统计")
            ttk.Button(btn_frame, text="确定", command=start_analysis, width=10).pack(side=tk.RIGHT, padx=5)
            ttk.Button(btn_frame, text="取消", command=input_window.destroy, width=10).pack(side=tk.RIGHT, padx=5)
            # 绑定回车键
            stock_text.focus()
        except Exception as e:
            messagebox.showerror("错误", f"打开粘贴实时统计失败: {e!s}", parent=self.root)
            import traceback
            traceback.print_exc()

    def _calculate_single_stock_realtime_stats(self, stock_name, stock_code):
        """计算单只股票的实时统计数据
        Returns:
            dict: 包含所有统计信息的字典
        """
        result = {
            'stock_name': stock_name,
            'stock_code': stock_code,
            'current_price': '',
            'change_pct': '',
            'amplitude': '',
            'change_5d': '',
            'change_10d': '',
            'change_20d': '',
            'low_5d_diff_pct': '',
            'high_5d_diff_pct': '',
            'ma10_diff_pct': '',
            'ma15_diff_pct': '',
            'ma20_diff_pct': '',
            'ma60_diff_pct': '',
            'main_net_flow': '',
            'large_order_inflow': '',
            'ma1_status': '',
            'ma5_status': '',
            'ma10_status': '',
            'ma20_status': '',
            'hot_rank': '',
            'news_logic': '',
            'news_content': '',  # 资讯内容
            'stock_logic': '',
            'pe': '',
            'market_cap': '',
            'turnover_rate': '',
            'sector': '',
            'concept': ''
        }
        try:
            import akshare as ak
            # 1. 获取当前股价、涨跌幅等基本信息
            try:
                spot_row = get_realtime_spot_row(stock_code, cache_duration=60)
                if spot_row:
                    result['current_price'] = f"{spot_row.get('最新价', ''):.2f}" if spot_row.get('最新价') else ''
                    result['change_pct'] = f"{spot_row.get('涨跌幅', ''):.2f}%" if spot_row.get('涨跌幅') else ''
                    result['amplitude'] = f"{spot_row.get('振幅', ''):.2f}%" if spot_row.get('振幅') else ''
                    result['pe'] = f"{spot_row.get('市盈率-动态', spot_row.get('市盈率', '')):.2f}" if spot_row.get('市盈率-动态') or spot_row.get('市盈率') else ''
                    result['market_cap'] = f"{spot_row.get('总市值', spot_row.get('市值', '')):.2f}" if spot_row.get('总市值') or spot_row.get('市值') else ''
                    result['turnover_rate'] = f"{spot_row.get('换手率', ''):.2f}%" if spot_row.get('换手率') else ''
            except:
                pass
            # 2. 获取历史数据计算涨跌幅和均线差值
            try:
                hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                if not hist_data.empty:
                    # 获取当前价格(用于计算)
                    current_price = None
                    try:
                        spot_row = get_realtime_spot_row(stock_code, cache_duration=60)
                        if spot_row and spot_row.get('最新价'):
                            current_price = float(spot_row.get('最新价'))
                    except:
                        pass
                    if current_price is None and len(hist_data) > 0:
                        current_price = float(hist_data.iloc[-1]['收盘'])
                    if current_price:
                        # 计算5日、10日、20日涨跌幅
                        if len(hist_data) >= 5:
                            price_5d_ago = float(hist_data.iloc[-5]['收盘'])
                            change_5d = ((current_price - price_5d_ago) / price_5d_ago) * 100
                            result['change_5d'] = f"{change_5d:+.2f}%"
                            # 5日最低点和最高点差值百分比
                            recent_5d = hist_data.tail(5)
                            min_low_5d = float(recent_5d['最低'].min())
                            max_high_5d = float(recent_5d['最高'].max())
                            if min_low_5d > 0:
                                low_diff_5d = ((current_price - min_low_5d) / min_low_5d) * 100
                                result['low_5d_diff_pct'] = f"{low_diff_5d:+.2f}%"
                            if max_high_5d > 0:
                                high_diff_5d = ((current_price - max_high_5d) / max_high_5d) * 100
                                result['high_5d_diff_pct'] = f"{high_diff_5d:+.2f}%"
                        if len(hist_data) >= 10:
                            price_10d_ago = float(hist_data.iloc[-10]['收盘'])
                            change_10d = ((current_price - price_10d_ago) / price_10d_ago) * 100
                            result['change_10d'] = f"{change_10d:+.2f}%"
                            # 10日均价差值百分比
                            ma10 = float(hist_data.tail(10)['收盘'].mean())
                            if ma10 > 0:
                                ma10_diff = ((current_price - ma10) / ma10) * 100
                                result['ma10_diff_pct'] = f"{ma10_diff:+.2f}%"
                        if len(hist_data) >= 15:
                            # 15日均价差值百分比
                            ma15 = float(hist_data.tail(15)['收盘'].mean())
                            if ma15 > 0:
                                ma15_diff = ((current_price - ma15) / ma15) * 100
                                result['ma15_diff_pct'] = f"{ma15_diff:+.2f}%"
                        if len(hist_data) >= 20:
                            price_20d_ago = float(hist_data.iloc[-20]['收盘'])
                            change_20d = ((current_price - price_20d_ago) / price_20d_ago) * 100
                            result['change_20d'] = f"{change_20d:+.2f}%"
                            # 20日均价差值百分比
                            ma20 = float(hist_data.tail(20)['收盘'].mean())
                            if ma20 > 0:
                                ma20_diff = ((current_price - ma20) / ma20) * 100
                                result['ma20_diff_pct'] = f"{ma20_diff:+.2f}%"
                        if len(hist_data) >= 60:
                            # 60日均价差值百分比
                            ma60 = float(hist_data.tail(60)['收盘'].mean())
                            if ma60 > 0:
                                ma60_diff = ((current_price - ma60) / ma60) * 100
                                result['ma60_diff_pct'] = f"{ma60_diff:+.2f}%"
            except:
                pass
            # 3. 均线检测(1日、5日、10日、20日)
            try:
                detection_result = self._three_dimensional_detection(stock_name, stock_code)
                if detection_result and detection_result.get('success'):
                    technical_result = detection_result.get('technical', {})
                    ma_status = technical_result.get('ma_status', {})
                    # ma_status是简单字典,ma1, ma5, ma10, ma20都是布尔值
                    result['ma1_status'] = '✓' if ma_status.get('ma1', False) else '✗'
                    result['ma5_status'] = '✓' if ma_status.get('ma5', False) else '✗'
                    result['ma10_status'] = '✓' if ma_status.get('ma10', False) else '✗'
                    result['ma20_status'] = '✓' if ma_status.get('ma20', False) else '✗'
            except Exception as e:
                print(f"均线检测失败 {stock_name}: {e}")
            # 4. 实时主力净量和资金大单流入
            try:
                large_order_result = self._get_large_order_net_inflow_with_accumulation(stock_code, days=1)
                if large_order_result:
                    daily_data = large_order_result.get('daily', [])
                    if daily_data:
                        latest = daily_data[-1]
                        net_flow = latest.get('net_inflow', 0)
                        result['main_net_flow'] = f"{net_flow:.2f}万元" if net_flow else ''
                        result['large_order_inflow'] = f"{latest.get('large_inflow', 0):.2f}万元" if latest.get('large_inflow') else ''
            except:
                pass
            # 5. 同花顺热门榜排名(检查是否在前100名)
            # 使用成交量或换手率作为热度指标,检查是否在前100名
            try:
                spot_em = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
                if not spot_em.empty and stock_code in spot_em['代码'].values.tolist():
                    # 按成交量排序,前100名视为热门股
                    sorted_by_volume = spot_em.sort_values('成交量', ascending=False)
                    stock_row = sorted_by_volume[sorted_by_volume['代码'] == stock_code]
                    if not stock_row.empty:
                        rank_by_volume = sorted_by_volume.index.get_loc(stock_row.index[0]) + 1
                        if rank_by_volume <= 100:
                            result['hot_rank'] = f"成交量第{rank_by_volume}名"
            except:
                pass
            # 6. 资讯表逻辑(最近半年)- 获取资讯内容
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                from datetime import datetime, timedelta
                six_months_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
                cursor.execute('''
                    SELECT content, created_at FROM news_info
                    WHERE content LIKE ? AND created_at >= ?
                    ORDER BY created_at DESC
                    LIMIT 10
                ''', (f'%{stock_name}%', six_months_ago))
                news_rows = cursor.fetchall()
                if news_rows:
                    # 合并最近10条资讯内容
                    news_contents = []
                    for row in news_rows[:10]:
                        content = row[0] if row[0] else ''
                        created_at = row[1] if len(row) > 1 else ''
                        if content:
                            # 清理内容(去除词云图片链接等)
                            import re
                            cleaned_content = re.sub(r'\[词云图片\].*?图片链接:.*?\n', '', content, flags=re.DOTALL)
                            cleaned_content = re.sub(r'文件路径:.*?\n', '', cleaned_content)
                            if created_at:
                                news_contents.append(f"[{created_at[:10]}] {cleaned_content[:500]}")  # 每条资讯最多500字
                            else:
                                news_contents.append(cleaned_content[:500])
                    if news_contents:
                        result['news_content'] = "\n\n".join(news_contents)
                        result['news_logic'] = f"最近半年{len(news_rows)}条资讯"
                conn.close()
            except Exception as e:
                print(f"获取资讯内容失败 {stock_name}: {e}")
            # 7. 股票数据表逻辑(获取实际逻辑内容)
            try:
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
                    logic_content = str(row[0])
                    # 只保存前50字
                    if len(logic_content) > 50:
                        result['stock_logic'] = logic_content[:50] + "..."
                    else:
                        result['stock_logic'] = logic_content
                conn.close()
            except Exception as e:
                print(f"获取股票数据表逻辑失败 {stock_name}: {e}")
            # 8. 板块和概念
            try:
                individual_info = ak.stock_individual_info_em(symbol=stock_code)
                if not individual_info.empty:
                    concepts_list = []
                    for _, row in individual_info.iterrows():
                        item = str(row.get('item', ''))
                        value = str(row.get('value', ''))
                        if value and value != 'nan' and value.strip():
                            if '所处行业' in item or (item == '行业' and not result['sector']):
                                result['sector'] = value.strip()
                            elif '概念' in item or '题材' in item:
                                concepts_list.append(value.strip())
                    if concepts_list:
                        result['concept'] = ', '.join(concepts_list[:10])  # 最多显示10个概念
            except Exception as e:
                print(f"获取板块概念失败 {stock_name}: {e}")
        except Exception as e:
            print(f"计算 {stock_name} ({stock_code}) 实时统计失败: {e}")
        return result


__all__ = ["RealtimeMixin"]
