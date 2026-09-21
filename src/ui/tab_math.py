"""数学/计算/评分"""
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
from utils.network import safe_call
from utils.config import *  # 路径/配置/Token
from data.snapshot import *  # get_news_stocks_* 函数

from datetime import datetime, timedelta
import re
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class MathMixin:
    """数学/计算/评分"""

    def _compute_3min_pct_1m_em(self, code6: str):
        """用最近 4 根 1 分钟 K 的收盘,估算约 3 分钟涨跌幅(%)。"""
        if not AKSHARE_AVAILABLE:
            return None
        import akshare as ak
        code6 = str(code6).zfill(6)
        try:
            df1 = ak.stock_zh_a_hist_min_em(symbol=code6, period="1", adjust="")
        except Exception:
            df1 = None
        if df1 is None or getattr(df1, "empty", True) or len(df1) < 4:
            return None
        close_col = None
        for c in df1.columns:
            cs = str(c)
            if "收盘" in cs or cs == "close":
                close_col = c
                break
        if close_col is None:
            return None
        try:
            c0 = float(df1.iloc[-4][close_col])
            c3 = float(df1.iloc[-1][close_col])
            if not c0:
                return None
            return (c3 - c0) / c0 * 100.0
        except Exception:
            return None

    def _hm_calc_for_stock(self, stock_code):
        """🦅 游资心法单股打分: 拉K线+指标 → 7大游资打分 → 返回dict
        Args:
            stock_code: 6位股票代码 (如 "600519")
        Returns:
            dict: 包含各游资分数、平均、流派、K线指标、情绪阶段
        """
        import os as _os_env
        from datetime import datetime as _dt_now
        from datetime import timedelta as _td

        import tushare as _ts_pro

        # ===== 7 个内嵌打分函数 (从闭包复制) =====
        def _score_zhaoge(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            """赵老哥 - 涨停板战法: 只做强势, 连板优先, 量能配合"""
            dims = []; s = 50
            ma_ok = m5 > m10 > m20
            if ma_ok: s += 20; dims.append(("均线多头", "🟢", "+20"))
            else: s -= 15; dims.append(("均线排列", "🔴", "-15"))
            if vr >= 1.2 and vr <= 3.0: s += 15; dims.append(("量能配合", "🟢", "+15"))
            elif vr > 4: s -= 10; dims.append(("量能", "🟡", "-10 天量"))
            else: dims.append(("量能", "🟡", "0"))
            if pct3 >= -10: s += 10; dims.append(("位置", "🟢", "+10 接近新高"))
            elif pct3 <= -20: s -= 15; dims.append(("位置", "🔴", "-15 深套"))
            else: dims.append(("位置", "🟡", "0"))
            if len(cl) >= 5:
                r5 = (cl[-1] - cl[-5]) / cl[-5] * 100
                if r5 > 8: s += 15; dims.append(("5日涨幅", "🟢", f"+15 ({r5:+.1f}%)"))
                elif r5 < -8: s -= 10; dims.append(("5日涨幅", "🔴", f"-10 ({r5:+.1f}%)"))
                else: dims.append(("5日涨幅", "🟡", "0"))
            return max(0, min(100, s)), dims, "只做强势股, 顺势而为, 不抄底"

        def _score_chai(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            """炒股养家 - 集合竞价/情绪周期: 高换手, 热门题材"""
            dims = []; s = 50
            if tr and tr > 8: s += 15; dims.append(("换手率", "🟢", f"+15 ({tr:.1f}%)"))
            elif tr and tr > 3: dims.append(("换手率", "🟡", "0"))
            else: s -= 10; dims.append(("换手率", "🔴", "-10 低换手"))
            if vr >= 1.5 and vr <= 4: s += 15; dims.append(("量能活跃", "🟢", "+15"))
            else: dims.append(("量能", "🟡", "0"))
            if m5 > m10 > m20: s += 15; dims.append(("均线多头", "🟢", "+15"))
            else: s -= 10; dims.append(("均线", "🔴", "-10"))
            if pct3 > 0: s += 10; dims.append(("新高", "🟢", "+10 创新高"))
            else: dims.append(("位置", "🟡", "0"))
            if len(hi) >= 10:
                amp = (max(hi[-10:]) - min(lo[-10:])) / min(lo[-10:]) * 100
                if amp > 20: s += 10; dims.append(("10日振幅", "🟢", f"+10 ({amp:.1f}%)"))
                elif amp < 8: s -= 5; dims.append(("10日振幅", "🔴", "-5 死水一潭"))
            return max(0, min(100, s)), dims, "情绪周期为王, 高换手热门股优先"

        def _score_fang(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            """方新侠 - 大资金波段: 低吸高抛, 趋势为王"""
            dims = []; s = 50
            if mv and mv > 100: s += 15; dims.append(("市值", "🟢", f"+15 ({mv/1e8:.0f}亿)"))
            elif mv and mv > 30: dims.append(("市值", "🟡", "0"))
            else: s -= 10; dims.append(("市值", "🔴", "-10 偏小"))
            if m5 > m10 > m20 and dma < -3 and dma > -8:
                s += 20; dims.append(("低吸区间", "🟢", f"+20 回调到位 ({dma:+.1f}%)"))
            elif m5 > m10 > m20: s += 10; dims.append(("均线多头", "🟢", "+10"))
            elif m5 < m10 < m20: s -= 20; dims.append(("均线空头", "🔴", "-20"))
            else: dims.append(("均线", "🟡", "0"))
            if pct3 < -15 and pct3 > -30: s += 10; dims.append(("位置", "🟢", f"+10 深跌后 ({pct3:.1f}%)"))
            elif pct3 > 5: s -= 10; dims.append(("位置", "🔴", "-10 偏高追涨"))
            return max(0, min(100, s)), dims, "大资金波段, 低吸高抛, 趋势为王"

        def _score_zhang(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            """章盟主 - 大资金龙头: 低估值, 大成交, 行业龙头"""
            dims = []; s = 50
            if pe and 0 < pe < 30: s += 20; dims.append(("PE估值", "🟢", f"+20 ({pe:.1f})"))
            elif pe and pe > 80: s -= 15; dims.append(("PE估值", "🔴", f"-15 ({pe:.1f} 泡沫)"))
            else: dims.append(("PE", "🟡", "0"))
            if mv and mv > 200: s += 15; dims.append(("大市值", "🟢", f"+15 ({mv/1e8:.0f}亿)"))
            else: dims.append(("市值", "🟡", "0"))
            if vr >= 1.0 and vr <= 2.5: s += 10; dims.append(("量能温和", "🟢", "+10"))
            elif vr > 3.5: s -= 10; dims.append(("量能", "🔴", "-10 天量"))
            if m5 > m20: s += 10; dims.append(("趋势向上", "🟢", "+10"))
            else: s -= 10; dims.append(("趋势", "🔴", "-10"))
            return max(0, min(100, s)), dims, "大资金价值投资, 低估值+行业龙头"

        def _score_ge(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            """葛卫东 - 混沌趋势: 只做大级别趋势, 不预测只跟随"""
            dims = []; s = 50
            if len(cl) >= 60:
                from numpy.polynomial import polynomial as P
                x60 = list(range(60)); y60 = cl[-60:]
                slope = P.polyfit(x60, y60, 1)[1]
                slope_pct = slope / cl[-60] * 100 * 60
                if slope_pct > 20: s += 25; dims.append(("60日斜率", "🟢", f"+25 ({slope_pct:+.1f}%)"))
                elif slope_pct < -20: s -= 20; dims.append(("60日斜率", "🔴", f"-20 ({slope_pct:+.1f}%)"))
                else: dims.append(("60日斜率", "🟡", "0 震荡"))
            if m5 > m10 > m20 > (sum(cl[-60:])/60 if len(cl)>=60 else cl[-1]):
                s += 15; dims.append(("完美多头", "🟢", "+15"))
            elif m5 < m10 < m20: s -= 15; dims.append(("空头排列", "🔴", "-15"))
            return max(0, min(100, s)), dims, "混沌理论, 只跟随大级别趋势, 不预测"

        def _score_xin(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            """作手新一 - 新生代情绪: 情绪周期, 快速止损"""
            dims = []; s = 50
            if len(cl) >= 3:
                r3 = (cl[-1] - cl[-3]) / cl[-3] * 100
                if r3 > 5: s += 15; dims.append(("3日涨幅", "🟢", f"+15 ({r3:+.1f}%)"))
                elif r3 < -5: s -= 10; dims.append(("3日涨幅", "🔴", f"-10 ({r3:+.1f}%)"))
            if tr and tr > 5: s += 15; dims.append(("换手率", "🟢", f"+15 ({tr:.1f}%)"))
            elif tr and tr < 1: s -= 10; dims.append(("换手率", "🔴", "-10 死水"))
            if vr >= 1.5: s += 10; dims.append(("量能放大", "🟢", "+10"))
            else: dims.append(("量能", "🟡", "0"))
            if m5 > m10 > m20: s += 10; dims.append(("均线多头", "🟢", "+10"))
            else: s -= 5; dims.append(("均线", "🟡", "-5"))
            if pct3 > -5: s += 10; dims.append(("创新高", "🟢", "+10"))
            elif pct3 < -15: s -= 10; dims.append(("深套", "🔴", "-10"))
            return max(0, min(100, s)), dims, "情绪周期+龙头战法, 快速止损不扛单"

        def _score_rhx(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv):
            """瑞鹤仙 - 只做强势, 均线多头, 量能活跃, 不追高"""
            dims = []; s = 50
            if m5 > m10 > m20: s += 25; dims.append(("均线多头", "🟢", "+25"))
            elif m5 < m10 < m20: s -= 25; dims.append(("均线空头", "🔴", "-25"))
            else: dims.append(("均线", "🟡", "0"))
            if 1.0 <= vr <= 2.0: s += 15; dims.append(("量能活跃", "🟢", "+15"))
            elif vr < 0.6: s -= 10; dims.append(("量能", "🔴", "-10 冷门"))
            elif vr > 3.0: s -= 15; dims.append(("量能", "🔴", "-15 天量"))
            if dma > 10: s -= 20; dims.append(("追高风险", "🔴", f"-20 ({dma:+.1f}%)"))
            elif -3 <= dma <= 3: s += 8; dims.append(("位置合理", "🟢", f"+8 ({dma:+.1f}%)"))
            if pct3 > -5: s += 10; dims.append(("接近新高", "🟢", f"+10 ({pct3:+.1f}%)"))
            elif pct3 < -20: s -= 15; dims.append(("深套", "🔴", f"-15 ({pct3:.1f}%)"))
            return max(0, min(100, s)), dims, "只做强势, 量能活跃, 不追高, 纪律至上"

        TRA_TO_SCHOOL = {
            "赵老哥": "龙头战法流",
            "炒股养家": "情绪周期流",
            "方新侠": "趋势波段流",
            "章盟主": "趋势波段流",
            "葛卫东": "趋势波段流",
            "作手新一": "低吸反包流",
            "瑞鹤仙": "龙头战法流",
        }

        SCHOOL_DESCS = {
            "龙头战法流": "二板定龙+弱转强+分歧一致",
            "情绪周期流": "情绪阶段(冰点→高潮)+仓位管理",
            "趋势波段流": "主升持有+下降通道空仓",
            "低吸反包流": "强势股缩量回踩+资金回流",
            "首板隔日套利流": "打首板隔日必走",
            "分仓复利悟道流": "账户风控总闸+连亏熔断",
        }

        # ===== 主逻辑 =====
        try:
            pure = str(stock_code).strip()

            # ===== 用 akshare 拉K线 (新浪 + 直连兜底) =====
            from ui._akshare_fetcher import fetch_daily_kline, fetch_realtime_basic

            daily = fetch_daily_kline(pure, days=250)
            if daily is None or len(daily) < 60:
                return {"scores": {}, "avg_score": None, "error": f"K线不足60根, 只有{len(daily) if daily is not None else 0}"}
            daily = daily.tail(80).reset_index(drop=True)
            stock_name = pure

            # 新浪有 turnover (小数) → 换算成百分比
            tr = None; pe = None; mv = None
            if "turnover" in daily.columns:
                _tr_val = daily.iloc[-1].get("turnover")
                if _tr_val is not None and str(_tr_val) not in ("nan", "NaN", ""):
                    try: tr = float(_tr_val) * 100
                    except: pass
            # PE/市值尝试从实时行情拿 (东财 spot_em, 网络封就 None)
            _rt = fetch_realtime_basic(pure)
            pe = _rt.get("pe"); mv = _rt.get("mv")

            # 提取数组
            cl = daily["close"].tolist()
            hi = daily["high"].tolist()
            lo = daily["low"].tolist()
            vo = daily["volume"].tolist()
            op = daily["open"].tolist()

            # 计算 MA
            def _ma(n):
                if len(cl) < n: return cl[-1]
                return sum(cl[-n:]) / n

            m5 = _ma(5); m10 = _ma(10); m20 = _ma(20)

            # VR 量比 (今日量 / 前5日均量)
            if len(vo) >= 6:
                vr = vo[-1] / max(sum(vo[-6:-1]) / 5, 1)
            else:
                vr = 1.0

            # DMA (close 相对 MA20 偏离%)
            dma = (cl[-1] - m20) / m20 * 100 if m20 else 0.0

            # PCT3 (距60日高点%)
            if len(hi) >= 60:
                h60 = max(hi[-60:])
            else:
                h60 = max(hi)
            pct3 = (cl[-1] - h60) / h60 * 100 if h60 else 0.0

            # ===== 调用 7 个打分函数 =====
            scorers = [
                ("赵老哥", _score_zhaoge),
                ("炒股养家", _score_chai),
                ("方新侠", _score_fang),
                ("章盟主", _score_zhang),
                ("葛卫东", _score_ge),
                ("作手新一", _score_xin),
                ("瑞鹤仙", _score_rhx),
            ]

            scores_out = {}
            total_score = 0
            for name, fn in scorers:
                sc, dims, phi = fn(cl, hi, lo, vo, op, vr, dma, pct3, m5, m10, m20, tr, pe, mv)
                school = TRA_TO_SCHOOL.get(name, "趋势波段流")
                scores_out[name] = {
                    "score": int(sc),
                    "dims": dims,
                    "phi": phi,
                    "desc": SCHOOL_DESCS.get(school, ""),
                }
                total_score += sc

            avg_score = int(total_score / len(scorers)) if scorers else 0

            # best_sch: 按流派聚合取平均分最高
            sch_scores = {}
            for name, info in scores_out.items():
                sch = TRA_TO_SCHOOL.get(name, "趋势波段流")
                sch_scores.setdefault(sch, []).append(info["score"])
            best_sch = max(sch_scores, key=lambda s: sum(sch_scores[s]) / max(len(sch_scores[s]), 1)) if sch_scores else "--"

            # 情绪阶段 (简化用 DMA 判断)
            if dma > 5:
                emo_stage = "高潮"
            elif dma > 0:
                emo_stage = "发酵"
            elif dma > -5:
                emo_stage = "退潮"
            else:
                emo_stage = "冰点"

            result = {
                "name": stock_name,
                "code": pure,
                "ts_code": ts_code,
                "scores": scores_out,
                "avg_score": avg_score,
                "best_sch": best_sch,
                "tra_to_school": TRA_TO_SCHOOL,
                "kline_info": {
                    "m5": round(m5, 3), "m10": round(m10, 3), "m20": round(m20, 3),
                    "vr": round(vr, 3), "dma": round(dma, 2), "pct3": round(pct3, 2),
                    "tr": round(tr, 2) if tr is not None else None,
                    "pe": round(pe, 2) if pe is not None else None,
                    "mv": round(mv, 2) if mv is not None else None,
                },
                "emo_stage": emo_stage,
            }

            # 写入缓存
            if not hasattr(self, '_hm_scores_cache'):
                self._hm_scores_cache = {}
            self._hm_scores_cache[pure] = avg_score

            return result

        except Exception as e:
            return {"scores": {}, "avg_score": None, "error": str(e)}

    def _compute_daily_support_resistance_line_prices(self, kline_data):
        """与日K图一致的枢轴支撑/压力算法,返回最后一根K线处的线价(若无绘制则 None)。
        Returns:
            dict: close, support_price, resistance_price
        """
        out = {'close': None, 'support_price': None, 'resistance_price': None}
        try:
            data = kline_data['data']
            ma_values = kline_data['ma_values']
            n = len(data)
            if n < 3:
                return out
            closes = data['收盘'].values
            highs = data['最高'].values
            lows = data['最低'].values
            out['close'] = float(closes[-1])
            uptrend = False
            downtrend = False
            if 'ma20' in ma_values and len(ma_values['ma20']) >= 6:
                m20 = np.asarray(ma_values['ma20'], dtype=float)
                uptrend = bool(m20[-1] > m20[-6])
                downtrend = bool(m20[-1] < m20[-6])
            elif n >= 12:
                uptrend = bool(closes[-1] > closes[-11])
                downtrend = bool(closes[-1] < closes[-11])
            piv_lo = [i for i in range(1, n - 1) if lows[i] <= lows[i - 1] and lows[i] <= lows[i + 1]]
            piv_hi = [i for i in range(1, n - 1) if highs[i] >= highs[i - 1] and highs[i] >= highs[i + 1]]
            x_end = float(n - 1)
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
                        out['support_price'] = float(y0 + m * (x_end - x0))
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
                        out['resistance_price'] = float(y0 + m * (x_end - x0))
        except Exception:
            pass
        return out


__all__ = ["MathMixin"]
