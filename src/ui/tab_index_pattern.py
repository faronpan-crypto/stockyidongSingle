# -*- coding: utf-8 -*-
"""
📈 指数日走势形态统计工具
用途: 统计指数/ETF/个股 近 N 天 每日的高开高走/高开低走/低开高走/低开低走 分布
      → 指导做 T 时机
数据源: AKShare (东方财富 + 新浪兜底)
"""
import re
import time as _time
import threading
import queue
import tkinter as tk
from tkinter import ttk, scrolledtext
from collections import Counter

# ── 🆕 快速内存缓存 (避免重复拉 K 线) ──
_KLINE_CACHE = {}          # (code, kind, days) → (df, timestamp)
_KLINE_CACHE_TTL = 300     # 5 分钟过期
_CN_MARKETDATA_FAIL = False  # 🆕 标记东方财富 index_zh_a_hist 是否已失败(一直挂则跳过)


# ═══════════════════════════════════════════════════════════════
# 📋 预设标的
# ═══════════════════════════════════════════════════════════════

# 指数 (用 index_zh_a_hist, symbol 不带 sh/sz 前缀)
INDEX_PRESETS = [
    ("上证指数", "000001", "index"),
    ("深证成指", "399001", "index"),
    ("创业板指", "399006", "index"),
    ("沪深300", "000300", "index"),
    ("中证500", "000905", "index"),
    ("中证1000", "000852", "index"),
    ("科创50", "000688", "index"),
    ("北证50", "899050", "index"),
]

# ETF (用 stock_zh_a_hist)
ETF_PRESETS = [
    ("沪深300ETF", "510300", "etf"),
    ("上证50ETF", "510050", "etf"),
    ("中证500ETF", "510500", "etf"),
    ("创业板ETF", "159915", "etf"),
    ("科创50ETF", "588000", "etf"),
    ("证券ETF", "512880", "etf"),
    ("银行ETF", "512800", "etf"),
    ("医药ETF", "512010", "etf"),
    ("半导体ETF", "512480", "etf"),
    ("金融ETF", "510230", "etf"),
    ("新能源ETF", "516160", "etf"),
    ("消费ETF", "159928", "etf"),
    ("军工ETF", "512660", "etf"),
    ("港股通ETF", "513900", "etf"),
    ("纳指ETF", "513100", "etf"),
    ("日经ETF", "513520", "etf"),
]

# 热门个股 (硬编码, 保证下拉框始终有得选)
HOT_STOCKS = [
    # 大消费
    ("贵州茅台", "600519"),
    ("五粮液", "000858"),
    ("泸州老窖", "000568"),
    ("中国中免", "601888"),
    ("海天味业", "603288"),
    ("伊利股份", "600887"),
    # 金融
    ("招商银行", "600036"),
    ("宁波银行", "002142"),
    ("中国平安", "601318"),
    ("东方财富", "300059"),
    ("中信证券", "600030"),
    ("华泰证券", "601688"),
    # 新能源/科技
    ("宁德时代", "300750"),
    ("比亚迪", "002594"),
    ("隆基绿能", "601012"),
    ("阳光电源", "300274"),
    ("亿纬锂能", "300014"),
    # 半导体
    ("中芯国际", "688981"),
    ("韦尔股份", "603501"),
    ("斯达半导", "603290"),
    ("北方华创", "002371"),
    ("中微公司", "688012"),
    # AI/计算机
    ("科大讯飞", "002230"),
    ("海康威视", "002415"),
    ("金山办公", "688111"),
    ("工业富联", "601138"),
    # 医药
    ("恒瑞医药", "600276"),
    ("药明康德", "603259"),
    ("迈瑞医疗", "300760"),
    # 周期/其他
    ("中国神华", "601088"),
    ("紫金矿业", "601899"),
    ("长江电力", "600900"),
    ("美的集团", "000333"),
    ("格力电器", "000651"),
    ("万科A", "000002"),
]


# ═══════════════════════════════════════════════════════════════
# 🔢 核心分析
# ═══════════════════════════════════════════════════════════════

def classify_daily_pattern(prev_close, open_p, close_p, gap_threshold=0.3):
    """
    单日形态分类

    Args:
        prev_close: 前一日收盘价
        open_p: 今日开盘
        close_p: 今日收盘
        gap_threshold: 高开/低开阈值 (%)

    Returns:
        "高开高走🟢" / "高开低走🔴" / "低开高走🟢" / "低开低走🔴" / "平开⚪" / "平走➖"
    """
    if prev_close <= 0 or open_p <= 0:
        return None
    gap_pct = (open_p - prev_close) / prev_close * 100
    body_pct = (close_p - open_p) / open_p * 100

    if gap_pct > gap_threshold:
        # 高开
        return "高开高走🟢" if body_pct >= 0 else "高开低走🔴"
    elif gap_pct < -gap_threshold:
        # 低开
        return "低开高走🟢" if body_pct >= 0 else "低开低走🔴"
    else:
        # 平开
        return "平走高🟢" if body_pct >= 0 else "平走低🔴"


def fetch_kline(code, kind="index", days=180):
    """
    拉 K 线数据 (带内存缓存 5 分钟)

    Returns:
        DataFrame with columns: date, open, high, low, close, volume, prev_close, gap_pct, body_pct, pattern
        or None on failure
    """
    import akshare as ak
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta

    # ── 🆕 内存缓存检查 ──
    cache_key = (code, kind, days)
    now = _time.time()
    if cache_key in _KLINE_CACHE:
        _df, _ts = _KLINE_CACHE[cache_key]
        if now - _ts < _KLINE_CACHE_TTL and _df is not None:
            print(f"[fetch_kline] 🆕 命中缓存 {code}: {len(_df)} 行")
            return _df.copy()

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

    global _CN_MARKETDATA_FAIL

    try:
        if kind == "index":
            df = None
            # 路径1: akshare index_zh_a_hist (东方财富) — 如果之前已失败则直接跳过
            if not _CN_MARKETDATA_FAIL:
                try:
                    df = ak.index_zh_a_hist(symbol=code, period="daily",
                                            start_date=start, end_date=end)
                except Exception as _e1:
                    print(f"[fetch_kline] index_zh_a_hist 失败: {_e1.__class__.__name__} → 标记跳过")
                    _CN_MARKETDATA_FAIL = True
                    df = None
            # 路径2: 🆕 新浪 stock_zh_index_daily (兜底, 99% 稳定)
            if df is None or len(df) == 0:
                try:
                    # 000/88/89 开头 → sh, 其他 → sz
                    if code.startswith("000") or code.startswith("88") or code.startswith("89"):
                        sina_code = f"sh{code}"
                    elif code.startswith("399"):
                        sina_code = f"sz{code}"
                    elif code.startswith("6"):
                        sina_code = f"sh{code}"
                    else:
                        sina_code = f"sz{code}"
                    df2 = ak.stock_zh_index_daily(symbol=sina_code)
                    if df2 is not None and len(df2) > 0:
                        df2 = df2.rename(columns={"date": "日期", "open": "开盘",
                                                  "high": "最高", "low": "最低",
                                                  "close": "收盘", "volume": "成交量"})
                        df = df2
                        print(f"[fetch_kline] ✅ 新浪兜底 {sina_code}: {len(df)} 行")
                except Exception as _e2:
                    print(f"[fetch_kline] 新浪兜底也失败: {_e2.__class__.__name__}")
                    df = None
        elif kind == "etf":
            df = None
            try:
                df = ak.fund_etf_hist_em(symbol=code, period="daily",
                                         start_date=start, end_date=end, adjust="qfq")
            except Exception as _e1:
                print(f"[fetch_kline] fund_etf_hist_em 失败: {_e1.__class__.__name__}")
                df = None
            # 🆕 新浪 ETF 日线兜底
            if df is None or len(df) == 0:
                try:
                    df2 = ak.stock_zh_index_daily(symbol=f"sh{code}" if code.startswith("5") else f"sz{code}")
                    if df2 is not None and len(df2) > 0:
                        df2 = df2.rename(columns={"date": "日期", "open": "开盘",
                                                  "high": "最高", "low": "最低",
                                                  "close": "收盘", "volume": "成交量"})
                        df = df2
                except Exception:
                    df = None
        else:
            # stock: stock_zh_a_hist → 新浪兜底
            df = None
            try:
                df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                        start_date=start, end_date=end, adjust="qfq")
            except Exception as _e1:
                print(f"[fetch_kline] stock_zh_a_hist 失败: {_e1.__class__.__name__}")
                df = None
            if df is None or len(df) == 0:
                try:
                    sina_code = f"sh{code}" if code.startswith("6") else f"sz{code}"
                    df2 = ak.stock_zh_index_daily(symbol=sina_code)
                    if df2 is not None and len(df2) > 0:
                        df2 = df2.rename(columns={"date": "日期", "open": "开盘",
                                                  "high": "最高", "low": "最低",
                                                  "close": "收盘", "volume": "成交量"})
                        df = df2
                except Exception:
                    df = None
    except Exception:
        return None

    if df is None or len(df) == 0:
        return None

    # 统一列名
    col_map = {"日期": "date", "date": "date",
               "开盘": "open", "open": "open",
               "收盘": "close", "close": "close",
               "最高": "high", "high": "high",
               "最低": "low", "low": "low",
               "成交量": "volume", "volume": "volume"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # 确保 date 列
    if "date" not in df.columns and "日期" in df.columns:
        df = df.rename(columns={"日期": "date"})

    # 类型转换
    for c in ["open", "high", "low", "close"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=["open", "close"]).sort_values("date").reset_index(drop=True)

    # 计算前收 + 形态
    df["prev_close"] = df["close"].shift(1)
    df["gap_pct"] = (df["open"] - df["prev_close"]) / df["prev_close"] * 100
    df["body_pct"] = (df["close"] - df["open"]) / df["open"] * 100
    df["pattern"] = df.apply(
        lambda r: classify_daily_pattern(r["prev_close"], r["open"], r["close"]), axis=1)

    _final = df.tail(days).reset_index(drop=True)
    # 🆕 写入缓存
    _KLINE_CACHE[cache_key] = (_final.copy(), _time.time())
    print(f"[fetch_kline] ✅ 缓存写入 {code}: {len(_final)} 行")
    return _final


def analyze_pattern_stats(df, windows=[5, 10, 20, 30, 60], gap_threshold=0.3):
    """
    多窗口形态统计

    Returns: {
        "overall": Counter,         # 全部形态计数
        "by_window": {5: Counter, 10: Counter, ...},
        "total_days": 180,
        "pattern_next_day": {pattern: {"up": N, "down": N, "next_avg_pct": x}},
        "suggestions": [...]
    }
    """
    if df is None or len(df) < 10:
        return None

    result = {
        "overall": Counter(),
        "by_window": {},
        "total_days": len(df),
        "pattern_next_day": {},
        "suggestions": [],
    }

    valid = df.dropna(subset=["pattern"]).copy()

    # 1) 整体统计
    for p in valid["pattern"].tolist():
        result["overall"][p] += 1

    # 2) 各窗口统计
    for w in windows:
        tail = valid.tail(w)
        result["by_window"][w] = Counter(tail["pattern"].tolist())

    # 3) 形态 → 次日表现分析 (核心: 哪种形态次日涨概率高)
    valid["next_pct"] = valid["close"].shift(-1) / valid["close"] - 1
    pattern_groups = valid.groupby("pattern")
    for p, g in pattern_groups:
        g_valid = g.dropna(subset=["next_pct"])
        if len(g_valid) < 3:
            continue
        up_count = (g_valid["next_pct"] > 0).sum()
        down_count = (g_valid["next_pct"] < 0).sum()
        avg_next = g_valid["next_pct"].mean() * 100
        result["pattern_next_day"][p] = {
            "count": len(g_valid),
            "up_rate": round(up_count / len(g_valid) * 100, 1),
            "avg_next_pct": round(avg_next, 2),
        }

    # 4) 做 T 建议
    suggestions = []

    # 4a. 高开低走 次日上涨概率
    hd_pattern = result["pattern_next_day"].get("高开低走🔴", {})
    if hd_pattern and hd_pattern.get("up_rate", 0) >= 60:
        suggestions.append(
            f"💡 高开低走🔴 后次日上涨概率 {hd_pattern['up_rate']}%, "
            f"均涨幅 {hd_pattern['avg_next_pct']}% — 高开低走日尾盘低吸做 T 成功率高")

    # 4b. 低开高走 次日延续性
    lu_pattern = result["pattern_next_day"].get("低开高走🟢", {})
    if lu_pattern and lu_pattern.get("up_rate", 0) >= 55:
        suggestions.append(
            f"💡 低开高走🟢 后次日上涨概率 {lu_pattern['up_rate']}%, "
            f"均涨幅 {lu_pattern['avg_next_pct']}% — 低开日开盘买入做 T 成功率高")

    # 4c. 最常见形态 (近60日)
    w60 = result["by_window"].get(60, Counter())
    if w60:
        top_pattern = w60.most_common(1)[0]
        top_pct = top_pattern[1] / sum(w60.values()) * 100
        suggestions.append(
            f"📊 近60日最常见形态: {top_pattern[0]} ({top_pattern[1]}天, 占{top_pct:.0f}%) — 可顺势做 T")

    # 4d. 涨跌交替规律
    hd_count = sum(1 for _ in valid["pattern"] if _ == "高开低走🔴")
    lu_count = sum(1 for _ in valid["pattern"] if _ == "低开高走🟢")
    if hd_count > lu_count * 1.5:
        suggestions.append("⚠️ 高开低走显著多于低开高走 — 市场偏空, 冲高先减仓为主")
    elif lu_count > hd_count * 1.5:
        suggestions.append("✅ 低开高走显著多于高开低走 — 市场偏多, 低开是上车机会")

    # 4e. 平走概率
    flat = sum(1 for _ in valid["pattern"] if _ and _.startswith("平"))
    if flat / len(valid) > 0.3:
        suggestions.append("⚖️ 平开比例 > 30% — 震荡市, 建议高抛低吸为主, 追涨风险大")

    result["suggestions"] = suggestions
    return result


# ═══════════════════════════════════════════════════════════════
# 🔮 明日形态推断 — A股量化主流因子体系
# ═══════════════════════════════════════════════════════════════

def predict_next_day_pattern(df, code="000001", app=None):
    """
    基于 A股量化主流因子 + 大数法则 推断明日开盘形态
    6 种形态: 高开高走🟢 / 高开低走🔴 / 低开高走🟢 / 低开低走🔴 / 平走高🟢 / 平走低🔴

    因子权重:
      1. 大数法则 · 历史条件概率  40%  ← 最核心, 相似状态次日分布
      2. 指数位置 · MA多空        15%  ← 价格 vs MA20/60/120
      3. 量能 · 相对均量          15%  ← 今日量 / 60日均量
      4. MA5 动量斜率            10%  ← 短期趋势方向
      5. 北向/涨跌家数           10%  ← 资金情绪
      6. 情绪 · 连板高度          10%  ← 涨停数/炸板率
    """
    import numpy as np
    pattern_keys = ["高开高走🟢", "高开低走🔴", "低开高走🟢", "低开低走🔴",
                    "平走高🟢", "平走低🔴"]
    n = len(df)
    if n < 60:
        return {"error": f"历史数据不足 60 天 (当前 {n})", "ok": False}

    closes = df["close"].values.astype(float)
    highs = df["high"].values.astype(float) if "high" in df.columns else closes.copy()
    lows = df["low"].values.astype(float) if "low" in df.columns else closes.copy()
    opens = df["open"].values.astype(float)
    volumes = df["volume"].values.astype(float) if "volume" in df.columns else np.ones(n) * np.nan

    # 今日状态 (T日)
    price_t = closes[-1]
    price_t1 = closes[-2] if n >= 2 else price_t
    ret_t = (price_t - price_t1) / price_t1 * 100

    # ═══════════════════════════════════════════════════════
    # 因子1: 大数法则 — 找历史上"跟今日状态相似"的日子, 看次日形态分布
    # ═══════════════════════════════════════════════════════
    scores = {p: 0.0 for p in pattern_keys}
    reasons = []

    # 今日状态标签 (3 个维度各 3 档 → 最多 27 种组合, 取 top5 相似)
    def _bucket(val, lo, mid, hi):
        """把连续值切成 3 档"""
        if val <= lo: return -1
        elif val <= mid: return 0
        else: return 1

    # 计算历史各指标
    ma20 = np.array([np.mean(closes[max(0, i-19):i+1]) for i in range(n)])
    ma60 = np.array([np.mean(closes[max(0, i-59):i+1]) for i in range(n)])
    vol_ma60 = np.array([np.mean(volumes[max(0, i-59):i+1]) if not np.isnan(volumes[i]) and volumes[i] > 0 else np.nan for i in range(n)])

    # 今日分桶
    pos_t = (price_t - ma60[-1]) / ma60[-1] * 100  # 距 MA60 %
    pos_bucket_t = _bucket(pos_t, -3, 3, 3)  # -1=低位, 0=中位, 1=高位
    # 量能分桶
    vol_ratio_t = volumes[-1] / vol_ma60[-1] if vol_ma60[-1] and not np.isnan(volumes[-1]) and volumes[-1] > 0 else 1.0
    vol_bucket_t = _bucket(vol_ratio_t, 0.7, 1.3, 1.3)  # -1=缩量, 0=平量, 1=放量
    # 动量分桶 (MA5 斜率)
    ma5_now = np.mean(closes[-5:]) if n >= 5 else price_t
    ma5_prev = np.mean(closes[-10:-5]) if n >= 10 else ma5_now
    mom_bucket_t = _bucket((ma5_now - ma5_prev) / ma5_prev * 100, -0.3, 0.3, 0.3)

    # 找历史相似日子 (排除最后一天, 因为它没有 next pattern)
    sim_count = {p: 0 for p in pattern_keys}
    sim_total = 0
    weights_by_dist = []  # (距离, pattern)

    for i in range(60, n - 1):  # 从 60 天开始 (MA60 有意义), 到倒数第2天 (有次日)
        # 历史日 i 的分桶
        pos_i = (closes[i] - ma60[i]) / ma60[i] * 100 if ma60[i] else 0
        pos_b_i = _bucket(pos_i, -3, 3, 3)
        vol_ratio_i = volumes[i] / vol_ma60[i] if vol_ma60[i] and not np.isnan(volumes[i]) and volumes[i] > 0 else 1.0
        vol_b_i = _bucket(vol_ratio_i, 0.7, 1.3, 1.3)
        ma5_i = np.mean(closes[max(0, i-4):i+1])
        ma5_p_i = np.mean(closes[max(0, i-9):i-4]) if i >= 10 else ma5_i
        mom_b_i = _bucket((ma5_i - ma5_p_i) / ma5_p_i * 100 if ma5_p_i else 0, -0.3, 0.3, 0.3)

        # 计算距离 (0~3, 越小越相似)
        dist = abs(pos_b_i - pos_bucket_t) + abs(vol_b_i - vol_bucket_t) + abs(mom_b_i - mom_bucket_t)
        if dist <= 2:  # 只看相似的 (dist=0 最像, 最多12%的日子)
            # 次日形态 = df["pattern"][i+1]
            pattern_next = df["pattern"].iloc[i + 1]
            if pattern_next in sim_count:
                w = 1.0 / (1.0 + dist * 0.3)  # 越像权重越高
                weights_by_dist.append((dist, pattern_next, w))
                sim_count[pattern_next] += w
                sim_total += w

    # 大数法则得分
    if sim_total >= 5:  # 至少 5 个相似样本
        for p in pattern_keys:
            scores[p] += (sim_count.get(p, 0) / sim_total) * 0.40
        top_p = max(sim_count, key=sim_count.get)
        top_ratio = sim_count[top_p] / sim_total
        reasons.append(f"📊【大数法则】找了 {int(sim_total)} 个历史相似状态 (位置{['低','中','高'][pos_bucket_t+1]}位+量能{['缩','平','放'][vol_bucket_t+1]}量+动量{['下','平','上'][mom_bucket_t+1]}) → 次日「{top_p[:4]}」胜率 {top_ratio*100:.0f}%")
    else:
        # 样本太少 → 降级用整体统计
        reasons.append(f"📊【大数法则】相似样本不足 5 (仅找到 {int(sim_total)}), 降级用整体形态分布")

    # ═══════════════════════════════════════════════════════
    # 因子2: 指数位置 — MA 多空排列
    # ═══════════════════════════════════════════════════════
    if ma60[-1] and ma20[-1]:
        above_ma20 = price_t > ma20[-1]
        above_ma60 = price_t > ma60[-1]
        # 多空排列 → 高开形态概率
        if above_ma20 and above_ma60:
            # 多头排列, 高开高走概率高
            scores["高开高走🟢"] += 0.12
            scores["平走高🟢"] += 0.03
            reasons.append(f"📈【指数位置】多空排列 (价{price_t:.0f}>MA20={ma20[-1]:.0f}>MA60={ma60[-1]:.0f}) → 高开高走偏好")
        elif not above_ma20 and not above_ma60:
            # 空头排列, 低开低走概率高
            scores["低开低走🔴"] += 0.12
            scores["高开低走🔴"] += 0.03
            reasons.append(f"📉【指数位置】空头排列 (价{price_t:.0f}<MA20={ma20[-1]:.0f}<MA60={ma60[-1]:.0f}) → 低开低走偏好")
        elif above_ma20 and not above_ma60:
            # 反弹中, 平开高走概率
            scores["平走高🟢"] += 0.08
            scores["低开高走🟢"] += 0.07
            reasons.append(f"🔄【指数位置】反弹期 (价在MA60下方但MA20上方) → 平开/低开高走偏好")
        else:
            # 回踩中
            scores["高开低走🔴"] += 0.07
            scores["平走低🔴"] += 0.08
            reasons.append(f"🔻【指数位置】回踩期 (价在MA20下方但MA60上方) → 高开/平开低走偏好")

    # ═══════════════════════════════════════════════════════
    # 因子3: 量能 — 相对均量
    # ═══════════════════════════════════════════════════════
    if vol_ratio_t > 0:
        if vol_ratio_t > 1.5:
            # 天量 → 次日大概率高开或低开高走 (情绪延续)
            if ret_t >= 0:
                scores["高开高走🟢"] += 0.10; scores["高开低走🔴"] += 0.05
            else:
                scores["低开高走🟢"] += 0.10; scores["平走高🟢"] += 0.05
            reasons.append(f"📊【量能】放量 ({vol_ratio_t:.1f}x 60日均量) 今日{'涨' if ret_t >= 0 else '跌'} → {'情绪延续' if ret_t >= 0 else '恐慌出清后反弹'}")
        elif vol_ratio_t < 0.6:
            # 地量 → 次日大概率平走高/低开高走 (变盘信号)
            scores["低开高走🟢"] += 0.08; scores["平走高🟢"] += 0.07
            reasons.append(f"📉【量能】缩量 ({vol_ratio_t:.1f}x 60日均量) → 变盘信号, 低开/平走高概率高")
        else:
            reasons.append(f"📊【量能】平量 ({vol_ratio_t:.1f}x 60日均量) → 中性, 看其他因子")

    # ═══════════════════════════════════════════════════════
    # 因子4: MA5 动量斜率
    # ═══════════════════════════════════════════════════════
    if ma5_now and ma5_prev:
        mom_pct = (ma5_now - ma5_prev) / ma5_prev * 100
        if mom_pct > 0.5:
            scores["高开高走🟢"] += 0.07; scores["平走高🟢"] += 0.03
            reasons.append(f"📈【动量】MA5 上拐 (斜率 +{mom_pct:.2f}%) → 高开延续")
        elif mom_pct < -0.5:
            scores["低开低走🔴"] += 0.07; scores["高开低走🔴"] += 0.03
            reasons.append(f"📉【动量】MA5 下拐 (斜率 {mom_pct:.2f}%) → 低开延续")
        else:
            reasons.append(f"⚖️【动量】MA5 走平 (斜率 {mom_pct:+.2f}%) → 方向不明")

    # ═══════════════════════════════════════════════════════
    # 因子5+6: 北向/涨跌家数 + 情绪 (尝试从 app 拿, 拿不到用硬编码)
    # ═══════════════════════════════════════════════════════
    sentiment_up = None
    up_count = down_count = None
    sh_pct = 0.0

    try:
        if app is not None and hasattr(app, '_get_market_up_down_counts'):
            upd = app._get_market_up_down_counts()
            if upd and isinstance(upd, dict):
                up_count = upd.get("up")
                down_count = upd.get("down")
                if up_count and down_count:
                    total = up_count + down_count
                    sentiment_up = up_count / total
    except Exception:
        pass

    try:
        from ui.speculator_watch import _get_sina_realtime
        rt = _get_sina_realtime()
        if rt:
            sh_pct = rt.get("indices", {}).get("IH", {}).get("pct", 0)
    except Exception:
        pass

    if sentiment_up is not None:
        # 涨跌家数比例 → 情绪指标
        if sentiment_up > 0.65:
            scores["高开高走🟢"] += 0.06; scores["平走高🟢"] += 0.04
            reasons.append(f"🔥【情绪】涨跌家数 {up_count}涨/{down_count}跌 ({sentiment_up*100:.0f}%) → 情绪高涨, 高开")
        elif sentiment_up < 0.35:
            scores["低开低走🔴"] += 0.06; scores["高开低走🔴"] += 0.04
            reasons.append(f"❄️【情绪】涨跌家数 {up_count}涨/{down_count}跌 ({sentiment_up*100:.0f}%) → 冰点, 低开")
        else:
            reasons.append(f"⚖️【情绪】涨跌家数平衡 ({sentiment_up*100:.0f}% 上涨)")

    # 实时大盘涨跌 → 辅助
    if sh_pct > 1.5:
        scores["高开高走🟢"] += 0.05
    elif sh_pct < -1.5:
        scores["低开低走🔴"] += 0.05

    # ═══════════════════════════════════════════════════════
    # 每个因子对每个形态的 raw score 贡献 (给 UI 展示用)
    # ═══════════════════════════════════════════════════════
    factor_contrib = {}  # factor_key → {pattern: delta}
    # 大数法则
    _fc1 = {p: (sim_count.get(p, 0) / sim_total * 0.40) if sim_total >= 5 else 0.0
            for p in pattern_keys}
    factor_contrib["①大数法则"] = _fc1

    # 指数位置
    _fc2 = {p: 0.0 for p in pattern_keys}
    if ma60[-1] and ma20[-1]:
        above_ma20 = price_t > ma20[-1]
        above_ma60 = price_t > ma60[-1]
        if above_ma20 and above_ma60:
            _fc2["高开高走🟢"] = 0.12; _fc2["平走高🟢"] = 0.03
        elif not above_ma20 and not above_ma60:
            _fc2["低开低走🔴"] = 0.12; _fc2["高开低走🔴"] = 0.03
        elif above_ma20 and not above_ma60:
            _fc2["平走高🟢"] = 0.08; _fc2["低开高走🟢"] = 0.07
        else:
            _fc2["高开低走🔴"] = 0.07; _fc2["平走低🔴"] = 0.08
    factor_contrib["②指数位置"] = _fc2

    # 量能
    _fc3 = {p: 0.0 for p in pattern_keys}
    if vol_ratio_t > 0:
        if vol_ratio_t > 1.5:
            if ret_t >= 0:
                _fc3["高开高走🟢"] = 0.10; _fc3["高开低走🔴"] = 0.05
            else:
                _fc3["低开高走🟢"] = 0.10; _fc3["平走高🟢"] = 0.05
        elif vol_ratio_t < 0.6:
            _fc3["低开高走🟢"] = 0.08; _fc3["平走高🟢"] = 0.07
    factor_contrib["③量能"] = _fc3

    # 动量
    _fc4 = {p: 0.0 for p in pattern_keys}
    if ma5_now and ma5_prev:
        mom_pct = (ma5_now - ma5_prev) / ma5_prev * 100
        if mom_pct > 0.5:
            _fc4["高开高走🟢"] = 0.07; _fc4["平走高🟢"] = 0.03
        elif mom_pct < -0.5:
            _fc4["低开低走🔴"] = 0.07; _fc4["高开低走🔴"] = 0.03
    factor_contrib["④动量"] = _fc4

    # 情绪
    _fc5 = {p: 0.0 for p in pattern_keys}
    if sentiment_up is not None:
        if sentiment_up > 0.65:
            _fc5["高开高走🟢"] = 0.06; _fc5["平走高🟢"] = 0.04
        elif sentiment_up < 0.35:
            _fc5["低开低走🔴"] = 0.06; _fc5["高开低走🔴"] = 0.04
    if sh_pct > 1.5:
        _fc5["高开高走🟢"] += 0.05
    elif sh_pct < -1.5:
        _fc5["低开低走🔴"] += 0.05
    factor_contrib["⑤情绪"] = _fc5

    # ═══════════════════════════════════════════════════════
    # 归一化 probs (6 因子加总 → 归一化)
    # ═══════════════════════════════════════════════════════
    total_score = sum(scores.values())
    if total_score < 0.01:
        total_score = 0.01
    probs = {p: scores[p] / total_score for p in pattern_keys}

    best = max(probs, key=probs.get)
    sorted_p = sorted(probs.items(), key=lambda x: -x[1])

    # 置信度
    top_prob = sorted_p[0][1]
    conf_level = "高" if top_prob >= 0.30 else ("中" if top_prob >= 0.22 else "低")

    return {
        "ok": True,
        "best": best,
        "confidence": conf_level,
        "probs": sorted_p,
        "factor_contrib": factor_contrib,  # 🆕 因子贡献拆解
        "reasons": reasons,
        "today_state": {
            "price": price_t, "ret_pct": ret_t,
            "ma20": ma20[-1], "ma60": ma60[-1],
            "pos_bucket": ["低位", "中位", "高位"][pos_bucket_t + 1],
            "vol_ratio": vol_ratio_t,
            "vol_bucket": ["缩量", "平量", "放量"][vol_bucket_t + 1],
            "mom_bucket": ["向下", "平", "向上"][mom_bucket_t + 1],
            "sh_pct": sh_pct,
            "sentiment_up": sentiment_up,
        }
    }


def predict_today_from_yesterday(df, code="000001", app=None):
    """
    🔮 今日回看 — 用昨天(T-1)收盘数据推断今天(T)形态, 跟实际对比验证模型

    返回:
      - predicted: 完整推断结果 (best, probs, factor_contrib...)
      - actual: 今天实际形态
      - hit: bool — 推断第一名是否命中
      - top3_hit: bool — 实际形态是否在 Top3 概率里
      - accuracy: 模型历史回测胜率 (相似样本条件概率)
    """
    n = len(df)
    if n < 61:
        return {"ok": False, "error": "历史数据不足"}

    # 用 yesterday 的状态做推断 (T-1 的所有值)
    # 复用同一个 predict 函数的逻辑 — 把 df 去掉最后一行, 就相当于 "今天变成了昨天"
    # 但更清晰的做法: 直接改 predict 的查询索引
    import numpy as np
    from collections import Counter

    pattern_keys = ["高开高走🟢", "高开低走🔴", "低开高走🟢", "低开低走🔴",
                    "平走高🟢", "平走低🔴"]
    closes = df["close"].values.astype(float)
    highs = df["high"].values.astype(float) if "high" in df.columns else closes.copy()
    lows = df["low"].values.astype(float) if "low" in df.columns else closes.copy()
    opens = df["open"].values.astype(float)
    volumes = df["volume"].values.astype(float) if "volume" in df.columns else np.ones(n) * np.nan

    def _bucket(val, lo, mid, hi):
        if val <= lo: return -1
        elif val <= mid: return 0
        else: return 1

    # ═══════════════════════════════════════════════════════
    # 关键: 用 T-1 (昨天) 的状态
    # ═══════════════════════════════════════════════════════
    idx_yesterday = n - 2  # T-1
    idx_today = n - 1      # T

    ma20 = np.array([np.mean(closes[max(0, i-19):i+1]) for i in range(n)])
    ma60 = np.array([np.mean(closes[max(0, i-59):i+1]) for i in range(n)])
    vol_ma60 = np.array([np.mean(volumes[max(0, i-59):i+1]) if not np.isnan(volumes[i]) and volumes[i] > 0 else np.nan for i in range(n)])

    # 昨天状态
    price_y = closes[idx_yesterday]
    pos_y = (price_y - ma60[idx_yesterday]) / ma60[idx_yesterday] * 100
    pos_bucket_y = _bucket(pos_y, -3, 3, 3)
    vol_ratio_y = volumes[idx_yesterday] / vol_ma60[idx_yesterday] if vol_ma60[idx_yesterday] and not np.isnan(volumes[idx_yesterday]) and volumes[idx_yesterday] > 0 else 1.0
    vol_bucket_y = _bucket(vol_ratio_y, 0.7, 1.3, 1.3)
    ma5_now_y = np.mean(closes[idx_yesterday-4:idx_yesterday+1]) if idx_yesterday >= 4 else price_y
    ma5_prev_y = np.mean(closes[idx_yesterday-9:idx_yesterday-4]) if idx_yesterday >= 10 else ma5_now_y
    mom_bucket_y = _bucket((ma5_now_y - ma5_prev_y) / ma5_prev_y * 100 if ma5_prev_y else 0, -0.3, 0.3, 0.3)
    ret_y = (price_y - closes[idx_yesterday-1]) / closes[idx_yesterday-1] * 100 if idx_yesterday >= 1 else 0

    # 实际今天形态
    actual_pattern = str(df["pattern"].iloc[idx_today]) if "pattern" in df.columns else "未知"
    price_today = closes[idx_today]
    ret_today = (price_today - price_y) / price_y * 100

    # ═══════════════════════════════════════════════════════
    # 大数法则: 在历史 i=60..idx_yesterday-1 中找相似 (排除昨天和今天!)
    # ═══════════════════════════════════════════════════════
    scores = {p: 0.0 for p in pattern_keys}
    reasons = []

    sim_count = {p: 0.0 for p in pattern_keys}
    sim_total = 0
    for i in range(60, idx_yesterday):  # 到 idx_yesterday 为止 (不含昨天)
        pos_i = (closes[i] - ma60[i]) / ma60[i] * 100 if ma60[i] else 0
        pos_b_i = _bucket(pos_i, -3, 3, 3)
        vol_ratio_i = volumes[i] / vol_ma60[i] if vol_ma60[i] and not np.isnan(volumes[i]) and volumes[i] > 0 else 1.0
        vol_b_i = _bucket(vol_ratio_i, 0.7, 1.3, 1.3)
        ma5_i = np.mean(closes[max(0, i-4):i+1])
        ma5_p_i = np.mean(closes[max(0, i-9):i-4]) if i >= 10 else ma5_i
        mom_b_i = _bucket((ma5_i - ma5_p_i) / ma5_p_i * 100 if ma5_p_i else 0, -0.3, 0.3, 0.3)
        dist = abs(pos_b_i - pos_bucket_y) + abs(vol_b_i - vol_bucket_y) + abs(mom_b_i - mom_bucket_y)
        if dist <= 2:
            p_next = df["pattern"].iloc[i + 1]  # 历史上 i 的次日 (对应 "今天" 的角色)
            if p_next in sim_count:
                w = 1.0 / (1.0 + dist * 0.3)
                sim_count[p_next] += w; sim_total += w

    # 计算因子贡献 (跟 predict_next_day_pattern 一模一样的逻辑, 只是查询对象是昨天)
    # 因子1 大数法则 (40%)
    _fc1 = {p: (sim_count.get(p, 0) / sim_total * 0.40) if sim_total >= 5 else 0.0 for p in pattern_keys}
    for p in pattern_keys: scores[p] += _fc1[p]
    factor_contrib = {"①大数法则": _fc1}

    top_sim = max(sim_count, key=sim_count.get) if sim_total >= 5 else None
    if sim_total >= 5:
        reasons.append(f"📊 找了 {int(sim_total)} 个历史相似状态 → 次日「{top_sim[:4]}」最高")
    else:
        reasons.append(f"📊 相似样本不足, 降级用整体分布")

    # 因子2 指数位置 (15%)
    above_ma20 = price_y > ma20[idx_yesterday]
    above_ma60 = price_y > ma60[idx_yesterday]
    _fc2 = {p: 0.0 for p in pattern_keys}
    if ma60[idx_yesterday] and ma20[idx_yesterday]:
        if above_ma20 and above_ma60:
            _fc2["高开高走🟢"] = 0.12; _fc2["平走高🟢"] = 0.03
        elif not above_ma20 and not above_ma60:
            _fc2["低开低走🔴"] = 0.12; _fc2["高开低走🔴"] = 0.03
        elif above_ma20 and not above_ma60:
            _fc2["平走高🟢"] = 0.08; _fc2["低开高走🟢"] = 0.07
        else:
            _fc2["高开低走🔴"] = 0.07; _fc2["平走低🔴"] = 0.08
    for p in pattern_keys: scores[p] += _fc2[p]
    factor_contrib["②指数位置"] = _fc2

    # 因子3 量能 (15%)
    _fc3 = {p: 0.0 for p in pattern_keys}
    if vol_ratio_y > 0:
        if vol_ratio_y > 1.5:
            if ret_y >= 0: _fc3["高开高走🟢"] = 0.10; _fc3["高开低走🔴"] = 0.05
            else: _fc3["低开高走🟢"] = 0.10; _fc3["平走高🟢"] = 0.05
        elif vol_ratio_y < 0.6:
            _fc3["低开高走🟢"] = 0.08; _fc3["平走高🟢"] = 0.07
    for p in pattern_keys: scores[p] += _fc3[p]
    factor_contrib["③量能"] = _fc3

    # 因子4 动量 (10%)
    _fc4 = {p: 0.0 for p in pattern_keys}
    mom_pct_y = (ma5_now_y - ma5_prev_y) / ma5_prev_y * 100 if ma5_prev_y else 0
    if mom_pct_y > 0.5:
        _fc4["高开高走🟢"] = 0.07; _fc4["平走高🟢"] = 0.03
    elif mom_pct_y < -0.5:
        _fc4["低开低走🔴"] = 0.07; _fc4["高开低走🔴"] = 0.03
    for p in pattern_keys: scores[p] += _fc4[p]
    factor_contrib["④动量"] = _fc4

    # 归一化
    total = sum(scores.values())
    probs = {p: scores[p] / total if total > 0 else 1/6 for p in pattern_keys}
    sorted_p = sorted(probs.items(), key=lambda x: -x[1])
    best = sorted_p[0][0]
    top3 = [p for p, _ in sorted_p[:3]]

    # 判定
    hit = (best == actual_pattern)
    top3_hit = (actual_pattern in top3)
    top1_prob = sorted_p[0][1]
    top3_sum = sum(probs.get(p, 0) for p in top3)
    actual_prob = probs.get(actual_pattern, 0)

    # 回测胜率: 相似样本的条件概率分布中 "实际形态" 出现的频率
    # 这就是模型的"理论胜率" — 历史上同样状态下, 发生这种形态的频率
    historical_hit_rate = (sim_count.get(actual_pattern, 0) / sim_total * 100) if sim_total >= 5 else None

    return {
        "ok": True,
        # 推断
        "predicted_best": best,
        "predicted_probs": sorted_p,
        "factor_contrib": factor_contrib,
        "confidence": "高" if top1_prob >= 0.30 else ("中" if top1_prob >= 0.22 else "低"),
        # 实际
        "actual_pattern": actual_pattern,
        "actual_date": str(df["date"].iloc[idx_today])[:10] if "date" in df.columns else "今天",
        "today_ret_pct": ret_today,
        "yesterday_state": {
            "date": str(df["date"].iloc[idx_yesterday])[:10] if "date" in df.columns else "昨天",
            "price": price_y, "ret_pct": ret_y,
            "ma20": ma20[idx_yesterday], "ma60": ma60[idx_yesterday],
            "pos_bucket": ["低位", "中位", "高位"][pos_bucket_y + 1],
            "vol_ratio": vol_ratio_y,
            "vol_bucket": ["缩量", "平量", "放量"][vol_bucket_y + 1],
            "mom_bucket": ["向下", "平", "向上"][mom_bucket_y + 1],
        },
        # 判定
        "hit_top1": hit,
        "hit_top3": top3_hit,
        "top3_list": top3,
        "actual_prob": actual_prob,
        "top1_prob": top1_prob,
        "top3_prob_sum": top3_sum,
        "historical_hit_rate": historical_hit_rate,
        "reasons": reasons,
        "sim_count": int(sim_total),
    }


def show_index_pattern_analyzer(parent, app=None):
    """📈 指数日走势形态统计 — 独立弹窗"""
    import threading
    import queue as _queue
    from datetime import datetime as _DT

    win = tk.Toplevel(parent)
    win.title("📈 指数日走势形态统计 — 做 T 指南")
    win.geometry("960x780")
    win.configure(bg="#F8FAFC")
    win.transient(parent)

    # ── 顶栏: 选择标的 + 时间窗口 + 阈值 ──
    top = tk.Frame(win, bg="#1565C0", height=56)
    top.pack(fill=tk.X)
    tk.Label(top, text="📈 指数日走势形态统计",
             font=("", 13, "bold"), bg="#1565C0", fg="white").pack(side=tk.LEFT, padx=14, pady=14)

    # 标的选择
    ctrl = tk.Frame(win, bg="#E3F2FD")
    ctrl.pack(fill=tk.X, padx=6, pady=6)

    tk.Label(ctrl, text="标的:", bg="#E3F2FD").pack(side=tk.LEFT, padx=(10, 2))

    # ── 收集所有下拉项 ──
    all_items = []
    # 1) 预设指数
    for n, c, _ in INDEX_PRESETS:
        all_items.append(f"🗂 指数 · {n} ({c})")
    # 2) 预设 ETF
    for n, c, _ in ETF_PRESETS:
        all_items.append(f"🗂 ETF · {n} ({c})")
    # 3) 热门个股 (硬编码, 保证有得选)
    for n, c in HOT_STOCKS:
        all_items.append(f"🔥 个股 · {n} ({c})")

    # 4) 从 app 注入持仓/龙头/资讯股 (有数据才加)
    if app is not None:
        group_map = [
            ("💼 持仓", "holding_stocks"),
            ("🐉 龙头", "holding_stocks_2"),
            ("📰 资讯", "holding_stocks_3"),
        ]
        for group_label, attr in group_map:
            stocks = getattr(app, attr, None)
            if not stocks:
                continue
            count = 0
            for item in stocks:
                if item is None:
                    continue
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    s_name, s_code = str(item[0]).strip(), str(item[1]).strip()
                    if s_code and s_name and s_code.isdigit() and len(s_code) == 6:
                        all_items.append(f"{group_label} · {s_name} ({s_code})")
                        count += 1
            if count > 0:
                pass  # 这个组有数据了就保留
            else:
                # 整个组都是 None, 不加 "💼 持仓 · ..." 这些
                pass

    combo_var = tk.StringVar(value=all_items[0])
    cb = ttk.Combobox(ctrl, textvariable=combo_var, values=all_items,
                      width=34)  # 可编辑
    cb.pack(side=tk.LEFT, padx=4)

    # 标的类型 (自定义时需要)
    type_var = tk.StringVar(value="自动")
    ttk.Combobox(ctrl, textvariable=type_var,
                 values=["自动", "指数", "ETF", "个股"],
                 width=6, state="readonly").pack(side=tk.LEFT, padx=(4, 0))

    # 时间窗口
    tk.Label(ctrl, text="窗口:", bg="#E3F2FD").pack(side=tk.LEFT, padx=(14, 2))
    win_var = tk.StringVar(value="60天")
    win_cb = ttk.Combobox(ctrl, textvariable=win_var,
                          values=["5天", "10天", "20天", "30天", "60天", "120天"],
                          width=8, state="readonly")
    win_cb.pack(side=tk.LEFT, padx=4)

    # 高开阈值
    tk.Label(ctrl, text="高开阈值:", bg="#E3F2FD").pack(side=tk.LEFT, padx=(14, 2))
    gap_var = tk.StringVar(value="0.3")
    gap_cb = ttk.Combobox(ctrl, textvariable=gap_var,
                          values=["0.1", "0.2", "0.3", "0.5", "1.0"],
                          width=5, state="readonly")
    gap_cb.pack(side=tk.LEFT, padx=4)
    tk.Label(ctrl, text="%", bg="#E3F2FD").pack(side=tk.LEFT)

    # 按钮
    status_var = tk.StringVar(value="⏳ 准备就绪")
    analyze_btn = ttk.Button(ctrl, text="▶ 开始统计", width=12)
    analyze_btn.pack(side=tk.RIGHT, padx=10)

    predict_btn = tk.Button(ctrl, text="🔮 明日推断", width=14,
                            bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
                            highlightbackground="#7B1FA2", highlightthickness=2,
                            font=("", 10, "bold"), cursor="hand2")
    predict_btn.pack(side=tk.RIGHT, padx=6)

    review_btn = tk.Button(ctrl, text="🔙 今日回看", width=12,
                           bg="#FFFFFF", fg="black", activebackground="#FFF3E0",
                           highlightbackground="#FB8C00", highlightthickness=2,
                           font=("", 10, "bold"), cursor="hand2")
    review_btn.pack(side=tk.RIGHT, padx=6)

    # ── Notebook: 统计图 + 建议 + 每日明细 ──
    nb = ttk.Notebook(win)
    nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

    # Tab 1: 统计卡片 + 建议
    tab1 = tk.Frame(nb, bg="#F8FAFC")
    nb.add(tab1, text="📊 统计与建议")

    # Tab 2: 每日明细表格
    tab2 = tk.Frame(nb, bg="#F8FAFC")
    nb.add(tab2, text="📅 每日明细")

    # ── Tab1: 统计卡片 ──
    cards_fr = tk.Frame(tab1, bg="#F8FAFC")
    cards_fr.pack(fill=tk.X, padx=8, pady=8)

    # 6 种形态的卡片
    pattern_keys = ["高开高走🟢", "高开低走🔴", "低开高走🟢", "低开低走🔴",
                    "平走高🟢", "平走低🔴"]
    card_labels = {
        "高开高走🟢": "高开高走",
        "高开低走🔴": "高开低走",
        "低开高走🟢": "低开高走",
        "低开低走🔴": "低开低走",
        "平走高🟢": "平走高",
        "平走低🔴": "平走低",
    }
    pattern_cards = {}  # key → (count_lbl, pct_lbl, next_lbl)

    for i, p in enumerate(pattern_keys):
        card = tk.Frame(cards_fr, bg="white", highlightbackground="#CBD5E1",
                        highlightthickness=1)
        card.grid(row=i // 3, column=i % 3, sticky="nsew", padx=4, pady=4)
        cards_fr.grid_columnconfigure(i % 3, weight=1)

        tk.Label(card, text=card_labels[p], bg="white", fg="#475569",
                 font=("", 10, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
        count_lbl = tk.Label(card, text="—", bg="white", fg="#1565C0",
                             font=("", 18, "bold"))
        count_lbl.pack(anchor="w", padx=10)
        pct_lbl = tk.Label(card, text="占比 —%", bg="white", fg="#64748B",
                           font=("", 9))
        pct_lbl.pack(anchor="w", padx=10)
        next_lbl = tk.Label(card, text="次日涨 — 均 —%", bg="white", fg="#94A3B8",
                            font=("", 9))
        next_lbl.pack(anchor="w", padx=10, pady=(0, 8))
        pattern_cards[p] = (count_lbl, pct_lbl, next_lbl)

    # 窗口对比
    win_fr = tk.LabelFrame(tab1, text="📊 各窗口形态对比", font=("", 10, "bold"),
                           bg="#F8FAFC")
    win_fr.pack(fill=tk.X, padx=8, pady=(8, 4))

    # Treeview 表格
    cols = ("window", "高开高走", "高开低走", "低开高走", "低开低走", "平走高", "平走低", "总计")
    tv = ttk.Treeview(win_fr, columns=cols, show="headings", height=8)
    for c in cols:
        tv.heading(c, text=c)
        tv.column(c, width=78 if c != "window" else 80, anchor="center")
    tv.pack(fill=tk.X, padx=6, pady=6)

    # 建议区
    sug_fr = tk.LabelFrame(tab1, text="💡 做 T 时机建议", font=("", 10, "bold"),
                           bg="#F8FAFC")
    sug_fr.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    sug_text = scrolledtext.ScrolledText(sug_fr, font=("", 10), wrap=tk.WORD,
                                         height=10, state="disabled")
    sug_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    # ── Tab2: 每日明细 ──
    # 帮助弹窗函数
    def _show_help(topic):
        help_win = tk.Toplevel(win)
        help_win.title("❓ 指标说明")
        help_win.geometry("620x560")
        help_win.configure(bg="#FFFDE7")
        help_win.transient(win)

        # 根据主题显示不同内容
        helps = {
            "gap": {
                "title": "gap_pct — 高开/低开幅度",
                "color": "#F57F17",
                "content": """
gap_pct = (今日开盘价 − 昨日收盘价) / 昨日收盘价 × 100%

═══════════════════════════════════

  正  → 高开 (跳空高开)
  负  → 低开 (跳空低开)
  0   → 平开

  例:
    昨收 10.00 → 今开 10.30 → gap_pct = +3.0%  高开
    昨收 10.00 → 今开  9.80 → gap_pct = −2.0%  低开
    昨收 10.00 → 今开 10.01 → gap_pct = +0.1%  基本平开

═══════════════════════════════════

⚙️ 高开阈值 (用户可配, 默认 0.3%)

  |gap_pct| > 阈值 → 判定为"高开"或"低开"
  |gap_pct| ≤ 阈值 → 判定为"平开"

  阈值越大 → 平开越多, 高开/低开越少
  阈值越小 → 高开/低开区分越敏感
""",
            },
            "body": {
                "title": "body_pct — 实体涨跌幅",
                "color": "#1565C0",
                "content": """
body_pct = (今日收盘价 − 今日开盘价) / 今日开盘价 × 100%

═══════════════════════════════════

  正  → 收盘 > 开盘 (阳线, 上影或锤子)
  负  → 收盘 < 开盘 (阴线, 下影或射击之星)
  0   → 收盘 = 开盘 (十字星)

  例:
    开盘 10.00 → 收盘 10.50 → body_pct = +5.0%  大阳线
    开盘 10.00 → 收盘  9.90 → body_pct = −1.0%  小阴线
    开盘 10.00 → 收盘 10.00 → body_pct =  0.0%  十字星

═══════════════════════════════════

💡 body_pct 回答的问题:
   "今天盘中是买盘赢还是卖盘赢？"
   不管高开低开, 只要收盘比开盘高 → 多方胜出 🟢
""",
            },
            "pattern": {
                "title": "pattern — 日走势形态分类逻辑",
                "color": "#2E7D32",
                "content": """
═══════════════════════════════════
  分类公式 (两步判定)
═══════════════════════════════════

  第一步: 看 gap_pct → 判定高开/低开/平开
  第二步: 看 body_pct → 判定高走/低走

═══════════════════════════════════

  gap_pct >  +阈值  → 高开组
    body ≥ 0 → 高开高走 🟢   (跳空向上, 盘中继续涨)
    body < 0 → 高开低走 🔴   (跳空向上, 盘中回落)

  gap_pct <  −阈值  → 低开组
    body ≥ 0 → 低开高走 🟢   (跳空向下, 盘中拉起)
    body < 0 → 低开低走 🔴   (跳空向下, 继续杀跌)

  |gap| ≤ 阈值      → 平开组
    body ≥ 0 → 平走高 🟢     (无跳空, 盘中收阳)
    body < 0 → 平走低 🔴     (无跳空, 盘中收阴)

═══════════════════════════════════
  做 T 实战意义
═══════════════════════════════════

  高开低走 🔴 → 多头试盘失败 → 次日低开概率高 → 尾盘低吸
  低开高走 🟢 → 空头施压被承接 → 次日延续概率高 → 低开买入
  平开多     → 震荡市, 追涨风险大 → 高抛低吸为主
""",
            },
            "next": {
                "title": "next_pct — 次日涨跌幅",
                "color": "#6A1B9A",
                "content": """
next_pct = 次日收盘价 / 当日收盘价 − 1

═══════════════════════════════════

  正  → 今日买入, 次日卖出可盈利
  负  → 今日买入, 次日卖出亏损

═══════════════════════════════════

💡 核心用途: 做 T 时机评估

  统计每种 pattern 出现后, next_pct > 0 的比例 → "次日上涨概率"

  例: 历史上 高开低走 出现 20 次, 次日涨 13 次
      → 高开低走后次日上涨概率 = 65%
      → 做 T 建议: 高开低走日尾盘低吸

  注意: 这是历史统计, 不构成投资建议
""",
            },
        }

        info = helps.get(topic, {"title": "帮助", "color": "#333", "content": ""})

        header = tk.Frame(help_win, bg=info["color"], height=44)
        header.pack(fill=tk.X)
        tk.Label(header, text=f"❓ {info['title']}",
                 font=("", 12, "bold"), bg=info["color"], fg="white",
                 pady=10).pack(side=tk.LEFT, padx=14)

        body = tk.LabelFrame(help_win, text="", bg="#FFFDE7", fg="#333")
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        tk.Label(body, text=info["content"], bg="#FFFDE7", fg="#212121",
                 font=("Menlo", 10), justify="left", anchor="w",
                 padx=10, pady=10).pack(fill=tk.BOTH, expand=True)

        tk.Button(help_win, text="关闭", bg="#333", fg="white",
                  font=("", 10), padx=20, pady=4,
                  command=help_win.destroy).pack(pady=(0, 12))

    # 列定义: (内部key, 显示名, 帮助topic或None, 宽度)
    col_defs = [
        ("date",     "日期",       None,     100),
        ("open",     "开盘价",     None,      80),
        ("close",    "收盘价",     None,      80),
        ("gap_pct",  "gap_pct ❓",  "gap",     90),
        ("body_pct", "body_pct ❓", "body",    90),
        ("pattern",  "形态 ❓",     "pattern", 130),
        ("next_pct", "次日涨跌 ❓", "next",   100),
    ]
    cols2 = tuple(c[0] for c in col_defs)
    tv2 = ttk.Treeview(tab2, columns=cols2, show="headings", height=20)

    # 帮助 topic 映射: key → topic
    col_topic_map = {c[0]: c[2] for c in col_defs}

    for key, disp, topic, w in col_defs:
        tv2.heading(key, text=disp)
        tv2.column(key, width=w, anchor="center")

    # macOS ttk.Treeview heading 的 command= 不生效!
    # 改用 <Button-1> + identify_column() 手动判定
    def _on_tv2_click(event):
        col_id = tv2.identify_column(event.x)  # 返回 "#1", "#2" ...
        try:
            idx = int(col_id.replace("#", "")) - 1
            key = cols2[idx]
            topic = col_topic_map.get(key)
            if topic:
                _show_help(topic)
        except (ValueError, IndexError):
            pass

    tv2.bind("<Button-1>", _on_tv2_click)

    tv2.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    # 底部提示
    hint = tk.Frame(tab2, bg="#E3F2FD")
    hint.pack(fill=tk.X, padx=6, pady=(0, 6))
    tk.Label(hint,
             text="💡 点击带 ❓ 的列标题查看公式与逻辑说明",
             bg="#E3F2FD", fg="#1565C0", font=("", 9)).pack(pady=4)

    # 队列 + worker
    _q = _queue.Queue()
    _stop = threading.Event()

    def _render_complete(df, stats, label_text):
        """主线程渲染结果"""
        try:
            if not win.winfo_exists():
                print("[📊index_pattern] win 已销毁, 跳过渲染", flush=True)
                return
            print(f"[📊index_pattern] 🎨 开始渲染: df={len(df)}行, stats_days={stats.get('total_days','?')}", flush=True)
            win.title(f"📈 指数日走势统计 — {label_text}")
            status_var.set(f"✅ 完成: {label_text} · {stats['total_days']} 天有效数据")
            analyze_btn.config(state="normal")

            # Tab1: 卡片
            for p, (c_lbl, p_lbl, n_lbl) in pattern_cards.items():
                cnt = stats["overall"].get(p, 0)
                total = sum(stats["overall"].values())
                pct = cnt / total * 100 if total > 0 else 0
                c_lbl.config(text=f"{cnt} 天")
                p_lbl.config(text=f"占比 {pct:.1f}%")
                nxt = stats["pattern_next_day"].get(p, {})
                if nxt:
                    up = nxt.get("up_rate", 0)
                    avg = nxt.get("avg_next_pct", 0)
                    n_lbl.config(text=f"次日涨 {up}% 均{avg:+.2f}%",
                                 fg="#2E7D32" if avg > 0 else "#C62828")
                else:
                    n_lbl.config(text="数据不足", fg="#94A3B8")

            # Tab1: 窗口表格
            tv.delete(*tv.get_children())
            for w in [5, 10, 20, 30, 60]:
                wc = stats["by_window"].get(w, Counter())
                row = [f"近 {w} 天"]
                for p in pattern_keys:
                    row.append(wc.get(p, 0))
                row.append(sum(wc.values()))
                tv.insert("", tk.END, values=row)

            # Tab1: 建议
            sug_text.config(state="normal")
            sug_text.delete("1.0", tk.END)
            sug_text.insert(tk.END, f"📊 统计标的: {label_text}\n")
            sug_text.insert(tk.END, f"📅 数据区间: {str(df['date'].iloc[0])[:10]} ~ {str(df['date'].iloc[-1])[:10]} "
                                    f"({stats['total_days']} 个交易日)\n")
            sug_text.insert(tk.END, f"📈 高开阈值: {gap_var.get()}%\n")
            sug_text.insert(tk.END, "═" * 50 + "\n\n")
            for i, s in enumerate(stats["suggestions"], 1):
                sug_text.insert(tk.END, f"{i}. {s}\n\n")
            sug_text.config(state="disabled")

            # Tab2: 每日明细
            tv2.delete(*tv2.get_children())
            tail_days = int(win_var.get().replace("天", ""))
            show_df = df.tail(tail_days).reset_index(drop=True)
            for _, r in show_df.iterrows():
                nxt = r.get("next_pct", None)
                nxt_str = f"{nxt * 100:+.2f}%" if nxt and nxt == nxt else "—"
                vals = (str(r["date"])[:10],
                        f"{r['open']:.2f}", f"{r['close']:.2f}",
                        f"{r['gap_pct']:+.2f}%", f"{r['body_pct']:+.2f}%",
                        r["pattern"], nxt_str)
                row_id = tv2.insert("", tk.END, values=vals)
                if "🟢" in str(r["pattern"]):
                    tv2.tag_configure("up", background="#E8F5E9")
                    tv2.item(row_id, tags=("up",))
                elif "🔴" in str(r["pattern"]):
                    tv2.tag_configure("down", background="#FFEBEE")
                    tv2.item(row_id, tags=("down",))
            print(f"[📊index_pattern] ✅ 渲染完成: {len(show_df)}行明细", flush=True)
        except Exception as _e:
            import traceback; traceback.print_exc()
            print(f"[📊index_pattern] ❌ 渲染失败: {_e}", flush=True)

    def _poll():
        try:
            while True:
                msg = _q.get_nowait()
                print(f"[📊index_pattern] _poll 收到 msg[0]={msg[0]}", flush=True)
                if msg[0] == "progress":
                    status_var.set(msg[1])
                elif msg[0] == "done":
                    df, stats, label = msg[1], msg[2], msg[3]
                    print(f"[📊index_pattern] ✅ done: df={len(df)}行, label={label}", flush=True)
                    _predict_store["df"] = df.copy()  # 🆕 存推断用 df
                    try:
                        if "(" in label and label.endswith(")"):
                            _predict_store["name"] = label.rsplit("(", 1)[0]
                            _predict_store["code"] = label.rsplit("(", 1)[1][:-1]
                    except Exception:
                        pass
                    _render_complete(df, stats, label)
                    analyze_btn.config(state="normal")
                    return
                elif msg[0] == "error":
                    print(f"[📊index_pattern] ❌ error: {msg[1]}", flush=True)
                    status_var.set(f"❌ {msg[1]}")
                    analyze_btn.config(state="normal"); predict_btn.config(state="normal")
                    return
                elif msg[0] == "predict_done":
                    result = msg[1]
                    print(f"[📊index_pattern] 🔮 predict_done: best={result.get('best')}", flush=True)
                    predict_btn.config(state="normal")
                    status_var.set("🔮 推断完成")
                    _show_predict_result(result)
                    return
                elif msg[0] == "predict_error":
                    print(f"[📊index_pattern] ❌ predict_error: {msg[1]}", flush=True)
                    predict_btn.config(state="normal")
                    status_var.set(f"❌ 推断失败: {msg[1]}")
                    return
                elif msg[0] == "review_done":
                    result = msg[1]
                    print(f"[📊index_pattern] 🔙 review_done: hit_top1={result.get('hit_top1')}", flush=True)
                    review_btn.config(state="normal")
                    status_var.set("🔙 回看完成")
                    _show_review_result(result)
                    return
                elif msg[0] == "review_error":
                    print(f"[📊index_pattern] ❌ review_error: {msg[1]}", flush=True)
                    review_btn.config(state="normal")
                    status_var.set(f"❌ 回看失败: {msg[1]}")
                    return
        except _queue.Empty:
            try:
                if win.winfo_exists():
                    win.after(150, _poll)
                else:
                    print("[📊index_pattern] win 已销毁, 停止轮询", flush=True)
            except RuntimeError as _re:
                print(f"[📊index_pattern] ⚠️ main loop 未就绪: {_re}", flush=True)
                try:
                    win.after(500, _poll)
                except Exception:
                    pass

    def _auto_detect_kind(code):
        """根据代码自动判断类型"""
        code = str(code).strip()
        # 指数代码特征
        if code.startswith("000") or code.startswith("399") or code.startswith("899"):
            return "index"
        if code.startswith("0006"):  # 科创50
            return "index"
        # ETF: 51xxxx/52xxxx (沪市) / 15xxxx/16xxxx (深市) / 58xxxx (科创板)
        if code.startswith("51") or code.startswith("52") or code.startswith("15") or code.startswith("16") or code.startswith("58"):
            return "etf"
        # 个股 (60/00/30开头)
        return "stock"

    # 模块级名字→代码缓存 (后台填充)
    _name_code_cache = {}
    _name_code_loaded = False

    def _ensure_name_cache():
        """首次调用时从 AKShare 拉全量名字映射"""
        if _name_code_loaded:
            return
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            # 股票
            for _, row in df.iterrows():
                _name_code_cache[row["名称"]] = row["代码"]
            _name_code_loaded = True
        except Exception:
            pass

    def _lookup_code_by_name(name):
        """名字→代码 (精确→模糊)"""
        if not _name_code_loaded:
            _ensure_name_cache()
        if name in _name_code_cache:
            return _name_code_cache[name]  # 精确
        # 模糊: 名字包含或被包含
        for n, c in _name_code_cache.items():
            if name in n or n in name:
                return c
        return None

    def _parse_selection(sel_text):
        """
        解析用户输入 → (name, code, kind, need_akshare_lookup)
        支持格式:
          1. "🗂 指数 · 上证指数 (000001)"   — 带分类前缀的预设
          2. "上证指数 (000001)"             — 原始预设格式
          3. "💼 持仓 · 贵州茅台 (600519)"   — app注入的持仓/龙头/资讯
          4. "600519" 或 "贵州茅台 600519"    — 纯代码 / 名字+代码
          5. "贵州茅台"                      — 纯名字 (需AKShare查询)
        """
        sel = sel_text.strip()

        # 统一正则: 提取末尾的 "名称 (6位代码)" 格式
        # 允许前面有 emoji 和分类前缀
        m = re.search(r"(.+?)\s*\((\d{6})\)\s*$", sel)
        if m:
            full_name_with_prefix = m.group(1).strip()
            code = m.group(2)
            # 去掉前缀 emoji 和 "xxx · " 部分
            # 例: "💼 持仓 · 贵州茅台" → "贵州茅台"
            # 例: "🗂 指数 · 上证指数" → "上证指数"
            name = re.sub(r"^[^\s]*\s+[^\s]*\s*·\s*", "", full_name_with_prefix).strip()
            if not name:
                name = full_name_with_prefix

            # 判断 kind — 先看文本标签, 再 fallback 代码特征
            kind = "stock"  # 默认个股
            if "指数" in sel or "🗂" in sel and "指数" in sel:
                kind = "index"
            elif "ETF" in sel:
                kind = "etf"
            elif "个股" in sel or "💼" in sel or "🐉" in sel or "📰" in sel or "🔥" in sel:
                kind = "stock"
            else:
                # 没明确标签才看代码特征
                if code.startswith("399") or code.startswith("899") or code.startswith("000688"):
                    kind = "index"  # 深证/北证/科创50
                elif code.startswith("51") or code.startswith("52") or code.startswith("15") or code.startswith("16") or code.startswith("58"):
                    kind = "etf"
                # 000xxx / 600xxx / 300xxx / 688xxx 都是个股
                else:
                    # 最后查预设确认 (覆盖 000001 这种)
                    for n, c, k in INDEX_PRESETS + ETF_PRESETS:
                        if c == code:
                            kind = k; break
            return name, code, kind, False

        # 2) 纯6位代码
        cm = re.search(r"(\d{6})", sel)
        if cm:
            code = cm.group(1)
            name = sel.replace(code, "").strip(" ·-— \t") or f"标的{code}"
            t = type_var.get()
            if t == "自动":
                kind = _auto_detect_kind(code)
            elif t == "指数":
                kind = "index"
            elif t == "ETF":
                kind = "etf"
            else:
                kind = "stock"
            return name, code, kind, False

        # 3) 纯名字 → 需要 AKShare 查询
        return sel, None, type_var.get(), True

    def _on_analyze():
        # 防重入: 已经在跑就忽略
        if analyze_btn.cget("state") == "disabled":
            return
        analyze_btn.config(state="disabled")

        # ⚠️ 关键修复: tk StringVar 不能在后台线程读!
        # 必须在主线程先全部读出来, 作为普通值传给 worker
        sel_text = combo_var.get()
        gap_th = float(gap_var.get())
        window_days = int(win_var.get().replace("天", ""))

        name, code, kind, need_lookup = _parse_selection(sel_text)

        if code is None and not need_lookup:
            status_var.set("❌ 无法识别标的")
            analyze_btn.config(state="normal"); return

        def _worker():
            nonlocal name, code, kind
            try:
                # 3) 纯名字 → 后台查代码
                if need_lookup:
                    _q.put(("progress", f"🔍 搜索「{name}」的股票代码..."))
                    found_code = _lookup_code_by_name(name)
                    if found_code is None:
                        _q.put(("error", f"找不到「{name}」的代码，请输入6位代码")); return
                    code = found_code
                    # 确定 kind (type_var 的值已经在 _parse_selection 里处理了)
                    _q.put(("progress", f"✅ {name} → {code} ({kind})"))

                _q.put(("progress", f"📥 拉取 {name}({code}) K 线..."))
                full_df = fetch_kline(code, kind=kind, days=300)
                if full_df is None or len(full_df) < 30:
                    _q.put(("error", f"{name}({code}) 数据不足")); return

                work_df = full_df.tail(window_days + 60).copy()
                work_df["next_pct"] = work_df["close"].shift(-1) / work_df["close"] - 1

                _q.put(("progress", "🔍 分析形态分布..."))
                stats = analyze_pattern_stats(work_df, gap_threshold=gap_th)
                if stats is None:
                    _q.put(("error", "分析失败")); return

                full_df["next_pct"] = full_df["close"].shift(-1) / full_df["close"] - 1
                _q.put(("done", full_df, stats, f"{name}({code})"))
            except Exception as e:
                import traceback; traceback.print_exc()
                _q.put(("error", str(e)))

        threading.Thread(target=_worker, daemon=True).start()
        status_var.set("⏳ 启动中...")
        _poll()

    analyze_btn.config(command=_on_analyze)

    # ── 🔮 明日推断 ──
    _predict_store = {"df": None, "code": None, "name": None}

    def _predict_click():
        """🔮 点击推断按钮"""
        if _predict_store["df"] is None:
            status_var.set("⚠️ 请先等统计完再推断 (自动统计中...)")
            return
        predict_btn.config(state="disabled")
        status_var.set("🔮 计算明日形态概率...")
        win.update_idletasks()

        def _pred_worker():
            try:
                result = predict_next_day_pattern(
                    _predict_store["df"],
                    code=_predict_store["code"] or "000001",
                    app=app
                )
                _q.put(("predict_done", result))
            except Exception as e:
                import traceback; traceback.print_exc()
                _q.put(("predict_error", str(e)))

        threading.Thread(target=_pred_worker, daemon=True).start()

    predict_btn.config(command=_predict_click)

    # ── 🔙 今日回看 ──
    def _review_click():
        """🔙 点击今日回看"""
        if _predict_store["df"] is None:
            status_var.set("⚠️ 请先等统计完再回看 (自动统计中...)")
            return
        review_btn.config(state="disabled")
        status_var.set("🔙 对比昨天→今天 推断 vs 实际...")
        win.update_idletasks()

        def _rev_worker():
            try:
                result = predict_today_from_yesterday(
                    _predict_store["df"],
                    code=_predict_store["code"] or "000001",
                    app=app
                )
                _q.put(("review_done", result))
            except Exception as e:
                import traceback; traceback.print_exc()
                _q.put(("review_error", str(e)))

        threading.Thread(target=_rev_worker, daemon=True).start()

    review_btn.config(command=_review_click)

    def _show_review_result(result):
        """🔙 弹出今日回看结果 — 推断 vs 实际 + 模型胜率"""
        dlg = tk.Toplevel(win)
        dlg.title(f"🔙 今日回看 — 昨天→今天 推断 vs 实际")
        dlg.geometry("740x700")
        dlg.configure(bg="#1a1a2e")
        dlg.transient(win)
        dlg.grab_set()

        if not result.get("ok"):
            tk.Label(dlg, text=f"❌ {result.get('error', '回看失败')}",
                     bg="#1a1a2e", fg="#EF5350",
                     font=("", 14)).pack(pady=40)
            return

        # 🎯 标题
        head = tk.Frame(dlg, bg="#1a1a2e")
        head.pack(fill=tk.X, pady=(14, 4))
        tk.Label(head, text=f"🔙 {result['actual_date']} 今日回看",
                 bg="#1a1a2e", fg="#FF8A65",
                 font=("", 16, "bold")).pack()
        tk.Label(head, text=f"用 {result['yesterday_state']['date']} 收盘数据 推断 {result['actual_date']} 走势",
                 bg="#1a1a2e", fg="#78909C", font=("", 10)).pack(pady=(2, 6))

        # ── 📊 三卡对比: 昨天 → 推断 → 实际 ──
        compare = tk.Frame(dlg, bg="#1a1a2e")
        compare.pack(fill=tk.X, padx=14, pady=6)

        # 昨天状态卡
        c1 = tk.Frame(compare, bg="#263238", width=220, highlightbackground="#546E7A", highlightthickness=1)
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        tk.Label(c1, text="📅 昨天 (T-1)", bg="#263238", fg="#90CAF9",
                 font=("", 11, "bold")).pack(pady=(8, 2))
        ys = result["yesterday_state"]
        tk.Label(c1, text=f"收盘: {ys['price']:.0f}", bg="#263238", fg="#E0E0E0",
                 font=("", 14, "bold")).pack()
        tk.Label(c1, text=f"{ys['ret_pct']:+.2f}%  位置{ys['pos_bucket']}",
                 bg="#263238", fg="#B0BEC5", font=("", 10)).pack()
        tk.Label(c1, text=f"量能{ys['vol_bucket']}({ys['vol_ratio']:.1f}x)  动量{ys['mom_bucket']}",
                 bg="#263238", fg="#78909C", font=("", 9)).pack(pady=(0, 8))

        # 箭头
        tk.Label(compare, text="→", bg="#1a1a2e", fg="#FFD54F",
                 font=("", 20, "bold")).pack(side=tk.LEFT, padx=4)

        # 推断卡
        predicted = result["predicted_best"]
        pred_emoji = "🟢" if "高走" in predicted else ("🔴" if "低走" in predicted else "⚪")
        pred_color = "#66BB6A" if "高走" in predicted else ("EF5350" if "低走" in predicted else "#FFD54F")
        c2 = tk.Frame(compare, bg="#263238", width=220, highlightbackground="#7B1FA2", highlightthickness=2)
        c2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        tk.Label(c2, text="🔮 模型推断", bg="#263238", fg="#CE93D8",
                 font=("", 11, "bold")).pack(pady=(8, 2))
        tk.Label(c2, text=f"{pred_emoji} {predicted[:4]}", bg="#263238", fg=pred_color,
                 font=("", 18, "bold")).pack()
        tk.Label(c2, text=f"置信度 {result['confidence']}  胜率 {result['top1_prob']*100:.0f}%",
                 bg="#263238", fg="#B0BEC5", font=("", 10)).pack()
        tk.Label(c2, text=f"相似样本 {result['sim_count']} 个",
                 bg="#263238", fg="#78909C", font=("", 9)).pack(pady=(0, 8))

        tk.Label(compare, text="→", bg="#1a1a2e", fg="#FFD54F",
                 font=("", 20, "bold")).pack(side=tk.LEFT, padx=4)

        # 实际卡
        actual = result["actual_pattern"]
        actual_emoji = "🟢" if "高走" in actual else ("🔴" if "低走" in actual else "⚪")
        actual_color = "#66BB6A" if "高走" in actual else ("EF5350" if "低走" in actual else "#FFD54F")
        hit_color = "#66BB6A" if result["hit_top1"] else "#EF5350"
        hit_text = "✅ 命中!" if result["hit_top1"] else ("🟡 Top3命中" if result["hit_top3"] else "❌ 未命中")
        c3 = tk.Frame(compare, bg="#263238", width=220,
                      highlightbackground=hit_color, highlightthickness=3)
        c3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        tk.Label(c3, text="📌 今天实际", bg="#263238", fg="#FFD54F",
                 font=("", 11, "bold")).pack(pady=(8, 2))
        tk.Label(c3, text=f"{actual_emoji} {actual[:4]}", bg="#263238", fg=actual_color,
                 font=("", 18, "bold")).pack()
        tk.Label(c3, text=f"涨跌 {result['today_ret_pct']:+.2f}%",
                 bg="#263238", fg="#B0BEC5", font=("", 10)).pack()
        tk.Label(c3, text=hit_text,
                 bg="#263238", fg=hit_color, font=("", 12, "bold")).pack(pady=(0, 6))

        # ── 模型评估卡 ──
        ev = tk.Frame(dlg, bg="#1a1a2e")
        ev.pack(fill=tk.X, padx=14, pady=6)

        # 评估指标
        metrics = [
            ("🎯 Top1 命中", "✅" if result["hit_top1"] else "❌", hit_color),
            ("🥉 Top3 命中", "✅" if result["hit_top3"] else "❌", "#66BB6A" if result["hit_top3"] else "#EF5350"),
            ("📈 推断胜率", f"{result['top1_prob']*100:.0f}%", "#FFD54F"),
            ("🎲 实际概率", f"{result['actual_prob']*100:.0f}%", actual_color),
            ("📊 Top3 概率和", f"{result['top3_prob_sum']*100:.0f}%", "#B0BEC5"),
            ("🏛️ 历史条件胜率",
             f"{result['historical_hit_rate']:.1f}%" if result['historical_hit_rate'] is not None else "N/A",
             "#64B5F6"),
        ]
        for i, (k, v, c) in enumerate(metrics):
            cell = tk.Frame(ev, bg="#2d2d4a", highlightbackground="#37474F", highlightthickness=1)
            cell.grid(row=i // 3, column=i % 3, padx=4, pady=4, sticky="nsew")
            ev.grid_columnconfigure(i % 3, weight=1)
            tk.Label(cell, text=k, bg="#2d2d4a", fg="#78909C", font=("", 9)).pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(cell, text=v, bg="#2d2d4a", fg=c, font=("", 14, "bold")).pack(anchor="w", padx=8, pady=(0, 6))

        # ── 因子贡献拆解表 (跟推断弹窗一模一样) ──
        contrib = result.get("factor_contrib", {})
        if contrib:
            fc_fr = tk.LabelFrame(dlg, text="🧩 因子贡献拆解", bg="#1a1a2e", fg="#CE93D8", font=("", 11, "bold"))
            fc_fr.pack(fill=tk.X, padx=14, pady=6)
            pattern_keys_full = [p for p, _ in result["predicted_probs"]]  # 概率排序
            pattern_keys_short = [p[:4] for p in pattern_keys_full]
            factor_names = list(contrib.keys())
            fc_wrap = tk.Frame(fc_fr, bg="#1a1a2e")
            fc_wrap.pack(fill=tk.X, padx=6, pady=4)
            tk.Label(fc_wrap, text="", width=9, bg="#1a1a2e").grid(row=0, column=0)
            for j, pk in enumerate(pattern_keys_short):
                color = "#FFD54F" if pk == predicted[:4] else "#B0BEC5"
                tk.Label(fc_wrap, text=pk, width=8, bg="#1a1a2e", fg=color,
                         font=("", 9, "bold")).grid(row=0, column=j+1)
            row_totals = {j: 0.0 for j in range(len(pattern_keys_short))}
            for i, fn in enumerate(factor_names):
                tk.Label(fc_wrap, text=fn, width=9, bg="#1a1a2e", fg="#A5D6A7",
                         font=("", 9)).grid(row=i+1, column=0, sticky="w")
                for j, pk in enumerate(pattern_keys_full):
                    v = contrib[fn].get(pk, 0.0)
                    row_totals[j] += v
                    if v > 0.001:
                        bg = "#4A148C" if pk == predicted else "#263238"
                        fg = "#FFD54F" if pk == predicted else "#E0E0E0"
                        tk.Label(fc_wrap, text=f"+{v*100:.0f}%", width=8, bg=bg, fg=fg,
                                 font=("", 9, "bold")).grid(row=i+1, column=j+1)
                    else:
                        tk.Label(fc_wrap, text="·", width=8, bg="#1a1a2e", fg="#37474F"
                                 ).grid(row=i+1, column=j+1)
            tk.Label(fc_wrap, text="合计", width=9, bg="#1a1a2e", fg="#FFD54F",
                     font=("", 9, "bold")).grid(row=len(factor_names)+1, column=0, sticky="w")
            for j, pk in enumerate(pattern_keys_full):
                v = row_totals[j]
                bg = "#311B92" if pk == predicted else "#1a1a2e"
                fg = "#FFD54F" if pk == predicted else "#E0E0E0"
                tk.Label(fc_wrap, text=f"{v*100:.0f}%", width=8, bg=bg, fg=fg,
                         font=("", 10, "bold")).grid(row=len(factor_names)+1, column=j+1)

        # ── 实际形态在概率分布的位置 ──
        actual_pos = next((i for i, (p, _) in enumerate(result["predicted_probs"]) if p.startswith(actual[:4])), -1)
        if actual_pos >= 0:
            pos_str = f"第 {actual_pos + 1} 名"
            pos_color = "#66BB6A" if actual_pos < 3 else ("#FFD54F" if actual_pos == 3 else "#EF5350")
        else:
            pos_str = "不在预测列表中"
            pos_color = "#EF5350"

        hint_fr = tk.Frame(dlg, bg="#1a1a2e")
        hint_fr.pack(fill=tk.X, padx=14, pady=(2, 10))
        hints = [
            f"📌 实际形态「{actual[:4]}」在概率分布中排名: {pos_str}  (概率 {result['actual_prob']*100:.1f}%)",
            f"🏛️ 历史回测: 相似状态 {result['sim_count']} 个, 其中次日为「{actual[:4]}」的频率 = {result['historical_hit_rate']:.1f}%",
        ]
        if result["hit_top1"]:
            hints.append(f"🎉 模型推断准确! 相似样本里的 Top1 就是实际发生的形态")
        elif result["hit_top3"]:
            hints.append(f"🟡 模型推断部分准确: 实际在 Top3 内, 但不是最优解")
        else:
            hints.append(f"❌ 模型这次没命中 — 可能受突发消息/板块异动影响 (条件概率本身就是分布, 不是确定性)")
        for h in hints:
            tk.Label(hint_fr, text=h, bg="#1a1a2e", fg="#B0BEC5",
                     font=("", 9), anchor="w").pack(fill=tk.X)

    def _show_predict_result(result):
        """🔮 弹出推断结果窗口"""
        dlg = tk.Toplevel(win)
        dlg.title(f"🔮 明日形态推断 — {_predict_store['name'] or ''}")
        dlg.geometry("720x640")
        dlg.configure(bg="#1a1a2e")
        dlg.transient(win)
        dlg.grab_set()

        # ═══════════════════════════════════════════════════════
        # 🆕 帮助弹窗 — 点击 ❓ 显示详细说明
        # ═══════════════════════════════════════════════════════
        HELP_TEXT = """🔮 明日形态推断 — 完整说明
═══════════════════════════════════════════════════════

❶ 六种形态是什么意思？
───────────────────────
  🟢 = 阳线（收盘 > 开盘，当天买方占优）
  🔴 = 阴线（收盘 < 开盘，当天卖方占优）

  高开  = 今日开盘  > 昨日收盘 + 0.3%
  低开  = 今日开盘  < 昨日收盘 - 0.3%
  平开  = 开盘价在 ±0.3% 以内

  高开高走🟢 / 高开低走🔴
  低开高走🟢 / 低开低走🔴
  平走高🟢   / 平走低🔴

❷ 为什么"大数法则"第一名不是最终结论？
──────────────────────────────────────────────────────
  大数法则只占 40% 权重，是核心但不是全部。
  最终结论 = 6 因子加权评分 归一化 取 argmax。

  举个例子：今天上证指数
  ┌─────────┬──────────┬──────────┬──────────┬─────────┐
  │  形态    │ ①大数法则 │ ②指数位置 │ ③量能  │ ④动量  │
  ├─────────┼──────────┼──────────┼──────────┼─────────┤
  │ 平走高🟢 │ +13.8%   │   +0%    │  +0%    │   +0%   │
  │ 低开低走🔴│  +4.8%   │ +12.0%   │  +0%    │   +0%   │
  └─────────┴──────────┴──────────┴──────────┴─────────┘
  平走高有大数支持，但空头排列（价<MA20<MA60）只给
  低开低走打 12% 加成 → 低开低走胜出 3%。

❸ 六大因子详解（按权重排序）
──────────────────────────────────────────────────────
  ① 大数法则 · 历史条件概率（权重 40%）
    把今日状态拆 3 维度（位置 高/中/低、量能 缩/平/放、
    动量 上/平/下），在全部 300 天历史里找"相似状态"
    （距离 ≤ 2，约 12% 的日子），统计这些相似日子的
    次日形态分布。越像的样本权重越高。

    ⚠️ 这是最核心的因子，但不保证结论正确。比如今日
    102 个相似状态里平走高占 34%，但低开低走也占 12%。

  ② 指数位置 · MA 多空排列（权重 15%）
    价 > MA20 > MA60 → 多头排列 → 高开高走 +12%, 平走高 +3%
    价 < MA20 < MA60 → 空头排列 → 低开低走 +12%, 高开低走 +3%
    MA20 < 价 < MA60 → 反弹期 → 平走高 +8%, 低开高走 +7%
    价 < MA20 但 > MA60 → 回踩期 → 高开低走 +7%, 平走低 +8%

  ③ 量能 · 相对均量（权重 15%）
    今日量 / 60 日均量 > 1.5 倍（天量）
      今日涨 → 高开高走 +10%, 高开低走 +5%（情绪延续）
      今日跌 → 低开高走 +10%, 平走高 +5%（恐慌出清反弹）
    < 0.6 倍（地量）→ 低开高走 +8%, 平走高 +7%（变盘信号）

  ④ MA5 动量斜率（权重 10%）
    MA5 最近 5 天 vs 再往前 5 天
    斜率 > +0.5% → 高开高走 +7%, 平走高 +3%
    斜率 < -0.5% → 低开低走 +7%, 高开低走 +3%

  ⑤ 情绪 · 涨跌家数（权重 10%）
    实时 up/(up+down)
    > 65% 上涨 → 高开高走 +6%, 平走高 +4%
    < 35% 上涨 → 低开低走 +6%, 高开低走 +4%
    拿不到数据 → 跳过

  ⑥ 实时大盘涨跌（辅助）
    上证实时 pct > +1.5% → 高开高走 +5%
    上证实时 pct < -1.5% → 低开低走 +5%

❹ 置信度是怎么来的？
──────────────────────────────────────────────────────
  把各因子的得分加起来归一化得到 6 种形态的概率。
  最高那个概率就是胜率。

  ≥ 30% → 高置信度（多因子同向共振，值得重视）
  ≥ 22% → 中置信度（有因子支持但有分歧）
  < 22% → 低置信度（形态模糊，6 种都差不多）

❺ 如何使用推断结果？
──────────────────────────────────────────────────────
  ✅ 置信度高 + 多个因子共振 → 可以做盘前预案
  ✅ 大数法则 vs 指数位置冲突 → 以位置因子为准
  ✅ 情绪因子拿不到 → 降低 10% 可信度
  ❌ 低置信度 → 不做任何预判，等开盘 15 分钟再看

❻ 局限性（必读！）
──────────────────────────────────────────────────────
  ⚠️ 这是条件概率推断，不是确定性预测
  ⚠️ 没有考虑：美联储加息、IPO 密集、节假日效应
  ⚠️ 相似样本 ≥ 5 个才可信，否则降级用整体分布
  ⚠️ 回测验证：相似状态胜率 ≈ 28%（A股整体水平）
  ⚠️ 股市有风险，下注需谨慎！

═══════════════════════════════════════════════════════
数据源：新浪日线(300天) + 新浪实时 + app 实例方法"""

        def _open_help():
            """弹出帮助说明 (带字体调节 + 背景色)"""
            hd = tk.Toplevel(dlg)
            hd.title("❓ 帮助 · 推断说明")
            hd.geometry("780x620")
            hd.configure(bg="#ECEFF1")
            hd.transient(dlg)
            hd.grab_set()

            # 字体状态
            _fs = [13]  # 列表存可变字体大小
            _bg = ["#FFFFFF"]
            _fg = ["#1A1A2E"]

            def _apply_font():
                try:
                    st.configure(font=("", _fs[0]))
                except Exception:
                    pass

            # 工具栏: A-/A+ + 背景色
            bar = tk.Frame(hd, bg="#CFD8DC", height=32)
            bar.pack(fill=tk.X)

            tk.Label(bar, text="帮助说明字体:", bg="#CFD8DC",
                     fg="#1A1A2E", font=("", 10)).pack(side=tk.LEFT, padx=8)

            tk.Button(bar, text="A-", width=3,
                      bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
                      highlightbackground="#546E7A", highlightthickness=1,
                      font=("", 10, "bold"),
                      command=lambda: (_fs.__setitem__(0, max(9, _fs[0] - 1)), _apply_font())
                      ).pack(side=tk.LEFT, padx=2)

            tk.Button(bar, text="A+", width=3,
                      bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
                      highlightbackground="#546E7A", highlightthickness=1,
                      font=("", 10, "bold"),
                      command=lambda: (_fs.__setitem__(0, min(24, _fs[0] + 1)), _apply_font())
                      ).pack(side=tk.LEFT, padx=2)

            tk.Label(bar, text=f"({_fs[0]}pt)", bg="#CFD8DC", fg="#37474F",
                     font=("", 9)).pack(side=tk.LEFT, padx=2)

            # 背景色
            tk.Label(bar, text=" 背景:", bg="#CFD8DC", fg="#1A1A2E",
                     font=("", 10)).pack(side=tk.LEFT, padx=(14, 2))
            for col, name in [("#FFFFFF", "白"), ("#F5F5F5", "浅灰"),
                              ("#FFFDE7", "米黄"), ("#E3F2FD", "浅蓝"),
                              ("#1A1A2E", "深色")]:
                def _set_bg(c=col):
                    _bg[0] = c
                    _fg[0] = "#ECEFF1" if c == "#1A1A2E" else "#1A1A2E"
                    try:
                        st.configure(bg=_bg[0], fg=_fg[0])
                        hd.configure(bg=_bg[0])
                    except Exception:
                        pass
                tk.Button(bar, text=name, width=3,
                          bg=col, fg="#1A1A2E" if col != "#1A1A2E" else "#FFFFFF",
                          activebackground=col,
                          highlightbackground="#546E7A", highlightthickness=1,
                          font=("", 9), command=_set_bg
                          ).pack(side=tk.LEFT, padx=1)

            # 滚动文本
            txt_frame = tk.Frame(hd, bg=_bg[0])
            txt_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

            sb = tk.Scrollbar(txt_frame)
            sb.pack(side=tk.RIGHT, fill=tk.Y)

            st = tk.Text(txt_frame, wrap="word", bg=_bg[0], fg=_fg[0],
                         font=("", _fs[0]), borderwidth=0, padx=16, pady=12,
                         yscrollcommand=sb.set)
            st.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.config(command=st.yview)

            st.insert(tk.END, HELP_TEXT)
            st.configure(state="disabled")

        # 🎯 标题行 — 加 ❓ 按钮
        head = tk.Frame(dlg, bg="#1a1a2e")
        head.pack(fill=tk.X, pady=(14, 6))
        tk.Label(head, text="🔮 明日开盘形态推断",
                 bg="#1a1a2e", fg="#FFD54F",
                 font=("", 16, "bold")).pack(side=tk.LEFT, padx=(14, 4))
        tk.Button(head, text="❓", width=3,
                  bg="#FFFFFF", fg="black", activebackground="#FFF9C4",
                  highlightbackground="#FFD54F", highlightthickness=2,
                  font=("", 12, "bold"), cursor="hand2",
                  command=_open_help).pack(side=tk.LEFT, padx=4)
        tk.Label(head, text="点此查看详细说明",
                 bg="#1a1a2e", fg="#78909C", font=("", 9)).pack(side=tk.LEFT)

        # 🎯 大结论
        concl = tk.Frame(dlg, bg="#2d2d4a", highlightbackground="#7B1FA2", highlightthickness=2)
        concl.pack(fill=tk.X, padx=14, pady=8)
        emoji = "🟢" if "高走" in best else ("🔴" if "低走" in best else "⚪")
        color = "#66BB6A" if "高走" in best else ("#EF5350" if "低走" in best else "#FFD54F")
        tk.Label(concl, text=f"{emoji} {best[:4]}", bg="#2d2d4a", fg=color,
                 font=("", 28, "bold")).pack(pady=(10, 0))
        tk.Label(concl, text=f"置信度: {conf}  ·  胜率 {probs[0][1]*100:.0f}%",
                 bg="#2d2d4a", fg="#B0BEC5", font=("", 12)).pack(pady=(0, 10))

        # 📊 概率分布条形图
        bar_fr = tk.LabelFrame(dlg, text="📊 6种形态概率分布", bg="#1a1a2e", fg="#FFD54F", font=("", 11, "bold"))
        bar_fr.pack(fill=tk.X, padx=14, pady=8)
        max_p = probs[0][1] if probs else 0.3
        for pattern, prob in probs:
            row = tk.Frame(bar_fr, bg="#1a1a2e")
            row.pack(fill=tk.X, padx=10, pady=2)
            tk.Label(row, text=pattern[:4], width=8, bg="#1a1a2e", fg="#E0E0E0",
                     font=("", 10)).pack(side=tk.LEFT)
            bar_w = int(prob / max_p * 380) if max_p > 0 else 0
            bar_color = "#7B1FA2" if pattern == best else "#546E7A"
            bar = tk.Frame(row, bg=bar_color, height=18, width=bar_w)
            bar.pack(side=tk.LEFT)
            tk.Label(row, text=f"{prob*100:.1f}%", width=7,
                     bg="#1a1a2e", fg="#FFD54F" if pattern == best else "#B0BEC5",
                     font=("", 10, "bold")).pack(side=tk.LEFT, padx=6)

        # 🧩 因子贡献拆解表 — 让用户看清为什么是这个结论
        contrib = result.get("factor_contrib", {})
        if contrib:
            fc_fr = tk.LabelFrame(dlg, text="🧩 因子贡献拆解 (每个因子给每个形态的加分)",
                                   bg="#1a1a2e", fg="#CE93D8", font=("", 11, "bold"))
            fc_fr.pack(fill=tk.X, padx=14, pady=6)

            # 表头 + 网格布局
            fc_wrap = tk.Frame(fc_fr, bg="#1a1a2e")
            fc_wrap.pack(fill=tk.X, padx=6, pady=4)

            pattern_keys = [p[:4] for p, _ in probs]  # 用概率分布里的顺序 (从高到低)
            factor_names = list(contrib.keys())

            # 第一格空白
            tk.Label(fc_wrap, text="", width=9, bg="#1a1a2e").grid(row=0, column=0)
            for j, pk in enumerate(pattern_keys):
                color = "#FFD54F" if pk == best[:4] else "#B0BEC5"
                tk.Label(fc_wrap, text=pk, width=8, bg="#1a1a2e", fg=color,
                         font=("", 9, "bold")).grid(row=0, column=j+1)

            # 数据行
            row_totals = {j: 0.0 for j in range(len(pattern_keys))}
            for i, fn in enumerate(factor_names):
                tk.Label(fc_wrap, text=fn, width=9, bg="#1a1a2e", fg="#A5D6A7",
                         font=("", 9)).grid(row=i+1, column=0, sticky="w")
                for j, pk in enumerate(pattern_keys):
                    # 找完整 key
                    full_key = None
                    for k in contrib[fn]:
                        if k.startswith(pk): full_key = k; break
                    v = contrib[fn].get(full_key, 0.0) if full_key else 0.0
                    row_totals[j] += v
                    if v > 0.001:
                        cell_bg = "#4A148C" if pk == best[:4] else "#263238"
                        cell_fg = "#FFD54F" if pk == best[:4] else "#E0E0E0"
                        tk.Label(fc_wrap, text=f"+{v*100:.0f}%", width=8,
                                 bg=cell_bg, fg=cell_fg, font=("", 9, "bold")
                                 ).grid(row=i+1, column=j+1)
                    else:
                        tk.Label(fc_wrap, text="·", width=8, bg="#1a1a2e", fg="#37474F"
                                 ).grid(row=i+1, column=j+1)

            # 合计行
            tk.Label(fc_wrap, text="合计", width=9, bg="#1a1a2e", fg="#FFD54F",
                     font=("", 9, "bold")).grid(row=len(factor_names)+1, column=0, sticky="w")
            for j, pk in enumerate(pattern_keys):
                v = row_totals[j]
                final_fg = "#FFD54F" if pk == best[:4] else "#E0E0E0"
                tk.Label(fc_wrap, text=f"{v*100:.0f}%", width=8,
                         bg="#311B92" if pk == best[:4] else "#1a1a2e",
                         fg=final_fg, font=("", 10, "bold")
                         ).grid(row=len(factor_names)+1, column=j+1)

            # 💡 关键发现行
            fc_hint = tk.Label(fc_fr, text="", bg="#1a1a2e", fg="#90CAF9",
                               font=("", 9), wraplength=680, justify="left")
            # 自动生成对比 hint
            if len(pattern_keys) >= 2:
                top1 = pattern_keys[0]; top2 = pattern_keys[1]
                t1_total = row_totals[0]; t2_total = row_totals[1]
                gap = (t1_total - t2_total) * 100
                # 找出哪个因子贡献了最大差距
                max_gap_factor = ""
                max_gap_val = 0
                for fn in factor_names:
                    full1 = full2 = None
                    for k in contrib[fn]:
                        if k.startswith(top1): full1 = k
                        if k.startswith(top2): full2 = k
                    v1 = contrib[fn].get(full1, 0) if full1 else 0
                    v2 = contrib[fn].get(full2, 0) if full2 else 0
                    if v1 - v2 > max_gap_val:
                        max_gap_val = v1 - v2
                        max_gap_factor = fn
                if gap > 0:
                    fc_hint.config(text=f"💡 {top1} 胜出 {gap:.0f}% 主要来自「{max_gap_factor}」贡献 {max_gap_val*100:.0f}%")
            fc_hint.pack(anchor="w", padx=8, pady=(2, 4))

        # 📍 今日状态
        state_fr = tk.LabelFrame(dlg, text="📍 今日市场状态 (T日)", bg="#1a1a2e", fg="#64B5F6", font=("", 11, "bold"))
        state_fr.pack(fill=tk.X, padx=14, pady=6)
        s = state
        items = [
            ("收盘价", f"{s['price']:.0f}  ({s['ret_pct']:+.2f}%)"),
            ("MA20 / MA60", f"{s['ma20']:.0f} / {s['ma60']:.0f}"),
            ("指数位置", s["pos_bucket"]),
            ("量能", f"{s['vol_bucket']} ({s['vol_ratio']:.1f}x)"),
            ("动量", s["mom_bucket"]),
            ("上证涨跌", f"{s['sh_pct']:+.2f}%"),
            ("情绪", f"{s['sentiment_up']*100:.0f}% 上涨" if s['sentiment_up'] is not None else "N/A"),
        ]
        for i, (k, v) in enumerate(items):
            r = i // 3; c = i % 3
            cell = tk.Frame(state_fr, bg="#1a1a2e")
            cell.grid(row=r, column=c, padx=10, pady=4, sticky="w")
            state_fr.grid_columnconfigure(c, weight=1)
            tk.Label(cell, text=k, bg="#1a1a2e", fg="#78909C",
                     font=("", 9)).pack(anchor="w")
            tk.Label(cell, text=v, bg="#1a1a2e", fg="#E0E0E0",
                     font=("", 11, "bold")).pack(anchor="w")

        # 📋 因子分析
        reason_fr = tk.LabelFrame(dlg, text="📋 因子分析 (按权重排列)", bg="#1a1a2e", fg="#A5D6A7", font=("", 11, "bold"))
        reason_fr.pack(fill=tk.BOTH, expand=True, padx=14, pady=6)
        text = tk.Text(reason_fr, bg="#0d0d1a", fg="#E0E0E0", font=("", 10),
                      height=10, wrap="word", borderwidth=0, padx=10, pady=8)
        sb = tk.Scrollbar(reason_fr, command=text.yview)
        text.configure(yscrollcommand=sb.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        for r in reasons:
            text.insert(tk.END, r + "\n\n")
        text.configure(state="disabled")

        # 底部
        tip = tk.Label(dlg,
                       text="⚠️ 推断仅供参考, 股市有风险, 下注需谨慎  |  回测验证: 相似状态胜率",
                       bg="#1a1a2e", fg="#78909C", font=("", 9))
        tip.pack(pady=4)

    # 下拉框切换 → 自动重跑 (macOS ttk.Combobox 用 <<ComboboxSelected>>)
    cb.bind("<<ComboboxSelected>>", lambda e: _on_analyze())
    gap_cb.bind("<<ComboboxSelected>>", lambda e: _on_analyze())
    win_cb.bind("<<ComboboxSelected>>", lambda e: _on_analyze())

    # 自动跑一次 (默认选中项) — 延迟到 mainloop 稳定后
    try:
        win.after(500, _on_analyze)
    except RuntimeError:
        try:
            win.after(1000, _on_analyze)
        except Exception:
            pass

    return win
