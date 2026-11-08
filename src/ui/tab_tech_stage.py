# -*- coding: utf-8 -*-
"""
📊 操盘阶段识别 + 技术形态分析 Mixin
========================================
核心算法: 判断股票处于 "吸筹 → 洗盘 → 拉升 → 出货" 哪个阶段
特征维度:
  1. MA5/MA10/MA20/MA60 均线位置、方向、排列
  2. 量能系统 (放量/缩量/倍量/地量/量价背离)
  3. K线形态 (上升/下降/震荡区间 + 红绿背景色)
  4. 机构票 vs 游资票识别 (均线操盘偏好 + 基金重仓 + 龙虎榜)
  5. MACD/RSI 辅助信号
数据源: AKShare 免费 (stock_zh_a_hist 日线) + stock_fund_stock_holder 基金持仓
"""
import json
import os
import re
import threading
import time
from collections import Counter
from datetime import datetime, timedelta

import tkinter as tk
from tkinter import ttk

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────
# 📐 核心计算函数 (纯数学, 不依赖 UI)
# ─────────────────────────────────────────────────────────────

def _calc_ma(series: pd.Series, window: int) -> pd.Series:
    """计算移动平均线 (pandas rolling)"""
    return series.rolling(window=window, min_periods=1).mean()


def _calc_macd(close: pd.Series, fast=12, slow=26, signal=9):
    """MACD 计算"""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = 2 * (dif - dea)
    return dif, dea, macd


def _calc_rsi(close: pd.Series, period=14) -> pd.Series:
    """RSI 计算"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _calc_boll(close: pd.Series, window=20, k=2):
    """布林带"""
    mid = close.rolling(window=window).mean()
    std = close.rolling(window=window).std()
    return mid - k * std, mid, mid + k * std


# ─────────────────────────────────────────────────────────────
# 🎯 操盘阶段识别主函数
# ─────────────────────────────────────────────────────────────

def analyze_trading_stage(df: pd.DataFrame, fund_df=None, top_n=20):
    """
    分析单只股票的操盘阶段 + 技术形态 + 机构/游资属性
    Args:
        df: 日线数据 (open/high/low/close/volume)
        fund_df: 基金持仓 DataFrame (可选, 判断机构票)
        top_n: 看最近多少根 K 线
    Returns:
        dict: {
            'stage': '吸筹'|'洗盘'|'拉升'|'出货'|'下跌'|'底部横盘',
            'stage_score': 0-100,
            'institution_vs_hot_money': '机构票'|'游资票'|'混合型',
            'institution_score': 0-100,
            'trend': '上升'|'下降'|'震荡',
            'ma_status': {ma5/ma10/ma20/ma60: {'pos': '上'|'下', 'dir': '↑'|'↓'|'→', 'align': '多头'|'空头'|'交叉'}},
            'volume_status': {'vratio': float, 'state': '放量'|'缩量'|'正常'|'倍量'|'地量'},
            'kline_pattern': '红三兵'|'启明星'|'黄昏星'|'射击之星'|'锤子线'|'吞噬'|'十字星'|'普通',
            'background_color': '#88EE88'(吸筹) | '#FFCC88'(洗盘) | '#88AAFF'(拉升) | '#FF8888'(出货) | '#CCCCCC'(下跌) | '#EEEEEE'(震荡),
            'key_signals': [...],
            'detail': {...}
        }
    """
    if df is None or len(df) < 60:
        return None

    df = df.copy()
    df = df.sort_values("日期" if "日期" in df.columns else df.columns[0]).reset_index(drop=True)

    close = df["收盘"] if "收盘" in df.columns else df.iloc[:, 4]
    open_ = df["开盘"] if "开盘" in df.columns else df.iloc[:, 1]
    high = df["最高"] if "最高" in df.columns else df.iloc[:, 2]
    low = df["最低"] if "最低" in df.columns else df.iloc[:, 3]
    vol = df["成交量"] if "成交量" in df.columns else df.iloc[:, 5]

    n = min(len(df), top_n + 60)
    close = close.tail(n).reset_index(drop=True)
    open_ = open_.tail(n).reset_index(drop=True)
    high = high.tail(n).reset_index(drop=True)
    low = low.tail(n).reset_index(drop=True)
    vol = vol.tail(n).reset_index(drop=True)

    # ── 1. 均线系统 ──
    ma5 = _calc_ma(close, 5)
    ma10 = _calc_ma(close, 10)
    ma20 = _calc_ma(close, 20)
    ma60 = _calc_ma(close, 60)

    last = close.iloc[-1]
    ma5_l, ma10_l, ma20_l, ma60_l = ma5.iloc[-1], ma10.iloc[-1], ma20.iloc[-1], ma60.iloc[-1]
    ma5_d = ma5.diff().iloc[-1]
    ma10_d = ma10.diff().iloc[-1]
    ma20_d = ma20.diff().iloc[-1]
    ma60_d = ma60.diff().iloc[-1]

    # 均线位置 (vs 最新价)
    def _pos(ma_val): return "上" if last > ma_val else "下"
    def _dir(diff):
        if diff > 0.01: return "↑"
        elif diff < -0.01: return "↓"
        return "→"

    # 均线排列
    if ma5_l > ma10_l > ma20_l > ma60_l:
        ma_align = "多头排列"
    elif ma5_l < ma10_l < ma20_l < ma60_l:
        ma_align = "空头排列"
    else:
        ma_align = "缠绕"

    ma_status = {
        "MA5": {"pos": _pos(ma5_l), "dir": _dir(ma5_d), "val": round(ma5_l, 2)},
        "MA10": {"pos": _pos(ma10_l), "dir": _dir(ma10_d), "val": round(ma10_l, 2)},
        "MA20": {"pos": _pos(ma20_l), "dir": _dir(ma20_d), "val": round(ma20_l, 2)},
        "MA60": {"pos": _pos(ma60_l), "dir": _dir(ma60_d), "val": round(ma60_l, 2)},
        "排列": ma_align,
    }

    # ── 2. 量能系统 ──
    vol_l = vol.iloc[-1]
    vol_ma5 = _calc_ma(vol, 5).iloc[-1]
    vol_ma20 = _calc_ma(vol, 20).iloc[-1]
    vol_ma60 = _calc_ma(vol, 60).iloc[-1]
    vratio = vol_l / vol_ma20 if vol_ma20 > 0 else 1.0

    if vratio >= 2.5:
        vol_state = "倍量"
    elif vratio >= 1.5:
        vol_state = "放量"
    elif vratio <= 0.3:
        vol_state = "地量"
    elif vratio <= 0.6:
        vol_state = "缩量"
    else:
        vol_state = "正常"

    # 量能趋势: 近5日均量 vs 前20日均量
    vol_trend = vol_ma5 / vol_ma20 if vol_ma20 > 0 else 1.0

    # ── 3. 趋势方向 (近 20 根K线) ──
    c20 = close.tail(20)
    c60 = close.tail(60)
    ret20 = (c20.iloc[-1] / c20.iloc[0] - 1) * 100 if c20.iloc[0] > 0 else 0
    ret60 = (c60.iloc[-1] / c60.iloc[0] - 1) * 100 if c60.iloc[0] > 0 else 0

    # 用线性回归斜率标准化
    x = np.arange(len(c20))
    slope20 = np.polyfit(x, c20.values, 1)[0]
    slope_pct = slope20 / c20.iloc[0] * 100  # 每日百分比斜率

    if ret20 > 10 and ma20_d > 0:
        trend = "上升"
    elif ret20 < -10 and ma20_d < 0:
        trend = "下降"
    else:
        trend = "震荡"

    # ── 4. MACD / RSI ──
    dif, dea, macd_hist = _calc_macd(close)
    rsi = _calc_rsi(close)
    dif_l = dif.iloc[-1]
    dea_l = dea.iloc[-1]
    macd_l = macd_hist.iloc[-1]
    rsi_l = rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50

    # MACD 金叉/死叉 (最近 5 根)
    dif_recent = dif.tail(5).values
    dea_recent = dea.tail(5).values
    macd_cross_up = any(dif_recent[i] > dea_recent[i] and dif_recent[i-1] <= dea_recent[i-1]
                        for i in range(1, 5))
    macd_cross_down = any(dif_recent[i] < dea_recent[i] and dif_recent[i-1] >= dea_recent[i-1]
                           for i in range(1, 5))

    # ── 5. K线形态 (最近 3 根) ──
    def _body(o, c): return abs(c - o)
    def _upper_shadow(o, c, h): return h - max(o, c)
    def _lower_shadow(o, c, l): return min(o, c) - l

    o3, c3, h3, l3 = open_.iloc[-3:].values, close.iloc[-3:].values, high.iloc[-3:].values, low.iloc[-3:].values

    # 单日形态
    last_o, last_c, last_h, last_l = o3[-1], c3[-1], h3[-1], l3[-1]
    body_l = _body(last_o, last_c)
    up_sh = _upper_shadow(last_o, last_c, last_h)
    lo_sh = _lower_shadow(last_o, last_c, last_l)
    body_avg = np.mean([_body(o3[i], c3[i]) for i in range(3)]) or 0.01

    if up_sh > body_l * 2 and lo_sh < body_l * 0.5:
        kline_pattern = "射击之星"
    elif lo_sh > body_l * 2 and up_sh < body_l * 0.5:
        kline_pattern = "锤子线"
    elif body_l < body_avg * 0.3:
        kline_pattern = "十字星"
    elif all(c3[i] > o3[i] and c3[i] > c3[i-1] for i in range(1, 3)) and c3[0] > o3[0]:
        kline_pattern = "红三兵"
    elif all(c3[i] < o3[i] and c3[i] < c3[i-1] for i in range(1, 3)) and c3[0] < o3[0]:
        kline_pattern = "黑三鸦"
    elif c3[-2] < o3[-2] and c3[-1] > o3[-1] and c3[-1] > (o3[-2]+c3[-2])/2 and o3[-1] < c3[-2]:
        kline_pattern = "启明星"
    elif c3[-2] > o3[-2] and c3[-1] < o3[-1] and c3[-1] < (o3[-2]+c3[-2])/2 and o3[-1] > c3[-2]:
        kline_pattern = "黄昏星"
    elif c3[-1] > o3[-1] and c3[-2] < o3[-2] and o3[-1] < min(o3[-2], c3[-2]) and c3[-1] > max(o3[-2], c3[-2]):
        kline_pattern = "看涨吞噬"
    elif c3[-1] < o3[-1] and c3[-2] > o3[-2] and o3[-1] > max(o3[-2], c3[-2]) and c3[-1] < min(o3[-2], c3[-2]):
        kline_pattern = "看跌吞噬"
    else:
        kline_pattern = "普通"

    # ── 6. 筹码峰 / 波动区间 ──
    h60 = high.tail(60).max()
    l60 = low.tail(60).min()
    pos_range = (last - l60) / (h60 - l60) * 100 if h60 != l60 else 50  # 当前价在 60 日区间位置

    # ── 7. 机构 vs 游资识别 ──
    inst_score = 0
    hm_score = 0

    # 7a. 均线操盘偏好
    if ma_align == "多头排列" and last > ma20_l and ma20_l > ma60_l:
        # 沿 MA20 稳步上升 = 机构特征
        inst_score += 25
    # 价格到 MA20 的距离 (越近 = 机构控盘好)
    dist_ma20 = abs(last - ma20_l) / ma20_l * 100
    if dist_ma20 < 3:
        inst_score += 15
    elif dist_ma20 < 5:
        inst_score += 10

    # 均线斜率平滑度 (机构稳步, 游资急)
    ma20_slope_std = ma20.tail(20).diff().std()
    ma5_slope_std = ma5.tail(20).diff().std()
    if ma20_slope_std > 0 and ma5_slope_std > 0:
        slope_ratio = ma5_slope_std / ma20_slope_std  # 游资应该 MA5 抖得厉害
        if slope_ratio > 3:
            hm_score += 20  # MA5 比 MA20 抖 3x = 游资
        elif slope_ratio < 1.5:
            inst_score += 15  # MA5 跟 MA20 差不多 = 机构稳健

    # 7b. 涨跌幅特征 (近 20 日)
    rets = close.tail(21).pct_change().dropna() * 100
    limit_up_days = (rets >= 9.5).sum()
    big_down_days = (rets <= -9.5).sum()
    total_volatile_days = ((rets.abs() >= 5)).sum()
    if limit_up_days >= 2:
        hm_score += 20
    if total_volatile_days >= 8:
        hm_score += 15
    # 机构偏好温和上涨 (近 20 日涨幅 5-15%, 小实体日多)
    small_body_days = ((rets.abs() >= 0) & (rets.abs() <= 2)).sum()
    if ret20 > 3 and ret20 < 20 and small_body_days >= 10:
        inst_score += 20

    # 7c. 基金重仓数据 (如果有)
    fund_institution = 50  # 默认中性
    if fund_df is not None and len(fund_df) > 0:
        col_candidates = ["基金名称", "持仓数量", "持股市值", "占流通股比例"]
        fund_count = len(fund_df)
        inst_score += min(30, fund_count // 50)  # 每 50 家基金 +15 分, 封顶 30
        fund_institution = 50 + min(50, fund_count // 30)

    # 综合判定
    inst_score = min(100, max(0, inst_score))
    hm_score = min(100, max(0, hm_score))
    if inst_score > hm_score + 10 and fund_institution >= 60:
        inst_hm = "机构票"
    elif hm_score > inst_score + 15:
        inst_hm = "游资票"
    else:
        inst_hm = "混合型"

    # ── 8. 🎯 操盘阶段判定 (核心) ──
    stage_scores = {
        "吸筹": 0, "洗盘": 0, "拉升": 0, "出货": 0, "下跌": 0, "底部横盘": 0,
    }

    # 吸筹特征
    if pos_range < 30:  # 股价在 60 日区间低位
        stage_scores["吸筹"] += 20
        stage_scores["底部横盘"] += 15
    if ret60 < 0 and pos_range < 40:  # 中期下跌后位置低
        stage_scores["吸筹"] += 15
    if vol_state in ("缩量", "地量") and pos_range < 40:
        stage_scores["吸筹"] += 15  # 低位缩量 = 吸筹特征
    if macd_cross_up and dif_l < 0:  # 低位金叉
        stage_scores["吸筹"] += 10
        stage_scores["底部横盘"] += 10
    if ma5_l > ma20_l and ma5_d > 0 and ma20_d <= 0:  # MA5 上穿 MA20 但 MA20 还没拐头
        stage_scores["吸筹"] += 10

    # 洗盘特征
    if trend == "下降" and ret20 > -15:  # 小回调
        stage_scores["洗盘"] += 20
    if vol_state in ("缩量", "地量") and pos_range > 50:  # 高位缩量回调
        stage_scores["洗盘"] += 15
    if ma5_l < ma20_l and ma5_d > 0 and vol_trend < 1:  # MA5 上穿缩量
        stage_scores["洗盘"] += 15
    if kline_pattern in ("锤子线", "启明星", "看涨吞噬") and pos_range > 40:
        stage_scores["洗盘"] += 10
    if rsi_l < 40 and rsi_l > 25 and pos_range > 50:
        stage_scores["洗盘"] += 10

    # 拉升特征
    if trend == "上升" and ma_align == "多头排列":
        stage_scores["拉升"] += 30
    if ret20 > 10 and ma20_d > 0:
        stage_scores["拉升"] += 20
    if vol_state in ("放量", "倍量") and ret20 > 5:
        stage_scores["拉升"] += 15
    if kline_pattern in ("红三兵", "看涨吞噬"):
        stage_scores["拉升"] += 10
    if pos_range > 70 and ret20 > 5:
        stage_scores["拉升"] += 10

    # 出货特征
    if pos_range > 80 and vol_state in ("放量", "倍量") and ret20 < 5:  # 高位放量滞涨
        stage_scores["出货"] += 25
    if pos_range > 70 and ma5_l < ma10_l < ma20_l and ma20_d > 0:  # 高位均线拐头
        stage_scores["出货"] += 20
    if kline_pattern in ("射击之星", "黄昏星", "看跌吞噬") and pos_range > 70:
        stage_scores["出货"] += 15
    if macd_cross_down and dif_l > 0:  # 高位死叉
        stage_scores["出货"] += 15
    if rsi_l > 75:
        stage_scores["出货"] += 10
    if ret20 > 20 and vol_state == "地量":  # 高位地量 = 无人接盘
        stage_scores["出货"] += 10

    # 下跌特征
    if trend == "下降" and ma_align == "空头排列":
        stage_scores["下跌"] += 30
    if ret60 < -15 and ma20_d < 0:
        stage_scores["下跌"] += 20
    if pos_range < 30 and ma60_d < 0:
        stage_scores["下跌"] += 15

    # 底部横盘
    if trend == "震荡" and pos_range < 40:
        stage_scores["底部横盘"] += 25
    if ma_align == "缠绕" and pos_range < 40:
        stage_scores["底部横盘"] += 20
    if vol_state == "地量" and pos_range < 40:
        stage_scores["底部横盘"] += 15

    # 找最高分
    stage = max(stage_scores, key=stage_scores.get)
    stage_score = min(100, stage_scores[stage])

    # ── 9. 关键信号汇总 ──
    signals = []
    if stage_scores["吸筹"] >= 20: signals.append(f"💡低位+缩量+MA金叉 → 吸筹中")
    if stage_scores["洗盘"] >= 20: signals.append(f"💡回调缩量+MA5拐头 → 洗盘结束在即")
    if stage_scores["拉升"] >= 25: signals.append(f"💡多头排列+放量 → 主升浪进行中")
    if stage_scores["出货"] >= 20: signals.append(f"⚠️ 高位放量滞涨 → 警惕出货")
    if stage_scores["下跌"] >= 20: signals.append(f"⚠️ 空头排列 → 观望为主")
    if macd_cross_up: signals.append(f"🟢 MACD 金叉")
    if macd_cross_down: signals.append(f"🔴 MACD 死叉")
    if limit_up_days >= 2: signals.append(f"🔥 近20日 {limit_up_days} 次涨停 → 游资票")
    if inst_score >= 65: signals.append(f"🏛️ 机构控盘 ({inst_score}分)")
    if hm_score >= 55: signals.append(f"🎭 游资活跃 ({hm_score}分)")
    if pos_range > 70: signals.append(f"📈 股价在60日高位区 ({pos_range:.0f}%)")
    if pos_range < 30: signals.append(f"📉 股价在60日低位区 ({pos_range:.0f}%)")

    # ── 10. 背景颜色 ──
    stage_colors = {
        "吸筹": ("#FFF9E6", "#D4A017"),      # 金黄色底 + 深金标签
        "洗盘": ("#E6F3FF", "#3B82F6"),      # 蓝色底 + 蓝标签
        "拉升": ("#E6FFE6", "#22C55E"),      # 绿色底 + 绿标签
        "出货": ("#FFE6E6", "#EF4444"),      # 红色底 + 红标签
        "下跌": ("#F5F5F5", "#6B7280"),      # 灰色底 + 灰标签
        "底部横盘": ("#FAF5FF", "#8B5CF6"),  # 紫色底 + 紫标签
    }
    bg_color, tag_color = stage_colors.get(stage, ("#FFFFFF", "#333333"))

    return {
        "stage": stage,
        "stage_score": stage_score,
        "institution_vs_hot_money": inst_hm,
        "institution_score": inst_score,
        "hot_money_score": hm_score,
        "fund_count": len(fund_df) if fund_df is not None else 0,
        "trend": trend,
        "ma_status": ma_status,
        "volume_status": {"vratio": round(vratio, 2), "state": vol_state, "trend": round(vol_trend, 2)},
        "kline_pattern": kline_pattern,
        "background_color": bg_color,
        "tag_color": tag_color,
        "signals": signals,
        "pos_range_pct": round(pos_range, 1),
        "ret20_pct": round(ret20, 1),
        "ret60_pct": round(ret60, 1),
        "rsi": round(rsi_l, 1),
        "macd_dif": round(dif_l, 3),
        "limit_up_days": int(limit_up_days),
        "detail": {
            "close": round(last, 2),
            "ma5": round(ma5_l, 2), "ma10": round(ma10_l, 2),
            "ma20": round(ma20_l, 2), "ma60": round(ma60_l, 2),
            "vol_ratio": round(vratio, 2),
            "high60": round(h60, 2), "low60": round(l60, 2),
        }
    }


# ─────────────────────────────────────────────────────────────
# 🖥️ UI Mixin — 卡片网格 + 扫描 + 双击开K线
# ─────────────────────────────────────────────────────────────

class TechStageMixin:
    """📊 操盘阶段识别 Mixin — 挂到主程序上"""

    def _show_tech_stage_dialog(self):
        """弹窗入口: 股票阶段扫描"""
        dlg = tk.Toplevel(getattr(self, "root", None))
        dlg.title("📊 操盘阶段识别 — 吸筹/洗盘/拉升/出货")
        dlg.geometry("1280x780")
        dlg.transient(getattr(self, "root", None))

        # 顶栏
        top = tk.Frame(dlg, bg="#F8FAFC", height=50)
        top.pack(fill=tk.X)
        tk.Label(top, text="📊 操盘阶段识别", font=("", 14, "bold"),
                 bg="#F8FAFC").pack(side=tk.LEFT, padx=12, pady=8)

        self._ts_status = tk.StringVar(value="⏳ 准备中...")
        tk.Label(top, textvariable=self._ts_status,
                 foreground="blue", bg="#F8FAFC").pack(side=tk.LEFT, padx=12)

        # 控制面板
        ctrl = tk.LabelFrame(dlg, text="🎛️ 扫描控制", padding=6)
        ctrl.pack(fill=tk.X, padx=8, pady=4)

        ttk.Button(ctrl, text="🔍 自选股扫描",
                   command=lambda: self._ts_scan_from_watchlist(dlg)).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctrl, text="📋 输入代码扫描",
                   command=lambda: self._ts_input_codes(dlg)).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctrl, text="💾 导出CSV",
                   command=lambda: self._ts_export_csv(dlg)).pack(side=tk.LEFT, padx=4)

        # 阶段过滤
        tk.Label(ctrl, text="  阶段过滤:", bg="#F1F5F9").pack(side=tk.LEFT, padx=(20, 4))
        self._ts_filter = tk.StringVar(value="全部")
        stage_opts = ["全部", "吸筹", "洗盘", "拉升", "出货", "下跌", "底部横盘"]
        ttk.Combobox(ctrl, textvariable=self._ts_filter, values=stage_opts,
                     width=10, state="readonly",
                     command=lambda e: self._ts_apply_filter()
                     ).pack(side=tk.LEFT, padx=4)

        # 类型过滤
        self._ts_filter_type = tk.StringVar(value="全部")
        tk.Label(ctrl, text="  票型:", bg="#F1F5F9").pack(side=tk.LEFT, padx=(10, 4))
        type_opts = ["全部", "机构票", "游资票", "混合型"]
        ttk.Combobox(ctrl, textvariable=self._ts_filter_type, values=type_opts,
                     width=10, state="readonly",
                     command=lambda e: self._ts_apply_filter()
                     ).pack(side=tk.LEFT, padx=4)

        # 进度条
        self._ts_progress = ttk.Progressbar(ctrl, length=200)
        self._ts_progress.pack(side=tk.RIGHT, padx=8)

        # 卡片容器 (Canvas + Scrollbar 实现滚动)
        container = tk.Frame(dlg)
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self._ts_canvas = tk.Canvas(container, highlightthickness=0, bg="#F8FAFC")
        sb = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self._ts_canvas.yview)
        self._ts_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._ts_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._ts_card_frame = tk.Frame(self._ts_canvas, bg="#F8FAFC")
        self._ts_canvas.create_window((0, 0), window=self._ts_card_frame, anchor="nw")
        self._ts_card_frame.bind("<Configure>",
                                 lambda e: self._ts_canvas.configure(scrollregion=self._ts_canvas.bbox("all")))

        # 底部统计
        self._ts_stats = tk.StringVar(value="统计: 等待扫描...")
        tk.Label(dlg, textvariable=self._ts_stats, anchor="w",
                 bg="#F1F5F9").pack(fill=tk.X, side=tk.BOTTOM)

        self._ts_dlg = dlg
        self._ts_cards = []  # [(widget, data_dict)]
        self._ts_all_results = []

    def _ts_scan_from_watchlist(self, dlg):
        """从自选股/监测池扫描"""
        codes = []
        names = []
        # 尝试多个来源
        for attr in ["monitor_stocks", "_monitor_stocks", "self_monitor_stocks", "watchlist_stocks", "_watchlist"]:
            val = getattr(self, attr, None)
            if val:
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, (tuple, list)) and len(item) >= 2:
                            n, c = item[0], item[1]
                            codes.append(str(c).strip())
                            names.append(str(n).strip())
                break

        if not codes:
            # 最后兜底: 从 db 的 monitor_list
            try:
                import sqlite3
                db = getattr(self, "_db_conn", None)
                if db:
                    cur = db.execute("SELECT code, name FROM monitor_list LIMIT 100")
                    for row in cur.fetchall():
                        codes.append(row[0])
                        names.append(row[1])
            except Exception:
                pass

        if not codes:
            # 再兜底: 提示用户手动输入
            self._ts_input_codes(dlg)
            return

        self._ts_run_scan(list(zip(names, codes)))

    def _ts_input_codes(self, dlg):
        """弹窗让用户输入代码"""
        sub = tk.Toplevel(dlg)
        sub.title("📋 输入股票代码 (多个用逗号/换行分隔)")
        sub.geometry("400x300")
        tk.Label(sub, text="例如: 300456, 600519\n或直接粘贴: 赛微电子 300456",
                 foreground="gray").pack(pady=4)
        txt = tk.Text(sub, height=12)
        txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        def _go():
            content = txt.get("1.0", tk.END).strip()
            pairs = []
            for line in content.replace("，", ",").split("\n"):
                for part in line.split(","):
                    part = part.strip()
                    if not part: continue
                    m = re.search(r"(\d{6})", part)
                    if m:
                        code = m.group(1)
                        name = part.replace(code, "").strip() or code
                        pairs.append((name, code))
            sub.destroy()
            if pairs:
                self._ts_run_scan(pairs)
            else:
                self._ts_status.set("❌ 没找到有效的 6 位代码")

        ttk.Button(sub, text="🔍 开始扫描", command=_go).pack(pady=6)

    def _ts_run_scan(self, pairs):
        """后台扫描线程 —— 逐只跑 AKShare + 分析"""
        import akshare as ak

        # 清空旧卡片
        for w in self._ts_card_frame.winfo_children():
            w.destroy()
        self._ts_cards = []
        self._ts_all_results = []

        self._ts_status.set(f"⏳ 开始扫描 {len(pairs)} 只...")
        self._ts_progress["maximum"] = len(pairs)
        self._ts_progress["value"] = 0

        def _run():
            results = []
            for i, (name, code) in enumerate(pairs):
                try:
                    code6 = re.search(r"(\d{6})", str(code)).group(1)
                    # 1. 拉 K 线 (AKShare)
                    df = None
                    for market_key in ["sh", "sz", "bj"]:
                        try:
                            df = ak.stock_zh_a_hist(symbol=code6, period="daily",
                                                    start_date=(datetime.now() - timedelta(days=400)).strftime("%Y%m%d"),
                                                    end_date=datetime.now().strftime("%Y%m%d"),
                                                    adjust="qfq")
                            if df is not None and len(df) >= 60:
                                break
                        except Exception:
                            continue

                    if df is None or len(df) < 60:
                        # 用实时数据补
                        try:
                            spot = ak.stock_zh_a_spot_em()
                            row = spot[spot["代码"] == code6]
                            if len(row) > 0:
                                price = float(row.iloc[0]["最新价"])
                                results.append({
                                    "name": name or row.iloc[0]["名称"],
                                    "code": code6,
                                    "price": price,
                                    "analyze": None,
                                    "error": "K线不足",
                                })
                        except Exception:
                            pass
                        continue

                    # 2. 拉基金持仓 (可选, 失败不阻塞)
                    fund_df = None
                    try:
                        fund_df = ak.stock_fund_stock_holder(symbol=code6)
                    except Exception:
                        pass

                    # 3. 分析
                    analysis = analyze_trading_stage(df, fund_df)
                    results.append({
                        "name": name, "code": code6,
                        "price": float(df.iloc[-1]["收盘"]),
                        "analyze": analysis, "error": None,
                    })

                except Exception as e:
                    results.append({
                        "name": name, "code": code,
                        "price": 0, "analyze": None, "error": str(e)[:60],
                    })

                if self._ts_dlg and self._ts_dlg.winfo_exists():
                    self._ts_dlg.after(0, lambda i=i, n=name: (
                        self._ts_progress.configure(value=i + 1),
                        self._ts_status.set(f"⏳ {i+1}/{len(pairs)} — {n}")
                    ))
                time.sleep(0.3)  # 节流 AKShare 频率

            # 完成
            if self._ts_dlg and self._ts_dlg.winfo_exists():
                self._ts_dlg.after(0, lambda: self._ts_finish_scan(results))

        threading.Thread(target=_run, daemon=True).start()

    def _ts_finish_scan(self, results):
        """渲染卡片网格"""
        self._ts_all_results = results
        self._ts_status.set(f"✅ 扫描完成 — 正在渲染 {len(results)} 张卡片...")
        self._ts_apply_filter()

    def _ts_apply_filter(self):
        """按阶段/票型过滤 + 渲染卡片网格"""
        for w in self._ts_card_frame.winfo_children():
            w.destroy()
        self._ts_cards = []

        stage_f = self._ts_filter.get()
        type_f = self._ts_filter_type.get()

        filtered = []
        for r in self._ts_all_results:
            a = r.get("analyze")
            if a is None:
                continue
            if stage_f != "全部" and a.get("stage") != stage_f:
                continue
            if type_f != "全部" and a.get("institution_vs_hot_money") != type_f:
                continue
            filtered.append(r)

        # 统计
        stage_cnt = Counter()
        type_cnt = Counter()
        for r in self._ts_all_results:
            a = r.get("analyze")
            if a:
                stage_cnt[a.get("stage", "?")] += 1
                type_cnt[a.get("institution_vs_hot_money", "?")] += 1

        total_good = sum(stage_cnt.values())
        stat_str = f"📊 总有效: {total_good} | " + " ".join(f"【{k}:{v}】" for k, v in stage_cnt.most_common())
        self._ts_stats.set(stat_str)

        # 卡片网格布局 (自动列数)
        cols = max(3, min(5, (self._ts_canvas.winfo_width() or 1000) // 240))
        cell_w, cell_h = 220, 175

        for idx, r in enumerate(filtered):
            a = r["analyze"]
            stage = a["stage"]
            bg = a["background_color"]
            tag_color = a["tag_color"]
            name, code = r["name"], r["code"]

            row, col = divmod(idx, cols)
            card = tk.Frame(self._ts_card_frame, bg=bg, width=cell_w, height=cell_h,
                            highlightbackground=tag_color, highlightthickness=2,
                            cursor="hand2")
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            card.pack_propagate(False)

            # 阶段标签 (右上角)
            tag = tk.Label(card, text=f"⏱ {stage}", bg=tag_color, fg="white",
                           font=("", 9, "bold"), padx=6, pady=1)
            tag.place(relx=0.98, rely=0, anchor="ne", y=4, x=-4)

            # 股票名 + 代码
            tk.Label(card, text=f"{name}", bg=bg, font=("", 12, "bold"),
                     anchor="w").pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(card, text=f"{code}", bg=bg, font=("", 9), fg="#666",
                     anchor="w").pack(anchor="w", padx=8)

            # 机构/游资标签
            inst = a.get("institution_vs_hot_money", "")
            inst_color = "#1E40AF" if "机构" in inst else "#DC2626" if "游资" in inst else "#6B7280"
            tk.Label(card, text=f"🏛 {inst}({a.get('institution_score',0)})",
                     bg=bg, fg=inst_color, font=("", 9, "bold"),
                     anchor="w").pack(anchor="w", padx=8, pady=(2, 0))

            # 价格 + 涨跌
            d = a.get("detail", {})
            tk.Label(card, text=f"¥{d.get('close','?')}  MA5={d.get('ma5','?')}  MA20={d.get('ma20','?')}",
                     bg=bg, font=("", 9), fg="#333",
                     anchor="w").pack(anchor="w", padx=8)

            # 均线排列
            ma_align = a.get("ma_status", {}).get("排列", "?")
            trend = a.get("trend", "?")
            vs = a.get("volume_status", {})
            vstate = vs.get("state", "?")
            tk.Label(card, text=f"📈{trend} | {ma_align} | 量:{vstate}({vs.get('vratio','?')}x)",
                     bg=bg, font=("", 8), fg="#555",
                     anchor="w").pack(anchor="w", padx=8)

            # K线形态 + MACD
            kp = a.get("kline_pattern", "?")
            rsi = a.get("rsi", "?")
            tk.Label(card, text=f"🕯 {kp} | RSI={rsi} | 60日位置={a.get('pos_range_pct','?')}%",
                     bg=bg, font=("", 8), fg="#555",
                     anchor="w").pack(anchor="w", padx=8)

            # 阶段分数
            tk.Label(card, text=f"🎯 {stage} 置信度: {a.get('stage_score','?')}/100",
                     bg=bg, font=("", 9, "bold"), fg=tag_color,
                     anchor="w").pack(anchor="w", padx=8, pady=(2, 0))

            # 点击事件 —— 双击卡片打开 K 线图
            def _on_dblclick(e, _r=r):
                self._ts_open_kline(_r)
            def _on_click(e, _r=r):
                self._ts_show_card_detail(_r)

            for w in [card, tag] + card.winfo_children():
                w.bind("<Double-Button-1>", _on_dblclick)
                w.bind("<Button-1>", _on_click)

            self._ts_cards.append((card, r))

        # 重算 canvas 宽度
        self._ts_card_frame.update_idletasks()
        if self._ts_dlg and self._ts_dlg.winfo_exists():
            self._ts_status.set(f"✅ 渲染完成: 显示 {len(filtered)}/{len(self._ts_all_results)} 张卡片")

    def _ts_show_card_detail(self, r):
        """单击卡片 → 显示详情面板"""
        a = r.get("analyze")
        if not a: return

        dlg = tk.Toplevel(self._ts_dlg)
        dlg.title(f"📋 {r['name']}({r['code']}) — {a['stage']} 详情")
        dlg.geometry("520x580")

        bg = a["background_color"]
        tk.Label(dlg, text=f"⏱ {a['stage']}  |  🏛 {a['institution_vs_hot_money']}  |  🎯 置信度 {a['stage_score']}",
                 bg=a["tag_color"], fg="white", font=("", 12, "bold"),
                 pady=8).pack(fill=tk.X)

        info = tk.Frame(dlg)
        info.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        # 均线详情
        tk.Label(info, text="📈 均线位置与方向", font=("", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(4, 2))
        for i, ma in enumerate(["MA5", "MA10", "MA20", "MA60"]):
            ms = a["ma_status"].get(ma, {})
            tk.Label(info, text=f"  {ma}: 价{'上' if ms.get('pos')=='上' else '下'}均线 {ms.get('dir','')} → {ms.get('val','')}",
                     font=("", 10)).grid(row=1 + i, column=0, columnspan=2, sticky="w")

        tk.Label(info, text=f"\n📊 均线排列: {a['ma_status'].get('排列','?')}", font=("", 10, "bold")).grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 2))
        tk.Label(info, text=f"📈 趋势方向: {a['trend']}", font=("", 10)).grid(row=7, column=0, sticky="w")
        tk.Label(info, text=f"💰 量能状态: {a['volume_status'].get('state','?')} ({a['volume_status'].get('vratio','')}x)", font=("", 10)).grid(row=7, column=1, sticky="w")
        tk.Label(info, text=f"🕯 K线形态: {a['kline_pattern']}", font=("", 10)).grid(row=8, column=0, sticky="w")
        tk.Label(info, text=f"📉 RSI: {a['rsi']}", font=("", 10)).grid(row=8, column=1, sticky="w")

        tk.Label(info, text=f"\n💰 价格位置 (60日): {a['pos_range_pct']}%  (60日高={a['detail'].get('high60','?')} 低={a['detail'].get('low60','?')})",
                 font=("", 10)).grid(row=9, column=0, columnspan=2, sticky="w")
        tk.Label(info, text=f"📅 近20日涨跌: {a['ret20_pct']}%  |  近60日: {a['ret60_pct']}%",
                 font=("", 10)).grid(row=10, column=0, columnspan=2, sticky="w")

        tk.Label(info, text=f"\n🏛 机构/游资识别", font=("", 10, "bold")).grid(row=11, column=0, columnspan=2, sticky="w", pady=(6, 2))
        tk.Label(info, text=f"  机构分: {a.get('institution_score','?')}  游资分: {a.get('hot_money_score','?')}  基金数: {a.get('fund_count',0)}",
                 font=("", 10)).grid(row=12, column=0, columnspan=2, sticky="w")

        # 关键信号
        tk.Label(info, text=f"\n💡 关键信号 ({len(a.get('signals',[]))})", font=("", 10, "bold")).grid(row=13, column=0, columnspan=2, sticky="w", pady=(6, 2))
        for j, sig in enumerate(a.get("signals", [])):
            tk.Label(info, text=f"  {sig}", font=("", 9), fg="#374151").grid(row=14 + j, column=0, columnspan=2, sticky="w")

        # 双击开 K 线按钮
        btn_row = tk.Frame(dlg)
        btn_row.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(btn_row, text="📊 双击也可打开 K 线图",
                   command=lambda: (dlg.destroy(), self._ts_open_kline(r))).pack(side=tk.LEFT)

    def _ts_open_kline(self, r):
        """双击卡片 → 调用主程序 K 线图 (如果存在)"""
        code = r["code"]
        name = r["name"]
        # 方式一: 直接打开主程序的 K 线 tab
        for attr in ["_open_kline_dialog", "_show_kline_dialog", "_open_chart", "_show_technical_dialog", "_open_1min_k_dialog"]:
            fn = getattr(self, attr, None)
            if fn:
                try:
                    fn(code)
                    return
                except Exception:
                    continue
        # 方式二: 弹窗提示
        tk.messagebox.showinfo("📊 K线图", f"双击了 {name}({code})\n\n你的主程序没有找到 K 线图组件。\n可以集成 stock_chart.py 或调用 AKShare 画图。")

    def _ts_export_csv(self, dlg):
        """导出扫描结果到 CSV"""
        if not self._ts_all_results:
            self._ts_status.set("⚠️ 没有扫描结果可导出")
            return
        try:
            rows = []
            for r in self._ts_all_results:
                a = r.get("analyze")
                if not a: continue
                row = {"名称": r["name"], "代码": r["code"], "价格": r.get("price", 0)}
                row.update({
                    "阶段": a["stage"], "阶段置信度": a["stage_score"],
                    "票型": a["institution_vs_hot_money"],
                    "机构分": a.get("institution_score", 0),
                    "游资分": a.get("hot_money_score", 0),
                    "基金数": a.get("fund_count", 0),
                    "趋势": a["trend"],
                    "均线排列": a["ma_status"].get("排列", ""),
                    "量能": a["volume_status"].get("state", ""),
                    "量比": a["volume_status"].get("vratio", 0),
                    "K线形态": a["kline_pattern"],
                    "RSI": a["rsi"],
                    "60日位置%": a["pos_range_pct"],
                    "近20日%": a["ret20_pct"],
                    "近60日%": a["ret60_pct"],
                })
                rows.append(row)
            df_exp = pd.DataFrame(rows)
            path = os.path.expanduser(f"~/Desktop/操盘阶段扫描_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
            df_exp.to_csv(path, index=False, encoding="utf-8-sig")
            self._ts_status.set(f"✅ 已导出到 {path}")
        except Exception as e:
            self._ts_status.set(f"❌ 导出失败: {e}")
