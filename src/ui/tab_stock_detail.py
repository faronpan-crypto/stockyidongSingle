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
            out = np.full(len(arr), np.nan)
            for i in range(period - 1, len(arr)):
                out[i] = np.max(arr[i - period + 1:i + 1])
            return out

        def _period_low(arr, period):
            out = np.full(len(arr), np.nan)
            for i in range(period - 1, len(arr)):
                out[i] = np.min(arr[i - period + 1:i + 1])
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
                text1.insert(tk.END, "▌云 (Kumo)\n", "subtitle")
                text1.insert(tk.END,
                    "  先行带 A 和 B 之间的填充区域就是云:\n"
                    "  🔴 红色云 (A > B): 看涨区域, 价格在云上=强多头\n"
                    "  🟢 绿色云 (A < B): 看跌区域, 价格在云下=强空头\n"
                    "  价格突破云的边界 = 重要买卖信号\n\n", "body")

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

                # 构建图表 (主图: 一目均衡 + K线; 副图: VW-MACD)
                fig = Figure(figsize=(14, 10), dpi=100, facecolor='#FAFAFA')
                gs = gridspec.GridSpec(2, 1, figure=fig, height_ratios=[3, 1], hspace=0.08)
                ax_main = fig.add_subplot(gs[0, 0])
                ax_sub = fig.add_subplot(gs[1, 0], sharex=ax_main)

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

                # 主图装饰 (动态标题: 根据勾选的指标名)
                active_inds = []
                if ind_vars["ichimoku"].get(): active_inds.append("一目均衡")
                if ind_vars["supertrend"].get(): active_inds.append("SuperTrend")
                if ind_vars["vwap_band"].get(): active_inds.append("VWAP+σ")
                if ind_vars["td_seq"].get(): active_inds.append("TD序列")
                if ind_vars["camarilla"].get(): active_inds.append("Camarilla")
                ax_main.set_title(f"📈 {sym_name} — {period_label} | " + " · ".join(active_inds) + " + VW-MACD",
                                  fontsize=13, fontweight='bold', pad=10)
                ax_main.legend(loc='upper left', fontsize=7, ncol=3)
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
                        f"  云: {cloud_label}",
                        f"  {tk_kijun}  |  {price_pos}",
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

                # ─── 副图: VW-MACD ───
                x = np.asarray(dates)
                ax_sub.plot(x, vw['dif'], label='VW-DIF', linewidth=1.0, color='#1565c0')
                ax_sub.plot(x, vw['dea'], label='VW-DEA', linewidth=1.0, color='#c62828')
                bar_colors = ['#d32f2f' if v >= 0 else '#388e3c' for v in vw['macdh']]
                ax_sub.bar(x, vw['macdh'], color=bar_colors, alpha=0.45, width=0.55)
                ax_sub.axhline(0, color="gray", linewidth=0.6)

                # 成交量比率提示线 (量能信号)
                vol_ratio = vw['vol_ratio']
                ax_sub2 = ax_sub.twinx()
                ax_sub2.plot(x, vol_ratio, color='#ff9800', linewidth=0.7,
                             alpha=0.5, linestyle=':', label='量比')
                ax_sub2.axhline(1.5, color='#ff9800', linestyle='--', linewidth=0.5, alpha=0.5)
                ax_sub2.axhline(0.7, color='#ff9800', linestyle='--', linewidth=0.5, alpha=0.5)
                ax_sub2.set_ylabel('量比', fontsize=8, color='#ff9800')
                ax_sub2.tick_params(axis='y', labelcolor='#ff9800', labelsize=8)
                ax_sub2.set_ylim(0, max(3.0, np.nanmax(vol_ratio) * 1.1))

                ax_sub.set_ylabel('VW-MACD', fontsize=9)
                ax_sub.legend(loc='upper left', fontsize=7)
                ax_sub2.legend(loc='upper right', fontsize=7)
                ax_sub.grid(True, alpha=0.3)

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


__all__ = ["StockDetailMixin"]
