"""交易/下单/模拟/回测"""
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
from logic.stock_names import *  # get_stock_name_by_code 等

from datetime import datetime, timedelta
import re
import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class TradeMixin:
    """交易/下单/模拟/回测"""

    def _map_codes_to_big_order_net_amount(self):
        """东财「今日」个股资金流排名中「大单净流入」净额(元)。返回 {六位代码: float}。"""
        out = {}
        if not AKSHARE_AVAILABLE:
            return out
        try:
            flow_rank = ak.stock_individual_fund_flow_rank(indicator="今日")
            if flow_rank is None or flow_rank.empty or '代码' not in flow_rank.columns:
                return out
            flow_rank = flow_rank.copy()
            flow_rank['_code'] = flow_rank['代码'].astype(str).str.zfill(6)
            da_col = None
            for col in flow_rank.columns:
                cs = str(col)
                if '大单净流入' in cs and '占比' not in cs:
                    da_col = col
                    break
            if da_col is None:
                return out
            for _, row in flow_rank.iterrows():
                c = row.get('_code', '')
                if not c:
                    continue
                try:
                    v = row[da_col]
                    if pd.notna(v):
                        out[c] = float(v)
                except (TypeError, ValueError):
                    pass
        except Exception as e:
            print(f"大单净额映射失败: {e}")
        return out

    def _perform_custom_backtest(self, stock_lines, buy_date, sell_date=None):
        """执行自定义回测分析"""
        # 解析股票代码
        target_stocks = []
        STOCK_NAME_TO_CODE, STOCK_CODES_DICT, _ = load_stock_names()
        for line in stock_lines:
            stock_code = None
            stock_name = None
            # 尝试提取6位数字代码
            code_match = re.search(r'(\d{6})', line)
            if code_match:
                code = code_match.group(1)
                if code in STOCK_CODES_DICT:
                    stock_code = code
                    stock_name = STOCK_CODES_DICT[code]
            # 如果没有找到代码,尝试查找名称
            if not stock_name:
                clean_name = line.split('(')[0].strip()
                if clean_name in STOCK_NAME_TO_CODE:
                    stock_name = clean_name
                    stock_code = STOCK_NAME_TO_CODE[clean_name]
                else:
                    stock_code = get_stock_code_by_name(clean_name)
                    if stock_code:
                        stock_name = STOCK_CODES_DICT.get(stock_code, clean_name)
            if stock_code and stock_name:
                target_stocks.append((stock_name, stock_code))
        if not target_stocks:
            messagebox.showwarning("警告", "没有找到有效的股票", parent=self.root)
            return
        try:
            # 创建回测结果窗口
            backtest_result_window = self._safe_toplevel(self.root)
            buy_date_str = buy_date.strftime('%Y-%m-%d')
            sell_date_str = sell_date.strftime('%Y-%m-%d') if sell_date else "至今"
            backtest_result_window.title(f"批量股票回测分析结果 - 买入日: {buy_date_str} 卖出日: {sell_date_str}")
            backtest_result_window.geometry("1000x700")
            # 确保窗口显示在最前面
            backtest_result_window.lift()
            backtest_result_window.focus_force()
            # 创建结果显示区域
            result_text_backtest = scrolledtext.ScrolledText(backtest_result_window, wrap=tk.WORD, font=("Consolas", 11))
            result_text_backtest.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            result_text_backtest.insert("1.0", "="*100 + "\n")
            result_text_backtest.insert(tk.END, "批量股票回测分析报告\n")
            result_text_backtest.insert(tk.END, f"买入日期: {buy_date_str}\n")
            result_text_backtest.insert(tk.END, f"卖出日期: {sell_date_str}\n")
            result_text_backtest.insert(tk.END, f"回测股票数量: {len(target_stocks)}\n")
            result_text_backtest.insert(tk.END, "本金: 1000万元\n")
            result_text_backtest.insert(tk.END, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            result_text_backtest.insert(tk.END, "="*100 + "\n\n")
            result_text_backtest.insert(tk.END, "正在计算回测结果,请稍候...\n\n")
            backtest_result_window.update_idletasks()
            backtest_result_window.update()
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", f"创建回测结果窗口失败: {e!s}", parent=self.root)
            return
        # 在后台线程中执行回测
        def custom_backtest_thread():
            try:
                backtest_results = []
                total_capital = 10000000  # 1000万
                # 更新进度信息
                def update_progress(msg):
                    try:
                        if backtest_result_window.winfo_exists():
                            result_text_backtest.insert(tk.END, f"{msg}\n")
                            result_text_backtest.see(tk.END)
                            backtest_result_window.update_idletasks()
                    except:
                        pass
                # 显示开始信息
                backtest_result_window.after(0, lambda: update_progress(f"开始回测,共 {len(target_stocks)} 只股票..."))
                time.sleep(0.1)  # 短暂延迟,确保窗口已显示
                for idx, (stock_name, stock_code) in enumerate(target_stocks, 1):
                    try:
                        # 更新进度
                        backtest_result_window.after(0, lambda n=stock_name, c=stock_code, i=idx, t=len(target_stocks): update_progress(f"[{i}/{t}] 正在计算 {n} ({c})..."))
                        if not AKSHARE_AVAILABLE:
                            continue
                        # 获取历史数据
                        hist_data = ak.stock_zh_a_hist(
                            symbol=stock_code,
                            period="daily",
                            adjust="qfq"
                        )
                        if hist_data is None or hist_data.empty:
                            continue
                        # 转换日期格式
                        hist_data['日期'] = pd.to_datetime(hist_data['日期']).dt.date
                        # 找到买入日的数据
                        buy_data = hist_data[hist_data['日期'] == buy_date]
                        if buy_data.empty:
                            # 找最近的数据
                            before_buy = hist_data[hist_data['日期'] <= buy_date]
                            if before_buy.empty:
                                continue
                            buy_data = before_buy.tail(1)
                        buy_date_actual = buy_data.iloc[0]['日期']
                        # 找到买入日次日的开盘价(买入价)
                        after_buy = hist_data[hist_data['日期'] > buy_date_actual].copy()
                        if after_buy.empty:
                            continue
                        # 买入日次日(第一个交易日)
                        next_day_data = after_buy.head(1)
                        if next_day_data.empty:
                            continue
                        next_day = next_day_data.iloc[0]['日期']
                        open_price = float(next_day_data.iloc[0]['开盘'])
                        close_price_prev = float(buy_data.iloc[0]['收盘'])
                        # 判断是否一字涨停板
                        limit_up_price = close_price_prev * 1.1
                        if open_price >= limit_up_price * 0.99:
                            continue
                        buy_price = open_price
                        # 计算卖出价
                        sell_price = None
                        sell_date_actual = None
                        profit_pct = None
                        if sell_date:
                            # 有指定卖出日期
                            sell_data = hist_data[hist_data['日期'] == sell_date]
                            if sell_data.empty:
                                # 找最近的数据
                                before_sell = hist_data[hist_data['日期'] <= sell_date]
                                if not before_sell.empty:
                                    sell_data = before_sell.tail(1)
                            if not sell_data.empty:
                                sell_date_actual = sell_data.iloc[0]['日期']
                                sell_price = float(sell_data.iloc[0]['收盘'])
                                profit_pct = ((sell_price - buy_price) / buy_price) * 100
                        else:
                            # 计算至今
                            latest_data = hist_data.tail(1)
                            if not latest_data.empty:
                                sell_date_actual = latest_data.iloc[0]['日期']
                                sell_price = float(latest_data.iloc[0]['收盘'])
                                profit_pct = ((sell_price - buy_price) / buy_price) * 100
                        if sell_price is None:
                            continue
                        backtest_data = {
                            'stock_name': stock_name,
                            'stock_code': stock_code,
                            'buy_date': next_day.strftime('%Y-%m-%d'),
                            'buy_price': buy_price,
                            'sell_date': sell_date_actual.strftime('%Y-%m-%d') if sell_date_actual else None,
                            'sell_price': sell_price,
                            'profit_pct': profit_pct,
                        }
                        backtest_results.append(backtest_data)
                    except Exception as e:
                        print(f"回测计算失败 {stock_name}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                # 计算每只股票的买入金额和市值
                if backtest_results:
                    capital_per_stock = total_capital / len(backtest_results)
                    for r in backtest_results:
                        r['buy_amount'] = capital_per_stock
                        r['sell_value'] = capital_per_stock * (1 + r['profit_pct'] / 100)
                # 显示结果
                def display_custom_backtest_results():
                    try:
                        result_text_backtest.delete("1.0", tk.END)
                        result_text_backtest.insert("1.0", "="*100 + "\n")
                        result_text_backtest.insert(tk.END, "批量股票回测分析报告\n")
                        result_text_backtest.insert(tk.END, f"买入日期: {buy_date_str}\n")
                        result_text_backtest.insert(tk.END, f"卖出日期: {sell_date_str}\n")
                        result_text_backtest.insert(tk.END, f"回测股票数量: {len(backtest_results)}\n")
                        result_text_backtest.insert(tk.END, "本金: 1000万元\n")
                        result_text_backtest.insert(tk.END, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        result_text_backtest.insert(tk.END, "="*100 + "\n\n")
                        if not backtest_results:
                            result_text_backtest.insert(tk.END, "没有符合条件的股票进行回测(可能都是一字涨停板买不进或数据获取失败)\n")
                            result_text_backtest.insert(tk.END, f"尝试回测的股票数量: {len(target_stocks)}\n")
                            result_text_backtest.insert(tk.END, "="*100 + "\n")
                            return
                        # 计算总体市值变化
                        total_value = sum(r['sell_value'] for r in backtest_results)
                        total_profit = total_value - total_capital
                        total_profit_pct = (total_profit / total_capital) * 100
                        capital_per_stock = total_capital / len(backtest_results)
                        result_text_backtest.insert(tk.END, "【总体市值变化统计】\n", "bold")
                        result_text_backtest.insert(tk.END, f"初始本金: {total_capital/10000:.2f}万元\n")
                        result_text_backtest.insert(tk.END, f"每只股票买入金额: {capital_per_stock/10000:.2f}万元\n\n")
                        tag = "red" if total_profit > 0 else "green"
                        result_text_backtest.insert(tk.END, f"总体市值: {total_value/10000:.2f}万元  ", tag)
                        result_text_backtest.insert(tk.END, f"盈亏: {total_profit/10000:.2f}万元 ({total_profit_pct:+.2f}%)\n", tag)
                        result_text_backtest.insert(tk.END, "\n" + "="*100 + "\n\n")
                        result_text_backtest.insert(tk.END, "【个股回测详情】\n", "bold")
                        for idx, r in enumerate(backtest_results, 1):
                            result_text_backtest.insert(tk.END, f"\n【{idx}】{r['stock_name']} ({r['stock_code']})\n", "bold")
                            result_text_backtest.insert(tk.END, f"买入日期: {r['buy_date']}  买入价: {r['buy_price']:.2f}  买入金额: {r['buy_amount']/10000:.2f}万元\n")
                            if r['sell_date']:
                                result_text_backtest.insert(tk.END, f"卖出日期: {r['sell_date']}  卖出价: {r['sell_price']:.2f}\n")
                            else:
                                result_text_backtest.insert(tk.END, f"当前日期: {r['sell_date']}  当前价: {r['sell_price']:.2f}\n")
                            tag = "red" if r['profit_pct'] > 0 else "green"
                            result_text_backtest.insert(tk.END, f"盈亏: {r['profit_pct']:.2f}%  市值: {r['sell_value']/10000:.2f}万元\n", tag)
                        result_text_backtest.insert(tk.END, "\n" + "="*100 + "\n")
                        result_text_backtest.insert(tk.END, "回测分析完成\n")
                        # 配置颜色标签
                        result_text_backtest.tag_config("red", foreground="red")
                        result_text_backtest.tag_config("green", foreground="green")
                        result_text_backtest.tag_config("bold", font=("Consolas", 11, "bold"))
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        result_text_backtest.delete("1.0", tk.END)
                        result_text_backtest.insert("1.0", f"显示回测结果失败: {e!s}\n")
                backtest_result_window.after(0, display_custom_backtest_results)
            except Exception as e:
                import traceback
                traceback.print_exc()
                def show_error(e=e):
                    result_text_backtest.delete("1.0", tk.END)
                    result_text_backtest.insert("1.0", f"回测计算失败: {e!s}\n")
                    result_text_backtest.insert(tk.END, traceback.format_exc())
                backtest_result_window.after(0, show_error)
        try:
            thread = threading.Thread(target=custom_backtest_thread, daemon=True)
            thread.start()
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", f"启动回测线程失败: {e!s}", parent=self.root)

    def _etf20_quick_backtest(self, pro, current_results, trade_date):
        """简化回测: 跑最近2年的月度调仓模拟"""
        import datetime as dt
        import time

        import numpy as np

        # 拉3年日线 (每只一次API)
        etf_codes = [r["ts_code"] for r in current_results]
        all_data = {}
        for tsc in etf_codes:
            try:
                h = pro.fund_daily(ts_code=tsc,
                    start_date=(dt.date.today()-dt.timedelta(days=1100)).strftime("%Y%m%d"),
                    end_date=trade_date)
                if h is not None and len(h) > 100:
                    all_data[tsc] = h.sort_values("trade_date").reset_index(drop=True)
                time.sleep(0.3)
            except Exception:
                pass

        if len(all_data) < 4:
            return {"win_rate": None, "note": "历史数据不足, 跳过回测"}

        # 计算每只ETF在绿灯/非绿灯状态下的下月平均收益
        stats = {}
        for tsc, df in all_data.items():
            cl = df["close"].values.astype(float)
            dates = df["trade_date"].values

            monthly = []
            last_month = ""
            for i in range(20, len(cl)-20):
                d = str(dates[i])
                ym = d[:6]
                if ym != last_month:
                    last_month = ym
                    ma20 = float(np.mean(cl[i-20:i]))
                    pct20 = (cl[i] - cl[i-20]) / cl[i-20] * 100
                    green = pct20 > 0 and cl[i] > ma20
                    next_ret = (cl[i+20] - cl[i]) / cl[i] * 100 if i+20 < len(cl) else None
                    if next_ret is not None:
                        monthly.append({"date": d, "green": green, "next_ret": next_ret})

            if monthly:
                green_rets = [m["next_ret"] for m in monthly if m["green"]]
                red_rets = [m["next_ret"] for m in monthly if not m["green"]]
                stats[tsc] = {
                    "n_months": len(monthly),
                    "green_avg": float(np.mean(green_rets)) if green_rets else 0,
                    "red_avg": float(np.mean(red_rets)) if red_rets else 0,
                    "green_count": len(green_rets),
                    "red_count": len(red_rets),
                }

        all_monthly_green_rets = []
        all_monthly_red_rets = []
        for s in stats.values():
            all_monthly_green_rets.extend([s["green_avg"]]*s["green_count"])
            all_monthly_red_rets.extend([s["red_avg"]]*s["red_count"])

        return {
            "win_rate_green": float(sum(1 for r in all_monthly_green_rets if r > 0) / max(len(all_monthly_green_rets), 1) * 100),
            "avg_ret_green": float(np.mean(all_monthly_green_rets)) if all_monthly_green_rets else 0,
            "avg_ret_red": float(np.mean(all_monthly_red_rets)) if all_monthly_red_rets else 0,
            "stats_per_etf": stats,
            "note": "简化回测: 绿灯状态下月平均收益 vs 非绿灯状态",
        }

    def _gather_trader_stock_context(self, stock_code: str):
        """交易员:单股近端 OHLC 与涨跌幅摘要。"""
        code = str(stock_code or "").strip().zfill(6)
        if len(code) != 6 or not code.isdigit():
            return None, "请输入6位股票代码或正确股票名称。"
        try:
            pack = self._fetch_recent_daily_ohlc(
                code, days=35, source="default", token=getattr(self, "ts_token", None)
            )
            if not pack or len(pack) < 4:
                return None, "无法获取日K线数据。"
            _dt, hi, lo, cl = pack[0], pack[1], pack[2], pack[3]
            n = len(cl)
            lines = []
            lines.append(f"股票代码:{code},共 {n} 个交易日(近样本)\n")
            for i in range(max(0, n - 8), n):
                lines.append(
                    f"  {i + 1}. 高={float(hi[i]):.3f} 低={float(lo[i]):.3f} 收={float(cl[i]):.3f}\n"
                )
            if n >= 2:
                chg = (float(cl[-1]) / float(cl[-2]) - 1.0) * 100.0
                lines.append(f"最新一日涨跌约:{chg:+.2f}%(相对前收)\n")
            return "\n".join(lines), None
        except Exception as e:
            return None, str(e)

    def _simulate_button_click(self, button):
        """模拟按钮点击"""
        try:
            if button and button.winfo_exists():
                # 获取按钮的命令函数并执行
                if hasattr(button, 'cget'):
                    command = button.cget("command")
                    if command:
                        command()
                else:
                    # 使用invoke方法
                    button.invoke()
        except Exception as e:
            print(f"[模拟按钮点击] 失败: {e}")


__all__ = ["TradeMixin"]
