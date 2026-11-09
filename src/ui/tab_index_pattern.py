# -*- coding: utf-8 -*-
"""
📈 指数日走势形态统计工具
用途: 统计指数/ETF/个股 近 N 天 每日的高开高走/高开低走/低开高走/低开低走 分布
      → 指导做 T 时机
数据源: AKShare (东方财富)
"""
import re
import threading
import queue
import tkinter as tk
from tkinter import ttk, scrolledtext
from collections import Counter


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
    拉 K 线数据

    Returns:
        DataFrame with columns: date, open, high, low, close, volume, prev_close, gap_pct, body_pct, pattern
        or None on failure
    """
    import akshare as ak
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

    try:
        if kind == "index":
            df = ak.index_zh_a_hist(symbol=code, period="daily",
                                    start_date=start, end_date=end)
            if df is None or len(df) == 0:
                # 试 sh 前缀 (上证指数 000001 走 stock_zh_index_daily)
                try:
                    sh_code = f"sh{code}" if code.startswith("000") or code.startswith("88") or code.startswith("89") else f"sz{code}"
                    df2 = ak.stock_zh_index_daily(symbol=sh_code)
                    if df2 is not None and len(df2) > 0:
                        df2 = df2.rename(columns={"date": "日期", "open": "开盘",
                                                  "high": "最高", "low": "最低",
                                                  "close": "收盘", "volume": "成交量"})
                        df = df2
                except Exception:
                    pass
        elif kind == "etf":
            # ETF: fund_etf_hist_em (stock_zh_a_hist 对 ETF 返回空)
            df = ak.fund_etf_hist_em(symbol=code, period="daily",
                                     start_date=start, end_date=end, adjust="qfq")
        else:
            # stock: stock_zh_a_hist
            df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                    start_date=start, end_date=end, adjust="qfq")
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

    return df.tail(days).reset_index(drop=True)


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
# 🎨 弹窗 UI
# ═══════════════════════════════════════════════════════════════

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
    all_items = ([f"{n} ({c})" for n, c, _ in INDEX_PRESETS] +
                 [f"{n} ({c})" for n, c, _ in ETF_PRESETS])
    combo_var = tk.StringVar(value=all_items[0])
    cb = ttk.Combobox(ctrl, textvariable=combo_var, values=all_items,
                      width=28)  # 可编辑, 用户可直接输入6位代码
    cb.pack(side=tk.LEFT, padx=4)

    # 标的类型 (自定义时需要)
    type_var = tk.StringVar(value="自动")
    ttk.Combobox(ctrl, textvariable=type_var,
                 values=["自动", "指数", "ETF", "个股"],
                 width=6, state="readonly").pack(side=tk.LEFT, padx=(4, 0))

    # 时间窗口
    tk.Label(ctrl, text="窗口:", bg="#E3F2FD").pack(side=tk.LEFT, padx=(14, 2))
    win_var = tk.StringVar(value="60天")
    ttk.Combobox(ctrl, textvariable=win_var,
                 values=["5天", "10天", "20天", "30天", "60天", "120天"],
                 width=8, state="readonly").pack(side=tk.LEFT, padx=4)

    # 高开阈值
    tk.Label(ctrl, text="高开阈值:", bg="#E3F2FD").pack(side=tk.LEFT, padx=(14, 2))
    gap_var = tk.StringVar(value="0.3")
    ttk.Combobox(ctrl, textvariable=gap_var,
                 values=["0.1", "0.2", "0.3", "0.5", "1.0"],
                 width=5, state="readonly").pack(side=tk.LEFT, padx=4)
    tk.Label(ctrl, text="%", bg="#E3F2FD").pack(side=tk.LEFT)

    # 按钮
    status_var = tk.StringVar(value="⏳ 准备就绪")
    analyze_btn = ttk.Button(ctrl, text="▶ 开始统计", width=12)
    analyze_btn.pack(side=tk.RIGHT, padx=10)

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
    cols2 = ("date", "open", "close", "gap_pct", "body_pct", "pattern", "next_pct")
    tv2 = ttk.Treeview(tab2, columns=cols2, show="headings", height=20)
    for c in cols2:
        tv2.heading(c, text=c)
        widths = {"date": 100, "open": 80, "close": 80, "gap_pct": 80,
                  "body_pct": 80, "pattern": 120, "next_pct": 100}
        tv2.column(c, width=widths.get(c, 80), anchor="center")
    tv2.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    # 队列 + worker
    _q = _queue.Queue()
    _stop = threading.Event()

    def _render_complete(df, stats, label_text):
        """主线程渲染结果"""
        if not win.winfo_exists():
            return
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
        sug_text.insert(tk.END, f"📅 数据区间: {df['date'].iloc[0][:10]} ~ {df['date'].iloc[-1][:10]} "
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
            # 根据形态上色
            if "🟢" in str(r["pattern"]):
                tv2.tag_configure("up", background="#E8F5E9")
                tv2.item(row_id, tags=("up",))
            elif "🔴" in str(r["pattern"]):
                tv2.tag_configure("down", background="#FFEBEE")
                tv2.item(row_id, tags=("down",))

    def _poll():
        try:
            while True:
                msg = _q.get_nowait()
                if msg[0] == "progress":
                    status_var.set(msg[1])
                elif msg[0] == "done":
                    df, stats, label = msg[1], msg[2], msg[3]
                    _render_complete(df, stats, label)
                    return
                elif msg[0] == "error":
                    status_var.set(f"❌ {msg[1]}")
                    analyze_btn.config(state="normal")
                    return
        except _queue.Empty:
            if win.winfo_exists():
                win.after(150, _poll)

    def _auto_detect_kind(code):
        """根据代码自动判断类型"""
        code = str(code).strip()
        # 指数代码特征
        if code.startswith("000") or code.startswith("399") or code.startswith("899") or code.startswith("0006"):
            return "index"
        # ETF: 51xxxx/52xxxx (沪市) / 15xxxx/16xxxx (深市) / 58xxxx (科创板)
        if code.startswith("51") or code.startswith("52") or code.startswith("15") or code.startswith("16") or code.startswith("58"):
            return "etf"
        # 个股
        return "stock"

    def _on_analyze():
        analyze_btn.config(state="disabled")
        status_var.set("⏳ 拉取数据中...")

        # 解析选择 — 支持 "名称 (代码)" 或纯6位代码
        sel = combo_var.get().strip()
        m = re.match(r"(.+?)\s*\((\d{6})\)", sel)
        if m:
            # 预设格式
            name, code = m.group(1).strip(), m.group(2)
            kind = "index"
            for n, c, k in INDEX_PRESETS + ETF_PRESETS:
                if c == code:
                    kind = k; break
        else:
            # 自定义 — 提取6位代码
            cm = re.search(r"(\d{6})", sel)
            if not cm:
                status_var.set("❌ 请选择预设或输入6位代码")
                analyze_btn.config(state="normal"); return
            code = cm.group(1)
            name = sel.replace(code, "").strip() or f"标的{code}"
            # 用户指定 or 自动检测
            t = type_var.get()
            if t == "自动":
                kind = _auto_detect_kind(code)
            elif t == "指数":
                kind = "index"
            elif t == "ETF":
                kind = "etf"
            else:
                kind = "stock"

        gap_th = float(gap_var.get())

        def _worker():
            try:
                _q.put(("progress", f"📥 拉取 {name}({code}) K 线..."))
                full_df = fetch_kline(code, kind=kind, days=300)
                if full_df is None or len(full_df) < 30:
                    _q.put(("error", f"{name} 数据不足")); return

                window_days = int(win_var.get().replace("天", ""))
                work_df = full_df.tail(window_days + 60).copy()  # 多拉 60 天算前收
                # 补 next_pct
                work_df["next_pct"] = work_df["close"].shift(-1) / work_df["close"] - 1

                _q.put(("progress", f"🔍 分析形态分布..."))
                stats = analyze_pattern_stats(work_df, gap_threshold=gap_th)
                if stats is None:
                    _q.put(("error", "分析失败")); return

                # 补回 show_df
                full_df["next_pct"] = full_df["close"].shift(-1) / full_df["close"] - 1
                _q.put(("done", full_df, stats, f"{name}({code})"))
            except Exception as e:
                import traceback; traceback.print_exc()
                _q.put(("error", str(e)))

        threading.Thread(target=_worker, daemon=True).start()
        _poll()

    analyze_btn.config(command=_on_analyze)

    # 自动跑一次 (默认选中项)
    win.after(200, _on_analyze)
