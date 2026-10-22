"""
🪙 筹码分析器 — 筹码分布 + 量价资金痕迹分析

核心理念 (参照视频文稿):
  技术分析看历史价格规律预测未来 (胜率随周期缩短而降低)
  资金分析看对方手里还有多少筹码 — "知道他要买, 跟着买就行"

筹码分析维度:
  1. 筹码分布 (成交量加权 → 简化版 CYQ)
     - 90%/70% 成本区宽度 → 集中 vs 发散
     - 获利盘比例 → 套牢盘 vs 获利盘
     - 平均成本 vs 当前价 → 吸筹区 vs 派发区
     - 密集峰位置 → 支撑 vs 阻力
  2. 量价资金痕迹
     - 换手率 (量比) → 活跃/地量/放量出货
     - 量价背离 → 涨缩量/跌放量 = 动力衰竭
     - OBV 趋势 → 能量潮累积
     - 主力行为 → 底部缩量吸筹 / 高位放量滞涨出货
  3. 筹码打分 + 历史回测

每行: [股票信息] [筹码分数条] [🟢吸筹/🔴派发信号] [回测] [❓]
双击日K → 嵌日K + 可移动筹码浮窗
"""
import matplotlib
# 🆕 Mac 中文字体优先: PingFang SC / Heiti SC / STHeiti
matplotlib.rcParams["font.sans-serif"] = [
    "PingFang SC", "Heiti SC", "STHeiti", "Hiragino Sans GB",
    "Arial Unicode MS", "SimHei", "Microsoft YaHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
import json
import os
import ssl
import threading
import urllib.request
from datetime import datetime

import numpy as np

# 复用 tab_jianlou 的颜色/数据获取工具
from ui.tab_jianlou import (
    _BG_DEEP, _BG_PANEL, _BG_CARD, _BG_TOOLBAR,
    _FG_RED, _FG_GREEN, _FG_GOLD, _FG_BLUE, _FG_CYAN,
    _FG_TEXT, _FG_DIM, _FG_ORANGE, _FG_PURPLE, _FG_PINK,
    _fetch_kline_sina, _fetch_hq_batch, _load_watchlist, _c6_to_sina,
    _compute_scores,
)


# ═══════════════════════════════════════════════════════════
#  筹码分布核心 — 简化版 CYQ
# ═══════════════════════════════════════════════════════════

def _build_chip_distribution(closes, volumes, highs=None, lows=None, n_bins=60, decay=0.95):
    """
    简化版筹码分布 — 把历史每根K线的成交量, 按当日价格区间加权投入价格 bins.
    
    每个 bin 代表一个价格区间的筹码量.
    decay 让远期筹码衰减 (默认 5%/日), 越近的筹码权重越高.
    
    返回: (bin_centers, chip_amounts, total_chips)
    """
    N = len(closes)
    if N < 30:
        return None, None, 0.0

    lo = np.min(closes) * 0.95
    hi = np.max(closes) * 1.05
    if hi <= lo:
        return None, None, 0.0

    bin_edges = np.linspace(lo, hi, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    bin_w = bin_edges[1] - bin_edges[0]
    chips = np.zeros(n_bins)

    for i in range(N):
        vol = volumes[i]
        if vol <= 0:
            continue
        # 衰减: 越近的K线, 筹码越"活"
        age = N - 1 - i
        w = decay ** min(age, 60)  # 60天后衰减到 0.95^60 ≈ 0.05
        vol_w = vol * w

        c = closes[i]
        h = highs[i] if highs is not None else c
        l = lows[i] if lows is not None else c

        # 把成交量在 [l, h] 区间均匀分布, 然后投入各 bin
        # 简化: 假设集中在 close, 按 h-l 宽度均匀撒
        if h > l and bin_w > 0:
            # 覆盖区间内的每个 bin 分到一份
            idx_lo = int(max(0, (l - lo) / bin_w))
            idx_hi = int(min(n_bins - 1, (h - lo) / bin_w))
            n_cov = idx_hi - idx_lo + 1
            if n_cov > 0:
                per_bin = vol_w / n_cov
                for bi in range(idx_lo, idx_hi + 1):
                    chips[bi] += per_bin
            else:
                # close 在边界外, 强行投一个
                idx_c = int(np.clip((c - lo) / bin_w, 0, n_bins - 1))
                chips[idx_c] += vol_w
        else:
            idx_c = int(np.clip((c - lo) / bin_w, 0, n_bins - 1))
            chips[idx_c] += vol_w

    total = chips.sum()
    if total > 0:
        chips = chips / total  # 归一化为百分比
    return bin_centers, chips, total


def _chip_metrics(bin_centers, chips, cur_price):
    """
    从筹码分布里提取核心指标.
    
    返回 dict:
      avg_cost       平均成本 (筹码加权平均价)
      profit_ratio   获利盘比例 (cur_price 以下的筹码%)
      band90_lo/hi   90% 成本区 (去掉最低/最高 5%)
      band70_lo/hi   70% 成本区 (去掉最低/最高 15%)
      band90_width   90% 成本区宽度 (相对 avg_cost 的百分比)
      band70_width   70% 成本区宽度
      peak_price     筹码峰所在价 (筹码最密集处)
      peak_amount    峰的筹码量 (该 bin 占比)
      is_concentrated 是否集中 (band90_width < 15%)
      cur_position   当前价相对峰的位置 ('above' / 'below' / 'at')
    """
    out = {
        "avg_cost": cur_price, "profit_ratio": 50.0,
        "band90_lo": cur_price, "band90_hi": cur_price, "band90_width": 0.0,
        "band70_lo": cur_price, "band70_hi": cur_price, "band70_width": 0.0,
        "peak_price": cur_price, "peak_amount": 0.0,
        "is_concentrated": False, "cur_position": "at",
    }
    if bin_centers is None or chips is None or chips.sum() == 0:
        return out

    # 平均成本 (加权)
    avg_cost = float(np.average(bin_centers, weights=chips))

    # 获利盘比例 (累计到 cur_price)
    cum = np.cumsum(chips)
    profit_ratio = float(np.interp(cur_price, bin_centers, cum) * 100)
    profit_ratio = max(0.0, min(100.0, profit_ratio))

    # 90% 成本区 (P5 ~ P95)
    lo90 = float(np.interp(0.05, cum, bin_centers))
    hi90 = float(np.interp(0.95, cum, bin_centers))
    w90 = (hi90 - lo90) / avg_cost * 100 if avg_cost > 0 else 0

    # 70% 成本区 (P15 ~ P85)
    lo70 = float(np.interp(0.15, cum, bin_centers))
    hi70 = float(np.interp(0.85, cum, bin_centers))
    w70 = (hi70 - lo70) / avg_cost * 100 if avg_cost > 0 else 0

    # 筹码峰 (最密集处)
    peak_idx = int(np.argmax(chips))
    peak_price = float(bin_centers[peak_idx])
    peak_amount = float(chips[peak_idx] * 100)

    # 当前价相对峰位置
    if cur_price > peak_price * 1.02:
        pos = "above"
    elif cur_price < peak_price * 0.98:
        pos = "below"
    else:
        pos = "at"

    out.update({
        "avg_cost": round(avg_cost, 2),
        "profit_ratio": round(profit_ratio, 1),
        "band90_lo": round(lo90, 2), "band90_hi": round(hi90, 2),
        "band90_width": round(w90, 1),
        "band70_lo": round(lo70, 2), "band70_hi": round(hi70, 2),
        "band70_width": round(w70, 1),
        "peak_price": round(peak_price, 2),
        "peak_amount": round(peak_amount, 1),
        "is_concentrated": w90 < 15,
        "cur_position": pos,
    })
    return out


def _obv(closes, volumes):
    """能量潮 OBV — 累积量能, 量价配合度"""
    N = len(closes)
    out = np.zeros(N)
    for i in range(1, N):
        if closes[i] > closes[i - 1]:
            out[i] = out[i - 1] + volumes[i]
        elif closes[i] < closes[i - 1]:
            out[i] = out[i - 1] - volumes[i]
        else:
            out[i] = out[i - 1]
    return out


# ═══════════════════════════════════════════════════════════
#  筹码 + 量价资金 信号检测
# ═══════════════════════════════════════════════════════════

def _ma(arr, n):
    if len(arr) < n:
        return np.full(len(arr), np.nan)
    out = np.full(len(arr), np.nan)
    for i in range(n - 1, len(arr)):
        out[i] = arr[i - n + 1:i + 1].mean()
    return out


def _detect_capital_signals(opens, highs, lows, closes, volumes):
    """
    筹码+量价资金 综合信号检测.
    
    返回: list of {type: 'accumulate'|'distribute', label, strength, reason, chip_metrics}
    
    type 定义:
      accumulate = 吸筹/筹码集中/有望上涨 (对应机会扫描器里的 'buy')
      distribute = 派发/筹码发散/警惕下跌 (对应机会扫描器里的 'sell')
    """
    signals = []
    N = len(closes)
    if N < 30:
        return signals

    cur = N - 1
    cur_price = closes[cur]

    # ── 筹码分布 ──
    bins, chips, _ = _build_chip_distribution(closes, volumes, highs, lows, n_bins=60)
    cm = _chip_metrics(bins, chips, cur_price)

    # ── 基础指标 ──
    ma5 = _ma(closes, 5)
    ma20 = _ma(closes, 20)
    ma60 = _ma(closes, 60)
    vol_ma5 = _ma(volumes.astype(float), 5)
    vol_ma20 = _ma(volumes.astype(float), 20)
    obv = _obv(closes, volumes)

    # ── 1. 筹码集中 (单峰密集) + 获利盘低 = 底部吸筹 ──
    if cm["is_concentrated"] and cm["profit_ratio"] < 20:
        # 价格在筹码峰下方/附近 → 套牢盘少, 机构成本集中
        signals.append({
            "type": "accumulate", "label": "底部单峰密集", "strength": 3,
            "reason": f"90%成本区宽度 {cm['band90_width']:.1f}% (集中), "
                      f"获利盘仅 {cm['profit_ratio']:.1f}%, "
                      f"平均成本 {cm['avg_cost']:.2f}, 筹码峰在 {cm['peak_price']:.2f}.\n"
                      f"经典底部吸筹形态: 机构在低位完成筹码收集, "
                      f"一旦放量突破成本区上沿 ({cm['band90_hi']:.2f}), "
                      f"大概率开启主升浪 (历史胜率 ~65%).",
            "chip_metrics": cm, "idx": cur,
        })

    # ── 2. 筹码集中 + 刚突破成本区上沿 = 突破吸筹 ──
    if cm["is_concentrated"] and cur_price > cm["band90_hi"]:
        # 成交量也要放大
        vol_ratio = volumes[cur] / vol_ma5[cur] if not np.isnan(vol_ma5[cur]) and vol_ma5[cur] > 0 else 1
        if vol_ratio > 1.3:
            signals.append({
                "type": "accumulate", "label": "突破筹码密集区", "strength": 3,
                "reason": f"股价刚放量突破 90% 成本区上沿 {cm['band90_hi']:.2f}, "
                          f"量比 {vol_ratio:.1f}x, 筹码集中 (宽度 {cm['band90_width']:.1f}%).\n"
                          f"这是筹码理论最经典的主升浪启动信号: "
                          f"机构吸筹完毕后第一波拉升, 利润空间通常 >20%.",
                "chip_metrics": cm, "idx": cur,
            })

    # ── 3. 筹码发散 (高位多峰) + 获利盘高 = 顶部派发 ──
    if not cm["is_concentrated"] and cm["profit_ratio"] > 70 and cur_price > cm["avg_cost"] * 1.1:
        signals.append({
            "type": "distribute", "label": "高位筹码发散", "strength": 3,
            "reason": f"90%成本区宽度 {cm['band90_width']:.1f}% (严重发散), "
                      f"获利盘 {cm['profit_ratio']:.1f}%, "
                      f"当前价 {cur_price:.2f} 远高于平均成本 {cm['avg_cost']:.2f}.\n"
                      f"机构高位派发典型特征: 筹码从集中变发散, "
                      f"散户在高位接盘, 后续大概率下跌 >15%.",
            "chip_metrics": cm, "idx": cur,
        })

    # ── 4. 获利盘 > 90% + 换手率飙升 = 出货 ──
    vol_ratio_cur = volumes[cur] / vol_ma20[cur] if not np.isnan(vol_ma20[cur]) and vol_ma20[cur] > 0 else 1
    if cm["profit_ratio"] > 85 and vol_ratio_cur > 2.0:
        signals.append({
            "type": "distribute", "label": "获利盘暴增+放量", "strength": 2,
            "reason": f"获利盘已达 {cm['profit_ratio']:.1f}% (绝大多数持仓者获利), "
                      f"量比 {vol_ratio_cur:.1f}x (显著放量).\n"
                      f"这是典型的机构出货信号: 散户亢奋接盘, 机构趁机派发.",
            "chip_metrics": cm, "idx": cur,
        })

    # ── 5. 量价背离 (价格新高但 OBV/量能没新高) ──
    if cur >= 40:
        # 看最近 20 天有没有价格新高
        lookback = 20
        price_high_20 = np.max(closes[cur - lookback:cur + 1])
        price_high_prev = np.max(closes[cur - lookback:cur])
        obv_high_20 = np.max(obv[cur - lookback:cur + 1])
        obv_high_prev = np.max(obv[cur - lookback:cur])

        # 顶背离: 价格新高但 OBV 没新高 (量能不支持)
        if closes[cur] >= price_high_prev and obv[cur] < obv_high_prev * 0.95:
            signals.append({
                "type": "distribute", "label": "顶背离 (量能枯竭)", "strength": 2,
                "reason": f"价格在 {cur_price:.2f} 创近期新高, "
                          f"但 OBV 能量潮没同步创新高.\n"
                          f"机构出货的经典信号: 用少量资金拉价格掩护出货, "
                          f"量能跟不上意味着上涨没有资金基础, 大概率即将回落.",
                "chip_metrics": cm, "idx": cur,
            })
        # 底背离: 价格新低但 OBV 没新低
        elif closes[cur] <= np.min(closes[cur - lookback:cur]) and obv[cur] > np.min(obv[cur - lookback:cur]) * 0.95:
            signals.append({
                "type": "accumulate", "label": "底背离 (资金承接)", "strength": 2,
                "reason": f"价格在 {cur_price:.2f} 创近期新低, "
                          f"但 OBV 能量潮没同步创新低.\n"
                          f"底部吸筹信号: 机构在下跌中悄悄承接筹码, "
                          f"抛压衰竭, 反弹一触即发.",
                "chip_metrics": cm, "idx": cur,
            })

    # ── 6. 换手率/量比地量 = 变盘前兆 ──
    if cur >= 20:
        vol_ratio_5 = volumes[cur] / vol_ma20[cur] if not np.isnan(vol_ma20[cur]) and vol_ma20[cur] > 0 else 1
        # 连续 3 天地量
        recent_vols = volumes[max(0, cur - 2):cur + 1]
        recent_vols_ma5 = vol_ma20[cur - 2:cur + 1]
        if all(recent_vols[i] < recent_vols_ma5[i] * 0.5 for i in range(3)
               if not np.isnan(recent_vols_ma5[i]) and recent_vols_ma5[i] > 0):
            signals.append({
                "type": "accumulate", "label": "连缩地量 (变盘前兆)", "strength": 2,
                "reason": f"连续 3 天成交量不足 20日均量的 50%, "
                          f"当前量比 {vol_ratio_5:.2f}x.\n"
                          f"地量是变盘前兆 — 82% 的历史大底都伴随地量. "
                          f"机构高度控盘后浮筹已清, 向上突破概率大.",
                "chip_metrics": cm, "idx": cur,
            })

    # ── 7. 换手率飙升 + 高位滞涨 = 出货 ──
    if cur >= 10:
        price_chg_10 = (closes[cur] - closes[cur - 10]) / closes[cur - 10] * 100
        vol_ratio_10_avg = np.mean([volumes[cur - i] / vol_ma20[cur - i]
                                     for i in range(10)
                                     if not np.isnan(vol_ma20[cur - i]) and vol_ma20[cur - i] > 0])
        if vol_ratio_10_avg > 2.0 and price_chg_10 < 3 and cur_price > ma60[cur] * 1.05:
            signals.append({
                "type": "distribute", "label": "高位放量滞涨", "strength": 3,
                "reason": f"近 10 天均量比 {vol_ratio_10_avg:.1f}x (显著放量), "
                          f"但涨幅仅 {price_chg_10:+.1f}%, 股价在 MA60 上方 +5%.\n"
                          f"典型的高位出货形态: 机构大量派发筹码, "
                          f"股价虽然还没大跌但已涨不动了, 后续大概率快速回落.",
                "chip_metrics": cm, "idx": cur,
            })

    # ── 8. 获利盘极低 + 股价在 MA60 下方 = 套牢区, 关注反弹 ──
    if cm["profit_ratio"] < 15 and cur >= 60 and cur_price < ma60[cur]:
        signals.append({
            "type": "accumulate", "label": "深套区 (反弹候选)", "strength": 1,
            "reason": f"获利盘仅 {cm['profit_ratio']:.1f}% (几乎全被套), "
                      f"股价在 MA60 ({ma60[cur]:.2f}) 下方.\n"
                      f"套牢盘密集区往往有强烈的反弹需求, "
                      f"如果后续出现放量突破 MA60, 就是好的抄底时机.",
            "chip_metrics": cm, "idx": cur,
        })

    # ── 9. OBV 金叉 (能量潮上穿均线) ──
    if cur >= 20:
        obv_ma10 = _ma(obv, 10)
        if (not np.isnan(obv_ma10[cur - 1]) and not np.isnan(obv_ma10[cur])
                and obv[cur - 1] < obv_ma10[cur - 1] and obv[cur] >= obv_ma10[cur]):
            signals.append({
                "type": "accumulate", "label": "OBV 能量潮金叉", "strength": 2,
                "reason": "OBV 能量潮上穿 MA10, 量能开始放大, "
                          "资金进场意愿增强. 与技术指标金叉不同的是, "
                          "OBV 直接反映的是多空资金的真实战斗结果.",
                "chip_metrics": cm, "idx": cur,
            })

    # ── 10. 筹码峰上移 = 机构成本上移 (趋势延续) ──
    if cur >= 20:
        _, chips_old, _ = _build_chip_distribution(
            closes[:cur - 10], volumes[:cur - 10],
            highs[:cur - 10], lows[:cur - 10], n_bins=60)
        bins_new, chips_new, _ = _build_chip_distribution(
            closes[cur - 10:], volumes[cur - 10:],
            highs[cur - 10:], lows[cur - 10:], n_bins=60)
        # 简化: 比较最新的 10 天峰价 vs 更早的 (其实上面已经是整体, 改看 band 上移)
        # 用 avg_cost 变化代替
        bins_all, chips_all, _ = _build_chip_distribution(
            closes, volumes, highs, lows, n_bins=60)
        if bins_all is not None and chips_all is not None:
            avg_cost_now = float(np.average(bins_all, weights=chips_all))
            if cur_price > avg_cost_now * 1.08:
                # 当前价远高于筹码加权平均, 说明大部分筹码获利
                # 这个已经被 profit_ratio 捕获了, 不重复发信号
                pass

    return signals


# ═══════════════════════════════════════════════════════════
#  筹码打分表
# ═══════════════════════════════════════════════════════════

_CHIP_SCORE_TABLE = {
    # accumulate / 吸筹
    "底部单峰密集": 18,
    "突破筹码密集区": 18,
    "底背离 (资金承接)": 14,
    "连缩地量 (变盘前兆)": 12,
    "深套区 (反弹候选)": 10,
    "OBV 能量潮金叉": 12,
    # distribute / 派发
    "高位筹码发散": 18,
    "获利盘暴增+放量": 14,
    "顶背离 (量能枯竭)": 14,
    "高位放量滞涨": 16,
}


def _compute_chip_scores(signals):
    """把 accumulate 视为买入侧, distribute 视为卖出侧, 归一化到 100"""
    raw_buy = 0.0   # accumulate
    raw_sell = 0.0  # distribute
    for s in signals:
        base = _CHIP_SCORE_TABLE.get(s["label"].split(" ")[0], 8)
        strength_mult = {1: 0.6, 2: 1.0, 3: 1.5}.get(s.get("strength", 2), 1.0)
        pts = base * strength_mult
        if s["type"] == "accumulate":
            raw_buy += pts
        else:
            raw_sell += pts

    total = raw_buy + raw_sell
    if total == 0:
        return 50, 50, raw_buy, raw_sell
    buy_100 = round(raw_buy / total * 100)
    return buy_100, 100 - buy_100, raw_buy, raw_sell


def _backtest_chip(closes, highs, lows, volumes, signal_type="accumulate", lookback=400):
    """
    历史回测 — 简化版: 用 MA20 位置 + 量比 作为"类似筹码状态"的近似.
    accumulate 触发条件: close < MA20 (超卖区) + vol_ratio < 0.7 (缩量)
    distribute 触发条件: close > MA20*1.08 (高位) + vol_ratio > 1.8 (放量)
    """
    N = len(closes)
    if N < 100:
        return None

    ma20 = _ma(closes, 20)
    vol_ma20 = _ma(volumes.astype(float), 20)
    start = max(21, N - lookback)
    trades = []

    for i in range(start, N - 25):
        if np.isnan(ma20[i]) or np.isnan(vol_ma20[i]) or vol_ma20[i] <= 0:
            continue
        vr = volumes[i] / vol_ma20[i]
        if signal_type == "accumulate":
            if closes[i] < ma20[i] and vr < 0.8:
                trades.append(i)
        else:
            if closes[i] > ma20[i] * 1.08 and vr > 1.8:
                trades.append(i)

    if len(trades) < 5:
        return None

    result = {"count": len(trades)}
    for f in (5, 10, 20):
        rets = []
        for idx in trades:
            if idx + f >= N:
                continue
            ret = (closes[idx + f] - closes[idx]) / closes[idx] * 100
            rets.append(ret)
        if not rets:
            continue
        if signal_type == "accumulate":
            wins = sum(1 for r in rets if r > 0)
        else:
            wins = sum(1 for r in rets if r < 0)
        avg = float(np.mean(rets))
        mdd = float(min(rets))
        result[f"win{f}"] = round(wins / len(rets) * 100)
        result[f"avg{f}"] = round(avg, 2)
        result[f"mdd{f}"] = round(mdd, 2)

    all_rets = []
    for idx in trades:
        if idx + 10 < N:
            all_rets.append((closes[idx + 10] - closes[idx]) / closes[idx] * 100)
    if all_rets:
        if signal_type == "accumulate":
            avg_win = np.mean([r for r in all_rets if r > 0]) if any(r > 0 for r in all_rets) else 0
            avg_loss = abs(np.mean([r for r in all_rets if r < 0])) if any(r < 0 for r in all_rets) else 0.01
        else:
            avg_win = abs(np.mean([r for r in all_rets if r < 0])) if any(r < 0 for r in all_rets) else 0
            avg_loss = np.mean([r for r in all_rets if r > 0]) if any(r > 0 for r in all_rets) else 0.01
        result["profit_loss_ratio"] = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0

    return result


# ═══════════════════════════════════════════════════════════
#  筹码绘制 (在 Figure 上画简化筹码分布柱)
# ═══════════════════════════════════════════════════════════

def _draw_chip_distribution(ax, bin_centers, chips, cur_price=None, cm=None, height_ratio=0.25):
    """
    在某个 matplotlib Axes 上画简化版筹码分布 (水平柱).
    height_ratio: 筹码图占主图高度的比例 (默认 25%).
    """
    if bin_centers is None or chips is None or chips.sum() == 0:
        return
    n = len(bin_centers)
    colors = ["#FF8A80" if chips[i] > np.percentile(chips, 80) else
              "#FFD54F" if chips[i] > np.percentile(chips, 50) else
              "#80DEEA" for i in range(n)]
    bar_heights = chips * 100  # 放大显示
    ax.barh(bin_centers, bar_heights, height=(bin_centers[1] - bin_centers[0]) * 0.8,
            color=colors, edgecolor="", alpha=0.85)

    # 标当前价线
    if cur_price is not None:
        ax.axhline(cur_price, color="#FFD54F", linewidth=1.2, linestyle="--", alpha=0.8)
        ax.text(ax.get_xlim()[1] * 0.95, cur_price,
                f"  ¥{cur_price:.2f}", va="center", color="#FFD54F",
                fontsize=8, fontweight="bold")

    # 标 90% 成本区
    if cm:
        lo, hi = cm["band90_lo"], cm["band90_hi"]
        ax.axhspan(lo, hi, alpha=0.1, color="#90CAF9")
        ax.text(ax.get_xlim()[1] * 0.95, lo, f"90%下限 ¥{lo:.2f}",
                va="bottom", color="#90CAF9", fontsize=7)
        ax.text(ax.get_xlim()[1] * 0.95, hi, f"90%上限 ¥{hi:.2f}",
                va="bottom", color="#90CAF9", fontsize=7)

    ax.set_xlabel("筹码量 %", fontsize=8, color="#888888")
    ax.tick_params(labelsize=8, colors="#888888")


# ═══════════════════════════════════════════════════════════
#  UI 扫描器
# ═══════════════════════════════════════════════════════════

class ChouMaMixin:
    """🪙 筹码分析器 mixin — 和 JianLouMixin 独立"""

    def _show_chouma(self):
        import tkinter as tk
        from tkinter import ttk

        dlg = tk.Toplevel(getattr(self, "win", None) or self.root)
        dlg.title("🪙 筹码分析")
        dlg.geometry("1440x860")
        dlg.configure(bg=_BG_DEEP)

        # ── 顶栏 ──
        top = tk.Frame(dlg, bg=_BG_TOOLBAR, height=42); top.pack(fill=tk.X)
        top.pack_propagate(False)
        tk.Label(top, text="🪙 筹码分析", bg=_BG_TOOLBAR, fg=_FG_GOLD,
                 font=("Menlo", 15, "bold")).pack(side=tk.LEFT, padx=12, pady=6)
        status = tk.Label(top, text="⏳ 准备扫描...", bg=_BG_TOOLBAR, fg=_FG_DIM,
                          font=("Menlo", 12))
        status.pack(side=tk.RIGHT, padx=12)

        scan_btn = tk.Button(top, text="🔄扫描", command=lambda: None,
                             bg=_BG_PANEL, fg=_FG_CYAN, activebackground=_BG_CARD,
                             activeforeground=_FG_CYAN, font=("Menlo", 12, "bold"),
                             relief=tk.FLAT, padx=10, pady=3, cursor="hand2")
        scan_btn.pack(side=tk.LEFT, padx=6, pady=6)

        tk.Label(top, text="  📈 筹码分布 + 量价资金痕迹  🟢吸筹  🔴派发",
                 bg=_BG_TOOLBAR, fg=_FG_DIM, font=("Menlo", 11)).pack(side=tk.LEFT, padx=10)

        # ── 主容器 ──
        main = tk.Frame(dlg, bg=_BG_DEEP); main.pack(fill=tk.BOTH, expand=True)

        # 左侧列表
        left = tk.Frame(main, bg=_BG_DEEP)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 3), pady=6)

        # 右侧K线嵌入
        right = tk.Frame(main, bg=_BG_DEEP, width=600)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(3, 6), pady=6)
        right.pack_propagate(False)

        kline_top = tk.Frame(right, bg=_BG_TOOLBAR, height=30); kline_top.pack(fill=tk.X)
        kline_top.pack_propagate(False)
        kline_title = tk.Label(kline_top, text="📊 点击左侧行查看日K+筹码",
                               bg=_BG_TOOLBAR, fg=_FG_DIM, font=("Menlo", 12))
        kline_title.pack(side=tk.LEFT, padx=10, pady=4)
        embed_frame = tk.Frame(right, bg=_BG_PANEL)
        embed_frame.pack(fill=tk.BOTH, expand=True)

        # ── Notebook ──
        style = ttk.Style()
        try:
            style.theme_use("clam")
            style.configure("TNotebook", background=_BG_DEEP, borderwidth=0)
            style.configure("TNotebook.Tab", background=_BG_PANEL, foreground=_FG_TEXT,
                            padding=(16, 5), font=("Menlo", 13))
            style.map("TNotebook.Tab", background=[("selected", _BG_CARD)],
                      foreground=[("selected", _FG_GOLD)])
        except:
            pass

        nb = ttk.Notebook(left)
        nb.pack(fill=tk.BOTH, expand=True)

        tab_all = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_all, text="📋 全部")
        tab_acc = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_acc, text="🟢 吸筹机会")
        tab_dis = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_dis, text="🔴 派发警告")

        def _make_scrollable(parent):
            cv = tk.Canvas(parent, bg=_BG_DEEP, highlightthickness=0)
            cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=cv.yview)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            cv.configure(yscrollcommand=sb.set)
            inner = tk.Frame(cv, bg=_BG_DEEP)
            cv.create_window((0, 0), window=inner, anchor="nw")
            inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
            cv.bind_all("<MouseWheel>", lambda e: cv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
            return cv, inner

        cv_all, inner_all = _make_scrollable(tab_all)
        cv_acc, inner_acc = _make_scrollable(tab_acc)
        cv_dis, inner_dis = _make_scrollable(tab_dis)

        # ── 筹码浮窗列表 (用于点击新行时关闭旧浮窗) ──
        _active_float_wins = []

        # ── 嵌日K + 筹码浮窗 ──
        def _embed_daily(sina_code, name, buy100=50, sell100=50,
                         bt_acc=None, bt_dis=None, signals=None, tag="",
                         chip_metrics=None, chip_kdata=None):
            import tkinter as tk
            from tkinter import ttk as _ttk
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            # 关旧浮窗
            for fw in _active_float_wins:
                try: fw.destroy()
                except: pass
            _active_float_wins.clear()

            for w in embed_frame.winfo_children():
                w.destroy()
            embed_frame.configure(bg=_BG_DEEP)

            # ═══════════════════════════════════════════════
            # 🆕 周期切换顶栏
            # ═══════════════════════════════════════════════
            _period_var = tk.StringVar(value="day")
            # 日线/60分/1分 → 新浪 scale; 周/月 → 东方财富 klt
            _period_map = {
                "1min":  {"src": "sina", "scale": 1,   "datalen": 240},
                "5min":  {"src": "sina", "scale": 5,   "datalen": 240},
                "15min": {"src": "sina", "scale": 15,  "datalen": 240},
                "30min": {"src": "sina", "scale": 30,  "datalen": 200},
                "60min": {"src": "sina", "scale": 60,  "datalen": 160},
                "day":   {"src": "sina", "scale": 240, "datalen": 120},
                "week":  {"src": "dfm",  "klt": "102", "datalen": 60},
                "month": {"src": "dfm",  "klt": "103", "datalen": 60},
            }

            def _fetch_kline(period, sina_code, datalen):
                """统一拉K线: 日线/分→新浪; 周/月→东方财富"""
                cfg = _period_map.get(period, _period_map["day"])
                if cfg["src"] == "sina":
                    return _fetch_kline_sina(sina_code, scale=cfg["scale"], datalen=datalen)
                else:
                    # 东方财富 klt: 102=周 103=月
                    import requests as _r
                    _prefix = sina_code[:2]; _code6 = sina_code[2:]
                    _secid = f"{'1' if _prefix=='sh' else '0'}.{_code6}"
                    url = (f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
                           f"?secid={_secid}&fields1=f1,f2,f3,f4,f5,f6"
                           f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
                           f"&klt={cfg['klt']}&fqt=1&end=20500101&lmt={datalen}")
                    try:
                        resp = _r.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                        d = resp.json()
                        klines = d.get("data", {}).get("klines", [])
                        if not klines: return None
                        dates, opens, highs, lows, closes, vols = [], [], [], [], [], []
                        for line in klines:
                            parts = line.split(",")
                            dates.append(parts[0])
                            opens.append(float(parts[1])); closes.append(float(parts[2]))
                            highs.append(float(parts[3]));  lows.append(float(parts[4]))
                            vols.append(float(parts[5]))
                        return {"dates": np.array(dates), "opens": np.array(opens),
                                "highs": np.array(highs), "lows": np.array(lows),
                                "closes": np.array(closes), "volumes": np.array(vols)}
                    except Exception as e:
                        print(f"[筹码] 东方财富 {period} 拉取失败: {e}", flush=True); return None

            top = tk.Frame(embed_frame, bg=_BG_TOOLBAR, height=32)
            top.pack(fill=tk.X, side=tk.TOP)
            top.pack_propagate(False)

            tk.Label(top, text=f"🪙 {name} ({sina_code})", bg=_BG_TOOLBAR, fg=_FG_GOLD,
                     font=("Menlo", 10, "bold")).pack(side=tk.LEFT, padx=8)
            tk.Label(top, text="周期:", bg=_BG_TOOLBAR, fg=_FG_DIM,
                     font=("", 9)).pack(side=tk.LEFT, padx=(6, 2))

            def _on_period_change():
                _reload_and_draw()

            for txt, val in [("1分", "1min"), ("5分", "5min"), ("15分", "15min"),
                             ("30分", "30min"), ("60分", "60min"),
                             ("日线", "day"), ("周线", "week"), ("月线", "month")]:
                tk.Radiobutton(top, text=txt, variable=_period_var, value=val,
                               bg=_BG_TOOLBAR, fg="white", selectcolor=_BG_DEEP,
                               activebackground=_BG_TOOLBAR, activeforeground="white",
                               command=_on_period_change).pack(side=tk.LEFT, padx=2)

            _period_lbl = tk.Label(top, text="", bg=_BG_TOOLBAR, fg=_FG_DIM,
                                   font=("", 9))
            _period_lbl.pack(side=tk.RIGHT, padx=10)

            # ── 主容器 (canvas 区 + 浮窗信息区) ──
            main_container = tk.Frame(embed_frame, bg=_BG_DEEP)
            main_container.pack(fill=tk.BOTH, expand=True)

            # 变量闭包: 让 draw 可以刷新
            _gen_counter = [0]

            def _reload_and_draw():
                """重新拉K线 + 重绘筹码图"""
                _gen_counter[0] += 1
                my_gen = _gen_counter[0]

                # 清旧 canvas
                for w in main_container.winfo_children():
                    w.destroy()

                period = _period_var.get()
                cfg = _period_map.get(period, _period_map["day"])
                datalen = cfg["datalen"]
                period_label = {"1min": "1分钟", "5min": "5分钟", "15min": "15分钟",
                                "30min": "30分钟", "60min": "60分钟",
                                "day": "日线", "week": "周线", "month": "月线"}.get(period, period)
                _period_lbl.config(text=f"⏳ 拉取 {period_label} ...")

                def _bg():
                    kdata_local = _fetch_kline(period, sina_code, datalen)
                    def _handle():
                        if my_gen != _gen_counter[0]:
                            return  # 代次不匹配, 丢弃
                        try:
                            if kdata_local is None or len(kdata_local["closes"]) < 10:
                                _period_lbl.config(text=f"❌ {period_label} 数据加载失败", fg="#EF5350")
                                tk.Label(main_container,
                                         text=f"❌ {period_label} K线数据加载失败 (可能该周期无数据)",
                                         bg=_BG_DEEP, fg=_FG_RED,
                                         font=("Menlo", 12)).pack(pady=40)
                                return
                            _period_lbl.config(text=f"✅ {period_label}  {len(kdata_local['closes'])}根")
                            _draw_chip_figure(kdata_local, period_label, period)
                        except Exception as _e:
                            import traceback
                            traceback.print_exc(); print(f"[筹码] _handle 异常: {_e}", flush=True)
                            _period_lbl.config(text=f"❌ 绘图异常: {_e}", fg="#EF5350")
                            tk.Label(main_container, text=f"❌ 绘图异常: {_e}",
                                     bg=_BG_DEEP, fg=_FG_RED,
                                     font=("Menlo", 12)).pack(pady=40)
                    embed_frame.after(0, _handle)
                threading.Thread(target=_bg, daemon=True).start()

            def _draw_chip_figure(kdata, period_label, period="day"):
                nonlocal chip_metrics, chip_kdata  # 允许重绘覆盖

                opens = kdata["opens"]; highs = kdata["highs"]
                lows = kdata["lows"]; closes = kdata["closes"]
                volumes = kdata["volumes"]; dates = kdata["dates"]
                N = len(closes); x = np.arange(N)

                # MA
                def _ma_local(a, n):
                    if len(a) < n: return np.full(len(a), np.nan)
                    cs = np.cumsum(a.astype(float))
                    out = np.full(len(a), np.nan)
                    out[n - 1:] = (cs[n - 1:] - np.concatenate([[0], cs[:-n]])) / n
                    return out
                ma5 = _ma_local(closes, 5); ma10 = _ma_local(closes, 10)
                ma20 = _ma_local(closes, 20); ma60 = _ma_local(closes, 60)
                vol_ma5 = _ma_local(volumes, 5)

                # 筹码分布 (任何周期都可以算, 密度和相对分布是核心)
                bins, chips, _ = _build_chip_distribution(closes, volumes, highs, lows, n_bins=50)
                cm = _chip_metrics(bins, chips, closes[-1])

                # ── 创建 Figure ──
                fig = Figure(figsize=(8, 5.6), facecolor=_BG_DEEP, dpi=100)
                ax = fig.add_axes([0.05, 0.24, 0.77, 0.68], facecolor=_BG_PANEL)
                axv = fig.add_axes([0.05, 0.06, 0.77, 0.16], sharex=ax, facecolor=_BG_PANEL)
                chip_ax = fig.add_axes([0.85, 0.24, 0.13, 0.68], sharey=ax, facecolor=_BG_PANEL)

                # ── K线蜡烛 ──
                for i in range(N):
                    up = closes[i] >= opens[i]
                    color = "#EF5350" if up else "#66BB6A"
                    ax.plot([x[i], x[i]], [lows[i], highs[i]], color=color, linewidth=0.7, solid_capstyle="round")
                    body_lo = min(opens[i], closes[i]); body_hi = max(opens[i], closes[i])
                    if body_hi - body_lo < 0.001: body_hi = body_lo + 0.001
                    ax.bar(x[i], body_hi - body_lo, bottom=body_lo, width=0.7,
                           color=color, edgecolor=color, linewidth=0.4)

                # MA 线
                ax.plot(x, ma5, color="#FFD54F", lw=1.0, label="MA5", alpha=0.85)
                ax.plot(x, ma10, color="#42A5F5", lw=1.0, label="MA10", alpha=0.85)
                ax.plot(x, ma20, color="#AB47BC", lw=1.0, label="MA20", alpha=0.85)
                ax.plot(x, ma60, color="#EF9A9A", lw=1.3, label="MA60", alpha=0.9)

                # ── 筹码关键位画在主图上 ──
                cur_p = closes[-1]
                ax.axhline(cur_p, color="#FFD54F", ls="--", lw=1.0, alpha=0.7)
                ax.text(x[-1] + 1, cur_p, f" ¥{cur_p:.2f}", color="#FFD54F", fontsize=8, va="center")
                if cm.get("band90_lo") and cm.get("band90_hi"):
                    ax.axhspan(cm["band90_lo"], cm["band90_hi"], alpha=0.08, color="#90CAF9")
                    ax.text(x[0] - 1, cm["band90_lo"], f"90%¥{cm['band90_lo']:.1f}",
                            color="#90CAF9", fontsize=7, va="bottom", ha="right")
                    ax.text(x[0] - 1, cm["band90_hi"], f"90%¥{cm['band90_hi']:.1f}",
                            color="#90CAF9", fontsize=7, va="bottom", ha="right")
                if cm.get("peak_price"):
                    ax.axhline(cm["peak_price"], color="#F48FB1", ls=":", lw=0.8, alpha=0.6)
                    ax.text(x[0] - 1, cm["peak_price"], f"峰¥{cm['peak_price']:.1f}",
                            color="#F48FB1", fontsize=7, va="bottom", ha="right")
                if cm.get("avg_cost"):
                    ax.axhline(cm["avg_cost"], color="#80DEEA", ls="-.", lw=0.8, alpha=0.5)
                    ax.text(x[-1] + 1, cm["avg_cost"], f"均¥{cm['avg_cost']:.1f}",
                            color="#80DEEA", fontsize=7, va="top")

                # 主图美化
                ax.set_facecolor(_BG_PANEL)
                ax.tick_params(colors="#888888", labelsize=8)
                ax.grid(True, alpha=0.08, color="#555555")
                ax.legend(loc="upper left", fontsize=7, facecolor=_BG_PANEL,
                         edgecolor="#555555", labelcolor="#CCCCCC", ncol=4)
                step_x = max(1, N // 10)
                ax.set_xticks(x[::step_x])
                ax.set_xticklabels([str(d)[:16] for d in dates[::step_x]], rotation=30, fontsize=7)

                # ── 成交量 ──
                vol_colors = ["#EF5350" if closes[i] >= opens[i] else "#66BB6A" for i in range(N)]
                axv.bar(x, volumes.astype(float), width=0.7, color=vol_colors, alpha=0.7)
                axv.plot(x, vol_ma5, color="#FFD54F", lw=0.8, alpha=0.7)
                axv.set_facecolor(_BG_PANEL)
                axv.tick_params(colors="#888888", labelsize=7)
                axv.grid(True, alpha=0.06, color="#555555")

                # ── 右侧筹码峰 ──
                if bins is not None and chips is not None and chips.sum() > 0:
                    bin_h = bins[1] - bins[0] if len(bins) > 1 else 1.0
                    max_chip = chips.max() * 100 if chips.max() > 0 else 1
                    for bi in range(len(bins)):
                        amt = chips[bi] * 100
                        if amt <= 0.05: continue
                        density = min(amt / max_chip, 1.0)
                        if bins[bi] <= cur_p:
                            r = int(180 + 60 * density); g = int(180 - 80 * density); b = int(100 + 30 * density)
                        else:
                            r = int(120 + 60 * density); g = int(100 + 40 * density); b = int(200 - 30 * density)
                        r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
                        chip_ax.barh(bins[bi], amt, height=bin_h * 0.85,
                                     color=f"#{r:02x}{g:02x}{b:02x}", edgecolor="none", alpha=0.9)
                    chip_ax.axhline(cur_p, color="#FFD54F", ls="--", lw=1.0, alpha=0.7)
                    if cm.get("band90_lo") and cm.get("band90_hi"):
                        chip_ax.axhspan(cm["band90_lo"], cm["band90_hi"], alpha=0.12, color="#90CAF9")
                        chip_ax.text(chip_ax.get_xlim()[1] * 0.7,
                                     (cm["band90_lo"] + cm["band90_hi"]) / 2,
                                     f"90%\n{cm['band90_width']:.0f}%",
                                     color="#90CAF9", fontsize=7, va="center", ha="center")
                    chip_ax.set_xlabel("%筹码", color="#888888", fontsize=8)
                    chip_ax.set_facecolor(_BG_PANEL)
                    chip_ax.tick_params(colors="#888888", labelsize=7)
                    chip_ax.grid(True, alpha=0.06, color="#555555")
                    chip_ax.tick_params(axis="y", left=False, labelleft=False)

                # 顶部标题
                _v = "🟢吸筹" if buy100 > sell100 else ("🔴派发" if sell100 > buy100 else "⚪中性")
                fig.text(0.05, 0.96,
                         f"🪙{name} {period_label}  {_v}  [吸筹{buy100}/派发{sell100}]  "
                         f"均价¥{cm.get('avg_cost',cur_p):.1f} 获利{cm.get('profit_ratio',50):.0f}%  "
                         f"{'单峰集中' if cm.get('is_concentrated') else '多峰发散'}",
                         color="#FFD54F", fontsize=9, va="top")

                # 🆕 筹码图也加买卖点 + 综合判断
                if N >= 30:
                    # MACD
                    _e12 = np.array(closes, dtype=float); _e26 = np.array(closes, dtype=float)
                    for _i in range(1, N):
                        _e12[_i] = closes[_i] * 2/13 + _e12[_i-1] * 11/13
                        _e26[_i] = closes[_i] * 2/27 + _e26[_i-1] * 25/27
                    _dif = _e12 - _e26; _dea = np.array(_dif, dtype=float)
                    for _i in range(1, N): _dea[_i] = _dif[_i] * 0.2 + _dea[_i-1] * 0.8
                    # BOLL
                    _boll_mid = _ma_local(closes, 20)
                    _boll_std_arr = np.full(N, np.nan)
                    for _i in range(19, N): _boll_std_arr[_i] = np.std(closes[_i-19:_i+1])
                    _boll_u = _boll_mid + 2*_boll_std_arr; _boll_l = _boll_mid - 2*_boll_std_arr
                    # RSI
                    _d = np.diff(closes.astype(float))
                    _g = np.where(_d > 0, _d, 0.0); _ls = np.where(_d < 0, -_d, 0.0)
                    _rsi = np.full(N, np.nan)
                    if len(_g) >= 14:
                        _ag = np.mean(_g[:14]); _al = np.mean(_ls[:14])
                        _rsi[14] = 100 - 100/(1+_ag/_al) if _al > 0 else 100
                        for _i in range(15, N):
                            _ag = (_ag*13 + _g[_i-1])/14; _al = (_al*13 + _ls[_i-1])/14
                            _rsi[_i] = 100 - 100/(1+_ag/_al) if _al > 0 else 100

                    # 画买卖点 (MA + MACD + BOLL + RSI, 最近25根)
                    _bs_chip = []
                    _ma_f = ma5; _ma_s = ma20 if period not in ("1min","5min","15min","30min","60min") else ma10
                    for _i in range(1, N):
                        if np.isnan(_ma_f[_i]) or np.isnan(_ma_s[_i]): continue
                        if _ma_f[_i-1] < _ma_s[_i-1] and _ma_f[_i] >= _ma_s[_i]:
                            _bs_chip.append((_i, lows[_i], "buy", "MA金叉"))
                        elif _ma_f[_i-1] > _ma_s[_i-1] and _ma_f[_i] <= _ma_s[_i]:
                            _bs_chip.append((_i, highs[_i], "sell", "MA死叉"))
                    for _i in range(1, N):
                        if np.isnan(_dif[_i]) or np.isnan(_dea[_i]): continue
                        if _dif[_i-1] < _dea[_i-1] and _dif[_i] >= _dea[_i]:
                            _bs_chip.append((_i, lows[_i], "buy", "MACD金叉"))
                        elif _dif[_i-1] > _dea[_i-1] and _dif[_i] <= _dea[_i]:
                            _bs_chip.append((_i, highs[_i], "sell", "MACD死叉"))
                    for _i in range(20, N):
                        if np.isnan(_boll_l[_i]): continue
                        if closes[_i-1] > _boll_l[_i-1] and closes[_i] <= _boll_l[_i]:
                            _bs_chip.append((_i, lows[_i], "buy", "BOLL下"))
                        if closes[_i-1] < _boll_u[_i-1] and closes[_i] >= _boll_u[_i]:
                            _bs_chip.append((_i, highs[_i], "sell", "BOLL上"))
                    for _i in range(14, N):
                        if np.isnan(_rsi[_i]): continue
                        if _rsi[_i-1] < 30 and _rsi[_i] >= 30:
                            _bs_chip.append((_i, lows[_i], "buy", "RSI超卖"))
                        if _rsi[_i-1] > 70 and _rsi[_i] <= 70:
                            _bs_chip.append((_i, highs[_i], "sell", "RSI超买"))
                    # 去重 + 只画最近25根
                    _seen_c = set(); _bs_c = []
                    for b in _bs_chip:
                        if b[0] not in _seen_c: _bs_c.append(b); _seen_c.add(b[0])
                    _bs_c = [b for b in _bs_c if b[0] >= N - 25]
                    for _idx, _pr, _typ, _lbl in _bs_c:
                        _col_b = "#66BB6A" if _typ == "buy" else "#EF5350"
                        _ym = lows[_idx] * 0.985 if _typ == "buy" else highs[_idx] * 1.015
                        _mkr = "^" if _typ == "buy" else "v"
                        ax.plot(x[_idx], _ym, marker=_mkr, color=_col_b, markersize=8,
                                zorder=11, markeredgecolor="white", markeredgewidth=0.5)
                        ax.annotate(f"{'↑' if _typ=='buy' else '↓'}{_lbl[:2]}",
                                    (x[_idx], _ym), xytext=(0, 6 if _typ=="buy" else -11),
                                    textcoords="offset points", fontsize=6.5, color=_col_b,
                                    ha="center", fontweight="bold")

                    # 综合判断 (右上角浮窗)
                    _cs2 = 0; _rsn2 = []
                    _last_c2 = closes[-1]
                    if not np.isnan(ma60[-1]):
                        if ma5[-1] > ma10[-1] > ma20[-1] > ma60[-1]:
                            _cs2 += 3; _rsn2.append("✅均线多头")
                        elif ma5[-1] < ma10[-1] < ma20[-1] < ma60[-1]:
                            _cs2 -= 3; _rsn2.append("❌均线空头")
                        if ma5[-1] > ma20[-1]: _cs2 += 1
                        else: _cs2 -= 1
                        if _last_c2 > ma60[-1]: _cs2 += 0.5; _rsn2.append("MA60上")
                        else: _cs2 -= 0.5
                    else:
                        _cs2 += 1.5 if ma5[-1] > ma20[-1] else -1.5
                    if _dif[-1] > _dea[-1]: _cs2 += 1; _rsn2.append("✅MACD+")
                    else: _cs2 -= 1; _rsn2.append("❌MACD-")
                    if _dif[-1] > 0: _cs2 += 0.3; _rsn2.append("零轴上")
                    else: _cs2 -= 0.3
                    if not np.isnan(_rsi[-1]):
                        if _rsi[-1] < 30: _cs2 += 1; _rsn2.append(f"RSI{_rsi[-1]:.0f}超卖")
                        elif _rsi[-1] > 70: _cs2 -= 1.5; _rsn2.append(f"RSI{_rsi[-1]:.0f}超买")
                        elif 40 <= _rsi[-1] <= 65: _cs2 += 0.5
                    if not np.isnan(_boll_mid[-1]):
                        if _last_c2 > _boll_mid[-1]: _cs2 += 0.5
                        else: _cs2 -= 0.5
                        if _last_c2 > _boll_u[-1]: _rsn2.append("⚠️BOLL上轨")
                        if _last_c2 < _boll_l[-1]: _rsn2.append("⚠️BOLL下轨")
                    if _cs2 >= 3.5:
                        _v2, _vc2, _vb2 = "🟢看多", "#66BB6A", "#1B3A1B"
                    elif _cs2 <= -2.5:
                        _v2, _vc2, _vb2 = "🔴看空", "#EF5350", "#3A1B1B"
                    else:
                        _v2, _vc2, _vb2 = "⚪中性", "#FFD54F", "#3A3A1B"
                    _s2 = f"{_v2} 得分{_cs2:+.1f}\n" + "  ".join(_rsn2[:4])
                    ax.text(0.98, 0.98, _s2, transform=ax.transAxes,
                            fontsize=7.5, color=_vc2, ha="right", va="top",
                            bbox=dict(boxstyle="round,pad=0.4", fc=_vb2, ec=_vc2, alpha=0.9))

                fig.subplots_adjust(top=0.94, bottom=0.02, left=0.02, right=0.99, wspace=0.05, hspace=0.0)

                # ── Canvas ──
                canvas = FigureCanvasTkAgg(fig, master=main_container)
                canvas.draw()
                canvas.get_tk_widget().configure(bg=_BG_DEEP)
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

                print(f"[筹码分析] 🎨 重绘完成 period={period_label} len={N}", flush=True)

            # ── 首次加载 (用默认日线) ──
            _period_var.set("day")
            _reload_and_draw()

            # ── 可移动浮窗 ──
            float_win = tk.Toplevel(dlg)
            float_win.overrideredirect(True)
            float_win.configure(bg=_BG_PANEL)
            float_win.attributes("-topmost", True)
            dlg.update_idletasks()
            bx = embed_frame.winfo_rootx() + 8
            by = embed_frame.winfo_rooty() + 8
            float_win.geometry(f"+{bx}+{by}")
            _active_float_wins.append(float_win)

            title_bar = tk.Frame(float_win, bg=_BG_TOOLBAR, height=28)
            title_bar.pack(fill=tk.X)
            _close_lbl = tk.Label(title_bar, text="✕", bg=_BG_TOOLBAR, fg=_FG_DIM,
                                  font=("Menlo", 11), cursor="hand2")
            _close_lbl.pack(side=tk.RIGHT, padx=6)
            _close_lbl.bind("<Button-1>", lambda e: float_win.destroy())

            _verdict = "🔴吸筹" if buy100 > sell100 else ("🟢派发" if sell100 > buy100 else "⚪中性")
            _verdict_fg = _FG_RED if buy100 > sell100 else (_FG_GREEN if sell100 > buy100 else _FG_DIM)
            tk.Label(title_bar, text=f"🪙 {name} {_verdict} [{tag}]",
                     bg=_BG_TOOLBAR, fg=_verdict_fg,
                     font=("Menlo", 11, "bold")).pack(side=tk.LEFT, padx=8, pady=2)

            _drag = {"x": 0, "y": 0}
            def _on_press(e): _drag["x"] = e.x_root - float_win.winfo_x(); _drag["y"] = e.y_root - float_win.winfo_y()
            def _on_move(e): float_win.geometry(f"+{e.x_root - _drag['x']}+{e.y_root - _drag['y']}")
            title_bar.bind("<ButtonPress-1>", _on_press)
            title_bar.bind("<B1-Motion>", _on_move)
            for c in title_bar.winfo_children():
                c.bind("<ButtonPress-1>", _on_press); c.bind("<B1-Motion>", _on_move)

            body = tk.Frame(float_win, bg=_BG_PANEL); body.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

            tk.Label(body, text=f"🪙 吸筹{buy100} / 派发{sell100}", bg=_BG_PANEL, fg=_FG_GOLD,
                     font=("Menlo", 10, "bold")).pack(anchor="w")
            bar = tk.Canvas(body, width=180, height=10, bg=_BG_DEEP, highlightthickness=0); bar.pack(anchor="w", pady=2)
            bw = int(buy100)
            bar.create_rectangle(0, 0, bw, 10, fill="#5D1F1F", outline="")
            if bw < 100: bar.create_rectangle(bw, 0, 100, 10, fill="#1F3D1F", outline="")

            for lbl, bt in [("📈吸筹回测", bt_acc), ("📉派发回测", bt_dis)]:
                if bt and bt.get("count", 0) >= 5:
                    w5 = bt.get("win5", 0); plr = bt.get("profit_loss_ratio", 0)
                    tk.Label(body, text=f"{lbl}: 胜率{w5}% 盈亏{plr:.1f}",
                             bg=_BG_PANEL, fg=_FG_BLUE, font=("Menlo", 9)).pack(anchor="w")
                else:
                    tk.Label(body, text=f"{lbl}: 样本不足",
                             bg=_BG_PANEL, fg=_FG_DIM, font=("Menlo", 9)).pack(anchor="w")

            if signals:
                tk.Label(body, text="─ 信号明细 ─", bg=_BG_PANEL, fg=_FG_DIM,
                         font=("Menlo", 9)).pack(anchor="w", pady=(4, 2))
                for s in signals[:6]:
                    sig_icon = "🔴" if s["type"] == "buy" else "🟢"
                    sig_fg = _FG_RED if s["type"] == "buy" else _FG_GREEN
                    star = "★" * s["strength"]
                    tk.Label(body, text=f"{sig_icon} {s['label']} [{star}]",
                             bg=_BG_PANEL, fg=sig_fg, font=("Menlo", 9)).pack(anchor="w")

            tk.Label(body, text="↔ 拖动标题栏移动  ✕关闭",
                     bg=_BG_PANEL, fg=_FG_DIM, font=("Menlo", 8)).pack(anchor="w", pady=(6, 0))

        # ── 渲染一行 ──
        def _render_row(parent, c6, sina, name, tag, hq_info, signals,
                        buy100=50, sell100=50, bt_acc=None, bt_dis=None,
                        chip_metrics=None, chip_kdata=None):
            row_bg = _BG_CARD if parent in (inner_all, inner_acc, inner_dis) else _BG_PANEL
            row = tk.Frame(parent, bg=row_bg)
            row.pack(fill=tk.X, padx=4, pady=2)

            chg = hq_info.get("chg", 0) if hq_info else 0
            price = hq_info.get("price", 0) if hq_info else 0
            chg_fg = _FG_GREEN if chg >= 0 else _FG_RED
            tk.Label(row, text=f"{name}", bg=row_bg, fg=_FG_TEXT,
                     font=("Menlo", 13, "bold")).pack(side=tk.LEFT, padx=(8, 4), pady=6)
            tk.Label(row, text=f"{c6}", bg=row_bg, fg=_FG_DIM,
                     font=("Menlo", 11)).pack(side=tk.LEFT, pady=6)
            tk.Label(row, text=f" ¥{price:.2f}  {chg:+.2f}%", bg=row_bg, fg=chg_fg,
                     font=("Menlo", 12)).pack(side=tk.LEFT, padx=4, pady=6)

            tag_color = {"持仓": _FG_GOLD, "龙头": _FG_PURPLE, "资讯": _FG_PINK,
                         "基金": _FG_CYAN}.get(tag, _FG_DIM)
            tk.Label(row, text=f"[{tag}]", bg=row_bg, fg=tag_color,
                     font=("Menlo", 10)).pack(side=tk.LEFT, padx=2, pady=6)

            # 筹码核心指标摘要 (均价/获利%)
            if chip_metrics:
                cm_txt = f"🪙¥{chip_metrics['avg_cost']:.1f}/利{chip_metrics['profit_ratio']:.0f}%"
                tk.Label(row, text=cm_txt, bg=row_bg, fg=_FG_BLUE,
                         font=("Menlo", 10)).pack(side=tk.LEFT, padx=4, pady=6)

            # 🎯 打分 (暗灰底 + 迷你色块, 不铺满)
            score_frame = tk.Frame(row, bg=row_bg)
            score_frame.pack(side=tk.LEFT, padx=6, pady=6)
            # Canvas 底: 深灰背景 (不抢戏)
            bar = tk.Canvas(score_frame, width=90, height=10, bg=_BG_DEEP,
                            highlightthickness=0)
            bar.pack(side=tk.LEFT, padx=2)
            bw = int(buy100)
            # 买入区 (左, 红但带透明度感 — 用较深红)
            bar.create_rectangle(0, 0, bw, 10, fill="#5D1F1F", outline="")
            if bw < 100:
                # 卖出区 (右, 深绿)
                bar.create_rectangle(bw, 0, 100, 10, fill="#1F3D1F", outline="")
            # 数字在 bar 下方 (小, 灰色, 不抢眼)
            bar_num = tk.Frame(score_frame, bg=row_bg)
            bar_num.pack(side=tk.LEFT, padx=2)
            tk.Label(bar_num, text=f"🔴{buy100}  🟢{sell100}", bg=row_bg,
                     fg=_FG_DIM, font=("Menlo", 9)).pack()

            # 信号标签 (去彩色填充 — 暗灰底 + 细边框 + emoji前缀)
            for sig in signals:
                is_acc = sig["type"] == "accumulate"
                emoji = "🔴" if is_acc else "🟢"
                fg_c = "#FF7043" if is_acc else "#66BB6A"  # 亮一点的红/绿
                badge = tk.Label(row, text=f" {emoji} {sig['label']} ",
                                 bg=_BG_CARD, fg=fg_c, font=("Menlo", 10))
                badge.pack(side=tk.LEFT, padx=2, pady=6)

            # 回测摘要
            if bt_acc and bt_acc.get("count", 0) >= 5:
                w5 = bt_acc.get("win5", 0); plr = bt_acc.get("profit_loss_ratio", 0)
                tk.Label(row, text=f"📈{w5}% 盈{plr:.1f}", bg=row_bg, fg=_FG_BLUE,
                         font=("Menlo", 10)).pack(side=tk.LEFT, padx=4, pady=6)

            # ❓
            reason_text = _format_reasons(name, signals, buy100, sell100,
                                          bt_acc, bt_dis, chip_metrics)
            def _show_help(_t=reason_text):
                _top = tk.Toplevel(dlg)
                _top.title(f"💡 {name} — 筹码/资金信号")
                _top.geometry("640x600")
                _top.configure(bg=_BG_DEEP)
                tk.Label(_top, text=f"💡 {name} 的筹码/资金信号逻辑",
                         bg=_BG_DEEP, fg=_FG_GOLD,
                         font=("Menlo", 14, "bold")).pack(anchor="w", padx=14, pady=10)
                txt = tk.Text(_top, bg=_BG_PANEL, fg=_FG_TEXT, font=("Menlo", 12),
                              wrap=tk.WORD, relief=tk.FLAT, padx=14, pady=12)
                txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
                txt.insert("1.0", _t)
                txt.config(state=tk.DISABLED)

            l_help = tk.Label(row, text="❓", bg=row_bg, fg=_FG_GOLD, cursor="hand2",
                              font=("Menlo", 13))
            l_help.pack(side=tk.RIGHT, padx=8, pady=6)
            l_help.bind("<Button-1>", lambda e, fn=_show_help: fn())

            # 双击整行
            def _bind_dbl(widget):
                widget.bind("<Double-Button-1>",
                            lambda e, sc=sina, nm=name:
                                _embed_daily(sc, nm, buy100, sell100,
                                             bt_acc, bt_dis, signals, tag,
                                             chip_metrics, chip_kdata))
                for child in widget.winfo_children():
                    _bind_dbl(child)
            _bind_dbl(row)

            # 悬停高亮
            def _on_enter(e):
                e.widget.master.configure(bg="#3A3A3A")
                for c in e.widget.master.winfo_children():
                    if isinstance(c, tk.Label) and c.cget("bg") not in ("#1B5E20", "#B71C1C"):
                        c.configure(bg="#3A3A3A")
            def _on_leave(e, bg=row_bg):
                e.widget.master.configure(bg=bg)
                for c in e.widget.master.winfo_children():
                    if isinstance(c, tk.Label) and c.cget("bg") not in ("#1B5E20", "#B71C1C"):
                        c.configure(bg=bg)
            def _bind_hover(widget, enter_fn, leave_fn):
                try:
                    widget.bind("<Enter>", enter_fn)
                    widget.bind("<Leave>", leave_fn)
                except:
                    pass
                for child in widget.winfo_children():
                    _bind_hover(child, enter_fn, leave_fn)
            _bind_hover(row, _on_enter, _on_leave)
            return row

        def _format_reasons(name, signals, buy100, sell100,
                            bt_acc, bt_dis, cm=None):
            lines = [f"🪙 {name} — 筹码/资金信号详解", "═" * 50, ""]

            verdict = "🟢 吸筹机会" if buy100 > sell100 else (
                "🔴 派发警告" if sell100 > buy100 else "⚪ 中性")
            lines.append(f"🎯 筹码打分: {verdict}")
            lines.append(f"   吸筹分 = {buy100}   派发分 = {sell100}")
            lines.append("")

            if cm:
                lines.append("─ 🪙 筹码核心指标 ─")
                lines.append(f"   平均成本: ¥{cm['avg_cost']:.2f}")
                lines.append(f"   当前获利盘: {cm['profit_ratio']:.1f}%")
                lines.append(f"   90% 成本区: ¥{cm['band90_lo']:.2f} ~ ¥{cm['band90_hi']:.2f}"
                             f"  (宽度 {cm['band90_width']:.1f}%)")
                lines.append(f"   筹码密集峰: ¥{cm['peak_price']:.2f}  "
                             f"(占比 {cm['peak_amount']:.1f}%)")
                lines.append(f"   状态: {'🟢 单峰集中' if cm['is_concentrated'] else '🔴 多峰发散'}  "
                             f"位置: {cm['cur_position']}")
                lines.append("")

            def _bt_lines(label, bt):
                if not bt or bt.get("count", 0) < 5:
                    return [f"📊 {label}: 历史样本不足"]
                out = [f"📊 {label}: 过去 {bt.get('count', 0)} 次类似形态"]
                for f in (5, 10, 20):
                    if f"win{f}" in bt:
                        out.append(f"   {f}日: 胜率{bt[f'win{f}']}% 均收{bt.get(f'avg{f}', 0):+.2f}%")
                plr = bt.get("profit_loss_ratio")
                if plr is not None:
                    out.append(f"   盈亏比 = {plr:.2f}")
                return out

            lines.extend(_bt_lines("🟢吸筹回测", bt_acc))
            lines.extend(_bt_lines("🔴派发回测", bt_dis))
            lines.append("")

            accs = [s for s in signals if s["type"] == "accumulate"]
            diss = [s for s in signals if s["type"] == "distribute"]
            if accs:
                lines.append("─ 🟢 吸筹信号 ─")
                for i, s in enumerate(accs, 1):
                    lines.append(f"  {i}. {s['label']} (强度 {'★' * s['strength']})")
                    lines.append(f"     {s['reason']}")
                    lines.append("")
            if diss:
                lines.append("─ 🔴 派发信号 ─")
                for i, s in enumerate(diss, 1):
                    lines.append(f"  {i}. {s['label']} (强度 {'★' * s['strength']})")
                    lines.append(f"     {s['reason']}")
                    lines.append("")
            lines.append("═" * 50)
            lines.append("💡 筹码分析核心理念:")
            lines.append("   '知道对方手里还有多少筹码, 就知道他下一步会做什么.'")
            lines.append("   技术分析看历史价格 → 预测未来 (胜率随周期缩短降低)")
            lines.append("   筹码/资金分析看对手仓位 → 看明牌 (顶级机构用这个)")
            return "\n".join(lines)

        # ── 背景扫描 ──
        def _scan_bg():
            watchlist = _load_watchlist()
            total = len(watchlist)
            dlg.after(0, lambda: status.config(text=f"📥 加载股票池 {total} 只..."))

            sina_codes = [sina for _, sina, _ in watchlist]
            results = {}
            lock = threading.Lock()

            def _work(idx, c6, sina, tag):
                kdata = _fetch_kline_sina(sina, scale=240, datalen=120)
                if kdata is None or len(kdata["closes"]) < 30:
                    return
                sigs = _detect_capital_signals(
                    kdata["opens"], kdata["highs"], kdata["lows"],
                    kdata["closes"], kdata["volumes"])
                # 筹码指标
                bins, chips, _ = _build_chip_distribution(
                    kdata["closes"], kdata["volumes"],
                    kdata["highs"], kdata["lows"], n_bins=60)
                cm = _chip_metrics(bins, chips, kdata["closes"][-1])
                # 打分
                buy100, sell100, _, _ = _compute_chip_scores(sigs)
                # 回测
                bt_acc = _backtest_chip(
                    kdata["closes"], kdata["highs"], kdata["lows"],
                    kdata["volumes"], "accumulate")
                bt_dis = _backtest_chip(
                    kdata["closes"], kdata["highs"], kdata["lows"],
                    kdata["volumes"], "distribute")
                with lock:
                    results[c6] = {
                        "sina": sina, "tag": tag, "signals": sigs,
                        "buy100": buy100, "sell100": sell100,
                        "bt_acc": bt_acc, "bt_dis": bt_dis,
                        "chip_metrics": cm, "kdata": kdata,
                    }

            threads = []
            for i, (c6, sina, tag) in enumerate(watchlist):
                t = threading.Thread(target=_work, args=(i, c6, sina, tag), daemon=True)
                t.start(); threads.append(t)
            for t in threads:
                t.join()

            hq_map = _fetch_hq_batch(sina_codes)
            dlg.after(0, lambda: status.config(text=f"📊 渲染 {len(results)} 只..."))

            for parent in (inner_all, inner_acc, inner_dis):
                for w in parent.winfo_children():
                    w.destroy()

            all_rows, acc_rows, dis_rows = [], [], []
            for c6, info in results.items():
                sina = info["sina"]
                hq = hq_map.get(sina, {})
                name = hq.get("name", sina)
                rd = (c6, sina, name, info["tag"], hq, info["signals"],
                      info["buy100"], info["sell100"],
                      info["bt_acc"], info["bt_dis"],
                      info["chip_metrics"], info["kdata"])
                all_rows.append(rd)
                if info["buy100"] > 50:
                    acc_rows.append(rd)
                if info["sell100"] > 50:
                    dis_rows.append(rd)

            all_rows.sort(key=lambda x: x[6] - x[7], reverse=True)
            acc_rows.sort(key=lambda x: x[6], reverse=True)
            dis_rows.sort(key=lambda x: x[7], reverse=True)

            for rd in all_rows:
                _render_row(inner_all, *rd)
            if not all_rows:
                tk.Label(inner_all, text="未扫描到股票", bg=_BG_DEEP, fg=_FG_DIM,
                         font=("Menlo", 13)).pack(pady=40)

            for rd in acc_rows:
                _render_row(inner_acc, *rd)
            if not acc_rows:
                tk.Label(inner_acc, text="当前关注池暂无吸筹机会 🔴", bg=_BG_DEEP,
                         fg=_FG_DIM, font=("Menlo", 13)).pack(pady=40)

            for rd in dis_rows:
                _render_row(inner_dis, *rd)
            if not dis_rows:
                tk.Label(inner_dis, text="当前关注池暂无派发警告 🔴", bg=_BG_DEEP,
                         fg=_FG_DIM, font=("Menlo", 13)).pack(pady=40)

            acc_count, dis_count = len(acc_rows), len(dis_rows)
            def _update_tabs():
                nb.tab(tab_all, text=f"📋 全部 ({len(all_rows)})")
                nb.tab(tab_acc, text=f"🟢 吸筹 ({acc_count})")
                nb.tab(tab_dis, text=f"🔴 派发 ({dis_count})")
            dlg.after(0, _update_tabs)
            dlg.after(0, lambda: status.config(
                text=f"✅ 扫描完成 {len(results)}只 | 🟢{acc_count} 🔴{dis_count}"))

        def _start_scan():
            scan_btn.config(state=tk.DISABLED, text="⏳扫描中...")
            threading.Thread(
                target=lambda: (_scan_bg(),
                                dlg.after(0, lambda: scan_btn.config(
                                    state=tk.NORMAL, text="🔄扫描"))),
                daemon=True).start()

        scan_btn.config(command=_start_scan)
        dlg.after(200, _start_scan)


__all__ = ["ChouMaMixin"]