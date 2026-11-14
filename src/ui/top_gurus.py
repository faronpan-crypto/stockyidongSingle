"""👥 大V榜 — A股交易体系总览
静态理论 + 动态活用：盘面诊断、风格判断、主线板块、候选股推荐
"""
import tkinter as _tk
import tkinter.ttk as _ttk
import webbrowser as _wb
import threading as _th
import time as _time

_BG = "#1A1A2E"
_PANEL = "#16213E"
_CARD = "#0F3460"
_FG = "#EAEAEA"
_MUTED = "#90A4AE"
_ACCENT = "#E94560"
_GOLD = "#FFD54F"
_GREEN = "#66BB6A"
_BLUE = "#64B5F6"

# ═══════════════════════════════════════════════════════
# 📦 数据层：一次拉全量 + 本地聚合，避免逐股频控
# ═══════════════════════════════════════════════════════
_CACHE = {"spot": (None, 0.0), "industry": (None, 0.0)}
_CACHE_TTL = 60  # 秒


def _open(url):
    try:
        _wb.open(url)
    except Exception:
        pass


def _link_label(parent, text, url):
    """蓝色可点击链接 Label（不布局，由调用方 pack/grid）"""
    lbl = _tk.Label(parent, text=text, fg=_BLUE, bg=parent["bg"],
                    font=("TkDefaultFont", 10, "underline"), cursor="hand2")
    lbl.bind("<Button-1>", lambda e, u=url: _open(u))
    lbl.bind("<Enter>", lambda e: lbl.config(fg="#FF8A65"))
    lbl.bind("<Leave>", lambda e: lbl.config(fg=_BLUE))
    return lbl


# ── 涨停/跌停阈值 ──
def _limit_pct(code):
    """主板±10%，科创/创业±20%，北交所±30%（先 strip sh/sz/bj 前缀）"""
    try:
        c = str(code).strip()
        # strip 交易所前缀
        for p in ("sh", "sz", "bj", "kc", "cy"):
            if c.startswith(p):
                c = c[len(p):]
                break
        c = c.zfill(6)
        if c.startswith(("30", "68")):
            return 20.0
        if c.startswith(("4", "8", "9")):
            return 30.0
    except Exception:
        pass
    return 10.0


def _fetch_spot():
    """📊 全 A 实时行情：东财全量 → 分市场 → 新浪兜底，60 秒缓存"""
    now = _time.time()
    df, ts = _CACHE["spot"]
    if df is not None and (now - ts) < _CACHE_TTL:
        return df
    try:
        import akshare as _ak
        import pandas as _pd
        dfs = []
        # 路径1: 东财全量
        try:
            part = _ak.stock_zh_a_spot_em()
            if part is not None and not part.empty and len(part) > 3000:
                dfs.append(part)
        except Exception:
            pass
        # 路径2: 东财分市场
        if not dfs:
            for fn in [_ak.stock_sh_a_spot_em, _ak.stock_sz_a_spot_em,
                       _ak.stock_kc_a_spot_em, _ak.stock_cy_a_spot_em,
                       _ak.stock_bj_a_spot_em]:
                try:
                    part = fn()
                    if part is not None and not part.empty:
                        dfs.append(part)
                except Exception:
                    continue
        # 路径3: 新浪兜底
        if not dfs:
            try:
                part = _ak.stock_zh_a_spot()
                if part is not None and not part.empty:
                    # 新浪列名不同，统一处理
                    dfs.append(part)
                    print(f"[👥大V榜] 新浪兜底成功: {len(part)} 只")
            except Exception as e:
                print(f"[👥大V榜] 新浪也失败: {e}")

        if dfs:
            df = _pd.concat(dfs, ignore_index=True)
            _CACHE["spot"] = (df, now)
            return df
        print("[👥大V榜❌] 所有行情源均失败")
        return None
    except Exception as e:
        print(f"[👥大V榜❌] 拉行情异常: {e}")
        return None


def _fetch_industry():
    """🏭 行业板块汇总（同花顺）"""
    now = _time.time()
    df, ts = _CACHE["industry"]
    if df is not None and (now - ts) < _CACHE_TTL:
        return df
    try:
        import akshare as _ak
        df = _ak.stock_board_industry_summary_ths()
        if df is not None and not df.empty:
            _CACHE["industry"] = (df, now)
        return df
    except Exception as e:
        print(f"[👥大V榜❌] 拉行业板块失败: {e}")
        return None


# ── 核心聚合：从全 A spot 计算市场诊断 ──
def _analyze_market(spot_df):
    """
    返回 dict:
      up_count, down_count, flat_count, limit_up, limit_down, tian_de_ban
      total_amount_yi, avg_change, rise_pct
      style: "大盘价值" / "小盘成长" / "均衡" / "数据不足"
      cycle_stage, cycle_score (0-100), position
    """
    if spot_df is None or spot_df.empty:
        return None
    df = spot_df.copy()
    HAS = {c: c in df.columns for c in
           ["涨跌幅", "成交额", "换手率", "振幅", "流通市值", "总市值", "代码"]}

    # 数值化
    for col in ["涨跌幅", "成交额", "换手率", "振幅", "流通市值", "总市值", "成交量"]:
        if HAS.get(col):
            df[col] = _pd_to_num(df[col])

    total = len(df)
    up = int((df["涨跌幅"] > 0).sum()) if HAS["涨跌幅"] else 0
    down = int((df["涨跌幅"] < 0).sum()) if HAS["涨跌幅"] else 0
    flat = total - up - down
    rise_pct = round(up / total * 100, 1) if total else 0
    avg_change = round(float(df["涨跌幅"].mean()), 2) if HAS["涨跌幅"] else 0

    # 涨停/跌停（逐股算阈值）
    limit_up = limit_down = tian_de_ban = 0
    if HAS["代码"] and HAS["涨跌幅"]:
        for _, row in df[["代码", "涨跌幅"]].dropna().iterrows():
            pct = _limit_pct(row["代码"])
            ch = row["涨跌幅"]
            if ch >= pct - 0.3:
                limit_up += 1
            elif ch <= -pct + 0.3:
                limit_down += 1
            if ch <= -9.5:
                tian_de_ban += 1

    # 成交额（亿）
    total_amount_yi = round(float(df["成交额"].sum()) / 1e8, 1) if HAS["成交额"] else 0

    # ── 风格判断：大盘 vs 小盘（有市值数据才判断） ──
    style = "📊 数据不足"
    mv_col = "流通市值" if HAS.get("流通市值") else ("总市值" if HAS.get("总市值") else None)
    if mv_col and HAS["涨跌幅"]:
        df_m = df[df[mv_col] > 0].copy()
        if len(df_m) > 100:
            n_top = max(1, int(len(df_m) * 0.2))
            top20 = df_m.nlargest(n_top, mv_col)["涨跌幅"].mean()
            bot20 = df_m.nsmallest(n_top, mv_col)["涨跌幅"].mean()
            diff = top20 - bot20
            if diff > 0.5:
                style = "🐘 大盘价值"
            elif diff < -0.5:
                style = "🚀 小盘成长"
            else:
                style = "⚖️ 均衡"
    elif HAS["成交额"] and HAS["涨跌幅"]:
        # 无市值时用成交额代理
        df_v = df[df["成交额"] > 0].copy()
        if len(df_v) > 100:
            n_top = max(1, int(len(df_v) * 0.2))
            top20 = df_v.nlargest(n_top, "成交额")["涨跌幅"].mean()
            bot20 = df_v.nsmallest(n_top, "成交额")["涨跌幅"].mean()
            diff = top20 - bot20
            if diff > 0.5:
                style = "🐘 大盘价值"
            elif diff < -0.5:
                style = "🚀 小盘成长"
            else:
                style = "⚖️ 均衡"

    # ── 情绪周期判定 ──
    ratio_score = min(30, max(0, (up / max(down, 1)) * 7.5))
    limit_score = min(25, limit_up * 1.25)
    down_penalty = min(0, -limit_down * 1.5)
    active_score = min(25, rise_pct * 0.5)
    td_penalty = min(0, -tian_de_ban * 3)
    score = max(0, min(100, ratio_score + limit_score + down_penalty + active_score + td_penalty))

    if score >= 75:
        stage = "🎯 高潮一致"; position = "≤ 20% 只卖不买"
    elif score >= 50:
        stage = "🔥 主升发酵"; position = "≥ 50% 重仓进攻"
    elif score >= 25:
        stage = "🧊 冰点试错"; position = "10-20% 小仓试探"
    else:
        stage = "📉 退潮主跌"; position = "强制空仓"

    return {
        "total": total, "up_count": up, "down_count": down, "flat_count": flat,
        "rise_pct": rise_pct, "avg_change": avg_change,
        "limit_up": limit_up, "limit_down": limit_down, "tian_de_ban": tian_de_ban,
        "total_amount_yi": total_amount_yi, "style": style,
        "cycle_stage": stage, "cycle_score": round(score), "position": position,
    }


def _pd_to_num(s):
    """pandas safe numeric convert"""
    try:
        import pandas as pd
        return pd.to_numeric(s, errors="coerce")
    except Exception:
        return s


def _find_mainline(spot_df, industry_df=None):
    """
    找出主线板块 + 适合不同风格的候选股（对缺失列容错）
    """
    if spot_df is None or spot_df.empty:
        return None
    df = spot_df.copy()
    HAS = {c: c in df.columns for c in
           ["涨跌幅", "成交额", "换手率", "振幅", "流通市值", "总市值"]}

    # 数值化
    for col in ["涨跌幅", "成交额", "换手率", "振幅", "流通市值", "总市值"]:
        if HAS.get(col):
            df[col] = _pd_to_num(df[col])

    # ── 行业板块聚合 ──
    industry_top = []
    if industry_df is not None and not industry_df.empty:
        try:
            idf = industry_df.copy()
            name_col = next((c for c in idf.columns if "名称" in c or "板块" in c), None)
            chg_col = next((c for c in idf.columns if "涨跌幅" in c or "涨幅" in c), None)
            amt_col = next((c for c in idf.columns if "成交额" in c), None)
            if name_col and chg_col:
                idf[chg_col] = _pd_to_num(idf[chg_col])
                if amt_col:
                    idf[amt_col] = _pd_to_num(idf[amt_col])
                for _, r in idf.nlargest(5, chg_col).iterrows():
                    # 同花顺成交额已是亿单位
                    amt_yi = round(float(r[amt_col]), 1) if amt_col and r[amt_col] else None
                    industry_top.append((str(r[name_col]), round(float(r[chg_col]), 2), amt_yi))
        except Exception as e:
            print(f"[👥大V榜] 行业聚合容错: {e}")

    # ── 候选股筛选 ──
    valid_cond = df["涨跌幅"].between(-25, 25) & (df["成交额"] > 0) if HAS["成交额"] and HAS["涨跌幅"] else None
    if valid_cond is None:
        valid_cond = df["涨跌幅"].between(-25, 25) if HAS["涨跌幅"] else _pd_to_num([True] * len(df))
    df_valid = df[valid_cond].dropna(subset=["涨跌幅"]) if HAS["涨跌幅"] else df.copy()

    mv_col = "流通市值" if HAS.get("流通市值") else ("总市值" if HAS.get("总市值") else None)
    use_turnover = HAS.get("换手率")

    # 短线：优先按换手率排序（有换手率），否则按成交额
    cd = df_valid.copy()
    if mv_col:
        cd = cd[cd[mv_col].between(50e8, 200e8)]
    cd_short = cd[cd["涨跌幅"] > 0] if HAS["涨跌幅"] else cd
    if use_turnover:
        cd_short = cd_short[cd_short["换手率"] > 3] if "换手率" in cd_short.columns else cd_short
        cd_short = cd_short.nlargest(10, "换手率")
    elif HAS.get("成交额"):
        cd_short = cd_short.nlargest(10, "成交额")
    else:
        cd_short = cd_short.head(10)

    # 中线：市值 100-500亿，成交额够
    cm = df_valid.copy()
    if mv_col:
        cm = cm[cm[mv_col].between(100e8, 500e8)]
    cm_mid = cm[cm["涨跌幅"].between(-8, 12)] if HAS["涨跌幅"] else cm
    if HAS.get("成交额"):
        cm_mid = cm_mid[cm_mid["成交额"] > 1e8]
        cm_mid = cm_mid.nlargest(10, "成交额")
    else:
        cm_mid = cm_mid.head(10)

    # 长线：大市值 + 成交额 Top
    cl = df_valid.copy()
    if mv_col:
        cl = cl[cl[mv_col] > 300e8]
    cl_long = cl.nlargest(10, mv_col) if mv_col else (
        cl.nlargest(10, "成交额") if HAS.get("成交额") else cl.head(10))

    def _pick_cols(df_in, cols):
        avail = [c for c in cols if c in df_in.columns]
        return df_in[avail].to_dict("records")

    def _fmt(recs):
        for r in recs:
            for k, v in list(r.items()):
                if isinstance(v, float) and v > 1e6:
                    r[k] = round(v / 1e8, 2)
                elif isinstance(v, float):
                    r[k] = round(v, 2)
        return recs

    return {
        "industry_top": industry_top,
        "candidates_duanxian": _fmt(_pick_cols(cd_short, ["代码", "名称", "涨跌幅", "成交额", "换手率"])),
        "candidates_zhongxian": _fmt(_pick_cols(cm_mid, ["代码", "名称", "涨跌幅", "成交额", "换手率"])),
        "candidates_changxian": _fmt(_pick_cols(cl_long, ["代码", "名称", "涨跌幅", "成交额", "流通市值"])),
    }


# ═══════════════════════════════════════════════════════
# 🖥️ UI 层
# ═══════════════════════════════════════════════════════
def _show_top_gurus_dialog(self):
    """👥 大V榜 主窗口"""
    win = _tk.Toplevel(getattr(self, 'root', None) or self)
    win.title("👥 大V榜 · A股交易体系总览")
    win.geometry("1160x820")
    win.configure(bg=_BG)
    win.minsize(900, 600)

    # ── 顶部标题栏 ──
    top = _tk.Frame(win, bg=_PANEL)
    top.pack(fill=_tk.X, padx=10, pady=(10, 6))
    _tk.Label(top, text="👥  大V榜 · A股交易体系总览  ",
              font=("TkDefaultFont", 15, "bold"),
              bg=_PANEL, fg=_ACCENT).pack(side=_tk.LEFT, padx=12, pady=8)

    # 状态标签（动态 Tab 用）
    status_lbl = _tk.Label(top, text="", bg=_PANEL, fg=_MUTED,
                           font=("TkDefaultFont", 9))
    status_lbl.pack(side=_tk.RIGHT, padx=12)

    # ── 字体调节 ──
    font_size = [10]
    def _fs_up(): font_size[0] = min(18, font_size[0] + 1); _rebuild_notebook()
    def _fs_dn(): font_size[0] = max(8, font_size[0] - 1); _rebuild_notebook()
    btn_frame = _tk.Frame(top, bg=_PANEL)
    btn_frame.pack(side=_tk.RIGHT, padx=6)
    for txt, cmd in [("A+", _fs_up), ("A-", _fs_dn)]:
        b = _tk.Button(btn_frame, text=txt, width=3, command=cmd,
                       bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
                       highlightbackground=_ACCENT, highlightthickness=2,
                       font=("TkDefaultFont", 9, "bold"))
        b.pack(side=_tk.LEFT, padx=2, pady=6)

    # ── Notebook ──
    nb = _ttk.Notebook(win)
    nb.pack(fill=_tk.BOTH, expand=True, padx=10, pady=(0, 10))
    style = _ttk.Style()
    try: style.theme_use("clam")
    except Exception: pass
    style.configure("Dark.TNotebook", background=_BG, borderwidth=0)
    style.configure("Dark.TNotebook.Tab", background=_PANEL, foreground=_MUTED,
                    padding=[14, 6], font=("TkDefaultFont", 10))
    style.map("Dark.TNotebook.Tab",
              background=[("selected", _CARD)], foreground=[("selected", _GOLD)])
    nb.configure(style="Dark.TNotebook")

    # ── 动态 Tab 的数据缓存（UI 模块级） ──
    _DYNAMIC_DATA = {"market": None, "mainline": None, "loading": False}

    # ══════════════════════════════════════════════════
    # 🔄 后台线程：拉数据 → 主线程更新 UI
    # ══════════════════════════════════════════════════
    def _async_refresh(ui_tabs):
        """后台拉取全A + 行业板块，计算市场诊断和主线"""
        if _DYNAMIC_DATA["loading"]:
            return
        _DYNAMIC_DATA["loading"] = True
        status_lbl.config(text="⏳ 拉取行情数据中...", fg=_GOLD)

        def _worker():
            try:
                spot = _fetch_spot()
                industry = _fetch_industry()
                market = _analyze_market(spot)
                mainline = _find_mainline(spot, industry)
                _DYNAMIC_DATA["market"] = market
                _DYNAMIC_DATA["mainline"] = mainline
                _DYNAMIC_DATA["loading"] = False
                # 回主线程更新
                win.after(0, lambda: _update_dynamic_tabs(ui_tabs))
            except Exception as e:
                import traceback as _tb
                _tb.print_exc()
                _DYNAMIC_DATA["loading"] = False
                win.after(0, lambda: status_lbl.config(
                    text=f"❌ 数据拉取失败: {e}", fg=_ACCENT))

        _th.Thread(target=_worker, daemon=True).start()

    def _update_dynamic_tabs(ui_tabs):
        _render_market_tab(ui_tabs["market"], _DYNAMIC_DATA["market"])
        _render_mainline_tab(ui_tabs["mainline"], _DYNAMIC_DATA["mainline"])
        status_lbl.config(text=f"✅ 数据更新于 {_time.strftime('%H:%M:%S')}", fg=_GREEN)

    # ============================================================
    # 📊 Tab 1: 四条主流路径（静态）
    # ============================================================
    def _build_tab_paths():
        tab = _tk.Frame(nb, bg=_BG)
        nb.add(tab, text="  📊 四条主流路径  ")
        _tk.Label(tab,
                  text="⚠️ 最容易亏钱的做法：用游资 1-3 天持仓逻辑，去扛自己扛不住波动的账户",
                  bg=_BG, fg="#FF8A65",
                  font=("TkDefaultFont", font_size[0], "bold")).pack(pady=(12, 8))

        cols = ("路径", "时间尺度", "选股标准", "代表人物")
        tv = _ttk.Treeview(tab, columns=cols, show="headings", height=10)
        for c, w in zip(cols, [160, 140, 380, 200]):
            tv.heading(c, text=c); tv.column(c, width=w, anchor="w")
        tv.pack(fill=_tk.X, padx=16, pady=6)
        for i, r in enumerate([
            ("⚡ 短线情绪博弈", "1–5 天", "主线总龙头，跟风股一概不碰", "陈小群 · 赵老哥 · 退学炒股"),
            ("🎯 逆向赔率", "1–3 年", "大幅下跌后逻辑清晰的公司", "冯柳 (高毅资产)"),
            ("📈 中线趋势景气", "1–2 年", "自下而上选择优质公司，不依赖择时", "朱少醒 (富国天惠)"),
            ("💎 长线价值", "5 年以上", "看得懂的生意 + 自由现金流", "段永平"),
        ]):
            tag = "odd" if i % 2 else "even"
            tv.insert("", "end", values=r, tags=(tag,))
        tv.tag_configure("even", background=_PANEL, foreground=_FG)
        tv.tag_configure("odd", background=_CARD, foreground=_FG)

        note_frame = _tk.Frame(tab, bg=_BG)
        note_frame.pack(fill=_tk.BOTH, expand=True, padx=16, pady=10)
        for emoji, title, desc in [
            ("⚡", "短线", "核心：只做主线只做总龙，拒绝杂毛。情绪周期定仓位。"),
            ("🎯", "逆向", "核心：市场错杀时捡便宜，接受「越跌越买」的波动。"),
            ("📈", "趋势", "核心：拥抱景气上行的行业和龙头，回撤就是上车机会。"),
            ("💎", "价值", "核心：买公司不是买股票，长期持有靠企业内生增长。"),
        ]:
            card = _tk.Frame(note_frame, bg=_CARD,
                             highlightthickness=1, highlightbackground="#455A64")
            card.pack(side=_tk.LEFT, fill=_tk.BOTH, expand=True, padx=4, pady=4)
            _tk.Label(card, text=f"{emoji}  {title}", bg=_CARD, fg=_GOLD,
                      font=("TkDefaultFont", font_size[0], "bold")).pack(anchor="w", padx=10, pady=(8, 2))
            _tk.Label(card, text=desc, bg=_CARD, fg=_FG, wraplength=200, justify="left",
                      font=("TkDefaultFont", font_size[0] - 1)).pack(anchor="w", padx=10, pady=(0, 10))
        return tab

    # ============================================================
    # 🔗 Tab 2: 可复用链接（静态）
    # ============================================================
    def _build_tab_links():
        tab = _tk.Frame(nb, bg=_BG)
        nb.add(tab, text="  🔗 可复用链接  ")
        _tk.Label(tab,
                  text="⚠️ 可信度提示：没有一位顶级游资公开过完整可审计的交割单；价值派数据相对靠谱（基金强制披露）",
                  bg=_BG, fg="#FF8A65", wraplength=1080, justify="left",
                  font=("TkDefaultFont", font_size[0], "bold")).pack(pady=(12, 8), padx=16, anchor="w")

        f1 = _tk.LabelFrame(tab, text=" ⚡ 游资短线派 ", bg=_BG, fg=_ACCENT,
                            font=("TkDefaultFont", font_size[0], "bold"))
        f1.pack(fill=_tk.X, padx=16, pady=6)
        for i, (title, url) in enumerate([
            ("陈小群 · 情绪周期 + 龙头战法完整拆解", "https://www.taoguba.com.cn/Article/689521/1"),
            ("七大游资风格对比（章盟主/赵老哥/方新侠等）", "https://xueqiu.com/9371964572/395707581"),
            ("退学炒股体系与心法", "https://xueqiu.com/9371964572/395707581"),
            ("华东大导弹 · 龙空龙体系", "https://www.taoguba.com.cn"),
        ]):
            row = _tk.Frame(f1, bg=_BG); row.pack(fill=_tk.X, padx=8, pady=2)
            _tk.Label(row, text=f"  {i+1}. ", bg=_BG, fg=_GOLD,
                      font=("TkDefaultFont", font_size[0], "bold")).pack(side=_tk.LEFT)
            _link_label(row, title, url).pack(side=_tk.LEFT)

        f2 = _tk.LabelFrame(tab, text=" 💎 逆向 & 价值派（可信度最高）", bg=_BG, fg=_GREEN,
                            font=("TkDefaultFont", font_size[0], "bold"))
        f2.pack(fill=_tk.X, padx=16, pady=6)
        for i, (title, url) in enumerate([
            ("冯柳 · 「弱者体系」原文（高毅资产官网）", "https://www.gaoyifund.com"),
            ("冯柳再谈方法论 · 寻找共识 依靠常识", "https://www.chinafundnews.com"),
            ("段永平 2026 年第三次加仓茅台 3 万股", "https://www.21jingji.com"),
        ]):
            row = _tk.Frame(f2, bg=_BG); row.pack(fill=_tk.X, padx=8, pady=2)
            _tk.Label(row, text=f"  {i+1}. ", bg=_BG, fg=_GOLD,
                      font=("TkDefaultFont", font_size[0], "bold")).pack(side=_tk.LEFT)
            _link_label(row, title, url).pack(side=_tk.LEFT)

        f3 = _tk.LabelFrame(tab, text=" 🆕 2026 新变量 ", bg=_BG, fg="#AB47BC",
                            font=("TkDefaultFont", font_size[0], "bold"))
        f3.pack(fill=_tk.X, padx=16, pady=6)
        for i, (title, url) in enumerate([
            ("量化私募规模突破 3 万亿，小微盘交易占比超 50%", "https://www.huashidai.com.cn"),
            ("极端风格切换：产业逻辑持仓比价格惯性模型更抗打", "https://www.cls.cn"),
        ]):
            row = _tk.Frame(f3, bg=_BG); row.pack(fill=_tk.X, padx=8, pady=2)
            _tk.Label(row, text=f"  {i+1}. ", bg=_BG, fg=_GOLD,
                      font=("TkDefaultFont", font_size[0], "bold")).pack(side=_tk.LEFT)
            _link_label(row, title, url).pack(side=_tk.LEFT)

        f4 = _tk.LabelFrame(tab, text=" 🏛️ 合规数据源（推荐）", bg=_BG, fg=_BLUE,
                            font=("TkDefaultFont", font_size[0], "bold"))
        f4.pack(fill=_tk.BOTH, expand=True, padx=16, pady=6)
        for title, desc in [
            ("📰 官方媒体", "证券时报 · 中国证券报 · 上海证券报 · 财联社 · 第一财经"),
            ("🏛️ 交易所/监管", "上交所 · 深交所 · 北交所 · 证监会官网公告"),
            ("📊 券商研究所", "各家研究所公开研报摘要与公众号（机构号，非个人）"),
        ]:
            row = _tk.Frame(f4, bg=_BG); row.pack(fill=_tk.X, padx=8, pady=4)
            _tk.Label(row, text=f"  {title}:", bg=_BG, fg=_GOLD, width=18, anchor="w",
                      font=("TkDefaultFont", font_size[0], "bold")).pack(side=_tk.LEFT)
            _tk.Label(row, text=desc, bg=_BG, fg=_FG,
                      font=("TkDefaultFont", font_size[0])).pack(side=_tk.LEFT)
        return tab

    # ============================================================
    # 🎯 Tab 3: 有个性的票（静态）
    # ============================================================
    def _build_tab_stock_quality():
        tab = _tk.Frame(nb, bg=_BG)
        nb.add(tab, text="  🎯 「有个性的票」  ")
        _tk.Label(tab, text="股性 = 5 个可量化指标（不需要别人推荐）",
                  bg=_BG, fg=_GOLD,
                  font=("TkDefaultFont", font_size[0] + 2, "bold")).pack(pady=(12, 8))
        for i, (num, name, val, desc, color) in enumerate([
            ("①", "流通市值", "50 – 200 亿", "太小容易被控盘，太大拉不动", _ACCENT),
            ("②", "日均成交额", "足够大", "保证进得去、出得来 — 流动性底线", _BLUE),
            ("③", "振幅 + 换手率", "高于同板块", "说明有资金在里面反复做，股性活跃", _GREEN),
            ("④", "明确题材归属", "带 ≥5 只同板块涨停", "政策/产业/事件驱动，能带动板块 — 总龙头硬标准", _GOLD),
            ("⑤", "辨识度高", "题材第一联想", "市场一提这个题材，第一个想到它", "#AB47BC"),
        ]):
            card = _tk.Frame(tab, bg=_PANEL, highlightthickness=1, highlightbackground=color)
            card.pack(fill=_tk.X, padx=16, pady=5)
            top_row = _tk.Frame(card, bg=_PANEL); top_row.pack(fill=_tk.X, padx=12, pady=(8, 2))
            _tk.Label(top_row, text=f"{num} {name}", bg=_PANEL, fg=color,
                      font=("TkDefaultFont", font_size[0] + 1, "bold")).pack(side=_tk.LEFT)
            _tk.Label(top_row, text=val, bg=_PANEL, fg=_GOLD,
                      font=("TkDefaultFont", font_size[0] + 1, "bold")).pack(side=_tk.RIGHT)
            _tk.Label(card, text=desc, bg=_PANEL, fg=_MUTED, wraplength=1000, justify="left",
                      font=("TkDefaultFont", font_size[0])).pack(anchor="w", padx=12, pady=(0, 8))
        exc = _tk.LabelFrame(tab, text=" ❌ 直接排除 ", bg=_BG, fg=_ACCENT,
                             font=("TkDefaultFont", font_size[0], "bold"))
        exc.pack(fill=_tk.X, padx=16, pady=10)
        for e in ["独立庄股（筹码高度集中，无板块联动）",
                  "过气老龙头（成交额长期萎缩，题材已退潮）",
                  "没有量能支撑的突破（缩量新高 = 诱多）",
                  "跟风杂毛（不是总龙头，靠龙头溢价跟风）"]:
            _tk.Label(exc, text=f"  ✖  {e}", bg=_BG, fg=_MUTED,
                      font=("TkDefaultFont", font_size[0])).pack(anchor="w", padx=8, pady=2)
        return tab

    # ============================================================
    # ⏰ Tab 4: 情绪周期（静态 + 动态映射）
    # ============================================================
    def _build_tab_cycle():
        tab = _tk.Frame(nb, bg=_BG)
        nb.add(tab, text="  ⏰ 情绪周期  ")
        _tk.Label(tab,
                  text="市场真正适合重仓的窗口非常少 — 一年仅 2-3 次主升窗口\n"
                       "华东大导弹 199 交易日：145 天空仓（73%），只做 40 笔交易，最大回撤 13.8%",
                  bg=_BG, fg=_GOLD, justify="center",
                  font=("TkDefaultFont", font_size[0], "bold")).pack(pady=(12, 10))

        cols = ("阶段", "量化特征", "仓位", "操作原则")
        tv = _ttk.Treeview(tab, columns=cols, show="headings", height=6)
        for c, w in zip(cols, [140, 340, 120, 380]):
            tv.heading(c, text=c); tv.column(c, width=w, anchor="w")
        tv.pack(fill=_tk.X, padx=16, pady=6)
        for i, r in enumerate([
            ("🧊 冰点试错", "全市场连板 < 3 家，亏钱效应还在", "10% – 20%", "小仓试错，不追高"),
            ("🔥 主升发酵", "板块批量涨停，连板 10-15 家", "≥ 50%", "核心仓位上总龙头"),
            ("🎯 高潮一致", "连板 > 15 只，龙头缩量加速", "≤ 20%", "只卖不买，分批止盈"),
            ("📉 退潮主跌", "天地板频发、炸板潮", "强制空仓", "管住手，不抄下降中飞刀"),
        ]):
            tv.insert("", "end", values=r, tags=(f"s{i}",))
            tv.tag_configure(f"s{i}", background=_PANEL if i % 2 else _CARD,
                             foreground=[_BLUE, _ACCENT, _GOLD, "#B0BEC5"][i])

        bottom = _tk.Frame(tab, bg=_BG); bottom.pack(fill=_tk.BOTH, expand=True, padx=16, pady=(0, 10))
        for pct, label, color in [("20%", "时间", _MUTED), ("80%", "收益", _GOLD)]:
            card = _tk.Frame(bottom, bg=_CARD, highlightthickness=1, highlightbackground=color)
            card.pack(side=_tk.LEFT, fill=_tk.BOTH, expand=True, padx=4)
            _tk.Label(card, text=pct, bg=_CARD, fg=color,
                      font=("TkDefaultFont", font_size[0] + 8, "bold")).pack(pady=(10, 0))
            _tk.Label(card, text=f"的交易贡献了\n{label}", bg=_CARD, fg=_FG, justify="center",
                      font=("TkDefaultFont", font_size[0])).pack(pady=(0, 10))
        return tab

    # ============================================================
    # 🎲 Tab 5: 盘面诊断（动态）
    # ============================================================
    market_tab_frame = {"root": None, "widgets": {}}  # 存控件引用用于刷新

    def _build_tab_market():
        tab = _tk.Frame(nb, bg=_BG)
        nb.add(tab, text="  🎲 盘面诊断  ")
        market_tab_frame["root"] = tab

        # 刷新按钮
        ref_row = _tk.Frame(tab, bg=_BG)
        ref_row.pack(fill=_tk.X, padx=16, pady=(12, 8))
        _tk.Label(ref_row, text="实时判断当前盘面状态 → 映射到情绪周期四阶段",
                  bg=_BG, fg=_GOLD,
                  font=("TkDefaultFont", font_size[0], "bold")).pack(side=_tk.LEFT)
        _tk.Button(ref_row, text="🔄 刷新盘面数据",
                   command=lambda: _async_refresh({"market": tab, "mainline": main_tab_frame["root"]}),
                   bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
                   highlightbackground=_ACCENT, highlightthickness=2,
                   font=("TkDefaultFont", font_size[0], "bold")).pack(side=_tk.RIGHT)

        # 仪表盘区域（占位，刷新时填入）
        gauge = _tk.Frame(tab, bg=_BG)
        gauge.pack(fill=_tk.X, padx=16, pady=6)
        market_tab_frame["widgets"]["gauge"] = gauge

        # 指标明细区
        detail = _tk.Frame(tab, bg=_BG)
        detail.pack(fill=_tk.X, padx=16, pady=6)
        market_tab_frame["widgets"]["detail"] = detail

        # 建议区
        advice = _tk.LabelFrame(tab, text=" 💡 操作建议 ", bg=_BG, fg=_GOLD,
                                font=("TkDefaultFont", font_size[0], "bold"))
        advice.pack(fill=_tk.BOTH, expand=True, padx=16, pady=10)
        market_tab_frame["widgets"]["advice"] = advice

        # 初始提示
        _render_market_tab(tab, None)
        return tab

    def _render_market_tab(tab, data):
        # 清空
        w = market_tab_frame["widgets"]
        for area_key in ["gauge", "detail", "advice"]:
            area = w.get(area_key)
            if area:
                for c in area.winfo_children():
                    c.destroy()

        if data is None:
            _tk.Label(w["gauge"],
                      text="⏳ 点右上角 🔄 刷新盘面数据\n\n"
                           "首次会拉取全 A 实时行情（约 1-3 秒）",
                      bg=_BG, fg=_MUTED, justify="center",
                      font=("TkDefaultFont", font_size[0] + 2)).pack(pady=40)
            return

        # ── 仪表盘：情绪得分 ──
        score = data["cycle_score"]
        if score >= 75:
            gauge_color = _GOLD; stage = data["cycle_stage"]; emoji = "🎯"
        elif score >= 50:
            gauge_color = _ACCENT; stage = data["cycle_stage"]; emoji = "🔥"
        elif score >= 25:
            gauge_color = _BLUE; stage = data["cycle_stage"]; emoji = "🧊"
        else:
            gauge_color = "#B0BEC5"; stage = data["cycle_stage"]; emoji = "📉"

        card = _tk.Frame(w["gauge"], bg=_PANEL,
                         highlightthickness=2, highlightbackground=gauge_color)
        card.pack(fill=_tk.X, pady=4)
        _tk.Label(card, text=f"{emoji}  当前情绪阶段：{stage}",
                  bg=_PANEL, fg=gauge_color,
                  font=("TkDefaultFont", font_size[0] + 4, "bold")).pack(pady=(12, 4))
        _tk.Label(card, text=f"情绪得分 {score} / 100   |   建议仓位：{data['position']}",
                  bg=_PANEL, fg=_FG,
                  font=("TkDefaultFont", font_size[0] + 1)).pack(pady=(0, 12))
        # 分数条
        bar = _tk.Frame(card, bg=_BG, height=10)
        bar.pack(fill=_tk.X, padx=30, pady=(0, 12))
        _tk.Frame(bar, bg=gauge_color, height=10).place(relx=0, rely=0, relwidth=score / 100, relheight=1)

        # ── 市场指标明细（6 指标卡） ──
        metrics = [
            ("📊 上涨 / 下跌", f"{data['up_count']} / {data['down_count']}",
             f"平盘 {data['flat_count']}   上涨占比 {data['rise_pct']}%", _GREEN if data['up_count'] > data['down_count'] else _ACCENT),
            ("📈 平均涨跌幅", f"{data['avg_change']:+.2f}%",
             f"全 {data['total']} 只 A 股", _ACCENT if data['avg_change'] > 0 else _GREEN),
            ("🔴 涨停 / 跌停", f"{data['limit_up']} / {data['limit_down']}",
             f"天地板 {data['tian_de_ban']} 只", _ACCENT if data['limit_down'] > 5 else _GREEN),
            ("💰 全市场成交额", f"{data['total_amount_yi']:,} 亿",
             "流动性判断依据", _GOLD),
            ("🎭 当前风格", data['style'],
             "大盘 vs 小盘 涨幅对比", _BLUE),
            ("🎯 匹配交易路径", _match_path(data),
             "按当前盘面选适合的路径", "#AB47BC"),
        ]
        for i, (title, val, sub, color) in enumerate(metrics):
            mcard = _tk.Frame(w["detail"], bg=_CARD,
                              highlightthickness=1, highlightbackground=color)
            mcard.grid(row=i // 3, column=i % 3, sticky="nsew", padx=4, pady=4)
            w["detail"].columnconfigure(i % 3, weight=1)
            _tk.Label(mcard, text=title, bg=_CARD, fg=_MUTED,
                      font=("TkDefaultFont", font_size[0])).pack(pady=(8, 0))
            _tk.Label(mcard, text=val, bg=_CARD, fg=color,
                      font=("TkDefaultFont", font_size[0] + 4, "bold")).pack(pady=(0, 0))
            _tk.Label(mcard, text=sub, bg=_CARD, fg=_MUTED,
                      font=("TkDefaultFont", font_size[0] - 1)).pack(pady=(0, 8))

        # ── 操作建议 ──
        advice_text = _build_advice(data)
        _tk.Label(w["advice"], text=advice_text, bg=_BG, fg=_FG,
                  wraplength=1060, justify="left",
                  font=("TkDefaultFont", font_size[0] + 1)).pack(anchor="w", padx=10, pady=10)

    def _match_path(data):
        """根据盘面匹配 4 条路径里当前最适合的"""
        score = data["cycle_score"]
        style = data["style"]
        if score >= 50 and style == "🚀 小盘成长":
            return "⚡ 短线情绪博弈"
        elif score < 25 and data['down_count'] > data['up_count'] * 1.5:
            return "🎯 逆向赔率 (冯柳)"
        elif style == "🐘 大盘价值":
            return "💎 长线价值 (段永平)"
        else:
            return "📈 中线趋势景气"

    def _build_advice(data):
        lines = []
        score = data["cycle_score"]
        lines.append(f"【当前阶段】{data['cycle_stage']}（得分 {score}）")
        lines.append(f"【建议仓位】{data['position']}")
        lines.append(f"【风格判断】{data['style']}")
        lines.append("")
        if score >= 75:
            lines.append("⚠️ 高潮一致阶段 — 只卖不买！龙头缩量加速意味着博弈进入最后阶段。")
            lines.append("   如果持仓浮盈厚，分批止盈；如果空仓，忍住不要追。")
        elif score >= 50:
            lines.append("✅ 主升发酵阶段 — 可以积极进攻。只做主线总龙头，跟风股只看不买。")
            lines.append("   警惕盘中分歧，第一次大分歧往往是上车机会（龙头回踩不破关键位）。")
        elif score >= 25:
            lines.append("🧊 冰点试错阶段 — 小仓试探，观察龙头诞生信号。")
            lines.append("   如果龙头首阴后能反包，说明行情延续；首阴被按跌停就是退潮信号。")
        else:
            lines.append("📉 退潮主跌阶段 — 管住手！空仓是最好的策略。")
            lines.append("   华东大导弹 73% 时间空仓，一年只做 40 笔交易。等待下一个冰点。")
        return "\n".join(lines)

    # ============================================================
    # 📈 Tab 6: 主线板块 & 候选股（动态）
    # ============================================================
    main_tab_frame = {"root": None, "widgets": {}}

    def _build_tab_mainline():
        tab = _tk.Frame(nb, bg=_BG)
        nb.add(tab, text="  📈 主线板块 · 候选股  ")
        main_tab_frame["root"] = tab

        ref_row = _tk.Frame(tab, bg=_BG)
        ref_row.pack(fill=_tk.X, padx=16, pady=(12, 8))
        _tk.Label(ref_row,
                  text="从全 A 实时行情聚合：主线板块 + 短线/中线/长线候选股",
                  bg=_BG, fg=_GOLD,
                  font=("TkDefaultFont", font_size[0], "bold")).pack(side=_tk.LEFT)
        _tk.Button(ref_row, text="🔄 刷新主线数据",
                   command=lambda: _async_refresh({"market": market_tab_frame["root"], "mainline": tab}),
                   bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
                   highlightbackground=_ACCENT, highlightthickness=2,
                   font=("TkDefaultFont", font_size[0], "bold")).pack(side=_tk.RIGHT)

        # 主线板块区
        ind_frame = _tk.LabelFrame(tab, text=" 🏭 行业主线 Top5（涨幅排名）", bg=_BG, fg=_ACCENT,
                                   font=("TkDefaultFont", font_size[0], "bold"))
        ind_frame.pack(fill=_tk.X, padx=16, pady=6)
        main_tab_frame["widgets"]["ind"] = ind_frame

        # 候选股区（3 种风格并列）
        can_frame = _tk.Frame(tab, bg=_BG)
        can_frame.pack(fill=_tk.BOTH, expand=True, padx=16, pady=6)
        main_tab_frame["widgets"]["can"] = can_frame

        _render_mainline_tab(tab, None)
        return tab

    def _render_mainline_tab(tab, data):
        w = main_tab_frame["widgets"]
        # 清空
        for c in w["ind"].winfo_children(): c.destroy()
        for c in w["can"].winfo_children(): c.destroy()

        if data is None:
            _tk.Label(w["ind"], text="⏳ 点 🔄 刷新主线数据",
                      bg=_BG, fg=_MUTED,
                      font=("TkDefaultFont", font_size[0] + 2)).pack(pady=20)
            return

        # ── 行业主线 Top5 ──
        industry_top = data.get("industry_top", [])
        if industry_top:
            cols = ("排名", "行业", "涨跌幅", "成交额(亿)")
            tv_ind = _ttk.Treeview(w["ind"], columns=cols, show="headings", height=5)
            for c, w_ in zip(cols, (60, 300, 120, 140)):
                tv_ind.heading(c, text=c); tv_ind.column(c, width=w_, anchor="w")
            tv_ind.pack(fill=_tk.X, padx=8, pady=6)
            for i, (name, chg, amt) in enumerate(industry_top):
                tv_ind.insert("", "end",
                              values=(f"#{i+1}", name, f"{chg:+.2f}%",
                                      f"{amt}" if amt else "-"))
        else:
            _tk.Label(w["ind"], text="⚠️ 行业数据暂不可用（同花顺接口可能失败）",
                      bg=_BG, fg=_ACCENT,
                      font=("TkDefaultFont", font_size[0])).pack(pady=10)

        # ── 候选股：短线 / 中线 / 长线 ──
        styles = [
            ("⚡ 短线候选 (换手率 Top · 市值50-200亿)", data.get("candidates_duanxian", []),
             ("代码", "名称", "涨跌幅%", "成交额亿", "换手率%"),
             _ACCENT),
            ("📈 中线候选 (市值100-500亿 · 成交额Top)", data.get("candidates_zhongxian", []),
             ("代码", "名称", "涨跌幅%", "成交额亿", "换手率%"),
             _BLUE),
            ("💎 长线候选 (大市值龙头 · 成交额稳定)", data.get("candidates_changxian", []),
             ("代码", "名称", "涨跌幅%", "成交额亿", "流通市值亿"),
             _GREEN),
        ]
        for i, (title, records, col_labels, color) in enumerate(styles):
            sub = _tk.LabelFrame(w["can"], text=f" {title} ", bg=_BG, fg=color,
                                 font=("TkDefaultFont", font_size[0], "bold"))
            sub.grid(row=i // 3, column=i % 3, sticky="nsew", padx=4, pady=4)
            w["can"].columnconfigure(i % 3, weight=1)

            if not records:
                _tk.Label(sub, text="暂无符合条件个股", bg=_BG, fg=_MUTED,
                          font=("TkDefaultFont", font_size[0] - 1)).pack(pady=10)
                continue

            tv_can = _ttk.Treeview(sub, columns=col_labels, show="headings", height=8)
            for c in col_labels:
                tv_can.heading(c, text=c); tv_can.column(c, width=90, anchor="w")
            tv_can.pack(fill=_tk.BOTH, expand=True, padx=4, pady=4)
            for rec in records:
                vals = []
                for c in col_labels:
                    raw = rec.get(c, rec.get({"代码": "代码", "名称": "名称",
                                               "涨跌幅%": "涨跌幅", "成交额亿": "成交额",
                                               "换手率%": "换手率", "流通市值亿": "流通市值"}[c], "-"))
                    if isinstance(raw, float):
                        vals.append(f"{raw:.2f}")
                    else:
                        vals.append(str(raw))
                tv_can.insert("", "end", values=vals)

    # ── 重建 Notebook ──
    def _rebuild_notebook():
        for tab in nb.tabs(): nb.forget(tab)
        for child in nb.winfo_children(): child.destroy()
        _build_tab_paths(); _build_tab_links()
        _build_tab_stock_quality(); _build_tab_cycle()
        _build_tab_market(); _build_tab_mainline()

    # 初始构建
    _build_tab_paths(); _build_tab_links()
    _build_tab_stock_quality(); _build_tab_cycle()
    _build_tab_market(); _build_tab_mainline()

    # 自动触发一次数据拉取（延迟 0.5s 让 UI 先加载）
    win.after(500, lambda: _async_refresh({"market": market_tab_frame["root"],
                                           "mainline": main_tab_frame["root"]}))

    # ── 底部免责声明 ──
    footer = _tk.Frame(win, bg=_PANEL)
    footer.pack(fill=_tk.X, padx=10, pady=(0, 10))
    _tk.Label(footer,
              text="⚠️ 免责声明：以上内容基于公开行情数据实时计算，仅供研究参考，不构成投资建议。市场有风险，投资需谨慎。",
              bg=_PANEL, fg=_MUTED, wraplength=1100, justify="center",
              font=("TkDefaultFont", 9)).pack(padx=10, pady=6)
