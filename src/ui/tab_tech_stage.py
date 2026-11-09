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

        # 控制面板
        ctrl = tk.LabelFrame(dlg, text="🎛️ 扫描控制", padx=6, pady=6)
        ctrl.pack(fill=tk.X, padx=8, pady=4)

        ttk.Button(ctrl, text="🔄 扫描 Main 持仓",
                   command=lambda: self._ts_start_scan_from_watchlist(ctrl)).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctrl, text="📋 输入代码扫描",
                   command=lambda: self._ts_input_codes_and_run(dlg)).pack(side=tk.LEFT, padx=4)
        # 🔴 Kill 按钮
        self._ts_kill_btn = ttk.Button(ctrl, text="⏹ 停止扫描",
                                       command=lambda: self._ts_kill_scan(),
                                       state=tk.DISABLED)
        self._ts_kill_btn.pack(side=tk.LEFT, padx=4)
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

        # 进度条 + 步骤标签
        self._ts_step_label = tk.Label(ctrl, text="[0%] 等待开始...",
                                       bg="#F1F5F9", fg="#1E40AF",
                                       font=("", 10, "bold"))
        self._ts_step_label.pack(side=tk.RIGHT, padx=(4, 8))
        self._ts_progress = ttk.Progressbar(ctrl, length=300, mode="determinate")
        self._ts_progress.pack(side=tk.RIGHT, padx=4)

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
        self._ts_cards = {}        # {code: (widget_row, data_dict)} 支持单只删
        self._ts_all_results = []
        self._ts_queue = _queue.Queue()
        self._ts_stop_event = threading.Event()
        self._ts_worker = None      # 当前线程 ref

        # 🚀 打开即自动扫描 Main 持仓
        dlg.after(200, lambda: self._ts_start_scan_from_watchlist(ctrl))

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
            cell_w, cell_h = 220, 180

            # 找到空位
            existing = list(self._ts_cards.values())
            idx = len(existing)
            row, col = divmod(idx, cols)

            if a is None:
                # 失败卡片
                bg = "#FEE2E2"; tag_color = "#991B1B"
                stage = "❌失败"
            else:
                stage = a["stage"]
                bg = a["background_color"]
                tag_color = a["tag_color"]

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
                tk.Label(card, text=f"📅 近20日={a.get('ret20_pct','?')}%  近60日={a.get('ret60_pct','?')}%  📍{a.get('pos_range_pct','?')}%",
                         bg=bg, font=("", 9), fg="#333",
                         anchor="w").pack(anchor="w", padx=8)
            else:
                tk.Label(card, text=f"❌ {err or '分析失败'}", bg=bg, font=("", 9),
                         fg="#991B1B", anchor="w").pack(anchor="w", padx=8, pady=(6, 0))

            # 单击详情 + 双击 K 线
            card.bind("<Button-1>", lambda e, r=r: self._ts_show_card_detail(r))
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
