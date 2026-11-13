# -*- coding: utf-8 -*-
"""
🌪️ 金融危机全景 — 历史复盘 / 结构性问题 / 金融战 / 世界格局 / 中国影响 / 全球实时资产
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import webbrowser


def show_crisis_dialog(parent=None):
    """主入口: 打开金融危机弹窗"""
    root = parent
    win = tk.Toplevel(root)
    win.title("🌪️ 金融危机全景 · 历史复盘 / 结构性问题 / 金融战 / 中国影响 / 全球资产实时")
    win.geometry("1280x820")
    win.configure(bg="#FAFAFA")
    if root is not None:
        try: win.transient(root)
        except Exception: pass

    # Banner
    banner = tk.Frame(win, bg="#B71C1C", height=44)
    banner.pack(fill=tk.X, padx=6, pady=(6, 4))
    banner.pack_propagate(False)
    tk.Label(banner, text="🌪️ 金融危机全景 · 历史复盘 / 结构性问题 / 金融战 / 世界格局 / 中国影响 / 全球资产",
             font=("Microsoft YaHei", 12, "bold"),
             bg="#B71C1C", fg="white").pack(side=tk.LEFT, padx=14)

    # 字体调节
    ctrl = tk.Frame(win, bg="#FAFAFA")
    ctrl.pack(fill=tk.X, padx=6, pady=(0, 4))
    tk.Label(ctrl, text="🔧字体:", bg="#FAFAFA", fg="#555", font=("", 9)).pack(side=tk.LEFT)
    size_var = tk.IntVar(value=9)
    size_cb = ttk.Combobox(ctrl, textvariable=size_var, width=4, state="readonly",
                           values=["8", "9", "10", "11", "12", "14"])
    size_cb.pack(side=tk.LEFT, padx=4)
    bg_var = tk.StringVar(value="#FAFAFA")
    tk.Label(ctrl, text="🎨背景:", bg="#FAFAFA", fg="#555", font=("", 9)).pack(side=tk.LEFT, padx=(10, 0))
    bg_cb = ttk.Combobox(ctrl, textvariable=bg_var, width=10, state="readonly",
                         values=["#FAFAFA", "#FFFFFF", "#FFF8E1", "#FCE4EC", "#E3F2FD", "#F1F8E9", "#1A1A2E"])
    bg_cb.pack(side=tk.LEFT, padx=4)
    _date_lbl = tk.Label(ctrl, text="📅 数据来源: 美联储FRED/IMF/Worldometers akshare实时数据 | 2026-11-13",
                         bg="#FAFAFA", fg="#999", font=("", 8))
    _date_lbl.pack(side=tk.RIGHT, padx=8)

    # 主 Notebook
    nb = ttk.Notebook(win)
    nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

    refs = {"size_var": size_var, "bg_var": bg_var, "text_widgets": []}

    # === 第一组: 历史复盘 ===
    _add_country_tab(nb, "🗺️ 世界危机", "#ECEFF1", WORLD_TEXT, refs)
    _add_country_tab(nb, "🇺🇸 美国危机", "#FFEBEE", US_TEXT, refs)
    _add_country_tab(nb, "🇯🇵 日本泡沫·少子化", "#FFF3E0", JP_TEXT, refs)
    _add_country_tab(nb, "🇪🇺 欧洲危机", "#E8EAF6", EU_TEXT, refs)
    _add_country_tab(nb, "🌎 南美·非洲", "#F3E5F5", SA_TEXT, refs)

    # === 第二组: 深层问题 (核心扩展) ===
    _add_country_tab(nb, "🏗️ 结构性问题", "#FFEBEE", STRUCTURAL_TEXT, refs)
    _add_country_tab(nb, "⚔️ 美国金融战", "#FFCDD2", FINANCIAL_WAR_TEXT, refs)
    _add_country_tab(nb, "🌍 世界格局演变", "#E1F5FE", WORLD_ORDER_TEXT, refs)
    _add_country_tab(nb, "📉 大萧条·影响链", "#ECEFF1", GREAT_DEPRESSION_TEXT, refs)

    # === 第三组: 中国视角 ===
    _add_country_tab(nb, "🇨🇳 影响·反思·预判", "#E8F5E9", CHINA_IMPACT_TEXT, refs)
    _add_live_assets_tab(nb, "📊 全球实时资产", "#FFF8E1", refs, win)

    # === 第四组: 书籍资源 ===
    _add_country_tab(nb, "📚 必读书籍", "#E8F5E9", BOOK_TEXT, refs)
    _add_country_tab(nb, "🔗 网络资源", "#E3F2FD", LINK_TEXT, refs)

    # 字体/背景调节
    def _apply(_e=None):
        sz = size_var.get(); bg = bg_var.get()
        for tw in refs["text_widgets"]:
            try: tw.config(font=("", sz), bg=bg)
            except Exception: pass
    size_cb.bind("<<ComboboxSelected>>", _apply)
    bg_cb.bind("<<ComboboxSelected>>", _apply)


# ═══════════════════════════════════════════════════════════
# 🎨 通用 Tab 构建器
# ═══════════════════════════════════════════════════════════

def _add_country_tab(nb, title, accent_color, content, refs):
    tab = tk.Frame(nb, bg="#FAFAFA")
    nb.add(tab, text=f"  {title}  ")

    card = tk.Frame(tab, bg=accent_color, highlightthickness=1, highlightbackground=accent_color)
    card.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    inner = tk.Frame(card, bg="#FAFAFA")
    inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    st = scrolledtext.ScrolledText(inner, wrap=tk.WORD, font=("", 9), bg="#FAFAFA", fg="#212121",
                                   bd=0, relief=tk.FLAT, padx=8, pady=6, spacing1=2, spacing3=4)
    st.pack(fill=tk.BOTH, expand=True)

    st.tag_configure("h1", font=("", 12, "bold"), foreground="#B71C1C", spacing1=10, spacing3=6)
    st.tag_configure("h2", font=("", 10, "bold"), foreground="#C62828", spacing1=6)
    st.tag_configure("year", font=("", 10, "bold"), foreground="#1565C0", spacing1=4)
    st.tag_configure("hot", foreground="#C62828", font=("", 9, "bold"))
    st.tag_configure("info", foreground="#2E7D32", font=("", 9, "bold"))
    st.tag_configure("warn", foreground="#E65100")
    st.tag_configure("link", foreground="#1565C0", font=("", 9, "underline"))
    st.tag_configure("quote", foreground="#616161", font=("", 9, "italic"))
    st.tag_configure("tbl", foreground="#4527A0", font=("", 9))
    st.tag_configure("bull", foreground="#2E7D32", font=("", 9, "bold"))
    st.tag_configure("bear", foreground="#C62828", font=("", 9, "bold"))

    for line in content.split("\n"):
        _tag = None
        if line.startswith("███"):
            _tag = "h1"
        elif line.startswith("## "):
            st.insert(tk.END, line[3:] + "\n", "h2"); continue
        elif line.startswith("📅 ") or line.startswith("📆 "):
            _tag = "year"
        elif line.startswith("🔥") or line.startswith("🚨") or line.startswith("⚠️"):
            _tag = "hot"
        elif line.startswith("💡") or line.startswith("✅") or line.startswith("📌"):
            _tag = "info"
        elif line.startswith("🔗") or line.startswith("http") or line.startswith("📚"):
            _tag = "link"
        elif line.startswith('"'):
            _tag = "quote"
        elif line.startswith("  ║") or line.startswith("  ╔") or line.startswith("  ╚") or line.startswith("  ╠"):
            _tag = "tbl"
        st.insert(tk.END, line + "\n", _tag)
    st.config(state=tk.DISABLED)
    refs["text_widgets"].append(st)
    return st


def _add_live_assets_tab(nb, title, accent_color, refs, win):
    """🆕 全球实时资产 Tab — 异步拉 akshare 数据 + 分析"""
    tab = tk.Frame(nb, bg="#FAFAFA")
    nb.add(tab, text=f"  {title}  ")

    card = tk.Frame(tab, bg=accent_color, highlightthickness=1, highlightbackground=accent_color)
    card.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    # 顶部操作栏
    top = tk.Frame(card, bg=accent_color)
    top.pack(fill=tk.X, padx=8, pady=(8, 4))
    tk.Label(top, text="📊 全球实时金融资产 · 对中国影响分析", font=("", 11, "bold"),
             bg=accent_color, fg="#BF360C").pack(side=tk.LEFT)
    refresh_btn = tk.Button(top, text="🔄 刷新数据", bg="#1565C0", fg="white",
                            font=("", 9, "bold"), relief=tk.FLAT, padx=12, pady=3)
    refresh_btn.pack(side=tk.RIGHT, padx=4)
    status_lbl = tk.Label(top, text="⏳ 点击刷新按钮拉取实时数据 (需联网)", bg=accent_color, fg="#555", font=("", 9))
    status_lbl.pack(side=tk.RIGHT, padx=10)

    # 主内容: 左表格 + 右分析
    main = tk.Frame(card, bg=accent_color)
    main.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    # --- 左: 全球资产实时表格 ---
    left = tk.Frame(main, bg="#FAFAFA")
    left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))

    # Treeview 表格
    cols = ("category", "name", "price", "change", "impact_cn")
    tree = ttk.Treeview(left, columns=cols, show="headings", height=16)
    tree.heading("category", text="类别")
    tree.heading("name", text="资产名称")
    tree.heading("price", text="最新价")
    tree.heading("change", text="涨跌幅")
    tree.heading("impact_cn", text="对A股影响")
    tree.column("category", width=70, anchor=tk.CENTER)
    tree.column("name", width=140, anchor=tk.W)
    tree.column("price", width=110, anchor=tk.E)
    tree.column("change", width=80, anchor=tk.E)
    tree.column("impact_cn", width=180, anchor=tk.W)

    vsb = ttk.Scrollbar(left, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)

    # 初始占位数据
    _placeholder_rows = [
        ("🖥️ 股票", "道琼斯工业", "—", "—", "美股涨→北向流入利好A股"),
        ("🖥️ 股票", "标普500", "—", "—", "同上, 关注科技权重"),
        ("🖥️ 股票", "纳斯达克", "—", "—", "科技涨→A股科技板块共振"),
        ("🖥️ 股票", "恒生指数", "—", "—", "港股→A股联动最直接"),
        ("🖥️ 股票", "日经225", "—", "—", "亚太风险偏好信号"),
        ("💵 货币", "美元指数 DXY", "—", "—", "美元强→新兴市场承压→A股利空"),
        ("💴 汇率", "USD/CNY 离岸", "—", "—", "汇率稳定>短期贬值, 关注7.3关口"),
        ("🏦 利率", "美国10Y国债", "—", "—", "美债收益率高→外资流出压力"),
        ("🏦 利率", "中国10Y国债", "—", "—", "下行→流动性宽松, 利好成长股"),
        ("💎 贵金属", "COMEX黄金", "—", "—", "黄金涨→避险升温, 对A股中性偏空"),
        ("🛢️ 能源", "布伦特原油", "—", "—", "油价涨→输入性通胀, 利空航空/化工成本"),
        ("🍞 大宗", "LME铜", "—", "—", "铜涨→经济预期好, 利好周期股"),
        ("₿ 加密", "BTC/USD", "—", "—", "加密涨→风险偏好高, 中小盘活跃"),
        ("💰 债市", "中债1Y期国债", "—", "—", "短债收益率→货币政策方向"),
    ]
    for r in _placeholder_rows:
        tree.insert("", tk.END, values=r, tags=("placeholder",))

    # 🔧 样式
    tree.tag_configure("bull", background="#E8F5E9")
    tree.tag_configure("bear", background="#FFEBEE")
    tree.tag_configure("placeholder", background="#FAFAFA", foreground="#999")
    tree.tag_configure("ok", background="#FFFFFF")

    # --- 右: 影响分析 ---
    right = tk.Frame(main, bg="#FAFAFA", width=420)
    right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)
    right.pack_propagate(False)

    analysis_title = tk.Label(right, text="🧠 对中国股市综合影响分析", font=("", 10, "bold"),
                              bg="#FAFAFA", fg="#1565C0")
    analysis_title.pack(anchor="w", padx=8, pady=(8, 2))

    analysis_st = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=("", 9), bg="#FAFAFA", fg="#212121",
                                            bd=0, relief=tk.FLAT, padx=8, pady=6, spacing1=2, spacing3=4)
    analysis_st.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    analysis_st.tag_configure("h2", font=("", 10, "bold"), foreground="#1565C0", spacing1=6)
    analysis_st.tag_configure("bull", foreground="#2E7D32", font=("", 9, "bold"))
    analysis_st.tag_configure("bear", foreground="#C62828", font=("", 9, "bold"))
    analysis_st.tag_configure("p", foreground="#424242")

    analysis_st.insert(tk.END, "📖 使用说明\n", "h2")
    analysis_st.insert(tk.END, "点击左侧 '🔄 刷新数据' 按钮, 系统会从 akshare 拉取全球实时资产数据, "
                              "然后基于价格/涨跌自动生成对A股的综合影响研判。\n\n", "p")
    analysis_st.insert(tk.END, "🔑 关键传导机制\n", "h2")
    analysis_st.insert(tk.END, "💵 美元指数 DXY", "bull")
    analysis_st.insert(tk.END, ": 走强→新兴市场资本外流→A股承压; 走弱→外资回流→利好\n", "p")
    analysis_st.insert(tk.END, "🏦 美债10年期收益率", "bull")
    analysis_st.insert(tk.END, ": 上行→中美利差收窄→外资流出; 下行→利差走阔→流入\n", "p")
    analysis_st.insert(tk.END, "🖥️ 美股 (纳指/道指)", "bull")
    analysis_st.insert(tk.END, ": 美股大涨→全球风险偏好↑→北向流入; 暴跌→风险偏好↓→抽血A股\n", "p")
    analysis_st.insert(tk.END, "💎 黄金", "bull")
    analysis_st.insert(tk.END, ": 大涨→避险情绪升温→短期利空A股风险资产\n", "p")
    analysis_st.insert(tk.END, "🛢️ 原油", "bull")
    analysis_st.insert(tk.END, ": 暴涨→输入性通胀→央行降息空间缩窄→利空; 暴跌→通缩担忧→也利空\n", "p")
    analysis_st.insert(tk.END, "₿ 加密货币", "bull")
    analysis_st.insert(tk.END, ": BTC大涨→风险偏好极强→中小盘活跃; 暴跌→避险→资金回流大盘蓝筹\n", "p")
    analysis_st.config(state=tk.DISABLED)
    refs["text_widgets"].append(analysis_st)

    # 刷新函数 (后台线程 + after 更新 UI)
    def _do_refresh():
        """后台线程拉数据"""
        import threading
        def worker():
            win.after(0, lambda: status_lbl.config(text="🔄 正在拉取全球数据...", fg="#1565C0"))
            try:
                rows = _fetch_global_assets()
                win.after(0, lambda: _update_tree_and_analysis(tree, analysis_st, rows, status_lbl))
            except Exception as e:
                import traceback
                traceback.print_exc()
                win.after(0, lambda: status_lbl.config(text=f"❌ 数据拉取失败: {e}", fg="#C62828"))
        threading.Thread(target=worker, daemon=True).start()

    refresh_btn.config(command=_do_refresh)


def _fetch_global_assets():
    """从 akshare 拉全球实时资产 — 返回 list of dict"""
    import akshare as ak
    results = []

    # 1. 全球指数
    try:
        df = ak.stock_us_daily(symbol="DJI", adjust="")  # 道琼斯
        last = df.iloc[-1]
        prev = df.iloc[-2]
        chg = (last["close"] - prev["close"]) / prev["close"] * 100
        results.append({"cat": "🖥️ 股票", "name": "道琼斯工业", "price": f"{last['close']:.2f}",
                        "chg": f"{chg:+.2f}%", "impact": "美股→北向资金→A股共振", "chg_val": chg})
    except Exception: pass

    try:
        df = ak.stock_us_daily(symbol=".IXIC", adjust="")  # 纳斯达克
        last = df.iloc[-1]; prev = df.iloc[-2]
        chg = (last["close"] - prev["close"]) / prev["close"] * 100
        results.append({"cat": "🖥️ 股票", "name": "纳斯达克", "price": f"{last['close']:.2f}",
                        "chg": f"{chg:+.2f}%", "impact": "科技股涨跌→A股科技联动", "chg_val": chg})
    except Exception: pass

    try:
        df = ak.stock_us_daily(symbol=".INX", adjust="")  # 标普500
        last = df.iloc[-1]; prev = df.iloc[-2]
        chg = (last["close"] - prev["close"]) / prev["close"] * 100
        results.append({"cat": "🖥️ 股票", "name": "标普500", "price": f"{last['close']:.2f}",
                        "chg": f"{chg:+.2f}%", "impact": "全球风险偏好基准", "chg_val": chg})
    except Exception: pass

    # 2. 恒生指数
    try:
        df = ak.stock_hk_index_daily_sina(symbol="HSI")
        last = df.iloc[-1]; prev = df.iloc[-2]
        chg = (float(last["close"]) - float(prev["close"])) / float(prev["close"]) * 100
        results.append({"cat": "🖥️ 股票", "name": "恒生指数", "price": f"{float(last['close']):.2f}",
                        "chg": f"{chg:+.2f}%", "impact": "港股→A股最直接联动", "chg_val": chg})
    except Exception: pass

    # 3. 美元指数
    try:
        df = ak.index_us_stock_sina(symbol=".DXY")
        last = df.iloc[-1]; prev = df.iloc[-2]
        chg = (float(last["close"]) - float(prev["close"])) / float(prev["close"]) * 100
        results.append({"cat": "💵 货币", "name": "美元指数 DXY", "price": f"{float(last['close']):.2f}",
                        "chg": f"{chg:+.2f}%", "impact": "强→新兴市场承压→A股利空", "chg_val": chg})
    except Exception: pass

    # 4. 黄金
    try:
        df = ak.futures_foreign_hist(symbol="XAU")
        last = df.iloc[-1]; prev = df.iloc[-2]
        chg = (float(last["close"]) - float(prev["close"])) / float(prev["close"]) * 100
        results.append({"cat": "💎 贵金属", "name": "COMEX黄金", "price": f"{float(last['close']):.2f}",
                        "chg": f"{chg:+.2f}%", "impact": "大涨→避险升温→中性偏空", "chg_val": chg})
    except Exception: pass

    # 5. 原油
    try:
        df = ak.futures_foreign_hist(symbol="CL")
        last = df.iloc[-1]; prev = df.iloc[-2]
        chg = (float(last["close"]) - float(prev["close"])) / float(prev["close"]) * 100
        results.append({"cat": "🛢️ 能源", "name": "WTI原油", "price": f"{float(last['close']):.2f}",
                        "chg": f"{chg:+.2f}%", "impact": "暴涨→输入性通胀→利空", "chg_val": chg})
    except Exception: pass

    # 6. BTC
    try:
        df = ak.crypto_hist(symbol="BTC", period="daily", start_date="20261101")
        last = df.iloc[-1]; prev = df.iloc[-2]
        chg = (float(last["close"]) - float(prev["close"])) / float(prev["close"]) * 100
        results.append({"cat": "₿ 加密", "name": "BTC/USD", "price": f"{float(last['close']):.0f}",
                        "chg": f"{chg:+.2f}%", "impact": "大涨→风险偏好↑→中小盘活跃", "chg_val": chg})
    except Exception: pass

    # 7. USD/CNY
    try:
        df = ak.currency_boc_safe()
        # 找美元兑人民币
        for _, row in df.iterrows():
            if "美元" in str(row.get("货币名称", "")) or "USD" in str(row.get("货币名称", "")).upper():
                mid = float(row.get("中行折算价", row.get("中间价", 0)))
                results.append({"cat": "💴 汇率", "name": "USD/CNY 中间价", "price": f"{mid:.4f}",
                                "chg": "—", "impact": "稳定>贬值, 关注7.3心理关口", "chg_val": 0})
                break
    except Exception: pass

    return results


def _update_tree_and_analysis(tree, analysis_st, rows, status_lbl):
    """刷新 Treeview + 生成 AI 式分析"""
    # 清空旧数据
    for item in tree.get_children():
        tree.delete(item)

    bull_count = 0; bear_count = 0
    for r in rows:
        tag = "ok"
        try:
            v = r["chg_val"]
            if v > 0.5: tag = "bull"; bull_count += 1
            elif v < -0.5: tag = "bear"; bear_count += 1
        except Exception: pass
        tree.insert("", tk.END,
                    values=(r["cat"], r["name"], r["price"], r["chg"], r["impact"]),
                    tags=(tag,))

    # 生成分析
    analysis_st.config(state=tk.NORMAL)
    analysis_st.delete("1.0", tk.END)

    analysis_st.insert(tk.END, "📊 全球资产实时快照 & A股影响研判\n", "h2")
    analysis_st.insert(tk.END, f"  数据点: {len(rows)} | 偏多资产: {bull_count} | 偏空资产: {bear_count}\n\n", "p")

    # 关键资产判断
    us_trend = "中性"
    dxy_trend = "中性"
    gold_trend = "中性"
    for r in rows:
        n = r["name"]
        if "道琼斯" in n or "纳斯达克" in n:
            if r["chg_val"] > 0.3: us_trend = "上涨📈 (利好A股风险偏好)"
            elif r["chg_val"] < -0.3: us_trend = "下跌📉 (利空A股风险偏好)"
        if "美元指数" in n:
            if r["chg_val"] > 0.3: dxy_trend = "走强 (新兴市场承压→A股利空)"
            elif r["chg_val"] < -0.3: dxy_trend = "走弱 (外资回流→A股利好)"
        if "黄金" in n:
            if r["chg_val"] > 1: gold_trend = "大涨 (避险升温)"
            elif r["chg_val"] < -1: gold_trend = "回落 (风险偏好回升)"

    analysis_st.insert(tk.END, "🔑 核心变量解读\n", "h2")
    analysis_st.insert(tk.END, f"  🖥️ 美股: {us_trend}\n",
                       "bull" if "利好" in us_trend or "上涨" in us_trend else "bear" if "利空" in us_trend else "p")
    analysis_st.insert(tk.END, f"  💵 DXY: {dxy_trend}\n",
                       "bear" if "利空" in dxy_trend else "bull" if "利好" in dxy_trend else "p")
    analysis_st.insert(tk.END, f"  💎 黄金: {gold_trend}\n\n",
                       "bear" if "避险" in gold_trend else "bull" if "回升" in gold_trend else "p")

    # 综合研判
    analysis_st.insert(tk.END, "🎯 综合研判\n", "h2")
    net = bull_count - bear_count
    if net >= 3:
        analysis_st.insert(tk.END, "  🌍 全球风险偏好偏强, 外资大概率回流A股, 中小盘和科技板块有望活跃\n", "bull")
    elif net <= -3:
        analysis_st.insert(tk.END, "  🌪️ 全球避险情绪升温, 外资流出压力大, 建议防守大盘蓝筹和黄金板块\n", "bear")
    else:
        analysis_st.insert(tk.END, "  ⚖️ 全球信号分化, A股将延续结构性行情, 关注政策面和北向资金实时动向\n", "p")

    analysis_st.insert(tk.END, "\n⚠️ 以上为量化模型自动生成的参考研判, 不构成投资建议\n", "p")
    analysis_st.config(state=tk.DISABLED)

    status_lbl.config(text=f"✅ 已更新 {len(rows)} 个资产 · {bull_count}涨 {bear_count}跌", fg="#2E7D32")


# ═══════════════════════════════════════════════════════════
# 📜 历史文本数据
# ═══════════════════════════════════════════════════════════

JP_TEXT = """███ 🇯🇵 日本泡沫·少子化 — 从泡沫破裂到无缘社会

📌 泡沫破裂35年, 日本发明了这些词: 就业冰河期·婚活·无缘社会·低欲望社会·8050·蛰居族·食草男·干物女

## 背景: 1990 泡沫经济破裂

  • 日经指数: 1989年末 38915点 → 1992年 14309点 (跌63%)
  • 地价: 长期阴跌, 日本经济30年未能回到泡沫前增长轨道
  • 企业: 冻结招聘、削减正职

## 完整因果链 (1990-2025)

📅 1990 · 泡沫破裂 "失去的十年" 开始
📅 1992 · 就业冰河期 — 大学生招聘骤减, 1993届起陷入长期冰河
📅 1995 · TFR总和生育率1.42 — 此后30年再未回到1.5
📅 1998 · NEET尼特族 — 不上学/不工作/不培训的青年成议题
📅 2002 · 蛰居族"百万人"震惊社会 — 大多依赖高龄父母生活 → 为日后"8050问题"埋伏笔
📅 2002 · 格差社会 — 菅直人出版《格差社会》批判雇佣两极化
📅 2005 · 人口自然减少开始 — 死亡首次超过出生
📅 2005 · 下流社会 — 三浦展: 中产整体下沉, 收入/消费/欲望同步降级
📅 2006 · 食草男 — 不主动恋爱/消费节俭/安于现状
📅 2007 · 婚活 — "像找工作一样结婚", 相亲全面产业化
📅 2010 · 无缘社会 — NHK: 无地缘/血缘/社缘的孤立生存
📅 2014 · 地方消灭 · 增田报告 — 896个市町村面临"消灭可能性"
📅 2014 · 低欲望社会 — 大前研一: 年轻人不买房/不买车/不消费
📅 2019 · 8050问题 — 80岁父母供养50岁蛰居子女
📅 2024 · 出生数首次跌破70万 — 68.6万人, 比政府预测提前15年
📅 2025 · TFR再创新低 1.14 — 自然减少91.8万

## 对中国的启示

💡 日本是少子化先行者, 其经历极有可能在中国重演, 且形势或许更为严峻
💡 35年因果链: 泡沫破裂 → 就业冰河 → 非正规雇用 → 收入差距 → 欲望降级 → 婚恋退出 → 少子化 → 无缘社会
💡 中国当前需警惕: 地产下行期 → 青年失业 → 婚育意愿下降 → 地方财政危机
"""

US_TEXT = """███ 🇺🇸 美国金融危机全景

## 关键危机事件

📅 1907 · 银行家危机 → 直接催生 1913年美联储
📅 1929 · 大萧条 Great Depression — 道琼斯跌89%, 银行倒闭9000+, 失业率25% → 罗斯福新政·FDIC·SEC
📅 1970s · 滞胀 — 石油危机 + 美元与黄金脱钩(1971尼克松冲击) → 沃尔克时代: 联邦基金利率提至20%
📅 1987 · 黑色星期一 — 道琼斯单日跌22.6%(史上最大) → 引入熔断机制
📅 2000 · 互联网泡沫破裂 — NASDAQ从5048跌至1108(跌78%)
📅 2008 · 次贷危机 — 雷曼兄弟破产(6390亿美, 史上最大) → Dodd-Frank法案 + QE
📅 2020 · 新冠冲击 — 4周史上最快暴跌(-35%) → 零利率+无限QE(扩表8万亿)
📅 2023 · 银行危机 — SVB(2090亿)+签名银行+第一共和接连倒闭

## 周期规律

💡 美国平均每8-12年一次中等以上危机
💡 每次危机后催生新监管, 但随后又在放松周期中积累新风险
💡 "格林斯潘对策"(救助金融机构) → 道德风险 → 更大的泡沫
💡 2026年当前风险: 商业地产贷款到期潮 + 利率高位 + 政府债务36万亿 + 美债34万亿
"""

WORLD_TEXT = """███ 🗺️ 世界金融危机全景

## 全球化下的主要危机

📅 1997 · 亚洲金融风暴 — 泰铢暴跌, 索罗斯狙击, 韩国/印尼崩盘
📅 1998 · 俄罗斯违约 + LTCM危机 — 卢布贬值70%, LTCM亏46亿
📅 2012 · 欧债危机 — 希腊违约, ECB德拉吉"不惜一切代价"救市
📅 2015 · 人民币汇改冲击 + 中国股灾 — A股从5178跌至2638(跌49%)
📅 2020 · 新冠全球冲击 — 3月全球同步熔断, 原油首次负价格
📅 2022 · 俄乌战争 + 能源危机 — 布伦特冲到133美, 欧洲天然气涨10倍
📅 2023-2026 · 高利率去杠杆 — 全球债务313万亿美(313% GDP), 加密(FTX)→银行(SVB)→商业地产

## 三次百年一遇对比

  ╔══════════╦════════════╦════════════╦══════════════════╗
  ║          ║ 1929大萧条 ║ 2008次贷   ║ 2026?当前阶段     ║
  ╠══════════╬════════════╬════════════╬══════════════════╣
  ║ 触发因素 ║ 股市泡沫   ║ 地产泡沫   ║ 债务+地产+科技?   ║
  ║ 政策响应 ║ 自由放任   ║ QE+救市    ║ 高利率僵持中      ║
  ║ 全球影响 ║ 10年衰退   ║ 7年低增长  ║ 去杠杆进行中      ║
  ║ 未解风险 ║ 二战才解决 ║ 通胀+债务  ║ 债务+地产+地缘    ║
  ╚══════════╩════════════╩════════════╩══════════════════╝

💡 每次危机都不同, 但核心都是 "杠杆 + 过度乐观 + 监管缺位" 的组合
"""

EU_TEXT = """███ 🇪🇺 欧洲金融危机全景

📅 1990s · 北欧银行危机 — 芬兰GDP萎缩14%, 瑞典被迫克朗贬值
📅 2010-2012 · 欧债危机 — 希腊违约, 国债10年期收益率飙升到48%
  → ESM稳定机制1.5万亿欧 + ECB德拉吉"不惜一切代价保卫欧元"
  → 希腊经济萎缩25%, 失业率27%
📅 2022 · 欧洲能源危机 — 俄断天然气, 产业大量外迁
📅 2023 · 瑞士信贷暴雷 — 167年历史投行, 被瑞银30亿瑞郎收购

💡 欧元区固有缺陷: 统一货币 + 分散财政 (没有统一财政部)
💡 德国"节俭文化" vs 南欧"福利文化" — 结构性矛盾
💡 2026风险: 意大利债务/GDP 140%, 若降息预期落空, 债务可持续性存疑
"""

SA_TEXT = """███ 🌎 南美 · 非洲金融危机

## 拉美 (反复上演的"繁荣-萧条"周期)

📅 1980s · 拉美债务危机 Lost Decade — 几乎全部拉美国家违约, GDP萎缩30%
📅 1994 · 墨西哥龙舌兰危机 — 比索贬15%, 克林顿500亿救助
📅 2001-2002 · 阿根廷违约 — 史上最大主权违约, 950亿美, 债权人放弃70%
📅 2018 · 土耳其汇率危机 — 里拉年内贬40%, 外债5000亿
📅 2024-2026 · 委内瑞拉/阿根廷持续危机 — 委内瑞拉通胀3位数连续8年

## 非洲

📅 2020-2026 · 非洲债务违约潮 — 加纳/赞比亚/斯里兰卡/黎巴嫩/埃塞俄比亚相继违约
  → "一带一路"债务 vs IMF条件性救助的地缘博弈

💡 拉美的 "繁荣-萧条" 周期平均8年: 外资流入→资产泡沫→美元加息→资本外逃→违约/贬值
💡 新兴市场风险本质: 本币计价债务少, 外币计价债务多 → 汇率一贬, 债务自动膨胀
💡 2026年: 30多个新兴市场面临债务到期 + 高利率环境
"""


# ═══════════════════════════════════════════════════════════
# 🆕 第二组: 深层结构性问题
# ═══════════════════════════════════════════════════════════

STRUCTURAL_TEXT = """███ 🏗️ 全球金融体系五大结构性问题

## 1️⃣ 债务爆炸 — 人类历史上最大的杠杆

  • 全球总债务: 313万亿美元 (IMF 2025)
  • 债务/GDP: 313% — 是1929年的3倍, 2008年的1.5倍
  • 美国: 联邦债务36万亿 + 私人债务48万亿 = 84万亿, 占全球27%
  • 中国: 宏观杠杆率280%, 企业债务160% (全球最高)
  • 日本: 政府债务/GDP 264% (全球最高)

  💡 明斯基时刻: 稳定本身孕育不稳定 — 低利率时期鼓励加杠杆, 最终无法偿付

## 2️⃣ 美元霸权的特里芬困境

  • 美元占全球储备货币62%, 国际结算42%, SWIFT交易45%
  • 特里芬困境: 世界需要美元流动性 → 美国必然贸易逆差 → 美元信用长期走弱
  • 1971尼克松冲击结束金本位后, 美元靠"石油美元"和"军事威慑"维持
  • 现在挑战: 人民币国际化 + 加密货币 + 多极化储备

## 3️⃣ 贫富分化 — 现代版"朱门酒肉臭"

  • 全球最富1%拥有的财富 > 最穷50%的总和 (Oxfam 2025)
  • 美国前0.1%的财富 = 后90%的总和
  • 中国基尼系数0.47 (2025), 超过0.4警戒线
  • 日本相对贫困率15.7% (OECD 2024), "一亿总中流"解体

  💡 贫富分化 → 消费不足 → 经济增长乏力 → 民粹主义崛起 → 政策摇摆 → 金融不稳定

## 4️⃣ 人口结构崩塌 — 全球老龄化+少子化

  • 全球65岁以上: 2025年10%, 2050年16%
  • 总和生育率: 全球2.3, 但发达国家已集体低于2.1更替水平
  • 日本1.14, 韩国0.78, 中国1.09, 德国1.58
  • 劳动人口减少 → 储蓄率下降 → 利率中枢下移 → 资产泡沫化
  • 养老金/医疗财政压力 → 政府债务膨胀 → 金融危机的隐性导火索

## 5️⃣ 金融化过度 — 实体经济被抽血

  • 美国: 金融+房地产利润占总企业利润40% (1950年是15%)
  • 中国: 金融业增加值占GDP 8.7%, 超过所有发达国家
  • 金融业的本质是服务实体经济, 但现在变成"资金空转"自我循环
  • 2008年次贷危机本质: 金融创新脱离实体经济, 自己制造了一个巨大的赌场

## 五大问题的共振效应

  ╔══════════════════════════════════════════════════════════════╗
  ║  债务爆炸 ──→ 利率敏感 ──→ 加息周期 ──→ 泡沫破裂            ║
  ║     ↑                                                        ║
  ║  金融化过度 ←── 贫富分化 ←── 人口崩塌 ←── 经济减速          ║
  ║     │                                                        ║
  ║  美元霸权 ←──────────────────────────────────────┘          ║
  ╚══════════════════════════════════════════════════════════════╝

💡 2026年我们处于五大问题的共振区间 — 任何一个导火索都可能引爆
💡 最危险的组合: 美国商业地产到期潮 + 中国地产出清 + 欧洲能源余波 + 新兴市场债务违约
"""


FINANCIAL_WAR_TEXT = """███ ⚔️ 美国金融战全景 — 从美元霸权到SWIFT制裁

## 金融战六大武器

  🔫 武器1: SWIFT制裁 — 切断国际结算通道
     • 2014年对俄罗斯制裁, 俄银行被迫转用人民币+欧元
     • 2022年全面踢出俄主要银行, 加速去SWIFT化
     • 威胁对中国: 若发生, 约3万亿美外汇储备无法清算

  🔫 武器2: 美元武器化 — 利用储备货币地位卡脖子
     • 冻结俄罗斯央行3000亿美外汇储备 (2022) — 史无前例
     • 伊朗央行资产被冻结超1000亿美
     • 委内瑞拉黄金被强占 (存放在英国央行)
     • 💡 核心震慑: 让所有国家意识到"存美元不安全"

  🔫 武器3: 美联储货币政策溢出 — 剪全球羊毛
     • 加息: 美元走强→新兴市场资本外逃→被迫加息→经济衰退
     • 降息: 美元走弱→热钱涌入→资产泡沫→加息时再刺破
     • "格林斯潘对策" + "鲍威尔冲击" — 每轮周期都有新兴市场倒下
     • 1994墨西哥/1997亚洲/2015巴西/2022全球

  🔫 武器4: 长臂管辖 — 用美国法律治外国公司
     • 法国阿尔斯通: 7.72亿美罚款, 核心部门被美国通用收购
     • 中兴通讯: 12亿美罚款 + 7年禁运
     • 华为: 实体清单, 禁止使用美国芯片/软件
     • 汇丰银行: 协助制裁伊朗, 差点被罚
     • 💡 本质: 用法律名义打经济战

  🔫 武器5: 评级机构话语权 — 标普/穆迪/惠誉
     • 下调评级 → 融资成本飙升 → 债券违约 → 恐慌蔓延
     • 2011年下调美国评级 (史上第一次), 全球震荡
     • 2024年下调中国主权评级展望, 影响外资信心
     • 💡 三大评级机构都是美国公司

  🔫 武器6: 金融市场威慑 — 做空+舆论+程序化
     • 索罗斯狙击英镑(1992) → 赚10亿美, 迫使英国退出欧洲货币体系
     • 对冲基金联合做空新兴市场货币
     • 舆论战: 华尔街日报/彭博/路透配合做空

## 反制力量

  🇨🇳 人民币国际化
    • 跨境人民币支付: 2025年占比48% (首次超过美元)
    • CIPS (人民币跨境支付系统): 覆盖180+国家/地区
    • 中俄本币结算: 100%人民币
    • 但: 资本账户未完全开放, 国际化受限

  🇷🇺 俄罗斯"去美元化"
    • 2022年后 90%能源出口用人民币/欧元
    • 建立SPFS替代SWIFT (覆盖20+国)
    • 央行外汇储备完全清空美元 (2025)

  🇪🇺 欧元挑战
    • 欧元占全球储备20%, 结算38%
    • 但: 无统一财政部, 欧债危机暴露制度缺陷

  🌐 加密货币
    • BTC被视为"数字黄金", 抗制裁
    • 但: 波动大, 监管不明确, 难以成为储备货币

  💡 核心判断: 美元霸权短期难以替代, 但已进入"相对衰落期"
  💡 金融战烈度会持续升级, 中国是主要目标

## 对中国的直接威胁

  🚨 SWIFT制裁: 最坏情况, 外贸结算中断, 约3万亿外汇储备无法使用
  🚨 芯片禁令: 高端芯片无法获取, 先进制造业卡死
  🚨 评级下调: 外资持续流出, 人民币汇率承压
  🚨 做空冲击: 对冲基金联合做空港股+人民币
  💡 中国反制: CIPS+数字人民币+去美化+内循环+关键技术自主
"""


WORLD_ORDER_TEXT = """███ 🌍 世界格局演变 — 从单极到多极的阵痛

## 历史演变

📅 1500-1914 · 欧洲中心主义
  葡萄牙/西班牙/荷兰/英国殖民扩张, 金融+军事双重统治

📅 1914-1945 · 两次世界大战+过渡期
  英国衰落, 美苏崛起, 布雷顿森林体系(1944)奠定美元霸权

📅 1945-1991 · 美苏两极冷战
  北约 vs 华约, 代理人战争, 核威慑下的和平

📅 1991-2008 · 美国单极时刻
  苏联解体, "历史的终结"(福山), 全球化高歌猛进
  美元独霸, WTO/IMF/世界银行美国主导

📅 2008-2020 · 危机后的多极萌芽
  次贷危机削弱美国, 中国崛起, 金砖国家, G20变重要
  但体系还是美国的, 只是话语权开始分散

📅 2020-2026 · 多极阵痛期
  新冠加速脱钩, 俄乌战争撕裂欧洲, 中美科技战, 全球进入"去全球化"
  💡 核心特征: 没有新秩序, 只有权力真空和混乱

## 2026年当前格局

  ╔══════════╦══════════════════════════════════════════╗
  ║ 力量中心 ║ 优势                                     ║
  ╠══════════╬══════════════════════════════════════════╣
  ║ 🇺🇸 美国 ║ 美元霸权·军事威慑·科技顶尖·SWIFT控制       ║
  ║ 🇨🇳 中国 ║ 制造第一·市场超大·基建能力·科技追赶·RCEP   ║
  ║ 🇪🇺 欧洲 ║ 欧元·工业基础·福利制度·但分裂·能源依赖     ║
  ║ 🇷🇺 俄国 ║ 能源+军工·战略纵深·但经济规模小·制裁中     ║
  ║ 🌏 印度 ║ 人口红利·IT服务业·但基建弱·种姓问题         ║
  ║ 🇯🇵 日本 ║ 科技+制造·但少子化·老龄化·安全依赖美国     ║
  ╚══════════╩══════════════════════════════════════════╝

## 三条主线

  1️⃣ 中美博弈 — 决定21世纪格局的核心变量
     • 科技战: 芯片/AI/量子计算 — 谁掌握未来技术
     • 金融战: 美元霸权 vs 人民币国际化
     • 地缘战: 台海/南海/朝鲜半岛
     • 贸易战: 关税+产业链转移+脱钩

  2️⃣ 去全球化 vs 区域化
     • 北美: USMCA
     • 亚洲: RCEP (全球最大自贸区)
     • 欧洲: 欧盟
     • 非洲: 非洲大陆自贸区
     • 💡 全球统一市场 → 区域化小圈子

  3️⃣ 能源转型 + 气候政治
     • 化石能源: 煤炭/石油/天然气还是全球80%
     • 新能源: 光伏/风电/储能快速增长, 中国产能全球80%
     • 气候政治: 发达国家想甩锅, 发展中国家要发展

💡 2026年最可能的未来: 不是单极也不是和谐多极, 而是"混乱多极"
💡 乱中机会: 区域化=本土化机会; 能源转型=新赛道; 人口结构=银发经济
"""


GREAT_DEPRESSION_TEXT = """███ 📉 1929大萧条 — 影响链 · 当今对照

## 大萧条影响链 (完整传导路径)

📅 1929.10.24 · 黑色星期四 — 道琼斯单日跌11%
  📌 触发: 股市杠杆10倍, 全民投机, 市场过热

📅 1929.10-1930 · 银行倒闭潮
  • 9000+银行倒闭, 储户损失1400亿美 (占GDP 15%)
  • 货币供应量下降30% — 通缩螺旋开始
  📌 传导: 股市→银行→货币→经济

📅 1930-1933 · 实体经济崩溃
  • GDP萎缩30% (史上最大)
  • 失业率飙升到25% (1/4劳动力失业)
  • 工业生产下降47%
  • 全球贸易暴跌67%
  📌 传导: 银行→企业→就业→消费→贸易

📅 1930-1933 · 通缩螺旋 (最致命的部分)
  • 物价每年降10%+ → 实际债务负担加重
  • 企业降价求生 → 利润为零 → 裁员更多
  • 消费者持币观望 → 需求进一步萎缩
  📌 核心: 通缩比通胀更难救 — 利率降到零也没用

📅 1930-1935 · 全球蔓延
  • 欧洲: 德国失业30%, 助长法西斯上台
  • 日本: "昭和恐慌", 军部掌权
  • 拉美: 几乎全部违约
  📌 传导: 美国→欧洲→亚洲→全球

📅 1933 · 罗斯福新政 (New Deal)
  • FDIC存款保险 — 结束银行挤兑
  • WPA公共工程 — 创造就业
  • 放弃金本位 — 货币贬值刺激出口
  • 监管华尔街 — SEC成立
  📌 30年代中期开始复苏, 但真正走出要到二战

📅 1939-1945 · 二战 — 终结大萧条
  • 战争支出创造需求, 彻底结束通缩
  • 美国GDP在战争中翻倍, 失业率降到2%
  📌 残酷的结论: 大规模基建+战争才能真正出清

## 2026年对照: 相似点 & 不同点

  ╔══════════════╦══════════════════════╦═══════════════════════════╗
  ║              ║ 1929大萧条           ║ 2026当前                   ║
  ╠══════════════╬══════════════════════╬═══════════════════════════╣
  ║ 杠杆水平     ║ 股市10倍杠杆         ║ 全球313% GDP杠杆 (更夸张) ║
  ║ 银行健康     ║ 无存款保险, 9000倒闭 ║ 有FDIC, 但影子银行大      ║
  ║ 货币政策     ║ 自由放任(犯大错)     ║ QE+零利率(但已无子弹)     ║
  ║ 通缩/通胀    ║ 严重通缩             ║ 高利率下的通胀+地产通缩   ║
  ║ 失业率       ║ 25%                  ║ 美国4.1%, 中国青年15%     ║
  ║ 全球贸易     ║ 关税战+暴跌67%       ║ 去全球化+科技战           ║
  ║ 人口结构     ║ 年轻人口多, 有红利   ║ 老龄化+少子化 (最大不同)  ║
  ║ 地缘政治     ║ 走向战争             ║ 俄乌+台海+多极 (火药桶)   ║
  ╚══════════════╩══════════════════════╩═══════════════════════════╝

## 可借鉴的教训

💡 教训1: 银行挤兑必须立即制止 — 存款保险+无限制流动性
💡 教训2: 通缩比通胀可怕 — 不能让物价持续下跌
💡 教训3: 财政刺激必须足够大 — 小打小闹没用
💡 教训4: 贸易战是自杀 — 全球化倒退两败俱伤
💡 教训5: 金融监管不能放松 — 放松→泡沫→危机
💡 教训6: 和平出清比战争出清好 — 但和平出清更慢更痛

💡 最关键的不同: 1929年是"年轻人的危机", 2026年是"老年人的危机" — 老龄化意味着财政压力更大, 复苏更慢
"""


CHINA_IMPACT_TEXT = """███ 🇨🇳 历次危机对中国的影响 · 反思 · 预判

## 历次危机对中国的冲击

📅 1997亚洲金融风暴
  • 影响: 出口暴跌, 周边国家货币贬值对中国形成压力
  • 应对: 人民币不贬值(顶住压力), 国企改革(下岗潮), 启动内需
  • 结果: 挺住了, 1998-2001通缩期后迎来WTO黄金十年
  • 💡 启示: 汇率稳定是定海神针

📅 2008次贷危机
  • 影响: 外需崩塌, 出口暴跌30%, 2000万农民工失业
  • 应对: 4万亿刺激计划 + 十大产业振兴
  • 结果: 成功保增长, 但留下后遗症 — 地方债+地产泡沫
  • 💡 反思: 刺激短期有效, 但结构问题延后爆炸

📅 2015股灾+汇改
  • 影响: A股从5178跌至2638(跌49%), 央行救市花1.5万亿
  • 应对: 证金公司直接入市, 国家队救市
  • 结果: 救住了, 但高杠杆股市从此被压制
  • 💡 反思: 政策市的天花板

📅 2022美联储加息
  • 影响: 人民币汇率从6.3贬到7.2, 外资净流出超5000亿
  • 应对: 外汇储备干预+资本管制+稳增长
  • 💡 启示: 中美利差是核心变量

📅 2024-2026 地产下行+城投债
  • 影响: 地产销售跌50%, 地方财政压力创纪录, 城投债风险显性化
  • 应对: "三大工程"(保交付+城中村+保障性住房)+地方化债
  • 💡 反思: 地产-财政-银行的三角风险终于被戳中

## 深层反思

  ⚠️ 反思1: 4万亿刺激的后遗症
     • 地方政府学会了"土地财政" → 依赖卖地 → 地产泡沫 → 现在出清
     • 国企扩产能 → 产能过剩 → 僵尸企业 → 金融资源错配
     • 教训: 刺激可以用, 但必须伴随结构改革

  ⚠️ 反思2: 金融自由化 vs 稳定
     • 2014-2015伞形基金→场外配资→股灾
     • 2016-2018 P2P暴雷潮(上千家, 几万亿)
     • 教训: 金融创新必须在监管框架内

  ⚠️ 反思3: 汇率改革的时机
     • 2015年8月11日汇改 — 时机选择不当, 放大了股灾冲击
     • 教训: 汇率改革需要选择合适的外部环境

  ⚠️ 反思4: 房地产的定位
     • 地产是"经济支柱"还是"民生产品"?
     • 过去20年靠地产拉动增长, 现在转型阵痛
     • 教训: 支柱产业单一化是最大风险

## 2026-2027 预判

  🎯 情景1: 软着陆 (概率55%)
     • 地产缓慢出清, 政策稳增长, 外部无大危机
     • A股震荡上行, 结构性行情为主
     • 关键观察: 地产销售何时企稳? 地方化债进展?

  🎯 情景2: 硬着陆 (概率25%)
     • 地产+城投+中小银行风险集中爆发
     • 人民币快速贬值, 资本外流加速
     • A股跌破2500点, 政策强力救市
     • 触发条件: 美国再加息+台海紧张+地产出清超预期

  🎯 情景3: 全球危机传导 (概率20%)
     • 美国商业地产暴雷 → 全球金融震荡 → A股跟跌
     • 但中国有独立货币政策空间, 跌幅会小于欧美
     • 机会: 危机后外资会重新配置中国核心资产

## 个人投资者操作建议

  💡 核心原则: 先保值再增值, 先防守再进攻
  💡 资产配置: 30%货币基金(流动性)+ 30%中短债(稳健)+ 20%宽基指数(进攻)+ 10%黄金(对冲)+ 10%另类
  💡 行业选择: 避开地产+城投相关, 关注消费复苏+科技自主+银发经济+能源安全
  💡 风险控制: 不加杠杆, 不满仓, 留足3年生活费的现金
  💡 心态: 危机永远有, 但每次危机都是买入好公司的机会

⚠️ 免责声明: 以上为历史复盘+情景分析, 不构成投资建议。投资有风险, 入市需谨慎。
"""


BOOK_TEXT = """███ 📚 金融危机必读书籍

## 总览类 (推荐先读)

📚 《这次不一样》(This Time Is Different)
  • 作者: 卡门·莱因哈特 / 肯尼斯·罗格夫
  • 800年历史的金融危机大全, 揭示每次危机"这次不一样"的幻象
  • 豆瓣: 9.1分 | 必读指数: ⭐⭐⭐⭐⭐

📚 《金融危机简史》(The Ascent of Money)
  • 作者: 尼尔·弗格森 (Niall Ferguson)
  • 金融如何塑造世界历史: 从债券市场到殖民帝国
  • 豆瓣: 8.5分 | 必读指数: ⭐⭐⭐⭐

## 大萧条

📚 《大萧条》(The Great Crash 1929) · 加尔布雷思 | 最经典的1929复盘 | ⭐⭐⭐⭐

## 日本失落三十年

📚 《低欲望社会》· 大前研一 | ⭐⭐⭐⭐
📚 《无缘社会》· NHK纪实 | ⭐⭐⭐⭐⭐ (社会警示录)
📚 《下流社会》· 三浦展 | ⭐⭐⭐⭐

## 2008次贷危机

📚 《危机直击》(The Big Short) · 迈克尔·刘易斯 | 最通俗的次贷入门 | ⭐⭐⭐⭐⭐
📚 《这次危机不一样》(Too Big to Fail) · 安德鲁·索尔金 | 雷曼破产72小时 | ⭐⭐⭐⭐

## 欧元区 / 新兴市场

📚 《欧元危机》· 保罗·德·格劳威 | 欧元区固有缺陷 | ⭐⭐⭐
📚 《为什么国家会失败》· 达龙·阿西莫格鲁 | 制度决定命运 | ⭐⭐⭐⭐

## 经典理论

📚 《稳定不稳定的经济》· 海曼·明斯基 | 稳定本身孕育不稳定 | ⭐⭐⭐⭐⭐
📚 《黑天鹅》· 纳西姆·塔勒布 | 极端事件颠覆认知 | ⭐⭐⭐⭐
📚 《反脆弱》· 塔勒布 | 从混乱中获益 | ⭐⭐⭐⭐⭐

## 美元霸权 / 金融战

📚 《霸权背后》· 威廉·恩道尔 | 美元霸权+石油美元 | ⭐⭐⭐⭐
📚 《金融战争》· 张宏良 | 美国金融战手法 | ⭐⭐⭐

## 中国视角

📚 《激荡三十年》· 吴晓波 | 中国改革开放金融史 | ⭐⭐⭐⭐
📚 《中国崛起的经济学》· 林毅夫 | 新结构经济学 | ⭐⭐⭐⭐
"""


LINK_TEXT = """███ 🔗 金融危机网络资源

## 学术/研究机构

🔗 美国国家经济研究局 NBER (金融危机数据库)
  https://www.nber.org/

🔗 国际货币基金组织 IMF (全球债务统计)
  https://www.imf.org/zh/Home

🔗 世界银行 World Bank (新兴市场债务监测)
  https://blogs.worldbank.org/zh-hans

🔗 美联储经济数据库 FRED (最权威宏观数据)
  https://fred.stlouisfed.org/

## 实时数据

🔗 全球债务时钟 Global Debt Clock (实时债务总量)
  https://www.worldometers.info/debt/

🔗 实时全球股市/债市/外汇
  https://www.marketwatch.com/investing

🔗 加密货币实时行情
  https://www.coingecko.com/

## 权威媒体/深度研究

🔗 格隆汇 (全球宏观+深度研究) https://m.gelonghui.com/
🔗 Forisight News (加密/宏观前沿) https://foresightnews.pro/
🔗 证券时报 (A股/宏观深度) https://stcn.com/

## 中国启示研究

🔗 中国社会科学院《世界经济黄皮书》(每年12月)
🔗 兴业证券《全球资产配置白皮书》(每年1月)
🔗 中信证券《A股展望》(定期更新)

💡 关键提醒: 以上链接仅供参考, 内容不构成投资建议
"""
