"""检查/验证/判断"""
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


class ChecksMixin:
    """检查/验证/判断"""

    def _is_st_or_delisted_name(self, name):
        """排除 *ST / ST / S*ST 等(问财已带「非ST」时再防一层)。"""
        if not name or not str(name).strip():
            return False
        s = str(name).strip()
        import re as _re
        return bool(_re.match(r"^(\*ST|*ST|S\*ST|ST)", s, _re.IGNORECASE))

    def _ensure_tushare_client(self, token: str | None = None):
        """确保Tushare客户端可用"""
        if not TS_AVAILABLE:
            raise ImportError("tushare 未安装,请先执行 pip install tushare")
        token_to_use = (token or self.ts_token or TS_DEFAULT_TOKEN).strip()
        if not token_to_use:
            raise ValueError("Tushare token 不能为空")
        if self.ts_client is None or token_to_use != self.ts_token:
            import os
            os.environ["TUSHARE_TOKEN"] = token_to_use
            self.ts_client = ts.pro_api()
            self.ts_token = token_to_use
        return self.ts_client

    def _check_golden_stock_recent_20d(self, stock_code: str, stock_name: str = ""):
        """近20个交易日形态:涨停前有连续小阳、涨停日放量、涨停次日跳空高开。
        满足则在「热门股非去重」等同花顺表中标注黄金股。"""
        if not stock_code:
            return False
        code6 = str(stock_code).strip()[-6:].zfill(6)
        try:
            _dates, opens, highs, _lows, closes, vols = self._fetch_recent_daily_ohlcv(
                code6, days=32, source="default", token=self.ts_token
            )
        except Exception as e:
            print(f"[黄金股] {code6} 数据失败: {e}")
            return False
        n = len(closes)
        if n < 12 or len(opens) != n or len(highs) != n or len(vols) != n:
            return False
        lim = self._limit_up_pct_threshold(code6, stock_name)
        small_hi = min(5.5, max(2.0, lim * 0.48))
        min_small_run = 2
        vol_ratio_min = 1.28
        window = 20
        if n < window:
            return False
        seq = list(range(n - window, n))
        o = [opens[i] for i in seq]
        h = [highs[i] for i in seq]
        cl = [closes[i] for i in seq]
        v = [vols[i] for i in seq]
        W = window
        def day_pct_chg(idx):
            if idx <= 0:
                return None
            p0, p1 = cl[idx - 1], cl[idx]
            if not p0 or p0 <= 0:
                return None
            return (p1 - p0) / p0 * 100.0
        def is_limit_up_idx(idx):
            pc = day_pct_chg(idx)
            if pc is None:
                return False
            return pc >= lim * 0.985
        def is_small_yang_idx(idx):
            pc = day_pct_chg(idx)
            if pc is None:
                return False
            if is_limit_up_idx(idx):
                return False
            if pc <= 0.04:
                return False
            if pc >= small_hi:
                return False
            return cl[idx] > o[idx]
        for zt_i in range(min_small_run, W - 1):
            if not is_limit_up_idx(zt_i):
                continue
            if cl[zt_i] <= o[zt_i]:
                continue
            pre_start = max(0, zt_i - 5)
            pre_slice = v[pre_start:zt_i]
            if not pre_slice:
                continue
            vol_base = sum(pre_slice) / len(pre_slice)
            if vol_base <= 0 or v[zt_i] < vol_ratio_min * vol_base:
                continue
            if zt_i + 1 >= W:
                continue
            if not (o[zt_i + 1] > h[zt_i]):
                continue
            run = 0
            j = zt_i - 1
            while j >= 0 and is_small_yang_idx(j):
                run += 1
                j -= 1
            if run >= min_small_run:
                return True
        return False

    def _check_buy_signal(self):
        """检查持仓股是否有买入信号(收盘价上穿主力成本线)"""
        buy_signal_stocks = []
        try:
            for group_index in range(1, 6):
                holding_stocks, _, _, _ = self._get_holding_group_data(group_index)
                for stock in holding_stocks:
                    if not stock or not stock[0] or not stock[1]:
                        continue
                    stock_code = str(stock[1]).strip()
                    stock_name = str(stock[0]).strip()
                    try:
                        kline_data = self._get_daily_kline_data_tushare(stock_code, days=30)
                        if kline_data and 'ma_values' in kline_data and 'vwap' in kline_data['ma_values']:
                            closes = kline_data['data']['收盘'].values
                            vwap_values = kline_data['ma_values']['vwap']
                            if len(closes) >= 2 and len(vwap_values) >= 2:
                                last_close = closes[-1]
                                prev_close = closes[-2]
                                last_vwap = vwap_values[-1]
                                prev_vwap = vwap_values[-2]
                                # 买入信号:收盘价上穿主力成本线(今日收盘 > VWAP,昨日收盘 < VWAP)
                                if last_close > last_vwap and prev_close < prev_vwap:
                                    buy_signal_stocks.append(f"{stock_name}({stock_code})")
                    except Exception as e:
                        print(f"[买入信号检测] 检查股票 {stock_code} 失败: {e}")
        except Exception as e:
            print(f"[买入信号检测] 整体检测失败: {e}")
        try:
            if hasattr(self, 'buy_signal_label'):
                if buy_signal_stocks:
                    self.buy_signal_label.config(text="本买: " + ", ".join(buy_signal_stocks))
                else:
                    self.buy_signal_label.config(text="")
        except Exception as e:
            print(f"[买入信号检测] 更新标签失败: {e}")
        return buy_signal_stocks

    def _check_ma_status(self, stock_code):
        """检测均线状态,返回站上的均线列表,并计算10日均线距离"""
        try:
            if not stock_code:
                return {
                    'ma1': False, 'ma5': False, 'ma10': False, 'ma20': False,
                    'below_ma20': False, 'ma10_distance_pct': None, 'near_ma10': False,
                    'fish_body': False, 'fish_tail': False,
                }
            # 获取最近收盘价数据
            result = self._fetch_recent_daily_closes(stock_code, days=45, source="default", token=self.ts_token, return_volume=False)
            if isinstance(result, tuple) and len(result) >= 2:
                dates, closes = result[:2]
            else:
                _dates, closes = result, []
            if not closes or len(closes) < 3:
                return {
                    'ma1': False, 'ma5': False, 'ma10': False, 'ma20': False,
                    'below_ma20': False, 'ma10_distance_pct': None, 'near_ma10': False,
                    'fish_body': False, 'fish_tail': False,
                }
            # 优先获取实时价格或当日价格
            realtime_price = None
            try:
                # 尝试使用tushare获取实时价格
                if TS_AVAILABLE and (self.ts_token or TS_DEFAULT_TOKEN):
                    try:
                        import tushare as ts
                        ts_token = self.ts_token or TS_DEFAULT_TOKEN
                        os.environ["TUSHARE_TOKEN"] = ts_token
                        ts_code = self._format_ts_code(stock_code)
                        # 先尝试实时行情
                        try:
                            df = ts.realtime_quote(ts_code=ts_code, src='dc')
                            if df is not None and not df.empty and 'price' in df.columns:
                                realtime_price = float(df.iloc[0]['price'])
                                if realtime_price > 0.01 and realtime_price < 10000:
                                    print(f"[持仓检测-实时] {stock_code} 实时价格: {realtime_price}")
                        except:
                            pass  # 跳过 daily fallback
                    except Exception as e:
                        print(f"获取实时价格失败 {stock_code}: {e}")
            except:
                pass
            # 如果获取到实时价格,使用实时价格;否则使用历史收盘价
            if realtime_price and realtime_price > 0:
                latest_price = realtime_price
            else:
                latest_price = float(closes[-1])
            ref_ma10 = prev_ma10 = ref_ma20 = prev_ma20 = None
            ma_status = {
                'ma1': False, 'ma5': False, 'ma10': False, 'ma20': False,
                'below_ma20': False, 'ma10_distance_pct': None, 'near_ma10': False,
                'fish_body': False, 'fish_tail': False,
            }
            # 检测1日线(不判断是否上升,只判断是否站上)
            if len(closes) >= 3:
                ref_price = float(closes[-2])
                float(closes[-3])
                ma1_crossed = latest_price >= ref_price
                # 1日线只判断是否站上,不考虑是否上升
                ma_status['ma1'] = ma1_crossed
            # 检测5日线
            if len(closes) >= 7:
                ma5_values = [float(closes[i]) for i in range(len(closes)-5, len(closes))]
                ref_ma5 = sum(ma5_values) / len(ma5_values)
                prev_ma5_values = [float(closes[i]) for i in range(len(closes)-10, len(closes)-5)]
                prev_ma5 = sum(prev_ma5_values) / len(prev_ma5_values) if len(prev_ma5_values) >= 5 else ref_ma5
                ma5_crossed = latest_price >= ref_ma5
                ma5_uptrend = ref_ma5 >= prev_ma5
                ma_status['ma5'] = ma5_crossed and ma5_uptrend
            # 检测10日线
            if len(closes) >= 12:
                ma10_values = [float(closes[i]) for i in range(len(closes)-10, len(closes))]
                ref_ma10 = sum(ma10_values) / len(ma10_values)
                prev_ma10_values = [float(closes[i]) for i in range(len(closes)-20, len(closes)-10)]
                prev_ma10 = sum(prev_ma10_values) / len(prev_ma10_values) if len(prev_ma10_values) >= 10 else ref_ma10
                ma10_crossed = latest_price >= ref_ma10
                ma10_uptrend = ref_ma10 >= prev_ma10
                ma_status['ma10'] = ma10_crossed and ma10_uptrend
                # 计算价格距离10日均线的百分比
                if ref_ma10 > 0:
                    distance_pct = abs((latest_price - ref_ma10) / ref_ma10) * 100
                    ma_status['ma10_distance_pct'] = distance_pct
                    # 判断是否在3%以内
                    ma_status['near_ma10'] = distance_pct <= 3.0
            # 检测20日线
            if len(closes) >= 22:
                ma20_values = [float(closes[i]) for i in range(len(closes)-20, len(closes))]
                ref_ma20 = sum(ma20_values) / len(ma20_values)
                prev_ma20_values = [float(closes[i]) for i in range(len(closes)-40, len(closes)-20)]
                prev_ma20 = sum(prev_ma20_values) / len(prev_ma20_values) if len(prev_ma20_values) >= 20 else ref_ma20
                ma20_crossed = latest_price >= ref_ma20
                ma20_uptrend = ref_ma20 >= prev_ma20
                ma_status['ma20'] = ma20_crossed and ma20_uptrend
                # 检测股价是否低于20日线
                ma_status['below_ma20'] = latest_price < ref_ma20
            # 鱼身 / 鱼尾(持仓检测按钮):站上10日线且10日、20日均线向上 → 鱼身;跌破10日线或20日均线向下 → 鱼尾
            if ref_ma20 is not None and ref_ma10 is not None:
                above_ma10 = latest_price >= ref_ma10
                ma10_up = ref_ma10 >= prev_ma10
                ma20_up = ref_ma20 >= prev_ma20
                ma20_down = ref_ma20 < prev_ma20
                ma_status['fish_body'] = bool(above_ma10 and ma10_up and ma20_up)
                ma_status['fish_tail'] = bool((latest_price < ref_ma10) or ma20_down)
            elif ref_ma10 is not None:
                ma_status['fish_tail'] = bool(latest_price < ref_ma10)
            return ma_status
        except Exception as e:
            print(f"检测均线状态失败: {e}")
            return {
                'ma1': False, 'ma5': False, 'ma10': False, 'ma20': False,
                'below_ma20': False, 'ma10_distance_pct': None, 'near_ma10': False,
                'fish_body': False, 'fish_tail': False,
            }

    def _check_new_high(self, stock_code, days=60):
        """检查股票是否创新高"""
        try:
            kd = self._get_daily_kline_data_tushare(str(stock_code).zfill(6), days=days)
            if not kd:
                return False
            highs = kd['data']['最高'].values
            if len(highs) < 2:
                return False
            current_high = float(highs[-1])
            previous_highs = highs[:-1]
            return current_high > max(previous_highs)
        except Exception:
            return False

    def _is_a_share_trading_time(now=None):
        """判断当前是否A股盘中（周一至周五 9:30-11:30 / 13:00-15:00，排除节假日太复杂，粗略判断即可）"""
        import datetime as dt
        if now is None: now = dt.datetime.now()
        # 周末直接不是
        if now.weekday() >= 5: return False
        h, m = now.hour, now.minute
        t = h * 60 + m
        return (9*60+30 <= t <= 11*60+30) or (13*60 <= t <= 15*60)


__all__ = ["ChecksMixin"]
