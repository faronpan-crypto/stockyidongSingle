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

    # 用近 N 天线性回归斜率判定均线方向 (比单天 diff 稳定得多)
    def _ma_slope(ma_series, n_days):
        """计算均线近 n_days 天的日均斜率"""
        recent = ma_series.dropna().tail(n_days)
        if len(recent) < 3:
            return 0.0
        x = np.arange(len(recent))
        slope = np.polyfit(x, recent.values, 1)[0]  # 每天变化值
        # 归一化为百分比斜率, 消除价格量级影响
        base = recent.iloc[0] if recent.iloc[0] != 0 else 1
        return slope / base * 100  # 每天变化百分比

    ma5_d = _ma_slope(ma5, 5)     # MA5 看近 5 天
    ma10_d = _ma_slope(ma10, 5)   # MA10 看近 5 天
    ma20_d = _ma_slope(ma20, 10)  # MA20 看近 10 天
    ma60_d = _ma_slope(ma60, 10)  # MA60 看近 10 天

    # 均线位置 (vs 最新价)
    def _pos(ma_val): return "上" if last > ma_val else "下"
    def _dir(slope_pct):
        """基于百分比斜率判定方向"""
        if slope_pct > 0.05: return "↑"    # 日均涨 > 0.05%
        elif slope_pct < -0.05: return "↓"  # 日均跌 > 0.05%
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

    # ── 当日/5日/10日 涨跌幅 ──
    def _ret(n):
        if len(close) > n and close.iloc[-n - 1] > 0:
            return (close.iloc[-1] / close.iloc[-n - 1] - 1) * 100
        return float("nan")
    ret1 = _ret(1)   # 当日 vs 昨收
    ret5 = _ret(5)   # 近5日
    ret10 = _ret(10)  # 近10日

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

    # 计算过程详情 (供 ❓帮助弹窗 + 面板 tooltip 使用)
    _ret20_detail = {
        "公式": f"(收盘价[-1] / 收盘价[-20] - 1) × 100",
        "20天前收盘": round(close.iloc[-20], 3) if len(close) >= 20 else None,
        "今日收盘": round(last, 3),
        "结果%": round(ret20, 2),
    }
    _ret60_detail = {
        "公式": f"(收盘价[-1] / 收盘价[-60] - 1) × 100",
        "60天前收盘": round(close.iloc[-60], 3) if len(close) >= 60 else None,
        "今日收盘": round(last, 3),
        "结果%": round(ret60, 2),
    }
    _pos_detail = {
        "公式": f"(当前价 - 60日最低) / (60日最高 - 60日最低) × 100",
        "60日最高": round(h60, 3),
        "60日最低": round(l60, 3),
        "当前价": round(last, 3),
        "区间振幅": round(h60 - l60, 3),
        "结果%": round(pos_range, 1),
    }

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
        "ret1_pct": round(ret1, 2) if not (ret1 != ret1) else None,
        "ret5_pct": round(ret5, 2) if not (ret5 != ret5) else None,
        "ret10_pct": round(ret10, 2) if not (ret10 != ret10) else None,
        "ret20_pct": round(ret20, 1),
        "ret60_pct": round(ret60, 1),
        "rsi": round(rsi_l, 1),
        "macd_dif": round(dif_l, 3),
        # 计算过程详情 (帮助弹窗用)
        "calc_detail": {
            "ret20": _ret20_detail,
            "ret60": _ret60_detail,
            "pos_range": _pos_detail,
            "ma60_slope_pct": round(ma60_d, 3),
            "ma20_slope_pct": round(ma20_d, 3),
            "volume_ratio": round(vratio, 2),
            "data_rows": len(close),
        },
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
    """📊 操盘阶段识别 Mixin — 挂到主程序上, 复用原"🧬生命周期"按钮"""

    # ── 🧬 原生命周期按钮入口 (覆盖原 MA20 简单判断, 升级为完整操盘阶段分析) ──

    def _show_lifecycle_popup(self):
        """🧬 生命周期扫描 — 升级为完整操盘阶段识别 (吸筹/洗盘/拉升/出货)"""
        print("\n" + "="*60)
        print("🧬 [操盘阶段 V2.0] 已加载! 吸筹→洗盘→拉升→出货 识别")
        print("="*60)
        pick = tk.Toplevel(getattr(self, "root", None))
        pick.title("🧬 生命周期·操盘阶段扫描 V2 — 选择候选池")
        pick.geometry("500x440")
        pick.configure(bg="#FCE4EC")
        pick.transient(getattr(self, "root", None))
        pick.grab_set()
        pick.resizable(False, False)

        tk.Label(pick, text="🧬 生命周期·操盘阶段扫描", bg="#FCE4EC",
                 font=("", 14, "bold"), fg="#AD1457").pack(pady=(18, 4))
        tk.Label(pick, text="吸筹 → 洗盘 → 拉升 → 出货  四阶段识别", bg="#FCE4EC",
                 font=("", 10), fg="#AD1457").pack()
        tk.Label(pick, text="(均线位置方向/量能/K线形态/机构票vs游资票)", bg="#FCE4EC",
                 font=("", 9), fg="#880E4F").pack(pady=(0, 12))

        _GROUP_MAP = [
            (2, "龙头股"), (4, "Main"), (6, "同花顺"),
            (7, "标签1"), (8, "标签2"), (9, "标签3"), (10, "标签4"),
            (11, "标签5"), (12, "标签6"), (13, "标签7"), (14, "标签8"),
        ]
        _selected = {gi: tk.BooleanVar(value=True) for gi, _ in _GROUP_MAP}

        _counts = {}
        for gi, _ in _GROUP_MAP:
            hs = getattr(self, f"holding_stocks_{gi}", [None] * 80)
            _counts[gi] = sum(1 for h in hs if h)

        box = tk.Frame(pick, bg="#FCE4EC")
        box.pack(padx=20, fill="x")
        for i, (gi, gname) in enumerate(_GROUP_MAP):
            cb = ttk.Checkbutton(box, text=f"{gname} ({_counts[gi]}只)", variable=_selected[gi])
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=8, pady=3)

        _total_all = sum(_counts.values())
        tk.Label(pick, text=f"📊 当前共 {_total_all} 只", bg="#FCE4EC", fg="#666", font=("", 9)).pack(pady=8)

        def _toggle_all(val):
            for v in _selected.values(): v.set(val)
        btn_row = tk.Frame(pick, bg="#FCE4EC")
        btn_row.pack()
        ttk.Button(btn_row, text="全选", command=lambda: _toggle_all(True)).pack(side="left", padx=4)
        ttk.Button(btn_row, text="全不选", command=lambda: _toggle_all(False)).pack(side="left", padx=4)

        def _do_scan():
            chosen = [gi for gi, _ in _GROUP_MAP if _selected[gi].get()]
            if not chosen:
                tk.messagebox.showwarning("提示", "请至少勾选一个标签页!", parent=pick)
                return
            pick.destroy()
            self._ts_scan_groups(chosen)

        ttk.Button(pick, text="🔍 开始扫描", command=_do_scan, width=18).pack(pady=14)

    def _ts_scan_groups(self, group_indices):
        """从指定 group_indices 取股票, 跑操盘阶段分析"""
        pairs = []
        seen = set()
        for gi in group_indices:
            hs = getattr(self, f"holding_stocks_{gi}", [None] * 80)
            for holding in hs:
                if not holding: continue
                name, code = holding
                code6 = re.search(r"(\d{6})", str(code))
                if code6:
                    c = code6.group(1)
                    if c not in seen:
                        seen.add(c)
                        pairs.append((str(name or c).strip(), c))

        print(f"🧬 [操盘阶段] 从 groups {group_indices} 取到 {len(pairs)} 只股票 (去重后)")

        if not pairs:
            tk.messagebox.showinfo("提示", "所选标签页均为空!")
            return

        # 弹窗 + 启动扫描
        self._show_tech_stage_dialog()
        # 覆盖状态文字
        self._ts_status.set(f"📊 已选 {len(group_indices)} 组 → {len(pairs)} 只股票 (去重后)")
        # 后台扫描
        self._ts_run_scan(pairs)

    # ── 备用独立入口 ──

    def _show_tech_stage_dialog(self):
        """弹窗入口: 操盘阶段卡片网格 (输入框+实时卡片+进度条+kill+单只重试)"""
        import queue as _queue
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

        # 控制面板 — 股票范围多选 + 扫描 + 保存 + 回看
        ctrl = tk.LabelFrame(dlg, text="🎛️ 扫描控制", padx=6, pady=6)
        ctrl.pack(fill=tk.X, padx=8, pady=4)

        # 🔘 股票范围多选 (Checkbutton)
        scope_frame = tk.Frame(ctrl); scope_frame.pack(fill=tk.X, pady=(0, 6))
        tk.Label(scope_frame, text="📂 扫描范围:", font=("", 10, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        self._ts_scope_vars = {}
        scope_opts = [
            ("💼自持股", "holding"),
            ("📰资讯股", "news"),
            ("🐉龙头股", "leader"),
            ("🔍选股宝", "xgb"),
            ("📌自选", "watchlist"),
            ("📋手动输入", "manual"),
        ]
        # 淘股吧/韭研等邮票格子
        stamp_opts = [("🍜淘股吧", "taoguba"), ("🥬韭研", "jiuyan"), ("🏆热榜", "hot")]
        tk.Label(scope_frame, text="邮票格:", font=("", 9, "bold")).pack(side=tk.LEFT, padx=(12, 4))
        for lbl, key in stamp_opts:
            var = tk.BooleanVar(value=False)
            self._ts_scope_vars[key] = var
            tk.Checkbutton(scope_frame, text=lbl, variable=var).pack(side=tk.LEFT, padx=2)
        tk.Label(scope_frame, text="持仓类:", font=("", 9, "bold")).pack(side=tk.LEFT, padx=(10, 4))
        for lbl, key in scope_opts[:3]:
            var = tk.BooleanVar(value=(key == "holding"))  # 默认勾选自持股
            self._ts_scope_vars[key] = var
            tk.Checkbutton(scope_frame, text=lbl, variable=var).pack(side=tk.LEFT, padx=2)
        tk.Label(scope_frame, text="其他:", font=("", 9, "bold")).pack(side=tk.LEFT, padx=(10, 4))
        for lbl, key in scope_opts[3:]:
            var = tk.BooleanVar(value=False)
            self._ts_scope_vars[key] = var
            tk.Checkbutton(scope_frame, text=lbl, variable=var).pack(side=tk.LEFT, padx=2)

        # 按钮行
        btn1_row = tk.Frame(ctrl); btn1_row.pack(fill=tk.X, pady=(2, 4))
        ttk.Button(btn1_row, text="▶ 开始扫描", command=self._ts_start_scan_from_scope).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn1_row, text="📋 手动输入",
                   command=lambda: self._ts_input_codes_and_run(dlg)).pack(side=tk.LEFT, padx=4)
        self._ts_kill_btn = ttk.Button(btn1_row, text="⏹ 停止",
                                       command=lambda: self._ts_kill_scan(),
                                       state=tk.DISABLED)
        self._ts_kill_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(btn1_row, text="💾 保存结果",
                   command=self._ts_save_session_to_db).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn1_row, text="🖼 存图片",
                   command=self._ts_save_as_image).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn1_row, text="📄 存文字",
                   command=self._ts_save_as_text).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn1_row, text="📸 存长图",
                   command=self._ts_save_as_long_image).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn1_row, text="📤 导出CSV",
                   command=lambda: self._ts_export_csv(dlg)).pack(side=tk.LEFT, padx=4)

        # 阶段/票型过滤 + 进度条
        btn2_row = tk.Frame(ctrl); btn2_row.pack(fill=tk.X, pady=2)
        tk.Label(btn2_row, text="阶段过滤:", bg="#F1F5F9").pack(side=tk.LEFT, padx=(0, 2))
        self._ts_filter = tk.StringVar(value="全部")
        stage_opts = ["全部", "吸筹", "洗盘", "拉升", "出货", "下跌", "底部横盘"]
        cb1 = ttk.Combobox(btn2_row, textvariable=self._ts_filter, values=stage_opts,
                     width=10, state="readonly")
        cb1.pack(side=tk.LEFT, padx=4)
        cb1.bind("<<ComboboxSelected>>", lambda e: self._ts_apply_filter())

        self._ts_filter_type = tk.StringVar(value="全部")
        tk.Label(btn2_row, text="票型:", bg="#F1F5F9").pack(side=tk.LEFT, padx=(12, 2))
        type_opts = ["全部", "机构票", "游资票", "混合型"]
        cb2 = ttk.Combobox(btn2_row, textvariable=self._ts_filter_type, values=type_opts,
                     width=10, state="readonly")
        cb2.pack(side=tk.LEFT, padx=4)
        cb2.bind("<<ComboboxSelected>>", lambda e: self._ts_apply_filter())

        self._ts_step_label = tk.Label(btn2_row, text="[0%] 等待开始...",
                                       bg="#F1F5F9", fg="#1E40AF",
                                       font=("", 10, "bold"))
        self._ts_step_label.pack(side=tk.RIGHT, padx=(4, 8))
        self._ts_progress = ttk.Progressbar(btn2_row, length=300, mode="determinate")
        self._ts_progress.pack(side=tk.RIGHT, padx=4)

        # 🆕 Notebook: 实时扫描 / 历史回看
        nb = ttk.Notebook(dlg); nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # Tab 1: 📊 实时扫描 (卡片网格)
        tab_live = tk.Frame(nb, bg="#F8FAFC"); nb.add(tab_live, text=" 📊 实时扫描 ")

        container = tk.Frame(tab_live, bg="#F8FAFC")
        container.pack(fill=tk.BOTH, expand=True)

        self._ts_canvas = tk.Canvas(container, highlightthickness=0, bg="#F8FAFC")
        sb = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self._ts_canvas.yview)
        self._ts_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._ts_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._ts_card_frame = tk.Frame(self._ts_canvas, bg="#F8FAFC")
        self._ts_canvas.create_window((0, 0), window=self._ts_card_frame, anchor="nw")
        self._ts_card_frame.bind("<Configure>",
                                 lambda e: self._ts_canvas.configure(scrollregion=self._ts_canvas.bbox("all")))

        # Tab 2: 📜 历史回看
        tab_hist = tk.Frame(nb, bg="#F8FAFC"); nb.add(tab_hist, text=" 📜 历史回看 ")
        self._ts_hist_nb = nb   # 存引用, 方便回看按钮切 Tab
        self._ts_build_history_tab(tab_hist)

        # 底部统计
        self._ts_stats = tk.StringVar(value="统计: 等待扫描...")
        tk.Label(dlg, textvariable=self._ts_stats, anchor="w",
                 bg="#F1F5F9").pack(fill=tk.X, side=tk.BOTTOM)

        self._ts_dlg = dlg
        self._ts_cards = {}
        self._ts_all_results = []
        self._ts_queue = _queue.Queue()
        self._ts_stop_event = threading.Event()
        self._ts_worker = None
        self._ts_status.set("⏳ 请勾选扫描范围 → 点 ▶ 开始扫描")

    def _ts_kill_scan(self):
        """⏹ 杀掉当前扫描线程"""
        self._ts_stop_event.set()
        self._ts_status.set("⏹ 停止信号已发送 — 等待当前步骤退出...")
        self._ts_kill_btn.configure(state=tk.DISABLED)

    def _ts_start_scan_from_watchlist(self, ctrl=None):
        """取 Main 持仓 + 自动扫描"""
        pairs = []
        seen = set()
        groups = [2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14]
        for gi in groups:
            hs = getattr(self, f"holding_stocks_{gi}", [None] * 80)
            for holding in hs:
                if not holding:
                    continue
                name, code = holding
                m = re.search(r"(\d{6})", str(code))
                if m:
                    c = m.group(1)
                    if c not in seen:
                        seen.add(c)
                        pairs.append((str(name or c).strip(), c))
        print(f"[操盘阶段] 自动扫描: {len(pairs)} 只")
        if pairs:
            self._ts_status.set(f"📊 取到 {len(pairs)} 只 → 开始扫描...")
            self._ts_run_scan(pairs)
        else:
            self._ts_status.set("⚠️ 所有持仓组都是空的")

    def _ts_input_codes_and_run(self, dlg):
        """弹窗让用户输入代码 → 解析 → 开始扫描"""
        sub = tk.Toplevel(dlg)
        sub.title("📋 输入股票代码 (多个用逗号/空格/换行分隔)")
        sub.geometry("480x420")
        sub.configure(bg="#F8FAFC")
        sub.transient(dlg)

        tk.Label(sub, text="📋 股票代码 (支持 名称,代码 或纯代码)",
                 bg="#F8FAFC", font=("", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(12, 4))

        txt_frame = tk.Frame(sub, bg="#F8FAFC")
        txt_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=12, pady=4)
        sub.rowconfigure(1, weight=1)
        sub.columnconfigure(0, weight=1)

        txt = scrolledtext.ScrolledText(txt_frame, font=("", 12),
                                        wrap=tk.WORD, borderwidth=1,
                                        relief="solid", height=14)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert("1.0", "601899\n300456,000001\n紫金矿业 601899")
        # 自动 focus
        sub.after(100, lambda: txt.focus_set())

        def _go():
            raw = txt.get("1.0", tk.END).strip()
            pairs = []
            for line in raw.replace(",", " ").replace("\n", " ").split():
                m = re.search(r"(\d{6})", line)
                if m:
                    c = m.group(1)
                    n = line.replace(c, "").replace(",", " ").strip() or c
                    pairs.append((n, c))
            sub.destroy()
            if pairs:
                self._ts_status.set(f"📊 输入 {len(pairs)} 只 → 开始扫描...")
                self._ts_run_scan(pairs)
            else:
                self._ts_status.set("⚠️ 没识别到有效 6 位代码")

        btn = ttk.Button(sub, text="▶ 开始扫描", command=_go)
        btn.grid(row=2, column=0, columnspan=2, pady=10)

    def _ts_run_scan(self, pairs):
        """🔒 后台扫描线程 — 进程安全版本
        后台线程只做两件事:
          1. 把进度/结果塞进 Queue
          2. 绝不碰任何 Tk widget
        主线程用 after(100ms) 轮询 Queue 并 render
        """
        import queue as _queue
        import akshare as ak
        from datetime import datetime, timedelta

        # 清空旧卡片 (主线程)
        try:
            for w in self._ts_card_frame.winfo_children():
                w.destroy()
        except Exception:
            pass
        self._ts_cards = {}
        self._ts_all_results = []
        self._ts_stop_event.clear()
        self._ts_kill_btn.configure(state=tk.NORMAL)

        N = len(pairs)
        TOTAL_STEPS = N * 3  # 3步/只: K线+基金+分析

        # 初始化进度
        self._ts_progress.configure(maximum=TOTAL_STEPS, value=0)
        self._ts_step_label.configure(text=f"[0%] 准备扫描 {N} 只...")

        q = _queue.Queue()

        def _worker():
            """后台 worker — 线程安全, 只往 Queue 塞消息"""
            step_counter = [0]

            for i, (name, code) in enumerate(pairs):
                if self._ts_stop_event.is_set():
                    q.put(("stopped", step_counter[0], N))
                    return

                code6 = re.search(r"(\d{6})", str(code))
                if not code6:
                    q.put(("result", {
                        "name": name, "code": code, "price": 0,
                        "analyze": None, "error": "无有效代码",
                        "index": i, "total": N,
                    }))
                    continue
                code6 = code6.group(1)

                # ── Step 1: 拉 K 线 ──
                if self._ts_stop_event.is_set(): break
                q.put(("progress", step_counter[0],
                       f"K线 {i+1}/{N} — {name}"))
                df = None
                try:
                    df = ak.stock_zh_a_hist(symbol=code6, period="daily",
                                            start_date=(datetime.now() - timedelta(days=400)).strftime("%Y%m%d"),
                                            end_date=datetime.now().strftime("%Y%m%d"),
                                            adjust="qfq")
                except Exception as e:
                    q.put(("log", f"⚠️ {code6} K线拉取异常: {str(e)[:80]}"))
                step_counter[0] += 1

                if df is None or len(df) < 60:
                    step_counter[0] += 2  # 跳过剩余 2 步
                    q.put(("result", {
                        "name": name, "code": code6,
                        "price": 0, "analyze": None,
                        "error": f"K线不足({len(df) if df is not None else 0}行)",
                        "index": i, "total": N,
                    }))
                    continue

                # ── Step 2: 拉基金持仓 ──
                if self._ts_stop_event.is_set(): break
                q.put(("progress", step_counter[0],
                       f"基金持仓 {i+1}/{N} — {name}"))
                fund_df = None
                try:
                    fund_df = ak.stock_fund_stock_holder(symbol=code6)
                except Exception:
                    pass
                step_counter[0] += 1

                # ── Step 3: 分析 ──
                if self._ts_stop_event.is_set(): break
                q.put(("progress", step_counter[0],
                       f"分析 {i+1}/{N} — {name}"))
                try:
                    analysis = analyze_trading_stage(df, fund_df)
                except Exception as e:
                    analysis = None
                    q.put(("log", f"⚠️ {name} 分析异常: {str(e)[:80]}"))
                step_counter[0] += 1

                q.put(("result", {
                    "name": name, "code": code6,
                    "price": float(df.iloc[-1]["收盘"]),
                    "analyze": analysis, "error": None,
                    "index": i, "total": N,
                }))

                if self._ts_stop_event.is_set(): break

            q.put(("done", step_counter[0], N))

        # 启动 worker 线程
        self._ts_worker = threading.Thread(target=_worker, daemon=True)
        self._ts_worker.start()

        # 🚀 主线程轮询 Queue — 彻底线程安全
        self._ts_poll_queue(q, TOTAL_STEPS, N)

    def _ts_poll_queue(self, q, total_steps, N):
        """主线程轮询 Queue — 每 80ms render 一次"""
        import queue as _queue

        try:
            msgs = []
            # 一次性 drain 所有可用消息
            while True:
                try:
                    msgs.append(q.get_nowait())
                except _queue.Empty:
                    break

            for msg in msgs:
                kind = msg[0]

                if kind == "progress":
                    step_val, text = msg[1], msg[2]
                    self._ts_progress.configure(value=min(step_val, total_steps))
                    pct = int(step_val / total_steps * 100) if total_steps else 0
                    self._ts_step_label.configure(text=f"[{pct}%] {text}")

                elif kind == "result":
                    data = msg[1]
                    self._ts_all_results.append(data)
                    self._ts_render_one_card(data)

                elif kind == "log":
                    self._ts_status.set(msg[1])

                elif kind == "stopped":
                    step_val, n = msg[1], msg[2]
                    self._ts_progress.configure(value=step_val)
                    self._ts_step_label.configure(text="[⏹] 用户停止")
                    self._ts_status.set(f"⏹ 扫描已停止 — 已完成 {len(self._ts_all_results)}/{n}")
                    self._ts_kill_btn.configure(state=tk.DISABLED)
                    self._ts_update_stats()
                    return

                elif kind == "done":
                    step_val, n = msg[1], msg[2]
                    self._ts_progress.configure(value=total_steps)
                    self._ts_step_label.configure(text="[100%] 扫描完成")
                    self._ts_status.set(f"✅ 全部完成 — {len(self._ts_all_results)}/{n} 只")
                    self._ts_kill_btn.configure(state=tk.DISABLED)
                    self._ts_update_stats()
                    return

        except Exception as e:
            print(f"[操盘阶段] poll_queue 异常: {e}")

        # 继续轮询
        if self._ts_dlg and self._ts_dlg.winfo_exists():
            self._ts_dlg.after(80, lambda: self._ts_poll_queue(q, total_steps, N))

    def _ts_render_one_card(self, r):
        """实时渲染一张卡片 (主线程调用)"""
        try:
            name, code = r["name"], r["code"]
            a = r.get("analyze")
            err = r.get("error")

            # 如果已有 (比如重试), 先删旧的
            if code in self._ts_cards:
                old_card, _ = self._ts_cards[code]
                try:
                    old_card.destroy()
                except Exception:
                    pass
                del self._ts_cards[code]

            cols = max(3, min(5, (self._ts_canvas.winfo_width() or 1000) // 240))
            cell_w, cell_h = 220, 210

            # 找到空位
            existing = list(self._ts_cards.values())
            idx = len(existing)
            row, col = divmod(idx, cols)

            # 颜色 fallback 表（与 analyze_trading_stage 保持一致）
            _FALLBACK_COLORS = {
                "吸筹": ("#FFF9E6", "#D4A017"), "洗盘": ("#E6F3FF", "#3B82F6"),
                "拉升": ("#E6FFE6", "#22C55E"), "出货": ("#FFE6E6", "#EF4444"),
                "下跌": ("#F5F5F5", "#6B7280"), "底部横盘": ("#FAF5FF", "#8B5CF6"),
            }
            if a is None:
                bg = "#FEE2E2"; tag_color = "#991B1B"; stage = "❌失败"
            else:
                stage = a.get("stage", "?")
                bg = a.get("background_color") or _FALLBACK_COLORS.get(stage, ("#FFFFFF", "#333333"))[0]
                tag_color = a.get("tag_color") or _FALLBACK_COLORS.get(stage, ("#FFFFFF", "#333333"))[1]

            card = tk.Frame(self._ts_card_frame, bg=bg, width=cell_w, height=cell_h,
                            highlightbackground=tag_color, highlightthickness=2,
                            cursor="hand2")
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            card.pack_propagate(False)

            # 阶段标签 + 🔄 重试按钮 (右上角)
            top_right = tk.Frame(card, bg=tag_color)
            top_right.place(relx=0.98, rely=0, anchor="ne", y=4, x=-4)
            tk.Label(top_right, text=f"{stage}", bg=tag_color, fg="white",
                     font=("", 9, "bold"), padx=6, pady=1).pack(side=tk.LEFT)
            retry_btn = tk.Label(top_right, text=" 🔄", bg=tag_color, fg="white",
                                 font=("", 9, "bold"), cursor="hand2", padx=3)
            retry_btn.pack(side=tk.LEFT)
            retry_btn.bind("<Button-1>", lambda e, c=code: self._ts_retry_one(c))

            tk.Label(card, text=f"{name}", bg=bg, font=("", 12, "bold"),
                     anchor="w").pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(card, text=f"{code}", bg=bg, font=("", 9), fg="#666",
                     anchor="w").pack(anchor="w", padx=8)

            if a is not None:
                inst = a.get("institution_vs_hot_money", "")
                inst_color = "#1E40AF" if "机构" in inst else "#DC2626" if "游资" in inst else "#6B7280"
                tk.Label(card, text=f"🏛 {inst}({a.get('institution_score',0)})",
                         bg=bg, fg=inst_color, font=("", 9, "bold"),
                         anchor="w").pack(anchor="w", padx=8, pady=(2, 0))
                d = a.get("detail", {})
                tk.Label(card, text=f"¥{d.get('close','?')}  MA5={d.get('ma5','?')}  MA20={d.get('ma20','?')}",
                         bg=bg, font=("", 9), fg="#333",
                         anchor="w").pack(anchor="w", padx=8)

                # 📊 涨跌幅行 —— 红涨绿跌
                def _pct_color(val):
                    """涨跌幅颜色: 红涨绿跌"""
                    try:
                        v = float(val)
                        if v > 0: return "#DC2626"   # 红
                        if v < 0: return "#16A34A"   # 绿
                        return "#666666"
                    except Exception:
                        return "#666666"

                def _fmt(val, n=2):
                    if val is None: return "--"
                    try:
                        return f"{float(val):+.{n}f}%"
                    except Exception:
                        return "--"

                # 第一行: 当日 + 5日
                r1, r5 = a.get("ret1_pct"), a.get("ret5_pct")
                row_r1 = tk.Frame(card, bg=bg)
                row_r1.pack(anchor="w", padx=8)
                tk.Label(row_r1, text="当日:", bg=bg, font=("", 9), fg="#333").pack(side=tk.LEFT)
                tk.Label(row_r1, text=_fmt(r1), bg=bg, font=("", 9, "bold"),
                         fg=_pct_color(r1)).pack(side=tk.LEFT, padx=(0, 10))
                tk.Label(row_r1, text="5日:", bg=bg, font=("", 9), fg="#333").pack(side=tk.LEFT)
                tk.Label(row_r1, text=_fmt(r5), bg=bg, font=("", 9, "bold"),
                         fg=_pct_color(r5)).pack(side=tk.LEFT)

                # 第二行: 10日 + 20日 + 60日 + 位置
                r10, r20, r60 = a.get("ret10_pct"), a.get("ret20_pct"), a.get("ret60_pct")
                row_r2 = tk.Frame(card, bg=bg)
                row_r2.pack(anchor="w", padx=8)
                tk.Label(row_r2, text="10日:", bg=bg, font=("", 9), fg="#333").pack(side=tk.LEFT)
                tk.Label(row_r2, text=_fmt(r10), bg=bg, font=("", 9, "bold"),
                         fg=_pct_color(r10)).pack(side=tk.LEFT, padx=(0, 10))
                tk.Label(row_r2, text="20日:", bg=bg, font=("", 9), fg="#333").pack(side=tk.LEFT)
                tk.Label(row_r2, text=_fmt(r20, 1), bg=bg, font=("", 9, "bold"),
                         fg=_pct_color(r20)).pack(side=tk.LEFT, padx=(0, 10))
                tk.Label(row_r2, text="📍", bg=bg, font=("", 9), fg="#333").pack(side=tk.LEFT)
                tk.Label(row_r2, text=f"{a.get('pos_range_pct','?')}%",
                         bg=bg, font=("", 9), fg="#333").pack(side=tk.LEFT)
            else:
                tk.Label(card, text=f"❌ {err or '分析失败'}", bg=bg, font=("", 9),
                         fg="#991B1B", anchor="w").pack(anchor="w", padx=8, pady=(6, 0))

            # 单击详情 + 双击 K 线 —— 定时器避免双击时先弹详情
            click_timer = {"id": None}
            def _on_click(e, _r=r):
                if click_timer["id"]:
                    self._ts_dlg.after_cancel(click_timer["id"])
                    click_timer["id"] = None
                click_timer["id"] = self._ts_dlg.after(260, lambda: self._ts_show_card_detail(_r))
            def _on_dblclick(e, _r=r):
                if click_timer["id"]:
                    self._ts_dlg.after_cancel(click_timer["id"]); click_timer["id"] = None
                self._ts_open_kline(_r)
            for w in [card] + [c for c in card.winfo_children() if c is not retry_btn]:
                w.bind("<Button-1>", _on_click)
                w.bind("<Double-Button-1>", _on_dblclick)
            retry_btn.bind("<Button-1>", lambda e, c=code: self._ts_retry_one(c))

            self._ts_cards[code] = (card, r)

        except Exception as e:
            print(f"[操盘阶段] render_card 异常: {e}")

    def _ts_retry_one(self, code):
        """🔄 单只重新跑 (后台线程, 不影响其他卡片)"""
        import akshare as ak
        from datetime import datetime, timedelta

        # 找 name
        name = code
        for r in self._ts_all_results:
            if r.get("code") == code:
                name = r.get("name", code)
                break

        # 更新状态
        self._ts_status.set(f"🔄 重跑 {name}({code})...")

        def _worker():
            df = fund_df = None
            try:
                df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                        start_date=(datetime.now() - timedelta(days=400)).strftime("%Y%m%d"),
                                        end_date=datetime.now().strftime("%Y%m%d"),
                                        adjust="qfq")
            except Exception:
                pass
            try:
                fund_df = ak.stock_fund_stock_holder(symbol=code)
            except Exception:
                pass

            if df is not None and len(df) >= 60:
                try:
                    a = analyze_trading_stage(df, fund_df)
                    price = float(df.iloc[-1]["收盘"])
                except Exception as e:
                    a = None; price = 0; print(f"[操盘阶段] 重跑异常: {e}")
                err = None
            else:
                a = None; price = 0; err = f"K线不足({len(df) if df is not None else 0}行)"

            # 主线程渲染
            def _apply():
                # 替换旧结果
                for i, r in enumerate(self._ts_all_results):
                    if r.get("code") == code:
                        self._ts_all_results[i] = {
                            "name": name, "code": code,
                            "price": price, "analyze": a, "error": err,
                            "index": r.get("index", 0), "total": r.get("total", 0),
                        }
                        break
                else:
                    self._ts_all_results.append({
                        "name": name, "code": code,
                        "price": price, "analyze": a, "error": err,
                        "index": 0, "total": 1,
                    })
                self._ts_render_one_card({
                    "name": name, "code": code,
                    "price": price, "analyze": a, "error": err,
                })
                self._ts_status.set(f"✅ {name}({code}) 重跑完成")
                self._ts_update_stats()

            if self._ts_dlg and self._ts_dlg.winfo_exists():
                self._ts_dlg.after(0, _apply)

        threading.Thread(target=_worker, daemon=True).start()

    def _ts_update_stats(self):
        """更新底部统计"""
        stage_cnt = Counter()
        total_good = 0
        for r in self._ts_all_results:
            a = r.get("analyze")
            if a:
                stage_cnt[a.get("stage", "?")] += 1
                total_good += 1
        if stage_cnt:
            stat = f"📊 总有效: {total_good} | " + " ".join(f"【{k}:{v}】" for k, v in stage_cnt.most_common())
        else:
            stat = f"📊 已完成 {len(self._ts_all_results)} 只 — 等待分析..."
        self._ts_stats.set(stat)

    def _ts_finish_scan(self, results):
        """兼容旧入口 — 现在实时渲染, 此函数不做全量 render"""
        # 保留引用以防外部调用
        self._ts_all_results = results
        self._ts_update_stats()

    def _ts_scan_from_watchlist(self, dlg):
        """从自选股/监测池扫描 —— 用主程序已有的持仓股列表"""
        pairs = []

        # 1. 优先用 _get_self_holding_monitor_stocks (龙头股+Main+同花顺+标签1-8, 去重)
        try:
            fn = getattr(self, "_get_self_holding_monitor_stocks", None)
            if fn:
                stocks = fn()
                for item in stocks:
                    if isinstance(item, (tuple, list)) and len(item) >= 2:
                        pairs.append((str(item[0]).strip() or str(item[1]), str(item[1]).strip()))
        except Exception as e:
            print(f"[操盘阶段] ⚠️ _get_self_holding_monitor_stocks 失败: {e}")

        # 2. 还不够的话, 再补 _get_main_holding_stocks (Main 标签页)
        if len(pairs) < 3:
            try:
                fn2 = getattr(self, "_get_main_holding_stocks", None)
                if fn2:
                    for item in fn2():
                        if isinstance(item, (tuple, list)) and len(item) >= 2:
                            pairs.append((str(item[0]).strip(), str(item[1]).strip()))
            except Exception:
                pass

        # 3. 再补 _get_monitor_holding_stocks (全部组)
        if len(pairs) < 3:
            try:
                fn3 = getattr(self, "_get_monitor_holding_stocks", None)
                if fn3:
                    for item in fn3():
                        if isinstance(item, (tuple, list)) and len(item) >= 2:
                            pairs.append((str(item[0]).strip(), str(item[1]).strip()))
            except Exception:
                pass

        # 去重 (按代码)
        seen = set()
        unique = []
        for name, code in pairs:
            code6 = re.search(r"(\d{6})", str(code))
            if code6 and code6.group(1) not in seen:
                seen.add(code6.group(1))
                unique.append((name, code6.group(1)))

        if not unique:
            # 兜底: 手动输入
            self._ts_input_codes(dlg)
            return

        self._ts_run_scan(unique)

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
        """后台扫描线程 —— 逐只跑 AKShare + 分析, 带分步骤进度"""
        import akshare as ak

        # 清空旧卡片 (主线程)
        try:
            if hasattr(self, '_ts_card_frame') and self._ts_card_frame.winfo_exists():
                for w in self._ts_card_frame.winfo_children():
                    w.destroy()
        except Exception:
            pass
        self._ts_cards = []
        self._ts_all_results = []
        dlg_ref = self._ts_dlg  # 主线程缓存, 后续只用这个引用

        N = len(pairs)

        # 初始化进度条 (主线程)
        try:
            self._ts_progress.configure(maximum=N * 3, value=0)  # 3步/只: K线+基金+分析
            self._ts_status.set(f"⏳ 准备扫描 {N} 只...")
            self._ts_step_label.configure(text="准备中...")
        except Exception:
            pass

        def _ui_update(step_text, bar_val):
            """🔒 主线程安全的 UI 更新 (必须通过 after 调)"""
            try:
                self._ts_progress.configure(value=bar_val)
                pct = int(bar_val / (N * 3) * 100)
                self._ts_status.set(f"📊 {step_text}  ({bar_val}/{N*3} 步骤, {pct}%)")
                self._ts_step_label.configure(text=f"[{pct}%] {step_text}")
            except Exception:
                pass

        def _run():
            results = []
            step_counter = [0]  # 用列表当可变计数器

            for i, (name, code) in enumerate(pairs):
                code6 = re.search(r"(\d{6})", str(code))
                if not code6:
                    results.append({"name": name, "code": code, "price": 0,
                                    "analyze": None, "error": "无有效代码"})
                    continue
                code6 = code6.group(1)

                # ── Step 1: 拉 K 线 ──
                dlg_ref.after(0, lambda n=name, idx=i:
                    _ui_update(f"拉K线 {idx+1}/{N} — {n}", step_counter[0]))
                df = None
                try:
                    df = ak.stock_zh_a_hist(symbol=code6, period="daily",
                                            start_date=(datetime.now() - timedelta(days=400)).strftime("%Y%m%d"),
                                            end_date=datetime.now().strftime("%Y%m%d"),
                                            adjust="qfq")
                except Exception:
                    pass
                step_counter[0] += 1

                if df is None or len(df) < 60:
                    results.append({
                        "name": name, "code": code6,
                        "price": 0, "analyze": None,
                        "error": f"K线不足({len(df) if df is not None else 0}行)",
                    })
                    # 跳过剩余 2 步
                    step_counter[0] += 2
                    dlg_ref.after(0, lambda n=name, idx=i:
                        _ui_update(f"⚠️ {idx+1}/{N} {n} K线不足, 跳过", step_counter[0]))
                    time.sleep(0.15)
                    continue

                # ── Step 2: 拉基金持仓 ──
                dlg_ref.after(0, lambda n=name, idx=i:
                    _ui_update(f"拉基金持仓 {idx+1}/{N} — {n}", step_counter[0]))
                fund_df = None
                try:
                    fund_df = ak.stock_fund_stock_holder(symbol=code6)
                except Exception:
                    pass
                step_counter[0] += 1

                # ── Step 3: 分析 ──
                dlg_ref.after(0, lambda n=name, idx=i:
                    _ui_update(f"分析操盘阶段 {idx+1}/{N} — {n}", step_counter[0]))
                try:
                    analysis = analyze_trading_stage(df, fund_df)
                except Exception as e:
                    analysis = None
                    print(f"[操盘阶段] 分析异常 {name}: {e}")
                step_counter[0] += 1

                results.append({
                    "name": name, "code": code6,
                    "price": float(df.iloc[-1]["收盘"]),
                    "analyze": analysis, "error": None,
                })

                dlg_ref.after(0, lambda n=name, idx=i, sc=step_counter[0]:
                    _ui_update(f"✅ {idx+1}/{N} 完成 — {n}", sc))
                time.sleep(0.15)

            # ── 完成 ──
            dlg_ref.after(0, lambda: _ui_update("全部扫描完成, 渲染卡片中...", N * 3))
            dlg_ref.after(200, lambda: self._ts_finish_scan(results))

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

        # 颜色 fallback（与 analyze_trading_stage 保持一致）
        _FC = {"吸筹": ("#FFF9E6", "#D4A017"), "洗盘": ("#E6F3FF", "#3B82F6"),
               "拉升": ("#E6FFE6", "#22C55E"), "出货": ("#FFE6E6", "#EF4444"),
               "下跌": ("#F5F5F5", "#6B7280"), "底部横盘": ("#FAF5FF", "#8B5CF6")}

        for idx, r in enumerate(filtered):
            a = r["analyze"]
            stage = a.get("stage", "?")
            bg = a.get("background_color") or _FC.get(stage, ("#FFFFFF", "#333333"))[0]
            tag_color = a.get("tag_color") or _FC.get(stage, ("#FFFFFF", "#333333"))[1]
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

            # 点击事件 —— 单击详情, 双击 K 线 (定时器避免冲突)
            click_timer2 = {"id": None}
            def _on_click(e, _r=r):
                if click_timer2["id"]:
                    self._ts_dlg.after_cancel(click_timer2["id"])
                    click_timer2["id"] = None
                click_timer2["id"] = self._ts_dlg.after(260, lambda: self._ts_show_card_detail(_r))
            def _on_dblclick(e, _r=r):
                if click_timer2["id"]:
                    self._ts_dlg.after_cancel(click_timer2["id"]); click_timer2["id"] = None
                self._ts_open_kline(_r)
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
        """双击卡片 → 日线 K 线 + 一目均衡表"""
        code = r["code"]; name = r["name"]
        import re
        m = re.search(r"(\d{6})", str(code))
        if not m: tk.messagebox.showerror("❌", f"无效代码: {code}"); return
        c6 = m.group(1)
        self._ts_show_daily_ichimoku(name, c6)

    def _ts_show_daily_ichimoku(self, name, c6):
        """🆕 日线 K 线 + 一目均衡表 — AKShare 日线 + matplotlib"""
        import threading as _th
        dlg_loading = tk.Toplevel(self._ts_dlg)
        dlg_loading.title("加载中"); dlg_loading.geometry("300x100")
        tk.Label(dlg_loading, text=f"⏳ 拉取 {name}({c6}) 日线 + 计算一目均衡...",
                 font=("", 11)).pack(expand=True)
        dlg_loading.transient(self._ts_dlg)

        def _run():
            try:
                import akshare as ak
                from datetime import datetime, timedelta
                df = ak.stock_zh_a_hist(
                    symbol=c6, period="daily",
                    start_date=(datetime.now() - timedelta(days=500)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d"), adjust="qfq")
                if df is None or len(df) < 60:
                    self._ts_dlg.after(0, lambda: (dlg_loading.destroy(),
                        tk.messagebox.showwarning("⚠️", f"{name} 日线不足")))
                    return
                self._ts_dlg.after(0, lambda: (dlg_loading.destroy(),
                    self._ts_render_daily_ichimoku(name, c6, df)))
            except Exception as e:
                import traceback; traceback.print_exc()
                self._ts_dlg.after(0, lambda: (dlg_loading.destroy(),
                    tk.messagebox.showerror("❌", f"拉取日线失败: {e}")))
        _th.Thread(target=_run, daemon=True).start()

    def _ts_render_daily_ichimoku(self, name, c6, df):
        """日线图 + 一目均衡表 — Notebook 2 Tab + 指标可选项"""
        import matplotlib; matplotlib.use("TkAgg")
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        from matplotlib.figure import Figure
        from matplotlib.patches import Rectangle
        from matplotlib import font_manager
        import numpy as np
        import pandas as pd

        # 中文字体
        _avail = {f.name for f in font_manager.fontManager.ttflist}
        for _f in ["PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS"]:
            if _f in _avail:
                matplotlib.rcParams["font.sans-serif"] = [_f]; break
        matplotlib.rcParams["axes.unicode_minus"] = False

        o = df["开盘"].to_numpy(); h = df["最高"].to_numpy()
        lo = df["最低"].to_numpy(); c = df["收盘"].to_numpy()
        v = df["成交量"].to_numpy()
        x = np.arange(len(c)); dates = df["日期"].astype(str).to_numpy()
        _XLIM = (max(0, len(x)-200), len(x)-1)
        _TICK = max(1, len(dates[-200:]) // 10)

        def _ma(a, n): return np.convolve(a, np.ones(n)/n, mode="valid")
        def _hlc(_h, _lo, n):
            return (np.array([np.max(_h[max(0,i-n+1):i+1]) for i in range(len(_h))]) +
                    np.array([np.min(_lo[max(0,i-n+1):i+1]) for i in range(len(_lo))])) / 2

        # 预计算所有指标
        ma5, ma10, ma20, ma60 = _ma(c, 5), _ma(c, 10), _ma(c, 20), _ma(c, 60)
        tenkan = _hlc(h, lo, 9); kijun = _hlc(h, lo, 26)
        senkou_a = (tenkan + kijun) / 2; senkou_b = _hlc(h, lo, 52)
        senkou_a_fwd = np.concatenate([senkou_a[26:], [np.nan]*26])
        senkou_b_fwd = np.concatenate([senkou_b[26:], [np.nan]*26])
        chikou = np.concatenate([[np.nan]*26, c[:-26]]) if len(c) > 26 else c

        ema12 = np.convolve(c, np.exp(-np.arange(24)/(2*12)), mode="full")[:len(c)] / np.exp(-np.arange(24)/(2*12)).sum()
        ema26 = np.convolve(c, np.exp(-np.arange(52)/(2*26)), mode="full")[:len(c)] / np.exp(-np.arange(52)/(2*26)).sum()
        dif = ema12 - ema26
        dea = np.convolve(dif, np.exp(-np.arange(18)/(2*9)), mode="full")[:len(c)] / np.exp(-np.arange(18)/(2*9)).sum()
        macd_h = (dif - dea) * 2

        # KDJ
        low9 = pd.Series(lo).rolling(9).min().to_numpy()
        high9 = pd.Series(h).rolling(9).max().to_numpy()
        rsv = np.where(high9 - low9 > 0, (c - low9) / (high9 - low9) * 100, 50.0)
        k = np.convolve(np.nan_to_num(rsv, 50), np.exp(-np.arange(6)/(2*3)), mode="full")[:len(c)] / np.exp(-np.arange(6)/(2*3)).sum()
        d = np.convolve(k, np.exp(-np.arange(6)/(2*3)), mode="full")[:len(c)] / np.exp(-np.arange(6)/(2*3)).sum()
        j = 3 * k - 2 * d

        # ═══════ Tk 窗口 ═══════
        dlg = tk.Toplevel(self._ts_dlg)
        dlg.title(f"{name}({c6})  日线 K 线 / 一目均衡表")
        dlg.geometry("1320x840"); dlg.configure(bg="#121212")

        # 顶栏: 指标选项
        top = tk.Frame(dlg, bg="#1E1E1E"); top.pack(fill=tk.X, padx=6, pady=4)
        tk.Label(top, text=f"{name}({c6})  收盘 ¥{c[-1]:.2f}  |  {dates[-1]}",
                 bg="#1E1E1E", fg="#FFD54F", font=("", 11, "bold")).pack(side=tk.LEFT, padx=6)

        opts = {"ma5": True, "ma10": True, "ma20": True, "ma60": True,
                "vol": True, "macd": True, "kdj": False}
        opt_vars = {k: tk.BooleanVar(value=v) for k, v in opts.items()}
        tk.Label(top, text="指标:", bg="#1E1E1E", fg="#9E9E9E").pack(side=tk.LEFT, padx=(14, 2))
        for k, lbl in [("ma5","MA5"),("ma10","MA10"),("ma20","MA20"),("ma60","MA60"),
                       ("vol","成交量"),("macd","MACD"),("kdj","KDJ")]:
            tk.Checkbutton(top, text=lbl, variable=opt_vars[k],
                           bg="#1E1E1E", fg="#CCC", selectcolor="#121212",
                           activebackground="#1E1E1E").pack(side=tk.LEFT, padx=1)

        nb = ttk.Notebook(dlg); nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        tab_frame1 = tk.Frame(nb, bg="#121212"); nb.add(tab_frame1, text="  📊 日线 K 线  ")
        tab_frame2 = tk.Frame(nb, bg="#121212"); nb.add(tab_frame2, text="  📈 一目均衡表  ")

        canvases = {"daily": None, "ichi": None}

        def _setup_ax(a):
            a.set_facecolor("#1E1E1E"); a.tick_params(colors="#9E9E9E", labelsize=8)
            for sp in a.spines.values(): sp.set_color("#444")
            a.grid(True, alpha=0.12, color="#666")

        def _do_candles(ax):
            for i in range(len(x)):
                up = c[i] >= o[i]; col = "#EF5350" if up else "#66BB6A"
                ax.plot([x[i], x[i]], [lo[i], h[i]], color=col, lw=0.8)
                ax.add_patch(Rectangle((x[i]-0.35, min(o[i],c[i])), 0.7, max(abs(c[i]-o[i]), 0.001),
                                        facecolor=col, edgecolor=col, linewidth=0.3))

        def _apply_xaxis(ax):
            ax.set_xlim(*_XLIM)
            tp = np.arange(_XLIM[0], _XLIM[1], _TICK)
            ax.set_xticks(tp); ax.set_xticklabels([dates[i][2:] for i in tp], rotation=45, fontsize=7)

        # ═══════ Tab 1: 📊 日线 K 线 ═══════
        def _draw_daily():
            for w in tab_frame1.winfo_children(): w.destroy()
            fig = Figure(figsize=(12.8, 7.8), dpi=100, facecolor="#121212")
            has_vol = opt_vars["vol"].get()
            has_macd = opt_vars["macd"].get()
            has_kdj = opt_vars["kdj"].get()
            sub_count = 1 + (1 if has_vol else 0) + (1 if has_macd else 0) + (1 if has_kdj else 0)
            hs = [4.5, 1.2, 1.0, 1.0][:sub_count]
            gs = fig.add_gridspec(sub_count, 1, height_ratios=hs, hspace=0.06)
            axes_list = [fig.add_subplot(gs[0])]
            _setup_ax(axes_list[0])
            cur_idx = 1
            if has_vol: axes_list.append(fig.add_subplot(gs[cur_idx], sharex=axes_list[0])); _setup_ax(axes_list[-1]); cur_idx += 1
            if has_macd: axes_list.append(fig.add_subplot(gs[cur_idx], sharex=axes_list[0])); _setup_ax(axes_list[-1]); cur_idx += 1
            if has_kdj: axes_list.append(fig.add_subplot(gs[cur_idx], sharex=axes_list[0])); _setup_ax(axes_list[-1])

            ax = axes_list[0]
            _do_candles(ax)
            if opt_vars["ma5"].get():  ax.plot(x[4:], ma5, color="#FFD54F", lw=1.1, label="MA5")
            if opt_vars["ma10"].get(): ax.plot(x[9:], ma10, color="#42A5F5", lw=1.1, label="MA10")
            if opt_vars["ma20"].get(): ax.plot(x[19:], ma20, color="#AB47BC", lw=1.3, label="MA20")
            if opt_vars["ma60"].get(): ax.plot(x[59:], ma60, color="#66BB6A", lw=1.4, label="MA60")
            ax.set_title(f"{name}({c6})  日线 K 线", color="white", fontsize=12, fontweight="bold")
            if any(opt_vars[k].get() for k in ["ma5","ma10","ma20","ma60"]):
                ax.legend(loc="upper left", fontsize=7, ncol=4, facecolor="#1E1E1E", labelcolor="#CCC", edgecolor="#444")
            _apply_xaxis(ax)

            ai = 1
            if has_vol:
                axv = axes_list[ai]; ai += 1
                colors_v = ["#EF5350" if c[i] >= o[i] else "#66BB6A" for i in range(len(c))]
                axv.bar(x, v / 1e6, color=colors_v, alpha=0.7, width=0.8)
                axv.set_ylabel("成交量(万手)", color="#9E9E9E", fontsize=8)
                _apply_xaxis(axv)
            if has_macd:
                axm = axes_list[ai]; ai += 1
                axm.plot(x, dif, color="#42A5F5", lw=1.0, label="DIF")
                axm.plot(x, dea, color="#FFAB40", lw=1.0, label="DEA")
                axm.bar(x, macd_h, color=["#EF5350" if m>=0 else "#66BB6A" for m in macd_h], width=0.8, alpha=0.8)
                axm.axhline(0, color="#555", lw=0.5)
                axm.legend(loc="upper left", fontsize=7, facecolor="#1E1E1E", labelcolor="#CCC", edgecolor="#444")
                axm.set_ylabel("MACD", color="#9E9E9E", fontsize=8)
                _apply_xaxis(axm)
            if has_kdj:
                axk = axes_list[ai]
                axk.plot(x, k, color="#FFD54F", lw=1.0, label="K")
                axk.plot(x, d, color="#42A5F5", lw=1.0, label="D")
                axk.plot(x, j, color="#EF5350", lw=0.9, label="J")
                axk.axhline(80, color="#EF5350", lw=0.5, ls="--", alpha=0.5)
                axk.axhline(20, color="#66BB6A", lw=0.5, ls="--", alpha=0.5)
                axk.set_ylim(-20, 120)
                axk.legend(loc="upper left", fontsize=7, facecolor="#1E1E1E", labelcolor="#CCC", edgecolor="#444")
                axk.set_ylabel("KDJ", color="#9E9E9E", fontsize=8)
                _apply_xaxis(axk)

            for a in axes_list[:-1]:
                try: a.tick_params(labelbottom=False)
                except: pass

            cv = FigureCanvasTkAgg(fig, master=tab_frame1); cv.draw()
            cv.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            tb = NavigationToolbar2Tk(cv, tab_frame1); tb.update(); tb.pack(side=tk.BOTTOM, fill=tk.X)
            canvases["daily"] = cv

        # ═══════ Tab 2: 📈 一目均衡表 ═══════
        def _draw_ichi():
            for w in tab_frame2.winfo_children(): w.destroy()
            fig = Figure(figsize=(12.8, 7.8), dpi=100, facecolor="#121212")
            sub_count = 1 + (1 if opt_vars["vol"].get() else 0)
            gs = fig.add_gridspec(sub_count, 1, height_ratios=[5, 1.5][:sub_count], hspace=0.06)
            ax = fig.add_subplot(gs[0]); _setup_ax(ax)
            _do_candles(ax)
            # 一目均衡
            ax.plot(x, tenkan, color="#FFAB40", lw=1.3, label="转换线(9)")
            ax.plot(x, kijun,  color="#40C4FF", lw=1.5, label="基准线(26)")
            ax.plot(x, senkou_a_fwd, color="#FF80AB", lw=1.2, label="先行带A")
            ax.plot(x, senkou_b_fwd, color="#7C4DFF", lw=1.2, label="先行带B")
            ax.fill_between(x, senkou_a_fwd, senkou_b_fwd,
                            where=senkou_a_fwd >= senkou_b_fwd, color="#FF80AB", alpha=0.15)
            ax.fill_between(x, senkou_a_fwd, senkou_b_fwd,
                            where=senkou_a_fwd < senkou_b_fwd, color="#7C4DFF", alpha=0.15)
            ax.plot(x, chikou, color="#FFF59D", lw=1.1, ls="--", label="延迟线(26)")
            ax.set_title(f"{name}({c6})  一目均衡表 (Tenkan9 / Kijun26 / Senkou52 / Displace26)",
                         color="white", fontsize=12, fontweight="bold")
            ax.legend(loc="upper left", fontsize=7, ncol=6, facecolor="#1E1E1E", labelcolor="#CCC", edgecolor="#444")
            _apply_xaxis(ax)

            if opt_vars["vol"].get():
                axv = fig.add_subplot(gs[1], sharex=ax); _setup_ax(axv)
                colors_v = ["#EF5350" if c[i] >= o[i] else "#66BB6A" for i in range(len(c))]
                axv.bar(x, v / 1e6, color=colors_v, alpha=0.7, width=0.8)
                axv.set_ylabel("成交量(万手)", color="#9E9E9E", fontsize=8)
                _apply_xaxis(axv)
                ax.tick_params(labelbottom=False)

            cv = FigureCanvasTkAgg(fig, master=tab_frame2); cv.draw()
            cv.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            tb = NavigationToolbar2Tk(cv, tab_frame2); tb.update(); tb.pack(side=tk.BOTTOM, fill=tk.X)
            canvases["ichi"] = cv

        def _redraw(): _draw_daily(); _draw_ichi()
        for _bv in opt_vars.values(): _bv.trace_add("write", lambda *a: _redraw())

        _draw_daily(); _draw_ichi()

    def _ts_simple_kline_fallback(self, name, c6):
        """🆕 极简 K 线 fallback — AKShare 日线 + matplotlib + MA"""
        import threading as _th
        def _run():
            try:
                import akshare as ak
                from datetime import datetime, timedelta
                df = ak.stock_zh_a_hist(
                    symbol=c6, period="daily",
                    start_date=(datetime.now() - timedelta(days=180)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d"), adjust="qfq")
                if df is None or len(df) < 20:
                    self._ts_status.set(f"⚠️ {name} K 线数据不足"); return
                self._ts_dlg.after(0, lambda: self._ts_render_simple_kline(name, c6, df))
            except Exception as e2:
                self._ts_dlg.after(0, lambda: tk.messagebox.showerror(
                    "❌ K线", f"拉取 {name}({c6}) 日线失败:\n{e2}"))
        _th.Thread(target=_run, daemon=True).start()

    def _ts_render_simple_kline(self, name, c6, df):
        """用 matplotlib 画极简日线 + MA"""
        try:
            import matplotlib; matplotlib.use("TkAgg")
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
        except Exception:
            tk.messagebox.showwarning("⚠️", "matplotlib 不可用, 无法画 K 线"); return

        dlg = tk.Toplevel(self._ts_dlg)
        dlg.title(f"📈 {name}({c6}) 日线 + MA20/60")
        dlg.geometry("1000x560")

        fig = Figure(figsize=(10, 5.5), dpi=100, facecolor="#F5F5F5")
        ax = fig.add_subplot(111)

        df["日期"] = pd.to_datetime(df["日期"])
        df["MA20"] = df["收盘"].rolling(20).mean()
        df["MA60"] = df["收盘"].rolling(60).mean()

        # K 线简易: 阳红阴绿 (收盘>=开盘红)
        colors = ["#EF4444" if c >= o else "#22C55E" for c, o in zip(df["收盘"], df["开盘"])]
        ax.bar(df["日期"], df["收盘"] - df["开盘"], bottom=df["开盘"],
               color=colors, width=0.8, alpha=0.8, label="K线")
        ax.plot(df["日期"], df["MA20"], color="#D4A017", linewidth=1.2, label="MA20")
        ax.plot(df["日期"], df["MA60"], color="#3B82F6", linewidth=1.2, label="MA60")
        ax.set_title(f"{name}({c6}) 日线  最新={df.iloc[-1]['收盘']:.2f}  涨跌={df.iloc[-1]['涨跌幅']:.2f}%")
        ax.legend(); ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()

        canvas = FigureCanvasTkAgg(fig, master=dlg)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

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

    # ══════════════════════════════════════════════════════════════
    # 🆕 股票范围采集 (Checkbutton 多选)
    # ══════════════════════════════════════════════════════════════

    def _ts_start_scan_from_scope(self):
        """根据勾选的范围收集股票 → 扫描"""
        pairs = []
        seen = set()

        def _add(name, code):
            m = re.search(r"(\d{6})", str(code))
            if m:
                c = m.group(1)
                if c not in seen:
                    seen.add(c)
                    pairs.append((str(name or c).strip(), c))

        # 1) 自持股 (原有逻辑)
        if self._ts_scope_vars.get("holding") and self._ts_scope_vars["holding"].get():
            for gi in [2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14]:
                hs = getattr(self, f"holding_stocks_{gi}", [None] * 80)
                for holding in hs:
                    if not holding: continue
                    try: _add(holding[0], holding[1])
                    except: pass

        # 2) 资讯股
        if self._ts_scope_vars.get("news") and self._ts_scope_vars["news"].get():
            for gi in [7, 8]:
                hs = getattr(self, f"holding_stocks_{gi}", [None] * 80)
                for h in hs:
                    if h and h[1]: _add(h[0], h[1])
            # 资讯表
            try:
                import sqlite3 as _sq
                db_path = os.path.join(os.getcwd(), "data", "stock_analysis.db")
                if os.path.exists(db_path):
                    conn = _sq.connect(db_path)
                    for row in conn.execute("SELECT DISTINCT title FROM news ORDER BY id DESC LIMIT 300"):
                        m = re.search(r"(\d{6})", str(row[0]))
                        if m: _add("资讯", m.group(1))
                    conn.close()
            except Exception: pass

        # 3) 龙头股 (持9, 热榜)
        if self._ts_scope_vars.get("leader") and self._ts_scope_vars["leader"].get():
            hs = getattr(self, "holding_stocks_9", [None] * 80)
            for h in hs:
                if h and h[1]: _add(h[0], h[1])

        # 4) 淘股吧邮票格子 — 从 _refresh_stamp_board 渲染的数据
        if self._ts_scope_vars.get("taoguba") and self._ts_scope_vars["taoguba"].get():
            for attr in ["_taoguba_stamp_data"]:
                items = getattr(self, attr, []) or []
                for item in items:
                    try: _add(item.get("name", ""), item.get("code", ""))
                    except: pass

        # 5) 韭研邮票格子
        if self._ts_scope_vars.get("jiuyan") and self._ts_scope_vars["jiuyan"].get():
            for attr in ["_jiuyan_stamp_data"]:
                items = getattr(self, attr, []) or []
                for item in items:
                    try: _add(item.get("name", ""), item.get("code", ""))
                    except: pass

        # 6) 热榜 (持 11)
        if self._ts_scope_vars.get("hot") and self._ts_scope_vars["hot"].get():
            hs = getattr(self, "holding_stocks_11", [None] * 80)
            for h in hs:
                if h and h[1]: _add(h[0], h[1])

        # 7) 选股宝 / 自选 (持 13/14)
        for key, gi in [("xgb", 13), ("watchlist", 14)]:
            if self._ts_scope_vars.get(key) and self._ts_scope_vars[key].get():
                hs = getattr(self, f"holding_stocks_{gi}", [None] * 80)
                for h in hs:
                    if h and h[1]: _add(h[0], h[1])

        print(f"[操盘阶段] 范围采集: {len(pairs)} 只 → {seen}")
        if pairs:
            self._ts_status.set(f"📊 扫描范围取到 {len(pairs)} 只 → 开始扫描...")
            self._ts_run_scan(pairs)
        else:
            self._ts_status.set("⚠️ 勾选的范围里没有股票 (试试勾选 💼自持股)")

    # ══════════════════════════════════════════════════════════════
    # 💾 DB 存取 (SQLite, 历史回看)
    # ══════════════════════════════════════════════════════════════

    def _ts_db_path(self):
        p = os.path.join(os.getcwd(), "data", "stock_analysis.db")
        if not os.path.exists(os.path.dirname(p)):
            os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def _ts_db_init(self, conn=None):
        import sqlite3 as _sq
        own = conn is None
        if own: conn = _sq.connect(self._ts_db_path())
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tech_stage_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,            -- ISO 时间戳
                scope TEXT,         -- 范围标签 (e.g. "💼自持股")
                stock_count INTEGER,
                json_data TEXT,     -- 完整 scan 结果 JSON
                note TEXT           -- 用户备注
            )
        """)
        conn.commit()
        if own: conn.close()

    def _ts_save_session_to_db(self):
        """💾 保存当前扫描结果到 DB"""
        if not self._ts_all_results:
            self._ts_status.set("⚠️ 没有扫描结果可保存")
            return
        import sqlite3 as _sq
        try:
            self._ts_db_init()
            conn = _sq.connect(self._ts_db_path())
            scope_labels = [k for k, v in self._ts_scope_vars.items() if v.get()]
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 简化 JSON: 只存核心字段 (完整 analyze dict)
            slim = []
            for r in self._ts_all_results:
                a = r.get("analyze")
                if not a: continue
                slim.append({
                    "code": r["code"], "name": r["name"],
                    "price": r.get("price"),
                    "stage": a.get("stage"),
                    "stage_score": a.get("stage_score"),
                    "trend": a.get("trend"),
                    "kline_pattern": a.get("kline_pattern"),
                    "rsi": a.get("rsi"),
                    "ret20_pct": a.get("ret20_pct"),
                    "ret60_pct": a.get("ret60_pct"),
                    "pos_range_pct": a.get("pos_range_pct"),
                    "institution_vs_hot_money": a.get("institution_vs_hot_money"),
                    "signals": a.get("signals", []),
                    "vol_state": a.get("volume_status", {}).get("state"),
                })
            conn.execute(
                "INSERT INTO tech_stage_history (ts, scope, stock_count, json_data, note) VALUES (?,?,?,?,?)",
                (ts, ",".join(scope_labels) or "unknown", len(slim),
                 json.dumps(slim, ensure_ascii=False), "")
            )
            conn.commit()
            new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()
            self._ts_status.set(f"✅ 已保存到 DB #{new_id} ({len(slim)}只, {ts})")
            # 刷新历史回看列表
            try: self._ts_refresh_history_list()
            except: pass
        except Exception as e:
            self._ts_status.set(f"❌ 保存失败: {e}")

    def _ts_list_history(self):
        """📜 列出历史记录"""
        import sqlite3 as _sq
        self._ts_db_init()
        conn = _sq.connect(self._ts_db_path())
        rows = conn.execute("SELECT id, ts, scope, stock_count, note FROM tech_stage_history ORDER BY id DESC").fetchall()
        conn.close()
        return rows

    def _ts_load_history(self, row_id):
        """🔄 加载一条历史记录 → 恢复扫描结果"""
        import sqlite3 as _sq
        conn = _sq.connect(self._ts_db_path())
        row = conn.execute("SELECT json_data FROM tech_stage_history WHERE id=?", (row_id,)).fetchone()
        conn.close()
        if not row: return None
        return json.loads(row[0])

    # ══════════════════════════════════════════════════════════════
    # 🖼 保存图片 / 文字 / 长图
    # ══════════════════════════════════════════════════════════════

    def _ts_save_as_image(self):
        """🖼 保存图片 — matplotlib 渲染卡片网格 (无需屏幕权限)"""
        if not self._ts_all_results:
            self._ts_status.set("⚠️ 没有扫描结果可保存"); return
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            path = os.path.expanduser(f"~/Desktop/操盘阶段_{ts}.png")
            img = self._ts_render_to_image(self._ts_all_results, long_mode=False)
            img.save(path, "PNG")
            self._ts_status.set(f"✅ PNG 已保存: {path}")
        except Exception as e:
            import traceback; traceback.print_exc()
            self._ts_status.set(f"❌ 存图片失败: {e}")

    def _ts_save_as_text(self):
        """📄 保存为文本格式 (每行一只, 适合今后 grep)"""
        if not self._ts_all_results:
            self._ts_status.set("⚠️ 没有扫描结果可保存"); return
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            path = os.path.expanduser(f"~/Desktop/操盘阶段_{ts}.txt")
            lines = [f"# 操盘阶段扫描 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  共 {len(self._ts_all_results)} 只", "="*60]
            for r in self._ts_all_results:
                a = r.get("analyze")
                if not a: continue
                stage_score = a.get("stage_score", "")
                lines.append(f"{r['name']}({r['code']})  价={r.get('price','')}  阶段={a.get('stage','?')}({stage_score})  票型={a.get('institution_vs_hot_money','?')}  趋势={a.get('trend','?')}  RSI={a.get('rsi','')}  20日={a.get('ret20_pct','')}%  60日={a.get('ret60_pct','')}%")
                for sig in a.get("signals", [])[:3]:
                    lines.append(f"   💡 {sig}")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self._ts_status.set(f"✅ 文字已保存: {path}")
        except Exception as e:
            self._ts_status.set(f"❌ 存文字失败: {e}")

    def _ts_save_as_long_image(self):
        """📸 长图 — matplotlib 把所有卡片纵向串成一张 (无需屏幕权限, 不遗漏)"""
        if not self._ts_all_results:
            self._ts_status.set("⚠️ 没有扫描结果可保存"); return
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            path = os.path.expanduser(f"~/Desktop/操盘阶段_长图_{ts}.png")
            img = self._ts_render_to_image(self._ts_all_results, long_mode=True)
            img.save(path, "PNG")
            self._ts_status.set(f"✅ 长图已保存 ({img.size[0]}x{img.size[1]}): {path}")
        except Exception as e:
            import traceback; traceback.print_exc()
            self._ts_status.set(f"❌ 存长图失败: {e}")

    def _ts_render_to_image(self, results, long_mode=False):
        """🖼 核心: matplotlib 从数据渲染卡片图 (无屏幕权限依赖)"""
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch
        from matplotlib import font_manager
        from PIL import Image as PILImage
        import io

        # 中文字体 fallback 链
        _CN_FONTS = ["PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS", "Noto Sans CJK SC"]
        _avail = {f.name for f in font_manager.fontManager.ttflist}
        _chosen = next((f for f in _CN_FONTS if f in _avail), "DejaVu Sans")
        plt.rcParams["font.sans-serif"] = [_chosen, "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
        print(f"[渲染图片] 字体={_chosen}")

        # 去 Emoji (matplotlib 不支持)
        import re
        def _strip_emoji(s):
            return re.sub(r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F02F]', '', str(s)).strip()

        _SC = {
            "吸筹": ("#FFF9E6", "#D4A017"), "洗盘": ("#E6F3FF", "#3B82F6"),
            "拉升": ("#E6FFE6", "#22C55E"), "出货": ("#FFE6E6", "#EF4444"),
            "下跌": ("#F5F5F5", "#6B7280"), "底部横盘": ("#FAF5FF", "#8B5CF6"),
        }

        if long_mode:
            # 长图 = 1 列 N 行
            cols = 1; rows = len(results)
            card_w = 14; card_h = 3.2; dpi = 120
        else:
            cols = max(3, min(5, int(18 / 3)))  # 4 列
            rows = (len(results) + cols - 1) // cols
            card_w = 4.2; card_h = 3.8; dpi = 120

        fig, axes = plt.subplots(rows, cols, figsize=(card_w * cols, card_h * rows),
                                  squeeze=False, facecolor="#F8FAFC")
        axes_flat = [a for row in axes for a in row]

        for i, r in enumerate(results):
            a = r.get("analyze")
            ax = axes_flat[i]
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values(): sp.set_visible(False)

            if a is None:
                ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.03",
                           facecolor="#FEE2E2", edgecolor="#991B1B", linewidth=2,
                           transform=ax.transAxes))
                ax.text(0.5, 0.5, f"{r['name']}({r['code']})\n❌ 分析失败",
                        ha="center", va="center", fontsize=10, color="#991B1B",
                        transform=ax.transAxes)
                continue

            stage = a.get("stage", "?")
            bg, tc = _SC.get(stage, ("#FFFFFF", "#333333"))
            price = r.get("price", 0)
            inst = a.get("institution_vs_hot_money", "?")
            trend = a.get("trend", "")
            rsip = a.get("ret20_pct", "")
            rs60 = a.get("ret60_pct", "")
            signals = a.get("signals", [])[:2]
            score = a.get("stage_score", "")

            # 卡片背景
            ax.add_patch(FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                         boxstyle="round,pad=0.02",
                         facecolor=bg, edgecolor=tc, linewidth=2,
                         transform=ax.transAxes))
            # 阶段标签
            ax.add_patch(FancyBboxPatch((0.65, 0.75), 0.30, 0.22,
                         boxstyle="round,pad=0.02",
                         facecolor=tc, edgecolor="none",
                         transform=ax.transAxes))
            ax.text(0.80, 0.86, stage, ha="center", va="center",
                    fontsize=9, fontweight="bold", color="white",
                    transform=ax.transAxes)

            # 内容 (去 Emoji)
            ax.text(0.06, 0.92, _strip_emoji(r["name"]), fontsize=11, fontweight="bold",
                    color="#1F2937", transform=ax.transAxes)
            ax.text(0.06, 0.80, _strip_emoji(r["code"]), fontsize=8.5, color="#6B7280",
                    transform=ax.transAxes)
            ax.text(0.06, 0.65, f"{_strip_emoji(inst)}  ¥{price}", fontsize=9, color="#374151",
                    transform=ax.transAxes)
            ax.text(0.06, 0.52, f"{_strip_emoji(trend)}  20日={rsip}%  60日={rs60}%", fontsize=8,
                    color="#4B5563", transform=ax.transAxes)
            # 信号
            sig_y = 0.38
            for s in signals:
                ax.text(0.06, sig_y, f"- {_strip_emoji(s)}", fontsize=7.5, color="#1E40AF",
                        transform=ax.transAxes)
                sig_y -= 0.12
            # 分数
            ax.text(0.06, 0.12, f"score: {score}/100", fontsize=8.5, fontweight="bold",
                    color=tc, transform=ax.transAxes)

        # 隐藏多余格子
        for j in range(len(results), len(axes_flat)):
            axes_flat[j].set_visible(False)

        # 标题 + 日期
        fig.suptitle(
            f"操盘阶段扫描 - 共 {len(results)} 只  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            fontsize=13, fontweight="bold", y=1.005)
        fig.tight_layout(pad=1.2)

        # 转 PIL Image
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        buf.seek(0)
        img = PILImage.open(buf)
        plt.close(fig)
        return img

    # ══════════════════════════════════════════════════════════════
    # 📜 历史回看 Tab
    # ══════════════════════════════════════════════════════════════

    def _ts_build_history_tab(self, tab):
        """构建历史回看 Tab UI — Treeview + 加载 + 查看图片"""
        top = tk.Frame(tab); top.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(top, text="🔄 刷新列表", command=self._ts_refresh_history_list).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="📂 载入选中 → 当前界面", command=self._ts_load_selected_history).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="🗑 删除选中", command=self._ts_delete_selected_history).pack(side=tk.LEFT, padx=4)

        cols = ("id", "ts", "scope", "count")
        tv = ttk.Treeview(tab, columns=cols, show="headings", height=20)
        tv.heading("id", text="#"); tv.heading("ts", text="时间"); tv.heading("scope", text="范围"); tv.heading("count", text="只数")
        tv.column("id", width=50, anchor="center"); tv.column("ts", width=160); tv.column("scope", width=200); tv.column("count", width=60, anchor="center")
        vsb = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=tv.yview)
        tv.configure(yscrollcommand=vsb.set)
        tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=4)
        vsb.pack(side=tk.RIGHT, fill=tk.Y, pady=4)

        self._ts_hist_tv = tv
        self._ts_refresh_history_list()

    def _ts_refresh_history_list(self):
        """刷新历史列表"""
        if not hasattr(self, "_ts_hist_tv") or not self._ts_hist_tv: return
        for item in self._ts_hist_tv.get_children():
            self._ts_hist_tv.delete(item)
        rows = self._ts_list_history()
        for r in rows:
            self._ts_hist_tv.insert("", tk.END, iid=str(r[0]), values=r[:4])
        self._ts_status.set(f"📜 历史记录 {len(rows)} 条")

    def _ts_load_selected_history(self):
        """载入选中的历史记录 → 渲染到实时扫描卡片区"""
        sel = self._ts_hist_tv.selection()
        if not sel:
            self._ts_status.set("⚠️ 请先点选一条历史记录")
            return
        row_id = int(sel[0])
        data = self._ts_load_history(row_id)
        if not data:
            self._ts_status.set("❌ 加载失败")
            return

        # 清空旧卡片
        for w in self._ts_card_frame.winfo_children():
            w.destroy()
        self._ts_cards = {}

        # ══ 补颜色映射（与 analyze_trading_stage 里 stage_colors 一致）══
        _stage_colors = {
            "吸筹": ("#FFF9E6", "#D4A017"),
            "洗盘": ("#E6F3FF", "#3B82F6"),
            "拉升": ("#E6FFE6", "#22C55E"),
            "出货": ("#FFE6E6", "#EF4444"),
            "下跌": ("#F5F5F5", "#6B7280"),
            "底部横盘": ("#FAF5FF", "#8B5CF6"),
        }

        # 把历史数据塞进 self._ts_all_results (格式要兼容卡片渲染)
        self._ts_all_results = []
        for slim in data:
            stage = slim.get("stage", "?")
            bg, tc = _stage_colors.get(stage, ("#FFFFFF", "#333333"))
            self._ts_all_results.append({
                "code": slim["code"], "name": slim["name"],
                "price": slim.get("price", 0),
                "analyze": {
                    "stage": stage,
                    "stage_score": slim.get("stage_score", ""),
                    "trend": slim.get("trend", ""),
                    "kline_pattern": slim.get("kline_pattern", ""),
                    "rsi": slim.get("rsi", ""),
                    "ret20_pct": slim.get("ret20_pct", 0),
                    "ret60_pct": slim.get("ret60_pct", 0),
                    "pos_range_pct": slim.get("pos_range_pct", ""),
                    "institution_vs_hot_money": slim.get("institution_vs_hot_money", ""),
                    "institution_score": 0,
                    "hot_money_score": 0,
                    "signals": slim.get("signals", []),
                    "volume_status": {"state": slim.get("vol_state", "")},
                    "ma_status": {"排列": ""},
                    "detail": {},
                    "background_color": bg,
                    "tag_color": tc,
                },
            })

        # 强制切回实时扫描 Tab
        try: self._ts_hist_nb.select(0)
        except: pass

        # 渲染卡片（用内联渲染避免 _ts_render_one_card 对 _ts_cards dict 的依赖）
        self._ts_apply_filter()
        self._ts_status.set(f"📜 已载入历史 #{row_id} ({len(data)}只)")

    def _ts_delete_selected_history(self):
        """删除选中的历史记录"""
        sel = self._ts_hist_tv.selection()
        if not sel:
            self._ts_status.set("⚠️ 请先点选要删除的记录")
            return
        import sqlite3 as _sq
        try:
            self._ts_db_init()
            conn = _sq.connect(self._ts_db_path())
            for rid in sel:
                conn.execute("DELETE FROM tech_stage_history WHERE id=?", (int(rid),))
            conn.commit(); conn.close()
            self._ts_status.set(f"✅ 已删除 {len(sel)} 条")
            self._ts_refresh_history_list()
        except Exception as e:
            self._ts_status.set(f"❌ 删除失败: {e}")

    def _ts_render_cards(self, results):
        """批量渲染卡片 — 供历史回看加载后复用 (worker 完成后也走这里)"""
        from collections import Counter
        stages = Counter()
        types = Counter()
        for r in results:
            a = r.get("analyze", {})
            stages[a.get("stage", "?")] += 1
            types[a.get("institution_vs_hot_money", "?")] += 1
        stat_parts = [f"{k}={v}" for k, v in stages.most_common()]
        self._ts_stats.set(f"📊 阶段: {' | '.join(stat_parts)}  票型: {dict(types)}")

        for r in results:
            try:
                self._ts_render_one_card(r)
            except Exception as e:
                print(f"[操盘阶段卡片] 渲染失败 {r.get('code')}: {e}")
