"""嵌套类 + 类属性"""
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

import os
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class InnerClassMixin:
    """嵌套类 _SingleAnalysis + 类属性常量"""

    class _SingleAnalysis:
        def __init__(self, gui, data):
            self.gui = gui
            self.data = data
            self.win = tk.Toplevel()
            self.name = data.get("name", "?")
            self.code = data.get("code", "?")
            self.ts_code = data.get("ts_code", "")
            self.score = data.get("score", 50)
            self.supp = data.get("supp", "N/A")
            self.resi = data.get("resi", "N/A")
            self.price = data.get("price", "-")
            self.vol_r = data.get("vol_ratio", "-")
            self.dev_m = data.get("dev_ma20", "-")
            self.rhx_score = data.get("rhx_score", 50)
            self.rhx_tag = data.get("rhx_tag", "")
            # 利弗莫尔数据
            self.lm_tag = data.get("lm_tag", "")
            self.lm_trend_dir = data.get("lm_trend_dir", "震荡")
            self.lm_sl_str = data.get("lm_sl_str", "")
            self.lm_eff_sl = data.get("lm_eff_sl", 0)
            # 从 dev_m 算均线方向 (瑞鹤仙用)
            self._rhx_ma_dir = "多" if data.get("ma5",0) > data.get("ma10",0) > data.get("ma20",0) else ("空" if data.get("ma5",0) < data.get("ma10",0) < data.get("ma20",0) else "震")
        def show(self):
            import threading
            from datetime import datetime as _dt
            from tkinter import scrolledtext, ttk

            import tushare as _ts_pro
            w = self.win
            w.title(f"🔍 {self.name}({self.code}) · 6维风险分析")
            w.geometry("1080x800"); w.lift(); w.focus_force()
            light = "🔴" if self.score < 40 else ("🟡" if self.score < 65 else "🟢")
            tk.Label(w, text=f"📊 {self.name}({self.code})  现价 {self.price}  评分 {self.score}/100 {light}",
                     bg="#EDE7F6", fg="#4527A0", font=("", 12, "bold"),
                     height=2).pack(fill=tk.X)
            # 双层 PanedWindow: 外层垂直(上下), 内层水平(左右)
            outer = tk.PanedWindow(w, orient=tk.VERTICAL, sashwidth=5); outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
            top = tk.Frame(outer, bg="white"); outer.add(top, minsize=240)
            bottom = tk.Frame(outer, bg="white"); outer.add(bottom, minsize=280)
            top_pw = tk.PanedWindow(top, orient=tk.HORIZONTAL, sashwidth=5); top_pw.pack(fill=tk.BOTH, expand=True)
            top_left = tk.Frame(top_pw, bg="white"); top_pw.add(top_left, width=380)
            top_right = tk.Frame(top_pw, bg="white"); top_pw.add(top_right)
            bot_pw = tk.PanedWindow(bottom, orient=tk.HORIZONTAL, sashwidth=5); bot_pw.pack(fill=tk.BOTH, expand=True)
            bot_left = tk.Frame(bot_pw, bg="white"); bot_pw.add(bot_left, width=480)
            bot_right = tk.Frame(bot_pw, bg="white"); bot_pw.add(bot_right)
            tk.Label(top_left, text="📡 6维信号", bg="white", fg="#333", font=("", 11, "bold")).pack(anchor="w", padx=6, pady=(6, 2))
            st = ttk.Treeview(top_left, columns=("v","val","j"), show="headings", height=10)
            st.heading("v",text="维度"); st.heading("val",text="值"); st.heading("j",text="判定")
            st.column("v",width=70); st.column("val",width=70); st.column("j",width=75)
            for t, bg in [("r","#FFEBEE"),("y","#FFFDE7"),("g","#E8F5E9")]:
                st.tag_configure(t, background=bg)
            st.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            def _sr(dim, val, c, desc):
                icon = {"red":"🔴","yellow":"🟡","green":"🟢"}.get(c,"⚫")
                t = {"red":"r","yellow":"y","green":"g"}.get(c,"")
                st.insert("", tk.END, values=(dim, val, f"{icon} {desc}"), tags=(t,))
            vr = float(self.vol_r) if self.vol_r != "-" else 1
            if vr > 2: _sr("量比", self.vol_r, "red", "放量过热")
            elif vr > 1.2: _sr("量比", self.vol_r, "yellow", "温和放量")
            elif vr < 0.5: _sr("量比", self.vol_r, "yellow", "缩量")
            else: _sr("量比", self.vol_r, "green", "正常")
            try:
                dv = float(str(self.dev_m).replace("%",""))
                if abs(dv) > 12: _sr("偏离MA20", self.dev_m, "red", "超买/超跌")
                elif abs(dv) > 5: _sr("偏离MA20", self.dev_m, "yellow", "偏高/偏低")
                else: _sr("偏离MA20", self.dev_m, "green", "正常")
            except: _sr("偏离MA20", self.dev_m, "yellow", "-")
            # 从 tushare 补维度 3-6
            def _more_dims():
                try:
                    df_k = _ts_pro.pro_api().daily(ts_code=self.ts_code, start_date="20251001",
                                                   end_date=_dt.now().strftime("%Y%m%d"))
                    if df_k is not None and len(df_k):
                        df_k = df_k.sort_values("trade_date")
                        closes = df_k["close"].astype(float).tolist()
                        pct = round(float(df_k.iloc[-1]["pct_chg"]), 2)
                        if pct > 7 or pct < -7: _sr("涨跌幅", f"{pct:+.2f}%", "red", "大涨/暴跌")
                        elif abs(pct) > 2: _sr("涨跌幅", f"{pct:+.2f}%", "yellow", "明显涨跌")
                        else: _sr("涨跌幅", f"{pct:+.2f}%", "green", "平稳")
                        ma5 = sum(closes[-5:])/5 if len(closes)>=5 else self.price
                        ma10 = sum(closes[-10:])/10 if len(closes)>=10 else self.price
                        ma20 = sum(closes[-20:])/20 if len(closes)>=20 else self.price
                        if ma5 > ma10 > ma20: _sr("均线排列", "多", "green", "多头")
                        elif ma5 < ma10 < ma20: _sr("均线排列", "空", "red", "空头")
                        else: _sr("均线排列", "震", "yellow", "震荡")
                except: pass
                _sr("支撑位", self.supp, "yellow", "关键支撑")
                _sr("阻力位", self.resi, "yellow", "关键阻力")
                _sr("综合评分", f"{self.score}/100",
                    "red" if self.score<40 else ("yellow" if self.score<65 else "green"),
                    "危险减仓" if self.score<40 else ("警惕观望" if self.score<65 else "安全持有"))
                # 瑞鹤仙心法维度
                rs = int(self.rhx_score) if self.rhx_score not in ("-", None, "") else 50
                if rs >= 70: _sr("瑞鹤仙", f"{rs}/100", "green", "✅强势可做")
                elif rs >= 50: _sr("瑞鹤仙", f"{rs}/100", "yellow", "⚠️观察等待")
                else: _sr("瑞鹤仙", f"{rs}/100", "red", "❌坚决回避")
                # 利弗莫尔四支柱维度
                _lm_t = self.lm_tag or "⏸️无数据"
                _lm_s = self.lm_sl_str or "-"
                if _lm_t.startswith(("✅", "🔺")):
                    _sr("利弗莫尔", self.lm_trend_dir, "green", _lm_t)
                elif _lm_t.startswith(("🔻", "🚫")):
                    _sr("利弗莫尔", self.lm_trend_dir, "red", _lm_t)
                else:
                    _sr("利弗莫尔", self.lm_trend_dir, "yellow", _lm_t)
                _sr("止损位", _lm_s.split("(")[0] if _lm_s != "-" else "-",
                    "red" if _lm_s.startswith("止损") else "yellow",
                    f"利弗莫尔{_lm_s}")
            _more_dims()
            # ===== 瑞鹤仙心法快速判断卡片 =====
            rhx_card = tk.Frame(top_right, bg="#E8EAF6", relief=tk.FLAT, bd=2)
            rhx_card.pack(fill=tk.X, padx=6, pady=(8, 4))
            tk.Label(rhx_card, text="🦅 瑞鹤仙心法", bg="#3949AB", fg="white",
                     font=("", 10, "bold")).pack(fill=tk.X, pady=(2, 2))
            rs_big = int(self.rhx_score) if self.rhx_score not in ("-", None, "") else 50
            if rs_big >= 70:
                rhx_col, rhx_txt = "#2E7D32", f"✅ 强势可做 ({rs_big}/100)"
            elif rs_big >= 50:
                rhx_col, rhx_txt = "#F57F17", f"⚠️ 观察等待 ({rs_big}/100)"
            else:
                rhx_col, rhx_txt = "#C62828", f"❌ 坚决回避 ({rs_big}/100)"
            tk.Label(rhx_card, text=rhx_txt, bg="#E8EAF6", fg=rhx_col,
                     font=("", 14, "bold")).pack(pady=(4, 2))
            rhx_detail = (f"均线{self._rhx_ma_dir} | 量比{self.vol_r} | "
                          f"偏离MA20 {self.dev_m} | 只做强势·量能活跃·不追高")
            tk.Label(rhx_card, text=rhx_detail, bg="#E8EAF6", fg="#333",
                     font=("", 8), justify=tk.LEFT).pack(pady=(0, 4))
            # ===== 利弗莫尔四支柱卡片 =====
            lm_card = tk.Frame(top_right, bg="#E0F2F1", relief=tk.FLAT, bd=2)
            lm_card.pack(fill=tk.X, padx=6, pady=(4, 4))
            tk.Label(lm_card, text="📐 利弗莫尔四支柱", bg="#00695C", fg="white",
                     font=("", 10, "bold")).pack(fill=tk.X, pady=(2, 2))
            lm_tag_display = self.lm_tag or "⏸️无数据"
            if lm_tag_display.startswith("✅"): lm_main_col = "#2E7D32"
            elif lm_tag_display.startswith("🔺"): lm_main_col = "#1565C0"
            elif lm_tag_display.startswith(("🔻", "🚫")): lm_main_col = "#C62828"
            else: lm_main_col = "#F57F17"
            tk.Label(lm_card, text=lm_tag_display, bg="#E0F2F1", fg=lm_main_col,
                     font=("", 14, "bold")).pack(pady=(4, 2))
            lm_sl_display = self.lm_sl_str or ""
            lm_detail_parts = [f"最小阻力线 {self.lm_trend_dir}"]
            if lm_sl_display: lm_detail_parts.append(lm_sl_display)
            lm_detail_parts.append("金字塔20%试仓·盈利10%加仓·永不满仓")
            tk.Label(lm_card, text=" | ".join(lm_detail_parts), bg="#E0F2F1", fg="#333",
                     font=("", 8), justify=tk.LEFT).pack(pady=(0, 4))
            # ===== 凯利公式卡片 =====
            kelly_card = tk.Frame(top_right, bg="#FFF8E1", relief=tk.FLAT, bd=2)
            kelly_card.pack(fill=tk.X, padx=6, pady=(4, 6))
            tk.Label(kelly_card, text="📐 凯利公式仓位建议", bg="#FFB300", fg="white",
                     font=("", 10, "bold")).pack(fill=tk.X, pady=(2, 2))
            # 凯利结果大字体占位 (后台线程算完填进去)
            kelly_result_var = tk.StringVar(value="⏳ 计算中...")
            tk.StringVar(value="#888")
            kelly_big = tk.Label(kelly_card, textvariable=kelly_result_var,
                                 bg="#FFF8E1", fg="#888",
                                 font=("", 16, "bold"))
            kelly_big.pack(pady=(4, 2))
            # 公式细节 (小字体)
            kelly_detail = tk.Label(kelly_card, text="f = (bp - q) / b",
                                    bg="#FFF8E1", fg="#555", font=("", 9), justify=tk.LEFT)
            kelly_detail.pack(pady=(0, 4))
            def _calc_kelly(closes_list):
                """用历史涨跌幅估计凯利: b=平均盈/平均亏, p=上涨概率"""
                if not closes_list or len(closes_list) < 10:
                    return None, None, None, None
                rets = [(closes_list[i] - closes_list[i-1]) / closes_list[i-1]
                        for i in range(1, len(closes_list))]
                ups = [r for r in rets if r > 0]
                dns = [r for r in rets if r < 0]
                if not ups or not dns:
                    return None, None, None, None
                avg_win = sum(ups) / len(ups)       # 平均涨幅
                avg_loss = abs(sum(dns) / len(dns)) # 平均跌幅
                b = avg_win / avg_loss if avg_loss > 0 else 0
                p = len(ups) / len(rets)             # 胜率
                q = 1 - p
                f = (b * p - q) / b if b > 0 else 0   # 凯利比例
                return f, b, p, avg_win, avg_loss
            def _go_kelly():
                try:
                    df_k = _ts_pro.pro_api().daily(ts_code=self.ts_code,
                                                    start_date="20250301",
                                                    end_date=_dt.now().strftime("%Y%m%d"))
                    if df_k is None or len(df_k) < 20:
                        w.after(0, lambda: (
                            kelly_result_var.set("数据不足"),
                            kelly_big.config(fg="#888")
                        ))
                        return
                    df_k = df_k.sort_values("trade_date")
                    closes = df_k["close"].astype(float).tolist()
                    rets = [(closes[i] - closes[i-1]) / closes[i-1]
                            for i in range(1, len(closes))]
                    ups = [r for r in rets if r > 0]
                    dns = [r for r in rets if r < 0]
                    if not ups or not dns:
                        w.after(0, lambda: (
                            kelly_result_var.set("波动太小"),
                            kelly_big.config(fg="#888")
                        ))
                        return
                    avg_win = sum(ups) / len(ups)
                    avg_loss = abs(sum(dns) / len(dns))
                    b = avg_win / avg_loss if avg_loss > 0 else 0
                    p = len(ups) / len(rets)
                    q = 1 - p
                    f = (b * p - q) / b if b > 0 else 0
                    # 上界截断到 25% (避免过激)
                    f_display = max(-0.05, min(0.25, f))
                    # 颜色 + 大文字
                    if f >= 0.15:
                        col = "#2E7D32"; label = f"✅ 建议重仓 {f_display:.1%}"
                    elif f >= 0.05:
                        col = "#F57F17"; label = f"⚠️ 建议轻仓 {f_display:.1%}"
                    elif f > 0:
                        col = "#EF6C00"; label = f"⚠️ 极轻仓 {f_display:.1%}"
                    else:
                        col = "#C62828"; label = "❌ 不建议参与 0%"
                    detail = (f"b={b:.2f} 盈亏比  p={p:.1%} 胜率  "
                              f"avg_win={avg_win:.2%}  avg_loss={avg_loss:.2%}\n"
                              f"f = ({b:.2f}×{p:.1%} - {q:.1%}) / {b:.2f} = {f:.4f}")
                    w.after(0, lambda: (
                        kelly_result_var.set(label),
                        kelly_big.config(fg=col),
                        kelly_detail.config(text=detail)
                    ))
                except Exception as e:
                    w.after(0, lambda e=e: (
                        kelly_result_var.set("计算失败"),
                        kelly_big.config(fg="#888"),
                        kelly_detail.config(text=str(e)[:60])
                    ))
            threading.Thread(target=_go_kelly, daemon=True).start()
            tk.Label(bot_left, text="🤖 AI 深度解读", bg="white", fg="#333", font=("", 11, "bold")).pack(anchor="w", padx=6, pady=(6,2))
            ai = scrolledtext.ScrolledText(bot_left, font=("", 10), wrap=tk.WORD, height=10, bg="#FAFAFA")
            ai.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0,4))
            ai.tag_configure("rg", foreground="#C62828", background="#FFEBEE")
            ai.tag_configure("yg", foreground="#F57F17", background="#FFFDE7")
            ai.tag_configure("gg", foreground="#2E7D32", background="#E8F5E9")
            ai.insert(tk.END, "⏳ AI 分析中 + 拉日K线图...")
            ai.config(state=tk.DISABLED)
            def _go():
                def w2():
                    try:
                        df_k2 = _ts_pro.pro_api().daily(ts_code=self.ts_code, start_date="20251001",
                                                        end_date=_dt.now().strftime("%Y%m%d"))
                        closes_s = ",".join([f"{round(float(c),2)}" for c in df_k2["close"].tolist()[-60:]]) if df_k2 is not None and len(df_k2) else ""
                    except: closes_s = ""
                    # 拉均线算瑞鹤仙需要的数据
                    ma_str = ""
                    try:
                        df_m = _ts_pro.pro_api().daily(ts_code=self.ts_code, start_date="20250601",
                                                       end_date=_dt.now().strftime("%Y%m%d"))
                        if df_m is not None and len(df_m):
                            df_m = df_m.sort_values("trade_date")
                            cls = df_m["close"].astype(float).tolist()
                            ma5_v = sum(cls[-5:])/5 if len(cls)>=5 else 0
                            ma10_v = sum(cls[-10:])/10 if len(cls)>=10 else 0
                            ma20_v = sum(cls[-20:])/20 if len(cls)>=20 else 0
                            ma_dir = "多头" if ma5_v>ma10_v>ma20_v else ("空头" if ma5_v<ma10_v<ma20_v else "震荡")
                            ma_str = f"MA5={ma5_v:.2f} MA10={ma10_v:.2f} MA20={ma20_v:.2f} 排列={ma_dir}"
                    except: pass
                    prompt = f"""对 {self.name}({self.code}) 做 6 维风险评估 + 瑞鹤仙心法点评。现价 {self.price}, 综合评分 {self.score}/100, 瑞鹤仙分 {self.rhx_score}/100 ({self.rhx_tag})。
支撑 {self.supp} | 阻力 {self.resi} | 量比 {self.vol_r} | 偏离MA20 {self.dev_m}。{ma_str}
近60日收盘: {closes_s[:400]}
请按以下结构输出:
1. 定性 (涨/跌/震荡)
2. 瑞鹤仙心法点评 (核心! 用瑞鹤仙24条心法判断: 是否强势? 量能? 均线? 位置? 给明确的"可做/观察/回避"结论 + 一句心法引用)
3. 能否做T
4. 是否持仓 (结合瑞鹤仙结论)
5. 基本面+技术面
6. 资金面+情绪面
🎯 一句话 (必须引用瑞鹤仙某条心法)"""
                    try:
                        res = self.gui.call_ai_model(prompt,
                            system_prompt="你是 rocket-scan 方法论 + 瑞鹤仙24条心法 双重认证的持仓风险分析师。瑞鹤仙心法核心: 只做强势、均线多头、量能活跃、不追高、分批试仓、纪律至上。每次分析必须引用至少一条瑞鹤仙心法原文。", max_tokens=2000)
                    except Exception as e: res = f"❌ AI 失败: {e}"
                    w.after(0, lambda: _render(res))
                    # K线
                    try:
                        import matplotlib; matplotlib.use("TkAgg")
                        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                        from matplotlib.figure import Figure
                        df_k3 = _ts_pro.pro_api().daily(ts_code=self.ts_code, start_date="20250901",
                                                        end_date=_dt.now().strftime("%Y%m%d"))
                        if df_k3 is not None and len(df_k3):
                            df_k3 = df_k3.sort_values("trade_date")
                            # 先清空 bot_right 旧图
                            for _c in bot_right.winfo_children(): _c.destroy()
                            # 顶部工具栏: 标题 + 斐波那契按钮
                            kf_tool = tk.Frame(bot_right, bg="white"); kf_tool.pack(fill=tk.X, padx=6, pady=(6,2))
                            tk.Label(kf_tool, text="📈 日K线图", bg="white", fg="#333", font=("", 11, "bold")).pack(side=tk.LEFT)
                            fib_btn = tk.Button(kf_tool, text="📐 斐波那契 0.7/0.786", bg="#FF6F00", fg="white",
                                                font=("", 9, "bold"), relief=tk.FLAT, padx=8, cursor="hand2")
                            fib_btn.pack(side=tk.RIGHT)
                            kf = tk.Frame(bot_right, bg="white"); kf.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
                            opens = df_k3["open"].astype(float).tolist()
                            cs = df_k3["close"].astype(float).tolist()
                            hs = df_k3["high"].astype(float).tolist()
                            ls = df_k3["low"].astype(float).tolist()
                            vs = df_k3["vol"].astype(float).tolist() if "vol" in df_k3.columns else [0]*len(cs)
                            x = list(range(len(cs)))
                            ds = df_k3["trade_date"].tolist()
                            cols = ["#C62828" if c >= o else "#2E7D32" for c, o in zip(cs, opens)]
                            def _ma(a, n): return [sum(a[i-n:i])/n for i in range(n,len(a))] if len(a)>=n else None
                            m5=_ma(cs,5); m10=_ma(cs,10); m20=_ma(cs,20); m60=_ma(cs,60)
                            step = max(1, len(cs)//8)
                            date_labels = [d[4:6]+"/"+d[6:] for d in ds[::step]]
                            date_ticks = x[::step]
                            # ===== 预计算所有指标 =====
                            # MACD (12,26,9)
                            def _ema(a, n):
                                    if len(a)<n: return None
                                    ema_val = sum(a[:n])/n
                                    k = 2/(n+1)
                                    out = [None]*(n-1) + [ema_val]
                                    for v in a[n:]:
                                        ema_val = v*k + ema_val*(1-k)
                                        out.append(ema_val)
                                        return out
                            ema12 = _ema(cs,12); ema26 = _ema(cs,26)
                            dif = [(e1-e2) if e1 and e2 else None for e1,e2 in zip(ema12,ema26)]
                            dif_valid = [d if d else 0 for d in dif]
                            dea = _ema(dif_valid, 9) if len(dif_valid)>=9 else None
                            macd_hist = [(d-e)*2 if d and e else 0 for d,e in zip(dif, dea)] if dif and dea else None
                                # BIAS (6,12,24)
                            def _bias(a, n):
                                    m = _ma(a,n)
                                    if not m: return None
                                    return [(a[n+i]-m[i])/m[i]*100 for i in range(len(m))]
                            bias6 = _bias(cs,6); bias12 = _bias(cs,12); bias24 = _bias(cs,24)
                            # KDJ (9,3,3)
                            def _kdj(h,l,c, n=9, m1=3, m2=3):
                                    rsv = [None]*(n-1)
                                    for i in range(n-1, len(c)):
                                        hn = max(h[i-n+1:i+1]); ln = min(l[i-n+1:i+1])
                                        rsv.append((c[i]-ln)/(hn-ln)*100 if hn!=ln else 50)
                                        k = d = j = [None]*len(rsv)
                                        k[n-1]=50; d[n-1]=50
                                    for i in range(n, len(rsv)):
                                        if rsv[i] is None: continue
                                    k[i] = (2/3)*k[i-1] + (1/3)*rsv[i]
                                    d[i] = (2/3)*d[i-1] + (1/3)*k[i]
                                    j[i] = 3*k[i] - 2*d[i]
                                    return k, d, j
                            k_kdj, d_kdj, j_kdj = _kdj(hs, ls, cs)
                            # ===== 构建图形函数 =====
                            def _build_fig(indicators):
                                    # indicators: list of "VOL","MACD","BIAS","KDJ"
                                    n_panels = 1 + len(indicators)  # 1 K线 + N 指标
                                    heights = [3] + [1.2]*len(indicators)
                                    hspace = 0.08
                                    total_h = 3.5 + 1.2*len(indicators)
                                    local_fig = Figure(figsize=(10, total_h), dpi=100, facecolor="#FAFAFA")
                                    import matplotlib.gridspec as gs
                                    gs_spec = gs.GridSpec(n_panels, 1, height_ratios=heights, hspace=hspace, top=0.95, bottom=0.05)
                                    local_axs = [local_fig.add_subplot(gs_spec[i], facecolor="#FAFAFA") for i in range(n_panels)]
                                    # 所有面板共享 x 轴
                                    for i in range(1, n_panels):
                                        local_axs[i].sharex(local_axs[0])
                                        # ---- K线 (主图) ----
                                        ax_main = local_axs[0]
                                        ax_main.bar(x, [h-l for h,l in zip(hs,ls)], bottom=ls, width=0.6, color=cols, alpha=0.5)
                                        ax_main.bar(x, [abs(c-o) for c,o in zip(cs,opens)],
                                                bottom=[min(c,o) for c,o in zip(cs,opens)], width=0.6, color=cols)
                                    if m5: ax_main.plot(range(5,len(cs)), m5, color="#FF9800", lw=1, label="MA5")
                                    if m10: ax_main.plot(range(10,len(cs)), m10, color="#9C27B0", lw=1, label="MA10")
                                    if m20: ax_main.plot(range(20,len(cs)), m20, color="#2196F3", lw=1, label="MA20")
                                    if m60: ax_main.plot(range(60,len(cs)), m60, color="#795548", lw=1, label="MA60")
                                    try:
                                        if self.supp!="N/A": ax_main.axhline(y=float(self.supp), color="#4CAF50", ls="--", lw=1, label=f"支撑{self.supp}")
                                        if self.resi!="N/A": ax_main.axhline(y=float(self.resi), color="#F44336", ls="--", lw=1, label=f"阻力{self.resi}")
                                    except: pass
                                    ax_main.set_title(f"{self.name}({self.code}) 日K+MA+支撑阻力", fontsize=10)
                                    ax_main.legend(fontsize=6, loc="upper left", ncol=4); ax_main.grid(True, alpha=0.2)
                                    # ---- 指标 ----
                                    for idx, ind in enumerate(indicators):
                                        a = local_axs[idx+1]
                                    if ind == "VOL":
                                        vcols = ["#C62828" if cs[i]>=opens[i] else "#2E7D32" for i in range(len(vs))]
                                        a.bar(x, vs, width=0.6, color=vcols, alpha=0.7)
                                        a.set_ylabel("VOL", fontsize=8); a.grid(True, alpha=0.2)
                                    elif ind == "MACD":
                                        if dif and dea:
                                            a.plot(x, dif, color="#E91E63", lw=0.8, label="DIF")
                                            a.plot(x, dea, color="#2196F3", lw=0.8, label="DEA")
                                            mcols = ["#C62828" if v>=0 else "#2E7D32" for v in macd_hist]
                                            a.bar(x, macd_hist, width=0.6, color=mcols, alpha=0.6)
                                        a.axhline(0, color="#888", lw=0.5); a.set_ylabel("MACD", fontsize=8); a.legend(fontsize=6, loc="upper left"); a.grid(True, alpha=0.2)
                                    elif ind == "BIAS":
                                        if bias6: a.plot(range(6,len(cs)), bias6, color="#E91E63", lw=0.8, label="BIAS6")
                                        if bias12: a.plot(range(12,len(cs)), bias12, color="#2196F3", lw=0.8, label="BIAS12")
                                        if bias24: a.plot(range(24,len(cs)), bias24, color="#FF9800", lw=0.8, label="BIAS24")
                                        a.axhline(0, color="#888", lw=0.5); a.set_ylabel("BIAS", fontsize=8); a.legend(fontsize=6, loc="upper left"); a.grid(True, alpha=0.2)
                                    elif ind == "KDJ":
                                        if k_kdj:
                                            kx = [i for i,v in enumerate(k_kdj) if v is not None]
                                            kv = [v for v in k_kdj if v is not None]
                                            dx = [i for i,v in enumerate(d_kdj) if v is not None]
                                            dv = [v for v in d_kdj if v is not None]
                                            jx = [i for i,v in enumerate(j_kdj) if v is not None]
                                            jv = [v for v in j_kdj if v is not None]
                                            a.plot(kx, kv, color="#E91E63", lw=0.8, label="K")
                                            a.plot(dx, dv, color="#2196F3", lw=0.8, label="D")
                                            a.plot(jx, jv, color="#FF9800", lw=0.8, label="J")
                                        a.axhline(50, color="#888", lw=0.5, ls="--")
                                        a.set_ylabel("KDJ", fontsize=8); a.set_ylim(-20, 120); a.legend(fontsize=6, loc="upper left"); a.grid(True, alpha=0.2)
                                    # 最底下面板画日期
                                    local_axs[-1].set_xticks(date_ticks)
                                    local_axs[-1].set_xticklabels(date_labels, rotation=45, fontsize=7)
                                    return local_fig, local_axs[0]
                            # ===== 指标勾选框 =====
                            ind_frame = tk.Frame(kf_tool, bg="white")
                            ind_frame.pack(side=tk.RIGHT, padx=(4, 8))
                            ind_vars = {}
                            for ind_name, ind_label in [("VOL","量"),("MACD","MACD"),("BIAS","BIAS"),("KDJ","KDJ")]:
                                    default = ind_name == "VOL"  # 量默认勾
                                    v = tk.BooleanVar(value=default); ind_vars[ind_name] = v
                                    tk.Checkbutton(ind_frame, text=ind_label, variable=v, bg="white",
                                               font=("", 8), cursor="hand2", activebackground="white").pack(side=tk.LEFT, padx=2)
                            # ===== 初始绘制 (VOL only) =====
                            _refs = {}  # 容器保存 ax/fig/cv, 斐波那契函数读这个
                            current_fig, _refs["ax"] = _build_fig(["VOL"])
                            _refs["fig"] = current_fig
                            _refs["cv"] = FigureCanvasTkAgg(current_fig, master=kf); _refs["cv"].draw()
                            _refs["cv"].get_tk_widget().pack(fill=tk.BOTH, expand=True)
                            # 给斐波那契函数用的变量名 (保持兼容)
                            ax = _refs["ax"]; fig = _refs["fig"]; cv = _refs["cv"]
                            # ===== 指标切换回调 =====
                            def _on_ind_toggle(*_):
                                    selected = [n for n,vv in ind_vars.items() if vv.get()]
                                    new_f, new_ax = _build_fig(selected)
                                    _refs["cv"].get_tk_widget().destroy()
                                    _refs["ax"] = new_ax; _refs["fig"] = new_f
                                    _refs["cv"] = FigureCanvasTkAgg(new_f, master=kf); _refs["cv"].draw()
                                    _refs["cv"].get_tk_widget().pack(fill=tk.BOTH, expand=True)
                                    # 更新斐波那契函数用的顶层变量
                                    nonlocal ax, fig, cv
                                    ax = new_ax; fig = new_f; cv = _refs["cv"]
                                    # 工具栏标题恢复
                                    for _c in kf_tool.winfo_children():
                                        if _c != fib_btn and _c.winfo_class() != "Label" and _c != ind_frame:
                                            _c.destroy()
                            for v in ind_vars.values(): v.trace_add("write", _on_ind_toggle)
                            # ===== 斐波那契绘制函数 =====
                            def _draw_fib():
                                    try:
                                        # 1) 先移除旧斐波那契线
                                        for ln in ax.lines[:]:
                                            if getattr(ln, "_fib", False):
                                                ln.remove()
                                        for tx in ax.texts[:]:
                                            if getattr(tx, "_fib", False):
                                                tx.remove()
                                        # 2) 找近 N 天的结构高低点 (含影线)
                                        N = min(60, len(hs))
                                        hh = hs[-N:]  # 近 N 天 high
                                        ll = ls[-N:]  # 近 N 天 low
                                        xx = x[-N:]
                                        # 全局最高 & 最低
                                        hi_idx = max(range(len(hh)), key=lambda i: hh[i])
                                        lo_idx = min(range(len(ll)), key=lambda i: ll[i])
                                        hi_price = hh[hi_idx]
                                        lo_price = ll[lo_idx]
                                        hi_x = xx[hi_idx]
                                        lo_x = xx[lo_idx]
                                        # 判断趋势方向
                                        is_up = hi_idx > lo_idx  # 低点先出现, 高点后出现 = 上涨趋势
                                        # 3) 计算 0.7 / 0.786 回撤
                                        diff = hi_price - lo_price
                                        if is_up:  # 上涨趋势: 从高点回撤
                                            r07 = hi_price - 0.7 * diff
                                            r0786 = hi_price - 0.786 * diff
                                            fib_label = "上涨回撤"
                                            fib_color = "#2E7D32"
                                        else:  # 下跌趋势: 从低点反弹
                                            r07 = lo_price + 0.7 * diff
                                            r0786 = lo_price + 0.786 * diff
                                            fib_label = "下跌反弹"
                                            fib_color = "#C62828"
                                            # 4) 强趋势判定: 回撤幅度 > 15% 且 MA20 方向一致
                                        ma20_last = m20[-1] if m20 else cs[-1]
                                        ma20_prev = m20[-10] if m20 and len(m20) > 10 else cs[-10]
                                        trend_strong = abs(diff / hi_price) > 0.15  # 结构幅度 > 15%
                                        ma_aligned = (is_up and ma20_last > ma20_prev) or (not is_up and ma20_last < ma20_prev)
                                        strong = trend_strong and ma_aligned
                                        win_rate = "73%+" if strong else "50-60%"
                                        # 5) 当前价在哪个区间
                                        cur = cs[-1]
                                        if is_up:
                                            in_zone = r0786 <= cur <= r07
                                        else:
                                            in_zone = r07 <= cur <= r0786
                                        # 6) 画斐波那契线
                                        def _fib_line(y, lbl, col):
                                            _line, = ax.plot([xx[0], xx[-1]], [y, y], color=col, ls="-.", lw=1.5, alpha=0.8)
                                        line._fib = True
                                        tx = ax.text(xx[-1]+0.5, y, f"{lbl}={y:.2f}", color=col, fontsize=8, fontweight="bold", va="center")
                                        tx._fib = True
                                        _fib_line(r07, "0.7", "#FF6F00")
                                        _fib_line(r0786, "0.786", "#6A1B9A")
                                        # 画结构高低点连线
                                        ax.plot([lo_x, hi_x], [lo_price, hi_price], color=fib_color, ls=":", lw=1, alpha=0.5)[0]._fib = True
                                        # 标注结构点
                                        for px, py, tag in [(lo_x, lo_price, f"低 {lo_price:.2f}"), (hi_x, hi_price, f"高 {hi_price:.2f}")]:
                                            ax.scatter([px], [py], color=fib_color, s=30, zorder=5)
                                        t = ax.text(px, py, tag, color=fib_color, fontsize=7, fontweight="bold")
                                        t._fib = True
                                        # 7) 标题写 Prashad 策略判断
                                        verdict = "✅ 强趋势·高胜率" if strong else "⚠️ 横盘·胜率较低"
                                        zone_msg = "🎯 在 0.7/0.786 区间" if in_zone else "不在入场区间"
                                        ax.set_title(f"Prashad斐波那契·{fib_label} | {verdict} | {zone_msg} | 胜率{win_rate}",
                                                 fontsize=10, color=fib_color, fontweight="bold")
                                        fig.tight_layout()
                                        cv.draw()
                                        # 8) 顶部工具栏显示详细建议
                                        for _c in kf_tool.winfo_children():
                                            if _c != fib_btn and _c.winfo_class() != "Label":
                                                _c.destroy()
                                        summary = (f"📐 结构: 高{hi_price:.2f} / 低{lo_price:.2f} | "
                                               f"0.7={r07:.2f}  0.786={r0786:.2f} | "
                                               f"当前价{cur:.2f} | {zone_msg} | {verdict}")
                                        tk.Label(kf_tool, text=summary, bg="white", fg=fib_color,
                                             font=("", 8)).pack(side=tk.LEFT, padx=(10, 0))
                                        fib_btn.config(text="🔄 重算", bg="#555")
                                    except Exception as e:
                                        import traceback; traceback.print_exc()
                                        ax.set_title(f"斐波那契计算失败: {e}", fontsize=9, color="red")
                                        fig.tight_layout(); cv.draw()
                            fib_btn.config(command=_draw_fib)
                    except Exception:
                        pass
                def _render(text):
                    ai.config(state=tk.NORMAL); ai.delete("1.0", tk.END)
                    for line in (text or "(无)").split("\n"):
                        if any(kw in line for kw in ["持有","安全","加仓","低吸","多头","绿灯"]):
                            ai.insert(tk.END, line+"\n", "gg")
                        elif any(kw in line for kw in ["减仓","危险","清仓","破位","空头","红灯","止损"]):
                            ai.insert(tk.END, line+"\n", "rg")
                        elif any(kw in line for kw in ["警惕","控制","观望","震荡","黄灯"]):
                            ai.insert(tk.END, line+"\n", "yg")
                        else: ai.insert(tk.END, line+"\n")
                    ai.config(state=tk.DISABLED)
                threading.Thread(target=w2, daemon=True).start()
            _go()

    ETF_POOL = [
        {"code": "510300", "ts_code": "510300.SH", "name": "沪深300ETF", "role": "A股大盘"},
        {"code": "510500", "ts_code": "510500.SH", "name": "中证500ETF", "role": "A股中小盘"},
        {"code": "512400", "ts_code": "512400.SH", "name": "有色金属ETF", "role": "商品进攻"},
        {"code": "518880", "ts_code": "518880.SH", "name": "黄金ETF", "role": "避险"},
        {"code": "511010", "ts_code": "511010.SH", "name": "国债ETF", "role": "避险"},
        {"code": "159611", "ts_code": "159611.SZ", "name": "电力ETF", "role": "防御"},
        {"code": "159920", "ts_code": "159920.SZ", "name": "恒生ETF", "role": "港股进攻", "optional": True},
    ]

    SKILL_DASHBOARD_DIR = os.path.expanduser("~/.qclaw/skills/大盘风险仪表盘")

    SKILL_DASHBOARD_SCRIPT = os.path.join(SKILL_DASHBOARD_DIR, "scripts", "dashboard.py")

    SKILL_CAPITAL_DIR = os.path.expanduser("~/.qclaw/skills/资金选择方向")

    SKILL_CAPITAL_TEMPLATE = os.path.join(SKILL_CAPITAL_DIR, "references", "monthly_report_template.md")

    PRECIOUS_METALS_STOCKS = [
        # 黄金
        ("黄金", "601899", "紫金矿业"),
        ("黄金", "600547", "山东黄金"),
        ("黄金", "600489", "中金黄金"),
        ("黄金", "600988", "赤峰黄金"),
        ("黄金", "000975", "银泰黄金"),
        ("黄金", "002155", "湖南黄金"),
        ("黄金", "002237", "恒邦股份"),
        # 白银
        ("白银", "000603", "盛达资源"),
        ("白银", "600988", "赤峰黄金"),
        ("白银", "002716", "金贵银业"),
        ("白银", "002237", "恒邦股份"),
        # 铜/有色
        ("有色金属", "601899", "紫金矿业"),
        ("有色金属", "600362", "江西铜业"),
        ("有色金属", "601857", "中国石油"),
        ("有色金属", "603993", "洛阳钼业"),
        ("有色金属", "600547", "山东黄金"),
        # 稀土/锂
        ("稀有金属", "600111", "北方稀土"),
        ("稀有金属", "002460", "赣锋锂业"),
        ("稀有金属", "300014", "亿纬锂能"),
        # 小金属
        ("小金属", "600219", "南山铝业"),
        ("小金属", "002149", "西部材料"),
        ("小金属", "000612", "焦作万方"),
    ]

    _SECTOR_LEADERS = {
        # 科技
        "半导体": [("中芯国际", "688981"), ("北方华创", "002371"), ("韦尔股份", "603501"), ("士兰微", "600460")],
        "芯片": [("中芯国际", "688981"), ("韦尔股份", "603501"), ("紫光国微", "002049"), ("寒武纪", "688256")],
        "AI": [("科大讯飞", "002230"), ("寒武纪", "688256"), ("海光信息", "688041"), ("中科曙光", "603019")],
        "人工智能": [("科大讯飞", "002230"), ("寒武纪", "688256"), ("海光信息", "688041"), ("中科曙光", "603019")],
        "消费电子": [("立讯精密", "002475"), ("歌尔股份", "002241"), ("蓝思科技", "300433"), ("闻泰科技", "600745")],
        "通信": [("中兴通讯", "000063"), ("烽火通信", "600498"), ("大唐电信", "600198")],
        "软件": [("用友网络", "600588"), ("金山办公", "688111"), ("恒生电子", "600570")],
        # 金融
        "银行": [("招商银行", "600036"), ("工商银行", "601398"), ("建设银行", "601939"), ("农业银行", "601288")],
        "券商": [("中信证券", "600030"), ("华泰证券", "601688"), ("国泰君安", "601211"), ("东方财富", "300059")],
        "证券": [("中信证券", "600030"), ("华泰证券", "601688"), ("东方财富", "300059")],
        "保险": [("中国平安", "601318"), ("中国人寿", "601628"), ("中国太保", "601601")],
        # 消费
        "白酒": [("贵州茅台", "600519"), ("五粮液", "000858"), ("泸州老窖", "000568"), ("山西汾酒", "600809")],
        "食品饮料": [("贵州茅台", "600519"), ("五粮液", "000858"), ("伊利股份", "600887")],
        "消费": [("贵州茅台", "600519"), ("五粮液", "000858"), ("伊利股份", "600887"), ("海天味业", "603288")],
        "医药": [("恒瑞医药", "600276"), ("药明康德", "603259"), ("迈瑞医疗", "300760"), ("中国生物", "600196")],
        "医疗": [("迈瑞医疗", "300760"), ("药明康德", "603259"), ("恒瑞医药", "600276")],
        # 新能源
        "新能源": [("宁德时代", "300750"), ("比亚迪", "002594"), ("隆基绿能", "601012")],
        "光伏": [("隆基绿能", "601012"), ("通威股份", "600438"), ("阳光电源", "300274")],
        "锂电": [("宁德时代", "300750"), ("赣锋锂业", "002460"), ("天齐锂业", "002466")],
        "锂电池": [("宁德时代", "300750"), ("赣锋锂业", "002460"), ("天齐锂业", "002466")],
        "新能源汽车": [("比亚迪", "002594"), ("宁德时代", "300750"), ("蔚来", "NIO"), ("小鹏汽车", "XPEV")],
        "汽车": [("比亚迪", "002594"), ("上汽集团", "600104"), ("长城汽车", "601633")],
        # 周期
        "房地产": [("万科A", "000002"), ("保利发展", "600048"), ("招商蛇口", "001979")],
        "钢铁": [("宝钢股份", "600019"), ("河钢股份", "000708"), ("华菱钢铁", "000932")],
        "煤炭": [("中国神华", "601088"), ("陕西煤业", "601225"), ("中煤能源", "601898")],
        "有色": [("紫金矿业", "601899"), ("洛阳钼业", "603993"), ("山东黄金", "600547")],
        "稀土": [("北方稀土", "600111"), ("五矿稀土", "000831"), ("盛和资源", "600392")],
        # 高端制造
        "军工": [("中航沈飞", "600760"), ("中航光电", "002179"), ("中国船舶", "600150")],
        "国防": [("中航沈飞", "600760"), ("中航光电", "002179"), ("中国船舶", "600150")],
        "航空": [("中航沈飞", "600760"), ("中航西飞", "000768")],
        "航天": [("中国卫星", "600118"), ("航天电子", "600879")],
        "机器人": [("汇川技术", "300124"), ("埃斯顿", "002747"), ("机器人", "300024")],
        "工业自动化": [("汇川技术", "300124"), ("中控技术", "688777")],
        # 其他
        "农业": [("牧原股份", "002714"), ("温氏股份", "300498"), ("隆平高科", "000998")],
        "养殖": [("牧原股份", "002714"), ("温氏股份", "300498")],
        "电力": [("长江电力", "600900"), ("华能水电", "600025"), ("国投电力", "600886")],
        "煤炭电力": [("长江电力", "600900"), ("中国神华", "601088")],
        "黄金": [("山东黄金", "600547"), ("中金黄金", "600489"), ("紫金矿业", "601899")],
        "石油": [("中国石油", "601857"), ("中国石化", "600028"), ("中海油", "600938")],
        "化工": [("万华化学", "600309"), ("恒力石化", "600346"), ("荣盛石化", "002493")],
        "新材料": [("万华化学", "600309"), ("恩捷股份", "002812"), ("国瓷材料", "300285")],
        "ETF": [("沪深300ETF", "510300"), ("创业板ETF", "159915"), ("科创50ETF", "588000")],
    }


__all__ = ["InnerClassMixin"]
