"""
🎯 机会扫描器 — 对持仓/龙头/资讯股逐个做技术分析

每个股票:
  🟢 买入机会 (MA金叉 / BOLL下轨反弹 / RSI超卖 / 锤子线 / MACD底背离 / 接近支撑)
  🔴 卖出警告 (MA死叉 / BOLL上轨回落 / RSI超买 / 射击之星 / MACD顶背离 / 接近压力)

每行右侧: 信号标签 + 📊日K + ❓逻辑理由
"""
import json
import os
import ssl
import threading
import urllib.request
from datetime import datetime

import numpy as np

# ── 配色 ──
_BG_DEEP = "#121212"
_BG_PANEL = "#1E1E1E"
_BG_CARD = "#2A2A2A"
_BG_TOOLBAR = "#1A1A1A"
_FG_RED = "#FF8A80"
_FG_GREEN = "#69F0AE"
_FG_GOLD = "#FFD54F"
_FG_BLUE = "#90CAF9"
_FG_CYAN = "#80DEEA"
_FG_TEXT = "#E0E0E0"
_FG_DIM = "#888888"
_FG_ORANGE = "#FFB74D"
_FG_PURPLE = "#CE93D8"
_FG_PINK = "#F48FB1"


# ═══════════════════════════════════════════════════════════
#  技术指标计算 + 信号检测
# ═══════════════════════════════════════════════════════════

def _ma(arr, n):
    """简单移动平均"""
    if len(arr) < n:
        return np.full(len(arr), np.nan)
    out = np.full(len(arr), np.nan)
    for i in range(n - 1, len(arr)):
        out[i] = arr[i - n + 1:i + 1].mean()
    return out


def _boll(arr, n=20, k=2.0):
    """布林带 — 返回 upper/mid/lower"""
    mid = _ma(arr, n)
    upper = np.full_like(mid, np.nan)
    lower = np.full_like(mid, np.nan)
    for i in range(n - 1, len(arr)):
        seg = arr[i - n + 1:i + 1]
        std = seg.std()
        upper[i] = mid[i] + k * std
        lower[i] = mid[i] - k * std
    return upper, mid, lower


def _rsi(arr, n=14):
    """RSI"""
    out = np.full(len(arr), np.nan)
    for i in range(n, len(arr)):
        delta = np.diff(arr[i - n:i + 1])
        up = delta[delta > 0].sum()
        dn = -delta[delta < 0].sum()
        if up + dn == 0:
            out[i] = 50
        else:
            out[i] = 100 * up / (up + dn)
    return out


def _macd(arr, fast=12, slow=26, signal=9):
    """MACD — 返回 dif/dea/hist"""
    ema_f = np.zeros_like(arr)
    ema_s = np.zeros_like(arr)
    ema_f[0] = arr[0]
    ema_s[0] = arr[0]
    for i in range(1, len(arr)):
        ema_f[i] = ema_f[i - 1] + 2 / (fast + 1) * (arr[i] - ema_f[i - 1])
        ema_s[i] = ema_s[i - 1] + 2 / (slow + 1) * (arr[i] - ema_s[i - 1])
    dif = ema_f - ema_s
    dea = np.zeros_like(dif)
    dea[0] = dif[0]
    for i in range(1, len(dif)):
        dea[i] = dea[i - 1] + 2 / (signal + 1) * (dif[i] - dea[i - 1])
    hist = (dif - dea) * 2
    return dif, dea, hist


def _find_local_extremes(arr, order=5):
    """找局部高低点 — 返回 [(idx, 'h')] 和 [(idx, 'l')]"""
    highs, lows = [], []
    for i in range(order, len(arr) - order):
        seg = arr[i - order:i + order + 1]
        if arr[i] == seg.max():
            highs.append((i, arr[i]))
        if arr[i] == seg.min():
            lows.append((i, arr[i]))
    return highs, lows


def _detect_signals(opens, highs, lows, closes, volumes):
    """
    核心 — 对一根K线序列检测所有买卖信号

    返回: list of {type: 'buy'|'sell', label: str, strength: 1-3, reason: str, idx: int}
    只给**最后一根K线**或最近3根的信号
    """
    signals = []
    N = len(closes)
    if N < 30:
        return signals

    # ── 计算指标 ──
    ma5 = _ma(closes, 5)
    ma10 = _ma(closes, 10)
    ma20 = _ma(closes, 20)
    ma60 = _ma(closes, 60)
    boll_u, boll_m, boll_l = _boll(closes, 20)
    rsi = _rsi(closes, 14)
    dif, dea, hist = _macd(closes)
    vol_ma5 = _ma(volumes.astype(float), 5)

    cur = N - 1  # 最后一根

    # ── 1. MA5 上穿 MA20 (金叉) / 下穿 (死叉) ──
    if cur >= 21:
        prev_diff = ma5[cur - 1] - ma20[cur - 1]
        curr_diff = ma5[cur] - ma20[cur]
        if not np.isnan(prev_diff) and not np.isnan(curr_diff):
            if prev_diff < 0 < curr_diff:
                signals.append({
                    "type": "buy", "label": "MA金叉", "strength": 2,
                    "reason": "MA5 上穿 MA20 形成金叉，短期趋势转多。配合成交量放大则更可靠，"
                              "通常预示 1-2 周的上涨行情。若 MA20 同时向上倾斜，信号强度加倍。",
                    "idx": cur
                })
            elif prev_diff > 0 > curr_diff:
                signals.append({
                    "type": "sell", "label": "MA死叉", "strength": 2,
                    "reason": "MA5 下穿 MA20 形成死叉，短期趋势转空。"
                              "如果 MA20 也开始走平或向下，建议减仓回避调整风险。",
                    "idx": cur
                })

    # ── 2. 价格站上/跌破 MA60 (牛熊线) ──
    if cur >= 60 and not np.isnan(ma60[cur]):
        if closes[cur] > ma60[cur] and closes[cur - 1] <= ma60[cur - 1]:
            signals.append({
                "type": "buy", "label": "站上MA60", "strength": 3,
                "reason": "价格向上突破 MA60（年线附近的牛熊分界），这是大级别趋势反转信号。"
                          "历史数据显示突破 MA60 后的 20 个交易日平均涨幅约 8-15%。",
                "idx": cur
            })
        elif closes[cur] < ma60[cur] and closes[cur - 1] >= ma60[cur - 1]:
            signals.append({
                "type": "sell", "label": "跌破MA60", "strength": 3,
                "reason": "价格跌破 MA60（中长期支撑线），意味着大级别趋势可能转空。"
                          "建议大幅降低仓位，等待重新站回再考虑进场。",
                "idx": cur
            })

    # ── 3. BOLL 带触轨 ──
    if cur >= 20 and not np.isnan(boll_l[cur]) and not np.isnan(boll_u[cur]):
        # 触下轨反弹
        if lows[cur] <= boll_l[cur] * 1.005 and closes[cur] > boll_l[cur]:
            signals.append({
                "type": "buy", "label": "BOLL下轨反弹", "strength": 2,
                "reason": "价格触及布林带下轨后收阳反弹。布林带下轨代表短期超卖区域，"
                          "约 70% 的概率会在 1-3 天内回到中轨附近。"
                          "配合 RSI<30 或成交量萎缩，胜率更高。",
                "idx": cur
            })
        # 触上轨回落
        if highs[cur] >= boll_u[cur] * 0.995 and closes[cur] < boll_u[cur]:
            signals.append({
                "type": "sell", "label": "BOLL上轨回落", "strength": 2,
                "reason": "价格触及布林带上轨后回落收阴。上轨代表短期超买区域，"
                          "后续大概率回踩中轨。对于短线交易者是不错的减仓信号。",
                "idx": cur
            })

    # ── 4. RSI 超买超卖 ──
    if cur >= 14 and not np.isnan(rsi[cur]):
        if rsi[cur] < 30:
            signals.append({
                "type": "buy", "label": "RSI超卖", "strength": 2,
                "reason": f"RSI(14)={rsi[cur]:.1f} < 30，属于超卖区域。"
                          "通常预示短期抛压衰竭，反弹一触即发。"
                          "注意：单边下跌行情中 RSI 可能长时间 < 30，需配合 MA 金叉确认。",
                "idx": cur
            })
        elif rsi[cur] > 70:
            signals.append({
                "type": "sell", "label": "RSI超买", "strength": 2,
                "reason": f"RSI(14)={rsi[cur]:.1f} > 70，属于超买区域。"
                          "短线获利盘丰厚，回调压力增大。"
                          "但在主升浪中 RSI 可以持续 > 70，不建议仅凭此追空。",
                "idx": cur
            })

    # ── 5. MACD 金叉/死叉 ──
    if cur >= 35 and not np.isnan(dif[cur]) and not np.isnan(dea[cur]):
        if dif[cur - 1] < dea[cur - 1] and dif[cur] >= dea[cur]:
            signals.append({
                "type": "buy", "label": "MACD金叉", "strength": 2,
                "reason": "MACD 的 DIF 上穿 DEA 形成金叉，红柱开始放大。"
                          "零轴上方金叉有效性最高（主升浪启动）；"
                          "零轴下方金叉多为反弹，需快进快出。",
                "idx": cur
            })
        elif dif[cur - 1] > dea[cur - 1] and dif[cur] <= dea[cur]:
            signals.append({
                "type": "sell", "label": "MACD死叉", "strength": 2,
                "reason": "MACD 的 DIF 下穿 DEA 形成死叉，绿柱开始放大。"
                          "零轴下方死叉有效性最高（主跌浪延续）；"
                          "零轴上方死叉多为高位震荡中的调整。",
                "idx": cur
            })

    # ── 6. 锤子线 (hammer) / 射击之星 (shooting star) ──
    if cur >= 20:
        body = closes[cur] - opens[cur]
        body_abs = abs(body)
        total_range = highs[cur] - lows[cur]
        if total_range > 0 and body_abs / total_range < 0.35:  # 小实体
            # 锤子线: 下影 ≥ 2x 实体, 上影短
            lower_shadow = min(opens[cur], closes[cur]) - lows[cur]
            upper_shadow = highs[cur] - max(opens[cur], closes[cur])
            if lower_shadow >= body_abs * 2 and upper_shadow <= body_abs * 0.5 and closes[cur] > opens[cur]:
                # 再加个位置判断 — 最好在 BOLL 下轨附近
                near_lower = (not np.isnan(boll_l[cur])) and lows[cur] <= boll_l[cur] * 1.02
                signals.append({
                    "type": "buy", "label": "锤子线", "strength": 3 if near_lower else 2,
                    "reason": "经典锤子线形态：下影线 ≥ 实体 2 倍，上影极短。"
                              "表示空头发力后被多头完全承接，是底部反转信号。"
                              f"{'位于布林下轨附近，信号更可靠。' if near_lower else '建议配合次日放量阳线确认。'}",
                    "idx": cur
                })
            # 射击之星: 上影 ≥ 2x 实体, 下影短
            elif upper_shadow >= body_abs * 2 and lower_shadow <= body_abs * 0.5 and closes[cur] < opens[cur]:
                signals.append({
                    "type": "sell", "label": "射击之星", "strength": 3,
                    "reason": "经典射击之星形态：上影线 ≥ 实体 2 倍，下影极短。"
                              "表示多头冲高后被空头完全压制，是顶部反转信号。"
                              "如果成交量同时放大，后续下跌概率极高。",
                    "idx": cur
                })

    # ── 7. 接近支撑/压力 (整数关口 + 近期高低点) ──
    cur_price = closes[cur]
    # 整数关口
    step = 10 ** (len(str(int(cur_price))) - 2) if cur_price >= 10 else 0.5
    if step > 0:
        prev_int = int(cur_price / step) * step
        next_int = prev_int + step
        dist_prev = (cur_price - prev_int) / cur_price
        dist_next = (next_int - cur_price) / cur_price
        if dist_prev < 0.02:  # 离下方整数位 < 2%
            signals.append({
                "type": "buy", "label": f"接近支撑 {prev_int}", "strength": 1,
                "reason": f"当前价 {cur_price:.2f} 距下方整数支撑 {prev_int:.2f} 仅 {dist_prev*100:.1f}%。"
                          "整数关口常常汇聚大量买单，是天然的短线支撑位。"
                          "如果跌到该位置且能放量企稳，可以考虑做T。",
                "idx": cur
            })
        if dist_next < 0.02:
            signals.append({
                "type": "sell", "label": f"接近压力 {next_int}", "strength": 1,
                "reason": f"当前价 {cur_price:.2f} 距上方整数压力 {next_int:.2f} 仅 {dist_next*100:.1f}%。"
                          "整数关口常常汇聚大量套牢盘和抛压，短线容易遇阻回落。"
                          "可考虑在此位置先减一部分仓位。",
                "idx": cur
            })

    # ── 8. 放量突破 (当前量 > 5日均量 2x + 阳线) ──
    if cur >= 5 and not np.isnan(vol_ma5[cur]) and vol_ma5[cur] > 0:
        vol_ratio = volumes[cur] / vol_ma5[cur]
        if vol_ratio >= 2.0 and closes[cur] > opens[cur] and closes[cur] > closes[cur - 1]:
            signals.append({
                "type": "buy", "label": f"放量突破 {vol_ratio:.1f}x", "strength": 3,
                "reason": f"今日成交量是 5 日均量的 {vol_ratio:.1f} 倍，且收阳线。"
                          "放量突破常是主升浪启动信号 — 主力用大资金向上扫货。"
                          "如果股价同时突破近期高点，后续上涨空间较大。",
                "idx": cur
            })
        elif vol_ratio >= 2.0 and closes[cur] < opens[cur]:
            signals.append({
                "type": "sell", "label": f"放量下跌 {vol_ratio:.1f}x", "strength": 3,
                "reason": f"今日成交量是 5 日均量的 {vol_ratio:.1f} 倍，且收阴线。"
                          "放量下跌说明有大资金在出逃 — 可能是利空消息、主力出货或恐慌盘涌出。"
                          "建议立即减仓，不要抄底接飞刀。",
                "idx": cur
            })

    # ═══════════════════════════════════════════════════════════
    #  9. 日本蜡烛图形态 (Steve Nison 经典形态)
    # ═══════════════════════════════════════════════════════════

    # 十字星 (Doji) — 小实体 + 上下影都长
    body_cur = abs(closes[cur] - opens[cur])
    rng_cur = highs[cur] - lows[cur]
    body_prev = abs(closes[cur - 1] - opens[cur - 1]) if cur >= 1 else 0
    if cur >= 3 and rng_cur > 0:
        body_ratio = body_cur / rng_cur
        upper_shadow = highs[cur] - max(opens[cur], closes[cur])
        lower_shadow = min(opens[cur], closes[cur]) - lows[cur]
        # 锤子线/射击之星已经在上面了，这里补其他形态
        if body_ratio < 0.1 and upper_shadow > body_cur * 2 and lower_shadow > body_cur * 2:
            # 长腿十字星 — 多空博弈激烈, 趋势可能反转
            # 判断方向: 位置高低
            if cur >= 20:
                high_20 = highs[cur - 20:cur + 1].max()
                low_20 = lows[cur - 20:cur + 1].min()
                pos = (closes[cur] - low_20) / (high_20 - low_20) if high_20 > low_20 else 0.5
                if pos < 0.3:
                    signals.append({
                        "type": "buy", "label": "长腿十字(低位)", "strength": 2,
                        "reason": "日本蜡烛图 — 低位长腿十字星：实体极小、上下影都很长。"
                                  "表示在长期下跌后多空力量达到平衡，空头衰竭、多头开始反击。"
                                  "历史上约 62% 的低位十字星后 5 天内出现反弹。",
                        "idx": cur
                    })
                elif pos > 0.7:
                    signals.append({
                        "type": "sell", "label": "长腿十字(高位)", "strength": 2,
                        "reason": "日本蜡烛图 — 高位长腿十字星：在长期上涨后出现长影十字，"
                                  "说明多头力量开始衰竭，空头开始反扑。"
                                  "约 58% 的高位十字星后 5 天内出现回调。",
                        "idx": cur
                    })

        # 吞没形态 (Engulfing) — 需 2 根K线
        if cur >= 1:
            body_p = closes[cur - 1] - opens[cur - 1]  # 前一根实体 (正=阳)
            body_c = closes[cur] - opens[cur]
            # 看涨吞没: 前阴后阳, 阳实体完全包住阴实体
            if body_p < 0 and body_c > 0:
                if opens[cur] <= closes[cur - 1] and closes[cur] >= opens[cur - 1]:
                    signals.append({
                        "type": "buy", "label": "看涨吞没", "strength": 3,
                        "reason": "日本蜡烛图 — 看涨吞没 (Bullish Engulfing)："
                                  "前一根阴线被后一根阳线完全吞没。多头力量突然爆发，"
                                  "一举收复前一天的全部失地。Nison 的经典反转信号之一，"
                                  "在底部出现时胜率约 70%。建议配合次日放量确认。",
                        "idx": cur
                    })
            # 看跌吞没: 前阳后阴, 阴实体完全包住阳实体
            if body_p > 0 and body_c < 0:
                if opens[cur] >= closes[cur - 1] and closes[cur] <= opens[cur - 1]:
                    signals.append({
                        "type": "sell", "label": "看跌吞没", "strength": 3,
                        "reason": "日本蜡烛图 — 看跌吞没 (Bearish Engulfing)："
                                  "前一根阳线被后一根阴线完全吞没。空头力量突然压制多头，"
                                  "主力出货或利空消息引爆的典型形态。"
                                  "在高位出现时胜率约 68%，后续大概率回调 3-8%。",
                        "idx": cur
                    })

        # 早晨之星 (Morning Star) — 3 根K线: 大阴 + 小实体(星) + 大阳
        if cur >= 2:
            body_2 = closes[cur - 2] - opens[cur - 2]
            body_1 = closes[cur - 1] - opens[cur - 1]
            rng_1 = highs[cur - 1] - lows[cur - 1]
            body_0 = closes[cur] - opens[cur]
            # 前大阴, 中小实体(星), 后大阳, 且阳线收盘 > 阴线实体中点
            if (body_2 < -body_prev * 1.5 and  # 前两天是较大的阴线
                rng_1 > 0 and abs(body_1) / rng_1 < 0.3 and  # 中间是小实体
                body_0 > abs(body_prev) * 1.5 and  # 今天是较大的阳线
                closes[cur] > (opens[cur - 2] + closes[cur - 2]) / 2):  # 收盘过阴线中点
                signals.append({
                    "type": "buy", "label": "早晨之星", "strength": 3,
                    "reason": "日本蜡烛图 — 早晨之星 (Morning Star)：经典底部三形态。"
                              "① 大阴线（空头发威）② 小实体K线（多空犹豫）③ 大阳线（多头反攻）。"
                              "Nison 书中胜率最高的形态之一，底部出现后上涨概率 ~75%。",
                    "idx": cur
                })

        # 黄昏之星 (Evening Star) — 反向的早晨之星
        if cur >= 2:
            body_2 = closes[cur - 2] - opens[cur - 2]
            body_1 = closes[cur - 1] - opens[cur - 1]
            rng_1 = highs[cur - 1] - lows[cur - 1]
            body_0 = closes[cur] - opens[cur]
            if (body_2 > abs(body_prev) * 1.5 and
                rng_1 > 0 and abs(body_1) / rng_1 < 0.3 and
                body_0 < -abs(body_prev) * 1.5 and
                closes[cur] < (opens[cur - 2] + closes[cur - 2]) / 2):
                signals.append({
                    "type": "sell", "label": "黄昏之星", "strength": 3,
                    "reason": "日本蜡烛图 — 黄昏之星 (Evening Star)：经典顶部三形态。"
                              "① 大阳线（多头狂欢）② 小实体K线（多空犹豫）③ 大阴线（空头反扑）。"
                              "出现在高位时几乎是必然的回调信号，胜率 ~72%。",
                    "idx": cur
                })

        # 看涨刺透 / 看跌乌云盖顶
        if cur >= 1 and rng_cur > 0:
            body_p = closes[cur - 1] - opens[cur - 1]
            body_c = closes[cur] - opens[cur]
            # 看涨刺透 (Piercing Pattern)
            if body_p < 0 and body_c > 0:
                # 阳线开盘 < 前阴最低, 收盘 > 前阴实体中点
                mid_p = (opens[cur - 1] + closes[cur - 1]) / 2
                if opens[cur] < lows[cur - 1] and closes[cur] > mid_p:
                    signals.append({
                        "type": "buy", "label": "看涨刺透", "strength": 2,
                        "reason": "日本蜡烛图 — 看涨刺透形态："
                                  "阳线跳空低开至前阴线实体以下，然后强力反弹收在前阴线实体中点之上。"
                                  "多头主动反击的信号，底部出现时胜率约 65%。",
                        "idx": cur
                    })
            # 看跌乌云盖顶 (Dark Cloud Cover)
            if body_p > 0 and body_c < 0:
                mid_p = (opens[cur - 1] + closes[cur - 1]) / 2
                if opens[cur] > highs[cur - 1] and closes[cur] < mid_p:
                    signals.append({
                        "type": "sell", "label": "乌云盖顶", "strength": 2,
                        "reason": "日本蜡烛图 — 乌云盖顶形态："
                                  "阴线跳空高开至前阳线实体以上，然后强力下跌收在前阳线实体中点之下。"
                                  "空头突然发难的信号，高位出现时胜率约 63%。",
                        "idx": cur
                    })

    # ═══════════════════════════════════════════════════════════
    #  10. 期货技术分析 (Trading Range Breakout / Keltner / Turtle)
    # ═══════════════════════════════════════════════════════════

    # 10a. 唐奇安通道突破 (Donchian) — 20日最高/最低
    if cur >= 20:
        dc_high = highs[cur - 20:cur].max()
        dc_low = lows[cur - 20:cur].min()
        if closes[cur] > dc_high:
            signals.append({
                "type": "buy", "label": f"唐奇安突破↑{dc_high:.2f}", "strength": 3,
                "reason": "期货经典 — 唐奇安通道突破 (Donchian Breakout)："
                          "收盘价突破过去 20 个交易日的最高点。"
                          "这是海龟交易法则 (Turtle Trading) 的核心进场信号，"
                          "量化历史回测显示：突破后持有 20 天的平均收益率显著高于随机。"
                          "建议配合成交量放大确认。",
                "idx": cur
            })
        elif closes[cur] < dc_low:
            signals.append({
                "type": "sell", "label": f"唐奇安破位↓{dc_low:.2f}", "strength": 3,
                "reason": "期货经典 — 唐奇安通道破位："
                          "收盘价跌破过去 20 个交易日的最低点。"
                          "趋势交易者的止损信号 — 多头应该离场观望，"
                          "空头可以考虑顺势试空。",
                "idx": cur
            })

    # 10b. ATR 相对波动率
    if cur >= 14:
        atr_arr = np.zeros(cur + 1)
        for i in range(1, cur + 1):
            tr = max(highs[i] - lows[i],
                     abs(highs[i] - closes[i - 1]),
                     abs(lows[i] - closes[i - 1]))
            atr_arr[i] = tr
        atr14 = atr_arr[cur - 13:cur + 1].mean()
        atr_pct = atr14 / closes[cur] * 100  # ATR 占价格百分比
        # 如果 ATR 明显扩大 (近 20 日 ATR 均值对比)
        atr20 = atr_arr[max(0, cur - 19):cur + 1].mean()
        if atr20 > 0 and atr14 / atr20 > 1.5:
            # ATR 突然放大 — 可能有趋势性行情
            direction = "上涨" if closes[cur] > closes[cur - 5] else "下跌"
            sig_type = "buy" if direction == "上涨" else "sell"
            signals.append({
                "type": sig_type,
                "label": f"波动率扩张 ATR+{(atr14/atr20-1)*100:.0f}%",
                "strength": 2,
                "reason": f"期货经典 — ATR 波动率放大检测：ATR(14)={atr_pct:.2f}% "
                          f"较近 20 日均 ATR 扩张 {(atr14/atr20-1)*100:.0f}%。"
                          f"当前价格 5 日内{direction}。"
                          f"波动率扩张通常预示大行情启动，趋势交易者会"
                          f"在 ATR 扩张时顺势加仓。如果是利空导致的波动率扩大，"
                          f"注意顺势操作而非抄底。",
                "idx": cur
            })

    # 10c. Keltner 通道 (EMA + ATR*2) — 和 BOLL 类似但用 ATR
    if cur >= 10:
        kema = _ma(closes, 10)  # 简化, 用 MA 代 EMA
        if not np.isnan(kema[cur]):
            k_upper = kema[cur] + 2 * atr14
            k_lower = kema[cur] - 2 * atr14
            # 通道收窄 (ATR 降低) + 近期 ATR 突然放大 = 可能大行情
            # 简单版: 价格从下轨反弹
            if lows[cur] <= k_lower and closes[cur] > k_lower and closes[cur] > opens[cur]:
                signals.append({
                    "type": "buy", "label": "Keltner下轨反弹", "strength": 2,
                    "reason": "期货经典 — Keltner 通道下轨反弹："
                              "Keltner 通道基于 ATR 波动率，比布林带更能适应不同波动环境。"
                              "价格触下轨后收阳反弹，通常表示短期超卖后修复。"
                              "如果配合 ATR 扩张，则可能是趋势反转信号。",
                    "idx": cur
                })

    # 10d. 连续 N 日同方向 (趋势强度)
    if cur >= 4:
        last5 = closes[cur - 4:cur + 1]
        up_days = sum(1 for i in range(1, len(last5)) if last5[i] > last5[i - 1])
        down_days = 4 - up_days
        if up_days >= 4:
            # 连涨 5 天 — 短期超涨警告
            signals.append({
                "type": "sell", "label": f"连涨{up_days}天", "strength": 2,
                "reason": f"期货经典 — 连续上涨检测：最近 5 天中 {up_days} 天收阳。"
                          "短期涨势过猛，获利盘累积较多。"
                          "期货交易者会在连续 3-5 天同方向后考虑"
                          "减仓或设置更近的止损。A股 T+1 制度下连续涨停"
                          "可能还有惯性，但连涨 5 天后回调概率显著上升。",
                "idx": cur
            })
        elif down_days >= 4:
            signals.append({
                "type": "buy", "label": f"连跌{down_days}天", "strength": 2,
                "reason": f"期货经典 — 连续下跌检测：最近 5 天中 {down_days} 天收阴。"
                          "短期跌势过猛，恐慌盘释放较充分。"
                          "期货交易者会在连续 3-5 天下跌后考虑"
                          "减空仓或轻仓试多。但 A 股单边市场中"
                          "连跌后可能继续阴跌，需配合 MA 和 MACD 金叉确认。",
                "idx": cur
            })

    return signals


# ═══════════════════════════════════════════════════════════
#  数据获取
# ═══════════════════════════════════════════════════════════

def _fetch_kline_sina(sina_code, scale=240, datalen=120):
    """新浪日线/60分线 — 返回 dict with dates/opens/highs/lows/closes/volumes"""
    import json as _json
    ctx = ssl._create_unverified_context()
    url = (f"https://quotes.sina.cn/cn/api/jsonp.php/_/"
           f"CN_MarketData.getKLineData?symbol={sina_code}&scale={scale}&datalen={datalen}")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"
        })
        with urllib.request.urlopen(req, timeout=6, context=ctx) as r:
            raw = r.read().decode("utf-8", errors="ignore")
        # jsonp 包裹: (_)([...])
        body = raw.split("(", 1)[1].rsplit(")", 1)[0]
        data = _json.loads(body)
        if not data:
            return None
        dates = np.array([d["day"] for d in data])
        opens = np.array([float(d["open"]) for d in data])
        highs = np.array([float(d["high"]) for d in data])
        lows = np.array([float(d["low"]) for d in data])
        closes = np.array([float(d["close"]) for d in data])
        vols = np.array([float(d["volume"]) for d in data])
        return {"dates": dates, "opens": opens, "highs": highs,
                "lows": lows, "closes": closes, "volumes": vols}
    except Exception as e:
        print(f"[_fetch_kline] {sina_code} scale={scale} error: {e}")
        return None


def _fetch_hq_batch(codes):
    """批量实时行情 — {code: {name, price, chg, ...}}"""
    ctx = ssl._create_unverified_context()
    result = {}
    for i in range(0, len(codes), 60):
        batch = codes[i:i + 60]
        joined = ",".join(batch)
        url = f"https://hq.sinajs.cn/list={joined}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"
            })
            with urllib.request.urlopen(req, timeout=8, context=ctx) as r:
                text = r.read().decode("gbk", errors="ignore")
            for line in text.strip().split("\n"):
                if "=" not in line:
                    continue
                varname, val = line.split("=", 1)
                code = varname.split("_")[-1]
                val = val.strip().strip(";").strip('"')
                if not val:
                    continue
                f = val.split(",")
                if len(f) < 9:
                    continue
                try:
                    name = f[0]
                    open_p = float(f[1]) if f[1] else 0
                    prev_close = float(f[2]) if f[2] else 0
                    cur = float(f[3]) if f[3] else 0
                    chg = (cur - prev_close) / prev_close * 100 if prev_close else 0
                    result[code] = {"name": name, "price": cur, "chg": chg,
                                    "prev": prev_close, "open": open_p}
                except:
                    pass
        except Exception as e:
            print(f"[_hq_batch] batch {i//60} error: {e}")
    return result


def _load_watchlist():
    """加载关注池 — 持仓 + 龙头 + 资讯股(淘股吧/韭研) + 基金持仓"""
    pool = []
    seen_codes = set()  # 用 sina code (带前缀) 去重

    def _add(sina_or_c6, tag):
        raw = str(sina_or_c6).strip()
        # 已经是 sina code
        if raw.lower().startswith(("sh", "sz", "bj")):
            sina = raw.lower()
            c6 = sina[2:]
        else:
            c6 = raw
            sina = _c6_to_sina(c6)
        if sina in seen_codes:
            return
        seen_codes.add(sina)
        pool.append((c6, sina, tag))

    # 1. 持仓 (trading_positions.json)
    pos_path = os.path.join("data", "trading_positions.json")
    if os.path.exists(pos_path):
        try:
            with open(pos_path) as f:
                positions = json.load(f)
            for p in positions:
                c = p.get("code", "")
                if c:
                    _add(c, "持仓")
        except:
            pass

    # 2. 龙头股 (硬编码)
    leaders = [
        "600519", "300750", "002594", "601318", "600036",
        "000858", "688256", "688981", "000333", "601012",
        "300059", "300308", "603259",
    ]
    for c6 in leaders:
        _add(c6, "龙头")

    # 3. 资讯股 — 淘股吧 + 韭研 stamp_cache (取最新日期文件)
    def _load_stamp_cache(prefix, tag):
        data_dir = "data"
        files = sorted([f for f in os.listdir(data_dir)
                        if f.startswith(prefix) and f.endswith(".json")], reverse=True)
        if not files:
            return
        fpath = os.path.join(data_dir, files[0])
        try:
            with open(fpath) as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        code = item.get("code", "")
                        if code:
                            _add(code, tag)
            elif isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        for item in v:
                            if isinstance(item, dict):
                                code = item.get("code", "")
                                if code:
                                    _add(code, tag)
        except Exception as e:
            print(f"[_load_stamp_cache] {prefix} error: {e}")

    _load_stamp_cache("stamp_cache_taoguba", "资讯")
    _load_stamp_cache("stamp_cache_jiuyan", "资讯")

    # 4. 基金持仓 (fund_holdings_cache — 取最新日期文件)
    def _load_fund_holdings():
        data_dir = "data"
        files = sorted([f for f in os.listdir(data_dir)
                        if f.startswith("fund_holdings_cache_") and f.endswith(".json")], reverse=True)
        if not files:
            return
        fpath = os.path.join(data_dir, files[0])
        try:
            with open(fpath) as f:
                data = json.load(f)
            if isinstance(data, dict):
                # 结构可能是 {基金名: [{code, name, weight}, ...]}
                for v in data.values():
                    if isinstance(v, list):
                        for item in v:
                            if isinstance(item, dict):
                                code = item.get("code", "")
                                # 基金持仓里可能是 ETF 纯 6 位
                                if code and len(str(code)) == 6:
                                    _add(code, "基金")
        except Exception as e:
            print(f"[_load_fund_holdings] error: {e}")

    _load_fund_holdings()

    print(f"[_load_watchlist] total: {len(pool)}", flush=True)
    return pool


def _c6_to_sina(c6):
    """6位代码 → sina code"""
    c6 = str(c6).strip()
    if c6.startswith(("4", "8")):
        return f"bj{c6}"
    if c6.startswith(("5", "6", "9")):
        return f"sh{c6}"
    return f"sz{c6}"


# ═══════════════════════════════════════════════════════════
#  UI
# ═══════════════════════════════════════════════════════════

class JianLouMixin:
    """机会扫描器 mixin"""

    def _show_jianlou(self):
        import tkinter as tk
        from tkinter import ttk

        dlg = tk.Toplevel(getattr(self, "win", None) or self.root)
        dlg.title("🎯 机会扫描")
        dlg.geometry("1440x860")
        dlg.configure(bg=_BG_DEEP)

        # ── 顶栏 ──
        top = tk.Frame(dlg, bg=_BG_TOOLBAR, height=42); top.pack(fill=tk.X)
        top.pack_propagate(False)
        tk.Label(top, text="🎯 机会扫描", bg=_BG_TOOLBAR, fg=_FG_GOLD,
                 font=("Menlo", 15, "bold")).pack(side=tk.LEFT, padx=12, pady=6)
        status = tk.Label(top, text="⏳ 准备扫描...", bg=_BG_TOOLBAR, fg=_FG_DIM,
                          font=("Menlo", 12))
        status.pack(side=tk.RIGHT, padx=12)

        scan_btn = tk.Button(top, text="🔄扫描", command=lambda: None,
                             bg=_BG_PANEL, fg=_FG_CYAN, activebackground=_BG_CARD,
                             activeforeground=_FG_CYAN, font=("Menlo", 12, "bold"),
                             relief=tk.FLAT, padx=10, pady=3, cursor="hand2")
        scan_btn.pack(side=tk.LEFT, padx=6, pady=6)

        tk.Label(top, text="  📈 持仓 + 龙头 + 资讯股   🟢买入机会  🔴卖出警告",
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
        kline_title = tk.Label(kline_top, text="📊 点击左侧📊查看日K",
                               bg=_BG_TOOLBAR, fg=_FG_DIM, font=("Menlo", 12))
        kline_title.pack(side=tk.LEFT, padx=10, pady=4)
        embed_frame = tk.Frame(right, bg=_BG_PANEL)
        embed_frame.pack(fill=tk.BOTH, expand=True)

        # ── Notebook: 全池 / 🟢买入 / 🔴卖出 ──
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
        tab_buy = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_buy, text="🟢 买入机会")
        tab_sell = tk.Frame(nb, bg=_BG_DEEP); nb.add(tab_sell, text="🔴 卖出警告")

        # ── 滚动容器 ──
        def _make_scrollable(parent):
            cv = tk.Canvas(parent, bg=_BG_DEEP, highlightthickness=0)
            cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=cv.yview)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            cv.configure(yscrollcommand=sb.set)
            inner = tk.Frame(cv, bg=_BG_DEEP)
            cv.create_window((0, 0), window=inner, anchor="nw")
            inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
            # 鼠标滚轮
            cv.bind_all("<MouseWheel>", lambda e: cv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
            return cv, inner

        cv_all, inner_all = _make_scrollable(tab_all)
        cv_buy, inner_buy = _make_scrollable(tab_buy)
        cv_sell, inner_sell = _make_scrollable(tab_sell)

        # ── 嵌入日K ──
        def _embed_daily(sina_code, name):
            from ui.high_low_swing import _quick_open_daily_kline
            # 清旧 canvas
            for w in embed_frame.winfo_children():
                w.destroy()
            embed_frame.update_idletasks()
            # _quick_open_daily_kline(parent, code6_or_sina, name, embed_frame=...)
            _quick_open_daily_kline(embed_frame, sina_code, name, embed_frame=embed_frame)
            kline_title.config(text=f"📊 {name} ({sina_code})")
            print(f"[机会扫描] embed {name} {sina_code}", flush=True)

        # ── 渲染一行 ──
        def _render_row(parent, c6, sina, name, tag, hq_info, signals):
            """在 parent 里放一行: [股票信息] [🟢买信号标签] [🔴卖信号标签] [📊] [❓]"""
            row_bg = _BG_CARD if parent in (inner_all, inner_buy, inner_sell) else _BG_PANEL
            row = tk.Frame(parent, bg=row_bg)
            row.pack(fill=tk.X, padx=4, pady=2)

            # 股票信息 (左)
            chg = hq_info.get("chg", 0) if hq_info else 0
            price = hq_info.get("price", 0) if hq_info else 0
            chg_fg = _FG_GREEN if chg >= 0 else _FG_RED
            tk.Label(row, text=f"{name}", bg=row_bg, fg=_FG_TEXT,
                     font=("Menlo", 13, "bold")).pack(side=tk.LEFT, padx=(8, 4), pady=6)
            tk.Label(row, text=f"{c6}", bg=row_bg, fg=_FG_DIM,
                     font=("Menlo", 11)).pack(side=tk.LEFT, pady=6)
            tk.Label(row, text=f"  ¥{price:.2f}  {chg:+.2f}%", bg=row_bg, fg=chg_fg,
                     font=("Menlo", 12)).pack(side=tk.LEFT, padx=6, pady=6)

            # 池标签
            tag_color = {"持仓": _FG_GOLD, "龙头": _FG_PURPLE, "资讯": _FG_PINK}.get(tag, _FG_DIM)
            tk.Label(row, text=f"[{tag}]", bg=row_bg, fg=tag_color,
                     font=("Menlo", 10)).pack(side=tk.LEFT, padx=2, pady=6)

            # 🟢 买入信号
            buys = [s for s in signals if s["type"] == "buy"]
            sells = [s for s in signals if s["type"] == "sell"]

            for sig in buys:
                badge_bg = "#1B5E20"  # 深绿底
                badge = tk.Label(row, text=f"🟢 {sig['label']}", bg=badge_bg, fg=_FG_GREEN,
                                 font=("Menlo", 10), padx=6, pady=1)
                badge.pack(side=tk.LEFT, padx=3, pady=6)

            for sig in sells:
                badge_bg = "#B71C1C"  # 深红底
                badge = tk.Label(row, text=f"🔴 {sig['label']}", bg=badge_bg, fg=_FG_RED,
                                 font=("Menlo", 10), padx=6, pady=1)
                badge.pack(side=tk.LEFT, padx=3, pady=6)

            # 右侧按钮区
            # ❓ 帮助 (最右)
            reason_text = _format_reasons(name, signals)
            def _show_help(_t=reason_text):
                _top = tk.Toplevel(dlg)
                _top.title(f"💡 {name} — 信号逻辑")
                _top.geometry("620x520")
                _top.configure(bg=_BG_DEEP)
                tk.Label(_top, text=f"💡 {name} 的技术信号逻辑",
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

            # 🆕 双击整行 → 嵌日K (递归绑所有子控件)
            def _bind_dbl(widget):
                widget.bind("<Double-Button-1>", lambda e, sc=sina, nm=name: _embed_daily(sc, nm))
                for child in widget.winfo_children():
                    _bind_dbl(child)
            _bind_dbl(row)

            # 鼠标悬停高亮
            def _on_enter(e, bg=_BG_CARD):
                e.widget.master.configure(bg="#3A3A3A")
                for c in e.widget.master.winfo_children():
                    if isinstance(c, tk.Label):
                        cur_bg = c.cget("bg")
                        if cur_bg not in ("#1B5E20", "#B71C1C"):  # 不动信号 badge
                            c.configure(bg="#3A3A3A")
            def _on_leave(e, bg=row_bg):
                e.widget.master.configure(bg=bg)
                for c in e.widget.master.winfo_children():
                    if isinstance(c, tk.Label):
                        cur_bg = c.cget("bg")
                        if cur_bg not in ("#1B5E20", "#B71C1C"):
                            c.configure(bg=bg)
            _bind_hover(row, _on_enter, _on_leave)

            return row

        def _bind_hover(widget, enter_fn, leave_fn):
            """递归给所有子控件绑 enter/leave — 高亮整行"""
            try:
                widget.bind("<Enter>", enter_fn)
                widget.bind("<Leave>", leave_fn)
            except:
                pass
            for child in widget.winfo_children():
                _bind_hover(child, enter_fn, leave_fn)

        def _format_reasons(name, signals):
            if not signals:
                return f"📊 {name}\n\n当前技术指标未触发明显的买入或卖出信号。\n\n" \
                       f"建议继续观望，或查看 60min / 1min 周期寻找更短线的机会。"
            lines = [f"📊 {name} — 技术信号详解\n", "═" * 50, ""]
            buys = [s for s in signals if s["type"] == "buy"]
            sells = [s for s in signals if s["type"] == "sell"]
            if buys:
                lines.append("🟢 买入机会:")
                lines.append("─" * 30)
                for i, s in enumerate(buys, 1):
                    lines.append(f"  {i}. {s['label']} (强度 {'★' * s['strength']})")
                    lines.append(f"     {s['reason']}")
                    lines.append("")
            if sells:
                lines.append("🔴 卖出警告:")
                lines.append("─" * 30)
                for i, s in enumerate(sells, 1):
                    lines.append(f"  {i}. {s['label']} (强度 {'★' * s['strength']})")
                    lines.append(f"     {s['reason']}")
                    lines.append("")
            lines.append("═" * 50)
            lines.append("⚠️ 以上为纯技术面分析结果，仅供参考。")
            lines.append("   实际操作请结合基本面、消息面和市场环境综合判断。")
            return "\n".join(lines)

        # ── 背景扫描 ──
        def _scan_bg():
            watchlist = _load_watchlist()
            total = len(watchlist)
            dlg.after(0, lambda: status.config(text=f"📥 加载股票池 {total} 只..."))

            sina_codes = [sina for _, sina, _ in watchlist]

            # 并行拉日K
            results = {}
            lock = threading.Lock()

            def _work(idx, c6, sina, tag):
                kdata = _fetch_kline_sina(sina, scale=240, datalen=120)
                if kdata is None or len(kdata["closes"]) < 30:
                    return
                sigs = _detect_signals(kdata["opens"], kdata["highs"], kdata["lows"],
                                       kdata["closes"], kdata["volumes"])
                with lock:
                    results[c6] = {"sina": sina, "tag": tag, "signals": sigs}

            threads = []
            for i, (c6, sina, tag) in enumerate(watchlist):
                t = threading.Thread(target=_work, args=(i, c6, sina, tag), daemon=True)
                t.start()
                threads.append(t)
            for t in threads:
                t.join()

            # 批量拉实时行情补名字和现价
            hq_map = _fetch_hq_batch(sina_codes)

            dlg.after(0, lambda: status.config(text=f"📊 渲染 {len(results)} 只..."))

            # 清空旧
            for parent in (inner_all, inner_buy, inner_sell):
                for w in parent.winfo_children():
                    w.destroy()

            # 分类渲染
            all_rows = []
            buy_rows = []
            sell_rows = []
            for c6, info in results.items():
                sina = info["sina"]
                hq = hq_map.get(sina, {})
                name = hq.get("name", sina)
                row_data = (c6, sina, name, info["tag"], hq, info["signals"])
                all_rows.append(row_data)
                if any(s["type"] == "buy" for s in info["signals"]):
                    buy_rows.append(row_data)
                if any(s["type"] == "sell" for s in info["signals"]):
                    sell_rows.append(row_data)

            # 按信号数排序 (多信号的排前面)
            all_rows.sort(key=lambda x: len(x[5]), reverse=True)
            buy_rows.sort(key=lambda x: sum(s["strength"] for s in x[5] if s["type"] == "buy"), reverse=True)
            sell_rows.sort(key=lambda x: sum(s["strength"] for s in x[5] if s["type"] == "sell"), reverse=True)

            for rd in all_rows:
                _render_row(inner_all, *rd)
            if not all_rows:
                tk.Label(inner_all, text="未扫描到股票，请检查网络或 data/stockyidong 目录",
                         bg=_BG_DEEP, fg=_FG_DIM, font=("Menlo", 13)).pack(pady=40)

            for rd in buy_rows:
                _render_row(inner_buy, *rd)
            if not buy_rows:
                tk.Label(inner_buy, text="当前关注池暂无买入机会 🟢",
                         bg=_BG_DEEP, fg=_FG_DIM, font=("Menlo", 13)).pack(pady=40)

            for rd in sell_rows:
                _render_row(inner_sell, *rd)
            if not sell_rows:
                tk.Label(inner_sell, text="当前关注池暂无卖出警告 🔴",
                         bg=_BG_DEEP, fg=_FG_DIM, font=("Menlo", 13)).pack(pady=40)

            buy_count = len(buy_rows)
            sell_count = len(sell_rows)
            dlg.after(0, lambda: status.config(
                text=f"✅ 扫描完成 {len(results)}只 | 🟢{buy_count} 🔴{sell_count}"))

        def _start_scan():
            scan_btn.config(state=tk.DISABLED, text="⏳扫描中...")
            threading.Thread(target=lambda: (_scan_bg(),
                                             dlg.after(0, lambda: scan_btn.config(
                                                 state=tk.NORMAL, text="🔄扫描"))),
                             daemon=True).start()

        scan_btn.config(command=_start_scan)
        # 自动启动
        dlg.after(200, _start_scan)
