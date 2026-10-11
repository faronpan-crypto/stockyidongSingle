# -*- coding: utf-8 -*-
"""
📊 股票比价 — 同板块龙头股横向对比
==================================
输入: 板块名称 (申万行业 / 概念) → 取前 10 龙头 (不够则 5/3)
输出: 基本面 + 技术面 + 情绪面 + AI 综合评价 + matplotlib 图形化对比
      + 操作建议 (买/卖/持有/减仓) + 基金持有情况 + 利好/估值等

数据源: Tushare (申万行业 index_classify + index_member) + akshare spot_em + call_ai_model
"""
import os
import re
import sys
import json
import threading
import webbrowser
from typing import Dict, List, Tuple, Optional, Any

# ===== 工具函数 =====
def _safe_float(v, default=None):
    try: return float(v) if v not in ("", "-", None) else default
    except: return default

def _get_tushare_pro():
    """拿 tushare pro (env var 方式, 避免 macOS tk.csv 权限问题)"""
    import tushare as ts
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token: return None
    try:
        ts.set_token(token)
        return ts.pro_api()
    except Exception: return None

def _load_industry_boards() -> List[Dict]:
    """申万一级行业列表 (31 个)"""
    pro = _get_tushare_pro()
    if not pro: return []
    try:
        df = pro.index_classify(level="L1", src="SW2021")
        if df is None or len(df) == 0: return []
        return [{"index_code": r["index_code"], "name": r["industry_name"], "type": "申万行业"}
                for _, r in df.iterrows()]
    except Exception: return []

def _load_concept_boards(limit=100) -> List[Dict]:
    """概念板块 (取有 item_size 大小的前 limit)"""
    pro = _get_tushare_pro()
    if not pro: return []
    try:
        df = pro.concept()
        if df is None or len(df) == 0: return []
        df = df.sort_values("item_size", ascending=False).head(limit)
        return [{"index_code": r["ts_code"], "name": r["name"], "type": "概念",
                 "size": int(r["item_size"]) if r["item_size"] else 0}
                for _, r in df.iterrows()]
    except Exception: return []

def _get_board_members(index_code: str) -> List[str]:
    """板块成分股 (申万用 index_member, 概念用 concept_detail)"""
    pro = _get_tushare_pro()
    if not pro: return []
    try:
        if ".SI" in index_code:  # 申万
            df = pro.index_member(index_code=index_code)
            if df is None: return []
            return df["con_code"].dropna().tolist()
        else:  # 概念
            df = pro.concept_detail(id=index_code)
            if df is None: return []
            # concept_detail 返回成分, ts_code 列名可能不同
            for col in df.columns:
                if "code" in col.lower() and "ts" in col.lower():
                    return df[col].dropna().tolist()
            return []
    except Exception as e:
        print(f"[板块] 获取成分失败 {index_code}: {e}")
        return []

def _get_top_by_mv(codes: List[str], top_n: int = 10) -> List[str]:
    """按市值排序取前 top_n (用 spot_em 或 daily_basic)"""
    if not codes: return []
    # 先尝试 tushare daily_basic (批量)
    pro = _get_tushare_pro()
    results: List[Tuple[float, str]] = []  # (mv, ts_code)
    if pro:
        # daily_basic 不支持批量 ts_code, 只能逐只, 限速 500次/min
        for tsc in codes[:15]:  # 最多查 15 只
            try:
                df = pro.daily_basic(ts_code=tsc, limit=1,
                                     fields="ts_code,total_mv,turnover_rate,pe_ttm,pb,roe")
                if df is not None and len(df) > 0:
                    mv = _safe_float(df.iloc[0]["total_mv"], 0) or 0
                    results.append((mv, tsc))
            except Exception: pass
    if results:
        results.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in results[:top_n]]
    # daily_basic 全挂 — 直接返回前 top_n (不排序)
    return codes[:top_n]

def _fetch_stock_fundamentals(tsc: str) -> Dict:
    """单只股票基本面: PE/PB/ROE/市值/营收增速/净利润"""
    pro = _get_tushare_pro()
    res = {"ts_code": tsc, "pe": None, "pb": None, "roe": None, "mv": None,
           "tr": None, "revenue_yoy": None, "profit_yoy": None}
    if not pro: return res
    try:
        df = pro.daily_basic(ts_code=tsc, limit=1,
                             fields="turnover_rate,pe_ttm,pb,total_mv")
        if df is not None and len(df) > 0:
            r = df.iloc[0]
            res["pe"] = _safe_float(r.get("pe_ttm"))
            res["pb"] = _safe_float(r.get("pb"))
            res["mv"] = _safe_float(r.get("total_mv"))
            res["tr"] = _safe_float(r.get("turnover_rate"))
    except Exception: pass
    # roe / 财报增速 (income 表)
    try:
        fi = pro.fina_indicator(ts_code=tsc, limit=1,
                                fields="ts_code,roe,revenue_yoy,n_income_yoy")
        if fi is not None and len(fi) > 0:
            r = fi.iloc[0]
            res["roe"] = _safe_float(r.get("roe"))
            res["revenue_yoy"] = _safe_float(r.get("revenue_yoy"))
            res["profit_yoy"] = _safe_float(r.get("n_income_yoy"))
    except Exception: pass
    return res

def _fetch_tech_indicators(tsc: str, days: int = 120) -> Dict:
    """技术面: MA/MACD/RSI/量比"""
    import numpy as np
    res = {"ts_code": tsc, "ma5": None, "ma20": None, "ma60": None,
           "macd": None, "rsi": None, "vol_ratio": None, "chg_5d": None, "chg_20d": None}
    pro = _get_tushare_pro()
    if not pro: return res
    try:
        df = pro.daily(ts_code=tsc, limit=days, fields="ts_code,trade_date,open,high,low,close,vol,amount")
        if df is None or len(df) < 30: return res
        df = df.sort_values("trade_date").reset_index(drop=True)
        closes = df["close"].values.astype(float)
        vols = df["vol"].values.astype(float)
        # MA
        for p in [5, 20, 60]:
            if len(closes) >= p:
                res[f"ma{p}"] = float(np.mean(closes[-p:]))
        # 最新价 vs MA20/60
        res["price"] = float(closes[-1])
        res["above_ma20"] = res["price"] > (res["ma20"] or 0)
        res["above_ma60"] = res["price"] > (res["ma60"] or 0)
        # MACD
        def _ema(a, w):
            r = np.empty_like(a); r[0] = a[0]; k = 2 / (w + 1)
            for i in range(1, len(a)): r[i] = a[i] * k + r[i-1] * (1 - k)
            return r
        ema12 = _ema(closes, 12); ema26 = _ema(closes, 26)
        dif = ema12 - ema26; dea = _ema(dif, 9); macd = (dif - dea) * 2
        res["macd"] = float(macd[-1])
        res["macd_trend"] = "金叉" if dif[-1] > dea[-1] and dif[-2] <= dea[-2] else \
                            "死叉" if dif[-1] < dea[-1] and dif[-2] >= dea[-2] else \
                            "多头" if dif[-1] > dea[-1] else "空头"
        # RSI
        delta = np.diff(closes); gain = np.where(delta > 0, delta, 0); loss = np.where(delta < 0, -delta, 0)
        if len(gain) >= 14:
            ag = np.mean(gain[-14:]); al = np.mean(loss[-14:])
            if al > 0:
                rs = ag / al; res["rsi"] = float(100 - 100 / (1 + rs))
            else: res["rsi"] = 100.0 if ag > 0 else 50.0
        # 量比 (近5日均量 vs 近20日均量)
        if len(vols) >= 20:
            res["vol_ratio"] = float(np.mean(vols[-5:]) / max(np.mean(vols[-20:]), 1))
        # 涨跌幅
        if len(closes) >= 20:
            res["chg_5d"] = float((closes[-1] / closes[-5] - 1) * 100)
            res["chg_20d"] = float((closes[-1] / closes[-20] - 1) * 100)
    except Exception as e:
        print(f"[技术面] {tsc} 失败: {e}")
    return res

def _fetch_holder_info(tsc: str) -> Dict:
    """基金持有 / 北向 / 龙虎榜"""
    res = {"ts_code": tsc, "fund_hold_count": None, "north_hold": None, "lhb_count_90d": 0}
    pro = _get_tushare_pro()
    if not pro: return res
    # 龙虎榜 90d 频次 (SQLite 兜底)
    try:
        import sqlite3
        _dbs = [
            os.path.expanduser("~/.stockyidong_dapan_cache.json"),  # 不是 db
        ]
        # 直接扫项目里 SQL
        for root, _, files in os.walk(os.path.expanduser("~/Agent/stockyidong_project")):
            for f in files:
                if f.endswith(".db") and "stock" in f.lower():
                    try:
                        conn = sqlite3.connect(os.path.join(root, f))
                        cur = conn.cursor()
                        tsc_short = tsc.split(".")[0]
                        cur.execute("SELECT COUNT(*) FROM lhb_records WHERE stock_code LIKE ?", (f"%{tsc_short}%",))
                        res["lhb_count_90d"] = cur.fetchone()[0]
                        conn.close()
                    except Exception: pass
    except Exception: pass
    return res


# ========== UI 弹窗 ==========
def show_stock_compare_dialog(parent_win=None, call_ai_fn=None):
    """📊 股票比价弹窗 — 板块选择 → 并行拉基本面/技术面/情绪面 → 图形化对比"""
    import tkinter as tk
    from tkinter import ttk, messagebox
    import threading
    import webbrowser
    import time

    win = tk.Toplevel(parent_win) if parent_win else tk.Tk()
    win.title("📊 同板块股票横向对比")
    win.geometry("1280x860")
    win.minsize(1000, 720)
    win.configure(bg="#F5F5F5")

    # ===== 顶栏 =====
    top = tk.Frame(win, bg="#263238"); top.pack(fill=tk.X)
    tk.Label(top, text="📊 同板块龙头股横向对比", bg="#263238", fg="#FFB300",
             font=("", 14, "bold")).pack(side=tk.LEFT, padx=14, pady=10)

    # 板块选择
    sel_f = tk.Frame(top, bg="#263238"); sel_f.pack(side=tk.LEFT, padx=10)
    tk.Label(sel_f, text="板块类型:", bg="#263238", fg="white", font=("", 10)).pack(side=tk.LEFT)
    board_type_var = tk.StringVar(value="申万行业")
    ttk.Combobox(sel_f, textvariable=board_type_var, values=["申万行业", "概念板块"],
                 width=10, state="readonly").pack(side=tk.LEFT, padx=4)

    tk.Label(sel_f, text="名称:", bg="#263238", fg="white", font=("", 10)).pack(side=tk.LEFT, padx=(10, 0))
    board_name_var = tk.StringVar()
    board_combo = ttk.Combobox(sel_f, textvariable=board_name_var, width=18, state="readonly")
    board_combo.pack(side=tk.LEFT, padx=4)

    topn_var = tk.IntVar(value=10)
    tk.Label(sel_f, text="取前:", bg="#263238", fg="white", font=("", 10)).pack(side=tk.LEFT, padx=(10, 0))
    ttk.Combobox(sel_f, textvariable=topn_var, values=[3, 5, 10], width=4,
                 state="readonly").pack(side=tk.LEFT, padx=4)

    status_var = tk.StringVar(value="⏳ 加载板块列表...")
    tk.Label(top, textvariable=status_var, bg="#263238", fg="#90A4AE",
             font=("", 8)).pack(side=tk.RIGHT, padx=12)

    # ===== 按钮 =====
    btn_row = tk.Frame(win, bg="#F5F5F5"); btn_row.pack(fill=tk.X, pady=(6, 2))

    # ===== 主布局 (PanedWindow) =====
    try:
        pw_v = tk.PanedWindow(win, orient=tk.VERTICAL, bg="#F5F5F5", sashwidth=6)
        pw_v.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))
    except Exception:
        pw_v = None

    # --- 上: Treeview ---
    top_f = tk.Frame(pw_v or win, bg="#FAFAFA")
    cols = ("股票", "代码", "市值亿", "PE", "PB", "ROE", "换手率", "营收增速",
            "MA20位置", "MACD", "RSI", "量比", "5日涨跌", "20日涨跌")
    tv = ttk.Treeview(top_f, columns=cols, show="headings", height=10)
    _widths = [100, 90, 80, 60, 55, 55, 65, 75, 85, 70, 55, 55, 65, 70]
    for c, w in zip(cols, _widths):
        tv.heading(c, text=c); tv.column(c, width=w, anchor="center")
    sb = ttk.Scrollbar(top_f, orient=tk.VERTICAL, command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)
    tv.tag_configure("buy", background="#C8E6C9")     # 建议买入
    tv.tag_configure("sell", background="#FFCDD2")    # 建议卖出
    tv.tag_configure("hold", background="#FFF9C4")    # 建议持有
    tv.tag_configure("reduce", background="#FFE0B2")  # 建议减仓

    if pw_v:
        pw_v.add(top_f, minsize=120)

    # --- 下: PanedWindow 水平 (AI建议 + matplotlib) ---
    try:
        pw_h_parent = tk.Frame(pw_v or win, bg="#F5F5F5")
        if pw_v: pw_v.add(pw_h_parent, minsize=200)
        pw_h = tk.PanedWindow(pw_h_parent, orient=tk.HORIZONTAL, bg="#F5F5F5", sashwidth=6)
        pw_h.pack(fill=tk.BOTH, expand=True)
    except Exception:
        pw_h = None; pw_h_parent = tk.Frame(pw_v or win, bg="#F5F5F5")
        if pw_v: pw_v.add(pw_h_parent)

    ai_container = tk.Frame(pw_h or pw_h_parent, bg="#F5F5F5")
    chart_container = tk.Frame(pw_h or pw_h_parent, bg="#F5F5F5")
    if pw_h:
        pw_h.add(ai_container, minsize=300)
        pw_h.add(chart_container, minsize=400)
    else:
        ai_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        chart_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # ===== 左: AI 综合建议 =====
    ai_f = tk.LabelFrame(ai_container, text="🤖 AI 综合操盘建议",
                         bg="#FFF8E1", fg="#F57F17", font=("", 10, "bold"))
    ai_f.pack(fill=tk.BOTH, expand=True, pady=2)
    ai_text = tk.Text(ai_f, bg="#FFFDF5", fg="#333", font=("", 11),
                      wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=8,
                      state=tk.DISABLED, cursor="hand2")
    ai_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
    ai_text.tag_configure("url", foreground="#1976D2", font=("", 11, "underline"))
    ai_text.tag_configure("hdr", foreground="#4527A0", font=("", 12, "bold"))
    ai_text.tag_configure("buy", foreground="#2E7D32", font=("", 11, "bold"))
    ai_text.tag_configure("sell", foreground="#C62828", font=("", 11, "bold"))
    ai_text.tag_configure("hold", foreground="#F57F17", font=("", 11, "bold"))

    # ===== 右: matplotlib 图形化 =====
    try:
        import matplotlib
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti SC", "SimHei"]
        plt.rcParams["axes.unicode_minus"] = False
        _MPL_OK = True
    except Exception:
        _MPL_OK = False
    chart_f = tk.LabelFrame(chart_container, text="📊 图形化对比",
                            bg="#E3F2FD", fg="#1565C0", font=("", 10, "bold"))
    chart_f.pack(fill=tk.BOTH, expand=True, pady=2)
    _chart_ph = tk.Label(chart_f, text="⏳ 选择板块 → 🔍搜索 后自动生成...",
                         bg="#E3F2FD", fg="#666", font=("", 10))
    _chart_ph.pack(pady=30)

    fig = None; canvas = None
    _current_compare: List[Dict] = []

    # ========= 核心流程 =========
    def _load_boards():
        def _bg():
            status_var.set("⏳ 加载行业/概念板块列表...")
            boards = _load_industry_boards() if board_type_var.get() == "申万行业" else _load_concept_boards()
            # 概念板块排序按 item_size 大的先
            if board_type_var.get() == "概念":
                boards = sorted(boards, key=lambda x: -x.get("size", 0))
            names = [b["name"] for b in boards]
            def _apply():
                board_combo.configure(values=names)
                if names: board_name_var.set(names[0])
                board_combo._boards = boards
                status_var.set(f"✅ {board_type_var.get()} 加载完成, 共 {len(boards)} 个")
            win.after(0, _apply)
        threading.Thread(target=_bg, daemon=True).start()

    _load_boards()

    # 切换类型时刷新列表
    def _on_type_change(_e=None):
        _load_boards()
    board_type_var.trace_add("write", lambda *_: _load_boards())

    def _decide_action(fund: Dict, tech: Dict) -> str:
        """综合基本面+技术面 → 建议 buy/sell/hold/reduce"""
        score = 0
        # PE (低估加分)
        pe = fund.get("pe")
        if pe is not None and 5 < pe < 15: score += 2
        elif pe is not None and pe > 50: score -= 1
        # PB
        pb = fund.get("pb")
        if pb is not None and pb < 1.2: score += 1
        # ROE
        roe = fund.get("roe")
        if roe is not None and roe > 15: score += 2
        elif roe is not None and roe < 3: score -= 1
        # 营收增速
        rev = fund.get("revenue_yoy")
        if rev is not None and rev > 20: score += 1
        # 技术面
        if tech.get("above_ma20"): score += 1
        if tech.get("macd"):
            trend = tech.get("macd_trend", "")
            if trend in ("金叉", "多头"): score += 1
            elif trend in ("死叉", "空头"): score -= 1
        rsi = tech.get("rsi")
        if rsi is not None and rsi < 30: score += 1
        elif rsi is not None and rsi > 70: score -= 1
        chg5 = tech.get("chg_5d")
        if chg5 is not None and chg5 < -8: score -= 1
        # 决策
        if score >= 4: return "buy"
        elif score >= 2: return "hold"
        elif score >= 0: return "reduce"
        else: return "sell"

    def _do_compare():
        board_name = board_name_var.get().strip()
        if not board_name or not hasattr(board_combo, "_boards"):
            messagebox.showinfo("提示", "请先选择板块")
            return
        board = next((b for b in board_combo._boards if b["name"] == board_name), None)
        if not board: return
        topn = topn_var.get()

        status_var.set(f"⏳ 获取 {board_name} 成分股...")
        for it in tv.get_children(): tv.delete(it)
        _chart_ph.pack(pady=30)
        ai_text.configure(state=tk.NORMAL); ai_text.delete("1.0", tk.END); ai_text.configure(state=tk.DISABLED)

        def _bg():
            codes = _get_board_members(board["index_code"])
            win.after(0, lambda: status_var.set(f"⏳ {board_name} 共 {len(codes)} 只成分, 取市值前 {topn}..."))
            top_codes = _get_top_by_mv(codes, topn)
            win.after(0, lambda: status_var.set(f"⏳ 并行拉 {len(top_codes)} 只的基本面/技术面..."))

            results = []
            def _one(tsc):
                f = _fetch_stock_fundamentals(tsc)
                t = _fetch_tech_indicators(tsc)
                h = _fetch_holder_info(tsc)
                action = _decide_action(f, t)
                # 名字 (tushare 拿不到, 直接用代码)
                results.append({"ts_code": tsc, "fund": f, "tech": t, "holder": h, "action": action})

            threads = [threading.Thread(target=_one, args=(c,), daemon=True) for c in top_codes]
            for th in threads: th.start()
            for th in threads: th.join(timeout=8)

            # 排序: 买入优先 → 持有 → 减仓 → 卖出
            _act_order = {"buy": 0, "hold": 1, "reduce": 2, "sell": 3}
            results.sort(key=lambda x: (_act_order.get(x["action"], 9), -((x["fund"].get("mv") or 0))))

            win.after(0, lambda: _render(results, board))

        threading.Thread(target=_bg, daemon=True).start()

    tk.Button(btn_row, text="🔍 对比板块", command=_do_compare,
              bg="#FFB300", fg="#1A237E", font=("", 10, "bold"),
              relief=tk.FLAT, padx=14).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_row, text="🤖 AI重跑建议", command=lambda: _do_ai_only(board_name_var.get(), _current_compare),
              bg="#FF9800", fg="white", font=("", 9, "bold"),
              relief=tk.FLAT, padx=10).pack(side=tk.LEFT, padx=2)

    def _render(results: List[Dict], board: Dict):
        nonlocal _current_compare
        _current_compare = results
        _names_map = {}
        for r in results:
            f = r["fund"]; t = r["tech"]
            tsc = r["ts_code"]
            code6 = tsc.split(".")[0]
            tv.insert("", tk.END, values=(
                _names_map.get(code6, code6), tsc,
                f"{(f.get('mv') or 0) / 10000:.1f}" if f.get("mv") else "—",
                f"{f.get('pe'):.1f}" if f.get("pe") else "—",
                f"{f.get('pb'):.2f}" if f.get("pb") else "—",
                f"{f.get('roe'):.1f}%" if f.get("roe") else "—",
                f"{f.get('tr'):.2f}%" if f.get("tr") else "—",
                f"{f.get('revenue_yoy'):.1f}%" if f.get("revenue_yoy") else "—",
                "↑MA20" if t.get("above_ma20") else "↓MA20",
                t.get("macd_trend") or "—",
                f"{t.get('rsi'):.0f}" if t.get("rsi") else "—",
                f"{t.get('vol_ratio'):.2f}" if t.get("vol_ratio") else "—",
                f"{t.get('chg_5d'):.1f}%" if t.get("chg_5d") else "—",
                f"{t.get('chg_20d'):.1f}%" if t.get("chg_20d") else "—",
            ), tags=(r["action"],))
        win.after(0, lambda: status_var.set(f"✅ {board['name']} 对比完成 | "
                                            f"买入={sum(1 for r in results if r['action']=='buy')} | "
                                            f"持有={sum(1 for r in results if r['action']=='hold')} | "
                                            f"减仓={sum(1 for r in results if r['action']=='reduce')} | "
                                            f"卖出={sum(1 for r in results if r['action']=='sell')}"))
        _render_chart(results)
        _do_ai_only(board_name_var.get(), results)

    def _render_chart(results: List[Dict]):
        nonlocal fig, canvas
        if not _MPL_OK or not results: return
        try: _chart_ph.pack_forget()
        except Exception: pass

        labels = [r["ts_code"].split(".")[0] for r in results]
        # 市值 (亿元)
        mvs = [(r["fund"].get("mv") or 0) / 10000 for r in results]
        # PE
        pes = [r["fund"].get("pe") or 0 for r in results]
        # ROE
        roes = [r["fund"].get("roe") or 0 for r in results]
        # 技术面综合分
        tech_scores = []
        for r in results:
            t = r["tech"]; s = 0
            if t.get("above_ma20"): s += 1
            if t.get("above_ma60"): s += 1
            trend = t.get("macd_trend", "")
            if trend in ("金叉", "多头"): s += 1
            if t.get("rsi", 50) < 30: s += 1
            elif t.get("rsi", 50) > 70: s -= 1
            tech_scores.append(s)
        # 雷达图标签 (买入/持有/减仓/卖出)
        _action_color = {"buy": "#2E7D32", "hold": "#F57F17", "reduce": "#FF8F00", "sell": "#C62828"}
        colors = [_action_color.get(r["action"], "#888") for r in results]

        fig = Figure(figsize=(7.2, 5.8), dpi=92, facecolor="#E3F2FD")
        ax1 = fig.add_subplot(2, 2, 1)   # 市值
        ax2 = fig.add_subplot(2, 2, 2)   # PE
        ax3 = fig.add_subplot(2, 2, 3)   # ROE + 营收增速
        ax4 = fig.add_subplot(2, 2, 4)   # 操作建议气泡
        fig.subplots_adjust(left=0.08, right=0.98, top=0.92, bottom=0.06, wspace=0.4, hspace=0.45)

        # 图1: 市值条形
        bars1 = ax1.barh(labels, mvs, color=colors)
        ax1.set_title("🏢 市值对比 (亿)", fontsize=10, fontweight="bold")
        ax1.set_xlabel("亿元", fontsize=8); ax1.grid(axis="x", alpha=0.3)
        for i, v in enumerate(mvs):
            if v > 0: ax1.text(v, i, f" {v:.0f}", va="center", fontsize=8)

        # 图2: PE (剔除负PE)
        pe_labels = [labels[i] for i, v in enumerate(pes) if v > 0 and v < 300]
        pe_vals = [v for v in pes if v > 0 and v < 300]
        pe_col = [colors[i] for i, v in enumerate(pes) if v > 0 and v < 300]
        if pe_vals:
            bars2 = ax2.bar(pe_labels, pe_vals, color=pe_col)
            ax2.axhline(y=20, color="#999", linestyle="--", linewidth=0.8, label="合理 PE=20")
            ax2.legend(fontsize=8)
        ax2.set_title("💰 PE对比 (越低越便宜)", fontsize=10, fontweight="bold")
        ax2.set_ylabel("PE", fontsize=8); ax2.tick_params(axis="x", rotation=30, labelsize=8)
        ax2.grid(axis="y", alpha=0.3)

        # 图3: ROE vs 营收增速 (双轴)
        x = range(len(labels))
        roe_vals = [max(-20, min(40, v)) for v in roes]
        rev_vals = [max(-50, min(100, r["fund"].get("revenue_yoy") or 0)) for r in results]
        ax3a = ax3
        b3a = ax3a.bar([i - 0.2 for i in x], roe_vals, width=0.4, color="#1976D2", label="ROE%")
        ax3b = ax3a.twinx()
        b3b = ax3b.bar([i + 0.2 for i in x], rev_vals, width=0.4, color="#43A047", label="营收增速%")
        ax3a.set_xticks(list(x)); ax3a.set_xticklabels(labels, fontsize=8, rotation=30)
        ax3a.set_title("📈 ROE vs 营收增速", fontsize=10, fontweight="bold")
        ax3a.axhline(y=15, color="#999", linestyle="--", linewidth=0.6)
        ax3a.axhline(y=0, color="#999", linewidth=0.5)
        lines1, labels1 = ax3a.get_legend_handles_labels()
        lines2, labels2 = ax3b.get_legend_handles_labels()
        ax3a.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper right")

        # 图4: 操作建议散点气泡
        ax4.axis("off")
        _action_text = {"buy": "🟢 买入", "hold": "🟡 持有", "reduce": "🟠 减仓", "sell": "🔴 卖出"}
        y_positions = [0.85, 0.70, 0.55, 0.40, 0.25, 0.10]
        for i, r in enumerate(results[:6]):
            y = y_positions[i % len(y_positions)]
            tsc = r["ts_code"].split(".")[0]
            action = r["action"]
            mv = (r["fund"].get("mv") or 0) / 10000
            pe = r["fund"].get("pe") or 0
            chg20 = r["tech"].get("chg_20d") or 0
            ax4.text(0.02, y, _action_text.get(action, "?"), fontsize=10, fontweight="bold",
                     color=_action_color.get(action, "#888"), transform=ax4.transAxes)
            ax4.text(0.22, y, f"{tsc}  市值{mv:.0f}亿  PE{pe:.1f}  20日{chg20:+.1f}%",
                     fontsize=9, transform=ax4.transAxes, va="center")
        if len(results) > 6:
            ax4.text(0.02, 0.0, f"... 还有 {len(results)-6} 只, 详见左侧 Treeview",
                     fontsize=8, color="#888", transform=ax4.transAxes)
        ax4.set_title("🎯 操作建议汇总", fontsize=10, fontweight="bold")

        if canvas:
            try: canvas.get_tk_widget().destroy()
            except Exception: pass
        canvas = FigureCanvasTkAgg(fig, master=chart_f)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _do_ai_only(board_name: str, results: List[Dict]):
        """调 AI 给综合建议"""
        if not call_ai_fn: return
        def _bg():
            win.after(0, lambda: ai_text.configure(state=tk.NORMAL) or ai_text.delete("1.0", tk.END) or
                      ai_text.insert(tk.END, "⏳ AI 正在生成综合建议...") or ai_text.configure(state=tk.DISABLED))
            # 构建 summary
            _lines = []
            for r in results[:8]:
                tsc = r["ts_code"].split(".")[0]
                f = r["fund"]; t = r["tech"]
                _lines.append(
                    f"{tsc}: 市值{(f.get('mv') or 0)/10000:.0f}亿 PE={f.get('pe') or '-'} "
                    f"ROE={f.get('roe') or '-'}% 营收增={f.get('revenue_yoy') or '-'}% "
                    f"MA20↑={t.get('above_ma20')} MACD={t.get('macd_trend')} RSI={t.get('rsi',0):.0f} "
                    f"20日涨跌={t.get('chg_20d',0):.1f}%"
                )
            _data_text = "\n".join(_lines)
            system_p = "你是A股机构级投顾, 擅长行业横向对比选股。回答中文, 分点简洁。"
            prompt = (f"板块「{board_name}」{len(results)} 只龙头股基本面+技术面横向对比数据:\n"
                      f"{_data_text}\n\n"
                      f"请输出:\n"
                      f"【板块整体判断】3 句话 (热度/估值/催化剂)\n"
                      f"【最值得买 Top2】代码 + 理由 (估值低/技术好/有催化剂)\n"
                      f"【最该避开 Top2】代码 + 理由\n"
                      f"【机构操作建议】基金持有 / 北向动向 / 龙虎榜活跃度\n"
                      f"【风险提示】2-3 条\n\n"
                      f"📌 代码直接给 6 位数字, 方便用户快速查。")
            try:
                res = call_ai_fn(prompt, system_prompt=system_p, max_tokens=800)
                if isinstance(res, str) and len(res) > 10:
                    win.after(0, lambda: _show_ai(res))
                else:
                    win.after(0, lambda: _show_ai(f"⚠️ AI 返回异常: {str(res)[:200]}"))
            except Exception as e:
                win.after(0, lambda: _show_ai(f"⚠️ AI 调用失败: {e}"))
        threading.Thread(target=_bg, daemon=True).start()

    def _show_ai(text: str):
        import re as _r
        ai_text.configure(state=tk.NORMAL)
        ai_text.delete("1.0", tk.END)
        t = (text or "").strip()
        for line in t.split("\n"):
            line = line.rstrip()
            m = _r.match(r"^【(.+?)】", line)
            tag = "hdr" if m else ("buy" if "买入" in line or "值得买" in line or "TOP" in line.upper() else
                                  "sell" if "避开" in line or "卖出" in line else
                                  "hold" if "持有" in line or "操作建议" in line or "机构" in line else None)
            # 链接
            parts = _r.split(r"(https?://\S+)", line)
            for seg in parts:
                if not seg: continue
                if _r.match(r"^https?://", seg):
                    ai_text.insert(tk.END, seg, "url")
                elif tag:
                    ai_text.insert(tk.END, seg, tag)
                else:
                    ai_text.insert(tk.END, seg)
            ai_text.insert(tk.END, "\n")
        ai_text.configure(state=tk.DISABLED)

    win.after(500, lambda: board_combo.focus_set())
    win.mainloop()


# ============ stub entry (from tab_dapan) ============
def _stub_show_stock_compare(self):
    """📊 股票比价 — lazy import stub"""
    import traceback as _tb
    print("[📊股票比价] 按钮被点击!", flush=True)
    try:
        from ui.stock_compare import show_stock_compare_dialog as _sc
        ai_fn = getattr(self, 'call_ai_model', None)
        _sc(getattr(self, 'root', None) or getattr(self, '_root', None), call_ai_fn=ai_fn)
    except Exception as e:
        print(f"[📊股票比价❌] {e}", flush=True)
        _tb.print_exc()


if __name__ == "__main__":
    show_stock_compare_dialog()
