"""个股详情/K线/分时/分钟"""
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
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
except ImportError: plt = None
from utils.network import safe_call
from utils.config import *  # 路径/配置/Token
from data.snapshot import *  # get_news_stocks_* 函数
from logic.stock_names import *  # get_stock_name_by_code 等

from datetime import datetime, timedelta
import re
import os
import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin
import sqlite3

# ===== 模块级: 买卖点计算 + 回测 (供 K 线弹窗复用) =====
def calc_trade_signals(closes, opens, highs, lows, vols):
    """
    计算完整 4 类买卖点信号
    返回: {
        'buy':   [(idx, y, label, color, symbol), ...]  # ★ 买入
        'add':   [(idx, y, label, color, symbol), ...]  # ▲ 加仓
        'sell':  [(idx, y, label, color, symbol), ...]  # ▼ 卖出
        'reduce': [(idx, y, label, color, symbol), ...] # ▽ 减仓
    }
    """
    import numpy as np
    _nan = np.nan
    n = len(closes)
    if n < 30: return {"buy": [], "add": [], "sell": [], "reduce": []}

    # MA
    def _ma(a, p):
        r = np.full(len(a), _nan); 
        if len(a) >= p:
            cumsum = np.cumsum(np.insert(a, 0, 0))
            r[p-1:] = (cumsum[p:] - cumsum[:-p]) / p
        return r
    m5 = _ma(closes.astype(float), 5); m10 = _ma(closes.astype(float), 10)
    m20 = _ma(closes.astype(float), 20)
    # MACD DIF / DEA — 用 pandas ewm, 避免自写 _ema 在某些情况下崩 (float16 / empty_like 未定义行为)
    try:
        import pandas as _pd
        _s = _pd.Series(closes.astype(float))
        ema12 = _s.ewm(span=12, adjust=False).mean().values
        ema26 = _s.ewm(span=26, adjust=False).mean().values
        dif = ema12 - ema26
        dea = _pd.Series(dif).ewm(span=9, adjust=False).mean().values
    except Exception:
        # fallback: 自写版本 (偶尔会崩, 但保底)
        def _ema(a, w):
            r = np.empty_like(a, dtype=np.float64); r[0] = a[0]; k = 2/(w+1)
            for i in range(1, len(a)): r[i] = a[i]*k + r[i-1]*(1-k)
            return r
        ema12 = _ema(closes.astype(float), 12); ema26 = _ema(closes.astype(float), 26)
        dif = ema12 - ema26; dea = _ema(dif, 9)
    # KDJ K/D
    k_arr = np.full(n, 50.0); d_arr = np.full(n, 50.0)
    for i in range(9, n):
        rv = max(highs[i-8:i+1]) - min(lows[i-8:i+1])
        rsv = (closes[i] - min(lows[i-8:i+1])) / max(rv, 0.001) * 100
        k_arr[i] = k_arr[i-1]*2/3 + rsv*1/3
        d_arr[i] = d_arr[i-1]*2/3 + k_arr[i]*1/3
    # BOLL
    boll_up = np.full(n, _nan); boll_lo = np.full(n, _nan)
    for i in range(19, n):
        seg = closes[i-19:i+1].astype(float)
        ma20v = np.mean(seg); stdev = np.std(seg)
        boll_up[i] = ma20v + 2*stdev; boll_lo[i] = ma20v - 2*stdev

    _buy, _sell, _add, _red = [], [], [], []
    # 1. MA5×MA10 金叉死叉
    for i in range(1, n):
        if _nan in (m5[i], m10[i], m5[i-1], m10[i-1]): continue
        if m5[i-1] < m10[i-1] and m5[i] >= m10[i]:
            _buy.append((i, lows[i]*0.97, "MA金", "#2E7D32", "★"))
        elif m5[i-1] > m10[i-1] and m5[i] <= m10[i]:
            _sell.append((i, highs[i]*1.03, "MA死", "#C62828", "▼"))
    # 2. MACD DIF×DEA
    for i in range(1, n):
        if dif[i-1] < dea[i-1] and dif[i] >= dea[i]:
            if dif[i] < 0: _buy.append((i, lows[i]*0.96, "MACD金", "#1565C0", "★"))
            else: _add.append((i, lows[i]*0.95, "MACD金(强)", "#FF9800", "▲"))
        elif dif[i-1] > dea[i-1] and dif[i] <= dea[i]:
            if dif[i] > 0: _sell.append((i, highs[i]*1.04, "MACD死", "#B71C1C", "▼"))
            else: _red.append((i, highs[i]*1.05, "MACD死(弱)", "#6A1B9A", "▽"))
    # 3. KDJ 低位金叉 / 高位死叉
    for i in range(1, n):
        if k_arr[i-1] < d_arr[i-1] and k_arr[i] >= d_arr[i]:
            if k_arr[i] < 30: _buy.append((i, lows[i]*0.95, "KDJ金(低)", "#388E3C", "★"))
        elif k_arr[i-1] > d_arr[i-1] and k_arr[i] <= d_arr[i]:
            if k_arr[i] > 70: _sell.append((i, highs[i]*1.05, "KDJ死(高)", "#D32F2F", "▼"))
    # 4. BOLL 反弹 / 回落
    for i in range(1, n):
        if _nan in (boll_up[i], boll_lo[i]): continue
        if closes[i-1] <= boll_lo[i-1] and closes[i] > boll_lo[i] and closes[i] > opens[i]:
            _buy.append((i, lows[i]*0.96, "布林反弹", "#00796B", "★"))
        elif closes[i-1] >= boll_up[i-1] and closes[i] < boll_up[i] and closes[i] < opens[i]:
            _sell.append((i, highs[i]*1.04, "布林回落", "#BF360C", "▼"))
    # 5. 放量突破前高 / 跌破前低 (20日窗口)
    vol_ma20 = np.full(n, 0.0)
    for i in range(19, n):
        vol_ma20[i] = np.mean(vols[i-19:i+1].astype(float))
    for i in range(20, n):
        prev_hi = max(highs[i-20:i]); prev_lo = min(lows[i-20:i])
        if closes[i] > prev_hi and vols[i] > vol_ma20[i]*1.5:
            if not any(abs(p[0]-i)<3 for p in _add):
                _add.append((i, lows[i]*0.93, "放量突破", "#F57C00", "▲"))
        if closes[i] < prev_lo and vols[i] > vol_ma20[i]*1.5:
            if not any(abs(p[0]-i)<3 for p in _red):
                _red.append((i, highs[i]*1.07, "放量破位", "#4A148C", "▽"))

    def _dedup(pts):
        best = {}
        for idx, y, lbl, col, sym in pts:
            if idx not in best: best[idx] = (y, lbl, col, sym)
            elif y < best[idx][0]: best[idx] = (y, lbl, col, sym)
        return [(idx, best[idx][0], best[idx][1], best[idx][2], best[idx][3])
                for idx in sorted(best.keys())]
    for k in (_buy, _sell, _add, _red):
        k = _dedup(k)
    # 只保留近 80 根 (避免密集)
    _cut = max(0, n - 120)
    return {
        "buy":    [p for p in _buy if p[0] >= _cut],
        "sell":   [p for p in _sell if p[0] >= _cut],
        "add":    [p for p in _add if p[0] >= _cut],
        "reduce": [p for p in _red if p[0] >= _cut],
        # 完整历史 (不截断) 供回测
        "buy_all": _dedup(_buy), "sell_all": _dedup(_sell),
        "add_all": _dedup(_add), "reduce_all": _dedup(_red),
    }

def backtest_signal(signal_type, signals_full, closes, highs=None, lows=None,
                    stop_loss_pct=0.05, take_profit_pct=0.10, max_hold_days=20):
    """
    真·回测: 带止损止盈 + 最大持仓天数 + 多时间窗统计 (告别固定 10 天)

    signal_type: 'buy'/'add'/'sell'/'reduce'
    signals_full: [(idx, y, lbl, col, sym), ...]
    closes/highs/lows: OHLC 序列
    stop_loss_pct: 止损线 (默认 5%)
    take_profit_pct: 止盈线 (默认 10%, 设 None 即不止盈)
    max_hold_days: 最大持仓天数 (默认 20, 超过按收盘价平仓)

    返回: {
        "count": 样本数,
        "win_rate": 胜率 %,
        "avg_profit": 平均盈利 %,
        "avg_loss": 平均亏损 %,
        "plr": 盈亏比,
        "median_ret": 收益中位数 %,
        "best": 单笔最佳 %, "worst": 单笔最差 %,
        "avg_hold_days": 平均持仓天数,
        "exit_reasons": {"止盈": n, "止损": n, "超时": n},
        "wr_by_window": {5: wr5%, 10: wr10%, 20: wr20%},  # 不同时间窗胜率
        "ret_by_window": {5: ret5%, 10: ret10%, 20: ret20%}, # 不同时间窗平均收益
    } 或 None
    """
    import numpy as np
    pts = signals_full
    if not pts or len(pts) < 3: return None
    c_arr = np.asarray(closes, dtype=float)
    h_arr = np.asarray(highs, dtype=float) if highs is not None else c_arr
    l_arr = np.asarray(lows, dtype=float) if lows is not None else c_arr
    n = len(c_arr)
    # 方向: buy/add 做多, sell/reduce 做空
    is_long = signal_type in ("buy", "add")

    trades = []  # [(entry_idx, exit_idx, ret%, hold_days, exit_reason)]
    # 用于固定时间窗统计 (5/10/20 天)
    wins_w = {5: 0, 10: 0, 20: 0}; rets_w = {5: [], 10: [], 20: []}

    for entry_idx, _y, _lbl, _col, _sym in pts:
        # entry_idx 必须留够 max_hold_days
        if entry_idx + 1 >= n: continue
        entry_p = float(c_arr[entry_idx])
        window_end = min(entry_idx + max_hold_days + 1, n)
        if window_end <= entry_idx + 1: continue

        # --- 固定时间窗统计 (不影响主回测, 只是并行记录) ---
        for _w in (5, 10, 20):
            _ei = entry_idx + _w
            if _ei >= n: continue
            _ep = float(c_arr[_ei])
            if is_long: _r = (_ep - entry_p) / entry_p * 100
            else: _r = (entry_p - _ep) / entry_p * 100
            rets_w[_w].append(_r)
            if _r >= 0: wins_w[_w] += 1

        # --- 真实逐 bar 止损止盈 ---
        exit_idx = None; exit_reason = None
        for j in range(entry_idx + 1, window_end):
            h_j = float(h_arr[j]); l_j = float(l_arr[j]); c_j = float(c_arr[j])
            if is_long:
                # 多头: 先看止损还是先看止盈 (通常止损先触发)
                # 日内先探低点 → 止损; 再探高点 → 止盈
                # 简化: 用当日 low 判断止损, high 判断止盈, 谁先到算谁
                if stop_loss_pct and l_j <= entry_p * (1 - stop_loss_pct):
                    exit_idx = j; exit_reason = "止损"; break
                if take_profit_pct and h_j >= entry_p * (1 + take_profit_pct):
                    exit_idx = j; exit_reason = "止盈"; break
            else:
                # 空头: 反向
                if stop_loss_pct and h_j >= entry_p * (1 + stop_loss_pct):
                    exit_idx = j; exit_reason = "止损"; break
                if take_profit_pct and l_j <= entry_p * (1 - take_profit_pct):
                    exit_idx = j; exit_reason = "止盈"; break
        if exit_idx is None:
            exit_idx = window_end - 1
            exit_reason = "超时"
        exit_p = float(c_arr[exit_idx])
        if is_long: ret = (exit_p - entry_p) / entry_p * 100
        else: ret = (entry_p - exit_p) / entry_p * 100
        hold_days = exit_idx - entry_idx
        trades.append((entry_idx, exit_idx, ret, hold_days, exit_reason))

    if not trades: return None
    rets = [t[2] for t in trades]
    holds = [t[3] for t in trades]
    gains = [r for r in rets if r >= 0]
    losses = [abs(r) for r in rets if r < 0]
    cnt = len(trades)
    wr = len(gains) / cnt * 100
    avg_gain = float(np.mean(gains)) if gains else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0
    plr = avg_gain / max(avg_loss, 0.01)
    # 出场原因统计
    exit_reasons = {}
    for t in trades:
        exit_reasons[t[4]] = exit_reasons.get(t[4], 0) + 1
    # 时间窗胜率
    wr_by_w = {}; ret_by_w = {}
    for _w in (5, 10, 20):
        if rets_w[_w]:
            wr_by_w[_w] = wins_w[_w] / len(rets_w[_w]) * 100
            ret_by_w[_w] = float(np.mean(rets_w[_w]))
        else:
            wr_by_w[_w] = 0; ret_by_w[_w] = 0.0

    return {
        "count": cnt,
        "win_rate": wr,
        "avg_profit": avg_gain,
        "avg_loss": avg_loss,
        "plr": plr,
        "median_ret": float(np.median(rets)),
        "best": float(max(rets)),
        "worst": float(min(rets)),
        "avg_hold_days": float(np.mean(holds)),
        "exit_reasons": exit_reasons,
        "wr_by_window": wr_by_w,
        "ret_by_window": ret_by_w,
    }


def backtest_single_point(idx, closes, highs=None, lows=None,
                          signal_type="buy",
                          stop_loss_pct=0.05, take_profit_pct=0.10, max_hold_days=20):
    """
    单点回测: 只回测第 idx 这一个信号点后面发生了什么
    返回 dict (entry / exit 实值 + 1/5/10/20 日收益 + 凯利用真实历史胜率参考) 或 None
    """
    import numpy as np
    c_arr = np.asarray(closes, dtype=float)
    h_arr = np.asarray(highs, dtype=float) if highs is not None else c_arr
    l_arr = np.asarray(lows, dtype=float) if lows is not None else c_arr
    n = len(c_arr)
    if idx + 1 >= n: return None
    is_long = signal_type in ("buy", "add")

    entry_p = float(c_arr[idx])
    entry_date_idx = idx
    window_end = min(idx + max_hold_days + 1, n)

    # 真实逐 bar 止损止盈 (谁先到算谁)
    exit_idx = None; exit_reason = None
    for j in range(idx + 1, window_end):
        h_j = float(h_arr[j]); l_j = float(l_arr[j])
        if is_long:
            if stop_loss_pct and l_j <= entry_p * (1 - stop_loss_pct):
                exit_idx = j; exit_reason = "止损"; break
            if take_profit_pct and h_j >= entry_p * (1 + take_profit_pct):
                exit_idx = j; exit_reason = "止盈"; break
        else:
            if stop_loss_pct and h_j >= entry_p * (1 + stop_loss_pct):
                exit_idx = j; exit_reason = "止损"; break
            if take_profit_pct and l_j <= entry_p * (1 - take_profit_pct):
                exit_idx = j; exit_reason = "止盈"; break
    if exit_idx is None:
        exit_idx = window_end - 1
        exit_reason = "超时"
    exit_p = float(c_arr[exit_idx])
    if is_long: ret = (exit_p - entry_p) / entry_p * 100
    else: ret = (entry_p - exit_p) / entry_p * 100

    # 固定时间窗收益 (5/10/20 日收盘价, 不管止盈止损)
    rets_w = {}
    for _w in (1, 3, 5, 10, 20):
        _ei = idx + _w
        if _ei < n:
            _ep = float(c_arr[_ei])
            rets_w[_w] = (_ep - entry_p) / entry_p * 100 if is_long else (entry_p - _ep) / entry_p * 100
        else:
            rets_w[_w] = None

    # 同期统计: 用历史同类型信号, 算胜率/盈亏比 (这个点是第几笔)
    # 简化: 返回这个点自己的真实结果 + 历史同类型 aggregate
    return {
        "entry_idx": idx, "entry_p": entry_p,
        "exit_idx": exit_idx, "exit_p": exit_p,
        "ret": float(ret),
        "hold_days": int(exit_idx - idx),
        "exit_reason": exit_reason,
        "wins": 1 if ret >= 0 else 0,
        "rets_by_window": rets_w,
    }


def backtest_build_per_point_cache(signal_type, signals_full, closes, highs=None, lows=None,
                                   stop_loss_pct=0.05, take_profit_pct=0.10, max_hold_days=20):
    """
    按 idx→单点回测结果 dict 构建缓存, 同时返回 aggregate 统计
    返回: (per_point_dict, aggregate_dict_or_None)
    """
    if not signals_full or len(signals_full) < 1: return {}, None
    per_point = {}
    for _pt in signals_full:
        _idx = _pt[0]
        _s = backtest_single_point(_idx, closes, highs=highs, lows=lows,
                                    signal_type=signal_type,
                                    stop_loss_pct=stop_loss_pct,
                                    take_profit_pct=take_profit_pct,
                                    max_hold_days=max_hold_days)
        if _s is not None:
            per_point[_idx] = _s
    # 同时返回 aggregate (用于标题栏凯利计算)
    agg = backtest_signal(signal_type, signals_full, closes, highs=highs, lows=lows,
                          stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct,
                          max_hold_days=max_hold_days)
    return per_point, agg


class StockDetailMixin:
    """个股详情/K线/分时/分钟"""

    def show_kline_dialog(self):
        """显示K线图对话框"""
        try:
            # 先获取热门股票作为默认数据
            hot_stocks = get_news_stocks_merged_recent_days(ndays=5)
            if hot_stocks:
                stock_name, stock_code = hot_stocks[0]
                # 获取K线数据
                kline_data = self._get_daily_kline_data_tushare(stock_code)
                if kline_data:
                    # 打开K线图弹窗
                    self._show_daily_kline_zoom(kline_data, stock_name)
                else:
                    messagebox.showwarning("提示", "无法获取股票K线数据", parent=self.root)
            else:
                messagebox.showwarning("提示", "暂无热门股票数据", parent=self.root)
        except Exception as e:
            messagebox.showerror("错误", f"打开K线图失败: {e}", parent=self.root)

    def _calc_intraday_composite(self, data):
        """主流量化盘中综合判别: 5维度打分 → 优良差危险
        维度: 指数趋势(25%) + 涨跌广度(25%) + 涨停情绪(20%) + 量能对比(15%) + 均线位置(15%)"""
        details = []
        scores = []

        # 1. 指数趋势分 (25%)
        idx_list = data.get("indices", [])
        if idx_list:
            main_idx = None
            for it in idx_list:
                if it["code"] == "000001": main_idx = it; break
            if main_idx is None and idx_list: main_idx = idx_list[0]
            idx_pct = main_idx["pct"] if main_idx else 0
            if idx_pct > 1.5: isc = 95; idesc = f"上证+{idx_pct:.2f}% 强趋势"
            elif idx_pct > 0.3: isc = 75; idesc = f"上证+{idx_pct:.2f}% 温和上涨"
            elif idx_pct > -0.3: isc = 50; idesc = f"上证{idx_pct:+.2f}% 震荡"
            elif idx_pct > -1.5: isc = 25; idesc = f"上证{idx_pct:+.2f}% 温和下跌"
            else: isc = 5; idesc = f"上证{idx_pct:+.2f}% 大跌!"
            scores.append(("指数趋势", isc, 25, idesc))
        else:
            scores.append(("指数趋势", 50, 25, "无数据"))

        # 2. 涨跌广度分 (25%)
        br = data.get("breadth", {})
        up, dn = br.get("up", 0), br.get("down", 0)
        if up + dn > 0:
            ratio = up / max(dn, 1)
            if ratio > 2.5: bsc = 95; bdesc = f"涨{up}/跌{dn} 极度普涨"
            elif ratio > 1.5: bsc = 75; bdesc = f"涨{up}/跌{dn} 偏多"
            elif ratio > 1.0: bsc = 60; bdesc = f"涨{up}/跌{dn} 略多"
            elif ratio > 0.7: bsc = 35; bdesc = f"涨{up}/跌{dn} 偏空"
            elif ratio > 0.4: bsc = 20; bdesc = f"涨{up}/跌{dn} 明显偏弱"
            else: bsc = 5; bdesc = f"涨{up}/跌{dn} 暴跌!"
            scores.append(("涨跌广度", bsc, 25, bdesc))
        else:
            scores.append(("涨跌广度", 50, 25, "无数据"))

        # 3. 涨停情绪分 (20%)
        zt, dt = br.get("zt", 0), br.get("dt", 0)
        if zt >= 80: zsc = 95; zdesc = f"涨停{zt} 高潮!"
        elif zt >= 50: zsc = 80; zdesc = f"涨停{zt} 情绪好"
        elif zt >= 25: zsc = 60; zdesc = f"涨停{zt} 一般"
        elif zt >= 10: zsc = 40; zdesc = f"涨停{zt} 偏弱"
        elif zt > 0: zsc = 20; zdesc = f"涨停{zt} 冰点"
        else: zsc = 10; zdesc = "0涨停 极寒!"
        if dt >= 10: zsc -= 20; zdesc += f" 跌停{dt}!"
        elif dt >= 5: zsc -= 10; zdesc += f" 跌停{dt}"
        scores.append(("涨停情绪", max(0, min(100, zsc)), 20, zdesc))

        # 4. 量能对比分 (15%)
        ar = data.get("amount_ratio", 1.0)
        if ar > 1.5: asc = 90; adesc = f"量比5日均量{ar:.1f}x 放量活跃"
        elif ar > 1.1: asc = 70; adesc = f"量比{ar:.1f}x 温和"
        elif ar > 0.8: asc = 50; adesc = f"量比{ar:.1f}x 正常"
        elif ar > 0.5: asc = 30; adesc = f"量比{ar:.1f}x 缩量"
        else: asc = 15; adesc = f"量比{ar:.1f}x 极度缩量"
        scores.append(("量能对比", asc, 15, adesc))

        # 5. 均线位置分 (15%)
        sh_ma5 = data.get("sh_ma5")
        sh_ma20 = data.get("sh_ma20")
        idx_list[0]["pct"] if idx_list else 0
        sh_close = idx_list[0]["close"] if idx_list else 0
        if sh_ma5 and sh_close > 0:
            if sh_close > sh_ma5 > sh_ma20: msc = 90; mdesc = "上证>MA5>MA20 多头排列"
            elif sh_close > sh_ma5: msc = 70; mdesc = "上证>MA5 站上短线均线"
            elif sh_close < sh_ma5 < sh_ma20: msc = 20; mdesc = "上证<MA5<MA20 空头排列"
            elif sh_close < sh_ma5: msc = 35; mdesc = "上证<MA5 跌破短线均线"
            else: msc = 50; mdesc = "均线缠绕"
            scores.append(("均线位置", msc, 15, mdesc))
        else:
            scores.append(("均线位置", 50, 15, "无数据"))

        # 加权总分
        total_w = sum(w for _, _, w, _ in scores)
        total_s = sum(s * w for _, s, w, _ in scores)
        final_score = round(total_s / total_w) if total_w > 0 else 50

        # 等级判定
        if final_score >= 75:
            level, signal = "excellent", "🟢"
            level_cn = "优"
        elif final_score >= 55:
            level, signal = "good", "🔵"
            level_cn = "良"
        elif final_score >= 35:
            level, signal = "warning", "🟡"
            level_cn = "差"
        else:
            level, signal = "danger", "🔴"
            level_cn = "危险"

        for name, s, w, desc in scores:
            emoji = "🟢" if s >= 70 else ("🟡" if s >= 40 else "🔴")
            details.append(f"{emoji} {name}: {s}分 ({w}%) → {desc}")

        return {"score": final_score, "level": level, "level_cn": level_cn,
                "signal": signal, "details": details}, details

    def _get_15min_kline_data(self, stock_code, days=10):
        """获取15分钟K线数据(10日周期)"""
        try:
            # 计算开始日期
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            start_date_str = start_date.strftime('%Y%m%d')
            end_date_str = end_date.strftime('%Y%m%d')
            # 获取15分钟K线数据
            kline_data = ak.stock_zh_a_hist_min_em(symbol=stock_code, period="15",
                                                   start_date=start_date_str,
                                                   end_date=end_date_str, adjust="")
            if kline_data is None or kline_data.empty:
                return None
            # 计算均线(1日、3日、5日、10日、20日)
            # 注意:15分钟K线,每天约16根(交易时间4小时=240分钟,240/15=16根)
            # 1日=1*16=16根,3日=48根,5日=80根,10日=160根,20日=320根
            close_prices = kline_data['收盘'].values if '收盘' in kline_data.columns else kline_data.iloc[:, -2].values
            # 计算均线周期(15分钟K线)
            periods = {
                'ma1': min(16, len(close_prices)),    # 1日约16根
                'ma3': min(48, len(close_prices)),    # 3日约48根
                'ma5': min(80, len(close_prices)),    # 5日约80根
                'ma10': min(160, len(close_prices)),  # 10日约160根
                'ma20': min(320, len(close_prices))   # 20日约320根
            }
            # 计算各均线值
            ma_values = {}
            for ma_name, period in periods.items():
                if len(close_prices) >= period:
                    ma_values[ma_name] = []
                    for i in range(period-1, len(close_prices)):
                        ma_value = sum(close_prices[i-period+1:i+1]) / period
                        ma_values[ma_name].append(ma_value)
                else:
                    ma_values[ma_name] = []
            return {
                'data': kline_data,
                'ma_values': ma_values,
                'dates': kline_data.index if hasattr(kline_data.index, '__len__') else range(len(kline_data))
            }
        except Exception as e:
            print(f"获取15分钟K线数据失败 {stock_code}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_daily_kline_data_tushare(self, stock_code, days=60):
        """获取日K线数据: Tushare Pro 优先 (0.08s), akshare 兜底"""
        # ===== 方案1: Tushare =====
        try:
            if TS_AVAILABLE and (getattr(self, 'ts_token', None) or TS_DEFAULT_TOKEN):
                self._ensure_tushare_client(self.ts_token or TS_DEFAULT_TOKEN)
                ts_code = self._format_ts_code(str(stock_code).zfill(6))
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=days + 30)).strftime('%Y%m%d')
                df = self.ts_client.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                if df is not None and not df.empty:
                    df = df.sort_values('trade_date').tail(days).reset_index(drop=True)
                    _vol = df['vol'].astype(float) if 'vol' in df.columns else pd.Series(np.zeros(len(df)))
                    data = pd.DataFrame({
                        '开盘': df['open'].astype(float), '收盘': df['close'].astype(float),
                        '最高': df['high'].astype(float), '最低': df['low'].astype(float),
                        '成交量': _vol,
                    })
                    close_prices = data['收盘'].values; opens = data['开盘'].values
                    highs = data['最高'].values; lows = data['最低'].values
                    periods = {'ma1': 1, 'ma5': 5, 'ma10': 10, 'ma20': 20}
                    ma_values = {}
                    for ma_name, period in periods.items():
                        if len(close_prices) >= period:
                            ma_values[ma_name] = [float(sum(close_prices[i - period + 1:i + 1]) / period)
                                                  for i in range(period - 1, len(close_prices))]
                        else:
                            ma_values[ma_name] = []
                    vwap_values = []
                    if len(close_prices) >= 2:
                        cum_amount = 0.0; cum_vol = 0.0
                        for i in range(len(close_prices)):
                            typ = (opens[i] + highs[i] + lows[i] + close_prices[i]) / 4.0
                            cum_amount += typ * float(data['成交量'].iloc[i]); cum_vol += float(data['成交量'].iloc[i])
                            vwap_values.append(float(cum_amount / cum_vol) if cum_vol > 0 else float(typ))
                    ma_values['vwap'] = vwap_values
                    dates_list = list(df['trade_date'].astype(str))
                    print(f"  [K线] ✅ Tushare Pro tab_stock_detail {stock_code} {len(data)} 根")
                    return {'data': data, 'ma_values': ma_values, 'dates': dates_list, 'trade_dates': dates_list}
        except Exception as e:
            print(f"  [K线] tab_stock_detail Tushare 挂: {e}")
        # ===== 方案2: akshare 兜底 =====
        try:
            return self._get_daily_kline_data_akshare(stock_code, days)
        except Exception as e:
            print(f"  [K线] tab_stock_detail akshare 挂: {e}")
        return None

    def _get_daily_kline_data_akshare(self, stock_code, days=60):
        """akshare 获取日K线 (新浪 stock_zh_a_daily + 直连兜底)"""
        from ui._akshare_fetcher import fetch_daily_kline
        code = str(stock_code).zfill(6)
        df = fetch_daily_kline(code, days=days + 30)
        if df is None or len(df) < 30:
            return None
        df = df.sort_values('date').tail(days).reset_index(drop=True)
        data = pd.DataFrame({
            '开盘': df['open'].astype(float),
            '收盘': df['close'].astype(float),
            '最高': df['high'].astype(float),
            '最低': df['low'].astype(float),
            '成交量': df['volume'].astype(float),
        })
        close_prices = data['收盘'].values; opens = data['开盘'].values
        highs = data['最高'].values; lows = data['最低'].values
        periods = {'ma1': 1, 'ma5': 5, 'ma10': 10, 'ma20': 20}
        ma_values = {}
        for ma_name, period in periods.items():
            if len(close_prices) >= period:
                ma_values[ma_name] = [float(sum(close_prices[i - period + 1:i + 1]) / period)
                                      for i in range(period - 1, len(close_prices))]
            else:
                ma_values[ma_name] = []
        vwap_values = []
        if len(close_prices) >= 2:
            cum_amount = 0.0; cum_vol = 0.0
            for i in range(len(close_prices)):
                typ = (opens[i] + highs[i] + lows[i] + close_prices[i]) / 4.0
                cum_amount += typ * float(data['成交量'].iloc[i]); cum_vol += float(data['成交量'].iloc[i])
                vwap_values.append(float(cum_amount / cum_vol) if cum_vol > 0 else float(typ))
        ma_values['vwap'] = vwap_values
        dates_list = pd.to_datetime(df['date']).dt.strftime('%Y%m%d').tolist()
        return {'data': data, 'ma_values': ma_values, 'dates': dates_list, 'trade_dates': dates_list}

    def _apply_daily_kline_ax(self, ax1, kline_data, stock_name, show_zoom_hint=True, hide_x_labels=False, show_support_resistance=True, show_bs_signals=True):
        """在给定 Axes 上绘制主图 K 线 + 均线 + 支撑/压力线。"""
        data = kline_data['data']
        ma_values = kline_data['ma_values']
        trade_dates = kline_data.get('trade_dates') or list(range(len(data)))
        dates = list(range(len(data)))
        n = len(dates)
        opens = data['开盘'].values
        closes = data['收盘'].values
        highs = data['最高'].values
        lows = data['最低'].values
        for i in range(len(dates)):
            color = 'red' if closes[i] >= opens[i] else 'green'
            body_bottom = min(opens[i], closes[i])
            body_top = max(opens[i], closes[i])
            ax1.bar(i, body_top - body_bottom, bottom=body_bottom, color=color, alpha=0.8, width=0.6)
            ax1.plot([i, i], [lows[i], body_bottom], color=color, linewidth=1)
            ax1.plot([i, i], [body_top, highs[i]], color=color, linewidth=1)
        ax1.plot(dates, closes, color='black', linewidth=0.5, label='收盘价', alpha=0.5, linestyle='--')
        ma_colors = {'ma1': '#FF0000', 'ma5': '#00FF00', 'ma10': '#0000FF', 'ma20': '#FF00FF', 'vwap': '#FFD700'}
        ma_labels = {'ma1': '1日均线', 'ma5': '5日均线', 'ma10': '10日均线', 'ma20': '20日均线', 'vwap': '主力成本线'}
        period_map = {'ma1': 1, 'ma5': 5, 'ma10': 10, 'ma20': 20, 'vwap': 1}
        for ma_name in ['ma1', 'ma5', 'ma10', 'ma20', 'vwap']:
            if ma_name not in ma_values or len(ma_values[ma_name]) == 0:
                continue
            ma_data = ma_values[ma_name]
            period = period_map[ma_name]
            start_idx = min(period - 1, len(dates) - 1)
            ma_indices = list(range(start_idx, start_idx + len(ma_data)))
            min_len = min(len(ma_indices), len(ma_data))
            if min_len > 0:
                ax1.plot(ma_indices[:min_len], ma_data[:min_len], color=ma_colors[ma_name],
                        linewidth=1.5, label=ma_labels[ma_name], alpha=0.8)
        # 股价震荡区间图
        try:
            import numpy as np
            # 计算20日移动平均线
            if n >= 20:
                # 计算移动平均线
                ma20 = np.convolve(closes, np.ones(20)/20, mode='valid')
                # 计算标准差
                std20 = np.array([np.std(closes[i:i+20]) for i in range(n-19)])
                # 计算上轨和下轨
                upper_band = ma20 + 2 * std20
                lower_band = ma20 - 2 * std20
                # 确定开始索引
                start_idx = 19
                # 绘制移动平均线
                ax1.plot(dates[start_idx:], ma20, color='#FFA500', linewidth=1.5, label='20日MA', alpha=0.8)
                # 绘制上轨和下轨
                ax1.plot(dates[start_idx:], upper_band, color='#4682B4', linewidth=1.0, label='上轨', alpha=0.8, linestyle='--')
                ax1.plot(dates[start_idx:], lower_band, color='#4682B4', linewidth=1.0, label='下轨', alpha=0.8, linestyle='--')
                # 填充震荡区间
                ax1.fill_between(dates[start_idx:], lower_band, upper_band, color='#E6E6FA', alpha=0.3, label='震荡区间')
        except Exception as e:
            print(f"绘制震荡区间失败: {e}")
        # 趋势:用 20 日均线近端斜率辅助判断
        uptrend = False
        downtrend = False
        if 'ma20' in ma_values and len(ma_values['ma20']) >= 6:
            m20 = np.asarray(ma_values['ma20'], dtype=float)
            uptrend = bool(m20[-1] > m20[-6])
            downtrend = bool(m20[-1] < m20[-6])
        elif n >= 12:
            uptrend = bool(closes[-1] > closes[-11])
            downtrend = bool(closes[-1] < closes[-11])
        # 波谷 / 波峰(简单枢轴)
        piv_lo = [i for i in range(1, n - 1) if lows[i] <= lows[i - 1] and lows[i] <= lows[i + 1]]
        piv_hi = [i for i in range(1, n - 1) if highs[i] >= highs[i - 1] and highs[i] >= highs[i + 1]]
        x_end = float(n - 1)
        # 绘制阶梯类型的长方形框架(平行的阻力线和支撑线)
        if show_support_resistance:
            try:
                # 处理支撑线(波谷)
                if len(piv_lo) >= 2:
                    # 按时间顺序排序波谷
                    sorted_piv_lo = sorted(piv_lo)
                    # 根据波谷数量确定线宽,数量越多级别越高
                    line_width = 1.0
                    if len(sorted_piv_lo) >= 3:
                        line_width = 2.0  # 3个及以上波谷,级别更高,线更粗
                    # 绘制水平支撑线
                    for i, piv in enumerate(sorted_piv_lo):
                        support_level = lows[piv]
                        # 绘制支撑线
                        ax1.axhline(y=support_level, color='#006400', linewidth=line_width, linestyle='--', alpha=0.7)
                        # 标注支撑线
                        ax1.text(piv, support_level - (max(closes) - min(closes)) * 0.02, f'支撑 {support_level:.2f}',
                                 fontsize=8, color='#006400', ha='center')
                        # 如果不是最后一个波谷,绘制与下一个波谷之间的垂直线
                        if i < len(sorted_piv_lo) - 1:
                            next_piv = sorted_piv_lo[i + 1]
                            ax1.plot([piv, piv], [support_level, lows[next_piv]], color='#006400', linewidth=line_width, linestyle='--', alpha=0.7)
                # 处理阻力线(波峰)
                if len(piv_hi) >= 2:
                    # 按时间顺序排序波峰
                    sorted_piv_hi = sorted(piv_hi)
                    # 根据波峰数量确定线宽,数量越多级别越高
                    line_width = 1.0
                    if len(sorted_piv_hi) >= 3:
                        line_width = 2.0  # 3个及以上波峰,级别更高,线更粗
                    # 绘制水平阻力线
                    for i, piv in enumerate(sorted_piv_hi):
                        resistance_level = highs[piv]
                        # 绘制阻力线
                        ax1.axhline(y=resistance_level, color='#8B0000', linewidth=line_width, linestyle='--', alpha=0.7)
                        # 标注阻力线
                        ax1.text(piv, resistance_level + (max(closes) - min(closes)) * 0.02, f'阻力 {resistance_level:.2f}',
                                 fontsize=8, color='#8B0000', ha='center')
                        # 如果不是最后一个波峰,绘制与下一个波峰之间的垂直线
                        if i < len(sorted_piv_hi) - 1:
                            next_piv = sorted_piv_hi[i + 1]
                            ax1.plot([piv, piv], [resistance_level, highs[next_piv]], color='#8B0000', linewidth=1.0, linestyle='--', alpha=0.7)
                # 绘制长方形框架
                if len(piv_lo) >= 2 and len(piv_hi) >= 2:
                    # 获取最近的波谷和波峰
                    recent_piv_lo = sorted(piv_lo)[-2:]
                    recent_piv_hi = sorted(piv_hi)[-2:]
                    # 绘制长方形框架
                    if len(recent_piv_lo) == 2 and len(recent_piv_hi) == 2:
                        # 确定长方形的四个顶点
                        x1 = min(recent_piv_lo[0], recent_piv_hi[0])
                        x2 = max(recent_piv_lo[1], recent_piv_hi[1])
                        y1 = min(lows[recent_piv_lo[0]], lows[recent_piv_lo[1]])
                        y2 = max(highs[recent_piv_hi[0]], highs[recent_piv_hi[1]])
                        # 绘制长方形
                        ax1.plot([x1, x2, x2, x1, x1], [y1, y1, y2, y2, y1], color='#9370DB', linewidth=1.5, linestyle='--', alpha=0.8, label='矩形框架')
            except Exception as e:
                print(f"绘制阶梯框架失败: {e}")
            # 趋势:用 20 日均线近端斜率辅助判断
            uptrend = False
            downtrend = False
            if 'ma20' in ma_values and len(ma_values['ma20']) >= 6:
                m20 = np.asarray(ma_values['ma20'], dtype=float)
                uptrend = bool(m20[-1] > m20[-6])
                downtrend = bool(m20[-1] < m20[-6])
            elif n >= 12:
                uptrend = bool(closes[-1] > closes[-11])
                downtrend = bool(closes[-1] < closes[-11])
            # 原有的支撑/压力线逻辑
            if uptrend and not downtrend and len(piv_lo) >= 2:
                cand = piv_lo[-3:] if len(piv_lo) >= 3 else piv_lo[-2:]
                ok = None
                if len(cand) >= 3 and lows[cand[-1]] > lows[cand[-2]] > lows[cand[-3]]:
                    ok = (cand[-3], cand[-1])
                elif len(cand) >= 2 and lows[cand[-1]] > lows[cand[-2]]:
                    ok = (cand[-2], cand[-1])
                if ok:
                    i0, i1 = ok
                    x0, y0, x1, y1 = float(i0), float(lows[i0]), float(i1), float(lows[i1])
                    if x1 != x0:
                        m = (y1 - y0) / (x1 - x0)
                        y_end = y0 + m * (x_end - x0)
                        ax1.plot([x0, x_end], [y0, y_end], color='#006400', linewidth=2.0, linestyle='--',
                                label='支撑线(低点连线)', alpha=0.95, zorder=6)
            elif downtrend and not uptrend and len(piv_hi) >= 2:
                cand = piv_hi[-3:] if len(piv_hi) >= 3 else piv_hi[-2:]
                ok = None
                if len(cand) >= 3 and highs[cand[-1]] < highs[cand[-2]] < highs[cand[-3]]:
                    ok = (cand[-3], cand[-1])
                elif len(cand) >= 2 and highs[cand[-1]] < highs[cand[-2]]:
                    ok = (cand[-2], cand[-1])
                if ok:
                    i0, i1 = ok
                    x0, y0, x1, y1 = float(i0), float(highs[i0]), float(i1), float(highs[i1])
                    if x1 != x0:
                        m = (y1 - y0) / (x1 - x0)
                        y_end = y0 + m * (x_end - x0)
                        ax1.plot([x0, x_end], [y0, y_end], color='#8B0000', linewidth=2.0, linestyle='--',
                                label='压力线(高点连线)', alpha=0.95, zorder=6)
        # 🔔 完整 4 类买卖点 (自动计算 + 回测胜率)
        if show_bs_signals:
            try:
                import numpy as _np
                if n >= 30:
                    if "成交量" in data.columns:
                        _vols = data["成交量"].values.astype(float)
                    else:
                        _vols = np.zeros(n, dtype=float)
                    sigs = calc_trade_signals(closes, opens, highs, lows, _vols)
                    _mp_cls = [
                        ("buy", "*", "#2E7D32", "★买入(MA金/MACD金/布林/锤子线)"),
                        ("add", "^", "#F57C00", "▲加仓(MACD强金/放量突破)"),
                        ("sell", "v", "#C62828", "▼卖出(MA死/MACD死/KDJ高位)"),
                        ("reduce", "D", "#6A1B9A", "▽减仓(MACD弱死/放量破位)"),
                    ]
                    for _key, _mk, _col, _lbl in _mp_cls:
                        _pts = sigs.get(_key, [])
                        if not _pts: continue
                        _xs = [p[0] for p in _pts]; _ys = [p[1] for p in _pts]
                        ax1.scatter(_xs, _ys, marker=_mk, s=110, color=_col,
                                    zorder=15, edgecolors="white", linewidths=0.8, label=_lbl)
                        for _pt in _pts:
                            _idx_p, _y_p, _lbl_p, _col_p, _sym_p = _pt
                            _off = -12 if _sym_p in ("★","▲") else 12
                            _va = "top" if _sym_p in ("★","▲") else "bottom"
                            ax1.annotate(_lbl_p, xy=(_idx_p, _y_p),
                                         xytext=(0,_off), textcoords="offset points",
                                         fontsize=5.5, color=_col_p, ha="center", va=_va,
                                         fontweight="bold", zorder=16)
                    # 图例 (合并)
                    handles, labels = ax1.get_legend_handles_labels()
                    _bs_legend = ax1.legend(handles[-4:], labels[-4:], loc="lower right", fontsize=7)
                    ax1.add_artist(_bs_legend)
                    # 回测胜率 (写入 ax1 标题下方 text) — 带止损止盈 + 3 时间窗
                    _bt_txt_parts = []
                    for _k, _lbl in [("buy","买入"),("add","加仓"),("sell","卖出"),("reduce","减仓")]:
                        _bt = backtest_signal(_k, sigs.get(f"{_k}_all",[]), closes,
                                              highs=highs, lows=lows)
                        if _bt:
                            _wr5 = _bt["wr_by_window"].get(5, 0)
                            _wr10 = _bt["wr_by_window"].get(10, 0)
                            _wr20 = _bt["wr_by_window"].get(20, 0)
                            _bt_txt_parts.append(
                                f"{_lbl}: 止盈10%止损5% 胜率{_bt['win_rate']:.0f}% 盈亏比{_bt['plr']:.2f} "
                                f"| 5日{_wr5:.0f}% 10日{_wr10:.0f}% 20日{_wr20:.0f}%")
                    if _bt_txt_parts:
                        ax1.text(0.5, 1.01, "  |  ".join(_bt_txt_parts),
                                 transform=ax1.transAxes, fontsize=7.5, color="#333",
                                 ha="center", va="bottom", style="italic")
            except Exception as _e:
                print(f"[买卖点] 绘制失败: {_e}")
        _hint = " 双击图表可放大" if show_zoom_hint else ""
        ax1.set_title(f"{stock_name} - 日K线图(Tushare){_hint}", fontsize=12, fontweight='bold')
        ax1.set_ylabel("价格", fontsize=10)
        ax1.legend(loc='upper left', fontsize=8)
        ax1.grid(True, alpha=0.3)
        ax1.set_xlabel("日期", fontsize=10)
        def _fmt_date(s):
            if not s or len(s) != 8:
                return str(s)
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        step = max(1, len(trade_dates) // 12)
        ax1.set_xticks(dates[::step])
        ax1.set_xticklabels([_fmt_date(trade_dates[i]) if i < len(trade_dates) else str(i) for i in dates[::step]], rotation=45, ha='right')
        if hide_x_labels:
            ax1.tick_params(axis="x", labelbottom=False)
            ax1.set_xlabel("")

    def _build_daily_kline_figure(self, kline_data, stock_name, figsize=(12, 6), show_zoom_hint=True, show_support_resistance=False):
        """单图日K线 Figure(嵌入持仓详情等)。"""
        from matplotlib.figure import Figure
        fig = Figure(figsize=figsize, dpi=100)
        # 根据情绪周期设置背景颜色
        emotion_cycle = getattr(self, 'emotion_cycle_var', None)
        if emotion_cycle:
            cycle = emotion_cycle.get()
            if cycle == "上行":
                fig.patch.set_facecolor('#E8F5E9')
                fig.patch.set_alpha(0.6)
            elif cycle == "震荡":
                fig.patch.set_facecolor('#FFF9C4')
                fig.patch.set_alpha(0.6)
            elif cycle == "下行":
                fig.patch.set_facecolor('#FFEBEE')
                fig.patch.set_alpha(0.6)
        ax1 = fig.add_subplot(111)
        # 设置axes背景颜色
        if emotion_cycle:
            cycle = emotion_cycle.get()
            if cycle == "上行":
                ax1.set_facecolor('#E8F5E9')
                ax1.patch.set_alpha(0.4)
            elif cycle == "震荡":
                ax1.set_facecolor('#FFF9C4')
                ax1.patch.set_alpha(0.4)
            elif cycle == "下行":
                ax1.set_facecolor('#FFEBEE')
                ax1.patch.set_alpha(0.4)
        self._apply_daily_kline_ax(ax1, kline_data, stock_name, show_zoom_hint, hide_x_labels=False, show_support_resistance=show_support_resistance)
        fig.tight_layout()
        return fig

    def _build_daily_kline_zoom_figure(self, kline_data, stock_name, indicator_keys):
        """放大窗口:主图 K 线 + 2~4 个副图指标(VOL/MACD/WR2/KDJ/BOLL)。"""
        from matplotlib import gridspec
        from matplotlib.figure import Figure
        allowed = {"VOL", "MACD", "WR2", "KDJ", "BOLL"}
        keys = [k for k in (indicator_keys or []) if k in allowed]
        if len(keys) < 2 or len(keys) > 4:
            raise ValueError("副图指标须选 2~4 个")
        ni = len(keys)
        data = kline_data["data"]
        n = len(data)
        dates = list(range(n))
        opens = data["开盘"].values
        closes = data["收盘"].values
        highs = data["最高"].values
        lows = data["最低"].values
        if "成交量" in data.columns:
            vol = data["成交量"].values.astype(float)
        else:
            vol = np.zeros(n, dtype=float)
        fig_h = 7.0 + 2.15 * ni
        fig = Figure(figsize=(14, fig_h), dpi=100)
        # 根据情绪周期设置背景颜色
        emotion_cycle = getattr(self, 'emotion_cycle_var', None)
        if emotion_cycle:
            cycle = emotion_cycle.get()
            if cycle == "上行":
                fig.patch.set_facecolor('#E8F5E9')
                fig.patch.set_alpha(0.6)
            elif cycle == "震荡":
                fig.patch.set_facecolor('#FFF9C4')
                fig.patch.set_alpha(0.6)
            elif cycle == "下行":
                fig.patch.set_facecolor('#FFEBEE')
                fig.patch.set_alpha(0.6)
        ratios = [3.2] + [1.0] * ni
        gs = gridspec.GridSpec(1 + ni, 1, figure=fig, height_ratios=ratios, hspace=0.14)
        ax_main = fig.add_subplot(gs[0, 0])
        # 设置主图背景颜色
        if emotion_cycle:
            cycle = emotion_cycle.get()
            if cycle == "上行":
                ax_main.set_facecolor('#E8F5E9')
                ax_main.patch.set_alpha(0.4)
            elif cycle == "震荡":
                ax_main.set_facecolor('#FFF9C4')
                ax_main.patch.set_alpha(0.4)
            elif cycle == "下行":
                ax_main.set_facecolor('#FFEBEE')
                ax_main.patch.set_alpha(0.4)
        self._apply_daily_kline_ax(ax_main, kline_data, stock_name, show_zoom_hint=False, hide_x_labels=True, show_support_resistance=True)
        for row, key in enumerate(keys, start=1):
            ax_sub = fig.add_subplot(gs[row, 0], sharex=ax_main)
            # 设置副图背景颜色
            if emotion_cycle:
                cycle = emotion_cycle.get()
                if cycle == "上行":
                    ax_sub.set_facecolor('#E8F5E9')
                    ax_sub.patch.set_alpha(0.3)
                elif cycle == "震荡":
                    ax_sub.set_facecolor('#FFF9C4')
                    ax_sub.patch.set_alpha(0.3)
                elif cycle == "下行":
                    ax_sub.set_facecolor('#FFEBEE')
                    ax_sub.patch.set_alpha(0.3)
            self._plot_kline_zoom_subpanel(ax_sub, key, dates, opens, closes, highs, lows, vol)
            if row < ni:
                ax_sub.tick_params(axis="x", labelbottom=False)
        fig.tight_layout()
        return fig

    def _show_daily_kline_zoom(self, kline_data, stock_name):
        """双击日K线:最大化窗口 + 可选 2~4 个副图指标。"""
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            win = self._safe_toplevel(self.root)
            win.title(f"{stock_name} - 日K线(放大)")
            try:
                win.state("zoomed")
            except Exception:
                try:
                    win.attributes("-zoomed", True)
                except Exception:
                    win.geometry("1200x900")
            top = ttk.Frame(win, padding=4)
            top.pack(fill=tk.X)
            # 添加只显示主图的选项
            main_only_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(top, text="只显示主图", variable=main_only_var).pack(side=tk.LEFT, padx=(0, 10))
            # 添加显示支撑/压力线的选项
            show_support_resistance_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(top, text="显示支撑/压力线", variable=show_support_resistance_var).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(top, text="副图指标(选 2~4 项后点「应用」):", font=("Microsoft YaHei", 10)).pack(
                side=tk.LEFT, padx=(0, 6)
            )
            opt_specs = [
                ("VOL", "VOL"),
                ("MACD", "MACD"),
                ("WR2", "WR(2)"),
                ("KDJ", "KDJ"),
                ("BOLL", "BOLL"),
            ]
            ivars = {}
            for code, _lbl in opt_specs:
                ivars[code] = tk.BooleanVar(value=code in ("VOL", "MACD", "KDJ"))
            for code, lbl in opt_specs:
                ttk.Checkbutton(top, text=lbl, variable=ivars[code]).pack(side=tk.LEFT, padx=3)
            # 🛒 买卖点 + 💡胜率提示
            show_bs_var = tk.BooleanVar(value=True)
            show_bt_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(top, text="🛒买卖点", variable=show_bs_var).pack(side=tk.LEFT, padx=(10,3))
            ttk.Checkbutton(top, text="💡胜率提示", variable=show_bt_var).pack(side=tk.LEFT, padx=3)
            chart_inner = None
            status_var = tk.StringVar(value="")
            # hover tooltip 浮动窗口
            hover_tt = None  # Toplevel ref
            hover_bs_cache = {}  # {idx: (sig_type, label, color)} 缓存
            hover_bt_cache = {}  # {sig_type: backtest_result} 缓存

            def _collect_keys():
                return [c for c, _ in opt_specs if ivars[c].get()]

            def redraw():
                nonlocal hover_bs_cache, hover_bt_cache
                # 预计算 signals 供 tooltip 用
                try:
                    _data0 = kline_data["data"]
                    _sig0 = calc_trade_signals(
                        _data0["收盘"].values, _data0["开盘"].values,
                        _data0["最高"].values, _data0["最低"].values,
                        _data0["成交量"].values.astype(float) if "成交量" in _data0.columns else np.zeros(len(_data0)))
                    # 建 idx→(type,label,color) 查找表
                    hover_bs_cache = {}
                    for _t, _col, _lbl in [("buy","#2E7D32","★买入"),("add","#F57C00","▲加仓"),
                                           ("sell","#C62828","▼卖出"),("reduce","#6A1B9A","▽减仓")]:
                        for _pt in _sig0.get(f"{_t}_all", []):
                            hover_bs_cache[_pt[0]] = (_t, _pt[2], _col)
                    # 预计算回测 (per-point + aggregate)
                    closes0 = _data0["收盘"].values.astype(float)
                    highs0 = _data0["最高"].values.astype(float) if "最高" in _data0.columns else closes0
                    lows0 = _data0["最低"].values.astype(float) if "最低" in _data0.columns else closes0
                    hover_bt_cache = {}  # type→aggregate dict (用于凯利计算/标题)
                    hover_pp_cache = {}  # idx→单点回测 dict (用于 per-point hover)
                    for _t in ("buy","add","sell","reduce"):
                        _pp, _agg = backtest_build_per_point_cache(
                            _t, _sig0.get(f"{_t}_all",[]), closes0, highs=highs0, lows=lows0)
                        if _agg: hover_bt_cache[_t] = _agg
                        hover_pp_cache.update(_pp)
                except Exception:
                    hover_bs_cache = {}; hover_bt_cache = {}; hover_pp_cache = {}
                if main_only_var.get():
                    # 只显示主图
                    for w in chart_inner.winfo_children():
                        w.destroy()
                    try:
                        original_apply2 = self._apply_daily_kline_ax
                        def temp_apply2(ax1, kline_data, stock_name, show_zoom_hint=True, hide_x_labels=False, show_support_resistance=True):
                            return original_apply2(ax1, kline_data, stock_name, show_zoom_hint, hide_x_labels,
                                                   show_support_resistance=show_support_resistance_var.get(),
                                                   show_bs_signals=show_bs_var.get())
                        self._apply_daily_kline_ax = temp_apply2
                        fig = self._build_daily_kline_figure(kline_data, stock_name, figsize=(14, 9), show_support_resistance=show_support_resistance_var.get())
                        self._apply_daily_kline_ax = original_apply2
                        canvas = FigureCanvasTkAgg(fig, chart_inner)
                        canvas.draw()
                        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                        status_var.set("当前显示:只显示主图 | 买卖点开" if show_bs_var.get() else "当前显示:只显示主图")
                        _bind_hover(canvas, fig)
                        # 🎯 叠加综合评分 hover (不影响原买卖点 hover)
                        try:
                            _df0 = kline_data["data"]
                            _d0 = _df0["日期"].tolist() if "日期" in _df0.columns else []
                            self._install_score_hover(
                                canvas, fig.axes[0],
                                _df0["开盘"].values.astype(float),
                                _df0["最高"].values.astype(float),
                                _df0["最低"].values.astype(float),
                                _df0["收盘"].values.astype(float),
                                _df0["成交量"].values.astype(float) if "成交量" in _df0.columns else None,
                                trade_dates=_d0)
                        except Exception:
                            pass
                    except Exception as ex:
                        messagebox.showerror("错误", f"绘制失败: {ex}", parent=win)
                else:
                    # 显示主图+副图
                    sel = _collect_keys()
                    if len(sel) < 2 or len(sel) > 4:
                        messagebox.showwarning("提示", "请勾选 2~4 个副图指标。", parent=win); return
                    for w in chart_inner.winfo_children():
                        w.destroy()
                    try:
                        original_apply = self._apply_daily_kline_ax
                        def temp_apply(ax1, kline_data, stock_name, show_zoom_hint=True, hide_x_labels=False, show_support_resistance=True):
                            return original_apply(ax1, kline_data, stock_name, show_zoom_hint, hide_x_labels,
                                                  show_support_resistance=show_support_resistance_var.get(),
                                                  show_bs_signals=show_bs_var.get())
                        self._apply_daily_kline_ax = temp_apply
                        fig = self._build_daily_kline_zoom_figure(kline_data, stock_name, sel)
                        self._apply_daily_kline_ax = original_apply
                        canvas = FigureCanvasTkAgg(fig, chart_inner)
                        canvas.draw()
                        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                        status_var.set(f"副图:{' + '.join(sel)} | 买卖点开" if show_bs_var.get() else f"副图:{' + '.join(sel)}")
                        _bind_hover(canvas, fig)
                        # 🎯 叠加综合评分 hover
                        try:
                            _df0 = kline_data["data"]
                            _d0 = _df0["日期"].tolist() if "日期" in _df0.columns else []
                            self._install_score_hover(
                                canvas, fig.axes[0],
                                _df0["开盘"].values.astype(float),
                                _df0["最高"].values.astype(float),
                                _df0["最低"].values.astype(float),
                                _df0["收盘"].values.astype(float),
                                _df0["成交量"].values.astype(float) if "成交量" in _df0.columns else None,
                                trade_dates=_d0)
                        except Exception:
                            pass
                    except Exception as ex:
                        if hasattr(self, '_apply_daily_kline_ax'): self._apply_daily_kline_ax = original_apply
                        messagebox.showerror("错误", f"绘制失败: {ex}", parent=win)

            def _bind_hover(canvas, fig):
                """canvas 绑定 mouse motion → 显示胜率 tooltip + 当日数据"""
                nonlocal hover_tt
                # 把 _data0 提取出来供 tooltip 用
                _kdata = kline_data
                def _on_motion(event):
                    nonlocal hover_tt
                    try:
                        if not show_bt_var.get():
                            if hover_tt: hover_tt.destroy(); hover_tt = None; return
                        if event.inaxes is None or event.xdata is None:
                            if hover_tt: hover_tt.destroy(); hover_tt = None; return
                        idx = int(round(event.xdata))
                        if idx not in hover_bs_cache:
                            if hover_tt: hover_tt.destroy(); hover_tt = None; return
                        sig_type, label, color = hover_bs_cache[idx]
                        bt = hover_bt_cache.get(sig_type)
                        _type_zh = {"buy":"★买入","add":"▲加仓","sell":"▼卖出","reduce":"▽减仓"}.get(sig_type, sig_type)
                        # ========== 📅 当日数据（日期/OHLCV/量比/量） ==========
                        lines = []
                        try:
                            _df = _kdata["data"]
                            if 0 <= idx < len(_df):
                                _row = _df.iloc[idx]
                                _d = str(_row.get("日期", ""))
                                if len(_d) == 8: _d = f"{_d[:4]}-{_d[4:6]}-{_d[6:8]}"
                                _open = float(_row.get("开盘", 0))
                                _hi   = float(_row.get("最高", 0))
                                _lo   = float(_row.get("最低", 0))
                                _cls  = float(_row.get("收盘", 0))
                                _vol  = float(_row.get("成交量", 0))
                                _amt  = float(_row.get("成交额", 0)) if "成交额" in _df.columns else 0
                                # 前收
                                if idx > 0:
                                    _prev_c = float(_df.iloc[idx-1]["收盘"])
                                    _chg = (_cls - _prev_c) / _prev_c * 100 if _prev_c else 0
                                else:
                                    _chg = 0
                                # 量比 (5日均量 / 20日均量)
                                _vols_all = _df["成交量"].values.astype(float) if "成交量" in _df.columns else None
                                if _vols_all is not None and idx >= 20:
                                    _v5 = float(_vols_all[max(0,idx-4):idx+1].mean())
                                    _v20 = float(_vols_all[max(0,idx-19):idx+1].mean())
                                    _vr5 = _vol / _v5 if _v5 > 0 else 0
                                    _vr20 = _vol / _v20 if _v20 > 0 else 0
                                else:
                                    _vr5 = _vr20 = 0
                                # 格式化
                                def _fmt_amt(a):
                                    if a >= 1e8: return f"{a/1e8:.2f}亿"
                                    elif a >= 1e4: return f"{a/1e4:.1f}万"
                                    return f"{a:.0f}"
                                _chg_arrow = "📈" if _chg >= 0 else "📉"
                                _chg_col = "#F44336" if _chg >= 0 else "#4CAF50"
                                lines.append(f"📅 {_d}  {_chg_arrow} 涨跌 {_chg:+.2f}%")
                                lines.append(f"  开 {_open:.2f}  高 {_hi:.2f}  低 {_lo:.2f}  收 {_cls:.2f}")
                                lines.append(f"  量 {_fmt_amt(_vol)}  额 {_fmt_amt(_amt)}  量比(5日) {_vr5:.2f}  量比(20日) {_vr20:.2f}")
                        except Exception:
                            pass
                        lines.append("")
                        lines.append(f"🎯 {_type_zh} — {label}")
                        # ========== 🎯 单点真实结果 (这根 K 线买入后实际发生了什么) ==========
                        pp = hover_pp_cache.get(idx)
                        if pp:
                            _is_long = sig_type in ("buy","add")
                            _arrow = "📈" if pp["ret"] >= 0 else "📉"
                            _reason = pp["exit_reason"]
                            _reason_color = {"止盈":"#2E7D32","止损":"#C62828","超时":"#F57C00"}.get(_reason, "#555")
                            lines.append(f"━━━━ 这根K线 {_type_zh} 真实结果 ━━━━")
                            lines.append(f"  入场价 {pp['entry_p']:.2f} → 出场价 {pp['exit_p']:.2f}  ({pp['hold_days']}天后)")
                            lines.append(f"  {_arrow} 单笔收益: {pp['ret']:+.2f}%   出场方式: {_reason}")
                            # 固定时间窗收益 (真实)
                            _rw = pp.get("rets_by_window", {})
                            _win_parts = []
                            for _w, _lbl in [(1,"1天"),(3,"3天"),(5,"5天"),(10,"10天"),(20,"20天")]:
                                _v = _rw.get(_w)
                                if _v is not None:
                                    _win_parts.append(f"{_lbl}{_v:+.1f}%")
                            if _win_parts:
                                lines.append(f"  固定时间窗收益: {' | '.join(_win_parts)}")
                            lines.append(f"━━━━ 历史同类型 {_type_zh} 汇总 ━━━━")
                        if bt:
                            cnt = bt["count"]; wr = bt["win_rate"]
                            avg_g = bt["avg_profit"]; avg_l = bt["avg_loss"]; plr = bt["plr"]
                            median_ret = bt["median_ret"]; best = bt["best"]; worst = bt["worst"]
                            avg_hold = bt["avg_hold_days"]
                            exit_reasons = bt["exit_reasons"]
                            wr_by_w = bt["wr_by_window"]; ret_by_w = bt["ret_by_window"]
                            lines.append(f"📊 历史信号: {cnt} 次 (止盈10% / 止损5% / 最长{int(avg_hold)+5}天)")
                            lines.append(f"✅ 真实胜率: {wr:.1f}%  (逐bar止损止盈后)")
                            lines.append(f"💰 平均盈利: +{avg_g:.2f}%  💔 平均亏损: -{avg_l:.2f}%")
                            lines.append(f"⚖️ 盈亏比: {plr:.2f}  🧭 单笔中位收益: {median_ret:+.2f}%")
                            lines.append(f"🏆 最佳 {best:+.1f}%  😰 最差 {worst:+.1f}%  ⏱ 平均持仓 {avg_hold:.1f}天")
                            # 出场原因
                            if exit_reasons:
                                _parts = [f"{k}{v}次" for k, v in sorted(exit_reasons.items())]
                                lines.append(f"🚪 出场: {' / '.join(_parts)}")
                            # 多时间窗 (不用固定10天)
                            lines.append("📐 不同时间窗(收盘价): "
                                         f"5日胜率{wr_by_w.get(5,0):.0f}%均收{ret_by_w.get(5,0):+.1f}%  "
                                         f"10日胜率{wr_by_w.get(10,0):.0f}%均收{ret_by_w.get(10,0):+.1f}%  "
                                         f"20日胜率{wr_by_w.get(20,0):.0f}%均收{ret_by_w.get(20,0):+.1f}%")
                            # 🧮 凯利公式 (用真实胜率)
                            try:
                                p = wr / 100.0; q = 1 - p; b = max(plr, 0.01)
                                kelly_f = (b * p - q) / b if b > 0 else 0
                                kelly_f = max(0, min(kelly_f, 1.0))
                                halving = kelly_f / 2
                                if kelly_f >= 0.25:
                                    kelly_level = "⭐⭐⭐⭐⭐ 强下注信号"
                                elif kelly_f >= 0.15:
                                    kelly_level = "⭐⭐⭐⭐ 值得下注"
                                elif kelly_f >= 0.05:
                                    kelly_level = "⭐⭐⭐ 轻仓试单"
                                elif kelly_f > 0:
                                    kelly_level = "⭐⭐ 观察信号"
                                else:
                                    kelly_level = "❌ 不值得下注 (负期望)"
                                lines.append("")
                                lines.append(f"🧮 凯利公式 (Kelly Criterion):")
                                lines.append(f"   f* = (bp - q)/b = ({b:.2f}×{p:.2f} - {q:.2f})/{b:.2f}")
                                lines.append(f"   ✅ 最优仓位: {kelly_f*100:.1f}%")
                                lines.append(f"   🔹 半凯利稳妥: {halving*100:.1f}%")
                                lines.append(f"   🎯 {kelly_level}")
                            except Exception:
                                pass
                        else:
                            lines.append("⚠️ 历史信号不足 3 次")
                        text = "\n".join(lines)
                        if hover_tt is None or not hover_tt.winfo_exists():
                            hover_tt = tk.Toplevel(win)
                            hover_tt.wm_overrideredirect(True)
                            hover_tt.attributes("-topmost", True)
                            hover_tt.configure(bg="#263238")
                            tk.Label(hover_tt, text=text, bg="#263238", fg="#FFFFFF",
                                     font=("", 10, "bold"), padx=10, pady=6, justify=tk.LEFT).pack()
                        else:
                            for w in hover_tt.winfo_children(): w.destroy()
                            tk.Label(hover_tt, text=text, bg="#263238", fg="#FFFFFF",
                                     font=("", 10, "bold"), padx=10, pady=6, justify=tk.LEFT).pack()
                        mx = win.winfo_pointerx(); my = win.winfo_pointery()
                        hover_tt.geometry(f"+{mx+15}+{my+15}")
                    except Exception:
                        if hover_tt: hover_tt.destroy(); hover_tt = None
                canvas.mpl_connect("motion_notify_event", _on_motion)
                def _on_leave(event):
                    nonlocal hover_tt
                    if hover_tt: hover_tt.destroy(); hover_tt = None
                canvas.mpl_connect("axes_leave_event", _on_leave)
            # 首次 redraw
            win.after(100, redraw)
            ttk.Button(top, text="应用", command=redraw).pack(side=tk.LEFT, padx=(10, 4))
            current_stock_data = {'kline_data': kline_data, 'stock_name': stock_name}
            def calculate_kelly():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_kelly_position(data, name)
                    self._show_kelly_result_dialog(result, name, win)
                except Exception as e:
                    messagebox.showerror("错误", f"凯利计算失败: {e}", parent=win)
            ttk.Button(top, text="凯利计算", command=calculate_kelly).pack(side=tk.LEFT, padx=(10, 4))
            def calculate_sharpe():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_sharpe_ratio(data, name)
                    self._show_analysis_result_dialog(result, name, "夏普比率分析", win)
                except Exception as e:
                    messagebox.showerror("错误", f"夏普比率计算失败: {e}", parent=win)
            ttk.Button(top, text="夏普比率", command=calculate_sharpe).pack(side=tk.LEFT, padx=(10, 4))
            def calculate_mean_reversion():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_mean_reversion(data, name)
                    self._show_analysis_result_dialog(result, name, "均值回归分析", win)
                except Exception as e:
                    messagebox.showerror("错误", f"均值回归计算失败: {e}", parent=win)
            ttk.Button(top, text="均值回归", command=calculate_mean_reversion).pack(side=tk.LEFT, padx=(10, 4))
            def predict_buy_points():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_buy_point_prediction(data, name)
                    self._show_buy_point_prediction_dialog(result, name, win)
                except Exception as e:
                    messagebox.showerror("错误", f"买点预测失败: {e}", parent=win)
            ttk.Button(top, text="买点预测", command=predict_buy_points).pack(side=tk.LEFT, padx=(10, 4))
            # 第二行按钮
            top2 = ttk.Frame(win)
            top2.pack(fill=tk.X, pady=(5, 0))
            def calculate_trend_tracking():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_trend_tracking(data, name)
                    self._show_analysis_result_dialog(result, name, "趋势跟踪分析", win)
                except Exception as e:
                    messagebox.showerror("错误", f"趋势跟踪计算失败: {e}", parent=win)
            ttk.Button(top2, text="趋势跟踪", command=calculate_trend_tracking).pack(side=tk.LEFT, padx=(10, 4))
            def calculate_dragon_head():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_dragon_head(data, name)
                    self._show_analysis_result_dialog(result, name, "龙头战法分析", win)
                except Exception as e:
                    messagebox.showerror("错误", f"龙头战法计算失败: {e}", parent=win)
            ttk.Button(top2, text="龙头战法", command=calculate_dragon_head).pack(side=tk.LEFT, padx=(10, 4))
            def calculate_overbought_bounce():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_overbought_bounce(data, name)
                    self._show_analysis_result_dialog(result, name, "超跌反弹分析", win)
                except Exception as e:
                    messagebox.showerror("错误", f"超跌反弹计算失败: {e}", parent=win)
            ttk.Button(top2, text="超跌反弹", command=calculate_overbought_bounce).pack(side=tk.LEFT, padx=(10, 4))
            def calculate_multi_factor():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_multi_factor(data, name)
                    self._show_analysis_result_dialog(result, name, "多因子评分", win)
                except Exception as e:
                    messagebox.showerror("错误", f"多因子评分计算失败: {e}", parent=win)
            ttk.Button(top2, text="多因子评分", command=calculate_multi_factor).pack(side=tk.LEFT, padx=(10, 4))
            def fetch_stock_info():
                try:
                    name = current_stock_data['stock_name']
                    result = self._fetch_stock_info(name)
                    self._show_stock_info_dialog(result, name, win)
                except Exception as e:
                    messagebox.showerror("错误", f"信息获取失败: {e}", parent=win)
            ttk.Button(top2, text="信息获取", command=fetch_stock_info).pack(side=tk.LEFT, padx=(10, 4))
            # 🦅 游资心法全解按钮
            def open_hotmoney_analysis():
                try:
                    self._open_hotmoney_single_dialog(win, current_stock_data)
                except Exception as e:
                    messagebox.showerror("错误", f"游资心法打开失败: {e}", parent=win)
            ttk.Button(top2, text="🦅 游资心法", command=open_hotmoney_analysis).pack(side=tk.LEFT, padx=(10, 4))
            # 添加股票输入下拉框和查询按钮
            stock_frame = ttk.Frame(top2, padding=2)
            stock_frame.pack(side=tk.LEFT, padx=(20, 0))
            ttk.Label(stock_frame, text="股票:", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(0, 5))
            # 股票输入框(支持下拉和手动输入)
            stock_var = tk.StringVar(value="")
            stock_combo = ttk.Combobox(stock_frame, textvariable=stock_var, width=20, font=("TkDefaultFont", 10), state="normal")
            # 加载股票数据到下拉框
            def load_stock_data():
                try:
                    # 获取持仓股(group_idx=1)和龙头股(group_idx=2)中的股票
                    all_holdings = self._get_all_holding_stocks()
                    # 筛选持仓股和龙头股
                    stock_items = []
                    seen_codes = set()
                    for stock_name, stock_code, group_idx, pos_idx in all_holdings:
                        if stock_code not in seen_codes:
                            seen_codes.add(stock_code)
                            if group_idx == 1:
                                stock_items.append(f"{stock_name}({stock_code})[持仓]")
                            elif group_idx == 2:
                                stock_items.append(f"{stock_name}({stock_code})[龙头股]")
                    # 如果没有数据,使用默认热门股票
                    if not stock_items:
                        hot_stocks = get_news_stocks_merged_recent_days(ndays=3)
                        for name, code in hot_stocks[:30]:
                            if code not in seen_codes:
                                stock_items.append(f"{name}({code})[热门]")
                    stock_combo['values'] = stock_items
                except Exception as e:
                    print(f"加载股票数据失败: {e}")
                    # 使用默认热门股票
                    hot_stocks = get_news_stocks_merged_recent_days(ndays=3)
                    stock_items = [f"{name}({code})[热门]" for name, code in hot_stocks[:30]]
                    stock_combo['values'] = stock_items
            # 加载股票数据
            load_stock_data()
            stock_combo.pack(side=tk.LEFT, padx=(0, 5))
            # 标签股下拉框
            tab_stock_frame = ttk.Frame(top, padding=2)
            tab_stock_frame.pack(side=tk.LEFT, padx=(10, 0))
            ttk.Label(tab_stock_frame, text="标签股:", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(0, 5))
            # 标签股输入框
            tab_stock_var = tk.StringVar(value="")
            tab_stock_combo = ttk.Combobox(tab_stock_frame, textvariable=tab_stock_var, width=20, font=("TkDefaultFont", 10), state="normal")
            # 加载标签股数据
            def load_tab_stock_data():
                try:
                    # 获取同花顺标签页(group_idx=6)的股票
                    all_holdings = self._get_all_holding_stocks()
                    # 筛选同花顺标签页的股票
                    tab_stock_items = []
                    seen_codes = set()
                    for stock_name, stock_code, group_idx, pos_idx in all_holdings:
                        if group_idx == 6 and stock_code not in seen_codes:
                            seen_codes.add(stock_code)
                            tab_stock_items.append(f"{stock_name}({stock_code})[同花顺]")
                    # 如果没有数据,使用默认热门股票
                    if not tab_stock_items:
                        hot_stocks = get_news_stocks_merged_recent_days(ndays=3)
                        for name, code in hot_stocks[:30]:
                            if code not in seen_codes:
                                tab_stock_items.append(f"{name}({code})[热门]")
                    tab_stock_combo['values'] = tab_stock_items
                except Exception as e:
                    print(f"加载标签股数据失败: {e}")
                    # 使用默认热门股票
                    hot_stocks = get_news_stocks_merged_recent_days(ndays=3)
                    tab_stock_items = [f"{name}({code})[热门]" for name, code in hot_stocks[:30]]
                    tab_stock_combo['values'] = tab_stock_items
            # 标签股选择事件处理
            def on_tab_stock_select(event):
                tab_stock_input = tab_stock_var.get().strip()
                if tab_stock_input:
                    # 提取股票代码
                    stock_code = None
                    stock_name = None
                    # 从输入中提取股票代码
                    code_match = re.search(r'\d{6}', tab_stock_input)
                    if code_match:
                        stock_code = code_match.group(0)
                    else:
                        # 从输入中提取股票名称
                        name_match = re.search(r'([^()]+)', tab_stock_input)
                        if name_match:
                            stock_name = name_match.group(1).strip()
                        else:
                            stock_name = tab_stock_input
                    try:
                        # 获取股票K线数据
                        if stock_code:
                            kline_data = self._get_daily_kline_data_tushare(stock_code)
                            stock_name = get_stock_name_by_code(stock_code)
                        else:
                            stock_code = get_stock_code_by_name(stock_name)
                            kline_data = self._get_daily_kline_data_tushare(stock_code)
                        if kline_data:
                            # 重新绘制K线图
                            for w in chart_inner.winfo_children():
                                w.destroy()
                            if main_only_var.get():
                                fig = self._build_daily_kline_figure(kline_data, stock_name, figsize=(14, 9), show_support_resistance=show_support_resistance_var.get())
                            else:
                                sel = _collect_keys()
                                # 临时修改_apply_daily_kline_ax的调用,添加show_support_resistance参数
                                original_apply = self._apply_daily_kline_ax
                                def temp_apply(ax1, kline_data, stock_name, show_zoom_hint=True, hide_x_labels=False, show_support_resistance=True):
                                    return original_apply(ax1, kline_data, stock_name, show_zoom_hint, hide_x_labels, show_support_resistance=show_support_resistance_var.get())
                                self._apply_daily_kline_ax = temp_apply
                                fig = self._build_daily_kline_zoom_figure(kline_data, stock_name, sel)
                                # 恢复原始函数
                                self._apply_daily_kline_ax = original_apply
                            canvas = FigureCanvasTkAgg(fig, chart_inner)
                            canvas.draw()
                            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                            # 🎯 叠加综合评分 hover (redraw 分支)
                            try:
                                _df0 = kline_data["data"]
                                _d0 = _df0["日期"].tolist() if "日期" in _df0.columns else []
                                self._install_score_hover(
                                    canvas, fig.axes[0],
                                    _df0["开盘"].values.astype(float),
                                    _df0["最高"].values.astype(float),
                                    _df0["最低"].values.astype(float),
                                    _df0["收盘"].values.astype(float),
                                    _df0["成交量"].values.astype(float) if "成交量" in _df0.columns else None,
                                    trade_dates=_d0)
                            except Exception:
                                pass
                            if main_only_var.get():
                                status_var.set("当前显示:只显示主图")
                            else:
                                status_var.set(f"当前副图:{' + '.join(sel)}")
                            # 更新窗口标题
                            win.title(f"{stock_name} - 日K线(放大)")
                            # 更新当前股票数据,供凯利计算等按钮使用
                            current_stock_data['kline_data'] = kline_data
                            current_stock_data['stock_name'] = stock_name
                        else:
                            messagebox.showwarning("提示", "无法获取股票K线数据", parent=win)
                    except Exception as e:
                        messagebox.showerror("错误", f"获取股票数据失败: {e}", parent=win)
            # 绑定标签股下拉框选择事件
            tab_stock_combo.bind("<<ComboboxSelected>>", on_tab_stock_select)
            # 加载标签股数据
            load_tab_stock_data()
            tab_stock_combo.pack(side=tk.LEFT, padx=(0, 5))
            # 查询按钮
            def query_stock():
                stock_input = stock_var.get().strip()
                tab_stock_input = tab_stock_var.get().strip()
                # 优先使用标签股输入,然后是股票输入
                input_to_use = tab_stock_input if tab_stock_input else stock_input
                if not input_to_use:
                    messagebox.showwarning("提示", "请输入股票名称或代码", parent=win)
                    return
                # 提取股票代码
                stock_code = None
                stock_name = None
                # 从输入中提取股票代码
                code_match = re.search(r'\d{6}', input_to_use)
                if code_match:
                    stock_code = code_match.group(0)
                else:
                    # 从输入中提取股票名称
                    name_match = re.search(r'([^()]+)', input_to_use)
                    if name_match:
                        stock_name = name_match.group(1).strip()
                    else:
                        stock_name = input_to_use
                try:
                    # 获取股票K线数据
                    if stock_code:
                        kline_data = self._get_daily_kline_data_tushare(stock_code)
                        stock_name = get_stock_name_by_code(stock_code)
                    else:
                        stock_code = get_stock_code_by_name(stock_name)
                        kline_data = self._get_daily_kline_data_tushare(stock_code)
                    if not kline_data:
                        messagebox.showwarning("提示", "无法获取股票K线数据", parent=win)
                        return
                    # 重新绘制K线图
                    for w in chart_inner.winfo_children():
                        w.destroy()
                    if main_only_var.get():
                        fig = self._build_daily_kline_figure(kline_data, stock_name, figsize=(14, 9), show_support_resistance=show_support_resistance_var.get())
                    else:
                        sel = _collect_keys()
                        # 临时修改_apply_daily_kline_ax的调用,添加show_support_resistance参数
                        original_apply = self._apply_daily_kline_ax
                        def temp_apply(ax1, kline_data, stock_name, show_zoom_hint=True, hide_x_labels=False, show_support_resistance=True):
                            return original_apply(ax1, kline_data, stock_name, show_zoom_hint, hide_x_labels, show_support_resistance=show_support_resistance_var.get())
                        self._apply_daily_kline_ax = temp_apply
                        fig = self._build_daily_kline_zoom_figure(kline_data, stock_name, sel)
                        # 恢复原始函数
                        self._apply_daily_kline_ax = original_apply
                    canvas = FigureCanvasTkAgg(fig, chart_inner)
                    canvas.draw()
                    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                    # 🎯 叠加综合评分 hover (query 分支)
                    try:
                        _df0 = kline_data["data"]
                        _d0 = _df0["日期"].tolist() if "日期" in _df0.columns else []
                        self._install_score_hover(
                            canvas, fig.axes[0],
                            _df0["开盘"].values.astype(float),
                            _df0["最高"].values.astype(float),
                            _df0["最低"].values.astype(float),
                            _df0["收盘"].values.astype(float),
                            _df0["成交量"].values.astype(float) if "成交量" in _df0.columns else None,
                            trade_dates=_d0)
                    except Exception:
                        pass
                    if main_only_var.get():
                        status_var.set("当前显示:只显示主图")
                    else:
                        status_var.set(f"当前副图:{' + '.join(sel)}")
                    # 更新窗口标题
                    win.title(f"{stock_name} - 日K线(放大)")
                    # 更新当前股票数据,供凯利计算等按钮使用
                    current_stock_data['kline_data'] = kline_data
                    current_stock_data['stock_name'] = stock_name
                except Exception as e:
                    messagebox.showerror("错误", f"获取股票数据失败: {e}", parent=win)
            ttk.Button(stock_frame, text="查询", command=query_stock).pack(side=tk.LEFT, padx=(0, 10))
            # 图表框架 - 在所有按钮之后创建
            chart_fr = ttk.Frame(win, padding=(4, 0, 4, 4))
            chart_fr.pack(fill=tk.BOTH, expand=True)
            chart_inner = ttk.Frame(chart_fr)
            chart_inner.pack(fill=tk.BOTH, expand=True)
            # 添加快速切换按钮
            quick_frame = ttk.Frame(top, padding=2)
            quick_frame.pack(side=tk.LEFT, padx=(10, 0))
            def switch_to_tab_stock(tab_name):
                try:
                    import re
                    import sqlite3
                    from collections import Counter
                    global STOCK_CODES_DICT
                    db_path = os.path.join(D_DB_DIR, "stock_analysis.db")
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    # 确保股票数据已加载
                    load_stock_names()
                    # 从该标签页获取股票
                    cursor.execute("SELECT content FROM news_info WHERE tab_name = ? LIMIT 1", (tab_name,))
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        content = row[0]
                        # 提取股票代码
                        codes = re.findall(r"\d{6}", content)
                        # 检查代码是否在STOCK_CODES_DICT中
                        valid = [c for c in codes if c in STOCK_CODES_DICT]
                        # 按出现频次排序
                        counter = Counter(valid)
                        most_common = counter.most_common(1)
                        if most_common:
                            stock_code = most_common[0][0]
                            stock_name = STOCK_CODES_DICT[stock_code]
                            # 更新标签股下拉框
                            tab_stock_var.set(f"{stock_name} ({stock_code})")
                            # 执行查询
                            query_stock()
                except Exception as e:
                    print(f"切换到标签股失败: {e}")
            ttk.Button(quick_frame, text="咨询股", command=lambda: switch_to_tab_stock("咨询")).pack(side=tk.LEFT, padx=3)
            ttk.Button(quick_frame, text="同花顺", command=lambda: switch_to_tab_stock("同花顺")).pack(side=tk.LEFT, padx=3)
            ttk.Button(quick_frame, text="Main", command=lambda: switch_to_tab_stock("Main")).pack(side=tk.LEFT, padx=3)
            ttk.Button(quick_frame, text="龙头股", command=lambda: switch_to_tab_stock("龙头股")).pack(side=tk.LEFT, padx=3)
            ttk.Button(quick_frame, text="15Min", command=lambda: switch_to_tab_stock("15Min")).pack(side=tk.LEFT, padx=3)
            lbl_st = ttk.Label(top, textvariable=status_var, font=("Microsoft YaHei", 9), foreground="gray")
            lbl_st.pack(side=tk.LEFT, padx=(8, 0))
            redraw()
            # 延迟自动打开凯利计算对话框,避免阻塞主界面
            # 注意:此功能暂时禁用,待主界面稳定后再启用
            # def delayed_kelly():
            #     try:
            #         result = self._calculate_kelly_position(kline_data, stock_name)
            #         self._show_kelly_result_dialog(result, stock_name, win)
            #     except Exception as e:
            #         pass
            # win.after(500, delayed_kelly)
        except Exception as e:
            messagebox.showerror("错误", f"打开放大K线失败: {e}", parent=self.root)

    def _draw_daily_kline_chart(self, parent, kline_data, stock_name, embed_zoom_handler=True):
        """绘制日K线图(Tushare),含均线与支撑/压力线;双击可弹出最大化查看。"""
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            fig = self._build_daily_kline_figure(kline_data, stock_name, figsize=(12, 6))
            canvas = FigureCanvasTkAgg(fig, parent)
            canvas.draw()
            w = canvas.get_tk_widget()
            w.pack(fill=tk.BOTH, expand=True)
            # 🎯 叠加综合评分 hover (嵌入版日K)
            try:
                _df0 = kline_data["data"]
                _d0 = _df0["日期"].tolist() if "日期" in _df0.columns else []
                self._install_score_hover(
                    canvas, fig.axes[0],
                    _df0["开盘"].values.astype(float),
                    _df0["最高"].values.astype(float),
                    _df0["最低"].values.astype(float),
                    _df0["收盘"].values.astype(float),
                    _df0["成交量"].values.astype(float) if "成交量" in _df0.columns else None,
                    trade_dates=_d0)
            except Exception:
                pass
            if embed_zoom_handler:
                w.bind("<Double-Button-1>", lambda e: self._show_daily_kline_zoom(kline_data, stock_name))
        except Exception as e:
            print(f"绘制日K线图失败: {e}")
            import traceback
            traceback.print_exc()
            error_label = ttk.Label(parent, text=f"绘制日K线图失败: {e}", font=("TkDefaultFont", 12), foreground="red")
            error_label.pack(expand=True)

    def _draw_15min_kline_chart(self, parent, kline_data, stock_name):
        """绘制15分钟K线图,包含1日、3日、5日、10日、20日均线"""
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            # 创建图表
            fig = Figure(figsize=(12, 6), dpi=100)
            ax = fig.add_subplot(111)
            data = kline_data['data']
            ma_values = kline_data['ma_values']
            # 准备K线数据
            dates = list(range(len(data)))  # 使用索引作为x轴
            if '开盘' in data.columns:
                opens = data['开盘'].values
                closes = data['收盘'].values
                highs = data['最高'].values
                lows = data['最低'].values
            else:
                # 如果列名不同,尝试使用位置索引
                opens = data.iloc[:, 1].values if len(data.columns) > 1 else data.iloc[:, 0].values
                closes = data.iloc[:, 2].values if len(data.columns) > 2 else data.iloc[:, 0].values
                highs = data.iloc[:, 3].values if len(data.columns) > 3 else data.iloc[:, 0].values
                lows = data.iloc[:, 4].values if len(data.columns) > 4 else data.iloc[:, 0].values
            # 绘制K线(使用蜡烛图样式)
            for i in range(len(dates)):
                color = 'red' if closes[i] >= opens[i] else 'green'
                # 绘制实体(开盘到收盘)
                body_bottom = min(opens[i], closes[i])
                body_top = max(opens[i], closes[i])
                ax.bar(i, body_top - body_bottom, bottom=body_bottom, color=color, alpha=0.8, width=0.6)
                # 绘制上下影线
                ax.plot([i, i], [lows[i], body_bottom], color=color, linewidth=1)
                ax.plot([i, i], [body_top, highs[i]], color=color, linewidth=1)
            # 绘制收盘价折线(辅助线)
            ax.plot(dates, closes, color='black', linewidth=0.5, label='收盘价', alpha=0.5, linestyle='--')
            # 绘制均线(不同颜色)
            ma_colors = {
                'ma1': '#FF0000',   # 红色
                'ma3': '#FFA500',   # 橙色
                'ma5': '#00FF00',   # 绿色
                'ma10': '#0000FF',  # 蓝色
                'ma20': '#FF00FF'   # 紫色
            }
            ma_labels = {
                'ma1': '1日均线',
                'ma3': '3日均线',
                'ma5': '5日均线',
                'ma10': '10日均线',
                'ma20': '20日均线'
            }
            period_map = {
                'ma1': 16,
                'ma3': 48,
                'ma5': 80,
                'ma10': 160,
                'ma20': 320
            }
            for ma_name in ['ma1', 'ma3', 'ma5', 'ma10', 'ma20']:
                if ma_name in ma_values and len(ma_values[ma_name]) > 0:
                    ma_data = ma_values[ma_name]
                    # 对齐日期(均线数据从period-1开始)
                    period = period_map[ma_name]
                    start_idx = min(period-1, len(dates)-1)
                    # 创建对应的x轴索引
                    ma_indices = list(range(start_idx, start_idx + len(ma_data)))
                    # 确保数据长度一致
                    min_len = min(len(ma_indices), len(ma_data))
                    if min_len > 0:
                        ax.plot(ma_indices[:min_len], ma_data[:min_len], color=ma_colors[ma_name],
                               linewidth=1.5, label=ma_labels[ma_name], alpha=0.8)
            ax.set_title(f"{stock_name} - 15分钟K线图(10日周期)", fontsize=12, fontweight='bold')
            ax.set_xlabel("K线序号", fontsize=10)
            ax.set_ylabel("价格", fontsize=10)
            ax.legend(loc='upper left', fontsize=8)
            ax.grid(True, alpha=0.3)
            # 设置x轴刻度(显示部分时间点)
            if len(dates) > 0:
                step = max(1, len(dates) // 10)  # 显示约10个刻度
                ax.set_xticks(dates[::step])
                ax.set_xticklabels([f"K{i+1}" for i in dates[::step]], rotation=45, ha='right')
            # 将图表嵌入到tkinter
            canvas = FigureCanvasTkAgg(fig, parent)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            # 🎯 叠加综合评分 hover (15min K 线, 无成交量数据则传 None)
            try:
                _vols15 = data['成交量'].values.astype(float) if '成交量' in data.columns else None
                self._install_score_hover(
                    canvas, ax,
                    opens.astype(float), highs.astype(float),
                    lows.astype(float), closes.astype(float),
                    _vols15, trade_dates=[str(d) for d in dates])
            except Exception:
                pass
        except Exception as e:
            print(f"绘制K线图失败: {e}")
            import traceback
            traceback.print_exc()
            error_label = ttk.Label(parent,
                                   text=f"绘制K线图失败: {e}",
                                   font=("TkDefaultFont", 12),
                                   foreground="red")
            error_label.pack(expand=True)

    def _show_stock_detail_direct(self, stock_name, stock_code, group_index=1):
        """直接显示股票详情(不依赖持仓列表)"""
        # 创建临时的持仓股列表,只包含这一个股票
        temp_holding_stocks = [(stock_name, stock_code)]
        temp_index = 0
        # 临时保存原始的_get_holding_group_data方法
        original_get_holding_group_data = self._get_holding_group_data
        # 创建一个临时的_get_holding_group_data方法
        def temp_get_holding_group_data(g_idx):
            # 返回临时数据
            return temp_holding_stocks, [], {}, {}
        # 临时替换方法
        self._get_holding_group_data = temp_get_holding_group_data
        try:
            # 调用原有的显示函数
            self._show_holding_detail(temp_index, group_index)
        finally:
            # 恢复原始方法
            self._get_holding_group_data = original_get_holding_group_data

    # ═══════════════════════════════════════════════════════════════
    # 通用: 复合指标综合评分 + 颜色渐变 + hover tooltip 安装
    # 任何 K 线 matplotlib 弹窗都能装这个
    # ═══════════════════════════════════════════════════════════════

    def _score_to_color(self, score):
        """0-100 → A股渐变: 低=绿 → 中=灰 → 高=红。返回 (浅色背景, 边框, 文字色, 原始色)."""
        score = max(0, min(100, score))
        if score <= 50:
            t = score / 50.0
            r = int(0x2e + (0x75 - 0x2e) * t)
            g = int(0x7d + (0x75 - 0x7d) * t)
            b = int(0x32 + (0x75 - 0x32) * t)
            edge = '#558B2F'; text_c = '#1B5E20'
        else:
            t = (score - 50) / 50.0
            r = int(0x75 + (0xc6 - 0x75) * t)
            g = int(0x75 + (0x28 - 0x75) * t)
            b = int(0x75 + (0x28 - 0x75) * t)
            edge = '#C62828'; text_c = '#B71C1C'
        face = f'#{r:02x}{g:02x}{b:02x}'
        face_light = f'#{(r+255)//2:02x}{(g+255)//2:02x}{(b+255)//2:02x}'
        return face_light, edge, text_c, face

    def _generic_indicator_scores(self, idx, closes, highs=None, lows=None,
                                   opens=None, vol=None):
        """通用评分: 只用基础 OHLCV (任何 K 线数据都有)。
        返回 (scores_list, total_0_100)。"""
        scores = []
        close = closes[idx]

        # 1) VW-MACD (总是算, 因为 VW-MACD 函数稳定)
        if vol is not None and len(closes) >= 26 + 9:
            try:
                vw = self._calc_vwmacd(closes, vol)
                dif_v = vw['dif'][idx]; dea_v = vw['dea'][idx]
                vr = vw['vol_ratio'][idx]
                if not (np.isnan(dif_v) or np.isnan(dea_v)):
                    vwmacd_score = 60 if dif_v > dea_v else -60
                    if vr > 1.3: vwmacd_score = int(vwmacd_score * 1.2)
                    elif vr < 0.7: vwmacd_score = int(vwmacd_score * 0.6)
                    desc = f"DIF{'>' if dif_v > dea_v else '<'}DEA"
                    if vr > 1.3: desc += "·放量"
                    elif vr < 0.7: desc += "·缩量"
                    scores.append(("VW-MACD", vwmacd_score, 1.0, desc))
            except Exception:
                pass

        # 2) 20 日均线方向 (最简单的趋势分)
        if len(closes) >= 20:
            ma20 = np.mean(closes[max(0, idx - 19):idx + 1])
            # 价在 MA20 上 + 20 日前也在 → 趋势向上
            if idx >= 20:
                ma20_prev = np.mean(closes[max(0, idx - 39):idx - 19])
                ma20_slope = ma20 - ma20_prev
            else:
                ma20_slope = 0
            pos_rel = (close - ma20) / close * 100  # 偏离 %
            # 在 MA20 上 + MA20 向上 → 多头 +60
            ma_score = 0
            if close > ma20: ma_score += 30
            if ma20_slope > 0: ma_score += 30
            elif ma20_slope < 0 and close < ma20: ma_score = -40
            if ma_score == 0 and close < ma20: ma_score = -20
            ma_desc = f"MA20={ma20:.2f} {'↑' if ma20_slope > 0 else ('↓' if ma20_slope < 0 else '—')}"
            scores.append(("MA20趋势", ma_score, 0.8, ma_desc))

        # 3) 量价配合 (今日 vs 前 5 日均量, 收盘 vs 开盘)
        if vol is not None and opens is not None and idx >= 5:
            avg_vol5 = np.mean(vol[max(0, idx - 4):idx + 1])
            vr_today = vol[idx] / avg_vol5 if avg_vol5 > 0 else 1
            pct_today = (close - opens[idx]) / opens[idx] * 100 if opens[idx] != 0 else 0
            vol_price_score = 0
            if pct_today > 0 and vr_today > 1.2:
                vol_price_score = 50  # 放量上涨
                vp_desc = "放量上涨"
            elif pct_today < 0 and vr_today > 1.2:
                vol_price_score = -50  # 放量下跌
                vp_desc = "放量下跌"
            elif pct_today > 0 and vr_today < 0.7:
                vol_price_score = 15  # 缩量上涨 (弱)
                vp_desc = "缩量上涨"
            elif pct_today < 0 and vr_today < 0.7:
                vol_price_score = -15
                vp_desc = "缩量下跌"
            else:
                vp_desc = "量平"
            scores.append(("量价配合", vol_price_score, 0.5,
                           f"{vp_desc}(量比={vr_today:.2f})"))

        # 4) 简单支撑压力 (用近 20 根高低)
        if highs is not None and lows is not None and idx >= 20:
            recent_h = np.max(highs[max(0, idx - 19):idx + 1])
            recent_l = np.min(lows[max(0, idx - 19):idx + 1])
            range_h = recent_h - recent_l
            pos_in_range = (close - recent_l) / range_h if range_h > 0 else 0.5
            # pos_in_range > 0.7 → 接近高位压力区, score 偏低
            sr_score = int((0.5 - pos_in_range) * 120)  # -60 到 +60
            sr_desc = f"位置{pos_in_range:.0%}(近20根)"
            scores.append(("简单S/R", sr_score, 0.5, sr_desc))

        # 加权平均 → 0-100
        total_w = sum(w for _, _, w, _ in scores)
        if total_w == 0:
            avg_raw = 0
        else:
            avg_raw = sum(s * w for _, s, w, _ in scores) / total_w
        total = int((avg_raw + 100) / 2)
        return scores, total

    def _install_score_hover(self, canvas, ax_main, opens, highs, lows, closes, vol,
                             trade_dates=None, extra_info_fn=None):
        """给 matplotlib canvas 的主图装一个综合评分 hover tooltip。
        - opens/highs/lows/closes/vol: numpy arrays
        - trade_dates: list of date strings (可选)
        - extra_info_fn: callable(idx) -> (scores_list, total)，让调用方可以传额外指标分
        返回 (hover_text, bbox_base) 供调用方自定义。
        """
        opens = np.asarray(opens, dtype=float)
        highs = np.asarray(highs, dtype=float) if highs is not None else None
        lows = np.asarray(lows, dtype=float) if lows is not None else None
        closes = np.asarray(closes, dtype=float)
        vol = np.asarray(vol, dtype=float) if vol is not None else None
        n = len(closes)
        # trade_dates 可能是 pandas Series → 强制转 list 避免 bool 判断报错
        if trade_dates is not None:
            try: trade_dates = list(trade_dates)
            except Exception: trade_dates = None

        bbox_base = dict(boxstyle='round,pad=0.5', alpha=0.95, linewidth=1.2)
        hover_text = ax_main.text(0.01, 0.99, "", transform=ax_main.transAxes,
                                  fontsize=8.5, va='top', ha='left',
                                  bbox=dict(bbox_base, facecolor='#F5F5F5', edgecolor='#888888'),
                                  linespacing=1.4, visible=False)

        def _on_hover(event):
            try:
                print(f"[hover] event! inaxes={event.inaxes is not None} "
                      f"xdata={event.xdata!r} ax_main={ax_main}", flush=True)
                if event.inaxes != ax_main:
                    hover_text.set_visible(False); canvas.draw_idle(); return
                if event.xdata is None or np.isnan(event.xdata):
                    hover_text.set_visible(False); canvas.draw_idle(); return
                idx = int(round(event.xdata))
                if idx < 0 or idx >= n:
                    hover_text.set_visible(False); canvas.draw_idle(); return

                print(f"[hover] idx={idx}/{n} calculating...", flush=True)
                # 先算通用分
                scores, total = self._generic_indicator_scores(
                    idx, closes, highs, lows, opens, vol)
                print(f"[hover] basic scores={len(scores)} total={total}", flush=True)

                # 调用方额外分 (例如一目均衡的复合指标)
                if extra_info_fn is not None:
                    try:
                        extra_scores, extra_total = extra_info_fn(idx)
                        if extra_scores:
                            scores.extend(extra_scores)
                        if extra_total is not None and len(scores) >= 4:
                            total = extra_total
                    except Exception as e2:
                        print(f"[hover] extra_info_fn error: {e2!s}", flush=True)
                        import traceback; traceback.print_exc()

                # 组装 tooltip
                close_val = float(closes[idx])
                op_val = float(opens[idx])
                hi = float(highs[idx]) if highs is not None else close_val
                lo = float(lows[idx]) if lows is not None else close_val
                pct_chg = (close_val - op_val) / op_val * 100 if op_val != 0 else 0

                # 日期标签: 兼容 Timestamp / string / int
                date_label = f"K{idx+1}"
                if trade_dates is not None and len(trade_dates) > 0 and idx < len(trade_dates):
                    try:
                        d0 = trade_dates[idx]
                        # Timestamp 对象只取日期部分
                        import pandas as _pd
                        if isinstance(d0, _pd.Timestamp):
                            date_label = d0.strftime("%Y-%m-%d")
                        else:
                            date_label = str(d0)[:10]
                    except Exception:
                        date_label = f"K{idx+1}"

                lines = [f"📅 {date_label}  K#{idx+1}"]
                lines.append(f"  O{op_val:.2f}  H{hi:.2f}  L{lo:.2f}  C{close_val:.2f} ({pct_chg:+.2f}%)")
                if scores:
                    lines.append("─" * 22)
                    for name, sc, _w, desc in scores:
                        sc_color = "🟢" if sc > 20 else ("🔴" if sc < -20 else "⚪")
                        lines.append(f"  {name:10s} {sc_color} {sc:+.0f}  {desc}")
                lines.append("─" * 22)
                if total >= 70: verdict = "🟢 偏多"
                elif total >= 55: verdict = "🟡 略偏多"
                elif total >= 45: verdict = "⚪ 中性"
                elif total >= 30: verdict = "🟠 略偏空"
                else: verdict = "🔴 偏空"
                lines.append(f"  🎯 综合: {total}/100  {verdict}")

                hover_text.set_text("\n".join(lines))
                face_light, edge, text_c, _ = self._score_to_color(total)
                hover_text.set_bbox(dict(boxstyle='round,pad=0.5',
                                         facecolor=face_light, edgecolor=edge,
                                         alpha=0.95, linewidth=1.2))
                hover_text.set_color(text_c)
                hover_text.set_visible(True)
                print(f"[hover] SHOWING tooltip total={total}", flush=True)
                if idx > n * 0.6:
                    hover_text.set_ha('right'); hover_text.set_x(0.99)
                else:
                    hover_text.set_ha('left'); hover_text.set_x(0.01)
                canvas.draw_idle()
            except Exception as e:
                print(f"[hover] 出错: {e!s}", flush=True)
                import traceback; traceback.print_exc()
                hover_text.set_visible(False)
                try: canvas.draw_idle()
                except Exception: pass

        canvas.mpl_connect("motion_notify_event", _on_hover)
        canvas.mpl_connect("axes_leave_event",
            lambda e: (hover_text.set_visible(False), canvas.draw_idle()))
        return hover_text

    # ═══════════════════════════════════════════════════════════════
    # 一目均衡表 (Ichimoku Kinko Hyo) 核心函数
    # ═══════════════════════════════════════════════════════════════

    def _calc_ichimoku(self, highs, lows, closes):
        """计算一目均衡表 (Ichimoku) 的 5 条线。
        参数都是 numpy 数组, 返回 dict 包含:
          - tenkan_sen (转换线/短期趋势线)
          - kijun_sen (基准线/中期趋势线)
          - senkou_span_a (先行带A/快线)
          - senkou_span_b (先行带B/慢线)
          - chikou_span (迟行带/落后线)
          - cloud_top, cloud_bottom (云的上下边界, 用于绘制填充)
        注意: 先行带 A/B 要向前偏移 26 根 K 线 (预测未来)
        """
        h = np.asarray(highs, dtype=float)
        l = np.asarray(lows, dtype=float)
        c = np.asarray(closes, dtype=float)
        n = len(c)

        def _period_high(arr, period):
            """滚动窗口最高, min_periods=1: 窗口不满也用已有数据算, 从第 1 根起就有值。"""
            out = np.full(len(arr), np.nan)
            for i in range(len(arr)):
                start = max(0, i - period + 1)
                out[i] = np.max(arr[start:i + 1])
            return out

        def _period_low(arr, period):
            """滚动窗口最低, min_periods=1: 窗口不满也用已有数据算。"""
            out = np.full(len(arr), np.nan)
            for i in range(len(arr)):
                start = max(0, i - period + 1)
                out[i] = np.min(arr[start:i + 1])
            return out

        # 1. 转换线 (Tenkan-sen): 短期 (9 期) 最高价和最低价的中点
        # 注意: 一目均衡的转换线是 (9 日最高 + 9 日最低) / 2, 然后再做一次 6 期平均
        # 简化版: 直接用 (9日最高+9日最低)/2
        tenkan_sen = (_period_high(h, 9) + _period_low(l, 9)) / 2.0

        # 2. 基准线 (Kijun-sen): 中期 (26 期) 最高价和最低价的中点
        kijun_sen = (_period_high(h, 26) + _period_low(l, 26)) / 2.0

        # 3. 先行带 A (Senkou Span A): (转换线 + 基准线) / 2, 向前偏移 26
        senkou_a = (tenkan_sen + kijun_sen) / 2.0
        senkou_a_shifted = np.full(n + 26, np.nan)
        senkou_a_shifted[26:26 + n] = senkou_a  # 右移 26 位

        # 4. 先行带 B (Senkou Span B): (52 期最高 + 52 期最低) / 2, 向前偏移 26
        senkou_b = (_period_high(h, 52) + _period_low(l, 52)) / 2.0
        senkou_b_shifted = np.full(n + 26, np.nan)
        senkou_b_shifted[26:26 + n] = senkou_b

        # 5. 迟行带 (Chikou Span): 当前收盘价左移 26 根 (画在过去 26 根的位置上)
        # 也就是: 位置 0 显示的是 c[26] 的值 (今天价格对应 26 天前的位置)
        chikou = np.full(n, np.nan)
        shift = 26
        if n > shift:
            chikou[:n - shift] = c[shift:]
        # 为了和先行带统一在同一个 extended 坐标系里展示, 扩展到 n+26
        chikou_extended = np.full(n + 26, np.nan)
        chikou_extended[:n] = chikou

        return {
            'tenkan_sen': tenkan_sen,
            'kijun_sen': kijun_sen,
            'senkou_a': senkou_a_shifted,
            'senkou_b': senkou_b_shifted,
            'chikou': chikou_extended,
        }

    def _plot_ichimoku_ax(self, ax, x, highs, lows, closes, show_explanation=True):
        """在主图上叠加一目均衡表 (Ichimoku Kinko Hyo)。
        x: 索引数组 (长度 n)
        ichimoku 的先行带 A/B 长度是 n+26 (右移了 26), 所以 x 也需要扩展
        """
        ich = self._calc_ichimoku(highs, lows, closes)
        n = len(closes)
        extended_x = list(range(n + 26))
        x_arr = np.asarray(x)

        # 云 (Kumo): 先行带 A 和 B 之间的填充区域
        sen_a = ich['senkou_a']
        sen_b = ich['senkou_b']

        # 云的上边界和下边界
        cloud_top = np.nanmax([sen_a, sen_b], axis=0)
        cloud_bottom = np.nanmin([sen_a, sen_b], axis=0)

        # 云的颜色: A > B = 看涨云 → 红色 (A股红涨绿跌习惯)
        # A < B = 看跌云 → 绿色
        ax.fill_between(extended_x, cloud_bottom, cloud_top,
                        where=sen_a >= sen_b, color='#c62828', alpha=0.20, label='看涨云(Kumo Bull)')
        ax.fill_between(extended_x, cloud_bottom, cloud_top,
                        where=sen_a < sen_b, color='#2e7d32', alpha=0.20, label='看跌云(Kumo Bear)')

        # 先行带 A 和 B 线 (预测未来 26 根)
        ax.plot(extended_x, sen_a, color='#2196f3', linewidth=1.0, alpha=0.7, label='先行带A (Senkou A)', linestyle='--')
        ax.plot(extended_x, sen_b, color='#ff9800', linewidth=1.0, alpha=0.7, label='先行带B (Senkou B)', linestyle='--')

        # 转换线 (Tenkan-sen): 红色
        tenkan_line = None
        if not np.all(np.isnan(ich['tenkan_sen'])):
            tenkan_line = ax.plot(x_arr, ich['tenkan_sen'], color='#e91e63', linewidth=1.2, label='转换线 (Tenkan)')
            # 末端加中文标签
            last_valid_idx = n - 1
            while last_valid_idx >= 0 and np.isnan(ich['tenkan_sen'][last_valid_idx]):
                last_valid_idx -= 1
            if last_valid_idx >= 0:
                ax.annotate('转', xy=(last_valid_idx, ich['tenkan_sen'][last_valid_idx]),
                            xytext=(5, 6), textcoords='offset points',
                            fontsize=8, color='#e91e63', fontweight='bold', alpha=0.85)

        # 基准线 (Kijun-sen): 蓝色
        if not np.all(np.isnan(ich['kijun_sen'])):
            ax.plot(x_arr, ich['kijun_sen'], color='#1565c0', linewidth=1.2, label='基准线 (Kijun)')
            last_valid_idx = n - 1
            while last_valid_idx >= 0 and np.isnan(ich['kijun_sen'][last_valid_idx]):
                last_valid_idx -= 1
            if last_valid_idx >= 0:
                ax.annotate('基', xy=(last_valid_idx, ich['kijun_sen'][last_valid_idx]),
                            xytext=(5, -10), textcoords='offset points',
                            fontsize=8, color='#1565c0', fontweight='bold', alpha=0.85)

        # 迟行带 (Chikou): 收盘价后移 26 根 — 画在后面
        if not np.all(np.isnan(ich['chikou'])):
            ax.plot(extended_x, ich['chikou'], color='#9c27b0', linewidth=0.9, alpha=0.6,
                    label='迟行带 (Chikou)', linestyle=':')

        # ═══════════════════════════════════════════════════════════════
        # 🎯 一目均衡关键信号标记
        # ═══════════════════════════════════════════════════════════════
        tenkan = ich['tenkan_sen']
        kijun = ich['kijun_sen']
        chikou = ich['chikou']

        # 1) 金叉/死叉: Tenkan 与 Kijun 交叉
        for i in range(1, n):
            if np.isnan(tenkan[i]) or np.isnan(tenkan[i-1]) or np.isnan(kijun[i]) or np.isnan(kijun[i-1]):
                continue
            prev_diff = tenkan[i-1] - kijun[i-1]
            curr_diff = tenkan[i] - kijun[i]
            if prev_diff <= 0 < curr_diff:
                # 金叉 → 转上穿基
                ax.scatter([i], [lows[i] * 0.998], marker='^', color='#d32f2f', s=60, zorder=15, edgecolors='none')
                ax.annotate('金', xy=(i, lows[i]), xytext=(0, -14), textcoords='offset points',
                            fontsize=7, color='#d32f2f', fontweight='bold', ha='center')
            elif prev_diff >= 0 > curr_diff:
                # 死叉 → 转下穿基
                ax.scatter([i], [highs[i] * 1.002], marker='v', color='#2e7d32', s=60, zorder=15, edgecolors='none')
                ax.annotate('死', xy=(i, highs[i]), xytext=(0, 6), textcoords='offset points',
                            fontsize=7, color='#2e7d32', fontweight='bold', ha='center')

        # 2) 出云/入云: Close 与云边界交叉 (cloud 在 extended_x 坐标)
        # cloud_top/cloud_bottom 长度 n+26, closes 长度 n
        # closes[i] 对应 cloud_top[i] / cloud_bottom[i]
        for i in range(1, n):
            ct, cb = cloud_top[i], cloud_bottom[i]
            ct_p, cb_p = cloud_top[i-1], cloud_bottom[i-1]
            if np.isnan(ct) or np.isnan(cb) or np.isnan(ct_p) or np.isnan(cb_p):
                continue
            ci, ci_p = closes[i], closes[i-1]
            # 出云: 上穿云顶
            if ci_p <= ct_p and ci > ct:
                ax.scatter([i], [ct], marker='^', color='#ff5722', s=70, zorder=15, edgecolors='white', linewidths=0.8)
                ax.annotate('出云', xy=(i, ct), xytext=(0, -16), textcoords='offset points',
                            fontsize=6, color='#ff5722', fontweight='bold', ha='center')
            # 入云: 下穿云底
            elif ci_p >= cb_p and ci < cb:
                ax.scatter([i], [cb], marker='v', color='#009688', s=70, zorder=15, edgecolors='white', linewidths=0.8)
                ax.annotate('入云', xy=(i, cb), xytext=(0, 8), textcoords='offset points',
                            fontsize=6, color='#009688', fontweight='bold', ha='center')

        # 3) 云变色: Senkou A 与 Senkou B 交叉 (限制在 K 线范围 0..n-1)
        for i in range(1, min(n, len(sen_a))):
            if np.isnan(sen_a[i]) or np.isnan(sen_a[i-1]) or np.isnan(sen_b[i]) or np.isnan(sen_b[i-1]):
                continue
            prev_sd = sen_a[i-1] - sen_b[i-1]
            curr_sd = sen_a[i] - sen_b[i]
            if prev_sd <= 0 < curr_sd:
                # 看涨云形成 (A上穿B)
                mid_y = (cloud_top[i] + cloud_bottom[i]) / 2
                ax.scatter([i], [mid_y], marker='o', color='#e53935', s=40, zorder=14, alpha=0.85)
                ax.annotate('云多', xy=(i, mid_y), xytext=(0, -12), textcoords='offset points',
                            fontsize=6, color='#e53935', fontweight='bold', ha='center')
            elif prev_sd >= 0 > curr_sd:
                # 看跌云形成 (A下穿B)
                mid_y = (cloud_top[i] + cloud_bottom[i]) / 2
                ax.scatter([i], [mid_y], marker='o', color='#43a047', s=40, zorder=14, alpha=0.85)
                ax.annotate('云空', xy=(i, mid_y), xytext=(0, 6), textcoords='offset points',
                            fontsize=6, color='#43a047', fontweight='bold', ha='center')

        # 4) 迟行带穿云信号: 迟行带进入/穿出云边界 (extended_x 坐标)
        # chikou[t] = closes[t-26], 云边界 cloud_top[t] 对应 t 位置
        for i in range(27, min(n, len(chikou))):
            if np.isnan(chikou[i]) or np.isnan(chikou[i-1]):
                continue
            ct_i, cb_i = cloud_top[i], cloud_bottom[i]
            ct_p, cb_p = cloud_top[i-1], cloud_bottom[i-1]
            if np.isnan(ct_i) or np.isnan(cb_i) or np.isnan(ct_p) or np.isnan(cb_p):
                continue
            # 迟行带上穿云顶 (看涨)
            if chikou[i-1] <= ct_p and chikou[i] > ct_i:
                ax.scatter([i], [ct_i], marker='^', color='#7c4dff', s=55, zorder=14, alpha=0.85, edgecolors='white', linewidths=0.6)
                ax.annotate('迟出', xy=(i, ct_i), xytext=(0, -12), textcoords='offset points',
                            fontsize=6, color='#7c4dff', fontweight='bold', ha='center')
            # 迟行带下穿云底 (看跌)
            elif chikou[i-1] >= cb_p and chikou[i] < cb_i:
                ax.scatter([i], [cb_i], marker='v', color='#ff4081', s=55, zorder=14, alpha=0.85, edgecolors='white', linewidths=0.6)
                ax.annotate('迟入', xy=(i, cb_i), xytext=(0, 6), textcoords='offset points',
                            fontsize=6, color='#ff4081', fontweight='bold', ha='center')

    # ═══════════════════════════════════════════════════════════════
    # VW-MACD (带成交量权重的 MACD)
    # ═══════════════════════════════════════════════════════════════

    def _calc_vwmacd(self, closes, vol, fast=12, slow=26, signal=9):
        """VW-MACD: 用成交量加权的 MACD。
        公式:
          1. typical_price = close
          2. 用成交量作为权重计算 VW-EMA (成交量加权指数平滑均线)
          3. DIF = VW-EMA(fast) - VW-EMA(slow)
          4. DEA = VW-EMA(DIF, signal)
          5. MACD 柱 = 2 * (DIF - DEA)
        简化版: 用成交量的 EMA 对 MACD 的 DIF 和 DEA 进行量能修正
        更通用的 VW-MACD 公式 (网上):
          VOL_MA = SMA(VOL, period)
          MACD_VOL = MACD * (VOL / VOL_MA)   ← 对 MACD 柱进行量能修正
        返回: {dif, dea, macdh, vol_ratio, vol_ma}
        """
        c = np.asarray(closes, dtype=float)
        v = np.asarray(vol, dtype=float)
        n = len(c)

        # 标准 MACD
        ema_fast = self._ema_np(c, fast) if hasattr(self, '_ema_np') else self._simple_ema(c, fast)
        ema_slow = self._ema_np(c, slow) if hasattr(self, '_ema_np') else self._simple_ema(c, slow)
        dif = ema_fast - ema_slow
        dea = self._ema_np(dif, signal) if hasattr(self, '_ema_np') else self._simple_ema(dif, signal)
        macdh = 2.0 * (dif - dea)

        # 成交量均线
        v_ma20 = pd.Series(v).rolling(20, min_periods=1).mean().values
        # 成交量比率 (当前量 / 20日均量)
        vol_ratio = np.where(v_ma20 > 0, v / v_ma20, 1.0)
        vol_ratio = np.clip(vol_ratio, 0.1, 5.0)  # 限制在合理范围

        # VW-MACD: 对 MACD 柱进行量能加权
        # 当成交量大时, MACD 柱放大 (信号更可信); 缩量时缩小
        vw_macdh = macdh * np.sqrt(vol_ratio)  # 用根号防止放大太夸张

        # 对 DIF/DEA 也做量能修正 (更高级版本)
        vw_dif = dif * (0.5 + 0.5 * np.sqrt(vol_ratio))
        vw_dea = self._ema_np(vw_dif, signal) if hasattr(self, '_ema_np') else self._simple_ema(vw_dif, signal)

        return {
            'dif': vw_dif,
            'dea': vw_dea,
            'macdh': vw_macdh,
            'vol_ratio': vol_ratio,
            'vol_ma': v_ma20,
            'vol': v,
        }

    def _simple_ema(self, data, period):
        """简单 EMA 计算 (fallback, 如果 _ema_np 不存在)"""
        arr = np.asarray(data, dtype=float)
        alpha = 2.0 / (period + 1)
        out = np.zeros(len(arr))
        out[0] = arr[0]
        for i in range(1, len(arr)):
            out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
        return out

    # ═══════════════════════════════════════════════════════════════
    # 复合指标: SuperTrend (ATR 趋势带 + 动态 S/R)
    # ═══════════════════════════════════════════════════════════════

    def _calc_supertrend(self, highs, lows, closes, period=10, multiplier=3):
        """SuperTrend: 基于 ATR 的趋势跟踪复合指标。
        自带动态压力支撑: 上涨趋势中 SuperTrend 线 = 动态支撑, 下跌趋势中 = 动态压力。
        返回 dict: trend_dir (+1 上 / -1 下), supertrend_line, upper, lower
        """
        h = np.asarray(highs, dtype=float)
        l = np.asarray(lows, dtype=float)
        c = np.asarray(closes, dtype=float)
        n = len(c)

        tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
        tr[0] = h[0] - l[0]
        atr = np.full(n, np.nan)
        for i in range(period - 1, n):
            atr[i] = np.mean(tr[i - period + 1:i + 1])

        hl2 = (h + l) / 2.0
        upper = hl2 + multiplier * atr
        lower = hl2 - multiplier * atr

        # 递归修正
        for i in range(period, n):
            if lower[i] > lower[i - 1] or c[i - 1] < lower[i - 1]:
                lower[i] = lower[i]
            else:
                lower[i] = lower[i - 1]
            if upper[i] < upper[i - 1] or c[i - 1] > upper[i - 1]:
                upper[i] = upper[i]
            else:
                upper[i] = upper[i - 1]

        trend_dir = np.ones(n, dtype=int)
        supertrend = np.full(n, np.nan)
        trend_dir[0] = 1
        supertrend[0] = lower[0]
        for i in range(1, n):
            if trend_dir[i - 1] == 1:
                if c[i] <= lower[i]:
                    trend_dir[i] = -1
                    supertrend[i] = upper[i]
                else:
                    trend_dir[i] = 1
                    supertrend[i] = lower[i]
            else:
                if c[i] >= upper[i]:
                    trend_dir[i] = 1
                    supertrend[i] = lower[i]
                else:
                    trend_dir[i] = -1
                    supertrend[i] = upper[i]

        return {'trend_dir': trend_dir, 'supertrend': supertrend, 'upper': upper, 'lower': lower}

    # ═══════════════════════════════════════════════════════════════
    # 复合指标: VWAP + σ 带 (机构公允价值 + 动态压力支撑)
    # ═══════════════════════════════════════════════════════════════

    def _calc_vwap(self, opens, highs, lows, closes, vol, anchor_days=120):
        """VWAP 带: 成交量加权均价 + ±1σ ±2σ 动态通道。
        anchor_days: 回看多少天累积 VWAP (0 = 从第一天开始)
        返回 dict: vwap, upper1, lower1 (±1σ), upper2, lower2 (±2σ)
        """
        o = np.asarray(opens, dtype=float)
        h = np.asarray(highs, dtype=float)
        l = np.asarray(lows, dtype=float)
        c = np.asarray(closes, dtype=float)
        v = np.asarray(vol, dtype=float)
        n = len(c)

        typical = (h + l + c) / 3.0

        anchor = max(0, n - anchor_days) if anchor_days > 0 else 0
        cum_tv = np.cumsum(typical * v)
        cum_v = np.cumsum(v)
        # 锚定后: 减去锚定点之前的值
        cum_tv2 = cum_tv - (cum_tv[anchor - 1] if anchor > 0 else 0)
        cum_v2 = cum_v - (cum_v[anchor - 1] if anchor > 0 else 0)

        vwap = np.full(n, np.nan)
        vwap[anchor:] = cum_tv2[anchor:] / np.maximum(cum_v2[anchor:], 1e-9)

        # σ 带: 每根 K 线 typical 与 vwap 的偏差, 累积加权 std
        # 注意: 只计算 anchor 之后的偏差 (anchor 之前 vwap 是 nan)
        dev_sq = np.zeros(n)
        for i in range(anchor, n):
            if v[i] > 0 and not np.isnan(vwap[i]):
                dev_sq[i] = v[i] * (typical[i] - vwap[i]) ** 2
        cum_dev = np.cumsum(dev_sq)
        var = np.full(n, np.nan)
        # var[i] = (cum_dev[i] - cum_dev[anchor-1]) / (cum_v2[i] - cum_v2[anchor-1])
        for i in range(anchor, n):
            denom = cum_v2[i] - (cum_v2[anchor - 1] if anchor > 0 else 0)
            if denom > 0:
                num = cum_dev[i] - (cum_dev[anchor - 1] if anchor > 0 else 0)
                var[i] = num / denom
        sigma = np.sqrt(np.maximum(var, 0))

        upper1 = np.full(n, np.nan); lower1 = np.full(n, np.nan)
        upper2 = np.full(n, np.nan); lower2 = np.full(n, np.nan)
        upper1[anchor:] = vwap[anchor:] + sigma[anchor:]
        lower1[anchor:] = vwap[anchor:] - sigma[anchor:]
        upper2[anchor:] = vwap[anchor:] + 2 * sigma[anchor:]
        lower2[anchor:] = vwap[anchor:] - 2 * sigma[anchor:]

        return {'vwap': vwap, 'upper1': upper1, 'lower1': lower1,
                'upper2': upper2, 'lower2': lower2}

    # ═══════════════════════════════════════════════════════════════
    # 复合指标: TD Sequential (迪马克序列 — 衰竭反转捕捉)
    # ═══════════════════════════════════════════════════════════════

    def _calc_td_sequential(self, closes, opens=None):
        """TD Sequential: 迪马克序列, 捕捉趋势衰竭反转。
        核心: 当前收盘 vs 4 天前收盘, 连续上涨或下跌计数。
        Setup Countdown (1-9): 9 是衰竭信号。
        返回 dict: td_count (1-9), td_sell_setup, td_buy_setup
        """
        c = np.asarray(closes, dtype=float)
        n = len(c)
        td_count = np.zeros(n, dtype=int)
        # 1=上涨 setup (当前 > 4 天前), -1=下跌 setup, 0=不确定
        td_sell_setup = np.full(n, np.nan)  # 9 时标记衰竭
        td_buy_setup = np.full(n, np.nan)

        direction = 0  # 当前 setup 方向
        count = 0
        for i in range(4, n):
            if c[i] > c[i - 4]:
                if direction == 1:
                    count += 1
                else:
                    direction = 1
                    count = 1
                td_count[i] = count
                if count == 9:
                    td_sell_setup[i] = c[i]  # 衰竭信号, 可能反转下跌
                    count = 0  # 重置
            elif c[i] < c[i - 4]:
                if direction == -1:
                    count += 1
                else:
                    direction = -1
                    count = 1
                td_count[i] = -count
                if count == 9:
                    td_buy_setup[i] = c[i]  # 衰竭信号, 可能反转上涨
                    count = 0
            else:
                td_count[i] = 0
                count = 0

        return {'td_count': td_count, 'td_sell': td_sell_setup, 'td_buy': td_buy_setup}

    # ═══════════════════════════════════════════════════════════════
    # 复合指标: Camarilla Pivot (精细日内 S/R — 支持多周期)
    # ═══════════════════════════════════════════════════════════════

    def _calc_camarilla_pivot(self, highs, lows, closes, anchor=10):
        """Camarilla Pivot: 比传统 Pivot 更精细的压力支撑位。
        用前 anchor 根 K 线的 H/L/C 计算一组 Pivot 线。
        返回 dict: pivot, r1-r4, s1-s4 (单组 S/R 线, 画成水平线)
        """
        h = np.asarray(highs, dtype=float)
        l = np.asarray(lows, dtype=float)
        c = np.asarray(closes, dtype=float)
        n = len(c)
        if n < anchor + 1:
            anchor = max(3, n // 2)

        # 最近 anchor 根 K 线
        hh = np.max(h[-anchor:])
        ll = np.min(l[-anchor:])
        cc = c[-1]
        pivot = (hh + ll + cc) / 3.0
        range_hl = hh - ll

        r1 = cc + 1.1 * range_hl / 12
        r2 = cc + 1.1 * range_hl / 6
        r3 = cc + 1.1 * range_hl / 4
        r4 = cc + 1.1 * range_hl / 2
        s1 = cc - 1.1 * range_hl / 12
        s2 = cc - 1.1 * range_hl / 6
        s3 = cc - 1.1 * range_hl / 4
        s4 = cc - 1.1 * range_hl / 2

        return {
            'pivot': pivot,
            'resistances': [r1, r2, r3, r4],
            'supports': [s1, s2, s3, s4],
            'high_anchor': hh,
            'low_anchor': ll,
        }

    # ═══════════════════════════════════════════════════════════════
    # 多周期数据获取 (60min / 日 / 周 / 月)
    # ═══════════════════════════════════════════════════════════════

    def _fetch_ichimoku_kline_data(self, symbol, period="daily", is_index=False):
        """获取一目均衡表所需的多周期 K 线数据 (120+ 根, 用于 Ichimoku 计算)。
        核心策略: 先拉日 K (成熟 fallback 链), 再用 resample 聚合成周/月 K。
        symbol: 股票代码/指数代码, 支持 "600519" / "sh000001" / "sz399001" / "510300"(ETF)
        period: "60min" / "daily" / "weekly" / "monthly"
        is_index: 是否为指数
        返回: DataFrame [日期, 开盘, 最高, 最低, 收盘, 成交量] 或 None
        """
        from datetime import datetime, timedelta

        # ─── 关键修复: 保留原始 symbol, 不重新推断 market_prefix ───
        # INDEX_LIST 里给的就是 "sh000001" / "sz399001" (正确的指数前缀)
        # ETF_LIST 里给的就是纯 6 位 "510300" (个股/ETF 用 fetch_daily_kline)
        # stock_options 里也是纯 6 位
        # 只有 akshare 接口需要纯 6 位时才 strip 前缀

        # sina_symbol: 给 fetch_index_daily 用 (需要 sh/sz 前缀)
        if len(symbol) == 8 and symbol[:2].lower() in ("sh", "sz", "bj"):
            sina_symbol = symbol  # 已经带正确前缀, 直接用
        else:
            # 纯 6 位 code — 根据首数字推断市场 (只用于个股/ETF)
            code6 = str(symbol).zfill(6)
            prefix = "sh" if code6.startswith(("6", "5", "9")) else "sz"
            sina_symbol = f"{prefix}{code6}"

        # code6: 给 akshare 等接口用 (纯 6 位)
        code6 = symbol[2:] if len(symbol) == 8 and symbol[:2].lower() in ("sh", "sz", "bj") else symbol
        code6 = str(code6).zfill(6)

        # 需要至少 ~150 根日 K (一目均衡 52+26=78 有效 + 尾部 resample 缓冲)
        DAILY_DAYS = 200

        # ─── 方案 1: 先拿日 K (项目里的成熟 fallback 链) ───
        daily_df = None

        try:
            from ui._akshare_fetcher import fetch_daily_kline, fetch_index_daily
            if is_index:
                # 指数 — fetch_index_daily 内部会正确拆分 prefix+code
                daily_df = fetch_index_daily(sina_symbol, days=DAILY_DAYS)
                _price_hint = ""
                if daily_df is not None and len(daily_df) > 0:
                    _price_hint = f", close≈{float(daily_df['close'].iloc[-1]):.1f}"
                print(f"[一目均衡] 指数 → {sina_symbol} → {len(daily_df) if daily_df is not None else 'None'} 根{_price_hint}")
            else:
                # 个股/ETF — fetch_daily_kline 支持 Tushare + 新浪 + 腾讯
                daily_df = fetch_daily_kline(code6, days=DAILY_DAYS)
                _price_hint = ""
                if daily_df is not None and len(daily_df) > 0:
                    _price_hint = f", close≈{float(daily_df['close'].iloc[-1]):.2f}"
                print(f"[一目均衡] 个股/ETF → {code6} → {len(daily_df) if daily_df is not None else 'None'} 根{_price_hint}")
        except Exception as e:
            print(f"[一目均衡] fetch_*_daily 异常: {e}")
            import traceback; traceback.print_exc()

        # ─── 方案 2: 如果 fallback 链也挂了, 直接用 akshare 尝试 ───
        if daily_df is None or len(daily_df) < 60:
            print(f"[一目均衡] fallback 链不足, 尝试直接 akshare...")
            try:
                import akshare as ak
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=DAILY_DAYS + 30)).strftime('%Y%m%d')
                if is_index:
                    daily_df = ak.index_zh_a_hist(symbol=code6, period="daily")
                else:
                    daily_df = ak.stock_zh_a_hist(symbol=code6, period="daily", adjust="qfq",
                                                  start_date=start_date, end_date=end_date)
                if daily_df is not None and not daily_df.empty:
                    # 列名标准化 (akshare 中文列)
                    col_map = {}
                    for cn, en in [("日期", "date"), ("开盘", "open"), ("最高", "high"),
                                   ("最低", "low"), ("收盘", "close"), ("成交量", "volume")]:
                        if cn in daily_df.columns:
                            col_map[cn] = en
                    daily_df = daily_df.rename(columns=col_map)
                    print(f"[一目均衡] akshare 日K 兜底成功: {len(daily_df)} 根")
                else:
                    daily_df = None
            except Exception as e:
                print(f"[一目均衡] akshare 兜底也挂: {e}")
                daily_df = None

        if daily_df is None or len(daily_df) < 60:
            print(f"[一目均衡] ❌ 所有日K源都挂了, 无法获取 {symbol}")
            return None

        # ─── 日K列名标准化 → [日期, 开盘, 最高, 最低, 收盘, 成交量] ───
        df = daily_df.copy()
        # 确保 date 列存在 (可能是 datetime 或 str)
        if 'date' not in df.columns and '日期' in df.columns:
            df = df.rename(columns={'日期': 'date'})
        for cn, en in [("开盘", "open"), ("最高", "high"), ("最低", "low"),
                       ("收盘", "close"), ("成交量", "volume")]:
            if cn in df.columns and en not in df.columns:
                df = df.rename(columns={cn: en})

        required = ["date", "open", "high", "low", "close"]
        for col in required:
            if col not in df.columns:
                print(f"[一目均衡] ❌ 日K缺少列 {col}, 实际={list(df.columns)}")
                return None
        if "volume" not in df.columns:
            df["volume"] = 0

        # 统一 date → string "YYYY-MM-DD" 格式
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        df = df.sort_values('date').reset_index(drop=True)

        # ─── 方案 A: daily 直接返回 ───
        if period == "daily":
            result = pd.DataFrame({
                '日期': df['date'],
                '开盘': df['open'].astype(float),
                '最高': df['high'].astype(float),
                '最低': df['low'].astype(float),
                '收盘': df['close'].astype(float),
                '成交量': df['volume'].astype(float),
            }).tail(150).reset_index(drop=True)
            print(f"[一目均衡] ✅ {symbol} 日K: {len(result)} 根, 日期 {result['日期'].iloc[0]} ~ {result['日期'].iloc[-1]}")
            return result

        # ─── 方案 B: weekly / monthly → pandas resample 聚合 ───
        if period in ("weekly", "monthly"):
            freq = "W" if period == "weekly" else "ME"
            df_dt = df.copy()
            df_dt['date'] = pd.to_datetime(df_dt['date'])
            df_dt = df_dt.set_index('date')
            resampled = df_dt.resample(freq).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum',
            }).dropna(subset=['close'])
            resampled = resampled.reset_index()
            resampled['date'] = resampled['date'].dt.strftime('%Y-%m-%d')
            result = pd.DataFrame({
                '日期': resampled['date'],
                '开盘': resampled['open'].astype(float),
                '最高': resampled['high'].astype(float),
                '最低': resampled['low'].astype(float),
                '收盘': resampled['close'].astype(float),
                '成交量': resampled['volume'].astype(float),
            }).tail(80).reset_index(drop=True)  # 周/月 K 只要 80 根就够了
            print(f"[一目均衡] ✅ {symbol} {period}K (resample): {len(result)} 根")
            return result

        # ─── 方案 C: 60min K ───
        if period == "60min":
            try:
                import akshare as ak
                if is_index:
                    # 指数分钟线 — 某些 akshare 版本没有, 跳过
                    try:
                        mdf = ak.index_zh_a_hist_min_em(symbol=code6, period="60", adjust="")
                    except AttributeError:
                        print(f"[一目均衡] ⚠️ akshare 没有 index_zh_a_hist_min_em, 60min 指数不可用")
                        return None
                    except Exception:
                        mdf = None
                else:
                    mdf = ak.stock_zh_a_hist_min_em(symbol=code6, period="60", adjust="qfq")
                if mdf is None or mdf.empty:
                    print(f"[一目均衡] ❌ 60min K 线返回空")
                    return None
                # 列名标准化
                col_map = {}
                for cn, en in [("时间", "date"), ("开盘", "open"), ("最高", "high"),
                               ("最低", "low"), ("收盘", "close"), ("成交量", "volume")]:
                    if cn in mdf.columns:
                        col_map[cn] = en
                mdf = mdf.rename(columns=col_map)
                mdf['date'] = pd.to_datetime(mdf['date']).dt.strftime('%Y-%m-%d %H:%M')
                result = pd.DataFrame({
                    '日期': mdf['date'],
                    '开盘': mdf['open'].astype(float),
                    '最高': mdf['high'].astype(float),
                    '最低': mdf['low'].astype(float),
                    '收盘': mdf['close'].astype(float),
                    '成交量': mdf['volume'].astype(float),
                }).tail(180).reset_index(drop=True)
                print(f"[一目均衡] ✅ {symbol} 60min K: {len(result)} 根")
                return result
            except Exception as e:
                print(f"[一目均衡] ❌ 60min K 失败: {e}")
                return None

        print(f"[一目均衡] ❌ 未知 period={period}")
        return None

    # ═══════════════════════════════════════════════════════════════
    # 一目均衡 K 线弹窗 (主入口)
    # ═══════════════════════════════════════════════════════════════

    def _show_ichimoku_kline_dialog(self):
        """📈 一目均衡 + VW-MACD K 线弹窗 — 支持多标的 + 多周期"""
        import traceback as _tb
        print("[📈一目均衡] 按钮被点击!", flush=True)
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib import gridspec
            from matplotlib.figure import Figure

            win = self._safe_toplevel(self.root)
            win.title("📈 一目均衡表 + VW-MACD K线分析")
            try:
                win.state("zoomed")
            except Exception:
                try:
                    win.attributes("-zoomed", True)
                except Exception:
                    win.geometry("1300x900")

            # ─── 标的下拉框 ───
            top_frame = ttk.Frame(win, padding=4)
            top_frame.pack(fill=tk.X)

            # 指数列表
            INDEX_LIST = [
                ("sh000001", "上证指数", True),
                ("sz399001", "深证成指", True),
                ("sz399006", "创业板指", True),
                ("sh000300", "沪深300", True),
                ("sh000905", "中证500", True),
                ("sh000016", "上证50", True),
                ("sz399300", "沪深300(深)", True),
            ]

            # ETF 列表
            ETF_LIST = [
                ("510300", "沪深300ETF", False),
                ("510500", "中证500ETF", False),
                ("510050", "上证50ETF", False),
                ("159915", "创业板ETF", False),
                ("512100", "中证1000ETF", False),
                ("512880", "证券ETF", False),
                ("515050", "5GETF", False),
                ("515790", "光伏ETF", False),
            ]

            # 持仓股 + 龙头股 + 资讯股
            stock_options = []
            seen = set()
            try:
                all_holdings = self._get_all_holding_stocks() if hasattr(self, '_get_all_holding_stocks') else []
                for sname, scode, gidx, _pos in all_holdings:
                    if scode not in seen:
                        seen.add(scode)
                        tag = "持仓" if gidx == 1 else ("龙头" if gidx == 2 else "其他")
                        stock_options.append((scode, f"{sname}({scode})[{tag}]", False))
            except Exception:
                pass
            try:
                from logic.stock_names import get_news_stocks_merged_recent_days
                hot = get_news_stocks_merged_recent_days(ndays=3)
                for sname, scode in hot[:30]:
                    if scode not in seen:
                        seen.add(scode)
                        stock_options.append((scode, f"{sname}({scode})[热门]", False))
            except Exception:
                pass

            # 合并所有选项
            all_options = []
            for sym, name, is_idx in INDEX_LIST:
                all_options.append((sym, name, is_idx))
            for sym, name, is_idx in ETF_LIST:
                all_options.append((sym, name, is_idx))
            for sym, name, is_idx in stock_options:
                all_options.append((sym, name, is_idx))

            display_names = [name for _, name, _ in all_options]
            sym_map = {name: (sym, is_idx) for sym, name, is_idx in all_options}

            # 控件
            ttk.Label(top_frame, text="📌 标的:").pack(side=tk.LEFT, padx=(0, 4))
            symbol_var = tk.StringVar(value="上证指数")
            sym_combo = ttk.Combobox(top_frame, values=display_names, width=22, state="normal",
                                     textvariable=symbol_var)
            sym_combo.pack(side=tk.LEFT, padx=2)

            def _resolve_and_draw():
                """解析输入: 纯代码/名称/名称(代码) 都能识别"""
                raw = symbol_var.get().strip()
                if not raw:
                    messagebox.showwarning("提示", "请输入股票名称或代码", parent=win)
                    return
                # 1) 精确匹配现有选项
                if raw in sym_map:
                    redraw()
                    return
                # 2) 名称模糊匹配 (只匹配本地已有的)
                hits = [name for name in sym_map if raw in name]
                if hits:
                    if len(hits) == 1:
                        symbol_var.set(hits[0]); redraw(); return
                    best = max(hits, key=len)
                    symbol_var.set(best); redraw(); return
                # 3) 输入是6位A股代码
                import re
                m_code = re.search(r'[036]\d{5}', raw)
                if m_code:
                    code6 = m_code.group()
                    # 先在已有下拉里反查
                    for dn in display_names:
                        if code6 in dn:
                            symbol_var.set(dn); redraw(); return
                    # 把新代码塞进 sym_map, 再 redraw
                    sym_map[code6] = (code6, False)
                    symbol_var.set(code6)
                    redraw(); return
                # 4) 名称(代码) 格式
                m2 = re.match(r'([\u4e00-\u9fa5A-Za-z·]{2,12})\s*[\(（]\s*([036]\d{5})\s*[\)）]', raw)
                if m2:
                    sym_code = m2.group(2)
                    sym_map[raw] = (sym_code, False)
                    redraw(); return
                # 兜底: 直接把输入当代码查
                sym_map[raw] = (raw, False)
                redraw()

            sym_combo.bind("<Return>", lambda e: (_resolve_and_draw(), "break"))
            sym_combo.bind("<FocusOut>", lambda e: _resolve_and_draw())

            ttk.Label(top_frame, text="  ⏱ 周期:").pack(side=tk.LEFT, padx=(10, 4))
            period_var = tk.StringVar(value="daily")
            PERIOD_LABELS = {"60min": "60分钟", "daily": "日K", "weekly": "周K", "monthly": "月K"}
            PERIOD_KEYS = ["60min", "daily", "weekly", "monthly"]
            period_combo = ttk.Combobox(top_frame, values=[PERIOD_LABELS[p] for p in PERIOD_KEYS],
                                        width=10, state="readonly")
            period_combo.set("日K")
            period_combo.pack(side=tk.LEFT, padx=2)

            ttk.Button(top_frame, text="🔄 刷新", command=lambda: redraw()).pack(side=tk.LEFT, padx=(15, 4))

            # ❓ 解释按钮
            def _show_ichimoku_help(_event=None):
                help_win = tk.Toplevel(win)
                help_win.title("📖 一目均衡表 + 复合指标说明 (3列)")
                help_win.geometry("1280x780")
                help_win.configure(bg="#ECEFF1")

                # 顶栏: 字体控件 (3 列同步)
                ctrl = ttk.Frame(help_win); ctrl.pack(fill=tk.X, padx=10, pady=(8, 4))
                ttk.Label(ctrl, text="🔤 字体:").pack(side=tk.LEFT)
                font_size_var = tk.IntVar(value=13)

                _texts = []  # 收集 3 个 text widget

                def _apply_font(size):
                    for t in _texts:
                        try:
                            t.configure(font=("Microsoft YaHei", size))
                            t.tag_configure("title", font=("Microsoft YaHei", size + 3, "bold"))
                            t.tag_configure("subtitle", font=("Microsoft YaHei", size + 1, "bold"))
                            t.tag_configure("body", font=("Microsoft YaHei", size))
                        except Exception:
                            pass

                ttk.Button(ctrl, text="A-", width=3,
                           command=lambda: (font_size_var.set(max(8, font_size_var.get() - 1)),
                                            _apply_font(font_size_var.get()))).pack(side=tk.LEFT, padx=(4, 0))
                ttk.Button(ctrl, text="A+", width=3,
                           command=lambda: (font_size_var.set(min(22, font_size_var.get() + 1)),
                                            _apply_font(font_size_var.get()))).pack(side=tk.LEFT)
                ttk.Label(ctrl, text=f"  {font_size_var.get()}pt").pack(side=tk.LEFT)
                def _on_scale(v):
                    try:
                        font_size_var.set(int(float(v)))
                        _apply_font(font_size_var.get())
                    except Exception:
                        pass
                scale = ttk.Scale(ctrl, from_=9, to=20, orient=tk.HORIZONTAL,
                                  command=_on_scale, length=180)
                scale.set(font_size_var.get())
                scale.pack(side=tk.LEFT, padx=(12, 0))
                ttk.Button(ctrl, text="重置", width=4,
                           command=lambda: (font_size_var.set(10), _apply_font(10), scale.set(10))
                           ).pack(side=tk.LEFT, padx=(6, 0))

                # 3 列 grid 容器
                cols_frame = tk.Frame(help_win, bg="#ECEFF1")
                cols_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
                for c in range(3):
                    cols_frame.columnconfigure(c, weight=1, uniform="col")
                cols_frame.rowconfigure(0, weight=1)

                # ─── 左列: 一目均衡 + VW-MACD ───
                left_frame = tk.Frame(cols_frame, bg="#FFF3E0", bd=1, relief=tk.SOLID)
                left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
                ttk.Label(left_frame, text="📈 主图指标",
                          font=("Microsoft YaHei", 13, "bold"),
                          background="#FF9800", foreground="white", anchor="center"
                          ).pack(fill=tk.X)
                sb1 = ttk.Scrollbar(left_frame); sb1.pack(side=tk.RIGHT, fill=tk.Y)
                text1 = tk.Text(left_frame, wrap=tk.WORD, font=("Microsoft YaHei", font_size_var.get()),
                                bg="#FFF8E1", fg="#3E2723", padx=10, pady=8,
                                yscrollcommand=sb1.set, height=30)
                text1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                sb1.config(command=text1.yview)
                _texts.append(text1)

                text1.tag_configure("title", foreground="#E65100")
                text1.tag_configure("subtitle", foreground="#BF360C")
                text1.tag_configure("body", foreground="#3E2723")

                text1.insert(tk.END, "═══ 一目均衡表 (Ichimoku) ═══\n\n", "title")
                text1.insert(tk.END, "▌五条线含义\n", "subtitle")
                text1.insert(tk.END,
                    "1. 🔴 转换线 (Tenkan-sen): 9期最高+最低的中点\n"
                    "   → 短期趋势线, 类似快均线\n\n"
                    "2. 🔵 基准线 (Kijun-sen): 26期最高+最低的中点\n"
                    "   → 中期趋势线, 类似慢均线\n"
                    "   → 转换线上穿基准线=金叉 (买入信号)\n"
                    "   → 转换线下穿基准线=死叉 (卖出信号)\n\n"
                    "3. 🔵 先行带 A: (转换+基准)/2, 右移 26 根\n"
                    "   → 预测未来 26 根的 S/R\n\n"
                    "4. 🟠 先行带 B: (52期高+低)/2, 右移 26 根\n"
                    "   → 预测未来 52 根的 S/R\n\n"
                    "5. 🟣 迟行带: 收盘价, 左移 26 根\n"
                    "   → 当前价格相对于 26 期前的位置\n\n", "body")
                text1.insert(tk.END, "═══ ⭐ 一目均衡实战应用技巧 ═══\n\n", "title")
                text1.insert(tk.END, "▌① 用云层定趋势与支撑阻力 (核心)\n", "subtitle")
                text1.insert(tk.END,
                    "趋势判断:\n"
                    "  价在云层上方 → 多头趋势 (云层=动态支撑)\n"
                    "  价在云层下方 → 空头趋势 (云层=动态阻力)\n"
                    "  价在云层内部 → 震荡市 (观望为主)\n\n"
                    "云层厚度:\n"
                    "  越厚 → 支撑/阻力越强, 突破需更大动能\n"
                    "  越薄 → 越易被突破 (趋势转弱信号)\n\n"
                    "云层颜色变换:\n"
                    "  未来云由红转绿 → 空头预警\n"
                    "  未来云由绿转红 → 多头预警\n\n", "body")
                text1.insert(tk.END, "▌② 用转换线+基准线抓短期信号\n", "subtitle")
                text1.insert(tk.END,
                    "金叉 (转换线上穿基准线):\n"
                    "  🟢 价格在云上 → 可靠买入信号 ✅\n"
                    "  🔴 价格在云内/下 → 假信号风险大 ⚠️\n\n"
                    "死叉 (转换线下穿基准线):\n"
                    "  🔴 价格在云下 → 可靠卖出信号 ✅\n"
                    "  🟢 价格在云内/上 → 假信号风险大 ⚠️\n\n"
                    "基准线方向:\n"
                    "  向上 → 短期偏多, 比单一均线更准\n"
                    "  向下 → 短期偏空\n\n", "body")
                text1.insert(tk.END, "▌③ 用迟行线确认动能\n", "subtitle")
                text1.insert(tk.END,
                    "迟行线在历史K线上方 → 多头动能强\n"
                    "迟行线在历史K线下方 → 空头动能强\n\n"
                    "与价格/云层无缠绕 → 趋势延续 (信号有效)\n"
                    "与价格/云层缠绕 → 震荡市 (信号无效)\n\n", "body")
                text1.insert(tk.END, "▌④ 实战组合策略 (过滤假信号)\n", "subtitle")
                text1.insert(tk.END,
                    "🎯 趋势交易 (高胜率):\n"
                    "  价在云上 + 基准线向上 + 迟行线在历史K线上方\n"
                    "  → 回调至转换线/云边买入; 止损云下\n\n"
                    "⚖️ 震荡交易 (低风险):\n"
                    "  价在云内 + 转换线与基准线反复交叉\n"
                    "  → 云边高抛低吸; 止损云层另一侧\n\n"
                    "🚀 突破交易 (抓拐点):\n"
                    "  价放量突破云层 + 转换线/基准线同步突破 + 迟行线配合\n"
                    "  → 顺突破方向入场; 止损突破点反侧\n\n", "body")
                text1.insert(tk.END, "▌⑤ 关键注意事项\n", "subtitle")
                text1.insert(tk.END,
                    "时间周期适配:\n"
                    "  日线/4小时 → 看趋势\n"
                    "  1小时 → 找入场 (短周期服从长周期)\n\n"
                    "结合量价:\n"
                    "  突破需放量, 缩量突破易回踩\n\n"
                    "多指标共振:\n"
                    "  搭配 RSI (超买超卖) / MACD (背离) 提升胜率\n\n"
                    "规避误区:\n"
                    "  震荡市信号频繁失效, 需严格止损\n"
                    "  参数 (9/26/52) 勿随意修改\n\n", "body")
                text1.insert(tk.END, "▌🎯 核心逻辑 (口诀)\n", "subtitle")
                text1.insert(tk.END,
                    "  云层定方向, 线组找点位,\n"
                    "  迟行线防骗线, 结合周期与量价 → 「一目」决策\n\n", "body")

                text1.insert(tk.END, "═══ VW-MACD (量价 MACD) ═══\n\n", "title")
                text1.insert(tk.END, "▌什么是 VW-MACD?\n", "subtitle")
                text1.insert(tk.END,
                    "VW-MACD = Volume-Weighted MACD\n"
                    "标准 MACD 只看价格, VW-MACD 把成交量作为权重:\n"
                    "量价齐升的信号更可靠, 缩量上涨的信号被弱化。\n\n", "body")
                text1.insert(tk.END, "▌公式原理\n", "subtitle")
                text1.insert(tk.END,
                    "1. 先算标准 MACD 的 DIF / DEA\n"
                    "2. VR = 当前量 / 20日均量\n"
                    "3. VW_MACD = MACD × √VR (放量放大, 缩量缩小)\n\n", "body")
                text1.insert(tk.END, "▌怎么看?\n", "subtitle")
                text1.insert(tk.END,
                    "• DIF 金叉 + 放量 = 强买入信号\n"
                    "• DIF 金叉但缩量 = 假突破可能\n"
                    "• DIF 死叉 + 放量 = 强卖出信号\n"
                    "• VW-MACD 柱放大 = 量价配合好, 趋势可靠\n\n", "body")
                text1.insert(tk.END, "▌与标准 MACD 的区别\n", "subtitle")
                text1.insert(tk.END,
                    "• 标准 MACD: 只看价格, 可能出现指标背离\n"
                    "• VW-MACD: 结合量价, 更早发现虚假突破\n"
                    "• 用法: 先看 VW-MACD 确认量能, 再用一目均衡判断趋势方向\n", "body")
                text1.config(state=tk.DISABLED)

                # ─── 中列: SuperTrend + VWAP ───
                mid_frame = tk.Frame(cols_frame, bg="#E8F5E9", bd=1, relief=tk.SOLID)
                mid_frame.grid(row=0, column=1, sticky="nsew", padx=4)
                ttk.Label(mid_frame, text="📊 通道类指标",
                          font=("Microsoft YaHei", 13, "bold"),
                          background="#43A047", foreground="white", anchor="center"
                          ).pack(fill=tk.X)
                sb2 = ttk.Scrollbar(mid_frame); sb2.pack(side=tk.RIGHT, fill=tk.Y)
                text2 = tk.Text(mid_frame, wrap=tk.WORD, font=("Microsoft YaHei", font_size_var.get()),
                                bg="#F1F8E9", fg="#1B5E20", padx=10, pady=8,
                                yscrollcommand=sb2.set, height=30)
                text2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                sb2.config(command=text2.yview)
                _texts.append(text2)

                text2.tag_configure("title", foreground="#1B5E20")
                text2.tag_configure("subtitle", foreground="#2E7D32")
                text2.tag_configure("body", foreground="#33691E")

                text2.insert(tk.END, "═══ SuperTrend ═══\n\n", "title")
                text2.insert(tk.END, "▌什么是 SuperTrend?\n", "subtitle")
                text2.insert(tk.END,
                    "基于 ATR (平均真实波幅) 的趋势跟踪复合指标,\n"
                    "波动大时通道宽, 波动小时通道窄。\n"
                    "核心: 线的颜色就是动态支撑/压力位本身。\n\n", "body")
                text2.insert(tk.END, "▌公式 (3 步)\n", "subtitle")
                text2.insert(tk.END,
                    "1. HL2 = (H + L) / 2\n"
                    "2. 通道 = HL2 ± (10期 ATR × 3)\n"
                    "3. 递归修正: 上涨通道下沿不降, 下跌上沿不升\n\n", "body")
                text2.insert(tk.END, "▌怎么看?\n", "subtitle")
                text2.insert(tk.END,
                    "• 🟢 绿色线 (↑): 动态支撑, 价踩线=买点\n"
                    "• 🔴 红色线 (↓): 动态压力, 价碰线=卖点\n"
                    "• 线变色 = 趋势反转信号\n"
                    "• 和云配合: 云方向 + SuperTrend = 双重确认\n\n", "body")

                text2.insert(tk.END, "═══ VWAP + σ 带 ═══\n\n", "title")
                text2.insert(tk.END, "▌什么是 VWAP?\n", "subtitle")
                text2.insert(tk.END,
                    "VWAP = 成交量加权平均价, 机构大户的交易基准。\n"
                    "价在 VWAP 以下 → 机构平均在亏损;\n"
                    "价在 VWAP 以上 → 机构平均在盈利。\n\n", "body")
                text2.insert(tk.END, "▌公式\n", "subtitle")
                text2.insert(tk.END,
                    "1. Typical = (H + L + C) / 3\n"
                    "2. VWAP = Σ(Typical × Vol) / Σ(Vol)\n"
                    "3. σ = √Σ(Vol × (Typical-VWAP)²) / Σ(Vol)\n"
                    "4. VWAP ± 1σ / ± 2σ = 动态波动通道\n\n", "body")
                text2.insert(tk.END, "▌怎么看?\n", "subtitle")
                text2.insert(tk.END,
                    "• 🟠 VWAP 线: 多空分水岭\n"
                    "• 价 < VWAP-2σ: 超跌区 (远低于机构成本)\n"
                    "• 价 > VWAP+2σ: 超买区 (远高于机构成本)\n"
                    "• ±1σ 带内: 正常波动区\n"
                    "• 突破 2σ + VW-MACD 配合 = 强反转信号\n\n", "body")
                text2.config(state=tk.DISABLED)

                # ─── 右列: TD Sequential + Camarilla + 组合建议 ───
                right_frame = tk.Frame(cols_frame, bg="#E3F2FD", bd=1, relief=tk.SOLID)
                right_frame.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
                ttk.Label(right_frame, text="🎯 反转与 S/R",
                          font=("Microsoft YaHei", 13, "bold"),
                          background="#1976D2", foreground="white", anchor="center"
                          ).pack(fill=tk.X)
                sb3 = ttk.Scrollbar(right_frame); sb3.pack(side=tk.RIGHT, fill=tk.Y)
                text3 = tk.Text(right_frame, wrap=tk.WORD, font=("Microsoft YaHei", font_size_var.get()),
                                bg="#E8EAF6", fg="#0D47A1", padx=10, pady=8,
                                yscrollcommand=sb3.set, height=30)
                text3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                sb3.config(command=text3.yview)
                _texts.append(text3)

                text3.tag_configure("title", foreground="#0D47A1")
                text3.tag_configure("subtitle", foreground="#1565C0")
                text3.tag_configure("body", foreground="#283593")

                text3.insert(tk.END, "═══ TD Sequential ═══\n\n", "title")
                text3.insert(tk.END, "▌什么是 TD 序列?\n", "subtitle")
                text3.insert(tk.END,
                    "Tom DeMark 发明的趋势衰竭捕捉指标。\n"
                    "连续 9 根 K 线收盘高于 (或低于) 4 天前收盘\n"
                    "→ 趋势能量耗尽, 即将反转。\n"
                    "9 不是买卖信号, 是「警惕信号」。\n\n", "body")
                text3.insert(tk.END, "▌公式\n", "subtitle")
                text3.insert(tk.END,
                    "• Setup: Close[i] > Close[i-4] 连满足 → +1, 否则重置\n"
                    "• 上涨 1-9 红色 (K线上方), 下跌 1-9 蓝色 (K线下方)\n"
                    "• 断档或方向改变 → 从 1 重新开始\n"
                    "• 图上只显示 6 以上的数字\n\n", "body")
                text3.insert(tk.END, "▌怎么看?\n", "subtitle")
                text3.insert(tk.END,
                    "• 🔴 上涨 9: 趋势衰竭, 警惕转跌\n"
                    "• 🔵 下跌 9: 抛压衰竭, 警惕反弹\n"
                    "• 需后续确认 (1-2 根 K 线反转)\n"
                    "• 周K/月K 9 信号 > 日K/60min (级别越高越可靠)\n\n", "body")

                text3.insert(tk.END, "═══ Camarilla Pivot ═══\n\n", "title")
                text3.insert(tk.END, "▌什么是 Camarilla?\n", "subtitle")
                text3.insert(tk.END,
                    "经典日内 S/R 方法, 比传统 Pivot 更精细。\n"
                    "4 组 R1-R4 / S1-S4, 密集覆盖价格区间。\n"
                    "价格在某个线反弹 = 重要介入/止盈位。\n\n", "body")
                text3.insert(tk.END, "▌公式 (近 10 根)\n", "subtitle")
                text3.insert(tk.END,
                    "H = 高, L = 低, C = 收, Range = H - L\n"
                    "Pivot = (H + L + C) / 3\n"
                    "R1 = C + 1.1×Range/12   S1 = C - 1.1×Range/12\n"
                    "R2 = C + 1.1×Range/6    S2 = C - 1.1×Range/6\n"
                    "R3 = C + 1.1×Range/4    S3 = C - 1.1×Range/4\n"
                    "R4 = C + 1.1×Range/2    S4 = C - 1.1×Range/2\n\n", "body")
                text3.insert(tk.END, "▌怎么看?\n", "subtitle")
                text3.insert(tk.END,
                    "• 🟠 Pivot: 多空焦点, 站上=偏多\n"
                    "• 🔴 R1-R4: 递增压力 (R4=强阻力)\n"
                    "• 🟢 S1-S4: 递减支撑 (S4=强支撑)\n"
                    "• 配合 SuperTrend: 绿线 + S2 = 双重底部\n"
                    "• 配合 VWAP: 突破 VWAP + R1 = 趋势启动\n\n", "body")

                text3.insert(tk.END, "═══ 🎯 指标组合建议 ═══\n\n", "title")
                text3.insert(tk.END, "【稳健波段】\n", "subtitle")
                text3.insert(tk.END,
                    "一目均衡 + SuperTrend + Camarilla\n"
                    "大方向 → 动态 S/R → 入场位\n\n", "body")
                text3.insert(tk.END, "【量价过滤】\n", "subtitle")
                text3.insert(tk.END,
                    "VWAP+σ + VW-MACD + TD 序列\n"
                    "机构成本 → 量能确认 → 衰竭反转\n\n", "body")
                text3.insert(tk.END, "【趋势捕捉】\n", "subtitle")
                text3.insert(tk.END,
                    "SuperTrend + TD 序列 + Camarilla\n"
                    "趋势启动 → 趋势衰竭 → 中途波段\n\n", "body")
                text3.insert(tk.END, "【高胜率抄底】\n", "subtitle")
                text3.insert(tk.END,
                    "TD 下跌9 + VWAP-2σ + Camarilla S3\n"
                    "三条件同时满足 = 价低 + 抛尽 + 支撑强\n"
                    "✨ 实战中命中率非常高\n", "body")
                text3.config(state=tk.DISABLED)

                _apply_font(font_size_var.get())

            help_btn = ttk.Button(top_frame, text="❓ 指标说明", command=_show_ichimoku_help)
            help_btn.pack(side=tk.LEFT, padx=(10, 0))

            # ─── 叠加指标 toggle 行 ───
            ind_row = ttk.LabelFrame(win, text="🛠️ 叠加指标 (可多选, 可随时开关重绘)", padding=4)
            ind_row.pack(fill=tk.X, padx=4, pady=(2, 2))

            # 预定义指标列表 (key, 显示名, 默认勾选, 说明)
            INDICATOR_LIST = [
                ("ichimoku", "一目均衡", True, "主图"),
                ("supertrend", "SuperTrend", True, "主图·ATR趋势带"),
                ("vwap_band", "VWAP+σ带", False, "主图·量价通道"),
                ("td_seq", "TD序列", False, "主图·衰竭反转计数"),
                ("camarilla", "Camarilla", False, "主图·动态S/R水平线"),
                ("ma", "MA均线", False, "主图·MA5/10/20/60"),
                ("boll", "BOLL布林", False, "主图·中轨±2σ"),
                ("cci", "🎵五线谱", False, "副图·CCI情绪区间-200~+200"),
            ]
            ind_vars = {}
            for key, label, default, tip in INDICATOR_LIST:
                v = tk.BooleanVar(value=default)
                ind_vars[key] = v
                cb = ttk.Checkbutton(ind_row, text=f"📊 {label}", variable=v,
                                     command=lambda: redraw())
                cb.pack(side=tk.LEFT, padx=6)

            # 图表容器
            chart_inner = ttk.Frame(win)
            chart_inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            status_var = tk.StringVar(value="⏳ 等待加载...")
            ttk.Label(win, textvariable=status_var, anchor=tk.W).pack(fill=tk.X, padx=4)

            # 当前数据缓存
            current_df = None
            current_info = None  # (symbol, name, is_index, period)

            def redraw():
                nonlocal current_df, current_info
                for w in chart_inner.winfo_children():
                    w.destroy()
                sym_name = symbol_var.get()
                period_label = period_combo.get()
                period_key = [k for k, v in PERIOD_LABELS.items() if v == period_label][0]
                if sym_name not in sym_map:
                    messagebox.showwarning("提示", f"无效标的: {sym_name}", parent=win)
                    return
                sym_code, is_index = sym_map[sym_name]
                status_var.set(f"⏳ 加载 {sym_name} {period_label} 数据...")
                win.update()

                df = self._fetch_ichimoku_kline_data(sym_code, period_key, is_index=is_index)
                if df is None or df.empty:
                    status_var.set(f"❌ 无法获取 {sym_name} {period_label} 数据")
                    return
                current_df = df
                current_info = (sym_code, sym_name, is_index, period_key)

                # 提取数组
                opens = df['开盘'].astype(float).values
                closes = df['收盘'].astype(float).values
                highs = df['最高'].astype(float).values
                lows = df['最低'].astype(float).values
                if '成交量' in df.columns:
                    vol = df['成交量'].astype(float).values
                else:
                    vol = np.zeros(len(closes))
                n = len(closes)
                dates = list(range(n))
                trade_dates = df.get('日期', [''] * n)

                # 构建图表 (主图: K线+叠加; 副图1: VW-MACD; 副图2: 成交量)
                fig = Figure(figsize=(14, 11), dpi=100, facecolor='#FAFAFA')
                gs = gridspec.GridSpec(3, 1, figure=fig, height_ratios=[5, 3, 2], hspace=0.06)
                ax_main = fig.add_subplot(gs[0, 0]); ax_main.set_facecolor('#FFFFFF')
                ax_sub1 = fig.add_subplot(gs[1, 0], sharex=ax_main); ax_sub1.set_facecolor('#FFFFFF')
                ax_sub2 = fig.add_subplot(gs[2, 0], sharex=ax_main); ax_sub2.set_facecolor('#FFFFFF')

                # ─── 主图: K 线 ───
                for i in range(n):
                    color = '#D32F2F' if closes[i] >= opens[i] else '#388E3C'
                    body_bottom = min(opens[i], closes[i])
                    body_top = max(opens[i], closes[i])
                    ax_main.bar(i, body_top - body_bottom, bottom=body_bottom,
                               color=color, alpha=0.8, width=0.6)
                    ax_main.plot([i, i], [lows[i], body_bottom], color=color, linewidth=1)
                    ax_main.plot([i, i], [body_top, highs[i]], color=color, linewidth=1)

                # ─── 主图叠加: 复合指标 (全部条件绘制) ───
                x_arr = np.asarray(dates)

                # 📦 闭包 dict: 存所有已计算的指标数据 (hover 时用来算分)
                ind_data = {}

                # 1) 一目均衡 (Ichimoku) — 默认勾选
                if ind_vars["ichimoku"].get():
                    ich = self._calc_ichimoku(highs, lows, closes)
                    ind_data['ich'] = ich
                    self._plot_ichimoku_ax(ax_main, dates, highs, lows, closes)

                # 2) SuperTrend (ATR 趋势带 + 动态 S/R)
                st = None
                if ind_vars["supertrend"].get():
                    st = self._calc_supertrend(highs, lows, closes)
                    ind_data['st'] = st
                    # 上涨 (trend=+1) 画绿色动态支撑线, 下跌 (trend=-1) 画红色压力线
                    mask_up = st['trend_dir'] == 1
                    mask_dn = st['trend_dir'] == -1
                    ax_main.plot(x_arr[mask_up], st['supertrend'][mask_up],
                                 color='#26a69a', linewidth=1.8, label='SuperTrend↑(支撑)', alpha=0.85)
                    ax_main.plot(x_arr[mask_dn], st['supertrend'][mask_dn],
                                 color='#ef5350', linewidth=1.8, label='SuperTrend↓(压力)', alpha=0.85)
                    # 末端加中文标签 (在最后一个有效点)
                    last_i = n - 1
                    # 找最后一个上涨段末端
                    up_mask_end = -1
                    for ii in range(n - 1, -1, -1):
                        if mask_up[ii]:
                            up_mask_end = ii; break
                    if up_mask_end >= 0:
                        ax_main.annotate('↑支撑', xy=(up_mask_end, st['supertrend'][up_mask_end]),
                                         xytext=(6, 8), textcoords='offset points',
                                         fontsize=8, color='#26a69a', fontweight='bold', alpha=0.9)
                    dn_mask_end = -1
                    for ii in range(n - 1, -1, -1):
                        if mask_dn[ii]:
                            dn_mask_end = ii; break
                    if dn_mask_end >= 0:
                        ax_main.annotate('↓压力', xy=(dn_mask_end, st['supertrend'][dn_mask_end]),
                                         xytext=(6, -12), textcoords='offset points',
                                         fontsize=8, color='#ef5350', fontweight='bold', alpha=0.9)

                # 3) VWAP + σ 带
                vwap_band = None
                if ind_vars["vwap_band"].get():
                    vwap_band = self._calc_vwap(opens, highs, lows, closes, vol)
                    ind_data['vwap_band'] = vwap_band
                    ax_main.plot(x_arr, vwap_band['vwap'], color='#ff9800', linewidth=1.4,
                                 label='VWAP', alpha=0.9)
                    ax_main.fill_between(x_arr, vwap_band['lower1'], vwap_band['upper1'],
                                        color='#ffb74d', alpha=0.10, label='VWAP±1σ')
                    ax_main.fill_between(x_arr, vwap_band['lower2'], vwap_band['upper2'],
                                        color='#ff8a65', alpha=0.06, label='VWAP±2σ')

                # 4) TD Sequential (衰竭反转计数 — 数字标在 K 线上)
                td = None
                if ind_vars["td_seq"].get():
                    td = self._calc_td_sequential(closes)
                    ind_data['td'] = td
                    for i in range(n):
                        cnt = td['td_count'][i]
                        if cnt == 0:
                            continue
                        if cnt == 9:
                            # 衰竭信号 — 特别标红/标绿 + 更大字号
                            ax_main.annotate("9", xy=(i, closes[i]), xytext=(i, closes[i] * 1.012),
                                             fontsize=9, fontweight='bold',
                                             ha='center', color='#e53935' if cnt > 0 else '#1e88e5',
                                             arrowprops=dict(arrowstyle='->', lw=0.6,
                                                             color='#e53935' if cnt > 0 else '#1e88e5'))
                        elif abs(cnt) >= 6:
                            # 6-8 计数 — 中等字号
                            ax_main.annotate(str(abs(cnt)), xy=(i, closes[i]),
                                             xytext=(0, 6), textcoords='offset points',
                                             fontsize=7, ha='center',
                                             color='#c62828' if cnt > 0 else '#0d47a1', alpha=0.85)

                # 5) Camarilla Pivot (动态 S/R 水平线)
                cam = None
                if ind_vars["camarilla"].get():
                    cam = self._calc_camarilla_pivot(highs, lows, closes)
                    ind_data['cam'] = cam
                    all_lines = []
                    labels = []
                    # 压力 (上方)
                    for j, r in enumerate(cam['resistances']):
                        all_lines.append(r); labels.append(f"R{j+1}={r:.2f}")
                    # 焦点 pivot
                    all_lines.append(cam['pivot']); labels.append(f"P={cam['pivot']:.2f}")
                    # 支撑 (下方)
                    for j, s in enumerate(cam['supports']):
                        all_lines.append(s); labels.append(f"S{j+1}={s:.2f}")
                    # 只画最靠近价格的 4 条 (减少视觉噪音)
                    last_c = closes[-1]
                    all_lines.sort()
                    # 找 last_c 附近的 4 条
                    idx_near = 0
                    for j, lv in enumerate(all_lines):
                        if lv < last_c:
                            idx_near = j
                        else:
                            break
                    chosen = all_lines[max(0, idx_near - 1):idx_near + 3]
                    for level in chosen:
                        if level > last_c:
                            color, ls, lbl = '#f44336', '--', f'压力 {level:.2f}'
                        elif level < last_c:
                            color, ls, lbl = '#4caf50', '--', f'支撑 {level:.2f}'
                        else:
                            color, ls, lbl = '#ff9800', '-.', f'Pivot {level:.2f}'
                        ax_main.axhline(y=level, color=color, linestyle=ls,
                                        linewidth=1.0, alpha=0.7, label=lbl)
                        # 在线右端加小标签 (只有主图范围内)
                        right_edge = n - 1
                        if level > last_c:
                            ax_main.annotate(f'压 {level:.0f}', xy=(right_edge, level),
                                             xytext=(-3, 5), textcoords='offset points',
                                             fontsize=7, color=color, ha='right', alpha=0.85)
                        elif level < last_c:
                            ax_main.annotate(f'支 {level:.0f}', xy=(right_edge, level),
                                             xytext=(-3, -10), textcoords='offset points',
                                             fontsize=7, color=color, ha='right', alpha=0.85)

                # 6) MA 均线 (MA5/10/20/60)
                if ind_vars["ma"].get():
                    _ma_c = {'ma5':'#ff9800','ma10':'#2196f3','ma20':'#9c27b0','ma60':'#607d8b'}
                    for ma_n, ma_c in [(5,'ma5'),(10,'ma10'),(20,'ma20'),(60,'ma60')]:
                        ma_vals = pd.Series(closes).rolling(ma_n, min_periods=1).mean().values
                        ax_main.plot(x_arr, ma_vals, color=_ma_c[ma_c], linewidth=0.9, alpha=0.8, label=f'MA{ma_n}')
                        ind_data[f'ma{ma_n}'] = ma_vals

                # 7) BOLL 布林带 (中轨 + ±2σ)
                if ind_vars["boll"].get():
                    c_s = pd.Series(closes, dtype=float)
                    mid = c_s.rolling(20, min_periods=1).mean()
                    std = c_s.rolling(20, min_periods=1).std()
                    up = (mid + 2*std).values; dn = (mid - 2*std).values; mid_v = mid.values
                    ax_main.plot(x_arr, mid_v, color='#ff9800', linewidth=0.8, alpha=0.7, label='BOLL中轨')
                    ax_main.plot(x_arr, up, color='#4caf50', linewidth=0.7, alpha=0.6, linestyle='--', label='BOLL上轨')
                    ax_main.plot(x_arr, dn, color='#4caf50', linewidth=0.7, alpha=0.6, linestyle='--', label='BOLL下轨')
                    ax_main.fill_between(x_arr, dn, up, color='#4caf50', alpha=0.07)
                    ind_data['boll_mid'] = mid_v; ind_data['boll_up'] = up; ind_data['boll_dn'] = dn

                # 主图装饰 (动态标题: 根据勾选的指标名)
                active_inds = []
                if ind_vars["ichimoku"].get(): active_inds.append("一目均衡")
                if ind_vars["supertrend"].get(): active_inds.append("SuperTrend")
                if ind_vars["vwap_band"].get(): active_inds.append("VWAP+σ")
                if ind_vars["td_seq"].get(): active_inds.append("TD序列")
                if ind_vars["camarilla"].get(): active_inds.append("Camarilla")
                ax_main.set_title(f"📈 {sym_name} — {period_label} | " + " · ".join(active_inds) + " + VW-MACD",
                                  fontsize=13, fontweight='bold', pad=10, color='#212121')
                ax_main.legend(loc='upper left', fontsize=7, ncol=3,
                               facecolor='#FFFFFF', edgecolor='#CCCCCC')
                ax_main.tick_params(colors='#424242')
                ax_main.grid(True, alpha=0.3)
                ax_main.tick_params(axis="x", labelbottom=False)
                # 初始视图聚焦 K 线区域 (0..n-1), 但允许 pan 到右侧看一目均衡未来预测 (n..n+26)
                ax_main.set_xlim(-1, n)
                # 保存 home 视图 (NavigationToolbar 的 🏠 按钮恢复到此范围)
                ax_main._initial_xlim = (-1, n)
                ax_main._initial_ylim = ax_main.get_ylim()
                # 副图 sharex=ax_main 会自动对齐

                # ─── 📊 图表角落加判别分析文本框 ───
                # 先把 VW-MACD 算出来 (后面要用)
                vw = self._calc_vwmacd(closes, vol)
                try:
                    ich = self._calc_ichimoku(highs, lows, closes)
                    last_tenkan = ich['tenkan_sen'][-1] if not np.isnan(ich['tenkan_sen'][-1]) else closes[-1]
                    last_kijun = ich['kijun_sen'][-1] if not np.isnan(ich['kijun_sen'][-1]) else closes[-1]
                    last_close = closes[-1]
                    cloud_idx = n - 1 + 26
                    if cloud_idx < len(ich['senkou_a']):
                        last_sen_a = ich['senkou_a'][cloud_idx]
                        last_sen_b = ich['senkou_b'][cloud_idx]
                        bull_cloud = bool(last_sen_a >= last_sen_b)
                    else:
                        bull_cloud = True
                        last_sen_a = last_sen_b = np.nan

                    # 1) 一目均衡信号
                    tk_kijun = "转>基" if last_tenkan > last_kijun else "转<基"
                    cloud_label = "红看涨云" if bull_cloud else "绿看跌云"
                    if bull_cloud and last_close > max(last_sen_a, last_sen_b):
                        price_pos = "价在云上 ✅"
                    elif not bull_cloud and last_close < min(last_sen_a, last_sen_b):
                        price_pos = "价在云下 ❌"
                    else:
                        price_pos = "价在云中 ➖"

                    # 云层厚度判断
                    if not (np.isnan(last_sen_a) or np.isnan(last_sen_b)):
                        cloud_thickness = abs(last_sen_a - last_sen_b)
                        cloud_pct = cloud_thickness / last_close * 100
                        if cloud_pct > 4:
                            thick_label = f"云厚 {cloud_pct:.1f}% (支撑强)"
                        elif cloud_pct > 2:
                            thick_label = f"云厚 {cloud_pct:.1f}% (中等)"
                        else:
                            thick_label = f"云薄 {cloud_pct:.1f}% (易突破)"
                    else:
                        thick_label = "云厚 —"

                    # 迟行线动能判断 (chikou 在 x=n-1 位置对应 closes[n-27])
                    try:
                        chikou_now = ich['chikou'][n - 1] if n - 1 < len(ich['chikou']) else np.nan
                        # 迟行线与历史K线的位置关系: 比较 chikou[t] 与 closes[t] 在时间轴上的缠绕程度
                        # 简化: 用最近 20 根 chikou 相对于 closes 的位置
                        lookback = min(30, n)
                        chikou_tail = ich['chikou'][max(26, n-lookback):n]
                        closes_tail = closes[max(0, n-lookback-26):n-26]
                        # 统计 chikou > close 的比例
                        if len(chikou_tail) > 5 and len(closes_tail) > 5:
                            min_len = min(len(chikou_tail), len(closes_tail))
                            chk_above = sum(1 for j in range(min_len) if chikou_tail[j] > closes_tail[j])
                            chk_ratio = chk_above / min_len
                            if chk_ratio > 0.7:
                                chk_label = "迟行强多 🟣↑"
                            elif chk_ratio < 0.3:
                                chk_label = "迟行强空 🟣↓"
                            else:
                                chk_label = "迟行缠绕 🟣〰"
                        else:
                            chk_label = "迟行 —"
                    except Exception:
                        chk_label = "迟行 —"

                    # 2) VW-MACD 信号
                    vw_dif_val = vw['dif'][-1]
                    vw_dea_val = vw['dea'][-1]
                    vw_h_val = vw['macdh'][-1]
                    vr = vw['vol_ratio'][-1]
                    macd_dir = "DIF>DEA" if vw_dif_val > vw_dea_val else "DIF<DEA"
                    vol_flag = "放量" if vr > 1.3 else ("缩量" if vr < 0.7 else "量平")

                    # 3) 综合判断 (4 维打分)
                    score = 0
                    score += 1 if (bull_cloud and last_close > max(last_sen_a, last_sen_b)) else 0
                    score += 1 if (last_tenkan > last_kijun) else 0
                    score += 1 if vw_dif_val > vw_dea_val else 0
                    score += 1 if (vw_dif_val > vw_dea_val and vr > 1.2) else 0  # 量价配合加分

                    if score >= 3:
                        verdict = "🟢 偏多, 可持有"
                    elif score >= 2:
                        verdict = "🟡 中性, 观望"
                    else:
                        verdict = "🔴 偏空, 谨慎"

                    # 组装分析文本 (放进 bbox)
                    analysis_lines = [
                        f"═══ 判别分析 ═══",
                        f"🎯 趋势: {verdict}",
                        f"─── 一目均衡 ───",
                        f"  云: {cloud_label} | {thick_label}",
                        f"  {tk_kijun}  |  {price_pos}",
                        f"  {chk_label}",
                        f"─── VW-MACD ───",
                        f"  {macd_dir}  |  {vol_flag}(量比{vr:.2f})",
                    ]
                    analysis_text = "\n".join(analysis_lines)
                    ax_main.text(0.02, 0.98, analysis_text,
                                transform=ax_main.transAxes,
                                fontsize=8.5, va='top', ha='left',
                                bbox=dict(boxstyle='round,pad=0.4', facecolor='#E3F2FD',
                                          edgecolor='#1565c0', alpha=0.92, linewidth=0.8),
                                linespacing=1.4)
                except Exception:
                    pass

                # ─── 副图1: VW-MACD (固定) ───
                x = np.asarray(dates)
                ax_sub1.plot(x, vw['dif'], label='VW-DIF', linewidth=1.0, color='#1565c0')
                ax_sub1.plot(x, vw['dea'], label='VW-DEA', linewidth=1.0, color='#c62828')
                bar_colors = ['#d32f2f' if v >= 0 else '#388e3c' for v in vw['macdh']]
                ax_sub1.bar(x, vw['macdh'], color=bar_colors, alpha=0.45, width=0.55)
                ax_sub1.axhline(0, color="gray", linewidth=0.6)
                # 量比
                vol_ratio = vw['vol_ratio']
                ax_sub1b = ax_sub1.twinx()
                ax_sub1b.plot(x, vol_ratio, color='#ff9800', linewidth=0.7, alpha=0.5, linestyle=':', label='量比')
                ax_sub1b.axhline(1.5, color='#ff9800', linestyle='--', linewidth=0.5, alpha=0.5)
                ax_sub1b.axhline(0.7, color='#ff9800', linestyle='--', linewidth=0.5, alpha=0.5)
                ax_sub1b.set_ylabel('量比', fontsize=8, color='#ff9800')
                ax_sub1b.tick_params(axis='y', labelcolor='#ff9800', labelsize=8)
                ax_sub1b.set_ylim(0, max(3.0, np.nanmax(vol_ratio) * 1.1))
                ax_sub1.set_ylabel('VW-MACD', fontsize=9, color='#424242')
                ax_sub1.tick_params(colors='#424242')
                ax_sub1.legend(loc='upper left', fontsize=7,
                               facecolor='#FFFFFF', edgecolor='#CCCCCC')
                ax_sub1b.legend(loc='upper right', fontsize=7,
                                facecolor='#FFFFFF', edgecolor='#CCCCCC')
                ax_sub1.grid(True, alpha=0.3)

                # ─── 副图2: 成交量 (默认) 或 🎵情绪五线谱 CCI ───
                if ind_vars['cci'].get():
                    # 🎵 情绪五线谱 CCI(14) + 5 条水平参考线
                    tp = (highs + lows + closes) / 3
                    sma_tp = pd.Series(tp).rolling(14, min_periods=1).mean().values
                    md_vals = np.zeros(n)
                    for _i in range(n):
                        _s = max(0, _i-13); md_vals[_i] = np.mean(np.abs(tp[_s:_i+1] - sma_tp[_i]))
                    cci = (tp - sma_tp) / (0.015 * np.maximum(md_vals, 1e-8))
                    cci = np.nan_to_num(cci, nan=0.0)
                    ax_sub2.plot(x, cci, color='#7b1fa2', linewidth=0.9, label='CCI(14)')
                    _bands = [(-200, '#00796b', '冰点'), (-100, '#388e3c', '超卖'),
                              (0,    '#999999', '中性'),
                              (100,  '#f4511e', '超买'), (200, '#c62828', '高潮')]
                    for _lv, _c, _lb in _bands:
                        ax_sub2.axhline(y=_lv, color=_c, linewidth=0.6, linestyle='--', alpha=0.8)
                        ax_sub2.text(n-1, _lv, f'  {_lv}({_lb})', va='center', fontsize=6, color=_c)
                    ax_sub2.set_ylabel('CCI', color='#7b1fa2', fontsize=9)
                    ax_sub2.tick_params(axis='y', colors='#7b1fa2')
                    _cci_lo = min(-250, float(np.min(cci)) - 30)
                    _cci_hi = max(250,  float(np.max(cci)) + 30)
                    ax_sub2.set_ylim(_cci_lo, _cci_hi)
                    # 成交量半透明叠加右轴
                    vol_colors2 = ['#d32f2f' if closes[i] >= opens[i] else '#2e7d32' for i in range(n)]
                    ax_sub2_r = ax_sub2.twinx()
                    ax_sub2_r.bar(x, vol, color=vol_colors2, width=0.55, alpha=0.2)
                    ax_sub2_r.tick_params(axis='y', colors='#424242', labelsize=7)
                    ax_sub2_r.set_ylabel('VOL', color='#424242', fontsize=8)
                else:
                    def _ma_series(s, n): return pd.Series(s).rolling(n, min_periods=1).mean().values
                    vol_colors = ['#d32f2f' if closes[i] >= opens[i] else '#2e7d32' for i in range(n)]
                    vol_ma5 = _ma_series(vol, 5)
                    ax_sub2.bar(x, vol, color=vol_colors, width=0.55, alpha=0.7)
                    ax_sub2.plot(x, vol_ma5, color='#ff9800', linewidth=0.8, label='VOL_MA5')
                    ax_sub2.set_ylabel('量', fontsize=9, color='#424242')
                    ax_sub2.tick_params(colors='#424242')
                ax_sub2.legend(loc='upper left', fontsize=7,
                               facecolor='#FFFFFF', edgecolor='#CCCCCC')
                ax_sub2.grid(True, alpha=0.3)

                # 日期轴 (副图2 显示)
                tick_idx = np.linspace(0, n-1, min(12, n), dtype=int)
                ax_sub2.set_xticks(tick_idx)
                ax_sub2.set_xticklabels([str(trade_dates[i])[-10:] if i < len(trade_dates) else '' for i in tick_idx],
                                        rotation=30, fontsize=7)
                ax_sub1.tick_params(axis='x', labelbottom=False)
                ax_main.tick_params(axis='x', labelbottom=False)

                fig.tight_layout()
                canvas = FigureCanvasTkAgg(fig, chart_inner)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                # 🎯 加 matplotlib 自带导航工具条 (平移 ↔ / 缩放 🔍 / 重置 🏠 / 保存 📷)
                try:
                    from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
                    _tb = NavigationToolbar2Tk(canvas, chart_inner, pack_toolbar=False)
                    _tb.update()
                    _tb.pack(side=tk.TOP, fill=tk.X, before=canvas.get_tk_widget())
                    # 隐藏不需要的按钮, 留下 Pan / Zoom / Home / Save
                    for _btn in _tb.winfo_children():
                        _txt = str(_btn.cget('text'))
                        if _txt in ('Subplots', 'Customize', 'A'):
                            _btn.pack_forget()
                except Exception as _etb:
                    pass
                # 双击图表 → 弹出指标说明 (复用 _show_ichimoku_help)
                canvas.mpl_connect("button_press_event",
                    lambda e: _show_ichimoku_help() if e.dblclick else None)

                # ─── 🖱️ 鼠标 hover → 综合评分 tooltip (用 mixin 通用方法, 加一目均衡复合指标分) ───
                def _ichimoku_extra_scores(idx):
                    """extra_info_fn: 附加一目均衡复合指标评分 (ind_data/ind_vars 已在闭包中)。"""
                    extra = []
                    if ind_vars["ichimoku"].get() and 'ich' in ind_data:
                        ich = ind_data['ich']
                        cloud_idx = min(idx + 26, len(ich['senkou_a']) - 1)
                        s_a = ich['senkou_a'][cloud_idx]
                        s_b = ich['senkou_b'][cloud_idx]
                        tenkan = ich['tenkan_sen'][idx]
                        kijun = ich['kijun_sen'][idx]
                        close = closes[idx]
                        cloud_score = 0
                        if not (np.isnan(s_a) or np.isnan(s_b)):
                            top_cloud = max(s_a, s_b); bot_cloud = min(s_a, s_b)
                            if close > top_cloud: cloud_score = 100
                            elif close < bot_cloud: cloud_score = -100
                        tk_score = 50 if (not np.isnan(tenkan) and not np.isnan(kijun) and tenkan > kijun) else -50
                        extra.append(("一目均衡", cloud_score * 0.6 + tk_score * 0.4, 2.0,
                                     f"价在{'云上✅' if cloud_score>50 else ('云下❌' if cloud_score<-50 else '云中')}"))
                    if ind_vars["supertrend"].get() and 'st' in ind_data:
                        st = ind_data['st']; td = st['trend_dir'][idx]
                        extra.append(("SuperTrend", 100 if td == 1 else -100, 1.5,
                                     "↑支撑" if td == 1 else "↓压力"))
                    if ind_vars["vwap_band"].get() and 'vwap_band' in ind_data:
                        vb = ind_data['vwap_band']
                        v = vb['vwap'][idx]; u2 = vb['upper2'][idx]; l2 = vb['lower2'][idx]
                        if not np.isnan(v):
                            if closes[idx] > u2: vs, vd = 80, "超买"
                            elif closes[idx] < l2: vs, vd = -80, "超跌"
                            elif closes[idx] > v: vs, vd = 40, "VWAP上"
                            else: vs, vd = -40, "VWAP下"
                        else: vs, vd = 0, "未成型"
                        extra.append(("VWAP+σ", vs, 1.0, vd))
                    if ind_vars["td_seq"].get() and 'td' in ind_data:
                        tdc = ind_data['td']['td_count'][idx]
                        extra.append(("TD序列", tdc * 8 if abs(tdc) < 9 else -tdc * 5, 0.5,
                                     f"setup {tdc:+d}"))
                    if ind_vars["camarilla"].get() and 'cam' in ind_data:
                        cam_data = ind_data['cam']
                        all_levs = cam_data['resistances'] + [cam_data['pivot']] + cam_data['supports']
                        nearest = min(all_levs, key=lambda lv: abs(lv - closes[idx]))
                        cam_s = 60 - abs(closes[idx] - nearest) / closes[idx] * 500
                        extra.append(("Camarilla", cam_s, 0.5, f"近位{nearest:.2f}"))
                    # 用 extra 自己算加权总分
                    total_w = sum(w for _, _, w, _ in extra)
                    if total_w > 0:
                        avg_raw = sum(s * w for _, s, w, _ in extra) / total_w
                        extra_total = int((avg_raw + 100) / 2)
                        return extra, extra_total
                    return extra, None

                self._install_score_hover(
                    canvas, ax_main, opens, highs, lows, closes, vol,
                    trade_dates=trade_dates, extra_info_fn=_ichimoku_extra_scores)

                # 状态: 当前信号简要
                try:
                    ich = self._calc_ichimoku(highs, lows, closes)
                    last_tenkan = ich['tenkan_sen'][-1] if not np.isnan(ich['tenkan_sen'][-1]) else closes[-1]
                    last_kijun = ich['kijun_sen'][-1] if not np.isnan(ich['kijun_sen'][-1]) else closes[-1]
                    last_close = closes[-1]
                    # 云的最后边界 (先取偏移 26 位的位置)
                    cloud_idx = n - 1 + 26  # 偏移后的索引
                    if cloud_idx < len(ich['senkou_a']):
                        last_sen_a = ich['senkou_a'][cloud_idx]
                        last_sen_b = ich['senkou_b'][cloud_idx]
                        cloud_type = "🟢看涨云" if last_sen_a >= last_sen_b else "🔴看跌云"
                    else:
                        cloud_type = "云数据不足"

                    # 转换线 vs 基准线
                    tk_kj_cross = "转>基 (金叉区)" if last_tenkan > last_kijun else "转<基 (死叉区)"
                    price_pos = "价在云上 ✅" if (not np.isnan(last_sen_a) and not np.isnan(last_sen_b)
                            and last_close > max(last_sen_a, last_sen_b)) else \
                               ("价在云下 ❌" if (not np.isnan(last_sen_a) and not np.isnan(last_sen_b)
                            and last_close < min(last_sen_a, last_sen_b)) else "价在云中")

                    # VW-MACD 最新
                    vw_dif_val = vw['dif'][-1]
                    vw_dea_val = vw['dea'][-1]
                    vw_signal = "DIF>DEA ✅" if vw_dif_val > vw_dea_val else "DIF<DEA ❌"
                    vr = vw['vol_ratio'][-1]
                    vol_desc = f"量比{vr:.2f}"

                    status_var.set(
                        f"📊 {sym_name} | 云: {cloud_type} | {tk_kj_cross} | {price_pos} | "
                        f"VW-MACD: {vw_signal} | {vol_desc}")
                except Exception as _e:
                    status_var.set(f"📊 {sym_name} (信号计算跳过: {_e})")

            # 事件绑定
            period_combo.bind("<<ComboboxSelected>>", lambda e: redraw())
            sym_combo.bind("<<ComboboxSelected>>", lambda e: redraw())
            win.after(100, redraw)

        except Exception as e:
            print(f"[📈一目均衡❌] {e}", flush=True)
            _tb.print_exc()
            messagebox.showerror("错误", f"打开一目均衡K线图失败: {e}", parent=getattr(self, 'root', None))

    # ═══════════════════════════════════════════════════════════════
    # 📊 ETF 联动分析弹窗 — 三列: ETF列表 → 持仓股 → K线图
    # ═══════════════════════════════════════════════════════════════
    def _show_etf_link_dialog(self):
        """📊 ETF 联动分析: 左列 ETF 强弱排行 + 中列持仓股 + 右列 K 线 Notebook"""
        import traceback as _tb_etf
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            import numpy as np
            import pandas as pd

            win = self._safe_toplevel(self.root)
            win.title("📊 ETF 联动分析 · ETF → 持仓股 → K线")
            win.geometry("1560x960")
            try: win.state("zoomed")
            except:
                try: win.attributes("-zoomed", True)
                except: pass

            # ── 1. 主流 ETF 列表 (40只, 覆盖宽基+行业+跨境) ──
            MAINSTREAM_ETFS = [
                # ── 宽基 ──
                ("510300.SH", "沪深300"), ("510500.SH", "中证500"), ("159915.SZ", "创业板"),
                ("588000.SH", "科创50"), ("510050.SH", "上证50"), ("512100.SH", "中证1000"),
                ("512980.SH", "中证红利"), ("510880.SH", "红利ETF"),
                # ── 科技成长 ──
                ("512480.SH", "半导体"), ("159995.SZ", "芯片ETF"), ("159875.SZ", "新能源"),
                ("515030.SH", "新能源车"), ("515790.SH", "光伏ETF"), ("512660.SH", "军工ETF"),
                ("159887.SZ", "人工智能"), ("159280.SZ", "大数据ETF"),
                # ── 消费医药 ──
                ("159928.SZ", "消费ETF"), ("512690.SH", "酒ETF"), ("512010.SH", "医药ETF"),
                ("515120.SH", "创新药"), ("159929.SZ", "医药50"),
                # ── 金融周期 ──
                ("512880.SH", "证券ETF"), ("512000.SH", "银行ETF"), ("515220.SH", "煤炭ETF"),
                ("512400.SH", "有色ETF"), ("512200.SH", "房地产"), ("510440.SH", "周期ETF"),
                # ── 港股通 ──
                ("513180.SH", "恒生科技"), ("513050.SH", "中概互联"), ("513070.SH", "港股通医药"),
                ("513130.SH", "港股通科技"),
                # ── 跨境QDII ──
                ("513100.SH", "纳指100"), ("513500.SH", "标普500"), ("513520.SH", "日经225"),
                ("513080.SH", "法国CAC"), ("513660.SH", "恒生指数"), ("513580.SH", "德国DAX"),
                # ── 其他主题 ──
                ("512890.SH", "红利低波"), ("515900.SH", "机器人ETF"), ("515210.SH", "钢铁ETF"),
                ("512760.SH", "芯片50"), ("159866.SZ", "算力ETF"),
            ]

            # ── 2. ETF → 核心持仓股映射 (硬编码 Top 5-8, 定期可更新) ──
            # 格式: [(sina_code, stock_name), ...]
            ETF_HOLDERS = {
                # ── 宽基 ──
                "沪深300": [("sh600519","贵州茅台"),("sh601318","中国平安"),("sh600036","招商银行"),
                            ("sh601398","工商银行"),("sh600900","长江电力"),("sh601012","隆基绿能"),
                            ("sz300750","宁德时代"),("sz002594","比亚迪")],
                "中证500": [("sh601872","招商轮船"),("sh600741","华域汽车"),("sz002415","海康威视"),
                            ("sz002230","科大讯飞"),("sh600309","万华化学"),("sz000568","泸州老窖")],
                "创业板": [("sz300750","宁德时代"),("sz300059","东方财富"),("sz300760","迈瑞医疗"),
                           ("sz300015","爱尔眼科"),("sz300124","汇川技术"),("sz300014","亿纬锂能")],
                "科创50": [("sh688981","中芯国际"),("sh688111","金山办公"),("sh688012","中微公司"),
                           ("sh688271","联影医疗"),("sh688008","澜起科技"),("sh688041","海光信息")],
                "上证50": [("sh600519","贵州茅台"),("sh601318","中国平安"),("sh600036","招商银行"),
                           ("sh601398","工商银行"),("sh601288","农业银行"),("sh600028","中国石化")],
                "中证1000": [("sh601872","招商轮船"),("sh603195","公牛集团"),("sz002812","恩捷股份"),
                            ("sz002371","北方华创"),("sz002049","紫光国微"),("sz300124","汇川技术")],
                "中证红利": [("sh601398","工商银行"),("sh600036","招商银行"),("sh601985","中国核电"),
                            ("sh601088","中国神华"),("sh600028","中国石化"),("sh601225","陕西煤业")],
                "红利ETF": [("sh601398","工商银行"),("sh600036","招商银行"),("sh601288","农业银行"),
                            ("sh600028","中国石化"),("sh601985","中国核电"),("sh601088","中国神华")],
                "红利低波": [("sh601398","工商银行"),("sh601288","农业银行"),("sh601985","中国核电"),
                            ("sh600036","招商银行"),("sh601318","中国平安"),("sh601088","中国神华")],
                # ── 科技成长 ──
                "半导体": [("sh688981","中芯国际"),("sz002371","北方华创"),("sz002049","紫光国微"),
                            ("sh688041","海光信息"),("sz300782","卓胜微"),("sh603986","兆易创新")],
                "芯片ETF": [("sh688981","中芯国际"),("sz002371","北方华创"),("sz002049","紫光国微"),
                            ("sh688041","海光信息"),("sz300782","卓胜微"),("sh603986","兆易创新")],
                "新能源": [("sz300750","宁德时代"),("sz002594","比亚迪"),("sz300014","亿纬锂能"),
                           ("sz002460","赣锋锂业"),("sh600104","上汽集团"),("sz002812","恩捷股份")],
                "新能源车": [("sz002594","比亚迪"),("sz300750","宁德时代"),("sh601127","赛力斯"),
                             ("sz300014","亿纬锂能"),("sz002812","恩捷股份"),("sh600104","上汽集团")],
                "光伏ETF": [("sh601012","隆基绿能"),("sh600438","通威股份"),("sz300274","阳光电源"),
                            ("sz002456","欧菲光"),("sh601899","紫金矿业"),("sz300750","宁德时代")],
                "军工ETF": [("sh600760","中航沈飞"),("sz000768","中航西飞"),("sh600862","中航高科"),
                            ("sz300034","钢研高纳"),("sh600372","中航机载"),("sz002179","中航光电")],
                "人工智能": [("sz002230","科大讯飞"),("sh688111","金山办公"),("sz300750","宁德时代"),
                            ("sh688041","海光信息"),("sz300059","东方财富"),("sh688981","中芯国际")],
                "大数据ETF": [("sz300059","东方财富"),("sz002230","科大讯飞"),("sh688111","金山办公"),
                              ("sh603881","数据港"),("sh600588","用友网络"),("sz300454","深信服")],
                "机器人ETF": [("sz300124","汇川技术"),("sh600031","三一重工"),("sz002747","埃斯顿"),
                              ("sz300693","盛弘股份"),("sh603416","信捷电气"),("sh688271","联影医疗")],
                "算力ETF": [("sh688981","中芯国际"),("sh688041","海光信息"),("sh688111","金山办公"),
                            ("sz002230","科大讯飞"),("sz300059","东方财富"),("sh600745","闻泰科技")],
                "芯片50": [("sh688981","中芯国际"),("sz002371","北方华创"),("sz002049","紫光国微"),
                           ("sh688041","海光信息"),("sz300782","卓胜微"),("sh603986","兆易创新")],
                # ── 消费医药 ──
                "消费ETF": [("sh600519","贵州茅台"),("sz000858","五粮液"),("sz000568","泸州老窖"),
                            ("sh600809","山西汾酒"),("sz002714","牧原股份"),("sz002594","比亚迪")],
                "酒ETF": [("sh600519","贵州茅台"),("sz000858","五粮液"),("sz000568","泸州老窖"),
                          ("sh600809","山西汾酒"),("sh603589","口子窖"),("sz000799","酒鬼酒")],
                "医药ETF": [("sz300760","迈瑞医疗"),("sh600276","恒瑞医药"),("sz300015","爱尔眼科"),
                            ("sh600196","复星医药"),("sz000538","云南白药"),("sz002007","华兰生物")],
                "创新药": [("sh600276","恒瑞医药"),("sz300760","迈瑞医疗"),("sz002007","华兰生物"),
                          ("sh600196","复星医药"),("sz300015","爱尔眼科"),("sh603259","药明康德")],
                "医药50": [("sz300760","迈瑞医疗"),("sh600276","恒瑞医药"),("sz300015","爱尔眼科"),
                          ("sh600196","复星医药"),("sz000538","云南白药"),("sz002007","华兰生物")],
                # ── 金融周期 ──
                "证券ETF": [("sh601211","国泰君安"),("sh600999","招商证券"),("sh601788","光大证券"),
                            ("sz000776","广发证券"),("sz002736","国信证券"),("sh600109","国金证券")],
                "银行ETF": [("sh601398","工商银行"),("sh600036","招商银行"),("sh601288","农业银行"),
                            ("sh601939","建设银行"),("sh601166","兴业银行"),("sh600016","民生银行")],
                "煤炭ETF": [("sh601088","中国神华"),("sh601225","陕西煤业"),("sh600508","上海能源"),
                            ("sh600188","兖矿能源"),("sz000933","神火股份"),("sh601699","潞安环能")],
                "有色ETF": [("sh601899","紫金矿业"),("sz000630","铜陵有色"),("sz000807","云铝股份"),
                            ("sh601600","中国铝业"),("sz002460","赣锋锂业"),("sz300750","宁德时代")],
                "房地产": [("sh600048","保利发展"),("sh600340","华夏幸福"),("sz001979","招商蛇口"),
                          ("sz000002","万科A"),("sh601155","新城控股"),("sh600036","招商银行")],
                "周期ETF": [("sh601088","中国神华"),("sh601899","紫金矿业"),("sh601600","中国铝业"),
                            ("sh600028","中国石化"),("sh601225","陕西煤业"),("sz000858","五粮液")],
                "钢铁ETF": [("sh600019","宝钢股份"),("sh601003","柳钢股份"),("sz000708","中信特钢"),
                          ("sh600282","南钢股份"),("sz000717","韶钢松山"),("sh600507","方大特钢")],
                # ── 港股通 ──
                "恒生科技": [("hk00700","腾讯控股"),("hk03690","美团-W"),("hk09988","阿里巴巴-W"),
                             ("hk09888","百度集团-W"),("hk03888","金山软件"),("hk01024","快手-W")],
                "中概互联": [("hk09988","阿里巴巴-W"),("hk00700","腾讯控股"),("hk03690","美团-W"),
                             ("hk09888","百度集团-W"),("hk09618","京东集团-SW"),("hk01024","快手-W")],
                "港股通医药": [("hk0005","汇丰控股"),("hk00700","腾讯控股"),("hk03690","美团-W"),
                               ("hk0017","新世界发展"),("hk0177","新世界中国"),("hk09988","阿里巴巴-W")],
                "港股通科技": [("hk00700","腾讯控股"),("hk09988","阿里巴巴-W"),("hk03690","美团-W"),
                               ("hk09888","百度集团-W"),("hk01024","快手-W"),("hk03888","金山软件")],
                "恒生指数": [("hk00700","腾讯控股"),("hk0005","汇丰控股"),("hk03690","美团-W"),
                             ("hk09988","阿里巴巴-W"),("hk0016","新鸿基地产"),("hk0011","恒生银行")],
                # ── 跨境QDII ──
                "纳指100": [("usAAPL","苹果"),("usMSFT","微软"),("usNVDA","英伟达"),
                            ("usGOOGL","谷歌"),("usAMZN","亚马逊"),("usMETA","Meta")],
                "标普500": [("usAAPL","苹果"),("usMSFT","微软"),("usNVDA","英伟达"),
                            ("usAMZN","亚马逊"),("usGOOGL","谷歌"),("usTSLA","特斯拉")],
                "日经225": [("jp7203","丰田汽车"),("jp6758","索尼集团"),("jp6594","日本发那科"),
                            ("jp8306","东京海上"),("jp4063","新日铁住金")],
                "法国CAC": [("frAC","安盛集团"),("frAI","空中客车"),("frBNP","法国巴黎银行"),
                            ("frFP","标致汽车"),("frGLE","欧莱雅"),("frOR","威立雅")],
                "德国DAX": [("deDAI","戴姆勒奔驰"),("deBMW","宝马集团"),("deVOW3","大众汽车"),
                            ("deSIE","西门子"),("deSAP","SAP"),("deALV","阿迪达斯")],
            }

            # ── 3. tushare token (复用 ETF 强弱的 tushare 初始化) ──
            import time as _time_etf
            import tushare as ts
            try:
                from utils.config import TS_DEFAULT_TOKEN
                if not getattr(self, "_ts_pro_init", False):
                    ts.set_token(TS_DEFAULT_TOKEN)
                    self._ts_pro = ts.pro_api()
                    self._ts_pro_init = True
            except Exception:
                pass

            # ── 4. 顶部工具栏 ──
            top = ttk.Frame(win, padding=6); top.pack(fill=tk.X)
            ttk.Label(top, text="📊 ETF 联动分析", font=("", 12, "bold"), foreground="#1565C0").pack(side=tk.LEFT)
            ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
            status_var_etf = tk.StringVar(value="⏳ 加载 ETF 涨跌幅...")
            ttk.Label(top, textvariable=status_var_etf, foreground="#666").pack(side=tk.LEFT)
            refresh_etf = ttk.Button(top, text="🔄 刷新", width=8); refresh_etf.pack(side=tk.RIGHT, padx=4)

            # ── 5. 三列 PanedWindow ──
            pw = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
            pw.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

            # ══════════ 左列: ETF Treeview ══════════
            left_frame = ttk.Frame(pw)
            pw.add(left_frame, weight=3)
            ttk.Label(left_frame, text="📊 ETF 板块 (点击选中, 双击联动)",
                      font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(4, 2))
            etf_tree_frame = ttk.Frame(left_frame)
            etf_tree_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
            etf_cols = ("code", "name", "r0", "r3", "r5", "r20", "score")
            etf_tree = ttk.Treeview(etf_tree_frame, columns=etf_cols, show="headings", height=30)
            for col, txt, w in [("code","代码",90),("name","ETF名称",100),
                                ("r0","当日%",52),("r3","3日%",52),("r5","5日%",52),
                                ("r20","20日%",58),("score","得分",52)]:
                etf_tree.heading(col, text=txt)
                etf_tree.column(col, width=w, anchor="center" if col!="name" else "w", stretch=False)
            vs1 = ttk.Scrollbar(etf_tree_frame, orient=tk.VERTICAL, command=etf_tree.yview)
            etf_tree.configure(yscrollcommand=vs1.set)
            etf_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            vs1.pack(side=tk.RIGHT, fill=tk.Y)
            # 红涨绿跌 tag
            etf_tree.tag_configure("up", foreground="#C62828", font=("", 10, "bold"))
            etf_tree.tag_configure("dn", foreground="#2E7D32", font=("", 10, "bold"))
            etf_tree.tag_configure("top", background="#FFEBEE")
            etf_tree.tag_configure("bot", background="#E8F5E9")

            # ══════════ 中列: 持仓股 Treeview ══════════
            mid_frame = ttk.Frame(pw)
            pw.add(mid_frame, weight=3)
            ttk.Label(mid_frame, text="📦 核心持仓股 (双击联动K线)",
                      font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(4, 2))
            hold_tree_frame = ttk.Frame(mid_frame)
            hold_tree_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
            hold_cols = ("code", "name", "r5", "r20", "reason")
            hold_tree = ttk.Treeview(hold_tree_frame, columns=hold_cols, show="headings", height=30)
            for col, txt, w in [("code","代码",78),("name","股票名称",92),
                                ("r5","5日%",50),("r20","20日%",54),("reason","逻辑/原因",180)]:
                hold_tree.heading(col, text=txt)
                hold_tree.column(col, width=w, anchor="center" if col!="reason" and col!="name" else "w", stretch=False)
            vs2 = ttk.Scrollbar(hold_tree_frame, orient=tk.VERTICAL, command=hold_tree.yview)
            hold_tree.configure(yscrollcommand=vs2.set)
            hold_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            vs2.pack(side=tk.RIGHT, fill=tk.Y)
            hold_tree.tag_configure("up", foreground="#C62828", font=("", 10, "bold"))
            hold_tree.tag_configure("dn", foreground="#2E7D32", font=("", 10, "bold"))

            # ══════════ 右列: Notebook 3 tab K线 + 指标工具栏 ══════════
            right_frame = ttk.Frame(pw)
            pw.add(right_frame, weight=5)

            # ── 指标工具栏 (Notebook 上面) ──
            right_tool = ttk.Frame(right_frame); right_tool.pack(fill=tk.X, padx=4, pady=(4, 0))
            ttk.Label(right_tool, text="📐 指标:", font=("",9,"bold")).pack(side=tk.LEFT)
            ma_chk_vars = {}
            for ma, label in [("ma5","MA5"),("ma10","MA10"),("ma20","MA20"),("ma60","MA60")]:
                v = tk.BooleanVar(value=(ma in ("ma5","ma10","ma20")))
                ma_chk_vars[ma] = v
                ttk.Checkbutton(right_tool, text=label, variable=v).pack(side=tk.LEFT, padx=1)
            ttk.Separator(right_tool, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
            chk_sr = tk.BooleanVar(value=True)
            ttk.Checkbutton(right_tool, text="支撑压力", variable=chk_sr).pack(side=tk.LEFT, padx=1)
            chk_sig = tk.BooleanVar(value=True)
            ttk.Checkbutton(right_tool, text="买卖点", variable=chk_sig).pack(side=tk.LEFT, padx=1)
            ttk.Separator(right_tool, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
            redraw_etf = ttk.Button(right_tool, text="🔄重绘", width=7)
            redraw_etf.pack(side=tk.LEFT, padx=2)

            # Notebook
            nb = ttk.Notebook(right_frame); nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

            # tab1: 日K线 (蜡烛+MA+指标)
            tab_kline = ttk.Frame(nb); nb.add(tab_kline, text="📈 日K线")
            fig1 = Figure(figsize=(7, 7), dpi=100); ax1 = fig1.add_subplot(111)
            cv1 = FigureCanvasTkAgg(fig1, master=tab_kline); cv1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # tab2: K线蜡烛 (简洁版, 也带支撑压力)
            tab_candle = ttk.Frame(nb); nb.add(tab_candle, text="🕯️ 蜡烛")
            fig2 = Figure(figsize=(7, 7), dpi=100); ax2 = fig2.add_subplot(111)
            cv2 = FigureCanvasTkAgg(fig2, master=tab_candle); cv2.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # tab3: 一目均衡
            tab_ichi = ttk.Frame(nb); nb.add(tab_ichi, text="📊 一目均衡")
            fig3 = Figure(figsize=(7, 7), dpi=100); ax3 = fig3.add_subplot(111)
            cv3 = FigureCanvasTkAgg(fig3, master=tab_ichi); cv3.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # ── tab4: 概要 (公司简介 + 基本数据) ──
            tab_summary = ttk.Frame(nb); nb.add(tab_summary, text="📋 概要")
            sum_canvas = tk.Canvas(tab_summary); sum_scroll = ttk.Scrollbar(tab_summary, orient=tk.VERTICAL, command=sum_canvas.yview)
            sum_inner = ttk.Frame(sum_canvas); sum_inner.bind("<Configure>", lambda e: sum_canvas.configure(scrollregion=sum_canvas.bbox("all")))
            sum_canvas.create_window((0,0), window=sum_inner, anchor="nw"); sum_canvas.configure(yscrollcommand=sum_scroll.set)
            sum_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sum_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            summary_text = tk.Text(sum_inner, wrap="word", font=("PingFang SC", 10), height=25, bg="#FAFAFA")
            summary_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            summary_text.insert("1.0", "⏳ 选中左侧持仓股后显示公司概要...\n\n数据源: tushare stock_basic + daily_basic + 新浪财经")
            summary_text.config(state="disabled")

            # ── tab5: 情绪 (资金流 + 北向 + 龙虎榜) ──
            tab_sent = ttk.Frame(nb); nb.add(tab_sent, text="🔥 情绪")
            sent_canvas = tk.Canvas(tab_sent); sent_scroll = ttk.Scrollbar(tab_sent, orient=tk.VERTICAL, command=sent_canvas.yview)
            sent_inner = ttk.Frame(sent_canvas); sent_inner.bind("<Configure>", lambda e: sent_canvas.configure(scrollregion=sent_canvas.bbox("all")))
            sent_canvas.create_window((0,0), window=sent_inner, anchor="nw"); sent_canvas.configure(yscrollcommand=sent_scroll.set)
            sent_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sent_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            sent_text = tk.Text(sent_inner, wrap="word", font=("PingFang SC", 10), height=25, bg="#FAFAFA")
            sent_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            sent_text.insert("1.0", "⏳ 选中左侧持仓股后显示资金情绪...\n\n数据源: tushare moneyflow + hsgt + margin + top_list")
            sent_text.config(state="disabled")

            # ── tab6: 逻辑股评 (SQLite DB + CRUD + 导入) ──
            import sqlite3 as _sql3
            _LOGIC_DB = "/Users/faronpan/Agent/stockyidong_project/data/stock_analysis.db"
            # 建表 (如果不存在)
            try:
                _conn_init = _sql3.connect(_LOGIC_DB)
                _cur_init = _conn_init.cursor()
                _cur_init.execute("""CREATE TABLE IF NOT EXISTS logic_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    review_type TEXT DEFAULT '逻辑',
                    content TEXT NOT NULL,
                    author TEXT DEFAULT '我',
                    source TEXT DEFAULT '手动',
                    article_title TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    updated_at TEXT DEFAULT (datetime('now','localtime'))
                )""")
                _cur_init.execute("""CREATE TABLE IF NOT EXISTS logic_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source TEXT DEFAULT '本地文件',
                    file_path TEXT,
                    content TEXT,
                    matching_stocks TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                )""")
                _conn_init.commit(); _conn_init.close()
            except Exception as _e_db:
                print(f"[📊ETF联动❌DB初始化] {_e_db}", flush=True)

            tab_logic = ttk.Frame(nb); nb.add(tab_logic, text="💡 逻辑股评")
            # 工具栏
            logic_tool = ttk.Frame(tab_logic); logic_tool.pack(fill=tk.X, padx=4, pady=(4, 2))
            ttk.Label(logic_tool, text="当前股票:").pack(side=tk.LEFT)
            logic_stock_var = tk.StringVar(value="未选中")
            ttk.Label(logic_tool, textvariable=logic_stock_var, foreground="#1565C0", font=("", 10, "bold")).pack(side=tk.LEFT, padx=(0, 8))
            # 先占位创建按钮, 后面 config(command=...) 绑回调
            btn_logic_add = ttk.Button(logic_tool, text="➕新增", width=7); btn_logic_add.pack(side=tk.LEFT, padx=1)
            btn_logic_edit = ttk.Button(logic_tool, text="✏️编辑", width=7); btn_logic_edit.pack(side=tk.LEFT, padx=1)
            btn_logic_del = ttk.Button(logic_tool, text="🗑️删除", width=7); btn_logic_del.pack(side=tk.LEFT, padx=1)
            ttk.Separator(logic_tool, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
            btn_logic_import = ttk.Button(logic_tool, text="📥导入文章", width=10); btn_logic_import.pack(side=tk.LEFT, padx=1)
            btn_logic_refresh = ttk.Button(logic_tool, text="🔄刷新", width=7); btn_logic_refresh.pack(side=tk.LEFT, padx=1)

            # Treeview
            logic_cols = ("id", "type", "content", "author", "source", "time")
            logic_tree_frame = ttk.Frame(tab_logic); logic_tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
            logic_tree = ttk.Treeview(logic_tree_frame, columns=logic_cols, show="headings", height=10)
            for col, txt, w in [("id","#",40),("type","类型",60),("content","内容/逻辑",380),
                                ("author","作者",55),("source","来源",75),("time","时间",110)]:
                logic_tree.heading(col, text=txt)
                logic_tree.column(col, width=w, anchor="w", stretch=False)
            log_vs = ttk.Scrollbar(logic_tree_frame, orient=tk.VERTICAL, command=logic_tree.yview)
            logic_tree.configure(yscrollcommand=log_vs.set)
            logic_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            log_vs.pack(side=tk.RIGHT, fill=tk.Y)
            logic_tree.tag_configure("logic", background="#E8F5E9")
            logic_tree.tag_configure("comment", background="#E3F2FD")
            logic_tree.tag_configure("article", background="#FFF8E1")

            # ── 逻辑股评辅助函数 ──
            def _logic_load(sina, sname):
                """从 DB 加载当前股票的所有 review"""
                for iid in logic_tree.get_children(): logic_tree.delete(iid)
                if not sina or sina == "未选中": return
                try:
                    conn = _sql3.connect(_LOGIC_DB); cur = conn.cursor()
                    cur.execute("SELECT id, review_type, content, author, source, created_at FROM logic_reviews WHERE stock_code=? ORDER BY created_at DESC", (sina,))
                    for row in cur.fetchall():
                        rid, rtype, content, author, source, ctime = row
                        t = "logic" if rtype == "逻辑" else ("comment" if rtype == "评论" else "article")
                        content_short = (content[:80] + "…") if content and len(content) > 80 else content
                        logic_tree.insert("", "end", values=(rid, rtype, content_short, author, source, ctime), tags=(t,))
                    conn.close()
                except Exception as _e:
                    print(f"[💡logic_load❌] {_e}", flush=True)

            def _logic_add(_evt=None):
                """新增逻辑/评论"""
                sina = kline_cache.get("sina"); sname = kline_cache.get("sname")
                if not sina or sina.startswith("us") or sina.startswith("hk") or sina.startswith("jp"):
                    messagebox.showinfo("提示", "请先选中 A 股持仓股", parent=win); return
                dlg = tk.Toplevel(win); dlg.title(f"💡 新增逻辑股评 · {sname}"); dlg.geometry("520x420")
                ttk.Label(dlg, text="类型:").grid(row=0, column=0, padx=8, pady=(10,2), sticky="e")
                type_var = tk.StringVar(value="逻辑")
                ttk.Combobox(dlg, textvariable=type_var, values=["逻辑","评论","文章摘录"], width=10, state="readonly").grid(row=0, column=1, pady=(10,2), sticky="w")
                ttk.Label(dlg, text="作者:").grid(row=1, column=0, padx=8, pady=2, sticky="e")
                auth_var = tk.StringVar(value="我")
                ttk.Entry(dlg, textvariable=auth_var, width=30).grid(row=1, column=1, pady=2, sticky="w")
                ttk.Label(dlg, text="内容/逻辑:").grid(row=2, column=0, padx=8, pady=2, sticky="ne")
                content_txt = tk.Text(dlg, width=50, height=12, font=("PingFang SC", 10))
                content_txt.grid(row=2, column=1, pady=2, sticky="nsew"); dlg.rowconfigure(2, weight=1); dlg.columnconfigure(1, weight=1)
                def _save():
                    txt = content_txt.get("1.0", "end").strip()
                    if not txt: messagebox.showwarning("提示", "内容不能为空", parent=dlg); return
                    try:
                        conn = _sql3.connect(_LOGIC_DB); cur = conn.cursor()
                        cur.execute("INSERT INTO logic_reviews(stock_code,stock_name,review_type,content,author,source) VALUES(?,?,?,?,?,?)",
                                    (sina, sname, type_var.get(), txt, auth_var.get(), "手动"))
                        conn.commit(); conn.close()
                        dlg.destroy(); _logic_load(sina, sname)
                        status_var_etf.set(f"✅ {sname} 已新增 {type_var.get()}")
                    except Exception as _e:
                        messagebox.showerror("错误", str(_e), parent=dlg)
                btns = ttk.Frame(dlg); btns.grid(row=3, column=0, columnspan=2, pady=8)
                ttk.Button(btns, text="💾保存", command=_save, width=10).pack(side=tk.LEFT, padx=8)
                ttk.Button(btns, text="取消", command=dlg.destroy, width=10).pack(side=tk.LEFT)

            def _logic_edit(_evt=None):
                """编辑选中行"""
                sel = logic_tree.selection()
                if not sel: messagebox.showinfo("提示", "请先选中一行", parent=win); return
                vals = logic_tree.item(sel[0], "values")
                rid = vals[0]; sina = kline_cache.get("sina"); sname = kline_cache.get("sname")
                # 取完整内容
                try:
                    conn = _sql3.connect(_LOGIC_DB); cur = conn.cursor()
                    cur.execute("SELECT review_type, content, author FROM logic_reviews WHERE id=?", (rid,))
                    row = cur.fetchone(); conn.close()
                    if not row: return
                    rtype, content, author = row
                except Exception: return
                dlg = tk.Toplevel(win); dlg.title(f"✏️ 编辑 #{rid}"); dlg.geometry("520x420")
                ttk.Label(dlg, text="类型:").grid(row=0, column=0, padx=8, pady=(10,2), sticky="e")
                type_var2 = tk.StringVar(value=rtype)
                ttk.Combobox(dlg, textvariable=type_var2, values=["逻辑","评论","文章摘录"], width=10, state="readonly").grid(row=0, column=1, pady=(10,2), sticky="w")
                ttk.Label(dlg, text="作者:").grid(row=1, column=0, padx=8, pady=2, sticky="e")
                auth_var2 = tk.StringVar(value=author)
                ttk.Entry(dlg, textvariable=auth_var2, width=30).grid(row=1, column=1, pady=2, sticky="w")
                content_txt2 = tk.Text(dlg, width=50, height=12, font=("PingFang SC", 10))
                content_txt2.grid(row=2, column=1, pady=2, sticky="nsew"); dlg.rowconfigure(2, weight=1); dlg.columnconfigure(1, weight=1)
                content_txt2.insert("1.0", content or "")
                def _save_edit():
                    txt = content_txt2.get("1.0", "end").strip()
                    try:
                        conn = _sql3.connect(_LOGIC_DB); cur = conn.cursor()
                        cur.execute("UPDATE logic_reviews SET review_type=?, content=?, author=?, updated_at=datetime('now','localtime') WHERE id=?",
                                    (type_var2.get(), txt, auth_var2.get(), rid))
                        conn.commit(); conn.close()
                        dlg.destroy(); _logic_load(sina, sname)
                        status_var_etf.set(f"✅ #{rid} 已更新")
                    except Exception as _e:
                        messagebox.showerror("错误", str(_e), parent=dlg)
                btns2 = ttk.Frame(dlg); btns2.grid(row=3, column=0, columnspan=2, pady=8)
                ttk.Button(btns2, text="💾保存", command=_save_edit, width=10).pack(side=tk.LEFT, padx=8)
                ttk.Button(btns2, text="取消", command=dlg.destroy, width=10).pack(side=tk.LEFT)

            def _logic_del(_evt=None):
                sel = logic_tree.selection()
                if not sel: return
                vals = logic_tree.item(sel[0], "values"); rid = vals[0]
                if not messagebox.askyesno("确认", f"删除 #{rid}?", parent=win): return
                sina = kline_cache.get("sina"); sname = kline_cache.get("sname")
                try:
                    conn = _sql3.connect(_LOGIC_DB); cur = conn.cursor()
                    cur.execute("DELETE FROM logic_reviews WHERE id=?", (rid,))
                    conn.commit(); conn.close(); _logic_load(sina, sname)
                    status_var_etf.set(f"🗑️ #{rid} 已删除")
                except Exception as _e: messagebox.showerror("错误", str(_e), parent=win)

            def _logic_import(_evt=None):
                """导入 txt/md 文件 → 逐行匹配持仓股名 → 写 review"""
                from tkinter import filedialog
                fpath = filedialog.askopenfilename(parent=win, title="选择文章文件 (.txt/.md)",
                                                   filetypes=[("文本文件","*.txt"),("Markdown","*.md"),("所有","*.*")])
                if not fpath: return
                try:
                    with open(fpath, "r", encoding="utf-8") as f: text = f.read()
                except Exception as _e:
                    messagebox.showerror("错误", f"读取失败: {_e}", parent=win); return
                # 取当前 ETF 的所有持仓股名做匹配
                sel = etf_tree.selection()
                if not sel: messagebox.showinfo("提示", "请先选中 ETF", parent=win); return
                evals = etf_tree.item(sel[0], "values"); ename = evals[1]
                holders = ETF_HOLDERS.get(ename, [])
                if not holders: messagebox.showinfo("提示", f"{ename} 暂无持仓映射", parent=win); return
                # 匹配每个股票名在文章中出现的段落
                matched = {}
                for sina, sname in holders:
                    import re
                    # 找包含股票名的行或段落
                    lines = text.split("\n")
                    hits = []
                    for i, line in enumerate(lines):
                        if sname in line or sina.replace("sh","").replace("sz","") in line:
                            # 取上下文 (前1行 + 当前行 + 后1行) 作为段落
                            start = max(0, i-1); end = min(len(lines), i+2)
                            paragraph = "\n".join(lines[start:end]).strip()
                            if paragraph and len(paragraph) > 10: hits.append(paragraph)
                    if hits: matched[sina] = (sname, hits)
                if not matched:
                    messagebox.showinfo("结果", f"文章中未匹配到 {ename} 持仓股的提及", parent=win); return
                # 批量写入 DB
                try:
                    conn = _sql3.connect(_LOGIC_DB); cur = conn.cursor()
                    import os
                    fname = os.path.basename(fpath)
                    for sina, (sname, paras) in matched.items():
                        for p in paras[:3]:  # 每只股最多 3 段
                            cur.execute("INSERT INTO logic_reviews(stock_code,stock_name,review_type,content,author,source,article_title) VALUES(?,?,?,?,?,?,?)",
                                        (sina, sname, "文章摘录", p[:500], "导入", fname, fname))
                    conn.commit(); conn.close()
                    # 同时写 articles 表
                    try:
                        conn2 = _sql3.connect(_LOGIC_DB); cur2 = conn2.cursor()
                        cur2.execute("INSERT INTO logic_articles(title,source,file_path,content,matching_stocks) VALUES(?,?,?,?,?)",
                                     (fname, "本地文件", fpath, text[:5000], ",".join([n for _,n in matched.values()])))
                        conn2.commit(); conn2.close()
                    except Exception: pass
                    # 刷新当前股票
                    cur_sina = kline_cache.get("sina"); cur_sname = kline_cache.get("sname")
                    if cur_sina in matched: _logic_load(cur_sina, cur_sname)
                    messagebox.showinfo("导入完成", f"✅ {fname}\n匹配到 {len(matched)} 只持仓股\n共写入 {sum(len(p[1]) for p in matched.values())} 条摘录", parent=win)
                except Exception as _e:
                    messagebox.showerror("错误", str(_e), parent=win)

            # 用变量直接绑 command (彻底避免 winfo_children 硬索引越界)
            btn_logic_add.config(command=_logic_add)
            btn_logic_edit.config(command=_logic_edit)
            btn_logic_del.config(command=_logic_del)
            btn_logic_import.config(command=_logic_import)
            btn_logic_refresh.config(command=lambda: _logic_load(kline_cache.get("sina"), kline_cache.get("sname")))

            # ── 辅助: 支撑压力线 (ZigZag 局部极值) ──
            def _sr_local(highs, lows, n_levels=3):
                """返回 (supports, resistances) 各 [(x_idx, price), ...]"""
                n = len(highs)
                if n < 20: return [], []
                peaks, troughs = [], []; w = 5
                for i in range(w, n - w):
                    if highs[i] == max(highs[i-w:i+w+1]): peaks.append((i, highs[i]))
                    if lows[i] == min(lows[i-w:i+w+1]): troughs.append((i, lows[i]))
                # 聚类相邻
                def _cluster(pts, is_high):
                    if not pts: return []
                    pts_sorted = sorted(pts, key=lambda p: p[1], reverse=is_high)
                    merged = [pts_sorted[0]]
                    for x_idx, price in pts_sorted[1:]:
                        if abs(price - merged[-1][1]) / merged[-1][1] < 0.01:
                            prev_x, prev_p = merged[-1]
                            merged[-1] = (prev_x, (prev_p + price) / 2)
                        else: merged.append((x_idx, price))
                    return merged
                p_c = _cluster(peaks, True); t_c = _cluster(troughs, False)
                # 取离最后K线最近的
                p_c.sort(key=lambda p: -p[0]); t_c.sort(key=lambda p: -p[0])
                return t_c[:n_levels], p_c[:n_levels]

            # ── 辅助: 买卖点 (MA5/MA20 金叉死叉) ──
            def _sig_local(closes):
                """返回 [(x, price, 'BUY'/'SELL'), ...]"""
                if len(closes) < 30: return []
                ma5 = pd.Series(closes).rolling(5).mean().values
                ma20 = pd.Series(closes).rolling(20).mean().values
                sigs = []
                for i in range(20, len(closes)):
                    if np.isnan(ma5[i]) or np.isnan(ma20[i]) or np.isnan(ma5[i-1]) or np.isnan(ma20[i-1]): continue
                    if ma5[i-1] <= ma20[i-1] and ma5[i] > ma20[i]:
                        if closes[i] > ma20[i]: sigs.append((i, closes[i], "BUY"))
                    elif ma5[i-1] >= ma20[i-1] and ma5[i] < ma20[i]:
                        if closes[i] < ma20[i]: sigs.append((i, closes[i], "SELL"))
                return sigs

            # 缓存当前股票数据 (指标重绘时复用)
            kline_cache = {"sina": None, "sname": None, "data": None}

            # ── 模块级缓存 (挂 self, 窗口关闭不丢) ──
            # 格式: (trade_date_str, fetch_ts, [(score,ts_code,ename,r0,r3,r5,r20), ...])
            if not hasattr(self, "_etf_link_cache"):
                self._etf_link_cache = None

            # ── 6. ETF 数据拉取 (带缓存 + 交易日判断 + 分级刷新) ──
            def _fill_tree(etf_results):
                """清 Treeview 填数据 (公共函数)"""
                for iid in etf_tree.get_children(): etf_tree.delete(iid)
                for rank, (score, ts_code, ename, r0, r3, r5, r20) in enumerate(etf_results):
                    tag = "top" if rank < 3 else ("bot" if rank >= len(etf_results)-3 else "")
                    rtag = "up" if score >= 0 else "dn"
                    etf_tree.insert("", "end",
                        values=(ts_code, ename, f"{r0:+.1f}", f"{r3:+.1f}", f"{r5:+.1f}",
                                f"{r20:+.1f}", f"{score:+.2f}"),
                        tags=(rtag, tag))

            def _compute_from_closes(ecloses):
                r0 = (ecloses[-1]/ecloses[-2]-1)*100 if len(ecloses)>=2 else np.nan
                r3 = (ecloses[-1]/ecloses[-4]-1)*100 if len(ecloses)>=4 else np.nan
                r5 = (ecloses[-1]/ecloses[-6]-1)*100 if len(ecloses)>=6 else np.nan
                r20 = (ecloses[-1]/ecloses[-21]-1)*100 if len(ecloses)>=21 else np.nan
                return r0, r3, r5, r20

            def _load_etf_list(force=False):
                """拉所有 ETF, 带缓存判断:
                force=True → 完全重拉; force=False → 先查缓存
                返回 (etf_results, trade_date) 或 None
                """
                now_ts = _time_etf.time()
                today_str = _time_etf.strftime("%Y%m%d")

                # ── 缓存命中 → 秒返回 ──
                if not force and self._etf_link_cache is not None:
                    cd_trade, cd_ts, cd_data = self._etf_link_cache
                    cache_age = now_ts - cd_ts
                    # 同交易日 & 30分钟内 → 直接用
                    if cd_trade == today_str and cache_age < 1800:
                        _fill_tree(cd_data)
                        status_var_etf.set(f"✅ 缓存命中 · 交易日 {cd_trade} · {len(cd_data)} 只 · {cache_age/60:.0f}min前")
                        return cd_data, cd_trade
                    # 同交易日但超过 30min → 增量刷新当日 (后台)
                    if cd_trade == today_str and cache_age >= 1800:
                        _fill_tree(cd_data)  # 先秒显示
                        status_var_etf.set(f"⏳ 缓存 {cache_age/60:.0f}min, 增量刷新当日..."); win.update_idletasks()
                        # 只重拉前 N 只做抽样验证, 如果 trade_date 没变就不重拉全量
                        sample_ts_code, sample_name = MAINSTREAM_ETFS[0]
                        try:
                            sdf = self._ts_pro.fund_daily(ts_code=sample_ts_code,
                                                          start_date="20260901", end_date=today_str)
                            if sdf is not None and len(sdf) > 0:
                                latest_trade = sdf["trade_date"].iloc[-1]
                                if latest_trade == cd_trade:
                                    status_var_etf.set(f"✅ {cd_trade} 盘中, 30min缓存有效")
                                    return cd_data, cd_trade
                        except Exception: pass
                        # trade_date 变了 → 完全重拉
                        force = True

                # ── 完全重拉 (force=True 或 首次 或 新交易日) ──
                status_var_etf.set("⏳ 拉取 ETF 行情 (40只)..."); win.update_idletasks()
                etf_results = []
                latest_trade_date = ""
                for idx, (ts_code, ename) in enumerate(MAINSTREAM_ETFS):
                    try:
                        edf = self._ts_pro.fund_daily(
                            ts_code=ts_code,
                            start_date="20260901", end_date=today_str)
                        if edf is None or len(edf) < 21: continue
                        edf = edf.sort_values("trade_date").reset_index(drop=True)
                        ecloses = edf["close"].astype(float).values
                        r0, r3, r5, r20 = _compute_from_closes(ecloses)
                        if np.isnan(r5) or np.isnan(r20): continue
                        score = r3*0.2 + r5*0.4 + r20*0.4
                        etf_results.append((score, ts_code, ename, r0, r3, r5, r20))
                        td = str(edf["trade_date"].iloc[-1])
                        if td > latest_trade_date: latest_trade_date = td
                        # 每 10 只刷一次 status (进度反馈)
                        if (idx+1) % 10 == 0:
                            status_var_etf.set(f"⏳ 已拉 {idx+1}/{len(MAINSTREAM_ETFS)} 只..."); win.update_idletasks()
                    except Exception:
                        pass
                etf_results.sort(reverse=True)
                _fill_tree(etf_results)
                # 写缓存
                self._etf_link_cache = (latest_trade_date or today_str, now_ts, etf_results)
                status_var_etf.set(f"✅ {latest_trade_date or today_str} · {len(etf_results)} 只 ETF 已刷新")
                return etf_results, (latest_trade_date or today_str)

            etf_cache = {"data": None}

            # ── 7. 选中 ETF → 刷新中列持仓股 ──
            def _on_etf_select(_evt=None):
                """左列选中 ETF, 刷中列持仓股 + 看多/看空原因"""
                sel = etf_tree.selection()
                if not sel: return
                vals = etf_tree.item(sel[0], "values")
                if not vals: return
                ename = vals[1]
                # 从 Treeview 取 r0/r3/r5/r20/score (都是 "+X.X%" 字符串, 去掉%)
                def _to_f(s):
                    try: return float(str(s).replace("%","").replace("+",""))
                    except: return 0.0
                r0 = _to_f(vals[2]); r3 = _to_f(vals[3]); r5 = _to_f(vals[4])
                r20 = _to_f(vals[5]); score = _to_f(vals[6])
                # 自动推断 ETF 看多/看空原因
                if score > 2 and r20 > 0:
                    etf_reason = f"✅ 综合得分 +{score:.2f}, 20日涨 +{r20:.1f}%, 短期强势领涨板块"
                elif score < -2 and r20 < 0:
                    etf_reason = f"⚠️ 综合得分 {score:.2f}, 20日跌 {r20:.1f}%, 短期弱势领跌板块"
                elif r0 > 1.5 and r5 > 3:
                    etf_reason = f"🔥 当日 +{r0:.1f}%, 5日 +{r5:.1f}%, 动量加速上涨"
                elif r0 < -1.5 and r5 < -3:
                    etf_reason = f"❄️ 当日 {r0:.1f}%, 5日 {r5:.1f}%, 动量加速下跌"
                else:
                    etf_reason = f"⚖️ 综合 {score:+.2f}, 20日 {r20:+.1f}%, 震荡观望"

                status_var_etf.set(f"⏳ 加载 {ename} 持仓股..."); win.update_idletasks()
                # 清中列
                for iid in hold_tree.get_children(): hold_tree.delete(iid)
                holders = ETF_HOLDERS.get(ename, [])
                if not holders:
                    hold_tree.insert("", "end", values=("", "暂无映射持仓", "", "", ""))
                    status_var_etf.set(f"ℹ️ {ename} 暂无持仓映射")
                    return
                # 顶部插入 ETF 原因 banner (不可选)
                hold_tree.insert("", "end", values=(
                    "ETF原因", f"💡 {etf_reason}", "", "", ""),
                    tags=("etf_reason",))
                # 拉每只持仓股 5日/20日
                for sina, sname in holders:
                    try:
                        kdf = self._fetch_ichimoku_kline_data(sina, period="daily",
                                                              is_index=isinstance(sina, str) and sina.startswith("us"))
                        if kdf is None or len(kdf) < 21:
                            hold_tree.insert("", "end", values=(sina, sname, "—", "—", "数据不足"))
                            continue
                        closes = kdf["收盘"].astype(float).values if "收盘" in kdf.columns else kdf["close"].astype(float).values
                        r5s = (closes[-1]/closes[-6]-1)*100 if len(closes)>=6 else np.nan
                        r20s = (closes[-1]/closes[-21]-1)*100 if len(closes)>=21 else np.nan
                        if np.isnan(r5s) or np.isnan(r20s):
                            hold_tree.insert("", "end", values=(sina, sname, "—", "—", ""))
                            continue
                        # 股票自动 reason
                        if r5s > 5: s_reason = "🔥 强势领涨, 5日+" + f"{r5s:.1f}%"
                        elif r5s > 2: s_reason = "📈 持续走强"
                        elif r5s < -5: s_reason = "⚠️ 领跌 5日" + f"{r5s:.1f}%"
                        elif r5s < -2: s_reason = "📉 持续走弱"
                        else: s_reason = "⚖️ 区间震荡"
                        tag = "up" if r5s >= 0 else "dn"
                        hold_tree.insert("", "end",
                            values=(sina, sname, f"{r5s:+.1f}", f"{r20s:+.1f}", s_reason), tags=(tag,))
                    except Exception:
                        hold_tree.insert("", "end", values=(sina, sname, "—", "—", ""))
                # ETF reason tag 样式 (浅蓝底)
                hold_tree.tag_configure("etf_reason", background="#E3F2FD", font=("", 9, "bold"))
                # 🆕 同时刷右列 ETF 视角
                ts_code = vals[0]  # e.g. "510300.SH"
                _mode_var.set("etf")
                _draw_etf_tabs(ts_code, ename)
                _refresh_etf_summary(ts_code, ename)
                _refresh_etf_sent(ts_code, ename)
                nb.select(0)  # 默认回到日K线 tab
                status_var_etf.set(f"✅ {ename} · {len(holders)}只持仓 · 右列已切 ETF 视角")

            # ── _mode 变量: "etf" | "stock" ──
            _mode_var = tk.StringVar(value="stock")

            # ── 8. 选中股票 → 刷新右列 3 tab K线 ──
            def _render_kline_from_cache(only_redraw=False):
                """从缓存重绘 (重绘按钮/指标变化时调用)"""
                if kline_cache["data"] is None: return
                sina = kline_cache["sina"]; sname = kline_cache["sname"]
                opens, highs, lows, closes, n, x, up_c, dn_c = kline_cache["data"]

                # 收集启用的 MA
                ma_on = []
                if ma_chk_vars["ma5"].get(): ma_on.append((5, "#FFC107", "MA5"))
                if ma_chk_vars["ma10"].get(): ma_on.append((10, "#2196F3", "MA10"))
                if ma_chk_vars["ma20"].get(): ma_on.append((20, "#9C27B0", "MA20"))
                if ma_chk_vars["ma60"].get(): ma_on.append((60, "#FF5722", "MA60"))

                # 支撑压力线
                sr_lines = []
                if chk_sr.get():
                    sup, res = _sr_local(highs, lows, n_levels=3)
                    sr_lines = [("S", p, "#2E7D32") for _, p in sup] + [("R", p, "#C62828") for _, p in res]

                # 买卖点
                sigs = _sig_local(closes) if chk_sig.get() else []

                # ── tab1: 日K线 ──
                ax1.clear()
                for i in range(n):
                    col = up_c if closes[i] >= opens[i] else dn_c
                    ax1.plot([x[i],x[i]], [lows[i], highs[i]], color=col, lw=0.8)
                    ax1.bar(x[i], closes[i]-opens[i], bottom=opens[i], color=col, width=0.6)
                for period, color, lbl in ma_on:
                    ma_v = pd.Series(closes).rolling(period).mean().values
                    ax1.plot(x, ma_v, color=color, lw=1.1, label=lbl)
                for kind, price, color in sr_lines:
                    ax1.axhline(price, color=color, lw=0.9, ls="--", alpha=0.75)
                    ax1.text(n - 1, price, f"  {kind} {price:.2f}", va="center", fontsize=7, color=color,
                             bbox=dict(boxstyle="round,pad=0.12", fc="white", ec=color, alpha=0.85))
                for sx, sp, stype in sigs:
                    if stype == "BUY":
                        ax1.scatter(sx, lows[sx] * 0.995, marker="^", color="#C62828", s=45, zorder=5)
                        ax1.annotate(f"买 {sp:.2f}", (sx, lows[sx]), xytext=(0, -18),
                                    textcoords="offset points", fontsize=7, color="#C62828",
                                    ha="center", fontweight="bold")
                    else:
                        ax1.scatter(sx, highs[sx] * 1.005, marker="v", color="#2E7D32", s=45, zorder=5)
                        ax1.annotate(f"卖 {sp:.2f}", (sx, highs[sx]), xytext=(0, 10),
                                    textcoords="offset points", fontsize=7, color="#2E7D32",
                                    ha="center", fontweight="bold")
                title1 = f"📈 日K线 · {sname}  |  MA:{','.join(l for _,_,l in ma_on) if ma_on else '无'}"
                if sr_lines: title1 += f"  |  S/R:{len(sr_lines)}"
                if sigs: title1 += f"  |  买卖:{len(sigs)}"
                ax1.set_title(title1, fontsize=10, fontweight="bold")
                if ma_on: ax1.legend(fontsize=6.5, loc="upper left", ncol=len(ma_on))
                ax1.grid(True, alpha=0.2, lw=0.6)
                cv1.draw()

                # ── tab2: 蜡烛 ──
                ax2.clear()
                for i in range(n):
                    col = up_c if closes[i] >= opens[i] else dn_c
                    ax2.plot([x[i],x[i]], [lows[i], highs[i]], color=col, lw=0.8)
                    ax2.bar(x[i], closes[i]-opens[i], bottom=opens[i], color=col, width=0.6)
                for kind, price, color in sr_lines:
                    ax2.axhline(price, color=color, lw=0.9, ls="--", alpha=0.75)
                    ax2.text(n - 1, price, f"  {kind} {price:.2f}", va="center", fontsize=7, color=color,
                             bbox=dict(boxstyle="round,pad=0.12", fc="white", ec=color, alpha=0.85))
                for sx, sp, stype in sigs:
                    if stype == "BUY":
                        ax2.scatter(sx, lows[sx] * 0.995, marker="^", color="#C62828", s=45, zorder=5)
                    else:
                        ax2.scatter(sx, highs[sx] * 1.005, marker="v", color="#2E7D32", s=45, zorder=5)
                ax2.set_title(f"🕯️ 蜡烛 · {sname}", fontsize=10, fontweight="bold")
                ax2.grid(True, alpha=0.2, lw=0.6)
                cv2.draw()

                # ── tab3: 一目均衡 ──
                ax3.clear()
                self._plot_ichimoku_ax(ax3, x, highs, lows, closes, show_explanation=False)
                # 一目均衡也叠支撑压力线
                for kind, price, color in sr_lines:
                    ax3.axhline(price, color=color, lw=0.8, ls="--", alpha=0.6)
                    ax3.text(n - 1, price, f"  {kind} {price:.2f}", va="center", fontsize=6.5, color=color)
                ax3.set_title(f"📊 一目均衡 · {sname}", fontsize=10, fontweight="bold")
                cv3.draw()

                status_var_etf.set(f"✅ {sname} · MA:{len(ma_on)} S/R:{len(sr_lines)} 买卖:{len(sigs)}")

            def _draw_kline_tabs(sina, sname):
                """右列 3 tab 画 K 线 (首次加载 → 缓存 → 渲染)"""
                status_var_etf.set(f"⏳ 加载 {sname}({sina}) K线..."); win.update_idletasks()
                # 海外兜底
                is_us = sina.startswith("us"); is_jp = sina.startswith("jp"); is_hk = sina.startswith("hk")
                if is_us or is_jp or is_hk:
                    for ax in [ax1, ax2, ax3]:
                        ax.clear()
                        ax.text(0.5, 0.5, f"{sname}\n({sina})\n⚠️ 海外暂不支持",
                                transform=ax.transAxes, fontsize=13, ha="center", va="center", color="#999")
                    for cv in [cv1, cv2, cv3]: cv.draw()
                    status_var_etf.set(f"ℹ️ {sname} 海外暂不支持"); return
                # A股拉数据
                kdf = self._fetch_ichimoku_kline_data(sina, period="daily", is_index=False)
                if kdf is None or len(kdf) < 30:
                    for ax in [ax1, ax2, ax3]:
                        ax.clear()
                        ax.text(0.5, 0.5, f"{sname}\n数据不足", transform=ax.transAxes,
                                fontsize=14, ha="center", va="center", color="#E53935")
                    for cv in [cv1, cv2, cv3]: cv.draw()
                    status_var_etf.set(f"❌ {sname} 数据不足"); return
                opens = kdf["开盘"].astype(float).values if "开盘" in kdf.columns else kdf["open"].astype(float).values
                highs = kdf["最高"].astype(float).values if "最高" in kdf.columns else kdf["high"].astype(float).values
                lows  = kdf["最低"].astype(float).values if "最低" in kdf.columns else kdf["low"].astype(float).values
                closes = kdf["收盘"].astype(float).values if "收盘" in kdf.columns else kdf["close"].astype(float).values
                n = len(closes); x = np.arange(n); up_c, dn_c = "#EF5350", "#66BB6A"
                kline_cache["sina"] = sina; kline_cache["sname"] = sname
                kline_cache["data"] = (opens, highs, lows, closes, n, x, up_c, dn_c)
                _render_kline_from_cache(only_redraw=False)

            # ── 9. 双击事件绑定 ──
            def _on_etf_double(_evt):
                """双击 ETF → 选中 + 刷中列 + 自动刷右列第一只持仓"""
                _on_etf_select()
                sel = etf_tree.selection()
                if not sel: return
                vals = etf_tree.item(sel[0], "values")
                ename = vals[1]
                holders = ETF_HOLDERS.get(ename, [])
                if not holders: return
                # 选中中列第一只
                hold_tree.selection_remove(hold_tree.selection())
                first_child = hold_tree.get_children()
                if first_child:
                    hold_tree.selection_set(first_child[0])
                    hold_tree.see(first_child[0])
                # 刷右列 (K线+概要+情绪+逻辑)
                sina, sname = holders[0]
                _on_stock_selected(sina, sname)

            def _refresh_summary(sina, sname):
                """刷新概要 tab (tushare stock_basic + daily_basic)"""
                # sina 转 tushare ts_code
                ts_code = None
                if sina.startswith("sh") and len(sina) == 8: ts_code = sina[2:] + ".SH"
                elif sina.startswith("sz") and len(sina) == 8: ts_code = sina[2:] + ".SZ"
                summary_text.config(state="normal"); summary_text.delete("1.0", "end")
                summary_text.insert("end", f"⏳ 加载 {sname} 概要..."); summary_text.config(state="disabled")
                if not ts_code:
                    summary_text.config(state="normal"); summary_text.delete("1.0", "end")
                    summary_text.insert("end", f"❌ {sname} 概要暂不支持 (海外/非A股)"); summary_text.config(state="disabled"); return
                try:
                    sb = self._ts_pro.stock_basic(ts_code=ts_code, fields="ts_code,name,area,industry,list_date,market")
                    db = self._ts_pro.daily_basic(ts_code=ts_code, fields="ts_code,total_mv,circ_mv,pe,pe_ttm,pb,ps_ttm,dv_ttm", limit=1)
                    sb = sb.iloc[0] if len(sb) > 0 else None
                    db = db.iloc[0] if len(db) > 0 else None
                    lines = [f"📋 {sname} ({ts_code})", "=" * 40]
                    if sb is not None:
                        lines.extend([
                            f"行业: {sb.get('industry','—')}  |  地区: {sb.get('area','—')}",
                            f"上市日: {sb.get('list_date','—')}  |  市场: {sb.get('market','—')}",
                        ])
                    if db is not None:
                        lines.extend([
                            "", "📊 估值指标", "-" * 24,
                            f"总市值: {db.get('total_mv',0)/10000:.2f} 万亿" if db.get('total_mv') else "",
                            f"流通市值: {db.get('circ_mv',0)/10000:.2f} 万亿" if db.get('circ_mv') else "",
                            f"PE(TTM): {db.get('pe_ttm','—')}  |  PB: {db.get('pb','—')}",
                            f"PS(TTM): {db.get('ps_ttm','—')}  |  股息率: {db.get('dv_ttm','—')}%",
                        ])
                    else:
                        lines.append("\n⚠️ daily_basic 数据暂不可用")
                    summary_text.config(state="normal"); summary_text.delete("1.0", "end")
                    summary_text.insert("end", "\n".join(l for l in lines if l is not None)); summary_text.config(state="disabled")
                except Exception as _e:
                    summary_text.config(state="normal"); summary_text.delete("1.0", "end")
                    summary_text.insert("end", f"❌ 概要加载失败: {_e}"); summary_text.config(state="disabled")

            def _refresh_sent(sina, sname):
                """刷新情绪 tab (moneyflow + hsgt + top_list)"""
                ts_code = None
                if sina.startswith("sh") and len(sina) == 8: ts_code = sina[2:] + ".SH"
                elif sina.startswith("sz") and len(sina) == 8: ts_code = sina[2:] + ".SZ"
                sent_text.config(state="normal"); sent_text.delete("1.0", "end")
                sent_text.insert("end", f"⏳ 加载 {sname} 资金情绪..."); sent_text.config(state="disabled")
                if not ts_code:
                    sent_text.config(state="normal"); sent_text.delete("1.0", "end")
                    sent_text.insert("end", f"❌ {sname} 海外暂不支持资金情绪"); sent_text.config(state="disabled"); return
                lines = [f"🔥 {sname} 资金情绪", "=" * 40]
                try:
                    # 1. 主力资金流 (最近3日)
                    mf = self._ts_pro.moneyflow(ts_code=ts_code, limit=3)
                    if mf is not None and len(mf) > 0:
                        mf = mf.sort_values("trade_date", ascending=False)
                        lines.append("📦 主力资金流 (最近3日)"); lines.append("-" * 24)
                        for _, row in mf.iterrows():
                            net = row.get("buy_sm_amount", 0) - row.get("sell_sm_amount", 0)
                            lines.append(f"  {row.get('trade_date','')}  主力净额: {net:+.2f}亿")
                        total_net = sum((r.get("buy_sm_amount",0)-r.get("sell_sm_amount",0)) for _,r in mf.iterrows())
                        lines.append(f"  3日合计: {total_net:+.2f}亿")
                    # 2. 北向持股 (如果是沪深港通)
                    try:
                        hsgt = self._ts_pro.hsgt_top10(ts_code=ts_code, limit=3)
                        if hsgt is not None and len(hsgt) > 0:
                            lines.append("\n🌏 北向持股变动"); lines.append("-" * 24)
                            for _, row in hsgt.sort_values("trade_date", ascending=False).iterrows():
                                lines.append(f"  {row.get('trade_date','')}  净买入: {row.get('net_buy_amount',0):+.2f}亿  持股: {row.get('hold_amount',0):.2f}亿")
                    except Exception: pass
                    # 3. 龙虎榜 (最近上榜)
                    try:
                        tl = self._ts_pro.top_list(ts_code=ts_code, limit=3)
                        if tl is not None and len(tl) > 0:
                            lines.append("\n🐉 龙虎榜上榜记录"); lines.append("-" * 24)
                            for _, row in tl.sort_values("trade_date", ascending=False).iterrows():
                                lines.append(f"  {row.get('trade_date','')}  {row.get('reason','')}  {row.get('close','')}  {row.get('pct_change',0):+.2f}%")
                    except Exception: pass
                    if len(lines) == 2: lines.append("\n⚠️ 暂无资金情绪数据 (tushare 接口可能需要更高积分)")
                    sent_text.config(state="normal"); sent_text.delete("1.0", "end")
                    sent_text.insert("end", "\n".join(lines)); sent_text.config(state="disabled")
                except Exception as _e:
                    sent_text.config(state="normal"); sent_text.delete("1.0", "end")
                    sent_text.insert("end", f"❌ 情绪加载失败: {_e}"); sent_text.config(state="disabled")

            # ── ETF 视角: 刷右列 3 个 K 线 tab (用 tushare fund_daily) ──
            def _draw_etf_tabs(ts_code, ename):
                """用 tushare fund_daily 拉 ETF K 线, 画 ax1/ax2/ax3"""
                status_var_etf.set(f"⏳ 加载 ETF {ename} K线..."); win.update_idletasks()
                try:
                    edf = self._ts_pro.fund_daily(ts_code=ts_code,
                                                  start_date="20250101",
                                                  end_date=_time_etf.strftime("%Y%m%d"))
                    if edf is None or len(edf) < 20:
                        for ax in [ax1, ax2, ax3]:
                            ax.clear(); ax.text(0.5, 0.5, f"⚠️ {ename} K线数据不足", ha="center", va="center", transform=ax.transAxes)
                        for cv in [cv1, cv2, cv3]: cv.draw(); return
                    edf = edf.sort_values("trade_date").reset_index(drop=True)
                    opens = edf["open"].astype(float).values
                    highs = edf["high"].astype(float).values
                    lows = edf["low"].astype(float).values
                    closes = edf["close"].astype(float).values
                    vols = edf["vol"].astype(float).values
                    n = len(closes); x = np.arange(n)

                    # 辅助 MA
                    def _ma(arr, w):
                        if len(arr) < w: return arr
                        m = np.convolve(arr, np.ones(w)/w, mode="valid")
                        return np.concatenate([np.full(w-1, np.nan), m])

                    # ── ax1: ETF 日K线 + MA ──
                    ax1.clear()
                    ax1.set_title(f"📈 {ename} ({ts_code}) 日K线", fontsize=11)
                    # 简化蜡烛 (ETF 用线图+MA 更清晰)
                    ax1.plot(x, closes, color="#1976D2", linewidth=1.2, label="收盘价")
                    ax1.plot(x, _ma(closes,5), color="#FF9800", linewidth=0.9, label="MA5", alpha=0.8)
                    ax1.plot(x, _ma(closes,20), color="#4CAF50", linewidth=0.9, label="MA20", alpha=0.8)
                    ax1.plot(x, _ma(closes,60), color="#9C27B0", linewidth=0.9, label="MA60", alpha=0.7)
                    # 支撑压力 (简单 ZigZag 局部极值)
                    from scipy.signal import argrelextrema
                    try:
                        local_max = argrelextrema(closes, np.greater, order=5)[0]
                        local_min = argrelextrema(closes, np.less, order=5)[0]
                        for idx in local_max[-3:]:
                            ax1.axhline(closes[idx], color="#FF5722", linestyle="--", linewidth=0.7, alpha=0.6, xmin=0.02, xmax=0.98)
                            ax1.annotate(f"R {closes[idx]:.2f}", xy=(n*0.98, closes[idx]), fontsize=7, color="#FF5722", ha="right")
                        for idx in local_min[-3:]:
                            ax1.axhline(closes[idx], color="#00BCD4", linestyle="--", linewidth=0.7, alpha=0.6, xmin=0.02, xmax=0.98)
                            ax1.annotate(f"S {closes[idx]:.2f}", xy=(n*0.98, closes[idx]), fontsize=7, color="#00BCD4", ha="right")
                    except Exception: pass
                    ax1.legend(loc="upper left", fontsize=8); ax1.grid(True, alpha=0.3); ax1.set_xlim(0, n-1)
                    cv1.draw()

                    # ── ax2: ETF 蜡烛图 (简化 OHLC 柱) ──
                    ax2.clear()
                    ax2.set_title(f"🕯️ {ename} ETF 蜡烛图", fontsize=11)
                    colors = ["#4CAF50" if closes[i] >= opens[i] else "#F44336" for i in range(n)]
                    ax2.bar(x, closes - opens, bottom=opens, color=colors, width=0.6, alpha=0.9)
                    ax2.vlines(x, lows, highs, color=colors, linewidth=0.6, alpha=0.8)
                    ax2.grid(True, alpha=0.3); ax2.set_xlim(0, n-1)
                    cv2.draw()

                    # ── ax3: ETF 一目均衡 (用收盘价构建近似) ──
                    ax3.clear()
                    ax3.set_title(f"📊 {ename} ETF 一目均衡 (近似)", fontsize=11)
                    # 基准线 (26 周期最高最低中点)
                    base_line = np.full(n, np.nan)
                    for i in range(26, n):
                        base_line[i] = (max(highs[i-26:i]) + min(lows[i-26:i])) / 2
                    # 转换线 (9 周期)
                    conv_line = np.full(n, np.nan)
                    for i in range(9, n):
                        conv_line[i] = (max(highs[i-9:i]) + min(lows[i-9:i])) / 2
                    ax3.plot(x, closes, color="#1976D2", linewidth=1.0, label="收盘价")
                    ax3.plot(x, base_line, color="#FF9800", linewidth=0.9, label="基准线", alpha=0.8)
                    ax3.plot(x, conv_line, color="#E91E63", linewidth=0.9, label="转换线", alpha=0.8)
                    # 云 (26 偏移)
                    cloud_a = np.full(n, np.nan)
                    for i in range(26, n):
                        cloud_a[i] = (conv_line[i-26] + base_line[i-26]) / 2
                    cloud_b = np.full(n, np.nan)
                    for i in range(26*2, n):
                        cloud_b[i] = (max(highs[i-26*2:i-26]) + min(lows[i-26*2:i-26])) / 2
                    ax3.fill_between(x, cloud_a, cloud_b, where=cloud_a > cloud_b, color="#4CAF50", alpha=0.15)
                    ax3.fill_between(x, cloud_a, cloud_b, where=cloud_a <= cloud_b, color="#F44336", alpha=0.15)
                    ax3.legend(loc="upper left", fontsize=8); ax3.grid(True, alpha=0.3); ax3.set_xlim(0, n-1)
                    cv3.draw()

                    # 更新缓存
                    kline_cache.update({"mode":"etf", "ts_code":ts_code, "ename":ename, "opens":opens, "highs":highs, "lows":lows, "closes":closes, "vols":vols})
                    status_var_etf.set(f"✅ {ename} ETF K线 · {n} 根")
                except Exception as _e:
                    import traceback; traceback.print_exc()
                    for ax in [ax1, ax2, ax3]:
                        ax.clear(); ax.text(0.5, 0.5, f"❌ ETF K线加载失败: {_e}", ha="center", va="center", transform=ax.transAxes)
                    for cv in [cv1, cv2, cv3]: cv.draw()

            # ── ETF 视角: tab4 概要 ──
            def _refresh_etf_summary(ts_code, ename):
                """ETF 概要: basic + fund_nav + 涨跌统计"""
                summary_text.config(state="normal"); summary_text.delete("1.0", "end")
                lines = [f"📋 ETF 概要 · {ename} ({ts_code})", "=" * 45]
                try:
                    # 1. fund_basic (tushare 基金基础信息)
                    try:
                        fb = self._ts_pro.fund_basic(ts_code=ts_code)
                        if fb is not None and len(fb) > 0:
                            r = fb.iloc[0]
                            lines.extend([
                                f"类型: {r.get('fund_type', 'ETF')}  |  管理人: {r.get('management', '')}",
                                f"发行公司: {r.get('name', '')}  |  上市日期: {r.get('list_date', '')}",
                                f"管理费率: {r.get('fee_rate', '')}  |  托管费率: {r.get('cust_fee', '')}",
                            ])
                    except Exception: pass
                    # 2. 从 fund_daily 计算涨跌统计
                    edf = self._ts_pro.fund_daily(ts_code=ts_code, start_date="20250101", end_date=_time_etf.strftime("%Y%m%d"))
                    if edf is not None and len(edf) > 20:
                        edf = edf.sort_values("trade_date").reset_index(drop=True)
                        closes = edf["close"].astype(float).values
                        ret1 = (closes[-1]/closes[-2]-1)*100 if len(closes)>=2 else 0
                        ret5 = (closes[-1]/closes[-6]-1)*100 if len(closes)>=6 else 0
                        ret20 = (closes[-1]/closes[-21]-1)*100 if len(closes)>=21 else 0
                        ret60 = (closes[-1]/closes[-61]-1)*100 if len(closes)>=61 else 0
                        # 波动率 (20日)
                        daily_ret = np.diff(closes)/closes[:-1]
                        vol20 = np.std(daily_ret[-20:]) * np.sqrt(252) * 100 if len(daily_ret) >= 20 else 0
                        # 最大回撤 (60日)
                        peak = np.maximum.accumulate(closes[-60:])
                        drawdown = (closes[-60:] - peak) / peak * 100
                        max_dd = abs(np.min(drawdown)) if len(drawdown) > 0 else 0
                        lines.extend([
                            "", "📊 涨跌幅统计", "-" * 28,
                            f"  当日:  {ret1:+.2f}%",
                            f"  5日:   {ret5:+.2f}%",
                            f"  20日:  {ret20:+.2f}%",
                            f"  60日:  {ret60:+.2f}%",
                            "", "📉 风险指标", "-" * 28,
                            f"  20日年化波动率: {vol20:.1f}%",
                            f"  60日最大回撤:   {max_dd:.2f}%",
                            f"  近 {len(closes)} 个交易日数据",
                        ])
                    # 3. 持仓股概览 (从 ETF_HOLDERS)
                    holders = ETF_HOLDERS.get(ename, [])
                    if holders:
                        lines.extend([
                            "", f"📦 核心持仓股 ({len(holders)} 只)", "-" * 28,
                            "  " + "、".join(n for _, n in holders[:8]),
                            "  " + ("..." if len(holders) > 8 else ""),
                        ])
                    # 4. 文章库匹配
                    try:
                        conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
                        cur.execute("SELECT COUNT(*) FROM articles WHERE title LIKE ? OR content LIKE ?", (f"%{ename}%", f"%{ename}%"))
                        art_cnt = cur.fetchone()[0]
                        cur.execute("SELECT COUNT(*) FROM articles WHERE stock_code=? OR stock_name LIKE ?",
                                    (ts_code.split(".")[0], f"%{ename}%"))
                        etf_art = cur.fetchone()[0]
                        conn.close()
                        lines.extend([
                            "", "📚 文章库", "-" * 28,
                            f"  提到 '{ename}' 的文章: {art_cnt} 篇",
                            f"  关联个股文章:         {etf_art} 篇",
                        ])
                    except Exception: pass
                except Exception as _e:
                    lines.append(f"\n⚠️ 概要加载异常: {_e}")
                summary_text.insert("end", "\n".join(lines)); summary_text.config(state="disabled")

            # ── ETF 视角: tab5 情绪 ──
            def _refresh_etf_sent(ts_code, ename):
                """ETF 情绪: 资金流 + 成交活跃度 + 关联持仓股资金"""
                sent_text.config(state="normal"); sent_text.delete("1.0", "end")
                lines = [f"🔥 ETF 资金情绪 · {ename}", "=" * 45]
                try:
                    # 1. ETF 自身成交活跃度 (从 fund_daily 算)
                    edf = self._ts_pro.fund_daily(ts_code=ts_code, start_date="20251001", end_date=_time_etf.strftime("%Y%m%d"))
                    if edf is not None and len(edf) >= 10:
                        edf = edf.sort_values("trade_date").reset_index(drop=True)
                        vols = edf["vol"].astype(float).values  # 手
                        amount = edf["amount"].astype(float).values if "amount" in edf.columns else np.zeros(len(vols))
                        avg_vol20 = np.mean(vols[-20:]) if len(vols) >= 20 else np.mean(vols)
                        avg_vol5 = np.mean(vols[-5:])
                        vol_ratio = avg_vol5 / avg_vol20 if avg_vol20 > 0 else 1
                        lines.extend([
                            "📊 ETF 成交活跃度", "-" * 35,
                            f"  20日均量:  {avg_vol20/1e4:.1f} 万手",
                            f"  5日均量:   {avg_vol5/1e4:.1f} 万手",
                            f"  量比(5/20): {vol_ratio:.2f}x",
                            f"  成交额(亿): {amount[-1]/1e4:.1f}" if len(amount)>0 else "",
                        ])
                        if vol_ratio > 2.0: lines.append(f"  ⚠️ 显著放量 ({vol_ratio:.1f}x), 资金关注度上升")
                        elif vol_ratio < 0.5: lines.append(f"  💤 明显缩量 ({vol_ratio:.1f}x), 交投清淡")
                    # 2. 关联持仓股资金流 TOP3
                    holders = ETF_HOLDERS.get(ename, [])
                    if holders:
                        lines.extend([
                            "", "💰 关联持仓股主力资金流 (TOP3)", "-" * 35,
                        ])
                        net_inflow_list = []
                        for sina, sname in holders[:10]:
                            if sina.startswith("sh") or sina.startswith("sz"):
                                code6 = sina[2:8]
                                try:
                                    mf = self._ts_pro.moneyflow(ts_code=code6 + ".SH" if sina.startswith("sh") else code6 + ".SZ", limit=1)
                                    if mf is not None and len(mf) > 0:
                                        r = mf.iloc[0]
                                        net = r.get("buy_sm_amount", 0) - r.get("sell_sm_amount", 0)
                                        net_inflow_list.append((sname, net))
                                except Exception: pass
                        net_inflow_list.sort(key=lambda x: x[1], reverse=True)
                        for sname, net in net_inflow_list[:3]:
                            flag = "🟢" if net >= 0 else "🔴"
                            lines.append(f"  {flag} {sname}: {net:+.2f}亿")
                        # 整体判断
                        if net_inflow_list:
                            total = sum(n for _, n in net_inflow_list)
                            if total > 1: lines.append(f"  ✅ ETF 核心持仓整体净流入 +{total:.2f}亿, 板块看多")
                            elif total < -1: lines.append(f"  ⚠️ ETF 核心持仓整体净流出 {total:.2f}亿, 板块看空")
                            else: lines.append(f"  ⚖️ ETF 持仓股资金整体均衡 ({total:+.2f}亿)")
                except Exception as _e:
                    lines.append(f"\n⚠️ 情绪加载异常: {_e}")
                sent_text.insert("end", "\n".join(lines)); sent_text.config(state="disabled")

            def _on_stock_selected(sina, sname):
                """统一刷新: K线 + 概要 + 情绪 + 逻辑股评 (切 stock 模式)"""
                _mode_var.set("stock")
                _draw_kline_tabs(sina, sname)
                logic_stock_var.set(f"{sname} ({sina})")
                _logic_load(sina, sname)
                if not sina.startswith("us") and not sina.startswith("hk") and not sina.startswith("jp"):
                    _refresh_summary(sina, sname)
                    _refresh_sent(sina, sname)

            def _on_hold_double(_evt):
                sel = hold_tree.selection()
                if not sel: return
                vals = hold_tree.item(sel[0], "values")
                if not vals or not vals[0] or vals[0] == "" or vals[1] == "ETF原因": return
                _on_stock_selected(vals[0], vals[1])

            def _on_hold_select(_evt=None):
                sel = hold_tree.selection()
                if not sel: return
                vals = hold_tree.item(sel[0], "values")
                if not vals or not vals[0] or vals[0] == "" or vals[1] == "ETF原因": return
                _on_stock_selected(vals[0], vals[1])

            etf_tree.bind("<<TreeviewSelect>>", _on_etf_select)
            etf_tree.bind("<Double-1>", lambda e: _on_etf_double(e))
            hold_tree.bind("<<TreeviewSelect>>", _on_hold_select)
            hold_tree.bind("<Double-1>", lambda e: _on_hold_double(e))

            refresh_etf.config(command=lambda: _load_etf_list(force=True))
            redraw_etf.config(command=lambda: _render_kline_from_cache(only_redraw=True))

            # ── 10. 启动加载 ──
            win.update_idletasks()
            try:
                result = _load_etf_list(force=False)  # 先查缓存, 秒填
                if result: etf_cache["data"] = result[0]
                # 默认选中: 优先预选 → 否则 Top1
                prefill_name = getattr(self, "_etf_link_prefill_name", None)
                matched_prefill = None
                if prefill_name:
                    for cid in etf_tree.get_children():
                        cvals = etf_tree.item(cid, "values")
                        if cvals and prefill_name in str(cvals[1]):
                            matched_prefill = cid; break
                if matched_prefill:
                    etf_tree.selection_set(matched_prefill)
                    etf_tree.see(matched_prefill)
                else:
                    first_child = etf_tree.get_children()
                    if first_child:
                        etf_tree.selection_set(first_child[0])
                        etf_tree.see(first_child[0])
                # 清预选标记 (一次性)
                try: del self._etf_link_prefill_name
                except Exception: pass
            except Exception as _e:
                status_var_etf.set(f"❌ 加载失败: {_e}")
                print(f"[📊ETF联动❌] {_e}", flush=True)
                _tb_etf.print_exc()

        except Exception as _e:
            print(f"[📊ETF联动❌] {_e}", flush=True)
            _tb_etf.print_exc()
            messagebox.showerror("错误", f"打开 ETF 联动弹窗失败: {_e}",
                                 parent=getattr(self, 'root', None))

    # ═══════════════════════════════════════════════════════════════
    # 🖼️ 图像分析弹窗 — 多图联动同时展示
    # ═══════════════════════════════════════════════════════════════

    def _show_image_analysis_dialog(self):
        """🖼️ 图像分析弹窗: 多图联动展示 (日K/一目均衡/BOLL/VOL/MACD/资金流向)"""
        import traceback as _tb_img
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
            from matplotlib.figure import Figure
            import matplotlib.dates as mdates
            import numpy as np

            win = self._safe_toplevel(self.root)
            win.title("🖼️ 图像分析 · 多图联动")
            try: win.state("zoomed")
            except:
                try: win.attributes("-zoomed", True)
                except: win.geometry("1200x1400")

            # ── 顶部工具栏 ──
            top = ttk.Frame(win, padding=6); top.pack(fill=tk.X)
            ttk.Label(top, text="📊 标的:", font=("",10,"bold")).pack(side=tk.LEFT)

            # ── 动态构建下拉: 指数 → 持仓股 → 龙头股 → 资讯股 → 热门 ──
            def _build_symbols():
                syms = []; seen = set()
                def _add(tag, name, code):
                    key = code.strip()
                    if not key or key in seen: return
                    seen.add(key)
                    # code 格式: 纯数字 6 位, 自动补 sina 前缀
                    if code.isdigit() and len(code)==6:
                        sina = f"sh{code}" if code.startswith(("6","9","000","399")) else f"sz{code}"
                        syms.append(f"[{tag}] {name}({sina})")
                    else:
                        syms.append(f"[{tag}] {name}({code})")
                # 1. 主要指数 (固定)
                for nm, cd in [("上证指数","sh000001"),("深证成指","sz399001"),("创业板指","sz399006"),
                               ("沪深300","sh000300"),("中证500","sh000905"),("科创50","sh000688")]:
                    _add("指数", nm, cd)
                # 2. 持仓股 (group_idx=1)
                try:
                    for i, h in enumerate(getattr(self, 'holding_stocks', []) or []):
                        if h: _add("持仓", h[0], h[1])
                except Exception: pass
                # 3. 龙头股 (group_idx=2)
                try:
                    for i, h in enumerate(getattr(self, 'holding_stocks_2', []) or []):
                        if h: _add("龙头", h[0], h[1])
                except Exception: pass
                # 4. 资讯股/同花顺 (group_idx=6)
                try:
                    for i, h in enumerate(getattr(self, 'holding_stocks_6', []) or []):
                        if h: _add("资讯", h[0], h[1])
                except Exception: pass
                # 5. Main (group_idx=4)
                try:
                    for i, h in enumerate(getattr(self, 'holding_stocks_4', []) or []):
                        if h: _add("Main", h[0], h[1])
                except Exception: pass
                # 6. 热门兜底 (硬编码)
                for nm, cd in [("贵州茅台","600519"),("宁德时代","300750"),("比亚迪","002594"),
                               ("中国平安","601318"),("招商银行","600036"),("五粮液","000858"),
                               ("长江电力","600900"),("美的集团","000333"),("中芯国际","688981")]:
                    _add("热门", nm, cd)
                return syms

            symbols = _build_symbols()
            sym_var = tk.StringVar(value=symbols[0] if symbols else "上证指数(sh000001)")
            sym_combo = ttk.Combobox(top, textvariable=sym_var, values=symbols, width=28)
            sym_combo.pack(side=tk.LEFT, padx=4)

            # 股票名/代码快速搜索
            ttk.Label(top, text="🔍 输入:", font=("",10)).pack(side=tk.LEFT, padx=(8,2))
            search_var = tk.StringVar(value="")
            search_entry = ttk.Entry(top, textvariable=search_var, width=12, font=("Menlo",10))
            search_entry.pack(side=tk.LEFT)

            def _on_search(_evt=None):
                """根据输入过滤下拉或直接触发刷新"""
                q = search_var.get().strip()
                if not q:
                    sym_combo["values"] = symbols
                    return
                ql = q.lower()
                matched = [s for s in symbols if ql in s.lower()]
                # 如果输入的是纯 6 位代码或带 sina 前缀, 也支持
                if len(matched) < 3:
                    # 尝试直接构造 sina 代码作为 fallback
                    code = q.zfill(6) if q.isdigit() else q
                    if code.isdigit() and len(code)==6:
                        sina = f"sh{code}" if code.startswith(("6","9","000","399")) else f"sz{code}"
                        matched.append(f"[手动] 自定义({sina})")
                    elif code.startswith(("sh","sz")) and len(code)==8:
                        matched.append(f"[手动] 自定义({code})")
                sym_combo["values"] = matched if matched else symbols
                if matched: sym_combo.set(matched[0])
            search_entry.bind("<KeyRelease>", _on_search)
            search_entry.bind("<Return>", lambda e: _refresh())

            # 清除搜索恢复全量
            def _on_focus_out(_evt=None):
                if not search_var.get().strip():
                    sym_combo["values"] = symbols
            search_entry.bind("<FocusOut>", _on_focus_out)

            ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
            ttk.Label(top, text="📐 图表:", font=("",10,"bold")).pack(side=tk.LEFT)

            # 图表类型
            chart_types = [
                ("daily_k", "📈日K线", True),
                ("ichimoku", "📊一目均衡", True),
                ("boll", "📉BOLL带", True),
                ("vol", "📦成交量", True),
                ("macd", "📐MACD", True),
                ("moneyflow", "💵资金流向", False),
                ("emotion", "🎯情绪复盘", False),
                ("etf_rank", "📊ETF强弱", False),
            ]
            chart_vars = {}
            for key, lbl, default in chart_types:
                v = tk.BooleanVar(value=default); chart_vars[key] = v
                ttk.Checkbutton(top, text=lbl, variable=v).pack(side=tk.LEFT, padx=2)

            ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
            refresh_btn = ttk.Button(top, text="🔄 刷新", width=10); refresh_btn.pack(side=tk.LEFT, padx=4)
            # ❓ 帮助按钮 — 弹 6 图说明分 3 列
            def _show_chart_help():
                help_win = tk.Toplevel(win); help_win.title("📖 图像分析 · 图表说明")
                help_win.geometry("900x560"); help_win.configure(bg="#FAFAFA")
                help_win.transient(win); help_win.grab_set()
                import tkinter.font as tkf
                try: help_win.attributes("-topmost", True)
                except: pass
                help_win.update_idletasks()
                sw = help_win.winfo_screenwidth()
                help_win.geometry(f"+{(sw-900)//2}+120")

                # 顶部标题栏
                title_frame = tk.Frame(help_win, bg="#2C3E50", height=50)
                title_frame.pack(fill=tk.X, side=tk.TOP)
                title_frame.pack_propagate(False)
                tk.Label(title_frame, text="📖 图像分析 · 六大图表说明", bg="#2C3E50", fg="white",
                         font=("Microsoft YaHei", 16, "bold")).pack(side=tk.LEFT, padx=20, pady=8)
                tk.Label(title_frame, text="鼠标悬停查看详情 · 点击卡片缩放", bg="#2C3E50", fg="#BDC3C7",
                         font=("", 10)).pack(side=tk.RIGHT, padx=20)

                # 帮助条目 (6 个)
                HELP_ITEMS = [
                    ("📈 日K线", "#E74C3C", "标准蜡烛图 + MA5/10/20/60 均线。\n最基础的技术分析视图，看多空排列和均线关系。",
                     "• 红涨绿跌（A股习惯）\n• MA20/MA60 判断趋势方向\n• 配合一目均衡更准"),
                    ("📊 一目均衡", "#3498DB", "Ichimoku Kinko Hyo — 一目均衡表。\n日本最流行的趋势判断工具，看云图多空区。",
                     "• 5 条线：转换/基准/先行A/B/迟行\n• Kumo 云 = 未来 26 天预测区\n• 红云看涨，绿云看跌"),
                    ("📉 BOLL带", "#9B59B6", "布林带 Bollinger Bands。\n标准差通道，判断波动区间和突破。",
                     "• 20日均线 ± 2倍标准差\n• 带宽收缩 = 变盘在即\n• 价格触上轨卖出，触下轨买入"),
                    ("📦 成交量", "#1ABC9C", "蜡烛色量柱 + VOL_MA5/10。\n量能是价的先行指标，量价配合才可靠。",
                     "• 放量突破更可靠\n• 缩量上涨警惕回调\n• 量能背离 = 趋势乏力"),
                    ("📐 MACD", "#F39C12", "DIF/DEA 差离值 + MACD 柱。\n经典金叉死叉信号，判断趋势动量。",
                     "• DIF 上穿 DEA = 金叉买入\n• DIF 下穿 DEA = 死叉卖出\n• 零轴上方金叉更可靠"),
                    ("🎯 情绪复盘", "#E67E22", "市场整体情绪 + 仓位温度计。\n从涨跌家数、涨停跌停判断市场温度。",
                     "• 上涨家数 > 60% = 强势市场\n• 涨停多 = 情绪亢奋\n• 建议仓位 = 情绪 × 周期"),
                    ("📊 ETF强弱", "#27AE60", "22 只主流 ETF 5日×0.6 + 20日×0.4 综合评分。\n横向条形图一眼看清最强最弱板块。",
                     "• 红条 = 近期强势板块\n• 绿条 = 近期弱势板块\n• 最强顺势，最弱规避"),
                ]

                # 滚动区 (Canvas + Frame)
                outer = tk.Frame(help_win, bg="#FAFAFA")
                outer.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
                canvas = tk.Canvas(outer, bg="#FAFAFA", highlightthickness=0)
                sb = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
                inner = tk.Frame(canvas, bg="#FAFAFA")
                inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
                canvas.create_window((0, 0), window=inner, anchor="nw")
                canvas.configure(yscrollcommand=sb.set)
                canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)

                # 3 列网格
                ncols = 3
                card_w = 275
                for i, (title, color, summary, detail) in enumerate(HELP_ITEMS):
                    r, c = divmod(i, ncols)
                    card = tk.Frame(inner, bg="white", highlightbackground="#E0E0E0", highlightthickness=1,
                                    width=card_w, bd=0)
                    card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
                    inner.grid_columnconfigure(c, weight=1)
                    # 彩色标题条
                    tk.Frame(card, bg=color, height=4).pack(fill=tk.X)
                    tk.Label(card, text=title, bg="white", fg=color,
                             font=("Microsoft YaHei", 13, "bold")).pack(anchor="w", padx=14, pady=(10, 4))
                    # summary
                    tk.Label(card, text=summary, bg="white", fg="#333", wraplength=card_w-28,
                             justify="left", font=("", 10)).pack(anchor="w", padx=14, pady=(0, 8))
                    # 分割线
                    tk.Frame(card, bg="#EEEEEE", height=1).pack(fill=tk.X, padx=14)
                    # detail (小字号)
                    tk.Label(card, text=detail, bg="white", fg="#666", wraplength=card_w-28,
                             justify="left", font=("", 9)).pack(anchor="w", padx=14, pady=(6, 10))

                # 鼠标滚轮
                def _on_mousewheel(evt): canvas.yview_scroll(int(-evt.delta/120), "units")
                canvas.bind_all("<MouseWheel>", _on_mousewheel)
                help_win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

            help_btn = ttk.Button(top, text="❓帮助", width=7, command=_show_chart_help)
            help_btn.pack(side=tk.LEFT, padx=(4, 4))
            # 🆕 ETF 联动分析按钮 — 打开三列 ETF→持仓股→K线 弹窗
            etf_btn = ttk.Button(top, text="📊ETF联动", width=10,
                                 command=lambda: self._show_etf_link_dialog())
            etf_btn.pack(side=tk.LEFT, padx=(0, 4))
            status_var = tk.StringVar(value="")
            ttk.Label(top, textvariable=status_var, foreground="gray").pack(side=tk.LEFT, padx=8)

            # ── 主绘图区 ──
            chart_area = tk.Frame(win); chart_area.pack(fill=tk.BOTH, expand=True)
            fig = Figure(figsize=(12, 16), dpi=100, facecolor="#FAFAFA")
            canvas = FigureCanvasTkAgg(fig, chart_area); canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, side=tk.TOP)
            # matplotlib 工具栏 (缩放/平移/保存)
            mpl_tb = NavigationToolbar2Tk(canvas, chart_area); mpl_tb.update()
            mpl_tb.pack(side=tk.BOTTOM, fill=tk.X)

            # ── 辅助函数: 解析 symbol → tushare code + is_index ──
            def _parse_symbol(raw):
                """解析 symbol → (sina_code, tushare_code, is_index, display_name)
                支持格式:
                  [指数] 上证指数(sh000001)
                  [持仓] 贵州茅台(sh600519)
                  [手动] 自定义(sh600519)
                  或直接输入: sh600519 / sz399001 / 600519
                """
                raw = (search_var.get().strip() or sym_var.get().strip())
                # 从最后一个 (...) 中提取 code
                import re
                m = re.search(r'\(([^()]+)\)\s*$', raw)
                if m:
                    code = m.group(1).strip()
                    # 提取名字: ] XXX( 中间的 XXX
                    m2 = re.search(r'\]\s*([^\(\[]+?)\s*\(', raw)
                    display = m2.group(1).strip() if m2 else raw.split("(")[0].strip()
                    if display.startswith("自定义"):
                        # 只从 code 推导显示名
                        display = code
                else:
                    # 纯代码输入
                    code = raw.strip()
                    display = code

                # code 归一化: 纯 6 位数字 → 补 sina 前缀
                if code.isdigit() and len(code) == 6:
                    code = f"sh{code}" if code.startswith(("6","9","000","399")) else f"sz{code}"

                # 判断是否指数
                is_index = code.startswith("sh000") or code.startswith("sz399")

                # tushare 代码: sh000001 → 000001.SH, sh600519 → 600519.SH
                if is_index:
                    ts_code = f"{code[2:]}.SH" if code.startswith("sh") else f"{code[2:]}.SZ"
                else:
                    digits = code[2:] if code.startswith(("sh","sz")) else code
                    if digits.startswith(("6","9")): ts_code = f"{digits}.SH"
                    else: ts_code = f"{digits}.SZ"
                return code, ts_code, is_index, display

            # ── 辅助函数: 计算技术指标 ──
            def _ma(series, n):
                s = pd.Series(series)
                return s.rolling(n).mean().values
            def _ema(series, n):
                s = pd.Series(series)
                return s.ewm(span=n, adjust=False).mean().values
            def _boll(series, n=20, k=2):
                s = pd.Series(series)
                mid = s.rolling(n).mean()
                std = s.rolling(n).std()
                return mid.values, (mid + k*std).values, (mid - k*std).values
            def _macd(close, f=12, s=26, m=9):
                c = pd.Series(close)
                ema_f = c.ewm(span=f, adjust=False).mean()
                ema_s = c.ewm(span=s, adjust=False).mean()
                dif = ema_f - ema_s
                dea = dif.ewm(span=m, adjust=False).mean()
                macd_hist = (dif - dea) * 2
                return dif.values, dea.values, macd_hist.values
            def _compute_regime(closes, highs, lows):
                """每根K线计算多空得分: +1=看多红, -1=看空绿, 0=中性"""
                s = pd.Series(closes)
                n = len(closes)
                ma20 = _ma(closes, 20); ma60 = _ma(closes, 60)
                dif, dea, _h = _macd(closes)
                # 简易 RSI
                delta = s.diff(); gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
                rs = gain.rolling(14).mean() / loss.rolling(14).mean()
                rsi = 100 - 100 / (1 + rs)
                scores = np.zeros(n, dtype=float)
                for i in range(n):
                    bull = 0; bear = 0; total = 0
                    # 价格 > MA20
                    if not np.isnan(ma20[i]):
                        total += 2
                        if closes[i] > ma20[i]: bull += 2
                        else: bear += 2
                    # MA20 > MA60
                    if not np.isnan(ma20[i]) and not np.isnan(ma60[i]):
                        total += 2
                        if ma20[i] > ma60[i]: bull += 2
                        else: bear += 2
                    # MACD 金叉
                    if not np.isnan(dif[i]) and not np.isnan(dea[i]):
                        total += 2
                        if dif[i] > dea[i]: bull += 2
                        else: bear += 2
                    # RSI (nan 不计入)
                    if not np.isnan(rsi.iloc[i]):
                        total += 2
                        if rsi.iloc[i] > 55: bull += 2
                        elif rsi.iloc[i] < 45: bear += 2
                    if total == 0:
                        scores[i] = 0
                    else:
                        scores[i] = (bull - bear) / total  # -1.0 ~ +1.0
                # 平滑避免抖动
                smooth = pd.Series(scores).rolling(5, min_periods=1).mean().values
                return smooth
            def _draw_regime_bg(ax, x, regime, y_lo=None, y_hi=None):
                """在 ax 上画浅红/浅绿背景带"""
                if y_lo is None or y_hi is None:
                    yl = ax.get_ylim(); y_lo, y_hi = yl[0], yl[1]
                ax.fill_between(x, y_lo, y_hi, where=regime > 0,
                                color="#FFCDD2", alpha=0.45, zorder=0)
                ax.fill_between(x, y_lo, y_hi, where=regime < 0,
                                color="#C8E6C9", alpha=0.45, zorder=0)

            def _find_support_resistance(highs, lows, n_levels=3):
                """ZigZag 式局部极值 → 聚类合并 → 返回 (supports, resistances)
                每个都是 [(x_idx, price), ...] 按价格排序, 取最近 n_levels 条
                """
                n = len(highs)
                if n < 20: return [], []
                # 1. 找局部高点 (左右各 5 根内最高)
                peaks = []; troughs = []
                w = 5  # 左右窗口
                for i in range(w, n - w):
                    if highs[i] == max(highs[i-w:i+w+1]):
                        peaks.append((i, highs[i]))
                    if lows[i] == min(lows[i-w:i+w+1]):
                        troughs.append((i, lows[i]))
                # 2. 聚类: 相邻峰/谷价格差 < 1% 合并
                def _cluster(points):
                    if not points: return []
                    pts = sorted(points, key=lambda p: p[1])
                    merged = [pts[0]]
                    for x_idx, price in pts[1:]:
                        if abs(price - merged[-1][1]) / merged[-1][1] < 0.01:
                            # 合并: 取平均价, 保留第一个的 x
                            prev_x, prev_p = merged[-1]
                            merged[-1] = (prev_x, (prev_p + price) / 2)
                        else:
                            merged.append((x_idx, price))
                    return merged
                peaks_c = _cluster(peaks)
                troughs_c = _cluster(troughs)
                # 3. 取最近的: 离最后一根 K 线最近的 n_levels 条
                def _recent(points):
                    if not points: return []
                    points_sorted = sorted(points, key=lambda p: -p[0])  # x 降序
                    return points_sorted[:n_levels]
                return _recent(troughs_c), _recent(peaks_c)  # 支撑, 压力

            def _find_trade_signals(closes, highs, lows):
                """MACD 金叉/死叉 + MA20 过滤 → 返回 [(x, price, 'BUY'/'SELL'), ...]"""
                n = len(closes)
                if n < 30: return []
                def _ma(s, p): return pd.Series(s).rolling(p).mean().values
                def _macd(c, f=12, se=26, m=9):
                    cp = pd.Series(c)
                    ef = cp.ewm(span=f, adjust=False).mean()
                    es = cp.ewm(span=se, adjust=False).mean()
                    d = ef - es; de = d.ewm(span=m, adjust=False).mean()
                    return d.values, de.values
                ma20 = _ma(closes, 20)
                dif, dea = _macd(closes)
                signals = []
                for i in range(1, n):
                    if np.isnan(dif[i]) or np.isnan(dif[i-1]) or np.isnan(dea[i]) or np.isnan(dea[i-1]):
                        continue
                    # 金叉: dif 上穿 dea
                    if dif[i-1] <= dea[i-1] and dif[i] > dea[i]:
                        # 买点确认: 价格在 MA20 之上, 且不是太近 (避免重复)
                        if not np.isnan(ma20[i]) and closes[i] > ma20[i]:
                            if not signals or i - signals[-1][0] > 3:
                                signals.append((i, lows[i], "BUY"))
                    # 死叉: dif 下穿 dea
                    elif dif[i-1] >= dea[i-1] and dif[i] < dea[i]:
                        if not np.isnan(ma20[i]) and closes[i] < ma20[i]:
                            if not signals or i - signals[-1][0] > 3:
                                signals.append((i, highs[i], "SELL"))
                return signals

            # ── 主刷新函数 ──
            def _refresh():
                import pandas as pd
                fig.clear()
                selected = [k for k,v in chart_vars.items() if v.get()]
                if not selected:
                    status_var.set("⚠️ 请至少选一个图表类型"); canvas.draw(); return
                raw_sym, ts_code, is_index, display_name = _parse_symbol(sym_var.get())
                status_var.set(f"⏳ 加载 {display_name} ({ts_code})...")
                win.update_idletasks()

                try:
                    # 拉取日K数据 (用一目均衡的成熟 fallback 链, 自动 150+ 根)
                    kdf = self._fetch_ichimoku_kline_data(raw_sym, period="daily", is_index=is_index)
                    if kdf is None or len(kdf) < 60:
                        # fallback: tushare 直接拉
                        if not is_index:
                            kdf = self._get_daily_kline_data_tushare(raw_sym if not raw_sym.startswith("sh") and not raw_sym.startswith("sz") else raw_sym[2:], days=200)
                        if kdf is None or len(kdf) < 60:
                            status_var.set(f"❌ 数据不足 ({len(kdf) if kdf is not None else 0} 根)"); canvas.draw(); return

                    # 统一列名
                    if "日期" in kdf.columns: dates_str = kdf["日期"].tolist()
                    elif "trade_date" in kdf.columns: dates_str = kdf["trade_date"].tolist()
                    else: dates_str = list(range(len(kdf)))
                    opens  = kdf["开盘"].astype(float).values if "开盘" in kdf.columns else kdf["open"].astype(float).values
                    highs  = kdf["最高"].astype(float).values if "最高" in kdf.columns else kdf["high"].astype(float).values
                    lows   = kdf["最低"].astype(float).values if "最低" in kdf.columns else kdf["low"].astype(float).values
                    closes = kdf["收盘"].astype(float).values if "收盘" in kdf.columns else kdf["close"].astype(float).values
                    vols   = kdf["成交量"].astype(float).values if "成交量" in kdf.columns else (kdf["vol"].astype(float).values if "vol" in kdf.columns else np.zeros_like(closes))

                    # 统一 dates 为数值索引 (matplotlib 兼容)
                    n = len(closes)
                    x = np.arange(n)

                    # 计算多空状态 (一次, 给所有图复用)
                    try:
                        regime = _compute_regime(closes, highs, lows)
                    except Exception:
                        regime = np.zeros(n)  # fallback: 全中性

                    # 计算支撑压力 + 买卖点 (一次, 复用)
                    try:
                        supports, resistances = _find_support_resistance(highs, lows, n_levels=3)
                    except Exception:
                        supports, resistances = [], []
                    try:
                        trade_signals = _find_trade_signals(closes, highs, lows)
                    except Exception:
                        trade_signals = []

                    # 布局计算: 简单网格, emotion/etf_rank 不再独占整行, 和普通图一样占一格
                    n_charts = len(selected)
                    if n_charts == 1: nrows, ncols = 1, 1
                    elif n_charts == 2: nrows, ncols = 2, 1
                    elif n_charts <= 4: nrows, ncols = 2, 2
                    elif n_charts <= 6: nrows, ncols = 3, 2
                    elif n_charts <= 9: nrows, ncols = 3, 3
                    else: nrows, ncols = 4, 3
                    # 全部行高一样, 让情绪复盘 + ETF 强弱 并排一行和上面 K 线同尺寸
                    height_ratios = [4.5] * nrows
                    fig_h = max(10, sum(height_ratios) * 1.2)
                    fig.set_size_inches(12, fig_h)
                    from matplotlib import gridspec
                    gs = gridspec.GridSpec(nrows, ncols, figure=fig, height_ratios=height_ratios,
                                           hspace=0.45, wspace=0.30)

                    idx = 0
                    for k in selected:
                        r, c = divmod(idx, ncols)
                        # 所有图统一占一格, 包括 emotion/etf_rank
                        ax = fig.add_subplot(gs[r, c])
                        idx += 1
                        ax.set_facecolor("#FFFFFF"); ax.grid(True, alpha=0.2)
                        _skip_regime = False  # 默认值, emotion/etf_rank case 会改成 True

                        if k == "daily_k":
                            # 标准日K + MA5/10/20/60
                            up_col, dn_col = "#EF5350", "#66BB6A"
                            for i in range(n):
                                col = up_col if closes[i] >= opens[i] else dn_col
                                ax.plot([x[i],x[i]], [lows[i], highs[i]], color=col, lw=0.8)
                                ax.bar(x[i], closes[i]-opens[i], bottom=opens[i], color=col, width=0.6)
                            # MA
                            ma5, ma10, ma20, ma60 = _ma(closes,5), _ma(closes,10), _ma(closes,20), _ma(closes,60)
                            ax.plot(x, ma5, color="#FFC107", lw=1.0, label="MA5")
                            ax.plot(x, ma10, color="#2196F3", lw=1.0, label="MA10")
                            ax.plot(x, ma20, color="#9C27B0", lw=1.2, label="MA20")
                            ax.plot(x, ma60, color="#FF5722", lw=1.2, label="MA60")
                            ax.set_title(f"📈 日K线 · {display_name}", fontsize=11, fontweight="bold")
                            ax.legend(fontsize=7, loc="upper left", ncol=4)
                            ax.set_ylabel("价格")

                        elif k == "ichimoku":
                            # 先画 K 线蜡烛 (和 daily_k 同方式)
                            up_col, dn_col = "#EF5350", "#66BB6A"
                            for i in range(n):
                                col = up_col if closes[i] >= opens[i] else dn_col
                                ax.plot([x[i],x[i]], [lows[i], highs[i]], color=col, lw=0.8)
                                ax.bar(x[i], closes[i]-opens[i], bottom=opens[i], color=col, width=0.6)
                            # 再叠加一目均衡 (tenkan/kijun 用 x, Kumo 云用 extended_x 自动右移 26)
                            self._plot_ichimoku_ax(ax, x, highs, lows, closes, show_explanation=False)
                            ax.set_title(f"📊 一目均衡 · {display_name}", fontsize=11, fontweight="bold")
                            ax.legend(fontsize=7, loc="upper left")
                            ax.set_ylabel("价格")

                        elif k == "boll":
                            # 主图 + BOLL 带
                            up_col, dn_col = "#EF5350", "#66BB6A"
                            for i in range(n):
                                col = up_col if closes[i] >= opens[i] else dn_col
                                ax.plot([x[i],x[i]], [lows[i], highs[i]], color=col, lw=0.8)
                                ax.bar(x[i], closes[i]-opens[i], bottom=opens[i], color=col, width=0.6)
                            mid, top, bot = _boll(closes, 20, 2)
                            ax.plot(x, mid, color="#2196F3", lw=1.0, label="MID")
                            ax.plot(x, top, color="#FF9800", lw=0.8, ls="--", label="UPPER")
                            ax.plot(x, bot, color="#4CAF50", lw=0.8, ls="--", label="LOWER")
                            ax.fill_between(x, bot, top, alpha=0.08, color="#2196F3")
                            ax.set_title(f"📉 BOLL带 · {display_name}", fontsize=11, fontweight="bold")
                            ax.legend(fontsize=7, loc="upper left")
                            ax.set_ylabel("价格")

                        elif k == "vol":
                            up_col, dn_col = "#EF5350", "#66BB6A"
                            colors = [up_col if closes[i] >= opens[i] else dn_col for i in range(n)]
                            ax.bar(x, vols, color=colors, width=0.6, alpha=0.8)
                            vol_ma5 = _ma(vols, 5); vol_ma10 = _ma(vols, 10)
                            ax.plot(x, vol_ma5, color="#FFC107", lw=1.0, label="VOL_MA5")
                            ax.plot(x, vol_ma10, color="#2196F3", lw=1.0, label="VOL_MA10")
                            ax.set_title(f"📦 成交量 · {display_name}", fontsize=11, fontweight="bold")
                            ax.legend(fontsize=7, loc="upper left")
                            ax.set_ylabel("VOL")

                        elif k == "macd":
                            dif, dea, hist = _macd(closes)
                            colors = ["#EF5350" if h >= 0 else "#66BB6A" for h in hist]
                            ax.bar(x, hist, color=colors, width=0.6, alpha=0.8)
                            ax.plot(x, dif, color="#FF9800", lw=1.0, label="DIF")
                            ax.plot(x, dea, color="#2196F3", lw=1.0, label="DEA")
                            ax.axhline(0, color="#999", lw=0.5)
                            ax.set_title(f"📐 MACD · {display_name}", fontsize=11, fontweight="bold")
                            ax.legend(fontsize=7, loc="upper left")
                            ax.set_ylabel("MACD")

                        elif k == "moneyflow":
                            # 简单资金流向: (close - open) * volume 近似 + OBV
                            money_flow = (closes - opens) * vols
                            colors = ["#EF5350" if m >= 0 else "#66BB6A" for m in money_flow]
                            ax.bar(x, money_flow, color=colors, width=0.6, alpha=0.8)
                            mf_ma5 = _ma(money_flow, 5); mf_ma10 = _ma(money_flow, 10)
                            ax.plot(x, mf_ma5, color="#FFC107", lw=1.2, label="MF_MA5")
                            ax.plot(x, mf_ma10, color="#9C27B0", lw=1.2, label="MF_MA10")
                            ax.axhline(0, color="#999", lw=0.5)
                            ax.set_title(f"💵 资金流向(近似) · {display_name}", fontsize=11, fontweight="bold")
                            ax.legend(fontsize=7, loc="upper left")
                            ax.set_ylabel("Money Flow")

                        elif k == "emotion":
                            # 🎯 情绪复盘 — 紧凑文字面板 (占一格, 与 ETF 并排)
                            ax.axis("off")
                            _skip_regime = True

                            emo_cycle = getattr(self, "emotion_cycle_var", None)
                            cycle_text = emo_cycle.get() if emo_cycle else "未获取"
                            cycle_color = {"上行": "#E53935", "震荡": "#FB8C00", "下行": "#43A047"}.get(cycle_text, "#9E9E9E")

                            snap = getattr(self, "_last_sentiment_zone_snapshot", None)
                            m = snap.get("metrics", {}) if snap else {}
                            m2 = m.get("m2_market", {}) if isinstance(m, dict) else {}
                            up_cnt = m2.get("up", "—") if isinstance(m2, dict) else "—"
                            dn_cnt = m2.get("down", "—") if isinstance(m2, dict) else "—"
                            flat_cnt = m2.get("flat", "—") if isinstance(m2, dict) else "—"
                            m5_hs300_v = m.get("m5_hs300", {}).get("value") if isinstance(m.get("m5_hs300"), dict) else None
                            m5_zz500_v = m.get("m5_zz500", {}).get("value") if isinstance(m.get("m5_zz500"), dict) else None

                            try:
                                total = int(up_cnt) + int(dn_cnt) + int(flat_cnt)
                                emo_score = round(int(up_cnt) / total * 100, 1) if total > 0 else 50
                            except Exception:
                                emo_score = 50.0

                            cycle_position = {"上行": 80, "震荡": 50, "下行": 20}.get(cycle_text, 50)
                            temperature = round((cycle_position + emo_score) / 2)
                            temp_color = "#E53935" if temperature >= 70 else ("#FB8C00" if temperature >= 40 else "#43A047")
                            emo_label = "贪婪" if emo_score > 70 else ("中性" if emo_score > 40 else "恐惧")

                            hs300_s = f"{m5_hs300_v:+.2f}%" if isinstance(m5_hs300_v, (int, float)) else "—"
                            zz500_s = f"{m5_zz500_v:+.2f}%" if isinstance(m5_zz500_v, (int, float)) else "—"

                            # 标题
                            ax.text(0.02, 0.97, "🎯 情绪复盘", transform=ax.transAxes,
                                    fontsize=11, fontweight="bold", va="top", ha="left", color="#263238")
                            ax.plot([0.02, 0.98], [0.93, 0.93], color="#E0E0E0", lw=1, transform=ax.transAxes)
                            # 主体文字块
                            lines = [
                                f"🕐 {snap.get('time','未刷新') if snap else '未刷新'}",
                                f"🎯 周期: {cycle_text}",
                                f"📈 涨跌: 上{up_cnt}  下{dn_cnt}  平{flat_cnt}",
                                f"📊 沪深300: {hs300_s}",
                                f"📊 中证500: {zz500_s}",
                            ]
                            ax.text(0.02, 0.90, "\n".join(lines), transform=ax.transAxes,
                                    fontsize=9.5, va="top", ha="left", linespacing=1.45)
                            # 情绪分数卡片
                            score_bg = "#FFEBEE" if emo_score > 70 else ("#FFF3E0" if emo_score > 40 else "#E8F5E9")
                            ax.text(0.02, 0.38, "情绪分数", transform=ax.transAxes,
                                    fontsize=8, va="top", ha="left", color="#666")
                            ax.text(0.02, 0.32, f"{emo_score:.0f} · {emo_label}",
                                    transform=ax.transAxes, fontsize=15, fontweight="bold",
                                    va="top", ha="left", color=temp_color,
                                    bbox=dict(boxstyle="round,pad=0.25", fc=score_bg,
                                              ec=temp_color, alpha=0.9, lw=1.2))
                            # 仓位建议卡片
                            ax.text(0.62, 0.38, "建议仓位", transform=ax.transAxes,
                                    fontsize=8, va="top", ha="left", color="#666")
                            ax.text(0.62, 0.32, f"{temperature}%", transform=ax.transAxes,
                                    fontsize=15, fontweight="bold", va="top", ha="left",
                                    color=temp_color,
                                    bbox=dict(boxstyle="round,pad=0.25", fc=score_bg,
                                              ec=temp_color, alpha=0.9, lw=1.2))
                            # 底部总结
                            ax.text(0.5, 0.06, f"💡 {cycle_text} · {emo_label}",
                                    transform=ax.transAxes, fontsize=10, fontweight="bold",
                                    ha="center", va="center", color=cycle_color,
                                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=cycle_color, lw=1.5))

                        elif k == "etf_rank":
                            # 📊 ETF 板块强弱 — 纯文字 TOP5/BOTTOM5 列表 (占一格, 与情绪并排)
                            ax.axis("off")
                            _skip_regime = True

                            ETF_LIST = [
                                ("510300.SH","沪深300"),("510500.SH","中证500"),("159915.SZ","创业板"),
                                ("588000.SH","科创50"),("510050.SH","上证50"),("512100.SH","中证1000"),
                                ("512880.SH","证券"),("512000.SH","银行"),("512010.SH","医药"),
                                ("510880.SH","红利"),("159928.SZ","消费"),("159875.SZ","新能源"),
                                ("512480.SH","半导体"),("512660.SH","军工"),("515790.SH","光伏"),
                                ("512400.SH","有色"),("515220.SH","煤炭"),("512690.SH","酒"),
                                ("513100.SH","纳指"),("513500.SH","标普"),("513520.SH","日经"),
                                ("513180.SH","恒生科技"),
                            ]
                            try:
                                import time as _time
                                import tushare as ts
                                from utils.config import TS_DEFAULT_TOKEN
                                cache = getattr(self, "_etf_rank_cache", None)
                                if cache and (_time.time() - cache[0]) < 1800:
                                    etf_results = cache[1]
                                else:
                                    if not getattr(self, "_ts_pro_init", False):
                                        ts.set_token(TS_DEFAULT_TOKEN)
                                        self._ts_pro = ts.pro_api()
                                        self._ts_pro_init = True
                                    etf_results = []
                                    for ecode, ename in ETF_LIST:
                                        try:
                                            edf = self._ts_pro.fund_daily(ts_code=ecode,
                                                                          start_date="20260901", end_date="20261101")
                                            if edf is None or len(edf) < 21: continue
                                            edf = edf.sort_values("trade_date").reset_index(drop=True)
                                            ecloses = edf["close"].astype(float).values
                                            r5 = (ecloses[-1]/ecloses[-6]-1)*100 if len(ecloses)>=6 else np.nan
                                            r20 = (ecloses[-1]/ecloses[-21]-1)*100 if len(ecloses)>=21 else np.nan
                                            if np.isnan(r5) or np.isnan(r20): continue
                                            score = r5*0.6 + r20*0.4
                                            etf_results.append((score, ename, r5, r20))
                                        except Exception:
                                            pass
                                    etf_results.sort(reverse=True)
                                    self._etf_rank_cache = (_time.time(), etf_results)
                            except Exception:
                                etf_results = []

                            if etf_results:
                                # 🔥 纯文字 TOP5 / BOTTOM5
                                top5 = etf_results[:5]
                                bot5 = etf_results[-5:]

                                # 标题
                                ax.text(0.02, 0.97, "📊 ETF 板块强弱", transform=ax.transAxes,
                                        fontsize=11, fontweight="bold", va="top", ha="left", color="#263238")
                                ax.plot([0.02, 0.98], [0.93, 0.93], color="#E0E0E0", lw=1, transform=ax.transAxes)

                                # 🔥 TOP5 强势 (红)
                                ax.text(0.02, 0.89, "🔥 TOP5 强势", transform=ax.transAxes,
                                        fontsize=9, fontweight="bold", va="top", ha="left", color="#C62828")
                                top_lines = []
                                for i, (s, n, r5, r20) in enumerate(top5):
                                    top_lines.append(f"  {i+1}. {n:<5s}  5日{r5:+.1f}%  20日{r20:+.1f}%  得分{s:+.2f}")
                                ax.text(0.02, 0.86, "\n".join(top_lines), transform=ax.transAxes,
                                        fontsize=8.5, va="top", ha="left", linespacing=1.45,
                                        color="#C62828")

                                # ❄️ BOTTOM5 弱势 (绿)
                                ax.text(0.02, 0.48, "❄️ BOTTOM5 弱势", transform=ax.transAxes,
                                        fontsize=9, fontweight="bold", va="top", ha="left", color="#2E7D32")
                                bot_lines = []
                                for i, (s, n, r5, r20) in enumerate(reversed(bot5)):
                                    bot_lines.append(f"  {len(etf_results)-i}. {n:<5s}  5日{r5:+.1f}%  20日{r20:+.1f}%  得分{s:+.2f}")
                                ax.text(0.02, 0.45, "\n".join(bot_lines), transform=ax.transAxes,
                                        fontsize=8.5, va="top", ha="left", linespacing=1.45,
                                        color="#2E7D32")

                                # 💡 建议
                                top_name = top5[0][1]; bot_name = etf_results[-1][1]
                                ax.text(0.5, 0.06,
                                        f"💡 顺势 {top_name}  ·  规避 {bot_name}",
                                        transform=ax.transAxes, fontsize=10, fontweight="bold",
                                        ha="center", va="center", color="#1565C0",
                                        bbox=dict(boxstyle="round,pad=0.3", fc="#E3F2FD", ec="#90CAF9", alpha=0.95))
                            else:
                                ax.text(0.5, 0.5, "ETF 数据加载失败\n(检查主界面联网 / tushare token)",
                                        transform=ax.transAxes, fontsize=10, ha="center", va="center", color="#999")

                        # 🎨 多空背景带 (浅红看多 / 浅绿看空) — 跳过 emotion/etf_rank
                        ax.autoscale_view()
                        if not _skip_regime:
                            _draw_regime_bg(ax, x, regime)
                            ax.set_ylim(ax.get_ylim())

                        # 📏 支撑压力线 + 买卖点标记 (只在主图类型显示)
                        if k in ("daily_k", "ichimoku", "boll"):
                            # 支撑线: 青绿色虚线
                            for sx_idx, sp in supports:
                                ax.axhline(y=sp, color="#00BCD4", ls="--", lw=0.9, alpha=0.7, zorder=4)
                                ax.annotate(f"支撑 {sp:.1f}", xy=(n-1, sp),
                                            xytext=(4, -14), textcoords="offset points",
                                            fontsize=8, color="#00838F", fontweight="bold",
                                            backgroundcolor="#E0F7FA", alpha=0.8, zorder=6)
                            # 压力线: 橙色虚线
                            for rx_idx, rp in resistances:
                                ax.axhline(y=rp, color="#FF9800", ls="--", lw=0.9, alpha=0.7, zorder=4)
                                ax.annotate(f"压力 {rp:.1f}", xy=(n-1, rp),
                                            xytext=(4, 6), textcoords="offset points",
                                            fontsize=8, color="#E65100", fontweight="bold",
                                            backgroundcolor="#FFF3E0", alpha=0.8, zorder=6)
                            # 买点: 🟢 红三角 (底部向上指)
                            for tx_idx, tp, ttype in trade_signals:
                                if ttype == "BUY":
                                    ax.annotate("⬆买", xy=(tx_idx, tp), xytext=(0, -22),
                                                textcoords="offset points", fontsize=8,
                                                color="#D32F2F", fontweight="bold", ha="center",
                                                arrowprops=dict(arrowstyle="->", color="#D32F2F", lw=1.2),
                                                bbox=dict(boxstyle="round,pad=0.2", fc="#FFEBEE", ec="#D32F2F", alpha=0.9),
                                                zorder=7)
                                else:
                                    ax.annotate("⬇卖", xy=(tx_idx, tp), xytext=(0, 22),
                                                textcoords="offset points", fontsize=8,
                                                color="#388E3C", fontweight="bold", ha="center",
                                                arrowprops=dict(arrowstyle="->", color="#388E3C", lw=1.2),
                                                bbox=dict(boxstyle="round,pad=0.2", fc="#E8F5E9", ec="#388E3C", alpha=0.9),
                                                zorder=7)

                        # 统一: x 轴日期稀疏显示
                        step = max(1, n // 12)
                        tick_idx = list(range(0, n, step)) + [n-1]
                        tick_idx = sorted(set(tick_idx))
                        if len(dates_str) == n:
                            tick_labels = [str(dates_str[i])[-8:] if len(str(dates_str[i]))>=8 else str(dates_str[i]) for i in tick_idx]
                        else:
                            tick_labels = [str(x[i]) for i in tick_idx]
                        ax.set_xticks([x[i] for i in tick_idx])
                        ax.set_xticklabels(tick_labels, rotation=30, fontsize=7)

                    # 注意: idx 已在循环开头的 gs 分配代码里递增, 这里不再 +=1

                    fig.suptitle(f"🖼️ 图像分析 · {display_name} · {ts_code} · {n} 根日K",
                                 fontsize=13, fontweight="bold", y=0.995)
                    canvas.draw()
                    status_var.set(f"✅ {n} 根K线 · {n_charts} 图 · {display_name}")

                except Exception as e:
                    _tb_img.print_exc()
                    status_var.set(f"❌ {e}"); canvas.draw()

            refresh_btn.config(command=_refresh)
            sym_combo.bind("<<ComboboxSelected>>", lambda e: _refresh())
            win.bind("<Control-r>", lambda e: _refresh())
            # 首次加载
            win.after(200, _refresh)

        except Exception as e:
            import traceback; traceback.print_exc()
            messagebox.showerror("错误", f"打开图像分析失败: {e}", parent=getattr(self, 'root', None))

    # ═══════════════════════════════════════════════════════════════════
    # 🏷️ 标签库 + 📚 文章库 — 完整实现
    # ═══════════════════════════════════════════════════════════════════

    # ── DB 路径 + 预设标签 ──
    _ARTICLE_DB = "/Users/faronpan/Agent/stockyidong_project/data/stock_analysis.db"
    _PRESET_TAGS = [
        # 技术形态 (红橙系)
        ("大涨", "技术形态", "#F44336"), ("大跌", "技术形态", "#4CAF50"),
        ("涨停", "技术形态", "#FF5722"), ("跌停", "技术形态", "#00BCD4"),
        ("连板", "技术形态", "#E91E63"), ("突破", "技术形态", "#9C27B0"),
        ("回调", "技术形态", "#3F51B5"), ("金叉", "技术形态", "#8BC34A"),
        ("死叉", "技术形态", "#FF9800"), ("底背离", "技术形态", "#00BCD4"),
        ("顶背离", "技术形态", "#FF5722"), ("缩量整理", "技术形态", "#607D8B"),
        ("V型反转", "技术形态", "#4CAF50"), ("箱体震荡", "技术形态", "#9E9E9E"),
        # 量价
        ("量增价涨", "量价", "#FF5722"), ("量增价跌", "量价", "#2196F3"),
        ("缩量上涨", "量价", "#8BC34A"), ("放量滞涨", "量价", "#FF9800"),
        ("巨量成交", "量价", "#E91E63"), ("地量见底", "量价", "#00BCD4"),
        # 资金情绪 (蓝绿系)
        ("主力净流入", "资金情绪", "#4CAF50"), ("主力净流出", "资金情绪", "#F44336"),
        ("北向增持", "资金情绪", "#8BC34A"), ("北向减持", "资金情绪", "#FF9800"),
        ("龙虎榜上榜", "资金情绪", "#9C27B0"), ("融资余额上升", "资金情绪", "#2196F3"),
        # 题材概念 (多彩)
        ("AI人工智能", "题材概念", "#2196F3"), ("半导体芯片", "题材概念", "#3F51B5"),
        ("新能源", "题材概念", "#8BC34A"), ("光伏", "题材概念", "#FFC107"),
        ("医药医疗", "题材概念", "#E91E63"), ("消费白酒", "题材概念", "#FF9800"),
        ("军工", "题材概念", "#607D8B"), ("机器人", "题材概念", "#00BCD4"),
        ("低空经济", "题材概念", "#9C27B0"), ("国产替代", "题材概念", "#4CAF50"),
        ("算力", "题材概念", "#795548"), ("储能", "题材概念", "#009688"),
        ("有色金属", "题材概念", "#FFD54F"), ("稀土", "题材概念", "#FF7043"),
        # 操作方向 (基本色)
        ("买入", "操作方向", "#4CAF50"), ("卖出", "操作方向", "#F44336"),
        ("持有", "操作方向", "#2196F3"), ("观望", "操作方向", "#9E9E9E"),
        ("抄底", "操作方向", "#00BCD4"), ("逃顶", "操作方向", "#FF9800"),
        ("止损", "操作方向", "#F44336"), ("加仓", "操作方向", "#8BC34A"),
    ]
    _TAG_CATEGORIES = ["技术形态", "量价", "资金情绪", "题材概念", "操作方向"]

    def _init_article_db(self):
        """首次调用时建表 + 插入预设标签"""
        import sqlite3 as _sql3
        conn = _sql3.connect(self._ARTICLE_DB)
        cur = conn.cursor()
        # 表 1: 标签库
        cur.execute("""CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT DEFAULT '技术形态',
            color TEXT DEFAULT '#1565C0',
            usage_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )""")
        # 表 2: 文章库
        cur.execute("""CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT, author TEXT, title TEXT, url TEXT,
            content TEXT, stock_code TEXT DEFAULT '', stock_name TEXT DEFAULT '',
            sentiment TEXT DEFAULT '', saved INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )""")
        # 表 3: 文章-标签关联 (多对多)
        cur.execute("""CREATE TABLE IF NOT EXISTS article_tags (
            article_id INTEGER, tag_id INTEGER,
            PRIMARY KEY (article_id, tag_id)
        )""")
        # 预设标签 (如果还没插过)
        cur.execute("SELECT COUNT(*) FROM tags")
        if cur.fetchone()[0] == 0:
            for name, cat, color in self._PRESET_TAGS:
                cur.execute("INSERT OR IGNORE INTO tags(name,category,color) VALUES(?,?,?)", (name, cat, color))
        conn.commit(); conn.close()

    # ── 爬取函数 (akshare) ──
    def _crawl_akshare_news(self, stock_code="", stock_name="", max_items=20):
        """爬取 akshare 个股新闻 + 研报 → 返回 list of dict"""
        results = []
        try:
            import akshare as ak
            code6 = stock_code.replace(".SH", "").replace(".SZ", "").replace("sh", "").replace("sz", "")
            if code6 and len(code6) == 6:
                # 个股新闻
                try:
                    df = ak.stock_news_em(symbol=code6)
                    if df is not None and len(df) > 0:
                        for _, row in df.head(max_items).iterrows():
                            results.append({
                                "source": "东方财富新闻",
                                "author": row.get("文章来源", "东财"),
                                "title": row.get("新闻标题", ""),
                                "url": row.get("新闻链接", ""),
                                "content": row.get("新闻内容", ""),
                                "stock_code": stock_code,
                                "stock_name": stock_name,
                                "created_at": str(row.get("发布时间", "")),
                            })
                except Exception: pass
                # 研报
                try:
                    df2 = ak.stock_research_report_em(symbol=code6)
                    if df2 is not None and len(df2) > 0:
                        for _, row in df2.head(max_items).iterrows():
                            results.append({
                                "source": "机构研报",
                                "author": row.get("机构名称", row.get("机构", "")),
                                "title": row.get("研报标题", row.get("标题", "")),
                                "url": "",
                                "content": f"评级: {row.get('评级', '')} | 目标价: {row.get('目标价', '')}",
                                "stock_code": stock_code,
                                "stock_name": stock_name,
                                "created_at": str(row.get("发布日期", row.get("日期", ""))),
                            })
                except Exception: pass
        except Exception as _e:
            print(f"[📚文章库❌爬取] {_e}", flush=True)
        # 全局热帖 (stock_comment_em)
        try:
            import akshare as ak
            df3 = ak.stock_comment_em()
            if df3 is not None and len(df3) > 0:
                for _, row in df3.head(max_items).iterrows():
                    results.append({
                        "source": "东财热帖",
                        "author": row.get("作者", ""),
                        "title": row.get("标题", row.get("帖子标题", "")),
                        "url": row.get("链接", row.get("帖子链接", "")),
                        "content": row.get("内容", ""),
                        "stock_code": "", "stock_name": "",
                        "created_at": str(row.get("时间", "")),
                    })
        except Exception: pass
        return results

    def _save_article_to_db(self, article):
        """保存一篇文章到 articles 表, 返回 article_id"""
        import sqlite3 as _sql3
        conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
        cur.execute("INSERT INTO articles(source,author,title,url,content,stock_code,stock_name,saved) VALUES(?,?,?,?,?,?,?,1)",
                    (article.get("source",""), article.get("author",""), article.get("title",""),
                     article.get("url",""), article.get("content",""),
                     article.get("stock_code",""), article.get("stock_name","")))
        aid = cur.lastrowid; conn.commit(); conn.close()
        return aid

    # ── 🏷️ 标签浮窗 (核心组件) ──
    def _show_tag_picker(self, parent, current_tag_ids=None, on_done=None):
        """弹出标签浮窗: Notebook 分类 + 搜索 + Checkbutton 多选
        返回选中的 tag_id list
        """
        import sqlite3 as _sql3
        current_tag_ids = set(current_tag_ids or [])
        conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
        cur.execute("SELECT id,name,category,color FROM tags ORDER BY category, name")
        all_tags = cur.fetchall()  # [(id,name,cat,color), ...]
        conn.close()

        win = tk.Toplevel(parent)
        win.title("🏷️ 选择标签"); win.geometry("520x480"); win.transient(parent); win.grab_set()
        # 让浮窗居中
        parent.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width()//2 - 260
        py = parent.winfo_rooty() + parent.winfo_height()//2 - 240
        win.geometry(f"+{max(0,px)}+{max(0,py)}")

        # 搜索框
        search_frame = ttk.Frame(win); search_frame.pack(fill=tk.X, padx=8, pady=(8, 4))
        ttk.Label(search_frame, text="🔍 搜索标签:").pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=4)

        # Notebook 分类 tab
        nb = ttk.Notebook(win); nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        check_vars = {}  # tag_id → BooleanVar
        check_widgets = {}  # tag_id → Checkbutton

        def _build_category_tab(cat_name):
            frame = ttk.Frame(nb)
            nb.add(frame, text=f"🏷️ {cat_name}")
            canvas = tk.Canvas(frame, highlightthickness=0)
            vs = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
            inner = ttk.Frame(canvas)
            inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0,0), window=inner, anchor="nw")
            canvas.configure(yscrollcommand=vs.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); vs.pack(side=tk.RIGHT, fill=tk.Y)
            # 放标签
            tags_in_cat = [(tid, tname, tcolor) for tid, tname, tcat, tcolor in all_tags if tcat == cat_name]
            for i, (tid, tname, tcolor) in enumerate(tags_in_cat):
                var = tk.BooleanVar(value=(tid in current_tag_ids))
                check_vars[tid] = var
                cb = ttk.Checkbutton(inner, text=tname, variable=var, width=12)
                cb.grid(row=i//3, column=i%3, sticky="w", padx=4, pady=2)
                # 给文字上色
                try:
                    # 用 tk 原生 Checkbutton 才能改前景色
                    cb.destroy()
                    cb2 = tk.Checkbutton(inner, text=tname, variable=var, fg=tcolor, activeforeground=tcolor,
                                        selectcolor="#FFFFFF", width=12, anchor="w")
                    cb2.grid(row=i//3, column=i%3, sticky="w", padx=4, pady=2)
                    check_widgets[tid] = cb2
                except Exception:
                    check_widgets[tid] = cb
            return frame, canvas, inner

        # 动态构建所有分类 tab
        tabs_info = {}
        for cat in self._TAG_CATEGORIES:
            t, cv, inner = _build_category_tab(cat)
            tabs_info[cat] = (t, cv, inner)

        # 底部已选标签展示
        sel_frame = ttk.Frame(win); sel_frame.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(sel_frame, text="已选:").pack(side=tk.LEFT)
        sel_label = ttk.Label(sel_frame, text="(无)", foreground="#666")
        sel_label.pack(side=tk.LEFT, padx=4)

        def _update_sel_label(*_):
            sel = [tid for tid, v in check_vars.items() if v.get()]
            names = []
            for tid in sel:
                for t in all_tags:
                    if t[0] == tid: names.append(t[1]); break
            sel_label.config(text=f"{len(sel)} 个标签: {', '.join(names[:6])}{'...' if len(names)>6 else ''}")

        # 绑定所有 var 变化
        for v in check_vars.values():
            v.trace_add("write", _update_sel_label)

        # 搜索过滤
        def _on_search(*_):
            kw = search_var.get().strip()
            for cat, (frame, canvas, inner) in tabs_info.items():
                for child in inner.winfo_children():
                    child.destroy()
                tags_in_cat = [(tid, tname, tcolor) for tid, tname, tcat, tcolor in all_tags
                               if tcat == cat and (kw in tname or not kw)]
                for i, (tid, tname, tcolor) in enumerate(tags_in_cat):
                    var = check_vars.get(tid) or tk.BooleanVar(value=(tid in current_tag_ids))
                    check_vars[tid] = var
                    cb = tk.Checkbutton(inner, text=tname, variable=var, fg=tcolor,
                                        activeforeground=tcolor, selectcolor="#FFFFFF", width=12, anchor="w")
                    cb.grid(row=i//3, column=i%3, sticky="w", padx=4, pady=2)

        search_var.trace_add("write", _on_search)

        # 按钮
        btns = ttk.Frame(win); btns.pack(fill=tk.X, padx=8, pady=8)
        result = {"tags": None}

        def _confirm():
            result["tags"] = [tid for tid, v in check_vars.items() if v.get()]
            if on_done: on_done(result["tags"])
            win.destroy()

        ttk.Button(btns, text="✅ 确定", command=_confirm, width=10).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btns, text="取消", command=win.destroy, width=10).pack(side=tk.RIGHT)
        ttk.Button(btns, text="🆕新增标签", width=10,
                  command=lambda: self._add_tag_inline(win, all_tags, tabs_info, check_vars, _on_search)).pack(side=tk.LEFT)

        win.wait_window()
        return result["tags"]

    def _add_tag_inline(self, parent, all_tags, tabs_info, check_vars, refresh_fn):
        """浮窗内快速新增标签"""
        name = simpledialog.askstring("🆕 新增标签", "标签名称:", parent=parent)
        if not name: return
        cat = simpledialog.askstring("🆕 新增标签", f"分类 ({'/'.join(self._TAG_CATEGORIES)}):",
                                     initialvalue="技术形态", parent=parent)
        if cat not in self._TAG_CATEGORIES: cat = "技术形态"
        import sqlite3 as _sql3
        conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO tags(name,category,color) VALUES(?,?,?)", (name, cat, "#1565C0"))
        conn.commit(); conn.close()
        messagebox.showinfo("✅", f"标签 '{name}' 已添加到 {cat} 分类", parent=parent)

    # ── 📚 文章库弹窗 ──
    def _show_article_library_dialog(self, prefill_stock_code="", prefill_stock_name=""):
        """完整文章库: 列表 + 筛选 + 爬取 + 查看 + 打标签"""
        self._init_article_db()
        import sqlite3 as _sql3
        win = tk.Toplevel(getattr(self, "root", None) or tk.Tk())
        win.title("📚 文章库 — 爬取+归档+打标签"); win.geometry("1100x720")
        win.transient(getattr(self, "root", None) or win.master)

        # 工具栏
        toolbar = ttk.Frame(win); toolbar.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(toolbar, text="🔍搜索:").pack(side=tk.LEFT)
        search_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=search_var, width=20).pack(side=tk.LEFT, padx=4)
        ttk.Label(toolbar, text="来源:").pack(side=tk.LEFT, padx=(8,0))
        source_var = tk.StringVar(value="全部")
        ttk.Combobox(toolbar, textvariable=source_var,
                     values=["全部","东方财富新闻","机构研报","东财热帖","淘股吧热帖","韭研公社","雪球讨论","手动导入"],
                     width=14, state="readonly").pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🔄刷新", width=7).pack(side=tk.LEFT, padx=4)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        # 爬取区
        ttk.Label(toolbar, text="📥爬取:").pack(side=tk.LEFT)
        crawl_stock_var = tk.StringVar(value=prefill_stock_code or "")
        ttk.Entry(toolbar, textvariable=crawl_stock_var, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🚀爬个股新闻", width=14).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🌐全站热帖", width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🏮淘股吧", width=9).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🌾韭研公社", width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="☃️雪球讨论", width=10).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(toolbar, text="➕新增", width=7).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🗑️删除", width=7).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🏷️打标签", width=8).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(toolbar, text="🔗联动分析", width=10, foreground="#1565C0").pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🔄遍历喂入", width=10, foreground="#E65100").pack(side=tk.LEFT, padx=2)

        # 主区: 左列表 + 右详情
        paned = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # 左: Treeview
        left_frame = ttk.Frame(paned); paned.add(left_frame, weight=3)
        cols = ("id", "title", "source", "stock", "time")
        tree = ttk.Treeview(left_frame, columns=cols, show="headings", height=20)
        for c, t, w in [("id","#",45),("title","标题",320),("source","来源",100),("stock","股票",100),("time","时间",110)]:
            tree.heading(c, text=t); tree.column(c, width=w, anchor="w", stretch=True)
        vs = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); vs.pack(side=tk.RIGHT, fill=tk.Y)
        tree.tag_configure("saved", background="#E8F5E9")
        tree.tag_configure("hot", foreground="#D32F2F")

        # 右: 详情 + 标签
        right_frame = ttk.Frame(paned); paned.add(right_frame, weight=4)
        r_top = ttk.Frame(right_frame); r_top.pack(fill=tk.X, pady=(0, 4))
        r_title_var = tk.StringVar(value="⬅️ 左侧选中文章查看详情")
        ttk.Label(r_top, textvariable=r_title_var, font=("", 12, "bold"), wraplength=500).pack(anchor="w")
        r_meta_var = tk.StringVar(value="")
        ttk.Label(r_top, textvariable=r_meta_var, foreground="#666").pack(anchor="w")

        # 当前标签 chip 区
        tags_frame = ttk.LabelFrame(r_top, text="🏷️ 已打标签", padding=4)
        tags_frame.pack(fill=tk.X, pady=4)
        tags_chips_var = tk.StringVar(value="(无)")
        ttk.Label(tags_frame, textvariable=tags_chips_var, foreground="#1565C0").pack(side=tk.LEFT)

        # 内容 text
        content_text = tk.Text(right_frame, wrap="word", font=("PingFang SC", 10), height=22, bg="#FAFAFA")
        content_text.pack(fill=tk.BOTH, expand=True)

        status = tk.StringVar(value="就绪")
        ttk.Label(win, textvariable=status, anchor="w").pack(fill=tk.X, padx=8, pady=2)

        # ── 刷新列表 ──
        def _refresh_list():
            for iid in tree.get_children(): tree.delete(iid)
            conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
            kw = search_var.get().strip()
            src = source_var.get()
            sql = "SELECT id,title,source,COALESCE(stock_code,''),COALESCE(stock_name,''),COALESCE(created_at,'') FROM articles WHERE 1=1"
            params = []
            if kw: sql += " AND (title LIKE ? OR content LIKE ?)"; params.extend([f"%{kw}%", f"%{kw}%"])
            if src != "全部": sql += " AND source=?"; params.append(src)
            sql += " ORDER BY id DESC LIMIT 500"
            cur.execute(sql, params)
            for row in cur.fetchall():
                aid, title, src2, scode, sname, ctime = row
                stock_col = f"{sname}({scode})" if sname else scode
                tag = "saved"
                tree.insert("", "end", values=(aid, title[:80], src2, stock_col, ctime), tags=(tag,))
            conn.close()
            status.set(f"📚 共显示 {len(tree.get_children())} 篇文章")

        def _load_detail(_evt=None):
            sel = tree.selection();
            if not sel: return
            vals = tree.item(sel[0], "values"); aid = vals[0]
            conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
            cur.execute("SELECT title,author,source,url,content,stock_code,stock_name,created_at FROM articles WHERE id=?", (aid,))
            row = cur.fetchone()
            # 标签
            cur.execute("SELECT t.id,t.name,t.color FROM tags t JOIN article_tags at ON t.id=at.tag_id WHERE at.article_id=?", (aid,))
            atags = cur.fetchall()
            conn.close()
            if not row: return
            title, author, source, url, content, scode, sname, ctime = row
            r_title_var.set(title)
            r_meta_var.set(f"✍️ {author}  |  📌 {source}  |  📅 {ctime}  |  🔗 {url[:60]}")
            content_text.config(state="normal"); content_text.delete("1.0", "end")
            content_text.insert("end", content or "(正文为空)"); content_text.config(state="disabled")
            # 标签 chips
            if atags:
                chip_str = "  ".join(f"[{n}]" for _, n, _ in atags)
                tags_chips_var.set(chip_str)
            else:
                tags_chips_var.set("(无标签)")
            # 保存当前 aid 到 closure
            _current_article_id[0] = aid
            _current_tags_ids[0] = [t[0] for t in atags]

        _current_article_id = [None]
        _current_tags_ids = [[]]

        # ── 爬取 ──
        def _do_crawl_stock():
            code = crawl_stock_var.get().strip()
            if not code: messagebox.showinfo("提示", "请输入股票代码 (如 002230)", parent=win); return
            status.set(f"⏳ 爬取 {code} 新闻..."); win.update_idletasks()
            items = self._crawl_akshare_news(stock_code=code, max_items=15)
            saved = 0
            conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
            for a in items:
                cur.execute("SELECT id FROM articles WHERE url=? AND title=?", (a.get("url",""), a.get("title","")))
                if cur.fetchone(): continue
                cur.execute("INSERT INTO articles(source,author,title,url,content,stock_code,stock_name,saved) VALUES(?,?,?,?,?,?,?,1)",
                            (a.get("source",""), a.get("author",""), a.get("title",""), a.get("url",""),
                             a.get("content",""), a.get("stock_code",""), a.get("stock_name","")))
                saved += 1
            conn.commit(); conn.close()
            _refresh_list()
            status.set(f"✅ 爬取完成: 新增 {saved} 篇 (共 {len(items)} 条)")

        def _do_crawl_global():
            status.set("⏳ 爬取全站热帖..."); win.update_idletasks()
            items = self._crawl_akshare_news(max_items=30)
            saved = 0
            conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
            for a in items:
                cur.execute("INSERT OR IGNORE INTO articles(source,author,title,url,content,stock_code,stock_name,saved) VALUES(?,?,?,?,?,?,?,1)",
                            (a.get("source",""), a.get("author",""), a.get("title",""), a.get("url",""),
                             a.get("content",""), a.get("stock_code",""), a.get("stock_name","")))
                if cur.rowcount > 0: saved += 1
            conn.commit(); conn.close()
            _refresh_list()
            status.set(f"✅ 全站热帖: 新增 {saved} 篇")

        # ── 打标签 ──
        def _do_tag():
            aid = _current_article_id[0]
            if not aid: messagebox.showinfo("提示", "请先选中文章", parent=win); return
            selected = self._show_tag_picker(win, current_tag_ids=_current_tags_ids[0])
            if selected is None: return
            import sqlite3 as _sql3
            conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
            cur.execute("DELETE FROM article_tags WHERE article_id=?", (aid,))
            for tid in selected:
                cur.execute("INSERT OR IGNORE INTO article_tags(article_id,tag_id) VALUES(?,?)", (aid, tid))
                cur.execute("UPDATE tags SET usage_count=usage_count+1 WHERE id=?", (tid,))
            conn.commit(); conn.close()
            _load_detail()
            status.set(f"✅ 已为 #{aid} 打 {len(selected)} 个标签")

        # ── 新增手动 ──
        def _do_add_manual():
            dlg = tk.Toplevel(win); dlg.title("➕ 手动新增文章"); dlg.geometry("560x460")
            dlg.transient(win); dlg.grab_set()
            ttk.Label(dlg, text="来源:").grid(row=0, column=0, padx=8, pady=(10,2), sticky="e")
            src_v = tk.StringVar(value="手动导入")
            ttk.Entry(dlg, textvariable=src_v, width=40).grid(row=0, column=1, pady=(10,2), sticky="w")
            ttk.Label(dlg, text="标题:").grid(row=1, column=0, padx=8, pady=2, sticky="e")
            tit_v = tk.StringVar()
            ttk.Entry(dlg, textvariable=tit_v, width=40).grid(row=1, column=1, pady=2, sticky="w")
            ttk.Label(dlg, text="作者:").grid(row=2, column=0, padx=8, pady=2, sticky="e")
            auth_v = tk.StringVar()
            ttk.Entry(dlg, textvariable=auth_v, width=40).grid(row=2, column=1, pady=2, sticky="w")
            ttk.Label(dlg, text="URL:").grid(row=3, column=0, padx=8, pady=2, sticky="e")
            url_v = tk.StringVar()
            ttk.Entry(dlg, textvariable=url_v, width=40).grid(row=3, column=1, pady=2, sticky="w")
            ttk.Label(dlg, text="股票:").grid(row=4, column=0, padx=8, pady=2, sticky="e")
            stk_v = tk.StringVar(value=prefill_stock_code or "")
            ttk.Entry(dlg, textvariable=stk_v, width=40).grid(row=4, column=1, pady=2, sticky="w")
            ttk.Label(dlg, text="正文:").grid(row=5, column=0, padx=8, pady=2, sticky="ne")
            body_txt = tk.Text(dlg, width=42, height=12); body_txt.grid(row=5, column=1, pady=2, sticky="nsew")
            dlg.rowconfigure(5, weight=1); dlg.columnconfigure(1, weight=1)

            def _save():
                body = body_txt.get("1.0","end").strip()
                if not tit_v.get(): messagebox.showwarning("提示", "标题不能为空", parent=dlg); return
                conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
                cur.execute("INSERT INTO articles(source,author,title,url,content,stock_code,saved) VALUES(?,?,?,?,?,?,1)",
                            (src_v.get(), auth_v.get(), tit_v.get(), url_v.get(), body, stk_v.get()))
                conn.commit(); conn.close()
                dlg.destroy(); _refresh_list(); status.set(f"✅ 已新增: {tit_v.get()[:30]}")
            ttk.Button(dlg, text="💾保存", command=_save, width=10).grid(row=6, column=1, pady=8, sticky="e")

        # ── 删除 ──
        def _do_delete():
            sel = tree.selection()
            if not sel: return
            if not messagebox.askyesno("确认", f"删除选中的 {len(sel)} 篇文章?", parent=win): return
            conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
            for s in sel:
                aid = tree.item(s, "values")[0]
                cur.execute("DELETE FROM article_tags WHERE article_id=?", (aid,))
                cur.execute("DELETE FROM articles WHERE id=?", (aid,))
            conn.commit(); conn.close()
            _refresh_list(); _current_article_id[0] = None; tags_chips_var.set("(无)"); r_title_var.set("⬅️ 左侧选中文章")

        # ── 爬淘股吧 (尽力而为, 反爬严时抓标题存手动待补) ──
        def _do_crawl_taoguba():
            status.set("⏳ 爬取淘股吧热帖..."); win.update_idletasks()
            items = []
            try:
                import requests
                from bs4 import BeautifulSoup
                headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                           "Referer":"https://www.taoguba.com.cn/"}
                # 尝试多个页面
                for url in ["https://www.taoguba.com.cn/hot",
                            "https://www.taoguba.com.cn/NewTopic",
                            "https://www.taoguba.com.cn/GubaAllTopic?ltype=1"]:
                    try:
                        r = requests.get(url, headers=headers, timeout=12)
                        if r.status_code != 200: continue
                        soup = BeautifulSoup(r.text, "html.parser")
                        # 找所有 a 标签里的文章链接
                        for a in soup.select("a[href]"):
                            href = a.get("href", "")
                            txt = a.get_text(strip=True)
                            if len(txt) > 8 and len(txt) < 100 and ("Article" in href or "topic" in href.lower() or "NewTopic" in href):
                                if txt not in [i["title"] for i in items]:
                                    items.append({
                                        "source": "淘股吧热帖", "author": "淘股吧",
                                        "title": txt, "url": href if href.startswith("http") else f"https://www.taoguba.com.cn{href}",
                                        "content": "", "stock_code": "", "stock_name": ""
                                    })
                        if items: break
                    except Exception: continue
            except Exception as e:
                status.set(f"⚠️ 淘股吧爬取异常: {e}")
            # 如果还没爬到, 存占位提示用户手动粘贴
            if not items:
                try:
                    items = [{
                        "source": "淘股吧热帖", "author": "系统",
                        "title": "⚠️ 淘股吧反爬严格 — 请手动复制文章内容后点➕新增粘贴",
                        "url": "https://www.taoguba.com.cn/hot", "content": "反爬提示", "stock_code": "", "stock_name": ""
                    }]
                except Exception: pass
            _save_and_refresh(items, "淘股吧热帖")

        # ── 爬韭研公社 ──
        def _do_crawl_jiuyan():
            status.set("⏳ 爬取韭研公社热帖..."); win.update_idletasks()
            items = []
            try:
                import requests
                from bs4 import BeautifulSoup
                headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                           "Accept":"text/html,application/xhtml+xml"}
                r = requests.get("https://www.jiuyangongshe.com/explore?sort=hot", headers=headers, timeout=15)
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    txt = a.get_text(strip=True)
                    href = a["href"]
                    if len(txt) > 10 and ("/article/" in href or "/share/" in href or "/posts/" in href):
                        full = href if href.startswith("http") else f"https://www.jiuyangongshe.com{href}"
                        if txt not in [i["title"] for i in items]:
                            items.append({
                                "source": "韭研公社", "author": "韭研公社",
                                "title": txt[:120], "url": full,
                                "content": "", "stock_code": "", "stock_name": ""
                            })
            except Exception as e:
                status.set(f"⚠️ 韭研公社爬取异常: {e}")
            if not items:
                items = [{"source":"韭研公社","author":"系统","title":"⚠️ 韭研公社反爬严格 — 请手动复制粘贴",
                         "url":"https://www.jiuyangongshe.com","content":"反爬提示","stock_code":"","stock_name":""}]
            _save_and_refresh(items, "韭研公社")

        # ── 爬雪球讨论 ──
        def _do_crawl_xueqiu():
            status.set("⏳ 爬取雪球热帖..."); win.update_idletasks()
            items = []
            try:
                import requests, json
                headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                           "Referer":"https://xueqiu.com/"}
                s = requests.Session()
                s.get("https://xueqiu.com/", headers=headers, timeout=10)  # 拿 cookie
                for cat in [115, 116, 117]:  # 热门讨论/策略/其他
                    try:
                        r = s.get(f"https://xueqiu.com/v4/statuses/public_timeline_by_category.json?since_id=-1&max_id=-1&count=15&category={cat}",
                                  headers=headers, timeout=10)
                        d = r.json()
                        list_items = d.get("data", {}).get("list") or d.get("list") or []
                        for it in list_items:
                            desc = it.get("description", "") or it.get("text", "") or ""
                            title = it.get("title", "") or desc[:50]
                            user = it.get("user", {}).get("screen_name", "")
                            if title and len(title) > 5:
                                items.append({
                                    "source":"雪球讨论","author":user or "雪球",
                                    "title":title[:120],"url":f"https://xueqiu.com/{it.get('user',{}).get('id','')}/{it.get('id','')}",
                                    "content":desc,"stock_code":"","stock_name":""
                                })
                    except Exception: continue
            except Exception as e:
                status.set(f"⚠️ 雪球爬取异常: {e}")
            if not items:
                items = [{"source":"雪球讨论","author":"系统","title":"⚠️ 雪球反爬 — 请手动复制粘贴 或 东财股吧更全",
                         "url":"https://xueqiu.com","content":"反爬提示","stock_code":"","stock_name":""}]
            _save_and_refresh(items, "雪球讨论")

        def _save_and_refresh(items, label):
            """通用: 去重保存到 DB + 刷新列表 + status"""
            saved = 0
            conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
            for a in items:
                cur.execute("SELECT id FROM articles WHERE title=? AND source=?", (a.get("title",""), label))
                if cur.fetchone(): continue
                cur.execute("INSERT INTO articles(source,author,title,url,content,stock_code,stock_name,saved) VALUES(?,?,?,?,?,?,?,1)",
                            (a.get("source",""), a.get("author",""), a.get("title",""), a.get("url",""),
                             a.get("content",""), a.get("stock_code",""), a.get("stock_name","")))
                saved += 1
            conn.commit(); conn.close(); _refresh_list()
            status.set(f"✅ {label}: 新增 {saved}/{len(items)} 篇")

        # ── 🔗 联动分析: 从文章提取股票 → 跳 ETF 联动弹窗预选 ──
        def _do_linked_analysis():
            sel = tree.selection();
            if not sel: messagebox.showinfo("提示", "请先选中一篇文章", parent=win); return
            vals = tree.item(sel[0], "values"); aid = vals[0]
            # 取文章详情 (可能包含 stock_code/stock_name)
            conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
            cur.execute("SELECT title,content,stock_code,stock_name FROM articles WHERE id=?", (aid,))
            row = cur.fetchone(); conn.close()
            if not row: return
            title, content, scode, sname = row
            # 反向构建: 股票名 → ETF 列表
            etf_link_fn = getattr(self, "_show_etf_link_dialog", None)
            if etf_link_fn is None:
                messagebox.showwarning("提示", "ETF 联动功能暂未就绪", parent=win); return
            # 如果文章里没直接存股票, 从 content/title 模糊匹配 ETF_HOLDERS
            target_stock = sname or ""
            if not target_stock:
                from src.ui.tab_stock_detail import ETF_HOLDERS as _EH  # 懒导入
                search_text = f"{title} {content}"
                for ename, holders in _EH.items():
                    for _, hname in holders:
                        if hname and hname in search_text:
                            target_stock = hname; break
                    if target_stock: break
            if not target_stock:
                target_stock = simpledialog.askstring("🔗联动分析",
                    "文章未识别到股票, 请手动输入股票名称/代码:", parent=win)
                if not target_stock: return
            # 找到该股票所属的 ETF
            from src.ui.tab_stock_detail import ETF_HOLDERS as _EH
            matching_etfs = []
            for ename, holders in _EH.items():
                for _, hname in holders:
                    if target_stock and (target_stock in hname or hname in target_stock):
                        matching_etfs.append(ename); break
            if not matching_etfs:
                # 没匹配到, 直接打开 ETF 联动弹窗让用户手动选
                self._etf_link_prefill_name = None
                self._show_etf_link_dialog(); return
            # 打开 ETF 联动 + 预选第一个匹配的 ETF
            target_etf = matching_etfs[0]
            self._etf_link_prefill_name = target_etf
            self._show_etf_link_dialog()
            status.set(f"🔗 跳 ETF 联动: ETF={target_etf}, 股票={target_stock}")

        # ── 🔄遍历喂入: articles → logic_reviews 自动匹配 ──
        def _do_crawl_feed_in():
            """遍历 articles 表 → 匹配 ETF_HOLDERS → 批量写入 logic_reviews"""
            self._init_article_db()
            from src.ui.tab_stock_detail import ETF_HOLDERS as _EH
            status.set("⏳ 遍历资讯库..."); win.update_idletasks()
            import sqlite3 as _sql3
            conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
            cur.execute("SELECT id, title, content, source, stock_code, stock_name, author FROM articles ORDER BY id DESC LIMIT 500")
            arts = cur.fetchall(); conn.close()

            # 构建反向映射: 股票名 → [(sina, sname), ...]
            stock_name_to_code = {}
            for ename, holders in _EH.items():
                for sina, sname in holders:
                    if sname not in stock_name_to_code:
                        stock_name_to_code[sname] = []
                    if sina not in [x[0] for x in stock_name_to_code[sname]]:
                        stock_name_to_code[sname].append((sina, sname))
            # ETF 名 → ETF 名
            etf_names = list(_EH.keys())

            # 遍历匹配
            candidates = []  # [(sina, sname, match_type, matched_key, art_id, art_title, art_src, snippet)]
            match_stock_cnt = 0; match_etf_cnt = 0
            for art_id, title, content, source, art_scode, art_sname, author in arts:
                text = f"{title} {content}" if content else title
                if not text or len(text.strip()) < 3: continue
                matched_keys = set()
                # 1. 股票名匹配 (从 ETF_HOLDERS 反向)
                for sname, code_list in stock_name_to_code.items():
                    if sname in text and sname not in matched_keys:
                        matched_keys.add(sname)
                        for sina, sn2 in code_list:
                            snippet = title[:60] + ("…" if len(title) > 60 else "")
                            candidates.append((sina, sname, "股票", sname, art_id, snippet, source, ""))
                            match_stock_cnt += 1
                # 2. ETF 名匹配
                for ename in etf_names:
                    if ename in text and ename not in matched_keys:
                        matched_keys.add(ename)
                        snippet = title[:60] + ("…" if len(title) > 60 else "")
                        candidates.append((ename, ename, "ETF", ename, art_id, snippet, source, ""))
                        match_etf_cnt += 1
                # 3. 文章已标记 stock_code 直接用
                if art_scode and art_sname and art_scode not in [c[0] for c in candidates if c[4] == art_id]:
                    if art_scode.startswith("sh") or art_scode.startswith("sz"):
                        snippet = title[:60] + ("…" if len(title) > 60 else "")
                        candidates.append((art_scode, art_sname, "文章标记", art_sname, art_id, snippet, source, ""))

            if not candidates:
                messagebox.showinfo("结果", f"📚 共遍历 {len(arts)} 篇文章, 未匹配到股票/ETF", parent=win); return

            # 去重 (同一 stock + 同一文章只保留第一条)
            seen = set(); dedup = []
            for c in candidates:
                key = (c[0], c[4])  # (sina, art_id)
                if key not in seen:
                    seen.add(key); dedup.append(c)
            candidates = dedup

            # 弹出审核窗口
            dlg = tk.Toplevel(win); dlg.title("🔄遍历喂入 — 审核并选择"); dlg.geometry("1100x620")
            dlg.transient(win); dlg.grab_set()

            ttk.Label(dlg,
                      text=f"📚 遍历 {len(arts)} 篇文章 → 匹配 {match_stock_cnt} 股票 + {match_etf_cnt} ETF → 去重后 {len(candidates)} 条候选",
                      font=("", 10, "bold"), foreground="#1565C0").pack(anchor="w", padx=8, pady=(8,4))

            cols = ("sel", "target", "match_type", "article_id", "article_title", "source")
            tree = ttk.Treeview(dlg, columns=cols, show="headings", height=20)
            for c, t, w in [("sel","✓",35),("target","股票/ETF",140),("match_type","匹配方式",80),
                            ("article_id","#",40),("article_title","文章标题",420),("source","来源",120)]:
                tree.heading(c, text=t); tree.column(c, width=w, anchor="w" if c != "sel" else "center", stretch=True)

            # Checkbutton 选中
            sel_vars = {}
            import tkinter as _tk
            for i, (sina, sname, mtype, mkey, art_id, snippet, src, _) in enumerate(candidates):
                var = _tk.BooleanVar(value=True)  # 默认全选
                sel_vars[i] = var
                prefix = "🔴" if mtype == "股票" else ("🟢" if mtype == "ETF" else "🔵")
                tree.insert("", "end", iid=str(i),
                            values=("☑", f"{prefix} {sname} ({sina})", mtype, art_id, snippet, src))
                if i % 2 == 1: tree.tag_configure(str(i), background="#F5F5F5"); tree.item(str(i), tags=(str(i),))

            vs = ttk.Scrollbar(dlg, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=vs.set)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=4)
            vs.pack(side=tk.RIGHT, fill=tk.Y, pady=4)

            # 全选/取消
            def _sel_all(v):
                for var in sel_vars.values(): var.set(v)
            sel_btns = ttk.Frame(dlg); sel_btns.pack(fill=tk.X, padx=8, pady=2)
            ttk.Button(sel_btns, text="✅ 全选", width=8, command=lambda: _sel_all(True)).pack(side=tk.LEFT, padx=2)
            ttk.Button(sel_btns, text="❌ 全不选", width=8, command=lambda: _sel_all(False)).pack(side=tk.LEFT, padx=2)
            ttk.Button(sel_btns, text="🔀 切换", width=8, command=lambda: [var.set(not var.get()) for var in sel_vars.values()]).pack(side=tk.LEFT, padx=2)

            ttk.Separator(dlg, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=4)
            ttk.Label(dlg, text="点击 '✓' 列切换勾选状态").pack(anchor="w", padx=8)

            # 点击行时切换选中
            def _on_row_click(evt):
                region = tree.identify("region", evt.x, evt.y)
                row_id = tree.identify_row(evt.y)
                if region == "cell" and row_id:
                    try:
                        idx = int(row_id)
                        sel_vars[idx].set(not sel_vars[idx].get())
                        tree.item(row_id, values=("☑" if sel_vars[idx].get() else "☐",) + tree.item(row_id, "values")[1:])
                    except Exception: pass
            tree.bind("<Button-1>", _on_row_click)

            # 底部按钮
            btns = ttk.Frame(dlg); btns.pack(fill=tk.X, padx=8, pady=8)
            result_var = tk.StringVar(value="")

            def _do_feed_in():
                # 收集选中项
                selected = [(i, c) for i, c in enumerate(candidates) if sel_vars[i].get()]
                if not selected: messagebox.showinfo("提示", "请至少勾选一条", parent=dlg); return
                status_var_feed = tk.StringVar(value="")
                status_lbl = ttk.Label(btns, textvariable=status_var_feed, foreground="#1565C0")
                status_lbl.pack(side=tk.LEFT, padx=16)
                status_var_feed.set(f"⏳ 写入 {len(selected)} 条 logic_reviews...")
                dlg.update_idletasks()
                import sqlite3 as _sql3
                conn2 = _sql3.connect(self._ARTICLE_DB); cur2 = conn2.cursor()
                written = 0; skipped = 0
                for i, (sina, sname, mtype, mkey, art_id, snippet, src, _) in selected:
                    try:
                        # 去重: 同一 stock + 同标题的 logic 不重复写
                        cur2.execute("SELECT id FROM logic_reviews WHERE stock_code=? AND article_title=?",
                                     (sina, snippet[:80]))
                        if cur2.fetchone(): skipped += 1; continue
                        # 构造内容 (简洁版)
                        content = f"【资讯匹配·{mtype}】来自 {src} 的文章提到 '{mkey}'。\n标题: {snippet}\n建议: 结合技术面判断是否跟进。"
                        cur2.execute("INSERT INTO logic_reviews(stock_code,stock_name,review_type,content,author,source,article_title) VALUES(?,?,?,?,?,?,?)",
                                     (sina, sname, "资讯匹配", content, "系统", src, snippet[:80]))
                        written += 1
                        # 同时给这篇文章打个"资讯匹配"标签 (自动)
                        cur2.execute("SELECT id FROM tags WHERE name='资讯匹配'")
                        tid_row = cur2.fetchone()
                        if not tid_row:
                            cur2.execute("INSERT INTO tags(name,category,color) VALUES('资讯匹配','操作方向','#607D8B')")
                            tid_row = cur2.lastrowid
                        tid = tid_row[0] if isinstance(tid_row, (tuple, list)) else tid_row
                        cur2.execute("INSERT OR IGNORE INTO article_tags(article_id,tag_id) VALUES(?,?)", (art_id, tid))
                        cur2.execute("UPDATE tags SET usage_count=usage_count+1 WHERE id=?", (tid,))
                    except Exception as _e:
                        print(f"[🔄喂入❌] {sina}: {_e}", flush=True)
                        skipped += 1
                conn2.commit(); conn2.close()
                result_var.set(f"✅ 已写入 {written} 条 logic_reviews (跳过重复 {skipped} 条)")
                status_var_feed.set(result_var.get())
                messagebox.showinfo("✅ 喂入完成",
                    f"遍历: {len(arts)} 篇\n匹配: {len(candidates)} 条候选\n勾选: {len(selected)} 条\n✅ 写入: {written} 条\n⏭️ 跳过重复: {skipped} 条\n\n👉 打开 ETF 联动 → 💡逻辑股评 tab 查看",
                    parent=dlg)
                # 刷新文章库列表
                _refresh_list()
                # 自动打开 ETF 联动 + 选中第一个匹配的股票
                if written > 0:
                    first_sina, first_sname = selected[0][1][0], selected[0][1][1]
                    # 找到所属 ETF
                    from src.ui.tab_stock_detail import ETF_HOLDERS as _EH2
                    for ename, holders in _EH2.items():
                        if any(s[0] == first_sina for s in holders):
                            self._etf_link_prefill_name = ename; break
                    self._show_etf_link_dialog()
                    status.set(f"✅ 喂入完成 {written} 条 → 已打开 ETF 联动")
                dlg.destroy()

            ttk.Button(btns, text="✅ 确认喂入", command=_do_feed_in, width=14).pack(side=tk.RIGHT, padx=6)
            ttk.Button(btns, text="取消", command=dlg.destroy, width=10).pack(side=tk.RIGHT)
            status.set(f"✅ 遍历完成: {len(arts)} 篇 → {len(candidates)} 条候选 (股票{match_stock_cnt} / ETF{match_etf_cnt})")

        # ── 绑按钮 (索引已更新) ──
        tw = toolbar.winfo_children()
        tw[4].config(command=_refresh_list)              # 🔄刷新
        tw[8].config(command=_do_crawl_stock)            # 🚀爬个股
        tw[9].config(command=_do_crawl_global)           # 🌐全站热帖
        tw[10].config(command=_do_crawl_taoguba)          # 🏮淘股吧
        tw[11].config(command=_do_crawl_jiuyan)           # 🌾韭研公社
        tw[12].config(command=_do_crawl_xueqiu)           # ☃️雪球讨论
        tw[14].config(command=_do_add_manual)             # ➕新增
        tw[15].config(command=_do_delete)                 # 🗑️删除
        tw[16].config(command=_do_tag)                    # 🏷️打标签
        tw[18].config(command=_do_linked_analysis)        # 🔗联动分析
        tw[19].config(command=_do_crawl_feed_in)          # 🔄遍历喂入 🆕
        tree.bind("<<TreeviewSelect>>", _load_detail)
        search_var.trace_add("write", lambda *_: _refresh_list())
        source_var.trace_add("write", lambda *_: _refresh_list())

        # 初始加载
        _refresh_list()
        if prefill_stock_code:
            crawl_stock_var.set(prefill_stock_code)

    # ── 🏷️ 标签库维护弹窗 ──
    def _show_tag_manager_dialog(self):
        """完整标签 CRUD + 预设管理"""
        self._init_article_db()
        import sqlite3 as _sql3
        win = tk.Toplevel(getattr(self, "root", None) or tk.Tk())
        win.title("🏷️ 标签库管理"); win.geometry("860x620")
        win.transient(getattr(self, "root", None) or win.master)

        # 工具栏
        tb = ttk.Frame(win); tb.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(tb, text="分类:").pack(side=tk.LEFT)
        cat_var = tk.StringVar(value="全部")
        ttk.Combobox(tb, textvariable=cat_var, values=["全部"] + self._TAG_CATEGORIES, width=10, state="readonly").pack(side=tk.LEFT, padx=4)
        ttk.Button(tb, text="🔄刷新", width=7).pack(side=tk.LEFT, padx=2)
        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(tb, text="➕新增", width=7).pack(side=tk.LEFT, padx=2)
        ttk.Button(tb, text="✏️编辑", width=7).pack(side=tk.LEFT, padx=2)
        ttk.Button(tb, text="🗑️删除", width=7).pack(side=tk.LEFT, padx=2)
        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(tb, text="📥导入预设40+标签", width=16).pack(side=tk.LEFT, padx=2)

        # 列表
        cols = ("id", "name", "category", "color", "usage", "created")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=22)
        for c, t, w in [("id","#",45),("name","标签名",120),("category","分类",100),("color","颜色",80),("usage","使用次数",80),("created","创建时间",150)]:
            tree.heading(c, text=t); tree.column(c, width=w, anchor="w", stretch=False)
        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        tree.tag_configure("has_usage", background="#E3F2FD")

        def _refresh():
            for iid in tree.get_children(): tree.delete(iid)
            conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
            cat = cat_var.get()
            sql = "SELECT id,name,category,color,usage_count,created_at FROM tags"
            if cat != "全部": sql += " WHERE category=?"; cur.execute(sql, (cat,))
            else: cur.execute(sql)
            for row in cur.fetchall():
                r = "has_usage" if row[4] > 0 else ""
                tree.insert("", "end", values=row, tags=(r,))
            conn.close()

        def _add_tag():
            dlg = tk.Toplevel(win); dlg.title("➕ 新增标签"); dlg.geometry("380x240"); dlg.transient(win); dlg.grab_set()
            ttk.Label(dlg, text="标签名:").grid(row=0, column=0, padx=8, pady=(15,4), sticky="e")
            n_var = tk.StringVar()
            ttk.Entry(dlg, textvariable=n_var, width=24).grid(row=0, column=1, pady=(15,4), sticky="w")
            ttk.Label(dlg, text="分类:").grid(row=1, column=0, padx=8, pady=4, sticky="e")
            c_var = tk.StringVar(value="技术形态")
            ttk.Combobox(dlg, textvariable=c_var, values=self._TAG_CATEGORIES, width=10, state="readonly").grid(row=1, column=1, pady=4, sticky="w")
            ttk.Label(dlg, text="颜色(Hex):").grid(row=2, column=0, padx=8, pady=4, sticky="e")
            col_var = tk.StringVar(value="#1565C0")
            ttk.Entry(dlg, textvariable=col_var, width=24).grid(row=2, column=1, pady=4, sticky="w")
            def _save():
                conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
                try:
                    cur.execute("INSERT INTO tags(name,category,color) VALUES(?,?,?)", (n_var.get(), c_var.get(), col_var.get()))
                    conn.commit(); conn.close(); dlg.destroy(); _refresh()
                except Exception as _e:
                    messagebox.showerror("错误", f"重复? {_e}", parent=dlg)
            ttk.Button(dlg, text="💾保存", command=_save, width=10).grid(row=3, column=1, pady=12, sticky="e")

        def _edit_tag():
            sel = tree.selection();
            if not sel: return
            row = tree.item(sel[0], "values"); tid = row[0]
            dlg = tk.Toplevel(win); dlg.title(f"✏️ 编辑 #{tid}"); dlg.geometry("380x240"); dlg.transient(win); dlg.grab_set()
            ttk.Label(dlg, text="标签名:").grid(row=0, column=0, padx=8, pady=(15,4), sticky="e")
            n_var = tk.StringVar(value=row[1])
            ttk.Entry(dlg, textvariable=n_var, width=24).grid(row=0, column=1, pady=(15,4), sticky="w")
            ttk.Label(dlg, text="分类:").grid(row=1, column=0, padx=8, pady=4, sticky="e")
            c_var = tk.StringVar(value=row[2])
            ttk.Combobox(dlg, textvariable=c_var, values=self._TAG_CATEGORIES, width=10, state="readonly").grid(row=1, column=1, pady=4, sticky="w")
            ttk.Label(dlg, text="颜色(Hex):").grid(row=2, column=0, padx=8, pady=4, sticky="e")
            col_var = tk.StringVar(value=row[3])
            ttk.Entry(dlg, textvariable=col_var, width=24).grid(row=2, column=1, pady=4, sticky="w")
            def _save():
                conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
                cur.execute("UPDATE tags SET name=?, category=?, color=? WHERE id=?", (n_var.get(), c_var.get(), col_var.get(), tid))
                conn.commit(); conn.close(); dlg.destroy(); _refresh()
            ttk.Button(dlg, text="💾保存", command=_save, width=10).grid(row=3, column=1, pady=12, sticky="e")

        def _del_tag():
            sel = tree.selection();
            if not sel: return
            ids = [tree.item(s, "values")[0] for s in sel]
            if not messagebox.askyesno("确认", f"删除 {len(ids)} 个标签? (关联文章会保留)", parent=win): return
            conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
            for tid in ids:
                cur.execute("DELETE FROM article_tags WHERE tag_id=?", (tid,))
                cur.execute("DELETE FROM tags WHERE id=?", (tid,))
            conn.commit(); conn.close(); _refresh()

        def _import_preset():
            conn = _sql3.connect(self._ARTICLE_DB); cur = conn.cursor()
            inserted = 0
            for name, cat, color in self._PRESET_TAGS:
                cur.execute("INSERT OR IGNORE INTO tags(name,category,color) VALUES(?,?,?)", (name, cat, color))
                if cur.rowcount > 0: inserted += 1
            conn.commit(); conn.close(); _refresh()
            messagebox.showinfo("✅", f"已导入 {inserted} 个预设标签", parent=win)

        tb.winfo_children()[2].config(command=_refresh)
        tb.winfo_children()[5].config(command=_add_tag)
        tb.winfo_children()[7].config(command=_edit_tag)
        tb.winfo_children()[9].config(command=_del_tag)
        tb.winfo_children()[12].config(command=_import_preset)
        cat_var.trace_add("write", lambda *_: _refresh())
        _refresh()


__all__ = ["StockDetailMixin"]
