# -*- coding: utf-8 -*-
"""
📊 股票分析弹窗 — 左侧主流分析方法 + 右侧完整 K 线图
=====================================================
左边面板:
  - 股票选择下拉框 (持仓股 + 今日涨停 + 热门资讯)
  - 🔍 搜索输入框 + 刷新按钮
  - 6 种主流分析方法 LabelFrame (点展开)
    ① 基本面 (PE/PB/ROE/市值/营收增速)
    ② 技术面 (MA位置/MACD/KDJ/RSI/量比)
    ③ 情绪面 (换手率/涨跌停/连板)
    ④ 资金面 (龙虎榜/北向/主力净量)
    ⑤ 生命周期 (吸筹/整理/拉升/出货/下跌)
    ⑥ 波浪理论 (1-5浪 / A-B-C)
右边面板:
  - matplotlib K 线主图 (MA + BOLL + 支撑压力 + 4类买卖点scatter + 顶部胜率)
  - 副图 (VOL / MACD / KDJ / BOLL, 2-4选)
  - hover 某根有买卖信号的 K 线 → tooltip 胜率+盈亏比
"""
import os, re, sys, json, threading, traceback
from typing import Dict, List, Optional, Any


def _fetch_kline_data(ts_code: str, days: int = 180) -> Optional[Dict]:
    """拉日 K 线 + 算均线 (优先 tushare, 兜底 akshare)"""
    import pandas as pd
    import numpy as np
    # === 路径1: tushare ===
    try:
        import tushare as ts
        token = os.environ.get("TUSHARE_TOKEN", "")
        if token:
            ts.set_token(token)
            pro = ts.pro_api()
            df = pro.daily(ts_code=ts_code, limit=days,
                           fields="ts_code,trade_date,open,high,low,close,vol,amount")
            if df is not None and len(df) >= 30:
                df = df.sort_values("trade_date").reset_index(drop=True)
                df["date"] = pd.to_datetime(df["trade_date"])
                data = pd.DataFrame({
                    "日期": df["trade_date"], "开盘": df["open"].astype(float),
                    "收盘": df["close"].astype(float),
                    "最高": df["high"].astype(float),
                    "最低": df["low"].astype(float),
                    "成交量": df["vol"].astype(float),
                    "成交额": df["amount"].astype(float),
                })
                # 算均线
                closes = data["收盘"].values.astype(float)
                ma_values = {}
                for ma_name, p in [("ma5",5),("ma10",10),("ma20",20),("ma60",60)]:
                    ma_values[ma_name] = np.convolve(closes, np.ones(p)/p, mode="valid").tolist()
                return {"data": data, "ma_values": ma_values, "trade_dates": df["trade_date"].tolist()}
    except Exception as e:
        print(f"[股票分析] tushare 拉K线失败 {ts_code}: {e}")
    return None


def _fetch_stock_name(ts_code: str) -> str:
    try:
        import tushare as ts
        token = os.environ.get("TUSHARE_TOKEN", "")
        if token:
            ts.set_token(token); pro = ts.pro_api()
            df = pro.stock_basic(ts_code=ts_code, fields="ts_code,name")
            if df is not None and len(df) > 0: return df.iloc[0]["name"]
    except Exception: pass
    return ts_code.split(".")[0]


# ============= UI 弹窗 =============
def show_stock_analysis_dialog(parent_win=None, call_ai_fn=None, auto_code=None, auto_name=None):
    import tkinter as tk
    from tkinter import ttk, messagebox
    import webbrowser

    win = tk.Toplevel(parent_win) if parent_win else tk.Tk()
    win.title("📊 股票分析 — 基本面+技术面+情绪面+资金面+K线图")
    win.geometry("1380x880"); win.minsize(1100, 750)
    win.configure(bg="#F5F5F5")

    # ===== 顶栏: 股票选择 =====
    top = tk.Frame(win, bg="#1A237E"); top.pack(fill=tk.X)
    tk.Label(top, text="📊 股票分析", bg="#1A237E", fg="#FFD54F",
             font=("", 14, "bold")).pack(side=tk.LEFT, padx=14, pady=10)
    tk.Label(top, text="股票:", bg="#1A237E", fg="white", font=("", 10)).pack(side=tk.LEFT)
    stock_var = tk.StringVar()
    combo = ttk.Combobox(top, textvariable=stock_var, width=18, state="normal")
    combo.pack(side=tk.LEFT, padx=6)
    search_btn = tk.Button(top, text="🔍 分析", bg="#FFB300", fg="#1A237E",
                           font=("", 10, "bold"), relief=tk.FLAT, padx=12)
    search_btn.pack(side=tk.LEFT, padx=6)
    status_var = tk.StringVar(value="⏳ 加载候选列表...")
    tk.Label(top, textvariable=status_var, bg="#1A237E", fg="#90A4AE",
             font=("", 8)).pack(side=tk.RIGHT, padx=14)

    # ===== PanedWindow 水平: 左分析方法 + 右K线 =====
    pw = tk.PanedWindow(win, orient=tk.HORIZONTAL, bg="#F5F5F5", sashwidth=6)
    pw.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    # ===== 左侧面板 =====
    left_f = tk.Frame(pw, bg="#FAFAFA")
    pw.add(left_f, minsize=360)

    tk.Label(left_f, text="🔍 股票分析方法 (点标题展开)", bg="#FAFAFA", fg="#4527A0",
             font=("", 11, "bold")).pack(fill=tk.X, padx=6, pady=(6, 4))

    # 分析方法容器 (可折叠)
    methods_canvas = tk.Canvas(left_f, bg="#FAFAFA", highlightthickness=0)
    methods_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    methods_sb = ttk.Scrollbar(left_f, orient=tk.VERTICAL, command=methods_canvas.yview)
    methods_sb.pack(side=tk.RIGHT, fill=tk.Y)
    methods_canvas.configure(yscrollcommand=methods_sb.set)
    methods_inner = tk.Frame(methods_canvas, bg="#FAFAFA")
    methods_canvas.create_window((0, 0), window=methods_inner, anchor="nw")
    methods_inner.bind("<Configure>", lambda e: methods_canvas.configure(scrollregion=methods_canvas.bbox("all")))

    # ===== 右侧面板: matplotlib =====
    right_f = tk.Frame(pw, bg="#FAFAFA")
    pw.add(right_f, minsize=600)
    rt = tk.Frame(right_f, bg="#FAFAFA"); rt.pack(fill=tk.X, pady=(0,4))
    ttk.Label(rt, text="K线图 + 指标 + 买卖点", font=("", 11, "bold"),
              background="#FAFAFA", foreground="#1565C0").pack(side=tk.LEFT, padx=6)
    # 指标选择 (复用放大弹窗逻辑)
    ivars = {}
    for code, lbl in [("VOL","VOL"),("MACD","MACD"),("WR2","WR2"),("KDJ","KDJ"),("BOLL","BOLL")]:
        ivars[code] = tk.BooleanVar(value=code in ("VOL","MACD","KDJ"))
        ttk.Checkbutton(rt, text=lbl, variable=ivars[code]).pack(side=tk.LEFT, padx=3)
    bs_var = tk.BooleanVar(value=True); bt_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(rt, text="🛒买卖点", variable=bs_var).pack(side=tk.LEFT, padx=(10,3))
    ttk.Checkbutton(rt, text="💡胜率提示", variable=bt_var).pack(side=tk.LEFT, padx=3)
    chart_inner = tk.Frame(right_f, bg="#FAFAFA"); chart_inner.pack(fill=tk.BOTH, expand=True, pady=4)

    # ===== 状态/缓存 =====
    _current_kline = None  # kline_data dict
    _current_fund: Dict = {}   # 基本面 dict
    _current_tech: Dict = {}   # 技术面 dict
    _current_name = ""

    # ========= 左侧分析方法生成 =========
    def _clear_methods():
        for w in methods_inner.winfo_children(): w.destroy()

    def _make_section(title: str, emoji: str, items: List[Tuple[str, str, str]]):
        """items: [(label, value, color)]"""
        lf = tk.LabelFrame(methods_inner, text=f"  {emoji} {title}  ",
                           bg="#FFFFFF", fg="#4527A0", font=("", 10, "bold"),
                           relief=tk.FLAT, bd=1)
        lf.pack(fill=tk.X, padx=6, pady=4)
        for lbl, val, col in items:
            row = tk.Frame(lf, bg="#FFFFFF"); row.pack(fill=tk.X, padx=6, pady=2)
            tk.Label(row, text=lbl, bg="#FFFFFF", fg="#666", font=("", 9)).pack(side=tk.LEFT)
            tk.Label(row, text=str(val), bg="#FFFFFF", fg=col, font=("", 9, "bold")).pack(side=tk.RIGHT)

    def _render_methods():
        """根据 _current_fund / _current_tech / _current_kline 生成左侧 6 个 section"""
        _clear_methods()
        if not _current_kline:
            tk.Label(methods_inner, text="⏳ 先在顶栏选择股票 → 点 🔍 分析",
                     bg="#FAFAFA", fg="#888", font=("", 10)).pack(pady=30)
            return
        f = _current_fund; t = _current_tech
        # ① 基本面
        _make_section("基本面", "💰", [
            ("股票名", _current_name, "#1565C0"),
            ("总市值", f"{(f.get('mv') or 0)/10000:.0f} 亿", "#333"),
            ("PE(TTM)", f"{f.get('pe') or '—'}", "#333"),
            ("PB", f"{f.get('pb') or '—'}", "#333"),
            ("ROE", f"{f.get('roe') or '—'} %", "#333"),
            ("营收增速", f"{f.get('revenue_yoy') or '—'} %", "#2E7D32" if (f.get('revenue_yoy') or 0) > 0 else "#C62828"),
            ("净利润增速", f"{f.get('profit_yoy') or '—'} %", "#2E7D32" if (f.get('profit_yoy') or 0) > 0 else "#C62828"),
        ])
        # ② 技术面
        _make_section("技术面", "📈", [
            ("MA20位置", "↑站上MA20" if t.get("above_ma20") else "↓跌破MA20",
             "#2E7D32" if t.get("above_ma20") else "#C62828"),
            ("MA60位置", "↑站上MA60" if t.get("above_ma60") else "↓跌破MA60",
             "#2E7D32" if t.get("above_ma60") else "#C62828"),
            ("MACD", t.get("macd_trend") or "—", "#333"),
            ("RSI(14)", f"{t.get('rsi') or 0:.0f}",
             "#C62828" if (t.get('rsi') or 50) > 70 else "#2E7D32" if (t.get('rsi') or 50) < 30 else "#333"),
            ("量比(5/20)", f"{t.get('vol_ratio') or 0:.2f}", "#333"),
            ("20日涨跌", f"{t.get('chg_20d') or 0:+.1f} %",
             "#2E7D32" if (t.get('chg_20d') or 0) > 0 else "#C62828"),
        ])
        # ③ 生命周期
        _make_section("生命周期阶段", "📅", [
            ("当前阶段", t.get("lc_desc") or "—", "#4527A0"),
            ("波浪理论", t.get("wave") or "—", "#4527A0"),
        ])
        # ④ 资金面 (简单版)
        try:
            import sqlite3
            lhb_cnt = 0
            for root, _, files in os.walk(os.path.expanduser("~/Agent/stockyidong_project")):
                for file in files:
                    if file.endswith(".db") and "stock" in file.lower():
                        try:
                            conn = sqlite3.connect(os.path.join(root, file))
                            cur = conn.cursor()
                            code6 = (_current_kline.get("trade_dates") or [""])[0][:6] if _current_kline else ""
                            if not code6 and t.get("ts_code"): code6 = t["ts_code"].split(".")[0]
                            cur.execute("SELECT COUNT(*) FROM lhb_records WHERE stock_code LIKE ?", (f"%{code6}%",))
                            lhb_cnt = cur.fetchone()[0]; conn.close(); break
                        except Exception: pass
                if lhb_cnt > 0: break
        except Exception: lhb_cnt = 0
        _make_section("资金面", "💴", [
            ("龙虎榜(90d)", f"{lhb_cnt} 次", "#333"),
            ("换手率", f"{f.get('tr') or '—'} %", "#333"),
        ])
        # ⑤ AI 综合建议
        if call_ai_fn:
            lf = tk.LabelFrame(methods_inner, text="  🤖 AI 综合操盘建议  ",
                               bg="#FFF8E1", fg="#F57F17", font=("", 10, "bold"),
                               relief=tk.FLAT, bd=1)
            lf.pack(fill=tk.X, padx=6, pady=4)
            tk.Label(lf, text="⏳ 点击「🔍 分析」后自动生成...",
                     bg="#FFF8E1", fg="#888", font=("", 9)).pack(padx=6, pady=10, anchor="w")

    # ========= matplotlib 重绘 =========
    def _collect_keys():
        return [c for c, _ in [("VOL",""),("MACD",""),("WR2",""),("KDJ",""),("BOLL","")] if ivars[c].get()]

    def _redraw_chart():
        if not _current_kline: return
        sel = _collect_keys()
        if len(sel) < 2 or len(sel) > 4:
            # 默认选 VOL+MACD+KDJ
            for k in ("VOL","MACD","KDJ"): ivars[k].set(True)
            sel = _collect_keys()
        for w in chart_inner.winfo_children(): w.destroy()
        try:
            import matplotlib
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            matplotlib.use("TkAgg")
            from matplotlib import gridspec
            import numpy as np
            plt_module = matplotlib.pyplot
            plt_module.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC"]
            plt_module.rcParams["axes.unicode_minus"] = False
            data = _current_kline["data"]
            closes = data["收盘"].values; opens = data["开盘"].values
            highs = data["最高"].values; lows = data["最低"].values
            vols = data["成交量"].values.astype(float) if "成交量" in data.columns else np.zeros(len(closes))
            ni = len(sel)
            ratios = [3.2] + [1.0]*ni
            fig = Figure(figsize=(9.5, 5.5 + 1.8*ni), dpi=100, facecolor="#FAFAFA")
            gs = gridspec.GridSpec(1+ni, 1, figure=fig, height_ratios=ratios, hspace=0.12)
            ax_main = fig.add_subplot(gs[0, 0])
            # K 线 (red>=close)
            for i in range(len(closes)):
                color = "red" if closes[i] >= opens[i] else "green"
                ax_main.bar(i, max(opens[i], closes[i]) - min(opens[i], closes[i]),
                           bottom=min(opens[i], closes[i]), color=color, alpha=0.8, width=0.6)
                ax_main.plot([i,i], [lows[i], min(opens[i], closes[i])], color=color, linewidth=1)
                ax_main.plot([i,i], [max(opens[i], closes[i]), highs[i]], color=color, linewidth=1)
            # MA
            ma_colors = {"ma5":"#FF0000","ma10":"#0000FF","ma20":"#FF00FF","ma60":"#00CED1"}
            ma_labels = {"ma5":"MA5","ma10":"MA10","ma20":"MA20","ma60":"MA60"}
            for ma_name, p in [("ma5",5),("ma10",10),("ma20",20),("ma60",60)]:
                if ma_name not in _current_kline.get("ma_values", {}): continue
                ma_arr = np.array(_current_kline["ma_values"][ma_name])
                idx_list = list(range(p-1, p-1+len(ma_arr)))
                ax_main.plot(idx_list, ma_arr, color=ma_colors[ma_name], linewidth=1.2,
                             label=ma_labels[ma_name], alpha=0.8)
            # BOLL (20日)
            if len(closes) >= 20:
                c20 = np.convolve(closes.astype(float), np.ones(20)/20, mode="valid")
                s20 = np.array([np.std(closes[i:i+20]) for i in range(len(closes)-19)])
                ax_main.plot(list(range(19, len(closes))), c20, color="#FFA500", linewidth=1.2, label="BOLL中轨")
                ax_main.plot(list(range(19, len(closes))), c20+2*s20, color="#4682B4", linestyle="--", linewidth=0.8, label="BOLL上轨")
                ax_main.plot(list(range(19, len(closes))), c20-2*s20, color="#4682B4", linestyle="--", linewidth=0.8, label="BOLL下轨")
            # 🛒 买卖点 + 回测胜率 (复用 calc_trade_signals)
            if bs_var.get() and len(closes) >= 30:
                try:
                    from ui.tab_stock_detail import calc_trade_signals, backtest_signal
                    sigs = calc_trade_signals(closes, opens, highs, lows, vols)
                    for _key, _mk, _col, _lbl in [("buy","★","#2E7D32","★买入"),("add","^","#F57C00","▲加仓"),
                                                   ("sell","v","#C62828","▼卖出"),("reduce","v","#6A1B9A","▽减仓")]:
                        _pts = sigs.get(_key, [])
                        if not _pts: continue
                        ax_main.scatter([p[0] for p in _pts], [p[1] for p in _pts],
                                        marker=_mk, s=100, color=_col, zorder=15,
                                        edgecolors="white", linewidths=0.8, label=_lbl)
                        for _pt in _pts:
                            _off = -10 if _pt[4] in ("★","▲") else 10
                            _va = "top" if _pt[4] in ("★","▲") else "bottom"
                            ax_main.annotate(_pt[2], xy=(_pt[0], _pt[1]),
                                             xytext=(0,_off), textcoords="offset points",
                                             fontsize=5, color=_pt[3], ha="center", va=_va,
                                             fontweight="bold", zorder=16)
                    # 回测 summary 文字
                    if bt_var.get():
                        _bt_txt = []
                        for _k, _lbl in [("buy","买入"),("add","加仓"),("sell","卖出"),("reduce","减仓")]:
                            _bt = backtest_signal(_k, sigs.get(f"{_k}_all",[]), closes)
                            if _bt: _bt_txt.append(f"{_lbl}胜率{_bt[1]:.0f}% 盈亏比{_bt[4]:.2f}")
                        if _bt_txt:
                            ax_main.text(0.5, 1.01, "  |  ".join(_bt_txt),
                                         transform=ax_main.transAxes, fontsize=7, color="#555",
                                         ha="center", va="bottom", style="italic")
                    # 存缓存给 hover tooltip
                    _hover_cache["bs"] = {}
                    for _k in ("buy","add","sell","reduce"):
                        for _pt in sigs.get(f"{_k}_all", []):
                            _hover_cache["bs"][_pt[0]] = (_k, _pt[2], _pt[3])
                    _hover_cache["bt"] = {}
                    for _k in ("buy","add","sell","reduce"):
                        _bt = backtest_signal(_k, sigs.get(f"{_k}_all",[]), closes)
                        if _bt: _hover_cache["bt"][_k] = _bt
                except Exception as _e:
                    print(f"[买卖点] 失败: {_e}")
            # 支撑/压力线 (简单枢轴)
            piv_lo = [i for i in range(1, len(closes)-1) if lows[i]<=lows[i-1] and lows[i]<=lows[i+1]]
            piv_hi = [i for i in range(1, len(closes)-1) if highs[i]>=highs[i-1] and highs[i]>=highs[i+1]]
            for i in piv_lo[-3:]:
                ax_main.axhline(y=lows[i], color="#006400", linestyle="--", alpha=0.5, linewidth=0.8)
            for i in piv_hi[-3:]:
                ax_main.axhline(y=highs[i], color="#8B0000", linestyle="--", alpha=0.5, linewidth=0.8)
            ax_main.set_title(f"{_current_name} - 日K线图", fontsize=12, fontweight="bold")
            ax_main.legend(loc="upper left", fontsize=7); ax_main.grid(True, alpha=0.25)
            ax_main.set_ylabel("价格", fontsize=9)
            # 副图
            for row, key in enumerate(sel, start=1):
                ax_s = fig.add_subplot(gs[row, 0], sharex=ax_main)
                if key == "VOL":
                    ax_s.bar(list(range(len(vols))), vols, color=["red" if closes[i]>=opens[i] else "green" for i in range(len(vols))], alpha=0.7)
                    ax_s.set_title("VOL", fontsize=8, loc="left"); ax_s.grid(True, alpha=0.2)
                elif key == "MACD":
                    ema12 = np.array(plt_module.mlab.ema(closes, 12)) if hasattr(plt_module, "mlab") else None
                    if ema12 is None:
                        def _ema(a, w):
                            r = np.empty_like(a); r[0]=a[0]; k=2/(w+1)
                            for i in range(1,len(a)): r[i]=a[i]*k+r[i-1]*(1-k); return r
                        ema12 = _ema(closes.astype(float), 12)
                    ema26 = _ema(closes.astype(float), 26)
                    dif = ema12 - ema26; dea = _ema(dif, 9); macd = (dif-dea)*2
                    ax_s.bar(list(range(len(closes))), macd, color=["red" if v>=0 else "green" for v in macd], alpha=0.7)
                    ax_s.plot(list(range(len(closes))), dif, color="#1976D2", label="DIF", linewidth=0.9)
                    ax_s.plot(list(range(len(closes))), dea, color="#FF9800", label="DEA", linewidth=0.9)
                    ax_s.legend(loc="upper left", fontsize=7); ax_s.grid(True, alpha=0.2)
                    ax_s.set_title("MACD", fontsize=8, loc="left")
                elif key == "KDJ":
                    kd_k = np.full(len(closes), 50.0); kd_d = np.full(len(closes), 50.0)
                    for i in range(9, len(closes)):
                        rv = max(highs[i-8:i+1]) - min(lows[i-8:i+1])
                        rsv = (closes[i] - min(lows[i-8:i+1])) / max(rv,0.001)*100
                        kd_k[i] = kd_k[i-1]*2/3 + rsv*1/3; kd_d[i] = kd_d[i-1]*2/3 + kd_k[i]*1/3
                    ax_s.plot(list(range(len(closes))), kd_k, color="#1976D2", label="K", linewidth=0.9)
                    ax_s.plot(list(range(len(closes))), kd_d, color="#FF9800", label="D", linewidth=0.9)
                    ax_s.axhline(y=70, color="gray", linestyle="--", alpha=0.5, linewidth=0.7)
                    ax_s.axhline(y=30, color="gray", linestyle="--", alpha=0.5, linewidth=0.7)
                    ax_s.legend(loc="upper left", fontsize=7); ax_s.grid(True, alpha=0.2)
                    ax_s.set_title("KDJ", fontsize=8, loc="left")
                elif key == "WR2":
                    wr = np.full(len(closes), 50.0)
                    for i in range(1, len(closes)):
                        rng = max(highs[max(0,i-10):i+1]) - min(lows[max(0,i-10):i+1])
                        wr[i] = (rng - (max(highs[max(0,i-10):i+1]) - closes[i])) / max(rng,0.001) * (-100)
                    ax_s.plot(list(range(len(closes))), wr, color="#9C27B0", linewidth=1)
                    ax_s.axhline(y=-20, color="gray", linestyle="--", alpha=0.5, linewidth=0.7)
                    ax_s.axhline(y=-80, color="gray", linestyle="--", alpha=0.5, linewidth=0.7)
                    ax_s.grid(True, alpha=0.2); ax_s.set_title("WR2", fontsize=8, loc="left")
                elif key == "BOLL":
                    ax_s.plot(list(range(19, len(closes))), closes[19:], color="#1976D2", label="收盘", linewidth=0.9)
                    ax_s.plot(list(range(19, len(closes))), c20, color="#FFA500", label="中轨", linewidth=0.9)
                    ax_s.plot(list(range(19, len(closes))), c20+2*s20, color="#C62828", linestyle="--", linewidth=0.7)
                    ax_s.plot(list(range(19, len(closes))), c20-2*s20, color="#2E7D32", linestyle="--", linewidth=0.7)
                    ax_s.legend(loc="upper left", fontsize=7); ax_s.grid(True, alpha=0.2)
                    ax_s.set_title("BOLL", fontsize=8, loc="left")
                if row < ni-1: ax_s.tick_params(axis="x", labelbottom=False)
            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, chart_inner); canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            # hover tooltip
            def _on_motion(event):
                if event.inaxes is None or event.xdata is None or not bt_var.get():
                    if _hover_tt and _hover_tt.winfo_exists(): _hover_tt.destroy(); return
                idx = int(round(event.xdata))
                if idx not in _hover_cache.get("bs", {}):
                    if _hover_tt and _hover_tt.winfo_exists(): _hover_tt.destroy(); return
                sig_type, label, col = _hover_cache["bs"][idx]
                bt = _hover_cache.get("bt", {}).get(sig_type)
                _zh = {"buy":"★买入","add":"▲加仓","sell":"▼卖出","reduce":"▽减仓"}[sig_type]
                _lines = [f"🎯 {_zh} — {label}", ""]
                if bt:
                    cnt, wr, avg_g, avg_l, plr = bt
                    _lines += [f"📊 历史{cnt}次", f"✅ 胜率{wr:.1f}%", f"💰 +{avg_g:.2f}%", f"💔 -{avg_l:.2f}%", f"⚖️ 盈亏比{plr:.2f}"]
                else: _lines.append("⚠️ 历史信号不足")
                _text = "\n".join(_lines)
                global _hover_tt
                if '_hover_tt' not in globals() or _hover_tt is None or not _hover_tt.winfo_exists():
                    _hover_tt = tk.Toplevel(win); _hover_tt.wm_overrideredirect(True)
                    _hover_tt.attributes("-topmost", True); _hover_tt.configure(bg="#263238")
                    tk.Label(_hover_tt, text=_text, bg="#263238", fg="#FFF",
                             font=("", 10, "bold"), padx=10, pady=6, justify=tk.LEFT).pack()
                else:
                    for _w in _hover_tt.winfo_children(): _w.destroy()
                    tk.Label(_hover_tt, text=_text, bg="#263238", fg="#FFF",
                             font=("", 10, "bold"), padx=10, pady=6, justify=tk.LEFT).pack()
                _hover_tt.geometry(f"+{win.winfo_pointerx()+15}+{win.winfo_pointery()+15}")
            canvas.mpl_connect("motion_notify_event", _on_motion)
            def _on_leave(event):
                global _hover_tt
                if '_hover_tt' in globals() and _hover_tt and _hover_tt.winfo_exists(): _hover_tt.destroy()
            canvas.mpl_connect("axes_leave_event", _on_leave)
        except Exception as ex:
            traceback.print_exc(); messagebox.showerror("错误", f"绘图失败: {ex}", parent=win)

    _hover_cache: Dict[str, Any] = {"bs": {}, "bt": {}}

    # ========= 🔍 搜索按钮 =========
    def _collect_candidates():
        candidates = []
        # 持仓股 (从 SQL tushare_stocks)
        try:
            import sqlite3, glob
            for root, _, files in os.walk(os.path.expanduser("~/Agent/stockyidong_project")):
                for f in files:
                    if f.endswith(".db") and "stock" in f.lower():
                        try:
                            conn = sqlite3.connect(os.path.join(root, f))
                            cur = conn.cursor()
                            cur.execute("SELECT stock_code FROM tushare_stocks LIMIT 200")
                            for row in cur.fetchall(): candidates.append(row[0])
                            conn.close(); break
                        except Exception: pass
        except Exception: pass
        # 今日涨停
        try:
            import akshare as ak; from datetime import datetime
            today = datetime.now().strftime("%Y%m%d")
            df = ak.stock_zt_pool_em(date=today)
            if df is not None:
                col = "代码" if "代码" in df.columns else "symbol"
                candidates += df[col].tolist()[:30]
        except Exception: pass
        return list(dict.fromkeys([c for c in candidates if c])).reverse()[:200]

    def _do_search():
        code = stock_var.get().strip()
        if not code: status_var.set("⚠️ 请输入或选择股票代码"); return
        # 去掉前缀
        code6 = re.sub(r"^(sh|sz|bj|SH|SZ|BJ)", "", code)
        # 补 tushare ts_code
        if "." not in code6:
            suffix = ".SH" if code6.startswith(("6","9","5")) else ".SZ"
            if code6.startswith(("4","8")) or code6.startswith("3"):
                suffix = ".SZ" if code6.startswith(("3","4")) else ".BJ"
            tsc = code6 + suffix
        else: tsc = code6
        status_var.set(f"⏳ 拉 {tsc} K线 + 基本面 + 技术面...")
        # 后台线程
        def _bg():
            global _hover_tt
            _hover_tt = None
            kline = _fetch_kline_data(tsc, 180)
            if not kline:
                win.after(0, lambda: status_var.set("❌ K线获取失败 (tushare熔断或无数据)")); return
            name = _fetch_stock_name(tsc)
            # 基本面
            fund = {}
            try:
                import tushare as ts
                ts.set_token(os.environ.get("TUSHARE_TOKEN",""))
                pro = ts.pro_api()
                db = pro.daily_basic(ts_code=tsc, limit=1,
                                     fields="turnover_rate,pe_ttm,pb,total_mv")
                if db is not None and len(db)>0:
                    r = db.iloc[0]
                    fund = {"pe": r.get("pe_ttm"), "pb": r.get("pb"),
                            "mv": r.get("total_mv"), "tr": r.get("turnover_rate")}
                fi = pro.fina_indicator(ts_code=tsc, limit=1,
                                        fields="roe,revenue_yoy,n_income_yoy")
                if fi is not None and len(fi)>0:
                    r = fi.iloc[0]
                    fund["roe"] = r.get("roe"); fund["revenue_yoy"] = r.get("revenue_yoy")
                    fund["profit_yoy"] = r.get("n_income_yoy")
            except Exception as e: print(f"[基本面] {e}")
            # 技术面 (复用 stock_compare 的生命周期 + 波浪)
            tech = {"ts_code": tsc}
            try:
                closes = kline["data"]["收盘"].values.astype(float)
                opens = kline["data"]["开盘"].values.astype(float)
                highs = kline["data"]["最高"].values.astype(float)
                lows = kline["data"]["最低"].values.astype(float)
                import numpy as np
                # MA
                def _ma(a, p):
                    if len(a) < p: return None
                    return float(np.mean(a[-p:]))
                tech["price"] = float(closes[-1])
                tech["ma20"] = _ma(closes, 20); tech["ma60"] = _ma(closes, 60)
                tech["above_ma20"] = tech["price"] > (tech["ma20"] or 0)
                tech["above_ma60"] = tech["price"] > (tech["ma60"] or 0)
                # MACD
                def _ema(a, w):
                    r = np.empty_like(a); r[0]=a[0]; k=2/(w+1)
                    for i in range(1,len(a)): r[i]=a[i]*k+r[i-1]*(1-k); return r
                dif = _ema(closes,12) - _ema(closes,26); dea = _ema(dif,9)
                tech["macd"] = float((dif[-1]-dea[-1])*2)
                tech["macd_trend"] = "金叉" if dif[-1]>dea[-1] and dif[-2]<=dea[-2] else \
                                     "死叉" if dif[-1]<dea[-1] and dif[-2]>=dea[-2] else \
                                     "多头" if dif[-1]>dea[-1] else "空头"
                # RSI
                d = np.diff(closes); g = np.where(d>0,d,0); l = np.where(d<0,-d,0)
                if len(g)>=14:
                    ag = np.mean(g[-14:]); al = np.mean(l[-14:])
                    tech["rsi"] = float(100 - 100/(1+ag/max(al,0.001)))
                # 生命周期 + 波浪
                sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
                from stock_compare import _detect_lifecycle, _detect_elliott_wave
                lc_phase, lc_desc = _detect_lifecycle(closes, kline["data"]["成交量"].values.astype(float))
                tech["lc_phase"] = lc_phase; tech["lc_desc"] = lc_desc
                tech["wave"] = _detect_elliott_wave(closes)
            except Exception as e: print(f"[技术面] {e}")

            win.after(0, lambda: _apply_data(name, kline, fund, tech))

        threading.Thread(target=_bg, daemon=True).start()

    def _apply_data(name, kline, fund, tech):
        global _hover_tt
        _hover_tt = None
        _current_name = name; _current_kline = kline
        _current_fund = fund; _current_tech = tech
        _render_methods()
        _redraw_chart()
        status_var.set(f"✅ {name}({stock_var.get().strip()}) 分析完成 | {tech.get('lc_desc','')}")
        # AI 综合
        if call_ai_fn:
            def _ai_bg():
                _lines = []
                for _k, _v in fund.items(): _lines.append(f"{_k}={_v}")
                for _k, _v in tech.items():
                    if _k not in ("ts_code",): _lines.append(f"{_k}={_v}")
                try:
                    res = call_ai_fn(
                        f"股票「{name}({stock_var.get().strip()})」基本面+技术面数据:\n"
                        + "\n".join(_lines) +
                        "\n\n请输出【3句话板块判断】【买点/卖点/持有】【主要风险】"
                        "\n代码直接给6位数字, 简洁!",
                        system_prompt="你是A股投顾, 回答中文简洁分点", max_tokens=400)
                    if isinstance(res, str) and len(res) > 10:
                        win.after(0, lambda: _update_ai(res))
                except Exception: pass
            threading.Thread(target=_ai_bg, daemon=True).start()

    def _update_ai(text):
        for w in methods_inner.winfo_children():
            if "AI" in (w.winfo_name() or ""): continue
        lf = tk.LabelFrame(methods_inner, text="  🤖 AI 综合操盘建议  ",
                           bg="#FFF8E1", fg="#F57F17", font=("", 10, "bold"), relief=tk.FLAT, bd=1)
        lf.pack(fill=tk.X, padx=6, pady=4)
        tb = tk.Text(lf, bg="#FFFDF5", fg="#333", font=("", 10), wrap=tk.WORD,
                     height=8, relief=tk.FLAT, padx=8, pady=6)
        tb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        tb.insert("1.0", text)
        tb.configure(state=tk.DISABLED)

    search_btn.configure(command=_do_search)

    # 初始加载候选
    def _load_candidates():
        cands = _collect_candidates()
        combo.configure(values=cands)
        # 优先预填 auto_code (来自工具栏/双击入口)
        target = auto_code or ""
        if target:
            # 去掉 sh/sz 前缀
            t6 = re.sub(r"^(sh|sz|bj|SH|SZ|BJ)", "", target)
            combo.set(t6)
            status_var.set(f"🎯 自动加载: {auto_name or t6}")
            # 自动触发分析
            win.after(300, _do_search)
        elif cands:
            combo.set(cands[0])
            status_var.set(f"✅ 候选 {len(cands)} 只 (持仓+涨停)")
        else:
            status_var.set("⚠️ 未找到候选股, 请手动输入")
    threading.Thread(target=_load_candidates, daemon=True).start()

    win.bind("<Return>", lambda e: _do_search())
    win.mainloop()


if __name__ == "__main__":
    show_stock_analysis_dialog()
