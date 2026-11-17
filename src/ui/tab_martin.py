# ═══════════════════════════════════════════════════════════════
# 🎯 Martin Luk 动量交易操盘系统
# ═══════════════════════════════════════════════════════════════
#
# 【核心理念】
#   一笔交易能赚多少没法预测, 能亏多少可以自己定
#   只挑止损能放得很近的地方买, 看错马上认亏, 看对多拿
#   亏损单平均 2%, 盈利单平均 14% — 盈亏比 7:1
#   27% 胜率 × 7:1 盈亏比 = 正期望
#
# 【技术指标 (仅3样)】
#   1. EMA 9 / 21 / 50 / 150 — 指数移动平均线 (所有周期统一)
#   2. AVWAP — 锚定成交量加权均价
#   3. 成交额 (股价×成交量) — 不看股数, 看成交了多少钱
#   + ADR (Average Daily Range) — 平均日内振幅 %
#
# 【三种买法】
#   ① 回调 Pullback (一半以上单子):
#      趋势向上 + 位置早(首次回调) + 支撑到位(EMA9/21/AVWAP/前高前低/缺口)
#   ② 突破 Breakout:
#      整理1-2周+ 波动收窄贴EMA9 + inside day + AVWAP上方
#   ③ EP跳空 Earnings Gap:
#      财报等消息跳空高开 ≥5% + 放量 ≥2x
#
# 【止损/仓位】
#   止损 = min(当日最低, 触发K最低) — 上限 ADR/2 且 ≤5%
#   仓位 = (账户 × 0.5%) / (入场价 - 止损价)
#   多数仓位 25-30%, 小盘 20% 以下
#
# 【止盈】
#   至少 3R/5R 才卖第一批 (每次15%)
#   日线 EMA9 升到入场价 → 止损移到保本
#   剩余用日线 EMA9 跟踪, 提前挂单在 EMA9 下方
#   比 EMA9 高出 15-20% 再卖一些
#
# 【环境判断】
#   ① 自己的单子 — 连亏就停 / 减风险
#   ② 指数 (QQQ/IWM or 上证/创业板) — EMA9/21 向上最好
#   ③ 观察名单强弱分布 — 强(>EMA50>EMA150) vs 弱
#   → 形态再漂亮也没有市场环境重要
#
# ═══════════════════════════════════════════════════════════════

import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np
import threading
import traceback
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import akshare as ak
    AKSHARE_OK = True
except ImportError:
    AKSHARE_OK = False


class MartinMixin:
    """🎯 Martin Luk 动量操盘系统 Mixin"""

    # ═══════════════════════════════════════════════════════
    # 📊 技术指标 (静态方法, 方便单元测试)
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _ema(series, n):
        """指数移动平均线"""
        s = pd.Series(series, dtype=float)
        return s.ewm(span=float(n), adjust=False).mean().values

    @staticmethod
    def _ma(series, n):
        """简单移动平均线 (SMA)"""
        s = pd.Series(series, dtype=float)
        return s.rolling(window=int(n), min_periods=1).mean().values

    @staticmethod
    def _detect_ma_signals(ma5, ma10, ma20, ma40, ma80):
        """🎯 MA40/MA80 双均线交易系统三档信号
        返回 [(idx, 'buy'/'sell_half'/'sell_all', price), ...]
        规则:
          买入  = MA40 上穿 MA80
          减仓半 = MA40 跌破 MA40阈值 (低于前x日均值 - 但仍在 MA80 之上)
          清仓  = MA40 下穿 MA80
        """
        signals = []
        n = len(ma40)
        for i in range(1, n):
            m40_now = ma40[i]
            m40_prev = ma40[i-1]
            m80_now = ma80[i]
            m80_prev = ma80[i-1]
            if np.isnan(m40_now) or np.isnan(m80_now) or np.isnan(m40_prev) or np.isnan(m80_prev):
                continue
            # 买入: MA40 从下方穿越 MA80
            if m40_prev <= m80_prev and m40_now > m80_now:
                signals.append((i, "buy", m40_now))
            # 清仓: MA40 从上方穿越 MA80 (下穿)
            elif m40_prev >= m80_prev and m40_now < m80_now:
                signals.append((i, "sell_all", m40_now))
            # 减仓半: MA40 连续 3 日走弱 + 但仍在 MA80 之上 (保护利润)
            elif i >= 3 and m40_now < m40_prev < ma40[i-2] < ma40[i-3] and m40_now > m80_now:
                signals.append((i, "sell_half", m40_now))
        return signals

    @staticmethod
    def _detect_ma40_penetration(ma40, closes):
        """简化版减仓半: MA40 跌破前一日 MA40 但收盘价仍在 MA40 之上 (预警)
        + MA40 下穿 MA40 自身 X 日前的高点 (主动回撤保护)"""
        signals = []
        n = len(ma40)
        for i in range(5, n):
            m40_now = ma40[i]
            c_now = closes[i]
            # 收盘价仍在 MA40 之上, 但 MA40 斜率转负
            if not np.isnan(m40_now) and not np.isnan(ma40[i-1]) and not np.isnan(ma40[i-3]):
                if m40_now < ma40[i-1] < ma40[i-3] and c_now >= m40_now:
                    signals.append((i, "sell_half", m40_now))
        return signals

    @staticmethod
    def _macd(close, fast=12, slow=26, signal=9):
        """MACD: DIF, DEA, 柱状"""
        s = pd.Series(close, dtype=float)
        ema_fast = s.ewm(span=fast, adjust=False).mean()
        ema_slow = s.ewm(span=slow, adjust=False).mean()
        dif = (ema_fast - ema_slow).values
        dea = pd.Series(dif).ewm(span=signal, adjust=False).mean().values
        hist = 2 * (dif - dea)
        return dif, dea, hist

    @staticmethod
    def _kdj(high, low, close, n=9, m1=3, m2=3):
        """KDJ 随机指标"""
        h, l, c = pd.Series(high), pd.Series(low), pd.Series(close)
        llv = l.rolling(n, min_periods=1).min()
        hhv = h.rolling(n, min_periods=1).max()
        rsv = (c - llv) / (hhv - llv + 1e-10) * 100
        k = rsv.ewm(com=m1 - 1, adjust=False).mean()
        d = k.ewm(com=m2 - 1, adjust=False).mean()
        j = 3 * k - 2 * d
        return k.values, d.values, j.values

    @staticmethod
    def _rsi(close, period=14):
        """RSI 相对强弱指标"""
        s = pd.Series(close, dtype=float)
        delta = s.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        return (100 - 100 / (1 + rs)).values

    @staticmethod
    def _boll(close, n=20, k=2):
        """布林带: 中轨, 上轨, 下轨"""
        s = pd.Series(close, dtype=float)
        mid = s.rolling(n, min_periods=1).mean()
        std = s.rolling(n, min_periods=1).std()
        return mid.values, (mid + k * std).values, (mid - k * std).values

    @staticmethod
    def _cci(high, low, close, n=14):
        """CCI 顺势指标"""
        h, l, c = pd.Series(high), pd.Series(low), pd.Series(close)
        tp = (h + l + c) / 3
        avg_tp = tp.rolling(n, min_periods=1).mean()
        mean_dev = tp.rolling(n, min_periods=1).apply(
            lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
        return ((tp - avg_tp) / (0.015 * mean_dev + 1e-10)).values

    @staticmethod
    def _ichimoku(high, low, close):
        """一目均衡表: Tenkan, Kijun, SpanA, SpanB, Chikou"""
        h, l, c = np.asarray(high, float), np.asarray(low, float), np.asarray(close, float)
        tenkan = np.full(len(c), np.nan)
        kijun = np.full(len(c), np.nan)
        for i in range(len(c)):
            if i >= 8:
                tenkan[i] = (np.max(h[i - 8:i + 1]) + np.min(l[i - 8:i + 1])) / 2
            if i >= 25:
                kijun[i] = (np.max(h[i - 25:i + 1]) + np.min(l[i - 25:i + 1])) / 2
        # Span A = (tenkan + kijun) / 2, 向前移 26
        span_a = np.full(len(c), np.nan)
        span_a[:len(c) - 26] = (tenkan[26:] + kijun[26:]) / 2
        # Span B = 52 天最高最低 / 2, 向前移 26
        span_b = np.full(len(c), np.nan)
        for i in range(len(c) - 26):
            if i + 26 >= 52:
                span_b[i] = (np.max(h[i - 26:i + 26 + 1] if i >= 26 else h[:i + 26 + 1])
                             + np.min(l[i - 26:i + 26 + 1] if i >= 26 else l[:i + 26 + 1])) / 2
        # Chikou = close 向后移 26 (显示时其实是当前 close 画在 t-26 位置)
        chikou = np.full(len(c), np.nan)
        chikou[26:] = c[:len(c) - 26]
        return tenkan, kijun, span_a, span_b, chikou

    @staticmethod
    def _identify_candle(open_, high, low, close):
        """单根蜡烛形态识别 → 返回 (形态名, 方向, 评分 1-5)"""
        o, h, l, c = float(open_), float(high), float(low), float(close)
        body = abs(c - o)
        upper_shadow = h - max(o, c)
        lower_shadow = min(o, c) - l
        total_range = h - l + 1e-10
        body_ratio = body / total_range
        upper_ratio = upper_shadow / total_range
        lower_ratio = lower_shadow / total_range

        if body_ratio < 0.1:
            if upper_ratio < 0.2 and lower_ratio > 0.6:
                return "锤子线(看涨)", "↑", 4
            if lower_ratio < 0.2 and upper_ratio > 0.6:
                return "射击之星(看跌)", "↓", 4
            return "十字星(犹豫)", "—", 2

        if lower_ratio > body_ratio * 2 and body_ratio < 0.3:
            return "锤子线(看涨)", "↑", 3
        if upper_ratio > body_ratio * 2 and body_ratio < 0.3:
            return "射击之星(看跌)", "↓", 3

        if c > o:
            if body_ratio > 0.7 and lower_ratio < 0.15:
                return "大阳线(强势)", "↑", 5
            if body_ratio < 0.3 and upper_ratio > 0.4:
                return "带上影小阳", "↑", 2
            return "阳线", "↑", 1
        else:
            if body_ratio > 0.7 and upper_ratio < 0.15:
                return "大阴线(强势)", "↓", 5
            if body_ratio < 0.3 and lower_ratio > 0.4:
                return "带下影小阴", "↓", 2
            return "阴线", "↓", 1

    @staticmethod
    def _calc_win_probability(close, ema9, ema21, ema50, adr_pct, pattern_type="pullback"):
        """估算 Martin 风格交易的成功概率 (基于 R 倍数 + 历史胜率)"""
        if len(close) < 50:
            return 50.0, "数据不足"
        c = float(close[-1])
        e9 = ema9[-1] if not np.isnan(ema9[-1]) else c
        e21 = ema21[-1] if not np.isnan(ema21[-1]) else c
        e50 = ema50[-1] if not np.isnan(ema50[-1]) else c

        score = 0.0
        notes = []

        # 趋势分 (EMA 排列)
        if e9 > e21 > e50:
            score += 20; notes.append("EMA多头排列+20")
        elif e9 > e21:
            score += 10; notes.append("EMA9>EMA21+10")
        elif e9 < e21 < e50:
            score -= 15; notes.append("EMA空头排列-15")

        # 位置分 (离 EMA 越近越安全)
        dist_ema9 = abs(c - e9) / c * 100
        if dist_ema9 < 1:
            score += 10; notes.append("紧贴EMA9+10")
        elif dist_ema9 < 2:
            score += 5; notes.append("靠近EMA9+5")
        elif dist_ema9 > 5:
            score -= 10; notes.append("远离EMA9-10")

        # 波动分 (ADR 适中)
        if 2.5 <= adr_pct <= 5:
            score += 10; notes.append(f"ADR{adr_pct:.1f}%适中+10")
        elif adr_pct > 6:
            score -= 5; notes.append(f"ADR过高-5")

        # 形态分
        pattern_bonus = {"pullback": 15, "breakout": 12, "ep_gap": 8}.get(pattern_type, 5)
        score += pattern_bonus
        notes.append(f"形态加成+{pattern_bonus}")

        # 历史胜率 base
        base = 27.0  # Martin 全年平均胜率
        prob = max(10, min(90, base + score))
        return round(prob, 1), "; ".join(notes)

    @staticmethod
    def _futures_kline_analysis(close, high, low, volume):
        """期货/股票通吃的 K 线结构分析"""
        n = len(close)
        if n < 30:
            return "数据不足"
        c = np.asarray(close, float)
        h = np.asarray(high, float)
        l = np.asarray(low, float)
        v = np.asarray(volume, float)

        # 结构高点/低点 (ZigZag 简化版)
        pivots_high = []
        pivots_low = []
        for i in range(2, n - 2):
            if h[i] > max(h[i-1], h[i-2], h[i+1], h[i+2]):
                pivots_high.append((i, h[i]))
            if l[i] < min(l[i-1], l[i-2], l[i+1], l[i+2]):
                pivots_low.append((i, l[i]))

        # 趋势结构
        higher_highs = len(pivots_high) >= 2 and pivots_high[-1][1] > pivots_high[-2][1]
        higher_lows = len(pivots_low) >= 2 and pivots_low[-1][1] > pivots_low[-2][1]
        lower_highs = len(pivots_high) >= 2 and pivots_high[-1][1] < pivots_high[-2][1]
        lower_lows = len(pivots_low) >= 2 and pivots_low[-1][1] < pivots_low[-2][1]

        # 量能
        avg_v = np.mean(v[-20:])
        cur_v = v[-1]
        vol_ratio = cur_v / (avg_v + 1e-10)

        parts = []
        if higher_highs and higher_lows:
            parts.append("📈 上升结构 (HH+HL)")
        elif lower_highs and lower_lows:
            parts.append("📉 下降结构 (LH+LL)")
        elif higher_highs and lower_lows:
            parts.append("⚠️ 收敛三角形 (HH+LL)")
        elif lower_highs and higher_lows:
            parts.append("⚠️ 扩散三角形 (LH+HL)")
        else:
            parts.append("➡️ 震荡整理")

        parts.append(f"量比 {vol_ratio:.2f}")
        if vol_ratio > 2:
            parts.append("放量!")
        elif vol_ratio < 0.5:
            parts.append("缩量")

        # 关键位
        if pivots_high:
            parts.append(f"前高 {pivots_high[-1][1]:.2f}")
        if pivots_low:
            parts.append(f"前低 {pivots_low[-1][1]:.2f}")

        return " | ".join(parts)

    @staticmethod
    def _avwap(high, low, close, volume, anchor_idx):
        """锚定成交量加权均价 (从 anchor_idx 开始累计)"""
        h = np.asarray(high, dtype=float)
        l = np.asarray(low, dtype=float)
        c = np.asarray(close, dtype=float)
        v = np.asarray(volume, dtype=float)
        typical = (h + l + c) / 3
        n = len(c)
        vwap = np.full(n, np.nan)
        cum_vol = 0.0
        cum_pv = 0.0
        for i in range(anchor_idx, n):
            cum_vol += v[i]
            cum_pv += typical[i] * v[i]
            if cum_vol > 0:
                vwap[i] = cum_pv / cum_vol
        return vwap

    @staticmethod
    def _adr(high, low, close, period=20):
        """Average Daily Range — 平均日内振幅百分比"""
        h = np.asarray(high, dtype=float)
        l = np.asarray(low, dtype=float)
        c = np.asarray(close, dtype=float)
        prev_close = np.roll(c, 1)
        tr = np.maximum(h - l, np.maximum(np.abs(h - prev_close), np.abs(l - prev_close)))
        tr[0] = h[0] - l[0]
        atr = pd.Series(tr).rolling(period).mean().values
        adr_pct = np.where(c > 0, atr / c * 100, 0.0)
        return adr_pct

    # ═══════════════════════════════════════════════════════
    # 🔍 三种买法形态识别
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _detect_pullback(ema9, ema21, ema50, close, avwap, recent_high_idx):
        """
        📉 回调形态 (Pullback) — Martin 一半以上的单子
        条件: 趋势向上 + 位置早 + 支撑到位
        """
        n = len(close)
        if n < 60:
            return None

        cur_price = close[-1]
        cur_ema9 = ema9[-1]
        cur_ema21 = ema21[-1]
        cur_ema50 = ema50[-1]
        cur_avwap = avwap[-1] if not np.isnan(avwap[-1]) else None

        # 条件1: 趋势向上 (EMA9 > EMA21 > EMA50, 且 EMA9/21 向上走)
        e9_slope = np.polyfit(range(-5, 0), ema9[-5:], 1)[0]
        e21_slope = np.polyfit(range(-5, 0), ema21[-5:], 1)[0]
        trend_up = (cur_ema9 > cur_ema21 > cur_ema50) and (e9_slope > 0) and (e21_slope > 0)

        if not trend_up:
            return None

        # 条件2: 股价从近期高点回落 (不是新高)
        recent_high = np.max(close[-20:])
        pullback_depth = (recent_high - cur_price) / recent_high
        if pullback_depth < 0.02:
            return None

        # 条件3: 回调到支撑区
        near_ema9 = abs(cur_price - cur_ema9) / cur_ema9 < 0.02
        near_ema21 = abs(cur_price - cur_ema21) / cur_ema21 < 0.02
        near_avwap = cur_avwap and abs(cur_price - cur_avwap) / cur_avwap < 0.02

        if not (near_ema9 or near_ema21 or near_avwap):
            return None

        # 评分
        score = 0
        reasons = []
        score += 30; reasons.append("EMA9>EMA21>EMA50 趋势向上")
        if near_ema9:
            score += 15; reasons.append("踩到EMA9支撑")
        if near_ema21:
            score += 25; reasons.append("踩到EMA21支撑 (胜率更高)")
        if near_avwap:
            score += 20; reasons.append("踩到AVWAP支撑")
        if cur_avwap and cur_price > cur_avwap:
            score += 10; reasons.append("AVWAP上方回踩")
        if pullback_depth > 0.08:
            score += 5; reasons.append(f"回调较深 {pullback_depth*100:.0f}%")

        return {
            "type": "pullback",
            "score": min(score, 100),
            "reasons": reasons,
            "support_level": round(cur_ema9 if near_ema9 else cur_ema21, 2),
            "pullback_depth": pullback_depth,
        }

    @staticmethod
    def _detect_breakout(close, high, low, volume, avwap, ema9):
        """
        🚀 突破形态 (Breakout)
        条件: 整理1-2周+ 波动收窄 + inside day + AVWAP上方
        """
        n = len(close)
        if n < 30:
            return None

        cur_price = close[-1]
        cur_avwap = avwap[-1] if not np.isnan(avwap[-1]) else None

        # 波动收窄: 最近5天 std < 前10天 std × 0.7
        vol_recent = np.std(close[-5:])
        vol_prev = np.std(close[-15:-5])
        vol_narrowing = vol_recent < vol_prev * 0.7 if vol_prev > 0 else False

        # 整理时间: 最近15天振幅 ≤ 15%
        recent_range = np.max(high[-15:]) - np.min(low[-15:])
        recent_avg = np.mean(close[-15:])
        range_pct = recent_range / recent_avg
        consolidating = range_pct <= 0.18

        # Inside Day: 今天高低点在昨天范围内
        inside_day = False
        if len(high) >= 2:
            inside_day = high[-1] < high[-2] and low[-1] > low[-2]

        # 股价在 AVWAP 上方
        above_avwap = cur_avwap is not None and cur_price > cur_avwap

        # K线贴着 EMA9 (±2%)
        near_ema9 = abs(cur_price - ema9[-1]) / ema9[-1] < 0.025

        # 必须至少满足整理+收窄
        if not (consolidating and vol_narrowing):
            return None

        score = 0
        reasons = []
        if consolidating:
            score += 20; reasons.append(f"整理区振幅 {range_pct*100:.1f}%")
        if vol_narrowing:
            score += 20; reasons.append("波动收窄蓄势")
        if inside_day:
            score += 25; reasons.append("Inside Day 信号")
        if above_avwap:
            score += 20; reasons.append("AVWAP上方")
        if near_ema9:
            score += 15; reasons.append("贴着EMA9")

        if score < 30:
            return None

        return {
            "type": "breakout",
            "score": min(score, 100),
            "reasons": reasons,
            "consolidation_high": round(np.max(high[-15:]), 2),
            "consolidation_low": round(np.min(low[-15:]), 2),
        }

    @staticmethod
    def _detect_ep_gap(open_, prev_close, volume, avg_volume_20):
        """
        ⚡ EP 跳空形态 (Earnings / News Gap)
        条件: 高开 ≥5% + 放量 ≥2x
        """
        if prev_close <= 0:
            return None
        gap_pct = (open_ - prev_close) / prev_close
        vol_ratio = volume / avg_volume_20 if avg_volume_20 > 0 else 0

        if gap_pct < 0.03 or vol_ratio < 1.5:
            return None

        score = 0
        reasons = []
        if gap_pct >= 0.10:
            score += 50; reasons.append(f"高开 {gap_pct*100:.1f}% (≥10% 强信号)")
        elif gap_pct >= 0.05:
            score += 35; reasons.append(f"高开 {gap_pct*100:.1f}%")
        else:
            score += 20; reasons.append(f"高开 {gap_pct*100:.1f}%")

        if vol_ratio >= 3:
            score += 50; reasons.append(f"放量 {vol_ratio:.1f}x (巨量)")
        elif vol_ratio >= 2:
            score += 30; reasons.append(f"放量 {vol_ratio:.1f}x")
        else:
            score += 15; reasons.append(f"量比 {vol_ratio:.1f}x")

        return {
            "type": "ep_gap",
            "score": min(score, 100),
            "reasons": reasons,
            "gap_pct": gap_pct,
            "vol_ratio": vol_ratio,
        }

    # ═══════════════════════════════════════════════════════
    # 💰 止损 / 仓位 / 止盈 计算器
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _calc_stop_loss(entry_price, day_low, trigger_k_low, adr_pct,
                        max_stop_loss_pct=0.05):
        """
        Martin 止损规则:
        - 优先用当日最低点 (60-70% 的单子)
        - 太远就用触发K最低点
        - 上限: ADR一半 且 ≤5% (通常 3% 以上就放弃)
        """
        candidates = []
        if day_low and day_low < entry_price:
            dist = (entry_price - day_low) / entry_price
            candidates.append(("当日最低点", round(day_low, 2), dist))
        if trigger_k_low and trigger_k_low < entry_price:
            dist = (entry_price - trigger_k_low) / entry_price
            candidates.append(("触发K最低点", round(trigger_k_low, 2), dist))

        if not candidates:
            return None

        adr_half = (adr_pct / 100) / 2 if adr_pct else 0.025
        upper_pct = min(adr_half, max_stop_loss_pct)

        # 选: 不超过上限中最低的止损 (给更多空间)
        valid = [c for c in candidates if c[2] <= upper_pct]
        if valid:
            best = min(valid, key=lambda x: x[2])  # 距离小的优先 (风险更可控)
        else:
            best = min(candidates, key=lambda x: x[2])

        return {
            "method": best[0],
            "stop_price": best[1],
            "distance_pct": round(best[2] * 100, 2),
            "r_multiple": 1.0,
            "warning": "⚠️ 止损偏宽 (>3%)" if best[2] > 0.03 else "",
        }

    @staticmethod
    def _calc_position_size(account_value, risk_pct, entry_price, stop_price):
        """
        倒推仓位法:
        风险金额 = 账户 × 风险%  (通常 0.5%)
        每股风险 = 入场价 - 止损价
        股数 = 风险金额 / 每股风险
        """
        if stop_price >= entry_price:
            return None
        risk_amount = account_value * risk_pct
        per_share = entry_price - stop_price
        shares = int(risk_amount / per_share)
        if shares <= 0:
            return None
        pos_value = shares * entry_price
        return {
            "account_value": account_value,
            "risk_pct": risk_pct,
            "risk_amount": round(risk_amount, 2),
            "per_share_risk": round(per_share, 2),
            "shares": shares,
            "position_value": round(pos_value, 2),
            "position_pct": round(pos_value / account_value * 100, 1),
        }

    @staticmethod
    def _calc_r_targets(entry_price, stop_price, targets_r=(3, 5, 15)):
        """R 倍数止盈目标 (1R = 入场价-止损价 的距离)"""
        if stop_price >= entry_price:
            return []
        risk = entry_price - stop_price
        return [
            {"r": r, "price": round(entry_price + risk * r, 2),
             "gain_pct": round(risk * r / entry_price * 100, 1)}
            for r in targets_r
        ]

    # ═══════════════════════════════════════════════════════
    # 🌐 市场环境判断
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _score_one_index(ema9_val, ema21_val, ema50_val):
        """单指数 EMA 得分"""
        if ema9_val <= 0 or ema21_val <= 0:
            return 0
        s = 0
        if ema9_val > ema21_val > ema50_val:
            s += 40  # 完美多头排列
        elif ema9_val > ema21_val:
            s += 20  # 短期金叉
        return s

    # ═══════════════════════════════════════════════════════
    # 🔌 股票数据源 (持仓/自选/涨停/热门等)
    # ═══════════════════════════════════════════════════════

    def _get_stock_pool(self, pool_name, kw=None):
        """
        根据 pool_name 返回 [(code, name), ...] 列表
        支持: holdings, watchlist, zt_pool, lianban, hot_plate, full_market, manual
        """
        results = []

        # ── 1. 持仓股 ──
        if pool_name == "持仓股":
            hs = getattr(self, "holding_stocks", []) or []
            # 多组持仓合并 (持仓1~8组)
            for gi in range(2, 9):
                hg = getattr(self, f"holding_stocks_{gi}", None)
                if hg:
                    hs = list(hs) + list(hg)
            if not hs:
                # 尝试从配置加载 group 1
                try:
                    if hasattr(self, '_load_holdings_from_config'):
                        self._load_holdings_from_config(group_index=1, display_only=False)
                        hs = getattr(self, "holding_stocks", []) or []
                except Exception:
                    pass
            if not hs:
                # 尝试从 config.json 兜底
                try:
                    import json, os
                    config_path = getattr(self, '_config_path', None)
                    if not config_path:
                        config_path = os.path.join(os.path.expanduser("~"), ".stockyidong_holdings.json")
                    if os.path.isfile(config_path):
                        with open(config_path, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                        for gi_str in ["1", "2", "3"]:
                            g = cfg.get(f"group_{gi_str}", [])
                            if isinstance(g, list):
                                hs.extend(g)
                except Exception:
                    pass
            # 去空 + 去重
            seen_codes = set()
            for h in hs:
                if not h:
                    continue
                if isinstance(h, dict):
                    c = h.get("code", "")
                    n = h.get("name", "")
                    if c and c not in seen_codes:
                        seen_codes.add(c); results.append((c, n))
                elif isinstance(h, (list, tuple)) and len(h) >= 2:
                    c, n = str(h[0]), str(h[1]) if len(h) > 1 else ""
                    if c and c not in seen_codes:
                        seen_codes.add(c); results.append((c, n))
                elif isinstance(h, str):
                    c = h.strip()
                    if c and c not in seen_codes:
                        seen_codes.add(c); results.append((c, ""))
            if not results:
                # 加几个A股常见票做兜底演示
                results = [("600519", "贵州茅台"), ("000858", "五粮液"),
                           ("300750", "宁德时代"), ("002594", "比亚迪")]

        # ── 2. 自选股 ──
        elif pool_name == "自选股":
            for gi in [1, 2, 3]:
                hg = getattr(self, f"holding_stocks_{gi}", None)
                if hg:
                    for h in hg:
                        if not h:
                            continue
                        if isinstance(h, dict):
                            results.append((h.get("code", ""), h.get("name", "")))
                        elif isinstance(h, (list, tuple)) and len(h) >= 2:
                            results.append((h[0], h[1]))
                        elif isinstance(h, str):
                            results.append((h, ""))

        # ── 3. 涨停池 ──
        elif pool_name == "涨停池":
            if not AKSHARE_OK:
                if kw:
                    kw.after(0, lambda: None)
                return results
            try:
                today = pd.Timestamp.now().strftime("%Y%m%d")
                zt_df = ak.stock_zt_pool_em(date=today)
                if zt_df is not None and not zt_df.empty:
                    for _, row in zt_df.iterrows():
                        code = str(row.get("代码", row.get("code", "")))
                        name = str(row.get("名称", row.get("name", "")))
                        if code:
                            results.append((code, name))
            except Exception as e:
                print(f"[🎯Martin] 涨停池获取失败: {e}", flush=True)

        # ── 4. 连板池 ──
        elif pool_name == "连板池":
            if not AKSHARE_OK:
                return results
            try:
                today = pd.Timestamp.now().strftime("%Y%m%d")
                lb_df = ak.stock_zt_pool_zbgc_em(date=today)
                if lb_df is not None and not lb_df.empty:
                    for _, row in lb_df.iterrows():
                        code = str(row.get("代码", row.get("code", "")))
                        name = str(row.get("名称", row.get("name", "")))
                        if code:
                            results.append((code, name))
            except Exception as e:
                print(f"[🎯Martin] 连板池获取失败: {e}", flush=True)

        # ── 5. 热门板块领涨 ──
        elif pool_name == "热门板块":
            if not AKSHARE_OK:
                return results
            try:
                try:
                    concept = ak.stock_board_concept_name_em()
                except Exception:
                    concept = None
                if concept is None or concept.empty:
                    try:
                        concept = ak.stock_board_industry_name_em()
                    except Exception:
                        concept = None
                if concept is not None and not concept.empty:
                    concept = concept.sort_values("涨跌幅", ascending=False).head(15)
                    seen = set()
                    for _, row in concept.iterrows():
                        bname = str(row.get("板块名称", row.get("name", "")))
                        try:
                            members = ak.stock_board_concept_cons_em(symbol=bname) if "概念" in pool_name else ak.stock_board_industry_cons_em(symbol=bname)
                            if members is not None and not members.empty:
                                members = members.sort_values("涨跌幅", ascending=False).head(3)
                                for _, m in members.iterrows():
                                    code = str(m.get("代码", ""))
                                    if code and code not in seen:
                                        seen.add(code)
                                        results.append((code, str(m.get("名称", ""))))
                        except Exception:
                            continue
            except Exception as e:
                print(f"[🎯Martin] 热门板块获取失败: {e}", flush=True)

        # ── 6. 全市场 (取 spot 后不过滤, 让后续筛选来做) ──
        elif pool_name == "全市场":
            if not AKSHARE_OK:
                return results
            try:
                df = self._ak_spot_with_retry(max_retries=3)
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        code = str(row.get("代码", ""))
                        name = str(row.get("名称", ""))
                        if code and not "ST" in name:
                            results.append((code, name))
            except Exception as e:
                print(f"[🎯Martin] 全市场获取失败: {e}", flush=True)

        return results

    def _ak_spot_with_retry(self, max_retries=3, timeout=10):
        """带重试的 akshare 实时行情拉取"""
        for attempt in range(max_retries):
            try:
                df = ak.stock_zh_a_spot_em()
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                print(f"[🎯Martin] spot 尝试 {attempt+1}/{max_retries} 失败: {e}", flush=True)
                if attempt < max_retries - 1:
                    import time; time.sleep(2)
        return None

    def _ak_hist_with_retry(self, code, max_retries=2, timeout=6):
        """带重试的 akshare 日线拉取 — 东方财富 → 腾讯 → 新浪 (3层兜底)"""
        import time
        # 先试东方财富
        for attempt in range(max_retries):
            try:
                h = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq",
                                       timeout=timeout)
                if h is not None and len(h) >= 30:
                    return h
            except Exception as e:
                print(f"[🎯Martin] hist EM {code} 尝试 {attempt+1}/{max_retries}: {str(e)[:30]}", flush=True)
                if attempt < max_retries - 1:
                    time.sleep(0.5)

        # 东方财富挂了 → 腾讯兜底
        try:
            h2 = ak.stock_zh_a_hist_tx(symbol=code, adjust="qfq", timeout=timeout)
            if h2 is not None and len(h2) >= 30:
                print(f"[🎯Martin] hist 腾讯兜底成功 {code} ({len(h2)}行)", flush=True)
                rename_map = {}
                for c in h2.columns:
                    cl = str(c).lower()
                    if "date" in cl or "日期" in str(c): rename_map[c] = "date"
                    elif "open" in cl or "开盘" in str(c): rename_map[c] = "open"
                    elif "close" in cl or "收盘" in str(c): rename_map[c] = "close"
                    elif "high" in cl or "最高" in str(c): rename_map[c] = "high"
                    elif "low" in cl or "最低" in str(c): rename_map[c] = "low"
                    elif "volume" in cl or "成交量" in str(c): rename_map[c] = "volume"
                return h2.rename(columns=rename_map)
        except Exception as e2:
            print(f"[🎯Martin] hist 腾讯也失败 {code}: {str(e2)[:30]}", flush=True)

        # 最后兜底: 新浪 (stock_zh_a_daily) / 网易 (stock_zh_a_hist_163)
        try:
            h3 = None
            for api_name, api_kwargs, has_timeout in [
                # stock_zh_a_daily 没有 timeout 参数!
                ("stock_zh_a_daily", {"symbol": f"sh{code}" if code.startswith(("6", "9")) else f"sz{code}",
                                       "adjust": "qfq"}, False),
                ("stock_zh_a_hist_163", {"symbol": code, "adjust": "qfq",
                                          "start_date": "20200101", "end_date": ""}, True),
            ]:
                try:
                    fn = getattr(ak, api_name, None)
                    if fn is None:
                        continue
                    if has_timeout:
                        h3 = fn(timeout=timeout, **api_kwargs)
                    else:
                        h3 = fn(**api_kwargs)  # 不支持 timeout
                    if h3 is not None and len(h3) >= 30:
                        print(f"[🎯Martin] hist 兜底 {api_name} 成功 {code} ({len(h3)}行)", flush=True)
                        rename_map = {}
                        for c in h3.columns:
                            cl = str(c).lower()
                            if "date" in cl or "日期" in str(c): rename_map[c] = "date"
                            elif "open" in cl or "开盘" in str(c): rename_map[c] = "open"
                            elif "close" in cl or "收盘" in str(c): rename_map[c] = "close"
                            elif "high" in cl or "最高" in str(c): rename_map[c] = "high"
                            elif "low" in cl or "最低" in str(c): rename_map[c] = "low"
                            elif "volume" in cl or "成交量" in str(c): rename_map[c] = "volume"
                        return h3.rename(columns=rename_map)
                except Exception as _e3:
                    print(f"[🎯Martin] hist {api_name} 失败 {code}: {str(_e3)[:50]}", flush=True)
                    continue
        except Exception as _e3b:
            print(f"[🎯Martin] hist 新浪/网易兜底也失败 {code}: {str(_e3b)[:50]}", flush=True)

        return None

    # ═══════════════════════════════════════════════════════
    # 🎯 主弹窗入口 (重写版)
    # ═══════════════════════════════════════════════════════

    def _show_martin_dialog(self):
        """🎯 Martin Luk 动量操盘系统 — 主入口"""
        print("[🎯Martin] 启动...", flush=True)
        root = getattr(self, 'root', None)
        kw = tk.Toplevel(root)
        kw.title("🎯 Martin Luk 动量操盘 | 27%胜率 × 7:1盈亏比 | 年赚969%")
        kw.geometry("1480x920")
        kw.configure(bg="#0f0f23")

        # ── 顶部: 第1行 — 股票来源 + 手动输入 ──
        tb1 = tk.Frame(kw, bg="#1a1a3e")
        tb1.pack(fill=tk.X)

        tk.Label(tb1, text="🎯 Martin Luk 动量操盘",
                font=("", 14, "bold"), bg="#1a1a3e", fg="#FFD54F").pack(side=tk.LEFT, padx=(12, 10), pady=6)

        # 股票来源下拉框
        tk.Label(tb1, text="📂 股票来源:", font=("", 10), bg="#1a1a3e", fg="#B0BEC5").pack(side=tk.LEFT, padx=(15, 2))
        pool_var = tk.StringVar(value="持仓股")
        pool_combo = ttk.Combobox(tb1, textvariable=pool_var, width=10, state="readonly",
                                  values=["持仓股", "自选股", "涨停池", "连板池", "热门板块", "全市场"])
        pool_combo.pack(side=tk.LEFT)

        # ── 股票快速选择 Combobox (可编辑 + 多池聚合) ──
        tk.Label(tb1, text="  🎯 快速选股:", font=("", 10), bg="#1a1a3e", fg="#B0BEC5").pack(side=tk.LEFT, padx=(10, 2))
        manual_var = tk.StringVar()
        quick_combo = ttk.Combobox(tb1, textvariable=manual_var, width=28, state="normal",
                                    font=("", 10))
        quick_combo.pack(side=tk.LEFT)

        def _rebuild_quick_combo():
            """聚合多池到 combobox (代码 名称 格式)"""
            all_items = []
            seen = set()

            def _add(pool_name, prefix):
                try:
                    items = self._get_stock_pool(pool_name, kw)
                    for code, name in items[:25]:  # 每池最多25只
                        if code and code not in seen:
                            seen.add(code)
                            label = f"{code} {name}" if name else code
                            all_items.append(f"[{prefix}] {label}")
                except Exception:
                    pass

            # 有网的才拉: 持仓/自选 (本地, 秒出), 涨停/热门 (需要网络, 失败就跳过)
            _add("持仓股", "持")
            _add("自选股", "选")
            try:
                _add("涨停池", "板")
            except Exception:
                pass
            try:
                _add("热门板块", "热")
            except Exception:
                pass

            # 演示/经典票兜底 (永远有)
            demos = [
                ("600519", "贵州茅台"), ("000858", "五粮液"), ("300750", "宁德时代"),
                ("002594", "比亚迪"), ("601318", "中国平安"), ("600036", "招商银行"),
                ("000333", "美的集团"), ("601888", "中国中免"), ("600900", "长江电力"),
                ("300059", "东方财富"), ("002415", "海康威视"), ("601012", "隆基绿能"),
                ("600276", "恒瑞医药"), ("000651", "格力电器"), ("600030", "中信证券"),
                ("601899", "紫金矿业"), ("002230", "科大讯飞"), ("300760", "迈瑞医疗"),
                ("000568", "泸州老窖"), ("600309", "万华化学"),
            ]
            for c, n in demos:
                if c not in seen:
                    seen.add(c)
                    all_items.append(f"[典] {c} {n}")

            # 历史分析过的
            hist = getattr(self, "_martin_history", [])
            for code, name in hist[-10:]:
                if code and code not in seen:
                    seen.add(code)
                    all_items.append(f"[史] {code} {name}")

            quick_combo["values"] = all_items

        # 初始化 + 后台补网络池
        _rebuild_quick_combo()

        def _bg_refresh_combo():
            import time; time.sleep(0.8)  # 等网络池拉完
            try:
                kw.after(0, _rebuild_quick_combo)
            except Exception:
                pass

        threading.Thread(target=_bg_refresh_combo, daemon=True).start()

        tk.Button(tb1, text="📊 分析", font=("", 10, "bold"),
                  bg="#FF9800", fg="white", relief=tk.FLAT, padx=8,
                  command=lambda: self._analyze_manual_code(
                      manual_var.get().strip(), kline_host, analysis_host,
                      float(acc_var.get()) if acc_var.get() else 100000,
                      float(risk_var.get()) if risk_var.get() else 0.5
                  )).pack(side=tk.LEFT, padx=4)

        # ❓ 帮助按钮
        tk.Button(tb1, text="❓", font=("", 12, "bold"),
                  bg="#1a1a3e", fg="#FFD54F", relief=tk.FLAT, cursor="hand2",
                  command=lambda: self._show_martin_help(kw)).pack(side=tk.RIGHT, padx=(4, 4), pady=6)

        # 环境标签
        env_lbl = tk.Label(tb1, text="🌐 环境: 检查中...", font=("", 10),
                           bg="#1a1a3e", fg="#9E9E9E")
        env_lbl.pack(side=tk.RIGHT, padx=15)

        # ── 顶部: 第2行 — 参数 ──
        tb2 = tk.Frame(kw, bg="#16213e")
        tb2.pack(fill=tk.X)

        tk.Label(tb2, text="📋 参数:", font=("", 10, "bold"), bg="#16213e", fg="#FFD54F").pack(side=tk.LEFT, padx=(12, 2), pady=4)

        acc_var = tk.StringVar(value="100000")
        risk_var = tk.StringVar(value="0.5")
        mc_var = tk.StringVar(value="5")
        amt_var = tk.StringVar(value="3000")
        adr_var = tk.StringVar(value="2.5")
        for label, var, w in [("账户(万):", acc_var, 8), ("风险%:", risk_var, 6),
                              ("市值≥(亿):", mc_var, 6), ("成交≥(万):", amt_var, 8),
                              ("ADR≥(%):", adr_var, 6)]:
            tk.Label(tb2, text=label, font=("", 10), bg="#16213e", fg="#B0BEC5").pack(side=tk.LEFT, padx=(10, 2))
            tk.Entry(tb2, textvariable=var, width=w, font=("", 10)).pack(side=tk.LEFT)

        # 扫描按钮
        scan_btn = tk.Button(tb2, text="🔍 扫描分析", font=("", 10, "bold"),
                             bg="#4CAF50", fg="white", relief=tk.FLAT, padx=14,
                             command=lambda: self._run_martin_scan_new(
                                 kw, tv, status_lbl,
                                 pool_var.get(),
                                 float(mc_var.get()) if mc_var.get() else 0,
                                 float(amt_var.get()) if amt_var.get() else 0,
                                 float(adr_var.get()) if adr_var.get() else 0,
                                 float(acc_var.get()) if acc_var.get() else 100000,
                                 float(risk_var.get()) if risk_var.get() else 0.5,
                                 kline_host, analysis_host
                             ))
        scan_btn.pack(side=tk.RIGHT, padx=12, pady=4)

        # ── 主体: PanedWindow 左右可拖拽分隔 ──
        pw = tk.PanedWindow(kw, orient=tk.HORIZONTAL, bg="#1a1a3e",
                            sashwidth=6, sashrelief=tk.FLAT,
                            handlepad=2)
        pw.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # ═══ 左: Notebook 三 tab (默认 540px, 可拖宽拖窄) ═══
        left = tk.Frame(pw, bg="#1a1a3e", width=540)
        pw.add(left, width=540)

        # 统一状态标签 (放在 Notebook 上面)
        status_lbl = tk.Label(left, text="👉 选股Tab点🔍扫描 | 机会K/筹码K Tab自动加载持仓龙头",
                              font=("", 10), bg="#1a1a3e", fg="#78909C", wraplength=530,
                              justify=tk.LEFT)
        status_lbl.pack(fill=tk.X, pady=(6, 2), padx=8)

        # Notebook (紧凑布局: 8 tab 要一排放得下)
        style_nb = ttk.Style()
        try:
            style_nb.theme_use("clam")
            style_nb.configure("TNotebook", background="#1a1a3e", borderwidth=0)
            style_nb.configure("TNotebook.Tab", background="#2a2a4e", foreground="#B0BEC5",
                               padding=(8, 3), font=("", 9))
            style_nb.map("TNotebook.Tab",
                         background=[("selected", "#FFD54F")],
                         foreground=[("selected", "#0f0f23")])
            try:
                style_nb.configure("TNotebook.Tab", focuscolor="none")
            except Exception:
                pass
        except Exception:
            pass

        nb = ttk.Notebook(left)
        nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        # ── Tab 1: Martin 选股列表 ──
        tab1 = tk.Frame(nb, bg="#1a1a3e"); nb.add(tab1, text="🎯 Martin选股")
        tv_frame = tk.Frame(tab1, bg="#1a1a3e")
        tv_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        cols = ("代码", "名称", "涨幅%", "成交(亿)", "ADR%", "形态", "评分", "支撑/备注")
        tv = ttk.Treeview(tv_frame, columns=cols, show="headings", height=28)
        for c, w, min_w in [("代码", 75, 60), ("名称", 100, 70), ("涨幅%", 60, 45),
                             ("成交(亿)", 65, 50), ("ADR%", 60, 45), ("形态", 85, 60),
                             ("评分", 50, 35), ("支撑/备注", 120, 80)]:
            tv.heading(c, text=c)
            tv.column(c, width=w, minwidth=min_w, stretch=False, anchor=tk.CENTER)
        vsb = ttk.Scrollbar(tv_frame, orient=tk.VERTICAL, command=tv.yview)
        hsb = ttk.Scrollbar(tv_frame, orient=tk.HORIZONTAL, command=tv.xview)
        tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tv_frame.grid_rowconfigure(0, weight=1)
        tv_frame.grid_columnconfigure(0, weight=1)

        # ── Tab 2: 🎯 机会K 列表 ──
        tab2 = tk.Frame(nb, bg="#1a1a3e"); nb.add(tab2, text="🎯 机会K")
        tv2_frame = tk.Frame(tab2, bg="#1a1a3e")
        tv2_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        cols2 = ("代码", "名称", "买入分", "卖出分", "信号数", "状态")
        tv2 = ttk.Treeview(tv2_frame, columns=cols2, show="headings", height=28)
        for c, w in [("代码", 80), ("名称", 120), ("买入分", 70),
                     ("卖出分", 70), ("信号数", 60), ("状态", 100)]:
            tv2.heading(c, text=c); tv2.column(c, width=w, anchor=tk.CENTER, stretch=False)
        vsb2 = ttk.Scrollbar(tv2_frame, orient=tk.VERTICAL, command=tv2.yview)
        tv2.configure(yscrollcommand=vsb2.set)
        tv2.grid(row=0, column=0, sticky="nsew")
        vsb2.grid(row=0, column=1, sticky="ns")
        tv2_frame.grid_rowconfigure(0, weight=1)
        tv2_frame.grid_columnconfigure(0, weight=1)
        # 存 watchlist 数据 (sina_code 转换映射)
        tv2_data = []  # [(c6, sina, name, buy100, sell100, signals_count, status)]

        # ── Tab 3: 📊 主流板块 (今日概念板块前3成分股) ──
        tab3 = tk.Frame(nb, bg="#1a1a3e"); nb.add(tab3, text="📊 主流板块")
        tv3_frame = tk.Frame(tab3, bg="#1a1a3e")
        tv3_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        cols3 = ("板块", "代码", "名称", "现价", "涨跌%")
        tv3 = ttk.Treeview(tv3_frame, columns=cols3, show="headings", height=28)
        for c, w in [("板块", 130), ("代码", 80), ("名称", 120), ("现价", 70), ("涨跌%", 70)]:
            tv3.heading(c, text=c); tv3.column(c, width=w, anchor=tk.CENTER, stretch=False)
        vsb3 = ttk.Scrollbar(tv3_frame, orient=tk.VERTICAL, command=tv3.yview)
        tv3.configure(yscrollcommand=vsb3.set)
        tv3.grid(row=0, column=0, sticky="nsew")
        vsb3.grid(row=0, column=1, sticky="ns")
        tv3_frame.grid_rowconfigure(0, weight=1)
        tv3_frame.grid_columnconfigure(0, weight=1)
        tv3_data = []  # [(c6, sina, name, block, price, chg), ...]

        # ── Tab 4: 📯 淘股吧 热股 (复用主窗口 self._taoguba_stamp_data) ──
        tab4 = tk.Frame(nb, bg="#1a1a3e"); nb.add(tab4, text="📯 淘股吧")
        tv4_frame = tk.Frame(tab4, bg="#1a1a3e")
        tv4_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        cols4 = ("代码", "名称", "现价", "涨跌%", "提及次数", "来源")
        tv4 = ttk.Treeview(tv4_frame, columns=cols4, show="headings", height=28)
        for c, w in [("代码", 80), ("名称", 110), ("现价", 65),
                     ("涨跌%", 65), ("提及次数", 70), ("来源", 100)]:
            tv4.heading(c, text=c); tv4.column(c, width=w, anchor=tk.CENTER, stretch=False)
        vsb4 = ttk.Scrollbar(tv4_frame, orient=tk.VERTICAL, command=tv4.yview)
        tv4.configure(yscrollcommand=vsb4.set)
        tv4.grid(row=0, column=0, sticky="nsew")
        vsb4.grid(row=0, column=1, sticky="ns")
        tv4_frame.grid_rowconfigure(0, weight=1)
        tv4_frame.grid_columnconfigure(0, weight=1)
        tv4_data = []  # [(c6, name), ...] 直接对应 row dict

        # ── Tab 5: 🧭 韭研公社 热股 (复用主窗口 self._jiuyan_stamp_data) ──
        tab5 = tk.Frame(nb, bg="#1a1a3e"); nb.add(tab5, text="🧭 韭研公社")
        tv5_frame = tk.Frame(tab5, bg="#1a1a3e")
        tv5_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        cols5 = ("代码", "名称", "现价", "涨跌%", "提及次数", "来源")
        tv5 = ttk.Treeview(tv5_frame, columns=cols5, show="headings", height=28)
        for c, w in [("代码", 80), ("名称", 110), ("现价", 65),
                     ("涨跌%", 65), ("提及次数", 70), ("来源", 100)]:
            tv5.heading(c, text=c); tv5.column(c, width=w, anchor=tk.CENTER, stretch=False)
        vsb5 = ttk.Scrollbar(tv5_frame, orient=tk.VERTICAL, command=tv5.yview)
        tv5.configure(yscrollcommand=vsb5.set)
        tv5.grid(row=0, column=0, sticky="nsew")
        vsb5.grid(row=0, column=1, sticky="ns")
        tv5_frame.grid_rowconfigure(0, weight=1)
        tv5_frame.grid_columnconfigure(0, weight=1)
        tv5_data = []  # 同 tv4_data

        # ── Tab 6: 👤 持仓自选 (快速选股) ──
        tab6 = tk.Frame(nb, bg="#1a1a3e"); nb.add(tab6, text="👤 持仓自选")
        tv6_frame = tk.Frame(tab6, bg="#1a1a3e")
        tv6_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        cols6 = ("代码", "名称", "池来源")
        tv6 = ttk.Treeview(tv6_frame, columns=cols6, show="headings", height=28)
        for c, w in [("代码", 90), ("名称", 140), ("池来源", 100)]:
            tv6.heading(c, text=c); tv6.column(c, width=w, anchor=tk.CENTER, stretch=False)
        vsb6 = ttk.Scrollbar(tv6_frame, orient=tk.VERTICAL, command=tv6.yview)
        tv6.configure(yscrollcommand=vsb6.set)
        tv6.grid(row=0, column=0, sticky="nsew")
        vsb6.grid(row=0, column=1, sticky="ns")
        tv6_frame.grid_rowconfigure(0, weight=1)
        tv6_frame.grid_columnconfigure(0, weight=1)
        tv6_data = []

        # ── Tab 7: 🔥 涨停热门 ──
        tab7 = tk.Frame(nb, bg="#1a1a3e"); nb.add(tab7, text="🔥 涨停热门")
        tv7_frame = tk.Frame(tab7, bg="#1a1a3e")
        tv7_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        cols7 = ("代码", "名称", "池来源")
        tv7 = ttk.Treeview(tv7_frame, columns=cols7, show="headings", height=28)
        for c, w in [("代码", 90), ("名称", 140), ("池来源", 100)]:
            tv7.heading(c, text=c); tv7.column(c, width=w, anchor=tk.CENTER, stretch=False)
        vsb7 = ttk.Scrollbar(tv7_frame, orient=tk.VERTICAL, command=tv7.yview)
        tv7.configure(yscrollcommand=vsb7.set)
        tv7.grid(row=0, column=0, sticky="nsew")
        vsb7.grid(row=0, column=1, sticky="ns")
        tv7_frame.grid_rowconfigure(0, weight=1)
        tv7_frame.grid_columnconfigure(0, weight=1)
        tv7_data = []

        # ── Tab 8: ⭐ 经典演示票 ──
        tab8 = tk.Frame(nb, bg="#1a1a3e"); nb.add(tab8, text="⭐ 经典票")
        tv8_frame = tk.Frame(tab8, bg="#1a1a3e")
        tv8_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        cols8 = ("代码", "名称", "板块")
        tv8 = ttk.Treeview(tv8_frame, columns=cols8, show="headings", height=28)
        for c, w in [("代码", 90), ("名称", 140), ("板块", 100)]:
            tv8.heading(c, text=c); tv8.column(c, width=w, anchor=tk.CENTER, stretch=False)
        vsb8 = ttk.Scrollbar(tv8_frame, orient=tk.VERTICAL, command=tv8.yview)
        tv8.configure(yscrollcommand=vsb8.set)
        tv8.grid(row=0, column=0, sticky="nsew")
        vsb8.grid(row=0, column=1, sticky="ns")
        tv8_frame.grid_rowconfigure(0, weight=1)
        tv8_frame.grid_columnconfigure(0, weight=1)
        tv8_data = []

        # ═══ 右: K线 + 分析 (可拖宽) ═══
        right = tk.Frame(pw, bg="#0f0f23")
        pw.add(right)

        kline_host = tk.Frame(right, bg="#0f0f23")
        kline_host.pack(fill=tk.BOTH, expand=True)

        analysis_host = tk.Frame(right, bg="#1a1a3e", height=180)
        analysis_host.pack(fill=tk.X, pady=(6, 0))
        analysis_host.pack_propagate(False)

        # ═══ 统一点击处理: 所有 tab 的点击 → 右边 Martin K 线 ═══
        def _build_args():
            return (kline_host, analysis_host,
                    float(acc_var.get()) if acc_var.get() else 100000,
                    float(risk_var.get()) if risk_var.get() else 0.5)

        def _on_select_tab1(_e=None):
            sel = tv.selection()
            if not sel: return
            vals = tv.item(sel[0], "values")
            self._show_martin_kline(vals[0], vals[1], *_build_args())

        def _on_select_tab2(_e=None):
            sel = tv2.selection()
            if not sel: return
            idx = tv2.index(sel[0])
            if idx < len(tv2_data):
                c6, _sina, name = tv2_data[idx][0], tv2_data[idx][1], tv2_data[idx][2]
                self._show_martin_kline(c6, name, *_build_args())

        def _on_select_tab3(_e=None):
            sel = tv3.selection()
            if not sel: return
            idx = tv3.index(sel[0])
            if idx < len(tv3_data):
                c6, _sina, name = tv3_data[idx][0], tv3_data[idx][1], tv3_data[idx][2]
                self._show_martin_kline(c6, name, *_build_args())

        tv.bind("<<TreeviewSelect>>", _on_select_tab1); tv.bind("<Double-1>", _on_select_tab1)
        tv2.bind("<<TreeviewSelect>>", _on_select_tab2); tv2.bind("<Double-1>", _on_select_tab2)
        tv3.bind("<<TreeviewSelect>>", _on_select_tab3); tv3.bind("<Double-1>", _on_select_tab3)

        # Tab4/5: 淘股吧/韭研 (从主窗口 stamp_data 读 dict → 新浪code转6位)
        def _sina_to_c6(sina_code):
            """sh600519 → 600519"""
            import re
            m = re.search(r"(\d{6})", str(sina_code))
            return m.group(1) if m else str(sina_code)

        def _on_select_tab4(_e=None):
            sel = tv4.selection()
            if not sel: return
            idx = tv4.index(sel[0])
            if idx < len(tv4_data):
                c6, nm = tv4_data[idx]
                self._show_martin_kline(c6, nm, *_build_args())

        def _on_select_tab5(_e=None):
            sel = tv5.selection()
            if not sel: return
            idx = tv5.index(sel[0])
            if idx < len(tv5_data):
                c6, nm = tv5_data[idx]
                self._show_martin_kline(c6, nm, *_build_args())

        tv4.bind("<<TreeviewSelect>>", _on_select_tab4); tv4.bind("<Double-1>", _on_select_tab4)
        tv5.bind("<<TreeviewSelect>>", _on_select_tab5); tv5.bind("<Double-1>", _on_select_tab5)

        # Tab6/7/8: 持仓自选 / 涨停热门 / 经典票
        def _on_select_tab6(_e=None):
            sel = tv6.selection()
            if not sel:
                print(f"[🎯Martin] Tab6: selection empty", flush=True)
                return
            idx = tv6.index(sel[0])
            print(f"[🎯Martin] Tab6: idx={idx}, tv6_data_len={len(tv6_data)}", flush=True)
            if idx < len(tv6_data):
                c6, nm = tv6_data[idx]
                print(f"[🎯Martin] Tab6 点击: code={c6} name={nm}", flush=True)
                self._show_martin_kline(c6, nm, *_build_args())
            else:
                print(f"[🎯Martin] Tab6: idx {idx} out of range", flush=True)

        def _on_select_tab7(_e=None):
            sel = tv7.selection()
            if not sel: return
            idx = tv7.index(sel[0])
            if idx < len(tv7_data):
                c6, nm = tv7_data[idx]
                self._show_martin_kline(c6, nm, *_build_args())

        def _on_select_tab8(_e=None):
            sel = tv8.selection()
            if not sel: return
            idx = tv8.index(sel[0])
            if idx < len(tv8_data):
                c6, nm = tv8_data[idx]
                self._show_martin_kline(c6, nm, *_build_args())

        tv6.bind("<<TreeviewSelect>>", _on_select_tab6); tv6.bind("<Double-1>", _on_select_tab6)
        tv7.bind("<<TreeviewSelect>>", _on_select_tab7); tv7.bind("<Double-1>", _on_select_tab7)
        tv8.bind("<<TreeviewSelect>>", _on_select_tab8); tv8.bind("<Double-1>", _on_select_tab8)

        # ── Tab8 经典票 (主线程直接填, 永远有) ──
        _demo_pool = [
            ("600519", "贵州茅台", "白酒"), ("000858", "五粮液", "白酒"),
            ("300750", "宁德时代", "新能源"), ("002594", "比亚迪", "新能源"),
            ("601318", "中国平安", "保险"), ("600036", "招商银行", "银行"),
            ("000333", "美的集团", "家电"), ("601888", "中国中免", "消费"),
            ("600900", "长江电力", "公用事业"), ("300059", "东方财富", "券商"),
            ("002415", "海康威视", "安防"), ("601012", "隆基绿能", "光伏"),
            ("600276", "恒瑞医药", "医药"), ("000651", "格力电器", "家电"),
            ("600030", "中信证券", "券商"), ("601899", "紫金矿业", "有色金属"),
            ("002230", "科大讯飞", "AI"), ("300760", "迈瑞医疗", "医疗器械"),
            ("000568", "泸州老窖", "白酒"), ("600309", "万华化学", "化工"),
        ]
        for c, n, s in _demo_pool:
            tv8.insert("", "end", values=(c, n, s))
            tv8_data.append((c, n))

        # ── Tab6 持仓自选 (本地, 秒出, 主线程直接填) ──
        def _ensure_code_first(tup):
            """确保 (code, name) 顺序, code 必须是 6 位数字"""
            import re
            a, b = tup[0], tup[1] if len(tup) > 1 else ""
            # 如果 a 不是 6 位纯数字, 但 b 是, 就交换
            if not re.match(r"^\d{6}$", str(a)) and re.match(r"^\d{6}$", str(b)):
                return (str(b), str(a))
            return (str(a), str(b))

        try:
            def _fill_pool(tv_w, tv_data_list, pool_name, label_prefix, limit=40):
                try:
                    items = self._get_stock_pool(pool_name, kw)
                    count = 0
                    for raw in items[:limit]:
                        code, name = _ensure_code_first(raw)
                        if not code:
                            continue
                        tv_w.insert("", "end", values=(code, name or code, label_prefix))
                        tv_data_list.append((code, name or code))
                        count += 1
                    return count
                except Exception as e:
                    print(f"[🎯Martin] _fill_pool {pool_name} 异常: {e}", flush=True)
                    return 0

            c6_h = _fill_pool(tv6, tv6_data, "持仓股", "持仓")
            c6_s = _fill_pool(tv6, tv6_data, "自选股", "自选")
            print(f"[🎯Martin] Tab6 持仓 {c6_h} + 自选 {c6_s}", flush=True)
            # 打印前 3 条验证顺序
            for i in range(min(3, len(tv6_data))):
                c, n = tv6_data[i]
                print(f"[🎯Martin] Tab6 验证 #{i}: code={c} name={n}", flush=True)
        except Exception as _e6:
            import traceback
            print(f"[🎯Martin] Tab6 填充跳过: {_e6}\n{traceback.format_exc()}", flush=True)

        # ── Tab7 涨停热门 (需要网络, 后台线程) ──
        import re as _re
        def _ec(tup):
            """ensure code first"""
            a, b = str(tup[0]), str(tup[1]) if len(tup) > 1 else ""
            if not _re.match(r"^\d{6}$", a) and _re.match(r"^\d{6}$", b):
                return (b, a)
            return (a, b)

        def _fill_tab7_bg():
            try:
                for pool_name, label in [("涨停池", "涨停"), ("热门板块", "热门板块")]:
                    try:
                        items = self._get_stock_pool(pool_name, kw)
                        for raw in items[:30]:
                            code, name = _ec(raw)
                            kw.after(0, lambda c=code, n=name, l=label: (
                                tv7.insert("", "end", values=(c, n or c, l)),
                                tv7_data.append((c, n or c))))
                    except Exception:
                        pass

            except Exception as _e7:
                print(f"[🎯Martin] Tab7 后台填充异常: {_e7}", flush=True)

        threading.Thread(target=_fill_tab7_bg, daemon=True).start()

        # ── 立即填充 Tab4/Tab5 (如果主窗口已经有 stamp_data) ──
        def _fill_stamp_tv(tv_widget, data_list, stamp_data):
            """把 stamp_data (dict list) 填到 Treeview, 返回 [(c6, name)]"""
            out = []
            for item in stamp_data[:80]:  # 最多 80 只
                try:
                    code = item.get("code", "")
                    name = item.get("name", "")
                    c6 = _sina_to_c6(code)
                    price = item.get("price", item.get("close", 0))
                    chg = item.get("chg", item.get("pct_chg", 0))
                    freq = item.get("freq", item.get("count", item.get("mentions", 0)))
                    src = item.get("source", item.get("src", ""))
                    if not name:
                        name = code
                    tv_widget.insert("", "end", values=(
                        c6, name,
                        f"{price:.2f}" if price else "-",
                        f"{chg:+.2f}%" if chg else "-",
                        freq, src[:10]))
                    out.append((c6, name))
                except Exception:
                    continue
            return out

        # ── 主线程立即填充 (三级容错: self属性 → 缓存文件 → 硬编码) ──
        def _load_stamp_with_fallback(source):
            """淘韭热股三级加载"""
            import json as _j, os as _os
            from datetime import datetime as _dt
            # 1) 主窗口已加载好的 self 属性
            data = getattr(self, f"_{source}_stamp_data", []) or []
            if data:
                return data
            # 2) 缓存文件 (tab_dapan.py 同一个)
            _today = _dt.now().strftime("%Y%m%d")
            _cache = _os.path.join(
                _os.path.dirname(_os.path.abspath(__file__)),
                "..", "..", "data", f"stamp_cache_{source}_{_today}.json")
            _cache = _os.path.normpath(_cache)
            if _os.path.exists(_cache):
                try:
                    with open(_cache, "r", encoding="utf-8") as f:
                        data = _j.load(f)
                    if isinstance(data, list) and data:
                        print(f"[🎯Martin] {source} 读缓存 OK: {len(data)} 只", flush=True)
                        return data
                except Exception:
                    pass
            # 3) 兜底: 用主流板块硬编码池 + 模拟热度
            print(f"[🎯Martin] {source} 无缓存, 用硬编码兜底池", flush=True)
            fallback_map = {
                "taoguba": [  # 淘股吧 → 半导体/CPO/机器人
                    {"code": "688256", "name": "寒武纪", "price": 0, "chg": 0, "freq": 88, "source": "淘股吧"},
                    {"code": "300308", "name": "中际旭创", "price": 0, "chg": 0, "freq": 76, "source": "淘股吧"},
                    {"code": "688981", "name": "中芯国际", "price": 0, "chg": 0, "freq": 65, "source": "淘股吧"},
                    {"code": "300496", "name": "中科创达", "price": 0, "chg": 0, "freq": 58, "source": "淘股吧"},
                    {"code": "002371", "name": "北方华创", "price": 0, "chg": 0, "freq": 52, "source": "淘股吧"},
                    {"code": "300394", "name": "天孚通信", "price": 0, "chg": 0, "freq": 48, "source": "淘股吧"},
                    {"code": "603501", "name": "韦尔股份", "price": 0, "chg": 0, "freq": 45, "source": "淘股吧"},
                    {"code": "300376", "name": "易事特", "price": 0, "chg": 0, "freq": 42, "source": "淘股吧"},
                    {"code": "300750", "name": "宁德时代", "price": 0, "chg": 0, "freq": 40, "source": "淘股吧"},
                    {"code": "002594", "name": "比亚迪", "price": 0, "chg": 0, "freq": 38, "source": "淘股吧"},
                ],
                "jiuyan": [  # 韭研 → 科技/消费/新能源
                    {"code": "600519", "name": "贵州茅台", "price": 0, "chg": 0, "freq": 92, "source": "韭研公社"},
                    {"code": "000858", "name": "五粮液", "price": 0, "chg": 0, "freq": 78, "source": "韭研公社"},
                    {"code": "300750", "name": "宁德时代", "price": 0, "chg": 0, "freq": 72, "source": "韭研公社"},
                    {"code": "002594", "name": "比亚迪", "price": 0, "chg": 0, "freq": 66, "source": "韭研公社"},
                    {"code": "601318", "name": "中国平安", "price": 0, "chg": 0, "freq": 58, "source": "韭研公社"},
                    {"code": "600036", "name": "招商银行", "price": 0, "chg": 0, "freq": 52, "source": "韭研公社"},
                    {"code": "000333", "name": "美的集团", "price": 0, "chg": 0, "freq": 48, "source": "韭研公社"},
                    {"code": "600900", "name": "长江电力", "price": 0, "chg": 0, "freq": 44, "source": "韭研公社"},
                    {"code": "601012", "name": "隆基绿能", "price": 0, "chg": 0, "freq": 42, "source": "韭研公社"},
                    {"code": "600276", "name": "恒瑞医药", "price": 0, "chg": 0, "freq": 38, "source": "韭研公社"},
                ],
            }
            return fallback_map.get(source, [])

        try:
            tg_data = _load_stamp_with_fallback("taoguba")
            jy_data = _load_stamp_with_fallback("jiuyan")
            if tg_data:
                tv4_data.extend(_fill_stamp_tv(tv4, tv4_data, tg_data))
            if jy_data:
                tv5_data.extend(_fill_stamp_tv(tv5, tv5_data, jy_data))
        except Exception as _e:
            print(f"[🎯Martin] stamp_data 填充异常: {_e}", flush=True)

        # 手动输入: 回车触发
        def _on_enter(_e):
            code = manual_var.get().strip()
            if code:
                self._analyze_manual_code(code, kline_host, analysis_host,
                                          float(acc_var.get()) if acc_var.get() else 100000,
                                          float(risk_var.get()) if risk_var.get() else 0.5)
        quick_combo.bind("<Return>", _on_enter)

        # ── 后台加载: 机会K watchlist + 主流前3板块 ──
        def _load_jc_bg():
            """机会K watchlist + 概念板块前3成分股 并行加载"""
            try:
                # 1) 机会K - 复用 tab_jianlou 的 watchlist
                try:
                    from ui.tab_jianlou import _load_watchlist as _jl_load
                    jl_pool = _jl_load()  # [(c6, sina, tag), ...]
                except Exception as e:
                    print(f"[🎯Martin] jianlou watchlist fail: {e}", flush=True)
                    jl_pool = []

                # 2) 主流板块 - 东财概念板块前3, 失败则硬编码热点龙头
                cm_pool = []  # [(c6, sina, name, block_name), ...]
                _EM_HOT = {
                    "🔬半导体": [
                        ("688256", "寒武纪"), ("688041", "海光信息"), ("688981", "中芯国际"),
                        ("002371", "北方华创"), ("603501", "韦尔股份"), ("688012", "中微公司"),
                        ("603986", "兆易创新"), ("688008", "澜起科技"), ("002049", "紫光国微"),
                        ("600460", "士兰微"),
                    ],
                    "💾存储芯片": [
                        ("603986", "兆易创新"), ("002049", "紫光国微"), ("300223", "北京君正"),
                        ("688521", "芯原股份"), ("600584", "长电科技"), ("002185", "华天科技"),
                        ("688008", "澜起科技"), ("688126", "沪硅产业"), ("688981", "中芯国际"),
                        ("603528", "多伦科技"),
                    ],
                    "🔗CPO/光模块": [
                        ("300308", "中际旭创"), ("300502", "新易盛"), ("002281", "光迅科技"),
                        ("300394", "天孚通信"), ("000988", "华工科技"), ("603083", "剑桥科技"),
                        ("688048", "长光华芯"), ("300548", "博创科技"), ("300620", "光库科技"),
                    ],
                    "🤖机器人": [
                        ("002747", "埃斯顿"), ("300124", "汇川技术"), ("601689", "拓普集团"),
                        ("002050", "三花智控"), ("603728", "鸣志电器"), ("688017", "绿的谐波"),
                        ("688165", "埃夫特"), ("002367", "康力电梯"), ("002472", "双环传动"),
                    ],
                    "📱电子/消费": [
                        ("002475", "立讯精密"), ("002241", "歌尔股份"), ("300433", "蓝思科技"),
                        ("002938", "鹏鼎控股"), ("600183", "生益科技"), ("002384", "东山精密"),
                        ("002463", "沪电股份"), ("002600", "领益智造"), ("300207", "欣旺达"),
                        ("601138", "工业富联"),
                    ],
                    "⛏️有色金属": [
                        ("601899", "紫金矿业"), ("600362", "江西铜业"), ("601600", "中国铝业"),
                        ("000630", "铜陵有色"), ("600489", "中金黄金"), ("601958", "金钼股份"),
                        ("002493", "荣盛石化"), ("000831", "五矿稀土"), ("600547", "山东黄金"),
                        ("002532", "新界泵业"),
                    ],
                    "🥇黄金": [
                        ("600489", "中金黄金"), ("600547", "山东黄金"), ("601899", "紫金矿业"),
                        ("600916", "中国黄金"), ("002155", "湖南黄金"), ("600311", "荣华实业"),
                        ("000975", "银泰黄金"), ("600086", "东方金钰"), ("603993", "洛阳钼业"),
                    ],
                    "🏦金融/券商": [
                        ("601318", "中国平安"), ("600036", "招商银行"), ("601398", "工商银行"),
                        ("600030", "中信证券"), ("601688", "华泰证券"), ("600837", "海通证券"),
                        ("601211", "国泰君安"), ("000776", "广发证券"), ("601788", "光大证券"),
                        ("601601", "中国太保"),
                    ],
                    "🔋储能/新能源": [
                        ("300750", "宁德时代"), ("002594", "比亚迪"), ("300014", "亿纬锂能"),
                        ("601012", "隆基绿能"), ("002459", "天合光能"), ("600905", "三峡能源"),
                        ("601865", "福斯特"), ("300274", "阳光电源"), ("002074", "国轩高科"),
                        ("600438", "通威股份"),
                    ],
                }

                # 2a) 尝试东财实时板块排行
                try:
                    import akshare as ak
                    import pandas as pd
                    df_concept = pd.DataFrame()
                    try:
                        df_concept = ak.stock_board_concept_name_em()
                    except Exception:
                        try: df_concept = ak.stock_board_industry_name_em()
                        except Exception: pass
                    if not df_concept.empty:
                        pct_col = next((c for c in df_concept.columns
                                       if "涨跌幅" in str(c) and "额" not in str(c)), None)
                        if pct_col:
                            df_concept = df_concept.sort_values(pct_col, ascending=False)
                        top3 = df_concept.head(3)
                        name_col = "板块名称" if "板块名称" in top3.columns else top3.columns[0]
                        for _, row in top3.iterrows():
                            bname = str(row[name_col]).strip()
                            if not bname or bname == "nan": continue
                            try:
                                df_cons = (ak.stock_board_concept_cons_em(symbol=bname)
                                           or ak.stock_board_industry_cons_em(symbol=bname))
                            except Exception:
                                continue
                            if df_cons is None or df_cons.empty: continue
                            code_col = next((c for c in df_cons.columns
                                             if "代码" in str(c) and "名称" not in str(c)), None)
                            name_col2 = next((c for c in df_cons.columns
                                              if "名称" in str(c)), None)
                            if not code_col: continue
                            for _, r2 in df_cons.head(15).iterrows():
                                c6 = str(r2[code_col]).strip()
                                if len(c6) != 6 or not c6.isdigit(): continue
                                nm = str(r2.get(name_col2, c6)).strip() if name_col2 else c6
                                sina = ("sh" if c6.startswith(("60","68","90"))
                                        else "sz" if c6.startswith(("00","30","20"))
                                        else "bj") + c6
                                cm_pool.append((c6, sina, nm, bname))
                        print(f"[🎯Martin] 主流板块(实时): {len(cm_pool)} 只", flush=True)
                except Exception as e:
                    print(f"[🎯Martin] 东财板块接口不可用({e}), 切换硬编码热点池", flush=True)

                # 2b) 硬编码 fallback (东财不可用或 cm_pool 为空时生效)
                if not cm_pool:
                    print(f"[🎯Martin] 使用硬编码热点池: 半导体/CPO/机器人/电子", flush=True)
                    for bname, stocks in _EM_HOT.items():
                        for c6, nm in stocks:
                            sina = ("sh" if c6.startswith(("60","68","90"))
                                    else "sz" if c6.startswith(("00","30","20"))
                                    else "bj") + c6
                            cm_pool.append((c6, sina, nm, bname))

                # 3) 并行拉基础行情 (只拿现价/涨跌幅/换手率/成交额)
                def _hq_map(codes_sina):
                    try:
                        from ui.tab_jianlou import _fetch_hq_batch
                        return _fetch_hq_batch(list(set(codes_sina)))
                    except Exception:
                        return {}

                jl_sinas = [s for _, s, _ in jl_pool]
                cm_sinas = [s for _, s, _, _ in cm_pool] if cm_pool else []
                hq_jl = _hq_map(jl_sinas)
                hq_cm = _hq_map(cm_sinas)

                # 4) 填 tab2 (机会K 列表, 简化版)
                jl_rows = []
                for c6, sina, tag in jl_pool:
                    hq = hq_jl.get(sina, {})
                    nm = hq.get("name", c6)
                    buy = sell = 50  # 默认中性
                    status = "🟢买入机会" if buy > sell else ("🔴卖出警告" if sell > buy else "⚪中性")
                    jl_rows.append((c6, sina, nm, buy, sell, 0, status))

                # 5) 填 tab3 (主流板块成分股, 5列)
                cm_rows = []
                for c6, sina, nm, bname in cm_pool:
                    hq = hq_cm.get(sina, {})
                    price = hq.get("price", 0)
                    chg = hq.get("chg", 0)
                    cm_rows.append((c6, sina, nm, bname, price, chg))

                # 6) 回主线程填充
                kw.after(0, lambda: _fill_tv2(jl_rows))
                kw.after(0, lambda: _fill_tv3(cm_rows))

            except Exception as e:
                import traceback
                print(f"[🎯Martin] JC watchlist 加载异常: {e}\n{traceback.format_exc()}", flush=True)
                kw.after(0, lambda: status_lbl.configure(
                    text=f"⚠️ 机会K/主流板块 加载失败"))

        def _fill_tv2(rows):
            for r in rows:
                tv2_data.append(r)
                tv2.insert("", "end", values=(r[0], r[2], r[3], r[4], r[5], r[6]))
            status_lbl.configure(text=f"✅ 机会K {len(rows)} 只 | 主流板块 加载中...")

        def _fill_tv3(rows):
            for r in rows:
                tv3_data.append(r)
                # cols3 = (板块, 代码, 名称, 现价, 涨跌%)
                tv3.insert("", "end", values=(r[3], r[0], r[2], r[4], r[5]))
            status_lbl.configure(text=f"✅ 机会K {len(tv2_data)} 只 | 主流板块 {len(rows)} 只 | 选股Tab点🔍扫描")

        threading.Thread(target=_load_jc_bg, daemon=True).start()

        # 环境检查 (后台)
        def _env_bg():
            try:
                r = self._check_market_env_safe()
                kw.after(0, lambda: env_lbl.configure(
                    text=f"🌐 环境: {r['status']}", fg=r['color']))
            except Exception:
                kw.after(0, lambda: env_lbl.configure(
                    text=f"🌐 环境: 检查失败", fg="#EF5350"))

        threading.Thread(target=_env_bg, daemon=True).start()
        print("[🎯Martin] 弹窗已打开 (3 tab: 选股/机会K/主流板块)", flush=True)

    def _analyze_manual_code(self, raw, kline_host, analysis_host, acc, risk):
        """
        解析输入 → 提取代码 → 显示 Martin 分析
        支持格式: "600519" / "600519 茅台" / "[典] 600519 贵州茅台" / "[持] 000858 五粮液"
        """
        if not raw:
            return
        raw = raw.strip()
        # 提取 6 位代码: 找第一个连续 6 位数字
        import re
        m = re.search(r'(\d{6})', raw)
        if not m:
            print(f"[🎯Martin] 无法解析代码: {raw}", flush=True)
            tk.Label(kline_host, text=f"❌ 无法识别代码: {raw}", font=("", 11),
                     bg="#0f0f23", fg="#EF5350").pack(pady=60)
            return
        code = m.group(1)
        # 提取名称 (可选, 代码后面的非数字部分)
        name = ""
        rest = raw[m.end():].strip()
        rest = re.sub(r'^[\s\]]+', '', rest)  # 去掉前导空格和 ]
        if rest:
            name = rest.split()[0] if rest.split() else rest

        print(f"[🎯Martin] 分析 {code} {name}", flush=True)

        # 记录历史
        if not hasattr(self, "_martin_history"):
            self._martin_history = []
        # 避免重复
        self._martin_history = [(c, n) for c, n in self._martin_history if c != code]
        self._martin_history.append((code, name))
        # 最多保留 20 只
        self._martin_history = self._martin_history[-20:]

        # 显示 K 线 + 分析
        self._show_martin_kline(code, name, kline_host, analysis_host, acc, risk)

    # ═══════════════════════════════════════════════════════
    # ❓ 帮助弹窗 — Martin 操盘方法完整介绍
    # ═══════════════════════════════════════════════════════

    def _show_martin_help(self, parent=None):
        """显示 Martin Luk 动量操盘系统完整说明 — 2列 + 字体可调节 + 默认大2号"""
        help_win = tk.Toplevel(parent)
        help_win.title("❓ Martin Luk 操盘方法完整介绍")
        help_win.geometry("1200x800")
        help_win.configure(bg="#1a1a3e")

        # ── 字体大小变量 (默认 +2: 12号) ──
        font_size = tk.IntVar(value=12)
        base_body = tk.StringVar(value="")  # 动态 font 字符串, 每次调节重建

        def _fonts(sz):
            """根据字号返回 4 种 font 元组"""
            return {
                "title": ("", sz + 4, "bold"),
                "subtitle": ("", sz + 1, "bold"),
                "section": ("", sz, "bold"),
                "body": ("", sz),
                "rule": ("", sz),
                "highlight": ("", sz, "bold"),
                "foot": ("", sz - 1),
            }

        # ── 顶部: 标题 + 字体调节 ──
        top = tk.Frame(help_win, bg="#1a1a3e")
        top.pack(fill=tk.X, pady=(10, 0))

        tk.Label(top, text="🎯 Martin Luk 动量操盘方法",
                font=_fonts(font_size.get())["title"],
                bg="#1a1a3e", fg="#FFD54F").pack(side=tk.LEFT, padx=12)
        tk.Label(top, text="27%胜率 × 7:1盈亏比 = 年赚969%",
                font=_fonts(font_size.get())["body"],
                bg="#1a1a3e", fg="#B0BEC5").pack(side=tk.LEFT, padx=6)

        # 字体调节
        ft = tk.Frame(top, bg="#1a1a3e")
        ft.pack(side=tk.RIGHT, padx=15)
        tk.Label(ft, text="🔤 字体:", font=("", 10),
                 bg="#1a1a3e", fg="#B0BEC5").pack(side=tk.LEFT, padx=(0, 4))

        def _change_font(delta):
            new_sz = max(8, min(20, font_size.get() + delta))
            font_size.set(new_sz)
            _rebuild_body()

        tk.Button(ft, text="A-", font=("", 10, "bold"), width=3,
                  bg="#37474F", fg="white", relief=tk.FLAT,
                  command=lambda: _change_font(-1)).pack(side=tk.LEFT, padx=2)
        tk.Label(ft, textvariable=font_size, width=3, anchor="center",
                 font=("", 10), bg="#1a1a3e", fg="#FFD54F").pack(side=tk.LEFT)
        tk.Button(ft, text="A+", font=("", 10, "bold"), width=3,
                  bg="#37474F", fg="white", relief=tk.FLAT,
                  command=lambda: _change_font(1)).pack(side=tk.LEFT, padx=2)
        tk.Button(ft, text="重置", font=("", 9), width=4,
                  bg="#37474F", fg="white", relief=tk.FLAT,
                  command=lambda: (font_size.set(12), _rebuild_body())
                  ).pack(side=tk.LEFT)

        # ── 2列主体 ──
        body_wrap = tk.Frame(help_win, bg="#1a1a3e")
        body_wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        col_left = tk.Frame(body_wrap, bg="#1a1a3e")
        col_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        col_right = tk.Frame(body_wrap, bg="#1a1a3e")
        col_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        def _make_scrollable(parent):
            """创建带滚动条的容器 frame"""
            outer = tk.Frame(parent, bg="#1a1a3e")
            outer.pack(fill=tk.BOTH, expand=True)
            cv = tk.Canvas(outer, bg="#1a1a3e", highlightthickness=0)
            sb = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=cv.yview)
            inner = tk.Frame(cv, bg="#1a1a3e")
            inner.bind("<Configure>", lambda _e: cv.configure(scrollregion=cv.bbox("all")))
            cv.create_window((0, 0), window=inner, anchor="nw")
            cv.configure(yscrollcommand=sb.set)
            cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            return cv, inner

        cv_L, frm_L = _make_scrollable(col_left)
        cv_R, frm_R = _make_scrollable(col_right)

        def _on_mousewheel_L(e): cv_L.yview_scroll(int(-1 * (e.delta / 120)), "units")
        def _on_mousewheel_R(e): cv_R.yview_scroll(int(-1 * (e.delta / 120)), "units")
        frm_L.bind_all("<MouseWheel>", _on_mousewheel_L)
        frm_R.bind_all("<MouseWheel>", _on_mousewheel_R)

        def _all_children(w):
            out = list(w.winfo_children())
            for c in out:
                out.extend(_all_children(c))
            return out

        # ── 构建内容 (延迟定义, 字体变化时重建) ──
        def _build_content(frame_container):
            """在 frame_container 上填充全部内容, 返回两个 inner frame"""
            fl = frame_container[0]  # frm_L
            fr = frame_container[1]  # frm_R

            def _sec(f, title, color="#FFD54F"):
                tk.Label(f, text=title, font=_fonts(font_size.get())["section"],
                         bg="#1a1a3e", fg=color).pack(anchor="w", pady=(14, 4), padx=4)

            def _body(f, text):
                tk.Label(f, text=text, font=_fonts(font_size.get())["body"],
                         bg="#1a1a3e", fg="#ECEFF1", wraplength=550,
                         justify=tk.LEFT).pack(anchor="w", padx=8)

            def _rule(f, text):
                tk.Label(f, text=f"  • {text}", font=_fonts(font_size.get())["rule"],
                         bg="#1a1a3e", fg="#B0BEC5", wraplength=550,
                         justify=tk.LEFT).pack(anchor="w", padx=8)

            def _hl(f, text):
                tk.Label(f, text=text, font=_fonts(font_size.get())["highlight"],
                         bg="#1a1a3e", fg="#66BB6A", wraplength=550,
                         justify=tk.LEFT).pack(anchor="w", padx=8, pady=2)

            # ═══════════ 左列: 核心理念 + 指标 + 三种买法 + 选股流程 ═══════════
            _sec(fl, "🧠 核心理念 — 先想亏多少, 再想赚多少", "#42A5F5")
            _body(fl, "Martin Luk (香港交易员), 2025 美国投资锦标赛冠军 (年收益 969%)。"
                     "方法来自瑞典交易员 Qullamaggie。")
            _hl(fl, "  一笔交易能赚多少没法预测, 能亏多少可以自己定")
            _body(fl, "只挑止损能放得很近的地方买, 看错马上认亏, 看对多拿。"
                     "亏钱单平均 -2%, 赚钱单平均 +14% → 盈亏比 7:1。"
                     "五笔亏四笔, 但赚一笔抵七笔 → 正期望。")

            _sec(fl, "📈 技术指标 (只用 4 样)", "#66BB6A")
            _rule(fl, "EMA (指数均线): 9 / 21 / 50 / 150 — 所有周期统一参数")
            _rule(fl, "成交额 (股价×成交量): 看成交了多少钱, 不是多少股")
            _rule(fl, "ADR (Average Daily Range): 平均每天振幅 % — 波动性")
            _hl(fl, "  AVWAP (锚定成交量加权均价) — 最核心! 下面详解")

            _sec(fl, "🔑 AVWAP 完整教程 (怎么看)", "#26C6DA")
            _body(fl, "💡 一句话: AVWAP 就是从【你指定的那根 K 线】开始, "
                     "把每天的成交价按成交量加权平均, 得到一条「这期间所有人的平均成本线」")
            _body(fl, "📐 公式 (每根K线算一个点, 从锚点往后累计):")
            _body(fl, "  AVWAP[t] = Σ(开盘×量 + 收盘×量 + 最高×量 + 最低×量) / Σ(量)")
            _hl(fl, "  锚点选哪里? Martin 的原则:")
            _rule(fl, "① 整理区最高的那根 K 线 (比如 AMPX 8月8日财报冲高回落的高点)")
            _rule(fl, "② 放巨量跳空的那一天 (市场分歧最大, 成本最集中)")
            _rule(fl, "③ 前后挪一两天, 看哪根让股价「碰得最准」就用哪根")
            _hl(fl, "  怎么看图上的 AVWAP?")
            _rule(fl, "📊 股价先【涨穿】AVWAP → 说明突破了所有人的平均成本 → 看多信号")
            _rule(fl, "📉 股价回落到 AVWAP 附近 → 【最佳买点】— 这里是大量人的持仓成本, 撑住概率极高")
            _rule(fl, "❌ 收盘跌破 AVWAP 且放量 → 支撑失效, 止损走")
            _body(fl, "  K线图上 AVWAP 是【橙色虚线】(EMA9黄 EMA21绿 EMA50蓝 EMA150紫)")
            _hl(fl, "  💎 Martin 秘籍: AVWAP + EMA9/21 + 前高前低 几样叠在一起 → 支撑最强!")

            _sec(fl, "🎯 三种买法 (一半以上是回调)", "#FF7043")
            _body(fl, "📉 ① 回调 Pullback — 最常用")
            _rule(fl, "趋势向上: EMA9 > EMA21 > EMA50, 且均线往上走")
            _rule(fl, "位置早: 从高点回落不久, 还在均线上方不远")
            _rule(fl, "支撑到位: 至少回 EMA9, 最好踩 EMA21 / AVWAP / 前高前低")
            _rule(fl, "几样支撑叠在一起最好 — 多拨人都在这里买")
            _hl(fl, "  ✅ 回 EMA21 胜率 > 只回 EMA9 (强股不给深回调)")

            _body(fl, "🚀 ② 突破 Breakout")
            _rule(fl, "整理至少 1-2 周 (横得越久突破越有力)")
            _rule(fl, "波动收窄: K 线贴着 EMA9, 振幅逐渐缩小")
            _rule(fl, "Inside Day: 今天高低都在前一天范围内 (蓄势)")
            _rule(fl, "位置在 AVWAP 上方")
            _hl(fl, "  ✅ 不等冲过整理区上沿, 过前一天高点就买 — 止损更近")

            _body(fl, "⚡ ③ EP 跳空 (财报/消息)")
            _rule(fl, "触发: 财报/重大消息 → 跳空高开 ≥5% + 巨量 ≥2x")
            _rule(fl, "2025版改进: 不等开盘突破, 先砸回来再买")
            _rule(fl, "先跌破开盘区间低点再涨回来的, 成功率更高")

            _sec(fl, "🔍 选股流程", "#AB47BC")
            _body(fl, "本程序提供 6 种股票来源:")
            _rule(fl, "持仓股 / 自选股 / 涨停池 / 连板池 / 热门板块 / 全市场")
            _hl(fl, "  ✅ 最快路径: 直接输入代码 (如 600519), 回车即分析")

            # ═══════════ 右列: 止损仓位 + 止盈 + 环境 + 操作流程 + 案例 + 注意 + 链接 ═══════════
            _sec(fr, "🛑 止损 / 📦 仓位 (命根子)", "#EF5350")
            _body(fr, "止损 (60-70% 单子用当日最低点):")
            _rule(fr, "优先: 当日最低价下方 (通常 1-3%)")
            _rule(fr, "太远: 触发买入K线最低点")
            _rule(fr, "上限: ADR一半 且 ≤5% — 超 3% 一般放弃")
            _hl(fr, "  ⚠️ 下单前先定好止损 — 这一条他从来不破例")

            _body(fr, "仓位计算 (倒推法):")
            _rule(fr, "风险金额 = 账户 × 0.5% (10万账户 → 每单最多亏 500 元)")
            _rule(fr, "每股风险 = 买入价 - 止损价")
            _rule(fr, "买多少股 = 风险金额 ÷ 每股风险")
            _rule(fr, "总仓位 25-30%, 小盘股 20% 以下")
            _hl(fr, "  ✅ 止损越窄 → 同风险买得越多 → 仓位自动放大")

            _sec(fr, "🎯 止盈 (分几步卖)", "#26A69A")
            _rule(fr, "第一批: 至少 3R/5R 才卖 (每次只卖 15%)")
            _rule(fr, "保本止损: EMA9 升到买入价 → 止损移到保本")
            _rule(fr, "跟踪止盈: 剩余仓位用 EMA9 跟踪")
            _rule(fr, "加速卖: 比 EMA9 高 15-20%, 或突然巨量大涨")
            _hl(fr, "  💡 行情顺的时候他拿很久 — 2025 大单子第一批多是 15R 才卖")

            _sec(fr, "🌐 市场环境 (最重要!)", "#FFCA28")
            _rule(fr, "① 自己的单子: 连被止损 → 少做, 风险往下调")
            _rule(fr, "② 指数: 上证/创业板 EMA9/21 多头排列最适合出手")
            _rule(fr, "③ 观察名单: 强股往下掉越来越多 → 行情变差")
            _hl(fr, "  ⛔ 连涨几星期没回调 → 不要大量开新仓, 多卖少买")

            _sec(fr, "📋 Martin 操盘完整流程 (8 步)", "#5C6BC0")
            _hl(fr, "  ─── ① 盘前: 环境判断 (最优先级!) ───")
            _rule(fr, "1.1 看指数 EMA9/21 方向 → 多头排列才出手")
            _rule(fr, "1.2 看自己最近几笔 → 连被止损? 今天少做或停手")
            _rule(fr, "1.3 看观察名单 → 强股往下掉的越来越多? 环境变差")

            _hl(fr, "  ─── ② 盘前: 选股 + 预判支撑 ───")
            _rule(fr, "2.1 扫出符合条件的票 (EMA21上方 + ADR≥2.5% + 成交够)")
            _rule(fr, "2.2 每只画好 AVWAP 起点 (整理区高点或巨量日)")
            _rule(fr, "2.3 标记支撑位: EMA9 / EMA21 / AVWAP / 前高前低")
            _hl(fr, "  💡 几样支撑叠在一起的价位 = 黄金买点区域")

            _hl(fr, "  ─── ③ 开盘: 等砸 (不要追!) ───")
            _rule(fr, "3.1 开盘头 30 分钟假突破最多 — 高开的票经常先被砸")
            _rule(fr, "3.2 等股价急砸 → 砸穿开盘低点更好 → 砸到支撑附近")
            _rule(fr, "3.3 分时图看量: 砸的时候量要大, 拉回来量要缩")

            _hl(fr, "  ─── ④ 分级别: 精确找买点 ───")
            _rule(fr, "4.1 开盘 5 分钟内 → 看 1 分钟图")
            _rule(fr, "4.2 开盘 5-60 分钟 → 看 5 分钟图")
            _rule(fr, "4.3 开盘 1 小时后 → 看 15 分钟图")
            _hl(fr, "  ✅ 唯一买点: 价格涨过【前一根 K 线的最高点】")
            _body(fr, "  不用等这根 K 线走完, 一过去就买!")

            _hl(fr, "  ─── ⑤ 下单: 先定止损, 再算仓位 ───")
            _rule(fr, "5.1 止损放哪? 当日最低价下方 / 触发K最低点下方")
            _rule(fr, "5.2 止损距离上限: ADR一半 且 ≤5% (超过3%一般放弃)")
            _rule(fr, "5.3 算仓位: 账户×0.5% ÷ 止损距离 = 买多少")
            _hl(fr, "  ✅ 下单前止损就定好 — 这一条他从来不破例!")

            _hl(fr, "  ─── ⑥ 买后: 立刻挂止损单 ───")
            _rule(fr, "6.1 市价买入 → 立刻挂止损市价单 (不是限价单!)")
            _rule(fr, "6.2 被打掉但形态还在? 可以再买 (止损还是放原位)")
            _rule(fr, "6.3 连被打 3-4 次 → 这只票不对, 换标的或停手")

            _hl(fr, "  ─── ⑦ 止盈: 分批卖, 用 EMA9 跟踪 ───")
            _rule(fr, "7.1 第一批: 到 3R/5R 才卖 (只卖 15%)")
            _rule(fr, "7.2 保本止损: EMA9 升到买入价 → 止损移到保本")
            _rule(fr, "7.3 跟踪: 剩余仓位用日线 EMA9 跟踪 (提前挂 EMA9 下方)")
            _rule(fr, "7.4 加速卖: 比 EMA9 高 15-20%, 或突然放巨量")
            _hl(fr, "  💡 行情顺的时候他拿很久 — 大单子多是 15R+ 才卖第一批")

            _hl(fr, "  ─── ⑧ 收盘: 复盘 + 环境评估 ───")
            _rule(fr, "8.1 标记今天哪些形态有效 (回调/突破/EP)")
            _rule(fr, "8.2 统计自己的 R 倍盈亏比 (是否还在 7:1 以上)")
            _rule(fr, "8.3 评估环境: 强股/中股/弱股比例")
            _rule(fr, "8.4 计划明天: 今天好的票回踩 EMA9/21 是明天的候选")
            _hl(fr, "  💎 连亏就少做, 连赚才加码 — 他 2025.12 回撤 26.6% 就是没守住这条!")

            _sec(fr, "🏆 成功案例", "#EC407A")
            _body(fr, "① AMPX (2025.9) 回调 赚 24R+23R")
            _rule(fr, "8月8日财报冲高回落 → 整理 5 周 → AVWAP 起点在高点")
            _rule(fr, "9月11日回踩支撑, 第一分钟砸, 第二分钟拉 → 7.57 买")
            _rule(fr, "止损 7.42 (-1.98%), 一周涨到 11+")

            _body(fr, "② SOFI (2024.11) 突破 赚 6R+19R")
            _rule(fr, "从 7→11 横一周 → inside day → 过前高 11.16 买")
            _rule(fr, "止损 10.94 (-1.97%), 拿到 EMA9 跌破全卖")

            _body(fr, "③ Planet Labs (2025.9) EP跳空 赚 23R+27R")
            _rule(fr, "高开 18% 砸到开盘价下 → 横住 5 分钟K → 下一根过前高")
            _rule(fr, "当天收 9.66 (+48%), 拿了 3 周")

            _sec(fr, "⚠️ 注意事项", "#FF5722")
            _rule(fr, "2025.12 他自己回撤 26.6% — 震荡行情来回打脸")
            _rule(fr, "85 笔一半不该做 — 连亏应停手而非赌气")
            _rule(fr, "宽止损 (>3%) 宁可不做")
            _hl(fr, "  💎 终极心法: 形态再漂亮也没有市场环境重要")

            _sec(fr, "🔗 原文链接", "#8D6E63")
            _body(fr, "知乎原文 (完整操盘方法披露):")
            _body(fr, "  https://zhuanlan.zhihu.com/p/2098724684871345451")
            _body(fr, "  (本文整理自该长文, 版权归原作者所有)")

        def _clear_frame(f):
            for c in f.winfo_children():
                c.destroy()

        def _rebuild_body():
            """字体变化时: 清空两列 → 重建"""
            _clear_frame(frm_L)
            _clear_frame(frm_R)
            _clear_frame(top)
            # 重建顶部 (字号随 font_size 变)
            tk.Label(top, text="🎯 Martin Luk 动量操盘方法",
                    font=_fonts(font_size.get())["title"],
                    bg="#1a1a3e", fg="#FFD54F").pack(side=tk.LEFT, padx=12)
            tk.Label(top, text="27%胜率 × 7:1盈亏比 = 年赚969%",
                    font=_fonts(font_size.get())["body"],
                    bg="#1a1a3e", fg="#B0BEC5").pack(side=tk.LEFT, padx=6)
            ft_new = tk.Frame(top, bg="#1a1a3e")
            ft_new.pack(side=tk.RIGHT, padx=15)
            tk.Label(ft_new, text="🔤 字体:", font=("", 10),
                     bg="#1a1a3e", fg="#B0BEC5").pack(side=tk.LEFT, padx=(0, 4))
            tk.Button(ft_new, text="A-", font=("", 10, "bold"), width=3,
                      bg="#37474F", fg="white", relief=tk.FLAT,
                      command=lambda: _change_font(-1)).pack(side=tk.LEFT, padx=2)
            tk.Label(ft_new, textvariable=font_size, width=3, anchor="center",
                     font=("", 10), bg="#1a1a3e", fg="#FFD54F").pack(side=tk.LEFT)
            tk.Button(ft_new, text="A+", font=("", 10, "bold"), width=3,
                      bg="#37474F", fg="white", relief=tk.FLAT,
                      command=lambda: _change_font(1)).pack(side=tk.LEFT, padx=2)
            tk.Button(ft_new, text="重置", font=("", 9), width=4,
                      bg="#37474F", fg="white", relief=tk.FLAT,
                      command=lambda: (font_size.set(12), _rebuild_body())
                      ).pack(side=tk.LEFT)
            _build_content((frm_L, frm_R))

        _build_content((frm_L, frm_R))

        # ── 底部关闭 ──
        close_bar = tk.Frame(help_win, bg="#1a1a3e")
        close_bar.pack(fill=tk.X, pady=(0, 10))
        tk.Button(close_bar, text="✅ 我知道了", font=_fonts(font_size.get())["section"],
                  bg="#4CAF50", fg="white", relief=tk.FLAT, padx=30, pady=6,
                  command=help_win.destroy).pack()

    def _check_market_env_safe(self):
        """检查市场环境 (用A股指数)"""
        if not AKSHARE_OK:
            return {"status": "⚪ 环境未知 (无AKShare)", "color": "#9E9E9E"}
        try:
            df_sh = ak.stock_zh_index_daily_em(symbol="sh000001")
            df_cy = ak.stock_zh_index_daily_em(symbol="sz399006")

            def _score(df):
                if df is None or df.empty or len(df) < 60:
                    return 0
                closes = df["close"].astype(float).values
                e9 = self._ema(closes, 9)[-1]
                e21 = self._ema(closes, 21)[-1]
                e50 = self._ema(closes, 50)[-1]
                return self._score_one_index(e9, e21, e50)

            total = _score(df_sh) + _score(df_cy)
            if total >= 60:
                return {"status": "🟢 环境友好 (趋势向上)", "color": "#4CAF50"}
            elif total >= 30:
                return {"status": "🟡 中性偏多 (轻仓试错)", "color": "#FFD54F"}
            else:
                return {"status": "🔴 环境偏空 (少做或观望)", "color": "#EF5350"}
        except Exception:
            return {"status": "⚪ 环境未知", "color": "#9E9E9E"}

    # ═══════════════════════════════════════════════════════
    # 🔍 选股扫描 (后台线程)
    # ═══════════════════════════════════════════════════════

    def _run_martin_scan_new(self, kw, tv, status_lbl,
                              pool_name, min_mc_yi, min_amt_wan, min_adr_pct,
                              account_value, risk_pct,
                              kline_host=None, analysis_host=None):
        """执行 Martin 风格选股 — 支持多数据源"""
        for it in tv.get_children():
            tv.delete(it)

        def _scan():
            if not AKSHARE_OK:
                kw.after(0, lambda: status_lbl.configure(text="❌ AKShare 未安装"))
                return
            try:
                kw.after(0, lambda: status_lbl.configure(
                    text=f"📂 加载 [{pool_name}] 股票池..."))
                pool = self._get_stock_pool(pool_name, kw)
                if not pool:
                    kw.after(0, lambda: status_lbl.configure(
                        text=f"⚠️ [{pool_name}] 股票池为空, 检查网络或数据源"))
                    return

                # 全市场额外基础过滤 (spot 取市值/成交额)
                spot_cache = {}
                if pool_name == "全市场":
                    df_spot = self._ak_spot_with_retry(max_retries=3)
                    if df_spot is not None and not df_spot.empty:
                        for _, row in df_spot.iterrows():
                            spot_cache[str(row.get("代码", ""))] = row

                kw.after(0, lambda: status_lbl.configure(
                    text=f"✅ [{pool_name}] 共 {len(pool)} 只, 开始分析 (会自动跳过无法连接的)"))

                results = []
                total = len(pool)

                for idx, (code, name_from_pool) in enumerate(pool):
                    if idx % 5 == 0 or idx == total - 1:
                        kw.after(0, lambda i=idx, n=total: status_lbl.configure(
                            text=f"🔄 {i+1}/{n} — 分析中... (已出 {len(results)} 只)"))

                    try:
                        # 全市场基础过滤 (用 spot)
                        if pool_name == "全市场" and spot_cache:
                            row = spot_cache.get(code)
                            if row is not None:
                                mc_col = "流通市值" if "流通市值" in row.index else "总市值"
                                mc_yi = float(row.get(mc_col, 0)) / 1e8
                                amt_y = float(row.get("成交额", 0)) / 1e8
                                if mc_yi < min_mc_yi or amt_y * 10000 < min_amt_wan:
                                    continue

                        # 拉K线 (带重试)
                        h = self._ak_hist_with_retry(code, max_retries=2)
                        if h is None or len(h) < 60:
                            continue

                        col_map = {}
                        for c in h.columns:
                            cl = str(c).lower()
                            if "日期" in c or "date" in cl: col_map[c] = "date"
                            elif "开盘" in c or "open" in cl: col_map[c] = "open"
                            elif "收盘" in c or "close" in cl: col_map[c] = "close"
                            elif "最高" in c or "high" in cl: col_map[c] = "high"
                            elif "最低" in c or "low" in cl: col_map[c] = "low"
                            elif "成交量" in c or "volume" in cl: col_map[c] = "volume"
                        h = h.rename(columns=col_map).tail(120)
                        for col in ["open", "close", "high", "low", "volume"]:
                            if col not in h.columns:
                                continue

                        closes = h["close"].astype(float).values
                        opens = h["open"].astype(float).values
                        highs = h["high"].astype(float).values
                        lows = h["low"].astype(float).values
                        vols = h["volume"].astype(float).values
                        n = len(closes)

                        ema9 = self._ema(closes, 9)
                        ema21 = self._ema(closes, 21)
                        ema50 = self._ema(closes, 50)
                        adr_arr = self._adr(highs, lows, closes, 20)
                        cur_adr = adr_arr[-1]
                        cur_price = closes[-1]

                        if cur_adr < min_adr_pct or cur_price <= ema21[-1]:
                            continue

                        anchor = np.argmax(highs[-30:]) + n - 30
                        avwap = self._avwap(highs, lows, closes, vols, anchor)

                        best = None
                        pb = self._detect_pullback(ema9, ema21, ema50, closes, avwap, anchor)
                        bk = self._detect_breakout(closes, highs, lows, vols, avwap, ema9)
                        avg_v = np.mean(vols[-20:]) if n >= 20 else vols[-1]
                        gp = self._detect_ep_gap(opens[-1], closes[-2] if n >= 2 else closes[-1],
                                                 vols[-1], avg_v)
                        for p in [pb, bk, gp]:
                            if p and (best is None or p["score"] > best["score"]):
                                best = p

                        if best is None:
                            continue

                        # 从 spot 拿补充信息, 或用 K 线数据
                        pct_chg = (closes[-1] / closes[-2] - 1) * 100 if n >= 2 else 0
                        amt_y_est = float(vols[-1] * closes[-1]) / 1e8 if n >= 1 else 0
                        display_name = name_from_pool
                        if pool_name == "全市场" and spot_cache:
                            row = spot_cache.get(code)
                            if row is not None:
                                display_name = str(row.get("名称", name_from_pool)) or name_from_pool
                                amt_y = float(row.get("成交额", 0)) / 1e8
                                if amt_y > 0:
                                    amt_y_est = amt_y

                        item = {
                            "code": code, "name": display_name or "",
                            "pct_chg": pct_chg, "amount_yi": amt_y_est,
                            "adr_pct": cur_adr, "pattern": best,
                        }
                        results.append(item)

                        # ⚡ 实时追加到 Treeview (边扫边出)
                        def _append_one(it=item):
                            if it["pattern"]["score"] < 40:
                                return  # 低分等最后排完再一次性填
                            pmap = {"pullback": "📉回调", "breakout": "🚀突破", "ep_gap": "⚡EP跳空"}
                            sup = ""
                            if it["pattern"]["type"] == "pullback":
                                sup = f"EMA={it['pattern'].get('support_level','')}"
                            elif it["pattern"]["type"] == "breakout":
                                sup = f"前高={it['pattern'].get('consolidation_high','')}"
                            else:
                                sup = f"高开={it['pattern'].get('gap_pct',0)*100:.0f}%"
                            tv.insert("", tk.END, values=(
                                it["code"], it["name"], f"{it['pct_chg']:+.2f}",
                                f"{it['amount_yi']:.1f}", f"{it['adr_pct']:.1f}",
                                pmap.get(it["pattern"]["type"], it["pattern"]["type"]),
                                it["pattern"]["score"], sup,
                            ))

                        kw.after(0, _append_one)

                        # 全市场每50只停1秒, 防封
                        if pool_name == "全市场" and idx % 50 == 0 and idx > 0:
                            import time; time.sleep(1)

                    except Exception as e:
                        print(f"[🎯Martin] 跳过 {code}: {str(e)[:50]}", flush=True)
                        continue

                # ── 全部扫完: 按分数排序 → 重排 Treeview ──
                results.sort(key=lambda x: x["pattern"]["score"], reverse=True)
                self._martin_results_cache = results

                def _fill_final():
                    # 先清空临时追加的 (只留最终Top60)
                    for it in tv.get_children():
                        tv.delete(it)
                    for r in results[:60]:
                        pmap = {"pullback": "📉回调", "breakout": "🚀突破", "ep_gap": "⚡EP跳空"}
                        sup = ""
                        if r["pattern"]["type"] == "pullback":
                            sup = f"EMA={r['pattern'].get('support_level','')}"
                        elif r["pattern"]["type"] == "breakout":
                            sup = f"前高={r['pattern'].get('consolidation_high','')}"
                        else:
                            sup = f"高开={r['pattern'].get('gap_pct',0)*100:.0f}%"
                        tv.insert("", tk.END, values=(
                            r["code"], r["name"], f"{r['pct_chg']:+.2f}",
                            f"{r['amount_yi']:.1f}", f"{r['adr_pct']:.1f}",
                            pmap.get(r["pattern"]["type"], r["pattern"]["type"]),
                            r["pattern"]["score"], sup,
                        ))
                    self._martin_last_tv_children = tv.get_children()
                    status_lbl.configure(
                        text=f"✅ 扫描完成 — [{pool_name}] 共 {len(pool)} 只 → 识别 {len(results)} 只形态候选",
                        fg="#4CAF50")

                kw.after(0, _fill_final)

            except Exception as e:
                err = traceback.format_exc()
                kw.after(0, lambda: status_lbl.configure(
                    text=f"❌ 扫描异常: {str(e)[:80]}"))
                print(f"[🎯Martin] 扫描异常:\n{err}", flush=True)

        threading.Thread(target=_scan, daemon=True).start()

    # ═══════════════════════════════════════════════════════
    # 📈 K 线弹窗 (带完整 Martin 指标)
    # ═══════════════════════════════════════════════════════

    def _show_martin_kline(self, code, name, kline_host, analysis_host,
                           account_value, risk_pct):
        """显示 Martin 风格 K 线图 + 完整交易计划 + 可勾选附图指标 + 鼠标浮窗"""
        # 清空
        for w in kline_host.winfo_children():
            w.destroy()
        for w in analysis_host.winfo_children():
            w.destroy()

        if not AKSHARE_OK:
            tk.Label(kline_host, text="❌ AKShare 未安装", font=("", 12),
                     bg="#0f0f23", fg="#EF5350").pack(pady=60)
            return

        try:
            h = self._ak_hist_with_retry(code, max_retries=2)
            print(f"[🎯Martin] _ak_hist_with_retry({code}) 返回: {'None' if h is None else f'{len(h)}行'}", flush=True)
            if h is None or len(h) < 60:
                tk.Label(kline_host, text="❌ 拉取失败 (东方财富/腾讯都连不上)", font=("", 11),
                         bg="#0f0f23", fg="#EF5350").pack(pady=60)
                return

            col_map = {}
            for c in h.columns:
                cl = str(c).lower()
                if "日期" in c or "date" in cl: col_map[c] = "date"
                elif "开盘" in c or "open" in cl: col_map[c] = "open"
                elif "收盘" in c or "close" in cl: col_map[c] = "close"
                elif "最高" in c or "high" in cl: col_map[c] = "high"
                elif "最低" in c or "low" in cl: col_map[c] = "low"
                elif "成交量" in c or "volume" in cl: col_map[c] = "volume"
                elif "成交额" in c or "amount" in cl: col_map[c] = "amount"
            h = h.rename(columns=col_map).tail(120).reset_index(drop=True)

            closes = h["close"].astype(float).values
            opens = h["open"].astype(float).values
            highs = h["high"].astype(float).values
            lows = h["low"].astype(float).values
            vols = h["volume"].astype(float).values
            amt_yi = (h["amount"].astype(float).values / 1e8
                      if "amount" in h.columns else vols * closes / 1e8)
            dates = h["date"].values if "date" in h.columns else np.arange(len(closes))
            n = len(closes)
            x = np.arange(n)

            # 预计算所有指标
            ema9 = self._ema(closes, 9)
            ema21 = self._ema(closes, 21)
            ema50 = self._ema(closes, 50)
            ema150 = self._ema(closes, 150)

            # 🎯 MA40/MA80 双均线系统 (用户指定)
            ma5 = self._ma(closes, 5)
            ma10 = self._ma(closes, 10)
            ma20 = self._ma(closes, 20)
            ma40 = self._ma(closes, 40)
            ma80 = self._ma(closes, 80)
            ma_signals = self._detect_ma_signals(ma5, ma10, ma20, ma40, ma80)

            adr_arr = self._adr(highs, lows, closes, 20)
            cur_adr = adr_arr[-1]
            anchor = np.argmax(highs[-30:]) + n - 30
            avwap = self._avwap(highs, lows, closes, vols, anchor)
            dif, dea, hist = self._macd(closes)
            k_kdj, d_kdj, j_kdj = self._kdj(highs, lows, closes)
            rsi = self._rsi(closes)
            boll_mid, boll_up, boll_dn = self._boll(closes)
            cci = self._cci(highs, lows, closes)
            tenkan, kijun, span_a, span_b, chikou = self._ichimoku(highs, lows, closes)

            # 形态
            pb = self._detect_pullback(ema9, ema21, ema50, closes, avwap, anchor)
            bk = self._detect_breakout(closes, highs, lows, vols, avwap, ema9)
            avg_v = np.mean(vols[-20:]) if n >= 20 else vols[-1]
            gp = self._detect_ep_gap(opens[-1], closes[-2] if n >= 2 else closes[-1],
                                     vols[-1], avg_v)
            patterns = [p for p in [pb, bk, gp] if p]
            best = max(patterns, key=lambda x: x["score"]) if patterns else None

            # ── 指标勾选面板 ──
            chk_frame = tk.Frame(kline_host, bg="#1a1a3e")
            chk_frame.pack(fill=tk.X, pady=(0, 2))

            # 默认勾: EMA + 布林 (主图叠加) + MACD + 成交额
            var_ema = tk.BooleanVar(value=False)     # EMA 关闭 (改 MA)
            var_avwap = tk.BooleanVar(value=True)
            var_boll = tk.BooleanVar(value=False)
            var_ichi = tk.BooleanVar(value=False)
            var_macd = tk.BooleanVar(value=True)
            var_kdj = tk.BooleanVar(value=False)
            var_rsi = tk.BooleanVar(value=False)
            var_cci = tk.BooleanVar(value=False)
            # 🎯 MA 系统开关
            var_ma_fast = tk.BooleanVar(value=True)   # MA5/10/20
            var_ma40 = tk.BooleanVar(value=True)      # MA40 红粗 (3x)
            var_ma80 = tk.BooleanVar(value=True)      # MA80 黄粗 (2x)
            var_ma_sig = tk.BooleanVar(value=True)    # 买卖信号标记
            # 🎨 情绪周期下拉框 (弹窗独立, 不依赖主界面)
            var_emo_bg = tk.BooleanVar(value=True)    # 默认勾上
            var_emo_cycle = tk.StringVar(value="震荡")  # 默认震荡 (避免主界面强制下行)

            def _mk_chk(parent, text, var, color):
                tk.Checkbutton(parent, text=text, variable=var, font=("", 9),
                               bg="#1a1a3e", fg=color, selectcolor="#1a1a3e",
                               activebackground="#1a1a3e", activeforeground=color,
                               bd=0, highlightthickness=0).pack(side=tk.LEFT, padx=3)

            tk.Label(chk_frame, text="📊MA均线:", font=("", 9, "bold"),
                     bg="#1a1a3e", fg="#FFD54F").pack(side=tk.LEFT, padx=(6, 2))
            _mk_chk(chk_frame, "MA5/10/20", var_ma_fast, "#FFD54F")
            _mk_chk(chk_frame, "MA40🔴", var_ma40, "#EF5350")
            _mk_chk(chk_frame, "MA80🟡", var_ma80, "#FFEB3B")
            _mk_chk(chk_frame, "✍️买卖信号", var_ma_sig, "#E91E63")
            tk.Label(chk_frame, text=" │ 其他:", font=("", 9),
                     bg="#1a1a3e", fg="#B0BEC5").pack(side=tk.LEFT, padx=(6, 2))
            _mk_chk(chk_frame, "AVWAP", var_avwap, "#FF7043")
            _mk_chk(chk_frame, "布林", var_boll, "#E040FB")
            _mk_chk(chk_frame, "一目均衡", var_ichi, "#26C6DA")
            # 🎭 独立情绪周期下拉框 (弹窗自己的, 不跟主界面走)
            tk.Label(chk_frame, text=" 🎭情绪:", font=("", 9, "bold"),
                     bg="#1a1a3e", fg="#FFD54F").pack(side=tk.LEFT, padx=(4, 1))
            emo_combo = ttk.Combobox(chk_frame, textvariable=var_emo_cycle,
                                     values=["上行", "震荡", "下行"],
                                     width=6, state="readonly", font=("", 9))
            emo_combo.pack(side=tk.LEFT, padx=2)
            emo_combo.bind("<<ComboboxSelected>>", lambda _e: _rebuild())
            tk.Label(chk_frame, text="  │ 副图:", font=("", 9),
                     bg="#1a1a3e", fg="#B0BEC5").pack(side=tk.LEFT, padx=(6, 2))
            _mk_chk(chk_frame, "MACD", var_macd, "#EF5350")
            _mk_chk(chk_frame, "KDJ", var_kdj, "#66BB6A")
            _mk_chk(chk_frame, "RSI", var_rsi, "#42A5F5")
            _mk_chk(chk_frame, "CCI", var_cci, "#AB47BC")

            # ── matplotlib: 动态布局 ──
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import matplotlib.patches as mpatches

            colors_candle = ["#EF5350" if closes[i] >= opens[i] else "#42A5F5" for i in range(n)]

            def _build_figure():
                """根据当前勾选重建 figure"""
                # 收集要画的副图
                subplots_main = []  # (name, data_tuple, ylabel)
                if var_macd.get():
                    subplots_main.append(("MACD", (dif, dea, hist), "MACD"))
                if var_kdj.get():
                    subplots_main.append(("KDJ", (k_kdj, d_kdj, j_kdj), "KDJ"))
                if var_rsi.get():
                    subplots_main.append(("RSI", (rsi,), "RSI"))
                if var_cci.get():
                    subplots_main.append(("CCI", (cci,), "CCI"))

                n_axes = 1 + len(subplots_main) + 1  # 主图 + 副图 + 成交
                height_ratios = [3] + [1.2] * len(subplots_main) + [1]

                # ── 🎯 情绪周期动态背景色 (弹窗独立下拉框, 不读主界面) ──
                _cycle = var_emo_cycle.get() if var_emo_bg.get() else None

                if _cycle == "上行":     # 🟢 绿色牛市背景 (差异极大!)
                    bg_fig = "#A5D6A7"; bg_ax = "#C8E6C9"
                    leg_bg = "#66BB6A"; leg_fg = "#002105"
                    spine_c = "#2E7D32"; grid_c = "#81C784"
                    tick_c = "#1B5E20"
                    cloud_up = "#2E7D32"; cloud_dn = "#66BB6A"  # 多云深绿
                elif _cycle == "下行":   # 🔴 红色熊市背景 (差异极大!)
                    bg_fig = "#EF9A9A"; bg_ax = "#FFCDD2"
                    leg_bg = "#EF5350"; leg_fg = "#210000"
                    spine_c = "#C62828"; grid_c = "#E57373"
                    tick_c = "#B71C1C"
                    cloud_up = "#EF5350"; cloud_dn = "#B71C1C"  # 空云深红
                else:                    # ⚪ 震荡/默认 米白+深色 (差异极大!)
                    bg_fig = "#ECEFF1"; bg_ax = "#F5F5F5"
                    leg_bg = "#37474F"; leg_fg = "#FFFFFF"
                    spine_c = "#546E7A"; grid_c = "#CFD8DC"
                    tick_c = "#263238"
                    cloud_up = "#26A69A"; cloud_dn = "#EF5350"

                fig = Figure(figsize=(13, 3 + 1.2 * n_axes),
                             facecolor=bg_fig, dpi=95)
                gs = fig.add_gridspec(n_axes, 1, height_ratios=height_ratios,
                                      hspace=0.15)
                axes = [fig.add_subplot(gs[i], facecolor=bg_ax) for i in range(n_axes)]
                ax_main = axes[0]

                # ── 主图: 蜡烛 ──
                for i in range(n):
                    ax_main.plot([x[i], x[i]], [lows[i], highs[i]],
                                 color=colors_candle[i], lw=0.5)
                    body_bot = min(opens[i], closes[i])
                    body_h = max(abs(closes[i] - opens[i]), 0.01)
                    ax_main.add_patch(mpatches.Rectangle(
                        (x[i] - 0.3, body_bot), 0.6, body_h,
                        facecolor=colors_candle[i], edgecolor=colors_candle[i]))

                # 🎯 主图叠加: MA 5/10/20/40/80 系统
                if var_ma_fast.get():
                    ax_main.plot(x, ma5, color="#FFD54F", lw=0.8, label="MA5", alpha=0.85)
                    ax_main.plot(x, ma10, color="#81D4FA", lw=0.9, label="MA10", alpha=0.85)
                    ax_main.plot(x, ma20, color="#66BB6A", lw=1.0, label="MA20", alpha=0.85)
                if var_ma40.get():
                    ax_main.plot(x, ma40, color="#EF5350", lw=3.0, label="MA40🔴", alpha=0.95)
                if var_ma80.get():
                    ax_main.plot(x, ma80, color="#FFEB3B", lw=2.5, label="MA80🟡", alpha=0.95)

                # 🎯 买卖信号标记 (基于 MA40/MA80 系统)
                if var_ma_sig.get() and ma_signals:
                    for idx_sig, sig_type, _price in ma_signals:
                        if sig_type == "buy":
                            # 买入: 绿色上三角 (在蜡烛下方)
                            ax_main.scatter(idx_sig, lows[idx_sig] * 0.97,
                                            marker="^", s=180, color="#00E676",
                                            zorder=10, edgecolors="white", linewidths=0.8)
                            ax_main.annotate("🟢买入", xy=(idx_sig, lows[idx_sig] * 0.97),
                                             xytext=(0, -18), textcoords="offset points",
                                             color="#00E676", fontsize=7, ha="center",
                                             fontweight="bold")
                        elif sig_type == "sell_half":
                            # 减仓半: 橙色下三角
                            ax_main.scatter(idx_sig, highs[idx_sig] * 1.03,
                                            marker="v", s=150, color="#FF9800",
                                            zorder=10, edgecolors="white", linewidths=0.8)
                            ax_main.annotate("🟠减仓半", xy=(idx_sig, highs[idx_sig] * 1.03),
                                             xytext=(0, 14), textcoords="offset points",
                                             color="#FF9800", fontsize=7, ha="center",
                                             fontweight="bold")
                        elif sig_type == "sell_all":
                            # 清仓: 红色大下三角 + 大字
                            ax_main.scatter(idx_sig, highs[idx_sig] * 1.05,
                                            marker="v", s=250, color="#D32F2F",
                                            zorder=10, edgecolors="white", linewidths=1.2)
                            ax_main.annotate("🔴清仓", xy=(idx_sig, highs[idx_sig] * 1.05),
                                             xytext=(0, 18), textcoords="offset points",
                                             color="#D32F2F", fontsize=8, ha="center",
                                             fontweight="bold",
                                             bbox=dict(boxstyle="round,pad=0.2",
                                                       fc="#FFCDD2", ec="#D32F2F", alpha=0.9))
                if var_avwap.get():
                    vw = ~np.isnan(avwap)
                    if np.any(vw):
                        ax_main.plot(x[vw], avwap[vw], color="#FF7043", lw=1.3,
                                     linestyle="--", label="AVWAP", alpha=0.9)
                        ax_main.annotate("AVWAP起点", xy=(anchor, highs[anchor]),
                                         color="#FF7043", fontsize=7, ha="center",
                                         xytext=(0, -15), textcoords="offset points")
                if var_boll.get():
                    ax_main.plot(x, boll_mid, color="#E040FB", lw=0.8, linestyle=":",
                                 label="BOLL中")
                    ax_main.plot(x, boll_up, color="#E040FB", lw=0.7, alpha=0.6)
                    ax_main.plot(x, boll_dn, color="#E040FB", lw=0.7, alpha=0.6)
                    ax_main.fill_between(x, boll_up, boll_dn, color="#E040FB", alpha=0.06)
                if var_ichi.get():
                    va = ~np.isnan(span_a); vb = ~np.isnan(span_b)
                    if np.any(va) and np.any(vb):
                        ax_main.fill_between(x,
                                             np.where(va & vb, np.maximum(span_a, span_b), np.nan),
                                             np.where(va & vb, np.minimum(span_a, span_b), np.nan),
                                             where=(span_a >= span_b),
                                             color=cloud_up, alpha=0.25)  # 多云
                        ax_main.fill_between(x,
                                             np.where(va & vb, np.maximum(span_a, span_b), np.nan),
                                             np.where(va & vb, np.minimum(span_a, span_b), np.nan),
                                             where=(span_a < span_b),
                                             color=cloud_dn, alpha=0.25)  # 空云
                    vt = ~np.isnan(tenkan); vk = ~np.isnan(kijun)
                    if np.any(vt):
                        ax_main.plot(x[vt], tenkan[vt], color="#26C6DA", lw=0.9,
                                     label="转换线T", alpha=0.9)
                    if np.any(vk):
                        ax_main.plot(x[vk], kijun[vk], color="#FFB74D", lw=0.9,
                                     label="基准线K", alpha=0.9)
                    vc = ~np.isnan(chikou)
                    if np.any(vc):
                        ax_main.plot(x[vc], chikou[vc], color="#CE93D8", lw=0.7,
                                     linestyle=":", label="迟行带C", alpha=0.8)

                # 主图标题 + 样式
                parts = [f"{code} {name}"]
                if best:
                    pt = {"pullback": "📉回调", "breakout": "🚀突破", "ep_gap": "⚡EP跳空"}.get(
                        best["type"], best["type"])
                    parts.append(f"| {pt} 评分 {best['score']}")
                ax_main.set_title("  ".join(parts), color=leg_fg, fontsize=11, fontweight="bold")
                ax_main.tick_params(colors=tick_c, labelsize=8)
                for s in ax_main.spines.values():
                    s.set_color(spine_c)
                ax_main.grid(True, color=grid_c, lw=0.3, alpha=0.5)
                ax_main.legend(loc="upper left", fontsize=7, facecolor=leg_bg,
                               edgecolor=spine_c, labelcolor=leg_fg, ncol=3)

                # ── 副图 MACD/KDJ/RSI/CCI ──
                for idx, (sub_name, data, ylabel) in enumerate(subplots_main):
                    ax = axes[idx + 1]
                    if sub_name == "MACD":
                        ax.bar(x, hist, color=["#EF5350" if v >= 0 else "#42A5F5" for v in hist],
                               width=0.6)
                        ax.plot(x, dif, color="#EF5350", lw=0.9, label="DIF")
                        ax.plot(x, dea, color="#42A5F5", lw=0.9, label="DEA")
                    elif sub_name == "KDJ":
                        ax.plot(x, data[0], color="#EF5350", lw=0.9, label="K")
                        ax.plot(x, data[1], color="#42A5F5", lw=0.9, label="D")
                        ax.plot(x, data[2], color="#FFD54F", lw=0.9, label="J", alpha=0.8)
                        ax.axhline(80, color="#555", ls="--", lw=0.5)
                        ax.axhline(20, color="#555", ls="--", lw=0.5)
                    elif sub_name == "RSI":
                        ax.plot(x, data[0], color="#42A5F5", lw=1.0, label="RSI14")
                        ax.axhline(70, color="#EF5350", ls="--", lw=0.5, alpha=0.6)
                        ax.axhline(30, color="#66BB6A", ls="--", lw=0.5, alpha=0.6)
                    elif sub_name == "CCI":
                        ax.plot(x, data[0], color="#AB47BC", lw=1.0, label="CCI")
                        ax.axhline(100, color="#EF5350", ls="--", lw=0.5, alpha=0.6)
                        ax.axhline(-100, color="#66BB6A", ls="--", lw=0.5, alpha=0.6)
                    ax.set_ylabel(ylabel, color=tick_c, fontsize=8)
                    ax.tick_params(colors=tick_c, labelsize=8)
                    for s in ax.spines.values():
                        s.set_color(spine_c)
                    ax.grid(True, color=grid_c, lw=0.3, alpha=0.3)
                    ax.legend(loc="upper left", fontsize=7, facecolor=leg_bg,
                              edgecolor=spine_c, labelcolor=leg_fg)

                # ── 最后一个轴: 成交额 ──
                ax_vol = axes[-1]
                ax_vol.bar(x, amt_yi, color=colors_candle, width=0.6)
                ax_vol.set_ylabel("成交(亿)", color=tick_c, fontsize=8)
                ax_vol.tick_params(colors=tick_c, labelsize=8)
                for s in ax_vol.spines.values():
                    s.set_color(spine_c)
                ax_vol.grid(True, color=grid_c, lw=0.3, alpha=0.3)

                # 日期轴 (只在最底部)
                tick_step = max(1, n // 10)
                ax_vol.set_xticks(x[::tick_step])
                try:
                    ax_vol.set_xticklabels([str(d)[:10] for d in dates[::tick_step]],
                                           color=tick_c, fontsize=7, rotation=30)
                except Exception:
                    pass
                for a in axes[:-1]:
                    a.set_xticklabels([])

                return fig, axes

            # 第一次构建
            fig, axes_list = _build_figure()
            canvas = FigureCanvasTkAgg(fig, master=kline_host)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # 重建函数 (勾选变化时调用)
            def _rebuild(*_):
                try:
                    canvas.get_tk_widget().destroy()
                    fig_new, axes_new = _build_figure()
                    canvas_new = FigureCanvasTkAgg(fig_new, master=kline_host)
                    canvas_new.draw()
                    canvas_new.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                    # 重新绑 motion
                    canvas_new.mpl_connect("motion_notify_event", _on_motion)
                    canvas_new.mpl_connect("axes_leave_event", _on_leave)
                    # 更新引用
                    canvas_ref[0] = canvas_new
                except Exception as e:
                    print(f"[🎯Martin] rebuild fail: {e}", flush=True)

            var_ema.trace_add("write", _rebuild)
            var_ma_fast.trace_add("write", _rebuild)
            var_ma40.trace_add("write", _rebuild)
            var_ma80.trace_add("write", _rebuild)
            var_ma_sig.trace_add("write", _rebuild)
            var_avwap.trace_add("write", _rebuild)
            var_boll.trace_add("write", _rebuild)
            var_ichi.trace_add("write", _rebuild)
            var_macd.trace_add("write", _rebuild)
            var_kdj.trace_add("write", _rebuild)
            var_rsi.trace_add("write", _rebuild)
            var_cci.trace_add("write", _rebuild)
            var_emo_bg.trace_add("write", _rebuild)

            canvas_ref = [canvas]  # 用 list 做可变引用

            # ── 鼠标浮窗 ──
            float_win = [None]  # 可变引用

            def _on_leave(_evt):
                if float_win[0] is not None:
                    try:
                        float_win[0].destroy()
                    except Exception:
                        pass
                    float_win[0] = None

            def _on_motion(event):
                if event.inaxes is None or event.xdata is None:
                    return
                idx = int(round(event.xdata))
                if idx < 0 or idx >= n:
                    return

                # 计算屏幕绝对右上位置
                root = kline_host.winfo_toplevel()
                sw = root.winfo_screenwidth()
                tw = 400  # 估算宽度
                th = 380
                geo = f"+{sw - tw - 20}+20"

                # 销毁旧浮窗
                if float_win[0] is not None:
                    try:
                        float_win[0].destroy()
                    except Exception:
                        pass
                fw = tk.Toplevel(root)
                fw.overrideredirect(True)  # 无边框
                fw.attributes("-topmost", True)
                fw.geometry(f"+{sw - 400 - 20}+20")
                float_win[0] = fw

                # 半透明深色卡
                card = tk.Frame(fw, bg="#1a1a3e", highlightbackground="#FFD54F",
                                highlightthickness=2)
                card.pack(fill=tk.BOTH, expand=True)

                date_str = str(dates[idx])[:10]
                cur_o = opens[idx]; cur_h = highs[idx]; cur_l = lows[idx]; cur_c = closes[idx]
                cur_v = vols[idx]
                pct = (cur_c / opens[idx] - 1) * 100

                # 标题
                tk.Label(card, text=f"📊 {code} {name}  {date_str}",
                         font=("", 11, "bold"), bg="#1a1a3e", fg="#FFD54F").pack(
                    anchor="w", padx=12, pady=(8, 2))

                # OHLCV
                color_pct = "#EF5350" if pct < 0 else "#66BB6A"
                tk.Label(card,
                         text=f"开 {cur_o:.2f}  高 {cur_h:.2f}  低 {cur_l:.2f}  收 {cur_c:.2f}  "
                              f"量 {cur_v/1e6:.1f}M",
                         font=("Menlo", 10), bg="#1a1a3e", fg="#ECEFF1").pack(anchor="w", padx=12)
                tk.Label(card, text=f"涨跌: {pct:+.2f}%",
                         font=("Menlo", 10, "bold"), bg="#1a1a3e", fg=color_pct).pack(
                    anchor="w", padx=12)

                # 分隔
                tk.Frame(card, bg="#37474F", height=1).pack(fill=tk.X, padx=12, pady=4)

                # ① 蜡烛形态
                candle_name, candle_dir, candle_score = self._identify_candle(cur_o, cur_h, cur_l, cur_c)
                dir_color = "#66BB6A" if candle_dir == "↑" else ("#EF5350" if candle_dir == "↓" else "#FFD54F")
                tk.Label(card, text=f"🕯️ 蜡烛形态",
                         font=("", 9, "bold"), bg="#1a1a3e", fg="#B0BEC5").pack(anchor="w", padx=12)
                tk.Label(card,
                         text=f"  {candle_name} {candle_dir}  (强度 {'★' * candle_score})",
                         font=("", 10, "bold"), bg="#1a1a3e", fg=dir_color).pack(anchor="w", padx=12)

                # ② 成功概率
                tk.Label(card, text=f"🎯 成功概率估算",
                         font=("", 9, "bold"), bg="#1a1a3e", fg="#B0BEC5").pack(anchor="w", padx=12, pady=(4, 0))
                try:
                    prob, notes = self._calc_win_probability(
                        closes[:idx + 1], ema9[:idx + 1], ema21[:idx + 1],
                        ema50[:idx + 1], adr_arr[min(idx, n - 1)],
                        best["type"] if best else "pullback")
                    prob_color = "#66BB6A" if prob >= 55 else ("#FFD54F" if prob >= 40 else "#EF5350")
                    tk.Label(card, text=f"  {prob}%  ({notes})",
                             font=("Menlo", 9), bg="#1a1a3e", fg=prob_color,
                             wraplength=370, justify=tk.LEFT).pack(anchor="w", padx=12)
                except Exception as e:
                    tk.Label(card, text=f"  计算中... ({str(e)[:20]})",
                             font=("", 9), bg="#1a1a3e", fg="#FFD54F").pack(anchor="w", padx=12)

                # ③ 期货K线结构分析
                tk.Label(card, text=f"📉 期货K线结构",
                         font=("", 9, "bold"), bg="#1a1a3e", fg="#B0BEC5").pack(anchor="w", padx=12, pady=(4, 0))
                try:
                    analysis = self._futures_kline_analysis(
                        closes[:idx + 1], highs[:idx + 1],
                        lows[:idx + 1], vols[:idx + 1])
                    tk.Label(card, text=f"  {analysis}",
                             font=("Menlo", 9), bg="#1a1a3e", fg="#ECEFF1",
                             wraplength=370, justify=tk.LEFT).pack(anchor="w", padx=12)
                except Exception:
                    pass

                # ④ 关键指标值
                tk.Label(card, text=f"📐 当前指标值",
                         font=("", 9, "bold"), bg="#1a1a3e", fg="#B0BEC5").pack(anchor="w", padx=12, pady=(4, 0))
                idx_e9 = ema9[idx] if not np.isnan(ema9[idx]) else float("nan")
                idx_e21 = ema21[idx] if not np.isnan(ema21[idx]) else float("nan")
                idx_e50 = ema50[idx] if not np.isnan(ema50[idx]) else float("nan")
                idx_rsi = rsi[idx] if not np.isnan(rsi[idx]) else float("nan")
                idx_cci = cci[idx] if not np.isnan(cci[idx]) else float("nan")
                idx_k = k_kdj[idx] if not np.isnan(k_kdj[idx]) else float("nan")
                idx_adx_placeholder = cur_adr

                tk.Label(card,
                         text=f"  EMA9={idx_e9:.2f}  EMA21={idx_e21:.2f}  EMA50={idx_e50:.2f}",
                         font=("Menlo", 9), bg="#1a1a3e", fg="#FFD54F").pack(anchor="w", padx=12)
                tk.Label(card,
                         text=f"  RSI={idx_rsi:.1f}  KDJ-K={idx_k:.1f}  CCI={idx_cci:.1f}  ADR={idx_adx_placeholder:.1f}%",
                         font=("Menlo", 9), bg="#1a1a3e", fg="#42A5F5").pack(anchor="w", padx=12, pady=(0, 6))

            canvas.mpl_connect("motion_notify_event", _on_motion)
            canvas.mpl_connect("axes_leave_event", _on_leave)

            # ── 分析面板 ──
            self._fill_martin_analysis(
                analysis_host, code, name, closes, ema9, ema21, ema50, ema150,
                avwap, cur_adr, best, account_value, risk_pct, highs, lows
            )

        except Exception as e:
            import traceback
            tk.Label(kline_host, text=f"K线失败: {str(e)[:80]}", font=("", 11),
                     bg="#0f0f23", fg="#EF5350").pack(pady=40)
            print(f"[🎯Martin] K线异常:\n{traceback.format_exc()}", flush=True)

    def _fill_martin_analysis(self, host, code, name, closes, ema9, ema21, ema50, ema150,
                               avwap, adr_pct, pattern, acc, risk_pct, highs, lows):
        """填充分析面板 — 左形态 | 中指标 | 右交易计划"""
        host.configure(bg="#1a1a3e")
        cur = closes[-1]

        # ── 左: 形态识别 ──
        L = tk.Frame(host, bg="#1a1a3e")
        L.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        tk.Label(L, text="📊 形态识别", font=("", 10, "bold"),
                bg="#1a1a3e", fg="#FFD54F").pack(anchor="w")
        if pattern:
            pt = {"pullback": "📉 回调", "breakout": "🚀 突破", "ep_gap": "⚡ EP跳空"}.get(
                pattern["type"], pattern["type"])
            tk.Label(L, text=f"{pt}  评分 {pattern['score']}/100", font=("", 10, "bold"),
                    bg="#1a1a3e", fg="#4CAF50").pack(anchor="w", pady=(2, 2))
            for r in pattern.get("reasons", []):
                tk.Label(L, text=f"• {r}", font=("", 9),
                        bg="#1a1a3e", fg="#90A4AE").pack(anchor="w")
        else:
            tk.Label(L, text="未识别到标准形态 (可参考支撑/止损手动判断)",
                    font=("", 9), bg="#1a1a3e", fg="#78909C", wraplength=280,
                    justify=tk.LEFT).pack(anchor="w", pady=5)

        # ── 中: 指标数值 ──
        M = tk.Frame(host, bg="#1a1a3e")
        M.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        tk.Label(M, text="📈 指标数值", font=("", 10, "bold"),
                bg="#1a1a3e", fg="#FFD54F").pack(anchor="w")
        lines = [f"当前价: {cur:.2f}"]
        for label, val in [("EMA9", ema9[-1]), ("EMA21", ema21[-1]), ("EMA50", ema50[-1])]:
            lines.append(f"{label}: {val:.2f} {'🟢' if cur > val else '🔴'}")
        v150 = ema150[-1] if not np.isnan(ema150[-1]) else None
        if v150:
            lines.append(f"EMA150:{v150:.2f} {'🟢' if cur > v150 else '🔴'}")
        vwap_v = avwap[-1] if not np.isnan(avwap[-1]) else None
        if vwap_v:
            lines.append(f"AVWAP: {vwap_v:.2f} {'🟢' if cur > vwap_v else '🔴'}")
        lines.append(f"ADR(20): {adr_pct:.1f}%")
        for line in lines:
            tk.Label(M, text=line, font=("", 9),
                    bg="#1a1a3e", fg="#ECEFF1").pack(anchor="w")

        # ── 右: 交易计划 ──
        R = tk.Frame(host, bg="#1a1a3e")
        R.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        tk.Label(R, text="💰 交易计划", font=("", 10, "bold"),
                bg="#1a1a3e", fg="#FFD54F").pack(anchor="w")

        # 止损
        sl = self._calc_stop_loss(cur, lows[-1], lows[-2] if len(lows) >= 2 else lows[-1], adr_pct)
        if sl:
            sl_color = "#4CAF50" if sl["distance_pct"] <= 3 else (
                "#FFD54F" if sl["distance_pct"] <= 5 else "#EF5350")
            tk.Label(R, text=f"🛑 止损 {sl['stop_price']:.2f} ({sl['distance_pct']:.2f}%)",
                    font=("", 10, "bold"), bg="#1a1a3e", fg=sl_color).pack(anchor="w")
            tk.Label(R, text=f"   {sl['method']}", font=("", 9),
                    bg="#1a1a3e", fg="#78909C").pack(anchor="w")
            if sl.get("warning"):
                tk.Label(R, text=sl["warning"], font=("", 9),
                        bg="#1a1a3e", fg="#FFD54F").pack(anchor="w")

            # 仓位
            pos = self._calc_position_size(acc, risk_pct, cur, sl["stop_price"])
            if pos:
                tk.Label(R, text=f"📦 {pos['shares']}股 × {cur:.2f} = {pos['position_value']:.0f}",
                        font=("", 9), bg="#1a1a3e", fg="#ECEFF1").pack(anchor="w", pady=(3, 0))
                tk.Label(R, text=f"   仓位 {pos['position_pct']:.1f}% | 风险 {pos['risk_amount']:.0f}",
                        font=("", 9), bg="#1a1a3e", fg="#78909C").pack(anchor="w")

            # 止盈
            tk.Label(R, text="🎯 R倍止盈:", font=("", 9),
                    bg="#1a1a3e", fg="#FFD54F").pack(anchor="w", pady=(3, 0))
            for tp in self._calc_r_targets(cur, sl["stop_price"]):
                tk.Label(R, text=f"   {tp['r']}R→{tp['price']:.2f} (+{tp['gain_pct']:.1f}%)",
                        font=("", 9), bg="#1a1a3e", fg="#66BB6A").pack(anchor="w")
        else:
            tk.Label(R, text="❌ 无法计算止损", font=("", 10),
                    bg="#1a1a3e", fg="#EF5350").pack(anchor="w", pady=10)

        # ── 底部: Martin 心法 ──
        tip_text = "💡 Martin心法: 止损越窄, 同样风险能买的越多 | 形态再漂亮也没有市场环境重要 | 连亏就停, 少做"
        tip = tk.Label(host, text=tip_text, font=("", 8), bg="#1a1a3e", fg="#546E7A")
        tip.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=(0, 4))
