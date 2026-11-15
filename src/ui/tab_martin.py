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
        """带重试的 akshare 日线拉取 — 东方财富 → 腾讯兜底 (单只超时 6 秒)"""
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

        # ═══ 左: 选股列表 (默认 520px, 可拖宽拖窄) ═══
        left = tk.Frame(pw, bg="#1a1a3e", width=520)
        pw.add(left, width=520)

        status_lbl = tk.Label(left, text="👉 选股票来源 → 点 🔍 扫描, 或直接输入代码回车",
                              font=("", 10), bg="#1a1a3e", fg="#78909C", wraplength=520,
                              justify=tk.LEFT)
        status_lbl.pack(fill=tk.X, pady=(8, 4), padx=8)

        # Treeview + 水平滚动条 (所有列都可拖拽宽度)
        tv_frame = tk.Frame(left, bg="#1a1a3e")
        tv_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        cols = ("代码", "名称", "涨幅%", "成交(亿)", "ADR%", "形态", "评分", "支撑/备注")
        tv = ttk.Treeview(tv_frame, columns=cols, show="headings", height=36)
        # 每列 stretch=False → 可手动拖宽度; 最小 widths 保证可见
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

        # ═══ 右: K线 + 分析 (可拖宽) ═══
        right = tk.Frame(pw, bg="#0f0f23")
        pw.add(right)

        # 工具栏 (独立在 kline_host 上方, 永不被挤)
        self._mk_toolbar = tk.Frame(right, bg="#0f0f23")
        self._mk_toolbar.pack(fill=tk.X, pady=(2, 2))
        # 占位提示 (选股票后会被替换成指标勾选行)
        tk.Label(self._mk_toolbar, text="📊 K线指标:  ⚠️ 请先选股票 (下拉回车 / 双击列表)",
                 font=("", 10), bg="#0f0f23", fg="#78909C").pack(side=tk.LEFT, padx=6)

        # 指标勾选列表 (直接嵌在工具栏, 勾选即时重绘)
        self._mk_ind_checks = {}

        kline_host = tk.Frame(right, bg="#0f0f23")
        kline_host.pack(fill=tk.BOTH, expand=True)

        analysis_host = tk.Frame(right, bg="#1a1a3e", height=180)
        analysis_host.pack(fill=tk.X, pady=(6, 0))
        analysis_host.pack_propagate(False)
        self._mk_analysis_host = analysis_host  # 立即存, 防 None
        self._mk_account = 100000
        self._mk_risk = 0.5
        self._mk_data = None

        # 点击 → K线
        def _on_select(_e=None):
            sel = tv.selection()
            if not sel:
                return
            vals = tv.item(sel[0], "values")
            self._show_martin_kline(vals[0], vals[1], kline_host, analysis_host,
                                    float(acc_var.get()) if acc_var.get() else 100000,
                                    float(risk_var.get()) if risk_var.get() else 0.5)

        tv.bind("<<TreeviewSelect>>", _on_select)
        tv.bind("<Double-1>", _on_select)

        # 手动输入: 回车触发
        def _on_enter(_e):
            code = manual_var.get().strip()
            if code:
                self._analyze_manual_code(code, kline_host, analysis_host,
                                          float(acc_var.get()) if acc_var.get() else 100000,
                                          float(risk_var.get()) if risk_var.get() else 0.5)

        quick_combo.bind("<Return>", _on_enter)

        # 环境检查 (后台)
        def _env_bg():
            try:
                r = self._check_market_env_safe()
                kw.after(0, lambda: env_lbl.configure(
                    text=f"🌐 环境: {r['status']}", fg=r['color']))
            except Exception as e:
                kw.after(0, lambda: env_lbl.configure(
                    text=f"🌐 环境: 检查失败", fg="#EF5350"))

        threading.Thread(target=_env_bg, daemon=True).start()
        print("[🎯Martin] 弹窗已打开", flush=True)

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
        """显示 Martin 风格 K 线图 + 完整交易计划 + 指标工具栏"""
        # 清空 (但保留工具栏!)
        for w in kline_host.winfo_children():
            w.destroy()
        for w in analysis_host.winfo_children():
            w.destroy()

        if not AKSHARE_OK:
            tk.Label(kline_host, text="❌ AKShare 未安装", font=("", 12),
                     bg="#0f0f23", fg="#EF5350").pack(pady=60)
            return

        try:
            # 清空 kline_host + analysis_host (工具栏在外面独立)
            for w in kline_host.winfo_children():
                w.destroy()
            for w in self._mk_toolbar.winfo_children():
                w.destroy()
            ah = getattr(self, "_mk_analysis_host", None)
            if ah is not None and ah.winfo_exists():
                for w in ah.winfo_children():
                    try: w.destroy()
                    except Exception: pass

            h = self._ak_hist_with_retry(code, max_retries=2)
            if h is None or len(h) < 60:
                tk.Label(kline_host, text="❌ 拉取失败", font=("", 11),
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
            n = len(closes)

            # 指标
            ema9 = self._ema(closes, 9)
            ema21 = self._ema(closes, 21)
            ema50 = self._ema(closes, 50)
            ema150 = self._ema(closes, 150)
            sma5 = self._sma(closes, 5)
            sma10 = self._sma(closes, 10)
            sma20 = self._sma(closes, 20)
            sma60 = self._sma(closes, 60)
            adr_arr = self._adr(highs, lows, closes, 20)

            anchor = np.argmax(highs[-30:]) + n - 30
            avwap = self._avwap(highs, lows, closes, vols, anchor)

            # 缓存所有数据 (供重绘用)
            self._mk_data = dict(
                code=code, name=name, n=n, h=h,
                opens=opens, closes=closes, highs=highs, lows=lows, vols=vols,
                ema9=ema9, ema21=ema21, ema50=ema50, ema150=ema150,
                sma5=sma5, sma10=sma10, sma20=sma20, sma60=sma60,
                avwap=avwap, anchor=anchor,
                adr_arr=adr_arr,
            )
            self._mk_account = account_value
            self._mk_risk = risk_pct
            self._mk_analysis_host = analysis_host
            self._mk_toolbar = None  # 稍后存工具栏 frame
            # 默认开启的指标
            if not hasattr(self, "_mk_indicators") or not self._mk_indicators:
                self._mk_indicators = {
                    "EMA": True, "AVWAP": True, "成交额": True,
                    "MA5/10": False, "MA20/60": False, "BOLL": False,
                    "MACD": False, "KDJ": False, "RSI": False, "ATR": False,
                    "OBV": False,
                }

            # ── 工具栏: 一排 Checkbutton, 勾选即时重绘 ──
            tb = self._mk_toolbar

            # 定义指标清单: (显示名, 内部key)
            main_inds = [("EMA", "EMA"), ("AVWAP", "AVWAP"), ("MA5/10", "MA5/10"),
                         ("MA20/60", "MA20/60"), ("BOLL", "BOLL")]
            sub_inds = [("成交额", "成交额"), ("MACD", "MACD"), ("KDJ", "KDJ"),
                        ("RSI", "RSI"), ("ATR", "ATR"), ("OBV", "OBV")]

            tk.Label(tb, text="📊主图:", font=("", 9, "bold"),
                     bg="#0f0f23", fg="#FFD54F").pack(side=tk.LEFT, padx=(4, 2))

            def _mk_cb(label, key):
                var = tk.BooleanVar(value=self._mk_indicators.get(key, False))
                self._mk_ind_checks[key] = var
                def _toggle(_v=var, _k=key):
                    self._mk_indicators[_k] = _v.get()
                    self._mk_redraw(kline_host, self._mk_analysis_host,
                                    self._mk_account, self._mk_risk)
                cb = tk.Checkbutton(tb, text=label, variable=var, command=_toggle,
                                    font=("", 9), bg="#0f0f23", fg="#ECEFF1",
                                    activebackground="#0f0f23", activeforeground="#FFD54F",
                                    selectcolor="#455A64", bd=0, highlightthickness=0)
                cb.pack(side=tk.LEFT, padx=1)

            for lab, key in main_inds:
                _mk_cb(lab, key)

            tk.Label(tb, text="  副图:", font=("", 9, "bold"),
                     bg="#0f0f23", fg="#66BB6A").pack(side=tk.LEFT, padx=(10, 2))
            for lab, key in sub_inds:
                _mk_cb(lab, key)

            # 右侧重置默认按钮
            def _reset_inds():
                for k, v in self._mk_indicators.items():
                    self._mk_indicators[k] = k in ["EMA", "AVWAP", "成交额"]
                for k, var in self._mk_ind_checks.items():
                    var.set(self._mk_indicators[k])
                self._mk_redraw(kline_host, self._mk_analysis_host,
                                self._mk_account, self._mk_risk)

            tk.Button(tb, text="🔄默认", font=("", 8),
                      bg="#546E7A", fg="white", relief=tk.FLAT, padx=6,
                      command=_reset_inds).pack(side=tk.RIGHT, padx=4)

            # ── 初始绘制 ──
            self._mk_redraw(kline_host, analysis_host, account_value, risk_pct)

            # 形态分析面板在 redraw 里已经画了
            return

        except Exception as e:
            import traceback
            tk.Label(kline_host, text=f"K线失败: {str(e)[:80]}", font=("", 11),
                     bg="#0f0f23", fg="#EF5350").pack(pady=40)
            print(f"[🎯Martin] K线异常:\n{traceback.format_exc()}", flush=True)

    def _sma(self, arr, period):
        """简单移动平均"""
        out = np.full(len(arr), np.nan)
        for i in range(period - 1, len(arr)):
            out[i] = np.mean(arr[i - period + 1:i + 1])
        return out

    def _boll(self, closes, period=20, k=2):
        """布林带"""
        mid = self._sma(closes, period)
        std = np.full(len(closes), np.nan)
        for i in range(period - 1, len(closes)):
            std[i] = np.std(closes[i - period + 1:i + 1])
        return mid, mid + k * std, mid - k * std

    def _macd(self, closes, fast=12, slow=26, signal=9):
        """MACD"""
        ema_fast = self._ema(closes, fast)
        ema_slow = self._ema(closes, slow)
        dif = ema_fast - ema_slow
        dea = self._ema(dif, signal)
        macd_hist = 2 * (dif - dea)
        return dif, dea, macd_hist

    def _rsi(self, closes, period=14):
        """RSI"""
        deltas = np.diff(closes, prepend=closes[0])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        out = np.full(len(closes), np.nan)
        for i in range(period, len(closes)):
            avg_gain = np.mean(gains[i - period + 1:i + 1])
            avg_loss = np.mean(losses[i - period + 1:i + 1])
            if avg_loss == 0:
                out[i] = 100
            else:
                out[i] = 100 - 100 / (1 + avg_gain / avg_loss)
        return out

    def _kdj(self, highs, lows, closes, n=9, m1=3, m2=3):
        """KDJ"""
        rsv = np.full(len(closes), np.nan)
        for i in range(n - 1, len(closes)):
            hh = np.max(highs[i - n + 1:i + 1])
            ll = np.min(lows[i - n + 1:i + 1])
            rsv[i] = (closes[i] - ll) / (hh - ll) * 100 if hh != ll else 50
        k = np.full(len(closes), 50.0)
        d = np.full(len(closes), 50.0)
        j = np.full(len(closes), 50.0)
        for i in range(1, len(closes)):
            if not np.isnan(rsv[i]):
                k[i] = (m1 - 1) / m1 * k[i - 1] + 1 / m1 * rsv[i]
                d[i] = (m2 - 1) / m2 * d[i - 1] + 1 / m2 * k[i]
                j[i] = 3 * k[i] - 2 * d[i]
            else:
                k[i] = k[i - 1]; d[i] = d[i - 1]; j[i] = j[i - 1]
        return k, d, j

    def _atr(self, highs, lows, closes, period=14):
        """ATR"""
        prev_close = np.roll(closes, 1); prev_close[0] = closes[0]
        tr = np.maximum(highs - lows,
                        np.maximum(np.abs(highs - prev_close), np.abs(lows - prev_close)))
        atr = np.full(len(tr), np.nan)
        for i in range(period - 1, len(tr)):
            atr[i] = np.mean(tr[i - period + 1:i + 1])
        return atr, tr

    def _obv(self, closes, vols):
        """OBV"""
        obv = np.zeros(len(closes))
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                obv[i] = obv[i - 1] + vols[i]
            elif closes[i] < closes[i - 1]:
                obv[i] = obv[i - 1] - vols[i]
            else:
                obv[i] = obv[i - 1]
        return obv

    def _mk_indicator_dialog(self, parent):
        """指标勾选弹窗"""
        win = tk.Toplevel(parent)
        win.title("📊 Martin K线指标设置")
        win.configure(bg="#1a1a3e")
        win.geometry("420x560")
        win.attributes("-topmost", True)
        win.grab_set()

        tk.Label(win, text="🎯 勾选要显示在 K 线图上的指标", font=("", 13, "bold"),
                 bg="#1a1a3e", fg="#FFD54F").pack(pady=(14, 10))

        checks = {}
        groups = [
            ("— 主图叠加 —", ["EMA", "AVWAP", "MA5/10", "MA20/60", "BOLL"], "#FFD54F"),
            ("— 副图指标 —", ["成交额", "MACD", "KDJ", "RSI", "ATR", "OBV"], "#66BB6A"),
        ]
        for title, items, color in groups:
            tk.Label(win, text=title, font=("", 10, "bold"), bg="#1a1a3e", fg=color).pack(anchor="w", padx=20, pady=(8, 2))
            for name in items:
                var = tk.BooleanVar(value=self._mk_indicators.get(name, False))
                c = tk.Checkbutton(win, text=name, variable=var,
                                   font=("", 11), bg="#1a1a3e", fg="#ECEFF1",
                                   activebackground="#1a1a3e", activeforeground="#FFD54F",
                                   selectcolor="#455A64")
                c.pack(anchor="w", padx=30, pady=1)
                checks[name] = var

        def _apply():
            for k, v in checks.items():
                self._mk_indicators[k] = v.get()
            win.destroy()
            # 找到 kline_host 重绘 (向上找两级: PanedWindow.right → kline_host)
            try:
                host = parent
                self._mk_redraw(host, None,
                                getattr(self, "_mk_account", 100000),
                                getattr(self, "_mk_risk", 0.5))
            except Exception as e:
                print(f"[🎯Martin] redraw err: {e}", flush=True)

        def _reset_default():
            for k, v in checks.items():
                checks[k].set(k in ["EMA", "AVWAP", "成交额"])

        btns = tk.Frame(win, bg="#1a1a3e")
        btns.pack(pady=14)
        tk.Button(btns, text="✅ 应用", font=("", 11, "bold"),
                  bg="#4CAF50", fg="white", relief=tk.FLAT, padx=20,
                  command=_apply).pack(side=tk.LEFT, padx=6)
        tk.Button(btns, text="🔄 默认", font=("", 11),
                  bg="#78909C", fg="white", relief=tk.FLAT, padx=14,
                  command=_reset_default).pack(side=tk.LEFT, padx=6)
        tk.Button(btns, text="❌ 取消", font=("", 11),
                  bg="#546E7A", fg="white", relief=tk.FLAT, padx=14,
                  command=win.destroy).pack(side=tk.LEFT, padx=6)

    def _mk_redraw(self, kline_host, analysis_host, account_value, risk_pct):
        """根据 self._mk_indicators 重绘 K 线图"""
        self._mk_account = account_value
        self._mk_risk = risk_pct
        d = self._mk_data
        if d is None:
            return

        # 用缓存的 analysis_host
        if analysis_host is None:
            analysis_host = self._mk_analysis_host

        # 只销毁 kline_host 内部 (canvas), 工具栏在外面独立不碰
        for w in list(kline_host.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

        import matplotlib
        matplotlib.use("TkAgg")
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        import matplotlib.patches as mpatches

        ind = self._mk_indicators
        n = d["n"]; x = np.arange(n)

        # 数副图: 成交额/MACD/KDJ/RSI/ATR/OBV
        sub_list = []
        if ind.get("成交额"): sub_list.append("成交额")
        if ind.get("MACD"): sub_list.append("MACD")
        if ind.get("KDJ"): sub_list.append("KDJ")
        if ind.get("RSI"): sub_list.append("RSI")
        if ind.get("ATR"): sub_list.append("ATR")
        if ind.get("OBV"): sub_list.append("OBV")

        n_axes = 1 + max(len(sub_list), 1)  # 主图 + 至少 1 个副图(成交额或空)
        fig_h = 2.2 + n_axes * 1.2

        fig = Figure(figsize=(11, fig_h), facecolor="#0f0f23", dpi=100)
        gs = fig.add_gridspec(n_axes, 1, height_ratios=[3] + [1] * (n_axes - 1),
                              hspace=0.08)

        ax_main = fig.add_subplot(gs[0], facecolor="#1a1a3e")
        ax_subs = {}
        for i, name in enumerate(sub_list):
            ax_subs[name] = fig.add_subplot(gs[i + 1], facecolor="#1a1a3e", sharex=ax_main)

        closes = d["closes"]; opens = d["opens"]
        highs = d["highs"]; lows = d["lows"]; vols = d["vols"]
        colors_candle = ["#EF5350" if closes[i] >= opens[i] else "#42A5F5" for i in range(n)]

        # 蜡烛
        for i in range(n):
            ax_main.plot([x[i], x[i]], [lows[i], highs[i]], color=colors_candle[i], linewidth=0.5)
            body_bot = min(opens[i], closes[i])
            body_h = max(abs(closes[i] - opens[i]), 0.01)
            ax_main.add_patch(mpatches.Rectangle(
                (x[i] - 0.3, body_bot), 0.6, body_h,
                facecolor=colors_candle[i], edgecolor=colors_candle[i]))

        # 主图叠加
        if ind.get("EMA"):
            ax_main.plot(x, d["ema9"], color="#FFD54F", lw=1.2, label="EMA9")
            ax_main.plot(x, d["ema21"], color="#66BB6A", lw=1.2, label="EMA21")
            ax_main.plot(x, d["ema50"], color="#42A5F5", lw=1.2, label="EMA50")
            v = ~np.isnan(d["ema150"])
            if np.any(v):
                ax_main.plot(x[v], d["ema150"][v], color="#AB47BC", lw=1.0, label="EMA150")

        if ind.get("AVWAP"):
            vw = ~np.isnan(d["avwap"])
            if np.any(vw):
                ax_main.plot(x[vw], d["avwap"][vw], color="#FF7043", lw=1.5, linestyle="--", label="AVWAP")

        if ind.get("MA5/10"):
            ax_main.plot(x, d["sma5"], color="#FFF176", lw=0.9, label="MA5")
            ax_main.plot(x, d["sma10"], color="#80DEEA", lw=0.9, label="MA10")
        if ind.get("MA20/60"):
            ax_main.plot(x, d["sma20"], color="#CE93D8", lw=0.9, label="MA20")
            ax_main.plot(x, d["sma60"], color="#BCAAA4", lw=0.9, label="MA60")

        if ind.get("BOLL"):
            mid, up, lo = self._boll(closes)
            ax_main.plot(x, mid, color="#FFEB3B", lw=0.8, label="BOLL中轨")
            ax_main.plot(x, up, color="#FF9800", lw=0.7, linestyle=":")
            ax_main.plot(x, lo, color="#FF9800", lw=0.7, linestyle=":")
            ax_main.fill_between(x, up, lo, alpha=0.08, color="#FF9800")

        # 主图标题 + 样式
        ax_main.set_title(f'{d["code"]} {d["name"]}', color="white", fontsize=11, fontweight="bold")
        ax_main.legend(loc="upper left", fontsize=7, facecolor="#1a1a3e",
                       edgecolor="#37474F", labelcolor="white")
        ax_main.tick_params(colors="#B0BEC5", labelsize=8, labelbottom=False)
        for s in ax_main.spines.values(): s.set_color("#37474F")
        ax_main.grid(True, color="#37474F", lw=0.3, alpha=0.4)

        # 副图
        def _style_sub(ax, ylabel):
            ax.tick_params(colors="#B0BEC5", labelsize=8)
            if ax != list(ax_subs.values())[-1]:
                ax.tick_params(labelbottom=False)
            for s in ax.spines.values(): s.set_color("#37474F")
            ax.grid(True, color="#37474F", lw=0.3, alpha=0.3)
            ax.set_ylabel(ylabel, color="#B0BEC5", fontsize=8)

        if "成交额" in ax_subs:
            amt = d["vols"] * closes / 1e8
            ax_subs["成交额"].bar(x, amt, color=colors_candle, width=0.6)
            _style_sub(ax_subs["成交额"], "成交额(亿)")

        if "MACD" in ax_subs:
            dif, dea, hist = self._macd(closes)
            hc = ["#EF5350" if v >= 0 else "#42A5F5" for v in hist]
            ax_subs["MACD"].bar(x, hist, color=hc, width=0.6, alpha=0.8)
            ax_subs["MACD"].plot(x, dif, color="#FFD54F", lw=0.9, label="DIF")
            ax_subs["MACD"].plot(x, dea, color="#66BB6A", lw=0.9, label="DEA")
            _style_sub(ax_subs["MACD"], "MACD")
            ax_subs["MACD"].legend(fontsize=7, loc="upper left", facecolor="#1a1a3e",
                                   edgecolor="#37474F", labelcolor="white")

        if "KDJ" in ax_subs:
            k_v, d_v, j_v = self._kdj(highs, lows, closes)
            ax_subs["KDJ"].plot(x, k_v, color="#FFD54F", lw=0.9, label="K")
            ax_subs["KDJ"].plot(x, d_v, color="#66BB6A", lw=0.9, label="D")
            ax_subs["KDJ"].plot(x, j_v, color="#AB47BC", lw=0.8, linestyle="--", label="J")
            ax_subs["KDJ"].axhline(80, color="#EF5350", lw=0.5, linestyle=":")
            ax_subs["KDJ"].axhline(20, color="#42A5F5", lw=0.5, linestyle=":")
            _style_sub(ax_subs["KDJ"], "KDJ")
            ax_subs["KDJ"].legend(fontsize=7, loc="upper left", facecolor="#1a1a3e",
                                  edgecolor="#37474F", labelcolor="white")

        if "RSI" in ax_subs:
            rsi = self._rsi(closes)
            ax_subs["RSI"].plot(x, rsi, color="#FFD54F", lw=0.9)
            ax_subs["RSI"].axhline(70, color="#EF5350", lw=0.5, linestyle=":")
            ax_subs["RSI"].axhline(30, color="#42A5F5", lw=0.5, linestyle=":")
            _style_sub(ax_subs["RSI"], "RSI(14)")

        if "ATR" in ax_subs:
            atr_v, _ = self._atr(highs, lows, closes)
            ax_subs["ATR"].plot(x, atr_v, color="#AB47BC", lw=0.9)
            _style_sub(ax_subs["ATR"], "ATR")

        if "OBV" in ax_subs:
            obv_v = self._obv(closes, vols)
            ax_subs["OBV"].plot(x, obv_v, color="#26C6DA", lw=0.9)
            _style_sub(ax_subs["OBV"], "OBV")

        # X 轴日期 (最后一个副图)
        if sub_list:
            last_ax = list(ax_subs.values())[-1]
            h_dates = d["h"]["date"].astype(str).values
            step = max(1, n // 12)
            last_ax.set_xticks(x[::step])
            last_ax.set_xticklabels([h_dates[i][-5:] for i in x[::step]], rotation=30, fontsize=7, color="#B0BEC5")

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=kline_host)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._mk_canvas = canvas

        # ── 鼠标 hover tooltip (固定屏幕右上) ──
        hover_ttl = [None]   # 用 list 存状态, 避免 nonlocal 复杂嵌套
        hover_ttl_lbl = [None]

        def _mk_hover_motion(event):
            try:
                if event.inaxes is None or event.xdata is None:
                    if hover_ttl[0]: hover_ttl[0].destroy(); hover_ttl[0] = None
                    return
                idx = int(round(event.xdata))
                if idx < 0 or idx >= n:
                    if hover_ttl[0]: hover_ttl[0].destroy(); hover_ttl[0] = None
                    return
                date_str = str(d["h"]["date"].iloc[idx])
                o, c, h, l = opens[idx], closes[idx], highs[idx], lows[idx]
                pct = (c / closes[idx - 1] - 1) * 100 if idx >= 1 and closes[idx - 1] else 0
                amp = (h - l) / o * 100 if o else 0
                vol_y = vols[idx] * c / 1e8

                lines = [
                    f"📅 {date_str}",
                    f"开 {o:.2f}  收 {c:.2f}",
                    f"高 {h:.2f}  低 {l:.2f}",
                    f"涨跌 {pct:+.2f}%  振幅 {amp:.1f}%",
                    f"成交额 {vol_y:.1f}亿",
                ]
                parts = []
                if not np.isnan(d["ema9"][idx]): parts.append(f"E9={d['ema9'][idx]:.2f}")
                if not np.isnan(d["ema21"][idx]): parts.append(f"E21={d['ema21'][idx]:.2f}")
                if not np.isnan(d["ema50"][idx]): parts.append(f"E50={d['ema50'][idx]:.2f}")
                if parts: lines.append("  ".join(parts))
                if not np.isnan(d["avwap"][idx]):
                    lines.append(f"AVWAP={d['avwap'][idx]:.2f}")
                text = "\n".join(lines)

                if hover_ttl[0] is None:
                    hover_ttl[0] = tk.Toplevel(canvas.get_tk_widget())
                    hover_ttl[0].overrideredirect(True)
                    hover_ttl[0].attributes("-topmost", True)
                    hover_ttl[0].configure(bg="#FFD54F", padx=1, pady=1)
                    bg = tk.Frame(hover_ttl[0], bg="#1a1a3e")
                    bg.pack(fill=tk.BOTH, expand=True)
                    hover_ttl_lbl[0] = tk.Label(bg, text="", font=("Menlo", 11),
                                                bg="#1a1a3e", fg="#ECEFF1", justify=tk.LEFT,
                                                anchor="w", padx=10, pady=6)
                    hover_ttl_lbl[0].pack(fill=tk.BOTH, expand=True)

                hover_ttl_lbl[0].configure(text=text)
                hover_ttl[0].lift()
                hover_ttl[0].update_idletasks()
                tw = hover_ttl[0].winfo_reqwidth()
                sw = hover_ttl[0].winfo_screenwidth()
                hover_ttl[0].geometry(f"+{max(0, sw - tw - 10)}+10")
            except Exception:
                if hover_ttl[0]: hover_ttl[0].destroy(); hover_ttl[0] = None

        def _mk_hover_leave(event):
            if hover_ttl[0]: hover_ttl[0].destroy(); hover_ttl[0] = None

        try:
            canvas.mpl_connect("motion_notify_event", _mk_hover_motion)
            canvas.mpl_connect("axes_leave_event", _mk_hover_leave)
        except Exception:
            pass

        # 重绘分析面板 (一次搞定)
        ah = analysis_host or getattr(self, "_mk_analysis_host", None)
        if ah is not None and ah.winfo_exists():
            try:
                for w in ah.winfo_children():
                    w.destroy()
            except Exception:
                pass
            anchor = d["anchor"]
            avg_v = np.mean(d["vols"][-20:]) if n >= 20 else d["vols"][-1]
            pb = self._detect_pullback(d["ema9"], d["ema21"], d["ema50"], closes, d["avwap"], anchor)
            bk = self._detect_breakout(closes, highs, lows, d["vols"], d["avwap"], d["ema9"])
            gp = self._detect_ep_gap(opens[-1], closes[-2] if n >= 2 else closes[-1], d["vols"][-1], avg_v)
            patterns = [p for p in [pb, bk, gp] if p]
            best = max(patterns, key=lambda x: x["score"]) if patterns else None
            self._fill_martin_analysis(
                ah, d["code"], d["name"], closes,
                d["ema9"], d["ema21"], d["ema50"], d["ema150"],
                d["avwap"], d["adr_arr"][-1], best,
                account_value, risk_pct, highs, lows
            )

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
